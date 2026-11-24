"""CP2.4: comment-bearing pragmas, separate syntax errors and CP2.3 equivalence."""
import hashlib
import importlib.util
import io
import json
import re
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path

import pytest

from compile_repair.core.model import CompilationUnit, Compiler, EnvironmentPlan, SourceFile
from compile_repair.core.provenance import apply_patches, verify_provenance
from compile_repair.core.store import ArtifactStore, read_checked_json
from compile_repair.pipeline import repair_unit
from compile_repair.rules.environment import make_plan, pragma_interval, pragma_patches
from compile_repair.toolchain.solc import ADDITION_SHA256, CP0_SHA256
from scripts.DFG.models import Unsupported

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "compile_repair/tests/fixtures"
NEW = FIXTURES / "pragma_comments"
REFERENCE = ROOT / "compile_repair/artifacts/cp2_4_v1/environment_cp23.py"
REFERENCE_SHA = "f0d4f4b9274532c0b3760d67341f37dba7f2f81430d9aad091f42644483429e0"


def cp23():
    """Load the hash-bound, unmodified CP2.3 reference, only in tests."""
    assert hashlib.sha256(REFERENCE.read_bytes()).hexdigest() == REFERENCE_SHA
    spec = importlib.util.spec_from_file_location("cp24_reference_environment", str(REFERENCE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def serial(value):
    if is_dataclass(value):
        return serial(asdict(value))
    if isinstance(value, bytes):
        return {"hex": value.hex()}
    if isinstance(value, (tuple, list)):
        return [serial(item) for item in value]
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    return value


def test_cp24_equivalence_all_readable_inputs(tmp_path):
    old = cp23()
    cp0 = read_checked_json(ROOT / "compile_repair/artifacts/cp0_v2/recon.json", CP0_SHA256)
    addition = read_checked_json(
        ROOT / "compile_repair/artifacts/cp0_1_compilers_v1/trusted_compilers_addition.json",
        ADDITION_SHA256)
    versions = sorted(set(cp0["compilers"]) | set(addition["compilers"]))
    assert len(versions) == 96
    assert sum((0, 4, 12) <= tuple(map(int, v.split("."))) < (0, 9, 0) for v in versions) == 92
    records, excluded = [], []
    sources = [(ROOT / row["path"], "mando", row) for row in cp0["inputs"]]
    sources += [(p, "fixtures", None) for p in sorted(FIXTURES.rglob("*")) if p.is_file()]
    for path, group, row in sources:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if row is not None:
            assert digest == row["sha256"]
        try:
            previous = old.pragma_interval([raw])
        except Unsupported as exc:
            assert group == "fixtures"
            excluded.append({"path": str(path.relative_to(ROOT)), "sha256": digest,
                             "exception_type": type(exc).__name__, "error": str(exc)})
            continue
        assert pragma_interval([raw]) == previous, str(path)
        old_patches = old.pragma_patches(raw)
        assert pragma_patches(raw) == old_patches, str(path)
        known = row["metadata"]["version"] if row and row["metadata"] else None
        regression = "mando" if row else None
        plans = {}
        for order in ("ascending", "descending"):
            before = asdict(old.make_plan([raw], versions, known, regression, order))
            after = asdict(make_plan([raw], versions, known, regression, order))
            assert set(after) == {field.name for field in fields(EnvironmentPlan)}
            assert after == before, (str(path), order)
            plans[order] = after
        records.append({"path": str(path.relative_to(ROOT)), "sha256": digest,
                        "group": group, "interval": previous, "patches": old_patches,
                        "plans": plans, "interval_equal": True, "patches_equal": True,
                        "all_plan_fields_equal": True})
    assert sum(r["group"] == "mando" for r in records) == 846
    assert {Path(r["path"]).name for r in excluded} == {
        "comment_inside.sol", "line_comment_inside.sol", "missing_semicolon.sol", "union_pragma.sol",
        # CP3 adds explicit negative constraint fixtures; all readable inputs
        # above still undergo exact old/new interval, patch and plan checks.
        "swallowed_directive.sol", "unsupported_expression.sol", "conflicting_pragma.sol",
        "unterminated.sol", "union.sol"}
    evidence = {"reference_sha256": REFERENCE_SHA, "compiler_versions": versions,
                "plan_fields": [f.name for f in fields(EnvironmentPlan)],
                "records": records, "excluded": excluded}
    (tmp_path / "equivalence.json").write_text(json.dumps(serial(evidence), sort_keys=True))


@pytest.mark.parametrize("name,expected", [
    ("comment_inside.sol", ((0, 8, 0), (0, 9, 0))),
    ("line_comment_inside.sol", ((0, 5, 0), (0, 6, 0))),
])
def test_comment_constraints_and_original_patch_bytes(name, expected):
    raw = (NEW / name).read_bytes()
    assert pragma_interval([raw]) == expected
    old = cp23()
    with pytest.raises(Unsupported, match="^F: unsupported pragma expression$"):
        old.pragma_interval([raw])
    patches = pragma_patches(raw)
    assert patches == old.pragma_patches(raw)
    copy, provenance = apply_patches(raw, patches)
    verify_provenance(raw, copy, provenance)
    assert len(copy) == len(raw)
    assert copy.index(b"contract") == raw.index(b"contract")
    assert [(i, b) for i, b in enumerate(raw) if b in (10, 13)] == [
        (i, b) for i, b in enumerate(copy) if b in (10, 13)]
    assert pragma_interval([copy]) is None
    assert all(p.expected == raw[p.start:p.end] for p in patches)


def test_comments_mask_fake_delimiters_and_keep_crlf_latin1():
    raw = (b"pragma /* ;{} */ solidity >=0.5.0 /* cafe\xe9; } */"
           b" <0.6.0 // ignored ; { pragma solidity 0.4.0;\r\n;\r\ncontract C {}")
    assert pragma_interval([raw]) == ((0, 5, 0), (0, 6, 0))
    patches = pragma_patches(raw)
    assert len(patches) == 1 and patches[0].end == raw.index(b"\r\n;") + 3
    assert patches[0].replacement == re.sub(rb"[^\r\n]", b" ", patches[0].expected)
    assert make_plan([raw], ["0.5.0", "0.5.17"]).groups == (("0.5.0", "0.5.17"),)


@pytest.mark.parametrize("tail", [
    b"", b" { contract C {};", b" } ;", b" // ;\n", b" /* ; {} */",
])
def test_unterminated_directive_distinguished_at_braces_and_eof(tail):
    raw = b"pragma solidity ^0.5.0" + tail
    for fn, argument in ((pragma_interval, [raw]), (pragma_patches, raw)):
        with pytest.raises(Unsupported, match="^F: unterminated pragma directive$"):
            fn(argument)
    with pytest.raises(Unsupported, match="^F: unterminated pragma directive$"):
        make_plan([raw], ["0.5.0"])


@pytest.mark.parametrize("raw,error", [
    (b"pragma solidity ^0.4.0 || ^0.5.0;", "F: unsupported pragma expression"),
    (b"pragma solidity *;", "F: unsupported pragma expression"),
    (b"pragma solidity >=0.5.0 <0.5.0;", "F: empty pragma intersection"),
])
def test_other_expression_diagnostics_unchanged(raw, error):
    for module in (cp23(),):
        with pytest.raises(Unsupported) as previous:
            module.pragma_interval([raw])
        assert str(previous.value) == error
    with pytest.raises(Unsupported) as current:
        pragma_interval([raw])
    assert str(current.value) == error


@pytest.mark.parametrize("name,error", [
    ("missing_semicolon.sol", "F: unterminated pragma directive"),
    ("union_pragma.sol", "F: unsupported pragma expression"),
])
def test_pipeline_records_error_without_calling_tools(tmp_path, name, error):
    """The environment stage records the constraint error and calls no tool.

    Since CP6.1 the repair steps then insert a missing pragma terminator (test_cp61);
    environment_only keeps this check to the stage that CP2.4 specified.
    """
    path = (NEW if name == "missing_semicolon.sol" else FIXTURES / "pragma_inputs") / name
    raw = path.read_bytes()
    source = SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw)
    unit = CompilationUnit("probe", (source,))
    calls = []
    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("An invalid pragma must not invoke a tool")
    store = ArtifactStore(tmp_path / "store")
    journal = io.StringIO()
    record = repair_unit(unit, {"0.5.0": Compiler("0.5.0", "/unused", "unused")},
                         store, journal, compile_fn=forbidden, slither_fn=forbidden, environment_only=True)
    assert record.status == "unrepaired" and record.flags == ["unsupported_version_constraints"]
    assert record.attempts == [{"stage": "environment_plan", "exception_type": "Unsupported",
                                "error_first_line": error}]
    assert calls == [] and journal.getvalue() == ""


def test_real_cp24_cli_comments_and_errors(tmp_path):
    from compile_repair.tests.test_production import production_required
    from compile_repair.cli import main
    production_required()
    paths = [NEW / name for name in ("comment_inside.sol", "line_comment_inside.sol",
                                    "missing_semicolon.sol")]
    paths.append(FIXTURES / "pragma_inputs/union_pragma.sol")
    output = tmp_path / "cli"
    def accept(record, directory):
        index = int(record.unit_id.rsplit("_", 1)[1]) - 1
        if index < 2:
            assert record.status == "success"
            assert record.selected_version == ("0.8.0", "0.5.0")[index]
            assert not record.flags and not record.settings
            assert record.attempts[-1]["solc"]["returncode"] == 0
            assert record.attempts[-1]["slither"]["d3"]
            assert record.attempts[-1]["slither"]["profile"] == "production"
            assert record.provenance[str(paths[index])].level == "none"
            assert (directory / "units" / record.unit_id / "input.sol").read_bytes() == paths[index].read_bytes()
        elif index == 2:
            # CP6.1: step 5 inserts the missing terminator; the environment error stays recorded.
            environment = json.loads((directory / "units" / record.unit_id / "environment_result.json").read_bytes())
            assert environment["attempts"][0]["error_first_line"] == "F: unterminated pragma directive"
            assert record.status == "success" and record.selected_version.startswith("0.5.")
            assert record.attempts[-1]["slither"]["d3"]
            proof = next(iter(record.provenance.values()))
            assert proof.level == "additive" and [c.new for c in proof.changes] == [b";"]
        else:
            assert record.status == "unrepaired"
            assert record.flags == ["unsupported_version_constraints"]
            assert len(record.attempts) == 1
            assert record.attempts[0]["error_first_line"] == "F: unsupported pragma expression"
    assert main(["repair"] + list(map(str, paths)) + ["--output", str(output)],
                result_check=accept) == 2
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == "unrepaired" and len(summary["units"]) == 4
    invocations = [json.loads(line) for line in (output / "invocations.jsonl").read_text().splitlines()]
    # Two tool calls per success; the unterminated pragma is compiled once repaired (CP6.1).
    assert len(invocations) == 6
    assert {r["unit_id"] for r in invocations} == {"input_0001", "input_0002", "input_0003"}
