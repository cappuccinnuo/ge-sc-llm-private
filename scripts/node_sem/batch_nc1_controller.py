"""N-C1 orchestration adapted from scripts/node_sem/batch_nb_controller.py
Source SHA256: 92935a73cf3e1c34b23cab532b68900cbcfc6ce80c5dd3acab8035ec64d1be43
Training and checkpoint algorithms imported unchanged; only batch admission differs.
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
from . import batch_nc1 as batch_na
from . import batch_nc1_worker as worker

MODULES=("batch_nc1.py","nc1_history.py","nc1_init.py","p8a_prepare.py","batch_nc1_worker.py","batch_nc1_controller.py")
OUT=batch_na.DEFAULT
ROOT=batch_na.ROOT


from .batch_na_controller import atomic, retry_external

def ordered(jobs):
    return batch_na.execution_order(jobs)


def seal(root=OUT):
    root=Path(root)
    plan=batch_na.load(root/"plan.json",mode="launch",deep=False)
    decisions=ref(root/"execution_decisions.json")
    approved=read(checked(decisions))
    if (approved.get("execution_authorized") is not True or not approved.get("user_request")
            or approved.get("plan") != ref(root/"plan.json")
            or approved.get("jobs") != 30 or approved.get("view") != "original"):
        raise PermissionError("Explicit N-C1 execution approval is required")
    power=read(checked(approved["power_check"]))
    if not(power["ac_power"] and power["sleep_disabled"] and power["hibernate_disabled"]):
        raise ValueError("Fresh pretraining power check incomplete")
    gates=dict(preparation=ref(root/"verification.json"),regressions=ref(root/"regressions.json"))
    for reference in gates.values():
        gate=read(checked(reference))
        if gate.get("passed") is not True: raise ValueError("N-C1 gate failed")
    if read(checked(gates["preparation"]))["jobs"] != 30:
        raise ValueError("N-C1 preparation incomplete")
    revision=dict(version="nodesem-nc1-execution-v1",plan=ref(root/"plan.json"),
        seal=ref(root/"plan.seal.json"),runtime={str((ROOT/"scripts/node_sem"/n).relative_to(ROOT)):
            ref(ROOT/"scripts/node_sem"/n)["sha256"] for n in MODULES},
        original_runtime_unchanged=True,gates=gates,decisions=decisions,order=ordered(plan["jobs"]),
        gate_sources={},configuration_override=False,carrier_policy="sealed_matrix_v1",
        no_new_algorithm=True,training_core="batch_na_worker.construct/run_core/verify_attempt",
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    write(root/"execution_revision.json",revision)
    write(root/"authorization.json",dict(execution_authorized=True,user_request=approved["user_request"],
        plan=revision["plan"],seal=revision["seal"],execution_revision=ref(root/"execution_revision.json"),
        jobs=30,view="original",label_policy="L-audit",seeds=[1],location="local_RTX3050",
        external_interrupt_retry_once=approved.get("external_interrupt_retry_once") is True,
        server_batch="separate replication, never pool device families"))
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
        child_pid=child,completed=len(completed),total=30,completed_job_ids=completed,
        heartbeat_unix_seconds=time.time(),error=error))


def progress(root,completed,receipts):
    primary=[r for r in receipts if r["job"]["task_id"]=="reentrancy_node" and r["job"]["profile"]=="G3R"]
    estimate=None
    if len(primary)>=4:
        times=[r["total_seconds"] for r in primary[:4]]
        estimate=dict(sample_fits=4,mean_fit_wall_seconds=sum(times)/4,
            estimated_30_fit_hours=30*sum(times)/4/3600,
            remaining_hours=(30-len(completed))*sum(times)/4/3600,
            caveat="First four node fits only; contract workloads, epochs and memory pressure may differ")
    atomic(Path(root)/"progress.json",dict(completed=len(completed),total=30,estimate=estimate,
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
    result=dict(passed=True,formal_fits=30,plan=ref(root/"plan.json"),
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
                    child=subprocess.Popen([sys.executable,"-m","scripts.node_sem.batch_nc1_worker",
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
        verify(root);status(root,"complete_training_pending_report",completed)
        progress(root,completed,receipts)
        # N-C1 report/diagnostic entry is bound separately after the plan-only stage.
        # Never claim report completion just because the 30 fits passed.
        status(root,"complete_training_pending_NC1_report",completed)


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
