"""Audit persisted artifacts against CSV using an independent reconstruction.

Run python -m backend.audit --write-evaluation after changing scoring policy.
The tree is not retrained; its case base and leaf evidence are verified from raw.
"""
import argparse
import ast
import csv
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
import shutil
import joblib
import numpy as np
from scipy.sparse import csr_matrix
from threadpoolctl import threadpool_limits
from .domain import ROOT, QUESTIONS, FEATURES, FIELD_COLUMNS
from .engine import Recommender, infer, POLICY_VERSION
from .train import evaluate


def audit(write_evaluation=False):
    checks=[]
    def check(name, ok, detail):
        checks.append({'check':name,'passed':bool(ok),'detail':detail})
        if not ok:
            raise AssertionError(f'{name}: {detail}')
        print(f'PASS {name}: {detail}',flush=True)
    model_path=ROOT/'artifacts/model.joblib'
    b=joblib.load(model_path)
    old_audit=json.loads((ROOT/'data/processed/audit.json').read_text())
    split=json.loads((ROOT/'data/processed/split.json').read_text())
    raw_path=ROOT/'data/raw/Stravl_Travel_Preference_Data.csv'
    sha=hashlib.sha256(raw_path.read_bytes()).hexdigest()
    check('source_checksum',sha==old_audit['csv_sha256'],sha)
    names=(ROOT/'data/raw/destination_ids.txt').read_text().splitlines()
    check('destination_mapping',names==b['destinations'] and len(set(names))==len(names),f'{len(names)} destination names')
    @lru_cache(None)
    def profile_values(value):
        return tuple(sorted(set(ast.literal_eval(value)))) if value else ()
    by_id={};seen=set();raw_count=duplicates=repeats=conflicts=empty=0
    fingerprints=set();canonical_duplicates=0
    with raw_path.open(newline='') as f:
        for raw in csv.DictReader(f):
            raw_count+=1
            signature=tuple(v for k,v in raw.items() if k!='id')
            if signature in seen:
                duplicates+=1
                continue
            seen.add(signature)
            profile={field:list(profile_values(raw[field])) for field in QUESTIONS}
            lists=[ast.literal_eval(raw[c]) for c in ['yes_swipes','no_swipes','maybe_swipes']]
            sets=[set(v) for v in lists]
            repeats+=sum(len(v)-len(set(v)) for v in lists)
            bad=(sets[0]&sets[1])|(sets[0]&sets[2])|(sets[1]&sets[2])
            conflicts+=len(bad)
            labels=[sorted(v-bad) for v in sets]
            assert all(type(d) is int and 0<=d<len(names) for v in labels for d in v)
            if not any(labels):
                empty+=1
                continue
            fingerprint=(tuple(tuple(v) for v in profile.values()),tuple(tuple(v) for v in labels))
            canonical_duplicates+=fingerprint in fingerprints
            fingerprints.add(fingerprint)
            assert raw['id'] not in by_id
            by_id[raw['id']]={'id':raw['id'],'profile':profile,**dict(zip(['yes','no','maybe'],labels))}
    reconstructed={'raw_users':raw_count,'duplicate_records_removed':duplicates,'repeated_swipes_removed_after_record_dedup':repeats,'conflicting_pairs_removed_after_record_dedup':conflicts,'empty_records_excluded':empty,'usable_users':len(by_id)}
    check('raw_cleaning_counts',all(old_audit[k]==v for k,v in reconstructed.items()),reconstructed)
    check('canonical_case_duplicates',canonical_duplicates==0,canonical_duplicates)
    tr,te=split['train_ids'],split['test_ids']
    check('user_split',len(set(tr))==len(tr) and len(set(te))==len(te) and set(tr).isdisjoint(te) and set(tr)|set(te)==set(by_id) and tr==b['ids'],{'train':len(tr),'test':len(te)})
    train=[by_id[i] for i in tr];test=[by_id[i] for i in te]
    def reference_encode(profile):
        return [int(not profile[field]) if val=='__missing__' else int(val in profile[field]) for field,val in FEATURES]
    expected_x=np.array([reference_encode(r['profile']) for r in train],dtype=np.float32)
    check('feature_encoding',np.array_equal(expected_x,b['X']) and [r['profile'] for r in train]==b['profiles'],f'{len(train)} case profiles / {len(FEATURES)} features')
    for kind in ['yes','no','maybe']:
        rr=[];cc=[]
        for i,row in enumerate(train):
            rr.extend([i]*len(row[kind]));cc.extend(row[kind])
        matrix=csr_matrix((np.ones(len(rr)),(rr,cc)),shape=(len(train),len(names)))
        check(f'case_base_{kind}',(matrix!=b[kind]).nnz==0,f'{matrix.nnz} interactions match CSV')
    all_rows=train+test
    all_x=np.array([reference_encode(r['profile']) for r in all_rows],dtype=np.float32)
    tree_leaves=b['tree'].apply(all_x)
    inferred=np.array([infer(b['rules'],r['profile'])['leaf'] for r in all_rows])
    check('all_rules_equal_tree',np.array_equal(inferred,tree_leaves),f'{len(all_rows)} profiles; {len(set(tree_leaves))} leaves')
    leaves=sorted(set(tree_leaves));indices={leaf:i for i,leaf in enumerate(leaves)}
    votes=np.zeros((len(leaves),len(names)));support=np.zeros_like(votes,dtype=int);users=np.zeros(len(leaves),dtype=int)
    for row,leaf in zip(train,tree_leaves[:len(train)]):
        i=indices[leaf];users[i]+=1
        if row['yes']:
            votes[i,row['yes']]+=1/len(row['yes'])
            support[i,row['yes']]+=1
    votes/=np.maximum(votes.sum(axis=1,keepdims=True),1e-12)
    check('leaf_weighted_scores',all(np.allclose(votes[i],b['leaf_scores'][int(leaf)],rtol=1e-10,atol=1e-12) for leaf,i in indices.items()),'Independent per-user weights reproduce every leaf distribution')
    check('leaf_support_counts',all(np.array_equal(support[i],b['leaf_support'][int(leaf)]) and users[i]==b['leaf_users'][int(leaf)] for leaf,i in indices.items()),'All destination support counts and segment users match raw cases')
    rec=Recommender(b)
    representatives=[]
    for leaf in leaves:
        row=all_rows[int(np.flatnonzero(tree_leaves==leaf)[0])]
        st=infer(b['rules'],row['profile'])
        answers={f:row['profile'][f] for f in st['used_fields']}
        representatives.append((row,st,answers))
    sample_checks=[]
    for row,st,answers in representatives:
        fields=tuple(f for f in QUESTIONS if answers.get(f))
        cols=[i for f in fields for i in FIELD_COLUMNS[f]]
        q=np.array(reference_encode(row['profile']),dtype=np.float64)[cols]
        raw_x=expected_x[:,cols].astype(np.float64)
        counts=raw_x.sum(axis=1)*q.sum()
        similarity=np.divide(raw_x@q,np.sqrt(counts),out=np.zeros(len(train)),where=counts>0)
        order=sorted(range(len(train)),key=lambda i:(-float(similarity[i]),i))
        nn=[i for i in order[:20] if similarity[i]>1e-8]
        numerator=np.ones(len(names));denominator=np.full(len(names),2.)
        evidence={k:np.zeros(len(names),dtype=int) for k in ['yes','no','maybe']}
        for n in nn:
            for kind,value in [('yes',1.),('no',0.),('maybe',.5)]:
                ds=train[n][kind]
                numerator[ds]+=similarity[n]*value
                denominator[ds]+=similarity[n]
                evidence[kind][ds]+=1
        reference_score=numerator/denominator
        reference_score[evidence['yes']==0]=-1
        actual_score,_,actual_nn,actual_similarity=rec.cbr_scores(answers)
        assert np.array_equal(actual_nn,np.array(nn))
        assert np.allclose(actual_similarity,similarity,atol=1e-14,rtol=1e-14)
        assert np.allclose(actual_score,reference_score,atol=1e-14,rtol=1e-14)
        result=rec.results(answers,st)
        for method in ['rules','cbr']:
            ids=[d['destination_id'] for d in result[method]]
            assert len(ids)<=5 and len(set(ids))==len(ids)
            for d in result[method]:
                idx=d['destination_id'];assert d['name']==names[idx]
                if d['fallback']:
                    assert d['support']==sum(idx in r['yes'] for r in train)
                elif method=='rules':
                    assert d['support']==support[indices[st['leaf']],idx]
                else:
                    assert d['evidence']=={k:int(v[idx]) for k,v in evidence.items()}
                    assert d['evidence']['yes']>0
                if method=='cbr':
                    assert not (evidence['no'][idx]>0 and evidence['yes'][idx]==0)
        sample_checks.append({'leaf':int(st['leaf']),'answers':answers,'rule_destinations':[r['name'] for r in result['rules']],'cbr_destinations':[r['name'] for r in result['cbr']]})
    check('independent_cbr_and_outputs',True,f'{len(representatives)} leaf representatives: cosine, neighbors, weighted votes, names, and displayed evidence')
    # Same profiles, grouped by actual known fields, prove exact live/batch parity.
    groups={}
    for r in train[:150]:
        answers={f:r['profile'][f] for f in ['form_a','form_f','form_g']}
        key=tuple(f for f in answers if answers[f])
        groups.setdefault(key,[]).append(answers)
    comparisons=0
    for fields,queries in groups.items():
        encoded=np.array([reference_encode({f:p.get(f,[]) for f in QUESTIONS}) for p in queries],dtype=np.float32)
        batch=rec.cosine_batch(encoded,fields)
        for answers,sims in zip(queries,batch):
            assert np.array_equal(sims,rec.similarities(answers))
            assert np.array_equal(rec.cbr_scores(answers,sims)[2],rec.cbr_scores(answers)[2])
            comparisons+=1
    check('live_evaluation_parity',comparisons==150,f'{comparisons} of {comparisons} exact matches')
    unknown=infer(rec.rules,{f:[] for f in QUESTIONS})
    result=rec.results({f:[] for f in unknown['used_fields']},unknown)
    check('unknown_answers_fallback',not result['personalized'] and result['neighbor_count']==0 and all(d['fallback'] for method in ['rules','cbr'] for d in result[method]),'No inferred preference or similar-user claim from missing answers')
    evaluation_path=ROOT/'artifacts/evaluation.json'
    backup=ROOT/'artifacts/evaluation-before-audit.json'
    if write_evaluation:
        if not backup.exists():
            shutil.copyfile(evaluation_path,backup)
        evaluation=evaluate(b,test)
        evaluation_path.write_text(json.dumps(evaluation,ensure_ascii=False,indent=2))
    evaluation=json.loads(evaluation_path.read_text())
    check('evaluation_policy',evaluation.get('policy_version')==POLICY_VERSION,evaluation.get('policy_version'))
    eligible=sum(bool(r['yes']) and len(r['yes'])+len(r['no'])>=5 for r in test)
    check('evaluation_population',evaluation['evaluated_users']==eligible and evaluation['test_users']==len(test),f'{eligible} eligible held-out users')
    result={'status':'passed','checked_at':datetime.now(timezone.utc).isoformat(),'policy_version':POLICY_VERSION,'source_sha256':sha,'model_sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),'evaluation_sha256':hashlib.sha256(evaluation_path.read_bytes()).hexdigest(),'checks':checks,'representative_outputs':sample_checks,'evaluation':evaluation}
    (ROOT/'artifacts/process_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--write-evaluation',action='store_true')
    args=parser.parse_args()
    with threadpool_limits(limits=2):
        result=audit(args.write_evaluation)
    print(f"Audit complete: {len(result['checks'])} checks passed",flush=True)
