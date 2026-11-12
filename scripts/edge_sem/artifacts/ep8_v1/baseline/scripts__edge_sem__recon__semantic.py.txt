"""EP0 statistics only: use frozen parsers/resolvers, never write graph edges."""
import argparse
import copy
from collections import Counter, defaultdict
import networkx as nx
import torch
from .common import OUT, ROOT, read, write, ref, checked, key, histogram, typed_data, canonical_rows, cfg_dominance

def graph_counts(graph):
    from sco_models import graph_utils as gu
    from scripts.DFG.dfg_v2 import FORWARD_RELATIONS
    from scripts.DFG.dfg_v2.model_input import edge_data, materialize
    working=gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(graph)))
    raw=edge_data(working)
    base={c:v for c,v in raw.items() if c[1] not in FORWARD_RELATIONS}
    reflected=gu.reflect_graph(base)
    merge=materialize(raw,"G3R")
    typed,_=typed_data(raw)
    same=[dict(canonical=list(c),forward_edges=len(v[0]),reflected_edges=len(reflected[c][0]))
          for c,v in base.items() if c[0]==c[2]]
    collisions=[dict(canonical=list(c),forward_edges=len(v[0]),
        incoming_reverse_edges=len(base[(c[2],c[1],c[0])][0]),reflected_edges=len(reflected[c][0]))
        for c,v in base.items() if c[0]!=c[2] and (c[2],c[1],c[0]) in base]
    return dict(raw=canonical_rows(raw),reflected_base=canonical_rows(reflected),
        merge=canonical_rows(merge),typed=canonical_rows(typed),
        same_type_merges=same,opposite_key_collisions=collisions,
        typed_sparse_lt20=[r for r in canonical_rows(typed) if r["edges"]<20],
        typed_count_distribution=histogram(len(v[0]) for v in typed.values()),
        relation_count_delta=len(typed)-len(merge),
        added_parameters_per_layer=(len(typed)-len(merge))*(2*8*16*16+8),
        parameter_formula="delta_R * (2 * heads * d_k^2 + heads), hidden=128, heads=8")

def nearest_events(ir, graph, block, forward):
    """Only contract eventless CFG blocks for projection; no guessed source lines."""
    todo=[block];seen=set();events=[]
    while todo:
        b=todo.pop()
        if b in seen:continue
        seen.add(b)
        if ir.blocks[b].events:
            events.append(ir.blocks[b].events[0 if forward else -1])
        else:
            todo.extend(graph.successors(b) if forward else graph.predecessors(b))
    return events

def cfg_file(cfg, sem, projection, projector, sub):
    rows=[]; back_pairs=set()
    for fn in sem.functions:
        if fn.child_by_field_name("body") is None:continue
        result=cfg.build(fn)
        row=dict(function=list(key(fn)),status=result["status"],errors=result.get("errors",{}))
        if result["status"]!="supported":
            rows.append(row);continue
        ir=result["ir"];g=nx.DiGraph()
        g.add_nodes_from(ir.blocks)
        for b in ir.blocks.values():g.add_edges_from((b.id,d)for d in b.successors)
        active,dom,post,back=cfg_dominance(g,ir.entry)
        anchors={e.anchor for b in ir.blocks.values()for e in b.events}
        mapped={}
        for a in anchors:
            try:
                nid=projector.by_ast.get(projection.compat_ids[projection.compat_key(a)])
            except (KeyError,ValueError):nid=None
            if nid is not None:mapped[a]=nid
        hits=set(); direct=0; projected=0
        for a,b in back:
            if ir.blocks[a].events and ir.blocks[b].events:direct+=1
            for left in nearest_events(ir,active,a,False):
                for right in nearest_events(ir,active,b,True):
                    s,t=mapped.get(left.anchor),mapped.get(right.anchor)
                    if s is None or t is None:continue
                    projected+=1
                    if sub.has_edge(s,t) and any(d.get("edge_type")=="next_line" for d in sub[s][t].values()):
                        hits.add((s,t))
        back_pairs.update(hits)
        row.update(route=result["route"],blocks=len(g),reachable=len(active),
            dominator_covered=len(dom),postdominator_covered=len(post)-1,
            postdominance_full=len(post)-1==len(active),semantic_backedges=len(back),
            backedges_direct_event_endpoints=direct,projected_backedge_candidate_pairs=projected,
            hcg_next_line_backedges=len(hits),event_anchors=len(anchors),
            mapped_event_anchors=len(mapped),unmapped_event_anchors=len(anchors)-len(mapped))
        rows.append(row)
    return rows,back_pairs

