"""Build the local case base from Mendeley v1 and evaluate on unseen reviewers."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .domain import CATEGORIES, DATA_VERSION, MIN_REVIEWERS, MODES, REGIONS
from .engine import recommend, score

ROOT = Path(__file__).resolve().parents[1]
REGION_IDS = {1: "bali", 2: "malang", 3: "yogyakarta"}
MODE_IDS = dict(enumerate(MODES, 1))
TYPE_IDS = {
    2: "culture", 10: "culture", 13: "nature", 19: "nature", 34: "recreation",
    44: "culture", 45: "culture", 61: "nature", 63: "nature", 64: "culture",
    72: "culture", 76: "culture", 82: "recreation", 84: "culture",
    91: "volcano", 92: "recreation", 93: "waterfall",
}
DISPLAY_NAMES = {"Merapi Volcano": "Gunung Merapi", "Coban Rondo Waterfall": "Air Terjun Coban Rondo"}
VISIT_KEY = ["UserId", "AttractionId", "VisitYear", "VisitMonth", "VisitMode"]


def read_source(source):
    names = ["Transaction", "Item", "User", "City", "Mode", "Type"]
    paths = {name: source / f"{name}.xlsx" for name in names}
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths.values()}
    tables = {name: pd.read_excel(path) for name, path in paths.items()}
    return tables, hashes


def clean(tables):
    visits, places = tables["Transaction"], tables["Item"].copy()
    references = [
        (visits.UserId, tables["User"].UserId),
        (visits.AttractionId, places.AttractionId),
        (visits.VisitMode, tables["Mode"].VisitModeId),
        (places.AttractionTypeId, tables["Type"].AttractionTypeId),
    ]
    if any(target.duplicated().any() or not values.isin(target).all() for values, target in references):
        raise ValueError("Kunci atau referensi sumber tidak valid.")
    if (visits.TransactionId.duplicated().any() or visits.isna().any().any()
            or not visits.Rating.isin(range(1, 6)).all()
            or not visits.VisitMonth.isin(range(1, 13)).all()
            or not visits.VisitMode.isin(MODE_IDS).all()):
        raise ValueError("Nilai transaksi di luar skema sumber.")
    unique = visits.drop_duplicates(subset=VISIT_KEY + ["Rating"])
    conflict = unique.groupby(VISIT_KEY).Rating.transform("nunique").gt(1)
    cleaned = unique.loc[~conflict].copy()
    places["region"] = places.AttractionCityId.map(REGION_IDS)
    places["category"] = places.AttractionTypeId.map(TYPE_IDS)
    places["name"] = places.Attraction.replace(DISPLAY_NAMES)
    if places[["region", "category", "name", "AttractionAddress"]].isna().any().any():
        raise ValueError("Katalog belum sepenuhnya dipetakan.")
    cleaned = cleaned.merge(places, on="AttractionId", validate="many_to_one")
    cleaned["mode"] = cleaned.VisitMode.map(MODE_IDS)
    audit = {
        "raw_visits": len(visits),
        "duplicates_removed": len(visits) - len(unique),
        "conflicting_rows_removed": int(conflict.sum()),
        "clean_visits": len(cleaned),
        "clean_reviewers": int(cleaned.UserId.nunique()),
        "visits_by_region": cleaned.groupby("region").size().to_dict(),
        "catalog": places[["AttractionId", "AttractionCityId", "Attraction", "AttractionAddress",
                           "AttractionTypeId", "region", "category", "name"]].to_dict("records"),
    }
    if (len(visits), len(places), len(cleaned)) != (52930, 30, 47156):
        raise ValueError("Jumlah baris berbeda dari audit Mendeley versi 1.")
    return cleaned, audit


def build_case_base(visits):
    catalog = []
    for attraction_id, rows in visits.groupby("AttractionId"):
        cases = rows.groupby(["mode", "UserId"]).Rating.mean()
        first = rows.iloc[0]
        groups = {}
        for mode, ratings in cases.groupby(level="mode"):
            # Choose distinct reviewers in a stable, rating-independent order.
            groups[mode] = {"count": len(ratings), "mean": float(ratings.mean()),
                            "examples": []}
            if {"VisitYear", "VisitMonth"} <= set(rows.columns):
                examples = rows[(rows["mode"] == mode) & rows.UserId.isin(ratings.head(3).index.get_level_values("UserId"))]
                examples = examples.sort_values(["VisitYear", "VisitMonth", "TransactionId"]).drop_duplicates("UserId")
                groups[mode]["examples"] = [
                    {"year": int(row.VisitYear), "month": int(row.VisitMonth), "rating": int(row.Rating)}
                    for row in examples.itertuples()
                ]
        catalog.append({
            "id": int(attraction_id), "name": first["name"], "region": first["region"],
            "category": first["category"], "groups": groups,
            "historical_mean": float(rows.groupby("UserId").Rating.mean().mean()),
        })
    return catalog


def coverage(catalog):
    report = {}
    for region in REGIONS:
        report[region] = {}
        for mode in MODES:
            supported = sum(
                recommend(catalog, {"region": region, "mode": mode, "category": category})[0] is not None
                for category in CATEGORIES
            )
            report[region][mode] = {"supported": supported, "scenarios": len(CATEGORIES)}
    return report


def evaluate(visits):
    reviewers = pd.Series(sorted(visits.UserId.unique()))
    test_users = set(reviewers.sample(frac=0.2, random_state=42))
    held_out = visits.UserId.isin(test_users)
    catalog = build_case_base(visits.loc[~held_out])
    by_place = {place["id"]: place for place in catalog}
    eligible_test = []
    test = visits.loc[held_out].groupby(["UserId", "AttractionId", "region", "mode"]).Rating.mean()
    for (_, attraction_id, region, mode), observed in test.items():
        place = by_place.get(attraction_id)
        group = place["groups"].get(mode) if place else None
        if group and group["count"] >= MIN_REVIEWERS:
            baseline = place["historical_mean"]
            estimate = score(group["count"], group["mean"], baseline)
            eligible_test.append((region, mode, abs(estimate - observed), abs(baseline - observed)))
    errors = pd.DataFrame(eligible_test, columns=["region", "mode", "cbr", "baseline"])

    def metrics(rows):
        return {
            "cases": len(rows),
            "cbr_mae": float(rows.cbr.mean()) if len(rows) else None,
            "baseline_mae": float(rows.baseline.mean()) if len(rows) else None,
        }

    return {
        "seed": 42, "train_reviewers": len(reviewers) - len(test_users),
        "test_reviewers": len(test_users), "held_out_cases": len(test),
        "overall": metrics(errors),
        "by_region_mode": {
            region: {mode: metrics(errors[(errors.region == region) & (errors["mode"] == mode)])
                     for mode in MODES}
            for region in REGIONS
        },
        "training_coverage": coverage(catalog),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    tables, hashes = read_source(args.source)
    visits, audit = clean(tables)
    active = visits[visits.region.isin(REGIONS)]
    excluded = {
        947: "Akses pendakian terkini perlu dikonfirmasi.",
        949: "Museum dilaporkan tutup permanen.",
        975: "Cagar alam, wisata umum dilarang.",
    }
    active = active[~active.AttractionId.isin(excluded)]
    places = build_case_base(active)
    audit["excluded_from_recommendations"] = excluded
    audit["source_sha256"] = hashes
    evaluation = evaluate(active)
    evaluation["serving_coverage"] = coverage(places)
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    artifact = {"version": DATA_VERSION, "places": places, "audit": audit, "evaluation": evaluation}
    (artifacts / "cbr.json").write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(evaluation["overall"]))


if __name__ == "__main__":
    main()
