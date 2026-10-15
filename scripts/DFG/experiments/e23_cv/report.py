"""Independent H1 per-fold, paired and pooled OOF summaries; historical baselines separate."""
import csv,json,math,statistics
from collections import Counter
from pathlib import Path
from types import FunctionType
from scripts.DFG.experiments.common import read_json,write_json,sha256,digest
from scripts.DFG.experiments.e23_pilot import report as g
from scripts.DFG.experiments.e23_pilot.inputs import TASK_ORDER,OLD_RUN,DEFAULT_OUTPUT as STAGE_G
from .control import verify_plan,verify,locate
METRICS=("buggy_f1","macro_f1","precision","recall")

def accepted(output,job):
    plan=read_json(Path(output)/"plan.json")
    attempt,attempts=locate(output,job,plan)
    if attempt is None:raise ValueError("Unfinished H1 job")
    receipt=read_json(attempt/"receipt.json")
    required={"result.json","binding.json","history.jsonl","cv_validation_predictions.json","best.pt","last.pt","effective_config.json","schema_support_audit.json"}
    if not required<=set(receipt["artifact_sha256"]):raise ValueError("Incomplete receipt")
    for rel,expected in receipt["artifact_sha256"].items():
        path=(attempt/rel).resolve()
        if attempt.resolve() not in path.parents:raise ValueError("Artifact escapes attempt")
        g._checked(path,expected)
    binding=read_json(attempt/"binding.json")
    if binding.get("execution_batch_version")!="stage-h1-e2-e3b-paper-kfold-v1" or binding.get("fold")!=job["fold"]:raise ValueError("H1 checkpoint fold/batch binding differs")
    if binding["pilot_plan_sha256"]!=digest(plan):raise ValueError("H1 checkpoint plan differs")
    g._checked(attempt/"result.json",receipt["result_sha256"])
    return attempt,receipt,[{"path":str(p),"status":"complete" if (p/"receipt.json").exists() else "failed_or_partial"} for p in attempts]

_read_new=FunctionType(g._read_fit.__code__,dict(g._read_fit.__globals__,_accepted_attempt=accepted),g._read_fit.__name__)

def read_fit(output,job):
    info=read_json(g._checked(job["task_manifest"],job["task_manifest_sha256"]))
    for key in ("task_id","fold","task","cohort"):
        if info[key]!=job[key]:raise ValueError("Manifest identity mismatch")
    expected=g._expected_population(info)
    if job["source"]=="stage_g_reuse":
        fit=g._read_fit(STAGE_G,job["stage_g_job"],info,expected)
        fit["job"]=job
    else:fit=_read_new(Path(output),job,info,expected)
    return fit

def aggregate(rows,keys,metrics=METRICS):
    groups={}
    for row in rows:groups.setdefault(tuple(row[k] for k in keys),[]).append(row)
    result=[]
    for identity,items in groups.items():
        r=dict(zip(keys,identity));r["folds"]=len(items)
        for metric in metrics:
            values=[float(x[metric]) for x in items]
            if len(values)<2:raise ValueError("Sample std needs at least two folds")
            r[metric+"_mean"]=statistics.mean(values);r[metric+"_sample_std"]=statistics.stdev(values)
        result.append(r)
    return result

def pooled(rows,expected_folds):
    seen=set();all_rows=[]
    if sorted(rows)!=list(range(expected_folds)):raise ValueError("Incomplete pooled folds")
    files=set()
    for fold,items in sorted(rows.items()):
        fold_files={x["file"] for x in items}
        if files & fold_files:raise ValueError("File occurs in multiple validation folds")
        files.update(fold_files)
        for row in items:
            key=(row["file"],json.dumps(row.get("original_graph_node_id"),sort_keys=True))
            if key in seen:raise ValueError("Duplicate OOF identity")
            seen.add(key);all_rows.append(row)
    return {ck:g._metrics([x["target"] for x in all_rows],[x[ck] for x in all_rows]) for ck in ("best","last")},all_rows

