#!/usr/bin/env python3
"""Independently re-evolve and verify a connected hierarchy receipt."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch

_V5_PATH = Path(__file__).with_name("toroidal_coherence_survival_v5_probe.py")
_V5_SPEC = importlib.util.spec_from_file_location("verify_hierarchy_v5_base", _V5_PATH)
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
ATOL = 1e-9
RTOL = 1e-7


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scalar(value: torch.Tensor | float) -> float:
    return float(value.detach().cpu().item() if isinstance(value, torch.Tensor) else value)


def compare_tree(
    stored: Any,
    recomputed: Any,
    path: str,
    errors: list[str],
    maximum: list[float],
) -> None:
    if isinstance(stored, dict) and isinstance(recomputed, dict):
        if set(stored) != set(recomputed):
            errors.append(f"{path}: key mismatch")
            return
        for key in sorted(stored):
            compare_tree(stored[key], recomputed[key], f"{path}.{key}", errors, maximum)
        return
    if isinstance(stored, list) and isinstance(recomputed, (list, tuple)):
        if len(stored) != len(recomputed):
            errors.append(f"{path}: length mismatch")
            return
        for index, (left, right) in enumerate(zip(stored, recomputed)):
            compare_tree(left, right, f"{path}[{index}]", errors, maximum)
        return
    if isinstance(stored, bool) or isinstance(recomputed, bool) or stored is None or recomputed is None:
        if stored != recomputed:
            errors.append(f"{path}: {stored!r} != {recomputed!r}")
        return
    if isinstance(stored, (int, float)) and isinstance(recomputed, (int, float)):
        difference = abs(float(stored) - float(recomputed))
        tolerance = ATOL + RTOL * max(abs(float(stored)), abs(float(recomputed)))
        normalized = difference / tolerance
        maximum[0] = max(maximum[0], normalized)
        if not math.isfinite(normalized) or normalized > 1.0:
            errors.append(f"{path}: normalized difference {normalized:.6g}")
        return
    if stored != recomputed:
        errors.append(f"{path}: {stored!r} != {recomputed!r}")


def make_grid(n: int, device: torch.device) -> dict[str, Any]:
    grid = v5.v4.make_grid(n, device)
    grid["radius"] = torch.sqrt(grid["x"] ** 2 + grid["y"] ** 2 + grid["z"] ** 2)
    fundamental = 2.0 * math.pi / BOX_SIZE
    grid["fine_mask"] = grid["k2"] >= (8.0 * fundamental) ** 2
    return grid


def normalize_pair(
    amplitude: torch.Tensor,
    grid: dict[str, Any],
    total_mass: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    phase = torch.zeros_like(amplitude)
    return v5.v4.normalize_components(amplitude, amplitude.clone(), phase, phase, grid, total_mass)


def initial_fields(
    grid: dict[str, Any],
    total_mass: float,
) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    radius = grid["radius"]
    core = torch.exp(-(radius**2) / (4.0 * CORE_SIGMA**2))
    envelope = torch.exp(
        -((radius - ENVELOPE_RADIUS) ** 2) / (4.0 * ENVELOPE_SIGMA**2)
    )
    return {
        "core": normalize_pair(core, grid, 0.25 * total_mass),
        "loop": v5.v4.v3.base.make_seed("closed", grid, 0.50 * total_mass),
        "envelope": normalize_pair(envelope, grid, 0.25 * total_mass),
    }


def densities(
    fields: dict[str, tuple[torch.Tensor, torch.Tensor]],
) -> dict[str, torch.Tensor]:
    return {
        scale: torch.abs(pair[0]) ** 2 + torch.abs(pair[1]) ** 2
        for scale, pair in fields.items()
    }


def poisson(density: torch.Tensor, grid: dict[str, Any]) -> torch.Tensor:
    transformed = torch.fft.fftn(density - torch.mean(density))
    potential = torch.zeros_like(transformed)
    mask = grid["k2"] > 0.0
    potential[mask] = -transformed[mask] / grid["k2"][mask]
    return torch.fft.ifftn(potential).real


def graph_potentials(
    fields: dict[str, tuple[torch.Tensor, torch.Tensor]],
    matrix: tuple[tuple[float, ...], ...],
    grid: dict[str, Any],
) -> dict[str, torch.Tensor]:
    rho = densities(fields)
    unique: dict[tuple[float, ...], torch.Tensor] = {}
    output: dict[str, torch.Tensor] = {}
    for scale, row in zip(SCALES, matrix):
        if row not in unique:
            source = torch.zeros_like(rho["core"])
            for coefficient, source_scale in zip(row, SCALES):
                if coefficient:
                    source = source + coefficient * rho[source_scale]
            unique[row] = poisson(source, grid)
        output[scale] = unique[row]
    return output


def kinetic(pair: tuple[torch.Tensor, torch.Tensor], grid: dict[str, Any]) -> float:
    value = torch.zeros((), device=pair[0].device, dtype=torch.float64)
    for field in pair:
        laplacian = torch.fft.ifftn(-grid["k2"] * torch.fft.fftn(field))
        value = value - 0.5 * torch.sum(torch.real(torch.conj(field) * laplacian)) * grid["dv"]
    return scalar(value)


def scale_metrics(
    pair: tuple[torch.Tensor, torch.Tensor],
    potential: torch.Tensor,
    grid: dict[str, Any],
) -> dict[str, float]:
    rho_y = torch.abs(pair[0]) ** 2
    rho_i = torch.abs(pair[1]) ** 2
    rho = rho_y + rho_i
    mass_y = scalar(torch.sum(rho_y) * grid["dv"])
    mass_i = scalar(torch.sum(rho_i) * grid["dv"])
    mass = mass_y + mass_i
    kinetic_value = kinetic(pair, grid)
    potential_value = scalar(0.5 * torch.sum(rho * potential) * grid["dv"])
    mean_radius = scalar(torch.sum(rho * grid["radius"]) * grid["dv"] / mass)
    second_radius = scalar(torch.sum(rho * grid["radius"] ** 2) * grid["dv"] / mass)
    transformed_y = torch.fft.fftn(pair[0])
    transformed_i = torch.fft.fftn(pair[1])
    modal = torch.real(
        transformed_y * torch.conj(transformed_y)
        + transformed_i * torch.conj(transformed_i)
    )
    return {
        "mass": mass,
        "mass_y": mass_y,
        "mass_i": mass_i,
        "component_ratio": mass_y / mass_i,
        "kinetic": kinetic_value,
        "potential": potential_value,
        "energy": kinetic_value + potential_value,
        "mean_radius": mean_radius,
        "rms_radius": math.sqrt(max(second_radius, 0.0)),
        "radial_width": math.sqrt(max(second_radius - mean_radius**2, 0.0)),
        "max_density": scalar(torch.max(rho)),
        "fine_mass_fraction": scalar(
            torch.sum(modal[grid["fine_mask"]]) / torch.sum(modal)
        ),
    }


def snapshot(
    fields: dict[str, tuple[torch.Tensor, torch.Tensor]],
    potentials: dict[str, torch.Tensor],
    grid: dict[str, Any],
    time_value: float,
    initial_center: list[float] | None,
) -> dict[str, Any]:
    per_scale = {
        scale: scale_metrics(fields[scale], potentials[scale], grid) for scale in SCALES
    }
    loop = v5.diagnose(
        fields["loop"][0],
        fields["loop"][1],
        grid,
        1.0,
        time_value,
        potentials["loop"],
        initial_center,
    )
    rho = densities(fields)
    self_potential = sum(
        scalar(0.5 * torch.sum(rho[scale] * poisson(rho[scale], grid)) * grid["dv"])
        for scale in SCALES
    )
    total_kinetic = sum(per_scale[scale]["kinetic"] for scale in SCALES)
    total_potential = sum(per_scale[scale]["potential"] for scale in SCALES)
    return {
        "time": time_value,
        "scales": per_scale,
        "loop": loop,
        "total_mass": sum(per_scale[scale]["mass"] for scale in SCALES),
        "total_kinetic": total_kinetic,
        "total_potential": total_potential,
        "total_energy": total_kinetic + total_potential,
        "interaction_energy": total_potential - self_potential,
        "virial": 2.0 * total_kinetic + total_potential,
    }


def summarize(series: list[dict[str, Any]]) -> dict[str, Any]:
    initial = series[0]
    final = series[-1]
    denominator = max(abs(initial["total_energy"]), 1e-30)
    deltas = {
        scale: (final["scales"][scale]["energy"] - initial["scales"][scale]["energy"])
        / denominator
        for scale in SCALES
    }
    mass_drifts = {
        scale: max(
            abs(row["scales"][scale]["mass"] - initial["scales"][scale]["mass"])
            / initial["scales"][scale]["mass"]
            for row in series
        )
        for scale in SCALES
    }
    scale_energy_drifts = {
        scale: max(
            abs(row["scales"][scale]["energy"] - initial["scales"][scale]["energy"])
            / denominator
            for row in series
        )
        for scale in SCALES
    }
    return {
        "final_time": final["time"],
        "mass_drifts": mass_drifts,
        "max_mass_drift": max(mass_drifts.values()),
        "total_energy_drift": max(
            abs(row["total_energy"] - initial["total_energy"]) / denominator for row in series
        ),
        "scale_energy_drifts": scale_energy_drifts,
        "energy_delta_fractions": deltas,
        "exchange_amplitude": 0.5 * sum(abs(value) for value in deltas.values()),
        "loop_energy_delta_fraction": deltas["loop"],
        "loop_helical_retention": final["loop"]["helix_order"] / initial["loop"]["helix_order"],
        "loop_radius_retention": final["loop"]["r_fit"] / initial["loop"]["r_fit"],
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


def apply_kick(
    fields: dict[str, tuple[torch.Tensor, torch.Tensor]],
    potentials: dict[str, torch.Tensor],
    matrix: tuple[tuple[float, ...], ...],
    interval: float,
) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    phases: dict[tuple[float, ...], torch.Tensor] = {}
    output: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
    for scale, row in zip(SCALES, matrix):
        if row not in phases:
            phases[row] = torch.exp(-1j * interval * potentials[scale])
        phase = phases[row]
        output[scale] = (fields[scale][0] * phase, fields[scale][1] * phase)
    return output


def apply_drift(
    fields: dict[str, tuple[torch.Tensor, torch.Tensor]],
    phase: torch.Tensor,
) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    output: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
    for scale in SCALES:
        output[scale] = tuple(
            torch.fft.ifftn(torch.fft.fftn(field) * phase) for field in fields[scale]
        )
    return output


def re_evolve(
    arm: dict[str, Any],
    total_mass: float,
    device: torch.device,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    grid = make_grid(arm["n"], device)
    fields = initial_fields(grid, total_mass)
    matrix = COUPLINGS[arm["graph"]]
    dt = float(arm["dt"])
    steps = round(T_END / dt)
    report_steps = round(REPORT_CADENCE / dt)
    cube_root_two = 2.0 ** (1.0 / 3.0)
    coefficients = (
        1.0 / (2.0 - cube_root_two),
        -cube_root_two / (2.0 - cube_root_two),
        1.0 / (2.0 - cube_root_two),
    )
    drift_phases = tuple(
        torch.exp(-0.5j * grid["k2"] * coefficient * dt) for coefficient in coefficients
    )
    potentials = graph_potentials(fields, matrix, grid)
    initial_rho = densities(fields)
    initial_total = sum(
        (initial_rho[scale] for scale in SCALES), torch.zeros_like(initial_rho["core"])
    )
    ceiling_reference = scalar(torch.max(initial_total))
    series: list[dict[str, Any]] = []
    initial_center: list[float] | None = None
    status = "complete"
    stop_reason: str | None = None

    def record(step: int) -> None:
        nonlocal initial_center
        row = snapshot(fields, potentials, grid, step * dt, initial_center)
        if initial_center is None:
            initial_center = row["loop"]["center"]
            row["loop"]["center_displacement"] = 0.0
        series.append(row)

    record(0)
    last_step = 0
    for step in range(1, steps + 1):
        for coefficient, phase in zip(coefficients, drift_phases):
            fields = apply_kick(fields, potentials, matrix, 0.5 * coefficient * dt)
            fields = apply_drift(fields, phase)
            potentials = graph_potentials(fields, matrix, grid)
            fields = apply_kick(fields, potentials, matrix, 0.5 * coefficient * dt)
        last_step = step
        rho = densities(fields)
        total = sum((rho[scale] for scale in SCALES), torch.zeros_like(rho["core"]))
        if not bool(torch.isfinite(total).all().item()):
            status, stop_reason = "stopped", "nonfinite field"
            break
        if scalar(torch.max(total)) > 1.0e8 * ceiling_reference:
            status, stop_reason = "stopped", "density ceiling"
            break
        if step % report_steps == 0:
            record(step)
    if series[-1]["time"] != last_step * dt:
        record(last_step)

    arrays = {
        f"{scale}_{component}": fields[scale][index].detach().cpu().numpy().copy()
        for scale in SCALES
        for index, component in enumerate(("y", "i"))
    }
    finite = all(np.isfinite(array).all() for array in arrays.values())
    dtype_ok = all(array.dtype == np.complex128 for array in arrays.values())
    result = {
        "status": status,
        "stop_reason": stop_reason,
        "finite": finite,
        "dtype_ok": dtype_ok,
        "metrics": series,
        "summary": summarize(series),
    }
    return result, arrays


def recompute_preflight(device: torch.device) -> tuple[dict[str, Any], float, dict[str, bool]]:
    grid = make_grid(64, device)
    unit = initial_fields(grid, 1.0)
    potentials = graph_potentials(unit, COUPLINGS["full"], grid)
    unit_rho = densities(unit)
    k1 = sum(kinetic(unit[scale], grid) for scale in SCALES)
    w1 = sum(
        scalar(0.5 * torch.sum(unit_rho[scale] * potentials[scale]) * grid["dv"])
        for scale in SCALES
    )
    total_mass = -2.0 * k1 / w1
    fields = initial_fields(grid, total_mass)
    potentials = graph_potentials(fields, COUPLINGS["full"], grid)
    initial = snapshot(fields, potentials, grid, 0.0, None)
    masses = {scale: initial["scales"][scale]["mass"] for scale in SCALES}
    summed_mass = sum(masses.values())
    mass_errors = {
        scale: abs(masses[scale] / summed_mass - MASS_FRACTIONS[scale]) for scale in SCALES
    }
    ratio_errors = {
        scale: abs(initial["scales"][scale]["component_ratio"] - PHI) / PHI
        for scale in SCALES
    }
    all_fields = [field for pair in fields.values() for field in pair]
    residual = abs(initial["virial"]) / max(
        abs(2.0 * initial["total_kinetic"]) + abs(initial["total_potential"]), 1e-30
    )
    gates = {
        "G1_finite_ordered_profiles": bool(
            all(bool(torch.isfinite(field).all().item()) for field in all_fields)
            and all(field.dtype == torch.complex128 for field in all_fields)
            and initial["scales"]["core"]["mean_radius"] < 2.0
            and 3.5 <= initial["loop"]["r_fit"] <= 4.5
            and 5.5 <= initial["scales"]["envelope"]["mean_radius"] <= 6.5
        ),
        "G2_mass_construction": bool(
            max(mass_errors.values()) <= 1e-12 and max(ratio_errors.values()) <= 1e-12
        ),
        "G3_loop_identity": bool(
            initial["loop"]["helix_order"] >= 0.80
            and abs(initial["loop"]["winding_y"] - 2.0) <= 0.05
            and abs(initial["loop"]["winding_i"] + 3.0) <= 0.05
        ),
        "G4_virial_calibration": bool(
            w1 < 0.0 and math.isfinite(total_mass) and 0.1 <= total_mass <= 1e6 and residual <= 1e-10
        ),
    }
    return {
        "k1": k1,
        "w1": w1,
        "virial_mass": total_mass,
        "virial_residual": residual,
        "mass_fraction_errors": mass_errors,
        "component_ratio_errors": ratio_errors,
        "initial": initial,
    }, total_mass, gates


def compare_summaries(
    first: dict[str, Any],
    second: dict[str, Any],
    helix_limit: float,
    radius_limit: float,
    energy_limit: float,
    exchange_limit: float,
) -> dict[str, Any]:
    differences = {
        "loop_helical_retention": abs(first["loop_helical_retention"] - second["loop_helical_retention"]),
        "loop_radius_retention": abs(first["loop_radius_retention"] - second["loop_radius_retention"]),
        "exchange_amplitude": abs(first["exchange_amplitude"] - second["exchange_amplitude"]),
        "energy_delta_fractions": {
            scale: abs(first["energy_delta_fractions"][scale] - second["energy_delta_fractions"][scale])
            for scale in SCALES
        },
    }
    directions = bool(
        math.copysign(1.0, first["loop_final_winding_y"])
        == math.copysign(1.0, second["loop_final_winding_y"])
        and math.copysign(1.0, first["loop_final_winding_i"])
        == math.copysign(1.0, second["loop_final_winding_i"])
    )
    return {
        "pass": bool(
            differences["loop_helical_retention"] <= helix_limit
            and differences["loop_radius_retention"] <= radius_limit
            and differences["exchange_amplitude"] <= exchange_limit
            and all(value <= energy_limit for value in differences["energy_delta_fractions"].values())
            and directions
        ),
        "differences": differences,
        "winding_directions_agree": directions,
    }


def evaluate_recomputed(
    arms: dict[str, dict[str, Any]],
    final_fields: dict[str, dict[str, np.ndarray]],
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
        row["complete"] and row["finite"] and row["dtype_ok"] and row["max_mass_drift"] <= 2e-9
        for row in q1_details.values()
    )
    q2_details = {
        arm_id: {
            "total_energy_drift": arm["summary"]["total_energy_drift"],
            "scale_energy_drifts": arm["summary"]["scale_energy_drifts"],
        }
        for arm_id, arm in arms.items()
    }
    q2 = all(row["total_energy_drift"] <= 5e-3 for row in q2_details.values()) and all(
        value <= 5e-3 for value in q2_details["B"]["scale_energy_drifts"].values()
    )
    q3 = compare_summaries(arms["A"]["summary"], arms["F"]["summary"], 0.08, 0.05, 0.03, 0.03)
    q4 = compare_summaries(arms["A"]["summary"], arms["E"]["summary"], 0.10, 0.08, 0.05, 0.05)
    field_errors = {}
    for key in ("loop_y", "loop_i"):
        denominator = max(float(np.max(np.abs(final_fields["B"][key]))), 1e-30)
        field_errors[key] = float(
            np.max(np.abs(final_fields["B"][key] - final_fields["D"][key])) / denominator
        )
    b_summary = arms["B"]["summary"]
    d_summary = arms["D"]["summary"]
    metric_errors = {
        "loop_helical_retention": abs(b_summary["loop_helical_retention"] - d_summary["loop_helical_retention"]),
        "loop_radius_retention": abs(b_summary["loop_radius_retention"] - d_summary["loop_radius_retention"]),
        "loop_energy_delta_fraction": abs(
            b_summary["loop_energy_delta_fraction"] - d_summary["loop_energy_delta_fraction"]
        ),
    }
    q5 = {
        "pass": bool(max(field_errors.values()) <= 1e-10 and max(metric_errors.values()) <= 1e-10),
        "field_relative_inf_errors": field_errors,
        "metric_errors": metric_errors,
    }
    gates = {
        "Q1_completion_mass": {"pass": q1, "arms": q1_details},
        "Q2_energy": {"pass": q2, "arms": q2_details},
        "Q3_time_step": q3,
        "Q4_resolution": q4,
        "Q5_loop_isolation": q5,
    }
    a = arms["A"]["summary"]
    b = arms["B"]["summary"]
    c = arms["C"]["summary"]
    d = arms["D"]["summary"]
    conditions = {
        "full_exchange": a["exchange_amplitude"] >= 0.02,
        "decoupled_quiet": b["exchange_amplitude"] <= 0.005,
        "isolated_loop_quiet": abs(d["loop_energy_delta_fraction"]) <= 0.005,
        "opposed_energy_signs": bool(
            any(value > 0.0 for value in a["energy_delta_fractions"].values())
            and any(value < 0.0 for value in a["energy_delta_fractions"].values())
        ),
    }
    emerges = all(conditions.values())
    chain_differences = {
        "energy_delta_fractions": {
            scale: abs(c["energy_delta_fractions"][scale] - a["energy_delta_fractions"][scale])
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
        if emerges and chain_supports
        else "CONTRADICTS NEAREST-NEIGHBOR SUFFICIENCY"
        if emerges
        else "NOT EVALUATED—NO CONNECTED REDISTRIBUTION"
    )
    delta_h = a["loop_helical_retention"] - b["loop_helical_retention"]
    delta_r = a["loop_radius_retention"] - b["loop_radius_retention"]
    if delta_h >= 0.10 and delta_r >= 0.10:
        loop_label = "SUPPORTS LOOP SURVIVAL"
    elif delta_h <= -0.10 and delta_r <= -0.10:
        loop_label = "CONTRADICTS LOOP SURVIVAL SUPPORT"
    elif abs(delta_h) < 0.05 and abs(delta_r) < 0.05 and a["loop_winding_survives"] == b["loop_winding_survives"]:
        loop_label = "NO MATERIAL LOOP EFFECT"
    else:
        loop_label = "INCONCLUSIVE—MIXED LOOP RESPONSE"
    quality = all(gate["pass"] for gate in gates.values())
    verdict = (
        "INCONCLUSIVE—NUMERICAL QUALITY"
        if not quality
        else "EMERGES—CONNECTED SCALE-ENERGY REDISTRIBUTION"
        if emerges
        else "DOES NOT EMERGE—CONNECTED SCALE-ENERGY REDISTRIBUTION"
    )
    physics = {
        "exchange_conditions": conditions,
        "chain_differences": chain_differences,
        "loop_response": {
            "delta_helical_retention": delta_h,
            "delta_radius_retention": delta_r,
        },
    }
    return gates, verdict, chain_label, loop_label, physics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    args = parser.parse_args()
    results_path = args.results.resolve()
    run_dir = results_path.parent
    output_path = run_dir / "verification.json"
    with results_path.open("r", encoding="utf-8") as handle:
        stored = json.load(handle)

    if args.device == "cuda" or (args.device == "auto" and torch.cuda.is_available()):
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("requested CUDA/ROCm device is unavailable")

    errors: list[str] = []
    metric_maximum = [0.0]
    field_maximum = 0.0
    if stored.get("probe") != "toroidal_connected_hierarchy":
        errors.append("probe identifier mismatch")
    expected_constants = {
        "box_size": BOX_SIZE,
        "t_end": T_END,
        "report_cadence": REPORT_CADENCE,
        "core_sigma": CORE_SIGMA,
        "envelope_radius": ENVELOPE_RADIUS,
        "envelope_sigma": ENVELOPE_SIGMA,
        "mass_fractions": MASS_FRACTIONS,
    }
    if stored.get("constants") != expected_constants:
        errors.append("constant manifest mismatch")
    if stored.get("dtype") != "complex128/float64":
        errors.append("dtype manifest mismatch")
    if stored.get("integrator") != "yoshida_triple_jump_s4":
        errors.append("integrator manifest mismatch")
    expected_sources = {
        "field-experience/toroidal-connected-hierarchy-pre-registration.md",
        "field-experience/toroidal_connected_hierarchy_probe.py",
        "field-experience/verify_toroidal_connected_hierarchy.py",
        *(f"field-experience/toroidal_coherence_survival_v{version}_probe.py" for version in (2, 3, 4, 5)),
    }
    if set(stored.get("sources", {})) != expected_sources:
        errors.append("source manifest mismatch")
    else:
        for relative, expected_hash in stored["sources"].items():
            if sha256_file(ROOT / relative) != expected_hash:
                errors.append(f"source hash mismatch: {relative}")
    if stored.get("arms_spec") != list(ARMS):
        errors.append("arm specification mismatch")
    if stored.get("couplings") != {key: [list(row) for row in value] for key, value in COUPLINGS.items()}:
        errors.append("coupling matrix mismatch")

    recomputed_preflight, total_mass, initialization_gates = recompute_preflight(device)
    compare_tree(stored["preflight"], recomputed_preflight, "preflight", errors, metric_maximum)
    compare_tree(
        stored["initialization_gates"], initialization_gates, "initialization_gates", errors, metric_maximum
    )

    recomputed_arms: dict[str, dict[str, Any]] = {}
    final_fields: dict[str, dict[str, np.ndarray]] = {}
    if all(initialization_gates.values()):
        for arm in ARMS:
            arm_id = arm["id"]
            print(f"re-evolving arm {arm_id} ({arm['name']})", flush=True)
            recomputed, arrays = re_evolve(arm, total_mass, device)
            recomputed_arms[arm_id] = recomputed
            final_fields[arm_id] = arrays
            stored_arm = stored["arms"][arm_id]
            if stored_arm.get("config") != arm:
                errors.append(f"arm {arm_id}: config mismatch")
            if stored_arm.get("coupling_matrix") != [list(row) for row in COUPLINGS[arm["graph"]]]:
                errors.append(f"arm {arm_id}: coupling mismatch")
            for key in ("status", "stop_reason", "finite", "dtype_ok"):
                if stored_arm.get(key) != recomputed[key]:
                    errors.append(f"arm {arm_id}.{key}: mismatch")
            compare_tree(stored_arm["metrics"], recomputed["metrics"], f"arms.{arm_id}.metrics", errors, metric_maximum)
            compare_tree(stored_arm["summary"], recomputed["summary"], f"arms.{arm_id}.summary", errors, metric_maximum)

            if stored_arm.get("fields_file") != f"fields_{arm_id}.npz":
                errors.append(f"arm {arm_id}: field filename mismatch")
            fields_path = run_dir / f"fields_{arm_id}.npz"
            if sha256_file(fields_path) != stored_arm["fields_sha256"]:
                errors.append(f"arm {arm_id}: final-field hash mismatch")
            with np.load(fields_path) as receipt:
                stored_time = float(receipt["time"])
                if stored_time != recomputed["summary"]["final_time"]:
                    errors.append(f"arm {arm_id}: final time mismatch")
                for key, recomputed_array in arrays.items():
                    stored_array = receipt[key]
                    if stored_array.shape != recomputed_array.shape or stored_array.dtype != np.complex128:
                        errors.append(f"arm {arm_id}.{key}: shape or dtype mismatch")
                        continue
                    normalized = np.abs(stored_array - recomputed_array) / (
                        ATOL + RTOL * np.maximum(np.abs(stored_array), np.abs(recomputed_array))
                    )
                    maximum = float(np.max(normalized))
                    field_maximum = max(field_maximum, maximum)
                    if not math.isfinite(maximum) or maximum > 1.0:
                        errors.append(f"arm {arm_id}.{key}: normalized field difference {maximum:.6g}")
            if device.type == "cuda":
                torch.cuda.empty_cache()

        gates, verdict, chain_label, loop_label, physics = evaluate_recomputed(
            recomputed_arms, final_fields
        )
        compare_tree(stored["gates"], gates, "gates", errors, metric_maximum)
        compare_tree(stored["physics"], physics, "physics", errors, metric_maximum)
        if stored.get("verdict") != verdict:
            errors.append(f"verdict mismatch: {stored.get('verdict')} != {verdict}")
        if stored.get("chain_label") != chain_label:
            errors.append("chain label mismatch")
        if stored.get("loop_response_label") != loop_label:
            errors.append("loop-response label mismatch")
    else:
        gates = {}
        verdict = "INCONCLUSIVE—INVALID INITIALIZATION"
        chain_label = "NOT EVALUATED—INVALID INITIALIZATION"
        loop_label = "NOT EVALUATED—INVALID INITIALIZATION"
        physics = {}
        if stored.get("verdict") != verdict:
            errors.append("invalid-initialization verdict mismatch")

    verification = {
        "verifier": "independent_connected_hierarchy_re_evolution_v1",
        "results_sha256": sha256_file(results_path),
        "device": str(device),
        "recomputed_initialization_gates": initialization_gates,
        "recomputed_gates": gates,
        "recomputed_physics": physics,
        "recomputed_verdict": verdict,
        "recomputed_chain_label": chain_label,
        "recomputed_loop_response_label": loop_label,
        "max_normalized_metric_error": metric_maximum[0],
        "max_normalized_field_error": field_maximum,
        "errors": errors,
        "pass": not errors,
    }
    with output_path.open("x", encoding="utf-8") as handle:
        json.dump(verification, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(verification, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
