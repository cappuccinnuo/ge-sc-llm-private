import json,os,subprocess,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
BASE=Path(__file__).resolve().parent
env=dict(os.environ,CUDA_VISIBLE_DEVICES="",PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",
 TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
records=[]
for name,paths in [("dfg_v2",["scripts/DFG/dfg_v2/tests"]),("legacy",["scripts/DFG/tests","tests/test_graph_utils.py"])]:
 cmd=["/home/zhao/miniconda3/envs/mando/bin/python","-B","-m","pytest","-q","-p","no:cacheprovider"]+paths
 start=time.monotonic()
 with (BASE/(name+"_tests.log")).open("x") as out:r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT)
 records.append(dict(suite=name,command=cmd,exit_code=r.returncode,seconds=time.monotonic()-start))
 (BASE/"test_runs.json").write_text(json.dumps(records,indent=2))
 if r.returncode:sys.exit(r.returncode)
