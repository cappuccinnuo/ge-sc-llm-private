"""Prompt 8H final-resource cache and explicit amendment regression tests."""
import copy,json
from pathlib import Path
import pytest
from scripts.DFG.dfg_v2.tests.test_acceptance_cache import fixture_case,dump,ref,_rebind_case
from scripts.DFG.dfg_v2.experiment import acceptance_cache as old
from scripts.DFG.dfg_v2.benchmark_v2 import acceptance_cache as new
from scripts.DFG.dfg_v2.benchmark_v2 import runtime_amendment as amendment
from scripts.DFG.dfg_v2.benchmark_v2.protocol import PROTOCOL_NAME

def final_case(root):
    c=fixture_case(root)
    plan=json.loads(c["plan"].read_text());plan["protocol"]=PROTOCOL_NAME;dump(c["plan"],plan)
    final=json.loads((c["attempt"]/"result.json").read_text())
    with c["raw"].open("a") as f:f.write('{"index": 1}\n')
    final["resources"]["raw_samples_sha256"]=old._sha(c["raw"])
    dump(c["attempt"]/"final_result.json",final)
    _rebind_case(c,[c["attempt"]/"final_result.json"])
    return c

def create(root,c):
    return new.create_cache(root/"cache",c["plan"],c["job"],c["attempt"],c["full"],"test-v1")

def verify(anchor,c):
    return new.verify_cache(anchor,expected_seal_sha=anchor["sha256"],plan_path=c["plan"],
        job=c["job"],attempt=c["attempt"],full_verify=c["full"],acceptance_version="test-v1")

def test_async_sampler_final_record_fixes_old_failure_without_mutation(tmp_path):
    c=final_case(tmp_path)
    before={str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(ValueError,match="Conflicting or changing dependency"):
        old.create_cache(tmp_path/"old",c["plan"],c["job"],c["attempt"],c["full"],"test-v1")
    a=create(tmp_path,c)
    assert verify(a,c)==c["accepted"]
    assert c["calls"]==["full"]
    for p,value in before.items():assert Path(p).read_bytes()==value
    deps=json.loads(Path(a["path"]).read_text())["dependencies"]
    raw=next(d for d in deps if d["path"]==str(c["raw"].resolve()))
    assert raw["sha256"]==old._sha(c["raw"])
    assert {str(c["attempt"]/"result.json"),str(c["attempt"]/"final_result.json")}<={d["path"] for d in deps}

def test_original_protocol_dependency_behavior_exact(tmp_path):
    c=fixture_case(tmp_path)
    assert new._dependencies(c["plan"],c["attempt"])==old._dependencies(c["plan"],c["attempt"])
    assert verify(create(tmp_path,c),c)==c["accepted"]

@pytest.mark.parametrize("target",["result.json","final_result.json","raw","receipt.json","sample_00.pt"])
def test_no_evidence_can_be_silently_changed_after_cache(tmp_path,target):
    c=final_case(tmp_path);a=create(tmp_path,c)
    p=c["raw"] if target=="raw" else c["attempt"]/target
    p.write_bytes(p.read_bytes()+b" ")
    with pytest.raises(new.AcceptanceCacheChanged):verify(a,c)

@pytest.mark.parametrize("missing",["file","binding"])
def test_final_resource_result_required(tmp_path,missing):
    c=final_case(tmp_path)
    if missing=="file":(c["attempt"]/"final_result.json").unlink()
    else:
        p=c["attempt"]/"receipt.json";r=json.loads(p.read_text())
        del r["artifacts"]["final_result.json"];dump(p,r)
    with pytest.raises((ValueError,OSError)):create(tmp_path,c)

def amendment_case(root):
    before=root/"executor_before.py";before.write_text("original executor\n")
    plan_path=dump(root/"plan.json",dict(protocol=PROTOCOL_NAME,
        runtime={amendment.EXECUTION:old._sha(before),"numerical.py":"1"*64}))
    seal=dump(root/"plan.seal.json",dict(plan=ref(plan_path)))
    actual={amendment.EXECUTION:"2"*64,"numerical.py":"1"*64}
    actual.update({name:"3"*64 for name in amendment.ADDITIONS})
    approval=dump(root/"approval.json",dict(plan=ref(plan_path),approved=True,new_fits=169,reuse_existing_fit=True))
    proof=dump(root/"proof.json",dict(passed=True,runtime=actual,numeric_functions_unchanged=True))
    legacy=dump(root/"legacy_receipt.json",dict(success=True))
    doc=dict(version=amendment.VERSION,plan=ref(plan_path),plan_seal=ref(seal),runtime=actual,
        approval=ref(approval),proof=ref(proof),before_execution=ref(before),legacy_successes=[ref(legacy)])
    path=dump(root/amendment.NAME,doc);dump(path.with_name(path.stem+".seal.json"),dict(amendment=ref(path)))
    return plan_path,json.loads(plan_path.read_text()),actual,path,legacy

def test_amendment_binds_unchanged_plan_and_only_allowed_runtime(tmp_path):
    path,plan,actual,patch,legacy=amendment_case(tmp_path)
    original=path.read_bytes()
    assert amendment.amendment_ref(path,plan,actual)==ref(patch)
    assert path.read_bytes()==original
    assert amendment.amendment_ref(path,plan,plan["runtime"]) is None

@pytest.mark.parametrize("damage",["model","extra","missing","seal","approval","proof","legacy"])
def test_amendment_rejects_unapproved_change(tmp_path,damage):
    path,plan,actual,patch,legacy=amendment_case(tmp_path)
    if damage=="model":actual["numerical.py"]="9"*64
    elif damage=="extra":actual["unexpected.py"]="9"*64
    elif damage=="missing":del actual["numerical.py"]
    elif damage=="seal":patch.write_text(patch.read_text()+" ")
    elif damage=="legacy":legacy.write_text("changed")
    else:
        p=tmp_path/(damage+".json");d=json.loads(p.read_text())
        d["approved" if damage=="approval" else "passed"]=False;dump(p,d)
    with pytest.raises(ValueError):amendment.amendment_ref(path,plan,actual)

def test_first_success_reused_but_new_fit_requires_amendment(tmp_path,monkeypatch):
    path,plan,actual,patch,legacy=amendment_case(tmp_path)
    bound=amendment.amendment_ref(path,plan,actual)
    monkeypatch.setattr(amendment,"amendment_ref",lambda p,q:bound)
    amendment.verify_start(path,plan,{},legacy)
    other=dump(tmp_path/"new_receipt.json",dict(success=True,new=True))
    with pytest.raises(ValueError,match="lacks"):amendment.verify_start(path,plan,{},other)
    amendment.verify_start(path,plan,dict(benchmark_runtime_amendment=bound),other)
    with pytest.raises(ValueError,match="differs"):
        amendment.verify_start(path,plan,dict(benchmark_runtime_amendment=dict(bound,sha256="0"*64)),other)
