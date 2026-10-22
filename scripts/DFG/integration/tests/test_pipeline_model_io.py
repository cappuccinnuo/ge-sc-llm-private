"""CPU integration tests. Solidity fixtures are parsed, never solc-validated."""
import copy
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
import torch

from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
from scripts.labeling_v2.safe_graph import read_graph, write_graph
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration import PROFILES, RELATIONS
from scripts.DFG.integration.pipeline import build_graph, assert_profile, assert_preserved
from scripts.DFG.integration.model import make_model
from scripts.DFG.integration.io import read_sources, write_bundle, sha256
from scripts.DFG.integration.cli import main
from scripts.DFG.model_validation import capture_model_input, assert_model_input
from scripts.DFG.experiments.e23_pilot.tests.test_model import graphs

SRC = ("pragma solidity ^0.4.24; contract C { uint s; "
       "function f(uint x,bool ok,address to) public returns(uint){ "
       'uint y=x; s=1; require(ok); uint z=s; to.call(""); s=2; return y+z; } }')


@pytest.fixture(autouse=True)
def cpu_threads():
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


def fixture():
    graph = generate_cfg_from_source(SRC, "case.sol")
    graph.graph["original_metadata"] = {"producer": "fixture", "versions": [1, 2]}
    for n, data in graph.nodes(data=True):
        data["token"] = np.linspace(n/100, n/100+1, 512, dtype=np.float32)
        data["node_info_vulnerabilities"] = [{"lines": [42]}] if n % 2 else None
    return graph


def enhancements(graph):
    return {(s,t,d["edge_type"]) for s,t,d in graph.edges(data=True)
            if d["edge_type"] in RELATIONS}


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_four_profiles_preserve_original_nodes_labels_features_and_base_edges(profile):
    graph = fixture()
    before = fingerprint(graph)
    result, audit = build_graph(graph, {"case.sol": SRC}, profile)
    assert fingerprint(graph) == before
    assert audit["invariants"]["base_nodes_exact"] and audit["invariants"]["base_edges_exact"]
    assert result.graph == graph.graph
    assert {relation for _,_,relation in enhancements(result)} == PROFILES[profile]
    assert_preserved(graph, result, profile)
    if profile == "baseline":
        assert fingerprint(result) == before and audit["stages"] == {}


def test_baseline_without_sources_and_missing_enhancement_source_keep_samples():
    graph = fixture()
    for profile in PROFILES:
        result, audit = build_graph(graph, {}, profile)
        assert fingerprint(result) == fingerprint(graph)
        assert set(result) == set(graph)


@pytest.mark.parametrize("mode", ["unknown_profile", "reverse", "already_enhanced", "cross_file"])
def test_reject_unknown_profile_reverse_duplicate_input_and_cross_file(mode):
    graph = fixture()
    nodes = list(graph)
    profile = "full_guard"
    if mode == "unknown_profile":
        profile = "fake"
    elif mode == "reverse":
        graph.add_edge(nodes[0], nodes[1], edge_type="REV_STATE_DEF_USE")
    elif mode == "already_enhanced":
        graph.add_edge(nodes[0], nodes[1], edge_type="DATA_DEF_USE")
    else:
        source,target = next(iter(graph.edges()))
        graph.nodes[target]["source_file"] = "different.sol"
    with pytest.raises(ValueError):
        build_graph(graph, {"case.sol": SRC}, profile)


@pytest.mark.parametrize("kind", ["duplicate", "self"])
def test_invariant_rejects_duplicate_and_self_enhancement(kind):
    graph = fixture()
    result, _ = build_graph(graph, {"case.sol": SRC}, "scalar")
    s,t,rel = next(iter(enhancements(result)))
    result.add_edge(s, t if kind == "duplicate" else s, edge_type=rel)
    with pytest.raises(AssertionError, match="Duplicate/self"):
        assert_preserved(graph, result, "scalar")


def test_labels_and_tokens_are_not_inputs_to_semantic_edge_selection():
    a = fixture(); b = copy.deepcopy(a)
    for node,data in b.nodes(data=True):
        data["node_info_vulnerabilities"] = [] if data["node_info_vulnerabilities"] else [{"category": "changed"}]
        data["token"] = np.full(512, 999, dtype=np.float32)
    ga,_ = build_graph(a, {"case.sol": SRC})
    gb,_ = build_graph(b, {"case.sol": SRC})
    assert enhancements(ga) == enhancements(gb)
    assert_preserved(a, ga, "full_guard")
    assert_preserved(b, gb, "full_guard")


def test_fresh_scalar_matches_existing_scalar_algorithm():
    from scripts.DFG.pipeline import augment
    graph = fixture()
    old,_ = augment(graph, {"case.sol": SRC})
    new,_ = build_graph(graph, {"case.sol": SRC}, "scalar")
    assert fingerprint(new) == fingerprint(old)


def source_manifest(tmp_path, graph):
    src = tmp_path / "case.sol"; src.write_text(SRC)
    manifest = tmp_path / "sources.json"
    manifest.write_text(json.dumps({"sources": {"case.sol": {"path": "case.sol", "sha256": sha256(src), "metadata": None}}}))
    return src,manifest


def test_source_hash_and_missing_identity_validation(tmp_path):
    graph = fixture(); src,manifest = source_manifest(tmp_path, graph)
    sources,metadata,used,missing = read_sources(manifest,graph)
    assert sources == {"case.sol": SRC} and not missing
    assert used["case.sol"]["path"] == str(src)
    src.write_text(SRC+"\n")
    with pytest.raises(ValueError, match="SHA256"):
        read_sources(manifest,graph)
    manifest.write_text('{"sources": {}}')
    assert read_sources(manifest,graph)[3] == ["case.sol"]


