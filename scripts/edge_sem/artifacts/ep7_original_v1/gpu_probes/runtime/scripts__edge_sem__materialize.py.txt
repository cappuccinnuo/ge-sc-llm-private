"""Input-only direction adapter; DFG v2 handling is delegated unchanged."""
import torch
from sco_models import graph_utils as gu
from scripts.DFG.dfg_v2 import FORWARD_RELATIONS
from scripts.DFG.dfg_v2.model_input import materialize as dfg_materialize, _validate_canonical
from . import NEW_RELATIONS, REVERSE_PREFIX, RELATION_FAMILY, FAMILIES, validate_profile


def _meta(canonical, reverse, anchor):
    base = canonical[1][len(REVERSE_PREFIX):] if reverse else canonical[1]
    family = RELATION_FAMILY.get(base)
    if family not in FAMILIES:
        raise ValueError("Unregistered relation family: " + base)
    # reverse describes an explicit REV key, not direction inside a merge key.
    return dict(base=base, reverse=reverse, family=family, anchor_key=anchor)


def parameter_key_map(rel_meta):
    """Canonical target -> actual G3R carrier; new E1 relations have no source."""
    return {c:r["anchor_key"] for c,r in rel_meta.items() if r["anchor_key"] is not None}


def materialize(data, profile):
    spec = validate_profile(profile)
    if spec["cf_back"]:
        raise NotImplementedError("cf_back is disabled by the EP0 measurements")
    ordinary, forward, additions = {}, {}, {}
    for c, pair in data.items():
        _validate_canonical(c, pair)
        relation = c[1]
        if relation.startswith(REVERSE_PREFIX):
            raise ValueError("Input REV_* canonical collision/forbidden: " + relation)
        if relation == "cf_back":
            raise ValueError("cf_back is disabled")
        if relation in FORWARD_RELATIONS:
            group = forward
        elif relation in NEW_RELATIONS:
            if relation not in spec["new_relations"]:
                raise ValueError("New relation not allowed by " + profile)
            group = additions
        else:
            group = ordinary
        _meta(c, False, None)
        if c in group:
            if group is additions:
                raise ValueError("New canonical collision: {!r}".format(c))
            group[c] = tuple(torch.cat((x,y)) for x,y in zip(group[c], pair))
        else:
            group[c] = pair
    out, metadata = {}, {}
    if spec["direction_mode"] == "merge":
        out.update(gu.reflect_graph(ordinary))
        metadata.update({c:_meta(c, False, c) for c in out})
    else:
        for c, pair in ordinary.items():
            rev = (c[2], REVERSE_PREFIX+c[1], c[0])
            for key, ends, reverse, origin in (
                    (c,pair,False,c), (rev,(pair[1],pair[0]),True,(c[2],c[1],c[0]))):
                if key in out:
                    out[key] = tuple(torch.cat((x,y)) for x,y in zip(out[key],ends))
                else:
                    out[key] = ends
                    metadata[key] = _meta(key, reverse, origin)
    # Preserve the frozen base-first, DFG-forward insertion order exactly in merge.
    for c, pair in dfg_materialize(forward, "G3R").items():
        if c in out:
            raise ValueError("DFG canonical collision: {!r}".format(c))
        out[c] = pair
        metadata[c] = _meta(c, c[1].startswith(REVERSE_PREFIX), c)
    for c, pair in additions.items():
        rev = (c[2], REVERSE_PREFIX+c[1], c[0])
        if c in out or rev in out:
            raise ValueError("New canonical collision: {!r}".format(c))
        out[c], out[rev] = pair, (pair[1],pair[0])
        metadata[c], metadata[rev] = _meta(c,False,None), _meta(rev,True,None)
    return out, metadata
