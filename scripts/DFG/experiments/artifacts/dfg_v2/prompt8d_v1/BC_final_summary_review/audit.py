"""Independent final Prompt8D summary acceptance; stdlib only, no model imports."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, hashlib, json, math, statistics, struct, time

ROOT=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
ART=ROOT/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1'
OUT=ART/'BC_final_summary_review'
MODES=('B_full','B_matched','C_matched')
VIEWS=('orig','C1')
COHORTS=('all','SolidiFI','nonSolidiFI')
SCORES=('buggy_f1','macro_f1','precision','recall')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def checked(r):
    if sha(r['path'])!=r['sha256']:raise AssertionError('SHA mismatch: '+r['path'])
    return Path(r['path'])
def jid(j):return (j['task_id'],j['fold'],j['seed'],j['profile'])
def nid(r):return (r['file'],r['original_graph_node_id'])
def unique(rows,key):
    result={}
    for r in rows:
        k=key(r)
        if k in result:raise AssertionError('duplicate key: '+repr(k))
        result[k]=r
    return result
def equal(a,b):
    if isinstance(b,dict):
        assert isinstance(a,dict)
        for k,v in b.items():assert k in a;equal(a[k],v)
    elif isinstance(b,list):
        assert isinstance(a,list) and len(a)==len(b)
        for x,y in zip(a,b):equal(x,y)
    elif isinstance(b,float):
        assert isinstance(a,(float,int)) and math.isfinite(a) and abs(a-b)<=1e-10,(a,b)
    else:assert a==b,(a,b)
def mean_sd(xs):
    xs=list(xs)
    return dict(mean=statistics.mean(xs) if xs else None,
                sample_sd=statistics.stdev(xs) if len(xs)>1 else None,n_folds=len(xs))
def metric(rows,views,label,state):
    c=[0,0,0,0]
    for r in rows:
        y=views[nid(r)][label];p=r[state+'_best']
        assert y in (0,1) and p in (0,1)
        c[2*y+p]+=1
    tn,fp,fn,tp=c;n=sum(c)
    result=dict(tn=tn,fp=fp,fn=fn,tp=tp,n=n,positive=tp+fn,tn_fp_fn_tp=c)
    if not n:result.update(dict.fromkeys(SCORES,None));return result
    pf=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.
    nf=2*tn/(2*tn+fp+fn) if 2*tn+fp+fn else 0.
    result.update(buggy_f1=100*pf,macro_f1=50*(pf+nf),
                  precision=100*tp/(tp+fp) if tp+fp else 0.,
                  recall=100*tp/(tp+fn) if tp+fn else 0.)
    return result
def choose(rows,views,cohort):
    assert cohort in COHORTS
    return [r for r in rows if cohort=='all' or views[nid(r)]['solidifi']==(cohort=='SolidiFI')]
def changes(rows,views,label):
    flips=0;prob=0;fixed=0;broken=0;absolute=[];counts={0:[0,0],1:[0,0]}
    for r in rows:
        y=views[nid(r)][label];old=r['original_best'];new=r['renamed_best']
        flip=old!=new;flips+=flip;prob+=r['original_probability']!=r['renamed_probability']
        fixed+=(old!=y and new==y);broken+=(old==y and new!=y)
        absolute.append(abs(r['renamed_probability']-r['original_probability']))
        counts[y][0]+=1;counts[y][1]+=flip
    out=dict(n=len(rows),changed_predictions=flips,changed_probabilities=prob,
             corrected_errors=fixed,introduced_errors=broken,net_errors_removed=fixed-broken,
             mean_absolute_probability_change=statistics.mean(absolute) if absolute else None,
             maximum_absolute_probability_change=max(absolute) if absolute else None)
    for y,name in ((0,'negative'),(1,'positive')):
        n,k=counts[y];out[name+'_n']=n;out[name+'_flips']=k
        out[name+'_flip_rate_percent']=100*k/n if n else None
    return out
def paired(left,right,views,label):
    ls=unique(left,nid);rs=unique(right,nid);assert set(ls)==set(rs)
    trans=[]
    for key,l in ls.items():
        r=rs[key]
        for field in ('source_sha256','target','original_best','original_probability'):
            assert l[field]==r[field]
        trans.append(dict(l,original_best=l['renamed_best'],original_probability=l['renamed_probability'],
                          renamed_best=r['renamed_best'],renamed_probability=r['renamed_probability']))
    lm=metric(left,views,label,'renamed');rm=metric(right,views,label,'renamed')
    return dict(left_metrics=lm,right_metrics=rm,
                metric_delta_pp={k:rm[k]-lm[k] if lm[k] is not None else None for k in SCORES},
                **changes(trans,views,label))
def selftest():
    v={('f',1):dict(orig=1,C1=0,solidifi=True)}
    left=[dict(file='f',original_graph_node_id=1,source_sha256='s',target=1,
               original_best=1,original_probability=.9,renamed_best=0,renamed_probability=.2)]
    right=[dict(left[0],renamed_best=1,renamed_probability=.8)]
    assert paired(left,right,v,'orig')['metric_delta_pp']['buggy_f1']==100
    assert paired(left,right,v,'C1')['introduced_errors']==1
    assert metric([],v,'orig','renamed')['buggy_f1'] is None
    assert mean_sd([1.,3.])['sample_sd']==math.sqrt(2)
    try:unique([left[0],left[0]],nid)
    except AssertionError:pass
    else:raise AssertionError('duplicate detector failed')
def main():
    started=time.time();selftest()
    if (OUT/'review.json').exists():raise FileExistsError('Review already exists')
    sp=ART/'BC_run/summary/summary.json';d=read(sp)
    assert d['status']=='complete' and d['inference_count']==300
    assert d['training_count']==d['optimizer_steps']==d['summary_forward_count']==0
    assert d['checkpoint']=='best' and set(d['views'])==set(VIEWS) and set(d['interventions'])==set(MODES)
    receipt=read(sp.with_name('receipt.json'));assert receipt['status']=='complete' and receipt['inferences']==300
    assert receipt['bindings']==d['bindings']
    for value in receipt['artifacts'].values():checked(value)
    for value in d['bindings'].values():checked(value)
    bp=checked(d['bindings']['execution_plan']);batch=read(bp)
    assert read(bp.with_name('execution_plan.seal.json'))['sha256']==sha(bp)
    plan=read(checked(batch['source_plan']))
    nodejobs={jid(j):j for j in plan['jobs'] if plan['tasks'][j['task_id']]['record']['task']=='node'}
    assert len(nodejobs)==100
    expected={(mode,)+key for mode in MODES for key in nodejobs}
    assert len(batch['jobs'])==300 and {(x['mode'],)+jid(x['job']) for x in batch['jobs']}==expected
    complete=read(checked(d['bindings']['completion']))
    assert complete['plan']==ref(bp) and complete['jobs']==300
    statuses=unique(complete['statuses'],lambda x:(x['mode'],)+jid(x['job']))
    assert set(statuses)==expected
    labelpath=checked(d['bindings']['label_views'])
    views={t:unique(rows,nid) for t,rows in read(labelpath).items()}
    grouped=defaultdict(dict);raw={};seen={};non_changes=defaultdict(lambda:[0,0,0]);resource=[]
    inputs=unique(d['inputs'],lambda x:(x['mode'],)+jid(x['job']))
    assert set(inputs)==expected
    for key,entry in sorted(inputs.items()):
        mode,task,fold,seed,profile=key;path=checked(entry['report']);r=read(path)
        status=read(checked(entry['status']))
        assert status==statuses[key] and status['returncode']==0 and status['result']==ref(path)
        checked(status['log']);checked(entry['prediction'])
        assert r['job']==nodejobs[key[1:]] and r['intervention']==mode
        assert r['optimizer_steps']==0 and r['weights_unchanged'] is True
        assert r['graph_edges_unchanged'] is True and r['unchanged_features_verified'] is True
        assert r['frozen_nx_attributes_untouched'] is True
        rows=r['predictions'];indexed=unique(rows,nid)
        group=(task,profile,mode);used=seen.setdefault(group,set())
        assert not (set(indexed)&used);used.update(indexed)
        for ni,row in indexed.items():
            v=views[task][ni]
            assert v['fold']==fold and row['source_sha256']==v['source_sha256'] and row['target']==v['orig']
            assert all(math.isfinite(row[k]) and 0.0<=row[k]<=1.0 for k in ('original_probability','renamed_probability'))
            if not v['solidifi']:
                counter=non_changes[(task,mode)];counter[0]+=1
                counter[1]+=row['original_best']!=row['renamed_best']
                counter[2]+=row['original_probability']!=row['renamed_probability']
                assert struct.pack('<f',row['original_probability'])==struct.pack('<f',row['renamed_probability'])
        grouped[group][fold]=rows;raw[(task,fold,seed,profile,mode)]=rows
        resource.append({k:r[k] for k in ('seconds','peak_allocated_bytes','peak_reserved_bytes')})
    for (task,profile,mode),actual in seen.items():assert actual==set(views[task])
    for value in non_changes.values():assert value[1:]==[0,0]
    for mode in MODES:
        for folder,suffix in (('jobs','.json'),('status','.json'),('logs','.log')):
            assert len(list((ART/'BC_run'/mode/folder).glob('*'+suffix)))==100
    tables=d['cohort_fold_metrics'];assert len(tables)==3600
    index=unique(tables,lambda x:tuple(x[k] for k in ('task','profile','intervention','fold','cohort','view','prediction_state')))
    for key,row in index.items():
        task,p,mode,fold,cohort,label,state=key
        assert label in VIEWS and state in ('original','renamed')
        subset=choose(grouped[(task,p,mode)][fold],views[task],cohort)
        equal(row,metric(subset,views[task],label,state))
    pooled=d['cohort_pooled_metrics'];assert len(pooled)==360
    unique(pooled,lambda x:tuple(x[k] for k in ('task','profile','intervention','cohort','view','prediction_state')))
    for row in pooled:
        task=row['task'];rows=sum([v for _,v in sorted(grouped[(task,row['profile'],row['intervention'])].items())],[])
        equal(row,metric(choose(rows,views[task],row['cohort']),views[task],row['view'],row['prediction_state']))
    means=d['cohort_fold_means'];assert len(means)==240
    unique(means,lambda x:tuple(x[k] for k in ('task','profile','intervention','cohort','view','prediction_state')))
    for row in means:
        assert row['cohort'] in ('all','SolidiFI')
        relevant=[x for x in tables if all(x[k]==row[k] for k in ('task','profile','intervention','cohort','view','prediction_state'))]
        assert row['empty_folds']==[x['fold'] for x in relevant if not x['n']]
        for score in SCORES:equal(row[score],mean_sd(x[score] for x in relevant if x['n']))
    assert len(d['cohort_changes'])==1980
    for row in d['cohort_changes']:
        task=row['task'];g=grouped[(task,row['profile'],row['intervention'])]
        rows=g[row['fold']] if row['fold'] is not None else sum(list(g.values()),[])
        equal(row,changes(choose(rows,views[task],row['cohort']),views[task],row['view']))
    old=read(checked(d['bindings']['old_idN_summary']));oldrows={}
    for entry in old['inputs']:
        report=read(checked(entry['intervention']))
        k=jid(report['job']);assert k not in oldrows;oldrows[k]=report['predictions']
    assert set(oldrows)==set(nodejobs)
    def lookup(task,profile,mode,fold):
        if mode=='8C_idN':return oldrows[(task,fold,1,profile)]
        return grouped[(task,profile,mode)][fold]
    allowed={('8C_idN','B_full'),('B_matched','C_matched')}
    for table,number in (('contrast_fold_metrics',1200),('contrast_pooled_metrics',120)):
        assert len(d[table])==number
        fields=('task','profile','left','right','cohort','view')+(('fold',) if table=='contrast_fold_metrics' else ())
        unique(d[table],lambda x:tuple(x[k] for k in fields))
        for row in d[table]:
            assert (row['left'],row['right']) in allowed and row['view'] in VIEWS
            task=row['task'];folds=[row['fold']] if 'fold' in row else plan['tasks'][task]['folds']
            left=sum([lookup(task,row['profile'],row['left'],f) for f in folds],[])
            right=sum([lookup(task,row['profile'],row['right'],f) for f in folds],[])
            equal(row,paired(choose(left,views[task],row['cohort']),choose(right,views[task],row['cohort']),views[task],row['view']))
    assert len(d['contrast_fold_means'])==80
    for row in d['contrast_fold_means']:
        assert row['cohort']!='nonSolidiFI'
        relevant=[x for x in d['contrast_fold_metrics'] if all(x[k]==row[k] for k in ('task','profile','left','right','cohort','view'))]
        for score in SCORES:equal(row['metric_delta_pp'][score],mean_sd(x['metric_delta_pp'][score] for x in relevant if x['n']))
    facts_path=ART/'report_facts.json';facts_status='not_yet_created'
    if facts_path.exists():
        facts=read(facts_path);assert facts['summary_sha256']==sha(sp)
        assert len(facts['main'])==10
        for row in facts['main']:
            for mode in MODES+('original',):
                for score in SCORES:
                    target=[x for x in means if x['task']==row['task'] and x['profile']==row['profile'] and
                            x['intervention']==('B_full' if mode=='original' else mode) and
                            x['cohort']=='all' and x['view']=='orig' and
                            x['prediction_state']==('original' if mode=='original' else 'renamed')]
                    assert len(target)==1;equal(row[mode][score],target[0][score])
        for (task,mode),c in non_changes.items():
            equal(facts['unchanged'][task+'/'+mode],dict(rows_across_five_profiles=c[0],class_changes=c[1],probability_changes=c[2]))
        equal(facts['resources'],dict(jobs=300,failures=0,retry_count=0,
            worker_internal_seconds_sum=sum(x['seconds'] for x in resource),
            subprocess_seconds_sum=sum(x['seconds'] for x in complete['statuses']),
            peak_allocated_bytes=max(x['peak_allocated_bytes'] for x in resource),
            peak_reserved_bytes=max(x['peak_reserved_bytes'] for x in resource)))
        facts_status='checked'
    result=dict(status='passed',model_forward_count=0,training_count=0,
        summary=ref(sp),execution_plan=ref(bp),labels=ref(labelpath),script=ref(Path(__file__)),
        report_facts=ref(facts_path) if facts_path.exists() else None,report_facts_status=facts_status,
        matrix=dict(total=300,per_mode=100,source_checkpoints=100,all_receipts_sha_verified=True,
                    successful_statuses=300,observed_extra_attempts=0),
        recalculated=dict(cohort_fold_metrics=3600,cohort_pooled_metrics=360,cohort_fold_means=240,
                          cohort_changes=1980,contrast_fold_metrics=1200,contrast_pooled_metrics=120,
                          contrast_fold_means=80),
        nonSolidiFI_unchanged={task+'/'+mode:dict(rows_across_profiles=c[0],class_changes=c[1],probability_changes=c[2])
                              for (task,mode),c in non_changes.items()},
        checks=['Original label/source/fold identities agree for every scored row.',
                'C1 separately re-scored against frozen node views; labels not edited.',
                'Per-fold and pooled scores independently recalculated from confusion counts.',
                'Equal-fold sample SD uses ddof1; no nonSolidiFI fold means.',
                'Contrasts are right-minus-left: B_full minus8C_idN; C_matched minusB_matched.',
                'Class-conditioned flips/errors/probability changes recalculated.',
                'NonSolidiFI argmax and float32 probabilities exactly unchanged.',
                'Exactly100 jobs/status/log files per mode; controller forbids implicit retry.'],
        elapsed_seconds=time.time()-started)
    with (OUT/'review.json').open('x') as f:json.dump(result,f,indent=2)
    text='# Prompt 8D 完整推理汇总独立验收\n\n状态：通过。验收无模型前向、无训练。\n\n'
    text+='300份结果/状态及SHA完整；orig/C1标签和source/fold身份一致。独立从预测重算3600逐折、360 pooled、240折均值、1980变化表、1200逐折配对、120 pooled配对和80配对均值。\n\n'
    text+='配对方向为B_full−8C_idN、C_matched−B_matched；两种标签/三种cohort不混用。非SolidiFI逐节点分类和float32概率完全不变；不输出非SolidiFI折均值。\n\n'
    text+='report_facts 状态：'+facts_status+'。详细SHA与逐项检查见review.json。该验收验证统计与身份，不证明诊断差异具有纯因果解释。\n'
    with (OUT/'REVIEW.md').open('x',encoding='utf8') as f:f.write(text)
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');args=p.parse_args()
    if args.self_test:selftest();print('Pure synthetic audit checks passed; final matrix not read.')
    else:main()
