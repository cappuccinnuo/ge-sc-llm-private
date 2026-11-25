"""Select real CP3 units for a CP6 check: unrepaired units whose CP3 causes include given categories.

Usage: python -B select_targets.py <targets.json> <category,category,...> [OLD_PREFIX=NEW_PREFIX ...] [cp3_NNNNN ...]
(CP6.2: unbalanced_structure,parser_error_other,file_level_member)
Reads the committed CP3 inventory (cp3_continue_v1/unit_inventory.jsonl) and attributions
(cp3_2_v1/unit_attributions.jsonl.gz). A unit is selected when its primary or any-candidate
categories meet the given set. Optional prefix pairs rewrite inventory paths (the cloud
check keeps corpora elsewhere); listed unit ids are added. Every entry is checked against its SHA-256.
"""
import gzip
import hashlib
import json
import sys
from pathlib import Path

ARTIFACTS = Path(__file__).resolve().parents[1]
WANTED = set(sys.argv[2].split(","))
out = Path(sys.argv[1])
prefixes = [tuple(arg.split("=", 1)) for arg in sys.argv[3:] if "=" in arg]
included = {arg for arg in sys.argv[3:] if "=" not in arg}


def local(path):
    for old, new in prefixes:
        if path and path.startswith(old):
            return new + path[len(old):]
    return path


with (ARTIFACTS / "cp3_continue_v1/unit_inventory.jsonl").open(encoding="utf8") as fp:
    inventory = {row["unit_id"]: row for row in map(json.loads, fp)}
targets = []
with gzip.open(ARTIFACTS / "cp3_2_v1/unit_attributions.jsonl.gz", "rt", encoding="utf8") as fp:
    for row in map(json.loads, fp):
        if row["status"] == "success" or row["corpus"] == "MANDO":
            continue
        primary = set(row["primary"]["categories"])
        candidates = set(row.get("any_categories") or ())
        if not (primary | candidates) & WANTED and row["unit_id"] not in included:
            continue
        unit = inventory[row["unit_id"]]
        path = Path(local(unit["path"]))
        if hashlib.sha256(path.read_bytes()).hexdigest() != unit["entry_sha256"]:
            raise ValueError("Entry differs from the CP3 inventory: " + row["unit_id"])
        targets.append(dict(unit_id=row["unit_id"], corpus=row["corpus"], kind=unit["kind"],
                            primary=sorted(primary), any=sorted(candidates), path=str(path),
                            sha=unit["entry_sha256"], project_root=local(unit["project_root"])))
out.write_text(json.dumps(targets, indent=1) + "\n", encoding="utf8")
print(json.dumps({"targets": len(targets), "by_corpus": {c: sum(t["corpus"] == c for t in targets)
                                                          for c in sorted({t["corpus"] for t in targets})}}))
