"""Score a human-filled review CSV against its immutable blank reference.

Intervals describe reviewed edge judgments in this file-clustered sample;
they are not independent-seed model uncertainty or a census of all edges.
"""
import argparse
import csv
import json
import math
from pathlib import Path

from scripts.DFG.integration.io import checked, read_json, write_json
from .review_sheet import VERSION, COLUMNS, EDITABLE_COLUMNS, RELATIONS


def _read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(COLUMNS):
            raise ValueError("Review CSV columns/order differ")
        rows = list(reader)
    if any(set(r) != set(COLUMNS) or any(v is None for v in r.values()) for r in rows):
        raise ValueError("Malformed review CSV row")
    ids = [r["review_id"] for r in rows]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("Empty or duplicate review identity")
    return rows


def wilson95(correct, total):
    if type(correct) is not int or type(total) is not int or not 0 <= correct <= total:
        raise ValueError("Invalid Wilson counts")
    if total == 0:
        return None
    z = 1.959963984540054
    proportion, z2 = correct / total, z * z
    denominator = 1 + z2 / total
    center = (proportion + z2 / (2 * total)) / denominator
    radius = z * math.sqrt(proportion * (1 - proportion) / total + z2 / (4 * total * total)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def score_review(csv_path, seal_path, equivalence=None):
    seal_path = Path(seal_path).resolve()
    seal = read_json(seal_path)
    if (seal.get("version") != VERSION or seal.get("columns") != list(COLUMNS)
            or seal.get("editable_columns") != list(EDITABLE_COLUMNS)
            or seal.get("human_verdicts_filled") is not False):
        raise ValueError("Review seal schema differs")
    def local_ref(record):
        name = record["path"]
        if Path(name).name != name or name in (".", ".."):
            raise ValueError("Review seal reference must be a sibling filename")
        return checked(seal_path.parent / name, record["sha256"])
    blank_path = local_ref(seal["blank_csv"])
    provenance = read_json(local_ref(seal["provenance"]))
    if (seal["csv_sha256"] != seal["blank_csv"]["sha256"]
            or provenance.get("version") != VERSION
            or provenance.get("sampling") != seal["sampling"]
            or provenance.get("store", {}).get("sha256") != seal["store_sha256"]):
        raise ValueError("Review seal/provenance binding differs")
    reference, filled = _read_csv(blank_path), _read_csv(csv_path)
    if len(reference) != seal["row_count"] or len(filled) != len(reference):
        raise ValueError("Review CSV row count differs")
    if [p["review_id"] for p in provenance["rows"]] != [r["review_id"] for r in reference]:
        raise ValueError("Review provenance identity differs")
    counts = {r: dict(correct=0, wrong=0, unsure=0, blank=0) for r in RELATIONS}
    for old, new in zip(reference, filled):
        if any(old[k] for k in EDITABLE_COLUMNS):
            raise ValueError("Sealed reference was not blank")
        if any(old[k] != new[k] for k in COLUMNS if k not in EDITABLE_COLUMNS):
            raise ValueError("Immutable review CSV field changed: " + old["review_id"])
        if new["relation"] not in counts:
            raise ValueError("Unknown review relation")
        verdict = new["verdict"]
        if verdict not in ("", "correct", "wrong", "unsure"):
            raise ValueError("Invalid review verdict: " + repr(verdict))
        counts[new["relation"]][verdict or "blank"] += 1
    result = {}
    for relation, values in counts.items():
        total = values["correct"] + values["wrong"]
        result[relation] = dict(values, reviewed_denominator=total, sampled=sum(values.values()),
            correct_proportion=values["correct"] / total if total else None,
            wilson95=wilson95(values["correct"], total))
    report = dict(version=VERSION, status="scored", row_count=len(filled), relations=result,
        completed=not any(v["blank"] for v in counts.values()),
        excluded_from_denominator=["unsure", "blank"],
        interval_scope="descriptive edge judgments in a file-clustered sample; not independent model trials",
        seal=str(seal_path), csv=str(Path(csv_path).resolve()))
    if equivalence is not None:
        from .store_diff import verify_equivalence
        report["equivalence"] = verify_equivalence(equivalence, seal_path)
        report["scoring_store"] = report["equivalence"]["scoring_store"]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--seal", required=True)
    parser.add_argument("--output")
    parser.add_argument("--equivalence", help="Sealed store_diff.json proving review carry-forward")
    args = parser.parse_args(argv)
    output = Path(args.output).resolve() if args.output else None
    if output is not None and output.exists():
        raise FileExistsError("Refusing existing score output")
    result = score_review(args.csv, args.seal, equivalence=args.equivalence)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
