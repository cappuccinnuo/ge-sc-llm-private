"""V2 materialized schema/support and supervised-gradient diagnostics.

Adapted from scripts/DFG/experiments/paper_runtime.py graph_schema_and_support
and gradient_audit; source SHA256:
319159bec961320307083f63dea2f4fb5eed3559db401c542bcd0af6eca6218e.
The adapter counts explicit REV_* canonicals, includes all three nested parts,
and never mutates the original graph. Graph registration and observed training
support are distinct: registered relations with no training edges stay present.
"""
import copy
from collections import Counter

import networkx as nx
import torch

from sco_models import graph_utils as gu
from scripts.DFG.experiments.common import digest
from scripts.DFG.experiments.runtime import assert_disconnected_files
from .. import FORWARD_RELATIONS, REVERSE_OF
from ..model import validate_registration
from ..model_input import edge_data, materialize
from .protocol import (FORWARD_SCOPE, PARTS, PROTOCOL_NAME, PROTOCOL_VERSION,
                       validate_parts)

V2_RELATIONS = FORWARD_RELATIONS | frozenset(REVERSE_OF.values())
SCHEMA_POLICY = "register_full_fixed_task_graph; audit_three_part_training_support"


def support(graph, profile, parts):
    """Count each materialized canonical by source file's nested membership."""
    assert_disconnected_files(graph)
    population = sorted({d["source_file"] for _, d in graph.nodes(data=True)})
    groups = validate_parts(parts, population)
    membership = {f: role for role in PARTS for f in groups[role]}
    working = gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(graph)))
    ids = gu.get_node_ids_dict(working)
    data = materialize(edge_data(working), profile)
    node_types, relations = sorted(ids), sorted(data)
    schema = {
        "node_types": [{"name": t, "index": i} for i, t in enumerate(node_types)],
        "canonical_relations": [{"canonical": list(c), "index": i}
                                for i, c in enumerate(relations)],
    }
    schema["sha256"] = digest(schema)
    nodes, edges = [], []
    for typ in node_types:
        counts = Counter(membership[working.nodes[n]["source_file"]] for n in ids[typ])
        row = {"name": typ}
        row.update({role + "_nodes": counts[role] for role in PARTS})
        nodes.append(row)
    for canonical in relations:
        source, destination = data[canonical]
        counts = Counter()
        for src, dst in zip(source.tolist(), destination.tolist()):
            sf = working.nodes[ids[canonical[0]][src]]["source_file"]
            df = working.nodes[ids[canonical[2]][dst]]["source_file"]
            if sf != df:
                raise ValueError("Materialized cross-file edge")
            counts[membership[sf]] += 1
        row = {"canonical": list(canonical)}
        row.update({role + "_edges": counts[role] for role in PARTS})
        edges.append(row)
    v2_count = sum(r["inner_train_edges"] for r in edges if r["canonical"][1] in V2_RELATIONS)
    return dict(
        protocol=PROTOCOL_NAME, protocol_version=PROTOCOL_VERSION,
        profile=profile, policy=SCHEMA_POLICY, forward_scope=FORWARD_SCOPE,
        schema=schema, supported=True,
        files={role: len(groups[role]) for role in PARTS},
        parts_sha256=digest(groups), nodes=nodes, relations=edges,
        registered_without_train_nodes=[r["name"] for r in nodes if not r["inner_train_nodes"]],
        registered_without_train_relations=[r["canonical"] for r in edges
                                            if not r["inner_train_edges"]],
        v2_training_edges=v2_count,
        ddg_training_edges=v2_count,
        no_samples_or_edges_removed=True,
    )


def _l1(gradient):
    if gradient is None:
        return 0.0
    if not bool(torch.isfinite(gradient).all()):
        raise AssertionError("Nonfinite supervised gradient")
    return float(gradient.detach().abs().sum())


def gradient_audit(model, registration_support):
    """Audit all v2 banks after backward, before decay/optimizer updates.

    An attention gradient may be zero when destination softmax has one incoming
    edge. A supported message slice can also have a zero observed gradient; that
    is reported distinctly from a disconnected parameter bank. Acceptance policy
    is applied by the caller, not by silently dropping such relations.
    """
    validate_registration(model, registration_support["schema"], deep=False)
    if model.dfg_profile != registration_support["profile"]:
        raise ValueError("Gradient support profile differs from model")
    backbone = [(n, p) for n, p in model.named_parameters() if not n.startswith("classify.")]
    if not any(p.grad is not None for _, p in backbone):
        raise AssertionError("Integration error: HGT backbone disconnected from supervised loss")
    result = {
        "backbone_gradient_l1": sum(_l1(p.grad) for _, p in backbone),
        "classifier_gradient_l1": sum(_l1(p.grad) for n, p in model.named_parameters()
                                      if n.startswith("classify.")),
        "v2_relations": [],
    }
    for row in registration_support["relations"]:
        canonical = tuple(row["canonical"])
        if canonical[1] not in V2_RELATIONS:
            continue
        index = model.etypes_dict[canonical]
        layers = []
        for layer_index, layer in enumerate(model.gcs):
            msg, att = layer.relation_msg.grad, layer.relation_att.grad
            layers.append(dict(layer=layer_index,
                message_gradient_l1=_l1(None if msg is None else msg[index]),
                attention_gradient_l1=_l1(None if att is None else att[index]),
                message_bank_connected=msg is not None,
                attention_bank_connected=att is not None))
        message = sum(r["message_gradient_l1"] for r in layers)
        attention = sum(r["attention_gradient_l1"] for r in layers)
        training = row["inner_train_edges"]
        if training and not any(r["message_bank_connected"] for r in layers):
            raise AssertionError("Integration error: registered supported v2 message bank disconnected")
        if not training and (message != 0 or attention != 0):
            raise AssertionError("Unexpected supervised gradient on heldout-only v2 relation")
        status = ("no_training_v2_support" if not training else
                  "training_support_nonzero_gradient" if message > 0 else
                  "training_support_zero_gradient_observed")
        result["v2_relations"].append(dict(row,
            message_gradient_l1=message, attention_gradient_l1=attention,
            per_layer=layers, status=status))
    result["v2_training_support"] = registration_support["v2_training_edges"]
    # Explicit compatibility aliases for the copied frozen fit loop. Both refer
    # to all v2 relations, never only the old DATA_DEF_USE subset.
    result["ddg_relations"] = copy.deepcopy(result["v2_relations"])
    result["ddg_training_support"] = result["v2_training_support"]
    result["note"] = ("Supervised gradients before optimizer/weight decay. "
        "Heldout-only registered relations remain present; zero is expected. "
        "A supported zero message gradient is explicitly recorded; single-edge "
        "attention softmax can legitimately have zero gradient.")
    return result
