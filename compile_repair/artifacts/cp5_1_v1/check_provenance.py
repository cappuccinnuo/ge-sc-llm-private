"""Read every attempted CP5 candidate and check its original bytes and any import-literal changes."""
from collections import Counter
import json
from pathlib import Path
import sys
import time

from evidence import verify_source
from population import LOCAL, OUT, load, save, sha256


def verify_unit(folder):
    rows = load(folder/"repair_steps.json") if (folder/"repair_steps.json").is_file() else []
    branches = [r for r in rows if "receipt" in r]
    counts = Counter()
    if not branches:
        return counts
    if (folder/"wrapper_sources").is_dir():
        origin = folder/"wrapper_sources"
    elif (folder/"project.json").is_file():
        origin = Path(load(folder/"project.json")["root"])
    else:
        origin = folder/"standalone"
    assert origin.is_dir()
    directory = folder.parents[1]
    for step in branches:
        receipt = directory/step["receipt"]
        result = load(receipt)
        project = receipt.with_name("project.json")
        work = receipt.parent/"input_project"
        if project.exists():
            assert Path(load(project)["root"]) == work
        for source, proof in result["provenance"].items():
            name = Path(source).relative_to(work)
            owner = origin/name
            changes = verify_source(source,proof)
            counts[proof["level"]+"_files"] += 1
            if proof["level"] == "additive":
                assert name.parts[:2] == (".compile_repair","deps") and not owner.exists() and not owner.is_symlink()
                counts["additive_edits"] += changes
            else:
                assert sha256(owner) == proof["original_sha256"]
                counts["rewrite_edits"] += changes
        counts["rounds"] += 1
        counts["accepted_rounds"] += bool(step.get("accepted"))
    return counts


def main(tag):
    start = time.monotonic()
    rows_file = OUT/(tag+".jsonl")
    modes = {"real_full", "real_dev", "real_masked", "benchmark", "package_dev"}
    assert tag in modes and load(OUT/(tag+"_summary.json"))["rows_sha256"] == sha256(rows_file)
    counts, units = Counter(), 0
    with rows_file.open(encoding="utf8") as stream:
        for row in map(json.loads,stream):
            if tag in ("benchmark","package_dev"):
                folder = LOCAL/tag/row["policy"]/row["operator"]/row["unit_id"]/"units"/row["unit_id"]
            else:
                folder = Path(row["result_path"]).parent
            counts.update(verify_unit(folder))
            units += 1
    save(OUT/(tag+"_provenance.json"),dict(measurements=units,counts=counts,rows_sha256=sha256(rows_file),
         scope="Every materialized candidate round, including rejected and pre-compilation rounds.",
         elapsed_seconds=time.monotonic()-start))
    print(tag,units,dict(counts),flush=True)


if __name__=="__main__":
    main(sys.argv[1])
