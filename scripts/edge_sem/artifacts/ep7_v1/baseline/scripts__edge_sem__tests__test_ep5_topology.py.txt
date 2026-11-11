"""CPU-only graph-space reachability and identity tests."""
import copy
import networkx as nx
import pytest
from scripts.edge_sem.recon.ep5_topology import reflected_graph,reachable_evidence,node_degrees,graph_statistics


def test_reflection_keeps_original_ids_and_typed_topology():
    g=nx.MultiDiGraph()
    g.add_node(19,node_type="expression_statement",source_file="f.sol")
    g.add_node("env:f",node_type="env_source",source_file="f.sol")
    g.add_node(42,node_type="expression_statement",source_file="f.sol")
    g.add_edge(19,42,edge_type="next_line")
    g.add_edge("env:f",19,edge_type="ENV_FLOW")
    original=copy.deepcopy(g)
    a,da=reflected_graph(g,"G3R");b,db=reflected_graph(g,"G3R-T")
    assert list(a)==list(g)==list(b)
    assert set(a.edges())==set(b.edges())=={(19,42),(42,19),("env:f",19),(19,"env:f")}
    assert len(da)==3 and len(db)==4
    assert list(g.edges(data=True))==list(original.edges(data=True))
    assert all("node_hetero_id" not in v for _,v in g.nodes(data=True))
    c,dc=reflected_graph(g,"G4R",[dict(src=42,dst=19,relation="GUARDS",file="f.sol")])
    assert c.number_of_edges()==6
    stats=graph_statistics(c,dc)
    assert stats["indegree_by_node_type"]["expression_statement"]["mean_indegree"]==2.5


def test_two_hop_counts_unique_nodes_and_excludes_origin_and_distant_nodes():
    g=nx.MultiDiGraph()
    g.add_edges_from([(0,1),(0,1),(1,0),(1,2),(2,3)])
    e=dict(external_call={0,1,3},state_write={1,2},guard_condition={2},modifier_definition=set())
    r=reachable_evidence(g,0,e)
    assert r["counts"]==dict(external_call=1,state_write=2,guard_condition=1,modifier_definition=0)
    assert r["total_unique"]==2 and r["distance"]==[dict(node=1,hops=1),dict(node=2,hops=2)]


def test_topology_refuses_cross_file_and_degree_keys_include_relation():
    g=nx.MultiDiGraph();g.add_node(0,node_type="if",source_file="a");g.add_node(1,node_type="if",source_file="b")
    with pytest.raises(ValueError,match="cross-file"):
        reflected_graph(g,"G4R",[dict(src=0,dst=1,relation="GUARDS",file="a")])
    g.add_edge(0,1,edge_type="next_line");a=node_degrees(g)
    g[0][1][0]["edge_type"]="pos_next"
    assert a!=node_degrees(g)

def test_case_fingerprints_use_frozen_store_algorithms(tmp_path):
    from scripts.edge_sem.recon.ep5_topology import validate_case,stored_fingerprint,computation_fingerprint
    from scripts.edge_sem.io import ref
    g=nx.MultiDiGraph();g.add_node(1,node_type="expression_statement",source_file="a.sol")
    src=tmp_path/"a.sol";src.write_text("contract C {}")
    gp=tmp_path/"graph.bin";gp.write_bytes(b"frozen reference")
    source=ref(src);record=ref(gp)
    record.update(fingerprint=stored_fingerprint(g),computation_fingerprint=computation_fingerprint(g))
    c=dict(task_id="t",case_type="persistent_fn",all_missed=True,file="a.sol",
        original_graph_node_id=1,node_type="expression_statement",source_sha256=source["sha256"],
        source=source,graph=record)
    ctx=dict(sources={"a.sol":source},provenance=dict(graphs={"F3":record}))
    validate_case(c,"t",ctx,g)
    for field in ("fingerprint","computation_fingerprint"):
        bad=copy.deepcopy(c);bad["graph"][field]="wrong"
        with pytest.raises(ValueError,match="fingerprint"):
            validate_case(bad,"t",ctx,g)
    bad=copy.deepcopy(c);bad["source_sha256"]="wrong"
    with pytest.raises(ValueError,match="source SHA"):validate_case(bad,"t",ctx,g)
