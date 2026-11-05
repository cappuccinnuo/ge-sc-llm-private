"""Read-only semantic and model-topology audit. Side relations are never model edges."""
from collections import Counter,deque
from . import STATE_DEF_USE
from .locations import alias

def next_events(ir,start,predicate,stop_on_may=False):
    positions={e.id:(b,i) for b,es in ir.events.items() for i,e in enumerate(es)}
    bid,index=positions[start.id]
    q=deque([((bid,index+1),(start.id,))]);seen=set();found=[]
    while q:
        (b,i),path=q.popleft()
        if (b,i) in seen:continue
        seen.add((b,i))
        if i==len(ir.events[b]):
            for nxt in sorted(ir.base.blocks[b].successors):q.append(((nxt,0),path+("block:"+nxt,)))
            continue
        e=ir.events[b][i];decision=predicate(e)
        if decision=="MATCH":
            found.append({"source":start.id,"target":e.id,"cfg_witness":path+(e.id,),
                          "path_status":"CFG_reachable_not_predicate_proven"});continue
        if decision=="STOP":continue
        q.append(((b,i+1),path+(e.id,)))
    return found

def side_relations(result):
    if result.ir is None:return []
    output=[];ir=result.ir
    for b,es in ir.events.items():
        if b not in result.reachable:continue
        for e in es:
            if e.kind in ("READ","WRITE"):
                def predicate(target):
                    if target.kind not in ("READ","WRITE"):return "CONTINUE"
                    rel=alias(e.location,target.location)
                    return "MATCH" if rel=="EXACT" else "STOP" if rel=="MAY" else "CONTINUE"
                for pair in next_events(ir,e,predicate):
                    output.append(dict(pair,relation="STATE_ACCESS_ORDER",policy="next_exact_access_before_may_alias",model_edge=False))
            if e.kind=="HAVOC":
                for pair in next_events(ir,e,lambda t:"MATCH" if t.kind=="WRITE" else "CONTINUE"):
                    output.append(dict(pair,relation="EXTERNAL_CALL_BEFORE_STATE_WRITE" if e.detail.startswith("EXTERNAL_CALL:") else "UNKNOWN_CALL_BEFORE_STATE_WRITE",
                                       model_edge=False))
    return output

def topology(graph,exclude_scalar=False):
    """Actual loader topology: base reflected; forward scalar/state remain forward."""
    outgoing={n:set() for n in graph}
    for s,t,d in graph.edges(data=True):
        rel=d.get("edge_type")
        if exclude_scalar and rel in ("DATA_DEF_USE",STATE_DEF_USE):continue
        outgoing[s].add(t)
        if rel not in ("DATA_DEF_USE",STATE_DEF_USE):outgoing[t].add(s)
    return outgoing

def two_hop(outgoing):
    result={}
    for n,one in outgoing.items():
        near=set(one)
        for x in one:near.update(outgoing[x])
        result[n]=near
    return result

def information_increment(base,enhanced):
    before=two_hop(topology(base));after=two_hop(topology(enhanced))
    hcg=two_hop(topology(base,True))
    pairs={(s,t) for s,t,d in enhanced.edges(data=True) if d.get("edge_type")==STATE_DEF_USE}
    newly={(s,t) for s in after for t in after[s]-before[s] if s!=t}
    canonical=lambda g:{(g.nodes[s]["node_type"],d["edge_type"],g.nodes[t]["node_type"]) for s,t,d in g.edges(data=True)}
    affected=Counter(enhanced.nodes[t]["node_type"] for _,t in newly)
    new_schema=canonical(enhanced)-canonical(base)
    return {"state_edges":len(pairs),"state_edges_outside_E2_two_hops":sum(t not in before[s] for s,t in pairs),
            "state_edges_outside_CFG_CG_two_hops":sum(t not in hcg[s] for s,t in pairs),
            "new_two_layer_source_target_pairs":len(newly),"new_context_target_nodes":len({t for _,t in newly}),
            "new_context_pairs_by_target_type":dict(affected),"new_canonical_relations":sorted(new_schema),
            "parameter_increment_if_hidden128_heads8_layers2":len(new_schema)*8208,
            "parameter_count_is_conditional_not_instantiated_full_model":True,
            "interpretation":"topological context only; not evidence of F1 improvement"}
