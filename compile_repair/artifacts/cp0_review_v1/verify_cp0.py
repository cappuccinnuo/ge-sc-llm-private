"""Independent recomputation of CP0 (cp0_v2) summary figures from raw records."""
import collections
import hashlib
import json
import os
import sys

REPO = sys.argv[1]
A = os.path.join(REPO, "compile_repair/artifacts/cp0_v2")
d = json.load(open(os.path.join(A, "recon.json")))
inputs = d["inputs"]
V = lambda s: tuple(int(x) for x in s.split("."))
out = collections.OrderedDict()

# 1. identities: re-hash the corpus in this clone
bad_sha = [x["path"] for x in inputs
           if hashlib.sha256(open(os.path.join(REPO, x["path"]), "rb").read()).hexdigest() != x["sha256"]]
out["inputs"] = len(inputs)
out["sha_mismatch_vs_git_corpus"] = len(bad_sha)

# 2. raw invocation index: (sha, version) -> solc rc ; (sha, version) -> slither d3
solc_rc, sl_d3 = {}, {}
for line in open(os.path.join(A, "invocations.jsonl")):
    r = json.loads(line)
    if r.get("scope") != "mando":
        continue
    key = (r["source_sha256"], r["compiler"]["version"] if "compiler" in r else r.get("version"))
    if r["kind"] == "solc":
        solc_rc.setdefault(key, []).append(r["returncode"])
    else:
        sl_d3.setdefault(key, []).append(r.get("d3"))
out["raw_solc_records_mando"] = sum(len(v) for v in solc_rc.values())
out["raw_slither_records_mando"] = sum(len(v) for v in sl_d3.values())

# 3. rule A
out["rule_a"] = dict(collections.Counter(x["rule_a_result"]["status"] for x in inputs))

# 4. selection checks against raw logs and interval/minor-series constraint
stats = collections.Counter()
viol = []
for x in inputs:
    s = x["selection"]
    asc, desc = s["ascending"], s["descending"]
    stats["asc_desc_differ"] += asc != desc
    stats["moved_from_rule_a"] += asc != x["rule_a_version"]
    for name, v in (("asc", asc), ("desc", desc)):
        k = (x["sha256"], v)
        if solc_rc.get(k) is None or 0 not in solc_rc[k]:
            viol.append((x["path"], name, v, "no rc0 solc record"))
        if True not in (sl_d3.get(k) or []):
            viol.append((x["path"], name, v, "no D3 slither record"))
        iv = x["interval"]
        if iv is not None:
            lo, hi = tuple(iv[0]), tuple(iv[1])
            if not (lo <= V(v) < hi):
                viol.append((x["path"], name, v, "outside interval"))
            if V(v)[:2] != lo[:2]:
                viol.append((x["path"], name, v, "different minor series from lower bound"))
        if V(v) < (0, 4, 12):
            viol.append((x["path"], name, v, "below 0.4.12"))
    stats["metadata_present"] += x["metadata"] is not None
    stats["dup_key4_files"] += (x.get("selected_duplicate_key4_count") or 0) > 0
    stats["no_pragma"] += x["interval"] is None
out["selection"] = dict(stats)
out["selection_violations"] = viol[:20]
out["selection_violation_count"] = len(viol)

# 5. cross-version file
cv = [json.loads(l) for l in open(os.path.join(A, "cross_version.jsonl"))]
out["cross_version_rows"] = len(cv)
out["cv_key4_equal"] = sum(r["lowest_highest"]["key4"]["equal"] for r in cv)
out["cv_ir_equal"] = sum(r["lowest_highest"]["slithir"]["equal"] for r in cv)
out["cv_len_equal"] = sum(r["lowest_highest"]["source_length"]["equal"] for r in cv)
out["cv_low_equals_asc"] = sum(r["low"] == r["selected"] for r in cv)

# 6. no-pragma handling and metadata priority
np_rows = [x for x in inputs if x["interval"] is None]
out["no_pragma_selected"] = dict(collections.Counter(x["selection"]["ascending"] for x in np_rows))
md = [x for x in inputs if x["metadata"] is not None]
out["metadata_selected_equals_recorded"] = sum(
    x["selection"]["ascending"] == (x["metadata"].get("version") or x["metadata"].get("recorded_version")) for x in md)
out["metadata_keys"] = sorted(md[0]["metadata"].keys()) if md else []
print(json.dumps(out, indent=1, default=str))
