"""Modifier source parity tests include binding, inheritance and rejected cases."""
import pytest
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.node_sem.facts_ast import AstSemantics
from scripts.node_sem.facts_guards import GuardAnalyzer
from scripts.edge_sem.guard_source import (
    modifier_guard_sources, inspect_modifier_guards, public_record)


@pytest.mark.parametrize("body,invocation,expected,unresolved", [
    ("require(x>0); _;", "gate", 1, {}),
    ("if(x>0) { _; }", "gate", 1, {}),
    ("if(x==0) return; _;", "gate", 1, {}),
    ("require(x>0); _; require(x>1);", "gate", 1, {}),
    ("_; _;", "gate", 0, {"modifier_multiple_placeholders":1}),
    ("require(x>0);", "gate", 0, {"modifier_placeholder_or_arguments_unresolved":1}),
    ("_;", "missing", 0, {"modifier_binding_unresolved":1}),
    ("_;", "gate", 0, {}),
])
def test_modifier_provenance_matches_frozen_record(body,invocation,expected,unresolved):
    src = ("pragma solidity ^0.4.24; contract C { uint x; modifier gate(){"+body+
           "} function f() public "+invocation+" {x=1;} }")
    sem = AstSemantics(ProjectionView(src,"x.sol"))
    analyzer = GuardAnalyzer(sem)
    fn = next(f for f in sem.functions if sem.text(f.child_by_field_name("name"))=="f")
    sources, problems, audit = inspect_modifier_guards(analyzer,fn)
    assert not analyzer.audit and not analyzer._modifier_cache
    frozen, failures = analyzer._modifiers(fn)
    assert [r["record"] for r in sources] == [public_record(g) for g in frozen]
    assert len(sources)==expected and dict(problems)==unresolved==dict(failures)
    assert audit==analyzer.audit
    assert modifier_guard_sources(analyzer,fn)==sources
    for row in sources:
        assert row["invocation"].type=="modifier_invocation"
        assert sem.owner(row["inner_anchor"]).type=="modifier_definition"
        assert "_anchor" not in row["record"] and "_auth_declarations" not in row["record"]


def test_inherited_parameter_binding_and_guard_sequence():
    src = """pragma solidity ^0.4.24;
      contract A { address owner; modifier gate(address p) {
        require(msg.sender==p); if(owner!=p) return; _; } }
      contract B is A { function f() public gate(owner) {} }
    """
    sem=AstSemantics(ProjectionView(src,"x.sol"))
    analyzer=GuardAnalyzer(sem)
    fn=next(f for f in sem.functions if sem.text(f.child_by_field_name("name"))=="f")
    rows,unresolved,audit=inspect_modifier_guards(analyzer,fn)
    expected,failures=analyzer._modifiers(fn)
    assert [r["record"] for r in rows]==[public_record(g)for g in expected]
    assert not unresolved and not failures and len(rows)==2
    assert audit["modifier_inherited"]==1
    assert rows[0]["inner_anchor"].start_byte > rows[1]["inner_anchor"].start_byte
    assert any(r["record"]["is_sender_guard"]for r in rows)


def test_mismatched_modifier_arguments():
    src="pragma solidity ^0.4.24; contract C { modifier m(uint p){require(p>0); _;} function f() m {} }"
    sem=AstSemantics(ProjectionView(src,"x.sol"))
    a=GuardAnalyzer(sem);fn=sem.functions[-1]
    rows,u,_=inspect_modifier_guards(a,fn)
    assert not rows and u==a._modifiers(fn)[1]


def test_builtin_constant_is_not_modifier():
    src="pragma solidity ^0.4.24; contract C { function f() public constant returns(uint) {return 1;} }"
    sem=AstSemantics(ProjectionView(src,"x.sol"));a=GuardAnalyzer(sem)
    assert inspect_modifier_guards(a,sem.functions[0]) == ([], {}, {})
