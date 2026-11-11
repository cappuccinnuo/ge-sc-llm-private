"""Read-only EP0c reference census, projected coverage and historical comparison.

The confirmed reference is resolver-conditioned. Coverage measures projection
and membership within that set, not independent semantic recall or precision.
"""
import argparse
from collections import Counter, defaultdict
from .common import key, ref, read, write
from .ep0c_common import OUT, EP0B, TASKS, contexts, file_views, anchor
from .ep0b_calls import call_name, site_census
from scripts.node_sem.facts import STATEMENTS
from scripts.node_sem.facts_ast import FUNCTIONS
from scripts.edge_sem.call_resolve import resolve_call
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint

EXCLUDED = frozenset(("address_builtin", "external_member", "cast_member", "new_contract", "builtin"))
ROUGH = {"reentrancy_node": dict(no_expression=76, address_builtin=99, external=33, total=208),
         "access_control_node": dict(no_expression=76, address_builtin=219, external=34, total=329)}


def classify_reference(target_anchor, candidates, endpoint_supported=True):
    if not endpoint_supported:
        return "undetermined", "function_endpoint_not_projected_in_same_file"
    if any(c["target_anchor"] == target_anchor and c["status"] == "resolved" for c in candidates):
        return "internal_confirmed", "exact_ast_target"
    if not candidates:
        return "no_expression", "no_matching_call_expression"
    if all(c["status"] in EXCLUDED for c in candidates):
        return "not_internal", "all_candidates_are_excluded_call_kinds"
    if any(c["target_anchor"] is not None for c in candidates):
        return "rebinding", "resolved_target_differs_from_hcg_target"
    return "undetermined", "unresolved_candidate_retained"


def serial(sem, call, inverse, resolved):
    target = resolved["target"]
    receiver = dict(call_anchor=anchor(call), status=resolved["status"],
        kind=resolved["kind"], reason=resolved["reason"], target_anchor=anchor(target),
        target_node=inverse.get(key(target)), source_line=call.start_point[0]+1,
        expression=sem.text(call))
    if target is not None:
        receiver["target_visibility"] = [sem.text(n) for n in target.named_children if n.type == "visibility"]
    return receiver


def census_sites(sem, inverse, resolved):
    seen, sites = set(), []
    for statement in sem.nodes:
        if statement.type not in STATEMENTS:
            continue
        for call in sem.owned_nodes(statement):
            if call.type != "call_expression" or key(call) in seen:
                continue
            seen.add(key(call))
            row = serial(sem, call, inverse, resolved[key(call)])
            source_id, owner_id = inverse.get(key(statement)), inverse.get(key(sem.owner(statement)))
            target_id = row["target_node"]
            row.update(statement_anchor=anchor(statement), source_node=source_id,
                owner_node=owner_id, projected=(row["status"] == "resolved"
                    and source_id is not None and target_id is not None and source_id != target_id))
            sites.append(row)
    return sites


