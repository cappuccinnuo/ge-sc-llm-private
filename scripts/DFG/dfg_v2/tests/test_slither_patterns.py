"""Parser-fixture tests; these do not claim Solidity compiler validation."""
import copy
import pytest
from scripts.DFG.dfg_v2.slither_align import SourceFacts
from scripts.DFG.dfg_v2.slither_patterns import classify_pattern, audit_binding_unresolved


CONVENTIONS = {k: {"confirmed": True, "observations": [{"fixture": "synthetic_probe_record"}]}
               for k in ("loop_header_merge_write", "aggregate_base_use", "bare_expression_use")}
CONVENTIONS["loop_header_merge_write"]["observations"] = [
    {"node_type": "IF_LOOP", "target_name": "i", "local_variables_written": ["i"], "phi_in_ssa": ["synthetic local Phi"]},
    {"node_type": "IF_LOOP", "target_name": "i", "state_variables_written": ["i"], "phi_in_ssa": ["synthetic state Phi"]},
]



def fixture(source):
    return SourceFacts(source)


def node(ast, typ, text):
    return next(n for n in ast.nodes if n.type == typ and ast.text(n) == text)


def event(ast, declaration, text, kind="USE", layer="L1", ntype="expression_statement"):
    decl = node(ast, "state_variable_declaration" if layer == "L2" else "parameter", declaration) if declaration.startswith("param:") else None
    if decl is None:
        matches = [n for n in ast.nodes if n.type in ("parameter", "variable_declaration", "state_variable_declaration")
                   and ast.text(n) == declaration]
        assert len(matches) == 1
        decl = matches[0]
    nd = node(ast, ntype, text)
    current = nd
    while current.type not in ("function_definition", "modifier_definition", "constructor_definition"):
        current = current.parent
    name = ast.text(decl.child_by_field_name("name"))
    return dict(event_id="{}:{}:{}".format(kind, nd.start_byte, name), layer=layer,
                side="slither" if kind in ("DEF", "WRITE") else "v2",
                span=ast.interval(nd), name=name, kind=kind,
                declaration=ast.interval(decl), function_start=current.start_byte,
                function_scope="supported", tags=[], evidence=[])


def call(ev, direction, ast, candidate=(), reference=(), diagnostics=(), conventions=CONVENTIONS):
    return classify_pattern(ev, direction, ast, list(candidate), list(reference),
                            list(diagnostics), conventions)


def test_modifier_exact_context_and_no_inlined_events():
    ast = fixture("contract C { modifier guard(uint x) { require(x>0); _; } function f() public {} }")
    e = event(ast, "uint x", "require(x>0);")
    assert call(e, "FN", ast)[0:3:2] == ("modifier_body_unanalyzed", "v2_scope_limit")
    inlined = dict(e, event_id="inlined", function_scope="supported")
    assert call(e, "FN", ast, [inlined]) is None


def test_modifier_name_alone_not_sufficient():
    ast = fixture("contract C { function guard(uint x) public { require(x>0); } }")
    e = event(ast, "uint x", "require(x>0);")
    e["tags"] = ["modifier_inlining"]
    assert call(e, "FN", ast) is None


@pytest.mark.parametrize("source,condition,declaration", [
    ("contract C { function f(uint n) public { uint i=0; while(i<n){i=i+1;} } }", "i<n", "uint i"),
    ("contract C { function f(uint n) public { for(uint i=0;i<n;i++){} } }", "i<n", "uint i"),
    ("contract C { uint i; function f(uint n) public { while(i<n){i=i+1;} } }", "i<n", "uint i;"),
])
def test_loop_condition_requires_actual_same_declaration_write(source, condition, declaration):
    ast = fixture(source)
    layer = "L2" if declaration.endswith(";") else "L1"
    e = event(ast, declaration, condition, "WRITE" if layer == "L2" else "DEF", layer, "binary_expression")
    result = call(e, "FN", ast)
    assert result[0] == "loop_header_merge_write"
    assert result[1]["actual_write_spans"]
    assert result[1]["reference_node_type_missing"] is True


@pytest.mark.parametrize("body", ["while(i<n){n=n+1;}", "while(i<n){{uint i=0;i=i+1;}}",
                                    "while((i=i+1)<n){}"])
