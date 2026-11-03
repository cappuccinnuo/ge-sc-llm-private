import os,subprocess,json,time,sys
from pathlib import Path
root=Path.cwd();base=root/'scripts/node_sem/artifacts/ns_p4';out=base/'attempt2'
if not json.loads((out/'prepare.complete.json').read_text())['passed']: raise RuntimeError('Preparation gate incomplete')
if json.loads((base/'regression_status.json').read_text())['status']!='complete': raise RuntimeError('Regression gate incomplete')
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TREE_SITTER_LIB_DIR='/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64')
runs=[]
for name in ['S2','S3','S4','S4g','S4-noG','S3m','S4m']:
 cmd=['/home/zhao/miniconda3/envs/mando/bin/python','-B','-m','scripts.node_sem.p4_acceptance','cpu','--only',name,'--out',str(out)]
 (out/'cpu_status.json').write_text(json.dumps(dict(status='running',name=name,pid=os.getpid(),completed=len(runs))))
 t=time.monotonic()
 with (out/('cpu_'+name+'.log')).open('x') as stream:
  p=subprocess.run(cmd,env=env,stdout=stream,stderr=subprocess.STDOUT)
 row=dict(name=name,command=cmd,exit_code=p.returncode,seconds=time.monotonic()-t)
 runs.append(row);(out/'cpu_commands.json').write_text(json.dumps(runs,indent=2));print(json.dumps(row),flush=True)
 if p.returncode:
  (out/'cpu_status.json').write_text(json.dumps(dict(status='failed',last=row,completed=len(runs)-1)));sys.exit(p.returncode)
(out/'cpu_status.json').write_text(json.dumps(dict(status='complete',completed=len(runs))))