def compare_rows(before,after,prefix):
    if len(before)!=len(after):raise ValueError("Pair population size differs")
    counter=Counter();details=[]
    ck=prefix["checkpoint"]
    for a,b in zip(before,after):
        for key in ("file","original_graph_node_id","target","node_type","model_node_id"):
            if a.get(key)!=b.get(key):raise ValueError("Paired prediction identity mismatch: "+key)
        ga=a[ck]==a["target"];gb=b[ck]==b["target"]
        transition="both_correct" if ga and gb else "fixed" if not ga and gb else "regressed" if ga and not gb else "both_wrong"
        counter[transition]+=1
        pa=a[ck+"_positive_probability"];pb=b[ck+"_positive_probability"]
        if pa!=pb:counter["probability_changed"]+=1
        if a[ck]!=b[ck]:counter["prediction_changed"]+=1
        if pa!=pb or a[ck]!=b[ck]:
            details.append(dict(prefix,file=a["file"],original_graph_node_id=a.get("original_graph_node_id"),
                node_type=a.get("node_type"),target=a["target"],before_prediction=a[ck],after_prediction=b[ck],
                before_probability=pa,after_probability=pb,probability_delta=pb-pa,
                prediction_changed=a[ck]!=b[ck],transition=transition))
    return {k:counter[k] for k in ("both_correct","both_wrong","fixed","regressed","probability_changed","prediction_changed")},details

