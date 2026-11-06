"""N-B final-only descriptive reporting; frozen N-A metric readers reused.
No model selection, significance test, training or feature changes.
Readers reused from scripts/node_sem/reporting.py, SHA256:
9d5835c1bf98130ca2fabfc4626d0a76687d6837e83124489ccdcef7a4d901f0
"""
import argparse
import json
import statistics
import math
from collections import defaultdict
from pathlib import Path
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.benchmark_v2.reporting import scored, csv_write
from scripts.DFG.dfg_v2.experiment.stats import aggregate_metrics, validate_records, METRICS
from scripts.DFG.experiments.common import metrics
from . import batch_nb as nb, batch_nb_worker as worker
from .reporting import aligned_rows, identity, read_artifact
from .reporting import manifest_attempts as na_attempts


def manifest_attempts(root, plan):
    root = Path(root)
    done = read(root / "complete.json")
    if (done.get("passed") is not True or done.get("formal_fits") != 120
            or done["plan"] != ref(root / "plan.json") or len(done["receipts"]) != 120):
        raise ValueError("All 120 accepted fits required before N-B analysis")
    found = {}
    for reference in done["receipts"]:
        receipt = read(checked(reference))
        key = worker.job_id(receipt["job"])
        if key in found:
            raise ValueError("Duplicate N-B receipt")
        found[key] = (Path(reference["path"]).parent, receipt)
    if set(found) != {worker.job_id(j) for j in plan["jobs"]}:
        raise ValueError("N-B receipt matrix differs")
    for job in plan["jobs"]:
        directory, receipt = found[worker.job_id(job)]
        worker.verify_attempt(root, plan, job, directory, deep=False)
    nb.validate_device_comparisons(plan["jobs"],
        [dict(r["job"], actual_device=r["actual_device"]) for _, r in found.values()])
    return found


def comparison_specs(policy):
    result = []
    for left, lg, right, rg in policy["planned_comparisons"]:
        result.append(dict(left=lg+"/"+left, right=rg+"/"+right,
            provenance="historically_planned_descriptive",
            stratification_provenance="r19_posthoc_descriptive" if (left,right)==("S3","S2")
            else "planned_descriptive"))
    for left, right in policy["posthoc_comparisons"]:
        result.append(dict(left="G3R/"+left, right="G3R/"+right,
            provenance="r19_posthoc_descriptive", stratification_provenance="r19_posthoc_descriptive"))
    keys = [(r["left"],r["right"]) for r in result]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicated comparison")
    return result


def paired_descriptive(records, task, left, right, checkpoint):
    sides = []
    for profile in (left,right):
        selected = [r for r in records if r["task_id"]==task
                    and r["profile"]==profile and r["checkpoint"]==checkpoint]
        values = {(r["fold"],r["seed"]):r for r in selected}
        if len(values)!=len(selected) or not values:
            raise ValueError("Missing/duplicate paired metric identity")
        sides.append(values)
    if set(sides[0]) != set(sides[1]):
        raise ValueError("Different paired folds")
    rows = []
    for metric in METRICS:
        folds = [dict(fold=k[0],seed=k[1],left=sides[0][k]["metrics"][metric],
            right=sides[1][k]["metrics"][metric],
            delta_pp=sides[0][k]["metrics"][metric]-sides[1][k]["metrics"][metric])
            for k in sorted(sides[0])]
        delta = [r["delta_pp"] for r in folds]
        rows.append(dict(task_id=task,left=left,right=right,checkpoint=checkpoint,metric=metric,
            mean_delta_pp=statistics.mean(delta),
            sample_sd_delta_pp=statistics.stdev(delta) if len(delta)>1 else None,
            improved=sum(x>0 for x in delta),tied=sum(x==0 for x in delta),declined=sum(x<0 for x in delta),
            folds=folds,inferential=False,p_value=None))
    return rows


def score_or_empty(rows, checkpoint):
    if rows:
        return scored(rows,checkpoint)
    return dict(n=0,positive=0,tn=0,fp=0,fn=0,tp=0,precision_wilson95=None,
        recall_wilson95=None,status="empty_stratum_no_metric",**{m:None for m in METRICS})


