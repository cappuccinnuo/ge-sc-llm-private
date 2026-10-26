"""Synthetic-only acceptance tests; no real models, CUDA allocation or fitting."""
import copy
import json
from pathlib import Path

import pytest
import torch

from scripts.DFG.experiments.common import digest, sha256
from scripts.DFG.dfg_v2.experiment import precision_gpu as pg


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf8")
    return dict(path=str(path.resolve()), sha256=sha256(path))


def _hist(delta=0.0):
    return [dict(epoch=i, train_loss=.8-.1*i+delta,
                 inner_val_loss=.7-.1*i+delta) for i in range(3)]


def _resources(free=500):
    return dict(device="cuda", minimum_free_mib=free, peak_allocated_mib=2000,
                peak_reserved_mib=2100, seconds=5, memory_samples=4)


def _roundtrips():
    return {role:{ck:True for ck in ("best", "last")}
            for role in ("inner_val", "outer_test")}


def test_exact_gpu_repeats_use_registered_floor():
    result=pg.compute_noise(_hist(),_hist(),_hist(5e-5))
    assert result["passed"]
    assert result["tolerance"] == 1e-4
    assert result["original_repeats_loss_bitwise_equal"]


def test_noise_tolerance_is_three_times_measured_spread():
    result=pg.compute_noise(_hist(),_hist(.0002),_hist(.0005))
    assert result["passed"]
    assert result["tolerance"] == pytest.approx(.0006)
    assert not result["original_repeats_loss_bitwise_equal"]


def test_shared_must_pass_both_original_comparisons():
    result=pg.compute_noise(_hist(),_hist(.0002),_hist(-.0005))
    assert result["shared_vs_original_1"]["passed"]
    assert not result["shared_vs_original_2"]["passed"]
    assert not result["passed"]


@pytest.mark.parametrize("bad",[float("nan"),float("inf")])
def test_noise_rejects_nonfinite_history(bad):
    h=_hist();h[1]["train_loss"]=bad
    with pytest.raises(ValueError):
        pg.compute_noise(h,_hist(),_hist())


def test_noise_rejects_partial_three_epoch_run():
    with pytest.raises(AssertionError):
        pg.compute_noise(_hist()[:2],_hist(),_hist())


def _cpu_fixture(tmp_path, monkeypatch):
    from scripts.DFG.dfg_v2.experiment import precision_real as pr
    source={"frozen.py":"source-hash"}
    monkeypatch.setattr(pr,"_source_identity",lambda:source)
    seen=[]
    def validate_static(report):
        seen.append("static")
        if report.get("raw_failed"):
            raise ValueError("raw static gate")
    def validate_trajectory(report):
        seen.append("trajectory")
        if report.get("raw_failed"):
            raise ValueError("raw trajectory gate")
    monkeypatch.setattr(pr,"validate_static_evidence",validate_static,raising=False)
    monkeypatch.setattr(pr,"validate_trajectory_evidence",validate_trajectory,raising=False)
    common=_write(tmp_path/"frozen.json",{"immutable":True})
    rows=[]
    for i,(task,profile,reducer) in enumerate(pg.CPU_CASES):
        static=dict(task_id=task,profile=profile,reducer=reducer,status="passed",
                    sources=source,graph=common,initial=common,labels_ref=common,
                    folds=common,archived_plan=common,config={"lr":.005},
                    seeds={"fit":1},split_sha256="same",task="contract",fold=0,
                    seed=1,device="cpu",dtype="float64")
        static_ref=_write(tmp_path/str(i)/"static.json",static)
        trajectory=dict(static,static=static_ref)
        rows.append(dict(task_id=task,profile=profile,reducer=reducer,
                         static=static_ref,trajectory=_write(tmp_path/str(i)/"trajectory.json",trajectory)))
    accepted=dict(status="accepted",cases=rows)
    path=tmp_path/"acceptance.json"
    _write(path,accepted)
    _write(tmp_path/"acceptance.seal.json",{"acceptance_sha256":sha256(path)})
    return path,accepted,seen


def _reseal(path,document):
    _write(path,document)
    _write(path.with_name("acceptance.seal.json"),{"acceptance_sha256":sha256(path)})


def test_cpu_requires_all_six_distinct_verified_raw_cases(tmp_path,monkeypatch):
    path,document,seen=_cpu_fixture(tmp_path,monkeypatch)
    assert pg.validate_cpu_acceptance(path)==document
    assert seen.count("static")==6 and seen.count("trajectory")==6


