"""F1 compare frozen Stage E corpus results with opt-in Stage F, before projection."""
from common import *
from pathlib import Path
from collections import Counter
import argparse,csv,pickle
from scripts.DFG.models import Unsupported
from scripts.DFG.state.stage_f.frontend import StageFSourceView
from scripts.DFG.state.stage_f.analyzer import analyze_view
from scripts.DFG.state.projection import result_record
from scripts.DFG.state.audit import side_relations
def find_metadata(source_sha,inputs):
 path=ORIGINAL/"data/smartbug-dataset/versions.csv";inputs[str(path)]=sha(path)
 matches=[]
 for row in csv.DictReader(path.open()):
  src=path.parent/row["file"]
  if src.is_file() and sha(src)==source_sha:
   inputs[str(src)]=source_sha
   matches.append({"csv_path":str(path),"csv_sha256":sha(path),"source_path":str(src),"source_sha256":source_sha,"row_file":row["file"],"version":row["compiled version"]})
 versions={m["version"] for m in matches}
 return matches[0] if len(versions)==1 else None
def signature(f):
 return (f["definition"]["anchor"]["start"],f["definition"]["expression"]["start"],f["use"]["anchor"]["start"],f["use"]["expression"]["start"],f["location_id"],f["certainty"])
def main(output):
 out=Path(output);out.mkdir(parents=True,exist_ok=False);cohorts,inputs=catalogue();support=[];evidence=[];lost=[];totals=[]
 syntactic=list(csv.DictReader((OUT/"F0_attempt_001/F0_FUNCTION_SUPPORT.csv").open()))
 for cohort,c in cohorts.items():
  before=read(OUT/"F0_attempt_001"/(cohort+"_stage_e_results.json"));records={};pickles={};metadatas={}
  for idx,file in enumerate(c["files"]["contract"]):
   spec=c["manifest"]["sources"][file];source=Path(spec["path"]).read_text()
   meta=find_metadata(spec["sha256"],inputs);metadatas[file]=meta
   try:view=StageFSourceView(source,file,meta);rs=analyze_view(view);reason=None
   except Unsupported as e:rs=[];reason=str(e)
   now=[]
   for r in rs:
    rec=result_record(r);rec["side_relations"]=side_relations(r);rec["binding_evidence"]=getattr(r,"binding_evidence",None);now.append(rec)
    if r.ir:evidence.append({"cohort":cohort,"file":file,"function":r.function,"source_sha256":spec["sha256"],
                            "binding":rec["binding_evidence"],"locations":rec["locations"]})
   records[file]={"reason":reason,"functions":now,"metadata":meta};pickles[file]=rs
   old={r["function"]:r for r in before[file]};new={r["function"]:r for r in now}
   for fid in sorted(set(old)|set(new)|{x["function"] for x in syntactic if x["cohort"]==cohort and x["file"]==file}):
    b=old.get(fid);n=new.get(fid);bs={signature(f) for f in b["facts"]} if b else set();ns={signature(f) for f in n["facts"]} if n else set()
    missing=bs-ns
    if missing:lost.append({"cohort":cohort,"file":file,"function":fid,"missing":sorted(missing)})
    row={"cohort":cohort,"file":file,"function":fid,"in_node":file in c["files"]["node"],
         "before":b["status"] if b else "file_fallback","after":n["status"] if n else "file_fallback",
         "reason":reason or (n["diagnostics"][0]["reason"] if n and n["diagnostics"] else ""),
         "before_exact":sum(f["certainty"]=="EXACT" for f in b["facts"]) if b else 0,"after_exact":sum(f["certainty"]=="EXACT" for f in n["facts"]) if n else 0,
         "old_facts_lost":len(missing),"new_facts":len(ns-bs)}
    for label,obj in (("before",b),("after",n)):
     for k in ("READ","WRITE","HAVOC"):row[label+"_"+k]=sum(e["kind"]==k for e in obj["events"]) if obj else 0
     row[label+"_locations"]=len(obj["locations"]) if obj else 0;row[label+"_unknown"]=len(obj["unknown_reads"]) if obj else 0
    support.append(row)
   if idx%25==0:print(cohort,idx+1,"/",len(c["files"]["contract"]),flush=True)
  dump(out/(cohort+"_results.json"),records)
  with (out/(cohort+"_results.pkl")).open("xb") as f:pickle.dump({"results":pickles,"metadata":metadatas},f,protocol=4)
  for task,names in c["files"].items():
   ss=[x for x in support if x["cohort"]==cohort and x["file"] in names]
   totals.append({"cohort":cohort,"task":task,"functions_compared":len(ss),"before_supported":sum(x["before"]=="supported_subset" for x in ss),
      "after_supported":sum(x["after"]=="supported_subset" for x in ss),"recovered_functions":sum(x["before"]!="supported_subset" and x["after"]=="supported_subset" for x in ss),
      "became_fallback":sum(x["before"]=="supported_subset" and x["after"]!="supported_subset" for x in ss),
      "before_exact":sum(x["before_exact"] for x in ss),"after_exact":sum(x["after_exact"] for x in ss),
      "old_facts_lost":sum(x["old_facts_lost"] for x in ss),"new_facts":sum(x["new_facts"] for x in ss)})
 check_inputs(inputs);dump(out/"INPUT_MANIFEST.json",{"inputs":inputs,"code":{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/"scripts/DFG/state/stage_f").glob("*.py")}})
 csv_out(out/"F1_SUPPORT_BEFORE_AFTER.csv",support);dump(out/"F1_BINDING_EVIDENCE.json",evidence);dump(out/"F1_LOST_FACTS.json",lost)
 dump(out/"F1_SUMMARY.json",totals);print(json.dumps(totals),flush=True)
 assert not lost,"Stop: old facts lost; investigate before projection"
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--output",required=True);main(p.parse_args().output)
