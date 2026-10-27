"""Read-only Prompt 8 reports: no model fitting or real-data scoring."""
import copy
import json
from pathlib import Path

import networkx as nx
import pytest

from scripts.DFG.dfg_v2.experiment import reporting, stats
from scripts.DFG.experiments.common import metrics
from scripts.DFG.integration.io import write_json, sha256


def ref(path):
    return dict(path=str(path), sha256=sha256(path))


def specification(sensitivity=None):
    return dict(version="prompt8-report-spec-v1", sensitivity=sensitivity or [],
        source_audit=None, review_sources=[],
        mechanism=dict(direction="model_message", hops=[1, 2],
            path_rule="directed path length <= h containing named new canonical relation",
            count_unit="changed original HCG node", interim_profile="G3R", final_profile="G*"),
        statistics=stats.specification())


@pytest.fixture
def small(tmp_path):
    sources = {}
    for i in range(5):
        path = tmp_path / ("file%d.sol" % i)
        path.write_text("contract C%d {}" % i)
        sources[path.name] = ref(path)
    record = dict(category="fictional", task="contract", sources=sources,
                  graph_files=sorted(sources))
    plan = dict(tasks={"fictional_contract": dict(record=record, folds=list(range(5)))},
                seeds=[1], profiles=["G0", "G3R"], jobs=[])
    bundles = []
    for fold, filename in enumerate(record["graph_files"]):
        for profile in plan["profiles"]:
            y = fold % 2
            pred = y if profile == "G3R" or fold != 1 else 0
            row = dict(file=filename, target=y, score_role="outer_test",
                       best=pred, last=1-pred, best_positive_probability=.8 if pred else .2,
                       last_positive_probability=.2 if pred else .8)
            job = dict(task_id="fictional_contract", fold=fold, seed=1, profile=profile)
            result = dict(outer_test={ck: metrics([y], [row[ck]]) for ck in ("best", "last")})
            bundle = dict(job=job, predictions=[row], result=result,
                          split={"outer_test_files": [filename]}, graph={})
            plan["jobs"].append(job)
            bundles.append(bundle)
    filename = record["graph_files"][1]
    spec = specification([dict(category="fictional", file=filename,
                               source_sha256=sources[filename]["sha256"])])
    return plan, bundles, spec


def test_sensitivity_identity_not_filename_only(small):
    plan, bundles, spec = small
    assert reporting.validate_reporting_metadata(spec, plan) == spec
    wrong = copy.deepcopy(spec)
    wrong["sensitivity"][0]["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Sensitivity source"):
        reporting.validate_reporting_metadata(wrong, plan)
    wrong = copy.deepcopy(spec)
    wrong["sensitivity"].append(wrong["sensitivity"][0])
    with pytest.raises(ValueError, match="duplicate"):
        reporting.validate_reporting_metadata(wrong, plan)


@pytest.mark.parametrize("kind", ["version", "mechanism", "statistics"])
def test_preregistered_methods_cannot_change(small, kind):
    plan, _, spec = small
    spec[kind] = "changed"
    with pytest.raises(ValueError):
        reporting.validate_reporting_metadata(spec, plan)


def test_metrics_best_last_pooled_and_empty_sensitive_fold(small):
    plan, bundles, spec = small
    tables = reporting.prediction_tables(plan, bundles, spec)
    assert len(tables["records"]) == 20
    assert len(tables["fold_metrics"]) == 40
    assert len(tables["pooled_oof"]) == 8
    baseline = next(r for r in tables["pooled_oof"] if r["profile"] == "G0"
                    and r["checkpoint"] == "best" and r["population"] == "all")
    assert baseline["n"] == 5 and baseline["fn"] == 1
    filtered = next(r for r in tables["pooled_oof"] if r["profile"] == "G0"
                    and r["checkpoint"] == "best" and r["population"] == "exclude_disputed")
    assert filtered["n"] == 4 and filtered["fn"] == 0
    empty = [r for r in tables["fold_metrics"] if r["population"] == "exclude_disputed"
             and r["fold"] == 1]
    assert len(empty) == 4 and all(r["n"] == 0 and r["buggy_f1"] is None for r in empty)
    assert len([r for r in tables["file_metrics"] if r["disputed"]]) == 4


@pytest.mark.parametrize("corruption", ["target", "probability", "role", "env", "duplicate", "missing"])
def test_prediction_corruption_is_rejected(small, corruption):
    plan, bundles, spec = small
    row = bundles[0]["predictions"][0]
    if corruption == "target":
        row["target"] = 1-row["target"]
    elif corruption == "probability":
        row["best_positive_probability"] = float("nan")
    elif corruption == "role":
        row["score_role"] = "inner_val"
    elif corruption == "env":
        row["node_type"] = "env_source"
    elif corruption == "duplicate":
        bundles[0]["predictions"].append(dict(row))
    else:
        bundles[0]["predictions"] = []
    with pytest.raises(ValueError):
        reporting.prediction_tables(plan, bundles, spec)


