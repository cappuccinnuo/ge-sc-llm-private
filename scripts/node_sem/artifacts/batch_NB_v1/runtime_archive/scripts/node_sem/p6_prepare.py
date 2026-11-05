"""NS-P6 CPU preparation adapted from scripts/node_sem/p5_prepare.py.\nSource SHA256: cc3c9b87c178025fa28a9b21d2607301ab92ba5864ad2e1bc812458ee16ada0f
Keeps model/initialization algorithms; adds N-B matrix and readonly N-A audit.
"""
import argparse
import copy
import csv
import gc
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
import traceback

import numpy as np
import torch
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.support import model_support
from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY
from scripts.DFG.experiments.common import digest, seed_all, tensor_digest
from . import batch_nb as na
from .carrier import write_carrier
from .model import make_nodesem_model, validate
from .init import initial_state, checked_initial, VERSION as INIT_VERSION
from .feature_spec import FeatureSpec
from .execution import _validate_carrier

BASE = na.ROOT / "scripts/node_sem"
P4B = BASE / "artifacts/ns_p4/attempt3/resume2"


def bind_spec(name, refs, token):
    value = read(BASE / "configs" / (name + ".json"))
    for m in value["modalities"]:
        m["manifest"] = (token if m["name"] == "token_ids" else
                         refs["ctx"]["masked" if name == "S4m" else "original"] if m["name"] == "ctx" else refs[m["name"]])
    spec = FeatureSpec.from_json(value)
    if spec.name not in na.NAMES or spec.view != "original":
        raise ValueError("N-B uses only registered original-view configurations")
    return spec


def prerequisites():
    p4 = read(checked(read(P4B / "plan.seal.json")["plan"]))
    gate_ref = read(P4B / "independent_verification.seal.json")
    # Use the reference actually present in the acceptance seal.
    refs = [v for v in gate_ref.values() if isinstance(v, dict) and "path" in v and "sha256" in v]
    if len(refs) != 1:
        raise ValueError("Ambiguous P4b verification seal")
    gate = read(checked(refs[0]))
    if (gate.get("passed") is not True or gate.get("node_gpu_passed") != 6
            or len(gate.get("checks", [])) != 14 or gate.get("plan") != ref(P4B / "plan.json")):
        raise ValueError("P4b GPU acceptance prerequisite incomplete")
    source = h8.load(checked(p4["source_h8_plan"]))
    audit = read(BASE / "artifacts/ns_p1_initial_digests/digests.json")
    if audit.get("passed") is not True or audit.get("count") != 60 or audit["plan"] != p4["source_h8_plan"]:
        raise ValueError("Historical zero-step digest audit missing")
    current_path = BASE / "artifacts/ns_p3/CURRENT.json"
    current = read(current_path)
    accepted = read(checked(current["validation"]))
    if (read(checked(current["seal"]))["validation"] != current["validation"]
            or accepted.get("passed") is not True or accepted.get("static_dimension") != 245):
        raise ValueError("P3b2 accepted features missing")
    prep = read(checked(source["source_preparation"]))
    token_ref = prep["bound_artifacts"]["feature_views"]
    views = read(checked(token_ref))
    return p4, source, current, accepted, views, dict(
        p4b_plan=ref(P4B / "plan.json"), p4b_verification=refs[0],
        p4b_verification_seal=ref(P4B / "independent_verification.seal.json"),
        initial_audit=ref(BASE / "artifacts/ns_p1_initial_digests/digests.json"),
        token_views=token_ref, p3_current_at_preparation=ref(current_path))


def device_policy():
    if torch.cuda.is_initialized():
        raise RuntimeError("CPU-only preparation must not initialize CUDA")
    observed = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits"], universal_newlines=True).strip().splitlines()
    if len(observed) != 1:
        raise ValueError("Explicit single local GPU identity required")
    name, memory, driver = [s.strip() for s in observed[0].split(",")]
    if "3050" not in name:
        raise ValueError("Approved local RTX3050 device not found")
    return dict(location="local_RTX3050", device_type="cuda", gpu_model=name,
        torch_version=torch.__version__, cuda_build_version=torch.version.cuda,
        allow_tf32=dict(matmul=torch.backends.cuda.matmul.allow_tf32,
                        cudnn=torch.backends.cudnn.allow_tf32)), dict(
        gpu_model=name, total_mib=float(memory), driver=driver, cuda_initialized=False)


