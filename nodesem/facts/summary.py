"""Function and contract summaries (writes, calls, guards, loops, ...) with field masks."""
from collections import defaultdict

from nodesem.facts.schema import new_facts
from nodesem.facts.syntax import LOOPS, key, walk


# ----------------------------------------------------------------------
# node_sem/facts_summary
# K/L/M summaries from full AST plus sealed L2 accesses, with field masks.
STATEMENTS = frozenset(("expression_statement","variable_declaration_statement","return_statement",
    "continue_statement","break_statement","emit_statement","revert_statement","throw_statement",
    "if_statement","for_statement","while_statement","do_while_statement","assembly_statement"))

EXISTENTIAL = frozenset(("read_in_guard", "used_as_call_value_or_target",
    "unguarded_writer", "state_write", "auth_write", "sender_guard",
    "write_then_call", "call_then_write", "auth_state"))

def mark(info, unknown):
    # Exists(true, unknown) is true. Saturated cardinalities cannot increase.
    unknown = set(unknown)
    unknown.difference_update(k for k in EXISTENTIAL if info.get(k) is True)
    unknown.difference_update(k for k in ("read_functions", "write_functions")
                              if info.get(k) == "many")
    info["unknown_fields"] = sorted(unknown)
    info["status"] = "unknown" if unknown else "supported"

def count(n):
    return "zero" if n == 0 else "one" if n == 1 else "many"

