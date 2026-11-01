"""Executor binding tests use disposable sealed inputs and own-module doubles.

Frozen modules are never patched. Real 8H construction/fit equivalence is an
additional acceptance run, not replaced by these orchestration unit tests.
"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from scripts.node_sem import execution as ns
from scripts.node_sem import TOKEN_IDS
from scripts.node_sem.feature_spec import FeatureSpec
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref, checked, read, write
from scripts.DFG.dfg_v2.experiment.init import seeds
from scripts.DFG.experiments.common import digest


def inputs(tmp_path, monkeypatch, name="S0"):
    def save(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf8")
        return ref(path)
    base = save("bound.json", {"evidence": "fixture"})
    spec = FeatureSpec(name, "anonymous",
        [dict(name=TOKEN_IDS, dim=512, manifest=base, normalize=False)],
        "raw_linear" if name == "S0" else "embed_pool",
        "raw_linear" if name == "S0" else "concat")
    spec_ref = save("spec.json", spec.to_json())
    initial = dict(base, state_sha256="b" * 64)
    split = dict(fold=0, inner_train_files=["train.sol"], inner_val_files=["val.sol"],
                 outer_test_files=["test.sol"])
    source_job = dict(task_id="fixture_node", fold=0, seed=1, profile="G0")
    cfg = dict(layer_impl="shared_projection", device="cuda:0")
    info = dict(task_id="fixture_node", fold=0, seed=1, seeds=seeds("node", 0),
                split=split, initialization=base,
                profiles={"G0": dict(graph=base, initial=initial, support={"schema": []})})
    prepared = save("prepared.json", info)
    source = dict(jobs=[source_job], source_preparation=base,
        tasks={"fixture_node": dict(config=cfg, feature_view=base, label_view=base,
            record=dict(labels=base, folds=base, graph_files=["train.sol", "val.sol", "test.sol"]),
            prepared={"0/1": prepared})})
    source_ref = save("h8.json", source)
    def source_reader(reference):
        checked(reference)
        return read(reference["path"])
    monkeypatch.setattr(ns, "_source_plan", source_reader)
    monkeypatch.setattr(ns, "ARTIFACT_ROOT", tmp_path)
    monkeypatch.setattr(ns, "runtime_refs", lambda: {"runtime.py": "a" * 64})
    job = dict(source_job, granularity="node", spec=spec_ref, spec_sha256=spec.digest(),
        config=cfg, seeds=info["seeds"], split=split,
        graph_files=["train.sol", "val.sol", "test.sol"], support={"schema": []},
        reuse_8h=name == "S0", receipt=base, h8_initial=initial, initial=initial,
        initialization=base, graph=base, labels=base, folds=base, label_view=base,
        feature_view=base, feature_npz=base, source_preparation=base)
    return dict(source_h8_plan=source_ref, jobs=[job]), dict(
        execution_authorized=False, scope="cpu_equivalence", user_request="fixture CPU acceptance")


def test_create_load_seal_authorization_and_no_overwrite(tmp_path, monkeypatch):
    matrix, auth = inputs(tmp_path, monkeypatch)
    batch = tmp_path / "batch"
    created = ns.create(batch, matrix, auth)
    assert ns.load(batch / "plan.json") == created
    assert created["jobs"][0]["reuse_8h"]
    assert read(batch / "authorization.json")["execution_authorized"] is False
    with pytest.raises(FileExistsError):
        ns.create(batch, matrix, auth)


@pytest.mark.parametrize("key", ["graph", "folds", "labels", "label_view", "feature_npz", "initial"])
def test_bound_file_tampering_rejected_before_execution(tmp_path, monkeypatch, key):
    matrix, auth = inputs(tmp_path, monkeypatch)
    matrix["jobs"][0][key] = dict(matrix["jobs"][0][key], sha256="c" * 64)
    with pytest.raises(ValueError):
        ns.create(tmp_path / "batch", matrix, auth)
    assert not (tmp_path / "batch").exists()


def test_wrong_spec_and_duplicate_jobs_rejected(tmp_path, monkeypatch):
    matrix, auth = inputs(tmp_path, monkeypatch)
    wrong = copy.deepcopy(matrix)
    wrong["jobs"][0]["spec_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="specification"):
        ns.create(tmp_path / "wrong", wrong, auth)
    matrix["jobs"].append(copy.deepcopy(matrix["jobs"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        ns.create(tmp_path / "duplicate", matrix, auth)


def test_runtime_plan_and_authorization_changes_rejected(tmp_path, monkeypatch):
    matrix, auth = inputs(tmp_path, monkeypatch)
    ns.create(tmp_path / "batch", matrix, auth)
    path = tmp_path / "batch" / "plan.json"
    monkeypatch.setattr(ns, "runtime_refs", lambda: {"runtime.py": "changed"})
    with pytest.raises(ValueError, match="runtime"):
        ns.load(path)
    monkeypatch.setattr(ns, "runtime_refs", lambda: {"runtime.py": "a" * 64})
    authorization = path.with_name("authorization.json")
    authorization.write_text("{}")
    with pytest.raises(ValueError):
        ns.load(path)
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="seal"):
        ns.load(path)


def test_formal_fit_denied_for_acceptance_plan(tmp_path, monkeypatch):
    matrix, auth = inputs(tmp_path, monkeypatch, "S1")
    ns.create(tmp_path / "batch", matrix, auth)
    with pytest.raises(PermissionError, match="not been authorized"):
        ns.fit_one(tmp_path / "batch" / "plan.json", matrix["jobs"][0])
    assert not (tmp_path / "batch" / "runs").exists()


def test_s0_fit_only_verifies_never_trains(tmp_path, monkeypatch):
    matrix, auth = inputs(tmp_path, monkeypatch)
    ns.create(tmp_path / "batch", matrix, auth)
    calls = []
    monkeypatch.setattr(ns, "verify_one", lambda *args: calls.append(args[2]) or "verified")
    monkeypatch.setattr(ns, "fit", lambda *args, **kwargs: pytest.fail("S0 must not fit"))
    assert ns.fit_one(tmp_path / "batch" / "plan.json", matrix["jobs"][0]) == "verified"
    assert calls == matrix["jobs"]


def test_failed_fit_retained_no_automatic_retry(tmp_path, monkeypatch):
    matrix, _ = inputs(tmp_path, monkeypatch, "S1")
    job = matrix["jobs"][0]
    folder = tmp_path / "runs"
    folder.mkdir()
    assert ns._next_attempt(tmp_path / "plan.json", job, folder).name == "attempt_001"
    failure = folder / "attempt_001.failure.json"
    failure.write_text('{"error":"OOM"}')
    before = failure.read_bytes()
    with pytest.raises(RuntimeError, match="explicit retry"):
        ns._next_attempt(tmp_path / "plan.json", job, folder)
    assert failure.read_bytes() == before


def test_worker_log_does_not_consume_attempt_but_exclusive_creation_protects_old_log(tmp_path, monkeypatch):
    matrix, _ = inputs(tmp_path, monkeypatch)
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "attempt_001.worker.log").write_text("worker started")
    assert ns._next_attempt(tmp_path / "plan.json", matrix["jobs"][0], folder).name == "attempt_001"
    with pytest.raises(FileExistsError):
        (folder / "attempt_001.worker.log").open("x")


def test_duplicate_successes_rejected(tmp_path):
    for name in ("attempt_001", "attempt_002"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "receipt.json").write_text("{}")
    with pytest.raises(ValueError, match="Duplicate"):
        ns._successful(tmp_path)


def test_carrier_manifest_and_vector_binding(tmp_path):
    import networkx as nx
    graph = nx.MultiDiGraph()
    graph.add_node(0, token=np.array([1, 2], dtype=np.float32))
    array = tmp_path / "carrier.npz"
    np.savez_compressed(str(array), features=np.array([[1, 2]], dtype=np.float32))
    record = dict(spec_sha256="a" * 64, rows=[{"row_key": "n"}])
    manifest = tmp_path / "carrier.json"
    manifest.write_text(json.dumps(dict(record, data=ref(array))))
    job = dict(feature_view=ref(manifest), feature_npz=ref(array))
    model = SimpleNamespace(nodesem_carrier_record=record, nx_graph=graph, original_graph_node_ids=["n"])
    ns._validate_carrier(model, job)
    graph.nodes[0]["token"][0] = 99
    with pytest.raises(ValueError, match="features"):
        ns._validate_carrier(model, job)


def test_binding_model_support_and_identity_are_not_bypassed(tmp_path, monkeypatch):
    matrix, auth = inputs(tmp_path, monkeypatch)
    plan = dict(jobs=matrix["jobs"])
    job = copy.deepcopy(matrix["jobs"][0])
    job["fold"] = 1
    with pytest.raises(ValueError, match="exact sealed"):
        ns.construct(plan, job)


def test_s1_initial_must_copy_bound_h8_common_parameters(tmp_path, monkeypatch):
    import torch
    matrix, _ = inputs(tmp_path, monkeypatch, "S1")
    job = matrix["jobs"][0]
    job["initial"] = dict(job["initial"], state_sha256="e" * 64)
    spec = FeatureSpec.from_json(read(job["spec"]["path"]))
    monkeypatch.setattr(ns, "_validate_job", lambda *args: spec)
    def initial(reference, *args):
        value = 2.0 if reference == job["initial"] else 1.0
        return dict(state_dict={"classify.weight": torch.tensor([value])})
    monkeypatch.setattr(ns, "checked_initial", initial)
    monkeypatch.setattr(ns, "make_nodesem_model",
                        lambda *args, **kwargs: pytest.fail("Mismatched initial must fail before construction"))
    with pytest.raises(ValueError, match="common parameters"):
        ns.construct(dict(jobs=[job]), job)


def test_resealed_invalid_authorization_still_rejected(tmp_path, monkeypatch):
    matrix, auth = inputs(tmp_path, monkeypatch)
    batch = tmp_path / "batch"
    ns.create(batch, matrix, auth)
    plan_path = batch / "plan.json"
    plan = read(plan_path)
    authorization = read(batch / "authorization.json")
    authorization["execution_authorized"] = "yes"
    (batch / "authorization.json").write_text(json.dumps(authorization))
    plan["authorization"] = ref(batch / "authorization.json")
    plan_path.write_text(json.dumps(plan))
    seal = read(batch / "plan.seal.json")
    seal["plan"] = ref(plan_path)
    (batch / "plan.seal.json").write_text(json.dumps(seal))
    with pytest.raises(ValueError, match="authorization"):
        ns.load(plan_path)


@pytest.mark.parametrize("field", [
    "task_id", "task", "fold", "seed", "profile", "source_preparation",
    "initial_weights_sha256", "initial_state_sha256", "support_sha256",
    "score_role", "selection_role", "forward_scope", "feature_spec_sha256",
])
def test_explicit_binding_identity_rejects_rebound_metadata(tmp_path, monkeypatch, field):
    matrix, _ = inputs(tmp_path, monkeypatch)
    job = matrix["jobs"][0]
    plan = dict(reducer="mean", layer_impl="shared_projection", label_policy="L-audit")
    spec = FeatureSpec.from_json(read(job["spec"]["path"]))
    binding = dict(
        protocol="dfg-v2-grouped-nested", protocol_version="dfg-v2-grouped-nested-v1",
        score_role="outer_test", selection_role="inner_val", forward_scope="full_fixed_task_graph",
        task_id=job["task_id"], task="node", fold=0, seed=1, profile="G0",
        reducer="mean", layer_impl="shared_projection",
        initial_weights_sha256=job["initial"]["sha256"],
        initial_state_sha256=job["initial"]["state_sha256"],
        support_sha256=digest(job["support"]), effective_config_sha256=digest(job["config"]),
        initialization=job["initialization"], source_preparation=job["source_preparation"],
        label_policy="L-audit", label_view=job["label_view"],
        feature_view=job["feature_view"], feature_npz=job["feature_npz"],
        graph=job["graph"], folds=job["folds"], labels=job["labels"], split=job["split"],
        registered_schema=job["support"]["schema"],
        nodesem_version="nodesem-v1", feature_spec=spec.to_json(),
        feature_spec_sha256=spec.digest())
    ns._validate_nodesem_binding(binding, plan, job)
    binding[field] = "wrong"
    with pytest.raises(ValueError, match=field):
        ns._validate_nodesem_binding(binding, plan, job)
