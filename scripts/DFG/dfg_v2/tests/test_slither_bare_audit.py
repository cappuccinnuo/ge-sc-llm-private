"""Parser-only fixtures; Solidity compilation is not claimed."""
import json
from pathlib import Path
import pytest

from scripts.DFG.dfg_v2.slither_align import SourceFacts
from scripts.DFG.dfg_v2.slither_bare_audit import check_shape, run


def shape(statement, receiver="address to"):
    ast = SourceFacts("contract C { function f(uint x, " + receiver + ") public {" + statement + "} }")
    node = next(n for n in ast.nodes if n.type == "expression_statement" and ast.text(n) == statement)
    return check_shape(ast, [node.start_byte, node.end_byte])


@pytest.mark.parametrize("statement", ["x;", "(x);", "to.call.value(x);", "to.call.gas(x);"])
def test_exact_bare_forms(statement):
    assert shape(statement)["accepted"] is True


@pytest.mark.parametrize("statement", [
    'to.call.value(x)();', 'to.call.value(x)("");', 'to.call.gas(x)();',
    'to.call("");', 'g(x);', 'x=x+1;', 'to.value(x);',
])
def test_actual_calls_and_assignments_rejected(statement):
    assert shape(statement)["accepted"] is False


def test_outer_invocation_is_explicitly_reported():
    row = shape("to.call.value(x)();")
    assert row["outer_invocation"] is True
    assert row["callee_type"] == "call_expression"


def test_contract_object_is_not_address_option_setter():
    assert shape("to.call.value(x);", "Target to")["accepted"] is False


def test_wrong_span_cannot_match_nearby_statement():
    ast = SourceFacts("contract C { function f(uint x) public {x;} }")
    node = next(n for n in ast.nodes if n.type == "expression_statement")
    assert not check_shape(ast, [node.start_byte + 1, node.end_byte])["accepted"]


def test_audit_refuses_existing_output(tmp_path):
    out = tmp_path / "old"
    out.mkdir()
    with pytest.raises(FileExistsError):
        run(tmp_path / "missing_alignment.json", out)


def test_audit_checks_source_hash_before_parsing(tmp_path):
    src = tmp_path / "x.sol"
    src.write_text("contract C {}")
    alignment = tmp_path / "alignment.json"
    alignment.write_text(json.dumps({"differences": [
        {"category": "bare_expression_use", "source_path": str(src),
         "source_sha256": "wrong"}
    ]}))
    with pytest.raises(ValueError, match="source SHA mismatch"):
        run(alignment, tmp_path / "new")
