"""Prompt 8H sealed benchmark executor. Old protocol delegates to its unchanged CLI."""
import argparse, copy, gc, json, os, subprocess, sys, time, traceback
from pathlib import Path
import torch
from .prepare import read, write, ref, checked
from .spelling_plan import verify_plan as verify_preparation
from .spelling_features import assemble
from .runtime_model import make_model,make_placebo,validate_registration
from .audit_supervision import make_part,bind_rows
from .support import model_support
from .checkpoint import build_binding
from .input_guard import FitInputGuard
from .trainer import fit
from .protocol import PROTOCOL_NAME,PROTOCOL_VERSION,PARTS,validate_parts
from .grouping import validate_splits
from ..experiment.init import initialize_family,seeds,INITIALIZATION_VERSION
from ..experiment.run import _Lock,_move_model,_code_refs,job_id,_job_directory
from ..experiment.preflight import LOCAL_DEV_POLICY,run_preflight,initialize_context,make_observed_resources
from ..tasks import read_labels
from scripts.DFG.experiments.common import seed_all,tensor_digest,digest,metrics
from .acceptance import DEFAULT,ROOT,ART

VERSION="prompt8h-benchmark-execution-v1"

def gate(name):
    p=DEFAULT/"acceptance"/name
    if not p.is_file() or read(p).get("passed") is not True:
        raise ValueError("Mandatory acceptance missing/failed: "+name)
    return ref(p)

