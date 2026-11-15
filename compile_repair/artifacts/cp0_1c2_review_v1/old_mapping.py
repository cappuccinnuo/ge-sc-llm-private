import os, sys, json
from slither import Slither
path, solc = sys.argv[1], sys.argv[2]
sl = Slither(path, solc=solc)
for c in sl.contracts:
    for f in c.functions_and_modifiers_declared:
        for n in f.nodes:
            sm = n.source_mapping
            d = sm if isinstance(sm, dict) else {"filename_absolute": getattr(getattr(sm, "filename", None), "absolute", None), "start": getattr(sm, "start", None), "filename_used": getattr(getattr(sm, "filename", None), "used", None)}
            print(json.dumps({k: d.get(k) for k in ("filename_absolute", "filename_used", "filename_relative", "start")}), os.getcwd())
            break
        break
