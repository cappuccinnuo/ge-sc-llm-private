"""Wait for the existing jobs; run acceptance once, never retry a failed job."""
import json,os,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parent
while True:
    states=[json.loads((BASE/name).read_text()) for name in ("pipeline_status.json","tests_status_v2.json")]
    if any(s["status"]=="failed" for s in states):
        (BASE/"acceptance_status.json").write_text(json.dumps(dict(status="blocked",upstream=states)))
        sys.exit(1)
    if all(s["status"]=="complete" for s in states):break
    time.sleep(10)
cmd=["/home/zhao/miniconda3/envs/mando/bin/python","-B","-m","scripts.node_sem.p3b2_acceptance","--base",str(BASE)]
env=dict(os.environ,CUDA_VISIBLE_DEVICES="",PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
(BASE/"acceptance_status.json").write_text(json.dumps(dict(status="running",command=cmd,pid=os.getpid())))
start=time.monotonic()
with (BASE/"acceptance.log").open("x") as log:
    proc=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
result=dict(status="complete" if proc.returncode==0 else "failed",command=cmd,exit_code=proc.returncode,seconds=time.monotonic()-start,automatic_retry=False)
(BASE/"acceptance_status.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
sys.exit(proc.returncode)
