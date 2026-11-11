"""EP7 approved adaptation of scripts/DFG/dfg_v2/benchmark_v2/support.py.
Frozen source SHA256: 00dd098948c72b68ae18164c180d124ce1323ca02fac1aef5f2372840559dcfc
Numeric training is unchanged; only EdgeSem registration/audit routing differs.
"""
"""Prompt 8H adaptation of experiment/support.py.\nFrozen source SHA256: 2cf21566bd48ba4183863b45582585d56fe05b05de7fdc4dd88621c1493ec859
Old-input equivalence is required before execution.
"""
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
from scripts.DFG.dfg_v2 import FORWARD_RELATIONS, REVERSE_OF
from .model import validate_registration
from scripts.DFG.dfg_v2.model_input import edge_data
from .materialize import materialize
from . import NEW_RELATIONS
from scripts.DFG.dfg_v2.benchmark_v2.protocol import (FORWARD_SCOPE, PARTS, PROTOCOL_NAME, PROTOCOL_VERSION,
                       validate_parts)

V2_RELATIONS = FORWARD_RELATIONS | frozenset(REVERSE_OF.values()) | frozenset(NEW_RELATIONS) | frozenset("REV_"+r for r in NEW_RELATIONS)
SCHEMA_POLICY = "register_full_fixed_task_graph; audit_three_part_training_support"


def support(graph, profile, parts):
    """Count each materialized canonical by source file's nested membership."""
    assert_disconnected_files(graph)
    population = sorted({d["source_file"] for _, d in graph.nodes(data=True)})
    groups = validate_parts(parts, population)
    membership = {f: role for role in PARTS for f in groups[role]}
    working = gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(graph)))
    ids = gu.get_node_ids_dict(working)
    data = materialize(edge_data(working), profile)[0]
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
    if getattr(model,"edge_profile",model.dfg_profile) != registration_support["profile"]:
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
    result["placebo_empty_relations"]=[]
    for canonical,index in model.etypes_dict.items():
        if not canonical[1].startswith("__G0P_EMPTY_"):
            continue
        per_layer=[]
        for i,layer in enumerate(model.gcs):
            values={name:_l1(None if getattr(layer,name).grad is None else getattr(layer,name).grad[index])
                    for name in ("relation_msg","relation_att","relation_pri")}
            if any(values.values()):raise AssertionError("Nonzero empty-relation supervised gradient")
            per_layer.append(dict(layer=i,gradient_l1=values))
        result["placebo_empty_relations"].append(dict(canonical=list(canonical),per_layer=per_layer))
    if hasattr(model, "edge_encoder"):
        result["edge_parameters"] = edge_gradient_audit(model)
    return result

def model_support(model, parts):
    """Actual canonical support, including registered zero-edge placebo rows."""
    from collections import Counter
    schema=validate_registration(model)
    population=sorted({d["source_file"] for _,d in model.nx_graph.nodes(data=True)})
    groups=validate_parts(parts,population)
    membership={f:role for role in PARTS for f in groups[role]}
    nodes=[]
    for typ,ids in model.node_ids_dict.items():
        counts=Counter(membership[model.nx_graph.nodes[i]["source_file"]] for i in ids)
        nodes.append(dict(name=typ,**{role+"_nodes":counts[role] for role in PARTS}))
    edges=[]
    graph=model.symmetrical_global_graph
    for c in graph.canonical_etypes:
        counts=Counter()
        ss,tt=graph.edges(etype=c,order="eid")
        for s,t in zip(ss.cpu().tolist(),tt.cpu().tolist()):
            sf=model.nx_graph.nodes[model.node_ids_dict[c[0]][s]]["source_file"]
            tf=model.nx_graph.nodes[model.node_ids_dict[c[2]][t]]["source_file"]
            if sf!=tf:raise ValueError("Cross-file graph connection")
            counts[membership[sf]]+=1
        edges.append(dict(canonical=list(c),**{r+"_edges":counts[r] for r in PARTS}))
    v2=sum(r["inner_train_edges"] for r in edges if r["canonical"][1] in V2_RELATIONS)
    return dict(protocol=PROTOCOL_NAME,protocol_version=PROTOCOL_VERSION,profile=getattr(model,"edge_profile",model.dfg_profile),
        policy=SCHEMA_POLICY,forward_scope=FORWARD_SCOPE,schema=schema,supported=True,
        files={r:len(groups[r]) for r in PARTS},parts_sha256=digest(groups),nodes=nodes,relations=edges,
        registered_without_train_nodes=[r["name"] for r in nodes if not r["inner_train_nodes"]],
        registered_without_train_relations=[r["canonical"] for r in edges if not r["inner_train_edges"]],
        v2_training_edges=v2,ddg_training_edges=v2,no_samples_or_edges_removed=True)


def edge_gradient_audit(model):
    """Bank-level connectivity; zero encoder gradient at u=U=0 is required."""
    layers=[];all_zero=True
    for i,layer in enumerate(model.gcs):
        zero=not bool(torch.count_nonzero(layer.u.detach())) and all(
            not bool(torch.count_nonzero(p.detach())) for p in layer.U.values())
        all_zero=all_zero and zero
        u=_l1(layer.u.grad)
        per_family={f:_l1(p.grad) for f,p in layer.U.items()}
        U=sum(per_family.values())
        if zero and (u<=0 or U<=0):
            raise AssertionError("Initial edge u/U bank disconnected or zero")
        layers.append(dict(layer=i,u_gradient_l1=u,U_gradient_l1=U,
            U_families_gradient_l1=per_family,initial_zero_correction=zero,
            u_frobenius=float(layer.u.detach().norm()),
            U_frobenius={f:float(p.detach().norm()) for f,p in layer.U.items()}))
    encoder={n:_l1(p.grad) for n,p in model.edge_encoder.named_parameters()}
    total=sum(encoder.values())
    if all_zero and total!=0:
        raise AssertionError("Encoder gradient must be zero when every correction is zero")
    return dict(layers=layers,encoder_gradient_l1=total,encoder_parameters=encoder,
        zero_encoder_expected=all_zero,
        note="u/U nonzero check is per layer bank; no per-slice nonzero requirement")


def edge_norms(model):
    rows=[]
    for i,layer in enumerate(model.gcs):
        rows.append(dict(layer=i,u_frobenius=float(layer.u.detach().norm()),
            U_frobenius={f:float(p.detach().norm()) for f,p in layer.U.items()}))
    return rows
