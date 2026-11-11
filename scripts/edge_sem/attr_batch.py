"""EP4 batch assembly: two node tasks share one outcome-blind core selection."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from .io import ROOT, ref, read, checked, write
from .build_f4 import load_edges, implementation_refs as f4_implementation_refs
from .attrs import (EDGE_FEATURE_NAMES, GROUPS, ONE_HOT_GROUPS, MULTI_HOT_GROUPS,
                    CORE_CANDIDATES, CONTEXT, _compute_attributes, edge_rows,
                    endpoint_test, select_groups, validate_vector)
from scripts.node_sem.facts_io import load_context
from scripts.node_sem.facts import extract, implementation_refs as fact_implementation_refs
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint

TASKS=("reentrancy_node","access_control_node")
F4=ROOT/"scripts/edge_sem/artifacts/f4_v2"


def implementation_refs():
    own=[ref(ROOT/"scripts/edge_sem"/n) for n in
         ("attrs.py","attr_sources.py","attr_batch.py","io.py")]
    records=own+f4_implementation_refs()+list(fact_implementation_refs().values())
    return list({r["path"]:r for r in records}.values())


def numeric_digest(keys, matrix):
    h=hashlib.sha256()
    h.update(json.dumps(keys,ensure_ascii=False,separators=(",",":")).encode("utf8"))
    h.update(matrix.tobytes(order="C"))
    return h.hexdigest()



def facts_digest(facts):
    # Original HCG IDs are ints, auxiliary row keys are strings. A row array
    # preserves both identity types and the frozen extraction order.
    payload=[dict(row_key=k,facts=v) for k,v in facts.items()]
    text=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(text.encode("utf8")).hexdigest()


def write_batch(out_dir, requested_task=None):
    if requested_task is not None and requested_task not in TASKS:
        raise ValueError("EP4 core selection requires the two registered node tasks")
    out=Path(out_dir).resolve()
    if ROOT/"scripts/edge_sem/artifacts" not in out.parents:
        raise ValueError("Output must be a new EdgeSem artifact directory")
    out.mkdir(parents=True,exist_ok=False)
    refs=implementation_refs()
    write(out/"started.json",dict(tasks=list(TASKS),implementation=refs,training_executed=False))
    data={};endpoints={}
    for task in TASKS:
        dest=out/task;dest.mkdir()
        manifest_path=F4/task/"manifest.json"
        edges=load_edges(manifest_path);f4=read(manifest_path)
        context=load_context(task)
        if context["provenance"]!=f4["inputs"] or context["sources"]!=f4["source_refs"]:
            raise ValueError("F4/current source provenance differs")
        context["f4_audit"]=read(checked(f4["audit"]))
        graph=context["graphs"]["F3"]
        if graph_fingerprint(graph)!=f4["original_fingerprint"]:
            raise ValueError("F4 graph identity differs")
        print(task,"extracting original-view frozen facts",flush=True)
        facts,facts_audit=extract(task,context=context,return_audit=True)
        fact_hash=facts_digest(facts)
        print(task,"computing forward attributes",flush=True)
        attrs,diagnostics=_compute_attributes(context,graph,edges,facts)
        rows=edge_rows(graph,edges);keys=[r["key"] for r in rows]
        matrix=np.stack([attrs[k] for k in keys])
        with (dest/"attrs.npz").open("xb") as stream:
            np.savez_compressed(stream,edge_keys=np.asarray(keys),attrs=matrix)
        write(dest/"diagnostics.json",diagnostics)
        write(dest/"fact_provenance.json",dict(rows=len(facts),
            facts_sha256=fact_hash,
            sources=context["sources"],provenance=context["provenance"],
            implementation=fact_implementation_refs(),source_view="original",
            labels_used_for_features=False))
        endpoints[task]=endpoint_test(attrs,edges,graph)
        write(dest/"endpoint_test.json",endpoints[task])
        data[task]=(context,graph,edges,attrs,rows,f4,manifest_path,matrix,keys)
        print(task,"attributes",matrix.shape,"complete",flush=True)
    # Selection precedes label access and uses only the per-task bit arrays.
    selection=select_groups(endpoints)
    selection["per_task"]={t:ref(out/t/"endpoint_test.json") for t in TASKS}
    write(out/"selection.json",selection)
    layout=dict(names=list(EDGE_FEATURE_NAMES),dimension=74,dtype="uint8",
                groups=GROUPS,one_hot_groups=list(ONE_HOT_GROUPS),
                multi_hot_groups=list(MULTI_HOT_GROUPS),core_candidates=list(CORE_CANDIDATES),
                context_candidates=list(CONTEXT),reverse_policy="copy exact forward vector; no recomputation")
    write(out/"layout.json",layout)
    manifests={}
    for task in TASKS:
        context,graph,edges,attrs,rows,f4,f4_path,matrix,keys=data[task]
        dest=out/task
        manifest=dict(version="edgesem-attrs-v1",task_id=task,dimension=74,dtype="uint8",rows=len(keys),
            attrs=ref(dest/"attrs.npz"),diagnostics=ref(dest/"diagnostics.json"),
            facts=ref(dest/"fact_provenance.json"),f4_manifest=ref(f4_path),
            input_provenance=context["provenance"],sources=context["sources"],
            original_fingerprint=graph_fingerprint(graph),implementation=refs,
            layout=ref(out/"layout.json"),selection=ref(out/"selection.json"),
            core_indices=selection["core_indices"],context_indices=selection["context_indices"],
            endpoint_tests=selection["per_task"],numeric_digest=numeric_digest(keys,matrix),
            original_graph_unchanged=True,source_view="original",
            labels_used_for_features=False,training_executed=False,gpu_executed=False)
        write(dest/"manifest.json",manifest)
        write(dest/"manifest.seal.json",dict(manifest=ref(dest/"manifest.json")))
        # The only label access occurs after arrays, selection and seals exist.
        from .attr_stats import descriptive_statistics
        write(dest/"stats.json",descriptive_statistics(rows,attrs,graph))
        manifests[task]=ref(dest/"manifest.json")
    write(out/"summary.json",dict(tasks=manifests,selection=ref(out/"selection.json"),
        stats={t:ref(out/t/"stats.json") for t in TASKS},descriptive_implementation=ref(ROOT/"scripts/edge_sem/attr_stats.py"),
        training_executed=False,gpu_executed=False))
    print("EP4 attributes sealed; core:",selection["core_indices"],flush=True)
    return manifests[requested_task] if requested_task else manifests


def load_attributes(manifest_path, graph=None, edges=None):
    path=Path(manifest_path);manifest=read(path)
    seal=read(path.with_name("manifest.seal.json"))
    if seal["manifest"]!=ref(path) or manifest["version"]!="edgesem-attrs-v1":
        raise ValueError("Attribute manifest seal/version differs")
    if manifest["dimension"]!=74 or manifest["dtype"]!="uint8" or manifest["task_id"] not in TASKS:
        raise ValueError("Attribute layout/task metadata differs")
    for r in manifest["implementation"]+list(manifest["sources"].values()):checked(r)
    for r in manifest["input_provenance"]["graphs"].values():checked(r)
    for name in ("plan","store","audit"):checked(manifest["input_provenance"][name])
    for name in ("attrs","diagnostics","facts","f4_manifest","layout","selection"):checked(manifest[name])
    layout=read(checked(manifest["layout"]))
    if layout["names"]!=list(EDGE_FEATURE_NAMES) or layout["dimension"]!=74 or layout["dtype"]!="uint8":
        raise ValueError("Attribute feature layout differs")
    load_edges(checked(manifest["f4_manifest"]))
    selection=read(checked(manifest["selection"]))
    for r in selection["per_task"].values():checked(r)
    if manifest["core_indices"]!=selection["core_indices"] or manifest["context_indices"]!=selection["context_indices"]:
        raise ValueError("Attribute core selection differs")
    with np.load(checked(manifest["attrs"]),allow_pickle=False) as npz:
        if set(npz.files)!={"edge_keys","attrs"}:raise ValueError("Unexpected NPZ fields")
        keys=npz["edge_keys"].tolist();matrix=npz["attrs"].copy()
    if matrix.dtype!=np.uint8 or matrix.shape!=(manifest["rows"],74) or len(keys)!=len(set(keys)):
        raise ValueError("Attribute shape or edge identity differs")
    if numeric_digest(keys,matrix)!=manifest["numeric_digest"]:raise ValueError("Attribute numeric digest differs")
    if graph is not None:
        if graph_fingerprint(graph)!=manifest["original_fingerprint"]:
            raise ValueError("Attribute graph identity differs")
        rows=edge_rows(graph,edges if edges is not None else load_edges(checked(manifest["f4_manifest"])))
        if keys!=[r["key"] for r in rows]:raise ValueError("Attribute edge ordering differs")
        for row,vec in zip(rows,matrix):validate_vector(vec,row["relation"])
    elif not np.isin(matrix,[0,1]).all():raise ValueError("Nonbinary attributes")
    return dict(zip(keys,matrix))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True)
    p.add_argument("--task",choices=TASKS)
    args=p.parse_args();write_batch(args.out,args.task)
