"""CP6.5: documented version migrations, NatSpec tags, tuple-call rewrite, pragma disjunction, struct stubs."""
import hashlib
import io
import json

import pytest

from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.provenance import apply_patches
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.rules.environment import disjunction_plan, pragma_interval
from compile_repair.rules.normalize import (documented_migrations, migration_versions, natspec_parameters,
    tuple_call_rewrites)
from compile_repair.rules.stubs import declaration_stubs
from compile_repair.tests.test_production import production_required, trusted_compilers
from scripts.DFG.models import Unsupported

MIGRATIONS = {
    "visibility": b"contract A { uint x; function f() { x = 1; } }\n",
    "constant": b"contract A { uint x; function f() public constant returns (uint) { return x; } }\n",
    "constructor": b"contract A { uint x; function A() public { x = 1; } }\n",
    "emit": b"contract A { event E(uint v); function f() public { E(1); } }\n",
    "builtins": (b"contract A { function f(uint a, bytes32 b) public returns (bytes32, uint, uint, bytes32) {"
                 b" bytes32 h = sha3(a, b); uint g = msg.gas; uint t = now; bytes32 bh = block.blockhash(1);"
                 b" return (h, g, t, bh); } function k() public { suicide(msg.sender); } }\n"),
    "years": b"contract A { function f() public pure returns (uint) { return 2 years; } }\n",
    "fallback": b"contract A { uint x; function() external payable { x = 1; } }\n",
    "unicode": b'contract A { function f() public pure returns (string memory) { return "h\xc3\xa9llo"; } }\n',
    "payable": b"contract A { address owner; function f() public { owner.transfer(1); msg.sender.transfer(2); } }\n",
    "natspec": b"contract A {\n  /// @param y the value\n  function f(uint x) public pure returns (uint) { return x; }\n}\n",
}
# The versions on which each input fails and must be repaired (fallback needs 0.6, unicode 0.7).
VERSIONS = {name: ("0.5.0", "0.5.17", "0.6.12", "0.7.6", "0.8.38") for name in MIGRATIONS}
VERSIONS["fallback"] = ("0.6.12", "0.7.6", "0.8.38")
VERSIONS["unicode"] = ("0.7.6", "0.8.38")


def _run(tmp_path, raw, version, name="A.sol"):
    production_required()
    path = tmp_path / name
    path.write_bytes(raw)
    unit = CompilationUnit("u", (SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw),))
    store = ArtifactStore(tmp_path / "run")
    record = repair_unit(unit, {version: trusted_compilers()[version]}, store, io.StringIO())
    assert path.read_bytes() == raw
    return record


@pytest.mark.parametrize("name,version", [(n, v) for n in MIGRATIONS for v in VERSIONS[n]])
def test_documented_migration_repairs_every_affected_version(tmp_path, name, version):
    record = _run(tmp_path, MIGRATIONS[name], version)
    assert record.status == "success", (name, version)
    steps = {c.step for p in record.provenance.values() for c in p.changes}
    assert steps == {"migrate"}


def _patched(raw, patches):
    return apply_patches(raw, tuple(sorted(patches, key=lambda p: -p.start)))[0]


def test_migrations_rewrite_only_the_old_spelling():
    rows = [{"message": '"sha3" has been deprecated in favour of "keccak256".', "versions": ["0.5.17"]}]
    raw = MIGRATIONS["builtins"]
    out = _patched(raw, documented_migrations(raw, rows)[0])
    assert b"keccak256(abi.encodePacked(a, b))" in out and b"selfdestruct(msg.sender)" in out
    assert b"gasleft()" in out and b"blockhash(1)" in out
    assert b"uint t = now;" in out  # now is still valid before 0.7.0
    out = _patched(MIGRATIONS["years"], documented_migrations(MIGRATIONS["years"],
                   [{"message": 'Using "years" as a unit denomination is deprecated.'}])[0])
    assert b"return (2 * 365 days);" in out


def test_migrations_need_a_migration_diagnostic():
    assert migration_versions([{"message": "Expected ';' but got identifier"}]) is None
    assert documented_migrations(MIGRATIONS["visibility"], []) == ([], [])


def test_transfer_on_contract_types_is_left_alone():
    """An ERC-20 transfer takes two arguments and its base is a token, not an address."""
    raw = (b"contract T { function transfer(address, uint) public returns (bool); }\n"
           b"contract A { T token; address owner; function f() public { token.transfer(owner, 1); owner.transfer(1); } }\n")
    rows = [{"message": '"send" and "transfer" are only available for objects of type "address payable", not "address".',
             "versions": ["0.6.12"]}]
    out = _patched(raw, documented_migrations(raw, rows)[0])
    assert b"token.transfer(owner, 1)" in out and b"payable(owner).transfer(1)" in out


def test_natspec_parameter_lines_are_blanked():
    raw = MIGRATIONS["natspec"]
    rows = [{"message": 'Documented parameter "y" not found in the parameter list of the function.'}]
    patches, evidence = natspec_parameters(raw, rows)
    out = _patched(raw, patches)
    assert len(out) == len(raw) and b"@param" not in out and evidence == [dict(parameter="y")]


# ---- tuple-call rewrite (step 10, PROMPTS 1.7) -------------------------------------------

TUPLE = (b"pragma solidity ^0.4.24;\ncontract W {\n  function pay(address to) public {\n"
         b'    (bool ok, ) = to.call.value(1)("");\n    require(ok);\n  }\n}\n')
