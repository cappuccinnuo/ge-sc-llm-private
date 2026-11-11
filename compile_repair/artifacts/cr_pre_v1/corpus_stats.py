"""Read-only corpus statistics for the compile-repair proposal (evidence only)."""
import collections
import json
import os
import re
import sys

ROOT = sys.argv[1]
BUGS = ["access_control", "arithmetic", "denial_of_service", "front_running",
        "reentrancy", "time_manipulation", "unchecked_low_level_calls"]
PRAGMA = re.compile(r"pragma\s+solidity\s+([^;]*);")
FIRST_VER = re.compile(r"pragma solidity\s*(?:\^|>=|<=|~)?\s*(\d+\.\d+\.\d+)")  # auto_version_solc rule
LABEL_COMMENT = re.compile(r"<yes>\s*<report>|@vulnerable_at_lines|@source:|@author:", re.I)
IMPORT = re.compile(r"^\s*import\s", re.M)
ADDR_NAME = re.compile(r"^0x[0-9a-fA-F]{40}")

out = {}
for bug in BUGS:
    for sub in ("source_files", "cleaned_buggy_curated", "buggy_curated", "curated"):
        d = os.path.join(ROOT, bug, sub)
        if not os.path.isdir(d):
            continue
        files = sorted(f for f in os.listdir(d) if f.endswith(".sol"))
        st = collections.Counter()
        forms = collections.Counter()
        minors = collections.Counter()
        names = collections.Counter()
        for f in files:
            src = open(os.path.join(d, f), encoding="utf8", errors="ignore").read()
            p = PRAGMA.findall(src)
            if not p:
                st["no_pragma"] += 1
            else:
                st["has_pragma"] += 1
                if len(set(x.strip() for x in p)) > 1:
                    st["multiple_distinct_pragmas"] += 1
                c = p[0].strip()
                if re.fullmatch(r"\^\s*\d+\.\d+\.\d+", c):
                    forms["caret"] += 1
                elif re.fullmatch(r"=?\s*\d+\.\d+\.\d+", c):
                    forms["exact"] += 1
                elif re.search(r"[<>]", c):
                    forms["range"] += 1
                else:
                    forms["other:" + c] += 1
            m = FIRST_VER.findall(src)
            v = m[0] if m else "none"
            minors[".".join(v.split(".")[:2]) if v != "none" else "none"] += 1
            if LABEL_COMMENT.search(src):
                st["label_bearing_comment"] += 1
            if IMPORT.search(src):
                st["has_import"] += 1
            if ADDR_NAME.match(f):
                names["address_named"] += 1
            elif f.startswith("buggy_"):
                names["buggy_prefix"] += 1
            else:
                names["other_name"] += 1
        out["%s/%s" % (bug, sub)] = {
            "n_files": len(files), "stats": dict(st), "pragma_forms": dict(forms),
            "first_version_minor": dict(sorted(minors.items())), "names": dict(names),
        }
print(json.dumps(out, indent=1, sort_keys=True))
