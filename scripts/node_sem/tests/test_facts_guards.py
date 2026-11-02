"""Actual frozen tree-sitter guard oracles; no Solidity compiler claim."""
import pytest

from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.frontend import walk
from scripts.node_sem.facts_ast import AstSemantics
from scripts.node_sem.facts_guards import GuardAnalyzer, key


def guard_fixture(body, prefix="", version="0.5.11"):
    source = "pragma solidity ^" + version + "; " + prefix + " contract Subject { address owner; uint value; " + body + " }"
    sem = AstSemantics(ProjectionView(source, "guard_oracle.sol"))
    return sem, GuardAnalyzer(sem)


def find(sem, source, typ="expression_statement", occurrence=0):
    values = [n for n in sem.nodes if n.type == typ and sem.text(n) == source]
    return values[occurrence]


def target(sem, analyzer, source="value = p;"):
    return analyzer.for_node(find(sem, source))


def test_prefix_require_sender_state_and_authorization():
    sem, guards = guard_fixture("function f(uint p) public { require(msg.sender == owner); value = p; }")
    out = target(sem, guards)
    assert out["guard_status"] == "present" and out["nearest"] == 0
    assert out["guards"][0]["rule"] == "1"
    assert out["guards"][0]["eq_pairs"] == ["env_state"]
    assert out["guards"][0]["is_sender_guard"]
    decl = find(sem, "address owner;", "state_variable_declaration")
    assert key(decl) in guards.auth_declarations(sem.contracts[-1])


def test_inequality_early_exit_and_self_condition_polarity():
    sem, guards = guard_fixture("function f(uint p) public { if (msg.sender != owner) revert(); value = p; }")
    out = target(sem, guards)
    assert out["guards"][0]["rule"] == "3"
    assert out["guards"][0]["polarity"] == -1
    assert out["guards"][0]["eq_pairs"] == ["env_state"]
    condition = find(sem, "if (msg.sender != owner) revert();", "if_statement")
    assert guards.for_node(condition)["self_condition"] == {
        "operand_classes": ["msg.sender", "state"], "eq_pairs": ["env_state"], "early_exit_if": True}


@pytest.mark.parametrize("condition,expected", [
    ("!(msg.sender != owner)", ["env_state"]),
    ("msg.sender == owner && p > 0", ["env_state"]),
    ("p > 0 || msg.sender == owner", []),
    ("!(msg.sender != owner && p > 0)", []),
])
def test_effective_equality_boolean_logic(condition, expected):
    sem, guards = guard_fixture("function f(uint p) public { require(" + condition + "); value = p; }")
    assert target(sem, guards)["guards"][0]["eq_pairs"] == expected


def test_if_finished_is_not_guard_and_branch_else_polarity():
    sem, guards = guard_fixture("function f(uint p) public { if (msg.sender != owner) { value = 1; } else { value = 2; } value = p; }")
    assert target(sem, guards)["guard_status"] == "none"
    yes = target(sem, guards, "value = 1;")["guards"][0]
    no = target(sem, guards, "value = 2;")["guards"][0]
    assert yes["polarity"] == 1 and yes["eq_pairs"] == []
    assert no["polarity"] == -1 and no["eq_pairs"] == ["env_state"]


def test_nearest_guard_uses_lexical_depth_and_all_guards_remain():
    sem, guards = guard_fixture("function f(uint p) public { require(p > 0); if (msg.sender == owner) { require(p == 2); value = p; } }")
    out = target(sem, guards)
    assert len(out["guards"]) == 3
    assert sem.text(out["guards"][out["nearest"]]["_anchor"]) == "require(p == 2);"


def test_loop_guard_does_not_contribute_operands_or_equalities():
    sem, guards = guard_fixture("function f(uint p) public { while (msg.sender == owner) { value = p; } }")
    out = target(sem, guards)
    assert out["guards"][0]["rule"] == "4"
    assert out["guards"][0]["operand_classes"] == []
    assert out["guards"][0]["eq_pairs"] == []


@pytest.mark.parametrize("prefix", ["", "contract Other { function require(bool x) public {} }"])
def test_file_wide_shadow_declared_after_or_in_other_contract(prefix):
    body = "function f(uint p) public { require(msg.sender == owner); value = p; }"
    if not prefix:
        body += " function require(bool x) internal {}"
    sem, guards = guard_fixture(body, prefix)
    assert target(sem, guards)["guard_status"] == "none"


