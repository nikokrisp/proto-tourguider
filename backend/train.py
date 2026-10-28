"""Rebuild the cleaned case base, decision tree, rules and reproducible evaluation."""
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from threadpoolctl import threadpool_limits
from .domain import ROOT, SEED, QUESTIONS, FEATURES, FIELD_COLUMNS, encode
from .engine import export_rules, infer, Recommender, POLICY_VERSION


def clean_row(row, destination_count):
    profile = {}
    for field, q in QUESTIONS.items():
        values = ast.literal_eval(row[field]) if row[field] else []
        valid = {v for v, _ in q["options"]}
        if not isinstance(values, list) or any(v not in valid for v in values):
            raise ValueError(f"Invalid {field} in {row['id']}")
        profile[field] = sorted(set(values))
    labels, duplicates = [], 0
    for col in ("yes_swipes", "no_swipes", "maybe_swipes"):
        values = ast.literal_eval(row[col])
        if any(type(v) is not int or not 0 <= v < destination_count for v in values):
            raise ValueError(f"Invalid destination ID in {row['id']}")
        duplicates += len(values) - len(set(values))
        labels.append(set(values))
    conflict = (labels[0] & labels[1]) | (labels[0] & labels[2]) | (labels[1] & labels[2])
    labels = [sorted(values - conflict) for values in labels]
    return {"id": row["id"], "profile": profile, "yes": labels[0], "no": labels[1], "maybe": labels[2]}, duplicates, len(conflict)


def make_matrix(rows, kind, n):
    rr, cc = [], []
    for i, row in enumerate(rows):
        rr.extend([i] * len(row[kind]))
        cc.extend(row[kind])
    return csr_matrix((np.ones(len(rr), dtype=np.float32), (rr, cc)), shape=(len(rows), n))


def metrics(ranking, positive):
    hits = [int(d in positive) for d in ranking]
    precision = sum(hits) / 5
    recall = sum(hits) / len(positive)
    dcg = sum(h / np.log2(i + 2) for i, h in enumerate(hits))
    ideal = sum(1 / np.log2(i + 2) for i in range(min(5, len(positive))))
    return np.array([precision, recall, dcg / ideal])


def evaluate(bundle, test_rows):
    rec = Recommender(bundle)
    sums = {name: np.zeros(3) for name in ["forward_chaining", "cbr", "popularity"]}
    eligible, excluded = [], {"no_positive": 0, "fewer_than_five_candidates": 0}
    route_groups = {}
    for row in test_rows:
        if not row["yes"]:
            excluded["no_positive"] += 1
            continue
        if len(row["yes"]) + len(row["no"]) < 5:
            excluded["fewer_than_five_candidates"] += 1
            continue
        state = infer(bundle["rules"], row["profile"])
        answers = {f: row["profile"][f] for f in state["used_fields"]}
        key = tuple(f for f in QUESTIONS if answers.get(f))
        route_groups.setdefault(key, []).append((row, state, answers))
        eligible.append(row)
    for fields, queries in route_groups.items():
        for start in range(0, len(queries), 64):
            batch = queries[start:start + 64]
            similarities = rec.cosine_batch(np.stack([encode(a) for _, _, a in batch]), fields)
            for (row, state, answers), sims in zip(batch, similarities):
                candidates = sorted(row["yes"] + row["no"])
                positive = set(row["yes"])
                context = rec.cbr_scores(answers, similarities=sims)
                ranked, _, _, _ = rec.recommendation_scores(answers, state, context)
                popularity = np.where(rec.popularity > 0, rec.popularity, -np.inf)
                for name, scores in [("forward_chaining", ranked["rules"]), ("cbr", ranked["cbr"]), ("popularity", popularity)]:
                    sums[name] += metrics(rec.rank(scores, candidates), positive)
        print(f"Evaluated route {fields}: {len(queries)} users", flush=True)
    n = len(eligible)
    return {"policy_version": POLICY_VERSION, "seed": SEED, "train_users": len(bundle["ids"]), "test_users": len(test_rows), "evaluated_users": n, "excluded": excluded, "candidate_policy": "Per pengguna uji: hanya destinasi dengan Yes/No, minimal 5 kandidat dan 1 Yes. Maybe dan destinasi tanpa penilaian tidak dianggap negatif. Kedua metode memakai kelompok pertanyaan pada jalur aturan yang sama. Jawaban belum tahu tidak menjadi dasar kemiripan CBR; destinasi yang hanya ditolak tetangga dikeluarkan dari rekomendasi CBR.", "limitation": "Evaluasi kandidat yang sudah dinilai, bukan pengukuran keberhasilan top-5 pada seluruh katalog atau kepuasan perjalanan nyata. Pemilihan kandidat dipengaruhi paparan pada situs asal.", "metrics": {name: dict(zip(["precision_at_5", "recall_at_5", "ndcg_at_5"], [round(float(v), 6) for v in values / max(1, n)])) for name, values in sums.items()}}


