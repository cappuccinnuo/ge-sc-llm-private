"""EP4 deterministic uint8[74] edge attributes; no labels or predictions.

The only spelling joins are exact frozen symbol/declaration identity joins in
attr_sources. All classification uses AST roles, operators or facts. Dataset
labels are read only by the separate descriptive attr_stats module.
"""
from collections import Counter, defaultdict
import numpy as np
from . import RELATION_FAMILY, NEW_RELATIONS

EDGE_FEATURE_NAMES = (
    "ctrl_src_dominates_dst", "ctrl_dst_postdominates_src", "ctrl_branch_contains_ext_call",
    "var_kind_local", "var_kind_parameter", "var_kind_return_var", "var_kind_other",
    "value_shape_mapping", "value_shape_array", "value_shape_address", "value_shape_integer",
    "value_shape_bool", "value_shape_bytes_string", "value_shape_struct_contract", "value_shape_other",
    "def_weak_update", "def_kind_assign", "def_kind_compound", "def_kind_decl_or_param", "def_kind_incdec_or_delete",
    "def_loop_carried", "use_path_crosses_ext_call",
    "use_context_condition", "use_context_call", "use_context_arithmetic", "use_context_state_write_value", "use_context_return",
    "arith_op_additive", "arith_op_multiplicative", "arith_op_exponent",
    "write_access_plain", "write_access_indexed", "write_access_member", "write_access_other",
    "write_op_assign", "write_op_increase", "write_op_decrease",
    "call_low_level", "call_delegatecall", "call_sends_value", "call_return_checked",
    "call_callee_writes_state", "call_callee_external_call",
    "guard_kind_require", "guard_kind_if_branch", "guard_kind_early_exit", "guard_kind_loop_cond",
    "guard_kind_modifier", "guard_kind_internal_check",
    "guard_operands_caller_identity", "guard_operands_block_time", "guard_operands_amount_balance",
    "guard_operands_external_result", "guard_operands_hash", "guard_operands_state",
    "ctx_src_is_ext_call", "ctx_dst_is_ext_call", "ctx_src_after_ext_call", "ctx_dst_after_ext_call",
    "ctx_in_loop", "ctx_leads_to_exit", "ctx_unchecked_arith", "ctx_fn_externally_visible", "ctx_call_in_loop",
    "env_kind_caller_identity", "env_kind_value", "env_kind_block_time_number", "env_kind_blockhash",
    "unk_cfg", "unk_dfg", "unk_order", "unk_state", "unk_guard", "call_to_library")
CORE_CANDIDATES = tuple(list(range(15)) + list(range(16,55)) + list(range(68,74)))
CONTEXT = tuple(range(55,68))
GROUPS = {
    "control": [0,1,2], "var_kind": list(range(3,7)), "value_shape": list(range(7,15)),
    "def_kind": list(range(16,20)), "data_path": [20,21],
    "use_context": list(range(22,27)), "arith_op": list(range(27,30)),
    "write_access": list(range(30,34)), "write_op": list(range(34,37)),
    "call": list(range(37,43)), "guard_kind": list(range(43,49)),
    "guard_operands": list(range(49,55)), "context": list(range(55,64)),
    "env_kind": list(range(64,68)), "unknown": list(range(68,73)), "library": [73]}
# User approved multi-evidence unions for var_kind and value_shape.
ONE_HOT_GROUPS = ("def_kind", "write_access", "write_op")
MULTI_HOT_GROUPS = ("var_kind", "value_shape")
DATA = frozenset(("DATA_DEF_USE","READS_STATE","WRITES_STATE","ENV_FLOW"))
STATE = frozenset(("READS_STATE","WRITES_STATE"))
CONTROL = frozenset(r for r,f in RELATION_FAMILY.items() if f=="control" and not r.startswith("REV_"))
GUARD_OPERANDS = {"msg.sender":49, "tx.origin":49, "timestamp":50, "block":50,
                  "msg.value":51, "balance":51, "external_result":52, "hash":53, "state":54}
GUARD_KINDS = ("require","if_branch","early_exit","loop_cond","modifier","internal_check")
SINK_BITS = {"guard":22,"loop_bound":22,"call_arg":23,"call_target":23,"call_value":23,"value":23,
             "arith":24,"state_write":25,"state":25,"return":26}
SHAPES = ("mapping","array","address","integer","bool","bytes_string","struct_contract","other")


