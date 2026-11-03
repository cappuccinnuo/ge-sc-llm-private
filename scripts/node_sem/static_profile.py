"""Name-independent, schema-driven encoding of accepted StatementFacts v1.1."""
import json
from pathlib import Path
import numpy as np
from . import facts_schema as fs

SCHEMA_PATH = Path(__file__).with_name("behavior_schema.json")
VERSION = "nodesem-static-v2"
STMT, FUNC = list(fs.STATEMENT_KINDS), list(fs.FUNCTION_KINDS)


def schema_definition():
    """Persisted JSON is the column contract; unknown K/L/M lists derive from facts."""
    fields = []
    def add(group, name, kinds, values=None, encoding="multi_hot", unknown=None,
            unknown_policy="zero", unknown_exclude=()):
        options = list(values) if values is not None else ["true"]
        if encoding == "one_hot": options = ["not_applicable"] + options
        start = sum(len(x["values"]) for x in fields)
        fields.append(dict(group=group, name=name, encoding=encoding, values=options,
            start=start, stop=start+len(options), applicable=kinds,
            inapplicable="not_applicable" if encoding=="one_hot" else "zero", unknown=unknown,
            unknown_policy=unknown_policy, unknown_exclude=list(unknown_exclude)))
    add("A", "external.kinds", STMT, fs.EXTERNAL_KINDS)
    add("A", "external.uninvoked_call_value", STMT)
    add("A1", "external.value_attached", STMT)
    add("A2", "external.target_classes", STMT, fs.TARGET_CLASSES)
    add("A3", "external.value_class", STMT, fs.VALUE_CLASSES, "one_hot")
    add("A4", "external.data_class", STMT, fs.DATA_CLASSES, "one_hot")
    for name in ("write_count", "read_count"):
        add("B", "state."+name, STMT, ("zero","one","many"), "one_hot", "state")
    for name in ("write_indexed","write_scalar","read_indexed","write_auth","read_auth","array_size_change"):
        add("B", "state."+name, STMT, unknown="state", unknown_policy="keep_true")
    for name in ("reachable_from_ext_call","dominated_by_ext_call","write_then_call","call_then_write","ext_call_in_loop"):
        add("C", "order."+name, STMT, unknown="order", unknown_policy="keep_true")
    add("D", "guards.kinds", STMT, ("none",)+fs.GUARD_KINDS+("sender",), unknown="guard", unknown_policy="keep_true", unknown_exclude=("none",))
    add("D1", "guards.operands", STMT, fs.OPERAND_CLASSES, unknown="guard", unknown_policy="keep_true")
    add("D2", "guards.pairs", STMT, fs.EQ_PAIRS, unknown="guard", unknown_policy="keep_true")
    add("D3", "condition.present", ["condition"])
    add("D3", "self_condition.operand_classes", ["condition"], fs.OPERAND_CLASSES)
    add("D3", "self_condition.eq_pairs", ["condition"], fs.EQ_PAIRS)
    add("D3", "self_condition.early_exit_if", ["condition"])
    add("E", "env.merged", STMT+["state_decl","env"],
        ("msg.sender","msg.value","msg.data_sig","tx.origin","tx.gasprice","block.timestamp",
         "block.number","block.other","blockhash","gasleft","this.balance"))
    add("E1", "env.uses", STMT+["state_decl"], fs.ENV_USES)
    add("F", "external.return_handling", STMT, tuple(x for x in fs.RETURN_HANDLING if x!="not_applicable"), "one_hot")
    add("G", "arith.ops", STMT, fs.ARITH_OPS)
    for name in ("on_state","small_int","from_param","from_env","result_to_sensitive","in_unchecked"):
        add("G", "arith."+name, STMT)
    add("G", "arith.checked_by_helper", list(fs.APPLICABILITY["checked_call"]), unknown="checked_call")
    add("H", "loop.bound", STMT, ("none","constant","state","param_local","unknown"), "one_hot")
    add("I", "function_ctx.visibility", STMT+FUNC, ("default","public","external","internal","private"), "one_hot")
    for name in ("payable","read_only","is_constructor","is_fallback","has_modifier","name_case_only_differs_from_contract"):
        add("I", "function_ctx."+name, STMT+FUNC)
    add("J", "syntax", STMT+["state_decl"], fs.SYNTAX)
    add("K", "state_decl.shape", ["state_decl"], fs.SHAPES, "one_hot", "state_decl.shape")
    for name in ("public","constant_immutable","has_initializer","auth"):
        add("K", "state_decl."+name, ["state_decl"], unknown="state_decl."+name)
    add("K", "state_decl.write_functions", ["state_decl"], ("zero","one","many"), "one_hot", "state_decl.write_functions")
    for name in ("only_constructor_writes","unguarded_writer","read_in_guard","used_as_call_value_or_target"):
        add("K", "state_decl."+name, ["state_decl"], unknown="state_decl."+name)
    for name,value in fs.new_facts("function")["fn_summary"].items():
        if type(value) is bool: add("L", "fn_summary."+name, FUNC, unknown="fn_summary."+name)
    add("M", "contract_summary.kind", ["contract"], ("contract","library","interface"), "one_hot", "contract_summary.kind")
    for name in ("explicit_constructor","payable_fallback","selfdestruct","auth_state"):
        add("M", "contract_summary."+name, ["contract"], unknown="contract_summary."+name)
    for name in ("dfg","order","guard","state","projection"):
        add("N", "unknown."+name, list(fs.NODE_KINDS))
    add("N", "unknown.checked_call", list(fs.APPLICABILITY["checked_call"]))
    for group,kind in (("state_decl","state_decl"),("fn_summary","function"),("contract_summary","contract")):
        for name in sorted(set(fs.new_facts(kind)[group])-{"status","unknown_fields"}):
            add("N", "unknown."+group+"."+name, list(fs.APPLICABILITY[group]))
    return dict(version=VERSION, facts_version=fs.VERSION, fields=fields,
        dimension=sum(len(x["values"]) for x in fields),
        unknown_one_hot_rule="zero value bits plus N indicator; otherwise exactly one including not_applicable")


