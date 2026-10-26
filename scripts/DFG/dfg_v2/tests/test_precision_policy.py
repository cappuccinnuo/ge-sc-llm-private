"""Small metadata fixtures for the 7b.3 policy; no model fits or CUDA."""
import copy
import json
import sys
import types
from pathlib import Path

import pytest

from scripts.DFG.experiments.common import digest, sha256
from scripts.DFG.dfg_v2.experiment import precision_policy as pp
from scripts.DFG.dfg_v2.experiment import precision_gpu as pg
from scripts.DFG.dfg_v2.experiment import precision_real as pr


def put(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf8")
    return pp.reference(path)


def get(ref):
    return json.loads(Path(ref["path"]).read_text())


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    sources = {"frozen": "unchanged"}
    monkeypatch.setattr(pr, "_source_identity", lambda: sources)
    monkeypatch.setattr(pp, "policy_sources", lambda: {"policy": "current"})
    def static_gate(raw):
        if raw.get("status") != "passed" or raw.get("raw_failed"):
            raise ValueError("raw static failure")
    def trajectory_gate(raw):
        if raw.get("status") != "passed" or raw.get("raw_failed"):
            raise ValueError("raw numerical failure")
    monkeypatch.setattr(pr, "validate_static_evidence", static_gate)
    monkeypatch.setattr(pr, "validate_trajectory_evidence", trajectory_gate)
    # Guard mechanics have independent tests; inject its validated receipt API.
    def guard_gate(path):
        raw = json.loads(Path(path).read_text())
        if raw.get("guard_invalid"):
            raise ValueError("invalid RSS receipt")
        return raw
    fake = types.ModuleType("scripts.DFG.dfg_v2.experiment.precision_guard")
    fake.validate_guard_evidence = guard_gate
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    old, new = tmp_path/"old", tmp_path/"prompt7b3_v1"
    common = put(old/"input.json", {"immutable": True})
    split = {"inner_train_files": ["a"], "inner_val_files": ["b"], "outer_test_files": ["c"]}
    seeds = {"constructor": 10000, "fit": 1010000}
    config = {"initial_lr": .0005, "schedule_epochs": 50}
    prep = put(old/"prepared.json", dict(
        profiles={p: dict(graph=common, initial=common) for p in ("G0", "G3R")},
        split=split, seeds=seeds))
    plan = put(old/"plan.json", {"tasks": {
        t: dict(prepared={"0/1": prep}, config=config,
                record=dict(task=k, labels=common, folds=common))
        for t, k in [("reentrancy_contract", "contract"), ("access_control_node", "node")]}})
    put(old/"plan.seal.json", {"plan_sha256": plan["sha256"]})
    statics, trajectories = {}, {}
    for i, (task, profile, reducer) in enumerate(pp.CPU_CASES):
        c = (task, profile, reducer)
        raw = dict(task_id=task, task="contract" if "contract" in task else "node",
                   profile=profile, reducer=reducer, fold=0, seed=1, device="cpu",
                   dtype="float64", graph=common, initial=common, labels_ref=common,
                   folds=common, archived_plan=plan, config=config, seeds=seeds,
                   split_sha256=digest(split), sources=sources, status="passed")
        statics[c] = put(old/str(i)/"static.json", raw)
        trajectories[c] = put(old/str(i)/"trajectory.json", dict(raw, static=statics[c]))
    oom_case = ("reentrancy_contract", "G3R", "mean")
    partial = get(trajectories[oom_case])
    partial["status"] = "running"
    partial_ref = put(old/"oom"/"trajectory.json", partial)
    state = put(old/"state.json", dict(stage="trajectory", case="reentrancy_contract_G3R_mean",
                                      returncode=-9))
    kernel = old/"kernel.log"
    kernel.write_text("Out of memory: Killed process 123 (python)\n")
    failure = put(old/"resource_failure.json", dict(
        status="stopped_resource_error", case="reentrancy_contract_G3R_mean", returncode=-9,
        signal="SIGKILL", kernel_oom_confirmed=True, kernel_line=kernel.read_text().strip(),
        partial_report=partial_ref, coordinator_state=state,
        kernel_evidence=pp.reference(kernel)))
    commands = put(old/"commands.json", [[
        "python", "-m", "scripts.DFG.dfg_v2.experiment.precision_real", "trajectory",
        "--plan", plan["path"], "--output", str(old/"oom"), "--task", "reentrancy_contract",
        "--profile", "G3R", "--reducer", "mean", "--static-report", statics[oom_case]["path"]]])
    rows = []
    for i, c in enumerate(pp.CPU_CASES):
        task, profile, reducer = c
        row = dict(task_id=task, profile=profile, reducer=reducer, static=statics[c])
        if c == pp.REUSED:
            evidence = dict(kind="reused_trajectory", ref=trajectories[c])
        elif c in pp.POLICY_SKIPS:
            ref = pp.write_policy_skip(new/"skip"/(str(i)+".json"),
                statics[c]["path"], failure["path"], commands["path"])
            evidence = dict(kind="policy_skip", ref=ref)
        else:
            guard = dict(status="passed",
                case=dict(task_id=task, profile=profile, reducer=reducer),
                refs=dict(static_report=statics[c], plan=plan), trajectory=trajectories[c])
            evidence = dict(kind="rss_guard", ref=put(new/"guard"/(str(i)+".json"), guard))
        rows.append(dict(row, trajectory_evidence=evidence))
    path = new/"cpu"/"acceptance.json"
    return dict(path=path, rows=rows, statics=statics, failure=failure,
                commands=commands, old=old, new=new, plan=plan)


def build(f):
    return pp.build_acceptance(f["path"], f["rows"])


def row_for(f, c):
    return next(r for r in f["rows"] if pp._identity(r) == c)


def mutate_ref(parent, key, **updates):
    ref = parent[key]
    raw = get(ref)
    raw.update(updates)
    parent[key] = put(ref["path"], raw)


def skip_guard(f, c):
    row = row_for(f, c)
    ev = row["trajectory_evidence"]
    mutate_ref(ev, "ref", status="skipped_cpu_memory")


def test_new_policy_accepts_required_reuse_two_explicit_skips_three_passes(fixture):
    report = build(fixture)
    assert pg.validate_cpu_acceptance(fixture["path"]) == report
    assert report["schema"] == pp.SCHEMA
    kinds = [r["trajectory_evidence"]["kind"] for r in report["cases"]]
    assert kinds.count("policy_skip") == 2
    assert kinds.count("reused_trajectory") == 1
    assert kinds.count("rss_guard") == 3


@pytest.mark.parametrize("completed", sorted(pp.COVERAGE))
def test_either_required_new_dimension_may_complete(fixture, completed):
    for case in pp.GUARDED - {completed}:
        skip_guard(fixture, case)
    assert build(fixture)["status"] == "accepted"


def test_both_extra_dimensions_skipped_blocks(fixture):
    for c in pp.COVERAGE:
        skip_guard(fixture, c)
    with pytest.raises(ValueError, match="No completed"):
        build(fixture)


@pytest.mark.parametrize("case", pp.CPU_CASES)
def test_every_case_requires_explicit_record(fixture, case):
    row_for(fixture, case).pop("trajectory_evidence")
    with pytest.raises(ValueError, match="Missing explicit"):
        build(fixture)


@pytest.mark.parametrize("case", sorted(pp.GUARDED))
@pytest.mark.parametrize("status", ["failed", "execution_error", "failed_trajectory_gate", "running"])
def test_actual_failures_cannot_be_resource_skips(fixture, case, status):
    mutate_ref(row_for(fixture, case)["trajectory_evidence"], "ref", status=status)
    with pytest.raises(ValueError, match="failure blocks"):
        build(fixture)


def test_guard_rejection_propagates(fixture):
    mutate_ref(row_for(fixture, sorted(pp.GUARDED)[0])["trajectory_evidence"],
               "ref", guard_invalid=True)
    with pytest.raises(ValueError, match="invalid RSS"):
        build(fixture)


@pytest.mark.parametrize("field", ["plan", "static_report", "case"])
def test_guard_input_or_identity_swap_rejected(fixture, field):
    ev = row_for(fixture, sorted(pp.GUARDED)[0])["trajectory_evidence"]
    raw = get(ev["ref"])
    if field == "case": raw[field] = {}
    else: raw["refs"][field] = {}
    ev["ref"] = put(ev["ref"]["path"], raw)
    with pytest.raises(ValueError, match="differ"):
        build(fixture)


def test_no_unprescribed_policy_skip(fixture):
    row_for(fixture, ("access_control_node", "G0", "mean"))["trajectory_evidence"] = copy.deepcopy(
        row_for(fixture, ("reentrancy_contract", "G3R", "mean"))["trajectory_evidence"])
    with pytest.raises(ValueError, match="requires RSS"):
        build(fixture)


@pytest.mark.parametrize("change", [
    {"skip_kind": "policy_not_run"}, {"reason": "memory"},
    {"executed_this_batch": True}, {"samples": [{"rss_bytes": 8e9}]},
    {"argv": ["python"]}, {"status": "passed"}, {"policy_sources": {"policy": "changed"}},
])
def test_policy_omission_never_fakes_execution_or_pass(fixture, change):
    ev = row_for(fixture, ("reentrancy_contract", "G3R", "mean"))["trajectory_evidence"]
    mutate_ref(ev, "ref", **change)
    with pytest.raises(ValueError, match="policy skip"):
        build(fixture)


def test_skip_records_distinguish_prior_oom_and_not_attempted(fixture):
    for c, kind in pp.POLICY_SKIPS.items():
        raw = get(row_for(fixture, c)["trajectory_evidence"]["ref"])
        assert raw["skip_kind"] == kind
        assert raw["samples"] == [] and raw["argv"] is None
        assert raw["executed_this_batch"] is False


def test_static_digest_change_rejected(fixture):
    ref = fixture["rows"][0]["static"]
    put(ref["path"], {"status": "passed"})
    with pytest.raises(ValueError):
        build(fixture)


def test_raw_numeric_failure_rejected_even_when_status_passed(fixture):
    row = row_for(fixture, pp.REUSED)
    mutate_ref(row["trajectory_evidence"], "ref", raw_failed=True)
    with pytest.raises(ValueError, match="raw numerical"):
        build(fixture)


@pytest.mark.parametrize("field,value", [("config", {}), ("split_sha256", "wrong"),
                                       ("sources", {}), ("seeds", {})])
def test_static_frozen_config_split_sources_bound(fixture, field, value):
    row = fixture["rows"][0]
    mutate_ref(row, "static", **{field: value})
    with pytest.raises(ValueError):
        build(fixture)


def test_prior_oom_raw_identity_checked(fixture):
    ev = row_for(fixture, ("reentrancy_contract", "G3R", "mean"))["trajectory_evidence"]
    raw = get(ev["ref"])
    fail = get(raw["prior_failure"])
    fail["kernel_oom_confirmed"] = False
    raw["prior_failure"] = put(raw["prior_failure"]["path"], fail)
    ev["ref"] = put(ev["ref"]["path"], raw)
    with pytest.raises(ValueError, match="prior R/G3R"):
        build(fixture)


def test_prior_oom_command_checked(fixture):
    ev = row_for(fixture, ("reentrancy_contract", "G3R", "mean"))["trajectory_evidence"]
    raw = get(ev["ref"])
    commands = get(raw["prior_commands"])
    commands[0][commands[0].index("--reducer")+1] = "nonempty_mean"
    raw["prior_commands"] = put(raw["prior_commands"]["path"], commands)
    ev["ref"] = put(ev["ref"]["path"], raw)
    with pytest.raises(ValueError, match="OOM command"):
        build(fixture)


def test_no_overwrite_or_write_into_old_batch(fixture):
    with pytest.raises(ValueError, match="prompt7b3_v1"):
        pp.build_acceptance(fixture["old"]/"acceptance.json", fixture["rows"])
    build(fixture)
    with pytest.raises(FileExistsError):
        build(fixture)


def test_seal_is_required_and_bound(fixture):
    build(fixture)
    seal = fixture["path"].with_name("acceptance.seal.json")
    put(seal, {"schema": pp.SCHEMA, "acceptance_sha256": "bad"})
    with pytest.raises(ValueError, match="seal"):
        pg.validate_cpu_acceptance(fixture["path"])


def test_unknown_schema_rejected_not_legacy(fixture):
    build(fixture)
    doc = get(pp.reference(fixture["path"]))
    doc["schema"] = "some-less-strict-policy"
    put(fixture["path"], doc)
    with pytest.raises(ValueError, match="Unknown"):
        pg.validate_cpu_acceptance(fixture["path"])


def test_source_drift_after_seal_rejected(fixture, monkeypatch):
    build(fixture)
    monkeypatch.setattr(pp, "policy_sources", lambda: {"policy": "other"})
    with pytest.raises(ValueError, match="seal"):
        pg.validate_cpu_acceptance(fixture["path"])


def test_new_skip_manifest_cannot_enter_legacy_gate(fixture):
    report = build(fixture)
    report.pop("schema")
    put(fixture["path"], report)
    put(fixture["path"].with_name("acceptance.seal.json"),
        {"acceptance_sha256": sha256(fixture["path"])})
    with pytest.raises(KeyError, match="trajectory"):
        pg.validate_cpu_acceptance(fixture["path"])
