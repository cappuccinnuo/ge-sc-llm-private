"""F4 construction: F3 plus the E1 relations MOD_APPLY, CALL_SITE and GUARDS.

``inspect_file`` derives one file's E1 edge records from its source and the F3 graph;
``add_edges`` returns a copy of a graph with those edges added (the F3 graph is never mutated).
"""
import copy
import hashlib
from collections import Counter

import networkx as nx

from dfg.analysis.frontend import walk
from dfg.graph.projection import ProjectionView, Projector
from edgesem.graph.calls import resolve_call
from edgesem.graph.guards import collect_guards, describe_unresolved_modifiers
from nodesem.facts.extract import STATEMENTS, _raw_projection
from nodesem.facts.guards import GuardAnalyzer, children, unwrap
from nodesem.facts.syntax import AstSemantics, key


RELATIONS=frozenset(("MOD_APPLY","CALL_SITE","GUARDS"))

def anchor(node):
    return None if node is None else list(key(node))

def modifier_target(analyzer,function,invocation):
    """The frozen scope/arguments/one-placeholder policy, with explicit reasons."""
    sem=analyzer.sem;scope=analyzer._scope(function);cs=children(invocation)
    if scope is None or not cs or cs[0].type!="identifier":
        return None,"unresolved","scope_or_invocation",False
    ds=scope.declarations(sem.text(cs[0]))
    if len(ds)>1:
        return None,"not_unique","declaration_ambiguous",False
    if len(ds)!=1 or ds[0].type!="modifier_definition":
        return None,"unresolved","modifier_binding",False
    target=ds[0];body=target.child_by_field_name("body")
    bindings=analyzer._bindings(target,invocation)
    holes=[] if body is None else [n for n in walk(body) if n.type=="expression_statement"
        and unwrap(n).type=="identifier" and sem.text(unwrap(n))=="_"]
    if bindings is None or not holes:
        return None,"unresolved","placeholder_or_arguments",False
    if len(holes)!=1:
        return None,"unresolved","multiple_placeholders",False
    return target,"resolved","frozen_modifier_binding",scope.owner.get(target.start_byte)!=scope.contract

def inspect_file(file,source,graph):
    """Build records from one exact AST/source identity; graph is read-only."""
    sha=hashlib.sha256(source.encode("utf8")).hexdigest()
    nodes=[n for n,d in graph.nodes(data=True) if d["source_file"]==file and d["node_type"]!="env_source"]
    view=ProjectionView(source,file);sem=AstSemantics(view)
    raw=_raw_projection(view,Projector(graph.subgraph(nodes),view))
    inverse={key(n):i for i,n in raw.items()}
    if len(inverse)!=len(raw):
        raise ValueError("Nonunique AST projection")
    analyzer=GuardAnalyzer(sem)
    function_keys={key(n) for n in sem.functions}
    edges={};events=[];counts=Counter();statuses=Counter();reasons=Counter()

    def emit(relation,src_node,target,evidence,kind=None):
        src,dst=inverse.get(key(src_node)),inverse.get(key(target))
        if src is None or dst is None:
            return "not_in_graph"
        if src==dst:
            return "self_loop"
        ident=(relation,src,dst)
        if ident not in edges:
            edges[ident]=dict(relation=relation,src=src,dst=dst,
                rule="E1-MOD-1" if relation=="MOD_APPLY" else "E1-CALL-1",
                src_anchor=anchor(src_node),dst_anchor=anchor(target),file=file,
                source_sha256=sha,evidence=[],kind=kind)
        elif edges[ident]["kind"]!=kind:
            raise ValueError("Same declaration edge has inconsistent kinds")
        edges[ident]["evidence"].append(evidence)
        return "duplicate" if len(edges[ident]["evidence"])>1 else "emitted"

    for fn in sem.functions:
        if fn.type not in ("function_definition","constructor_definition","fallback_receive_definition"):
            continue
        invocations=[n for n in children(fn) if n.type=="modifier_invocation"
            and not (sem.text(n)=="constant" and not sem.members(fn).get("constant"))]
        for invocation in invocations:
            counts["modifier_invocations"]+=1
            target,status,reason,inherited=modifier_target(analyzer,fn,invocation)
            output=status
            if target is not None:
                counts["modifier_resolved"]+=1
                counts["modifier_inherited"]+=int(inherited)
                output=emit("MOD_APPLY",fn,target,dict(invocation_anchor=anchor(invocation),
                    reason=reason,inherited=inherited))
            statuses["MOD_APPLY:"+output]+=1
            reasons["MOD_APPLY:"+reason]+=1
            events.append(dict(relation="MOD_APPLY",anchor=anchor(invocation),owner_anchor=anchor(fn),
                target_anchor=anchor(target),status=status,outcome=output,reason=reason))
    seen=set()
    for statement in sem.nodes:
        if statement.type not in STATEMENTS:
            continue
        for call in sem.owned_nodes(statement):
            if call.type!="call_expression" or key(call) in seen:
                continue
            seen.add(key(call));counts["statement_calls"]+=1
            result=resolve_call(sem,call);target=result["target"]
            output=result["status"]
            if target is not None:
                counts["call_resolved"]+=1
                counts["call_kind:"+result["kind"]]+=1
                if key(target) not in function_keys:
                    raise ValueError("Call target outside same source file")
                output=emit("CALL_SITE",statement,target,dict(call_anchor=anchor(call),
                    kind=result["kind"],reason=result["reason"]),kind=result["kind"])
            statuses["CALL_SITE:"+output]+=1
            statuses["CALL_STATUS:"+result["status"]]+=1
            reasons["CALL_SITE:"+result["reason"]]+=1
            events.append(dict(relation="CALL_SITE",anchor=anchor(call),owner_anchor=anchor(statement),
                target_anchor=anchor(target),status=result["status"],outcome=output,
                kind=result["kind"],reason=result["reason"]))
    guard_rows,guard_audit=collect_guards(file,source,sem,raw,analyzer)
    result=list(edges.values())+guard_rows
    counts.update({"edges:"+r:sum(e["relation"]==r for e in result) for r in RELATIONS})
    return result,dict(file=file,source_sha256=sha,projected_nodes=len(raw),counts=dict(counts),
                      statuses=dict(statuses),reasons=dict(reasons),events=events,guards=guard_audit,
                      unresolved_modifier_declarations=describe_unresolved_modifiers(sem,analyzer,events))

