"""Read-only structure statistics for DAppSCAN-source/contracts (evidence only)."""
import collections
import json
import os
import re
import sys

ROOT = sys.argv[1]
IMPORT = re.compile(r'^\s*import\s+[^;]*?["\']([^"\']+)["\']', re.M)
PRAGMA = re.compile(r"pragma\s+solidity\s+([^;]*);")
FIRST = re.compile(r"(\d+)\.(\d+)\.(\d+)")
CFG = ("hardhat.config.js", "hardhat.config.ts", "truffle-config.js", "truffle.js", "foundry.toml",
       "package.json", "remappings.txt", "brownie-config.yaml")

projects = sorted(d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, d)))
st = collections.Counter()
minors = collections.Counter()
imp_kind = collections.Counter()
per_proj = []
for p in projects:
    base = os.path.join(ROOT, p)
    sols, cfgs, nm = [], set(), False
    for dp, dn, fn in os.walk(base):
        if "node_modules" in dp.split(os.sep):
            nm = True
            continue
        for f in fn:
            if f.endswith(".sol"):
                sols.append(os.path.join(dp, f))
            if f in CFG:
                cfgs.add(f)
    files = set(os.path.relpath(s, base) for s in sols)
    unresolved = 0
    n_imp = 0
    for s in sols:
        src = open(s, encoding="utf8", errors="ignore").read()
        m = PRAGMA.findall(src)
        if m:
            v = FIRST.search(m[0])
            minors["%s.%s" % (v.group(1), v.group(2)) if v else "unparsed"] += 1
        else:
            minors["none"] += 1
        for imp in IMPORT.findall(src):
            n_imp += 1
            if imp.startswith("."):
                target = os.path.normpath(os.path.join(os.path.dirname(s), imp))
                if os.path.exists(target):
                    imp_kind["relative_found"] += 1
                else:
                    imp_kind["relative_missing"] += 1
                    unresolved += 1
            else:
                pkg = imp.split("/")[0] if not imp.startswith("@") else "/".join(imp.split("/")[:2])
                imp_kind["package:" + pkg if pkg.startswith("@") or pkg in ("openzeppelin-solidity", "zeppelin-solidity") else "bare_other"] += 1
                unresolved += 1
    st["projects"] += 1
    st["sol_files"] += len(sols)
    st["projects_with_imports"] += n_imp > 0
    st["projects_with_node_modules_dir"] += nm
    for c in cfgs:
        st["cfg:" + c] += 1
    st["projects_without_any_cfg"] += not cfgs
    per_proj.append({"project": p, "sol": len(sols), "imports": n_imp, "unresolved_imports_static": unresolved,
                     "configs": sorted(cfgs), "node_modules": nm})
st["projects_with_unresolved_static_imports"] = sum(x["unresolved_imports_static"] > 0 for x in per_proj)
out = {"summary": dict(st), "pragma_minor_of_first_version": dict(minors.most_common()),
       "import_kinds_top": dict(imp_kind.most_common(25)), "projects": per_proj}
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(json.dumps({k: out[k] for k in ("summary", "pragma_minor_of_first_version", "import_kinds_top")}, indent=1))