@pytest.mark.parametrize("problem",["failed","missing","duplicate","wrong_case"])
def test_cpu_refuses_incomplete_or_duplicate_aggregate(tmp_path,monkeypatch,problem):
    path,doc,seen=_cpu_fixture(tmp_path,monkeypatch)
    if problem=="failed":doc["status"]="failed"
    elif problem=="missing":doc["cases"].pop()
    elif problem=="duplicate":doc["cases"][-1]=doc["cases"][0]
    else:doc["cases"][0]["profile"]="G2R"
    _reseal(path,doc)
    with pytest.raises(ValueError):
        pg.validate_cpu_acceptance(path)


def test_cpu_seal_tamper_rejected(tmp_path,monkeypatch):
    path,doc,seen=_cpu_fixture(tmp_path,monkeypatch)
    doc["extra"]="tamper"
    _write(path,doc)
    with pytest.raises(ValueError,match="seal"):
        pg.validate_cpu_acceptance(path)


@pytest.mark.parametrize("field",["static","trajectory"])
def test_cpu_report_digest_tamper_rejected(tmp_path,monkeypatch,field):
    path,doc,seen=_cpu_fixture(tmp_path,monkeypatch)
    ref=doc["cases"][0][field]
    _write(ref["path"],{"status":"passed","wrong":True})
    with pytest.raises((ValueError,AssertionError)):
        pg.validate_cpu_acceptance(path)


@pytest.mark.parametrize("field",["static","trajectory"])
def test_cpu_does_not_trust_sealed_passed_status_without_raw_gate(tmp_path,monkeypatch,field):
    path,doc,seen=_cpu_fixture(tmp_path,monkeypatch)
    row=doc["cases"][0]
    ref=row[field]
    raw=json.loads(Path(ref["path"]).read_text());raw["raw_failed"]=True
    row[field]=_write(ref["path"],raw)
    if field=="static":
        tr=json.loads(Path(row["trajectory"]["path"]).read_text());tr["static"]=row["static"]
        row["trajectory"]=_write(row["trajectory"]["path"],tr)
    _reseal(path,doc)
    with pytest.raises(ValueError,match="raw"):
        pg.validate_cpu_acceptance(path)


def test_cpu_rejects_static_trajectory_input_drift(tmp_path,monkeypatch):
    path,doc,seen=_cpu_fixture(tmp_path,monkeypatch)
    ref=doc["cases"][0]["trajectory"]
    raw=json.loads(Path(ref["path"]).read_text());raw["split_sha256"]="wrong"
    doc["cases"][0]["trajectory"]=_write(ref["path"],raw)
    _reseal(path,doc)
    with pytest.raises(ValueError,match="inputs differ"):
        pg.validate_cpu_acceptance(path)


def _identity(tmp_path):
    ref=_write(tmp_path/"frozen.json",{})
    initial=dict(ref,state_sha256="untrained-state")
    return dict(task_id="access_control_node",task="node",profile="G0",graph=ref,
                initial=initial,config={"schedule_epochs":50},seeds={"fit":1010000},
                split={"inner_train_files":["a"],"inner_val_files":["b"],"outer_test_files":["c"]},
                folds=ref,labels_ref=ref,archived_plan=ref,fold=0,seed=1,reducer="mean")


def _gpu_fixture(tmp_path,deltas=(0,0,0)):
    identity=_identity(tmp_path)
    cpu=_write(tmp_path/"cpu.json",{"accepted":True})
    for repeat,delta in zip(pg.REPEATS,deltas):
        root=tmp_path/repeat
        impl=pg.IMPLEMENTATIONS[repeat]
        config=dict(identity["config"],maximum_training_epochs=3,device="cuda:0",
                    layer_impl=impl,mode="projection_equivalence")
        binding=dict(graph=identity["graph"],labels=identity["labels_ref"],
            folds=identity["folds"],split=identity["split"],layer_impl=impl,
            initial_state_sha256=identity["initial"]["state_sha256"],
            effective_config_sha256=digest(config))
        result=dict(status="complete",history_rows=3,layer_impl=impl,
            initial_sha256=identity["initial"]["state_sha256"],
            resources=_resources(),checkpoint_roundtrip_exact=_roundtrips())
        binding_ref=_write(root/"fit"/"binding.json",binding)
        model_input = {"source": "synthetic-frozen-input"}
        _write(root/"fit"/"model_input.json", model_input)
        checkpoints = {}
        for name, epoch in (("best", 1), ("last", 2)):
            weight = root/"fit"/(name+".pt")
            weight.write_bytes(("synthetic checkpoint " + impl + " " + name).encode("utf8"))
            checkpoints[name] = sha256(weight)
            _write(root/"fit"/(name+".json"), dict(format="ddg-controlled-v1",
                state_sha256="a"*64, binding=binding, binding_sha256=digest(binding),
                epoch=epoch, model_input=model_input))
        result.update(checkpoint_sha256=checkpoints, best_epoch=1, last_epoch=2)
        result_ref=_write(root/"fit"/"result.json",result)
        history=root/"fit"/"history.jsonl"
        history.write_text("".join(json.dumps(row)+"\n" for row in _hist(delta)),encoding="utf8")
        record=dict(status="complete",repeat=repeat,profile="G0",layer_impl=impl,
            device="cuda:0",dtype="float32",identity=identity,environment={"torch":"frozen"},
            runtime={"source":"sha"},cpu_acceptance=cpu,resources=_resources(),
            artifacts={"binding.json":binding_ref,"result.json":result_ref,
                       "history.jsonl":dict(path=str(history),sha256=sha256(history))})
        _write(root/"run.json",record)
    return tmp_path