def allowed_indices(relation):
    if relation not in RELATION_FAMILY or relation.startswith("REV_"):
        raise ValueError("Unknown or reverse relation in forward attributes")
    if relation == "recursive_method_call":
        return set()
    allowed = {55,56,57,58,59,62,63,70,72}
    if relation in CONTROL:
        allowed.update((0,1,60,68))
    if relation in ("pos_next","neg_next"):
        allowed.add(2)
    if relation in DATA:
        allowed.update((61,69))
    if relation in STATE:
        allowed.update(list(range(7,15))+[71])
    if relation == "DATA_DEF_USE":
        allowed.update(list(range(3,15))+list(range(16,30))+list(range(37,41))+[68])
    if relation == "WRITES_STATE":
        allowed.update(range(30,37))
    if relation in ("CALL_SITE","internal_call","external_call"):
        allowed.update((41,42))
    if relation in ("GUARDS","MOD_APPLY"):
        allowed.update(range(43,55))
    if relation == "ENV_FLOW":
        allowed.update(range(64,68))
    if relation == "CALL_SITE":
        allowed.add(73)
    return allowed


def validate_vector(vec, relation):
    a=np.asarray(vec)
    if a.dtype != np.uint8 or a.shape != (74,) or not np.isin(a,[0,1]).all():
        raise ValueError("Expected binary uint8[74]")
    if any(a[i] for i in set(range(74))-allowed_indices(relation)):
        raise ValueError("Inapplicable edge attribute")
    for group in ONE_HOT_GROUPS:
        if a[GROUPS[group]].sum()>1:
            raise ValueError("Invalid single-hot group: "+group)
    if relation=="DATA_DEF_USE" and not a[69]:
        if not a[3:7].any() or not a[7:15].any() or not a[16:20].any():
            raise ValueError("Known DATA_DEF_USE requires kinds and shape")
    if relation in STATE and not (a[69] or a[71]) and not a[7:15].any():
        raise ValueError("Known state edge requires shape")
    if relation=="WRITES_STATE" and not a[71] and not a[30:34].any():
        raise ValueError("Known write requires access class")
    # Unsupported multiplicative/other write operations deliberately have no bit.
    if a[27:30].any() and not a[24]:
        raise ValueError("Arithmetic bits require arithmetic use context")
    if a[37:41].any() and not a[23]:
        raise ValueError("Call bits require call use context")
    return a


def explain_edge(vec):
    a=np.asarray(vec)
    if a.dtype!=np.uint8 or a.shape!=(74,) or not np.isin(a,[0,1]).all():
        raise ValueError("Expected binary uint8[74]")
    return [name for i,name in enumerate(EDGE_FEATURE_NAMES) if a[i]]


def edge_rows(f3_graph, f4_edges):
    """Stable keys; sort original nx keys within each (src,dst,relation)."""
    groups=defaultdict(list)
    for src,dst,k,a in f3_graph.edges(keys=True,data=True):
        groups[(src,dst,a["edge_type"])].append((k,a))
    result=[]
    for (src,dst,relation), entries in groups.items():
        for ordinal,(nx_key,data) in enumerate(sorted(entries,key=lambda x:x[0])):
            file=f3_graph.nodes[src]["source_file"]
            result.append(dict(key="{}::{}->{}::{}::{}".format(file,src,dst,relation,ordinal),
                               src=src,dst=dst,relation=relation,file=file,k=ordinal,
                               nx_key=nx_key,data=data,origin="F3"))
    for row in f4_edges:
        identity=(row["src"],row["dst"],row["relation"])
        if identity in groups or row["relation"] not in NEW_RELATIONS:
            raise ValueError("Duplicate or non-E1 F4 record")
        if row["src"]==row["dst"] or any(n not in f3_graph for n in (row["src"],row["dst"])):
            raise ValueError("Invalid F4 endpoints")
        if any(f3_graph.nodes[n]["source_file"]!=row["file"] for n in (row["src"],row["dst"])):
            raise ValueError("Cross-file F4 record")
        groups[identity]=[row]
        result.append(dict(key="{}::{}->{}::{}::0".format(row["file"],row["src"],row["dst"],row["relation"]),
                           src=row["src"],dst=row["dst"],relation=row["relation"],file=row["file"],
                           k=0,nx_key=None,data=row,origin="F4"))
    if len({r["key"] for r in result})!=len(result):
        raise ValueError("Nonunique edge keys")
    return result


