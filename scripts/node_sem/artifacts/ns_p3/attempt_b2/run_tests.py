import os,subprocess,time,json,sys
from pathlib import Path
ROOT=Path.cwd();BASE=Path(__file__).resolve().parent
M="/home/zhao/miniconda3/envs/mando/bin/python"
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",CUDA_VISIBLE_DEVICES="",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
commands=[
 ("node_sem",[M,"-B","-m","pytest","-q","-p","no:cacheprovider","scripts/node_sem/tests"]),
 ("dfg_v2",[M,"-B","-m","pytest","-q","-p","no:cacheprovider","scripts/DFG/dfg_v2/tests"]),
 ("legacy",[M,"-B","-m","pytest","-q","-p","no:cacheprovider","scripts/DFG/tests","tests/test_graph_utils.py"]),
 ("offline",["/home/zhao/miniconda3/envs/nodesem/bin/python","-s","-B","-m","unittest","discover","-s","scripts/node_sem/offline","-p","test_ctx_budget.py"])]
runs=[]
for name,cmd in commands:
 (BASE/"tests_status.json").write_text(json.dumps(dict(status="running",current=name,pid=os.getpid())))
 start=time.monotonic()
 with (BASE/(name+"_tests.log")).open("x") as log:
  proc=subprocess.run(cmd,env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
 row=dict(name=name,command=cmd,exit_code=proc.returncode,seconds=time.monotonic()-start)
 runs.append(row);(BASE/"tests.json").write_text(json.dumps(runs,indent=2));print(json.dumps(row),flush=True)
 if proc.returncode:
  (BASE/"tests_status.json").write_text(json.dumps(dict(status="failed",last=row)))
  sys.exit(proc.returncode)
(BASE/"tests_status.json").write_text(json.dumps(dict(status="complete",suites=len(runs))))
