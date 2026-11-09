"""Read-only N-C1 finalization; frozen metric/alignment routines, one registered test."""
import argparse
import json
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.benchmark_v2.reporting import scored, csv_write
from scripts.DFG.dfg_v2.experiment.stats import aggregate_metrics, validate_records, paired_comparison, METRICS
from . import batch_nc1 as batch, batch_nc1_worker as worker
from .nc1_history import verify_index
from .reporting import aligned_rows, identity, read_artifact
from .nb_reporting import paired_rows, paired_descriptive, score_or_empty

def complete_entries(root, plan):
    done = read(root/"complete.json")
    if (done.get("passed") is not True or done.get("formal_fits") != 30
            or done["plan"] != ref(root/"plan.json")
            or done["execution_revision"] != ref(root/"execution_revision.json")
            or len(done["receipts"]) != 30):
        raise ValueError("All 30 accepted fits required")
    expected = {worker.job_id(j):j for j in plan["jobs"]}
    entries = {}
    for reference in done["receipts"]:
        receipt = read(checked(reference)); job = receipt["job"]; key = worker.job_id(job)
        if key in entries or job != expected.get(key):
            raise ValueError("Duplicate or unexpected receipt identity")
        directory = Path(reference["path"]).parent
        worker.verify_attempt(root, plan, job, directory, deep=True)
        entries[key] = (directory, receipt)
    if set(entries) != set(expected):
        raise ValueError("Missing fit identity")
    batch.validate_device_comparisons(plan["jobs"],
        [dict(r["job"],actual_device=r["actual_device"]) for _,r in entries.values()])
    return entries

def check_scores(rows, result):
    for ck in ("best","last"):
        actual = scored(rows,ck)
        if any(actual[k] != result["outer_test"][ck][k] for k in METRICS):
            raise ValueError("Independent metrics differ from frozen trainer")

def oof(rows, kind):
    if len({identity(r,kind) for r in rows}) != len(rows):
        raise ValueError("Repeated OOF identity")
    return rows

def changes(left, right, kind, ck):
    output = []
    for x,y in paired_rows(left,right,kind):
        output.append(dict(file=x["file"],source_sha256=x["source_sha256"],
            source_id=x.get("source_id"),cohort=x["cohort"],
            original_graph_node_id=x.get("original_graph_node_id"),target=x["target"],
            fold=x["fold"],S6_prediction=x[ck],S4_prediction=y[ck],
            S6_probability=x[ck+"_positive_probability"],S4_probability=y[ck+"_positive_probability"],
            probability_delta=x[ck+"_positive_probability"]-y[ck+"_positive_probability"],
            class_changed=x[ck]!=y[ck],
            corrected=x[ck]==x["target"] and y[ck]!=y["target"],
            new_error=x[ck]!=x["target"] and y[ck]==y["target"]))
        if x["fold"] != y["fold"]:
            raise ValueError("Paired outer fold differs")
    return output

def change_summary(rows):
    if not rows:
        return dict(n=0,probability_changed=0,class_changed=0,probability_only=0,
                    corrected=0,new_error=0,mean_abs_probability_delta=None,max_abs_probability_delta=None)
    return dict(n=len(rows),probability_changed=sum(r["probability_delta"]!=0 for r in rows),
        class_changed=sum(r["class_changed"] for r in rows),
        probability_only=sum(r["probability_delta"]!=0 and not r["class_changed"] for r in rows),
        corrected=sum(r["corrected"] for r in rows),new_error=sum(r["new_error"] for r in rows),
        mean_abs_probability_delta=statistics.mean(abs(r["probability_delta"]) for r in rows),
        max_abs_probability_delta=max(abs(r["probability_delta"]) for r in rows))

def result_matrix(records,jobs):
    expected=[(j["task_id"],"G3R/"+name,j["fold"],j["seed"],ck)
              for j in jobs for name in ("S4","S6") for ck in ("best","last")]
    return validate_records(records,expected_keys=expected)

def continuation_from_tables(paired,pooled):
    selected=[r for r in paired if r["task_id"]=="reentrancy_node"
              and r["checkpoint"]=="best" and r["metric"]=="buggy_f1"]
    a=[r for r in pooled if r["task_id"]=="reentrancy_node" and r["checkpoint"]=="best"
       and r["cohort"]=="nonSolidiFI"]
    if len(selected)!=1 or len(a)!=2 or {r["name"] for r in a}!={"S4","S6"}:
        raise ValueError("Registered continuation inputs incomplete or duplicated")
    values={r["name"]:r["buggy_f1"] for r in a}
    if any(v is None for v in values.values()):
        raise ValueError("Missing stratum score is not zero")
    return batch.continuation(selected[0]["mean_delta_pp"],values["S6"]-values["S4"])

