"""Characterize the residual code/line mismatches found by verify_source_correspondence.

Groups them by node_type and prints the raw tree-sitter label, to confirm whether the
cause is the same label-parsing weakness already known for end_if: generator.py reads
the last two dash-separated fields of the label as (first_line, last_line), which does
not hold for every node type.
"""
import re
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from process_graphs.tree_sitter_codeviews.utils import preprocessor  # noqa: E402

SRC = REPO / "experiments/ge-sc-data/source_code/reentrancy/source_files"
GRAPH = REPO / "experiments/ge-sc-data/source_code/reentrancy/cfg_compressed_graphs.gpickle"
COMMENT = re.compile(r'//.*?$|/\*.*?\*/', re.DOTALL | re.MULTILINE)


def norm(t):
    return re.sub(r"\s+", " ", t or "").strip()


g = nx.read_gpickle(str(GRAPH))
cache = {}
for _, d in g.nodes(data=True):
    sf = d["source_file"]
    if sf not in cache:
        raw = (SRC / sf).read_text(encoding="utf8", errors="ignore")
        pre = preprocessor.remove_empty_lines(raw)
        pre = preprocessor.remove_comments("solidity", pre)
        cache[sf] = pre.split("\n")

bad_types = Counter()
all_types = Counter()
samples = []
for _, d in g.nodes(data=True):
    code = d.get("code")
    pre_lines = d.get("node_source_code_lines") or []
    ntype = d.get("node_type")
    all_types[ntype] += 1
    if not code or not pre_lines:
        continue
    lo, hi = min(pre_lines), max(pre_lines)
    slice_text = norm("\n".join(cache[d["source_file"]][lo - 1:hi]))
    c = norm(code)
    if not (c in slice_text or slice_text in c):
        bad_types[ntype] += 1
        if len(samples) < 8:
            samples.append((d["source_file"], ntype, pre_lines, d.get("label", "")[-40:], c[:70], slice_text[:70]))

print("mismatching nodes by node_type (count / total of that type):")
for t, n in bad_types.most_common():
    print(f"  {t:24s} {n:5d} / {all_types[t]}")
print()
print("samples (label tail shows what generator.py parses for line numbers):")
for sf, ntype, lines, label, code, src in samples:
    print(f"  {sf}  type={ntype}  declared_pre_lines={lines}")
    print(f"    label tail : ...{label}")
    print(f"    node code  : {code}")
    print(f"    source slice: {src}")
    print()
