"""NS-P4b regression: node-type-specific local modality dropout."""
import torch
from scripts.node_sem.adapter import NodeSemAdapter
from scripts.node_sem.tests.test_fusion import spec
from scripts.DFG.dfg_v2.experiment.init import parameter_seed


def test_seed_explicitly_binds_node_type():
    a=NodeSemAdapter(spec(dropout=.1),'if')
    actual=a.reset_dropout(1010000,'reentrancy_node',0,'G3R')
    assert actual==parameter_seed(1010000,'modality_dropout',
        ['reentrancy_node',0,'G3R',a.spec_digest,'if'])


def test_different_types_get_different_reproducible_masks_without_global_rng():
    a=NodeSemAdapter(spec(dropout=.1),'if')
    b=NodeSemAdapter(spec(dropout=.1),'return')
    clone=NodeSemAdapter(spec(dropout=.1),'if')
    for model in (a,b,clone):model.reset_dropout(1010000,'reentrancy_node',0,'G3R')
    state=torch.get_rng_state().clone();x=torch.ones(4096,3)
    for count in range(3):
        left=a._drop_presence(x);right=b._drop_presence(x);repeat=clone._drop_presence(x)
        assert torch.equal(left,repeat)
        assert not torch.equal(left,right)
        assert a.forward_count==b.forward_count==clone.forward_count==count+1
        assert torch.equal(state,torch.get_rng_state())
    a.eval();before=a.forward_count
    assert torch.equal(a._drop_presence(x),x) and a.forward_count==before
    assert torch.equal(state,torch.get_rng_state())


import copy
import pytest
from scripts.node_sem.p4b_acceptance import matrix,validate_matrix,logits_comparison,compare_resources,history_row,gate_checks,unchanged_history


def minimal_plan():
    return dict(formal_training_authorized=False,jobs=[dict(actual_device=d,task_id=t,name=n,profile='G0' if n=='S4-noG' else 'G3R',fold=0,seed=1) for d,t,n in matrix()])


def test_fixed_matrix():
    p=minimal_plan();assert validate_matrix(p)
    assert len(p['jobs'])==14
    assert sum(j['actual_device']=='cpu' for j in p['jobs'])==6
    assert sum(j['actual_device']=='gpu' and j['task_id']=='reentrancy_node' for j in p['jobs'])==6


@pytest.mark.parametrize('damage',['duplicate','missing','fold','seed','profile','formal'])
def test_matrix_rejects_drift(damage):
    p=minimal_plan()
    if damage=='duplicate':p['jobs'][1]=copy.deepcopy(p['jobs'][0])
    elif damage=='missing':p['jobs'].pop()
    elif damage=='formal':p['formal_training_authorized']=True
    else:p['jobs'][0][damage]={'fold':1,'seed':2,'profile':'G0'}[damage]
    with pytest.raises(ValueError):validate_matrix(p)


def test_parity_reports_near_zero_elementwise_without_relaxing_absolute_gate():
    r=logits_comparison(torch.tensor([1.,0.]),torch.tensor([1.,1e-9]))
    assert r['passed'] and r['max_elementwise_relative']==1.
    assert not logits_comparison(torch.tensor([100.]),torch.tensor([100.01]))['passed']
    assert not logits_comparison(torch.tensor([1e-7]),torch.tensor([2e-7]))['passed']
    assert logits_comparison(torch.zeros(2),torch.zeros(2))['passed']


@pytest.mark.parametrize('b',[torch.tensor([float('nan')]),torch.ones(2),torch.tensor([float('inf')])])
def test_parity_rejects_invalid(b):
    with pytest.raises(ValueError):logits_comparison(torch.ones(1),b)


def test_low_free_memory_is_advisory_not_failure():
    old=dict(peak_allocated_mib=100.,peak_reserved_mib=200.,minimum_free_mib=50.)
    now=dict(peak_allocated_mib=101.,peak_reserved_mib=250.,minimum_free_mib=1.)
    assert not compare_resources(now,old)['significant_memory_increase']
    now['peak_reserved_mib']=251.
    assert compare_resources(now,old)['significant_memory_increase']
    assert compare_resources(now,old)['advisory_only']


def test_history_requires_exact_unique_identity(tmp_path):
    p=tmp_path/'resources.csv'
    row='reentrancy_node,0,1,G3R,1,2,3\n'
    p.write_text('task_id,fold,seed,profile,peak_allocated_mib,peak_reserved_mib,minimum_free_mib\n'+row)
    j=dict(task_id='reentrancy_node',fold=0,seed=1,profile='G3R')
    assert history_row(p,j)['peak_reserved_mib']==2.
    p.write_text(p.read_text()+row)
    with pytest.raises(ValueError):history_row(p,j)


def test_gate_storage_and_normalization():
    class A:pass
    m=A();a=A();a.ntype='if';a.last_gates=torch.tensor([[.4,.6],[0.,0.]])
    m.adapt_ws=[a];assert gate_checks(m)[0]['active_rows']==1
    a.last_gates=torch.tensor([[.4,.5]])
    with pytest.raises(ValueError):gate_checks(m)


@pytest.mark.parametrize('damage',[False,True])
def test_previous_attempt_preserved(tmp_path,monkeypatch,damage):
    import hashlib,json
    from scripts.node_sem import p4b_acceptance as driver
    monkeypatch.setattr(driver,'ROOT',tmp_path)
    monkeypatch.setattr(driver,'ATTEMPT',tmp_path)
    p=tmp_path/'historical.txt';p.write_bytes(b'old evidence')
    snapshot=dict(previous_attempt_files=[dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())])
    (tmp_path/'before.json').write_text(json.dumps(snapshot))
    if damage:
        p.write_bytes(b'changed evidence')
        with pytest.raises(ValueError):unchanged_history()
    else:assert unchanged_history()==1



def test_phase_log_appends_without_overwriting_prior_records(tmp_path,monkeypatch):
    import json
    from scripts.node_sem import p4b_acceptance as driver
    monkeypatch.setattr(driver,'OUT',tmp_path)
    job=minimal_plan()['jobs'][0]
    record=driver.phase_writer(job)
    record('construct_and_validate_initial')
    record('frozen_fit_train_validation_checkpoint_reload')
    lines=(tmp_path/(driver.identity(job)+'.phases.jsonl')).read_text().splitlines()
    assert [json.loads(l)['phase'] for l in lines]==['construct_and_validate_initial','frozen_fit_train_validation_checkpoint_reload']



@pytest.mark.parametrize('raise_error',[False,True])
def test_parity_precision_scope_restores_global_flags(raise_error):
    from scripts.node_sem.p4b_acceptance import full_fp32_eval,precision_flags
    before=precision_flags()
    try:
        with full_fp32_eval():
            assert precision_flags()==dict(matmul=False,cudnn=False)
            if raise_error:raise RuntimeError('synthetic eval error')
    except RuntimeError:
        assert raise_error
    assert precision_flags()==before
