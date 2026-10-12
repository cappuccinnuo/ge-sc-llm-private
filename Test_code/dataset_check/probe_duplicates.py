"""Read-only: for every SolidiFI file with duplicated annotation lines, where (if at all)
does the authors' annotation stop, relative to the duplicates?

    python -B Test_code/dataset_check/probe_duplicates.py
"""
import ast
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pickle5

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Test_code/labeling_v3"))
import author_rule as rule  # noqa: E402

UP = REPO / "data/upstream_mando_llm/graph_detection"
SRC = REPO / "experiments/ge-sc-data/source_code"


def lit(v):
    for _ in range(3):
        if not isinstance(v, str):
            break
        try:
            v = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            break
    return v


for bug in rule.BUG_TYPES:
    g = pickle5.load(open(UP / f"{bug}_tree_sitter_cfg_cg_compressed_graphs.gpickle", "rb"))
    ann = defaultdict(set)
    files = set()
    for _, d in g.nodes(data=True):
        files.add(d["source_file"])
        recs = lit(d.get("node_info_vulnerabilities"))
        for r in (recs if isinstance(recs, list) else []):
            ann[d["source_file"]].update(r["lines"])
    for name in sorted(f for f in files if f.startswith("buggy_")):
        number = name[6:-4]
        path = rule.SOLIDIFI_DIR / rule.SOLIDIFI_CATEGORY[bug] / f"BugLog_{number}.csv"
        if not path.exists() or name not in ann:
            continue
        rows = [(int(r["loc"]), int(r["length"])) for r in csv.DictReader(open(path, newline=""))]
        raw = sorted(n for loc, length in rows for n in range(loc, loc + length))
        dups = sorted(v for v, c in Counter(raw).items() if c > 1)
        if not dups:
            continue
        source = (SRC / bug / "source_files" / name).read_text(encoding="utf8")
        fwd = rule.original_to_preprocessed(source)
        text = source.split("\n")
        kept = [o for o in sorted(set(raw)) if fwd.get(o) and set(fwd[o]) <= ann[name]]
        lost = [o for o in sorted(set(raw)) if fwd.get(o) and not (set(fwd[o]) & ann[name])]
        npre = len(rule.build_line_map(source))
        garbage = sorted(a for a in ann[name] if a > npre)
        srows = sorted(rows)
        overlaps = [(a, b) for a, b in zip(srows, srows[1:]) if a[0] + a[1] > b[0]]
        last_kept = kept[-1] if kept else None
        first_lost = lost[0] if lost else None
        print(f"{bug:26s} {name:13s} dups {len(dups):2d} first {dups[:6]} | overlapping rows (loc,len): {overlaps[:4]} "
              f"| kept {len(kept)} lost {len(lost)} first_lost {first_lost} garbage {len(garbage)}")
        d = dups[0]
        print(f"      first dup line {d}: {text[d - 1].strip()[:70]!r}  mapped pre {fwd.get(d)}  "
              f"blank/comment-only: {not fwd.get(d)}")
