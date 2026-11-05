"""Formal N-A worker: frozen fit, sealed originals, no configuration overrides.

Core adapted from scripts/node_sem/p4_acceptance.py::run_fit/binding_parts
SHA256: 4c28f362f359420a70258bb4ddabfffde492b89041058c9e508d07cf2a239d41
Acceptance-only hooks and epoch override are excluded. The unchanged 8H
trainer owns optimization, early stopping, scores, exports and reload checks.
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
from . import batch_na
from .adapter import reset_modality_dropout
from .execution import GPU_LOCK
from .init import checked_initial
from .na_carrier import load_carrier, construct_carried

ROOT = batch_na.ROOT
OUT = batch_na.DEFAULT


def job_id(job):
    return "{}__{}__{}__fold_{}".format(job["task_id"],job["profile"],job["name"],job["fold"])


def load_plan(root=OUT):
    root=Path(root)
    seal=read(root/"plan.seal.json")
    plan=read(checked(seal["plan"]))
    if Path(seal["plan"]["path"]).resolve() != (root/"plan.json").resolve():
        raise ValueError("Plan seal path differs")
    batch_na.validate_envelope(plan,seal,ref(root/"plan.json"))
    return plan


def formal_config(plan,job):
    matches=[j for j in plan["jobs"] if batch_na.key(j)==batch_na.key(job)]
    if len(matches)!=1 or matches[0]!=job:
        raise ValueError("Job differs from sealed plan")
    # Do not normalize, coerce, or override any training field.
    return copy.deepcopy(job["config"])


def actual_device():
    return dict(location="local_RTX3050",device_type="cuda",
        gpu_model=torch.cuda.get_device_name(0),torch_version=torch.__version__,
        cuda_build_version=torch.version.cuda,
        allow_tf32=dict(matmul=torch.backends.cuda.matmul.allow_tf32,
                        cudnn=torch.backends.cudnn.allow_tf32))


def binding_parts(plan,job,model,cfg,execution=None,purpose="formal_NA"):
    binding=build_binding(model,task_id=job["task_id"],fold=job["fold"],seed=job["seed"],
        profile=job["profile"],reducer="mean",graph_ref=job["graph"],
        fold_ref=job["folds"],label_ref=job["labels"],initial_sha256=job["initial"]["sha256"],
        config=cfg,split=job["split"],support=job["support"],initialization_record=job["initialization"])
    binding.update(initial_state_sha256=job["initial"]["state_sha256"],label_policy="L-audit",
        label_view=job["label_view"],feature_view=job["feature_view"],feature_npz=job["feature_npz"],
        source_preparation=plan["source_preparation"],nodesem_version=NODESEM_VERSION,
        feature_spec=model.nodesem_spec,feature_spec_sha256=model.nodesem_spec_sha256,purpose=purpose)
    if execution is not None:binding["nodesem_execution_revision"]=execution
    groups=validate_parts(job["split"],job["graph_files"])
    return binding,{role:make_part(model,job["granularity"],groups[role],binding) for role in PARTS}


class EpochLog:
    """Format only the frozen trainer's progress line; no numerical callbacks."""
    def __init__(self,stream,folder):self.stream,self.folder,self.buffer=stream,Path(folder),""
    def write(self,text):
        self.buffer+=text
        while "\n" in self.buffer:
            line,self.buffer=self.buffer.split("\n",1)
            if " epoch " in line and " complete; patience=" in line:
                row=json.loads((self.folder/"history.jsonl").read_text().splitlines()[-1])
                line="{} epoch={} loss={:.9g} inner_val_loss={:.9g} seconds={:.3f}".format(
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),row["epoch"]+1,
                    row["train_loss"],row["inner_val_loss"],row["seconds"])
            self.stream.write(line+"\n");self.stream.flush()
        return len(text)
    def flush(self):self.stream.flush()


def run_core(plan,job,model,cfg,folder,resources=None,execution=None,purpose="formal_NA"):
    """Shared core; nonformal selfchecks supply their explicit diagnostic cfg."""
    folder=Path(folder);folder.parent.mkdir(parents=True,exist_ok=True)
    binding,parts=binding_parts(plan,job,model,cfg,execution,purpose)
    labels=read_labels(job["labels"])
    seed_all(job["seeds"]["fit"])
    dropout=reset_modality_dropout(model,job["seeds"]["fit"],job["task_id"],job["fold"],job["profile"])
    started=time.monotonic()
    with FitInputGuard(model,binding,parts,labels) as guard:
        with contextlib.redirect_stdout(EpochLog(sys.stdout,folder)):
            result=fit(model,guard.wrap_parts(),job["granularity"],labels,cfg,folder,binding,
                model.original_graph_node_ids,job["support"],memory_guard=resources)
        guard.finish()
        performance=guard.summary()
        write(folder/"validation_performance.json",performance)
    write(folder/"effective_config.json",cfg)
    write(folder/"dropout_identity.json",dict(seeds=dropout,fit_seed=job["seeds"]["fit"],
        counters={a.ntype:a.forward_count for a in model.adapt_ws if hasattr(a,"forward_count")}))
    return result,dict(fit_inclusive=time.monotonic()-started,
        epoch_loop=sum(json.loads(l)["seconds"] for l in (folder/"history.jsonl").read_text().splitlines()),
        scoring=performance["evaluation_seconds"],
        checkpoint_write=performance["save_seconds"],checkpoint_reload=performance["restore_seconds"])


