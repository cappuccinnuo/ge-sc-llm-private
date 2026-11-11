"""Read-only diagnosis of sealed data edges missing target fact entries."""
from collections import defaultdict
from scripts.edge_sem.attr_batch import TASKS, F4
from scripts.edge_sem.io import read, checked, write
from scripts.edge_sem.build_f4 import load_edges
from scripts.edge_sem.attrs import edge_rows
from scripts.edge_sem.attr_sources import AttributeSource
from scripts.node_sem.facts_io import load_context, check_layer_edge
from scripts.node_sem.facts import extract
from scripts.node_sem.carrier import row_key
from pathlib import Path
out={}
for task in TASKS:
    context=load_context(task);graph=context["graphs"]["F3"]
    edges=load_edges(F4/task/"manifest.json")
    facts=extract(task,context=context)
    mapped={nid:facts[row_key(nid,a) if a["node_type"]=="env_source" else nid] for nid,a in graph.nodes(data=True)}
    files=defaultdict(list)
    for row in edge_rows(graph,edges):
        if row["relation"]=="DATA_DEF_USE":files[row["file"]].append(row)
    failures=[]
    for file,rows in files.items():
        source=AttributeSource(context["source_text"][file],file,graph,context["sources"][file].get("metadata"))
        for row in rows:
            for ev in check_layer_edge(row["src"],row["dst"],row["data"],context["audit"]):
                fn=source.functions[ev["function"]]
                symbol=source.cfg.symbol(fn,ev["analysis_path"],ev["symbol"])
                target=mapped[row["dst"]]
                matched=[x["kind"] for x in target["dfg"].get("uses",()) if x["var"]==symbol.name]
                if symbol.kind not in matched:
                    failures.append(dict(edge_key=row["key"],file=file,src=row["src"],dst=row["dst"],
                         src_type=graph.nodes[row["src"]]["node_type"],dst_type=graph.nodes[row["dst"]]["node_type"],
                         dst_ast=source.raw[row["dst"]].type,dfg=target["dfg"],
                         symbol_name=symbol.name,symbol_kind=symbol.kind,evidence=ev))
    out[task]=failures
    print(task,len(failures),flush=True)
write(Path(__file__).with_name("dfg_target_diagnosis.json"),out)
