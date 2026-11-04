"""Recompute frozen-label fold-0 metrics and paired prediction changes."""
import csv,pickle
from pathlib import Path
from .common import *
from .control import completed
from scripts.DFG.experiments.common import metrics
def summarize(output):
 output=Path(output);plan=verify_plan(output);rows=[];comparisons=[];allchanges=[]
 for task in plan["tasks"]:
  info=read_json(task["manifest"]);indices={};resultmap={}
  with Path(info["graphs"]["B0"]["path"]).open("rb") as f:g=pickle.load(f)
  expected={(d["source_file"],n):int(d["node_info_vulnerabilities"] is not None)
            for n,d in g.nodes(data=True) if d["source_file"] in info["split"]["val_files"]}
  prepared=read_json(info["source_prepared_manifest"])
  for v in VARIANTS:
   folder=completed(output,{"task_id":task["task_id"],"variant":v,"fold":0},plan)
   if folder is None:raise ValueError("Missing fit")
   pred=read_json(folder/"cv_validation_predictions.json");idx={}
   for p in pred:
    key=(p["file"],p["original_graph_node_id"])
    if key in idx or key not in expected or p["target"]!=expected[key] or p["score_role"]!="cv_validation":
     raise ValueError("Prediction identity/label mismatch")
    idx[key]=p
   if set(idx)!=set(expected):raise ValueError("Missing validation nodes")
   indices[v]=idx;result=read_json(folder/"result.json");resultmap[v]=result
   for ck in ("best","last"):
    ordered=sorted(expected)
    m=metrics([expected[k] for k in ordered],[idx[k][ck] for k in ordered])
    if m!=result["cv_validation"][ck]:raise ValueError("Independent metric mismatch")
    rows.append(dict(task_id=task["task_id"],variant=v,checkpoint=ck,fold=0,score_role="cv_validation",
      **m,best_epoch=result["best_epoch"],last_epoch=result["last_epoch"],parameters=result["parameters"],
      seconds=result["wall_seconds_monotonic"],peak_allocated_mib=result["resource"]["peak_allocated_bytes"]/1048576,
      peak_reserved_mib=result["resource"]["peak_reserved_bytes"]/1048576,
      min_card_free_mib=result["resource"]["card"]["minimum_whole_card_free_mib"]))
  for ck in ("best","last"):
   changes=[]
   for k,y in expected.items():
    a,b=indices["B0"][k],indices["B1"][k];delta=b[ck+"_positive_probability"]-a[ck+"_positive_probability"]
    status="corrected" if a[ck]!=y and b[ck]==y else "regressed" if a[ck]==y and b[ck]!=y else "both_correct" if a[ck]==y else "both_wrong"
    record={"task_id":task["task_id"],"checkpoint":ck,"file":k[0],"source_sha256":prepared["sources"][k[0]]["sha256"],
      "node_id":k[1],"target":y,"B0":a[ck],"B1":b[ck],"probability_delta":delta,"status":status}
    changes.append(record);allchanges.append(record)
   comparison={"task_id":task["task_id"],"checkpoint":ck,"fold":0,
      "delta_pp":{k:resultmap["B1"]["cv_validation"][ck][k]-resultmap["B0"]["cv_validation"][ck][k]
       for k in ("buggy_f1","macro_f1","precision","recall")},
      "corrected":sum(x["status"]=="corrected" for x in changes),
      "regressed":sum(x["status"]=="regressed" for x in changes),
      "probability_changes":sum(abs(x["probability_delta"])>1e-8 for x in changes)}
   comparisons.append(comparison)
 for name,data in [("results.csv",rows),("prediction_changes.csv",allchanges)]:
  with (output/name).open("w",newline="") as f:
   w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 write_json(output/"paired_results.json",comparisons)
 write_json(output/"summary.json",{"status":"complete","formal_fits":4,"tasks":2,"folds_per_task":1,
      "score_role":"cv_validation","independent_test":False,"metrics":rows,"paired":comparisons,
      "baseline":"fresh current paired B0 uses frozen old E3b graph; not copied historical model score",
      "hard_files_in_validation":{t["task_id"]:sorted(set(read_json(t["manifest"])["split"]["val_files"])&
             {"buggy_18.sol","buggy_36.sol","buggy_26.sol"}) for t in plan["tasks"]}})
 print(comparisons)
 return comparisons
