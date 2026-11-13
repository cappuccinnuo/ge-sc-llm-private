"""Manifest-bound uint8 edge rows and EP6 model assembly; no fact recomputation."""
import copy
import hashlib
import json
from pathlib import Path
import networkx as nx
import numpy as np
import torch
from torch import nn
from sco_models import graph_utils as gu
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.experiment.init import seeds
from scripts.labeling_v2.safe_graph import read_graph
from . import NEW_RELATIONS, validate_profile
from .attrs import edge_rows
from .attr_batch import load_attributes
from .build_f4 import load_edges,add_edges
from .io import ref,read,checked
from .hgt_edge import EdgeAttrEncoder,EdgeAwareHGTLayer
from .forward import EdgeNodeClassifier,EdgeGraphClassifier
from .placebo import permute_attributes


def row_binding_digest(keys):
    rows=[dict(canonical=list(c),keys=list(keys[c])) for c in sorted(keys)]
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def typed_attributes(original, model_graph, rows, values):
    """Join original multiedges to type-local EIDs, then copy explicit reverses."""
    mapping={n:i for i,n in enumerate(original.nodes())}
    if list(model_graph)!=list(range(len(mapping))):raise ValueError("Original/model node mapping differs")
    lookup={}
    for row in rows:
        token=(row["src"],row["dst"],row["relation"],row.get("nx_key") if row["origin"]=="F3" else None)
        if token in lookup:raise ValueError("Duplicate original edge identity")
        lookup[token]=row["key"]
    forward={};endpoints={}
    for src,dst,key,data in original.edges(keys=True,data=True):
        rel=data["edge_type"]
        token=(src,dst,rel,None if rel in NEW_RELATIONS else key)
        if token not in lookup:raise ValueError("Unbound forward edge identity")
        ident=lookup[token]
        a,b=model_graph.nodes[mapping[src]],model_graph.nodes[mapping[dst]]
        c=(a["node_type"],rel,b["node_type"])
        forward.setdefault(c,[]).append(ident)
        endpoints.setdefault(c,[]).append((a["node_hetero_id"],b["node_hetero_id"]))
    keys={};matrices={};pairs={}
    for c,ids in forward.items():
        rev=(c[2],"REV_"+c[1],c[0])
        if c in keys or rev in keys:raise ValueError("Forward/reverse collision")
        v=torch.from_numpy(np.stack([values[k] for k in ids]).copy())
        ab=torch.tensor(endpoints[c],dtype=torch.long).t()
        keys[c],keys[rev]=tuple(ids),tuple(ids)
        matrices[c],matrices[rev]=v,v.clone()
        pairs[c],pairs[rev]=(ab[0],ab[1]),(ab[1],ab[0])
    return matrices,keys,pairs


