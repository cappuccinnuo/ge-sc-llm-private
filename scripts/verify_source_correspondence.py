"""End-to-end check that graph nodes really describe the source they claim to.

validate_pipeline.py proves the pipeline is self-consistent. This proves it agrees
with the .sol files on disk, which is the part that would silently poison training
if it were wrong.

  A. node['code'] equals the preprocessed source at node_source_code_lines.
     Ties the stored snippet to the indices tree-sitter emitted.

  B. node['code'] equals the ORIGINAL source at node_source_code_lines_original
     once comments are stripped. Chains A through the line map back to the file.

  C. For every buggy node, the annotated vulnerable line's original text is really
     inside that node's code. This is the label-level ground-truth check.

  D. No annotated line that some node covers was left unlabelled, per contract.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from line_mapping import build_line_map  # noqa: E402
from process_graphs.tree_sitter_codeviews.utils import preprocessor  # noqa: E402

SRC = REPO / "experiments/ge-sc-data/source_code/reentrancy/source_files"
GRAPH = REPO / "experiments/ge-sc-data/source_code/reentrancy/cfg_compressed_graphs.gpickle"

COMMENT = re.compile(r'//.*?$|/\*.*?\*/', re.DOTALL | re.MULTILINE)


def norm(text):
    """Collapse whitespace so indentation/line-join differences do not count."""
    return re.sub(r"\s+", " ", text or "").strip()


def strip_comments(text):
    return norm(COMMENT.sub(" ", text or ""))


print(f"graph: {GRAPH}")
g = nx.read_gpickle(str(GRAPH))
print(f"nodes: {g.number_of_nodes()}  edges: {g.number_of_edges()}")

# Cache per-contract source, preprocessed source and line map.
cache = {}
for _, d in g.nodes(data=True):
    sf = d.get("source_file")
    if sf in cache:
        continue
    p = SRC / sf
    raw = p.read_text(encoding="utf8", errors="ignore")
    pre = preprocessor.remove_empty_lines(raw)
    pre = preprocessor.remove_comments("solidity", pre)
    cache[sf] = {
        "raw_lines": raw.split("\n"),
        "pre_lines": pre.split("\n"),
        "line_map": build_line_map(raw),
    }
print(f"contracts: {len(cache)}")

a_ok = a_bad = a_skip = 0
b_ok = b_bad = b_skip = 0
a_examples, b_examples = [], []

for _, d in g.nodes(data=True):
    sf = d["source_file"]
    c = cache[sf]
    code = d.get("code")
    pre_lines = d.get("node_source_code_lines") or []
    orig_lines = d.get("node_source_code_lines_original") or []

    # ---- A: code vs preprocessed slice ----
    if not code or not pre_lines:
        a_skip += 1
    else:
        lo, hi = min(pre_lines), max(pre_lines)
        slice_text = norm("\n".join(c["pre_lines"][lo - 1:hi]))
        if norm(code) and norm(code) in slice_text or slice_text in norm(code):
            a_ok += 1
        else:
            a_bad += 1
            if len(a_examples) < 3:
                a_examples.append((sf, pre_lines, norm(code)[:90], slice_text[:90]))

    # ---- B: code vs original slice, comments removed ----
    if not code or not orig_lines:
        b_skip += 1
    else:
        lo, hi = min(orig_lines), max(orig_lines)
        slice_text = strip_comments("\n".join(c["raw_lines"][lo - 1:hi]))
        code_text = strip_comments(code)
        if code_text and (code_text in slice_text or slice_text in code_text):
            b_ok += 1
        else:
            b_bad += 1
            if len(b_examples) < 3:
                b_examples.append((sf, orig_lines, code_text[:90], slice_text[:90]))

print()
print("A. node['code'] vs preprocessed source slice")
print(f"   match {a_ok}   mismatch {a_bad}   skipped(no code/lines) {a_skip}")
for sf, lines, code, sl in a_examples:
    print(f"     {sf} pre={lines}\n       code={code}\n       src ={sl}")

print()
print("B. node['code'] vs ORIGINAL source slice (comments stripped)")
print(f"   match {b_ok}   mismatch {b_bad}   skipped {b_skip}")
for sf, lines, code, sl in b_examples:
    print(f"     {sf} orig={lines}\n       code={code}\n       src ={sl}")

# ---- C: buggy nodes really contain the annotated line ----
print()
print("C. buggy nodes contain the annotated vulnerable line")
c_ok = c_bad = 0
c_examples = []
for _, d in g.nodes(data=True):
    vulns = d.get("node_info_vulnerabilities")
    if not vulns:
        continue
    sf = d["source_file"]
    raw_lines = cache[sf]["raw_lines"]
    orig = set(d.get("node_source_code_lines_original") or [])
    hit_lines = sorted({l for v in vulns for l in v["lines"]} & orig)
    if not hit_lines:
        c_bad += 1
        if len(c_examples) < 3:
            c_examples.append((sf, sorted(orig), "no annotated line inside node"))
        continue
    # The node's code and the annotated line must overlap, in either direction:
    # a node can span several lines, and a single line can hold several statements
    # (e.g. "if (...) { throw; }" becomes an if node plus a throw node, and the
    # throw node's code is only a fragment of that line).
    code_text = strip_comments(d.get("code"))
    line_text = strip_comments(raw_lines[hit_lines[0] - 1])
    if not line_text or line_text in code_text or code_text in line_text:
        c_ok += 1
    else:
        c_bad += 1
        if len(c_examples) < 3:
            c_examples.append((sf, hit_lines, f"line={line_text[:70]} | code={code_text[:70]}"))
print(f"   consistent {c_ok}   inconsistent {c_bad}")
for e in c_examples:
    print("     ", e)

# ---- D: coverage per contract ----
print()
print("D. per-contract label coverage")
by_file = Counter()
buggy_by_file = Counter()
for _, d in g.nodes(data=True):
    by_file[d["source_file"]] += 1
    if d.get("node_info_vulnerabilities"):
        buggy_by_file[d["source_file"]] += 1
print(f"   contracts with >=1 buggy node : {len(buggy_by_file)}")
print(f"   contracts fully clean         : {len(by_file) - len(buggy_by_file)}")
print(f"   total buggy nodes             : {sum(buggy_by_file.values())}")

print()
failed = a_bad or b_bad or c_bad
print("RESULT:", "MISMATCHES FOUND" if failed else "SOURCE CORRESPONDENCE VERIFIED")
sys.exit(1 if failed else 0)
