"""CPU-only synthetic acceptance cache tests; no training or old result writes."""
import json
import os
from pathlib import Path

import pytest

from scripts.DFG.dfg_v2.experiment import acceptance_cache as cache


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf8")
    return path


def ref(path):
    return dict(path=str(path.resolve()), sha256=cache._sha(path))


def fixture_case(root, index=0):
    plan = root / "plan.json"
    if not plan.exists():
        dump(plan, dict(synthetic_only=True))
        dump(root / "plan.seal.json", dict(plan_sha256=cache._sha(plan)))
    job = dict(task_id="synthetic_node", fold=index, seed=1, profile="G0")
    attempt = root / "runs" / str(index) / "attempt_001"
    attempt.mkdir(parents=True)
    authorization = dump(root / "authorization.json", dict(plan=ref(plan), synthetic_only=True))
    start = dump(attempt.with_suffix(".started.json"),
                 dict(job=job, execution_authorization=ref(authorization)))
    preflight = dump(root / "resource" / ("preflight_%d.json" % index), dict(status="passed"))
    context = dump(attempt.with_suffix(".context.json"), dict(synthetic_context=True))
    raw = attempt.with_suffix(".memory_samples.jsonl")
    raw.write_text('{"index": 0}\n', encoding="utf8")
    resources = dict(preflight=ref(preflight), context_ref=ref(context),
                     raw_samples_path=str(raw), raw_samples_sha256=cache._sha(raw))
    resource_sidecar = dump(attempt.with_suffix(".resources.json"), resources)
    # Twenty separate sample artifacts make cache hit checks nontrivial.
    for number in range(20):
        (attempt / ("sample_%02d.pt" % number)).write_bytes(bytes([number]) * 256)
    dump(attempt / "result.json", dict(status="complete", resources=resources))
    receipt = dump(attempt / "receipt.json", dict(status="complete", job=job,
        execution_start=ref(start), plan_sha256=cache._sha(plan),
        artifacts={p.name: cache._sha(p) for p in attempt.iterdir() if p.is_file()}))
    expected = {str(p): cache._sha(p) for p in attempt.iterdir() if p.is_file()}
    for p in (plan, authorization, start, preflight, context, raw, resource_sidecar):
        expected[str(p)] = cache._sha(p)
    calls = []
    accepted = dict(job=job, attempt=str(attempt), result={"status": "complete"},
                    audit={"passed": True})

    def full_verify():
        calls.append("full")
        for path, checksum in expected.items():
            if cache._sha(path) != checksum:
                raise ValueError("Synthetic full acceptance rejects changed artifact")
        return accepted

    return dict(plan=plan, job=job, attempt=attempt, full=full_verify, calls=calls,
                accepted=accepted, raw=raw, authorization=authorization,
                preflight=preflight, context=context, resource_sidecar=resource_sidecar,
                expected=expected)


def create(root, case, **kw):
    return cache.create_cache(root / "new_cache_generation", case["plan"], case["job"],
                              case["attempt"], case["full"], "validator-source-sha-v1", **kw)


def verify(anchor, case, **kw):
    options = dict(expected_seal_sha=anchor["sha256"], plan_path=case["plan"],
                   job=case["job"], attempt=case["attempt"], full_verify=case["full"],
                   acceptance_version="validator-source-sha-v1")
    options.update(kw)
    return cache.verify_cache(anchor, **options)


def test_twenty_sample_files_cache_hit_skips_full_and_weight_sha(tmp_path, monkeypatch):
    case = fixture_case(tmp_path)
    anchor = create(tmp_path, case)
    assert case["calls"] == ["full"]
    original_sha = cache._sha
    observed = []

    def checked_sha(path):
        observed.append(str(path))
        assert Path(path).suffix != ".pt", "cache hit must not read weights"
        return original_sha(path)

    monkeypatch.setattr(cache, "_sha", checked_sha)
    assert verify(anchor, case) == case["accepted"]
    assert case["calls"] == ["full"]
    assert observed
    document = json.loads(Path(anchor["path"]).read_text())
    assert len([r for r in document["dependencies"] if r["path"].endswith(".pt")]) == 20


