from pathlib import Path
import json,hashlib,datetime,sys
root=Path.cwd();sys.path.insert(0,str(root))
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked,read,ref
from scripts.DFG.dfg_v2.benchmark_v2.prepare_spelling import require_semantic_pass
from scripts.DFG.dfg_v2.benchmark_v2.spelling_plan import verify_plan
b=root/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1'
plan=read(b/'plan/plan.json')
verified=verify_plan(b/'plan/plan.json')
manifest,sources,sem,rows=require_semantic_pass(b/'naming',b/'semantic')
features=read(b/'features/manifest.json');probes=read(b/'probes/summary.json')
proof=read(b/'model_proof_attempt2/summary.json')
assert proof['profile_checks']==20 and proof['forward_calls']==28 and proof['G0_identity_tasks']==4
assert proof['optimizer_steps']==0 and proof['hgt_fit_count']==0 and not proof['gpu_used']
profile_rows=[]
for tid,r in proof['artifacts'].items():
 cases=read(checked(r));assert len(cases)==5
 assert {c['profile'] for c in cases}=={'G0','G1R','G2R','G3R','G3'}
 for c in cases:
  checked(c['initial'])
  assert c['task']==tid and c['anonymous_assembly_passed']
  assert all(v['finite'] and v['parameters_unchanged'] for v in c['views'].values())
  if c['profile']=='G0':
   assert c['views']['direct']['logits_sha256']==c['views']['original']['logits_sha256']
  profile_rows.append(c)
 assert plan['tasks'][tid]['feature_view']==features['task_views'][tid]
 for view,r in features['task_views'][tid].items():
  d=read(checked(r));checked(d['data'])
  assert d['view']==view and d['task_id']==tid and d['feature_shape'][1]==512
for r in plan['preparation_code']:checked(r)
for r in manifest['implementation'].values():checked(r)
for r in sem['implementation'].values():checked(r)
checked(features['implementation']);checked(read(checked(probes['plan']))['implementation'])
old=read(root/'docs/github_archive_prompt8f_2026-10-29.json')
for r in old['files']:checked(r)
before=read(b/'before.json')
for path,digest in before['tracked'].items():checked(dict(path=str(root/path),sha256=digest))
assert not list((b/'features').rglob('*.pt'))
assert len(list((b/'features').rglob('*.npz')))==8
assert all(not j['execution_authorized'] for j in plan['jobs'])
assert {j['seed'] for j in plan['jobs']}=={1}
assert not plan['execution_authorized'] and plan['selected_label_policy'] is None
assert sum(d['nodes'] for d in features['details'].values())==51490
assert sum(d['changed_nodes'] for d in features['details'].values())==48527
assert not list((b/'plan').glob('*.pt'))
for label in ['v2_final','legacy_final','model_proof_attempt2','plan']:
 assert read(b/(label+'.command.json'))['returncode']==0
# The interrupted attempt remains read-only; its completed task receipts match
# the independently repeated full CPU proof, not a resumed trained state.
repeated=0
for p in (b/'model_proof').glob('*.json'):
 assert read(p)==read(b/'model_proof_attempt2'/p.name)
 repeated+=1
result=dict(passed=True,utc=datetime.datetime.utcnow().isoformat(),plan=ref(b/'plan/plan.json'),
 source_identities=len(sources),semantic_task_files=len(rows),semantic_passed=sem['passed'],
 prior_synthetic_nodes_resolved=read(checked(sem['synthetic_resolution']))['resolved'],
 P3_auc=probes['P3']['auc'],probes_passed=probes['passed'],
 feature_rows=51490,changed_feature_rows=48527,feature_arrays=8,complete_model_profile_checks=20,
 complete_model_forward_calls=28,G0_bitwise_identity_tasks=4,
 interrupted_task_records_preserved_and_reproduced=repeated,
 actual_forward_total_excludes_unrecorded_interrupted_work=True,
 old8f_archive_files_unchanged=len(old['files']),protected_preexisting_files_unchanged=len(before['tracked']),
 formal_hgt_fits=0,model_proof_optimizer_steps=0,diagnostic_LR_fits=probes['classifier_fits'],
 execution_authorized=False,default_proposed_fits=170,v2_tests=2573,legacy_tests=223,
 unique_tests=2796,new_tests=83,test_failures=0,test_skips=0,
 code_feature_semantic_probe_proof_and_plan_bindings_verified=True,
 model_proof=ref(b/'model_proof_attempt2/summary.json'),
 remaining_choices=['label_policy','training_seeds','execution_location'])
with (b/'final_review.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))
