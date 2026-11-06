"""Resume the original N-B order after one user-authorized manual retry."""
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
sys.path.insert(0,"/home/zhao/SmartContract/ge-sc-llm-ddg-v11")
from scripts.node_sem import batch_nb_controller as control
from scripts.node_sem import batch_nb_worker as worker
from scripts.DFG.dfg_v2.experiment.run import _Lock
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,write,ref
from recovery_common import BATCH,HERE,JOB,load_authorization,checked

def run():
    auth=load_authorization()
    plan=worker.load_plan(BATCH)
    revision,original_auth=worker.validate_execution(BATCH,plan)
    byid={worker.job_id(j):j for j in plan["jobs"]}
    completed=[]
    receipts=[]
    with _Lock(BATCH/".controller.lock"):
        try:
            control.status(BATCH,"verifying_existing",auth["accepted_job_ids"])
            # Verify the original successful prefix; never train these jobs again.
            for key in revision["order"][:115]:
                if key not in auth["accepted_job_ids"]:
                    raise ValueError("Accepted prefix differs")
                done=control.successful(BATCH,plan,byid[key],deep=True)
                if done is None:
                    raise ValueError("An accepted fit is missing")
                completed.append(key);receipts.append(done[1])
                if len(completed)%10==0:
                    print("Verified completed fits {}/115".format(len(completed)),flush=True)
                    control.status(BATCH,"verifying_existing",auth["accepted_job_ids"])
            if completed!=auth["accepted_job_ids"] or revision["order"][115:]!=auth["remaining_job_ids"]:
                raise ValueError("Original execution order changed")
            write(HERE/"accepted_prefix_verified.json",dict(passed=True,count=115,
                receipts=[ref(BATCH/"runs"/k/"attempt_001/receipt.json") for k in completed],
                authorization=ref(HERE/"authorization.json")))
            for key in auth["remaining_job_ids"]:
                job=byid[key]
                existing=control.successful(BATCH,plan,job,deep=True)
                if existing is not None:
                    raise FileExistsError("A remaining job already completed; do not launch duplicate")
                directory=BATCH/"runs"/key
                directory.mkdir(exist_ok=True)
                previous=sorted(directory.glob("attempt_*"))
                if key==JOB:
                    if len(previous)!=1 or previous[0].name!="attempt_001":
                        raise ValueError("Retry attempt layout differs")
                    log=directory/"worker_attempt_002.log"
                    command=[sys.executable,"-B","-u",str(HERE/"retry_worker.py"),
                        "--root",str(BATCH),"--only",key]
                else:
                    if previous:
                        raise ValueError("New remaining task already has an attempt")
                    log=directory/"worker_attempt_001.log"
                    command=[sys.executable,"-B","-u","-m","scripts.node_sem.batch_nb_worker",
                        "--root",str(BATCH),"--only",key]
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",
                    HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",TOKENIZERS_PARALLELISM="false",
                    NODESEM_STARTED_UNIX=str(time.time()))
                with log.open("xb") as stream:
                    child=subprocess.Popen(command,cwd=str(worker.ROOT),env=env,
                        stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                    while child.poll() is None:
                        control.status(BATCH,"running",completed,key,child.pid)
                        time.sleep(5)
                    code=child.returncode
                if code!=0:
                    raise RuntimeError("Resumed worker failed; no automatic retry: {} returncode={}".format(key,code))
                done=control.successful(BATCH,plan,job,deep=True)
                if done is None:
                    raise RuntimeError("Worker exited without an accepted receipt")
                completed.append(key);receipts.append(done[1])
                control.progress(BATCH,completed,receipts)
                control.status(BATCH,"accepted",completed,key)
                print("Accepted {}/120 {}".format(len(completed),key),flush=True)
            control.verify(BATCH)
            for reference in auth["failed_attempt_files"]:
                checked(reference)
            write(HERE/"complete.json",dict(passed=True,formal_fits=120,
                preserved_original_successes=115,new_successful_fits=5,
                manual_retry_job=JOB,manual_retry_attempt="attempt_002",
                failed_attempt_preserved=True,original_runtime_unchanged=True,
                authorization=ref(HERE/"authorization.json")))
            control.status(BATCH,"complete_training_pending_NB_report",completed)
            print("120/120 training fits verified; N-B diagnostics/report remain pending.",flush=True)
        except BaseException as error:
            previous=read(BATCH/"controller_status.json")
            control.status(BATCH,"stopped",completed or auth["accepted_job_ids"],
                previous.get("current_job"),error=dict(error=repr(error),traceback=traceback.format_exc()))
            write(HERE/"failure.json",dict(error=repr(error),traceback=traceback.format_exc(),
                completed=len(completed),automatic_retry=False))
            raise

if __name__=="__main__":
    run()
