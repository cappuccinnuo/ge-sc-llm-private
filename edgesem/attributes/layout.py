"""The 74-bit edge attribute layout, its per-relation validity rules and stable edge row keys.
"""
from collections import defaultdict

import numpy as np

from edgesem.schema import NEW_RELATIONS, RELATION_FAMILY


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
