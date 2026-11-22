"""Describe (without copying content) corpus entries left as Trace on-chain parser_error_other.
Usage: python3 -I inspect_nonsolidity.py <dir with <unit_id>.sol> <list.txt: unit sha name> <out.json>"""
import hashlib, json, os, re, sys
d, listing, out = sys.argv[1:4]
PRAGMA = re.compile(r"^\s*#\s*(?:@version|pragma\s+version)\b.*$", re.M)
DECOR = re.compile(r"^@(?:external|internal|view|pure|payable|nonpayable|deploy)\s*$", re.M)
rows = []
for line in open(listing):
    uid, sha, name = line.split()
    raw = open(os.path.join(d, uid + ".sol"), "rb").read()
    text = raw.decode("utf8", "replace")
    row = {"unit_id": uid, "file": name, "sha256_matches_inventory": hashlib.sha256(raw).hexdigest() == sha,
           "bytes": len(raw), "double_brace_json": text.strip().startswith("{{")}
    if row["double_brace_json"]:
        row["json_language"] = json.loads(text.strip()[1:-1]).get("language")
    m = PRAGMA.search(text)
    row["vyper_version_pragma"] = m.group(0).strip() if m else None
    row["vyper_decorator_lines"] = len(DECOR.findall(text))
    row["contains_pragma_solidity"] = "pragma solidity" in text
    rows.append(row)
json.dump(rows, open(out, "w"), indent=1)
print(len(rows), sum(r["sha256_matches_inventory"] for r in rows),
      sum(r.get("json_language") == "Vyper" for r in rows), sum(bool(r["vyper_version_pragma"]) and not r["double_brace_json"] for r in rows),
      [r["unit_id"] for r in rows if not r["double_brace_json"] and not r["vyper_version_pragma"]])
