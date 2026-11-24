"""CP6.1: step-5 normalizations (identical duplicates, repeated SPDX/pragmas, pragma terminator, ABI coder)."""
import hashlib
import io
import json

import pytest

from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.provenance import apply_patches
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.rules.normalize import (abi_coder_pragma, duplicate_licenses, duplicate_pragmas,
    identical_duplicates, normalization_repairs, pragma_terminators)
from compile_repair.tests.test_production import production_required, trusted_compilers

IFACE = b"interface I {\n  function f() external view returns (uint);\n}\n"


def _apply(raw, patches):
    return apply_patches(raw, tuple(sorted(patches, key=lambda p: -p.start)))[0]


def _diag(raw, needle, category, message=""):
    at = raw.index(needle)
    line = raw[:at].count(b"\n") + 1
    column = at - (raw.rfind(b"\n", 0, at) + 1) + 1
    return {"category": category, "line": line, "column": column, "message": message}


def test_identical_duplicate_is_blanked_keeping_offsets_and_lines():
    raw = b"pragma solidity ^0.7.0;\n" + IFACE + b"contract C {}\n" + IFACE
    second = raw.rindex(b"interface I")
    row = {"category": "duplicate_definition", "line": raw[:second].count(b"\n") + 1, "column": 1}
    patches, evidence = identical_duplicates(raw, [row])
    out = _apply(raw, patches)
    assert len(out) == len(raw) and out.count(b"\n") == raw.count(b"\n")
    assert out[:second] == raw[:second] and out[second:].strip() == b""
    assert evidence[0]["copies"] == 2 and evidence[0]["blanked"] == 1


@pytest.mark.parametrize("second", [IFACE.replace(b"view", b"pure"), b"contract D {\n" + IFACE.replace(b"interface I", b"struct I") + b"}\n"])
def test_non_identical_or_other_scope_duplicates_are_left_to_later_stages(second):
    raw = b"pragma solidity ^0.7.0;\n" + IFACE + second
    at = raw.rindex(b"interface I") if b"interface I" in second else raw.rindex(b"struct I")
    row = {"category": "duplicate_definition", "line": raw[:at].count(b"\n") + 1,
           "column": at - (raw.rfind(b"\n", 0, at) + 1) + 1}
    patches, evidence = identical_duplicates(raw, [row])
    assert patches == [] and evidence[0].get("reason") in ("not_byte_identical", "no_declaration_at_location")


def test_function_reported_at_first_definition_blanks_the_later_copy():
    body = b"  function f() public {}\n"
    raw = b"pragma solidity ^0.4.24;\ncontract A {\n" + body + body + b"}\n"
    patches, _ = identical_duplicates(raw, [_diag(raw, b"function f", "duplicate_definition")])
    out = _apply(raw, patches)
    assert out.count(b"function f") == 1 and out.index(b"function f") == raw.index(b"function f")


def test_spdx_and_pragma_repeats_only_when_identical():
    spdx = b"// SPDX-License-Identifier: MIT\npragma solidity ^0.8.0;\n// SPDX-License-Identifier: MIT\ncontract A {}\n"
    rows = [{"category": "multiple_license_or_pragma", "message": "Multiple SPDX license identifiers found"}]
    patches, _ = duplicate_licenses(spdx, rows)
    assert _apply(spdx, patches).count(b"SPDX") == 1
    mixed = spdx.replace(b"MIT\ncontract", b"GPL-3.0\ncontract")
    assert duplicate_licenses(mixed, rows)[0] == []
    rows = [{"category": "multiple_license_or_pragma", "message": "Duplicate experimental feature name."}]
    twice = b"pragma experimental ABIEncoderV2;\npragma experimental ABIEncoderV2;\npragma solidity >=0.5.0;\ncontract A {}\n"
    assert _apply(twice, duplicate_pragmas(twice, rows)[0]).count(b"ABIEncoderV2") == 1
    conflict = b"pragma solidity ^0.8.0;\npragma abicoder v1;\npragma abicoder v2;\ncontract A {}\n"
    patches, evidence = duplicate_pragmas(conflict, rows)
    assert patches == [] and evidence[0]["reason"] == "conflicting_abicoder"


@pytest.mark.parametrize("raw,expected", [
    (b"pragma solidity ^0.4.24\ncontract A {}\n", b"pragma solidity ^0.4.24;\ncontract A {}\n"),
    (b"pragma solidity >=0.5.0 <0.7.0\nimport \"./B.sol\";\n", b"pragma solidity >=0.5.0 <0.7.0;\nimport \"./B.sol\";\n"),
    (b"pragma solidity >=0.5.0 < 0.9.0\n\n", b"pragma solidity >=0.5.0 < 0.9.0;\n\n"),
    (b"pragma solidity ^0.4.24 foo\n", None),
    (b"pragma solidity ^0.4.24;\ncontract A {}\n", None),
    (b"// pragma solidity ^0.4.24\ncontract A {}\n", None),
])
def test_pragma_terminator(raw, expected):
    patches = pragma_terminators(raw)
    assert (_apply(raw, patches) if patches else None) == expected


