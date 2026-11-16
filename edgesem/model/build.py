"""Build and validate EdgeSem models.

Every profile starts from a fresh G3R anchor constructed under the fold's constructor seed
(on CPU, inside a private RNG scope). Structural profiles re-materialize the anchor's graph
with typed directions and/or the E1 relations and copy its parameters relation by relation
(``edgesem.model.init``); attribute profiles additionally swap in the edge-aware HGT layer
and a shared edge encoder whose new parameters start at zero; the placebos rewire E1 edges
or permute attribute rows with the same constructor seed.

Inputs are in memory: the F3 graph (with node tokens), the task's F4 edge records and the
attribute matrix keyed by ``edgesem.attributes.layout.edge_rows`` keys.
"""
import copy
import hashlib
import json

import dgl
import networkx as nx
import numpy as np
import torch
from torch import nn

from dfg.graph.audit import fingerprint as graph_fingerprint
from dfg.model.hgt import HGTLayerSharedProjection
from dfg.model.model import _features, _node_labels, _pool_rows, edge_data
from dfg.model.model import make_model as make_anchor
from dfg.model.model import validate_registration as original_validate
from dfg.model.registration import assert_disconnected_files
from dfg.model.registration import validate_registration as native_registration
from dfg.schema import AUX_NODE_TYPES
from dfg.train.init import seeds
from dfg.utils import digest
from edgesem.attributes.layout import edge_rows
from edgesem.graph.f4 import add_edges
from edgesem.model.init import copy_typed_layer_parameters
from edgesem.model.layers import EdgeAttrEncoder, EdgeAwareHGTLayer, EdgeGraphClassifier, EdgeNodeClassifier
from edgesem.model.placebo import add_placebo_edges, permute_attributes, randomize_edges
from edgesem.model.relations import materialize, parameter_key_map
from edgesem.schema import CONTEXT_INDICES, CORE_INDICES, NEW_RELATIONS, VERSION, validate_profile
from sco_models import graph_utils as gu


def feature_indices(profile):
    """Attribute columns a profile reads: core, or core plus context."""
    mode = validate_profile(profile)["edge_features"]
    if mode == "none":
        return ()
    return tuple(CORE_INDICES if mode == "core" else sorted(set(CORE_INDICES) | set(CONTEXT_INDICES)))


def _derive(anchor, profile, working_graph=None):
    spec = validate_profile(profile)
    if spec["edge_features"] != "none" or spec["placebo"] != "none":
        raise ValueError("Only structural profiles derive directly from the anchor")
    if anchor.dfg_profile != "G3R" or anchor.dfg_layer_impl != "shared_projection" or anchor.dfg_reducer != "mean":
        raise ValueError("Expected a fresh G3R shared_projection/mean anchor")
    if any(p.grad is not None for p in anchor.parameters()):
        raise ValueError("Anchor must be untrained")
    original_validate(anchor)
    model = copy.deepcopy(anchor)
    if working_graph is not None:
        model.nx_graph = working_graph
    data, metadata = materialize(edge_data(model.nx_graph), profile)
    graph = dgl.heterograph(data, num_nodes_dict=anchor.number_of_nodes).to(anchor.device)
    for typ in graph.ntypes:
        graph.nodes[typ].data["inp"] = anchor.symmetrical_global_graph.nodes[typ].data["inp"].detach().clone()
    model.etypes_dict = {c: i for i, c in enumerate(graph.canonical_etypes)}
    for c, i in model.etypes_dict.items():
        graph.edges[c].data["id"] = torch.full((graph.num_edges(c),), i, dtype=torch.long, device=anchor.device)
    model.symmetrical_global_graph, model.symmetrical_global_graph_data = graph, data
    model.edge_profile, model.edge_version = profile, VERSION
    # dfg_profile records the anchor lineage; edge_profile owns the schema.
    model.dfg_profile = "G3R"
    model.edge_rel_meta, model.edge_key_map = metadata, parameter_key_map(metadata)
    layers, receipts = [], []
    for old in anchor.gcs:
        new = HGTLayerSharedProjection(anchor.hidden_size, anchor.hidden_size, model.ntypes_dict,
                                       model.etypes_dict, anchor.num_heads, dropout=old.drop.p,
                                       use_norm=old.use_norm).to(anchor.device)
        receipts.append(copy_typed_layer_parameters(old, new, model.edge_key_map))
        layers.append(new)
    model.gcs, model.edge_initialization = nn.ModuleList(layers), receipts
    model.meta_paths = (gu.get_length_2_metapath(graph) if model.dfg_task == "node"
                        else gu.get_symmatrical_metapaths(graph))
    model.full_metapath = {}
    for path in model.meta_paths:
        model.full_metapath.setdefault(path[0][0], []).append(path)
    model.train(anchor.training)
    validate_registration(model)
    return model


