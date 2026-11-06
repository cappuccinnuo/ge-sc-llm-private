"""N-B read-only diagnostics adapted from scripts/node_sem/na_attention.py.
Source SHA256: bf4c09ddde4072e79336dedbba32849e990467cda5fa67aaa846ef5d07a66d7d
Frozen first-layer observation unchanged; adds available-modality gate summaries.
"""
import argparse
from pathlib import Path
import time
import torch
from scripts.DFG.dfg_v2.attention_probe import _relation,_attention_summary,_distribution
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,write,ref,checked
from scripts.DFG.dfg_v2.experiment.run import _Lock,_move_model
from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY,run_preflight,initialize_context,make_observed_resources
from scripts.DFG.experiments.common import tensor_digest
from .execution import GPU_LOCK
from .checkpoint_io import load_checked
from . import batch_nb_worker as worker
import numpy as np
import statistics
from .adapter import NodeSemAdapter


def evaluate(root,only):
    root=Path(root);check_analysis(root);plan=worker.load_plan(root);worker.validate_execution(root,plan)
    entries=accepted_entries(root,plan)
    jobs=[j for j in plan["jobs"] if worker.job_id(j)==only and j["profile"]=="G3R"]
    if len(jobs)!=1:raise ValueError("Unknown attention job")
    job=jobs[0];out=root/"diagnostics"/only;out.mkdir(parents=True,exist_ok=False)
    with _Lock(GPU_LOCK):
        pre=run_preflight(job,ref(root/"plan.json")["sha256"],out,LOCAL_DEV_POLICY)
        context=initialize_context(pre["baseline"],job["config"]["device"])
        resource=make_observed_resources(job["config"]["device"],pre["baseline"],context,
            out/"samples.jsonl",policy=LOCAL_DEV_POLICY,history_path=out/"eval_has_no_epoch_history.jsonl")
        with resource:
            if worker.actual_device()!=job["device_policy"]:raise ValueError("Attention device/TF32 differs")
            model=worker.construct(job);directory,receipt=entries[only]
            ckpath=(directory/"fit/best.pt").resolve()
            references=[r for r in receipt["artifacts"] if Path(r["path"]).resolve()==ckpath]
            if len(references)!=1:raise ValueError("Best checkpoint reference missing")
            payload=load_checked(references[0])
            if payload["binding"]!=read(directory/"fit/binding.json"):
                raise ValueError("Best checkpoint binding differs")
            model.load_state_dict(payload["state_dict"],strict=True)
            before=payload["state_sha256"];del payload
            model=_move_model(model,job["config"]["device"]);model.eval()
            rows=[];calls=[]
            def observe(layer,args):
                graph,h=args;calls.append(1)
                for canonical in graph.canonical_etypes:
                    with graph.local_scope():
                        trace=_relation(layer,graph,h,canonical)
                        summary=_attention_summary(trace,None)
                        targets=summary.pop("targets")
                        summary["heads"]=[dict(head=i,
                            all_targets=_distribution([t["max_weight_by_head"][i] for t in targets]),
                            multi_neighbor_targets=_distribution([t["max_weight_by_head"][i] for t in targets if t["in_degree"]>=2]))
                            for i in range(layer.n_heads)]
                        rows.append(summary)
            hook=model.gcs[0].register_forward_pre_hook(observe)
            started=time.monotonic()
            try:
                with torch.no_grad():
                    if job["granularity"]=="node":model()
                    else:model(job["graph_files"])
            finally:hook.remove()
            if len(calls)!=1 or tensor_digest(model.state_dict())!=before:
                raise AssertionError("Attention probe changed weights or forwarded repeatedly")
            gates=collect_gates(model,job)
            resource.check()
        write(out/"report.json",dict(passed=True,job_id=only,checkpoint=references[0],
            model_unchanged=True,eval_forwards=1,optimizer_steps=0,actual_device=worker.actual_device(),
            analysis_revision=ref(root/"analysis_revision.json"),gates=gates,gate_applicable=job["name"]=="S4g",
            relations=rows,resources=resource.summary(),seconds=time.monotonic()-started,
            note="One-neighbor max=1 is structural, not saturation evidence; multi-neighbor distribution reported separately"))
        write(out/"receipt.json",dict(report=ref(out/"report.json"),
            artifacts=[ref(p) for p in sorted(out.iterdir()) if p.is_file()]))


def check_analysis(root):
    root=Path(root);value=read(root/"analysis_revision.json")
    if (value.get("version")!="nodesem-nb-analysis-v1"
            or value["plan"]!=ref(root/"plan.json")
            or value["execution_revision"]!=ref(root/"execution_revision.json")
            or value.get("training_changed") is not False):
        raise ValueError("Analysis binding differs")
    expected={str((worker.ROOT/"scripts/node_sem"/n).resolve())
        for n in ("nb_diagnostics.py","nb_reporting.py","nb_finalize.py")}
    if not expected.issubset({str(Path(r["path"]).resolve()) for r in value["sources"]}):
        raise ValueError("Analysis code binding incomplete")
    for r in value["sources"]:checked(r)
    for r in value["gates"]:
        if read(checked(r)).get("passed") is not True:raise ValueError("Analysis gate failed")
    return value


