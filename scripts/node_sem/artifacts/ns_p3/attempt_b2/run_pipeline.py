"""NS-P3b2 four preparations + eight serial offline encodings; no fit/retry."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path.cwd()
BASE=Path(__file__).resolve().parent
M="/home/zhao/miniconda3/envs/mando/bin/python"
N="/home/zhao/miniconda3/envs/nodesem/bin/python"
tasks=sorted(json.loads((ROOT/"scripts/node_sem/artifacts/facts_v1/CURRENT.json").read_text())["tasks"])
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONNOUSERSITE="1",
 OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64",
 HF_HUB_DISABLE_PROGRESS_BARS="1")
records=[]
def run(cmd,label,gpu=False):
    state=dict(status="running",label=label,completed=len(records),pid=os.getpid(),command=cmd)
    (BASE/"pipeline_status.json").write_text(json.dumps(state,indent=2))
    child_env=dict(env)
    if not gpu: child_env["CUDA_VISIBLE_DEVICES"]=""
    started=time.monotonic()
    with (BASE/(label+".log")).open("x") as stream:
        proc=subprocess.run(cmd,env=child_env,stdout=stream,stderr=subprocess.STDOUT,cwd=ROOT)
    item=dict(label=label,command=cmd,exit_code=proc.returncode,seconds=time.monotonic()-started)
    records.append(item); print(json.dumps(item),flush=True)
    (BASE/"pipeline_runs.json").write_text(json.dumps(records,indent=2))
    if proc.returncode:
        (BASE/"pipeline_status.json").write_text(json.dumps(dict(status="failed",last=item,automatic_retry=False),indent=2))
        sys.exit(proc.returncode)
for task in tasks:
    run([M,"-B","-m","scripts.node_sem.p3_prepare","--task",task,
         "--ctx-out",str(BASE/"fields/original"/task),
         "--static-out",str(BASE/"static/original"/task)],"prepare_"+task)
for task in tasks:
    for mode in ("original","masked"):
        suffix="" if mode=="original" else "_masked"
        run([N,"-s","-B","scripts/node_sem/offline/encode_ctx.py","--fields",
             str(BASE/"fields/original"/task/("ctx_fields"+suffix+".jsonl")),
             "--out",str(BASE/"encoded/original"/task/("ctx"+suffix))],
             "encode_"+task+"_"+mode,gpu=True)
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref,write,read
index=dict(version="nodesem-p3b2-encoding-index-v1",tasks={})
for task in tasks:
    index["tasks"][task]={}
    for mode in ("original","masked"):
        suffix="" if mode=="original" else "_masked"
        manifest=BASE/"encoded/original"/task/("ctx"+suffix)/"manifest.json"
        meta=read(manifest)["encoding"]
        if not meta["repeat_bitwise"] or meta["repeat_max_abs_error"]!=0:
            raise ValueError("NS-P3b2 requires bitwise repeated encoding")
        index["tasks"][task][mode]=ref(manifest)
write(BASE/"encoding_index.json",index)
write(BASE/"encoding_index.seal.json",dict(index=ref(BASE/"encoding_index.json")))
(BASE/"pipeline_status.json").write_text(json.dumps(dict(status="complete",completed=len(records)),indent=2))
