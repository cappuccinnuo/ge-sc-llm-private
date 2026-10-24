"""Real-parser binding tests; no Solidity compilation is performed.

Duplicate names, namespace qualification and absent/ambiguous pragmas include
parser-robustness cases, not assertions of compiler legality.
"""
import hashlib

import pytest

from scripts.DFG.frontend import text, walk
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.state_binding import StateBinder, chain_root


def make_binding(source, name="f", include_constants=False, metadata=None):
    view = ProjectionView(source, "binding.sol")
    node = next(n for n in walk(view.tree.root_node)
                if n.type in ("function_definition", "modifier_definition")
                and text(source, n.child_by_field_name("name")) == name)
    return view, node, StateBinder(view, node, metadata, include_constants)


def occurrence(view, spelling, nth=-1, kind="identifier"):
    nodes = [n for n in walk(view.tree.root_node)
             if n.type == kind and text(view.source, n) == spelling]
    return nodes[nth]


def names(view, decision):
    return [text(view.source, n.child_by_field_name("name")) for n in decision.declarations]


@pytest.mark.parametrize("declaration", ["uint x;", "uint[] x;", "mapping(uint=>uint) x;"])
def test_whole_callable_local_mask_includes_declarations_after_occurrence(declaration):
    view, function, binder = make_binding("pragma solidity ^0.4.24; contract C { uint x; "
                                  "function f() public { x=1; " + declaration + " } }")
    target = next(n for n in walk(function) if n.type == "assignment_expression").child_by_field_name("left")
    result = binder.resolve(target)
    assert result.classification == "local" and result.declarations == ()


@pytest.mark.parametrize("signature", ["uint x", "uint[] memory x", "S storage x"])
def test_parameters_shadow_state_without_symboltable_type_gate(signature):
    view, _, binder = make_binding("pragma solidity ^0.5.0; contract C { struct S { uint a; } "
                            "uint x; function f(" + signature + ") public { x; } }")
    assert not binder.resolve(occurrence(view, "x")).declarations


def test_named_return_modifier_parameters_and_legacy_tuple_mask():
    view, _, binder = make_binding("pragma solidity ^0.4.24; contract C { uint x; uint y; "
                            "function f() public returns(uint x) { var (y,z)=g(); x; y; } }")
    assert {"x", "y", "z"} <= binder.locals
    assert not binder.resolve(occurrence(view, "y")).declarations
    view, _, binder = make_binding("pragma solidity ^0.4.24; contract C { uint x; "
                            "modifier f(uint x) { require(x>0); _; } }")
    assert not binder.resolve(occurrence(view, "x")).declarations


def test_c3_unique_inherited_state_identity_and_duplicate_ambiguity():
    source = ("pragma solidity ^0.5.0; contract A { uint x; } contract B is A { "
              "function f() public { x=1; } }")
    view, _, binder = make_binding(source)
    result = binder.resolve(occurrence(view, "x"))
    assert names(view, result) == ["x"]
    assert result.declarations[0].start_byte == source.index("uint x;")
    source = source.replace("contract B is A {", "contract B is A { uint x;")
    view, _, binder = make_binding(source)
    result = binder.resolve(occurrence(view, "x"))
    assert result.classification == "unresolved" and result.reason == "state_name_ambiguous"


def test_c3_failure_falls_back_only_to_own_contract_not_unresolved_base():
    view, _, binder = make_binding("pragma solidity ^0.5.0; import 'x.sol'; contract C is A { "
                            "uint x; function f() public { x=1; y=2; } }")
    assert names(view, binder.resolve(occurrence(view, "x"))) == ["x"]
    assert not binder.resolve(occurrence(view, "y")).declarations
    assert binder.scope_fallback == "J: unresolved imports"
    assert binder.audit()["scope_fallback"]


def test_constant_excluded_by_default_but_explicit_configuration_includes():
    source = "pragma solidity ^0.5.0; contract C { uint constant K=1; function f() public { K; } }"
    view, _, binder = make_binding(source)
    assert binder.resolve(occurrence(view, "K")).classification == "constant"
    view, _, binder = make_binding(source, include_constants=True)
    assert names(view, binder.resolve(occurrence(view, "K"))) == ["K"]


def test_explicit_storage_alias_needs_no_version_and_unions_reassignments():
    view, _, binder = make_binding("contract C { struct S { uint a; } S st; S other; "
                            "function f() public { S storage p=st; p.a=1; p=other; } }")
    assert binder.mode is None
    assert {text(view.source, n.child_by_field_name("name")) for n in binder.aliases["p"]} == {"st", "other"}
    decision = binder.resolve(chain_root(occurrence(view, "p.a", kind="member_expression")), chain=True)
    assert decision.via_alias and len(decision.declarations) == 2
    assert len(binder.audit()["aliases"]) == 2


@pytest.mark.parametrize("version,expected", [("^0.4.24", True), ("^0.5.0", False),
                                             (">=0.4.24 <0.6.0", False)])