ASSERTION = ["AssertionError:  [solc 0.4.24]"]


def test_tuple_call_declaration_becomes_a_bool_declaration():
    out = _patched(TUPLE, tuple_call_rewrites(TUPLE, ASSERTION)[0])
    assert out == TUPLE.replace(b"(bool ok, ) =", b"bool ok =")
    assert tuple_call_rewrites(TUPLE, ["AssertionError:  [solc 0.5.17]"]) == ([], [])


def test_pipeline_rewrites_the_tuple_call_for_slither(tmp_path):
    record = _run(tmp_path, TUPLE, "0.4.24")
    assert record.status == "success"
    assert {c.step for p in record.provenance.values() for c in p.changes} == {"slither_compat"}


def test_tuple_rewrite_keeps_the_version_solc_accepted(tmp_path):
    """The rewritten line also compiles on 0.4.12; the trial keeps 0.4.24, where solc passed."""
    production_required()
    raw = TUPLE.replace(b"^0.4.24", b"^0.4.0")
    path = tmp_path / "A.sol"
    path.write_bytes(raw)
    unit = CompilationUnit("u", (SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw),))
    versions = ("0.4.12", "0.4.24")
    record = repair_unit(unit, {v: trusted_compilers()[v] for v in versions}, ArtifactStore(tmp_path / "run"),
                         io.StringIO())
    assert record.status == "success" and record.selected_version == "0.4.24"


# ---- pragma disjunction (D6 unsupported_disjunction) -------------------------------------

def _versions(*values):
    return {v: None for v in values}


@pytest.mark.parametrize("pragma,expected", [
    (b"^0.4.24 || ^0.6.0", (("0.4.24", "0.4.26"), ("0.6.12",))),
    (b">=0.4.22 <0.6.0 || ^0.8.0", (("0.4.24", "0.4.26"), ("0.5.17",), ("0.8.38",))),
])
def test_disjunction_tries_the_union_of_its_alternatives(pragma, expected):
    raw = [b"pragma solidity " + pragma + b";\ncontract A {}\n"]
    with pytest.raises(Unsupported):
        pragma_interval(raw)  # the frozen reader is unchanged
    plan = disjunction_plan(raw, _versions("0.4.24", "0.4.26", "0.5.17", "0.6.12", "0.7.6", "0.8.38"))
    assert plan.groups == expected and plan.origin == "pragma_disjunction" and not plan.override


def test_disjunction_intersects_sources():
    raw = [b"pragma solidity ^0.4.24 || ^0.6.0;\n", b"pragma solidity >=0.5.0;\n"]
    plan = disjunction_plan(raw, _versions("0.4.26", "0.5.17", "0.6.12"))
    assert plan.groups == (("0.6.12",),)


@pytest.mark.parametrize("pragma", [b"^0.4.24 ||", b"^0.4.24 || foo", b"^0.4.24"])
def test_malformed_disjunction_stays_unsupported(pragma):
    with pytest.raises(Unsupported):
        disjunction_plan([b"pragma solidity " + pragma + b";\ncontract A {}\n"], _versions("0.4.26"))


def test_pipeline_compiles_a_disjunction(tmp_path):
    raw = b"pragma solidity ^0.4.24 || ^0.6.0;\ncontract A { function f() public pure returns (uint) { return 1; } }\n"
    production_required()
    path = tmp_path / "A.sol"
    path.write_bytes(raw)
    unit = CompilationUnit("u", (SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw),))
    versions = ("0.5.17", "0.6.12")
    record = repair_unit(unit, {v: trusted_compilers()[v] for v in versions}, ArtifactStore(tmp_path / "run"),
                         io.StringIO())
    assert record.status == "success" and record.selected_version == "0.6.12"
    assert "pragma_disjunction" in record.flags and len(record.attempts) == 1


# ---- struct stubs ------------------------------------------------------------------------

STRUCT = (b"pragma solidity ^0.5.0;\ncontract C {\n  function f(address a) public returns (uint) {\n"
          b"    Info memory i = Info({owner: a, amount: 5});\n    return i.amount;\n  }\n}\n")


def _row(raw, needle):
    at = raw.index(needle)
    return [dict(category="undeclared_identifier", line=raw[:at].count(b"\n") + 1, column=at - raw.rfind(b"\n", 0, at))]


def test_struct_stub_from_named_construction():
    patches, evidence = declaration_stubs(STRUCT, _row(STRUCT, b"Info memory"))
    assert evidence[0]["stub"] == "struct Info { address owner; uint256 amount; }"
    assert _patched(STRUCT, patches).startswith(b"pragma solidity ^0.5.0;\ncontract C { struct Info {")


@pytest.mark.parametrize("change", [
    (b"return i.amount;", b"return i.total;"),           # a field no construction names
    (b"Info({owner: a, amount: 5})", b"Info(a, 5)"),     # positional: names unknown
])
def test_struct_stub_needs_every_field_proven(change):
    raw = STRUCT.replace(*change)
    patches, evidence = declaration_stubs(raw, _row(raw, b"Info memory"))
    assert patches == [] and evidence[0].get("reason") in ("unknown_struct_fields", "mixed_or_unknown_use")


def test_pipeline_declares_a_struct_stub(tmp_path):
    record = _run(tmp_path, STRUCT, "0.5.17")
    assert record.status == "success"
    assert {c.step for p in record.provenance.values() for c in p.changes} == {"stub"}
