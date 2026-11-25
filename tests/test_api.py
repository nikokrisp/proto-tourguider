"""Integration tests for the active Tourguider FastAPI endpoints."""
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.engine import score

client = TestClient(app)


def test_history_api_recommends_real_cases():
    partial = {"region": ["yogyakarta"], "mode": ["family"]}
    next_question = client.post("/api/consultations/answer", json={"answers": partial}).json()
    assert next_question["question"]["id"] == "category"
    result = client.post("/api/consultations/answer", json={"answers": {**partial, "category": ["volcano"]}}).json()
    item, trace = result["recommendation"], result["trace"]
    assert item["name"] == "Gunung Merapi"
    assert "Gunung Merapi" in parse_qs(urlparse(item["map_url"]).query)["query"][0]
    assert item["access"]
    assert trace["reviewer_count"] == 189 and len(trace["examples"]) == 3
    assert all(x["mode"] == "Keluarga" and 1 <= x["rating"] <= 5 and 1 <= x["month"] <= 12 for x in trace["examples"])
    assert trace["score"] == pytest.approx(score(trace["reviewer_count"], trace["similar_mean"], trace["historical_mean"]))
    assert trace["ranking"][0]["name"] == item["name"]
    assert client.get("/alur-cbr").status_code == 200


def test_bali_volcano_is_disabled():
    result = client.post("/api/consultations/answer", json={"answers": {
        "region": ["bali"], "mode": ["family"],
    }}).json()
    assert "volcano" in result["question"]["unavailable"]


def test_html_is_revalidated_and_uses_versioned_script():
    response = client.get("/")
    assert response.headers["cache-control"] == "no-store"
    assert "/assets/app.js?v=cbr-kasus-4" in response.text


def test_malang_waterfall_trace_and_support():
    answers = {"region": ["malang"], "mode": ["friends"], "category": ["waterfall"]}
    data = client.post("/api/consultations/answer", json={"answers": answers}).json()
    assert data["recommendation"]["name"] == "Air Terjun Coban Rondo"
    assert "Pandesari" in data["recommendation"]["recorded_location"]
    trace = data["trace"]
    assert trace["reviewer_count"] == 21
    assert trace["score"] == pytest.approx(3.9295101553166067)
    assert [(x["mode"], x["rating"]) for x in trace["examples"]] == [
        ("Teman", 4), ("Teman", 3), ("Teman", 5),
    ]
    answers["mode"] = ["solo"]
    del answers["category"]
    question = client.post("/api/consultations/answer", json={"answers": answers}).json()["question"]
    # The selected v4 policy admits Coban Rondo for solo travel; v3 requires 10 reviewers.
    assert ("waterfall" in question["unavailable"]) == (trace["evidence_type"] == "legacy_summary")
    assert "volcano" in question["unavailable"]


def test_catalog_and_overview_endpoints():
    cat = client.get("/api/catalog")
    assert cat.status_code == 200
    payload = cat.json()
    assert len(payload["places"]) == 27
    assert set(payload["regions"]) == {"bali", "yogyakarta", "malang"}

    ov = client.get("/api/overview")
    assert ov.status_code == 200
    overview = ov.json()
    assert overview["counts"]["active_places"] == 27
    assert overview["counts"]["active_visits"] == 46989
    assert len(overview["regions"]) == 3
    assert client.get("/basis-kasus").status_code == 200
    assert client.get("/evaluasi").status_code == 200


def test_consultation_only_allows_three_regions():
    start = client.post("/api/consultations/start").json()
    assert set(start["question"]["options"]) == {"bali", "yogyakarta", "malang"}
    invalid = client.post("/api/consultations/answer", json={"answers": {"region": ["all"]}})
    assert invalid.status_code == 422
