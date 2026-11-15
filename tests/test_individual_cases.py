import json

import pytest
from fastapi.testclient import TestClient

from backend import app as api
from backend.cases import CaseIndex, CASE_VERSION, load_individual
from backend.domain import DATA_VERSION

ANSWERS = {"region": "malang", "category": "nature", "mode": "friends"}


def test_individual_reuse_uses_each_reviewer_once():
    places = [
        {"id": 1, "name": "Air terjun", "region": "malang", "category": "waterfall"},
        {"id": 2, "name": "Taman", "region": "malang", "category": "nature"},
        {"id": 3, "name": "Pantai", "region": "bali", "category": "nature"},
    ]
    records = [
        dict(case_id=f"private-{i}", transaction_id=i, reviewer=reviewer,
             destination_id=place, region=places[place - 1]["region"],
             category=places[place - 1]["category"], mode=mode, year=2018, month=i, rating=rating)
        for i, (place, reviewer, mode, rating) in enumerate([
            (1, 1, "friends", 3), (1, 1, "friends", 5), (1, 2, "friends", 2),
            (1, 1, "solo", 1), (2, 3, "friends", 5), (3, 4, "friends", 5),
        ], 1)
    ]
    index = CaseIndex(records, places, 2, 10)
    assert index.has_match(ANSWERS)
    result, trace = index.recommend(ANSWERS)
    assert result["id"] == 1
    assert trace["similarity"] == {"0": 1, "1": 4, "threshold": 1}
    assert trace["winner_visit_count"] == 3
    assert trace["matched_unique_reviewers"] == 3
    assert trace["reviewer_count"] == 2
    assert trace["similar_mean"] == 3
    assert trace["historical_mean"] == pytest.approx(2.5)
    assert trace["score"] == pytest.approx((2 * 3 + 10 * 2.5) / 12)
    assert trace["examples"][0]["reviewer_visit_count"] == 2
    assert trace["examples"][0]["reviewer_mean"] == 4
    assert trace["candidates"][1]["status"] == "below_support"
    assert "private-" not in json.dumps(trace)
    assert "transaction_id" not in json.dumps(trace)
    assert index.recommend({**ANSWERS, "mode": "solo"})[1]["reason"] == "below_support"
    assert index.recommend({**ANSWERS, "mode": "family"})[1]["reason"] == "no_matching_cases"
    assert index.recommend({**ANSWERS, "category": "volcano"})[1]["reason"] == "no_places"


def test_individual_ranking_uses_support_then_id():
    places = [dict(id=i, name=str(i), region="malang", category="waterfall") for i in (3, 2, 1)]
    records = [dict(case_id=str(i * 10 + j), transaction_id=i * 10 + j, reviewer=j,
                    destination_id=i, region="malang", category="waterfall",
                    mode="friends", year=2018, month=1, rating=4)
               for i in (3, 2, 1) for j in range(1, 4 if i != 1 else 3)]
    result, trace = CaseIndex(records, places, 2, 10).recommend(ANSWERS)
    assert result["id"] == 2
    assert [row["id"] for row in trace["ranking"]] == [2, 3, 1]


def test_legacy_fallback_is_identifiable(monkeypatch, tmp_path):
    broken = tmp_path / "bad.json"
    broken.write_text('{"version": "invalid"}')
    monkeypatch.setattr(api, "CASE_V4_PATH", broken)
    old, index = api.load_case_base()
    assert index is None and old["version"] == DATA_VERSION
    monkeypatch.setattr(api, "case_base", old)
    monkeypatch.setattr(api, "case_index", None)
    client = TestClient(api.app)
    assert client.get("/api/health").json()["evidence_type"] == "legacy_summary"
    result = client.post("/api/consultations/answer", json={"answers": {
        key: [value] for key, value in ANSWERS.items()
    }}).json()
    assert result["trace"]["evidence_type"] == "legacy_summary"


def test_local_artifact_and_public_trace():
    if not api.CASE_V4_PATH.exists():
        pytest.skip("Bangun artefak lokal v4 untuk pengujian snapshot.")
    artifact, index = load_individual(api.CASE_V4_PATH)
    assert len(artifact["cases"]) == 47156
    assert artifact["audit"]["active_visits"] == 46989
    assert len(index.places) == 27
    client = TestClient(api.app)
    assert client.get("/api/health").json()["version"] == CASE_VERSION
    result = client.post("/api/consultations/answer", json={"answers": {
        key: [value] for key, value in {**ANSWERS, "category": "waterfall"}.items()
    }}).json()
    trace = result["trace"]
    assert trace["score"] == pytest.approx(3.9295101553166067)
    assert trace["winner_visit_count"] == 21
    assert trace["matched_unique_reviewers"] == 21
    assert trace["examples"][0]["label"] == "Kasus 01"
    assert all(k not in json.dumps(result) for k in ('"case_id"', '"reviewer"', '"transaction_id"'))
    insufficient = client.post("/api/consultations/answer", json={"answers": {
        "region": ["bali"], "mode": ["family"], "category": ["volcano"],
    }}).json()
    assert insufficient["status"] == "insufficient_support"
    assert insufficient["trace"]["reason"] == "no_places"
    assert all(client.post("/api/consultations/answer", json={"answers": option["answers"]})
               .json()["status"] == "recommended" for option in insufficient["alternatives"])


def test_serving_matrix_and_evidence():
    if api.case_index is None:
        pytest.skip("Bangun artefak lokal v4 untuk menguji matriks aktif.")
    from pathlib import Path
    from statistics import mean

    report = json.loads((Path(__file__).resolve().parents[1] / "docs/cbr-evaluation.json").read_text())
    client = TestClient(api.app)
    assert len(report["matrix"]) == 120
    for row in report["matrix"]:
        answers = row["answers"]
        result = client.post("/api/consultations/answer", json={
            "answers": {key: [value] for key, value in answers.items()},
        }).json()
        winner = (result["recommendation"] or {}).get("id")
        trace = result["trace"]
        assert winner == row["winner"]
        assert trace == row["trace"]
        assert trace["visit_count"] == trace["similarity"]["0"] + trace["similarity"]["1"]
        if winner is None:
            assert trace["eligible_places"] == 0
            continue
        n, k = trace["reviewer_count"], trace["prior_weight"]
        assert trace["score"] == pytest.approx((n * trace["similar_mean"] + k * trace["historical_mean"]) / (n + k))
        reviewers = api.case_index.by_place[winner][answers["mode"]]
        for example in trace["examples"]:
            assert any(
                len(visits) == example["reviewer_visit_count"]
                and mean(visit.rating for visit in visits) == example["reviewer_mean"]
                and any((visit.year, visit.month, visit.rating) == (example["year"], example["month"], example["rating"])
                        for visit in visits)
                for visits in reviewers.values()
            )
