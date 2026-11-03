"""NS-P4 sealed, nonformal CPU smoke and separately authorized GPU probes.

Imports the frozen benchmark trainer/guard/checkpoint/supervision unchanged.
No new formal execution matrix is enabled. Existing plans/seals stay immutable.
"""
import argparse
import copy
import gc
import json
import os
from pathlib import Path
import time
import traceback
import numpy as np
import torch
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.benchmark_v2.checkpoint import build_binding, validate_binding
from scripts.DFG.dfg_v2.benchmark_v2.protocol import PARTS, validate_parts
from scripts.DFG.dfg_v2.benchmark_v2.audit_supervision import make_part
from scripts.DFG.dfg_v2.benchmark_v2.support import model_support
from scripts.DFG.dfg_v2.benchmark_v2.input_guard import FitInputGuard
from scripts.DFG.dfg_v2.benchmark_v2.trainer import fit
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.experiment.run import _Lock, _move_model
from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY,run_preflight,initialize_context,make_observed_resources
from scripts.DFG.dfg_v2.experiment.resources import Resources
from scripts.DFG.dfg_v2.tasks import read_labels
from scripts.DFG.experiments.common import seed_all, tensor_digest
from scripts.labeling_v2.safe_graph import read_graph
from .feature_spec import FeatureSpec
from .model import make_nodesem_model,validate
from .adapter import reset_modality_dropout
from .init import initial_state,checked_initial,VERSION as INIT_VERSION
from .carrier import carry,write_carrier
from .execution import runtime_refs,GPU_LOCK
from .checkpoint_io import load_checked
from . import VERSION as NODESEM_VERSION

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"scripts/node_sem"
OUT=BASE/"artifacts/ns_p4"
CPU_NAMES=("S2","S3","S4","S4g","S4-noG","S3m","S4m")
GPU_NAMES=("S1o","S4")
VERSION="nodesem-p4-acceptance-v1"


def save_initial(model,spec,task_id,profile,info,entry,path):
    state,sha=initial_state(model,spec,task_id,0,profile,entry["initial"])
    payload=dict(kind="untrained_initial",optimizer_steps=0,task_id=task_id,fold=0,seed=1,
        profile=profile,constructor_seed=info["seeds"]["constructor"],fit_seed=info["seeds"]["fit"],
        feature_spec_sha256=spec.digest(),state_dict=state,state_sha256=sha,
        initialization_version=INIT_VERSION,source=entry["initial"],nonformal=True)
    with path.open("xb") as stream: torch.save(payload,stream)
    reference=dict(ref(path),state_sha256=sha)
    # Immediate SHA guard and tensor check, using the previously approved local scope.
    loaded=checked_initial(reference,task_id,0,profile,spec_digest=spec.digest())
    model.load_state_dict(loaded["state_dict"],strict=True)
    return reference


def _source():
    audit=read(BASE/"artifacts/ns_p1_initial_digests/digests.json")
    if audit.get("passed") is not True or audit.get("count")!=60:
        raise ValueError("Historical initial digest audit missing")
    return audit,h8.load(checked(audit["plan"]))


def _entry(source,task_id,profile):
    jobs=[j for j in source["jobs"] if (j["task_id"],j["profile"],j["fold"],j["seed"])==(task_id,profile,0,1)]
    if len(jobs)!=1: raise ValueError("Historical identity missing/ambiguous")
    return jobs[0],h8.prepared(source,jobs[0])


def bind_spec(name,task_id,refs,token_ref):
    s=read(BASE/"configs"/(name+".json"))
    for m in s["modalities"]:
        if m["name"]=="token_ids": m["manifest"]=token_ref
        elif m["name"]=="ctx": m["manifest"]=refs["ctx"]["masked" if name in ("S3m","S4m") else "original"]
        else: m["manifest"]=refs[m["name"]]
    result=FeatureSpec.from_json(s)
    if result.view!="original": raise ValueError("NS-P4 uses original main view")
    return result


