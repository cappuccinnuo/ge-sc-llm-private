"""NS-P3b2: source oracles and three-valued feature corrections (no solc claim)."""
import copy
import numpy as np
import pytest
from scripts.node_sem import static_profile as sp
from scripts.node_sem.facts_schema import new_facts
from scripts.node_sem.ctx_fields import ctx_fields, source_distance, variable_distance
from scripts.node_sem.tests.test_ctx_static import make_rows
from scripts.node_sem.tests.test_facts_integration import graph_fixture
from scripts.node_sem.p3_acceptance import verify_static
from scripts.node_sem.p3_prepare import field_stats


def rows(body):
    s,g,e=graph_fixture(body)
    return make_rows(s,g,e)


def test_checked_helper_from_unique_function_and_ambiguous_overload():
    helper="function add(uint a,uint b) internal returns(uint) { uint c = a + b; require(c >= a); return c; }"
    call="function f(uint p) public returns(uint) { return add(p,1); }"
    for extra,expected in (("",True),("function add(uint a) internal returns(uint) { return a; }",False)):
        fs,ts=rows(helper+extra+call)
        i=next(i for i,t in enumerate(ts) if t["text"]=="return add(p,1);")
        f=fs[i]["facts"]; names=sp.explain(sp.encode(f))
        assert f["checked_call"]["result_condition_check"] == expected
        assert ("arith.checked_by_helper=true" in names)==expected
        assert ("unknown.checked_call=true" in names)==(not expected)


@pytest.mark.parametrize("kind",["statement","condition","function","modifier"])
def test_checked_helper_status_and_applicability(kind):
    f=new_facts(kind)
    f["checked_call"].update(has_arithmetic=True,has_guard=True,result_condition_check=True)
    for status in ("supported","unknown","not_applicable"):
        f["checked_call"]["status"]=status
        names=sp.explain(sp.encode(f))
        assert ("arith.checked_by_helper=true" in names)==(status=="supported")
        assert ("unknown.checked_call=true" in names)==(status=="unknown")


def test_partial_state_order_guard_preserve_positive_evidence_and_unknown():
    fs,ts=rows("address owner; uint total; function f(uint p) public { require(msg.sender==owner); total=p; }")
    i=next(i for i,t in enumerate(ts) if t["text"]=="total=p;")
    f=copy.deepcopy(fs[i]["facts"])
    assert f["guards"] and f["state"]["writes"]
    f["state"]["status"]="unknown"; f["guard_status"]="unknown"
    # True event with another unresolved path must retain both known and unknown.
    f["order"].update(status="unknown",call_then_write=True)
    schema=sp.load_schema(); names=sp.explain(sp.encode(f,schema),schema)
    for name in ("state.write_scalar=true","order.call_then_write=true",
                 "guards.kinds=sender","guards.kinds=require","guards.pairs=env_state",
                 "unknown.state=true","unknown.order=true","unknown.guard=true"):
        assert name in names
    assert "guards.kinds=none" not in names
    assert not any(n.startswith(("state.write_count=","state.read_count=")) for n in names)
    verify_static([{"facts":f}],np.stack([sp.encode(f,schema)]).astype(np.float32),schema)


def test_schema_policy_drives_unknown_handling_without_field_name_dispatch():
    f=new_facts("statement")
    f["order"]["call_then_write"]=True
    schema=sp.load_schema()
    target=next(x for x in schema["fields"] if x["name"]=="order.call_then_write")
    assert target["unknown_policy"]=="keep_true"
    assert sp.encode(f,schema)[target["start"]]==1
    target["unknown_policy"]="zero"
    assert sp.encode(f,schema)[target["start"]]==0


def test_missing_guards_do_not_invent_none_and_known_absence_does():
    f=new_facts("statement");f["guard_status"]="unknown"
    names=sp.explain(sp.encode(f))
    assert "guards.kinds=none" not in names and "unknown.guard=true" in names
    f["guard_status"]="none"
    assert "guards.kinds=none" in sp.explain(sp.encode(f))


def test_parameter_entry_is_explicit_in_both_ctx_policies():
    fs,ts=rows("function f(uint p) public returns(uint) { uint x=p; return x; }")
    i=next(i for i,t in enumerate(ts) if t["text"]=="uint x=p;")
    for mode in ("original","masked"):
        fields=ctx_fields(fs[i],ts[i],mode)
        assert fields["FROM"][0].startswith("entry: function ")
        assert fields["USE"]==[("p" if mode=="original" else "PARAM1")+":param:entry"]
    j=next(i for i,t in enumerate(ts) if t["text"]=="return x;")
    fields=ctx_fields(fs[j],ts[j])
    assert fields["FROM"][0].startswith("@-1:")
    assert fields["USE"]==["x:local:@-1"]