def test_twenty_completed_jobs_each_full_once_then_cached(tmp_path):
    cases = [fixture_case(tmp_path, i) for i in range(20)]
    anchors = [create(tmp_path, c) for c in cases]
    for anchor, case in zip(anchors, cases):
        assert verify(anchor, case) == case["accepted"]
        assert case["calls"] == ["full"]
    assert len({a["path"] for a in anchors}) == 20


@pytest.mark.parametrize("mutation", ["size", "mtime", "delete"])
def test_metadata_drift_runs_full_and_stops_without_refresh(tmp_path, mutation):
    case = fixture_case(tmp_path)
    anchor = create(tmp_path, case)
    seal_bytes = Path(anchor["path"]).read_bytes()
    path = case["attempt"] / "sample_00.pt"
    if mutation == "size":
        path.write_bytes(b"changed")
    elif mutation == "delete":
        path.unlink()
    else:
        value = path.stat()
        os.utime(str(path), ns=(value.st_atime_ns, value.st_mtime_ns + 1000000))
    with pytest.raises(cache.AcceptanceCacheChanged, match="review required"):
        verify(anchor, case)
    assert case["calls"] == ["full", "full"]
    assert Path(anchor["path"]).read_bytes() == seal_bytes


@pytest.mark.parametrize("dependency", ["authorization", "preflight", "context", "raw", "resource_sidecar"])
def test_external_evidence_cannot_be_skipped(tmp_path, dependency):
    case = fixture_case(tmp_path)
    anchor = create(tmp_path, case)
    path = case[dependency]
    path.write_text(path.read_text() + " ", encoding="utf8")
    with pytest.raises(cache.AcceptanceCacheChanged):
        verify(anchor, case)
    assert case["calls"] == ["full", "full"]


def test_seal_corruption_and_untrusted_sidecar_fail_closed(tmp_path):
    case = fixture_case(tmp_path)
    anchor = create(tmp_path, case)
    path = Path(anchor["path"])
    doc = json.loads(path.read_text())
    doc["accepted"]["audit"]["passed"] = False
    dump(path, doc)
    forged = ref(path)
    with pytest.raises(ValueError, match="trusted controller anchor"):
        verify(forged, case, expected_seal_sha=anchor["sha256"])
    with pytest.raises(ValueError, match="trusted controller anchor"):
        verify(anchor, case)
    assert case["calls"] == ["full"]


@pytest.mark.parametrize("field,value", [("expected_seal_sha", None),
    ("job", {"task_id": "wrong", "fold": 0, "seed": 1, "profile": "G0"}),
    ("acceptance_version", "changed-validator")])
def test_identity_and_validator_binding(tmp_path, field, value):
    case = fixture_case(tmp_path)
    anchor = create(tmp_path, case)
    with pytest.raises(ValueError):
        verify(anchor, case, **{field: value})


def test_cache_is_exclusive_and_does_not_touch_attempt(tmp_path):
    case = fixture_case(tmp_path)
    before = {str(p): p.read_bytes() for p in case["attempt"].rglob("*") if p.is_file()}
    anchor = create(tmp_path, case)
    assert case["attempt"] not in Path(anchor["path"]).parents
    with pytest.raises(FileExistsError):
        create(tmp_path, case)
    after = {str(p): p.read_bytes() for p in case["attempt"].rglob("*") if p.is_file()}
    assert before == after
    with pytest.raises(ValueError, match="historical attempt"):
        cache.create_cache(case["attempt"] / "cache", case["plan"], case["job"],
                           case["attempt"], case["full"], "version")


@pytest.mark.parametrize("later", ["started", "duplicate_receipt"])
def test_cached_success_does_not_hide_later_attempt(tmp_path, later):
    case = fixture_case(tmp_path)
    anchor = create(tmp_path, case)
    if later == "started":
        dump(case["attempt"].parent / "attempt_002.started.json", {"job": case["job"]})
    else:
        dump(case["attempt"].parent / "attempt_002" / "receipt.json", {"status": "complete"})
    with pytest.raises(cache.AcceptanceCacheChanged):
        verify(anchor, case)
    assert case["calls"] == ["full", "full"]


