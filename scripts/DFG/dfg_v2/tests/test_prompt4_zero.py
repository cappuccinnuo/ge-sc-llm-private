"""Prompt 4.0 regressions use the installed parser, not solc compilation.

Modern implicit-local storage examples and selected grammar robustness cases
are intentionally not claims of compiler legality.
"""
import pytest

from scripts.DFG.frontend import text, walk
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.dfg_v2 import READS_STATE, WRITES_STATE
from scripts.DFG.dfg_v2.l2 import augment_l2, assert_preserved
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.units import iter_statement_regions, projected_node
from scripts.DFG.dfg_v2.tests.test_l1 import graph_for, FILE
from scripts.DFG.dfg_v2.tests.test_state_access import build, facts, region
from scripts.DFG.dfg_v2.tests.test_state_binding import make_binding
from scripts.DFG.dfg_v2.tests.test_units import exact_projector


@pytest.mark.parametrize("state_receiver", [False, True])
def test_call_option_field_names_are_not_state_reads(state_receiver):
    members = "uint value; uint gas; uint salt; uint x; uint g;"
    params = "" if state_receiver else "address a"
    if state_receiver:
        members += "address a;"
    statement = 'a.call{value:x,gas:g}("");'
    view, _, _, extractor = build(statement, members, params, "^0.6.2")
    fields = [n for n in walk(view.tree.root_node) if n.type == "struct_field_assignment"]
    assert [text(view.source, n.child_by_field_name("name")) for n in fields] == ["value", "gas"]
    assert [text(view.source, n.child_by_field_name("value")) for n in fields] == ["x", "g"]
    structured = next(n for n in walk(view.tree.root_node) if n.type == "struct_expression")
    assert text(view.source, structured.child_by_field_name("type")) == "a.call"
    expected = {("READ", "x", False), ("READ", "g", False)}
    if state_receiver:
        expected.add(("READ", "a", False))
    assert facts(extractor, region(view, statement)) == expected
    base = graph_for(view.source)
    before = fingerprint(base)
    output, audit = augment_l2(base, {FILE: view.source})
    assert fingerprint(base) == before
    assert_preserved(base, output)
    accesses = {e["state"]["name"] for e in audit["evidence"]}
    assert accesses == {item[1] for item in expected}
    assert all(e["relation"] == READS_STATE for e in audit["evidence"])


@pytest.mark.parametrize("type_name", ["bytes", "string"])
@pytest.mark.parametrize("local_type", ["typed", "var"])
def test_legacy_string_and_bytes_local_alias_selected_type(type_name, local_type):
    declaration = type_name if local_type == "typed" else "var"
    source = ("pragma solidity ^0.4.24; contract C {" + type_name +
              " data; function f() public {" + declaration + " b=data;} }")
    _, _, binder = make_binding(source)
    assert binder.mode == "legacy"
    assert len(binder.aliases.get("b", ())) == 1
    assert binder.alias_bindings[0]["state_name"] == "data"
    assert binder.alias_bindings[0]["selected_type"] == type_name


@pytest.mark.parametrize("local_type", ["bytes", "var"])
def test_legacy_bytes_alias_write_reaches_original_state(local_type):
    view, _, binder, extractor = build(
        local_type + " b=data; b[0]=1;", "bytes data;", "", "^0.4.24")
    assert binder.mode == "legacy"
    assert facts(extractor, region(view, "b[0]=1;")) == {("WRITE", "data", True)}
    base = graph_for(view.source)
    output, audit = augment_l2(base, {FILE: view.source})
    assert_preserved(base, output)
    writes = [e for e in audit["evidence"] if e["relation"] == WRITES_STATE]
    assert len(writes) == 1 and writes[0]["via_alias"] and writes[0]["status"] == "projected"
    assert writes[0]["state"]["name"] == "data"


