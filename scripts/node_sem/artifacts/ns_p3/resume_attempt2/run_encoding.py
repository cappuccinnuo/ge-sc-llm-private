"""Authorized recovery of interrupted NS-P3b offline work, no automatic retry."""
import json,os,subprocess,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
BASE=Path(__file__).resolve().parent
ART=ROOT/"scripts/node_sem/artifacts"
def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def save(p,d):p.write_text(json.dumps(d,indent=2),encoding="utf8")
tasks=sorted(json.loads((ART/"facts_v1/CURRENT.json").read_text())["tasks"])
index={task:{} for task in tasks}
first=ART/"ns_p3/encoded/original/access_control_contract/ctx/manifest.json"
index["access_control_contract"]["original"]=ref(first)
records=[]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONNOUSERSITE="1",
         OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",HF_HUB_DISABLE_PROGRESS_BARS="1")
for task in tasks:
 for mode in ("original","masked"):
  if task=="access_control_contract" and mode=="original":continue
  suffix="" if mode=="original" else "_masked"
  output=BASE/"encoded/original"/task/("ctx"+suffix)
  cmd=["/home/zhao/miniconda3/envs/nodesem/bin/python","-s","-B",
       "scripts/node_sem/offline/encode_ctx.py","--fields",
       str(ART/"ctx_v1/original"/task/("ctx_fields"+suffix+".jsonl")),"--out",str(output)]
  started=time.monotonic()
  save(BASE/"status.json",dict(current_task=task,names=mode,completed=len(records),reused=1,pid=os.getpid(),command=cmd))
  with (BASE/(task+"_"+mode+"_encode.log")).open("x") as stream:
   proc=subprocess.run(cmd,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
  record=dict(task=task,names=mode,command=cmd,exit_code=proc.returncode,seconds=time.monotonic()-started)
  records.append(record);save(BASE/"runs.json",records)
  if proc.returncode:
   save(BASE/"status.json",dict(status="failed",last=record,completed=len(records)-1,reused=1))
   sys.exit(proc.returncode)
  index[task][mode]=ref(output/"manifest.json")
  save(BASE/"completed_index.json",index)
save(BASE/"encoding_index.json",dict(tasks=index,reused=[ref(first)],new_jobs=7))
save(BASE/"encoding_index.seal.json",dict(index=ref(BASE/"encoding_index.json")))
save(BASE/"status.json",dict(status="complete",completed=7,reused=1))
