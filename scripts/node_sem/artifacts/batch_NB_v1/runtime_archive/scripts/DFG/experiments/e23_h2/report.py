"""Read-only complete three-variant ablation. Identity-keyed prediction comparison."""
import json, math, statistics
from pathlib import Path
from collections import Counter, defaultdict
from scripts.DFG.experiments.common import read_json, sha256, digest
from scripts.DFG.experiments.e23_pilot import report as g
from scripts.DFG.experiments.e23_cv import report as hreport, control as hc
from scripts.DFG.experiments.e23_pilot.inputs import TASK_ORDER
from . import H1
from . import control
METRICS = g.METRICS
CONTRASTS = (("E2","E3a"),("E3a","E3b"),("E2","E3b"))

def row_key(row):
    return (row["file"], json.dumps(row.get("original_graph_node_id"),sort_keys=True))

def align(rows, expected):
    index = {}
    for row in rows:
        key=row_key(row)
        if key in index: raise ValueError("Duplicate prediction identity")
        if row.get("score_role") != "cv_validation": raise ValueError("Mixed scoring role")
        index[key]=row
    if set(index) != {row_key(x) for x in expected}: raise ValueError("Prediction population differs")
    ordered=[]
    for truth in sorted(expected,key=row_key):
        row=index[row_key(truth)]
        if any(row.get(k)!=v for k,v in truth.items()): raise ValueError("Identity/target mismatch")
        ordered.append(row)
    return ordered

def validate_matrix(fits):
    actual=[(f["job"]["task_id"],f["job"]["fold"],f["job"]["variant"]) for f in fits]
    expected=hc.expected_jobs(("E2","E3a","E3b"))
    if len(actual)!=90 or len(set(actual))!=90 or set(actual)!=set(expected):
        raise ValueError("Missing/duplicate three-variant fits")

def read_fit(output,job,plan,cache):
    folder,attempts=control.locate(output,job,plan)
    if folder is None: raise ValueError("Incomplete fit")
    info=read_json(g._checked(job["task_manifest"],job["task_manifest_sha256"]))
    for key in ("task_id","fold","task","cohort"):
        if info[key]!=job[key]: raise ValueError("Task identity mismatch")
    receipt=read_json(folder/"receipt.json")
    required={"result.json","binding.json","history.jsonl","cv_validation_predictions.json",
              "best.pt","last.pt","effective_config.json","schema_support_audit.json"}
    if not required<=set(receipt["artifact_sha256"]): raise ValueError("Incomplete receipt")
    result=read_json(folder/"result.json");config=read_json(folder/"effective_config.json")
    binding=read_json(folder/"binding.json")
    if any(config.get(k)!=v for k,v in info["config"].items()): raise ValueError("Effective task config differs")
    if binding["effective_config_sha256"]!=digest(config): raise ValueError("Config binding differs")
    if binding["protocol"]!="paper_kfold" or binding["score_role"]!="cv_validation": raise ValueError("Wrong protocol")
    if binding["registered_schema"]!=info["support"][job["variant"]]["schema"]: raise ValueError("Schema binding differs")
    if read_json(folder/"schema_support_audit.json")!=info["support"][job["variant"]]: raise ValueError("Support differs")
    key=(job["task_id"],job["fold"])
    if key not in cache: cache[key]=g._expected_population(info)
    rows=align(read_json(folder/"cv_validation_predictions.json"),cache[key])
    scores={}
    for ck in ("best","last"):
        for row in rows:
            prob=row[ck+"_positive_probability"]
            if not math.isfinite(prob) or not 0<=prob<=1: raise ValueError("Invalid probability")
        scores[ck]=g._metrics([x["target"] for x in rows],[x[ck] for x in rows])
        g._assert_metrics(result["cv_validation"][ck],scores[ck],"independent H2 recomputation")
    return {"job":job,"info":info,"result":result,"scores":scores,"predictions":rows,
            "attempt":str(folder),"receipt_sha256":sha256(folder/"receipt.json"),
            "attempts":[str(p) for p in attempts]}

def store_outputs(output,outputs):
    output=Path(output)
    for name,value in outputs.items():
        p=output/name
        if p.exists() and p.read_text(encoding="utf8")!=value:
            raise FileExistsError("Refuse differing summary: "+str(p))
    for name,value in outputs.items():
        p=output/name
        if not p.exists():p.write_text(value,encoding="utf8")

