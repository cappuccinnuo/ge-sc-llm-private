import copy
import json
from pathlib import Path
import pytest
import torch
from scripts.DFG.experiments.stage_i_diagnostics import common
from scripts.DFG.experiments.audit.ddg_diagnostics_v1.run_diagnostics import archived_gate
from scripts.DFG.experiments.common import metrics


def jobs():
    return [dict(task_id=t, task="contract" if t.endswith("_contract") else "node", fold=f, variant=v)
            for t in common.TASK_ORDER for f in range(5 if t.endswith("_contract") else 10)
            for v in ("E3a", "E3b")]


def test_complete_matrix():
    common.validate_jobs(jobs())


@pytest.mark.parametrize("kind", ["missing", "duplicate", "variant", "unit"])
def test_reject_wrong_matrix(kind):
    j = jobs()
    if kind == "missing": j.pop()
    if kind == "duplicate": j[-1] = j[0]
    if kind == "variant": j[0]["variant"] = "E2"
    if kind == "unit": j[0]["task"] = "node"
    with pytest.raises(ValueError): common.validate_jobs(j)


def test_frozen_scalar_relation_not_masked():
    assert common.CONDITIONS["N"] == ()
    assert not any("DATA_DEF_USE" in v for v in common.CONDITIONS.values())
    assert set(common.CONDITIONS["Z_ALL"]) == set().union(*common.CONDITIONS.values())


def test_failed_or_partial_not_retried(tmp_path):
    assert not common.verified_success(tmp_path / "absent")
    d = tmp_path / "failed"; d.mkdir()
    (d / "failure.json").write_text('{}')
    with pytest.raises(ValueError, match="explicit investigation"):
        common.verified_success(d)


def test_success_artifact_tampering_rejected(tmp_path):
    f = tmp_path / "audit.json"; f.write_text('{}')
    common.write_json(tmp_path / "receipt.json", {"status":"passed", "artifact_sha256":{"audit.json":common.file_sha(f)}})
    assert common.verified_success(tmp_path)
    f.write_text('{"changed":true}')
    with pytest.raises(ValueError, match="changed"): common.verified_success(tmp_path)


def test_archive_identity_and_metrics_gate():
    records = [dict(file="x.sol", original_graph_node_id=17, node_type="EXPRESSION", target=1)]
    logits = torch.tensor([[0., 1.]])
    prob = logits.softmax(1)[:,1].tolist()
    old = [dict(records[0], best=1, best_positive_probability=prob[0])]
    expected = metrics([1], [1])
    assert archived_gate(old, records, "node", "best", logits, prob, expected)["metrics_match"]
    wrong = copy.deepcopy(old); wrong[0]["original_graph_node_id"] = 18
    with pytest.raises(ValueError): archived_gate(wrong, records, "node", "best", logits, prob, expected)
    wrong = copy.deepcopy(old); wrong[0]["best"] = 0
    with pytest.raises(AssertionError): archived_gate(wrong, records, "node", "best", logits, prob, expected)


def test_runner_has_no_training_operations():
    import ast
    from scripts.DFG.experiments.stage_i_diagnostics import run
    tree = ast.parse(Path(run.__file__).read_text())
    names = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert not set(names).intersection({"backward", "step", "zero_grad", "train"})


@pytest.mark.parametrize("kind", ["plan", "job", "source", "missing"])
def test_reuse_requires_exact_plan_job_source_and_completeness(tmp_path, kind):
    job = dict(task_id="a", fold=1, variant="E3a", receipt_sha256="source")
    for ck in ("best", "last"):
        d = tmp_path / ck; d.mkdir()
        for name in ("scores.json", "predictions.json", "audit.json"):
            (d / name).write_text('{}')
    common.write_json(tmp_path / "metadata.json", {"job":job})
    hashes = {str(p.relative_to(tmp_path)):common.file_sha(p) for p in tmp_path.rglob("*.json")}
    receipt = dict(status="passed", plan_sha256="plan", source_receipt_sha256="source", artifact_sha256=hashes)
    if kind == "plan": receipt["plan_sha256"] = "other"
    if kind == "source": receipt["source_receipt_sha256"] = "other"
    if kind == "missing": receipt["artifact_sha256"].pop("last/audit.json")
    common.write_json(tmp_path / "receipt.json", receipt)
    if kind == "job": job = dict(job, fold=2)
    with pytest.raises(ValueError): common.verified_success(tmp_path, "plan", job)


def test_dependency_drift_is_rejected(tmp_path, monkeypatch):
    dependency = tmp_path / "computation.py"; dependency.write_text('old')
    plan = dict(version=common.VERSION, score_role=common.ROLE, inference_only=True, jobs=jobs(),
                runtime_sha256={str(dependency):common.file_sha(dependency)}, historical_sha256={}, observed_static_sha256={})
    common.write_json(tmp_path / "plan.json", plan)
    common.write_json(tmp_path / "plan.seal.json", {"plan_sha256":common.file_sha(tmp_path / "plan.json")})
    common.verify_plan(tmp_path)
    dependency.write_text('new')
    with pytest.raises(ValueError, match="dependency changed"): common.verify_plan(tmp_path)


def test_real_safe_graph_api_receives_path(tmp_path):
    import pickle
    import networkx as nx
    from scripts.labeling_v2.safe_graph import read_graph
    graph = nx.MultiDiGraph(); graph.add_node(1, node_type="X", source_file="a.sol")
    path = tmp_path / "g.gpickle"
    path.write_bytes(pickle.dumps(graph))
    assert list(read_graph(Path(str(path)))) == [1]
