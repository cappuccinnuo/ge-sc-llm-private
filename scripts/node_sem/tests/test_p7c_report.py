import pytest
from scripts.node_sem.llm_full import write,reference,read
from scripts.node_sem.p7c_report import collect
from scripts.node_sem.p7c_pipeline import alive


def fixture(base):
    d=base/"diagnostics";d.mkdir()
    plan=dict(tasks={"x_node":dict(folds=[0,1])})
    write(d/"plan.json",plan);write(d/"plan.seal.json",dict(plan=reference(d/"plan.json")))
    write(d/"completed.json",dict(passed=True,folds=2,plan=reference(d/"plan.json")))
    for fold in (0,1):
        f=d/"folds"/("x_node__"+str(fold));f.mkdir(parents=True)
        ridge=dict(status="ok",outer_mean_cosine=.8,baseline_mean_cosine=.6,
            ridge_on_baseline_population=.79,baseline_unseen_rows=1)
        signal=[dict(source=name,status="ok" if fold==0 else "not_estimable_inner_train_empty",
            **(dict(buggy_f1=v,auc=.7) if fold==0 else {})) for name,v in (("static",.4),("static_teacher",.5))]
        result=dict(task_id="x_node",fold=fold,plan=reference(d/"plan.json"),ridge=ridge,signal=signal)
        write(f/"result.json",result);write(f/"receipt.json",dict(passed=True,result=reference(f/"result.json")))
    return d


def test_paired_and_not_estimable_reporting(tmp_path):
    fixture(tmp_path)
    r=collect(tmp_path)["x_node"]["summary"]
    assert r["ridge_estimable"]==2
    assert r["signal"]["static_teacher"]["f1_estimable"]==1
    assert r["paired_f1_delta"]==pytest.approx(.1)
    assert r["paired_signal"][1]["buggy_f1_delta"] is None


def test_incomplete_controller_rejected(tmp_path):
    d=fixture(tmp_path)
    (d/"completed.json").write_text('{"passed": false}')
    with pytest.raises(ValueError,match="incomplete"):collect(tmp_path)


def test_wrong_fold_rejected_even_if_result_hash_is_updated(tmp_path):
    d=fixture(tmp_path);f=d/"folds/x_node__0";p=f/"result.json"
    result=read(p);result["fold"]=9;p.unlink();write(p,result)
    (f/"receipt.json").unlink();write(f/"receipt.json",dict(passed=True,result=reference(p)))
    with pytest.raises(ValueError,match="identity"):collect(tmp_path)


def test_mutated_result_rejected(tmp_path):
    d=fixture(tmp_path);p=d/"folds/x_node__0/result.json"
    p.write_bytes(p.read_bytes()+b" ")
    with pytest.raises(ValueError,match="SHA"):collect(tmp_path)


def test_dead_process_is_not_treated_as_success():
    assert not alive(2147483647)
