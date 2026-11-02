"""NS-P3a original-spelling facts; source semantics plus frozen graph evidence.

No feature vectors, model fitting or anonymous-view production occurs here.
All graph projection uses the frozen exact AST Projector. Source spans and
symbol identities are transient joins and never enter feature groups.
"""
import argparse
import copy
import hashlib
import inspect
import json
from collections import Counter, defaultdict
from pathlib import Path

from scripts.DFG.frontend import walk
from scripts.DFG.models import Unsupported
from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref, write
from .carrier import row_key
from .facts_schema import new_facts, validate, VERSION
from .facts_ast import AstSemantics, key, shape, operator, FUNCTIONS, CONTRACTS, LOOPS
from .facts_guards import GuardAnalyzer
from .facts_cfg import FileCFG, apply_order
from .facts_io import load_context, check_layer_edge

ROOT = Path(__file__).resolve().parents[2]
STATEMENTS = frozenset(("expression_statement", "variable_declaration_statement",
    "return_statement", "continue_statement", "break_statement", "emit_statement",
    "revert_statement", "throw_statement", "if_statement", "for_statement",
    "while_statement", "do_while_statement", "assembly_statement"))


def kind_of(node, sem):
    if node.type in CONTRACTS:
        return "contract"
    if node.type in FUNCTIONS:
        return "modifier" if node.type == "modifier_definition" else "function"
    if node.type == "state_variable_declaration":
        return "state_decl"
    if node.type == "variable_declaration" and node.parent.type == "state_variable_declaration":
        return "state_decl"
    if node.type in ("if_statement", "for_statement", "while_statement", "do_while_statement"):
        return "condition"
    if node.type == "expression_statement":
        if any(n.type == "call_expression" and sem.builtin_call(n, ("require", "assert"))
               for n in sem.owned_nodes(node)):
            return "condition"
    if node.type in STATEMENTS or (node.type == "variable_declaration" and sem.owner(node) is not None):
        return "statement"
    return "other"


def _unique(items):
    seen, out = set(), []
    for item in items:
        frozen = json.dumps(item, sort_keys=True)
        if frozen not in seen:
            seen.add(frozen)
            out.append(item)
    return out


def _shape(node, sem):
    return shape(sem.text(node.child_by_field_name("type")))


def _count(n):
    return "zero" if n == 0 else "one" if n == 1 else "many"


def _raw_projection(view, projector):
    inverse = defaultdict(list)
    for raw, compat in view.mapping.items():
        inverse[compat].append(raw)
    result = {}
    by_id = {i: k for k, i in view.compat_ids.items()}
    for ast_id, nid in projector.by_ast.items():
        raw = inverse[by_id[ast_id]]
        if len(raw) != 1:
            raise ValueError("AST projection has no unique raw identity")
        result[nid] = view.raw_nodes[raw[0]]
    return result


def _offsets(nodes, sem):
    functions = defaultdict(list)
    for nid, node in nodes.items():
        fn = sem.owner(node)
        if fn is not None and kind_of(node, sem) in ("statement", "condition"):
            functions[key(fn)].append((node.start_byte, -node.end_byte, str(nid), nid))
    result = {}
    for group in functions.values():
        result.update({row[-1]: i for i, row in enumerate(sorted(group))})
    return result


def _relative(a, b, nodes, sem, offsets):
    if a not in offsets or b not in offsets or key(sem.owner(nodes[a])) != key(sem.owner(nodes[b])):
        return None
    return offsets[a] - offsets[b]


def _guard_records(raw, nid, node, nodes, sem, offsets):
    by_anchor = {key(ast): ident for ident, ast in nodes.items()}
    out = []
    for guard in raw:
        value = {k: v for k, v in guard.items() if not k.startswith("_")}
        source = by_anchor.get(key(guard.get("_anchor")))
        value["offset"] = _relative(source, nid, nodes, sem, offsets) if source is not None else None
        out.append(value)
    return out


