"""Independent complete-fold statistics, OOF identities and error changes."""
import csv,json,pickle,math
from collections import defaultdict,Counter
from pathlib import Path
from scripts.DFG.experiments.common import metrics
from scripts.DFG.experiments.e23_cv.report import aggregate,pooled,compare_rows,METRICS
from .common import *
from .checks import completed
def key(row):return (row["file"],json.dumps(row.get("original_graph_node_id"),sort_keys=True))
def expected_population(info,g):
 files=set(info["split"]["val_files"])
 if info["task"]=="node":
  return {(a["source_file"],json.dumps(n,sort_keys=True)):int(a["node_info_vulnerabilities"] is not None)
          for n,a in g.nodes(data=True) if a["source_file"] in files}
 labels={r["contract_name"]:int(r["targets"]) for r in read_json(info["labels_path"])}
 return {(f,json.dumps(None)):labels[f] for f in files}
def checked_predictions(rows,expected):
 index={}
 for row in rows:
  k=key(row)
  if k in index or k not in expected or row["target"]!=expected[k]:raise ValueError("Prediction population/label mismatch")
  if row.get("score_role")!="cv_validation":raise ValueError("Mixed scoring role")
  for ck in ("best","last"):
   if row[ck] not in (0,1) or not math.isfinite(row[ck+"_positive_probability"]) or not 0<=row[ck+"_positive_probability"]<=1:raise ValueError("Invalid prediction")
  index[k]=row
 if set(index)!=set(expected):raise ValueError("Missing predictions")
 return [index[k] for k in sorted(index)]
def csv_write(path,rows):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 fields=list(dict.fromkeys(k for row in rows for k in row))
 with path.open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for row in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list,tuple)) else v for k,v in row.items()})
