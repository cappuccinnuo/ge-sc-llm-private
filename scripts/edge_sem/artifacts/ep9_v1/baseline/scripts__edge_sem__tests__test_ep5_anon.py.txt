"""EP5 exact binding translation, negative integrity gates and loop exceptions."""
import copy
import hashlib
import numpy as np
import pytest
from scripts.edge_sem.tests.test_attrs import bundle,FILE
from scripts.edge_sem.recon.ep5_anon import translate,evaluate,TranslationError,EvidenceTranslation
from scripts.edge_sem.recon.ep5_delta import hard_delta
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.anon_binding import anonymize


@pytest.mark.parametrize("body",[
    "uint state; function f(uint p) public { uint x=p; state=x; }",
    "uint owner; modifier check(uint p) { require(p>owner); _; } function f(uint p) public check(p) { uint x=p; owner=x; }",
    "function f(uint p) public { { uint x=p; uint y=x; } { uint x=p+1; uint y=x; } }",
])
def test_translation_preserves_graph_space_attributes(body):
    ctx,g,edges,facts,values=bundle(body=body,pragma="^0.5.11")
    before=graph_fingerprint(g);old=copy.deepcopy(ctx["audit"])
    h,evidence,result,proof=translate(ctx["source_text"][FILE],FILE,g,ctx["audit"])
    assert result["status"]=="renamed"
    fresh,attrs,_=evaluate(result["rewritten"],FILE,h,evidence,proof["metadata"],proof["original_names"])
    assert {(e["src"],e["dst"],e["relation"]) for e in fresh}=={(e["src"],e["dst"],e["relation"]) for e in edges}
    assert attrs.keys()==values.keys()
    assert all(np.array_equal(values[k],attrs[k]) for k in attrs)
    assert graph_fingerprint(g)==before and ctx["audit"]==old


def test_fallback_is_identity_and_counted():
    ctx,g,_,_,_=bundle(body="function f() public { assembly { mstore(0,1) } }")
    h,evidence,result,proof=translate(ctx["source_text"][FILE],FILE,g,ctx["audit"])
    assert result["status"]=="fallback" and proof["fallback_identity"]
    assert graph_fingerprint(h)==graph_fingerprint(g) and evidence==ctx["audit"]


def test_bad_sealed_symbol_is_rejected():
    ctx,g,_,_,_=bundle(body="function f(uint p) public { uint x=p; uint y=x; }")
    bad=copy.deepcopy(ctx["audit"]);bad["layers"]["L1"]["evidence"][0]["symbol"]="wrong"
    with pytest.raises(ValueError,match="symbol identity"):
        translate(ctx["source_text"][FILE],FILE,g,bad)


def test_unbound_occurrence_not_replaced_by_global_name():
    ctx,g,_,_,_=bundle(body="uint state; function f(uint p) public { state=p; }")
    source=ctx["source_text"][FILE];result=anonymize(source)
    tx=EvidenceTranslation(source,FILE,result)
    with pytest.raises(TranslationError,match="No unique"):
        tx.name_at(dict(name="state",start=0,end=1,role="identifier"))


def test_tampered_binding_rejected():
    source="pragma solidity ^0.5.11; contract C { uint state; }"
    result=anonymize(source);bad=copy.deepcopy(result);bad["edits"][0]["new"]="wrong"
    with pytest.raises(TranslationError,match="new name"):
        EvidenceTranslation(source,"f.sol",bad)


def test_delta_rejects_unauthorized_bits_order_and_added_carried():
    old=np.zeros((2,74),dtype=np.uint8);old[0,20]=1;new=old.copy();new[0,20]=0
    assert hard_delta(["a","b"],old,["a","b"],new)["changed_bit20"]==1
    with pytest.raises(ValueError,match="order"):hard_delta(["a","b"],old,["b","a"],new)
    new[1,3]=1
    with pytest.raises(ValueError,match="Unauthorized"):hard_delta(["a","b"],old,["a","b"],new)
    new[1,3]=0;new[1,20]=1
    with pytest.raises(ValueError,match="subset"):hard_delta(["a","b"],old,["a","b"],new)


def test_state_initializer_callable_identity_is_translated():
    source="pragma solidity ^0.5.11; contract L {} contract C { L internal x = L(address(0)); function f(uint p) public { uint y=p; } }"
    ctx,g,edges,_,values=bundle(source=source)
    h,evidence,result,proof=translate(source,FILE,g,ctx["audit"])
    assert result["status"]=="renamed"
    fresh,attrs,_=evaluate(result["rewritten"],FILE,h,evidence,proof["metadata"],proof["original_names"])
    assert all(np.array_equal(values[k],attrs[k]) for k in values)

def synthetic_if_graph():
    import networkx as nx
    from scripts.DFG.dfg_v2.projection_view import ProjectionView
    source="pragma solidity ^0.5.11; contract C { function f(bool success) public { if (!success) { revert(); } } function g(bool success) public { if (!success) { revert(); } } }"
    view=ProjectionView(source,FILE);graph=nx.MultiDiGraph()
    ids=[]
    for k,i in view.compat_ids.items():
        if k[2]!="if_statement":continue
        node=view.compat_nodes[k];code=view.compat[k[0]:k[1]].decode()
        graph.add_node(i,source_file=FILE,node_type="if",code=code,
            label="{}-if-{}-{}".format(i,node.start_point[0]+1,node.end_point[0]+1))
        ids.append(i)
    for i in ids:
        graph.add_node("end:"+str(i),source_file=FILE,node_type="end_if",code=graph.nodes[i]["code"],label="end_if")
        graph.add_edge(i,"end:"+str(i),edge_type="neg_next")
    return source,graph,ids


def test_synthetic_end_if_unique_cfg_parent_recovers_exact_binding():
    from scripts.edge_sem.recon.ep5_anon import exact_code_view
    from scripts.DFG.dfg_v2.benchmark_v2.anon_parity import node_code_view
    source,g,ids=synthetic_if_graph();result=anonymize(source)
    with pytest.raises(ValueError,match="Synthetic code projection"):
        node_code_view(g,FILE,source,result)
    codes,proof=exact_code_view(g,FILE,source,result)
    assert codes[ids[0]]!=codes[ids[1]]
    for i in ids:assert codes["end:"+str(i)]==codes[i]
    assert sum(r["basis"]=="unique_neg_next_from_exact_if" for r in proof)==2


@pytest.mark.parametrize("change",["missing","multiple","wrong_role"])
def test_synthetic_end_if_other_ambiguity_rejected(change):
    from scripts.edge_sem.recon.ep5_anon import exact_code_view
    source,g,ids=synthetic_if_graph();target="end:"+str(ids[0])
    if change=="missing":g.remove_edge(ids[0],target)
    elif change=="multiple":g.add_edge(ids[1],target,edge_type="neg_next")
    else:
        g.remove_edge(ids[0],target)
        g.add_edge("end:"+str(ids[1]),target,edge_type="neg_next")
    with pytest.raises(TranslationError,match="end_if"):
        exact_code_view(g,FILE,source,anonymize(source))
