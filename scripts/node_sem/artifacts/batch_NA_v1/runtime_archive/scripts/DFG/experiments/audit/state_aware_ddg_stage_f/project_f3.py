"""F2/F3 automated candidate verification on unchanged complete task populations."""
import argparse,pickle,copy
from pathlib import Path
from collections import Counter
from dataclasses import asdict
from common import *
from scripts.DFG.models import Unsupported
from scripts.DFG.state.stage_f.frontend import StageFSourceView
from scripts.DFG.state.stage_f.relations import order_relations,read_call_write,validate_witness
from scripts.DFG.state.stage_f.projection import projected_file,materialize,assert_preserved
from scripts.DFG.state.stage_f.model_adapter import information_increment,build_dgl
from scripts.DFG.graph_audit import fingerprint
def main(output):
 out=Path(output);out.mkdir(parents=True,exist_ok=False);cohorts,inputs=catalogue()
 allproof=[];orders=[];patterns=[];proj=[];graphs=[];invariants=[];schema=[];oracle_results=[]
 for cohort,c in cohorts.items():
  cached=OUT/"F1_attempt_002"/(cohort+"_results.pkl");inputs[str(cached)]=sha(cached)
  with cached.open("rb") as f:data=pickle.load(f)
  before=read(OUT/"F1_attempt_002"/(cohort+"_results.json"));proof=[]
  for idx,file in enumerate(c["files"]["contract"]):
   rs=data["results"][file];source=Path(c["manifest"]["sources"][file]["path"]).read_text()
   for r in rs:
    oside,u=order_relations(r)
    for o in oside:
     validate_witness(r.ir,o.cfg_witness)
     orders.append({"cohort":cohort,"file":file,"function":r.function,"relation":o.relation,"source":o.definition.id,"target":o.use.id,
                    "source_kind":o.definition.kind,"target_kind":o.use.kind,"certainty":o.certainty,"source_location":o.definition.location.id if o.definition.location else None,
                    "target_location":o.use.location.id if o.use.location else None,"external_calls":o.call_events,"unknown_calls":o.unknown_call_events,
                    "cfg_witness":o.cfg_witness,"path_status":o.path_status,"human_approved":False})
    for p in read_call_write(r):
     validate_witness(r.ir,p["cfg_witness"]);patterns.append(dict(p,cohort=cohort,file=file,function=r.function,human_approved=False))
   try:
    v=StageFSourceView(source,file,data["metadata"][file]);ev,a=projected_file(c["graphs"]["contract"],v,rs)
   except Unsupported as e:ev=[];a={"file_projection_fallback":str(e)}
   proof.extend(ev);a.pop("patterns",None)
   proj.append(dict(a,cohort=cohort,file=file,in_node=file in c["files"]["node"],materializable_evidence=len(ev)))
   if idx%35==0:print(cohort,idx+1,"/",len(c["files"]["contract"]),flush=True)
  for task,base in c["graphs"].items():
   for variant,relations in (("E3a",{"STATE_DEF_USE"}),("E3b",{"STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE"})):
    new,inv=materialize(base,proof,relations)
    off,_=materialize(base,proof,relations,False);assert fingerprint(off)==fingerprint(base)
    info=information_increment(base,new);info.update(cohort=cohort,task=task,variant=variant)
    edges=sum(info["new_model_edges_by_relation"].values())
    path=out/(cohort+"_"+task+"_"+variant+"_candidate.gpickle")
    if edges:
     with path.open("xb") as f:pickle.dump(new,f,protocol=4)
     with path.open("rb") as f:assert fingerprint(pickle.load(f))==fingerprint(new)
     info.update(path=str(path),sha256=sha(path),effective_new_graph=True)
    else:info.update(path=None,sha256=None,effective_new_graph=False,same_as_E2=True)
    dg,_=build_dgl(new)
    for rel in ("STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE"):
     nx_count=sum(d.get("edge_type")==rel for _,_,d in new.edges(data=True))
     dgl_count=sum(dg.num_edges(k) for k in dg.canonical_etypes if k[1]==rel)
     assert nx_count==dgl_count,("unwanted reflection",rel)
    schema.append({"cohort":cohort,"task":task,"variant":variant,"canonical_relations":list(dg.canonical_etypes),"node_types":dg.ntypes,"no_new_relation_reflection":True})
    invariants.append(dict(inv,cohort=cohort,task=task,variant=variant,off_exact=True));graphs.append(info)
  allproof.append({"cohort":cohort,"evidence":proof})
 # Recheck every Stage E oracle with immutable source/AST identities; changed fallback is not redefined as oracle truth.
 oracle=read(ROOT/"scripts/DFG/experiments/audit/state_aware_ddg_prototype_v1/ORACLE_EXPECTATIONS.json")
 from scripts.DFG.state.stage_f.analyzer import analyze_view
 from scripts.DFG.state.projection import result_record
 from compare_f1 import find_metadata
 for o in oracle["oracles"]:
  src=Path(o["source_path"]).read_text() if o["source_path"] else o["source"]
  assert __import__("hashlib").sha256(src.encode()).hexdigest()==o["source_sha256"]
  file=Path(o["source_path"]).name if o["source_path"] else o["oracle_id"]+".sol"
  try:
   v=StageFSourceView(src,file,find_metadata(o["source_sha256"],inputs))
   rs=analyze_view(v,[o["function_identity"]]);r=rs[0]
   oracle_results.append({"oracle_id":o["oracle_id"],"source_sha256":o["source_sha256"],"analysis":result_record(r),
      "relations":[asdict(x) for x in order_relations(r)[0]],"patterns":read_call_write(r),"reviewer_status":"Codex_static_recheck_independent_approval_pending","compiled":False})
  except Unsupported as e:oracle_results.append({"oracle_id":o["oracle_id"],"fallback":str(e),"compiled":False,"human_approved":False})
 check_inputs(inputs);dump(out/"INPUT_MANIFEST.json",{"inputs":inputs,"code":{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/"scripts/DFG/state/stage_f").glob("*.py")}})
 csv_out(out/"F2_EVENT_ORDER.csv",orders);csv_out(out/"F2_CALL_STATE_PATTERNS.csv",patterns);csv_out(out/"F2_PROJECTION_AUDIT.csv",proj)
 dump(out/"F2_ORACLE_RESULTS.json",oracle_results);dump(out/"F3_EDGE_PROVENANCE.json",allproof)
 dump(out/"F3_GRAPH_INVARIANTS.json",invariants);dump(out/"F3_CANONICAL_SCHEMA.json",schema);csv_out(out/"F3_INFORMATION_INCREMENT.csv",graphs)
 dump(out/"GRAPH_MANIFEST.json",graphs)
 print(json.dumps(graphs),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--output",required=True);main(p.parse_args().output)
