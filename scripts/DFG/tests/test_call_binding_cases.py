"""Binding/CFG regressions. UNCOMPILED fixtures, not Solidity-validity proofs.

ROBUSTNESS cases intentionally include invalid scalar callees, removed builtins,
incomplete imports or computed callees. The audit lists these separately.
"""
import copy
import pytest
import numpy as np
from scripts.DFG.call_binding import BUILTIN, NON_BUILTIN, UNKNOWN
from scripts.DFG.ddg_builder import DDGBuilder
from scripts.DFG.frontend import parse_source, solidity_version_interval
from scripts.DFG.semantic_cfg import analyze
from scripts.DFG.reaching_definitions import solve
from scripts.DFG.pipeline import augment
from scripts.DFG.graph_audit import fingerprint, assert_augmented, frozen
from scripts.DFG.configuration import prepare_graph
from scripts.DFG.models import DDGConfig
from scripts.DFG.tests.test_call_binding import POINTER_SOURCE, fact_codes
from scripts.DFG.tests.test_semantic_cfg import reach, block_for
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source


def bindings(result):
    return [d for d in result.diagnostics if "classification" in d]


def source(body, declarations="", pragma="^0.5.17", extra="", prefix=""):
    # Explicit fixture versions only; avoid 0.5-only address-payable syntax in 0.4 examples.
    old_syntax = pragma in ("^0.4.25", "^0.4.0", "0.4.10", ">=0.4.10 <0.5.0")
    address_type = "address" if old_syntax else "address payable"
    return ("pragma solidity " + pragma + "; " + prefix + "contract C {" + declarations
            + "function f(" + address_type + " a,uint p) public returns(uint){"
            + body + "}" + extra + "}")


@pytest.mark.parametrize("call,pragma", [
    ("selfdestruct(a);", "^0.5.17"),
    ("suicide(a);", "^0.4.25"),
    ("revert();", "^0.5.17"),
    ('revert(string(abi.encode(p)));', "^0.5.17"),
])
def test_builtin_binding_cuts_cfg_but_preserves_argument_reads(call, pragma):
    s = source("uint x=p;" + call + "x=2;return x;", pragma=pragma)
    v = parse_source(s, "b1.sol")
    analysis = analyze(v)
    assert len(analysis.functions) == 1, analysis.diagnostics
    ir = analysis.functions[0]
    decision = bindings(analysis)
    assert len(decision) == 1 and decision[0]["classification"] == BUILTIN
    assert decision[0]["evidence"]["pragma_interval"]
    block = block_for(v, ir, call)
    assert ir.blocks[block].successors == set()
    assert block_for(v, ir, "x=2;") not in reach(ir, ir.entry)
    rd = solve(ir)
    call_facts = [f for f in rd.facts if v.raw[f.use.anchor.start:f.use.anchor.end].decode() == call]
    if "selfdestruct" in call or "suicide" in call:
        assert {ir.symbols[f.symbol].name for f in call_facts} == {"a"}
    elif "abi.encode" in call:
        assert {ir.symbols[f.symbol].name for f in call_facts} == {"p"}
    assert not [f for f in rd.facts if f.use.kind == "return"]


@pytest.mark.parametrize("name", ["selfdestruct", "revert", "suicide"])
@pytest.mark.parametrize("decl_after", [False, True])
def test_unique_user_function_is_nonbuiltin_and_order_independent(name, decl_after):
    decl = "function " + name + "(address payable a) internal {}"
    s = source(name + "(a);uint x=p;return x;",
               declarations="" if decl_after else decl,
               extra=decl if decl_after else "")
    result = DDGBuilder().analyze_source(s, "b1.sol")
    assert not [d for d in result.diagnostics if d["kind"] == "function_fallback"]
    d = next(d for d in bindings(result) if d["call_name"] == name)
    assert d["classification"] == NON_BUILTIN
    assert d["reason"] == "unique_visible_user_function"
    assert ("uint x=p;", "return x;") in fact_codes(s, result)
    v = result.view
    analysis = analyze(v)
    fn = next(n for n in v.functions if n.child_by_field_name("name").text == b"f")
    ir = next(ir for ir in analysis.functions if ir.id == "b1.sol:" + str(fn.start_byte))
    assert block_for(v, ir, "return x;") in reach(ir, block_for(v, ir, name + "(a);"))


