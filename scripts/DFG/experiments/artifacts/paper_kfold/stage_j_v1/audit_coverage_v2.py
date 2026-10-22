"""Read-only post-build opportunity audit; no new predictions or labels."""
import csv, json, pickle, hashlib
from pathlib import Path
from collections import Counter
from scripts.DFG.experiments.stage_i_diagnostics.evidence import context_features, raw_edges
ROOT=Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11")
B=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False))
def load(p):
 with Path(p).open("rb") as f:return pickle.load(f)
def rows(p):
 with Path(p).open() as f:return list(csv.DictReader(f))
def save(p,rs):
 with p.open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for row in rs for k in row)));w.writeheader();w.writerows(rs)
def main():
 out=B/"opportunity_v2"
 if out.exists():raise ValueError("No overwrite")
 out.mkdir()
 receipt=read(B/"build/receipt.json")
 for name,digest in receipt["files"].items():
  if sha(B/"build"/name)!=digest:raise ValueError("Build receipt mismatch: "+name)
 predpath=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/stage_i_v1/static/prediction_evidence.csv"
 predictions=rows(predpath)
 inputs={str(predpath):sha(predpath),str(B/"build/receipt.json"):sha(B/"build/receipt.json")}
 summary=[];file_rows=[];cases=[];totals=[];fallbacks=[]
 for task in read(read(B/"build/plan.json")["input_manifest"])["tasks"]:
  taskid=task["id"];p=B/"build"/taskid
  sourceinfo=read(p/"sources.json")["sources"]
  old=load(p/"frozen/enhanced.gpickle");new=load(p/"modifiers/enhanced.gpickle")
  audit=read(p/"modifiers/audit.json")
  features,edges,new_schema=context_features(old,new)
  cohort=read(p/"modifiers/manifest.json")["cohort"]
  sourcebytes={}
  for file,info in sourceinfo.items():
   if sha(info["path"])!=info["sha256"]:raise ValueError("Source mismatch")
   sourcebytes[file]=Path(info["path"]).read_bytes()
  # Current function totals exclude file-level frontend fallbacks; reconcile exactly.
  sidepaths=[Path(k) for k in read(B/"build/input_manifest.json")["inputs"] if k.endswith(cohort+"_results.json")]
  if len(sidepaths)!=1:raise ValueError("sidecar ambiguity")
  side=read(sidepaths[0]);diff=[]
  for file,a in audit["files"].items():
   before=side[file]["functions"];current=a["functions"]
   if len(before)!=len(current):
    diff.append({"file":file,"old_records":len(before),"current_analyzed_functions":len(current),
                 "current_file_status":a["status"],"current_reason":a.get("reason"),
                 "old_function_status_counts":dict(Counter(x["status"] for x in before))})
   for fn in current:
    if fn["after"]=="function_fallback":
     fallbacks.append({"task_id":taskid,"file":file,"source_sha256":sourceinfo[file]["sha256"],
                       "function":fn["function"],"name":fn["name"],
                       "reason":json.dumps(fn.get("after_diagnostics",fn.get("before_diagnostics",[])))})
  totals.append({"task_id":taskid,"old_records":sum(len(side[f]["functions"]) for f in sourceinfo),
                 "current_analyzed_functions":sum(len(a["functions"]) for a in audit["files"].values()),
                 "differences":diff})
  # Exact file + source SHA + node identity joins; old predictions remain historical.
  pred=[x for x in predictions if x["task_id"]==taskid and x["contrast"]=="E3b-E2" and x["checkpoint"]=="best"]
  ids={str(n):n for n in new}
  if len(ids)!=len(new):raise ValueError("Ambiguous serialized node ID")
  seen=set();errors={"E2":set(),"E3b":set()}
  isnode=taskid.endswith("_node")
  for x in pred:
   file=x["file"]
   if x["source_sha256"]!=sourceinfo[file]["sha256"] or x["score_role"]!="cv_validation":raise ValueError("Prediction identity drift")
   key=ids[x["original_graph_node_id"]] if isnode else file
   if key in seen:raise ValueError("Duplicate prediction")
   seen.add(key)
   if isnode:
    d=new.nodes[key]
    if d["source_file"]!=file or int(d["node_info_vulnerabilities"] is not None)!=int(x["target"]):
     raise ValueError("Prediction node/label drift")
   for name,col in (("E2","before_best"),("E3b","after_best")):
    if x[col]!=x["target"]:errors[name].add(key)
  if seen!=(set(new) if isnode else set(sourceinfo)):raise ValueError("Prediction population mismatch")
  scope={n for n,d in features.items() if d["potential_influence_within_two"]}
  context={n for n,d in features.items() if d["new_upstream_count_two"]>0}
  row={"task_id":taskid,"added_relations_vs_E3b":len(edges),"direct_targets":sum(d["direct_added_relation_target"] for d in features.values()),
       "potential_two_layer_scope":len(scope),"new_upstream_context_targets":len(context),"new_canonical_relations":len(new_schema)}
  if isnode:
   for v,es in errors.items():
    row.update({v+"_historical_errors":len(es),v+"_errors_in_added_scope":len(es&scope),v+"_errors_with_new_upstream_context":len(es&context)})
  summary.append(row)
  for file in sorted(sourceinfo):
   ns={n for n,d in new.nodes(data=True) if d["source_file"]==file}
   fr={"task_id":taskid,"file":file,"source_sha256":sourceinfo[file]["sha256"],
       "new_relations_vs_E3b":sum(e["file"]==file for e in edges),
       "potential_two_layer_scope":len(ns&scope),"new_upstream_context_targets":len(ns&context),
       "recovered_functions":audit["files"][file].get("recovered_functions",0),
       "file_status":audit["files"][file]["status"]}
   for v,es in errors.items():
    fr[v+"_historical_errors"]=len(es&ns) if isnode else int(file in es)
    if isnode:
     fr[v+"_errors_in_added_scope"]=len(es&ns&scope)
     fr[v+"_errors_with_new_upstream_context"]=len(es&ns&context)
   file_rows.append(fr)
  added=set(raw_edges(new)-raw_edges(old));case_seen=set()
  for proof in audit["evidence"]:
   k=(proof["source_node"],proof["target_node"],proof["relation"])
   if k not in added or k in case_seen:continue
   case_seen.add(k);file=new.nodes[k[0]]["source_file"]
   fn=next(x for x in audit["files"][file]["functions"] if x["function"]==proof["function"])
   raw=sourcebytes[file]
   example={"task_id":taskid,"file":file,"source_sha256":sourceinfo[file]["sha256"],
            "function":fn["name"],"function_id":fn["function"],"function_line":fn["line"],
            "relation":proof["relation"],"source_node":k[0],"target_node":k[1],
            "runtime_function":fn["runtime_function"],"binding":fn.get("binding"),
            "source_role":proof["definition"]["kind"],"target_role":proof["use"]["kind"],
            "path_status":proof.get("path_status",""),"certainty":proof["certainty"],
            "new_context_at_target":features[k[1]]["new_upstream_count_two"],
            "historical_E3b_error_at_target":k[1] in errors["E3b"] if isnode else None}
   for name,slot in (("definition","source"),("use","target")):
    a=proof[name]["anchor"]
    example[slot+"_line"]=raw[:a["start"]].count(b"\n")+1
    example[slot+"_text"]=raw[a["start"]:a["end"]].decode("utf8")
    example[slot+"_location"]=proof[name].get("location")
   cases.append(example)
  print(json.dumps(row),flush=True)
 save(out/"file_opportunities.csv",file_rows);save(out/"remaining_fallbacks.csv",fallbacks)
 write(out/"summary.json",summary);write(out/"function_count_reconciliation.json",totals)
 write(out/"new_edge_cases.json",cases)
 save(out/"summary.csv",[{k:v for k,v in x.items()} for x in summary if x["task_id"].endswith("_node")])
 write(out/"audit_receipt.json",{"status":"passed","new_predictions":False,"training_executed":False,
      "metric":"structural opportunity overlay on historical CV validation errors; not accuracy",
      "inputs":inputs,"files":{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
if __name__=="__main__":main()
