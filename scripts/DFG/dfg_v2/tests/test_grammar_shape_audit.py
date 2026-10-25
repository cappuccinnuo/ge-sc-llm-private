"""Read-only grammar audit tests; parser results are not solc validation."""
import copy
import json
from pathlib import Path

import pytest

from scripts.DFG.frontend import walk
from scripts.DFG.integration.io import sha256, write_json
from scripts.DFG.dfg_v2 import grammar_shape_audit as audit
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.state_binding import StateBinder


def source(body, members="uint n; uint[] xs; uint i;"):
    return "pragma solidity ^0.5.0; contract C{" + members + "function f() public{" + body + "}}"


@pytest.mark.parametrize("body,outer,wrapper,op", [
    ("uint x=n+gasleft();", "call_expression", "binary_expression", "+"),
    ("uint x=~gasleft();", "call_expression", "unary_expression", "~"),
    ("uint x=n+address(this).balance;", "member_expression", "binary_expression", "+"),
    ("uint x=n+xs[i];", "array_access", "binary_expression", "+"),
])
def test_raw_slot_shapes_and_operators(body, outer, wrapper, op):
    data = audit.audit_source(source(body), "fixture.sol")
    rows = data["postfix_shapes"]
    assert any(r["ast_type"] == outer and r["wrapper_type"] == wrapper and r["operator"] == op for r in rows)
    row = next(r for r in rows if r["ast_type"] == outer)
    assert row["slot"] == audit.SLOTS[outer]
    assert row["line"] == 1 and row["column"] > 1
    assert data["raw_ast"] and not data["labels_used"] and not data["features_used"]
    assert data["compiler_validation"] == "not_performed"


@pytest.mark.parametrize("body", [
    "uint x=(n+gasleft)();",
    "uint x=(n+msg).sender;",
    "uint x=(n+xs)[i];",
])
def test_explicit_composite_parentheses_not_called_unparenthesized(body):
    data = audit.audit_source(source(body), "fixture.sol")
    assert data["postfix_shapes"] == []
    assert data["swallowed_push_pop"] == []


@pytest.mark.parametrize("body,method", [
    ("uint x=n+xs.push(1);", "push"),
    ("uint x=n+xs.pop();", "pop"),
    ("uint x=~xs.pop();", "pop"),
    ("uint x=n+xs[i].push(1);", "push"),
])
def test_swallowed_member_call_candidates_listed_without_fixing(body, method):
    # pop return values and nested-array shape can be parser-only negatives.
    original = source(body)
    data = audit.audit_source(original, "fixture.sol")
    assert len(data["swallowed_push_pop"]) == 1
    row = data["swallowed_push_pop"][0]
    assert row["method"] == method
    assert row["text"].endswith(")")
    assert row["requires_review"] is True
    assert row["affected_shapes"]
    assert data["summary"]["requires_user_decision"] is True
    assert original == source(body)


def test_ordinary_push_and_user_method_without_swallowed_suffix_not_candidates():
    data = audit.audit_source(source("xs.push(1); target.push(1);", "uint[] xs; Other target;"), "fixture.sol")
    assert data["swallowed_push_pop"] == []


def test_swallowed_nonarray_method_is_flagged_as_candidate_not_claimed_write():
    data = audit.audit_source(source("uint n=1; uint x=n+target.push(1);", "Other target;"), "fixture.sol")
    row = data["swallowed_push_pop"][0]
    assert row["existing_array_receiver_confirmed"] is False
    assert row["existing_array_receiver_reason"] == "receiver_not_dynamic_array"
    assert "not proof" in row["note"]


def test_declaration_type_names_are_excluded_not_reported_as_expressions():
    code = ("pragma solidity ^0.5.0; contract B {} contract C is B {"
            "using A.B for D.E; struct S{uint x;} S state; "
            "function f(S memory p) public {S memory local; D.E memory other; new D.E();}}")
    data = audit.audit_source(code, "types.sol")
    assert data["expression_user_defined_types"] == []
    assert sum(data["user_defined_type_excluded"].values()) >= 5


def test_prefix_classification_uses_same_owner_names_and_reports_shadowing():
    code = source("uint local; msg.sender memory a; state.field memory b; local.field memory c;",
                  "struct S{uint field;} S state;")
    view = ProjectionView(code, "prefix.sol")
    owner = next(n for n in walk(view.tree.root_node) if n.type == "function_definition")
    binder = StateBinder(view, owner)
    nodes = [n for n in walk(owner) if n.type == "user_defined_type"]
    flags = {audit.describe(view,n)["text"]:audit._prefix(view,n,binder) for n in nodes}
    assert flags["msg.sender"]["environment_prefix"] and flags["msg.sender"]["possible_L3"]
    assert flags["state.field"]["state_name_prefix"] and flags["state.field"]["possible_L2"]
    assert flags["local.field"]["local_name_prefix"] and flags["local.field"]["possible_L1"]
    # These are syntactic type positions and must not themselves trigger audit.
    data = audit.audit_source(code, "prefix.sol")
    assert data["summary"]["requires_user_decision"] is False


