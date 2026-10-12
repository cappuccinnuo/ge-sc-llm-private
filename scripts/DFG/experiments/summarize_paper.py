"""Export explicitly named CV validation scores; never mix nested results."""
import argparse
import csv
from pathlib import Path
from .common import read_json, write_json
from .paper_protocol import NAME, VERSION, SCORE_ROLE, protocol_output


def rows_for(summary):
    if (summary.get("protocol"), summary.get("protocol_version"), summary.get("score_role")) != (NAME, VERSION, SCORE_ROLE):
        raise ValueError("Refusing mixed protocol or scoring role")
    rows = []
    for fold in summary["folds"]:
        if fold["status"] != "complete":
            raise ValueError("Incomplete fold; do not silently omit")
        for variant, result in fold["variants"].items():
            if result.get("score_role") != SCORE_ROLE or "outer_test" in result:
                raise ValueError("Wrong score role in fold")
            for ck, score in result["cv_validation"].items():
                rows.append(dict(score, cohort=summary["cohort"], task=summary["task"],
                    fold=fold["fold"], variant=variant, checkpoint=ck, mode=summary["mode"],
                    protocol=NAME, protocol_version=VERSION, score_role=SCORE_ROLE,
                    best_epoch=result["best_epoch"], last_epoch=result["last_epoch"]))
    return rows


def summarize(runs, output):
    out = protocol_output(output)
    rows = []
    for path in runs:
        rows.extend(rows_for(read_json(Path(path) / "result.json")))
    identities = [(r["cohort"], r["task"], r["fold"], r["variant"], r["checkpoint"]) for r in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate scored fold; keep runs separate")
    out.mkdir(parents=True)
    write_json(out / "cv_validation_summary.json", {"protocol": NAME, "score_role": SCORE_ROLE,
        "rows": rows, "note": "No independent test estimate. Short fold0 checks cannot establish DDG efficacy."})
    with (out / "cv_validation_summary.csv").open("w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", nargs="+", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    summarize(a.runs, a.output)


if __name__ == "__main__":
    main()
