"""Reproduce the legacy baseline and compare the individual-case policy."""
import argparse
import hashlib
import json
import os
from tempfile import NamedTemporaryFile
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from .cases import CASE_VERSION, CaseIndex, visit_records
from .domain import CATEGORIES, MODES, REGIONS, MIN_REVIEWERS, PRIOR_WEIGHT
from .engine import recommend as legacy_recommend
from .train import build_case_base, clean, read_source

GRID = list(product(("all", *REGIONS), MODES, CATEGORIES))
GROUP = ["AttractionId", "mode"]
TARGET = ["UserId", "AttractionId", "region", "mode"]
LEGACY = (MIN_REVIEWERS, PRIOR_WEIGHT)
EXCLUDED = (947, 949, 975)


def user_split(visits, seed):
    users = pd.Series(sorted(visits.UserId.unique()))
    test = visits.UserId.isin(users.sample(frac=.2, random_state=seed))
    return visits.loc[~test], visits.loc[test]


def load(source):
    tables, hashes = read_source(source)
    visits, audit = clean(tables)
    excluded = visits[visits.AttractionId.isin(EXCLUDED)]
    active = visits[visits.region.isin(REGIONS) & ~visits.AttractionId.isin(EXCLUDED)]
    audit.update(source_sha256=hashes, active_visits=len(active),
                 active_reviewers=active.UserId.nunique(),
                 active_places=active.AttractionId.nunique(),
                 active_units=active.groupby(TARGET).ngroups,
                 active_by_region=active.groupby("region").size().to_dict(),
                 excluded_visits=excluded.groupby("AttractionId").size().to_dict())
    return visits, active, audit


def pairs(train, test):
    catalog = build_case_base(train)
    groups = pd.DataFrame([
        {"AttractionId": p["id"], "mode": mode, "n": group["count"], "mean": group["mean"]}
        for p in catalog for mode, group in p["groups"].items()
    ])
    prior = pd.Series({p["id"]: p["historical_mean"] for p in catalog})
    data = test.groupby(TARGET, as_index=False).Rating.mean()
    data["prior"] = data.AttractionId.map(prior)
    return data.merge(groups, on=GROUP, how="left", validate="many_to_one")


def predictions(data, policy):
    minimum, weight = policy
    return ((data.n * data["mean"] + weight * data.prior) / (data.n + weight)).where(data.n.ge(minimum))


def accuracy(actual, predicted):
    error = predicted - actual
    return {"n": int(error.notna().sum()), "mae": float(error.abs().mean()) if error.notna().any() else None,
            "rmse": float(np.sqrt(error.pow(2).mean())) if error.notna().any() else None}


def paired_metrics(data, models):
    common = pd.DataFrame(models).notna().all(axis=1)
    return {region: {
        "held_out_cases": len(part),
        "common_cases": int(common.loc[part.index].sum()),
        "models": {name: {
            "prediction_coverage": float(pred.loc[part.index].notna().mean()),
            "own_support": accuracy(part.Rating, pred.loc[part.index]),
            "common_support": accuracy(part.Rating[common.loc[part.index]], pred.loc[part.index][common.loc[part.index]]),
        } for name, pred in models.items()},
    } for region, part in [("all", data), *data.groupby("region")]}


def matrix(recommender):
    report = []
    for region, mode, category in GRID:
        answers = dict(region=region, mode=mode, category=category)
        winner, trace = recommender(answers)
        report.append({"answers": answers, "winner": winner["id"] if winner else None, "trace": trace})
    return report


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def freeze(source, output):
    _, active, audit = load(source)
    artifact = Path(__file__).resolve().parents[1] / "artifacts/cbr.json"
    legacy = json.loads(artifact.read_text())
    assert audit["source_sha256"] == legacy["audit"]["source_sha256"]
    assert build_case_base(active) == legacy["places"]
    train, test = user_split(active, 42)
    data = pairs(train, test)
    report = {
        "policy_version": legacy["version"], "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "cleaning": {"duplicate_key": ["UserId", "AttractionId", "VisitYear", "VisitMonth", "VisitMode", "Rating"],
                     "conflicting_ratings": "remove all conflicting values for the same visit context",
                     "excluded_destinations": list(EXCLUDED)},
        "audit": audit, "split": {"seed": 42, "train_users": train.UserId.nunique(), "test_users": test.UserId.nunique()},
        "matrix": matrix(lambda answers: legacy_recommend(legacy["places"], answers)),
        "rating": paired_metrics(data, {"A": data.prior, "B": predictions(data, LEGACY)}),
    }
    write(output, report)


