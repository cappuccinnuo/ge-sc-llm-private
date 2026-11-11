"""EP7 authorization, immutable-runtime and diagnostic-scope regression tests."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
from scripts.edge_sem import execution as ex,runtime
from scripts.edge_sem.io import ref,read
from scripts.edge_sem.protocol_p2 import DECISIONS,require_decisions
from scripts.edge_sem.support import edge_gradient_audit
from scripts.edge_sem.hgt_edge import EdgeAttrEncoder
from scripts.edge_sem.tests.test_hgt_edge import sample
from scripts.edge_sem.tests.test_execution_core import setup_case,CONFIG,LABELS
from scripts.edge_sem.pilot import train_only


def put(path,value):
    path.write_text(json.dumps(value),encoding="utf8")


def test_decisions_require_explicit_three_choices_and_seal(tmp_path):
    path=tmp_path/"decisions.json"
    value=dict(date="2026-11-11",user_request="synthetic approval only",
        decisions={k:dict(status="confirmed",value=v) for k,v in DECISIONS.items()})
    put(path,value);put(path.with_suffix(".seal.json"),dict(decisions=ref(path)))
    require_decisions(path)
    for field in DECISIONS:
        bad=copy.deepcopy(value);bad["decisions"][field]["status"]="pending"
        put(path,bad);put(path.with_suffix(".seal.json"),dict(decisions=ref(path)))
        with pytest.raises(ValueError):require_decisions(path)


def test_runtime_archive_uses_sealed_snapshot_not_current_code(tmp_path,monkeypatch):
    snap=tmp_path/"runtime.txt";snap.write_text("sealed source",encoding="utf8")
    name="scripts/edge_sem/future_runtime.py"
    plan=dict(runtime={name:ref(snap)["sha256"]},runtime_snapshots={name:ref(snap)})
    monkeypatch.setattr(runtime,"runtime_refs",lambda:{name:"changed"})
    runtime.verify_snapshot(plan,False)
    with pytest.raises(ValueError):runtime.verify_snapshot(plan,True)
    snap.write_text("damaged",encoding="utf8")
    with pytest.raises(ValueError):runtime.verify_snapshot(plan,False)


def test_success_is_reused_and_duplicate_receipts_rejected(tmp_path,monkeypatch):
    job=dict(task_id="reentrancy_node",fold=0,seed=1,edge_profile="G3R")
    path=tmp_path/"plan.json";put(path,{})
    plan=dict(jobs=[job])
    folder=ex.job_directory(tmp_path,job);attempt=folder/"attempt_001";attempt.mkdir(parents=True)
    put(attempt/"receipt.json",{})
    called=[]
    monkeypatch.setattr(ex,"load",lambda p:plan)
    monkeypatch.setattr(ex,"authorized",lambda *a,**k:{})
    monkeypatch.setattr(ex,"verify_one",lambda *a,**k:called.append("verified"))
    monkeypatch.setattr(ex,"construct",lambda *a,**k:pytest.fail("Successful fit was reconstructed"))
    assert ex.fit_one(path,job)=="reused" and called==["verified"]
    (folder/"attempt_002").mkdir();put(folder/"attempt_002/receipt.json",{})
    with pytest.raises(ValueError):ex._successful(folder)


def test_failed_attempt_is_retained_and_never_auto_retried(tmp_path):
    job=dict(task_id="reentrancy_node",fold=0,seed=1,edge_profile="G3R")
    folder=ex.job_directory(tmp_path,job);folder.mkdir(parents=True)
    failed=folder/"attempt_001.failure.json";put(failed,dict(error="synthetic"))
    with pytest.raises(RuntimeError):ex._next_attempt(tmp_path/"plan.json",job,folder)
    assert read(failed)==dict(error="synthetic")


def test_edge_audit_initial_zero_encoder_and_post_update_nonzero():
    graph,h,parent,layer=sample()
    encoder=EdgeAttrEncoder(9,dropout=0)
    model=torch.nn.Module();model.gcs=torch.nn.ModuleList([layer]);model.edge_encoder=encoder
    attrs={c:torch.randint(0,2,(graph.num_edges(c),9),dtype=torch.uint8) for c in graph.canonical_etypes}
    weights={t:torch.randn_like(h[t]) for t in h}
    optimizer=torch.optim.Adam(model.parameters(),lr=.001)
    def step():
        optimizer.zero_grad()
        psi={c:encoder(v) for c,v in attrs.items()}
        out=layer(graph,h,psi)
        sum((v*weights[t]).sum() for t,v in out.items()).backward()
        return edge_gradient_audit(model)
    first=step()
    assert first["zero_encoder_expected"] is True and first["encoder_gradient_l1"]==0
    optimizer.step()
    second=step()
    assert second["zero_encoder_expected"] is False and second["encoder_gradient_l1"]>0


def test_train_only_entry_has_no_heldout_parts_or_metrics(tmp_path):
    _,model,binding,parts,counts=setup_case(tmp_path/"inputs")
    class Resource:
        def check(self):pass
        def summary(self):return dict(device="cpu")
    # Only one part is passed; a heldout target/forward cannot be accessed.
    result=train_only(model,parts["inner_train"],LABELS,CONFIG,counts,tmp_path/"probe",Resource(),1,False)
    assert result["validation_or_test_supervision_constructed"] is False
    assert result["validation_or_test_scored"] is False and result["best_selected"] is False
    history=[json.loads(line) for line in (tmp_path/"probe/history.jsonl").read_text().splitlines()]
    assert len(history)==1
    assert not any(k in history[0] for k in ("inner_val","outer_test","train_loss","best"))
    assert not list((tmp_path/"probe").glob("*.pt"))
