"""Compute the uint8[74] attribute vector of every F3/F4 edge from source facts (original view).
"""
from collections import defaultdict

import numpy as np

from edgesem.attributes.layout import (
    CONTROL, DATA, GUARD_KINDS, GUARD_OPERANDS, SHAPES, SINK_BITS, STATE, edge_rows, validate_vector)


def _unknown_group(fact, group):
    value=fact.get(group,{})
    return bool(value) and value.get("status")=="unknown"

def _field_unknown(value, field):
    return (not value or field not in value or field in value.get("unknown_fields",())
            or (value.get("status")=="unknown" and "unknown_fields" not in value))

def _fill_guards(vec, records):
    for record in records:
        vec[43+GUARD_KINDS.index(record["kind"])]=1
        for operand in record["operand_classes"]:
            if operand in GUARD_OPERANDS:vec[GUARD_OPERANDS[operand]]=1

def sealed_sinks(source, row, audit, source_fact):
    """The identical sink inputs used by frozen facts._bind_layers (lines 193-201)."""
    from nodesem.facts.state import check_layer_edge
    proof = check_layer_edge(row["src"], row["dst"], row["data"], audit)
    if not proof:
        raise ValueError("Missing sealed data evidence for sink")
    sinks = set()
    parameter = False
    for evidence in proof:
        fn = source.functions[evidence["function"]]
        symbol = source.cfg.symbol(fn, evidence["analysis_path"], evidence["symbol"])
        sinks.add(source.sem.sink(source.raw[row["dst"]], symbol))
        parameter |= symbol.kind == "parameter" and source.raw[row["src"]].type in (
            "function_definition", "constructor_definition", "fallback_receive_definition", "modifier_definition")
    recorded = {r["sink"] for r in source_fact["dfg"].get("to", ()) if r["node"] == row["dst"]}
    if recorded and recorded != sinks:
        raise ValueError("Recorded/frozen sink mismatch for " + row["key"] + ": " + repr((recorded, sinks)))
    return sorted(sinks), dict(edge_key=row["key"], source="recorded" if recorded else "frozen_sink_sealed_symbol",
                              sinks=sorted(sinks), parameter_entry=parameter, evidence_count=len(proof))