def inspect(task):
    ctx = contexts(task)
    graph = ctx["graphs"]["F3"]
    before = graph_fingerprint(graph)
    old_path = EP0B/("calls_refined_"+task+".json")
    old = read(old_path)
    old_edges = {(r["source_node"],r["target_node"],r["edge_key"]):r
                 for r in old["edges"] if r["relation"] == "internal_call"}
    all_sites, all_edges, all_ep0, files, raw_calls = [], [], [], [], []
    old_identity_equal = True
    for file_index, (file, source, sub, sem, raw, inverse) in enumerate(file_views(ctx)):
        source_ref = ctx["sources"][file]
        all_calls = [n for n in sem.nodes if n.type == "call_expression"]
        resolved = {key(n): resolve_call(sem,n) for n in all_calls}
        owner_calls = defaultdict(list)
        for call in all_calls:
            owner_calls[key(sem.owner(call))].append(call)
        sites = census_sites(sem,inverse,resolved)
        ep0, old_pairs = site_census(sem,raw,inverse)
        expected_old = [r for r in old["ep0_call_sites"] if r["file"] == file]
        actual_old = [dict(file=file,**r) for r in ep0]
        assert expected_old == actual_old, (task,file,"EP0 changed")
        all_ep0.extend(actual_old)
        for row in sites:
            row.update(file=file, source_sha256=source_ref["sha256"])
        all_sites.extend(sites)
        for call in all_calls:
            raw_calls.append(dict(file=file,source_sha256=source_ref["sha256"],
                owner_anchor=anchor(sem.owner(call)), **serial(sem,call,inverse,resolved[key(call)])))
        owner_pairs = defaultdict(list)
        for r in sites:
            if r["projected"]:
                owner_pairs[(r["owner_node"],r["target_node"])].append(r)
        local_edges = []
        for source_id in sub:
            for _, target_id, edge_key, attrs in graph.out_edges(source_id, keys=True, data=True):
                if attrs["edge_type"] != "internal_call":
                    continue
                src, dst = raw.get(source_id), raw.get(target_id)
                target_name = sem.text(dst.child_by_field_name("name")) if dst is not None else ""
                candidates = [serial(sem,c,inverse,resolved[key(c)])
                    for c in owner_calls[key(src)] if target_name and call_name(sem,c) == target_name]
                supported = (src is not None and dst is not None and src.type in FUNCTIONS
                    and dst.type in FUNCTIONS and graph.nodes[target_id]["source_file"] == file)
                category, reason = classify_reference(anchor(dst),candidates,supported)
                previous = old_edges[(source_id,target_id,edge_key)]
                old_anchors = [r["anchor"] for r in previous["expression_candidates"]]
                assert old_anchors == [r["call_anchor"] for r in candidates]
                r5_covered = bool(owner_pairs.get((source_id,target_id)))
                ep0_covered = bool(old_pairs.get((source_id,target_id)))
                assert previous["covered"] == ep0_covered
                row = dict(file=file, source_sha256=source_ref["sha256"], source_node=source_id,
                    target_node=target_id, edge_key=edge_key, source_anchor=anchor(src),
                    target_anchor=anchor(dst), target_file=graph.nodes[target_id]["source_file"],
                    reference_class=category, reason=reason, expression_candidates=candidates,
                    r5_covered=r5_covered, ep0_covered=ep0_covered,
                    ep0b_category=previous["category"],
                    projected_call_anchors=[s["call_anchor"] for s in owner_pairs.get((source_id,target_id),[])],
                    mixed_resolved_and_unknown=any(c["status"]=="resolved" for c in candidates)
                        and any(c["status"] in ("unknown","super","overload_unresolved") for c in candidates))
                all_edges.append(row)
                local_edges.append(row)
        files.append(dict(file=file,source=source_ref,call_expressions=len(all_calls),
                          statement_call_expressions=len(sites),internal_edges=len(local_edges)))
        if file_index % 20 == 0:
            print(task, file_index+1, "/",len(ctx["sources"]),flush=True)

    assert len(all_edges) == len(old_edges)
    counts = Counter(r["reference_class"] for r in all_edges)
    confirmed = [r for r in all_edges if r["reference_class"] == "internal_confirmed"]
    denominator = len(confirmed)
    r5_count = sum(r["r5_covered"] for r in confirmed)
    ep0_count = sum(r["ep0_covered"] for r in confirmed)
    unique = defaultdict(list)
    ep0_unique = {(r["source_node"],r["target_node"]) for r in all_ep0 if r["projected"]}
    for row in all_sites:
        if row["projected"]:
            unique[(row["source_node"],row["target_node"])].append(row)
    assert ep0_unique <= set(unique), "Prior resolved statement edges lost"
    hcg_pairs = {(r["source_node"],r["target_node"]) for r in all_edges}
    projected = [dict(source_node=s,target_node=t,owner_node=rows[0]["owner_node"],
        file=rows[0]["file"],source_sha256=rows[0]["source_sha256"],
        kinds=sorted(set(r["kind"] for r in rows)),
        call_anchors=[r["call_anchor"] for r in rows],
        statement_anchor=rows[0]["statement_anchor"],target_anchor=rows[0]["target_anchor"],
        added_vs_ep0=(s,t) not in ep0_unique,
        absent_from_hcg=(rows[0]["owner_node"],t) not in hcg_pairs)
        for (s,t),rows in sorted(unique.items())]
    rough_actual = Counter()
    rough_details = []
    for row in all_edges:
        category = row["reference_class"]
        if category == "no_expression":
            group = "no_expression"
        elif category == "not_internal":
            statuses = {c["status"] for c in row["expression_candidates"]}
            group = "address_builtin" if statuses == {"address_builtin"} else "external"
        else:
            group = "not_excluded"
        rough_actual[group] += 1
        rough_details.append(dict(file=row["file"],source_sha256=row["source_sha256"],
            source_node=row["source_node"],target_node=row["target_node"],edge_key=row["edge_key"],
            r5_coarse_comparable_group=group,reference_class=category,ep0b_category=row["ep0b_category"],
            expression_statuses=[c["status"] for c in row["expression_candidates"]],
            reason=row["reason"]))
    rough_actual["total"] = sum(rough_actual[x] for x in ("no_expression","address_builtin","external"))
    observed = {k:rough_actual[k] for k in ROUGH[task]}
    r5_coverage = r5_count/denominator if denominator else None
    unknown_ratio = counts["undetermined"]/denominator if denominator else None
    summary = dict(internal_hcg_edges=len(all_edges),reference_classes=dict(counts),
        confirmed_denominator=denominator,r5_covered=r5_count,ep0_covered=ep0_count,
        r5_coverage=r5_coverage,ep0_coverage=ep0_count/denominator if denominator else None,
        undetermined_to_confirmed=unknown_ratio,
        coverage_gate_pass=bool(denominator and r5_coverage>=.8),
        unknown_gate_pass=bool(denominator and unknown_ratio<=.2),
        gate_pass=bool(denominator and r5_coverage>=.8 and unknown_ratio<=.2),
        unique_call_site_edges=len(projected),ep0_unique_edges=len(ep0_unique),
        added_edges=sum(r["added_vs_ep0"] for r in projected),
        absent_from_hcg_edges=sum(r["absent_from_hcg"] for r in projected),
        unique_edges_by_kind=dict(Counter(k for r in projected for k in r["kinds"])),
        call_statuses=dict(Counter(r["status"] for r in raw_calls)),
        call_kinds=dict(Counter(r["kind"] for r in raw_calls if r["kind"])),
        rough_expected=ROUGH[task],rough_observed=observed,
        rough_delta={k:observed[k]-ROUGH[task][k] for k in observed})
    assert graph_fingerprint(graph) == before
    output = dict(task_id=task,provenance=ctx["provenance"],prior_ep0b=ref(old_path),
        summary=summary,files=files,reference_edges=all_edges,call_sites=all_sites,
        raw_calls=raw_calls,projected_call_sites=projected,rough_comparison=rough_details,
        rough_comparison_limitation="r5 publishes counts, not a per-edge coarse label list; rows expose final membership and exact old EP0b evidence, not an invented historical identity set",
        coverage_interpretation="projection coverage conditional on this resolver, not independently annotated semantic recall",
        ep0_sites_unchanged=old_identity_equal,input_graph_unchanged=True,
        graphs_written=0,production_edges_written=0,training_executed=False)
    write(OUT/("calls_"+task+".json"),output)
    print(task,summary,flush=True)


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--task",required=True,choices=TASKS)
    inspect(p.parse_args().task)
