"""Detached serial N-A controller and immutable execution binding.
Only successful SHA-bound attempts are reused. No training results are ranked
or summarized while this controller runs. External SIGTERM/SIGHUP retries are
bounded to one; SIGKILL without provenance is deliberately not called external.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, checked, ref
from scripts.DFG.dfg_v2.experiment.run import _Lock
from . import batch_na
from . import batch_na_worker as worker

MODULES=("na_carrier.py","batch_na_worker.py","batch_na_controller.py","reporting.py","na_attention.py")
OUT=batch_na.DEFAULT
ROOT=batch_na.ROOT


def atomic(path,value):
    path=Path(path)
    temporary=path.with_name(path.name+".tmp."+str(os.getpid()))
    with temporary.open("x",encoding="utf8") as f:
        json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2);f.write("\n")
        f.flush();os.fsync(f.fileno())
    os.replace(str(temporary),str(path))


def ordered(jobs):
    def select(task,profile,name,fold):
        return next(j for j in jobs if (j["task_id"],j["profile"],j["name"],j["fold"])==(task,profile,name,fold))
    pilots=[select("reentrancy_node","G3R","S4",0),select("reentrancy_contract","G3R","S4",0)]
    primary=[select("reentrancy_node","G3R",name,f) for f in range(10) for name in ("S0o","S4","S2","S1o")]
    result=[];seen=set()
    for j in pilots+primary+jobs:
        k=worker.job_id(j)
        if k not in seen:result.append(k);seen.add(k)
    if len(result)!=240 or len(seen)!=240:raise ValueError("Execution order lost jobs")
    return result


def seal(root=OUT):
    root=Path(root)
    plan=batch_na.load(root/"plan.json",mode="launch",deep=False)
    gates=dict(carriers=ref(root/"acceptance/carriers/carrier_proof.json"),
        cpu=ref(root/"acceptance/cpu/cpu_proof.json"),
        regressions=ref(root/"acceptance/regressions_final.json"))
    for r in gates.values():
        if not read(checked(r)).get("passed"):raise ValueError("Missing required gate")
    carrier=read(checked(gates["carriers"]));cpu=read(checked(gates["cpu"]))
    if (carrier["count"]!=32 or len(carrier["checks"])!=32
            or cpu["cpu_acceptance_fits"]!=6 or [r["epochs"] for r in cpu["checks"]]!=[1,2,2]
            or carrier["plan"]!=ref(root/"plan.json") or cpu["plan"]!=ref(root/"plan.json")):
        raise ValueError("Acceptance gate identity/count differs")
    decisions=ref(root/"decisions_P5A.json")
    approved=read(checked(decisions))
    if not approved.get("two_pilots_first") or not approved.get("user_request"):
        raise PermissionError("Execution decisions absent")
    power=read(checked(approved["power_check"]))
    if not(power["ac_power"] and power["sleep_disabled"] and power["hibernate_disabled"]):
        raise ValueError("Startup power check incomplete")
    revision=dict(version="nodesem-na-execution-v1",plan=ref(root/"plan.json"),
        seal=ref(root/"plan.seal.json"),runtime={str((ROOT/"scripts/node_sem"/n).relative_to(ROOT)):
            ref(ROOT/"scripts/node_sem"/n)["sha256"] for n in MODULES},
        original_runtime_unchanged=True,original_runtime_count=len(plan["runtime"]),
        gates=gates,decisions=decisions,order=ordered(plan["jobs"]),
        gate_sources={str(p.relative_to(ROOT)):ref(p)["sha256"] for p in
                      [ROOT/"scripts/node_sem/p5a_acceptance.py"]},
        configuration_override=False,carrier_policy="sealed_matrix_v1",
        analysis_refs={n:ref(Path(plan["source_h8_plan"]["path"]).parent/"reports"/n)
                       for n in ("report.json","fold_metrics.json")},
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    write(root/"execution_revision.json",revision)
    write(root/"authorization.json",dict(execution_authorized=True,
        user_request=approved["user_request"],decision_replies=approved["decision_replies"],
        plan=revision["plan"],seal=revision["seal"],execution_revision=ref(root/"execution_revision.json"),
        jobs=240,view="original",label_policy="L-audit",seeds=[1],location="local_RTX3050",
        external_interrupt_retry_once=approved["external_interrupt_retry_once"],
        historical_8h_scores_reused=False,server_batch="separately preregistered replication, never pooled or selected by outcome"))
    return revision


def successful(root,plan,job,deep=True):
    directory=Path(root)/"runs"/worker.job_id(job)
    attempts=sorted(directory.glob("attempt_*"))
    good=[p for p in attempts if (p/"complete.json").exists() and not (p/"failure.json").exists()]
    if len(good)>1:raise ValueError("Duplicate successful fits")
    if good:
        receipt=worker.verify_attempt(root,plan,job,good[0],deep=deep)
        return good[0],receipt
    return None


def retry_external(root,job,returncode,auth):
    directory=Path(root)/"runs"/worker.job_id(job)
    attempts=sorted(directory.glob("attempt_*"))
    if not attempts:return False
    a=attempts[-1];log=a.parent/("worker_"+a.name+".log")
    text=log.read_text(encoding="utf8",errors="replace") if log.exists() else ""
    confirmed=(returncode in (-signal.SIGTERM,-signal.SIGHUP)
        and not (a/"failure.json").exists()
        and not any(s in text.lower() for s in ("traceback","out of memory","cuda error","nonfinite")))
    allowed=confirmed and len(attempts)==1 and auth.get("external_interrupt_retry_once") is True
    if not (a/"external_interruption.json").exists():
        write(a/"external_interruption.json",dict(confirmed_external=confirmed,
            observed_returncode=returncode,retry_authorized=allowed,
            evidence="Observed SIGTERM/SIGHUP without Python/CUDA error" if confirmed else "Cause unconfirmed; manual review required",
            unix_seconds=time.time(),same_zero_step_initial=job["initial"]))
    return allowed


def status(root,state,completed,current=None,child=None,error=None):
    atomic(Path(root)/"controller_status.json",dict(pid=os.getpid(),state=state,current_job=current,
        child_pid=child,completed=len(completed),total=240,completed_job_ids=completed,
        heartbeat_unix_seconds=time.time(),error=error))


def progress(root,completed,receipts):
    primary=[r for r in receipts if r["job"]["task_id"]=="reentrancy_node" and r["job"]["profile"]=="G3R"]
    estimate=None
    if len(primary)>=4:
        times=[r["total_seconds"] for r in primary[:4]]
        estimate=dict(sample_fits=4,mean_fit_wall_seconds=sum(times)/4,
            estimated_240_fit_hours=240*sum(times)/4/3600,
            remaining_hours=(240-len(completed))*sum(times)/4/3600,
            caveat="First four node fits only; contract workloads, epochs and memory pressure may differ")
    atomic(Path(root)/"progress.json",dict(completed=len(completed),total=240,estimate=estimate,
        updated=time.time(),metrics_summarized=False))


def verify(root=OUT):
    root=Path(root);plan=worker.load_plan(root);worker.validate_execution(root,plan)
    receipts=[];records=[]
    for job in plan["jobs"]:
        done=successful(root,plan,job,deep=True)
        if done is None:raise ValueError("Missing success: "+worker.job_id(job))
        path,r=done;receipts.append(ref(path/"receipt.json"))
        records.append(dict(job,actual_device=r["actual_device"]))
    batch_na.validate_device_comparisons(plan["jobs"],records)
    result=dict(passed=True,formal_fits=240,plan=ref(root/"plan.json"),
        execution_revision=ref(root/"execution_revision.json"),receipts=receipts,
        device_and_tf32_consistent=True)
    target=root/"complete.json"
    if target.exists():
        if read(target)!=result:raise ValueError("Existing final verification differs")
    else:write(target,result)
    return result


def run(root=OUT):
    root=Path(root);plan=worker.load_plan(root);revision,auth=worker.validate_execution(root,plan)
    by_id={worker.job_id(j):j for j in plan["jobs"]}
    completed=[];receipts=[]
    # The controller lock serializes restarts, worker's global GPU lock serializes all experiments.
    with _Lock(root/".controller.lock"):
        status(root,"verifying_existing",completed)
        for key in revision["order"]:
            job=by_id[key]
            done=successful(root,plan,job,deep=True)
            if done:
                completed.append(key);receipts.append(done[1]);continue
            directory=root/"runs"/key;directory.mkdir(parents=True,exist_ok=True)
            attempts=sorted(directory.glob("attempt_*"))
            if attempts:
                permit=attempts[-1]/"external_interruption.json"
                if (not permit.exists() or not read(permit).get("retry_authorized") or len(attempts)!=1):
                    raise RuntimeError("Incomplete/failed attempt requires explicit review: "+key)
            while True:
                idx=len(list(directory.glob("attempt_*")))+1
                log=directory/("worker_attempt_{:03d}.log".format(idx))
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",
                    HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",TOKENIZERS_PARALLELISM="false",
                    NODESEM_STARTED_UNIX=str(time.time()))
                with log.open("xb") as stream:
                    child=subprocess.Popen([sys.executable,"-m","scripts.node_sem.batch_na_worker",
                        "--root",str(root),"--only",key],cwd=str(ROOT),env=env,
                        stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                    while child.poll() is None:
                        status(root,"running",completed,key,child.pid)
                        time.sleep(5)
                    code=child.returncode
                if code==0:
                    done=successful(root,plan,job,deep=True)
                    if done is None:raise RuntimeError("Worker exited without accepted success")
                    completed.append(key);receipts.append(done[1]);progress(root,completed,receipts)
                    status(root,"accepted",completed,key)
                    break
                if not retry_external(root,job,code,auth):
                    raise RuntimeError("Worker failed; batch stopped: {} returncode={}".format(key,code))
            # Two formal pilot successes are gates, not additional fits.
            if len(completed)==2:
                write(root/"pilot_acceptance.json",dict(passed=True,jobs=completed[:],
                    receipts=[ref(successful(root,plan,by_id[k],deep=False)[0]/"receipt.json") for k in completed],
                    formal_fit_count=2,retraining=False))
        verify(root);status(root,"complete_training_pending_report",completed)
        progress(root,completed,receipts)
        # Post-training eval diagnostics are separate from the 240 formal fits.
        for job in plan["jobs"]:
            if job["profile"]!="G3R":continue
            key=worker.job_id(job);directory=root/"attention"/key
            if directory.exists():
                receipt=read(directory/"receipt.json")
                checked(receipt["report"])
                if not read(checked(receipt["report"]))["passed"]:raise ValueError("Incomplete attention evaluation")
                continue
            log=root/("attention_"+key+".log")
            with log.open("xb") as stream:
                child=subprocess.Popen([sys.executable,"-m","scripts.node_sem.na_attention","--root",str(root),"--only",key],
                    cwd=str(ROOT),env=dict(os.environ,HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1"),
                    stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                while child.poll() is None:
                    status(root,"attention_eval",completed,key,child.pid);time.sleep(5)
                if child.returncode:raise RuntimeError("Attention evaluation stopped: "+key)
        from .na_attention import verify as verify_attention
        if not (root/"attention/complete.json").exists():verify_attention(root)
        status(root,"final_reporting",completed)
        from .reporting import build
        if (root/"reports/receipt.json").exists():
            final=read(root/"reports/receipt.json")
            if final["plan"]!=ref(root/"plan.json"):raise ValueError("Report plan differs")
            for item in final["artifacts"]:checked(item)
            if not read(root/"reports/report.json")["passed"]:raise ValueError("Final report not accepted")
        else:
            build(root)
        status(root,"complete",completed)


def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=("seal","run","verify"))
    p.add_argument("--root",default=str(OUT));a=p.parse_args()
    try:globals()[a.command](Path(a.root))
    except BaseException as error:
        existing=read(Path(a.root)/"controller_status.json") if (Path(a.root)/"controller_status.json").exists() else {}
        if not existing or existing.get("pid")==os.getpid():
            status(a.root,"stopped",existing.get("completed_job_ids",[]),existing.get("current_job"),
                error=dict(error=repr(error),traceback=traceback.format_exc()))
        else:
            # A second launcher must not overwrite the running controller's heartbeat.
            write(Path(a.root)/("controller_launch_failure_"+str(os.getpid())+".json"),
                dict(error=repr(error),traceback=traceback.format_exc()))
        raise


if __name__=="__main__":main()
