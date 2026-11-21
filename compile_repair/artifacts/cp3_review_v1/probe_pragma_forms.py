"""Pragma spellings that solc accepts versus compile_repair's pragma_interval.
Usage (production env, repo root): python -I probe_pragma_forms.py <repo> <solc dir> <out.json>"""
import json, os, subprocess, sys, tempfile
repo, solc_dir, out = sys.argv[1:4]
sys.path.insert(0, repo); os.chdir(repo)
from compile_repair.rules.environment import pragma_interval
CASES = [("0.4.x", "0.4.24"), ("0.5.*", "0.5.17"), ("^0.5", "0.5.17"), ("0.4.X", "0.4.24"),
         ("^ 0.5.0", "0.5.17"), ("=0.5.12", "0.5.12"), ("~0.4.24", "0.4.24"), (">=0.4.22 <0.6.0", "0.5.17")]
rows, tmp = [], tempfile.mkdtemp()
for expr, version in CASES:
    src = ("pragma solidity %s;\ncontract A {}\n" % expr).encode()
    path = os.path.join(tmp, "p.sol"); open(path, "wb").write(src)
    run = subprocess.run([os.path.join(solc_dir, "solc-" + version), "--combined-json", "abi", path], capture_output=True, text=True)
    try:
        module = repr(pragma_interval([src]))
    except Exception as exc:
        module = "%s: %s" % (type(exc).__name__, exc)
    rows.append({"expression": expr, "solc_version": version, "solc_rc": run.returncode,
                 "solc_error": run.stderr.strip().splitlines()[0] if run.returncode else None, "module": module})
    print(json.dumps(rows[-1]))
json.dump(rows, open(out, "w"), indent=1)
