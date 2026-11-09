"""NS-P8b CPU preparation entry: exclusively creates N-C2, never launches HGT."""
import argparse
import datetime
from pathlib import Path
import time
import traceback
import torch
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,write,ref,checked
from scripts.DFG.experiments.common import digest
from . import batch_nc1
from .nc1_history import verify_index
from .student_artifacts import inputs,build
from .student import POLICY,split_indices

BASE=Path(__file__).resolve().parent
DEFAULT=BASE/"artifacts/batch_NC2_v1"

def prepare(out=DEFAULT):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    write(out/"started.json",dict(stage="CPU student preparation",unix_seconds=time.time(),HGT_fits=0))
    try:
        parent=batch_nc1.load(batch_nc1.DEFAULT/"plan.json")
        done=read(batch_nc1.DEFAULT/"completion_status.json")
        report=read(checked(done["report"]));checked(done["report_receipt"])
        if done["state"]!="complete" or not report["continuation"]["continue_student"]:
            raise ValueError("N-C1 did not pass continuation")
        parents=verify_index(parent["na_result_index"])
        teacher=read(checked(parent["teacher_index"]))["tasks"]
        tasks={};jobs=[]
        for task,n in batch_nc1.TASK_FOLDS:
            old=[r["job"] for r in parents.values() if r["job"]["task_id"]==task]
            old.sort(key=lambda j:j["fold"])
            if [j["fold"] for j in old]!=list(range(n)):raise ValueError("Missing S4 folds")
            data=inputs(read(checked(old[0]["spec"])),teacher[task]);tasks[task]=data
            for j in old:
                ridge=BASE/"artifacts/llm_v3/diagnostics/folds"/(task+"__"+str(j["fold"]))/"result.json"
                rr=ref(ridge);r=read(checked(rr))
                if r["split_sha256"]!=digest(j["split"]):raise ValueError("Ridge split mismatch")
                ix=split_indices([v["file"] for v in data[0]["rows"]],j["split"],data[4])
                for role,ids in ix.items():
                    if r["splits"][role]["row_sha256"]!=digest([data[0]["rows"][int(i)]["row_key"] for i in ids]):
                        raise ValueError("Ridge population mismatch")
                jobs.append(dict(task_id=task,fold=j["fold"],fit_seed=j["seeds"]["fit"],
                    split=j["split"],ridge=rr,baseline_job_id=__import__("scripts.node_sem.batch_na_worker",fromlist=["job_id"]).job_id(j)))
        decisions=dict(three_file_two_fold_test=True,S5_S8_all_initial_tensors_equal=True,
            S5_S8_fit_and_modality_dropout_seeds_equal=True,
            user_approval="2026-11-09 asynchronous replies: three-file strict split and S5/S8 permutation-only contrast",
            final_server="Separate sufficiently provisioned server batch; current RTX3050 constraint is local only")
        write(out/"decisions.json",decisions)
        sources={n:ref(BASE/n) for n in ("student.py","student_artifacts.py","p8b_students.py")}
        plan=dict(version="nodesem-nc2-students-v1",jobs=jobs,policy=POLICY,
            sources=sources,parent_plan=ref(batch_nc1.DEFAULT/"plan.json"),
            parent_complete=ref(batch_nc1.DEFAULT/"completion_status.json"),
            parent_report=done["report"],na_result_index=parent["na_result_index"],
            teacher_index=parent["teacher_index"],decisions=ref(out/"decisions.json"),
            HGT_execution_authorized=False,CPU_student_fits_authorized_by_NS_P8b=True,
            role_head=False,view="original")
        write(out/"student_plan.json",plan);write(out/"student_plan.seal.json",dict(plan=ref(out/"student_plan.json")))
        records=[]
        for j in jobs:
            for r in sources.values():checked(r)
            d=out/"students"/j["task_id"]/("fold_%d"%j["fold"])
            value=build(d,j["task_id"],j["fold"],j["fit_seed"],j["split"],tasks[j["task_id"]],j["ridge"])
            records.append(ref(d/"complete.json"))
            print("student %d/30 %s fold%d"%(len(records),j["task_id"],j["fold"]),flush=True)
            (out/"student_progress.json").write_text(__import__("json").dumps(dict(completed=len(records),total=30)),encoding="utf8")
        if torch.cuda.is_initialized():raise ValueError("CPU preparation initialized CUDA")
        write(out/"students_complete.json",dict(passed=True,students=30,records=records,
            plan=ref(out/"student_plan.json"),HGT_fits=0,cuda_initialized=False))
    except BaseException:
        write(out/"students_failure.json",dict(traceback=traceback.format_exc(),automatic_retry=False))
        raise

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",default=str(DEFAULT));a=p.parse_args()
    torch.set_num_threads(2);prepare(a.out)
