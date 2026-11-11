"""EP0 probes are independently checked before observing frozen inputs."""
import networkx as nx
import pytest
import torch
from scripts.edge_sem.recon.common import typed_data, cfg_dominance, checked
from scripts.edge_sem.recon.semantic import nearest_events

def test_probe_imports():
    from scripts.node_sem.facts import STATEMENTS
    from scripts.node_sem.facts_ast import AstSemantics
    assert "expression_statement" in STATEMENTS
    assert hasattr(AstSemantics,"resolve_callable")

def test_typed_preserves_opposite_forward_identity():
    data={("A","next_line","B"):(torch.tensor([0,1]),torch.tensor([2,3])),
          ("B","next_line","A"):(torch.tensor([4]),torch.tensor([5]))}
    out,origins=typed_data(data)
    assert len(out)==4
    assert out[("A","next_line","B")][0].tolist()==[0,1]
    assert out[("A","REV_next_line","B")][0].tolist()==[5]
    assert origins[("B","REV_next_line","A")]==("B","next_line","A")

def test_v2_reverse_and_same_type_are_distinct():
    data={("A","DATA_DEF_USE","A"):(torch.tensor([0]),torch.tensor([1]))}
    out,origin=typed_data(data)
    assert len(out)==2
    assert out[("A","REV_DATA_DEF_USE","A")][0].tolist()==[1]
    assert origin[("A","REV_DATA_DEF_USE","A")]==("A","REV_DATA_DEF_USE","A")

def test_reverse_input_rejected():
    with pytest.raises(ValueError):
        typed_data({("A","REV_X","B"):(torch.tensor([0]),torch.tensor([0]))})

def test_loop_dominance_and_multiple_exits():
    g=nx.DiGraph([(0,1),(1,2),(2,1),(1,3),(2,4)])
    active,dom,post,back=cfg_dominance(g,0)
    assert back==[(2,1)]
    assert len(post)-1==len(active)==5
    assert dom[2]==1

def test_nonterminating_path_not_reported_as_postdominated():
    g=nx.DiGraph([(0,1),(0,2),(1,1)])
    active,dom,post,back=cfg_dominance(g,0)
    assert 1 in dom and 1 not in post
    assert len(post)-1<len(active)

def test_irreducible_cycle_not_called_natural_backedge():
    g=nx.DiGraph([(0,1),(0,2),(1,2),(2,1),(2,3)])
    assert cfg_dominance(g,0)[3]==[]

def test_sha_mismatch_rejected(tmp_path):
    p=tmp_path/"x";p.write_bytes(b"x")
    with pytest.raises(ValueError):
        checked(dict(path=str(p),sha256="0"*64))


def test_call_census_excludes_builtin_and_event():
    from scripts.DFG.dfg_v2.projection_view import ProjectionView
    from scripts.node_sem.facts_ast import AstSemantics
    from scripts.edge_sem.recon.calls import classify
    src = "pragma solidity ^0.4.24; contract C { uint x; event Changed(uint v); function h() internal {} function f() public { require(x>0); h(); Changed(x); emit Changed(x); } }"
    sem=AstSemantics(ProjectionView(src,"fixture.sol"))
    kinds=[classify(sem,n)[0]for n in sem.nodes if n.type=="call_expression"]
    assert kinds.count("builtin")==1
    assert kinds.count("resolved_internal")==1
    assert kinds.count("event_struct_enum_error")==1
    assert "unclassified_unqualified" not in kinds

def test_modifier_anchor_is_invocation_not_body():
    from scripts.DFG.dfg_v2.projection_view import ProjectionView
    from scripts.node_sem.facts_ast import AstSemantics
    from scripts.node_sem.facts_guards import GuardAnalyzer
    src="pragma solidity ^0.4.24; contract C { uint x; modifier gate(){require(x>0); _;} function f() public gate {x=1;} }"
    sem=AstSemantics(ProjectionView(src,"fixture.sol"))
    guards=GuardAnalyzer(sem)
    f=next(n for n in sem.functions if sem.text(n.child_by_field_name("name"))=="f")
    st=next(n for n in sem.nodes if n.type=="expression_statement" and sem.owner(n)==f)
    values=[g for g in guards.for_node(st)["guards"]if g["kind"]=="modifier"]
    assert len(values)==1 and values[0]["_anchor"].type=="modifier_invocation"

def test_all_attribute_slots_are_audited():
    from scripts.edge_sem.recon.report import source_table
    rows=source_table()
    assert len(rows)==73
    assert rows[15]["status"]=="unavailable_zero_as_specified"
    assert rows[7]["status"]=="needs_source_join"
