"""EP1 fixed-graph structural adapter. No EdgeAware math or checkpoint bypass.

Derivation reference: scripts/DFG/dfg_v2/benchmark_v2/runtime_model.py
SHA256 b0016a00d2a26e5aca7a7103f9eebc6739aedebe9a67096c601282ab45494c62
Deep registration adapted from scripts/DFG/dfg_v2/model.py
SHA256 3f77f5ae056059a1a7f4414bb137b0d300adf51bdd70d1f57a91f296fddf0644
Only the materializer and profile dispatch differ. Original forward/pooling
and HGTLayerSharedProjection are reused, not copied or rebound.
"""
import copy
from pathlib import Path
import dgl
import networkx as nx
import torch
from torch import nn
from sco_models import graph_utils as gu
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.dfg_v2.model import make_model as make_anchor
from scripts.DFG.dfg_v2.model import validate_registration as original_validate
from scripts.DFG.dfg_v2.model import _features, _pool_rows, _node_labels
from scripts.DFG.dfg_v2.model_input import edge_data
from scripts.DFG.dfg_v2 import AUX_NODE_TYPES
from scripts.DFG.dfg_v2.hgt_layer import HGTLayerSharedProjection
from scripts.DFG.dfg_v2.experiment.init import seeds
from scripts.DFG.experiments.paper_runtime import validate_registration as native_registration
from scripts.DFG.experiments.runtime import assert_disconnected_files
from . import VERSION, NEW_RELATIONS, validate_profile
from .materialize import materialize, parameter_key_map
from .init import copy_typed_layer_parameters


def _derive(anchor, profile, working_graph=None):
    spec = validate_profile(profile)
    if spec["edge_features"]!="none":
        raise NotImplementedError("EdgeAware profiles are registered; EP6 implements their model")
    if spec["placebo"]!="none":
        raise NotImplementedError("Placebo construction is not implemented in EP1")
    if anchor.dfg_profile!="G3R" or anchor.dfg_layer_impl!="shared_projection" or anchor.dfg_reducer!="mean":
        raise ValueError("Expected a fresh G3R shared_projection/mean anchor")
    if any(p.grad is not None for p in anchor.parameters()) or any(
            getattr(anchor,name,0)!=0 for name in ("optimizer_steps","_dfg_optimizer_steps")):
        raise ValueError("Anchor must be untrained")
    original_validate(anchor)
    model = copy.deepcopy(anchor)
    if working_graph is not None:
        model.nx_graph = working_graph
    data, metadata = materialize(edge_data(model.nx_graph), profile)
    graph = dgl.heterograph(data,num_nodes_dict=anchor.number_of_nodes).to(anchor.device)
    for typ in graph.ntypes:
        graph.nodes[typ].data["inp"] = anchor.symmetrical_global_graph.nodes[typ].data["inp"].detach().clone()
    model.etypes_dict = {c:i for i,c in enumerate(graph.canonical_etypes)}
    for c,i in model.etypes_dict.items():
        graph.edges[c].data["id"] = torch.full((graph.num_edges(c),),i,dtype=torch.long,device=anchor.device)
    model.symmetrical_global_graph,model.symmetrical_global_graph_data = graph,data
    model.edge_profile,model.edge_version = profile,VERSION
    # G3R records the frozen anchor lineage only. edge_profile owns the schema.
    # Typed models must never enter the frozen deep/checkpoint validation path.
    model.dfg_profile = "G3R"
    model.edge_rel_meta,model.edge_key_map = metadata,parameter_key_map(metadata)
    layers, receipts = [], []
    for old in anchor.gcs:
        new = HGTLayerSharedProjection(anchor.hidden_size,anchor.hidden_size,model.ntypes_dict,
            model.etypes_dict,anchor.num_heads,dropout=old.drop.p,use_norm=old.use_norm).to(anchor.device)
        receipts.append(copy_typed_layer_parameters(old,new,model.edge_key_map))
        layers.append(new)
    model.gcs,model.edge_initialization = nn.ModuleList(layers),receipts
    model.meta_paths = (gu.get_length_2_metapath(graph) if model.dfg_task=="node"
                        else gu.get_symmatrical_metapaths(graph))
    model.full_metapath = {}
    for path in model.meta_paths:
        model.full_metapath.setdefault(path[0][0],[]).append(path)
    model.train(anchor.training)
    validate_registration(model)
    return model


