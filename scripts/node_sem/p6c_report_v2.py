# Report-only correction copied from scripts/node_sem/p6c_report.py
# Original source SHA256: d30884e187aecc0d4ff11f617afd699b64dd45deee70cfa58db365044a682ef0
# Only explicit merging of the shared, equal sample count differs.
"""Compact per-fold NS-P6c reporting; never rewrite historical results."""
from collections import defaultdict
from pathlib import Path
import argparse
import statistics
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.benchmark_v2.reporting import csv_write
from scripts.DFG.experiments.common import metrics
from .p6c_run import load, OUT, worker
from .p6c_core import distribution


def changes(full,other,kind):
    key=lambda r:(r["file"],r.get("original_graph_node_id")) if kind=="node" else (r["file"],)
    a={key(r):r for r in full};b={key(r):r for r in other}
    if len(a)!=len(full) or len(b)!=len(other) or set(a)!=set(b): raise ValueError("Prediction identities differ")
    for k in a:
        if any(a[k][f]!=b[k][f] for f in ("target","source_sha256","cohort")): raise ValueError("Target/source changed")
    changed=sum(a[k]["prediction"]!=b[k]["prediction"] for k in a)
    positives=[k for k in a if a[k]["cohort"]=="nonSolidiFI" and a[k]["target"]==1]
    return dict(n=len(a),changed=changed,changed_fraction=changed/len(a),
        probability_MAE=statistics.mean(abs(a[k]["probability"]-b[k]["probability"]) for k in a),
        nonSolidifi_positive_n=len(positives),
        nonSolidifi_positive_changed=sum(a[k]["prediction"]!=b[k]["prediction"] for k in positives),
        corrected=sum(a[k]["prediction"]!=a[k]["target"] and b[k]["prediction"]==b[k]["target"] for k in a),
        new_error=sum(a[k]["prediction"]==a[k]["target"] and b[k]["prediction"]!=b[k]["target"] for k in a))


def merged_fold_row(job,condition,score,delta):
    if score.get("n")!=delta.get("n"):
        raise ValueError("Metric and identity sample counts differ")
    overlap=(set(score)&set(delta))-{ "n" }
    if overlap:
        raise ValueError("Unexpected overlapping report keys")
    row=dict(task_id=job["task_id"],fold=job["fold"],name=job["name"],condition=condition)
    row.update(score)
    row.update(delta)
    return row