def _base_rows(view, nodes, sem, guards, references):
    rows, offsets = {}, _offsets(nodes, sem)
    for nid, node in nodes.items():
        kind = kind_of(node, sem)
        record = new_facts(kind)
        record.update(sem.base_facts(node, kind))
        if kind in ("statement", "condition"):
            result = guards.for_node(node)
            record["guards"] = _guard_records(result["guards"], nid, node, nodes, sem, offsets)
            record["guard_status"] = result["guard_status"]
            record["nearest"] = result["nearest"]
            if kind == "condition" and result["self_condition"] is not None:
                record["self_condition"] = result["self_condition"]
            record["unresolved"].update(result["unresolved"])
            record["state"]["array_size_change"] = sem.array_size_change(node)
            record["order"]["ext_call_in_loop"] = bool(record["external"]["kinds"] and record["loop"]["bound"] != "none")
        if record["checked_call"]:
            record["checked_call"] = guards.checked_arithmetic(node)
        if kind == "state_decl":
            declaration = node.parent if node.type == "variable_declaration" else node
            record["state_decl"].update(shape=_shape(declaration, sem),
                public=any(sem.text(n) == "public" for n in declaration.named_children),
                constant_immutable=any(sem.text(n) in ("constant", "immutable") for n in declaration.children),
                has_initializer=declaration.child_by_field_name("value") is not None)
        if kind == "contract":
            record["contract_summary"]["kind"] = node.type.replace("_declaration", "")
        record["provenance"] = dict(source_sha256=view.sha256, store_refs=references, view="original")
        rows[nid] = record
    return rows, offsets


def _bind_layers(rows, nodes, graph, audit, file, sem, cfg, offsets, diagnostics):
    layers = audit["layers"]
    raw_functions = {file + ":" + str(fn.start_byte): fn for fn in sem.functions}
    function_records = {r["function"]: r for r in layers["L1"]["files"].get(file, {}).get("analysis", {}).get("functions", [])}
    for nid, node in nodes.items():
        fn = sem.owner(node)
        ident = file + ":" + str(fn.start_byte) if fn is not None else None
        if rows[nid]["dfg"] and function_records.get(ident, {}).get("status") == "supported":
            rows[nid]["dfg"]["status"] = "supported"
        if rows[nid]["state"]:
            rec = layers["L2"]["files"].get(file, {})
            if ident in rec.get("callables", {}):
                rows[nid]["state"]["status"] = "supported"
    # Any unresolved state access in an owning callable remains explicit.
    for d in layers["L2"]["files"].get(file, {}).get("diagnostics", []):
        if "unresolved" not in d.get("kind", "") and "fallback" not in d.get("kind", ""):
            continue
        fn = raw_functions.get(d.get("callable"))
        for nid, node in nodes.items():
            if rows[nid]["state"] and fn is not None and key(sem.owner(node)) == key(fn):
                rows[nid]["state"]["status"] = "unknown"
                if d.get("kind") == "state_alias_unresolved":
                    rows[nid]["unresolved"]["state_alias_unresolved"] = 1
                reason = "state_" + d.get("reason", "unresolved")
                rows[nid]["unresolved"][reason] = rows[nid]["unresolved"].get(reason, 0) + 1
    for ev in layers["L2"].get("evidence", []):
        if ev.get("file") != file or ev.get("status") == "projected":
            continue
        fn = raw_functions.get(ev.get("callable"))
        for nid, node in nodes.items():
            if rows[nid]["state"] and fn is not None and key(sem.owner(node)) == key(fn):
                rows[nid]["state"]["status"] = "unknown"
                rows[nid]["unresolved"]["state_projection_missing"] = rows[nid]["unresolved"].get("state_projection_missing", 0) + 1
                if ev.get("relation") == "WRITES_STATE":
                    rows[nid]["unresolved"]["state_write_projection_missing"] = 1
    lookup_count = 0
    for source, target, attrs in graph.edges(data=True):
        proof = check_layer_edge(source, target, attrs, audit)
        if not proof:
            continue
        relation = attrs["edge_type"]
        for ev in proof:
            if relation == "DATA_DEF_USE":
                fn = raw_functions.get(ev["function"])
                if fn is None or function_records.get(ev["function"], {}).get("status") != "supported":
                    raise ValueError("L1 edge belongs to non-supported function")
                symbol = cfg.symbol(fn, ev["analysis_path"], ev["symbol"])
                lookup_count += 1
                if source not in rows or target not in rows:
                    raise ValueError("Evidence endpoint lacks exact AST projection")
                distance = _relative(source, target, nodes, sem, offsets)
                if rows[source]["dfg"]:
                    rows[source]["dfg"]["defs"].append(dict(var=symbol.name, kind=symbol.kind, from_offset=0))
                    rows[source]["dfg"]["to"].append(dict(node=target,
                        offset=_relative(target, source, nodes, sem, offsets), sink=sem.sink(nodes[target], symbol)))
                if rows[target]["dfg"]:
                    rows[target]["dfg"]["uses"].append(dict(var=symbol.name, kind=symbol.kind, from_offset=distance))
                    rows[target]["dfg"]["from"].append(dict(node=source, offset=distance))
            elif relation in ("READS_STATE", "WRITES_STATE"):
                declaration = source if relation == "READS_STATE" else target
                statement = target if relation == "READS_STATE" else source
                if declaration not in nodes or statement not in nodes:
                    raise ValueError("State evidence endpoint lacks exact AST projection")
                if not rows[statement]["state"]:
                    continue
                decl = nodes[declaration]
                if decl.type == "variable_declaration" and decl.parent.type == "state_variable_declaration":
                    decl = decl.parent
                evidence_key = (ev["state"]["start"], ev["state"]["end"], ev["state"]["role"])
                if key(decl) != evidence_key:
                    raise ValueError("State declaration exact identity differs")
                names = attrs.get("state_vars", [])
                name = ev["state"]["name"]
                if name not in names:
                    raise ValueError("State spelling missing from sealed edge")
                mode = "reads" if relation == "READS_STATE" else "writes"
                rows[statement]["state"][mode].append(dict(var=name, shape=_shape(decl, sem), auth=False))
            elif relation == "ENV_FLOW":
                if target not in rows:
                    raise ValueError("Environment target lacks exact AST projection")
                if rows[target]["env"]:
                    rows[target]["env"]["keys"] = sorted(set(rows[target]["env"]["keys"]) | {ev["env_key"]})
    for record in rows.values():
        if record["dfg"]:
            for field in ("defs", "uses", "from", "to"):
                record["dfg"][field] = _unique(record["dfg"][field])
        if record["state"]:
            for field in ("reads", "writes"):
                record["state"][field] = _unique(record["state"][field])
        record["names"] = sorted({x["var"] for group, fields in (("dfg", ("defs", "uses")), ("state", ("reads", "writes")))
                                  for field in fields for x in record[group].get(field, [])})
    diagnostics["symbol_exact_lookups"] = lookup_count