def individual_pairs(index, test):
    data = test.groupby(TARGET, as_index=False).Rating.mean()
    group = {}
    for place, mode in index.support:
        _, ratings = index.evidence(place, mode)
        group[(place, mode)] = (len(ratings), sum(ratings.values()) / len(ratings))
    values = pd.DataFrame(
        [group.get((place, mode), (0, np.nan)) for place, mode in zip(data.AttractionId, data["mode"])],
        columns=["n", "mean"],
    )
    data[["n", "mean"]] = values
    data["prior"] = data.AttractionId.map(index.priors)
    return data


def metrics_by_region(rows):
    report = {}
    for region in ("all", *REGIONS):
        scoped = [r for r in rows if r["answers"]["region"] == region]
        wins = pd.Series([r["winner"] for r in scoped], dtype="Int64").value_counts()
        report[region] = {
            "supported": int(wins.sum()), "without_result": len(scoped) - int(wins.sum()),
            "unique_winners": len(wins), "winner_counts": {int(k): int(v) for k, v in wins.items()},
            "single_candidate": sum(r["trace"]["eligible_places"] == 1 for r in scoped),
            "mean_eligible_candidates": float(np.mean([r["trace"]["eligible_places"] for r in scoped])),
        }
    return report


def preference_changes(rows):
    report = {}
    for region in ("all", *REGIONS, "overall"):
        for field in ("region", "mode", "category"):
            pairs = [(a["winner"], b["winner"]) for i, a in enumerate(rows) for b in rows[i + 1:]
                     if (region == "overall" or a["answers"]["region"] == region == b["answers"]["region"])
                     and [key for key in a["answers"] if a["answers"][key] != b["answers"][key]] == [field]]
            if not pairs:
                continue
            comparable = sum(a is not None and b is not None for a, b in pairs)
            swaps = sum(a is not None and b is not None and a != b for a, b in pairs)
            toggles = sum((a is None) != (b is None) for a, b in pairs)
            report.setdefault(region, {})[field] = {
                "pairs": len(pairs), "both_supported": comparable, "changed_place": swaps,
                "changed_support": toggles, "change_rate": (swaps + toggles) / len(pairs),
                "changed_place_rate_on_both_supported": swaps / comparable if comparable else None,
            }
    return report


def bootstrap_mae(delta, users):
    values = pd.DataFrame({"delta": delta, "user": users}).groupby("user").delta.agg(["sum", "size"])
    if values.empty:
        return None
    sums, counts = values["sum"].to_numpy(), values["size"].to_numpy()
    rng = np.random.default_rng(44)
    boot = []
    for _ in range(500):
        indices = rng.integers(0, len(values), len(values))
        boot.append(sums[indices].sum() / counts[indices].sum())
    return [float(v) for v in np.quantile(boot, [.025, .975])]