def create():
    source=DEFAULT/"authorization.json";auth=read(source)
    oldpath=checked(auth["source_plan"]);verify_preparation(oldpath);old=read(oldpath)
    if auth["label_policy"]!="L-audit" or auth["seeds"]!=[1] or auth["formal_fit_count"]!=170:
        raise ValueError("Execution authorization differs")
    gates={n:gate(n) for n in ("cpu_attempt2/report.json","gpu/report.json","historical_archive.json","real_mask.json","placebo_smoke.json")}
    if (DEFAULT/"plan.json").exists():raise FileExistsError("Do not replace sealed execution plan")
    out=DEFAULT/"prepared";out.mkdir(exist_ok=False)
    plan=dict(version=VERSION,protocol=PROTOCOL_NAME,protocol_version=PROTOCOL_VERSION,
        authorization=ref(source),source_preparation=ref(oldpath),source_seal=auth["source_seal"],
        label_policy="L-audit",feature_policy=old["feature_policy"],resource_policy=LOCAL_DEV_POLICY,
        layer_impl="shared_projection",reducer="mean",seeds=[1],tasks={},jobs=copy.deepcopy(old["jobs"]),
        gates=gates,runtime=_code_refs(),selection_rule=old["selection_rule"],statistics=old["statistics"],
        source_bound_artifacts=old["bound_artifacts"],G0P=old["G0P"],
        execution_policy="serial fresh process; stop on any failed fit; no automatic retry",
        primary_endpoint="L-audit best outer_test HCG node/file; reentrancy_node G3R-G0",
        final_server_intent=auth["final_server_intent"])
    torch.set_num_threads(2)
    for tid,t in old["tasks"].items():
        task=copy.deepcopy(t)
        task["record"]=copy.deepcopy(t["original_record"]);task["record"]["folds"]=t["folds"]
        task["config"]=copy.deepcopy(t["effective_config"]);task["prepared"]={}
        folds=read(checked(t["folds"]));validate_splits(folds,read(checked(t["population"])))
        task["label_view"]=old["bound_artifacts"]["label_views"]
        task["feature_view"]=t["feature_view"]["anonymous"]
        task["feature_npz"]=read(checked(task["feature_view"]))["data"]
        graphs={p:assemble(checked(e["graph"]),task["feature_view"]) for p,e in t["profiles"].items()}
        for split in folds["folds"]:
            fold=split["fold"];sf=seeds(t["granularity"],fold,1)
            folder=out/tid/("fold_"+str(fold));folder.mkdir(parents=True)
            seed_all(sf["constructor"])
            cfg=task["config"]
            anchor=make_model(t["granularity"],graphs["G0"],"G0","cpu",hidden_size=cfg["hidden_size"],layers=cfg["layers"],heads=cfg["heads"],reducer="mean",layer_impl="shared_projection")
            entries,init_records={},{}
            profiles=["G0","G1R","G2R","G3R","G3"]+(["G0P"] if t["granularity"]=="node" else [])
            for profile in profiles:
                if profile=="G0":model=anchor
                elif profile=="G0P":model=make_placebo(anchor,old["G0P"]["schemas"][tid]["target_counts"])
                else:
                    seed_all(sf["constructor"])
                    model=make_model(t["granularity"],graphs[profile],profile,"cpu",
                        hidden_size=cfg["hidden_size"],layers=cfg["layers"],heads=cfg["heads"],reducer="mean",layer_impl="shared_projection")
                if profile!="G0P":
                    record=initialize_family({"G0":anchor} if profile=="G0" else {"G0":anchor,profile:model},sf["constructor"])["profiles"][profile]
                else:
                    record=dict(state_sha256=tensor_digest(model.state_dict()),optimizer_steps=0,
                        common_G0_parameters="exact semantic copy",extras="empty attention/message zero,priority one",
                        target_counts=old["G0P"]["schemas"][tid]["target_counts"])
                state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                payload=dict(kind="untrained_initial",optimizer_steps=0,task_id=tid,fold=fold,seed=1,
                    profile=profile,fit_seed=sf["fit"],constructor_seed=sf["constructor"],
                    initialization_version=INITIALIZATION_VERSION,state_dict=state,state_sha256=tensor_digest(state))
                initial=folder/(profile+"_initial.pt");torch.save(payload,str(initial))
                counts=model_support(model,split)
                bind_rows(model,tid,task["label_view"])
                entries[profile]=dict(graph=t["profiles"]["G0" if profile=="G0P" else profile]["graph"],
                    initial=dict(ref(initial),state_sha256=payload["state_sha256"]),support=counts)
                init_records[profile]=record
                if profile!="G0":del model
                del state,payload
                gc.collect()
            init_path=folder/"initialization.json";write(init_path,dict(version=INITIALIZATION_VERSION,seeds=sf,profiles=init_records))
            info=dict(task_id=tid,fold=fold,seed=1,seeds=sf,split=split,profiles=entries,initialization=ref(init_path))
            path=folder/"manifest.json";write(path,info)
            task["prepared"][str(fold)+"/1"]=ref(path)
            del anchor
            print("prepared",tid,fold,flush=True)
        del graphs
        plan["tasks"][tid]=task
    for j in plan["jobs"]:j["execution_authorized"]=True
    if len(plan["jobs"])!=170 or len({job_id(j) for j in plan["jobs"]})!=170:raise ValueError("Matrix differs")
    if plan["runtime"]!=_code_refs():raise ValueError("Code changed during initialization")
    write(DEFAULT/"plan.json",plan);write(DEFAULT/"plan.seal.json",dict(plan=ref(DEFAULT/"plan.json"),jobs=170))
    return plan

def load(path):
    path=Path(path);plan=read(path)
    if plan.get("protocol")!=PROTOCOL_NAME:raise ValueError("Not a grouped benchmark plan")
    if plan.get("version")!=VERSION or read(path.with_name("plan.seal.json"))["plan"]!=ref(path):
        raise ValueError("Execution plan/seal differs")
    if plan["runtime"]!=_code_refs():raise ValueError("Frozen execution runtime differs")
    auth=read(checked(plan["authorization"]))
    if (auth["source_plan"]!=plan["source_preparation"] or auth["formal_fit_count"]!=len(plan["jobs"])
        or auth["label_policy"]!=plan["label_policy"] or auth["seeds"]!=plan["seeds"]):
        raise ValueError("Plan authorization mismatch")
    for r in plan["gates"].values():
        if not read(checked(r))["passed"]:raise ValueError("Mandatory gate failed")
    return plan

def prepared(plan,job):
    task=plan["tasks"][job["task_id"]]
    info=read(checked(task["prepared"][str(job["fold"])+"/"+str(job["seed"])]))
    entry=info["profiles"][job["profile"]]
    if any(info[k]!=job[k] for k in ("task_id","fold","seed")):raise ValueError("Prepared identity differs")
    return task,info,entry

