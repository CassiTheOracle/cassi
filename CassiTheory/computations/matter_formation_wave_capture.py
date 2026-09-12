#!/usr/bin/env python3
"""Axisymmetric charged-wave capture in the supplied scalar parent action.

The runner uses a separate charged diagnostic from the older neutral-packet
experiment.  A collision counts only when a post-collision remnant remains
bound after outgoing radiation has separated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "computations") not in sys.path:
    sys.path.insert(0, str(ROOT / "computations"))

from matter_formation_neutral_packets import (  # noqa: E402
    CylindricalGrid,
    YOSHIDA,
)
from matter_formation_radial_cloud import CONSTANTS, OMEGA_INF  # noqa: E402

SELF = Path(__file__).resolve()
PREREG = ROOT / "computations" / "matter_formation_wave_capture_v2_prereg.md"
NEUTRAL_SOURCE = ROOT / "computations" / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = ROOT / "computations" / "matter_formation_radial_cloud.py"
VERIFIER_SOURCE = ROOT / "computations" / "verify_matter_formation_wave_capture.py"
SCHEMA = "matter-formation-wave-capture-primary-v2"
A = float(CONSTANTS["a"])
CPSI = float(CONSTANTS["c_psi"])
URHO = float(CONSTANTS["u_rho"])
UC = float(CONSTANTS["u_C"])
K = float(CONSTANTS["k_Cx"])
HC = float(CONSTANTS["h_C"])
B = float(CONSTANTS["e_C"] + 1.0 / (4.0 * A))
VSTAR = math.sqrt(K / (2.0 * A))
T_FINAL = 48.0
SAMPLE_DT = 0.5
LATE_START = 32.0
CORE_RADIUS = 8.0
CUT_RADIUS = 8.0
CUT_WIDTH = 4.0
SHELL_RADIUS = CUT_RADIUS + CUT_WIDTH
OUTER_SHELL_WIDTH = 16.0
ENERGY_DRIFT_TOL = 2.0e-4
CHARGE_DRIFT_TOL = 2.0e-5
BOUNDARY_ENERGY_TOL = 1.0e-6
LOCAL_BALANCE_TOL = 1.0e-8
COMPARISON_TOL = 0.05
SNAPSHOT_TOL = 0.02
RETAINED_FRACTION = 0.25
BINDING_RATIO_MAX = 0.99
CORE_RMS_MAX = 6.0
LATE_CORE_VARIATION = 0.10
SHELL_ENERGY_FRACTION = 0.05
INITIAL_OVERLAP_MAX = 0.01
INITIAL_CORE_FRACTION_MAX = 0.10

GRID_SPECS = {
    "G0": (192, 0.5, 1.0 / 64.0),
    "G1": (192, 0.25, 1.0 / 64.0),
    "G2": (256, 0.5, 1.0 / 64.0),
    "T1": (192, 0.5, 1.0 / 128.0),
}
BASE_ARMS = ("single64", "single128", "single256", "pair64", "pair128", "pair256", "antiphase256", "outgoing256", "uncoupled256")
COMPARISON_ARMS = ("single256", "pair256", "antiphase256", "uncoupled256")
SNAPSHOT_TIMES = (0.0, 32.0, 40.0, 48.0)
REQUIRED_OBSERVABLES = (
    "energy",
    "charge",
    "abs_charge",
    "center",
    "core_charge",
    "core_abs_charge",
    "core_fraction",
    "core_rms",
    "core_f2",
    "mediator_depletion",
    "core_energy",
    "cut_energy",
    "cut_charge",
    "momentum",
    "radicand",
    "binding_ratio",
    "shell_energy",
    "shell_energy_fraction",
    "boundary_energy",
    "boundary_energy_fraction",
    "core_energy_derivative",
    "core_energy_flux",
    "core_energy_balance_error",
    "core_charge_derivative",
    "core_charge_flux",
    "core_charge_balance_error",
)




def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value: Any) -> bool:
    if isinstance(value, (float, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, (int, str, bool)) or value is None:
        return True
    if isinstance(value, np.ndarray):
        return bool(np.isfinite(value).all())
    if isinstance(value, dict):
        return all(finite(k) and finite(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite(item) for item in value)
    return False


def finite_number(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def write_json(path: Path, value: dict[str, Any]) -> None:
    if not finite(value):
        raise RuntimeError(f"nonfinite JSON payload: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=True, exist_ok=False)
    result: dict[str, str] = {}
    for path in (SELF, PREREG, NEUTRAL_SOURCE, CLOUD_SOURCE, VERIFIER_SOURCE):
        rel = path.relative_to(ROOT).as_posix()
        destination = source_dir / rel.replace("/", "__")
        shutil.copyfile(path, destination)
        result[rel] = sha256(path)
    return result


def smooth_cut(distance: torch.Tensor, inner: float = CUT_RADIUS, width: float = CUT_WIDTH) -> torch.Tensor:
    s = torch.clamp((distance - inner) / width, 0.0, 1.0)
    return 1.0 - 3.0 * s.square() + 2.0 * s.pow(3)


def axial_derivative(value: torch.Tensor, h: float) -> torch.Tensor:
    result = torch.empty_like(value)
    result[..., 1:-1] = (value[..., 2:] - value[..., :-2]) / (2.0 * h)
    result[..., 0] = (value[..., 1] - value[..., 0]) / h
    result[..., -1] = (value[..., -1] - value[..., -2]) / h
    return result


def energy_components(grid: CylindricalGrid, q: torch.Tensor, v: torch.Tensor, coupling: float) -> dict[str, float]:
    f = q[0] + 1.0
    n = q[1].square() + q[2].square()
    mediator = (grid.volume * (URHO / 4.0 * (f.square() - 1.0).square())).sum()
    carrier = (grid.volume * ((B - coupling + coupling * f.square()) * n + UC / 2.0 * n.square())).sum()
    kinetic = (grid.volume * (CPSI / 2.0 * v[0].square() + A * (v[1].square() + v[2].square()))).sum()
    radial_faces = ((q[:, 1:, :] - q[:, :-1, :]).square() * grid.radial_edge) / 2.0
    radial_faces[1:] *= K
    radial = radial_faces.sum() + grid.radial_boundary / 2.0 * (
        q[0, -1, :].square() + K * q[1, -1, :].square() + K * q[2, -1, :].square()
    ).sum()
    axial_faces = ((q[:, :, 1:] - q[:, :, :-1]).square() * grid.axial_edge) / 2.0
    axial_faces[1:] *= K
    axial = axial_faces.sum() + (
        grid.axial_edge[:, 0] * (
            q[0, :, 0].square() + K * (q[1, :, 0].square() + q[2, :, 0].square())
        )
    ).sum()
    axial += (
        grid.axial_edge[:, 0] * (
            q[0, :, -1].square() + K * (q[1, :, -1].square() + q[2, :, -1].square())
        )
    ).sum()
    return {
        "mediator_potential": float(mediator),
        "carrier_potential": float(carrier),
        "kinetic_energy": float(kinetic),
        "radial_gradient": float(radial),
        "axial_gradient": float(axial),
    }


def cell_energy(grid: CylindricalGrid, q: torch.Tensor, v: torch.Tensor, coupling: float) -> torch.Tensor:
    """Allocate the exact grid energy to cells for shell and boundary checks."""
    f = q[0] + 1.0
    n = q[1].square() + q[2].square()
    potential = URHO / 4.0 * (f.square() - 1.0).square() + (B - coupling + coupling * f.square()) * n + UC / 2.0 * n.square()
    kinetic = CPSI / 2.0 * v[0].square() + A * (v[1].square() + v[2].square())
    result = (potential + kinetic) * grid.volume
    radial_faces = ((q[:, 1:, :] - q[:, :-1, :]).square() * grid.radial_edge) / 2.0
    radial_faces[1:] *= K
    radial_total = radial_faces.sum(dim=0)
    result[1:, :] += radial_total / 2.0
    result[:-1, :] += radial_total / 2.0
    result[-1, :] += grid.radial_boundary / 2.0 * (
        q[0, -1, :].square() + K * q[1, -1, :].square() + K * q[2, -1, :].square())
    axial_faces = ((q[:, :, 1:] - q[:, :, :-1]).square() * grid.axial_edge) / 2.0
    axial_faces[1:] *= K
    axial_total = axial_faces.sum(dim=0)
    result[:, 1:] += axial_total / 2.0
    result[:, :-1] += axial_total / 2.0
    result[:, 0] += grid.axial_edge[:, 0] * (
        q[0, :, 0].square() + K * q[1, :, 0].square() + K * q[2, :, 0].square())
    result[:, -1] += grid.axial_edge[:, 0] * (
        q[0, :, -1].square() + K * q[1, :, -1].square() + K * q[2, :, -1].square())
    return result


def potential_gradient(q: torch.Tensor, coupling: float) -> torch.Tensor:
    f = q[0] + 1.0
    n = q[1].square() + q[2].square()
    coefficient = B - coupling + coupling * f.square() + UC * n
    result = torch.empty_like(q)
    result[0] = URHO * (f.square() - 1.0) * f + 2.0 * coupling * f * n
    result[1:] = 2.0 * coefficient * q[1:]
    return result


def local_balances(
    grid: CylindricalGrid,
    q: torch.Tensor,
    v: torch.Tensor,
    acc: torch.Tensor,
    coupling: float,
    core_mask: torch.Tensor,
) -> dict[str, float]:
    """Assemble fixed-core action derivatives and oriented face currents."""
    gradient_coeff = torch.as_tensor((1.0, K, K), dtype=q.dtype, device=q.device)[:, None, None]
    mass_coeff = torch.as_tensor((CPSI, 2.0 * A, 2.0 * A), dtype=q.dtype, device=q.device)[:, None, None]
    local = mass_coeff * grid.volume * v * acc + grid.volume * potential_gradient(q, coupling) * v
    edge_derivative = torch.zeros_like(core_mask, dtype=q.dtype)
    core_index = core_mask.to(dtype=q.dtype)
    energy_flux = torch.zeros((), dtype=q.dtype, device=q.device)
    charge_flux = torch.zeros((), dtype=q.dtype, device=q.device)

    radial_difference = q[:, 1:, :] - q[:, :-1, :]
    radial_velocity_difference = v[:, 1:, :] - v[:, :-1, :]
    radial_derivative = (gradient_coeff * grid.radial_edge * radial_difference * radial_velocity_difference).sum(dim=0)
    edge_derivative[1:, :] += radial_derivative / 2.0
    edge_derivative[:-1, :] += radial_derivative / 2.0
    radial_energy_flux = -0.5 * (gradient_coeff * grid.radial_edge * radial_difference * (v[:, 1:, :] + v[:, :-1, :])).sum(dim=0)
    radial_charge_flux = K * grid.radial_edge * (
        q[1, :-1, :] * q[2, 1:, :] - q[2, :-1, :] * q[1, 1:, :])
    energy_flux += (radial_energy_flux * (core_index[:-1, :] - core_index[1:, :])).sum()
    charge_flux += (radial_charge_flux * (core_index[:-1, :] - core_index[1:, :])).sum()

    axial_difference = q[:, :, 1:] - q[:, :, :-1]
    axial_velocity_difference = v[:, :, 1:] - v[:, :, :-1]
    axial_derivative_value = (gradient_coeff * grid.axial_edge * axial_difference * axial_velocity_difference).sum(dim=0)
    edge_derivative[:, 1:] += axial_derivative_value / 2.0
    edge_derivative[:, :-1] += axial_derivative_value / 2.0
    axial_energy_flux = -0.5 * (gradient_coeff * grid.axial_edge * axial_difference * (v[:, :, 1:] + v[:, :, :-1])).sum(dim=0)
    axial_charge_flux = K * grid.axial_edge * (
        q[1, :, :-1] * q[2, :, 1:] - q[2, :, :-1] * q[1, :, 1:])
    energy_flux += (axial_energy_flux * (core_index[:, :-1] - core_index[:, 1:])).sum()
    charge_flux += (axial_charge_flux * (core_index[:, :-1] - core_index[:, 1:])).sum()

    radial_boundary_derivative = grid.radial_boundary * (
        q[0, -1, :] * v[0, -1, :] + K * q[1, -1, :] * v[1, -1, :] + K * q[2, -1, :] * v[2, -1, :])
    edge_derivative[-1, :] += radial_boundary_derivative
    axial_boundary_derivative = 2.0 * grid.axial_edge[:, 0] * (
        q[0, :, 0] * v[0, :, 0] + K * q[1, :, 0] * v[1, :, 0] + K * q[2, :, 0] * v[2, :, 0])
    edge_derivative[:, 0] += axial_boundary_derivative
    edge_derivative[:, -1] += 2.0 * grid.axial_edge[:, 0] * (
        q[0, :, -1] * v[0, :, -1] + K * q[1, :, -1] * v[1, :, -1] + K * q[2, :, -1] * v[2, :, -1])

    energy_derivative = float(((local.sum(dim=0) + edge_derivative) * core_mask).sum())
    charge_density_derivative = -2.0 * A * (q[1] * acc[2] - q[2] * acc[1])
    charge_derivative = float((grid.volume * charge_density_derivative * core_mask).sum())
    return {
        "core_energy_derivative": energy_derivative,
        "core_energy_flux": float(energy_flux),
        "core_energy_balance_error": abs(energy_derivative + float(energy_flux)) / max(1.0, abs(energy_derivative), abs(float(energy_flux))),
        "core_charge_derivative": charge_derivative,
        "core_charge_flux": float(charge_flux),
        "core_charge_balance_error": abs(charge_derivative + float(charge_flux)) / max(1.0, abs(charge_derivative), abs(float(charge_flux))),
    }


def arm_definition(arm: str) -> tuple[float, float, float, bool, bool]:
    if arm.startswith("single"):
        charge = float(arm.removeprefix("single"))
        return charge, 0.0, OMEGA_INF, False, False
    charge = 256.0
    if arm in ("pair64", "pair128"):
        charge = float(arm.removeprefix("pair"))
    if arm == "uncoupled256":
        return 256.0, 1.0, math.sqrt(OMEGA_INF * OMEGA_INF + 8.0), True, True
    if arm == "antiphase256":
        return 256.0, 1.0, math.sqrt(OMEGA_INF * OMEGA_INF + 8.0), True, False
    if arm == "outgoing256":
        return 256.0, 1.0, math.sqrt(OMEGA_INF * OMEGA_INF + 8.0), True, False
    if arm.startswith("pair"):
        return charge, 1.0, math.sqrt(OMEGA_INF * OMEGA_INF + 8.0), True, False
    raise ValueError(f"unknown arm: {arm}")


def initial_state(grid: CylindricalGrid, arm: str) -> tuple[torch.Tensor, torch.Tensor, float, dict[str, float | bool]]:
    charge, wave_number, omega, pair, uncoupled = arm_definition(arm)
    r = grid.r
    zeta = grid.axial
    if arm.startswith("single"):
        envelope = torch.exp(-(grid.r2 + zeta[None, :].square()) / (2.0 * 4.0 ** 2))
        complex_field = envelope.to(dtype=torch.complex128)
        centers = (0.0,)
    else:
        envelope_right = torch.exp(-(grid.r2 + (zeta[None, :] + 12.0).square()) / (2.0 * 4.0 ** 2))
        envelope_left = torch.exp(-(grid.r2 + (zeta[None, :] - 12.0).square()) / (2.0 * 4.0 ** 2))
        phase_right = wave_number * (zeta[None, :] + 12.0)
        phase_left = -wave_number * (zeta[None, :] - 12.0)
        sign_left = -1.0 if arm == "antiphase256" else 1.0
        if arm == "outgoing256":
            phase_right = -phase_right
            phase_left = -phase_left
        complex_field = envelope_right * torch.exp(1j * phase_right) + sign_left * envelope_left * torch.exp(1j * phase_left)
        centers = (-12.0, 12.0)
    norm = torch.sum(grid.volume * (complex_field.real.square() + complex_field.imag.square()))
    norm_value = float(norm)
    if not finite_number(charge) or charge <= 0.0 or not finite_number(norm_value) or norm_value <= 0.0:
        raise RuntimeError(f"invalid initial normalization for {arm}")
    complex_field = complex_field * math.sqrt(charge / (2.0 * A * omega * norm_value))
    q = torch.zeros((3, grid.nr, grid.nz), dtype=torch.float64, device="cuda")
    q[1] = complex_field.real
    q[2] = complex_field.imag
    v = torch.zeros_like(q)
    v[1] = omega * q[2]
    v[2] = -omega * q[1]
    overlap = 0.0
    if pair:
        a = torch.exp(-(grid.r2 + (zeta[None, :] + 12.0).square()) / (2.0 * 4.0 ** 2))
        b = torch.exp(-(grid.r2 + (zeta[None, :] - 12.0).square()) / (2.0 * 4.0 ** 2))
        overlap = float(torch.abs(torch.sum(grid.volume * a * b)) / torch.sqrt(torch.sum(grid.volume * a.square()) * torch.sum(grid.volume * b.square())))
    rho = 2.0 * A * omega * (q[1].square() + q[2].square())
    distance = torch.sqrt(grid.r2 + grid.axial[None, :].square())
    initial_core = float((grid.volume * rho * (distance < CORE_RADIUS)).sum()) / charge
    metadata = {"charge": charge, "omega": omega, "pair": pair, "uncoupled": uncoupled, "initial_overlap": overlap, "initial_core_fraction": initial_core, "centers": list(centers), "initially_unbound": bool((not pair) or (overlap <= INITIAL_OVERLAP_MAX and initial_core <= INITIAL_CORE_FRACTION_MAX))}
    return q, v, (0.0 if uncoupled else HC), metadata


def diagnostics(
    grid: CylindricalGrid,
    q: torch.Tensor,
    v: torch.Tensor,
    coupling: float,
    initial_charge: float,
    initial_energy: float,
    acc: torch.Tensor | None = None,
) -> dict[str, float | None]:
    if acc is None:
        acc = grid.acceleration(q, coupling)
    components = energy_components(grid, q, v, coupling)
    rho = -2.0 * A * (q[1] * v[2] - q[2] * v[1])
    abs_rho = torch.abs(rho)
    total_charge = float((grid.volume * rho).sum())
    abs_charge = float((grid.volume * abs_rho).sum())
    mass = max(abs_charge, 1.0e-30)
    center = float((grid.volume * abs_rho * grid.axial[None, :]).sum()) / mass
    distance2 = grid.r2 + grid.axial[None, :].square()
    core_mask = distance2 < CORE_RADIUS * CORE_RADIUS
    core_charge = float((grid.volume * rho * core_mask).sum())
    core_abs = float((grid.volume * abs_rho * core_mask).sum())
    core_rms = math.sqrt(max(0.0, float((grid.volume * abs_rho * distance2 * core_mask).sum()) / max(core_abs, 1.0e-30)))
    core_f2 = float((grid.volume * abs_rho * (q[0] + 1.0).square() * core_mask).sum()) / max(core_abs, 1.0e-30)
    distance = torch.sqrt(distance2)
    cut = smooth_cut(distance)
    cut_q = cut * q
    cut_v = cut * v
    cut_energy = float(grid.energy(cut_q, cut_v, coupling))
    cut_charge = float((grid.volume * rho * cut.square()).sum())
    dz = axial_derivative(cut_q, grid.h)
    momentum = -float((grid.volume * (CPSI * cut_v[0] * dz[0] + 2.0 * A * (cut_v[1] * dz[1] + cut_v[2] * dz[2]))).sum())
    radicand = cut_energy * cut_energy - (VSTAR * momentum) ** 2
    binding_ratio: float | None = None
    if cut_charge != 0.0 and radicand >= 0.0:
        binding_ratio = math.sqrt(radicand) / (OMEGA_INF * abs(cut_charge))
    allocated = cell_energy(grid, q, v, coupling)
    shell_mask = (distance >= CUT_RADIUS) & (distance < SHELL_RADIUS)
    boundary_mask = (grid.r[:, None] >= grid.R - OUTER_SHELL_WIDTH) | (torch.abs(grid.axial[None, :]) >= grid.R - OUTER_SHELL_WIDTH)
    shell_energy = float((allocated * shell_mask).sum())
    boundary_energy = float((allocated * boundary_mask).sum())
    total_energy = float(grid.energy(q, v, coupling))
    balances = local_balances(grid, q, v, acc, coupling, core_mask)
    return {
        "energy": total_energy,
        "charge": total_charge,
        "abs_charge": abs_charge,
        "center": center,
        "core_charge": core_charge,
        "core_abs_charge": core_abs,
        "core_fraction": core_charge / initial_charge if abs(initial_charge) > 1.0e-30 else None,
        "core_rms": core_rms,
        "core_f2": core_f2,
        "mediator_depletion": 1.0 - core_f2,
        "core_energy": float((allocated * core_mask).sum()),
        "cut_energy": cut_energy,
        "cut_charge": cut_charge,
        "momentum": momentum,
        "radicand": radicand,
        "binding_ratio": binding_ratio,
        "shell_energy": shell_energy,
        "shell_energy_fraction": shell_energy / max(abs(initial_energy), 1.0e-30),
        "boundary_energy": boundary_energy,
        "boundary_energy_fraction": boundary_energy / max(abs(initial_energy), 1.0e-30),
        **components,
        **balances,
    }


def write_state(path: Path, grid: CylindricalGrid, q: torch.Tensor, v: torch.Tensor, time_value: float) -> dict[str, str | float]:
    with path.open("xb") as stream:
        np.savez_compressed(stream, fields=q.detach().cpu().numpy(), velocities=v.detach().cpu().numpy(), r=grid.r.detach().cpu().numpy(), axial=grid.axial.detach().cpu().numpy(), volume=grid.volume.detach().cpu().numpy(), time=np.asarray(time_value))
    return {"path": path.name, "sha256": sha256(path), "time": time_value}


def run_row(output: Path, grid_name: str, grid: CylindricalGrid, dt: float, arm: str) -> dict[str, Any]:
    started = time.perf_counter()
    q, v, coupling, metadata = initial_state(grid, arm)
    acc = grid.acceleration(q, coupling)
    initial_energy = float(grid.energy(q, v, coupling))
    initial_rho = -2.0 * A * (q[1] * v[2] - q[2] * v[1])
    initial_charge = float((grid.volume * initial_rho).sum())
    if not finite_number(initial_energy) or not finite_number(initial_charge):
        raise RuntimeError(f"nonfinite initial reference for {grid_name}_{arm}")
    times = np.arange(int(round(T_FINAL / SAMPLE_DT)) + 1, dtype=np.float64) * SAMPLE_DT
    trace: list[dict[str, float | None]] = []
    initial = diagnostics(grid, q, v, coupling, initial_charge, initial_energy, acc)
    trace.append(initial)
    states: list[dict[str, str | float]] = [write_state(output / f"{grid_name}_{arm}_t000.npz", grid, q, v, 0.0)]
    sample_step = int(round(SAMPLE_DT / dt))
    steps = int(round(T_FINAL / dt))
    for step in range(1, steps + 1):
        for weight in YOSHIDA:
            h = weight * dt
            v.add_(acc, alpha=h / 2.0)
            q.add_(v, alpha=h)
            acc = grid.acceleration(q, coupling)
            v.add_(acc, alpha=h / 2.0)
        if step % sample_step == 0:
            current = step * dt
            trace.append(diagnostics(grid, q, v, coupling, initial_charge, initial_energy, acc))
            if any(abs(current - target) < 1.0e-12 for target in SNAPSHOT_TIMES[1:]):
                states.append(write_state(output / f"{grid_name}_{arm}_t{int(round(current)):03d}.npz", grid, q, v, current))
    if not trace:
        raise RuntimeError(f"empty diagnostic trace for {grid_name}_{arm}")
    energy_values = [row.get("energy") for row in trace]
    charge_values = [row.get("charge") for row in trace]
    energy_drift = (
        max(abs(float(value) - initial_energy) for value in energy_values) / max(1.0, abs(initial_energy))
        if all(finite_number(value) for value in energy_values) else math.inf
    )
    charge_drift = (
        max(abs(float(value) - initial_charge) for value in charge_values) / max(1.0, abs(initial_charge))
        if all(finite_number(value) for value in charge_values) else math.inf
    )
    late = [row for index, row in enumerate(trace) if times[index] >= LATE_START]
    core_fraction_values = [row.get("core_fraction") for row in late]
    binding_values = [row.get("binding_ratio") for row in late]
    finite_trace = all(finite(row) for row in trace)
    complete_observables = bool(
        trace
        and all(finite_number(row.get(name)) for row in trace for name in REQUIRED_OBSERVABLES)
    )
    balance_error = (
        max(
            max(float(row["core_energy_balance_error"]) for row in trace),
            max(float(row["core_charge_balance_error"]) for row in trace),
        )
        if complete_observables else math.inf
    )
    numerically_qualified = bool(
        finite_trace
        and complete_observables
        and energy_drift < ENERGY_DRIFT_TOL
        and charge_drift < CHARGE_DRIFT_TOL
        and max(float(row["boundary_energy_fraction"]) for row in trace) < BOUNDARY_ENERGY_TOL
        and balance_error <= LOCAL_BALANCE_TOL
    )
    eligibility = bool(metadata["initially_unbound"] and initial_energy >= OMEGA_INF * abs(initial_charge)) if metadata["pair"] else True
    late_variation = math.inf
    if late and abs(initial_charge) > 1.0e-30 and all(finite_number(row.get("core_charge")) for row in late):
        late_variation = (max(float(row["core_charge"]) for row in late) - min(float(row["core_charge"]) for row in late)) / abs(initial_charge)
    persistent = bool(
        late
        and complete_observables
        and min(float(value) for value in core_fraction_values) >= RETAINED_FRACTION
        and max(float(value) for value in binding_values) < BINDING_RATIO_MAX
        and max(float(row["core_rms"]) for row in late) <= CORE_RMS_MAX
        and max(float(row["shell_energy_fraction"]) for row in late) <= SHELL_ENERGY_FRACTION
        and late_variation <= LATE_CORE_VARIATION
    )
    formation = bool(metadata["pair"] and eligibility and numerically_qualified and persistent)
    self_localized = bool((not metadata["pair"]) and numerically_qualified and persistent)
    row = {
        "grid": grid_name,
        "arm": arm,
        "R": grid.R,
        "spacing": grid.h,
        "dt": dt,
        "coupling": coupling,
        "metadata": metadata,
        "initial": initial,
        "times": times.tolist(),
        "trace": trace,
        "states": states,
        "energy_drift": energy_drift,
        "charge_drift": charge_drift,
        "local_balance_max_error": balance_error,
        "late_core_variation": late_variation,
        "numerically_qualified": numerically_qualified,
        "preparation_eligible": eligibility,
        "persistent_remnant": persistent,
        "formation": formation,
        "self_localized": self_localized,
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_json(output / f"{grid_name}_{arm}.json", row)
    return row


def compare_rows(left: dict[str, Any], right: dict[str, Any], kind: str) -> dict[str, Any]:
    key_left = left["grid"] + "_" + left["arm"]
    key_right = right["grid"] + "_" + right["arm"]
    names = ("energy", "charge", "core_fraction", "core_rms", "binding_ratio", "shell_energy_fraction")
    result: dict[str, Any] = {"kind": kind, "left": key_left, "right": key_right, "errors": {}, "pass": False}
    if not left.get("numerically_qualified", False) or not right.get("numerically_qualified", False):
        result["reason"] = "both rows must pass numerical qualification"
        return result
    if len(left.get("times", [])) != len(left.get("trace", [])) or len(right.get("times", [])) != len(right.get("trace", [])):
        result["reason"] = "trace/time coverage mismatch"
        return result
    left_late = [row for index, row in enumerate(left["trace"]) if left["times"][index] >= LATE_START]
    right_late = [row for index, row in enumerate(right["trace"]) if right["times"][index] >= LATE_START]
    if not left_late or not right_late:
        result["reason"] = "late trace missing"
        return result
    if any(not finite_number(row.get(name)) for row in left_late + right_late for name in REQUIRED_OBSERVABLES):
        result["reason"] = "nonfinite required observable"
        return result
    initial_values = (
        left.get("initial", {}).get("energy"),
        right.get("initial", {}).get("energy"),
        left.get("initial", {}).get("charge"),
        right.get("initial", {}).get("charge"),
    )
    if not all(finite_number(value) for value in initial_values):
        result["reason"] = "nonfinite initial comparison scale"
        return result
    left_means = {name: float(np.mean([row[name] for row in left_late])) for name in names}
    right_means = {name: float(np.mean([row[name] for row in right_late])) for name in names}
    scales = {
        "energy": max(1.0, abs(float(left["initial"]["energy"])), abs(float(right["initial"]["energy"]))),
        "charge": max(1.0, abs(float(left["initial"]["charge"])), abs(float(right["initial"]["charge"]))),
        "core_fraction": 1.0,
        "core_rms": CORE_RADIUS,
        "binding_ratio": 1.0,
        "shell_energy_fraction": 1.0,
    }
    errors = {name: abs(left_means[name] - right_means[name]) / scales[name] for name in names}
    result["errors"] = errors
    result["pass"] = bool(all(finite_number(value) for value in errors.values()) and max(errors.values()) < COMPARISON_TOL)
    return result


def run_smoke() -> int:
    grid = CylindricalGrid(32, 1.0)
    q, v, coupling, metadata = initial_state(grid, "pair256")
    acc = grid.acceleration(q, coupling)
    initial_energy = float(grid.energy(q, v, coupling))
    initial_rho = -2.0 * A * (q[1] * v[2] - q[2] * v[1])
    initial_charge = float((grid.volume * initial_rho).sum())
    initial = diagnostics(grid, q, v, coupling, initial_charge, initial_energy, acc)
    for weight in YOSHIDA:
        h = weight * 0.0625
        v.add_(acc, alpha=h / 2.0)
        q.add_(v, alpha=h)
        acc = grid.acceleration(q, coupling)
        v.add_(acc, alpha=h / 2.0)
    current = diagnostics(grid, q, v, coupling, initial_charge, initial_energy, acc)
    components = energy_components(grid, q, v, coupling)
    assert abs(sum(components.values()) - float(grid.energy(q, v, coupling))) < 1.0e-8

    vacuum = torch.zeros_like(q)
    assert torch.count_nonzero(grid.acceleration(vacuum, coupling)) == 0
    assert metadata["pair"] is True and metadata["initial_overlap"] < INITIAL_OVERLAP_MAX
    assert all(finite(row) for row in (initial, current))
    assert abs(float(smooth_cut(torch.tensor(8.0, device=q.device))) - 1.0) < 1.0e-14
    assert abs(float(smooth_cut(torch.tensor(12.0, device=q.device))) - 0.0) < 1.0e-14

    conjugate_q, conjugate_v = q.clone(), v.clone()
    conjugate_q[2].neg_()
    conjugate_v[2].neg_()
    conjugate_rho = -2.0 * A * (conjugate_q[1] * conjugate_v[2] - conjugate_q[2] * conjugate_v[1])
    assert abs(float(grid.energy(conjugate_q, conjugate_v, coupling)) - float(grid.energy(q, v, coupling))) < 1.0e-8
    assert abs(float((grid.volume * conjugate_rho).sum()) + float((grid.volume * (-2.0 * A * (q[1] * v[2] - q[2] * v[1]))).sum())) < 1.0e-8

    probe = torch.zeros_like(q)
    probe[0, 2, 3] = 0.1
    probe_v = torch.zeros_like(q)
    probe_acc = grid.acceleration(probe, coupling)
    epsilon = 1.0e-6
    plus, minus = probe.clone(), probe.clone()
    plus[0, 2, 3] += epsilon
    minus[0, 2, 3] -= epsilon
    derivative = float((grid.energy(plus, probe_v, coupling) - grid.energy(minus, probe_v, coupling)) / (2.0 * epsilon))
    expected = -CPSI * float(grid.volume[2, 0]) * float(probe_acc[0, 2, 3])
    assert abs(derivative - expected) / max(1.0, abs(derivative), abs(expected)) < 1.0e-6

    free = torch.zeros_like(q)
    free[1, 2, 3] = 1.0e-6
    free_acc = grid.acceleration(free, 0.0)
    linear = grid.laplacian(free)
    linear[1:] *= K / 2.0
    linear[1:] -= B * free[1:]
    linear[1:] /= A
    assert float(torch.max(torch.abs(free_acc[1:] - linear[1:]))) < 1.0e-8

    torch.manual_seed(17)
    balance_q = torch.randn_like(q) * 1.0e-3
    balance_v = torch.randn_like(v) * 1.0e-3
    balance_acc = grid.acceleration(balance_q, coupling)
    core = grid.r2 + grid.axial[None, :].square() < CORE_RADIUS * CORE_RADIUS
    analytic = local_balances(grid, balance_q, balance_v, balance_acc, coupling, core)
    balance_step = 1.0e-6
    plus_energy = float(cell_energy(grid, balance_q + balance_step * balance_v, balance_v + balance_step * balance_acc, coupling)[core].sum())
    minus_energy = float(cell_energy(grid, balance_q - balance_step * balance_v, balance_v - balance_step * balance_acc, coupling)[core].sum())
    finite_energy = (plus_energy - minus_energy) / (2.0 * balance_step)
    plus_rho = -2.0 * A * ((balance_q[1] + balance_step * balance_v[1]) * (balance_v[2] + balance_step * balance_acc[2]) - (balance_q[2] + balance_step * balance_v[2]) * (balance_v[1] + balance_step * balance_acc[1]))
    minus_rho = -2.0 * A * ((balance_q[1] - balance_step * balance_v[1]) * (balance_v[2] - balance_step * balance_acc[2]) - (balance_q[2] - balance_step * balance_v[2]) * (balance_v[1] - balance_step * balance_acc[1]))
    finite_charge = float((grid.volume * (plus_rho - minus_rho) * core).sum()) / (2.0 * balance_step)
    assert abs(finite_energy - analytic["core_energy_derivative"]) / max(1.0, abs(finite_energy), abs(analytic["core_energy_derivative"])) < 1.0e-6
    assert abs(finite_charge - analytic["core_charge_derivative"]) / max(1.0, abs(finite_charge), abs(analytic["core_charge_derivative"])) < 1.0e-6

    source_paths = (SELF, PREREG, NEUTRAL_SOURCE, CLOUD_SOURCE, VERIFIER_SOURCE)
    source_identity = {path.relative_to(ROOT).as_posix(): sha256(path) for path in source_paths}
    assert all(path.is_file() and len(source_identity[path.relative_to(ROOT).as_posix()]) == 64 for path in source_paths)
    reference = ROOT / "runs" / "20260911_matter_formation_minimum_droplet" / "stationary" / "q16_S1_c1p2.json"
    reference_archive = reference.with_suffix(".npz")
    reference_record = json.loads(reference.read_text(encoding="utf-8"))
    assert reference_record["stationary"] is True and reference_record["binding_witness"] is True
    assert reference_record["archive_sha256"] == sha256(reference_archive)
    print(json.dumps({
        "smoke": "PASS",
        "controls": ["energy_gradient", "vacuum", "charge_sign", "free_propagation", "source_identity", "stationary_reference", "local_balance"],
        "initial_energy": initial["energy"],
        "one_step_energy": current["energy"],
        "initial_overlap": metadata["initial_overlap"],
    }))
    return 0


def run_campaign(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    source_hashes = snapshot_sources(output)
    primary = output / "primary"
    primary.mkdir()
    rows: list[dict[str, Any]] = []
    for arm in BASE_ARMS:
        grid = CylindricalGrid(*GRID_SPECS["G0"][:2])
        rows.append(run_row(primary, "G0", grid, GRID_SPECS["G0"][2], arm))
    for grid_name in ("G1", "G2", "T1"):
        radius, spacing, dt = GRID_SPECS[grid_name]
        for arm in COMPARISON_ARMS:
            rows.append(run_row(primary, grid_name, CylindricalGrid(radius, spacing), dt, arm))
    indexed = {(row["grid"], row["arm"]): row for row in rows}
    comparisons: list[dict[str, Any]] = []
    for arm in COMPARISON_ARMS:
        comparisons.append(compare_rows(indexed[("G0", arm)], indexed[("G1", arm)], "space"))
        comparisons.append(compare_rows(indexed[("G0", arm)], indexed[("G2", arm)], "domain"))
        comparisons.append(compare_rows(indexed[("G0", arm)], indexed[("T1", arm)], "time"))
    coupled_candidates = [row for row in rows if row["formation"] and row["arm"] in ("pair64", "pair128", "pair256", "antiphase256")]
    fully_compared = []
    for candidate in coupled_candidates:
        candidate_comparisons = [
            item for item in comparisons
            if item["left"] == candidate["grid"] + "_" + candidate["arm"]
            or item["right"] == candidate["grid"] + "_" + candidate["arm"]
        ]
        if len(candidate_comparisons) == 3 and all(item["pass"] for item in candidate_comparisons):
            fully_compared.append(candidate)
    uncoupled = indexed.get(("G0", "uncoupled256"))
    uncoupled_failed = bool(uncoupled is not None and uncoupled["numerically_qualified"] and not uncoupled["formation"])
    comparison_pass = bool(comparisons) and len(comparisons) == len(COMPARISON_ARMS) * 3 and all(item["pass"] for item in comparisons)
    if not comparison_pass:
        verdict = "INCONCLUSIVE"
    elif fully_compared and uncoupled_failed:
        verdict = "EMERGES—conditional post-collision bound remnant"
    else:
        verdict = "DOES NOT EMERGE in the specified wave-capture calculation"
    receipt = {"schema": SCHEMA, "protocol_sha256": sha256(PREREG), "source_sha256": source_hashes, "constants": {"a": A, "c_psi": CPSI, "u_rho": URHO, "u_C": UC, "k_Cx": K, "h_C": HC, "B": B, "omega_inf": OMEGA_INF, "v_star": VSTAR}, "rows": rows, "comparisons": comparisons, "coupled_candidates": [row["grid"] + "_" + row["arm"] for row in coupled_candidates], "fully_compared_candidates": [row["grid"] + "_" + row["arm"] for row in fully_compared], "uncoupled_control_failed": uncoupled_failed, "numerical_pass": comparison_pass, "verdict": verdict, "complete_physical_matter_formation": False, "gravitational_capture_established": False, "physical_size_map_established": False, "packet_count_minimum_established": False, "library_versions": {"python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__, "device": "cuda" if torch.cuda.is_available() else "cpu"}}
    write_json(output / "result.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "20260911_matter_formation_wave_capture")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    receipt = run_campaign(args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), "verdict": receipt["verdict"], "fully_compared_candidates": receipt["fully_compared_candidates"]}))
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