def summarize(output):
    output=Path(output);plan=verify_plan(output)
    if verify(output)["total_complete"]!=60:raise ValueError("Incomplete H1")
    fits=[read_fit(output,j) for j in plan["jobs"]]
    summary={ck:[g._summary_row(f,ck) for f in fits] for ck in ("best","last")}
    deltas=[];errors=[];pool=[];oof_export=[]
    for task in TASK_ORDER:
        k=5 if task.endswith("_contract") else 10
        for fold in range(k):
            a=next(f for f in fits if f["job"]["task_id"]==task and f["job"]["fold"]==fold and f["job"]["variant"]=="E2")
            b=next(f for f in fits if f["job"]["task_id"]==task and f["job"]["fold"]==fold and f["job"]["variant"]=="E3b")
            for ck in ("best","last"):
                prefix={"task_id":task,"fold":fold,"checkpoint":ck,"contrast":"E3b-E2","score_role":"cv_validation"}
                counts,details=compare_rows(a["predictions"],b["predictions"],prefix)
                row=dict(prefix,**counts)
                for m in METRICS:row[m+"_delta_pp"]=b["scores"][ck][m]-a["scores"][ck][m]
                row["E2_buggy_f1"]=a["scores"][ck]["buggy_f1"];row["E2_errors"]=a["scores"][ck]["tn_fp_fn_tp"][1]+a["scores"][ck]["tn_fp_fn_tp"][2]
                row["E2_buggy_f1_headroom_pp"]=100-row["E2_buggy_f1"]
                deltas.append(row);errors.extend(details)
        for variant in ("E2","E3b"):
            ff=[f for f in fits if f["job"]["task_id"]==task and f["job"]["variant"]==variant]
            scores,rows=pooled({f["job"]["fold"]:f["predictions"] for f in ff},k)
            info=ff[0]["info"]
            document=read_json(info["source_splits_path"])
            if {r["file"] for r in rows}!=set(document["files"]):raise ValueError("OOF file coverage differs")
            if info["task"]=="node" and len(rows)!=info["graphs"][variant]["nodes"]:raise ValueError("OOF node coverage differs")
            for ck in ("best","last"):pool.append(dict(task_id=task,variant=variant,checkpoint=ck,score_role="pooled_cv_validation_oof",**scores[ck]))
            for f in ff:oof_export.extend(dict(task_id=task,variant=variant,fold=f["job"]["fold"],**r) for r in f["predictions"])
    paired=aggregate(deltas,("task_id","checkpoint"),tuple(m+"_delta_pp" for m in METRICS))
    for r in paired:
        subset=[x for x in deltas if x["task_id"]==r["task_id"] and x["checkpoint"]==r["checkpoint"]]
        for metric in ("buggy_f1","macro_f1"):
            vals=[x[metric+"_delta_pp"] for x in subset]
            r[metric+"_improved"]=sum(x>1e-10 for x in vals)
            r[metric+"_tied"]=sum(abs(x)<=1e-10 for x in vals)
            r[metric+"_declined"]=sum(x< -1e-10 for x in vals)
    baseline_rows=[];historical_deltas=[];baseline_audit=[]
    inventory=read_json(output/"baseline_inventory.json")
    for job in inventory["jobs"]:
        task=job["cohort"]+"_"+job["task"];fold=job["fold"]
        match=next(f for f in fits if f["job"]["task_id"]==task and f["job"]["fold"]==fold and f["job"]["variant"]=="E2")
        config=read_json(job["effective_config"])
        for key,value in match["info"]["config"].items():
            if key not in ("mode","maximum_training_epochs") and config.get(key)!=value:raise ValueError("Baseline numeric configuration differs: "+key)
        for variant in ("E0","E1"):
            spec=job["variants"][variant];paths=spec["paths"]
            for key,p in paths.items():
                h=spec["hashes_from_receipt"].get(key)
                if h is None or sha256(p)!=h:raise ValueError("Baseline receipt asset differs: "+p)
            pred=read_json(paths["cv_validation_predictions.json"]);result=read_json(paths["result.json"])
            binding=read_json(paths["binding.json"])
            if binding["split"]!=match["info"]["split"]:raise ValueError("Baseline split differs")
            compare_rows(pred,match["predictions"],{"checkpoint":"best"})
            for ck in ("best","last"):
                metrics=g._metrics([r["target"] for r in pred],[r[ck] for r in pred]);g._assert_metrics(result["cv_validation"][ck],metrics,"baseline")
                baseline_rows.append(dict(task_id=task,fold=fold,variant=variant,checkpoint=ck,comparison_role="historical_reference",**metrics))
                for new in ("E2","E3b"):
                    now=next(f for f in fits if f["job"]["task_id"]==task and f["job"]["fold"]==fold and f["job"]["variant"]==new)
                    row={"task_id":task,"fold":fold,"checkpoint":ck,"contrast":new+"-"+variant,"comparison_role":"historical_same_fold_not_common_initialized"}
                    row.update({m+"_delta_pp":now["scores"][ck][m]-metrics[m] for m in METRICS});historical_deltas.append(row)
            baseline_audit.append({"task_id":task,"fold":fold,"variant":variant,"same_scored_targets_and_ids":True,
                "same_numeric_config":True,"same_split":True,"old_initialization_version":binding.get("initialization_version"),
                "new_initialization_version":"state-forward-semantic-paired-v1/triple-chain-v1",
                "common_initial_parameters_proven_identical":False,"not_a_strict_new_three_variant_pair":True})
    outputs={"summary.csv":g._csv(summary["best"]),"last_summary.csv":g._csv(summary["last"]),
        "fold_statistics.csv":g._csv(aggregate(summary["best"],("task_id","variant"))),
        "last_fold_statistics.csv":g._csv(aggregate(summary["last"],("task_id","variant"))),
        "paired_deltas.csv":g._csv(deltas),"paired_statistics.csv":g._csv(paired),
        "pooled_oof.csv":g._csv(pool),"oof_predictions.json":json.dumps(oof_export,indent=2)+"\n",
        "error_changes.csv":g._csv(errors),"baseline_folds.csv":g._csv(baseline_rows),
        "baseline_statistics.csv":g._csv(aggregate(baseline_rows,("task_id","variant","checkpoint"))),
        "historical_baseline_deltas.csv":g._csv(historical_deltas),
        "baseline_comparison_audit.json":json.dumps(baseline_audit,indent=2)+"\n"}
    report={"status":"complete","score_role":"cv_validation","fits":60,"new":52,"reused":8,"h2_trained":False,
            "fold_counts":{t:5 if t.endswith("_contract") else 10 for t in TASK_ORDER},
            "paired_statistics":paired,"equal_fold_means":aggregate(summary["best"],("task_id","variant")),
            "pooled_oof":pool,"plan_sha256":sha256(output/"plan.json"),
            "limitations":["Same val selects and scores checkpoint; OOF is not independent test.",
              "One seed; no seven-class or cross-dataset generalization claim.",
              "Baseline E0/E1 are historical references; common initial parameters across old/new not proven identical."]}
    outputs["report.json"]=json.dumps(report,indent=2)+"\n"
    for name,contents in outputs.items():
        p=output/name
        if p.exists() and p.read_text()!=contents:raise FileExistsError("Do not overwrite differing summary: "+name)
    for name,contents in outputs.items():
        p=output/name
        if not p.exists():p.write_text(contents,encoding="utf8")
    return report
