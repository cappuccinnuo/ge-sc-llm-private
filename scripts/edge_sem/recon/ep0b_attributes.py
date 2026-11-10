"""Count feasibility of r4 attribute sources; never compute feature vectors."""
import argparse
import re
from collections import Counter, defaultdict
from .common import key, write
from .ep0b_common import OUT, contexts, file_views, anchor
from scripts.node_sem.facts_ast import shape, unwrap, walk, operator, FUNCTIONS
from scripts.node_sem.facts_cfg import FileCFG
from scripts.node_sem.facts_io import check_layer_edge
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint

# Read-only probe of the explicitly approved r4 rule. Production EP4 API is not
# implemented here. Reference facts_ast.shape SHA:
# 644ca31a1dd890f67ac850e28fa68b9ae6b585cb0be019a6611aba154fc1d5a5
def shape_safe(type_name):
    name = " ".join(type_name.split())
    if name.startswith("mapping"):
        return "mapping"
    if "[" in name:
        return "array"
    if name in ("address", "address payable"):
        return "address"
    # Restore the remaining frozen categories without its startswith(address).
    if name.startswith("address"):
        return "struct_contract" if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$.]*",name) else "other"
    return shape(type_name)


def declaration_shape(sem, statement, variable):
    """Follow r4 literally; partial/unresolved identifier matches stay unknown."""
    occurrences = [n for n in sem.owned_nodes(statement)
                   if n.type == "identifier" and sem.text(n) == variable]
    bindings = [sem.root_binding(n) for n in occurrences]
    declarations = {key(b["declaration"]): b for b in bindings if b["declaration"] is not None}
    missing = sum(b["declaration"] is None or not b["type_name"] for b in bindings)
    if len(declarations) > 1:
        status = "multiple_declarations"
    elif not occurrences:
        status = "no_identifier_occurrence"
    elif missing or not declarations:
        status = "unresolved_binding_or_type"
    else:
        status = "resolved"
    binding = next(iter(declarations.values())) if status == "resolved" else None
    return dict(status=status, occurrences=len(occurrences), unresolved_occurrences=missing,
                declarations=[list(x) for x in sorted(declarations)], declaration_count=len(declarations),
                type_name=binding["type_name"] if binding else None,
                shape=shape_safe(binding["type_name"]) if binding else None)


def def_kind(node):
    if node is None:
        return "unknown"
    if node.type in FUNCTIONS or node.type in ("variable_declaration_statement", "variable_declaration", "parameter"):
        return "decl_or_param"
    expression = unwrap(node)
    op = operator(expression)
    if expression.type in ("assignment_expression", "augmented_assignment_expression"):
        if op == "=":
            return "assign"
        if op.endswith("="):
            return "compound"
    if op in ("++", "--", "delete"):
        return "incdec_or_delete"
    return "unknown"


def write_access(node):
    if node is None:
        return "unknown"
    node = unwrap(node)
    return {"identifier":"plain", "array_access":"indexed",
            "member_expression":"member"}.get(node.type, "other")


def write_op(node):
    cursor = node
    while cursor is not None and cursor.type not in FUNCTIONS:
        if cursor.type in ("assignment_expression", "augmented_assignment_expression",
                           "update_expression", "unary_expression"):
            op = operator(cursor)
            return {"=":"assign", "+=":"increase", "++":"increase",
                    "-=":"decrease", "--":"decrease"}.get(op, "other")
        cursor = cursor.parent
    return "other"


def inspect(task):
    ctx = contexts(task)
    graph = ctx["graphs"]["F3"]
    before = graph_fingerprint(graph)
    rows, types, differences = [], Counter(), {}
    counts = defaultdict(Counter)
    unique_definitions = {}
    for index,(file,source,sub,sem,raw,inverse) in enumerate(file_views(ctx)):
        cfg = FileCFG(source,file,ctx["sources"][file].get("metadata"))
        functions = {file+":"+str(fn.start_byte):fn for fn in sem.functions}
        ast_by_key = {key(n):n for n in sem.nodes}
        for decl in sem.declarations:
            typ = sem.text(decl.child_by_field_name("type"))
            types[typ] += 1
            if shape(typ) != shape_safe(typ):
                differences.setdefault(typ,dict(old=shape(typ),safe=shape_safe(typ),declarations=[]))
                differences[typ]["declarations"].append(dict(file=file,source_sha256=ctx["sources"][file]["sha256"],
                                                            anchor=anchor(decl)))
        for s,t,k,attrs in sub.edges(keys=True,data=True):
            relation = attrs["edge_type"]
            if relation not in ("DATA_DEF_USE","READS_STATE","WRITES_STATE"):
                continue
            proof = check_layer_edge(s,t,attrs,ctx["audit"])
            evidence_rows = []
            for ev in proof:
                if relation == "DATA_DEF_USE":
                    symbol = cfg.symbol(functions[ev["function"]],ev["analysis_path"],ev["symbol"])
                    variable = symbol.name
                else:
                    variable = ev["state"]["name"]
                statement = raw[s if relation == "WRITES_STATE" else t]
                resolution = declaration_shape(sem,statement,variable)
                counts[relation+"_value_shape"][resolution["status"]] += 1
                item = dict(variable=variable,resolution=resolution)
                if relation == "DATA_DEF_USE":
                    kind = def_kind(raw[s])
                    counts["def_kind_edge_evidence"][kind] += 1
                    unique_definitions[(file,s,ev["symbol"])] = kind
                    item.update(def_kind=kind,symbol_identity=ev["symbol"])
                if relation == "WRITES_STATE":
                    occurrence = ev["occurrence"]
                    occurrence_key = (occurrence["start"],occurrence["end"],occurrence["role"])
                    node = ast_by_key.get(occurrence_key)
                    access = write_access(node)
                    counts["write_access_event"][access] += 1
                    op = write_op(node)
                    counts["write_op_event"][op] += 1
                    item.update(write_anchor=anchor(node),write_access=access,write_op=op,
                                occurrence_found=node is not None)
                evidence_rows.append(item)
            rows.append(dict(file=file,source_sha256=ctx["sources"][file]["sha256"],
                             relation=relation,source_node=s,target_node=t,edge_key=k,
                             evidence=evidence_rows))
        if index % 20 == 0:
            print(task,index+1,"/",len(ctx["sources"]),flush=True)
    counts["def_kind_unique_node_variable"].update(unique_definitions.values())
    assert graph_fingerprint(graph) == before
    write(OUT/("attributes_"+task+".json"),dict(task_id=task,provenance=ctx["provenance"],
        counts={k:dict(v)for k,v in counts.items()},data_edges=rows,
        type_names=dict(types),all_shape_differences=differences,
        counting_unit="edge evidence variable occurrence; unique defining node/variable also reported",
        input_graph_unchanged=True,production_edges_written=0,attribute_vectors_written=0,
        unknown_rule="Missing or any unresolved match stays unknown; more than one exact declaration is multiple."))
    print(task,{k:dict(v)for k,v in counts.items()},"shape_differences",list(differences),flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--task",required=True,choices=["reentrancy_node","access_control_node"])
    inspect(parser.parse_args().task)
