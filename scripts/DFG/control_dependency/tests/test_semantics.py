"""Semantic expectations on parser fixtures; no solc compilation claimed.

Fixtures are labelled parser/source-level cases, not compiled exploit proofs.
"""
import unittest
from scripts.DFG.control_dependency.analysis import analyze_source, postdominators, reachable
from scripts.DFG.frontend import text
from scripts.DFG.models import Unsupported


def run(body, members="", pragma="^0.4.24", params="bool ok, uint amount, address to"):
    source = "pragma solidity " + pragma + "; contract C { uint x; uint y; address owner; " + members + " function f(" + params + ") public { " + body + " } }"
    view, results = analyze_source(source, "fixture.sol")
    function = next(n for n in view.functions if n.child_by_field_name("name") is not None
                    and text(source, n.child_by_field_name("name")) == "f")
    result = next(r for r in results if r.function == "fixture.sol:" + str(function.start_byte))
    return source, view, result


def spell(source, anchor):
    return source.encode("utf8")[anchor.start:anchor.end].decode("utf8")


def edges(source, result):
    return {(spell(source, f.controller), spell(source, f.controlled), f.branch) for f in result.facts}


class ControlSemanticsTests(unittest.TestCase):
    def analyzed(self, body, **kwargs):
        source, view, result = run(body, **kwargs)
        self.assertEqual(result.status, "analyzed", result.diagnostics)
        return source, view, result

    def test_require_controls_following_but_not_prior(self):
        source, _, r = self.analyzed("x=1; require(ok); y=2;")
        es = edges(source, r)
        self.assertIn(("require(ok);", "y=2;", "pass"), es)
        self.assertFalse(any(t == "x=1;" for _, t, _ in es))
        guard = next(n for n in r.ir.nodes.values() if n.kind == "guard")
        self.assertIn(r.ir.exceptional_exit, guard.successors)
        self.assertEqual(guard.successors[r.ir.exceptional_exit], "fail")

    def test_assert_binding_and_guard(self):
        source, _, r = self.analyzed("assert(ok); x=1;")
        self.assertIn(("assert(ok);", "x=1;", "pass"), edges(source, r))

    def test_if_merges_without_overconnecting(self):
        source, _, r = self.analyzed("if(ok) {x=1;} y=2;")
        self.assertTrue(any(t == "x=1;" and branch == "true" for _, t, branch in edges(source, r)))
        self.assertFalse(any(t == "y=2;" for _, t, _ in edges(source, r)))

    def test_if_else_polarity(self):
        source, _, r = self.analyzed("if(ok) {x=1;} else {x=2;} y=3;")
        es = edges(source, r)
        self.assertTrue(any(t == "x=1;" and b == "true" for _, t, b in es))
        self.assertTrue(any(t == "x=2;" and b == "false" for _, t, b in es))
        self.assertFalse(any(t == "y=3;" for _, t, b in es))

    def test_comment_between_if_else(self):
        source, _, r = self.analyzed("if(ok) {x=1;} /* comment */ else {x=2;} y=3;")
        self.assertTrue(any(t == "x=2;" and b == "false" for _, t, b in edges(source, r)))
        self.assertFalse(any(t == "y=3;" for _, t, b in edges(source, r)))

    def test_early_return_controls_false_continuation(self):
        source, _, r = self.analyzed("if(ok) {return;} y=2;")
        self.assertTrue(any(t == "y=2;" and b == "false" for _, t, b in edges(source, r)))
        ret = next(n for n in r.ir.nodes.values() if n.kind == "return")
        self.assertEqual(ret.successors, {r.ir.normal_exit: "normal"})

    def test_revert_explicit_exception(self):
        source, _, r = self.analyzed("if(ok) {revert();} y=2;")
        self.assertTrue(any(t == "y=2;" and b == "false" for _, t, b in edges(source, r)))
        ret = next(n for n in r.ir.nodes.values() if n.kind == "revert")
        self.assertEqual(ret.successors, {r.ir.exceptional_exit: "revert"})

    def test_unreachable_statements_do_not_generate_facts(self):
        source, _, r = self.analyzed("require(ok); return; y=2;")
        self.assertFalse(any(n.anchor and spell(source, n.anchor) == "y=2;" for n in r.ir.nodes.values()))

    def test_no_transitive_closure_of_nested_guards(self):
        source, _, r = self.analyzed("require(ok); require(amount>0); x=1;")
        es = edges(source, r)
        self.assertIn(("require(ok);", "require(amount>0);", "pass"), es)
        self.assertIn(("require(amount>0);", "x=1;", "pass"), es)
        self.assertNotIn(("require(ok);", "x=1;", "pass"), es)

    def test_guard_controls_external_transfer_statement(self):
        source, _, r = self.analyzed("require(msg.sender==owner); to.transfer(amount); x=1;")
        es = edges(source, r)
        self.assertIn(("require(msg.sender==owner);", "to.transfer(amount);", "pass"), es)
        self.assertTrue(any(n.kind == "opaque_call_outcome" for n in r.ir.nodes.values()))
        self.assertFalse(any(s == "to.transfer(amount);" for s, _, _ in es))

    def test_address_low_level_call_and_write(self):
        source, _, r = self.analyzed('require(ok); bool success=msg.sender.call.value(amount)(""); x=0;')
        self.assertTrue(any('call.value' in target for _, target, _ in edges(source, r)))
        self.assertIn(("require(ok);", "x=0;", "pass"), edges(source, r))

    def test_low_level_call_in_if_is_bound(self):
        source, _, r = self.analyzed('if(!(msg.sender.send(amount))) {revert();} x=0;')
        self.assertTrue(any(target == "x=0;" and b == "false" for _, target, b in edges(source, r)))

    def test_parser_unary_receiver_ambiguity_is_explicit_fallback(self):
        # Existing grammar parses this legal-looking surface form as
        # (!msg.sender).send(amount); do not infer an address behind wrong AST.
        _, _, r = run('if(!msg.sender.send(amount)) {revert();} x=0;')
        self.assertEqual(r.status, "function_fallback")
        self.assertIn("unresolved member call", r.diagnostics[0]["reason"])
        self.assertEqual(r.facts, [])

    def test_literal_guard_false_prunes_unreachable_continuation(self):
        source, _, r = self.analyzed("require(false); x=1;")
        self.assertEqual(r.facts, [])
        self.assertFalse(any(n.anchor and spell(source, n.anchor) == "x=1;" for n in r.ir.nodes.values()))
        guard = next(n for n in r.ir.nodes.values() if n.kind == "guard")
        self.assertEqual(guard.successors, {r.ir.exceptional_exit: "fail"})

    def test_literal_guard_true_does_not_create_false_dependence(self):
        source, _, r = self.analyzed("assert((true)); x=1;")
        self.assertEqual(r.facts, [])
        self.assertTrue(any(n.anchor and spell(source, n.anchor) == "x=1;" for n in r.ir.nodes.values()))

    def test_literal_if_prunes_branch_and_has_no_conditional_fact(self):
        source, _, r = self.analyzed("if(false){x=1;} else {x=2;} y=3;")
        self.assertEqual(r.facts, [])
        self.assertFalse(any(n.anchor and spell(source, n.anchor) == "x=1;" for n in r.ir.nodes.values()))
        self.assertTrue(any(n.anchor and spell(source, n.anchor) == "x=2;" for n in r.ir.nodes.values()))

    def test_same_name_user_function_is_not_guard(self):
        source, _, r = self.analyzed("require(ok); x=1;", members="function require(bool v) internal {x=2;}")
        self.assertFalse(any(n.kind == "guard" for n in r.ir.nodes.values()))
        self.assertTrue(any(n.kind == "opaque_call_outcome" for n in r.ir.nodes.values()))
        self.assertTrue(any(d["classification"] == "non_builtin" for d in r.ir.evidence["calls"]))
        self.assertEqual(r.facts, [])

    def test_later_declaration_is_still_shadowing(self):
        source = "pragma solidity ^0.4.24; contract C { uint x; function f(bool ok) public {require(ok); x=1;} function require(bool ok) internal {} }"
        view, results = analyze_source(source)
        r = results[0]
        self.assertEqual(r.status, "analyzed", r.diagnostics)
        self.assertFalse(any(n.kind == "guard" for n in r.ir.nodes.values()))

    def test_other_contract_does_not_shadow(self):
        source = "pragma solidity ^0.4.24; contract A {function require(bool b) public {}} contract C {uint x; function f(bool b) public {require(b); x=1;}}"
        view, results = analyze_source(source)
        r = results[-1]
        self.assertEqual(r.status, "analyzed", r.diagnostics)
        self.assertTrue(any(n.kind == "guard" for n in r.ir.nodes.values()))

    def test_state_function_pointer_not_builtin(self):
        _, _, r = self.analyzed("require(ok); x=1;", members="function(bool) internal require;")
        self.assertFalse(any(n.kind == "guard" for n in r.ir.nodes.values()))
        self.assertTrue(any(d["reason"] == "unique state function pointer" for d in r.ir.evidence["calls"]))

    def test_reference_parameter_does_not_force_scalar_fallback(self):
        source, _, r = self.analyzed("require(ok); x=1;", pragma="^0.5.17", params="bool ok, bytes memory payload")
        self.assertIn(("require(ok);", "x=1;", "pass"), edges(source, r))

    def test_unknown_name_fallback_has_no_residual(self):
        source, _, r = run("require(ok); unknownCall(); x=1;")
        self.assertEqual(r.status, "function_fallback")
        self.assertIsNone(r.ir)
        self.assertEqual(r.facts, [])
        self.assertFalse(r.diagnostics[0]["partial_control_facts_published"])

    def test_member_guard_is_not_builtin(self):
        _, _, r = run("require(ok); to.require(ok); x=1;")
        self.assertEqual(r.status, "function_fallback")
        self.assertIn("unresolved member call", r.diagnostics[0]["reason"])
        self.assertEqual(r.facts, [])

    def test_unknown_inheritance_fallback(self):
        source = "pragma solidity ^0.4.24; contract C is Missing {function f(bool ok) public {require(ok);}}"
        _, results = analyze_source(source)
        self.assertEqual(results[0].status, "function_fallback")
        self.assertEqual(results[0].facts, [])

    def test_inherited_prefix_modifier_has_function_context(self):
        source = "pragma solidity ^0.4.24; contract A {address owner; modifier check(){require(msg.sender==owner); _;}} contract C is A {uint x; function f() public check {x=1;}}"
        view, results = analyze_source(source)
        r = results[-1]
        self.assertEqual(r.status, "analyzed", r.diagnostics)
        self.assertIn(("require(msg.sender==owner);", "x=1;", "pass"), edges(source, r))
        self.assertTrue(r.ir.evidence["modifier"])
        self.assertTrue(all(f.function == r.function for f in r.facts))
        fn_start = int(r.function.split(":")[-1])
        self.assertTrue(any(f.controller.start < fn_start for f in r.facts))

    def test_multiple_modifier_or_suffix_fallback(self):
        source = "pragma solidity ^0.4.24; contract C {uint x; modifier check(){_; require(x>0);} function f() public check {x=1;}}"
        _, results = analyze_source(source)
        self.assertEqual(results[-1].status, "function_fallback")
        self.assertEqual(results[-1].facts, [])

    def test_loop_fallback_retains_other_function(self):
        source = "pragma solidity ^0.4.24; contract C {uint x; function f(bool ok) public {require(ok); while(ok){x++;}} function g(bool ok) public {require(ok);x=1;}}"
        _, results = analyze_source(source)
        self.assertEqual(results[0].status, "function_fallback")
        self.assertEqual(results[0].facts, [])
        self.assertEqual(results[1].status, "analyzed")
        self.assertEqual(len(results[1].facts), 1)

    def test_user_predicate_call_and_effectful_short_circuit_fallback(self):
        for body in ("if(test()) {x=1;}", "if(ok && msg.sender.send(amount)){x=1;}"):
            _, _, r = run(body, members="function test() internal returns(bool){return true;}")
            self.assertEqual(r.status, "function_fallback", body)
            self.assertEqual(r.facts, [])

    def test_pure_short_circuit_predicate_allowed(self):
        source, _, r = self.analyzed("if(ok && amount>0) {x=1;} y=1;")
        self.assertTrue(any(t == "x=1;" for _, t, _ in edges(source, r)))
        self.assertFalse(any(t == "y=1;" for _, t, _ in edges(source, r)))

    def test_unified_exit_and_fact_cfg_witness(self):
        _, _, r = self.analyzed("require(ok); if(amount>0){return;} x=1;")
        self.assertEqual(r.ir.nodes[r.ir.normal_exit].successors, {r.ir.exit: "exit"})
        self.assertEqual(r.ir.nodes[r.ir.exceptional_exit].successors, {r.ir.exit: "exit"})
        pd, ipd = postdominators(r.ir)
        self.assertTrue(all(r.ir.exit in ps for ps in pd.values()))
        for f in r.facts:
            self.assertEqual(f.cfg_path[:2], f.cfg_edge)
            for a, b in zip(f.cfg_path, f.cfg_path[1:]):
                self.assertIn(b, r.ir.nodes[a].successors)
            self.assertEqual(f.source_sha256, r.ir.source_sha256)
            self.assertFalse(f.evidence["transitive_closure_added"])

    def test_modern_lexical_declaration_does_not_shadow_outer_call(self):
        source, _, r = self.analyzed("{uint require=1; x=require;} require(ok); y=2;", pragma="^0.5.17")
        self.assertIn(("require(ok);", "y=2;", "pass"), edges(source, r))

    def test_legacy_later_function_scoped_declaration_prevents_builtin(self):
        _, _, r = run("require(ok); uint require=1;")
        self.assertEqual(r.status, "function_fallback")
        self.assertEqual(r.facts, [])

    def test_modern_later_declaration_does_not_shadow_earlier_call(self):
        source, _, r = self.analyzed("require(ok); uint require=1; x=require;", pragma="^0.5.17")
        self.assertTrue(any(n.kind == "guard" for n in r.ir.nodes.values()))

    def test_terminator_keeps_no_normal_successor(self):
        source, _, r = self.analyzed("require(ok); selfdestruct(to); x=1;")
        self.assertIn(("require(ok);", "selfdestruct(to);", "pass"), edges(source, r))
        self.assertFalse(any(n.anchor and spell(source, n.anchor) == "x=1;" for n in r.ir.nodes.values()))

    def test_nonbuiltin_revert_nested_argument_falls_back(self):
        _, _, r = run("require(ok); revert(helper()); x=1;", members="function revert(uint n) internal {} function helper() internal returns(uint){return 1;}")
        self.assertEqual(r.status, "function_fallback")
        self.assertEqual(r.facts, [])

    def test_builtin_availability_must_hold_over_range(self):
        _, _, r = run("require(ok); x=1;", pragma="^0.4.0")
        self.assertEqual(r.status, "function_fallback")
        self.assertIn("builtin_not_guaranteed", r.diagnostics[0]["reason"])

    def test_modifier_uses_own_lexical_parameter_scope(self):
        source = "pragma solidity ^0.4.24; contract C {uint x; modifier check(){require(x>0); _;} function f(uint require) public check {x=1;}}"
        _, results = analyze_source(source)
        r = results[-1]
        self.assertEqual(r.status, "analyzed", r.diagnostics)
        self.assertIn(("require(x>0);", "x=1;", "pass"), edges(source, r))

    def test_view_source_hash_independent_of_labels(self):
        _, view, r = self.analyzed("require(ok); x=1;")
        self.assertTrue(all(f.source_sha256 == view.sha256 for f in r.facts))
        self.assertNotIn("label", str(r.ir.evidence))


if __name__ == "__main__":
    unittest.main()
