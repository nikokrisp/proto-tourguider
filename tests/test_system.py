import json
from pathlib import Path

from backend.engine import recommend

case_base = json.loads((Path(__file__).resolve().parents[1] / "artifacts/cbr.json").read_text())
def test_tie_break_and_threshold():
    def place(place_id, count):
        return {
            "id": place_id, "name": str(place_id), "region": "bali", "category": "nature",
            "historical_mean": 4, "groups": {"family": {"count": count, "mean": 4, "examples": []}},
        }
    answer = {"region": "bali", "mode": "family", "category": "nature"}
    result, trace = recommend([place(1, 9), place(4, 10), place(3, 11), place(2, 11)], answer)
    assert result["id"] == 2
    assert trace["eligible_places"] == 3


def test_audit_and_active_catalog():
    audit = case_base["audit"]
    assert audit["raw_visits"] == 52930
    assert audit["duplicates_removed"] == 3722
    assert audit["conflicting_rows_removed"] == 2052
    assert audit["clean_visits"] == 47156
    assert audit["visits_by_region"] == {"bali": 43014, "malang": 827, "yogyakarta": 3315}
    assert len(case_base["places"]) == 27
    assert sum(place["category"] == "volcano" for place in case_base["places"]) == 1


def test_case_aggregation_counts_a_reviewer_once():
    import pandas as pd
    from backend.train import build_case_base

    records = pd.DataFrame({
        "AttractionId": [1, 1, 1, 1],
        "UserId": [2, 2, 2, 3],
        "Rating": [3, 5, 4, 2],
        "mode": ["family", "family", "solo", "family"],
        "name": ["Contoh"] * 4,
        "region": ["bali"] * 4,
        "category": ["nature"] * 4,
    })
    place = build_case_base(records)[0]
    assert place["groups"]["family"]["count"] == 2
    assert place["groups"]["family"]["mean"] == 3
    assert place["historical_mean"] == 3