def _to_device(model, device):
    if str(device) != "cpu":
        model.to(device)
        model.symmetrical_global_graph = model.symmetrical_global_graph.to(device)
        model.supervised_node_mask = model.supervised_node_mask.to(device)
        model.device = str(device)
    return model


def _structural(task, source, profile, fold, node_feature, hidden_size, layers, heads, seed=1):
    """Fresh G3R anchor on the graph without E1 edges, re-materialized as ``profile``."""
    spec = validate_profile(profile)
    seed_info = seeds(task, fold, seed)
    base = copy.deepcopy(source)
    remove = [(a, b, k) for a, b, k, d in base.edges(keys=True, data=True) if d.get("edge_type") in NEW_RELATIONS]
    if remove and not spec["new_relations"]:
        raise ValueError("E1 relations supplied to a profile without them")
    base.remove_edges_from(remove)
    if any(d.get("edge_type", "").startswith("REV_") for _, _, d in base.edges(data=True)):
        raise ValueError("Stored inputs must be forward-only")
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed_info["constructor"])
        anchor = make_anchor(task, base, "G3R", device="cpu", node_feature=node_feature, hidden_size=hidden_size,
                             layers=layers, heads=heads, reducer="mean", layer_impl="shared_projection")
        working = None
        if remove:
            working = gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(source)))
        model = _derive(anchor, profile, working)
    model.edge_seeds = seed_info
    return model


def row_binding_digest(keys):
    rows = [dict(canonical=list(c), keys=list(keys[c])) for c in sorted(keys)]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def typed_attributes(original, model_graph, rows, values):
    """Join original multiedges to type-local edge ids, then copy explicit reverses."""
    mapping = {n: i for i, n in enumerate(original.nodes())}
    if list(model_graph) != list(range(len(mapping))):
        raise ValueError("Original/model node mapping differs")
    lookup = {}
    for row in rows:
        token = (row["src"], row["dst"], row["relation"], row.get("nx_key") if row["origin"] == "F3" else None)
        if token in lookup:
            raise ValueError("Duplicate original edge identity")
        lookup[token] = row["key"]
    forward, endpoints = {}, {}
    for src, dst, key, data in original.edges(keys=True, data=True):
        rel = data["edge_type"]
        token = (src, dst, rel, None if rel in NEW_RELATIONS else key)
        if token not in lookup:
            raise ValueError("Unbound forward edge identity")
        a, b = model_graph.nodes[mapping[src]], model_graph.nodes[mapping[dst]]
        c = (a["node_type"], rel, b["node_type"])
        forward.setdefault(c, []).append(lookup[token])
        endpoints.setdefault(c, []).append((a["node_hetero_id"], b["node_hetero_id"]))
    keys, matrices, pairs = {}, {}, {}
    for c, ids in forward.items():
        rev = (c[2], "REV_" + c[1], c[0])
        if c in keys or rev in keys:
            raise ValueError("Forward/reverse collision")
        v = torch.from_numpy(np.stack([values[k] for k in ids]).copy())
        ab = torch.tensor(endpoints[c], dtype=torch.long).t()
        keys[c], keys[rev] = tuple(ids), tuple(ids)
        matrices[c], matrices[rev] = v, v.clone()
        pairs[c], pairs[rev] = (ab[0], ab[1]), (ab[1], ab[0])
    return matrices, keys, pairs


