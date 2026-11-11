"""EP3 guard topology and evidence tests against explicit source expectations."""
import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts.edge_sem.tests.test_build_f4_calls import synthetic,code
from scripts.edge_sem.build_f4 import inspect_file,add_edges,load_edges
from scripts.edge_sem.guard_edges import collect_guards,task_guard_audit
from scripts.edge_sem.recon.ep3_archive import load_ep2_edges,_check_source,EP2
from scripts.edge_sem.recon.common import ref
from scripts.node_sem.facts import STATEMENTS,_raw_projection
from scripts.node_sem.facts_ast import AstSemantics,key
from scripts.node_sem.facts_guards import GuardAnalyzer
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint

FIXTURE=Path(__file__).parent/"fixtures"/"ep3_guards.sol"


@pytest.fixture(scope="module")
def bundle():
    source,graph=synthetic(FIXTURE.read_text())
    rows,audit=inspect_file("ep2.sol",source,graph)
    return source,graph,rows,audit


def owner(source,row):
    sem=AstSemantics(ProjectionView(source,"ep2.sol"))
    node=next(n for n in sem.nodes if list(key(n))==row["dst_anchor"])
    fn=sem.owner(node)
    name=fn.child_by_field_name("name")
    return sem.text(name) if name is not None else fn.type


def guards(bundle,function=None,destination=None):
    source,_,rows,_=bundle
    return [r for r in rows if r["relation"]=="GUARDS"
            and (function is None or owner(source,r)==function)
            and (destination is None or code(source,r["dst_anchor"])==destination)]


def test_require_sender_and_raw_operands(bundle):
    source,_,_,_=bundle
    rows=guards(bundle,"direct","owner = n;")
    assert len(rows)==1 and code(source,rows[0]["src_anchor"])=="require(msg.sender == owner);"
    e=rows[0]["evidence"][0]
    assert e["kind"]=="require" and e["is_sender_guard"] and e["polarity"]==1
    assert "msg.sender" in e["operand_classes"] and "caller_identity" not in e["operand_classes"]
    assert e["source"]=="lexical" and e["offset"]==0
    assert rows[0]["kind"]==["require"]


def test_timestamp_true_branch(bundle):
    rows=guards(bundle,"timed","x = 1;")
    assert len(rows)==1
    e=rows[0]["evidence"][0]
    # Frozen operand_classes maps the unshadowed 'now' builtin to timestamp.
    assert e["kind"]=="if_branch" and e["polarity"]==1 and "timestamp" in e["operand_classes"]


def test_false_branch_polarity(bundle):
    rows=guards(bundle,"branch","y = 2;")
    assert len(rows)==1 and rows[0]["evidence"][0]["polarity"]==-1


def test_internal_check_preserves_two_records_on_one_edge(bundle):
    source,_,_,audit=bundle
    rows=guards(bundle,"internalGuard","z = 1;")
    assert len(rows)==1 and code(source,rows[0]["src_anchor"])=="_check();"
    assert rows[0]["kind"]==["internal_check"] and len(rows[0]["evidence"])==2
    assert all(e["kind"]=="internal_check" and e["source"]=="lexical" for e in rows[0]["evidence"])
    assert audit["guards"]["counts"]["multi_evidence_edges"]>=1


def test_two_modifier_sources_for_each_statement(bundle):
    source,_,_,_=bundle
    for statement in ("owner = n;","x = 1;"):
        rows=guards(bundle,"two",statement)
        assert len(rows)==2
        assert {code(source,r["src_anchor"]) for r in rows}=={"require(msg.sender == owner);","require(x > 0);"}
        assert all(r["kind"]==["modifier"] for r in rows)
        assert all(e["source"]=="modifier" and e["invocation_anchor"][2]=="modifier_invocation"
                   for r in rows for e in r["evidence"])


def test_single_modifier_origin_is_body_not_invocation(bundle):
    source,_,_,_=bundle
    rows=guards(bundle,"single")
    assert len(rows)==2
    assert all(r["src_anchor"][2]=="expression_statement" for r in rows)
    assert all(code(source,r["src_anchor"])=="require(msg.sender == owner);" for r in rows)


def test_inherited_guard_and_conditional_target(bundle):
    rows=guards(bundle,"inherited")
    assert len(rows)==3
    modifiers=[r for r in rows if r["kind"]==["modifier"]]
    assert len(modifiers)==2
    assert any(r["dst_anchor"][2]=="if_statement" for r in modifiers)


def test_base_constructor_invocation_stays_unknown(bundle):
    _,_,rows,audit=bundle
    records=audit["unresolved_modifier_declarations"]
    base=[r for r in records if r["function_anchor"][2]=="constructor_definition"]
    assert len(base)==1 and base[0]["declaration_types"]==["contract_declaration"]
    anchor=base[0]["function_anchor"]
    targets=[r for r in audit["guards"]["targets"] if r["function_anchor"]==anchor]
    assert len(targets)==1 and targets[0]["guard_status"]=="unknown"
    assert not [r for r in rows if r["relation"]=="MOD_APPLY" and r["src_anchor"]==anchor]
    assert not guards(bundle,"constructor_definition")


