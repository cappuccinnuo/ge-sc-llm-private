"""Structural CFG event order, distinct from value dependence and exploitability."""
from dataclasses import dataclass,asdict
from collections import deque
from ..locations import alias
from ..audit import next_events
@dataclass(frozen=True)
class OrderRelation:
 relation:str
 definition:object
 use:object
 certainty:str
 cfg_witness:tuple
 call_events:tuple=()
 unknown_call_events:tuple=()
 path_status:str="CFG_structure_only_path_predicates_not_proven"
def events_of(r):
 return {e.id:e for b,es in r.ir.events.items() if b in r.reachable for e in es} if r.ir else {}
def external(e):return e.kind=="HAVOC" and e.detail.startswith("EXTERNAL_CALL:")
def order_relations(r):
 if r.ir is None:return [],[]
 events=events_of(r);relations=[];uncertain=[]
 for start in events.values():
  if start.kind in ("READ","WRITE"):
   if start.location.certainty!="EXACT":
    uncertain.append({"event":start.id,"reason":"source_location_not_exact"});continue
   def pred(target):
    if target.kind not in ("READ","WRITE"):return "CONTINUE"
    a=alias(start.location,target.location)
    return "MATCH" if a=="EXACT" else "STOP" if a=="MAY" else "CONTINUE"
   pairs=next_events(r.ir,start,pred)
   kind="STATE_ACCESS_ORDER"
  elif start.kind=="HAVOC":
   pairs=next_events(r.ir,start,lambda t:"MATCH" if t.kind=="WRITE" else "CONTINUE")
   kind="EXTERNAL_CALL_BEFORE_STATE_WRITE" if external(start) else "UNKNOWN_CALL_BEFORE_STATE_WRITE"
  else:continue
  for pair in pairs:
   target=events[pair["target"]];path=tuple(pair["cfg_witness"])
   calls=tuple(x for x in path if x in events and external(events[x]))
   unknown=tuple(x for x in path if x in events and events[x].kind=="HAVOC" and not external(events[x]))
   certainty="EXACT" if target.location.certainty=="EXACT" else "UNKNOWN"
   relations.append(OrderRelation(kind,start,target,certainty,path,calls,unknown))
 return relations,uncertain
def read_call_write(r):
 """Same-location nearest-write pattern; no intervening write or additional opaque call."""
 if r.ir is None:return []
 ir=r.ir;events=events_of(r);positions={e.id:(b,i) for b,es in ir.events.items() for i,e in enumerate(es)};output=[]
 for start in events.values():
  if start.kind!="READ":continue
  bid,idx=positions[start.id]
  queue=deque([((bid,idx+1),None,(start.id,))]);seen=set()
  while queue:
   (b,i),call,path=queue.popleft();state=(b,i,call)
   if state in seen:continue
   seen.add(state)
   if i==len(ir.events[b]):
    for nxt in sorted(ir.base.blocks[b].successors):queue.append(((nxt,0),call,path+("block:"+nxt,)))
    continue
   e=ir.events[b][i];newpath=path+(e.id,)
   if e.kind=="HAVOC":
    if call is not None:continue
    if not external(e):
     output.append({"pattern":"READ_OPAQUE_CALL_UNRESOLVED","read":start.id,"call":e.id,"write":None,"certainty":"UNKNOWN","cfg_witness":newpath,"model_edge":False});continue
    queue.append(((b,i+1),e.id,newpath));continue
   if e.kind=="WRITE":
    relation=alias(start.location,e.location)
    if call is not None:
     output.append({"pattern":"READ_CALL_WRITE_SAME_LOCATION" if relation=="EXACT" else "READ_CALL_WRITE_MAY_ALIAS" if relation=="MAY" else "READ_CALL_WRITE_DIFFERENT_LOCATION",
       "read":start.id,"call":call,"write":e.id,"read_location":start.location.id,"write_location":e.location.id,
       "certainty":relation,"cfg_witness":newpath,"path_status":"CFG_structure_only_path_predicates_not_proven","model_edge":False})
    if relation!="NO_ALIAS":continue
   queue.append(((b,i+1),call,newpath))
 return output
def validate_witness(ir,ids):
 """Independently replay witness adjacency including block transitions."""
 index={e.id:(b,i) for b,es in ir.events.items() for i,e in enumerate(es)}
 if not ids or ids[0] not in index:raise ValueError("Missing source event")
 b,i=index[ids[0]];i+=1
 for token in ids[1:]:
  if token.startswith("block:"):
   target=token[6:]
   if i!=len(ir.events[b]) or target not in ir.base.blocks[b].successors:raise ValueError("Invalid CFG transition")
   b,i=target,0
  else:
   if i>=len(ir.events[b]) or ir.events[b][i].id!=token:raise ValueError("Non-adjacent event")
   i+=1
 return True