def _attribute_model(task, source, profile, fold, edges, attrs, node_feature, hidden_size, layers, heads, seed=1):
    spec = validate_profile(profile)
    base = copy.deepcopy(source)
    if any(d.get("edge_type") in NEW_RELATIONS for _, _, d in base.edges(data=True)):
        raise ValueError("Attribute profiles take the F3 graph and add F4 edges themselves")
    rows = edge_rows(base, edges)
    if set(attrs) != {r["key"] for r in rows}:
        raise ValueError("Attribute rows differ from the F3/F4 edge rows")
    enriched = add_edges(base, edges) if spec["new_relations"] else base
    seed_value, seed = seed, seeds(task, fold, seed)
    values, permutation = attrs, None
    if spec["placebo"] == "attributes":
        values, permutation = permute_attributes(rows, attrs, seed["constructor"])
    indices = feature_indices(profile)
    structural = "G4R" if spec["new_relations"] else "G3R-T"
    fresh = _structural(task, enriched, structural, fold, node_feature, hidden_size, layers, heads, seed_value)
    model = (EdgeNodeClassifier if task == "node" else EdgeGraphClassifier)(fresh)
    matrices, keys, pairs = typed_attributes(enriched, model.nx_graph, rows, values)
    g = model.symmetrical_global_graph
    if set(matrices) != set(g.canonical_etypes):
        raise ValueError("Attribute schema differs")
    for c, mat in matrices.items():
        if not all(torch.equal(x, y) for x, y in zip(pairs[c], g.edges(etype=c, order="eid"))):
            raise ValueError("Attribute/endpoints alignment differs")
        g.edges[c].data["ea"] = mat
    # The structural model already holds every shared/typed/new relation parameter;
    # each layer is rebuilt as edge-aware and receives them, so only u/U are new (zero).
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed["constructor"])
        upgraded = []
        for old in model.gcs:
            layer = EdgeAwareHGTLayer(hidden_size, hidden_size, model.ntypes_dict, model.etypes_dict,
                                      heads, dropout=old.drop.p, use_norm=old.use_norm)
            result = layer.load_state_dict(old.state_dict(), strict=False)
            if set(result.missing_keys) != {"u"} | {"U." + f for f in layer.U} or result.unexpected_keys:
                raise ValueError("Parent parameter copy mismatch")
            if any(not torch.equal(v, layer.state_dict()[k]) for k, v in old.state_dict().items()):
                raise AssertionError("Shared parameter copy differs")
            upgraded.append(layer)
        model.gcs = nn.ModuleList(upgraded)
        model.edge_encoder = EdgeAttrEncoder(len(indices))
    model.edge_profile, model.edge_indices, model.edge_attribute_keys = profile, indices, keys
    model.edge_attribute_values = attrs
    model.edge_attribute_binding = dict(key_digest=row_binding_digest(keys), constructor_seed=seed["constructor"],
                                        permutation=permutation,
                                        row_relations=[dict(key=r["key"], relation=r["relation"]) for r in rows])
    model.train(fresh.training)
    return model


def _relation_placebo(task, source, fold, edges, node_feature, hidden_size, layers, heads, seed=1):
    base = copy.deepcopy(source)
    if any(d.get("edge_type") in NEW_RELATIONS for _, _, d in base.edges(data=True)):
        raise ValueError("The relation placebo takes the F3 graph")
    seed_info = seeds(task, fold, seed)
    rows, audit = randomize_edges(base, edges, seed=seed_info["constructor"])
    model = _structural(task, add_placebo_edges(base, rows, edges), "G4R", fold, node_feature, hidden_size,
                        layers, heads, seed)
    model.edge_profile, model.edge_placebo_source, model.edge_placebo_fold = "G4R-P", base, fold
    model.edge_placebo_rows, model.edge_seed = edges, seed
    model.edge_placebo_binding = dict(source_fingerprint=graph_fingerprint(base), real_rows_sha256=digest(edges),
                                      rows_sha256=digest(rows), audit=audit)
    return model