def prepare():
    audit,source=_source()
    current=read(BASE/"artifacts/ns_p3/CURRENT.json")
    accepted=read(checked(current["validation"]))
    if read(checked(current["seal"]))["validation"]!=current["validation"]:
        raise ValueError("P3b2 acceptance seal differs")
    if not accepted["passed"] or accepted["static_dimension"]!=245: raise ValueError("P3b2 gate absent")
    source_preparation=read(checked(source["source_preparation"]))
    views_ref=source_preparation["bound_artifacts"]["feature_views"]
    views=read(checked(views_ref))
    out=OUT/"prepared";out.mkdir(exist_ok=False)
    checks=[];specs={};jobs=[]
    for task_id,refs in accepted["tasks"].items():
        token=views["task_views"][task_id]["original"]
        for name in ("S0o","S1o")+CPU_NAMES:
            spec=bind_spec(name,task_id,refs,token)
            dest=out/"specs"/task_id/(name+".json")
            dest.parent.mkdir(parents=True,exist_ok=True)
            write(dest,spec.to_json());specs[(task_id,name)]=ref(dest)
        for profile in ("G0","G3R"):
            _,(task,info,entry)=_entry(source,task_id,profile)
            graph=read_graph(checked(entry["graph"]))
            before=graph_fingerprint(graph)
            spec=FeatureSpec.from_json(read(checked(specs[(task_id,"S0o")])))
            carried,record=carry(graph,spec,task_id)
            if not all(np.array_equal(graph.nodes[n]["token"],carried.nodes[n]["token"]) for n in graph):
                raise ValueError("Original token view is not bitwise identical to frozen graph tokens")
            if graph_fingerprint(graph)!=before: raise ValueError("Original graph changed")
            checks.append(dict(task_id=task_id,profile=profile,graph=entry["graph"],token_manifest=token,
                exact=True,nodes=len(graph),carrier_dim=spec.carrier_dim()))
            del graph,carried;gc.collect()
        print("original-token verification PASS "+task_id,flush=True)
    # A measured historical construction baseline; no fitting or new anonymous features.
    oldjob,(task,info,entry)=_entry(source,"reentrancy_node","G3R")
    started=time.monotonic();model=h8.construct(source,oldjob,"cpu");baseline_seconds=time.monotonic()-started
    old_sha=tensor_digest(model.state_dict());del model;gc.collect()
    spec=FeatureSpec.from_json(read(checked(specs[("reentrancy_node","S0o")])))
    seed_all(info["seeds"]["constructor"])
    model=make_nodesem_model("node",entry["graph"],"G3R",spec,task["config"],"cpu","reentrancy_node")
    raw_initial=save_initial(model,spec,"reentrancy_node","G3R",info,entry,out/"S0o_initial.pt")
    if raw_initial["state_sha256"]!=old_sha: raise ValueError("S0o differs from historical S0 parameter state")
    write(out/"S0o_proof.json",dict(passed=True,initial=raw_initial,h8_initial=entry["initial"],
        all_parameters_exact=True,original_tokens_exact=True,h8_constructor_seconds=baseline_seconds))
    del model;gc.collect()
    requested=[("cpu","reentrancy_node",n) for n in CPU_NAMES]+[("gpu","reentrancy_contract",n) for n in GPU_NAMES]
    for device,task_id,name in requested:
        profile="G0" if name=="S4-noG" else "G3R"
        _,(task,info,entry)=_entry(source,task_id,profile)
        spec_ref=specs[(task_id,name)];spec=FeatureSpec.from_json(read(checked(spec_ref)))
        directory=out/device/name;directory.mkdir(parents=True,exist_ok=False)
        seed_all(info["seeds"]["constructor"]);start=time.monotonic()
        model=make_nodesem_model(task["granularity"],entry["graph"],profile,spec,task["config"],"cpu",task_id)
        seconds=time.monotonic()-start
        initial=save_initial(model,spec,task_id,profile,info,entry,directory/"initial.pt")
        carrier=write_carrier(spec,task_id,read_graph(checked(entry["graph"])),directory/"carrier")
        support=model_support(model,info["split"])
        params=sum(p.numel()*p.element_size() for p in model.parameters())
        inp=sum(model.symmetrical_global_graph.nodes[n].data["inp"].numel()*4 for n in model.symmetrical_global_graph.ntypes)
        edges=sum(sum(t.numel()*t.element_size() for t in model.symmetrical_global_graph.edges(etype=e)) for e in model.symmetrical_global_graph.canonical_etypes)
        job=dict(name=name,actual_device=device,task_id=task_id,granularity=task["granularity"],fold=0,seed=1,
            profile=profile,spec=spec_ref,spec_sha256=spec.digest(),graph=entry["graph"],
            initial=initial,h8_initial=entry["initial"],initialization=info["initialization"],
            labels=task["record"]["labels"],folds=task["record"]["folds"],label_view=task["label_view"],
            split=info["split"],graph_files=task["record"]["graph_files"],seeds=info["seeds"],
            config=task["config"],feature_view=carrier["manifest"],feature_npz=carrier["data"],
            support=support,constructor_seconds=seconds,carrier_dim=spec.carrier_dim(),
            parameters=sum(p.numel() for p in model.parameters()),
            tensor_memory=dict(parameter_bytes=params,gradient_bytes=params,adam_moments_bytes=2*params,
                input_bytes=inp,edge_endpoint_bytes=edges,estimated_subtotal_mib=(4*params+inp+edges)/1024**2,
                excludes="activations, attention buffers, graph caches, allocator/context and peak lifetimes"))
        jobs.append(job);write(directory/"job.json",job)
        print("prepared {} {} D={} {:.2f}s".format(device,name,spec.carrier_dim(),seconds),flush=True)
        del model;gc.collect()
    plan=dict(version=VERSION,formal_training_authorized=False,jobs=jobs,source_h8_plan=audit["plan"],
        source_preparation=source["source_preparation"],feature_source=current,original_token_sources=views_ref,
        original_token_checks=checks,h8_constructor_seconds=baseline_seconds,decisions=ref(OUT/"decisions.json"),
        runtime=runtime_refs(),driver=ref(Path(__file__)),config_index=ref(BASE/"configs/NS_P4_INDEX.json"),
        cpu_fits=7,gpu_probes=2,maximum_training_epochs=1,only_training_config_override="maximum_training_epochs")
    write(OUT/"plan.json",plan);write(OUT/"plan.seal.json",dict(plan=ref(OUT/"plan.json")))
    return plan


