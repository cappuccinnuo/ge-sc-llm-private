"""Per-relation losses at exact projection; no graph writes."""
import pickle
from collections import Counter
from common import *
from scripts.DFG.state.stage_f.frontend import StageFSourceView
from scripts.DFG.state.stage_f.relations import order_relations
from scripts.DFG.projection import Projector
from scripts.DFG.models import Unsupported
def main():
 cohorts,inputs=catalogue();output=[]
 for cohort,c in cohorts.items():
  with (OUT/"F1_attempt_002"/(cohort+"_results.pkl")).open("rb") as f:cache=pickle.load(f)
  bytask={t:Counter() for t in c["files"]}
  for file in c["files"]["contract"]:
   rs=cache["results"][file];eligible=[]
   for r in rs:
    eligible.extend(("STATE_DEF_USE",f) for f in r.facts if f.certainty=="EXACT")
    eligible.extend((o.relation,o) for o in order_relations(r)[0] if o.relation in ("STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE") and o.certainty=="EXACT")
   if not eligible:continue
   counts=Counter()
   try:
    view=StageFSourceView(Path(c["manifest"]["sources"][file]["path"]).read_text(),file,cache["metadata"][file])
    mapping,missing=Projector(c["graphs"]["contract"],view).map_facts([f for _,f in eligible])
    for rel,f in eligible:
     counts[(rel,"semantic")]+=1
     if f.definition.anchor not in mapping or f.use.anchor not in mapping:counts[(rel,"missing_endpoint")]+=1
     elif mapping[f.definition.anchor]==mapping[f.use.anchor]:counts[(rel,"same_hcg_node")]+=1
     else:counts[(rel,"projected_evidence")]+=1
   except Unsupported:
    for rel,f in eligible:counts[(rel,"semantic")]+=1;counts[(rel,"file_projection_fallback")]+=1
   for task,files in c["files"].items():
    if file in files:bytask[task].update(counts)
  for task,counts in bytask.items():
   for rel in sorted({r for r,s in counts}):
    row={"cohort":cohort,"task":task,"relation":rel}
    for status in ("semantic","missing_endpoint","same_hcg_node","projected_evidence","file_projection_fallback"):row[status]=counts[rel,status]
    assert row["semantic"]==sum(row[k] for k in ("missing_endpoint","same_hcg_node","projected_evidence","file_projection_fallback"))
    output.append(row)
 check_inputs(inputs);dump(OUT/"PROJECTION_BREAKDOWN.json",output);print(json.dumps(output))
if __name__=="__main__":main()
