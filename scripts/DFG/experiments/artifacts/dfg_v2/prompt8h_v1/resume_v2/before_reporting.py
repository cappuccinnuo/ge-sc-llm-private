"""Prompt 8H final-only reporting; all 170 accepted fits required."""
import argparse,csv,json,math,statistics
from collections import defaultdict
from pathlib import Path
from .execution import load,prepared,VERSION
from .prepare import read,write,ref,checked
from .acceptance import DEFAULT
from ..experiment.run import _job_directory,job_id
from ..experiment.stats import aggregate_metrics,paired_comparison,holm_adjust,METRICS
from scripts.DFG.experiments.common import metrics

def csv_write(path,rows):
    rows=list(rows)
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open("x",newline="",encoding="utf8") as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})

def wilson(success,total):
    if not total:return None
    z=1.959963984540054;p=success/total;d=1+z*z/total
    mid=(p+z*z/(2*total))/d;half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [100*(mid-half),100*(mid+half)]

def scored(rows,ck):
    result=metrics([r["target"] for r in rows],[r[ck] for r in rows])
    tp=sum(r["target"]==1 and r[ck]==1 for r in rows);fp=sum(r["target"]==0 and r[ck]==1 for r in rows)
    fn=sum(r["target"]==1 and r[ck]==0 for r in rows);tn=len(rows)-tp-fp-fn
    return dict(result,n=len(rows),positive=tp+fn,tn=tn,fp=fp,fn=fn,tp=tp,
        precision_wilson95=wilson(tp,tp+fp),recall_wilson95=wilson(tp,tp+fn),
        interval_interpretation="P/R descriptive proportion intervals; correlated nodes; not an F1 interval")

def stratified_score(rows,ck,cohort):
    result=scored(rows,ck)
    if cohort=="nonSolidiFI":
        result={k:v for k,v in result.items() if k in ("n","positive","tn","fp","fn","tp","precision_wilson95","recall_wilson95","interval_interpretation")}
    return result

