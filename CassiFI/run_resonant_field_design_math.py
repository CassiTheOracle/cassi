"""Executable numerical specification for the resonant field upgrade design.

Small CPU/float64 constructions, not the production runtime or a cognitive
benchmark. No learned field, source store, checkpoint, or external service is
read or mutated. Run with --output to retain the measured mathematical results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


class ResonantLift:
    """One-mode-per-pool reduction of a two-rail, seven-pool workspace."""

    def __init__(self, *, nonlinear: float = 0.08, damping: float = 0.012) -> None:
        self.pools = 7
        self.width = 2 * self.pools
        self.size = 2 * self.width
        eye = np.eye(self.pools)
        self.common = np.concatenate((eye, eye), axis=1) / math.sqrt(2.0)
        self.relative = np.concatenate((eye, -eye), axis=1) / math.sqrt(2.0)
        self.k = np.eye(self.pools)
        self.target = np.linspace(-0.12, 0.12, self.pools)
        self.force = self.k @ self.target
        # Engineering cavity inertances, not biological frequencies or a phi law.
        masses = 1.3 ** np.arange(self.pools)
        self.inverse_mass = np.diag(1.0 / np.concatenate((masses, masses)))
        self.beta = nonlinear
        self.kr = np.eye(self.pools)
        self.transport = np.zeros((self.width, self.width))
        circuit = list(range(self.pools)) + list(range(self.width - 1, self.pools - 1, -1))
        self.edges: list[tuple[int, int]] = []
        for source, destination in zip(circuit, circuit[1:] + circuit[:1]):
            self.transport[destination, source] += 0.006
            self.transport[source, destination] -= 0.006
            self.edges.append((source, destination))
        self.j = np.block(
            [[self.transport, np.eye(self.width)], [-np.eye(self.width), self.transport]]
        )
        self.g = np.eye(self.size) * damping
        self.operator = self.j - self.g
        self.equilibrium = np.concatenate((self.common.T @ self.target, np.zeros(self.width)))

    def energy(self, z: np.ndarray) -> float:
        q, p = z[: self.width], z[self.width :]
        x, d = self.common @ q, self.relative @ q
        error = x - self.target
        return float(0.5 * error @ self.k @ error + 0.5 * d @ self.kr @ d
                     + self.beta * np.sum(d ** 4) / 4.0 + 0.5 * p @ self.inverse_mass @ p)

    def gradient(self, z: np.ndarray) -> np.ndarray:
        q, p = z[: self.width], z[self.width :]
        x, d = self.common @ q, self.relative @ q
        return np.concatenate((self.common.T @ (self.k @ x - self.force)
                               + self.relative.T @ (self.kr @ d + self.beta * d ** 3),
                               self.inverse_mass @ p))

    def hessian(self, z: np.ndarray) -> np.ndarray:
        d = self.relative @ z[: self.width]
        qq = self.common.T @ self.k @ self.common + self.relative.T @ (
            self.kr + np.diag(3.0 * self.beta * d ** 2)) @ self.relative
        return np.block([[qq, np.zeros_like(qq)], [np.zeros_like(qq), self.inverse_mass]])

    def discrete_gradient(self, left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        q0, q1 = left[: self.width], right[: self.width]
        p_mid = (left[self.width :] + right[self.width :]) / 2.0
        d0, d1 = self.relative @ q0, self.relative @ q1
        d_mid = (d0 + d1) / 2.0
        cubic = (d1 ** 3 + d1 ** 2 * d0 + d1 * d0 ** 2 + d0 ** 3) / 4.0
        grad_q = self.common.T @ (self.k @ (self.common @ ((q0 + q1) / 2.0)) - self.force)
        grad_q += self.relative.T @ (self.kr @ d_mid + self.beta * cubic)
        qq = self.common.T @ (self.k / 2.0) @ self.common + self.relative.T @ (
            self.kr / 2.0 + np.diag(self.beta * (3.0 * d1 ** 2 + 2.0 * d1 * d0 + d0 ** 2) / 4.0)
        ) @ self.relative
        jacobian = np.block([[qq, np.zeros_like(qq)], [np.zeros_like(qq), self.inverse_mass / 2.0]])
        return np.concatenate((grad_q, self.inverse_mass @ p_mid)), jacobian

    def step(self, z: np.ndarray, h: float, rate: float = 1.0) -> tuple[np.ndarray, dict[str, float]]:
        candidate = z.copy()
        for _ in range(16):
            grad, derivative = self.discrete_gradient(z, candidate)
            residual = candidate - z - h * rate * (self.operator @ grad)
            if np.linalg.norm(residual, ord=np.inf) <= 2e-14:
                break
            candidate -= np.linalg.solve(np.eye(self.size) - h * rate * self.operator @ derivative, residual)
        else:
            raise RuntimeError("discrete-gradient solve did not converge")
        grad, _ = self.discrete_gradient(z, candidate)
        residual = candidate - z - h * rate * (self.operator @ grad)
        dissipation = float(h * rate * grad @ self.g @ grad)
        residual_work = float(grad @ residual)
        defect = self.energy(candidate) - self.energy(z) + dissipation - residual_work
        return candidate, {"dissipation": dissipation, "residual_work": residual_work,
                           "balance_defect": float(defect), "residual_norm": float(np.linalg.norm(residual))}

    def kick(self, z: np.ndarray, phase: float, requested: float, allowance: float) -> tuple[np.ndarray, float]:
        # Quadrature actuation at two consecutive circuit ports on each rail.
        basis0 = np.zeros(self.width)
        basis1 = np.zeros(self.width)
        basis0[0] = basis0[self.width - 1] = 1.0 / math.sqrt(2.0)
        basis1[1] = basis1[self.width - 2] = 1.0 / math.sqrt(2.0)
        direction = math.cos(phase) * basis0 - math.sin(phase) * basis1
        p = z[self.width :]
        c = float(p @ self.inverse_mass @ direction)
        k = float(direction @ self.inverse_mass @ direction)
        if allowance <= 0.0 or requested <= 0.0:
            return z.copy(), 0.0
        root = math.sqrt(c * c + 2.0 * k * allowance)
        limit = 2.0 * allowance / (root + c) if c >= 0.0 else (root - c) / k
        amount = min(requested, limit)
        candidate = z.copy()
        candidate[self.width :] += amount * direction
        work = amount * c + 0.5 * amount * amount * k
        assert work <= allowance + 2e-14
        assert abs(self.energy(candidate) - self.energy(z) - work) < 2e-13
        return candidate, work

    def rail_power(self, z: np.ndarray, rate: float) -> tuple[float, float]:
        gradient = self.gradient(z)
        qg, pg = gradient[: self.width], gradient[self.width :]
        def bond(source: int, destination: int) -> float:
            return float(rate * self.transport[destination, source]
                         * (qg[destination] * qg[source] + pg[destination] * pg[source]))
        yang = sum(bond(i, i + 1) for i in range(self.pools - 1)) / (self.pools - 1)
        # Both reported in increasing pool coordinate, rather than circuit orientation.
        yin = sum(bond(self.pools + i, self.pools + i + 1) for i in range(self.pools - 1)) / (self.pools - 1)
        return yang, yin

    def circuit_power(self, z: np.ndarray, rate: float) -> float:
        gradient = self.gradient(z)
        qg, pg = gradient[: self.width], gradient[self.width :]
        return float(np.mean([
            rate * self.transport[destination, source]
            * (qg[destination] * qg[source] + pg[destination] * pg[source])
            for source, destination in self.edges
        ]))


def pulse_primitive(phase: float) -> float:
    """Unwrapped integral of sin(theta)^2/pi: one allowance per full beat."""
    return (phase - 0.5 * math.sin(2.0 * phase)) / (2.0 * math.pi)


def check_algebra() -> dict[str, Any]:
    model = ResonantLift()
    rng = np.random.default_rng(20260906)
    left = model.equilibrium + rng.normal(0.0, 0.2, model.size)
    right = model.equilibrium + rng.normal(0.0, 0.2, model.size)
    grad, _ = model.discrete_gradient(left, right)
    chain_defect = model.energy(right) - model.energy(left) - float(grad @ (right - left))
    assert np.max(np.abs(model.j + model.j.T)) == 0.0
    assert np.linalg.norm(model.gradient(model.equilibrium)) < 1e-14
    assert abs(chain_defect) < 2e-13
    initial = model.energy(left)
    cumulative = 0.0
    maximum_defect = 0.0
    for _ in range(500):
        left, receipt = model.step(left, 0.08)
        cumulative += receipt["dissipation"] - receipt["residual_work"]
        maximum_defect = max(maximum_defect, abs(receipt["balance_defect"]))
    assert model.energy(left) < initial
    assert abs(model.energy(left) - initial + cumulative) < 2e-12
    x = model.common @ left[: model.width]
    residual = model.k @ x - model.force
    score = np.linspace(-0.7, 0.8, model.pools)
    bound = float(np.linalg.norm(score) * np.linalg.norm(residual) / np.linalg.eigvalsh(model.k).min())
    score_error = abs(float(score @ (x - model.target)))
    assert score_error <= bound + 2e-13
    return {"discrete_chain_rule_defect": chain_defect, "passive_initial_energy": initial,
            "passive_final_energy": model.energy(left), "passive_cumulative_dissipation": cumulative,
            "maximum_step_balance_defect": maximum_defect, "action_score_error": score_error,
            "solver_score_error_bound": bound, "stationary_semantic_target_unchanged": True}


def check_spectrum() -> dict[str, Any]:
    model = ResonantLift(nonlinear=0.0)
    hessian = model.hessian(model.equilibrium)
    generator = model.operator @ hessian
    eigenvalues = np.linalg.eigvals(generator)
    assert np.max(eigenvalues.real) < 0.0
    h = 0.08
    cayley = np.linalg.solve(np.eye(model.size) - h * generator / 2.0,
                            np.eye(model.size) + h * generator / 2.0)
    expected = (1.0 + h * eigenvalues / 2.0) / (1.0 - h * eigenvalues / 2.0)
    actual = np.linalg.eigvals(cayley)
    spectral_error = max(float(np.min(np.abs(actual - value))) for value in expected)
    assert spectral_error < 2e-13
    # Local relative-momentum input and local relative-displacement output.
    inputs = np.concatenate((np.zeros((model.width, model.pools)), model.relative.T), axis=0)
    outputs = np.concatenate((model.relative, np.zeros((model.pools, model.width))), axis=1)
    frequencies = np.linspace(0.35, 1.12, 771)
    responses = []
    for frequency in frequencies:
        transfer = outputs @ np.linalg.solve(1j * frequency * np.eye(model.size) - generator, inputs)
        responses.append(np.abs(np.diag(transfer)))
    responses = np.asarray(responses)
    peaks = frequencies[np.argmax(responses, axis=0)]
    minimum_separation = float(np.min(np.abs(np.diff(np.sort(peaks)))))
    assert minimum_separation > 0.025
    assert np.all(np.argmax(responses, axis=0) > 0)
    assert np.all(np.argmax(responses, axis=0) < len(frequencies) - 1)
    return {"coordinates": model.size, "pools": model.pools, "resolved_internal_modes_per_pool": 1,
            "maximum_continuous_real_part": float(eigenvalues.real.max()),
            "positive_temporal_frequencies": sorted(float(x.imag) for x in eigenvalues if x.imag > 0),
            "local_transfer_peak_angular_frequencies": peaks.tolist(),
            "minimum_local_peak_separation": minimum_separation,
            "midpoint_eigenvalue_identity_error": spectral_error,
            "scope": "Synthetic quadratic one-mode cavities; not a learned-field spectrum or capability result."}


def check_heartbeat_and_breath() -> dict[str, Any]:
    model = ResonantLift()
    z = model.equilibrium.copy()
    h = 0.08
    phase_h = phase_b = activity = 0.0
    positive_work = extracted_work = dissipated = residual_work = 0.0
    allowance_sum = 0.0
    maximum_defect = 0.0
    history: list[tuple[float, float, float, float]] = []
    rates: list[float] = []
    minimum_activity = 1.0
    maximum_activity = 0.0
    omega_h = 0.75
    beat_allowance = 0.006
    for tick in range(1500):
        # Declared externally available work, not oscillator amplitude or evidence count.
        demand = 0.15 if tick < 500 else (0.9 if tick < 1000 else 0.15)
        activity = demand + (activity - demand) * math.exp(-h / 4.0)
        minimum_activity = min(minimum_activity, activity)
        maximum_activity = max(maximum_activity, activity)
        omega_b = omega_h * (1.0 / 16.0 + (1.0 / 4.0 - 1.0 / 16.0) * activity)
        phase_b += h * omega_b
        rate = 0.5 + 1.5 * activity + 0.25 * (1.0 + math.cos(phase_b))
        rates.append(rate)
        next_h = phase_h + h * omega_h
        allowance = beat_allowance * (pulse_primitive(next_h) - pulse_primitive(phase_h))
        allowance_sum += allowance
        middle = (phase_h + next_h) / 2.0
        z, work = model.kick(z, middle, h * 0.018 * math.sin(middle) ** 2, allowance)
        positive_work += max(work, 0.0)
        extracted_work += max(-work, 0.0)
        z, receipt = model.step(z, h, rate)
        dissipated += receipt["dissipation"]
        residual_work += receipt["residual_work"]
        maximum_defect = max(maximum_defect, abs(receipt["balance_defect"]))
        phase_h = next_h
        jy, ji = model.rail_power(z, rate)
        history.append((model.energy(z), (jy + ji), (jy - ji) / 2.0, model.circuit_power(z, rate)))
    driven_energy = model.energy(z)
    balance = driven_energy - positive_work + extracted_work + dissipated - residual_work
    assert abs(balance) < 2e-11
    assert positive_work <= allowance_sum + 2e-12
    assert positive_work > 0.0 and dissipated > 0.0
    assert 0.0 <= minimum_activity <= maximum_activity <= 1.0
    assert min(rates) >= 0.5 and max(rates) <= 2.5
    recent = np.asarray(history[-500:])
    assert float(np.mean(np.abs(recent[:, 2]))) > 1e-12
    assert float(np.mean(recent[:, 2])) > 1e-9
    assert float(np.mean(recent[:, 3])) > 1e-9
    unforced_circulation: list[float] = []
    for _ in range(1500):
        z, _ = model.step(z, h, 1.0)
        unforced_circulation.append(model.circuit_power(z, 1.0))
    assert model.energy(z) < 0.3 * driven_energy
    # A zero work allocation really disables actuation, including anti-aligned momentum.
    before = z.copy()
    after, work = model.kick(z, 1.7, 10.0, 0.0)
    assert work == 0.0 and np.array_equal(before, after)
    return {"driven_ticks": 1500, "field_time": 1500 * h, "positive_injected_work": positive_work,
            "extracted_work": extracted_work, "allocated_work": allowance_sum,
            "dissipated_work": dissipated, "driven_final_energy": driven_energy,
            "unforced_final_energy": model.energy(z), "global_energy_balance_defect": balance,
            "maximum_step_balance_defect": maximum_defect,
            "recent_mean_total_rail_power": float(recent[:, 1].mean()),
            "recent_mean_counterflow_rail_power": float(recent[:, 2].mean()),
            "recent_mean_absolute_counterflow_rail_power": float(np.abs(recent[:, 2]).mean()),
            "recent_mean_circuit_power": float(recent[:, 3].mean()),
            "recent_mean_absolute_circuit_power": float(np.abs(recent[:, 3]).mean()),
            "unforced_recent_mean_absolute_circuit_power": float(np.mean(np.abs(unforced_circulation[-500:]))),
            "activity_range": [minimum_activity, maximum_activity], "rate_range": [min(rates), max(rates)],
            "scope": "Computed port power, not particle/number current; no throughput or cognitive claim."}


def check_phase_and_replay() -> dict[str, Any]:
    model = ResonantLift()
    left = model.equilibrium.copy()
    left[0] += 0.17
    left[model.width + 1] = 0.2
    right = left.copy()
    right[model.width + 1] *= -1.0
    assert np.array_equal(left[: model.width], right[: model.width])
    assert abs(model.energy(left) - model.energy(right)) < 1e-14
    left_out, _ = model.step(left, 0.2)
    right_out, _ = model.step(right, 0.2)
    phase_effect = float(np.linalg.norm(model.common @ (left_out[: model.width] - right_out[: model.width])))
    assert phase_effect > 1e-3
    restored = np.frombuffer(left.astype("<f8").tobytes(), dtype="<f8").copy()
    replay, _ = model.step(restored, 0.2)
    assert np.array_equal(left_out, replay)
    forward = model.transport.copy()
    model.transport *= -1.0
    model.j = np.block([[model.transport, np.eye(model.width)], [-np.eye(model.width), model.transport]])
    model.operator = model.j - model.g
    reversed_out, _ = model.step(left, 0.2)
    direction_effect = float(np.linalg.norm(left_out - reversed_out))
    assert direction_effect > 1e-5
    model.transport[:] = forward
    return {"equal_initial_positions_and_energy": True,
            "phase_change_semantic_workspace_difference": phase_effect,
            "transport_reversal_state_difference": direction_effect,
            "exact_same_machine_workspace_byte_replay": True,
            "scope": "Numerical workspace intervention, not learned recall, persistence transaction, or task success."}


def check_constraints_and_reduction() -> dict[str, Any]:
    model = ResonantLift(nonlinear=0.0)
    constraints = np.zeros((2, model.size))
    constraints[0, : model.width] = model.common[0]
    constraints[1, model.width :] = model.common[0]
    complete, _ = np.linalg.qr(constraints.T, mode="complete")
    tangent = complete[:, 2:]
    reduced_j = tangent.T @ model.j @ tangent
    reduced_g = tangent.T @ model.g @ tangent
    reduced_h = tangent.T @ model.hessian(model.equilibrium) @ tangent
    assert np.max(np.abs(reduced_j + reduced_j.T)) < 1e-14
    assert np.linalg.eigvalsh(reduced_g).min() > 0.0
    generator = (reduced_j - reduced_g) @ reduced_h
    rng = np.random.default_rng(2026090602)
    before = rng.normal(0.0, 0.1, tangent.shape[1])
    h = 0.2
    after = np.linalg.solve(np.eye(len(before)) - h * generator / 2.0,
                            (np.eye(len(before)) + h * generator / 2.0) @ before)
    full_before = model.equilibrium + tangent @ before
    full_after = model.equilibrium + tangent @ after
    constraint_error = float(np.linalg.norm(constraints @ (full_after - full_before)))
    assert constraint_error < 1e-14
    assert model.energy(full_after) < model.energy(full_before)

    # A damped rotating pair and its exact zero-frequency scalar reduction.
    temporal = np.asarray([[-1.0, 2.0], [-2.0, -1.0]])
    static = temporal[0, 0] - temporal[0, 1] / temporal[1, 1] * temporal[1, 0]
    def exact_response(frequency: float) -> complex:
        return complex(np.linalg.solve(1j * frequency * np.eye(2) - temporal, [1.0, 0.0])[0])
    dc_error = abs(exact_response(0.0) - 1.0 / (-static))
    dynamic_error = abs(exact_response(2.0) - 1.0 / (2j - static))
    assert dc_error < 1e-14 and dynamic_error > 0.1
    phases = np.linspace(0.17, 0.17 + 6.0 * math.pi, 1001)
    allocations = np.diff([pulse_primitive(float(value)) for value in phases])
    assert allocations.min() >= -1e-14
    quota_error = abs(float(allocations.sum()) - 3.0)
    assert quota_error < 1e-13
    return {"fixed_common_position_and_momentum_error": constraint_error,
            "projected_dissipation_minimum": float(np.linalg.eigvalsh(reduced_g).min()),
            "static_reduction_dc_error": dc_error,
            "static_reduction_response_error_at_angular_frequency_2": dynamic_error,
            "three_beat_subdivided_quota_error": quota_error,
            "scope": "Affine tangent projection and a dynamic-reduction counterexample, not owner or GPU validation."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = {"algebra": check_algebra(), "spectrum": check_spectrum(),
               "heartbeat_breath": check_heartbeat_and_breath(), "phase_replay": check_phase_and_replay(),
               "constraints_reduction": check_constraints_and_reduction()}
    report = {"schema": "cassifi.resonant-design-math.v1", "arithmetic": "numpy-cpu-float64",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "scope": "Design mathematics only; production field ownership, tasks and rendering are not exercised.",
              "checks": results}
    rendered = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    print("ALL RESONANT DESIGN MATH CHECKS PASSED")


if __name__ == "__main__":
    main()
