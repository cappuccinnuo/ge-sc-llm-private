"""D16 feature probe: Slither construction + D3-style mapping check on one file."""
import json
import os
import sys

from slither import Slither

path, solc = sys.argv[1], sys.argv[2]
try:
    sl = Slither(path, solc=solc)
    nodes = missing = 0
    for c in sl.contracts:
        for f in c.functions_and_modifiers_declared:
            for n in f.nodes:
                nodes += 1
                sm = n.source_mapping or {}
                fn = sm.get("filename_absolute") if isinstance(sm, dict) else getattr(sm, "filename", None)
                fn = getattr(fn, "absolute", fn)
                start = sm.get("start") if isinstance(sm, dict) else getattr(sm, "start", None)
                if not fn or os.path.realpath(fn) != os.path.realpath(path) or start is None:
                    missing += 1
    free = len(getattr(sl, "functions_top_level", []) or [])
    print(json.dumps({"file": os.path.basename(path), "ok": True, "nodes": nodes, "unmapped": missing,
                      "top_level_functions": free}))
except Exception as e:
    print(json.dumps({"file": os.path.basename(path), "ok": False,
                      "error": type(e).__name__ + ": " + (str(e).splitlines() or [""])[0][:120]}))
