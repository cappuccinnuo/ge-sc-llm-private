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


# Prompt 7c: these are synthetic resource/identity tests, never GPU fits.
def approval_for(path, doc, output):
    record = dict(version=resource_plan.APPROVAL_VERSION, approved=True,
        policy="local_dev_v1", source_plan=resource_plan._ref(path),
        authorized_jobs=[run.job_id(job) for job in doc["jobs"]],
        user_answer="Synthetic test approval", recorded_at="2026-10-26T12:00:00-04:00",
        test_fixture=True)
    write_json(output, record)
    return output


@pytest.fixture
def strict_parent(source_plan, tmp_path, monkeypatch):
    old_path, old = source_plan
    parent = resource_plan.create_resource_plan(old_path, tmp_path/"strict")
    path = tmp_path/"strict/plan.json"
    approval = approval_for(path, parent, tmp_path/"approval.json")
    current = dict(parent["runtime"])
    current[RUN_PATH] = "local-run"
    current["scripts/DFG/dfg_v2/experiment/local_dev.py"] = "local-resource-helper"
    current["scripts/DFG/dfg_v2/experiment/precision_gpu.py"] = "local-policy-audit-dispatch"
    monkeypatch.setattr(run, "_code_refs", lambda:dict(current))
    return path, parent, approval


def test_local_plan_immediate_parent_chain_initials_and_approval(strict_parent,tmp_path,monkeypatch):
    path, parent, approval = strict_parent
    historical = {str(p):p.read_bytes() for folder in ("strict","old")
                  for p in (tmp_path/folder).rglob("*") if p.is_file()}
    monkeypatch.setattr(run, "make_model", lambda *a,**k:pytest.fail("No new initialization"))
    doc = resource_plan.create_resource_plan(path,tmp_path/"local",
        resource_policy="local_dev_v1",approval_record=approval)
    assert doc["resource_origin"]["version"] == resource_plan.LOCAL_ORIGIN_VERSION
    assert doc["resource_origin"]["plan"] == resource_plan._ref(path)
    assert doc["resource_origin"]["approval"] == resource_plan._ref(approval)
    assert doc["tasks"] == parent["tasks"] and doc["jobs"] == parent["jobs"]
    assert doc["resource_policy"]["version"] == "local_dev_v1"
    assert doc["resource_policy"]["running_minimum_free_mib"] == 100
    assert run._load_plan(tmp_path/"local/plan.json") == doc
    assert historical == {str(p):p.read_bytes() for folder in ("strict","old")
                          for p in (tmp_path/folder).rglob("*") if p.is_file()}
    # Old origin still validates against its historical source, not current code.
    assert resource_plan.validate_resource_origin(parent)["frozen_fields_identical"]
    with pytest.raises(ValueError,match="original production"):
        resource_plan.create_resource_plan(path,tmp_path/"wrong-default")
    with pytest.raises(ValueError,match="directly reference"):
        resource_plan.create_resource_plan(tmp_path/"local/plan.json",tmp_path/"grandchild",
            resource_policy="local_dev_v1",approval_record=approval)


@pytest.mark.parametrize("damage",["missing","unapproved","wrong_source","jobs","answer","time","policy"])
def test_local_approval_fail_closed(strict_parent,tmp_path,damage):
    path,parent,approval=strict_parent
    rec=read_json(approval)
    if damage=="missing":
        approval=None
    elif damage=="unapproved":
        rec["approved"]=False
    elif damage=="wrong_source":
        rec["source_plan"]["sha256"]="0"*64
    elif damage=="jobs":
        rec["authorized_jobs"]=rec["authorized_jobs"][:1]
    elif damage=="answer":
        rec["user_answer"]=""
    elif damage=="time":
        rec["recorded_at"]=""
    else:
        rec["policy"]="different"
    if approval:
        write_json(approval,rec)
    with pytest.raises(ValueError):
        resource_plan.create_resource_plan(path,tmp_path/"blocked",
            resource_policy="local_dev_v1",approval_record=approval)
    assert not (tmp_path/"blocked").exists()


