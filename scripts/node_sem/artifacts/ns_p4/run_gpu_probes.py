import os,subprocess,json,time,sys
from pathlib import Path
base=Path.cwd()/'scripts/node_sem/artifacts/ns_p4';out=base/'attempt2'
verified=json.loads((out/'cpu_independent_verification.json').read_text())
if not verified['passed'] or len(verified['checks'])!=7: raise RuntimeError('CPU independent verification incomplete')
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TREE_SITTER_LIB_DIR='/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64')
env.pop('CUDA_VISIBLE_DEVICES',None)
runs=[]
for name in ['S1o','S4']:
 cmd=['/home/zhao/miniconda3/envs/mando/bin/python','-B','-m','scripts.node_sem.p4_acceptance','gpu','--only',name,'--out',str(out)]
 (out/'gpu_status.json').write_text(json.dumps(dict(status='running',name=name,pid=os.getpid(),completed=len(runs))))
 t=time.monotonic()
 with (out/('gpu_'+name+'.log')).open('x') as stream:
  p=subprocess.run(cmd,env=env,stdout=stream,stderr=subprocess.STDOUT)
 row=dict(name=name,command=cmd,exit_code=p.returncode,seconds=time.monotonic()-t)
 runs.append(row);(out/'gpu_commands.json').write_text(json.dumps(runs,indent=2));print(json.dumps(row),flush=True)
 if p.returncode:
  (out/'gpu_status.json').write_text(json.dumps(dict(status='failed',last=row,completed=len(runs)-1)));sys.exit(p.returncode)
(out/'gpu_status.json').write_text(json.dumps(dict(status='complete',completed=len(runs))))