def make_edge_model(task, graph, profile, fold, edges=None, attrs=None, device="cpu", seed=1,
                    node_feature="inside_token", hidden_size=128, layers=2, heads=8):
    """Untrained EdgeSem model of ``profile`` on the F3 ``graph`` (never mutated)."""
    spec = validate_profile(profile)
    if not isinstance(graph, nx.MultiDiGraph):
        raise TypeError("Expected the F3 directed multigraph")
    before = graph_fingerprint(graph)
    needs_edges = bool(spec["new_relations"]) or spec["edge_features"] != "none"
    if needs_edges and edges is None:
        raise ValueError("%s needs the task's F4 edges" % profile)
    if (attrs is None) != (spec["edge_features"] == "none"):
        raise ValueError("%s takes attributes exactly when it reads edge features" % profile)
    args = (node_feature, hidden_size, layers, heads, seed)
    if spec["placebo"] == "relations":
        model = _relation_placebo(task, graph, fold, edges, *args)
    elif spec["edge_features"] != "none":
        model = _attribute_model(task, graph, profile, fold, edges, attrs, *args)
    else:
        source = add_edges(graph, edges) if spec["new_relations"] else graph
        model = _structural(task, source, profile, fold, *args)
    if graph_fingerprint(graph) != before:
        raise AssertionError("F3 graph mutated")
    _to_device(model, device)
    validate_registration(model)
    return model


def validate_attributes(model, deep=True):
    if type(model) not in (EdgeNodeClassifier, EdgeGraphClassifier):
        raise ValueError("Attribute profile requires the edge forward adapter")
    if not isinstance(model.edge_encoder, EdgeAttrEncoder):
        raise ValueError("Missing shared edge encoder")
    binding, indices = model.edge_attribute_binding, feature_indices(model.edge_profile)
    if indices != model.edge_indices or model.edge_encoder.in_dim != len(indices):
        raise ValueError("Edge feature selection differs")
    if row_binding_digest(model.edge_attribute_keys) != binding["key_digest"]:
        raise ValueError("Edge row identity differs")
    graph = model.symmetrical_global_graph
    if set(model.edge_attribute_keys) != set(graph.canonical_etypes):
        raise ValueError("Attribute relation schema differs")
    for c in graph.canonical_etypes:
        ea = graph.edges[c].data.get("ea")
        if ea is None or ea.dtype != torch.uint8 or ea.shape != (graph.num_edges(c), 74) or ea.requires_grad:
            raise ValueError("Invalid frozen edge attributes")
    if not deep:
        return
    values = model.edge_attribute_values
    if validate_profile(model.edge_profile)["placebo"] == "attributes":
        values, audit = permute_attributes(binding["row_relations"], values, model.edge_seeds["constructor"])
        if audit != binding["permutation"]:
            raise ValueError("Attribute permutation binding differs")
    elif binding["permutation"] is not None:
        raise ValueError("Unexpected attribute permutation")
    if binding["constructor_seed"] != model.edge_seeds["constructor"]:
        raise ValueError("Attribute seed differs")
    for c, ids in model.edge_attribute_keys.items():
        expected = torch.from_numpy(np.stack([values[k] for k in ids]))
        if not torch.equal(expected, graph.edges[c].data["ea"].cpu()):
            raise ValueError("Edge attributes differ from their rows")


