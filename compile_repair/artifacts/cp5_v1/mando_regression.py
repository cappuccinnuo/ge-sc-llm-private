"""CP5 acceptance through the public repair CLI, comparing against immutable v5 bytes."""
import json
import sys
import time
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
from compile_repair.cli import main
from compile_repair.core.store import emit, read_checked_json, sha256
from compile_repair.toolchain.solc import CP0_SHA256

start = time.monotonic()
reference = OUT.parent / "cr_store_mando_v5"
frozen_hash = "db925ee1642b5f8eae79d20defbbec673ffbaa7b4a0bb37cc270027bb1a8372b"
frozen = read_checked_json(reference / "seal.json", frozen_hash)
baseline = read_checked_json(reference / "summary.json", frozen["files"]["summary.json"])
inputs = read_checked_json(OUT.parent / "cp0_v2/recon.json", CP0_SHA256)["inputs"]
paths = [str((ROOT / r["path"]).resolve()) for r in inputs]
assert len(paths) == len(baseline["units"]) == 846
assert all(sha256(p) == r["sha256"] for p, r in zip(paths, inputs))
assert baseline["supplied"] == [dict(path=p, kind="file") for p in paths]
dest = ROOT.parent / "compile-repair-local/cp5_v1/mando_regression"
assert not dest.exists()
counts = Counter()
with (OUT/"mando_regression.jsonl").open("x", encoding="utf8") as audit:
    def check(record, store):
        original = baseline["units"][sum(counts.values())]
        row = dict(unit_id=record.unit_id, status=record.status, selected_version=record.selected_version,
                   reason=record.reason, source_sha256=record.inputs[0]["sha256"], d3=False)
        key = "units/" + record.unit_id + "/graph.json"
        row["steps_2_to_4"] = (store / "units" / record.unit_id / "repair_steps.json").exists()
        try:
            assert original["unit_id"] == record.unit_id and original["input_sha256"] == row["source_sha256"]
            assert all(row[k] == original[k] for k in ("status", "reason", "selected_version"))
            if record.status == "success":
                old, new = (reference / key).read_bytes(), (store / key).read_bytes()
                row["graph_sha256"] = sha256(store / key)
                assert sha256(reference / key) == frozen["files"][key] and new == old
                last = record.attempts[-1]
                row["d3"] = last["solc"]["returncode"] == 0 and last["slither"]["d3"]
                assert row["d3"] and not row["steps_2_to_4"]
            else:
                assert not (store / key).exists()
            row["passed"] = True
        except Exception as exc:
            row.update(passed=False, exception=type(exc).__name__, message=str(exc))
            raise
        finally:
            counts[record.status] += 1
            emit(audit, row)
    rc = main(["repair"] + paths + ["--regression", "mando", "--order", "ascending", "--output", str(dest)],
              result_check=check)
summary = json.loads((dest/"summary.json").read_bytes())
result = dict(status=summary["status"], counts=counts, cli_returncode=rc, reference_seal=frozen_hash,
              store=str(dest), store_seal=sha256(dest/"seal.json"), elapsed_seconds=time.monotonic()-start)
result["passed"] = rc == 2 and summary["status"] == "unrepaired" and counts == {"success":843, "unrepaired":3}
with (OUT/"mando_regression.json").open("x") as fp:
    json.dump(result, fp, indent=2)
    fp.write("\n")
print(result, flush=True)
assert result["passed"]
