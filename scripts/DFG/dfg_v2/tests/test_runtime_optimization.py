"""CPU-only execution-ticket and final-acceptance integration regressions."""
import copy
import json
from pathlib import Path

import pytest

from scripts.DFG.dfg_v2.experiment import batch, run, acceptance_cache
from scripts.DFG.dfg_v2.tests.test_acceptance_cache import fixture_case
from scripts.DFG.dfg_v2.tests.test_experiment_run import graph_store, CONFIG


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf8")
    return path


@pytest.fixture
def ticket_case(tmp_path, monkeypatch):
    jobs = [dict(task_id="synthetic_node", fold=0, seed=1, profile=profile)
            for profile in ("G0", "G3R", "G1R", "G2R", "G3")]
    plan = dict(jobs=jobs, test_mode=True,
        files=["synthetic_%02d.sol" % i for i in range(20)],
        batch_registration={"stages": {
            stage: dict(profiles=profiles,
                jobs=[run.job_id(j) for j in jobs if j["profile"] in profiles])
            for stage, profiles in (("A", ["G0", "G3R"]), ("B", ["G1R", "G2R", "G3"]))}})
    path = dump(tmp_path / "batch" / "plan.json", plan)
    interim = dump(path.parent / "batch_records" / "interim_A.json",
        dict(version=batch.VERSION, stage="A", status="complete",
             plan_sha256=batch.sha256(path), report_files={}))
    amendment = dump(tmp_path / "amendment.json", dict(synthetic_only=True))
    decision = dict(version=batch.AUTH_VERSION, approved=True, stage="B",
        plan=batch._ref(path), authorized_jobs=plan["batch_registration"]["stages"]["B"]["jobs"],
        user_answer="synthetic test approval only", recorded_at="synthetic",
        interim_receipt=batch._ref(interim), amendment=batch._ref(amendment))
    authorization = dump(tmp_path / "authorization.json", decision)
    pid, start_time = 12345, "101010"
    monkeypatch.setattr(batch.os, "getppid", lambda: pid)
    monkeypatch.setattr(batch, "_process_start", lambda p: start_time)
    invocation = dump(path.parent / "batch_records" / "executions" / "B" / "invocation_001" / "started.json",
        dict(pid=pid, stage="B", plan=batch._ref(path), authorization=batch._ref(authorization)))
    job = jobs[2]
    ticket = dict(version=batch.TICKET_VERSION, parent_pid=pid, parent_start=start_time,
        plan=batch._ref(path), job=run.job_id(job), authorization=batch._ref(authorization),
        amendment=batch._ref(amendment), invocation_start=batch._ref(invocation), completed={})
    ticket_path = dump(tmp_path / "execution_ticket.json", ticket)
    return dict(path=path, plan=plan, job=job, amendment=amendment,
        authorization=authorization, decision=decision, invocation=invocation,
        ticket=ticket, ticket_path=ticket_path)


def validate(case, ticket_sha=None):
    return batch.validate_execution_ticket(
        case["ticket_path"], ticket_sha or batch.sha256(case["ticket_path"]),
        case["path"], case["plan"], case["job"], case["authorization"], case["amendment"])


def test_ticket_live_parent_positive_binding(ticket_case):
    c = ticket_case
    assert validate(c) == c["ticket"]


@pytest.mark.parametrize("field,value", [
    ("version", "wrong"), ("parent_pid", 999), ("parent_start", "old-pid-start"),
    ("plan", {}), ("job", "synthetic_node/9/1/G1R"), ("authorization", {}),
    ("amendment", {}), ("completed", None),
    ("completed", {"foreign/0/1/G0": {"path": "none", "sha256": "0" * 64}})])
def test_ticket_rejects_parent_identity_and_anchor_schema(ticket_case, field, value):
    c = ticket_case
    changed = copy.deepcopy(c["ticket"])
    changed[field] = value
    dump(c["ticket_path"], changed)
    with pytest.raises(ValueError):
        validate(c)


def test_ticket_rejects_changed_bytes_against_supplied_sha(ticket_case):
    c = ticket_case
    trusted = batch.sha256(c["ticket_path"])
    c["ticket_path"].write_text(c["ticket_path"].read_text() + " ")
    with pytest.raises(ValueError, match="SHA"):
        validate(c, trusted)


@pytest.mark.parametrize("field,value", [("pid", 999), ("stage", "A"), ("plan", {}), ("authorization", {})])
def test_ticket_rejects_misbound_invocation_even_after_rehash(ticket_case, field, value):
    c = ticket_case
    first = json.loads(c["invocation"].read_text())
    first[field] = value
    dump(c["invocation"], first)
    ticket = copy.deepcopy(c["ticket"])
    ticket["invocation_start"] = batch._ref(c["invocation"])
    dump(c["ticket_path"], ticket)
    with pytest.raises(ValueError, match="invocation"):
        validate(c)