@pytest.mark.parametrize("node_type,kind",[("function_definition","function"),("constructor_definition","function"),("modifier_definition","modifier"),("fallback_receive_definition","function")])
def test_entry_recognition_uses_identity_not_function_spelling(node_type,kind):
    item={"node":"f","offset":None}
    piece={"node_kind":kind,"node_type":node_type,"text":"not inspected",
           "identifiers":[{"name":"p","role":"PARAM"}]}
    side={"neighbors":{"f":piece}}
    assert source_distance(item,side)=="entry"
    var={"var":"p","kind":"parameter","from_offset":None}
    assert variable_distance(var,{"from":[item]},side)=="entry"
    piece["node_kind"]="statement"
    piece["text"]="function f(uint p)"
    assert source_distance(item,side)=="unknown"
    assert variable_distance(var,{"from":[item]},side)=="unknown"
    assert source_distance(item,{"neighbors":{}})=="unknown"


def test_parameter_reassignment_retains_local_distance_and_unmatched_is_unknown():
    side={"neighbors":{"f":{"node_kind":"function","identifiers":[{"name":"q","role":"PARAM"}]}}}
    dfg={"from":[{"node":"f","offset":None}]}
    var={"var":"p","kind":"parameter","from_offset":None}
    assert variable_distance(var,dfg,side)=="unknown"
    var["from_offset"]=-2
    assert variable_distance(var,dfg,side)=="@-2"


def test_entry_and_unknown_statistics_are_separate():
    stats=field_stats([{"fields":{"FROM":["entry: function f()"]}},
                      {"fields":{"FROM":["unknown"]}},{"fields":{"FROM":["@-1: x=1;"]}}])
    assert stats["FROM"]["entry"]==1 and stats["FROM"]["unknown"]==1
    assert stats["FROM"]["entry_rate"]==stats["FROM"]["unknown_rate"]==1/3

@pytest.mark.parametrize("body,supported",[
    ("constructor(uint p) public { uint x=p; }",True),
    ("modifier m(uint p) { uint x=p; _; }",False),
])
def test_constructor_modifier_real_projection_entry(body,supported):
    fs,ts=rows(body)
    i=next(i for i,t in enumerate(ts) if t["text"]=="uint x=p;")
    fields=ctx_fields(fs[i],ts[i])
    if supported:
        assert fs[i]["facts"]["dfg"]["status"]=="supported"
        assert fields["FROM"][0].startswith("entry:")
        assert "p:param:entry" in fields["USE"]
    else:
        # Existing L1 excludes this modifier: do not invent entry evidence.
        assert fs[i]["facts"]["dfg"]["status"]=="unknown"
        assert fields["FROM"]==fields["USE"]==["unknown"]

def test_comparison_rejects_other_ctx_text_edits():
    from scripts.node_sem.p3b2_acceptance import compare_fields
    row={"row_key":"s","file":"fixture.sol","fields":{"STMT":["x=1;"],"FROM":["unknown: function f(uint p)"]},"field_order":["STMT","FROM"]}
    after=copy.deepcopy(row);after["fields"]["FROM"]=["entry: function f(uint p)"]
    facts=[{"row_key":"s","facts":new_facts("statement")},{"row_key":"f","facts":new_facts("function")}]
    facts[0]["facts"]["dfg"]["from"]=[{"node":"f","offset":None}]
    assert len(compare_fields([row],[after],facts,"original"))==1
    after["fields"]["STMT"]=["x=2;"]
    with pytest.raises(ValueError,match="Unapproved CTX"):compare_fields([row],[after],facts,"original")
    after=copy.deepcopy(row);after["fields"]["FROM"]=["entry: function f(uint p)"]
    facts[1]["facts"]["node_kind"]="statement"
    with pytest.raises(ValueError,match="Unapproved CTX"):compare_fields([row],[after],facts,"original")

def test_static_delta_gate_rejects_unrelated_bit_change():
    from scripts.node_sem.p3b2_acceptance import compare_static
    schema=sp.load_schema()
    old_schema=copy.deepcopy(schema)
    old_schema["fields"]=[f for f in old_schema["fields"] if f["name"] not in ("arith.checked_by_helper","unknown.checked_call")]
    names=sp.column_names(schema);old_names=sp.column_names(old_schema)
    f=new_facts("statement");f["order"]["call_then_write"]=True
    new=np.stack([sp.encode(f,schema)])
    old=new[:,[names.index(n) for n in old_names]].copy()
    old[0,old_names.index("order.call_then_write=true")]=0
    compare_static(old,new,[{"facts":f}],old_schema,schema)
    altered=new.copy();altered[0,names.index("arith.from_param=true")]=1
    with pytest.raises(ValueError,match="Unapproved STATIC"):
        compare_static(old,altered,[{"facts":f}],old_schema,schema)
