"""N-C2 append-only carrier preparation; checked against full carry per task."""
import copy
from pathlib import Path
import numpy as np
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,checked,ref,write
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from .carrier import _load,_aligned,vector_sha,row_key
from .feature_spec import FeatureSpec

def extend(old,graph,spec,student_ref,out):
    oldspec=FeatureSpec.from_json(read(checked(old["spec"])))
    record=read(checked(old["feature_view"]))
    if record["spec_sha256"]!=oldspec.digest() or record["data"]!=old["feature_npz"]:
        raise ValueError("Old carrier binding differs")
    before=graph_fingerprint(graph)
    if before!=old["original_graph_fingerprint"] or record["original_graph_fingerprint"]!=before:
        raise ValueError("Frozen graph differs")
    with np.load(str(checked(old["feature_npz"])),allow_pickle=False) as f:previous=f["features"].copy()
    meta,values=_load(student_ref)
    _aligned(meta,graph,old["task_id"],"original",384)
    if spec.modalities[:-1]!=oldspec.modalities or spec.modalities[-1]["manifest"]!=student_ref:
        raise ValueError("Student changed old modalities")
    index={r["row_key"]:i for i,r in enumerate(meta["rows"])}
    matrix=np.zeros((len(graph),spec.carrier_dim()),dtype=np.float32)
    for name,part in oldspec.layout().items():
        now=spec.layout()[name]
        matrix[:,now["presence"]]=previous[:,part["presence"]]
        matrix[:,now["start"]:now["stop"]]=previous[:,part["start"]:part["stop"]]
    student=spec.layout()["student"]
    newrows=[];carried=copy.deepcopy(graph)
    for i,((nid,attrs),r) in enumerate(zip(graph.nodes(data=True),record["rows"])):
        if row_key(nid,attrs)!=r["row_key"] or nid!=r["original_graph_node_id"]:
            raise ValueError("Old row identity mismatch")
        source=index[r["row_key"]]
        matrix[i,student["presence"]]=float(meta["rows"][source]["present"])
        matrix[i,student["start"]:student["stop"]]=values[source]
        row=copy.deepcopy(r);row["presence"]=list(r["presence"])+[meta["rows"][source]["present"]]
        row["vector_sha256"]=vector_sha(matrix[i]);newrows.append(row)
        carried.nodes[nid]["token"]=matrix[i]
    result=copy.deepcopy(record)
    result.update(rows=newrows,spec=spec.to_json(),spec_sha256=spec.digest(),
        modalities={m["name"]:m["manifest"] for m in spec.modalities},
        feature_shape=list(matrix.shape),carrier_graph_fingerprint=graph_fingerprint(carried))
    if graph_fingerprint(graph)!=before:raise ValueError("Input graph mutated")
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    with (out/"carrier.npz").open("xb") as f:np.savez_compressed(f,features=matrix)
    result["data"]=ref(out/"carrier.npz")
    write(out/"carrier_manifest.json",result)
    return dict(manifest=ref(out/"carrier_manifest.json"),data=result["data"],record=result)

def compare_deep(fast,deep):
    a=read(checked(fast["manifest"]));b=deep
    if {k:v for k,v in a.items() if k!="data"}!={k:v for k,v in b.items() if k!="data"}:
        raise ValueError("Fast and complete carrier metadata differs")
    with np.load(str(checked(fast["data"])),allow_pickle=False) as f:values=f["features"]
    if any(vector_sha(v)!=r["vector_sha256"] for v,r in zip(values,b["rows"])):
        raise ValueError("Fast and complete carrier vectors differ")
    return True
