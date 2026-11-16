"""Cumulative L1 -> L2 -> L3 augmentation of an HCG with invariant checks after each layer."""
import copy
import hashlib
from collections import Counter
from numbers import Integral

import networkx as nx

from dfg.graph import env as l3, local as l1, state as l2
from dfg.graph.audit import computation_fingerprint, fingerprint, frozen
from dfg.schema import (
    DATA_DEF_USE,
    ENV_FLOW,
    ENV_SOURCE,
    FORWARD_RELATIONS,
    PROFILES,
    READS_STATE,
    REVERSE_OF,
    VERSION,
    WRITES_STATE,
    forward_relations)


# ----------------------------------------------------------------------
# dfg_v2/pipeline
# Compose the frozen L1/L2/L3 analyzers without rewriting their semantics.
#
# Sources are supplied once by the caller; each existing analyzer still owns its
# internal parser/view lifecycle. F0 is the original graph object. Serialized F0
# storage must reference the original file and SHA, never repickle this object.
PIPELINE_VERSION = "dfg-v2-pipeline-v1"

GRAPH_RELATIONS = {
    "F0": frozenset(),
    "F1": frozenset((DATA_DEF_USE,)),
    "F2": frozenset((DATA_DEF_USE, WRITES_STATE, READS_STATE)),
    "F3": FORWARD_RELATIONS,
}

LAYERS = ("L1", "L2", "L3")

_RELATION_LAYER = {
    DATA_DEF_USE: "L1", WRITES_STATE: "L2", READS_STATE: "L2", ENV_FLOW: "L3",
}

def layers_for_key(key):
    if key not in GRAPH_RELATIONS:
        raise ValueError("Unknown forward graph key: " + str(key))
    return LAYERS[:int(key[1:])]

def key_for_layers(layers):
    if not isinstance(layers, (tuple, list)):
        raise ValueError("layers must be an ordered L1/L2/L3 prefix")
    layers = tuple(layers)
    if layers not in [LAYERS[:n] for n in range(4)]:
        raise ValueError("layers must be an ordered L1/L2/L3 prefix")
    return "F" + str(len(layers))

def key_for_profile(profile):
    relations = forward_relations(profile)
    if PROFILES[profile] - (FORWARD_RELATIONS | frozenset(REVERSE_OF.values())):
        raise ValueError("Profile declares an unknown relation: " + str(profile))
    matches = [key for key, allowed in GRAPH_RELATIONS.items() if relations == allowed]
    if len(matches) != 1:
        raise ValueError("Profile forward relations have no unique graph key: " + str(profile))
    return matches[0]

def profiles_for_key(key):
    layers_for_key(key)
    # No second profile table: directional controls registered later work too.
    return tuple(profile for profile in PROFILES if key_for_profile(profile) == key)

def _base(graph):
    if not isinstance(graph, nx.MultiDiGraph) or not graph:
        raise ValueError("Expected a nonempty original HCG MultiDiGraph")
    for _, data in graph.nodes(data=True):
        if (not isinstance(data.get("source_file"), str) or not data["source_file"]
                or not isinstance(data.get("node_type"), str) or not data["node_type"]):
            raise ValueError("Nodes require source_file and node_type")
        if data["node_type"] == ENV_SOURCE or data.get("dfg_v2_aux"):
            raise ValueError("Expected original HCG without auxiliary nodes")
    for src, dst, attrs in graph.edges(data=True):
        relation = attrs.get("edge_type")
        if not isinstance(relation, str):
            raise ValueError("Edges require edge_type")
        if relation in FORWARD_RELATIONS or relation.startswith("REV_"):
            raise ValueError("Expected original HCG without v2 or REV relations")
        if graph.nodes[src]["source_file"] != graph.nodes[dst]["source_file"]:
            raise ValueError("Cross-file original edge")

def _evidence(source, target, attrs, layers):
    relation = attrs["edge_type"]
    layer = _RELATION_LAYER[relation]
    if layer not in layers:
        raise AssertionError("Missing layer evidence: " + layer)
    proof = layers[layer].get("evidence", [])
    index_key = "ddg_fact_indices" if relation == DATA_DEF_USE else "evidence_indices"
    indices = attrs.get(index_key)
    if (not isinstance(indices, list) or not indices or
            any(not isinstance(i, Integral) or isinstance(i, bool) or i < 0 or i >= len(proof)
                for i in indices) or len(indices) != len(set(indices))):
        raise AssertionError("Invalid or missing v2 edge evidence indices")
    for index in indices:
        evidence = proof[index]
        if evidence.get("source") != source or evidence.get("target") != target:
            raise AssertionError("Edge/evidence endpoint mismatch")
        if relation == DATA_DEF_USE:
            if evidence.get("self_fact") is not False:
                raise AssertionError("Self fact cannot justify a model edge")
        else:
            if evidence.get("status") != "projected":
                raise AssertionError("Unprojected evidence cannot justify a model edge")
            if relation in (WRITES_STATE, READS_STATE) and evidence.get("relation") != relation:
                raise AssertionError("Edge/evidence relation mismatch")
            if relation == ENV_FLOW and evidence.get("env_key") != attrs.get("env_key"):
                raise AssertionError("Environment edge/evidence key mismatch")
    return layer, indices

