"""Independent check of cp2_desc_v1 against cr_store_mando_v3 (both unpacked)."""
import collections, hashlib, json, os, sys
asc, desc, out = sys.argv[1], sys.argv[2], sys.argv[3]

def seal(root):
    s = json.load(open(os.path.join(root, "seal.json")))
    bad = [p for p, h in s["files"].items()
           if hashlib.sha256(open(os.path.join(root, p), "rb").read()).hexdigest() != h]
    return {"sealed": len(s["files"]), "mismatch": len(bad)}

sa, sd = json.load(open(asc + "/summary.json")), json.load(open(desc + "/summary.json"))
assert [x["path"] for x in sa["supplied"]] == [x["path"] for x in sd["supplied"]]
ud = {u["unit_id"]: u for u in sd["units"]}
res = {"seal_asc": seal(asc), "seal_desc": seal(desc), "order_desc": sd["order"],
       "status_pairs": collections.Counter(), "same_version": 0, "different_version": 0,
       "cross_series": [], "node_key5_ir_equal": 0, "node_key5_ir_different": [],
       "edges_calls_equal": 0, "graph_bytes_equal": 0, "graph_diff_fields": collections.Counter(),
       "length_diff_files": 0, "version_pairs": collections.Counter()}
for u in sa["units"]:
    uid, d = u["unit_id"], ud[u["unit_id"]]
    res["status_pairs"][f'{u["status"]}|{d["status"]}|{d["reason"]}'] += 1
    if u["status"] != "success":
        continue
    va, vd = u["selected_version"], d["selected_version"]
    if va == vd:
        res["same_version"] += 1
    else:
        res["different_version"] += 1
        res["version_pairs"][f"{va}->{vd}"] += 1
        if va.rsplit(".", 1)[0] != vd.rsplit(".", 1)[0]:
            res["cross_series"].append(uid)
    ba = open(f"{asc}/units/{uid}/graph.json", "rb").read()
    bd = open(f"{desc}/units/{uid}/graph.json", "rb").read()
    res["graph_bytes_equal"] += ba == bd
    ga, gd = json.loads(ba), json.loads(bd)
    key = lambda g: [(n["key5"], n["ir"], n["node_type"], n["declaration_kind"], n["provenance"]) for n in g["nodes"]]
    if key(ga) == key(gd):
        res["node_key5_ir_equal"] += 1
    else:
        res["node_key5_ir_different"].append(uid)
    rest = lambda g: {k: v for k, v in g.items() if k != "nodes"}
    res["edges_calls_equal"] += rest(ga) == rest(gd)
    lens = 0
    for x, y in zip(ga["nodes"], gd["nodes"]):
        for f in set(x) | set(y):
            if x.get(f) != y.get(f):
                res["graph_diff_fields"][f] += 1
                lens += f == "length"
    res["length_diff_files"] += lens > 0
json.dump(res, open(out, "w"), indent=1, sort_keys=True, default=dict)
print(json.dumps({k: v for k, v in res.items() if k != "version_pairs"}, default=dict))