def test_known_guards_survive_unknown_modifier(bundle):
    _,_,_,audit=bundle
    rows=guards(bundle,"uncertain","owner = n;")
    assert len(rows)==1 and rows[0]["kind"]==["modifier"]
    target=next(t for t in audit["guards"]["targets"] if t["node"]==rows[0]["dst"])
    assert target["guard_status"]=="unknown"


def test_early_exit_guard(bundle):
    source,_,_,_=bundle
    row=guards(bundle,"early","y = 2;")[0]
    assert code(source,row["src_anchor"])=="if (!ok) revert();"
    assert row["kind"]==["early_exit"] and row["evidence"][0]["polarity"]==-1


def test_arithmetic_guard_has_no_sender_class(bundle):
    row=guards(bundle,"arithmetic","z = a + b;")[0]
    e=row["evidence"][0]
    assert "caller_identity" not in e["operand_classes"] and "msg.sender" not in e["operand_classes"]
    assert not e["is_sender_guard"]


def test_loop_and_nested_condition_targets(bundle):
    row=guards(bundle,"loop","arr[i].transfer(1);")[0]
    assert row["kind"]==["loop_cond"] and row["src_anchor"][2]=="for_statement"
    # Frozen rule 4 intentionally clears the classes even for arr.length.
    assert row["evidence"][0]["operand_classes"]==[]
    rows=guards(bundle,"nested")
    assert any(r["dst_anchor"][2]=="if_statement" and r["kind"]==["require"] for r in rows)
    assert any(r["dst_anchor"][2]=="while_statement" and r["kind"]==["if_branch"] for r in rows)


@pytest.mark.parametrize("endpoint",["src_anchor","dst_anchor"])
def test_reject_nonstatement_guard_roles_without_mutation(bundle,endpoint):
    _,graph,_,_=bundle
    row=copy.deepcopy(guards(bundle,"direct")[0]);row[endpoint][2]="function_definition"
    fp=graph_fingerprint(graph)
    with pytest.raises(ValueError,match="GUARDS roles"):add_edges(graph,[row])
    assert graph_fingerprint(graph)==fp


def test_guard_missing_exact_source_is_counted(bundle):
    source,graph,_,_=bundle
    view=ProjectionView(source,"ep2.sol");sem=AstSemantics(view)
    raw=_raw_projection(view,Projector(graph,view))
    source_id=guards(bundle,"internalGuard")[0]["src"]
    raw.pop(source_id)
    rows,audit=collect_guards("ep2.sol",source,sem,raw,GuardAnalyzer(sem))
    missing=[r for r in audit["missing"] if r["evidence"]["kind"]=="internal_check"]
    assert len(missing)==2 and all(r["source_anchor"][2]=="expression_statement" for r in missing)
    assert audit["counts"]["nonmodifier_unmapped"]==2
    assert not any(r["src"]==source_id for r in rows)


def test_all_guard_evidence_matches_frozen_sequence_and_graph_unchanged(bundle):
    source,graph,rows,audit=bundle
    fp=graph_fingerprint(graph)
    enriched=add_edges(graph,rows)
    assert graph_fingerprint(graph)==fp and list(enriched)==list(graph)
    assert not audit["guards"]["missing"] and audit["guards"]["correspondence_pass"]
    for r in guards(bundle):
        assert r["src"]!=r["dst"] and r["src_anchor"][2] in STATEMENTS and r["dst_anchor"][2] in STATEMENTS
        assert r["kind"]==sorted(set(e["kind"] for e in r["evidence"]))
        assert r["rule"]=="E1-GUARD-1"
    assert len({(r["relation"],r["src"],r["dst"]) for r in rows})==len(rows)


@pytest.mark.parametrize("task",["reentrancy_node","access_control_node"])
def test_archived_ep2_is_explicit_and_current_loader_still_rejects(task):
    manifest=EP2/task/"manifest.json"
    rows=load_ep2_edges(manifest)
    assert len(rows)==(748 if task=="reentrancy_node" else 759)
    with pytest.raises(ValueError,match="SHA mismatch"):load_edges(manifest)


def test_archive_snapshot_hash_mismatch_rejected(tmp_path):
    p=tmp_path/"snapshot.txt";p.write_text("original")
    record=ref(p);snap=ref(p)
    p.write_text("changed")
    with pytest.raises(ValueError,match="SHA mismatch"):_check_source(record,{record["path"]:snap})
    with pytest.raises(ValueError,match="identity differs"):
        _check_source(record,{record["path"]:ref(p)})
