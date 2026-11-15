"""Summarize CP2.1 observations without changing the acceptance criteria."""
import json
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ART = OUT.parent

def read(path):
    return json.loads(path.read_text())

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]

def write(name, value):
    with (OUT/name).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")

def execute():
    ascending = rows(OUT/"ascending1_acceptance.jsonl")
    categories = {}
    for row in ascending:
        category = Path(row["path"]).parts[-3]
        value = categories.setdefault(category, Counter())
        value[row["status"]] += 1
    result = dict(ascending1=read(OUT/"ascending1_receipt.json"),
                  categories={k:dict(v) for k,v in categories.items()},
                  versions=dict(Counter(r["selected_version"] for r in ascending if r["status"] == "success")),
                  cp0_attribution=dict(Counter(r["cp0_version_attribution"]["kind"]
                      for r in ascending if "cp0_version_attribution" in r)),
                  archive_equal=sum(r.get("production_archive_equal", False) for r in ascending),
                  code_scope="graph_facts only; 14 production files")
    if (OUT/"ascending2_receipt.json").exists():
        result["ascending2"] = read(OUT/"ascending2_receipt.json")
    if (ART/"cp2_6c_v2/summary.json").exists():
        result["replay"] = read(ART/"cp2_6c_v2/summary.json")
    if (OUT/"descending_receipt.json").exists():
        descending = rows(OUT/"descending_acceptance.jsonl")
        difference = []
        for row in descending:
            diff = row.get("cross_version")
            if diff is None:
                continue
            if not (diff["key5"]["equal"] and diff["slithir"]["equal"]):
                difference.append(dict(path=row["path"], source_sha256=row["source_sha256"],
                    ascending_version=row["ascending_version"], descending_version=row["selected_version"],
                    key5_equal=diff["key5"]["equal"], slithir_equal=diff["slithir"]["equal"],
                    length_equal=diff["source_length"]["equal"],
                    full_difference=diff))
        counts = Counter()
        for row in descending:
            diff=row["cross_version"]
            counts["key5_equal" if diff["key5"]["equal"] else "key5_different"] += 1
            counts["ir_equal" if diff["slithir"]["equal"] else "ir_different"] += 1
            counts["both_equal" if diff["key5"]["equal"] and diff["slithir"]["equal"]
                   else "any_difference"] += 1
            counts["length_equal" if diff["source_length"]["equal"] else "length_different"] += 1
            counts["same_version" if row["ascending_version"]==row["selected_version"]
                   else "different_version"] += 1
        result["descending"] = read(OUT/"descending_receipt.json")
        result["cross_version_counts"] = dict(counts)
        result["cross_version_version_pairs"] = dict(Counter(
            r["ascending_version"]+" -> "+r["selected_version"] for r in descending))
        write("cross_version_differences.json", difference)
    modes = ["ascending1","ascending2","descending"]
    result["run_status"] = {mode:read(OUT/(mode+"_receipt.json"))["passed"]
                           if (OUT/(mode+"_receipt.json")).exists() else "not_run" for mode in modes}
    result["run_status"]["replay"] = result.get("replay", {}).get("passed", "not_run")
    write("cp2_1_summary.json", result)
    print(json.dumps({k:v for k,v in result.items() if k!="cross_version_version_pairs"},
                     ensure_ascii=False, indent=2))

if __name__ == "__main__":
    execute()
