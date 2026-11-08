"""CPU-only static redundancy and non-SolidiFI signal probes for NS-P6c."""
import argparse
import time
from pathlib import Path
import numpy as np
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.experiments.common import digest
from .p6c_core import split_indices, logistic_probe
from .p6c_run import load, OUT
from .na_carrier import load_carrier


def task_data(plan,task):
    jobs=sorted([e["job"] for e in plan["jobs"] if e["job"]["task_id"]==task],key=lambda j:j["fold"])
    if not jobs: raise ValueError("Unknown task")
    first=jobs[0]
    for j in jobs:
        if any(j[k]!=first[k] for k in ("feature_npz","feature_view","label_view","spec","graph","folds")):
            raise ValueError("Mixed task inputs")
        checked(j["folds"])
    carried,record,spec=load_carrier(first)
    matrix=np.asarray([carried.nodes[n]["token"] for n in carried],dtype=np.float32)
    parts={n:matrix[:,s["start"]:s["stop"]] for n,s in spec.layout().items()}
    presence={n:matrix[:,s["presence"]]==1 for n,s in spec.layout().items()}
    return jobs,record["rows"],parts,presence


def run(out,task):
    out=Path(out);plan=load(out);dest=out/"probes"/task;dest.mkdir(parents=True,exist_ok=False)
    write(dest/"started.json",dict(task=task,plan=ref(out/"plan.json"),time=time.time()))
    jobs,rows,parts,presence=task_data(plan,task)
    files=[r["file"] for r in rows]
    schema=read(checked(plan["schema"]))
    static=parts["static"]
    if static.shape[1]!=schema["dimension"] or not np.isin(static,[0,1]).all():
        raise ValueError("STATIC contract differs")
    columns=[]
    for f in schema["fields"]:
        for i,v in enumerate(f["values"],f["start"]):
            columns.append(dict(index=i,group=f["group"],parent_group=f["group"][0],field=f["name"],value=v))
    if [c["index"] for c in columns]!=list(range(static.shape[1])):raise ValueError("Schema column gaps")
    prevalence=static[presence["static"]].mean(0)
    eligible=[dict(c,prevalence=float(prevalence[c["index"]])) for c in columns if .01<=prevalence[c["index"]]<=.99]
    write(dest/"population.json",dict(task=task,rows=len(rows),eligible=eligible,
        input=jobs[0]["feature_npz"],manifest=jobs[0]["feature_view"],schema=plan["schema"],
        global_prevalence_uses_unlabelled_task_population=True,
        labels_unused_for_redundancy=True))
    results=[];start=time.monotonic()
    for j in jobs:
        counts={}
        for source in ("code","ctx"):
            ix=split_indices(files,j["split"],presence[source] & presence["static"])
            counts[source]={r:dict(n=len(idx),row_sha256=digest([rows[int(i)]["row_key"] for i in idx]),
                files=sorted(set(files[int(i)] for i in idx))) for r,idx in ix.items()}
            for col in eligible:
                answer=logistic_probe(parts[source],static[:,col["index"]],ix)
                answer.pop("probabilities",None);answer.pop("predictions",None)
                results.append(dict(task_id=task,fold=j["fold"],source=source,column=col,**answer))
        write(dest/("redundancy_fold_%d.json"%j["fold"]),dict(results=results[-len(eligible)*2:],
            splits=counts,fold_ref=j["folds"],split_sha256=digest(j["split"])))
        print(task,"redundancy fold",j["fold"],"seconds",round(time.monotonic()-start,2),flush=True)
    signal=[]
    if task.endswith("_node"):
        labels=read(checked(jobs[0]["label_view"]))[task]
        table={(r["file"],r["original_graph_node_id"]):r for r in labels}
        y=np.zeros(len(rows),dtype=int);usable=np.zeros(len(rows),dtype=bool)
        for i,r in enumerate(rows):
            label=table.get((r["file"],r["original_graph_node_id"]))
            if label is None:continue  # env_source has no vulnerability label.
            if label["node_type"]!=r["node_type"]:raise ValueError("Label node type differs")
            y[i]=label["L-audit_target"]
            usable[i]=(label["L-audit_include"] and not Path(r["file"]).name.startswith("buggy_")
                and presence["code"][i] and presence["static"][i])
        expected=32 if task=="reentrancy_node" else 20
        if int(y[usable].sum())!=expected:raise ValueError("Non-SolidiFI positive population changed")
        for j in jobs:
            ix=split_indices(files,j["split"],usable)
            split_evidence={r:dict(n=len(idx),positive=int(y[idx].sum()),
                row_sha256=digest([rows[int(i)]["row_key"] for i in idx]),
                files=sorted(set(files[int(i)] for i in idx))) for r,idx in ix.items()}
            for source,x in (("code",parts["code"]),("static",parts["static"]),
                             ("code_static",np.concatenate((parts["code"],static),axis=1))):
                answer=logistic_probe(x,y,ix,select_threshold=True)
                predictions=[]
                for i,prob,pred in zip(ix["outer_test"],answer.pop("probabilities",[]),answer.pop("predictions",[])):
                    r=rows[int(i)];label=table[(r["file"],r["original_graph_node_id"])]
                    predictions.append(dict(file=r["file"],original_graph_node_id=r["original_graph_node_id"],
                        source_sha256=label["source_sha256"],target=int(y[i]),probability=prob,prediction=pred))
                signal.append(dict(task_id=task,fold=j["fold"],source=source,split=split_evidence,
                    predictions=predictions,**answer))
        write(dest/"signal.json",signal)
    write(dest/"complete.json",dict(task=task,plan=ref(out/"plan.json"),redundancy_results=len(results),
        signal_results=len(signal),seconds=time.monotonic()-start,
        artifacts=[ref(p) for p in sorted(dest.glob("*.json")) if p.name not in ("started.json","complete.json")]))
    print(task,"probes complete",round(time.monotonic()-start,2),flush=True)


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",default=str(OUT));ap.add_argument("--task",required=True)
    args=ap.parse_args();run(args.out,args.task)
