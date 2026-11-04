"""Regression for diagnostic-only torch1.8 telemetry and output safety."""
import pytest
from . import run_diagnostics as runner

def test_cuda_initialized_before_reset(monkeypatch):
    calls=[]
    monkeypatch.setattr(runner.torch.cuda,'init',lambda:calls.append('init'))
    def reset(device):
        assert calls==['init']
        calls.append(('reset',device))
    monkeypatch.setattr(runner.torch.cuda,'reset_peak_memory_stats',reset)
    runner.reset_device_statistics('cuda:0')
    assert calls==['init',('reset','cuda:0')]

@pytest.mark.parametrize('name',['../pilot','/tmp/run','pilot/v2',''])
def test_output_path_rejects_escape(name):
    with pytest.raises(ValueError):runner.stage_name(name)

def test_output_name_accepts_independent_attempt():
    assert runner.stage_name('pilot_v2')=='pilot_v2'
