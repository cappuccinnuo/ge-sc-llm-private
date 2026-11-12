"""EP8 single entry point: prepare, seal, authorize, run, verify, analyze.

The existing EdgeSem execution.controller/worker/trainer remain the only fit
path. No implicit execution approval, no retry, no copied scoring algorithm.
"""
import argparse
import copy
from datetime import datetime, timezone
import gc
import hashlib
from pathlib import Path
import subprocess
import sys
import time
import traceback

import torch
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.experiment.run import _code_refs
from scripts.DFG.experiments.common import tensor_digest
from .. import execution as ex
from ..io import ROOT, ref, checked, read, write
from ..checkpoint import edge_fields
from ..feature_views import source_feature
from ..protocol_p2 import EA_D1, DECISIONS, require_registration_commit
from ..analysis_ea import PROFILES, score, summarize, preparation_index

DEFAULT_ROOT = ROOT/"scripts/edge_sem/artifacts/ep8_v1"
EP7 = ROOT/"scripts/edge_sem/artifacts/ep7_original_v1"
ANON_EP7 = ROOT/"scripts/edge_sem/artifacts/ep7_v1"
DOCS = ("HANDOVER.md","docs/training_changes_2026-10-07.md","scripts/edge_sem/PROGRESS.md")


def sealed_json(path, key):
    path=Path(path)
    if read(path.with_suffix(".seal.json")).get(key)!=ref(path):
        raise ValueError("Seal differs: "+str(path))
    return read(path)


def frozen(root):
    before=read(Path(root)/"before.json")
    for row in before["frozen_code"]+before["prior_artifacts"]:
        checked(row)
    for row in before["edge_sources"]:
        checked(row["snapshot"])
    for name,row in before["documents"].items():
        data=(ROOT/name).read_bytes()[:row["bytes"]]
        if hashlib.sha256(data).hexdigest()!=row["sha256"]:
            raise ValueError("Historical document prefix changed")
    if _code_refs()!=read(EP7/"before.json")["dfg_code_refs"]:
        raise ValueError("Frozen DFG runtime list changed")
    return dict(passed=True,frozen_sources=len(before["frozen_code"]),
                prior_files=len(before["prior_artifacts"]),
                document_prefixes_preserved=True,dfg_code_refs_unchanged=True)


def source_index():
    path=ANON_EP7/"preparation/index.json"
    data=sealed_json(path,"index")
    for row in data["jobs"]:
        if read(checked(row["record"]))!=row["job"]:
            raise ValueError("EP7 zero-step index record differs")
        checked(row["job"]["initial"])
    return data


