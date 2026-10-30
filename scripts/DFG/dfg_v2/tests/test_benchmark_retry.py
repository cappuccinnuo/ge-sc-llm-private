"""Explicit user-approved retry preserves old evidence and numerical training."""
import ast
import json
from pathlib import Path
import pytest
from scripts.DFG.dfg_v2.benchmark_v2 import retry
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
from scripts.DFG.dfg_v2.benchmark_v2.acceptance_cache import _attempt_inventory

def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))
    return path

def case(root):
    plan=dump(root/"plan.json",{})
    seal=dump(root/"plan.seal.json",{"plan":ref(plan)})
    folder=root/"runs"/"node"/"fold_7"/"seed_1"/"G3"
    first=folder/"attempt_001"
    evidence=dump(first/"history.jsonl",{"epoch":31})
    start=dump(folder/"attempt_001.started.json",{"old":True})
    job=dict(task_id="node",fold=7,seed=1,profile="G3")
    incident=dump(root/"interruption.json",dict(job=job,old_attempt=str(first),files=[ref(evidence),ref(start)]))
    approval=dump(root/"approval.json",dict(plan=ref(plan),approved=True,retry_job=job,retry_attempt="attempt_002",
        restart_from_sealed_initial=True,automatic_retry=False,reuse_successes=71,new_fits=99,interruption=ref(incident)))
    before={}
    for i,name in enumerate(sorted(retry.CHANGED)):
        p=root/("before_"+str(i));p.write_text(name);before[name]=ref(p)
    prior_runtime={name:r["sha256"] for name,r in before.items()}
    prior_runtime["numerical.py"]="0"*64
    parent=dump(root/"parent.json",dict(runtime=prior_runtime))
    actual=dict(prior_runtime)
    actual.update({name:"1"*64 for name in retry.CHANGED})
    actual.update({name:"2"*64 for name in retry.ADDED})
    prior=[]
    for i in range(71):prior.append(ref(dump(root/"receipts"/str(i),dict(i=i))))
    successes=dump(root/"successes.json",dict(passed=True,count=71,receipts=prior))
    proof=dump(root/"proof.json",dict(passed=True,runtime=actual,numeric_functions_unchanged=True))
    doc=dict(version=retry.VERSION,plan=ref(plan),plan_seal=ref(seal),runtime=actual,
        parent_amendment=ref(parent),before_sources=before,approval=ref(approval),
        proof=ref(proof),prior_successes=ref(successes))
    patch=dump(root/retry.NAME,doc);dump(patch.with_name(patch.stem+".seal.json"),dict(amendment=ref(patch)))
    def parent_check(p,q,a):
        assert a==prior_runtime
        return ref(parent)
    return dict(plan=plan,folder=folder,job=job,patch=patch,actual=actual,parent_check=parent_check,first=first,approval=approval)

def test_retry_retains_original_bytes_and_is_only_fresh_002(tmp_path):
    c=case(tmp_path)
    before={p:p.read_bytes() for p in c["folder"].rglob("*") if p.is_file()}
    assert retry.successful_attempt(c["folder"]) is None
    assert retry.next_attempt(c["plan"],c["job"],c["folder"])==c["folder"]/"attempt_002"
    assert retry.verify_resume(c["plan"],{},c["actual"],c["parent_check"])==ref(c["patch"])
    assert all(p.read_bytes()==v for p,v in before.items())

@pytest.mark.parametrize("damage",["wrong_job","no_approval","tampered_history","started_002","partial_002","third_start","seal"])
def test_retry_refuses_unapproved_or_repeated_attempt(tmp_path,damage):
    c=case(tmp_path)
    if damage=="wrong_job":c["job"]=dict(c["job"],fold=8)
    elif damage=="no_approval":
        x=json.loads(c["approval"].read_text());x["approved"]=False;dump(c["approval"],x)
    elif damage=="tampered_history":(c["first"]/"history.jsonl").write_text("tamper")
    elif damage=="started_002":dump(c["folder"]/"attempt_002.started.json",{})
    elif damage=="partial_002":dump(c["folder"]/"attempt_002/partial.json",{})
    elif damage=="third_start":dump(c["folder"]/"attempt_003.started.json",{})
    else:c["patch"].write_text(c["patch"].read_text()+" ")
    with pytest.raises((ValueError,RuntimeError)):retry.next_attempt(c["plan"],c["job"],c["folder"])

