"""0.4.x `(bool x, ) = <call>;` crashes production Slither; test the single-line rewrite `bool x = <call>;`.
Writes rewritten copies to a temp dir only. Usage: python -I probe_slither_compat.py <solc dir> <out.json> <versions,> <file> ..."""
import json, os, re, subprocess, sys, tempfile
from slither import Slither
solc_dir, out, versions, files = sys.argv[1], sys.argv[2], sys.argv[3].split(","), sys.argv[4:]
PAT = re.compile(rb"\(\s*bool\s+(\w+)\s*,\s*\)\s*=\s*([^;\n]*\.call[^;\n]*);")
rows = []
tmp = tempfile.mkdtemp()
for f in files:
    raw = open(f, "rb").read()
    new, n = PAT.subn(lambda m: b"bool " + m.group(1) + b" = " + m.group(2) + b";", raw)
    g = os.path.join(tmp, os.path.basename(f)); open(g, "wb").write(new)
    for v in versions:
        solc = os.path.join(solc_dir, "solc-" + v)
        row = {"file": os.path.basename(f), "version": v, "rewrites": n}
        for tag, path in (("original", f), ("rewritten", g)):
            row[tag + "_solc_rc"] = subprocess.run([solc, "--combined-json", "abi", path], capture_output=True).returncode
            try:
                s = Slither(path, solc=solc, solc_disable_warnings=True)
                row[tag + "_slither"] = "ok:%d" % sum(len(c.functions) for c in s.contracts)
            except Exception as exc:
                row[tag + "_slither"] = type(exc).__name__
        rows.append(row); print(json.dumps(row), flush=True)
json.dump(rows, open(out, "w"), indent=1)
