"""Independent JSON-only Prompt 8B metric and identity audit.
No project metric code, pickle deserialization or checkpoint loading.
"""
import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
BATCH = ROOT/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1'
OUT = Path(__file__).resolve().parent
FIELDS = ('n','positive','tn','fp','fn','tp','buggy_f1','macro_f1','precision','recall')
METRICS = ('buggy_f1','macro_f1','precision','recall')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def ref(obj):
    assert sha(obj['path']) == obj['sha256'], obj['path']
    return read(obj['path'])

def dump(path,obj):
    with Path(path).open('x') as stream:
        json.dump(obj,stream,indent=2,ensure_ascii=False)
        stream.write('\n')

def metric(rows,checkpoint):
    tn=fp=fn=tp=0
    for row in rows:
        truth,pred=row['target'],row[checkpoint]
        assert truth in (0,1) and pred in (0,1)
        if truth==0:
            if pred==0:tn+=1
            else:fp+=1
        else:
            if pred==0:fn+=1
            else:tp+=1
    ratio=lambda a,b: a/b if b else 0.0
    fpos=ratio(2*tp,2*tp+fp+fn)
    fneg=ratio(2*tn,2*tn+fp+fn)
    return dict(n=tn+fp+fn+tp,positive=tp+fn,tn=tn,fp=fp,fn=fn,tp=tp,
                buggy_f1=100*fpos,macro_f1=50*(fpos+fneg),
                precision=100*ratio(tp,tp+fp),recall=100*ratio(tp,tp+fn))

def canonical_identity(row,record):
    return (record['category'],row['file'],record['sources'][row['file']]['sha256'],
            row.get('original_graph_node_id'))