def _compute_attributes(context, f3_graph, f4_edges, facts):
    from edgesem.attributes.sources import AttributeSource
    from edgesem.attributes.sources import declaration_shape
    from edgesem.attributes.sources import def_kind
    from edgesem.attributes.sources import write_access
    from edgesem.attributes.sources import write_op
    from edgesem.attributes.sources import dominates
    from edgesem.attributes.sources import reaches
    from edgesem.attributes.sources import carried
    from nodesem.facts.state import check_layer_edge
    from nodesem.facts.syntax import key
    from nodesem.facts.syntax import contains
    from nodesem.rows import row_key
    from dfg.graph.env import ENV_KEYS
    from dfg.graph.audit import fingerprint as graph_fingerprint
    before=graph_fingerprint(f3_graph)
    rows=edge_rows(f3_graph,f4_edges)
    audit=context["f4_audit"]
    if not audit["hard_conditions_pass"]:
        raise ValueError("F4 guard mapping gate failed")
    target_guards={t["node"]:t for f in audit["files"] for t in f["guards"]["targets"]}
    mapped_facts={}
    for nid,a in f3_graph.nodes(data=True):
        ident=row_key(nid,a) if a["node_type"]=="env_source" else nid
        if ident not in facts:
            raise ValueError("Missing fact for exact node identity: "+str(nid))
        mapped_facts[nid]=facts[ident]
    by_file=defaultdict(list)
    for row in rows:by_file[row["file"]].append(row)
    output={};diagnostics=[];sink_records=[];cfg_audit={}
    for file,subset in sorted(by_file.items()):
        source=AttributeSource(context["source_text"][file],file,f3_graph,
                               context["sources"][file].get("metadata"))
        sha=context["sources"][file]["sha256"]
        if source.view.sha256!=sha:
            raise ValueError("Attribute/source identity differs")
        for t in target_guards.values():
            if t["node"] in source.raw and list(key(source.raw[t["node"]]))!=t["anchor"]:
                raise ValueError("Guard target exact AST identity differs")
        external=[n for n in source.raw if mapped_facts[n]["external"].get("kinds")]
        for row in subset:
            src,dst,rel=row["src"],row["dst"],row["relation"]
            v=np.zeros(74,dtype=np.uint8);missing={};gaps=[]
            def unknown(bits,reason,marker=None):
                for b in bits:
                    v[b]=0;missing.setdefault(str(b),[]).append(reason)
                if marker is not None:v[marker]=1
            if rel=="recursive_method_call":
                output[row["key"]]=v
                continue
            a,b=mapped_facts[src],mapped_facts[dst]
            v[55]=bool(a["external"].get("kinds"));v[56]=bool(b["external"].get("kinds"))
            for bit,fact,field in ((57,a,"reachable_from_ext_call"),(58,b,"reachable_from_ext_call"),
                                   (63,b,"ext_call_in_loop")):
                value=fact["order"]
                if value.get("status")=="unknown":unknown([bit],"order.status=unknown",70)
                else:v[bit]=bool(value.get(field,False))
            bound=b["loop"].get("bound","none")
            if bound=="unknown":unknown([59],"loop.bound=unknown")
            else:v[59]=bound!="none"
            v[62]=b["function_ctx"].get("visibility") in ("public","external","default")
            if dst in target_guards:
                v[72]=target_guards[dst]["guard_status"]=="unknown"
            if rel in CONTROL or rel=="DATA_DEF_USE":
                semantic=source.endpoints(src,dst)
                path_bits=[0,1] if rel in CONTROL else [20,21]
                if semantic is None:unknown(path_bits,"semantic_cfg_or_endpoint_unavailable",68)
                elif rel in CONTROL:
                    left,right=semantic["blocks"][src],semantic["blocks"][dst]
                    v[0]=all(any(dominates(semantic["dom"],x,y) for x in left) for y in right)
                    if not (left|right)<=set(semantic["post"]):
                        unknown([1],"postdominance_exit_unreachable",68)
                    else:v[1]=all(any(dominates(semantic["post"],y,x) for y in right) for x in left)
                else:
                    v[20]=carried(semantic,src,dst)
                    fn=source.sem.owner(source.raw[src])
                    calls=[n for n in external if key(source.sem.owner(source.raw[n]))==key(fn)]
                    hits=[n for n in calls if semantic["blocks"].get(n)
                          and reaches(semantic,src,n) and reaches(semantic,n,dst)]
                    if hits:v[21]=1
                    elif any(n not in semantic["blocks"] for n in calls):
                        unknown([21],"external_call_cfg_anchor_unavailable",68)
            if rel in CONTROL:
                v[60]=bool(set(b["syntax"])&{"exit","return"})
            if rel in ("pos_next","neg_next"):
                from dfg.analysis.cfg import _if_bodies
                from dfg.analysis.ir import Unsupported
                ast=source.raw.get(src);branch=None;branch_known=False
                if ast is not None:
                    try:
                        if ast.type=="if_statement":
                            yes,no=_if_bodies(ast)
                            branch=yes if rel=="pos_next" else no
                            branch_known=True
                        elif ast.type in ("for_statement","while_statement","do_while_statement"):
                            branch=ast.child_by_field_name("body") if rel=="pos_next" else None
                            branch_known=True
                    except Unsupported:
                        pass
                if not branch_known:unknown([2],"branch_ast_unavailable")
                elif branch is not None:v[2]=any(contains(branch,source.raw[n]) for n in external)
            if rel in DATA:
                dfg_unknown=_unknown_group(a,"dfg") or _unknown_group(b,"dfg")
                v[69]=dfg_unknown
                sinks=[]
                if rel == "DATA_DEF_USE":
                    sinks, sink_record = sealed_sinks(source, row, context["audit"], a)
                    sink_record["dfg_unknown"] = dfg_unknown
                    sink_records.append(sink_record)
                if rel != "DATA_DEF_USE":
                    gaps.append("use_context_inapplicable_no_frozen_sink")
                elif dfg_unknown:
                    unknown(list(range(22,30))+list(range(37,41)),"dfg.status=unknown",69)
                elif not sinks:
                    gaps.append("no_exact_dfg_to_for_this_edge")
                else:
                    for sink in sinks:
                        if sink in SINK_BITS:v[SINK_BITS[sink]]=1
                    if v[24]:
                        ops=set(b["arith"].get("ops",()))
                        v[27]=bool(ops&{"+","-"});v[28]=bool(ops&{"*","/","%"});v[29]="**" in ops
                    if v[23]:
                        e=b["external"];kinds=set(e.get("kinds",()))
                        v[37]=bool(kinds&{"call","send","delegatecall","staticcall"})
                        v[38]="delegatecall" in kinds;v[39]=bool(e.get("value_attached"))
                        if e.get("return_handling")=="unknown":
                            unknown([40],"external.return_handling=unknown")
                        else:v[40]=e.get("return_handling") in ("checked_in_require","checked_in_if","assigned_checked")
                if b["arith"].get("in_unchecked"):v[61]=1
                elif source.pre_08 is not None:v[61]=source.pre_08
                else:unknown([61],"pragma_not_proven_pre_or_post_0_8")
            if rel in ("DATA_DEF_USE","READS_STATE","WRITES_STATE"):
                proof=check_layer_edge(src,dst,row["data"],context["audit"])
                if not proof:raise ValueError("Missing sealed data evidence")
                statement=src if rel=="WRITES_STATE" else dst
                types=set();type_missing=False;kinds=set();evidence_details=[]
                for evidence in proof:
                    if rel=="DATA_DEF_USE":
                        fn=source.functions[evidence["function"]]
                        symbol=source.cfg.symbol(fn,evidence["analysis_path"],evidence["symbol"])
                        variable=symbol.name
                        matched=[x["kind"] for x in b["dfg"].get("uses",()) if x["var"]==variable]
                        if not b["dfg"]:
                            # Frozen NodeSem excludes raw for-loop updates from
                            # statement facts. The exact sealed symbol lookup
                            # above is the same source used to populate uses.
                            gaps.append("target_dfg_inapplicable_var_kind_from_sealed_symbol")
                        elif symbol.kind not in matched:
                            raise ValueError("Frozen dfg uses disagree with sealed symbol")
                        kinds.add({"local":3,"parameter":4,"return":5}.get(symbol.kind,6))
                    else:variable=evidence["state"]["name"]
                    resolution=declaration_shape(source.sem,source.raw[statement],variable)
                    if resolution["status"]=="resolved":types.add(resolution["shape"])
                    else:type_missing=True
                    evidence_details.append(dict(status=resolution["status"],shape=resolution["shape"],
                                                 declarations=resolution["declarations"]))
                state_unknown=rel in STATE and _unknown_group(mapped_facts[statement],"state")
                if state_unknown:
                    v[71]=1;unknown(list(range(7,15)),"state.status=unknown",71)
                elif rel=="DATA_DEF_USE" and v[69]:
                    unknown(list(range(3,15))+list(range(16,20)),"dfg.status=unknown",69)
                else:
                    for shape in types:v[7+SHAPES.index(shape)]=1
                    if type_missing:
                        # Known evidence remains a union; unresolved evidence is
                        # represented separately, rather than treated as absence.
                        v[69]=1;missing["7-14"]=["one_or_more_declaration_types_unresolved"]
                if rel=="DATA_DEF_USE" and not dfg_unknown:
                    for bit in kinds:v[bit]=1
                    dk=def_kind(source.raw.get(src))
                    if dk=="unknown":unknown(list(range(16,20)),"definition_ast_kind_unavailable",69)
                    else:v[16+("assign","compound","decl_or_param","incdec_or_delete").index(dk)]=1
                if rel=="WRITES_STATE":
                    access=set();ops=set();absent=False
                    for evidence in proof:
                        o=evidence["occurrence"]
                        node=source.ast.get((o["start"],o["end"],o["role"]))
                        absent|=node is None
                        access.add(write_access(node));ops.add(write_op(node))
                    if state_unknown or absent:
                        unknown(list(range(30,37)),"state_unknown_or_write_anchor_missing",71)
                    else:
                        if len(access)!=1:
                            unknown(list(range(30,34)),"mixed_write_access",71)
                        else:v[30+("plain","indexed","member","other").index(next(iter(access)))]=1
                        if len(ops)!=1:
                            unknown(list(range(34,37)),"mixed_write_operations",71)
                        elif next(iter(ops)) in ("assign","increase","decrease"):
                            v[34+("assign","increase","decrease").index(next(iter(ops)))]=1
            if rel in ("CALL_SITE","internal_call","external_call"):
                summary=b["fn_summary"]
                for bit,field in ((41,"state_write"),(42,"external_call")):
                    if _field_unknown(summary,field):unknown([bit],"fn_summary."+field+"=unknown_or_inapplicable")
                    else:v[bit]=summary[field]
            if rel=="CALL_SITE":v[73]=row["data"]["kind"]=="library"
            if rel=="GUARDS":_fill_guards(v,row["data"]["evidence"])
            if rel=="MOD_APPLY":
                _fill_guards(v,source.modifier_records(src,dst))
                v[72]=source.function_guard_unknown(src)
            if rel=="ENV_FLOW":
                env=f3_graph.nodes[src]["code"]
                if env not in ENV_KEYS:raise ValueError("Unknown reserved environment expression")
                env_bits={"msg.sender":64,"tx.origin":64,"msg.value":65,
                          "block.timestamp":66,"block.number":66,"blockhash":67}
                if env in env_bits:v[env_bits[env]]=1
            validate_vector(v,rel)
            output[row["key"]]=v
            if missing or gaps:
                diagnostics.append(dict(edge_key=row["key"],relation=rel,unknown_fields=missing,source_gaps=gaps))
        cfg_audit[file]=dict(functions=len(source.cfg_cache),
            supported=sum(r["status"]=="supported" for r in source.cfg_cache.values()),
            unknown=sum(r["status"]=="unknown" for r in source.cfg_cache.values()),
            pre_08=source.pre_08)
    if graph_fingerprint(f3_graph)!=before:
        raise AssertionError("Original F3 graph mutated")
    if set(output)!={r["key"] for r in rows}:raise ValueError("Incomplete edge attributes")
    return output,dict(edges=diagnostics,sinks=sink_records,cfg=cfg_audit,original_graph_unchanged=True,
        label_used_for_features=False,reverse_edges_computed=False,
        unknown_fields_policy="Unrepresented unknowns remain zero with explicit per-edge reasons; zero does not imply absence")

def compute_attributes(context, f3_graph, f4_edges, facts):
    return _compute_attributes(context,f3_graph,f4_edges,facts)[0]
