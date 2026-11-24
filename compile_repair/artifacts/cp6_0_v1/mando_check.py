"""CP6.0 check: the 846 MANDO inputs still give the sealed v5 results under D3(c).

Usage: python -B mando_check.py <extracted cr_store_mando_v5 dir> <new output dir> <summary.json>
The MANDO input paths are read from the v5 summary; with --repo-root they are re-rooted
from the recorded checkout to the given one (same relative path, SHA256 still checked).
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from compile_repair.cli import main  # noqa: E402
from compile_repair.core.store import read_checked_json, sha256  # noqa: E402

SEAL_SHA256 = "db925ee1642b5f8eae79d20defbbec673ffbaa7b4a0bb37cc270027bb1a8372b"
RECORDED_ROOT = "/home/zhao/SmartContract/ge-sc-llm-compile"

parser = argparse.ArgumentParser()
parser.add_argument("reference")
parser.add_argument("output")
parser.add_argument("summary")
parser.add_argument("--repo-root", default=RECORDED_ROOT)
args = parser.parse_args()
ref, dest = Path(args.reference), Path(args.output)
base = read_checked_json(ref / "seal.json", SEAL_SHA256)
summary = read_checked_json(ref / "summary.json", base["files"]["summary.json"])
priors = {r["unit_id"]: r for r in summary["units"]}
paths = [r["path"].replace(RECORDED_ROOT, args.repo_root, 1) for r in summary["supplied"]]
assert len(paths) == len(priors) == 846
count = dict(graphs_equal=0, historical_failures=0, steps_on_truths=0, d3_c_true=0)
mismatches = []
start = time.monotonic()


def verify(record, store):
    old, key = priors[record.unit_id], "units/" + record.unit_id + "/graph.json"
    same = (old["status"], old["selected_version"], old["reason"]) == (
        record.status, record.selected_version, record.reason) and record.inputs[0]["sha256"] == old["input_sha256"]
    if record.status == "success":
        same = same and (ref / key).read_bytes() == (store / key).read_bytes()
        count["graphs_equal"] += int(same)
        count["d3_c_true"] += int(record.attempts[-1]["slither"].get("d3_c") is True)
        count["steps_on_truths"] += int((store / "units" / record.unit_id / "repair_steps.json").exists())
    else:
        same = same and not (store / key).exists()
        count["historical_failures"] += int(same)
    if not same:
        mismatches.append(record.unit_id)


rc = main(["repair"] + paths + ["--regression", "mando", "--order", "ascending", "--output", str(dest)],
          result_check=verify)
expected = dict(graphs_equal=843, historical_failures=3, steps_on_truths=0, d3_c_true=843)
receipt = dict(passed=rc == 2 and count == expected and not mismatches, returncode=rc, counts=count,
               expected=expected, mismatches=mismatches, reference_seal_sha256=SEAL_SHA256,
               new_seal_sha256=sha256(dest / "seal.json"), elapsed_seconds=round(time.monotonic() - start, 2))
Path(args.summary).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf8")
print(json.dumps(receipt["counts"]), receipt["passed"])
sys.exit(0 if receipt["passed"] else 1)
