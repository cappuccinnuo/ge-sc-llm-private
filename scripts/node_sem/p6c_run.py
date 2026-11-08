"""NS-P6c evaluation-only batch. Never updates N-A/N-B or invokes their trainer."""
import argparse
import copy
import datetime
import json
import os
import subprocess
import time
from pathlib import Path
import numpy as np
import torch
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.experiment.run import _Lock, _move_model
from scripts.DFG.experiments.common import tensor_digest, digest
from . import batch_nb_worker as worker
from .nb_diagnostics import accepted_entries
from .checkpoint_io import load_checked
from .na_carrier import load_carrier, construct_carried
from .reporting import aligned_rows, read_artifact, identity
from .feature_spec import FeatureSpec
from .execution import GPU_LOCK
from .p6c_core import contribution_arrays, distribution, removed_input

ROOT = worker.ROOT
OUT = ROOT / "scripts/node_sem/artifacts/ns_p6c"
NB = ROOT / "scripts/node_sem/artifacts/batch_NB_v1"
SOURCES = ("p6c_core.py","p6c_run.py","p6c_probes.py","p6c_report.py")


def prepare(out=OUT):
    out=Path(out)
    if out.exists():
        raise FileExistsError("NS-P6c output already exists")
    plan=worker.load_plan(NB)
    worker.validate_execution(NB,plan)
    entries=accepted_entries(NB,plan)
    jobs=[j for j in plan["jobs"] if j["name"]=="S4g" and j["profile"]=="G3R"]
    if len(jobs)!=30: raise ValueError("Expected 30 S4g")
    out.mkdir()
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    weights=[];selected=[]
    for j in plan["jobs"]:
        directory,receipt=entries[worker.job_id(j)]
        references=[r for r in receipt["artifacts"] if Path(r["path"])==directory/"fit/best.pt"]
        if len(references)!=1: raise ValueError("Checkpoint reference missing")
        p=checked(references[0])
        weights.append(dict(job_id=worker.job_id(j),size_bytes=p.stat().st_size,**references[0]))
        if j in jobs:
            selected.append(dict(job=j,receipt=ref(directory/"receipt.json"),best=references[0]))
    missing=read(NB/"historical_weight_availability.json")
    git_common=subprocess.check_output(["git","rev-parse","--git-common-dir"],cwd=str(ROOT),text=True).strip()
    git_dir=(ROOT/git_common).resolve()
    git_bytes=int(subprocess.check_output(["du","-sb",str(git_dir)],text=True).split()[0])
    write(out/"na_checkpoint_note.json",dict(recorded_at_utc=now,
        source=ref(ROOT/"scripts/node_sem/PROMPTS.md"),source_section="5.9c.1",
        user_statement_as_recorded_in_user_supplied_prompt="N-A 的 480 个 best.pt/last.pt 是用户本人为节省空间主动删除的。",
        direct_chat_deletion_time_available=False,deletion_timestamp=None,
        cause="user_initiated_space_cleanup",historical_availability_unchanged=ref(NB/"historical_weight_availability.json"),
        historical_predictions_metrics_preserved=True,old_attention_already_sealed=True,
        current_checkpoint_reload_possible=False,server_replication_requires_retraining=True))
    write(out/"retained_nb_best_index.json",dict(weights=weights,count=len(weights),deletions=0))
    value=dict(version="nodesem-ns-p6c-v1",created_utc=now,
        head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT),text=True).strip(),
        nb_plan=ref(NB/"plan.json"),nb_seal=ref(NB/"plan.seal.json"),
        nb_complete=ref(NB/"complete.json"),nb_history=ref(NB/"historical_weight_availability.json"),
        jobs=selected,models=30,eval_conditions=["full","no_ctx","no_static","code_only"],
        S4_status="not_executed_missing_NA_weights_no_substitution",training=False,
        view="original",label_policy="L-audit",seed=1,
        runtime={n:ref(ROOT/"scripts/node_sem"/n) for n in SOURCES},
        schema=ref(ROOT/"scripts/node_sem/behavior_schema.json"),
        git_common_dir=str(git_dir),git_size_bytes=git_bytes,
        decisions=dict(S4="user approved S4g only; S4 unavailable",
            interpretation="user approved classification sensitivity, not proof of nonuse",
            sparse="user approved C grid and nonestimable single-class folds; no fold changes"),
        methods=dict(contribution="g_m * L2(P_m(normalized_x_m)); no shared bias; norm shares not causal or signed contributions",
            aggregation="per task/fold/model/node-type first, equal fold means; no independence of repeated nodes",
            removal="presence bit zero only in in-memory DGL local_scope; original graph/NPZ unchanged; gates recomputed",
            interpretation_threshold="code_only prediction changes <0.001 AND zero nonSolidiFI positive class changes",
            interpretation_limit="insensitivity to this intervention cannot prove nonuse; probability changes also reported",
            probe_C=[.01,.1,1,10],C_meaning="inverse L2 strength",
            solver="liblinear",tol=1e-4,max_iter=1000,standardization_fit="inner_train",
            C_selection="highest inner_val ROC AUC; ties smallest C; no refit on inner_val",
            threshold_selection="redundancy=0.5; signal=max inner_val BF1, ties closest 0.5 then lower threshold",
            prevalence="task-wide available STATIC rows, inclusive 1%-99%, as prescribed; transductive unsupervised bit filter disclosed",
            population="redundancy=all available carrier nodes by frozen file split; signal=L-audit included nonSolidiFI original nodes with CODE+STATIC available",
            groups="full schema subgroup and A-N parent both retained",
            undefined="train/val empty or single-class not estimable; test single-class AUC/BA null, BF1 retained",
            inference="descriptive only; no significance claims; probes fit logistic coefficients only, never HGT",
            final_server="Separate future batch on adequate VRAM; local RTX3050 is current limitation"))
    write(out/"plan.json",value);write(out/"plan.seal.json",dict(plan=ref(out/"plan.json")))
    return value