def summarize(rows, nodes, sem, guards, support, kind_of):
    precision = {}
    auth = {key(c): guards.auth_declarations(c) for c in sem.contracts}
    declaration_auth = set().union(*auth.values()) if auth else set()
    declaration_scopes = defaultdict(set)
    for c in sem.contracts:
        for declarations in sem.members(c).values():
            for d in declarations: declaration_scopes[key(d)].add(key(c))
    for nid,node in nodes.items():
        for mode in ("reads","writes"):
            for item in rows[nid]["state"].get(mode,[]):
                ds = sem.members(node).get(item["var"],[])
                if len(ds)==1: item["auth"] = key(ds[0]) in auth.get(key(sem.contract(node)),set())

    full, fn_summaries, fn_precision = {}, {}, {}
    for fn in sem.functions:
        children = [n for n in walk(fn) if n.type in STATEMENTS]
        records = []
        for n in children:
            k = kind_of(n,sem)
            r = sem.base_facts(n,k)
            g = guards.for_node(n)
            full[key(n)] = (r,g)
            records.append((n,r,g))
        events = [e for e in support.events if key(e["function"]) == key(fn)]
        writers = [e for e in events if e["writing"]]
        projected = [r for nid,r in rows.items() if r["state"] and key(sem.owner(nodes[nid]))==key(fn)]
        own_auth = auth.get(key(sem.contract(fn)),set())
        info = new_facts("function")["fn_summary"]
        # Full AST, including absent HCG emit/revert/condition nodes.
        self_sender = False
        for n,r,g in records:
            condition = guards._require(n)
            polarity = 1
            if condition is None:
                condition = guards._early(n)
                polarity = -1
            if condition is not None:
                self_sender |= guards._equalities(condition,polarity,{})[2]
        info.update(external_call=any(r["external"].get("kinds") for _,r,_ in records),
            state_write=bool(writers),
            sender_guard=self_sender or any(gd["is_sender_guard"] for _,_,g in records for gd in g["guards"]),
            auth_write=any(key(e["declaration"]) in own_auth for e in writers),
            selfdestruct=any("selfdestruct" in r["external"].get("kinds",[]) for _,r,_ in records),
            delegatecall=any("delegatecall" in r["external"].get("kinds",[]) for _,r,_ in records),
            loop=any(n.type in LOOPS for n in walk(fn)),
            ext_call_in_loop=any(r["external"].get("kinds") and r["loop"].get("bound")!="none" for _,r,_ in records),
            timestamp=any("block.timestamp" in r["env"].get("keys",[]) for _,r,_ in records),
            tx_origin=any("tx.origin" in r["env"].get("keys",[]) for _,r,_ in records),
            write_then_call=any(r["order"]["write_then_call"] for r in projected),
            call_then_write=any(r["order"]["call_then_write"] for r in projected))
        unknown = set()
        potential_write = bool(writers or support.function_issues(fn,True))
        if not support.available:
            potential_write |= any(n.type in ("assignment_expression","augmented_assignment_expression","update_expression")
                                   and sem.root_binding(n.child_by_field_name("left") or n.child_by_field_name("argument"))["kind"] in ("state","unknown")
                                   for n in walk(fn))
        if support.function_issues(fn,True) or (potential_write and not support.available):
            unknown.update(("state_write","auth_write"))
        if any(g["guard_status"]=="unknown" for _,_,g in records):
            unknown.add("sender_guard")
        # With no possible call/write pair the ordering bits are known false;
        # missing a harmless emit cannot invalidate the remaining summary.
        if potential_write and info["external_call"]:
            if not projected or any(r["order"]["status"]=="unknown" for r in projected):
                unknown.update(("write_then_call","call_then_write"))
        before_mask = set(unknown)
        mark(info,unknown)
        fn_precision[key(fn)] = sorted(before_mask - set(info["unknown_fields"]))
        fn_summaries[key(fn)] = info

    for nid,node in nodes.items():
        record = rows[nid]
        if record["fn_summary"]:
            record["fn_summary"] = dict(fn_summaries[key(node)])
            if fn_precision[key(node)]:
                precision[nid] = dict(group="fn_summary", three_value=fn_precision[key(node)], target_scope=[])
        if not record["state_decl"]: continue
        decl = node.parent if node.type=="variable_declaration" else node
        info = record["state_decl"]
        info["auth"] = key(decl) in declaration_auth
        events = [e for e in support.events if key(e["declaration"])==key(decl) and e["function"] is not None]
        readers,writers,unguarded = set(),set(),set()
        unknown = set()
        for e in events:
            fn,stmt = e["function"],e["statement"]
            (writers if e["writing"] else readers).add(key(fn))
            g = guards.for_node(stmt)
            if e["writing"]:
                if g["guard_status"]=="unknown":
                    unknown.update(("unguarded_writer","unguarded_write_functions"))
                elif not any(x["is_sender_guard"] for x in g["guards"]):
                    unguarded.add(key(fn))
            else:
                if kind_of(stmt,sem)=="condition": info["read_in_guard"]=True
                for call in sem.calls(stmt):
                    if not call["invoked"]: continue
                    for expression in (call["target"],call["value"]):
                        if expression is not None and any(key(sem.resolve_identifier(x).get("declaration"))==key(decl) for x in sem.identifiers(expression)):
                            info["used_as_call_value_or_target"]=True
        info.update(read_functions=count(len(readers)),write_functions=count(len(writers)),
                    unguarded_writer=bool(unguarded),unguarded_write_functions=len(unguarded))
        functions = {key(fn):fn for fn in sem.functions}
        info["only_constructor_writes"] = bool(writers) and all(sem.function_context(functions[k])["is_constructor"] for k in writers)
        write_fields = {"write_functions","only_constructor_writes","unguarded_writer","unguarded_write_functions"}
        if not support.available:
            unknown.update(write_fields|{"read_functions","read_in_guard","used_as_call_value_or_target"})
        scopes = declaration_scopes[key(decl)] | {key(sem.contract(decl))}
        broad_unknown = set(unknown)
        for issue in support.issues:
            # Diagnostic counterfactual only: old broad scope, same current
            # certain events/guards. This does not affect exported facts.
            old_applies = key(sem.contract(issue["node"])) in scopes
            if issue["reason"] == "unprojected_state_effect":
                old_applies = old_applies and key(decl) in issue["targets"]
            if old_applies:
                if issue["writing"]: broad_unknown.update(write_fields)
                elif issue["reason"] != "unprojected_state_effect":
                    broad_unknown.update(("read_functions", "read_in_guard", "used_as_call_value_or_target"))
            if issue["targets"] is not None:
                if key(decl) not in issue["targets"]: continue
            elif key(sem.contract(issue["node"])) not in scopes:
                continue
            if issue["writing"]: unknown.update(write_fields)
            elif issue["reason"] != "unprojected_state_effect":
                unknown.update(("read_functions","read_in_guard","used_as_call_value_or_target"))
        before_mask = set(unknown)
        if any(not sem.function_context(functions[k])["is_constructor"] for k in writers):
            unknown.discard("only_constructor_writes")
            broad_unknown.discard("only_constructor_writes")
        broad_info = dict(info)
        mark(broad_info, broad_unknown)
        mark(info,unknown)
        three_value = sorted(before_mask - set(info["unknown_fields"]))
        target_scope = sorted(set(broad_info["unknown_fields"]) - set(info["unknown_fields"]))
        if three_value or target_scope:
            precision[nid] = dict(group="state_decl", three_value=three_value, target_scope=target_scope)

    for nid,node in nodes.items():
        info = rows[nid]["contract_summary"]
        if not info: continue
        functions = [fn for fn in sem.functions if key(sem.contract(fn))==key(node)]
        infos = [fn_summaries[key(fn)] for fn in functions]
        contexts = [sem.function_context(fn) for fn in functions]
        info.update(explicit_constructor=any(r["is_constructor"] for r in contexts),
            payable_fallback=any(r["is_fallback"] and r["payable"] for r in contexts),
            selfdestruct=any(r["selfdestruct"] for r in infos),
            auth_state=bool(auth.get(key(node))),auth_state_count=len(auth.get(key(node),())))
        unknown=set()
        if any("sender_guard" in r["unknown_fields"] for r in infos):
            unknown.update(("auth_state","auth_state_count"))
        before_mask = set(unknown)
        mark(info,unknown)
        removed = sorted(before_mask - set(info["unknown_fields"]))
        if removed:
            precision[nid] = dict(group="contract_summary", three_value=removed, target_scope=[])
    return precision
