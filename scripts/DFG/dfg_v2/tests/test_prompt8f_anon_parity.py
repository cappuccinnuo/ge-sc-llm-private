"""8F source/HCG identity, parity normalization and fail-closed preparation."""
import copy
import json
import pytest
from scripts.DFG.dfg_v2.benchmark_v2.anon_binding import anonymize
from scripts.DFG.dfg_v2.benchmark_v2.anon_parity import (
    check_file, node_code_view, bound_evidence_counter)
from scripts.DFG.dfg_v2.benchmark_v2.prepare_anon import load_names, require_complete
from scripts.DFG.dfg_v2.benchmark_v2.prepare import write, ref
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.tests.test_l1 import graph_for, FILE
from scripts.DFG.dfg_v2.tests.test_l3 import Encoder
from scripts.DFG.dfg_v2.pipeline import build

SOURCE = """pragma solidity ^0.5.0;
contract C {
 struct S { uint quantity; }
 uint stored;
 function f(uint amount) public {
   S memory local;
   local.quantity=amount;
   uint other=local.quantity;
   stored=other;
   require(msg.sender != tx.origin);
 }
}"""

def fixture():
    base=graph_for(SOURCE)
    archive,audit=build(base,{FILE:SOURCE},{},["L1","L2","L3"],Encoder())
    return base,archive,audit,anonymize(SOURCE)

def test_all_name_parity_preserves_raw_facts_edges_labels_and_tokens():
    base,archive,audit,res=fixture()
    before=graph_fingerprint(base)
    out=check_file(base,archive,audit,SOURCE,FILE,res,None,Encoder())
    assert out["passed"] and out["normalized_facts_exact"] and out["projected_endpoints_exact"]
    assert graph_fingerprint(base)==before

def test_analysis_path_v2_is_never_a_user_identifier():
    base,archive,audit,res=fixture()
    # Force one anonymous declaration to v2 if this seed already did not.
    # The audit vocabulary must always stay "v2" regardless of inverse mapping.
    counters=bound_evidence_counter(audit,FILE,SOURCE,{"v2":"not_an_analysis_path"})
    assert any(json.loads(s)["analysis_path"]=="v2" for s in counters["L1"])
    assert all("not_an_analysis_path" not in s for s in counters["L1"])

def test_exact_fact_tampering_fails_without_hiding_in_counts():
    base,archive,audit,res=fixture()
    audit["layers"]["L1"]["evidence"][0]["target"]=-999
    out=check_file(base,archive,audit,SOURCE,FILE,res,None,Encoder())
    assert not out["passed"] and not out["normalized_facts_exact"]

def test_missing_projected_edge_fails():
    base,archive,audit,res=fixture()
    s,t,k=next((s,t,k) for s,t,k,a in archive.edges(keys=True,data=True) if a["edge_type"]=="DATA_DEF_USE")
    archive.remove_edge(s,t,k)
    out=check_file(base,archive,audit,SOURCE,FILE,res,None,Encoder())
    assert not out["passed"] and not out["projected_endpoints_exact"]

def test_graph_code_tampering_is_rejected():
    base,archive,audit,res=fixture()
    nid=next(iter(base))
    base.nodes[nid]["code"]="not the source"
    with pytest.raises(Exception):
        node_code_view(base,FILE,SOURCE,res)

def test_fallback_has_no_node_feature_view():
    source="contract C { uint x; }"
    with pytest.raises(ValueError,match="Fallback"):
        node_code_view(graph_for(source),FILE,source,anonymize(source))

def test_same_text_synthetic_node_with_different_bindings_rejected():
    source="""pragma solidity ^0.5.0;
contract C {
 function a(uint amount) public { if(amount>0) { amount--; } }
 function b(uint amount) public { if(amount>0) { amount--; } }
}"""
    graph=graph_for(source)
    res=anonymize(source)
    assert res["status"]=="renamed"
    with pytest.raises(ValueError,match="ambiguous declaration binding"):
        node_code_view(graph,FILE,source,res)

def make_manifest(tmp_path,status="fallback"):
    src=tmp_path/"a.sol";src.write_text("original")
    result=tmp_path/"a.json";write(result,dict(status=status,edits=[],bindings=[]))
    rows={"example/a.sol":dict(source=ref(src),result=ref(result))}
    path=tmp_path/"sources.json";write(path,rows)
    manifest=dict(source_identities=1,fallback_files=int(status=="fallback"),
                  binding_complete=status=="renamed",artifacts={"sources":ref(path)})
    write(tmp_path/"manifest.json",manifest)
    write(tmp_path/"manifest.seal.json",dict(manifest=ref(tmp_path/"manifest.json")))
    return manifest,rows

def test_partial_population_cannot_silently_enter_probes_or_plan(tmp_path):
    make_manifest(tmp_path)
    manifest,rows=load_names(tmp_path)
    with pytest.raises(ValueError,match="fallback"):
        require_complete(manifest,rows)

def test_false_passed_flag_does_not_override_file_fallback(tmp_path):
    manifest,rows=make_manifest(tmp_path)
    manifest.update(binding_complete=True,fallback_files=0)
    with pytest.raises(ValueError,match="fallback"):
        require_complete(manifest,rows)

@pytest.mark.parametrize("name",["sources.json","a.json","a.sol","manifest.json"])
def test_mutated_source_result_manifest_rejected(tmp_path,name):
    make_manifest(tmp_path)
    with (tmp_path/name).open("a") as f:f.write("changed")
    with pytest.raises((ValueError,KeyError)):
        load_names(tmp_path)

def test_decl_renaming_covers_modifiers_struct_named_args_and_library_calls():
    source="""pragma solidity ^0.5.0;
library Lib { function inc(uint amount) internal returns(uint) { return amount+1; } }
contract C {
 using Lib for uint;
 struct Item {uint total;}
 modifier allowed(uint flag) { require(flag>0); _; }
 Item item; uint stored;
 function f(uint amount) public allowed(amount) {
   item=Item({total:amount}); stored=amount.inc();
 }
}"""
    res=anonymize(source)
    assert res["status"]=="renamed",res["issues"]
    for name in ("Lib","inc","Item","total","allowed","flag"):
        assert len({e["new"] for e in res["edits"] if e["old"]==name})==1

def test_disjoint_scope_unknown_receiver_does_not_pick_global_same_name():
    source="pragma solidity 0.5.11; contract A { uint x; function f() public { missing.x=1; } }"
    res=anonymize(source)
    assert res["status"]=="fallback" and not res["edits"]

def test_utf8_comments_strings_keep_original_bytes():
    source='pragma solidity 0.5.11; /* 中文 */ contract C { string text="名字"; uint amount; function f() public { amount++; } }'
    result=anonymize(source)
    assert result["status"]=="renamed"
    assert '/* 中文 */' in result["rewritten"] and '"名字"' in result["rewritten"]

def test_state_initializers_normalize_declaration_descriptions_only():
    source="pragma solidity ^0.5.0; contract C { address owner=msg.sender; address other=owner; function f() public { other=msg.sender; } }"
    base=graph_for(source)
    archive,audit=build(base,{FILE:source},{},["L1","L2","L3"],Encoder())
    out=check_file(base,archive,audit,source,FILE,anonymize(source),None,Encoder())
    assert out["passed"]