def _summaries(rows, nodes, sem, guards, graph=None):
    auth = {key(c): guards.auth_declarations(c) for c in sem.contracts}
    # A shared declaration node represents confirmed uses across this file.
    # Statement, function and contract summaries retain their scoped identities.
    declaration_auth = set().union(*auth.values()) if auth else set()
    declaration_scopes = defaultdict(set)
    for contract in sem.contracts:
        for declarations in sem.members(contract).values():
            for declaration in declarations:
                declaration_scopes[key(declaration)].add(key(contract))
    by_function = defaultdict(list)
    for nid, node in nodes.items():
        fn = sem.owner(node)
        if fn is not None and rows[nid]["node_kind"] in ("statement", "condition"):
            by_function[key(fn)].append(nid)
        if rows[nid]["state"]:
            members = sem.members(node)
            for field in ("reads", "writes"):
                for item in rows[nid]["state"][field]:
                    declarations = members.get(item["var"], [])
                    if len(declarations) == 1:
                        item["auth"] = key(declarations[0]) in auth.get(key(sem.contract(node)), set())
    for nid, node in nodes.items():
        record = rows[nid]
        if record["state_decl"]:
            decl = node.parent if node.type == "variable_declaration" else node
            info = record["state_decl"]
            info["auth"] = key(decl) in declaration_auth
            readers, writers, unguarded = set(), set(), set()
            if graph is not None:
                related = [(src, dst, d) for src, dst, d in graph.edges(data=True)
                           if (src == nid and d.get("edge_type") == "READS_STATE") or
                              (dst == nid and d.get("edge_type") == "WRITES_STATE")]
                for src, dst, attrs in related:
                    writing = attrs["edge_type"] == "WRITES_STATE"
                    other = src if writing else dst
                    if other not in nodes:
                        continue
                    fn = sem.owner(nodes[other])
                    if fn is None:
                        continue
                    (writers if writing else readers).add(key(fn))
                    if writing and rows[other]["guard_status"] != "unknown" and not any(g["is_sender_guard"] for g in rows[other]["guards"]):
                        unguarded.add(key(fn))
                    if not writing and rows[other]["node_kind"] == "condition":
                        info["read_in_guard"] = True
                    if not writing and rows[other]["external"]:
                        for call in sem.calls(nodes[other]):
                            if not call["invoked"]:
                                continue
                            for expression in (call["target"], call["value"]):
                                if expression is not None and any(key(sem.resolve_identifier(x).get("declaration")) == key(decl) for x in sem.identifiers(expression)):
                                    info["used_as_call_value_or_target"] = True
                info.update(read_functions=_count(len(readers)), write_functions=_count(len(writers)),
                            unguarded_writer=bool(unguarded), unguarded_write_functions=len(unguarded))
                callable_by_key = {key(fn): fn for fn in sem.functions}
                info["only_constructor_writes"] = bool(writers) and all(
                    sem.function_context(callable_by_key[x])["is_constructor"] for x in writers)
                # Source-level missing projections/bindings cannot establish absence.
                scopes = declaration_scopes[key(decl)] | {key(sem.contract(node))}
                siblings = [r for other, r in rows.items() if r["state"] and key(sem.contract(nodes[other])) in scopes]
                incomplete_projection = any(r["unresolved"].get("projection_missing") for other, r in rows.items()
                    if key(sem.contract(nodes[other])) in scopes)
                info["status"] = "unknown" if incomplete_projection or any(r["state"]["status"] == "unknown" or r["guard_status"] == "unknown" or r["unresolved"].get("projection_missing") for r in siblings) else "supported"
        if record["fn_summary"]:
            children = [rows[x] for x in by_function[key(node)]]
            info = record["fn_summary"]
            info.update(external_call=any(r["external"]["kinds"] for r in children),
                state_write=any(r["state"]["writes"] for r in children),
                sender_guard=any(g["is_sender_guard"] for r in children for g in r["guards"]) or any(set(rows[x]["self_condition"].get("eq_pairs", [])) & {"env_state", "env_param", "env_literal"} for x in by_function[key(node)] if nodes[x].type not in LOOPS),
                auth_write=any(x["auth"] for r in children for x in r["state"]["writes"]),
                selfdestruct=any("selfdestruct" in r["external"]["kinds"] for r in children),
                delegatecall=any("delegatecall" in r["external"]["kinds"] for r in children),
                loop=any(x.type in LOOPS for x in walk(node)),
                ext_call_in_loop=any(r["order"]["ext_call_in_loop"] for r in children),
                timestamp=any("block.timestamp" in r["env"]["keys"] for r in children),
                tx_origin=any("tx.origin" in r["env"]["keys"] for r in children),
                write_then_call=any(r["order"]["write_then_call"] for r in children),
                call_then_write=any(r["order"]["call_then_write"] for r in children),
                status="unknown" if not children or any(r["state"]["status"] == "unknown" or
                    r["order"]["status"] == "unknown" or r["guard_status"] == "unknown" or r["unresolved"].get("projection_missing") for r in children) else "supported")
    for nid, node in nodes.items():
        info = rows[nid]["contract_summary"]
        if not info:
            continue
        children = [r for other, r in rows.items() if r["fn_summary"] and key(sem.contract(nodes[other])) == key(node)]
        info.update(explicit_constructor=any(r["function_ctx"]["is_constructor"] for r in children),
            payable_fallback=any(r["function_ctx"]["is_fallback"] and r["function_ctx"]["payable"] for r in children),
            selfdestruct=any(r["fn_summary"]["selfdestruct"] for r in children),
            auth_state=bool(auth.get(key(node))), auth_state_count=len(auth.get(key(node), ())),
            status="unknown" if any(r["fn_summary"]["status"] == "unknown" for r in children) else "supported")