def register(root):
    root=Path(root)
    before=read(root/"before.json")
    checked(before["prompt"])
    old=source_index()
    source=h8.load(checked(old["source_h8_plan"]))
    preparation=read(checked(source["source_preparation"]))
    # These paths are specified by EP8 or resolved from sealed indexes.
    analysis_inputs=dict(
        node_diagnostic_views=preparation["bound_artifacts"]["node_diagnostic_views"],
        node_label_audit=preparation["bound_artifacts"]["node_label_audit"],
        persistent_cases=ref(ROOT/"scripts/node_sem/artifacts/summary_NS_v1/cases_attempt2/persistent_cases.json"),
        attrs={t:next(j["job"]["attrs_manifest"] for j in old["jobs"] if j["job"]["task_id"]==t)
               for t in ex.TASKS})
    for key,value in analysis_inputs.items():
        if key!="attrs":checked(value)
    decisions=dict(date=datetime.now(timezone.utc).isoformat(),experiment_stage="E-A",
        user_request="Implement EP8 from the updated user-supplied PROMPTS.md r16",
        choice_verbatim="Original + anonymized check",
        choice_source=dict(document=before["prompt"],section="4.10.0; r16 records user choice on 2026-11-11"),
        previous_user_decision=ref(EP7/"user_decision.json"),
        implementation_approval=dict(question_id="call_068df1e5a5b44c43930a9e7fb1018a34",
            answer="同意显式区分主批与敏感性批（推荐）",
            scope="Explicit E-A batch roles; preserve legacy EP7 records and validation"),
        decisions={k:dict(status="confirmed",value=EA_D1 if k=="D1" else v) for k,v in DECISIONS.items()},
        training_execution_authorized=False)
    write(root/"decisions.json",decisions)
    write(root/"decisions.seal.json",dict(decisions=ref(root/"decisions.json")))
    reg=copy.deepcopy(read(EP7/"protocol_p2/registration.json"))
    for k in ("ep7_formal_fits","view_revision","gpu_probe","norm_pilot"):
        reg.pop(k,None)
    reg.update(version="edgesem-E-A-registration-r16-v1",experiment_stage="E-A",
        prompt=before["prompt"],previous_registration=ref(EP7/"protocol_p2/registration.json"),
        decisions=ref(root/"decisions.json"),
        batches={
            "primary":dict(view="original",profiles=list(PROFILES[1:]),fits=60,holm_member=True,
                           baseline=dict(plan=ref(EP7/"formal/plan.json"),fits=20,retrain=False)),
            "sensitivity":dict(view="anonymous",profiles=list(PROFILES),fits=80,holm_member=False,
                               interpretation="descriptive sensitivity; not a second primary endpoint")},
        order=["primary","sensitivity"],analysis_inputs=analysis_inputs,
        initialization_pairing="Same task/fold/profile across views references one identical zero-step file",
        placebo_seed="constructor seed; frozen G4R-P file/type/degree-preserving algorithm",
        checkpoints=dict(primary="best",auxiliary="last"),
        rules=dict(lexical="Reuse frozen original-name lexical_prediction, on the same L-audit identities in both views; audit comparator, not anonymous-input predictor",
                   guard="State-write source without caller_identity GUARDS incoming; exclude unknown guard targets",
                   cross="State-write node with incoming DATA_DEF_USE bit21; unverified required CFG input excluded",
                   unknown="Report excluded node counts; zero unknown never asserted as verified absence"),
        error_reduction="100*(baseline errors-current errors)/baseline errors; null when baseline has zero errors",
        required_reports=reg["required_reports"]+["zero-difference folds","relative error reductions",
            "pooled counts by frozen 8C strata","Wilson precision/recall intervals",
            "frozen lexical rule in both strata","original/anonymous side-by-side raw p values"],
        execution_authorized=False,new_formal_fits=140,
        no_automatic_EP9=True,
        final_server_intent="Final experiments will use a server with sufficient VRAM; current limitation is this local computer.")
    write(root/"protocol_p2/registration.json",reg)
    write(root/"protocol_p2/registration.seal.json",
          dict(registration=ref(root/"protocol_p2/registration.json")))
    print("EP8 registered: original 60 + anonymous 80; training not authorized",flush=True)


def archive_baseline(root):
    dest=Path(root)/"baseline_verification"
    path=EP7/"formal/plan.json"
    if (dest/"verification.json").exists():
        value=sealed_json(dest/"verification.json","verification")
        if value.get("passed") is not True or value.get("plan")!=ref(path) or value.get("verified_fits")!=20:
            raise ValueError("Retained baseline verification differs")
        for item in value["receipts"]:
            checked(item["receipt"]);checked(item["initial"])
        frozen(root)
        return value
    dest.mkdir(exist_ok=False)
    plan=ex.load(path,mode="verify")
    if len(plan["jobs"])!=20 or any(j["edge_profile"]!="G3R" for j in plan["jobs"]):
        raise ValueError("Historical original baseline differs")
    rows=[]
    for j in plan["jobs"]:
        data=ex.verify_one(path,plan,j)
        preds=read(Path(data["attempt"])/"outer_test_predictions.json")
        for ck in ("best","last"):
            observed=score(preds,ck)
            expected=data["result"]["outer_test"][ck]
            if observed["tn_fp_fn_tp"]!=expected["tn_fp_fn_tp"] or any(
                abs(observed[k]-expected[k])>1e-10 for k in ("buggy_f1","macro_f1","precision","recall")):
                raise ValueError("Frozen scorer vs EP7 independent metric mismatch")
        rows.append(dict(job_id=ex.job_id(j),receipt=ref(Path(data["attempt"])/"receipt.json"),
                         initial=j["initial"],checkpoints_verified=True,predictions_verified=True))
        print("EP8 archived baseline",ex.job_id(j),flush=True)
    value=dict(passed=True,plan=ref(path),receipts=rows,verified_fits=20,training_executed=False,
        old_runtime="Exact sealed source snapshots checked; current EdgeSem code equality not required",
        current_frozen=frozen(root))
    write(dest/"verification.json",value)
    write(dest/"verification.seal.json",dict(verification=ref(dest/"verification.json")))
    return value


def topology_equal(a,b):
    if a.original_graph_node_ids!=b.original_graph_node_ids:
        raise ValueError("Cross-view node identity/order differs")
    x,y=a.symmetrical_global_graph,b.symmetrical_global_graph
    if x.canonical_etypes!=y.canonical_etypes or x.ntypes!=y.ntypes:
        raise ValueError("Cross-view schema differs")
    for c in x.canonical_etypes:
        if any(not torch.equal(p,q) for p,q in zip(x.edges(etype=c),y.edges(etype=c))):
            raise ValueError("Cross-view edge order/endpoints differ")


