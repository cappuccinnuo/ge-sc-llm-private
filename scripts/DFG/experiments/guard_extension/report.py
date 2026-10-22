"""Independently recompute frozen-label CV metrics for three versions, without refitting archives."""
import math
from pathlib import Path
from collections import defaultdict
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.experiments.common import metrics
from scripts.DFG.experiments.e23_cv.report import aggregate,pooled,compare_rows,METRICS
from scripts.DFG.experiments.overall_cv.report import expected_population,checked_predictions,csv_write
from scripts.DFG.experiments.overall_cv.checks import completed as old_completed
from .common import *
from .checks import completed
from .archive import verify_archive
from . import BASELINES,VARIANT

def summarize(output=DEFAULT,tasks=TASKS):
    output=Path(output);plan=verify_plan(output)
    if not tasks or len(set(tasks))!=len(tasks) or any(t not in TASKS for t in tasks):
        raise ValueError("Unknown/duplicate summary task")
    oldplan,archive=verify_archive(plan["source_batch"])
    if archive["plan_sha256"]!=plan["source_plan_sha256"]:raise ValueError("Baseline plan drift")
    destination=output if tuple(tasks)==TASKS else output/"reports"/tasks[0]
    destination.mkdir(parents=True,exist_ok=True)
    variants=BASELINES+(VARIANT,)
    contrasts=(("HCG","HCG_DDG"),("HCG_DDG",VARIANT),("HCG",VARIANT))
    rows=[];deltas=[];errors=[];pools=[];oof=[];resources=[];relations=[];file_errors=[]
    for tid in tasks:
        first=read_json(task_ref(plan,tid,0)["manifest"])
        graph=read_graph(Path(first["graphs"][VARIANT]["path"]))
        sources=read_json(first["source_prepared_manifest"])["sources"]
        predictions={v:{} for v in variants}
        for fold in range(folds(tid)):
            info=read_json(task_ref(plan,tid,fold)["manifest"])
            expected=expected_population(info,graph);scores={}
            for v in variants:
                job=dict(task_id=tid,fold=fold,variant=v)
                folder=(completed(output,job,plan) if v==VARIANT
                        else old_completed(Path(plan["source_batch"]),job,oldplan))
                if folder is None:raise ValueError("Missing candidate/baseline fit: "+identity(job))
                result=read_json(folder/"result.json")
                pred=checked_predictions(read_json(folder/"cv_validation_predictions.json"),expected)
                predictions[v][fold]=pred;scores[v]={}
                for ck in ("best","last"):
                    m=metrics([r["target"] for r in pred],[r[ck] for r in pred]);scores[v][ck]=m
                    if m!=result["cv_validation"][ck]:raise ValueError("Independent metric mismatch")
                    rows.append(dict(job,cohort=info["cohort"],task=info["task"],checkpoint=ck,
                        score_role="cv_validation",**m,best_epoch=result["best_epoch"],last_epoch=result["last_epoch"],
                        historical_reuse=v in BASELINES))
                    for file in sorted({r["file"] for r in pred}):
                        rr=[r for r in pred if r["file"]==file]
                        file_errors.append(dict(job,checkpoint=ck,file=file,source_sha256=sources[file]["sha256"],
                            population=len(rr),errors=sum(r[ck]!=r["target"] for r in rr),
                            false_positive=sum(r[ck]==1 and r["target"]==0 for r in rr),
                            false_negative=sum(r[ck]==0 and r["target"]==1 for r in rr)))
                oof.extend(dict(job,cohort=info["cohort"],source_sha256=sources[r["file"]]["sha256"],**r) for r in pred)
                resources.append(dict(job,historical_reuse=v in BASELINES,parameters=result["parameters"],
                    best_epoch=result["best_epoch"],last_epoch=result["last_epoch"],epochs=result["history_rows"],
                    seconds=result["wall_seconds_monotonic"],peak_allocated_mib=result["resource"]["peak_allocated_bytes"]/1048576,
                    peak_reserved_mib=result["resource"]["peak_reserved_bytes"]/1048576,
                    minimum_card_free_mib=result["resource"]["card"]["minimum_whole_card_free_mib"],
                    checkpoint_roundtrip_exact=all(result["checkpoint_roundtrip_exact"].values()),accepted_attempt=str(folder)))
                byrelation=defaultdict(list)
                for epoch in result["gradient_audit"]["epochs"]:
                    for item in epoch["enhancement_relations"]:byrelation[tuple(item["canonical"])].append(item)
                for c,seq in sorted(byrelation.items()):
                    if any(not math.isfinite(x["message_gradient_l1"]) for x in seq):raise ValueError("Nonfinite relation gradient")
                    relations.append(dict(job,canonical=list(c),relation=c[1],train_edges=seq[0]["train_edges"],
                        val_edges=seq[0]["val_edges"],max_message_gradient_l1=max(x["message_gradient_l1"] for x in seq),
                        has_training_support=seq[0]["train_edges"]>0,
                        observed_nonzero_gradient=any(x["message_gradient_l1"]>0 for x in seq)))
            for left,right in contrasts:
                for ck in ("best","last"):
                    prefix=dict(task_id=tid,cohort=info["cohort"],fold=fold,checkpoint=ck,
                                contrast=right+"-"+left,score_role="cv_validation")
                    counts,changes=compare_rows(predictions[left][fold],predictions[right][fold],prefix)
                    deltas.append(dict(prefix,**counts,**{m+"_delta_pp":scores[right][ck][m]-scores[left][ck][m] for m in METRICS}))
                    errors.extend(dict(row,source_sha256=sources[row["file"]]["sha256"]) for row in changes)
        for v in variants:
            scores,allrows=pooled(predictions[v],folds(tid))
            split_doc=read_json(first["source_splits_path"])
            if {r["file"] for r in allrows}!=set(split_doc["files"]):raise ValueError("Incomplete OOF files")
            if first["task"]=="node" and len(allrows)!=len(graph):raise ValueError("Incomplete OOF nodes")
            for ck in ("best","last"):
                pools.append(dict(task_id=tid,variant=v,checkpoint=ck,score_role="pooled_cv_validation_oof",**scores[ck]))
    stats=aggregate(rows,("task_id","variant","checkpoint"))
    paired=aggregate(deltas,("task_id","checkpoint","contrast"),tuple(m+"_delta_pp" for m in METRICS))
    for row in paired:
        group=[x for x in deltas if all(x[k]==row[k] for k in ("task_id","checkpoint","contrast"))]
        for metric in ("buggy_f1","macro_f1"):
            values=[x[metric+"_delta_pp"] for x in group]
            row[metric+"_improved"]=sum(x>1e-10 for x in values)
            row[metric+"_tied"]=sum(abs(x)<=1e-10 for x in values)
            row[metric+"_declined"]=sum(x< -1e-10 for x in values)
    tables={"fold_results.csv":rows,"fold_statistics.csv":stats,"paired_deltas.csv":deltas,
            "paired_statistics.csv":paired,"pooled_oof.csv":pools,"oof_predictions.csv":oof,
            "prediction_changes.csv":errors,"file_error_analysis.csv":file_errors,
            "relation_support_gradients.csv":relations,"resources.csv":resources}
    for name,table in tables.items():csv_write(destination/name,table)
    report=dict(status="complete",tasks=list(tasks),new_fits=sum(folds(t) for t in tasks),
        reused_fits=sum(folds(t)*2 for t in tasks),score_role="cv_validation",independent_test=False,
        statistics=stats,paired=paired,pooled_oof=pools,
        interpretation="equal-fold means and sample SD; same validation selects/scores best; node unit is HCG node",
        causal_limit="Contrast includes new relation parameters, aggregation and optimization trajectory, not pure semantic causality",
        failures=[str(p.relative_to(output)) for p in (output/"runs").rglob("*.failure.json")])
    write_json(destination/"report.json",report)
    print("SUMMARY_ACCEPTED",list(tasks),report["new_fits"],"new fits",flush=True)
    return dict(tasks=list(tasks),new_fits=report["new_fits"],output=str(destination))
