"""Detached command record for the explicitly approved Prompt 8H resume."""
import os,sys,json,time,subprocess
from pathlib import Path
b=Path(__file__).resolve().parent
env=os.environ.copy()
env.pop("CUDA_VISIBLE_DEVICES",None)
env.update(PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",
    TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
status=b/"orchestration_resume_v3_status.json"
record=dict(pid=os.getpid(),started_unix=time.time(),automatic_retry=False,
    existing_successes=71,new_fits_authorized=99,
    read_only_predecessor="resume_v2/controller_scan_race.json",restart_from_sealed_initial=True,
    detached_session=True,head=subprocess.check_output(["git","rev-parse","HEAD"],universal_newlines=True).strip())
steps=[("full_matrix","scripts.DFG.dfg_v2.benchmark_v2.execution","all"),
    ("reporting","scripts.DFG.dfg_v2.benchmark_v2.reporting",None)]
with (b/"orchestration_resume_v3.command.json").open("x") as h:
    json.dump(dict(record,steps=steps,python=sys.executable),h,indent=2)
if status.exists():raise FileExistsError(status)
def save(stage,state,**kw):
    value=dict(record,stage=stage,status=state,updated_unix=time.time(),**kw)
    tmp=status.with_suffix(".tmp")
    tmp.write_text(json.dumps(value,indent=2))
    tmp.replace(status)
for name,module,arg in steps:
    cmd=[sys.executable,"-B","-m",module]+([arg] if arg else [])
    log=b/(name+"_resume_v3.log")
    save(name,"running",command=cmd,log=str(log))
    print("running",name,flush=True)
    with log.open("x") as h:
        p=subprocess.run(cmd,env=env,stdout=h,stderr=subprocess.STDOUT)
    if p.returncode:
        save(name,"stopped",returncode=p.returncode,log=str(log))
        print("STOP",name,p.returncode,flush=True)
        sys.exit(p.returncode)
    print("completed",name,flush=True)
save("all","complete")
print("complete",flush=True)
