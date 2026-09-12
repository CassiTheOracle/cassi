#!/usr/bin/env python3
"""Independent verifier and RK4 reconstruction for charged-wave capture."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import tempfile
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "computations" / "matter_formation_wave_capture_v2_prereg.md"
PRIMARY_SOURCE = ROOT / "computations" / "matter_formation_wave_capture.py"
NEUTRAL_SOURCE = ROOT / "computations" / "matter_formation_neutral_packets.py"
CLOUD_SOURCE = ROOT / "computations" / "matter_formation_radial_cloud.py"
VERIFIER_SOURCE = Path(__file__).resolve()
SCHEMA = "matter-formation-wave-capture-verification-v2"
PRIMARY_SCHEMAS = ("matter-formation-wave-capture-primary-v1", "matter-formation-wave-capture-primary-v2")
A = 1.0 / 16.0
CPSI = 1.0 / 8.0
URHO = 4.0
UC = 1.0
K = 1.0
HC = 2.9598260763447164
B = 4.75
OMEGA_INF = math.sqrt(B / A)
VSTAR = math.sqrt(K / (2.0 * A))
T_FINAL = 48.0
CORE_RADIUS = 8.0
CUT_RADIUS = 8.0
CUT_WIDTH = 4.0
SHELL_RADIUS = CUT_RADIUS + CUT_WIDTH
OUTER_SHELL_WIDTH = 16.0
SAMPLE_TIMES = (0.0, 32.0, 40.0, 48.0)
ARMS = ("single256", "pair256", "antiphase256", "uncoupled256")
RECONSTRUCTION_TOL = 1.0e-8
METHOD_TOL = 0.05
ENERGY_DRIFT_TOL = 2.0e-4
CHARGE_DRIFT_TOL = 2.0e-5
LOCAL_BALANCE_TOL = 1.0e-8


class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    if not finite(value):
        raise VerificationError(f"nonfinite JSON payload: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")

def strict_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise VerificationError(f"nonfinite JSON constant {value}: {path}")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise VerificationError(f"object required: {path}")
    return value
def finite(value: Any) -> bool:
    if isinstance(value, (float, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, (int, str, bool)) or value is None:
        return True
    if isinstance(value, np.ndarray):
        return bool(np.isfinite(value).all())
    if isinstance(value, dict):
        return all(finite(key) and finite(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite(item) for item in value)
    return False


class IndependentGrid:
    def __init__(self, radius: int, spacing: float) -> None:
        self.R = int(radius)
        self.h = float(spacing)
        self.nr = int(round(self.R / self.h))
        self.nz = 2 * self.nr
        dtype = torch.float64
        device = "cuda"
        self.r = (torch.arange(self.nr, dtype=dtype, device=device) + 0.5) * self.h
        self.axial = -self.R + (torch.arange(self.nz, dtype=dtype, device=device) + 0.5) * self.h
        faces = torch.arange(self.nr + 1, dtype=dtype, device=device) * self.h
        self.volume = (math.pi * (faces[1:].square() - faces[:-1].square()) * self.h)[:, None]
        self.radial_edge = (2.0 * math.pi * faces[1:-1])[:, None]
        self.axial_edge = self.volume / self.h**2
        self.radial_boundary = 4.0 * math.pi * self.R
        self.r2 = self.r[:, None].square()

    def laplacian(self, q: torch.Tensor) -> torch.Tensor:
        result = torch.zeros_like(q)
        difference = q[:, 1:, :] - q[:, :-1, :]
        result[:, :-1, :] += difference * ((self.r + self.h / 2.0) / (self.r * self.h**2))[:-1, None]
        result[:, 1:, :] -= difference * ((self.r - self.h / 2.0) / (self.r * self.h**2))[1:, None]
        difference = (q[:, :, 1:] - q[:, :, :-1]) / self.h**2
        result[:, :, :-1] += difference
        result[:, :, 1:] -= difference
        result[:, -1, :] -= (2.0 * self.R / (self.r[-1] * self.h**2)) * q[:, -1, :]
        result[:, :, 0] -= 2.0 / self.h**2 * q[:, :, 0]
        result[:, :, -1] -= 2.0 / self.h**2 * q[:, :, -1]
        return result

    def acceleration(self, q: torch.Tensor, coupling: float) -> torch.Tensor:
        result = self.laplacian(q)
        f = q[0] + 1.0
        n = q[1].square() + q[2].square()
        coefficient = B - coupling + coupling * f.square() + UC * n
        result[0] -= URHO * (f.square() - 1.0) * f + 2.0 * coupling * f * n
        result[0] /= CPSI
        result[1:] *= K / 2.0
        result[1:] -= coefficient * q[1:]
        result[1:] /= A
        return result

    def energy(self, q: torch.Tensor, v: torch.Tensor, coupling: float) -> torch.Tensor:
        f = q[0] + 1.0
        n = q[1].square() + q[2].square()
        potential = URHO / 4.0 * (f.square() - 1.0).square() + (B - coupling + coupling * f.square()) * n + UC / 2.0 * n.square()
        kinetic = CPSI / 2.0 * v[0].square() + A * (v[1].square() + v[2].square())
        radial = ((q[:, 1:, :] - q[:, :-1, :]).square() * self.radial_edge).sum()
        axial = ((q[:, :, 1:] - q[:, :, :-1]).square() * self.axial_edge).sum()
        boundary_r = self.radial_boundary * q[:, -1, :].square().sum()
        boundary_z = (2.0 * self.axial_edge[:, 0] * (q[:, :, 0].square() + q[:, :, -1].square())).sum()
        gradient = (radial + axial + boundary_r + boundary_z) / 2.0
        # The carrier gradient is K times the first component's gradient.
        carrier_gradient = ((q[1:, 1:, :] - q[1:, :-1, :]).square() * self.radial_edge).sum()
        carrier_gradient += ((q[1:, :, 1:] - q[1:, :, :-1]).square() * self.axial_edge).sum()
        carrier_gradient += self.radial_boundary * q[1:, -1, :].square().sum()
        carrier_gradient += (2.0 * self.axial_edge[:, 0] * (q[1:, :, 0].square() + q[1:, :, -1].square())).sum()
        gradient = gradient + (K - 1.0) * carrier_gradient / 2.0
        return ((potential + kinetic) * self.volume).sum() + gradient
    def axial_derivative(self, value: torch.Tensor) -> torch.Tensor:
        result = torch.empty_like(value)
        result[..., 1:-1] = (value[..., 2:] - value[..., :-2]) / (2.0 * self.h)
        result[..., 0] = (value[..., 1] - value[..., 0]) / self.h
        result[..., -1] = (value[..., -1] - value[..., -2]) / self.h
        return result



def cut(distance: torch.Tensor) -> torch.Tensor:
    s = torch.clamp((distance - CUT_RADIUS) / CUT_WIDTH, 0.0, 1.0)
    return 1.0 - 3.0 * s.square() + 2.0 * s.pow(3)


def potential_gradient(q: torch.Tensor, coupling: float) -> torch.Tensor:
    f = q[0] + 1.0
    n = q[1].square() + q[2].square()
    coefficient = B - coupling + coupling * f.square() + UC * n
    result = torch.empty_like(q)
    result[0] = URHO * (f.square() - 1.0) * f + 2.0 * coupling * f * n
    result[1:] = 2.0 * coefficient * q[1:]
    return result


def cell_energy(grid: IndependentGrid, q: torch.Tensor, v: torch.Tensor, coupling: float) -> torch.Tensor:
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


def local_balances(
    grid: IndependentGrid,
    q: torch.Tensor,
    v: torch.Tensor,
    acc: torch.Tensor,
    coupling: float,
    core_mask: torch.Tensor,
) -> dict[str, float]:
    gradient_coeff = torch.as_tensor((1.0, K, K), dtype=q.dtype, device=q.device)[:, None, None]
    mass_coeff = torch.as_tensor((CPSI, 2.0 * A, 2.0 * A), dtype=q.dtype, device=q.device)[:, None, None]
    local = mass_coeff * grid.volume * v * acc + grid.volume * potential_gradient(q, coupling) * v
    edge_derivative = torch.zeros_like(q[0])
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

    edge_derivative[-1, :] += grid.radial_boundary * (
        q[0, -1, :] * v[0, -1, :] + K * q[1, -1, :] * v[1, -1, :] + K * q[2, -1, :] * v[2, -1, :])
    edge_derivative[:, 0] += 2.0 * grid.axial_edge[:, 0] * (
        q[0, :, 0] * v[0, :, 0] + K * q[1, :, 0] * v[1, :, 0] + K * q[2, :, 0] * v[2, :, 0])
    edge_derivative[:, -1] += 2.0 * grid.axial_edge[:, 0] * (
        q[0, :, -1] * v[0, :, -1] + K * q[1, :, -1] * v[1, :, -1] + K * q[2, :, -1] * v[2, :, -1])
    energy_derivative = float(((local.sum(dim=0) + edge_derivative) * core_mask).sum())
    charge_derivative = float((grid.volume * (-2.0 * A * (q[1] * acc[2] - q[2] * acc[1])) * core_mask).sum())
    return {
        "core_energy_derivative": energy_derivative,
        "core_energy_flux": float(energy_flux),
        "core_energy_balance_error": abs(energy_derivative + float(energy_flux)) / max(1.0, abs(energy_derivative), abs(float(energy_flux))),
        "core_charge_derivative": charge_derivative,
        "core_charge_flux": float(charge_flux),
        "core_charge_balance_error": abs(charge_derivative + float(charge_flux)) / max(1.0, abs(charge_derivative), abs(float(charge_flux))),
    }


def metric(
    grid: IndependentGrid,
    q: torch.Tensor,
    v: torch.Tensor,
    coupling: float,
    charge_reference: float,
    energy_reference: float,
) -> dict[str, float | None]:
    rho = -2.0 * A * (q[1] * v[2] - q[2] * v[1])
    abs_rho = rho.abs()
    total = float((grid.volume * rho).sum())
    abs_total = float((grid.volume * abs_rho).sum())
    center = float((grid.volume * abs_rho * grid.axial[None, :]).sum()) / max(abs_total, 1.0e-30)
    distance2 = grid.r2 + grid.axial[None, :].square()
    core = distance2 < CORE_RADIUS**2
    core_charge = float((grid.volume * rho * core).sum())
    core_abs = float((grid.volume * abs_rho * core).sum())
    core_rms = math.sqrt(max(0.0, float((grid.volume * abs_rho * distance2 * core).sum()) / max(core_abs, 1.0e-30)))
    core_f2 = float((grid.volume * abs_rho * (q[0] + 1.0).square() * core).sum()) / max(core_abs, 1.0e-30)
    smooth = cut(torch.sqrt(distance2))
    cut_q, cut_v = smooth * q, smooth * v
    cut_energy = float(grid.energy(cut_q, cut_v, coupling))
    cut_charge = float((grid.volume * rho * smooth.square()).sum())
    dz = grid.axial_derivative(cut_q)
    momentum = -float((grid.volume * (CPSI * cut_v[0] * dz[0] + 2.0 * A * (cut_v[1] * dz[1] + cut_v[2] * dz[2]))).sum())
    radicand = cut_energy * cut_energy - (VSTAR * momentum) ** 2
    binding: float | None = None
    if cut_charge != 0.0 and radicand >= 0.0:
        binding = math.sqrt(radicand) / (OMEGA_INF * abs(cut_charge))
    allocated = cell_energy(grid, q, v, coupling)
    shell = (distance2 >= CUT_RADIUS**2) & (distance2 < SHELL_RADIUS**2)
    boundary = (grid.r[:, None] >= grid.R - OUTER_SHELL_WIDTH) | (torch.abs(grid.axial[None, :]) >= grid.R - OUTER_SHELL_WIDTH)
    energy = float(grid.energy(q, v, coupling))
    balances = local_balances(grid, q, v, grid.acceleration(q, coupling), coupling, core)
    return {
        "energy": energy,
        "charge": total,
        "abs_charge": abs_total,
        "center": center,
        "core_charge": core_charge,
        "core_abs_charge": core_abs,
        "core_fraction": core_charge / charge_reference if abs(charge_reference) > 1.0e-30 else None,
        "core_rms": core_rms,
        "core_f2": core_f2,
        "mediator_depletion": 1.0 - core_f2,
        "core_energy": float((allocated * core).sum()),
        "cut_energy": cut_energy,
        "cut_charge": cut_charge,
        "momentum": momentum,
        "radicand": radicand,
        "binding_ratio": binding,
        "shell_energy": float((allocated * shell).sum()),
        "shell_energy_fraction": float((allocated * shell).sum()) / max(abs(energy_reference), 1.0e-30),
        "boundary_energy": float((allocated * boundary).sum()),
        "boundary_energy_fraction": float((allocated * boundary).sum()) / max(abs(energy_reference), 1.0e-30),
        **balances,
    }


def initial(grid: IndependentGrid, arm: str) -> tuple[torch.Tensor, torch.Tensor, float, float]:
    pair = arm != "single256"
    uncoupled = arm == "uncoupled256"
    charge = 256.0
    omega = OMEGA_INF if not pair else math.sqrt(OMEGA_INF**2 + 8.0)
    if not pair:
        envelope = torch.exp(-(grid.r2 + grid.axial[None, :].square()) / 32.0)
        z = envelope.to(torch.complex128)
    else:
        right = torch.exp(-(grid.r2 + (grid.axial[None, :] + 12.0).square()) / 32.0)
        left = torch.exp(-(grid.r2 + (grid.axial[None, :] - 12.0).square()) / 32.0)
        phase_right = grid.axial[None, :] + 12.0
        phase_left = -(grid.axial[None, :] - 12.0)
        if arm == "outgoing256":
            phase_right = -phase_right
            phase_left = -phase_left
        sign = -1.0 if arm == "antiphase256" else 1.0
        z = right * torch.exp(1j * phase_right) + sign * left * torch.exp(1j * phase_left)
    norm = torch.sum(grid.volume * (z.real.square() + z.imag.square()))
    z = z * math.sqrt(charge / (2.0 * A * omega * float(norm)))
    q = torch.zeros((3, grid.nr, grid.nz), dtype=torch.float64, device="cuda")
    q[1], q[2] = z.real, z.imag
    v = torch.zeros_like(q)
    v[1], v[2] = omega * q[2], -omega * q[1]
    return q, v, (0.0 if uncoupled else HC), charge


def rk4_step(grid: IndependentGrid, q: torch.Tensor, v: torch.Tensor, dt: float, coupling: float) -> tuple[torch.Tensor, torch.Tensor]:
    kq1, kv1 = v, grid.acceleration(q, coupling)
    q2, v2 = q + 0.5 * dt * kq1, v + 0.5 * dt * kv1
    kq2, kv2 = v2, grid.acceleration(q2, coupling)
    q3, v3 = q + 0.5 * dt * kq2, v + 0.5 * dt * kv2
    kq3, kv3 = v3, grid.acceleration(q3, coupling)
    q4, v4 = q + dt * kq3, v + dt * kv3
    kq4, kv4 = v4, grid.acceleration(q4, coupling)
    return q + dt * (kq1 + 2.0 * kq2 + 2.0 * kq3 + kq4) / 6.0, v + dt * (kv1 + 2.0 * kv2 + 2.0 * kv3 + kv4) / 6.0


def _write_independent_state(
    archive_dir: Path,
    arm: str,
    grid: IndependentGrid,
    q: torch.Tensor,
    v: torch.Tensor,
    time_value: float,
) -> dict[str, str | float]:
    path = archive_dir / f"{arm}_t{int(round(time_value)):03d}.npz"
    with path.open("xb") as stream:
        np.savez_compressed(
            stream,
            fields=q.detach().cpu().numpy(),
            velocities=v.detach().cpu().numpy(),
            r=grid.r.detach().cpu().numpy(),
            axial=grid.axial.detach().cpu().numpy(),
            volume=grid.volume.detach().cpu().numpy(),
            time=np.asarray(time_value),
        )
    return {"path": path.name, "sha256": sha256(path), "time": float(time_value)}


def independent_evolution(
    arm: str,
    radius: int,
    spacing: float,
    dt: float,
    archive_dir: Path,
) -> dict[str, Any]:
    grid = IndependentGrid(radius, spacing)
    q, v, coupling, charge = initial(grid, arm)
    initial_rho = -2.0 * A * (q[1] * v[2] - q[2] * v[1])
    charge_reference = float((grid.volume * initial_rho).sum())
    energy_reference = float(grid.energy(q, v, coupling))
    results = {0.0: metric(grid, q, v, coupling, charge_reference, energy_reference)}
    states = [_write_independent_state(archive_dir, arm, grid, q, v, 0.0)]
    targets = {int(round(t / dt)): t for t in SAMPLE_TIMES[1:]}
    for step in range(1, int(round(T_FINAL / dt)) + 1):
        q, v = rk4_step(grid, q, v, dt, coupling)
        if step in targets:
            t = targets[step]
            results[t] = metric(grid, q, v, coupling, charge_reference, energy_reference)
            states.append(_write_independent_state(archive_dir, arm, grid, q, v, t))
    if len(results) != len(SAMPLE_TIMES) or len(states) != len(SAMPLE_TIMES):
        raise VerificationError(f"independent evolution missed snapshot for {arm}")
    energy_drift = max(abs(float(values["energy"]) - energy_reference) for values in results.values()) / max(1.0, abs(energy_reference))
    charge_drift = max(abs(float(values["charge"]) - charge_reference) for values in results.values()) / max(1.0, abs(charge_reference))
    finite_snapshots = all(finite(values) for values in results.values())
    return {
        "arm": arm,
        "grid": radius,
        "spacing": spacing,
        "dt": dt,
        "charge_reference": charge_reference,
        "energy_reference": energy_reference,
        "snapshots": results,
        "states": states,
        "energy_drift": energy_drift,
        "charge_drift": charge_drift,
        "finite_snapshots": finite_snapshots,
        "conservation_pass": bool(finite_snapshots and energy_drift <= ENERGY_DRIFT_TOL and charge_drift <= CHARGE_DRIFT_TOL),
        "raw_state_archive_complete": False,
    }


def _state_path(root: Path, state: dict[str, Any]) -> Path:
    relative = Path(str(state["path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise VerificationError("state path escapes primary archive")
    primary = (root / "primary").resolve()
    path = (primary / relative).resolve()
    try:
        path.relative_to(primary)
    except ValueError as error:
        raise VerificationError("state path escapes primary archive") from error
    return path


def _independent_state_path(archive_dir: Path, state: dict[str, Any]) -> Path:
    relative = Path(str(state["path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise VerificationError("independent state path escapes archive")
    root = archive_dir.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise VerificationError("independent state path escapes archive") from error
    return path


def _validate_independent_state(archive_dir: Path, item: dict[str, Any], state: dict[str, Any]) -> None:
    state_path = _independent_state_path(archive_dir, state)
    if not state_path.is_file():
        raise VerificationError(f"missing independent state: {state_path}")
    expected_hash = state.get("sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise VerificationError(f"independent state hash missing: {state_path.name}")
    if sha256(state_path) != expected_hash:
        raise VerificationError(f"independent state hash mismatch: {state_path.name}")
    with np.load(state_path, allow_pickle=False) as data:
        required = {"fields", "velocities", "r", "axial", "volume", "time"}
        if set(data.files) != required:
            raise VerificationError(f"independent state fields mismatch: {state_path.name}")
        fields_raw = np.array(data["fields"], copy=True)
        velocities_raw = np.array(data["velocities"], copy=True)
        r = np.array(data["r"], copy=True)
        axial = np.array(data["axial"], copy=True)
        volume = np.array(data["volume"], copy=True)
        embedded_time = float(np.asarray(data["time"]).reshape(()))
    radius = int(item["grid"])
    spacing = float(item["spacing"])
    nr = int(round(radius / spacing))
    nz = 2 * nr
    if fields_raw.dtype != np.float64 or velocities_raw.dtype != np.float64:
        raise VerificationError(f"independent state dtype mismatch: {state_path.name}")
    if fields_raw.shape != (3, nr, nz) or velocities_raw.shape != fields_raw.shape:
        raise VerificationError(f"independent state shape mismatch: {state_path.name}")
    if r.shape != (nr,) or axial.shape != (nz,) or volume.shape != (nr, 1):
        raise VerificationError(f"independent state geometry shape mismatch: {state_path.name}")
    arrays = (fields_raw, velocities_raw, r, axial, volume, np.asarray(embedded_time))
    if not all(np.isfinite(array).all() for array in arrays):
        raise VerificationError(f"nonfinite independent state: {state_path.name}")
    expected_r = (np.arange(nr, dtype=np.float64) + 0.5) * spacing
    expected_axial = -radius + (np.arange(nz, dtype=np.float64) + 0.5) * spacing
    faces = np.arange(nr + 1, dtype=np.float64) * spacing
    expected_volume = (math.pi * (faces[1:] ** 2 - faces[:-1] ** 2) * spacing)[:, None]
    if not np.allclose(r, expected_r, rtol=0.0, atol=1.0e-12):
        raise VerificationError(f"independent radial coordinate mismatch: {state_path.name}")
    if not np.allclose(axial, expected_axial, rtol=0.0, atol=1.0e-12):
        raise VerificationError(f"independent axial coordinate mismatch: {state_path.name}")
    if not np.allclose(volume, expected_volume, rtol=0.0, atol=1.0e-12):
        raise VerificationError(f"independent volume mismatch: {state_path.name}")
    if abs(embedded_time - float(state["time"])) > 1.0e-12:
        raise VerificationError(f"independent time mismatch: {state_path.name}")


def _validate_independent_archive(archive_dir: Path, independent: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]]]:
    details: list[dict[str, Any]] = []
    complete = bool(independent)
    for item in independent:
        states = item.get("states", [])
        errors: list[str] = []
        if not isinstance(states, list) or len(states) != len(SAMPLE_TIMES):
            errors.append("independent snapshot count")
            states = states if isinstance(states, list) else []
        times = [state.get("time") for state in states if isinstance(state, dict)]
        if {float(value) for value in times if value is not None} != set(SAMPLE_TIMES):
            errors.append("independent snapshot time coverage")
        for state in states:
            if not isinstance(state, dict):
                errors.append("independent state metadata")
                continue
            try:
                _validate_independent_state(archive_dir, item, state)
            except (KeyError, OSError, ValueError, VerificationError) as error:
                errors.append(str(error))
        passed = not errors
        item["raw_state_archive_complete"] = passed
        details.append({"arm": item.get("arm"), "states": len(states), "errors": errors, "pass": passed})
        complete = complete and passed
    return complete, details


def _validate_state_archive(root: Path, row: dict[str, Any], state: dict[str, Any]) -> tuple[IndependentGrid, torch.Tensor, torch.Tensor]:
    state_path = _state_path(root, state)
    if not state_path.is_file():
        raise VerificationError(f"missing state: {state_path}")
    expected_hash = state.get("sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise VerificationError(f"state hash missing: {state_path.name}")
    if sha256(state_path) != expected_hash:
        raise VerificationError(f"state hash mismatch: {state_path.name}")
    with np.load(state_path, allow_pickle=False) as data:
        required = {"fields", "velocities", "r", "axial", "volume", "time"}
        if set(data.files) != required:
            raise VerificationError(f"state fields mismatch: {state_path.name}")
        fields_raw = np.asarray(data["fields"])
        velocities_raw = np.asarray(data["velocities"])
        r = np.asarray(data["r"])
        axial = np.asarray(data["axial"])
        volume = np.asarray(data["volume"])
        embedded_time = float(np.asarray(data["time"]).reshape(()))
    radius = int(row["R"])
    spacing = float(row["spacing"])
    nr = int(round(radius / spacing))
    nz = 2 * nr
    if fields_raw.dtype != np.float64 or velocities_raw.dtype != np.float64:
        raise VerificationError(f"state dtype mismatch: {state_path.name}")
    if fields_raw.shape != (3, nr, nz) or velocities_raw.shape != fields_raw.shape:
        raise VerificationError(f"state shape mismatch: {state_path.name}")
    if r.shape != (nr,) or axial.shape != (nz,) or volume.shape != (nr, 1):
        raise VerificationError(f"state geometry shape mismatch: {state_path.name}")
    arrays = (fields_raw, velocities_raw, r, axial, volume, np.asarray(embedded_time))
    if not all(np.isfinite(array).all() for array in arrays):
        raise VerificationError(f"nonfinite state: {state_path.name}")
    expected_r = (np.arange(nr, dtype=np.float64) + 0.5) * spacing
    expected_axial = -radius + (np.arange(nz, dtype=np.float64) + 0.5) * spacing
    faces = np.arange(nr + 1, dtype=np.float64) * spacing
    expected_volume = (math.pi * (faces[1:] ** 2 - faces[:-1] ** 2) * spacing)[:, None]
    if not np.allclose(r, expected_r, rtol=0.0, atol=1.0e-12):
        raise VerificationError(f"radial coordinate mismatch: {state_path.name}")
    if not np.allclose(axial, expected_axial, rtol=0.0, atol=1.0e-12):
        raise VerificationError(f"axial coordinate mismatch: {state_path.name}")
    if not np.allclose(volume, expected_volume, rtol=0.0, atol=1.0e-12):
        raise VerificationError(f"volume mismatch: {state_path.name}")
    if abs(embedded_time - float(state["time"])) > 1.0e-12:
        raise VerificationError(f"embedded time mismatch: {state_path.name}")
    grid = IndependentGrid(radius, spacing)
    return grid, torch.as_tensor(fields_raw, dtype=torch.float64, device="cuda"), torch.as_tensor(velocities_raw, dtype=torch.float64, device="cuda")


def primary_snapshot_metric(root: Path, row: dict[str, Any], state: dict[str, Any]) -> dict[str, float | None]:
    grid, q, v = _validate_state_archive(root, row, state)
    initial = row.get("initial", {})
    return metric(
        grid,
        q,
        v,
        float(row["coupling"]),
        float(initial["charge"]),
        float(initial["energy"]),
    )


def _real_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    try:
        left_float, right_float = float(left), float(right)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(left_float) or not math.isfinite(right_float):
        return False
    return abs(left_float - right_float) <= RECONSTRUCTION_TOL * max(1.0, abs(left_float), abs(right_float))


def verify_primary_rows(root: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    hash_attempted = hash_passed = reconstruction_attempted = reconstruction_passed = 0
    expected_trace_length = int(round(T_FINAL / 0.5)) + 1
    expected_state_times = set(SAMPLE_TIMES)
    for row in receipt.get("rows", []):
        row_hash_passed = 0
        row_hash_attempted = 0
        checks: list[bool] = []
        failures: list[str] = []
        trace = row.get("trace", [])
        row_times = row.get("times", [])
        coverage = len(trace) == expected_trace_length and len(row_times) == expected_trace_length and np.allclose(
            np.asarray(row_times, dtype=np.float64),
            np.arange(expected_trace_length, dtype=np.float64) * 0.5,
            rtol=0.0,
            atol=1.0e-12,
        )
        state_times = {float(state.get("time", math.nan)) for state in row.get("states", [])}
        if state_times != expected_state_times:
            coverage = False
            failures.append("snapshot time coverage")
        for state in row.get("states", []):
            hash_attempted += 1
            row_hash_attempted += 1
            t = float(state["time"])
            index = int(round(t / 0.5))
            if index >= len(trace):
                failures.append(f"trace missing state time {t}")
                continue
            try:
                grid, q, v = _validate_state_archive(root, row, state)
                row_hash_passed += 1
                del grid, q, v
                hash_passed += 1
                rebuilt = primary_snapshot_metric(root, row, state)
            except (KeyError, OSError, ValueError, VerificationError) as error:
                failures.append(str(error))
                continue
            observed = trace[index]
            names = (
                "energy", "charge", "core_fraction", "core_rms", "binding_ratio",
                "shell_energy_fraction", "core_energy", "mediator_depletion",
                "core_energy_balance_error", "core_charge_balance_error",
            )
            for name in names:
                reconstruction_attempted += 1
                passed = _real_equal(rebuilt.get(name), observed.get(name))
                reconstruction_passed += int(passed)
                checks.append(passed)
                if not passed:
                    failures.append(f"{state['path']}:{name}")
        details.append({
            "key": row["grid"] + "_" + row["arm"],
            "coverage_pass": coverage,
            "hash_checks": row_hash_attempted,
            "hash_passed": row_hash_passed,
            "reconstruction_checks": len(checks),
            "reconstruction_passed": sum(checks),
            "failures": failures,
            "pass": bool(coverage and checks and all(checks) and len(failures) == 0),
        })
    return {
        "details": details,
        "hash_checks_attempted": hash_attempted,
        "hash_checks_passed": hash_passed,
        "reconstruction_checks_attempted": reconstruction_attempted,
        "reconstruction_checks_passed": reconstruction_passed,
        "pass": bool(details and all(item["pass"] for item in details)),
    }


def mutation_control(root: Path, row: dict[str, Any]) -> bool:
    state = row["states"][0]
    grid, original_q, velocity_tensor = _validate_state_archive(root, row, state)
    original_fields = original_q.detach().cpu().numpy()
    before_energy = float(grid.energy(original_q, velocity_tensor, float(row["coupling"])))
    mutated_fields = np.array(original_fields, copy=True)
    mutated_fields[0, 0, 0] += 0.1
    mutated_q = torch.as_tensor(mutated_fields, dtype=torch.float64, device="cuda")
    after_energy = float(grid.energy(mutated_q, velocity_tensor, float(row["coupling"])))
    rejected_by_reconstruction = abs(after_energy - before_energy) > 1.0e-8
    rejected_against_receipt = abs(after_energy - float(row["trace"][0]["energy"])) > 1.0e-8
    return bool(not np.array_equal(mutated_fields, original_fields) and rejected_by_reconstruction and rejected_against_receipt)


def _archived_source_checks(input_dir: Path, receipt: dict[str, Any]) -> dict[str, bool]:
    required = (
        PREREG,
        PRIMARY_SOURCE,
        NEUTRAL_SOURCE,
        CLOUD_SOURCE,
        VERIFIER_SOURCE,
    )
    recorded = receipt.get("source_sha256", {})
    checks: dict[str, bool] = {
        "protocol_live": receipt.get("protocol_sha256") == sha256(PREREG),
    }
    for path in required:
        key = path.relative_to(ROOT).as_posix()
        archived = input_dir / "sources" / key.replace("/", "__")
        expected = recorded.get(key)
        present = archived.is_file()
        archive_hash = sha256(archived) if present else ""
        checks[key] = bool(present and isinstance(expected, str) and archive_hash == expected)
        checks[f"live_{key}"] = bool(checks[key] and sha256(path) == archive_hash)
    checks["archive_bytes"] = bool(all(checks[key] for key in checks if key != "protocol_live" and not key.startswith("live_")))
    checks["live_source_bytes"] = bool(all(checks[key] for key in checks if key.startswith("live_")))
    return checks


def _corrupted_hash_control(input_dir: Path, receipt: dict[str, Any]) -> bool:
    mutated = copy.deepcopy(receipt)
    row = next(row for row in mutated.get("rows", []) if row.get("grid") == "G0" and row.get("arm") == "pair256")
    row["states"][0]["sha256"] = "0" * 64
    details = verify_primary_rows(input_dir, mutated)
    return bool(not details["pass"] and any("hash mismatch" in failure for item in details["details"] for failure in item["failures"]))


def _legacy_independent(input_dir: Path) -> list[dict[str, Any]]:
    path = input_dir / "verification.json"
    if not path.is_file():
        return []
    saved = strict_json(path)
    return [item for item in saved.get("independent_evolution", []) if isinstance(item, dict)]


def _preserved_independent_summary(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for item in items:
        snapshots = item.get("snapshots", {})
        numeric = [values for values in snapshots.values() if isinstance(values, dict)]
        energy_values = [float(values["energy"]) for values in numeric if "energy" in values and math.isfinite(float(values["energy"]))]
        charge_values = [float(values["charge"]) for values in numeric if "charge" in values and math.isfinite(float(values["charge"]))]
        energy_reference = energy_values[0] if energy_values else None
        charge_reference = charge_values[0] if charge_values else None
        energy_drift = (
            max(abs(value - float(energy_reference)) for value in energy_values) / max(1.0, abs(float(energy_reference)))
            if energy_reference is not None else None
        )
        charge_drift = (
            max(abs(value - float(charge_reference)) for value in charge_values) / max(1.0, abs(float(charge_reference)))
            if charge_reference is not None else None
        )
        finite_snapshots = bool(numeric) and all(finite(values) for values in numeric)
        summaries.append({
            "arm": item.get("arm"),
            "grid": item.get("grid"),
            "spacing": item.get("spacing"),
            "dt": item.get("dt"),
            "charge_reference": charge_reference,
            "energy_reference": energy_reference,
            "snapshots": snapshots,
            "energy_drift": energy_drift,
            "charge_drift": charge_drift,
            "finite_snapshots": finite_snapshots,
            "conservation_pass": bool(
                finite_snapshots
                and energy_drift is not None
                and charge_drift is not None
                and energy_drift <= ENERGY_DRIFT_TOL
                and charge_drift <= CHARGE_DRIFT_TOL
            ),
            "raw_state_archive_complete": False,
            "source": "preserved legacy verification.json",
        })
    return summaries


def _method_comparison(primary_row: dict[str, Any] | None, independent: dict[str, Any]) -> dict[str, Any]:
    arm = independent.get("arm")
    result: dict[str, Any] = {"arm": arm, "errors": {}, "failures": [], "pass": False}
    if primary_row is None:
        result["failures"].append("primary T1 row missing")
        return result
    names = ("energy", "charge", "core_fraction", "core_rms", "binding_ratio", "shell_energy_fraction", "core_energy", "mediator_depletion")
    snapshots = independent.get("snapshots", {})
    for time_value in SAMPLE_TIMES:
        values = snapshots.get(str(time_value), snapshots.get(time_value))
        index = int(round(time_value / 0.5))
        if not isinstance(values, dict) or index >= len(primary_row.get("trace", [])):
            result["failures"].append(f"missing snapshot {time_value}")
            continue
        observed = primary_row["trace"][index]
        for name in names:
            observed_value = observed.get(name)
            rebuilt_value = values.get(name)
            if observed_value is None or rebuilt_value is None:
                result["failures"].append(f"{time_value}:{name} missing or invalid")
                continue
            try:
                observed_float, rebuilt_float = float(observed_value), float(rebuilt_value)
            except (TypeError, ValueError):
                result["failures"].append(f"{time_value}:{name} nonnumeric")
                continue
            if not math.isfinite(observed_float) or not math.isfinite(rebuilt_float):
                result["failures"].append(f"{time_value}:{name} nonfinite")
                continue
            result["errors"][f"{time_value}:{name}"] = abs(observed_float - rebuilt_float) / max(1.0, abs(observed_float), abs(rebuilt_float))
    result["pass"] = bool(result["errors"]) and not result["failures"] and max(result["errors"].values()) < METHOD_TOL
    return result


def run(input_dir: Path, output_path: Path, replay_only: bool = False) -> dict[str, Any]:
    if output_path.exists():
        raise VerificationError(f"refusing to overwrite existing verifier output: {output_path}")
    receipt = strict_json(input_dir / "result.json")
    primary_schema = receipt.get("schema")
    if primary_schema not in PRIMARY_SCHEMAS:
        raise VerificationError("primary schema mismatch")
    if primary_schema == "matter-formation-wave-capture-primary-v1" and not replay_only:
        raise VerificationError("legacy v1 receipt requires explicit --replay-only")
    source_checks = _archived_source_checks(input_dir, receipt)
    snapshot_details = verify_primary_rows(input_dir, receipt)
    base_row = next((row for row in receipt.get("rows", []) if row.get("grid") == "G0" and row.get("arm") == "pair256"), None)
    if base_row is None:
        raise VerificationError("G0 pair256 row missing")
    mutation = mutation_control(input_dir, base_row)
    corrupted_hash_rejected = _corrupted_hash_control(input_dir, receipt)

    if replay_only:
        independent = _preserved_independent_summary(_legacy_independent(input_dir))
        archive_validation = [{
            "arm": item.get("arm"),
            "states": 0,
            "errors": ["preserved legacy verification has no independent raw-state archive"],
            "pass": False,
        } for item in independent]
        independent_complete = False
    else:
        archive_dir = output_path.parent / f"{output_path.stem}_independent_states"
        if archive_dir.exists():
            raise VerificationError(f"refusing to overwrite independent archive: {archive_dir}")
        archive_dir.mkdir(parents=True, exist_ok=False)
        independent = []
        for arm in ARMS:
            evolved = independent_evolution(arm, 192, 0.5, 1.0 / 128.0, archive_dir)
            independent.append({
                **evolved,
                "snapshots": {str(t): values for t, values in evolved["snapshots"].items()},
                "source": "fresh independent RK4 integration",
            })
        independent_complete, archive_validation = _validate_independent_archive(archive_dir, independent)
    rows_by_arm = {row.get("arm"): row for row in receipt.get("rows", []) if row.get("grid") == "T1"}
    method_comparisons = [_method_comparison(rows_by_arm.get(item.get("arm")), item) for item in independent]
    conservation_checks = [{
        "arm": item.get("arm"),
        "energy_drift": item.get("energy_drift"),
        "charge_drift": item.get("charge_drift"),
        "pass": bool(item.get("conservation_pass", False)),
        "raw_state_archive_complete": bool(item.get("raw_state_archive_complete", False)),
    } for item in independent]
    primary_comparisons = receipt.get("comparisons", [])
    primary_comparison_pass = bool(
        receipt.get("numerical_pass") is True
        and isinstance(primary_comparisons, list)
        and len(primary_comparisons) == len(ARMS) * 3
        and all(isinstance(item, dict) and item.get("pass") is True for item in primary_comparisons)
    )
    result = {
        "schema": SCHEMA,
        "primary": str(input_dir),
        "primary_schema": primary_schema,
        "replay_only": replay_only,
        "source_checks": source_checks,
        "snapshot_details": snapshot_details,
        "rejection_control_mutated_state_rejected": mutation,
        "rejection_control_corrupted_hash_rejected": corrupted_hash_rejected,
        "independent_evolution": independent,
        "independent_archive_validation": archive_validation,
        "conservation_checks": conservation_checks,
        "method_comparisons": method_comparisons,
        "primary_comparison_pass": primary_comparison_pass,
        "independent_raw_archive_complete": independent_complete,
        "scalar_snapshot_comparison_pass": bool(method_comparisons and all(item["pass"] for item in method_comparisons)),
        "independent_conservation_pass": bool(conservation_checks and all(item["pass"] for item in conservation_checks)),
        "complete_physical_matter_formation": False,
        "gravitational_capture_established": False,
        "physical_size_map_established": False,
        "packet_count_minimum_established": False,
    }
    result["numeric_pass"] = bool(
        primary_schema == "matter-formation-wave-capture-primary-v2"
        and all(source_checks.values())
        and snapshot_details["pass"]
        and primary_comparison_pass
        and mutation
        and corrupted_hash_rejected
        and result["scalar_snapshot_comparison_pass"]
        and result["independent_conservation_pass"]
        and independent_complete
    )
    write_json(output_path, result)
    return result


def run_smoke() -> int:
    grid = IndependentGrid(16, 1.0)
    q, v, coupling, _ = initial(grid, "pair256")
    charge_reference = float((grid.volume * (-2.0 * A * (q[1] * v[2] - q[2] * v[1]))).sum())
    energy_reference = float(grid.energy(q, v, coupling))
    assert abs(float(cut(torch.tensor(8.0, device=q.device))) - 1.0) < 1.0e-14
    assert abs(float(cut(torch.tensor(12.0, device=q.device))) - 0.0) < 1.0e-14
    vacuum = torch.zeros_like(q)
    assert torch.count_nonzero(grid.acceleration(vacuum, coupling)) == 0

    conjugate_q, conjugate_v = q.clone(), v.clone()
    conjugate_q[2].neg_()
    conjugate_v[2].neg_()
    original_energy = float(grid.energy(q, v, coupling))
    conjugate_energy = float(grid.energy(conjugate_q, conjugate_v, coupling))
    original_charge = float((grid.volume * (-2.0 * A * (q[1] * v[2] - q[2] * v[1]))).sum())
    conjugate_charge = float((grid.volume * (-2.0 * A * (conjugate_q[1] * conjugate_v[2] - conjugate_q[2] * conjugate_v[1]))).sum())
    assert abs(original_energy - conjugate_energy) < 1.0e-8
    assert abs(original_charge + conjugate_charge) < 1.0e-8

    probe = torch.zeros_like(q)
    probe[0, 2, 3] = 0.1
    probe_acc = grid.acceleration(probe, coupling)
    epsilon = 1.0e-6
    plus, minus = probe.clone(), probe.clone()
    plus[0, 2, 3] += epsilon
    minus[0, 2, 3] -= epsilon
    finite_gradient = float((grid.energy(plus, torch.zeros_like(v), coupling) - grid.energy(minus, torch.zeros_like(v), coupling)) / (2.0 * epsilon))
    action_gradient = -CPSI * float(grid.volume[2, 0]) * float(probe_acc[0, 2, 3])
    assert abs(finite_gradient - action_gradient) / max(1.0, abs(finite_gradient), abs(action_gradient)) < 1.0e-6

    free = torch.zeros_like(q)
    free[1, 2, 3] = 1.0e-6
    free_acc = grid.acceleration(free, 0.0)
    linear = grid.laplacian(free)
    linear[1:] *= K / 2.0
    linear[1:] -= B * free[1:]
    linear[1:] /= A
    assert float(torch.max(torch.abs(free_acc[1:] - linear[1:]))) < 1.0e-8

    torch.manual_seed(7)
    balance_q = torch.randn_like(q) * 1.0e-3
    balance_v = torch.randn_like(v) * 1.0e-3
    balance_acc = grid.acceleration(balance_q, coupling)
    core = grid.r2 + grid.axial[None, :].square() < CORE_RADIUS**2
    analytic = local_balances(grid, balance_q, balance_v, balance_acc, coupling, core)
    step = 1.0e-6
    plus_energy = float(cell_energy(grid, balance_q + step * balance_v, balance_v + step * balance_acc, coupling)[core].sum())
    minus_energy = float(cell_energy(grid, balance_q - step * balance_v, balance_v - step * balance_acc, coupling)[core].sum())
    finite_energy = (plus_energy - minus_energy) / (2.0 * step)
    plus_rho = -2.0 * A * ((balance_q[1] + step * balance_v[1]) * (balance_v[2] + step * balance_acc[2]) - (balance_q[2] + step * balance_v[2]) * (balance_v[1] + step * balance_acc[1]))
    minus_rho = -2.0 * A * ((balance_q[1] - step * balance_v[1]) * (balance_v[2] - step * balance_acc[2]) - (balance_q[2] - step * balance_v[2]) * (balance_v[1] - step * balance_acc[1]))
    finite_charge = float((grid.volume * (plus_rho - minus_rho) * core).sum()) / (2.0 * step)
    assert abs(finite_energy - analytic["core_energy_derivative"]) / max(1.0, abs(finite_energy), abs(analytic["core_energy_derivative"])) < 1.0e-6
    assert abs(finite_charge - analytic["core_charge_derivative"]) / max(1.0, abs(finite_charge), abs(analytic["core_charge_derivative"])) < 1.0e-6

    stationary = ROOT / "runs" / "20260911_matter_formation_minimum_droplet" / "stationary" / "q16_S1_c1p2.json"
    archive = stationary.with_suffix(".npz")
    record = json.loads(stationary.read_text(encoding="utf-8"))
    assert record["stationary"] is True and record["binding_witness"] is True
    assert record["archive_sha256"] == sha256(archive)
    source_identity = {str(path): sha256(path) for path in (PREREG, PRIMARY_SOURCE, NEUTRAL_SOURCE, CLOUD_SOURCE, VERIFIER_SOURCE)}
    assert all(path.is_file() and len(value) == 64 for path, value in ((Path(key), value) for key, value in source_identity.items()))
    print(json.dumps({
        "smoke": "PASS",
        "controls": ["energy_gradient", "vacuum", "charge_sign", "free_propagation", "source_identity", "stationary_reference", "local_balance_finite_difference"],
        "energy_reference": energy_reference,
        "charge_reference": charge_reference,
    }))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "20260911_matter_formation_wave_capture")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    input_dir = args.input.resolve()
    if args.replay_only and args.output is None:
        parser.error("--replay-only requires --output outside the preserved run directory")
    output = (args.output or (input_dir / "verification-repair.json")).resolve()
    result = run(input_dir, output, replay_only=args.replay_only)
    print(json.dumps({
        "output": str(output),
        "numeric_pass": result["numeric_pass"],
        "replay_only": result["replay_only"],
        "snapshot_pass": result["snapshot_details"]["pass"],
        "conservation_pass": result["independent_conservation_pass"],
    }))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