def store_job(dest,job,model,initialization):
    dest.mkdir(parents=True,exist_ok=False)
    write(dest/"initialization.json",initialization)
    job["initialization"]=ref(dest/"initialization.json")
    if model is not None:
        job["support"]=ex.model_support(model,job["split"])
        job["edge_binding"]=edge_fields(model)
    ex._validate_job(job)
    write(dest/"job.json",job)
    return dict(job=job,record=ref(dest/"job.json"))



def _zero_state(job, payload):
    if (payload.get("kind")!="untrained_initial" or payload.get("optimizer_steps")!=0
            or any(payload.get(k)!=job[k] for k in ("task_id","fold","seed","edge_profile"))
            or payload.get("fit_seed")!=job["seeds"]["fit"]
            or payload.get("constructor_seed")!=job["seeds"]["constructor"]
            or tensor_digest(payload["state_dict"])!=job["initial"]["state_sha256"]
            or payload.get("state_sha256")!=job["initial"]["state_sha256"]):
        raise ValueError("Prepared zero-step identity/digest differs")


def install_untrained_view(model, job):
    """Approved CPU preparation shortcut; formal execution never calls this."""
    from scripts.DFG.dfg_v2.model import _features
    if (any(p.device.type!="cpu" or p.grad is not None for p in model.parameters())
            or any(getattr(model,n,0)!=0 for n in
                   ("optimizer_steps","_dfg_optimizer_steps","edge_optimizer_steps"))):
        raise ValueError("View installation requires an untrained CPU model")
    if (model.edge_profile!=job["edge_profile"] or model.edge_seeds!=job["seeds"]
            or job.get("token_view")!="anonymous"):
        raise ValueError("Prepared model/view identity differs")
    before=ex.graph_fingerprint(model.nx_graph)
    state_sha=tensor_digest(model.state_dict())
    original=ex.read_graph(checked(job["graph"]))
    original_sha=ex.graph_fingerprint(original)
    graph=ex.assemble(original,job["feature_view"])
    if model.original_graph_node_ids!=list(graph):
        raise ValueError("View node identity/order differs")
    result=copy.deepcopy(model)
    for i,n in enumerate(result.original_graph_node_ids):
        if result.nx_graph.nodes[i]["source_file"]!=graph.nodes[n]["source_file"]:
            raise ValueError("View source identity differs")
        result.nx_graph.nodes[i]["token"]=copy.deepcopy(graph.nodes[n]["token"])
    for typ,value in _features(result).items():
        result.symmetrical_global_graph.nodes[typ].data["inp"]=value
    if result.edge_profile=="G4R-P":
        if list(result.edge_placebo_source)!=list(graph):
            raise ValueError("Placebo source node order differs")
        for n in graph:
            result.edge_placebo_source.nodes[n]["token"]=copy.deepcopy(graph.nodes[n]["token"])
        result.edge_placebo_binding["source_fingerprint"]=ex.graph_fingerprint(result.edge_placebo_source)
    ex.validate_registration(result)
    topology_equal(model,result)
    if (tensor_digest(result.state_dict())!=state_sha
            or tensor_digest(model.state_dict())!=state_sha
            or ex.graph_fingerprint(model.nx_graph)!=before
            or ex.graph_fingerprint(original)!=original_sha):
        raise ValueError("View installation changed parameters or source model")
    return result


def identical_assembly(fast, full, split):
    """Prove the shortcut against the unchanged full assembly on real inputs."""
    topology_equal(fast,full)
    a,b=fast.state_dict(),full.state_dict()
    if list(a)!=list(b) or any(a[k].dtype!=b[k].dtype or not torch.equal(a[k],b[k]) for k in a):
        raise ValueError("Fast/full parameter tensors differ")
    x,y=fast.symmetrical_global_graph,full.symmetrical_global_graph
    for typ in x.ntypes:
        da,db=x.nodes[typ].data,y.nodes[typ].data
        if set(da)!=set(db) or any(not torch.equal(da[k],db[k]) for k in da):
            raise ValueError("Fast/full node tensors differ")
    for typ in x.canonical_etypes:
        da,db=x.edges[typ].data,y.edges[typ].data
        if set(da)!=set(db) or any(not torch.equal(da[k],db[k]) for k in da):
            raise ValueError("Fast/full edge tensors differ")
    if (ex.graph_fingerprint(fast.nx_graph)!=ex.graph_fingerprint(full.nx_graph)
            or edge_fields(fast)!=edge_fields(full)
            or ex.model_support(fast,split)!=ex.model_support(full,split)):
        raise ValueError("Fast/full graph, binding or support differs")
    return dict(parameters_bitwise_equal=True,node_tensors_bitwise_equal=True,
                edge_tensors_bitwise_equal=True,graph_fingerprint_equal=True,
                binding_equal=True,support_equal=True,state_sha256=tensor_digest(a))


