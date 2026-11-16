"""Per-task EdgeSem store.

Layout (``root`` is usually ``data/edgesem``)::

    <root>/<dataset>/<category>/<task>/f4_edges.jsonl    E1 edge records (MOD_APPLY, CALL_SITE, GUARDS)
                                      /f4_audit.json     per-file evidence and the guard correspondence audit
                                      /attributes.npz    edge_keys (str) and attrs (uint8[rows, 74])
                                      /diagnostics.json  per-edge attribute reasons and unknown fields
                                      /summary.json      counts, digests and the F3 graph it was built from

Edge keys and F4 endpoints are F3 node ids, so a store is valid only for the F3 graph whose
sha256 ``summary.json`` records; training checks it.
"""
import json
from pathlib import Path

import numpy as np

from nodesem.store import read_jsonl, write_jsonl


class EdgeStore:
    def __init__(self, root, dataset, category, task):
        self.path = Path(root) / dataset / category / task

    def summary(self):
        path = self.path / "summary.json"
        if not path.is_file():
            raise FileNotFoundError("%s has no EdgeSem store; run `python -m edgesem build`" % self.path)
        return json.loads(path.read_text())

    def write(self, edges, audit, keys, matrix, diagnostics, summary):
        self.path.mkdir(parents=True, exist_ok=True)
        write_jsonl(self.path / "f4_edges.jsonl", edges)
        (self.path / "f4_audit.json").write_text(json.dumps(audit, sort_keys=True, default=str))
        (self.path / "diagnostics.json").write_text(json.dumps(diagnostics, sort_keys=True, default=str))
        np.savez_compressed(self.path / "attributes.npz", edge_keys=np.asarray(keys), attrs=matrix)
        # Written last: its presence marks a complete store.
        (self.path / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))

    def edges(self):
        return read_jsonl(self.path / "f4_edges.jsonl")

    def attributes(self):
        """{edge row key: uint8[74]} in stored row order."""
        with np.load(self.path / "attributes.npz", allow_pickle=False) as archive:
            keys, matrix = archive["edge_keys"].tolist(), archive["attrs"].copy()
        if matrix.dtype != np.uint8 or matrix.shape != (len(keys), 74) or len(set(keys)) != len(keys):
            raise ValueError("%s: malformed attribute matrix" % self.path)
        return dict(zip(keys, matrix))
