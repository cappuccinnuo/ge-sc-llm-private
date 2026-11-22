"""Independent oracle: module interval membership vs real solc acceptance.
Usage (production env, repo root): python -I oracle_pragma.py <repo> <solc dir> <out.json>
Uses every solc-<version> binary present in <solc dir> between 0.4.12 and 0.8.x."""
import glob, json, os, re, subprocess, sys, tempfile
repo, solc_dir, out = sys.argv[1:4]
sys.path.insert(0, repo); os.chdir(repo)
from compile_repair.rules.environment import pragma_interval
from scripts.DFG.models import Unsupported
vt = lambda v: tuple(map(int, v.split(".")))
versions = sorted({os.path.basename(p)[5:] for p in glob.glob(os.path.join(solc_dir, "solc-0.*"))
                   if re.fullmatch(r"solc-0\.\d+\.\d+", os.path.basename(p))}, key=vt)
versions = [v for v in versions if (0, 4, 12) <= vt(v) < (0, 9, 0)]
EXPR = [">=0.4.x", "<0.5", "^0.4", "~0.5", "0.4.*", ">0.4", "<=0.5", ">=0.4 <0.6", "0.*", "^0.5.x",
        "~0.4.x", "0.5", ">=0.4.24 <0.5", "=0.4", "^0.4.*", ">=0.5.x <=0.5.10", "0.x", "^0", "~0", ">0.4.x"]
tmp = tempfile.mkdtemp(); path = os.path.join(tmp, "p.sol")
rows, mismatches = [], []
for e in EXPR:
    src = ("pragma solidity %s;\ncontract A {}\n" % e).encode()
    try:
        lo, hi = pragma_interval([src]); mod = [lo, hi]
    except Unsupported as exc:
        lo = hi = None; mod = str(exc)
    open(path, "wb").write(src)
    for v in versions:
        r = subprocess.run([os.path.join(solc_dir, "solc-" + v), "--combined-json", "abi", path], capture_output=True, text=True)
        solc_ok = r.returncode == 0
        inside = lo is not None and lo <= vt(v) < hi
        why = None if solc_ok else ("version" if "requires different compiler version" in r.stderr else "syntax")
        row = {"expression": e, "version": v, "solc_ok": solc_ok, "solc_reject": why, "module": mod, "inside": inside}
        rows.append(row)
        if inside != solc_ok:
            mismatches.append(row)
summary = {"versions": versions, "expressions": len(EXPR), "pairs": len(rows),
           "mismatches": len(mismatches), "mismatch_rows": mismatches}
json.dump({"summary": summary, "rows": rows}, open(out, "w"), indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != "mismatch_rows"}))
for m in mismatches[:30]: print(m)
