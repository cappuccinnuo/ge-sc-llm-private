"""Focused final-report guards; CPU only, no formal fits/checkpoint changes."""
import ast
import copy
import json
from pathlib import Path
import pytest
import torch
from scripts.node_sem import nb_diagnostics as d, nb_reporting as r, batch_nb as nb
from scripts.node_sem.nb_finalize import launch_command
from scripts.node_sem.reporting import scored as old_scored
from scripts.DFG.dfg_v2.experiment.stats import METRICS, validate_records


def row(i,target=1,pred=1):
    return dict(file="f.sol",original_graph_node_id=i,target=target,source_sha256="abc",
        source_id="file-id",cohort="nonSolidiFI",best=pred,last=pred,
        best_positive_probability=0.8 if pred else 0.2,last_positive_probability=0.8 if pred else 0.2)


def test_pair_alignment_uses_identity():
    left=[row(1),row(2)];right=list(reversed(copy.deepcopy(left)))
    assert list(r.paired_rows(left,right,"node"))==[(left[0],left[0]),(left[1],left[1])]


@pytest.mark.parametrize("field,value",[
    ("target",0),("source_sha256","wrong"),("source_id","wrong"),("cohort","SolidiFI"),
    ("file","other.sol"),("original_graph_node_id",88)])
def test_changed_identity_rejected(field,value):
    other=row(1);other[field]=value
    with pytest.raises(ValueError):list(r.paired_rows([row(1)],[other],"node"))


@pytest.mark.parametrize("mode",["duplicate","missing"])
def test_missing_duplicate_predictions(mode):
    with pytest.raises(ValueError):
        list(r.paired_rows([row(1),row(2)],[row(1),row(1)] if mode=="duplicate" else [row(1)],"node"))


@pytest.mark.parametrize("value",[float("nan"),float("inf"),-0.01,1.01])
def test_invalid_probability(value):
    a=row(1);a["best_positive_probability"]=value
    with pytest.raises(ValueError):list(r.paired_rows([a],[row(1)],"node"))


def metric_records():
    return [dict(task_id="task",task_kind="node",profile=profile,fold=f,seed=1,
        checkpoint="best",metrics={m:score for m in METRICS})
        for profile,scores in [("left",[81.,80.,79.]),("right",[80.,80.,80.])]
        for f,score in enumerate(scores)]


def test_descriptive_pairing_not_row_order():
    values=list(reversed(metric_records()))
    result=r.paired_descriptive(values,"task","left","right","best")
    assert len(result)==4
    for x in result:
        assert x["mean_delta_pp"]==0 and x["sample_sd_delta_pp"]==1
        assert (x["improved"],x["tied"],x["declined"])==(1,1,1)
        assert x["p_value"] is None and x["inferential"] is False
        assert [f["fold"] for f in x["folds"]]==[0,1,2]


@pytest.mark.parametrize("mode",["missing","duplicate","wrong_seed"])
def test_paired_folds_reject(mode):
    values=metric_records()
    if mode=="missing":values.pop()
    elif mode=="duplicate":values.append(copy.deepcopy(values[0]))
    else:values[-1]["seed"]=2
    with pytest.raises(ValueError):r.paired_descriptive(values,"task","left","right","best")


def test_comparison_provenance_once():
    values=r.comparison_specs(nb.statistics_spec())
    assert len(values)==10
    one=[v for v in values if (v["left"],v["right"])==("G3R/S3","G3R/S2")]
    assert len(one)==1 and one[0]["stratification_provenance"]=="r19_posthoc_descriptive"


def test_duplicate_comparison_rejected():
    policy=nb.statistics_spec();policy["posthoc_comparisons"].append(["S3","S2"])
    with pytest.raises(ValueError):r.comparison_specs(policy)


def test_score_reader_unchanged():
    values=[row(1),row(2,1,0),row(3,0,1),row(4,0,0)]
    assert r.score_or_empty(values,"best")==old_scored(values,"best")
    assert r.score_or_empty([],"best")["buggy_f1"] is None