def test_unique_successful_retry_is_selected_and_inventory_keeps_failure(tmp_path):
    c=case(tmp_path);second=c["folder"]/"attempt_002"
    dump(second/"receipt.json",dict(success=True));dump(c["folder"]/"attempt_002.started.json",{})
    assert retry.successful_attempt(c["folder"])==second
    retry.validate_retry_receipt(c["plan"],c["job"],second)
    records=_attempt_inventory(second)
    assert {Path(x["path"]).name for x in records}=={"receipt.json","attempt_001.started.json","attempt_002.started.json"}
    dump(c["folder"]/"attempt_003.started.json",{})
    with pytest.raises(RuntimeError):retry.successful_attempt(c["folder"])

def test_duplicate_success_is_rejected(tmp_path):
    c=case(tmp_path)
    for n in ["attempt_001","attempt_002"]:dump(c["folder"]/n/"receipt.json",{})
    with pytest.raises(ValueError):retry.successful_attempt(c["folder"])

@pytest.mark.parametrize("damage",["numeric","extra","source","proof","success","approval","parent"])
def test_resume_cannot_change_computation_or_history(tmp_path,damage):
    c=case(tmp_path)
    if damage=="numeric":c["actual"]["numerical.py"]="9"*64
    elif damage=="extra":c["actual"]["unrelated.py"]="9"*64
    else:
        doc=json.loads(c["patch"].read_text())
        target={"source":next(iter(doc["before_sources"].values()))["path"],
            "proof":doc["proof"]["path"],"success":str(tmp_path/"receipts"/"1"),
            "approval":doc["approval"]["path"],"parent":doc["parent_amendment"]["path"]}[damage]
        p=Path(target);p.write_text(p.read_text()+" ")
    with pytest.raises(ValueError):retry.verify_resume(c["plan"],{},c["actual"],c["parent_check"])

def test_fresh_jobs_keep_attempt001_and_orphan_artifact_blocks(tmp_path):
    p=dump(tmp_path/"plan.json",{})
    folder=tmp_path/"new"
    assert retry.next_attempt(p,{},folder)==folder/"attempt_001"
    dump(folder/"attempt_001/partial.json",{})
    with pytest.raises(RuntimeError):retry.next_attempt(p,{},folder)

def test_fit_numeric_try_body_and_model_functions_unchanged():
    import hashlib
    root=Path(__file__).resolve().parents[4]
    current=root/"scripts/DFG/dfg_v2/benchmark_v2/execution.py"
    tree={n.name:n for n in ast.parse(current.read_text()).body if isinstance(n,ast.FunctionDef)}
    expected={'construct': 'e2a7c08d71d4aaab3a118515e3fc2885f7741e9562c021db15bf4e33060797cc', 'binding_parts': '555714d77d06d6374bd0c7abba25dee9845883fbac8a5ce99b9802493abc408f', 'prepared': 'cba72bb9929fb19bbc0397e69bf55c3082b8ee05a2d01ff3ce06c64f5411040a', 'fit_numeric_try': '6987c275858a6dc5b8178e2df709316ffa4adf116f9b32266acc0e236bf19435'}
    digest=lambda n:hashlib.sha256(ast.dump(n).encode()).hexdigest()
    for name in ["construct","binding_parts","prepared"]:assert digest(tree[name])==expected[name]
    numeric=next(n for n in tree["fit_one"].body if isinstance(n,ast.Try))
    assert digest(numeric)==expected["fit_numeric_try"]

def test_retry_receipt_cannot_belong_to_other_job(tmp_path):
    c=case(tmp_path)
    with pytest.raises(ValueError):retry.validate_retry_receipt(c["plan"],dict(c["job"],fold=8),c["folder"]/"attempt_002")
    with pytest.raises(ValueError):retry.validate_retry_receipt(c["plan"],c["job"],c["folder"]/"attempt_003")

def test_historical_start_binding_requires_listed_receipt(tmp_path,monkeypatch):
    from scripts.DFG.dfg_v2.benchmark_v2 import runtime_amendment
    c=case(tmp_path);doc=json.loads(c["patch"].read_text())
    monkeypatch.setattr(runtime_amendment,"amendment_ref",lambda p,q:ref(c["patch"]))
    prior=Path(json.loads(Path(doc["prior_successes"]["path"]).read_text())["receipts"][0]["path"])
    for value in [None,doc["parent_amendment"]]:
        runtime_amendment.verify_start(c["plan"],{},dict(benchmark_runtime_amendment=value),prior)
    other=dump(tmp_path/"unlisted.json",{})
    with pytest.raises(ValueError):runtime_amendment.verify_start(c["plan"],{},dict(benchmark_runtime_amendment=doc["parent_amendment"]),other)
    runtime_amendment.verify_start(c["plan"],{},dict(benchmark_runtime_amendment=ref(c["patch"])),other)