def load():
    plan=read(checked(read(OUT/"plan.seal.json")["plan"]))
    if (plan["version"]!=VERSION or plan["runtime"]!=runtime_refs()
            or plan["driver"]!=ref(Path(__file__))): raise ValueError("NS-P4 acceptance runtime changed")
    if not read(checked(plan["decisions"]))["gpu_probe"]["user_approved"]:
        raise ValueError("Probe approval missing")
    h8.load(checked(plan["source_h8_plan"]))
    return plan


def binding_parts(plan,job,model,cfg):
    spec=FeatureSpec.from_json(read(checked(job["spec"])))
    binding=build_binding(model,task_id=job["task_id"],fold=0,seed=1,profile=job["profile"],reducer="mean",
        graph_ref=job["graph"],fold_ref=job["folds"],label_ref=job["labels"],
        initial_sha256=job["initial"]["sha256"],config=cfg,split=job["split"],support=job["support"],
        initialization_record=job["initialization"])
    binding.update(initial_state_sha256=job["initial"]["state_sha256"],label_policy="L-audit",
        label_view=job["label_view"],feature_view=job["feature_view"],feature_npz=job["feature_npz"],
        source_preparation=plan["source_preparation"],nodesem_version=NODESEM_VERSION,
        feature_spec=spec.to_json(),feature_spec_sha256=spec.digest(),purpose="nonformal_ns_p4_one_epoch_acceptance")
    validate_binding(model,binding)
    groups=validate_parts(job["split"],job["graph_files"])
    return binding,{role:make_part(model,job["granularity"],groups[role],binding) for role in PARTS}


class ProbeGuard:
    """Keep local_dev telemetry but enforce the separately approved P4 stop gate."""
    def __init__(self,inner): self.inner=inner
    def __enter__(self): self.inner.__enter__();return self
    def __exit__(self,*args): return self.inner.__exit__(*args)
    def check(self): Resources.check(self.inner)
    def summary(self): return self.inner.summary()


