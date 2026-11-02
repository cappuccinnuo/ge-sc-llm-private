"""NS-P3a3 handwritten regression expectations; fixtures are parser-only."""
import copy
import pytest
import networkx as nx
from scripts.node_sem.facts import extract_source
from scripts.node_sem.facts_schema import new_facts, validate
from scripts.node_sem.tests.test_facts_integration import graph_fixture, row, FILE, run
from scripts.node_sem.tests.test_facts_oracle import FIXTURES, MANIFEST, choose, values_at, assert_subset
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint

CASES = [c for c in MANIFEST["cases"] if c["id"] in ("oo","pp","qq","rr","ss","tt","uu","vv")]

@pytest.mark.parametrize("case",CASES,ids=lambda c:c["id"])
def test_correction_oracles_sealed(case):
    s,g,e=graph_fixture("",source_override=(FIXTURES/case["source"]).read_text())
    before=graph_fingerprint(g); evidence=copy.deepcopy(e)
    rs,a=extract_source(s,FILE,graph=g,evidence=e)
    assert e==evidence and graph_fingerprint(g)==before
    for check in case["checks"]:
        f=choose(rs,a["rows"],check)
        for p,x in check.get("equals",{}).items(): assert values_at(f,p.split("."))==x
        for p,x in check.get("contains",{}).items(): assert_subset(values_at(f,p.split(".")),x)
    if case["id"]=="ss":
        assert all(r["state"]["status"]=="supported" for r in rs.values() if r["state"])
    if case["id"]=="vv":
        assert not a["state_precision"]["issues"]

@pytest.mark.parametrize("expression,pairs,sender",[
    ("(x == p) && ready",["state_param"],False),
    ("!(x != p)",["state_param"],False),
    ("(now == deadline) && ready",["time_state_param"],False),
    ("(msg.sender == owner) && (x == p)",["env_state","state_param"],True),
    ("!(msg.sender != owner || x != p)",["env_state","state_param"],True),
    ("ready || msg.sender == owner",[],False),
])
def test_preserve_non_sender_valid_equalities(expression,pairs,sender):
    _,g,_,rs,_=run("uint x;uint deadline;bool ready;address owner;function f(uint p) public { require("+expression+"); x=p; }")
    out=row(g,rs,"x=p;")["guards"][0]
    assert sorted(out["eq_pairs"])==pairs
    assert out["is_sender_guard"] is sender

def test_rootless_immediate_dominators_is_identical(monkeypatch):
    s,g,e=graph_fixture('uint x; function f(bool p) public { if(p) { msg.sender.call(""); } x=1; }')
    expected,a=extract_source(s,FILE,graph=g,evidence=e)
    old=nx.immediate_dominators
    def rootless(graph,root):
        result=old(graph,root); result.pop(root,None);return result
    monkeypatch.setattr(nx,"immediate_dominators",rootless)
    actual,b=extract_source(s,FILE,graph=g,evidence=e)
    assert actual==expected and b["cfg"]==a["cfg"]

@pytest.mark.parametrize("kind,group",[("state_decl","state_decl"),("function","fn_summary"),("contract","contract_summary")])
def test_unknown_status_iff_nonempty_fields(kind,group):
    validate(new_facts(kind))
    f=new_facts(kind);f[group].update(status="unknown",unknown_fields=[])
    with pytest.raises(ValueError): validate(f)
    f[group].update(status="supported")
    validate(f)

def test_known_true_and_saturated_counts_survive_uncertainty():
    _,g,_,rs,_=run('''uint x; address owner;
    function f() public { require(x>0); x=1; }
    function g() public { require(x>1); x=2; }
    function uncertain() public absent { assembly { sstore(0,1) let z := sload(0) } }
    function guarded() public absent { require(msg.sender==owner); owner=msg.sender; }''')
    k=row(g,rs,"uint x;")["state_decl"]
    assert k["read_functions"]==k["write_functions"]=="many"
    assert k["read_in_guard"] and k["unguarded_writer"]
    assert not k["only_constructor_writes"]
    assert not set(("read_functions","write_functions","read_in_guard","unguarded_writer","only_constructor_writes")) & set(k["unknown_fields"])
    assert "unguarded_write_functions" in k["unknown_fields"]
    f=next(r["fn_summary"] for nid,r in rs.items() if g.nodes[nid]["code"].startswith("function guarded"))
    assert f["state_write"] and f["sender_guard"] and f["auth_write"]
    assert not set(("state_write","sender_guard","auth_write")) & set(f["unknown_fields"])
    c=next(r["contract_summary"] for r in rs.values() if r["contract_summary"])
    assert c["auth_state"] and "auth_state" not in c["unknown_fields"]
    assert "auth_state_count" in c["unknown_fields"]

