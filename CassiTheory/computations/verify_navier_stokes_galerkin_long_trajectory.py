#!/usr/bin/env python3
"""Run the fixed longer-horizon Fourier-Galerkin trajectory probe.

This verifier is self-contained and independent of the short-time trajectory
and endpoint-control verifiers. It measures a finite-cutoff positive remainder
for four periodic controls, with direct physical-space strain checks at five
checkpoints and timestep/product-grid refinements. It makes no regularity
claim.
The projected convection is evaluated through the exact identity
P((u dot grad)u)=P(omega cross u), with the gradient term removed by Leray
projection. The real Fourier field uses the nonnegative-k_z half-spectrum;
Parseval sums apply the corresponding one- or two-fold conjugate weights.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.fft import irfftn, rfftn

try:
    import torch
except ImportError:  # pragma: no cover - the production rig supplies ROCm Torch
    torch = None


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "navier-stokes-galerkin-long-trajectory-prereg.md"
NEAR_RANK_NOTE = ROOT / "turbulence" / "navier-stokes-near-rank-recovery-obstruction.md"
SCRIPT = Path(__file__).resolve()
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_galerkin_long_trajectory_probe_20260914"
    / "verification.json"
)
SCHEMA = "cassi.navier-stokes.galerkin-long-trajectory.verification.v1"

NU = 0.1
T_END = 0.5
CUTOFFS = (2, 4, 8, 16)
PRIMARY_STEPS = 2048
REFINED_STEPS = 4096
PRIMARY_GRID_FACTOR = 4
REFINED_GRID_FACTOR = 6
FFT_WORKERS = 1
MAX_WORKERS = 1
SMOKE_WORKERS = 4
DEFAULT_BACKEND = "numpy"
VOLUME = (2.0 * math.pi) ** 3
CONTROLS = ("shear", "abc", "rank_two", "near_rank")
CHECKPOINT_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)


class GalerkinBox:
    """Fourier-Galerkin algebra on an odd, quadratic-alias-free grid."""

    def __init__(self, cutoff: int, grid_size: int) -> None:
        self.cutoff = int(cutoff)
        self.grid_size = int(grid_size)
        full_frequencies = np.rint(
            np.fft.fftfreq(self.grid_size) * self.grid_size
        ).astype(np.int64)
        half_frequencies = np.rint(
            np.fft.rfftfreq(self.grid_size) * self.grid_size
        ).astype(np.int64)
        self.kx, self.ky, self.kz = np.meshgrid(
            full_frequencies,
            full_frequencies,
            half_frequencies,
            indexing="ij",
        )
        self.wave_numbers = np.stack(
            (self.kx, self.ky, self.kz), axis=-1
        ).astype(np.float64)
        self.k2 = (
            self.kx.astype(np.float64) ** 2
            + self.ky.astype(np.float64) ** 2
            + self.kz.astype(np.float64) ** 2
        )
        self.nonzero = self.k2 > 0.0
        self.shell = self.nonzero & (self.k2 <= float(self.cutoff**2))
        self.parseval_weight = np.where(self.kz == 0, 1.0, 2.0)

    def grid(self, coefficients: np.ndarray) -> np.ndarray:
        transformed = np.asarray(
            irfftn(
                coefficients,
                s=(self.grid_size, self.grid_size, self.grid_size),
                axes=(0, 1, 2),
                workers=FFT_WORKERS,
            )
        )
        return transformed * float(self.grid_size**3)

    def coefficients(self, values: np.ndarray) -> np.ndarray:
        transformed = np.asarray(
            rfftn(values, axes=(0, 1, 2), workers=FFT_WORKERS)
        )
        return transformed / float(self.grid_size**3)

    def project(self, coefficients: np.ndarray) -> np.ndarray:
        projected = np.zeros_like(coefficients)
        dot = (
            self.kx * coefficients[..., 0]
            + self.ky * coefficients[..., 1]
            + self.kz * coefficients[..., 2]
        )
        quotient = np.zeros_like(dot)
        np.divide(dot, self.k2, out=quotient, where=self.nonzero)
        projected[..., 0] = coefficients[..., 0] - self.kx * quotient
        projected[..., 1] = coefficients[..., 1] - self.ky * quotient
        projected[..., 2] = coefficients[..., 2] - self.kz * quotient
        projected[~self.shell] = 0.0
        return projected

    def right_hand_side(self, state: np.ndarray) -> np.ndarray:
        velocity = self.grid(state)
        vorticity = self.grid(self.curl(state))
        rotational = np.cross(vorticity, velocity)
        rotational_coefficients = self.coefficients(rotational)
        projected_rotational = self.project(rotational_coefficients)
        result = -NU * self.k2[..., None] * state - projected_rotational
        result[~self.shell] = 0.0
        return result

    def curl(self, state: np.ndarray) -> np.ndarray:
        return np.stack(
            (
                1j * (self.ky * state[..., 2] - self.kz * state[..., 1]),
                1j * (self.kz * state[..., 0] - self.kx * state[..., 2]),
                1j * (self.kx * state[..., 1] - self.ky * state[..., 0]),
            ),
            axis=-1,
        )

    def strain_and_vorticity(
        self, state: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        gradient_coefficients = (
            1j * state[..., :, None] * self.wave_numbers[..., None, :]
        )
        gradient = self.grid(gradient_coefficients)
        strain = 0.5 * (gradient + np.swapaxes(gradient, -1, -2))
        vorticity = self.grid(self.curl(state))
        return strain, vorticity

    def spectral_observables(
        self, state: np.ndarray, rhs: np.ndarray
    ) -> dict[str, float]:
        vorticity_coefficients = self.curl(state)
        vorticity_rhs = self.curl(rhs)
        parseval_weight = self.parseval_weight[..., None]
        palinstrophy = VOLUME * float(
            np.sum(
                parseval_weight
                * self.k2[..., None]
                * np.abs(vorticity_coefficients) ** 2
            )
        )
        enstrophy_derivative = 2.0 * VOLUME * float(
            np.real(
                np.sum(
                    parseval_weight
                    * np.conj(vorticity_coefficients)
                    * vorticity_rhs
                )
            )
        )
        production = 0.5 * enstrophy_derivative + NU * palinstrophy
        enstrophy = VOLUME * float(
            np.sum(parseval_weight * np.abs(vorticity_coefficients) ** 2)
        )
        energy = 0.5 * VOLUME * float(
            np.sum(parseval_weight * np.abs(state) ** 2)
        )
        divergence = (
            self.kx * state[..., 0]
            + self.ky * state[..., 1]
            + self.kz * state[..., 2]
        )
        return {
            "production": production,
            "enstrophy": enstrophy,
            "palinstrophy": palinstrophy,
            "energy": energy,
            "divergence_residual": float(np.max(np.abs(divergence))),
            "remainder": production - NU * palinstrophy / 2.0,
        }

    def direct_production(self, state: np.ndarray) -> float:
        strain, vorticity = self.strain_and_vorticity(state)
        stretching = np.einsum(
            "...i,...ij,...j->...", vorticity, strain, vorticity
        )
        return VOLUME * float(np.real(np.mean(stretching)))

class TorchGalerkinBox:
    """The same half-spectrum Galerkin algebra executed on the ROCm GPU."""

    def __init__(self, cutoff: int, grid_size: int) -> None:
        if torch is None or not torch.cuda.is_available():
            raise RuntimeError("the long trajectory probe requires a CUDA/ROCm GPU")
        self.cutoff = int(cutoff)
        self.grid_size = int(grid_size)
        self.device = torch.device("cuda")
        real_frequencies = np.rint(
            np.fft.fftfreq(self.grid_size) * self.grid_size
        ).astype(np.int64)
        half_frequencies = np.rint(
            np.fft.rfftfreq(self.grid_size) * self.grid_size
        ).astype(np.int64)
        self.kx, self.ky, self.kz = (
            torch.as_tensor(values, dtype=torch.float64, device=self.device)
            for values in np.meshgrid(
                real_frequencies,
                real_frequencies,
                half_frequencies,
                indexing="ij",
            )
        )
        self.wave_numbers = torch.stack(
            (self.kx, self.ky, self.kz), dim=-1
        )
        self.k2 = self.kx**2 + self.ky**2 + self.kz**2
        self.nonzero = self.k2 > 0.0
        self.shell = self.nonzero & (self.k2 <= float(self.cutoff**2))
        self.parseval_weight = torch.where(
            self.kz == 0.0,
            torch.ones_like(self.kz),
            torch.full_like(self.kz, 2.0),
        )

    def grid(self, coefficients: Any) -> Any:
        return torch.fft.irfftn(
            coefficients,
            s=(self.grid_size, self.grid_size, self.grid_size),
            dim=(0, 1, 2),
            norm="backward",
        ) * float(self.grid_size**3)

    def coefficients(self, values: Any) -> Any:
        return torch.fft.rfftn(
            values, dim=(0, 1, 2), norm="backward"
        ) / float(self.grid_size**3)

    def project(self, coefficients: Any) -> Any:
        projected = torch.zeros_like(coefficients)
        dot = (
            self.kx * coefficients[..., 0]
            + self.ky * coefficients[..., 1]
            + self.kz * coefficients[..., 2]
        )
        safe_k2 = torch.where(self.nonzero, self.k2, torch.ones_like(self.k2))
        quotient = dot / safe_k2
        quotient = torch.where(self.nonzero, quotient, torch.zeros_like(quotient))
        projected[..., 0] = coefficients[..., 0] - self.kx * quotient
        projected[..., 1] = coefficients[..., 1] - self.ky * quotient
        projected[..., 2] = coefficients[..., 2] - self.kz * quotient
        return projected.masked_fill(~self.shell[..., None], 0.0)

    def curl(self, state: Any) -> Any:
        return torch.stack(
            (
                1j * (self.ky * state[..., 2] - self.kz * state[..., 1]),
                1j * (self.kz * state[..., 0] - self.kx * state[..., 2]),
                1j * (self.kx * state[..., 1] - self.ky * state[..., 0]),
            ),
            dim=-1,
        )

    def right_hand_side(self, state: Any) -> Any:
        velocity = self.grid(state)
        vorticity = self.grid(self.curl(state))
        rotational = torch.cross(vorticity, velocity, dim=-1)
        rotational_coefficients = self.coefficients(rotational)
        projected_rotational = self.project(rotational_coefficients)
        result = -NU * self.k2[..., None] * state - projected_rotational
        return result.masked_fill(~self.shell[..., None], 0.0)

    def strain_and_vorticity(self, state: Any) -> tuple[Any, Any]:
        gradient_coefficients = (
            1j * state[..., :, None] * self.wave_numbers[..., None, :]
        )
        gradient = self.grid(gradient_coefficients)
        strain = 0.5 * (gradient + torch.swapaxes(gradient, -1, -2))
        return strain, self.grid(self.curl(state))

    def spectral_observables(self, state: Any, rhs: Any) -> dict[str, float]:
        vorticity_coefficients = self.curl(state)
        vorticity_rhs = self.curl(rhs)
        parseval_weight = self.parseval_weight[..., None]
        palinstrophy = VOLUME * float(
            torch.sum(
                parseval_weight
                * self.k2[..., None]
                * torch.abs(vorticity_coefficients) ** 2
            ).item()
        )
        enstrophy_derivative = 2.0 * VOLUME * float(
            torch.real(
                torch.sum(
                    parseval_weight
                    * torch.conj(vorticity_coefficients)
                    * vorticity_rhs
                )
            ).item()
        )
        production = 0.5 * enstrophy_derivative + NU * palinstrophy
        enstrophy = VOLUME * float(
            torch.sum(
                parseval_weight * torch.abs(vorticity_coefficients) ** 2
            ).item()
        )
        energy = 0.5 * VOLUME * float(
            torch.sum(parseval_weight * torch.abs(state) ** 2).item()
        )
        divergence = (
            self.kx * state[..., 0]
            + self.ky * state[..., 1]
            + self.kz * state[..., 2]
        )
        return {
            "production": production,
            "enstrophy": enstrophy,
            "palinstrophy": palinstrophy,
            "energy": energy,
            "divergence_residual": float(torch.abs(divergence).max().item()),
            "remainder": production - NU * palinstrophy / 2.0,
        }

    def initial_state(self, kind: str) -> tuple[Any, float, float]:
        axis = (
            2.0
            * math.pi
            * torch.arange(
                self.grid_size, dtype=torch.float64, device=self.device
            )
            / self.grid_size
        )
        x, y, z = torch.meshgrid(axis, axis, axis, indexing="ij")
        zeros = torch.zeros_like(x)
        if kind == "shear":
            components = (-torch.sin(2.0 * y), zeros, zeros)
        elif kind == "abc":
            components = (
                torch.sin(z) + torch.cos(y),
                torch.sin(x) + torch.cos(z),
                torch.sin(y) + torch.cos(x),
            )
        elif kind in {"rank_two", "near_rank"}:
            base = (
                -torch.sin(y),
                zeros,
                torch.sin(x) + torch.cos(x) * torch.sin(y),
            )
            if kind == "rank_two":
                components = base
            else:
                perturbation = (
                    torch.sin(z) + torch.cos(y),
                    torch.sin(x) + torch.cos(z),
                    torch.sin(y) + torch.cos(x),
                )
                components = tuple(
                    base[index] + 0.1 * perturbation[index]
                    for index in range(3)
                )
        else:
            raise ValueError(f"unknown control {kind}")
        values = torch.stack(components, dim=-1)
        raw = self.coefficients(values)
        projected = self.project(raw)
        projection_error = float(torch.abs(raw - projected).max().item())
        reconstructed = self.coefficients(self.grid(projected))
        roundtrip_error = float(
            torch.abs(reconstructed - projected).max().item()
        )
        return projected, projection_error, roundtrip_error

    def direct_production(self, state: Any) -> float:
        strain, vorticity = self.strain_and_vorticity(state)
        stretching = torch.einsum(
            "...i,...ij,...j->...", vorticity, strain, vorticity
        )
        return VOLUME * float(torch.real(stretching).mean().item())


def initial_field(
    kind: str, x: np.ndarray, y: np.ndarray, z: np.ndarray
) -> np.ndarray:
    zeros = np.zeros_like(x)
    if kind == "shear":
        components = (-np.sin(2.0 * y), zeros, zeros)
    elif kind == "abc":
        components = (
            np.sin(z) + np.cos(y),
            np.sin(x) + np.cos(z),
            np.sin(y) + np.cos(x),
        )
    elif kind in {"rank_two", "near_rank"}:
        base = (
            -np.sin(y),
            zeros,
            np.sin(x) + np.cos(x) * np.sin(y),
        )
        if kind == "rank_two":
            components = base
        else:
            perturbation = (
                np.sin(z) + np.cos(y),
                np.sin(x) + np.cos(z),
                np.sin(y) + np.cos(x),
            )
            components = tuple(
                base[index] + 0.1 * perturbation[index]
                for index in range(3)
            )
    else:
        raise ValueError(f"unknown control {kind}")
    return np.stack(components, axis=-1).astype(np.float64)


def initial_state(
    box: GalerkinBox, kind: str
) -> tuple[np.ndarray, float, float]:
    axis = 2.0 * math.pi * np.arange(box.grid_size) / box.grid_size
    x, y, z = np.meshgrid(axis, axis, axis, indexing="ij")
    raw = box.coefficients(initial_field(kind, x, y, z))
    projected = box.project(raw)
    projection_error = float(np.max(np.abs(raw - projected)))
    reconstructed = box.coefficients(box.grid(projected))
    roundtrip_error = float(np.max(np.abs(reconstructed - projected)))
    return projected, projection_error, roundtrip_error


def rk4_update(
    box: Any,
    state: Any,
    dt: float,
    first_rhs: Any,
) -> Any:
    second_rhs = box.right_hand_side(state + 0.5 * dt * first_rhs)
    third_rhs = box.right_hand_side(state + 0.5 * dt * second_rhs)
    fourth_rhs = box.right_hand_side(state + dt * third_rhs)
    updated = state + (dt / 6.0) * (
        first_rhs + 2.0 * second_rhs + 2.0 * third_rhs + fourth_rhs
    )
    if isinstance(box, TorchGalerkinBox):
        return updated.masked_fill(~box.shell[..., None], 0.0)
    updated[~box.shell] = 0.0
    return updated


def integrate_control(
    kind: str,
    cutoff: int,
    grid_size: int,
    steps: int,
    backend: str = DEFAULT_BACKEND,
) -> dict[str, Any]:
    if backend == "torch":
        box: Any = TorchGalerkinBox(cutoff, grid_size)
        state, projection_error, roundtrip_error = box.initial_state(kind)
    elif backend == "numpy":
        box = GalerkinBox(cutoff, grid_size)
        state, projection_error, roundtrip_error = initial_state(box, kind)
    else:
        raise ValueError(f"unknown backend {backend}")
    dt = T_END / float(steps)
    first_rhs = box.right_hand_side(state)
    initial = box.spectral_observables(state, first_rhs)
    checkpoint_steps = {
        int(round(fraction * steps)) for fraction in CHECKPOINT_FRACTIONS
    }
    checkpoints: list[dict[str, float]] = []
    max_direct_abs = 0.0
    max_direct_difference = 0.0
    max_direct_relative_error = 0.0

    def record_checkpoint(index: int, observables: dict[str, float]) -> None:
        nonlocal max_direct_abs
        nonlocal max_direct_difference
        nonlocal max_direct_relative_error
        direct = box.direct_production(state)
        difference = abs(direct - observables["production"])
        relative_error = difference / max(1.0, observables["palinstrophy"])
        max_direct_abs = max(max_direct_abs, abs(direct))
        max_direct_difference = max(max_direct_difference, difference)
        max_direct_relative_error = max(
            max_direct_relative_error, relative_error
        )
        checkpoints.append(
            {
                "step": float(index),
                "time": float(index * dt),
                "direct_production": direct,
                "spectral_production": observables["production"],
                "absolute_difference": difference,
                "relative_error": relative_error,
            }
        )

    record_checkpoint(0, initial)
    previous = initial
    previous_positive = max(0.0, initial["remainder"])
    integral = 0.0
    max_divergence = initial["divergence_residual"]
    max_positive_energy_increment = 0.0
    max_abs_production = abs(initial["production"])
    max_positive_remainder = previous_positive

    for index in range(steps):
        state = rk4_update(box, state, dt, first_rhs)
        first_rhs = box.right_hand_side(state)
        current = box.spectral_observables(state, first_rhs)
        current_positive = max(0.0, current["remainder"])
        integral += 0.5 * dt * (previous_positive + current_positive)
        previous_positive = current_positive
        max_positive_remainder = max(
            max_positive_remainder, current_positive
        )
        max_divergence = max(
            max_divergence, current["divergence_residual"]
        )
        max_positive_energy_increment = max(
            max_positive_energy_increment,
            current["energy"] - previous["energy"],
        )
        max_abs_production = max(
            max_abs_production, abs(current["production"])
        )
        previous = current
        if index + 1 in checkpoint_steps:
            record_checkpoint(index + 1, current)

    return {
        "control": kind,
        "cutoff": cutoff,
        "grid_size": grid_size,
        "steps": steps,
        "backend": backend,
        "dt": dt,
        "projection_error": projection_error,
        "roundtrip_error": roundtrip_error,
        "initial": initial,
        "final": previous,
        "positive_remainder_integral": float(integral),
        "positive_remainder_max": max_positive_remainder,
        "max_divergence_residual": max_divergence,
        "max_positive_energy_increment": max_positive_energy_increment,
        "max_abs_production": max_abs_production,
        "direct_checkpoints": checkpoints,
        "direct_production_max_abs": max_direct_abs,
        "max_direct_spectral_difference": max_direct_difference,
        "max_direct_spectral_relative_error": max_direct_relative_error,
    }


def execute_case(
    specification: tuple[str, int, int, int, str, str]
) -> dict[str, Any]:
    control, cutoff, grid_size, steps, label, backend = specification
    record = integrate_control(
        control, cutoff, grid_size, steps, backend=backend
    )
    record["run"] = label
    return record


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_change(left: float, right: float) -> float:
    return abs(left - right) / max(1.0, abs(left), abs(right))


def all_finite(records: list[dict[str, Any]]) -> bool:
    scalar_fields = (
        "positive_remainder_integral",
        "positive_remainder_max",
        "max_divergence_residual",
        "max_positive_energy_increment",
        "max_abs_production",
        "direct_production_max_abs",
        "max_direct_spectral_difference",
        "max_direct_spectral_relative_error",
    )
    for record in records:
        values = [record[field] for field in scalar_fields]
        values.extend(
            (
                record["initial"]["production"],
                record["initial"]["palinstrophy"],
                record["initial"]["energy"],
                record["final"]["enstrophy"],
            )
        )
        values.extend(
            value
            for checkpoint in record["direct_checkpoints"]
            for value in (
                checkpoint["direct_production"],
                checkpoint["spectral_production"],
                checkpoint["absolute_difference"],
                checkpoint["relative_error"],
            )
        )
        if not all(math.isfinite(float(value)) for value in values):
            return False
    return True


def build_specifications(
    backend: str = DEFAULT_BACKEND,
) -> list[tuple[str, int, int, int, str, str]]:
    specifications: list[tuple[str, int, int, int, str, str]] = []
    for control in CONTROLS:
        for cutoff in CUTOFFS:
            specifications.extend(
                (
                    (
                        control,
                        cutoff,
                        PRIMARY_GRID_FACTOR * cutoff + 1,
                        PRIMARY_STEPS,
                        "primary",
                        backend,
                    ),
                    (
                        control,
                        cutoff,
                        PRIMARY_GRID_FACTOR * cutoff + 1,
                        REFINED_STEPS,
                        "time_refined",
                        backend,
                    ),
                    (
                        control,
                        cutoff,
                        REFINED_GRID_FACTOR * cutoff + 1,
                        PRIMARY_STEPS,
                        "grid_refined",
                        backend,
                    ),
                )
            )
    return specifications


def run_probe(backend: str = DEFAULT_BACKEND) -> dict[str, Any]:
    specifications = build_specifications(backend)
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        records = list(executor.map(execute_case, specifications))
    by_key = {
        (record["control"], int(record["cutoff"]), record["run"]): record
        for record in records
    }

    checks: dict[str, dict[str, Any]] = {}

    def check(name: str, passed: bool, detail: Any) -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    expected_count = len(CONTROLS) * len(CUTOFFS) * 3
    expected_specifications = set(specifications)
    observed_specifications = {
        (
            record["control"],
            int(record["cutoff"]),
            int(record["grid_size"]),
            int(record["steps"]),
            record["run"],
            record["backend"],
        )
        for record in records
    }
    check(
        "declared_matrix_integrity",
        len(specifications) == expected_count
        and len(expected_specifications) == expected_count
        and len(records) == expected_count
        and observed_specifications == expected_specifications,
        {
            "expected_count": expected_count,
            "scheduled_count": len(specifications),
            "unique_scheduled_count": len(expected_specifications),
            "completed_count": len(records),
            "unique_completed_count": len(observed_specifications),
        },
    )
    check("finite_states_and_observables", all_finite(records), {"runs": len(records)})

    checkpoint_counts = {
        f"{record['control']}:N={record['cutoff']}:{record['run']}": len(
            record["direct_checkpoints"]
        )
        for record in records
    }
    check(
        "direct_checkpoint_coverage",
        all(count == len(CHECKPOINT_FRACTIONS) for count in checkpoint_counts.values()),
        checkpoint_counts,
    )

    max_direct_relative_error = max(
        record["max_direct_spectral_relative_error"] for record in records
    )
    check(
        "direct_strain_production_agreement",
        max_direct_relative_error <= 1e-9,
        {"maximum_relative_error": max_direct_relative_error, "bound": 1e-9},
    )

    max_divergence = max(record["max_divergence_residual"] for record in records)
    check(
        "divergence_residual",
        max_divergence <= 1e-10,
        {"maximum": max_divergence, "bound": 1e-10},
    )

    max_energy_increment = max(
        record["max_positive_energy_increment"] for record in records
    )
    energy_bound = 1e-9 * max(
        1.0,
        max(record["initial"]["energy"] for record in records),
    )
    check(
        "kinetic_energy_dissipation",
        max_energy_increment <= energy_bound,
        {"maximum_positive_increment": max_energy_increment, "bound": energy_bound},
    )

    heat_records = [
        record for record in records if record["control"] in {"shear", "abc"}
    ]
    heat_case_bounds = {
        f"{record['control']}:N={record['cutoff']}:{record['run']}": 1e-9
        * max(1.0, record["initial"]["palinstrophy"])
        for record in heat_records
    }
    heat_case_excesses = {
        key: record["direct_production_max_abs"] - heat_case_bounds[key]
        for key, record in (
            (
                f"{record['control']}:N={record['cutoff']}:{record['run']}",
                record,
            )
            for record in heat_records
        )
    }
    heat_production = max(
        record["direct_production_max_abs"] for record in heat_records
    )
    check(
        "exact_heat_control_production",
        all(excess <= 0.0 for excess in heat_case_excesses.values()),
        {
            "maximum_abs_direct_production": heat_production,
            "maximum_excess": max(heat_case_excesses.values()),
            "per_run_bounds": heat_case_bounds,
        },
    )

    endpoint_remainders = {
        f"{control}:N={cutoff}": by_key[(control, cutoff, "primary")]["initial"][
            "remainder"
        ]
        for control in ("rank_two", "near_rank")
        for cutoff in CUTOFFS
    }
    check(
        "positive_endpoint_controls",
        all(value > 0.0 for value in endpoint_remainders.values()),
        endpoint_remainders,
    )

    timestep_relative_change = {
        f"{control}:N={cutoff}": relative_change(
            by_key[(control, cutoff, "primary")]["positive_remainder_integral"],
            by_key[(control, cutoff, "time_refined")]["positive_remainder_integral"],
        )
        for control in CONTROLS
        for cutoff in CUTOFFS
    }
    max_timestep_change = max(timestep_relative_change.values())
    check(
        "timestep_refinement",
        max_timestep_change <= 1e-6,
        {"maximum_relative_change": max_timestep_change, "bound": 1e-6},
    )

    grid_relative_change = {
        f"{control}:N={cutoff}": relative_change(
            by_key[(control, cutoff, "primary")]["positive_remainder_integral"],
            by_key[(control, cutoff, "grid_refined")]["positive_remainder_integral"],
        )
        for control in CONTROLS
        for cutoff in CUTOFFS
    }
    max_grid_change = max(grid_relative_change.values())
    check(
        "product_grid_refinement",
        max_grid_change <= 1e-6,
        {"maximum_relative_change": max_grid_change, "bound": 1e-6},
    )

    max_projection = max(record["projection_error"] for record in records)
    max_roundtrip = max(record["roundtrip_error"] for record in records)
    check(
        "initial_fourier_projection_and_roundtrip",
        max_projection <= 1e-10 and max_roundtrip <= 1e-12,
        {
            "maximum_projection_error": max_projection,
            "maximum_roundtrip_error": max_roundtrip,
        },
    )

    cutoff_sequence = {
        control: {
            str(cutoff): by_key[(control, cutoff, "primary")][
                "positive_remainder_integral"
            ]
            for cutoff in CUTOFFS
        }
        for control in CONTROLS
    }
    all_passed = all(entry["passed"] for entry in checks.values())
    return {
        "schema": SCHEMA,
        "status": "PASS" if all_passed else "FAIL",
        "classification": (
            "SUPPORTS—longer-horizon finite-mode trajectory measurement only"
            if all_passed
            else "FAIL"
        ),
        "scope": {
            "backend": backend,
            "reference_backend": "numpy",
            "nu": NU,
            "T": T_END,
            "cutoffs": list(CUTOFFS),
            "primary_steps": PRIMARY_STEPS,
            "refined_steps": REFINED_STEPS,
            "primary_grid": "4N+1",
            "refined_grid": "6N+1",
            "checkpoint_fractions": list(CHECKPOINT_FRACTIONS),
            "theorem_target": "UNRESOLVED",
            "production_relative_compensation": "UNRESOLVED",
            "arbitrary_data_regularity": "UNRESOLVED",
        },
        "checks": checks,
        "refinement": {
            "timestep_relative_change": timestep_relative_change,
            "grid_relative_change": grid_relative_change,
        },
        "cutoff_sequence": cutoff_sequence,
        "runs": records,
        "source_hashes": {
            "computations/navier-stokes-galerkin-long-trajectory-prereg.md": sha256(
                PROTOCOL
            ),
            "computations/verify_navier_stokes_galerkin_long_trajectory.py": sha256(
                SCRIPT
            ),
            "turbulence/navier-stokes-near-rank-recovery-obstruction.md": sha256(
                NEAR_RANK_NOTE
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def run_scheduler_smoke(backend: str = DEFAULT_BACKEND) -> None:
    smoke_cutoff = 4
    smoke_steps = 16
    specifications = [
        (
            control,
            smoke_cutoff,
            PRIMARY_GRID_FACTOR * smoke_cutoff + 1,
            smoke_steps,
            "smoke",
            backend,
        )
        for control in CONTROLS
    ]
    with ProcessPoolExecutor(
        max_workers=min(SMOKE_WORKERS, len(specifications))
    ) as executor:
        records = list(executor.map(execute_case, specifications))
    observed = {
        (
            record["control"],
            int(record["cutoff"]),
            int(record["grid_size"]),
            int(record["steps"]),
            record["run"],
            record["backend"],
        )
        for record in records
    }
    if len(records) != len(specifications) or observed != set(specifications):
        raise RuntimeError("scheduler smoke did not complete its unique control rows")
    if not all_finite(records):
        raise RuntimeError("scheduler smoke produced a nonfinite observable")
    if any(
        len(record["direct_checkpoints"]) != len(CHECKPOINT_FRACTIONS)
        for record in records
    ):
        raise RuntimeError("scheduler smoke missed a direct checkpoint")
    if max(
        record["max_direct_spectral_relative_error"] for record in records
    ) > 1e-9:
        raise RuntimeError("scheduler smoke failed direct strain agreement")
    print(
        f"scheduler smoke: PASS (backend={backend}, "
        f"N={smoke_cutoff}, {len(records)} controls)"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--backend", choices=("numpy", "torch"), default=DEFAULT_BACKEND)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        run_scheduler_smoke(args.backend)
        return 0
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing receipt: {output}")
    receipt = run_probe(args.backend)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"status: {receipt['status']}")
    print(f"classification: {receipt['classification']}")
    for name, entry in receipt["checks"].items():
        print(f"{name}: {'PASS' if entry['passed'] else 'FAIL'}")
    print(f"runs: {len(receipt['runs'])}")
    print(f"receipt: {output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
