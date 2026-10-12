"""Read-only: where exactly does the authors' annotation stop being correct in the odd files?

For every file whose embedded author annotation differs from the public annotation
(in preprocessed coordinates), list which annotated original lines survive and show
the source around the first lost line, plus any non-ASCII / tab / CR characters.

    python -B Test_code/dataset_check/probe_break_points.py
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

BUGS = ["access_control", "arithmetic", "denial_of_service", "front_running", "reentrancy",
        "time_manipulation", "unchecked_low_level_calls"]


def lit(v):
    for _ in range(3):
        if not isinstance(v, str):
            break
        try:
            v = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            break
    return v


for bug in BUGS:
    g = pickle5.load(open(UP / f"graph_detection/{bug}_tree_sitter_cfg_cg_compressed_graphs.gpickle", "rb"))
    ann = defaultdict(set)
    for _, d in g.nodes(data=True):
        recs = lit(d.get("node_info_vulnerabilities"))
        for r in (recs if isinstance(recs, list) else []):
            ann[d["source_file"]].update(r["lines"])
    recs = {Path(r["name"]).name: r for r in json.load(open(HGT / f"data/solidifi_buggy_contracts/{bug}/vulnerabilities.json"))}
    for name in sorted(ann):
        if name not in recs:
            continue
        text = (SRC / bug / "source_files" / name).read_text(encoding="utf8")
        orig = text.split("\n")
        lm = build_line_map(text)
        o2p = defaultdict(set)
        for p, os_ in enumerate(lm, 1):
            for o in os_:
                o2p[o].add(p)
        raw = sorted({n for v in recs[name]["vulnerabilities"] for n in v["lines"]})
        expected = {p for o in raw for p in o2p[o]}
        if ann[name] == expected:
            continue
        kept = [o for o in raw if o2p[o] and o2p[o] <= ann[name]]
        lost = [o for o in raw if o2p[o] and not (o2p[o] & ann[name])]
        nonascii = [(i + 1, [hex(ord(c)) for c in l if ord(c) > 127][:3]) for i, l in enumerate(orig) if any(ord(c) > 127 for c in l)]
        print("=" * 100)
        print(f"{bug} {name}: raw annotated {len(raw)}  kept {len(kept)}  lost {len(lost)}  "
              f"orig lines {len(orig)}  pre lines {len(lm)}")
        print(f"   kept range {kept[0] if kept else None}..{kept[-1] if kept else None}   "
              f"lost range {lost[0] if lost else None}..{lost[-1] if lost else None}   "
              f"lost lines below last kept: {[o for o in lost if kept and o < kept[-1]][:12]}")
        has_cr = chr(13) in text
        print(f"   non-ASCII lines (first 6): {nonascii[:6]}  total {len(nonascii)};  CR: {has_cr}")
        # vulnerability record order in the json: is the kept part a prefix of the record list?
        order = [v["lines"][0] for v in recs[name]["vulnerabilities"]]
        print(f"   json record count {len(order)}, first-line order (first 12): {order[:12]}")
        if lost:
            lo = lost[0]
            for i in range(max(1, lo - 4), min(len(orig), lo + 3) + 1):
                flag = "K" if i in kept else ("L" if i in lost else " ")
                print(f"      {flag} {i:4d} pre{sorted(o2p[i])} {orig[i - 1][:95]!r}")
