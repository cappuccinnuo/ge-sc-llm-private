from scripts.DFG.state.audit import side_relations,information_increment
from scripts.DFG.state.tests.test_semantics import run
from scripts.DFG.state.tests.test_projection import fixture
from scripts.DFG.state.projection import augment_state

def test_access_order_sidecar_not_reverse_def_use():
    _,r=run('uint a=b[msg.sender];to.call.value(a)("");b[msg.sender]=0;')
    assert not r.facts
    sides=side_relations(r)
    assert any(x["relation"]=="STATE_ACCESS_ORDER" for x in sides)
    assert any(x["relation"]=="EXTERNAL_CALL_BEFORE_STATE_WRITE" for x in sides)
    assert all(not x["model_edge"] for x in sides)

def test_access_order_is_next_access_not_transitive_closure():
    _,r=run("x=1;x=2;require(x>0);")
    sides=[x for x in side_relations(r) if x["relation"]=="STATE_ACCESS_ORDER"]
    assert len(sides)==2

def test_topology_increment_keeps_original_nodes_and_reports_no_score():
    g,s=fixture();out,_=augment_state(g,{"p.sol":s})
    d=information_increment(g,out)
    assert d["state_edges"]==1
    assert len(d["new_canonical_relations"])==1
    assert d["parameter_increment_if_hidden128_heads8_layers2"]==8208
