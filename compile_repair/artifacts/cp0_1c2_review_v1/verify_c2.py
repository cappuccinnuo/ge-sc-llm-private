"""Independent check of CP0.1 C continuation (cp0_1_env_v2, cp0_1_compilers_v2).
Usage: verify_c2.py <repo> <claude_0116_batch.jsonl>"""
import collections, gzip, hashlib, json, os, re, sys

repo, mine_path = sys.argv[1:3]
A = os.path.join(repo, "compile_repair/artifacts")
out = collections.OrderedDict()
RX = re.compile(r"<([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+) object at 0x[0-9a-fA-F]+>")

def arch(path):
    rows = {}
    for l in gzip.open(path, "rt"):
        r = json.loads(l); rows[(r["source_sha256"], r["version"], tuple(r.get("settings") or ()))] = r
    return rows

def selfhash(r):
    return hashlib.sha256(json.dumps(r["nodes"], sort_keys=True).encode("utf8")).hexdigest()

# 1. seals
for d in ("cp0_1_env_v2", "cp0_1_compilers_v2"):
    p = os.path.join(A, d, "seal.json")
    if os.path.exists(p):
        s = json.load(open(p)); files = s.get("files", {})
        bad = [f for f, h in files.items()
               if hashlib.sha256(open(os.path.join(repo, f) if f.startswith("compile_repair/") else os.path.join(A, d, f), "rb").read()).hexdigest() != h]
        out["seal_" + d] = {"files": len(files), "mismatch": bad}

# 2. determinism run1 vs run2, self-consistency, residual addresses
r1 = arch(os.path.join(A, "cp0_1_env_v2/production_run1_node_facts_v2.jsonl.gz"))
r2 = arch(os.path.join(A, "cp0_1_env_v2/production_run2_node_facts_v2.jsonl.gz"))
out["run_rows"] = [len(r1), len(r2)]
out["run1_eq_run2_nodes"] = sum(r1[k]["nodes"] == r2.get(k, {}).get("nodes") for k in r1)
out["run1_eq_run2_sha"] = sum(r1[k].get("node_facts_v2_sha256") == r2.get(k, {}).get("node_facts_v2_sha256") for k in r1)
out["selfhash_ok"] = sum(selfhash(r) == r.get("node_facts_v2_sha256") for r in list(r1.values()) + list(r2.values()))
out["residual_object_addr"] = sum(" object at 0x" in ir for r in r1.values() for n in r["nodes"] for ir in n["ir"])
out["run_nodes"] = sum(len(r["nodes"]) for r in r1.values())

# 3. vs B archive: only canonicalised lines may differ
b = arch(os.path.join(A, "cp0_1_env_v1/production_node_facts_v2.jsonl.gz"))
same = canon_same = other = 0; changed = []
for k, r in r1.items():
    o = b.get(k)
    if o is None:
        other += 1; continue
    if o["nodes"] == r["nodes"]:
        same += 1; continue
    canon = [dict(n, ir=[RX.sub(r"<\1>", x) for x in n["ir"]]) for n in o["nodes"]]
    if sorted(json.dumps(n, sort_keys=True) for n in canon) == sorted(json.dumps(n, sort_keys=True) for n in r["nodes"]):
        canon_same += 1; changed.append(r["source_path"].split("source_code/")[-1])
    else:
        other += 1
out["vs_B"] = {"identical": same, "identical_after_canonicalising_B": canon_same, "other": other, "changed_files": changed}

# 4. vs Claude's independent 0.11.6 run (canonicalise mine)
mine = {}
for l in open(mine_path):
    m = json.loads(l)
    if m["ok"]:
        mine[(m["id"].split("@")[0], m["version"])] = collections.Counter(
            json.dumps([k, [RX.sub(r"<\1>", x) for x in ir]]) for k, ir in m["key5_ir"])
eq = df = 0
for (sha, v, st), r in r1.items():
    m = mine.get((sha, v))
    if m is None or not r["nodes"]:
        continue
    c = collections.Counter(json.dumps([n["key5"], n["ir"]]) for n in r["nodes"])
    eq += c == m; df += c != m
out["vs_claude_0116_canonical"] = {"equal": eq, "differ": df}

# 5. regression sample vs A archive
a = arch(os.path.join(A, "cp0_1_v1/node_facts_v2.jsonl.gz"))
rs = arch(os.path.join(A, "cp0_1_env_v2/regression_sample_node_facts_v2.jsonl.gz"))
out["regression_sample"] = {"rows": len(rs), "equal_to_A": sum(a.get(k, {}).get("nodes") == r["nodes"] for k, r in rs.items())}
plan = json.load(open(os.path.join(A, "cp0_1_env_v2/regression_sample_plan.json")))
out["regression_plan_keys"] = sorted(plan)[:10]

# 6. compatibility v2
cp = json.load(open(os.path.join(A, "cp0_1_compilers_v2/compatibility_plan.json")))
jobs = cp["jobs"]
out["plan_jobs"] = len(jobs)
kinds = collections.Counter((j.get("kind"), tuple(j.get("settings") or ()), j.get("expected") or j.get("expect")) for j in jobs)
out["plan_kinds"] = {str(k): v for k, v in kinds.items()}
inv = [json.loads(l) for l in open(os.path.join(A, "cp0_1_compilers_v2/compatibility_invocations.jsonl"))]
out["inv_kinds"] = dict(collections.Counter(r.get("kind") for r in inv))
neg = [(r.get("compiler", {}).get("version") or r.get("version"), os.path.basename(r.get("source_path", "")), r.get("returncode"), r.get("error_first_line"))
       for r in inv if r.get("kind") == "solc" and r.get("returncode") != 0]
out["solc_nonzero"] = neg
sl = [r for r in inv if r.get("kind") == "slither"]
out["slither"] = {"n": len(sl), "d3": sum(bool(r.get("d3")) for r in sl),
                  "with_settings": [(r["version"], os.path.basename(r["source_path"]), r.get("settings"), r.get("d3")) for r in sl if r.get("settings")]}
# original 496 jobs preserved?
v1 = json.load(open(os.path.join(A, "cp0_1_compilers_v1/compatibility_plan.json")))["jobs"]
key = lambda j: (j["version"], os.path.basename(j.get("fixture") or j.get("path") or ""), j.get("kind"))
out["v1_jobs_in_v2"] = len(set(map(key, v1)) & set(key(j) for j in jobs if not j.get("settings")))
c = json.load(open(os.path.join(A, "cp0_1_compilers_v2/compatibility.json")))
out["compat_summary"] = {k: c[k] for k in c if not isinstance(c[k], (list, dict)) or k in ("counts",)}
print(json.dumps(out, indent=1, default=str))
