"""Fail-closed acceptance and sealed input tests for Prompt 8E."""
import copy
import math
import pytest

from scripts.DFG.dfg_v2.benchmark_v2.acceptance_real import gate_failures, binary_metrics, compare_metrics
from scripts.DFG.dfg_v2.benchmark_v2.prepare_real import load_naming
from scripts.DFG.dfg_v2.benchmark_v2.prepare import write, ref


def summary(delta=5.0, auc=0.60):
    return dict(P1={"N-real": dict(passed=True)},
                P2={"N-real": {"reentrancy_node": {"orig": dict(
                    pooled={"buggy_f1": 50.0+delta}, all_positive={"buggy_f1": 50.0})}}},
                P3={"N-real": dict(auc=auc)})


def test_exact_preregistered_boundaries_pass():
    assert gate_failures(summary()) == []


@pytest.mark.parametrize("delta,auc,probe", [(5.00001, .60, "P2"), (5., .600001, "P3")])
def test_gate_failure_cannot_be_overridden_by_passed_flag(delta, auc, probe):
    report = summary(delta, auc)
    report["passed"] = True
    assert gate_failures(report)[0]["probe"] == probe


@pytest.mark.parametrize("delta,auc", [(math.nan, .6), (5., math.inf)])
def test_nonfinite_acceptance_rejected(delta, auc):
    with pytest.raises(ValueError, match="Non-finite"):
        gate_failures(summary(delta, auc))


def test_independent_metrics_and_tamper_rejection():
    actual = binary_metrics([(1,1),(1,1),(0,1),(1,0),(0,0)])
    assert actual["buggy_f1"] == pytest.approx(200*2/6)
    compare_metrics(actual, actual)
    bad = dict(actual, tp=100)
    with pytest.raises(ValueError, match="mismatch"):
        compare_metrics(bad, actual)


def test_naming_manifest_and_artifact_hashes_are_enforced(tmp_path):
    refs = {}
    for name in ("inventories", "pool", "mappings"):
        path = tmp_path/(name+".json")
        write(path, {})
        refs[name] = ref(path)
    path = tmp_path/"manifest.json"
    write(path, dict(artifacts=refs))
    write(tmp_path/"manifest.seal.json", dict(manifest=ref(path)))
    load_naming(tmp_path)
    (tmp_path/"mappings.json").write_text('{"tampered":true}')
    with pytest.raises(ValueError, match="SHA"):
        load_naming(tmp_path)


def test_refuse_overwrite_artifact(tmp_path):
    p = tmp_path/"f.json"
    write(p, {"original":True})
    with pytest.raises(FileExistsError):
        write(p, {"changed":True})
    assert "original" in p.read_text()
