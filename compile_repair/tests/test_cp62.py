"""CP6.2: step-8 structure completion and D27 phase progress."""
import hashlib
import io
import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.provenance import apply_patches
from compile_repair.core.store import ArtifactStore
from compile_repair.evaluation.report import primary_causes
from compile_repair.pipeline import _failure_phase, repair_unit
from compile_repair.rules.stubs import structure_completion, structure_repairs
from compile_repair.tests.test_production import production_required, trusted_compilers

PARSER = {"category": "parser_error_other", "line": 1, "column": 1}


def _apply(raw, patches):
    return apply_patches(raw, tuple(sorted(patches, key=lambda p: -p.start)))[0]


def test_missing_closing_braces_are_appended_at_the_end():
    raw = b"pragma solidity ^0.5.0;\ncontract A {\n  function f() public {\n"
    patches, evidence = structure_completion(raw, [PARSER])
    assert _apply(raw, patches) == raw + b"\n}}\n"
    assert {"rule": "closing_braces", "added": 2} in evidence


@pytest.mark.parametrize("raw,unclosed,stray", [
    (b"contract A {\n}\n}\n", [], True),
    (b"contract A {\n function f(uint a {\n", ["{", "(", "{"], False),
])
def test_ambiguous_brackets_are_left_alone(raw, unclosed, stray):
    patches, evidence = structure_completion(raw, [PARSER])
    assert patches == [] and evidence == [dict(reason="ambiguous_brackets", unclosed=unclosed, stray_closer=stray)]


def test_diagnosed_members_are_wrapped_and_name_avoids_collisions():
    raw = b"uint public Fragment;\nfunction f() public {}\n\nevent E(uint a);\n"
    patches, evidence = structure_completion(raw, [PARSER])
    out = _apply(raw, patches)
    assert out == b"contract Fragment1 { uint public Fragment;\nfunction f() public {}\n\nevent E(uint a);\n\n}\n"
    assert evidence[0]["members"] == 3 and evidence[0]["kinds"] == ["event", "function", "uint"]


def test_wrapper_and_closing_braces_share_the_end_of_file():
    raw = b"function f() public {\n  if (true) {\n"
    out = _apply(raw, structure_completion(raw, [PARSER])[0])
    assert out == b"contract Fragment { function f() public {\n  if (true) {\n}}\n}\n"


def test_only_runs_with_a_diagnostic_are_wrapped():
    raw = b"pragma solidity ^0.8.0;\nfunction g() pure returns (uint) { return 1; }\ncontract C {}\nuint public x;\n"
    row = {"category": "file_level_member", "line": 4, "column": 1}
    out = _apply(raw, structure_completion(raw, [row])[0])
    assert out == raw.replace(b"uint public x;\n", b"contract Fragment { uint public x;\n\n}\n")


def test_statements_and_non_parser_errors_are_not_wrapped():
    raw = b"require(x > 0);\nx = 1;\n"
    patches, evidence = structure_completion(raw, [PARSER])
    assert patches == [] and evidence == [dict(reason="no_fragment")]
    assert structure_completion(b"function f() {}\n", [{"category": "undeclared_identifier"}]) == ([], [])


def test_structure_repairs_reports_per_file():
    edits, patches, evidence = structure_repairs({"A.sol": b"contract A {\n"}, {"A.sol": [PARSER]}, 4)
    assert edits == {"A.sol": b"contract A {\n\n}\n"} and patches["A.sol"][0].round == 4
    assert evidence[-1]["rule"] == "applied"


def _record(stderr, status="unrepaired"):
    attempt = dict(stage="compile", version="0.8.38", solc=dict(returncode=1, timed_out=False, stderr=stderr))
    return SimpleNamespace(status=status, attempts=[attempt], inputs=[])


@pytest.mark.parametrize("stderr,phase", [
    ("Error: Expected pragma, import directive or contract/interface/library/struct/enum definition.\n"
     " --> A.sol:1:1:\n", 1),
    ("DeclarationError: Undeclared identifier.\n --> A.sol:2:5:\n", 3),
    ("Error: Undeclared identifier.\n --> A.sol:2:5:\n", 3),
    ("TypeError: Type uint256 is not implicitly convertible to expected type bool.\n --> A.sol:2:5:\n", 4),
    ("CompilerError: Stack too deep, try removing local variables.\n --> A.sol:2:5:\n", 5),
])
def test_failure_phase_follows_the_compiler_pipeline(stderr, phase):
    assert _failure_phase(_record(stderr)) == phase


def test_failure_phase_is_unknown_for_unclassified_errors():
    assert _failure_phase(_record("Internal compiler error: Solidity assertion failed\n")) is None
    assert _failure_phase(SimpleNamespace(status="success", attempts=[], inputs=[])) is None


def _run(tmp_path, raw, versions):
    production_required()
    path = tmp_path / "A.sol"
    path.write_bytes(raw)
    unit = CompilationUnit("u", (SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw),))
    store = ArtifactStore(tmp_path / "run")
    record = repair_unit(unit, {v: trusted_compilers()[v] for v in versions}, store, io.StringIO())
    assert path.read_bytes() == raw
    receipt = store.path / "units/u/repair_steps.json"
    steps = json.loads(receipt.read_bytes()) if receipt.exists() else []
    return record, [s for s in steps if s["step"] == 8], store.path / "units/u"


@pytest.mark.parametrize("name,raw,versions", [
    ("fragment", b"function f() public pure returns (uint) { return 1; }\nuint public x;\n", ("0.4.24",)),
    ("unclosed", b"pragma solidity ^0.5.0;\ncontract A {\n  function f() public pure returns (uint) { return 1; }\n",
     ("0.5.17",)),
    ("visibility_0_8", b"pragma solidity ^0.8.0;\nfunction f() public pure returns (uint) { return 1; }\n", ("0.8.38",)),
])
def test_pipeline_completes_structure(tmp_path, name, raw, versions):
    record, steps, folder = _run(tmp_path, raw, versions)
    assert record.status == "success" and (folder / "graph.json").exists(), name
    accepted = [s for s in steps if s["accepted"]]
    assert accepted and accepted[-1]["accepted_by"] == "success"
    provenance = next(iter(record.provenance.values()))
    assert provenance.level == "additive" and all(c.step == "structure" for c in provenance.changes)


def test_phase_progress_is_accepted_and_attributed(tmp_path):
    """D27: wrapping removes the parser error; the undeclared name is now the blocker."""
    record, steps, _ = _run(tmp_path, b"function f() public { by1 = 1; }\n", ("0.4.24",))
    assert record.status != "success"
    accepted = [s for s in steps if s["accepted"]]
    assert accepted[0]["accepted_by"] == "phase_advanced"
    assert (accepted[0]["phase_before"], accepted[0]["phase_after"]) == (1, 3)
    assert primary_causes(asdict(record))["categories"] == ["undeclared_identifier"]


def test_valid_free_function_is_not_moved(tmp_path):
    raw = b"pragma solidity ^0.8.0;\nfunction g() pure returns (uint) { return x; }\n"
    record, steps, _ = _run(tmp_path, raw, ("0.8.38",))
    assert record.status != "success" and not any(s["accepted"] for s in steps)