def test_creation_rejects_changes_during_full_acceptance(tmp_path):
    case = fixture_case(tmp_path)

    def changed():
        value = case["full"]()
        (case["attempt"] / "sample_01.pt").write_bytes(b"changed during validation")
        return value

    with pytest.raises(cache.AcceptanceCacheChanged):
        cache.create_cache(tmp_path / "cache", case["plan"], case["job"], case["attempt"],
                           changed, "version")
    assert not list((tmp_path / "cache").rglob("acceptance_seal.json"))


def test_final_full_verification_still_rehashes_even_when_fast_stat_matches(tmp_path):
    case = fixture_case(tmp_path)
    anchor = create(tmp_path, case)
    path = case["attempt"] / "sample_00.pt"
    before = path.stat()
    path.write_bytes(b"x" * before.st_size)
    os.utime(str(path), ns=(before.st_atime_ns, before.st_mtime_ns))
    # This intentionally documents the fast stat check boundary.
    assert verify(anchor, case) == case["accepted"]
    with pytest.raises(ValueError, match="full acceptance"):
        case["full"]()


def _rebind_case(case, additional_paths=()):
    authorization = json.loads(case["authorization"].read_text())
    authorization["plan"] = ref(case["plan"])
    dump(case["authorization"], authorization)
    start = case["attempt"].with_suffix(".started.json")
    dump(start, dict(job=case["job"], execution_authorization=ref(case["authorization"])))
    receipt = json.loads((case["attempt"] / "receipt.json").read_text())
    receipt["execution_start"] = ref(start)
    receipt["plan_sha256"] = cache._sha(case["plan"])
    receipt["artifacts"] = {p.name: cache._sha(p) for p in case["attempt"].iterdir()
                            if p.is_file() and p.name != "receipt.json"}
    dump(case["attempt"] / "receipt.json", receipt)
    for path in list(case["expected"]) + list(additional_paths):
        case["expected"][str(path)] = cache._sha(path)


def test_stage_b_interim_report_markdown_remains_checked(tmp_path):
    case = fixture_case(tmp_path)
    report = dump(tmp_path / "report.json", {"status": "complete"})
    markdown = tmp_path / "REPORT.md"
    markdown.write_text("Frozen interim report", encoding="utf8")
    interim = dump(tmp_path / "batch_records" / "interim_A.json",
        {"report_files": {"report.json": ref(report), "REPORT.md": ref(markdown)}})
    authorization = json.loads(case["authorization"].read_text())
    authorization.update(stage="B", interim_receipt=ref(interim))
    dump(case["authorization"], authorization)
    _rebind_case(case, [interim, report, markdown])
    anchor = create(tmp_path, case)
    records = json.loads(Path(anchor["path"]).read_text())["dependencies"]
    assert {str(interim), str(report), str(markdown)} <= {r["path"] for r in records}
    markdown.write_text("Changed interim report", encoding="utf8")
    with pytest.raises(cache.AcceptanceCacheChanged):
        verify(anchor, case)


def test_updated_historical_prompt_provenance_is_not_a_current_dependency(tmp_path):
    case = fixture_case(tmp_path)
    prompt = tmp_path / "PROMPTS.md"
    prompt.write_text("Stage A historical instructions", encoding="utf8")
    authorization = json.loads(case["authorization"].read_text())
    authorization.update(stage="A", provenance={"source_prompt": ref(prompt)})
    dump(case["authorization"], authorization)
    _rebind_case(case)
    # This is the real regression: provenance accurately records old bytes,
    # while the user legitimately updates the same document for the next stage.
    prompt.write_text("New Stage B instructions", encoding="utf8")
    anchor = create(tmp_path, case)
    records = json.loads(Path(anchor["path"]).read_text())["dependencies"]
    assert str(prompt) not in {r["path"] for r in records}
    prompt.write_text("Further clarified Stage B instructions", encoding="utf8")
    assert verify(anchor, case) == case["accepted"]
    assert case["calls"] == ["full"]


