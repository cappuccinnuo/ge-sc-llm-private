"""Label-independent, degree-preserving DDG rewiring on a new in-memory graph."""
import random
from collections import Counter, defaultdict

import dgl
import torch

DDG = "DATA_DEF_USE"


def rewire_ddg(graph, node_files_by_type, function_by_type, seed=101,
               attempts_per_edge=40):
    """Return (copied_graph, audit), never mutate the input.

    Both metadata maps use exact DGL type-row order. A function identity must be
    independently confirmed from source/provenance; None means unknown and its
    edges are retained. No labels, predictions, or validation masks are read.
    All EIDs stay in place; directed double swaps only exchange destinations.
    """
    rng = random.Random(int(seed))
    for ntype in graph.ntypes:
        size = graph.num_nodes(ntype)
        if len(node_files_by_type.get(ntype, [])) != size:
            raise ValueError("Missing or misaligned file map: " + ntype)
        if len(function_by_type.get(ntype, [])) != size:
            raise ValueError("Missing or misaligned function map: " + ntype)
    data = {}
    audits = []
    total_ddg = 0
    unknown_edges = 0
    for canonical in graph.canonical_etypes:
        src_t, _, dst_t = canonical
        src_tensor, dst_tensor = graph.edges(etype=canonical, order="eid")
        sources = src_tensor.detach().cpu().tolist()
        targets = dst_tensor.detach().cpu().tolist()
        original_pairs = list(zip(sources, targets))
        if canonical[1] == DDG:
            total_ddg += len(sources)
            if len(set(original_pairs)) != len(original_pairs):
                raise ValueError("Existing DDG duplicate pairs need explicit audit")
            existing = set(original_pairs)
            groups = defaultdict(list)
            for eid, (source, target) in enumerate(original_pairs):
                fs = node_files_by_type[src_t][source]
                ft = node_files_by_type[dst_t][target]
                us = function_by_type[src_t][source]
                ut = function_by_type[dst_t][target]
                if fs is None or ft is None or us is None or ut is None:
                    unknown_edges += 1
                    groups[(str(fs), "__unknown_function_or_file__")].append(eid)
                elif fs != ft or us != ut:
                    unknown_edges += 1
                    groups[(str(fs), "__unconfirmed_same_function__")].append(eid)
                else:
                    groups[(str(fs), str(us))].append(eid)
            for (file, function), eids in sorted(groups.items()):
                before = [(sources[i], targets[i]) for i in eids]
                trials = successes = 0
                unique_s = len({sources[i] for i in eids})
                unique_d = len({targets[i] for i in eids})
                if function.startswith("__"):
                    reason = function
                elif len(eids) < 2:
                    reason = "fewer_than_two_edges"
                elif unique_s < 2:
                    reason = "single_unique_source"
                elif unique_d < 2:
                    reason = "single_unique_destination"
                else:
                    reason = "budget_exhausted_without_valid_swap"
                    for _ in range(max(1, int(attempts_per_edge)) * len(eids)):
                        trials += 1
                        i, j = rng.sample(eids, 2)
                        a, b = sources[i], targets[i]
                        c, d = sources[j], targets[j]
                        if a == c or b == d:
                            continue
                        if src_t == dst_t and (a == d or c == b):
                            continue
                        if (a, d) in existing or (c, b) in existing:
                            continue
                        existing.remove((a, b))
                        existing.remove((c, d))
                        existing.add((a, d))
                        existing.add((c, b))
                        targets[i], targets[j] = d, b
                        successes += 1
                    if successes:
                        reason = "swaps_executed"
                after = [(sources[i], targets[i]) for i in eids]
                changed = sum(x != y for x, y in zip(before, after))
                removed = len(set(before) - set(after))
                audits.append(dict(canonical=list(canonical), file=file, function=function,
                                   edge_count=len(eids), unique_sources=unique_s,
                                   unique_destinations=unique_d, attempts=trials,
                                   accepted_swaps=successes, changed_eid_endpoints=changed,
                                   replaced_semantic_edges=removed,
                                   semantic_perturbation_fraction=removed / len(eids),
                                   reason=reason,
                                   effective_semantic_perturbation=bool(removed)))
            # Invariants use native typed node IDs and relation-local degrees.
            if Counter(sources) != Counter(x for x, _ in original_pairs):
                raise AssertionError("Source degree changed")
            if Counter(targets) != Counter(y for _, y in original_pairs):
                raise AssertionError("Destination degree changed")
            if len(set(zip(sources, targets))) != len(sources):
                raise AssertionError("A duplicate DDG edge was created")
            original_self = {(a, b) for a, b in original_pairs if src_t == dst_t and a == b}
            new_self = {(a, b) for a, b in zip(sources, targets) if src_t == dst_t and a == b}
            if not new_self.issubset(original_self):
                raise AssertionError("A new DDG self-loop was created")
        data[canonical] = (torch.tensor(sources, dtype=graph.idtype, device=graph.device),
                           torch.tensor(targets, dtype=graph.idtype, device=graph.device))
    copied = dgl.heterograph(data, num_nodes_dict={t: graph.num_nodes(t) for t in graph.ntypes},
                            idtype=graph.idtype, device=graph.device)
    if copied.ntypes != graph.ntypes or copied.canonical_etypes != graph.canonical_etypes:
        raise AssertionError("Rewiring changed registered schema order")
    for ntype in graph.ntypes:
        for key, value in graph.nodes[ntype].data.items():
            copied.nodes[ntype].data[key] = value.detach().clone()
    for canonical in graph.canonical_etypes:
        for key, value in graph.edges[canonical].data.items():
            copied.edges[canonical].data[key] = value.detach().clone()
    changed = sum(row["changed_eid_endpoints"] for row in audits)
    removed = sum(row["replaced_semantic_edges"] for row in audits)
    audit = dict(seed=int(seed), algorithm="directed-double-swap-v1",
                 attempts_per_edge=int(attempts_per_edge), ddg_edges=total_ddg,
                 unknown_or_mismatched_function_edges=unknown_edges,
                 changed_eid_endpoints=changed, replaced_semantic_edges=removed,
                 semantic_perturbation_fraction=removed / total_ddg if total_ddg else 0.0,
                 groups=len(audits),
                 groups_with_semantic_perturbation=sum(r["effective_semantic_perturbation"]
                                                       for r in audits),
                 unchanged_groups=sum(not r["effective_semantic_perturbation"]
                                      for r in audits),
                 labels_read=False, graph_persisted=False, group_details=audits)
    return copied, audit
