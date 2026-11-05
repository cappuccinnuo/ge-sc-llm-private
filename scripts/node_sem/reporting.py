"""Final-only N-A analysis: select on inner validation, then score outer OOF.
Uses frozen benchmark_v2.reporting metrics/Wilson and experiment.stats.
Historical anonymous scores are descriptive only, never a paired baseline.
"""
import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,write,ref,checked
from scripts.DFG.dfg_v2.benchmark_v2.reporting import scored,stratified_score,csv_write
from scripts.DFG.dfg_v2.experiment.stats import aggregate_metrics,paired_comparison,holm_adjust,METRICS
from scripts.DFG.experiments.common import metrics
from . import batch_na
from . import batch_na_worker as worker


def identity(row,kind):
    return (row["file"],row["original_graph_node_id"]) if kind=="node" else (row["file"],)


def aligned_rows(rows,job,labels,role="outer_test",original=False):
    kind=job["granularity"];files=set(job["split"][role+"_files"])
    truth={identity(r,kind):r for r in labels[job["task_id"]] if r["file"] in files
        and (original or r["L-audit_include"])}
    if len(rows)!=len(truth) or len({identity(r,kind) for r in rows})!=len(rows):
        raise ValueError("Missing or duplicated prediction identity")
    result=[]
    for row in rows:
        key=identity(row,kind)
        if key not in truth or row["score_role"]!=role:
            raise ValueError("Prediction split/identity differs")
        expected=truth[key]["orig" if original else "L-audit_target"]
        if row["target"]!=expected:raise ValueError("Prediction target differs from frozen labels")
        result.append(dict(row,source_sha256=truth[key]["source_sha256"],
            source_id=truth[key].get("source_id"),cohort="SolidiFI" if Path(row["file"]).name.startswith("buggy_") else "nonSolidiFI"))
    return result


def manifest_attempts(root,plan):
    done=read(root/"complete.json")
    if (not done.get("passed") or done.get("formal_fits")!=240
            or done["plan"]!=ref(root/"plan.json") or len(done["receipts"])!=240):
        raise ValueError("All 240 fits required before any results analysis")
    found={}
    for reference in done["receipts"]:
        receipt=read(checked(reference));key=worker.job_id(receipt["job"])
        if key in found:raise ValueError("Duplicate receipt")
        found[key]=(Path(reference["path"]).parent,receipt)
    if set(found)!={worker.job_id(j) for j in plan["jobs"]}:raise ValueError("Receipt matrix differs")
    batch_na.validate_device_comparisons(plan["jobs"],
        [dict(r["job"],actual_device=r["actual_device"]) for _,r in found.values()])
    return found


def read_artifact(entry,name):
    directory,receipt=entry
    path=(directory/"fit"/name).resolve()
    candidates=[r for r in receipt["artifacts"] if Path(r["path"]).resolve()==path]
    if len(candidates)!=1:raise ValueError("Missing/duplicate receipt artifact: "+name)
    return read(checked(candidates[0]))


def select_inner(root,plan,entries,labels):
    target=root/"selection.json"
    if target.exists():
        seal=read(root/"selection.seal.json")
        if seal["selection"]!=ref(target) or seal["plan"]!=ref(root/"plan.json"):
            raise ValueError("Existing selection seal differs")
        return read(target)
    values=defaultdict(lambda:defaultdict(list));inputs=[];widths={}
    for job in plan["jobs"]:
        if job["profile"]!="G3R" or job["name"] not in plan["statistics"]["s_star"]["candidates"]:continue
        rows=aligned_rows(read_artifact(entries[worker.job_id(job)],"inner_val_predictions.json"),
            job,labels,role="inner_val")
        value=metrics([r["target"] for r in rows],[r["best"] for r in rows])["buggy_f1"]
        values[job["name"]][job["task_id"]].append(value);widths[job["name"]]=job["carrier_dim"]
        inputs.append(ref(entries[worker.job_id(job)][0]/"fit/inner_val_predictions.json"))
    means={name:statistics.mean(statistics.mean(v) for v in tasks.values()) for name,tasks in values.items()}
    if set(means)!=set(plan["statistics"]["s_star"]["candidates"]):raise ValueError("Selection candidates incomplete")
    selected=min(means,key=lambda n:(-means[n],widths[n],n))
    result=dict(selected=selected,inner_equal_task_fold_means=means,outer_test_used=False,
        role="inner_val",checkpoint="best",rule=plan["statistics"]["s_star"],inputs=inputs)
    write(target,result);write(root/"selection.seal.json",dict(selection=ref(target),plan=ref(root/"plan.json")))
    return result