@pytest.mark.parametrize("type_name", ["bytes", "string"])
@pytest.mark.parametrize("version", ["^0.5.0", ">=0.4.24 <0.6.0"])
def test_implicit_reference_alias_needs_legacy_version_evidence(type_name, version):
    # Missing location in 0.5+ is parser-only: do not infer illegal storage.
    source = ("pragma solidity " + version + "; contract C {" + type_name +
              " data; function f() public {" + type_name + " b=data;} }")
    _, _, binder = make_binding(source)
    assert not binder.aliases


@pytest.mark.parametrize("type_name", ["bytes1", "bytes32"])
@pytest.mark.parametrize("local_type", ["typed", "var"])
def test_fixed_bytes_are_values_not_reference_aliases(type_name, local_type):
    declaration = type_name if local_type == "typed" else "var"
    source = ("pragma solidity ^0.4.24; contract C {" + type_name +
              " data; function f() public {" + declaration + " b=data;} }")
    _, _, binder = make_binding(source)
    assert binder.mode == "legacy" and not binder.aliases


@pytest.mark.parametrize("location", ["memory", "calldata"])
def test_explicit_location_is_not_overridden_by_legacy_string_bytes_fix(location):
    source = ("pragma solidity ^0.4.24; contract C { bytes data; function f() public {"
              "bytes " + location + " b=data; b[0]=1;} }")
    _, _, binder = make_binding(source)
    assert not binder.aliases


TRY_SOURCE = ("pragma solidity ^0.6.0; contract C { uint st; function f() public { "
              "try this.other(st) returns(uint x) { st=x; } catch { st=1; } } }")


def test_try_attempt_is_owned_separately_and_missing_is_audited():
    view = ProjectionView(TRY_SOURCE, FILE)
    attempt_node = next(n for n in walk(view.tree.root_node) if n.type == "try_statement")
    attempt = attempt_node.child_by_field_name("attempt")
    assert attempt.type == "call_expression" and text(view.source, attempt) == "this.other(st)"
    function = next(n for n in walk(view.tree.root_node) if n.type == "function_definition")
    declaration = next(n for n in walk(view.tree.root_node) if n.type == "state_variable_declaration")
    projector = exact_projector(view, [function, declaration])
    # Give the state its real existing declaration role, preserving AST anchor.
    decl_id = projected_node(view, projector, declaration)
    attrs = projector.graph.nodes[decl_id]
    attrs["node_type"] = "new_variable"
    attrs["label"] = attrs["label"].replace("-state_variable_declaration-", "-new_variable-")
    candidates = list(iter_statement_regions(view, projector))
    tries = [c for c in candidates if c.ast_node == attempt_node]
    assert len(tries) == 1 and tries[0].regions == (attempt,)
    fn_candidate = next(c for c in candidates if c.ast_node == function)
    assert fn_candidate.regions == ()
    assert projected_node(view, projector, attempt_node) is None
    before = fingerprint(projector.graph)
    output, audit = augment_l2(projector.graph, {FILE: TRY_SOURCE})
    assert fingerprint(output) == before
    events = [e for e in audit["evidence"] if e["statement"]["role"] == "try_statement"]
    assert len(events) == 1
    assert events[0]["state"]["name"] == "st"
    assert events[0]["relation"] == READS_STATE and events[0]["status"] == "unmapped"
    assert events[0]["target"] is None
    assert audit["files"][FILE]["unmapped"] == 3  # attempt + two separate body writes
    assert_preserved(projector.graph, output)


def test_try_attempt_can_use_its_own_exact_node_without_entering_bodies():
    view = ProjectionView(TRY_SOURCE, FILE)
    statement = next(n for n in walk(view.tree.root_node) if n.type == "try_statement")
    projector = exact_projector(view, [statement])
    records = [c for c in iter_statement_regions(view, projector) if c.ast_node == statement]
    assert len(records) == 1
    assert records[0].regions == (statement.child_by_field_name("attempt"),)
    assert projected_node(view, projector, statement) is not None
