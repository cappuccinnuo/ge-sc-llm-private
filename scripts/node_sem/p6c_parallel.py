"""Approved CPU fold scheduling revision; same p6c_core.logistic_probe.
Input extraction delegates to p6c_probes.task_data. No fit algorithm changes.
Original serial attempts and their completed folds remain in place.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,write,ref,checked
from scripts.DFG.experiments.common import digest
from .p6c_run import load, OUT
from .p6c_probes import task_data
from .p6c_core import split_indices,logistic_probe


def prepare(out=OUT):
    out=Path(out);plan=load(out);rev=out/"cpu_parallel_revision"
    interrupt=read(rev/"interruption.json")
    for r in interrupt["prior_files"]:checked(r)
    if (rev/"revision.json").exists():raise FileExistsError("CPU revision already sealed")
    tasks={}
    for task in sorted(set(e["job"]["task_id"] for e in plan["jobs"])):
        jobs,rows,parts,presence=task_data(plan,task)
        d=rev/"cache"/task;d.mkdir(parents=True,exist_ok=False)
        refs={}
        for name,x in parts.items():
            np.save(str(d/(name+".npy")),x,allow_pickle=False)
            disk=np.load(str(d/(name+".npy")),allow_pickle=False)
            if not np.array_equal(x,disk):raise ValueError("Cache changed features")
            refs[name]=ref(d/(name+".npy"))
        metadata=dict(rows=rows,presence={n:a.tolist() for n,a in presence.items()},jobs=jobs)
        write(d/"rows.json",metadata)
        tasks[task]=dict(arrays=refs,rows=ref(d/"rows.json"),
            population=ref(out/"probes"/task/"population.json"))
    value=dict(plan=ref(out/"plan.json"),approval=ref(rev/"interruption.json"),
        source=ref(Path(__file__)),tasks=tasks,old_runtime_unchanged=plan["runtime"],
        compute="p6c_core.logistic_probe unchanged; arrays byte-exact; folds unchanged",
        max_workers_while_gpu_active=6,max_workers_after_gpu=12,
        no_automatic_retry=True)
    write(rev/"revision.json",value);write(rev/"seal.json",dict(revision=ref(rev/"revision.json")))


def cached(out,task):
    out=Path(out);load(out);rev=out/"cpu_parallel_revision"
    value=read(checked(read(rev/"seal.json")["revision"]))
    checked(value["source"]);d=value["tasks"][task]
    meta=read(checked(d["rows"]))
    arrays={n:np.load(str(checked(r)),allow_pickle=False,mmap_mode="r") for n,r in d["arrays"].items()}
    presence={n:np.asarray(p,dtype=bool) for n,p in meta["presence"].items()}
    return meta,arrays,presence,read(checked(d["population"]))


def compute_fold(meta,parts,presence,pop,fold):
    jobs=[j for j in meta["jobs"] if j["fold"]==fold]
    if len(jobs)!=1:raise ValueError("Bad fold")
    j=jobs[0];rows=meta["rows"];files=[r["file"] for r in rows];counts={};results=[]
    for source in ("code","ctx"):
        ix=split_indices(files,j["split"],presence[source]&presence["static"])
        counts[source]={r:dict(n=len(idx),row_sha256=digest([rows[int(i)]["row_key"] for i in idx]),
            files=sorted(set(files[int(i)] for i in idx))) for r,idx in ix.items()}
        for number,col in enumerate(pop["eligible"]):
            a=logistic_probe(parts[source],parts["static"][:,col["index"]],ix)
            a.pop("probabilities",None);a.pop("predictions",None)
            results.append(dict(task_id=j["task_id"],fold=fold,source=source,column=col,**a))
            if number%20==0:print(j["task_id"],fold,source,number,flush=True)
    return dict(results=results,splits=counts,fold_ref=j["folds"],split_sha256=digest(j["split"]))


def run_fold(out,task,fold):
    out=Path(out);rev=out/"cpu_parallel_revision";dest=rev/"jobs"/(task+"__"+str(fold))
    dest.mkdir(parents=True,exist_ok=False)
    write(dest/"started.json",dict(task=task,fold=fold,time=time.time(),pid=os.getpid(),revision=ref(rev/"revision.json")))
    target=out/"probes"/task/("redundancy_fold_%d.json"%fold)
    if target.exists():raise FileExistsError("Successful fold must not be repeated")
    meta,parts,presence,pop=cached(out,task)
    result=compute_fold(meta,parts,presence,pop,fold)
    write(target,result);write(dest/"receipt.json",dict(result=ref(target),revision=ref(rev/"revision.json"),passed=True))


def signal(out,task):
    out=Path(out);meta,parts,presence,pop=cached(out,task)
    jobs=meta["jobs"];rows=meta["rows"];files=[r["file"] for r in rows]
    labels=read(checked(jobs[0]["label_view"]))[task];table={(r["file"],r["original_graph_node_id"]):r for r in labels}
    y=np.zeros(len(rows),dtype=int);usable=np.zeros(len(rows),dtype=bool)
    for i,r in enumerate(rows):
        label=table.get((r["file"],r["original_graph_node_id"]))
        if label is None:continue
        if label["node_type"]!=r["node_type"]:raise ValueError("Wrong label type")
        y[i]=label["L-audit_target"]
        usable[i]=(label["L-audit_include"] and not Path(r["file"]).name.startswith("buggy_")
            and presence["code"][i] and presence["static"][i])
    if y[usable].sum()!=(32 if task=="reentrancy_node" else 20):raise ValueError("Wrong positives")
    results=[]
    for j in jobs:
        ix=split_indices(files,j["split"],usable)
        evidence={r:dict(n=len(idx),positive=int(y[idx].sum()),
            row_sha256=digest([rows[int(i)]["row_key"] for i in idx]),
            files=sorted(set(files[int(i)] for i in idx))) for r,idx in ix.items()}
        for source,x in (("code",parts["code"]),("static",parts["static"]),
            ("code_static",np.concatenate((parts["code"],parts["static"]),axis=1))):
            a=logistic_probe(x,y,ix,select_threshold=True);pred=[]
            for i,prob,cls in zip(ix["outer_test"],a.pop("probabilities",[]),a.pop("predictions",[])):
                r=rows[int(i)];label=table[(r["file"],r["original_graph_node_id"])]
                pred.append(dict(file=r["file"],original_graph_node_id=r["original_graph_node_id"],
                    source_sha256=label["source_sha256"],target=int(y[i]),probability=prob,prediction=cls))
            results.append(dict(task_id=task,fold=j["fold"],source=source,split=evidence,predictions=pred,**a))
    return results


def controller(out=OUT):
    out=Path(out);rev=out/"cpu_parallel_revision";plan=load(out);revision=read(checked(read(rev/"seal.json")["revision"]))
    checked(revision["source"])
    queue=[]
    preserved={r["path"]:r for r in read(checked(revision["approval"]))["prior_files"]}
    for e in plan["jobs"]:
        j=e["job"];p=out/"probes"/j["task_id"]/("redundancy_fold_%d.json"%j["fold"])
        if p.exists():
            if str(p) not in preserved:raise ValueError("Unreceipted preexisting fold")
            checked(preserved[str(p)])
        else:queue.append((j["task_id"],j["fold"]))
    active=[];completed=[]
    while queue or active:
        gpu=read(out/"eval_progress.json")["state"]
        limit=revision["max_workers_after_gpu"] if gpu=="complete" else revision["max_workers_while_gpu_active"]
        while queue and len(active)<limit:
            task,fold=queue.pop(0);log=rev/(task+"__"+str(fold)+".log")
            if log.exists():raise FileExistsError("Prior attempt exists")
            stream=log.open("x")
            process=subprocess.Popen([sys.executable,"-B","-u","-m","scripts.node_sem.p6c_parallel",
                "fold","--out",str(out),"--task",task,"--fold",str(fold)],stdout=stream,stderr=subprocess.STDOUT,
                env=dict(os.environ,CUDA_VISIBLE_DEVICES=""))
            active.append((process,stream,task,fold))
        for proc,stream,task,fold in list(active):
            code=proc.poll()
            if code is None:continue
            stream.close();active.remove((proc,stream,task,fold))
            if code:
                write(rev/"failure.json",dict(task=task,fold=fold,exit=code))
                for other,_,_,_ in active:other.terminate()
                raise RuntimeError("Probe failed; no retry")
            receipt=read(rev/"jobs"/(task+"__"+str(fold))/"receipt.json")
            checked(receipt["result"]);completed.append((task,fold))
            print("completed",task,fold,"new",len(completed),flush=True)
        # This status is intentionally mutable; receipts and results are exclusive.
        (rev/"progress.json").write_text(__import__("json").dumps(dict(queued=len(queue),
            active=[(t,f) for _,_,t,f in active],completed=completed)),encoding="utf8")
        time.sleep(2)
    for task in revision["tasks"]:
        signal_count=0;d=out/"probes"/task
        if task.endswith("_node"):
            values=signal(out,task);write(d/"signal.json",values);signal_count=len(values)
        files=sorted(d.glob("redundancy_fold_*.json"))
        expected=sum(e["job"]["task_id"]==task for e in plan["jobs"])
        if len(files)!=expected:raise ValueError("Incomplete fold set")
        count=sum(len(read(p)["results"]) for p in files)
        write(d/"complete.json",dict(task=task,plan=ref(out/"plan.json"),redundancy_results=count,
            signal_results=signal_count,cpu_revision=ref(rev/"revision.json"),
            artifacts=[ref(p) for p in sorted(d.glob("*.json")) if p.name not in ("started.json","complete.json")]))
    write(rev/"complete.json",dict(passed=True,new_folds=len(completed),reused_folds=30-len(completed),
        revision=ref(rev/"revision.json")))


if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("command",choices=["prepare","run","fold"])
    a.add_argument("--out",default=str(OUT));a.add_argument("--task");a.add_argument("--fold",type=int)
    args=a.parse_args()
    if args.command=="prepare":prepare(args.out)
    elif args.command=="run":controller(args.out)
    else:run_fold(args.out,args.task,args.fold)