def test_summary_rechecks_identity_history_resources_and_seals(tmp_path):
    _gpu_fixture(tmp_path)
    result=pg.summarize_noise(tmp_path)
    assert result["passed"] and result["diagnostic_fits"]==3
    assert json.loads((tmp_path/"acceptance.seal.json").read_text())[
        "acceptance_sha256"]==sha256(tmp_path/"acceptance.json")
    with pytest.raises(FileExistsError):
        pg.summarize_noise(tmp_path)


def test_summary_retains_failed_noise_evidence(tmp_path):
    _gpu_fixture(tmp_path,deltas=(0,0,.01))
    with pytest.raises(AssertionError):
        pg.summarize_noise(tmp_path)
    assert json.loads((tmp_path/"acceptance.json").read_text())["status"]=="failed_noise_gate"


@pytest.mark.parametrize("field",["identity","environment","runtime","repeat","layer_impl","status"])
def test_summary_rejects_mixed_runs(tmp_path,field):
    _gpu_fixture(tmp_path)
    path=tmp_path/"shared"/"run.json"
    record=json.loads(path.read_text())
    if field=="identity":record[field]["seeds"]["fit"]+=1
    elif field=="environment":record[field]["torch"]="other"
    elif field=="runtime":record[field]["source"]="other"
    else:record[field]="wrong"
    _write(path,record)
    with pytest.raises(ValueError):
        pg.summarize_noise(tmp_path)


def test_summary_rejects_tampered_fit_artifact(tmp_path):
    _gpu_fixture(tmp_path)
    path=tmp_path/"shared"/"fit"/"history.jsonl"
    path.write_text(path.read_text()+"\n",encoding="utf8")
    with pytest.raises((ValueError,AssertionError)):
        pg.summarize_noise(tmp_path)


def _pilot_result():
    return dict(status="complete",layer_impl="shared_projection",resources=_resources(),
        checkpoint_roundtrip_exact=_roundtrips(),outer_supervision_used_in_optimization=False,
        gradient_audit={"epochs":[{"epoch":0,"v2_training_support":2,"v2_relations":[
            {"canonical":["a","DATA_DEF_USE","b"],"inner_train_edges":2,"message_gradient_l1":.25},
            {"canonical":["b","REV_DATA_DEF_USE","a"],"inner_train_edges":0,"message_gradient_l1":0}]}]})


def test_pilot_counts_training_and_heldout_canonicals():
    result=pg.audit_pilot_result(_pilot_result())
    assert result["passed"]
    assert result["training_supported_canonical_count"]==1
    assert result["heldout_only_canonical_count"]==1


@pytest.mark.parametrize("issue",["memory","reload","outer","zero_gradient","heldout_gradient","missing_epoch"])
def test_pilot_rejects_required_acceptance_failure(issue):
    result=_pilot_result()
    if issue=="memory":result["resources"]["minimum_free_mib"]=99
    elif issue=="reload":result["checkpoint_roundtrip_exact"]["inner_val"]["last"]=False
    elif issue=="outer":result["outer_supervision_used_in_optimization"]=True
    elif issue=="zero_gradient":result["gradient_audit"]["epochs"][0]["v2_relations"][0]["message_gradient_l1"]=0
    elif issue=="heldout_gradient":result["gradient_audit"]["epochs"][0]["v2_relations"][1]["message_gradient_l1"]=.2
    else:result["gradient_audit"]["epochs"]=[]
    assert not pg.audit_pilot_result(result)["passed"]


def test_resource_warning_does_not_weaken_100_mib_gate():
    result=_pilot_result();result["resources"]["minimum_free_mib"]=299
    audit=pg.audit_pilot_result(result)
    assert audit["passed"] and audit["resources"]["below_300_mib_warning"]
    result["resources"]["minimum_free_mib"]=99
    assert not pg.audit_pilot_result(result)["passed"]


