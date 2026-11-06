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
summary=[]
for (task,profile,ck),v in sorted(groups.items()):
 non=[x for x in pooled[(task,profile)] if x["cohort"]=="nonSolidiFI"]
 z=dict(task=task,profile=profile,checkpoint=ck,mean=statistics.mean(v),sd=statistics.stdev(v),folds=v,nonSolidiFI=scored(non,ck))
 summary.append(z)
 if ck=="best":print(task,profile,round(z["mean"],5),round(z["sd"],5),"non",z["nonSolidiFI"]["tp"],z["nonSolidiFI"]["fp"],z["nonSolidiFI"]["fn"],round(z["nonSolidiFI"]["buggy_f1"],4),flush=True)
write(r/"analysis_metric_recompute.json",dict(passed=True,summary=summary,formal_fits=360))
