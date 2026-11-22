"""What solc actually reports for the CP4 operators that yielded no samples, and for
their corrected forms. Usage: python3 -I probe_operator_messages.py <repo> <solc dir> <fixtures dir> <out.json>"""
import json, os, subprocess, sys
repo, solc_dir, fx, out = sys.argv[1:5]
sys.path.insert(0, repo)
from compile_repair.toolchain.solc import parse_diagnostics, classify_diagnostic
VERSIONS = ["0.4.24", "0.5.17", "0.8.0", "0.8.38"]
rows = []
for name in sorted(os.listdir(fx)):
    path = os.path.join(fx, name)
    src = open(path, "rb").read()
    for v in VERSIONS:
        r = subprocess.run([os.path.join(solc_dir, "solc-" + v), "--combined-json", "abi", name],
                           cwd=fx, capture_output=True, text=True, errors="replace")
        lines = [l for l in r.stderr.splitlines() if l.strip()]
        try:
            diags = [classify_diagnostic(d, src) for d in parse_diagnostics(r.stderr)]
            cats = sorted({d["category"] for d in diags if d.get("failure")})
        except Exception as exc:
            cats = ["<classifier error: %s>" % type(exc).__name__]
        what = next((l.split("what: ", 1)[1] for l in lines if "std::exception::what" in l), None)
        first = next((l for l in lines if "Error" in l or "error" in l), lines[0] if lines else None)
        rows.append({"fixture": name, "version": v, "rc": r.returncode, "first_error_line": first,
                     "exception_what": what, "module_categories": cats})
        print(name, v, r.returncode, cats, (what or first or "")[:90])
json.dump(rows, open(out, "w"), indent=1)
