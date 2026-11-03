import os, subprocess, json, time
from pathlib import Path
out=Path(__file__).resolve().parent
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TREE_SITTER_LIB_DIR='/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64')
python='/home/zhao/miniconda3/envs/mando/bin/python'
results=[]
for name,paths in [('nodesem',['scripts/node_sem/tests']),('dfg_v2',['scripts/DFG/dfg_v2/tests']),('legacy',['scripts/DFG/tests','tests/test_graph_utils.py'])]:
 command=[python,'-B','-m','pytest','-q','-p','no:cacheprovider']+paths
 started=time.time()
 with (out/(name+'_tests.log')).open('x') as stream:r=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT)
 results.append(dict(suite=name,command=command,exit_code=r.returncode,seconds=time.time()-started))
 (out/'regressions.json').write_text(json.dumps(results,indent=2)+'\n')
 if r.returncode:raise SystemExit(r.returncode)