def retained_jobs(root, orig, source):
    """Only complete, identity-checked old records may be referenced."""
    result={}
    for path in sorted((Path(root)/"preparation").rglob("job.json")):
        job=read(path);ex._validate_job(job)
        template=orig[(job["task_id"],job["fold"],"G3R")]
        changed={"edge_profile","initial","initialization","support","edge_binding",
                 "token_view","feature_view","feature_npz"}
        if set(job)!=set(template) or any(job[k]!=template[k] for k in template if k not in changed):
            raise ValueError("Retained prepared job changed frozen inputs")
        expected=source_feature(source,job["task_id"],job["token_view"])
        if (job["feature_view"],job["feature_npz"])!=expected:
            raise ValueError("Retained feature view differs")
        payload=ex.load_checked(job["initial"]);_zero_state(job,payload)
        key=(job["task_id"],job["fold"],job["edge_profile"],job["token_view"])
        if key in result:raise ValueError("Duplicate retained job")
        result[key]=dict(job=job,record=ref(path))
    return result


def prepare(root, preparation_name="preparation"):
    root=Path(root)
    if preparation_name not in ("preparation","preparation_attempt2"):
        raise ValueError("Unregistered preparation attempt")
    revised=preparation_name=="preparation_attempt2"
    approval=None
    if revised:
        approval=root/"preparation_revision_v2/approval.json"
        record=read(approval)
        if (record.get("new_preparation")!=preparation_name
                or record.get("user_question_id")!="call_545e729cd68640a39272d166dc807d0e"
                or record.get("formal_training_unchanged") is not True):
            raise PermissionError("Preparation optimization approval differs")
    reg=sealed_json(root/"protocol_p2/registration.json","registration")
    folder=root/preparation_name
    folder.mkdir(exist_ok=False)
    jobs={"primary":[],"sensitivity":[]};proof=[];generated=0;fast_proofs={}
    start=time.monotonic()
    try:
        archive=archive_baseline(root)
        old=source_index()
        source=h8.load(checked(old["source_h8_plan"]))
        prior={(x["job"]["task_id"],x["job"]["fold"],x["job"]["edge_profile"]):x["job"] for x in old["jobs"]}
        original_index=sealed_json(EP7/"preparation/index.json","index")
        orig={(x["job"]["task_id"],x["job"]["fold"],x["job"]["edge_profile"]):x["job"] for x in original_index["jobs"]}
        retained=retained_jobs(root,orig,source) if revised else {}
        if revised:
            write(folder/"retained_records.json",dict(records=list(retained.values()),
                source_snapshot=ref(root/"preparation_revision_v2/ep8_run.py.before.txt"),
                approval=ref(approval),old_directory_preserved=True))
        for task_id in ex.TASKS:
            for fold in range(10):
                for profile in PROFILES:
                    key=(task_id,fold,profile)
                    retained_original=retained.get(key+("original",))
                    retained_anonymous=retained.get(key+("anonymous",))
                    if profile=="G3R":
                        if retained_anonymous:
                            jobs["sensitivity"].append(retained_anonymous)
                            proof.append(dict(task_id=task_id,fold=fold,profile=profile,
                                initial=retained_anonymous["job"]["initial"],reused_preparation=retained_anonymous["record"]))
                            continue
                        job=copy.deepcopy(prior[key]);job["token_view"]="anonymous"
                        if job["initial"]!=orig[key]["initial"]:
                            raise ValueError("EP7 view-paired G3R initial reference differs")
                        payload=ex.load_checked(job["initial"]);_zero_state(job,payload)
                        init=dict(kind="reuse_EP7_unexecuted_anonymous_G3R_zero_step",optimizer_steps=0,
                            initial=job["initial"],previous_initialization=job["initialization"],
                            parameter_count=sum(v.numel() for v in payload["state_dict"].values()),
                            EP7_view_proof=ref(EP7/"preparation/index.json"))
                        dest=folder/"anonymous"/task_id/("fold_%d"%fold)/profile
                        jobs["sensitivity"].append(store_job(dest,job,None,init))
                        proof.append(dict(task_id=task_id,fold=fold,profile=profile,
                            initial=job["initial"],proof_source="EP7 all-fold bitwise view proof",fresh_weight_file=False))
                        del payload
                        continue
                    if retained_original and retained_anonymous:
                        a,b=retained_original["job"],retained_anonymous["job"]
                        if a["initial"]!=b["initial"] or a["support"]!=b["support"]:
                            raise ValueError("Retained view pair differs")
                        jobs["primary"].append(retained_original);jobs["sensitivity"].append(retained_anonymous)
                        proof.append(dict(task_id=task_id,fold=fold,profile=profile,
                            initial=a["initial"],cross_view_fresh_parameters_bitwise_equal=True,
                            reused_preparation=[retained_original["record"],retained_anonymous["record"]],
                            proof_source=ref(root/"preparation_revision_v2/ep8_run.py.before.txt")))
                        print("EP8 reused completed pair",task_id,fold,profile,flush=True)
                        continue
                    original=copy.deepcopy(orig[(task_id,fold,"G3R")]);original["edge_profile"]=profile
                    model=ex.assemble_model(original)
                    state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                    sha=tensor_digest(state)
                    if retained_original or key in prior:
                        initial=(retained_original["job"] if retained_original else prior[key])["initial"]
                        payload=ex.load_checked(initial)
                        if tensor_digest(payload["state_dict"])!=sha or initial["state_sha256"]!=sha:
                            raise ValueError("Fresh derived model differs from retained zero-step state")
                    else:
                        weights=folder/"weights"/task_id/("fold_%d"%fold)/profile
                        weights.mkdir(parents=True,exist_ok=False)
                        payload=dict(kind="untrained_initial",optimizer_steps=0,task_id=task_id,
                            fold=fold,seed=1,edge_profile=profile,fit_seed=original["seeds"]["fit"],
                            constructor_seed=original["seeds"]["constructor"],state_dict=state,state_sha256=sha)
                        torch.save(payload,str(weights/"initial.pt"))
                        initial=dict(ref(weights/"initial.pt"),state_sha256=sha);generated+=1
                    original["initial"]=initial
                    check=ex.load_checked(initial);_zero_state(original,check)
                    model.load_state_dict(check["state_dict"],strict=True)
                    if tensor_digest(model.state_dict())!=sha:raise ValueError("Strict initial reload differs")
                    init=dict(kind="fresh_G3R_anchor_semantic_copy",optimizer_steps=0,
                        seeds=original["seeds"],initial=initial,shared_copy=model.edge_initialization,
                        parameter_count=sum(v.numel() for v in state.values()),
                        reused_EP7_initial=key in prior,source_job=ref(EP7/"preparation/index.json"))
                    item=store_job(folder/"original"/task_id/("fold_%d"%fold)/profile,original,model,init)
                    jobs["primary"].append(item)
                    anonymous=copy.deepcopy(original);anonymous["token_view"]="anonymous"
                    anonymous["feature_view"],anonymous["feature_npz"]=source_feature(source,task_id,"anonymous")
                    if revised:
                        paired_model=install_untrained_view(model,anonymous)
                        proof_key=(task_id,profile)
                        if proof_key not in fast_proofs:
                            full_model=ex.assemble_model(anonymous)
                            evidence=identical_assembly(paired_model,full_model,anonymous["split"])
                            evidence.update(task_id=task_id,profile=profile,fold=fold,approval=ref(approval),
                                            full_assembly_unchanged=True,zero_optimizer_steps=True)
                            p=folder/"equivalence"/(task_id+"__"+profile+".json")
                            write(p,evidence);fast_proofs[proof_key]=ref(p)
                            del full_model;gc.collect()
                            print("EP8 fast/full proof passed",task_id,profile,fold,flush=True)
                    else:
                        paired_model=ex.assemble_model(anonymous)
                    if tensor_digest(paired_model.state_dict())!=sha:
                        raise ValueError("Cross-view parameters are not bitwise equal")
                    topology_equal(model,paired_model)
                    anonymous["initial"]=initial
                    item=store_job(folder/"anonymous"/task_id/("fold_%d"%fold)/profile,anonymous,paired_model,
                        dict(init,kind="view_pair_reusing_same_zero_step",paired_initialization=original["initialization"],
                             view_assembly_proof=fast_proofs.get((task_id,profile))))
                    jobs["sensitivity"].append(item)
                    if original["support"]!=anonymous["support"]:raise ValueError("Cross-view support differs")
                    if profile=="G4R-P" and anonymous["edge_binding"]["edge_placebo_binding"]["audit"]["seed"]!=anonymous["seeds"]["constructor"]:
                        raise ValueError("Placebo seed differs from constructor")
                    proof.append(dict(task_id=task_id,fold=fold,profile=profile,initial=initial,
                        cross_view_parameters_bitwise_equal=True,same_edges_and_schema=True,strict_reload_exact=True,
                        full_assembly_proof=fast_proofs.get((task_id,profile)),
                        placebo_source_fingerprint_view_specific=profile=="G4R-P"))
                    print("EP8 prepared paired",task_id,fold,profile,flush=True)
                    del model,paired_model,state,payload,check;gc.collect()
        initial_paths={i["job"]["initial"]["path"] for group in jobs.values() for i in group}
        prior_paths={j["initial"]["path"] for j in prior.values()}
        if ([len(jobs[k]) for k in ("primary","sensitivity")]!=[60,80]
                or len(initial_paths)!=80 or len(initial_paths-prior_paths)!=56
                or (revised and len(fast_proofs)!=6)):
            raise ValueError("EP8 preparation matrix/weight/proof count differs")
        primary={(i["job"]["task_id"],i["job"]["fold"],i["job"]["edge_profile"]):i["job"] for i in jobs["primary"]}
        for task_id in ex.TASKS:
            for fold in range(10):
                if primary[(task_id,fold,"G4R")]["initial"]["state_sha256"]!=primary[(task_id,fold,"G4R-P")]["initial"]["state_sha256"]:
                    raise ValueError("G4R/placebo initial parameters differ")
        if torch.cuda.is_initialized():raise ValueError("CPU preparation initialized CUDA")
        value=dict(jobs=jobs,proof=proof,source_h8_plan=old["source_h8_plan"],
            baseline_plan=ref(EP7/"formal/plan.json"),baseline_verification=ref(root/"baseline_verification/verification.json"),
            registration=ref(root/"protocol_p2/registration.json"),analysis_inputs=reg["analysis_inputs"],
            new_weight_files=56,created_this_attempt=generated,retained_records=len(retained),
            preparation_approval=ref(approval) if approval else None,fast_full_equivalence=list(fast_proofs.values()),
            optimizer_steps=0,cuda_initialized=False,seconds=time.monotonic()-start,
            implementation={name:ref(ROOT/"scripts/edge_sem"/name) for name in ("analysis_ea.py","recon/ep8_run.py")})
        write(folder/"index.json",value);write(folder/"index.seal.json",dict(index=ref(folder/"index.json")))
        write(root/"preparation_index.json",dict(index=ref(folder/"index.json")))
        write(root/"preparation_index.seal.json",dict(pointer=ref(root/"preparation_index.json")))
        print("EP8 CPU preparation complete",time.monotonic()-start,flush=True)
    except Exception as error:
        write(folder/"failure.json",dict(error=repr(error),traceback=traceback.format_exc(),
            completed_primary=len(jobs["primary"]),completed_sensitivity=len(jobs["sensitivity"]),automatic_retry=False))
        raise