@pytest.mark.parametrize("changed", ["prepared", "graph", "initial", "labels", "folds"])
def test_exact_prepared_task_input_dependencies_remain_bound(tmp_path, changed):
    case = fixture_case(tmp_path)
    graph = tmp_path / "graph.gpickle"
    initial = tmp_path / "untrained.pt"
    graph.write_bytes(b"synthetic graph")
    initial.write_bytes(b"synthetic untrained initial")
    labels = dump(tmp_path / "labels.json", {"sample.sol": 1})
    folds = dump(tmp_path / "folds.json", {"train": ["sample.sol"]})
    prepared = dump(tmp_path / "prepared.json",
        {"profiles": {"G0": {"graph": ref(graph), "initial": ref(initial)}}})
    plan = json.loads(case["plan"].read_text())
    plan["tasks"] = {case["job"]["task_id"]: {
        "prepared": {"0/1": ref(prepared)},
        "record": {"labels": ref(labels), "folds": ref(folds)}}}
    dump(case["plan"], plan)
    paths = dict(prepared=prepared, graph=graph, initial=initial, labels=labels, folds=folds)
    _rebind_case(case, paths.values())
    anchor = create(tmp_path, case)
    records = json.loads(Path(anchor["path"]).read_text())["dependencies"]
    assert {str(p) for p in paths.values()} <= {r["path"] for r in records}
    path = paths[changed]
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(cache.AcceptanceCacheChanged):
        verify(anchor, case)


def test_every_receipt_artifact_is_bound_even_if_it_is_markdown(tmp_path):
    case = fixture_case(tmp_path)
    markdown = case["attempt"] / "artifact.md"
    markdown.write_text("Retained run artifact", encoding="utf8")
    _rebind_case(case, [markdown])
    anchor = create(tmp_path, case)
    markdown.write_text("Changed artifact", encoding="utf8")
    with pytest.raises(cache.AcceptanceCacheChanged):
        verify(anchor, case)


@pytest.mark.parametrize("bad_value", [None, {}, {"audit": {"passed": False}}])
def test_cache_requires_successful_full_independent_audit(tmp_path, bad_value):
    case = fixture_case(tmp_path)
    with pytest.raises(ValueError, match="incomplete, failed or misbound"):
        cache.create_cache(tmp_path / "cache", case["plan"], case["job"],
                           case["attempt"], lambda: bad_value, "version")


@pytest.mark.parametrize("with_failure", [False, True])
def test_creation_rejects_newer_started_attempt_already_present(tmp_path, with_failure):
    case = fixture_case(tmp_path)
    dump(case["attempt"].parent / "attempt_002.started.json", {"job": case["job"]})
    if with_failure:
        dump(case["attempt"].parent / "attempt_002.failure.json", {"error": "retained"})
    with pytest.raises(ValueError, match="Newer started/incomplete"):
        create(tmp_path, case)
    assert case["calls"] == []


@pytest.mark.parametrize("changed", ["amendment", "amendment_seal", "proof", "evidence", "ticket"])
def test_amended_execution_binds_proof_and_ticket_but_not_nested_cache_refs(tmp_path, changed):
    case = fixture_case(tmp_path)
    evidence = tmp_path / "proof_result.pt"
    evidence.write_bytes(b"synthetic verified proof evidence")
    proof = dump(tmp_path / "proof.json", {"jobs": [{"refs": {"weights": ref(evidence)}}]})
    amendment = dump(tmp_path / "amendment.json", {"equivalence_proof": ref(proof)})
    amendment_seal = dump(tmp_path / "amendment.seal.json",
                          {"amendment_sha256": cache._sha(amendment)})
    ticket = dump(tmp_path / "ticket.json", {"completed": {
        "old/job": {"path": str(tmp_path / "unavailable_old_cache.json"), "sha256": "0" * 64}}})
    start = case["attempt"].with_suffix(".started.json")
    started = json.loads(start.read_text())
    started.update(runtime_amendment=ref(amendment), execution_ticket=ref(ticket))
    dump(start, started)
    receipt_path = case["attempt"] / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["execution_start"] = ref(start)
    dump(receipt_path, receipt)
    paths = dict(amendment=amendment, amendment_seal=amendment_seal,
                 proof=proof, evidence=evidence, ticket=ticket)
    for path in [start, receipt_path] + list(paths.values()):
        case["expected"][str(path)] = cache._sha(path)
    anchor = create(tmp_path, case)
    records = json.loads(Path(anchor["path"]).read_text())["dependencies"]
    assert {str(p) for p in paths.values()} <= {r["path"] for r in records}
    target = paths[changed]
    target.write_bytes(target.read_bytes() + b" changed")
    with pytest.raises(cache.AcceptanceCacheChanged):
        verify(anchor, case)