def main():
    raw_path = ROOT / "data/raw/Stravl_Travel_Preference_Data.csv"
    raw = raw_path.read_bytes()
    df = pd.read_csv(raw_path, keep_default_na=False)
    names = (ROOT / "data/raw/destination_ids.txt").read_text().splitlines()
    audit = {"source": "https://github.com/Stravl/Stravl-Data", "csv_sha256": hashlib.sha256(raw).hexdigest(), "generated_at": datetime.now(timezone.utc).isoformat(), "raw_users": len(df), "raw_columns": len(df.columns), "destinations": len(names), "raw_swipes": {kind: int(df[col].map(lambda x: len(ast.literal_eval(x))).sum()) for kind, col in [("yes", "yes_swipes"), ("no", "no_swipes"), ("maybe", "maybe_swipes")]}, "missing_fields": {f: int((df[f] == "").sum()) for f in QUESTIONS}}
    duplicate_mask = df.drop(columns="id").duplicated()
    audit["duplicate_records_removed"] = int(duplicate_mask.sum())
    kept = df.loc[~duplicate_mask]
    rows, repeated, conflicts, empty = [], 0, 0, 0
    for row in kept.to_dict("records"):
        cleaned, dup, conflict = clean_row(row, len(names))
        repeated += dup
        conflicts += conflict
        if cleaned["yes"] or cleaned["no"] or cleaned["maybe"]:
            rows.append(cleaned)
        else:
            empty += 1
    audit.update({"repeated_swipes_removed_after_record_dedup": repeated, "conflicting_pairs_removed_after_record_dedup": conflicts, "empty_records_excluded": empty, "usable_users": len(rows), "clean_interactions": {k: sum(len(r[k]) for r in rows) for k in ["yes", "no", "maybe"]}})
    train_rows, test_rows = train_test_split(rows, test_size=.2, random_state=SEED)
    assert not ({r["id"] for r in train_rows} & {r["id"] for r in test_rows})
    X = np.stack([encode(r["profile"]) for r in train_rows])
    ix, y, weights = [], [], []
    for i, row in enumerate(train_rows):
        for d in row["yes"]:
            ix.append(i)
            y.append(d)
            weights.append(1 / len(row["yes"]))
    tree = DecisionTreeClassifier(max_depth=5, min_samples_leaf=200, random_state=SEED)
    print(f"Training: {len(train_rows)} users, {len(y)} positive pairs, {len(FEATURES)} features", flush=True)
    tree.fit(X[ix], y, sample_weight=weights)
    rules = export_rules(tree)
    leaves = tree.apply(X)
    mats = {k: make_matrix(train_rows, k, len(names)) for k in ["yes", "no", "maybe"]}
    leaf_scores, leaf_support, leaf_users = {}, {}, {}
    for leaf in np.unique(leaves):
        leaf = int(leaf)
        dist = np.zeros(len(names), dtype=np.float64)
        dist[tree.classes_.astype(int)] = tree.tree_.value[leaf][0]
        leaf_scores[leaf] = dist
        mask = leaves == leaf
        leaf_support[leaf] = np.asarray(mats["yes"][mask].sum(axis=0)).ravel().astype(int)
        leaf_users[leaf] = int(mask.sum())
    bundle = {"tree": tree, "rules": rules, "X": X, "ids": [r["id"] for r in train_rows], "profiles": [r["profile"] for r in train_rows], "destinations": names, "leaf_scores": leaf_scores, "leaf_support": leaf_support, "leaf_users": leaf_users, **mats}
    # Verify the generated forward-chaining rule base against EVERY train/test record.
    for split in (train_rows, test_rows):
        expected = tree.apply(np.stack([encode(r["profile"]) for r in split]))
        actual = [infer(rules, r["profile"])["leaf"] for r in split]
        assert np.array_equal(expected, actual), "Exported rules differ from source tree"
    audit.update({"train_users": len(train_rows), "test_users": len(test_rows), "positive_training_pairs": len(y), "tree_depth": int(tree.get_depth()), "leaf_count": int(tree.get_n_leaves()), "rule_count": len(rules), "rule_equivalence_records": len(rows), "feature_count": len(FEATURES)})
    for folder in ["artifacts", "data/processed"]:
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, ROOT / "artifacts/model.joblib", compress=3)
    (ROOT / "artifacts/rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=2))
    (ROOT / "data/processed/audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2))
    (ROOT / "data/processed/split.json").write_text(json.dumps({"seed": SEED, "train_ids": bundle["ids"], "test_ids": [r["id"] for r in test_rows]}))
    print(json.dumps(audit, indent=2), flush=True)
    evaluation = evaluate(bundle, test_rows)
    (ROOT / "artifacts/evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2))
    print(json.dumps(evaluation, indent=2), flush=True)


if __name__ == "__main__":
    with threadpool_limits(limits=2):
        main()
