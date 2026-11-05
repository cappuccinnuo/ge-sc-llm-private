"""One offline entry; reuse existing algorithms, preserving model nodes."""
import copy
import hashlib
from collections import Counter
from ..graph_audit import frozen, fingerprint
from ..pipeline import augment as scalar_augment
from ..state.stage_k.pipeline import prepare_graph as state_prepare
from ..state.stage_j.configuration import DDGConfig
from . import VERSION, RELATIONS, PROFILES


def assert_profile(graph, profile, original=False):
    if profile not in PROFILES:
        raise ValueError("Unknown DDG profile: " + str(profile))
    if not graph.is_directed() or not graph.is_multigraph():
        raise ValueError("Expected directed MultiDiGraph")
    allowed = frozenset() if original else PROFILES[profile]
    for _, data in graph.nodes(data=True):
        if not isinstance(data.get("source_file"), str) or not data.get("node_type"):
            raise ValueError("Nodes require exact source_file and node_type")
    for s, t, data in graph.edges(data=True):
        rel = data.get("edge_type")
        if not isinstance(rel, str):
            raise ValueError("Edges require edge_type")
        if rel.startswith("REV_") and rel[4:] in RELATIONS:
            raise ValueError("Reverse enhancement relations unsupported")
        if rel in RELATIONS and rel not in allowed:
            raise ValueError("Relation/profile mismatch: " + rel)
        if graph.nodes[s]["source_file"] != graph.nodes[t]["source_file"]:
            raise ValueError("Cross-file model edge unsupported")


def computation_fingerprint(graph):
    """Exact nodes/features/labels and typed edge multiplicity; no proof metadata."""
    edges = Counter((frozen(s), frozen(t), d["edge_type"]) for s,t,d in graph.edges(data=True))
    value = (frozen(list(graph.nodes(data=True))),
             tuple(sorted(edges.items(), key=lambda x: repr(x[0]))))
    return hashlib.sha256(repr(value).encode("utf8")).hexdigest()


def assert_preserved(base, enhanced, profile):
    assert_profile(enhanced, profile)
    if frozen(base.graph) != frozen(enhanced.graph):
        raise AssertionError("Original graph attributes changed")
    if frozen(list(base.nodes(data=True))) != frozen(list(enhanced.nodes(data=True))):
        raise AssertionError("Node order/identities/types/features/labels changed")
    retained = [(s,t,k,d) for s,t,k,d in enhanced.edges(keys=True,data=True)
                if d["edge_type"] not in RELATIONS]
    if frozen(list(base.edges(keys=True,data=True))) != frozen(retained):
        raise AssertionError("Original CFG/CG edge identities or attributes changed")
    seen = set()
    for s,t,d in enhanced.edges(data=True):
        if d["edge_type"] in RELATIONS:
            key = (s,t,d["edge_type"])
            if s == t or key in seen:
                raise AssertionError("Duplicate/self enhancement edge")
            seen.add(key)
    return {"base_nodes_exact": True, "base_edges_exact": True, "base_nodes": len(base),
            "base_edges": base.number_of_edges(), "output_edges": enhanced.number_of_edges(),
            "added_by_relation": dict(Counter(k[2] for k in seen))}


def build_graph(graph, sources=None, profile="full_guard", metadata=None, max_iterations=100000):
    """All profiles start from unenhanced HCG. Unknown files retain original samples."""
    assert_profile(graph, profile, original=True)
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be positive integer")
    before = fingerprint(graph)
    audit = {"version": VERSION, "profile": profile, "stages": {},
             "labels_used_for_analysis": False, "token_features_changed": False,
             "requested_max_iterations": max_iterations,
             "effective_max_iterations": {
                 "scalar": max_iterations if profile != "baseline" else None,
                 "state": max_iterations if profile in ("full", "full_guard") else None,
                 "control": max_iterations if profile == "full_guard" else None,
             },
             "source_hashes": {n: hashlib.sha256(c.encode("utf8")).hexdigest()
                               for n,c in (sources or {}).items()}, "input_fingerprint": before}
    output = copy.deepcopy(graph)
    if profile != "baseline":
        output, audit["stages"]["scalar"] = scalar_augment(output, sources or {}, max_iterations)
    if profile in ("full", "full_guard"):
        output, audit["stages"]["state"] = state_prepare(output, sources or {},
            DDGConfig(add_scalar=False, state_mode="orders", recovery="modifiers",
                      max_iterations=max_iterations), metadata or {})
    if profile == "full_guard":
        from .control_v2 import augment
        output, audit["stages"]["control"] = augment(
            output, sources or {}, metadata or {}, max_iterations=max_iterations)
    audit["invariants"] = assert_preserved(graph, output, profile)
    audit["output_fingerprint"] = fingerprint(output)
    audit["computation_fingerprint"] = computation_fingerprint(output)
    if fingerprint(graph) != before:
        raise AssertionError("Input mutated during enhancement")
    return output, audit
