"""May-reaching state origins. TOP suppresses unjustified concrete call-crossing facts."""
from collections import deque
from ..models import Unsupported
from ..reaching_definitions import _validate_and_index, _reachable_order
from .models import StateFact,StateAnalysisResult
from .locations import alias

def transfer(state,event,locations):
    current={k:set(v) for k,v in state.items()}
    if event.kind=="HAVOC":
        return {k:{"HAVOC:"+event.id} for k in locations}
    if event.kind=="WRITE":
        for k,l in locations.items():
            relation=alias(event.location,l)
            if relation=="EXACT" and event.location.certainty=="EXACT":
                current[k]={event.id}
            elif relation!="NO_ALIAS":
                current[k].add(event.id)
    return current

def witness(ir,definition,use,location):
    """A kill-free CFG path, NOT an SMT proof of feasible branch predicates."""
    locs=ir.locations
    positions={e.id:(b,i) for b,events in ir.events.items() for i,e in enumerate(events)}
    start_b,start_i=positions[definition.id]
    target=positions[use.id]
    q=deque([((start_b,start_i+1),(definition.id,))]);seen=set()
    while q:
        (bid,index),path=q.popleft()
        if (bid,index) in seen:continue
        seen.add((bid,index))
        if (bid,index)==target:return path+(use.id,)
        events=ir.events[bid]
        if index==len(events):
            for nxt in sorted(ir.base.blocks[bid].successors):q.append(((nxt,0),path+("block:"+nxt,)))
            continue
        event=events[index]
        if event.kind=="HAVOC":continue
        if event.kind=="WRITE" and event.id!=definition.id and event.location.certainty=="EXACT" and alias(event.location,location)=="EXACT":continue
        q.append(((bid,index+1),path+(event.id,)))
    raise AssertionError("State RD fact has no kill-free CFG witness")

def solve(ir,max_iterations=100000):
    if type(max_iterations) is not int or max_iterations<1:raise ValueError("Invalid iteration bound")
    _,_,pred=_validate_and_index(ir.base)
    order,reachable=_reachable_order(ir.base)
    if set(ir.events)!=set(ir.base.blocks):raise Unsupported("state: side table block mismatch")
    base_events={e.id:(bid,e) for bid,b in ir.base.blocks.items() for e in b.events}
    event_index={}
    for bid,events in ir.events.items():
        for e in events:
            if e.id in event_index:raise Unsupported("state: duplicate event")
            if e.kind not in ("READ","WRITE","HAVOC","ENVIRONMENT","CALL_CONFIGURATION"):
                raise Unsupported("state: unregistered event kind")
            if e.block!=bid or e.function!=ir.base.id or e.scalar_event not in base_events or base_events[e.scalar_event][0]!=bid:
                raise Unsupported("state: invalid side table identity")
            if e.anchor!=base_events[e.scalar_event][1].anchor:raise Unsupported("state: source anchor mismatch")
            if e.expression.file!=ir.base.file or not (e.anchor.start<=e.expression.start<=e.expression.end<=e.anchor.end):
                raise Unsupported("state: expression outside verified scalar anchor")
            if e.kind in ("READ","WRITE") and (e.location is None or ir.locations.get(e.location.id)!=e.location):
                raise Unsupported("state: unregistered location")
            event_index[e.id]=e
    empty=lambda:{k:set() for k in ir.locations}
    inputs={b:empty() for b in ir.base.blocks};outputs={b:empty() for b in ir.base.blocks}
    q=deque(order);queued=set(order);iterations=0
    while q:
        if iterations>=max_iterations:raise Unsupported("state: fixpoint limit reached; no partial facts")
        bid=q.popleft();queued.remove(bid);iterations+=1
        cur=empty()
        if bid==ir.base.entry:
            cur={k:{"ENTRY_UNKNOWN:"+k} for k in ir.locations}
        for previous in pred[bid]&reachable:
            for k in cur:cur[k].update(outputs[previous][k])
        inputs[bid]=cur
        for e in ir.events[bid]:cur=transfer(cur,e,ir.locations)
        if cur!=outputs[bid]:
            outputs[bid]=cur
            for nxt in sorted(ir.base.blocks[bid].successors):
                if nxt not in queued:q.append(nxt);queued.add(nxt)
    facts=[];unknown=[]
    for bid in order:
        cur={k:set(v) for k,v in inputs[bid].items()}
        for e in ir.events[bid]:
            if e.kind=="READ":
                for origin in sorted(cur[e.location.id]):
                    if origin not in event_index:
                        unknown.append({"use":e.id,"location":e.location.id,"origin":origin})
                    else:
                        d=event_index[origin]
                        certainty=alias(d.location,e.location)
                        if certainty=="NO_ALIAS":raise AssertionError("Impossible alias in state")
                        facts.append(StateFact(d,e,e.location.id,certainty,witness(ir,d,e,e.location)))
            cur=transfer(cur,e,ir.locations)
        assert cur==outputs[bid]
    return StateAnalysisResult(ir.base.id,"supported_subset",ir,facts,unknown,[],
                               iterations,reachable)
