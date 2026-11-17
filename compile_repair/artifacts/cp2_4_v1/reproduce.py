"""CP2.4: reproduce the reviewed defects before changing production code."""
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
from compile_repair.cli import main
from compile_repair.core.store import sha256, emit
from compile_repair.rules.environment import pragma_interval
from compile_repair.toolchain.solc import compile_file, load_trusted_compilers
from compile_repair.toolchain.slither import check_profile, run_slither
from scripts.DFG.models import Unsupported

def execute():
    baseline = json.loads((OUT / "baseline.json").read_text())
    assert all(sha256(ROOT / p) == h for p, h in baseline["implementation_sha256"].items())
    compilers, _, trust = load_trusted_compilers()
    result = {"profile": check_profile("production"), "trust": trust, "cases": [],
              "cost_usd": 0, "llm_calls": 0}
    review = ROOT / "compile_repair/artifacts/cp2_3_review_v1/edge_cases"
    paths = []
    start = time.monotonic()
    with (OUT / "reproduction_invocations.jsonl").open("x") as journal:
        for filename, version, success in [
            ("comment_inside.sol", "0.8.0", True),
            ("line_comment_inside.sol", "0.5.17", True),
            ("missing_semicolon.sol", "0.5.17", False),
        ]:
            path = review / filename
            paths.append(path)
            row = {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            try:
                pragma_interval([path.read_bytes()])
            except Unsupported as exc:
                row["old_error"] = str(exc)
            else:
                raise AssertionError("Expected reviewed rejection: " + filename)
            assert row["old_error"] == "F: unsupported pragma expression"
            compiled = compile_file(path, compilers[version])
            emit(journal, dict(kind="solc", **asdict(compiled)))
            assert not compiled.timed_out
            assert (compiled.returncode == 0) == success, asdict(compiled)
            row.update(version=version, compiler_sha256=compiled.compiler.sha256,
                       solc_returncode=compiled.returncode, error_first_line=compiled.error_first_line)
            if success:
                analysis = run_slither(compiled, profile="production")
                emit(journal, dict(kind="slither", **analysis))
                assert analysis["d3"], analysis
                row["d3"] = True
            else:
                assert "Expected ';' but got end of source" in compiled.stderr, compiled.stderr
            result["cases"].append(row)
            print("Reproduced " + filename, flush=True)
    paths.append(ROOT / "compile_repair/tests/fixtures/pragma_inputs/union_pragma.sol")
    argv = ["repair"] + list(map(str, paths)) + ["--output", str(OUT / "reproduction_cli")]
    def check(record, _):
        assert record.status == "unrepaired"
        assert record.flags == ["unsupported_version_constraints"]
        assert len(record.attempts) == 1
        assert record.attempts[0]["error_first_line"] == "F: unsupported pragma expression"
    rc = main(argv, result_check=check)
    assert rc == 2
    assert (OUT / "reproduction_cli/invocations.jsonl").read_bytes() == b""
    summary = json.loads((OUT / "reproduction_cli/summary.json").read_text())
    assert summary["status"] == "unrepaired" and len(summary["units"]) == 4
    result.update(passed=True, cli_argv=argv, cli_returncode=rc,
                  elapsed_seconds=time.monotonic() - start)
    with (OUT / "reproduction.json").open("x") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({"passed": True, "cases": len(result["cases"]), "cli_rejections": 4}))

if __name__ == "__main__":
    execute()
