import json
import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy.sparse import csr_matrix
from backend.domain import ROOT, FEATURES, encode
from backend.engine import Recommender, infer
from backend.train import clean_row, metrics
from backend.app import app


@pytest.fixture(scope="module")
def bundle():
    return joblib.load(ROOT / "artifacts/model.joblib")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_missing_is_not_a_negative_answer():
    x = encode({"form_f": []})
    y = encode({"form_f": ["2"]})
    missing = FEATURES.index(("form_f", "__missing__"))
    assert x[missing] == 1 and y[missing] == 0
    assert y[FEATURES.index(("form_f", "2"))] == 1


def test_cleaning_deduplicates_and_removes_conflicting_labels():
    row = {"id": "test", **{f: "['1']" for f in ["form_a", "form_b", "form_c", "form_f", "form_g", "form_h", "form_i", "form_j"]}, "yes_swipes": "[0,0,1]", "no_swipes": "[1,2]", "maybe_swipes": "[2,3]"}
    clean, dup, conflicts = clean_row(row, 4)
    assert (clean["yes"], clean["no"], clean["maybe"]) == ([0], [], [3])
    assert dup == 1 and conflicts == 2
    row["yes_swipes"] = "[99]"
    with pytest.raises(ValueError):
        clean_row(row, 4)


def test_all_leaves_have_equivalent_chained_rules(bundle):
    tree = bundle["tree"]
    leaves = tree.apply(bundle["X"])
    for leaf in np.unique(leaves):
        i = int(np.flatnonzero(leaves == leaf)[0])
        state = infer(bundle["rules"], bundle["profiles"][i])
        assert state["leaf"] == leaf
        assert len(state["trace"]) >= 2
        assert len(state["used_fields"]) == len(set(state["used_fields"]))
        assert state["trace"][0]["premise"] == "node:0"
        for before, after in zip(state["trace"], state["trace"][1:]):
            assert before["conclusion"] == after["premise"]


def test_scheduler_only_asks_active_path_and_retracts_old_branch(bundle):
    # Walk every leaf's actual path one field at a time.
    leaves = bundle["tree"].apply(bundle["X"])
    root = infer(bundle["rules"], {})["next_field"]
    root_feature = FEATURES[bundle["rules"][0]["feature"]][1]
    routes = []
    for leaf in np.unique(leaves):
        profile = bundle["profiles"][int(np.flatnonzero(leaves == leaf)[0])]
        answers = {}
        asked = []
        while True:
            result = infer(bundle["rules"], answers)
            if result["leaf"] is not None:
                assert result["leaf"] == leaf
                break
            field = result["next_field"]
            assert field not in asked
            asked.append(field)
            answers[field] = profile[field]
        routes.append(asked)
    left = infer(bundle["rules"], {root: []})
    right = infer(bundle["rules"], {root: [root_feature]})
    assert left["trace"][0]["conclusion"] != right["trace"][0]["conclusion"]
    assert len({tuple(r) for r in routes}) > 1


def test_clean_case_base_and_user_split_are_disjoint(bundle):
    split = json.loads((ROOT / "data/processed/split.json").read_text())
    assert set(split["train_ids"]).isdisjoint(split["test_ids"])
    assert set(bundle["ids"]) == set(split["train_ids"])
    assert not bundle["yes"].multiply(bundle["no"]).nnz
    assert not bundle["yes"].multiply(bundle["maybe"]).nnz
    assert not bundle["no"].multiply(bundle["maybe"]).nnz


def test_cbr_weighted_vote_has_known_expected_value():
    profiles = [{"form_f": ["2"]}, {"form_f": ["2"]}]
    toy = {"X": np.stack([encode(p) for p in profiles]), "yes": csr_matrix([[1., 0., 0.], [0., 1., 0.]]), "no": csr_matrix([[0., 1., 0.], [1., 0., 0.]]), "maybe": csr_matrix((2, 3)), "rules": [], "destinations": ["A", "B", "C"]}
    rec = Recommender(toy)
    score, support, neighbors, _ = rec.cbr_scores({"form_f": ["2"]})
    assert np.allclose(score[:2], [.5, .5])
    assert score[2] == -1 and support[2] == 0
    assert len(neighbors) == 2
    toy["X"][1] = encode({"form_f": ["7"]})
    different = Recommender(toy)
    assert different.similarities({"form_f": ["2"]})[0] > different.similarities({"form_f": ["2"]})[1]


def test_ranking_metrics_against_hand_calculation():
    p, r, n = metrics([1, 2, 4, 6, 8], {1, 4, 9})
    assert p == .4 and r == 2 / 3
    expected = (1 + 1 / np.log2(4)) / (1 + 1 / np.log2(3) + 1 / np.log2(4))
    assert np.isclose(n, expected)


def test_api_end_to_end_and_effective_answers(client, bundle):
    response = client.post('/api/consultations/start', json={})
    assert response.status_code == 200
    data = response.json()
    answers = {}
    profile = bundle["profiles"][123]
    for _ in range(6):
        if data["complete"]:
            break
        field = data["question"]["field"]
        assert field not in answers
        answers[field] = profile[field]
        data = client.post('/api/consultations/answer', json={"answers": answers}).json()
    assert data["complete"]
    for method in ['rules', 'cbr']:
        dests = [d['destination_id'] for d in data['results'][method]]
        assert len(dests) == 5 and len(set(dests)) == 5
        assert all(0 <= d < len(bundle['destinations']) for d in dests)
    assert data['results']['neighbor_count'] <= 20
    assert len(data['answers']) == len(data['summary'])
    # Extra answers from an old path must not enter CBR or the displayed summary.
    all_answers = client.post('/api/consultations/answer', json={"answers": profile}).json()
    assert set(all_answers['answers']) == set(answers)
    reset = client.post('/api/consultations/answer', json={"answers": {}}).json()
    assert reset['answers'] == {} and reset['trace'] == [] and reset['results'] is None


@pytest.mark.parametrize('answers', [{"not_a_field": ["1"]}, {"form_h": ["0", "1"]}, {"form_f": ["9"]}, {"form_g": ["2", "2"]}])
def test_invalid_answers_rejected(client, answers):
    assert client.post('/api/consultations/answer', json={"answers": answers}).status_code == 422


def test_static_assets_and_project_report(client):
    assert client.get('/').status_code == 200
    assert client.get('/assets/style.css').status_code == 200
    assert client.get('/assets/inter-400.ttf').status_code == 200
    assert client.get('/api/health').json()['status'] == 'ready'
    report = client.get('/api/project').json()
    assert report['audit']['raw_users'] == 80301
    assert report['evaluation']['evaluated_users'] > 0
    for scores in report['evaluation']['metrics'].values():
        assert all(0 <= n <= 1 for n in scores.values())
