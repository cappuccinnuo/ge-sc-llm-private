"""Prompt 7b diagnostic acceptance helpers; no models or GPU execution."""
import copy

import pytest
import torch

from scripts.DFG.dfg_v2.experiment.projection_validation import (
    ATOL, RTOL, CPU_CASES, compare_histories, gradient_difference,
    summarize_cpu, compare_gpu,
)


def _history(validation="inner_val_loss"):
    return [dict(epoch=i, train_loss=0.8-i*0.1, **{validation:0.7-i*0.1})
            for i in range(3)]


def test_gradient_zero_and_none_have_explicit_meanings():
    assert gradient_difference(None, None)["passed"]
    assert not gradient_difference(None, torch.zeros(2))["passed"]
    assert not gradient_difference(torch.zeros(2), None)["passed"]
    result=gradient_difference(torch.zeros(2),torch.zeros(2))
    assert result["passed"]
    assert result["tensor_scale"] == 0
    assert result["maximum_absolute_difference"] == 0
    assert result["elementwise_relative_difference"] == 0
    assert result["tolerance"] == ATOL


def test_gradient_reports_raw_near_zero_error_without_hiding_it():
    result=gradient_difference(torch.tensor([1e-10],dtype=torch.float64),
                               torch.tensor([-1e-10],dtype=torch.float64))
    assert result["passed"]
    assert not result["pure_relative_passed"]
    assert result["elementwise_relative_difference"] == pytest.approx(2.0)
    assert result["tensor_relative_difference"] == pytest.approx(2.0)
    assert result["maximum_absolute_difference"] == pytest.approx(2e-10)


def test_gradient_tensor_scale_formula_and_actual_bad_gradient_rejection():
    a=torch.tensor([1.0,1e-10],dtype=torch.float64)
    b=torch.tensor([1.0,-1e-10],dtype=torch.float64)
    result=gradient_difference(a,b)
    assert result["passed"]
    assert result["elementwise_relative_difference"] == pytest.approx(2.0)
    assert result["tolerance"] == pytest.approx(ATOL+RTOL)
    assert not gradient_difference(a,a+0.1)["passed"]


@pytest.mark.parametrize("bad",[float("nan"),float("inf"),-float("inf")])
@pytest.mark.parametrize("which",["old","new"])
def test_gradient_nonfinite_is_rejected(bad,which):
    a=torch.ones(2)
    b=torch.ones(2)
    (a if which=="old" else b)[0]=bad
    result=gradient_difference(a,b)
    assert not result["passed"]
    assert result["nonfinite"]


@pytest.mark.parametrize("other",[torch.zeros(3),torch.zeros(2,dtype=torch.float64)])
def test_gradient_shape_or_dtype_mismatch_rejected(other):
    with pytest.raises(ValueError):
        gradient_difference(torch.zeros(2),other)


def test_history_exact_and_requested_tolerance():
    a=_history()
    b=copy.deepcopy(a)
    assert compare_histories(a,b,1e-6)["passed"]
    b[1]["train_loss"]+=5e-7
    result=compare_histories(a,b,1e-6)
    assert result["passed"]
    assert result["maximum_absolute_loss_difference"] == pytest.approx(5e-7)
    b[1]["train_loss"]+=0.01
    assert not compare_histories(a,b,1e-6)["passed"]


def test_history_column_mapping_for_archived_cv_validation():
    assert compare_histories(_history("cv_validation_loss"),_history(),1e-4,
                             "cv_validation_loss")["passed"]


@pytest.mark.parametrize("side",["old","new"])
@pytest.mark.parametrize("column",["train_loss","inner_val_loss"])
@pytest.mark.parametrize("bad",[float("nan"),float("inf"),-float("inf")])
def test_history_rejects_nonfinite_in_either_loss_even_if_other_loss_matches(side,column,bad):
    a=_history();b=_history()
    (a if side=="old" else b)[1][column]=bad
    with pytest.raises((ValueError,AssertionError)):
        compare_histories(a,b,1e-6)


@pytest.mark.parametrize("epochs",[[0,0,0],[1,2,3],[0,2,1]])
def test_history_rejects_noncanonical_matching_epoch_lists(epochs):
    a=_history();b=_history()
    for i,epoch in enumerate(epochs):
        a[i]["epoch"]=b[i]["epoch"]=epoch
    with pytest.raises((ValueError,AssertionError)):
        compare_histories(a,b,1e-6)


@pytest.mark.parametrize("n",[0,1,2,4])
def test_history_requires_three_epochs(n):
    a=(_history()+[_history()[0]])[:n]
    with pytest.raises((ValueError,AssertionError)):
        compare_histories(a,a,1e-6)


@pytest.mark.parametrize("tolerance",[-1,float("nan"),float("inf")])
def test_history_rejects_invalid_tolerance(tolerance):
    with pytest.raises((ValueError,AssertionError)):
        compare_histories(_history(),_history(),tolerance)


def _write_json(path, value):
    import json
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding="utf-8")


def _accepted_cpu_reports(root):
    for task,profile,reducer in CPU_CASES:
        report=dict(task_id=task,profile=profile,reducer=reducer,status="accepted",
            logits_bitwise_equal=True,layer_outputs_bitwise_equal=[{"n":True},{"n":True}],
            gradients={"p":{"passed":True}},
            trajectory=dict(passed=True,maximum_absolute_loss_difference=0.0,tolerance=1e-6))
        _write_json(root/(task+"_"+profile+"_"+reducer)/"equivalence.json",report)


@pytest.mark.parametrize("corruption",["trajectory","logits","layer","gradient"])
def test_cpu_summary_does_not_trust_status_over_failed_evidence(tmp_path,corruption):
    import json
    _accepted_cpu_reports(tmp_path)
    task,profile,reducer=CPU_CASES[0]
    path=tmp_path/(task+"_"+profile+"_"+reducer)/"equivalence.json"
    report=json.loads(path.read_text())
    if corruption=="trajectory": report["trajectory"]["passed"]=False
    elif corruption=="logits": report["logits_bitwise_equal"]=False
    elif corruption=="layer": report["layer_outputs_bitwise_equal"][0]["n"]=False
    else: report["gradients"]["p"]["passed"]=False
    _write_json(path,report)
    with pytest.raises(ValueError):
        summarize_cpu(tmp_path)
    assert not (tmp_path/"acceptance.json").exists()


@pytest.mark.parametrize("wrong_impl",["original","wrong"])
def test_gpu_summary_rejects_mislabeled_implementation(tmp_path,wrong_impl):
    import json
    for impl in ("original","shared_projection"):
        root=tmp_path/impl
        report=dict(status="accepted",layer_impl=impl,reference={"same":"history"},
            resources={},history_comparison={"passed":True})
        if impl=="shared_projection": report["layer_impl"]=wrong_impl
        _write_json(root/"diagnostic.json",report)
        history=root/"fit"/"history.jsonl"
        history.parent.mkdir(parents=True,exist_ok=True)
        history.write_text("".join(json.dumps(row)+"\n" for row in _history()),encoding="utf-8")
    with pytest.raises(ValueError):
        compare_gpu(tmp_path)
    assert not (tmp_path/"acceptance.json").exists()