def test_abi_coder_pragma_only_when_needed_and_unselected():
    rows = [{"category": "abi_coder_required"}]
    raw = b"pragma solidity >=0.5.0;\ncontract A {}\n"
    assert _apply(raw, abi_coder_pragma(raw, rows)) == b"pragma solidity >=0.5.0;\npragma experimental ABIEncoderV2;\ncontract A {}\n"
    assert abi_coder_pragma(raw, []) == []
    assert abi_coder_pragma(b"pragma solidity ^0.8.0;\npragma abicoder v1;\ncontract A {}\n", rows) == []


def test_normalization_repairs_skips_overlapping_proposals_and_reports_evidence():
    raw = b"pragma solidity ^0.4.24\ncontract A {}\n"
    edits, patches, evidence = normalization_repairs({"A.sol": raw}, {}, 3)
    assert edits == {"A.sol": raw.replace(b"24\n", b"24;\n", 1)} and patches["A.sol"][0].round == 3
    assert evidence[-1]["rule"] == "applied"


def _run(tmp_path, raw, versions):
    production_required()
    path = tmp_path / "A.sol"
    path.write_bytes(raw)
    unit = CompilationUnit("u", (SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw),))
    store = ArtifactStore(tmp_path / "run")
    compilers = {v: trusted_compilers()[v] for v in versions}
    record = repair_unit(unit, compilers, store, io.StringIO())
    assert path.read_bytes() == raw
    steps = json.loads((store.path / "units/u/repair_steps.json").read_bytes())
    return record, [s for s in steps if s["step"] == 5], store.path / "units/u"


@pytest.mark.parametrize("name,raw,versions,level", [
    ("duplicate", b"// SPDX-License-Identifier: MIT\npragma solidity ^0.7.0;\n" + IFACE + b"contract C {}\n" + IFACE,
     ("0.7.6",), "rewrite"),
    ("terminator", b"pragma solidity ^0.4.24\ncontract A { function f() public pure returns (uint) { return 1; } }\n",
     ("0.4.24",), "additive"),
    ("abi_coder", b"pragma solidity ^0.5.0;\ncontract A { function f(uint[][] memory x) public pure returns (uint) { return x.length; } }\n",
     ("0.5.17",), "additive"),
    ("terminator_at_eof", b"pragma solidity >=0.5.0 < 0.9.0\n\n", ("0.8.38",), "additive"),
    ("spdx", b"// SPDX-License-Identifier: MIT\npragma solidity ^0.8.0;\n// SPDX-License-Identifier: MIT\ncontract A {}\n",
     ("0.8.38",), "rewrite"),
])
def test_pipeline_repairs_with_step_5(tmp_path, name, raw, versions, level):
    record, steps, folder = _run(tmp_path, raw, versions)
    assert record.status == "success" and (folder / "graph.json").exists(), name
    accepted = [s for s in steps if s["accepted"]]
    assert accepted and accepted[-1]["status"] == "success"
    provenance = next(iter(record.provenance.values()))
    assert provenance.level == level and all(c.step == "normalize" for c in provenance.changes)


def test_conflicting_abicoder_is_not_chosen(tmp_path):
    raw = b"pragma solidity ^0.8.0;\npragma abicoder v1;\npragma abicoder v2;\ncontract A {}\n"
    record, steps, folder = _run(tmp_path, raw, ("0.8.38",))
    assert record.status != "success" and not any(s["accepted"] for s in steps)


def test_diagnostics_reported_by_several_versions_are_kept_once(tmp_path):
    from types import SimpleNamespace
    from compile_repair.pipeline import _diagnostics_by_file
    stderr = ("DeclarationError: Identifier already declared.\n --> {}/A.sol:3:1:\n  |\n3 | interface I {{}}\n"
              "  | ^^^^^^^^^^^^^^\n").format(tmp_path)
    attempts = [dict(version=v, solc=dict(returncode=1, timed_out=False, stderr=stderr, cwd=str(tmp_path)))
                for v in ("0.7.5", "0.7.6")]
    rows = _diagnostics_by_file(SimpleNamespace(attempts=attempts), {"A.sol"})
    assert len(rows["A.sol"]) == 1 and rows["A.sol"][0]["versions"] == ["0.7.5", "0.7.6"]
    assert rows["A.sol"][0]["category"] == "duplicate_definition" and rows["A.sol"][0]["line"] == 3