def build(root=batch.DEFAULT):
    root=Path(root); plan=batch.load(root/"plan.json",deep=False)
    worker.validate_execution(root,plan)
    out=root/"reports"
    if out.exists(): raise FileExistsError("Preserve previous report attempt")
    checks=read(root/"report_checks.json")
    if checks.get("passed") is not True: raise ValueError("Reporting regression gate absent")
    sources=[ref(Path(__file__)),ref(batch.ROOT/"scripts/node_sem/tests/test_nc1_reporting.py")]
    sources += [ref(batch.ROOT/p) for p in (
        "scripts/node_sem/reporting.py","scripts/node_sem/nb_reporting.py",
        "scripts/DFG/dfg_v2/benchmark_v2/reporting.py","scripts/DFG/dfg_v2/experiment/stats.py")]
    binding=dict(plan=ref(root/"plan.json"),execution_revision=ref(root/"execution_revision.json"),
        complete=ref(root/"complete.json"),sources=sources,tests=ref(root/"report_checks.json"),
        statistics=plan["statistics"],formal_fits_added=0,model_evals_added=0,
        no_new_selection=True,created_unix=time.time())
    write(root/"reporting_revision.json",binding)
    out.mkdir()
    try:
        entries=complete_entries(root,plan); parents=verify_index(plan["na_result_index"])
        labels=read(checked(plan["jobs"][0]["label_view"]))
        records=[];original_records=[];counts=[];resources=[];support=[];tables={}
        for job in plan["jobs"]:
            old=parents[job["baseline_job_id"]]
            for j,entry in ((old["job"],(Path(old["receipt"]["path"]).parent,read(checked(old["receipt"])))),
                            (job,entries[worker.job_id(job)])):
                main=[dict(r,fold=j["fold"]) for r in aligned_rows(
                    read_artifact(entry,"outer_test_predictions.json"),j,labels)]
                original=aligned_rows(read_artifact(entry,"outer_test_orig_all_predictions.json"),j,labels,original=True)
                result=read_artifact(entry,"result.json"); check_scores(main,result)
                tables[(j["task_id"],j["name"],j["fold"])]=main
                for ck in ("best","last"):
                    ident=dict(task_id=j["task_id"],task_kind=j["granularity"],
                        profile="G3R/"+j["name"],fold=j["fold"],seed=j["seed"],checkpoint=ck)
                    m=scored(main,ck)
                    records.append(dict(ident,metrics={k:m[k] for k in METRICS}))
                    counts.append(dict(ident,**m))
                    original_records.append(dict(ident,metrics={k:scored(original,ck)[k] for k in METRICS}))
                rc=entry[1]
                resources.append(dict(task_id=j["task_id"],name=j["name"],fold=j["fold"],
                    best_epoch=result["best_epoch"],last_epoch=result["last_epoch"],epochs=result["history_rows"],
                    parameters=result["parameter_count"],fit_seconds=result["seconds"],
                    total_seconds=rc["total_seconds"],
                    peak_allocated_mib=rc["resources"]["peak_allocated_mib"],
                    peak_reserved_mib=rc["resources"]["peak_reserved_mib"],
                    minimum_free_mib=rc["resources"]["minimum_free_mib"],
                    actual_device=rc["actual_device"],checkpoint_roundtrip_exact=result["checkpoint_roundtrip_exact"]))
                gradient=read_artifact(entry,"gradient_audit.json")
                relations={}
                for epoch in gradient["epochs"]:
                    for g in epoch["v2_relations"]:
                        k=tuple(g["canonical"])
                        value=relations.setdefault(k,dict(canonical=list(k),
                            inner_train_edges=g["inner_train_edges"],inner_val_edges=g["inner_val_edges"],
                            outer_test_edges=g["outer_test_edges"],max_message_gradient_l1=0.,
                            max_attention_gradient_l1=0.,nonzero_message_epochs=0))
                        value["max_message_gradient_l1"]=max(value["max_message_gradient_l1"],g["message_gradient_l1"])
                        value["max_attention_gradient_l1"]=max(value["max_attention_gradient_l1"],g["attention_gradient_l1"])
                        value["nonzero_message_epochs"]+=g["message_gradient_l1"]>0
                support.append(dict(task_id=j["task_id"],name=j["name"],fold=j["fold"],
                    support=j["support"],relations=list(relations.values()),
                    message_update_l1=gradient["v2_message_update_l1"],
                    original_gradient_ref=ref(entry[0]/"fit/gradient_audit.json")))
            print("scored S4/S6 "+worker.job_id(job),flush=True)
        records=result_matrix(records,plan["jobs"]);result_matrix(original_records,plan["jobs"])
        aggregates=aggregate_metrics(records);orig_aggregates=aggregate_metrics(original_records)
        paired=[];pooled=[];positive=[];summaries=[];file_changes=[];count_audit={}
        with (out/"prediction_changes.jsonl").open("x",encoding="utf8") as stream:
            for task,folds in batch.TASK_FOLDS:
                kind=task.rsplit("_",1)[-1]
                groups={n:oof([r for f in range(folds) for r in tables[(task,n,f)]],kind) for n in ("S4","S6")}
                for ck in ("best","last"):
                    paired.extend(paired_descriptive(records,task,"G3R/S6","G3R/S4",ck))
                    for name,rows in groups.items():
                        for cohort in ("all","SolidiFI","nonSolidiFI"):
                            chosen=[r for r in rows if cohort=="all" or r["cohort"]==cohort]
                            pooled.append(dict(task_id=task,name=name,checkpoint=ck,cohort=cohort,**score_or_empty(chosen,ck)))
                    pairs=changes(groups["S6"],groups["S4"],kind,ck)
                    for cohort in ("all","SolidiFI","nonSolidiFI"):
                        selected=[r for r in pairs if cohort=="all" or r["cohort"]==cohort]
                        summaries.append(dict(task_id=task,checkpoint=ck,cohort=cohort,**change_summary(selected)))
                    byfile=defaultdict(list)
                    for row in pairs:
                        byfile[(row["file"],row["source_sha256"],row["cohort"])].append(row)
                        if row["probability_delta"] or row["class_changed"]:
                            stream.write(json.dumps(dict(task_id=task,checkpoint=ck,**row))+"\n")
                        if kind=="node" and row["cohort"]=="nonSolidiFI" and row["target"]==1:
                            positive.append(dict(task_id=task,checkpoint=ck,**row))
                    for (file,sha,cohort),rows in byfile.items():
                        file_changes.append(dict(task_id=task,checkpoint=ck,file=file,source_sha256=sha,
                            cohort=cohort,**change_summary(rows)))
                if kind=="node":
                    expected=plan["statistics"]["descriptive"]["non_solidiFI_positive_rows"][task]
                    actual=sum(r["target"]==1 and r["cohort"]=="nonSolidiFI" for r in groups["S6"])
                    if actual!=expected:raise ValueError("NonSolidiFI positive population differs")
                    count_audit[task]=dict(actual=actual,expected=expected,passed=True)
        primary=paired_comparison(records,"reentrancy_node","G3R/S6","G3R/S4","best","buggy_f1")
        decision=continuation_from_tables(paired,pooled)
        changes_compact=dict(aggregates=aggregates,paired=paired,pooled=pooled,prediction_changes=summaries,
            primary=primary,continuation=decision,nonSolidiFI_positive_audit=count_audit)
        flat=[dict(task_id=r["task_id"],checkpoint=r["checkpoint"],metric=r["metric"],**f) for r in paired for f in r["folds"]]
        for filename,rows in (
            ("fold_counts.csv",counts),("paired_folds.csv",flat),
            ("best_fold_means.csv",[r for r in aggregates if r["checkpoint"]=="best"]),
            ("last_fold_means.csv",[r for r in aggregates if r["checkpoint"]=="last"]),
            ("orig_all_fold_means.csv",orig_aggregates),("pooled_oof.csv",pooled),
            ("nonSolidiFI_positive_pairs.csv",positive),("prediction_change_summary.csv",summaries),
            ("file_error_changes.csv",file_changes),("resources.csv",resources)):
            csv_write(out/filename,rows)
        write(out/"fold_metrics.json",records);write(out/"orig_all_fold_metrics.json",original_records)
        write(out/"relation_support_gradients.json",support)
        write(out/"report.json",dict(passed=True,new_fits=30,S4_reference_fits=30,formal_fits_added=0,
            checkpoint="best_primary_last_auxiliary",view="original",label_policy="L-audit",protocol=plan["protocol"],
            score_role="outer_test",selection_role="inner_val",inference_tests=1,
            **changes_compact))
        failures=list((root/"runs").glob("*/attempt_*/failure.json"))
        attempts=list((root/"runs").glob("*/attempt_*"))
        write(out/"integrity.json",dict(passed=True,successful_receipts=30,S4_metric_references=30,
            S6_checkpoint_files_checked=60,S4_missing_best_last=read(checked(plan["na_result_index"]))["missing_checkpoints"],
            failures=len(failures),attempts=len(attempts),runtime_unchanged=True,device_tf32_consistent=True,
            original_and_Laudit_scores_recomputed=True,identity_aligned=True,no_new_model_load_or_forward=True))
        for source in sources:checked(source)
        write(out/"receipt.json",dict(plan=ref(root/"plan.json"),reporting_revision=ref(root/"reporting_revision.json"),
            artifacts=[ref(p) for p in sorted(out.iterdir()) if p.is_file()]))
        write(root/"report_complete.json",dict(passed=True,report=ref(out/"report.json"),
            receipt=ref(out/"receipt.json"),formal_fits=30,automatic_student_execution=False))
        print(json.dumps(dict(primary_p=primary.get("p_raw"),continuation=decision)))
        return changes_compact
    except BaseException:
        import traceback
        write(out/"failure.json",dict(traceback=traceback.format_exc(),automatic_retry=False))
        raise

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(batch.DEFAULT))
    build(p.parse_args().root)