class Node:
    """Minimal parent-field fixture to test exclusion boundaries only."""
    def __init__(self, kind, parent=None, field=None):
        self.type, self.parent, self.field = kind, parent, field
        self.fields = {}
        if parent is not None and field is not None:
            parent.fields[field] = self
    def child_by_field_name(self, field):
        return self.fields.get(field)


@pytest.mark.parametrize("parent", [
    "type_name", "inheritance_specifier", "using_directive", "override_specifier",
    "modifier_invocation", "import_directive",
])
def test_type_context_filter_explicit_declaration_parents(parent):
    assert audit.type_position_reason(Node("user_defined_type", Node(parent))) is not None


@pytest.mark.parametrize("parent", [
    "member_expression", "call_argument", "return_statement",
    "binary_expression", "expression_statement", "struct_expression",
])
def test_expression_wrappers_not_excluded_merely_due_enclosing_function(parent):
    function = Node("function_definition")
    middle = Node(parent, function)
    candidate = Node("user_defined_type", middle)
    assert audit.type_position_reason(candidate) is None


def make_bundle(tmp_path, body="require(msg.sender==owner);"):
    directory = tmp_path/"l3"
    directory.mkdir()
    source_path=tmp_path/"input.sol"
    source_path.write_text(source(body,"address owner; uint n; uint[] xs;"),encoding="utf8")
    source_manifest=tmp_path/"sources.json";source_manifest.write_text("{}")
    task_manifest=tmp_path/"task.json";task_manifest.write_text("{}")
    td=directory/"demo_node";td.mkdir()
    inputs=dict(
        source_manifest=str(source_manifest),source_manifest_sha256=sha256(source_manifest),
        task_manifest=str(task_manifest),task_manifest_sha256=sha256(task_manifest),
        sources={"input.sol":dict(path=str(source_path),sha256=sha256(source_path),metadata=None)})
    write_json(td/"inputs.json",inputs)
    bundle=dict(layer="L3",files={"inputs":sha256(td/"inputs.json")})
    write_json(td/"manifest.json",bundle)
    summary=dict(all_acceptance_passed=True,profiles=["G3","G3R"],tasks=[dict(task_id="demo_node",bundle=bundle)])
    write_json(directory/"summary.json",summary)
    receipt=dict(status="accepted",training_executed=False,optimizer_steps=0,
                 summary_sha256=sha256(directory/"summary.json"),
                 task_manifests={"demo_node":sha256(td/"manifest.json")})
    write_json(directory/"receipt.json",receipt)
    return directory,source_path


def test_frozen_sources_are_bound_without_opening_any_graph(tmp_path):
    directory,path=make_bundle(tmp_path)
    tasks,binding=audit.frozen_inputs(directory)
    assert list(tasks)==["demo_node"]
    assert tasks["demo_node"]["sources"]["input.sol"]["sha256"]==sha256(path)
    assert binding["receipt_sha256"]==sha256(directory/"receipt.json")


@pytest.mark.parametrize("target", [
    "input.sol", "sources.json", "task.json",
    "l3/demo_node/inputs.json", "l3/demo_node/manifest.json", "l3/summary.json",
])
def test_source_or_binding_tamper_is_rejected(tmp_path,target):
    directory,_=make_bundle(tmp_path)
    with (tmp_path/target).open("a") as stream:stream.write(" ")
    with pytest.raises(ValueError):
        audit.frozen_inputs(directory)


def test_complete_read_only_run_and_no_overwrite(tmp_path):
    directory,source_path=make_bundle(tmp_path)
    before={str(p):sha256(p) for p in tmp_path.rglob("*") if p.is_file()}
    output=tmp_path/"output"
    summary=audit.run(output,directory)
    assert summary["task_file_instances"]==1
    assert summary["requires_user_decision"] is False
    assert summary["graph_deserialized"] is False and summary["analysis_modified"] is False
    for path,digest in before.items():assert sha256(path)==digest
    with pytest.raises(FileExistsError):audit.run(output,directory)


