"""Find where the attribute-less nodes come from, and whether call edges duplicate.

networkx silently creates a bare node when add_edge references an id that was never
added with attributes; those nodes have node_type None and _annotate_cfg_graph then
deletes them along with their edges. This locates which edge types introduce them,
and checks whether add_dummy_edges and add_function_call_edges both connect the same
(caller, callee) pair under different type names.
"""
import contextlib
import io
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from process_graphs.tree_sitter_codeviews.codeviews.CFG.CFG_driver import CFGDriver  # noqa: E402

SRC = REPO / "experiments/ge-sc-data/source_code/reentrancy/source_files"
SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 20

edges_into_none = Counter()
none_is_source = Counter()
dup_pairs = Counter()
total_none = 0

for path in sorted(SRC.glob("*.sol"))[:SAMPLE]:
    source = path.read_text(encoding="utf8", errors="ignore")
    with contextlib.redirect_stdout(io.StringIO()):
        g = CFGDriver("solidity", source, output_file=None).graph

    none_nodes = {n for n, d in g.nodes(data=True) if d.get("node_type") is None}
    total_none += len(none_nodes)

    for s, t, d in g.edges(data=True):
        et = d.get("edge_type")
        if t in none_nodes:
            edges_into_none[et] += 1
        if s in none_nodes:
            none_is_source[et] += 1

    # same ordered pair carrying more than one edge type
    pair_types = {}
    for s, t, d in g.edges(data=True):
        pair_types.setdefault((s, t), set()).add(d.get("edge_type"))
    for pair, types in pair_types.items():
        if len(types) > 1:
            dup_pairs[tuple(sorted(str(x) for x in types))] += 1

print(f"sampled {SAMPLE} contracts")
print(f"attribute-less (node_type=None) nodes: {total_none}")
print("\nedge types pointing INTO those nodes:")
for t, n in edges_into_none.most_common():
    print(f"  {str(t):24s} {n}")
print("\nedge types leaving FROM those nodes:")
for t, n in none_is_source.most_common():
    print(f"  {str(t):24s} {n}")
print("\nnode pairs carrying multiple edge types (possible duplicate semantics):")
for types, n in dup_pairs.most_common(10):
    print(f"  {types}  x{n}")
