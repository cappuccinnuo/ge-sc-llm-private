"""TODO docstring."""
import copy
import re




# ----------------------------------------------------------------------
# node_sem/facts_schema
# Closed, JSON-safe statement-fact contract for the AST backend.
#
# Facts describe syntax and resolved declarations. Unknown analysis support is
# separate from a known absence. No target, dataset class or compiler version is
# part of the feature contract. Provenance remains outside the feature groups.
VERSION = "nodesem-statement-facts-v1.1"

NODE_KINDS = ("statement", "condition", "state_decl", "function", "modifier", "contract", "env", "end", "other")

EXTERNAL_KINDS = ("call", "delegatecall", "staticcall", "send", "transfer", "member", "new", "selfdestruct")

TARGET_CLASSES = ("msg.sender", "tx.origin", "param", "state", "local", "literal", "this", "other")

VALUE_CLASSES = ("none", "literal", "param", "state", "msg.value", "this.balance", "local", "arith", "unknown")

DATA_CLASSES = ("none", "msg.data", "param", "other")

RETURN_HANDLING = ("not_applicable", "checked_in_require", "checked_in_if", "assigned_checked", "assigned_unchecked", "ignored", "unknown")

OPERAND_CLASSES = ("msg.sender", "tx.origin", "state", "param", "local", "literal", "timestamp", "block", "msg.value", "balance", "external_result", "hash")

EQ_PAIRS = ("env_state", "env_param", "env_literal", "state_param", "hash_state_literal", "time_state_param")

ENV_KEYS = ("msg.sender", "msg.value", "msg.data", "msg.sig", "tx.origin", "tx.gasprice", "block.timestamp", "block.number", "block.difficulty", "block.coinbase", "block.gaslimit", "blockhash", "gasleft", "this.balance")

ENV_USES = ("arith", "hash", "guard", "state", "call")

ARITH_OPS = ("+", "-", "*", "/", "%", "**")

SINKS = ("state", "guard", "value", "local", "call_arg", "call_target", "return", "other", "call_value", "state_write", "arith", "hash_input", "array_index", "loop_bound")

SHAPES = ("mapping", "array", "address", "integer", "bool", "bytes_string", "struct_contract", "other")

SYNTAX = ("assign", "add_assign", "sub_assign", "compound_assign", "delete", "emit", "ternary", "index", "deep_member", "literal", "hash", "ecrecover", "abi_encode", "exit", "return", "assembly")

GUARD_KINDS = ("require", "if_branch", "early_exit", "loop_cond", "modifier", "internal_check")

SYMBOL_KINDS = ("local", "parameter", "return", "state", "unknown")

STATUSES = ("supported", "unknown")

STATEMENT_KINDS = ("statement", "condition")

FUNCTION_KINDS = ("function", "modifier")

_DEFAULTS = {
    "external": {"kinds": [], "value_attached": False, "uninvoked_call_value": False, "target_classes": [], "value_class": "none", "data_class": "none", "return_handling": "not_applicable"},
    "state": {"writes": [], "reads": [], "array_size_change": False, "status": "unknown"},
    "dfg": {"defs": [], "uses": [], "from": [], "to": [], "status": "unknown"},
    "order": {"reachable_from_ext_call": False, "dominated_by_ext_call": False, "write_then_call": False, "call_then_write": False, "ext_call_in_loop": False, "status": "unknown", "pre_ext_call": None},
    "checked_call": {"status": "not_applicable", "has_arithmetic": False, "has_guard": False, "result_condition_check": False},
    "self_condition": {"operand_classes": [], "eq_pairs": [], "early_exit_if": False},
    "env": {"keys": [], "uses": []},
    "arith": {"ops": [], "on_state": False, "small_int": False, "from_param": False, "from_env": False, "sinks": [], "in_unchecked": False},
    "loop": {"bound": "none"},
    "function_ctx": {"visibility": "default", "payable": False, "read_only": False, "is_constructor": False, "is_fallback": False, "has_modifier": False, "name_case_only_differs_from_contract": False},
    "state_decl": {"unknown_fields": [], "shape": "other", "public": False, "constant_immutable": False, "has_initializer": False, "auth": False, "write_functions": "zero", "read_functions": "zero", "unguarded_write_functions": 0, "status": "unknown", "only_constructor_writes": False, "unguarded_writer": False, "read_in_guard": False, "used_as_call_value_or_target": False},
    "fn_summary": {"unknown_fields": [], "status": "unknown", "external_call": False, "state_write": False, "sender_guard": False, "auth_write": False, "selfdestruct": False, "delegatecall": False, "loop": False, "ext_call_in_loop": False, "timestamp": False, "tx_origin": False, "write_then_call": False, "call_then_write": False},
    "contract_summary": {"unknown_fields": [], "status": "unknown", "kind": "contract", "auth_state_count": 0, "explicit_constructor": False, "payable_fallback": False, "selfdestruct": False, "auth_state": False},
}

