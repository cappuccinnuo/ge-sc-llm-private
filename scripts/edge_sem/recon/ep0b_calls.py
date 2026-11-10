"""Compare frozen statement-call candidates with every HCG function-call edge.

Name comparison is used only to find diagnostic candidates for missing edges,
never to assert a CALL_SITE dependency or alter a graph. Ambiguous candidates
are retained in the denominator; the gate excludes only absent expressions.
"""
import argparse
from collections import Counter, defaultdict
from .common import key, write
from .ep0b_common import OUT, contexts, file_views, anchor
from .calls import classify
from scripts.node_sem.facts import STATEMENTS
from scripts.node_sem.facts_ast import unwrap, walk, FUNCTIONS
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint


def call_name(sem, call):
    callee = sem._postfix(unwrap(call.child_by_field_name("function")))
    if callee is None:
        return ""
    if callee.type == "identifier":
        return sem.text(callee)
    if callee.type == "member_expression":
        return sem.text(callee.child_by_field_name("property"))
    return ""


def modifier_argument(call):
    parent = call.parent
    while parent is not None and parent.type not in FUNCTIONS:
        if parent.type == "modifier_invocation":
            return True
        parent = parent.parent
    return False


def site_census(sem, raw, inverse):
    seen, records, owner_pairs = set(), [], defaultdict(list)
    for statement in sem.nodes:
        if statement.type not in STATEMENTS:
            continue
        for call in sem.owned_nodes(statement):
            if call.type != "call_expression" or key(call) in seen:
                continue
            seen.add(key(call))
            category, target = classify(sem, call)
            s = inverse.get(key(statement))
            t = inverse.get(key(target)) if target is not None else None
            owner = sem.owner(statement)
            f = inverse.get(key(owner)) if owner is not None else None
            projected = category == "resolved_internal" and s is not None and t is not None and s != t
            row = dict(call=anchor(call), statement=anchor(statement), source_node=s,
                       target_node=t, owner_node=f, category=category, projected=projected)
            records.append(row)
            if projected:
                owner_pairs[(f, t)].append(row)
    return records, owner_pairs


def gap_category(sem, source, target, candidates, initialization_candidates):
    if source is None or target is None:
        return "other", "endpoint_has_no_exact_ast_projection"
    if source.type not in FUNCTIONS or target.type not in FUNCTIONS:
        return "other", "non_function_endpoint"
    if source.type == "modifier_definition" or target.type == "modifier_definition":
        return "modifier", "modifier_endpoint_or_application"
    if any(modifier_argument(c) for c in candidates):
        return "modifier_argument", "call_in_modifier_invocation_arguments"
    if initialization_candidates and not candidates:
        return "state_initializer", "name_candidate_in_state_initializer"
    if target.child_by_field_name("name") is None:
        return "other", "target_has_no_callable_name"
    if not candidates:
        return "no_call_expression", "no_matching_call_expression_in_owner_or_initializer"
    kinds = [classify(sem, c)[0] for c in candidates]
    if "library" in kinds:
        return "library_using", "frozen_resolver_binds_library"
    if "unresolved_super" in kinds:
        return "super", "super_member_call"
    if "unresolved_overload" in kinds:
        return "overload", "multiple_function_declarations_in_frozen_scope"
    if any(len(sem.members(c).get(call_name(sem, c), [])) > 1 for c in candidates):
        return "multiple_declarations", "name_has_multiple_visible_declarations"
    if "resolved_internal" in kinds:
        return "other", "exact_binding_is_different_or_statement_endpoint_missing"
    return "other", "expression_present_but_outside_ep0_internal_subset"


def sample(sem, call):
    return dict(anchor=anchor(call), source_line=call.start_point[0]+1,
                source_end_line=call.end_point[0]+1, expression=sem.text(call),
                classification=classify(sem, call)[0])