class FactBackend:
    def extract(self, file_ctx):
        raise NotImplementedError


class AstBackend(FactBackend):
    def extract(self, file_ctx):
        return extract_source(**file_ctx)[0]


def extract_source(source, file="fixture.sol", graph=None, evidence=None, metadata=None, references=None):
    """Return facts plus audit. Source-only mode deliberately has no DFG/CFG facts."""
    references = references or []
    before = graph_fingerprint(graph) if graph is not None else None
    projection = ProjectionView(source, file)
    sem, rows = AstSemantics(projection), {}
    guards = GuardAnalyzer(sem)
    diagnostics = dict(view="original", projection_missing=0, cfg={}, symbol_exact_lookups=0)
    if graph is None:
        selected = [n for n in sem.nodes if n.type in STATEMENTS | FUNCTIONS | CONTRACTS | {"state_variable_declaration"}]
        nodes = {"ast:" + str(i): n for i, n in enumerate(selected)}
        projector = None
    else:
        projector = Projector(graph, projection)
        nodes = _raw_projection(projection, projector)
        all_semantic = {key(n) for n in sem.nodes if n.type in STATEMENTS | FUNCTIONS | CONTRACTS | {"state_variable_declaration"}}
        diagnostics["projection_missing"] = len(all_semantic - {key(n) for n in nodes.values()})
    rows, offsets = _base_rows(projection, nodes, sem, guards, references)
    if evidence is not None:
        if evidence.get("source_hashes", {}).get(file) != projection.sha256:
            raise ValueError("Source/evidence hash differs")
        for layer in ("L1", "L2", "L3"):
            if evidence["layers"][layer].get("source_hashes", {}).get(file) != projection.sha256:
                raise ValueError("Layer/source hash differs")
        cfg = FileCFG(source, file, metadata)
        _bind_layers(rows, nodes, graph, evidence, file, sem, cfg, offsets, diagnostics)
        for fn in sem.functions:
            owned = {nid: n for nid, n in nodes.items() if key(sem.owner(n)) == key(fn)}
            if fn.child_by_field_name("body") is None:
                continue
            diagnostics["cfg"][str(fn.start_byte)] = apply_order(rows, owned, cfg, fn, projection, projector, offsets)
            # A valid CFG does not make incomplete state-write evidence complete.
            # Name-only read diagnostics (e.g. an unresolved builtin name) do not
            # trigger this write-order guard.
            write_evidence_missing = any(rows[n]["unresolved"].get(reason)
                for n in owned for reason in ("state_alias_unresolved", "state_write_projection_missing"))
            for ast in walk(fn):
                if ast.type in ("assignment_expression", "augmented_assignment_expression"):
                    target = ast.child_by_field_name("left")
                elif ast.type == "update_expression" or operator(ast) == "delete":
                    target = ast.child_by_field_name("argument")
                else:
                    continue
                if sem.root_binding(target)["kind"] == "unknown":
                    write_evidence_missing = True
            if write_evidence_missing:
                for nid in owned:
                    if rows[nid]["order"]:
                        rows[nid]["order"]["status"] = "unknown"
                        rows[nid]["unresolved"]["incomplete_state_write_order"] = 1

        # The relation target describes where the computed value is consumed.
        for row in rows.values():
            if row["arith"].get("ops"):
                conversion = {"state_write":"state", "call_value":"value"}
                row["arith"]["sinks"] = sorted(set(row["arith"]["sinks"]) |
                    {conversion.get(x["sink"], x["sink"]) for x in row["dfg"]["to"]
                     if x["sink"] in ("guard", "state_write", "call_value", "call_arg", "call_target", "return")})
    if graph is not None:
        mapped = {key(n) for n in nodes.values()}
        missing_by_function = Counter()
        missing_effects = set()
        for ast in sem.nodes:
            if ast.type not in STATEMENTS or key(ast) in mapped:
                continue
            fn = sem.owner(ast)
            if fn is None:
                continue
            missing_by_function[key(fn)] += 1
            uncertain_effect = bool(sem.calls(ast)) or ast.type == "assembly_statement"
            for expression in sem.owned_nodes(ast):
                target = None
                if expression.type in ("assignment_expression", "augmented_assignment_expression"):
                    target = expression.child_by_field_name("left")
                elif expression.type == "update_expression" or operator(expression) == "delete":
                    target = expression.child_by_field_name("argument")
                else:
                    continue
                if sem.root_binding(target)["kind"] in ("state", "unknown"):
                    uncertain_effect = True
            if uncertain_effect:
                missing_effects.add(key(fn))
        for nid, ast in nodes.items():
            fn_key = key(sem.owner(ast))
            if missing_by_function[fn_key]:
                rows[nid]["unresolved"]["projection_missing"] = missing_by_function[fn_key]
            if rows[nid]["order"] and fn_key in missing_effects:
                rows[nid]["order"]["status"] = "unknown"
                rows[nid]["unresolved"]["unprojected_effect_order"] = 1
    _summaries(rows, nodes, sem, guards, graph)
    if graph is not None:
        for nid, attrs in graph.nodes(data=True):
            if attrs["node_type"] in ("end_if", "end_loop"):
                rows[nid] = new_facts("end")
                rows[nid]["provenance"] = dict(source_sha256=projection.sha256, store_refs=references, view="original")
        if graph_fingerprint(graph) != before:
            raise AssertionError("Facts producer mutated the fixed graph")
    diagnostics["modifiers"] = dict(guards.audit)
    diagnostics["auth_variables_by_contract"] = [len(guards.auth_declarations(c)) for c in sem.contracts]
    diagnostics["rows"] = {nid: dict(text=sem.text(node), node_kind=rows[nid]["node_kind"],
                                    function=sem.text(sem.owner(node).child_by_field_name("name")) if sem.owner(node) is not None else "")
                           for nid, node in nodes.items()}
    for fact in rows.values():
        validate(fact)
    return rows, diagnostics


