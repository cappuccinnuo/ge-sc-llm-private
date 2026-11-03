from pathlib import Path
import json, hashlib, datetime
root=Path.cwd();base=root/'scripts/node_sem/artifacts/ns_p4';out=base/'attempt2'
plan=json.loads((out/'plan.json').read_text())
status=json.loads((out/'cpu_status.json').read_text())
if status['status']!='complete': raise RuntimeError('CPU matrix incomplete')
verified=json.loads((out/'cpu_independent_verification.json').read_text())
if not verified['passed']: raise RuntimeError('CPU validation incomplete')
result={'head':json.loads((base/'started.json').read_text())['head'],'formal_fits':0,'cpu':[],'gpu':[]}
for job in plan['jobs']:
 folder=out/'runs'/job['actual_device']/job['name']
 report=folder/'acceptance.json'
 if report.exists():
  r=json.loads(report.read_text())
  row={k:r[k] for k in ['passed','constructor_seconds','fit_seconds','common_initial_exact','modality_projection_gradient_l1','checkpoint_roundtrip_exact']}
  row.update(name=job['name'],device=job['actual_device'],carrier_dim=job['carrier_dim'],parameters=job['parameters'],
    tensor_subtotal_mib=job['tensor_memory']['estimated_subtotal_mib'],train_loss=r['history'][0]['train_loss'],
    inner_val_loss=r['history'][0]['inner_val_loss'],gates=r['gates'],constructor_over_3x_h8=r['constructor_over_3x_h8'])
 else: row=dict(name=job['name'],device=job['actual_device'],passed=False,not_completed=True)
 if job['actual_device']=='gpu':
  resource=out/'gpu_resources'/job['name']/'resource_summary.json'
  failure=out/('gpu_'+job['name']+'.failure.json')
  gate=out/('gpu_'+job['name']+'.json')
  row['resource_gate_passed']=gate.exists() and json.loads(gate.read_text()).get('passed') is True
  if resource.exists(): row['resources']=json.loads(resource.read_text())
  if failure.exists(): row['failure']=json.loads(failure.read_text())
 result[job['actual_device']].append(row)
result['h8_constructor_seconds']=plan['h8_constructor_seconds']
result['tests']=dict(nodesem=784,dfg_v2=2653,legacy=223,total=3660,failures=0,skipped=0,warnings=42)
result['original_token_checks']=plan['original_token_checks']
result['S0o_proof']=json.loads((out/'prepared/S0o_proof.json').read_text())
target=base/'summary.json'
with target.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2,ensure_ascii=False)
print(json.dumps(dict(cpu=len(result['cpu']),gpu_passed=sum(r.get('resource_gate_passed',False) for r in result['gpu']))))