def summarize(output):
    output=Path(output);plan=control.verify_plan(output)
    if control.verify(output)["total_complete"]!=30: raise ValueError("Incomplete E3a")
    old=read_json(H1/"plan.json");cache={}
    fits=[read_fit(H1,j,old,cache) for j in old["jobs"]]
    fits += [read_fit(output,j,plan,cache) for j in plan["jobs"]]
    fits.sort(key=lambda f:(TASK_ORDER.index(f["job"]["task_id"]),f["job"]["fold"],f["job"]["variant"]))
    validate_matrix(fits)
    summaries={ck:[g._summary_row(f,ck) for f in fits] for ck in ("best","last")}
    byid={(f["job"]["task_id"],f["job"]["fold"],f["job"]["variant"]):f for f in fits}
    sources={}
    for f in fits:
        task=f["job"]["task_id"]
        if task not in sources:
            prep=g._checked(f["info"]["source_prepared_manifest"],f["info"]["source_prepared_manifest_sha256"])
            sources[task]=read_json(prep)["sources"]
    deltas=[];changes=[];file_errors=[];pooled=[];oof=[];probsummary=[]
    support=[];gradients=[]
    for task in TASK_ORDER:
        k=5 if task.endswith("_contract") else 10
        for fold in range(k):
            for before,after in CONTRASTS:
                a,b=byid[(task,fold,before)],byid[(task,fold,after)]
                for ck in ("best","last"):
                    prefix={"task_id":task,"cohort":a["job"]["cohort"],"fold":fold,"checkpoint":ck,
                            "contrast":after+"-"+before,"score_role":"cv_validation"}
                    counts,details=hreport.compare_rows(a["predictions"],b["predictions"],prefix)
                    for row in details:
                        row["source_sha256"]=sources[task][row["file"]]["sha256"]
                    changes.extend(details)
                    row=dict(prefix,**counts)
                    for m in METRICS:row[m+"_delta_pp"]=b["scores"][ck][m]-a["scores"][ck][m]
                    deltas.append(row)
                    diffs=[abs(x[ck+"_positive_probability"]-y[ck+"_positive_probability"]) for x,y in zip(a["predictions"],b["predictions"])]
                    probsummary.append(dict(prefix,**counts,n=len(diffs),mean_abs_probability_delta=statistics.mean(diffs),
                        max_abs_probability_delta=max(diffs),probability_only=counts["probability_changed"]-counts["prediction_changed"]))
                    perfile=defaultdict(list)
                    for x,y in zip(a["predictions"],b["predictions"]):perfile[x["file"]].append((x,y))
                    for name,pairs in perfile.items():
                        cm1=g._metrics([x["target"] for x,y in pairs],[x[ck] for x,y in pairs])["tn_fp_fn_tp"]
                        cm2=g._metrics([y["target"] for x,y in pairs],[y[ck] for x,y in pairs])["tn_fp_fn_tp"]
                        fixed=sum(x[ck]!=x["target"] and y[ck]==y["target"] for x,y in pairs)
                        regressed=sum(x[ck]==x["target"] and y[ck]!=y["target"] for x,y in pairs)
                        file_errors.append(dict(prefix,file=name,source_sha256=sources[task][name]["sha256"],
                            n=len(pairs),positive=sum(x["target"] for x,y in pairs),
                            before_fp=cm1[1],before_fn=cm1[2],after_fp=cm2[1],after_fn=cm2[2],
                            before_errors=cm1[1]+cm1[2],after_errors=cm2[1]+cm2[2],fixed=fixed,regressed=regressed))
        for v in ("E2","E3a","E3b"):
            ff=[byid[(task,f,v)] for f in range(k)]
            scores,rows=hreport.pooled({f["job"]["fold"]:f["predictions"] for f in ff},k)
            doc=read_json(ff[0]["info"]["source_splits_path"])
            if set(x["file"] for x in rows)!=set(doc["files"]):raise ValueError("OOF file coverage mismatch")
            if ff[0]["info"]["task"]=="node" and len(rows)!=ff[0]["info"]["graphs"][v]["nodes"]: raise ValueError("OOF node coverage mismatch")
            for ck in ("best","last"):
                pooled.append(dict(task_id=task,variant=v,checkpoint=ck,score_role="pooled_cv_validation_oof",**scores[ck]))
            for fit in ff:
                for row in fit["predictions"]:
                    oof.append(dict(task_id=task,cohort=fit["job"]["cohort"],fold=fit["job"]["fold"],variant=v,
                                    source_sha256=sources[task][row["file"]]["sha256"],**row))
    for f in fits:
        prefix={k:f["job"][k] for k in ("task_id","cohort","fold","variant")}
        sup=f["info"]["support"][f["job"]["variant"]]
        for rel,value in sup["enhancement_support"].items():support.append(dict(prefix,relation=rel,**value))
        banks=defaultdict(list)
        for epoch in f["result"]["gradient_audit"]["epochs"]:
            for item in epoch["enhancement_relations"]:banks[tuple(item["canonical"])].append(item)
        for canonical,items in banks.items():
            total=sum(item[bank+"_gradient_l1"] for item in items for bank in ("relation_msg","relation_att","relation_pri"))
            gradients.append(dict(prefix,canonical=json.dumps(canonical),relation=canonical[1],
                train_edges=items[0]["train_edges"],val_edges=items[0]["val_edges"],
                gradient_l1_sum=total,nonzero_epochs=sum(any(x[bank+"_gradient_l1"]>0 for bank in ("relation_msg","relation_att","relation_pri")) for x in items),
                finite=all(math.isfinite(x[bank+"_gradient_l1"]) for x in items for bank in ("relation_msg","relation_att","relation_pri")),
                status="no_training_support" if items[0]["train_edges"]==0 else "supported_nonzero" if total>0 else "supported_zero"))
    paired=hreport.aggregate(deltas,("task_id","checkpoint","contrast"),tuple(m+"_delta_pp" for m in METRICS))
    for row in paired:
        items=[x for x in deltas if all(x[k]==row[k] for k in ("task_id","checkpoint","contrast"))]
        for m in ("buggy_f1","macro_f1"):
            vals=[x[m+"_delta_pp"] for x in items]
            row[m+"_improved"]=sum(x>1e-10 for x in vals)
            row[m+"_tied"]=sum(abs(x)<=1e-10 for x in vals)
            row[m+"_declined"]=sum(x< -1e-10 for x in vals)
    stats={ck:hreport.aggregate(summaries[ck],("task_id","variant")) for ck in ("best","last")}
    report={"status":"complete","new_E3a":26,"reused_E3a":4,"complete_E3a":30,"complete_three_variants":90,
        "score_role":"cv_validation","metrics_independently_recomputed":True,"identity_keyed_alignment":True,
        "plan_sha256":sha256(output/"plan.json"),"paired_statistics":paired,
        "best_statistics":stats["best"],"last_statistics":stats["last"],
        "gradient_status":dict(Counter(x["status"] for x in gradients)),
        "nonfinite_gradient_records":sum(not x["finite"] for x in gradients),
        "accepted":[{"task_id":f["job"]["task_id"],"fold":f["job"]["fold"],"variant":f["job"]["variant"],
                     "attempt":f["attempt"],"receipt_sha256":f["receipt_sha256"]} for f in fits],
        "limitations":["Same validation fold selects and scores; pooled OOF is not independent test.",
          "One seed; fold SD descriptive, not independent seed variance.",
          "Parameter/schema aggregation/optimization differences are part of each contrast, not pure semantic causality.",
          "Reentrancy E3b combines two order relations; access_control has no call-before-write edges.",
          "Historical E0/E1 do not have proven identical shared initialization."]}
    outputs={"summary.csv":g._csv([x for x in summaries["best"] if x["variant"]=="E3a"]),
        "last_summary.csv":g._csv([x for x in summaries["last"] if x["variant"]=="E3a"]),
        "three_variant_best.csv":g._csv(summaries["best"]),"three_variant_last.csv":g._csv(summaries["last"]),
        "fold_statistics.csv":g._csv(stats["best"]),"last_fold_statistics.csv":g._csv(stats["last"]),
        "paired_deltas.csv":g._csv(deltas),"paired_statistics.csv":g._csv(paired),
        "pooled_oof.csv":g._csv(pooled),"oof_predictions.json":json.dumps(oof,indent=2)+"\n",
        "error_changes.csv":g._csv(changes),"file_error_analysis.csv":g._csv(file_errors),
        "prediction_change_summary.csv":g._csv(probsummary),"enhancement_support.csv":g._csv(support),
        "gradient_support_detail.csv":g._csv(gradients),"resource_folds.csv":g._csv(summaries["best"]),
        "report.json":json.dumps(report,indent=2)+"\n"}
    store_outputs(output,outputs)
    return report