def load_schema(path=SCHEMA_PATH):
    schema=json.loads(Path(path).read_text(encoding="utf8"))
    if schema!=schema_definition(): raise ValueError("Behavior schema differs from versioned field contract")
    return schema


def unknown(facts, field):
    if field=="guard": return facts["guard_status"]=="unknown"
    if field=="projection": return any("projection_missing" in k for k in facts["unresolved"])
    if "." in field:
        group,name=field.split(".",1)
        return name in facts[group].get("unknown_fields",[])
    return facts.get(field,{}).get("status")=="unknown"


def _count(items):
    n=len({x["var"] for x in items})
    return "zero" if n==0 else "one" if n==1 else "many"


def _value(f,name):
    if name.startswith("unknown."): return unknown(f,name[len("unknown."):])
    if name=="arith.checked_by_helper":
        return f["checked_call"]["status"]=="supported" and f["checked_call"]["result_condition_check"]
    if name=="condition.present": return True
    if name.startswith("guards."):
        guards=f["guards"]
        if name=="guards.kinds":
            return (["none"] if not guards else [g["kind"] for g in guards])+(["sender"] if any(g["is_sender_guard"] for g in guards) else [])
        key="operand_classes" if name=="guards.operands" else "eq_pairs"
        return [x for g in guards if g["kind"]!="loop_cond" for x in g[key]]
    if name=="env.merged":
        merge={"msg.data":"msg.data_sig","msg.sig":"msg.data_sig","block.difficulty":"block.other","block.coinbase":"block.other","block.gaslimit":"block.other"}
        return [merge.get(x,x) for x in f["env"]["keys"]]
    if name=="arith.result_to_sensitive":
        return bool(set(f["arith"]["sinks"]) & {"state","state_write","guard","value","call_value"})
    state=f["state"]
    if name in ("state.write_count","state.read_count"):
        return _count(state["writes" if name=="state.write_count" else "reads"])
    if name in ("state.write_indexed","state.read_indexed","state.write_scalar"):
        items=state["reads" if name=="state.read_indexed" else "writes"]
        return any((x["shape"] not in ("mapping","array")) if name=="state.write_scalar" else (x["shape"] in ("mapping","array")) for x in items)
    if name in ("state.write_auth","state.read_auth"):
        return any(x["auth"] for x in state["writes" if name=="state.write_auth" else "reads"])
    value=f
    for part in name.split("."): value=value[part]
    return value


def encode(facts_row,schema=None):
    f=facts_row.get("facts",facts_row)
    fs.validate(f)
    schema=load_schema() if schema is None else schema
    out=np.zeros(schema["dimension"],dtype=np.uint8)
    for field in schema["fields"]:
        if f["node_kind"] not in field["applicable"]:
            values=["not_applicable"] if field["encoding"]=="one_hot" else []
        elif field["unknown"] and unknown(f,field["unknown"]) and field["unknown_policy"]=="zero": values=[]
        else:
            value=_value(f,field["name"])
            values=(["true"] if value else []) if type(value) is bool else ([value] if isinstance(value,str) else value)
        if field["unknown"] and unknown(f,field["unknown"]):
            values=[value for value in values if value not in field["unknown_exclude"]]
        for value in set(values):
            if value not in field["values"]: raise ValueError("Invalid behavior value for "+field["name"])
            out[field["start"]+field["values"].index(value)]=1
    return out


def column_names(schema=None):
    schema=load_schema() if schema is None else schema
    return [f["name"]+"="+v for f in schema["fields"] for v in f["values"]]


def explain(vector,schema=None):
    names=column_names(schema)
    vector=np.asarray(vector)
    if vector.shape!=(len(names),) or not np.isin(vector,[0,1]).all(): raise ValueError("Behavior vector must be binary with exact schema width")
    return [name for name,bit in zip(names,vector) if bit]


def from_explanation(names,schema=None):
    columns=column_names(schema)
    if len(set(names))!=len(names) or not set(names).issubset(columns): raise ValueError("Unknown or duplicate behavior column")
    return np.asarray([name in names for name in columns],dtype=np.uint8)
