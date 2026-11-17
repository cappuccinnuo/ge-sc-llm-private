"""Pickle/JSON I/O and the per-category output layout.

Graphs are written with pickle protocol 4 so the legacy Python 3.7 environment can
still load them (protocol 5, used by the authors' files, needs Python 3.8+).
networkx 3 removed read_gpickle/write_gpickle; these are the same thin wrappers.
``read_audited_graph`` is the restricted reader for graphs from untrusted locations.
"""
import hashlib
import io
import json
import pickle
import pickletools
from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import numpy as np
from networkx.classes.coreviews import MultiAdjacencyView
from networkx.classes.reportviews import NodeView

PROTOCOL = 4


def read_gpickle(path):
    with open(path, "rb") as handle:
        return pickle.load(handle)


# Restricted reading (formerly scripts/labeling_v2/safe_graph.py, unchanged): only a
# MultiDiGraph of plain dicts and NumPy arrays may be unpickled.
_ALLOWED = {
    ("networkx.classes.multidigraph", "MultiDiGraph"): nx.MultiDiGraph,
    ("networkx.classes.coreviews", "MultiAdjacencyView"): MultiAdjacencyView,
    ("networkx.classes.reportviews", "NodeView"): NodeView,
    ("builtins", "dict"): dict,
    ("numpy.core.multiarray", "_reconstruct"): np.core.multiarray._reconstruct,
    ("numpy", "ndarray"): np.ndarray,
    ("numpy", "dtype"): np.dtype,
}


class _RestrictedReader(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) not in _ALLOWED:
            raise pickle.UnpicklingError("Unapproved pickle global: " + module + "." + name)
        return _ALLOWED[(module, name)]

    def persistent_load(self, pid):
        raise pickle.UnpicklingError("Persistent references are not supported")


def read_audited_graph(path):
    """Unpickle a graph allowing only audited globals and opcodes; validate node tokens."""
    raw = Path(path).read_bytes()
    for op, _, _ in pickletools.genops(raw):
        if op.name in {"EXT1", "EXT2", "EXT4", "PERSID", "BINPERSID", "INST", "OBJ"}:
            raise pickle.UnpicklingError("Unsupported pickle opcode: " + op.name)
    graph = _RestrictedReader(io.BytesIO(raw)).load()
    if type(graph) is not nx.MultiDiGraph:
        raise ValueError("Expected the audited MultiDiGraph format")
    for _, data in graph.nodes(data=True):
        token = data.get("token")
        if token is not None:
            array = np.asarray(token)
            if array.dtype.kind not in "iuf" or array.ndim != 1 or not np.isfinite(array).all():
                raise ValueError("Token feature must be a finite numeric vector")
    return graph


def write_gpickle(obj, path, protocol=PROTOCOL):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        pickle.dump(obj, handle, protocol=protocol)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def dump_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


@dataclass(frozen=True)
class CategoryOutput:
    """Files written for one category: <root>/<dataset>/<category>/..."""
    directory: Path

    @property
    def contract_level(self):
        return self.directory / "contract_level.gpickle"

    @property
    def line_level(self):
        return self.directory / "line_level.gpickle"

    @property
    def graph_labels(self):
        return self.directory / "graph_labels.json"

    @property
    def annotations(self):
        return self.directory / "annotations.json"

    @property
    def line_node_ids(self):
        return self.directory / "line_node_ids.json"

    @property
    def manifest(self):
        return self.directory / "manifest.json"
