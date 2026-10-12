import pytest
from scripts.DFG.experiments.checkpoint import StopMonitor


def test_strict_best_is_independent_of_delta_patience():
    monitor = StopMonitor(patience=2, delta=0.01)
    assert monitor.step(1.0) == (True, False)
    assert monitor.step(0.995) == (True, False)
    assert monitor.step(0.994) == (True, True)
    assert monitor.best == 0.994


def test_significant_inner_improvement_resets_counter():
    monitor = StopMonitor(patience=2, delta=0.01)
    monitor.step(1.0)
    monitor.step(1.1)
    assert monitor.step(0.95) == (True, False)
    assert monitor.counter == 0


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_invalid_validation_loss_fails(value):
    with pytest.raises(ValueError):
        StopMonitor().step(value)
