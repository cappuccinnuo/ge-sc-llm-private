"""Input-only DFG v2 adapter; no source analysis or feature modification.

The build_dgl interface follows scripts/DFG/state/stage_f/model_adapter.py
SHA256 90c49bf72d33a87e53e6edcc85f7438bf0792cac43f7517a6bac8b8ab4737086.
This wrapper calls the original graph utilities directly rather than rebinding
or copying their code. G0 parity is tested against the original reflect_graph
and the Stage F build_dgl on the generated baseline fixture.
"""
from numbers import Integral

import dgl
import networkx as nx
import torch

from sco_models import graph_utils as gu
from . import AUX_NODE_TYPES, FORWARD_RELATIONS, PROFILES, REVERSE_OF


def _check_profile(profile):
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError("Unknown DFG v2 profile: {!r}".format(profile))


def edge_data(nx_graph):
    """Preserve the original canonical insertion order and endpoint tensors."""
    return gu.generate_hetero_graph_data(nx_graph)


def _validate_canonical(canonical, endpoints):
    if (not isinstance(canonical, tuple) or len(canonical) != 3 or
            any(not isinstance(name, str) or not name for name in canonical)):
        raise ValueError("Invalid canonical relation: {!r}".format(canonical))
    if not isinstance(endpoints, (tuple, list)) or len(endpoints) != 2:
        raise ValueError("Canonical endpoints must be a source/destination pair")
    for tensor in endpoints:
        if (not isinstance(tensor, torch.Tensor) or tensor.ndim != 1 or
                tensor.dtype not in (torch.int32, torch.int64)):
            raise ValueError("Canonical endpoints must be one-dimensional integer tensors")
        if tensor.numel() and bool((tensor < 0).any()):
            raise ValueError("Canonical endpoints cannot contain negative row IDs")
    if endpoints[0].numel() != endpoints[1].numel():
        raise ValueError("Canonical source/destination lengths differ")


def materialize(data, profile):
    """Reflect base edges unchanged, keep v2 directed, and explicitly add REV_.

    NetworkX inputs for G3 and G3R contain the same forward relations. Explicit
    reverses exist only in this model-input dictionary, never in the source HCG.
    Multiple base canonicals that the original reflector merges retain its exact
    behavior; newly inserted v2 canonicals may never overwrite an existing key.
    """
    _check_profile(profile)
    ordinary = {}
    forward = {}
    for canonical, endpoints in data.items():
        _validate_canonical(canonical, endpoints)
        relation = canonical[1]
        if relation.startswith("REV_"):
            raise ValueError("Input REV_* relations are forbidden: " + relation)
        if relation in FORWARD_RELATIONS:
            if relation not in PROFILES[profile]:
                raise ValueError("Relation {} is not allowed by {}".format(relation, profile))
            forward[canonical] = endpoints
        else:
            ordinary[canonical] = endpoints
    result = gu.reflect_graph(ordinary)
    for canonical, endpoints in forward.items():
        if canonical in result:
            raise ValueError("Canonical collision: {!r}".format(canonical))
        result[canonical] = endpoints
        if profile == "G3R":
            reverse = (canonical[2], REVERSE_OF[canonical[1]], canonical[0])
            if reverse in result:
                raise ValueError("Canonical collision: {!r}".format(reverse))
            result[reverse] = (endpoints[1], endpoints[0])
    return result


def build_dgl(nx_graph, profile, device="cpu"):
    """Return (DGL graph, original-node -> actual type-local row), without edits.

    Callers assign node_hetero_id on a private working copy, as in the frozen
    constructor. This function refuses stale/missing row mappings; it never
    silently renumbers nodes or modifies labels, tokens, or the input graph.
    """
    _check_profile(profile)
    if not isinstance(nx_graph, nx.MultiDiGraph):
        raise TypeError("Expected an HCG directed multigraph")
    if not nx_graph:
        raise ValueError("Cannot materialize an empty HCG")
    ids = {}
    counts = {}
    for node, attrs in nx_graph.nodes(data=True):
        typ = attrs.get("node_type")
        if not isinstance(typ, str) or not typ:
            raise ValueError("Every node must have a nonempty node_type")
        if typ in AUX_NODE_TYPES and profile not in ("G3", "G3R"):
            raise ValueError("Auxiliary nodes are allowed only in G3/G3R")
        row = counts.get(typ, 0)
        assigned = attrs.get("node_hetero_id")
        if (not isinstance(assigned, Integral) or isinstance(assigned, bool) or
                assigned != row):
            raise AssertionError("Node type-local row differs from node_hetero_id: {!r}".format(node))
        ids[node] = row
        counts[typ] = row + 1
    number_of_nodes = gu.get_number_of_nodes(nx_graph)
    if counts != number_of_nodes:
        raise AssertionError("Node count mapping differs from original graph utility")
    data = materialize(edge_data(nx_graph), profile)
    graph = dgl.heterograph(data, num_nodes_dict=number_of_nodes).to(device)
    return graph, ids