APPLICABILITY = {
    "external": STATEMENT_KINDS, "state": STATEMENT_KINDS,
    "dfg": STATEMENT_KINDS, "order": STATEMENT_KINDS,
    "self_condition": ("condition",),
    "checked_call": STATEMENT_KINDS + FUNCTION_KINDS,
    "env": STATEMENT_KINDS + ("state_decl", "env"),
    "arith": STATEMENT_KINDS, "loop": STATEMENT_KINDS,
    "function_ctx": STATEMENT_KINDS + FUNCTION_KINDS,
    "state_decl": ("state_decl",), "fn_summary": FUNCTION_KINDS,
    "contract_summary": ("contract",),
}

def new_facts(node_kind):
    """Return independent defaults. Applicable but unanalysed support is unknown."""
    if node_kind not in NODE_KINDS:
        raise ValueError("unknown node kind: %r" % (node_kind,))
    out = {"node_kind": node_kind}
    for group, default in _DEFAULTS.items():
        out[group] = copy.deepcopy(default) if node_kind in APPLICABILITY[group] else {}
        if out[group] and "unknown_fields" in default:
            out[group]["unknown_fields"] = sorted(set(default) - {"status", "unknown_fields"})
    out.update({"guards": [], "guard_status": "none", "nearest": None,
                "syntax": [], "names": [], "unresolved": {},
                "provenance": {"source_sha256": "", "store_refs": [], "view": "original"}})
    return out

def _fail(path, message):
    raise ValueError("%s: %s" % (path, message))

def _enum(value, choices, path):
    if not isinstance(value, str) or value not in choices:
        _fail(path, "invalid enum %r" % (value,))

def _bool(value, path):
    if type(value) is not bool:
        _fail(path, "expected bool")

