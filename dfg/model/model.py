"""DFG-aware HGT classifiers: DGL graph construction per profile and model factory."""
import copy
from numbers import Integral
from pathlib import Path

import dgl
import networkx as nx
import torch
from sco_models import graph_utils as gu
from sco_models.model_hgt import HGTLayer, HGTVulGraphClassifier, HGTVulNodeClassifier
from scripts.labeling_v2.safe_graph import read_graph
from torch import nn

from dfg.model.hgt import (
    HGTLayerNonEmptyMean,
    HGTLayerSharedProjection,
    HGTLayerSharedProjectionNonEmptyMean)
from dfg.model.registration import (
    assert_disconnected_files,
    validate_registration as native_registration)
from dfg.schema import (
    AUX_NODE_TYPES,
    ENV_FLOW,
    FORWARD_RELATIONS,
    REVERSE_OF,
    forward_relations,
    has_reverse)


# ----------------------------------------------------------------------
# dfg_v2/model_input
# Input-only DFG v2 adapter; no source analysis or feature modification.
#
# The build_dgl interface follows scripts/DFG/state/stage_f/model_adapter.py
# SHA256 90c49bf72d33a87e53e6edcc85f7438bf0792cac43f7517a6bac8b8ab4737086.
# This wrapper calls the original graph utilities directly rather than rebinding
# or copying their code. G0 parity is tested against the original reflect_graph
# and the Stage F build_dgl on the generated baseline fixture.
def _check_profile(profile):
    forward_relations(profile)

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
    allowed_forward = forward_relations(profile)
    ordinary = {}
    forward = {}
    for canonical, endpoints in data.items():
        _validate_canonical(canonical, endpoints)
        relation = canonical[1]
        if relation.startswith("REV_"):
            raise ValueError("Input REV_* relations are forbidden: " + relation)
        if relation in FORWARD_RELATIONS:
            if relation not in allowed_forward:
                raise ValueError("Relation {} is not allowed by {}".format(relation, profile))
            forward[canonical] = endpoints
        else:
            ordinary[canonical] = endpoints
    result = gu.reflect_graph(ordinary)
    for canonical, endpoints in forward.items():
        if canonical in result:
            raise ValueError("Canonical collision: {!r}".format(canonical))
        result[canonical] = endpoints
        if has_reverse(profile, canonical[1]):
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
        if typ in AUX_NODE_TYPES and ENV_FLOW not in forward_relations(profile):
            raise ValueError("Auxiliary nodes require a profile allowing ENV_FLOW")
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


# ----------------------------------------------------------------------
# dfg_v2/model
# DFG v2 input adapter around the unchanged production classifier forward.
#
# Constructor source: scripts/DFG/experiments/e23_pilot/model.py::_construct
# SHA256: 00472900d131fe9cfc20db09ff20d910edde7ebdc82b59b100bdb2282610f141
# Registration source: scripts/DFG/experiments/paper_runtime.py
# SHA256: 319159bec961320307083f63dea2f4fb5eed3559db401c542bcd0af6eca6218e
# The copied constructor keeps allocation/RNG order. Differences are the v2
# materializer, explicit profile/reducer, nodetype features and auxiliary masks.
# Original forward and graph mean pooling are inherited, not copied or rebound.
# Only fixed-graph forward is covered here; new-graph inference is Prompt 9.
LAYER_IMPLEMENTATIONS = ("original", "shared_projection")

def _layer_type(layer_impl, reducer):
    if layer_impl not in LAYER_IMPLEMENTATIONS:
        raise ValueError("Unsupported layer_impl")
    if reducer not in ("mean", "nonempty_mean"):
        raise ValueError("Unsupported relation reducer")
    return {
        ("original", "mean"): HGTLayer,
        ("original", "nonempty_mean"): HGTLayerNonEmptyMean,
        ("shared_projection", "mean"): HGTLayerSharedProjection,
        ("shared_projection", "nonempty_mean"): HGTLayerSharedProjectionNonEmptyMean,
    }[(layer_impl, reducer)]

def _original_nodes(graph):
    return [n for n, attrs in graph.nodes(data=True)
            if attrs["node_type"] not in AUX_NODE_TYPES]

