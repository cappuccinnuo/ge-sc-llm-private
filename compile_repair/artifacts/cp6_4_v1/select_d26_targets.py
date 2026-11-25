"""Select CP5 target units that D26 can affect: unresolved `name-X.Y.Z/...` imports of indexed releases.

Usage: python -B select_d26_targets.py <dependency index dir> <targets.json>
Reads the committed CP5.2 continuation records (cp5_2_v1/packed/continuation/real_0?.jsonl.gz)
and, for units that still failed D3 with an unresolved package import, each unit's local
result.json (result_path, checked against result_sha256). A unit is selected when one of its
unresolved import paths starts with a prefix `name-X.Y.Z` that is not itself an indexed
package while `name@X.Y.Z` is. Entry paths come from the committed CP3 unit inventory.
"""
import collections
import gzip
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from compile_repair.rules.dependencies import _VERSIONED_PREFIX, OfflineIndex, package_spec  # noqa: E402

ARTIFACTS = Path(__file__).resolve().parents[1]
index, out = OfflineIndex(sys.argv[1]), Path(sys.argv[2])
with (ARTIFACTS / "cp3_continue_v1/unit_inventory.jsonl").open(encoding="utf8") as fp:
    inventory = {row["unit_id"]: row for row in map(json.loads, fp)}
targets, prefixes, skipped = [], collections.Counter(), collections.Counter()
for part in sorted((ARTIFACTS / "cp5_2_v1/packed/continuation").glob("real_0?.jsonl.gz")):
    with gzip.open(part, "rt", encoding="utf8") as fp:
        for row in map(json.loads, fp):
            if row["d3"] or "unresolved_package_import" not in row["primary"]:
                continue
            result = Path(row["result_path"])
            raw = result.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["result_sha256"]:
                raise ValueError("Result differs from the CP5.2 record: " + row["unit_id"])
            record, found = json.loads(raw), set()
            for attempt in record["attempts"]:
                for issue in attempt.get("issues", ()):
                    spec = package_spec(issue.get("path", ""))
                    versioned = spec and _VERSIONED_PREFIX.fullmatch(spec[0])
                    if versioned and spec[0] not in index.packages and \
                            versioned.group(2) in index.packages.get(versioned.group(1), {}):
                        found.add(spec[0])
            if not found:
                skipped["no_indexed_versioned_prefix"] += 1
                continue
            unit = inventory[row["unit_id"]]
            prefixes.update(found)
            targets.append(dict(unit_id=row["unit_id"], corpus=row["corpus"], kind=unit["kind"],
                                primary=row["primary"], any=[], path=unit["path"], sha=unit["entry_sha256"],
                                project_root=unit["project_root"], versioned_prefixes=sorted(found)))
out.write_text(json.dumps(targets, indent=1) + "\n", encoding="utf8")
print(json.dumps(dict(targets=len(targets), prefixes=dict(prefixes.most_common()), skipped=dict(skipped),
                      projects=len({t["project_root"] for t in targets}))))
