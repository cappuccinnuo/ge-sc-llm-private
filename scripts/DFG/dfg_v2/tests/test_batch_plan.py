"""Prompt 8 registration tests: no GPU and no pilot metric reads."""
import copy
from collections import namedtuple
from pathlib import Path

import pytest

from scripts.DFG.integration.io import read_json, write_json, sha256
from scripts.DFG.dfg_v2.experiment import batch_plan as bp, run
from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    records = {t: {"task": "contract" if t.endswith("contract") else "node", "task_id": t}
               for t in bp.DEFAULT_TASKS}
    store = tmp_path / "store.json"
    store_body = {"tasks": {}, "input_manifest": {"path": "mocked", "sha256": "mocked"}}
    for task in records:
        store_body["tasks"][task] = {"graphs": {}}
        for profile in bp.PROFILES:
            key = run.key_for_profile(profile)
            entry = store_body["tasks"][task]["graphs"].setdefault(key, {
                "graph": {"path": str(tmp_path / (task + key)), "sha256": "graph"},
                "profiles": {}})
            entry["profiles"][profile] = {"schema": {"nodes": [], "canonical_relations": []}}
    write_json(store, store_body)
    approval = tmp_path / "historical_approval.json"
    original_source = {"path": str(tmp_path / "historical_plan.json"), "sha256": "historical"}
    jobs = [j for j in bp._matrix(list(records), records, ("G0", "G3R")) if j["fold"] == 0]
    write_json(approval, {"version": "prompt7c-local-dev-approval-v1", "approved": True,
        "policy": "local_dev_v1", "source_plan": original_source,
        "authorized_jobs": [run.job_id(j) for j in jobs]})
    pilot_path = tmp_path / "pilot" / "plan.json"
    pilot_path.parent.mkdir()
    pilot = {"jobs": jobs, "store": bp._ref(store), "layer_impl": "shared_projection",
             "resource_policy": copy.deepcopy(LOCAL_DEV_POLICY),
             "resource_origin": {"version": "prompt7c-local-resource-plan-v1",
                 "approval": bp._ref(approval), "plan": original_source},
             "tasks": {t: {"record": rec, "config": {"layer_impl": "shared_projection"},
                           "prepared": {}} for t, rec in records.items()}}
    for task in records:
        folder = tmp_path / "old_initials" / task
        folder.mkdir(parents=True)
        entries = {}
        for profile in ("G0", "G3R"):
            path = folder / (profile + ".pt")
            path.write_bytes(b"x" * (10 if profile == "G0" else 20))
            entries[profile] = {"initial": bp._ref(path), "layer_impl": "shared_projection"}
        task_path = folder / "task.json"
        write_json(task_path, {"task_id": task, "fold": 0, "seed": 1,
            "layer_impl": "shared_projection", "profiles": entries})
        pilot["tasks"][task]["prepared"]["0/1"] = bp._ref(task_path)
    write_json(pilot_path, pilot)
    write_json(pilot_path.with_name("plan.seal.json"), {"plan_sha256": sha256(pilot_path)})
    for job in jobs:
        folder = run._job_directory(pilot_path.parent, job) / "attempt_001"
        folder.mkdir(parents=True)
        artifacts = {}
        for name in ("best.pt", "last.pt"):
            p = folder / name
            p.write_bytes(b"x" * (30 if job["profile"] == "G0" else 60))
            artifacts[name] = sha256(p)
        write_json(folder / "receipt.json", {"status": "complete", "job": job,
            "plan_sha256": sha256(pilot_path), "artifacts": artifacts})
        # Deliberately invalid JSON; the planning path must not read metrics.
        (folder / "result.json").write_text("DO NOT READ PILOT F1")
        (folder / "outer_test_predictions.json").write_text("DO NOT READ PILOT F1")
    auth = tmp_path / "authorization.json"
    write_json(auth, {"version": bp.AUTHORIZATION_VERSION, "approved": True,
        "policy": "local_dev_v1", "authorized_scope": "prepare_batch1_150_only",
        "execution_authorized": False, "store": bp._ref(store),
        "historical_policy_approval": bp._ref(approval),
        "pilot_plan": bp._ref(pilot_path), "task_ids": list(records),
        "profiles": list(bp.PROFILES), "seeds": [1],
        "user_answer": "Approved separate preparation", "recorded_at": "2026-10-26"})
    spec = tmp_path / "report_spec.json"
    write_json(spec, {"version": bp.REPORT_VERSION})
    monkeypatch.setattr(bp, "load_manifest", lambda *a, **k: {"tasks": records})
    monkeypatch.setattr(bp, "checked_ref",
                        lambda ref: Path(ref["path"]) if ref["path"] == "mocked"
                        else run.checked_ref(ref))
    monkeypatch.setattr(bp, "load_folds",
                        lambda rec: {"k_folds": 5 if rec["task"] == "contract" else 10})
    monkeypatch.setattr(bp, "_check_report", lambda *a, **k: {})
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(bp.shutil, "disk_usage", lambda path: usage(10**12, 0, 10**12))
    return {"records": records, "store": store, "pilot_path": pilot_path, "pilot": pilot,
            "approval": approval, "authorization": auth, "spec": spec,
            "output": tmp_path / "new"}