@pytest.mark.parametrize("decl_after", [False, True])
@pytest.mark.parametrize("name", ["selfdestruct", "revert", "suicide"])
def test_state_pointer_declaration_order_and_classification(decl_after, name):
    decl = "function(address payable) internal " + name + " = g;"
    helper = "function g(address payable a) internal {}"
    s = source(name + "(a);uint x=p;return x;",
               declarations="" if decl_after else decl,
               extra=helper + (decl if decl_after else ""))
    result = DDGBuilder().analyze_source(s, "b1.sol")
    d = bindings(result)[0]
    assert d["classification"] == NON_BUILTIN
    assert d["reason"] == "unique_state_function_pointer"
    assert not d["evidence"]["pointee_resolved"]
    assert ("uint x=p;", "return x;") in fact_codes(s, result)
    v = result.view
    a = analyze(v)
    fn = next(n for n in v.functions if n.child_by_field_name("name").text == b"f")
    ir = next(ir for ir in a.functions if ir.id == "b1.sol:" + str(fn.start_byte))
    assert block_for(v, ir, "return x;") in reach(ir, block_for(v, ir, name + "(a);"))


def test_unrelated_contract_and_function_scopes_do_not_shadow():
    s = source("selfdestruct(a);uint x=p;return x;",
               extra="function other(uint selfdestruct) public {}")
    s += "contract Other {function(address payable) internal selfdestruct;}"
    result = DDGBuilder().analyze_source(s, "b1.sol")
    assert bindings(result)[0]["classification"] == BUILTIN
    assert ("uint x=p;", "return x;") not in fact_codes(s, result)


def test_closed_inner_block_name_does_not_shadow_outer_call():
    s = source("{uint selfdestruct=1;}selfdestruct(a);uint x=p;return x;")
    result = DDGBuilder().analyze_source(s, "b1.sol")
    assert bindings(result)[0]["classification"] == BUILTIN
    assert ("uint x=p;", "return x;") not in fact_codes(s, result)


@pytest.mark.parametrize("pragma,expected", [("^0.4.25", UNKNOWN), ("^0.5.17", BUILTIN)])
def test_late_local_visibility_uses_existing_scope_policy(pragma, expected):
    # ROBUSTNESS: legacy case calls a uint and is deliberately not type-valid.
    s = source("selfdestruct(a);uint selfdestruct=1;return p;", pragma=pragma)
    result = DDGBuilder().analyze_source(s, "b1.sol")
    assert bindings(result)[0]["classification"] == expected
    if expected == UNKNOWN:
        assert not result.facts and result.stats["functions_supported"] == 0


@pytest.mark.parametrize("name", ["selfdestruct", "revert", "suicide"])
def test_member_call_does_not_use_global_builtin_semantics(name):
    s = ("pragma solidity ^0.5.17; contract Other {function " + name
         + "(uint a) public {}} contract C {Other obj;"
         + "function f(uint p) public returns(uint){obj." + name
         + "(p);uint x=p;return x;}}")
    result = DDGBuilder().analyze_source(s, "b1.sol")
    d = bindings(result)[0]
    assert d["classification"] == NON_BUILTIN and d["call_form"] == "member_call"
    assert ("uint x=p;", "return x;") in fact_codes(s, result)
    assert any(target == "obj." + name + "(p);" for _, target in fact_codes(s, result))