def compute():
    plan=read(BATCH/'plan.json')
    plan_sha=sha(BATCH/'plan.json')
    assert len(plan['jobs'])==150
    key=lambda j:(j['task_id'],j['fold'],j['seed'],j['profile'])
    expected={key(j) for j in plan['jobs']}
    assert len(expected)==150
    paths={}
    for rp in (BATCH/'runs').glob('**/receipt.json'):
        rec=read(rp)
        if rec.get('status')=='complete' and rec.get('plan_sha256')==plan_sha:
            k=key(rec['job'])
            assert k not in paths,('duplicate',k)
            paths[k]=(rp,rec)
    assert set(paths)==expected,('missing/extra',expected-set(paths),set(paths)-expected)
    spec=ref(read(BATCH/'reports/interim_A/report.json')['spec'])
    excluded={(x['category'],x['file'],x['source_sha256']) for x in spec['sensitivity']}
    sources=set(); label_refs={}; labels={}
    for task,info in plan['tasks'].items():
        record=info['record']
        raw=ref(record['labels'])
        labels[task]={x['contract_name']:x['targets'] for x in raw}
        assert len(labels[task])==len(raw)
        label_refs[task]=record['labels']
        for f,s in record['sources'].items():
            identity=(s['path'],s['sha256'])
            if identity not in sources:
                assert sha(s['path'])==s['sha256']
                sources.add(identity)
    canonical={}; canonical_fold={}; pooled=defaultdict(list)
    fold_rows=[]; file_rows=[]; audits=[]; per_profile_ids=defaultdict(set)
    # G0 first so node labels can be checked across profiles, independently of row order.
    order=sorted(expected,key=lambda x:(x[0],x[1],x[2],x[3]!='G0',x[3]))
    for task,fold,seed,profile in order:
        rp,rec=paths[(task,fold,seed,profile)]; directory=rp.parent
        record=plan['tasks'][task]['record']
        prepared=ref(plan['tasks'][task]['prepared'][str(fold)+'/'+str(seed)])
        for name in ('outer_test_predictions.json','outer_test_supervision.json','binding.json'):
            assert sha(directory/name)==rec['artifacts'][name],(str(directory),name)
        rows=read(directory/'outer_test_predictions.json')
        supervision=read(directory/'outer_test_supervision.json')
        binding=read(directory/'binding.json')
        assert binding['split']==prepared['split']
        assert binding['graph']==prepared['profiles'][profile]['graph']
        assert binding['labels']==record['labels']
        for k,v in (('task_id',task),('fold',fold),('seed',seed),('profile',profile)):
            assert binding[k]==v
        files=set(prepared['split']['outer_test_files'])
        assert set(supervision['files'])==files
        assert {x['file'] for x in rows}==files
        assert not (files & set(prepared['split']['inner_train_files']))
        assert not (files & set(prepared['split']['inner_val_files']))
        ids=[canonical_identity(x,record) for x in rows]
        assert len(set(ids))==len(ids),('duplicate rows',task,fold,profile)
        for row in rows:
            assert row['score_role']=='outer_test'
            assert row['target'] in (0,1)
            for checkpoint in ('best','last'):
                prob=row[checkpoint+'_positive_probability']
                assert math.isfinite(prob) and 0<=prob<=1
                assert row[checkpoint] in (0,1)
                # Argmax on two softmax scores; exact ties are allowed either only at .5.
                if prob!=0.5: assert row[checkpoint]==int(prob>0.5)
        if record['task']=='node':
            assert {x['model_node_id'] for x in rows}==set(supervision['model_node_ids'])
            assert all(x['node_type']!='env_source' for x in rows)
            fields=('target','node_type','graph_stored_source_lines','graph_label_anchor')
        else:
            assert all(x['target']==labels[task][x['file']] for x in rows)
            fields=('target',)
        identity_labels={i:tuple(json.dumps(x.get(k),sort_keys=True) for k in fields) for i,x in zip(ids,rows)}
        tf=(task,fold,seed)
        if profile=='G0':
            canonical_fold[tf]=identity_labels
        else:
            assert canonical_fold[tf]==identity_labels,('profile identity/label mismatch',task,fold,profile)
        pp=(task,seed,profile)
        assert not (set(ids)&per_profile_ids[pp]),('OOF duplicate',task,profile,fold)
        per_profile_ids[pp].update(ids)
        compact=[]
        for x,i in zip(rows,ids):
            compact.append(dict(file=x['file'],identity=i,target=x['target'],best=x['best'],last=x['last']))
        pooled[pp].extend(compact)
        for checkpoint in ('best','last'):
            for population in ('all','exclude_disputed'):
                selected=compact if population=='all' else [x for x in compact if tuple(x['identity'][:3]) not in excluded]
                common=dict(task_id=task,task_kind=record['task'],profile=profile,fold=fold,seed=seed,
                            checkpoint=checkpoint,population=population)
                fold_rows.append(dict(common,**metric(selected,checkpoint)))
            for file in sorted(files):
                selected=[x for x in compact if x['file']==file]
                common=dict(task_id=task,task_kind=record['task'],profile=profile,fold=fold,seed=seed,
                            checkpoint=checkpoint,file=file,source_sha256=record['sources'][file]['sha256'])
                file_rows.append(dict(common,**metric(selected,checkpoint)))
        audits.append(dict(task_id=task,fold=fold,seed=seed,profile=profile,n=len(rows),receipt=str(rp),
                           receipt_sha256=sha(rp),prediction_sha256=rec['artifacts']['outer_test_predictions.json'],
                           supervision_sha256=rec['artifacts']['outer_test_supervision.json']))
    pooled_rows=[]
    for (task,seed,profile),rows in sorted(pooled.items()):
        record=plan['tasks'][task]['record']
        assert {x['file'] for x in rows}==set(record['graph_files'])
        if record['task']=='node':assert len(rows)==record['original_graph']['nodes']
        else:assert len(rows)==len(record['graph_files'])
        for checkpoint in ('best','last'):
            for population in ('all','exclude_disputed'):
                selected=rows if population=='all' else [x for x in rows if tuple(x['identity'][:3]) not in excluded]
                pooled_rows.append(dict(task_id=task,task_kind=record['task'],profile=profile,seed=seed,
                                        checkpoint=checkpoint,population=population,**metric(selected,checkpoint)))
    means=[]
    for task,seed,profile in sorted(pooled):
        for checkpoint in ('best','last'):
            for population in ('all','exclude_disputed'):
                selected=[x for x in fold_rows if (x['task_id'],x['seed'],x['profile'],x['checkpoint'],x['population'])==
                          (task,seed,profile,checkpoint,population)]
                assert len(selected)==len(plan['tasks'][task]['folds'])
                for name in METRICS:
                    values=[x[name] for x in selected]
                    means.append(dict(task_id=task,profile=profile,seed=seed,checkpoint=checkpoint,
                                      population=population,metric=name,mean=statistics.mean(values),
                                      sample_sd=statistics.stdev(values),n_pairs=len(values)))
    out=dict(version='independent-json-metrics-v1',status='passed',plan_sha256=plan_sha,
             script_sha256=sha(__file__),fit_count=len(audits),source_files_hashed=len(sources),
             label_scope={'contract':'Direct SHA-verified frozen graph_labels.json comparison',
                          'node':'Cross-profile identity and target equality to frozen G0 prediction targets; JSON masks checked.',
                          'limitation':'No direct node-label-to-pickle comparison in this independent audit. Auto-review rejected pickle.load as unsafe deserialization. No workaround was attempted. Official full verification supplies graph/label binding evidence separately.'},
             metric_formula='Direct binary confusion counts; BF1=2TP/(2TP+FP+FN); MF1=(F1_positive+F1_negative)/2; zero denominator -> 0; percent',
             source_identity='task/category/file/source SHA/original_graph_node_id; never CSV row position',
             fits=audits,tables={'fold_metrics':fold_rows,'file_metrics':file_rows,'pooled_oof':pooled_rows,'fold_means':means})
    dump(OUT/'computed.json',out)
    print(json.dumps({k:v for k,v in out.items() if k not in ('fits','tables')},ensure_ascii=False))
    for x in means:
        if x['checkpoint']=='best' and x['population']=='all' and x['metric']=='buggy_f1':
            print(x['task_id'],x['profile'],x['mean'],x['sample_sd'])

