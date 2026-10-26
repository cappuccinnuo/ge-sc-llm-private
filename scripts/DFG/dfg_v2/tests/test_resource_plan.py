"""Resource-only plans reuse exact initial files; no CUDA or real-data fitting."""
import copy
import pytest
from scripts.DFG.integration.io import read_json, write_json, sha256
from scripts.DFG.dfg_v2.experiment import run, resource_plan
from scripts.DFG.dfg_v2.experiment.preflight import DEFAULT_PREFLIGHT_POLICY
from scripts.DFG.dfg_v2.tests.test_experiment_run import graph_store, CONFIG

RUN_PATH = "scripts/DFG/dfg_v2/experiment/run.py"
NEW_PATH = "scripts/DFG/dfg_v2/experiment/preflight.py"


def reseal(path, doc):
    write_json(path, doc)
    seal = read_json(path.with_name("plan.seal.json"))
    seal.update(plan_sha256=sha256(path), test_mode=doc["test_mode"])
    write_json(path.with_name("plan.seal.json"), seal)


@pytest.fixture
def source_plan(graph_store, tmp_path, monkeypatch):
    old_runtime = {RUN_PATH: "before", "sco_models/model_hgt.py": "frozen"}
    monkeypatch.setattr(run, "_code_refs", lambda: dict(old_runtime))
    doc = run.create_plan(graph_store, tmp_path/"old", tasks=["synthetic_contract"],
        profiles=["G0", "G3R"], folds=[0], layer_impl="shared_projection",
        test_mode=True, test_config=CONFIG)
    # This fixture never executes CUDA. Give sealed synthetic data a production
    # descriptor solely to exercise resource-plan identity without real assets.
    doc["test_mode"] = False
    for task in doc["tasks"].values():
        task["config"]["device"] = "cuda:0"
    path = tmp_path/"old/plan.json"
    reseal(path, doc)
    new_runtime = dict(old_runtime)
    new_runtime.update({RUN_PATH:"after", NEW_PATH:"new"})
    monkeypatch.setattr(run, "_code_refs", lambda: dict(new_runtime))
    return path, doc


def test_exact_frozen_refs_and_policy_sealed(source_plan, tmp_path, monkeypatch):
    source, old = source_plan
    before = {str(p):p.read_bytes() for p in source.parent.rglob("*") if p.is_file()}
    monkeypatch.setattr(run, "make_model", lambda *a,**k: pytest.fail("No reinitialization"))
    new = resource_plan.create_resource_plan(source, tmp_path/"new", 3100)
    assert new["tasks"] == old["tasks"] and new["jobs"] == old["jobs"]
    assert new["resource_policy"]["baseline_minimum_free_mib"] == 3100
    assert new["resource_policy"]["running_minimum_free_mib"] == 100
    assert new["resource_origin"]["plan"]["sha256"] == sha256(source)
    assert resource_plan.validate_resource_origin(new)["untrained_initials_reused"]
    assert before == {str(p):p.read_bytes() for p in source.parent.rglob("*") if p.is_file()}
    assert run._load_plan(tmp_path/"new/plan.json") == new
    with pytest.raises(FileExistsError):
        resource_plan.create_resource_plan(source,tmp_path/"new")


@pytest.mark.parametrize("field", ["tasks", "jobs", "initialization_version", "profiles"])
def test_resealed_frozen_field_changes_rejected(source_plan,tmp_path,field):
    source, old = source_plan
    doc = resource_plan.create_resource_plan(source,tmp_path/"new")
    if field == "tasks":
        doc["tasks"]["synthetic_contract"]["config"]["initial_lr"] *= 2
    elif field == "jobs":
        doc["jobs"][0]["seed"] += 1
    elif field == "profiles":
        doc[field] = ["G0"]
    else:
        doc[field] = "changed"
    reseal(tmp_path/"new/plan.json",doc)
    with pytest.raises(ValueError):
        run._load_plan(tmp_path/"new/plan.json")


def test_computation_changes_and_missing_files_rejected(source_plan,tmp_path,monkeypatch):
    source, old = source_plan
    changed = dict(old["runtime"])
    changed["sco_models/model_hgt.py"] = "changed"
    monkeypatch.setattr(run,"_code_refs",lambda:changed)
    with pytest.raises(ValueError,match="Frozen computation"):
        resource_plan.create_resource_plan(source,tmp_path/"bad")
    assert not (tmp_path/"bad").exists()
    with pytest.raises(ValueError,match="Frozen computation"):
        resource_plan.runtime_difference(old["runtime"], {})


def test_source_initial_and_source_seal_tampering_rejected(source_plan,tmp_path):
    source, old=source_plan
    task,info,entry=run._prepared(old,old["jobs"][0])
    initial=run.Path(entry["initial"]["path"])
    original=initial.read_bytes()
    try:
        initial.write_bytes(original+b"tamper")
        with pytest.raises(ValueError,match="SHA256"):
            resource_plan.create_resource_plan(source,tmp_path/"bad")
    finally:
        initial.write_bytes(original)
    resource_plan.create_resource_plan(source,tmp_path/"new")
    source.write_bytes(source.read_bytes()+b" ")
    with pytest.raises(ValueError,match="SHA256"):
        run._load_plan(tmp_path/"new/plan.json")


