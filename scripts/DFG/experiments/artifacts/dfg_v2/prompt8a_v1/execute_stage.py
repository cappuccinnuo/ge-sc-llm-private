"""Invoke sealed stage A once; stop on any failure, never retry or execute B."""
import os,sys,subprocess,json,time
from pathlib import Path
ROOT=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11');os.chdir(str(ROOT))
OUT=Path(__file__).resolve().parent
PLAN=ROOT/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json'
AUTH=PLAN.parent/'stage_A_authorization.json'
for name in ['store_verify','targeted_tests','v2_tests','legacy_tests']:
 with (OUT/(name+'.command.json')).open() as f:assert json.load(f)['returncode']==0
with (OUT/'preflight_acceptance.json').open() as f:assert json.load(f)['passed']
commands=[
 ('stage_A_execute',['execute','--plan',str(PLAN),'--stage','A','--authorization-record',str(AUTH)]),
 ('stage_A_verify',['verify','--plan',str(PLAN),'--stage','A']),
 ('stage_A_interim',['interim','--plan',str(PLAN),'--stage','A'])]
for name,args in commands:
 argv=[sys.executable,'-u','-B','-m','scripts.DFG.dfg_v2.experiment.batch']+args
 start=time.time()
 with (OUT/(name+'.started.json')).open('x') as f:json.dump(dict(argv=argv,started_unix=start,pid=os.getpid()),f,indent=2)
 print(name,'starting; child output isolated in',str(OUT/(name+'.log')),flush=True)
 with (OUT/(name+'.log')).open('x',encoding='utf8') as stream:
  proc=subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT,env=os.environ.copy())
 result=dict(argv=argv,returncode=proc.returncode,seconds=time.time()-start,finished_unix=time.time())
 with (OUT/(name+'.command.json')).open('x') as f:json.dump(result,f,indent=2)
 print(name,'finished',proc.returncode,'seconds',round(result['seconds'],2),flush=True)
 if proc.returncode:raise SystemExit(proc.returncode)
print('Stage A complete and interim report sealed. STOP: stage B remains unauthorized.',flush=True)
