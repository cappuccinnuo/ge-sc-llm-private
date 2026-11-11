"""Cross-version invariance of Slither 0.8.0 CFG nodes (evidence only, not production code).

For every file in slither_probe.json, run Slither at the two compiler versions recorded there and compare
  key4 = (contract, function full_name, node type, start offset)
  key5 = key4 + sorted SlithIR strings of the node
  span = key4 + source length
Usage: python cross_version.py <slither_probe.json> <corpus source_code dir> <solc dir> <out.json>
"""
import json
import os
import sys

from slither import Slither

PROBE, CORPUS, SOLC, OUT = sys.argv[1:5]
result = []
for o in json.load(open(PROBE)):
    path = os.path.join(CORPUS, o["class"], "source_files", o["file"])
    per = {}
    for v in o["runs"]:
        sl = Slither(path, solc=os.path.join(SOLC, "solc-" + v))
        k4, k5, sp, nofile = set(), set(), set(), 0
        for c in sl.contracts:
            for f in c.functions_and_modifiers_declared:
                for n in f.nodes:
                    sm = n.source_mapping or {}
                    key = (c.name, f.full_name, str(n.type), sm.get("start"))
                    k4.add(key)
                    k5.add(key + (tuple(sorted(str(x) for x in n.irs)),))
                    sp.add(key + (sm.get("length"),))
                    nofile += not (sm.get("filename_absolute") or sm.get("filename_used"))
        per[v] = (k4, k5, sp, nofile)
    rec = {"class": o["class"], "file": o["file"], "versions": list(per),
           "nodes_without_filename": {v: per[v][3] for v in per}}
    if len(per) == 2:
        a, b = list(per.values())
        rec["same_key4"] = a[0] == b[0]
        rec["same_key5_ir"] = a[1] == b[1]
        rec["same_span_length"] = a[2] == b[2]
        rec["span_length_differences"] = len(a[2] ^ b[2]) // 2
    result.append(rec)
json.dump(result, open(OUT, "w"), indent=1)
pairs = [r for r in result if "same_key4" in r]
print(json.dumps({
    "files": len(result), "pairs": len(pairs),
    "same_key4": sum(r["same_key4"] for r in pairs),
    "same_key5_ir": sum(r["same_key5_ir"] for r in pairs),
    "same_span_length": sum(r["same_span_length"] for r in pairs),
    "versions_with_missing_filename": sorted({v for r in result for v, n in r["nodes_without_filename"].items() if n}),
}))
