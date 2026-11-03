import os,subprocess,json,time
from pathlib import Path
out=Path(__file__).resolve().parent
cpu=json.loads((out/'cpu_controller.json').read_text())
if len(cpu)!=6 or any(r['exit_code'] for r in cpu):raise RuntimeError('All six CPU checks must finish successfully first')
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TREE_SITTER_LIB_DIR='/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64')
env.pop('CUDA_VISIBLE_DEVICES',None)
python='/home/zhao/miniconda3/envs/mando/bin/python'
jobs=[('reentrancy_node',n) for n in ('S1o','S2','S4','S4g','S4m','S4-noG')]+[('reentrancy_contract',n) for n in ('S1o','S4')]
results=[]
for task,name in jobs:
 job='gpu_'+task+'_'+name
 command=[python,'-B','-u','-m','scripts.node_sem.p4b_acceptance','run','--only',job,'--out',str(out)]
 started=time.time()
 with (out/(job+'.log')).open('x') as stream:r=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT)
 failure=out/(job+'.failure.json')
 allowed_oom=task=='reentrancy_contract' and failure.exists() and json.loads(failure.read_text()).get('cuda_oom') is True
 results.append(dict(job=job,command=command,exit_code=r.returncode,allowed_contract_oom=allowed_oom,seconds=time.time()-started))
 (out/'gpu_controller.json').write_text(json.dumps(results,indent=2)+'\n')
 if r.returncode and not allowed_oom:raise SystemExit(r.returncode)
