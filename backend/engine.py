"""Forward chaining executes exported rules, never the tree predictor."""
import numpy as np
from .domain import FEATURES, QUESTIONS, encode, feature_description

POLICY_VERSION = "tourguider-audit-2"


def export_rules(tree):
    rules = []
    t = tree.tree_
    for node in range(t.node_count):
        if t.children_left[node] == -1:
            rules.append({"id": f"R{len(rules)+1:03}", "requires": f"node:{node}", "concludes": f"leaf:{node}", "node": node, "kind": "terminal"})
        else:
            for branch, child in [("absent", t.children_left[node]), ("present", t.children_right[node])]:
                rules.append({"id": f"R{len(rules)+1:03}", "requires": f"node:{node}", "concludes": f"node:{int(child)}", "node": node, "kind": "branch", "feature": int(t.feature[node]), "threshold": float(t.threshold[node]), "branch": branch})
    return rules


def infer(rules, supplied_answers):
    """Monotonic working memory; each applicable rule fires once per run.

    The question scheduler asks only for a missing fact on an enabled branch.
    Facts from old, inactive paths never enter the effective answer set.
    """
    facts = {"node:0"}
    fired, trace, used = set(), [], []
    x = encode(supplied_answers)
    while True:
        progressed = False
        for r in rules:
            if r["id"] in fired or r["requires"] not in facts:
                continue
            if r["kind"] == "branch":
                field, _ = FEATURES[r["feature"]]
                if field not in used:
                    used.append(field)
                if field not in supplied_answers:
                    return {"leaf": None, "next_field": field, "trace": trace, "facts": sorted(facts), "used_fields": used}
                right = bool(x[r["feature"]] > r["threshold"])
                if right != (r["branch"] == "present"):
                    continue
                if supplied_answers[field]:
                    condition = feature_description(r["feature"]) + (" — terpenuhi" if right else " — tidak terpenuhi")
                else:
                    condition = f"{QUESTIONS[field]['label']} belum diketahui; penanda kosong dataset memberi indikator {float(x[r['feature']]):g} untuk {feature_description(r['feature'])}"
            else:
                condition = "Kelompok preferensi telah terbentuk"
            facts.add(r["concludes"])
            fired.add(r["id"])
            trace.append({"rule_id": r["id"], "premise": r["requires"], "condition": condition, "conclusion": r["concludes"]})
            progressed = True
            if r["kind"] == "terminal":
                return {"leaf": r["node"], "next_field": None, "trace": trace, "facts": sorted(facts), "used_fields": used}
        if not progressed:
            raise RuntimeError("Basis aturan tidak mencapai pertanyaan atau kesimpulan.")


