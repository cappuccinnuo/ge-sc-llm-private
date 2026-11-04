"""Codex 2026-10-08: restricted I/O for the audited NetworkX/NumPy assets."""
import hashlib
import io
import pickletools
try:
    import pickle5 as pickle
except ImportError:
    import pickle
import networkx as nx
import numpy as np
from networkx.classes.coreviews import MultiAdjacencyView
from networkx.classes.reportviews import NodeView

ALLOWED = {
    ("networkx.classes.multidigraph", "MultiDiGraph"): nx.MultiDiGraph,
    ("networkx.classes.coreviews", "MultiAdjacencyView"): MultiAdjacencyView,
    ("networkx.classes.reportviews", "NodeView"): NodeView,
    ("builtins", "dict"): dict,
    ("numpy.core.multiarray", "_reconstruct"): np.core.multiarray._reconstruct,
    ("numpy", "ndarray"): np.ndarray,
    ("numpy", "dtype"): np.dtype,
}

class RestrictedReader(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) not in ALLOWED:
            raise pickle.UnpicklingError("Unapproved pickle global: " + module + "." + name)
        return ALLOWED[(module, name)]

    def persistent_load(self, pid):
        raise pickle.UnpicklingError("Persistent references are not supported")

def sha256(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def loads_graph(raw):
    for op, _, _ in pickletools.genops(raw):
        if op.name in {"EXT1", "EXT2", "EXT4", "PERSID", "BINPERSID", "INST", "OBJ"}:
            raise pickle.UnpicklingError("Unsupported pickle opcode: " + op.name)
    graph = RestrictedReader(io.BytesIO(raw)).load()
    if type(graph) is not nx.MultiDiGraph:
        raise ValueError("Expected the audited MultiDiGraph format")
    for _, data in graph.nodes(data=True):
        token = data.get("token")
        if token is not None:
            array = np.asarray(token)
            if array.dtype.kind not in "iuf" or array.ndim != 1 or not np.isfinite(array).all():
                raise ValueError("Token feature must be a finite numeric vector")
    return graph

def read_graph(path):
    return loads_graph(path.read_bytes())

def write_graph(graph, path):
    # Protocol 4 is readable by the project's Python 3.7 training environment.
    with path.open("xb") as handle:
        pickle.dump(graph, handle, protocol=4)
