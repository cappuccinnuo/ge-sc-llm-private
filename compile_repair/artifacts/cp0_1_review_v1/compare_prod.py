"""Compare Codex-code D3 batch outputs (production candidates) with the CP0.1 0.8.0 archive.
Usage: compare_prod.py <repo> <batch.jsonl> [<batch2.jsonl> ...]"""
import collections, gzip, json, os, sys

repo = sys.argv[1]
arch = {}
for l in gzip.open(os.path.join(repo, "compile_repair/artifacts/cp0_1_v1/node_facts_v2.jsonl.gz"), "rt"):
    r = json.loads(l)
    arch[(r["source_sha256"], r["version"])] = r["nodes"]
res = collections.OrderedDict()
for path in sys.argv[2:]:
    st = collections.Counter(); extra = collections.Counter(); missing = collections.Counter()
    fails = []; files_struct_diff = 0; secs = 0.0
    for l in open(path):
        r = json.loads(l)
        secs += r["seconds"]
        st["rows"] += 1
        if not r["ok"]:
            st["exception"] += 1; fails.append([r["id"][:12], r["version"], r["error"][:120]]); continue
        st["d3_pass"] += r["d3_a"] and r["d3_b"]
        st["d3_a_fail"] += not r["d3_a"]; st["d3_b_fail"] += not r["d3_b"]
        st["top_level_nonzero"] += r["counts"].get("top_level_functions", 0) > 0
        base = arch[(r["id"].split("@")[0], r["version"])]
        a = collections.Counter(json.dumps(n["key5"][:4]) for n in base)
        b = collections.Counter(json.dumps(k[:4]) for k, ir in r["key5_ir"])
        if a != b:
            files_struct_diff += 1
            for k, v in (b - a).items():
                kk = json.loads(k); extra[(kk[2], "slitherConstructor" in kk[1])] += v
            for k, v in (a - b).items():
                kk = json.loads(k); missing[(kk[2], "slitherConstructor" in kk[1])] += v
        ai = collections.Counter(json.dumps([n["key5"], n["ir"]]) for n in base)
        bi = collections.Counter(json.dumps([k, ir]) for k, ir in r["key5_ir"])
        st["key5_ir_equal"] += ai == bi
        st["key5_equal"] += collections.Counter(json.dumps(n["key5"]) for n in base) == \
            collections.Counter(json.dumps(k) for k, ir in r["key5_ir"])
    res[os.path.basename(path)] = {"stats": dict(st), "structure_differs_files_key4": files_struct_diff,
        "extra_nodes_by_type_synthetic": {str(k): v for k, v in extra.most_common()},
        "missing_nodes_by_type_synthetic": {str(k): v for k, v in missing.most_common()},
        "exceptions": fails, "slither_seconds_total": round(secs, 1)}
print(json.dumps(res, indent=1))
