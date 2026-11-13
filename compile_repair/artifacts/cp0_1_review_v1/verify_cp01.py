"""Independent check of CP0.1 (cp0_1_v1) against Claude's own Slither 0.8.0 dumps
and against the raw journals. Usage: verify_cp01.py <repo> <run_dir> <nodetype_map.json>"""
import collections, glob, gzip, hashlib, json, os, sys

REPO, RUN, NT = sys.argv[1:4]
A = os.path.join(REPO, "compile_repair/artifacts/cp0_1_v1")
V2 = os.path.join(REPO, "compile_repair/artifacts/cp0_v2")
out = collections.OrderedDict()
name_of = {v: k for k, v in json.load(open(NT)).items()}   # str(NodeType) -> enum name

# seal integrity
seal = json.load(open(os.path.join(A, "seal.json")))
out["seal_files_ok"] = all(hashlib.sha256(open(os.path.join(A, f), "rb").read()).hexdigest() == h
                           for f, h in seal["files"].items())

arch = [json.loads(l) for l in gzip.open(os.path.join(A, "node_facts_v2.jsonl.gz"), "rt")]
out["archive_rows"] = len(arch)
out["archive_keys"] = sorted(k for k in arch[0] if k != "nodes")

def recompute_hash(nodes):
    return hashlib.sha256(json.dumps(nodes, sort_keys=True).encode("utf8")).hexdigest()

# each archive row: does its stored sha equal sha of its nodes (CP0-style encoding)?
eq = sum(recompute_hash(r["nodes"]) == r["node_facts_v2_sha256"] for r in arch)
out["archive_hash_self_consistent"] = eq

# key5 recomputed independently from Claude's 0.8.0 node_dump (Slither node order)
def mine(tag):
    rows = {}
    for f in glob.glob(os.path.join(RUN, "out_%s_*.jsonl" % tag)):
        for line in open(f):
            r = json.loads(line)
            if not r["ok"]:
                continue
            c = collections.Counter()
            for contract, fn, seq in r["funcs"]:
                seen = collections.Counter()
                for t, start, ir in seq:
                    t = name_of[t]
                    seen[(t, start)] += 1
                    c[json.dumps([[contract, fn, t, start, seen[(t, start)]], ir])] += 1
            rows[(r["id"].split("@")[0], r["version"])] = c
    return rows

my = mine("s080_sel")
my.update(mine("s080_ends"))
idk = [k for k in out["archive_keys"] if k in ("source_sha256", "version", "compiler_version")]
match = diff = absent = 0
examples = []
for r in arch:
    key = (r.get("source_sha256"), r.get("version") or r.get("compiler_version"))
    m = my.get(key)
    if m is None:
        absent += 1
        continue
    c = collections.Counter(json.dumps([n["key5"], n["ir"]]) for n in r["nodes"])
    if c == m:
        match += 1
    else:
        diff += 1
        if len(examples) < 3:
            examples.append([key, list((c - m).items())[:2], list((m - c).items())[:2]])
out["key5_ir_equal_to_claude_dump"] = match
out["key5_ir_differs"] = diff
out["archive_rows_not_in_claude_dump"] = absent
out["examples"] = examples

# per-row duplicates of key5 (must be 0)
out["rows_with_duplicate_key5"] = sum(
    any(v > 1 for v in collections.Counter(json.dumps(n["key5"]) for n in r["nodes"]).values()) for r in arch)

# journals vs summary
inv = [json.loads(l) for l in open(os.path.join(A, "invocations.jsonl"))]
k = collections.Counter(r.get("kind") for r in inv)
out["invocation_kinds"] = dict(k)
sl = [r for r in inv if r.get("kind") == "slither"]
out["slither_constructed"] = sum(bool(r.get("constructed")) for r in sl)
out["slither_d3"] = sum(bool(r.get("d3")) for r in sl)
out["slither_d3_b_true"] = sum(bool(r.get("d3_b")) for r in sl)
out["slither_profiles"] = dict((str(k), v) for k, v in collections.Counter((r.get("profile"), r.get("slither_version"), r.get("crytic_compile_version")) for r in sl).items())
out["coverage_formats"] = dict(collections.Counter(a["format"] for r in sl for a in (r.get("contract_coverage") or {}).get("asts", [])))
out["coverage_expected_empty"] = sum(not (r.get("contract_coverage") or {}).get("expected") for r in sl)
out["solc_rc0"] = sum(r.get("returncode") == 0 for r in inv if r.get("kind") == "solc")

# selections used == cp0_v2 selection.ascending / lowest / highest
recon = json.load(open(os.path.join(V2, "recon.json")))
sha_of = {x["path"]: x["sha256"] for x in recon["inputs"]}
cv2 = {}
for l in open(os.path.join(V2, "cross_version.jsonl")):
    r = json.loads(l); r["source_sha256"] = sha_of[r["path"]]; cv2[r["path"]] = r
want = set()
for x in recon["inputs"]:
    want.add((x["sha256"], x["selection"]["ascending"]))
for r in cv2.values():
    want.add((r.get("source_sha256"), r["low"]))
    want.add((r.get("source_sha256"), r.get("high")))
got = set((r.get("source_sha256"), r.get("version")) for r in sl)
out["slither_pairs"] = len(got)
out["cp0_v2_pairs_expected"] = len(want)
out["pairs_missing"] = len(want - got)
out["pairs_extra"] = len(got - want)

# CP0 projection vs cp0_v2 node_facts_sha256
old = {}
for l in open(os.path.join(V2, "invocations.jsonl")):
    r = json.loads(l)
    if r.get("kind") == "slither" and r.get("scope") == "mando":
        old[(r["source_sha256"], r.get("version"))] = r.get("node_facts_sha256")
pe = [old.get((r["source_sha256"], r["version"])) == r.get("cp0_projection_sha256") for r in sl if r.get("cp0_projection_sha256")]
out["cp0_projection_rows"] = len(pe)
out["cp0_projection_equal"] = sum(pe)
print(json.dumps(out, indent=1, default=str))
