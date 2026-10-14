"""Add only audited exact-location STATE_DEF_USE to a copy of E2."""
import copy
from dataclasses import asdict
from ..models import Unsupported
from ..frontend import SourceView
from ..projection import Projector
from ..graph_audit import fingerprint
from . import VERSION,STATE_DEF_USE
from .analyzer import analyze_view

def assert_state_augmented(base,enhanced):
    clean=copy.deepcopy(enhanced)
    pairs=set()
    for s,t,k,d in list(clean.edges(keys=True,data=True)):
        if d.get("edge_type")!=STATE_DEF_USE:continue
        if s==t or (s,t) in pairs:raise AssertionError("State duplicate/self graph edge")
        if clean.nodes[s]["source_file"]!=clean.nodes[t]["source_file"]:raise AssertionError("Cross-file state edge")
        pairs.add((s,t));clean.remove_edge(s,t,k)
    if fingerprint(clean)!=fingerprint(base):raise AssertionError("E2 nodes/labels/features/scalar/base edges changed")
    return {"base_fingerprint":fingerprint(base),"enhanced_fingerprint":fingerprint(enhanced),
            "state_edges":len(pairs),"base_preserved":True}

def result_record(result):
    ir=result.ir
    return {"function":result.function,"status":result.status,"diagnostics":result.diagnostics,
            "iterations":result.iterations,"reachable_blocks":sorted(result.reachable),
            "events":[asdict(e) for b,es in ir.events.items() if b in result.reachable for e in es] if ir else [],
            "locations":{k:asdict(v) for k,v in ir.locations.items()} if ir else {},
            "cfg":{b:sorted(v.successors) for b,v in ir.base.blocks.items()} if ir else {},
            "facts":[asdict(f) for f in result.facts],"unknown_reads":result.unknown_reads}

def augment_state(base,sources,enabled=True,selected_functions=None,max_iterations=100000):
    if type(enabled) is not bool:raise ValueError("enabled must be bool")
    if not base.is_directed() or not base.is_multigraph():raise ValueError("Requires directed multigraph E2")
    if any(d.get("edge_type")==STATE_DEF_USE for _,_,d in base.edges(data=True)):
        raise ValueError("Use unenhanced E2; state augmentation is not cumulative")
    original=fingerprint(base);out=copy.deepcopy(base)
    audit={"version":VERSION,"enabled":enabled,"files":{},"evidence":[],
           "policy":"materialize exact location, may-reaching CFG facts; MAY alias remains sidecar",
           "path_scope":"CFG reachability only; path predicates not solved"}
    if enabled:
        for file in dict.fromkeys(d["source_file"] for _,d in base.nodes(data=True)):
            if selected_functions is not None and file not in selected_functions:continue
            rec={"functions":[],"projection_missing":[],"facts_projected":0,
                 "may_alias_sidecar_facts":0,"self_facts":0,"edges_added":0}
            audit["files"][file]=rec
            if file not in sources:
                rec["fallback"]="Exact source identity not supplied";continue
            try:
                view=SourceView(sources[file],file)
                rec["source_sha256"]=view.sha256
                results=analyze_view(view,None if selected_functions is None else selected_functions[file],max_iterations)
                rec["functions"]=[result_record(r) for r in results]
                projector=Projector(base,view)
                exact=[f for r in results for f in r.facts if f.certainty=="EXACT"]
                rec["may_alias_sidecar_facts"]=sum(f.certainty!="EXACT" for r in results for f in r.facts)
                mapping,rec["projection_missing"]=projector.map_facts(exact)
                groups={}
                for f in exact:
                    if f.definition.anchor not in mapping or f.use.anchor not in mapping:continue
                    a,b=mapping[f.definition.anchor],mapping[f.use.anchor]
                    evidence=dict(asdict(f),source_node=a,target_node=b,relation=STATE_DEF_USE,version=VERSION)
                    idx=len(audit["evidence"]);audit["evidence"].append(evidence)
                    rec["facts_projected"]+=1
                    if a==b:rec["self_facts"]+=1;continue
                    groups.setdefault((a,b),[]).append(idx)
                for (a,b),indices in groups.items():
                    out.add_edge(a,b,edge_type=STATE_DEF_USE,state_version=VERSION,state_fact_indices=indices)
                rec["edges_added"]=len(groups)
            except Unsupported as exc:
                rec["fallback"]=str(exc)
    audit["invariants"]=assert_state_augmented(base,out)
    assert fingerprint(base)==original
    return out,audit
