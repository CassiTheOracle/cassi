#!/usr/bin/env python3
"""Run the fixed-H3 adversarial Galerkin probe on ROCm Torch.

The initial data changes with the cutoff through a declared high-frequency
vector-potential family. The projected H3 norm is normalized before every
trajectory. This is a separate exploratory executable from the fixed-control
long-trajectory verifier and makes no regularity claim.
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
import torch


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "navier-stokes-galerkin-fixed-h3-rocm-prereg.md"
SCRIPT = Path(__file__).resolve()
DEFAULT_OUTPUT = (
    ROOT / "runs" / "navier_stokes_galerkin_fixed_h3_rocm_20260914"
    / "verification.json"
)
SCHEMA = "cassi.navier-stokes.galerkin-fixed-h3-rocm.verification.v1"

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
VOLUME = (2.0 * math.pi) ** 3
DEVICE = torch.device("cuda")
DTYPE = torch.float64

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
    """Half-spectrum Fourier-Galerkin algebra on a ROCm Torch device."""

    def __init__(self, cutoff: int, grid_size: int) -> None:
        self.cutoff = int(cutoff)
        self.grid_size = int(grid_size)
        full = torch.as_tensor(
            np.rint(np.fft.fftfreq(self.grid_size) * self.grid_size),
            dtype=DTYPE,
            device=DEVICE,
        )
        half = torch.as_tensor(
            np.rint(np.fft.rfftfreq(self.grid_size) * self.grid_size),
            dtype=DTYPE,
            device=DEVICE,
        )
        self.kx, self.ky, self.kz = torch.meshgrid(
            full, full, half, indexing="ij"
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

    def grid(self, coefficients: torch.Tensor) -> torch.Tensor:
        return torch.fft.irfftn(
            coefficients,
            s=(self.grid_size, self.grid_size, self.grid_size),
            dim=(0, 1, 2),
            norm="backward",
        ) * float(self.grid_size**3)

    def coefficients(self, values: torch.Tensor) -> torch.Tensor:
        return torch.fft.rfftn(
            values, dim=(0, 1, 2), norm="backward"
        ) / float(self.grid_size**3)

    def project(self, coefficients: torch.Tensor) -> torch.Tensor:
        projected = torch.zeros_like(coefficients)
        dot = (
            self.kx * coefficients[..., 0]
            + self.ky * coefficients[..., 1]
            + self.kz * coefficients[..., 2]
        )
        safe_k2 = torch.where(self.nonzero, self.k2, torch.ones_like(self.k2))
        quotient = torch.where(self.nonzero, dot / safe_k2, torch.zeros_like(dot))
        projected[..., 0] = coefficients[..., 0] - self.kx * quotient
        projected[..., 1] = coefficients[..., 1] - self.ky * quotient
        projected[..., 2] = coefficients[..., 2] - self.kz * quotient
        return projected.masked_fill(~self.shell[..., None], 0.0)

    def curl(self, state: torch.Tensor) -> torch.Tensor:
        return torch.stack(
            (
                1j * (self.ky * state[..., 2] - self.kz * state[..., 1]),
                1j * (self.kz * state[..., 0] - self.kx * state[..., 2]),
                1j * (self.kx * state[..., 1] - self.ky * state[..., 0]),
            ),
            dim=-1,
        )

    def right_hand_side(self, state: torch.Tensor) -> torch.Tensor:
        velocity = self.grid(state)
        vorticity = self.grid(self.curl(state))
        rotational = torch.cross(vorticity, velocity, dim=-1)
        projected_rotational = self.project(self.coefficients(rotational))
        result = -NU * self.k2[..., None] * state - projected_rotational
        return result.masked_fill(~self.shell[..., None], 0.0)

    def strain_and_vorticity(
        self, state: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        gradient_coefficients = (
            1j * state[..., :, None] * self.wave_numbers[..., None, :]
        )
        gradient = self.grid(gradient_coefficients)
        strain = 0.5 * (gradient + torch.swapaxes(gradient, -1, -2))
        vorticity = self.grid(self.curl(state))
        return strain, vorticity

    def spectral_observables(
        self, state: torch.Tensor, rhs: torch.Tensor
    ) -> dict[str, float]:
        vorticity_coefficients = self.curl(state)
        vorticity_rhs = self.curl(rhs)
        weight = self.parseval_weight[..., None]
        palinstrophy = VOLUME * float(
            (
                weight
                * self.k2[..., None]
                * torch.abs(vorticity_coefficients) ** 2
            ).sum().real.item()
        )
        enstrophy_derivative = 2.0 * VOLUME * float(
            (
                weight
                * torch.conj(vorticity_coefficients)
                * vorticity_rhs
            ).sum().real.item()
        )
        production = 0.5 * enstrophy_derivative + NU * palinstrophy
        enstrophy = VOLUME * float(
            (weight * torch.abs(vorticity_coefficients) ** 2).sum().real.item()
        )
        energy = 0.5 * VOLUME * float(
            (weight * torch.abs(state) ** 2).sum().real.item()
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

    def direct_production(self, state: torch.Tensor) -> float:
        strain, vorticity = self.strain_and_vorticity(state)
        stretching = torch.einsum(
            "...i,...ij,...j->...", vorticity, strain, vorticity
        )
        return VOLUME * float(torch.real(stretching).mean().item())

    def h3_norm(self, coefficients: torch.Tensor) -> float:
        weight = self.parseval_weight[..., None]
        value = VOLUME * (
            weight
            * (1.0 + self.k2[..., None]) ** 3
            * torch.abs(coefficients) ** 2
        ).sum().real.item()
        return float(math.sqrt(max(0.0, value)))

    def l2_norm(self, coefficients: torch.Tensor) -> float:
        weight = self.parseval_weight[..., None]
        value = VOLUME * (weight * torch.abs(coefficients) ** 2).sum().real.item()
        return float(math.sqrt(max(0.0, value)))

    def support_max(self, coefficients: torch.Tensor) -> float:
        magnitude = torch.abs(coefficients).amax(dim=-1)
        threshold = 1.0e-10 * max(1.0, float(magnitude.max().item()))
        active = magnitude > threshold
        if not bool(active.any().item()):
            return 0.0
        return float(torch.sqrt(self.k2[active].max()).item())

    def divergence_residual(self, coefficients: torch.Tensor) -> float:
        divergence = (
            self.kx * coefficients[..., 0]
            + self.ky * coefficients[..., 1]
            + self.kz * coefficients[..., 2]
        )
        return float(torch.abs(divergence).max().item())

    def projection_error(
        self, raw: torch.Tensor, projected: torch.Tensor
    ) -> float:
        return float(torch.abs(raw - projected).max().item())



def initial_values(
    arm: str, cutoff: int, grid_size: int
) -> tuple[torch.Tensor, torch.Tensor]:
    axis = 2.0 * math.pi * torch.arange(
        grid_size, dtype=DTYPE, device=DEVICE
    ) / grid_size
    x, y, z = torch.meshgrid(axis, axis, axis, indexing="ij")
    base = torch.stack(
        (-torch.sin(y), torch.zeros_like(x), torch.sin(x) + torch.cos(x) * torch.sin(y)),
        dim=-1,
    )
    high = torch.zeros((*x.shape, 3), dtype=DTYPE, device=DEVICE)
    for index in range(len(HIGH_WAVEVECTORS)):
        k = (cutoff / 2.0) * torch.as_tensor(
            HIGH_WAVEVECTORS[index], dtype=DTYPE, device=DEVICE
        )
        a = torch.as_tensor(HIGH_A[index], dtype=DTYPE, device=DEVICE)
        b = torch.as_tensor(HIGH_B[index], dtype=DTYPE, device=DEVICE)
        theta = k[0] * x + k[1] * y + k[2] * z
        k_norm = torch.linalg.vector_norm(k)
        high += (
            -torch.linalg.cross(k, a) * torch.sin(theta)[..., None]
            + torch.linalg.cross(k, b) * torch.cos(theta)[..., None]
        ) / k_norm
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
) -> tuple[torch.Tensor, dict[str, float]]:
    values, high_values = initial_values(arm, box.cutoff, box.grid_size)
    raw = box.coefficients(values)
    high_coefficients = box.coefficients(high_values)
    projected = box.project(raw)
    projected_h3 = box.h3_norm(projected)
    if projected_h3 <= 0.0:
        raise RuntimeError(f"zero projected H3 norm for arm={arm}")
    state = projected * (RADIUS / projected_h3)
    high_magnitude = torch.abs(high_coefficients).amax(dim=-1)
    high_threshold = 1.0e-10 * max(1.0, float(high_magnitude.max().item()))
    high_active = high_magnitude > high_threshold
    high_dot = (
        box.kx * high_coefficients[..., 0]
        + box.ky * high_coefficients[..., 1]
        + box.kz * high_coefficients[..., 2]
    )
    high_transversality = float(torch.abs(high_dot[high_active]).max().item())
    metadata = {
        "raw_h3_norm": box.h3_norm(raw),
        "projected_h3_before_scale": projected_h3,
        "normalized_h3_norm": box.h3_norm(state),
        "normalization_error": abs(box.h3_norm(state) - RADIUS),
        "raw_l2_norm": box.l2_norm(raw),
        "normalized_l2_norm": box.l2_norm(state),
        "projection_error": box.projection_error(raw, projected),
        "roundtrip_error": float(
            torch.abs(box.coefficients(box.grid(projected)) - projected)
            .max()
            .item()
        ),
        "support_max": box.support_max(state),
        "high_support_max": box.support_max(high_coefficients),
        "high_transversality_residual": high_transversality,
        "high_active_mode_count": int(high_active.sum().item()),
        "initial_divergence_residual": box.divergence_residual(state),
    }
    return state, metadata



def rk4_update(
    box: GalerkinBox,
    state: torch.Tensor,
    dt: float,
    first_rhs: torch.Tensor,
) -> torch.Tensor:
    second_rhs = box.right_hand_side(state + 0.5 * dt * first_rhs)
    third_rhs = box.right_hand_side(state + 0.5 * dt * second_rhs)
    fourth_rhs = box.right_hand_side(state + dt * third_rhs)
    updated = state + (dt / 6.0) * (
        first_rhs + 2.0 * second_rhs + 2.0 * third_rhs + fourth_rhs
    )
    return updated.masked_fill(~box.shell[..., None], 0.0)



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
    positive_remainder_evaluation_count = 1
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
        positive_remainder_evaluation_count += 1
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

    result = {
        "arm": arm,
        "cutoff": cutoff,
        "grid_size": grid_size,
        "steps": steps,
        "run": label,
        "backend": "torch-rocm",
        "device": torch.cuda.get_device_name(0),
        "dtype": str(DTYPE),
        "dt": dt,
        "initial_metadata": metadata,
        "initial": initial,
        "final": previous,
        "positive_remainder_integral": float(integral),
        "positive_remainder_max": max_positive_remainder,
        "positive_remainder_evaluation_count": positive_remainder_evaluation_count,
        "max_divergence_residual": max_divergence,
        "max_positive_energy_increment": max_positive_energy_increment,
        "max_abs_production": max_abs_production,
        "direct_checkpoints": checkpoints,
        "direct_production_max_abs": max_direct_abs,
        "max_direct_spectral_difference": max_direct_difference,
        "max_direct_spectral_relative_error": max_direct_relative_error,
    }
    del state, first_rhs, box
    torch.cuda.empty_cache()
    return result



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
    with torch.no_grad():
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
        len(records) == expected_count and len(by_key) == expected_count,
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
            "INCONCLUSIVE—fixed-H³ ROCm exploratory sequence"
            if all_passed
            else "FAIL"
        ),
        "scope": {
            "backend": "torch-rocm",
            "device": torch.cuda.get_device_name(0),
            "dtype": str(DTYPE),
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
            "computations/navier-stokes-galerkin-fixed-h3-rocm-prereg.md": sha256(
                PROTOCOL
            ),
            "computations/verify_navier_stokes_galerkin_fixed_h3_rocm.py": sha256(
                SCRIPT
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }



def run_smoke() -> None:
    with torch.no_grad():
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
    print("smoke: PASS (ROCm, N=8, three arms, 16 RK4 steps)")



def main() -> int:
    if not torch.cuda.is_available():
        raise SystemExit("ROCm Torch CUDA device is required")
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