def accepted_entries(root,plan):
    root=Path(root);done=read(root/"complete.json")
    if (not done.get("passed") or done.get("formal_fits")!=120
            or len(done.get("receipts",[]))!=120 or done["plan"]!=ref(root/"plan.json")
            or done["execution_revision"]!=ref(root/"execution_revision.json")):
        raise ValueError("Full 120 accepted fit matrix required")
    entries={}
    for r in done["receipts"]:
        v=read(checked(r));key=worker.job_id(v["job"])
        if key in entries:raise ValueError("Duplicate fit receipt")
        entries[key]=(Path(r["path"]).parent,v)
    if set(entries)!={worker.job_id(j) for j in plan["jobs"]}:
        raise ValueError("Accepted matrix differs")
    return entries


def gate_summary(weights,presence,names,ntype):
    weights=weights.detach().cpu();presence=presence.detach().cpu()
    if (weights.ndim!=2 or weights.shape!=presence.shape or weights.shape[1]!=len(names)
            or len(set(names))!=len(names) or not bool(torch.isfinite(weights).all())
            or not bool(((presence==0)|(presence==1)).all())
            or bool(((weights<0)|(weights>1)).any())):
        raise ValueError("Invalid gate/presence")
    active=presence==1;any_active=active.any(dim=1)
    if bool((weights[~active]!=0).any()) or not torch.allclose(
            weights.sum(dim=1),any_active.to(weights.dtype),rtol=0,atol=1e-6):
        raise ValueError("Unavailable gate or normalization differs")
    rows=[]
    for i,name in enumerate(names):
        values=weights[active[:,i],i].tolist()
        qs=np.percentile(values,[5,25,50,75,95]).tolist() if values else [None]*5
        rows.append(dict(node_type=ntype,modality=name,available_rows=len(values),
            total_rows=int(weights.shape[0]),any_available_rows=int(any_active.sum()),
            all_missing_rows=int((~any_active).sum()),
            mean=statistics.mean(values) if values else None,
            sample_sd=statistics.stdev(values) if len(values)>1 else None,
            minimum=min(values) if values else None,maximum=max(values) if values else None,
            p05=qs[0],p25=qs[1],median=qs[2],p75=qs[3],p95=qs[4],
            fraction_ge_0_9=sum(x>=0.9 for x in values)/len(values) if values else None))
    return rows


def collect_gates(model,job):
    if job["name"]!="S4g":return []
    rows=[]
    for adapter in model.adapt_ws:
        if not isinstance(adapter,NodeSemAdapter) or adapter.spec.fusion!="gated":
            raise ValueError("S4g adapter differs")
        if adapter.last_gates is None:raise ValueError("Gate observation absent")
        inp=model.symmetrical_global_graph.nodes[adapter.ntype].data["inp"]
        rows.extend(gate_summary(adapter.last_gates,inp[:,:len(adapter.names)],adapter.names,adapter.ntype))
    return rows


def verify_one(root,job):
    root=Path(root);p=root/"diagnostics"/worker.job_id(job)/"report.json"
    receipt=read(p.with_name("receipt.json"))
    if receipt["report"]!=ref(p):raise ValueError("Diagnostic receipt differs")
    for reference in receipt["artifacts"]:checked(reference)
    value=read(checked(receipt["report"]))
    if (value.get("passed") is not True or value["job_id"]!=worker.job_id(job)
            or value["actual_device"]!=job["device_policy"] or value["eval_forwards"]!=1
            or value["optimizer_steps"]!=0 or value["model_unchanged"] is not True
            or value["analysis_revision"]!=ref(root/"analysis_revision.json")
            or value["gate_applicable"]!=(job["name"]=="S4g")):
        raise ValueError("Diagnostic identity differs")
    if job["name"]=="S4g" and not value["gates"]:raise ValueError("Gates missing")
    return receipt["report"]


def verify(root):
    root=Path(root);check_analysis(root);plan=worker.load_plan(root)
    worker.validate_execution(root,plan);accepted_entries(root,plan)
    jobs=[j for j in plan["jobs"] if j["profile"]=="G3R"]
    if len(jobs)!=90 or sum(j["name"]=="S4g" for j in jobs)!=30:
        raise ValueError("Diagnostic matrix differs")
    value=dict(passed=True,count=90,gate_evals=30,noG_not_applicable=30,
        artifacts=[verify_one(root,j) for j in jobs],analysis_revision=ref(root/"analysis_revision.json"))
    path=root/"diagnostics/complete.json"
    if path.exists():
        if read(path)!=value:raise ValueError("Existing diagnostics differ")
    else:write(path,value)
    return value


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(worker.OUT));p.add_argument("--only")
    p.add_argument("--verify",action="store_true");a=p.parse_args();torch.set_num_threads(2)
    verify(a.root) if a.verify else evaluate(a.root,a.only)