def construct(plan,job,device="cpu"):
    task,info,entry=prepared(plan,job);cfg=task["config"]
    initial=torch.load(str(checked(entry["initial"])),map_location="cpu")
    if (initial["kind"]!="untrained_initial" or initial["optimizer_steps"]!=0
        or any(initial[k]!=job[k] for k in ("task_id","fold","seed","profile"))
        or initial["fit_seed"]!=info["seeds"]["fit"]
        or initial["state_sha256"]!=entry["initial"]["state_sha256"]
        or tensor_digest(initial["state_dict"])!=initial["state_sha256"]):
        raise ValueError("Initial-state provenance/digest differs")
    seed_all(info["seeds"]["constructor"])
    graph=assemble(checked(entry["graph"]),task["feature_view"])
    base_profile="G0" if job["profile"]=="G0P" else job["profile"]
    model=make_model(task["granularity"],graph,base_profile,"cpu",hidden_size=cfg["hidden_size"],
        layers=cfg["layers"],heads=cfg["heads"],reducer=plan["reducer"],layer_impl=plan["layer_impl"])
    if job["profile"]=="G0P":model=make_placebo(model,plan["G0P"]["schemas"][job["task_id"]]["target_counts"])
    model.load_state_dict(initial["state_dict"],strict=True)
    if tensor_digest(model.state_dict())!=initial["state_sha256"]:raise ValueError("Loaded state differs")
    if model_support(model,info["split"])!=entry["support"]:raise ValueError("Prepared relation support differs")
    del initial,graph
    return _move_model(model,device)

def binding_parts(plan,job,model,config=None):
    task,info,entry=prepared(plan,job);cfg=task["config"] if config is None else config
    binding=build_binding(model,task_id=job["task_id"],fold=job["fold"],seed=job["seed"],
        profile=job["profile"],reducer=plan["reducer"],graph_ref=entry["graph"],
        fold_ref=task["record"]["folds"],label_ref=task["record"]["labels"],
        initial_sha256=entry["initial"]["sha256"],config=cfg,split=info["split"],
        support=entry["support"],initialization_record=info["initialization"])
    binding.update(initial_state_sha256=entry["initial"]["state_sha256"],label_policy=plan["label_policy"],
        label_view=task["label_view"],feature_view=task["feature_view"],feature_npz=task["feature_npz"],
        source_preparation=plan["source_preparation"])
    groups=validate_parts(info["split"],task["record"]["graph_files"])
    parts={r:make_part(model,task["granularity"],groups[r],binding) for r in PARTS}
    return binding,parts

