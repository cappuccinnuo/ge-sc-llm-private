"""EP7 execution adaptation of scripts/node_sem/execution.py.
Frozen source SHA256: 6eb1f1ff6768b93fcf8309d730f470d9eb37ffa2bfbd3dcc40d1ac90a5d5c069
Numeric training is routed through the approved registration-only adapter.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
import numpy as np
import torch
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.benchmark_v2.spelling_features import assemble
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.protocol import PROTOCOL_NAME,PROTOCOL_VERSION,PARTS,validate_parts,FORWARD_SCOPE,SCORE_ROLE,SELECTION_ROLE
from scripts.DFG.dfg_v2.experiment.run import _Lock,_move_model
from scripts.DFG.dfg_v2.experiment.init import seeds
from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY,run_preflight,initialize_context,make_observed_resources
from scripts.DFG.dfg_v2.tasks import read_labels
from scripts.DFG.experiments.common import seed_all,tensor_digest,digest,metrics
from scripts.labeling_v2.safe_graph import read_graph
from . import VERSION as EDGESEM_VERSION,validate_profile
from .io import ROOT,read,write,ref,checked
from .runtime import runtime_refs,snapshot_runtime,verify_snapshot
from .model import make_edge_model,validate_registration
from .build_f4 import load_edges,add_edges
from .support import model_support
from .checkpoint import build_binding,validate_binding,freeze_binding,edge_fields,extra_references
from .supervision import make_part
from .input_guard import FitInputGuard
from .trainer import fit
from .feature_views import FEATURE_POLICIES,selected_view,source_feature,validate_view,validate_plan_view

VERSION="edgesem-execution-p2-v1"
ARTIFACT_ROOT=ROOT/"scripts/edge_sem/artifacts"
GPU_LOCK=ROOT/"scripts/DFG/experiments/artifacts/dfg_v2/.training.lock"
TASKS=("reentrancy_node","access_control_node")


def job_id(job):
    return "{task_id}/{fold}/{seed}/{edge_profile}".format(**job)


def job_directory(root,job):
    return Path(root)/"runs"/job["task_id"]/("fold_%d"%job["fold"])/job["edge_profile"]


def _member(plan,job):
    if sum(j==job for j in plan["jobs"])!=1:raise ValueError("Job is not an exact unique plan member")



def validate_environment(cfg):
    import dgl,sklearn,numpy,networkx
    observed=dict(python=sys.version,torch=torch.__version__,dgl=dgl.__version__,
        sklearn=sklearn.__version__,numpy=numpy.__version__,networkx=networkx.__version__)
    if observed!=cfg["environment"]:raise ValueError("Frozen package environment differs")
    return dict(packages=observed,tf32_matmul=bool(torch.backends.cuda.matmul.allow_tf32),
        tf32_cudnn=bool(torch.backends.cudnn.allow_tf32))

def p2_config(original):
    if original["maximum_training_epochs"]!=50 or original["schedule_epochs"]!=50:
        raise ValueError("P2 requires the frozen 50-step schedule")
    result=copy.deepcopy(original)
    result["patience"]=result["maximum_training_epochs"]+1
    return result


def load_checked(reference,map_location="cpu"):
    # Only sealed local initial/checkpoint references created by this executor.
    return torch.load(str(checked(reference)),map_location=map_location)


def assemble_model(job):
    """Sealed original/anonymous S0 tokens; unchanged structure and fresh G3R anchor."""
    cfg=job["config"];spec=validate_profile(job["edge_profile"])
    original=read_graph(checked(job["graph"]));before=graph_fingerprint(original)
    graph=assemble(original,job["feature_view"])
    kwargs=dict(hidden_size=cfg["hidden_size"],layers=cfg["layers"],heads=cfg["heads"],
                node_feature="inside_token",fold=job["fold"],device="cpu")
    refs={}
    if spec["new_relations"]:refs["f4_manifest"]=job["f4_manifest"]
    if spec["edge_features"]!="none":
        refs["attrs_manifest"]=job["attrs_manifest"]
        model=make_edge_model("node",original,job["edge_profile"],
            attributes_manifest=checked(job["attrs_manifest"]),**kwargs)
        # Attribute provenance binds the original graph. Install only the
        # already verified 8H token view on this private model after alignment.
        if model.original_graph_node_ids!=list(graph):raise ValueError("Token view node identity differs")
        for i,n in enumerate(model.original_graph_node_ids):
            if model.nx_graph.nodes[i]["source_file"]!=graph.nodes[n]["source_file"]:
                raise ValueError("Token view file identity differs")
            model.nx_graph.nodes[i]["token"]=copy.deepcopy(graph.nodes[n]["token"])
        from scripts.DFG.dfg_v2.model import _features
        for typ,value in _features(model).items():
            model.symmetrical_global_graph.nodes[typ].data["inp"]=value
    elif spec["placebo"]=="relations":
        model=make_edge_model("node",graph,job["edge_profile"],f4_manifest=checked(job["f4_manifest"]),**kwargs)
    else:
        if spec["new_relations"]:graph=add_edges(graph,load_edges(checked(job["f4_manifest"])))
        model=make_edge_model("node",graph,job["edge_profile"],**kwargs)
    model.edge_input_refs=refs
    validate_registration(model)
    if graph_fingerprint(original)!=before:raise AssertionError("Original graph mutated")
    return model


def _validate_job(job,plan=None,check_initial=True):
    if job["task_id"] not in TASKS or job["granularity"]!="node" or job["seed"]!=1:
        raise ValueError("Unsupported EdgeSem task/seed")
    if type(job["fold"]) is not int or not 0<=job["fold"]<10:raise ValueError("Invalid fold")
    spec=validate_profile(job["edge_profile"])
    if job["seeds"]!=seeds("node",job["fold"],1):raise ValueError("Frozen seeds differ")
    for name in ("graph","folds","labels","label_view","feature_view","feature_npz","source_preparation","initialization"):
        checked(job[name])
    if check_initial:
        checked(job["initial"])
        if not job["initial"].get("state_sha256"):raise ValueError("Missing initial tensor digest")
    if spec["new_relations"]:checked(job["f4_manifest"])
    if spec["edge_features"]!="none":checked(job["attrs_manifest"])
    validate_parts(job["split"],job["graph_files"])
    if job["config"]!=p2_config(job["historical_config"]):raise ValueError("P2 config drift")
    if job["support"]["profile"]!=job["edge_profile"]:raise ValueError("Support profile differs")
    view=validate_view(job,plan)
    if plan is not None:
        source=h8.load(checked(plan["source_h8_plan"]))
        old=dict(task_id=job["task_id"],fold=job["fold"],seed=1,profile="G3R")
        task,info,entry=h8.prepared(source,old)
        feature_view,feature_npz=source_feature(source,job["task_id"],view)
        expected=dict(graph=entry["graph"],folds=task["record"]["folds"],labels=task["record"]["labels"],
            label_view=task["label_view"],feature_view=feature_view,feature_npz=feature_npz,
            source_preparation=source["source_preparation"],split=info["split"],
            graph_files=task["record"]["graph_files"],historical_config=task["config"],seeds=info["seeds"])
        if any(job[k]!=v for k,v in expected.items()):raise ValueError("Historical input identity differs")


def create(batch_dir,matrix):
    batch=Path(batch_dir).resolve()
    if ARTIFACT_ROOT not in batch.parents or batch.exists():raise ValueError("New EdgeSem batch required")
    jobs=copy.deepcopy(matrix["jobs"])
    view=selected_view(matrix)
    if any(selected_view(j)!=view for j in jobs):raise ValueError("Mixed plan token views")
    if not jobs or len({job_id(j) for j in jobs})!=len(jobs):raise ValueError("Empty/duplicate jobs")
    batch.mkdir(parents=True,exist_ok=False)
    runtime,snapshots=snapshot_runtime(batch/"runtime")
    plan=dict(version=VERSION,edgesem_version=EDGESEM_VERSION,protocol=PROTOCOL_NAME,
        protocol_version=PROTOCOL_VERSION,training_protocol="P2",jobs=jobs,
        source_h8_plan=matrix["source_h8_plan"],registration=matrix["registration"],scope=matrix.get("scope","formal"),
        label_policy="L-audit",node_features=FEATURE_POLICIES[view],reducer="mean",layer_impl="shared_projection",
        seeds=[1],resource_policy=LOCAL_DEV_POLICY,runtime=runtime,runtime_snapshots=snapshots,
        authorization=ref(batch/"authorization.json") if (batch/"authorization.json").exists() else None,
        final_server_intent="Final experiments use a server with sufficient VRAM; current constraints are local only.")
    if view!="anonymous":plan["token_view"]=view
    if "view_revision" in matrix:plan["view_revision"]=matrix["view_revision"]
    for field in ("experiment_stage","analysis_role","baseline_plan","prior_main_plan"):
        if field in matrix:plan[field]=matrix[field]
    validate_plan_view(plan)
    authorization=dict(version=VERSION,execution_authorized=False,scope=plan["scope"],jobs=[job_id(j) for j in jobs],
        matrix_sha256=digest(jobs),user_request=None)
    write(batch/"authorization.json",authorization);plan["authorization"]=ref(batch/"authorization.json")
    for job in jobs:_validate_job(job,plan)
    write(batch/"plan.json",plan)
    write(batch/"plan.seal.json",dict(version=VERSION,plan=ref(batch/"plan.json"),matrix_sha256=digest(jobs),jobs=len(jobs)))
    return plan


def load(path,mode="execute"):
    if mode not in ("execute","verify"):raise ValueError("Unknown load mode")
    path=Path(path);plan=read(path);seal=read(path.with_name("plan.seal.json"))
    if (plan.get("version")!=VERSION or plan.get("edgesem_version")!=EDGESEM_VERSION
        or plan.get("training_protocol")!="P2" or seal.get("plan")!=ref(path)
        or seal.get("jobs")!=len(plan["jobs"]) or seal.get("matrix_sha256")!=digest(plan["jobs"])):
        raise ValueError("EdgeSem plan/seal differs")
    if (plan["label_policy"]!="L-audit" or plan["node_features"]!=FEATURE_POLICIES[selected_view(plan)]
        or plan["reducer"]!="mean" or plan["layer_impl"]!="shared_projection" or plan["seeds"]!=[1]
        or plan["resource_policy"]!=LOCAL_DEV_POLICY):raise ValueError("Execution protocol differs")
    if plan.get("protocol")!=PROTOCOL_NAME or plan.get("protocol_version")!=PROTOCOL_VERSION or plan.get("scope") not in ("formal","gpu_probes","norm_pilot"):
        raise ValueError("Protocol or execution scope differs")
    verify_snapshot(plan,mode=="execute")
    auth=read(checked(plan["authorization"]))
    if auth["jobs"]!=[job_id(j) for j in plan["jobs"]] or auth["matrix_sha256"]!=digest(plan["jobs"]):
        raise ValueError("Authorization matrix differs")
    if len({job_id(j) for j in plan["jobs"]})!=len(plan["jobs"]):raise ValueError("Duplicate jobs")
    validate_plan_view(plan)
    for job in plan["jobs"]:_validate_job(job,plan)
    return plan


def authorized(path,plan,scope="formal",archive=False):
    """Later approval is separate, never mutates the unapproved sealed plan."""
    p=Path(path).parent/"execution_authorization.json"
    if not p.is_file():raise PermissionError("EP7 execution is not authorized")
    approval=read(p);seal=read(p.with_suffix(".seal.json"))
    if (seal.get("authorization")!=ref(p) or approval.get("plan")!=ref(path)
        or approval.get("scope")!=scope or approval.get("execution_authorized") is not True
        or not approval.get("user_request") or approval.get("jobs")!=[job_id(j) for j in plan["jobs"]]):
        raise PermissionError("Execution approval identity differs")
    from .protocol_p2 import require_decisions,require_registration_commit
    require_decisions(checked(approval["decisions"]),selected_view(plan),plan.get("experiment_stage"))
    if not archive:require_registration_commit(plan["registration"],approval["registration_commit"])
    if plan["scope"]!=scope:raise PermissionError("Execution scope differs")
    if plan.get("experiment_stage")=="E-A":
        if approval.get("analysis_role")!=plan["analysis_role"]:
            raise PermissionError("E-A approval batch role differs")
        if approval.get("baseline_plan")!=plan["baseline_plan"]:
            raise PermissionError("E-A approval baseline differs")
        checked(plan["baseline_plan"])
        if plan["analysis_role"]=="sensitivity":
            previous=checked(plan["prior_main_plan"])
            prior=read(previous)
            if (prior.get("experiment_stage")!="E-A" or prior.get("analysis_role")!="primary"
                    or prior.get("registration")!=plan["registration"]):
                raise PermissionError("Sensitivity predecessor identity differs")
            completed=previous.parent/"complete.json"
            if not completed.is_file():raise PermissionError("Primary batch must complete first")
            data=read(completed)
            if (data.get("plan")!=plan["prior_main_plan"] or data.get("passed") is not True
                    or len(data.get("receipts",[]))!=60):
                raise PermissionError("Primary batch completion differs")
            if read(completed.with_suffix(".seal.json")).get("complete")!=ref(completed):
                raise ValueError("Primary batch completion seal differs")
            for prior_job, item in zip(prior["jobs"], data["receipts"]):
                receipt_path=checked(item["receipt"])
                receipt=read(receipt_path)
                if (item.get("job")!=prior_job or receipt.get("job")!=prior_job
                        or receipt.get("plan")!=plan["prior_main_plan"]
                        or receipt.get("status")!="complete"
                        or read(receipt_path.with_name("receipt.seal.json")).get("receipt")!=ref(receipt_path)):
                    raise ValueError("Primary result receipt differs")
    prerequisites=approval.get("prerequisites",[])
    required_scopes={"gpu_probes":set(),"norm_pilot":{"gpu_probes"},"formal":{"gpu_probes","norm_pilot"}}[scope]
    if len(prerequisites)!=len(required_scopes) or {read(checked(p)).get("scope") for p in prerequisites}!=required_scopes:
        raise PermissionError("Required EP7 prerequisite plans missing")
    for prerequisite in prerequisites:
        complete=Path(prerequisite["path"]).parent/"complete.json"
        if not complete.is_file():raise PermissionError("Required prior EP7 gate not completed")
        data=read(complete)
        if read(complete.with_suffix(".seal.json")).get("complete")!=ref(complete) or data.get("plan")!=prerequisite or data.get("passed") is not True:
            raise ValueError("Prior EP7 gate failed")
        prior_plan=read(checked(prerequisite))
        if len(data.get("receipts",[]))!=len(prior_plan["jobs"]):raise ValueError("Prior gate receipt count differs")
        from .pilot import verify_one as verify_probe
        for prior_job,r in zip(prior_plan["jobs"],data["receipts"]):
            verify_probe(prerequisite["path"],prior_plan,prior_job,checked(r).parent)
    return ref(p)


def construct(plan,job,device="cpu"):
    _member(plan,job);initial=load_checked(job["initial"])
    if (initial.get("kind")!="untrained_initial" or initial.get("optimizer_steps")!=0
        or any(initial.get(k)!=job[k] for k in ("task_id","fold","seed","edge_profile"))
        or initial.get("fit_seed")!=job["seeds"]["fit"]
        or initial.get("constructor_seed")!=job["seeds"]["constructor"]
        or tensor_digest(initial["state_dict"])!=job["initial"]["state_sha256"]
        or initial.get("state_sha256")!=job["initial"]["state_sha256"]):
        raise ValueError("Initial identity/digest differs")
    model=assemble_model(job);model.load_state_dict(initial["state_dict"],strict=True)
    if tensor_digest(model.state_dict())!=job["initial"]["state_sha256"]:raise ValueError("Reload changed initial")
    if model_support(model,job["split"])!=job["support"]:raise ValueError("Support differs")
    if edge_fields(model)!=job["edge_binding"]:raise ValueError("Prepared EdgeSem identity differs")
    return _move_model(model,device)


def _validate_edgesem_binding(binding,plan,job,config=None):
    cfg=job["config"] if config is None else config
    expected=dict(protocol=PROTOCOL_NAME,protocol_version=PROTOCOL_VERSION,score_role=SCORE_ROLE,
        selection_role=SELECTION_ROLE,forward_scope=FORWARD_SCOPE,training_protocol="P2",
        task_id=job["task_id"],task="node",fold=job["fold"],seed=1,profile="G3R",
        reducer=plan["reducer"],layer_impl=plan["layer_impl"],
        initial_weights_sha256=job["initial"]["sha256"],initial_state_sha256=job["initial"]["state_sha256"],
        support_sha256=digest(job["support"]),effective_config_sha256=digest(cfg),
        initialization=job["initialization"],source_preparation=job["source_preparation"],
        label_policy=plan["label_policy"],label_view=job["label_view"],
        feature_view=job["feature_view"],feature_npz=job["feature_npz"],
        graph=job["graph"],folds=job["folds"],labels=job["labels"],split=job["split"],
        registered_schema=job["support"]["schema"])
    expected.update(job["edge_binding"])
    if any(binding.get(k)!=v for k,v in expected.items()):raise ValueError("EdgeSem binding differs from plan")
    return binding


def binding_parts(plan,job,model,config=None):
    _member(plan,job);cfg=job["config"] if config is None else config
    binding=build_binding(model,task_id=job["task_id"],fold=job["fold"],seed=1,profile="G3R",
        reducer=plan["reducer"],graph_ref=job["graph"],fold_ref=job["folds"],label_ref=job["labels"],
        initial_sha256=job["initial"]["sha256"],config=cfg,split=job["split"],support=job["support"],
        initialization_record=job["initialization"])
    binding.update(initial_state_sha256=job["initial"]["state_sha256"],label_policy="L-audit",
        label_view=job["label_view"],feature_view=job["feature_view"],feature_npz=job["feature_npz"],
        source_preparation=job["source_preparation"],training_protocol="P2")
    _validate_edgesem_binding(binding,plan,job,cfg)
    freeze_binding(model,binding)
    groups=validate_parts(job["split"],job["graph_files"])
    parts={r:make_part(model,"node",groups[r],binding) for r in PARTS}
    return binding,parts

def _successful(folder):
    results = list(Path(folder).glob("attempt_*/receipt.json"))
    if len(results) > 1:
        raise ValueError("Duplicate successful EdgeSem fits")
    return results[0].parent if results else None


def _next_attempt(path, job, folder):
    """A failed attempt cannot restart without a new independently sealed approval."""
    folder = Path(folder)
    prior = sorted(p for p in folder.glob("attempt_*")
                   if p.is_dir() or p.name.endswith((".started.json", ".failure.json")))
    if not prior:
        return folder / "attempt_001"
    approval_path = Path(path).parent / ("retry_" + digest(job) + ".json")
    if not approval_path.is_file():
        raise RuntimeError("Retained failed/incomplete attempt; explicit retry approval required")
    approval = read(approval_path)
    if read(approval_path.with_suffix(".seal.json")).get("approval") != ref(approval_path):
        raise ValueError("Retry approval seal differs")
    if (approval.get("approved") is not True or approval.get("plan") != ref(path)
            or approval.get("job") != job or not approval.get("user_request")
            or approval.get("automatic_retry") is not False
            or approval.get("restart_from_sealed_initial") is not True):
        raise ValueError("Retry approval identity/policy differs")
    name = approval.get("attempt", "")
    if not re.match(r"^attempt_[0-9]{3}$", name):
        raise ValueError("Invalid retry attempt name")
    number = max(int(p.name[8:11]) for p in prior)
    if name != "attempt_%03d" % (number + 1):
        raise ValueError("Retry attempt is not the next retained generation")
    checked(approval["failure"])
    if Path(approval["failure"]["path"]).resolve().parent != folder.resolve():
        raise ValueError("Retry failure belongs to another job")
    return folder / name


def fit_one(path, job):
    plan = load(path)
    _member(plan, job)
    approval = authorized(path,plan)
    folder = job_directory(Path(path).parent, job)
    existing = _successful(folder)
    if existing:
        verify_one(path, plan, job, existing)
        return "reused"
    attempt = _next_attempt(path, job, folder)
    folder.mkdir(parents=True, exist_ok=True)
    start = dict(job=job, plan=ref(path), execution_authorization=approval,
                 runtime=plan["runtime"], started_unix=time.time(), pid=os.getpid(),
                 automatic_retry=False)
    write(attempt.with_suffix(".started.json"), start)
    cfg = job["config"]
    try:
        # Preserve the historical environment and resource gates.
        import dgl, sklearn, numpy, networkx
        environment = dict(python=sys.version, torch=torch.__version__, dgl=dgl.__version__,
            sklearn=sklearn.__version__, numpy=numpy.__version__, networkx=networkx.__version__)
        if environment != cfg["environment"]:
            raise ValueError("Frozen package environment differs")
        pre = run_preflight(job, ref(path)["sha256"], folder, plan["resource_policy"])
        context = initialize_context(pre["baseline"], cfg["device"])
        write(attempt.with_suffix(".context.json"), context)
        resources = make_observed_resources(cfg["device"], pre["baseline"], context,
            attempt.with_suffix(".memory_samples.jsonl"), minimum_free_mib=100,
            policy=plan["resource_policy"], history_path=attempt / "history.jsonl")
        torch.set_num_threads(cfg["threads"])
        with resources:
            model = construct(plan, job, cfg["device"])
            resources.check()
            binding, parts = binding_parts(plan, job, model)
            labels = read_labels(job["labels"])
            seed_all(job["seeds"]["fit"])
            with FitInputGuard(model, binding, parts, labels) as guard:
                result = fit(model, guard.wrap_parts(), job["granularity"], labels, cfg, attempt,
                    binding, model.original_graph_node_ids, job["support"], memory_guard=resources)
                guard.finish()
                write(attempt / "validation_performance.json", guard.summary())
        result["resources"] = dict(resources.summary(), preflight=pre["receipt_ref"],
            resource_policy=plan["resource_policy"], context_ref=ref(attempt.with_suffix(".context.json")),
            training_pid=os.getpid())
        write(attempt / "final_result.json", result)
        write(attempt / "effective_config.json", cfg)
        write(attempt / "schema_support_audit.json", job["support"])
        write(attempt / "initialization_ref.json", job["initial"])
        write(attempt / "receipt.json", dict(version=VERSION, status="complete", job=job, plan=ref(path),
            execution_start=ref(attempt.with_suffix(".started.json")), binding_sha256=digest(binding),
            artifacts={str(p.relative_to(attempt)): ref(p)["sha256"]
                       for p in sorted(attempt.rglob("*")) if p.is_file()}))
        # Seal the receipt separately so irrelevant receipt field edits
        # cannot silently pass read-only verification.
        write(attempt / "receipt.seal.json", dict(
            version=VERSION, receipt=ref(attempt / "receipt.json"), plan=ref(path)))
    except Exception as error:
        write(attempt.with_suffix(".failure.json"), dict(job=job, error=repr(error),
            traceback=traceback.format_exc(), automatic_retry=False, stop_batch=True))
        raise
    verify_one(path, plan, job, attempt)
    return "complete"

def _result_inputs(plan, job, historical):
    if historical:
        task, info, entry = h8.prepared(plan, job)
        return task, info, entry
    task = dict(granularity=job["granularity"], config=job["config"],
        record=dict(labels=job["labels"], folds=job["folds"], graph_files=job["graph_files"]),
        label_view=job["label_view"], feature_view=job["feature_view"], feature_npz=job["feature_npz"])
    info = dict(split=job["split"], initialization=job["initialization"], seeds=job["seeds"])
    entry = dict(graph=job["graph"], initial=job["initial"], support=job["support"])
    return task, info, entry


def _verify_execution_records(path, plan, job, attempt):
    """Authenticate a completed EdgeSem fit without consulting today's code."""
    attempt = Path(attempt)
    authorized(path,plan,archive=True)
    receipt_path = attempt / "receipt.json"
    receipt = read(receipt_path)
    if plan["version"] == VERSION:
        anchor = read(attempt / "receipt.seal.json")
        if (anchor.get("version") != VERSION or anchor.get("plan") != ref(path)
                or anchor.get("receipt") != ref(receipt_path)):
            raise ValueError("EdgeSem receipt seal differs")
    if (receipt.get("version") != plan["version"] or receipt.get("job") != job
            or receipt.get("plan") != ref(path) or receipt.get("status") != "complete"):
        raise ValueError("Receipt identity/version differs")
    start = read(checked(receipt["execution_start"]))
    if (start.get("job") != job or start.get("plan") != ref(path)
            or start.get("execution_authorization") != ref(Path(path).parent/"execution_authorization.json")
            or start.get("runtime") != plan["runtime"]):
        raise ValueError("EdgeSem started runtime/authorization differs")
    # v1's entire recorded runtime (including diagnostics/recon) is compared
    # above, never reduced to the newer RUNTIME_MODULES subset.
    for name, sha in receipt["artifacts"].items():
        target = (attempt / name).resolve()
        if attempt.resolve() not in target.parents:
            raise ValueError("Receipt path escapes fit")
        checked(dict(path=str(target), sha256=sha))
    return dict(current_code_equality="not_required", started_runtime_matches_plan=True)


