"""State occurrence tests use installed parser; no solc validation is claimed."""
import pytest

from scripts.DFG.frontend import text, walk
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.state_binding import StateBinder
from scripts.DFG.dfg_v2.state_access import StateAccessExtractor


def build(body, members="uint x; uint y; uint i; uint[] a;", params="", version="^0.5.0"):
    source = ("pragma solidity " + version + "; contract C { " + members +
              " function f(" + params + ") public { " + body + " } }")
    view = ProjectionView(source, "access.sol")
    function = next(n for n in walk(view.tree.root_node) if n.type == "function_definition")
    binder = StateBinder(view, function)
    extractor = StateAccessExtractor(binder)
    return view, function, binder, extractor


def region(view, spelling, kind="expression_statement"):
    matches = [n for n in walk(view.tree.root_node)
               if n.type == kind and text(view.source, n) == spelling]
    assert len(matches) == 1, [(n.type, n.start_byte) for n in matches]
    return matches[0]


def facts(extractor, node):
    return {(x.kind, x.state_name, x.via_alias) for x in extractor.extract(node)}


@pytest.mark.parametrize("statement,expected", [
    ("x=y;", {("WRITE","x",False), ("READ","y",False)}),
    ("x+=y;", {("WRITE","x",False), ("READ","x",False), ("READ","y",False)}),
    ("x-=1;", {("WRITE","x",False), ("READ","x",False)}),
    ("x++;", {("WRITE","x",False), ("READ","x",False)}),
    ("--x;", {("WRITE","x",False), ("READ","x",False)}),
    ("delete x;", {("WRITE","x",False)}),
    ("a[i]=y;", {("WRITE","a",False), ("READ","i",False), ("READ","y",False)}),
    ("a.push(y);", {("READ","a",False), ("WRITE","a",False), ("READ","y",False)}),
    ("a.pop();", {("READ","a",False), ("WRITE","a",False)}),
    ("(x,y)=(y,x);", {("READ","x",False), ("READ","y",False),
                      ("WRITE","x",False), ("WRITE","y",False)}),
])
def test_basic_reads_writes_and_tuple(statement, expected):
    view, _, _, extractor = build(statement)
    assert facts(extractor, region(view, statement)) == expected


@pytest.mark.parametrize("statement,expected", [
    ("delete balances[msg.sender];", {("WRITE","balances",False)}),
    ("++counts[k];", {("READ","counts",False), ("WRITE","counts",False), ("READ","k",False)}),
    ("delete holders[i].amount;", {("WRITE","holders",False), ("READ","i",False)}),
    ("--holders[i].amount;", {("WRITE","holders",False), ("READ","holders",False), ("READ","i",False)}),
])
def test_real_grammar_prefix_access_shapes(statement, expected):
    members = ("struct S {uint amount;} mapping(address=>uint) balances; mapping(uint=>uint) counts; "
               "S[] holders; uint i; uint k;")
    view, _, _, extractor = build(statement, members=members)
    assert facts(extractor, region(view, statement)) == expected
    events = extractor.extract(region(view, statement))
    assert all(event.occurrence_span.file == view.file for event in events)
    assert all(view.raw[event.occurrence_span.start:event.occurrence_span.end].decode("utf8")
               == text(view.source, event.occurrence) for event in events)


def test_member_property_is_not_separate_state_read_and_this_is_excluded():
    view, _, _, extractor = build("a.x=y; this.x; C.x;",
                                  members="struct S{uint x;} S a; uint x; uint y;")
    assert facts(extractor, region(view, "a.x=y;")) == {("WRITE","a",False),("READ","y",False)}
    assert facts(extractor, region(view, "this.x;")) == set()
    assert facts(extractor, region(view, "C.x;")) == set()


def test_legacy_var_alias_my_bank_and_declaration_read():
    body = "var acc=Acc[msg.sender]; if(acc.balance>=MinSum) { acc.balance-=_am; }"
    members = "struct Holder{uint balance;} mapping(address=>Holder) Acc; uint MinSum;"
    view, function, _, extractor = build(body, members, "uint _am", "^0.4.24")
    declaration = region(view, "var acc=Acc[msg.sender];", "variable_declaration_statement")
    assert facts(extractor, declaration) == {("READ","Acc",False)}
    condition = next(n for n in walk(function) if n.type == "if_statement").child_by_field_name("condition")
    assert facts(extractor, condition) == {("READ","Acc",True), ("READ","MinSum",False)}
    assert facts(extractor, region(view, "acc.balance-=_am;")) == {
        ("READ","Acc",True), ("WRITE","Acc",True)}


@pytest.mark.parametrize("location,alias", [("storage",True),("memory",False),("calldata",False)])
def test_storage_alias_but_not_memory_or_calldata(location, alias):
    view, _, _, extractor = build("S " + location + " p=st; p.a=1;", "struct S{uint a;} S st;")
    declaration = region(view, "S " + location + " p=st;", "variable_declaration_statement")
    assert facts(extractor, declaration) == {("READ","st",False)}
    assert facts(extractor, region(view, "p.a=1;")) == ({("WRITE","st",True)} if alias else set())


