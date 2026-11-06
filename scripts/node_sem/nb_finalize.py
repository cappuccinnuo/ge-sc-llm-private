"""N-B post-training audit and serial read-only analysis. Never trains models."""
import argparse
import ast
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, checked, ref
from scripts.DFG.dfg_v2.experiment.run import _Lock
from . import batch_nb as nb, batch_nb_worker as worker
from .batch_na_controller import atomic
from . import nb_diagnostics as diagnostic

OUT=worker.OUT


def verify_historical_exports(receipt):
    """Historical metric reuse only; never pretend absent weights are verified."""
    missing=[];present=0
    artifacts=receipt["artifacts"]
    weights=[a for a in artifacts if Path(a["path"]).name in ("best.pt","last.pt")]
    if len(weights)!=2 or {Path(a["path"]).name for a in weights}!={"best.pt","last.pt"}:
        raise ValueError("Historical checkpoint references incomplete")
    for item in artifacts:
        path=Path(item["path"])
        if path.name in ("best.pt","last.pt") and not path.exists():
            missing.append(item)
        else:
            checked(item)
            present+=int(path.name in ("best.pt","last.pt"))
    return dict(missing_checkpoints=missing,present_checkpoints=present)


def audit(root=OUT):
    root=Path(root);plan=nb.load(root/"plan.json",deep=False)
    worker.validate_execution(root,plan)
    from .reporting import manifest_attempts as na_entries
    entries=diagnostic.accepted_entries(root,plan)
    for job in plan["jobs"]:
        worker.verify_attempt(root,plan,job,entries[worker.job_id(job)][0],deep=True)
    old=read(checked(plan["na_parent"]["plan"]));na_root=Path(plan["na_parent"]["plan"]["path"]).parent
    old_entries=na_entries(na_root,old)
    for reference in plan["na_parent"].values():checked(reference)
    missing_weights=[];existing_weights=0
    for job in old["jobs"]:
        directory,receipt=old_entries[worker.job_id(job)]
        if (receipt["job"]!=job or receipt["plan"]!=plan["na_parent"]["plan"]
                or receipt["execution_revision"]!=plan["na_parent"]["revision"]):
            raise ValueError("N-A historical receipt identity differs")
        current=verify_historical_exports(receipt)
        missing_weights.extend(current["missing_checkpoints"])
        existing_weights+=current["present_checkpoints"]
    write(root/"historical_weight_availability.json",dict(
        scope="N-A receipt-bound historical exports; not current checkpoint reload",
        missing_count=len(missing_weights),missing=missing_weights,
        present_checkpoints=existing_weights,deletion_cause="not established",
        earlier_audit_failure=ref(root/"analysis_checks/audit.json"),
        policy="NS-P6 requires read-only receipt SHA references; no old verifier changed"))
    recovery=root/"manual_resume_20261105_v1"
    auth=read(recovery/"authorization.json");done=read(recovery/"complete.json")
    if (auth.get("manual_resume_authorized") is not True or not auth.get("user_request")
            or auth["plan"]!=ref(root/"plan.json") or auth["maximum_manual_retries"]!=1
            or done.get("passed") is not True or done["authorization"]!=ref(recovery/"authorization.json")
            or done["formal_fits"]!=120 or done["preserved_original_successes"]!=115):
        raise ValueError("Manual recovery binding differs")
    for reference in auth["failed_attempt_files"]:checked(reference)
    # The recovery uses the original compute body; only retry admission differs.
    trees=[]
    for path,fn in ((worker.ROOT/"scripts/node_sem/batch_nb_worker.py","run_formal"),
                    (recovery/"retry_worker.py","run_retry")):
        node=next(x for x in ast.parse(path.read_text()).body if isinstance(x,ast.FunctionDef) and x.name==fn)
        index=next(i for i,x in enumerate(node.body) if isinstance(x,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=="attempt" for t in x.targets))
        trees.append([ast.dump(x,include_attributes=False) for x in node.body[index:]])
    if trees[0]!=trees[1]:raise ValueError("Recovery compute body changed")
    failures=sorted((root/"runs").glob("*/attempt_*/failure.json"))
    if len(failures)!=1 or failures[0].parent.name!="attempt_001":
        raise ValueError("Unexpected failure/retry history")
    failed=read(failures[0])
    if failed["cuda_oom"] or "Current whole-card memory measurement failed" not in failed["error"]:
        raise ValueError("Unexpected failure classification")
    key=auth["failed_job_id"];attempt,receipt=entries[key]
    if attempt.name!="attempt_002" or receipt["job"]["initial"]!=auth["failed_job"]["initial"]:
        raise ValueError("Retried fit initial differs")
    kept=read(recovery/"accepted_prefix_verified.json")
    if kept.get("passed") is not True or kept["count"]!=115:raise ValueError("Accepted prefix missing")
    for reference in kept["receipts"]:
        checked(reference)
        if reference not in read(root/"complete.json")["receipts"]:raise ValueError("Historical success replaced")
    value=dict(passed=True,plan=ref(root/"plan.json"),formal_NB=120,formal_NA=240,
        checkpoint_files_checked=240+existing_weights,
        NB_all_artifacts_sha_checked=True,NA_noncheckpoint_artifacts_sha_checked=True,
        NA_checkpoint_reload_available=not missing_weights,
        NA_missing_checkpoints=len(missing_weights),
        NA_availability=ref(root/"historical_weight_availability.json"),
        failures=1,manual_retries=1,failed_epoch_rows=len((failures[0].parent/"fit/history.jsonl").read_text().splitlines()),
        recovery_compute_body_exact=True,recovery_authorization=ref(recovery/"authorization.json"),
        recovery_complete=ref(recovery/"complete.json"),retained_prefix=115,
        formal_completion=ref(root/"complete.json"))
    write(root/"analysis_audit.json",value)
    return value


