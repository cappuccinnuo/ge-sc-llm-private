import hashlib, json, os, sys
repo = sys.argv[1]; sys.path.insert(0, repo); os.chdir(repo)
from pathlib import Path
from compile_repair.core.model import Compiler
from compile_repair.toolchain.solc import command
recon = json.load(open("compile_repair/artifacts/cp0_v2/recon.json"))
plan = json.load(open("compile_repair/artifacts/cp0_1_compilers_v2/compatibility_plan.json"))["jobs"]
items = [(x["path"], x["selection"]["ascending"]) for x in recon["inputs"]]
items += [(j.get("fixture") or j.get("path"), j["version"]) for j in plan]
def old(source, cwd):
    return source[len(cwd) + 1:] if source.startswith(cwd) else source
eq = diff = 0; ex = []
cwd = str(Path.cwd().resolve())
for p, v in items:
    c = Compiler(v, "/nonexistent/solc-" + v, "0" * 64)
    a = command(p, c, cwd=cwd)
    src = str(Path(p).resolve())
    b = a[:4] + (["--allow-paths", ".", old(src, cwd)] if a[4:5] == ["--allow-paths"] else [])
    b += a[len(b):] if len(a) > 7 else []
    if a == b: eq += 1
    else:
        diff += 1; ex.append((p, a[-1], b[-1]))
print(json.dumps({"items": len(items), "equal": eq, "differ": diff, "examples": ex[:3]}))
