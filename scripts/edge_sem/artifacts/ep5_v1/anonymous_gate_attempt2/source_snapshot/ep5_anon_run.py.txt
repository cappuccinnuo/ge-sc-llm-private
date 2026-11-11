"""EP5 all-source graph-space invariance gate, fail-fast with durable evidence."""
import argparse
from pathlib import Path
import copy
import hashlib
import json
from collections import Counter
import numpy as np
from .common import ROOT,read,write,ref,checked
from .ep5_common import OUT,TASKS
from .ep5_anon import translate,evaluate
from scripts.node_sem.facts_io import load_context
from scripts.edge_sem.attr_batch import load_attributes,numeric_digest
from scripts.edge_sem.attrs import edge_rows
from scripts.edge_sem.build_f4 import load_edges
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint


def main(out_dir=None):
    if not read(OUT/"attribute_delta.json")["passed"]:
        raise ValueError("Section 0 has not passed")
    dest=Path(out_dir).resolve() if out_dir else OUT/"anonymous_gate"
    if dest.parent!=OUT:raise ValueError("Gate output must be a new EP5 attempt")
    dest.mkdir(exist_ok=False)
    sources=[ref(ROOT/p) for p in ("scripts/edge_sem/recon/ep5_anon.py","scripts/edge_sem/recon/ep5_anon_run.py")]
    write(dest/"started.json",dict(implementation=sources,training_executed=False))
    completed=[]
    task=file=None
    try:
        for task in TASKS:
            ctx=load_context(task);graph=ctx["graphs"]["F3"];before=graph_fingerprint(graph)
            manifest_path=OUT/"attributes"/task/"manifest.json"
            manifest=read(manifest_path);edges=load_edges(checked(manifest["f4_manifest"]))
            attrs=load_attributes(manifest_path,graph,edges)
            audit_before=hashlib.sha256(json.dumps(ctx["audit"],sort_keys=True).encode()).hexdigest()
            for index,(file,source) in enumerate(sorted(ctx["source_text"].items())):
                sub=graph.subgraph([n for n,a in graph.nodes(data=True) if a["source_file"]==file]).copy()
                old_edges=[e for e in edges if e["file"]==file]
                rows=edge_rows(sub,old_edges);keys=[r["key"] for r in rows]
                original,old_values,_=evaluate(source,file,sub,ctx["audit"],ctx["sources"][file].get("metadata"))
                if {(e["src"],e["dst"],e["relation"]) for e in original}!={(e["src"],e["dst"],e["relation"]) for e in old_edges}:
                    raise ValueError("Original E1 recomputation differs from sealed F4")
                if set(keys)!=set(old_values) or any(not np.array_equal(old_values[k],attrs[k]) for k in keys):
                    raise ValueError("Original per-file attributes differ from sealed EP5")
                temp,proof,result,adapter=translate(source,file,sub,ctx["audit"],ctx["sources"][file].get("metadata"))
                fresh,new_values,_=evaluate(result["rewritten"],file,temp,proof,adapter["metadata"],adapter["original_names"])
                old_set={(e["src"],e["dst"],e["relation"]) for e in old_edges}
                new_set={(e["src"],e["dst"],e["relation"]) for e in fresh}
                differences=[dict(edge_key=k,bits=np.flatnonzero(old_values[k]!=new_values[k]).tolist())
                             for k in keys if k in new_values and not np.array_equal(old_values[k],new_values[k])]
                row=dict(task_id=task,file=file,source=ctx["sources"][file],status=result["status"],
                    renamed_sha256=hashlib.sha256(result["rewritten"].encode()).hexdigest(),
                    old_new_edges_equal=old_set==new_set,attribute_keys_equal=set(keys)==set(new_values),
                    attribute_differences=differences,
                    missing_edges=sorted(old_set-new_set,key=str),added_edges=sorted(new_set-old_set,key=str),
                    input_edges=len(keys),new_relation_edges=len(old_edges),
                    projection_nodes=len(adapter.get("projection",[])),
                    binding_occurrences=len(result.get("bindings",[])),
                    translation_proof=list({json.dumps(r,sort_keys=True):r for r in adapter["bindings"]}.values()),
                    fallback_issues=result.get("issues",[]),
                    metadata_policy=adapter["compiler_metadata_policy"],
                    original_numeric_digest=numeric_digest(keys,np.stack([old_values[k] for k in keys])) if keys else None)
                row["passed"]=row["old_new_edges_equal"] and row["attribute_keys_equal"] and not differences
                path=dest/task/(str(index).zfill(3)+".json");write(path,row)
                completed.append(ref(path))
                if not row["passed"]:raise ValueError("Graph-space invariance failed: "+task+"/"+file)
                print(task,index+1,"/",len(ctx["sources"]),file,result["status"],"passed",flush=True)
            if before!=graph_fingerprint(graph) or audit_before!=hashlib.sha256(json.dumps(ctx["audit"],sort_keys=True).encode()).hexdigest():
                raise AssertionError("Original graph/evidence mutated")
        records=[read(checked(r)) for r in completed]
        write(dest/"summary.json",dict(passed=True,files=completed,counts=dict(Counter(r["status"] for r in records)),
            tasks={t:dict(files=sum(r["task_id"]==t for r in records),
                          statuses=dict(Counter(r["status"] for r in records if r["task_id"]==t)))
                   for t in TASKS},training_executed=False,graphs_written=0,
            note="Fallback checks are identity controls, not evidence of invariance under a nontrivial renaming.",
            implementation=sources))
    except Exception as exc:
        write(dest/"failure.json",dict(passed=False,task_id=task,file=file,error=repr(exc),completed=completed))
        raise

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--out")
    main(parser.parse_args().out)
