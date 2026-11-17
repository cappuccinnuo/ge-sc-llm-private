"""CP2.3: capture the two known defects before editing production files."""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
from compile_repair.cli import main
from compile_repair.core.store import emit, sha256
from compile_repair.rules.environment import pragma_interval, pragma_patches, infer_interval
from compile_repair.toolchain.solc import compile_file, load_trusted_compilers
from compile_repair.toolchain.slither import check_profile, run_slither

FEATURE_NAMES = ("f0813_using_global", "f0819_user_operator", "f0828_transient",
                 "h0822_file_event", "h0829_layout_at")


def execute():
    baseline = json.loads((OUT / "baseline.json").read_text())
    for p, h in baseline["implementation_sha256"].items():
        assert sha256(ROOT / p) == h, "Reproduction must precede implementation"
    profile = check_profile("production")
    compilers, _, trust = load_trusted_compilers()
    paths = [ROOT / "compile_repair/tests/fixtures/features" / (n + ".sol") for n in FEATURE_NAMES]
    paths.append(ROOT / "compile_repair/artifacts/cp2_2_review_v1/fixtures/latin1_comment.sol")
    result = {"profile": profile, "trust": trust, "inputs": [], "cost_usd": 0, "llm_calls": 0}
    started = time.monotonic()
    with (OUT / "reproduction_invocations.jsonl").open("x", encoding="utf8") as journal:
        for path in paths:
            raw = path.read_bytes()
            row = {"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "direct": []}
            expected = "UnicodeDecodeError" if path.name == "latin1_comment.sol" else "Unsupported"
            for name, fn, argument in (("pragma_interval", pragma_interval, [raw]),
                                       ("pragma_patches", pragma_patches, raw)):
                try:
                    fn(argument)
                except Exception as exc:
                    row[name] = {"exception_type": type(exc).__name__, "message": str(exc)}
                else:
                    row[name] = {"exception_type": None}
                assert row[name]["exception_type"] == expected, row
            versions = ("0.4.24", "0.5.17", "0.8.0", "0.8.38") if path.name == "latin1_comment.sol" else ("0.8.38",)
            for version in versions:
                compiled = compile_file(path, compilers[version])
                emit(journal, dict(kind="solc", **asdict(compiled)))
                assert compiled.returncode == 0 and not compiled.timed_out, row
                analysis = run_slither(compiled, profile="production")
                emit(journal, dict(kind="slither", **analysis))
                assert analysis["d3"], analysis
                row["direct"].append({"version": version, "solc_rc": compiled.returncode,
                                      "d3": analysis["d3"], "compiler_sha256": compiled.compiler.sha256})
            result["inputs"].append(row)
            print("Reproduced " + path.name, flush=True)
    argv = ["repair"] + [str(p) for p in paths] + ["--output", str(OUT / "reproduction_cli")]
    result["cli_argv"] = argv
    def check(record, _):
        assert record.status == "unrepaired"
        assert record.flags == ["unsupported_version_constraints"]
        expected = "UnicodeDecodeError" if record.inputs[0]["path"].endswith("latin1_comment.sol") else "Unsupported"
        assert len(record.attempts) == 1 and record.attempts[0]["exception_type"] == expected
    rc = main(argv, result_check=check)
    summary = json.loads((OUT / "reproduction_cli/summary.json").read_text())
    assert rc == 2 and summary["status"] == "unrepaired" and len(summary["units"]) == 6
    result.update(passed=True, reproduced=6, direct_d3_passes=9, cli_returncode=rc,
                  elapsed_seconds=time.monotonic() - started)
    with (OUT / "reproduction.json").open("x", encoding="utf8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k not in ("inputs", "trust", "cli_argv")}), flush=True)


if __name__ == "__main__":
    execute()
