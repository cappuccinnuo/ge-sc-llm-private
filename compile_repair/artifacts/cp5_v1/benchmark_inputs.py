"""Audit the public CP4.1 benchmark denominators before running any CP5 repair."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ART = HERE.parent
ROOT = ART.parents[1]
TARGET = {"unresolved_package_import": 114, "missing_relative_file": 400,
          "standard_json_input": 950, "io_error": 400, "closure_version_conflict": 400}


def checked(path, digest):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Frozen artifact hash changed: " + str(path))
    return raw


def pinned(path):
    rel = path.relative_to(ROOT).as_posix()
    raw = subprocess.check_output(["git", "show", "26f44492:"+rel], cwd=str(ROOT))
    return checked(path, hashlib.sha256(raw).hexdigest())


def samples():
    cp41 = ART/"cp4_1_v1"
    seal = json.loads(pinned(cp41/"migration_stop_seal.json"))["batch_files_excluding_this_seal"]
    selected = []
    for name in ("original_reclassified", "new_observations", "supplement_observations"):
        name += ".jsonl.gz"
        rows = gzip.decompress(checked(cp41/name, seal[name]["sha256"])).splitlines()
        selected.extend(r for r in map(json.loads, rows) if r["outcome"] == "included" and r["operator"] in TARGET)
    assert Counter(r["operator"] for r in selected) == TARGET
    assert len({(r["unit_id"],r["operator"],r["mutation_sha256"]) for r in selected}) == sum(TARGET.values())
    return sorted(selected, key=lambda r: (r["operator"],r["unit_id"],r["mutation_sha256"]))


if __name__ == "__main__":
    rows = samples()
    counts = defaultdict(Counter)
    for r in rows:
        counts[r["operator"]][r["split"]] += 1
    with (HERE/"benchmark_inventory.json").open("x") as fp:
        json.dump(dict(units=len(rows), per_operator=counts,
                       source="frozen included observations only; no CP5 outcomes"), fp, indent=2, sort_keys=True)
        fp.write("\n")
    print(dict(counts), flush=True)