def choose_policy(train, validation):
    catalog = build_case_base(train)
    index = CaseIndex(visit_records(train), catalog, *LEGACY)
    data = individual_pairs(index, validation)
    baseline = predictions(data, LEGACY)
    reports = []
    for policy in product((3, 5, 10, 15), (0, 5, 10, 20)):
        index.minimum, index.prior_weight = policy
        current = predictions(data, policy)
        common = current.notna() & baseline.notna()
        delta = (current[common] - data.Rating[common]).abs() - (baseline[common] - data.Rating[common]).abs()
        interval = bootstrap_mae(delta, data.UserId[common])
        rows = matrix(lambda answers: index.recommend(answers, examples=False))
        reports.append({
            "minimum": policy[0], "prior_weight": policy[1],
            "rating": paired_metrics(data, {"B": baseline, "C": current}),
            "mae_delta_ci95": interval,
            "coverage": metrics_by_region(rows),
        })
        reports[-1]["winners"] = [r["winner"] for r in rows]

    base = next(row for row in reports if (row["minimum"], row["prior_weight"]) == LEGACY)
    accepted = []
    for row in reports:
        b, c = (row["rating"]["all"]["models"][name]["common_support"] for name in ("B", "C"))
        row["same_winner_as_10_10"] = sum(x == y for x, y in zip(row["winners"], base["winners"]))
        stable = all(row["coverage"][r]["supported"] >= base["coverage"][r]["supported"]
                     for r in ("all", *REGIONS))
        gain = (row["coverage"]["all"]["supported"] > base["coverage"]["all"]["supported"]
                or any(row["coverage"][r]["supported"] > base["coverage"][r]["supported"] for r in REGIONS)
                or c["mae"] < b["mae"])
        row["passes_gate"] = bool(stable and c["rmse"] <= b["rmse"] and row["mae_delta_ci95"][1] <= 0 and gain)
        if row["passes_gate"]:
            accepted.append(row)
    if not accepted:
        return LEGACY, reports
    best = min(accepted, key=lambda row: (
        -sum(item["supported"] for item in row["coverage"].values()),
        row["rating"]["all"]["models"]["C"]["common_support"]["mae"],
        abs(row["minimum"] - 10) + abs(row["prior_weight"] - 10),
        row["minimum"], row["prior_weight"],
    ))
    return (best["minimum"], best["prior_weight"]), reports


def stability(visits, rows, policy):
    # Resample users, keeping all their visits together. Multiplicity weights their means;
    # the support threshold still counts distinct sampled people.
    rng = np.random.default_rng(45)
    units = visits.groupby(["AttractionId", "mode", "UserId"], as_index=False).Rating.mean()
    priors = visits.groupby(["AttractionId", "UserId"], as_index=False).Rating.mean()
    users = pd.Index(sorted(visits.UserId.unique()))
    groups = {(int(place), mode): (users.get_indexer(part.UserId), part.Rating.to_numpy())
              for (place, mode), part in units.groupby(GROUP)}
    historical = {int(place): (users.get_indexer(part.UserId), part.Rating.to_numpy())
                  for place, part in priors.groupby("AttractionId")}
    wins = np.zeros(len(rows), dtype=int)
    minimum, k = policy
    for _ in range(100):
        weights = np.bincount(rng.integers(0, len(users), len(users)), minlength=len(users))
        prior = {place: float(np.average(ratings, weights=weights[idx]))
                 for place, (idx, ratings) in historical.items() if weights[idx].any()}
        scores = {}
        for key, (idx, ratings) in groups.items():
            w = weights[idx]
            n = int(np.count_nonzero(w))
            if n >= minimum:
                scores[key] = ((n * float(np.average(ratings, weights=w)) + k * prior[key[0]]) / (n + k), n, -key[0])
        for i, row in enumerate(rows):
            mode = row["answers"]["mode"]
            eligible = [scores[(candidate["id"], mode)] for candidate in row["trace"]["candidates"]
                        if (candidate["id"], mode) in scores]
            winner = -max(eligible)[2] if eligible else None
            wins[i] += winner == row["winner"]
    return [{"answers": row["answers"], "winner": row["winner"], "retention_rate": int(count) / 100}
            for row, count in zip(rows, wins)]