@pytest.mark.parametrize("pragma,name,expected", [
    ("^0.4.25", "suicide", BUILTIN),
    ("0.5.17", "suicide", UNKNOWN),     # ROBUSTNESS: removed builtin, not user-declared.
    (">=0.5.0 <0.9.0", "suicide", UNKNOWN),
    ("^0.4.0", "revert", UNKNOWN),     # Range spans revert's introduction.
    ("0.4.10", "revert", BUILTIN),
    (">=0.4.10 <0.5.0", "revert", BUILTIN),
    (">=0.5.0", "selfdestruct", UNKNOWN),  # No upper bound on known language versions.
])
def test_availability_over_entire_pragma_range(pragma, name, expected):
    call = "revert();" if name == "revert" else name + "(a);"
    result = DDGBuilder().analyze_source(source(call, pragma=pragma), "b1.sol")
    d = bindings(result)[0]
    assert d["classification"] == expected
    assert "selected_compiler_version" not in d["evidence"]
    if expected == UNKNOWN:
        assert result.stats["functions_supported"] == 0 and not result.facts


def test_missing_pragma_override_is_scope_only_not_compiler_version():
    s = "contract C {function f(address payable a) public {selfdestruct(a);}}"
    r = DDGBuilder().analyze_source(s, "b1.sol", mode="modern")
    assert bindings(r)[0]["reason"] == "pragma_missing_for_builtin_availability"
    assert not r.facts


def test_experimental_legacy_suicide_is_not_assumed_available():
    s = source("suicide(a);", pragma="^0.4.25",
               prefix='pragma experimental "v0.5.0";')
    r = DDGBuilder().analyze_source(s, "b1.sol")
    assert bindings(r)[0]["reason"] == "experimental_mode_suicide_unverified"
    assert not r.facts


@pytest.mark.parametrize("kind", ["import", "inheritance", "overload", "computed", "custom_error"])
def test_uncertain_binding_is_function_local_and_has_no_partial_facts(kind):
    declarations = ""
    bad = "selfdestruct(a);"
    prefix = ""
    if kind == "overload":
        declarations = ("function selfdestruct(address payable a) internal {}"
                        "function selfdestruct(uint x) internal {}")
    elif kind == "import":
        prefix = 'import "./not_loaded.sol";'  # ROBUSTNESS: external source unavailable.
    elif kind == "computed":
        bad = "(selfdestruct)(a);"  # ROBUSTNESS: deliberately unsupported callee form.
    elif kind == "custom_error":
        declarations = "error E(uint x);"
        bad = "revert E(p);"
    s = source("uint x=p;uint y=x;" + bad + "return y;",
               declarations=declarations, prefix=prefix,
               pragma="^0.8.19" if kind == "custom_error" else "^0.5.17",
               extra="function good(uint v) public returns(uint){uint z=v;return z;}")
    if kind == "inheritance":
        s = s.replace("contract C {", "contract C is Base {") + "contract Base {}"
    r = DDGBuilder().analyze_source(s, "b1.sol")
    fallback = next(d for d in r.diagnostics if d["kind"] == "function_fallback")
    assert fallback["classification"] == UNKNOWN
    assert all(k in fallback for k in ["function", "file", "start", "end", "line",
                                      "column", "call_name", "call_form", "reason", "evidence"])
    assert all(f.use.function != fallback["function"] for f in r.facts)
    assert ("uint z=v;", "return z;") in fact_codes(s, r)
    assert ("uint x=p;", "uint y=x;") not in fact_codes(s, r)
    assert len([d for d in r.diagnostics if d["kind"] == "function_fallback"]) == 1


def test_nested_builtin_does_not_silently_continue():
    # ROBUSTNESS: builtin has no return value, invalid as ordinary argument.
    s = source("foo(selfdestruct(a));uint x=p;return x;")
    r = DDGBuilder().analyze_source(s, "b1.sol")
    assert bindings(r)[0]["reason"] == "nested_builtin_termination_not_supported"
    assert not r.facts