def test_alias_union_is_ready_before_first_region_and_bare_rebinding_does_not_write_state():
    view, _, binder, extractor = build("S storage p=st; p.a=1; p=other;",
                                      "struct S{uint a;} S st; S other;")
    assert set(binder.aliases) == {"p"}
    assert facts(extractor, region(view, "p.a=1;")) == {("WRITE","st",True),("WRITE","other",True)}
    assert facts(extractor, region(view, "p=other;")) == {("READ","other",False)}


def test_call_arguments_return_require_and_assert_are_reads_without_callee_summary():
    view, _, _, extractor = build("require(x>0); assert(y>0); foo(a,x); return y;")
    assert facts(extractor, region(view, "require(x>0);")) == {("READ","x",False)}
    assert facts(extractor, region(view, "assert(y>0);")) == {("READ","y",False)}
    assert facts(extractor, region(view, "foo(a,x);")) == {("READ","a",False),("READ","x",False)}
    assert facts(extractor, region(view, "return y;", "return_statement")) == {("READ","y",False)}


def test_type_and_declaration_names_do_not_become_reads():
    view, _, _, extractor = build("uint x=y; S memory s=st;",
                                  "struct S{uint a;} S st; uint x; uint y;")
    assert facts(extractor, region(view, "uint x=y;", "variable_declaration_statement")) == {("READ","y",False)}
    assert facts(extractor, region(view, "S memory s=st;", "variable_declaration_statement")) == {("READ","st",False)}


def test_assembly_in_function_does_not_disable_other_regions():
    view, _, _, extractor = build("assembly { let z := 1 } x=y;")
    assert facts(extractor, region(view, "x=y;")) == {("WRITE","x",False),("READ","y",False)}


def test_diagnostics_accumulate_but_extract_returns_only_current_occurrences():
    view, _, binder, extractor = build("unknown=x; y=1;")
    assert facts(extractor, region(view, "unknown=x;")) == {("READ","x",False)}
    assert any(d["reason"]=="state_name_missing" for d in binder.diagnostics)
    old_count = len(binder.diagnostics)
    assert facts(extractor, region(view, "y=1;")) == {("WRITE","y",False)}
    assert len(binder.diagnostics) >= old_count


def test_extractor_does_not_walk_function_body_or_control_substatements():
    view, function, _, extractor = build("if(x>0){y=1;}")
    assert extractor.extract(function.child_by_field_name("body")) == []
    assert extractor.diagnostics[-1]["reason"] == "non_expression_region_requires_unit_selection"


def test_nested_index_update_occurrence_set_does_not_claim_evaluation_order():
    view, _, _, extractor = build("delete a[i++];")
    assert facts(extractor, region(view, "delete a[i++];")) == {
        ("WRITE","a",False), ("READ","i",False), ("WRITE","i",False)}


def test_state_initializer_reads_other_state_but_does_not_write_itself():
    source = "contract C { uint x=1; uint y=x; }"
    view = ProjectionView(source, "init.sol")
    declaration = region(view, "uint y=x;", "state_variable_declaration")
    extractor = StateAccessExtractor(StateBinder(view, declaration))
    assert facts(extractor, declaration) == {("READ","x",False)}

def test_push_pop_on_storage_alias_write_and_read_original_state():
    view, _, _, extractor = build("uint[] storage p=a; p.push(x); p.pop();")
    assert facts(extractor, region(view, "p.push(x);")) == {
        ("READ","a",True), ("WRITE","a",True), ("READ","x",False)}
    assert facts(extractor, region(view, "p.pop();")) == {
        ("READ","a",True), ("WRITE","a",True)}


def test_modifier_parameter_scope_and_owner_read_remain_separate():
    source = ("pragma solidity ^0.4.24; contract C { address owner; uint x; "
              "modifier m(uint x) { require(msg.sender==owner); x; _; } }")
    view = ProjectionView(source, "modifier.sol")
    modifier = next(n for n in walk(view.tree.root_node) if n.type=="modifier_definition")
    extractor = StateAccessExtractor(StateBinder(view, modifier))
    assert facts(extractor, region(view, "require(msg.sender==owner);")) == {("READ","owner",False)}
    assert facts(extractor, region(view, "x;")) == set()

def test_custom_error_revert_argument_wrapper_keeps_state_reads():
    # Parse-only Solidity 0.8 custom-error sample; no solc validation.
    source = ("pragma solidity ^0.8.4; contract C { uint x; uint E; "
              "error Failure(uint value); function f() public {revert Failure(x);} }")
    view = ProjectionView(source, "revert.sol")
    function = next(n for n in walk(view.tree.root_node) if n.type=="function_definition")
    extractor = StateAccessExtractor(StateBinder(view, function))
    statement = region(view, "revert Failure(x);", "revert_statement")
    assert facts(extractor, statement) == {("READ","x",False)}
    assert not any(d.get("name")=="Failure" for d in extractor.binder.diagnostics)