@pytest.mark.parametrize("damage",["config","initial_ref","graph_ref","approval","parent","runtime"])
def test_local_resealed_mismatches_rejected(strict_parent,tmp_path,damage):
    path,parent,approval=strict_parent
    doc=resource_plan.create_resource_plan(path,tmp_path/"local",
        resource_policy="local_dev_v1",approval_record=approval)
    restore = None
    if damage=="config":
        doc["tasks"]["synthetic_contract"]["config"]["initial_lr"] *= 2
    elif damage in ("initial_ref","graph_ref"):
        task,info,entry=run._prepared(doc,doc["jobs"][0])
        key="initial" if damage=="initial_ref" else "graph"
        target=run.Path(entry[key]["path"])
        restore=(target,target.read_bytes())
        target.write_bytes(restore[1]+b"tamper")
    elif damage=="approval":
        changed=read_json(approval)
        changed["approved"]=False
        write_json(approval,changed)
        doc["resource_origin"]["approval"]=resource_plan._ref(approval)
    elif damage=="parent":
        path.write_bytes(path.read_bytes()+b" ")
    else:
        doc["runtime"]["sco_models/model_hgt.py"]="changed"
    reseal(tmp_path/"local/plan.json",doc)
    try:
        with pytest.raises(ValueError):
            run._load_plan(tmp_path/"local/plan.json")
    finally:
        if restore:
            restore[0].write_bytes(restore[1])


def test_local_extensions_do_not_relax_old_runtime_allowlist():
    before={RUN_PATH:"before"}
    after=dict(before,**{"scripts/DFG/dfg_v2/experiment/local_dev.py":"new"})
    with pytest.raises(ValueError,match="Frozen computation"):
        resource_plan.runtime_difference(before,after)
    assert resource_plan.runtime_difference(before,after,resource_plan.LOCAL_RUNTIME_CHANGES)


def test_local_cli_arguments(monkeypatch,tmp_path):
    calls=[]
    monkeypatch.setattr(resource_plan,"create_resource_plan",
        lambda *a,**k:calls.append((a,k)) or {"jobs":[{}]})
    run.main(["plan","--from-plan","parent.json","--output",str(tmp_path/"new"),
              "--resource-policy","local_dev_v1","--approval-record","approval.json"])
    assert calls[0][1]["resource_policy"]=="local_dev_v1"
    assert calls[0][1]["approval_record"]=="approval.json"
    with pytest.raises(ValueError,match="requires --from-plan"):
        run.main(["plan","--store","store.json","--output","x",
                  "--resource-policy","local_dev_v1"])



@pytest.fixture
def local_result(resource_result,tmp_path):
    import json
    from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY
    from scripts.DFG.dfg_v2.experiment.local_dev import timing_summary
    result,plan,job,path,raw,receipt_path=resource_result
    plan["resource_policy"]=copy.deepcopy(LOCAL_DEV_POLICY)
    write_json(path,plan)
    receipt=read_json(receipt_path)
    receipt["policy"]=plan["resource_policy"]
    receipt["plan_sha256"]=sha256(path)
    write_json(receipt_path,receipt)
    resources=result["resources"]
    resources["resource_policy"]=plan["resource_policy"]
    resources["preflight"]=resource_plan._ref(receipt_path)
    sample=json.loads(raw.read_text())
    sample.update(free_mib=50,used_mib=4000,
        non_torch_residual_estimate_mib=3646,
        context_adjusted_residual_estimate_mib=3546)
    raw.write_text(json.dumps(sample)+"\n")
    resources.update(raw_samples_sha256=sha256(raw),minimum_free_mib=50,
        non_torch_residual_estimate_mib=3546,
        context_adjusted_residual_estimate_mib=3446,
        memory_tight=True,possible_memory_spill=True)
    rows=[dict(epoch=i,seconds=s) for i,s in enumerate([1,1,1,3])]
    history=tmp_path/"history.jsonl"
    history.write_text("".join(json.dumps(row)+"\n" for row in rows))
    resources["epoch_timing"]=timing_summary(rows)
    result.update(memory_tight=True,possible_memory_spill=True)
    return result,plan,job,path,raw,receipt_path,history


def test_local_low_free_success_requires_consistent_raw_resource_evidence(local_result):
    result,plan,job,path,raw,receipt,history=local_result
    resource_plan.validate_resource_result(result,plan,job,path,history_path=history)


@pytest.mark.parametrize("damage",["flag","result_flag","timing","history"])
def test_local_forged_advisory_and_timing_rejected(local_result,damage):
    import json
    result,plan,job,path,raw,receipt,history=local_result
    if damage=="flag":
        result["resources"]["memory_tight"]=False
    elif damage=="result_flag":
        result["possible_memory_spill"]=False
    elif damage=="timing":
        result["resources"]["epoch_timing"]["epoch_seconds"][-1]=1
    else:
        rows=[json.loads(line) for line in history.read_text().splitlines()]
        rows[-1]["seconds"]=1
        history.write_text("".join(json.dumps(row)+"\n" for row in rows))
    with pytest.raises(ValueError):
        resource_plan.validate_resource_result(result,plan,job,path,history_path=history)
