import os,subprocess,json,time,sys
from pathlib import Path
out=Path(__file__).resolve().parent
root=Path.cwd()
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TREE_SITTER_LIB_DIR='/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64')
python='/home/zhao/miniconda3/envs/mando/bin/python'
commands=[('nodesem',['scripts/node_sem/tests']),('dfg_v2',['scripts/DFG/dfg_v2/tests']),('legacy',['scripts/DFG/tests','tests/test_graph_utils.py'])]
runs=[]
for name,paths in commands:
 cmd=[python,'-B','-m','pytest','-q','-p','no:cacheprovider']+paths;t=time.monotonic()
 (out/'regression_status.json').write_text(json.dumps(dict(status='running',current=name,pid=os.getpid())))
 with (out/(name+'_regression.log')).open('x') as stream:
  p=subprocess.run(cmd,env=env,cwd=str(root),stdout=stream,stderr=subprocess.STDOUT)
 row=dict(name=name,command=cmd,exit_code=p.returncode,seconds=time.monotonic()-t)
 runs.append(row);(out/'regressions.json').write_text(json.dumps(runs,indent=2));print(json.dumps(row),flush=True)
 if p.returncode:
  (out/'regression_status.json').write_text(json.dumps(dict(status='failed',last=row)));sys.exit(p.returncode)
(out/'regression_status.json').write_text(json.dumps(dict(status='complete',suites=3)))
