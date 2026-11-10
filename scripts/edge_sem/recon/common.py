"""Read-only EP0 helpers. All outputs must stay under the new EdgeSem folder."""
import hashlib
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "scripts/edge_sem/artifacts/ep0_v1"
PLAN = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/plan.json"

def ref(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return dict(path=str(path), sha256=h.hexdigest(), bytes=path.stat().st_size)

def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))

def checked(row):
    p = Path(row["path"])
    if ref(p)["sha256"] != row["sha256"]:
        raise ValueError("SHA mismatch: " + str(p))
    return p

def write(path, value):
    path = Path(path).resolve()
    if ROOT / "scripts/edge_sem" not in path.parents:
        raise ValueError("Output outside EdgeSem")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")

def key(node):
    return None if node is None else (node.start_byte, node.end_byte, node.type)

def histogram(values):
    return {str(k): v for k, v in sorted(Counter(values).items())}

def canonical_rows(data):
    return [dict(canonical=list(c), edges=len(data[c][0])) for c in sorted(data)]

def typed_data(data):
    """Probe-only edge dictionary, no stored graph or production materializer."""
    from scripts.DFG.dfg_v2 import FORWARD_RELATIONS, REVERSE_OF
    out, origins = {}, {}
    for c, pair in data.items():
        if c[1].startswith("REV_"):
            raise ValueError("Expected forward-only stored input")
        rev = (c[2], REVERSE_OF.get(c[1], "REV_" + c[1]), c[0])
        if c in out or rev in out:
            raise ValueError("Typed key collision")
        out[c], out[rev] = pair, (pair[1], pair[0])
        origins[c] = c
        origins[rev] = rev if c[1] in FORWARD_RELATIONS else (c[2], c[1], c[0])
    return out, origins

def cfg_dominance(graph, entry):
    """Exit-rooted postdominance is partial when nodes cannot reach an exit."""
    import networkx as nx
    reached = {entry} | nx.descendants(graph, entry)
    active = graph.subgraph(reached).copy()
    dom = nx.immediate_dominators(active, entry)
    def dominates(a, b):
        while True:
            if a == b:
                return True
            parent = dom[b]
            if parent == b:
                return False
            b = parent
    back = [(a,b) for a,b in active.edges() if dominates(b,a)]
    exits = [n for n in active if active.out_degree(n) == 0]
    reverse = active.reverse(copy=True)
    sink = ("EP0", "virtual_exit")
    reverse.add_node(sink)
    reverse.add_edges_from((sink, n) for n in exits)
    post = nx.immediate_dominators(reverse, sink)
    return active, dom, post, back
