"""Verify accepted Stage F attempts and aggregate evidence without training."""
import csv,json
from collections import Counter
from common import ROOT,OUT,read,dump,sha,check_inputs

def rows(path):
 with path.open() as f:return list(csv.DictReader(f))
def main():
 before=rows(OUT/"F0_attempt_001/F0_FUNCTION_SUPPORT.csv")
 after=rows(OUT/"F1_attempt_002/F1_SUPPORT_BEFORE_AFTER.csv")
 key=lambda r:(r["cohort"],r["file"],r["function"])
 assert len(before)==len(after)==6552
 assert {key(r) for r in before}=={key(r) for r in after}
 assert len({key(r) for r in after})==len(after)
 old={key(r):r for r in before}
 assert all(int(r["old_facts_lost"])==0 for r in after)
 assert not any(r["before"]=="supported_subset" and r["after"]!="supported_subset" for r in after)
 for stage in ("F1_attempt_002","F3_attempt_002"):
  m=read(OUT/stage/"INPUT_MANIFEST.json");check_inputs(m["inputs"])
  for p,h in m["code"].items():assert sha(ROOT/p)==h
 graphs=read(OUT/"F3_attempt_002/GRAPH_MANIFEST.json")
 for g in graphs:assert g["effective_new_graph"] and sha(g["path"])==g["sha256"]
 invariants=read(OUT/"F3_attempt_002/F3_GRAPH_INVARIANTS.json")
 assert len(invariants)==len(graphs)==8
 assert all(r["base_preserved"] and r["off_exact"] for r in invariants)
 orders=rows(OUT/"F3_attempt_002/F2_EVENT_ORDER.csv")
 patterns=rows(OUT/"F3_attempt_002/F2_CALL_STATE_PATTERNS.csv")
 projection=rows(OUT/"F3_attempt_002/F2_PROJECTION_AUDIT.csv")
 totals=[];difficult=[]
 selected={"reentrancy_author":{"buggy_18.sol","buggy_27.sol","buggy_36.sol"},"access_control_author":{"mapping_write.sol","buggy_18.sol","buggy_26.sol","arbitrary_location_write_simple.sol"}}
 for cohort in selected:
  records=read(OUT/"F1_attempt_002"/(cohort+"_results.json"))
  for task in ("contract","node"):
   ss=[r for r in after if r["cohort"]==cohort and (task=="contract" or r["in_node"]=="True")]
   files={r["file"] for r in ss};pr=[r for r in projection if r["cohort"]==cohort and r["file"] in files]
   recs=[r for f in files for r in records[f]["functions"]]
   item={"cohort":cohort,"task":task,"files":len(files),"functions":len(ss),
    "recovered_from_reasons":dict(Counter(old[key(r)]["first_fallback_reason"] for r in ss if r["before"]!="supported_subset" and r["after"]=="supported_subset")),
    "remaining_reasons":dict(Counter(r["reason"] for r in ss if r["after"]!="supported_subset")),
    "source_matched_metadata_files":sum(records[f]["metadata"] is not None for f in files),
    "file_frontend_failures":{f:records[f]["reason"] for f in files if records[f]["reason"]},
    "order_candidates":dict(Counter(r["relation"] for r in orders if r["cohort"]==cohort and r["file"] in files)),
    "triple_patterns":dict(Counter(r["pattern"] for r in patterns if r["cohort"]==cohort and r["file"] in files)),
    "after_MAY":sum(f["certainty"]=="MAY" for r in recs for f in r["facts"]),
    "after_external_calls":sum(e["kind"]=="HAVOC" and e["detail"].startswith("EXTERNAL_CALL:") for r in recs for e in r["events"]),
    "projection":{k:sum(int(r.get(k) or 0) for r in pr) for k in ("exact_state_facts","eligible_relations","projected_facts","self_facts","materializable_evidence","uncertain_candidates")},
    "projection_file_failures":{r["file"]:r["file_projection_fallback"] for r in pr if r["file_projection_fallback"]},
    "projection_missing_anchor_records":sum(len(json.loads(r["missing_anchors"] or "[]")) for r in pr)}
   for prefix in ("before","after"):
    item[prefix]={k:sum(int(r[prefix+"_"+k]) for r in ss) for k in ("READ","WRITE","HAVOC","locations","unknown","exact")}
   totals.append(item)
  for file in sorted(selected[cohort]):
   rr=[r for r in after if r["cohort"]==cohort and r["file"]==file]
   difficult.append({"cohort":cohort,"file":file,"functions":len(rr),
    "before_supported":sum(r["before"]=="supported_subset" for r in rr),"after_supported":sum(r["after"]=="supported_subset" for r in rr),
    "after_exact":sum(int(r["after_exact"]) for r in rr),
    "orders":dict(Counter(r["relation"] for r in orders if r["cohort"]==cohort and r["file"]==file)),
    "patterns":dict(Counter(r["pattern"] for r in patterns if r["cohort"]==cohort and r["file"]==file)),
    "projection":next(r for r in projection if r["cohort"]==cohort and r["file"]==file)})
 oracle=read(OUT/"F3_attempt_002/F2_ORACLE_RESULTS.json")
 result={"accepted":{"F0":"F0_attempt_001","F1":"F1_attempt_002","F3":"F3_attempt_002"},"complete_population_rows":len(after),
 "old_facts_lost":0,"new_function_fallbacks":0,"candidate_graphs_verified":len(graphs),"tasks":totals,"difficult_files":difficult,
 "oracle_rechecks":len(oracle),"independent_human_approved":0,"compiler_validated":0,
 "oracle_status_counts":dict(Counter(x.get("analysis",{}).get("status","file_fallback") for x in oracle)),
 "real_world_binding_error_rate":"not established by independent ground truth; regression failures zero","training_executed":False}
 if "--validate-only" in __import__("sys").argv:
  assert result==read(OUT/"FINAL_ANALYSIS.json"), "accepted analysis changed"
  print("Verified accepted inputs, code, 6552 function identities and eight candidate graphs")
 else:
  dump(OUT/"FINAL_ANALYSIS.json",result)
  print(json.dumps(result))
if __name__=="__main__":main()