def extract(task_id, view="original", context=None, graph=None, return_audit=False):
    if view != "original":
        raise ValueError("Current experiment policy permits only original spelling")
    context = load_context(task_id) if context is None else context
    if context["task_id"] != task_id:
        raise ValueError("Task identity mismatch")
    graph = context["graphs"]["F3"] if graph is None else graph
    before = graph_fingerprint(graph)
    originals = [n for n, a in graph.nodes(data=True) if a["node_type"] != "env_source"]
    if originals != context["order"]:
        raise ValueError("Original node order/population differs")
    grouped = defaultdict(list)
    for nid in originals:
        grouped[graph.nodes[nid]["source_file"]].append(nid)
    if set(grouped) != set(context["sources"]):
        raise ValueError("Source population mismatch")
    records, audits = {}, {}
    reference = context.get("provenance", {}).get("audit")
    refs = [reference] if reference else []
    for file in sorted(grouped):
        subgraph = graph.subgraph(grouped[file]).copy()
        # Include ENV edges only after the auxiliary source is outside Projector.
        evidence_graph = subgraph
        rows, audit = extract_source(context["source_text"][file], file, evidence_graph,
            context["audit"], context["sources"][file].get("metadata"), refs)
        records.update(rows)
        audit.pop("rows", None)
        audits[file] = audit
    ordered = {n: records[n] for n in context["order"]}
    for nid, attrs in sorted(((n,a) for n,a in graph.nodes(data=True) if a["node_type"] == "env_source"),
                             key=lambda x:(x[1]["source_file"], x[1]["code"])):
        fact = new_facts("env")
        fact["env"]["keys"] = [attrs["code"]]
        fact["provenance"] = dict(source_sha256=context["sources"][attrs["source_file"]]["sha256"], store_refs=refs, view="original")
        validate(fact)
        ordered[row_key(nid, attrs)] = fact
    # Check ENV evidence from full graph, then join the exact original endpoint.
    for src, dst, attrs in graph.edges(data=True):
        if attrs.get("edge_type") == "ENV_FLOW":
            for ev in check_layer_edge(src, dst, attrs, context["audit"]):
                if ordered[dst]["env"]:
                    ordered[dst]["env"]["keys"] = sorted(set(ordered[dst]["env"]["keys"]) | {ev["env_key"]})
    if len(ordered) != len(graph) or graph_fingerprint(graph) != before:
        raise AssertionError("Population changed or graph mutated")
    for fact in ordered.values():
        validate(fact)
    return (ordered, audits) if return_audit else ordered


