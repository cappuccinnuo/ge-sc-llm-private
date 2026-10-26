"""Prompt 7b.1 validation mechanics, including honest strict-gate failures.

Passing these tests does not accept the numerical experiment: the real tiny
float64 comparisons fail the requested relative gate on a near-zero key bias.
Tests require that rejection to propagate; they do not xfail or change the gate.
No optimizer, real-data fit, GPU execution, or historical artifact is involved.
"""

import pytest
import torch

from scripts.DFG.dfg_v2.experiment.precision_validation import (
    forward_difference,
    small_case,
    strict_gradient_difference,
)


def _double(values):
    return torch.tensor(values, dtype=torch.float64)


def test_gradient_identical_values_have_zero_error():
    value = _double([1., -2., 0.])
    result = strict_gradient_difference(value, value.clone())
    assert result['passed']
    assert result['maximum_absolute_difference'] == 0.
    assert result['reference_scale'] == 2.
    assert result['denominator'] == 2.
    assert result['relative_difference'] == 0.


def test_gradient_both_missing_are_explicitly_recorded():
    result = strict_gradient_difference(None, None)
    assert result['passed']
    assert result['none_old'] is True
    assert result['none_new'] is True


@pytest.mark.parametrize('missing_old', [False, True])
def test_gradient_one_missing_is_rejected(missing_old):
    old, new = (None, _double([0.])) if missing_old else (_double([0.]), None)
    result = strict_gradient_difference(old, new)
    assert not result['passed']
    assert result['none_old'] is missing_old
    assert result['none_new'] is not missing_old


def test_gradient_float32_is_not_silently_cast():
    with pytest.raises(ValueError):
        strict_gradient_difference(torch.zeros(2, dtype=torch.float32), _double([0., 0.]))


def test_gradient_different_shapes_are_rejected():
    with pytest.raises(ValueError):
        strict_gradient_difference(_double([1., 2.]), _double([[1., 2.]]))


@pytest.mark.parametrize('nonfinite', [float('nan'), float('inf'), -float('inf')])
def test_gradient_nonfinite_values_cannot_pass(nonfinite):
    result = strict_gradient_difference(_double([0.]), _double([nonfinite]))
    assert not result['passed']
    assert result['nonfinite'] is True


def test_gradient_denominator_floor_and_reference_side_are_literal():
    zero = _double([0.])
    accepted = strict_gradient_difference(zero, _double([4e-41]))
    rejected = strict_gradient_difference(zero, _double([2e-40]))
    assert accepted['reference_scale'] == 0.
    assert accepted['denominator'] == 1e-30
    assert accepted['relative_difference'] == pytest.approx(4e-11)
    assert accepted['passed']
    assert rejected['relative_difference'] == pytest.approx(2e-10)
    assert not rejected['passed']
    # The prompt names the reference gradient, not the larger of both norms.
    asymmetric = strict_gradient_difference(_double([1.]), _double([3.]))
    assert asymmetric['denominator'] == 1.
    assert asymmetric['relative_difference'] == 2.


def test_gradient_exact_threshold_is_inclusive_and_not_relaxed():
    old = _double([1e10])
    boundary = strict_gradient_difference(old, _double([1e10 + 1.]))
    outside = strict_gradient_difference(old, _double([1e10 + 2.]))
    assert boundary['relative_difference'] == 1e-10
    assert boundary['passed']
    assert outside['relative_difference'] == 2e-10
    assert not outside['passed']


def test_forward_identical_values_are_bitwise_equal():
    value = _double([[1., -2.], [0., 3.]])
    result = forward_difference(value, value.clone())
    assert result['passed']
    assert result['bitwise_equal']
    assert result['maximum_absolute_difference'] == 0.


def test_forward_exact_threshold_is_inclusive_and_separate_from_bitwise():
    zero = _double([0.])
    boundary = forward_difference(zero, _double([1e-12]))
    outside = forward_difference(zero, _double([2e-12]))
    assert boundary['maximum_absolute_difference'] == 1e-12
    assert boundary['passed']
    assert not boundary['bitwise_equal']
    assert not outside['passed']


def test_forward_float32_is_not_silently_cast():
    with pytest.raises(ValueError):
        forward_difference(torch.zeros(2, dtype=torch.float32), _double([0., 0.]))


def test_forward_different_shapes_are_rejected():
    with pytest.raises(ValueError):
        forward_difference(_double([1., 2.]), _double([[1., 2.]]))