def test_loop_no_write_shadow_or_condition_assignment_rejected(body):
    ast = fixture("contract C { function f(uint n) public { uint i=0; " + body + " } }")
    decl = next(n for n in ast.nodes if n.type == "variable_declaration" and ast.text(n) == "uint i")
    condition = next(n.child_by_field_name("condition") for n in ast.nodes if n.type == "while_statement")
    e = dict(event_id="test", layer="L1", span=ast.interval(condition), name="i", kind="DEF",
             declaration=ast.interval(decl), function_start=next(n.start_byte for n in ast.nodes if n.type == "function_definition"),
             evidence=[], tags=[])
    assert call(e, "FN", ast) is None


def test_loop_requires_positive_direct_probe():
    ast = fixture("contract C { function f(uint n) public { uint i=0; while(i<n){i++;} } }")
    e = event(ast, "uint i", "i<n", "DEF", "L1", "binary_expression")
    assert call(e, "FN", ast, conventions={}) is None
    assert call(e, "FN", ast, conventions={"loop_header_merge_write": {"confirmed": True}}) is None


def aggregate_fixture():
    ast = fixture("contract C { function f(uint[] memory a, uint i, uint v) public { a[i]=v; } }")
    e = event(ast, "uint[] memory a", "a[i]=v;")
    weak = dict(e, event_id="weak", kind="DEF", evidence=[{"weak_write": True}])
    ref = dict(e, event_id="ref", kind="DEF", span=[e["span"][0], e["span"][1]-1])
    return ast, e, weak, ref


def test_aggregate_precise_weak_definition_and_reference_write():
    ast, e, weak, ref = aggregate_fixture()
    assert call(e, "FP", ast, [e, weak], [ref])[0] == "aggregate_base_use"


@pytest.mark.parametrize("mutation", ["reference_read", "different_declaration", "strong_write", "missing_probe"])
def test_aggregate_rejects_nonmatching_cases(mutation):
    ast, e, weak, ref = aggregate_fixture()
    refs, conv = [ref], CONVENTIONS
    if mutation == "reference_read": refs.append(dict(ref, kind="USE", event_id="read"))
    if mutation == "different_declaration": ref["declaration"] = [1, 2]
    if mutation == "strong_write": weak["evidence"] = [{"weak_write": False}]
    if mutation == "missing_probe": conv = {}
    assert call(e, "FP", ast, [weak], refs, conventions=conv) is None


@pytest.mark.parametrize("statement,decl", [("x;", "uint x"), ("to.call.value(amount);", "uint amount")])
def test_bare_expression_exact_and_no_reference_read(statement, decl):
    ast = fixture("contract C { function f(uint x, address to, uint amount) public {" + statement + "} }")
    e = event(ast, decl, statement)
    result = call(e, "FP", ast)
    assert result[0] == "bare_expression_use"
    assert call(e, "FP", ast, reference=[dict(e, event_id="ref")]) is None


@pytest.mark.parametrize("statement", ["g(x);", "to.call.value(x)();", "x=x+1;"])
def test_real_call_and_assignment_not_bare(statement):
    ast = fixture("contract C { function f(uint x, address to) public {" + statement + "} }")
    e = event(ast, "uint x", statement)
    assert call(e, "FP", ast) is None


def alias_fixture():
    ast = fixture("contract C { uint[] values; function f(uint k) public { var a=values[k]; a.x=1; } }")
    e = event(ast, "uint[] values;", "a.x=1", "WRITE", "L2", "assignment_expression")
    alias = node(ast, "variable_declaration", "var a")
    occurrence = node(ast, "identifier", "a")  # declaration name is first
    occurrence = next(n for n in ast.nodes if n.type == "identifier" and ast.text(n) == "a"
                      and e["span"][0] <= n.start_byte < e["span"][1])
    diagnostics = [
        dict(reason="legacy_alias_version_unconfirmed", callable="x.sol:"+str(e["function_start"]),
             start=alias.start_byte, end=alias.end_byte),
        dict(reason="callable_local_shadows_state", callable="x.sol:"+str(e["function_start"]),
             start=occurrence.start_byte, end=occurrence.end_byte)]
    return ast, e, diagnostics


