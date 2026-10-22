"""Read-only JSON/CSV audit; no graph/model deserialization or fitting."""
import csv,json,math,hashlib,statistics,subprocess,sys
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
ROOT=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
B=ROOT/'scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1'
OUT=Path(__file__).resolve().parent

def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()
def metrics(rs,ck):
    cm=[0,0,0,0]
    for r in rs:cm[2*int(r['target'])+int(r[ck])]+=1
    tn,fp,fn,tp=cm
    div=lambda a,b:a/b if b else 0.0
    pos=div(2*tp,2*tp+fp+fn);neg=div(2*tn,2*tn+fp+fn)
    return dict(n=len(rs),positive=tp+fn,buggy_f1=100*pos,macro_f1=50*(pos+neg),precision=100*div(tp,tp+fp),recall=100*div(tp,tp+fn),tn_fp_fn_tp=cm)
def identity(r):return (r['file'],str(r.get('original_graph_node_id','')))

print('Verifying immutable plan and all fit receipts...',flush=True)
proc=subprocess.run([sys.executable,'-B','-m','scripts.DFG.experiments.overall_cv.control','verify'],cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
(OUT/'verify.log').write_text(proc.stdout)
assert proc.returncode==0,proc.stdout
print(proc.stdout.strip(),flush=True)
plan=read(B/'plan.json');assert sha(B/'plan.json')==read(B/'plan.seal.json')['sha256']
raw=rows(B/'oof_predictions.csv');groups=defaultdict(list)
for x in raw:groups[(x['task_id'],int(x['fold']),x['variant'])].append(x)
fold_csv=rows(B/'fold_results.csv');published={(x['task_id'],int(x['fold']),x['variant'],x['checkpoint']):x for x in fold_csv}
assert len(fold_csv)==len(published)==120
counts=Counter();fold_results=[];recomputed={};val_files=defaultdict(Counter);task_population={};predictions_seen=defaultdict(set);errors=defaultdict(Counter)
for ref in plan['tasks']:
    m=read(ref['manifest']);task=m['task_id'];fold=m['fold'];spl=m['split'];tr=set(spl['train_files']);va=set(spl['val_files'])
    assert not tr&va and len(tr)==len(spl['train_files']) and len(va)==len(spl['val_files'])
    task_population.setdefault(task,tr|va);assert task_population[task]==tr|va
    val_files[task].update(va)
    pairing=read(m['initialization_audit_path']);assert pairing['semantic_equality']['exact'] and pairing['semantic_equality']['independent_storage']
    assert sha(m['initialization_audit_path'])==m['initialization_audit_sha256']
    assert m['graphs']['HCG']['node_attributes_sha256']==m['graphs']['HCG_DDG']['node_attributes_sha256']
    labels={x['contract_name']:x['targets'] for x in read(m['labels_path'])}
    assert (tr|va)<=set(labels)
    if m['task']=='node':assert all(labels[x]==1 for x in tr|va)
    before_after=[]
    for variant in ['HCG','HCG_DDG']:
        folder=B/'runs'/task/('fold_'+str(fold))/variant/'attempt_001'
        assert len([x for x in folder.parent.glob('attempt_*') if x.is_dir()])==1
        result=read(folder/'result.json');config=read(folder/'effective_config.json');binding=read(folder/'binding.json')
        assert all(config[k]==v for k,v in m['config'].items())
        assert binding['graph_sha256']==m['graphs'][variant]['sha256']
        assert binding['initial_weights_sha256']==m['initialization'][variant]['sha256']
        assert binding['initial_state_sha256']==m['initialization'][variant]['state_sha256']
        assert binding['split']==spl and config['score_role']=='cv_validation'
        audit=read(folder/'schema_support_audit.json');assert audit['no_samples_or_edges_removed']
        preds=read(folder/'cv_validation_predictions.json');indexed={identity(x):x for x in preds}
        assert len(indexed)==len(preds) and set(x['file'] for x in preds)==va
        assert all(x['score_role']=='cv_validation' for x in preds)
        for x in preds:
            assert x['target'] in [0,1]
            if m['task']=='contract':assert x['target']==labels[x['file']]
            for ck in ['best','last']:
                q=x[ck+'_positive_probability'];assert math.isfinite(q) and 0<=q<=1 and x[ck]==int(q>0.5)
        src={(x['file'],str(x.get('original_graph_node_id',''))):x for x in groups[(task,fold,variant)]}
        assert set(src)==set(indexed)
        for k,x in indexed.items():
            o=src[k];assert int(o['target'])==x['target']
            for ck in ['best','last']:
                assert int(o[ck])==x[ck] and float(o[ck+'_positive_probability'])==x[ck+'_positive_probability']
            unique=(x['file'],str(x.get('original_graph_node_id','')))
            assert unique not in predictions_seen[(task,variant)];predictions_seen[(task,variant)].add(unique)
        h=[json.loads(x) for x in (folder/'history.jsonl').read_text().splitlines()]
        assert len(h)==result['history_rows'] and all(math.isfinite(x[k]) for x in h for k in ['train_loss','cv_validation_loss'])
        minimum=min(h,key=lambda x:x['cv_validation_loss'])
        assert result['best_epoch']==minimum['epoch']==read(folder/'best.json')['epoch']
        assert result['last_epoch']==h[-1]['epoch']==read(folder/'last.json')['epoch']
        assert read(folder/'gradient_audit.json')['backbone_update_l1']>0
        for ck in ['best','last']:
            calc=metrics(preds,ck);pub=published[(task,fold,variant,ck)]
            assert calc['tn_fp_fn_tp']==json.loads(pub['tn_fp_fn_tp'])
            assert calc['n']==int(pub['n']) and calc['positive']==int(pub['positive'])
            for k in ['buggy_f1','macro_f1','precision','recall']:assert abs(calc[k]-float(pub[k]))<1e-9
            recomputed[(task,fold,variant,ck)]=calc;counts['metric_groups']+=1
        before_after.append(indexed);counts['fits']+=1
    a,b=before_after
    assert set(a)==set(b)
    for k in a:
        assert a[k]['target']==b[k]['target']
        for ck in ['best','last']:
            old=a[k][ck]!=a[k]['target'];new=b[k][ck]!=b[k]['target']
            errors[(task,ck)].update({'before_errors':int(old),'after_errors':int(new),'fixed':int(old and not new),'regressed':int(new and not old),'class_changed':int(a[k][ck]!=b[k][ck])})
    counts['paired_folds']+=1
for task,c in val_files.items():assert set(c)==task_population[task] and set(c.values())=={1}
for x in rows(B/'fold_statistics.csv'):
    values=[v for (t,f,var,ck),v in recomputed.items() if (t,var,ck)==(x['task_id'],x['variant'],x['checkpoint'])]
    for metric in ['buggy_f1','macro_f1','precision','recall']:
        vs=[v[metric] for v in values]
        assert abs(statistics.mean(vs)-float(x[metric+'_mean']))<1e-9
        assert abs(statistics.stdev(vs)-float(x[metric+'_sample_std']))<1e-9
    counts['aggregate_groups']+=1
for x in rows(B/'pooled_oof.csv'):
    rs=[r for (t,f,v),a in groups.items() if (t,v)==(x['task_id'],x['variant']) for r in a]
    calc=metrics(rs,x['checkpoint'])
    for k in ['buggy_f1','macro_f1','precision','recall']:assert abs(calc[k]-float(x[k]))<1e-9
    counts['pooled_groups']+=1
support=rows(B/'relation_support_gradients.csv');supported=[x for x in support if int(x['train_edges'])>0]
zero_grad=[x for x in supported if float(x['max_message_gradient_l1'])<=0]
assert not zero_grad
no_support=[x for x in support if int(x['train_edges'])==0]
overlap=defaultdict(Counter)
for x in rows(B/'code_overlap.csv'):
    for k in ['validation_nodes','validation_positive_nodes','exact_type_code_in_train','positive_exact_type_code_in_train']:overlap[x['task_id']][k]+=int(x[k])
for task,c in overlap.items():
    c['all_node_overlap_percent']=100*c['exact_type_code_in_train']/c['validation_nodes']
    c['positive_node_overlap_percent']=100*c['positive_exact_type_code_in_train']/c['validation_positive_nodes']
labelpath=Path('/home/zhao/SmartContract/ge-sc-llm/Test_code/label_pipeline/artifacts/public_endpoints_verified_v1/summary.json')
label_disagreements=[x for x in read(labelpath) if x['category'] in ['reentrancy','access_control']]
disputed=[]
label_root=labelpath.parent
for category in ['reentrancy','access_control']:
    task=category+'_author_node';base=label_root/category;ld=read(base/'label_differences.json');lm=read(base/'manifest.json')
    evidence={str(x['node_id']):x for x in (json.loads(line) for line in (base/'node_label_evidence.jsonl').read_text().splitlines())}
    graph=lm['graph_input'];assert sha(graph)==lm['input_sha256'][graph]
    lookup={(x['source_file'],str(x['author_node_id'])):x for x in ld};assert len(lookup)==len(ld)
    for variant in ['HCG','HCG_DDG']:
        rs=[x for (t,f,v),a in groups.items() if (t,v)==(task,variant) for x in a]
        hits={};file_counts=defaultdict(Counter);count=Counter()
        for x in rs:
            k=identity(x);bad=int(x['best'])!=int(x['target']);flag=k in lookup
            count['errors']+=bad;count['errors_on_disputed_nodes']+=bad and flag
            count['errors_on_agreed_nodes']+=bad and not flag
            if flag:
                d=lookup[k];e=evidence[str(d['node_id'])]
                assert int(x['target'])==d['author'] and e['label']==d['public']
                assert x['node_type']==d['node_type']==e['node_type']
                assert x['source_sha256']==lm['source_checks'][x['file']]['local_sha256']
                file_counts[x['file']]['disputed']+=1;file_counts[x['file']]['errors_on_disputed_nodes']+=bad
                hits[k]=x
        assert set(hits)==set(lookup)
        count['disputed_nodes']=len(hits)
        disputed.append(dict(task_id=task,variant=variant,counts=dict(count),by_file=dict(file_counts),label_audit_manifest_sha256=sha(base/'manifest.json'),label_differences_sha256=sha(base/'label_differences.json')))

report={'created_utc':datetime.now(timezone.utc).isoformat(),'reviewer':'Codex','status':'passed_with_known_scientific_limitations','plan_sha256':sha(B/'plan.json'),'head':plan['head'],'counts':dict(counts),'source_hashes':len(plan['runtime']),'frozen_asset_hashes':len(plan['frozen']),'exported_prediction_rows':len(raw),'task_file_populations':{k:len(v) for k,v in task_population.items()},'score_role':'cv_validation','independent_test':False,'errors':[dict(task_id=t,checkpoint=c,**dict(v)) for (t,c),v in errors.items()],'relations':{'canonical_fold_rows':len(support),'with_train_support':len(supported),'supported_with_zero_message_gradient':len(zero_grad),'without_train_support':len(no_support),'unseen_relation_rows_preserved':no_support},'overlap':dict(overlap),'known_label_disagreements':label_disagreements,'errors_vs_label_disagreements':disputed,'limits':['Hash/receipt identity does not prove semantic truth of author labels.','Node targets checked between frozen variants and exports; no new graph deserialization or model forward in this audit.','Exported metrics independently recomputed without project metric helper; graph/code overlap statistics inherited from hash-verified report.','Existing checkpoint replay evidence verified by receipts; not rerun on GPU.','Known public-vs-author label disagreements are not a new corrected ground truth.','No model or graph changes; no training.']}
(OUT/'audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':report['status'],'counts':report['counts'],'relations':{k:v for k,v in report['relations'].items() if k!='unseen_relation_rows_preserved'},'overlap':report['overlap'],'disputed_error_counts':[{k:v for k,v in x.items() if k in ['task_id','variant','counts']} for x in disputed],'errors_best':[x for x in report['errors'] if x['checkpoint']=='best']},indent=2),flush=True)
