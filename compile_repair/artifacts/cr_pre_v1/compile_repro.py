"""Compile-only reproduction (evidence for the CompileRepair proposal).

Step A: auto_version_solc rule (first x.y.z after `pragma solidity`, default 0.4.25), one try.
Step B: for A-failures, try every locally available solc inside the pragma interval
        (conjunctive interval, same semantics as scripts/DFG/state/stage_f/versioning.py::interval).
Bare `solc <file>`; exit code decides. No source is modified.
"""
import collections
import json
import os
import re
import subprocess
import sys

ROOT, SOLC_DIR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
BUGS = ["access_control", "arithmetic", "denial_of_service", "front_running",
        "reentrancy", "time_manipulation", "unchecked_low_level_calls"]
FIRST = re.compile(r"pragma solidity\s*(?:\^|>=|<=|~)?\s*(\d+\.\d+\.\d+)")
PRAG = re.compile(r"pragma\s+solidity\s+([^;]*);")
TERM = re.compile(r"(\^|~|>=|<=|>|<|=)?\s*(\d+)\.(\d+)\.(\d+)")
AVAIL = sorted((tuple(map(int, f[5:].split("."))) for f in os.listdir(SOLC_DIR) if f.startswith("solc-")))


def interval(src):
    exprs = [e.strip() for e in PRAG.findall(src)]
    if not exprs:
        return None
    lo, hi = (0, 0, 0), (999, 0, 0)
    for e in exprs:
        if "||" in e or re.sub(TERM, "", e).strip():
            return "unsupported"
        for m in TERM.finditer(e):
            op = m.group(1) or "="
            v = tuple(int(m.group(i)) for i in (2, 3, 4))
            nxt = (v[0], v[1], v[2] + 1)
            if op in ("=", "^", "~"):
                if op == "=":
                    up = nxt
                elif op == "~":
                    up = (v[0], v[1] + 1, 0)
                else:
                    up = (v[0] + 1, 0, 0) if v[0] else ((0, v[1] + 1, 0) if v[1] else nxt)
                lo, hi = max(lo, v), min(hi, up)
            elif op in (">", ">="):
                lo = max(lo, nxt if op == ">" else v)
            else:
                hi = min(hi, nxt if op == "<=" else v)
    return (lo, hi) if lo < hi else "empty"


def run(ver, path):
    exe = os.path.join(SOLC_DIR, "solc-%d.%d.%d" % ver)
    p = subprocess.run([exe, path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    err = p.stderr.decode("utf8", "replace")
    first = next((l for l in err.splitlines() if "Error" in l), "")
    kind = re.search(r"(\w*Error)", first)
    return p.returncode == 0, (kind.group(1) if kind else ""), first[:300]


rows = []
for bug in BUGS:
    d = os.path.join(ROOT, bug, "source_files")
    for f in sorted(x for x in os.listdir(d) if x.endswith(".sol")):
        path = os.path.join(d, f)
        src = open(path, encoding="utf8", errors="ignore").read()
        m = FIRST.findall(src)
        sel = tuple(map(int, (m[0] if m else "0.4.25").split(".")))
        r = {"class": bug, "file": f, "selected": "%d.%d.%d" % sel, "origin": "pragma" if m else "default"}
        iv = interval(src)
        r["interval"] = iv if isinstance(iv, str) or iv is None else ["%d.%d.%d" % iv[0], "%d.%d.%d" % iv[1]]
        if sel not in AVAIL:
            r["A"] = "unavailable_here"
        else:
            ok, kind, msg = run(sel, path)
            r["A"] = "ok" if ok else "fail"
            r["A_error_kind"], r["A_error"] = kind, msg
        if r["A"] != "ok" and isinstance(iv, tuple):
            cands = [v for v in AVAIL if iv[0] <= v < iv[1] and v != sel]
            r["B_candidates"] = len(cands)
            r["B_ok_versions"] = ["%d.%d.%d" % v for v in cands if run(v, path)[0]]
        rows.append(r)

json.dump(rows, open(OUT, "w"), indent=1)
summ = collections.defaultdict(collections.Counter)
for r in rows:
    key = r["class"]
    summ[key]["files"] += 1
    summ[key]["A_" + r["A"]] += 1
    if r["A"] != "ok":
        summ[key]["B_recovered" if r.get("B_ok_versions") else "B_not_recovered"] += 1
for k, v in summ.items():
    print(k, dict(v))