def _node_labels(graph):
    """Apply the original label rule only to supervised HCG nodes.

    -1 is an internal ignored-row sentinel, not an auxiliary clean label.
    The input graph and its label attributes are never rewritten.
    """
    original = _original_nodes(graph)
    selected = graph.subgraph(original)
    labels, labeled_ids, label_ids = gu.get_node_label(selected)
    by_node = dict(zip(selected.nodes(), labels))
    return [by_node.get(n, -1) for n in graph], labeled_ids, label_ids

def _pool_rows(graph):
    selected = graph.subgraph(_original_nodes(graph))
    rows = gu.get_node_ids_by_filename(selected)
    files = {d["source_file"] for _, d in graph.nodes(data=True)}
    if set(rows) != files:
        raise ValueError("Every file needs original HCG nodes for supervision/pooling")
    return rows

def _features(model):
    if model.node_feature == "inside_token":
        return gu.get_node_token(model.nx_graph)
    return {typ: model._nodetype2onehot(typ).repeat(
        model.symmetrical_global_graph.num_nodes(typ), 1)
        for typ in model.node_types}

def _construct(model, task, graph_or_path, profile, device, node_feature,
               hidden_size, layers, heads, reducer, layer_impl):
    nn.Module.__init__(model)
    if task not in ("node", "contract"):
        raise ValueError("Unknown task")
    if node_feature not in ("inside_token", "nodetype"):
        raise ValueError("Unsupported node feature")
    layer_type = _layer_type(layer_impl, reducer)
    model.compressed_global_graph_path = (str(graph_or_path) if not isinstance(graph_or_path, nx.Graph)
                                         else "<in-memory-frozen-graph>")
    source = graph_or_path if isinstance(graph_or_path, nx.Graph) else read_graph(Path(graph_or_path))
    if not isinstance(source, nx.MultiDiGraph):
        raise TypeError("Expected the frozen directed multigraph")
    assert_disconnected_files(source)
    model.original_graph_node_ids = list(source)
    model.nx_graph = gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(source)))
    model.hidden_size, model.num_heads, model.device = hidden_size, heads, str(device)
    model.dfg_profile, model.dfg_reducer, model.dfg_task = profile, reducer, task
    model.dfg_layer_impl = layer_impl
    model.total_nodes = len(model.nx_graph)
    model.node_ids_dict = gu.get_node_ids_dict(model.nx_graph)
    model.supervised_node_mask = torch.tensor(
        [d["node_type"] not in AUX_NODE_TYPES for _, d in model.nx_graph.nodes(data=True)],
        dtype=torch.bool, device=device)
    pool_rows = _pool_rows(model.nx_graph)
    if task == "node":
        model.node_labels, model.labeled_node_ids, model.label_ids = _node_labels(model.nx_graph)
    else:
        model.node_ids_by_filename = pool_rows
    model.number_of_nodes = gu.get_number_of_nodes(model.nx_graph)
    model.symmetrical_global_graph_data = materialize(edge_data(model.nx_graph), profile)
    model.symmetrical_global_graph, actual_local_ids = build_dgl(model.nx_graph, profile, device)
    for node, attrs in model.nx_graph.nodes(data=True):
        if actual_local_ids[node] != attrs["node_hetero_id"]:
            raise AssertionError("Adapter changed node type-local row")
    model.meta_paths = (gu.get_length_2_metapath(model.symmetrical_global_graph) if task == "node"
                        else gu.get_symmatrical_metapaths(model.symmetrical_global_graph))
    model.full_metapath = {}
    for path in model.meta_paths:
        model.full_metapath.setdefault(path[0][0], []).append(path)
    model.node_types = list(model.symmetrical_global_graph.ntypes)
    model.ntypes_dict = {name: idx for idx, name in enumerate(model.node_types)}
    model.etypes_dict = {c: idx for idx, c in enumerate(model.symmetrical_global_graph.canonical_etypes)}
    for c, idx in model.etypes_dict.items():
        model.symmetrical_global_graph.edges[c].data["id"] = torch.full(
            (model.symmetrical_global_graph.num_edges(c),), idx, dtype=torch.long, device=device)
    model.node_feature = node_feature
    features = _features(model)
    model.in_size = list(features.values())[0].shape[-1]
    for typ in model.node_types:
        if features[typ].ndim != 2 or features[typ].shape[1] != model.in_size:
            raise ValueError("Inconsistent frozen input features")
        if not features[typ].is_floating_point() or not bool(torch.isfinite(features[typ]).all()):
            raise ValueError("Frozen input features must be finite floating-point tensors")
        emb = nn.Parameter(features[typ], requires_grad=False)
        model.symmetrical_global_graph.nodes[typ].data["inp"] = emb.to(device)
    # Preserve original allocation order and RNG draws, including diagnostic mode.
    model.gcs = nn.ModuleList()
    model.out_size, model.num_layers = 2, layers
    model.adapt_ws = nn.ModuleList([nn.Linear(model.in_size, hidden_size) for _ in model.ntypes_dict])
    for _ in range(layers):
        model.gcs.append(layer_type(hidden_size, hidden_size, model.ntypes_dict,
                                   model.etypes_dict, heads, use_norm=True))
    model.classify = nn.Linear(hidden_size, model.out_size)