def test_noise_fit_refuses_overwrite_before_any_execution(tmp_path,monkeypatch):
    monkeypatch.setattr(pg,"_fit_context",lambda *a,**kw:pytest.fail("no fit permitted"))
    with pytest.raises(FileExistsError):
        pg.run_noise_fit("unused","G0","original_1",tmp_path,"unused")


def test_noise_fit_cpu_gate_failure_retained_and_no_fallback(tmp_path,monkeypatch):
    def fail_cpu(path):raise ValueError("CPU rejected")
    monkeypatch.setattr(pg,"validate_cpu_acceptance",fail_cpu)
    monkeypatch.setattr(pg,"_fit_context",lambda *a,**kw:pytest.fail("no fit permitted"))
    output=tmp_path/"attempt"
    with pytest.raises(ValueError,match="CPU rejected"):
        pg.run_noise_fit("unused","G0","original_1",output,"unused")
    assert json.loads((output/"run.json").read_text())["status"]=="failed"
    assert json.loads((output/"failure.json").read_text())["automatic_retry"] is False

def test_pilot_rejects_missing_canonical_rows_with_positive_training_support():
    result=_pilot_result()
    result["gradient_audit"]["epochs"][0]["v2_relations"]=[]
    assert not pg.audit_pilot_result(result)["passed"]


@pytest.mark.parametrize("blocker",["environment","dtype","cuda"])
def test_noise_fit_blocks_unapproved_environment_dtype_or_cpu_fallback(tmp_path,monkeypatch,blocker):
    identity=_identity(tmp_path)
    identity["config"]["environment"]={"torch":"frozen"}
    cpu=_write(tmp_path/"cpu.json",{"accepted":True})
    monkeypatch.setattr(pg,"validate_cpu_acceptance",lambda path:{"cases":[]})
    monkeypatch.setattr(pg,"_cpu_case_matches",lambda report,ctx:None)
    monkeypatch.setattr(pg,"_context",lambda *args:identity)
    monkeypatch.setattr(pg,"_environment",lambda:{"torch":"changed" if blocker=="environment" else "frozen"})
    monkeypatch.setattr(torch.cuda,"is_available",lambda:blocker!="cuda")
    monkeypatch.setattr(pg,"_fit_context",lambda *a,**kw:pytest.fail("no fit permitted"))
    output=tmp_path/"attempt"
    before=torch.get_default_dtype()
    try:
        if blocker=="dtype":torch.set_default_dtype(torch.float64)
        with pytest.raises((ValueError,RuntimeError)):
            pg.run_noise_fit("plan","G0","original_1",output,cpu["path"])
    finally:
        torch.set_default_dtype(before)
    assert json.loads((output/"failure.json").read_text())["automatic_retry"] is False


@pytest.mark.parametrize("name", ["best", "last"])
@pytest.mark.parametrize("damage", ["missing_weights", "changed_weights", "missing_sidecar", "binding", "epoch", "input"])
def test_noise_summary_checks_actual_checkpoint_bytes_and_metadata(tmp_path, name, damage):
    _gpu_fixture(tmp_path)
    fit = tmp_path/"shared"/"fit"
    weight = fit/(name+".pt")
    metadata_path = fit/(name+".json")
    if damage == "missing_weights":
        weight.unlink()
    elif damage == "changed_weights":
        weight.write_bytes(weight.read_bytes()+b"changed")
    elif damage == "missing_sidecar":
        metadata_path.unlink()
    else:
        metadata = json.loads(metadata_path.read_text())
        if damage == "binding":
            metadata["binding"]["layer_impl"] = "original"
        elif damage == "epoch":
            metadata["epoch"] = 99
        else:
            metadata["model_input"] = {"wrong": True}
        _write(metadata_path, metadata)
    with pytest.raises(ValueError, match="Checkpoint"):
        pg.summarize_noise(tmp_path)
    assert not (tmp_path/"acceptance.json").exists()


def test_noise_summary_requires_both_checkpoint_digests(tmp_path):
    _gpu_fixture(tmp_path)
    run_path = tmp_path/"shared"/"run.json"
    record = json.loads(run_path.read_text())
    result_ref = record["artifacts"]["result.json"]
    result = json.loads(Path(result_ref["path"]).read_text())
    result["checkpoint_sha256"].pop("last")
    record["artifacts"]["result.json"] = _write(result_ref["path"], result)
    _write(run_path, record)
    with pytest.raises(ValueError, match="digests"):
        pg.summarize_noise(tmp_path)