def test_pooled_duplicate_and_missing_folds_rejected(small):
    plan, bundles, spec = small
    with pytest.raises(ValueError, match="Repeated OOF"):
        reporting.prediction_tables(plan, bundles + [copy.deepcopy(bundles[0])], spec)
    with pytest.raises(ValueError, match="every frozen file"):
        reporting.prediction_tables(plan, bundles[2:], spec)


def test_identity_alignment_independent_of_row_order(small):
    plan, bundles, spec = small
    reporting.prediction_tables(plan, bundles, spec)
    tables = reporting.comparison_tables(plan, list(reversed(bundles)), "A", "G3R")
    assert len(tables["error_changes"]) == 10
    corrected = [r for r in tables["error_changes"] if r["checkpoint"] == "best"]
    assert sum(r["corrected"] for r in corrected) == 1
    last = [r for r in tables["error_changes"] if r["checkpoint"] == "last"]
    assert sum(r["regressed"] for r in last) == 1
    assert tables["mechanism"] == []


def test_pair_target_mismatch_rejected(small):
    plan, bundles, spec = small
    reporting.prediction_tables(plan, bundles, spec)
    bundles[0]["indexed"][next(iter(bundles[0]["indexed"]))]["target"] = 1
    with pytest.raises(ValueError, match="identity or target"):
        reporting.comparison_tables(plan, bundles, "A", "G3R")


def graph():
    g = nx.MultiDiGraph()
    for name in ("a", "b", "c", "d"):
        g.add_node(name, node_type="statement", source_file="x.sol")
    g.add_edge("a", "b", edge_type="DATA_DEF_USE")
    g.add_edge("b", "c", edge_type="next")
    g.add_edge("d", "a", edge_type="next")
    return g


def test_reachability_uses_materialized_direction_and_named_canonical():
    g = graph()
    before = copy.deepcopy(g)
    forward = reporting.directed_relation_reach(g, "G3")
    key = ("statement", "DATA_DEF_USE", "statement")
    assert forward[key][1] == {"b"}
    assert forward[key][2] == {"b", "c"}
    assert "a" not in forward[key][2]  # DATA_DEF_USE is not silently reflected.
    assert ("statement", "REV_DATA_DEF_USE", "statement") not in forward
    reverse = reporting.directed_relation_reach(g, "G3R")
    rkey = ("statement", "REV_DATA_DEF_USE", "statement")
    assert reverse[rkey][1] == {"a"}
    assert reverse[rkey][2] == {"a", "b", "d"}
    assert nx.utils.graphs_equal(before, g)


def test_cross_file_message_edge_rejected():
    g = graph()
    g.nodes["b"]["source_file"] = "other.sol"
    with pytest.raises(ValueError, match="Cross-file"):
        reporting.directed_relation_reach(g, "G3R")


def test_env_participates_only_as_message_vertex():
    g = graph()
    g.add_node("env", node_type="env_source", source_file="x.sol")
    g.add_edge("env", "a", edge_type="ENV_FLOW")
    reach = reporting.directed_relation_reach(g, "G3R")
    assert reach[("env_source", "ENV_FLOW", "statement")][1] == {"a"}
    assert "env" in reach[("statement", "REV_ENV_FLOW", "env_source")][1]


def test_statistics_interim_is_not_selection_or_completed_holm(small):
    plan, bundles, spec = small
    tables = reporting.prediction_tables(plan, bundles, spec)
    report = reporting.statistical_tables(tables["records"], "A")
    assert len(report["paired"]) == 8  # 4 metrics x best/last.
    assert all(r["p_raw"] is None for r in report["paired"])
    assert all(r["p_adjusted"].get("G3R") is None for r in report["holm"])


def test_export_is_exclusive_and_binds_all_tables(tmp_path):
    report = dict(stage="A", plan={"path": "sealed-plan", "sha256": "x"},
                  interpretation="中间结果", tables={"best": [{"value": 2}]},
                  manual_review={"status": "未完成"})
    dest = tmp_path / "report"
    result = reporting.export_report(dest, report)
    assert result["report"]["sha256"] == sha256(dest / "REPORT_INTERIM_A.md")
    assert "中间结果" in (dest / "REPORT_INTERIM_A.md").read_text()
    assert "未完成" in (dest / "REPORT_INTERIM_A.md").read_text()
    assert set(result["artifacts"]) == {"REPORT_INTERIM_A.md", "report.json", "best.csv"}
    before = {p.name: p.read_bytes() for p in dest.iterdir()}
    with pytest.raises(FileExistsError):
        reporting.export_report(dest, report)
    assert before == {p.name: p.read_bytes() for p in dest.iterdir()}


def test_complete_report_requires_sealed_selection(small, tmp_path, monkeypatch):
    from scripts.DFG.dfg_v2.experiment import run
    plan, bundles, spec = small
    path = tmp_path / "plan.json"
    specpath = tmp_path / "spec.json"
    write_json(specpath, spec)
    plan["batch_registration"] = {"report_spec": ref(specpath)}
    write_json(path, plan)
    monkeypatch.setattr(run, "_load_plan", lambda p: plan)
    with pytest.raises(FileNotFoundError):
        reporting.build_report(path, stage="complete")
    assert not (tmp_path / "reports").exists()


