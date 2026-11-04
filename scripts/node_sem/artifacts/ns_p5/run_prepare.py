import os,subprocess,time,json
from pathlib import Path
out=Path(__file__).resolve().parent
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TREE_SITTER_LIB_DIR='/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64')
cmd=['/home/zhao/miniconda3/envs/mando/bin/python','-B','-m','scripts.node_sem.p5_prepare','prepare','--decisions',str(out/'decisions.json')]
start=time.monotonic()
with (out/'prepare.log').open('xb') as stream:
    p=subprocess.run(cmd,env=env,stdout=stream,stderr=subprocess.STDOUT)
(out/'prepare_exit.json').write_text(json.dumps(dict(command=cmd,exit_code=p.returncode,seconds=time.monotonic()-start),indent=2)+'\n')
print((out/'prepare.log').read_text()[-6000:]);raise SystemExit(p.returncode)
