"""CP2.3: one ascending production CLI run, checked against immutable v3."""
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ART = OUT.parent
sys.path.insert(0, str(ROOT))
from compile_repair.cli import main
from compile_repair.core.store import emit, read_checked_json, sha256
from compile_repair.toolchain.solc import CP0_SHA256, version_tuple


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def write(name, value):
    with (OUT / name).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def execute():
    assert Path.cwd() == ROOT
    for mode in ("production", "mando", "dfg"):
        assert read(OUT / ("pytest_" + mode + ".json"))["returncode"] == 0
    assert read(OUT / "probes.json")["passed"]
    inputs = read_checked_json(ART / "cp0_v2/recon.json", CP0_SHA256)["inputs"]
    assert len(inputs) == 846
    first, output = ART / "cr_store_mando_v3", ART / "cr_store_mando_v5"
    seal = read(first / "seal.json")
    assert all(sha256(first / p) == h for p, h in seal["files"].items())
    records = {r["inputs"][0]["path"]: r for r in
               map(json.loads, (first / "manifest.jsonl").read_text().splitlines())}
    paths = [str((ROOT / r["path"]).resolve()) for r in inputs]
    assert len(records) == len(paths) == 846
    assert read(first / "summary.json")["supplied"] == [{"path": p, "kind": "file"} for p in paths]
    expected_failed = {str((ROOT / row["path"]).resolve()) for row in inputs
                       if row["category"] == "reentrancy" and row["file"] in
                       {"reentrancy_bonus.sol", "reentrancy_cross_function.sol", "reentrancy_insecure.sol"}}
    assert len(expected_failed) == 3
    for row, path in zip(inputs, paths):
        assert sha256(Path(path)) == row["sha256"]
    assert not output.exists()
    argv = ["repair"] + paths + ["--regression", "mando", "--order", "ascending", "--output", str(output)]
    write("regression_plan.json", dict(argv=argv, cwd=str(ROOT), inputs=846, profile="production",
        reference=str(first), reference_seal_sha256=sha256(first / "seal.json"),
        driver_sha256=sha256(Path(__file__)), expected_failures=sorted(expected_failed),
        comparison_fields=["status", "reason", "selected_version", "settings", "flags"],
        graph_comparison="exact bytes", llm_calls=0, cost_usd=0))
    accepted = []
    started = time.monotonic()
    with (OUT / "regression_acceptance.jsonl").open("x", encoding="utf8") as stream:
        def check(record, store):
            current = asdict(record)
            original = records[record.inputs[0]["path"]]
            item = dict(unit_id=record.unit_id, path=record.inputs[0]["path"],
                        source_sha256=record.inputs[0]["sha256"], status=record.status,
                        selected_version=record.selected_version, settings=record.settings,
                        flags=record.flags, issues=[])
            try:
                # JSON-normalize tuples only; values/order must remain identical.
                projected = json.loads(json.dumps(current))
                fields = ("status", "reason", "selected_version", "settings", "flags")
                item["fields_equal"] = {k: projected[k] == original[k] for k in fields}
                assert all(item["fields_equal"].values()), item["fields_equal"]
                assert record.inputs == original["inputs"]
                graph = store / "units" / record.unit_id / "graph.json"
                if item["path"] in expected_failed:
                    assert record.status == "unrepaired" and record.reason == "slither_side_failure"
                    assert not graph.exists()
                else:
                    assert record.status == "success"
                    last = record.attempts[-1]
                    assert last["solc"]["returncode"] == 0 and last["slither"]["d3"]
                    assert last["slither"]["profile"] == "production"
                    original_graph = first / "units" / original["unit_id"] / "graph.json"
                    item["graph_equal"] = graph.read_bytes() == original_graph.read_bytes()
                    item["graph_sha256"] = sha256(graph)
                    assert item["graph_equal"], "graph bytes differ"
                item["passed"] = True
            except Exception as exc:
                item.update(passed=False, issues=[type(exc).__name__ + ": " + str(exc)])
                emit(stream, item)
                accepted.append(item)
                raise
            emit(stream, item)
            accepted.append(item)
        rc = main(argv, result_check=check)
    summary, seal = read(output / "summary.json"), read(output / "seal.json")
    sealed = all(sha256(output / p) == h for p, h in seal["files"].items())
    counts = Counter(r["status"] for r in accepted)
    support = [v for v in seal["tools"]["compilers"] if (0,4,12) <= version_tuple(v) < (0,9,0)]
    result = dict(passed=(len(accepted) == 846 and counts == {"success":843, "unrepaired":3}
                         and all(r["passed"] for r in accepted) and sealed and len(support) == 92
                         and summary["status"] == "unrepaired" and rc == 2),
                  units_checked=len(accepted), status_counts=dict(counts), returncode=rc,
                  fields_equal={k:sum(r["fields_equal"][k] for r in accepted) for k in
                                ("status", "reason", "selected_version", "settings", "flags")},
                  graphs_equal=sum(r.get("graph_equal", False) for r in accepted),
                  supported_compilers=len(support), sealed_files=len(seal["files"]),
                  seal_readback_equal=sealed, seal_sha256=sha256(output / "seal.json"),
                  elapsed_seconds=time.monotonic()-started, cost_usd=0, llm_calls=0,
                  differences=[r for r in accepted if not r["passed"]])
    write("regression.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    execute()