def test_policy_and_origin_required_together(source_plan,tmp_path):
    source,old=source_plan
    doc=resource_plan.create_resource_plan(source,tmp_path/"new")
    del doc["resource_policy"]
    reseal(tmp_path/"new/plan.json",doc)
    with pytest.raises(ValueError,match="origin requires"):
        run._load_plan(tmp_path/"new/plan.json")


def test_cli_source_and_threshold_validation(monkeypatch,tmp_path):
    called=[]
    monkeypatch.setattr(resource_plan,"create_resource_plan",
        lambda *a,**k: called.append((a,k)) or {"jobs":[{}]})
    run.main(["plan","--from-plan","source.json","--output",str(tmp_path/"new"),
              "--baseline-min-free-mib","3200"])
    assert called[0][1]["baseline_minimum_free_mib"] == 3200
    with pytest.raises(ValueError,match="preserves"):
        run.main(["plan","--from-plan","source.json","--output","x","--profiles","G0"])
    with pytest.raises(ValueError,match="requires --from-plan"):
        run.main(["plan","--store","store.json","--output","x","--baseline-min-free-mib","1"])
    with pytest.raises(SystemExit):
        run.main(["plan","--store","x","--from-plan","y","--output","z"])


@pytest.fixture
def resource_result(tmp_path):
    from scripts.DFG.dfg_v2.experiment import preflight
    import json
    plan={"resource_policy":copy.deepcopy(DEFAULT_PREFLIGHT_POLICY)}
    job={"task_id":"synthetic_node","fold":0,"seed":1,"profile":"G3R"}
    plan_path=tmp_path/"resource_plan.json"
    write_json(plan_path,plan)
    baseline=dict(uuid="GPU-test",total_mib=4096,used_mib=500,free_mib=3500)
    after=dict(uuid="GPU-test",total_mib=4096,used_mib=600,free_mib=3400)
    context=dict(baseline=baseline,after_initialization=after,
                 free_decrease_mib=100,used_increase_mib=100)
    context_path=tmp_path/"context.json"
    write_json(context_path,context)
    receipt=dict(status="passed",job=job,plan_sha256=sha256(plan_path),
        policy=plan["resource_policy"],baseline=baseline,cuda_initialized_before=False,
        cuda_initialized_after=False,process_scope="fresh_process_one_job",pid=123)
    receipt_path=tmp_path/"preflight.json"
    write_json(receipt_path,receipt)
    sample=dict(index=0,uuid="GPU-test",total_mib=4096,used_mib=1000,free_mib=3000,
        torch_allocated_mib=200,torch_reserved_mib=400,non_torch_residual_estimate_mib=696,
        context_adjusted_residual_estimate_mib=596)
    raw=tmp_path/"samples.jsonl"
    raw.write_text(json.dumps(sample)+"\n")
    result={"resources":dict(resource_policy=plan["resource_policy"],
        preflight=resource_plan._ref(receipt_path),baseline=baseline,
        context_ref=resource_plan._ref(context_path),context_observation=context,
        raw_samples_path=str(raw),raw_samples_sha256=sha256(raw),
        paired_sample_count=1,memory_samples=1,minimum_free_mib=3000,total_mib=4096,
        peak_allocated_mib=250,peak_reserved_mib=500,non_torch_residual_estimate_mib=596,
        context_adjusted_residual_estimate_mib=496,training_pid=123)}
    return result,plan,job,plan_path,raw,receipt_path


def test_resource_evidence_is_verified(resource_result):
    result,plan,job,path,raw,receipt_path=resource_result
    resource_plan.validate_resource_result(result,plan,job,path)
    raw.write_bytes(raw.read_bytes()+b" ")
    with pytest.raises(ValueError,match="SHA256"):
        resource_plan.validate_resource_result(result,plan,job,path)


@pytest.mark.parametrize("damage",["initialized","pid","baseline","context","count","minimum","residual"])
def test_rehashed_inconsistent_resource_evidence_rejected(resource_result,damage):
    result,plan,job,path,raw,receipt_path=resource_result
    resources=result["resources"]
    if damage in ("initialized","pid"):
        receipt=read_json(receipt_path)
        receipt["cuda_initialized_before" if damage=="initialized" else "pid"]=True if damage=="initialized" else 456
        write_json(receipt_path,receipt)
        resources["preflight"]=resource_plan._ref(receipt_path)
    elif damage=="baseline":
        resources["baseline"]=dict(resources["baseline"],free_mib=100)
    elif damage=="context":
        resources["context_observation"]=dict(resources["context_observation"],free_decrease_mib=1)
    elif damage=="count":
        resources["memory_samples"]=2
    elif damage=="minimum":
        resources["minimum_free_mib"]=3001
    else:
        resources["non_torch_residual_estimate_mib"]=1
    with pytest.raises(ValueError):
        resource_plan.validate_resource_result(result,plan,job,path)
