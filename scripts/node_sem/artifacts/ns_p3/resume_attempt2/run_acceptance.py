"""Await authorized encoder completion, then run acceptance exactly once."""
import json,os,subprocess,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
BASE=Path(__file__).resolve().parent
while True:
 state=json.loads((BASE/"status.json").read_text())
 if state.get("status")=="failed":
  raise RuntimeError("Encoder failed; acceptance not started")
 if state.get("status")=="complete":break
 time.sleep(5)
cmd=["/home/zhao/miniconda3/envs/mando/bin/python","-B","-m","scripts.node_sem.p3_acceptance",
 "--out","scripts/node_sem/artifacts/ns_p3/acceptance_v1",
 "--encoding-index",str(BASE/"encoding_index.json")]
env=dict(os.environ,CUDA_VISIBLE_DEVICES="",PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",
 TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
with (BASE/"acceptance.log").open("x") as out:r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT)
(BASE/"acceptance_run.json").write_text(json.dumps(dict(command=cmd,exit_code=r.returncode),indent=2))
sys.exit(r.returncode)
