#!/usr/bin/env python3
"""Run the preregistered toroidal coherence survival probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

PHI = (1.0 + math.sqrt(5.0)) / 2.0
CONSTANTS: dict[str, Any] = {
    "box_size": 16.0,
    "reference_n": 48,
    "low_n": 32,
    "high_n": 64,
    "dt": 0.005,
    "dt_half": 0.0025,
    "t_end": 4.0,
    "report_cadence": 0.25,
    "major_radius": 4.0,
    "strand_offset": 1.2,
    "sigma": 0.60,
    "spatial_winding": 1,
    "yang_winding": 2,
    "yin_winding": -3,
    "component_ratio": PHI,
    "random_seed": 20260831,
    "winding_sectors": 64,
}
ARMS = [
    {"id": "A", "name": "closed_primary", "seed": "closed", "n": 48, "dt": 0.005, "g": 1.0},
    {"id": "B", "name": "closed_free", "seed": "closed", "n": 48, "dt": 0.005, "g": 0.0},
    {"id": "C", "name": "untwisted", "seed": "untwisted", "n": 48, "dt": 0.005, "g": 1.0},
    {"id": "D", "name": "open", "seed": "open", "n": 48, "dt": 0.005, "g": 1.0},
    {"id": "E", "name": "scrambled", "seed": "scrambled", "n": 48, "dt": 0.005, "g": 1.0},
    {"id": "F", "name": "sphere", "seed": "sphere", "n": 48, "dt": 0.005, "g": 1.0},
    {"id": "G", "name": "perturbed", "seed": "perturbed", "n": 48, "dt": 0.005, "g": 1.0},
    {"id": "H", "name": "closed_n32", "seed": "closed", "n": 32, "dt": 0.005, "g": 1.0},
    {"id": "I", "name": "closed_n64", "seed": "closed", "n": 64, "dt": 0.005, "g": 1.0},
    {"id": "J", "name": "closed_dt_half", "seed": "closed", "n": 48, "dt": 0.0025, "g": 1.0},
]
ROOT = Path(__file__).resolve().parents[1]
BASE_PREREG = ROOT / "field-experience" / "toroidal-coherence-survival-pre-registration.md"
V2_PREREG = ROOT / "field-experience" / "toroidal-coherence-survival-v2-pre-registration.md"
VERIFIER = ROOT / "field-experience" / "verify_toroidal_coherence_survival_v2.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scalar(value: torch.Tensor | float) -> float:
    return float(value.detach().cpu().item() if isinstance(value, torch.Tensor) else value)


def make_grid(n: int, device: torch.device) -> dict[str, Any]:
    box = CONSTANTS["box_size"]
    dx = box / n
    axis = (torch.arange(n, device=device, dtype=torch.float32) - n / 2) * dx
    x, y, z = torch.meshgrid(axis, axis, axis, indexing="ij")
    r_perp = torch.sqrt(x * x + y * y)
    chi = torch.atan2(y, x)
    k_axis = 2.0 * math.pi * torch.fft.fftfreq(n, d=dx, device=device)
    kx, ky, kz = torch.meshgrid(k_axis, k_axis, k_axis, indexing="ij")
    k2 = kx * kx + ky * ky + kz * kz
    sector = torch.floor((chi + math.pi) * CONSTANTS["winding_sectors"] / (2.0 * math.pi)).to(torch.int64)
    sector.clamp_(0, CONSTANTS["winding_sectors"] - 1)
    return {
        "n": n,
        "dx": dx,
        "dv": dx**3,
        "x": x,
        "y": y,
        "z": z,
        "r_perp": r_perp,
        "chi": chi,
        "k2": k2,
        "kx": kx,
        "ky": ky,
        "kz": kz,
        "sector": sector.reshape(-1),
    }


def normalize_components(
    amp_y: torch.Tensor,
    amp_i: torch.Tensor,
    phase_y: torch.Tensor,
    phase_i: torch.Tensor,
    grid: dict[str, Any],
    total_mass: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    ratio = CONSTANTS["component_ratio"]
    target_y = total_mass * ratio / (1.0 + ratio)
    target_i = total_mass / (1.0 + ratio)
    norm_y = torch.sum(amp_y * amp_y) * grid["dv"]
    norm_i = torch.sum(amp_i * amp_i) * grid["dv"]
    amp_y = amp_y * torch.sqrt(torch.tensor(target_y, device=amp_y.device) / norm_y)
    amp_i = amp_i * torch.sqrt(torch.tensor(target_i, device=amp_i.device) / norm_i)
    psi_y = torch.polar(amp_y, phase_y).to(torch.complex64)
    psi_i = torch.polar(amp_i, phase_i).to(torch.complex64)
    return psi_y, psi_i


def filtered_noise(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((n, n, n))
    dx = CONSTANTS["box_size"] / n
    k = 2.0 * math.pi * np.fft.fftfreq(n, d=dx)
    kx, ky, kz = np.meshgrid(k, k, k, indexing="ij")
    kmag = np.sqrt(kx * kx + ky * ky + kz * kz)
    cutoff = math.pi / CONSTANTS["sigma"]
    smooth = np.fft.ifftn(np.fft.fftn(noise) * np.exp(-((kmag / cutoff) ** 4))).real
    return smooth.astype(np.float32)


def weighted_phase_gradient_energy(phase: torch.Tensor, density: torch.Tensor, grid: dict[str, Any]) -> torch.Tensor:
    phase_hat = torch.fft.fftn(phase)
    gradient_sq = torch.zeros_like(phase)
    for wave in (grid["kx"], grid["ky"], grid["kz"]):
        derivative = torch.fft.ifftn(1j * wave * phase_hat).real
        gradient_sq += derivative * derivative
    return 0.5 * torch.sum(density * gradient_sq) * grid["dv"]


def random_phase(
    density: torch.Tensor,
    grid: dict[str, Any],
    seed: int,
    *,
    target_gradient_energy: float | None = None,
    target_rms: float | None = None,
) -> torch.Tensor:
    phase = torch.from_numpy(filtered_noise(grid["n"], seed)).to(density.device)
    mass = torch.sum(density) * grid["dv"]
    phase -= torch.sum(density * phase) * grid["dv"] / mass
    if target_gradient_energy is not None:
        energy = weighted_phase_gradient_energy(phase, density, grid)
        phase *= math.sqrt(target_gradient_energy / max(scalar(energy), 1e-30))
    elif target_rms is not None:
        rms = torch.sqrt(torch.sum(density * phase * phase) * grid["dv"] / mass)
        phase *= target_rms / max(scalar(rms), 1e-30)
    else:
        raise ValueError("random phase requires a frozen scaling target")
    return phase


def make_seed(kind: str, grid: dict[str, Any], total_mass: float) -> tuple[torch.Tensor, torch.Tensor]:
    r_perp = grid["r_perp"]
    chi = grid["chi"]
    z = grid["z"]
    r0 = CONSTANTS["major_radius"]
    offset = CONSTANTS["strand_offset"]
    sigma = CONSTANTS["sigma"]
    shape_m = 0 if kind == "untwisted" else CONSTANTS["spatial_winding"]
    ellipticity = 0.05 if kind == "perturbed" else 0.0
    r_e = r0 * (1.0 + ellipticity * torch.cos(2.0 * chi))
    poloidal = shape_m * chi
    d_y2 = (r_perp - r_e - offset * torch.cos(poloidal)) ** 2 + (z - offset * torch.sin(poloidal)) ** 2
    d_i2 = (r_perp - r_e + offset * torch.cos(poloidal)) ** 2 + (z + offset * torch.sin(poloidal)) ** 2

    if kind == "sphere":
        sphere_sigma = r0 / 2.0
        radius2 = grid["x"] ** 2 + grid["y"] ** 2 + z**2
        amp_y = torch.exp(-radius2 / (4.0 * sphere_sigma**2))
        amp_i = amp_y.clone()
    else:
        amp_y = torch.exp(-d_y2 / (4.0 * sigma**2))
        amp_i = torch.exp(-d_i2 / (4.0 * sigma**2))

    if kind == "open":
        delta = torch.atan2(torch.sin(chi - math.pi), torch.cos(chi - math.pi))
        gap = math.pi / 2.0
        edge = 0.10
        window = 0.5 * (1.0 + torch.tanh((torch.abs(delta) - gap / 2.0) / edge))
        amp_y *= window
        amp_i *= window

    coherent_y = CONSTANTS["yang_winding"] * chi
    coherent_i = CONSTANTS["yin_winding"] * chi
    phase_y = torch.zeros_like(chi) if kind == "sphere" else coherent_y
    phase_i = torch.zeros_like(chi) if kind == "sphere" else coherent_i

    if kind == "scrambled":
        provisional_y, provisional_i = normalize_components(
            amp_y, amp_i, torch.zeros_like(chi), torch.zeros_like(chi), grid, 1.0
        )
        rho_y = torch.abs(provisional_y) ** 2
        rho_i = torch.abs(provisional_i) ** 2
        safe_r2 = torch.clamp(r_perp * r_perp, min=(grid["dx"] / 2.0) ** 2)
        target_y = scalar(0.5 * torch.sum(rho_y * CONSTANTS["yang_winding"] ** 2 / safe_r2) * grid["dv"])
        target_i = scalar(0.5 * torch.sum(rho_i * CONSTANTS["yin_winding"] ** 2 / safe_r2) * grid["dv"])
        phase_y = random_phase(rho_y, grid, CONSTANTS["random_seed"], target_gradient_energy=target_y)
        phase_i = random_phase(rho_i, grid, CONSTANTS["random_seed"] + 1, target_gradient_energy=target_i)
    elif kind == "perturbed":
        provisional_y, provisional_i = normalize_components(amp_y, amp_i, coherent_y, coherent_i, grid, 1.0)
        phase_y = coherent_y + random_phase(
            torch.abs(provisional_y) ** 2,
            grid,
            CONSTANTS["random_seed"],
            target_rms=0.05,
        )
        phase_i = coherent_i + random_phase(
            torch.abs(provisional_i) ** 2,
            grid,
            CONSTANTS["random_seed"] + 1,
            target_rms=0.05,
        )

    return normalize_components(amp_y, amp_i, phase_y, phase_i, grid, total_mass)


def solve_phi(psi_y: torch.Tensor, psi_i: torch.Tensor, grid: dict[str, Any]) -> torch.Tensor:
    density = torch.abs(psi_y) ** 2 + torch.abs(psi_i) ** 2
    source_hat = torch.fft.fftn(density - torch.mean(density))
    phi_hat = torch.zeros_like(source_hat)
    mask = grid["k2"] > 0
    phi_hat[mask] = -source_hat[mask] / grid["k2"][mask]
    return torch.fft.ifftn(phi_hat).real


def energy_terms(
    psi_y: torch.Tensor,
    psi_i: torch.Tensor,
    grid: dict[str, Any],
    g: float,
    phi_field: torch.Tensor | None = None,
) -> tuple[float, float, float]:
    kinetic = torch.zeros((), device=psi_y.device)
    for field in (psi_y, psi_i):
        laplacian = torch.fft.ifftn(-grid["k2"] * torch.fft.fftn(field))
        kinetic += -0.5 * torch.sum(torch.real(torch.conj(field) * laplacian)) * grid["dv"]
    if g == 0.0:
        potential = 0.0
    else:
        phi_field = solve_phi(psi_y, psi_i, grid) if phi_field is None else phi_field
        density = torch.abs(psi_y) ** 2 + torch.abs(psi_i) ** 2
        potential = scalar(0.5 * g * torch.sum(density * phi_field) * grid["dv"])
    k_value = scalar(kinetic)
    return k_value, potential, k_value + potential


def periodic_center(density: torch.Tensor, grid: dict[str, Any]) -> list[float]:
    center: list[float] = []
    mass = torch.sum(density)
    for coordinate in (grid["x"], grid["y"], grid["z"]):
        moment = torch.sum(density * torch.exp(2j * math.pi * coordinate / CONSTANTS["box_size"])) / mass
        center.append(scalar(torch.angle(moment)) * CONSTANTS["box_size"] / (2.0 * math.pi))
    return center


def center_displacement(center: list[float], initial: list[float]) -> float:
    box = CONSTANTS["box_size"]
    delta = [((a - b + box / 2.0) % box) - box / 2.0 for a, b in zip(center, initial)]
    return math.sqrt(sum(value * value for value in delta))


def winding(field: torch.Tensor, grid: dict[str, Any]) -> tuple[float, float]:
    sectors = CONSTANTS["winding_sectors"]
    flat = field.reshape(-1)
    real = torch.zeros(sectors, device=field.device).scatter_add_(0, grid["sector"], flat.real)
    imag = torch.zeros(sectors, device=field.device).scatter_add_(0, grid["sector"], flat.imag)
    values = torch.complex(real, imag)
    increments = torch.angle(torch.roll(values, shifts=-1) * torch.conj(values))
    turns = scalar(torch.sum(increments) / (2.0 * math.pi))
    coherence = scalar(torch.min(torch.abs(values)) / torch.clamp(torch.mean(torch.abs(values)), min=1e-30))
    return turns, coherence


def diagnose(
    psi_y: torch.Tensor,
    psi_i: torch.Tensor,
    grid: dict[str, Any],
    g: float,
    time_value: float,
    phi_field: torch.Tensor | None,
    initial_center: list[float] | None,
) -> dict[str, Any]:
    rho_y = torch.abs(psi_y) ** 2
    rho_i = torch.abs(psi_i) ** 2
    density = rho_y + rho_i
    mass_y = torch.sum(rho_y) * grid["dv"]
    mass_i = torch.sum(rho_i) * grid["dv"]
    mass = mass_y + mass_i
    kinetic, potential, energy = energy_terms(psi_y, psi_i, grid, g, phi_field)
    r_fit = torch.sum(grid["r_perp"] * density) * grid["dv"] / mass
    d_tor = torch.sqrt((grid["r_perp"] - r_fit) ** 2 + grid["z"] ** 2)
    core_fraction = torch.sum(density[d_tor <= 2.5 * CONSTANTS["sigma"]]) * grid["dv"] / mass
    theta = torch.atan2(grid["z"], grid["r_perp"] - r_fit)
    carrier = torch.exp(1j * (theta - CONSTANTS["spatial_winding"] * grid["chi"]))
    h_y = torch.sum(rho_y * carrier) * grid["dv"] / mass_y
    h_i = torch.sum(rho_i * carrier) * grid["dv"] / mass_i
    abs_y = torch.abs(h_y)
    abs_i = torch.abs(h_i)
    helical_order = 0.5 * (abs_y + abs_i)
    opposition: float | None = None
    if scalar(abs_y) >= 1e-8 and scalar(abs_i) >= 1e-8:
        opposition = scalar(-torch.real(h_y * torch.conj(h_i)) / (abs_y * abs_i))
    winding_y, coherence_y = winding(psi_y, grid)
    winding_i, coherence_i = winding(psi_i, grid)
    center = periodic_center(density, grid)
    return {
        "time": time_value,
        "mass_y": scalar(mass_y),
        "mass_i": scalar(mass_i),
        "mass": scalar(mass),
        "component_ratio": scalar(mass_y / mass_i),
        "kinetic": kinetic,
        "potential": potential,
        "energy": energy,
        "virial": 2.0 * kinetic + potential,
        "r_fit": scalar(r_fit),
        "core_fraction": scalar(core_fraction),
        "winding_y": winding_y,
        "winding_i": winding_i,
        "coherence_y": coherence_y,
        "coherence_i": coherence_i,
        "helix_y": scalar(abs_y),
        "helix_i": scalar(abs_i),
        "helix_order": scalar(helical_order),
        "opposition": opposition,
        "center": center,
        "center_displacement": 0.0 if initial_center is None else center_displacement(center, initial_center),
        "max_density": scalar(torch.max(density)),
    }


def analytic_closure_error() -> float:
    def point(angle: float, sign: float) -> np.ndarray:
        center = np.array([CONSTANTS["major_radius"] * math.cos(angle), CONSTANTS["major_radius"] * math.sin(angle), 0.0])
        radial = np.array([math.cos(angle), math.sin(angle), 0.0])
        vertical = np.array([0.0, 0.0, 1.0])
        offset = sign * CONSTANTS["strand_offset"] * (
            radial * math.cos(CONSTANTS["spatial_winding"] * angle)
            + vertical * math.sin(CONSTANTS["spatial_winding"] * angle)
        )
        return center + offset

    return max(
        float(np.linalg.norm(point(0.0, sign) - point(2.0 * math.pi, sign)))
        for sign in (1.0, -1.0)
    )


def relative_difference(a: float, b: float, floor: float = 1e-8) -> float:
    return abs(a - b) / max(abs(a), abs(b), floor)


def survival(metrics: list[dict[str, Any]]) -> dict[str, bool]:
    initial = metrics[0]
    final = metrics[-1]
    s1 = all(
        abs(row["winding_y"] - 2.0) <= 0.25
        and abs(row["winding_i"] + 3.0) <= 0.25
        and row["coherence_y"] >= 0.05
        and row["coherence_i"] >= 0.05
        for row in metrics
    )
    s2 = (
        final["core_fraction"] / initial["core_fraction"] >= 0.75
        and 0.80 <= final["r_fit"] / initial["r_fit"] <= 1.20
        and all(
            0.75 <= row["r_fit"] / initial["r_fit"] <= 1.25
            for row in metrics
            if row["time"] >= 1.0 - 1e-9
        )
        and final["center_displacement"] <= 0.25 * CONSTANTS["major_radius"]
    )
    s3 = (
        final["helix_order"] / initial["helix_order"] >= 0.70
        and final["opposition"] >= 0.70
    )
    return {"S1_winding": s1, "S2_localization": s2, "S3_helix": s3}


def compare_end(first: dict[str, Any], second: dict[str, Any], limit: float) -> tuple[bool, dict[str, float]]:
    differences = {
        key: relative_difference(first[key], second[key])
        for key in ("r_fit", "core_fraction", "helix_order", "opposition")
    }
    return all(value <= limit for value in differences.values()), differences


def evaluate_gates(
    arms: dict[str, dict[str, Any]],
    preflight: dict[str, Any],
) -> tuple[dict[str, Any], str, list[str], str]:
    gates: dict[str, Any] = {}
    gates["G1"] = preflight["closure_error"] <= 1e-12
    initial_a = arms["A"]["metrics"][0]
    initial_c = arms["C"]["metrics"][0]
    gates["G2"] = (
        abs(initial_a["winding_y"] - 2.0) <= 0.05
        and abs(initial_a["winding_i"] + 3.0) <= 0.05
        and initial_a["coherence_y"] >= 0.20
        and initial_a["coherence_i"] >= 0.20
    )
    gates["G3"] = (
        initial_a["helix_order"] >= 0.80
        and initial_a["opposition"] >= 0.80
        and initial_c["helix_order"] <= 0.20
    )
    gates["G4"] = (
        abs(initial_a["component_ratio"] - PHI) / PHI <= 1e-5
        and abs(initial_a["virial"]) / (2.0 * initial_a["kinetic"] + abs(initial_a["potential"])) <= 1e-5
    )
    geometry_ok = all(gates[name] for name in ("G1", "G2", "G3", "G4"))

    q1 = all(arm["status"] == "complete" for arm in arms.values())
    q2_details: dict[str, float] = {}
    q3_details: dict[str, float] = {}
    for arm_id, arm in arms.items():
        metrics = arm["metrics"]
        mass0 = metrics[0]["mass"]
        energy0 = metrics[0]["energy"]
        denominator = max(abs(energy0), metrics[0]["kinetic"], 1e-12)
        q2_details[arm_id] = max(abs(row["mass"] - mass0) / mass0 for row in metrics)
        q3_details[arm_id] = max(abs(row["energy"] - energy0) / denominator for row in metrics)
    gates["Q1"] = q1
    gates["Q2"] = {"pass": all(value <= 2e-4 for value in q2_details.values()), "max_relative_mass_drift": q2_details}
    gates["Q3"] = {"pass": all(value <= 5e-3 for value in q3_details.values()), "max_relative_energy_drift": q3_details}

    q4_pass, q4_diff = compare_end(arms["A"]["metrics"][-1], arms["J"]["metrics"][-1], 0.05)
    q4_winding = max(
        abs(arms["A"]["metrics"][-1]["winding_y"] - arms["J"]["metrics"][-1]["winding_y"]),
        abs(arms["A"]["metrics"][-1]["winding_i"] - arms["J"]["metrics"][-1]["winding_i"]),
    )
    gates["Q4"] = {"pass": q4_pass and q4_winding <= 0.10, "differences": q4_diff, "winding_difference": q4_winding}

    q5_pass, q5_diff = compare_end(arms["A"]["metrics"][-1], arms["I"]["metrics"][-1], 0.10)
    q5_winding = max(
        abs(arms["A"]["metrics"][-1]["winding_y"] - arms["I"]["metrics"][-1]["winding_y"]),
        abs(arms["A"]["metrics"][-1]["winding_i"] - arms["I"]["metrics"][-1]["winding_i"]),
    )
    direction_agreement = survival(arms["A"]["metrics"]) == survival(arms["I"]["metrics"])
    gates["Q5"] = {
        "pass": q5_pass and q5_winding <= 0.10 and direction_agreement,
        "differences": q5_diff,
        "winding_difference": q5_winding,
        "direction_agreement": direction_agreement,
    }

    primary_survival = survival(arms["A"]["metrics"])
    gates.update(primary_survival)
    perturb_survival = survival(arms["G"]["metrics"])
    p_compare, p_diff = compare_end(arms["A"]["metrics"][-1], arms["G"]["metrics"][-1], 0.15)
    gates["P1"] = {
        "pass": all(perturb_survival.values()) and p_compare,
        "survival": perturb_survival,
        "differences": p_diff,
    }

    quality_ok = (
        gates["Q1"]
        and gates["Q2"]["pass"]
        and gates["Q3"]["pass"]
        and gates["Q4"]["pass"]
        and gates["Q5"]["pass"]
    )
    labels: list[str] = []
    if not primary_survival["S1_winding"]:
        labels.append("UNWINDS")
    initial, final = arms["A"]["metrics"][0], arms["A"]["metrics"][-1]
    if final["core_fraction"] / initial["core_fraction"] < 0.75:
        labels.append("DELOCALIZES")
    radius_ratio = final["r_fit"] / initial["r_fit"]
    if radius_ratio < 0.80:
        labels.append("RADIUS COLLAPSES")
    elif radius_ratio > 1.20:
        labels.append("RADIUS EXPANDS")
    if not primary_survival["S3_helix"]:
        labels.append("HELIX DISSOLVES")
    if final["center_displacement"] > 0.25 * CONSTANTS["major_radius"]:
        labels.append("DRIFTS")

    if not geometry_ok:
        verdict = "INCONCLUSIVE—INVALID INITIALIZATION"
        perturbation_verdict = "UNSCORED"
    elif not quality_ok:
        verdict = "INCONCLUSIVE—NUMERICAL QUALITY"
        perturbation_verdict = "UNSCORED"
    elif all(primary_survival.values()):
        verdict = "EMERGES CONDITIONALLY"
        perturbation_verdict = "PASS" if gates["P1"]["pass"] else "FAIL"
    else:
        verdict = "DOES NOT EMERGE"
        perturbation_verdict = "PASS" if gates["P1"]["pass"] else "FAIL"
    return gates, verdict, labels, perturbation_verdict


def evolve_arm(
    arm: dict[str, Any],
    total_mass: float,
    device: torch.device,
    run_dir: Path,
) -> dict[str, Any]:
    grid = make_grid(arm["n"], device)
    psi_y, psi_i = make_seed(arm["seed"], grid, total_mass)
    g = arm["g"]
    dt = arm["dt"]
    steps = round(CONSTANTS["t_end"] / dt)
    report_steps = round(CONSTANTS["report_cadence"] / dt)
    kinetic_phase = torch.exp(-0.5j * grid["k2"] * dt)
    phi_field = solve_phi(psi_y, psi_i, grid) if g != 0.0 else None
    initial_max_density = scalar(torch.max(torch.abs(psi_y) ** 2 + torch.abs(psi_i) ** 2))
    metrics: list[dict[str, Any]] = []
    fields_y: list[np.ndarray] = []
    fields_i: list[np.ndarray] = []
    times: list[float] = []
    initial_center: list[float] | None = None
    status = "complete"
    stop_reason: str | None = None

    def capture(step: int) -> None:
        nonlocal initial_center
        time_value = step * dt
        row = diagnose(psi_y, psi_i, grid, g, time_value, phi_field, initial_center)
        if initial_center is None:
            initial_center = row["center"]
            row["center_displacement"] = 0.0
        metrics.append(row)
        times.append(time_value)
        fields_y.append(psi_y.detach().cpu().numpy().astype(np.complex64, copy=True))
        fields_i.append(psi_i.detach().cpu().numpy().astype(np.complex64, copy=True))

    capture(0)
    for step in range(1, steps + 1):
        if g != 0.0:
            phase = torch.exp(-0.5j * dt * g * phi_field)
            psi_y *= phase
            psi_i *= phase
        psi_y = torch.fft.ifftn(torch.fft.fftn(psi_y) * kinetic_phase)
        psi_i = torch.fft.ifftn(torch.fft.fftn(psi_i) * kinetic_phase)
        if g != 0.0:
            phi_field = solve_phi(psi_y, psi_i, grid)
            phase = torch.exp(-0.5j * dt * g * phi_field)
            psi_y *= phase
            psi_i *= phase
        density = torch.abs(psi_y) ** 2 + torch.abs(psi_i) ** 2
        if not bool(torch.isfinite(density).all().item()):
            status, stop_reason = "stopped", "nonfinite field"
            break
        if scalar(torch.max(density)) > 1.0e8 * initial_max_density:
            status, stop_reason = "stopped", "density ceiling"
            break
        if step % report_steps == 0:
            capture(step)

    receipt_path = run_dir / f"fields_{arm['id']}.npz"
    np.savez_compressed(
        receipt_path,
        times=np.asarray(times, dtype=np.float64),
        psi_y=np.stack(fields_y),
        psi_i=np.stack(fields_i),
    )
    return {
        "config": arm,
        "status": status,
        "stop_reason": stop_reason,
        "metrics": metrics,
        "fields_file": receipt_path.name,
        "fields_sha256": sha256_file(receipt_path),
    }


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
    run_dir = args.output or ROOT / "runs" / f"{stamp}_toroidal_coherence_survival_v2"
    run_dir.mkdir(parents=True, exist_ok=False)

    sources = {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
        for path in (Path(__file__).resolve(), BASE_PREREG, V2_PREREG, VERIFIER)
    }
    reference_grid = make_grid(CONSTANTS["reference_n"], device)
    unit_y, unit_i = make_seed("closed", reference_grid, 1.0)
    reference_phi = solve_phi(unit_y, unit_i, reference_grid)
    k1, w1, _ = energy_terms(unit_y, unit_i, reference_grid, 1.0, reference_phi)
    virial_mass = -2.0 * k1 / w1
    if w1 >= 0.0 or not math.isfinite(virial_mass) or not 0.1 <= virial_mass <= 1.0e6:
        raise RuntimeError(f"invalid virial calibration: K1={k1}, W1={w1}, M={virial_mass}")

    scaled_y, scaled_i = make_seed("closed", reference_grid, virial_mass)
    scaled_phi = solve_phi(scaled_y, scaled_i, reference_grid)
    closed_initial = diagnose(scaled_y, scaled_i, reference_grid, 1.0, 0.0, scaled_phi, None)
    untwisted_y, untwisted_i = make_seed("untwisted", reference_grid, virial_mass)
    untwisted_phi = solve_phi(untwisted_y, untwisted_i, reference_grid)
    untwisted_initial = diagnose(untwisted_y, untwisted_i, reference_grid, 1.0, 0.0, untwisted_phi, None)
    preflight = {
        "closure_error": analytic_closure_error(),
        "k1": k1,
        "w1": w1,
        "virial_mass": virial_mass,
        "closed_initial": closed_initial,
        "untwisted_initial": untwisted_initial,
    }
    initialization_ok = (
        preflight["closure_error"] <= 1e-12
        and abs(closed_initial["winding_y"] - 2.0) <= 0.05
        and abs(closed_initial["winding_i"] + 3.0) <= 0.05
        and closed_initial["coherence_y"] >= 0.20
        and closed_initial["coherence_i"] >= 0.20
        and closed_initial["helix_order"] >= 0.80
        and closed_initial["opposition"] >= 0.80
        and untwisted_initial["helix_order"] <= 0.20
        and abs(closed_initial["component_ratio"] - PHI) / PHI <= 1e-5
        and abs(closed_initial["virial"]) / (2.0 * closed_initial["kinetic"] + abs(closed_initial["potential"])) <= 1e-5
    )
    if not initialization_ok:
        invalid = {
            "probe": "toroidal_coherence_survival_v2",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "constants": CONSTANTS,
            "sources": sources,
            "device": str(device),
            "dtype": "complex64/float32",
            "preflight": preflight,
            "verdict": "INCONCLUSIVE—INVALID INITIALIZATION",
        }
        with (run_dir / "results.json").open("x", encoding="utf-8") as handle:
            json.dump(invalid, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(json.dumps({"run_dir": str(run_dir), "verdict": invalid["verdict"]}, indent=2))
        return

    arm_results: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        print(f"running arm {arm['id']} ({arm['name']})", flush=True)
        arm_results[arm["id"]] = evolve_arm(arm, virial_mass, device, run_dir)
        if arm_results[arm["id"]]["status"] != "complete":
            print(f"arm {arm['id']} stopped: {arm_results[arm['id']]['stop_reason']}", flush=True)

    gates, verdict, failure_labels, perturbation_verdict = evaluate_gates(arm_results, preflight)
    results = {
        "probe": "toroidal_coherence_survival_v2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "constants": CONSTANTS,
        "arms": arm_results,
        "sources": sources,
        "device": str(device),
        "device_name": torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU",
        "torch_version": torch.__version__,
        "dtype": "complex64/float32",
        "preflight": preflight,
        "gates": gates,
        "verdict": verdict,
        "failure_labels": failure_labels,
        "perturbation_verdict": perturbation_verdict,
    }
    results_path = run_dir / "results.json"
    with results_path.open("x", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "verdict": verdict,
                "failure_labels": failure_labels,
                "perturbation_verdict": perturbation_verdict,
                "gates": gates,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