def seal(root):
    root=Path(root)
    _,index=preparation_index(root)
    for role in ("primary","sensitivity"):
        items=index["jobs"][role]
        for item in items:
            if read(checked(item["record"]))!=item["job"]:
                raise ValueError("Prepared job record differs")
        matrix=dict(jobs=[i["job"] for i in items],source_h8_plan=index["source_h8_plan"],
            registration=index["registration"],scope="formal",experiment_stage="E-A",analysis_role=role,
            token_view="original" if role=="primary" else "anonymous",baseline_plan=index["baseline_plan"])
        if role=="sensitivity":matrix["prior_main_plan"]=ref(root/"primary/plan.json")
        ex.create(root/role,matrix)
        ex.load(root/role/"plan.json")
        print("EP8 sealed",role,len(items),"execution_authorized=False",flush=True)


def authorize(root,commit,request_file):
    root=Path(root)
    request=read(request_file)
    if (request.get("execution_authorized") is not True or not request.get("user_request")
            or request.get("primary_fits")!=60 or request.get("sensitivity_fits")!=80
            or request.get("order")!=["primary","sensitivity"] or request.get("automatic_retry") is not False):
        raise PermissionError("Explicit EP8 60+80 serial execution approval required")
    acceptance=sealed_json(root/"cpu_acceptance.json","acceptance")
    if acceptance.get("passed") is not True:
        raise ValueError("CPU acceptance missing")
    require_registration_commit(ref(root/"protocol_p2/registration.json"),commit)
    frozen(root)
    for role in ("primary","sensitivity"):
        path=root/role/"plan.json"
        plan=ex.load(path)
        approval=dict(execution_authorized=True,user_request=request["user_request"],
            user_approval=ref(request_file),date=datetime.now(timezone.utc).isoformat(),
            scope="formal",analysis_role=role,plan=ref(path),jobs=[ex.job_id(j) for j in plan["jobs"]],
            decisions=ref(root/"decisions.json"),registration_commit=commit,
            baseline_plan=plan["baseline_plan"],
            prerequisites=[ref(EP7/name/"plan.json") for name in ("gpu_probes","norm_pilot")],
            cpu_acceptance=ref(root/"cpu_acceptance.json"),automatic_retry=False)
        target=path.with_name("execution_authorization.json")
        write(target,approval);write(target.with_suffix(".seal.json"),dict(authorization=ref(target)))
    # The sealed false authorization files remain unchanged by design.