def _verify_result(path, plan, job, attempt, historical=False):
    """Read-only adaptation of 8H verify_one; every deserialization is SHA guarded."""
    attempt = Path(attempt)
    receipt = read(attempt / "receipt.json")
    if (receipt["job"] != job or receipt["plan"] != ref(path)
            or receipt["status"] != "complete"):
        raise ValueError("Receipt identity differs")
    start = read(checked(receipt["execution_start"]))
    if (start["job"] != job or start["plan"] != ref(path)
            or start["execution_authorization"] != ref(Path(path).parent/"execution_authorization.json")):
        raise ValueError("Start authorization differs")
    if historical:
        h8.verify_start(path, plan, start, attempt / "receipt.json")
        h8.validate_retry_receipt(path, job, attempt)
    else:
        _verify_execution_records(path, plan, job, attempt)
    required = {"best.pt", "last.pt", "best.json", "last.json", "binding.json",
        "final_result.json", "history.jsonl", "inner_val_predictions.json",
        "outer_test_predictions.json", "inner_val_orig_all_predictions.json",
        "outer_test_orig_all_predictions.json", "validation_performance.json",
        "effective_config.json", "schema_support_audit.json", "initialization_ref.json"}
    if not required <= set(receipt["artifacts"]):
        raise ValueError("Missing fit artifacts")
    for name, sha in receipt["artifacts"].items():
        target = (attempt / name).resolve()
        if attempt.resolve() not in target.parents:
            raise ValueError("Receipt path escapes fit")
        checked(dict(path=str(target), sha256=sha))
    task, info, entry = _result_inputs(plan, job, historical)
    binding = read(attempt / "binding.json")
    if (receipt["binding_sha256"] != digest(binding) or binding["protocol"] != PROTOCOL_NAME
            or binding["label_policy"] != plan["label_policy"]
            or binding["label_view"] != task["label_view"]
            or binding["feature_view"] != task["feature_view"]
            or binding["feature_npz"] != task["feature_npz"]
            or binding["graph"] != entry["graph"] or binding["folds"] != task["record"]["folds"]
            or binding["labels"] != task["record"]["labels"] or binding["split"] != info["split"]
            or binding["initial_state_sha256"] != entry["initial"]["state_sha256"]
            or binding["effective_config_sha256"] != digest(task["config"])
            or binding["registered_schema"] != entry["support"]["schema"]):
        raise ValueError("Fit binding differs from sealed execution plan")
    if not historical:
        _validate_edgesem_binding(binding, plan, job)
    for name in ("graph", "folds", "labels", "label_view", "feature_view", "feature_npz"):
        checked(binding[name])
    for reference in extra_references(binding):checked(reference)
    checked(entry["initial"])
    if (read(attempt / "effective_config.json") != task["config"]
            or read(attempt / "schema_support_audit.json") != entry["support"]
            or read(attempt / "initialization_ref.json") != entry["initial"]):
        raise ValueError("Effective inputs differ")
    result = read(attempt / "final_result.json")
    history = [json.loads(x) for x in (attempt / "history.jsonl").read_text().splitlines()]
    if (len(history) != 50
            or [x["epoch"] for x in history] != list(range(len(history)))
            or result["best_epoch"] != min(range(len(history)), key=lambda i: history[i]["inner_val_loss"])):
        raise ValueError("Best/history selection differs")
    if (result["last_epoch"] != len(history) - 1
            or result["outer_supervision_used_in_optimization"] is not False):
        raise ValueError("Training boundary differs")
    if result["checkpoint_roundtrip_exact"] != {
            role: {ck: True for ck in ("best", "last")} for role in ("inner_val", "outer_test")}:
        raise ValueError("Checkpoint reload was not exact")
    for ck in ("best", "last"):
        payload = load_checked(dict(path=str(attempt / (ck + ".pt")),
                                   sha256=receipt["artifacts"][ck + ".pt"]), map_location="cpu")
        if (payload["binding"] != binding
                or tensor_digest(payload["state_dict"]) != payload["state_sha256"]
                or payload["epoch"] != result[ck + "_epoch"]
                or result["checkpoint_sha256"][ck] != receipt["artifacts"][ck + ".pt"]):
            raise ValueError("Checkpoint differs")
        side = read(attempt / (ck + ".json"))
        if any(payload[k] != side[k] for k in ("state_sha256", "binding", "model_input", "epoch", "monitor")):
            raise ValueError("Checkpoint sidecar differs")
        del payload
    if read(attempt / "validation_performance.json")["deep_boundaries"] != [
            "start", "after_training", "after_evaluation"]:
        raise ValueError("Three deep boundaries absent")
    from scripts.DFG.dfg_v2.experiment.local_dev import validate_local_resource_summary
    resources = result["resources"]
    checked(dict(path=resources["raw_samples_path"], sha256=resources["raw_samples_sha256"]))
    pre = read(checked(resources["preflight"]))
    read(checked(resources["context_ref"]))
    if (pre["job"] != job or pre["plan_sha256"] != ref(path)["sha256"]
            or pre["policy"] != plan["resource_policy"] or pre["pid"] != resources["training_pid"]):
        raise ValueError("Fresh-process preflight differs")
    if pre["cuda_initialized_before"] is not False or pre["cuda_initialized_after"] is not False:
        raise ValueError("Preflight occurred after CUDA initialization")
    samples = [json.loads(x) for x in Path(resources["raw_samples_path"]).read_text().splitlines()]
    validate_local_resource_summary(resources, plan["resource_policy"], attempt / "history.jsonl", samples)
    rows = read(checked(task["label_view"]))[job["task_id"]]
    node = task["granularity"] == "node"
    key = lambda x: (x["file"], x["original_graph_node_id"]) if node else x["file"]
    for role in ("inner_val", "outer_test"):
        candidates = [x for x in rows if x["file"] in info["split"][role + "_files"]]
        for aux in (False, True):
            table = {key(x): x for x in candidates if aux or x["L-audit_include"]}
            pred = read(attempt / (role + ("_orig_all" if aux else "") + "_predictions.json"))
            if len(pred) != len(table) or {key(x) for x in pred} != set(table):
                raise ValueError("Prediction identity/population differs")
            field = "orig" if aux else "L-audit_target"
            if any(x["target"] != table[key(x)][field] for x in pred):
                raise ValueError("Prediction truth differs")
            for ck in ("best", "last"):
                observed = metrics([x["target"] for x in pred], [x[ck] for x in pred])
                expected = result["orig_all_auxiliary"][role][ck] if aux else result[role][ck]
                if observed != expected:
                    raise ValueError("Independent metric recalculation differs")
    return dict(job=job, attempt=str(attempt.resolve()),
                audit=dict(passed=True, current_code_equality=(
                    "8H_effective_runtime_required" if historical else "not_required")),
                current_code_equality="not_required", result=result)


