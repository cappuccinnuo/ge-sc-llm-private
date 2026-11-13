"""Count unique .sol files with an `event` declaration at brace depth 0 (file level).
Strips comments and string literals crudely. Usage: python toplevel_event.py <dir>"""
import hashlib, os, re, sys, json
C = re.compile(r"//[^\n]*|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", re.S)
seen, hits, ex = set(), 0, []
for d, _, fs in os.walk(sys.argv[1]):
    for f in fs:
        if not f.endswith(".sol"): continue
        p = os.path.join(d, f); raw = open(p, "rb").read(); h = hashlib.sha256(raw).hexdigest()
        if h in seen: continue
        seen.add(h); s = C.sub("", raw.decode("utf8", "replace")); depth = 0; i = 0; found = False
        for m in re.finditer(r"[{}]|\bevent\s+\w+\s*\(", s):
            t = m.group(0)
            if t == "{": depth += 1
            elif t == "}": depth -= 1
            elif depth == 0: found = True; break
        if found:
            hits += 1
            if len(ex) < 3: ex.append(p)
print(json.dumps({"unique": len(seen), "file_level_event_files": hits, "examples": ex}))