def fit_one(path,job):
    plan=load(path);root=Path(path).parent;folder=_job_directory(root,job)
    existing=list(folder.glob("attempt_*/receipt.json"))
    if existing:
        verify_one(path,plan,job,existing[0].parent);return "reused"
    if list(folder.glob("attempt_*.started.json")):raise RuntimeError("Previous incomplete/failed attempt: explicit user review required")
    folder.mkdir(parents=True,exist_ok=True)
    pre=run_preflight(job,ref(path)["sha256"],folder,plan["resource_policy"])
    attempt=folder/"attempt_001"
    start=dict(job=job,plan=ref(path),execution_authorization=plan["authorization"],
        started_unix=time.time(),pid=os.getpid(),automatic_retry=False)
    write(attempt.with_suffix(".started.json"),start)
    task,info,entry=prepared(plan,job);cfg=task["config"]
    try:
        import dgl,sklearn,numpy,networkx
        env=dict(python=sys.version,torch=torch.__version__,dgl=dgl.__version__,sklearn=sklearn.__version__,numpy=numpy.__version__,networkx=networkx.__version__)
        if env!=cfg["environment"]:raise ValueError("Frozen package environment differs")
        context=initialize_context(pre["baseline"],cfg["device"])
        write(attempt.with_suffix(".context.json"),context)
        resources=make_observed_resources(cfg["device"],pre["baseline"],context,
            attempt.with_suffix(".memory_samples.jsonl"),minimum_free_mib=100,
            policy=plan["resource_policy"],history_path=attempt/"history.jsonl")
        torch.set_num_threads(cfg["threads"])
        with resources:
            model=construct(plan,job,cfg["device"]);resources.check()
            binding,parts=binding_parts(plan,job,model)
            labels=read_labels(task["record"]["labels"])
            seed_all(info["seeds"]["fit"])
            with FitInputGuard(model,binding,parts,labels) as guard:
                result=fit(model,guard.wrap_parts(),task["granularity"],labels,cfg,attempt,
                    binding,model.original_graph_node_ids,entry["support"],memory_guard=resources)
                guard.finish()
                write(attempt/"validation_performance.json",guard.summary())
        result["resources"]=dict(resources.summary(),preflight=pre["receipt_ref"],
            resource_policy=plan["resource_policy"],context_ref=ref(attempt.with_suffix(".context.json")),training_pid=os.getpid())
        # fit wrote its first result before watcher exit. Preserve it and write the
        # final watcher/acceptance record separately rather than silently replacing.
        write(attempt/"final_result.json",result)
        write(attempt/"effective_config.json",cfg);write(attempt/"schema_support_audit.json",entry["support"])
        write(attempt/"initialization_ref.json",entry["initial"])
        write(attempt/"receipt.json",dict(version=VERSION,status="complete",job=job,plan=ref(path),
            execution_start=ref(attempt.with_suffix(".started.json")),binding_sha256=digest(binding),
            artifacts={str(p.relative_to(attempt)):ref(p)["sha256"] for p in sorted(attempt.rglob("*")) if p.is_file()}))
    except Exception as error:
        write(attempt.with_suffix(".failure.json"),dict(job=job,error=repr(error),traceback=traceback.format_exc(),automatic_retry=False,stop_batch=True))
        raise
    verify_one(path,plan,job,attempt)
    return "complete"