def prove_reuse(model, spec, task_id, profile, task, info, entry):
    """Compare every initialized tensor for fold 1 against a fresh constructor."""
    if any(p.grad is not None for p in model.parameters()):
        raise ValueError("Preparation model has gradients")
    seed_all(info["seeds"]["constructor"])
    fresh = make_nodesem_model(task["granularity"], entry["graph"], profile, spec,
                              task["config"], "cpu", task_id)
    a, ash = initial_state(model, spec, task_id, 1, profile, entry["initial"])
    b, bsh = initial_state(fresh, spec, task_id, 1, profile, entry["initial"])
    if set(a) != set(b) or ash != bsh or any(not torch.equal(a[k], b[k]) for k in a):
        raise ValueError("Reused structure is not identical to fresh fold initialization")
    if model.ntypes_dict != fresh.ntypes_dict or model.etypes_dict != fresh.etypes_dict:
        raise ValueError("Semantic schema registration differs")
    result = dict(passed=True, task_id=task_id, profile=profile, name=spec.name,
        fold=1, state_sha256=ash, tensor_keys=len(a), all_tensors_bitwise_equal=True,
        optimizer_steps=0, no_forward_or_fit=True, source=entry["initial"])
    del fresh, a, b; gc.collect()
    return result


def save_initial(model, spec, job, target):
    state, sha = initial_state(model, spec, job["task_id"], job["fold"], job["profile"], job["h8_initial"])
    payload = dict(kind="untrained_initial", optimizer_steps=0, task_id=job["task_id"],
        fold=job["fold"], seed=1, profile=job["profile"],
        constructor_seed=job["seeds"]["constructor"], fit_seed=job["seeds"]["fit"],
        feature_spec_sha256=spec.digest(), initialization_version=INIT_VERSION,
        state_dict=state, state_sha256=sha, source=job["h8_initial"], formal_training=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        torch.save(payload, stream)
    reference = dict(ref(target), state_sha256=sha)
    loaded = checked_initial(reference, job["task_id"], job["fold"], job["profile"], spec_digest=spec.digest())
    model.load_state_dict(loaded["state_dict"], strict=True)
    if tensor_digest(model.state_dict()) != sha:
        raise ValueError("CPU model reload digest differs")
    del payload, state, loaded
    return reference


def estimate_resources(index_ref, jobs):
    rows = read(checked(index_ref))["records"]
    result = []
    for task, folds in na.TASK_FOLDS:
        for name in na.NAMES:
            profile = na.PROFILE_BY_NAME[name]
            old = [r for r in rows if r["job"]["task_id"] == task
                   and r["job"]["profile"] == profile and r["job"]["name"] == "S4"]
            if len(old) != folds:
                raise ValueError("N-A resource reference incomplete")
            seconds = sum(x["total_seconds"] for x in old)
            result.append(dict(task_id=task, name=name, profile=profile, fits=folds,
                reference="N-A S4 same task/profile full wall time",
                historical_seconds=seconds, estimate_low_seconds=seconds*0.8,
                estimate_high_seconds=seconds*1.5))
    return dict(by_group=result, total_hours=[
        sum(x[k] for x in result)/3600 for k in ("estimate_low_seconds","estimate_high_seconds")],
        not_measured_NB=True, assumptions="0.8-1.5x N-A S4 wall time scenario, not confidence interval",
        caveats=["early stopping and OS GPU contention may change duration",
                 "zero HGT layers can reduce fit cost but preparation/scoring overhead remains",
                 "N-A minimum free VRAM 34 MiB; memory_tight logs only; OOM stops whole batch",
                 "attention/gate eval and preparation excluded; server not measured"])



def prepare(out, decisions):
    out = Path(out).resolve()
    if na.ARTIFACTS.resolve() not in out.parents:
        raise ValueError("Output must stay inside NodeSem artifacts")
    out.mkdir(parents=True, exist_ok=False)
    write(out / "prepare.started.json", dict(pid=os.getpid(), started=time.time(), training=False))
    started = time.monotonic()
    try:
        decision = read(checked(decisions))
        if decision.get("local_pilot_approved") is not True or decision.get("reuse_untrained_structures_approved") is not True:
            raise ValueError("Explicit approved preparation choices missing")
        from .nb_history import audit
        from .batch_na import DEFAULT as NA_DEFAULT
        parent_plan, parent_refs, parent_index = audit(NA_DEFAULT, out / "na_result_index.json")
        p4, source, current, accepted, views, prereqs = prerequisites()
        if current != read(checked(parent_plan["feature_source"])):
            raise ValueError("N-A and N-B feature source snapshots differ")
        policy, hardware = device_policy()
        if any(v != policy for v in parent_plan["device_families"].values()):
            raise ValueError("N-B device/torch/CUDA/TF32 must equal N-A")
        table = na._historical_table(source)
        write(out / "feature_source.json", current)
        # CURRENT is a moving pointer: bind its immutable snapshot and accepted files.
        prereqs["p3_current_at_preparation"] = dict(source_path=prereqs["p3_current_at_preparation"]["path"],
            source_sha256=prereqs["p3_current_at_preparation"]["sha256"])
        inputs = out / "inputs"; inputs.mkdir()
        for name in ("PROMPTS.md", "EXPERIMENT_POLICY.md"):
            (inputs / name).write_bytes((BASE / name).read_bytes())
        runtime = na.runtime()
        archives = {}
        for rel, sha in runtime.items():
            target = out / "runtime_archive" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write((na.ROOT / rel).read_bytes())
            archives[rel] = ref(target)
            if archives[rel]["sha256"] != sha:
                raise ValueError("Runtime changed while archiving")
        jobs, group_proofs, token_checks = [], [], []
        for task_id, folds in na.TASK_FOLDS:
            for profile in na.PROFILES:
                task0, info0, entry0 = table[(task_id, 0, profile)]
                graph = read_graph(checked(entry0["graph"]))
                fingerprint = graph_fingerprint(graph)
                for name in na.NAMES:
                    if na.PROFILE_BY_NAME[name] != profile:
                        continue
                    groupdir = out / "prepared" / task_id / profile / name
                    groupdir.mkdir(parents=True, exist_ok=False)
                    spec = bind_spec(name, accepted["tasks"][task_id], views["task_views"][task_id]["original"])
                    write(groupdir / "spec.json", spec.to_json())
                    write(groupdir / "template.json", read(BASE / "configs" / (name + ".json")))
                    carrier = write_carrier(spec, task_id, graph, groupdir / "carrier")
                    start = time.monotonic()
                    seed_all(info0["seeds"]["constructor"])
                    model = make_nodesem_model(task0["granularity"], entry0["graph"], profile, spec,
                                              task0["config"], "cpu", task_id)
                    constructor_seconds = time.monotonic()-start
                    mini = dict(feature_view=carrier["manifest"], feature_npz=carrier["data"])
                    _validate_carrier(model, mini)
                    if name in ("S0o", "S1o"):
                        columns = spec.layout()["token_ids"]
                        with np.load(str(checked(carrier["data"])), allow_pickle=False) as a:
                            original = np.stack([attrs["token"] for _, attrs in graph.nodes(data=True)])
                            observed = a["features"][:, columns["start"]:columns["stop"]]
                            if not np.array_equal(original, observed):
                                raise ValueError("Original token carrier differs from downloaded graph")
                        token_checks.append(dict(task_id=task_id, profile=profile, name=name,
                            original_token_exact=True, nodes=len(graph)))
                    # Load fold0 first, then prove fold1 reinitialization on a fresh structure.
                    state0, _ = initial_state(model, spec, task_id, 0, profile, entry0["initial"])
                    model.load_state_dict(state0, strict=True); del state0
                    task1, info1, entry1 = table[(task_id, 1, profile)]
                    proof = prove_reuse(model, spec, task_id, profile, task1, info1, entry1)
                    write(groupdir / "reuse_proof.json", proof)
                    group_proofs.append(ref(groupdir / "reuse_proof.json"))
                    for fold in range(folds):
                        task, info, entry = table[(task_id, fold, profile)]
                        if entry["graph"] != entry0["graph"] or task["config"] != task0["config"]:
                            raise ValueError("Structure reuse group differs across folds")
                        j = dict(name=name, task_id=task_id, granularity=task["granularity"], fold=fold,
                            seed=1, profile=profile, view="original", reuse_8h=False,
                            spec=ref(groupdir / "spec.json"), spec_sha256=spec.digest(),
                            config_template=ref(groupdir / "template.json"), graph=entry["graph"],
                            labels=task["record"]["labels"], folds=task["record"]["folds"],
                            label_view=task["label_view"], config=task["config"], split=info["split"],
                            graph_files=task["record"]["graph_files"], h8_initial=entry["initial"],
                            initialization=info["initialization"], seeds=info["seeds"],
                            source_preparation=source["source_preparation"],
                            feature_view=carrier["manifest"], feature_npz=carrier["data"],
                            original_graph_fingerprint=fingerprint, node_count=len(graph),
                            registered_node_types=[r["name"] for r in entry["support"]["schema"]["node_types"]],
                            carrier_dim=spec.carrier_dim(), parameters=sum(p.numel() for p in model.parameters()),
                            device_policy=copy.deepcopy(policy), constructor_seconds=constructor_seconds,
                            support=model_support(model, info["split"]))
                        if j["support"] != entry["support"]:
                            raise ValueError("Schema/training support changed from fixed graph")
                        fold_dir = groupdir / ("fold_%d" % fold)
                        j["initial"] = save_initial(model, spec, j, fold_dir / "initial.pt")
                        j["dropout"] = na.dropout_identity(model, j, spec)
                        check = na.validate_initial(j, spec)
                        write(fold_dir / "preparation.json", dict(identity=list(na.key(j)), initial=j["initial"],
                            cpu_loaded_digest_exact=True, common_initial_exact=check["passed"],
                            all_parameters_exact=check["all_parameters_exact"], dropout=j["dropout"],
                            model_never_trained=True, optimizer_steps=0, reused_structure_proof=ref(groupdir / "reuse_proof.json")))
                        j["preparation_evidence"] = ref(fold_dir / "preparation.json")
                        write(fold_dir / "job.json", j); jobs.append(j)
                        print("prepared %d/120 %s fold%d %s %s" % (len(jobs), task_id, fold, profile, name), flush=True)
                    from .na_carrier import load_carrier, construct_carried
                    carried, record, fast_spec = load_carrier(j)
                    seed_all(j["seeds"]["constructor"])
                    fast = construct_carried(j, carried, record, fast_spec)
                    fast.load_state_dict(checked_initial(j["initial"], j["task_id"], j["fold"],
                        j["profile"], spec_digest=spec.digest())["state_dict"], strict=True)
                    if (tensor_digest(fast.state_dict()) != tensor_digest(model.state_dict())
                            or any(not torch.equal(fast.symmetrical_global_graph.nodes[t].data["inp"],
                                model.symmetrical_global_graph.nodes[t].data["inp"])
                                for t in model.ntypes_dict)):
                        raise ValueError("N-B fast carrier/model differs from original assembly")
                    write(groupdir / "fast_carrier_proof.json", dict(passed=True, input_exact=True,
                        parameter_exact=True, group=[task_id, profile, name],
                        zero_layers=(len(fast.gcs) == 0), actual_layers=len(fast.gcs),
                        training_fits=0, initial=j["initial"]))
                    del fast, carried, record
                    validate(model, spec)
                    if graph_fingerprint(graph) != fingerprint:
                        raise ValueError("Frozen input graph mutated")
                    del model; gc.collect()
                del graph; gc.collect()
        jobs.sort(key=lambda j: [na.key(x) for x in na.matrix()].index(na.key(j)))
        na.validate_matrix(jobs); na.validate_device_comparisons(jobs)
        estimates = estimate_resources(parent_index, jobs)
        write(out / "resource_estimate.json", estimates)
        write(out / "preparation_audit.json", dict(passed=True,
            fast_carrier_proofs=[ref(p) for p in sorted((out/"prepared").rglob("fast_carrier_proof.json"))], jobs=len(jobs), structure_proofs=group_proofs,
            original_token_checks=token_checks, cpu_seconds=time.monotonic()-started,
            zero_step_states=120, reused_trained_weights=False, optimizer_steps=0,
            training_fits=0, cuda_initialized=torch.cuda.is_initialized(), hardware=hardware))
        if torch.cuda.is_initialized() or runtime != na.runtime():
            raise ValueError("CUDA initialized or runtime changed during preparation")
        families = {t:copy.deepcopy(policy) for t, _ in na.TASK_FOLDS}
        auth = dict(version=na.VERSION, execution_authorized=False, scope="formal_NB",
            label_policy="L-audit", seeds=[1], view="original", resource_policy=LOCAL_DEV_POLICY,
            jobs=120, matrix_sha256=digest(jobs), planned_device_families=families,
            run_location=None, user_request=None, instructions="Create separate authorized record bound to final plan SHA; never edit this sealed template")
        write(out / "authorization.template.json", auth)
        code_version = dict(head=subprocess.check_output(["git","rev-parse","HEAD"],universal_newlines=True).strip(),
            branch=subprocess.check_output(["git","branch","--show-current"],universal_newlines=True).strip(),
            computation_identity="per-file archived runtime SHA; preparation may precede commit")
        plan = dict(code_version=code_version, na_parent=parent_refs, na_result_index=parent_index, version=na.VERSION, protocol=na.PROTOCOL_NAME, protocol_version=na.PROTOCOL_VERSION,
            view="original", label_policy="L-audit", execution_authorized=False,
            jobs=jobs, source_h8_plan=p4["source_h8_plan"], source_preparation=source["source_preparation"],
            historical_score_use="N-A original results are SHA-bound paired comparators; anonymous 8H scores reference only",
            feature_source=ref(out / "feature_source.json"), prerequisites=prereqs,
            runtime=runtime, runtime_archive=archives, statistics=na.statistics_spec(),
            device_families=families, resource_policy=LOCAL_DEV_POLICY,
            training_precision="preserve default TF32; each receipt must record actual flags/device/torch/CUDA",
            authorization_template=ref(out / "authorization.template.json"),
            preparation_audit=ref(out / "preparation_audit.json"), resource_estimate=ref(out / "resource_estimate.json"),
            resource_evidence=dict(na_results=parent_index, p4b_resources=ref(P4B / "resources_summary.csv")),
            decisions=decisions, prompt=ref(inputs / "PROMPTS.md"), experiment_policy=ref(inputs / "EXPERIMENT_POLICY.md"),
            initialization_version=INIT_VERSION, init_provenance="60 sealed 8H zero-step anchors; no best/last/smoke weights",
            execution_policy=dict(serial=True, fresh_process_per_fit=True, shared_gpu_lock=str(na.ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/.training.lock"),
                failure="stop whole batch and retain all evidence; no automatic retry/CPU fallback/graph reduction",
                oom="move a whole task/all configurations only after explicit user decision; new server batch",
                successful="verify and reuse within same sealed execution batch",
                entrypoint="scripts.node_sem.batch_nb_controller; explicit new execution revision/authorization required",
                runtime_update="explicit independent execution revision, old plan/seal immutable"),
            final_server_intent="Final adequately provisioned server experiments form a separate batch; local RTX3050 limitations are developmental; server not measured")
        write(out / "plan.json", plan)
        write(out / "plan.seal.json", dict(version=na.VERSION, plan=ref(out / "plan.json"), jobs=120, matrix_sha256=digest(jobs)))
        na.load(out / "plan.json", deep=True)
        write(out / "verification.json", dict(passed=True, plan=ref(out / "plan.json"), jobs=120,
            original_token_groups=len(token_checks), fresh_structure_comparisons=len(group_proofs),
            formal_fits=0, historical_NA_comparators=240, precision_policy=policy,
            preparation_seconds=time.monotonic()-started))
        write(out / "verification.seal.json", dict(verification=ref(out / "verification.json"), plan=ref(out / "plan.json")))
        print("N-B plan sealed and independently verified: 120 zero-step jobs, 0 fits", flush=True)
        return plan
    except Exception as error:
        write(out / "prepare.failure.json", dict(error=repr(error), traceback=traceback.format_exc(),
            stop=True, automatic_retry=False, optimizer_steps=0))
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "verify", "check-launch"))
    parser.add_argument("--out", default=str(na.DEFAULT))
    parser.add_argument("--decisions")
    args = parser.parse_args(); torch.set_num_threads(2)
    if args.command == "prepare":
        if not args.decisions:
            parser.error("--decisions required")
        prepare(args.out, ref(Path(args.decisions)))
    elif args.command == "verify":
        result = na.load(Path(args.out) / "plan.json", deep=True)
        print(json.dumps(dict(passed=True, jobs=len(result["jobs"]), training=False)))
    else:
        na.require_launch_authorization(Path(args.out) / "plan.json")


if __name__ == "__main__":
    main()
