from pathlib import Path
from collections import defaultdict
import statistics,json
from scripts.node_sem import nb_reporting as n, batch_nb_worker as w
from scripts.node_sem.reporting import manifest_attempts,read_artifact,aligned_rows
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,checked,write
from scripts.DFG.dfg_v2.benchmark_v2.reporting import scored
r=w.OUT;plan=read(r/"plan.json");old=read(checked(plan["na_parent"]["plan"]));nr=Path(plan["na_parent"]["plan"]["path"]).parent
entries=manifest_attempts(nr,old)
for ref in read(r/"complete.json")["receipts"]:
 rec=read(checked(ref));entries[w.job_id(rec["job"])]=(Path(ref["path"]).parent,rec)
label=read(checked(plan["jobs"][0]["label_view"]));groups=defaultdict(list);pooled=defaultdict(list)
for j in old["jobs"]+plan["jobs"]:
 e=entries[w.job_id(j)];rows=aligned_rows(read_artifact(e,"outer_test_predictions.json"),j,label)
 for ck in ("best","last"):
  groups[(j["task_id"],j["profile"]+"/"+j["name"],ck)].append(scored(rows,ck)["buggy_f1"])
 pooled[(j["task_id"],j["profile"]+"/"+j["name"])].extend(rows)
audit=[]
for task in sorted({k[0] for k in pooled}):
 for a,b in [("G3R/S3","G3R/S2"),("G3R/S4","G3R/S3"),("G3R/S4g","G3R/S4"),("G3R/S4m","G3R/S4")]:
  c=dict(task=task,left=a,right=b,samples=0,probability_changed=0,class_changed=0,corrected=0,new_error=0)
  for x,y in n.paired_rows(pooled[(task,a)],pooled[(task,b)],task.rsplit("_",1)[-1]):
   c["samples"]+=1;c["probability_changed"]+=x["best_positive_probability"]!=y["best_positive_probability"]
   c["class_changed"]+=x["best"]!=y["best"]
   c["corrected"]+=x["best"]==x["target"] and y["best"]!=x["target"]
   c["new_error"]+=x["best"]!=x["target"] and y["best"]==x["target"]
  audit.append(c);print(c,flush=True)
write(r/"analysis_checks/prediction_delta_check.json",dict(passed=True,comparisons=audit))
