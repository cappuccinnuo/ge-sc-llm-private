"""Run make_plan's pragma reader, solc and production Slither on inputs that solc accepts.

Usage (production Slither env, repo root, TREE_SITTER_LIB_DIR set):
  python -I probe_inputs.py <repo> <solc dir> <out.json> <file:version> ...
"""
import json, os, subprocess, sys
repo, solc_dir, out = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, repo); os.chdir(repo)
from compile_repair.rules.environment import pragma_interval
from slither import Slither
rows = []
for spec in sys.argv[4:]:
    path, version = spec.rsplit(":", 1)
    raw = open(path, "rb").read()
    row = {"file": os.path.basename(path), "version": version}
    try:
        row["pragma_interval"] = pragma_interval([raw])
    except Exception as exc:
        row["pragma_interval_error"] = f"{type(exc).__name__}: {exc}"
    solc = os.path.join(solc_dir, "solc-" + version)
    row["solc_rc"] = subprocess.run([solc, "--combined-json", "abi", path], capture_output=True).returncode
    try:
        s = Slither(path, solc=solc, solc_disable_warnings=True)
        row["slither"] = "ok"; row["functions"] = sum(len(c.functions) for c in s.contracts)
    except Exception as exc:
        row["slither"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    rows.append(row); print(json.dumps(row), flush=True)
json.dump(rows, open(out, "w"), indent=1)
