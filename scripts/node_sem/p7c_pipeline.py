"""NS-P7c detached stage controller; immutable generation, no automatic retries."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from .llm_full import BASE, ROOT, read, checked, reference, write, load

MANDO="/home/zhao/miniconda3/envs/mando/bin/python"
NODESEM="/home/zhao/miniconda3/envs/nodesem/bin/python"
SOURCES=("llm_teacher.py","llm_post_v2.py","llm_post.py","llm_role_review.py",
    "teacher_vectors.py","offline/teacher_encode.py","offline/asset_registry.py","offline/encode.py",
    "teacher_diagnostics.py","p7c_diagnostics.py","p6c2_run.py","p6c2_core.py","p6c_core.py",
    "carrier.py","feature_spec.py","p7c_report.py","p7c_pipeline.py","doc_check.py")


def alive(pid):
    try:
        stat=Path("/proc")/str(pid)/"stat"
        return stat.read_text().split(") ",1)[1].split()[0]!="Z"
    except FileNotFoundError:
        return False


def prepare(base=BASE):
    base=Path(base);load(base)
    out=base/"pipeline";out.mkdir(exist_ok=False)
    commands=[
        ("post",[MANDO,"-B","-m","scripts.node_sem.llm_teacher","--out",str(base)]),
        ("encode",[NODESEM,"-s","-B",str(ROOT/"scripts/node_sem/offline/teacher_encode.py"),"--out",str(base)]),
        ("diagnostic_prepare",[MANDO,"-B","-m","scripts.node_sem.p7c_diagnostics","prepare","--out",str(base)]),
        ("diagnostic_run",[MANDO,"-B","-u","-m","scripts.node_sem.p7c_diagnostics","run","--out",str(base)]),
        ("report",[MANDO,"-B","-m","scripts.node_sem.p7c_report"]),
    ]
    plan=dict(version="nodesem-p7c-pipeline-v1",generation_plan=reference(base/"plan.json"),
        launch=reference(base/"launch.json"),contract=reference(base/"stage_contract.json"),
        sources={n:reference(ROOT/"scripts/node_sem"/n) for n in SOURCES},
        commands=[dict(name=name,argv=cmd) for name,cmd in commands],
        automatic_retry=False,HGT_training=False,student_training=False,
        scope="Complete authorized NS-P7c; stop after report, before NS-P8a")
    write(out/"plan.json",plan);write(out/"plan.seal.json",dict(plan=reference(out/"plan.json")))
    return plan


def run(base=BASE):
    base=Path(base);out=base/"pipeline"
    plan=read(checked(read(out/"plan.seal.json")["plan"]))
    def verify():
        for r in plan["sources"].values():checked(r)
        for k in ("generation_plan","launch","contract"):checked(plan[k])
        load(base)
    verify()
    write(out/"started.json",dict(pid=os.getpid(),plan=reference(out/"plan.json"),started=time.time()))
    stage="waiting_generation";started=time.monotonic()
    def heartbeat(child=None):
        target=out/"heartbeat.json";tmp=out/"heartbeat.tmp"
        tmp.write_text(json.dumps(dict(stage=stage,child_pid=child,
            elapsed_seconds=time.monotonic()-started,
            utc=datetime.datetime.now(datetime.timezone.utc).isoformat())),encoding="utf8")
        tmp.replace(target)
    try:
        pid=read(checked(plan["launch"]))["pid"]
        while True:
            if (base/"run1/failure.json").exists():raise RuntimeError("Generation failed; no automatic retry")
            if not alive(pid):
                if not (base/"run1/completed.seal.json").exists():
                    raise RuntimeError("Generation process exited without completed receipt")
                break
            heartbeat();time.sleep(15)
        checked(read(base/"run1/completed.seal.json")["completed"])
        records=[]
        for item in plan["commands"]:
            verify();stage=item["name"];heartbeat()
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONNOUSERSITE="1",
                TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64",
                OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",OPENBLAS_NUM_THREADS="2",
                HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1")
            # llama.cpp's private CUDA libraries never contaminate PyTorch/BGE.
            env.pop("LD_LIBRARY_PATH",None)
            if stage=="encode":env.pop("CUDA_VISIBLE_DEVICES",None)
            else:env["CUDA_VISIBLE_DEVICES"]=""
            t=time.monotonic()
            with (out/(stage+".log")).open("x") as stream:
                child=subprocess.Popen(item["argv"],cwd=str(ROOT),env=env,
                    stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
                while child.poll() is None:
                    heartbeat(child.pid);time.sleep(15)
            record=dict(stage=stage,command=item["argv"],returncode=child.returncode,
                elapsed_seconds=time.monotonic()-t,log=reference(out/(stage+".log")))
            write(out/(stage+".receipt.json"),record);records.append(record)
            if child.returncode:raise RuntimeError("Stage failed: "+stage+"; no automatic retry")
        stage="complete";heartbeat()
        write(out/"completed.json",dict(passed=True,stages=records,
            plan=reference(out/"plan.json"),report=reference(ROOT/"scripts/node_sem/NS_P7C_REPORT.md")))
    except Exception:
        write(out/"failure.json",dict(stage=stage,error=traceback.format_exc(),automatic_retry=False))
        raise


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=("prepare","run"))
    parser.add_argument("--out",default=str(BASE));args=parser.parse_args()
    if args.command=="prepare":prepare(Path(args.out).resolve())
    else:run(Path(args.out).resolve())
