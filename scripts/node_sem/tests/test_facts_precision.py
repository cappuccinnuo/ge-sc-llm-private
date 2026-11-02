"""NS-P3a2 independent regressions: roles, local uncertainty, partial summaries."""
import copy
import json
from pathlib import Path
import pytest
from scripts.node_sem.facts import extract_source
from scripts.node_sem.facts_schema import new_facts, validate
from scripts.node_sem.tests.test_facts_integration import graph_fixture, row, FILE, run
from scripts.node_sem.tests.test_facts_oracle import FIXTURES, MANIFEST, choose, values_at, assert_subset
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint


@pytest.mark.parametrize("case",[c for c in MANIFEST["cases"] if c["id"] in ("ii","jj","kk","ll","mm","nn")],ids=lambda c:c["id"])
def test_new_oracles_on_sealed_layers(case):
    source,g,e=graph_fixture("",source_override=(FIXTURES/case["source"]).read_text())
    if case["id"]=="nn":
        omitted=[n for n,d in g.nodes(data=True) if d["node_type"]=="emit_statement"]
        assert omitted
        g.remove_nodes_from(omitted)
    before=graph_fingerprint(g)
    rows,audit=extract_source(source,FILE,graph=g,evidence=e)
    assert graph_fingerprint(g)==before
    for check in case["checks"]:
        record=choose(rows,audit["rows"],check)
        for path,expected in check.get("equals",{}).items():
            assert values_at(record,path.split("."))==expected
        for path,expected in check.get("contains",{}).items():
            assert_subset(values_at(record,path.split(".")),expected)
    if case["id"]=="mm":
        fn=next(r["fn_summary"] for r in rows.values() if r["node_kind"]=="function")
        assert fn["state_write"] and "state_write" not in fn["unknown_fields"]
        assert "auth_write" in fn["unknown_fields"]
        assert "timestamp" not in fn["unknown_fields"]
        assert not fn["timestamp"]
    if case["id"]=="ll":
        assert all(r["state"]["status"]=="supported" for r in rows.values() if r["state"])
        assert any(r["unresolved"].get("state_state_name_missing") for r in rows.values())


@pytest.mark.parametrize("condition,positive",[
    ("msg.sender == a || msg.sender == b",True),
    ("(msg.sender == a) || (tx.origin == b)",True),
    ("msg.sender == a || enabled",False),
    ("enabled || msg.sender == a",False),
    ("msg.sender != a || msg.sender == b",False),
    ("!((msg.sender != a) && (msg.sender != b))",True),
    ("(msg.sender == a || enabled) && enabled",False),
    ("enabled ? msg.sender == a : msg.sender == b",False),
    ("keccak256(abi.encode(msg.sender)) == h || enabled",False),
])
def test_disjunction_boolean_proof_not_any_sender_substring(condition,positive):
    _,g,_,rs,_=run("address a; address b; bool enabled; bytes32 h; uint x; function f() public { require("+condition+"); x=1; }")
    guard=row(g,rs,"x=1;")["guards"][0]
    assert guard["is_sender_guard"] is positive
    assert guard["disjunctive"] is positive


def test_external_value_name_is_unknown_only_in_its_statement():
    _,g,_,rs,_=run("uint known; function f() public { uint local = missing; known=1; }")
    assert row(g,rs,"uint local = missing;")["state"]["status"]=="unknown"
    assert row(g,rs,"known=1;")["state"]["status"]=="supported"
    info=next(r["fn_summary"] for r in rs.values() if r["node_kind"]=="function")
    assert "state_write" not in info["unknown_fields"]


def test_recover_missing_diagnostic_position_read_only():
    s,g,e=graph_fixture("uint known; function f() public { missing=1; known=2; }")
    expected,audit=extract_source(s,FILE,graph=g,evidence=e)
    original=copy.deepcopy(e)
    for d in e["layers"]["L2"]["files"][FILE]["diagnostics"]:
        if d.get("name")=="missing":
            for k in ("start","end","ast_type"):d.pop(k,None)
    output,other=extract_source(s,FILE,graph=g,evidence=e)
    assert output==expected
    assert other["state_precision"]["recovered_positions"]>0
    assert original["layers"]["L2"]["evidence"]==e["layers"]["L2"]["evidence"]


