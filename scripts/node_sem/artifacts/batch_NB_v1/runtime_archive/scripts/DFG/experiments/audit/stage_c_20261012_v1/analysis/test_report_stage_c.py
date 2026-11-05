"""Numerical/reporting tests only: synthetic JSON, no models or GPU."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location("stage_c_report", Path(__file__).with_name("report_stage_c.py"))
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    r.write_json(path, value)


def row(file, target, best, last=None, node=None):
    out = {"file":file, "target":target, "best":best, "last":best if last is None else last,
           "score_role":r.ROLE}
    if node is not None:
        out.update(original_graph_node_id=node, node_type="expression_statement")
    return out


def synthetic_rows(folds=3):
    result = []
    for fold in range(folds):
        for ck in ("best","last"):
            for variant in ("E0","E1"):
                score = 50 + fold * 10 + ([2,0,-2][fold] if variant == "E1" else 0)
                result.append(dict(fold=fold,checkpoint=ck,variant=variant,
                                   **{m:float(score) for m in r.METRICS}))
    return result


def reseal(run, state, job):
    entry = state["jobs"][job]
    receipt_path = run / entry["receipt"]
    receipt = r.read_json(receipt_path)
    receipt["artifacts"] = r.tree_hashes(run / entry["attempt"])
    dump(receipt_path,receipt)
    entry["receipt_sha256"] = r.sha256(receipt_path)
    dump(run/"state.json",state)


def fixture_run(tmp_path, complete_folds=5):
    run = tmp_path/"run"
    run.mkdir()
    jobs = []
    state = {"stage_b":"passed","stage_c":"running","jobs":{}}
    for cohort,task,k in r.TASKS:
        splits_path = tmp_path/(cohort+"_"+task+"_splits.json")
        splits = {"folds":[{"fold":f,"val_files":["file_{}_a.sol".format(f),"file_{}_b.sol".format(f)]}
                           for f in range(k)]}
        dump(splits_path,splits)
        for f in range(k):
            job = dict(id=cohort+"_"+task+"_fold"+str(f),cohort=cohort,task=task,fold=f,
                       splits=str(splits_path))
            jobs.append(job)
            if cohort != "reentrancy_author" or task != "contract" or f >= complete_folds:
                continue
            attempt = run/"jobs"/job["id"]/"attempt_001"
            fold_dir = attempt/("fold_"+str(f))
            predictions = {"E0":[row(splits["folds"][f]["val_files"][0],0,0),
                                  row(splits["folds"][f]["val_files"][1],1,0,1)],
                           "E1":[row(splits["folds"][f]["val_files"][0],0,0),
                                  row(splits["folds"][f]["val_files"][1],1,1,0)]}
            variants, acceptance = {}, {}
            for variant in ("E0","E1"):
                scores = {ck:r.metrics_from_predictions(predictions[variant],ck) for ck in ("best","last")}
                vr = dict(status="complete",score_role=r.ROLE,cv_validation=scores,
                          checkpoint_roundtrip_exact={"best":True,"last":True})
                variants[variant]=vr
                parameter_count=100 if variant=="E0" else 110
                timing=10.0 if variant=="E0" else 12.0
                acceptance[variant] = dict(best_epoch=0,last_epoch=1,epochs=2,stop_reason="fixture",
                     parameter_count=parameter_count,fit_eval_checkpoint_wall_seconds=timing,
                     ddg_train_edges=0 if variant=="E0" else 3,
                     ddg_gradient_l1_sum=0.0 if variant=="E0" else 0.5,
                     ddg_message_update_l1=0.0 if variant=="E0" else 0.2,
                     validation_only_relations=[] if variant=="E0" else [["x","DATA_DEF_USE","y"]])
                dest=fold_dir/variant
                dump(dest/"result.json",vr)
                dump(dest/"cv_validation_predictions.json",predictions[variant])
                dump(dest/"telemetry.json",dict(parameters={"total":parameter_count},
                     fit_eval_checkpoint_wall_seconds=timing,simultaneously_loaded_model_count=2,
                     memory_after=dict(cuda=True,device="cuda:0",peak_allocated_bytes=2**20,
                                       peak_reserved_bytes=2*2**20)))
                (dest/"best.pt").write_bytes(b"synthetic checkpoint identity only")
            deltas = {ck:{m:variants["E1"]["cv_validation"][ck][m]-variants["E0"]["cv_validation"][ck][m]
                          for m in r.METRICS} for ck in ("best","last")}
            fold = dict(fold=f,status="complete",variants=variants,paired_cv_validation_delta=deltas)
            result = dict(protocol=r.NAME,protocol_version=r.VERSION,score_role=r.ROLE,mode="full",
                          cohort=cohort,task=task,completed_folds=1,requested_folds=1,folds=[fold])
            dump(attempt/"result.json",result)
            dump(fold_dir/"result.json",fold)
            dump(attempt/"splits.json",splits)
            errors = {}
            for ck in ("best","last"):
                e=r.paired_errors(predictions["E0"],predictions["E1"],ck,task)
                errors[ck]={"counts":e["counts"],"changed":[{key:value for key,value in rr.items()
                                                       if key!="error_change"} for rr in e["changed"]]}
            receipt = dict(acceptance=dict(status="passed",score_role=r.ROLE,job=job["id"],
                                          variants=acceptance,paired_errors=errors),
                           artifacts=r.tree_hashes(attempt))
            receipt_path=attempt.parent/"attempt_001.receipt.json"
            dump(receipt_path,receipt)
            state["jobs"][job["id"]]=dict(status="passed",attempt=str(attempt.relative_to(run)),
                receipt=str(receipt_path.relative_to(run)),receipt_sha256=r.sha256(receipt_path),exit_code=0)
    source=tmp_path/"frozen.txt"
    source.write_text("same",encoding="utf-8")
    plan=dict(format="ddg-formal-gated-v1",protocol=r.NAME,protocol_version=r.VERSION,
              score_role=r.ROLE,mode="full",seed=1,epochs=50,jobs=jobs,
              task_order=[dict(cohort=c,task=t,folds=k) for c,t,k in r.TASKS],
              frozen_files={str(source):r.sha256(source)})
    dump(run/"plan.json",plan)
    dump(run/"plan.seal.json",{"sha256":r.sha256(run/"plan.json")})
    dump(run/"state.json",state)
    return run,plan,state


def test_four_metrics_known_confusion():
    rows=[row("a",0,0),row("b",0,1),row("c",1,0),row("d",1,1)]
    scores=r.metrics_from_predictions(rows,"best")
    assert scores==dict(n=4,positive=2,buggy_f1=50.0,macro_f1=50.0,
                       precision=50.0,recall=50.0,tn_fp_fn_tp=[1,1,1,1])


def test_zero_denominators_and_macro_two_labels():
    scores=r.metrics_from_predictions([row("a",0,0)],"best")
    assert scores["buggy_f1"]==0 and scores["macro_f1"]==50


def test_mean_sample_std_and_paired_direction():
    summary=r.metric_summary(synthetic_rows(),3)
    assert summary["best"]["E0"]["buggy_f1"]["mean"]==60
    assert summary["best"]["E0"]["buggy_f1"]["sample_std"]==10
    delta=summary["best"]["E1-E0"]["buggy_f1"]
    assert delta["mean"]==0 and delta["sample_std"]==2
    assert delta["fold_direction_counts"]==dict(improved=1,tied=1,declined=1)


def test_last_does_not_replace_best():
    rows=synthetic_rows()
    for rr in rows:
        if rr["checkpoint"]=="last" and rr["variant"]=="E1":
            rr["buggy_f1"] += 10
    result=r.metric_summary(rows,3)
    assert result["best"]["E1-E0"]["buggy_f1"]["mean"]==0
    assert result["last"]["E1-E0"]["buggy_f1"]["mean"]==10


@pytest.mark.parametrize("mutation",["missing","duplicate","wrong_fold","nan"])
def test_invalid_summary_rejected(mutation):
    rows=synthetic_rows()
    if mutation=="missing": rows.pop()
    elif mutation=="duplicate": rows[-1]=copy.deepcopy(rows[0])
    elif mutation=="wrong_fold": rows[0]["fold"]=99
    else: rows[0]["buggy_f1"]=float("nan")
    with pytest.raises(ValueError): r.metric_summary(rows,3)


def test_error_changes_include_fp_and_fn():
    left=[row("a",0,1),row("b",1,0),row("c",0,0),row("d",1,1)]
    right=[row("a",0,0),row("b",1,1),row("c",0,1),row("d",1,0)]
    result=r.paired_errors(left,right,"best","contract")
    assert result["error_types"]==dict(corrected_fp=1,corrected_fn=1,introduced_fp=1,introduced_fn=1)
    assert result["counts"]==dict(both_correct=0,e0_wrong_e1_correct=2,e0_correct_e1_wrong=2,both_wrong=0)


def test_node_identity_is_not_deduplicated_by_file():
    rows=[row("same.sol",0,0,node=1),row("same.sol",1,1,node=2)]
    assert r.paired_errors(rows,rows,"best","node")["counts"]["both_correct"]==2
    with pytest.raises(ValueError,match="Duplicate"):
        r.paired_errors(rows,rows,"best","contract")


@pytest.mark.parametrize("kind",["duplicate","truth","role","identities"])
def test_prediction_corruption_rejected(kind):
    a=[row("a",0,0),row("b",1,1)]
    b=copy.deepcopy(a)
    if kind=="duplicate": b.append(b[0])
    elif kind=="truth": b[0]["target"]=1
    elif kind=="role": b[0]["score_role"]="independent_test"
    else: b[0]["file"]="different"
    with pytest.raises(ValueError): r.paired_errors(a,b,"best","contract")


def test_complete_task_and_pending_tasks(tmp_path):
    run,plan,state=fixture_run(tmp_path)
    report=r.build_report(run)
    assert report["complete_tasks"]==1
    task=report["tasks"][0]
    assert task["metrics"]["best"]["E1"]["buggy_f1"]["mean"]==100
    assert task["metrics"]["last"]["E1"]["buggy_f1"]["mean"]==0
    assert task["error_transition_totals"]["best"]["corrected_fn"]==5
    assert task["error_transition_totals"]["last"]["introduced_fn"]==5
    assert task["telemetry_summary"]["E0"]["fit_eval_checkpoint_wall_seconds_total"]==50
    assert task["telemetry_summary"]["E1"]["fit_eval_checkpoint_wall_seconds_total"]==60
    assert len(task["fit_telemetry"])==10  # not 20 best/last rows
    assert all("metrics" not in t for t in report["tasks"][1:])


def test_partial_task_has_no_means(tmp_path):
    run,plan,state=fixture_run(tmp_path,complete_folds=4)
    report=r.build_report(run)
    assert report["complete_tasks"]==0
    assert report["tasks"][0]["status"]=="pending"
    assert "metrics" not in report["tasks"][0]


@pytest.mark.parametrize("kind",["plan","receipt","artifact","frozen_file"])
def test_digest_corruption_rejected(tmp_path,kind):
    run,plan,state=fixture_run(tmp_path)
    entry=state["jobs"][plan["jobs"][0]["id"]]
    if kind=="plan": target=run/"plan.json"
    elif kind=="receipt": target=run/entry["receipt"]
    elif kind=="artifact": target=run/entry["attempt"]/"fold_0/E0/best.pt"
    else: target=Path(next(iter(plan["frozen_files"])))
    with target.open("ab") as stream: stream.write(b"\nchanged")
    with pytest.raises(ValueError,match="mismatch"): r.build_report(run)


def test_nested_protocol_rejected_even_with_valid_seal(tmp_path):
    run,plan,state=fixture_run(tmp_path)
    plan["protocol"]="nested_strict"
    dump(run/"plan.json",plan)
    dump(run/"plan.seal.json",{"sha256":r.sha256(run/"plan.json")})
    with pytest.raises(ValueError,match="Only paper_kfold"): r.build_report(run)


def test_smoke_result_rejected_even_with_receipt_hashes(tmp_path):
    run,plan,state=fixture_run(tmp_path)
    job=plan["jobs"][0]["id"]
    path=run/state["jobs"][job]["attempt"]/"result.json"
    result=r.read_json(path)
    result["mode"]="smoke"
    dump(path,result)
    reseal(run,state,job)
    with pytest.raises(ValueError,match="Mixed protocol"): r.build_report(run)


def test_attempt_history_is_not_fabricated(tmp_path):
    run,plan,state=fixture_run(tmp_path,complete_folds=0)
    job=plan["jobs"][0]
    parent=run/"jobs"/job["id"]
    parent.mkdir(parents=True)
    (parent/"attempt_001.log").write_text("RuntimeError: CUDA out of memory\n")
    (parent/"attempt_002.log").write_text("running\n")
    state["jobs"][job["id"]]=dict(status="failed",attempt=str((parent/"attempt_002").relative_to(run)),
                                exit_code=2,error="explicit fixture failure")
    rows=r.attempt_inventory(run,plan,state)
    assert rows[0]["status"]=="unaccepted_history_unknown" and rows[0]["exit_code"] is None
    assert "CUDA out of memory" in rows[0]["error_log_excerpt"]
    assert rows[1]["status"]=="failed" and rows[1]["retry"] and rows[1]["exit_code"]==2


def test_report_outputs_and_no_overwrite(tmp_path):
    run,plan,state=fixture_run(tmp_path)
    report=r.build_report(run)
    output=tmp_path/"derived"
    r.emit_report(report,output,run)
    assert (output/"REPORT.md").is_file()
    assert (output/"metric_summary.csv").is_file()
    assert "PENDING" in (output/"REPORT.md").read_text()
    with pytest.raises(ValueError,match="exists"): r.emit_report(report,output,run)
    with pytest.raises(ValueError,match="outside"): r.emit_report(report,run/"derived",run)


def test_no_model_or_gpu_modules_are_imported():
    source=Path(r.__file__).read_text()
    assert "import torch" not in source and "import dgl" not in source
    assert "subprocess" not in source


def test_precision_of_tie_rule():
    rows=synthetic_rows()
    for rr in rows:
        if rr["variant"]=="E1":
            rr["precision"] = 50 + rr["fold"]*10 + 1e-12
    result=r.metric_summary(rows,3)
    assert result["best"]["E1-E0"]["precision"]["fold_direction_counts"]["tied"]==3
