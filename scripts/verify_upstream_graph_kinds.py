"""Establish what each of the authors' two graphs actually is, from content not names.

The filenames say cfg for node_detection and cfg_cg for graph_detection, but a name
is not evidence. A call graph shows up as call-typed edges between function nodes, so
that is what gets checked here, together with the contract counts the two phases are
supposed to differ on (line level: buggy contracts only; contract level: the balanced
full corpus).
"""
import pickle
from collections import Counter
from pathlib import Path

try:
    import pickle5
except ImportError:
    pickle5 = None

REPO = Path(__file__).resolve().parents[1]
UP = REPO / "data/upstream_mando_llm"

FILES = {
    "node_detection  (line level)":
        UP / "node_detection/reentrancy_tree_sitter_cfg_compressed_graphs.gpickle",
    "graph_detection (contract level)":
        UP / "graph_detection/reentrancy_tree_sitter_cfg_cg_compressed_graphs.gpickle",
}

CALL_MARKERS = ("call", "invoke", "return", "recursive")


def load(path):
    with open(path, "rb") as f:
        try:
            return pickle.load(f)
        except ValueError:
            pass
    with open(path, "rb") as f:
        return pickle5.load(f)


for title, path in FILES.items():
    print("=" * 78)
    print(title)
    print(f"  file: {path.name}")
    print("=" * 78)
    g = load(path)

    etypes = Counter(d.get("edge_type") for _, _, d in g.edges(data=True))
    ntype = {n: d.get("node_type") for n, d in g.nodes(data=True)}
    files = {d.get("source_file") for _, d in g.nodes(data=True)}
    buggy_files = set()
    for _, d in g.nodes(data=True):
        if d.get("node_info_vulnerabilities"):
            buggy_files.add(d.get("source_file"))

    print(f"  nodes {g.number_of_nodes()}   edges {g.number_of_edges()}")
    print(f"  contracts {len(files)}   of which carry >=1 buggy node: {len(buggy_files)}")
    print(f"  clean contracts present: {len(files - buggy_files)}")

    print(f"\n  edge types ({len(etypes)}):")
    for t, n in etypes.most_common():
        print(f"    {str(t):22s} {n:6d}")

    call_types = [t for t in etypes if t and any(m in str(t).lower() for m in CALL_MARKERS)]
    print(f"\n  call-like edge types present: {call_types or 'NONE'}")

    # a call graph links function-level nodes to each other
    fn_to_fn = 0
    for s, t, d in g.edges(data=True):
        if (ntype.get(s) in ("function_definition", "constructor_definition")
                and ntype.get(t) in ("function_definition", "constructor_definition")):
            fn_to_fn += 1
    print(f"  function->function edges of any type: {fn_to_fn}")

    verdict = "CFG + CG (call structure present)" if call_types else "CFG only (no call structure)"
    print(f"\n  VERDICT: {verdict}")
    print()

print("=" * 78)
print("what the repository's own asset resolver expects")
print("=" * 78)
import sys
sys.path.insert(0, str(REPO))
from sco_models.classifier_cli import graph_asset_paths, node_asset_paths
gp = graph_asset_paths("mando-assets", "reentrancy", tree_sitter=True)
np_ = node_asset_paths("mando-assets", "reentrancy", tree_sitter=True)
print(f"  contract level (graph_classifier): {Path(gp['compressed_graph']).name}")
print(f"  line level     (node_classifier) : {Path(np_['compressed_graph']).name}")
