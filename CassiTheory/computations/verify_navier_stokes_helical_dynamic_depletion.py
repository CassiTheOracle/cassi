#!/usr/bin/env python3
"""Stress-test dynamic helical vortex-stretching depletion on ROCm."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "navier-stokes-helical-dynamic-depletion-prereg.md"
SCRIPT = Path(__file__).resolve()
LONG_TRAJECTORY_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_galerkin_long_trajectory.py"
)
DEFAULT_OUTPUT = ROOT / "runs" / "navier_stokes_helical_dynamic_depletion" / "verification.json"
SCHEMA = "cassi.navier-stokes.helical-dynamic-depletion.verification.v1"
PROTOCOL_REVISION = "A1"

NU = 0.1
T_END = 0.5
TARGET_KINETIC_ENERGY = 1.0
CUTOFFS = (16, 32)
PRIMARY_STEPS = 1024
REFINED_STEPS = 2048
PRIMARY_GRID_FACTOR = 6
CHECKPOINT_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
POSITIVE_PRODUCTION_THRESHOLD = 1.0e-8
BELTRAMI_PRODUCTION_TOLERANCE = 1.0e-10


def load_long_trajectory() -> Any:
    spec = importlib.util.spec_from_file_location(
        "navier_stokes_long_trajectory", LONG_TRAJECTORY_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load trajectory implementation: {LONG_TRAJECTORY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


long_trajectory = load_long_trajectory()
long_trajectory.NU = NU


CASES: tuple[dict[str, Any], ...] = (
    {"name": "beltrami", "family": "single_curl_eigenmode"},
    {"name": "homochiral_modes", "family": "same_curl_sign_interacting_modes"},
    {"name": "opposite_helical_modes", "family": "opposite_curl_sign_modes"},
    {
        "name": "helix_wide",
        "family": "helical_vorticity_tube",
        "tube_radius": 0.5,
        "pitch_turns": 1,
        "centerline_radius": 0.75,
    },
    {
        "name": "helix_narrow",
        "family": "helical_vorticity_tube",
        "tube_radius": 0.25,
        "pitch_turns": 1,
        "centerline_radius": 0.75,
    },
    {
        "name": "helix_tight_pitch",
        "family": "helical_vorticity_tube",
        "tube_radius": 0.25,
        "pitch_turns": 4,
        "centerline_radius": 0.75,
    },
    {
        "name": "two_scale_helices",
        "family": "same_handed_interacting_scales",
        "tube_radius": (0.5, 0.25),
        "pitch_turns": (1, 4),
    },
    {
        "name": "opposite_handed_helices",
        "family": "opposite_handed_interacting_tubes",
        "tube_radius": 0.25,
        "pitch_turns": (3, -3),
    },
)

HELICAL_MODE_SPECS: dict[str, tuple[tuple[tuple[int, int, int], int, float, float], ...]] = {
    "homochiral_modes": (
        ((1, 0, 0), 1, 1.0, 0.0),
        ((0, 1, 0), 1, 0.8, math.pi / 4.0),
        ((1, 1, 0), 1, 0.6, -0.3),
        ((2, 1, 0), 1, 0.5, 0.7),
    ),
    "opposite_helical_modes": (
        ((1, 0, 0), 1, 1.0, 0.0),
        ((0, 1, 0), -1, 1.0, math.pi / 4.0),
        ((1, 1, 0), 1, 0.6, -0.3),
        ((1, -1, 0), -1, 0.6, 0.7),
    ),
}


# The imported long-trajectory module uses the normalized Fourier coefficients
# and the same TorchGalerkinBox for all dynamics and physical-space checks.
VOLUME = float(long_trajectory.VOLUME)


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
    if isinstance(value, (int, float, bool)):
        return math.isfinite(float(value))
    if isinstance(value, str) or value is None:
        return True
    return False


def torus_delta(value: torch.Tensor, center: float | torch.Tensor) -> torch.Tensor:
    return 2.0 * torch.sin(0.5 * (value - center))


def helical_frame(
    wavevector: tuple[int, int, int],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    k = torch.as_tensor(wavevector, dtype=torch.float64, device="cuda")
    k_norm = torch.linalg.vector_norm(k)
    k_hat = k / k_norm
    reference = torch.as_tensor((0.0, 0.0, 1.0), dtype=torch.float64, device="cuda")
    if abs(float(torch.dot(k_hat, reference).item())) > 0.9:
        reference = torch.as_tensor((0.0, 1.0, 0.0), dtype=torch.float64, device="cuda")
    e1 = torch.linalg.cross(reference, k_hat)
    e1 = e1 / torch.linalg.vector_norm(e1)
    e2 = torch.linalg.cross(k_hat, e1)
    return k, e1, e2


def helical_mode_field(
    x: torch.Tensor,
    y: torch.Tensor,
    z: torch.Tensor,
    specs: tuple[tuple[tuple[int, int, int], int, float, float], ...],
) -> torch.Tensor:
    values = torch.zeros((*x.shape, 3), dtype=torch.float64, device=x.device)
    for wavevector, sigma, amplitude, phase in specs:
        k, e1, e2 = helical_frame(wavevector)
        theta = k[0] * x + k[1] * y + k[2] * z + phase
        values += amplitude * (
            torch.cos(theta)[..., None] * e1
            - float(sigma) * torch.sin(theta)[..., None] * e2
        )
    return values


def tube_vorticity_seed(
    x: torch.Tensor,
    y: torch.Tensor,
    z: torch.Tensor,
    *,
    center_x: float,
    center_y: float,
    centerline_radius: float,
    pitch_turns: int,
    tube_radius: float,
    strength: float = 1.0,
) -> torch.Tensor:
    angle = float(pitch_turns) * z
    centerline_x = center_x + centerline_radius * torch.cos(angle)
    centerline_y = center_y + centerline_radius * torch.sin(angle)
    dx = torus_delta(x, centerline_x)
    dy = torus_delta(y, centerline_y)
    radial_squared = dx * dx + dy * dy
    profile = torch.exp(-0.5 * radial_squared / (tube_radius * tube_radius))
    tangent = torch.stack(
        (
            -centerline_radius * float(pitch_turns) * torch.sin(angle),
            centerline_radius * float(pitch_turns) * torch.cos(angle),
            torch.ones_like(z),
        ),
        dim=-1,
    )
    tangent = tangent / torch.linalg.vector_norm(tangent, dim=-1, keepdim=True)
    return float(strength) * profile[..., None] * tangent


def case_raw_field(
    case: dict[str, Any],
    box: Any,
) -> tuple[torch.Tensor, str, dict[str, Any]]:
    axis = (
        2.0
        * math.pi
        * torch.arange(box.grid_size, dtype=torch.float64, device=box.device)
        / box.grid_size
    )
    x, y, z = torch.meshgrid(axis, axis, axis, indexing="ij")
    name = case["name"]
    if name == "beltrami":
        values = torch.stack((torch.sin(z), torch.cos(z), torch.zeros_like(z)), dim=-1)
        return values, "velocity", {"exact_invariant": True}
    if name in HELICAL_MODE_SPECS:
        values = helical_mode_field(x, y, z, HELICAL_MODE_SPECS[name])
        return values, "velocity", {"mode_specs": HELICAL_MODE_SPECS[name]}
    if name == "helix_wide":
        seed = tube_vorticity_seed(
            x,
            y,
            z,
            center_x=math.pi,
            center_y=math.pi,
            centerline_radius=case["centerline_radius"],
            pitch_turns=case["pitch_turns"],
            tube_radius=case["tube_radius"],
        )
        return seed, "vorticity", {"center": (math.pi, math.pi)}
    if name == "helix_narrow":
        seed = tube_vorticity_seed(
            x,
            y,
            z,
            center_x=math.pi,
            center_y=math.pi,
            centerline_radius=case["centerline_radius"],
            pitch_turns=case["pitch_turns"],
            tube_radius=case["tube_radius"],
        )
        return seed, "vorticity", {"center": (math.pi, math.pi)}
    if name == "helix_tight_pitch":
        seed = tube_vorticity_seed(
            x,
            y,
            z,
            center_x=math.pi,
            center_y=math.pi,
            centerline_radius=case["centerline_radius"],
            pitch_turns=case["pitch_turns"],
            tube_radius=case["tube_radius"],
        )
        return seed, "vorticity", {"center": (math.pi, math.pi)}
    if name == "two_scale_helices":
        wide = tube_vorticity_seed(
            x,
            y,
            z,
            center_x=math.pi,
            center_y=math.pi,
            centerline_radius=0.75,
            pitch_turns=1,
            tube_radius=0.5,
            strength=1.0,
        )
        narrow = tube_vorticity_seed(
            x,
            y,
            z,
            center_x=math.pi + 1.6,
            center_y=math.pi,
            centerline_radius=0.375,
            pitch_turns=4,
            tube_radius=0.25,
            strength=0.45,
        )
        return wide + narrow, "vorticity", {
            "centers": ((math.pi, math.pi), (math.pi + 1.6, math.pi)),
            "scales": ((0.5, 1), (0.25, 4)),
        }
    if name == "opposite_handed_helices":
        positive = tube_vorticity_seed(
            x,
            y,
            z,
            center_x=math.pi - 1.6,
            center_y=math.pi,
            centerline_radius=0.75,
            pitch_turns=3,
            tube_radius=0.25,
            strength=1.0,
        )
        negative = tube_vorticity_seed(
            x,
            y,
            z,
            center_x=math.pi + 1.6,
            center_y=math.pi,
            centerline_radius=0.75,
            pitch_turns=-3,
            tube_radius=0.25,
            strength=1.0,
        )
        return positive + negative, "vorticity", {
            "centers": ((math.pi - 1.6, math.pi), (math.pi + 1.6, math.pi)),
            "handedness": (1, -1),
        }
    raise ValueError(f"unknown case {name}")


def spectral_integral(_box: Any, value: torch.Tensor) -> float:
    return VOLUME * float(torch.real(value).mean().item())


def spectral_energy(box: Any, state: torch.Tensor) -> float:
    return 0.5 * VOLUME * float(
        torch.sum(box.parseval_weight[..., None] * torch.abs(state) ** 2).item()
    )


def initial_state(
    case: dict[str, Any], box: Any
) -> tuple[torch.Tensor, dict[str, Any]]:
    raw_values, raw_kind, geometry = case_raw_field(case, box)
    raw_coefficients = box.coefficients(raw_values)
    raw_divergence = box.kx * raw_coefficients[..., 0]
    raw_divergence += box.ky * raw_coefficients[..., 1]
    raw_divergence += box.kz * raw_coefficients[..., 2]
    projected = box.project(raw_coefficients)
    projection_error = float(torch.abs(raw_coefficients - projected).max().item())
    projected_divergence = box.kx * projected[..., 0]
    projected_divergence += box.ky * projected[..., 1]
    projected_divergence += box.kz * projected[..., 2]

    if raw_kind == "velocity":
        state = projected
    else:
        safe_k2 = torch.where(box.nonzero, box.k2, torch.ones_like(box.k2))
        state = box.curl(projected) / safe_k2[..., None]
        state = torch.where(box.nonzero[..., None], state, torch.zeros_like(state))
        state = state.masked_fill(~box.shell[..., None], 0.0)

    kinetic_before = spectral_energy(box, state)
    if kinetic_before <= 0.0:
        raise RuntimeError(f"zero projected kinetic energy for {case['name']}")
    state = state * math.sqrt(TARGET_KINETIC_ENERGY / kinetic_before)
    reconstructed = box.coefficients(box.grid(state))
    state_divergence = box.kx * state[..., 0]
    state_divergence += box.ky * state[..., 1]
    state_divergence += box.kz * state[..., 2]
    metadata = {
        "raw_kind": raw_kind,
        "geometry": geometry,
        "raw_divergence_residual": float(torch.abs(raw_divergence).max().item()),
        "projected_divergence_residual": float(torch.abs(projected_divergence).max().item()),
        "projection_error": projection_error,
        "roundtrip_error": float(torch.abs(reconstructed - state).max().item()),
        "kinetic_energy_before_normalization": kinetic_before,
        "normalized_kinetic_energy": spectral_energy(box, state),
        "normalization_error": abs(spectral_energy(box, state) - TARGET_KINETIC_ENERGY),
        "state_divergence_residual": float(torch.abs(state_divergence).max().item()),
    }
    return state, metadata


def metrics(box: Any, state: torch.Tensor, rhs: torch.Tensor) -> dict[str, float]:
    strain, vorticity = box.strain_and_vorticity(state)
    stretching_density = torch.einsum(
        "...i,...ij,...j->...", vorticity, strain, vorticity
    )
    strain_vorticity = torch.einsum("...ij,...j->...i", strain, vorticity)
    vorticity_magnitude = torch.linalg.vector_norm(vorticity, dim=-1)
    strain_vorticity_magnitude = torch.linalg.vector_norm(strain_vorticity, dim=-1)
    absolute_stretching = spectral_integral(box, torch.abs(stretching_density))
    local_positive_stretching = spectral_integral(
        box, torch.clamp(stretching_density, min=0.0)
    )
    alignment_denominator = spectral_integral(
        box, vorticity_magnitude * strain_vorticity_magnitude
    )

    vorticity_coefficients = box.curl(state)
    vorticity_gradient_coefficients = (
        1j * vorticity_coefficients[..., :, None] * box.wave_numbers[..., None, :]
    )
    vorticity_gradient = box.grid(vorticity_gradient_coefficients)
    vorticity_squared = torch.sum(vorticity * vorticity, dim=-1)
    gradient_squared = torch.sum(vorticity_gradient * vorticity_gradient, dim=(-2, -1))
    enstrophy = 0.5 * spectral_integral(box, vorticity_squared)
    palinstrophy = 0.5 * spectral_integral(box, gradient_squared)

    direction_mask = vorticity_magnitude > 1.0e-12 * max(
        1.0, float(vorticity_magnitude.max().item())
    )
    safe_magnitude = torch.where(
        direction_mask, vorticity_magnitude, torch.ones_like(vorticity_magnitude)
    )
    direction = vorticity / safe_magnitude[..., None]
    directional_derivative = torch.einsum(
        "...i,...ij->...j", direction, vorticity_gradient
    )
    direction_gradient = (
        vorticity_gradient
        - direction[..., :, None] * directional_derivative[..., None, :]
    ) / safe_magnitude[..., None, None]
    direction_gradient = torch.where(
        direction_mask[..., None, None],
        direction_gradient,
        torch.zeros_like(direction_gradient),
    )
    direction_gradient_squared = torch.sum(
        direction_gradient * direction_gradient, dim=(-2, -1)
    )
    weighted_direction_gradient = spectral_integral(
        box, vorticity_squared * direction_gradient_squared
    )
    vorticity_l2_squared = spectral_integral(box, vorticity_squared)
    direction_gradient_rms = math.sqrt(
        weighted_direction_gradient / max(vorticity_l2_squared, 1.0e-30)
    )

    parseval_weight = box.parseval_weight[..., None]
    helicity = VOLUME * float(
        torch.real(
            torch.sum(
                parseval_weight
                * torch.conj(state)
                * vorticity_coefficients
            )
        ).item()
    )
    curl_weighted_energy = VOLUME * float(
        torch.sum(
            parseval_weight * torch.sqrt(box.k2[..., None]) * torch.abs(state) ** 2
        ).item()
    )
    kinetic_energy = spectral_energy(box, state)
    energy_derivative = VOLUME * float(
        torch.real(torch.sum(parseval_weight * torch.conj(state) * rhs)).item()
    )
    divergence = box.kx * state[..., 0] + box.ky * state[..., 1] + box.kz * state[..., 2]
    production = spectral_integral(box, stretching_density)
    positive_production = max(production, 0.0)
    spectral_enstrophy_derivative = VOLUME * float(
        torch.real(
            torch.sum(
                parseval_weight
                * torch.conj(vorticity_coefficients)
                * box.curl(rhs)
            )
        ).item()
    )
    spectral_production = (
        spectral_enstrophy_derivative + 2.0 * NU * palinstrophy
    )
    remainder = production - 2.0 * NU * palinstrophy
    return {
        "kinetic_energy": kinetic_energy,
        "enstrophy": enstrophy,
        "palinstrophy": palinstrophy,
        "production": production,
        "spectral_production": spectral_production,
        "positive_production": positive_production,
        "local_positive_stretching": local_positive_stretching,
        "positive_remainder": max(0.0, remainder),
        "absolute_stretching": absolute_stretching,
        "alignment_denominator": alignment_denominator,
        "absolute_alignment": (
            absolute_stretching / alignment_denominator
            if alignment_denominator > 0.0
            else 0.0
        ),
        "signed_alignment": (
            production / alignment_denominator if alignment_denominator > 0.0 else 0.0
        ),
        "local_positive_stretching_fraction": (
            local_positive_stretching / absolute_stretching
            if absolute_stretching > 0.0
            else 0.0
        ),
        "direction_gradient_rms": direction_gradient_rms,
        "helicity": helicity,
        "curl_weighted_energy": curl_weighted_energy,
        "helicity_fraction": (
            helicity / curl_weighted_energy if curl_weighted_energy > 0.0 else 0.0
        ),
        "energy_derivative": energy_derivative,
        "energy_balance_residual": energy_derivative + 2.0 * NU * enstrophy,
        "divergence_residual": float(torch.abs(divergence).max().item()),
        "vorticity_max": float(vorticity_magnitude.max().item()),
        "strain_max": float(torch.linalg.matrix_norm(strain, dim=(-2, -1)).max().item()),
    }

def integrate_case(
    case: dict[str, Any], cutoff: int, grid_size: int, steps: int, label: str
) -> dict[str, Any]:
    box = long_trajectory.TorchGalerkinBox(cutoff, grid_size)
    state, metadata = initial_state(case, box)
    dt = T_END / float(steps)
    rhs = box.right_hand_side(state)
    initial = metrics(box, state, rhs)
    checkpoint_steps = {int(round(fraction * steps)) for fraction in CHECKPOINT_FRACTIONS}
    checkpoints: list[dict[str, Any]] = []
    previous = initial
    previous_positive = initial["positive_production"]
    positive_integral = 0.0
    maximum_positive_production = previous_positive
    maximum_local_positive_stretching = initial["local_positive_stretching"]
    maximum_signed_production = initial["production"]
    maximum_absolute_production = abs(initial["production"])
    maximum_divergence = initial["divergence_residual"]
    maximum_energy_increment = 0.0
    maximum_energy_balance_residual = abs(initial["energy_balance_residual"])
    evaluation_count = 1

    def record_checkpoint(index: int, values: dict[str, float]) -> None:
        checkpoints.append(
            {
                "step": index,
                "time": index * dt,
                **values,
            }
        )

    record_checkpoint(0, initial)
    for index in range(steps):
        state = long_trajectory.rk4_update(box, state, dt, rhs)
        rhs = box.right_hand_side(state)
        current = metrics(box, state, rhs)
        evaluation_count += 1
        positive_integral += 0.5 * dt * (
            previous_positive + current["positive_production"]
        )
        previous_positive = current["positive_production"]
        maximum_positive_production = max(
            maximum_positive_production, current["positive_production"]
        )
        maximum_absolute_production = max(
            maximum_absolute_production, abs(current["production"])
        )
        maximum_signed_production = max(
            maximum_signed_production, current["production"]
        )
        maximum_local_positive_stretching = max(
            maximum_local_positive_stretching,
            current["local_positive_stretching"],
        )
        maximum_divergence = max(maximum_divergence, current["divergence_residual"])
        maximum_energy_increment = max(
            maximum_energy_increment,
            current["kinetic_energy"] - previous["kinetic_energy"],
        )
        maximum_energy_balance_residual = max(
            maximum_energy_balance_residual,
            abs(current["energy_balance_residual"]),
        )
        previous = current
        if index + 1 in checkpoint_steps:
            record_checkpoint(index + 1, current)

    result = {
        "case": case["name"],
        "family": case["family"],
        "cutoff": cutoff,
        "grid_size": grid_size,
        "steps": steps,
        "run": label,
        "backend": "torch-rocm",
        "device": torch.cuda.get_device_name(0),
        "dtype": "torch.float64",
        "dt": dt,
        "geometry_parameters": {
            key: value
            for key, value in case.items()
            if key not in {"name", "family"}
        },
        "initial_metadata": metadata,
        "initial": initial,
        "final": previous,
        "checkpoints": checkpoints,
        "maximum_positive_production": maximum_positive_production,
        "maximum_signed_production": maximum_signed_production,
        "maximum_local_positive_stretching": maximum_local_positive_stretching,
        "maximum_absolute_production": maximum_absolute_production,
        "maximum_divergence_residual": maximum_divergence,
        "maximum_positive_energy_increment": maximum_energy_increment,
        "maximum_energy_balance_residual": maximum_energy_balance_residual,
        "positive_part_evaluation_count": evaluation_count,
        "positive_stretching_integral": positive_integral,
    }
    del rhs, state, box
    torch.cuda.empty_cache()
    return result


def relative_change(left: float, right: float) -> float:
    return abs(left - right) / max(1.0, abs(left), abs(right))


def run_probe() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    with torch.no_grad():
        for case in CASES:
            for cutoff in CUTOFFS:
                grid_size = PRIMARY_GRID_FACTOR * cutoff + 1
                records.append(
                    integrate_case(case, cutoff, grid_size, PRIMARY_STEPS, "primary")
                )
                if cutoff == max(CUTOFFS):
                    records.append(
                        integrate_case(
                            case,
                            cutoff,
                            grid_size,
                            REFINED_STEPS,
                            "time_refined",
                        )
                    )

    checks: dict[str, dict[str, Any]] = {}

    def check(name: str, passed: bool, detail: Any) -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    expected_count = len(CASES) * (len(CUTOFFS) + 1)
    keys = {
        (record["case"], record["cutoff"], record["run"]): record for record in records
    }
    check(
        "declared_matrix_integrity",
        len(records) == expected_count and len(keys) == expected_count,
        {"expected_count": expected_count, "completed_count": len(records)},
    )
    check("finite_states_and_observables", all_finite(records), {"runs": len(records)})

    normalization_errors = {
        f"{record['case']}:N={record['cutoff']}:{record['run']}": record[
            "initial_metadata"
        ]["normalization_error"]
        for record in records
    }
    max_normalization_error = max(normalization_errors.values())
    check(
        "kinetic_normalization",
        max_normalization_error <= 1.0e-10,
        {"maximum": max_normalization_error, "bound": 1.0e-10},
    )

    max_divergence = max(record["maximum_divergence_residual"] for record in records)
    check(
        "divergence_residual",
        max_divergence <= 1.0e-10,
        {"maximum": max_divergence, "bound": 1.0e-10},
    )

    max_balance_residual = max(
        record["maximum_energy_balance_residual"] for record in records
    )
    check(
        "energy_balance_residual",
        max_balance_residual <= 1.0e-9,
        {"maximum": max_balance_residual, "bound": 1.0e-9},
    )

    max_energy_increment = max(
        record["maximum_positive_energy_increment"] for record in records
    )
    energy_increment_bound = 1.0e-9 * max(1.0, TARGET_KINETIC_ENERGY)
    check(
        "kinetic_energy_dissipation",
        max_energy_increment <= energy_increment_bound,
        {"maximum": max_energy_increment, "bound": energy_increment_bound},
    )

    max_direction_gradient = max(
        record["initial"]["direction_gradient_rms"] for record in records
    )
    check(
        "direction_diagnostics_finite",
        math.isfinite(max_direction_gradient),
        {"maximum_initial_direction_gradient_rms": max_direction_gradient},
    )

    max_initial_divergence = max(
        record["initial_metadata"]["state_divergence_residual"] for record in records
    )
    check(
        "initial_state_divergence",
        max_initial_divergence <= 1.0e-10,
        {"maximum": max_initial_divergence, "bound": 1.0e-10},
    )

    max_time_change = 0.0
    time_changes: dict[str, float] = {}
    for case in CASES:
        key = (case["name"], max(CUTOFFS))
        primary = keys[(key[0], key[1], "primary")]
        refined = keys[(key[0], key[1], "time_refined")]
        change = relative_change(
            primary["positive_stretching_integral"],
            refined["positive_stretching_integral"],
        )
        time_changes[f"{key[0]}:N={key[1]}"] = change
        max_time_change = max(max_time_change, change)
    check(
        "timestep_refinement",
        max_time_change <= 1.0e-4,
        {"maximum": max_time_change, "bound": 1.0e-4, "changes": time_changes},
    )

    direct_production_errors: dict[str, float] = {}
    for record in records:
        checkpoint_errors = [
            abs(checkpoint["spectral_production"] - checkpoint["production"])
            / max(1.0, abs(checkpoint["production"]))
            for checkpoint in record["checkpoints"]
        ]
        direct_production_errors[
            f"{record['case']}:N={record['cutoff']}:{record['run']}"
        ] = max(checkpoint_errors)
    max_direct_error = max(direct_production_errors.values())
    check(
        "direct_spectral_production_agreement",
        max_direct_error <= 1.0e-9,
        {"maximum_relative_error": max_direct_error, "bound": 1.0e-9},
    )

    # The sign hypothesis uses signed spatial production P(t)=∫ω·Sω.
    # Local positive stretching mass is retained separately as a diagnostic.
    max_signed_production_by_case = {
        case["name"]: max(
            record["maximum_signed_production"]
            for record in records
            if record["case"] == case["name"]
        )
        for case in CASES
    }
    max_positive_production_by_case = {
        case["name"]: max(
            record["maximum_positive_production"]
            for record in records
            if record["case"] == case["name"]
        )
        for case in CASES
    }
    max_positive_local_stretching_by_case = {
        case["name"]: max(
            record["maximum_local_positive_stretching"]
            for record in records
            if record["case"] == case["name"]
        )
        for case in CASES
    }
    max_abs_beltrami_production = max(
        record["maximum_absolute_production"]
        for record in records
        if record["case"] == "beltrami"
    )
    check(
        "beltrami_preserved_depletion",
        max_abs_beltrami_production <= BELTRAMI_PRODUCTION_TOLERANCE,
        {
            "maximum_trajectory_absolute_production": max_abs_beltrami_production,
            "bound": BELTRAMI_PRODUCTION_TOLERANCE,
        },
    )

    nonbeltrami_signed_maxima = {
        name: value
        for name, value in max_signed_production_by_case.items()
        if name != "beltrami"
    }
    sign_counterexample_cases = {
        name: value
        for name, value in nonbeltrami_signed_maxima.items()
        if value > POSITIVE_PRODUCTION_THRESHOLD
    }
    check(
        "positive_branch_detection",
        all(
            math.isfinite(value)
            for value in (
                *max_signed_production_by_case.values(),
                *max_positive_local_stretching_by_case.values(),
            )
        ),
        {
            "threshold": POSITIVE_PRODUCTION_THRESHOLD,
            "maximum_signed_production_by_case": max_signed_production_by_case,
            "maximum_positive_local_stretching_by_case": (
                max_positive_local_stretching_by_case
            ),
        },
    )

    all_passed = all(entry["passed"] for entry in checks.values())
    if not all_passed:
        scientific_classification = "FAIL"
    elif sign_counterexample_cases:
        scientific_classification = (
            "CONTRADICTS—universal sign-depletion in the declared helical family"
        )
    else:
        scientific_classification = (
            "INCONCLUSIVE—no positive signed-production branch in the declared "
            "non-Beltrami family"
        )

    case_classification: dict[str, str] = {
        "beltrami": (
            "PRESERVED"
            if max_abs_beltrami_production <= BELTRAMI_PRODUCTION_TOLERANCE
            else "FAIL"
        )
    }
    case_classification.update(
        {
            name: (
                "CONTRADICTS"
                if name in sign_counterexample_cases
                else "INCONCLUSIVE"
            )
            for name in nonbeltrami_signed_maxima
        }
    )


    return {
        "schema": SCHEMA,
        "protocol_revision": PROTOCOL_REVISION,
        "status": "PASS" if all_passed else "FAIL",
        "classification": scientific_classification,
        "case_classification": case_classification,
        "scope": {
            "equation": "original unforced 3-D incompressible Navier-Stokes",
            "backend": "torch-rocm",
            "device": torch.cuda.get_device_name(0),
            "dtype": "torch.float64",
            "nu": NU,
            "T": T_END,
            "target_kinetic_energy": TARGET_KINETIC_ENERGY,
            "cutoffs": list(CUTOFFS),
            "primary_steps": PRIMARY_STEPS,
            "refined_steps": REFINED_STEPS,
            "primary_grid": "6N+1",
            "theorem_target": "UNRESOLVED",
            "arbitrary_data_regularity": "UNRESOLVED",
            "dynamic_alignment_bound": "UNRESOLVED",
        },
        "checks": checks,
        "time_refinement": time_changes,
        "maximum_signed_production_by_case": max_signed_production_by_case,
        "maximum_positive_production_by_case": max_positive_production_by_case,
        "maximum_positive_local_stretching_by_case": (
            max_positive_local_stretching_by_case
        ),
        "runs": records,
        "source_hashes": {
            "computations/navier-stokes-helical-dynamic-depletion-prereg.md": sha256(
                PROTOCOL
            ),
            "computations/verify_navier_stokes_helical_dynamic_depletion.py": sha256(
                SCRIPT
            ),
            "computations/verify_navier_stokes_galerkin_long_trajectory.py": sha256(
                LONG_TRAJECTORY_SCRIPT
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def run_smoke() -> None:
    with torch.no_grad():
        for case in CASES[:2]:
            record = integrate_case(case, 8, 49, 16, "smoke")
            if not all_finite(record):
                raise RuntimeError(f"smoke produced a nonfinite value for {case['name']}")
            if record["initial_metadata"]["state_divergence_residual"] > 1.0e-10:
                raise RuntimeError(f"smoke failed divergence check for {case['name']}")
    print("smoke: PASS (ROCm, Beltrami and homochiral helical controls)")


def main() -> int:
    if not torch.cuda.is_available():
        raise SystemExit("ROCm Torch CUDA device is required")
    parser = argparse.ArgumentParser(description=__doc__)
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
