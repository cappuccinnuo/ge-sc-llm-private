"""Build the sealed knowledge directory the agent reads (K1 + K2 [+ K3]).

Usage: python -B build_knowledge.py <docs root> <out dir> [--index <dependency index>]
                                    [--memory <targets.json> <run dir>]...
K1 comes from artifacts/cp7_v1/fetch_docs.py output; K2 from the sealed CP5 offline index;
K3 from real_check.py run directories (successful repairs with changes; the group of a
unit is its project root, or the file of a stand-alone snippet). Retrieval leaves the
queried project's own K3 entries out, so one memory can serve every project.
"""
import json
import sys
from pathlib import Path

from compile_repair.rag.knowledge import (KnowledgeBase, documentation_entries, documented_terms, library_entries,
    repair_entries)

docs, out, rest = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
index, memory = None, []
while rest:
    if rest[0] == "--index":
        index, rest = rest[1], rest[2:]
    elif rest[0] == "--memory":
        memory.append((rest[1], rest[2]))
        rest = rest[3:]
    else:
        raise SystemExit("unknown argument " + rest[0])
k1 = documentation_entries(docs)
vocabulary = documented_terms(k1)
k2 = library_entries(index) if index else []
records = {}
for targets, run in memory:
    for target in json.loads(Path(targets).read_text(encoding="utf8")):
        unit = Path(run) / target["unit_id"] / "units" / target["unit_id"]
        if (unit / "environment_result.json").exists():
            records[target["unit_id"]] = (target.get("project_root") or target["path"],
                                          json.loads((unit / "environment_result.json").read_text()),
                                          json.loads((unit / "result.json").read_text()))
k3 = repair_entries(records.values(), vocabulary)
seal = KnowledgeBase(k1 + k2 + k3, vocabulary, provenance=dict(
    docs=str(docs), index=index, memory=[list(m) for m in memory])).save(out)
print(json.dumps(dict(counts=seal["counts"], entries_sha256=seal["entries_sha256"])))
