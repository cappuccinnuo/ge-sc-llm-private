"""Read-only summary checks; no training, feature generation or model forward."""
import copy
import math
import pytest
from scripts.node_sem.summary import Sources, reference, same, merge_records, node_join, SELECTED, collect


def metric():
    return dict(task_id="toy_node",task_kind="node",profile="G3R/S4",fold=0,seed=1,
        checkpoint="best",metrics={k:50.0 for k in ("buggy_f1","macro_f1","precision","recall")})


def test_hash_missing_and_tampering(tmp_path):
    p=tmp_path/"input.json";p.write_text("{}")
    ref=reference(p)
    assert Sources().check(ref)==p
    p.write_text('{"changed":1}')
    with pytest.raises(ValueError,match="SHA"): Sources().check(ref)
    p.unlink()
    with pytest.raises(ValueError,match="Missing"): Sources().check(ref)


def test_binary64_and_duplicate_history():
    r=metric()
    rows,origins=merge_records([("NA",[r]),("NC2",[copy.deepcopy(r)])])
    assert len(rows)==1 and len(next(iter(origins.values())))==2
    altered=copy.deepcopy(r);altered["metrics"]["buggy_f1"]=50.00000000000001
    with pytest.raises(ValueError,match="Historical metric"):merge_records([("NA",[r]),("NC2",[altered])])
    assert not same(0.0,-0.0)


def test_duplicate_within_batch_rejected():
    with pytest.raises(ValueError,match="Duplicate"):merge_records([("NA",[metric(),metric()])])


def test_identity_not_row_order():
    row=dict(file="same.sol",source_sha256="sha1",source_id="id1",original_graph_node_id=9,
        target=1,cohort="nonSolidiFI",node_type="expression_statement",fold=1,
        best=0,last=1,best_positive_probability=.2,last_positive_probability=.8)
    tables={n:{("sha1","same.sol",9):copy.deepcopy(row)} for n in SELECTED}
    out=node_join(tables)
    assert out[0]["all_missed"] and not out[1]["all_missed"]
    tables["S5"]={("sha2","same.sol",9):copy.deepcopy(row)}
    with pytest.raises(ValueError,match="identities"): node_join(tables)


def test_target_disagreement_rejected():
    row=dict(target=1)
    tables={n:{("sha","a.sol",7):copy.deepcopy(row)} for n in SELECTED}
    tables["S5"][("sha","a.sol",7)]["target"]=0
    with pytest.raises(ValueError,match="targets"):node_join(tables)


def test_output_exclusive(tmp_path):
    with pytest.raises(FileExistsError):collect(tmp_path)


def test_summary_has_no_inference_or_training_calls():
    import ast
    from pathlib import Path
    import scripts.node_sem.summary as module
    tree=ast.parse(Path(module.__file__).read_text())
    banned={"fit","forward","holm_adjust","paired_comparison","torch_load","encode"}
    calls=[n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
    assert not set(calls)&banned

def test_original_auxiliary_record_optional_counts():
    from scripts.DFG.dfg_v2.experiment.stats import validate_records
    a=metric();b=copy.deepcopy(a);b["metrics"].update(n=3,tn_fp_fn_tp=[1,0,1,1])
    assert same(validate_records([a]),validate_records([b]))

def test_message_reverses_are_not_forward_semantics():
    from scripts.node_sem.summary_edges import path_evidence
    e={"nodes":[{"id":1,"node_type":"statement"},{"id":2,"node_type":"statement"},{"id":3,"node_type":"statement"}],
       "edges":[{"source":1,"target":2,"key":0,"attributes":{"edge_type":"DATA_DEF_USE"}}]}
    reverse=path_evidence(e,2,1)
    assert reverse["raw_forward_shortest_path"] is None
    assert reverse["message_direct_relations"]==["REV_DATA_DEF_USE"]
    assert reverse["within_two_message_layers"]
    assert path_evidence(e,1,3)["G3R_message_shortest_path"] is None


def test_frozen_auxiliary_identity_is_distinct():
    from scripts.node_sem.carrier import row_key
    assert row_key(4,{"node_type":"env_source","code":"msg.sender","source_file":"a.sol"})=="env:a.sol:msg.sender"


def test_actual_summary_sources_match():
    from pathlib import Path
    from scripts.node_sem.summary import ART, read
    report=ART/"summary_NS_v1/collection_attempt3/collect_complete.json"
    if not report.exists():pytest.skip("Local sealed summary unavailable")
    value=read(report)
    assert value["fits"]==450 and value["metric_rows"]==900
    assert value["binary64_aggregates_exact"]
    assert value["prior_positive_tables"]=={"NC1":104,"NC2":312}
    assert value["persistent_best"]=={"reentrancy_node":6,"access_control_node":15}

def test_node_fold_and_type_alignment_rejected():
    row=dict(file="a.sol",source_sha256="sha",source_id="id",original_graph_node_id=1,
        target=1,cohort="nonSolidiFI",node_type="statement",fold=0,
        best=0,last=0,best_positive_probability=.1,last_positive_probability=.2)
    tables={n:{("sha","a.sol",1):copy.deepcopy(row)} for n in SELECTED}
    tables["S6"][("sha","a.sol",1)]["fold"]=1
    with pytest.raises(ValueError,match="fold"):node_join(tables)
    tables["S6"][("sha","a.sol",1)]["fold"]=0
    tables["S6"][("sha","a.sol",1)]["node_type"]="function_definition"
    with pytest.raises(ValueError,match="node_type"):node_join(tables)