def run_fit(plan,job,resources=None,*,output_root=None,run_directory=None,device_setup=None,phase=None):
    output_root=Path(output_root) if output_root is not None else OUT
    phase=phase if phase is not None else lambda value: None
    phase("construct_and_validate_initial")
    cfg=copy.deepcopy(job["config"]);cfg["maximum_training_epochs"]=1
    spec=FeatureSpec.from_json(read(checked(job["spec"])))
    seed_all(job["seeds"]["constructor"]);started=time.monotonic()
    model=make_nodesem_model(job["granularity"],job["graph"],job["profile"],spec,cfg,"cpu",job["task_id"])
    construct_seconds=time.monotonic()-started
    payload=checked_initial(job["initial"],job["task_id"],0,job["profile"],spec_digest=spec.digest())
    model.load_state_dict(payload["state_dict"],strict=True);del payload
    old=checked_initial(job["h8_initial"],job["task_id"],0,job["profile"])["state_dict"]
    if not all(torch.equal(v,old[k]) for k,v in model.state_dict().items() if k.startswith(("gcs.","classify."))):
        raise ValueError("Common initial parameters differ")
    del old
    validate(model,spec)
    if model.nodesem_carrier_record!={k:v for k,v in read(checked(job["feature_view"])).items() if k!="data"}:
        raise ValueError("Carrier manifest differs")
    if model_support(model,job["split"])!=job["support"]: raise ValueError("Support differs")
    if device_setup is not None:
        model=device_setup(model,cfg)
    elif job["actual_device"]=="gpu":
        model=_move_model(model,cfg["device"])
    if resources: resources.check()
    binding,parts=binding_parts(plan,job,model,cfg)
    labels=read_labels(job["labels"])
    gradients={};handles=[]
    def capture(name):
        def hook(grad):
            gradients[name]=dict(finite=bool(torch.isfinite(grad).all()),l1=float(grad.detach().abs().sum()),nonzero=int(torch.count_nonzero(grad)))
        return hook
    for name,p in model.named_parameters():
        if name.startswith(("adapt_ws.","nodesem_shared.")): handles.append(p.register_hook(capture(name)))
    seed_all(job["seeds"]["fit"])
    dropout=reset_modality_dropout(model,job["seeds"]["fit"],job["task_id"],0,job["profile"])
    folder=Path(run_directory) if run_directory is not None else output_root/"runs"/job["actual_device"]/job["name"]
    folder.parent.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    phase("frozen_fit_train_validation_checkpoint_reload")
    try:
        with FitInputGuard(model,binding,parts,labels) as guard:
            result=fit(model,guard.wrap_parts(),job["granularity"],labels,cfg,folder,binding,
                       model.original_graph_node_ids,job["support"],memory_guard=resources)
            guard.finish();write(folder/"validation_performance.json",guard.summary())
    finally:
        for h in handles: h.remove()
    history=[json.loads(l) for l in (folder/"history.jsonl").read_text().splitlines()]
    if len(history)!=1 or not all(np.isfinite(history[0][k]) for k in ("train_loss","inner_val_loss")):
        raise ValueError("One-epoch finite-loss smoke failed")
    if not gradients or not all(r["finite"] for r in gradients.values()) or not any(r["nonzero"] for r in gradients.values()):
        raise ValueError("No finite nonzero adapter supervision gradient")
    # Check each modality receives a nonzero gradient somewhere, not every rare type.
    modality_grad={}
    for m in spec.modalities:
        fragment="token_projection.weight" if model.adapt_ws[0].legacy_token else "proj."+m["name"]+".weight"
        modality_grad[m["name"]]=sum(v["l1"] for k,v in gradients.items() if fragment in k)
    if not all(v>0 for v in modality_grad.values()): raise ValueError("A modality has no nonzero projection gradient")
    gates=[]
    for a in model.adapt_ws:
        if a.last_gates is not None:
            sums=a.last_gates.sum(1);active=sums!=0
            error=float((sums[active]-1).abs().max()) if bool(active.any()) else 0.
            if error>1e-6: raise ValueError("Gate normalization failed")
            gates.append(dict(node_type=a.ntype,rows=len(sums),active_rows=int(active.sum()),max_sum_error=error))
    report=dict(passed=True,job=job,formal_fit=False,epochs=1,actual_device=job["actual_device"],
        common_initial_exact=True,constructor_seconds=construct_seconds,fit_seconds=time.monotonic()-start,
        constructor_over_3x_h8=construct_seconds>3*plan["h8_constructor_seconds"],
        effective_config=cfg,only_config_override="maximum_training_epochs",history=history,
        gradients=gradients,modality_projection_gradient_l1=modality_grad,gates=gates,
        dropout_seeds=dropout,dropout_forward_counts={a.ntype:a.forward_count for a in model.adapt_ws},
        checkpoint_roundtrip_exact=result["checkpoint_roundtrip_exact"],checkpoint_sha256=result["checkpoint_sha256"])
    write(folder/"acceptance.json",report)
    write(folder/"effective_config.json",cfg)
    write(folder/"acceptance.seal.json",dict(acceptance=ref(folder/"acceptance.json"),plan=ref(output_root/"plan.json")))
    phase("accepted")
    print("PASS "+job["actual_device"]+" "+job["name"],flush=True)
    return report