def _positive(value):
    if isinstance(value, str):
        return value not in ("none", "not_applicable", "default", "unknown", "zero")
    return bool(value)


def statistics(records):
    stats = {"rows":len(records), "node_kinds":dict(Counter(r["node_kind"] for r in records.values())),
             "guard_rules":dict(Counter(g["rule"] for r in records.values() for g in r["guards"])),
             "unresolved":dict(sum((Counter(r["unresolved"]) for r in records.values()),Counter())),
             "uninvoked_call_value":sum(r["external"].get("uninvoked_call_value",False) for r in records.values()),
             "unknown":{}, "nonempty":{}, "positive":{}, "field_applicable":{}}
    for group in ("dfg", "order", "state", "checked_call"):
        applicable = [r[group] for r in records.values() if r[group]]
        stats["unknown"][group] = dict(count=sum(x["status"]=="unknown" for x in applicable), applicable=len(applicable))
    stats["unknown"]["guards"] = dict(count=sum(r["guard_status"]=="unknown" for r in records.values()), applicable=len(records))
    for group in next(iter(records.values()), {}):
        if group in ("provenance","names","unresolved","node_kind"):
            continue
        samples=[r[group] for r in records.values()]
        if samples and isinstance(samples[0],dict):
            for field in sorted({k for x in samples for k in x}):
                name = group+"."+field
                stats["nonempty"][name]=sum(bool(x.get(field)) for x in samples)
                stats["positive"][name]=sum(_positive(x.get(field)) for x in samples)
                stats["field_applicable"][name]=sum(field in x for x in samples)
        else:
            stats["nonempty"][group]=sum(bool(x) for x in samples)
            stats["positive"][group]=sum(_positive(x) for x in samples)
            stats["field_applicable"][group]=len(samples)
    return stats


