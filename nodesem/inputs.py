"""Task context for NodeSem producers, from hcg and dfg outputs.

A context holds, for one task: the HCG graph (``F0``) and the full DFG graph
(``F3``, which adds ``env_source`` nodes), the original node order, every source
file (text, SHA-256, recorded compiler version), the F3 layer audit whose evidence
backs the DFG edges, and each file's identifier bijection (used only to gate the
code view on exact AST identities).
"""
import json
from pathlib import Path

from dfg.inputs import load_task
from dfg.train.features import anonymize
from hcg.datasets.registry import get_dataset
from hcg.store.io import read_gpickle, sha256

REPO = Path(__file__).resolve().parents[1]


def _relative(path):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def load_context(dataset, category, task, hcg_root, dfg_root, label_root):
    inp = load_task(hcg_root, dataset, category, task, label_root)
    store = Path(dfg_root) / dataset / category / task
    summary = json.loads((store / "summary.json").read_text())
    if summary["hcg_graph"]["sha256"] != sha256(inp.graph_path):
        raise ValueError("%s: DFG store was built from a different HCG graph" % inp.task_id)
    if "F3" not in summary["graphs"]:
        raise ValueError("%s: NodeSem needs the full DFG graph (python -m dfg build, L1-L3)" % inp.task_id)
    f3 = read_gpickle(store / "F3/graph.gpickle")
    audit_path = store / "F3/audit.json"
    corpus = get_dataset(dataset).corpus(REPO, category)
    sources = {f: dict(path=_relative(corpus / f), sha256=sha256(corpus / f), metadata=inp.metadata.get(f))
               for f in inp.sources}
    return dict(task_id=inp.task_id, dataset=dataset, category=category, task=task,
                graphs=dict(F0=inp.graph, F3=f3), order=list(inp.graph), sources=sources,
                source_text=inp.sources, audit=json.loads(audit_path.read_text()),
                naming={f: anonymize(s) for f, s in inp.sources.items()},
                provenance=dict(audit=dict(path=_relative(audit_path), sha256=sha256(audit_path))))
