#!/usr/bin/env python3
"""Run the fixed-H3 adversarial Fourier-Galerkin exploratory probe.

The initial data changes with the cutoff through a declared high-frequency
vector-potential family. The projected H3 norm is normalized before every
trajectory. This script is independent of the fixed-control long-trajectory
verifier and makes no regularity claim.
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
from scipy.fft import irfftn, rfftn


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "navier-stokes-galerkin-fixed-h3-exploratory-prereg.md"
SCRIPT = Path(__file__).resolve()
DEFAULT_OUTPUT = (
    ROOT / "runs" / "navier_stokes_galerkin_fixed_h3_exploratory_20260914"
    / "verification.json"
)
SCHEMA = "cassi.navier-stokes.galerkin-fixed-h3-exploratory.verification.v1"

NU = 0.1
T_END = 0.5
RADIUS = 1.0
CUTOFFS = (8, 16, 32)
ARMS = ("base", "high", "combined")
PRIMARY_STEPS = 1024
REFINED_STEPS = 2048
PRIMARY_GRID_FACTOR = 4
REFINED_GRID_FACTOR = 6
CHECKPOINT_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
FFT_WORKERS = 1
VOLUME = (2.0 * math.pi) ** 3

HIGH_WAVEVECTORS = np.asarray(
    (
        (1, 0, 0),
        (0, 1, 0),
        (-1, -1, 0),
        (0, 0, 1),
        (0, -1, -1),
    ),
    dtype=np.int64,
)
HIGH_A = np.asarray(
    (
        (0, 1, 1),
        (1, 0, 1),
        (1, -1, 1),
        (1, 1, 0),
        (1, 0, 1),
    ),
    dtype=np.float64,
)
HIGH_B = np.asarray(
    (
        (0, 1, -1),
        (1, 0, -1),
        (1, 1, 0),
        (1, -1, 0),
        (1, 0, -1),
    ),
    dtype=np.float64,
)


class GalerkinBox:
    """Half-spectrum Fourier-Galerkin algebra on an odd product grid."""

    def __init__(self, cutoff: int, grid_size: int) -> None:
        self.cutoff = int(cutoff)
        self.grid_size = int(grid_size)
        full = np.rint(
            np.fft.fftfreq(self.grid_size) * self.grid_size
        ).astype(np.int64)
        half = np.rint(
            np.fft.rfftfreq(self.grid_size) * self.grid_size
        ).astype(np.int64)
        self.kx, self.ky, self.kz = np.meshgrid(
            full, full, half, indexing="ij"
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
        values = irfftn(
            coefficients,
            s=(self.grid_size, self.grid_size, self.grid_size),
            axes=(0, 1, 2),
            workers=FFT_WORKERS,
        )
        return np.asarray(values) * float(self.grid_size**3)

    def coefficients(self, values: np.ndarray) -> np.ndarray:
        transformed = rfftn(
            values, axes=(0, 1, 2), workers=FFT_WORKERS
        )
        return np.asarray(transformed) / float(self.grid_size**3)

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

    def curl(self, state: np.ndarray) -> np.ndarray:
        return np.stack(
            (
                1j * (self.ky * state[..., 2] - self.kz * state[..., 1]),
                1j * (self.kz * state[..., 0] - self.kx * state[..., 2]),
                1j * (self.kx * state[..., 1] - self.ky * state[..., 0]),
            ),
            axis=-1,
        )

    def right_hand_side(self, state: np.ndarray) -> np.ndarray:
        velocity = self.grid(state)
        vorticity = self.grid(self.curl(state))
        rotational = np.cross(vorticity, velocity)
        projected_rotational = self.project(self.coefficients(rotational))
        result = -NU * self.k2[..., None] * state - projected_rotational
        result[~self.shell] = 0.0
        return result

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
        weight = self.parseval_weight[..., None]
        palinstrophy = VOLUME * float(
            np.sum(
                weight
                * self.k2[..., None]
                * np.abs(vorticity_coefficients) ** 2
            )
        )
        enstrophy_derivative = 2.0 * VOLUME * float(
            np.real(
                np.sum(
                    weight
                    * np.conj(vorticity_coefficients)
                    * vorticity_rhs
                )
            )
        )
        production = 0.5 * enstrophy_derivative + NU * palinstrophy
        enstrophy = VOLUME * float(
            np.sum(weight * np.abs(vorticity_coefficients) ** 2)
        )
        energy = 0.5 * VOLUME * float(
            np.sum(weight * np.abs(state) ** 2)
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
        return VOLUME * float(np.real(stretching).mean())

    def h3_norm(self, coefficients: np.ndarray) -> float:
        weight = self.parseval_weight[..., None]
        value = VOLUME * np.sum(
            weight
            * (1.0 + self.k2[..., None]) ** 3
            * np.abs(coefficients) ** 2
        )
        return float(np.sqrt(max(0.0, float(np.real(value)))))

    def l2_norm(self, coefficients: np.ndarray) -> float:
        weight = self.parseval_weight[..., None]
        value = VOLUME * np.sum(weight * np.abs(coefficients) ** 2)
        return float(np.sqrt(max(0.0, float(np.real(value)))))

    def support_max(self, coefficients: np.ndarray) -> float:
        magnitude = np.max(np.abs(coefficients), axis=-1)
        threshold = 1.0e-10 * max(1.0, float(np.max(magnitude)))
        active = magnitude > threshold
        if not np.any(active):
            return 0.0
        return float(np.sqrt(np.max(self.k2[active])))

    def divergence_residual(self, coefficients: np.ndarray) -> float:
        divergence = (
            self.kx * coefficients[..., 0]
            + self.ky * coefficients[..., 1]
            + self.kz * coefficients[..., 2]
        )
        return float(np.max(np.abs(divergence)))

    def projection_error(self, raw: np.ndarray, projected: np.ndarray) -> float:
        return float(np.max(np.abs(raw - projected)))



def base_field(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    del z
    return np.stack(
        (-np.sin(y), np.zeros_like(x), np.sin(x) + np.cos(x) * np.sin(y)),
        axis=-1,
    ).astype(np.float64)



def high_field(
    x: np.ndarray, y: np.ndarray, z: np.ndarray, cutoff: int
) -> np.ndarray:
    h = cutoff // 2
    field = np.zeros(x.shape + (3,), dtype=np.float64)
    for index in range(len(HIGH_WAVEVECTORS)):
        k = h * HIGH_WAVEVECTORS[index].astype(np.float64)
        theta = k[0] * x + k[1] * y + k[2] * z
        field += (
            -np.cross(k, HIGH_A[index]) * np.sin(theta)[..., None]
            + np.cross(k, HIGH_B[index]) * np.cos(theta)[..., None]
        ) / float(np.linalg.norm(k))
    return field



def initial_values(
    arm: str, cutoff: int, grid_size: int
) -> tuple[np.ndarray, np.ndarray]:
    axis = 2.0 * math.pi * np.arange(grid_size) / grid_size
    x, y, z = np.meshgrid(axis, axis, axis, indexing="ij")
    base = base_field(x, y, z)
    high = high_field(x, y, z, cutoff)
    if arm == "base":
        values = base
    elif arm == "high":
        values = high
    elif arm == "combined":
        values = base + high
    else:
        raise ValueError(f"unknown arm {arm}")
    return values, high



def initial_state(
    box: GalerkinBox, arm: str
) -> tuple[np.ndarray, dict[str, float]]:
    values, high_values = initial_values(arm, box.cutoff, box.grid_size)
    raw = box.coefficients(values)
    high_coefficients = box.coefficients(high_values)
    projected = box.project(raw)
    projected_h3 = box.h3_norm(projected)
    if projected_h3 <= 0.0:
        raise RuntimeError(f"zero projected H3 norm for arm={arm}")
    state = projected * (RADIUS / projected_h3)
    high_magnitude = np.max(np.abs(high_coefficients), axis=-1)
    high_threshold = 1.0e-10 * max(1.0, float(np.max(high_magnitude)))
    high_active = high_magnitude > high_threshold
    high_dot = (
        box.kx * high_coefficients[..., 0]
        + box.ky * high_coefficients[..., 1]
        + box.kz * high_coefficients[..., 2]
    )
    high_transversality = float(np.max(np.abs(high_dot[high_active])))
    metadata = {
        "raw_h3_norm": box.h3_norm(raw),
        "projected_h3_before_scale": projected_h3,
        "normalized_h3_norm": box.h3_norm(state),
        "normalization_error": abs(box.h3_norm(state) - RADIUS),
        "raw_l2_norm": box.l2_norm(raw),
        "normalized_l2_norm": box.l2_norm(state),
        "projection_error": box.projection_error(raw, projected),
        "roundtrip_error": float(
            np.max(np.abs(box.coefficients(box.grid(projected)) - projected))
        ),
        "support_max": box.support_max(state),
        "high_support_max": box.support_max(high_coefficients),
        "high_transversality_residual": high_transversality,
        "high_active_mode_count": int(np.count_nonzero(high_active)),
        "initial_divergence_residual": box.divergence_residual(state),
    }
    return state, metadata



def rk4_update(
    box: GalerkinBox, state: np.ndarray, dt: float, first_rhs: np.ndarray
) -> np.ndarray:
    second_rhs = box.right_hand_side(state + 0.5 * dt * first_rhs)
    third_rhs = box.right_hand_side(state + 0.5 * dt * second_rhs)
    fourth_rhs = box.right_hand_side(state + dt * third_rhs)
    updated = state + (dt / 6.0) * (
        first_rhs + 2.0 * second_rhs + 2.0 * third_rhs + fourth_rhs
    )
    updated[~box.shell] = 0.0
    return updated



def integrate_case(
    arm: str, cutoff: int, grid_size: int, steps: int, label: str
) -> dict[str, Any]:
    box = GalerkinBox(cutoff, grid_size)
    state, metadata = initial_state(box, arm)
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
        max_direct_relative_error = max(max_direct_relative_error, relative_error)
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
        max_positive_remainder = max(max_positive_remainder, current_positive)
        max_divergence = max(max_divergence, current["divergence_residual"])
        max_positive_energy_increment = max(
            max_positive_energy_increment,
            current["energy"] - previous["energy"],
        )
        max_abs_production = max(max_abs_production, abs(current["production"]))
        previous = current
        if index + 1 in checkpoint_steps:
            record_checkpoint(index + 1, current)

    return {
        "arm": arm,
        "cutoff": cutoff,
        "grid_size": grid_size,
        "steps": steps,
        "run": label,
        "backend": "numpy",
        "dt": dt,
        "initial_metadata": metadata,
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



def relative_change(left: float, right: float) -> float:
    return abs(left - right) / max(1.0, abs(left), abs(right))



def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()



def all_finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(all_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(all_finite(item) for item in value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, str) or value is None:
        return True
    return False



def run_probe() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for arm in ARMS:
        for cutoff in CUTOFFS:
            records.append(
                integrate_case(
                    arm,
                    cutoff,
                    PRIMARY_GRID_FACTOR * cutoff + 1,
                    PRIMARY_STEPS,
                    "primary",
                )
            )
            records.append(
                integrate_case(
                    arm,
                    cutoff,
                    PRIMARY_GRID_FACTOR * cutoff + 1,
                    REFINED_STEPS,
                    "time_refined",
                )
            )
            records.append(
                integrate_case(
                    arm,
                    cutoff,
                    REFINED_GRID_FACTOR * cutoff + 1,
                    PRIMARY_STEPS,
                    "grid_refined",
                )
            )

    by_key = {
        (record["arm"], int(record["cutoff"]), record["run"]): record
        for record in records
    }
    checks: dict[str, dict[str, Any]] = {}

    def check(name: str, passed: bool, detail: Any) -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    expected_count = len(ARMS) * len(CUTOFFS) * 3
    check(
        "declared_matrix_integrity",
        len(records) == expected_count
        and len(by_key) == expected_count,
        {"expected_count": expected_count, "completed_count": len(records)},
    )
    check("finite_states_and_observables", all_finite(records), {"runs": len(records)})

    normalization_errors = {
        f"{record['arm']}:N={record['cutoff']}:{record['run']}": record[
            "initial_metadata"
        ]["normalization_error"]
        for record in records
    }
    max_normalization_error = max(normalization_errors.values())
    check(
        "projected_h3_normalization",
        max_normalization_error <= 1e-10,
        {"maximum": max_normalization_error, "bound": 1e-10},
    )

    support_values = {
        f"{record['arm']}:N={record['cutoff']}:{record['run']}": record[
            "initial_metadata"
        ]["support_max"]
        for record in records
    }
    high_support_values = {
        f"N={record['cutoff']}:{record['run']}": record["initial_metadata"][
            "high_support_max"
        ]
        for record in records
    }
    support_excess = max(
        max(0.0, support_values[key] - float(int(key.split("N=")[1].split(":")[0])))
        for key in support_values
    )
    high_support_excess = max(
        max(0.0, high_support_values[key] - float(int(key.split("N=")[1].split(":")[0])))
        for key in high_support_values
    )
    check(
        "declared_support_bounds",
        support_excess <= 1e-10 and high_support_excess <= 1e-10,
        {
            "maximum_support_excess": support_excess,
            "maximum_high_support_excess": high_support_excess,
            "bound": 1e-10,
        },
    )

    max_transversality = max(
        record["initial_metadata"]["high_transversality_residual"]
        for record in records
    )
    check(
        "high_field_transversality",
        max_transversality <= 1e-10,
        {"maximum": max_transversality, "bound": 1e-10},
    )

    max_divergence = max(record["max_divergence_residual"] for record in records)
    check(
        "divergence_residual",
        max_divergence <= 1e-10,
        {"maximum": max_divergence, "bound": 1e-10},
    )

    max_direct_relative_error = max(
        record["max_direct_spectral_relative_error"] for record in records
    )
    check(
        "direct_strain_production_agreement",
        max_direct_relative_error <= 1e-9,
        {"maximum": max_direct_relative_error, "bound": 1e-9},
    )

    max_energy_increment = max(
        record["max_positive_energy_increment"] for record in records
    )
    energy_bound = 1e-9 * max(
        1.0, max(record["initial"]["energy"] for record in records)
    )
    check(
        "kinetic_energy_dissipation",
        max_energy_increment <= energy_bound,
        {"maximum": max_energy_increment, "bound": energy_bound},
    )

    timestep_changes = {
        f"{arm}:N={cutoff}": relative_change(
            by_key[(arm, cutoff, "primary")]["positive_remainder_integral"],
            by_key[(arm, cutoff, "time_refined")]["positive_remainder_integral"],
        )
        for arm in ARMS
        for cutoff in CUTOFFS
    }
    max_timestep_change = max(timestep_changes.values())
    check(
        "timestep_refinement",
        max_timestep_change <= 1e-6,
        {"maximum": max_timestep_change, "bound": 1e-6},
    )

    grid_changes = {
        f"{arm}:N={cutoff}": relative_change(
            by_key[(arm, cutoff, "primary")]["positive_remainder_integral"],
            by_key[(arm, cutoff, "grid_refined")]["positive_remainder_integral"],
        )
        for arm in ARMS
        for cutoff in CUTOFFS
    }
    max_grid_change = max(grid_changes.values())
    check(
        "product_grid_refinement",
        max_grid_change <= 1e-6,
        {"maximum": max_grid_change, "bound": 1e-6},
    )

    max_projection = max(
        record["initial_metadata"]["projection_error"] for record in records
    )
    max_roundtrip = max(
        record["initial_metadata"]["roundtrip_error"] for record in records
    )
    check(
        "initial_projection_and_roundtrip",
        max_projection <= 1e-10 and max_roundtrip <= 1e-12,
        {
            "maximum_projection_error": max_projection,
            "maximum_roundtrip_error": max_roundtrip,
        },
    )

    cutoff_sequence = {
        arm: {
            str(cutoff): {
                "I_N": by_key[(arm, cutoff, "primary")][
                    "positive_remainder_integral"
                ],
                "I_hat_N": by_key[(arm, cutoff, "primary")][
                    "positive_remainder_integral"
                ]
                / (T_END * RADIUS**3),
            }
            for cutoff in CUTOFFS
        }
        for arm in ARMS
    }
    all_passed = all(entry["passed"] for entry in checks.values())
    return {
        "schema": SCHEMA,
        "status": "PASS" if all_passed else "FAIL",
        "classification": (
            "INCONCLUSIVE—fixed-H³ exploratory sequence"
            if all_passed
            else "FAIL"
        ),
        "scope": {
            "backend": "numpy",
            "nu": NU,
            "T": T_END,
            "radius": RADIUS,
            "arms": list(ARMS),
            "cutoffs": list(CUTOFFS),
            "primary_steps": PRIMARY_STEPS,
            "refined_steps": REFINED_STEPS,
            "primary_grid": "4N+1",
            "refined_grid": "6N+1",
            "theorem_target": "UNRESOLVED",
            "production_relative_compensation": "UNRESOLVED",
            "arbitrary_data_regularity": "UNRESOLVED",
        },
        "checks": checks,
        "refinement": {
            "timestep_relative_change": timestep_changes,
            "grid_relative_change": grid_changes,
        },
        "cutoff_sequence": cutoff_sequence,
        "runs": records,
        "source_hashes": {
            "computations/navier-stokes-galerkin-fixed-h3-exploratory-prereg.md": sha256(
                PROTOCOL
            ),
            "computations/verify_navier_stokes_galerkin_fixed_h3_exploratory.py": sha256(
                SCRIPT
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }



def run_smoke() -> None:
    records = [
        integrate_case(
            arm,
            8,
            PRIMARY_GRID_FACTOR * 8 + 1,
            16,
            "smoke",
        )
        for arm in ARMS
    ]
    if not all_finite(records):
        raise RuntimeError("smoke produced a nonfinite value")
    if max(record["max_divergence_residual"] for record in records) > 1e-10:
        raise RuntimeError("smoke failed divergence check")
    if max(
        record["max_direct_spectral_relative_error"] for record in records
    ) > 1e-9:
        raise RuntimeError("smoke failed direct strain agreement")
    print("smoke: PASS (N=8, three arms, 16 RK4 steps)")



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        run_smoke()
        return 0
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing receipt: {output}")
    receipt = run_probe()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + chr(10), encoding="utf-8")
    print(f"status: {receipt['status']}")
    print(f"classification: {receipt['classification']}")
    for name, entry in receipt["checks"].items():
        print(f"{name}: {'PASS' if entry['passed'] else 'FAIL'}")
    print(f"runs: {len(receipt['runs'])}")
    print(f"receipt: {output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
