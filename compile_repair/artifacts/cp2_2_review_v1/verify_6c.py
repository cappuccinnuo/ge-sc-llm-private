"""Recount CP2.2 6c evidence from the unpacked cp2_6c_v3 archive (no reference report needed)."""
import collections, gzip, hashlib, json, os, sys
root, out = sys.argv[1], sys.argv[2]

def seal(d):
    s = json.load(open(os.path.join(d, "seal.json")))
    return sum(hashlib.sha256(open(os.path.join(d, p), "rb").read()).hexdigest() != h for p, h in s["files"].items())

def key(x):
    return json.dumps([x["layer"], x["function_name"], x["function"]["start"], x["context_contract"],
                       x["inherited_context"], x["node"]["start"], x["declaration"]["start"],
                       x["canonical_name"], x["fact"], x["tags"]], sort_keys=True)

res = {"seal_mismatch": {d: seal(os.path.join(root, d)) for d in (".", "continuation", "d20a/0227")}}
e = json.load(gzip.open(os.path.join(root, "d20a/0227/extractions/001.json.gz")))
res["d20a_0227"] = {"samples": len(os.listdir(os.path.join(root, "d20a/0227/extractions"))),
                    "occurrences": len(e["occurrences"]),
                    "out_282_DEF_by_context": collections.Counter(
                        f'{x["context_contract"]}|inherited={x["inherited_context"]}' for x in e["occurrences"]
                        if x["layer"] == "L1" and x["fact"] == [282, "out", "DEF"] and x["node"]["start"] == 9337)}
rows = []
for line in open(os.path.join(root, "continuation/comparison.jsonl")):
    r = json.loads(line)
    p = os.path.join(root, "continuation/extractions/%04d.json.gz" % r["index"])
    occ = json.load(gzip.open(p))["occurrences"]
    rows.append({"index": r["index"], "version": r["version"], "recount": len(occ), "recorded": r["occurrences"],
                 "reference": r["reference_occurrences"], "criterion": r["criterion"], "passed": r["passed"],
                 "only_reference": len(r["only_reference"]), "only_replay": len(r["only_replay"]),
                 "sha_ok": hashlib.sha256(gzip.open(p).read()).hexdigest() == r["extraction_sha256"]})
res["continuation"] = rows
files = [os.path.join(root, "continuation/extractions/0239.json.gz")] + \
        [os.path.join(root, "continuation/d20/0239/extractions/%03d.json.gz" % i) for i in range(1, 11)]
counts = [collections.Counter(key(x) for x in json.load(gzip.open(f))["occurrences"]) for f in files]
allk = set().union(*counts)
res["file_239"] = {"totals": [sum(c.values()) for c in counts],
                   "varying_keys": [{"function": json.loads(k)[1], "fact": json.loads(k)[8], "counts": [c[k] for c in counts]}
                                    for k in sorted(allk) if len({c[k] for c in counts}) > 1]}
json.dump(res, open(out, "w"), indent=1, sort_keys=True)
print(json.dumps(res["seal_mismatch"]), json.dumps(res["d20a_0227"]), json.dumps(res["file_239"]))