def test_legacy_implicit_alias_uses_evidence_without_guessing_mode(version, expected):
    view, _, binder = make_binding("pragma solidity " + version + "; contract C { struct S { uint a; } "
                            "mapping(uint=>S) st; function f() public { var p=st[0]; p.a=1; } }")
    assert bool(binder.aliases.get("p")) == expected
    assert view.mode is None
    if expected:
        assert binder.mode == "legacy"
        assert binder.alias_bindings[0]["kind"] == "legacy_inferred"
    elif binder.mode is None:
        assert any(d["reason"] == "legacy_alias_version_unconfirmed" for d in binder.diagnostics)


@pytest.mark.parametrize("location", ["memory", "calldata"])
def test_memory_and_calldata_cannot_alias_state(location):
    _, _, binder = make_binding("pragma solidity ^0.4.24; contract C { struct S { uint a; } S st; "
                         "function f() public { S " + location + " p=st; p.a=1; } }")
    assert "p" not in binder.aliases


def test_scalar_var_initializer_is_not_storage_alias_and_contract_type_is_not_struct():
    _, _, binder = make_binding("pragma solidity ^0.4.24; contract C { uint value; C other; "
                         "function f() public { var p=value; C q=other; } }")
    assert not binder.aliases
    assert any(d["reason"] == "legacy_var_not_proven_reference" for d in binder.diagnostics)


def test_duplicate_local_names_block_alias_union_across_scopes():
    _, _, binder = make_binding("pragma solidity ^0.4.24; contract C { struct S { uint a; } S st; S other; "
                         "function f() public { S storage p=st; { S storage p=other; p.a=1; } p.a=2; } }")
    assert "p" not in binder.aliases
    assert any(d["reason"] == "ambiguous_local_declaration" for d in binder.diagnostics)


def test_state_initializer_context_has_no_callable_locals():
    source = "contract C { uint x=1; uint y=x; function f(uint x) public {} }"
    view = ProjectionView(source, "init.sol")
    declaration = next(n for n in walk(view.tree.root_node)
                       if n.type == "state_variable_declaration" and text(source, n).startswith("uint y"))
    binder = StateBinder(view, declaration)
    assert not binder.locals
    assert names(view, binder.resolve(declaration.child_by_field_name("value"))) == ["x"]


def test_namespace_and_nonstate_exclusions_are_distinct_from_unresolved():
    view, _, binder = make_binding("contract C { uint x; function f() public { this.x; C.x; unknown; } }")
    assert binder.resolve(occurrence(view, "this")).classification == "non_state"
    assert binder.resolve(occurrence(view, "C")).classification == "non_state"
    assert binder.resolve(occurrence(view, "unknown")).classification == "unresolved"
    assert {d["kind"] for d in binder.diagnostics} >= {"state_binding_excluded", "state_binding_unresolved"}


def test_bound_recorded_version_allows_legacy_inference_without_pragma(tmp_path):
    source = "contract C { struct S {uint a;} S st; function f() public { var p=st; p.a=1; } }"
    origin = tmp_path / "binding.sol"
    origin.write_text(source)
    csv = tmp_path / "versions.csv"
    csv.write_text("file,compiled version\nbinding.sol,0.4.25\n")
    metadata = {"source_path": str(origin), "source_sha256": hashlib.sha256(origin.read_bytes()).hexdigest(),
                "csv_path": str(csv), "csv_sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
                "row_file": "binding.sol", "version": "0.4.25"}
    _, _, binder = make_binding(source, metadata=metadata)
    assert binder.mode == "legacy" and "p" in binder.aliases
    metadata["source_sha256"] = "wrong"
    _, _, binder = make_binding(source, metadata=metadata)
    assert binder.mode is None and not binder.aliases
    assert "hash mismatch" in binder.version_evidence["reason"]

def test_legacy_reference_parameter_and_named_return_do_not_default_to_storage():
    _, _, binder = make_binding(
        "pragma solidity ^0.4.24; contract C { struct S {uint a;} S st; "
        "function f(S p) public returns(S q) { p=st; q=st; p.a=1; q.a=2; } }")
    assert not binder.aliases


def test_same_state_name_in_unrelated_contracts_keeps_declaration_identity():
    source = ("contract A {uint x;} contract C {uint x; "
              "function f() public {x=1;} }")
    view, _, binder = make_binding(source)
    decision = binder.resolve(occurrence(view, "x"))
    assert len(decision.declarations) == 1
    assert decision.declarations[0].start_byte == source.rindex("uint x;")

def test_malformed_metadata_shape_is_not_swallowed_as_unknown_version():
    source = "contract C { uint x; function f() public {x=1;} }"
    with pytest.raises(KeyError):
        make_binding(source, metadata={"version": "0.4.25"})

def test_alias_audit_retains_selected_pointee_type_for_receiver_proof():
    source = ("pragma solidity ^0.4.24; contract C { struct S{uint[] arr;} S[] holders; "
              "function f(uint i) public {var p=holders[i]; p.arr.pop();} }")
    view, _, binder = make_binding(source)
    assert binder.alias_bindings[0]["selected_type"] == "S"
    expr = occurrence(view, "p.arr", kind="member_expression")
    assert binder.array_receiver(expr) == (True, "confirmed_dynamic_storage_array")
    assert binder.array_receiver(occurrence(view, "p", nth=-1))[0] is False
