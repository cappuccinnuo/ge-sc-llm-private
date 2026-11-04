"""Summarize D1 and gate D2 after immutable-input correctness checks."""
import csv,hashlib,json,sys
from collections import Counter
from pathlib import Path
OUT=Path(__file__).resolve().parent
ORIGINAL=Path('/home/zhao/SmartContract/ge-sc-llm')
WORKTREE=OUT.parents[4]
sys.path.insert(0,str(OUT))
from coverage_rebuild import read,dump,sha,csvout
def rows(path):
    with Path(path).open() as f:return list(csv.DictReader(f))
def fact_key(r):return (r['task_key'],r['symbol'],r['definition'],r['use'])
def validate_core(before,after):
    changes=sorted(k for k in before if before[k]!=after[k])
    expected=sorted(['scripts/DFG/__init__.py','scripts/DFG/projection.py','scripts/DFG/semantic_cfg.py'])
    if changes!=expected:raise AssertionError('Unexpected core change '+repr(changes))
    return changes
def main():
    b=read(OUT/'before/summary.json');a=read(OUT/'after/summary.json')
    assert b['status']==a['status']=='passed' and b['input_hashes']==a['input_hashes']
    changed=validate_core(b['runtime_code_sha256'],a['runtime_code_sha256'])
    assert all(sha(ORIGINAL/k)==v for k,v in b['runtime_code_sha256'].items())
    assert all(sha(WORKTREE/k)==v for k,v in a['runtime_code_sha256'].items())
    testnames=['full_regression_worktree_v2','original_absolute_resource_test']
    tests={n:read(OUT/(n+'.json')) for n in testnames}
    assert all(r['returncode']==0 for r in tests.values())
    assert read(OUT/'archive_before.json')['returncode']==0
    assert read(OUT/'coverage_before.json')['returncode']==read(OUT/'coverage_after.json')['returncode']==0
    plan=read(ORIGINAL/'scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c/plan.json')
    for cohort in ['reentrancy_author','access_control_author']:
        assert len({j['prepared'] for j in plan['jobs'] if j['cohort']==cohort})==1
    bf={fact_key(r):r for r in rows(OUT/'before/facts.csv')}
    af={fact_key(r):r for r in rows(OUT/'after/facts.csv')}
    assert set(bf)<=set(af),'Lost semantic facts'
    beforef={(r['task_key'],r['function']):r for r in rows(OUT/'before/function_coverage.csv')}
    afterf={(r['task_key'],r['function']):r for r in rows(OUT/'after/function_coverage.csv')}
    fnchanges=[]
    for k,r in afterf.items():
        previous=beforef[k]
        if previous!=r:
            fnchanges.append({'task_key':k[0],'function':k[1],'file':r['file'],
                'function_name':r.get('name'),'before':previous,'after':r})
        assert int(r['analyzed'])>=int(previous['analyzed'])
        if int(r['analyzed'])>int(previous['analyzed']):
            assert 'comment' in previous['fallback_reason']
    attribution=[]
    for edge in read(OUT/'after/added_edges_with_evidence.json'):
        causes=Counter()
        for f in edge['raw_fact_details']:
            prev=bf.get(fact_key(f))
            if prev is not None:
                assert int(prev['projected'])==0
                kind='existing_scalar_fact_exact_projection_recovered'
            else:
                oldfn=beforef[(f['task_key'],f['function'])]
                assert 'comment' in oldfn['fallback_reason']
                kind='if_comment_semantics_recovered'
            causes[kind]+=1
        attribution.append({'task_key':edge['task_key'],'file':edge['file'],
            'source':edge['source'],'target':edge['target'],'fact_causes':dict(causes),
            'file_level_diagnostic_tags':edge['cause']['fixes'],
            'note':'File-level diagnostic tags alone are not per-edge causal attribution.'})
    dump(OUT/'D1_RECOVERY_ATTRIBUTION.json',attribution)
    dump(OUT/'D1_FUNCTION_CHANGES.json',fnchanges)
    summary=[]
    fields=['files','functions_total','functions_analyzed','functions_fallback','file_fallback',
            'files_projection_rejected','facts_extracted','facts_projected',
            'actual_unique_ddg_edges','facts_unmapped_after_projection','self_filtered']
    for key,new in a['tasks'].items():
        old=b['tasks'][key];r={'task_key':key}
        for name in fields:
            r[name+'_before']=old['counts'][name];r[name+'_after']=new['counts'][name]
            r[name+'_delta']=new['counts'][name]-old['counts'][name]
        r.update(added_edges=new['added_edges'],removed_edges=new['removed_edges'],
           new_canonical=len(new['new_canonical']),changed_files=new['changed_files'],
           semantically_unchanged_files=new['unchanged_files'],
           base_unchanged=new['original_base_sha256']==old['original_base_sha256'])
        assert r['base_unchanged'] and not r['removed_edges']
        assert sha(new['graph_file']['path'])==new['graph_file']['sha256']
        summary.append(r)
    csvout(OUT/'D1_COVERAGE_BEFORE_AFTER.csv',summary)
    manifest={'version':'ddg-v1.1-correctness-fix','modified_by':'Codex',
        'base_head':read(OUT/'protected_before.json')['head'],
        'frozen_training_base':'646e9b3495c0fe7f2c4a6e4b72d0bab64d6ee2fc',
        'original_repository':str(ORIGINAL),'development_worktree':str(WORKTREE),
        'core_hashes':a['runtime_code_sha256'],'changed_core_files':changed,
        'input_hashes':a['input_hashes'],'graphs':{k:v['graph_file'] for k,v in a['tasks'].items()},
        'E0':'Original prepared files by reference, byte-identical; no E0 regeneration',
        'E2':'Correctness-fixed scalar DDG; no new training or state analysis',
        'scope':'Only forward DATA_DEF_USE; new canonical combinations may add future model parameters',
        'new_graph_file_sha_verified':True}
    dump(OUT/'D1_PROVENANCE.json',manifest)
    gate={'status':'passed','version':manifest['version'],'modified_by':'Codex',
        'test_executions':tests,'unique_tests_in_main_partition':390,
        'failed_final':0,'skipped_final':0,
        'initial_environment_failures':{'failed':18,'passed':372,'log':'full_regression.log',
            'causes':['17 ROOT-relative grammar library absent','1 original absolute-resource binding in copied worktree'],
            'resolution':'Same pre-existing grammar copied with SHA; absolute-resource assertion run unchanged in original repo'},
        'old_core_hashes_unchanged':True,'old_archive_readonly_check':'passed',
        'all_four_rebuilds_passed':True,'all_previous_semantic_edges_and_evidence_retained':True,
        'no_E0_node_label_feature_source_mapping_base_edge_changes':True,
        'new_edges_have_exact_fact_provenance':True,
        'coverage':summary,'output_manifest_sha256':sha(OUT/'D1_PROVENANCE.json'),
        'final_full_asset_hash_audit':'Pending until D2/D3 and authorized documentation appends finish',
        'compiler_validation':'Not executed; parser robustness != Solidity compiler validation',
        'ready_for_D2':True}
    dump(OUT/'D1_REGRESSION_RESULTS.json',gate)
    print(json.dumps({'status':'passed','tasks':[{k:r[k] for k in ['task_key','added_edges','new_canonical','functions_analyzed_delta','facts_extracted_delta','facts_projected_delta','semantically_unchanged_files']} for r in summary]}),flush=True)
if __name__=='__main__':main()
