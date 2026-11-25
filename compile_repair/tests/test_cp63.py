"""CP6.3: step-7 declaration stubs inferred only from how undeclared names are used."""
import hashlib
import io
import json

import pytest

from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.provenance import apply_patches
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.rules.stubs import declaration_stubs, stub_repairs
from compile_repair.tests.test_production import production_required, trusted_compilers

OWNED = (b"pragma solidity ^0.5.0;\ncontract A is Owned {\n  constructor(address o) Owned(o) public {}\n"
         b"  function f() public onlyOwner { emit Paid(msg.sender, 1); }\n}\n")
TOKEN = (b"pragma solidity ^0.8.0;\ncontract B {\n  IERC20 public token;\n  function g(address a) public {\n"
         b"    uint256 b = token.balanceOf(a);\n    require(IERC20(a).transfer(msg.sender, b));\n"
         b"    token.approve(a, 5);\n  }\n}\n")


def _rows(raw, needles, category="undeclared_identifier"):
    rows = []
    for needle in needles:
        at = raw.index(needle)
        rows.append({"category": category, "line": raw[:at].count(b"\n") + 1,
                     "column": at - (raw.rfind(b"\n", 0, at) + 1) + 1})
    return rows


def _apply(raw, patches):
    return apply_patches(raw, tuple(sorted(patches, key=lambda p: -p.start)))[0]


def test_base_modifier_and_event_stubs():
    patches, evidence = declaration_stubs(OWNED, _rows(OWNED, [b"Owned", b"onlyOwner", b"Paid"]))
    out = _apply(OWNED, patches)
    assert b"contract Owned { constructor(address _s0) public {} }\ncontract A is Owned {" in out
    assert b"contract A is Owned { event Paid(address, uint256); modifier onlyOwner() { _; }\n" in out
    assert {e["name"]: e["uses"] for e in evidence} == {"Owned": ["base"], "Paid": ["event"], "onlyOwner": ["modifier"]}
    # Only insertions: the original bytes are a subsequence at their old relative order.
    assert out.replace(b"contract Owned { constructor(address _s0) public {} }\n", b"").replace(
        b" event Paid(address, uint256); modifier onlyOwner() { _; }", b"") == OWNED


def test_interface_lists_exactly_the_called_functions():
    patches, _ = declaration_stubs(TOKEN, _rows(TOKEN, [b"IERC20"], "missing_base_contract"))
    out = _apply(TOKEN, patches)
    assert out.startswith(b"pragma solidity ^0.8.0;\ninterface IERC20 { function approve(address _s0, uint256 _s1) external;"
                          b" function balanceOf(address _s0) external returns (uint256);"
                          b" function transfer(address _s0, uint256 _s1) external returns (bool); }\ncontract B {")


@pytest.mark.parametrize("raw,needle,reason", [
    # A plain call or a struct-like use says nothing about a declaration.
    (b"contract C { function h() public { f(1); } }\n", b"f(1)", "mixed_or_unknown_use"),
    (b"contract C { function h() public { s memory x; } }\n", b"s memory", "mixed_or_unknown_use"),
    # Call sites that disagree on the argument types.
    (b"contract C { function h(bool k) public { emit E(1); emit E(k); } }\n", b"E(1)", "unknown_or_disagreeing_types"),
    # An argument whose type cannot be read from the file.
    (b"contract C { function h() public { emit E(foo()); } }\n", b"E(foo", "unknown_or_disagreeing_types"),
    # A member read instead of called, so no interface can be written.
    (b"contract C { I public i; function h() public { uint256 v = i.x; } }\n", b"I public", "unknown_member_signature"),
])
def test_uses_that_prove_nothing_are_skipped(raw, needle, reason):
    patches, evidence = declaration_stubs(raw, _rows(raw, [needle]))
    assert patches == [] and evidence[0]["reason"] == reason


def test_keywords_and_unbalanced_files_are_not_stubbed():
    raw = b"contract C { function h() public virtual {} }\n"
    assert declaration_stubs(raw, _rows(raw, [b"virtual"])) == ([], [])
    raw = b"contract C { function h() public onlyOwner {\n"
    assert declaration_stubs(raw, _rows(raw, [b"onlyOwner"])) == ([], [dict(reason="unbalanced")])
    assert declaration_stubs(OWNED, [{"category": "type_error_other", "line": 2, "column": 1}]) == ([], [])


def test_stub_repairs_reports_per_file():
    edits, patches, evidence = stub_repairs({"A.sol": OWNED}, {"A.sol": _rows(OWNED, [b"Paid"])}, 6)
    assert edits["A.sol"].count(b"event Paid(address, uint256);") == 1 and patches["A.sol"][0].round == 6
    assert patches["A.sol"][0].step == "stub" and evidence[-1]["rule"] == "applied"


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
    return record, steps, store.path / "units/u"


@pytest.mark.parametrize("name,raw,versions,steps_used", [
    ("owned", OWNED, ("0.5.17",), {"stub"}),
    ("token", TOKEN, ("0.8.38",), {"stub"}),
    # Step 8 wraps the fragment; step 7 then declares the modifier and the event inside it.
    ("fragment", b"function f() public onlyOwner { emit Paid(msg.sender); }\n", ("0.4.24",), {"structure", "stub"}),
])
def test_pipeline_declares_stubs(tmp_path, name, raw, versions, steps_used):
    record, steps, folder = _run(tmp_path, raw, versions)
    assert record.status == "success" and (folder / "graph.json").exists(), name
    provenance = next(iter(record.provenance.values()))
    assert provenance.level == "additive" and {c.step for c in provenance.changes} == steps_used
    assert any(s["step"] == 7 and s["accepted"] for s in steps)


def test_plain_undeclared_call_stays_unrepaired(tmp_path):
    record, steps, _ = _run(tmp_path, b"pragma solidity ^0.8.0;\ncontract C { function h() public { f(1); } }\n",
                            ("0.8.38",))
    assert record.status != "success" and not any(s["accepted"] for s in steps)
