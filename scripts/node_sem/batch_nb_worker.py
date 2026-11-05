"""N-B orchestration adapted from scripts/node_sem/batch_na_worker.py.\nSource SHA256: c2d199d35d8f35e56fca85ee4887a1fa731ebcb359e1b5f528357a68332faac9
Training/assembly/verification core imported unchanged; only batch gates differ.
"""
import argparse
import copy
import contextlib
import datetime
import json
import os
from pathlib import Path
import sys
import time
import traceback
import torch
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.benchmark_v2.checkpoint import build_binding
from scripts.DFG.dfg_v2.benchmark_v2.protocol import PARTS, validate_parts
from scripts.DFG.dfg_v2.benchmark_v2.audit_supervision import make_part
from scripts.DFG.dfg_v2.benchmark_v2.support import model_support
from scripts.DFG.dfg_v2.benchmark_v2.input_guard import FitInputGuard
from scripts.DFG.dfg_v2.benchmark_v2.trainer import fit
from scripts.DFG.dfg_v2.experiment.run import _Lock, _move_model
from scripts.DFG.dfg_v2.experiment.preflight import (
    LOCAL_DEV_POLICY, run_preflight, initialize_context, make_observed_resources)
from scripts.DFG.dfg_v2.tasks import read_labels
from scripts.DFG.experiments.common import seed_all, tensor_digest, digest
from . import VERSION as NODESEM_VERSION
from . import batch_nb as batch_na
from .adapter import reset_modality_dropout
from .execution import GPU_LOCK
from .init import checked_initial
from .na_carrier import load_carrier, construct_carried


from .batch_na_worker import job_id, formal_config, actual_device, construct, run_core
from .batch_na_worker import verify_attempt as verify_na_attempt
ROOT = batch_na.ROOT
OUT = batch_na.DEFAULT

def load_plan(root=OUT):
    root=Path(root)
    seal=read(root/"plan.seal.json")
    plan=read(checked(seal["plan"]))
    if Path(seal["plan"]["path"]).resolve() != (root/"plan.json").resolve():
        raise ValueError("Plan seal path differs")
    batch_na.validate_envelope(plan,seal,ref(root/"plan.json"))
    return plan

def validate_execution(root,plan):
    root=Path(root)
    revision=read(root/"execution_revision.json")
    if (revision["plan"]!=ref(root/"plan.json") or revision["seal"]!=ref(root/"plan.seal.json")
            or revision.get("version")!="nodesem-nb-execution-v1"):
        raise ValueError("Execution revision binding differs")
    for name,sha in plan["runtime"].items():checked(dict(path=str(ROOT/name),sha256=sha))
    for name,sha in revision["runtime"].items():checked(dict(path=str(ROOT/name),sha256=sha))
    for name,sha in revision["gate_sources"].items():checked(dict(path=str(ROOT/name),sha256=sha))
    for r in revision["gates"].values():
        if not read(checked(r)).get("passed"):raise ValueError("Pretraining gate absent")
    if (revision.get("order") != batch_na.execution_order(plan["jobs"])
            or revision.get("configuration_override") is not False):
        raise ValueError("N-B execution order/config differs")
    auth=read(root/"authorization.json")
    if (auth.get("execution_authorized") is not True or auth.get("jobs")!=120
            or auth.get("view")!="original" or auth.get("label_policy")!="L-audit"
            or auth.get("seeds")!=[1] or auth.get("location")!="local_RTX3050"
            or not auth.get("user_request")
            or auth.get("plan")!=revision["plan"] or auth.get("seal")!=revision["seal"]
            or auth.get("execution_revision")!=ref(root/"execution_revision.json")):
        raise PermissionError("N-B execution authorization differs")
    return revision,auth


def verify_attempt(root, plan, job, attempt, deep=True):
    receipt = verify_na_attempt(root, plan, job, attempt, deep=deep)
    binding = read(Path(attempt)/"fit/binding.json")
    if binding.get("purpose") != "formal_NB":
        raise ValueError("Wrong N-B scoring purpose")
    return receipt


def run_formal(root,only):
    root=Path(root);plan=load_plan(root);revision,auth=validate_execution(root,plan)
    matches=[j for j in plan["jobs"] if job_id(j)==only]
    if len(matches)!=1:raise ValueError("Unknown formal job")
    job=matches[0];cfg=formal_config(plan,job)
    runs=root/"runs"/only;runs.mkdir(parents=True,exist_ok=True)
    old=sorted(runs.glob("attempt_*"))
    if any((a/"complete.json").exists() for a in old):
        raise FileExistsError("Successful fit must be verified/reused, never retrained")
    if old:
        # Only an explicit controller record can authorize one external interruption retry.
        permit=read(old[-1]/"external_interruption.json")
        if (len(old)!=1 or not auth.get("external_interrupt_retry_once")
                or permit.get("confirmed_external") is not True
                or permit.get("retry_authorized") is not True or (old[-1]/"failure.json").exists()):
            raise PermissionError("Failed fit cannot be automatically retried")
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

def main():
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(OUT));p.add_argument("--only",required=True)
    a=p.parse_args();torch.set_num_threads(2);run_formal(a.root,a.only)

if __name__ == "__main__": main()
