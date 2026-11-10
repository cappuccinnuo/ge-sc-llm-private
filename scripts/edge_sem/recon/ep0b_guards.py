"""Whole-corpus modifier provenance equivalence and projection counts only."""
import argparse
from collections import Counter, defaultdict
from .common import key, histogram, write, ref
from .ep0b_common import OUT, contexts, file_views, anchor
from scripts.edge_sem.guard_source import inspect_modifier_guards, public_record
from scripts.node_sem.facts_guards import GuardAnalyzer
from scripts.node_sem.facts import kind_of
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint


def inspect(task):
    ctx = contexts(task)
    graph = ctx["graphs"]["F3"]
    fingerprint = graph_fingerprint(graph)
    files = []
    total = Counter()
    all_modifier, all_nonmodifier = set(), set()
    incoming_counts = []
    for index, (file, source, sub, sem, raw, inverse) in enumerate(file_views(ctx)):
        analyzer = GuardAnalyzer(sem)
        functions = []
        per_function = {}
        modifier_stats = defaultdict(Counter)
        for fn in sem.functions:
            records, unresolved, audit = inspect_modifier_guards(analyzer, fn)
            before = dict(analyzer.audit)
            expected, expected_unresolved = analyzer._modifiers(fn)
            actual_audit = Counter(analyzer.audit)
            actual_audit.subtract(before)
            actual_audit = +actual_audit
            assert [x["record"] for x in records] == [public_record(x) for x in expected], (file, anchor(fn))
            assert unresolved == expected_unresolved, (file, anchor(fn), "unresolved")
            assert audit == actual_audit, (file, anchor(fn), "audit")
            per_function[key(fn)] = records
            entries = []
            for row in records:
                inner = row["inner_anchor"]
                owner = sem.owner(inner)
                group = str(anchor(owner))
                mapped = inverse.get(key(inner))
                modifier_stats[group]["records_per_applied_function"] += 1
                modifier_stats[group]["mapped" if mapped is not None else "unmapped"] += 1
                entries.append(dict(record=row["record"], invocation=anchor(row["invocation"]),
                                    inner_anchor=anchor(inner), modifier=anchor(owner),
                                    graph_node=mapped,
                                    mapping_reason="exact_ast_identity" if mapped is not None else "anchor_has_no_exact_hcg_node"))
            functions.append(dict(function=anchor(fn), graph_node=inverse.get(key(fn)),
                                  sequence_equal=True, unresolved=dict(unresolved),
                                  audit=dict(audit), records=entries))
            total["functions_checked"] += 1
            total["body_functions_checked"] += int(fn.child_by_field_name("body") is not None)
            total["modifier_records_per_function"] += len(records)
            total.update(audit)
        local_mod, local_nonmod = set(), set()
        expanded = Counter()
        missing = []
        statements = []
        for nid, node in raw.items():
            if kind_of(node, sem) not in ("statement", "condition"):
                continue
            guards = analyzer.for_node(node)["guards"]
            expected = [g for g in guards if g["kind"] == "modifier"]
            owner = sem.owner(node)
            sources = per_function.get(key(owner), [])
            assert [public_record(g) for g in expected] == [r["record"] for r in sources]
            mod_index = 0
            for guard in guards:
                if guard["kind"] == "modifier":
                    row = sources[mod_index]
                    mod_index += 1
                    src = inverse.get(key(row["inner_anchor"]))
                    expanded["modifier_records"] += 1
                    expanded["modifier_mapped" if src is not None else "modifier_unmapped"] += 1
                    if src is None:
                        missing.append(dict(target=nid, function=anchor(owner),
                                            invocation=anchor(row["invocation"]),
                                            inner_anchor=anchor(row["inner_anchor"]),
                                            reason="anchor_has_no_exact_hcg_node"))
                    elif src != nid:
                        local_mod.add((src, nid))
                    else:
                        expanded["self_skipped"] += 1
                else:
                    src = inverse.get(key(guard["_anchor"]))
                    if src is not None and src != nid:
                        local_nonmod.add((src, nid))
            statements.append(nid)
        combined = local_mod | local_nonmod
        incoming = Counter(t for _, t in combined)
        incoming_counts.extend(incoming[n] for n in statements)
        all_modifier.update(local_mod)
        all_nonmodifier.update(local_nonmod)
        total.update(expanded)
        files.append(dict(file=file, source=ctx["sources"][file], functions=functions,
            per_modifier={k:dict(v) for k,v in modifier_stats.items()},
            expanded_counts=dict(expanded), unmapped=missing,
            statement_count=len(statements), unique_modifier=len(local_mod),
            unique_nonmodifier=len(local_nonmod), unique_combined=len(combined),
            incoming_distribution=histogram(incoming[n] for n in statements),
            prospective_pairs=[dict(source=s, target=t, modifier=(s,t) in local_mod,
                                    nonmodifier=(s,t) in local_nonmod)
                               for s,t in sorted(combined, key=str)]))
        if index % 15 == 0:
            print(task, index+1, "/", len(ctx["sources"]), flush=True)
    combined = all_modifier | all_nonmodifier
    assert graph_fingerprint(graph) == fingerprint
    result = dict(task_id=task, provenance=ctx["provenance"], all_sequences_equal=True,
        counts=dict(total), files=files, unique_modifier=len(all_modifier),
        unique_nonmodifier=len(all_nonmodifier), unique_combined=len(combined),
        with_reverse=2*len(combined), incoming_distribution=histogram(incoming_counts),
        input_graph_unchanged=True, graphs_written=0, production_edges_written=0)
    write(OUT/("guards_"+task+".json"), result)
    print(task, dict(total), "combined", len(combined), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    inspect(parser.parse_args().task)