def test_manual_review_blank_status():
    assert reporting._manual_review({"review_sources": []})["status"] == "未完成"


def test_sensitive_empty_fold_not_silently_dropped(small):
    plan, bundles, spec = small
    rows = reporting.prediction_tables(plan, bundles, spec)["fold_metrics"]
    means = reporting.sensitivity_means(rows)
    assert len(means) == 16
    assert all(r["status"] == "unavailable_empty_filtered_fold" and r["mean"] is None for r in means)
    complete = reporting.prediction_tables(plan, bundles, specification())["fold_metrics"]
    means = reporting.sensitivity_means(complete)
    assert all(r["status"] == "complete" and r["n_pairs"] == 5 for r in means)


@pytest.mark.parametrize("via_batch", [False, True])
def test_build_interim_report_from_verified_jobs(small, tmp_path, monkeypatch, via_batch):
    from scripts.DFG.dfg_v2.experiment import run, batch
    plan, bundles, spec = small
    specpath = tmp_path / "spec.json"
    write_json(specpath, spec)
    plan["batch_registration"] = {"report_spec": ref(specpath)}
    planpath = tmp_path / "plan.json"
    write_json(planpath, plan)
    if via_batch:
        phase_a = list(plan["jobs"])
        phase_b = [dict(job, profile=profile) for job in phase_a if job["profile"] == "G0"
                   for profile in ("G1R", "G2R", "G3")]
        plan["jobs"] = phase_a + phase_b
        plan["profiles"] = ["G0", "G1R", "G2R", "G3R", "G3"]
        plan["resource_policy"] = {"version": "synthetic_reporting_interface"}
        plan["batch_registration"]["stages"] = {
            "A": {"profiles": ["G0", "G3R"], "jobs": [run.job_id(j) for j in phase_a]},
            "B": {"profiles": ["G1R", "G2R", "G3"], "jobs": [run.job_id(j) for j in phase_b]}}
        write_json(planpath, plan)
    entries = {}
    for i, bundle in enumerate(bundles):
        dest = tmp_path / ("attempt_%d" % i)
        dest.mkdir()
        write_json(dest / "outer_test_predictions.json", bundle["predictions"])
        write_json(dest / "receipt.json", {"job": bundle["job"]})
        result = bundle["result"]
        result.update(best_epoch=1, last_epoch=2, parameter_count=10, seconds=3.,
                      resources={"peak_allocated_mib": 1, "peak_reserved_mib": 2,
                                 "minimum_free_mib": 300},
                      checkpoint_roundtrip_exact={"best": True, "last": True},
                      gradient_audit={"epochs": [{"v2_relations": []}]})
        entries[run.job_id(bundle["job"])] = (dest, bundle)
    monkeypatch.setattr(run, "_load_plan", lambda p: plan)
    monkeypatch.setattr(run, "_completed", lambda root, p, j, path:
        (entries[run.job_id(j)][0], entries[run.job_id(j)][1]["result"]))
    monkeypatch.setattr(run, "_prepared", lambda p, j:
        (plan["tasks"][j["task_id"]],
         {"split": entries[run.job_id(j)][1]["split"]},
         {"graph": {}, "support": {"relations": []}}))
    monkeypatch.setattr(run, "_selection", lambda *a: pytest.fail("Interim cannot select G*"))
    if via_batch:
        monkeypatch.setattr(batch, "audit_pilot_result", lambda *a, **k: {"passed": True})
        # Exercise real verify_stage -> _accept wrapper -> interim -> reporting.
        outcome = batch.interim(planpath)
        path = Path(outcome["report"])
        artifact = {"report": ref(path / "REPORT_INTERIM_A.md")}
        assert outcome["stop_for_user_review"]
    else:
        artifact = reporting.build_report(planpath)
        path = Path(artifact["output"])
    report = json.loads((path / "report.json").read_text())
    assert report["completed_jobs"] == 10 and report["selected_profile"] is None
    assert report["manual_review"]["status"] == "未完成"
    assert (path / "REPORT_INTERIM_A.md").exists()
    assert report["tables"]["best_fold_means"] and report["tables"]["last_fold_means"]
    assert report["tables"]["sensitivity_fold_means"]
    assert all(r["p_adjusted"]["G3R"] is None for r in report["tables"]["holm"])
    assert len(report["tables"]["fit_resources"]) == 10
    assert artifact["report"]["sha256"] == sha256(path / "REPORT_INTERIM_A.md")


def test_missing_job_rejects_before_report_creation(small, tmp_path, monkeypatch):
    from scripts.DFG.dfg_v2.experiment import run
    plan, _, spec = small
    specpath = tmp_path / "spec.json"
    write_json(specpath, spec)
    plan["batch_registration"] = {"report_spec": ref(specpath)}
    planpath = tmp_path / "plan.json"
    write_json(planpath, plan)
    monkeypatch.setattr(run, "_load_plan", lambda p: plan)
    monkeypatch.setattr(run, "_completed", lambda *a: None)
    with pytest.raises(ValueError, match="Incomplete report matrix"):
        reporting.build_report(planpath)
    assert not (tmp_path / "reports").exists()
