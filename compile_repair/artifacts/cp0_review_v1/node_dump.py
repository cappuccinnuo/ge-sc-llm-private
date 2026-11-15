"""Dump Slither nodes in Slither's own order, per declared function/modifier and top-level function.

Usage: python node_dump.py <jobs.jsonl> <solc_dir> <out.jsonl> <worker_index> <worker_count>
Each job: {"id", "path", "version"}. Output rows carry the CP0 fingerprint hash so the
run can be checked against Codex's invocations.jsonl (node_facts_sha256).
"""
import hashlib
import json
import os
import sys

from slither import Slither

jobs_path, solc_dir, out_path, wi, wn = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])


def smap(n):
    sm = n.source_mapping
    if isinstance(sm, dict):
        return sm.get("filename_absolute"), sm.get("start"), sm.get("length")
    fn = getattr(sm, "filename", None)
    return getattr(fn, "absolute", None), getattr(sm, "start", None), getattr(sm, "length", None)


with open(out_path, "w") as out:
    for i, line in enumerate(open(jobs_path)):
        if i % wn != wi:
            continue
        job = json.loads(line)
        rec = {"id": job["id"], "path": job["path"], "version": job["version"]}
        try:
            sl = Slither(job["path"], solc=os.path.join(solc_dir, "solc-" + job["version"]))
            funcs, cp0_rows, unmapped = [], [], 0
            for c in sl.contracts:
                for f in c.functions_and_modifiers_declared:
                    seq = []
                    for n in f.nodes:
                        fn, start, length = smap(n)
                        unmapped += (not fn) or start is None
                        ir = [str(x) for x in n.irs]
                        seq.append([str(n.type), start, ir])
                        cp0_rows.append({"key4": [c.name, f.full_name, str(n.type), start], "ir": ir, "length": length})
                    funcs.append([c.name, f.full_name, seq])
            top = []
            for cu in sl.compilation_units:
                for f in getattr(cu, "functions_top_level", []) or []:
                    top.append([f.full_name, len(f.nodes)])
            cp0_rows = sorted(cp0_rows, key=lambda r: json.dumps(r, sort_keys=True))
            rec.update({"ok": True, "funcs": funcs, "top_level": top, "unmapped": unmapped,
                        "cp0_sha": hashlib.sha256(json.dumps(cp0_rows, sort_keys=True).encode("utf8")).hexdigest()})
        except Exception as e:
            rec.update({"ok": False, "error": type(e).__name__ + ": " + (str(e).splitlines() or [""])[0][:160]})
        out.write(json.dumps(rec) + "\n")
        out.flush()