def summarize_records(records,plan):
    expected={(j["task_id"],j["profile"]+"/"+j["name"],j["fold"],j["seed"],ck)
        for j in plan["jobs"] for ck in ("best","last")}
    actual={(r["task_id"],r["profile"],r["fold"],r["seed"],r["checkpoint"]) for r in records}
    if len(records)!=480 or actual!=expected:raise ValueError("Incomplete or mixed score matrix")
    return aggregate_metrics(records)


def comparisons(records,plan):
    output=[];holm=[]
    for task,_ in batch_na.TASK_FOLDS:
        for graph in batch_na.PROFILES:
            for ck in ("best","last"):
                for name,base in plan["statistics"]["holm_family"]:
                    c=paired_comparison(records,task,graph+"/"+name,graph+"/"+base,ck)
                    # Only the preregistered primary task/profile/best family is inferential.
                    if not(task=="reentrancy_node" and graph=="G3R" and ck=="best"):
                        c.update(p_raw=None,wilcoxon_statistic=None,inference="descriptive_only")
                    c.update(name=name,baseline_name=base,graph=graph)
                    output.append(c)
    family=[c for c in output if c["task_id"]=="reentrancy_node" and c["graph"]=="G3R" and c["checkpoint"]=="best"]
    family_names=[a+"-"+b for a,b in plan["statistics"]["holm_family"]]
    holm=holm_adjust({c["name"]+"-"+c["baseline_name"]:c["p_raw"] for c in family},
                     expected_profiles=family_names)
    return output,holm


