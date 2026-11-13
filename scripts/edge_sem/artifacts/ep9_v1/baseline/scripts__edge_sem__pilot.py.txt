"""EP7 one-step resource probes and approved train-only norm pilot.
Optimization steps reproduce benchmark_v2/trainer.py Adam/OneCycle/CE order.
This diagnostic never constructs heldout supervision or scores/chooses a best.
Source SHA is recorded in the approved trainer adapter and runtime snapshot.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import torch
from scripts.DFG.experiments.common import seed_all,tensor_digest,digest,scheduler_metadata
from .io import ROOT,ref,read,checked,write
from . import execution as ex
from .support import gradient_audit,edge_norms
from .supervision import make_part
from .checkpoint import validate_binding,extra_references
from scripts.DFG.dfg_v2.benchmark_v2.protocol import PARTS


def train_only(model,train,labels,config,support,dest,resources,epochs,norm_gate):
    """No validation part, target tensor, prediction, loss or checkpoint selection."""
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=False)
    if epochs not in (1,50):raise ValueError("Only sealed probe or norm durations")
    target=train.targets(model,labels)
    optimizer=torch.optim.Adam(model.parameters(),lr=config["initial_lr"],weight_decay=config["weight_decay"])
    scheduler=torch.optim.lr_scheduler.OneCycleLR(optimizer,max_lr=config["max_lr"],
        total_steps=config["schedule_epochs"],div_factor=config["div_factor"],
        final_div_factor=config["final_div_factor"],cycle_momentum=config["cycle_momentum"])
    criterion=torch.nn.CrossEntropyLoss();history=[];initial=tensor_digest(model.state_dict())
    post_encoder=None
    for epoch in range(epochs):
        start=time.monotonic();resources.check();model.train();optimizer.zero_grad()
        loss=criterion(train.forward(model),target)
        if not torch.isfinite(loss):raise ValueError("Nonfinite diagnostic train loss")
        loss.backward();audit=gradient_audit(model,support)
        if norm_gate and epoch==1:
            post_encoder=audit["edge_parameters"]["encoder_gradient_l1"]
            if post_encoder<=0:raise ValueError("Encoder gradient disconnected after first update")
        optimizer.step();scheduler.step()
        # No loss or classification metrics are exported by the norm-only path.
        row=dict(epoch=epoch,seconds=time.monotonic()-start,gradient_audit=audit,
            norms=edge_norms(model) if hasattr(model,"edge_encoder") else [])
        history.append(row)
        with (dest/"history.jsonl").open("a",encoding="utf8") as f:f.write(json.dumps(row)+"\n")
        resources.check()
        if str(model.device).startswith("cuda") and torch.cuda.max_memory_reserved()/1024**2>3584:
            raise RuntimeError("EP7 peak reserved VRAM exceeds 3.5 GiB")
        print("EP7 diagnostic epoch",epoch+1,"/",epochs,flush=True)
    final=history[-1]["norms"]
    if norm_gate:
        values=[r["u_frobenius"] for r in final]+[v for r in final for v in r["U_frobenius"].values()]
        if not values or all(v<.001 for v in values):raise ValueError("All final edge correction norms <1e-3")
    return dict(passed=True,epochs=epochs,initial_sha256=initial,final_state_sha256=tensor_digest(model.state_dict()),
        first_post_update_encoder_gradient_l1=post_encoder,final_norms=final,
        validation_or_test_supervision_constructed=False,validation_or_test_scored=False,best_selected=False,
        comparison_fit=False,resources=resources.summary())


def run_one(path,job):
    plan=ex.load(path);scope=plan["scope"]
    if scope not in ("gpu_probes","norm_pilot"):raise ValueError("Not a diagnostic plan")
    approval=ex.authorized(path,plan,scope)
    ex._member(plan,job);folder=ex.job_directory(Path(path).parent,job)
    found=ex._successful(folder)
    if found:return verify_one(path,plan,job,found)
    attempt=ex._next_attempt(path,job,folder);folder.mkdir(parents=True,exist_ok=True)
    write(attempt.with_suffix(".started.json"),dict(plan=ref(path),job=job,runtime=plan["runtime"],
        execution_authorization=approval,pid=os.getpid(),automatic_retry=False))
    cfg=job["config"]
    try:
        environment=ex.validate_environment(cfg)
        torch.set_num_threads(cfg["threads"])
        pre=ex.run_preflight(job,ref(path)["sha256"],folder,plan["resource_policy"])
        context=ex.initialize_context(pre["baseline"],cfg["device"])
        write(attempt.with_suffix(".context.json"),context)
        resources=ex.make_observed_resources(cfg["device"],pre["baseline"],context,
            attempt.with_suffix(".memory_samples.jsonl"),policy=plan["resource_policy"],history_path=attempt/"history.jsonl")
        with resources:
            model=ex.construct(plan,job,cfg["device"])
            # bind only the training part. Frozen assembly validates immutable
            # graph/label identities; it does not create heldout targets.
            binding=ex.build_binding(model,task_id=job["task_id"],fold=job["fold"],seed=1,profile="G3R",
                reducer="mean",graph_ref=job["graph"],fold_ref=job["folds"],label_ref=job["labels"],
                initial_sha256=job["initial"]["sha256"],config=cfg,split=job["split"],support=job["support"],
                initialization_record=job["initialization"])
            binding.update(initial_state_sha256=job["initial"]["state_sha256"],label_policy="L-audit",
                label_view=job["label_view"],feature_view=job["feature_view"],feature_npz=job["feature_npz"],
                source_preparation=job["source_preparation"],training_protocol="P2")
            ex._validate_edgesem_binding(binding,plan,job);validate_binding(model,binding)
            train=make_part(model,"node",job["split"]["inner_train_files"],binding)
            labels=ex.read_labels(job["labels"]);seed_all(job["seeds"]["fit"])
            result=train_only(model,train,labels,cfg,job["support"],attempt,resources,
                50 if scope=="norm_pilot" else 1,scope=="norm_pilot")
            validate_binding(model,binding)
        result["environment"]=environment
        result["resources"]=dict(resources.summary(),preflight=pre["receipt_ref"],
            context_ref=ref(attempt.with_suffix(".context.json")),resource_policy=plan["resource_policy"],training_pid=os.getpid())
        write(attempt/"binding.json",binding);write(attempt/"result.json",result)
        write(attempt/"receipt.json",dict(plan=ref(path),job=job,passed=True,runtime=plan["runtime"],
            started=ref(attempt.with_suffix(".started.json")),approval=approval,
            artifacts={p.name:ref(p) for p in sorted(attempt.iterdir()) if p.is_file()}))
        write(attempt/"receipt.seal.json",dict(receipt=ref(attempt/"receipt.json")))
    except Exception as e:
        write(attempt.with_suffix(".failure.json"),dict(error=repr(e),traceback=traceback.format_exc(),
            job=job,stop_batch=True,automatic_retry=False))
        raise
    return verify_one(path,plan,job,attempt)


def verify_one(path,plan,job,attempt):
    r=read(Path(attempt)/"receipt.json")
    if read(Path(attempt)/"receipt.seal.json")["receipt"]!=ref(Path(attempt)/"receipt.json"):raise ValueError("Diagnostic seal differs")
    if r["plan"]!=ref(path) or r["job"]!=job or r["runtime"]!=plan["runtime"] or r["passed"] is not True:
        raise ValueError("Diagnostic receipt identity differs")
    for reference in r["artifacts"].values():checked(reference)
    result=read(Path(attempt)/"result.json")
    if result["epochs"]!=(50 if plan["scope"]=="norm_pilot" else 1):raise ValueError("Diagnostic duration differs")
    if result["validation_or_test_scored"] is not False or result["best_selected"] is not False:raise ValueError("Diagnostic scoring not allowed")
    if result["resources"]["peak_reserved_mib"]>3584:raise ValueError("VRAM gate failed")
    ex._validate_edgesem_binding(read(Path(attempt)/"binding.json"),plan,job)
    if result["initial_sha256"]!=job["initial"]["state_sha256"]:raise ValueError("Diagnostic initial differs")
    if plan["scope"]=="norm_pilot":
        values=[r["u_frobenius"] for r in result["final_norms"]]+[v for r in result["final_norms"] for v in r["U_frobenius"].values()]
        if not values or all(v<.001 for v in values) or result["first_post_update_encoder_gradient_l1"]<=0:
            raise ValueError("Norm/encoder gate failed")
    resources=result["resources"]
    checked(dict(path=resources["raw_samples_path"],sha256=resources["raw_samples_sha256"]))
    checked(resources["preflight"]);checked(resources["context_ref"])
    return result


def controller(path):
    plan=ex.load(path);ex.authorized(path,plan,plan["scope"])
    root=Path(path).parent;accepted=[]
    with ex._Lock(root/".controller.lock"):
        for job in plan["jobs"]:
            folder=ex.job_directory(root,job);found=ex._successful(folder)
            if found is None:
                candidate=ex._next_attempt(path,job,folder);folder.mkdir(parents=True,exist_ok=True)
                with (folder/(candidate.name+".worker.log")).open("x",encoding="utf8") as f:
                    subprocess.run([sys.executable,"-B","-m","scripts.edge_sem.pilot","worker","--plan",str(path),
                        "--only",ex.job_id(job)],check=True,cwd=str(ROOT),stdout=f,stderr=subprocess.STDOUT)
                found=ex._successful(folder)
            if found is None:raise ValueError("Missing diagnostic receipt")
            verify_one(path,plan,job,found)
            accepted.append(ref(found/"receipt.json"))
        value=dict(plan=ref(path),passed=True,receipts=accepted)
        if (root/"complete.json").exists():
            if read(root/"complete.json")!=value:raise ValueError("Diagnostic completion differs")
        else:
            write(root/"complete.json",value);write(root/"complete.seal.json",dict(complete=ref(root/"complete.json")))

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=("worker","all"))
    p.add_argument("--plan",required=True);p.add_argument("--only");a=p.parse_args()
    if a.command=="all":controller(a.plan)
    else:
        plan=ex.load(a.plan);jobs=[j for j in plan["jobs"] if ex.job_id(j)==a.only]
        if len(jobs)!=1:raise ValueError("Select one sealed diagnostic")
        with ex._Lock(ex.GPU_LOCK):run_one(a.plan,jobs[0])

if __name__=="__main__":main()
