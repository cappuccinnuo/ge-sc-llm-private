"""Graph pickle I/O that works on networkx 2.x and 3.x.

networkx 3.0 removed nx.read_gpickle / nx.write_gpickle. Those were thin wrappers
around pickle, so these helpers reproduce them exactly. Graphs are written with
pickle protocol 4 so the legacy Python 3.7 environment can still read files built
on the new machine (the authors' protocol-5 gpickles could not be read there).

It lives here rather than in sco_models/ so no pinned file or pinned directory
changes; training already reads graphs through sco_models.graph_utils.read_gpickle,
which falls back to pickle on networkx 3.
"""
import pickle

PROTOCOL = 4


def read_gpickle(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def write_gpickle(graph, path, protocol=PROTOCOL):
    with open(path, "wb") as f:
        pickle.dump(graph, f, protocol=protocol)
