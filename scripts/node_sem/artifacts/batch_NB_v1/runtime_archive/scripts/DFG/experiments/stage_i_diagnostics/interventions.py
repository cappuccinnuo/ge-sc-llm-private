"""Fixed-weight state-relation interventions, retaining native HGT computation.

Reuses DiagnosticContext's instance-only forward binding/restoration and the
message-zero operation from experiments/audit/ddg_diagnostics_v1/interventions.py.
No HGT forward, attention, schema, graph, parameter, or cross-mean replacement.

The observed norms are Frobenius norms of each canonical relation's destination
SUM aggregate (after native attention), not per-edge norms or contribution
attributions. Zeroing a message keeps every canonical relation in cross-mean.
Normal/absent-relation modes remain the original numerical forward.
"""
import json
import math
import types
from collections import Counter

import torch

from scripts.DFG.experiments.audit.ddg_diagnostics_v1.interventions import (
    DiagnosticContext, _ABSENT, _restore_attr, _zero_message,
)

VERSION = "stage-i-native-message-zero-v1"
RELATIONS = frozenset(("STATE_DEF_USE", "STATE_ACCESS_ORDER",
                       "EXTERNAL_CALL_BEFORE_STATE_WRITE"))


def _norm(tensor):
    # One scalar per relation; no retained tensors or per-node norm arrays.
    value = float(torch.norm(tensor.detach()).cpu())
    if not math.isfinite(value):
        raise ValueError("Non-finite diagnostic aggregate norm")
    return value


class StateIntervention(DiagnosticContext):
    """Temporary native-message intervention on one eval model instance.

    Use inside torch.no_grad(). `audit` is JSON serializable and contains only
    scalar accumulators, schema identifiers, and counts. Repeated forwards add
    observations rather than retaining node representations. Norms across
    invocations are stored as sums/maxima, not treated as independent evidence.
    """
    def __init__(self, model, relations=(), record=True):
        if isinstance(relations, str):
            raise TypeError("relations must be a sequence of relation names")
        selected = frozenset(relations)
        if selected - RELATIONS:
            raise ValueError("Only state/order relations can be intervened on: " +
                             repr(sorted(selected - RELATIONS)))
        super().__init__(model, record=record)
        self.relations = selected
        self.audit = {
            "version": VERSION, "requested_relations": sorted(selected),
            "record": bool(record),
            "method": "zero_after_native_attention_before_native_sum_and_cross_mean",
            "norm_unit": "canonical_destination_sum_Frobenius_L2",
            "graph_schema_and_cross_mean_denominator_preserved": True,
            "layers": {},
        }

    def _forward(self, index, layer, original_forward, graph, hidden):
        if torch.is_grad_enabled():
            raise ValueError("Fixed-weight diagnostics require torch.no_grad()")
        previous_multi = graph.__dict__.get("multi_update_all", _ABSENT)
        previous_node_frames, previous_edge_frames = graph._node_frames, graph._edge_frames
        native_multi = graph.multi_update_all
        stat = None
        if self.record:
            stat = self.audit["layers"].setdefault(str(index), {
                "forward_calls": 0, "canonical": {}, "cross_mean": {},
                "present_requested_relations": [], "absent_requested_relations": [],
            })
            stat["forward_calls"] += 1
            names = {c[1] for c in graph.canonical_etypes}
            stat["present_requested_relations"] = sorted(self.relations & names)
            stat["absent_requested_relations"] = sorted(self.relations - names)

        def intercepted(this, etype_dict, cross_reducer, apply_node_func=None):
            if cross_reducer != "mean" or apply_node_func is not None:
                raise RuntimeError("Unexpected native HGT aggregation signature")
            effective = dict(etype_dict)
            counts = Counter(c[2] for c in etype_dict)
            for canonical, funcs in etype_dict.items():
                selected = canonical[1] in self.relations
                if selected:
                    eid = layer.edge_dict[canonical]
                    effective[canonical] = (_zero_message("v_%d" % eid),) + tuple(funcs[1:])
                if self.record:
                    # Observe ORIGINAL relation sums before masking. Subgraph
                    # scope leaves parent input frames and attention unchanged.
                    sub = graph[canonical]
                    with sub.local_scope():
                        sub.update_all(*funcs)
                        value = _norm(sub.dstdata["t"])
                    key = json.dumps(list(canonical), separators=(",", ":"))
                    row = stat["canonical"].setdefault(key, {
                        "canonical": list(canonical), "masked": selected,
                        "edge_count": graph.num_edges(canonical),
                        "destination_node_count": graph.num_nodes(canonical[2]),
                        "cross_mean_relation_count": counts[canonical[2]],
                        "observations": 0, "original_aggregate_l2_sum": 0.0,
                        "original_aggregate_l2_max": 0.0,
                        "zeroed_aggregate_l2_sum": 0.0,
                        "effective_aggregate_l2_sum": 0.0,
                    })
                    if (row["edge_count"] != graph.num_edges(canonical) or
                            row["cross_mean_relation_count"] != counts[canonical[2]]):
                        raise ValueError("Diagnostic graph changed between forwards")
                    row["observations"] += 1
                    row["original_aggregate_l2_sum"] += value
                    row["original_aggregate_l2_max"] = max(row["original_aggregate_l2_max"], value)
                    row["zeroed_aggregate_l2_sum"] += value if selected else 0.0
                    row["effective_aggregate_l2_sum"] += 0.0 if selected else value
            result = native_multi(effective, cross_reducer, apply_node_func)
            if self.record:
                for ntype, count in counts.items():
                    value = _norm(graph.nodes[ntype].data["t"])
                    row = stat["cross_mean"].setdefault(ntype, {
                        "cross_mean_relation_count": count, "observations": 0,
                        "effective_aggregate_l2_sum": 0.0,
                        "effective_aggregate_l2_max": 0.0,
                    })
                    row["observations"] += 1
                    row["effective_aggregate_l2_sum"] += value
                    row["effective_aggregate_l2_max"] = max(row["effective_aggregate_l2_max"], value)
            return result

        graph.multi_update_all = types.MethodType(intercepted, graph)
        try:
            return original_forward(graph, hidden)
        finally:
            # DGL 0.6 local_scope is not exception-safe; preserve original frame
            # references even when native forward or observation raises.
            graph._node_frames, graph._edge_frames = previous_node_frames, previous_edge_frames
            _restore_attr(graph, "multi_update_all", previous_multi)


def intervention(model, relations=(), record=True):
    """Return an eval-only, no-grad, reversible message-zero context manager."""
    return StateIntervention(model, relations=relations, record=record)
