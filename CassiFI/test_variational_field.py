from __future__ import annotations

import math

import pytest
import torch

from cassi_variational_field import VariationalField


@pytest.fixture
def learned():
    torch.set_num_threads(1)
    model = VariationalField(3, ((0, 1), (1, 2)))
    field = model.initial_state()
    for value in (1.0, -1.0) * 6:
        field = model.observe(field, 0, [value, 1.5 * value], exposure=0.5)
        field = model.observe(field, 1, [value, -0.75 * value], exposure=0.5)
    return model, field


def test_energy_gradient_matches_the_shared_precision(learned):
    model, field = learned
    point = torch.tensor([0.4, -0.2, 0.3], dtype=torch.float64)
    gradient = model.precision(field) @ point
    numeric = torch.empty_like(point)
    epsilon = 1e-6
    for index in range(model.dimension):
        plus, minus = point.clone(), point.clone()
        plus[index] += epsilon
        minus[index] -= epsilon
        numeric[index] = (
            model.energy(model.clamp(field, range(model.dimension), plus))
            - model.energy(model.clamp(field, range(model.dimension), minus))
        ) / (2 * epsilon)
    torch.testing.assert_close(numeric, gradient, rtol=1e-8, atol=1e-6)


def test_implicit_step_obeys_exact_energy_decrement_for_a_large_step(learned):
    model, field = learned
    before = model.clamp(field, (0, 1, 2), [0.6, -0.5, 0.3])
    duration = 1000.0
    after = model.relax(before, (0,), [0.6], duration=duration)
    delta = model.workspace(after)[1:] - model.workspace(before)[1:]
    hessian = model.precision(before)[1:, 1:]
    predicted_drop = float(delta @ delta / duration + 0.5 * delta @ hessian @ delta)
    measured_drop = model.energy(before) - model.energy(after)
    assert measured_drop > 0
    assert measured_drop == pytest.approx(predicted_drop, rel=1e-9, abs=1e-8)
    assert float(model.workspace(after)[0]) == pytest.approx(0.6, abs=1e-15)
    precision = model.precision(before)
    free = model.workspace(before)[1:]
    explicit = free - duration * (hessian @ free + precision[1:, :1].flatten() * 0.6)
    before_quadratic = 0.5 * free @ hessian @ free + free @ precision[1:, :1].flatten() * 0.6
    after_quadratic = 0.5 * explicit @ hessian @ explicit + explicit @ precision[1:, :1].flatten() * 0.6
    assert after_quadratic > before_quadratic


def test_learning_uses_the_metric_flow_and_preserves_unaddressed_memory(learned):
    model, field = learned
    original = field.clone()
    observation = torch.tensor([0.3, -0.6], dtype=torch.float64)
    exposure = 0.7
    old_covariance = model.covariance(field, 1)
    clamped = model.clamp(field, model.scopes[1], observation)
    after = model.observe(field, 1, observation, exposure=exposure)
    target = torch.outer(observation, observation) + model.ridge * torch.eye(2, dtype=field.dtype)
    expected = math.exp(-exposure) * old_covariance + (-math.expm1(-exposure)) * target
    torch.testing.assert_close(model.covariance(after, 1), expected, rtol=1e-12, atol=1e-14)
    assert model.energy(after) < model.energy(clamped)
    before_parts = field.reshape(2, 9, model.modes)
    after_parts = after.reshape(2, 9, model.modes)
    assert torch.equal(after_parts[0, (0, 2)], before_parts[0, (0, 2)])
    assert torch.equal(field, original)


def test_inference_freezes_evidence_and_restart_continuation_is_exact(learned):
    model, field = learned
    before_memory = field.reshape(2, 9, model.modes)[:, (0, 2)].clone()
    for value in (0.4, -0.8, 0.2):
        field = model.relax(field, (0,), [value], duration=1.0)
    assert torch.equal(field.reshape(2, 9, model.modes)[:, (0, 2)], before_memory)
    resumed = model.restore(model.checkpoint(field))
    assert torch.equal(resumed, field)
    assert torch.equal(
        model.relax(resumed, (0,), [0.1], duration=1.0),
        model.relax(field, (0,), [0.1], duration=1.0),
    )


def test_invalid_memory_and_wrong_interpretation_are_rejected(learned):
    model, field = learned
    wrong = dict(model.checkpoint(field))
    wrong["schema"] = "cassi.qi-flow-state.v3"
    with pytest.raises(ValueError, match="different field interpretation"):
        model.restore(wrong)
    incompatible = VariationalField(3, ((0, 1), (1, 2)), ridge=2e-4)
    with pytest.raises(ValueError, match="different field interpretation"):
        incompatible.restore(model.checkpoint(field))
    corrupt = field.clone()
    corrupt.reshape(2, 9, model.modes)[0, (0, 2), :] = 0
    with pytest.raises(ValueError, match="spectral bounds"):
        model.validate(corrupt)
    hidden_coordinate = field.clone()
    hidden_coordinate.reshape(2, 9, model.modes)[0, 0, 0] += 0.01
    with pytest.raises(ValueError, match="common coordinate"):
        model.validate(hidden_coordinate)
    original = field.clone()
    with pytest.raises(ValueError, match="norm bound"):
        model.observe(field, 0, [10.0, 0.0], exposure=1.0)
    assert torch.equal(field, original)