def seal(root=OUT):
    root=Path(root)
    for name in ("analysis_audit.json","analysis_checks/regressions.json","analysis_checks/attempt2/focused.json","analysis_checks/attempt2/nodesem.json"):
        if read(root/name).get("passed") is not True:raise ValueError("Analysis acceptance incomplete")
    sources=[worker.ROOT/"scripts/node_sem"/n for n in
        ("nb_diagnostics.py","nb_reporting.py","nb_finalize.py","tests/test_nb_analysis.py")]
    value=dict(version="nodesem-nb-analysis-v1",plan=ref(root/"plan.json"),
        execution_revision=ref(root/"execution_revision.json"),sources=[ref(p) for p in sources],
        gates=[ref(root/n) for n in ("analysis_audit.json","analysis_checks/regressions.json","analysis_checks/attempt2/focused.json","analysis_checks/attempt2/nodesem.json")],
        user_request="Complete the N-B report",training_changed=False,formal_fits_added=0,
        diagnostic_evals=90,gate_evals=30,noG_not_applicable=30,
        scoring="original/L-audit grouped outer evaluation; best primary; descriptive only",
        created_unix=time.time())
    write(root/"analysis_revision.json",value)
    return value


def launch_command(module,root,key=None):
    cmd=[sys.executable,"-B","-u","-m",module,"--root",str(root)]
    if key is not None:cmd.extend(["--only",key])
    return cmd


def run(root=OUT):
    root=Path(root);diagnostic.check_analysis(root)
    plan=worker.load_plan(root);worker.validate_execution(root,plan)
    diagnostic.accepted_entries(root,plan)
    jobs=[j for j in plan["jobs"] if j["profile"]=="G3R"]
    with _Lock(root/".analysis.lock"):
        for number,job in enumerate(jobs,1):
            key=worker.job_id(job);out=root/"diagnostics"/key
            if out.exists():
                diagnostic.verify_one(root,job)
                continue
            logs=root/"analysis_logs";logs.mkdir(exist_ok=True)
            cmd=launch_command("scripts.node_sem.nb_diagnostics",root,key)
            with (logs/(key+".log")).open("xb") as log:
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2")
                env.pop("CUDA_VISIBLE_DEVICES",None)
                child=subprocess.Popen(cmd,cwd=str(worker.ROOT),env=env,stdout=log,stderr=subprocess.STDOUT)
                while child.poll() is None:
                    atomic(root/"completion_status.json",dict(state="diagnostics",completed=number-1,total=90,
                        job=key,child_pid=child.pid,updated=time.time()))
                    time.sleep(5)
                if child.returncode:raise RuntimeError("Diagnostic stopped: "+key)
            diagnostic.verify_one(root,job)
            print("DIAGNOSTIC {}/90 {}".format(number,key),flush=True)
        diagnostic.verify(root)
        atomic(root/"completion_status.json",dict(state="reporting",completed=90,total=90,updated=time.time()))
        from .nb_reporting import build
        build(root)
        atomic(root/"completion_status.json",dict(state="analysis_complete_pending_documentation",
            completed=90,total=90,formal_fits=120,updated=time.time()))


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=("audit","seal","run"))
    parser.add_argument("--root",default=str(OUT));args=parser.parse_args()
    try:globals()[args.command](Path(args.root))
    except BaseException as error:
        if args.command=="run":
            atomic(Path(args.root)/"completion_status.json",dict(state="stopped",error=repr(error),
                traceback=traceback.format_exc(),automatic_retry=False,updated=time.time()))
        raise
