"""Seal membership and publish both CP3.1 statistics from the same selected observations."""
from batch import *
from compile_repair.evaluation.report import aggregate_attributions
import gzip

units,refs=members()
replacement=saved('replacement_provenance.json')
previous=saved('baseline_classification.json')
old_rows=[json.loads(x) for x in verified(previous['subset_log'],previous['subset_log_sha256']).splitlines()]
changed=replacement['rows'];run=Path(replacement['seal_path']).parent
seal=json.loads(verified(replacement['seal_path'],replacement['seal_sha256']))
for rel,h in seal['files'].items():verified(run/rel,h)
taxonomy=json.loads(committed(ART/'cp3_continue_v1/taxonomy_verified.json'))
routes=json.loads(committed(ART/'cp3_paths_v1/d6_cp4_final.json'))
category='standard_json_input'
assert category not in {r['category'] for r in taxonomy['categories']}
taxonomy['sources']['etherscan_wrapper']={'path':'compile_repair/PROMPTS.md','section':'4.5b.2; cp3_review_v1/trace_wrapper_example.json; cp3_1_v1/wrapper_premises.json'}
taxonomy['categories'].append(dict(category=category,solc_error_types=[],message_templates=[],error_codes=[],cause='Input container holds named Solidity source contents.',sources=['etherscan_wrapper'],candidate_repair='CP5: materialize the validated source map and map supported compilation settings.',change_level='none',verification=['Compare materialized source bytes with each declared content','D3 and project graph gates after compilation'],verified_versions=['0.8.24','0.8.38'],cp4_operator='Wrap a compilable project as a Solidity standard JSON input or Etherscan source map.',observed_templates=[],d6_route_status='deterministic CP5 project assembly; format detection already implemented'))
taxonomy['input_format_stage']='before version plan; CP3.1 classification only'
taxonomy['duplicate_name_policy']='D21: reject project graph for duplicate AST definitions; primary label slither_incomplete only for a solc-success/Slither-side outcome'
taxonomy['previous_taxonomy_sha256']=sha(committed(ART/'cp3_continue_v1/taxonomy_verified.json'))
save('taxonomy.json',taxonomy)
cats=[r['category'] for r in taxonomy['categories']]
assert len(cats)==30 and len(taxonomy['breaking_changes'])==125
observations=[];mando=[];signatures=Counter();groups=defaultdict(Counter)
destination=B/'unit_attributions.jsonl.gz'
with destination.open('xb') as target, gzip.GzipFile(filename='',mode='wb',fileobj=target,mtime=0) as gz:
    for old in old_rows:
        uid=old['unit_id'];ref=refs[uid]
        assert ref['result_sha256']==old['original_ref']
        current=dict(old)
        if uid in changed:
            row=changed[uid]
            assert row['old']==ref and old['entry_sha256']==row['entry_sha256']
            ref=row['new']
            for k in ('status','primary','any_categories'):current[k]=row[k]
            data=json.loads(verified(ref['result_path'],ref['result_sha256']))
            assert data['status']==row['status']
            if row['status']=='success':
                h=data['attempts'][-1]['slither']['graph_sha256']
                verified(Path(ref['result_path']).with_name('graph.json'),h)
                assert data['attempts'][-1]['slither'].get('graph_usable',True)
            groups[row['impact'][0]][old['status']+' -> '+row['status']]+=1
        else:verified(ref['result_path'],ref['result_sha256'])
        current['selected_result']=ref
        current['source']='cp3_1' if uid in changed else 'cp3'
        observations.append(current)
        gz.write((json.dumps(current,ensure_ascii=False)+'\n').encode())
        if current['corpus']=='MANDO' and current['status']!='success':
            assert current['primary']['categories']==['slither_incomplete']
            mando.append(uid)
        if 'version_dependent' in current['primary']['categories']:
            sig=tuple((v,tuple(c)) for v,c in sorted(current['primary']['by_version'].items(), key=lambda i:tuple(map(int,i[0].split('.')))))
            signatures[sig]+=1
assert len(mando)==3 and len({o['unit_id'] for o in observations})==len(refs)==31071
summary=aggregate_attributions(observations,cats)
for key,labels in [('primary',lambda r:r['primary']['categories']),('any_candidate',lambda r:r['any_categories'])]:
    examples=defaultdict(list)
    for r in sorted(observations,key=lambda r:(r['entry_sha256'],r['unit_id'])):
        for cat in labels(r):
            if len(examples[cat])<3:examples[cat].append({k:r[k] for k in ('unit_id','corpus','entry_sha256','selected_result')})
    for row in summary[key]['category_unit_counts']:row['unit_examples']=examples[row['category']]
summary.update(denominator='remaining unrepaired eligible units; multi-label counts once per unit per category',
        old_basis='cp3_paths_v1/failure_summary.json (the unreplaced historical any-candidate table)',
        eligible=len(refs),excluded_non_solidity=len(units)-len(refs),mando_primary_slither_only=mando,
        source_artifact_sha256=sha(destination.read_bytes()),replacement_transitions=groups,
        selected_new=len(changed),reused_old=len(refs)-len(changed),
        version_dependent_signatures=[dict(versions=dict(sig),units=n) for sig,n in signatures.most_common(10)])
save('failure_summary.json',summary)
pcounts={r['category']:r for r in summary['primary']['category_unit_counts']}
acounts={r['category']:r for r in summary['any_candidate']['category_unit_counts']}
routes['categories'].append(dict(category=category,route='deterministic',repair='CP5 解包并核验源字节，映射受支持的编译设置',change_level='none',mechanical_checks='逐源 SHA、D3 与项目图检查',cp4_operator='将可编译项目及其设置包装为 standard JSON / Etherscan 多文件对象',fallback=None,sources=['etherscan_wrapper'],implementation_in_cp3=False,no_source_corruption_operator_reason=None))
for row in routes['categories']:
    name=row['category']
    row.update(observed_units=pcounts[name]['units'],fraction_remaining_failures=pcounts[name]['fraction_remaining_failures'],any_candidate_units=acounts[name]['units'])
    if name=='slither_incomplete':row['duplicate_contract_names']='D21: tool limitation; do not rewrite legal source.'
routes['schema']='cp3.1-d6-priority'
routes['status']='complete_cp3.1_routes_and_cp4_operator_inventory'
routes['implementation_priority_by_frequency_only']=sorted(cats,key=lambda k:(-pcounts[k]['units'],k))
routes['zero_frequency_categories_retained']=sorted(k for k in cats if not pcounts[k]['units'])
routes['count_basis']='primary causes; version_dependent is a statistics bucket outside the taxonomy'
routes['frequency_summary_sha256']=sha((B/'failure_summary.json').read_bytes())
routes['basis_sha256']=sha((B/'taxonomy.json').read_bytes())
assert len(routes['categories'])==30 and len(routes['breaking_changes'])==125
save('d6_cp4_final.json',routes)
print('success',sum(summary['primary']['success'].values()),'remaining',sum(summary['primary']['remaining_failures'].values()),'replaced',len(changed))
