"""8G probe adaptation preserves old estimators and verifies exported identities."""
import copy
import pytest
import networkx as nx
from scripts.DFG.frontend import walk
from scripts.DFG.dfg_v2.benchmark_v2.spelling_probes import rank_auc, role_results, verify_p2, node_rows
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import anonymize
from scripts.DFG.dfg_v2.benchmark_v2.leakage_probes import p2_all, p3_samples, PROTOCOL
from scripts.DFG.dfg_v2.benchmark_v2.prepare import write, ref
from scripts.DFG.dfg_v2.tests.test_l1 import graph_for, FILE
from scripts.DFG.dfg_v2.projection_view import ProjectionView


def test_independent_auc_handles_ties_and_single_class():
    assert rank_auc([dict(probability=.5,target=0),dict(probability=.5,target=1)]) == .5
    assert rank_auc([dict(probability=.1,target=0),dict(probability=.9,target=1)]) == 1
    assert rank_auc([dict(probability=.9,target=0),dict(probability=.1,target=1)]) == 0
    assert rank_auc([dict(probability=.9,target=1)]) is None


def test_role_auc_is_subset_of_pooled_predictions_and_reports_undefined():
    rows=[dict(role="state",probability=.1,target=0),dict(role="state",probability=.9,target=1),
          dict(role="event",probability=.5,target=0)]
    out=role_results(rows)
    assert out["state"]["auc"]==1 and out["state"]["samples"]==2
    assert out["event"]["auc"] is None and not out["event"]["defined"]


def p2_fixture():
    rows=[dict(file=f,source_sha256=f,original_graph_node_id=i,solidifi=True,orig=i%2,C1=i%2,
               own_code="v1;",function_code=None)
          for f in ("a","b","c","d") for i in range(2)]
    folds=[dict(fold=0,inner_train_files=["a"],inner_val_files=["b"],outer_test_files=["c","d"]),
           dict(fold=1,inner_train_files=["c"],inner_val_files=["d"],outer_test_files=["a","b"])]
    return rows,folds,p2_all(rows,folds,"orig")


def test_p2_export_recount_uses_identity_and_original_gate():
    rows,folds,score=p2_fixture()
    assert verify_p2(score,rows,folds,"orig")["unique_predictions"]==8
    assert PROTOCOL["P2"]["threshold_pp"]==5 and PROTOCOL["P3"]["threshold_auc"]==.60


@pytest.mark.parametrize("kind",["label","identity","fold","score"])
def test_p2_tampering_rejected(kind):
    rows,folds,score=p2_fixture()
    pred=score["folds"][0]["predictions"][0]
    if kind=="label":pred["orig"]=1-pred["orig"]
    if kind=="identity":pred["original_graph_node_id"]=999
    if kind=="fold":pred["fold"]=1
    if kind=="score":score["pooled"]["buggy_f1"]+=1
    with pytest.raises(ValueError):
        verify_p2(score,rows,folds,"orig")


def test_p3_reuses_full_name_mappings_on_both_cohorts():
    inventory={"cat_node/a":dict(source_sha256="a",declarations=[
        dict(word="ordinary",role="local",injected=False),
        dict(word="injected",role="local",injected=True)])}
    samples=p3_samples(inventory,{"cat_node/a":{"ordinary":"v3","injected":"v1"}},{"cat_node/a":"group"})
    assert {r["name"] for r in samples}=={"v3","v1"}
    assert len(samples)==2 and {r["target"] for r in samples}=={0,1}


def test_node_and_exact_function_code_view_use_ast_mapping(tmp_path):
    source="pragma solidity ^0.5.0; contract C { uint stored; function f(uint amount) public { stored=amount; require(msg.sender!=tx.origin); } }"
    base=graph_for(source)
    path=tmp_path/"g.gpickle";nx.write_gpickle(base,str(path))
    src=tmp_path/"a.sol";src.write_text(source)
    result=anonymize(source);del result["rewritten"]
    result_path=tmp_path/"a.json";write(result_path,result)
    reference=ref(src)
    tid="toy_node"
    sources={"toy/"+FILE:dict(source=reference,result=ref(result_path))}
    task=dict(record=dict(original_graph=ref(path),category="toy",sources={FILE:reference}))
    view=ProjectionView(source,FILE)
    fn=next(n for n in walk(view.compat_tree.root_node) if n.type=="function_definition")
    span=[fn.start_byte,fn.end_byte]
    scopes=[dict(file=FILE,original_graph_node_id=n,source_sha256=reference["sha256"],
                 function_compat_span=span) for n in base]
    labels=[dict(file=FILE,original_graph_node_id=n,source_sha256=reference["sha256"],
                 orig=int(a.get("node_info_vulnerabilities") is not None),C1=0) for n,a in base.nodes(data=True)]
    inventory={tid+"/"+FILE:dict(source_sha256=reference["sha256"],solidifi=False)}
    rows,originals=node_rows(tid,task,sources,inventory,scopes,labels)
    assert len(rows)==len(base)
    assert all("amount" not in r["function_code"] and "msg.sender" in r["function_code"] for r in rows)
    assert all("amount" in r["function_code"] for r in originals)
    assert all(not r["solidifi"] for r in rows)
    assert any(r["own_code"]!=o["own_code"] for r,o in zip(rows,originals))
