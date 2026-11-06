from pathlib import Path
import collections,json,math
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,ref,checked,write
r=Path("scripts/node_sem/artifacts/batch_NB_v1");p=read(r/"plan.json")
counts=collections.Counter();ranges={}
for j in p["jobs"]:
 if j["name"]=="S3":
  t=j["task_id"];s=j["support"]
  ranges.setdefault(t,[]).append(dict(fold=j["fold"],v2_training_edges=s["v2_training_edges"],ddg_training_edges=s["ddg_training_edges"],registered_no_train=len(s["registered_without_train_relations"])))
for item in read(r/"complete.json")["receipts"]:
 receipt=read(checked(item))
 g=next(x for x in receipt["artifacts"] if x["path"].endswith("/gradient_audit.json"))
 grad=read(checked(g))
 for epoch in grad["epochs"]:
  for rel in epoch.get("v2_relations",[]):
   counts[rel["status"]]+=1
   for key in ("message_gradient_l1","attention_gradient_l1"):
    assert math.isfinite(rel[key])
write(r/"analysis_checks/support_summary.json",dict(passed=True,gradient_status_counts=dict(counts),support_by_fold=ranges,finite_gradients=True))
print(json.dumps(dict(counts=counts,ranges=ranges)))