def verify_one(path, plan, job, attempt=None):
    _member(plan, job)
    if attempt is None:
        attempt = _successful(job_directory(Path(path).parent, job))
    if attempt is None:
        raise ValueError("No successful EdgeSem attempt")
    return _verify_result(path, plan, job, attempt)


def execute(path, only):
    plan = load(path)
    selected = [j for j in plan["jobs"] if job_id(j) == only]
    if len(selected) != 1:
        raise ValueError("Select exactly one sealed EdgeSem job")
    with _Lock(GPU_LOCK):
        return fit_one(path, selected[0])


def controller(path):
    """One worker per job, in order; never silently restart a failed attempt."""
    plan = load(path)
    authorized(path,plan)
    root = Path(path).parent
    accepted = []
    with _Lock(root / ".controller.lock"):
        for job in plan["jobs"]:
            folder = job_directory(root, job)
            found = _successful(folder)
            if found is None:
                candidate = _next_attempt(path, job, folder)
                log = folder / (candidate.name + ".worker.log")
                folder.mkdir(parents=True, exist_ok=True)
                # Exclusive mode keeps prior failures and their logs intact.
                with log.open("x", encoding="utf8") as stream:
                    subprocess.run([sys.executable, "-B", "-m", "scripts.edge_sem.execution",
                        "worker", "--plan", str(path), "--only", job_id(job)],
                        check=True, stdout=stream, stderr=subprocess.STDOUT, cwd=str(ROOT))
                found = _successful(folder)
            if found is None:
                raise RuntimeError("Worker produced no success receipt")
            verify_one(path, plan, job, found)
            accepted.append(dict(job=job, receipt=ref(found / "receipt.json"), reuse_8h=False))
        complete = root / "complete.json"
        payload = dict(version=VERSION, plan=ref(path), passed=True, receipts=accepted)
        if complete.exists():
            if read(complete) != payload:
                raise ValueError("Existing completion differs")
        else:
            write(complete, payload)
        if plan.get("experiment_stage")=="E-A":
            seal=complete.with_suffix(".seal.json")
            value=dict(complete=ref(complete),plan=ref(path))
            if seal.exists():
                if read(seal)!=value:raise ValueError("Completion seal differs")
            else:write(seal,value)
    return accepted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("worker", "all", "verify"))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--only")
    args = parser.parse_args()
    if args.command == "worker":
        execute(args.plan, args.only)
    elif args.command == "all":
        controller(args.plan)
    else:
        plan = load(args.plan, mode="verify")
        for job in plan["jobs"]:
            verify_one(args.plan, plan, job)
        print(json.dumps(dict(passed=True, jobs=len(plan["jobs"]),
                              current_code_equality="not_required")))


if __name__ == "__main__":
    main()
