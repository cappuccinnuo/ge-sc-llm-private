"""Run input_format_evidence over files and directories.
Usage: python3 -I probe_language.py <repo> <out.json> <path> ..."""
import glob, json, os, sys
repo, out, paths = sys.argv[1], sys.argv[2], sys.argv[3:]
sys.path.insert(0, repo)
from compile_repair.toolchain.project import input_format_evidence
rows = []
for p in paths:
    files = sorted(glob.glob(os.path.join(p, "**", "*.*"), recursive=True)) if os.path.isdir(p) else [p]
    for f in files:
        if not f.endswith((".sol", ".vy")):
            continue
        lang, wrapper = input_format_evidence(open(f, "rb").read())
        rows.append({"file": os.path.relpath(f, repo) if f.startswith(repo) else os.path.basename(f),
                     "status": lang["status"], "basis": lang.get("basis"), "language": lang.get("language"),
                     "wrapper": None if wrapper is None else {k: wrapper[k] for k in wrapper if k != "source_names"}})
json.dump(rows, open(out, "w"), indent=1)
import collections
print(collections.Counter((os.path.dirname(r["file"]).split("/")[0] if "/" in r["file"] else "-", r["status"]) for r in rows))