class DfgV2NodeClassifier(HGTVulNodeClassifier):
    def __init__(self, graph_or_path, profile, device="cpu", node_feature="inside_token",
                 hidden_size=128, layers=2, heads=8, reducer="mean", layer_impl="original"):
        _construct(self, "node", graph_or_path, profile, device, node_feature,
                   hidden_size, layers, heads, reducer, layer_impl)

class DfgV2GraphClassifier(HGTVulGraphClassifier):
    def __init__(self, graph_or_path, profile, device="cpu", node_feature="inside_token",
                 hidden_size=128, layers=2, heads=8, reducer="mean", layer_impl="original"):
        _construct(self, "contract", graph_or_path, profile, device, node_feature,
                   hidden_size, layers, heads, reducer, layer_impl)

def make_model(task, graph_or_path, profile, device="cpu", node_feature="inside_token",
               hidden_size=128, layers=2, heads=8, reducer="mean", layer_impl="original"):
    if task not in ("node", "contract"):
        raise ValueError("Unknown task")
    cls = DfgV2NodeClassifier if task == "node" else DfgV2GraphClassifier
    model = cls(graph_or_path, profile, device, node_feature, hidden_size,
                layers, heads, reducer, layer_impl).to(device)
    validate_registration(model)
    return model

def validate_registration(model, expected_schema=None, deep=True):
    """Reuse frozen schema checks; validate v2 direction and auxiliary masks."""
    expected_layer = _layer_type(model.dfg_layer_impl, model.dfg_reducer)
    if any(type(layer) is not expected_layer for layer in model.gcs):
        raise ValueError("Model layer_impl does not match actual HGT layer classes")
    schema = native_registration(model, expected_schema, deep=False)
    if not deep:
        return schema
    assert_disconnected_files(model.nx_graph)
    expected_ids = gu.get_node_ids_dict(model.nx_graph)
    if model.node_ids_dict != expected_ids:
        raise ValueError("Node row dictionary misaligned")
    expected_mask = torch.tensor(
        [d["node_type"] not in AUX_NODE_TYPES for _, d in model.nx_graph.nodes(data=True)],
        dtype=torch.bool, device=model.device)
    if not torch.equal(model.supervised_node_mask, expected_mask):
        raise ValueError("Supervised auxiliary mask mismatch")
    if hasattr(model, "node_ids_by_filename") and model.node_ids_by_filename != _pool_rows(model.nx_graph):
        raise ValueError("File pooling row dictionary misaligned")
    if hasattr(model, "node_labels") and model.node_labels != _node_labels(model.nx_graph)[0]:
        raise ValueError("Node labels mismatch")
    expected = materialize(edge_data(model.nx_graph), model.dfg_profile)
    graph = model.symmetrical_global_graph
    if set(expected) != set(model.etypes_dict) or set(expected_ids) != set(model.ntypes_dict):
        raise ValueError("Graph/schema mismatch")
    features = _features(model)
    for typ, rows in expected_ids.items():
        if len(rows) != graph.num_nodes(typ):
            raise ValueError("Graph node count mismatch")
        actual = graph.nodes[typ].data["inp"]
        if actual.requires_grad or actual.dtype != features[typ].dtype or not torch.equal(actual.cpu(), features[typ].cpu()):
            raise ValueError("Frozen input features mismatch")
    for c, endpoints in expected.items():
        if not all(torch.equal(x.cpu(), y.cpu()) for x, y in zip(endpoints, graph.edges(etype=c, order="eid"))):
            raise ValueError("Graph endpoints mismatch")
    return schema
