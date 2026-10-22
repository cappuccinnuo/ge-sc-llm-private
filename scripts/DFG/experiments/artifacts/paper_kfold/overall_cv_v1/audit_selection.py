"""Read-only final selection/config/history audit; writes only an audit artifact."""
import json,math
from pathlib import Path
B=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
plan=read(B/"plan.json")
rows=[]
for job in plan["jobs"]:
 t=job["task_id"];f=job["fold"];v=job["variant"]
 root=B/"runs"/t/("fold_"+str(f))/v
 recs=list(root.glob("attempt_*/receipt.json"))
 assert len(recs)==1,(job,len(recs))
 p=recs[0].parent
 d=read(p/"result.json");c=read(p/"effective_config.json")
 h=[json.loads(x) for x in (p/"history.jsonl").read_text().splitlines()]
 assert [x["epoch"] for x in h]==list(range(len(h))),job
 idx=min(range(len(h)),key=lambda i:h[i]["cv_validation_loss"])
 assert idx==d["best_epoch"],(job,idx,d["best_epoch"])
 assert len(h)-1==d["last_epoch"] and len(h)==d["history_rows"],job
 assert h[idx]["cv_validation_loss"]==d["best_cv_validation_loss"],job
 assert c["maximum_training_epochs"]==50 and c["patience"]==7 and c["delta"]==0.001,job
 contract=t.endswith("_contract")
 assert c["initial_lr"]==(0.0005 if contract else 0.0002),job
 assert c["max_lr"]==(0.01 if contract else 0.005),job
 assert c["weight_decay"]==(5e-6 if contract else 0),job
 assert c["score_role"]=="cv_validation" and c["forward_scope"]=="complete_fixed_task_graph",job
 assert c["hidden_size"]==128 and c["layers"]==2 and c["heads"]==8 and c["feature"]=="inside_token",job
 assert all(math.isfinite(x[k]) for x in h for k in ("train_loss","cv_validation_loss","lr")),job
 assert d["gradient_audit"]["backbone_update_l1"]>0,job
 assert all(math.isfinite(e[k]) for e in d["gradient_audit"]["epochs"] for k in ("backbone_gradient_l1","classifier_gradient_l1")),job
 assert d["checkpoint_roundtrip_exact"]=={"best":True,"last":True},job
 assert d["no_parameters_created_during_training_or_scoring"],job
 rows.append(dict(job,attempt=p.name,epochs=len(h),minimum_loss_epoch=idx,last_epoch=d["last_epoch"],best_selection_correct=True,backbone_updated=True,checkpoints_exact=True))
assert len(rows)==60
assert all(x["attempt"]=="attempt_001" for x in rows)
out=dict(status="passed",fits=len(rows),checkpoint_roundtrips=120,strict_minimum_selection_verified=True,finite_history=True,attempts=rows)
(B/"final_selection_audit.json").write_text(json.dumps(out,indent=2)+"\n")
print("SELECTION_CONFIG_HISTORY_AUDIT PASSED",len(rows),"fits",120,"checkpoint roundtrips")