def test_member_require_is_not_builtin_guard():
    sem, guards = guard_fixture("function f(uint p) public { this.require(msg.sender == owner); value = p; } function require(bool x) external {}")
    assert target(sem, guards)["guard_status"] == "none"


@pytest.mark.parametrize("modifier,rule,polarity", [
    ("modifier gate() { require(msg.sender == owner); _; }", "5", 1),
    ("modifier gate() { if (msg.sender == owner) _; }", "5p", 1),
    ("modifier gate() { if (msg.sender != owner) { revert(); } _; }", "5", -1),
    ("modifier gate() { if (msg.sender != owner) {} else { _; } }", "5p", -1),
])
def test_modifier_prefix_conditional_and_early_exit(modifier, rule, polarity):
    sem, guards = guard_fixture(modifier + " function f(uint p) public gate { value = p; }")
    out = target(sem, guards)
    assert out["guard_status"] == "present"
    guard = out["guards"][0]
    assert (guard["rule"], guard["polarity"], guard["eq_pairs"]) == (rule, polarity, ["env_state"])


@pytest.mark.parametrize("modifier", ["", "modifier gate() { require(true); }"])
def test_missing_modifier_or_placeholder_reports_unknown(modifier):
    sem, guards = guard_fixture(modifier + " function f(uint p) public gate { value = p; }")
    out = target(sem, guards)
    assert out["guard_status"] == "unknown" and out["unresolved"]


def test_modifier_parameter_substitutes_bound_argument_identity():
    sem, guards = guard_fixture("modifier gate(address expected) { require(msg.sender == expected); _; } function f(uint p) public gate(owner) { value = p; }")
    guard = target(sem, guards)["guards"][0]
    assert guard["operand_classes"] == ["msg.sender", "state"]
    assert guard["eq_pairs"] == ["env_state"]


def test_inherited_modifier_uses_closed_scope():
    source = "pragma solidity ^0.5.11; contract Base { address owner; modifier gate() { require(msg.sender == owner); _; } } contract Child is Base { uint value; function f(uint p) public gate { value = p; } }"
    sem = AstSemantics(ProjectionView(source, "inheritance.sol"))
    guards = GuardAnalyzer(sem)
    out = target(sem, guards)
    assert out["guard_status"] == "present" and out["guards"][0]["eq_pairs"] == ["env_state"]
    assert guards.audit["modifier_inherited"] == 1


def test_internal_check_parameter_binding_one_level_only():
    sem, guards = guard_fixture("function check(address expected) internal { require(msg.sender == expected); } function second() internal { check(owner); } function f(uint p) public { check(owner); value = p; } function g(uint p) public { second(); value = p; }")
    first = guards.for_node(find(sem, "value = p;", occurrence=0))
    second = guards.for_node(find(sem, "value = p;", occurrence=1))
    assert first["guards"][0]["rule"] == "6" and first["guards"][0]["eq_pairs"] == ["env_state"]
    assert second["guard_status"] == "none"


def test_internal_check_not_public_nested_branch_or_overload():
    sem, guards = guard_fixture("function check() public { require(msg.sender == owner); } function nested() internal { if (true) require(msg.sender == owner); } function overloaded() internal { require(msg.sender == owner); } function overloaded(uint p) internal {} function f(uint p) public { check(); nested(); overloaded(); value = p; }")
    assert target(sem, guards)["guard_status"] == "none"


def test_sender_state_parameter_and_hash_pairs():
    sem, guards = guard_fixture("bytes32 digest; function f(address expected, bytes32 proof, uint p) public { require(tx.origin == expected); require(keccak256(abi.encodePacked(proof)) == digest); value = p; }")
    out = target(sem, guards)
    pairs = set(pair for g in out["guards"] for pair in g["eq_pairs"])
    assert pairs == {"env_param", "hash_state_literal"}


def test_checked_arithmetic_internal_result_identity_and_kill():
    sem, guards = guard_fixture("function good(uint a,uint b) internal returns(uint) { uint c=a+b; require(c>=a); return c; } function bad(uint a,uint b) internal returns(uint) { uint c=a+b; c=1; require(c>=a); return c; } function f(uint p) public { value = good(p,1); value = bad(p,1); }")
    good = guards.checked_arithmetic(find(sem, "value = good(p,1);"))
    bad = guards.checked_arithmetic(find(sem, "value = bad(p,1);"))
    assert good == {"status": "supported", "has_arithmetic": True, "has_guard": True, "result_condition_check": True}
    assert bad == {"status": "supported", "has_arithmetic": True, "has_guard": True, "result_condition_check": False}


