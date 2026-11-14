"""Run frozen 6c extraction on one file; report the disputed L1 DEF occurrence and total count."""
import json, os, sys
repo, path, solc = sys.argv[1:4]
sys.path.insert(0, repo); os.chdir(repo)
from scripts.DFG.dfg_v2 import validate_slither as V
raw = open(path, "rb").read()
sl = V._compile(path, solc)
ref, ext = V.slither_full_facts(sl, path, raw)
occ = ext.get("occurrences") if isinstance(ext, dict) else None
hit = [o for o in (occ or []) if o.get("layer") == "L1" and list(o.get("fact", [])) == [162, "out", "DEF"]]
print(json.dumps({"seed": os.environ.get("PYTHONHASHSEED"), "occ": len(occ or []),
                  "hits": [(o.get("context_contract"), o.get("declarer")) for o in hit]}))
if len(sys.argv) > 4:
    json.dump(occ, open(sys.argv[4], "w"))
