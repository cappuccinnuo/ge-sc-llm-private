"""Per-candidate solc outcome for the three MANDO Slither-side failures (all ^0.4.0).
Usage: python3 -I probe_mando_versions.py <repo> <solc dir> <out.json>"""
import json, os, subprocess, sys
repo, solc_dir, out = sys.argv[1:4]
D = os.path.join(repo, "experiments/ge-sc-data/source_code/reentrancy/source_files")
V = ["0.4.%d" % i for i in range(12, 27)]
rows = []
for name in ("reentrancy_bonus", "reentrancy_cross_function", "reentrancy_insecure"):
    for v in V:
        r = subprocess.run([os.path.join(solc_dir, "solc-" + v), "--combined-json", "abi", os.path.join(D, name + ".sol")], capture_output=True, text=True)
        first = next((l for l in r.stderr.splitlines() if "Error" in l), None)
        rows.append({"file": name + ".sol", "version": v, "rc": r.returncode, "first_error": first and first.split("Error: ", 1)[-1]})
json.dump(rows, open(out, "w"), indent=1)
for name in sorted({r["file"] for r in rows}):
    print(name, [(r["version"], r["rc"]) for r in rows if r["file"] == name])
