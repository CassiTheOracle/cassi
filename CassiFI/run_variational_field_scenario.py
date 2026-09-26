"""Measure the isolated variational field on synthetic relations and revisions.

Run from CassiFI: python run_variational_field_scenario.py
No corpus, prototype checkpoint, provider, network service or model is used.
The two transition relations are taught separately. Their composition, inverse
and partially observed trajectory are queried on independent held-out inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path
from typing import Any, Sequence

import torch
from torch import Tensor

from cassi_variational_field import VariationalField


def _directions(count: int, seed: int) -> Tensor:
    generator = torch.Generator().manual_seed(seed)
    values = torch.randn(count, 2, generator=generator, dtype=torch.float64)
    return values / torch.linalg.vector_norm(values, dim=1, keepdim=True)


def _memory(field: Tensor, model: VariationalField) -> Tensor:
    return field.reshape(len(model.scopes), 9, model.modes)[:, (0, 2), :].clone()


def _settle(model: VariationalField, field: Tensor, indices: Sequence[int], values: Tensor) -> tuple[Tensor, list[float], dict[str, Any]]:
    state = model.clamp(field, indices, values)
    energies = [model.energy(state)]
    precision = model.precision(state)
    free = [i for i in range(model.dimension) if i not in indices]
    gradient_tolerance = 1e-11
    iterations = 0
    certificate: dict[str, Any] = {
        "free_coordinates": len(free), "iterations": 0,
        "initial_workspace": model.workspace(state).tolist(),
        "minimum_curvature": None, "contraction_factor": None,
        "free_gradient_norm": 0.0, "conditional_solution_error": 0.0,
        "gradient_error_bound": 0.0, "analytic_free_coordinates": [],
    }
    if free:
        residual = float(torch.linalg.vector_norm(precision[free] @ model.workspace(state)))
        hessian = precision[free][:, free]
        eigenvalues = torch.linalg.eigvalsh(hessian)
        minimum_curvature = float(eigenvalues.min())
        boundary = model.workspace(state)
        boundary[free] = 0
        optimum = torch.linalg.solve(hessian, -(precision @ boundary)[free])
        if residual > gradient_tolerance:
            # The implicit step contracts the free gradient by at most
            # 1/(1+minimum_curvature). Use that bound, not a fixed step count.
            iterations = math.ceil(math.log(residual / gradient_tolerance) / math.log1p(minimum_curvature))
    for _ in range(iterations):
        state = model.relax(state, indices, values, duration=1.0)
        energies.append(model.energy(state))
    tolerance = 1e-8 * max(1.0, abs(energies[0]))
    assert max((b - a for a, b in zip(energies, energies[1:])), default=0.0) <= tolerance
    if free:
        gradient_norm = float(torch.linalg.vector_norm(precision[free] @ model.workspace(state)))
        solution_error = float(torch.linalg.vector_norm(model.workspace(state)[free] - optimum))
        error_bound = gradient_norm / minimum_curvature
        roundoff = 128 * torch.finfo(field.dtype).eps * float(eigenvalues.max()) / minimum_curvature * (1 + float(torch.linalg.vector_norm(optimum)))
        assert gradient_norm <= 100 * gradient_tolerance
        assert solution_error <= error_bound + roundoff
        certificate.update({
            "iterations": iterations, "minimum_curvature": minimum_curvature,
            "contraction_factor": 1.0 / (1.0 + minimum_curvature),
            "free_gradient_norm": gradient_norm,
            "conditional_solution_error": solution_error,
            "gradient_error_bound": error_bound,
            "analytic_free_coordinates": optimum.tolist(),
        })
    return state, energies, certificate


def _relative_error(prediction: Tensor, target: Tensor) -> float:
    return float(torch.linalg.vector_norm(prediction - target) / torch.linalg.vector_norm(target))


def _instantaneous_q(field: Tensor, model: VariationalField) -> Tensor:
    parts = field.reshape(len(model.scopes), 9, model.modes)
    ey = parts[:, 0].square() + parts[:, 1].square()
    ei = parts[:, 2].square() + parts[:, 3].square()
    rho = ey + ei
    epsilon = ey - model.phi * ei
    return rho.square() / (rho.square() + model.phi ** -2 + epsilon.square())


def _action_readout_scenario(
    model: VariationalField, field: Tensor, initial: Tensor,
    counterfactual: Tensor, held_out: Tensor, world_composition: Tensor,
) -> dict[str, Any]:
    """Test fixed sign readout under declared sensor error, not model error."""
    radius = 0.1
    readout = field.new_zeros((2, model.dimension))
    readout[0, -1], readout[1, -1] = 1.0, -1.0
    noise = 0.8 * radius * _directions(len(held_out), 606)
    memory = _memory(field, model)
    working = field
    records: list[dict[str, Any]] = []
    certified_count = certified_correct = nominal_correct = 0
    maximum_witness_error = 0.0
    for clean, perturbation in zip(held_out, noise):
        measured = clean + perturbation
        working, certificate = model.certify_linear_action(working, (0, 1), measured, readout, radius=radius)
        truth_action = int(float((world_composition @ clean)[-1]) < 0)
        nominal_correct += int(certificate["nominal_action"] == truth_action)
        if certificate["certified_action"] is not None:
            certified_count += 1
            certified_correct += int(certificate["certified_action"] == truth_action)
        assert torch.equal(_memory(working, model), memory)
        delta = torch.tensor(certificate["worst_case_observation_delta"], dtype=field.dtype)
        assert float(torch.linalg.vector_norm(delta)) <= radius + 1e-14
        witness, _ = model.condition(working, (0, 1), measured + delta)
        witness_scores = readout @ model.workspace(witness) / certificate["readout_scale"]
        winner, competitor = certificate["nominal_action"], certificate["limiting_competitor"]
        witness_margin = float(witness_scores[winner] - witness_scores[competitor])
        recorded_margin = min(certificate["normalized_worst_case_margins"])
        witness_error = abs(witness_margin - recorded_margin)
        assert witness_error < 1e-10
        maximum_witness_error = max(maximum_witness_error, witness_error)
        if certificate["certified_action"] is not None:
            assert int(witness_scores.argmax()) == certificate["certified_action"]
        elif recorded_margin < -1e-10:
            assert int(witness_scores.argmax()) != winner
        records.append({
            "clean_observation": clean.tolist(), "measured_observation": measured.tolist(),
            "true_sign_action": truth_action, "certificate": certificate,
            "worst_case_witness_margin": witness_margin,
        })
    assert certified_count > 0 and certified_correct == certified_count

    _, response = model.condition(field, (0, 1), held_out[0])
    direction = response[-1] / torch.linalg.vector_norm(response[-1])
    tangent = torch.stack((-direction[1], direction[0]))
    near_boundary = 0.5 * tangent + 0.25 * radius * direction
    _, uncertain = model.certify_linear_action(field, (0, 1), near_boundary, readout, radius=radius)
    assert uncertain["certified_action"] is None
    _, no_relation = model.certify_linear_action(initial, (0, 1), held_out[0], readout, radius=radius)
    assert no_relation["certified_action"] is None

    # A wrong but internally stable field can certify its wrong prediction.
    # This directly excludes an interpretation as model truth or confidence.
    _, normal = model.certify_linear_action(field, (0, 1), held_out[0], readout, radius=radius)
    _, wrong = model.certify_linear_action(counterfactual, (0, 1), held_out[0], readout, radius=radius)
    assert normal["certified_action"] is not None and wrong["certified_action"] is not None
    assert normal["certified_action"] != wrong["certified_action"]
    true_action = int(float((world_composition @ held_out[0])[-1]) < 0)
    assert normal["certified_action"] == true_action and wrong["certified_action"] != true_action
    return {
        "declared_observation_L2_radius": radius,
        "actual_noise_norm": 0.8 * radius,
        "nominal_correct": nominal_correct, "total": len(held_out),
        "certified": certified_count, "correct_among_certified": certified_correct,
        "abstained": len(held_out) - certified_count,
        "maximum_worst_case_witness_error": maximum_witness_error,
        "memory_bit_identical": True,
        "near_boundary": uncertain, "empty_memory": no_relation,
        "wrong_model_control": {"normal": normal, "wrong": wrong, "true_action": true_action},
        "samples": records,
        "scope": "model-conditional robustness to declared input error; not truth, probability, permission or a floating-point interval proof",
    }


def run() -> dict[str, Any]:
    torch.set_num_threads(1)
    model = VariationalField(6, ((0, 1, 2, 3), (2, 3, 4, 5)))
    initial = model.initial_state()
    field = initial.clone()
    a = torch.tensor([[1.2, 0.4], [-0.3, 0.8]], dtype=torch.float64)
    b = torch.tensor([[0.8, -0.5], [0.25, 1.1]], dtype=torch.float64)
    train_a, train_b = _directions(64, 101), _directions(64, 202)
    exposure = 0.125
    learning_drops: list[float] = []
    boundary_work: list[float] = []
    for x, y in zip(train_a, train_b):
        for factor, local in ((0, torch.cat((x, a @ x))), (1, torch.cat((y, b @ y)))):
            clamped = model.clamp(field, model.scopes[factor], local)
            boundary_work.append(model.energy(clamped) - model.energy(field))
            after = model.observe(field, factor, local, exposure=exposure)
            drop = model.energy(clamped) - model.energy(after)
            assert drop >= -1e-8
            learning_drops.append(drop)
            field = after

    trained_memory = _memory(field, model)
    held_out = _directions(32, 303)
    forward_errors, backward_errors, partial_errors = [], [], []
    decisions_correct = 0
    first_energy_trace: list[float] = []
    convergence_certificates: list[dict[str, Any]] = []
    for number, x in enumerate(held_out):
        truth = torch.cat((x, a @ x, b @ a @ x))
        forward, energy_trace, convergence = _settle(model, field, (0, 1), x)
        convergence_certificates.append(convergence)
        if number == 0:
            first_energy_trace = energy_trace
        inferred = model.workspace(forward)
        forward_errors.append(_relative_error(inferred[2:], truth[2:]))
        decisions_correct += int(bool((inferred[5] >= 0) == (truth[5] >= 0)))
        backward, _, convergence = _settle(model, field, (4, 5), truth[4:])
        convergence_certificates.append(convergence)
        backward_errors.append(_relative_error(model.workspace(backward)[:4], truth[:4]))
        partial, _, convergence = _settle(model, field, (0, 5), truth[[0, 5]])
        convergence_certificates.append(convergence)
        partial_errors.append(_relative_error(model.workspace(partial), truth))
        assert torch.equal(_memory(forward, model), trained_memory)
        assert torch.equal(_memory(backward, model), trained_memory)
        assert torch.equal(_memory(partial, model), trained_memory)
    assert max(forward_errors + backward_errors + partial_errors) < 0.01
    assert decisions_correct == len(held_out)

    # A field-only sign intervention changes the relation while preserving every
    # local amplitude-square Qi diagnostic and every covariance eigenvalue.
    counterfactual = field.clone()
    parts = counterfactual.reshape(len(model.scopes), 9, model.modes)
    signs = torch.tensor([1.0, 1.0, -1.0, -1.0], dtype=field.dtype)
    mask = torch.outer(signs, signs).reshape(-1)
    parts[0, 0, :16] *= mask
    parts[0, 2, :16] *= mask
    model.validate(counterfactual)
    q_equal = torch.equal(_instantaneous_q(field, model), _instantaneous_q(counterfactual, model))
    assert q_equal
    normal, _, _ = _settle(model, field, (0, 1), held_out[0])
    intervened, _, _ = _settle(model, counterfactual, (0, 1), held_out[0])
    empty, _, _ = _settle(model, initial, (0, 1), held_out[0])
    normal_result = model.workspace(normal)[2:]
    intervened_result = model.workspace(intervened)[2:]
    empty_result = model.workspace(empty)[2:]
    intervention_change = _relative_error(intervened_result, normal_result)
    assert intervention_change > 1.0
    assert float(torch.linalg.vector_norm(empty_result)) < 1e-12
    assert bool((model.workspace(normal)[5] >= 0) != (model.workspace(intervened)[5] >= 0))
    action_readout = _action_readout_scenario(model, field, initial, counterfactual, held_out, b @ a)

    # Only actual changed observations teach the second relation. Imagined
    # trajectories never enter observe(). The first factor remains bit-exact.
    revised = field.clone()
    old_first_memory = _memory(field, model)[0].clone()
    new_b = torch.tensor([[-0.6, 0.7], [0.9, 0.3]], dtype=field.dtype)
    for y in _directions(96, 404):
        revised = model.observe(revised, 1, torch.cat((y, new_b @ y)), exposure=exposure)
    assert torch.equal(_memory(revised, model)[0], old_first_memory)
    revised_errors = []
    for x in held_out:
        result, _, _ = _settle(model, revised, (0, 1), x)
        target = torch.cat((a @ x, new_b @ a @ x))
        revised_errors.append(_relative_error(model.workspace(result)[2:], target))
    assert max(revised_errors) < 0.01

    # Continued inference changes workspace only, not the stored evidence.
    retained = revised.clone()
    revised_memory = _memory(revised, model)
    for index in range(256):
        x = held_out[index % len(held_out)]
        retained = model.relax(retained, (0, 1), x, duration=1.0)
    idle_memory_exact = torch.equal(_memory(retained, model), revised_memory)
    assert idle_memory_exact

    # Bounded streams preserve the covariance interval. This is not a claim
    # that older incompatible relations survive the exponential write law.
    stressed = revised.clone()
    for index, x in enumerate(_directions(512, 505)):
        local = torch.cat((x, (a if index % 2 == 0 else -a) @ x))
        stressed = model.observe(stressed, 0, local, exposure=exposure)
    eigenvalues = torch.cat([torch.linalg.eigvalsh(model.covariance(stressed, f)) for f in range(len(model.scopes))])
    minimum_eigenvalue, maximum_eigenvalue = float(eigenvalues.min()), float(eigenvalues.max())
    assert minimum_eigenvalue >= model.ridge - 1e-10
    assert maximum_eigenvalue <= model.ridge + model.observation_norm_bound ** 2 + 1e-10

    # Contradictory facts in one fixed scope cancel their cross relation. A
    # stable conditional zero is neither a correct answer nor a truth signal.
    conflict_model = VariationalField(2, ((0, 1),))
    conflict = conflict_model.initial_state()
    for index, target in enumerate((1.0, -1.0) * 16, start=1):
        gain = 1.0 / (index + 1)
        conflict = conflict_model.observe(conflict, 0, [1.0, target], exposure=-math.log1p(-gain))
    conflict, _, conflict_convergence = _settle(conflict_model, conflict, (0,), torch.tensor([1.0], dtype=torch.float64))
    conflict_output = float(conflict_model.workspace(conflict)[1])
    assert abs(conflict_output) < 1e-10
    conditional_spread = float(torch.linalg.inv(conflict_model.precision(conflict)[1:, 1:])[0, 0])

    # Exact restart with fixed-geometry metadata; never a v2/v3 paper artifact.
    with tempfile.TemporaryDirectory(prefix="cassi-variational-") as directory:
        checkpoint = Path(directory) / "field.pt"
        torch.save(model.checkpoint(revised), checkpoint)
        restored = model.restore(torch.load(checkpoint, weights_only=True))
        reload_exact = torch.equal(restored, revised)
        replay_a = model.relax(revised, (0, 1), held_out[0], duration=1.0)
        replay_b = model.relax(restored, (0, 1), held_out[0], duration=1.0)
        continuation_exact = torch.equal(replay_a, replay_b)
        assert reload_exact and continuation_exact

    sources = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (Path(__file__), Path(__file__).with_name("cassi_variational_field.py"))
    }
    return {
        "scope": "isolated real-valued quadratic field; fixed factor scopes; synthetic data",
        "device": str(field.device),
        "dtype": str(field.dtype),
        "torch_version": torch.__version__,
        "sources_sha256": sources,
        "geometry": model.checkpoint(field)["geometry"],
        "adaptive_state": {"shape": list(field.shape), "bytes": field.numel() * field.element_size(), "persistent_tensor_count": 1},
        "training": {"separate_pairs_per_relation": 64, "held_out_inputs": 32, "exposure": exposure, "minimum_fixed_observation_energy_drop": min(learning_drops), "maximum_boundary_work": max(boundary_work)},
        "held_out": {"forward_composed_max_relative_error": max(forward_errors), "backward_max_relative_error": max(backward_errors), "partial_trajectory_max_relative_error": max(partial_errors), "sign_actions_correct": decisions_correct, "sign_actions_total": len(held_out), "first_inference_energy_trace": first_energy_trace, "maximum_conditional_solution_error": max(row["conditional_solution_error"] for row in convergence_certificates), "maximum_free_gradient_norm": max(row["free_gradient_norm"] for row in convergence_certificates), "convergence_certificates": convergence_certificates},
        "field_only_counterfactual": {"instantaneous_q_bit_identical": q_equal, "relative_prediction_change": intervention_change, "sign_action_changed": True, "empty_memory_output_norm": float(torch.linalg.vector_norm(empty_result))},
        "revision": {"observed_pairs": 96, "untouched_factor_memory_bit_identical": True, "composed_max_relative_error": max(revised_errors)},
        "retention": {"inference_steps": 256, "memory_bit_identical": idle_memory_exact, "old_write_weight_after_96_updates": math.exp(-96 * exposure)},
        "bounded_stream": {"updates": 512, "minimum_covariance_eigenvalue": minimum_eigenvalue, "maximum_covariance_eigenvalue": maximum_eigenvalue, "declared_interval": [model.ridge, model.ridge + model.observation_norm_bound ** 2]},
        "contradiction": {"estimate": conflict_output, "analytic_conditional_estimate": conflict_convergence["analytic_free_coordinates"][0], "cross_moment": float(conflict_model.covariance(conflict, 0)[0, 1]), "convergence": conflict_convergence, "conditional_quadratic_spread": conditional_spread, "interpretation": "unsupported compromise; stability is not truth; spread is not calibrated confidence"},
        "restart": {"raw_state_bit_identical": reload_exact, "continuation_bit_identical": continuation_exact},
        "action_readout": action_readout,
        "boundaries": ["no prototype or host-adapter replacement", "not a W3-compatible profile/checkpoint", "no learned codec or factor-scope discovery", "no calibrated probability or commitment policy", "no general intelligence or particle-formation claim", "no physical energy or performance advantage measured"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
