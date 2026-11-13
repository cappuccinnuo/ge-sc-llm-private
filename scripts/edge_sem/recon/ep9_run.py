"""EP9 E-B: one preparation/registration/execution/freeze entry point.

Formal fitting delegates to execution.py unchanged numeric functions.
EP8 preparation helpers are imported; sealed EP7/EP8 files are never edited.
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
from scripts.DFG.experiments.common import tensor_digest
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from .. import execution as ex
from ..io import ROOT, ref, checked, read, write
from ..feature_views import source_feature
from ..protocol_p2 import EA_D1, DECISIONS, require_registration_commit
from ..analysis_ea import preparation_index, score
from .ep8_run import (sealed_json, frozen, _zero_state, store_job,
                     install_untrained_view, identical_assembly, topology_equal)

DEFAULT_ROOT = ROOT/"scripts/edge_sem/artifacts/ep9_v1"
EA = ROOT/"scripts/edge_sem/artifacts/ep8_v1"
EP7 = ROOT/"scripts/edge_sem/artifacts/ep7_original_v1"
PROFILES = ("G4R-A", "G4R-Api", "G3R-TA")
BASELINES = ("G3R", "G3R-T", "G4R")
PAIRS = {"G4R-A":"G4R", "G4R-Api":"G4R", "G3R-TA":"G3R-T"}


def prior_plans():
    return {"original":[EP7/"formal/plan.json", EA/"primary/plan.json"],
            "anonymous":[EA/"sensitivity/plan.json"]}


def registration(root):
    root=Path(root)
    before=sealed_json(root/"before.json","before")
    checked(before["prompt"])
    ea=sealed_json(EA/"results/summary.json","summary")
    old=sealed_json(EA/"protocol_p2/registration.json","registration")
    if ea.get("passed") is not True or ea["new_fits"]!=140 or ea["reused_fits"]!=20:
        raise ValueError("Completed E-A summary required")
    decision=dict(experiment_stage="E-B",date=datetime.now(timezone.utc).isoformat(),
        user_request="完成EP9",choice_verbatim="Original + anonymized (Recommended)",
        choice_source=dict(document=before["prompt"],section="4.11.0 / r18; user choice 2026-11-12"),
        previous_decisions=ref(EA/"decisions.json"),
        decisions={k:dict(status="confirmed",value=EA_D1 if k=="D1" else v) for k,v in DECISIONS.items()},
        training_execution_authorized=False)
    write(root/"decisions.json",decision)
    write(root/"decisions.seal.json",dict(decisions=ref(root/"decisions.json")))
    reg=copy.deepcopy(old)
    for k in ("no_automatic_EP9","previous_registration"):
        reg.pop(k,None)
    reg.update(version="edgesem-E-B-registration-r18-v1",experiment_stage="E-B",
        prompt=before["prompt"],previous_registration=ref(EA/"protocol_p2/registration.json"),
        decisions=ref(root/"decisions.json"),new_formal_fits=120,
        batches={role:dict(view=view,profiles=list(PROFILES),fits=60,holm_member=role=="primary")
                 for role,view in (("primary","original"),("sensitivity","anonymous"))},
        baseline_plans={v:[ref(p) for p in paths] for v,paths in prior_plans().items()},
        baseline_profiles=list(BASELINES),baseline_retraining=False,
        H1_source=ref(EA/"results/summary.json"),
        H1_raw_p=ea["hypotheses"]["original"]["H1_raw_p"],
        H1_already_nonsignificant=True,
        correction=dict(method="Holm",family=["H1","H2"],alpha=.05,
            H1="sealed EP8 original reentrancy_node best BF1 max component raw p",
            H2="original reentrancy_node best BF1 max component raw p",
            anonymous="descriptive, outside family"),
        placebo_seed="constructor seed; frozen placebo.permute_attributes",
        zero_initial_gates=dict(common_parameters="bitwise EP8 same-fold G4R or G3R-T",
            u_U="exact zeros",encoder="existing constructor seed",A_Api="entire state bitwise",
            real_fold0_logits="CPU eval bitwise for A/G4R and TA/G3R-T in both views"),
        mechanism=dict(checkpoint="best",population="incoming edges of scored outer_test destination nodes",
            measures=["u Frobenius norm per layer/canonical relation",
                      "U Frobenius norm per layer/family",
                      "u transpose phi per layer/family/head by destination truth"],
            statistical_test=False,dropout="eval",raw_weights_in_report=False),
        execution_authorized=False,no_automatic_server_stage=True)
    write(root/"protocol_p2/registration.json",reg)
    write(root/"protocol_p2/registration.seal.json",
          dict(registration=ref(root/"protocol_p2/registration.json")))
    print("EP9 registered: original 60 + anonymous 60; not yet execution-authorized",flush=True)


def baseline_jobs():
    out={}
    for view,paths in prior_plans().items():
        for path in paths:
            plan=ex.load(path,mode="verify")
            if ex.selected_view(plan)!=view:raise ValueError("Baseline view mismatch")
            for job in plan["jobs"]:
                if job["edge_profile"] not in BASELINES:continue
                key=(view,job["task_id"],job["fold"],job["edge_profile"])
                if key in out:raise ValueError("Duplicate baseline")
                out[key]=(path,plan,job)
    if len(out)!=120:raise ValueError("Expected 120 read-only baseline results")
    return out


def archive(root, baselines):
    dest=Path(root)/"baseline_verification/verification.json"
    records=[]
    for key,(path,plan,job) in sorted(baselines.items()):
        result=ex.verify_one(path,plan,job)
        payload=ex.load_checked(job["initial"]);_zero_state(job,payload);del payload
        for ck in ("best","last"):
            observed=score(read(Path(result["attempt"])/"outer_test_predictions.json"),ck)
            expected=result["result"]["outer_test"][ck]
            if observed["tn_fp_fn_tp"]!=expected["tn_fp_fn_tp"]:
                raise ValueError("Archived scorer mismatch")
        records.append(dict(view=key[0],job_id=ex.job_id(job),plan=ref(path),
            receipt=ref(Path(result["attempt"])/"receipt.json"),initial=job["initial"]))
        print("EP9 archive",key,flush=True)
    value=dict(passed=True,verified_fits=120,training_executed=False,records=records)
    write(dest,value);write(dest.with_suffix(".seal.json"),dict(verification=ref(dest)))
    return ref(dest)


def check_initial(model, baseline, expected_pair=None):
    state=model.state_dict()
    reference=baseline["state_dict"]
    missing=set(reference)-set(state)
    if missing or any(state[k].dtype!=v.dtype or not torch.equal(v,state[k]) for k,v in reference.items()):
        raise ValueError("Common parameters differ from EP8 zero-step initial")
    extra=set(state)-set(reference)
    expected={k for k in state if k.startswith("edge_encoder.") or
              (k.startswith("gcs.") and (k.endswith(".u") or ".U." in k))}
    if extra!=expected:raise ValueError("Unexpected added parameters")
    corrections=[v for k,v in state.items() if k in extra and not k.startswith("edge_encoder.")]
    if not corrections or any(torch.count_nonzero(v).item()!=0 for v in corrections):
        raise ValueError("u/U are not exactly zero")
    if expected_pair is not None:
        if list(state)!=list(expected_pair) or any(not torch.equal(v,expected_pair[k]) for k,v in state.items()):
            raise ValueError("G4R-A/Api full zero-step parameters differ")
    return dict(common_parameters_bitwise_equal=True,u_U_exact_zero=True,
        common_parameter_tensors=len(reference),added_parameter_tensors=len(extra),
        A_Api_entire_state_bitwise_equal=expected_pair is not None,
        state_sha256=tensor_digest(state))


def check_logits(model, reference):
    model.eval()
    with torch.no_grad():actual=model()
    if not torch.isfinite(actual).all() or actual.shape!=reference.shape:
        raise ValueError("Invalid zero-step logits")
    result=dict(bitwise_equal=torch.equal(actual,reference),
        max_abs=float((actual-reference).abs().max()),shape=list(actual.shape))
    return result


def prepare(root):
    root=Path(root);folder=root/"preparation"
    folder.mkdir(exist_ok=False)
    jobs={"primary":[],"sensitivity":[]};proofs=[]
    started=time.monotonic()
    try:
        reg=sealed_json(root/"protocol_p2/registration.json","registration")
        old=baseline_jobs()
        archive_ref=archive(root,old)
        source_ref=next(iter(old.values()))[1]["source_h8_plan"]
        source=h8.load(checked(source_ref))
        equivalence=[]
        for task in ex.TASKS:
            for fold in range(10):
                paired_state=None
                for profile in PROFILES:
                    base_profile=PAIRS[profile]
                    old_job=old[("original",task,fold,base_profile)][2]
                    payload=ex.load_checked(old_job["initial"]);_zero_state(old_job,payload)
                    job=copy.deepcopy(old_job)
                    job.update(edge_profile=profile,token_view="original",
                               attrs_manifest=reg["analysis_inputs"]["attrs"][task])
                    manifest=read(checked(job["attrs_manifest"]))
                    expected=ROOT/"scripts/edge_sem/artifacts/ep6_v1/attributes"/task/"manifest.json"
                    if job["attrs_manifest"]!=ref(expected):raise ValueError("EP6 attributes required")
                    job["f4_manifest"]=manifest["f4_manifest"]
                    if job["f4_manifest"]!=old[("original",task,fold,"G4R")][2]["f4_manifest"]:
                        raise ValueError("Frozen F4 v2 differs")
                    print("EP9 assembling",task,fold,profile,flush=True)
                    model=ex.assemble_model(job)
                    gate=check_initial(model,payload,paired_state if profile=="G4R-Api" else None)
                    state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                    if profile=="G4R-A":paired_state=state
                    sha=tensor_digest(state)
                    weight=folder/"weights"/task/("fold_%d"%fold)/profile/"initial.pt"
                    weight.parent.mkdir(parents=True,exist_ok=False)
                    torch.save(dict(kind="untrained_initial",optimizer_steps=0,task_id=task,
                        fold=fold,seed=1,edge_profile=profile,fit_seed=job["seeds"]["fit"],
                        constructor_seed=job["seeds"]["constructor"],state_dict=state,state_sha256=sha),str(weight))
                    job["initial"]=dict(ref(weight),state_sha256=sha)
                    reread=ex.load_checked(job["initial"]);_zero_state(job,reread)
                    model.load_state_dict(reread["state_dict"],strict=True)
                    if tensor_digest(model.state_dict())!=sha:raise ValueError("Strict reload changed initial")
                    anon=copy.deepcopy(job);anon["token_view"]="anonymous"
                    anon["feature_view"],anon["feature_npz"]=source_feature(source,task,"anonymous")
                    fast=install_untrained_view(model,anon)
                    if fold==0:
                        full=ex.assemble_model(anon)
                        eq=identical_assembly(fast,full,anon["split"])
                        eq.update(task_id=task,profile=profile,fold=fold,optimizer_steps=0)
                        dest=folder/"equivalence"/(task+"__"+profile+".json")
                        write(dest,eq);equivalence.append(ref(dest))
                        del full;gc.collect()
                    logits=[]
                    if fold==0 and profile!="G4R-Api":
                        for view,current in (("original",model),("anonymous",fast)):
                            baseline_job=old[(view,task,fold,base_profile)][2]
                            parent=ex.assemble_model(baseline_job)
                            initial=ex.load_checked(baseline_job["initial"]);_zero_state(baseline_job,initial)
                            parent.load_state_dict(initial["state_dict"],strict=True);parent.eval()
                            with torch.no_grad():reference=parent()
                            value=check_logits(current,reference)
                            value.update(task_id=task,fold=fold,profile=profile,baseline=base_profile,view=view,
                                         baseline_initial=baseline_job["initial"])
                            dest=folder/"zero_logits"/(task+"__"+profile+"__"+view+".json")
                            write(dest,value);logits.append(ref(dest))
                            if not value["bitwise_equal"]:raise ValueError("EP9 zero-step CPU logits not bitwise equal: "+str(dest))
                            del parent,reference,initial;gc.collect()
                    init=dict(kind="EP9_EP8_paired_zero_step",optimizer_steps=0,
                        seeds=job["seeds"],initial=job["initial"],baseline_initial=old_job["initial"],
                        common_gate=gate,encoder_rule="frozen make_attribute_model constructor seed",
                        shared_copy=model.edge_initialization,zero_logits=logits,
                        parameter_count=sum(v.numel() for v in state.values()))
                    jobs["primary"].append(store_job(folder/"original"/task/("fold_%d"%fold)/profile,job,model,init))
                    jobs["sensitivity"].append(store_job(folder/"anonymous"/task/("fold_%d"%fold)/profile,anon,fast,
                        dict(init,kind="same_zero_step_across_views",paired_initialization=job["initialization"])))
                    if job["support"]!=anon["support"]:raise ValueError("View support mismatch")
                    topology_equal(model,fast)
                    proofs.append(dict(task_id=task,fold=fold,profile=profile,initial=job["initial"],gate=gate))
                    print("EP9 paired preparation accepted",task,fold,profile,flush=True)
                    del model,fast,state,payload,reread;gc.collect()
                del paired_state;gc.collect()
        if any(len(jobs[k])!=60 for k in jobs) or len(equivalence)!=6:
            raise ValueError("Incomplete 60+60 preparation or full/fast proofs")
        if torch.cuda.is_initialized():raise ValueError("CPU preparation initialized CUDA")
        result=dict(jobs=jobs,proofs=proofs,fast_full_equivalence=equivalence,
            source_h8_plan=source_ref,baseline_plans=reg["baseline_plans"],
            baseline_plan=ref(EA/"primary/plan.json"),baseline_verification=archive_ref,
            registration=ref(root/"protocol_p2/registration.json"),analysis_inputs=reg["analysis_inputs"],
            optimizer_steps=0,cuda_initialized=False,seconds=time.monotonic()-started,
            implementation=ref(Path(__file__)))
        write(folder/"index.json",result);write(folder/"index.seal.json",dict(index=ref(folder/"index.json")))
        write(root/"preparation_index.json",dict(index=ref(folder/"index.json")))
        write(root/"preparation_index.seal.json",dict(pointer=ref(root/"preparation_index.json")))
        print("EP9 preparation completed",flush=True)
    except Exception as error:
        write(folder/"failure.json",dict(error=repr(error),traceback=traceback.format_exc(),
            completed_primary=len(jobs["primary"]),completed_sensitivity=len(jobs["sensitivity"]),
            automatic_retry=False,training_executed=False))
        raise


def accept(root):
    root=Path(root)
    path,index=preparation_index(root)
    if (root/"preparation/failure.json").exists():raise RuntimeError("Retained preparation failure")
    if (root/"preparation_source_revision.json").exists():
        # The running prepare function may have been completed before the CLI
        # was finalized. Its entire preparation call path must match the saved source.
        import ast
        snapshot=checked(read(root/"preparation_source_revision.json")["snapshot"])
        before={n.name:ast.dump(n) for n in ast.parse(snapshot.read_text()).body if isinstance(n,ast.FunctionDef)}
        after={n.name:ast.dump(n) for n in ast.parse(Path(__file__).read_text()).body if isinstance(n,ast.FunctionDef)}
        for name in ("registration","baseline_jobs","archive","check_initial","check_logits","prepare"):
            if before[name]!=after[name]:raise ValueError("Running preparation algorithm changed")
    tests=sealed_json(regression_folder(root)/"results.json","results")
    expected={"scripts/edge_sem/tests","scripts/node_sem/tests","scripts/DFG/dfg_v2/tests"}
    if ({r["suite"] for r in tests["results"]}!=expected
            or any(r["returncode"]!=0 for r in tests["results"])):
        raise ValueError("All three regression suites must pass")
    for r in tests["results"]:checked(r["log"])
    if tests["runtime"]!=ex.runtime_refs():raise ValueError("Implementation changed after full regressions")
    archive_result=sealed_json(checked(index["baseline_verification"]),"verification")
    if archive_result["verified_fits"]!=120:raise ValueError("Baseline receipt count differs")
    for r in archive_result["records"]:checked(r["receipt"]);checked(r["initial"])
    if any(len(index["jobs"][r])!=60 for r in ("primary","sensitivity")):
        raise ValueError("Incomplete preparation")
    if len(index["fast_full_equivalence"])!=6:raise ValueError("Missing six full/fast proofs")
    for reference in index["fast_full_equivalence"]:
        v=read(checked(reference))
        if not all(v[k] is True for k in ("parameters_bitwise_equal","node_tensors_bitwise_equal",
            "edge_tensors_bitwise_equal","graph_fingerprint_equal","binding_equal","support_equal")):
            raise ValueError("Full/fast equivalence failed")
    zero=list((path.parent/"zero_logits").glob("*.json"))
    if len(zero)!=8 or any(read(p)["bitwise_equal"] is not True or read(p)["max_abs"]!=0 for p in zero):
        raise ValueError("Missing or failed eight real zero-step logits gates")
    by_key={}
    for role in ("primary","sensitivity"):
        for row in index["jobs"][role]:
            job=row["job"]
            if read(checked(row["record"]))!=job:raise ValueError("Prepared job changed")
            ex._validate_job(job)
            payload=ex.load_checked(job["initial"]);_zero_state(job,payload)
            by_key[(role,job["task_id"],job["fold"],job["edge_profile"])]=job
    for task in ex.TASKS:
        for fold in range(10):
            a=by_key[("primary",task,fold,"G4R-A")]
            b=by_key[("primary",task,fold,"G4R-Api")]
            if a["initial"]["state_sha256"]!=b["initial"]["state_sha256"]:
                raise ValueError("A/Api state digest differs")
            for profile in PROFILES:
                a=by_key[("primary",task,fold,profile)];b=by_key[("sensitivity",task,fold,profile)]
                if a["initial"]!=b["initial"]:raise ValueError("Cross-view initial file differs")
    h8.load(checked(index["source_h8_plan"]))
    value=dict(passed=True,preparation=ref(path),tests=ref(regression_folder(root)/"results.json"),
        prepared_jobs=120,zero_logits_checks=8,full_fast_proofs=6,training_executed=False,
        frozen=frozen(root),runtime=ex.runtime_refs())
    write(root/"cpu_acceptance.json",value)
    write(root/"cpu_acceptance.seal.json",dict(acceptance=ref(root/"cpu_acceptance.json")))
    return value


def seal(root):
    root=Path(root)
    accepted=sealed_json(root/"cpu_acceptance.json","acceptance")
    if accepted.get("passed") is not True or accepted["runtime"]!=ex.runtime_refs():
        raise ValueError("Current CPU acceptance required")
    _,index=preparation_index(root)
    for role,view in (("primary","original"),("sensitivity","anonymous")):
        matrix=dict(jobs=[i["job"] for i in index["jobs"][role]],source_h8_plan=index["source_h8_plan"],
            registration=index["registration"],scope="formal",experiment_stage="E-B",analysis_role=role,
            token_view=view,baseline_plan=index["baseline_plan"])
        if role=="sensitivity":matrix["prior_main_plan"]=ref(root/"primary/plan.json")
        ex.create(root/role,matrix)
        ex.load(root/role/"plan.json")


def authorize(root,commit,request_file):
    root=Path(root);request=read(request_file)
    if (request.get("execution_authorized") is not True or not request.get("user_request")
            or request.get("primary_fits")!=60 or request.get("sensitivity_fits")!=60
            or request.get("order")!=["primary","sensitivity"] or request.get("automatic_retry") is not False):
        raise PermissionError("Explicit current EP9 60+60 execution request required")
    acceptance=sealed_json(root/"cpu_acceptance.json","acceptance")
    if acceptance.get("passed") is not True or acceptance["runtime"]!=ex.runtime_refs():
        raise ValueError("CPU acceptance differs")
    require_registration_commit(ref(root/"protocol_p2/registration.json"),commit)
    frozen(root)
    for role in ("primary","sensitivity"):
        path=root/role/"plan.json";plan=ex.load(path)
        approval=dict(execution_authorized=True,user_request=request["user_request"],
            user_approval=ref(request_file),date=datetime.now(timezone.utc).isoformat(),
            scope="formal",analysis_role=role,plan=ref(path),jobs=[ex.job_id(j) for j in plan["jobs"]],
            decisions=ref(root/"decisions.json"),registration_commit=commit,
            baseline_plan=plan["baseline_plan"],
            prerequisites=[ref(EP7/name/"plan.json") for name in ("gpu_probes","norm_pilot")],
            cpu_acceptance=ref(root/"cpu_acceptance.json"),automatic_retry=False)
        dest=path.with_name("execution_authorization.json")
        write(dest,approval);write(dest.with_suffix(".seal.json"),dict(authorization=ref(dest)))
    ex.authorized(root/"primary/plan.json",ex.load(root/"primary/plan.json"))


def freeze_schema(root):
    from .. import VERSION,NEW_RELATIONS,RELATION_FAMILY,PROFILES as REGISTRY
    from ..attrs import EDGE_FEATURE_NAMES
    from ..analysis_eb import LIMITATIONS,sealed_summary
    from scripts.DFG.dfg_v2.benchmark_v2 import anon_binding
    root=Path(root)
    _,summary=sealed_summary(root)
    if summary["new_fits"]!=120:raise ValueError("Incomplete E-B analysis")
    for role in ("primary","sensitivity"):
        path=root/role/"plan.json";p=ex.load(path,mode="verify")
        complete=sealed_json(path.parent/"complete.json","complete")
        if complete["passed"] is not True or complete["plan"]!=ref(path) or len(complete["receipts"])!=60:
            raise ValueError("Both formal batches must complete")
        for job,item in zip(p["jobs"],complete["receipts"]):
            if item["job"]!=job:raise ValueError("Completion ordering differs")
            checked(item["receipt"])
    reg=sealed_json(root/"protocol_p2/registration.json","registration")
    inputs={};unknown={}
    for task,reference in reg["analysis_inputs"]["attrs"].items():
        manifest=read(checked(reference));diagnostics=read(checked(manifest["diagnostics"]))
        unknown_count=sum("61" in r.get("unknown_fields",{}) for r in diagnostics["edges"])
        unknown[task]=dict(unknown_edges=unknown_count,all_forward_attribute_rows=manifest["rows"],
            fraction_of_all_rows=unknown_count/manifest["rows"],
            reason="pragma interval not proven pre/post 0.8; includes unbounded upper ranges",
            source=manifest["diagnostics"])
        inputs[task]=dict(attributes=reference,f4=manifest["f4_manifest"],
            core_indices=manifest["core_indices"],context_indices=manifest["context_indices"],
            anonymous_feature=source_feature(h8.load(checked(reg["source_h8_plan"])),task,"anonymous")[0])
    _,index=preparation_index(root)
    source=h8.load(checked(index["source_h8_plan"]))
    prepared=read(checked(source["source_preparation"]))
    production={str(p.relative_to(ROOT)):ref(p) for p in sorted((ROOT/"scripts/edge_sem").rglob("*.py"))
                if not any(x in p.relative_to(ROOT/"scripts/edge_sem").parts for x in ("tests","recon","artifacts"))}
    profiles={k:dict(v,new_relations=sorted(v["new_relations"])) for k,v in REGISTRY.items()}
    schema=dict(version=VERSION,NEW_RELATIONS=list(NEW_RELATIONS),RELATION_FAMILY=RELATION_FAMILY,PROFILES=profiles,
        EDGE_FEATURE_NAMES=list(EDGE_FEATURE_NAMES),inputs=inputs,
        core_indices=inputs[ex.TASKS[0]]["core_indices"],context_indices=inputs[ex.TASKS[0]]["context_indices"],
        E3=dict(hidden=32,embedding_dim=16,dropout=.1,u_initial=0,U_initial=0),
        P2=dict(registration=ref(root/"protocol_p2/registration.json"),epochs=50,patience=51,
            best="strict minimum inner_val loss; first tie",label_policy="L-audit",seed=1,
            hyperparameters=reg["effective_config"],train="inner_train only; outer_test scored after training"),
        seeds=dict(constructor="10000 + fold + 1000 * is_contract",fit="constructor + 1000000",
            new_relation="EP1 sha256 semantic relation key",attribute_permutation="constructor seed"),
        view_decision=dict(D1=EA_D1,EP8=ref(EA/"decisions.json"),EP9=ref(root/"decisions.json")),
        anonymous=dict(version=anon_binding.VERSION,implementation=ref(Path(anon_binding.__file__)),
            source_8G_preparation=source["source_preparation"],
            spelling_evidence={k:v for k,v in prepared["bound_artifacts"].items() if k.startswith("spelling_")},
            gate=ref(ROOT/"scripts/edge_sem/artifacts/ep6_v1/anonymous_gate/summary.json")),
        production_sources=production,known_limitations=LIMITATIONS,bit61_unknown=unknown,
        result_summary=ref(root/"results/summary.json"),
        next_stage_policy="E-C0/E-C/E-D use this immutable version; changes require a new version and reason",
        final_server_intent="Final experiments will run on a server with sufficient VRAM; current limits are local only.")
    if any(v["core_indices"]!=schema["core_indices"] or v["context_indices"]!=schema["context_indices"] for v in inputs.values()):
        raise ValueError("Task-specific attribute layout is forbidden")
    dest=ROOT/"scripts/edge_sem/artifacts/frozen_schema/schema.json"
    if dest.parent.exists():raise FileExistsError("Frozen schema directory already exists")
    write(dest,schema);write(dest.with_suffix(".seal.json"),dict(schema=ref(dest)))
    return ref(dest)


def finish_documents(root,schema):
    from ..analysis_eb import reports,sealed_summary
    root=Path(root)
    reports(root,schema)
    _,summary=sealed_summary(root)
    text=("\n\n## EP9：E-B 完成与 EdgeSem v1 冻结\n\n"
          "本轮按 PROMPTS r18 完成原名60次、匿名60次 P2 正式拟合；只读复用120个基线结果。"
          "原名为唯一主终点，匿名只作预登记描述性敏感性分析。"
          "H2采用两项配对p的较大者，与封存H1组成两项Holm族；H1原始p约0.1997，仍不显著。\n\n"
          "所有初值共享参数逐位核验，A/Api全部初值相同，u/U为零；8项真实fold0零步输出与6项跨视图装配核验通过。"
          "训练计算不变；新增 analysis_eb.py 和 recon/ep9_run.py，现有入口增加E-B身份、矩阵核验及显式监控恢复修订。"
          "三套CPU回归和全部收据核验见 ep9_v1/cpu_tests 与 cpu_tests_delivery1、cpu_acceptance.json 与 results/summary.json。\n\n"
          "结果报告：scripts/edge_sem/EP9_REPORT.md；综合报告：scripts/edge_sem/EDGESEM_REPORT.md；"
          "冻结：scripts/edge_sem/artifacts/frozen_schema/schema.json。机制描述只读取best权重，按outer_test目标入边汇总，"
          "不把节点/边当作独立实验。原图、标签、折、旧产物及冻结DFG/NodeSem均保持原SHA。\n\n"
          "最终七类实验将在显存充足的服务器另建批次；当前限制仅因本机，不自动启动服务器阶段。"
          "已批准的交付调整：大于等于1MiB的JSON以确定性gzip副本交付，原文件、SHA、恢复入口完整保留；本地训练继续读取原JSON，plan/seal与计算不变。Windows长命令写入改用base64标准输入，仅为文件传输方式。\n\n"
          "采样恢复修订见 ep9_v1/recovery_sampling_v2：原计划不变，已完成4次结果复用，第5次从封存初值重跑；"
          "查询失败保存原异常，最多3次查询，持续失败停止；修订后三套回归在 recovery_sampling_v2/cpu_tests。"
          "实际恢复命令：python -B -m scripts.edge_sem.recon.ep9_run run --recovery scripts/edge_sem/artifacts/ep9_v1/recovery_sampling_v2；"
          "初值 prepare，登记 register，验收 accept，封存 seal，授权 authorize，各在独立记录中。\n")
    documents=read(root/"before.json")["documents"]
    offsets=[]
    for name in documents:
        p=ROOT/name;offset=p.stat().st_size
        with p.open("a",encoding="utf8") as stream:stream.write(text)
        offsets.append(str(p)+":"+str(offset))
    cmd=[sys.executable,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+offsets+[
        str(ROOT/"scripts/edge_sem/EP9_REPORT.md"),str(ROOT/"scripts/edge_sem/EDGESEM_REPORT.md")]
    subprocess.run(cmd,check=True,cwd=str(ROOT))
    return dict(documents={n:ref(ROOT/n) for n in documents},
        reports=[ref(ROOT/"scripts/edge_sem"/n) for n in ("EP9_REPORT.md","EDGESEM_REPORT.md")])



def seal_sampling_recovery(root, folder):
    """Reuse prepared jobs and completed fits; record one approved fresh attempt."""
    from ..runtime import (REVISION_VERSION, REVISION_FILES, SAMPLING_RETRY_POLICY,
                           snapshot_runtime, verify_execution_revision)
    root, folder = Path(root).resolve(), Path(folder).resolve()
    if folder.parent != root:
        raise ValueError("Recovery must be a new EP9 subdirectory")
    request_path = folder/"request.json"
    request = sealed_json(request_path, "request")
    if (request.get("execution_authorized") is not True or not request.get("user_request")
            or request.get("automatic_fit_retry") is not False
            or request.get("restart_failed_job_from_sealed_initial") is not True
            or request.get("pipeline_failure") != ref(root/"pipeline_failure.json")):
        raise PermissionError("Current EP9 failure recovery approval required")
    plans = {role: ex.load(root/role/"plan.json", mode="verify")
             for role in ("primary", "sensitivity")}
    refs = {role: ref(root/role/"plan.json") for role in plans}
    if refs != request["prior_plans"] or any(p["runtime"] != request["old_runtime"] for p in plans.values()):
        raise ValueError("Recovery original plans differ")
    regression = sealed_json(folder/"cpu_tests/results.json", "results")
    if regression["runtime"] != ex.runtime_refs():
        raise ValueError("Recovery tests do not cover current code")
    observed = []
    for role, plan in plans.items():
        for job in plan["jobs"]:
            attempt = ex._successful(ex.job_directory(root/role, job))
            if attempt is not None:
                ex.verify_one(root/role/"plan.json", plan, job, attempt)
                observed.append(ref(attempt/"receipt.json"))
    observed.sort(key=lambda r: r["path"])
    if observed != sorted(request["completed_receipts"], key=lambda r: r["path"]):
        raise ValueError("Recovery completed population changed")
    verification = folder/"verified_successes.json"
    write(verification, dict(passed=True, receipts=request["completed_receipts"],
                             count=len(observed), no_retraining_successes=True))
    write(verification.with_suffix(".seal.json"), dict(verification=ref(verification)))
    frozen_evidence = frozen(root)
    runtime, snapshots = snapshot_runtime(folder/"runtime")
    revision = dict(version=REVISION_VERSION, plans=refs, request=ref(request_path),
        old_runtime=request["old_runtime"], runtime=runtime, runtime_snapshots=snapshots,
        changed_files=sorted(REVISION_FILES), sampling_policy=SAMPLING_RETRY_POLICY,
        tests=ref(folder/"cpu_tests/results.json"), verified_successes=ref(verification),
        frozen=frozen_evidence, training_calculations_unchanged=True)
    path = folder/"runtime_revision.json"
    write(path, revision)
    write(path.with_suffix(".seal.json"), dict(revision=ref(path)))
    failure_path = checked(request["failure"])
    failed = read(failure_path)
    job = failed["job"]
    if (job not in plans["primary"]["jobs"]
            or failure_path.parent != ex.job_directory(root/"primary", job)
            or ex._successful(failure_path.parent) is not None):
        raise ValueError("Recovery failure identity differs")
    retry = root/"primary"/("retry_"+ex.digest(job)+".json")
    write(retry, dict(approved=True, plan=refs["primary"], job=job,
        user_request=request["user_request"], user_approval=ref(request_path),
        automatic_retry=False, restart_from_sealed_initial=True,
        failure=ref(failure_path), attempt="attempt_002", execution_revision=ref(path)))
    write(retry.with_suffix(".seal.json"), dict(approval=ref(retry)))
    for role, plan in plans.items():
        verify_execution_revision(root/role/"plan.json", plan, path, execute=True)
    if ex._next_attempt(root/"primary/plan.json", job, failure_path.parent).name != "attempt_002":
        raise ValueError("Recovery fresh attempt differs")
    print("EP9 recovery sealed: reuse %d fits; one approved fresh attempt; remaining jobs unchanged" % len(observed),
          flush=True)
    return ref(path)


def run(root,recovery=None):
    root=Path(root)
    from ..analysis_eb import summarize
    with ex._Lock(root/".pipeline.lock"):
        if (root/"pipeline_complete.json").exists():raise FileExistsError("EP9 already complete")
        recovery_folder = root if recovery is None else Path(recovery).resolve()
        revision = None
        if recovery is None:
            if (root/"pipeline_failure.json").exists():raise RuntimeError("Retained failure; no automatic retry")
        else:
            if recovery_folder.parent != root.resolve():raise ValueError("Recovery folder outside EP9")
            if (recovery_folder/"pipeline_started.json").exists():
                raise RuntimeError("Recovery already attempted; no automatic retry")
            from ..runtime import verify_execution_revision
            revision = recovery_folder/"runtime_revision.json"
            for role in ("primary","sensitivity"):
                path=root/role/"plan.json"
                verify_execution_revision(path,ex.load(path,mode="verify"),revision,execute=True)
            request=read(checked(read(revision)["request"]))
            if request["pipeline_failure"]!=ref(root/"pipeline_failure.json"):
                raise ValueError("Recovery failure identity changed")
            write(recovery_folder/"pipeline_started.json",dict(revision=ref(revision),started_unix=time.time()))
        try:
            for role in ("primary","sensitivity"):
                command=[sys.executable,"-B","-m","scripts.edge_sem.execution","all",
                    "--plan",str(root/role/"plan.json")]
                if revision is not None:command += ["--execution-revision",str(revision)]
                subprocess.run(command,check=True,cwd=str(ROOT))
            summary=summarize(root,root/"results")
            schema=freeze_schema(root)
            docs=finish_documents(root,schema)
            evidence=frozen(root)
            write(root/"pipeline_complete.json",dict(passed=True,new_fits=120,reused_fits=120,
                summary=ref(root/"results/summary.json"),schema=schema,documentation=docs,
                frozen=evidence,automatic_server_stage=False,
                execution_recovery=None if revision is None else ref(revision)))
            write(root/"pipeline_complete.seal.json",dict(complete=ref(root/"pipeline_complete.json")))
            followup=followup_folder(root)
            if (followup/"followup_started.json").exists():
                write(followup/"followup_complete.json",dict(passed=True,pipeline=ref(root/"pipeline_complete.json")))
            commit_delivery(root,"EP9 complete E-B comparisons and freeze EdgeSem v1")
        except Exception as error:
            write(recovery_folder/"pipeline_failure.json",dict(error=repr(error),traceback=traceback.format_exc(),automatic_retry=False))
            raise



DELIVERY_JSON_THRESHOLD = 1024 * 1024


def _delivery_path(repository, name, prefix, suffix):
    """Accept a relative path inside the one documented delivery namespace."""
    from pathlib import PurePosixPath
    repository=Path(repository).resolve()
    relative=PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise ValueError("Unsafe delivery path")
    path=repository/str(relative)
    scope=(repository/prefix).resolve()
    if scope not in path.resolve().parents or path.suffix!=suffix:
        raise ValueError("Delivery path outside allowed scope")
    # A symlink may remain inside the scope but must not redirect a restore.
    current=repository
    for part in relative.parts:
        current=current/part
        if current.is_symlink():raise ValueError("Symlink in delivery path")
    return path


def _gzip_content_digest(path, expected_bytes):
    import gzip
    total=0;digest=hashlib.sha256()
    with gzip.open(str(path),"rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            total+=len(chunk)
            if total>expected_bytes:raise ValueError("Expanded delivery exceeds recorded size")
            digest.update(chunk)
    if total!=expected_bytes:raise ValueError("Expanded delivery size differs")
    return digest.hexdigest()


def delivery_bundle(root, candidates, threshold=DELIVERY_JSON_THRESHOLD):
    """Lossless deterministic gzip for large JSON; never change the raw input."""
    import gzip
    root=Path(root).resolve()
    if root!=DEFAULT_ROOT.resolve():raise ValueError("Unexpected EP9 delivery root")
    folder=root/"github_delivery"
    objects=folder/"objects";objects.mkdir(parents=True,exist_ok=True)
    rows=[];selected=[]
    for path in sorted(set(Path(p).resolve() for p in candidates)):
        relative=str(path.relative_to(ROOT))
        if path.suffix!=".json" or path.stat().st_size<threshold:
            selected.append(relative);continue
        _delivery_path(ROOT,relative,"scripts/edge_sem/artifacts",".json")
        original=ref(path)
        packed=objects/(original["sha256"]+".json.gz")
        if not packed.exists():
            with packed.open("xb") as output:
                with gzip.GzipFile(filename="",fileobj=output,mode="wb",mtime=0,compresslevel=6) as stream:
                    with path.open("rb") as source:
                        for chunk in iter(lambda:source.read(1024*1024),b""):
                            stream.write(chunk)
        if (_gzip_content_digest(packed,original["bytes"])!=original["sha256"]
                or ref(path)!=original):
            raise ValueError("Lossless delivery check failed")
        compressed=ref(packed)
        rows.append(dict(source_path=relative,source_sha256=original["sha256"],
            source_bytes=original["bytes"],gzip_path=str(packed.relative_to(ROOT)),
            gzip_sha256=compressed["sha256"],gzip_bytes=compressed["bytes"]))
        selected.append(str(packed.relative_to(ROOT)))
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    manifest=folder/("manifest_"+stamp+".json")
    write(manifest,dict(version="EP9-lossless-json-gzip-v1",threshold_bytes=threshold,
        algorithm="gzip level 6; mtime=0; no embedded filename",local_raw_files_unchanged=True,
        rows=rows,restore_command="python -B -m scripts.edge_sem.recon.ep9_run restore-delivery --manifest "+str(manifest.relative_to(ROOT)),
        excluded_formats=[".pt",".npz",".npy"],approval=ref(root/"delivery_revision1/approval.json")))
    write(manifest.with_suffix(".seal.json"),dict(manifest_name=manifest.name,
        sha256=ref(manifest)["sha256"],bytes=manifest.stat().st_size))
    # Include all prior bundles as well: earlier commits remain restorable.
    selected.extend(str(p.relative_to(ROOT)) for p in folder.rglob("*") if p.is_file())
    return sorted(set(selected)),manifest


def restore_delivery(manifest, repository=None):
    """Restore only missing approved JSON; refuse changed existing destinations."""
    import gzip
    import os
    repository=ROOT if repository is None else Path(repository).resolve()
    manifest=Path(manifest).resolve()
    expected=_delivery_path(repository,str(manifest.relative_to(repository)),
        "scripts/edge_sem/artifacts/ep9_v1/github_delivery",".json")
    seal=read(expected.with_suffix(".seal.json"))
    if (seal.get("manifest_name")!=expected.name or seal.get("sha256")!=ref(expected)["sha256"]
            or seal.get("bytes")!=expected.stat().st_size):
        raise ValueError("Delivery manifest seal mismatch")
    value=read(expected)
    if value.get("version")!="EP9-lossless-json-gzip-v1":raise ValueError("Unknown delivery format")
    verified=[]
    # Validate every blob and destination before writing any recovered file.
    for row in value["rows"]:
        source=_delivery_path(repository,row["source_path"],"scripts/edge_sem/artifacts",".json")
        blob=_delivery_path(repository,row["gzip_path"],
            "scripts/edge_sem/artifacts/ep9_v1/github_delivery/objects",".gz")
        if ref(blob)["sha256"]!=row["gzip_sha256"] or blob.stat().st_size!=row["gzip_bytes"]:
            raise ValueError("Compressed delivery SHA mismatch")
        if _gzip_content_digest(blob,row["source_bytes"])!=row["source_sha256"]:
            raise ValueError("Restored content SHA mismatch")
        if source.exists() and (source.stat().st_size!=row["source_bytes"]
                or ref(source)["sha256"]!=row["source_sha256"]):
            raise ValueError("Existing local JSON differs; will not overwrite")
        verified.append((row,source,blob))
    result=[]
    for row,source,blob in verified:
        existed=source.exists()
        if not existed:
            source.parent.mkdir(parents=True,exist_ok=True)
            temp=source.with_name("."+source.name+"."+row["source_sha256"][:16]+".restore.tmp")
            # Do not remove an earlier interrupted restore or an unrelated file.
            with temp.open("xb") as output:
                try:
                    with gzip.open(str(blob),"rb") as stream:
                        for chunk in iter(lambda:stream.read(1024*1024),b""):
                            output.write(chunk)
                    output.flush();os.fsync(output.fileno())
                    if ref(temp)["sha256"]!=row["source_sha256"]:raise ValueError("Written restore SHA mismatch")
                    os.link(str(temp),str(source))  # Atomic and cannot replace an existing file.
                finally:
                    temp.unlink()
        result.append(dict(path=row["source_path"],already_present=existed,sha256=row["source_sha256"]))
    return dict(passed=True,restored=sum(not r["already_present"] for r in result),files=result)



def commit_delivery(root,message):
    """Explicit local-only delivery; no weights, caches, remote push or broad add."""
    root=Path(root)
    candidates=[]
    for path in [ROOT/"HANDOVER.md",ROOT/"docs/training_changes_2026-10-07.md",
                 ROOT/"scripts/edge_sem/PROGRESS.md"]:
        candidates.append(path)
    for path in sorted((ROOT/"scripts/edge_sem").rglob("*")):
        if not path.is_file():continue
        relative=path.relative_to(ROOT/"scripts/edge_sem")
        if "artifacts" in relative.parts:
            if not (root.resolve() in path.resolve().parents or
                    ROOT/"scripts/edge_sem/artifacts/frozen_schema" in path.parents):
                continue
        if path.suffix not in (".py",".md",".json",".jsonl",".csv",".txt",".log"):
            continue
        if "__pycache__" in relative.parts or "github_delivery" in relative.parts:continue
        if path.suffix==".log" and path.parent==root:continue  # Live supervisor logs stay local.
        candidates.append(path)
    selected,manifest=delivery_bundle(root,candidates)
    path=root/("delivery_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".nul")
    path.write_bytes(b"\0".join(n.encode("utf8") for n in selected)+b"\0")
    staged=subprocess.check_output(["git","diff","--cached","--name-only","-z"],cwd=str(ROOT)).decode().split("\0")
    if any(n and n not in selected for n in staged):raise ValueError("Unrelated staged changes require review")
    subprocess.run(["git","add","-f","--pathspec-from-file="+str(path),"--pathspec-file-nul"],check=True,cwd=str(ROOT))
    subprocess.run(["git","diff","--cached","--check"],check=True,cwd=str(ROOT))
    subprocess.run(["git","commit","-m",message],check=True,cwd=str(ROOT))


def followup_folder(root):
    root=Path(root)
    return root/"delivery_revision1" if (root/"delivery_revision1/approval.json").exists() else root


def regression_folder(root):
    root=Path(root)
    return root/("cpu_tests_delivery1" if followup_folder(root)!=root else "cpu_tests")


def tests(root,recovery=None):
    root=Path(root);folder=regression_folder(root) if recovery is None else Path(recovery)/"cpu_tests"
    folder.mkdir(exist_ok=False)
    import os
    runtime=ex.runtime_refs();results=[]
    environment=dict(os.environ,CUDA_VISIBLE_DEVICES="")
    for suite in ("scripts/edge_sem/tests","scripts/node_sem/tests","scripts/DFG/dfg_v2/tests"):
        target=folder/(suite.replace("/","__")+".log")
        command=[sys.executable,"-B","-m","pytest","-q","-p","no:cacheprovider",suite]
        start=time.monotonic()
        with target.open("x",encoding="utf8") as stream:
            rc=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,cwd=str(ROOT),env=environment).returncode
        row=dict(suite=suite,returncode=rc,command=command,seconds=time.monotonic()-start,log=ref(target))
        results.append(row);write(folder/(suite.replace("/","__")+".json"),row)
        print("EP9 tests",suite,rc,flush=True)
        if rc:
            write(folder/"failure.json",dict(results=results,automatic_retry=False))
            raise RuntimeError("Regression suite failed")
    if runtime!=ex.runtime_refs():raise ValueError("Runtime changed during regression suites")
    write(folder/"results.json",dict(results=results,runtime=runtime))
    write(folder/"results.seal.json",dict(results=ref(folder/"results.json")))


def finish_preparation(root,request_file):
    """Finish an already-running CPU prepare, then commit before authorization."""
    import os
    root=Path(root)
    folder=followup_folder(root)
    with ex._Lock(root/".preparation_followup.lock"):
        if (folder/"followup_started.json").exists():raise FileExistsError("Follow-up already started")
        write(folder/"followup_started.json",dict(pid=os.getpid(),request=ref(request_file)))
        try:
            process=read(root/"preparation_process.json")
            while Path("/proc/%d"%process["pid"]).exists():
                status=Path("/proc/%d/stat"%process["pid"])
                if status.exists() and status.read_text().split(") ",1)[1].startswith("Z "):break
                time.sleep(30)
            if (root/"preparation/failure.json").exists():raise RuntimeError("CPU preparation failed; retained")
            testing=folder/"cpu_tests_process.json"
            if testing.exists():
                pid=read(testing)["pid"]
                while Path("/proc/%d"%pid).exists():
                    status=Path("/proc/%d/stat"%pid)
                    if status.exists() and status.read_text().split(") ",1)[1].startswith("Z "):break
                    time.sleep(30)
                if not (regression_folder(root)/"results.json").exists():
                    raise RuntimeError("CPU regressions interrupted or failed; no retry")
            elif not (regression_folder(root)/"results.json").exists():
                tests(root)
            accept(root);seal(root)
            commit_delivery(root,"EP9 register E-B 120-fit protocol and verified paired initialization")
            commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT),universal_newlines=True).strip()
            authorize(root,commit,request_file)
            run(root)
        except Exception as error:
            write(folder/"followup_failure.json",dict(error=repr(error),traceback=traceback.format_exc(),automatic_retry=False))
            raise

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=("register","prepare","frozen","tests","accept","seal","authorize","run",
                                          "analyze","freeze","finish-preparation","restore-delivery","seal-recovery"))
    parser.add_argument("--root",default=str(DEFAULT_ROOT))
    parser.add_argument("--commit")
    parser.add_argument("--request")
    parser.add_argument("--manifest")
    parser.add_argument("--recovery")
    args=parser.parse_args()
    if args.command=="restore-delivery":print(restore_delivery(args.manifest))
    elif args.command=="register":registration(args.root)
    elif args.command=="prepare":prepare(args.root)
    elif args.command=="frozen":print(frozen(args.root))
    elif args.command=="tests":tests(args.root,args.recovery)
    elif args.command=="accept":accept(args.root)
    elif args.command=="seal":seal(args.root)
    elif args.command=="authorize":authorize(args.root,args.commit,args.request)
    elif args.command=="run":run(args.root,args.recovery)
    elif args.command=="seal-recovery":seal_sampling_recovery(args.root,args.recovery)
    elif args.command=="freeze":freeze_schema(args.root)
    elif args.command=="finish-preparation":finish_preparation(args.root,args.request)
    else:
        from ..analysis_eb import summarize
        summarize(args.root,Path(args.root)/"results")


if __name__=="__main__":
    main()
