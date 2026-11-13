"""Count IR strings containing Python object reprs with memory addresses in node_facts_v2 archives.
Usage: python ir_object_repr.py <archive.jsonl.gz> ..."""
import collections, gzip, json, re, sys
rx = re.compile(r"<[\w.]+ object at 0x[0-9a-f]+>")
for f in sys.argv[1:]:
    files = lines = 0; cls = collections.Counter(); ex = []
    for l in gzip.open(f, "rt"):
        r = json.loads(l); hit = False
        for n in r["nodes"]:
            for ir in n["ir"]:
                m = rx.findall(ir)
                if m:
                    lines += 1; hit = True; cls.update(x.split(" object")[0][1:] for x in m)
                    if len(ex) < 4: ex.append([r["source_path"].split("source_code/")[-1], n["key5"], ir])
        files += hit
    print(json.dumps({"archive": f, "files": files, "ir_lines": lines, "classes": dict(cls), "examples": ex}, indent=1))
