"""Read-only analysis of completed H1 receipts. No model loading, training or input mutation."""
import csv,json,math,statistics,hashlib
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def write(name,value):
 p=ROOT/name
 text=json.dumps(value,indent=2,ensure_ascii=False)+"\n"
 if p.exists() and p.read_text()!=text:raise ValueError("Refuse differing analysis output: "+name)
 if not p.exists():p.write_text(text,encoding="utf8")
def csvwrite(name,rows):
 import io
 s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 p=ROOT/name
 if p.exists() and p.read_text()!=s.getvalue().replace("\r\n","\n"):raise ValueError("Refuse differing CSV: "+name)
 if not p.exists():p.write_text(s.getvalue(),encoding="utf8")
def metrics(rows,ck):
 tn=sum(r["target"]==0 and r[ck]==0 for r in rows);fp=sum(r["target"]==0 and r[ck]==1 for r in rows)
 fn=sum(r["target"]==1 and r[ck]==0 for r in rows);tp=sum(r["target"]==1 and r[ck]==1 for r in rows)
 div=lambda a,b:100*a/b if b else 0.0
 bf=div(2*tp,2*tp+fp+fn);cf=div(2*tn,2*tn+fp+fn)
 return dict(n=len(rows),positive=tp+fn,tn=tn,fp=fp,fn=fn,tp=tp,buggy_f1=bf,macro_f1=(bf+cf)/2,precision=div(tp,tp+fp),recall=div(tp,tp+fn))
