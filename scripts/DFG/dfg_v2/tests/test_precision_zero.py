"""Static-only classification: shared tensors, multiedges and supervision paths."""
import copy
import json

import pytest

from scripts.DFG.dfg_v2.experiment import precision_zero as module


def support(edges=None, active=None, layers=2):
    return module.topology_support(
        ["S", "T", "env_source"],
        edges if edges is not None else {("S", "r", "T"): [(0, 0), (0, 0)]},
        active if active is not None else {"S": set(), "T": {0}, "env_source": set()},
        layers)


@pytest.mark.parametrize("name", ["gcs.0.k_linears.0.bias", "gcs.1.k_linears.2.bias"])
def test_key_bias_invariance(name):
    assert module.classify_parameter(name, support(), "G3R")["category"] == "a"


@pytest.mark.parametrize("name", ["gcs.1.k_linears.0.weight", "gcs.1.q_linears.1.weight",
                                   "gcs.1.q_linears.1.bias"])
def test_parallel_same_source_is_one_source(name):
    row = module.classify_parameter(name, support(), "G3R")
    assert row["category"] == "b"
    assert row["evidence"]["parallel_single_source_groups"] == 1


@pytest.mark.parametrize("name", ["gcs.1.k_linears.0.weight", "gcs.1.q_linears.1.weight",
                                   "gcs.1.q_linears.1.bias"])
def test_distinct_sources_are_not_parallel_identity(name):
    topo = support({("S", "r", "T"): [(0, 0), (1, 0)]})
    row = module.classify_parameter(name, topo, "G3R")
    assert row["category"] == "d"
    assert not row["structural_proof"]


@pytest.mark.parametrize("name", ["gcs.1.k_linears.0.weight", "gcs.1.q_linears.1.weight"])
def test_all_relations_must_prove_shared_tensor_independence(name):
    topo = support({("S", "r", "T"): [(0, 0), (0, 0)],
                    ("S", "other", "T"): [(0, 0), (1, 0)]})
    row = module.classify_parameter(name, topo, "G3R")
    assert row["category"] == "d"
    assert row["evidence"]["relation_count"] == 2


def test_different_destinations_each_with_one_source():
    topo = support({("S", "r", "T"): [(0, 0), (1, 1)]},
                   {"S": set(), "T": {0, 1}, "env_source": set()})
    assert module.classify_parameter("gcs.1.k_linears.0.weight", topo, "G3R")["category"] == "b"


def test_unreachable_multisource_destination_does_not_block_proof():
    topo = support({("S", "r", "T"): [(0, 0), (0, 1), (1, 1)]})
    assert module.classify_parameter("gcs.1.k_linears.0.weight", topo, "G3R")["category"] == "b"


def test_no_relation_does_not_create_vacuous_single_source_proof():
    row = module.classify_parameter("gcs.1.k_linears.0.weight", support({}), "G3R")
    assert row["category"] == "d"
    assert row["evidence"]["relation_count"] == 0


@pytest.mark.parametrize("kind", ["q_linears", "a_linears", "norms"])
@pytest.mark.parametrize("member", ["weight", "bias"])
def test_last_layer_auxiliary_target_has_no_supervision_path(kind, member):
    row = module.classify_parameter("gcs.1.{}.2.{}".format(kind, member), support(), "G3R")
    assert row["category"] == "c"


@pytest.mark.parametrize("name", ["gcs.1.v_linears.2.weight", "gcs.1.k_linears.2.weight",
                                   "adapt_ws.2.weight", "gcs.1.skip"])
def test_unsupervised_target_does_not_prove_source_or_input_parameter_zero(name):
    # env_source may still emit messages to supervised T nodes.
    topo = support({("env_source", "ENV_FLOW", "T"): [(0, 0)]})
    row = module.classify_parameter(name, topo, "G3R")
    assert row["category"] != "c"


def test_earlier_auxiliary_target_can_reach_training_via_next_layer():
    topo = support({("S", "REV_ENV_FLOW", "env_source"): [(0, 0)],
                    ("env_source", "ENV_FLOW", "T"): [(0, 0)]})
    assert topo["layers"][1]["output_nodes_reaching_train"]["env_source"] == 0
    assert topo["layers"][0]["output_nodes_reaching_train"]["env_source"] == 1
    assert module.classify_parameter("gcs.0.a_linears.2.weight", topo, "G3R")["category"] == "d"


def test_category_c_requires_profile_and_last_layer():
    assert module.classify_parameter("gcs.1.norms.2.weight", support(), "G0")["category"] == "d"
    assert module.classify_parameter("gcs.0.norms.2.weight", support(), "G3R")["category"] == "d"


def test_residual_keeps_supervised_target_reachable():
    topo = support({})
    assert topo["input_nodes_reaching_train"]["T"] == 1
    assert all(r["output_nodes_reaching_train"]["T"] == 1 for r in topo["layers"])


@pytest.mark.parametrize("name", ["gcs.2.k_linears.0.weight", "gcs.1.q_linears.9.bias"])
def test_parameter_schema_mismatch_rejected(name):
    with pytest.raises(ValueError):
        module.classify_parameter(name, support(), "G3R")


@pytest.mark.parametrize("types,edges,active,layers", [
    (["S", "S"], {}, {"S": set()}, 1),
    (["S"], {}, {"T": set()}, 1),
    (["S"], {}, {"S": set()}, 0),
    (["S"], {("S", "r", "missing"): []}, {"S": set()}, 1),
])
def test_invalid_topology_rejected(types, edges, active, layers):
    with pytest.raises(ValueError):
        module.topology_support(types, edges, active, layers)


def test_existing_output_refused_before_reading_evidence(tmp_path):
    path = tmp_path / "result.json"
    path.write_text("unchanged")
    with pytest.raises(FileExistsError):
        module.classify_report(tmp_path / "missing.json", path)
    assert path.read_text() == "unchanged"


@pytest.mark.parametrize("status,passed", [("failed", True), ("passed", False)])
def test_reject_unaccepted_static_evidence(tmp_path, status, passed):
    source = tmp_path / "static.json"
    source.write_text(json.dumps({"status": status, "gradient_comparison": {"passed": passed}}))
    with pytest.raises(ValueError):
        module.classify_report(source, tmp_path / "out.json")


@pytest.mark.parametrize("names,candidates", [
    (["x", "x"], ["x"]), (["x"], ["y"]),
])
def test_reject_duplicate_or_mismatched_zero_tensors(tmp_path, names, candidates):
    source = tmp_path / "static.json"
    source.write_text(json.dumps({"status": "passed", "gradient_comparison": {
        "passed": True, "zero_tensors": names, "candidate_zero_tensors": candidates}}))
    with pytest.raises(ValueError):
        module.classify_report(source, tmp_path / "out.json")


def test_classification_does_not_mutate_support():
    topo = support()
    old = copy.deepcopy(topo)
    module.classify_parameter("gcs.0.k_linears.0.weight", topo, "G3R")
    assert topo == old
