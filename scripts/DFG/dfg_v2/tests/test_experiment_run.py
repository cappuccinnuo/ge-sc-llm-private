"""Runner integration on twenty synthetic source-file identities; never CUDA."""
import copy
from pathlib import Path
import pytest
import torch
from scripts.DFG.integration.io import read_json, sha256, write_json
from scripts.DFG.dfg_v2 import store
from scripts.DFG.dfg_v2.inputs import build_manifest
from scripts.DFG.dfg_v2.tests.task_fixtures import synthetic_registry, SyntheticEncoder
from scripts.DFG.dfg_v2.experiment import run

CONFIG = dict(seed=1,schedule_epochs=50,maximum_training_epochs=2,
    hidden_size=8,layers=2,heads=2,feature="inside_token",threads=2,
    initial_lr=.0005,max_lr=.01,div_factor=20,final_div_factor=1,
    cycle_momentum=True,weight_decay=5e-6,patience=7,delta=.001)


@pytest.fixture(scope="module")
def graph_store(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("runner_graphs")
    registry = synthetic_registry(tmp)
    manifest = build_manifest(tmp / "inputs", registry=registry)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(store,"TokenEncoder",SyntheticEncoder)
        patch.setattr(store,"_runtime",lambda:{"fixture":"unchanged"})
        store.build_store(manifest,output=tmp/"store",graph_keys="F1,F2,F3")
    return tmp / "store/store.json"


@pytest.fixture
def plan(graph_store,tmp_path,monkeypatch):
    # Keep CPU tests independent of other parallel authors editing new code.
    monkeypatch.setattr(run,"_code_refs",lambda:{"fixture":"frozen"})
    result = run.create_plan(graph_store,tmp_path/"batch",tasks=["synthetic_contract"],
        profiles=["G0","G3R"],folds=[0],test_mode=True,test_config=CONFIG)
    return tmp_path/"batch/plan.json",result


def test_cpu_end_to_end_and_success_reuse(plan,monkeypatch):
    path,doc = plan
    with pytest.raises(ValueError,match="Selection"):
        run.summarize(path)
    with pytest.raises(ValueError,match="explicit programmatic"):
        run.execute(path)
    rows = run.execute(path,allow_cpu_test=True)
    assert len(rows)==2 and all(r["status"]=="complete" for r in rows)
    assert run.verify(path)["completed_jobs"]==2
    def never(*args,**kwargs):raise AssertionError("Successful job retrained")
    monkeypatch.setattr(run,"_run_one",never)
    assert all(r["status"]=="reused" for r in run.execute(path,allow_cpu_test=True))
    real_read = run.read_json
    def no_outer_reads(p):
        assert Path(p).name not in ("result.json","outer_test_predictions.json")
        return real_read(p)
    with monkeypatch.context() as patch:
        patch.setattr(run,"read_json",no_outer_reads)
        selection = run.select(path)
    assert selection["outer_test_used"] is False
    assert selection["additional_seed_condition_met"] is False
    assert selection["efficacy_conclusion_allowed"] is False
    assert run.summarize(path)["completed_jobs"]==2
    for job in doc["jobs"]:
        attempt = run._job_directory(path.parent,job)/"attempt_001"
        for role in ("inner_val","outer_test"):
            assert all(r.get("node_type")!="env_source" for r in read_json(attempt/(role+"_predictions.json")))
    with pytest.raises(FileExistsError):run.select(path)
    with pytest.raises(FileExistsError):run.summarize(path)


def test_plan_preserves_folds_and_initial_identity(plan):
    path,doc=plan
    assert len(doc["jobs"])==2
    assert doc["protocol_version"]=="dfg-v2-nested-v1"
    assert doc["score_role"]=="outer_test" and doc["selection_role"]=="inner_val"
    for job in doc["jobs"]:
        task,info,entry=run._prepared(doc,job)
        initial=run._initial(entry,info,job)
        assert initial["optimizer_steps"]==0
        assert len(set(info["split"]["inner_train_files"]) & set(info["split"]["inner_val_files"]))==0
    assert run.verify(path,require_complete=False)["completed_jobs"]==0
    with pytest.raises(ValueError,match="Incomplete"):run.verify(path)


@pytest.mark.parametrize("damage",["plan","initial","graph","folds","labels","code"])
def test_tampering_rejected(plan,damage,monkeypatch):
    path,doc=plan
    task,info,entry=run._prepared(doc,doc["jobs"][0])
    if damage=="code":
        monkeypatch.setattr(run,"_code_refs",lambda:{"fixture":"changed"})
        with pytest.raises(ValueError):run._load_plan(path)
        return
    target = path if damage=="plan" else Path(entry["initial" if damage=="initial" else "graph"]["path"]) if damage in ("initial","graph") else Path(task["record"][damage]["path"])
    original=target.read_bytes()
    try:
        target.write_bytes(original+b"tampered")
        with pytest.raises(ValueError):run._load_plan(path)
    finally:
        target.write_bytes(original)


def test_failure_retained_requires_explicit_retry(plan,monkeypatch):
    path,doc=plan
    job=doc["jobs"][0]
    only=run.job_id(job)
    calls=[]
    real=run._run_one
    def fail(*args,**kwargs):
        calls.append(1)
        raise RuntimeError("simulated resource failure")
    monkeypatch.setattr(run,"_run_one",fail)
    with pytest.raises(RuntimeError,match="simulated"):
        run.execute(path,only=only,allow_cpu_test=True)
    folder=run._job_directory(path.parent,job)
    assert (folder/"attempt_001.failure.json").is_file()
    with pytest.raises(RuntimeError,match="explicit --retry"):
        run.execute(path,only=only,allow_cpu_test=True)
    assert len(calls)==1
    monkeypatch.setattr(run,"_run_one",real)
    result=run.execute(path,only=only,retry=True,allow_cpu_test=True)
    assert result[0]["attempt"].endswith("attempt_002")
    assert (folder/"attempt_001.failure.json").is_file()
    started=read_json(folder/"attempt_002.started.json")
    assert started["resume_epoch"] is False and started["retry_from_same_untrained_initial"] is True


def test_lock_and_unknown_job_rejection(plan):
    path,doc=plan
    with run._Lock(path.parent/".synthetic.lock"):
        with pytest.raises(RuntimeError,match="lock"):
            run.execute(path,allow_cpu_test=True)
    with pytest.raises(ValueError,match="Unknown"):
        run.execute(path,only="fake/0/1/G0",allow_cpu_test=True)


def test_original_prediction_identity_target_and_probability_checks(plan):
    path,doc=plan
    task,info,entry=run._prepared(doc,doc["jobs"][0])
    labels=run.read_labels(task["record"]["labels"])
    rows=[dict(file=f,target=labels[f],score_role="inner_val",best=0,last=0,
        best_positive_probability=.1,last_positive_probability=.2) for f in info["split"]["inner_val_files"]]
    run._validate_predictions(rows,"inner_val",task,info,entry)
    for mode in ("missing","target","probability","role","duplicate"):
        bad=copy.deepcopy(rows)
        if mode=="missing":bad.pop()
        if mode=="target":bad[0]["target"]=1-bad[0]["target"]
        if mode=="probability":bad[0]["best_positive_probability"]=float("nan")
        if mode=="role":bad[0]["score_role"]="outer_test"
        if mode=="duplicate":bad.append(copy.deepcopy(bad[0]))
        with pytest.raises(ValueError):run._validate_predictions(bad,"inner_val",task,info,entry)


def test_invalid_selector_and_output_reuse(graph_store,plan,tmp_path):
    path,doc=plan
    with pytest.raises(FileExistsError):run.create_plan(graph_store,path.parent)
    for kwargs in ({"profiles":["bad"]},{"tasks":["unknown"]},{"seeds":[0]},{"folds":[0,0]}):
        with pytest.raises(ValueError):
            run.create_plan(graph_store,tmp_path/"invalid",test_mode=True,test_config=CONFIG,**kwargs)


def test_node_prediction_original_identity_and_aux_exclusion(graph_store,tmp_path,monkeypatch):
    monkeypatch.setattr(run,"_code_refs",lambda:{"fixture":"frozen"})
    output=tmp_path/"node_batch"
    doc=run.create_plan(graph_store,output,tasks=["synthetic_node"],profiles=["G3R"],
        folds=[0],test_mode=True,test_config=CONFIG)
    path=output/"plan.json"
    run.execute(path,allow_cpu_test=True)
    assert run.verify(path)["completed_jobs"]==1
    job=doc["jobs"][0]
    task,info,entry=run._prepared(doc,job)
    attempt=run._job_directory(output,job)/"attempt_001"
    rows=read_json(attempt/"outer_test_predictions.json")
    assert rows and all(r["node_type"]!="env_source" for r in rows)
    bad=copy.deepcopy(rows)
    bad[0]["original_graph_node_id"]=999999
    with pytest.raises(ValueError,match="identity"):
        run._validate_predictions(bad,"outer_test",task,info,entry)
    bad=copy.deepcopy(rows)
    bad[0]["model_node_id"]+=1
    with pytest.raises(ValueError,match="node type"):
        run._validate_predictions(bad,"outer_test",task,info,entry)


def test_payload_sidecar_disagreement_even_after_outer_file_hashes_updated(plan):
    path,doc=plan
    job=doc["jobs"][0]
    run.execute(path,only=run.job_id(job),allow_cpu_test=True)
    attempt=run._job_directory(path.parent,job)/"attempt_001"
    payload=torch.load(str(attempt/"best.pt"),map_location="cpu")
    payload["epoch"]+=1
    torch.save(payload,str(attempt/"best.pt"))
    result=read_json(attempt/"result.json")
    result["checkpoint_sha256"]["best"]=sha256(attempt/"best.pt")
    write_json(attempt/"result.json",result)
    receipt=read_json(attempt/"receipt.json")
    receipt["artifacts"]["best.pt"]=sha256(attempt/"best.pt")
    receipt["artifacts"]["result.json"]=sha256(attempt/"result.json")
    write_json(attempt/"receipt.json",receipt)
    with pytest.raises(ValueError,match="payload/sidecar"):
        run.verify(path,require_complete=False)