def test_bundle_roundtrip_original_metadata_and_overwrite_rejection(tmp_path):
    graph = fixture(); result,audit = build_graph(graph, {"case.sol": SRC}, "full_guard")
    output = tmp_path / "bundle"
    doc = write_bundle(output,result,audit,{"source": "synthetic"})
    loaded = read_graph(Path(doc["graph"]["path"]))
    assert fingerprint(loaded) == fingerprint(result)
    assert loaded.graph == graph.graph
    assert doc["graph"]["sha256"] == sha256(output / "hcg.gpickle")
    assert doc["profile"] == "full_guard" and not doc["training_executed"]
    before = sha256(output / "manifest.json")
    with pytest.raises(FileExistsError):
        write_bundle(output,result,audit,{})
    assert sha256(output / "manifest.json") == before


def test_cli_records_input_sha_and_preserves_successful_output(tmp_path):
    graph = fixture(); path = tmp_path / "input.gpickle"; write_graph(graph,path)
    src,manifest = source_manifest(tmp_path,graph)
    output = tmp_path / "output"
    args = ["--graph",str(path),"--source-manifest",str(manifest),"--profile","full_guard","--output",str(output)]
    result = main(args)
    inputs = json.loads((output / "inputs.json").read_text())
    assert inputs["graph_sha256"] == sha256(path)
    assert inputs["sources"]["case.sol"]["sha256"] == sha256(src)
    assert result["adapter"] == "scripts.DFG.integration.model.make_model"
    with pytest.raises(FileExistsError):
        main(args)


def model_fixture():
    graph = graphs()["E2"]
    for s,t,k,d in list(graph.edges(keys=True,data=True)):
        if d["edge_type"] in RELATIONS:
            graph.remove_edge(s,t,k)
    for file in ("train.sol", "val.sol"):
        for rel in sorted(RELATIONS):
            graph.add_edge(file+":0", file+":1", edge_type=rel)
    return graph


@pytest.mark.parametrize("task", ["node", "contract"])
def test_adapter_five_forward_relations_parallel_edges_real_hgt_backward_and_input_capture(task):
    from sco_models.model_hgt import HGTLayer
    graph = model_fixture(); before = fingerprint(graph)
    torch.manual_seed(7)
    model = make_model(task,graph,"full_guard",hidden_size=8,layers=1,heads=2)
    assert fingerprint(graph) == before
    assert model.integration_profile == "full_guard"
    assert all(type(layer) is HGTLayer for layer in model.gcs)
    for rel in RELATIONS:
        assert ("z",rel,"a") in model.etypes_dict
        assert ("a",rel,"z") not in model.etypes_dict
        assert model.symmetrical_global_graph.num_edges(("z",rel,"a")) == 2
    assert ("z","next","a") in model.etypes_dict
    assert ("a","next","z") in model.etypes_dict
    prediction = model() if task == "node" else model(["train.sol","val.sol"])[0]
    targets = torch.tensor([0,1]*3 if task == "node" else [0,1], dtype=torch.long)
    loss = torch.nn.functional.cross_entropy(prediction,targets)
    loss.backward()
    assert torch.isfinite(loss)
    for rel in RELATIONS:
        row = model.etypes_dict[("z",rel,"a")]
        assert model.gcs[0].relation_msg.grad[row].abs().sum().item() > 0
    metadata = {"profile": "full_guard", "integration_version": model.integration_version}
    manifest = capture_model_input(model,metadata)
    assert manifest["schema"]["input_size"] == 512
    assert_model_input(model,manifest,metadata)
    assert all(not model.symmetrical_global_graph.nodes[n].data["inp"].requires_grad
               for n in model.symmetrical_global_graph.ntypes)
    original_ids = {name:id(value) for name,value in model.named_parameters()}
    model.eval()
    with torch.no_grad():
        again = model() if task == "node" else model(["train.sol","val.sol"])[0]
    assert torch.isfinite(again).all()
    assert original_ids == {name:id(value) for name,value in model.named_parameters()}
    with pytest.raises(ValueError,match="profile"):
        make_model(task,graph,"baseline",hidden_size=8,layers=1,heads=2)


@pytest.mark.parametrize("change", ["features", "labels", "schema"])
def test_capture_detects_model_input_drift(change):
    model = make_model("node",model_fixture(),"full_guard",hidden_size=8,layers=1,heads=2)
    manifest = capture_model_input(model)
    if change == "features":
        model.symmetrical_global_graph.nodes["z"].data["inp"][0,0] += 1
    elif change == "labels":
        model.node_labels[0] = 1-model.node_labels[0]
    else:
        model.etypes_dict.pop(next(iter(model.etypes_dict)))
    with pytest.raises(ValueError):
        assert_model_input(model,manifest)


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_profile_records_active_algorithm_limits_and_propagates_control_bound(profile):
    graph = fixture()
    result,audit = build_graph(graph,{"case.sol":SRC},profile,max_iterations=1)
    expected = {"scalar":1 if profile != "baseline" else None,
                "state":1 if profile in ("full","full_guard") else None,
                "control":1 if profile == "full_guard" else None}
    assert audit["requested_max_iterations"] == 1
    assert audit["effective_max_iterations"] == expected
    if profile == "full_guard":
        control = audit["stages"]["control"]
        assert control["effective_max_iterations"] == 1
        assert control["evidence"] == []
        assert control["function_status_counts"] == {"function_fallback": 1}
        assert not any(rel == "CONTROL_DEPENDENCE" for _,_,rel in enhancements(result))
    assert_preserved(graph,result,profile)