def api_evaluation(data, estimate, rating, index, dev_index, development, holdout, final_rows):
    def coverage(rows):
        return {region: {mode: {
            "supported": sum(row["winner"] is not None for row in rows
                             if row["answers"]["region"] == region and row["answers"]["mode"] == mode),
            "scenarios": len(CATEGORIES),
        } for mode in MODES} for region in REGIONS}

    def errors(part):
        observed = part.Rating
        cbr = estimate.loc[part.index]
        supported = cbr.notna() & part.prior.notna()
        return {"cases": int(supported.sum()), "cbr_mae": accuracy(observed[supported], cbr[supported])["mae"],
                "baseline_mae": accuracy(observed[supported], part.prior[supported])["mae"]}

    return {
        "seed": 42, "train_reviewers": development.UserId.nunique(), "test_reviewers": holdout.UserId.nunique(),
        "held_out_cases": len(data), "overall": errors(data),
        "by_region_mode": {region: {mode: errors(data[(data.region == region) & (data["mode"] == mode)])
                                   for mode in MODES} for region in REGIONS},
        "training_coverage": coverage(matrix(lambda answers: dev_index.recommend(answers, examples=False))),
        "serving_coverage": coverage(final_rows), "rating": rating,
        "policy": {"minimum": index.minimum, "prior_weight": index.prior_weight},
    }


def optimize(source, output, artifact_path):
    visits, active, audit = load(source)
    development, holdout = user_split(active, 42)
    train, validation = user_split(development, 43)
    assert not set(train.UserId) & set(validation.UserId)
    assert not set(development.UserId) & set(holdout.UserId)
    policy, sensitivity = choose_policy(train, validation)
    catalog = build_case_base(active)
    records = visit_records(visits)
    index = CaseIndex(records, catalog, *LEGACY)
    legacy = matrix(lambda answers: legacy_recommend(catalog, answers))
    parity = matrix(lambda answers: index.recommend(answers, examples=False))
    maximum = 0
    for before, after in zip(legacy, parity):
        assert before["winner"] == after["winner"]
        left, right = before["trace"], after["trace"]
        assert (left["matching_places"], left["eligible_places"]) == (right["matching_places"], right["eligible_places"])
        assert [(v["name"], v["count"]) for v in left.get("ranking", [])] == [
            (v["name"], v["count"]) for v in right["ranking"]]
        for x, y in zip(left.get("ranking", []), right["ranking"]):
            maximum = max(maximum, abs(x["score"] - y["score"]))
    assert maximum <= 1e-12
    dev_index = CaseIndex(visit_records(development), build_case_base(development), *policy)
    data = pairs(development, holdout)
    individual = individual_pairs(dev_index, holdout)
    assert data[TARGET].equals(individual[TARGET])
    legacy_pred = predictions(data, LEGACY)
    equivalent = predictions(individual, LEGACY)
    assert np.allclose(legacy_pred, equivalent, atol=1e-12, rtol=0, equal_nan=True)
    estimate = predictions(individual, policy)
    rating = paired_metrics(data, {"A": data.prior, "B": legacy_pred, "C": estimate})
    index.minimum, index.prior_weight = policy
    final_rows = matrix(index.recommend)
    stability_before = stability(active, parity, LEGACY)
    report = {
        "policy_version": CASE_VERSION, "selected": {"minimum": policy[0], "prior_weight": policy[1]},
        "audit": audit, "parity": {"scenarios": len(parity), "max_score_difference": maximum},
        "splits": {"outer_seed": 42, "inner_seed": 43, "train_users": train.UserId.nunique(),
                   "validation_users": validation.UserId.nunique(), "holdout_users": holdout.UserId.nunique()},
        "sensitivity": sensitivity, "rating": rating,
        "coverage_before": metrics_by_region(legacy), "coverage_after": metrics_by_region(final_rows),
        "changes_before": preference_changes(legacy), "changes_after": preference_changes(final_rows),
        "stability_before": stability_before,
        "stability_after": stability_before if policy == LEGACY else stability(active, final_rows, policy),
        "matrix": final_rows,
    }
    write(output, report)
    artifact = {
        "version": CASE_VERSION, "policy": report["selected"], "places": catalog, "audit": audit,
        "evaluation": api_evaluation(data, estimate, rating, index, dev_index, development, holdout, final_rows),
        "cases": records,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", dir=artifact_path.parent, prefix=".cbr-cases-v4.",
                                encoding="utf-8", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(artifact, handle, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        os.replace(temporary, artifact_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, help="If set, evaluate and build the individual-case artifact")
    args = parser.parse_args()
    if args.artifact:
        optimize(args.source, args.output, args.artifact)
    else:
        freeze(args.source, args.output)
