"""Typed relation parameter copy from the G3R anchor; new E1 rows use a per-relation
sha256 seed and the anchor bank's Xavier bound. No global RNG is consumed.
"""
import hashlib
import json
import math

import torch

from edgesem.schema import NEW_RELATIONS, REVERSE_PREFIX


RELATION_PARAMETERS = ("relation_att", "relation_msg", "relation_pri")

def canonical_string(canonical):
    if not isinstance(canonical, tuple) or len(canonical)!=3 or any(
            not isinstance(s,str) or not s for s in canonical):
        raise ValueError("Invalid canonical key")
    return json.dumps(list(canonical), ensure_ascii=True, separators=(",",":"))

def relation_seed(canonical):
    return int(hashlib.sha256(canonical_string(canonical).encode("utf-8")).hexdigest()[:16],16)

def copy_typed_layer_parameters(anchor_layer, new_layer, key_map):
    if anchor_layer is new_layer:
        raise ValueError("Provide a distinct fresh receiving layer")
    if anchor_layer.node_dict != new_layer.node_dict:
        raise ValueError("Node type order differs")
    for bank in (anchor_layer.edge_dict, new_layer.edge_dict):
        if set(bank.values()) != set(range(len(bank))):
            raise ValueError("Invalid relation indices")
    if not set(key_map) <= set(new_layer.edge_dict) or not set(key_map.values()) <= set(anchor_layer.edge_dict):
        raise ValueError("Key map references an absent relation")
    for c in set(new_layer.edge_dict)-set(key_map):
        relation = c[1][len(REVERSE_PREFIX):] if c[1].startswith(REVERSE_PREFIX) else c[1]
        if relation not in NEW_RELATIONS:
            raise ValueError("Only new E1 relation rows may lack an anchor")
    src = anchor_layer.state_dict()
    dst = {k:v.detach().clone() for k,v in new_layer.state_dict().items()}
    if set(src)!=set(dst):
        raise ValueError("Layer parameter sets differ")
    for name,value in dst.items():
        if name in RELATION_PARAMETERS:
            if (src[name].shape[1:]!=value.shape[1:] or src[name].shape[0]!=len(anchor_layer.edge_dict)
                    or value.shape[0]!=len(new_layer.edge_dict) or src[name].dtype!=value.dtype):
                raise ValueError("Relation bank shape/dtype mismatch")
        else:
            if value.shape!=src[name].shape or value.dtype!=src[name].dtype:
                raise ValueError("Shared parameter shape/dtype mismatch")
            value.copy_(src[name])
    h, dk = anchor_layer.n_heads, anchor_layer.d_k
    if (new_layer.n_heads,new_layer.d_k)!=(h,dk):
        raise ValueError("Attention dimensions differ")
    bound = math.sqrt(6.0/((h+len(anchor_layer.edge_dict))*dk*dk))
    for c,index in new_layer.edge_dict.items():
        if c in key_map:
            for name in RELATION_PARAMETERS:
                dst[name][index].copy_(src[name][anchor_layer.edge_dict[key_map[c]]])
        else:
            gen = torch.Generator(device="cpu")
            gen.manual_seed(relation_seed(c))
            for name in ("relation_att","relation_msg"):
                value = dst[name][index]
                draw = torch.rand(tuple(value.shape),dtype=value.dtype,device="cpu",generator=gen)
                value.copy_(draw.mul(2*bound).sub(bound).to(value.device))
            dst["relation_pri"][index].fill_(1)
    new_layer.load_state_dict(dst, strict=True)
    actual = new_layer.state_dict()
    for name,value in src.items():
        if name not in RELATION_PARAMETERS:
            assert torch.equal(value,actual[name]),name
        else:
            for c,origin in key_map.items():
                assert torch.equal(value[anchor_layer.edge_dict[origin]],
                                   actual[name][new_layer.edge_dict[c]]),(name,c)
    return dict(anchor_relations=len(anchor_layer.edge_dict),new_relations=len(new_layer.edge_dict),
                copied_rows=len(key_map),initialized_rows=len(new_layer.edge_dict)-len(key_map),
                xavier_bound=bound,seed_format="sha256(JSON canonical, compact ASCII)[:16]")
