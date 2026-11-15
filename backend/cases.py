"""Individual Mendeley visits and the local recommendation index."""
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

from .domain import CATEGORIES, MODES, REGIONS

CASE_VERSION = "mendeley-h58s544674-v1-cbr-4"


@dataclass(frozen=True, slots=True)
class Visit:
    case_id: str
    transaction_id: int
    reviewer: int
    destination_id: int
    region: str
    category: str
    mode: str
    year: int
    month: int
    rating: int


def visit_records(frame):
    # The ordinal is local to this source snapshot and never sent to the browser.
    reviewers = {user: index for index, user in enumerate(sorted(frame.UserId.unique()), 1)}
    return [
        {
            "case_id": hashlib.sha256(f"mendeley:h58s544674:1:{row.TransactionId}".encode()).hexdigest(),
            "transaction_id": int(row.TransactionId),
            "reviewer": reviewers[row.UserId],
            "destination_id": int(row.AttractionId),
            "region": row.region, "category": row.category, "mode": row.mode,
            "year": int(row.VisitYear), "month": int(row.VisitMonth), "rating": int(row.Rating),
        }
        for row in frame.sort_values("TransactionId").itertuples()
    ]


class CaseIndex:
    def __init__(self, records, places, minimum, prior_weight):
        self.places = {place["id"]: place for place in places}
        self.minimum = minimum
        self.prior_weight = prior_weight
        self.by_place = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        historical = defaultdict(lambda: defaultdict(list))
        seen = set()
        for record in records:
            visit = Visit(**record)
            if (visit.case_id in seen or visit.region not in REGIONS or visit.category not in CATEGORIES
                    or visit.mode not in MODES or visit.month not in range(1, 13)
                    or visit.rating not in range(1, 6)):
                raise ValueError("Kasus kunjungan tidak valid.")
            seen.add(visit.case_id)
            place = self.places.get(visit.destination_id)
            if place is None:
                continue
            if (visit.region, visit.category) != (place["region"], place["category"]):
                raise ValueError("Konteks kasus berbeda dari katalog.")
            self.by_place[visit.destination_id][visit.mode][visit.reviewer].append(visit)
            historical[visit.destination_id][visit.reviewer].append(visit.rating)
        if set(self.by_place) != set(self.places):
            raise ValueError("Basis kasus aktif tidak lengkap.")
        self.priors = {
            place_id: mean(mean(ratings) for ratings in reviewers.values())
            for place_id, reviewers in historical.items()
        }
        self.support = {(place_id, mode): len(reviewers)
                        for place_id, modes in self.by_place.items()
                        for mode, reviewers in modes.items()}

    def candidates(self, answers):
        region, category = answers["region"], answers["category"]
        return [
            place for place in self.places.values()
            if region in ("all", place["region"])
            and (category in ("all", place["category"])
                 or (category == "nature" and place["category"] == "waterfall"))
        ]

    def has_match(self, answers):
        return any(self.support.get((place["id"], answers["mode"]), 0) >= self.minimum
                   for place in self.candidates(answers))

    def evidence(self, place_id, mode):
        reviewers = self.by_place[place_id].get(mode, {})
        ratings = {key: mean(visit.rating for visit in visits) for key, visits in reviewers.items()}
        return reviewers, ratings

    def recommend(self, answers, *, examples=True):
        mode = answers["mode"]
        candidates = []
        reviewers_seen, reviewers_matched = set(), set()
        total = matched = 0
        for place in self.candidates(answers):
            place_id = place["id"]
            for reviewers in self.by_place[place_id].values():
                reviewers_seen.update(reviewers)
                total += sum(map(len, reviewers.values()))
            reviewers, ratings = self.evidence(place_id, mode)
            visits = sum(map(len, reviewers.values()))
            matched += visits
            reviewers_matched.update(reviewers)
            n = len(ratings)
            similar_mean = mean(ratings.values()) if n else None
            prior = self.priors[place_id]
            eligible = n >= self.minimum
            candidates.append({
                "id": place_id, "name": place["name"], "count": n, "visit_count": visits,
                "similar_mean": similar_mean, "historical_mean": prior,
                "status": "eligible" if eligible else "below_support" if n else "no_matching_cases",
                "score": (n * similar_mean + self.prior_weight * prior) / (n + self.prior_weight)
                if eligible else None,
            })
        ranking = sorted((item for item in candidates if item["status"] == "eligible"),
                         key=lambda item: (-item["score"], -item["count"], item["id"]))
        trace = {
            "policy_version": CASE_VERSION, "evidence_type": "individual",
            "matching_places": len(candidates), "eligible_places": len(ranking),
            "min_reviewers": self.minimum, "prior_weight": self.prior_weight,
            "visit_count": total, "unique_reviewers": len(reviewers_seen),
            "matched_visit_count": matched, "matched_unique_reviewers": len(reviewers_matched),
            "similarity": {"0": total - matched, "1": matched, "threshold": 1},
            "candidates": candidates, "ranking": ranking,
        }
        if not ranking:
            trace["reason"] = ("no_places" if not candidates else "no_matching_cases"
                               if not matched else "below_support")
            return None, trace

        winner = ranking[0]
        place = self.places[winner["id"]]
        reviewers, ratings = self.evidence(place["id"], mode)
        evidence = []
        if examples:
            selected = sorted(
                (min(reviewers[key], key=lambda v: (v.year, v.month, v.transaction_id))
                 for key in sorted(reviewers)[:3]),
                key=lambda v: (v.year, v.month, v.transaction_id),
            )
            evidence = [{
                "label": f"Kasus {index:02}", "year": visit.year, "month": visit.month,
                "mode": MODES[mode], "rating": visit.rating, "similarity": 1,
                "reviewer_visit_count": len(reviewers[visit.reviewer]),
                "reviewer_mean": ratings[visit.reviewer],
            } for index, visit in enumerate(selected, 1)]
        trace.update(reviewer_count=winner["count"], winner_visit_count=winner["visit_count"],
                     similar_mean=winner["similar_mean"], historical_mean=winner["historical_mean"],
                     score=winner["score"], examples=evidence,
                     similar_sum=winner["count"] * winner["similar_mean"])
        return {
            "id": place["id"], "name": place["name"], "region": place["region"],
            "category": CATEGORIES[place["category"]], "reviewer_count": winner["count"],
        }, trace


def load_individual(path):
    artifact = json.loads(path.read_text(encoding="utf-8"))
    if artifact["version"] != CASE_VERSION:
        raise ValueError("Versi basis kasus tidak sesuai.")
    minimum, weight = artifact["policy"]["minimum"], artifact["policy"]["prior_weight"]
    if minimum not in (3, 5, 10, 15) or weight not in (0, 5, 10, 20):
        raise ValueError("Konfigurasi CBR tidak valid.")
    index = CaseIndex(artifact["cases"], artifact["places"], minimum, weight)
    active = sum(len(visits) for modes in index.by_place.values()
                 for reviewers in modes.values() for visits in reviewers.values())
    if (active != artifact["audit"]["active_visits"]
            or len(artifact["cases"]) != artifact["audit"]["clean_visits"]):
        raise ValueError("Jumlah kasus berbeda dari audit.")
    return artifact, index