def inspect(task, tag="calls"):
    ctx = contexts(task)
    graph = ctx["graphs"]["F3"]
    fingerprint = graph_fingerprint(graph)
    files, edge_rows, sites = [], [], []
    totals = {"internal_call": Counter(), "external_call": Counter()}
    reasons = {"internal_call": Counter(), "external_call": Counter()}
    for file_index, (file, source_text, sub, sem, raw, inverse) in enumerate(file_views(ctx)):
        records, owner_pairs = site_census(sem, raw, inverse)
        sites.extend(dict(file=file, **r) for r in records)
        all_calls = [n for n in sem.nodes if n.type == "call_expression"]
        owner_calls = defaultdict(list)
        state_calls = []
        for call in all_calls:
            fn = sem.owner(call)
            if fn is not None:
                owner_calls[key(fn)].append(call)
            else:
                parent = call.parent
                while parent is not None:
                    if parent.type == "state_variable_declaration":
                        state_calls.append(call)
                        break
                    parent = parent.parent
        local = []
        for source_id in sub.nodes():
            for _, target_id, edge_key, attrs in graph.out_edges(source_id, keys=True, data=True):
                relation = attrs["edge_type"]
                if relation not in totals:
                    continue
                source, target = raw.get(source_id), raw.get(target_id)
                coverage = owner_pairs.get((source_id, target_id), [])
                candidates, initializers = [], []
                if source is not None and target is not None:
                    name = sem.text(target.child_by_field_name("name"))
                    if name:
                        candidates = [c for c in owner_calls[key(source)] if call_name(sem,c) == name]
                        same_contract = key(sem.contract(source))
                        initializers = [c for c in state_calls if key(sem.contract(c)) == same_contract
                                        and call_name(sem,c) == name]
                if coverage:
                    category, reason = "covered", "exact_projected_ep0_statement_call"
                else:
                    category, reason = gap_category(sem, source, target, candidates, initializers)
                totals[relation]["edges"] += 1
                totals[relation]["covered"] += int(bool(coverage))
                reasons[relation][category] += 1
                row = dict(file=file, source_sha256=ctx["sources"][file]["sha256"],
                    relation=relation, source_node=source_id, target_node=target_id, edge_key=edge_key,
                    target_file=graph.nodes[target_id]["source_file"],
                    source_kind=graph.nodes[source_id]["node_type"],
                    target_kind=graph.nodes[target_id]["node_type"],
                    source_anchor=anchor(source), target_anchor=anchor(target),
                    source_lines=graph.nodes[source_id].get("node_source_code_lines"),
                    target_lines=graph.nodes[target_id].get("node_source_code_lines"),
                    covered=bool(coverage), category=category, reason=reason,
                    call_sites=coverage, expression_candidates=[sample(sem,c) for c in candidates],
                    initializer_candidates=[sample(sem,c) for c in initializers])
                edge_rows.append(row)
                local.append(row)
        files.append(dict(file=file, source=ctx["sources"][file], site_count=len(records),
                          function_edges=len(local)))
        if file_index % 20 == 0:
            print(task, file_index+1, "/", len(ctx["sources"]), flush=True)
    for relation in totals:
        assert totals[relation]["edges"] == sum(a["edge_type"] == relation for _,_,a in graph.edges(data=True))
        count = totals[relation]["edges"]
        covered = totals[relation]["covered"]
        excluded = reasons[relation]["no_call_expression"]
        denominator = count-excluded
        totals[relation].update(no_expression_excluded=excluded, adjusted_denominator=denominator)
    summary = {}
    for relation in totals:
        d = dict(totals[relation])
        d["categories"] = dict(reasons[relation])
        d["coverage"] = d["covered"]/d["edges"] if d["edges"] else None
        d["adjusted_coverage"] = d["covered"]/d["adjusted_denominator"] if d["adjusted_denominator"] else None
        d["gate_80_percent_pass"] = (d["adjusted_coverage"] is not None and d["adjusted_coverage"] >= .8)
        summary[relation] = d
    assert graph_fingerprint(graph) == fingerprint
    result = dict(task_id=task, provenance=ctx["provenance"], files=files, edges=edge_rows,
                  ep0_call_sites=sites, summary=summary, input_graph_unchanged=True,
                  production_edges_written=0, graphs_written=0,
                  gate_applies_to="internal_call only; external_call is separately descriptive")
    write(OUT/(tag+"_"+task+".json"), result)
    print(task, summary, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, choices=["reentrancy_node","access_control_node"])
    parser.add_argument("--tag",default="calls")
    args=parser.parse_args()
    inspect(args.task,args.tag)
