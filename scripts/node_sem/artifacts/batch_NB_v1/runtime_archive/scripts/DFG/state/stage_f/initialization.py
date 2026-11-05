"""Experimental Stage F schema extension of frozen semantic paired initialization.
Copied from protocol.py at HEAD 08a4488; numeric RNG and tensor mapping unchanged.
Old protocol initializer remains untouched. This module is not wired to training.
"""
import re,math,json
from ...experiments.protocol import _validate_schema,_state_digest,_digest
from . import FORWARD_RELATIONS
INITIALIZATION_VERSION="state-forward-semantic-paired-v1"
def initialize_pair(e0_model, e1_model, seed=1):
    """Copy *fresh* E0 weights to E1 by node name and canonical relation.

    Both supplied models must be newly constructed, without optimization or
    checkpoint loading. No E0 trained checkpoint is read or accepted here.
    E0 is left unchanged. New forward relation slices receive isolated
    deterministic initial draws; classifier and common HGT/adaptation parameters
    are exactly equal by semantic identity even when integer type IDs differ.
    """
    import torch
    nodes0, nodes1 = e0_model.ntypes_dict, e1_model.ntypes_dict
    edges0, edges1 = e0_model.etypes_dict, e1_model.etypes_dict
    for mapping in (nodes0, nodes1):
        _validate_schema(mapping)
    for mapping in (edges0, edges1):
        _validate_schema(mapping, canonical=True)
    if set(nodes0) != set(nodes1):
        raise ValueError("Paired graph node type sets differ")
    if not set(edges0).issubset(edges1):
        raise ValueError("E1 removed an E0 canonical relation")
    for nodes, edges in ((nodes0, edges0), (nodes1, edges1)):
        if any(edge[0] not in nodes or edge[2] not in nodes for edge in edges):
            raise ValueError("Canonical relation references unknown node types")
    new_edges = set(edges1) - set(edges0)
    if any(edge[1] not in FORWARD_RELATIONS for edge in new_edges):
        raise ValueError("Only registered forward enhancement relations may be added")
    source = {k: v.detach().cpu().clone() for k, v in e0_model.state_dict().items()}
    target = {k: v.detach().cpu().clone() for k, v in e1_model.state_dict().items()}
    initial_e0_hash = _state_digest(source)
    if set(source) != set(target):
        raise ValueError("Paired architectures have different state keys")
    inverse1 = {index: name for name, index in nodes1.items()}
    shared0, shared1, new_state = {}, {}, {}
    node_pattern = re.compile(r"^(adapt_ws)\.(\d+)\.(.+)$")
    layer_node_pattern = re.compile(
        r"^(gcs\.\d+\.(?:k_linears|q_linears|v_linears|a_linears|norms))\.(\d+)\.(.+)$")
    for name, value in target.items():
        if re.match(r"^gcs\.\d+\.relation_(pri|att|msg)$", name):
            if value.shape[0] != len(edges1) or source[name].shape[0] != len(edges0):
                raise ValueError("Relation tensor/schema mismatch: " + name)
            if value.shape[1:] != source[name].shape[1:]:
                raise ValueError("Relation tensor shapes differ: " + name)
            for edge, index in sorted(edges1.items()):
                identity = name + "|" + json.dumps(edge)
                if edge in edges0:
                    value[index].copy_(source[name][edges0[edge]])
                    shared0[identity] = source[name][edges0[edge]]
                    shared1[identity] = value[index]
                else:
                    relation_seed = int(_digest([int(seed), name, edge])[:15], 16)
                    with torch.random.fork_rng(devices=[]):
                        torch.manual_seed(relation_seed)
                        if name.endswith("relation_pri"):
                            value[index].fill_(1)
                        else:
                            # Match the original HGT full relation-bank Xavier
                            # distribution, not the fan dimensions of a 3D slice.
                            fan_in, fan_out = torch.nn.init._calculate_fan_in_and_fan_out(value)
                            bound = math.sqrt(6.0 / float(fan_in + fan_out))
                            value[index].uniform_(-bound, bound)
                    new_state[identity] = value[index]
        elif re.match(r"^gcs\.\d+\.skip$", name):
            if value.shape != (len(nodes1),) or source[name].shape != (len(nodes0),):
                raise ValueError("Skip vector/schema mismatch")
            for node, index in nodes1.items():
                identity = name + "|" + node
                value[index].copy_(source[name][nodes0[node]])
                shared0[identity] = source[name][nodes0[node]]
                shared1[identity] = value[index]
        else:
            match = node_pattern.match(name) or layer_node_pattern.match(name)
            if match:
                prefix, index, suffix = match.groups()
                node = inverse1[int(index)]
                source_name = prefix + "." + str(nodes0[node]) + "." + suffix
                identity = prefix + "|" + node + "|" + suffix
            else:
                source_name = name
                identity = name
            if value.shape != source[source_name].shape:
                raise ValueError("Common parameter shape mismatch: " + name)
            value.copy_(source[source_name])
            shared0[identity] = source[source_name]
            shared1[identity] = value
    if _state_digest(shared0) != _state_digest(shared1):
        raise AssertionError("Semantically shared initial weights differ")
    e1_model.load_state_dict(target, strict=True)
    if _state_digest(e0_model.state_dict()) != initial_e0_hash:
        raise AssertionError("Paired initialization mutated E0")
    return {"initialization_version": INITIALIZATION_VERSION, "new_relation_seed": int(seed),
            "initialization_source": "fresh E0 constructor state; no trained checkpoint",
            "e0_state_sha256": initial_e0_hash,
            "e1_state_sha256": _state_digest(e1_model.state_dict()),
            "shared_semantic_sha256": _state_digest(shared0),
            "new_relations_sha256": _state_digest(new_state),
            "shared_tensor_count": len(shared0),
            "new_canonical_relations": [list(e) for e in sorted(new_edges)],
            "node_type_alignment": {n: [nodes0[n], nodes1[n]] for n in sorted(nodes0)},
            "e0_canonical_order": [list(e) for e, _ in sorted(edges0.items(), key=lambda x: x[1])],
            "e1_canonical_order": [list(e) for e, _ in sorted(edges1.items(), key=lambda x: x[1])],
            "e0_parameters": sum(p.numel() for p in e0_model.parameters()),
            "e1_parameters": sum(p.numel() for p in e1_model.parameters())}