@pytest.mark.parametrize("wrong", ["missing", "different"])
def test_stage_authorization_must_bind_same_amendment(ticket_case, wrong):
    c = ticket_case
    decision = copy.deepcopy(c["decision"])
    if wrong == "missing":
        decision.pop("amendment")
    else:
        other = dump(c["amendment"].with_name("other_amendment.json"), {"different": True})
        decision["amendment"] = batch._ref(other)
    dump(c["authorization"], decision)
    # Refresh ordinary auth/invocation references, so only amendment disagreement
    # remains. No stale file checksum should be the reason this test rejects.
    invocation = json.loads(c["invocation"].read_text())
    invocation["authorization"] = batch._ref(c["authorization"])
    dump(c["invocation"], invocation)
    ticket = copy.deepcopy(c["ticket"])
    ticket["authorization"] = batch._ref(c["authorization"])
    ticket["invocation_start"] = batch._ref(c["invocation"])
    dump(c["ticket_path"], ticket)
    with pytest.raises(ValueError, match="[Aa]mendment"):
        validate(c)


def test_cached_completed_uses_explicit_trusted_parent_ref(tmp_path, monkeypatch):
    c = fixture_case(tmp_path)
    anchor = acceptance_cache.create_cache(tmp_path / "new_generation",
        c["plan"], c["job"], c["attempt"], c["full"], batch._acceptance_version())
    monkeypatch.setattr(run, "_job_directory", lambda root, job: c["attempt"].parent)

    def forbidden(*args, **kwargs):
        raise AssertionError("cache hit repeated full acceptance")

    monkeypatch.setattr(batch, "_accept", forbidden)
    ticket = {"completed": {run.job_id(c["job"]): anchor}}
    assert batch._ticket_completed(c["plan"], {}, c["job"], ticket) == (
        c["attempt"], c["accepted"]["result"])
    assert c["calls"] == ["full"]


def test_receipt_without_controller_anchor_is_rejected(tmp_path, monkeypatch):
    c = fixture_case(tmp_path)
    monkeypatch.setattr(run, "_job_directory", lambda root, job: c["attempt"].parent)
    with pytest.raises(ValueError, match="no live-controller"):
        batch._ticket_completed(c["plan"], {}, c["job"], {"completed": {}})


def test_new_started_attempt_cannot_hide_behind_cached_success(tmp_path, monkeypatch):
    c = fixture_case(tmp_path)
    anchor = acceptance_cache.create_cache(tmp_path / "new_generation",
        c["plan"], c["job"], c["attempt"], c["full"], batch._acceptance_version())
    monkeypatch.setattr(run, "_job_directory", lambda root, job: c["attempt"].parent)
    monkeypatch.setattr(batch, "_accept", lambda *args: c["full"]())
    dump(c["attempt"].parent / "attempt_002.started.json", {"job": c["job"]})
    with pytest.raises(acceptance_cache.AcceptanceCacheChanged):
        batch._ticket_completed(c["plan"], {}, c["job"],
                               {"completed": {run.job_id(c["job"]): anchor}})
    assert c["calls"] == ["full", "full"]


def test_failed_started_job_still_blocks_authorization(ticket_case, monkeypatch):
    c = ticket_case
    failed = c["plan"]["jobs"][0]
    monkeypatch.setattr(batch, "_attempts",
        lambda p, j: [Path("failed.started.json")] if j == failed else [])
    monkeypatch.setattr(batch, "_ticket_completed", lambda *args: None)
    with pytest.raises(RuntimeError, match="failed/incomplete"):
        batch.authorize_job(c["path"], c["plan"], c["job"],
                            c["authorization"], execution_ticket=c["ticket"])


def test_amended_stage_a_allows_readonly_full_verify_but_not_execute(ticket_case, monkeypatch):
    c = ticket_case
    loads, accepted = [], []

    def load(path, **kwargs):
        loads.append(kwargs.get("amendment_path"))
        return c["plan"]

    def accept(path, plan, job):
        accepted.append(run.job_id(job))
        return dict(job=job, attempt="synthetic", result={}, audit={"passed": True})

    monkeypatch.setattr(run, "_load_plan", load)
    monkeypatch.setattr(batch, "_accept", accept)
    monkeypatch.setattr(batch, "_ticket_completed",
        lambda *args: pytest.fail("final verification used cached path"))
    result = batch.verify_stage(c["path"], "A", amendment_path=c["amendment"])
    assert result["completed_jobs"] == 2
    assert accepted == c["plan"]["batch_registration"]["stages"]["A"]["jobs"]
    assert loads == [c["amendment"]]
    with pytest.raises(ValueError, match="stage B only"):
        batch.execute(c["path"], "A", c["authorization"], amendment_path=c["amendment"])
    with pytest.raises(ValueError, match="stage B controller"):
        run.execute(c["path"], only=run.job_id(c["plan"]["jobs"][0]), allow_cpu_test=True,
                    execution_authorization=c["authorization"], amendment_path=c["amendment"],
                    execution_ticket=c["ticket_path"], ticket_sha256=batch.sha256(c["ticket_path"]))


