"""Read existing NS-P9 predictions, facts and graph edges; AST is used only for identity."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import networkx as nx
import numpy as np
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from .facts_ast import FUNCTIONS, key
from .static_profile import explain
from .carrier import row_key
from .summary import ART, DEFAULT, Sources, read, write, reference, csv_write


def align_file(graph, filename, source):
    ids=[n for n,a in graph.nodes(data=True) if a["source_file"]==filename and a["node_type"]!="env_source"]
    view=ProjectionView(source, filename)
    projector=Projector(graph.subgraph(ids).copy(),view)
    inverse=defaultdict(list)
    for raw,compat in view.mapping.items():
        inverse[compat].append(raw)
    by_ast={i:k for k,i in view.compat_ids.items()}
    aligned={}
    for ast_id,nid in projector.by_ast.items():
        candidates=inverse[by_ast[ast_id]]
        if len(candidates)!=1:raise ValueError("Ambiguous raw AST identity")
        node=view.raw_nodes[candidates[0]]
        owner=node
        while owner is not None and owner.type not in FUNCTIONS:
            owner=owner.parent
        def text(n):return view.raw[n.start_byte:n.end_byte].decode("utf8") if n is not None else ""
        if owner is None:
            function=None;owner_key=None;function_lines=None
        else:
            body=owner.child_by_field_name("body")
            function=view.raw[owner.start_byte:body.start_byte if body else owner.end_byte].decode("utf8").strip()
            owner_key=list(key(owner));function_lines=[owner.start_point[0]+1,owner.end_point[0]+1]
        aligned[nid]=dict(function=function,function_key=owner_key,function_lines=function_lines,
            raw_lines=[node.start_point[0]+1,node.end_point[0]+1],
            raw_span=[node.start_byte,node.end_byte],source_text=text(node),
            graph_stored_lines=graph.nodes[nid].get("node_source_code_lines"))
    return aligned


def edges(graph, ids):
    selected=set(ids)
    return [dict(source=u,target=v,key=k,attributes=a) for u,v,k,a in graph.edges(keys=True,data=True)
            if u in selected and v in selected]


def build(root=DEFAULT, collection=None):
    root=Path(root)
    collection=Path(collection) if collection else root/"collection_attempt3"
    out=root/"cases_attempt2"
    out.mkdir(exist_ok=False)
    sources=Sources()
    complete=read(sources.root(collection/"collect_complete.json"))
    sources.refs(complete["artifacts"])
    positives=read(collection/"reports/positive_nodes.json")
    persistent=[r for r in positives if r["checkpoint"]=="best" and r["all_missed"]]
    corrected=read(collection/"reports/removed_false_positives.json")
    plan=read(sources.root(ART/"batch_NC2_v1/plan.json"))
    cases=[];files=[];counts=[];false_positives=[]
    for task in sorted({r["task_id"]for r in persistent}):
        job=next(j for j in plan["jobs"]if j["task_id"]==task and j["fold"]==0 and j["name"]=="S5")
        graph=nx.read_gpickle(sources.check(job["graph"]))
        before=graph_fingerprint(graph)
        labels=sources.json(job["label_view"])[task]
        label_index={r["original_graph_node_id"]:r for r in labels}
        spec=sources.json(job["spec"])
        manifest=sources.json(next(m["manifest"]for m in spec["modalities"]if m["name"]=="static"))
        npz=np.load(sources.check(manifest["data"]),allow_pickle=False)
        static=npz["features"]
        fact_rows=[__import__("json").loads(l) for l in sources.check(manifest["input_text"]).read_text().splitlines()]
        facts={r["row_key"]:r["facts"]for r in fact_rows}
        rows=manifest["rows"];positions={r["row_key"]:i for i,r in enumerate(rows)}
        sources.refs(manifest["accepted"]["proof"])
        schema_ref=next(r for r in manifest["implementation"].values() if r["path"].endswith("behavior_schema.json"))
        schema=sources.json(schema_ref)
        selected=[dict(r,case_type="persistent_fn")for r in persistent if r["task_id"]==task]
        selected += [dict(r,case_type="removed_fp")for r in corrected if r["task_id"]==task]
        filenames=sorted({r["file"]for r in selected})
        for filename in filenames:
            src_ref=manifest["sources"][filename]
            text=sources.check(src_ref).read_text(encoding="utf8")
            aligned=align_file(graph,filename,text)
            ids=[n for n,a in graph.nodes(data=True) if a["source_file"]==filename]
            file_edges=edges(graph,ids)
            node_evidence=[]
            for nid in ids:
                a=graph.nodes[nid]
                node_evidence.append(dict(id=nid,node_type=a["node_type"],code=a["code"],
                    alignment=aligned.get(nid),facts=facts[row_key(nid,a)]))
            filename_out=task+"__"+filename+".json"
            write(out/filename_out,dict(task_id=task,file=filename,source=src_ref,graph=job["graph"],
                nodes=node_evidence,edges=file_edges,
                note="Raw F3 stored directions. G3R uses explicit reverse semantic relations in the model; no reversed edge is a reversed causal fact."))
            files.append(reference(out/filename_out))
            for row in [r for r in selected if r["file"]==filename]:
                nid=row["original_graph_node_id"]
                if nid not in aligned:raise ValueError("Required case lacks exact AST projection")
                pos=positions[nid]
                if rows[pos]["source_sha256"]!=row["source_sha256"] or rows[pos]["node_type"]!=row["node_type"]:
                    raise ValueError("Static case identity differs")
                if src_ref["sha256"]!=row["source_sha256"]:
                    raise ValueError("Source identity differs")
                label=label_index[nid]
                detail=dict(row,alignment=aligned[nid],frozen_label=label,
                    source=src_ref,static_active_bits=explain(static[pos],schema),
                    static_manifest=next(m["manifest"]for m in spec["modalities"]if m["name"]=="static"),
                    facts=facts[nid],graph=job["graph"],
                    incident_edges=[e for e in file_edges if nid in (e["source"],e["target"])],
                    file_evidence=files[-1])
                counts_for_case=[]
                for j in plan["jobs"]:
                    if j["task_id"]!=task or j["name"]!="S5":continue
                    train=set(j["split"]["inner_train_files"])
                    matching=[r for r in labels if r["file"]in train and r["L-audit_include"]
                        and r["L-audit_target"]==1 and not r["solidifi"]and r["node_type"]==row["node_type"]]
                    counts_for_case.append(dict(fold=j["fold"],positive_nodes=len(matching),
                        positive_files=len({r["file"]for r in matching}),node_ids=[r["original_graph_node_id"]for r in matching]))
                detail["same_type_nonSolidiFI_inner_train"]=counts_for_case
                if row["case_type"]=="persistent_fn":
                    cases.append(detail)
                    for c in counts_for_case:
                        counts.append(dict(task_id=task,file=filename,node_id=nid,node_type=row["node_type"],**c))
                else:false_positives.append(detail)
        if graph_fingerprint(graph)!=before:raise ValueError("Graph modified by inspection")
    write(out/"persistent_cases.json",cases)
    write(out/"removed_fp_cases.json",false_positives)
    csv_write(out/"train_support.csv",counts)
    csv_write(out/"removed_false_positives.csv",[dict(task_id=r["task_id"],file=r["file"],
        source_sha256=r["source_sha256"],node_id=r["original_graph_node_id"],node_type=r["node_type"],
        function=r["alignment"]["function"],raw_lines=r["alignment"]["raw_lines"],
        graph_stored_lines=r["alignment"]["graph_stored_lines"],
        S4_probability=r["S4_probability"],S5_probability=r["S5_probability"])
        for r in false_positives])
    write(out/"source_audit.json",list(sources.verified.values()))
    write(out/"complete.json",dict(passed=True,cases=len(cases),removed_fp=len(false_positives),
        graph_unchanged=True,new_features=False,artifacts=[reference(p)for p in sorted(out.iterdir())if p.is_file()]))
    return cases


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=str(DEFAULT))
    build(p.parse_args().root)
