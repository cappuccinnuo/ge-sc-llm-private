"""Read-only: compare the ORDER of lines in the authors' embedded record with the public record.

    python -B Test_code/dataset_check/probe_record_order.py
"""
import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

import pickle5

REPO = Path(__file__).resolve().parents[2]
HGT = REPO.parent / "ge-sc-transformer"
UP = REPO / "data/upstream_mando_llm"
SRC = REPO / "experiments/ge-sc-data/source_code"
sys.path.insert(0, str(REPO / "scripts"))
from line_mapping import build_line_map  # noqa: E402

CASES = [("reentrancy", "buggy_18.sol"), ("access_control", "buggy_18.sol"), ("access_control", "buggy_26.sol"),
         ("arithmetic", "buggy_18.sol"), ("unchecked_low_level_calls", "buggy_26.sol"),
         ("reentrancy", "buggy_19.sol"), ("front_running", "buggy_18.sol")]


def lit(v):
    for _ in range(3):
        if not isinstance(v, str):
            break
        try:
            v = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            break
    return v


graphs = {}
for bug, name in CASES:
    if bug not in graphs:
        graphs[bug] = pickle5.load(open(UP / f"graph_detection/{bug}_tree_sitter_cfg_cg_compressed_graphs.gpickle", "rb"))
    g = graphs[bug]
    author_lists = set()
    for _, d in g.nodes(data=True):
        if d["source_file"] == name:
            recs = lit(d.get("node_info_vulnerabilities"))
            for r in (recs if isinstance(recs, list) else []):
                author_lists.add(tuple(r["lines"]))
    rec = next(r for r in json.load(open(HGT / f"data/solidifi_buggy_contracts/{bug}/vulnerabilities.json"))
               if Path(r["name"]).name == name)
    public = [list(v["lines"]) for v in rec["vulnerabilities"]]
    text = (SRC / bug / "source_files" / name).read_text(encoding="utf8")
    lm = build_line_map(text)
    o2p = defaultdict(list)
    for p, os_ in enumerate(lm, 1):
        for o in os_:
            o2p[o].append(p)
    print("=" * 100)
    print(bug, name, "| distinct author record line-lists:", len(author_lists),
          "| public records:", len(public), "lens", [len(x) for x in public][:5])
    for al in author_lists:
        al = list(al)
        print("  author list len", len(al), "sorted:", al == sorted(al), "dups:", len(al) - len(set(al)))
        print("  author :", al[:70])
    pl = public[0]
    print("  public  len", len(pl), "sorted:", pl == sorted(pl), "dups:", len(pl) - len(set(pl)))
    print("  public  :", pl[:70])
    conv = [o2p[o][0] if o2p[o] else None for o in pl]
    print("  public->pre (same order):", conv[:70])
    al = list(next(iter(author_lists)))
    k = 0
    while k < len(al) and k < len(conv):
        # skip Nones in conv when comparing
        k += 1
    conv_nn = [c for c in conv if c is not None]
    m = 0
    while m < min(len(al), len(conv_nn)) and al[m] == conv_nn[m]:
        m += 1
    print(f"  common prefix (author vs converted-public without unmapped): {m} of author {len(al)} / public-mapped {len(conv_nn)}")
    print("  author tail  :", al[m:m + 45])
    print("  expected tail:", conv_nn[m:m + 45])
    print("  public raw at the same positions:", [o for o in pl if o2p[o]][m:m + 45])