def load(out=OUT):
    out=Path(out);seal=read(out/"plan.seal.json")
    if Path(seal["plan"]["path"]).resolve()!=(out/"plan.json").resolve(): raise ValueError("Wrong plan path")
    p=read(checked(seal["plan"]))
    if p["version"]!="nodesem-ns-p6c-v1" or p["training"] is not False or len(p["jobs"])!=30:
        raise ValueError("Wrong diagnostic batch")
    for r in p["runtime"].values(): checked(r)
    for name in ("nb_plan","nb_seal","nb_complete","nb_history","schema"): checked(p[name])
    return p


def output_rows(model,job,logits):
    labels=read(checked(job["label_view"]))[job["task_id"]]
    truth={identity(r,job["granularity"]):r for r in labels
        if r["file"] in job["split"]["outer_test_files"] and r["L-audit_include"]}
    order=([ (d["source_file"],model.original_graph_node_ids[i]) for i,d in model.nx_graph.nodes(data=True)]
        if job["granularity"]=="node" else [(f,) for f in job["split"]["outer_test_files"]])
    probs=torch.softmax(logits,dim=-1).detach().cpu().numpy()
    pred=logits.argmax(dim=-1).detach().cpu().tolist()
    if len(order)!=len(probs): raise ValueError("Forward shape differs")
    rows=[]
    for k,prediction,prob in zip(order,pred,probs):
        if k not in truth: continue
        r=truth[k]
        rows.append(dict(file=r["file"],original_graph_node_id=r.get("original_graph_node_id"),
            source_sha256=r["source_sha256"],source_id=r.get("source_id"),
            target=r["L-audit_target"],prediction=int(prediction),probability=float(prob[1]),
            cohort="SolidiFI" if Path(r["file"]).name.startswith("buggy_") else "nonSolidiFI"))
    if len(rows)!=len(truth): raise ValueError("Lost scored identity")
    return rows


def contributions(model):
    rows=[];task_values={n:dict(gate=[],effective=[],share=[]) for n in ("code","ctx","static")}
    for adapter in model.adapt_ws:
        inp=model.symmetrical_global_graph.nodes[adapter.ntype].data["inp"]
        pres=adapter._input_presence(inp)
        projected=[]
        for name in adapter.names:
            span=adapter.spec.layout()[name];x=inp[:,span["start"]:span["stop"]]
            if name in adapter.norm: x=adapter.norm[name](x)
            projected.append(adapter.proj[name](x)*pres[:,adapter.names.index(name):adapter.names.index(name)+1])
        gates=adapter.last_gates.to(inp.device)
        eff,share,valid=contribution_arrays(torch.stack(projected,dim=1),gates,pres)
        for i,name in enumerate(adapter.names):
            active=pres[:,i]==1
            vals=dict(gate=gates[active,i].cpu().tolist(),effective=eff[active,i].cpu().tolist(),
                share=share[active & valid,i].cpu().tolist())
            rows.append(dict(node_type=adapter.ntype,modality=name,available_rows=int(active.sum()),
                zero_total_rows=int((~valid & active).sum()),**{k:distribution(v) for k,v in vals.items()}))
            for k,v in vals.items():task_values[name][k].extend(v)
    return rows,{n:{k:distribution(v) for k,v in d.items()} for n,d in task_values.items()}


