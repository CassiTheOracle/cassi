#!/usr/bin/env python3
"""Run the preregistered connected toroidal hierarchy campaign."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

_V5_PATH = Path(__file__).with_name("toroidal_coherence_survival_v5_probe.py")
_V5_SPEC = importlib.util.spec_from_file_location("toroidal_coherence_survival_v5_probe", _V5_PATH)
if _V5_SPEC is None or _V5_SPEC.loader is None:
    raise ImportError(f"cannot load {_V5_PATH}")
v5 = importlib.util.module_from_spec(_V5_SPEC)
_V5_SPEC.loader.exec_module(v5)

ROOT = Path(__file__).resolve().parents[1]
SCALES = ("core", "loop", "envelope")
MASS_FRACTIONS = {"core": 0.25, "loop": 0.50, "envelope": 0.25}
COUPLINGS = {
    "full": ((1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0)),
    "decoupled": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "chain": ((1.0, 1.0, 0.0), (1.0, 1.0, 1.0), (0.0, 1.0, 1.0)),
    "loop_disconnected": ((1.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 1.0)),
}
ARMS = (
    {"id": "A", "name": "full", "graph": "full", "n": 64, "dt": 0.0025},
    {"id": "B", "name": "decoupled", "graph": "decoupled", "n": 64, "dt": 0.0025},
    {"id": "C", "name": "nearest_neighbor", "graph": "chain", "n": 64, "dt": 0.0025},
    {"id": "D", "name": "loop_disconnected", "graph": "loop_disconnected", "n": 64, "dt": 0.0025},
    {"id": "E", "name": "high_resolution", "graph": "full", "n": 80, "dt": 0.0025},
    {"id": "F", "name": "half_step", "graph": "full", "n": 64, "dt": 0.00125},
)
BOX_SIZE = 16.0
T_END = 4.0
REPORT_CADENCE = 0.25
CORE_SIGMA = 0.80
ENVELOPE_RADIUS = 6.0
ENVELOPE_SIGMA = 0.80
PHI = (1.0 + math.sqrt(5.0)) / 2.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scalar(value: torch.Tensor | float) -> float:
    return float(value.detach().cpu().item() if isinstance(value, torch.Tensor) else value)


def make_grid(n: int, device: torch.device) -> dict[str, Any]:
    grid = v5.v4.make_grid(n, device)
    radius = torch.sqrt(grid["x"] ** 2 + grid["y"] ** 2 + grid["z"] ** 2)
    fundamental = 2.0 * math.pi / BOX_SIZE
    grid["radius"] = radius
    grid["fine_mask"] = grid["k2"] >= (8.0 * fundamental) ** 2
    return grid



def pair_kinetic(pair: tuple[torch.Tensor, torch.Tensor], grid: dict[str, Any]) -> float:
    kinetic = torch.zeros((), device=pair[0].device, dtype=torch.float64)
    for field in pair:
        laplacian = torch.fft.ifftn(-grid["k2"] * torch.fft.fftn(field))
        kinetic = kinetic - 0.5 * torch.sum(torch.real(torch.conj(field) * laplacian)) * grid["dv"]
    return scalar(kinetic)


def normalize_pair(
    amplitude: torch.Tensor,
    grid: dict[str, Any],
    total_mass: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    phase = torch.zeros_like(amplitude)
    return v5.v4.normalize_components(amplitude, amplitude.clone(), phase, phase, grid, total_mass)


def make_fields(
    grid: dict[str, Any],
    total_mass: float,
) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    radius = grid["radius"]
    core_amplitude = torch.exp(-(radius**2) / (4.0 * CORE_SIGMA**2))
    envelope_amplitude = torch.exp(
        -((radius - ENVELOPE_RADIUS) ** 2) / (4.0 * ENVELOPE_SIGMA**2)
    )
    return {
        "core": normalize_pair(core_amplitude, grid, total_mass * MASS_FRACTIONS["core"]),
        "loop": v5.v4.v3.base.make_seed(
            "closed", grid, total_mass * MASS_FRACTIONS["loop"]
        ),
        "envelope": normalize_pair(
            envelope_amplitude, grid, total_mass * MASS_FRACTIONS["envelope"]
        ),
    }


def scale_densities(
    fields: dict[str, tuple[torch.Tensor, torch.Tensor]],
) -> dict[str, torch.Tensor]:
    return {
        scale: torch.abs(pair[0]) ** 2 + torch.abs(pair[1]) ** 2
        for scale, pair in fields.items()
    }


def solve_density(density: torch.Tensor, grid: dict[str, Any]) -> torch.Tensor:
    source_hat = torch.fft.fftn(density - torch.mean(density))
    potential_hat = torch.zeros_like(source_hat)
    nonzero = grid["k2"] > 0.0
    potential_hat[nonzero] = -source_hat[nonzero] / grid["k2"][nonzero]
    return torch.fft.ifftn(potential_hat).real


def effective_potentials(
    fields: dict[str, tuple[torch.Tensor, torch.Tensor]],
    matrix: tuple[tuple[float, ...], ...],
    grid: dict[str, Any],
) -> dict[str, torch.Tensor]:
    densities = scale_densities(fields)
    cache: dict[tuple[float, ...], torch.Tensor] = {}
    result: dict[str, torch.Tensor] = {}
    for scale, row in zip(SCALES, matrix):
        if row not in cache:
            source = torch.zeros_like(densities["core"])
            for weight, source_scale in zip(row, SCALES):
                if weight != 0.0:
                    source = source + weight * densities[source_scale]
            cache[row] = solve_density(source, grid)
        result[scale] = cache[row]
    return result


def kick(
    fields: dict[str, tuple[torch.Tensor, torch.Tensor]],
    potentials: dict[str, torch.Tensor],
    matrix: tuple[tuple[float, ...], ...],
    half_step: float,
) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    phase_cache: dict[tuple[float, ...], torch.Tensor] = {}
    kicked: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
    for scale, row in zip(SCALES, matrix):
        if row not in phase_cache:
            phase_cache[row] = torch.exp(-1j * half_step * potentials[scale])
        phase = phase_cache[row]
        pair = fields[scale]
        kicked[scale] = (pair[0] * phase, pair[1] * phase)
    return kicked


def drift(
    fields: dict[str, tuple[torch.Tensor, torch.Tensor]],
    kinetic_phase: torch.Tensor,
) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    return {
        scale: tuple(
            torch.fft.ifftn(torch.fft.fftn(field) * kinetic_phase) for field in pair
        )
        for scale, pair in fields.items()
    }


def scale_snapshot(
    pair: tuple[torch.Tensor, torch.Tensor],
    potential: torch.Tensor,
    grid: dict[str, Any],
) -> dict[str, float]:
    density_y = torch.abs(pair[0]) ** 2
    density_i = torch.abs(pair[1]) ** 2
    density = density_y + density_i
    mass_y = scalar(torch.sum(density_y) * grid["dv"])
    mass_i = scalar(torch.sum(density_i) * grid["dv"])
    mass = mass_y + mass_i
    kinetic = pair_kinetic(pair, grid)
    potential_energy = scalar(0.5 * torch.sum(density * potential) * grid["dv"])
    mean_radius = scalar(torch.sum(density * grid["radius"]) * grid["dv"] / mass)
    mean_radius2 = scalar(torch.sum(density * grid["radius"] ** 2) * grid["dv"] / mass)
    rms_radius = math.sqrt(max(mean_radius2, 0.0))
    radial_width = math.sqrt(max(mean_radius2 - mean_radius**2, 0.0))
    modal_density = torch.abs(torch.fft.fftn(pair[0])) ** 2 + torch.abs(
        torch.fft.fftn(pair[1])
    ) ** 2
    fine_fraction = scalar(
        torch.sum(modal_density[grid["fine_mask"]]) / torch.sum(modal_density)
    )
    return {
        "mass": mass,
        "mass_y": mass_y,
        "mass_i": mass_i,
        "component_ratio": mass_y / mass_i,
        "kinetic": kinetic,
        "potential": potential_energy,
        "energy": kinetic + potential_energy,
        "mean_radius": mean_radius,
        "rms_radius": rms_radius,
        "radial_width": radial_width,
        "max_density": scalar(torch.max(density)),
        "fine_mass_fraction": fine_fraction,
    }


def capture_snapshot(
    fields: dict[str, tuple[torch.Tensor, torch.Tensor]],
    potentials: dict[str, torch.Tensor],
    grid: dict[str, Any],
    time_value: float,
    initial_loop_center: list[float] | None,
) -> dict[str, Any]:
    scales = {
        scale: scale_snapshot(fields[scale], potentials[scale], grid) for scale in SCALES
    }
    loop = v5.diagnose(
        fields["loop"][0],
        fields["loop"][1],
        grid,
        1.0,
        time_value,
        potentials["loop"],
        initial_loop_center,
    )
    densities = scale_densities(fields)
    self_potential = 0.0
    for scale in SCALES:
        own_potential = solve_density(densities[scale], grid)
        self_potential += scalar(
            0.5 * torch.sum(densities[scale] * own_potential) * grid["dv"]
        )
    total_kinetic = sum(scales[scale]["kinetic"] for scale in SCALES)
    total_potential = sum(scales[scale]["potential"] for scale in SCALES)
    return {
        "time": time_value,
        "scales": scales,
        "loop": loop,
        "total_mass": sum(scales[scale]["mass"] for scale in SCALES),
        "total_kinetic": total_kinetic,
        "total_potential": total_potential,
        "total_energy": total_kinetic + total_potential,
        "interaction_energy": total_potential - self_potential,
        "virial": 2.0 * total_kinetic + total_potential,
    }


def arm_summary(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    initial = metrics[0]
    final = metrics[-1]
    energy_scale = max(abs(initial["total_energy"]), 1e-30)
    energy_deltas = {
        scale: (final["scales"][scale]["energy"] - initial["scales"][scale]["energy"])
        / energy_scale
        for scale in SCALES
    }
    mass_drifts = {
        scale: max(
            abs(row["scales"][scale]["mass"] - initial["scales"][scale]["mass"])
            / initial["scales"][scale]["mass"]
            for row in metrics
        )
        for scale in SCALES
    }
    scale_energy_drifts = {
        scale: max(
            abs(row["scales"][scale]["energy"] - initial["scales"][scale]["energy"])
            / energy_scale
            for row in metrics
        )
        for scale in SCALES
    }
    helical_retention = final["loop"]["helix_order"] / initial["loop"]["helix_order"]
    radius_retention = final["loop"]["r_fit"] / initial["loop"]["r_fit"]
    return {
        "final_time": final["time"],
        "mass_drifts": mass_drifts,
        "max_mass_drift": max(mass_drifts.values()),
        "total_energy_drift": max(
            abs(row["total_energy"] - initial["total_energy"]) / energy_scale
            for row in metrics
        ),
        "scale_energy_drifts": scale_energy_drifts,
        "energy_delta_fractions": energy_deltas,
        "exchange_amplitude": 0.5 * sum(abs(value) for value in energy_deltas.values()),
        "loop_energy_delta_fraction": energy_deltas["loop"],
        "loop_helical_retention": helical_retention,
        "loop_radius_retention": radius_retention,
        "loop_final_winding_y": final["loop"]["winding_y"],
        "loop_final_winding_i": final["loop"]["winding_i"],
        "loop_winding_survives": bool(
            abs(final["loop"]["winding_y"] - 2.0) <= 0.1
            and abs(final["loop"]["winding_i"] + 3.0) <= 0.1
        ),
        "loop_fine_mass_change": (
            final["scales"]["loop"]["fine_mass_fraction"]
            - initial["scales"]["loop"]["fine_mass_fraction"]
        ),
        "initial_interaction_energy": initial["interaction_energy"],
        "final_interaction_energy": final["interaction_energy"],
        "final_scale_mean_radii": {
            scale: final["scales"][scale]["mean_radius"] for scale in SCALES
        },
    }


def evolve_arm(
    arm: dict[str, Any],
    total_mass: float,
    device: torch.device,
    run_dir: Path,
) -> dict[str, Any]:
    grid = make_grid(arm["n"], device)
    fields = make_fields(grid, total_mass)
    matrix = COUPLINGS[arm["graph"]]
    dt = float(arm["dt"])
    steps = round(T_END / dt)
    report_steps = round(REPORT_CADENCE / dt)
    cube_root_two = 2.0 ** (1.0 / 3.0)
    w1 = 1.0 / (2.0 - cube_root_two)
    w0 = -cube_root_two / (2.0 - cube_root_two)
    coefficients = (w1, w0, w1)
    kinetic_phases = tuple(
        torch.exp(-0.5j * grid["k2"] * (coefficient * dt))
        for coefficient in coefficients
    )
    potentials = effective_potentials(fields, matrix, grid)
    initial_densities = scale_densities(fields)
    initial_total_density = sum(
        (initial_densities[scale] for scale in SCALES),
        torch.zeros_like(initial_densities["core"]),
    )
    initial_max_density = scalar(torch.max(initial_total_density))
    metrics: list[dict[str, Any]] = []
    initial_loop_center: list[float] | None = None
    status = "complete"
    stop_reason: str | None = None

    def capture(step: int) -> None:
        nonlocal initial_loop_center
        row = capture_snapshot(
            fields, potentials, grid, step * dt, initial_loop_center
        )
        if initial_loop_center is None:
            initial_loop_center = row["loop"]["center"]
            row["loop"]["center_displacement"] = 0.0
        metrics.append(row)

    capture(0)
    last_step = 0
    for step in range(1, steps + 1):
        for coefficient, kinetic_phase in zip(coefficients, kinetic_phases):
            substep = coefficient * dt
            fields = kick(fields, potentials, matrix, 0.5 * substep)
            fields = drift(fields, kinetic_phase)
            potentials = effective_potentials(fields, matrix, grid)
            fields = kick(fields, potentials, matrix, 0.5 * substep)
        last_step = step
        densities = scale_densities(fields)
        total_density = sum(
            (densities[scale] for scale in SCALES),
            torch.zeros_like(densities["core"]),
        )
        if not bool(torch.isfinite(total_density).all().item()):
            status, stop_reason = "stopped", "nonfinite field"
            break
        if scalar(torch.max(total_density)) > 1.0e8 * initial_max_density:
            status, stop_reason = "stopped", "density ceiling"
            break
        if step % report_steps == 0:
            capture(step)
    if metrics[-1]["time"] != last_step * dt:
        capture(last_step)

    final_arrays = {
        f"{scale}_{component}": fields[scale][index].detach().cpu().numpy().copy()
        for scale in SCALES
        for index, component in enumerate(("y", "i"))
    }
    fields_path = run_dir / f"fields_{arm['id']}.npz"
    np.savez_compressed(
        fields_path,
        time=np.asarray(last_step * dt),
        core_y=final_arrays["core_y"],
        core_i=final_arrays["core_i"],
        loop_y=final_arrays["loop_y"],
        loop_i=final_arrays["loop_i"],
        envelope_y=final_arrays["envelope_y"],
        envelope_i=final_arrays["envelope_i"],
    )
    finite = all(np.isfinite(array).all() for array in final_arrays.values())
    dtype_ok = all(array.dtype == np.complex128 for array in final_arrays.values())
    return {
        "config": arm,
        "coupling_matrix": matrix,
        "status": status,
        "stop_reason": stop_reason,
        "finite": finite,
        "dtype_ok": dtype_ok,
        "metrics": metrics,
        "summary": arm_summary(metrics),
        "fields_file": fields_path.name,
        "fields_sha256": sha256_file(fields_path),
    }


def comparison(
    first: dict[str, Any],
    second: dict[str, Any],
    helix_limit: float,
    radius_limit: float,
    energy_limit: float,
    exchange_limit: float,
) -> dict[str, Any]:
    differences = {
        "loop_helical_retention": abs(
            first["loop_helical_retention"] - second["loop_helical_retention"]
        ),
        "loop_radius_retention": abs(
            first["loop_radius_retention"] - second["loop_radius_retention"]
        ),
        "exchange_amplitude": abs(
            first["exchange_amplitude"] - second["exchange_amplitude"]
        ),
        "energy_delta_fractions": {
            scale: abs(
                first["energy_delta_fractions"][scale]
                - second["energy_delta_fractions"][scale]
            )
            for scale in SCALES
        },
    }
    winding_directions_agree = bool(
        math.copysign(1.0, first["loop_final_winding_y"])
        == math.copysign(1.0, second["loop_final_winding_y"])
        and math.copysign(1.0, first["loop_final_winding_i"])
        == math.copysign(1.0, second["loop_final_winding_i"])
    )
    passed = bool(
        differences["loop_helical_retention"] <= helix_limit
        and differences["loop_radius_retention"] <= radius_limit
        and differences["exchange_amplitude"] <= exchange_limit
        and all(
            value <= energy_limit
            for value in differences["energy_delta_fractions"].values()
        )
        and winding_directions_agree
    )
    return {
        "pass": passed,
        "differences": differences,
        "winding_directions_agree": winding_directions_agree,
    }


def loop_field_isolation(run_dir: Path, arms: dict[str, Any]) -> dict[str, Any]:
    arrays: dict[str, dict[str, np.ndarray]] = {}
    for arm_id in ("B", "D"):
        with np.load(run_dir / arms[arm_id]["fields_file"]) as receipt:
            arrays[arm_id] = {key: receipt[key] for key in ("loop_y", "loop_i")}
    field_errors = {}
    for key in ("loop_y", "loop_i"):
        denominator = max(float(np.max(np.abs(arrays["B"][key]))), 1e-30)
        field_errors[key] = float(
            np.max(np.abs(arrays["B"][key] - arrays["D"][key])) / denominator
        )
    b = arms["B"]["summary"]
    d = arms["D"]["summary"]
    metric_errors = {
        "loop_helical_retention": abs(
            b["loop_helical_retention"] - d["loop_helical_retention"]
        ),
        "loop_radius_retention": abs(
            b["loop_radius_retention"] - d["loop_radius_retention"]
        ),
        "loop_energy_delta_fraction": abs(
            b["loop_energy_delta_fraction"] - d["loop_energy_delta_fraction"]
        ),
    }
    return {
        "pass": bool(
            max(field_errors.values()) <= 1e-10
            and max(metric_errors.values()) <= 1e-10
        ),
        "field_relative_inf_errors": field_errors,
        "metric_errors": metric_errors,
    }


def evaluate(
    arms: dict[str, Any],
    run_dir: Path,
) -> tuple[dict[str, Any], str, str, str, dict[str, Any]]:
    q1_details = {
        arm_id: {
            "complete": arm["status"] == "complete",
            "finite": arm["finite"],
            "dtype_ok": arm["dtype_ok"],
            "max_mass_drift": arm["summary"]["max_mass_drift"],
        }
        for arm_id, arm in arms.items()
    }
    q1 = all(
        details["complete"]
        and details["finite"]
        and details["dtype_ok"]
        and details["max_mass_drift"] <= 2e-9
        for details in q1_details.values()
    )
    q2_details = {
        arm_id: {
            "total_energy_drift": arm["summary"]["total_energy_drift"],
            "scale_energy_drifts": arm["summary"]["scale_energy_drifts"],
        }
        for arm_id, arm in arms.items()
    }
    q2 = all(
        details["total_energy_drift"] <= 5e-3 for details in q2_details.values()
    ) and all(value <= 5e-3 for value in q2_details["B"]["scale_energy_drifts"].values())
    q3 = comparison(arms["A"]["summary"], arms["F"]["summary"], 0.08, 0.05, 0.03, 0.03)
    q4 = comparison(arms["A"]["summary"], arms["E"]["summary"], 0.10, 0.08, 0.05, 0.05)
    q5 = loop_field_isolation(run_dir, arms)
    gates = {
        "Q1_completion_mass": {"pass": q1, "arms": q1_details},
        "Q2_energy": {"pass": q2, "arms": q2_details},
        "Q3_time_step": q3,
        "Q4_resolution": q4,
        "Q5_loop_isolation": q5,
    }
    quality = all(gate["pass"] for gate in gates.values())

    a = arms["A"]["summary"]
    b = arms["B"]["summary"]
    c = arms["C"]["summary"]
    d = arms["D"]["summary"]
    exchange_conditions = {
        "full_exchange": a["exchange_amplitude"] >= 0.02,
        "decoupled_quiet": b["exchange_amplitude"] <= 0.005,
        "isolated_loop_quiet": abs(d["loop_energy_delta_fraction"]) <= 0.005,
        "opposed_energy_signs": bool(
            any(value > 0.0 for value in a["energy_delta_fractions"].values())
            and any(value < 0.0 for value in a["energy_delta_fractions"].values())
        ),
    }
    exchange_emerges = all(exchange_conditions.values())
    chain_differences = {
        "energy_delta_fractions": {
            scale: abs(
                c["energy_delta_fractions"][scale]
                - a["energy_delta_fractions"][scale]
            )
            for scale in SCALES
        },
        "exchange_amplitude": abs(c["exchange_amplitude"] - a["exchange_amplitude"]),
    }
    chain_supports = bool(
        max(chain_differences["energy_delta_fractions"].values()) <= 0.03
        and chain_differences["exchange_amplitude"] <= 0.03
    )
    chain_label = (
        "SUPPORTS NEAREST-NEIGHBOR SCALE CHAIN"
        if exchange_emerges and chain_supports
        else "CONTRADICTS NEAREST-NEIGHBOR SUFFICIENCY"
        if exchange_emerges
        else "NOT EVALUATED—NO CONNECTED REDISTRIBUTION"
    )

    delta_h = a["loop_helical_retention"] - b["loop_helical_retention"]
    delta_r = a["loop_radius_retention"] - b["loop_radius_retention"]
    if delta_h >= 0.10 and delta_r >= 0.10:
        loop_label = "SUPPORTS LOOP SURVIVAL"
    elif delta_h <= -0.10 and delta_r <= -0.10:
        loop_label = "CONTRADICTS LOOP SURVIVAL SUPPORT"
    elif (
        abs(delta_h) < 0.05
        and abs(delta_r) < 0.05
        and a["loop_winding_survives"] == b["loop_winding_survives"]
    ):
        loop_label = "NO MATERIAL LOOP EFFECT"
    else:
        loop_label = "INCONCLUSIVE—MIXED LOOP RESPONSE"

    if not quality:
        verdict = "INCONCLUSIVE—NUMERICAL QUALITY"
    elif exchange_emerges:
        verdict = "EMERGES—CONNECTED SCALE-ENERGY REDISTRIBUTION"
    else:
        verdict = "DOES NOT EMERGE—CONNECTED SCALE-ENERGY REDISTRIBUTION"
    physics = {
        "exchange_conditions": exchange_conditions,
        "chain_differences": chain_differences,
        "loop_response": {
            "delta_helical_retention": delta_h,
            "delta_radius_retention": delta_r,
        },
    }
    return gates, verdict, chain_label, loop_label, physics


def preflight(device: torch.device) -> tuple[dict[str, Any], float, dict[str, bool]]:
    grid = make_grid(64, device)
    unit_fields = make_fields(grid, 1.0)
    full_matrix = COUPLINGS["full"]
    unit_potentials = effective_potentials(unit_fields, full_matrix, grid)
    unit_densities = scale_densities(unit_fields)
    k1 = sum(pair_kinetic(unit_fields[scale], grid) for scale in SCALES)
    w1 = sum(
        scalar(
            0.5
            * torch.sum(unit_densities[scale] * unit_potentials[scale])
            * grid["dv"]
        )
        for scale in SCALES
    )
    virial_mass = -2.0 * k1 / w1
    fields = make_fields(grid, virial_mass)
    potentials = effective_potentials(fields, full_matrix, grid)
    initial = capture_snapshot(fields, potentials, grid, 0.0, None)
    masses = {scale: initial["scales"][scale]["mass"] for scale in SCALES}
    total_mass = sum(masses.values())
    mass_fraction_errors = {
        scale: abs(masses[scale] / total_mass - MASS_FRACTIONS[scale]) for scale in SCALES
    }
    ratio_errors = {
        scale: abs(initial["scales"][scale]["component_ratio"] - PHI) / PHI
        for scale in SCALES
    }
    all_fields = [field for pair in fields.values() for field in pair]
    finite = all(bool(torch.isfinite(field).all().item()) for field in all_fields)
    dtype_ok = all(field.dtype == torch.complex128 for field in all_fields)
    virial_residual = abs(initial["virial"]) / max(
        abs(2.0 * initial["total_kinetic"]) + abs(initial["total_potential"]),
        1e-30,
    )
    gates = {
        "G1_finite_ordered_profiles": bool(
            finite
            and dtype_ok
            and initial["scales"]["core"]["mean_radius"] < 2.0
            and 3.5 <= initial["loop"]["r_fit"] <= 4.5
            and 5.5 <= initial["scales"]["envelope"]["mean_radius"] <= 6.5
        ),
        "G2_mass_construction": bool(
            max(mass_fraction_errors.values()) <= 1e-12
            and max(ratio_errors.values()) <= 1e-12
        ),
        "G3_loop_identity": bool(
            initial["loop"]["helix_order"] >= 0.80
            and abs(initial["loop"]["winding_y"] - 2.0) <= 0.05
            and abs(initial["loop"]["winding_i"] + 3.0) <= 0.05
        ),
        "G4_virial_calibration": bool(
            w1 < 0.0
            and math.isfinite(virial_mass)
            and 0.1 <= virial_mass <= 1e6
            and virial_residual <= 1e-10
        ),
    }
    record = {
        "k1": k1,
        "w1": w1,
        "virial_mass": virial_mass,
        "virial_residual": virial_residual,
        "mass_fraction_errors": mass_fraction_errors,
        "component_ratio_errors": ratio_errors,
        "initial": initial,
    }
    return record, virial_mass, gates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="fresh receipt directory")
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    args = parser.parse_args()

    if args.device == "cuda" or (args.device == "auto" and torch.cuda.is_available()):
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("requested CUDA/ROCm device is unavailable")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output or ROOT / "runs" / f"{stamp}_toroidal_connected_hierarchy"
    run_dir.mkdir(parents=True, exist_ok=False)

    source_names = (
        "toroidal-connected-hierarchy-pre-registration.md",
        "toroidal_connected_hierarchy_probe.py",
        "verify_toroidal_connected_hierarchy.py",
        *(f"toroidal_coherence_survival_v{version}_probe.py" for version in (2, 3, 4, 5)),
    )
    sources = {
        f"field-experience/{name}": sha256_file(ROOT / "field-experience" / name)
        for name in source_names
    }

    preflight_record, virial_mass, initialization_gates = preflight(device)
    if not all(initialization_gates.values()):
        result = {
            "probe": "toroidal_connected_hierarchy",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "device": str(device),
            "dtype": "complex128/float64",
            "integrator": "yoshida_triple_jump_s4",
            "constants": {
                "box_size": BOX_SIZE,
                "t_end": T_END,
                "report_cadence": REPORT_CADENCE,
                "core_sigma": CORE_SIGMA,
                "envelope_radius": ENVELOPE_RADIUS,
                "envelope_sigma": ENVELOPE_SIGMA,
                "mass_fractions": MASS_FRACTIONS,
            },
            "couplings": COUPLINGS,
            "arms_spec": ARMS,
            "sources": sources,
            "preflight": preflight_record,
            "initialization_gates": initialization_gates,
            "verdict": "INCONCLUSIVE—INVALID INITIALIZATION",
        }
        with (run_dir / "results.json").open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(json.dumps({"run_dir": str(run_dir), "verdict": result["verdict"], "gates": initialization_gates}, indent=2))
        return

    arm_results: dict[str, Any] = {}
    for arm in ARMS:
        print(f"running arm {arm['id']} ({arm['name']})", flush=True)
        arm_results[arm["id"]] = evolve_arm(arm, virial_mass, device, run_dir)
        if device.type == "cuda":
            torch.cuda.empty_cache()

    gates, verdict, chain_label, loop_label, physics = evaluate(arm_results, run_dir)
    result = {
        "probe": "toroidal_connected_hierarchy",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "device": str(device),
        "device_name": torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU",
        "torch_version": torch.__version__,
        "dtype": "complex128/float64",
        "integrator": "yoshida_triple_jump_s4",
        "constants": {
            "box_size": BOX_SIZE,
            "t_end": T_END,
            "report_cadence": REPORT_CADENCE,
            "core_sigma": CORE_SIGMA,
            "envelope_radius": ENVELOPE_RADIUS,
            "envelope_sigma": ENVELOPE_SIGMA,
            "mass_fractions": MASS_FRACTIONS,
        },
        "couplings": COUPLINGS,
        "arms_spec": ARMS,
        "sources": sources,
        "preflight": preflight_record,
        "initialization_gates": initialization_gates,
        "arms": arm_results,
        "gates": gates,
        "physics": physics,
        "verdict": verdict,
        "chain_label": chain_label,
        "loop_response_label": loop_label,
    }
    results_path = run_dir / "results.json"
    with results_path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "verdict": verdict,
                "chain_label": chain_label,
                "loop_response_label": loop_label,
                "initialization_gates": initialization_gates,
                "gates": gates,
                "summaries": {
                    arm_id: arm["summary"] for arm_id, arm in arm_results.items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
