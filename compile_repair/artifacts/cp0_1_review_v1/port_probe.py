"""Run Codex's CP0.1 node_facts / contract_coverage under the current venv's Slither.
Usage: python port_probe.py <repo> <file.sol> <solc>"""
import json, sys
repo, path, solc = sys.argv[1:4]
sys.path.insert(0, repo)
from slither import Slither
from compile_repair.toolchain import slither as T

rec = {"file": path.rsplit("/", 1)[-1], "solc": solc.rsplit("-", 1)[-1]}
try:
    from importlib_metadata import version  # what check_profile imports
    rec["importlib_metadata"] = True
except ImportError as e:
    rec["importlib_metadata"] = "ImportError"
try:
    sl = Slither(path, solc=solc, solc_disable_warnings=True)
except Exception as e:
    rec["construct"] = type(e).__name__ + ": " + str(e).splitlines()[0][:120]
    print(json.dumps(rec)); sys.exit()
for name, fn in (("a", lambda: T.node_facts(sl, [path])), ("b", lambda: T.contract_coverage(sl, [path]))):
    try:
        r = fn()
        if name == "a":
            rec["a"] = {"ok": r["mapping_complete"], "counts": {k: r["counts"][k] for k in ("nodes", "top_level_functions", "missing_filename", "foreign_filename")}}
            rec["dup_key5"] = len(r["nodes"]) - len({json.dumps(n["key5"]) for n in r["nodes"]})
        else:
            rec["b"] = {"ok": r["complete"], "expected": r["expected"], "actual": r["actual"], "fmt": [a["format"] for a in r["asts"]]}
    except Exception as e:
        rec[name] = "EXC " + type(e).__name__ + ": " + str(e).splitlines()[0][:160]
print(json.dumps(rec))