def evaluate(out,only):
    out=Path(out);plan=load(out)
    matches=[e for e in plan["jobs"] if worker.job_id(e["job"])==only]
    if len(matches)!=1: raise ValueError("Unknown model")
    e=matches[0];j=e["job"];dest=out/"eval"/only;dest.mkdir(parents=True,exist_ok=False)
    write(dest/"started.json",dict(job_id=only,time=time.time(),plan=ref(out/"plan.json")))
    with _Lock(GPU_LOCK):
        if worker.actual_device()!=j["device_policy"]: raise ValueError("GPU/TF32 differs")
        receipt=read(checked(e["receipt"]));directory=Path(e["receipt"]["path"]).parent
        if receipt["job"]!=j: raise ValueError("Receipt job differs")
        # Reuse verified frozen assembly; no call to fit and no new initial file.
        model=worker.construct(j)
        original_fp=graph_fingerprint(model.nx_graph)
        payload=load_checked(e["best"])
        binding=read_artifact((directory,receipt),"binding.json")
        if payload["binding"]!=binding: raise ValueError("Checkpoint binding mismatch")
        model.load_state_dict(payload["state_dict"],strict=True)
        before=payload["state_sha256"];del payload
        model=_move_model(model,j["config"]["device"]);model.eval()
        if tensor_digest(model.state_dict())!=before: raise ValueError("Load changed state")
        recorded=aligned_rows(read_artifact((directory,receipt),"outer_test_predictions.json"),j,
            read(checked(j["label_view"])))
        reference={identity(r,j["granularity"]):r for r in recorded}
        conditions={};elapsed={};contrib=None;aggregate=None
        for name,removed in (("full",()),("no_ctx",("ctx",)),("no_static",("static",)),("code_only",("ctx","static"))):
            start=time.monotonic()
            with model.symmetrical_global_graph.local_scope(), torch.no_grad():
                for adapter in model.adapt_ws:
                    data=model.symmetrical_global_graph.nodes[adapter.ntype].data
                    data["inp"]=removed_input(data["inp"],adapter.spec,removed)
                raw=model() if j["granularity"]=="node" else model(j["split"]["outer_test_files"])[0]
                if not bool(torch.isfinite(raw).all()): raise ValueError("Nonfinite eval logits")
                conditions[name]=output_rows(model,j,raw)
                if name=="full":contrib,aggregate=contributions(model)
            elapsed[name]=time.monotonic()-start
            if tensor_digest(model.state_dict())!=before: raise ValueError("Eval changed parameters")
        baseline=conditions["full"]
        errors=[abs(r["probability"]-reference[identity(r,j["granularity"])]["best_positive_probability"]) for r in baseline]
        if any(r["prediction"]!=reference[identity(r,j["granularity"])]["best"] for r in baseline) or max(errors,default=0)>1e-6:
            raise ValueError("Full-input checkpoint baseline does not reproduce exported predictions")
        if graph_fingerprint(model.nx_graph)!=original_fp: raise ValueError("Graph mutation")
        checked(e["best"])
        write(dest/"result.json",dict(job_id=only,task_id=j["task_id"],fold=j["fold"],name="S4g",
            granularity=j["granularity"],checkpoint=e["best"],receipt=e["receipt"],plan=ref(out/"plan.json"),
            conditions=conditions,contributions=contrib,aggregate_contributions=aggregate,
            eval_mode=True,optimizer_steps=0,parameter_digest_before=before,
            parameter_digest_after=tensor_digest(model.state_dict()),source_graph_unchanged=True,
            historical_baseline_max_probability_error=max(errors,default=0),seconds=elapsed,
            actual_device=worker.actual_device()))
        write(dest/"receipt.json",dict(result=ref(dest/"result.json"),passed=True))


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("command",choices=["prepare","eval"])
    ap.add_argument("--out",default=str(OUT));ap.add_argument("--only");args=ap.parse_args()
    torch.set_num_threads(2)
    prepare(args.out) if args.command=="prepare" else evaluate(args.out,args.only)