def test_final_verify_checks_each_job_without_cache(ticket_case, monkeypatch):
    c = ticket_case
    checked_jobs = []
    monkeypatch.setattr(run, "_load_plan", lambda path, **kwargs: c["plan"])

    def completed(output, plan, job, plan_path):
        checked_jobs.append(run.job_id(job))
        return Path("synthetic"), {"status": "complete"}

    monkeypatch.setattr(run, "_completed", completed)
    monkeypatch.setattr(batch, "_ticket_completed",
        lambda *args: pytest.fail("final verification used cache"))
    result = run.verify(c["path"], amendment_path=c["amendment"])
    assert result["completed_jobs"] == len(c["plan"]["jobs"])
    assert checked_jobs == [run.job_id(j) for j in c["plan"]["jobs"]]


def test_select_full_integrity_precedes_inner_only_selection(ticket_case, monkeypatch):
    c = ticket_case
    events = []
    monkeypatch.setattr(run, "_load_plan", lambda path, **kwargs: c["plan"])

    def verify(*args, **kwargs):
        events.append("full")
        raise ValueError("incomplete matrix")

    monkeypatch.setattr(run, "verify", verify)
    monkeypatch.setattr(run, "_selection", lambda *args: events.append("selection"))
    with pytest.raises(ValueError, match="incomplete"):
        run.select(c["path"], amendment_path=c["amendment"])
    assert events == ["full"]
    assert not (c["path"].parent / "selection.json").exists()


def test_twenty_file_cpu_results_final_verify_and_select_rehash(graph_store, tmp_path, monkeypatch):
    monkeypatch.setattr(run, "_code_refs", lambda: {"fixture": "frozen"})
    plan_path = tmp_path / "synthetic_batch" / "plan.json"
    plan = run.create_plan(graph_store, plan_path.parent, tasks=["synthetic_contract"],
        profiles=["G0", "G3R"], folds=[0], test_mode=True, test_config=CONFIG)
    assert len(plan["tasks"]["synthetic_contract"]["record"]["graph_files"]) == 20
    outcomes = run.execute(plan_path, allow_cpu_test=True)
    assert len(outcomes) == 2
    verifier = run._verify_attempt
    calls = []

    def full(*args, **kwargs):
        calls.append(args[2])
        return verifier(*args, **kwargs)

    monkeypatch.setattr(run, "_verify_attempt", full)
    monkeypatch.setattr(acceptance_cache, "verify_cache",
        lambda *args, **kwargs: pytest.fail("final integrity used fast acceptance cache"))
    assert run.verify(plan_path)["completed_jobs"] == 2
    assert len(calls) == 2

    selection = run._selection
    read_json = run.read_json

    def inner_only(plan, directory):
        def forbid_outer_in_choice(path):
            assert Path(path).name not in ("result.json", "outer_test_predictions.json")
            return read_json(path)
        with monkeypatch.context() as local:
            local.setattr(run, "read_json", forbid_outer_in_choice)
            return selection(plan, directory)

    monkeypatch.setattr(run, "_selection", inner_only)
    selected = run.select(plan_path)
    assert selected["outer_test_used"] is False
    assert len(calls) == 4
    assert run.summarize(plan_path)["completed_jobs"] == 2
    assert len(calls) == 6


def test_restart_cannot_cache_old_success_after_a_newer_started_attempt(tmp_path):
    c = fixture_case(tmp_path)
    dump(c["attempt"].parent / "attempt_002.started.json", {"job": c["job"]})
    dump(c["attempt"].parent / "attempt_002.failure.json", {"reason": "synthetic failure"})
    with pytest.raises(ValueError, match="started|incomplete|successful"):
        acceptance_cache.create_cache(tmp_path / "new_generation",
            c["plan"], c["job"], c["attempt"], c["full"], batch._acceptance_version())


def test_earlier_failed_attempt_does_not_invalidate_later_verified_success(tmp_path):
    c = fixture_case(tmp_path)
    dump(c["attempt"].parent / "attempt_000.started.json", {"job": c["job"]})
    dump(c["attempt"].parent / "attempt_000.failure.json", {"reason": "older failure"})
    anchor = acceptance_cache.create_cache(tmp_path / "new_generation",
        c["plan"], c["job"], c["attempt"], c["full"], batch._acceptance_version())
    assert acceptance_cache.verify_cache(anchor, expected_seal_sha=anchor["sha256"],
        plan_path=c["plan"], job=c["job"], attempt=c["attempt"], full_verify=c["full"],
        acceptance_version=batch._acceptance_version()) == c["accepted"]
