"""Explicit experimental input adapter; no mutation of legacy loaders or HGT.

Legacy reflection protects only DATA_DEF_USE. Use this adapter for state schema
checks. Existing formal training entry points are NOT automatically migrated.
"""
from collections import OrderedDict
from . import STATE_DEF_USE

def reflected_input(edge_data):
    from sco_models.graph_utils import reflect_graph
    base=OrderedDict((k,v) for k,v in edge_data.items() if k[1]!=STATE_DEF_USE)
    result=reflect_graph(base)
    for k,v in edge_data.items():
        if k[1]==STATE_DEF_USE:
            if k in result:raise ValueError("State/base canonical collision")
            result[k]=v
    return result

def build_dgl(graph):
    import torch,dgl
    data=OrderedDict();ids={};counts={}
    for node,attr in graph.nodes(data=True):
        typ=attr["node_type"];ids[node]=counts.get(typ,0);counts[typ]=ids[node]+1
    for s,t,d in graph.edges(data=True):
        k=(graph.nodes[s]["node_type"],d["edge_type"],graph.nodes[t]["node_type"])
        pair=data.setdefault(k,([],[]));pair[0].append(ids[s]);pair[1].append(ids[t])
    tensors=OrderedDict((k,(torch.tensor(v[0],dtype=torch.int64),torch.tensor(v[1],dtype=torch.int64))) for k,v in data.items())
    return dgl.heterograph(reflected_input(tensors),num_nodes_dict=counts),ids
