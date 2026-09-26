#!/usr/bin/env python3
"""Run a short-time Fourier-Galerkin trajectory probe for periodic Navier–Stokes.

The implementation is intentionally self-contained. It does not import the
endpoint-control verifier or the replica-coherence verifier. It measures the
finite-cutoff positive remainder and qualifies Fourier reconstruction, Leray
projection, timestep refinement, and product-grid refinement. It makes no
continuation or regularity claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import numpy as np
from scipy.fft import fftn, ifftn


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "navier-stokes-galerkin-trajectory-prereg.md"
NEAR_RANK_NOTE = ROOT / "turbulence" / "navier-stokes-near-rank-recovery-obstruction.md"
SCRIPT = Path(__file__).resolve()
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_galerkin_trajectory_probe_20260913"
    / "verification.json"
)
SCHEMA = "cassi.navier-stokes.galerkin-trajectory.verification.v1"

NU = 0.1
T_END = 0.25
CUTOFFS = (2, 4, 8)
PRIMARY_STEPS = 1024
REFINED_STEPS = 2048
GRID_FACTORS = (4, 6)
VOLUME = (2.0 * math.pi) ** 3


class SpectralGalerkin:
    """Fourier-Galerkin algebra on an odd, alias-free product grid."""

    def __init__(self, cutoff: int, grid_size: int) -> None:
        self.cutoff = int(cutoff)
        self.grid_size = int(grid_size)
        frequencies = np.rint(
            np.fft.fftfreq(self.grid_size) * self.grid_size
        ).astype(np.int64)
        self.kx, self.ky, self.kz = np.meshgrid(
            frequencies, frequencies, frequencies, indexing="ij"
        )
        self.wave_numbers = np.stack(
            (self.kx, self.ky, self.kz), axis=-1
        ).astype(np.float64)
        self.k2 = (
            self.kx.astype(np.float64) ** 2
            + self.ky.astype(np.float64) ** 2
            + self.kz.astype(np.float64) ** 2
        )
        self.shell = (self.k2 > 0.0) & (self.k2 <= float(self.cutoff**2))
        self.nonzero = self.k2 > 0.0

    def to_grid(self, coefficients: np.ndarray) -> np.ndarray:
        return ifftn(
            coefficients, axes=(0, 1, 2), workers=-1
        ) * float(self.grid_size**3)

    def to_coefficients(self, values: np.ndarray) -> np.ndarray:
        return fftn(
            values, axes=(0, 1, 2), workers=-1
        ) / float(self.grid_size**3)

    def leray(self, coefficients: np.ndarray) -> np.ndarray:
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

    def rhs(self, coefficients: np.ndarray) -> np.ndarray:
        velocity = self.to_grid(coefficients)
        nonlinear = np.zeros_like(velocity)
        for direction, wave_numbers in enumerate(
            (self.kx, self.ky, self.kz)
        ):
            derivative = self.to_grid(
                1j * wave_numbers[..., None] * coefficients
            )
            nonlinear += velocity[..., direction, None] * derivative
        nonlinear_coefficients = self.to_coefficients(nonlinear)
        projected_nonlinear = self.leray(nonlinear_coefficients)
        result = -NU * self.k2[..., None] * coefficients - projected_nonlinear
        result[~self.shell] = 0.0
        return result

    def curl(self, coefficients: np.ndarray) -> np.ndarray:
        return np.stack(
            [
                1j * (
                    self.ky * coefficients[..., 2]
                    - self.kz * coefficients[..., 1]
                ),
                1j * (
                    self.kz * coefficients[..., 0]
                    - self.kx * coefficients[..., 2]
                ),
                1j * (
                    self.kx * coefficients[..., 1]
                    - self.ky * coefficients[..., 0]
                ),
            ],
            axis=-1,
        )

    def strain_and_vorticity(
        self, coefficients: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        gradient_coefficients = (
            1j * coefficients[..., :, None] * self.wave_numbers[..., None, :]
        )
        gradient = self.to_grid(gradient_coefficients)
        strain = 0.5 * (gradient + np.swapaxes(gradient, -1, -2))
        return strain, self.to_grid(self.curl(coefficients))

    def observables_from_rhs(
        self, coefficients: np.ndarray, rhs: np.ndarray
    ) -> dict[str, float]:
        omega_coefficients = self.curl(coefficients)
        omega_rhs = self.curl(rhs)
        palinstrophy = VOLUME * float(
            np.sum(self.k2[..., None] * np.abs(omega_coefficients) ** 2)
        )
        enstrophy_derivative = 2.0 * VOLUME * float(
            np.real(np.sum(np.conj(omega_coefficients) * omega_rhs))
        )
        production = 0.5 * enstrophy_derivative + NU * palinstrophy
        enstrophy = VOLUME * float(np.sum(np.abs(omega_coefficients) ** 2))
        energy = 0.5 * VOLUME * float(np.sum(np.abs(coefficients) ** 2))
        divergence = (
            self.kx * coefficients[..., 0]
            + self.ky * coefficients[..., 1]
            + self.kz * coefficients[..., 2]
        )
        return {
            "production": production,
            "enstrophy": enstrophy,
            "palinstrophy": palinstrophy,
            "energy": energy,
            "divergence_residual": float(np.max(np.abs(divergence))),
            "remainder": production - NU * palinstrophy / 2.0,
        }

    def direct_production(self, coefficients: np.ndarray) -> float:
        strain, vorticity = self.strain_and_vorticity(coefficients)
        stretching = np.einsum(
            "...i,...ij,...j->...", vorticity, strain, vorticity
        )
        return VOLUME * float(np.real(np.mean(stretching)))

    def observables(self, coefficients: np.ndarray) -> dict[str, float]:
        return self.observables_from_rhs(coefficients, self.rhs(coefficients))


def initial_field(kind: str, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
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
                base[index] + 0.1 * perturbation[index] for index in range(3)
            )
    else:
        raise ValueError(f"unknown control {kind}")
    return np.stack(components, axis=-1).astype(np.complex128)


def initial_coefficients(
    solver: SpectralGalerkin, kind: str
) -> tuple[np.ndarray, float, float]:
    grid_axis = 2.0 * math.pi * np.arange(solver.grid_size) / solver.grid_size
    x, y, z = np.meshgrid(grid_axis, grid_axis, grid_axis, indexing="ij")
    raw = solver.to_coefficients(initial_field(kind, x, y, z))
    projected = solver.leray(raw)
    projection_error = float(np.max(np.abs(raw - projected)))
    roundtrip_error = float(
        np.max(np.abs(solver.to_coefficients(solver.to_grid(projected)) - projected))
    )
    return projected, projection_error, roundtrip_error


def rk4_step(
    solver: SpectralGalerkin,
    coefficients: np.ndarray,
    dt: float,
    first: np.ndarray,
) -> np.ndarray:
    second = solver.rhs(coefficients + 0.5 * dt * first)
    third = solver.rhs(coefficients + 0.5 * dt * second)
    fourth = solver.rhs(coefficients + dt * third)
    updated = coefficients + (dt / 6.0) * (
        first + 2.0 * second + 2.0 * third + fourth
    )
    updated[~solver.shell] = 0.0
    return updated


def integrate(
    kind: str, cutoff: int, grid_size: int, steps: int
) -> dict[str, Any]:
    solver = SpectralGalerkin(cutoff, grid_size)
    coefficients, projection_error, roundtrip_error = initial_coefficients(solver, kind)
    dt = T_END / float(steps)
    first = solver.rhs(coefficients)
    initial = solver.observables_from_rhs(coefficients, first)
    times = np.linspace(0.0, T_END, steps + 1, dtype=np.float64)
    positive_remainder = np.empty(steps + 1, dtype=np.float64)
    positive_remainder[0] = max(0.0, initial["remainder"])
    checkpoint_indices = {
        int(round(fraction * steps)) for fraction in (0.0, 0.25, 0.5, 0.75, 1.0)
    }
    direct_checkpoints: list[dict[str, float]] = []
    direct_production_max_abs = 0.0
    max_direct_spectral_difference = 0.0
    max_direct_spectral_relative_error = 0.0

    def check_direct(index: int, state: dict[str, float]) -> None:
        nonlocal direct_production_max_abs
        nonlocal max_direct_spectral_difference
        nonlocal max_direct_spectral_relative_error
        direct = solver.direct_production(coefficients)
        difference = abs(direct - state["production"])
        relative_error = difference / max(1.0, state["palinstrophy"])
        direct_production_max_abs = max(direct_production_max_abs, abs(direct))
        max_direct_spectral_difference = max(max_direct_spectral_difference, difference)
        max_direct_spectral_relative_error = max(
            max_direct_spectral_relative_error, relative_error
        )
        direct_checkpoints.append(
            {
                "step": float(index),
                "time": float(times[index]),
                "direct_production": direct,
                "spectral_production": state["production"],
                "absolute_difference": difference,
                "relative_error": relative_error,
            }
        )

    check_direct(0, initial)
    current = initial
    divergence_max = current["divergence_residual"]
    energy_positive_increment = 0.0
    production_max_abs = abs(current["production"])
    remainder_max = positive_remainder[0]
    previous_energy = current["energy"]

    for index in range(steps):
        coefficients = rk4_step(solver, coefficients, dt, first)
        first = solver.rhs(coefficients)
        current = solver.observables_from_rhs(coefficients, first)
        positive_remainder[index + 1] = max(0.0, current["remainder"])
        divergence_max = max(divergence_max, current["divergence_residual"])
        energy_positive_increment = max(
            energy_positive_increment, current["energy"] - previous_energy
        )
        production_max_abs = max(production_max_abs, abs(current["production"]))
        remainder_max = max(remainder_max, positive_remainder[index + 1])
        previous_energy = current["energy"]
        if index + 1 in checkpoint_indices:
            check_direct(index + 1, current)

    integral = float(np.trapezoid(positive_remainder, times))
    return {
        "control": kind,
        "cutoff": cutoff,
        "grid_size": grid_size,
        "steps": steps,
        "dt": dt,
        "projection_error": projection_error,
        "roundtrip_error": roundtrip_error,
        "initial": initial,
        "final": current,
        "positive_remainder_integral": integral,
        "positive_remainder_max": remainder_max,
        "max_divergence_residual": divergence_max,
        "max_positive_energy_increment": energy_positive_increment,
        "max_abs_production": production_max_abs,
        "direct_checkpoints": direct_checkpoints,
        "direct_production_max_abs": direct_production_max_abs,
        "max_direct_spectral_difference": max_direct_spectral_difference,
        "max_direct_spectral_relative_error": max_direct_spectral_relative_error,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(1.0, abs(left), abs(right))


def run_probe() -> dict[str, Any]:
    controls = ("shear", "abc", "rank_two", "near_rank")
    records: list[dict[str, Any]] = []
    by_key: dict[tuple[str, int, str], dict[str, Any]] = {}
    for control in controls:
        for cutoff in CUTOFFS:
            primary = integrate(control, cutoff, GRID_FACTORS[0] * cutoff + 1, PRIMARY_STEPS)
            refined_time = integrate(control, cutoff, GRID_FACTORS[0] * cutoff + 1, REFINED_STEPS)
            refined_grid = integrate(control, cutoff, GRID_FACTORS[1] * cutoff + 1, PRIMARY_STEPS)
            for label, record in (
                ("primary", primary),
                ("time_refined", refined_time),
                ("grid_refined", refined_grid),
            ):
                record["run"] = label
                records.append(record)
                by_key[(control, cutoff, label)] = record

    checks: dict[str, dict[str, Any]] = {}

    def check(name: str, passed: bool, detail: Any) -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    finite = all(
        math.isfinite(float(value))
        for record in records
        for value in (
            record["positive_remainder_integral"],
            record["positive_remainder_max"],
            record["max_divergence_residual"],
            record["max_positive_energy_increment"],
            record["max_abs_production"],
            record["direct_production_max_abs"],
            record["max_direct_spectral_difference"],
            record["max_direct_spectral_relative_error"],
            record["initial"]["production"],
            record["initial"]["palinstrophy"],
            record["final"]["enstrophy"],
        )
    ) and all(
        math.isfinite(float(value))
        for record in records
        for checkpoint in record["direct_checkpoints"]
        for value in (
            checkpoint["direct_production"],
            checkpoint["spectral_production"],
            checkpoint["absolute_difference"],
            checkpoint["relative_error"],
        )
    )
    check("finite_states_and_observables", finite, {"runs": len(records)})

    checkpoint_counts = {
        f"{record['control']}:N={record['cutoff']}:{record['run']}":
        len(record["direct_checkpoints"])
        for record in records
    }
    check(
        "direct_checkpoint_coverage",
        all(count == 5 for count in checkpoint_counts.values()),
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

    heat_production = max(
        record["direct_production_max_abs"]
        for record in records
        if record["control"] in {"shear", "abc"}
    )
    heat_bound = 1e-9 * max(
        1.0,
        max(
            record["initial"]["palinstrophy"]
            for record in records
            if record["control"] in {"shear", "abc"}
        ),
    )
    check(
        "exact_heat_control_production",
        heat_production <= heat_bound,
        {"maximum_abs_direct_production": heat_production, "bound": heat_bound},
    )

    endpoint_remainders = {
        f"{control}:N={cutoff}": by_key[(control, cutoff, "primary")]["initial"]["remainder"]
        for control in ("rank_two", "near_rank")
        for cutoff in CUTOFFS
    }
    endpoint_positive = all(value > 0.0 for value in endpoint_remainders.values())
    check(
        "positive_endpoint_controls",
        endpoint_positive,
        endpoint_remainders,
    )

    time_refinement = {
        f"{control}:N={cutoff}": relative_difference(
            by_key[(control, cutoff, "primary")]["positive_remainder_integral"],
            by_key[(control, cutoff, "time_refined")]["positive_remainder_integral"],
        )
        for control in controls
        for cutoff in CUTOFFS
    }
    max_time_refinement = max(time_refinement.values())
    check(
        "timestep_refinement",
        max_time_refinement <= 1e-6,
        {"maximum_relative_change": max_time_refinement, "bound": 1e-6},
    )

    grid_refinement = {
        f"{control}:N={cutoff}": relative_difference(
            by_key[(control, cutoff, "primary")]["positive_remainder_integral"],
            by_key[(control, cutoff, "grid_refined")]["positive_remainder_integral"],
        )
        for control in controls
        for cutoff in CUTOFFS
    }
    max_grid_refinement = max(grid_refinement.values())
    check(
        "product_grid_refinement",
        max_grid_refinement <= 1e-6,
        {"maximum_relative_change": max_grid_refinement, "bound": 1e-6},
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

    all_passed = all(entry["passed"] for entry in checks.values())
    status = "PASS" if all_passed else "FAIL"
    return {
        "schema": SCHEMA,
        "status": status,
        "classification": (
            "SUPPORTS—short-time finite-mode trajectory measurement only"
            if all_passed
            else "FAIL"
        ),
        "scope": {
            "nu": NU,
            "T": T_END,
            "cutoffs": list(CUTOFFS),
            "primary_steps": PRIMARY_STEPS,
            "refined_steps": REFINED_STEPS,
            "primary_grid": "4N+1",
            "refined_grid": "6N+1",
            "theorem_target": "UNRESOLVED",
            "arbitrary_data_regularity": "UNRESOLVED",
        },
        "checks": checks,
        "refinement": {
            "timestep_relative_change": time_refinement,
            "grid_relative_change": grid_refinement,
        },
        "runs": records,
        "source_hashes": {
            "computations/navier-stokes-galerkin-trajectory-prereg.md": sha256(PROTOCOL),
            "computations/verify_navier_stokes_galerkin_trajectory.py": sha256(SCRIPT),
            "turbulence/navier-stokes-near-rank-recovery-obstruction.md": sha256(
                NEAR_RANK_NOTE
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing receipt: {output}")
    receipt = run_probe()
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
