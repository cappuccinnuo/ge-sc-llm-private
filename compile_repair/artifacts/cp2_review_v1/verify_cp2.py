"""Independent check of CP2 production stores. Usage: verify_cp2.py <repo> <store1> <store2> <out.json>"""
import collections, gzip, hashlib, json, os, sys
repo, s1, s2, outp = sys.argv[1:5]
A = os.path.join(repo, "compile_repair/artifacts")
H = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
out = collections.OrderedDict()
for name, s in (("store1", s1), ("store2", s2)):
    seal = json.load(open(os.path.join(s, "seal.json")))
    files = seal.get("files") or {}
    bad = [f for f, v in files.items() if H(os.path.join(s, f)) != (v["sha256"] if isinstance(v, dict) else v)]
    out[name + "_seal"] = {"files": len(files), "mismatch": len(bad)}
units = sorted(os.listdir(os.path.join(s1, "units")))
recon = json.load(open(os.path.join(A, "cp0_v2/recon.json")))
by_sha = collections.defaultdict(list)
for x in recon["inputs"]:
    by_sha[x["sha256"]].append(x)
arch = {}
for l in gzip.open(os.path.join(A, "cp0_1_env_v2/production_run1_node_facts_v2.jsonl.gz"), "rt"):
    r = json.loads(l); arch[(r["source_sha256"], r["version"])] = r["nodes"]
st = collections.Counter(); edges = collections.Counter(); calls = collections.Counter(); unrep = []; diffs = []
lib_as_high = 0; dangling = 0; prov = collections.Counter()
for u in units:
    r1 = json.load(open(os.path.join(s1, "units", u, "result.json")))
    r2 = json.load(open(os.path.join(s2, "units", u, "result.json")))
    st[r1["status"]] += 1
    st["status_version_equal"] += (r1["status"], r1["selected_version"]) == (r2["status"], r2["selected_version"])
    rec = json.load(open(os.path.join(s1, "units", u, "input_record.json")))
    if r1["status"] != "success":
        unrep.append((os.path.basename(rec["path"]), r1["reason"])); continue
    g1p = os.path.join(s1, "units", u, "graph.json"); g2p = os.path.join(s2, "units", u, "graph.json")
    st["graph_bytes_equal"] += open(g1p, "rb").read() == open(g2p, "rb").read()
    g = json.load(open(g1p))
    keys = {json.dumps(n["key5"]) for n in g["nodes"]}
    st["nodes"] += len(g["nodes"]); st["edges"] += len(g["cfg_edges"]); st["calls"] += len(g["calls"])
    for n in g["nodes"]:
        prov[n["provenance"] if isinstance(n["provenance"], str) else "tagged"] += 1
    for e in g["cfg_edges"]:
        edges[e["kind"]] += 1
        dangling += json.dumps(e["source"]) not in keys or json.dumps(e["target"]) not in keys
    for c in g["calls"]:
        calls[c["kind"]] += 1
        lib_as_high += c["operation"] == "LibraryCall" and c["kind"] != "library"
        dangling += json.dumps(c["node"]) not in keys
    # same-version comparison with cp0_1_env_v2 production archive
    sha = rec["sha256"]; v = r1["selected_version"]
    base = arch.get((sha, v))
    if base is None:
        st["no_same_version_archive"] += 1; diffs.append((os.path.basename(rec["path"]), v)); continue
    a = collections.Counter(json.dumps([n["key5"], n["ir"]]) for n in base)
    b = collections.Counter(json.dumps([n["key5"], n["ir"]]) for n in g["nodes"])
    st["same_version_nodes_equal"] += a == b
out["stats"] = dict(st); out["edge_kinds"] = dict(edges); out["call_kinds"] = dict(calls)
out["library_classified_as_high_level"] = lib_as_high; out["dangling_refs"] = dangling
out["provenance"] = dict(prov); out["unrepaired"] = unrep; out["no_same_version_archive"] = diffs
json.dump(out, open(outp, "w"), indent=1); print(json.dumps(out, indent=1))