def summarize(output,tasks=TASKS):
 output=Path(output);plan=verify_plan(output)
 if not tasks or len(set(tasks))!=len(tasks) or any(t not in TASKS for t in tasks):raise ValueError("Unknown/duplicate summary tasks")
 dest=output if tuple(tasks)==TASKS else output/"reports"/tasks[0]
 dest.mkdir(parents=True,exist_ok=True)
 rows=[];deltas=[];errors=[];pools=[];oof=[];support=[];resources=[];file_errors=[];overlap=[]
 for tid in tasks:
  first=read_json(task_ref(plan,tid,0)["manifest"])
  with Path(first["graphs"]["HCG"]["path"]).open("rb") as f:g=pickle.load(f)
  sources=read_json(first["source_prepared_manifest"])["sources"]
  allpred={v:{} for v in VARIANTS}
  for fold in range(folds(tid)):
   info=read_json(task_ref(plan,tid,fold)["manifest"]);expected=expected_population(info,g);resultmap={}
   if info["task"]=="node":
    tr=set(info["split"]["train_files"]);va=set(info["split"]["val_files"])
    seen={(a["node_type"],a["code"]) for _,a in g.nodes(data=True) if a["source_file"] in tr}
    val=[a for _,a in g.nodes(data=True) if a["source_file"] in va];pos=[a for a in val if a["node_info_vulnerabilities"] is not None]
    overlap.append(dict(task_id=tid,fold=fold,validation_nodes=len(val),validation_positive_nodes=len(pos),
       exact_type_code_in_train=sum((a["node_type"],a["code"]) in seen for a in val),
       positive_exact_type_code_in_train=sum((a["node_type"],a["code"]) in seen for a in pos),
       interpretation="descriptive code overlap, not proof of causal memorization or isolated-template generalization"))
   for v in VARIANTS:
    job=dict(task_id=tid,fold=fold,variant=v);folder=completed(output,job,plan)
    if folder is None:raise ValueError("Missing formal fit: "+identity(job))
    result=read_json(folder/"result.json");resultmap[v]=result
    pred=checked_predictions(read_json(folder/"cv_validation_predictions.json"),expected);allpred[v][fold]=pred
    for ck in ("best","last"):
     m=metrics([x["target"] for x in pred],[x[ck] for x in pred])
     if m!=result["cv_validation"][ck]:raise ValueError("Independent metric mismatch")
     rows.append(dict(job,cohort=info["cohort"],task=info["task"],checkpoint=ck,score_role="cv_validation",
        **m,best_epoch=result["best_epoch"],last_epoch=result["last_epoch"],parameters=result["parameters"]))
     for file in sorted({x["file"] for x in pred}):
      rr=[x for x in pred if x["file"]==file]
      file_errors.append(dict(job,cohort=info["cohort"],checkpoint=ck,file=file,source_sha256=sources[file]["sha256"],
       nodes_or_files=len(rr),errors=sum(x[ck]!=x["target"] for x in rr),false_positive=sum(x[ck]==1 and x["target"]==0 for x in rr),
       false_negative=sum(x[ck]==0 and x["target"]==1 for x in rr)))
    records=defaultdict(list)
    for epoch in result["gradient_audit"]["epochs"]:
     for rec in epoch["enhancement_relations"]:records[tuple(rec["canonical"])].append(rec)
    for c,seq in sorted(records.items()):
     if any(not math.isfinite(x["message_gradient_l1"]) for x in seq):raise ValueError("Nonfinite relation gradient")
     support.append(dict(job,canonical=list(c),relation=c[1],train_edges=seq[0]["train_edges"],val_edges=seq[0]["val_edges"],
         max_message_gradient_l1=max(x["message_gradient_l1"] for x in seq),
         has_training_support=seq[0]["train_edges"]>0,observed_nonzero_gradient=any(x["message_gradient_l1"]>0 for x in seq)))
    resources.append(dict(job,parameters=result["parameters"],epochs=result["history_rows"],
      best_epoch=result["best_epoch"],last_epoch=result["last_epoch"],seconds=result["wall_seconds_monotonic"],
      peak_allocated_mib=result["resource"]["peak_allocated_bytes"]/1048576,
      peak_reserved_mib=result["resource"]["peak_reserved_bytes"]/1048576,
      minimum_card_free_mib=result["resource"]["card"]["minimum_whole_card_free_mib"],
      checkpoint_roundtrip_exact=all(result["checkpoint_roundtrip_exact"].values()),accepted_attempt=str(folder)))
    oof.extend(dict(job,cohort=info["cohort"],source_sha256=sources[x["file"]]["sha256"],**x) for x in pred)
   for ck in ("best","last"):
    prefix=dict(task_id=tid,cohort=info["cohort"],fold=fold,checkpoint=ck,contrast="HCG_DDG-HCG",score_role="cv_validation")
    counts,details=compare_rows(allpred["HCG"][fold],allpred["HCG_DDG"][fold],prefix)
    deltas.append(dict(prefix,**counts,**{m+"_delta_pp":resultmap["HCG_DDG"]["cv_validation"][ck][m]-resultmap["HCG"]["cv_validation"][ck][m] for m in METRICS}))
    errors.extend(dict(x,source_sha256=sources[x["file"]]["sha256"]) for x in details)
  for v in VARIANTS:
   scores,allrows=pooled(allpred[v],folds(tid));document=read_json(first["source_splits_path"])
   if {x["file"] for x in allrows}!=set(document["files"]):raise ValueError("Incomplete OOF file population")
   if first["task"]=="node" and len(allrows)!=len(g):raise ValueError("Incomplete OOF node population")
   for ck in ("best","last"):pools.append(dict(task_id=tid,variant=v,checkpoint=ck,score_role="pooled_cv_validation_oof",**scores[ck]))
 stats=aggregate(rows,("task_id","variant","checkpoint"))
 paired=aggregate(deltas,("task_id","checkpoint"),tuple(m+"_delta_pp" for m in METRICS))
 for row in paired:
  group=[x for x in deltas if x["task_id"]==row["task_id"] and x["checkpoint"]==row["checkpoint"]]
  for m in ("buggy_f1","macro_f1"):
   values=[x[m+"_delta_pp"] for x in group]
   row[m+"_improved"]=sum(x>1e-10 for x in values);row[m+"_tied"]=sum(abs(x)<=1e-10 for x in values);row[m+"_declined"]=sum(x< -1e-10 for x in values)
 tables={"fold_results.csv":rows,"fold_statistics.csv":stats,"paired_deltas.csv":deltas,"paired_statistics.csv":paired,
    "pooled_oof.csv":pools,"oof_predictions.csv":oof,"prediction_changes.csv":errors,"file_error_analysis.csv":file_errors,
    "relation_support_gradients.csv":support,"resources.csv":resources,"code_overlap.csv":overlap}
 for name,table in tables.items():csv_write(dest/name,table)
 report=dict(status="complete",tasks=list(tasks),formal_fits=sum(folds(t)*2 for t in tasks),score_role="cv_validation",independent_test=False,
   statistics=stats,paired=paired,pooled_oof=pools,resources=resources,
   interpretation="equal-fold means and sample SD; same validation selects and scores best; no independent-seed variance",
   graph_variant="original author CFG+CG versus frozen Stage K overall DDG; common fresh parameters",
   failures=list(str(p.relative_to(output)) for p in (output/"runs").rglob("*.failure.json")))
 write_json(dest/"report.json",report)
 print("SUMMARY_ACCEPTED",list(tasks),report["formal_fits"],flush=True)
 return dict(tasks=list(tasks),formal_fits=report["formal_fits"],output=str(dest))
