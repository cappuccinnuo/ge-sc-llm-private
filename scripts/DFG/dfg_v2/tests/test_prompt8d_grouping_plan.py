import copy
import json
from pathlib import Path

import pytest

from scripts.DFG.dfg_v2.benchmark_v2.grouping import (
    assign_groups, build_groups, grouped_folds, validate_splits)
from scripts.DFG.dfg_v2.benchmark_v2.prepare import make_jobs, ref, verify_prepared, write


def population(n=40):
    return [
        {"file": "f%03d.sol" % i, "source_id": "source%03d" % i,
         "source_sha256": str(i).zfill(64), "group_id": "group%03d" % (i//2),
         "file_label": (i//2) % 2, "cohort": "A" if i % 3 else "B",
         "node_positive": 1 + i % 7, "node_negative": 10 + i % 5,
         "audit_node_positive": 1 + i % 7, "audit_node_negative": 9+i%5,
         "audit_masked_nodes": 1}
        for i in range(n)
    ]


def test_groups_union_exact_near_and_retain_singletons():
    sources = [{"source_id": name} for name in ("a", "b", "c", "d")]
    clusters = {"exact": [{"members": ["a", "b"]}],
                "near": [{"members": ["b", "c"]}]}
    groups = build_groups(sources, clusters)
    assert sorted(sorted(g["members"]) for g in groups) == [["a", "b", "c"], ["d"]]
    assert groups == build_groups(list(reversed(sources)), clusters)


@pytest.mark.parametrize("clusters", [
    {"exact": [{"members": ["a", "missing"]}], "near": []},
    {"exact": [{"members": ["a", "a"]}], "near": []},
    {"exact": [], "near": [{"members": ["a"]}]},
])
def test_groups_reject_invalid_components(clusters):
    with pytest.raises(ValueError):
        build_groups([{"source_id": "a"}], clusters)


def test_groups_reject_duplicate_source_id():
    with pytest.raises(ValueError, match="Duplicate source"):
        build_groups([{"source_id": "same"}, {"source_id": "same"}], {"exact": [], "near": []})


@pytest.mark.parametrize("k", [5, 10])
def test_grouped_nested_all_samples_once_and_no_leakage(k):
    rows = population()
    doc = grouped_folds("fictional_" + str(k), rows, k)
    assert doc["validation"]["passed"]
    assert doc["seed"] == 1 and doc["inner_fraction"] == .2
    assert doc == grouped_folds("fictional_" + str(k), list(reversed(rows)), k)
    original_groups = {r["file"]: r["group_id"] for r in rows}
    for fold in doc["folds"]:
        roles = [fold[r] for r in ("inner_train_files", "inner_val_files", "outer_test_files")]
        gs = [{original_groups[name] for name in role} for role in roles]
        assert all(not gs[i] & gs[j] for i in range(3) for j in range(i))
        assert sum(len(role) for role in roles) == len(rows)


def test_too_few_whole_groups_rejected_without_shrinking_k():
    with pytest.raises(ValueError, match="Too few"):
        grouped_folds("small", population(8), 10)


def test_unknown_k_rejected():
    with pytest.raises(ValueError, match="5 or 10"):
        grouped_folds("task", population(), 3)


def test_no_predictions_or_label_choice_enter_split_algorithm():
    rows = population()
    result = grouped_folds("task", rows, 10)
    changed = copy.deepcopy(rows)
    for r in changed:
        r["audit_node_positive"] = 999
        r["audit_node_negative"] = 0
        r["audit_masked_nodes"] = 0
    other = grouped_folds("task", changed, 10)
    for old, new in zip(result["folds"], other["folds"]):
        for role in ("inner_train_files", "inner_val_files", "outer_test_files"):
            assert old[role] == new[role]


def test_validation_rejects_a_group_split_even_without_file_overlap():
    rows = population()
    doc = grouped_folds("task", rows, 10)
    split = doc["folds"][0]
    left = split["inner_train_files"][0]
    right = split["outer_test_files"][0]
    split["inner_train_files"][0], split["outer_test_files"][0] = right, left
    with pytest.raises(ValueError, match="group leakage"):
        validate_splits(doc, rows)


def test_validation_rejects_missing_or_duplicate_test_membership():
    rows = population()
    doc = grouped_folds("task", rows, 10)
    doc["folds"][1] = copy.deepcopy(doc["folds"][0])
    doc["folds"][1]["fold"] = 1
    with pytest.raises(ValueError, match="exactly once"):
        validate_splits(doc, rows)


def test_classless_contract_partition_rejected_not_retried():
    rows = population()
    for r in rows:
        r["file_label"] = int(r["group_id"] == "group000")
    with pytest.raises(ValueError, match="lacks a contract class"):
        grouped_folds("task", rows, 5)


@pytest.mark.parametrize("fractions,seed", [([.5,.4], 1), ([1,0],1), ([.5,.5],-1)])
def test_invalid_stratification_configuration_rejected(fractions, seed):
    with pytest.raises(ValueError):
        assign_groups([{"group_id": "a", "strata": {"n": 1}},
                       {"group_id": "b", "strata": {"n": 2}}], fractions, seed)


def test_170_matrix_only_node_placebo_no_implicit_seed_expansion():
    tasks = {category+"_"+kind: {"granularity": kind, "k_folds": k}
             for category in ("x", "y") for kind,k in (("contract",5),("node",10))}
    jobs = make_jobs(tasks, [1])
    assert len(jobs) == 170
    assert sum(j["profile"] == "G0P" for j in jobs) == 20
    assert all(j["execution_authorized"] is False for j in jobs)
    assert all(j["task_id"].endswith("_node") for j in jobs if j["profile"] == "G0P")
    for task in tasks:
        per_fold = [j for j in jobs if j["task_id"] == task and j["fold"] == 0]
        assert len({j["fit_seed"] for j in per_fold}) == 1
    assert len(make_jobs(tasks, [1,2])) == 340
    with pytest.raises(ValueError):
        make_jobs(tasks,[1,1])


def _sealed_minimal(tmp_path):
    data = tmp_path/"data.json"
    write(data, {"value": 1})
    plan = {"execution_authorized": False, "training_executed": 0,
            "bound_artifacts": {"test": ref(data)}, "jobs": [], "fit_count": 0, "tasks": {}}
    path = tmp_path/"plan.json"
    write(path, plan)
    write(tmp_path/"plan.seal.json", {"plan_sha256": ref(path)["sha256"]})
    return path, data


def test_preparation_verifier_rejects_input_mutation(tmp_path):
    plan, data = _sealed_minimal(tmp_path)
    assert verify_prepared(plan)["passed"]
    data.write_text('{"value":2}')
    with pytest.raises(ValueError, match="SHA differs"):
        verify_prepared(plan)


def test_preparation_seal_detects_permission_mutation(tmp_path):
    path, _ = _sealed_minimal(tmp_path)
    plan = json.loads(path.read_text())
    plan["execution_authorized"] = True
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="seal"):
        verify_prepared(path)


def test_even_resealed_preparation_cannot_authorize_fits(tmp_path):
    path, _ = _sealed_minimal(tmp_path)
    plan = json.loads(path.read_text())
    plan["execution_authorized"] = True
    path.write_text(json.dumps(plan))
    (tmp_path/"plan.seal.json").write_text(json.dumps({"plan_sha256": ref(path)["sha256"]}))
    with pytest.raises(ValueError, match="cannot authorize"):
        verify_prepared(path)


def test_exclusive_writes_preserve_prior_artifact(tmp_path):
    path = tmp_path/"original.json"
    write(path, {"sentinel": 1})
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        write(path, {"sentinel": 2})
    assert path.read_bytes() == before

def _population_fixture(tmp_path):
    import networkx as nx
    import pickle
    graph = nx.MultiDiGraph()
    graph.add_node(4, source_file="buggy_1.sol", node_type="expression_statement",
                   node_info_vulnerabilities=None)
    graph.add_node(8, source_file="buggy_1.sol", node_type="contract_declaration",
                   node_info_vulnerabilities=[{"lines": [1]}])
    path = tmp_path/"graph.gpickle"
    path.write_bytes(pickle.dumps(graph))
    labels = tmp_path/"labels.json"
    write(labels, [{"contract_name": "buggy_1.sol", "targets": 1}])
    source_sha = "a" * 64
    entry = {"record": {"graph_files": ["buggy_1.sol"], "sources": {
        "buggy_1.sol": {"sha256": source_sha}}, "labels": ref(labels),
        "original_graph": ref(path), "task": "node"}}
    source = {"file": "buggy_1.sol", "source_id": "stable-source",
              "source_sha256": source_sha, "cohort": "author",
              "category": "fictional", "task_outer_folds": {"fake_node": 0}}
    views = {"fake_node": [
        {"file": "buggy_1.sol", "original_graph_node_id": 4, "source_sha256": source_sha,
         "node_type": "expression_statement", "orig": 0, "C1": 1, "C2_include": True,
         "exclusion_reasons": [], "solidifi": True},
        {"file": "buggy_1.sol", "original_graph_node_id": 8, "source_sha256": source_sha,
         "node_type": "contract_declaration", "orig": 1, "C1": 1, "C2_include": False,
         "exclusion_reasons": ["container"], "solidifi": True},
    ]}
    return entry, [source], [{"group_id": "one-group", "members": ["stable-source"]}], views


def test_audit_targets_are_separate_and_exclusion_never_deletes_graph_nodes(tmp_path):
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import task_population
    entry, sources, groups, views = _population_fixture(tmp_path)
    before_graph = Path(entry["record"]["original_graph"]["path"]).read_bytes()
    before_views = copy.deepcopy(views)
    files, labels, conflicts = task_population("fake_node", entry, sources, groups, views)
    assert len(labels) == 2 and conflicts == []
    assert labels[0]["orig"] == 0 and labels[0]["L-audit_target"] == 1
    assert labels[1]["orig"] == 1 and labels[1]["L-audit_include"] is False
    assert all(row["L-orig_include"] for row in labels)
    assert files[0]["audit_masked_nodes"] == 1
    assert files[0]["node_positive"] == files[0]["node_negative"] == 1
    assert files[0]["audit_node_positive"] == 1 and files[0]["audit_node_negative"] == 0
    assert Path(entry["record"]["original_graph"]["path"]).read_bytes() == before_graph
    assert views == before_views


@pytest.mark.parametrize("field,value", [
    ("source_sha256", "b"*64), ("orig", 1),
    ("node_type", "return"), ("original_graph_node_id", 999),
])
def test_label_view_mismatch_rejected(tmp_path, field, value):
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import task_population
    entry, sources, groups, views = _population_fixture(tmp_path)
    views["fake_node"][0][field] = value
    with pytest.raises(ValueError):
        task_population("fake_node", entry, sources, groups, views)


def test_task_population_uses_source_identity_not_basename_only(tmp_path):
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import task_population
    entry, sources, groups, views = _population_fixture(tmp_path)
    sources[0]["source_sha256"] = "different_cohort_source"
    with pytest.raises(ValueError):
        task_population("fake_node", entry, sources, groups, views)


def test_nested_feature_reference_tampering_rejected(tmp_path):
    path, data = _sealed_minimal(tmp_path)
    plan = json.loads(path.read_text())
    plan["bound_artifacts"] = {}
    plan["nested_feature_view"] = {"profile": {"data": ref(data)}}
    path.write_text(json.dumps(plan))
    (tmp_path/"plan.seal.json").write_text(json.dumps({"plan_sha256": ref(path)["sha256"]}))
    assert verify_prepared(path)["passed"]
    data.write_text('{"value": 9}')
    with pytest.raises(ValueError, match="SHA differs"):
        verify_prepared(path)


def test_resealed_duplicate_or_wrong_profile_job_rejected(tmp_path):
    path, _ = _sealed_minimal(tmp_path)
    plan = json.loads(path.read_text())
    plan["jobs"] = [{"task_id": "unknown", "profile": "G0P", "execution_authorized": False}]
    plan["fit_count"] = 1
    path.write_text(json.dumps(plan))
    (tmp_path/"plan.seal.json").write_text(json.dumps({"plan_sha256": ref(path)["sha256"]}))
    with pytest.raises(ValueError, match="matrix differs"):
        verify_prepared(path)


@pytest.mark.parametrize("field,value", [("C1",2),("C2_include","false")])
def test_invalid_audit_label_or_mask_type_is_rejected(tmp_path,field,value):
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import task_population
    entry,sources,groups,views=_population_fixture(tmp_path)
    views["fake_node"][0][field]=value
    with pytest.raises(ValueError,match="binary"):
        task_population("fake_node",entry,sources,groups,views)
