"""Read-only first-layer N-A attention diagnostics after all formal fits.
Uses dfg_v2/attention_probe.py::_relation and _attention_summary unchanged.
One eval forward per G3R best checkpoint; no gradients, optimizer or training.
Degree-one attention is reported separately from multi-neighbor concentration.
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
from . import batch_na_worker as worker
from .reporting import manifest_attempts


def evaluate(root,only):
    root=Path(root);plan=worker.load_plan(root);worker.validate_execution(root,plan)
    entries=manifest_attempts(root,plan)
    jobs=[j for j in plan["jobs"] if worker.job_id(j)==only and j["profile"]=="G3R"]
    if len(jobs)!=1:raise ValueError("Unknown attention job")
    job=jobs[0];out=root/"attention"/only;out.mkdir(parents=True,exist_ok=False)
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
            resource.check()
        write(out/"report.json",dict(passed=True,job_id=only,checkpoint=references[0],
            model_unchanged=True,eval_forwards=1,optimizer_steps=0,actual_device=worker.actual_device(),
            relations=rows,resources=resource.summary(),seconds=time.monotonic()-started,
            note="One-neighbor max=1 is structural, not saturation evidence; multi-neighbor distribution reported separately"))
        write(out/"receipt.json",dict(report=ref(out/"report.json"),
            artifacts=[ref(p) for p in sorted(out.iterdir()) if p.is_file()]))


def verify(root):
    root=Path(root);plan=worker.load_plan(root);artifacts=[]
    jobs=[j for j in plan["jobs"] if j["profile"]=="G3R"]
    if len(jobs)!=120:raise ValueError("Attention matrix differs")
    for job in jobs:
        p=root/"attention"/worker.job_id(job)/"report.json"
        receipt=read(p.with_name("receipt.json"))
        if receipt["report"]!=ref(p):raise ValueError("Attention receipt differs")
        report=read(checked(receipt["report"]))
        if not report["passed"] or report["job_id"]!=worker.job_id(job) or report["actual_device"]!=job["device_policy"]:
            raise ValueError("Attention identity differs")
        artifacts.append(receipt["report"])
    write(root/"attention/complete.json",dict(passed=True,count=120,artifacts=artifacts))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(worker.OUT));p.add_argument("--only")
    p.add_argument("--verify",action="store_true");a=p.parse_args()
    torch.set_num_threads(2)
    verify(a.root) if a.verify else evaluate(a.root,a.only)
