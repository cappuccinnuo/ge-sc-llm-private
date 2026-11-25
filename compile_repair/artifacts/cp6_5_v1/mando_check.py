"""CP6.5 check: the 843 sealed v5 graphs are unchanged; the 3 historical failures now succeed.

The three v5 failures (input_0550, input_0551, input_0553) compile on 0.4.24 but Slither 0.11.6
asserts on `(bool ok, ) = x.call...` there; the CP6.5 step-10 tuple-call rewrite repairs them.
They must succeed through step 10 alone (slither_compat), on the version solc accepted, with D3(c).

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
count = dict(graphs_equal=0, new_successes=0, steps_on_truths=0, d3_c_true=0)
mismatches = []
start = time.monotonic()


NEW_SUCCESSES = ("input_0550", "input_0551", "input_0553")


def verify(record, store):
    old, key = priors[record.unit_id], "units/" + record.unit_id + "/graph.json"
    if record.unit_id in NEW_SUCCESSES:
        steps = {c.step for p in record.provenance.values() for c in p.changes}
        same = (old["status"] != "success" and record.status == "success" and steps == {"slither_compat"}
                and record.selected_version == "0.4.24" and record.attempts[-1]["slither"].get("d3_c") is True
                # The record of a repaired unit describes its working copy; the supplied file is
                # checked against the sealed input hash instead.
                and sha256(Path(paths[int(record.unit_id.rsplit("_", 1)[1]) - 1])) == old["input_sha256"])
        count["new_successes"] += int(same)
    elif record.status == "success":
        same = (old["status"], old["selected_version"], old["reason"]) == (
            record.status, record.selected_version, record.reason) and record.inputs[0]["sha256"] == old["input_sha256"]
        same = same and (ref / key).read_bytes() == (store / key).read_bytes()
        count["graphs_equal"] += int(same)
        count["d3_c_true"] += int(record.attempts[-1]["slither"].get("d3_c") is True)
        count["steps_on_truths"] += int((store / "units" / record.unit_id / "repair_steps.json").exists())
    else:
        same = False
    if not same:
        mismatches.append(record.unit_id)


rc = main(["repair"] + paths + ["--regression", "mando", "--order", "ascending", "--output", str(dest)],
          result_check=verify)
expected = dict(graphs_equal=843, new_successes=3, steps_on_truths=0, d3_c_true=843)
receipt = dict(passed=rc == 0 and count == expected and not mismatches, returncode=rc, counts=count,
               expected=expected, mismatches=mismatches, reference_seal_sha256=SEAL_SHA256,
               new_seal_sha256=sha256(dest / "seal.json"), elapsed_seconds=round(time.monotonic() - start, 2))
Path(args.summary).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf8")
print(json.dumps(receipt["counts"]), receipt["passed"])
sys.exit(0 if receipt["passed"] else 1)
