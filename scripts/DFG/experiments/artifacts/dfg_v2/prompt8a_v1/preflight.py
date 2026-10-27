"""Prompt 8A read-only preparation acceptance; no fitting and no F1 output."""
import os, sys, json, subprocess, time, gc, shutil
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
os.chdir(str(ROOT));sys.path.insert(0,str(ROOT))
OUT=Path(__file__).resolve().parent
from scripts.DFG.dfg_v2.experiment import run,batch
from scripts.DFG.dfg_v2.experiment.init import _semantic
from scripts.DFG.integration.io import sha256,read_json
import torch
def save(name,v):
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,ensure_ascii=False);f.write('\n')
plan_path=ROOT/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json'
assert sha256(plan_path)=='07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de'
assert sha256(plan_path.with_name('plan.seal.json'))=='55aebf929cd578a4a9cd6df4956a4cc3816af010d1963b57a52a1559db5a59f8'
t=time.monotonic()
plan=run._load_plan(plan_path)
partial=run.verify(plan_path,require_complete=False)
assert partial['completed_jobs']==0 and partial['expected_jobs']==150
assert not (plan_path.parent/'runs').exists()
assert not batch._controller_failures(plan_path)
rows=[];families=[]
for task_id,task in plan['tasks'].items():
 for fold in task['folds']:
  common=None
  for profile in plan['profiles']:
   job=next(j for j in plan['jobs'] if j['task_id']==task_id and j['fold']==fold and j['profile']==profile)
   _,info,entry=run._prepared(plan,job)
   initial=run._initial(entry,info,job)
   schema=entry['support']['schema']
   nodes={r['name']:r['index'] for r in schema['node_types']}
   edges={tuple(r['canonical']):r['index'] for r in schema['canonical_relations']}
   semantic=_semantic(initial['state_dict'],nodes,edges)
   if profile=='G0':common=semantic
   else:
    assert set(common)<=set(semantic)
    assert all(torch.equal(v,semantic[k]) for k,v in common.items())
   assert initial['optimizer_steps']==0
   assert sum(v.numel() for v in initial['state_dict'].values())==entry['parameter_count']
   rows.append(dict(job=run.job_id(job),initial=entry['initial'],fit_seed=initial['fit_seed'],optimizer_steps=0,common_exact=True))
   del initial,semantic
  families.append(dict(task_id=task_id,fold=fold,profiles=list(plan['profiles']),common_exact=True))
  del common;gc.collect()
  print(task_id,fold,'five saved initial states verified',flush=True)
save('preflight_acceptance.json',dict(passed=True,plan=run._ref(plan_path),seal=run._ref(plan_path.with_name('plan.seal.json')),
 expected_jobs=150,completed_jobs=0,stage_A_jobs=60,stage_B_jobs=90,runtime_exact=True,initials=rows,families=families,
 initial_tensor_count=len(rows),family_count=len(families),seconds=time.monotonic()-t,
 command_adaptation='Existing run.verify(require_complete=False) used; batch verify requires complete stage. No production changes.',
 current_head=run._git_head(),wsl_disk_free_bytes=shutil.disk_usage(str(ROOT)).free))
print('PREFLIGHT PASSED: 0/150 fits; 150 saved states and 30 common-parameter families accepted',flush=True)