def prospective_rows(pairs,graph):
    out={}
    for rel,values in pairs.items():
        counts=Counter((graph.nodes[s]["node_type"],rel,graph.nodes[t]["node_type"])for s,t in values)
        out[rel]=dict(unique_forward=len(values),with_reverse=2*len(values),
            canonicals=[dict(canonical=list(c),edges=n)for c,n in sorted(counts.items())])
    return out

def observe(tid):
    from scripts.node_sem.facts_io import load_context
    from scripts.node_sem.facts import _raw_projection,kind_of,STATEMENTS
    from scripts.node_sem.facts_ast import AstSemantics, walk, unwrap
    from scripts.node_sem.facts_guards import GuardAnalyzer
    from scripts.node_sem.facts_cfg import FileCFG
    from scripts.DFG.dfg_v2.projection_view import ProjectionView
    from scripts.DFG.projection import Projector
    from scripts.DFG.models import Unsupported
    from scripts.DFG.state.stage_f.versioning import interval, effective_interval
    from scripts.DFG.dfg_v2.benchmark_v2.prepare_spelling import load_result
    from scripts.DFG.dfg_v2.benchmark_v2.anon_parity import node_code_view
    from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
    inputs=read(OUT/"inputs.json")["tasks"][tid]
    context=load_context(tid)
    graph=context["graphs"]["F3"];before=graph_fingerprint(graph)
    output=dict(task_id=tid,graph_counts=graph_counts(graph),files=[],source=inputs["graph_refs"]["F3"])
    pairs={r:set()for r in ("MOD_APPLY","CALL_SITE","GUARDS")}
    env=defaultdict(Counter)
    for n,a in graph.nodes(data=True):
        if a["node_type"]=="env_source":env[a["source_file"]][a["code"]]+=1
    output["env"]={f:dict(c)for f,c in sorted(env.items())}
    for index,(file,source) in enumerate(sorted(context["source_text"].items())):
        nodes=[n for n,a in graph.nodes(data=True)if a["source_file"]==file and a["node_type"]!="env_source"]
        sub=graph.subgraph(nodes).copy()
        projection=ProjectionView(source,file);projector=Projector(sub,projection)
        raw=_raw_projection(projection,projector);by_ast={key(a):n for n,a in raw.items()}
        sem=AstSemantics(projection);guards=GuardAnalyzer(sem)
        row=dict(file=file,source=context["sources"][file],original_projected=len(raw),
            ast_loops=dict(Counter(n.type for n in sem.nodes if n.type in ("for_statement","while_statement","do_while_statement"))),
            hcg_loops=dict(Counter(a["node_type"]for _,a in sub.nodes(data=True)if a["node_type"]in ("for","while","do","do_while"))))
        mods=Counter();calls=Counter();guard_stats=defaultdict(Counter);guard_dist=[];samples=[]
        for fn in sem.functions:
            guards._modifiers(fn)
            invocations=[n for n in fn.named_children if n.type=="modifier_invocation" and
                not (sem.text(n)=="constant" and not sem.members(fn).get("constant"))]
            scope=guards._scope(fn)
            for inv in invocations:
                mods["invocations"]+=1
                cs=inv.named_children
                ds=scope.declarations(sem.text(cs[0])) if scope and cs and cs[0].type=="identifier" else []
                if len(ds)!=1 or ds[0].type!="modifier_definition":
                    mods["binding_unresolved"]+=1;continue
                target=ds[0];mods["unique_definition"]+=1
                if scope.owner.get(target.start_byte)!=scope.contract:mods["inherited_definition"]+=1
                s,t=by_ast.get(key(fn)),by_ast.get(key(target))
                mods["definition_in_graph" if t is not None else "definition_missing"]+=1
                if s is not None and t is not None and s!=t:pairs["MOD_APPLY"].add((s,t));mods["both_endpoints"]+=1
        seen_calls=set()
        for statement in sem.nodes:
            if statement.type not in STATEMENTS:continue
            for call in sem.owned_nodes(statement):
                if call.type!="call_expression" or key(call) in seen_calls:continue
                seen_calls.add(key(call));calls["all_call_expressions"]+=1
                callee=unwrap(call.child_by_field_name("function"))
                resolved=sem.resolve_callable(call)
                if resolved is not None:
                    owner=sem.contract(resolved)
                    if owner is not None and owner.type=="library_declaration":
                        calls["excluded_library"]+=1;continue
                    calls["internal_candidates"]+=1;calls["unique_same_file_definition"]+=1
                    s,t=by_ast.get(key(statement)),by_ast.get(key(resolved))
                    if s is not None and t is not None and s!=t:
                        pairs["CALL_SITE"].add((s,t));calls["projected"]+=1
                    else:calls["endpoint_missing"]+=1
                elif callee is not None and callee.type=="identifier":
                    binding=sem.resolve_identifier(callee)
                    if binding["kind"] in ("function","unknown"):
                        # Unknown unqualified call is a candidate, never an asserted internal call.
                        calls["internal_candidates"]+=1
                        calls["unresolved_"+binding["kind"]]+=1
                    else:calls["excluded_"+binding["kind"]]+=1
                else:calls["excluded_member_new_or_call_wrapper"]+=1
        for nid,node in raw.items():
            if kind_of(node,sem) not in ("statement","condition"):continue
            result=guards.for_node(node);guard_dist.append(len(result["guards"]))
            for guard in result["guards"]:
                kind=guard["kind"];anchor=guard["_anchor"];s=by_ast.get(key(anchor))
                guard_stats[kind]["records"]+=1
                guard_stats[kind]["mapped" if s is not None else "unmapped"]+=1
                guard_stats[kind]["anchor_type:"+anchor.type]+=1
                if s is not None and s!=nid:pairs["GUARDS"].add((s,nid))
                if s==nid:guard_stats[kind]["self_skipped"]+=1
                if s is None and len(samples)<8:
                    samples.append(dict(kind=kind,anchor=list(key(anchor)),target=nid))
        row.update(modifiers=dict(mods),guard_analyzer_audit=dict(guards.audit),
            calls=dict(calls),guards={k:dict(v)for k,v in guard_stats.items()},
            guards_per_statement=histogram(guard_dist),guard_unmapped_examples=samples)
        cfg=FileCFG(source,file,context["sources"][file].get("metadata"))
        row["cfg_functions"],bp=cfg_file(cfg,sem,projection,projector,sub)
        row["hcg_backedges"]=sorted([list(x)for x in bp],key=str)
        row["unmapped_ast_statements"]=sum(n.type in STATEMENTS and key(n)not in by_ast for n in sem.nodes)
        row["pragma"]=[sem.text(n)for n in projection.tree.root_node.named_children if n.type=="pragma_directive"]
        for tag,operation in [("pragma_interval",lambda:interval(source,projection.tree.root_node)),
            ("effective_interval",lambda:effective_interval(source,projection.tree.root_node,context["sources"][file].get("metadata"))[0])]:
            try:
                iv=operation()
                row[tag]=dict(interval=iv,pre_08=(True if iv and iv[1]<=(0,8,0) else False if iv and iv[0]>=(0,8,0) else None))
            except Unsupported as exc:row[tag]=dict(unknown=str(exc))
        original,result=load_result(inputs["naming_sources"][file]);assert original==source
        renamed=ProjectionView(result["rewritten"],file)
        try:
            Projector(sub,renamed)
            direct=dict(passed=True)
        except Unsupported as exc:direct=dict(passed=False,reason=str(exc))
        codes,proof=node_code_view(sub,file,source,result)
        temp=copy.deepcopy(sub)
        for n,code in codes.items():temp.nodes[n]["code"]=code
        renamed_projector=Projector(temp,renamed)
        row["anonymous_projection"]=dict(direct_original_graph=direct,
            code_view_same_ast_to_hcg=projector.by_ast==renamed_projector.by_ast,
            code_view_nodes=len(codes),materialized_on_disk=False,
            original_sha=ref(checked(context["sources"][file]))["sha256"],
            naming_result=inputs["naming_sources"][file]["result"])
        assert row["anonymous_projection"]["code_view_same_ast_to_hcg"]
        output["files"].append(row)
        if index%10==0:print(tid,index+1,"/",len(context["sources"]),file,flush=True)
    output["prospective_relations"]=prospective_rows(pairs,graph)
    output["cf_back_existing_next_line"]=sum(len(r["hcg_backedges"])for r in output["files"])
    output["cf_back_enable_threshold50"]=output["cf_back_existing_next_line"]>=50
    output["graph_unchanged"]=graph_fingerprint(graph)==before
    assert output["graph_unchanged"]
    output["graphs_written"]=0;output["new_production_edges"]=0
    write(OUT/(tid+".json"),output)
    print("completed",tid,output["cf_back_existing_next_line"],output["prospective_relations"],flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--task",required=True)
    observe(parser.parse_args().task)
