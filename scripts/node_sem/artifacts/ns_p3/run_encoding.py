"""Execute exactly eight frozen-encoder jobs serially; stop on first failure."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
BASE=Path(__file__).resolve().parent
tasks=sorted(json.loads((ROOT/"scripts/node_sem/artifacts/facts_v1/CURRENT.json").read_text())["tasks"])
records=[]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONNOUSERSITE="1",
         OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",HF_HUB_DISABLE_PROGRESS_BARS="1")
for task in tasks:
 for mode in ("original","masked"):
  suffix="" if mode=="original" else "_masked"
  output=BASE/"encoded/original"/task/("ctx" if mode=="original" else "ctx_masked")
  cmd=["/home/zhao/miniconda3/envs/nodesem/bin/python","-s","-B",
       "scripts/node_sem/offline/encode_ctx.py","--fields",
       str(ROOT/"scripts/node_sem/artifacts/ctx_v1/original"/task/("ctx_fields"+suffix+".jsonl")),
       "--out",str(output)]
  started=time.monotonic()
  status=dict(current_task=task,names=mode,completed=len(records),pid=os.getpid(),command=cmd)
  (BASE/"encoding_status.json").write_text(json.dumps(status,indent=2))
  with (BASE/(task+"_"+mode+"_encode.log")).open("x") as stream:
   proc=subprocess.run(cmd,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
  record=dict(task=task,names=mode,command=cmd,exit_code=proc.returncode,seconds=time.monotonic()-started)
  records.append(record)
  print(json.dumps(record),flush=True)
  (BASE/"encoding_runs.json").write_text(json.dumps(records,indent=2))
  if proc.returncode:
   (BASE/"encoding_status.json").write_text(json.dumps(dict(status="failed",last=record,completed=len(records)-1),indent=2))
   sys.exit(proc.returncode)
(BASE/"encoding_status.json").write_text(json.dumps(dict(status="complete",completed=len(records)),indent=2))