class Recommender:
    def __init__(self, bundle):
        self.b = bundle
        self.X = bundle["X"]
        self.yes, self.no, self.maybe = (bundle[k] for k in ("yes", "no", "maybe"))
        self.rules = bundle["rules"]
        self.names = bundle["destinations"]
        self.popularity = np.asarray(self.yes.sum(axis=0)).ravel().astype(float)
        self._norm_cache = {}

    def similarities(self, answers):
        fields = tuple(f for f in QUESTIONS if answers.get(f))
        return self.cosine_batch(np.stack([encode(answers)]), fields)[0]

    def cosine_batch(self, encoded_queries, fields):
        """Binary overlap counts are exact; one formula serves live and evaluation.

        Dividing separately normalized float32 vectors used to break mathematical
        ties differently in matrix-vector and matrix-matrix multiplication.
        """
        from .domain import FIELD_COLUMNS
        fields = tuple(fields)
        if not fields:
            return np.zeros((len(encoded_queries), self.X.shape[0]), dtype=np.float64)
        if fields not in self._norm_cache:
            cols = [i for f in fields for i in FIELD_COLUMNS[f]]
            mat = np.ascontiguousarray(self.X[:, cols])
            self._norm_cache[fields] = (cols, mat, mat.sum(axis=1, dtype=np.float64))
        cols, mat, counts = self._norm_cache[fields]
        queries = np.asarray(encoded_queries, dtype=np.float32)[:, cols]
        overlap = queries @ mat.T
        denominator = np.sqrt(queries.sum(axis=1, dtype=np.float64)[:, None] * counts[None, :])
        return np.clip(np.divide(overlap, denominator, out=np.zeros(denominator.shape), where=denominator > 0), 0, 1)

    def neighbor_evidence(self, neighbors):
        return {name: np.asarray(matrix[neighbors].sum(axis=0)).ravel().astype(int) for name, matrix in [("yes", self.yes), ("no", self.no), ("maybe", self.maybe)]}

    def cbr_scores(self, answers, similarities=None):
        sims = self.similarities(answers) if similarities is None else np.asarray(similarities, dtype=np.float64)
        # Stable ties make the same input reproducible, including offline evaluation.
        neighbors = np.lexsort((np.arange(len(sims)), -sims))[:20]
        neighbors = neighbors[sims[neighbors] > 1e-8]
        if len(neighbors) == 0:
            return np.full(len(self.names), -1.), np.zeros(len(self.names)), neighbors, sims
        weights = sims[neighbors]
        yes, no, maybe = self.yes[neighbors], self.no[neighbors], self.maybe[neighbors]
        exposure = np.asarray((yes + no + maybe).T @ weights).ravel()
        positive = np.asarray((yes + maybe * .5).T @ weights).ravel()
        score = (1 + positive) / (2 + exposure)
        # A destination needs at least one explicit Yes to be a personalized CBR
        # recommendation; a pure rejection must never be presented as a match.
        has_yes = np.asarray(yes.sum(axis=0)).ravel() > 0
        score[~has_yes] = -1
        support = np.asarray((yes + no + maybe).sum(axis=0)).ravel()
        return score, support, neighbors, sims

    def rule_scores(self, leaf):
        return self.b["leaf_scores"][int(leaf)]

    def rank(self, scores, candidates=None, k=5):
        ids = np.arange(len(scores)) if candidates is None else np.asarray(candidates, dtype=int)
        ids = ids[np.isfinite(np.asarray(scores)[ids])]
        return ids[np.lexsort((ids, -np.asarray(scores)[ids]))][:k].tolist()

    def with_fallback(self, primary, blocked=None):
        scores = np.full(len(self.names), -np.inf)
        blocked = np.zeros(len(self.names), dtype=bool) if blocked is None else blocked
        fallback = (self.popularity > 0) & ~blocked
        scores[fallback] = -.5 + .49 * self.popularity[fallback] / max(1, self.popularity.max())
        supported = (np.asarray(primary) > 0) & ~blocked
        scores[supported] = np.asarray(primary)[supported]
        return scores, fallback & ~supported

    def recommendation_scores(self, answers, inference, cbr_context=None):
        context = self.cbr_scores(answers) if cbr_context is None else cbr_context
        cscores, _, neighbors, _ = context
        evidence = self.neighbor_evidence(neighbors)
        blocked = (evidence["no"] > 0) & (evidence["yes"] == 0)
        personalized = any(answers.values())
        rscores = self.rule_scores(inference["leaf"]) if personalized else np.zeros(len(self.names))
        rules, rfallback = self.with_fallback(rscores)
        cbr, cfallback = self.with_fallback(cscores, blocked)
        return {"rules": rules, "cbr": cbr}, {"rules": rfallback, "cbr": cfallback}, context, evidence

    def results(self, answers, inference):
        leaf = inference["leaf"]
        scores, fallback, context, evidence = self.recommendation_scores(answers, inference)
        _, csupport, neighbors, sims = context
        personalized = any(answers.values())
        outputs = {"rules": [], "cbr": []}
        for method in outputs:
            for d in self.rank(scores[method]):
                is_fallback = bool(fallback[method][d])
                detail = None
                if is_fallback:
                    support = int(self.popularity[d])
                    reason = f"Alternatif populer, disukai oleh {support} pengguna dalam data pelatihan."
                    scope = "training_popularity"
                elif method == "rules":
                    support = int(self.b["leaf_support"][leaf][d])
                    reason = f"Disukai oleh {support} pengguna pada kelompok preferensi ini."
                    scope = "segment"
                else:
                    detail = {name: int(values[d]) for name, values in evidence.items()}
                    support = int(csupport[d])
                    reason = f"Di antara {len(neighbors)} kasus serupa: {detail['yes']} Ya, {detail['maybe']} Mungkin, dan {detail['no']} Tidak untuk destinasi ini."
                    scope = "similar_cases"
                outputs[method].append({"destination_id": d, "name": self.names[d], "support": support, "reason": reason, "fallback": is_fallback, "evidence_scope": scope, "evidence": detail, "ranking_score": round(float(scores[method][d]), 9)})
        similar_cases = []
        for n in neighbors[:3]:
            idx = int(n)
            common = []
            for f, vals in answers.items():
                shared = set(vals) & set(self.b["profiles"][idx].get(f, []))
                if shared:
                    labels = dict(QUESTIONS[f]["options"])
                    common.extend(labels[v] for v in sorted(shared))
            similar_cases.append({"case_id": f"Kasus {idx+1:05}", "similarity": round(float(sims[idx]), 6), "shared_preferences": common})
        known_fields = sum(bool(v) for v in answers.values())
        notice = "Belum ada preferensi yang diisi. Daftar ini menggunakan popularitas data pelatihan." if not personalized else ("Beberapa preferensi belum ditentukan. Rekomendasi menggunakan jawaban yang tersedia." if known_fields < len(answers) else "")
        return {**outputs, "similar_cases": similar_cases, "neighbor_count": len(neighbors), "segment_users": int(self.b["leaf_users"][leaf]) if personalized else 0, "personalized": personalized, "known_fields_count": known_fields, "notice": notice, "policy_version": POLICY_VERSION}
