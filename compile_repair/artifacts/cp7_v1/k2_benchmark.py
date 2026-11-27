"""CP7 K2 benchmark on the CP4/CP5 package-removal samples (PROMPTS 3.4, 4.7).

Usage: python -B k2_benchmark.py <dependency index> <out.json> <mutation.json> [<mutation.json> ...]
Each mutation.json is an unresolved_package_import sample written by
evaluation/benchmark.py (fields package, logical_package_paths, original_sha256, version,
split, group). One query per removed file: the import path the damaged source still uses
and the sample's compiler version, nothing else. A hit is
- correct when it is a file of the removed package at the same path (any release);
- identical when its bytes equal the removed vendored file (original_sha256).
"""
import collections
import json
import sys
from pathlib import Path

from compile_repair.evaluation.report import hit_rates
from compile_repair.rag.knowledge import KnowledgeBase, library_entries
from compile_repair.rag.retrieve import Query, retrieve

KS = (1, 2, 3, 5, 8, 10)
kb = KnowledgeBase(library_entries(sys.argv[1]), vocabulary=frozenset())
out, manifests = Path(sys.argv[2]), sys.argv[3:]
entries = {e.entry_id: e for e in kb.by_source["K2"]}
indexed = collections.defaultdict(set)
for e in entries.values():
    indexed[e.payload["package"], e.payload["path"]].add(e.payload["sha256"])
correct, identical, skipped = [], [], collections.Counter()
for path in manifests:
    mutation = json.loads(Path(path).read_text(encoding="utf8"))
    if mutation.get("operator") != "unresolved_package_import":
        skipped["other_operator"] += 1
        continue
    package = mutation["package"]
    for old, logical in sorted(mutation["logical_package_paths"].items()):
        inside = logical[len(package) + 1:]
        if (package, inside) not in indexed:
            skipped["path_not_in_index"] += 1
            continue
        query = Query(import_paths=(logical,), version=mutation["version"], group=mutation["group"])
        hits = retrieve(kb, query, KS[-1], ("K2",))["K2"]
        base = dict(sample=path + "#" + old, operator=package, split=mutation["split"], group=mutation["group"])
        good = [i + 1 for i, h in enumerate(hits)
                if (entries[h.entry_id].payload["package"], entries[h.entry_id].payload["path"]) == (package, inside)]
        correct.append(dict(base, rank=good[0] if good else None, returned=len(hits)))
        if mutation["original_sha256"].get(old) in indexed[package, inside]:
            same = [i + 1 for i, h in enumerate(hits) if entries[h.entry_id].payload["sha256"] == mutation["original_sha256"][old]]
            identical.append(dict(base, rank=same[0] if same else None, returned=len(hits)))
        else:
            skipped["no_identical_release_in_index"] += 1
result = dict(k2_entries=len(entries), queries=len(correct), identical_queries=len(identical), skipped=dict(skipped),
              ks=KS, correct=hit_rates(correct, KS), identical=hit_rates(identical, KS))
out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf8")
print(json.dumps(dict(queries=len(correct), identical_queries=len(identical), skipped=dict(skipped),
                      correct=result["correct"].get("all"), identical=result["identical"].get("all")), sort_keys=True))
