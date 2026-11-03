import os, subprocess, json, time
from pathlib import Path
out=Path(__file__).resolve().parent
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TREE_SITTER_LIB_DIR='/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64')
python='/home/zhao/miniconda3/envs/mando/bin/python'
results=[]
for name in ('S3','S3m','S4','S4g','S4m','S4-noG'):
 job='cpu_reentrancy_node_'+name
 command=[python,'-B','-u','-m','scripts.node_sem.p4b_acceptance','run','--only',job]
 started=time.time()
 with (out/(job+'.log')).open('x') as stream:r=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT)
 results.append(dict(job=job,command=command,exit_code=r.returncode,seconds=time.time()-started))
 (out/'cpu_controller.json').write_text(json.dumps(results,indent=2)+'\n')
 if r.returncode:raise SystemExit(r.returncode)