def build(out=OUT):
    out=Path(out);plan=load(out)
    if (out/"report.json").exists():raise FileExistsError("Report already exists")
    folds=[];contrib=[];special=[];refs=[];model_contrib=[];groups=defaultdict(list)
    for e in plan["jobs"]:
        job=e["job"];path=out/"eval"/worker.job_id(job)/"receipt.json";receipt=read(path)
        v=read(checked(receipt["result"]));refs.append(ref(path))
        if not receipt["passed"] or v["parameter_digest_before"]!=v["parameter_digest_after"] or v["optimizer_steps"]!=0:
            raise ValueError("Model diagnostic not accepted")
        if v["plan"]!=ref(out/"plan.json") or v["checkpoint"]!=e["best"]:raise ValueError("Mixed eval batch")
        for condition,rows in v["conditions"].items():
            score=metrics([r["target"] for r in rows],[r["prediction"] for r in rows])
            delta=changes(v["conditions"]["full"],rows,job["granularity"])
            row=merged_fold_row(job,condition,score,delta)
            if condition=="code_only":
                row["no_observed_classification_sensitivity"]=(delta["changed_fraction"]<.001 and delta["nonSolidifi_positive_changed"]==0)
            folds.append(row)
            groups[(job["task_id"],condition)].append(row)
        for r in v["contributions"]:
            contrib.append(dict(task_id=job["task_id"],fold=job["fold"],model="S4g",**r))
        for name,r in v["aggregate_contributions"].items():
            model_contrib.append(dict(task_id=job["task_id"],fold=job["fold"],modality=name,**r))
        if job["granularity"]=="node":
            full=v["conditions"]["full"]
            for i,r in enumerate(full):
                condition_rows={c:rr[i] for c,rr in v["conditions"].items()}
                if any((x["file"],x["original_graph_node_id"])!=(r["file"],r["original_graph_node_id"]) for x in condition_rows.values()):
                    raise ValueError("Diagnostic row order changed")
                if r["cohort"]=="nonSolidiFI" and (r["target"]==1 or any(x["prediction"]==1 for x in condition_rows.values())):
                    special.append(dict(task_id=job["task_id"],fold=job["fold"],**r,
                        conditions={c:dict(prediction=x["prediction"],probability=x["probability"]) for c,x in condition_rows.items()}))
    aggregate=[]
    for (task,condition),rows in sorted(groups.items()):
        aggregate.append(dict(task_id=task,condition=condition,folds=len(rows),
            **{k:distribution([r[k] for r in rows]) for k in ("buggy_f1","macro_f1","changed_fraction","probability_MAE")},
            total_changed=sum(r["changed"] for r in rows),total_n=sum(r["n"] for r in rows),
            positive_changed=sum(r["nonSolidifi_positive_changed"] for r in rows)))
    effective=[]
    for task in sorted(set(r["task_id"] for r in model_contrib)):
        for modality in ("code","ctx","static"):
            rows=[r for r in model_contrib if r["task_id"]==task and r["modality"]==modality]
            effective.append(dict(task_id=task,modality=modality,
                **{k:distribution([r[k]["mean"] for r in rows if r[k]["mean"] is not None]) for k in ("gate","effective","share")}))
    redundancy=[];signal=[];eligibility=[]
    for task in sorted(set(e["job"]["task_id"] for e in plan["jobs"])):
        d=out/"probes"/task;done=read(d/"complete.json")
        if done["plan"]!=ref(out/"plan.json"):raise ValueError("Mixed probe batch")
        for r in done["artifacts"]:checked(r)
        refs.append(ref(d/"complete.json"));pop=read(d/"population.json");eligibility.append(pop)
        for p in sorted(d.glob("redundancy_fold_*.json")):redundancy.extend(read(p)["results"])
        if (d/"signal.json").exists(): signal.extend(read(d/"signal.json"))
    bitgroups=defaultdict(list)
    for r in redundancy:bitgroups[(r["task_id"],r["source"],r["column"]["index"])].append(r)
    bits=[]
    for (task,source,index),rows in sorted(bitgroups.items()):
        vals=[r["auc"] for r in rows if r.get("auc") is not None]
        bits.append(dict(task_id=task,source=source,index=index,column=rows[0]["column"],
            valid_folds=len(vals),total_folds=len(rows),auc=distribution(vals),
            ba=distribution([r["balanced_accuracy"] for r in rows if r.get("balanced_accuracy") is not None]),
            high_auc=bool(vals) and statistics.mean(vals)>=.95,
            all_folds_estimable=len(vals)==len(rows)))
    grouped=[]
    for task in sorted(set(r["task_id"] for r in bits)):
        for source in ("code","ctx"):
            for group in ["ALL"]+list("ABCDEFGHIJKLMN"):
                rows=[r for r in bits if r["task_id"]==task and r["source"]==source and (group=="ALL" or r["column"]["parent_group"]==group)]
                valid=[r for r in rows if r["valid_folds"]>0]
                grouped.append(dict(task_id=task,source=source,group=group,eligible_bits=len(rows),
                    estimable_bits=len(valid),high_auc_bits=sum(r["high_auc"] for r in valid),
                    high_auc_fraction=sum(r["high_auc"] for r in valid)/len(valid) if valid else None,
                    all_folds_estimable_bits=sum(r["all_folds_estimable"] for r in valid)))
    paired=[]
    for task in sorted(set(r["task_id"] for r in signal)):
        for fold in sorted(set(r["fold"] for r in signal if r["task_id"]==task)):
            sides={r["source"]:r for r in signal if r["task_id"]==task and r["fold"]==fold}
            a,b=sides["code_static"],sides["code"]
            paired.append(dict(task_id=task,fold=fold,code_status=b["status"],combined_status=a["status"],
                auc_delta=None if a.get("auc") is None or b.get("auc") is None else a["auc"]-b["auc"],
                BF1_delta_pp=None if a.get("buggy_f1") is None or b.get("buggy_f1") is None else 100*(a["buggy_f1"]-b["buggy_f1"])))
    for task,expected in (("reentrancy_node",32),("access_control_node",20)):
        actual=sum(r["task_id"]==task and r["target"]==1 for r in special)
        if actual!=expected:raise ValueError("Special positive table incomplete")
    write(out/"contributions_by_type.json",contrib)
    write(out/"redundancy_bits.json",bits)
    write(out/"nonSolidifi_changes.json",special)
    csv_write(out/"removal_folds.csv",folds)
    csv_write(out/"redundancy_groups.csv",grouped)
    csv_write(out/"signal_paired.csv",paired)
    write(out/"signal_results.json",signal)
    report=dict(passed=True,plan=ref(out/"plan.json"),models=30,eval_forwards=120,
        new_HGT_fits=0,parameter_updates=0,S4="not_executed_missing_NA_weights",
        aggregate_removal=aggregate,effective_contributions=effective,redundancy_groups=grouped,
        signal_paired=paired,diagnostics=refs,
        limitations=plan["methods"])
    write(out/"report.json",report)
    write(out/"result.seal.json",dict(report=ref(out/"report.json"),
        artifacts=[ref(out/n) for n in ("contributions_by_type.json","redundancy_bits.json",
            "nonSolidifi_changes.json","removal_folds.csv","redundancy_groups.csv","signal_paired.csv","signal_results.json")]))
    return report


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",default=str(OUT));a=ap.parse_args();build(a.out)
