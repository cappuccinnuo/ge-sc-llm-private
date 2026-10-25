"""Complete IR event inventory; parser fixtures, no compiler assertions."""
from dataclasses import replace
import pytest

from scripts.DFG.dfg_v2 import l1_occurrences as lo
from scripts.DFG.dfg_v2.l1 import analyze_file


def wrap(body, parameters="", version="^0.5.0"):
    return ("pragma solidity %s;\ncontract C {\nfunction f(%s) public returns(uint) {\n%s\n}\n}"
            % (version, parameters, body))


def test_unconsumed_definition_not_limited_to_projected_du_facts():
    source = wrap("uint unused = 1;\nreturn 0;")
    old_facts, _, _ = analyze_file(source, "s.sol")
    assert not old_facts
    facts, report = lo.extract(source, "s.sol")
    assert (4, "unused", "DEF") in facts
    assert report["functions_supported"] == 1
    assert report["no_projection"]
    assert not report["token_occurrence_count"] and not report["ddg_edge_recall"]


def test_parameters_use_declaration_line_and_preserve_identity():
    source = wrap("return x;", "uint x")
    facts, report = lo.extract(source, "s.sol")
    assert (3, "x", "DEF") in facts and (4, "x", "USE") in facts
    rows = [row for row in report["occurrences"] if row["name"] == "x"]
    assert len({row["symbol"] for row in rows}) == 1
    definition = next(row for row in rows if row["kind"] == "DEF")
    assert definition["symbol_kind"] == "parameter"
    assert definition["tags"] == ["entry_initialization"]


def test_duplicate_token_reads_are_event_sets_not_occurrence_counts():
    facts, report = lo.extract(wrap("return x+x;", "uint x"), "s.sol")
    uses = [row for row in report["occurrences"] if row["kind"] == "USE"]
    assert len(uses) == 1
    assert facts[(4, "x", "USE")] == set()


def test_same_name_different_scopes_keep_declaration_identities():
    source = wrap("uint x=1; { uint x=2; x++; }\nreturn x;")
    facts, report = lo.extract(source, "s.sol")
    assert report["functions_supported"] == 1
    identities = {row["symbol"] for row in report["occurrences"] if row["name"] == "x"}
    assert len(identities) == 2
    assert any(row["fact"] == [4, "x", "DEF"] for row in report["ambiguous_triples"])


def test_weak_write_and_alias_have_explicit_evidence():
    source = """pragma solidity ^0.5.0;
contract C { uint[] a;
function f() public returns(uint) {
uint[] storage b=a;
b.push(1);
return b.length;
}
}"""
    facts, report = lo.extract(source, "s.sol")
    rows = [row for row in report["occurrences"] if row["weak_write"]]
    assert rows and all(row["kind"] == "DEF" for row in rows)
    assert rows[0]["origin"] == "v2" and "alias" in rows[0]["tags"]
    assert (5, "b", "DEF") in facts


def test_unreachable_events_retained_and_annotated():
    facts, report = lo.extract(wrap("return 0;\nuint x=1;\nreturn x;"), "s.sol")
    assert (5, "x", "DEF") in facts and (6, "x", "USE") in facts
    assert "unreachable_ir" in facts[(5, "x", "DEF")]
    assert any(not row["reachable"] for row in report["occurrences"])


def test_failed_function_publishes_no_partial_occurrences():
    source = """pragma solidity ^0.5.0; contract C {
function bad(uint x) public returns(uint) { uint y=x; assembly { let z := 1 } return y; }
function good(uint x) public returns(uint) { return x; }
}"""
    _, report = lo.extract(source, "s.sol")
    bad = next(row for row in report["functions"] if row["name"] == "bad")
    assert bad["status"] == "fallback" and bad["occurrence_count"] == 0
    assert not any(row["function"] == bad["function"] for row in report["occurrences"])
    assert report["functions_supported"] == 1 and report["functions_fallback"] == 1


def test_missing_pragma_is_not_filled_from_external_compiler():
    source = "contract C { function f(uint x) public returns(uint) { return x; } }"
    facts, report = lo.extract(source, "s.sol")
    assert not facts and report["functions_supported"] == 0
    assert report["functions_fallback"] == 1


def test_supported_route_must_use_legacy_builder(monkeypatch):
    monkeypatch.setattr(lo, "V2CFGBuilder", lambda *args: pytest.fail("legacy must stay legacy"))
    _, report = lo.extract(wrap("return x;", "uint x"), "s.sol")
    assert {row["origin"] for row in report["occurrences"]} == {"legacy"}


def test_rebuild_identity_mismatch_is_not_silently_dropped(monkeypatch):
    original = lo.CFGBuilder
    class WrongBuilder(original):
        def build(self):
            ir = super().build()
            ir.id = "wrong:function"
            return ir
    monkeypatch.setattr(lo, "CFGBuilder", WrongBuilder)
    with pytest.raises(ValueError, match="IR identity"):
        lo.extract(wrap("return x;", "uint x"), "s.sol")


def test_unknown_event_symbol_raises_integration_error(monkeypatch):
    original = lo.CFGBuilder
    class WrongBuilder(original):
        def build(self):
            ir = super().build()
            block = ir.blocks[ir.entry]
            block.events[0] = replace(block.events[0], reads=("not-declared",))
            return ir
    monkeypatch.setattr(lo, "CFGBuilder", WrongBuilder)
    with pytest.raises(ValueError, match="unknown symbol"):
        lo.extract(wrap("return x;", "uint x"), "s.sol")


def test_raw_offsets_require_valid_utf8_boundary():
    raw = "// \u4e2d\nx".encode("utf8")
    assert lo._line(raw, len(raw)-1) == 2
    with pytest.raises(UnicodeDecodeError):
        lo._line(raw, 4)
    with pytest.raises(ValueError):
        lo._line(raw, len(raw)+1)
