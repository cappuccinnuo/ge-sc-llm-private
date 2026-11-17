"""Compare CP2.3 pragma_interval/pragma_patches with the frozen interval() and with the
pre-CP2.3 implementation (git show 361772f74:compile_repair/rules/environment.py > <old.py>).
Usage (production env, repo root, TREE_SITTER_LIB_DIR): python -I verify_equivalence.py <repo> <old.py> <out.json> <dir> ..."""
import glob, importlib.util, json, os, sys
repo, old_path, out, dirs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
sys.path.insert(0, repo); os.chdir(repo)
from compile_repair.rules import environment as new
from scripts.DFG.frontend import parse
from scripts.DFG.state.stage_f.versioning import interval as frozen
spec = importlib.util.spec_from_file_location("env_old", old_path)
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)

def run(fn):
    try:
        return ["ok", repr(fn())]
    except Exception as exc:
        return ["raise", type(exc).__name__]

rows = []
for d in dirs:
    for f in sorted(glob.glob(os.path.join(d, "**", "*.sol"), recursive=True)):
        raw = open(f, "rb").read()
        r = {"file": os.path.relpath(f, repo)}
        r["new"] = run(lambda: new.pragma_interval([raw]))
        r["old"] = run(lambda: old.pragma_interval([raw]))
        r["frozen"] = run(lambda: frozen(raw.decode("utf8"), parse(raw.decode("utf8")).root_node))
        r["new_patches"] = run(lambda: [(p.start, p.end) for p in new.pragma_patches(raw)])
        r["old_patches"] = run(lambda: [(p.start, p.end) for p in old.pragma_patches(raw)])
        r["old_usable"] = r["old"][0] == "ok" or r["old"][1] == "Unsupported" and r["frozen"][0] == "raise" and r["frozen"][1] == "Unsupported" and r["old_patches"][0] == "ok"
        r["interval_equal_old"] = r["new"] == r["old"]
        r["patches_equal_old"] = r["new_patches"] == r["old_patches"]
        rows.append(r)
summary = {"files": len(rows),
           "old_path_ok": sum(r["old"][0] == "ok" for r in rows),
           "interval_equal_where_old_ok": sum(r["interval_equal_old"] for r in rows if r["old"][0] == "ok"),
           "patches_equal_where_old_ok": sum(r["patches_equal_old"] for r in rows if r["old_patches"][0] == "ok"),
           "old_patches_ok": sum(r["old_patches"][0] == "ok" for r in rows),
           "differences": [r for r in rows if not (r["interval_equal_old"] and r["patches_equal_old"])]}
json.dump({"summary": summary, "rows": rows}, open(out, "w"), indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != "differences"}))
for r in summary["differences"]:
    print(json.dumps({k: r[k] for k in ("file", "new", "old", "frozen", "new_patches", "old_patches")}))