def build(root=worker.OUT):
    root=Path(root);plan=worker.load_plan(root);entries=manifest_attempts(root,plan)
    labels=read(checked(plan["jobs"][0]["label_view"]))
    # This function reads no outer predictions/results before the immutable selection.
    selection=select_inner(root,plan,entries,labels)
    out=root/"reports";out.mkdir(exist_ok=False)
    records=[];orig_records=[];fold_counts=[];resources=[];tables={};support=[]
    for job in plan["jobs"]:
        key=worker.job_id(job);entry=entries[key]
        main=aligned_rows(read_artifact(entry,"outer_test_predictions.json"),job,labels)
        original=aligned_rows(read_artifact(entry,"outer_test_orig_all_predictions.json"),job,labels,original=True)
        tables[(job["task_id"],job["profile"],job["name"],job["fold"])]=main
        result=read_artifact(entry,"result.json")
        for ck in ("best","last"):
            ident=dict(task_id=job["task_id"],task_kind=job["granularity"],
                profile=job["profile"]+"/"+job["name"],fold=job["fold"],seed=job["seed"],checkpoint=ck)
            m=scored(main,ck)
            # Independently recomputed scores must equal the frozen trainer's recorded scores.
            if any(m[k]!=result["outer_test"][ck][k] for k in METRICS):
                raise ValueError("Independent outer metrics differ")
            records.append(dict(ident,metrics={k:m[k] for k in METRICS}))
            orig_records.append(dict(ident,metrics=metrics([r["target"] for r in original],[r[ck] for r in original])))
            fold_counts.append(dict(ident,**m,errors=m["fp"]+m["fn"]))
        receipt=entry[1]
        resources.append(dict(job_id=key,task_id=job["task_id"],profile=job["profile"],name=job["name"],fold=job["fold"],
            best_epoch=result["best_epoch"],last_epoch=result["last_epoch"],parameters=result["parameter_count"],
            fit_seconds=result["seconds"],total_seconds=receipt["total_seconds"],
            actual_device=receipt["actual_device"],**receipt["resources"]))
        support.append(dict(job_id=key,support=job["support"],
            gradient=read_artifact(entry,"gradient_audit.json")))
    aggregates=summarize_records(records,plan);orig_aggregates=summarize_records(orig_records,plan)
    paired,holm=comparisons(records,plan)
    pooled=[];special=[];changes=[];interactions=[];errors=[]
    for task,folds in batch_na.TASK_FOLDS:
        kind=task.rsplit("_",1)[-1]
        for graph in batch_na.PROFILES:
            groups={}
            for name in batch_na.NAMES:
                rows=[r for f in range(folds) for r in tables[(task,graph,name,f)]]
                keys=[identity(r,kind) for r in rows]
                if len(keys)!=len(set(keys)):raise ValueError("OOF identity repeated across folds")
                groups[name]={identity(r,kind):r for r in rows}
                for ck in ("best","last"):
                    for cohort in ("all","SolidiFI","nonSolidiFI"):
                        chosen=[r for r in rows if cohort=="all" or r["cohort"]==cohort]
                        if chosen:
                            summary=stratified_score(chosen,ck,cohort)
                            # Explicit pooled point estimates; Wilson only for P/R.
                            summary.update({k:scored(chosen,ck)[k] for k in METRICS})
                        else:
                            summary=dict(n=0,positive=0,tn=0,fp=0,fn=0,tp=0,
                                precision_wilson95=None,recall_wilson95=None,
                                status="empty_stratum_no_metric",**{k:None for k in METRICS})
                        pooled.append(dict(task_id=task,profile=graph,name=name,checkpoint=ck,cohort=cohort,**summary))
                    if kind=="node":
                        for row in rows:
                            if row["cohort"]=="nonSolidiFI" and (row["target"]==1 or
                                    (task=="reentrancy_node" and row[ck]==1 and row["target"]==0)):
                                special.append(dict(task_id=task,profile=graph,name=name,checkpoint=ck,
                                    **row,prediction=row[ck],probability=row[ck+"_positive_probability"]))
            for name,base in plan["statistics"]["holm_family"]:
                if set(groups[name])!=set(groups[base]):raise ValueError("Paired prediction identities differ")
                for ck in ("best","last"):
                    for k,left in groups[name].items():
                        right=groups[base][k]
                        if left["target"]!=right["target"] or left["source_sha256"]!=right["source_sha256"]:
                            raise ValueError("Paired source/label identity differs")
                        delta=left[ck+"_positive_probability"]-right[ck+"_positive_probability"]
                        if delta or left[ck]!=right[ck]:
                            changes.append(dict(task_id=task,profile=graph,name=name,baseline=base,checkpoint=ck,
                                file=left["file"],source_sha256=left["source_sha256"],
                                original_graph_node_id=left.get("original_graph_node_id"),target=left["target"],
                                prediction=left[ck],baseline_prediction=right[ck],probability_delta=delta,
                                class_changed=left[ck]!=right[ck],
                                corrected=left[ck]==left["target"] and right[ck]!=left["target"],
                                new_error=left[ck]!=left["target"] and right[ck]==left["target"]))
            for f in range(folds):
                for ck in ("best","last"):
                    a=scored(tables[(task,graph,"S4",f)],ck);b=scored(tables[(task,graph,"S0o",f)],ck)
                    ea,eb=a["fp"]+a["fn"],b["fp"]+b["fn"]
                    errors.append(dict(task_id=task,profile=graph,fold=f,checkpoint=ck,S4_errors=ea,S0o_errors=eb,
                        relative_error_reduction=None if eb==0 else 1-ea/eb))
        for ck in ("best","last"):
            delta=[]
            for f in range(folds):
                effects={g:scored(tables[(task,g,"S4",f)],ck)["buggy_f1"]-
                           scored(tables[(task,g,"S0o",f)],ck)["buggy_f1"] for g in batch_na.PROFILES}
                delta.append(dict(fold=f,interaction_pp=effects["G3R"]-effects["G0"]))
            interactions.append(dict(task_id=task,checkpoint=ck,folds=delta,
                mean_pp=statistics.mean(r["interaction_pp"] for r in delta),inferential=False))
    count_audit={}
    for task,expected in plan["statistics"]["special_tables"]["expected_positive_counts"].items():
        actual=sum(r["L-audit_include"] and r["L-audit_target"]==1
            and not Path(r["file"]).name.startswith("buggy_") for r in labels[task])
        count_audit[task]=dict(expected=expected,actual=actual,matched=expected==actual,
            policy="Never discard rows to match expected counts")
    historical_root=Path(checked(plan["source_h8_plan"])).parent
    revision=read(root/"execution_revision.json")
    historical_ref=revision["analysis_refs"]["report.json"];history=read(checked(historical_ref))
    historical_folds=read(checked(revision["analysis_refs"]["fold_metrics.json"]))
    historical=dict(source=historical_ref,
        aggregates=aggregate_metrics([r for r in historical_folds if r["profile"] in ("G0","G3R") and r["seed"]==1]),
        warning="Anonymous 8H reference only; not an original-name paired baseline")
    keyword=dict(source=historical_ref,rows=history["keyword_baselines"],
        warning="Historical keyword baseline, descriptive external reference")
    attention_index=root/"attention/complete.json"
    attention=read(attention_index)
    if not attention.get("passed") or attention.get("count")!=120:raise ValueError("120 G3R attention evaluations required")
    for r in attention["artifacts"]:checked(r)
    for filename,rows in (("fold_counts.csv",fold_counts),("best_fold_means.csv",[r for r in aggregates if r["checkpoint"]=="best"]),
        ("last_fold_means.csv",[r for r in aggregates if r["checkpoint"]=="last"]),("orig_all_fold_means.csv",orig_aggregates),
        ("pooled_oof.csv",pooled),("paired.csv",paired),("errors.csv",errors),("resources.csv",resources),
        ("nonSolidifi_nodes.csv",special)):
        csv_write(out/filename,rows)
    write(out/"prediction_changes.json",changes);write(out/"relation_support_gradients.json",support)
    write(out/"historical_8H.json",historical);write(out/"keyword_reference.json",keyword)
    write(out/"fold_metrics.json",records);write(out/"orig_all_fold_metrics.json",orig_records)
    result=dict(passed=True,formal_fits=240,view="original",label_policy="L-audit",selection=selection,
        local_batch="RTX3050 family; default TF32 matmul/cudnn true",
        server="Separate preregistered replication; never pool or select favorable batch; disclose disagreement",
        aggregates=aggregates,paired=paired,holm=holm,interactions=interactions,pooled_oof=pooled,
        nonSolidifi_positive_audit=count_audit,attention=ref(attention_index),
        gate_distribution="Not applicable: N-A uses concat/raw_linear, no gated configuration",
        caveats=["Single seed; folds share training data; uncertainty is descriptive.",
            "Full fixed graph transductive forward; grouped outer evaluation is not external independent testing.",
            "L-audit is a diagnostic label view, not proven gold standard.",
            "Original names may expose SolidiFI markers; examine stratified results.",
            "Feature/graph/optimization differences are not isolated semantic causal contributions."])
    write(out/"report.json",result)
    lines=["# NS-P5A N-A results","",
        "本批为本机 RTX3050、默认 TF32 的原名视图实验，240/240 正式拟合通过验收。",
        "最终服务器实验另行封存并按同一预先登记复现；两批不合并、不择优，结论不一致时都报告。","",
        "| Task | Graph / configuration | Best BF1 mean | Sample SD |","|---|---|---:|---:|"]
    for row in aggregates:
        if row["checkpoint"]=="best" and row["metric"]=="buggy_f1":
            lines.append("| {} | {} | {:.4f} | {:.4f} |".format(row["task_id"],row["profile"],row["mean"],row["sample_sd"]))
    lines+=["","S*（只用 inner_val，参考项）："+selection["selected"],"",
        "主终点为重入节点 G3R、S4−S0o；best 按最低 inner_val loss 选择，outer_test 仅在拟合后评分。",
        "best/last、折均值/pooled OOF、原标签辅助结果分别报告。Wilson 区间仅用于 Precision/Recall。",
        "详见 report.json、paired.csv、nonSolidifi_nodes.csv、errors.csv 和注意力验收索引。",""]
    (out/"REPORT.md").write_text("\n".join(lines),encoding="utf8")
    write(out/"receipt.json",dict(plan=ref(root/"plan.json"),selection=ref(root/"selection.json"),
        artifacts=[ref(p) for p in sorted(out.iterdir()) if p.is_file()]))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(worker.OUT));a=p.parse_args();build(a.root)
