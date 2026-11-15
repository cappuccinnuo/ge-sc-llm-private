"""Run frozen extraction over the first N replay jobs in ONE process; report disputed fact per run of target."""
import json, os, sys
repo, plan, solc_dir, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
sys.path.insert(0, repo); os.chdir(repo)
from scripts.DFG.dfg_v2 import validate_slither as V
jobs = json.load(open(plan))["jobs"][:n]
for i, j in enumerate(jobs, 1):
    path = os.path.join(repo, j["source"])
    raw = open(path, "rb").read()
    try:
        ref, ext = V.slither_full_facts(V._compile(path, os.path.join(solc_dir, "solc-" + j["version"])), path, raw)
    except Exception as e:
        print(json.dumps({"i": i, "error": type(e).__name__})); continue
    if "buggy_43" in path:
        occ = ext["occurrences"]
        hit = [o["context_contract"] for o in occ if o.get("layer") == "L1" and list(o["fact"]) == [162, "out", "DEF"]]
        print(json.dumps({"i": i, "occ": len(occ), "hits": hit}))