def make_attribute_model(task,graph_or_path,profile,attributes_manifest,device,fold,
                         node_feature,hidden_size,layers,heads):
    from .model import make_edge_model,validate_registration
    spec=validate_profile(profile)
    path=Path(attributes_manifest).resolve();manifest=read(path)
    if manifest["task_id"].rsplit("_",1)[-1]!=task:raise ValueError("Attribute task granularity differs")
    source=graph_or_path if isinstance(graph_or_path,nx.Graph) else read_graph(Path(graph_or_path))
    if not isinstance(source,nx.MultiDiGraph):raise TypeError("Expected directed multigraph")
    before=graph_fingerprint(source)
    base=copy.deepcopy(source)
    remove=[(s,t,k) for s,t,k,d in base.edges(keys=True,data=True) if d.get("edge_type") in NEW_RELATIONS]
    base.remove_edges_from(remove)
    if remove and not spec["new_relations"]:raise ValueError("E1 edges supplied to G3R-TA")
    edges=load_edges(checked(manifest["f4_manifest"]))
    values=load_attributes(path,base,edges)
    rows=edge_rows(base,edges)
    enriched=add_edges(base,edges) if spec["new_relations"] else base
    if remove and before!=graph_fingerprint(enriched):raise ValueError("E1 input differs from frozen F4")
    seed=seeds(task,fold)
    permutation=None
    if spec["placebo"]=="attributes":
        values,permutation=permute_attributes(rows,values,seed["constructor"])
    indices=list(manifest["core_indices"])
    if spec["edge_features"]=="core_context":
        indices=sorted(set(indices)|set(manifest["context_indices"]))
    structural="G4R" if spec["new_relations"] else "G3R-T"
    fresh=make_edge_model(task,enriched,structural,device="cpu",fold=fold,
                         node_feature=node_feature,hidden_size=hidden_size,layers=layers,heads=heads)
    model=(EdgeNodeClassifier if task=="node" else EdgeGraphClassifier)(fresh)
    matrices,keys,pairs=typed_attributes(enriched,model.nx_graph,rows,values)
    g=model.symmetrical_global_graph
    if set(matrices)!=set(g.canonical_etypes):raise ValueError("Attribute schema differs")
    for c,mat in matrices.items():
        if not all(torch.equal(x,y) for x,y in zip(pairs[c],g.edges(etype=c,order="eid"))):
            raise ValueError("Attribute/endpoints alignment differs")
        g.edges[c].data["ea"]=mat
    # Structural adapter already copied every shared/new typed parameter using
    # EP1. Reconstruct each parent, then copy those parameters; only u/U remain new.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed["constructor"])
        upgraded=[]
        for old in model.gcs:
            layer=EdgeAwareHGTLayer(hidden_size,hidden_size,model.ntypes_dict,model.etypes_dict,
                                   heads,dropout=old.drop.p,use_norm=old.use_norm)
            result=layer.load_state_dict(old.state_dict(),strict=False)
            if set(result.missing_keys)!={"u"}|{"U."+f for f in layer.U} or result.unexpected_keys:
                raise ValueError("Parent parameter copy mismatch")
            if any(not torch.equal(v,layer.state_dict()[k]) for k,v in old.state_dict().items()):
                raise AssertionError("Shared parameter copy differs")
            upgraded.append(layer)
        model.gcs=nn.ModuleList(upgraded)
        model.edge_encoder=EdgeAttrEncoder(len(indices))
    model.edge_profile=profile
    model.edge_indices=tuple(indices)
    model.edge_attribute_keys=keys
    model.edge_attribute_binding=dict(manifest=ref(path),key_digest=row_binding_digest(keys),
        constructor_seed=seed["constructor"],permutation=permutation,
        row_relations=[dict(key=r["key"],relation=r["relation"]) for r in rows])
    model.train(fresh.training)
    if str(device)!="cpu":
        model.to(device);model.symmetrical_global_graph=g.to(device)
        model.supervised_node_mask=model.supervised_node_mask.to(device)
        model.device=str(device)
    if before!=graph_fingerprint(source):raise AssertionError("Original graph mutated")
    validate_registration(model)
    return model


def validate_attributes(model,deep=True):
    if type(model) not in (EdgeNodeClassifier,EdgeGraphClassifier):
        raise ValueError("Attribute profile requires the edge forward adapter")
    if not isinstance(model.edge_encoder,EdgeAttrEncoder):
        raise ValueError("Missing shared edge encoder")
    binding=model.edge_attribute_binding
    path=checked(binding["manifest"]);manifest=read(path)
    spec=validate_profile(model.edge_profile)
    indices=manifest["core_indices"]
    if spec["edge_features"]=="core_context":indices=sorted(set(indices)|set(manifest["context_indices"]))
    if tuple(indices)!=model.edge_indices or model.edge_encoder.in_dim!=len(indices):
        raise ValueError("Edge feature selection differs")
    if row_binding_digest(model.edge_attribute_keys)!=binding["key_digest"]:
        raise ValueError("Edge row identity differs")
    graph=model.symmetrical_global_graph
    if set(model.edge_attribute_keys)!=set(graph.canonical_etypes):raise ValueError("Attribute relation schema differs")
    for c in graph.canonical_etypes:
        ea=graph.edges[c].data.get("ea")
        if ea is None or ea.dtype!=torch.uint8 or ea.shape!=(graph.num_edges(c),74) or ea.requires_grad:
            raise ValueError("Invalid frozen edge attributes")
    if not deep:return
    values=load_attributes(path)
    if spec["placebo"]=="attributes":
        values,audit=permute_attributes(binding["row_relations"],values,model.edge_seeds["constructor"])
        if audit!=binding["permutation"]:raise ValueError("Attribute permutation binding differs")
    elif binding["permutation"] is not None:raise ValueError("Unexpected attribute permutation")
    if binding["constructor_seed"]!=model.edge_seeds["constructor"]:raise ValueError("Attribute seed differs")
    for c,ids in model.edge_attribute_keys.items():
        expected=torch.from_numpy(np.stack([values[k] for k in ids]))
        if not torch.equal(expected,graph.edges[c].data["ea"].cpu()):
            raise ValueError("Edge attributes differ from sealed NPZ rows")
