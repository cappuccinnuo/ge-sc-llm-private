"""Candidate graph variants and exact event projection; original E2 is immutable."""
import copy
from dataclasses import asdict
from ...models import Unsupported
from ...projection import Projector
from ...graph_audit import fingerprint
from . import VERSION
from .relations import order_relations,read_call_write,validate_witness
RELATIONS=frozenset(("STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE"))
def assert_preserved(base,new):
 clean=copy.deepcopy(new)
 for s,t,k,d in list(clean.edges(keys=True,data=True)):
  if d.get("edge_type") in RELATIONS:
   if s==t:raise AssertionError("new self edge")
   if clean.nodes[s]["source_file"]!=clean.nodes[t]["source_file"]:raise AssertionError("cross-file relation")
   clean.remove_edge(s,t,k)
 if fingerprint(clean)!=fingerprint(base):raise AssertionError("E2 nodes/features/labels/base edges changed")
 return {"base_fingerprint":fingerprint(base),"new_fingerprint":fingerprint(new),"base_preserved":True}
def projected_file(base,view,results):
 """Projection output is committed only after all endpoint checks; fallbacks keep base."""
 evidence=[];audit={"exact_state_facts":0,"order_candidates":0,"eligible_relations":0,"projected_facts":0,"self_facts":0,"missing_anchors":[],
 "fallback_functions":sum(r.ir is None for r in results),"uncertain_candidates":0,"patterns":[]}
 eligible=[]
 for r in results:
  if r.ir is None:continue
  orders,unknown=order_relations(r);audit["uncertain_candidates"]+=len(unknown)
  audit["patterns"]+=read_call_write(r)
  for f in r.facts:
   if f.certainty=="EXACT":
    audit["exact_state_facts"]+=1;eligible.append(("STATE_DEF_USE",f,asdict(f),r.function))
  audit["order_candidates"]+=len(orders)
  for o in orders:
   validate_witness(r.ir,o.cfg_witness)
   if o.relation in RELATIONS and o.certainty=="EXACT":eligible.append((o.relation,o,asdict(o),r.function))
 audit["eligible_relations"]=len(eligible)
 try:
  projector=Projector(base,view);mapping,audit["missing_anchors"]=projector.map_facts([e[1] for e in eligible])
 except Unsupported as e:
  audit["file_projection_fallback"]=str(e);return [],audit
 for rel,f,proof,fid in eligible:
  if f.definition.anchor not in mapping or f.use.anchor not in mapping:continue
  s,t=mapping[f.definition.anchor],mapping[f.use.anchor];audit["projected_facts"]+=1
  proof.update(source_node=s,target_node=t,relation=rel,function=fid,source_sha256=view.sha256,version=VERSION)
  if s==t:audit["self_facts"]+=1;continue
  evidence.append(proof)
 return evidence,audit
def materialize(base,evidence,relations=RELATIONS,enabled=True):
 if any(d.get("edge_type") in RELATIONS for _,_,d in base.edges(data=True)):raise ValueError("Use frozen E2 input")
 out=copy.deepcopy(base);groups={}
 if enabled:
  for i,e in enumerate(evidence):
   if e["relation"] not in relations:continue
   s,t=e["source_node"],e["target_node"]
   if s not in base or t not in base:continue
   if s==t:raise ValueError("Self relation must be audited before materialization")
   groups.setdefault((s,t,e["relation"]),[]).append(i)
  for (s,t,rel),ids in groups.items():out.add_edge(s,t,edge_type=rel,state_version=VERSION,state_evidence_indices=ids)
 return out,assert_preserved(base,out)
