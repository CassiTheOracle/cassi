#!/usr/bin/env python3
"""Decompose the retained charged-wave compact observable from raw states."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
CAMPAIGN = ROOT / "runs" / "20260911_matter_formation_wave_capture_spatial_convergence_20260911"
PRIMARY_RECEIPT = CAMPAIGN / "result.json"
VERIFICATION_RECEIPT = CAMPAIGN / "verification.json"
PRIMARY_STATES = CAMPAIGN / "primary"
PREREG = COMPUTATIONS / "matter_formation_compact_observable_decomposition_prereg.md"
SELF = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs" / "20260911_matter_formation_compact_observable_decomposition_20260911"

SCHEMA = "matter-formation-compact-observable-decomposition-20260911"
PRIMARY_RECEIPT_SHA256 = "c9619d8e431c840b8656ec470ec411ede23614bb20d8b200fbd6f7fd8b356ae9"
VERIFICATION_RECEIPT_SHA256 = "45755f677b83b11a65f1fb2271f6c85fa4844e068cc482e4cbb1c74a220abf64"
EXPECTED_SOURCE_SHA256 = {
    "computations/matter_formation_wave_capture_spatial_convergence.py": "4deabd70cca5979c8de7b90d7ef71fda938b455d8195563d1d52de76faf91c6b",
    "computations/matter_formation_wave_capture.py": "6f8f6ceaced604e38aab1d08b53eadcf06aa4db1fd1b2f27459995c5d65a5aaa",
    "computations/verify_matter_formation_wave_capture.py": "e6111739e6c355a5e4015aca2c468a2855bc9b9a84d713709a7db518c1717a84",
    "computations/verify_matter_formation_wave_capture_spatial_convergence.py": "589a26fd4580b61056fdf31a3116981f50f2ec94e29d077b4b82afb130652126",
}
ARCHIVED_SOURCE_PATHS = {
    key: CAMPAIGN / "sources" / key.replace("/", "__")
    for key in EXPECTED_SOURCE_SHA256
}
TARGET_GRIDS = ("S0", "S1", "S2")
TARGET_ARMS = ("pair256", "antiphase256")
SNAPSHOT_TIMES = (32.0, 40.0, 48.0)
CUT_INNERS = (4.0, 6.0, 8.0, 10.0, 12.0)
CUT_WIDTHS = (2.0, 4.0, 6.0)
REFERENCE_CUT = (8.0, 4.0)
CORE_RADIUS = 8.0
SHELL_RADIUS = 12.0
COMPARISON_TOL = 0.05
RETAINED_FRACTION = 0.25
RECONSTRUCTION_TOL = 5.0e-8
ENERGY_IDENTITY_TOL = 1.0e-8
REQUIRED_KEYS = {"fields", "velocities", "r", "axial", "volume", "time"}
MEAN_FIELDS = (
    "energy",
    "charge",
    "abs_charge",
    "core_charge",
    "core_abs_charge",
    "core_fraction",
    "core_rms",
    "core_energy",
    "shell_energy",
    "shell_energy_fraction",
    "cut_energy",
    "cut_charge",
    "cut_abs_charge",
    "cut_charge_fraction",
    "momentum",
    "momentum_energy",
    "radicand",
    "sqrt_radicand",
    "binding_ratio",
    "cut_denominator",
    "mediator_potential",
    "carrier_potential",
    "kinetic_energy",
    "radial_gradient",
    "axial_gradient",
    "cut_mediator_potential",
    "cut_carrier_potential",
    "cut_kinetic_energy",
    "cut_radial_gradient",
    "cut_axial_gradient",
)
RECONSTRUCTION_FIELDS = (
    "energy",
    "charge",
    "abs_charge",
    "core_charge",
    "core_abs_charge",
    "core_fraction",
    "core_rms",
    "core_energy",
    "cut_energy",
    "cut_charge",
    "momentum",
    "radicand",
    "binding_ratio",
    "shell_energy",
    "shell_energy_fraction",
)
A = 1.0 / 16.0
CPSI = 1.0 / 8.0
URHO = 4.0
UC = 1.0
K = 1.0
HC = 2.9598260763447164
B = 4.75
OMEGA_INF = math.sqrt(B / A)
VSTAR = math.sqrt(K / (2.0 * A))


class ArchivedGrid:
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


def energy_components(grid: ArchivedGrid, q: torch.Tensor, v: torch.Tensor, coupling: float) -> dict[str, float]:
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


def cell_energy(grid: ArchivedGrid, q: torch.Tensor, v: torch.Tensor, coupling: float) -> torch.Tensor:
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
        q[0, -1, :].square() + K * q[1, -1, :].square() + K * q[2, -1, :].square()
    )
    axial_faces = ((q[:, :, 1:] - q[:, :, :-1]).square() * grid.axial_edge) / 2.0
    axial_faces[1:] *= K
    axial_total = axial_faces.sum(dim=0)
    result[:, 1:] += axial_total / 2.0
    result[:, :-1] += axial_total / 2.0
    result[:, 0] += grid.axial_edge[:, 0] * (
        q[0, :, 0].square() + K * q[1, :, 0].square() + K * q[2, :, 0].square()
    )
    result[:, -1] += grid.axial_edge[:, 0] * (
        q[0, :, -1].square() + K * q[1, :, -1].square() + K * q[2, :, -1].square()
    )
    return result


class DiagnosticError(RuntimeError):
    pass




def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise DiagnosticError(f"nonfinite JSON constant {value}: {path}")

    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, DiagnosticError) as error:
        if isinstance(error, DiagnosticError):
            raise
        raise DiagnosticError(f"invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise DiagnosticError(f"JSON object required: {path}")
    return value


def finite_number(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def source_hashes() -> tuple[dict[str, str], dict[str, str]]:
    archived = {key: sha256(path) for key, path in ARCHIVED_SOURCE_PATHS.items()}
    if archived != EXPECTED_SOURCE_SHA256:
        raise DiagnosticError(f"archived source identity mismatch: {archived}")
    live = {key: sha256(ROOT / key) for key in EXPECTED_SOURCE_SHA256}
    return archived, live


def snapshot_sources(output: Path, archived_hashes: dict[str, str]) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=True, exist_ok=False)
    paths = [(SELF, SELF.relative_to(ROOT).as_posix()), (PREREG, PREREG.relative_to(ROOT).as_posix())]
    paths.extend((ARCHIVED_SOURCE_PATHS[key], key) for key in EXPECTED_SOURCE_SHA256)
    recorded: dict[str, str] = {}
    for path, relative in paths:
        destination = source_dir / relative.replace("/", "__")
        shutil.copyfile(path, destination)
        recorded[relative] = sha256(path)
    if any(recorded.get(key) != value for key, value in archived_hashes.items()):
        raise DiagnosticError("archived source snapshot changed during capture")
    return recorded


def expected_geometry(radius: int, spacing: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    nr = int(round(radius / spacing))
    nz = 2 * nr
    radial = (np.arange(nr, dtype=np.float64) + 0.5) * spacing
    axial = -radius + (np.arange(nz, dtype=np.float64) + 0.5) * spacing
    faces = np.arange(nr + 1, dtype=np.float64) * spacing
    volume = (math.pi * (faces[1:] ** 2 - faces[:-1] ** 2) * spacing)[:, None]
    return radial, axial, volume


def validate_state(row: dict[str, Any], state: dict[str, Any]) -> tuple[Path, np.ndarray, np.ndarray, float]:
    if not isinstance(state, dict) or not isinstance(state.get("path"), str):
        raise DiagnosticError("malformed state metadata")
    state_path = (PRIMARY_STATES / state["path"]).resolve()
    try:
        state_path.relative_to(PRIMARY_STATES.resolve())
    except ValueError as error:
        raise DiagnosticError(f"state escapes primary archive: {state_path}") from error
    if not state_path.is_file() or sha256(state_path) != state.get("sha256"):
        raise DiagnosticError(f"state hash mismatch: {state_path}")
    with np.load(state_path, allow_pickle=False) as data:
        if set(data.files) != REQUIRED_KEYS:
            raise DiagnosticError(f"state keys mismatch: {state_path}")
        arrays = {key: np.asarray(data[key]) for key in REQUIRED_KEYS}
    if any(array.dtype != np.float64 for array in arrays.values()):
        raise DiagnosticError(f"state dtype mismatch: {state_path}")
    fields = arrays["fields"]
    velocities = arrays["velocities"]
    radius = int(row["R"])
    spacing = float(row["spacing"])
    nr = int(round(radius / spacing))
    nz = 2 * nr
    if fields.shape != (3, nr, nz) or velocities.shape != fields.shape:
        raise DiagnosticError(f"state field shape mismatch: {state_path}")
    if arrays["r"].shape != (nr,) or arrays["axial"].shape != (nz,) or arrays["volume"].shape != (nr, 1):
        raise DiagnosticError(f"state geometry shape mismatch: {state_path}")
    expected_r, expected_axial, expected_volume = expected_geometry(radius, spacing)
    for actual, expected, label in (
        (arrays["r"], expected_r, "r"),
        (arrays["axial"], expected_axial, "axial"),
        (arrays["volume"], expected_volume, "volume"),
    ):
        if not np.isfinite(actual).all() or not np.array_equal(actual, expected):
            raise DiagnosticError(f"state {label} mismatch: {state_path}")
    if not np.isfinite(fields).all() or not np.isfinite(velocities).all():
        raise DiagnosticError(f"nonfinite field state: {state_path}")
    embedded_time = float(np.asarray(arrays["time"]).reshape(()))
    if not finite_number(embedded_time) or abs(embedded_time - float(state["time"])) > 1.0e-12:
        raise DiagnosticError(f"state time mismatch: {state_path}")
    return state_path, fields, velocities, embedded_time


def smooth_cut(distance: torch.Tensor, inner: float, width: float) -> torch.Tensor:
    s = torch.clamp((distance - inner) / width, 0.0, 1.0)
    return 1.0 - 3.0 * s.square() + 2.0 * s.pow(3)


def measure_cut(
    grid: ArchivedGrid,
    q: torch.Tensor,
    v: torch.Tensor,
    coupling: float,
    charge_reference: float,
    energy_reference: float,
    inner: float,
    width: float,
) -> dict[str, float]:
    rho = -2.0 * A * (q[1] * v[2] - q[2] * v[1])
    abs_rho = rho.abs()
    distance2 = grid.r2 + grid.axial[None, :].square()
    distance = torch.sqrt(distance2)
    core = distance2 < CORE_RADIUS**2
    shell = (distance2 >= CORE_RADIUS**2) & (distance2 < SHELL_RADIUS**2)
    smooth = smooth_cut(distance, inner, width)
    cut_q, cut_v = smooth * q, smooth * v
    energy = float(grid.energy(q, v, coupling))
    cut_energy = float(grid.energy(cut_q, cut_v, coupling))
    total_charge = float((grid.volume * rho).sum())
    abs_charge = float((grid.volume * abs_rho).sum())
    core_charge = float((grid.volume * rho * core).sum())
    core_abs_charge = float((grid.volume * abs_rho * core).sum())
    core_rms = math.sqrt(
        max(0.0, float((grid.volume * abs_rho * distance2 * core).sum()) / max(core_abs_charge, 1.0e-30))
    )
    core_f2 = float((grid.volume * abs_rho * (q[0] + 1.0).square() * core).sum()) / max(core_abs_charge, 1.0e-30)
    cut_charge = float((grid.volume * rho * smooth.square()).sum())
    dz = grid.axial_derivative(cut_q)
    momentum = -float(
        (
            grid.volume
            * (
                CPSI * cut_v[0] * dz[0]
                + 2.0 * A * (cut_v[1] * dz[1] + cut_v[2] * dz[2])
            )
        ).sum()
    )
    radicand = cut_energy * cut_energy - (VSTAR * momentum) ** 2
    if radicand < 0.0 or cut_charge == 0.0:
        raise DiagnosticError(f"undefined binding observable at cut ({inner}, {width})")
    sqrt_radicand = math.sqrt(radicand)
    binding_ratio = sqrt_radicand / (OMEGA_INF * abs(cut_charge))
    allocated = cell_energy(grid, q, v, coupling)
    components = energy_components(grid, q, v, coupling)
    cut_components = energy_components(grid, cut_q, cut_v, coupling)
    component_total = sum(components.values())
    cut_component_total = sum(cut_components.values())
    energy_identity_error = abs(component_total - energy) / max(1.0, abs(energy))
    cut_energy_identity_error = abs(cut_component_total - cut_energy) / max(1.0, abs(cut_energy))
    result = {
        "energy": energy,
        "charge": total_charge,
        "abs_charge": abs_charge,
        "core_charge": core_charge,
        "core_abs_charge": core_abs_charge,
        "core_fraction": core_charge / charge_reference,
        "core_rms": core_rms,
        "core_energy": float((allocated * core).sum()),
        "shell_energy": float((allocated * shell).sum()),
        "shell_energy_fraction": float((allocated * shell).sum()) / max(abs(energy_reference), 1.0e-30),
        "cut_energy": cut_energy,
        "cut_charge": cut_charge,
        "cut_abs_charge": abs(cut_charge),
        "cut_charge_fraction": abs(cut_charge) / abs(charge_reference),
        "momentum": momentum,
        "momentum_energy": VSTAR * momentum,
        "radicand": radicand,
        "sqrt_radicand": sqrt_radicand,
        "binding_ratio": binding_ratio,
        "cut_denominator": OMEGA_INF * abs(cut_charge),
        "energy_identity_error": energy_identity_error,
        "cut_energy_identity_error": cut_energy_identity_error,
    }
    result.update(components)
    result.update({f"cut_{key}": value for key, value in cut_components.items()})
    if energy_identity_error > ENERGY_IDENTITY_TOL or cut_energy_identity_error > ENERGY_IDENTITY_TOL:
        raise DiagnosticError(f"energy decomposition mismatch at cut ({inner}, {width})")
    if not all(finite_number(value) for value in result.values()):
        raise DiagnosticError(f"nonfinite measurement at cut ({inner}, {width})")
    return result


def comparison_mean(left: dict[str, Any], right: dict[str, Any], field: str) -> float:
    return abs(float(left[field]) - float(right[field]))


def reconstruct_row(row: dict[str, Any]) -> tuple[dict[str, Any], dict[tuple[float, float], dict[str, Any]]]:
    if row.get("grid") not in TARGET_GRIDS or row.get("arm") not in TARGET_ARMS:
        raise DiagnosticError("unexpected target row")
    initial = row.get("initial")
    states = row.get("states")
    times = row.get("times")
    trace = row.get("trace")
    if not isinstance(initial, dict) or not isinstance(states, list) or not isinstance(times, list) or not isinstance(trace, list):
        raise DiagnosticError("row schema mismatch")
    if len(times) != len(trace):
        raise DiagnosticError("row trace/time mismatch")
    charge_reference = float(initial["charge"])
    energy_reference = float(initial["energy"])
    grid = ArchivedGrid(int(row["R"]), float(row["spacing"]))
    state_by_time = {float(state["time"]): state for state in states}
    if set(state_by_time) != {0.0, *SNAPSHOT_TIMES}:
        raise DiagnosticError(f"snapshot schedule mismatch for {row['grid']}_{row['arm']}")
    initial_state_path, initial_fields, initial_velocities, initial_embedded_time = validate_state(row, state_by_time[0.0])
    snapshot_outputs: list[dict[str, Any]] = []
    reconstruction_checks: list[dict[str, Any]] = []
    late_values: dict[tuple[float, float], list[dict[str, float]]] = {
        (inner, width): [] for inner in CUT_INNERS for width in CUT_WIDTHS
    }
    initial_q = torch.as_tensor(initial_fields, dtype=torch.float64, device="cuda")
    initial_v = torch.as_tensor(initial_velocities, dtype=torch.float64, device="cuda")
    del initial_fields, initial_velocities
    initial_cut_outputs: list[dict[str, Any]] = []
    for inner in CUT_INNERS:
        for width in CUT_WIDTHS:
            measurement = measure_cut(
                grid,
                initial_q,
                initial_v,
                float(row["coupling"]),
                charge_reference,
                energy_reference,
                inner,
                width,
            )
            initial_cut_outputs.append({"inner": inner, "width": width, "observables": measurement})
    initial_trace_index = next((index for index, value in enumerate(times) if abs(float(value)) < 1.0e-12), None)
    if initial_trace_index is None:
        raise DiagnosticError("trace snapshot missing at 0.0")
    initial_expected = trace[initial_trace_index]
    initial_default = next(
        item["observables"]
        for item in initial_cut_outputs
        if (item["inner"], item["width"]) == REFERENCE_CUT
    )
    initial_checks: dict[str, Any] = {}
    for field in RECONSTRUCTION_FIELDS:
        observed = initial_default[field]
        expected_value = initial_expected.get(field)
        if not finite_number(expected_value):
            raise DiagnosticError(f"archived trace field missing: {field}")
        error = abs(observed - float(expected_value))
        tolerance = RECONSTRUCTION_TOL * max(1.0, abs(float(expected_value)))
        initial_checks[field] = {
            "observed": observed,
            "expected": float(expected_value),
            "absolute_error": error,
            "tolerance": tolerance,
            "pass": bool(error <= tolerance),
        }
    reconstruction_checks.append({"time": 0.0, "state": initial_state_path.name, "checks": initial_checks})
    initial_snapshot_output = {
        "time": initial_embedded_time,
        "state": initial_state_path.name,
        "cuts": initial_cut_outputs,
    }
    del initial_q, initial_v
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    for time_value in SNAPSHOT_TIMES:
        state_path, fields, velocities, embedded_time = validate_state(row, state_by_time[time_value])
        q = torch.as_tensor(fields, dtype=torch.float64, device="cuda")
        v = torch.as_tensor(velocities, dtype=torch.float64, device="cuda")
        del fields, velocities
        cut_outputs: list[dict[str, Any]] = []
        for inner in CUT_INNERS:
            for width in CUT_WIDTHS:
                measurement = measure_cut(
                    grid,
                    q,
                    v,
                    float(row["coupling"]),
                    charge_reference,
                    energy_reference,
                    inner,
                    width,
                )
                cut_outputs.append({"inner": inner, "width": width, "observables": measurement})
                late_values[(inner, width)].append(measurement)
        trace_index = next((index for index, value in enumerate(times) if abs(float(value) - time_value) < 1.0e-12), None)
        if trace_index is None:
            raise DiagnosticError(f"trace snapshot missing at {time_value}")
        expected = trace[trace_index]
        default = next(item["observables"] for item in cut_outputs if (item["inner"], item["width"]) == REFERENCE_CUT)
        checks: dict[str, Any] = {}
        for field in RECONSTRUCTION_FIELDS:
            observed = default[field]
            expected_value = expected.get(field)
            if not finite_number(expected_value):
                raise DiagnosticError(f"archived trace field missing: {field}")
            error = abs(observed - float(expected_value))
            tolerance = RECONSTRUCTION_TOL * max(1.0, abs(float(expected_value)))
            checks[field] = {
                "observed": observed,
                "expected": float(expected_value),
                "absolute_error": error,
                "tolerance": tolerance,
                "pass": bool(error <= tolerance),
            }
        reconstruction_checks.append({"time": time_value, "state": state_path.name, "checks": checks})
        snapshot_outputs.append({"time": embedded_time, "state": state_path.name, "cuts": cut_outputs})
        del q, v
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    reconstruction_pass = bool(
        reconstruction_checks
        and all(check["pass"] for item in reconstruction_checks for check in item["checks"].values())
    )
    summaries: dict[str, dict[str, float]] = {}
    for cut_key, values in late_values.items():
        summaries[f"{cut_key[0]:g},{cut_key[1]:g}"] = {
            field: float(np.mean([item[field] for item in values])) for field in MEAN_FIELDS
        }
    return (
        {
            "grid": row["grid"],
            "arm": row["arm"],
            "R": row["R"],
            "spacing": row["spacing"],
            "coupling": row["coupling"],
            "initial_energy": energy_reference,
            "initial_charge": charge_reference,
            "initial_snapshot": initial_snapshot_output,
            "snapshots": snapshot_outputs,
            "late_snapshot_times": list(SNAPSHOT_TIMES),
            "late_means": summaries,
            "reconstruction_checks": reconstruction_checks,
            "reconstruction_pass": reconstruction_pass,
        },
        summaries,
    )


def compare(
    left_row: dict[str, Any],
    right_row: dict[str, Any],
    left: dict[str, float],
    right: dict[str, float],
    inner: float,
    width: float,
    level_pair: str,
) -> dict[str, Any]:
    energy_scale = max(1.0, abs(float(left_row["initial_energy"])), abs(float(right_row["initial_energy"])))
    charge_scale = max(1.0, abs(float(left_row["initial_charge"])), abs(float(right_row["initial_charge"])))
    errors = {
        "cut_energy": comparison_mean(left, right, "cut_energy") / energy_scale,
        "cut_charge": comparison_mean(left, right, "cut_charge") / charge_scale,
        "momentum_energy": comparison_mean(left, right, "momentum_energy") / energy_scale,
        "sqrt_radicand": comparison_mean(left, right, "sqrt_radicand") / energy_scale,
        "binding_ratio": comparison_mean(left, right, "binding_ratio"),
    }
    component_failures = [
        name for name in ("cut_energy", "cut_charge", "momentum_energy") if errors[name] >= COMPARISON_TOL
    ]
    return {
        "arm": left_row["arm"],
        "level_pair": level_pair,
        "inner": inner,
        "width": width,
        "energy_scale": energy_scale,
        "charge_scale": charge_scale,
        "left": {field: left[field] for field in MEAN_FIELDS},
        "right": {field: right[field] for field in MEAN_FIELDS},
        "errors": errors,
        "ratio_fail": bool(errors["binding_ratio"] >= COMPARISON_TOL),
        "component_failures": component_failures,
        "left_charge_fraction": left["cut_charge_fraction"],
        "right_charge_fraction": right["cut_charge_fraction"],
        "component_disagreement": bool(component_failures),
    }


def run(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    if not torch.cuda.is_available():
        raise DiagnosticError("CUDA/ROCm device required for archived-state decomposition")
    primary_hash = sha256(PRIMARY_RECEIPT)
    verification_hash = sha256(VERIFICATION_RECEIPT)
    if primary_hash != PRIMARY_RECEIPT_SHA256 or verification_hash != VERIFICATION_RECEIPT_SHA256:
        raise DiagnosticError("immutable campaign receipt hash mismatch")
    primary = strict_json(PRIMARY_RECEIPT)
    verification = strict_json(VERIFICATION_RECEIPT)
    if primary.get("schema") != "matter-formation-spatial-convergence-primary-20260911":
        raise DiagnosticError("primary schema mismatch")
    if verification.get("schema") != "matter-formation-spatial-convergence-verification-20260911":
        raise DiagnosticError("verification schema mismatch")
    archived_hashes, live_hashes = source_hashes()
    output.mkdir(parents=True, exist_ok=False)
    captured_sources = snapshot_sources(output, archived_hashes)
    all_rows = {
        (row.get("grid"), row.get("arm")): row
        for row in primary.get("rows", [])
        if isinstance(row, dict)
    }
    expected_rows = {(grid, arm) for grid in TARGET_GRIDS for arm in TARGET_ARMS}
    if not expected_rows.issubset(all_rows):
        raise DiagnosticError(f"target row set mismatch: {set(all_rows)}")
    rows = {key: all_rows[key] for key in expected_rows}
    row_outputs: dict[tuple[str, str], dict[str, Any]] = {}
    summaries: dict[tuple[str, str], dict[str, dict[str, float]]] = {}
    for grid_name, arm in sorted(expected_rows):
        row_output, row_summaries = reconstruct_row(rows[(grid_name, arm)])
        row_outputs[(grid_name, arm)] = row_output
        summaries[(grid_name, arm)] = row_summaries
    comparisons: list[dict[str, Any]] = []
    for arm in TARGET_ARMS:
        for left_grid, right_grid, level_pair in (("S0", "S1", "S0->S1"), ("S1", "S2", "S1->S2")):
            for inner in CUT_INNERS:
                for width in CUT_WIDTHS:
                    key = f"{inner:g},{width:g}"
                    comparisons.append(
                        compare(
                            row_outputs[(left_grid, arm)],
                            row_outputs[(right_grid, arm)],
                            summaries[(left_grid, arm)][key],
                            summaries[(right_grid, arm)][key],
                            inner,
                            width,
                            level_pair,
                        )
                    )
    reference = [
        item
        for item in comparisons
        if item["level_pair"] == "S1->S2"
        and (float(item["inner"]), float(item["width"])) == REFERENCE_CUT
    ]
    reconstruction_pass = bool(all(item["reconstruction_pass"] for item in row_outputs.values()))
    integrity_pass = bool(reconstruction_pass and captured_sources and primary_hash == PRIMARY_RECEIPT_SHA256 and verification_hash == VERIFICATION_RECEIPT_SHA256)
    denominator_conditioned = bool(
        any(
            item["ratio_fail"]
            and not item["component_disagreement"]
            and item["left_charge_fraction"] < RETAINED_FRACTION
            and item["right_charge_fraction"] < RETAINED_FRACTION
            for item in reference
        )
    )
    component_disagreement = bool(
        any(
            item["ratio_fail"]
            and (
                item["component_disagreement"]
                or item["left_charge_fraction"] >= RETAINED_FRACTION
                or item["right_charge_fraction"] >= RETAINED_FRACTION
            )
            for item in reference
        )
    )
    no_ratio_failure = bool(reference and all(not item["ratio_fail"] for item in reference))
    if not integrity_pass:
        verdict = "INCONCLUSIVE—archive integrity failure"
    elif component_disagreement:
        verdict = "COMPONENT-DISAGREEMENT"
    elif denominator_conditioned:
        verdict = "DENOMINATOR-CONDITIONED"
    elif no_ratio_failure:
        verdict = "NO_RATIO_FAILURE"
    else:
        verdict = "INCONCLUSIVE—decision branches do not separate"
    result = {
        "schema": SCHEMA,
        "protocol_sha256": sha256(PREREG),
        "source_sha256": captured_sources,
        "inputs": {
            "primary_receipt": PRIMARY_RECEIPT.relative_to(ROOT).as_posix(),
            "primary_receipt_sha256": primary_hash,
            "verification_receipt": VERIFICATION_RECEIPT.relative_to(ROOT).as_posix(),
            "verification_receipt_sha256": verification_hash,
            "campaign_primary_comparison_pass": verification.get("primary_comparison_pass"),
            "campaign_numeric_pass": verification.get("numeric_pass"),
            "archived_source_sha256": archived_hashes,
            "live_source_sha256": live_hashes,
        },
        "schedule": {
            "target_grids": list(TARGET_GRIDS),
            "target_arms": list(TARGET_ARMS),
            "snapshot_times": list(SNAPSHOT_TIMES),
            "cut_inners": list(CUT_INNERS),
            "cut_widths": list(CUT_WIDTHS),
            "reference_cut": list(REFERENCE_CUT),
            "comparison_tolerance": COMPARISON_TOL,
            "retained_fraction": RETAINED_FRACTION,
            "reconstruction_tolerance": RECONSTRUCTION_TOL,
            "energy_identity_tolerance": ENERGY_IDENTITY_TOL,
        },
        "integrity": {
            "primary_receipt_hash": primary_hash == PRIMARY_RECEIPT_SHA256,
            "verification_receipt_hash": verification_hash == VERIFICATION_RECEIPT_SHA256,
            "source_hashes": archived_hashes == EXPECTED_SOURCE_SHA256,
            "reconstruction_pass": reconstruction_pass,
            "pass": integrity_pass,
        },
        "rows": [row_outputs[key] for key in sorted(row_outputs)],
        "comparisons": comparisons,
        "summary": {
            "reference_comparisons": reference,
            "denominator_conditioned": denominator_conditioned,
            "component_disagreement": component_disagreement,
            "no_ratio_failure": no_ratio_failure,
            "reference_ratio_failures": sum(1 for item in reference if item["ratio_fail"]),
            "reference_component_failures": {
                item["arm"]: item["component_failures"] for item in reference
            },
        },
        "verdict": verdict,
        "formation_claim": False,
    }
    write_json(output / "result.json", result)
    return result


def run_smoke() -> int:
    if not torch.cuda.is_available():
        raise DiagnosticError("CUDA/ROCm device required for smoke")
    grid = ArchivedGrid(8, 1.0)
    q = torch.zeros((3, grid.nr, grid.nz), dtype=torch.float64, device="cuda")
    v = torch.zeros_like(q)
    q[1].fill_(0.25)
    v[2].fill_(0.25)
    result = measure_cut(grid, q, v, HC, 1.0, 1.0, 2.0, 2.0)
    if result["cut_energy_identity_error"] > ENERGY_IDENTITY_TOL or not finite_number(result["binding_ratio"]):
        raise DiagnosticError("smoke decomposition failed")
    print(json.dumps({"smoke": "PASS", "cut_energy": result["cut_energy"], "cut_charge": result["cut_charge"], "binding_ratio": result["binding_ratio"]}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    result = run(args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), "verdict": result["verdict"], "integrity_pass": result["integrity"]["pass"]}))
    return 0 if result["integrity"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
