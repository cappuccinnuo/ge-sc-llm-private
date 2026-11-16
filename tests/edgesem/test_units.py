"""Unit tests for the edgesem package on one reentrancy contract (no dataset needed)."""
import json
from pathlib import Path

import networkx as nx
import numpy as np
import pytest
import torch

from dfg.graph.pipeline import iter_build
from edgesem import schema
from edgesem.__main__ import main as cli
from edgesem.attributes import sources as attribute_sources
from edgesem.attributes.compute import _compute_attributes
from edgesem.attributes.layout import edge_rows, validate_vector
from edgesem.model.build import feature_indices, make_edge_model, validate_registration
from edgesem.model.layers import verify_frozen_sources
from edgesem.pipeline import build_edges
from hcg.store.io import sha256
from nodesem.facts.extract import extract
from tests.dfg.test_units import CONTRACT, CORPUS, fake_encoder
from tests.edgesem.canonical import attribute_digest, f4_digest, graph_positions

REFERENCE = json.loads((Path(__file__).parent / "reference" / "one_contract.json").read_text())


@pytest.fixture(scope="module")
def built():
    from hcg.cfg.builder import build_corpus
    graph, failures = build_corpus([CORPUS / CONTRACT])
    assert not failures
    for _, data in graph.nodes(data=True):
        data["token"] = np.zeros(512, dtype=np.float32)
        data["node_info_vulnerabilities"] = None
    source = (CORPUS / CONTRACT).read_bytes().decode("utf8")
    outputs = {k: (g, a) for k, g, a in iter_build(graph, {CONTRACT: source}, {CONTRACT: None}, ("L1", "L2", "L3"),
                                                   token_encoder=fake_encoder)}
    f3, audit = outputs["F3"]
    context = dict(task_id="reentrancy_node", graphs=dict(F0=graph, F3=f3),
                   order=[n for n, d in f3.nodes(data=True) if d["node_type"] != "env_source"],
                   sources={CONTRACT: dict(sha256=sha256(CORPUS / CONTRACT), metadata=None)},
                   source_text={CONTRACT: source}, audit=audit)
    edges, f4_audit = build_edges(context)
    context["f4_audit"] = f4_audit
    attrs, _ = _compute_attributes(context, f3, edges, extract("reentrancy_node", context))
    return context, edges, attrs


def test_schema_profiles_and_frozen_columns():
    assert set(schema.TRAIN_PROFILES) == set(schema.PROFILES)
    for name in schema.PROFILES:
        spec = schema.validate_profile(name)
        assert name.startswith("G3R") or spec["direction_mode"] == "typed"
    assert len(set(schema.CORE_INDICES)) == 50 and len(set(schema.CONTEXT_INDICES)) == 26
    assert set(schema.CORE_INDICES) | set(schema.CONTEXT_INDICES) <= set(range(74))
    assert feature_indices("G4R") == () and feature_indices("G4R-A") == schema.CORE_INDICES
    assert len(feature_indices("G4R-AC")) == len(set(schema.CORE_INDICES) | set(schema.CONTEXT_INDICES))
    assert schema.P2_OVERRIDES == dict(patience=51)


def test_one_contract_matches_the_sealed_edges_and_attributes(built):
    context, edges, attrs = built
    pos = graph_positions(context["graphs"]["F3"])
    assert context["f4_audit"]["hard_conditions_pass"]
    assert len(edges) == REFERENCE["f4"]["rows"]
    assert f4_digest(edges, pos) == REFERENCE["f4"]["digest"]
    assert len(attrs) == REFERENCE["attributes"]["rows"]
    assert attribute_digest(list(attrs), np.stack(list(attrs.values())), pos) == REFERENCE["attributes"]["digest"]
    for row in edge_rows(context["graphs"]["F3"], edges):
        validate_vector(attrs[row["key"]], row["relation"])


def test_attributes_do_not_depend_on_the_networkx_dominator_root(built, monkeypatch):
    """networkx >= 3.5 leaves the start node out of immediate_dominators; results must not change."""
    context, edges, attrs = built
    original = nx.immediate_dominators

    def without_root(graph, start):
        tree = dict(original(graph, start))
        tree.pop(start, None)
        return tree

    monkeypatch.setattr(attribute_sources.nx, "immediate_dominators", without_root)
    again, _ = _compute_attributes(context, context["graphs"]["F3"], edges, extract("reentrancy_node", context))
    assert again.keys() == attrs.keys() and all(np.array_equal(again[k], attrs[k]) for k in attrs)


@pytest.mark.parametrize("task", ["node", "contract"])
def test_every_profile_builds_validates_runs_and_reloads(built, task):
    context, edges, attrs = built
    graph = context["graphs"]["F3"]
    states = {}
    for profile in schema.TRAIN_PROFILES:
        uses = schema.PROFILES[profile]["edge_features"] != "none"
        model = make_edge_model(task, graph, profile, 0, edges=edges, attrs=attrs if uses else None)
        validate_registration(model, deep=True)
        model.eval()
        with torch.no_grad():
            out = model() if task == "node" else model([CONTRACT])[0]
        assert out.shape == ((graph.number_of_nodes(), 2) if task == "node" else (1, 2))
        assert torch.isfinite(out).all()
        twin = make_edge_model(task, graph, profile, 0, edges=edges, attrs=attrs if uses else None)
        assert all(torch.equal(v, twin.state_dict()[k]) for k, v in model.state_dict().items())
        twin.load_state_dict(model.state_dict(), strict=True)
        states[profile] = model.state_dict()
        if uses:
            layer = model.gcs[0]
            assert not layer.u.any() and not any(p.any() for p in layer.U.values())
    # Typed copies share the anchor's node-side parameters across profiles.
    assert torch.equal(states["G3R"]["gcs.0.k_linears.0.weight"], states["G4R-A"]["gcs.0.k_linears.0.weight"])
    assert torch.equal(states["G4R-A"]["edge_encoder.w1.weight"], states["G4R-Api"]["edge_encoder.w1.weight"])
    with pytest.raises(ValueError, match="F4 edges"):
        make_edge_model(task, graph, "G4R", 0)
    with pytest.raises(ValueError, match="attributes"):
        make_edge_model(task, graph, "G4R", 0, edges=edges, attrs=attrs)


def test_placebo_rewires_e1_edges_deterministically(built):
    context, edges, _ = built
    graph = context["graphs"]["F3"]
    a = make_edge_model("node", graph, "G4R-P", 0, edges=edges)
    b = make_edge_model("node", graph, "G4R-P", 0, edges=edges)
    assert a.edge_placebo_binding == b.edge_placebo_binding
    assert a.edge_placebo_binding["rows_sha256"] != a.edge_placebo_binding["real_rows_sha256"]


def test_edge_layer_pins_the_dfg_hgt_layer():
    """EdgeAwareHGTLayer copies the dfg shared-projection forward; a changed parent must be deliberate."""
    verify_frozen_sources()


def test_cli_rejects_unknown_category():
    with pytest.raises(SystemExit, match="unknown categories"):
        cli(["build", "--categories", "nope"])