def construct(job,phase=None):
    phase=phase or (lambda x:None)
    phase("carrier");carried,record,spec=load_carrier(job)
    phase("construct");seed_all(job["seeds"]["constructor"])
    model=construct_carried(job,carried,record,spec)
    phase("initial")
    initial=checked_initial(job["initial"],job["task_id"],job["fold"],job["profile"],
        seed=job["seed"],spec_digest=spec.digest())
    model.load_state_dict(initial["state_dict"],strict=True)
    if tensor_digest(model.state_dict())!=job["initial"]["state_sha256"]:
        raise ValueError("Loaded initial digest differs")
    if model_support(model,job["split"])!=job["support"]:
        raise ValueError("Registered support differs")
    return model


def validate_execution(root,plan):
    root=Path(root)
    revision=read(root/"execution_revision.json")
    if (revision["plan"]!=ref(root/"plan.json") or revision["seal"]!=ref(root/"plan.seal.json")
            or revision.get("version")!="nodesem-na-execution-v1"):
        raise ValueError("Execution revision binding differs")
    for name,sha in plan["runtime"].items():checked(dict(path=str(ROOT/name),sha256=sha))
    for name,sha in revision["runtime"].items():checked(dict(path=str(ROOT/name),sha256=sha))
    for name,sha in revision["gate_sources"].items():checked(dict(path=str(ROOT/name),sha256=sha))
    for r in revision["gates"].values():
        if not read(checked(r)).get("passed"):raise ValueError("Pretraining gate absent")
    auth=read(root/"authorization.json")
    if (auth.get("execution_authorized") is not True or auth.get("jobs")!=240
            or auth.get("view")!="original" or auth.get("label_policy")!="L-audit"
            or auth.get("seeds")!=[1] or auth.get("location")!="local_RTX3050"
            or not auth.get("user_request")
            or auth.get("plan")!=revision["plan"] or auth.get("seal")!=revision["seal"]
            or auth.get("execution_revision")!=ref(root/"execution_revision.json")):
        raise PermissionError("N-A execution authorization differs")
    return revision,auth


def verify_attempt(root,plan,job,attempt,deep=True):
    attempt=Path(attempt)
    complete=read(attempt/"complete.json")
    receipt=read(checked(complete["receipt"]))
    if (not complete.get("passed") or receipt["job"]!=job
            or receipt["plan"]!=ref(Path(root)/"plan.json")
            or receipt["execution_revision"]!=ref(Path(root)/"execution_revision.json")
            or receipt["actual_device"]!=job["device_policy"]):
        raise ValueError("Receipt identity/device differs")
    if deep:
        for item in receipt["artifacts"]:checked(item)
    run=attempt/"fit"
    if read(run/"effective_config.json")!=job["config"]:raise ValueError("Effective training config differs")
    binding=read(run/"binding.json")
    if (binding["initial_state_sha256"]!=job["initial"]["state_sha256"]
            or binding["effective_config_sha256"]!=digest(job["config"])
            or binding["split"]!=job["split"] or binding["fold"]!=job["fold"]
            or binding["profile"]!=job["profile"] or binding["feature_spec_sha256"]!=job["spec_sha256"]):
        raise ValueError("Checkpoint input/config binding differs")
    for name in ("graph","folds","labels","label_view","feature_view","feature_npz"):
        if binding[name]!=job[name]:raise ValueError("Receipt input binding differs")
    result=read(run/"result.json")
    if (result["status"]!="complete" or result["outer_supervision_used_in_optimization"]
            or not all(all(v.values()) for v in result["checkpoint_roundtrip_exact"].values())
            or result["initial_sha256"]!=job["initial"]["state_sha256"]
            or result["history_rows"]>job["config"]["maximum_training_epochs"]
            or result["parameter_count"]!=job["parameters"]):
        raise ValueError("Fit completeness differs")
    for ck in ("best","last"):
        if ref(run/(ck+".pt"))["sha256"]!=result["checkpoint_sha256"][ck]:
            raise ValueError("Checkpoint SHA differs")
    from scripts.DFG.dfg_v2.experiment.local_dev import validate_local_resource_summary
    resource=read(attempt/"resources/resource_summary.json")
    if resource!=receipt["resources"]:raise ValueError("Receipt resource summary differs")
    samples=[json.loads(l) for l in (attempt/"resources/samples.jsonl").read_text().splitlines()]
    validate_local_resource_summary(resource,LOCAL_DEV_POLICY,run/"history.jsonl",samples)
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
        plan=ref(root/"plan.json"),execution_revision=ref(root/"execution_revision.json")))
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
                    ref(root/"execution_revision.json"))
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


if __name__=="__main__":main()