@pytest.mark.parametrize("method", ["push", "pop"])
def test_non_array_state_contract_member_named_push_pop_is_read_only(method):
    # The member spelling alone does not identify a storage-array builtin.
    source = ("pragma solidity ^0.5.0; contract D {function push(uint v) public {} "
              "function pop() public {}} contract C {D target; uint value; "
              "function f() public {target." + method + ("(value);" if method=="push" else "();") + "}}")
    view = ProjectionView(source, "receiver.sol")
    function = next(n for n in walk(view.tree.root_node)
                    if n.type=="function_definition" and text(source,n.child_by_field_name("name"))=="f")
    extractor = StateAccessExtractor(StateBinder(view, function))
    statement = next(n for n in walk(function) if n.type=="expression_statement")
    expected = {("READ","target",False)}
    if method=="push":
        expected.add(("READ","value",False))
    assert facts(extractor, statement) == expected
    assert any(d["reason"].startswith("push_pop_write_skipped:")
               for d in extractor.diagnostics)

@pytest.mark.parametrize("body,members,expected,skip", [
    ("a.push(x);", "uint[] a; uint x;", {("READ","a",False),("WRITE","a",False),("READ","x",False)}, False),
    ("bytesData.pop();", "bytes bytesData;", {("READ","bytesData",False),("WRITE","bytesData",False)}, False),
    ("fixeds.pop();", "uint[3] fixeds;", {("READ","fixeds",False)}, True),
    ("bytesData.pop();", "bytes32 bytesData;", {("READ","bytesData",False)}, True),
    ("str.pop();", "string str;", {("READ","str",False)}, True),
    ("st.arr.push(x);", "struct S{uint[] arr;} S st; uint x;",
     {("READ","st",False),("WRITE","st",False),("READ","x",False)}, False),
    ("groups[i].push(x);", "mapping(uint=>uint[]) groups; uint i; uint x;",
     {("READ","groups",False),("WRITE","groups",False),("READ","i",False),("READ","x",False)}, False),
    ("holders[i].arr.pop();", "struct S{uint[] arr;} S[] holders; uint i;",
     {("READ","holders",False),("WRITE","holders",False),("READ","i",False)}, False),
    ("holders[i].pop();", "struct S{uint value;} S[] holders; uint i;",
     {("READ","holders",False),("READ","i",False)}, True),
])
def test_push_pop_proves_selected_receiver_type(body, members, expected, skip):
    # Nonarray/fixed-array cases are intentional parser-robustness negatives.
    view, _, _, extractor = build(body, members)
    assert facts(extractor, region(view, body)) == expected
    assert any(d["reason"].startswith("push_pop_write_skipped:")
               for d in extractor.diagnostics) == skip


@pytest.mark.parametrize("prefix,statement,members,expected,skip", [
    ("S storage p=holders[i];", "p.arr.pop();",
     "struct S{uint[] arr;} S[] holders; uint i;",
     {("READ","holders",True),("WRITE","holders",True)}, False),
    ("var p=holders[i];", "p.pop();",
     "struct S{uint value;} S[] holders; uint i;",
     {("READ","holders",True)}, True),
    ("uint[] storage p=groups[i];", "p.push(x);",
     "mapping(uint=>uint[]) groups; uint i; uint x;",
     {("READ","groups",True),("WRITE","groups",True),("READ","x",False)}, False),
    ("var p=groups[i];", "p.pop();",
     "mapping(uint=>uint[]) groups; uint i;",
     {("READ","groups",True),("WRITE","groups",True)}, False),
    ("bytes storage p=data;", "p.pop();",
     "bytes data;",
     {("READ","data",True),("WRITE","data",True)}, False),
])
def test_push_pop_alias_type_is_selected_pointee_not_rootstate(prefix, statement, members, expected, skip):
    view, _, _, extractor = build(prefix + statement, members, version="^0.4.24")
    assert facts(extractor, region(view, statement)) == expected
    assert any(d["reason"].startswith("push_pop_write_skipped:")
               for d in extractor.diagnostics) == skip


def test_unknown_member_receiver_and_partial_alias_union_skip_writes_but_keep_reads():
    view, _, _, extractor = build("Unknown target; target.push(x);", "uint x;")
    assert facts(extractor, region(view, "target.push(x);")) == {("READ","x",False)}
    assert any(d["reason"].startswith("push_pop_write_skipped:") for d in extractor.diagnostics)
    view, _, _, extractor = build(
        "uint[] storage p=a; p=st.missing; p.pop();",
        "struct S{uint value;} S st; uint[] a;")
    # The second target's selected type cannot be resolved: do not turn the
    # known root array into proof for all members of this coarse alias union.
    assert facts(extractor, region(view, "p.pop();")) == {("READ","a",True),("READ","st",True)}
    assert any(d["reason"]=="push_pop_write_skipped:receiver_selected_type_unresolved"
               for d in extractor.diagnostics)