def test_checked_library_extension_and_explicit_call():
    library = "library Math { function plus(uint a,uint b) internal returns(uint) { uint c=a+b; require(c>=a); return c; } }"
    sem, guards = guard_fixture("using Math for uint; function f(uint p) public { value = p.plus(1); value = Math.plus(p,1); }", library)
    for statement in ("value = p.plus(1);", "value = Math.plus(p,1);"):
        checked = guards.checked_arithmetic(find(sem, statement))
        assert checked["status"] == "supported" and checked["result_condition_check"]


def test_checked_library_overload_is_unknown_and_does_not_guess():
    library = "library Math { function plus(uint a,uint b) internal returns(uint) { uint c=a+b; require(c>=a); return c; } function plus(uint a) internal returns(uint) { return a; } }"
    sem, guards = guard_fixture("using Math for uint; function f(uint p) public { value = p.plus(1); }", library)
    checked = guards.checked_arithmetic(find(sem, "value = p.plus(1);"))
    assert checked["status"] == "unknown" and not checked["result_condition_check"]


def test_overloaded_internal_and_explicit_library_summary_are_unknown():
    library = "library Math { function plus(uint a,uint b) internal returns(uint) { uint c=a+b; require(c>=a); return c; } function plus(uint a) internal returns(uint) { return a; } }"
    sem, guards = guard_fixture("function plus(uint a) internal returns(uint) { return a; } function plus(uint a,uint b) internal returns(uint) { return a+b; } function f(uint p) public { value = plus(p); value = Math.plus(p,1); }", library)
    for statement in ("value = plus(p);", "value = Math.plus(p,1);"):
        checked = guards.checked_arithmetic(find(sem, statement))
        assert checked["status"] == "unknown" and not checked["result_condition_check"]


def test_shadowed_internal_function_cannot_supply_guard():
    sem, guards = guard_fixture("function check() internal { require(msg.sender == owner); } function f(uint p, function() internal check) public { check(); value = p; }")
    assert target(sem, guards)["guard_status"] == "none"


def test_guard_unknown_for_imported_modifier_and_multiple_placeholders():
    sem, guards = guard_fixture("function f(uint p) public gate { value = p; }", 'import "external.sol";')
    assert target(sem, guards)["guard_status"] == "unknown"
    sem, guards = guard_fixture("modifier gate() { if (msg.sender == owner) _; _; } function f(uint p) public gate { value = p; }")
    out = target(sem, guards)
    assert out["guard_status"] == "unknown"
    assert out["guards"] == []
    assert out["unresolved"] == {"modifier_multiple_placeholders": 1}


def test_legacy_throw_early_exit_matches_revert_without_version_features():
    old, go = guard_fixture("function f(uint p) public { if (msg.sender != owner) throw; value = p; }", version="0.4.24")
    new, gn = guard_fixture("function f(uint p) public { if (msg.sender != owner) revert(); value = p; }")
    a, b = target(old, go), target(new, gn)
    public = lambda result: [{k: v for k, v in g.items() if not k.startswith("_")} for g in result["guards"]]
    assert public(a) == public(b)
    assert public(a)[0]["eq_pairs"] == ["env_state"]


def test_condition_summary_does_not_leak_calls_from_branch_body():
    sem, guards = guard_fixture("function plus(uint a,uint b) internal returns(uint) { uint c=a+b; require(c>=a); return c; } function f(uint p) public { if(p>0) { value = plus(p,1); } }")
    condition = find(sem, "if(p>0) { value = plus(p,1); }", "if_statement")
    assert guards.checked_arithmetic(condition)["status"] == "not_applicable"
    assert guards.checked_arithmetic(find(sem, "value = plus(p,1);"))["result_condition_check"]


def test_hash_on_right_handles_frozen_ast_postfix_grouping():
    sem, guards = guard_fixture("bytes32 digest; function f(bytes32 proof,uint p) public { require(digest == sha3(proof)); value = p; }")
    assert target(sem, guards)["guards"][0]["eq_pairs"] == ["hash_state_literal"]


def test_legacy_constant_is_mutability_not_unknown_modifier():
    sem, guards = guard_fixture("function f(uint p) public constant returns(uint) { return p; }", version="0.4.24")
    record = guards.for_node(find(sem, "return p;", "return_statement"))
    assert record["guard_status"] == "none" and record["unresolved"] == {}
