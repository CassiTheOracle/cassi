"""Focused controls for the preregistered L41 exact-solver audit."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification.run_l41_exact_cyclic_solver_audit import DT, run_audit


def laplacian(value: np.ndarray) -> np.ndarray:
    return 2.0 * value - np.roll(value, 1, axis=0) - np.roll(value, -1, axis=0)


def rk4_linear(
    position: np.ndarray,
    velocity: np.ndarray,
    base_omega2: np.ndarray,
    coupling: np.ndarray,
    gamma: np.ndarray,
    microsteps: int,
) -> tuple[np.ndarray, np.ndarray]:
    step = DT / microsteps

    def rhs(q: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return v, -base_omega2 * q - coupling * laplacian(q) - gamma * v

    q = position.copy()
    v = velocity.copy()
    for _ in range(microsteps):
        q1, v1 = rhs(q, v)
        q2, v2 = rhs(q + 0.5 * step * q1, v + 0.5 * step * v1)
        q3, v3 = rhs(q + 0.5 * step * q2, v + 0.5 * step * v2)
        q4, v4 = rhs(q + step * q3, v + step * v3)
        q += step * (q1 + 2.0 * q2 + 2.0 * q3 + q4) / 6.0
        v += step * (v1 + 2.0 * v2 + 2.0 * v3 + v4) / 6.0
    return q, v


def test_l41_no_term_stability_and_conservation_controls() -> None:
    metrics, arrays = run_audit(
        torch.device("cpu"), control_steps=32, stability_ticks=8
    )

    assert metrics["operator_eigenvalue_max_error"] <= 2.0e-12
    assert metrics["parseval_energy_absolute_error"] <= 2.0e-12
    assert metrics["free_drift_max_error"] <= 1.0e-12
    assert metrics["split_no_term_relative_error"] <= 1.0e-12
    assert metrics["independent_rk4_max_error"] <= 2.0e-10
    assert metrics["conservative_relative_energy_drift"] <= 2.0e-9
    assert metrics["damped_final_energy_ratio"] < 1.0
    assert metrics["damped_max_positive_increment_ratio"] <= 2.0e-10
    assert metrics["nonlinear_roundtrip_relative_error"] <= 2.0e-10
    assert metrics["nonlinear_hamiltonian_relative_envelope"] <= 2.0e-5
    assert metrics["zero_state_nonzero_count"] == 0
    assert metrics["zero_state_clamp_count"] == 0
    assert metrics["driven_finite"]
    assert metrics["driven_clamp_count"] == 0
    assert metrics["driven_maximum_dynamic_energy"] <= 1.05
    assert metrics["driven_maximum_absolute_input_energy_drift"] <= 2.0e-5

    expected_position, expected_velocity = rk4_linear(
        arrays["common_initial"],
        arrays["common_velocity_initial"],
        arrays["base_omega2"],
        arrays["coupling"],
        2.0 * arrays["alpha"],
        1024,
    )
    assert np.max(np.abs(arrays["spot_position"] - expected_position)) <= 2.0e-10
    assert np.max(np.abs(arrays["spot_velocity"] - expected_velocity)) <= 2.0e-10
