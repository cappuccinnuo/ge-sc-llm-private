"""Graph integration fixtures are static parser tests, not solc validation."""
import copy, json, pickle
import numpy as np
import pytest
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.pipeline import augment
from scripts.DFG.state.stage_j.pipeline import prepare_graph
from scripts.DFG.state.stage_j.configuration import DDGConfig
from scripts.DFG.state.stage_j.cli import main,sha,load_sources
from scripts.DFG.state.stage_f.projection import assert_preserved
from scripts.DFG.state.stage_f.model_adapter import build_dgl
from scripts.DFG.state.stage_f.compatibility import smoke
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source

SRC="pragma solidity 0.5.17;contract A{uint s;}contract B{}contract C is A,B{modifier init(){s=1;_;}function f(address payable to) public init returns(uint){to.transfer(s);s=2;return s;}}"
def graph(src=SRC):
    g=generate_cfg_from_source(src,"p.sol")
    for i,(_,d) in enumerate(g.nodes(data=True)):
        d["token"]=np.arange(8,dtype=np.float32)+i
        d["node_info_vulnerabilities"]=None
    return augment(g,{"p.sol":src})[0]

def typed(g):
    return {(s,t,d["edge_type"]) for s,t,d in g.edges(data=True)}

def test_project_facts_and_keep_original_graph():
    g=graph();before=fingerprint(g)
    new,a=prepare_graph(g,{"p.sol":SRC})
    assert fingerprint(g)==before
    assert_preserved(g,new)
    assert len(new)==len(g) and list(g.nodes)==list(new.nodes)
    assert typed(g)<=typed(new)
    assert a["files"]["p.sol"]["recovered_functions"]==1
    assert a["files"]["p.sol"]["recovered_runtime_functions"]==1
    assert set(a["relation_counts"]) >= {"STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE"}
    assert a["invariants"]["new_fingerprint"]==fingerprint(new)
    assert all(e["coverage_analysis"]["recovered_function"] for e in a["evidence"])

def test_off_exact_and_no_source_required():
    g=graph();new,a=prepare_graph(g,config=DDGConfig(use_ddg=False))
    assert fingerprint(g)==fingerprint(new) and a["disabled_exact"]

def test_state_off_preserves_scalar_input():
    g=graph();new,_=prepare_graph(g,config=DDGConfig(state_mode="off"))
    assert fingerprint(g)==fingerprint(new)

def test_raw_hcg_to_complete_pipeline():
    g=generate_cfg_from_source(SRC,"p.sol")
    for _,d in g.nodes(data=True):d["token"]=np.zeros(8,dtype=np.float32);d["node_info_vulnerabilities"]=None
    new,a=prepare_graph(g,{"p.sol":SRC},DDGConfig(add_scalar=True))
    assert "scalar" in a and len(new)==len(g)
    assert "STATE_DEF_USE" in a["relation_counts"]

def test_double_application_rejected():
    g=graph();new,_=prepare_graph(g,{"p.sol":SRC})
    with pytest.raises(ValueError,match="mix state"):
        prepare_graph(new,{"p.sol":SRC})

@pytest.mark.parametrize("sources",[{},{"p.sol":SRC.replace("s=2;","s=99;")}])
def test_missing_or_wrong_source_no_guess_mapping(sources):
    g=graph();new,a=prepare_graph(g,sources)
    assert fingerprint(new)==fingerprint(g)

def test_label_and_feature_values_not_used_to_construct_edges():
    g=graph();a,aa=prepare_graph(g,{"p.sol":SRC})
    for _,d in g.nodes(data=True):
        d["node_info_vulnerabilities"]=[{"lines":[999999],"category":"fake"}]
        d["token"]=np.ones(8,dtype=np.float32)*777
    b,bb=prepare_graph(g,{"p.sol":SRC})
    assert typed(a)==typed(b) and aa["evidence"]==bb["evidence"]

def test_scope_modes_select_only_authorized_recovery():
    g=graph()
    a,_=prepare_graph(g,{"p.sol":SRC},DDGConfig(recovery="frozen"))
    b,_=prepare_graph(g,{"p.sol":SRC},DDGConfig(recovery="inheritance"))
    assert fingerprint(g)==fingerprint(a)==fingerprint(b)
    c,_=prepare_graph(g,{"p.sol":SRC},DDGConfig(state_mode="def_use"))
    added=typed(c)-typed(g)
    assert added and {r for _,_,r in added}=={"STATE_DEF_USE"}