@pytest.mark.parametrize("name", ["selfdestruct", "revert"])
def test_related_noncallable_declaration_does_not_restore_builtin(name):
    # ROBUSTNESS: a state scalar masks the callable name.
    s = source(name + "(a);", declarations="uint " + name + ";")
    r = DDGBuilder().analyze_source(s, "b1.sol")
    assert bindings(r)[0]["classification"] == UNKNOWN
    assert bindings(r)[0]["evidence"]["declarations"][0]["kind"] == "state_variable_declaration"


def test_fallback_pipeline_preserves_base_and_only_adds_good_function_edges():
    s = source("uint x=p;uint y=x;selfdestruct(a);return y;",
               declarations="function selfdestruct(address payable a) internal {}"
                            "function selfdestruct(uint x) internal {}",
               extra="function good(uint v) public returns(uint){uint z=v;return z;}")
    g = generate_cfg_from_source(s, "b1.sol")
    for n, data in g.nodes(data=True):
        data["token"] = np.arange(512, dtype=np.float32)
        data["node_info_vulnerabilities"] = [{"lines": [17]}] if n % 2 else None
    first, second = next(iter(g.edges()))
    g.add_edge(first, second, key="original_parallel", edge_type="next")
    before = fingerprint(g)
    out, audit = augment(g, {"b1.sol": s})
    assert fingerprint(g) == before
    assert_augmented(g, out)
    assert frozen(list(g.nodes(data=True))) == frozen(list(out.nodes(data=True)))
    records = audit["files"]["b1.sol"]["diagnostics"]
    bad = next(d["function"] for d in records if d["kind"] == "function_fallback")
    assert audit["evidence"] and all(e["function"] != bad for e in audit["evidence"])
    assert any(out.nodes[u]["code"] == "uint z=v;" and out.nodes[v]["code"] == "return z;"
               for u, v, d in out.edges(data=True) if d["edge_type"] == "DATA_DEF_USE")
    off, _ = prepare_graph(g, config=DDGConfig(use_ddg=False))
    assert fingerprint(off) == before


@pytest.mark.parametrize("variant", ["builtin", "user_function", "state_pointer"])
def test_binding_variants_project_without_changing_original_hcg(variant):
    decl = ""
    if variant == "user_function":
        decl = "function selfdestruct(address payable a) internal {}"
    elif variant == "state_pointer":
        decl = "function(address payable) internal selfdestruct = g;function g(address payable a) internal {}"
    s = source("selfdestruct(a);uint x=p;return x;", declarations=decl)
    g = generate_cfg_from_source(s, "b1.sol")
    for n, data in g.nodes(data=True):
        data["token"] = np.arange(512, dtype=np.float32) + n
        data["node_info_vulnerabilities"] = [{"lines": [2]}] if n % 2 else None
    before = fingerprint(g)
    out, audit = augment(g, {"b1.sol": s})
    assert fingerprint(g) == before
    assert_augmented(g, out)
    assert frozen(list(g.nodes(data=True))) == frozen(list(out.nodes(data=True)))
    pairs = {(out.nodes[u]["code"], out.nodes[v]["code"])
             for u, v, d in out.edges(data=True) if d["edge_type"] == "DATA_DEF_USE"}
    assert (("uint x=p;", "return x;") in pairs) == (variant != "builtin")
    d = next(d for d in audit["files"]["b1.sol"]["diagnostics"] if d["kind"] == "call_binding")
    assert d["classification"] == (BUILTIN if variant == "builtin" else NON_BUILTIN)


def test_local_function_reference_stays_outside_scalar_mvp():
    # No extension of function-typed parameters, even when their binding is explicit.
    s = ("pragma solidity ^0.5.17; contract C {"
         "function f(function(address payable) internal selfdestruct,address payable a) internal {"
         "selfdestruct(a);}}")
    result = DDGBuilder().analyze_source(s, "b1.sol")
    assert not result.facts and result.stats["functions_supported"] == 0
    assert any(d["kind"] == "function_fallback" and "non-scalar" in d["reason"]
               for d in result.diagnostics)