def test_no_projection_for_timestamp_emit_preserves_full_ast_summary():
    s,g,e=graph_fixture("event Log(uint t); function f() public { emit Log(now); }")
    omitted=next(n for n,d in g.nodes(data=True) if d["node_type"]=="emit_statement")
    g.remove_node(omitted)
    rs,a=extract_source(s,FILE,graph=g,evidence=e)
    f=next(r["fn_summary"] for r in rs.values() if r["node_kind"]=="function")
    c=next(r["contract_summary"] for r in rs.values() if r["node_kind"]=="contract")
    assert f["timestamp"] and f["status"]=="supported" and f["unknown_fields"]==[]
    assert c["status"]=="supported"


def test_unmapped_sealed_write_count_and_unaffected_fields():
    s,g,e=graph_fixture("uint known; address payable dst; function f() public { dst.transfer(1); known=2; }")
    omitted=next(n for n,d in g.nodes(data=True) if d["code"]=="known=2;")
    g.remove_node(omitted)
    rs,a=extract_source(s,FILE,graph=g,evidence=e)
    decl=row(g,rs,"uint known;")["state_decl"]
    assert decl["write_functions"]=="one" and "write_functions" in decl["unknown_fields"]
    f=next(r["fn_summary"] for r in rs.values() if r["node_kind"]=="function")
    assert f["external_call"] and f["state_write"]
    assert set(f["unknown_fields"])=={"auth_write","write_then_call","call_then_write"}
    assert row(g,rs,"dst.transfer(1);")["state"]["status"]=="supported"


def test_nonstate_callee_is_excluded_but_external_receiver_value_is_not():
    _,g,_,rs,_=run("uint x; function f() public { importedFunction(); missingReceiver.run(); x=1; }")
    assert row(g,rs,"importedFunction();")["state"]["status"]=="supported"
    assert row(g,rs,"missingReceiver.run();")["state"]["status"]=="unknown"
    assert row(g,rs,"x=1;")["state"]["status"]=="supported"


@pytest.mark.parametrize("group,kind",[("state_decl","state_decl"),("fn_summary","function"),("contract_summary","contract")])
def test_unknown_fields_rejects_unknown_keys_duplicates_and_supported_group(group,kind):
    for fields,status in [(["bogus"],"unknown"),(["status"],"unknown"),(["unknown_fields"],"unknown")]:
        f=new_facts(kind);f[group].update(unknown_fields=fields,status=status)
        with pytest.raises(ValueError):validate(f)
    field=next(k for k in new_facts(kind)[group] if k not in ("unknown_fields","status"))
    for fields,status in [([field,field],"unknown"),([field],"supported")]:
        f=new_facts(kind);f[group].update(unknown_fields=fields,status=status)
        with pytest.raises(ValueError):validate(f)


def test_summary_evidence_unprojected_identity_tamper_rejected():
    s,g,e=graph_fixture("uint x; function f() public { x=1; }")
    g.remove_node(next(n for n,d in g.nodes(data=True) if d["code"]=="x=1;"))
    e["layers"]["L2"]["evidence"][0]["statement"]["start"]+=1
    with pytest.raises(ValueError,match="identity"):
        extract_source(s,FILE,graph=g,evidence=e)

@pytest.mark.parametrize("field",["file","name","callable"])
def test_unprojected_summary_cannot_bypass_identity_checks(field):
    s,g,e=graph_fixture("uint x; function f() public { x=1; }")
    g.remove_node(next(n for n,d in g.nodes(data=True) if d["code"]=="x=1;"))
    ev=e["layers"]["L2"]["evidence"][0]
    if field=="callable":ev[field]="wrong:0"
    else:ev["state"][field]="wrong"
    with pytest.raises(ValueError,match="identity"):
        extract_source(s,FILE,graph=g,evidence=e)


def test_unlocated_file_fallback_does_not_claim_complete_function_writes():
    s,g,e=graph_fixture("uint x; function f() public { x=1; }")
    e["layers"]["L2"]["files"][FILE]["diagnostics"].append(
        dict(kind="projection_fallback",reason="unverified"))
    rs,_=extract_source(s,FILE,graph=g,evidence=e)
    fn=next(r["fn_summary"] for r in rs.values() if r["node_kind"]=="function")
    assert fn["state_write"] and "state_write" not in fn["unknown_fields"]
    assert "auth_write" in fn["unknown_fields"]
    assert row(g,rs,"x=1;")["state"]["status"]=="unknown"


def test_revision_audit_rejects_unsupported_fact_changes():
    from scripts.node_sem.facts_revision_audit import allowed
    for p in [("state","writes","0","var"),("state","reads","0","shape"),
              ("dfg","status"),("external","value_class"),("syntax",),("order","call_then_write"),
              ("guards","0","operand_classes")]:
        assert allowed(p) is None
    assert allowed(("order","status"))
    assert allowed(("state","writes","0","auth"))
