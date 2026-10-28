import json
import joblib
import numpy as np
import pytest
from scipy.sparse import csr_matrix
from fastapi.testclient import TestClient
from backend.domain import ROOT, QUESTIONS, encode
from backend.engine import Recommender, infer
from backend.app import app


@pytest.fixture(scope='module')
def rec():
    return Recommender(joblib.load(ROOT / 'artifacts/model.joblib'))


def test_online_and_batched_cosine_and_neighbors_are_identical(rec):
    fields = ('form_a', 'form_f', 'form_g')
    profiles = [{f: p[f] for f in fields} for p in rec.b['profiles'][:150]]
    groups = {}
    for p in profiles:
        key=tuple(f for f in fields if p.get(f))
        groups.setdefault(key,[]).append(p)
    for key, queries in groups.items():
        batch = rec.cosine_batch(np.stack([encode(p) for p in queries]), key)
        for p, reference in zip(queries, batch):
            live = rec.similarities(p)
            assert np.array_equal(live, reference)
            assert np.array_equal(rec.cbr_scores(p)[2], rec.cbr_scores(p, reference)[2])


def test_unknown_fields_never_create_similarity(rec):
    assert np.array_equal(rec.similarities({'form_a':['1']}), rec.similarities({'form_a':['1'],'form_f':[],'form_g':[]}))
    assert not np.any(rec.similarities({f:[] for f in QUESTIONS}))


def test_all_unknown_answers_are_explicit_popularity_fallbacks():
    with TestClient(app) as client:
        c = client.post('/api/consultations/start', json={}).json()
        answers = {}
        for _ in range(6):
            if c['complete']:
                break
            answers[c['question']['field']] = []
            c = client.post('/api/consultations/answer', json={'answers':answers}).json()
        assert c['complete']
        result = c['results']
        assert result['personalized'] is False
        assert result['neighbor_count'] == 0 and result['similar_cases'] == []
        assert result['notice']
        for method in ['rules','cbr']:
            assert len(result[method]) == 5
            assert all(d['fallback'] and d['evidence_scope']=='training_popularity' for d in result[method])
        assert all('belum diketahui' in t['condition'] for t in c['trace'][:-1])


def test_negative_only_destinations_are_blocked_even_from_fallback():
    profiles = [{'form_f':['2']}, {'form_f':['2']}, {'form_f':['7']}]
    bundle = {'X':np.stack([encode(p) for p in profiles]), 'rules':[], 'destinations':['A','B','C'],
        'yes':csr_matrix([[1.,0,0],[0,0,0],[0,1,1]]),
        'no':csr_matrix([[0.,1,0],[0,1,0],[0,0,0]]), 'maybe':csr_matrix((3,3))}
    r = Recommender(bundle)
    scores, _, neighbors, _ = r.cbr_scores({'form_f':['2']})
    assert neighbors.tolist()==[0,1]
    assert scores[0]>0 and scores[1]==-1
    counts = r.neighbor_evidence(neighbors)
    blocked = (counts['no']>0)&(counts['yes']==0)
    final, fallback = r.with_fallback(scores,blocked)
    assert r.rank(final)==[0,2]
    assert not np.isfinite(final[1]) and fallback[2]


def test_maybe_response_and_smoothing_have_independent_expected_score():
    profiles=[{'form_f':['2']},{'form_f':['2']}]
    bundle={'X':np.stack([encode(p) for p in profiles]),'rules':[],'destinations':['A','B'],
        'yes':csr_matrix([[1.,0],[0,0]]),'no':csr_matrix([[0.,1],[0,1]]),'maybe':csr_matrix([[0.,0],[1,0]])}
    r=Recommender(bundle)
    score,support,neighbors,_=r.cbr_scores({'form_f':['2']})
    assert score[0]==pytest.approx((1+1+.5)/(2+2))
    assert support.tolist()==[2,2] and score[1]==-1


def test_output_evidence_and_ranking_match_actual_cases(rec):
    leaves=rec.b['tree'].apply(rec.X)
    for leaf in np.unique(leaves):
        p=rec.b['profiles'][int(np.flatnonzero(leaves==leaf)[0])]
        state=infer(rec.rules,p)
        answers={f:p[f] for f in state['used_fields']}
        result=rec.results(answers,state)
        context=rec.cbr_scores(answers)
        counts=rec.neighbor_evidence(context[2])
        for method in ['rules','cbr']:
            rows=result[method]
            assert len(rows)==len({r['destination_id'] for r in rows})
            assert all(rows[i]['ranking_score']>=rows[i+1]['ranking_score'] for i in range(len(rows)-1))
            for row in rows:
                d=row['destination_id']
                assert row['name']==rec.names[d]
                if row['fallback']:
                    assert row['support']==rec.popularity[d]
                elif method=='rules':
                    assert row['support']==rec.b['leaf_support'][leaf][d]
                else:
                    assert row['evidence']=={k:int(v[d]) for k,v in counts.items()}
                    assert row['evidence']['yes']>=1
                    assert row['support']==sum(row['evidence'].values())


def test_runtime_and_evaluation_share_the_same_ranking(rec):
    for p in rec.b['profiles'][:40]:
        state=infer(rec.rules,p)
        answers={f:p[f] for f in state['used_fields']}
        scores,_,_,_=rec.recommendation_scores(answers,state)
        result=rec.results(answers,state)
        for method in ['rules','cbr']:
            assert rec.rank(scores[method])==[d['destination_id'] for d in result[method]]


def test_model_unavailable_has_explicit_status(monkeypatch):
    import importlib
    module=importlib.import_module('backend.app')
    with TestClient(app) as client:
        monkeypatch.setattr(module,'rec',None)
        assert client.get('/api/health').json()['status']=='model_missing'
        assert client.post('/api/consultations/start',json={}).status_code==503


def test_outdated_evaluation_is_not_displayed(tmp_path):
    from backend.app import current_evaluation
    from backend.engine import POLICY_VERSION
    p=tmp_path/'evaluation.json'
    p.write_text(json.dumps({'policy_version':'obsolete','metrics':{}}))
    assert current_evaluation(p) is None
    p.write_text(json.dumps({'policy_version':POLICY_VERSION,'metrics':{}}))
    assert current_evaluation(p)['policy_version']==POLICY_VERSION
