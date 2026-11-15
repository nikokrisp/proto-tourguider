"""Acceptance matrix fixed from the sourced activities before running the ranker."""
from collections import Counter
from itertools import product
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

import json
from pathlib import Path

from backend.app import app
catalog = json.loads((Path(__file__).resolve().parents[1] / "data/curated.json").read_text())
from backend.curated import CATEGORIES, MINUTES, MODES, PROVINCES, recommend

client = TestClient(app)

SCENARIOS = [
    ("bali", "culture", "family", None, "any", True),
    ("bali", "nature", "solo", None, "any", True),
    ("bali", "recreation", "couples", None, "any", True),
    ("yogyakarta", "volcano", "family", "visit", "any", "gunung-api-purba"),
    ("yogyakarta", "culture", "friends", None, "any", True),
    ("yogyakarta", "nature", "couples", None, "any", True),
    ("jawa-barat", "volcano", "family", "visit", "any", "tangkuban-parahu"),
    ("jawa-barat", "culture", "family", None, "any", True),
    ("jawa-barat", "recreation", "friends", None, "any", True),
    ("jawa-tengah", "volcano", "couples", "visit", "any", "kawah-sikidang"),
    ("jawa-tengah", "culture", "solo", None, "any", True),
    ("jawa-tengah", "recreation", "family", None, "any", True),
    ("jawa-timur", "nature", "solo", None, "any", True),
    ("jawa-timur", "culture", "couples", None, "any", True),
    ("jawa-timur", "recreation", "family", None, "any", True),
    ("ntb", "volcano", "friends", "hike", "half-day", "bukit-pergasingan"),
    ("ntb", "volcano", "solo", "hike", "day", True),
    ("ntb", "culture", "family", None, "any", True),
    ("sumatera-barat", "nature", "friends", None, "any", True),
    ("sumatera-barat", "culture", "couples", None, "any", True),
    ("sumatera-barat", "recreation", "family", None, "any", True),
    ("sulawesi-selatan", "nature", "family", None, "any", "bissoloro_1"),
    ("sulawesi-selatan", "culture", "solo", None, "any", True),
    ("sulawesi-selatan", "recreation", "friends", None, "any", True),
    ("bali", "volcano", "family", "hike", "half-day", False),
    ("bali", "volcano", "family", "visit", "any", "museum-gunung-api-batur"),
    ("yogyakarta", "recreation", "solo", None, "half-day", "widosari"),
    ("yogyakarta", "culture", "family", None, "half-day", False),
]


@pytest.mark.parametrize("region,category,mode,activity,duration,expected", SCENARIOS)
def test_visit_scenarios(region, category, mode, activity, duration, expected):
    answer = {"region": region, "category": category, "mode": mode, "duration": duration}
    if activity:
        answer["activity"] = activity
    result, trace, alternatives = recommend(catalog, answer)
    if expected is False:
        assert result is None
        assert alternatives
        for option in alternatives:
            adjusted = {key: values[0] for key, values in option["answers"].items()}
            assert recommend(catalog, adjusted)[0]
        return
    assert result["region"] == PROVINCES[region]
    assert result["category"] == CATEGORIES[category]
    assert trace["case"]["source"].startswith("https://")
    if isinstance(expected, str):
        assert result["id"] == expected
    if duration in MINUTES:
        assert result["minutes"] <= MINUTES[duration]
    if activity == "hike":
        assert result["route"] and result["access"]


def test_catalog_coverage_and_integrity():
    counts = Counter(place["region"] for place in catalog)
    assert len(catalog) >= 60 and len(counts) >= 6
    assert min(counts.values()) >= 5
    assert len({place["id"] for place in catalog}) == len(catalog)
    assert len({(round(place["lat"], 5), round(place["lon"], 5)) for place in catalog}) == len(catalog)
    assert len({(place["region"], place["name"].casefold()) for place in catalog}) == len(catalog)
    for place in catalog:
        assert -11 <= place["lat"] <= 6 and 95 <= place["lon"] <= 141
        assert place["district"] and place["checked"]
        assert place["coordinate_source"].startswith("https://")
        for case in place["cases"]:
            assert case["category"] in CATEGORIES and case["source"].startswith("https://")
            assert case["evidence"]
            if case.get("activity") == "hike":
                assert case["route"] and case["access"]
    for region in counts:
        assert len({case["category"] for p in catalog if p["region"] == region for case in p["cases"]}) >= 2


def test_all_categories_do_not_opt_into_hiking():
    for region, mode in product(PROVINCES, MODES):
        result, _, _ = recommend(catalog, {"region": region, "mode": mode, "category": "all", "duration": "any"})
        assert result and result["route"] is None


def test_history_api_recommends_real_cases():
    from backend.engine import score

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
    assert '/assets/app.js?v=cbr-kasus-4' in response.text


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
