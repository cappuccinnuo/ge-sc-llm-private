import hashlib, json, os, sys
repo, solc_dir, out, *files = sys.argv[1:]
sys.path.insert(0, repo)
from compile_repair.core.model import Compiler, CompilationUnit, SourceFile
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
comps = {}
for f in os.listdir(solc_dir):
    if f.startswith("solc-"):
        p = os.path.join(solc_dir, f); v = f[5:]
        if v.startswith(("0.4.", "0.5.")):
            comps[v] = Compiler(v, p, hashlib.sha256(open(p, "rb").read()).hexdigest())
store = ArtifactStore(out)
with store.journal("invocations.jsonl") as j:
    for i, f in enumerate(files, 1):
        raw = open(f, "rb").read()
        unit = CompilationUnit("u%02d" % i, (SourceFile(f, hashlib.sha256(raw).hexdigest(), raw, "file"),), None, None)
        r = repair_unit(unit, comps, store, j)
        prov = r.provenance[f]
        print(json.dumps({"file": os.path.basename(f), "status": r.status, "reason": r.reason, "selected": r.selected_version,
                          "flags": r.flags, "override": r.plan.override if r.plan else None,
                          "interval": r.plan.effective_interval if r.plan else None, "origin": r.plan.origin if r.plan else None,
                          "attempted": [a["version"] for a in r.attempts][:6]}, default=str))
        nodes = os.path.join(out, "units", unit.unit_id, "nodes.json")
        if os.path.exists(nodes):
            nd = json.load(open(nodes))["nodes"]
            from collections import Counter
            print("   provenance", dict(Counter(n["provenance"] if isinstance(n["provenance"], str) else json.dumps(n["provenance"]) for n in nd)))
        for name in ("pragma_overridden.sol", "input.sol"):
            p = os.path.join(out, "units", unit.unit_id, name)
            if os.path.exists(p):
                b = open(p, "rb").read(); print("  ", name, len(b) == len(raw), b[:60])