def build(path):
    path=Path(path);plan=load(path);root=path.parent;done=read(root/"complete.json")
    if done.get("passed") is not True or done["formal_fits"]!=170 or len(done["receipts"])!=170:raise ValueError("Require full 170-fit acceptance")
    for r in done["receipts"]:checked(r)
    out=root/"reports";out.mkdir(exist_ok=False)
    records,orig_records,resources,predictions,support_rows=[],[],[],{},[]
    labels=read(checked(plan["source_bound_artifacts"]["label_views"]))
    # G* selection reads only inner scores; outer results cannot influence it.
    inner=defaultdict(lambda:defaultdict(list));schema_counts=defaultdict(list)
    for j in plan["jobs"]:
        d=_job_directory(root,j)/"attempt_001";receipt=read(d/"receipt.json")
        checked(dict(path=str(d/"inner_val_predictions.json"),sha256=receipt["artifacts"]["inner_val_predictions.json"]))
        r=read(d/"inner_val_predictions.json")
        inner[j["profile"]][j["task_id"]].append(metrics([x["target"] for x in r],[x["best"] for x in r])["buggy_f1"])
        _,_,entry=prepared(plan,j);schema_counts[j["profile"]].append(len(entry["support"]["schema"]["canonical_relations"]))
    candidate=plan["selection_rule"]["candidates"]
    means={p:statistics.mean(statistics.mean(v) for v in inner[p].values()) for p in candidate+["G0"]}
    best=max(candidate,key=lambda p:means[p]);tied=[p for p in candidate if means[best]-means[p]<.1]
    selected=min(tied,key=lambda p:(sum(schema_counts[p]),p))
    selection=dict(selected=selected,inner_equal_task_fold_means=means,tied=tied,outer_used=False,tie_rule=plan["selection_rule"])
    write(out/"selection.json",selection)
    for j in plan["jobs"]:
        tid,profile=j["task_id"],j["profile"];task=plan["tasks"][tid];kind=task["granularity"]
        d=_job_directory(root,j)/"attempt_001";receipt=read(d/"receipt.json")
        for name in ("final_result.json","outer_test_predictions.json","outer_test_orig_all_predictions.json","gradient_audit.json","schema_support_audit.json"):
            checked(dict(path=str(d/name),sha256=receipt["artifacts"][name]))
        result=read(d/"final_result.json");main=read(d/"outer_test_predictions.json");orig=read(d/"outer_test_orig_all_predictions.json")
        predictions[(tid,profile,j["fold"])]=main
        for ck in ("best","last"):
            identity=dict(task_id=tid,task_kind=kind,profile=profile,fold=j["fold"],seed=j["seed"],checkpoint=ck)
            records.append(dict(identity,metrics=metrics([r["target"] for r in main],[r[ck] for r in main])))
            orig_records.append(dict(identity,metrics=metrics([r["target"] for r in orig],[r[ck] for r in orig])))
        rs=result["resources"]
        resources.append(dict(j,best_epoch=result["best_epoch"],last_epoch=result["last_epoch"],parameter_count=result["parameter_count"],
            fit_seconds=result["seconds"],peak_allocated_mib=rs["peak_allocated_mib"],peak_reserved_mib=rs["peak_reserved_mib"],
            minimum_free_mib=rs["minimum_free_mib"],memory_tight=rs["memory_tight"],
            possible_memory_spill=rs["possible_memory_spill"],checkpoint_roundtrip=result["checkpoint_roundtrip_exact"]))
        counts=read(d/"schema_support_audit.json");grad=read(d/"gradient_audit.json")
        for row in counts["relations"]:
            support_rows.append(dict(j,**row,epochs=[dict(epoch=g["epoch"],details=[x for x in g["v2_relations"] if x["canonical"]==row["canonical"]]) for g in grad["epochs"]]))
    expected={(j["task_id"],j["profile"],j["fold"],j["seed"],ck) for j in plan["jobs"] for ck in ("best","last")}
    if len(records)!=340 or {(r["task_id"],r["profile"],r["fold"],r["seed"],r["checkpoint"]) for r in records}!=expected:raise ValueError("Incomplete/duplicate metric matrix")
    aggregates=aggregate_metrics(records);originals=aggregate_metrics(orig_records)
    comparisons=[];holm=[]
    for tid,t in plan["tasks"].items():
        available=set(j["profile"] for j in plan["jobs"] if j["task_id"]==tid)
        for ck in ("best","last"):
            for metric in METRICS:
                family=[]
                for profile in ("G1R","G2R","G3R","G3"):
                    c=paired_comparison(records,tid,profile,"G0",ck,metric);comparisons.append(c);family.append(c)
                holm.append(dict(task_id=tid,checkpoint=ck,metric=metric,family_name="four_profiles_vs_G0",
                    **holm_adjust({c["profile"]:c["p_raw"] for c in family})))
                extras=[("G3R","G3")]+([("G0P","G0"),("G3R","G0P")] if "G0P" in available else [])
                family=[]
                for p,b in extras:
                    c=paired_comparison(records,tid,p,b,ck,metric);comparisons.append(c);family.append(c)
                # Direction/placebo comparisons remain separate, without Holm.
    pooled=[];changes=[];keywords=[]
    for tid,t in plan["tasks"].items():
        node=t["granularity"]=="node";key=lambda r:(r["file"],r["original_graph_node_id"]) if node else r["file"]
        lookup={key(r):r for r in labels[tid]}
        population=read(checked(t["population"]))
        if not isinstance(population,list) or any(r["cohort"] not in ("SolidiFI","nonSolidiFI") for r in population):
            raise ValueError("Unknown frozen source cohort")
        cohorts={r["file"]:r["cohort"]=="SolidiFI" for r in population}
        if len(cohorts)!=len(population) or set(cohorts)!={r["file"] for r in labels[tid]}:
            raise ValueError("Source cohort identity differs")
        for r in labels[tid]:
            if "solidifi" in r and r["solidifi"]!=cohorts[r["file"]]:
                raise ValueError("Node/source cohort disagreement")
        profiles=sorted(set(j["profile"] for j in plan["jobs"] if j["task_id"]==tid))
        tables={}
        for p in profiles:
            combined=[r for fold in range(t["k_folds"]) for r in predictions[(tid,p,fold)]]
            if len({key(r) for r in combined})!=len(combined):raise ValueError("Duplicate outer prediction identity across folds")
            tables[p]={key(r):r for r in combined}
            for cohort in ("all","SolidiFI","nonSolidiFI"):
                chosen=[r for r in combined if cohort=="all" or cohorts[r["file"]]==(cohort=="SolidiFI")]
                for ck in ("best","last"):
                    pooled.append(dict(task_id=tid,profile=p,checkpoint=ck,cohort=cohort,**stratified_score(chosen,ck,cohort)))
        for p,b in [(p,"G0") for p in profiles if p!="G0"]+[("G3R","G3")]+([("G3R","G0P")] if "G0P" in profiles else []):
            if set(tables[p])!=set(tables[b]):raise ValueError("Paired identities differ")
            for ck in ("best","last"):
                for k,left in tables[p].items():
                    right=tables[b][k];prob=left[ck+"_positive_probability"]-right[ck+"_positive_probability"]
                    if left[ck]!=right[ck] or prob:
                        source=lookup[k]
                        changes.append(dict(task_id=tid,profile=p,baseline=b,checkpoint=ck,file=left["file"],
                            original_graph_node_id=left.get("original_graph_node_id"),
                            source_sha256=source["source_sha256"],target=left["target"],prediction=left[ck],baseline_prediction=right[ck],
                            corrected=right[ck]!=left["target"] and left[ck]==left["target"],
                            new_error=right[ck]==left["target"] and left[ck]!=left["target"],
                            probability_delta=prob,class_changed=left[ck]!=right[ck]))
        if node:
            summary=read(checked(plan["source_bound_artifacts"]["keyword_baselines"]))
            kw=read(checked(summary["keywords"][tid]["artifact"]))["predictions"]
            table={key(r):r for r in kw}
            selected_rows=[dict(target=r["L-audit_target"],prediction=table[key(r)]["prediction"],file=r["file"]) for r in labels[tid] if r["L-audit_include"]]
            for cohort in ("all","SolidiFI","nonSolidiFI"):
                subset=[r for r in selected_rows if cohort=="all" or cohorts[r["file"]]==(cohort=="SolidiFI")]
                keywords.append(dict(task_id=tid,label_policy="L-audit",cohort=cohort,**stratified_score(subset,"prediction",cohort)))
    write(out/"fold_metrics.json",records);write(out/"orig_all_fold_metrics.json",orig_records)
    for name,data in (("best_fold_means",[r for r in aggregates if r["checkpoint"]=="best"]),
        ("last_fold_means",[r for r in aggregates if r["checkpoint"]=="last"]),("orig_all_fold_means",originals),
        ("paired",comparisons),("holm",holm),("pooled_oof",pooled),("resources",resources),("keyword_baselines",keywords)):
        csv_write(out/(name+".csv"),data)
    write(out/"error_probability_changes.json",changes);write(out/"relation_support_gradients.json",support_rows)
    old=Path(plan["source_bound_artifacts"]["historical_plan"]["path"]).parent/"reports/final/best_fold_means.csv"
    historical=list(csv.DictReader(old.open(encoding="utf8")))
    write(out/"historical_original_names_descriptive.json",dict(source=ref(old),rows=historical,
        warning="Different naming, group splits and label policy; not the same controlled comparison; no mixed p-values."))
    report=dict(version=VERSION,complete=True,formal_fits=170,selection=selection,aggregates=aggregates,
        comparisons=comparisons,holm=holm,pooled_oof=pooled,keyword_baselines=keywords,
        interpretation=["L-audit is a diagnostic policy, not proven ground truth.",
            "Grouped nested outer evaluation uses full fixed transductive graphs; not an independent external test.",
            "Single seed; shared-training folds are not independent replications.",
            "Changes include relation parameters/aggregation/optimization, not isolated semantic causal effects.",
            "Access-control node task and contract tasks are descriptive; primary endpoint reentrancy_node G3R-G0."],
        maximum_memory_mib=max(r["peak_reserved_mib"] for r in resources),fit_seconds=sum(r["fit_seconds"] for r in resources))
    write(out/"report.json",report)
    lines=["# Prompt 8H results","", "170/170 fits accepted. Primary: L-audit, best by inner validation loss; grouped outer evaluation.","",
        "| Task | Profile | BF1 mean | Sample SD |","|---|---|---:|---:|"]
    for r in aggregates:
        if r["checkpoint"]=="best" and r["metric"]=="buggy_f1":
            lines.append("| {} | {} | {:.4f} | {:.4f} |".format(r["task_id"],r["profile"],r["mean"],r["sample_sd"]))
    lines+=["","Selected G*: "+selected+" (inner validation only).","",
        "See paired.csv, holm.csv, orig_all_fold_means.csv, last_fold_means.csv and pooled_oof.csv; folds and pooled scores are separate.",
        "Precision/recall Wilson intervals are descriptive; F1 has no Wilson interval.","",
        "Final experiments are intended for a server with sufficient VRAM; current results were run locally with frozen local_dev_v1.",
        "No additional seeds, vulnerability categories, or model extensions were started."]
    (out/"REPORT.md").write_text("\n".join(lines)+"\n")
    write(out/"receipt.json",dict(plan=ref(path),complete=ref(root/"complete.json"),artifacts={p.name:ref(p) for p in out.iterdir() if p.is_file()}))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--plan",default=str(DEFAULT/"plan.json"));a=p.parse_args();build(a.plan)
