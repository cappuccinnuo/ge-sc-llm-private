import json, os, sys
repo, path, solc, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
sys.path.insert(0, repo); os.chdir(repo)
from scripts.DFG.dfg_v2 import validate_slither as V
raw = open(path, "rb").read()
for i in range(n):
    ref, ext = V.slither_full_facts(V._compile(path, solc), path, raw)
    occ = ext["occurrences"]
    hits = sorted(o["context_contract"] for o in occ if o.get("layer") == "L1" and list(o["fact"]) == [282, "out", "DEF"])
    print(json.dumps({"run": i + 1, "occ": len(occ), "hits": hits}), flush=True)
