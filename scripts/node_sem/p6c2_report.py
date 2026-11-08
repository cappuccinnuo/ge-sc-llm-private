"""NS-P6c2 reporting only, using sealed CPU results and prior evidence."""
import argparse
from collections import defaultdict, Counter
import csv
import json
from pathlib import Path
import statistics
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from .p6c_core import distribution
from .p6c2_run import load, OUT, OLD

SOURCES = ("code", "ctx", "kind_syntax")


def csv_out(path, rows):
    if not rows:
        raise ValueError("Empty report table")
    with Path(path).open("x",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def bit_summary(rows):
    groups=defaultdict(list)
    seen=set()
    for r in rows:
        key=(r["task_id"],r["fold"],r["source"],r["column"]["index"])
        if key in seen:raise ValueError("Duplicate probe identity")
        seen.add(key);groups[(key[0],key[2],key[3])].append(r)
    result=[]
    for (task,source,index),rs in sorted(groups.items()):
        auc=[r["auc"] for r in rs if r.get("auc") is not None]
        ba=[r["balanced_accuracy"] for r in rs if r.get("balanced_accuracy") is not None]
        result.append(dict(task_id=task,source=source,index=index,column=rs[0]["column"],
            total_folds=len(rs),valid_folds=len(auc),auc=distribution(auc),balanced_accuracy=distribution(ba),
            high_auc=bool(auc) and statistics.mean(auc)>=.95))
    return result


def grouped(bits):
    result=[]
    for task in sorted(set(r["task_id"] for r in bits)):
        for source in sorted(set(r["source"] for r in bits if r["task_id"]==task)):
            taskbits=[r for r in bits if r["task_id"]==task and r["source"]==source]
            groups=[("all","ALL")]+[("parent",g) for g in "ABCDEFGHIJKLMN"]
            groups += [("atomic",g) for g in sorted(set(r["column"]["group"] for r in taskbits))]
            for level,g in groups:
                selected=[r for r in taskbits if level=="all" or r["column"]["parent_group" if level=="parent" else "group"]==g]
                valid=[r for r in selected if r["valid_folds"]]
                high=sum(r["high_auc"] for r in valid)
                result.append(dict(task_id=task,source=source,level=level,group=g,
                    eligible_bits=len(selected),estimable_bits=len(valid),high_auc_bits=high,
                    high_auc_fraction_estimable=high/len(valid) if valid else None,
                    high_auc_fraction_eligible=high/len(selected) if selected else None,
                    median_fold_mean_auc=statistics.median(r["auc"]["mean"] for r in valid) if valid else None,
                    all_folds_estimable_bits=sum(r["valid_folds"]==r["total_folds"] for r in valid)))
    return result


def pair_rows(new, other, comparison, source):
    other_map={(r["task_id"],r["fold"],r["column"]["index"]):r for r in other if r["source"]==source}
    out=[]
    for r in new:
        if r["source"]!="code":continue
        key=(r["task_id"],r["fold"],r["column"]["index"]);b=other_map.get(key)
        a=r.get("auc");c=b.get("auc") if b else None
        out.append(dict(task_id=key[0],fold=key[1],index=key[2],group=r["column"]["group"],
            parent_group=r["column"]["parent_group"],comparison=comparison,
            code_auc=a,reference_auc=c,auc_delta=None if a is None or c is None else a-c,
            code_status=r["status"],reference_status=b["status"] if b else "ineligible_in_reference"))
    return out


def build(out=OUT):
    out=Path(out);plan=load(out)
    done=read(out/"computation_complete.json")
    if done["passed"] is not True or done["folds"]!=30 or done["plan"]!=ref(out/"plan.json"):
        raise ValueError("Incomplete or mixed computation")
    if (out/"report.json").exists():raise FileExistsError("Report exists")
    new=[];signal=[];receipts=[];populations={}
    for task,t in plan["tasks"].items():
        pop=read(checked(t["population"]));populations[task]=pop
        eligible={c["index"] for c in pop["columns"] if c["eligible"]}
        for j in t["folds"]:
            d=out/"folds"/(task+"__"+str(j["fold"]))
            receipt=read(d/"receipt.json");value=read(checked(receipt["result"]))
            if receipt["passed"] is not True or receipt["plan"]!=ref(out/"plan.json"):
                raise ValueError("Wrong receipt")
            if value["split_sha256"]!=j["split_sha256"]:
                raise ValueError("Changed folds")
            rows=value["redundancy"];keys=[(r["source"],r["column"]["index"]) for r in rows]
            if len(keys)!=len(set(keys)) or set(keys)!={(s,i) for s in SOURCES for i in eligible}:
                raise ValueError("Missing/duplicated probe population")
            if any(r["task_id"]!=task or r["fold"]!=j["fold"] for r in rows+value["signal"]):
                raise ValueError("Mixed task/fold rows")
            if task.endswith("_node") and {r["source"] for r in value["signal"]}!={"code","static","code_static"}:
                raise ValueError("Missing signal input")
            new+=rows;signal+=value["signal"];receipts.append(ref(d/"receipt.json"))
    old=[]
    inventory={r["path"]:r for r in read(checked(plan["old_inventory"]))["files"]}
    for task in plan["tasks"]:
        for p in sorted((OLD/"probes"/task).glob("redundancy_fold_*.json")):
            old+=read(checked(inventory[str(p)]))["results"]
    old_signal=read(checked(inventory[str(OLD/"signal_results.json")]))
    oldbits=bit_summary(old);bits=bit_summary(new)
    oldgroups=grouped(oldbits);groups=grouped(bits)
    lookup={(r["task_id"],r["source"],r["level"],r["group"]):r for r in oldgroups}
    comparison=[]
    for r in groups:
        if r["source"]=="kind_syntax":continue
        previous=lookup.get((r["task_id"],r["source"],r["level"],r["group"]),{})
        comparison.append(dict(task_id=r["task_id"],source=r["source"],level=r["level"],group=r["group"],
            old_eligible=previous.get("eligible_bits",0),new_eligible=r["eligible_bits"],
            old_estimable=previous.get("estimable_bits",0),new_estimable=r["estimable_bits"],
            old_high=previous.get("high_auc_bits",0),new_high=r["high_auc_bits"],
            old_fraction=previous.get("high_auc_fraction_estimable"),
            new_fraction=r["high_auc_fraction_estimable"],
            old_median_auc=previous.get("median_fold_mean_auc"),new_median_auc=r["median_fold_mean_auc"]))
    pairs=pair_rows(new,new,"CODE minus kind/syntax", "kind_syntax")+pair_rows(new,old,"applicable CODE minus all-row CODE","code")
    pairgroups=[]
    for task in plan["tasks"]:
        for comparison_name in sorted(set(r["comparison"] for r in pairs)):
            for g in ["ALL"]+list("ABCDEFGHIJKLMN"):
                r=[r for r in pairs if r["task_id"]==task and r["comparison"]==comparison_name and (g=="ALL" or r["parent_group"]==g)]
                perbit=defaultdict(list)
                for x in r:
                    if x["auc_delta"] is not None:perbit[x["index"]].append(x["auc_delta"])
                means=[statistics.mean(v) for v in perbit.values()]
                pairgroups.append(dict(task_id=task,comparison=comparison_name,group=g,paired_bits=len(perbit),
                    paired_bit_folds=sum(map(len,perbit.values())),median_bit_mean_auc_delta=statistics.median(means) if means else None,
                    mean_bit_mean_auc_delta=statistics.mean(means) if means else None))
    signal_summary=[];signal_pairs=[]
    for task in ("reentrancy_node","access_control_node"):
        for view,records in (("all_nodes",old_signal),("statement_condition",signal)):
            for source in ("code","static","code_static"):
                rs=[r for r in records if r["task_id"]==task and r["source"]==source]
                auc=[r["auc"] for r in rs if r.get("auc") is not None]
                bf=[100*r["buggy_f1"] for r in rs if r.get("buggy_f1") is not None]
                signal_summary.append(dict(task_id=task,view=view,source=source,total_folds=len(rs),auc_folds=len(auc),
                    mean_auc=statistics.mean(auc) if auc else None,BF1_folds=len(bf),mean_BF1=statistics.mean(bf) if bf else None))
            for fold in range(10):
                rs={r["source"]:r for r in records if r["task_id"]==task and r["fold"]==fold}
                for name in ("static","code_static"):
                    a,b=rs[name],rs["code"]
                    signal_pairs.append(dict(task_id=task,view=view,fold=fold,comparison=name+" minus code",
                        auc_delta=a["auc"]-b["auc"] if a.get("auc") is not None and b.get("auc") is not None else None,
                        BF1_delta_pp=100*(a["buggy_f1"]-b["buggy_f1"]) if a.get("buggy_f1") is not None and b.get("buggy_f1") is not None else None))
    for name,rows in (("groups",groups),("old_new",comparison),("paired_groups",pairgroups),
        ("paired_fold_bits",pairs),("signal_summary",signal_summary),("signal_paired",signal_pairs)):
        csv_out(out/(name+".csv"),rows)
    write(out/"bits.json",bits);write(out/"signal_results.json",signal)
    fits=sum(len(r.get("candidates",[])) for r in new+signal)
    result=dict(passed=True,plan=ref(out/"plan.json"),folds=30,probe_results=len(new),signal_results=len(signal),accepted_logistic_fits=fits,
        groups=groups,old_new=comparison,paired_groups=pairgroups,signal_summary=signal_summary,signal_paired=signal_pairs,
        positive_distributions={t:v["signal"] for t,v in populations.items() if "signal" in v},
        status_counts=dict(Counter(r["status"] for r in new)),receipts=receipts,
        HGT_models_loaded=0,HGT_fits=0,GPU_used=False,
        limitations=["Task-wide unlabelled applicable prevalence screening is transductive.",
            "CTX derived from same facts: encoding fidelity only.",
            "J syntax targets occur in the control input; high control AUC is tautological.",
            "N targets analysis support; they are not vulnerability facts.",
            "High linear predictability is not a causal claim; low AUC is not proof of absent nonlinear information.",
            "Different eligible bit sets require paired-bit/fold comparison as well as own-population summaries.",
            "Small non-SolidiFI subsets; undefined folds retained; no significance tests."])
    write(out/"report.json",result)
    artifacts=[ref(p) for p in sorted(out.glob("*.csv"))]+[ref(out/"bits.json"),ref(out/"signal_results.json")]
    write(out/"result.seal.json",dict(report=ref(out/"report.json"),artifacts=artifacts))
    return result


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",default=str(OUT));args=ap.parse_args();build(args.out)
