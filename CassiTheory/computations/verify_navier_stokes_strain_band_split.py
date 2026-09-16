"""Split vortex-stretching production between spectral strain bands on ROCm.

This verifier evolves the six declared families of
`computations/navier-stokes-strain-band-split-prereg.md` with the retained
Fourier-Galerkin integrator, reuses the retained helical-family construction
for identical geometry, and measures

    P_low(k_c) = integral of omega . S_{|k|<=k_c} omega

against the complementary high band. Band values, band energies, the band
identity residual, the strain operator norm and the accumulated strain dose
are recorded at every accepted state for the cutoffs k_c in {2, 4}.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "navier-stokes-strain-band-split-prereg.md"
SCRIPT = Path(__file__).resolve()
LONG_TRAJECTORY_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_galerkin_long_trajectory.py"
)
HELICAL_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_helical_dynamic_depletion.py"
)
DEFAULT_OUTPUT = ROOT / "runs" / "navier_stokes_strain_band_split" / "verification.json"
SCHEMA = "cassi.navier-stokes.strain-band-split.verification.v1"

NU = 0.1
T_END = 0.5
TARGET_KINETIC_ENERGY = 1.0
GRID_CUTOFFS = (16, 32)
BAND_CUTOFFS = (2, 4)
PRIMARY_STEPS = 1024
REFINED_STEPS = 2048
PRIMARY_GRID_FACTOR = 6
CHECKPOINT_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
BAND_IDENTITY_BOUND = 1.0e-10
BAND_PARSEVAL_BOUND = 1.0e-9
NORMALIZATION_BOUND = 1.0e-10
DIVERGENCE_BOUND = 1.0e-10
ENERGY_INCREMENT_BOUND = 1.0e-9
REFINEMENT_BOUND = 1.0e-4
BELTRAMI_BAND_BOUND = 1.0e-10
HIGH_BAND_SUPPORT_FRACTION = 0.1
LOW_BAND_SUPPORT_FRACTION = 0.5
HIGH_BAND_CONTRADICTION_FRACTION = 0.5

CASES: tuple[dict[str, Any], ...] = (
    {"name": "beltrami", "family": "single_curl_eigenmode"},
    {
        "name": "helix_wide",
        "family": "wide_helical_tube",
        "centerline_radius": 0.75,
        "pitch_turns": 1,
        "tube_radius": 0.5,
    },
    {
        "name": "helix_narrow",
        "family": "narrow_helical_tube",
        "centerline_radius": 0.75,
        "pitch_turns": 1,
        "tube_radius": 0.25,
    },
    {
        "name": "helix_tight_pitch",
        "family": "tight_pitch_helical_tube",
        "centerline_radius": 0.75,
        "pitch_turns": 4,
        "tube_radius": 0.25,
    },
    {
        "name": "two_scale_helices",
        "family": "two_scale_helices",
        "centerline_radius": 0.75,
        "pitch_turns": 1,
        "tube_radius": 0.5,
        "secondary_centerline_radius": 0.375,
        "secondary_pitch_turns": 4,
        "secondary_tube_radius": 0.25,
    },
    {
        "name": "opposite_handed_helices",
        "family": "opposite_handed_helices",
        "centerline_radius": 0.75,
        "pitch_turns": 3,
        "tube_radius": 0.25,
        "counter_pitch_turns": -3,
    },
)
TUBE_FAMILIES = tuple(
    case["name"] for case in CASES if case["name"] != "beltrami"
)


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


long_trajectory = load_module("navier_stokes_long_trajectory", LONG_TRAJECTORY_SCRIPT)
helical = load_module("navier_stokes_helical_dynamic_depletion", HELICAL_SCRIPT)
VOLUME = float(long_trajectory.VOLUME)
spectral_integral = helical.spectral_integral
spectral_energy = helical.spectral_energy


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
    if isinstance(value, float):
        return math.isfinite(value)
    return True


def relative_change(left: float, right: float) -> float:
    return abs(left - right) / max(1.0, abs(left), abs(right))


def packed_strain(
    box: Any, state: torch.Tensor, cutoff: int | None
) -> tuple[torch.Tensor, float]:
    """Return the six independent strain components and their spectral sum.

    Components are ordered (xx, xy, xz, yy, yz, zz). With a cutoff the strain
    is restricted to |k| <= cutoff before evaluation. The spectral sum is the
    Parseval weight sum of the Frobenius band energy demanded by the
    prereg, formed from the six unique components with the three
    off-diagonal entries counted twice; the physical counterpart sums the
    same nine entries, so the agreement check is exact. The sum is zero when
    no cutoff is declared.
    """
    gradient_coefficients = 1j * state[..., :, None] * box.wave_numbers[..., None, :]
    coefficients = 0.5 * (
        gradient_coefficients + torch.swapaxes(gradient_coefficients, -1, -2)
    )
    del gradient_coefficients
    spectral_sum = 0.0
    if cutoff is None:
        selection = box.nonzero
    else:
        selection = box.nonzero & (box.k2 <= float(cutoff) ** 2)
    coefficients = coefficients * selection[..., None, None]
    components = torch.stack(
        (
            coefficients[..., 0, 0],
            coefficients[..., 0, 1],
            coefficients[..., 0, 2],
            coefficients[..., 1, 1],
            coefficients[..., 1, 2],
            coefficients[..., 2, 2],
        ),
        dim=-1,
    )
    del coefficients
    if cutoff is not None:
        magnitude = torch.abs(components) ** 2
        spectral_sum = float(
            torch.sum(box.parseval_weight * packed_frobenius_energy(magnitude)).item()
        )
        del magnitude
    physical = box.grid(components)
    del components
    return physical, spectral_sum


def packed_frobenius_energy(squared: torch.Tensor) -> torch.Tensor:
    """Return the nine-entry Frobenius sum of packed squared values.

    Input: already-squared real strain components, or squared moduli in
    spectral space, in the packed order (xx, xy, xz, yy, yz, zz). The three
    off-diagonal entries are counted twice, which is the nine-entry sum the
    prereg's Parseval check takes as its denominator.
    """
    return squared.sum(dim=-1) + squared[..., 1] + squared[..., 2] + squared[..., 4]


def packed_quadratic_form(components: torch.Tensor, vorticity: torch.Tensor) -> torch.Tensor:
    """Return the pointwise omega . S omega form of packed strain components."""
    s00, s01, s02, s11, s12, s22 = components.unbind(dim=-1)
    w0, w1, w2 = vorticity.unbind(dim=-1)
    return (
        s00 * w0 * w0
        + s11 * w1 * w1
        + s22 * w2 * w2
        + 2.0 * (s01 * w0 * w1 + s02 * w0 * w2 + s12 * w1 * w2)
    )


def packed_matrix_vector(components: torch.Tensor, vorticity: torch.Tensor) -> torch.Tensor:
    """Return the pointwise matrix-vector product of packed strain with vorticity."""
    s00, s01, s02, s11, s12, s22 = components.unbind(dim=-1)
    w0, w1, w2 = vorticity.unbind(dim=-1)
    return torch.stack(
        (
            s00 * w0 + s01 * w1 + s02 * w2,
            s01 * w0 + s11 * w1 + s12 * w2,
            s02 * w0 + s12 * w1 + s22 * w2,
        ),
        dim=-1,
    )


def packed_operator_norm(components: torch.Tensor) -> torch.Tensor:
    """Return the exact spectral norm of symmetric packed 3x3 tensors.

    The trace-free part is diagonalized with the trigonometric solution of the
    depressed cubic; the smoke self-test compares the packed result against the
    exact spectral norm of the full strain matrices.
    """
    s00, s01, s02, s11, s12, s22 = components.unbind(dim=-1)
    mean = (s00 + s11 + s22) / 3.0
    b00, b11, b22 = s00 - mean, s11 - mean, s22 - mean
    half_trace = 0.5 * (
        b00 * b00 + b11 * b11 + b22 * b22 + 2.0 * (s01 * s01 + s02 * s02 + s12 * s12)
    )
    determinant = (
        b00 * (b11 * b22 - s12 * s12)
        - s01 * (s01 * b22 - s12 * s02)
        + s02 * (s01 * s12 - b11 * s02)
    )
    radius = torch.sqrt(torch.clamp(half_trace / 3.0, min=0.0))
    safe = torch.where(radius > 0.0, radius, torch.ones_like(radius))
    theta = torch.acos(torch.clamp(0.5 * determinant / safe**3, -1.0, 1.0))
    roots = torch.stack(
        (
            torch.cos(theta / 3.0),
            torch.cos((theta - 2.0 * math.pi) / 3.0),
            torch.cos((theta + 2.0 * math.pi) / 3.0),
        )
    )
    eigenvalues = mean + 2.0 * radius * roots
    extremes = torch.maximum(
        eigenvalues.max(dim=0).values.abs(), eigenvalues.min(dim=0).values.abs()
    )
    return torch.where(radius > 0.0, extremes, mean.abs())


def metrics(box: Any, state: torch.Tensor, rhs: torch.Tensor) -> dict[str, float]:
    components, _ = packed_strain(box, state, None)
    vorticity = box.grid(box.curl(state))
    vorticity_magnitude = torch.linalg.vector_norm(vorticity, dim=-1)
    full_density = packed_quadratic_form(components, vorticity)
    production = spectral_integral(box, full_density)

    values: dict[str, float] = {
        "production": production,
        "positive_production": max(production, 0.0),
        "vorticity_max": float(vorticity_magnitude.max().item()),
        "strain_operator_max": float(packed_operator_norm(components).max().item()),
    }

    maximum_band_identity = 0.0
    maximum_parseval = 0.0
    for cutoff in BAND_CUTOFFS:
        low_components, spectral_sum = packed_strain(box, state, cutoff)
        low_density = packed_quadratic_form(low_components, vorticity)
        low_band_production = spectral_integral(box, low_density)
        high_band_production = production - low_band_production
        physical_sum = float(
            torch.mean(packed_frobenius_energy(low_components * low_components)).item()
        )
        parseval = abs(physical_sum - spectral_sum) / max(1.0, abs(spectral_sum))
        maximum_parseval = max(maximum_parseval, parseval)
        identity = abs(production - low_band_production - high_band_production) / max(
            1.0, abs(production)
        )
        maximum_band_identity = max(maximum_band_identity, identity)
        low_band_coupling = packed_matrix_vector(low_components, vorticity)
        low_band_denominator = spectral_integral(
            box, vorticity_magnitude * torch.linalg.vector_norm(low_band_coupling, dim=-1)
        )
        high_band_coupling = packed_matrix_vector(components - low_components, vorticity)
        high_band_denominator = spectral_integral(
            box, vorticity_magnitude * torch.linalg.vector_norm(high_band_coupling, dim=-1)
        )
        tag = str(cutoff)
        values[f"low_band_production_k{tag}"] = low_band_production
        values[f"high_band_production_k{tag}"] = high_band_production
        values[f"low_band_alignment_k{tag}"] = (
            low_band_production / low_band_denominator
            if low_band_denominator > 0.0
            else 0.0
        )
        values[f"high_band_alignment_k{tag}"] = (
            high_band_production / high_band_denominator if high_band_denominator > 0.0 else 0.0
        )
        del low_components, low_density, low_band_coupling, high_band_coupling
    del full_density, components

    enstrophy = 0.5 * spectral_integral(box, torch.sum(vorticity * vorticity, dim=-1))
    vorticity_coefficients = box.curl(state)
    palinstrophy = 0.5 * VOLUME * float(
        torch.sum(
            box.parseval_weight[..., None]
            * box.k2[..., None]
            * torch.abs(vorticity_coefficients) ** 2
        ).item()
    )
    kinetic_energy = spectral_energy(box, state)
    parseval_weight = box.parseval_weight[..., None]
    helicity = VOLUME * float(
        torch.real(
            torch.sum(parseval_weight * torch.conj(state) * vorticity_coefficients)
        ).item()
    )
    curl_weighted_energy = VOLUME * float(
        torch.sum(parseval_weight * torch.sqrt(box.k2[..., None]) * torch.abs(state) ** 2).item()
    )
    energy_derivative = VOLUME * float(
        torch.real(torch.sum(parseval_weight * torch.conj(state) * rhs)).item()
    )
    divergence = (
        box.kx * state[..., 0] + box.ky * state[..., 1] + box.kz * state[..., 2]
    )
    values.update(
        {
            "kinetic_energy": kinetic_energy,
            "enstrophy": enstrophy,
            "palinstrophy": palinstrophy,
            "helicity": helicity,
            "curl_weighted_energy": curl_weighted_energy,
            "helicity_fraction": (
                helicity / curl_weighted_energy if curl_weighted_energy > 0.0 else 0.0
            ),
            "energy_derivative": energy_derivative,
            "energy_balance_residual": energy_derivative + 2.0 * NU * enstrophy,
            "divergence_residual": float(torch.abs(divergence).max().item()),
            "band_identity_residual": maximum_band_identity,
            "band_parseval_residual": maximum_parseval,
        }
    )
    return values


def integrate_case(
    case: dict[str, Any], grid_cutoff: int, grid_size: int, steps: int, label: str
) -> dict[str, Any]:
    box = long_trajectory.TorchGalerkinBox(grid_cutoff, grid_size)
    state, metadata = helical.initial_state(case, box)
    dt = T_END / float(steps)
    rhs = box.right_hand_side(state)
    initial = metrics(box, state, rhs)
    checkpoint_steps = {int(round(fraction * steps)) for fraction in CHECKPOINT_FRACTIONS}
    checkpoint_values: list[dict[str, Any]] = []
    previous = initial
    band_integrals = {cutoff: 0.0 for cutoff in BAND_CUTOFFS}
    local_integrals = {cutoff: 0.0 for cutoff in BAND_CUTOFFS}
    positive_integral = 0.0
    dose_integral = 0.0
    maxima = {
        "low_band_production": -math.inf,
        "high_band_production": -math.inf,
        "low_band_positive_integral": 0.0,
        "high_band_positive_integral": 0.0,
        "absolute_band_production": 0.0,
    }
    progress_start = time.time()
    previous_positive = initial["positive_production"]
    previous_low_band_positive = {
        cutoff: max(initial[f"low_band_production_k{cutoff}"], 0.0)
        for cutoff in BAND_CUTOFFS
    }
    previous_high_band_positive = {
        cutoff: max(initial[f"high_band_production_k{cutoff}"], 0.0)
        for cutoff in BAND_CUTOFFS
    }
    maximum_divergence = initial["divergence_residual"]
    maximum_energy_increment = 0.0
    maximum_balance_residual = abs(initial["energy_balance_residual"])
    maximum_band_identity = initial["band_identity_residual"]
    maximum_band_parseval = initial["band_parseval_residual"]
    maximum_absolute_production = abs(initial["production"])
    evaluations = 1

    checkpoint_values.append({"step": 0, "time": 0.0, **initial})
    for index in range(steps):
        state = long_trajectory.rk4_update(box, state, dt, rhs)
        rhs = box.right_hand_side(state)
        current = metrics(box, state, rhs)
        evaluations += 1
        positive_integral += 0.5 * dt * (
            previous_positive + current["positive_production"]
        )
        dose_integral += 0.5 * dt * (
            previous["strain_operator_max"] + current["strain_operator_max"]
        )
        previous_positive = current["positive_production"]
        maximum_absolute_production = max(
            maximum_absolute_production, abs(current["production"])
        )
        for band in BAND_CUTOFFS:
            low_band_value = current[f"low_band_production_k{band}"]
            high_band_value = current[f"high_band_production_k{band}"]
            band_integrals[band] += 0.5 * dt * (
                previous_low_band_positive[band] + max(low_band_value, 0.0)
            )
            local_integrals[band] += 0.5 * dt * (
                previous_high_band_positive[band] + max(high_band_value, 0.0)
            )
            previous_low_band_positive[band] = max(low_band_value, 0.0)
            previous_high_band_positive[band] = max(high_band_value, 0.0)
            maxima["low_band_production"] = max(
                maxima["low_band_production"], low_band_value
            )
            maxima["high_band_production"] = max(maxima["high_band_production"], high_band_value)
            maxima["absolute_band_production"] = max(
                maxima["absolute_band_production"],
                abs(low_band_value),
                abs(high_band_value),
            )
        maximum_divergence = max(maximum_divergence, current["divergence_residual"])
        maximum_energy_increment = max(
            maximum_energy_increment, current["kinetic_energy"] - previous["kinetic_energy"]
        )
        maximum_balance_residual = max(
            maximum_balance_residual, abs(current["energy_balance_residual"])
        )
        maximum_band_identity = max(
            maximum_band_identity, current["band_identity_residual"]
        )
        maximum_band_parseval = max(
            maximum_band_parseval, current["band_parseval_residual"]
        )
        previous = current
        if index + 1 in checkpoint_steps:
            checkpoint_values.append({"step": index + 1, "time": (index + 1) * dt, **current})
        if (index + 1) % 128 == 0:
            elapsed = time.time() - progress_start
            rate = (index + 1) / elapsed if elapsed > 0.0 else 0.0
            print(
                f"    {case['name']} N={grid_cutoff} {label} step {index + 1}/{steps} "
                f"({elapsed:.0f}s, {rate:.1f} states/s)",
                flush=True,
            )

    result = {
        "case": case["name"],
        "family": case["family"],
        "cutoff": grid_cutoff,
        "grid_size": grid_size,
        "steps": steps,
        "run": label,
        "backend": "torch-rocm",
        "device": torch.cuda.get_device_name(0),
        "dtype": "torch.float64",
        "dt": dt,
        "geometry_parameters": {
            key: value for key, value in case.items() if key not in {"name", "family"}
        },
        "initial_metadata": metadata,
        "initial": initial,
        "final": previous,
        "checkpoints": checkpoint_values,
        "positive_stretching_integral": positive_integral,
        "strain_dose_integral": dose_integral,
        "low_band_positive_integral": {
            str(band): band_integrals[band] for band in BAND_CUTOFFS
        },
        "high_band_positive_integral": {
            str(band): local_integrals[band] for band in BAND_CUTOFFS
        },
        "maximum_low_band_production": maxima["low_band_production"],
        "maximum_high_band_production": maxima["high_band_production"],
        "maximum_absolute_band_production": maxima["absolute_band_production"],
        "maximum_absolute_production": maximum_absolute_production,
        "maximum_divergence_residual": maximum_divergence,
        "maximum_positive_energy_increment": maximum_energy_increment,
        "maximum_energy_balance_residual": maximum_balance_residual,
        "maximum_band_identity_residual": maximum_band_identity,
        "maximum_band_parseval_residual": maximum_band_parseval,
        "state_evaluation_count": evaluations,
    }
    del rhs, state, box
    torch.cuda.empty_cache()
    return result


def case_ratios(record: dict[str, Any]) -> dict[str, dict[str, float]]:
    total = max(record["positive_stretching_integral"], 1.0e-12)
    ratios: dict[str, dict[str, float]] = {}
    for cutoff in BAND_CUTOFFS:
        tag = str(cutoff)
        ratios[tag] = {
            "high_band_fraction": record["high_band_positive_integral"][tag] / total,
            "low_band_fraction": record["low_band_positive_integral"][tag] / total,
            "total_positive_integral": record["positive_stretching_integral"],
        }
    return ratios


def run_probe() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    with torch.no_grad():
        for case in CASES:
            for cutoff in GRID_CUTOFFS:
                grid_size = PRIMARY_GRID_FACTOR * cutoff + 1
                print(
                    f"[run] {case['name']} primary N={cutoff} M={grid_size} "
                    f"steps={PRIMARY_STEPS}",
                    flush=True,
                )
                records.append(
                    integrate_case(case, cutoff, grid_size, PRIMARY_STEPS, "primary")
                )
            refined_grid = PRIMARY_GRID_FACTOR * GRID_CUTOFFS[-1] + 1
            print(
                f"[run] {case['name']} time_refined N={GRID_CUTOFFS[-1]} "
                f"M={refined_grid} steps={REFINED_STEPS}",
                flush=True,
            )
            records.append(
                integrate_case(
                    case, GRID_CUTOFFS[-1], refined_grid, REFINED_STEPS, "time_refined"
                )
            )
            summary = records[-3:]
            for entry in summary:
                bands = ", ".join(
                    f"k{band} low={entry['low_band_positive_integral'][str(band)]:.6e} "
                    f"high={entry['high_band_positive_integral'][str(band)]:.6e}"
                    for band in BAND_CUTOFFS
                )
                print(
                    f"[done] {entry['case']} {entry['run']} N={entry['cutoff']} "
                    f"I+={entry['positive_stretching_integral']:.6e} {bands}",
                    flush=True,
                )

    by_key = {
        (record["case"], int(record["cutoff"]), record["run"]): record
        for record in records
    }
    checks: dict[str, Any] = {}

    def check(name: str, passed: bool, detail: Any) -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    expected = len(CASES) * (len(GRID_CUTOFFS) + 1)
    check("declared_run_count", len(records) == expected, len(records))
    check(
        "finite_values",
        all(all_finite(record) for record in records),
        sum(1 for record in records if not all_finite(record)),
    )
    check(
        "kinetic_normalization",
        max(
            record["initial_metadata"]["normalization_error"] for record in records
        )
        <= NORMALIZATION_BOUND,
        max(record["initial_metadata"]["normalization_error"] for record in records),
    )
    check(
        "divergence_residual",
        max(record["maximum_divergence_residual"] for record in records)
        <= DIVERGENCE_BOUND,
        max(record["maximum_divergence_residual"] for record in records),
    )
    check(
        "band_identity",
        max(record["maximum_band_identity_residual"] for record in records)
        <= BAND_IDENTITY_BOUND,
        max(record["maximum_band_identity_residual"] for record in records),
    )
    check(
        "band_parseval",
        max(record["maximum_band_parseval_residual"] for record in records)
        <= BAND_PARSEVAL_BOUND,
        max(record["maximum_band_parseval_residual"] for record in records),
    )
    check(
        "energy_increment",
        max(record["maximum_positive_energy_increment"] for record in records)
        <= ENERGY_INCREMENT_BOUND,
        max(record["maximum_positive_energy_increment"] for record in records),
    )
    balance_ratios = {
        f"{record['case']}@{record['cutoff']}:{record['run']}": abs(
            record["maximum_energy_balance_residual"]
        )
        / max(
            1.0,
            abs(record["initial"]["energy_derivative"]),
            2.0 * NU * record["initial"]["enstrophy"],
        )
        for record in records
    }
    check(
        "energy_balance",
        max(balance_ratios.values()) <= ENERGY_INCREMENT_BOUND,
        max(balance_ratios.values()),
    )
    refinement_changes = {}
    for case in CASES:
        name = case["name"]
        primary = by_key[(name, GRID_CUTOFFS[-1], "primary")]
        refined = by_key[(name, GRID_CUTOFFS[-1], "time_refined")]
        for key in ("positive_stretching_integral", "strain_dose_integral"):
            refinement_changes[f"{name}:{key}"] = relative_change(
                primary[key], refined[key]
            )
        for cutoff in BAND_CUTOFFS:
            tag = str(cutoff)
            refinement_changes[f"{name}:low@{tag}"] = relative_change(
                primary["low_band_positive_integral"][tag],
                refined["low_band_positive_integral"][tag],
            )
            refinement_changes[f"{name}:high@{tag}"] = relative_change(
                primary["high_band_positive_integral"][tag],
                refined["high_band_positive_integral"][tag],
            )
    maximum_refinement = max(refinement_changes.values())
    check("timestep_refinement", maximum_refinement <= REFINEMENT_BOUND, maximum_refinement)
    beltrami_records = [record for record in records if record["case"] == "beltrami"]
    beltrami_maximum = max(
        record["maximum_absolute_band_production"] for record in beltrami_records
    )
    check(
        "beltrami_band_control",
        beltrami_maximum <= BELTRAMI_BAND_BOUND,
        beltrami_maximum,
    )

    ratios = {
        name: case_ratios(by_key[(name, GRID_CUTOFFS[-1], "primary")])
        for name in TUBE_FAMILIES
    }
    family_verdicts: dict[str, dict[str, Any]] = {}
    for name in TUBE_FAMILIES:
        per_cutoff = {}
        for cutoff in BAND_CUTOFFS:
            tag = str(cutoff)
            high_band_fraction = ratios[name][tag]["high_band_fraction"]
            low_band_fraction = ratios[name][tag]["low_band_fraction"]
            if high_band_fraction > HIGH_BAND_CONTRADICTION_FRACTION:
                verdict = "CONTRADICTS"
            elif (
                high_band_fraction <= HIGH_BAND_SUPPORT_FRACTION
                and low_band_fraction >= LOW_BAND_SUPPORT_FRACTION
            ):
                verdict = "SUPPORTS"
            else:
                verdict = "INCONCLUSIVE"
            per_cutoff[tag] = {
                "high_band_fraction": high_band_fraction,
                "low_band_fraction": low_band_fraction,
                "verdict": verdict,
            }
        verdicts = {entry["verdict"] for entry in per_cutoff.values()}
        family_verdicts[name] = {
            "per_cutoff": per_cutoff,
            "verdict": verdicts.pop() if len(verdicts) == 1 else "INCONCLUSIVE",
        }

    family_verdict_values = {entry["verdict"] for entry in family_verdicts.values()}
    if "CONTRADICTS" in family_verdict_values:
        classification = "CONTRADICTS"
    elif family_verdict_values == {"SUPPORTS"}:
        classification = "SUPPORTS"
    else:
        classification = "INCONCLUSIVE"

    integrity_passed = all(entry["passed"] for entry in checks.values())
    dosage = {
        name: by_key[(name, GRID_CUTOFFS[-1], "primary")]["strain_dose_integral"]
        for name in TUBE_FAMILIES
    }
    receipt = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if integrity_passed else "FAIL",
        "classification": classification,
        "classification_scope": "low-band dominance of positive production at the declared spectral cutoffs",
        "scope": {
            "equation": "unforced incompressible Navier-Stokes on the 2*pi torus",
            "nu": NU,
            "T": T_END,
            "grid_cutoffs": list(GRID_CUTOFFS),
            "band_cutoffs": list(BAND_CUTOFFS),
            "primary_steps": PRIMARY_STEPS,
            "refined_steps": REFINED_STEPS,
            "primary_grid": f"{PRIMARY_GRID_FACTOR}N+1",
            "checkpoints": list(CHECKPOINT_FRACTIONS),
            "families": [case["name"] for case in CASES],
        },
        "checks": checks,
        "ratios": ratios,
        "family_verdicts": family_verdicts,
        "strain_dose": dosage,
        "refinement_changes": refinement_changes,
        "runs": records,
        "source_hashes": {
            "computations/navier-stokes-strain-band-split-prereg.md": sha256(PROTOCOL),
            "computations/verify_navier_stokes_strain_band_split.py": sha256(SCRIPT),
            "computations/verify_navier_stokes_galerkin_long_trajectory.py": sha256(
                LONG_TRAJECTORY_SCRIPT
            ),
            "computations/verify_navier_stokes_helical_dynamic_depletion.py": sha256(
                HELICAL_SCRIPT
            ),
        },
    }
    return receipt


def self_test_packed_path() -> None:
    """Check the packed strain path against the retained full-matrix path."""
    box = long_trajectory.TorchGalerkinBox(8, 33)
    state, _ = helical.initial_state(CASES[0], box)
    band = BAND_CUTOFFS[0]
    full_packed, _ = packed_strain(box, state, None)
    packed_components, packed_spectral = packed_strain(box, state, band)
    full_strain, vorticity = box.strain_and_vorticity(state)
    gradient = 1j * state[..., :, None] * box.wave_numbers[..., None, :]
    strain_coefficients = 0.5 * (gradient + torch.swapaxes(gradient, -1, -2))
    mask = box.nonzero & (box.k2 <= float(band) ** 2)
    masked = strain_coefficients * mask[..., None, None]
    full_spectral = float(
        torch.sum(box.parseval_weight[..., None, None] * torch.abs(masked) ** 2).item()
    )
    masked_physical = box.grid(masked)
    full_physical = float(torch.mean(torch.sum(masked_physical**2, dim=(-2, -1))).item())
    packed_physical = float(
        torch.mean(packed_frobenius_energy(packed_components * packed_components)).item()
    )
    reference_norm = float(
        torch.linalg.matrix_norm(full_strain, dim=(-2, -1), ord=2).max().item()
    )
    frobenius_norm = float(
        torch.linalg.matrix_norm(full_strain, dim=(-2, -1)).max().item()
    )
    packed_norm = float(packed_operator_norm(full_packed).max().item())
    packed_form = spectral_integral(box, packed_quadratic_form(full_packed, vorticity))
    full_form = spectral_integral(
        box, torch.einsum("...i,...ij,...j->...", vorticity, full_strain, vorticity)
    )
    scale = max(1.0, abs(full_form), abs(full_physical), abs(full_spectral))
    deviations = {
        "operator_norm": abs(packed_norm - reference_norm) / max(1.0, reference_norm),
        "quadratic_form": abs(packed_form - full_form) / scale,
        "physical_sum": abs(packed_physical - full_physical) / scale,
        "spectral_sum": abs(packed_spectral - full_spectral) / scale,
    }
    worst = max(deviations.values())
    print(
        "smoke equivalence: " + ", ".join(f"{k}={v:.3e}" for k, v in deviations.items())
    )
    print(
        f"smoke norms: operator={packed_norm:.6e} reference={reference_norm:.6e} "
        f"frobenius={frobenius_norm:.6e}"
    )
    if worst > 1.0e-12:
        raise SystemExit(f"smoke FAILED: packed strain path deviates by {worst:.3e}")


def run_smoke() -> None:
    with torch.no_grad():
        for case in CASES[:2]:
            record = integrate_case(case, 8, 49, 16, "smoke")
            if record["cutoff"] != 8 or record["grid_size"] != 49:
                raise SystemExit(
                    f"smoke FAILED: record labels drifted to "
                    f"cutoff={record['cutoff']} grid={record['grid_size']}"
                )
            print(
                f"smoke: {record['case']} P={record['final']['production']:.6e} "
                f"P_nl(k2)={record['final']['low_band_production_k2']:.6e} "
                f"P_loc(k2)={record['final']['high_band_production_k2']:.6e} "
                f"identity={record['maximum_band_identity_residual']:.2e} "
                f"parseval={record['maximum_band_parseval_residual']:.2e}"
            )
        self_test_packed_path()


def main() -> int:
    if not torch.cuda.is_available():
        raise SystemExit("ROCm Torch CUDA device is required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--smoke", action="store_true")
    arguments = parser.parse_args()
    if arguments.smoke:
        run_smoke()
        return 0

    receipt = run_probe()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    failed = [name for name, entry in receipt["checks"].items() if not entry["passed"]]
    print(f"status={receipt['status']} classification={receipt['classification']}")
    print(f"checks: {len(receipt['checks']) - len(failed)}/{len(receipt['checks'])} passed")
    for name in failed:
        print(f"FAILED {name}: {receipt['checks'][name]['detail']}")
    for name, entry in receipt["family_verdicts"].items():
        detail = entry["per_cutoff"]
        print(
            f"{name}: {entry['verdict']} "
            f"(k2 high={detail['2']['high_band_fraction']:.6f} "
            f"low={detail['2']['low_band_fraction']:.6f}; "
            f"k4 high={detail['4']['high_band_fraction']:.6f} "
            f"low={detail['4']['low_band_fraction']:.6f})"
        )
    print(f"receipt: {arguments.output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
