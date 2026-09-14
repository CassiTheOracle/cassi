#!/usr/bin/env python3
"""Audit a finite Galerkin trajectory with explicit signed-mode convolution.

This verifier deliberately uses a different representation from the production
long-trajectory probe: all signed Fourier modes are stored, the nonlinear term
is assembled by direct convolution, and the checkpoint production is also
reconstructed by a signed triple convolution.  It is a finite diagnostic and
makes no regularity claim.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "navier-stokes-galerkin-long-trajectory-audit-prereg.md"
REFERENCE = (
    ROOT
    / "runs"
    / "navier_stokes_galerkin_long_trajectory_probe_20260914"
    / "verification.json"
)
SCRIPT = Path(__file__).resolve()
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_galerkin_long_trajectory_audit_20260914"
    / "verification.json"
)
SCHEMA = "cassi.navier-stokes.galerkin-long-trajectory-audit.verification.v1"

NU = 0.1
T_END = 0.5
LONG_STEPS = 2048
REFINED_STEPS = 4096
TRUNCATION_STEPS = 512
CHECKPOINT_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
CONTROLS = ("shear", "abc", "rank_two", "near_rank")
GRID_SIZES = (9, 13)
VOLUME = (2.0 * math.pi) ** 3

PROJECTOR_TOLERANCE = 1e-14
DIVERGENCE_TOLERANCE = 1e-12
ENERGY_INCREMENT_TOLERANCE = 1e-10
DIRECT_TOLERANCE = 1e-10
REFERENCE_TOLERANCE = 1e-8
REFINEMENT_TOLERANCE = 1e-6


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_mode(table: dict[tuple[int, int, int], np.ndarray], key: tuple[int, int, int], component: int, value: complex) -> None:
    vector = table.setdefault(key, np.zeros(3, dtype=np.complex128))
    vector[component] += value


def add_sine(
    table: dict[tuple[int, int, int], np.ndarray],
    component: int,
    axis: int,
    frequency: int,
    amplitude: float = 1.0,
) -> None:
    key = [0, 0, 0]
    key[axis] = frequency
    positive = tuple(key)
    negative = tuple(-value for value in key)
    add_mode(table, positive, component, amplitude / (2.0j))
    add_mode(table, negative, component, -amplitude / (2.0j))


def add_cosine(
    table: dict[tuple[int, int, int], np.ndarray],
    component: int,
    axis: int,
    frequency: int,
    amplitude: float = 1.0,
) -> None:
    key = [0, 0, 0]
    key[axis] = frequency
    positive = tuple(key)
    negative = tuple(-value for value in key)
    add_mode(table, positive, component, amplitude / 2.0)
    add_mode(table, negative, component, amplitude / 2.0)


def scalar_sine(axis: int, frequency: int, amplitude: float = 1.0) -> dict[tuple[int, int, int], complex]:
    table: dict[tuple[int, int, int], complex] = {}
    key = [0, 0, 0]
    key[axis] = frequency
    positive = tuple(key)
    negative = tuple(-value for value in key)
    table[positive] = amplitude / (2.0j)
    table[negative] = -amplitude / (2.0j)
    return table


def scalar_cosine(axis: int, frequency: int, amplitude: float = 1.0) -> dict[tuple[int, int, int], complex]:
    table: dict[tuple[int, int, int], complex] = {}
    key = [0, 0, 0]
    key[axis] = frequency
    positive = tuple(key)
    negative = tuple(-value for value in key)
    table[positive] = amplitude / 2.0
    table[negative] = amplitude / 2.0
    return table


def multiply_scalar_modes(
    left: dict[tuple[int, int, int], complex],
    right: dict[tuple[int, int, int], complex],
) -> dict[tuple[int, int, int], complex]:
    result: dict[tuple[int, int, int], complex] = {}
    for left_key, left_value in left.items():
        for right_key, right_value in right.items():
            key = tuple(a + b for a, b in zip(left_key, right_key))
            result[key] = result.get(key, 0.0j) + left_value * right_value
    return result


def add_scalar_modes(
    table: dict[tuple[int, int, int], np.ndarray],
    component: int,
    scalar_modes: dict[tuple[int, int, int], complex],
    multiplier: float = 1.0,
) -> None:
    for key, value in scalar_modes.items():
        add_mode(table, key, component, multiplier * value)


def initial_coefficients(kind: str) -> dict[tuple[int, int, int], np.ndarray]:
    """Build analytic controls from their signed Fourier coefficients."""
    field: dict[tuple[int, int, int], np.ndarray] = {}
    if kind == "shear":
        add_sine(field, 0, axis=1, frequency=2, amplitude=-1.0)
        return field

    abc: dict[tuple[int, int, int], np.ndarray] = {}
    add_sine(abc, 0, axis=2, frequency=1)
    add_cosine(abc, 0, axis=1, frequency=1)
    add_sine(abc, 1, axis=0, frequency=1)
    add_cosine(abc, 1, axis=2, frequency=1)
    add_sine(abc, 2, axis=1, frequency=1)
    add_cosine(abc, 2, axis=0, frequency=1)
    if kind == "abc":
        return abc

    if kind not in {"rank_two", "near_rank"}:
        raise ValueError(f"unknown control {kind}")
    add_sine(field, 0, axis=1, frequency=1, amplitude=-1.0)
    add_sine(field, 2, axis=0, frequency=1)
    add_scalar_modes(
        field,
        2,
        multiply_scalar_modes(scalar_cosine(axis=0, frequency=1), scalar_sine(axis=1, frequency=1)),
    )
    if kind == "near_rank":
        for key, value in abc.items():
            vector = field.setdefault(key, np.zeros(3, dtype=np.complex128))
            vector += 0.1 * value
    return field


class DirectConvolutionBox:
    """Full signed Fourier Galerkin algebra with explicit mode convolution."""

    def __init__(self, cutoff: int) -> None:
        self.cutoff = int(cutoff)
        mode_list = []
        for kx in range(-self.cutoff, self.cutoff + 1):
            for ky in range(-self.cutoff, self.cutoff + 1):
                for kz in range(-self.cutoff, self.cutoff + 1):
                    if 0 < kx * kx + ky * ky + kz * kz <= self.cutoff * self.cutoff:
                        mode_list.append((kx, ky, kz))
        self.modes = tuple(mode_list)
        self.index = {mode: index for index, mode in enumerate(self.modes)}
        self.wave_numbers = np.asarray(self.modes, dtype=np.float64)
        self.k2 = np.einsum("ni,ni->n", self.wave_numbers, self.wave_numbers)
        self.projectors = np.eye(3, dtype=np.float64)[None, :, :] - (
            self.wave_numbers[:, :, None] * self.wave_numbers[:, None, :]
            / self.k2[:, None, None]
        )
        pair_p: list[int] = []
        pair_q: list[int] = []
        pair_target: list[int] = []
        for p_index, p in enumerate(self.modes):
            for q_index, q in enumerate(self.modes):
                target = self.index.get((p[0] + q[0], p[1] + q[1], p[2] + q[2]))
                if target is not None:
                    pair_p.append(p_index)
                    pair_q.append(q_index)
                    pair_target.append(target)
        self.pair_p = np.asarray(pair_p, dtype=np.int64)
        self.pair_q = np.asarray(pair_q, dtype=np.int64)
        self.pair_target = np.asarray(pair_target, dtype=np.int64)

        triple_p: list[int] = []
        triple_q: list[int] = []
        triple_r: list[int] = []
        for p_index, p in enumerate(self.modes):
            for q_index, q in enumerate(self.modes):
                r_index = self.index.get((-p[0] - q[0], -p[1] - q[1], -p[2] - q[2]))
                if r_index is not None:
                    triple_p.append(p_index)
                    triple_q.append(q_index)
                    triple_r.append(r_index)
        self.triple_p = np.asarray(triple_p, dtype=np.int64)
        self.triple_q = np.asarray(triple_q, dtype=np.int64)
        self.triple_r = np.asarray(triple_r, dtype=np.int64)

    def initial_state(self, kind: str) -> tuple[np.ndarray, float]:
        state = np.zeros((len(self.modes), 3), dtype=np.complex128)
        raw = initial_coefficients(kind)
        missing = sorted(set(raw) - set(self.index))
        if missing:
            raise ValueError(f"{kind} has modes outside N={self.cutoff}: {missing}")
        for key, value in raw.items():
            state[self.index[key]] = value
        projected = np.einsum("nij,nj->ni", self.projectors, state)
        projection_error = float(np.max(np.abs(projected - state)))
        return projected, projection_error

    def curl(self, state: np.ndarray) -> np.ndarray:
        return 1j * np.cross(self.wave_numbers, state)

    def strain(self, state: np.ndarray) -> np.ndarray:
        first = state[:, :, None] * self.wave_numbers[:, None, :]
        second = self.wave_numbers[:, :, None] * state[:, None, :]
        return 0.5j * (first + second)

    def rhs(self, state: np.ndarray) -> np.ndarray:
        dot = np.einsum(
            "pi,pi->p",
            state[self.pair_p],
            self.wave_numbers[self.pair_q],
        )
        contributions = 1j * dot[:, None] * state[self.pair_q]
        advective = np.zeros_like(state)
        np.add.at(advective, self.pair_target, contributions)
        projected = np.einsum("nij,nj->ni", self.projectors, advective)
        return -NU * self.k2[:, None] * state - projected

    def observables(self, state: np.ndarray, rhs: np.ndarray) -> dict[str, float]:
        omega = self.curl(state)
        omega_rhs = self.curl(rhs)
        enstrophy = VOLUME * float(np.sum(np.abs(omega) ** 2))
        palinstrophy = VOLUME * float(np.sum(self.k2[:, None] * np.abs(omega) ** 2))
        enstrophy_derivative = 2.0 * VOLUME * float(
            np.real(np.sum(np.conj(omega) * omega_rhs))
        )
        production = 0.5 * enstrophy_derivative + NU * palinstrophy
        energy = 0.5 * VOLUME * float(np.sum(np.abs(state) ** 2))
        divergence = np.einsum("ni,ni->n", self.wave_numbers, state)
        return {
            "production": production,
            "enstrophy": enstrophy,
            "palinstrophy": palinstrophy,
            "energy": energy,
            "divergence_residual": float(np.max(np.abs(divergence))),
            "remainder": production - NU * palinstrophy / 2.0,
        }

    def triple_production(self, state: np.ndarray) -> float:
        omega = self.curl(state)
        strain = self.strain(state)
        terms = np.einsum(
            "pi,pij,pj->p",
            omega[self.triple_p],
            strain[self.triple_q],
            omega[self.triple_r],
        )
        return VOLUME * float(np.real(np.sum(terms)))

    def grid_production(self, state: np.ndarray, grid_size: int) -> float:
        def to_grid(coefficients: np.ndarray) -> np.ndarray:
            array = np.zeros((grid_size, grid_size, grid_size), dtype=np.complex128)
            for index, mode in enumerate(self.modes):
                array[mode[0] % grid_size, mode[1] % grid_size, mode[2] % grid_size] = coefficients[index]
            return np.fft.ifftn(array) * float(grid_size**3)

        omega_coefficients = self.curl(state)
        omega = np.stack(
            [to_grid(omega_coefficients[:, component]) for component in range(3)],
            axis=-1,
        )
        gradient = np.empty((grid_size, grid_size, grid_size, 3, 3), dtype=np.complex128)
        for component in range(3):
            for direction in range(3):
                gradient[..., component, direction] = to_grid(
                    1j * self.wave_numbers[:, direction] * state[:, component]
                )
        strain = 0.5 * (gradient + np.swapaxes(gradient, -1, -2))
        stretching = np.einsum("...i,...ij,...j->...", omega, strain, omega)
        return VOLUME * float(np.real(np.mean(stretching)))


def rk4_step(
    box: DirectConvolutionBox,
    state: np.ndarray,
    dt: float,
    first_rhs: np.ndarray,
) -> tuple[np.ndarray, bool, bool]:
    second_state = state + 0.5 * dt * first_rhs
    second_rhs = box.rhs(second_state)
    third_state = state + 0.5 * dt * second_rhs
    third_rhs = box.rhs(third_state)
    fourth_state = state + dt * third_rhs
    fourth_rhs = box.rhs(fourth_state)
    updated = state + (dt / 6.0) * (
        first_rhs + 2.0 * second_rhs + 2.0 * third_rhs + fourth_rhs
    )
    states_finite = all(
        bool(np.all(np.isfinite(value)))
        for value in (state, second_state, third_state, fourth_state, updated)
    )
    rhs_finite = all(
        bool(np.all(np.isfinite(value)))
        for value in (first_rhs, second_rhs, third_rhs, fourth_rhs)
    )
    return updated, states_finite, rhs_finite


def run_trajectory(
    control: str,
    cutoff: int,
    steps: int,
    grid_sizes: tuple[int, ...] = GRID_SIZES,
) -> dict[str, Any]:
    box = DirectConvolutionBox(cutoff)
    state, projection_error = box.initial_state(control)
    dt = T_END / float(steps)
    checkpoint_steps = {
        int(round(fraction * steps)) for fraction in CHECKPOINT_FRACTIONS
    }
    first_rhs = box.rhs(state)
    initial = box.observables(state, first_rhs)
    states: dict[int, np.ndarray] = {0: state.copy()}
    checkpoint_observables: dict[int, dict[str, float]] = {0: initial}
    previous = initial
    previous_positive = max(0.0, initial["remainder"])
    integral = 0.0
    max_divergence = initial["divergence_residual"]
    max_positive_energy_increment = 0.0
    max_abs_production = abs(initial["production"])
    max_positive_remainder = previous_positive
    all_states_finite = bool(np.all(np.isfinite(state)))
    all_rhs_finite = bool(np.all(np.isfinite(first_rhs)))
    all_observables_finite = all(np.isfinite(value) for value in initial.values())

    for step in range(steps):
        state, stages_states_finite, stages_rhs_finite = rk4_step(
            box, state, dt, first_rhs
        )
        first_rhs = box.rhs(state)
        current = box.observables(state, first_rhs)
        all_states_finite &= stages_states_finite and bool(np.all(np.isfinite(state)))
        all_rhs_finite &= stages_rhs_finite and bool(np.all(np.isfinite(first_rhs)))
        all_observables_finite &= all(
            np.isfinite(value) for value in current.values()
        )
        current_positive = max(0.0, current["remainder"])
        integral += 0.5 * dt * (previous_positive + current_positive)
        max_positive_remainder = max(max_positive_remainder, current_positive)
        max_divergence = max(max_divergence, current["divergence_residual"])
        max_positive_energy_increment = max(
            max_positive_energy_increment,
            current["energy"] - previous["energy"],
        )
        max_abs_production = max(max_abs_production, abs(current["production"]))
        previous_positive = current_positive
        previous = current
        completed_step = step + 1
        if completed_step in checkpoint_steps:
            states[completed_step] = state.copy()
            checkpoint_observables[completed_step] = current

    checkpoints: list[dict[str, Any]] = []
    direct_convolution_max_difference = 0.0
    direct_convolution_max_relative_error = 0.0
    grid_max_difference = 0.0
    grid_max_relative_error = 0.0
    all_checkpoint_values_finite = True
    for fraction in CHECKPOINT_FRACTIONS:
        step = int(round(fraction * steps))
        checkpoint_state = states[step]
        observable = checkpoint_observables[step]
        triple = box.triple_production(checkpoint_state)
        triple_difference = abs(triple - observable["production"])
        triple_relative = triple_difference / max(1.0, observable["palinstrophy"])
        direct_convolution_max_difference = max(
            direct_convolution_max_difference, triple_difference
        )
        direct_convolution_max_relative_error = max(
            direct_convolution_max_relative_error, triple_relative
        )
        grid_values: dict[str, float] = {}
        grid_differences: dict[str, float] = {}
        for grid_size in grid_sizes:
            grid_value = box.grid_production(checkpoint_state, grid_size)
            grid_values[str(grid_size)] = grid_value
            grid_difference = abs(grid_value - triple)
            grid_relative = grid_difference / max(1.0, abs(observable["production"]))
            grid_differences[str(grid_size)] = grid_difference
            grid_max_difference = max(grid_max_difference, grid_difference)
            grid_max_relative_error = max(grid_max_relative_error, grid_relative)
        all_checkpoint_values_finite &= all(
            np.isfinite(value)
            for value in (
                *checkpoint_state.ravel(),
                *observable.values(),
                triple,
                triple_difference,
                triple_relative,
                *grid_values.values(),
                *grid_differences.values(),
            )
        )
        checkpoints.append(
            {
                "step": step,
                "time": step * dt,
                "spectral_production": observable["production"],
                "triple_convolution_production": triple,
                "triple_convolution_absolute_difference": triple_difference,
                "triple_convolution_relative_error": triple_relative,
                "grid_production": grid_values,
                "grid_triple_absolute_difference": grid_differences,
            }
        )

    return {
        "control": control,
        "cutoff": cutoff,
        "steps": steps,
        "dt": dt,
        "mode_count": len(box.modes),
        "pair_count": len(box.pair_target),
        "triple_count": len(box.triple_p),
        "projection_error": projection_error,
        "all_states_finite": all_states_finite,
        "all_rhs_finite": all_rhs_finite,
        "all_observables_finite": all_observables_finite,
        "all_checkpoint_values_finite": all_checkpoint_values_finite,
        "initial": initial,
        "final": previous,
        "positive_remainder_integral": float(integral),
        "positive_remainder_max": max_positive_remainder,
        "max_divergence_residual": max_divergence,
        "max_positive_energy_increment": max_positive_energy_increment,
        "max_abs_production": max_abs_production,
        "direct_convolution_max_difference": direct_convolution_max_difference,
        "direct_convolution_max_relative_error": direct_convolution_max_relative_error,
        "grid_max_difference": grid_max_difference,
        "grid_max_relative_error": grid_max_relative_error,
        "checkpoints": checkpoints,
    }


def relative_change(first: float, second: float) -> float:
    return abs(first - second) / max(1.0, abs(first))


def check(checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: Any) -> None:
    checks[name] = {"passed": bool(passed), "detail": detail}


def reference_rows() -> dict[tuple[str, int, int, str], dict[str, Any]]:
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    return {
        (
            row["control"],
            int(row["cutoff"]),
            int(row["steps"]),
            row["run"],
        ): row
        for row in reference["runs"]
    }


def run_audit() -> dict[str, Any]:
    projector_details: dict[str, dict[str, float]] = {}
    max_projector_symmetry = 0.0
    max_projector_idempotence = 0.0
    max_projector_divergence = 0.0
    for cutoff in (2, 4):
        box = DirectConvolutionBox(cutoff)
        symmetry = max(float(np.max(np.abs(projector - projector.T))) for projector in box.projectors)
        idempotence = max(
            float(np.max(np.abs(projector @ projector - projector)))
            for projector in box.projectors
        )
        annihilation = max(
            float(np.max(np.abs(wave @ projector)))
            for wave, projector in zip(box.wave_numbers, box.projectors)
        )
        projector_details[str(cutoff)] = {
            "mode_count": len(box.modes),
            "maximum_symmetry_error": symmetry,
            "maximum_idempotence_error": idempotence,
            "maximum_wave_annihilation_error": annihilation,
        }
        max_projector_symmetry = max(max_projector_symmetry, symmetry)
        max_projector_idempotence = max(max_projector_idempotence, idempotence)
        max_projector_divergence = max(max_projector_divergence, annihilation)

    long_records = [run_trajectory(control, 2, LONG_STEPS) for control in CONTROLS]
    refined_records = [
        run_trajectory(control, 2, REFINED_STEPS, grid_sizes=())
        for control in ("rank_two", "near_rank")
    ]
    truncation_records = [
        run_trajectory(control, cutoff, TRUNCATION_STEPS, grid_sizes=())
        for control in ("rank_two", "near_rank")
        for cutoff in (2, 4)
    ]

    checks: dict[str, dict[str, Any]] = {}
    all_records = long_records + refined_records + truncation_records
    scalar_finite = all(
        bool(np.isfinite(value))
        for record in all_records
        for value in (
            record["positive_remainder_integral"],
            record["positive_remainder_max"],
            record["max_divergence_residual"],
            record["max_positive_energy_increment"],
            record["max_abs_production"],
            record["direct_convolution_max_difference"],
            record["grid_max_difference"],
            record["initial"]["enstrophy"],
            record["final"]["enstrophy"],
        )
    )
    state_and_rhs_finite = all(
        record["all_states_finite"]
        and record["all_rhs_finite"]
        and record["all_observables_finite"]
        and record["all_checkpoint_values_finite"]
        for record in all_records
    )
    finite = scalar_finite and state_and_rhs_finite
    check(
        checks,
        "finite_states_and_observables",
        finite,
        {
            "records": len(all_records),
            "scalar_values_finite": scalar_finite,
            "state_rhs_observable_tracking": state_and_rhs_finite,
        },
    )

    check(
        checks,
        "orthogonal_leray_projectors",
        max_projector_symmetry <= PROJECTOR_TOLERANCE
        and max_projector_idempotence <= PROJECTOR_TOLERANCE
        and max_projector_divergence <= PROJECTOR_TOLERANCE,
        {
            "per_cutoff": projector_details,
            "bounds": {
                "symmetry": PROJECTOR_TOLERANCE,
                "idempotence": PROJECTOR_TOLERANCE,
                "wave_annihilation": PROJECTOR_TOLERANCE,
            },
        },
    )

    max_divergence = max(record["max_divergence_residual"] for record in all_records)
    check(
        checks,
        "divergence_free_direct_trajectories",
        max_divergence <= DIVERGENCE_TOLERANCE,
        {"maximum_residual": max_divergence, "bound": DIVERGENCE_TOLERANCE},
    )

    max_energy_increment = max(
        record["max_positive_energy_increment"] for record in all_records
    )
    energy_bounds = {
        f"{record['control']}:N={record['cutoff']}:steps={record['steps']}": ENERGY_INCREMENT_TOLERANCE
        * max(1.0, record["initial"]["energy"])
        for record in all_records
    }
    energy_excesses = {
        key: record["max_positive_energy_increment"] - energy_bounds[key]
        for key, record in (
            (
                f"{record['control']}:N={record['cutoff']}:steps={record['steps']}",
                record,
            )
            for record in all_records
        )
    }
    check(
        checks,
        "kinetic_energy_nonincrease",
        all(excess <= 0.0 for excess in energy_excesses.values()),
        {
            "maximum_positive_increment": max_energy_increment,
            "maximum_excess": max(energy_excesses.values()),
            "per_record_bounds": energy_bounds,
        },
    )

    heat_records = [record for record in long_records if record["control"] in {"shear", "abc"}]
    heat_bounds = {
        record["control"]: 1e-9 * max(1.0, record["initial"]["palinstrophy"])
        for record in heat_records
    }
    heat_excesses = {
        record["control"]: record["max_abs_production"] - heat_bounds[record["control"]]
        for record in heat_records
    }
    check(
        checks,
        "exact_heat_control_production",
        all(excess <= 0.0 for excess in heat_excesses.values()),
        {
            "maximum_abs_production": max(record["max_abs_production"] for record in heat_records),
            "maximum_excess": max(heat_excesses.values()),
            "per_control_bounds": heat_bounds,
        },
    )

    max_direct_difference = max(
        record["direct_convolution_max_difference"] for record in long_records
    )
    max_direct_relative = max(
        record["direct_convolution_max_relative_error"] for record in long_records
    )
    check(
        checks,
        "triple_convolution_matches_rhs_production",
        max_direct_relative <= DIRECT_TOLERANCE,
        {
            "maximum_absolute_difference": max_direct_difference,
            "maximum_relative_error": max_direct_relative,
            "maximum_excess": max_direct_relative - DIRECT_TOLERANCE,
            "bound": DIRECT_TOLERANCE,
        },
    )

    max_grid_relative = max(record["grid_max_relative_error"] for record in long_records)
    check(
        checks,
        "alias_free_grid_matches_triple_convolution",
        max_grid_relative <= DIRECT_TOLERANCE,
        {
            "maximum_absolute_difference": max(record["grid_max_difference"] for record in long_records),
            "maximum_relative_error": max_grid_relative,
            "bound": DIRECT_TOLERANCE,
            "grid_sizes": list(GRID_SIZES),
        },
    )

    reference = reference_rows()
    reference_differences: dict[str, dict[str, float]] = {}
    reference_excesses: dict[str, float] = {}
    for record in long_records:
        key = f"{record['control']}:N=2"
        expected = reference[(record["control"], 2, LONG_STEPS, "primary")]
        differences = {
            "positive_remainder_integral": abs(
                record["positive_remainder_integral"]
                - expected["positive_remainder_integral"]
            ),
            "positive_remainder_max": abs(
                record["positive_remainder_max"] - expected["positive_remainder_max"]
            ),
            "initial_enstrophy": abs(
                record["initial"]["enstrophy"] - expected["initial"]["enstrophy"]
            ),
            "final_enstrophy": abs(
                record["final"]["enstrophy"] - expected["final"]["enstrophy"]
            ),
        }
        reference_differences[key] = differences
        relative_integral = differences["positive_remainder_integral"] / max(
            1.0, abs(expected["positive_remainder_integral"])
        )
        reference_excesses[key] = relative_integral - REFERENCE_TOLERANCE
    check(
        checks,
        "independent_long_recomputation_matches_saved_receipt",
        all(excess <= 0.0 for excess in reference_excesses.values()),
        {
            "per_control_absolute_differences": reference_differences,
            "maximum_relative_integral_difference": max(
                value + REFERENCE_TOLERANCE for value in reference_excesses.values()
            ),
            "bound": REFERENCE_TOLERANCE,
        },
    )

    primary_by_control = {record["control"]: record for record in long_records}
    refined_by_control = {record["control"]: record for record in refined_records}
    timestep_changes = {
        control: relative_change(
            primary_by_control[control]["positive_remainder_integral"],
            refined_by_control[control]["positive_remainder_integral"],
        )
        for control in ("rank_two", "near_rank")
    }
    check(
        checks,
        "timestep_refinement",
        max(timestep_changes.values()) <= REFINEMENT_TOLERANCE,
        {
            "relative_changes": timestep_changes,
            "maximum": max(timestep_changes.values()),
            "bound": REFINEMENT_TOLERANCE,
        },
    )

    truncation_by_key = {
        (record["control"], int(record["cutoff"])): record
        for record in truncation_records
    }
    truncation_sequence = {
        control: {
            str(cutoff): truncation_by_key[(control, cutoff)]["positive_remainder_integral"]
            for cutoff in (2, 4)
        }
        for control in ("rank_two", "near_rank")
    }
    truncation_finite = all(
        np.isfinite(value)
        for values in truncation_sequence.values()
        for value in values.values()
    )
    check(
        checks,
        "finite_truncation_witness",
        bool(truncation_finite),
        {
            "steps": TRUNCATION_STEPS,
            "integrals": truncation_sequence,
            "differences": {
                control: values["4"] - values["2"]
                for control, values in truncation_sequence.items()
            },
        },
    )

    all_passed = all(entry["passed"] for entry in checks.values())
    return {
        "schema": SCHEMA,
        "status": "PASS" if all_passed else "FAIL",
        "classification": (
            "SUPPORTS—independent finite-mode reproducibility diagnostic only"
            if all_passed
            else "FAIL"
        ),
        "scope": {
            "nu": NU,
            "T": T_END,
            "long_controls": list(CONTROLS),
            "long_cutoff": 2,
            "long_steps": LONG_STEPS,
            "refined_controls": ["rank_two", "near_rank"],
            "refined_steps": REFINED_STEPS,
            "grid_sizes": list(GRID_SIZES),
            "truncation_cutoffs": [2, 4],
            "truncation_steps": TRUNCATION_STEPS,
            "theorem_target": "UNRESOLVED",
            "production_relative_compensation": "UNRESOLVED",
            "arbitrary_data_regularity": "UNRESOLVED",
        },
        "checks": checks,
        "projector_controls": projector_details,
        "long_recomputation": long_records,
        "timestep_refinement": refined_records,
        "truncation_witness": truncation_records,
        "truncation_sequence": truncation_sequence,
        "source_hashes": {
            "computations/navier-stokes-galerkin-long-trajectory-audit-prereg.md": sha256(PROTOCOL),
            "computations/verify_navier_stokes_galerkin_long_trajectory_audit.py": sha256(SCRIPT),
            "runs/navier_stokes_galerkin_long_trajectory_probe_20260914/verification.json": sha256(REFERENCE),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        record = run_trajectory("near_rank", 2, 16)
        if not np.isfinite(record["positive_remainder_integral"]):
            raise SystemExit("smoke produced a nonfinite integral")
        print(
            "direct-convolution smoke: PASS "
            f"(N={record['cutoff']}, modes={record['mode_count']}, steps={record['steps']})"
        )
        return 0
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing receipt: {output}")
    receipt = run_audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"status: {receipt['status']}")
    print(f"classification: {receipt['classification']}")
    for name, entry in receipt["checks"].items():
        print(f"{name}: {'PASS' if entry['passed'] else 'FAIL'}")
    print(f"long rows: {len(receipt['long_recomputation'])}")
    print(f"truncation rows: {len(receipt['truncation_witness'])}")
    print(f"receipt: {output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
