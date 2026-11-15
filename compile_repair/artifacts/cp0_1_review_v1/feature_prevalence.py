"""Count .sol files (unique by SHA256) in a corpus containing source patterns that the
cp0.1-review probes showed to break some Slither versions. Text-level heuristic only:
comments are stripped crudely; matches are an upper-bound indicator, not compilation proof.
Usage: python feature_prevalence.py <corpus_dir> <name>"""
import hashlib, json, os, re, sys, collections

root, name = sys.argv[1:3]
COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
PRAGMA = re.compile(r"pragma\s+solidity\s+([^;]+);")
ASM = re.compile(r"assembly\s*(\(\s*\"memory-safe\"\s*\))?\s*\{")
PAT = collections.OrderedDict([
    ("asm_tload_tstore", re.compile(r"\b(tload|tstore)\s*\(")),
    ("asm_mcopy", re.compile(r"\bmcopy\s*\(")),
    ("asm_blob", re.compile(r"\b(blobbasefee|blobhash)\s*\(")),
    ("asm_basefee", re.compile(r"\bbasefee\s*\(")),
    ("asm_prevrandao", re.compile(r"\bprevrandao\s*\(")),
    ("transient_keyword", re.compile(r"\btransient\s+[A-Za-z_]")),
    ("v04_bool_tuple_call", re.compile(r"\(\s*bool\s+\w+\s*,\s*\)\s*=\s*[^;]*\.call\s*\.\s*value\s*\(")),
])
TOP_EVENT = re.compile(r"^event\s+\w+\s*\(", re.M)
seen, counts, minor = set(), collections.Counter(), collections.Counter()
for d, _, fs in os.walk(root):
    for f in fs:
        if not f.endswith(".sol"):
            continue
        p = os.path.join(d, f)
        try:
            raw = open(p, "rb").read()
        except OSError:
            continue
        h = hashlib.sha256(raw).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        src = COMMENT.sub("", raw.decode("utf8", "replace"))
        m = PRAGMA.search(src)
        v = re.search(r"0\.(\d+)", m.group(1)) if m else None
        series = "0." + v.group(1) if v else "none"
        minor[series] += 1
        has_asm = bool(ASM.search(src))
        for k, rx in PAT.items():
            if k.startswith("asm_") and not has_asm:
                continue
            if k == "v04_bool_tuple_call" and series != "0.4":
                continue
            if rx.search(src):
                counts[k] += 1
                counts[k + "@" + series] += 1
        if TOP_EVENT.search(src):
            counts["file_level_event"] += 1
print(json.dumps({"corpus": name, "unique_files": len(seen), "pragma_series": dict(minor),
                  "matches": dict(sorted(counts.items()))}, indent=1))
