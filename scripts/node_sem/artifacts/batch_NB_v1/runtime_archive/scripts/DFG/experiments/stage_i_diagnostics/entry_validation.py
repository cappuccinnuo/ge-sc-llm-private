"""Read-only Stage I entry guard; frozen training entry points are not patched.

This checks relation-direction compatibility, not checkpoint/source provenance.
Callers must still run the existing graph/label/feature/schema/receipt validators.
"""
from collections import Counter

from scripts.DFG.state.stage_f import FORWARD_RELATIONS

VALID_ENTRIES = frozenset(("legacy", "stage_f", "e23_pilot"))
STATE_RELATIONS = FORWARD_RELATIONS - frozenset(("DATA_DEF_USE",))
RESERVED_PREFIXES = ("DATA_", "STATE_", "REV_", "EXTERNAL_CALL_")
VALIDATOR_VERSION = "stage-i-entry-direction-v1"


def validate_entry(graph, entry_name):
    """Return a JSON-safe compatibility audit, without changing graph or model.

    Explicit opt-in sidecar: directly calling an old training script bypasses it.
    legacy protects only DATA_DEF_USE; state-aware inputs require stage_f or
    e23_pilot. Unknown enhancement relations fail closed; ordinary CFG/CG edge
    names are preserved, not whitelisted or removed.
    """
    if not isinstance(entry_name, str) or entry_name not in VALID_ENTRIES:
        raise ValueError("Unknown entry: {!r}; expected {}".format(
            entry_name, sorted(VALID_ENTRIES)))
    if not (hasattr(graph, "is_directed") and graph.is_directed()
            and graph.is_multigraph()):
        raise ValueError("Expected a directed HCG multigraph")
    for _, attrs in graph.nodes(data=True):
        if not isinstance(attrs.get("node_type"), str) or not attrs["node_type"]:
            raise ValueError("Every HCG node must have a nonempty node_type")
    counts = Counter()
    canonicals = set()
    for source, target, attrs in graph.edges(data=True):
        relation = attrs.get("edge_type")
        if not isinstance(relation, str) or not relation:
            raise ValueError("Every HCG edge must have a nonempty edge_type")
        if (relation.startswith(RESERVED_PREFIXES)
                and relation not in FORWARD_RELATIONS):
            raise ValueError("Unsupported enhancement relation: " + relation)
        counts[relation] += 1
        canonicals.add((graph.nodes[source]["node_type"], relation,
                       graph.nodes[target]["node_type"]))
    state = sorted(STATE_RELATIONS.intersection(counts))
    if state and entry_name == "legacy":
        raise ValueError("Legacy reflect_graph would reflect state relations {}; "
                         "use stage_f or e23_pilot".format(state))
    enhancements = sorted(FORWARD_RELATIONS.intersection(counts))
    return {
        "validator_version": VALIDATOR_VERSION,
        "entry_name": entry_name,
        "supported": True,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "relation_counts": dict(sorted(counts.items())),
        "canonical_relations": [list(item) for item in sorted(canonicals)],
        "enhancement_relations": enhancements,
        "state_relations": state,
        "direction_policy": (
            "legacy_CFG_CG_reflection_with_forward_DATA_DEF_USE"
            if entry_name == "legacy"
            else "legacy_CFG_CG_reflection_with_four_forward_enhancements"),
        "scope": "relation_direction_compatibility_only",
        "graph_mutated": False,
        "intercepts_unmodified_legacy_scripts": False,
    }