def test_alias_exact_initializer_and_occurrence_diagnostic():
    ast, e, diagnostics = alias_fixture()
    result = call(e, "FN", ast, diagnostics=diagnostics)
    assert result[0] == "legacy_alias_unconfirmed"
    assert result[2] == "v2_scope_limit"


@pytest.mark.parametrize("mutation", ["other_function", "other_declaration", "no_exclusion"])
def test_alias_unrelated_diagnostic_rejected(mutation):
    ast, e, diagnostics = alias_fixture()
    if mutation == "other_function": diagnostics[0]["callable"] = "x.sol:1"
    if mutation == "other_declaration": diagnostics[0]["start"] += 1
    if mutation == "no_exclusion": diagnostics = diagnostics[:1]
    assert call(e, "FN", ast, diagnostics=diagnostics) is None


def test_binding_fallback_requires_different_declaration_owner_and_inheritance():
    ast = fixture("contract B { uint x; } contract C is B { function f() public { x=1; } }")
    e = event(ast, "uint x;", "x=1", "WRITE", "L2", "assignment_expression")
    d = dict(kind="state_binding_unresolved", reason="state_name_missing", name="x",
             start=e["span"][0], end=e["span"][0]+1, callable="x.sol:"+str(e["function_start"]))
    audits = {d["callable"]: {"scope_fallback": "J: unsupported inheritance", "callable": d["callable"]}}
    result = audit_binding_unresolved(e, ast, [d], audits)
    assert result[0]["subtype"] == "closed_scope_fallback_inherited_state_missing"
    assert result[0]["verdict"] == "v2_scope_limit"
    assert audit_binding_unresolved(e, ast, [d], {})[0]["verdict"] == "unclear"


def test_binding_local_missing_not_claimed_inheritance():
    ast = fixture("contract C { uint x; function f() public { x=1; } }")
    e = event(ast, "uint x;", "x=1", "WRITE", "L2", "assignment_expression")
    d = dict(kind="state_binding_unresolved", reason="state_name_missing", name="x",
             start=e["span"][0], end=e["span"][0]+1, callable="x.sol:"+str(e["function_start"]))
    assert audit_binding_unresolved(e, ast, [d], {d["callable"]: {"scope_fallback": "J: failed"}})[0]["verdict"] == "unclear"

def test_local_loop_probe_does_not_prove_state_loop():
    ast = fixture("contract C { uint i; function f(uint n) public { while(i<n){i++;} } }")
    e = event(ast, "uint i;", "i<n", "WRITE", "L2", "binary_expression")
    only_local = copy.deepcopy(CONVENTIONS)
    only_local["loop_header_merge_write"]["observations"] = only_local["loop_header_merge_write"]["observations"][:1]
    assert call(e, "FN", ast, conventions=only_local) is None

def test_loop_body_accumulator_need_not_appear_in_condition():
    ast = fixture("contract C { function f(uint n) public { uint total=0; uint i=0; while(i<n){total+=i;i++;} } }")
    e = event(ast, "uint total", "i<n", "DEF", "L1", "binary_expression")
    assert call(e, "FN", ast)[0] == "loop_header_merge_write"

def test_binding_same_name_unrelated_owner_is_not_inheritance():
    ast = fixture("contract A { uint x; } contract B {} contract C is B { function f() public { x=1; } }")
    e = event(ast, "uint x;", "x=1", "WRITE", "L2", "assignment_expression")
    d = dict(kind="state_binding_unresolved", reason="state_name_missing", name="x",
             start=e["span"][0], end=e["span"][0]+1, callable="x.sol:"+str(e["function_start"]))
    audit = {d["callable"]: {"scope_fallback": "J: failed"}}
    assert audit_binding_unresolved(e, ast, [d], audit)[0]["verdict"] == "unclear"


def test_binding_bad_declaration_cannot_be_accepted_scope():
    ast = fixture("contract C { uint x; function f() public { x=1; } }")
    e = event(ast, "uint x;", "x=1", "WRITE", "L2", "assignment_expression")
    e["declaration"] = [1, 2]
    d = dict(kind="state_binding_unresolved", reason="state_name_ambiguous", name="x",
             start=e["span"][0], end=e["span"][0]+1, callable="x.sol:"+str(e["function_start"]))
    assert audit_binding_unresolved(e, ast, [d], {})[0]["verdict"] == "unclear"