def paired_rows(left, right, kind):
    a={identity(r,kind):r for r in left};b={identity(r,kind):r for r in right}
    if len(a)!=len(left) or len(b)!=len(right) or set(a)!=set(b):
        raise ValueError("Paired prediction identities differ")
    for key in sorted(a,key=repr):
        x,y=a[key],b[key]
        if any(x.get(f)!=y.get(f) for f in ("target","source_sha256","source_id","cohort")):
            raise ValueError("Paired source/label identity differs")
        for row in (x,y):
            for ck in ("best","last"):
                if row[ck] not in (0,1) or not math.isfinite(row[ck+"_positive_probability"]) or not 0<=row[ck+"_positive_probability"]<=1:
                    raise ValueError("Invalid prediction/probability")
        yield x,y


def build(root=worker.OUT):
    from .nb_diagnostics import check_analysis, verify as verify_diagnostics
    root=Path(root);check_analysis(root);verify_diagnostics(root)
    plan=nb.load(root/"plan.json",deep=False)
    worker.validate_execution(root,plan)
    entries=manifest_attempts(root,plan)
    na_plan=read(checked(plan["na_parent"]["plan"]))
    na_root=Path(checked(plan["na_parent"]["plan"])).parent
    old_entries=na_attempts(na_root,na_plan)
    entries.update(old_entries)
    jobs=na_plan["jobs"]+plan["jobs"]
    if len(jobs)!=360 or len({worker.job_id(j) for j in jobs})!=360:
        raise ValueError("Combined N-A/N-B job matrix differs")
    diagnostics=read(root/"diagnostics/complete.json")
    if not diagnostics.get("passed") or diagnostics.get("count")!=90 or diagnostics.get("gate_evals")!=30:
        raise ValueError("Complete N-B attention/gate diagnostics required")
    for r in diagnostics["artifacts"]:
        checked(r)
    labels=read(checked(jobs[0]["label_view"]))
    if any(j["label_view"]!=jobs[0]["label_view"] for j in jobs):
        raise ValueError("Mixed label view")
    out=root/"reports";out.mkdir(exist_ok=False)
    records=[];orig_records=[];fold_counts=[];resources=[];support=[];tables={};false_positives=[]
    for job in jobs:
        key=worker.job_id(job);entry=entries[key]
        main=aligned_rows(read_artifact(entry,"outer_test_predictions.json"),job,labels)
        original=aligned_rows(read_artifact(entry,"outer_test_orig_all_predictions.json"),job,labels,original=True)
        result=read_artifact(entry,"result.json")
        group=job["profile"]+"/"+job["name"]
        tables[(job["task_id"],group,job["fold"])]=main
        for ck in ("best","last"):
            ident=dict(task_id=job["task_id"],task_kind=job["granularity"],profile=group,
                       fold=job["fold"],seed=1,checkpoint=ck)
            score=scored(main,ck)
            if any(score[m]!=result["outer_test"][ck][m] for m in METRICS):
                raise ValueError("Independent score differs from trainer")
            records.append(dict(ident,metrics={m:score[m] for m in METRICS}))
            orig_records.append(dict(ident,metrics=metrics([r["target"] for r in original],[r[ck] for r in original])))
            fold_counts.append(dict(ident,**score))
        receipt=entry[1]
        resources.append(dict(job_id=key,task_id=job["task_id"],profile=job["profile"],name=job["name"],
            fold=job["fold"],best_epoch=result["best_epoch"],last_epoch=result["last_epoch"],
            parameters=result["parameter_count"],fit_seconds=result["seconds"],
            total_seconds=receipt["total_seconds"],actual_device=receipt["actual_device"],**receipt["resources"]))
        support.append(dict(job_id=key,support=job["support"],gradient=read_artifact(entry,"gradient_audit.json")))
    expected={(j["task_id"],j["profile"]+"/"+j["name"],j["fold"],j["seed"],ck)
        for j in jobs for ck in ("best","last")}
    records=validate_records(records,expected);orig_records=validate_records(orig_records,expected)
    aggregates=aggregate_metrics(records);orig_aggregates=aggregate_metrics(orig_records)
    paired=[];pooled=[];special=[];change_summary=[];file_changes=[];strata_comparisons=[]
    comparisons=comparison_specs(plan["statistics"])
    with (out/"prediction_changes.jsonl").open("x",encoding="utf8") as stream:
        for task,folds in nb.TASK_FOLDS:
            kind=task.rsplit("_",1)[-1]
            names=sorted({j["profile"]+"/"+j["name"] for j in jobs if j["task_id"]==task})
            groups={}
            for name in names:
                rows=[r for f in range(folds) for r in tables[(task,name,f)]]
                if len({identity(r,kind) for r in rows})!=len(rows):
                    raise ValueError("Repeated OOF sample across folds")
                groups[name]=rows
                for ck in ("best","last"):
                    for cohort in ("all","SolidiFI","nonSolidiFI"):
                        chosen=[r for r in rows if cohort=="all" or r["cohort"]==cohort]
                        pooled.append(dict(task_id=task,profile=name,checkpoint=ck,cohort=cohort,
                            **score_or_empty(chosen,ck)))
                    if kind=="node":
                        for row in rows:
                            if row["cohort"]=="nonSolidiFI" and row["target"]==1:
                                special.append(dict(task_id=task,profile=name,checkpoint=ck,
                                    **row,prediction=row[ck],probability=row[ck+"_positive_probability"]))
                            if row["cohort"]=="nonSolidiFI" and row["target"]==0 and row[ck]==1:
                                false_positives.append(dict(task_id=task,profile=name,checkpoint=ck,**row))
            for comp in comparisons:
                left,right=comp["left"],comp["right"]
                for ck in ("best","last"):
                    for value in paired_descriptive(records,task,left,right,ck):
                        paired.append(dict(value,**{k:v for k,v in comp.items() if k not in ("left","right")}))
                    counts=dict(samples=0,probability_changed=0,class_changed=0,probability_only=0,
                        corrected=0,new_error=0,absolute_probability_delta_sum=0.0,
                        maximum_absolute_probability_delta=0.0)
                    files=defaultdict(lambda:dict(samples=0,corrected=0,new_error=0,class_changed=0))
                    for x,y in paired_rows(groups[left],groups[right],kind):
                        delta=x[ck+"_positive_probability"]-y[ck+"_positive_probability"]
                        change=x[ck]!=y[ck]
                        corrected=x[ck]==x["target"] and y[ck]!=y["target"]
                        new_error=x[ck]!=x["target"] and y[ck]==y["target"]
                        counts["samples"]+=1;counts["probability_changed"]+=bool(delta)
                        counts["class_changed"]+=change;counts["probability_only"]+=bool(delta) and not change
                        counts["corrected"]+=corrected;counts["new_error"]+=new_error
                        counts["absolute_probability_delta_sum"]+=abs(delta)
                        counts["maximum_absolute_probability_delta"]=max(counts["maximum_absolute_probability_delta"],abs(delta))
                        item=files[(x["file"],x["source_sha256"],x["cohort"])]
                        for key,val in (("samples",1),("corrected",corrected),("new_error",new_error),("class_changed",change)):
                            item[key]+=val
                        if delta or change:
                            stream.write(json.dumps(dict(task_id=task,left=left,right=right,checkpoint=ck,
                                file=x["file"],source_sha256=x["source_sha256"],cohort=x["cohort"],
                                original_graph_node_id=x.get("original_graph_node_id"),target=x["target"],
                                left_prediction=x[ck],right_prediction=y[ck],probability_delta=delta,
                                class_changed=change,corrected=corrected,new_error=new_error))+"\n")
                    counts["mean_absolute_probability_delta"]=counts["absolute_probability_delta_sum"]/counts["samples"] if counts["samples"] else None
                    change_summary.append(dict(task_id=task,checkpoint=ck,**comp,**counts))
                    for (file,sha,cohort),value in files.items():
                        file_changes.append(dict(task_id=task,checkpoint=ck,left=left,right=right,file=file,
                            source_sha256=sha,cohort=cohort,**value))
                    for cohort in ("SolidiFI","nonSolidiFI"):
                        ls=score_or_empty([r for r in groups[left] if r["cohort"]==cohort],ck)
                        rs=score_or_empty([r for r in groups[right] if r["cohort"]==cohort],ck)
                        strata_comparisons.append(dict(task_id=task,checkpoint=ck,cohort=cohort,**comp,
                            left_scores=ls,right_scores=rs,delta_BF1_pp=None if ls["buggy_f1"] is None else ls["buggy_f1"]-rs["buggy_f1"]))
    count_audit={}
    for task,expected_count in plan["statistics"]["special_tables"]["expected_positive_counts"].items():
        actual=sum(r["L-audit_include"] and r["L-audit_target"]==1 and not Path(r["file"]).name.startswith("buggy_") for r in labels[task])
        count_audit[task]=dict(expected=expected_count,actual=actual,matched=actual==expected_count)
        if actual!=expected_count:raise ValueError("Frozen nonSolidiFI positive population differs")
    paired_folds=[]
    for r in paired:
        for f in r["folds"]:
            paired_folds.append(dict({k:v for k,v in r.items() if k!="folds"},**{("value_"+k if k in ("left","right") else k):v for k,v in f.items()}))
    gates=[]
    for r in diagnostics["artifacts"]:
        report=read(checked(r))
        for g in report.get("gates",[]):
            gates.append(dict(job_id=report["job_id"],**g))
    for name,rows in (("fold_counts.csv",fold_counts),("paired.csv",paired),("paired_folds.csv",paired_folds),
        ("best_fold_means.csv",[r for r in aggregates if r["checkpoint"]=="best"]),
        ("last_fold_means.csv",[r for r in aggregates if r["checkpoint"]=="last"]),
        ("orig_all_fold_means.csv",orig_aggregates),("pooled_oof.csv",pooled),
        ("nonSolidifi_positive_nodes.csv",special),("nonSolidifi_false_positive_nodes.csv",false_positives),("prediction_change_summary.csv",change_summary),
        ("file_error_changes.csv",file_changes),("resources.csv",resources),("gates.csv",gates)):
        csv_write(out/name,rows)
    write(out/"fold_metrics.json",records);write(out/"orig_all_fold_metrics.json",orig_records)
    write(out/"relation_support_gradients.json",support);write(out/"stratified_comparisons.json",strata_comparisons)
    result=dict(passed=True,new_fits=120,NA_reference_fits=240,combined_fits=360,
        view="original",label_policy="L-audit",score_role="outer_test",selection_role="inner_val",
        all_comparisons="descriptive_only",inferential_tests=False,holm=None,
        aggregates=aggregates,paired=paired,pooled_oof=pooled,prediction_changes=change_summary,
        nonSolidifi_positive_audit=count_audit,diagnostics=ref(root/"diagnostics/complete.json"),
        integrity=read(root/"analysis_audit.json"),
        caveats=["N-A historical receipt-bound predictions verified; 480 historical checkpoint files unavailable at reporting time, so no current N-A reload claimed.",
            "Single seed; overlapping training folds; no independent-seed significance.",
            "S2 modality dropout=0, S3/S4=0.1: feature and regularization effects are confounded.",
            "New adapters use spec-dependent seeds; only shared graph/classifier initial values are exactly aligned.",
            "Full graph transductive grouped outer evaluation is not external testing.",
            "S4m masks CTX only; CODE is original. S4-noG still includes DFG-derived features.",
            "S2 has no learned gate. Gate weights are not causal modality contributions.",
            "L-audit is diagnostic, not verified gold labels; inspect both cohorts.",
            "Final server batch is separate from local RTX3050; never pool or cherry-pick."])
    write(out/"report.json",result)
    lines=["# NS-P6 N-B results","",
        "120/120 N-B fits accepted; 240 N-A fits referenced read-only. Original view, L-audit, grouped outer evaluation.",
        "All comparisons descriptive; no significance test or Holm. Best/last and fold means/pooled OOF are separate.","",
        "| Task | Configuration | Best BF1 mean | Sample SD |","|---|---|---:|---:|"]
    for row in aggregates:
        if row["checkpoint"]=="best" and row["metric"]=="buggy_f1":
            lines.append("| {} | {} | {:.4f} | {:.4f} |".format(row["task_id"],row["profile"],row["mean"],row["sample_sd"]))
    lines+=["","See paired.csv, stratified_comparisons.json, nonSolidifi_positive_nodes.csv, gates.csv and prediction_change_summary.csv.",""]
    (out/"REPORT.md").write_text("\n".join(lines),encoding="utf8")
    write(out/"receipt.json",dict(plan=ref(root/"plan.json"),NA_plan=plan["na_parent"]["plan"],
        analysis_revision=ref(root/"analysis_revision.json"),
        artifacts=[ref(p) for p in sorted(out.iterdir()) if p.is_file()]))
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--root",default=str(worker.OUT))
    build(parser.parse_args().root)
