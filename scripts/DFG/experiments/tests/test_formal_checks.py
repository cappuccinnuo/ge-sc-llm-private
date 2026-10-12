from argparse import Namespace
import copy
import math
import pytest
import torch
from scripts.DFG.experiments.formal_checks import history_check, prediction_check, paired_errors, metric_summary, METRICS
from scripts.DFG.experiments.common import metrics
from scripts.DFG.experiments.paper_run import effective_config
from scripts.DFG.experiments.checkpoint import StopMonitor


def history_fixture(losses):
    config = effective_config("contract", Namespace(mode="full",seed=1,epochs=50,smoke_epochs=3,device="cpu",threads=1))
    p = torch.nn.Parameter(torch.zeros(1))
    opt = torch.optim.Adam([p], lr=config["initial_lr"], weight_decay=config["weight_decay"])
    sched = torch.optim.lr_scheduler.OneCycleLR(opt,max_lr=config["max_lr"],total_steps=50,
                div_factor=config["div_factor"],final_div_factor=1,cycle_momentum=True)
    stop = StopMonitor(7,0.001)
    rows = []
    for i,loss in enumerate(losses):
        best, stopped = stop.step(loss)
        if best:
            best_epoch = i
        rows.append(dict(epoch=i,lr=opt.param_groups[0]["lr"],adam_beta1=opt.param_groups[0]["betas"][0],
                         train_loss=0.3,cv_validation_loss=loss,saved_best=best,patience_counter=stop.counter))
        opt.step()
        sched.step()
    result = dict(best_epoch=best_epoch,last_epoch=len(rows)-1,best_cv_validation_loss=min(losses),history_rows=len(rows))
    return rows,result,config


@pytest.mark.parametrize("losses,reason", [([1.0]*8,"patience"),([1-i*.01 for i in range(50)],"epoch_cap")])
def test_full_history_schedule_best_and_stop(losses,reason):
    assert history_check(*history_fixture(losses))["stop_reason"] == reason


@pytest.mark.parametrize("case", ["smoke","lr","best","nan","late","epoch"])
def test_reject_truncated_or_corrupt_training(case):
    rows,result,config = history_fixture([1.0]*8)
    if case == "smoke":
        rows,result,config = history_fixture([1.0,.9,.8])
    elif case == "lr": rows[1]["lr"] *= 2
    elif case == "best": result["best_epoch"] = 7
    elif case == "nan": rows[2]["cv_validation_loss"] = float("nan")
    elif case == "late": rows,result,config = history_fixture([1.0]*9)
    else: rows[1]["epoch"] = 0
    with pytest.raises(ValueError):
        history_check(rows,result,config)


def prediction_fixture():
    rows = [dict(file="a.sol",original_graph_node_id=i,target=y,score_role="cv_validation",
                 best=x,last=x,best_positive_probability=.9 if x else .1,
                 last_positive_probability=.9 if x else .1) for i,(y,x) in enumerate([(1,1),(0,1)])]
    score = metrics([1,0],[1,1])
    return rows,dict(best=score,last=score)


def test_prediction_metrics_and_paired_error_transitions():
    rows,scores = prediction_fixture()
    prediction_check(rows,scores,["a.sol"],"node")
    right=copy.deepcopy(rows)
    right[1]["best"] = 0
    report=paired_errors(rows,right,"best")
    assert report["counts"] == dict(both_correct=1,e0_wrong_e1_correct=1,e0_correct_e1_wrong=0,both_wrong=0)
    assert report["changed"][0]["original_graph_node_id"] == 1
    right[1]["target"] = 1
    with pytest.raises(ValueError,match="truth"):
        paired_errors(rows,right,"best")


@pytest.mark.parametrize("change", ["duplicate","role","metric","files"])
def test_prediction_rejects_invalid_population(change):
    rows,scores = prediction_fixture()
    if change=="duplicate": rows.append(rows[0])
    elif change=="role": rows[0]["score_role"]="outer_test"
    elif change=="metric": scores["best"]=dict(scores["best"],buggy_f1=99)
    else: rows[0]["file"]="b.sol"
    with pytest.raises(ValueError):
        prediction_check(rows,scores,["a.sol"],"node")


def summary_fixture():
    return [dict(fold=f,variant=v,checkpoint=ck,**{m:80+f+(2 if v=="E1" else 0) for m in METRICS})
            for f in range(5) for ck in ("best","last") for v in ("E0","E1")]


def test_summary_fold_mean_std_and_paired_delta():
    out=metric_summary(summary_fixture(),5)
    assert out["score_role"]=="cv_validation"
    assert out["metrics"]["best"]["E0"]["buggy_f1"]["mean"]==82
    assert math.isclose(out["metrics"]["best"]["E0"]["buggy_f1"]["sample_std"],math.sqrt(2.5))
    assert out["metrics"]["best"]["E1-E0"]["buggy_f1"]["mean"]==2
    assert out["metrics"]["last"]["E1-E0"]["buggy_f1"]["sample_std"]==0


@pytest.mark.parametrize("change", ["missing","duplicate","fold"])
def test_summary_never_drops_or_duplicates_a_fold(change):
    rows=summary_fixture()
    if change=="missing": rows=rows[:-1]
    elif change=="duplicate": rows[-1]=rows[0]
    else: rows[-1]["fold"]=6
    with pytest.raises(ValueError):
        metric_summary(rows,5)
