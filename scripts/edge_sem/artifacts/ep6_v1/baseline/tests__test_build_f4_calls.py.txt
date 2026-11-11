"""EP2 builder unit tests and independently specified real-source cases."""
import copy
import hashlib
import json
from pathlib import Path
import networkx as nx
import pytest
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
from scripts.node_sem.facts_ast import AstSemantics,key
from scripts.node_sem.facts import _raw_projection
from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.edge_sem.build_f4 import inspect_file,add_edges,modifier_target
from scripts.edge_sem.recon.common import ROOT,read,checked

FIXTURE=Path(__file__).parent/"fixtures"/"ep2_calls.sol"


def synthetic(source=None):
    source=source or FIXTURE.read_text()
    graph=nx.MultiDiGraph(generate_cfg_from_source(source,"ep2.sol"))
    return source,graph


def code(source,anchor):
    return source.encode()[anchor[0]:anchor[1]].decode()


def target_name(source,row):
    sem=AstSemantics(ProjectionView(source,row["file"]))
    target=next(n for n in sem.functions if list(key(n))==row["dst_anchor"])
    return sem.text(target.child_by_field_name("name"))


def test_modifiers_inheritance_constructor_and_unresolved():
    source,graph=synthetic()
    edges,audit=inspect_file("ep2.sol",source,graph)
    rows=[r for r in edges if r["relation"]=="MOD_APPLY"]
    run=[r for r in rows if code(source,r["src_anchor"]).startswith("function run")]
    assert len(run)==2 and {target_name(source,r) for r in run}=={"localGate","inheritedGate"}
    assert len([r for r in rows if r["src_anchor"][2]=="constructor_definition"])==1
    assert audit["counts"]["modifier_inherited"]==2
    assert audit["statuses"]["MOD_APPLY:unresolved"]==1
    assert not any(code(source,r["src_anchor"]).startswith("function bad") for r in rows)


def test_call_sites_dedup_library_overloads_and_exclusions():
    source,graph=synthetic()
    edges,audit=inspect_file("ep2.sol",source,graph)
    calls=[r for r in edges if r["relation"]=="CALL_SITE"]
    assert len(calls)==7
    double=next(r for r in calls if code(source,r["src_anchor"])=="x = helper(a) + helper(a);")
    assert target_name(source,double)=="helper" and len(double["evidence"])==2
    assert audit["statuses"]["CALL_SITE:duplicate"]==1
    assert any(code(source,r["src_anchor"])=="helper(1);" for r in calls)
    assert sum(r["kind"]=="library" for r in calls)==2
    assert sum(r["kind"]=="overload_arity" for r in calls)==2
    assert audit["statuses"]["CALL_STATUS:external_member"]==1
    assert audit["statuses"]["CALL_STATUS:address_builtin"]==1
    assert not any(target_name(source,r)=="transfer" for r in calls)


@pytest.mark.parametrize("body,invocation,reason",[
    ("_;","g(1,2)","placeholder_or_arguments"),
    ("uint a=1;","g(1)","placeholder_or_arguments"),
    ("_;_;","g(1)","multiple_placeholders"),
])
def test_modifier_frozen_argument_and_placeholder_limits(body,invocation,reason):
    source,graph=synthetic("pragma solidity ^0.5.11; contract C {modifier g(uint x){"+body+
        "} function f() public "+invocation+" {}}")
    edges,audit=inspect_file("ep2.sol",source,graph)
    assert not [r for r in edges if r["relation"]=="MOD_APPLY"]
    assert audit["reasons"]["MOD_APPLY:"+reason]==1


def test_missing_graph_endpoint_is_audited_without_guess():
    source,graph=synthetic()
    edges,_=inspect_file("ep2.sol",source,graph)
    target=next(r["dst"] for r in edges if r["relation"]=="CALL_SITE" and target_name(source,r)=="helper")
    graph.remove_node(target)
    changed,audit=inspect_file("ep2.sol",source,graph)
    assert all(r["dst"]!=target for r in changed)
    assert audit["statuses"]["CALL_SITE:not_in_graph"]==4


