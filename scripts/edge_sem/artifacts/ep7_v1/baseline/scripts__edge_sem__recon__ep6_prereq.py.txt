"""EP6 prerequisite reconstruction and strict read-only historical comparisons."""
import argparse
import json
from collections import Counter
import numpy as np
from .ep6_common import OUT, TASKS, historical_refs
from .common import ROOT, read, checked, write, ref
from scripts.edge_sem.build_f4 import build_task, load_edges
from scripts.edge_sem.attr_batch import load_attributes, numeric_digest
F4 = OUT.parent/"f4_v2"
OLD = OUT.parent/"ep5_v1/attributes"
BITS = list(range(22,30))+list(range(37,41))


def historical_manifest(path, attrs=False):
    before=read(OUT/"before.json")
    inventory={r["path"]:r for r in before["prior_artifacts"]}
    checked(inventory[str(path)])
    m=read(path)
    historical_refs(m["implementation"])
    for r in (m["sources"] if attrs else m["source_refs"]).values():checked(r)
    inputs=m["input_provenance"] if attrs else m["inputs"]
    for r in inputs["graphs"].values():checked(r)
    for name in ("plan","store","audit"):checked(inputs[name])
    names=("attrs","diagnostics","facts","f4_manifest","layout","selection") if attrs else ("edges","audit")
    for name in names:checked(m[name])
    if attrs:
        seal=path.with_name("manifest.seal.json")
        checked(inventory[str(seal)])
        if read(seal)["manifest"]!=ref(path):raise ValueError("Historical seal mismatch")
        for r in read(checked(m["selection"]))["per_task"].values():checked(r)
    return m


def f4():
    summary={}
    for task in ("reentrancy_contract","access_control_contract")+TASKS:
        oldpath=OUT.parent/"f4_v1"/task/"manifest.json"
        old=historical_manifest(oldpath)
        rows=[json.loads(s) for s in checked(old["edges"]).read_text().splitlines()]
        build_task(task,F4/task)
        new=load_edges(F4/task/"manifest.json")
        oldkeys={(r["src"],r["dst"],r["relation"]) for r in rows}
        extra=[r for r in new if (r["src"],r["dst"],r["relation"]) not in oldkeys]
        if [r for r in new if (r["src"],r["dst"],r["relation"]) in oldkeys]!=rows:
            raise ValueError("Historical F4 rows differ")
        if any(r["relation"]!="MOD_APPLY" or r["src_anchor"][2]!="fallback_receive_definition" for r in extra):
            raise ValueError("Unexpected new F4 rows")
        report=dict(old=ref(oldpath),new=ref(F4/task/"manifest.json"),extra_rows=extra,
                    old_rows_exact=True,old_rows=len(rows),new_rows=len(new),
                    audit=ref(F4/task/"f4_audit.json"))
        write(OUT/"f4_delta"/(task+".json"),report)
        if task in TASKS and extra:raise ValueError("Node F4 rows unexpectedly changed; see f4_delta")
        summary[task]=report
    write(OUT/"f4_delta.json",dict(passed=True,tasks=summary))


def strict_delta(keys,old,newkeys,new,gaps,relations):
    if keys!=newkeys or old.shape!=new.shape:raise ValueError("Edge key/shape mismatch")
    changes=np.argwhere(old!=new)
    for row,bit in changes:
        if int(bit) not in BITS or keys[row] not in gaps or relations[row]!="DATA_DEF_USE" or old[row,bit]!=0 or new[row,bit]!=1:
            raise ValueError("Unauthorized attribute delta: "+str((keys[row],int(bit))))
    return dict(edge_keys_exact=True,other_columns_bitwise_exact=True,only_missing_sink_zero_to_one=True,
                changed_bits=len(changes),changed_edges=len(set(int(r) for r,b in changes)))


def attributes():
    from scripts.node_sem.facts_io import load_context
    from scripts.edge_sem.attrs import edge_rows
    from scripts.DFG.frontend import parse,walk
    summary={}
    for task in TASKS:
        old=historical_manifest(OLD/task/"manifest.json",True)
        with np.load(checked(old["attrs"]),allow_pickle=False) as a:
            keys=a["edge_keys"].tolist();previous=a["attrs"].copy()
        if numeric_digest(keys,previous)!=old["numeric_digest"]:raise ValueError("Historical numeric digest mismatch")
        ctx=load_context(task);g=ctx["graphs"]["F3"];edges=load_edges(F4/task/"manifest.json")
        path=OUT/"attributes"/task/"manifest.json";m=read(path)
        values=load_attributes(path,g,edges);new=np.stack(list(values.values()))
        rows=edge_rows(g,edges)
        gaps={r["edge_key"] for r in read(checked(old["diagnostics"]))["edges"]
              if "no_exact_dfg_to_for_this_edge" in r["source_gaps"]}
        delta=strict_delta(keys,previous,list(values),new,gaps,[r["relation"] for r in rows])
        diag=read(checked(m["diagnostics"]));sinks={r["edge_key"]:r for r in diag["sinks"]}
        parameter=[i for i,k in enumerate(keys) if sinks.get(k,{}).get("parameter_entry")]
        data=[i for i,r in enumerate(rows) if r["relation"]=="DATA_DEF_USE"]
        counts={str(b):dict(old=int(previous[:,b].sum()),new=int(new[:,b].sum()),
            parameter_entry_added=int((new[parameter,b]-previous[parameter,b]).sum())) for b in BITS}
        no_pragma=[]
        files={r["file"] for r in rows if r["relation"] in ("DATA_DEF_USE","READS_STATE","WRITES_STATE","ENV_FLOW")}
        for file in sorted(files):
            if diag["cfg"][file]["pre_08"] is not None:continue
            text=ctx["source_text"][file]
            pragmas=[text.encode()[n.start_byte:n.end_byte].decode() for n in walk(parse(text).root_node)
                     if n.type=="pragma_directive"]
            no_pragma.append(dict(file=file,source_sha256=ctx["sources"][file]["sha256"],pragmas=pragmas,
                compiler_metadata=ctx["sources"][file].get("metadata"),
                has_compiler_metadata=bool(ctx["sources"][file].get("metadata"))))
        selection=read(checked(m["selection"]));before=read(checked(old["selection"]))
        summary[task]=dict(delta=delta,bits=counts,sink_consistency_compared=sum(r["source"]=="recorded" for r in sinks.values()),
            sink_sources=dict(Counter(r["source"] for r in sinks.values())),
            data_without_mapped_sink=int(np.sum(new[data,22:27].sum(axis=1)==0)),
            unknown_pre08_files=no_pragma,manifest=ref(path),
            selection_changes={name:dict(old=before[name],new=selection[name],
                added=sorted(set(selection[name])-set(before[name])),removed=sorted(set(before[name])-set(selection[name])))
                for name in ("core_indices","context_indices")})
        print(task,delta,counts,flush=True)
    write(OUT/"attribute_delta.json",dict(passed=True,tasks=summary))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=("f4","attributes"));a=p.parse_args()
    (f4 if a.mode=="f4" else attributes)()