@pytest.mark.parametrize('nonfinite', [float('nan'), float('inf'), -float('inf')])
def test_forward_nonfinite_values_cannot_pass(nonfinite):
    result = forward_difference(_double([0.]), _double([nonfinite]))
    assert not result['passed']


@pytest.mark.parametrize('reducer', ['mean', 'nonempty_mean'])
@pytest.mark.parametrize('use_norm', [False, True])
def test_real_tiny_probe_propagates_near_zero_gradient_rejection(reducer, use_norm):
    result = small_case(reducer=reducer, use_norm=use_norm)
    assert result['all_required_ops_float64']
    assert not result['negative_control']
    assert result['forward_passed']
    assert all(item['bitwise_equal'] for item in result['forwards'].values())
    assert all(item['maximum_absolute_difference'] == 0.
               for item in result['forwards'].values())
    assert result['missing_parameter_gradients'] == []
    failed = {name: item for name, item in result['gradients'].items()
              if not item['passed']}
    assert set(failed) == {'k_linears.0.bias'}
    bias = failed['k_linears.0.bias']
    assert bias['reference_scale'] < 1e-15
    assert bias['maximum_absolute_difference'] < 1e-15
    assert bias['relative_difference'] > 1e-10
    assert not result['gradient_passed']
    assert result['status'] == 'failed_static_gate'
    assert result['maximum_absolute_gradient_difference'] < 1e-12


@pytest.mark.parametrize('reducer', ['mean', 'nonempty_mean'])
def test_omitted_relation_is_detected_beyond_near_zero_bias(reducer):
    result = small_case(reducer=reducer, use_norm=True, drop_relation=True)
    assert result['negative_control']
    assert result['all_required_ops_float64']
    assert not result['forward_passed']
    assert any(not item['passed'] for item in result['forwards'].values())
    assert not result['gradient_passed']
    assert any(not item['passed'] and not name.endswith('.bias')
               for name, item in result['gradients'].items())
    assert result['status'] == 'failed_static_gate'


def test_preflight_existing_directory_is_never_overwritten(tmp_path, monkeypatch):
    from scripts.DFG.dfg_v2.experiment import precision_validation as validation
    destination = tmp_path / 'existing'
    destination.mkdir()
    sentinel = destination / 'acceptance.json'
    sentinel.write_text('historical evidence', encoding='utf8')
    calls = []
    monkeypatch.setattr(validation, 'small_case', lambda **kw: calls.append(kw))
    with pytest.raises(FileExistsError):
        validation.run_preflight(destination)
    assert sentinel.read_text(encoding='utf8') == 'historical evidence'
    assert calls == []


def test_preflight_first_failure_is_saved_and_blocks_further_cases(tmp_path, monkeypatch):
    import json
    from scripts.DFG.dfg_v2.experiment import precision_validation as validation
    calls = []
    def failed_case(**kwargs):
        calls.append(kwargs)
        return {'status': 'failed_static_gate', 'failure_evidence': 'synthetic unit test'}
    monkeypatch.setattr(validation, 'small_case', failed_case)
    destination = tmp_path / 'failed'
    with pytest.raises(AssertionError, match='strict float64'):
        validation.run_preflight(destination)
    report = json.loads((destination / 'acceptance.json').read_text())
    case = json.loads((destination / 'mean.json').read_text())
    assert calls == [{'reducer': 'mean', 'use_norm': True}]
    assert report['status'] == case['status'] == 'failed_static_gate'
    assert case['failure_evidence'] == 'synthetic unit test'
    assert report['fits'] == report['real_data_cases'] == report['gpu_runs'] == 0
    assert report['stopped_before'] == 'real_data_float64_and_all_gpu_stages'
    assert not (destination / 'nonempty_mean.json').exists()


def test_preflight_execution_error_is_preserved_without_acceptance(tmp_path, monkeypatch):
    import json
    from scripts.DFG.dfg_v2.experiment import precision_validation as validation
    def unsupported_operation(**kwargs):
        raise RuntimeError('synthetic unsupported float64 operation')
    monkeypatch.setattr(validation, 'small_case', unsupported_operation)
    destination = tmp_path / 'error'
    with pytest.raises(RuntimeError, match='unsupported float64'):
        validation.run_preflight(destination)
    report = json.loads((destination / 'acceptance.json').read_text())
    assert report['status'] == 'execution_error'
    assert report['error_type'] == 'RuntimeError'
    assert report['error'] == 'synthetic unsupported float64 operation'
    assert report['cases'] == []
    assert report['fits'] == report['real_data_cases'] == report['gpu_runs'] == 0