def cpu(name):
    plan=load();jobs=[j for j in plan["jobs"] if j["actual_device"]=="cpu" and j["name"]==name]
    if len(jobs)!=1: raise ValueError("Unknown CPU check")
    return run_fit(plan,jobs[0])


def gpu(name):
    plan=load()
    for n in CPU_NAMES:
        record=read(OUT/"runs/cpu"/n/"acceptance.json")
        if record.get("passed") is not True: raise ValueError("CPU gate incomplete")
    jobs=[j for j in plan["jobs"] if j["actual_device"]=="gpu" and j["name"]==name]
    if len(jobs)!=1: raise ValueError("Unknown GPU probe")
    if name=="S4" and not read(OUT/"gpu_S1o.json")["passed"]: raise ValueError("First GPU probe not accepted")
    job=jobs[0];folder=OUT/"gpu_resources"/name;folder.mkdir(parents=True,exist_ok=False)
    with _Lock(GPU_LOCK):
        pre=run_preflight(job,ref(OUT/"plan.json")["sha256"],folder,LOCAL_DEV_POLICY)
        context=initialize_context(pre["baseline"],job["config"]["device"])
        write(folder/"context.json",context)
        inner=make_observed_resources(job["config"]["device"],pre["baseline"],context,folder/"samples.jsonl",
            policy=LOCAL_DEV_POLICY,history_path=OUT/"runs/gpu"/name/"history.jsonl")
        resource=ProbeGuard(inner)
        try:
            with resource:
                resource.check();run_fit(plan,job,resource);resource.check()
        finally:
            write(folder/"resource_summary.json",resource.summary())
        summary=resource.summary()
        if summary["minimum_free_mib"]<100: raise RuntimeError("Probe minimum free below 100 MiB; stop")
        report=dict(passed=True,resources=summary,preflight=pre["receipt_ref"],context=ref(folder/"context.json"))
        write(OUT/("gpu_"+name+".json"),report)
        return report


def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument("stage",choices=("prepare","cpu","gpu"));parser.add_argument("--only")
    parser.add_argument("--out",default=str(OUT))
    args=parser.parse_args();torch.set_num_threads(2)
    OUT=Path(args.out).resolve()
    if (BASE/"artifacts").resolve() not in OUT.parents: raise ValueError("Output must be under NodeSem artifacts")
    OUT.mkdir(parents=True,exist_ok=True)
    identity=args.stage+("_"+args.only if args.only else "")
    marker=OUT/(identity+".started.json")
    if marker.exists(): raise FileExistsError("Stage already attempted; preserve result and obtain retry approval")
    write(marker,dict(stage=args.stage,only=args.only,started=time.time(),pid=os.getpid(),driver=ref(Path(__file__))))
    try:
        result=prepare() if args.stage=="prepare" else globals()[args.stage](args.only)
        write(OUT/(identity+".complete.json"),dict(passed=True,finished=time.time()))
    except Exception as e:
        write(OUT/(identity+".failure.json"),dict(error=repr(e),traceback=traceback.format_exc(),automatic_retry=False))
        raise


if __name__=="__main__": main()