def make_edge_model(task,graph_or_path,profile="G3R",device="cpu",fold=0,
                    node_feature="inside_token",hidden_size=128,layers=2,heads=8):
    spec = validate_profile(profile)
    if spec["edge_features"]!="none" or spec["placebo"]!="none":
        raise NotImplementedError("Attribute/placebo models are reserved for later prompts")
    seed_info = seeds(task,fold)
    source = graph_or_path if isinstance(graph_or_path,nx.Graph) else read_graph(Path(graph_or_path))
    if not isinstance(source,nx.MultiDiGraph):
        raise TypeError("Expected frozen directed multigraph")
    # E1 edges may be supplied by a future builder, never constructed here.
    # They cannot alter the G3R anchor's graph or initialization.
    base = copy.deepcopy(source)
    remove = [(a,b,k) for a,b,k,d in base.edges(keys=True,data=True) if d.get("edge_type") in NEW_RELATIONS]
    if remove and not spec["new_relations"]:
        raise ValueError("Unexpected E1 relation in baseline")
    base.remove_edges_from(remove)
    if any(d.get("edge_type","").startswith("REV_") for _,_,d in base.edges(data=True)):
        raise ValueError("Stored inputs must be forward-only")
    # CPU construction under a private RNG scope; no trained checkpoint loaded.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed_info["constructor"])
        anchor = make_anchor(task,base,"G3R",device="cpu",node_feature=node_feature,
            hidden_size=hidden_size,layers=layers,heads=heads,reducer="mean",layer_impl="shared_projection")
        working = None
        if remove:
            working = gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(source)))
        model = _derive(anchor,profile,working)
    model.edge_seeds,model.edge_optimizer_steps = seed_info,0
    if str(device)!="cpu":
        model.to(device)
        model.symmetrical_global_graph = model.symmetrical_global_graph.to(device)
        model.supervised_node_mask = model.supervised_node_mask.to(device)
        model.device = str(device)
    validate_registration(model)
    return model


def validate_registration(model,expected_schema=None,deep=True):
    profile = getattr(model,"edge_profile",None)
    if profile is None:
        return original_validate(model,expected_schema,deep)
    spec = validate_profile(profile)
    if spec["edge_features"]!="none" or spec["placebo"]!="none":
        raise ValueError("This EP1 model cannot claim an attribute/placebo profile")
    if model.edge_version!=VERSION or model.dfg_profile!="G3R":
        raise ValueError("EdgeSem/anchor identity mismatch")
    if model.dfg_layer_impl!="shared_projection" or model.dfg_reducer!="mean":
        raise ValueError("EdgeSem structural layer policy mismatch")
    if len(model.gcs)!=model.num_layers or any(type(layer) is not HGTLayerSharedProjection for layer in model.gcs):
        raise ValueError("EdgeSem HGT layer classes/count mismatch")
    if profile=="G3R":
        return original_validate(model,expected_schema,deep)
    schema = native_registration(model,expected_schema,deep=False)
    if not deep:
        return schema
    assert_disconnected_files(model.nx_graph)
    expected_ids = gu.get_node_ids_dict(model.nx_graph)
    if model.node_ids_dict!=expected_ids:
        raise ValueError("Node row dictionary misaligned")
    mask = torch.tensor([d["node_type"] not in AUX_NODE_TYPES for _,d in model.nx_graph.nodes(data=True)],
                        dtype=torch.bool,device=model.device)
    if not torch.equal(model.supervised_node_mask,mask):
        raise ValueError("Supervised auxiliary mask mismatch")
    if hasattr(model,"node_ids_by_filename") and model.node_ids_by_filename!=_pool_rows(model.nx_graph):
        raise ValueError("File pooling row dictionary misaligned")
    if hasattr(model,"node_labels") and model.node_labels!=_node_labels(model.nx_graph)[0]:
        raise ValueError("Node labels mismatch")
    expected,metadata = materialize(edge_data(model.nx_graph),profile)
    graph = model.symmetrical_global_graph
    if set(expected)!=set(model.etypes_dict) or set(expected_ids)!=set(model.ntypes_dict):
        raise ValueError("Graph/schema mismatch")
    if metadata!=model.edge_rel_meta or parameter_key_map(metadata)!=model.edge_key_map:
        raise ValueError("Relation metadata/key map mismatch")
    if set(model.symmetrical_global_graph_data)!=set(expected):
        raise ValueError("Cached graph schema mismatch")
    features = _features(model)
    for typ,rows in expected_ids.items():
        if len(rows)!=graph.num_nodes(typ):
            raise ValueError("Graph node count mismatch")
        value = graph.nodes[typ].data["inp"]
        if value.requires_grad or value.dtype!=features[typ].dtype or not torch.equal(value.cpu(),features[typ].cpu()):
            raise ValueError("Frozen input features mismatch")
    for c,ends in expected.items():
        for observed in (graph.edges(etype=c,order="eid"),model.symmetrical_global_graph_data[c]):
            if not all(torch.equal(x.cpu(),y.cpu()) for x,y in zip(ends,observed)):
                raise ValueError("Graph endpoints mismatch")
    return schema