def test_add_edges_preserves_input_nodes_original_edges_and_independent_values():
    source,graph=synthetic();edges,_=inspect_file("ep2.sol",source,graph)
    before=graph_fingerprint(graph)
    enriched=add_edges(graph,edges)
    assert graph_fingerprint(graph)==before and enriched is not graph
    assert list(enriched.nodes(data=True))==list(graph.nodes(data=True))
    for a,b,k,attrs in graph.edges(keys=True,data=True):assert enriched[a][b][k]==attrs
    assert enriched.number_of_edges()==graph.number_of_edges()+len(edges)
    first=next(iter(graph));enriched.nodes[first]["code"]="changed"
    assert graph_fingerprint(graph)==before


@pytest.mark.parametrize("change",["cross_file","missing","relation","duplicate","self","anchor"])
def test_invalid_edge_bundle_rejected_without_mutation(change):
    source,graph=synthetic();edges,_=inspect_file("ep2.sol",source,graph)
    before=graph_fingerprint(graph);rows=copy.deepcopy(edges)
    if change=="cross_file":rows[0]["file"]="other.sol"
    elif change=="missing":rows[0]["dst"]="absent"
    elif change=="relation":rows[0]["relation"]="GUARDS"
    elif change=="duplicate":rows.append(copy.deepcopy(rows[0]))
    elif change=="self":rows[0]["dst"]=rows[0]["src"]
    else:rows[0]["src_anchor"][0]=-1
    with pytest.raises(ValueError):add_edges(graph,rows)
    assert graph_fingerprint(graph)==before


def test_predictions_labels_and_spelling_do_not_select_edges():
    source,graph=synthetic();rows,audit=inspect_file("ep2.sol",source,graph)
    changed=copy.deepcopy(graph)
    for _,attrs in changed.nodes(data=True):
        attrs.update(type_label=999,node_info_vulnerabilities=[{"category":"anything"}],
                     method="arbitrary",prediction=1)
    assert inspect_file("ep2.sol",source,changed)==(rows,audit)


# Reviewed directly in the original sources, before running the builder.
REAL_EXPECTATIONS={
    ("reentrancy_node","reentrancy_bonus.sol"):(
        "628f60b16c878d8dfe5a271a26f6a83574fbeaae27a62a059467dab8974db332",
        [],[("withdrawReward(recipient);","withdrawReward")]),
    ("access_control_node","rubixi.sol"):(
        "a4c33aa1b035feff8e114e5afab6a15e524636d4ea4660459d3b5909272eabed",
        ["collectAllFees","collectFeesInEther","collectPercentOfFees","changeOwner","changeMultiplier","changeFeePercentage"],
        [("init();","init"),("addPayout(_fee);","addPayout"),("collectAllFees();","collectAllFees")]),
    ("access_control_node","unprotected0.sol"):(
        "8cfc8702a1a0afe407c2ea83e0c48e97909f66af1955ee5e1321f1dc2818a045",[],[]),
}


@pytest.mark.parametrize("identity",list(REAL_EXPECTATIONS))
def test_real_manually_reviewed_files(identity):
    from scripts.node_sem.facts_io import load_context
    task,file=identity;sha,mods,calls=REAL_EXPECTATIONS[identity]
    ctx=load_context(task)
    assert file in ctx["source_text"],"Required real file missing: "+file
    source=ctx["source_text"][file]
    assert hashlib.sha256(source.encode()).hexdigest()==sha
    rows,audit=inspect_file(file,source,ctx["graphs"]["F3"])
    sem=AstSemantics(ProjectionView(source,file))
    functions={key(n):n for n in sem.functions}
    actual_mods=[]
    for r in rows:
        if r["relation"]=="MOD_APPLY":
            actual_mods.append(sem.text(functions[tuple(r["src_anchor"])].child_by_field_name("name")))
            assert target_name(source,r)=="onlyowner"
    assert sorted(actual_mods)==sorted(mods)
    assert sorted((code(source,r["src_anchor"]),target_name(source,r)) for r in rows
                  if r["relation"]=="CALL_SITE")==sorted(calls)
