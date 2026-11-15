"""Analyse node_dump outputs: (1) my 0.8.0 run vs Codex cp0_v2 fingerprints;
(2) Slither 0.8.0 vs 0.8.3 vs 0.11.6 on the same compilers; (3) ordinal identity stability."""
import collections
import glob
import json
import sys

RUN, RECON = sys.argv[1], sys.argv[2]


def load(tag):
    rows = {}
    for f in glob.glob("%s/out_%s_*.jsonl" % (RUN, tag)):
        for line in open(f):
            r = json.loads(line)
            rows[r["id"]] = r
    return rows


def key4_multiset(r):
    c = collections.Counter()
    for contract, fn, seq in r["funcs"]:
        for t, start, ir in seq:
            c[(contract, fn, t, start)] += 1
    return c


def ordinal_seq(r, with_ir):
    """Per function: list of (type, start, ordinal-among-same-(type,start)[, ir]) in Slither node order."""
    out = {}
    for contract, fn, seq in r["funcs"]:
        seen = collections.Counter()
        items = []
        for t, start, ir in seq:
            seen[(t, start)] += 1
            items.append((t, start, seen[(t, start)]) + ((tuple(ir),) if with_ir else ()))
        out[(contract, fn)] = items
    return out


res = collections.OrderedDict()
d = json.load(open(RECON))
sel_sha = {x["sha256"]: x for x in d["inputs"]}

# Codex fingerprints of the selected version
inv = {}
for line in open(RECON.replace("recon.json", "invocations.jsonl")):
    r = json.loads(line)
    if r["kind"] == "slither" and r.get("scope") == "mando":
        inv[(r["source_sha256"], r["version"])] = r.get("node_facts_sha256")

s080 = load("s080_sel")
res["s080_rows"] = len(s080)
res["s080_ok"] = sum(r["ok"] for r in s080.values())
match = mism = 0
for rid, r in s080.items():
    sha = rid.split("@")[0]
    if inv.get((sha, r["version"])) == r.get("cp0_sha"):
        match += 1
    else:
        mism += 1
res["s080_fingerprint_equal_to_codex"] = match
res["s080_fingerprint_differs"] = mism

for tag in ("s083_sel", "s0116_sel"):
    other = load(tag)
    st = collections.Counter()
    examples = []
    for rid, r in s080.items():
        o = other.get(rid)
        if o is None:
            st["missing_row"] += 1
            continue
        if not o["ok"]:
            st["failed"] += 1
            examples.append((rid[:12], o["error"]))
            continue
        st["unmapped_nodes_files"] += o["unmapped"] > 0
        k_eq = key4_multiset(r) == key4_multiset(o)
        st["key4_equal"] += k_eq
        ir_eq = ordinal_seq(r, True) == ordinal_seq(o, True)
        st["ordered_ir_equal"] += ir_eq
        if not k_eq and len(examples) < 6:
            a, b = key4_multiset(r), key4_multiset(o)
            examples.append((rid[:12], "only_080", list((a - b).items())[:2], "only_new", list((b - a).items())[:2]))
        st["top_level_nonempty"] += bool(o["top_level"])
    res[tag] = dict(st)
    res[tag + "_examples"] = examples[:6]

# ordinal stability across compiler versions (Slither 0.8.0, lowest vs highest D3)
ends = load("s080_ends")
st = collections.Counter()
for x in d["inputs"]:
    if not x["cross_version"]:
        continue
    lo, hi = ends.get(x["sha256"] + "@low"), ends.get(x["sha256"] + "@high")
    if not lo or not hi or not lo["ok"] or not hi["ok"]:
        st["missing_or_failed"] += 1
        continue
    st["pairs"] += 1
    st["ordinal_key_equal"] += ordinal_seq(lo, False) == ordinal_seq(hi, False)
    st["ordinal_key_ir_equal"] += ordinal_seq(lo, True) == ordinal_seq(hi, True)
    dup = (x.get("selected_duplicate_key4_count") or 0) > 0
    st["dup_files"] += dup
    st["dup_files_ordinal_equal"] += dup and ordinal_seq(lo, True) == ordinal_seq(hi, True)
res["ordinal_stability_s080"] = dict(st)
print(json.dumps(res, indent=1, default=str))