def create(e, **extra):
    return bp.create_batch_plan(e["store"], e["output"],
        approval_record=e["approval"], authorization_record=e["authorization"],
        report_spec=e["spec"], **extra)


def test_150_stage_orders_and_fresh_constructor_no_pilot_result_reads(evidence, monkeypatch):
    e = evidence
    before = {str(p): p.read_bytes() for p in e["pilot_path"].parent.rglob("*") if p.is_file()}
    captured = {}
    def fresh(*args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return {"jobs": []}
    monkeypatch.setattr(run, "create_plan", fresh)
    create(e)
    reg = captured["kwargs"]["_batch_registration"]
    assert len(reg["jobs"]) == 150
    assert len(reg["stages"]["A"]["jobs"]) == 60
    assert len(reg["stages"]["B"]["jobs"]) == 90
    assert reg["stages"]["A"]["jobs"][:4] == [
        "reentrancy_contract/0/1/G0", "reentrancy_contract/0/1/G3R",
        "reentrancy_contract/1/1/G0", "reentrancy_contract/1/1/G3R"]
    assert reg["stages"]["B"]["jobs"][:3] == [
        "reentrancy_contract/0/1/G1R", "reentrancy_contract/0/1/G2R",
        "reentrancy_contract/0/1/G3"]
    assert captured["args"][3] == list(bp.PROFILES)
    assert reg["fresh_initial_states"] and not reg["pilot_results_reused"]
    assert not reg["execution_authorized"]
    assert not e["output"].exists()
    assert before == {str(p): p.read_bytes() for p in e["pilot_path"].parent.rglob("*") if p.is_file()}


@pytest.mark.parametrize("field,value", [
    ("approved", False), ("execution_authorized", True),
    ("authorized_scope", "all_jobs_authorized"), ("policy", "other"),
    ("user_answer", ""), ("recorded_at", ""), ("seeds", [2]),
    ("profiles", ["G0", "G3R"]), ("task_ids", list(reversed(bp.DEFAULT_TASKS))),
    ("historical_policy_approval", {"path": "other", "sha256": "other"}),
    ("store", {"path": "other", "sha256": "other"}),
])
def test_new_authorization_exact_scope_required(evidence, monkeypatch, field, value):
    e = evidence
    doc = read_json(e["authorization"])
    doc[field] = value
    write_json(e["authorization"], doc)
    monkeypatch.setattr(run, "create_plan", lambda *a, **k: pytest.fail("Prepared without authorization"))
    with pytest.raises(ValueError, match="preparation-only authorization"):
        create(e)
    assert not e["output"].exists()


def test_old_eight_job_approval_cannot_authorize_new_batch(evidence, monkeypatch):
    e = evidence
    e["authorization"] = e["approval"]
    monkeypatch.setattr(run, "create_plan", lambda *a, **k: pytest.fail("Reused pilot approval"))
    with pytest.raises(ValueError):
        create(e)


@pytest.mark.parametrize("extra", [{"profiles": ["G0", "G3R"]}, {"seeds": [2]}, {"folds": [0]},
    {"tasks": ["reentrancy_contract"]}, {"layer_impl": "original"}, {"reducer": "nonempty_mean"}])
def test_matrix_restrictions_precede_preparation(evidence, monkeypatch, extra):
    monkeypatch.setattr(run, "create_plan", lambda *a, **k: pytest.fail("Bad matrix was prepared"))
    with pytest.raises(ValueError):
        create(evidence, **extra)
    assert not evidence["output"].exists()


def test_disk_gate_before_any_output_or_model(evidence, monkeypatch):
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(bp.shutil, "disk_usage", lambda path: usage(1000, 999, 1))
    monkeypatch.setattr(run, "create_plan", lambda *a, **k: pytest.fail("Insufficient disk prepared"))
    with pytest.raises(ValueError, match="Insufficient disk"):
        create(evidence)
    assert not evidence["output"].exists()


def test_storage_estimate_includes_initials_and_two_times(evidence):
    rows = bp._pilot_sizes(evidence["pilot"], bp._ref(evidence["pilot_path"]))
    jobs = bp._matrix(list(evidence["records"]), evidence["records"])
    result = bp.estimate_storage(rows, jobs)
    assert result["estimated_checkpoint_bytes"] == 150 * 120
    assert result["estimated_initial_bytes"] == 150 * 20
    assert result["required_free_bytes"] == 2 * 150 * 140
    with pytest.raises(ValueError):
        bp.estimate_storage(rows[:-1], jobs)


def test_pilot_checkpoint_tampering_rejected_before_prepare(evidence, monkeypatch):
    e = evidence
    first = next(e["pilot_path"].parent.rglob("best.pt"))
    first.write_bytes(b"tampered")
    monkeypatch.setattr(run, "create_plan", lambda *a, **k: pytest.fail("Tampered pilot accepted"))
    with pytest.raises(ValueError, match="SHA256"):
        create(e)


def test_attach_does_not_grant_execution_or_change_training_config(evidence, monkeypatch):
    capture = {}
    monkeypatch.setattr(run, "create_plan", lambda *a, **k: capture.update(k) or {})
    create(evidence)
    plan = {"test_mode": False, "reducer": "mean", "layer_impl": "shared_projection",
            "config": {"learning_rate": "frozen"}}
    bp.attach_registration(plan, capture["_batch_registration"])
    assert plan["resource_origin"]["version"] == bp.ORIGIN_VERSION
    assert plan["config"] == {"learning_rate": "frozen"}
    assert plan["resource_policy"] == LOCAL_DEV_POLICY
    assert not plan["batch_registration"]["execution_authorized"]
    with pytest.raises(ValueError):
        bp.attach_registration(dict(plan, test_mode=True), capture["_batch_registration"])


def test_fresh_batch_cli_dispatch_and_old_path_guards(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(bp, "create_batch_plan", lambda *a, **k: calls.append((a, k)) or {"jobs": [None] * 150})
    run.main(["plan", "--store", "store.json", "--output", str(tmp_path / "new"),
        "--resource-policy", "local_dev_v1", "--approval-record", "old.json",
        "--authorization-record", "new.json", "--report-spec", "report.json",
        "--layer-impl", "shared_projection"])
    assert calls[0][1]["authorization_record"] == "new.json"
    assert calls[0][1]["report_spec"] == "report.json"
    with pytest.raises(ValueError, match="preserves"):
        run.main(["plan", "--from-plan", "old", "--output", "new", "--authorization-record", "new"])
    with pytest.raises(ValueError, match="requires --from-plan"):
        run.main(["plan", "--store", "old", "--output", "new", "--authorization-record", "new"])


@pytest.fixture
def expanded_plan(evidence, monkeypatch):
    e = evidence
    captured = {}
    monkeypatch.setattr(run, "create_plan", lambda *a, **kw: captured.update(kw) or {})
    create(e)
    reg = captured["_batch_registration"]
    plan = {"test_mode": False, "reducer": "mean", "layer_impl": "shared_projection",
            "profiles": list(bp.PROFILES), "seeds": [1], "requested_folds": None,
            "store": bp._ref(e["store"]), "selection_rule": copy.deepcopy(run.SELECTION_RULE),
            "input_manifest": read_json(e["store"])["input_manifest"],
            "initialization_version": bp.INITIALIZATION_VERSION, "tasks": {}, "jobs": bp._matrix(list(e["records"]), e["records"])}
    bp.attach_registration(plan, reg)
    store = read_json(e["store"])
    for task, record in e["records"].items():
        count = 5 if record["task"] == "contract" else 10
        info_task = {"record": record, "config": copy.deepcopy(e["pilot"]["tasks"][task]["config"]),
                     "folds": list(range(count)), "prepared": {}}
        for fold in range(count):
            folder = e["output"] / "prepared" / task / ("fold_%d" % fold) / "seed_1"
            folder.mkdir(parents=True)
            profiles = {}
            for profile in bp.PROFILES:
                initial = folder / (profile + "_initial.pt")
                initial.write_bytes(b"synthetic fresh initial")
                graph = store["tasks"][task]["graphs"][run.key_for_profile(profile)]
                profiles[profile] = {"initial": bp._ref(initial), "graph": graph["graph"],
                    "support": {"schema": graph["profiles"][profile]["schema"]}}
            info = {"profiles": profiles}
            path = folder / "task.json"
            write_json(path, info)
            info_task["prepared"]["%d/1" % fold] = bp._ref(path)
        plan["tasks"][task] = info_task
    return e, plan, e["output"] / "plan.json"


def test_registered_complete_matrix_validates_without_execution(expanded_plan):
    e, plan, path = expanded_plan
    result = bp.validate_batch_plan(plan, path)
    assert not result["execution_authorized"]
    assert len(result["stages"]["A"]["jobs"]) == 60
    assert len(result["stages"]["B"]["jobs"]) == 90


@pytest.mark.parametrize("damage", [
    "config", "fold", "stage_order", "missing_job", "duplicate_job", "profile",
    "endpoint", "selection", "execution", "pilot_reuse", "disk", "size", "authorization", "initialization_version", "input_manifest"])
def test_resealed_batch_semantic_tampering_rejected(expanded_plan, damage):
    e, plan, path = expanded_plan
    reg = plan["batch_registration"]
    if damage == "initialization_version":
        plan["initialization_version"] = "changed"
    elif damage == "input_manifest":
        plan["input_manifest"] = {"path": "wrong", "sha256": "wrong"}
    elif damage == "config":
        plan["tasks"]["reentrancy_contract"]["config"]["initial_lr"] = 123
    elif damage == "fold":
        plan["tasks"]["reentrancy_contract"]["folds"].pop()
    elif damage == "stage_order":
        reg["stages"]["A"]["jobs"].reverse()
    elif damage == "missing_job":
        plan["jobs"].pop()
    elif damage == "duplicate_job":
        plan["jobs"][-1] = copy.deepcopy(plan["jobs"][0])
    elif damage == "profile":
        plan["profiles"].reverse()
    elif damage == "endpoint":
        reg["primary_endpoint"]["checkpoint"] = "last"
    elif damage == "selection":
        reg["selection_rule"]["outer_test_used"] = True
    elif damage == "execution":
        reg["execution_authorized"] = True
    elif damage == "pilot_reuse":
        reg["pilot_results_reused"] = True
    elif damage == "disk":
        reg["storage_preflight"]["available_bytes_at_preparation"] = 1
    elif damage == "size":
        reg["pilot_size_evidence"][0]["checkpoints"]["best.pt"]["bytes"] += 1
    else:
        e["authorization"].write_bytes(e["authorization"].read_bytes() + b" ")
    with pytest.raises(ValueError):
        bp.validate_batch_plan(plan, path)


@pytest.mark.parametrize("damage", ["pilot_initial", "graph", "schema", "missing_profile"])
def test_fresh_prepared_data_cannot_point_to_other_profiles_or_pilot(expanded_plan, damage):
    e, plan, path = expanded_plan
    task = plan["tasks"]["reentrancy_contract"]
    ref = task["prepared"]["0/1"]
    info = read_json(ref["path"])
    entry = info["profiles"]["G0"]
    if damage == "pilot_initial":
        old = read_json(e["pilot"]["tasks"]["reentrancy_contract"]["prepared"]["0/1"]["path"])
        entry["initial"] = old["profiles"]["G0"]["initial"]
    elif damage == "graph":
        entry["graph"] = {"path": "wrong", "sha256": "wrong"}
    elif damage == "schema":
        entry["support"]["schema"] = {"nodes": ["wrong"], "canonical_relations": []}
    else:
        del info["profiles"]["G3"]
    write_json(ref["path"], info)
    task["prepared"]["0/1"] = bp._ref(ref["path"])
    with pytest.raises(ValueError):
        bp.validate_batch_plan(plan, path)


@pytest.fixture
def authorized_start(tmp_path):
    from scripts.DFG.dfg_v2.experiment import batch
    jobs = [dict(task_id="synthetic_node", fold=0, seed=1, profile=p,
                 layer_impl="shared_projection") for p in bp.PROFILES]
    plan = {"jobs": jobs, "batch_registration": {"stages": bp._stages(jobs)}}
    path = tmp_path / "plan.json"
    write_json(path, plan)
    job = jobs[0]
    approval = tmp_path / "stage_A.json"
    write_json(approval, {"version": batch.AUTH_VERSION, "approved": True,
        "stage": "A", "plan": bp._ref(path),
        "authorized_jobs": plan["batch_registration"]["stages"]["A"]["jobs"],
        "user_answer": "Run exact stage A", "recorded_at": "2026-10-26"})
    attempt = tmp_path / "attempt_001"
    started_path = attempt.with_suffix(".started.json")
    started = {"job": job, "plan_sha256": sha256(path),
               "execution_authorization": bp._ref(approval),
               "resume_epoch": False, "retry_from_same_untrained_initial": True,
               "retry_of": []}
    write_json(started_path, started)
    receipt = {"execution_start": bp._ref(started_path)}
    return attempt, plan, job, path, approval, started_path, started, receipt


def test_completed_receipt_approval_archive_verification(authorized_start, monkeypatch):
    from scripts.DFG.dfg_v2.experiment import batch
    attempt, plan, job, path, approval, started_path, started, receipt = authorized_start
    # Historical acceptance must not use the current failed-attempt latch.
    monkeypatch.setattr(batch, "authorize_job",
                        lambda *a, **k: pytest.fail("Live gate used for archive verification"))
    run._verify_execution_authorization(attempt, plan, job, path, receipt)


@pytest.mark.parametrize("damage", ["start_hash", "auth_hash", "job", "plan", "resume",
                                   "from_initial", "approval_scope"])
def test_completed_receipt_rejects_stage_authorization_tampering(authorized_start, damage):
    attempt, plan, job, path, approval, started_path, started, receipt = authorized_start
    if damage == "start_hash":
        started_path.write_bytes(started_path.read_bytes() + b" ")
    elif damage == "auth_hash":
        approval.write_bytes(approval.read_bytes() + b" ")
    else:
        if damage == "job":
            started["job"] = dict(job, profile="G3R")
        elif damage == "plan":
            started["plan_sha256"] = "changed"
        elif damage == "resume":
            started["resume_epoch"] = True
        elif damage == "from_initial":
            started["retry_from_same_untrained_initial"] = False
        else:
            doc = read_json(approval)
            doc["approved"] = False
            write_json(approval, doc)
            started["execution_authorization"] = bp._ref(approval)
        write_json(started_path, started)
        receipt["execution_start"] = bp._ref(started_path)
    with pytest.raises(ValueError):
        run._verify_execution_authorization(attempt, plan, job, path, receipt)


def test_existing_receipt_needs_no_new_authorization(tmp_path):
    run._verify_execution_authorization(tmp_path / "not_present", {}, {}, tmp_path / "no_plan", {})


@pytest.fixture
def selection_summary_plan(tmp_path, monkeypatch):
    jobs = [{"task_id": "synthetic_node", "fold": 0, "seed": 1, "profile": profile}
            for profile in bp.PROFILES]
    plan = {"jobs": jobs, "batch_registration": {"jobs": [run.job_id(job) for job in jobs]}}
    path = tmp_path / "plan.json"
    write_json(path, plan)
    monkeypatch.setattr(run, "_load_plan", lambda p: plan)
    selection = {"complete_matrix": True, "candidate_set_complete": True,
                 "outer_test_used": False,
                 "receipts": {run.job_id(job): {} for job in jobs}}
    return path, plan, selection


@pytest.mark.parametrize("damage", ["incomplete", "candidate", "outer", "missing_receipt", "order"])
def test_new_selection_refuses_incomplete_registered_matrix_before_writing(
        selection_summary_plan, monkeypatch, damage):
    path, plan, selection = selection_summary_plan
    if damage == "incomplete":
        selection["complete_matrix"] = False
    elif damage == "candidate":
        selection["candidate_set_complete"] = False
    elif damage == "outer":
        selection["outer_test_used"] = True
    elif damage == "missing_receipt":
        selection["receipts"].pop(next(iter(selection["receipts"])))
    else:
        plan["batch_registration"]["jobs"].reverse()
    monkeypatch.setattr(run, "_selection", lambda *args: selection)
    with pytest.raises(ValueError, match="every frozen job"):
        run.select(path)
    assert not (path.parent / "selection.json").exists()
    assert not (path.parent / "selection.seal.json").exists()


def test_new_selection_full_inner_matrix_still_seals(selection_summary_plan, monkeypatch):
    path, plan, selection = selection_summary_plan
    monkeypatch.setattr(run, "_selection", lambda *args: selection)
    assert run.select(path) == selection
    seal = read_json(path.parent / "selection.seal.json")
    assert seal["selection_sha256"] == sha256(path.parent / "selection.json")


def test_summarize_cli_dispatches_complete_report_with_raw_results(selection_summary_plan, monkeypatch):
    from scripts.DFG.dfg_v2.experiment import reporting
    path, plan, selection = selection_summary_plan
    selection["receipts"] = {}
    selected = path.parent / "selection.json"
    write_json(selected, selection)
    write_json(path.parent / "selection.seal.json", {
        "plan_sha256": sha256(path), "selection_sha256": sha256(selected)})
    result = {"status": "complete", "structural_fixture_only": True}
    identity = run.job_id(plan["jobs"][0])
    monkeypatch.setattr(run, "verify", lambda p: {"completed_jobs": 150, "results": {
        identity: {"job": plan["jobs"][0], "attempt": "synthetic", "result": result}}})
    calls = []
    def report(p, **kwargs):
        calls.append((p, kwargs))
        return {"report": {"path": "REPORT.md", "sha256": "synthetic"}}
    monkeypatch.setattr(reporting, "build_report", report)
    answer = run.main(["summarize", "--plan", str(path)])
    assert answer == {"completed_jobs": 150, "score_role": "outer_test"}
    assert calls[0][1] == {"stage": "complete", "verified_results": {identity: result}}
    summary = read_json(path.parent / "summary.json")
    assert summary["report_artifacts"]["report"]["path"] == "REPORT.md"
    with pytest.raises(FileExistsError, match="existing summary"):
        run.summarize(path)
    assert len(calls) == 1


def test_legacy_summary_does_not_dispatch_new_report(selection_summary_plan, monkeypatch):
    from scripts.DFG.dfg_v2.experiment import reporting
    path, plan, selection = selection_summary_plan
    del plan["batch_registration"]
    selection["receipts"] = {}
    selected = path.parent / "selection.json"
    write_json(selected, selection)
    write_json(path.parent / "selection.seal.json", {
        "plan_sha256": sha256(path), "selection_sha256": sha256(selected)})
    monkeypatch.setattr(run, "verify", lambda p: {"completed_jobs": 2, "results": {}})
    monkeypatch.setattr(reporting, "build_report",
                        lambda *a, **k: pytest.fail("Historical summary dispatched new reporting"))
    assert run.summarize(path)["completed_jobs"] == 2
    assert "report_artifacts" not in read_json(path.parent / "summary.json")
