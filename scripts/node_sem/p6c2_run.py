"""NS-P6c2 sealed CPU schedule. No graph/model construction or torch.load."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import numpy as np
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.experiments.common import digest
from .p6c_core import logistic_probe, split_indices, C_GRID
from .p6c2_core import aligned_kinds, controls, population, redundancy_one, signal_population
from .facts_schema import NODE_KINDS

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "scripts/node_sem/artifacts/ns_p6c"
OUT = ROOT / "scripts/node_sem/artifacts/ns_p6c2"
SOURCES = ("p6c2_core.py", "p6c2_run.py", "p6c_core.py", "facts_schema.py",
           "behavior_schema.json")


def prepare(out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    old = read(checked(read(OLD / "plan.seal.json")["plan"]))
    done = read(OLD / "complete.json")
    if not done["passed"]:
        raise ValueError("Old batch incomplete")
    checked(done["report"])
    rev = read(checked(read(OLD / "cpu_parallel_revision/seal.json")["revision"]))
    checked(rev["source"])
    for r in old["runtime"].values():
        checked(r)
    schema = read(checked(old["schema"]))
    tasks = {}
    for task, cached in rev["tasks"].items():
        meta = read(checked(cached["rows"]))
        arrays = {n: np.load(str(checked(r)), mmap_mode="r", allow_pickle=False)
                  for n, r in cached["arrays"].items()}
        rows = meta["rows"]
        presence = {n: np.asarray(v, dtype=bool) for n, v in meta["presence"].items()}
        jobs = meta["jobs"]
        carrier = read(checked(jobs[0]["feature_view"]))
        static_ref = carrier["modalities"]["static"]
        static_manifest = read(checked(static_ref))
        facts_ref = static_manifest["input_text"]
        facts = [json.loads(l) for l in checked(facts_ref).read_text(encoding="utf8").splitlines()]
        if facts_ref != static_manifest["accepted"]["proof"]["facts"]:
            raise ValueError("Unaccepted facts")
        checked(static_manifest["accepted"]["proof"]["seal"])
        checked(static_manifest["implementation"]["scripts/node_sem/behavior_schema.json"])
        if static_manifest["implementation"]["scripts/node_sem/behavior_schema.json"] != old["schema"]:
            raise ValueError("Different schema")
        kinds = aligned_kinds(rows, static_manifest["rows"], facts)
        by_fact = {r["row_key"]: r["facts"] for r in facts}
        syntax = next(f for f in schema["fields"] if f["name"] == "syntax")
        for i, row in enumerate(rows):
            expected = np.asarray([v in by_fact[row["row_key"]]["syntax"] for v in syntax["values"]])
            if not np.array_equal(expected, arrays["static"][i, syntax["start"]:syntax["stop"]]):
                raise ValueError("Syntax/frozen feature mismatch")
        control, control_names = controls(kinds, arrays["static"], schema)
        cols = population(kinds, arrays["static"], presence, schema)
        d = out / "prepared" / task
        d.mkdir(parents=True)
        write(d / "kinds.json", kinds.tolist())
        np.save(str(d / "control.npy"), control, allow_pickle=False)
        # Exact file-level fold membership and all row identities remain in the old read-only cache.
        jobrefs = []
        for j in jobs:
            checked(j["folds"])
            jobrefs.append(dict(fold=j["fold"], split_sha256=digest(j["split"]), folds=j["folds"]))
        evidence = dict(task_id=task, total_rows=len(rows),
            kinds=dict(Counter(kinds)), columns=cols,
            control_columns=control_names, control_is_target_for_syntax_group=True,
            population="schema.applicable intersect CODE/STATIC presence",
            eligibility_scope="whole-task unlabelled applicable population")
        if task.endswith("_node"):
            label_ref = jobs[0]["label_view"]
            labels = read(checked(label_ref))[task]
            y, base, selected, counts = signal_population(rows, kinds, presence, labels)
            if int(y[base].sum()) != (32 if task == "reentrancy_node" else 20):
                raise ValueError("Non-SolidiFI positive count changed")
            evidence["signal"] = dict(original_positive_kinds=counts,
                all_n=int(base.sum()), statement_condition_n=int(selected.sum()),
                statement_condition_positive=int(y[selected].sum()),
                positive_hcg_node_types=dict(Counter(r["node_type"] for i,r in enumerate(rows) if base[i] and y[i])),
                labels=label_ref)
        write(d / "population.json", evidence)
        tasks[task] = dict(cache=cached, kinds=ref(d/"kinds.json"),
            control=ref(d/"control.npy"), population=ref(d/"population.json"),
            facts=facts_ref, static_manifest=static_ref, carrier=jobs[0]["feature_view"], folds=jobrefs)
    prefixes = {n: dict(bytes=(ROOT/n).stat().st_size, sha256=ref(ROOT/n)["sha256"])
        for n in ("HANDOVER.md", "docs/training_changes_2026-10-07.md", "scripts/node_sem/PROGRESS.md")}
    write(out/"doc_prefixes.json", prefixes)
    plan = dict(version="nodesem-p6c2-applicable-v1",
        head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT),universal_newlines=True).strip(),
        old_plan=ref(OLD/"plan.json"), old_seal=ref(OLD/"plan.seal.json"),
        old_complete=ref(OLD/"complete.json"), old_report=ref(OLD/"report.json"),
        old_inventory=ref(OLD/"artifact_inventory.json"), old_cpu_revision=ref(OLD/"cpu_parallel_revision/revision.json"),
        schema=old["schema"], tasks=tasks, sources={n:ref(Path(__file__).parent/n) for n in SOURCES},
        methods=dict(C_grid=list(C_GRID),seed=1,solver="unchanged p6c_core.logistic_probe",
            HGT_models_loaded=0,GPU_used=False,workers=12,no_automatic_retry=True,
            control="facts.node_kind one-hot plus frozen syntax bits; no names, labels, or other STATIC fields",
            ctx_interpretation="facts-derived encoding fidelity; not independent redundancy evidence",
            signal="original non-SolidiFI labels; additional statement/condition-only view",
            aggregation="equal fold means over estimable folds, counts and missingness retained",
            old_new_comparison="own eligible populations plus matched bit/fold comparisons; no causal claim"))
    write(out/"plan.json",plan)
    write(out/"plan.seal.json",dict(plan=ref(out/"plan.json")))
    print("Prepared", {t:sum(c["eligible"] for c in read(v["population"]["path"])["columns"])
                       for t,v in tasks.items()},flush=True)


def load(out=OUT):
    out=Path(out);plan=read(checked(read(out/"plan.seal.json")["plan"]))
    for r in plan["sources"].values():
        checked(r)
    for k in ("old_plan","old_seal","old_complete","old_report","old_inventory","old_cpu_revision","schema"):
        checked(plan[k])
    return plan


def task_data(plan, task):
    d=plan["tasks"][task];cache=d["cache"]
    meta=read(checked(cache["rows"]))
    parts={n:np.load(str(checked(r)),allow_pickle=False,mmap_mode="r") for n,r in cache["arrays"].items()}
    presence={n:np.asarray(v,dtype=bool) for n,v in meta["presence"].items()}
    kinds=np.asarray(read(checked(d["kinds"])))
    control=np.load(str(checked(d["control"])),allow_pickle=False,mmap_mode="r")
    pop=read(checked(d["population"]))
    return meta,parts,presence,kinds,control,pop


def fit_fold(out,task,fold):
    out=Path(out);plan=load(out);d=out/"folds"/(task+"__"+str(fold))
    d.mkdir(parents=True,exist_ok=False)
    write(d/"started.json",dict(plan=ref(out/"plan.json"),task=task,fold=fold,pid=os.getpid(),time=time.time()))
    try:
        meta,parts,presence,kinds,control,pop=task_data(plan,task)
        jobs=[j for j in meta["jobs"] if j["fold"]==fold]
        if len(jobs)!=1:raise ValueError("Wrong fold")
        j=jobs[0];rows=meta["rows"];results=[];split_proofs={}
        for number,col in enumerate(c for c in pop["columns"] if c["eligible"]):
            answers,ix=redundancy_one(parts,rows,kinds,presence,col,j["split"],control)
            key="|".join(col["applicable"])
            proof={r:dict(n=len(idx),row_sha256=digest([rows[int(i)]["row_key"] for i in idx])) for r,idx in ix.items()}
            if key in split_proofs and proof!=split_proofs[key]:raise ValueError("Unequal same-population splits")
            split_proofs[key]=proof
            for source,value in answers.items():
                results.append(dict(task_id=task,fold=fold,source=source,column=col,**value))
            if number%20==0:print(task,fold,"column",number,flush=True)
        signal=[]
        if task.endswith("_node"):
            labels=read(checked(pop["signal"]["labels"]))[task]
            y,base,selected,_=signal_population(rows,kinds,presence,labels)
            ix=split_indices([r["file"] for r in rows],j["split"],selected)
            labeltable={(r["file"],r["original_graph_node_id"]):r for r in labels}
            for source,x in (("code",parts["code"]),("static",parts["static"]),
                    ("code_static",np.concatenate((parts["code"],parts["static"]),axis=1))):
                value=logistic_probe(x,y,ix,select_threshold=True)
                predictions=[]
                for i,prob,cls in zip(ix["outer_test"],value.pop("probabilities",[]),value.pop("predictions",[])):
                    r=rows[int(i)];label=labeltable[(r["file"],r["original_graph_node_id"])]
                    predictions.append(dict(file=r["file"],node_id=r["original_graph_node_id"],
                        source_sha256=label["source_sha256"],node_kind=str(kinds[i]),
                        target=int(y[i]),probability=prob,prediction=cls))
                signal.append(dict(task_id=task,fold=fold,source=source,predictions=predictions,**value))
        value=dict(task_id=task,fold=fold,plan=ref(out/"plan.json"),split_sha256=digest(j["split"]),
            redundancy=results,signal=signal,splits=split_proofs)
        write(d/"result.json",value);write(d/"receipt.json",dict(passed=True,result=ref(d/"result.json"),
            plan=ref(out/"plan.json")))
    except Exception:
        write(d/"failure.json",dict(error=traceback.format_exc()))
        raise


def run(out=OUT):
    out=Path(out);plan=load(out)
    lock=out/"controller.started.json";write(lock,dict(pid=os.getpid(),plan=ref(out/"plan.json"),time=time.time()))
    queue=[(task,j["fold"]) for task,d in plan["tasks"].items() for j in d["folds"]]
    active=[];completed=[]
    while queue or active:
        while queue and len(active)<plan["methods"]["workers"]:
            task,fold=queue.pop(0);logs=out/"logs";logs.mkdir(exist_ok=True)
            stream=(logs/(task+"__"+str(fold)+".log")).open("x")
            proc=subprocess.Popen([sys.executable,"-B","-u","-m","scripts.node_sem.p6c2_run",
                "fold","--out",str(out),"--task",task,"--fold",str(fold)],
                stdout=stream,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES=""))
            active.append((proc,stream,task,fold))
        for proc,stream,task,fold in list(active):
            if proc.poll() is None:continue
            stream.close();active.remove((proc,stream,task,fold))
            if proc.returncode:
                write(out/"failure.json",dict(task=task,fold=fold,exit_code=proc.returncode))
                for other,_,_,_ in active:other.terminate()
                raise RuntimeError("CPU probe failure; no automatic retry")
            receipt=read(out/"folds"/(task+"__"+str(fold))/"receipt.json");checked(receipt["result"])
            completed.append((task,fold));print("complete",len(completed),task,fold,flush=True)
        (out/"progress.json").write_text(json.dumps(dict(active=[(t,f) for _,_,t,f in active],
            queued=len(queue),completed=completed)),encoding="utf8")
        time.sleep(2)
    write(out/"computation_complete.json",dict(passed=True,folds=len(completed),plan=ref(out/"plan.json")))


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("command",choices=["prepare","run","fold"])
    ap.add_argument("--out",default=str(OUT));ap.add_argument("--task");ap.add_argument("--fold",type=int)
    a=ap.parse_args()
    if a.command=="prepare":prepare(a.out)
    elif a.command=="run":run(a.out)
    else:fit_fold(a.out,a.task,a.fold)