def run(root):
    root=Path(root).resolve()
    with ex._Lock(root/".pipeline.lock"):
        if (root/"pipeline_complete.json").exists():
            raise FileExistsError("EP8 already complete; verify the existing results")
        if (root/"pipeline_failure.json").exists():
            raise RuntimeError("Retained EP8 failure; explicit recovery required")
        try:
            for role in ("primary","sensitivity"):
                subprocess.run([sys.executable,"-B","-m","scripts.edge_sem.execution",
                    "all","--plan",str(root/role/"plan.json")],check=True,cwd=str(ROOT))
            result=summarize(root,root/"results")
            write(root/"pipeline_complete.json",dict(passed=True,new_fits=result["new_fits"],
                reused_fits=result["reused_fits"],summary=ref(root/"results/summary.json")))
            write(root/"pipeline_complete.seal.json",dict(complete=ref(root/"pipeline_complete.json")))
        except Exception as error:
            write(root/"pipeline_failure.json",dict(error=repr(error),traceback=traceback.format_exc(),
                automatic_retry=False))
            raise


def accept_preparation(root):
    """Read-only acceptance before either formal batch can start."""
    root=Path(root)
    index_path,index=preparation_index(root)
    if (index.get("optimizer_steps")!=0 or index.get("cuda_initialized") is not False
            or index.get("new_weight_files")!=56
            or [len(index["jobs"][k]) for k in ("primary","sensitivity")]!=[60,80]):
        raise ValueError("CPU preparation result differs")
    suites=read(root/"cpu_tests_v1/results.json")
    if suites.get("passed") is not True or {x["suite"] for x in suites["suites"]}!={"edge_sem","node_sem","DFG/dfg_v2"}:
        raise ValueError("Required CPU regressions missing")
    for item in suites["suites"]:
        if item["exit_code"]!=0:raise ValueError("CPU regression failed")
        checked(item["log"])
    postfix=read(root/"postfix_tests/result.json")
    targeted=read(root/"preparation_revision_v2/targeted_tests.json")
    if (postfix.get("exit_code")!=0 or targeted.get("passed") is not True
            or targeted.get("exit_code")!=0 or targeted.get("count")!=37):
        raise ValueError("Targeted CPU acceptance failed")
    followup=read(root/"preparation_revision_v2/followup_tests.json")
    if followup.get("exit_code")!=0 or followup.get("count")!=39:
        raise ValueError("Preparation followup tests missing")
    for value in followup["sources"].values():checked(value)
    refs=index.get("fast_full_equivalence",[])
    if len(refs)!=6:raise ValueError("Missing real fast/full assembly proofs")
    required={"parameters_bitwise_equal","node_tensors_bitwise_equal","edge_tensors_bitwise_equal",
              "graph_fingerprint_equal","binding_equal","support_equal","full_assembly_unchanged","zero_optimizer_steps"}
    keys=set()
    for row in refs:
        value=read(checked(row))
        if any(value.get(k) is not True for k in required):raise ValueError("Fast/full proof failed")
        key=(value["task_id"],value["profile"])
        if key in keys:raise ValueError("Repeated fast/full proof")
        keys.add(key)
    if keys!={(t,p) for t in ex.TASKS for p in PROFILES[1:]}:
        raise ValueError("Incomplete task/profile proof coverage")
    unique={}
    for group in index["jobs"].values():
        for item in group:
            job=item["job"]
            if read(checked(item["record"]))!=job:raise ValueError("Prepared record differs")
            ex._validate_job(job)
            initial=job["initial"]
            if initial["path"] not in unique:
                payload=ex.load_checked(initial);_zero_state(job,payload)
                unique[initial["path"]]=initial
    if len(unique)!=80:raise ValueError("Initial matrix differs")
    # Appended orchestration/report code must not alter the preparation code
    # that the detached process actually imported.
    import ast
    previous=root/"preparation_revision_v2/recon__ep8_run.py.after.txt"
    def functions(path):
        return {n.name:ast.dump(n) for n in ast.parse(Path(path).read_text()).body if isinstance(n,ast.FunctionDef)}
    old,new=functions(previous),functions(__file__)
    for name in ("prepare","install_untrained_view","identical_assembly","retained_jobs","_zero_state","archive_baseline","store_job"):
        if old[name]!=new[name]:raise ValueError("Preparation implementation changed while running")
    h8.load(checked(index["source_h8_plan"]))
    result=dict(passed=True,preparation=ref(index_path),unique_initial_files=80,
        primary_jobs=60,sensitivity_jobs=80,real_assembly_proofs=refs,
        full_regressions=ref(root/"cpu_tests_v1/results.json"),
        targeted_tests=[ref(root/name) for name in ("postfix_tests/result.json","preparation_revision_v2/targeted_tests.json","preparation_revision_v2/followup_tests.json")],
        frozen=frozen(root),source_h8_plan_load=True,preparation_code_unchanged=True,
        zero_optimizer_steps=True,execution_core_unchanged=True)
    write(root/"cpu_acceptance.json",result)
    write(root/"cpu_acceptance.seal.json",dict(acceptance=ref(root/"cpu_acceptance.json")))
    return result