def implementation_refs():
    paths = list(Path(__file__).parent.glob("facts*.py"))
    paths += [ROOT / p for p in ("scripts/DFG/frontend.py", "scripts/DFG/projection.py",
        "scripts/DFG/symbol_table.py", "scripts/DFG/semantic_cfg.py", "scripts/DFG/dfg_v2/projection_view.py",
        "scripts/DFG/dfg_v2/l1_cfg.py", "scripts/DFG/dfg_v2/l1_symbols.py", "scripts/DFG/dfg_v2/env.py",
        "scripts/DFG/state/stage_j/binding.py", "scripts/DFG/state/stage_k/profile.py")]
    return {str(p.relative_to(ROOT)):ref(p) for p in sorted(paths)}


def write_task(task_id, output, context=None):
    context = load_context(task_id) if context is None else context
    dest = Path(output) / "original" / task_id
    dest.mkdir(parents=True, exist_ok=False)
    rows, audits = extract(task_id, context=context, return_audit=True)
    with (dest/"facts.jsonl").open("x",encoding="utf8") as stream:
        for nid, fact in rows.items():
            stream.write(json.dumps(dict(row_key=nid,facts=fact),sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n")
    write(dest/"audit.json", audits)
    manifest = dict(version=VERSION, task_id=task_id, view="original", rows=len(rows),
        profiles=context["profiles"], sources=context["sources"], provenance=context["provenance"],
        implementation=implementation_refs(), facts=ref(dest/"facts.jsonl"), audit=ref(dest/"audit.json"),
        stats=statistics(rows), training_executed=False, gpu_used=False,
        policy="original spelling only; historical anonymous results not a paired baseline")
    write(dest/"manifest.json",manifest)
    write(dest/"manifest.seal.json",dict(manifest=ref(dest/"manifest.json")))
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    result=write_task(args.task,args.out)
    print(json.dumps(dict(task=args.task,rows=result["rows"],stats=result["stats"]),indent=2))


if __name__ == "__main__":
    main()