def add_edges(nx_graph_copy,edges):
    """Return an independent deep copy with validated forward E1 edges.

    Taking a private copy here enforces the no-original-mutation guarantee even
    if the caller accidentally supplies the original. Original nodes and keyed
    edges retain their order and attributes; repeated E1 pairs are rejected.
    """
    if not isinstance(nx_graph_copy,nx.MultiDiGraph):
        raise TypeError("Expected a directed multigraph")
    records=list(edges);seen=set()
    for row in records:
        relation=row["relation"];src,dst=row["src"],row["dst"]
        if relation not in RELATIONS or src not in nx_graph_copy or dst not in nx_graph_copy or src==dst:
            raise ValueError("Invalid E1 endpoints/relation")
        if any(nx_graph_copy.nodes[n]["source_file"]!=row["file"] for n in (src,dst)):
            raise ValueError("Cross-file E1 edge")
        ident=(relation,src,dst)
        if ident in seen or any(d.get("edge_type")==relation for d in nx_graph_copy.get_edge_data(src,dst,default={}).values()):
            raise ValueError("Duplicate E1 edge")
        seen.add(ident)
        for name in ("src_anchor","dst_anchor"):
            a=row[name]
            if (not isinstance(a,list) or len(a)!=3 or type(a[0]) is not int
                    or type(a[1]) is not int or not 0<=a[0]<a[1] or not isinstance(a[2],str)):
                raise ValueError("Invalid provenance anchor")
        if relation=="MOD_APPLY":
            if row["src_anchor"][2] not in ("function_definition","constructor_definition","fallback_receive_definition") or row["dst_anchor"][2]!="modifier_definition":
                raise ValueError("Invalid modifier roles")
        elif relation=="CALL_SITE":
            if row["src_anchor"][2] not in STATEMENTS or row["dst_anchor"][2]!="function_definition":
                raise ValueError("Invalid call roles")
        elif row["src_anchor"][2] not in STATEMENTS or row["dst_anchor"][2] not in STATEMENTS:
            raise ValueError("Invalid GUARDS roles")
    graph=copy.deepcopy(nx_graph_copy)
    for row in records:
        graph.add_edge(row["src"],row["dst"],edge_type=row["relation"],edge_sem_provenance=copy.deepcopy(row))
    return graph