def validate_relation_placebo(model, deep=True):
    binding = model.edge_placebo_binding
    expected_seed = seeds(model.dfg_task, model.edge_placebo_fold, model.edge_seed)
    if model.edge_seeds != expected_seed or binding["audit"]["seed"] != expected_seed["constructor"]:
        raise ValueError("Placebo seed/fold differs")
    if not deep:
        return
    source, real = model.edge_placebo_source, model.edge_placebo_rows
    if any(d.get("edge_type") in NEW_RELATIONS for _, _, d in source.edges(data=True)):
        raise ValueError("Placebo base contains E1")
    if graph_fingerprint(source) != binding["source_fingerprint"] or digest(real) != binding["real_rows_sha256"]:
        raise ValueError("Placebo source or real rows differ")
    rows, audit = randomize_edges(source, real, seed=expected_seed["constructor"])
    if audit != binding["audit"] or digest(rows) != binding["rows_sha256"]:
        raise ValueError("Placebo recomputation/audit differs")
    expected = gu.add_hetero_ids(nx.convert_node_labels_to_integers(add_placebo_edges(source, rows, real)))
    if graph_fingerprint(expected) != graph_fingerprint(model.nx_graph):
        raise ValueError("Placebo model graph differs from recomputed edges")


def validate_registration(model, expected_schema=None, deep=True):
    """Schema, layer, attribute and placebo consistency of an EdgeSem model."""
    profile = getattr(model, "edge_profile", None)
    if profile is None:
        return original_validate(model, expected_schema, deep)
    spec = validate_profile(profile)
    if spec["placebo"] == "relations":
        validate_relation_placebo(model, deep=deep)
    if spec["edge_features"] != "none":
        expected_layer = EdgeAwareHGTLayer
        validate_attributes(model, deep=deep)
    else:
        expected_layer = HGTLayerSharedProjection
    if model.edge_version != VERSION or model.dfg_profile != "G3R":
        raise ValueError("EdgeSem/anchor identity mismatch")
    if model.dfg_layer_impl != "shared_projection" or model.dfg_reducer != "mean":
        raise ValueError("EdgeSem structural layer policy mismatch")
    if len(model.gcs) != model.num_layers or any(type(layer) is not expected_layer for layer in model.gcs):
        raise ValueError("EdgeSem HGT layer classes/count mismatch")
    if profile == "G3R":
        return original_validate(model, expected_schema, deep)
    schema = native_registration(model, expected_schema, deep=False)
    if not deep:
        return schema
    assert_disconnected_files(model.nx_graph)
    expected_ids = gu.get_node_ids_dict(model.nx_graph)
    if model.node_ids_dict != expected_ids:
        raise ValueError("Node row dictionary misaligned")
    mask = torch.tensor([d["node_type"] not in AUX_NODE_TYPES for _, d in model.nx_graph.nodes(data=True)],
                        dtype=torch.bool, device=model.device)
    if not torch.equal(model.supervised_node_mask, mask):
        raise ValueError("Supervised auxiliary mask mismatch")
    if hasattr(model, "node_ids_by_filename") and model.node_ids_by_filename != _pool_rows(model.nx_graph):
        raise ValueError("File pooling row dictionary misaligned")
    if hasattr(model, "node_labels") and model.node_labels != _node_labels(model.nx_graph)[0]:
        raise ValueError("Node labels mismatch")
    expected, metadata = materialize(edge_data(model.nx_graph), profile)
    graph = model.symmetrical_global_graph
    if set(expected) != set(model.etypes_dict) or set(expected_ids) != set(model.ntypes_dict):
        raise ValueError("Graph/schema mismatch")
    if metadata != model.edge_rel_meta or parameter_key_map(metadata) != model.edge_key_map:
        raise ValueError("Relation metadata/key map mismatch")
    if set(model.symmetrical_global_graph_data) != set(expected):
        raise ValueError("Cached graph schema mismatch")
    features = _features(model)
    for typ, rows in expected_ids.items():
        if len(rows) != graph.num_nodes(typ):
            raise ValueError("Graph node count mismatch")
        value = graph.nodes[typ].data["inp"]
        if value.requires_grad or value.dtype != features[typ].dtype or not torch.equal(value.cpu(), features[typ].cpu()):
            raise ValueError("Frozen input features mismatch")
    for c, ends in expected.items():
        for observed in (graph.edges(etype=c, order="eid"), model.symmetrical_global_graph_data[c]):
            if not all(torch.equal(x.cpu(), y.cpu()) for x, y in zip(ends, observed)):
                raise ValueError("Graph endpoints mismatch")
    return schema