def main():
 report=read(ROOT/"report.json");assert report["status"]=="complete" and report["fits"]==60
 plan=read(ROOT/"plan.json");fits={};resources=[];gradients=[];checks=[]
 for j in plan["jobs"]:
  a=Path(j["stage_g_receipt"]).parent if j["source"]=="stage_g_reuse" else ROOT/"runs"/j["task_id"]/("fold_"+str(j["fold"]))/j["variant"]/"attempt_001"
  assert (a/"receipt.json").exists()
  r=read(a/"result.json");pred=read(a/"cv_validation_predictions.json");info=read(j["task_manifest"])
  fits[(j["task_id"],j["fold"],j["variant"])]=(r,pred,info)
  assert all(r["checkpoint_roundtrip_exact"].values()) and r["no_parameters_created_during_training_or_scoring"]
  h=[json.loads(line) for line in (a/"history.jsonl").read_text().splitlines() if line.strip()]
  checks.append(dict(task_id=j["task_id"],fold=j["fold"],variant=j["variant"],source=j["source"],history_rows=len(h),
    best_reload_exact=r["checkpoint_roundtrip_exact"]["best"],last_reload_exact=r["checkpoint_roundtrip_exact"]["last"],
    no_new_parameters=r["no_parameters_created_during_training_or_scoring"]))
  for ck in ("best","last"):
   m=metrics(pred,ck)
   for key in ("buggy_f1","macro_f1","precision","recall"):assert abs(m[key]-r["cv_validation"][ck][key])<1e-8
  samples=r["resource"]["card"]["samples"]
  resources.append(dict(task_id=j["task_id"],fold=j["fold"],variant=j["variant"],source=j["source"],
   parameters=r["parameters"],best_epoch_0based=r["best_epoch"],last_epoch_0based=r["last_epoch"],
   epochs=r["history_rows"],stop_reason=r["stop_reason"],seconds_monotonic=r["wall_seconds_monotonic"],
   peak_allocated_gib=r["resource"]["peak_allocated_bytes"]/2**30,peak_reserved_gib=r["resource"]["peak_reserved_bytes"]/2**30,
   min_card_free_mib=min(s["free_mib"] for s in samples),attempt=str(a)))
  gs={}
  for epoch in r["gradient_audit"]["epochs"]:
   for e in epoch["enhancement_relations"]:
    key=tuple(e["canonical"])
    if key not in gs:gs[key]=dict(train=e["train_edges"],val=e["val_edges"],msg=[],att=[],pri=[],statuses=Counter())
    z=gs[key];assert (z["train"],z["val"])==(e["train_edges"],e["val_edges"])
    for bank in ("msg","att","pri"):
     value=e["relation_"+bank+"_gradient_l1"];assert math.isfinite(value)
     z[bank].append(value)
    z["statuses"][e["status"]]+=1
  for canonical,z in sorted(gs.items()):
   gradients.append(dict(task_id=j["task_id"],fold=j["fold"],variant=j["variant"],canonical=json.dumps(canonical),
     relation=canonical[1],train_edges=z["train"],val_edges=z["val"],registered=True,
     epochs_observed=len(z["msg"]),max_message_gradient_l1=max(z["msg"]),sum_message_gradient_l1=sum(z["msg"]),
     max_attention_gradient_l1=max(z["att"]),max_priority_gradient_l1=max(z["pri"]),
     ever_message_gradient_nonzero=any(x>0 for x in z["msg"]),ever_any_gradient_nonzero=any(x>0 for k in ("msg","att","pri") for x in z[k]),
     statuses=json.dumps(z["statuses"],sort_keys=True)))
 tasks=list(dict.fromkeys(j["task_id"] for j in plan["jobs"]));files=[];pair_summary=[]
 for task in tasks:
  k=5 if task.endswith("_contract") else 10
  for ck in ("best","last"):
   total=Counter();prob=[];target_counts=Counter()
   for fold in range(k):
    a=fits[(task,fold,"E2")][1];b=fits[(task,fold,"E3b")][1];byfile=defaultdict(lambda:([],[]))
    for x,y in zip(a,b):
     assert all(x.get(key)==y.get(key) for key in ("file","original_graph_node_id","target","node_type"))
     aa,bb=byfile[x["file"]];aa.append(x);bb.append(y)
    assert len(a)==len(b)
    for file,(aa,bb) in sorted(byfile.items()):
     ma=metrics(aa,ck);mb=metrics(bb,ck);counts=Counter();d=[]
     for x,y in zip(aa,bb):
      t=x["target"];pa=x[ck];pb=y[ck]
      c="fixed" if pa!=t and pb==t else "regressed" if pa==t and pb!=t else "both_correct" if pa==t else "both_wrong"
      counts[c]+=1
      if c=="fixed":counts["fixed_fn" if t else "fixed_fp"]+=1
      if c=="regressed":counts["new_fn" if t else "new_fp"]+=1
      delta=abs(y[ck+"_positive_probability"]-x[ck+"_positive_probability"]);d.append(delta)
      counts["probability_changed"]+=delta>0
      counts["probability_only_changed"]+=(delta>0 and pa==pb)
      counts["prediction_changed"]+=pa!=pb
     total.update(counts);prob.extend(d);target_counts["n"]+=len(aa)
     row=dict(task_id=task,fold=fold,checkpoint=ck,file=file,n=len(aa),positive=ma["positive"],
       E2_buggy_f1=ma["buggy_f1"],E3b_buggy_f1=mb["buggy_f1"],E2_fp=ma["fp"],E2_fn=ma["fn"],
       E3b_fp=mb["fp"],E3b_fn=mb["fn"],E2_errors=ma["fp"]+ma["fn"],E3b_errors=mb["fp"]+mb["fn"])
     row.update({key:counts[key] for key in ("fixed","regressed","fixed_fn","fixed_fp","new_fn","new_fp","prediction_changed","probability_changed")})
     row.update(mean_absolute_probability_delta=statistics.mean(d),max_absolute_probability_delta=max(d))
     files.append(row)
   pair_summary.append(dict(task_id=task,checkpoint=ck,n=target_counts["n"],
     **{key:total[key] for key in ("both_correct","both_wrong","fixed","regressed","fixed_fn","fixed_fp","new_fn","new_fp","prediction_changed","probability_changed","probability_only_changed")},
     mean_absolute_probability_delta=statistics.mean(prob),max_absolute_probability_delta=max(prob),
     probability_changes_at_least_001=sum(x>=.01 for x in prob),probability_changes_at_least_01=sum(x>=.1 for x in prob)))
 resource_summary=[]
 for task in tasks:
  for v in ("E2","E3b"):
   rows=[r for r in resources if r["task_id"]==task and r["variant"]==v]
   resource_summary.append(dict(task_id=task,variant=v,folds=len(rows),parameters=sorted(set(r["parameters"] for r in rows)),
    fit_seconds_sum=sum(r["seconds_monotonic"] for r in rows),fit_seconds_mean=statistics.mean(r["seconds_monotonic"] for r in rows),
    peak_allocated_gib=max(r["peak_allocated_gib"] for r in rows),peak_reserved_gib=max(r["peak_reserved_gib"] for r in rows),
    min_card_free_mib=min(r["min_card_free_mib"] for r in rows),epochs_min=min(r["epochs"] for r in rows),epochs_max=max(r["epochs"] for r in rows)))
 issues=[g for g in gradients if g["train_edges"]>0 and not g["ever_any_gradient_nonzero"]]
 no_support=[g for g in gradients if g["train_edges"]==0]
 analysis=dict(status="complete",score_role="cv_validation",pair_prediction_summary=pair_summary,resource_summary=resource_summary,
  gradient_summary=dict(rows=len(gradients),with_train_support=sum(g["train_edges"]>0 for g in gradients),
    no_train_support=len(no_support),with_train_support_but_no_observed_gradient=issues,
    no_train_support_with_nonzero_gradient=[g for g in no_support if g["ever_any_gradient_nonzero"]]),
  fits_checked=len(checks),new_fit_seconds=sum(r["seconds_monotonic"] for r in resources if r["source"]!="stage_g_reuse"),
  limitations=["Postprocessing only; no training/model code change.","Gradients prove computational use, not semantic or causal validity.",
   "Parameter updates can include weight decay; gradient histories are checked separately.",
   "Timing includes different epochs and changing Windows GPU competition; not a controlled speed benchmark."])
 csvwrite("file_error_analysis.csv",files);csvwrite("prediction_change_summary.csv",pair_summary)
 csvwrite("gradient_support_detail.csv",gradients);csvwrite("resource_folds.csv",resources)
 write("postprocessing_checks.json",checks);write("analysis.json",analysis)
 print(json.dumps(analysis,indent=2)[:22000])
if __name__=="__main__":main()