def compare():
    calc=read(OUT/'computed.json'); report=read(BATCH/'reports/final/report.json')
    assert report['completed_jobs']==150
    checks={}; maxdiff=0.0
    def table(name,keys,fields,filterer=lambda x:True):
        nonlocal maxdiff
        actual={tuple(x[k] for k in keys):x for x in report['tables'][name] if filterer(x)}
        expected={tuple(x[k] for k in keys):x for x in calc['tables'][name]}
        assert len(actual)==sum(1 for x in report['tables'][name] if filterer(x))
        assert set(actual)==set(expected),(name,'keys',len(actual),len(expected))
        for key,row in expected.items():
            for f in fields:
                delta=abs(row[f]-actual[key][f])
                maxdiff=max(maxdiff,delta)
                assert delta<=1e-10,(name,key,f,row[f],actual[key][f])
        checks[name]=len(actual)
    table('fold_metrics',('task_id','profile','fold','seed','checkpoint','population'),FIELDS)
    table('file_metrics',('task_id','profile','fold','seed','checkpoint','file','source_sha256'),FIELDS)
    table('pooled_oof',('task_id','profile','seed','checkpoint','population'),FIELDS)
    for checkpoint in ('best','last'):
        name=checkpoint+'_fold_means'
        actual={(x['task_id'],x['profile'],x['metric']):x for x in report['tables'][name]}
        exp={(x['task_id'],x['profile'],x['metric']):x for x in calc['tables']['fold_means'] if x['checkpoint']==checkpoint and x['population']=='all'}
        assert set(actual)==set(exp)
        for k,row in exp.items():
            for f in ('mean','sample_sd','n_pairs'):
                delta=abs(row[f]-actual[k][f]);maxdiff=max(maxdiff,delta)
                assert delta<=1e-10,(name,k,f,row[f],actual[k][f])
        checks[name]=len(actual)
    out=dict(status='passed',report_path=str(BATCH/'reports/final/report.json'),
             report_sha256=sha(BATCH/'reports/final/report.json'),computed_sha256=sha(OUT/'computed.json'),
             comparisons=checks,max_absolute_metric_difference=maxdiff,script_sha256=sha(__file__),
             limitation=calc['label_scope']['limitation'])
    dump(OUT/'comparison.json',out); print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('compute','compare'))
    args=parser.parse_args()
    if args.action=='compute':compute()
    else:compare()
