"""Slither 0.8.0 probe on files that failed under the auto_version_solc rule (evidence only)."""
import json
import os
import sys

from slither import Slither

ROWS, CORPUS, SOLC_DIR, OUT = sys.argv[1:5]
rows = json.load(open(ROWS))
todo = [r for r in rows if r["A"] != "ok"]


def node_set(sl, path):
    nodes, missing = set(), 0
    for c in sl.contracts:
        for f in c.functions_and_modifiers_declared:
            for n in f.nodes:
                sm = n.source_mapping or {}
                fn = sm.get("filename_absolute") or sm.get("filename_used")
                if not fn or os.path.realpath(fn) != os.path.realpath(path):
                    missing += 1
                    continue
                nodes.add((c.name, f.full_name, str(n.type), sm.get("start"), sm.get("length")))
    return nodes, missing


res = []
for r in todo:
    path = os.path.join(CORPUS, r["class"], "source_files", r["file"])
    oks = r.get("B_ok_versions", [])
    if not oks and r["A"] == "fail":
        continue
    picks = sorted({oks[0], oks[-1]}, key=lambda v: tuple(map(int, v.split("."))))
    out = {"class": r["class"], "file": r["file"], "selected_by_rule": r["selected"], "runs": {}}
    sets = {}
    for v in picks:
        try:
            sl = Slither(path, solc=os.path.join(SOLC_DIR, "solc-" + v))
            s, miss = node_set(sl, path)
            sets[v] = s
            out["runs"][v] = {"ok": True, "nodes_mapped": len(s), "nodes_missing_filename": miss}
        except Exception as e:  # recorded, not hidden
            out["runs"][v] = {"ok": False, "error": type(e).__name__ + ": " + str(e)[:200]}
    if len(sets) == 2:
        a, b = list(sets.values())
        out["identical_node_set_across_versions"] = a == b
        out["sym_diff"] = len(a ^ b)
    res.append(out)
json.dump(res, open(OUT, "w"), indent=1)
ok = sum(all(x["ok"] for x in o["runs"].values()) for o in res)
miss = sum(any(x.get("nodes_missing_filename") for x in o["runs"].values()) for o in res)
same = sum(o.get("identical_node_set_across_versions") is True for o in res)
pairs = sum("identical_node_set_across_versions" in o for o in res)
print("files", len(res), "all runs ok", ok, "any missing filename", miss, "identical across versions", same, "/", pairs)
