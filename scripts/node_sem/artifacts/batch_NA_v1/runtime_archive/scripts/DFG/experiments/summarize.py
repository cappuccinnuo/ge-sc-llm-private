"""Summarize all requested runs, including blocked folds (never discard them)."""
import argparse
import csv
from pathlib import Path
from .common import read_json, write_json, new_output


def summarize(runs, output):
    out = new_output(output)
    rows = []
    for directory in runs:
        directory = Path(directory).resolve()
        doc = read_json(directory / "result.json")
        for fold in doc["folds"]:
            for variant in ("E0", "E1"):
                for checkpoint in ("best", "last"):
                    row = {"run": str(directory), "cohort": doc["cohort"], "task": doc["task"],
                           "mode": doc["mode"], "fold": fold["fold"], "status": fold["status"],
                           "variant": variant, "checkpoint": checkpoint}
                    if fold["status"] == "complete":
                        result = fold["variants"][variant]
                        score = result["outer_test"][checkpoint]
                        for key in ("n", "positive", "buggy_f1", "macro_f1", "precision", "recall"):
                            row[key] = score[key]
                        row["tn"], row["fp"], row["fn"], row["tp"] = score["tn_fp_fn_tp"]
                        row["epoch"] = result[checkpoint + "_epoch"]
                        row["ddg_gradient_l1"] = sum(
                            x["message_gradient_l1"] for x in result["gradient_audit"]["ddg_relations"].values())
                        row["ddg_message_update_l1"] = result["gradient_audit"]["ddg_message_update_l1"]
                        for key, value in fold["paired_outer_delta"][checkpoint].items():
                            row["paired_E1_minus_E0_" + key] = value
                    rows.append(row)
    out.mkdir(parents=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (out / "summary.csv").open("w", encoding="utf8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    write_json(out / "summary.json", {
        "rows": rows, "scores_unit": "percent; deltas are percentage points",
        "note": "Smoke is interface validation, not a final efficacy experiment. Blocked folds have blank metrics.",
        "runs": [str(Path(r).resolve()) for r in runs]})
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", nargs="+", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    summarize(a.runs, a.output)


if __name__ == "__main__":
    main()
