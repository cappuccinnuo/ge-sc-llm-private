"""Compare CP2.4 environment.py with CP2.3 (git show 76a2cc810:compile_repair/rules/environment.py).
Usage (production env, repo root, TREE_SITTER_LIB_DIR):
  python -I verify_cp24.py <repo> <env_cp23.py> <list.json> <unpacked v5 store> <out.json> <dir> ..."""
import glob, importlib.util, json, os, sys
repo, old_path, list_json, store, out, dirs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6:]
sys.path.insert(0, repo); os.chdir(repo)
from compile_repair.rules import environment as new
spec = importlib.util.spec_from_file_location("env_cp23", old_path)
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
vt = lambda v: tuple(map(int, v.split(".")))
versions = sorted((v for v in json.load(open(list_json))["releases"] if (0, 4, 12) <= vt(v) < (0, 9, 0)), key=vt)

def run(fn):
    try:
        return ["ok", repr(fn())]
    except Exception as exc:
        return ["raise", type(exc).__name__, str(exc)]

rows = []
for d in dirs:
    for f in sorted(glob.glob(os.path.join(d, "**", "*.sol"), recursive=True)):
        raw = open(f, "rb").read()
        r = {"file": os.path.relpath(f, repo),
             "new": run(lambda: new.pragma_interval([raw])), "old": run(lambda: old.pragma_interval([raw])),
             "new_patches": run(lambda: new.pragma_patches(raw)), "old_patches": run(lambda: old.pragma_patches(raw))}
        rows.append(r)
summary = json.load(open(os.path.join(store, "summary.json")))
plans = {"inputs": 0, "equal": 0, "different": []}
for sup, unit in zip(summary["supplied"], summary["units"]):
    rec = json.load(open(os.path.join(store, "units", unit["unit_id"], "input_record.json")))
    raw = open(sup["path"].split("ge-sc-llm-compile/")[1], "rb").read()
    for order in ("ascending", "descending"):
        a = run(lambda: new.make_plan([raw], versions, rec["known_version"], "mando", order))
        b = run(lambda: old.make_plan([raw], versions, rec["known_version"], "mando", order))
        plans["inputs"] += 1
        if a == b:
            plans["equal"] += 1
        else:
            plans["different"].append([unit["unit_id"], order, a, b])
res = {"versions": len(versions),
       "files": len(rows),
       "old_ok": sum(r["old"][0] == "ok" for r in rows),
       "interval_equal_where_old_ok": sum(r["new"] == r["old"] for r in rows if r["old"][0] == "ok"),
       "patches_equal_where_old_ok": sum(r["new_patches"] == r["old_patches"] for r in rows if r["old_patches"][0] == "ok"),
       "old_patches_ok": sum(r["old_patches"][0] == "ok" for r in rows),
       "differences": [r for r in rows if r["new"] != r["old"] or r["new_patches"] != r["old_patches"]],
       "make_plan_mando": plans}
json.dump(res, open(out, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ("differences", "make_plan_mando")}),
      json.dumps({k: plans[k] if k != "different" else len(plans[k]) for k in plans}))
for r in res["differences"]:
    print(r["file"], "| new", r["new"][:3], "| old", r["old"][:3])