def endpoint_test(attrs, f4_edges, f3_graph):
    rows=edge_rows(f3_graph,f4_edges)
    if set(attrs)!={r["key"] for r in rows}:
        raise ValueError("Attribute edge population differs")
    output={}
    for bit in CORE_CANDIDATES:
        if 68<=bit<=72:
            output[bit]=dict(per_relation={},source=[0,0,None],target=[0,0,None],verdict="unknown_marker",positives=sum(int(v[bit]) for v in attrs.values()))
            continue
        per_relation={}
        for relation in sorted({r["relation"] for r in rows}):
            if bit not in allowed_indices(relation):
                continue
            subset=[r for r in rows if r["relation"]==relation]
            sides={}
            for name,field in (("source","src"),("target","dst")):
                groups=defaultdict(list)
                for r in subset:
                    groups[r[field]].append(int(attrs[r["key"]][bit]))
                qualified=[v for v in groups.values() if len(v)>=2 and any(v)]
                constant=sum(all(v) for v in qualified)
                sides[name]=[len(qualified),constant,constant/len(qualified) if qualified else None]
            per_relation[relation]=sides
        totals={}
        for side in ("source","target"):
            count=sum(x[side][0] for x in per_relation.values())
            constant=sum(x[side][1] for x in per_relation.values())
            totals[side]=[count,constant,constant/count if count else None]
        verdict=("endpoint" if any(v[0]>=30 and v[1]/v[0]>=.99 for v in totals.values())
                 else "undetermined" if all(v[0]<30 for v in totals.values()) else "core")
        output[bit]=dict(per_relation=per_relation,verdict=verdict,
                         positives=sum(int(v[bit]) for v in attrs.values()),**totals)
    return output


# Which known fields each unknown marker qualifies; no outcome labels involved.
UNKNOWN_DEPENDENCIES = {
    68: (0,1,20,21), 69: tuple(list(range(3,15))+list(range(16,20))+list(range(22,30))+list(range(37,41))),
    70: (57,58,63), 71: tuple(list(range(7,15))+list(range(30,37))),
    72: tuple(range(43,55))}


def select_groups(results):
    """Task-common selection: a bit moved in either task cannot remain core."""
    if not results:
        raise ValueError("Missing endpoint results")
    base=set(range(55,68));core=set();context=set(base);zero=[]
    decisions={}
    for b in CORE_CANDIDATES:
        if 68<=b<=72:continue
        entries=[r[b] for r in results.values()]
        if not sum(e["positives"] for e in entries):
            zero.append(b);core.add(b);decision="no_local_support"
        elif any(e["verdict"]=="endpoint" for e in entries):
            context.add(b);decision="endpoint"
        else:
            core.add(b);decision="undetermined" if any(e["verdict"]=="undetermined" for e in entries) else "core"
        decisions[b]=decision
    for unknown,fields in UNKNOWN_DEPENDENCIES.items():
        if not sum(r[unknown]["positives"] for r in results.values()):
            zero.append(unknown);core.add(unknown);decisions[unknown]="no_local_support"
            continue
        if set(fields)&core:core.add(unknown)
        if set(fields)&context:context.add(unknown)
    return dict(core_indices=sorted(core),context_indices=sorted(context),
                disabled_indices=[15],all_zero_candidates=sorted(zero),decisions=decisions,
                thresholds=dict(minimum_eligible_nodes=30,endpoint_ratio=.99),
                per_task_verdicts={t:{b:e["verdict"] for b,e in r.items()} for t,r in results.items()},
                task_rule="endpoint in either task moves to context; all-zero candidates retained as no_local_support")

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


def _compute_attributes(context, f3_graph, f4_edges, facts):
    from .attr_sources import (AttributeSource, declaration_shape, def_kind,
                              write_access, write_op, dominates, reaches, carried)
    from scripts.node_sem.facts_io import check_layer_edge
    from scripts.node_sem.facts_ast import key, contains
    from scripts.node_sem.carrier import row_key
    from scripts.DFG.dfg_v2.env import ENV_KEYS
    from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
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
    output={};diagnostics=[];cfg_audit={}
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
                from scripts.DFG.semantic_cfg import _if_bodies
                from scripts.DFG.models import Unsupported
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
                sinks=[r["sink"] for r in a["dfg"].get("to",()) if r["node"]==dst]
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
    return output,dict(edges=diagnostics,cfg=cfg_audit,original_graph_unchanged=True,
        label_used_for_features=False,reverse_edges_computed=False,
        unknown_fields_policy="Unrepresented unknowns remain zero with explicit per-edge reasons; zero does not imply absence")


def compute_attributes(context, f3_graph, f4_edges, facts):
    return _compute_attributes(context,f3_graph,f4_edges,facts)[0]


def write_attributes(task_id,out_dir):
    """Write both node tasks for a common selection, return the requested task ref."""
    from .attr_batch import write_batch
    return write_batch(out_dir,requested_task=task_id)