def finish_preparation(root, commit, request_file):
    """Wait for the approved CPU attempt, then use existing seal/fit paths."""
    root=Path(root)
    with ex._Lock(root/".preparation_followup.lock"):
        if (root/"followup_started.json").exists():
            raise FileExistsError("Followup already started; inspect its receipts, never retry implicitly")
        process=read(root/"preparation_attempt2_process.json")
        write(root/"followup_started.json",dict(process=ref(root/"preparation_attempt2_process.json"),
            registration_commit=commit,user_request=ref(request_file),automatic_retry=False,
            order=["CPU_acceptance","seal","authorize","primary","sensitivity","analysis"]))
        try:
            print("EP8 waiting for approved CPU preparation",process["pid"],flush=True)
            while True:
                failure=root/"preparation_attempt2/failure.json"
                if failure.exists():raise RuntimeError("CPU preparation failed; preserved at "+str(failure))
                status=Path("/proc")/str(process["pid"])/"status"
                try:
                    content=status.read_text()
                except FileNotFoundError:
                    break
                if any(x.startswith("State:") and "Z" in x for x in content.splitlines()):break
                cmdline=status.with_name("cmdline")
                try:
                    argv=cmdline.read_bytes().split(b"\0")
                except FileNotFoundError:
                    break
                if b"scripts.edge_sem.recon.ep8_run" not in argv or b"prepare" not in argv:
                    raise RuntimeError("Preparation PID belongs to another process")
                time.sleep(30)
            print("EP8 CPU process ended; validating prepared results",flush=True)
            accept_preparation(root)
            seal(root)
            authorize(root,commit,request_file)
            print("EP8 accepted and sealed; starting primary then sensitivity",flush=True)
            run(root)
            write(root/"followup_complete.json",dict(passed=True,
                pipeline_complete=ref(root/"pipeline_complete.json"),registration_commit=commit))
        except Exception as error:
            write(root/"followup_failure.json",dict(error=repr(error),traceback=traceback.format_exc(),
                automatic_retry=False))
            raise



def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("register","prepare","seal","authorize","run","verify","analyze","frozen","finish-preparation"))
    parser.add_argument("--root",default=str(DEFAULT_ROOT))
    parser.add_argument("--preparation-name",default="preparation")
    parser.add_argument("--registration-commit")
    parser.add_argument("--request-file")
    args=parser.parse_args()
    root=Path(args.root).resolve()
    if ROOT/"scripts/edge_sem/artifacts" not in root.parents:
        raise ValueError("EP8 root must remain under EdgeSem artifacts")
    if args.command in ("authorize","finish-preparation"):
        if not args.registration_commit or not args.request_file:
            parser.error("authorize requires committed registration and a user approval file")
        action=authorize if args.command=="authorize" else finish_preparation
        action(root,args.registration_commit,args.request_file)
    elif args.command=="verify":
        for role in ("primary","sensitivity"):
            path=root/role/"plan.json";plan=ex.load(path,mode="verify")
            for job in plan["jobs"]:ex.verify_one(path,plan,job)
    elif args.command=="analyze":summarize(root,root/"results")
    elif args.command=="prepare":prepare(root,args.preparation_name)
    else:globals()[args.command](root)


if __name__=="__main__":
    main()