def verify_one(path,plan,job,attempt):
    attempt=Path(attempt);receipt=read(attempt/"receipt.json")
    if receipt["job"]!=job or receipt["plan"]!=ref(path) or receipt["status"]!="complete":raise ValueError("Receipt identity differs")
    start=read(checked(receipt["execution_start"]))
    if start["job"]!=job or start["plan"]!=ref(path) or start["execution_authorization"]!=plan["authorization"]:raise ValueError("Start authorization differs")
    required={"best.pt","last.pt","best.json","last.json","binding.json","final_result.json","history.jsonl",
        "inner_val_predictions.json","outer_test_predictions.json","inner_val_orig_all_predictions.json",
        "outer_test_orig_all_predictions.json","validation_performance.json","effective_config.json","schema_support_audit.json","initialization_ref.json"}
    if not required<=set(receipt["artifacts"]):raise ValueError("Missing fit artifacts")
    for name,sha in receipt["artifacts"].items():
        target=(attempt/name).resolve()
        if attempt.resolve() not in target.parents:raise ValueError("Receipt path escapes fit")
        checked(dict(path=str(target),sha256=sha))
    task,info,entry=prepared(plan,job);binding=read(attempt/"binding.json")
    if (receipt["binding_sha256"]!=digest(binding) or binding["protocol"]!=PROTOCOL_NAME
        or binding["label_policy"]!=plan["label_policy"] or binding["label_view"]!=task["label_view"]
        or binding["feature_view"]!=task["feature_view"] or binding["feature_npz"]!=task["feature_npz"]
        or binding["graph"]!=entry["graph"] or binding["folds"]!=task["record"]["folds"]
        or binding["labels"]!=task["record"]["labels"] or binding["split"]!=info["split"]
        or binding["initial_state_sha256"]!=entry["initial"]["state_sha256"]
        or binding["effective_config_sha256"]!=digest(task["config"])
        or binding["registered_schema"]!=entry["support"]["schema"]):
        raise ValueError("Fit binding differs from frozen execution plan")
    for name in ("graph","folds","labels","label_view","feature_view","feature_npz"):checked(binding[name])
    checked(entry["initial"])
    if read(attempt/"effective_config.json")!=task["config"] or read(attempt/"schema_support_audit.json")!=entry["support"] or read(attempt/"initialization_ref.json")!=entry["initial"]:raise ValueError("Effective inputs differ")
    r=read(attempt/"final_result.json");history=[json.loads(x) for x in (attempt/"history.jsonl").read_text().splitlines()]
    if not history or len(history)>50 or [x["epoch"] for x in history]!=list(range(len(history))) or r["best_epoch"]!=min(range(len(history)),key=lambda i:history[i]["inner_val_loss"]):raise ValueError("Best/history selection differs")
    if r["last_epoch"]!=len(history)-1 or r["outer_supervision_used_in_optimization"] is not False:raise ValueError("Training boundary differs")
    if r["checkpoint_roundtrip_exact"]!={role:{ck:True for ck in ("best","last")} for role in ("inner_val","outer_test")}:
        raise ValueError("Checkpoint reload was not exact")
    for ck in ("best","last"):
        payload=torch.load(str(attempt/(ck+".pt")),map_location="cpu")
        if payload["binding"]!=binding or tensor_digest(payload["state_dict"])!=payload["state_sha256"] or payload["epoch"]!=r[ck+"_epoch"] or r["checkpoint_sha256"][ck]!=receipt["artifacts"][ck+".pt"]:raise ValueError("Checkpoint differs")
        side=read(attempt/(ck+".json"))
        if any(payload[k]!=side[k] for k in ("state_sha256","binding","model_input","epoch","monitor")):raise ValueError("Checkpoint sidecar differs")
        del payload
    if read(attempt/"validation_performance.json")["deep_boundaries"]!=["start","after_training","after_evaluation"]:raise ValueError("Three deep boundaries absent")
    from ..experiment.local_dev import validate_local_resource_summary
    resources=r["resources"]
    checked(dict(path=resources["raw_samples_path"],sha256=resources["raw_samples_sha256"]))
    pre=read(checked(resources["preflight"]));read(checked(resources["context_ref"]))
    if pre["job"]!=job or pre["plan_sha256"]!=ref(path)["sha256"] or pre["policy"]!=plan["resource_policy"] or pre["pid"]!=resources["training_pid"]:
        raise ValueError("Fresh-process resource preflight binding differs")
    if pre["cuda_initialized_before"] is not False or pre["cuda_initialized_after"] is not False:
        raise ValueError("Preflight occurred after CUDA initialization")
    samples=[json.loads(x) for x in Path(resources["raw_samples_path"]).read_text().splitlines()]
    validate_local_resource_summary(resources,plan["resource_policy"],attempt/"history.jsonl",samples)
    rows=read(checked(task["label_view"]))[job["task_id"]]
    node=task["granularity"]=="node"
    key=lambda x:(x["file"],x["original_graph_node_id"]) if node else x["file"]
    for role in ("inner_val","outer_test"):
        candidates=[x for x in rows if x["file"] in info["split"][role+"_files"]]
        for aux in (False,True):
            table={key(x):x for x in candidates if aux or x["L-audit_include"]}
            name=role+("_orig_all" if aux else "")+"_predictions.json"
            pred=read(attempt/name)
            if len(pred)!=len(table) or {key(x) for x in pred}!=set(table):raise ValueError("Prediction identity/population differs")
            field="orig" if aux else "L-audit_target"
            if any(x["target"]!=table[key(x)][field] for x in pred):raise ValueError("Prediction truth differs")
            for ck in ("best","last"):
                observed=metrics([x["target"] for x in pred],[x[ck] for x in pred])
                expected=r["orig_all_auxiliary"][role][ck] if aux else r[role][ck]
                if observed!=expected:raise ValueError("Independent metric recalculation differs")
    return dict(job=job,attempt=str(attempt.resolve()),audit=dict(passed=True),result=r)

def execute(path,only):
    raw=read(path)
    if raw.get("protocol")=="dfg-v2-nested":
        from ..experiment.run import execute as old_execute
        return old_execute(path,only=only)
    plan=load(path);matches=[j for j in plan["jobs"] if job_id(j)==only]
    if len(matches)!=1:raise ValueError("Select exactly one frozen job")
    with _Lock(ROOT/"scripts/DFG/experiments/artifacts/dfg_v2/.execution.lock"):
        return fit_one(path,matches[0])

