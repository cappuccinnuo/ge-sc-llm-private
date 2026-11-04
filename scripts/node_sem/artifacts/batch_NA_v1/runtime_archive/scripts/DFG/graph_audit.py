"""Exact structural invariants for adding only forward DDG edges."""
import hashlib
import numpy as np
from . import DATA_DEF_USE

def frozen(value):
    if isinstance(value,np.ndarray):
        return ("ndarray",value.dtype.str,value.shape,value.tobytes().hex())
    if isinstance(value,np.generic): return ("numpy",str(value.dtype),value.item())
    if isinstance(value,dict):
        return ("dict",tuple((frozen(k),frozen(v)) for k,v in value.items()))
    if isinstance(value,(list,tuple)):
        return (type(value).__name__,tuple(frozen(x) for x in value))
    if isinstance(value,(str,int,float,bool,bytes)) or value is None:
        return (type(value).__name__,repr(value))
    raise ValueError("Unaudited graph attribute type: "+type(value).__name__)

def fingerprint(graph, exclude_ddg=False):
    nodes=tuple((frozen(n),frozen(d)) for n,d in graph.nodes(data=True))
    edges=tuple((frozen(s),frozen(t),frozen(k),frozen(d))
                for s,t,k,d in graph.edges(keys=True,data=True)
                if not (exclude_ddg and d.get("edge_type")==DATA_DEF_USE))
    body=repr((frozen(graph.graph),nodes,edges)).encode("utf8")
    return hashlib.sha256(body).hexdigest()

def assert_augmented(base, enhanced):
    if fingerprint(base)!=fingerprint(enhanced,exclude_ddg=True):
        raise AssertionError("Base nodes/order/attributes/edges/keys changed")
    pairs=set()
    for s,t,d in enhanced.edges(data=True):
        if d.get("edge_type")=="REV_DATA_DEF_USE":
            raise AssertionError("Reverse DDG is outside phase-one scope")
        if d.get("edge_type")!=DATA_DEF_USE: continue
        if s==t or (s,t) in pairs: raise AssertionError("DDG duplicate or self edge")
        if enhanced.nodes[s]["source_file"]!=enhanced.nodes[t]["source_file"]:
            raise AssertionError("Cross-file DDG edge")
        pairs.add((s,t))
    return {"base_sha256":fingerprint(base),"enhanced_sha256":fingerprint(enhanced),
            "base_nodes":len(base),"base_edges":base.number_of_edges(),
            "ddg_edges":len(pairs),
            "canonical_relations":len({(enhanced.nodes[s]["node_type"],
                d["edge_type"],enhanced.nodes[t]["node_type"])
                for s,t,d in enhanced.edges(data=True)})}