def assert_preserved(base, output, key, layer_audits):
    """Validate original identities/attributes and every added edge's proof."""
    allowed = GRAPH_RELATIONS[key]
    if frozen(base.graph) != frozen(output.graph):
        raise AssertionError("Original graph attributes changed")
    retained_nodes = [(n, d) for n, d in output.nodes(data=True) if n in base]
    if frozen(list(base.nodes(data=True))) != frozen(retained_nodes):
        raise AssertionError("Original node identities/order/attributes changed")
    if list(output)[:len(base)] != list(base):
        raise AssertionError("Original node insertion order changed")
    retained_edges = [(s, t, k, d) for s, t, k, d in output.edges(keys=True, data=True)
                      if d.get("edge_type") not in FORWARD_RELATIONS]
    if frozen(list(base.edges(keys=True, data=True))) != frozen(retained_edges):
        raise AssertionError("Original edge identities/order/attributes changed")
    extras = [n for n in output if n not in base]
    if key != "F3" and extras:
        raise AssertionError("Only F3 may add nodes")
    if any(output.nodes[n].get("node_type") != ENV_SOURCE or
           output.nodes[n].get("dfg_v2_aux") is not True for n in extras):
        raise AssertionError("Unexpected auxiliary node")
    seen, referenced = set(), {layer: set() for layer in layer_audits}
    for source, target, attrs in output.edges(data=True):
        relation = attrs.get("edge_type")
        if not isinstance(relation, str) or relation.startswith("REV_"):
            raise AssertionError("Invalid/REV relation in stored graph")
        if output.nodes[source]["source_file"] != output.nodes[target]["source_file"]:
            raise AssertionError("Cross-file edge")
        if relation not in FORWARD_RELATIONS:
            continue
        if relation not in allowed:
            raise AssertionError("Relation outside graph key")
        triple = (source, target, relation)
        if source == target or triple in seen:
            raise AssertionError("Duplicate/self v2 edge")
        seen.add(triple)
        layer, indices = _evidence(source, target, attrs, layer_audits)
        if referenced[layer].intersection(indices):
            raise AssertionError("Evidence reused by different model edges")
        referenced[layer].update(indices)
    for layer, audit in layer_audits.items():
        if audit.get("labels_used_for_analysis") is not False:
            raise AssertionError("Layer must explicitly exclude labels from analysis")
        expected = {i for i, evidence in enumerate(audit.get("evidence", []))
                    if (not evidence.get("self_fact", True) if layer == "L1"
                        else evidence.get("status") == "projected")}
        if referenced[layer] != expected:
            raise AssertionError("Projected evidence missing from graph")
    if key == "F3":
        # This also checks consecutive IDs, auxiliary labels/features, endpoints,
        # per-file/key uniqueness, and exact removal of ENV nodes and edges.
        l3.assert_preserved(l3.strip_aux(output), output)
    return dict(original_nodes_exact=True, original_edges_and_attributes_exact=True,
                no_cross_file_edges=True, no_reverse_edges=True,
                evidence_complete=True, added_nodes=len(extras),
                added_by_relation=dict(Counter(t[2] for t in seen)))

def iter_build(graph, sources, metadata, layers, token_encoder=None, max_iterations=100000):
    """Yield F0 and each cumulative layer exactly once, without mutating inputs."""
    final_key = key_for_layers(layers)
    layers = tuple(layers)
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    if (not isinstance(sources, dict) or
            any(not isinstance(f, str) or not isinstance(s, str) for f, s in sources.items())):
        raise ValueError("sources must map exact file identities to source strings")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("metadata must be a file-keyed dictionary or None")
    if "L3" in layers and not callable(token_encoder):
        raise ValueError("L3 requires a callable token_encoder")
    _base(graph)
    before = fingerprint(graph)
    input_computation = computation_fingerprint(graph)
    files = {d["source_file"] for _, d in graph.nodes(data=True)}
    source_hashes = {f: hashlib.sha256(sources[f].encode("utf8")).hexdigest()
                     for f in sorted(files & set(sources))}
    missing = sorted(files - set(sources))
    provenance = copy.deepcopy(getattr(token_encoder, "provenance", None))
    if token_encoder is not None and provenance is None:
        provenance = {"source": "caller_supplied_encoder"}
    layer_audits = {}
    output = graph

    def snapshot(key):
        checks = assert_preserved(graph, output, key, layer_audits)
        if fingerprint(graph) != before:
            raise AssertionError("Pipeline mutated the original HCG")
        return dict(version=VERSION, pipeline_version=PIPELINE_VERSION, graph_key=key,
                    requested_graph_key=final_key, profiles=list(profiles_for_key(key)),
                    forward_relations=sorted(GRAPH_RELATIONS[key]), layers=copy.deepcopy(layer_audits),
                    input_fingerprint=before, output_fingerprint=fingerprint(output),
                    input_computation_fingerprint=input_computation,
                    computation_fingerprint=computation_fingerprint(output),
                    source_hashes=dict(source_hashes), missing_sources=missing[:],
                    tokenizer=copy.deepcopy(provenance), labels_used_for_analysis=False,
                    requested_max_iterations=max_iterations, invariants=checks,
                    parsing="existing analyzers own their parse/view lifecycle")

    yield "F0", output, snapshot("F0")
    for layer in layers:
        previous = output
        previous_fingerprint = fingerprint(previous)
        if layer == "L1":
            output, record = l1.augment_l1(previous, sources, metadata, max_iterations)
        elif layer == "L2":
            output, record = l2.augment_l2(previous, sources, metadata)
        else:
            output, record = l3.augment_l3(previous, sources, metadata, token_encoder)
        if fingerprint(previous) != previous_fingerprint:
            raise AssertionError("Layer mutated its preceding graph")
        layer_audits[layer] = record
        key = key_for_layers(layers[:layers.index(layer) + 1])
        yield key, output, snapshot(key)

def build(graph, sources, metadata, layers, token_encoder=None, max_iterations=100000):
    """Return only the final graph/audit; iter_build exposes incremental outputs."""
    result = None
    for _, output, audit in iter_build(graph, sources, metadata, layers,
                                      token_encoder, max_iterations):
        result = output, audit
    return result