@pytest.mark.parametrize("op,writing",[
    ("sstore(0,1)",True),("let x := sload(0)",False),
    ("let x := delegatecall(gas(),0,0,0,0,0)",True),
    ("let x := callcode(gas(),0,0,0,0,0,0)",True),
])
def test_storage_assembly_targets_all_scoped_declarations(op,writing):
    _,g,_,rs,a=run("uint x; uint[] ys; function f() public { assembly { "+op+" } }")
    issues=[i for i in a["state_precision"]["issues"] if i["reason"]=="assembly_effect"]
    assert len(issues)==1 and issues[0]["writing"] is writing
    assert len(issues[0]["targets"])==2
    for code in ("uint x;","uint[] ys;"):
        k=row(g,rs,code)["state_decl"]
        assert ("write_functions" if writing else "read_functions") in k["unknown_fields"]

def test_ambiguous_name_targets_only_same_name_inherited_declarations():
    s,g,e=graph_fixture("",source_override="""pragma solidity ^0.5.11;
    contract A { uint x; uint other; }
    contract B { uint x; }
    contract C is A,B { function f() public { x=1; } }""")
    rs,a=extract_source(s,FILE,graph=g,evidence=e)
    issues=[i for i in a["state_precision"]["issues"] if i["targets"]]
    assert issues and all(len(i["targets"])==2 for i in issues)
    assert row(g,rs,"uint other;")["state_decl"]["unknown_fields"]==[]
    xs=[rs[n]["state_decl"] for n,d in g.nodes(data=True) if d["code"]=="uint x;"]
    assert len(xs)==2 and all("write_functions" in x["unknown_fields"] for x in xs)

def test_alias_targets_reference_types_not_value_types_or_other_contract():
    body="""struct Rec { uint n; } Rec[] recs; mapping(uint=>uint) m;
    string s; bytes b; bytes32 hash; uint a; address dest; bool ok;
    function f(uint i) public { Rec storage r = recs[i]; { Rec storage r = recs[i]; } r.n=1; }"""
    _,g,_,rs,a=run(body)
    issues=[i for i in a["state_precision"]["issues"] if i["reason"]=="unresolved_alias_use"]
    assert issues and all(len(i["targets"])==4 for i in issues)
    for code in ("uint a;","address dest;","bool ok;","bytes32 hash;"):
        assert row(g,rs,code)["state_decl"]["unknown_fields"]==[]

def test_revision3_audit_rejects_count_and_call_drift():
    from scripts.node_sem.facts_revision_audit import allowed
    for p in [("state_decl","write_functions"),("state_decl","read_functions"),("fn_summary","external_call"),
              ("contract_summary","explicit_constructor"),("state_decl","only_constructor_writes")]:
        assert allowed(p,revision="ns-p3a3") is None
    assert allowed(("state_decl","unknown_fields","0"),revision="ns-p3a3")


def test_sender_inside_index_does_not_become_sender_guard():
    _,g,_,rs,_=run("mapping(address=>address) refs; uint x; function f() public { require(refs[msg.sender] == 0 && refs[msg.sender] != msg.sender); x=1; }")
    guard=row(g,rs,"x=1;")["guards"][0]
    assert guard["eq_pairs"]==[] and not guard["is_sender_guard"]

def test_array_suffix_boolean_misparse_repaired_without_dropping_index():
    _,g,_,rs,_=run("struct Item { bool status; } mapping(address=>Item) items; address owner; uint x; function f(address p) public { require(msg.sender == owner && items[p].status == false); x=1; }")
    guard=row(g,rs,"x=1;")["guards"][0]
    assert guard["eq_pairs"]==["env_state"] and guard["is_sender_guard"]


def test_unlocated_fallback_includes_local_base_states_without_import_resolution():
    s,g,e=graph_fixture("",source_override="""pragma solidity ^0.5.11;
    contract Base { uint baseValue; }
    contract Derived is Base,Outside { function f() public {} }
    contract Other { uint own; }""")
    fn=next(n for n,d in g.nodes(data=True) if d["code"]=="function f() public {}")
    e["layers"]["L2"]["files"][FILE]["diagnostics"].append(dict(kind="projection_fallback",reason="unverified"))
    rs,a=extract_source(s,FILE,graph=g,evidence=e)
    assert "write_functions" in row(g,rs,"uint baseValue;")["state_decl"]["unknown_fields"]
    assert row(g,rs,"uint own;")["state_decl"]["unknown_fields"]==[]

@pytest.mark.parametrize("field",[
    "read_in_guard","used_as_call_value_or_target","unguarded_writer",
    "state_write","auth_write","sender_guard","write_then_call","call_then_write","auth_state",
])
def test_exists_three_value_truth_table(field):
    from scripts.node_sem.facts_summary import mark
    for value,uncertain,expected in [(True,True,[]),(False,True,[field]),
                                     (True,False,[]),(False,False,[])]:
        info={field:value}
        mark(info,{field} if uncertain else set())
        assert info["unknown_fields"]==expected
        assert (info["status"]=="unknown")==bool(expected)

def test_constructor_only_and_exact_counts_remain_unknown_when_additions_possible():
    from scripts.node_sem.facts_summary import mark
    info=dict(only_constructor_writes=True,read_functions="one",write_functions="one",
              unguarded_write_functions=2,auth_state_count=1)
    fields=set(info)
    mark(info,fields)
    assert set(info["unknown_fields"])==fields