def test_full_720_identity_matrix():
    jobs=nb.matrix()+[dict(task_id=t,granularity=t.rsplit("_",1)[-1],fold=f,seed=1,
        name=n,profile=g) for t,k in nb.TASK_FOLDS for f in range(k)
        for n in ("S0o","S1o","S2","S4") for g in ("G0","G3R")]
    values=[dict(task_id=j["task_id"],task_kind=j["granularity"],profile=j["profile"]+"/"+j["name"],
        fold=j["fold"],seed=1,checkpoint=ck,metrics={m:80. for m in METRICS})
        for j in jobs for ck in ("best","last")]
    keys={(v["task_id"],v["profile"],v["fold"],v["seed"],v["checkpoint"]) for v in values}
    assert len(validate_records(values,keys))==720
    with pytest.raises(ValueError):validate_records(values[:-1],keys)


def test_gate_conditional_rows_and_missing_modalities():
    p=torch.tensor([[1.,1.,0.],[1.,0.,0.],[0.,0.,0.]])
    w=torch.tensor([[.25,.75,0.],[1.,0.,0.],[0.,0.,0.]])
    before=w.clone();s=d.gate_summary(w,p,["code","ctx","static"],"expr")
    assert s[0]["mean"]==.625 and s[0]["available_rows"]==2 and s[0]["fraction_ge_0_9"]==.5
    assert s[1]["mean"]==.75 and s[1]["available_rows"]==1
    assert s[2]["mean"] is None and s[2]["available_rows"]==0
    assert all(v["all_missing_rows"]==1 for v in s)
    assert torch.equal(before,w)


@pytest.mark.parametrize("weights,presence",[
    ([[.1,.9]],[[0.,1.]]),([[.2,.2]],[[1.,1.]]),
    ([[float("nan"),1.]],[[1.,1.]]),([[-.1,1.1]],[[1.,1.]]),
    ([[0.,1.]],[[.5,1.]])])
def test_invalid_gate_rejected(weights,presence):
    with pytest.raises(ValueError):d.gate_summary(torch.tensor(weights),torch.tensor(presence),["code","ctx"],"expr")


def test_zero_node_type_gate():
    values=d.gate_summary(torch.empty(0,2),torch.empty(0,2),["code","ctx"],"empty")
    assert all(v["available_rows"]==0 and v["mean"] is None for v in values)


@pytest.mark.parametrize("count",[0,119,121])
def test_incomplete_formal_matrix_rejects_before_gpu(tmp_path,count):
    (tmp_path/"complete.json").write_text(json.dumps(dict(passed=True,formal_fits=count)))
    with pytest.raises(ValueError):d.accepted_entries(tmp_path,dict(jobs=[]))


def test_frozen_attention_observer_ast_unchanged():
    root=Path(d.__file__).parent
    def body(path):
        tree=ast.parse(path.read_text())
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=="observe")
        return ast.dump(node,include_attributes=False)
    assert body(root/"na_attention.py")==body(root/"nb_diagnostics.py")


def test_analysis_runner_has_no_training_command():
    cmd=launch_command("scripts.node_sem.nb_diagnostics","/some/root","task")
    assert cmd[-2:]==["--only","task"] and "batch_nb_worker" not in " ".join(cmd)


def test_non_gate_config_has_no_fabricated_gate():
    assert d.collect_gates(None,dict(name="S3"))==[]



def test_historical_export_audit_discloses_missing_weights(tmp_path):
    from scripts.node_sem.nb_finalize import verify_historical_exports
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
    paths=[tmp_path/n for n in ("best.pt","last.pt","prediction.json")]
    for p in paths:p.write_text("sealed")
    receipt=dict(artifacts=[ref(p) for p in paths])
    assert verify_historical_exports(receipt)["present_checkpoints"]==2
    paths[0].unlink();paths[1].unlink()
    result=verify_historical_exports(receipt)
    assert len(result["missing_checkpoints"])==2 and result["present_checkpoints"]==0
    paths[2].write_text("tampered")
    with pytest.raises((ValueError,AssertionError)):
        verify_historical_exports(receipt)


def test_historical_export_audit_rejects_missing_export_and_changed_weight(tmp_path):
    from scripts.node_sem.nb_finalize import verify_historical_exports
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
    paths=[tmp_path/n for n in ("best.pt","last.pt","prediction.json")]
    for p in paths:p.write_text("sealed")
    receipt=dict(artifacts=[ref(p) for p in paths])
    paths[0].write_text("changed")
    with pytest.raises((ValueError,AssertionError)):
        verify_historical_exports(receipt)
    paths[0].write_text("sealed");paths[2].unlink()
    with pytest.raises(FileNotFoundError):
        verify_historical_exports(receipt)
