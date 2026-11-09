"""NS-P7c sealed per-fold CPU ridge and non-SolidiFI signal diagnostics."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import numpy as np
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked,read,ref,write
from scripts.DFG.experiments.common import digest
from .p6c2_run import load as load_old,task_data
from .p6c2_core import signal_population
from .p6c_core import logistic_probe,split_indices,C_GRID
from .teacher_diagnostics import ridge_probe,align_teacher,ALPHA_GRID
from .carrier import _load
from .feature_spec import FeatureSpec
from . import TEACHER
from .llm_full import BASE

OLD=Path(__file__).resolve().parents[2]/"scripts/node_sem/artifacts/ns_p6c2"
SOURCES=("teacher_diagnostics.py","p7c_diagnostics.py","p6c2_run.py","p6c2_core.py","p6c_core.py","carrier.py","feature_spec.py")


def prepare(base=BASE):
    base=Path(base);out=base/"diagnostics";out.mkdir(exist_ok=False)
    old=load_old(OLD)
    teacher_index=read(checked(read(base/"teacher/index.seal.json")["index"]))
    tasks={}
    for task,d in old["tasks"].items():
        manifest_ref=teacher_index["tasks"][task]
        manifest,values=_load(manifest_ref)
        if manifest["task_id"]!=task or manifest["modality"]!=TEACHER:raise ValueError("Teacher task/modality differs")
        spec=FeatureSpec("TEACHER_load_check","original",
            [dict(name=TEACHER,dim=384,manifest=manifest_ref,normalize=True)],"none","concat")
        if spec.carrier_dim()!=385:raise ValueError("Teacher registry/layout differs")
        meta,parts,presence,kinds,control,pop=task_data(old,task)
        teacher,available=align_teacher(meta["rows"],manifest,values)
        if teacher.shape!=(len(meta["rows"]),384):raise ValueError("Teacher dimension differs")
        td=out/"prepared"/task;td.mkdir(parents=True)
        np.save(str(td/"teacher.npy"),teacher,allow_pickle=False)
        np.save(str(td/"present.npy"),available,allow_pickle=False)
        tasks[task]=dict(manifest=manifest_ref,values=ref(td/"teacher.npy"),present=ref(td/"present.npy"),
            rows=len(meta["rows"]),available=int(available.sum()),folds=[j["fold"] for j in meta["jobs"]],
            feature_layout=spec.layout())
    plan=dict(version="nodesem-teacher-diagnostics-v1",old_plan=ref(OLD/"plan.json"),
        teacher_index=ref(base/"teacher/index.json"),tasks=tasks,
        sources={n:ref(Path(__file__).parent/n) for n in SOURCES},
        methods=dict(ridge_alpha=list(ALPHA_GRID),logistic_C=list(C_GRID),seed=1,
            ridge_fit="inner_train",ridge_selection="inner_val mean cosine; smaller alpha on ties",
            ridge_population="Teacher, CTX and STATIC present",baseline="inner_train mean teacher per HCG node_type",
            unseen_baseline_type="not estimable; ridge/baseline paired comparison on supported subset",
            signal="Old non-SolidiFI statement/condition population; no filtering by teacher availability",
            signal_features="STATIC vs STATIC + normalized 384d TEACHER + presence bit; missing TEACHER zero",
            signal_selection="Unchanged logistic_probe: inner_val AUC selects C; inner_val selects BF1 threshold",
            workers=4,no_HGT=True,no_student=True))
    write(out/"plan.json",plan);write(out/"plan.seal.json",dict(plan=ref(out/"plan.json")))
    return plan


def load(base=BASE):
    out=Path(base)/"diagnostics"
    plan=read(checked(read(out/"plan.seal.json")["plan"]))
    for r in plan["sources"].values():checked(r)
    checked(plan["old_plan"]);checked(plan["teacher_index"])
    return plan


def fit_fold(base,task,fold):
    base=Path(base);plan=load(base);old=load_old(OLD)
    td=plan["tasks"][task]
    out=base/"diagnostics/folds"/(task+"__"+str(fold));out.mkdir(parents=True,exist_ok=False)
    write(out/"started.json",dict(pid=os.getpid(),plan=ref(base/"diagnostics/plan.json"),time=time.time()))
    try:
        meta,parts,presence,kinds,control,pop=task_data(old,task)
        teacher=np.load(str(checked(td["values"])),allow_pickle=False,mmap_mode="r")
        available=np.load(str(checked(td["present"])),allow_pickle=False)
        jobs=[j for j in meta["jobs"] if j["fold"]==fold]
        if len(jobs)!=1:raise ValueError("Wrong fold")
        job=jobs[0];rows=meta["rows"]
        mask=available & presence["ctx"] & presence["static"]
        ix=split_indices([r["file"] for r in rows],job["split"],mask)
        x=np.concatenate((parts["ctx"],parts["static"]),axis=1)
        ridge=ridge_probe(x,teacher,[r["node_type"] for r in rows],ix)
        proofs={r:dict(n=len(idx),row_sha256=digest([rows[int(i)]["row_key"] for i in idx])) for r,idx in ix.items()}
        signal=[]
        if task.endswith("_node"):
            labels=read(checked(pop["signal"]["labels"]))[task]
            y,base_mask,selected,_=signal_population(rows,kinds,presence,labels)
            sx=split_indices([r["file"] for r in rows],job["split"],selected)
            augmented=np.concatenate((parts["static"],teacher,available[:,None].astype(np.float32)),axis=1)
            lt={(r["file"],r["original_graph_node_id"]):r for r in labels}
            for name,matrix in (("static",parts["static"]),("static_teacher",augmented)):
                value=logistic_probe(matrix,y,sx,select_threshold=True)
                predictions=[]
                for i,p,c in zip(sx["outer_test"],value.pop("probabilities",[]),value.pop("predictions",[])):
                    r=rows[int(i)];label=lt[(r["file"],r["original_graph_node_id"])]
                    predictions.append(dict(file=r["file"],node_id=r["original_graph_node_id"],
                        source_sha256=label["source_sha256"],target=int(y[i]),probability=p,prediction=c,
                        teacher_present=bool(available[i])))
                signal.append(dict(source=name,predictions=predictions,**value))
            proofs["signal"]={r:dict(n=len(idx),positive=int(y[idx].sum()),
                teacher_present=int(available[idx].sum()),row_sha256=digest([rows[int(i)]["row_key"] for i in idx])) for r,idx in sx.items()}
        result=dict(task_id=task,fold=fold,plan=ref(base/"diagnostics/plan.json"),
            split_sha256=digest(job["split"]),ridge=ridge,signal=signal,splits=proofs)
        write(out/"result.json",result);write(out/"receipt.json",dict(passed=True,result=ref(out/"result.json")))
    except Exception:
        write(out/"failure.json",dict(error=traceback.format_exc(),automatic_retry=False));raise


def run(base=BASE):
    base=Path(base);plan=load(base);out=base/"diagnostics"
    write(out/"controller.started.json",dict(pid=os.getpid(),time=time.time(),plan=ref(out/"plan.json")))
    queue=[(t,f) for t,d in plan["tasks"].items() for f in d["folds"]];active=[];done=[]
    logs=out/"logs";logs.mkdir()
    while queue or active:
        while queue and len(active)<plan["methods"]["workers"]:
            t,f=queue.pop(0)
            stream=(logs/(t+"__"+str(f)+".log")).open("x")
            proc=subprocess.Popen([sys.executable,"-B","-u","-m","scripts.node_sem.p7c_diagnostics",
                "fold","--out",str(base),"--task",t,"--fold",str(f)],stdout=stream,stderr=subprocess.STDOUT,
                env=dict(os.environ,CUDA_VISIBLE_DEVICES="",OMP_NUM_THREADS="1",MKL_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1"))
            active.append((proc,stream,t,f))
        for proc,stream,t,f in list(active):
            if proc.poll() is None:continue
            stream.close();active.remove((proc,stream,t,f))
            if proc.returncode:
                write(out/"failure.json",dict(task=t,fold=f,exit_code=proc.returncode))
                for other,_,_,_ in active:other.terminate()
                raise RuntimeError("Diagnostic failure; no automatic retry")
            receipt=read(out/"folds"/(t+"__"+str(f))/"receipt.json");checked(receipt["result"])
            done.append((t,f));print("complete",len(done),t,f,flush=True)
        (out/"progress.json").write_text(json.dumps(dict(completed=done,active=[(t,f) for _,_,t,f in active],queued=len(queue))),encoding="utf8")
        time.sleep(2)
    write(out/"completed.json",dict(passed=True,folds=len(done),plan=ref(out/"plan.json")))


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("command",choices=("prepare","run","fold"))
    ap.add_argument("--out",default=str(BASE));ap.add_argument("--task");ap.add_argument("--fold",type=int)
    a=ap.parse_args()
    if a.command=="prepare":prepare(a.out)
    elif a.command=="run":run(a.out)
    else:fit_fold(a.out,a.task,a.fold)