def test_conflicting_writes_settle_to_the_covariance_conditional():
    from run_variational_field_scenario import _settle

    torch.set_num_threads(1)
    model = VariationalField(2, ((0, 1),))
    field = model.initial_state()
    for index, target in enumerate((1.0, -1.0) * 16, start=1):
        field = model.observe(field, 0, [1.0, target], exposure=-math.log1p(-1.0 / (index + 1)))
    covariance = model.covariance(field, 0)
    direct_conditional = float(covariance[1, 0] / covariance[0, 0])
    settled, _, certificate = _settle(model, field, (0,), torch.tensor([1.0], dtype=torch.float64))
    estimate = float(model.workspace(settled)[1])
    assert estimate == pytest.approx(direct_conditional, abs=1e-10)
    assert certificate["analytic_free_coordinates"][0] == pytest.approx(direct_conditional, abs=1e-14)
    assert abs(estimate - direct_conditional) <= certificate["gradient_error_bound"] + 1e-14


def test_condition_response_matches_reordered_observation_differences(learned):
    model, field = learned
    indices = (2, 0)
    observation = torch.tensor([0.2, -0.4], dtype=field.dtype)
    conditioned, response = model.condition(field, indices, observation)
    torch.testing.assert_close(model.workspace(conditioned)[list(indices)], observation, rtol=0, atol=1e-15)
    epsilon = 1e-6
    for column in range(len(indices)):
        plus, minus = observation.clone(), observation.clone()
        plus[column] += epsilon
        minus[column] -= epsilon
        high, _ = model.condition(field, indices, plus)
        low, _ = model.condition(field, indices, minus)
        derivative = (model.workspace(high) - model.workspace(low)) / (2 * epsilon)
        torch.testing.assert_close(derivative, response[:, column], rtol=1e-8, atol=1e-9)
    parts = conditioned.reshape(2, 9, model.modes)
    assert torch.equal(parts[:, (0, 2)], field.reshape(2, 9, model.modes)[:, (0, 2)])
    residual = model.precision(field) @ model.workspace(conditioned)
    assert abs(float(residual[1])) < 1e-10


def test_linear_action_noise_certificate_has_a_sharp_boundary(learned):
    model, field = learned
    readout = torch.tensor([[0.0, 0.0, 1.0], [0.0, 0.0, -1.0]], dtype=field.dtype)
    _, certified = model.certify_linear_action(field, (0,), [0.4], readout, radius=0.1)
    winner = certified["nominal_action"]
    assert certified["certified_action"] == winner
    for perturbation in (-0.1, 0.0, 0.1):
        changed, _ = model.condition(field, (0,), [0.4 + perturbation])
        assert int((readout @ model.workspace(changed)).argmax()) == winner
    boundary = certified["linear_stability_radius"]
    _, tied = model.certify_linear_action(field, (0,), [0.4], readout, radius=boundary)
    assert tied["certified_action"] is None
    _, crossed = model.certify_linear_action(field, (0,), [0.4], readout, radius=boundary * 1.25)
    assert crossed["certified_action"] is None
    altered_observation = 0.4 + crossed["worst_case_observation_delta"][0]
    altered, _ = model.condition(field, (0,), [altered_observation])
    altered_scores = readout @ model.workspace(altered)
    competitor = crossed["limiting_competitor"]
    actual_margin = float(altered_scores[winner] - altered_scores[competitor])
    assert actual_margin == pytest.approx(min(crossed["normalized_worst_case_margins"]), abs=1e-12)
    assert int(altered_scores.argmax()) != winner


def test_robust_readout_checks_more_than_the_nominal_runner_up():
    model = VariationalField(2, ((0, 1),))
    field = model.initial_state()
    readout = torch.tensor([[1.0, 0.0], [0.9, 0.01], [0.0, 10.0]], dtype=field.dtype)
    _, result = model.certify_linear_action(field, (0, 1), [1.0, 0.0], readout, radius=0.2)
    assert result["nominal_action"] == 0
    assert result["certified_action"] is None
    assert result["limiting_competitor"] == 2
    perturbed = torch.tensor([1.0, 0.0], dtype=field.dtype) + torch.tensor(result["worst_case_observation_delta"], dtype=field.dtype)
    changed, _ = model.condition(field, (0, 1), perturbed)
    assert int((readout @ model.workspace(changed)).argmax()) == 2


def test_robust_readout_refuses_ties_and_inadmissible_error_balls(learned):
    model, field = learned
    readout = torch.tensor([[0.0, 0.0, 1.0], [0.0, 0.0, -1.0]], dtype=field.dtype)
    _, tie = model.certify_linear_action(field, (0,), [0.0], readout, radius=0.0)
    assert tie["certified_action"] is None
    _, empty = model.certify_linear_action(model.initial_state(), (0,), [0.4], readout, radius=0.1)
    assert empty["certified_action"] is None
    _, zero_readout = model.certify_linear_action(field, (0,), [0.4], torch.zeros_like(readout), radius=0.1)
    assert zero_readout["certified_action"] is None
    assert zero_readout["readout_scale"] > 0
    unconstrained, response = model.condition(field, (), [])
    assert response.shape == (model.dimension, 0)
    torch.testing.assert_close(model.workspace(unconstrained), torch.zeros(model.dimension, dtype=field.dtype), rtol=0, atol=0)
    with pytest.raises(ValueError, match="uncertainty ball"):
        model.certify_linear_action(field, (0,), [3.9], readout, radius=0.2)


def test_robust_readout_does_not_depend_on_score_units(learned):
    model, field = learned
    readout = torch.tensor([[0.0, 0.0, 1.0], [0.0, 0.0, -1.0]], dtype=field.dtype)
    _, reference = model.certify_linear_action(field, (0,), [0.4], readout, radius=0.1)
    for scale in (1e-200, 1e200):
        _, result = model.certify_linear_action(field, (0,), [0.4], scale * readout, radius=0.1)
        assert result["certified_action"] == reference["certified_action"]
        assert result["linear_stability_radius"] == pytest.approx(reference["linear_stability_radius"])