def controller(path,pilots=False):
    from ..experiment.acceptance_cache import create_cache,verify_cache
    plan=load(path);root=Path(path).parent
    chosen=[j for j in plan["jobs"] if
        (j["task_id"],j["fold"],j["profile"]) in (("reentrancy_contract",0,"G0"),("reentrancy_node",0,"G3R"))] if pilots else plan["jobs"]
    if not pilots:gate("pilots.json")
    generation=root/("cache_"+str(time.time_ns()));cache={}
    with _Lock(root/".controller.lock"):
        for j in chosen:
            # A retained failed/incomplete fit stops the whole batch.
            for prior in plan["jobs"]:
                folder=_job_directory(root,prior)
                if list(folder.glob("attempt_*.started.json")) and not list(folder.glob("attempt_*/receipt.json")):
                    raise RuntimeError("Prior incomplete/failed fit: "+job_id(prior))
            folder=_job_directory(root,j);found=list(folder.glob("attempt_*/receipt.json"))
            if len(found)>1:raise ValueError("Duplicate successful fit")
            if not found:
                log=folder.parent/(j["profile"]+"_worker.log")
                log.parent.mkdir(parents=True,exist_ok=True)
                if log.exists():raise FileExistsError("Retained worker log without accepted fit")
                cmd=[sys.executable,"-B","-m","scripts.DFG.dfg_v2.benchmark_v2.execution","worker","--plan",str(path),"--only",job_id(j)]
                with log.open("w") as h:
                    subprocess.run(cmd,check=True,stdout=h,stderr=subprocess.STDOUT)
                found=list(folder.glob("attempt_*/receipt.json"))
            if len(found)!=1:raise ValueError("Worker did not produce one success receipt")
            attempt=found[0].parent
            task,info,entry=prepared(plan,j)
            full=lambda j=j,attempt=attempt:verify_one(path,plan,j,attempt)
            cache[job_id(j)]=create_cache(generation,path,j,attempt,full,VERSION,
                extra_refs=[task["label_view"],task["feature_view"],task["feature_npz"],plan["authorization"]])
            # Check the previous successes cheaply; no F1 is printed or selected.
            for prior_id,anchor in cache.items():
                prior=next(x for x in chosen if job_id(x)==prior_id)
                prior_attempt=_job_directory(root,prior)/"attempt_001"
                verify_cache(anchor,expected_seal_sha=anchor["sha256"],plan_path=path,job=prior,attempt=prior_attempt,
                    full_verify=lambda prior=prior,prior_attempt=prior_attempt:verify_one(path,plan,prior,prior_attempt),
                    acceptance_version=VERSION)
            print("accepted {}/{} {}".format(len(cache),len(chosen),job_id(j)),flush=True)
    if pilots:
        write(root/"acceptance/pilots.json",dict(passed=True,formal_fits=2,reused_in_full_matrix=True,receipts={job_id(j):ref(_job_directory(root,j)/"attempt_001/receipt.json") for j in chosen}))
    else:
        full=[verify_one(path,plan,j,_job_directory(root,j)/"attempt_001") for j in plan["jobs"]]
        write(root/"complete.json",dict(passed=True,formal_fits=len(full),receipts=[ref(Path(x["attempt"])/"receipt.json") for x in full]))
    return True

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=["prepare","worker","pilots","all","verify"])
    p.add_argument("--plan",default=str(DEFAULT/"plan.json"));p.add_argument("--only");a=p.parse_args()
    if a.command=="prepare":create()
    elif a.command=="worker":execute(a.plan,a.only)
    elif a.command in ("pilots","all"):controller(Path(a.plan),a.command=="pilots")
    elif a.command=="verify":
        plan=load(a.plan)
        for j in plan["jobs"]:verify_one(a.plan,plan,j,_job_directory(Path(a.plan).parent,j)/"attempt_001")
if __name__=="__main__":main()
