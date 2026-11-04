"""Prompt 8H placebo adapter; original classifiers and HGT math unchanged."""
import copy
import dgl
import torch
from torch import nn
from sco_models import graph_utils as gu
from ..model import make_model, validate_registration as original_validate
from ..model import _layer_type, _features, _pool_rows, _node_labels
from ..model_input import edge_data, materialize
from .. import AUX_NODE_TYPES
from scripts.DFG.experiments.paper_runtime import validate_registration as native_registration
from scripts.DFG.experiments.runtime import assert_disconnected_files
from ..diagnostics8c.placebo import make_placebo_data, copy_common_layer_parameters

def make_placebo(anchor, target_counts):
    if anchor.dfg_profile != "G0" or anchor.dfg_task != "node":
        raise ValueError("G0P requires a fresh node G0")
    if any(p.grad is not None for p in anchor.parameters()):
        raise ValueError("G0P anchor is not fresh")
    original_validate(anchor)
    model=copy.deepcopy(anchor)
    data=make_placebo_data(anchor.symmetrical_global_graph_data,target_counts,anchor.ntypes_dict)
    graph=dgl.heterograph(data,num_nodes_dict={t:anchor.symmetrical_global_graph.num_nodes(t) for t in anchor.ntypes_dict}).to(anchor.device)
    for t in graph.ntypes:graph.nodes[t].data["inp"]=anchor.symmetrical_global_graph.nodes[t].data["inp"].detach().clone()
    model.etypes_dict={c:i for i,c in enumerate(graph.canonical_etypes)}
    for c,i in model.etypes_dict.items():graph.edges[c].data["id"]=torch.full((graph.num_edges(c),),i,dtype=torch.long,device=anchor.device)
    model.symmetrical_global_graph=graph
    model.symmetrical_global_graph_data=data
    model.dfg_profile="G0P"
    model.placebo_target_counts=copy.deepcopy(target_counts)
    layers=[]
    for old in anchor.gcs:
        new=type(old)(anchor.hidden_size,anchor.hidden_size,model.ntypes_dict,model.etypes_dict,anchor.num_heads,use_norm=True).to(anchor.device)
        copy_common_layer_parameters(old,new)
        layers.append(new)
    model.gcs=nn.ModuleList(layers)
    model.meta_paths=gu.get_length_2_metapath(graph)
    model.full_metapath={}
    for p in model.meta_paths:model.full_metapath.setdefault(p[0][0],[]).append(p)
    validate_registration(model)
    return model

# Registration body adapted from model.py SHA256 3f77f5ae056059a1a7f4414bb137b0d300adf51bdd70d1f57a91f296fddf0644
def validate_registration(model, expected_schema=None, deep=True):
    """Reuse frozen schema checks; validate v2 direction and auxiliary masks."""
    if model.dfg_profile != "G0P":
        return original_validate(model,expected_schema,deep)
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
    expected = make_placebo_data(materialize(edge_data(model.nx_graph), "G0"), model.placebo_target_counts, model.ntypes_dict)
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