def test_missing_write_anchor_still_kills_in_semantic_ir():
    src="pragma solidity 0.5.17;contract A{uint s;}contract B{}contract C is A,B{function f() public returns(uint){s=1;s=2;return s;}}"
    g=graph(src)
    remove=[n for n,d in g.nodes(data=True) if d.get("code")=="s=2;"]
    assert len(remove)==1;g.remove_node(remove[0])
    new,a=prepare_graph(g,{"p.sol":src})
    assert not any(d["edge_type"]=="STATE_DEF_USE" for _,_,d in new.edges(data=True))
    assert a["files"]["p.sol"]["projection"]["missing_anchors"]

def test_failed_modifier_leaves_no_partial_edges_and_other_function_recovers():
    src="pragma solidity 0.5.17;contract A{uint s;}contract B{}contract C is A,B{modifier bad(){s=1;_;s=2;}function f() public bad returns(uint){return s;}function good() public returns(uint){s=3;return s;}}"
    g=graph(src);new,a=prepare_graph(g,{"p.sol":src})
    assert any(d["edge_type"]=="STATE_DEF_USE" for _,_,d in new.edges(data=True))
    functions=a["files"]["p.sol"]["functions"]
    assert next(x for x in functions if x["name"]=="f")["after"]=="function_fallback"
    assert next(x for x in functions if x["name"]=="good")["recovered"]
    assert all(e["function"]!=next(x for x in functions if x["name"]=="f")["function"] for e in a["evidence"])

def test_same_endpoint_different_relations_survive_and_forward_counts():
    g=graph();new,_=prepare_graph(g,{"p.sol":SRC})
    edge=next((s,t) for s,t,d in new.edges(data=True) if d["edge_type"]=="STATE_DEF_USE")
    g.add_edge(*edge,edge_type="next")
    new,_=prepare_graph(g,{"p.sol":SRC})
    assert new.has_edge(*edge) and {"next","STATE_DEF_USE"} <= {d["edge_type"] for d in new.get_edge_data(*edge).values()}
    dg,_=build_dgl(new)
    for rel in ["DATA_DEF_USE","STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE"]:
        assert sum(dg.num_edges(k) for k in dg.canonical_etypes if k[1]==rel)==sum(d["edge_type"]==rel for _,_,d in new.edges(data=True))

def test_real_hgt_layer_reads_new_relations_and_reloads(tmp_path):
    g=graph();new,_=prepare_graph(g,{"p.sol":SRC})
    record=smoke(g,new,tmp_path/"synthetic_initial.pt")
    assert record["optimizer_steps"]==0 and len(record["relation_message_gradient_l1"])==3
    assert all(v>0 for v in record["relation_message_gradient_l1"].values())

@pytest.mark.parametrize("kwargs",[{"state_mode":"all"},{"recovery":"guess"},{"max_iterations":0}])
def test_invalid_config_rejected(kwargs):
    with pytest.raises(ValueError):DDGConfig(**kwargs)

def test_cli_end_to_end_and_overwrite_rejection(tmp_path):
    g=graph();p=tmp_path/"g.pickle";p.write_bytes(pickle.dumps(g))
    s=tmp_path/"p.sol";s.write_text(SRC)
    m=tmp_path/"sources.json";m.write_text(json.dumps({"sources":{"p.sol":{"path":str(s),"sha256":sha(s)}}}))
    args=["--graph",str(p),"--graph-sha256",sha(p),"--sources",str(m),"--output",str(tmp_path/"out")]
    main(args)
    record=json.loads((tmp_path/"out/manifest.json").read_text())
    assert not record["training_executed"] and record["forward_relation_counts"]["STATE_DEF_USE"]>0
    with pytest.raises(ValueError,match="exists"):main(args)

def test_bad_source_hash_rejected(tmp_path):
    p=tmp_path/"p.sol";p.write_text(SRC)
    m=tmp_path/"manifest.json";m.write_text(json.dumps({"p.sol":{"path":str(p),"sha256":"wrong"}}))
    with pytest.raises(ValueError,match="digest"):load_sources(m)
