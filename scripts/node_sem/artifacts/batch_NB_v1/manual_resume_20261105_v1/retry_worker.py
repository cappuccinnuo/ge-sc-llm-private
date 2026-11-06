"""Explicit manual retry; frozen worker body unchanged except retry admission."""
import sys
from pathlib import Path
sys.path.insert(0,"/home/zhao/SmartContract/ge-sc-llm-ddg-v11")
from scripts.node_sem.batch_nb_worker import *
from scripts.node_sem.batch_nb_worker import _Lock, _move_model
from recovery_common import validate_manual_retry

def run_retry(root,only):
    root=Path(root);plan=load_plan(root);revision,auth=validate_execution(root,plan)
    matches=[j for j in plan["jobs"] if job_id(j)==only]
    if len(matches)!=1:raise ValueError("Unknown formal job")
    job=matches[0];cfg=formal_config(plan,job)
    runs=root/"runs"/only;runs.mkdir(parents=True,exist_ok=True)
    old=sorted(runs.glob("attempt_*"))
    if any((a/"complete.json").exists() for a in old):
        raise FileExistsError("Successful fit must be verified/reused, never retrained")
    validate_manual_retry(root,plan,job,old)
    attempt=runs/("attempt_{:03d}".format(len(old)+1));attempt.mkdir()
    started=time.monotonic();last=[started,"startup"]
    launch_unix=float(os.environ.get("NODESEM_STARTED_UNIX",time.time()))
    durations={"process_import_and_binding_validation":time.time()-launch_unix}
    def phase(name):
        now=time.monotonic();durations[last[1]]=now-last[0];last[:]=[now,name]
        with (attempt/"phases.jsonl").open("a",encoding="utf8") as f:
            f.write(json.dumps(dict(phase=name,unix_seconds=time.time()))+"\n")
    write(attempt/"started.json",dict(pid=os.getpid(),unix_seconds=time.time(),job_id=only,
        plan=ref(root/"plan.json"),execution_revision=ref(root/"execution_revision.json"), purpose="formal_NB"))
    resources=None
    try:
        with _Lock(GPU_LOCK):
            rdir=attempt/"resources";rdir.mkdir()
            pre=run_preflight(job,revision["plan"]["sha256"],rdir,LOCAL_DEV_POLICY)
            context=initialize_context(pre["baseline"],cfg["device"])
            write(rdir/"context.json",context)
            device=actual_device()
            if device!=job["device_policy"]:raise ValueError("Actual GPU/TF32 environment differs")
            resources=make_observed_resources(cfg["device"],pre["baseline"],context,
                rdir/"samples.jsonl",policy=LOCAL_DEV_POLICY,history_path=attempt/"fit/history.jsonl")
            with resources:
                resources.check()
                model=construct(job,phase)
                phase("binding_and_move")
                model=_move_model(model,cfg["device"])
                phase("train_and_score")
                result,times=run_core(plan,job,model,cfg,attempt/"fit",resources,
                    ref(root/"execution_revision.json"), purpose="formal_NB")
                resources.check()
                if actual_device()!=device:raise ValueError("Device/precision changed during fit")
            phase("write")
            summary=dict(resources.summary(),resource_policy=LOCAL_DEV_POLICY)
            write(rdir/"resource_summary.json",summary)
            phase("complete")
            write(attempt/"timing.json",dict(phases=durations,fit=times,
                total_seconds=time.time()-launch_unix,
                process_start_source="controller" if "NODESEM_STARTED_UNIX" in os.environ else "worker_entry_after_import",
                timing_note="fit inclusive overlaps epoch/scoring/checkpoint breakdown; never sum overlapping fields"))
            receipt=dict(job=job,plan=ref(root/"plan.json"),
                execution_revision=ref(root/"execution_revision.json"),authorization=ref(root/"authorization.json"),
                actual_device=device,resources=summary,fit=times,
                total_seconds=time.time()-launch_unix,
                artifacts=[ref(p) for p in sorted(attempt.rglob("*")) if p.is_file()])
            write(attempt/"receipt.json",receipt)
            write(attempt/"complete.json",dict(passed=True,receipt=ref(attempt/"receipt.json"),finished=time.time()))
            verify_attempt(root,plan,job,attempt)
    except BaseException as error:
        if resources is not None and not (attempt/"resources/resource_summary.json").exists():
            write(attempt/"resources/resource_summary.json",resources.summary())
        write(attempt/"failure.json",dict(error=repr(error),traceback=traceback.format_exc(),
            phase=last[1],cuda_oom="out of memory" in str(error).lower(),
            automatic_retry=False,unix_seconds=time.time()))
        raise

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",required=True)
    parser.add_argument("--only",required=True)
    args=parser.parse_args()
    torch.set_num_threads(2)
    run_retry(args.root,args.only)
