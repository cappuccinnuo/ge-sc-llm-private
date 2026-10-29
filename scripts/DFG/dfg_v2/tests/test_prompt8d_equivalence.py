"""Exact scheduler-state acceptance: implementation identity, not object IDs."""
import copy
import pytest
import torch
from scripts.DFG.dfg_v2.benchmark_v2.equivalence import nested_equal, scheduler_equal

def make_scheduler():
    parameter=torch.nn.Parameter(torch.tensor([1.0],dtype=torch.float32))
    optimizer=torch.optim.Adam([parameter],lr=.001)
    scheduler=torch.optim.lr_scheduler.OneCycleLR(
        optimizer,max_lr=.001,total_steps=50,pct_start=.3,anneal_strategy="cos",
        cycle_momentum=True,base_momentum=.85,max_momentum=.95,div_factor=25,final_div_factor=10000)
    parameter.grad=torch.zeros_like(parameter)
    optimizer.step();scheduler.step()
    return scheduler

def test_distinct_real_onecycle_instances_accept_identical_implementation_and_numerics():
    left,right=make_scheduler(),make_scheduler()
    a,b=left.state_dict(),right.state_dict()
    callable_keys=[key for key in a if callable(a[key])]
    assert callable_keys  # Frozen torch1.8.1 stores anneal_func as a bound method.
    for key in callable_keys:
        assert a[key] is not b[key]
        assert a[key] != b[key]
        assert a[key].__func__ is b[key].__func__
    assert not nested_equal(a,b)  # Reproduces the rejected object-identity criterion.
    assert scheduler_equal(a,b)

@pytest.mark.parametrize("field",["last_epoch","_step_count","base_lrs","_last_lr","total_steps"])
def test_scheduler_numerical_state_change_rejected(field):
    a,b=make_scheduler().state_dict(),make_scheduler().state_dict()
    assert field in b
    if isinstance(b[field],list):
        b[field]=list(b[field]);b[field][0]+=1e-12
    else:b[field]+=1
    assert not scheduler_equal(a,b)

def test_scheduler_different_annealing_implementation_rejected():
    left,right=make_scheduler(),make_scheduler()
    a,b=left.state_dict(),right.state_dict()
    key=next(key for key in b if callable(b[key]))
    b[key]=right._annealing_linear
    assert a[key].__func__ is not b[key].__func__
    assert not scheduler_equal(a,b)

def test_scheduler_callable_removed_or_key_missing_rejected():
    a,b=make_scheduler().state_dict(),make_scheduler().state_dict()
    key=next(key for key in b if callable(b[key]))
    b[key]="cos"
    assert not scheduler_equal(a,b)
    b=dict(a);b.pop(key)
    assert not scheduler_equal(a,b)

def test_nested_tensor_changes_are_exact_not_tolerance_based():
    original={"weights":[torch.tensor([1.,2.],dtype=torch.float32)],"nested":{"step":1}}
    same=copy.deepcopy(original)
    assert nested_equal(original,same)
    different=copy.deepcopy(original)
    # Next representable float32 value: no tolerance may hide this change.
    different["weights"][0][0]=1.+torch.finfo(torch.float32).eps
    assert not nested_equal(original,different)
    assert not nested_equal(original,{"weights":[original["weights"][0].double()],"nested":{"step":1}})
    assert not nested_equal({"x":torch.zeros(2)},{"x":torch.zeros(1,2)})
    assert not nested_equal({"x":[1]},{"x":(1,)})
    assert not nested_equal({"x":1},{"x":True})
    assert not nested_equal({"x":1},{"y":1})

def test_review_existing_reuses_saved_runs_without_fit_and_retains_failed_record(tmp_path,monkeypatch):
    import json
    from scripts.DFG.dfg_v2.benchmark_v2 import equivalence as eq
    from scripts.DFG.experiments.common import tensor_digest
    from scripts.DFG.integration.io import sha256
    def json_file(path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
    existing=tmp_path/"prior";existing.mkdir()
    reference=tmp_path/"bound";reference.write_text("fixed")
    ref=dict(path=str(reference),sha256=sha256(reference))
    original_report=dict(passed=False,forward_bitwise=True,source_plan=ref,
                         feature_manifest=ref,identity_view=ref,acceptance_optimizer_steps=2,
                         formal_fits=0,checks={"scheduler_state_equal":False})
    json_file(existing/"equivalence.json",original_report)
    old_sha=sha256(existing/"equivalence.json")
    history=dict(epoch=0,lr=.0002,adam_beta1=.95,train_loss=.7,inner_val_loss=.6,
                 inner_val={"buggy_f1":50.},patience_counter=0,saved_best=True)
    for branch in ("original","bound_original_view"):
        directory=existing/branch;directory.mkdir()
        state={"weight":torch.tensor([1.],dtype=torch.float32)}
        payload=dict(state_dict=state,state_sha256=tensor_digest(state),
                     optimizer={"state":{},"param_groups":[]},
                     scheduler=make_scheduler().state_dict())
        torch.save(payload,str(directory/"last.pt"))
        json_file(directory/"result.json",{"checkpoint_sha256":{"last":sha256(directory/"last.pt")},
                                          "outer_test":{"best":{"buggy_f1":50.},"last":{"buggy_f1":50.}}})
        (directory/"history.jsonl").write_text(json.dumps(history)+"\n")
    def no_fit(*args,**kwargs):
        raise AssertionError("Review must not fit another model")
    monkeypatch.setattr(eq,"fit",no_fit)
    result=eq.review_existing(existing,tmp_path/"review")
    assert result["passed"] and result["extra_optimizer_steps"]==0
    assert result["scheduler_state_equal"] and result["optimizer_state_equal"]
    assert result["acceptance_optimizer_steps"]==2 and result["formal_fits"]==0
    assert sha256(existing/"equivalence.json")==old_sha
    # Integrity checks reject a changed saved checkpoint before any new result.
    checkpoint=existing/"original/last.pt"
    checkpoint.write_bytes(checkpoint.read_bytes()+b"tamper")
    with pytest.raises(ValueError,match="checkpoint changed"):
        eq.review_existing(existing,tmp_path/"bad_review")
