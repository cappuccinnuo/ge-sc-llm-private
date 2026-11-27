"""CP7 K3 benchmark and leave-one-project check (PROMPTS 3.4, 4.7).

Usage: python -B k3_benchmark.py <docs root> <out.json> <targets.json> <run dir> [<targets.json> <run dir> ...]
The docs root gives the documented-term vocabulary of the templates (the same as K1).
Each run dir holds real_check.py results (<unit>/units/<unit>/{environment_result,result}.json).
The memory is every successful repair with changes; a unit appearing in several runs keeps
its last run. The group of a unit is its project root (a file for a stand-alone snippet).

For every memory entry, the query is what an agent sees before repairing: the templates of
the original errors, their categories, the version and the project group. A hit is correct
when it comes from another project and repaired with the same set of steps. Leave one
project out is checked twice: retrieval never returns an entry of the query's own group,
and with K3 restricted to that group alone nothing is returned.
"""
import json
import sys
from pathlib import Path

from compile_repair.evaluation.report import hit_rates
from compile_repair.rag.knowledge import (KnowledgeBase, documentation_entries, documented_terms, removed_errors,
    repair_entries)
from compile_repair.rag.retrieve import Query, retrieve

KS = (1, 2, 3, 5, 8, 10)
vocabulary = documented_terms(documentation_entries(sys.argv[1]))
out, pairs = Path(sys.argv[2]), sys.argv[3:]
records, groups = {}, {}
for targets, run in zip(pairs[::2], pairs[1::2]):
    for target in json.loads(Path(targets).read_text(encoding="utf8")):
        unit = Path(run) / target["unit_id"] / "units" / target["unit_id"]
        # A unit without environment_result.json needed no repair step (no memory entry).
        if (unit / "environment_result.json").exists():
            group = target.get("project_root") or target["path"]
            groups[target["unit_id"]] = group
            records[target["unit_id"]] = (group, json.loads((unit / "environment_result.json").read_text()),
                                          json.loads((unit / "result.json").read_text()))
entries = repair_entries(records.values(), vocabulary)
kb = KnowledgeBase(entries, vocabulary)
by_id = {e.entry_id: e for e in entries}
steps = {e.entry_id: frozenset(c["step"] for c in e.payload["changes"]) for e in entries}
own_group_returned, ranks = 0, []
for entry in entries:
    group, environment, final = records[entry.payload["unit_id"]]
    errors = removed_errors(environment, kb.vocabulary)
    query = Query(errors=tuple(t for _, t in errors), version=final.get("selected_version"),
                  categories=tuple(sorted({c for c, _ in errors})), group=group)
    hits = retrieve(kb, query, KS[-1], ("K3",))["K3"]
    own_group_returned += sum(by_id[h.entry_id].group == group for h in hits)
    candidates = [e for e in entries if e.group != group and steps[e.entry_id] == steps[entry.entry_id]]
    if not candidates:
        continue
    rank = next((i + 1 for i, h in enumerate(hits) if steps[h.entry_id] == steps[entry.entry_id]), None)
    ranks.append(dict(sample=entry.entry_id, operator="+".join(sorted(steps[entry.entry_id])), split="all",
                      group=group, rank=rank, returned=len(hits)))
# Isolation: a memory holding only one project's repairs gives that project nothing.
isolated = 0
for group in sorted({e.group for e in entries}):
    alone = KnowledgeBase([e for e in entries if e.group == group], vocabulary)
    entry = alone.entries[0]
    hits = retrieve(alone, Query(errors=tuple(entry.payload["errors"][0][1:]), group=group), KS[-1], ("K3",))["K3"]
    isolated += int(not hits)
result = dict(units=len(records), memory_entries=len(entries), groups=len({e.group for e in entries}),
              scored=len(ranks), own_group_returned=own_group_returned, isolation_groups=len({e.group for e in entries}),
              isolation_empty=isolated, ks=KS, rates=hit_rates(ranks, KS))
out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf8")
print(json.dumps({k: v for k, v in result.items() if k != "rates"}, sort_keys=True))
print(json.dumps(result["rates"], sort_keys=True))