def test_run_with_candidates_completes_evidence_but_requests_user_decision(tmp_path):
    directory,_=make_bundle(tmp_path,"uint x=n+xs.push(1);")
    summary=audit.run(tmp_path/"output",directory)
    assert summary["requires_user_decision"] is True
    assert summary["findings"][0]["summary"]["swallowed_push_pop"]==1
    receipt=json.loads((tmp_path/"output/receipt.json").read_text())
    assert receipt["status"]=="requires_user_decision"
    assert receipt["graphs_modified"] is False


@pytest.mark.parametrize("spelling", ["msg . sender", "tx/*a*/ . origin", "block . /*a*/ timestamp"])
def test_environment_prefix_uses_ast_segments_not_raw_dot_spacing(spelling):
    code = source(spelling + " memory v;")
    view = ProjectionView(code, "spaced.sol")
    owner = next(n for n in walk(view.tree.root_node) if n.type == "function_definition")
    candidate = next(n for n in walk(owner) if n.type == "user_defined_type")
    flags = audit._prefix(view,candidate,StateBinder(view,owner))
    assert flags["environment_prefix"] is True
    assert flags["possible_L3"] is True
    # It remains excluded from real counts because this fixture is a type.
    assert audit.audit_source(code,"spaced.sol")["summary"]["expression_user_defined_types"] == 0


def add_metadata(directory,source_path):
    csv_path = source_path.parent/"versions.csv"
    csv_path.write_text("file,compiled version\ninput.sol,0.5.0\n")
    metadata = dict(csv_path=str(csv_path),csv_sha256=sha256(csv_path),
                    source_path=str(source_path),source_sha256=sha256(source_path),
                    row_file="input.sol",version="0.5.0")
    inputs = json.loads((directory/"demo_node/inputs.json").read_text())
    inputs["sources"]["input.sol"]["metadata"] = metadata
    write_json(directory/"demo_node/inputs.json",inputs)
    bundle = json.loads((directory/"demo_node/manifest.json").read_text())
    bundle["files"]["inputs"] = sha256(directory/"demo_node/inputs.json")
    write_json(directory/"demo_node/manifest.json",bundle)
    summary = json.loads((directory/"summary.json").read_text())
    summary["tasks"][0]["bundle"] = bundle
    write_json(directory/"summary.json",summary)
    receipt = json.loads((directory/"receipt.json").read_text())
    receipt["summary_sha256"] = sha256(directory/"summary.json")
    receipt["task_manifests"]["demo_node"] = sha256(directory/"demo_node/manifest.json")
    write_json(directory/"receipt.json",receipt)
    return csv_path


def test_metadata_assets_checked_and_recorded_without_binder_fallback(tmp_path):
    directory,path=make_bundle(tmp_path)
    csv_path=add_metadata(directory,path)
    tasks,_=audit.frozen_inputs(directory)
    assets=tasks["demo_node"]["sources"]["input.sol"]["metadata_assets"]
    assert assets["csv"]["sha256"] == sha256(csv_path)
    assert assets["source"]["sha256"] == sha256(path)


def test_metadata_csv_mutation_is_rejected_before_source_analysis(tmp_path):
    directory,path=make_bundle(tmp_path)
    csv_path=add_metadata(directory,path)
    with csv_path.open("a") as stream: stream.write("other.sol,0.5.0\n")
    with pytest.raises(ValueError,match="SHA256"):
        audit.frozen_inputs(directory)


def test_metadata_origin_asset_mutation_is_rejected_even_if_current_source_same(tmp_path):
    directory,path=make_bundle(tmp_path)
    add_metadata(directory,path)
    inputs_path=directory/"demo_node/inputs.json"
    inputs=json.loads(inputs_path.read_text())
    origin=tmp_path/"origin.sol";origin.write_bytes(path.read_bytes())
    inputs["sources"]["input.sol"]["metadata"]["source_path"]=str(origin)
    write_json(inputs_path,inputs)
    bundle=json.loads((directory/"demo_node/manifest.json").read_text())
    bundle["files"]["inputs"]=sha256(inputs_path)
    write_json(directory/"demo_node/manifest.json",bundle)
    summary=json.loads((directory/"summary.json").read_text())
    summary["tasks"][0]["bundle"]=bundle
    write_json(directory/"summary.json",summary)
    receipt=json.loads((directory/"receipt.json").read_text())
    receipt["summary_sha256"]=sha256(directory/"summary.json")
    receipt["task_manifests"]["demo_node"]=sha256(directory/"demo_node/manifest.json")
    write_json(directory/"receipt.json",receipt)
    origin.write_text("changed")
    with pytest.raises(ValueError,match="SHA256"):
        audit.frozen_inputs(directory)