def _int(value, path, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        _fail(path, "expected integer" + (" >= %d" % minimum if minimum is not None else ""))

def _str(value, path):
    if not isinstance(value, str):
        _fail(path, "expected string")

def _node_id(value, path):
    if type(value) not in (str, int):
        _fail(path, "expected original string or integer node identity")

def _list(value, path):
    if not isinstance(value, list):
        _fail(path, "expected JSON list")

def _set(value, choices, path):
    _list(value, path)
    for v in value:
        _enum(v, choices, path)
    if len(set(value)) != len(value):
        _fail(path, "duplicate set member")

def _keys(obj, expected, path):
    if not isinstance(obj, dict) or set(obj) != set(expected):
        _fail(path, "keys must equal %s" % sorted(expected))

def validate(facts):
    """Raise ValueError on schema, enum, applicability or provenance violations."""
    if not isinstance(facts, dict):
        _fail("facts", "expected dict")
    kind = facts.get("node_kind")
    _enum(kind, NODE_KINDS, "node_kind")
    _keys(facts, new_facts(kind), "facts")
    for group, default in _DEFAULTS.items():
        obj = facts[group]
        if kind not in APPLICABILITY[group]:
            if obj != {}:
                _fail(group, "inapplicable group must be empty")
            continue
        _keys(obj, default, group)
        if "unknown_fields" in default:
            _set(obj["unknown_fields"], set(default) - {"status", "unknown_fields"}, group + ".unknown_fields")
            if (obj["status"] == "unknown") != bool(obj["unknown_fields"]):
                _fail(group, "unknown status must exactly match nonempty unknown_fields")
        for key, val in default.items():
            if type(val) is bool:
                _bool(obj[key], group + "." + key)
        if group == "external":
            _set(obj["kinds"], EXTERNAL_KINDS, group + ".kinds")
            _set(obj["target_classes"], TARGET_CLASSES, group + ".target_classes")
            _enum(obj["value_class"], VALUE_CLASSES, group + ".value_class")
            _enum(obj["data_class"], DATA_CLASSES, group + ".data_class")
            _enum(obj["return_handling"], RETURN_HANDLING, group + ".return_handling")
            if not obj["kinds"] and obj["return_handling"] != "not_applicable":
                _fail(group, "no invoked call has no return-handling fact")
        elif group == "state":
            _enum(obj["status"], STATUSES, group + ".status")
            for mode in ("reads", "writes"):
                _list(obj[mode], group + "." + mode)
                for item in obj[mode]:
                    _keys(item, ("var", "shape", "auth"), group + "." + mode)
                    _str(item["var"], "state.var")
                    _enum(item["shape"], SHAPES, "state.shape")
                    _bool(item["auth"], "state.auth")
        elif group == "dfg":
            _enum(obj["status"], STATUSES, group + ".status")
            for field in ("defs", "uses", "from", "to"):
                _list(obj[field], "dfg." + field)
                for item in obj[field]:
                    if field in ("defs", "uses"):
                        _keys(item, ("var", "kind", "from_offset"), "dfg." + field)
                        _str(item["var"], "dfg.var")
                        _enum(item["kind"], SYMBOL_KINDS, "dfg.kind")
                        if item["from_offset"] is not None:
                            _int(item["from_offset"], "dfg.from_offset")
                    else:
                        _keys(item, ("node", "offset", "sink") if field == "to" else ("node", "offset"), "dfg." + field)
                        _node_id(item["node"], "dfg.node")
                        if item["offset"] is not None:
                            _int(item["offset"], "dfg.offset")
                        if field == "to":
                            _enum(item["sink"], SINKS, "dfg.sink")
        elif group == "order":
            _enum(obj["status"], STATUSES, "order.status")
            if obj["pre_ext_call"] is not None:
                _keys(obj["pre_ext_call"], ("node", "offset"), "order.pre_ext_call")
                _node_id(obj["pre_ext_call"]["node"], "order.pre_ext_call.node")
                if obj["pre_ext_call"]["offset"] is not None:
                    _int(obj["pre_ext_call"]["offset"], "order.pre_ext_call.offset")
        elif group == "checked_call":
            _enum(obj["status"], ("supported", "unknown", "not_applicable"), "checked_call.status")
            if obj["result_condition_check"] and not (obj["has_arithmetic"] and obj["has_guard"]):
                _fail("checked_call", "result check requires operation and condition")
        elif group == "self_condition":
            _set(obj["operand_classes"], OPERAND_CLASSES, group + ".operand_classes")
            _set(obj["eq_pairs"], EQ_PAIRS, group + ".eq_pairs")
        elif group == "env":
            _set(obj["keys"], ENV_KEYS, "env.keys")
            _set(obj["uses"], ENV_USES, "env.uses")
            if kind == "env" and obj["uses"]:
                _fail("env.uses", "source node does not itself consume its environment value")
        elif group == "arith":
            _set(obj["ops"], ARITH_OPS, "arith.ops")
            _set(obj["sinks"], SINKS, "arith.sinks")
        elif group == "loop":
            _enum(obj["bound"], ("none", "constant", "state", "param_local", "unknown"), "loop.bound")
        elif group == "function_ctx":
            _enum(obj["visibility"], ("default", "public", "external", "internal", "private"), "function_ctx.visibility")
        elif group == "state_decl":
            _enum(obj["shape"], SHAPES, "state_decl.shape")
            _enum(obj["write_functions"], ("zero", "one", "many"), "state_decl.write_functions")
            _enum(obj["read_functions"], ("zero", "one", "many"), "state_decl.read_functions")
            _int(obj["unguarded_write_functions"], "state_decl.unguarded_write_functions", 0)
            _enum(obj["status"], STATUSES, "state_decl.status")
        elif group == "fn_summary":
            _enum(obj["status"], STATUSES, "fn_summary.status")
        elif group == "contract_summary":
            _enum(obj["kind"], ("contract", "library", "interface"), "contract_summary.kind")
            _int(obj["auth_state_count"], "contract_summary.auth_state_count", 0)
            _enum(obj["status"], STATUSES, "contract_summary.status")
    _list(facts["guards"], "guards")
    for g in facts["guards"]:
        _keys(g, ("rule", "kind", "polarity", "operand_classes", "eq_pairs", "is_sender_guard", "disjunctive", "offset"), "guard")
        _enum(g["rule"], ("1", "2", "3", "4", "5", "5p", "6"), "guard.rule")
        _enum(g["kind"], GUARD_KINDS, "guard.kind")
        _int(g["polarity"], "guard.polarity")
        if g["polarity"] not in (-1, 1):
            _fail("guard.polarity", "expected -1 or 1")
        _set(g["operand_classes"], OPERAND_CLASSES, "guard.operand_classes")
        _set(g["eq_pairs"], EQ_PAIRS, "guard.eq_pairs")
        _bool(g["is_sender_guard"], "guard.is_sender_guard")
        _bool(g["disjunctive"], "guard.disjunctive")
        if g["disjunctive"] and not g["is_sender_guard"]:
            _fail("guard", "disjunctive requires confirmed sender restriction")
        if g["offset"] is not None:
            _int(g["offset"], "guard.offset")
    _enum(facts["guard_status"], ("none", "present", "unknown"), "guard_status")
    near = facts["nearest"]
    if near is not None:
        _int(near, "nearest", 0)
        if near >= len(facts["guards"]):
            _fail("nearest", "must index a guard")
    if facts["guards"] and facts["guard_status"] == "none":
        _fail("guard_status", "known guards cannot have none status")
    if facts["guard_status"] == "present" and not facts["guards"]:
        _fail("guard_status", "present needs at least one guard")
    if kind not in STATEMENT_KINDS and (facts["guards"] or facts["guard_status"] != "none" or near is not None):
        _fail("guards", "inapplicable to this node kind")
    _set(facts["syntax"], SYNTAX, "syntax")
    if kind not in STATEMENT_KINDS + ("state_decl",) and facts["syntax"]:
        _fail("syntax", "inapplicable to this node kind")
    _list(facts["names"], "names")
    for name in facts["names"]:
        _str(name, "names")
    if len(set(facts["names"])) != len(facts["names"]):
        _fail("names", "duplicate name")
    if not isinstance(facts["unresolved"], dict):
        _fail("unresolved", "expected dict")
    for reason, count in facts["unresolved"].items():
        _str(reason, "unresolved reason")
        _int(count, "unresolved count", 1)
    provenance = facts["provenance"]
    _keys(provenance, ("source_sha256", "store_refs", "view"), "provenance")
    _str(provenance["source_sha256"], "provenance.source_sha256")
    if provenance["source_sha256"] and not re.fullmatch(r"[0-9a-f]{64}", provenance["source_sha256"]):
        _fail("provenance.source_sha256", "expected empty or lowercase SHA256")
    _enum(provenance["view"], ("original",), "provenance.view")
    _list(provenance["store_refs"], "provenance.store_refs")
    for ref in provenance["store_refs"]:
        _keys(ref, ("path", "sha256"), "provenance.store_refs")
        _str(ref["path"], "store ref path")
        if not isinstance(ref["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]):
            _fail("store ref sha256", "expected lowercase SHA256")
    return facts
