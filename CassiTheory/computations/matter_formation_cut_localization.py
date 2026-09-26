#!/usr/bin/env python3
"""Diagnose compact-cut conditioning from retained charged-wave states."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
PREREG = COMPUTATIONS / "matter_formation_cut_localization_prereg.md"
DEFAULT_CAMPAIGN = ROOT / "runs" / "20260911_matter_formation_wave_capture_spatial_convergence_20260911"
DEFAULT_VERIFICATION = DEFAULT_CAMPAIGN / "verification.json"
DEFAULT_OUTPUT = ROOT / "runs" / "20260911_matter_formation_cut_localization_20260911"
SCHEMA = "matter-formation-cut-localization-primary-20260911"
CAMPAIGN_SCHEMA = "matter-formation-spatial-convergence-primary-20260911"
VERIFICATION_SCHEMA = "matter-formation-spatial-convergence-verification-20260911"

A = 1.0 / 16.0
CPSI = 1.0 / 8.0
URHO = 4.0
UC = 1.0
K = 1.0
HC = 2.9598260763447164
B = 4.75
OMEGA_INF = math.sqrt(B / A)
VSTAR = math.sqrt(K / (2.0 * A))
CORE_RADIUS = 8.0
SHELL_OUTER = 12.0
TARGET_GRIDS = ("S0", "S1", "S2")
TARGET_ARMS = ("pair256", "antiphase256")
SNAPSHOT_TIMES = (0.0, 32.0, 40.0, 48.0)
LATE_TIMES = (32.0, 40.0, 48.0)
CUT_INNERS = (4.0, 6.0, 8.0, 10.0, 12.0)
CUT_WIDTHS = (2.0, 4.0, 6.0)
HARD_RADII = (4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 24.0, 32.0)
FIXED_CORE_CHARGE_FRACTION_MAX = 0.25
COMPONENT_COMPARISON_TOL = 0.05
RECONSTRUCTION_TOL = 5.0e-8

RECONSTRUCTION_NAMES = (
    "energy",
    "charge",
    "core_charge",
    "core_fraction",
    "core_rms",
    "core_energy",
    "cut_energy",
    "cut_charge",
    "binding_ratio",
    "shell_energy_fraction",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_number(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def strict_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"nonfinite JSON constant {value}: {path}")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f"object required: {path}")
    return value


def smooth_cut(distance: np.ndarray, inner: float, width: float) -> np.ndarray:
    s = np.clip((distance - inner) / width, 0.0, 1.0)
    return 1.0 - 3.0 * s * s + 2.0 * s * s * s


def axial_derivative(value: np.ndarray, spacing: float) -> np.ndarray:
    result = np.empty_like(value)
    result[..., 1:-1] = (value[..., 2:] - value[..., :-2]) / (2.0 * spacing)
    result[..., 0] = (value[..., 1] - value[..., 0]) / spacing
    result[..., -1] = (value[..., -1] - value[..., -2]) / spacing
    return result


class Geometry:
    def __init__(self, radius: int, spacing: float, r: np.ndarray, axial: np.ndarray, volume: np.ndarray) -> None:
        self.radius = int(radius)
        self.spacing = float(spacing)
        self.r = np.asarray(r, dtype=np.float64)
        self.axial = np.asarray(axial, dtype=np.float64)
        self.volume = np.asarray(volume, dtype=np.float64)
        self.nr = int(round(self.radius / self.spacing))
        self.nz = 2 * self.nr
        faces = np.arange(self.nr + 1, dtype=np.float64) * self.spacing
        self.radial_edge = (2.0 * math.pi * faces[1:-1])[:, None]
        self.axial_edge = self.volume / self.spacing**2
        self.radial_boundary = 4.0 * math.pi * self.radius
        self.distance = np.sqrt(self.r[:, None] ** 2 + self.axial[None, :] ** 2)
        self.distance2 = self.distance * self.distance
        self.shell_mask = (self.distance >= CORE_RADIUS) & (self.distance < SHELL_OUTER)


def validate_geometry(geometry: Geometry) -> None:
    expected_r = (np.arange(geometry.nr, dtype=np.float64) + 0.5) * geometry.spacing
    expected_axial = -geometry.radius + (np.arange(geometry.nz, dtype=np.float64) + 0.5) * geometry.spacing
    faces = np.arange(geometry.nr + 1, dtype=np.float64) * geometry.spacing
    expected_volume = (math.pi * (faces[1:] ** 2 - faces[:-1] ** 2) * geometry.spacing)[:, None]
    if not np.allclose(geometry.r, expected_r, rtol=0.0, atol=1.0e-12):
        raise ValueError("radial coordinates mismatch")
    if not np.allclose(geometry.axial, expected_axial, rtol=0.0, atol=1.0e-12):
        raise ValueError("axial coordinates mismatch")
    if not np.allclose(geometry.volume, expected_volume, rtol=0.0, atol=1.0e-12):
        raise ValueError("cell volumes mismatch")


def cell_energy(q: np.ndarray, v: np.ndarray, geometry: Geometry, coupling: float) -> np.ndarray:
    f = q[0] + 1.0
    n = q[1] * q[1] + q[2] * q[2]
    potential = URHO / 4.0 * (f * f - 1.0) ** 2 + (B - coupling + coupling * f * f) * n + UC / 2.0 * n * n
    kinetic = CPSI / 2.0 * v[0] * v[0] + A * (v[1] * v[1] + v[2] * v[2])
    result = (potential + kinetic) * geometry.volume

    radial_difference = q[:, 1:, :] - q[:, :-1, :]
    radial_faces = radial_difference * radial_difference * geometry.radial_edge[None, :, :] / 2.0
    radial_faces[1:] *= K
    radial_total = radial_faces.sum(axis=0)
    result[1:, :] += radial_total / 2.0
    result[:-1, :] += radial_total / 2.0
    result[-1, :] += geometry.radial_boundary / 2.0 * (
        q[0, -1, :] ** 2 + K * q[1, -1, :] ** 2 + K * q[2, -1, :] ** 2
    )

    axial_difference = q[:, :, 1:] - q[:, :, :-1]
    axial_faces = axial_difference * axial_difference * geometry.axial_edge[None, :, :] / 2.0
    axial_faces[1:] *= K
    axial_total = axial_faces.sum(axis=0)
    result[:, 1:] += axial_total / 2.0
    result[:, :-1] += axial_total / 2.0
    result[:, 0] += geometry.axial_edge[:, 0] * (
        q[0, :, 0] ** 2 + K * q[1, :, 0] ** 2 + K * q[2, :, 0] ** 2
    )
    result[:, -1] += geometry.axial_edge[:, 0] * (
        q[0, :, -1] ** 2 + K * q[1, :, -1] ** 2 + K * q[2, :, -1] ** 2
    )
    return result


def energy_components(q: np.ndarray, v: np.ndarray, geometry: Geometry, coupling: float) -> dict[str, float]:
    f = q[0] + 1.0
    n = q[1] * q[1] + q[2] * q[2]
    mediator = (geometry.volume * (URHO / 4.0 * (f * f - 1.0) ** 2)).sum()
    carrier = (geometry.volume * ((B - coupling + coupling * f * f) * n + UC / 2.0 * n * n)).sum()
    kinetic = (geometry.volume * (CPSI / 2.0 * v[0] * v[0] + A * (v[1] * v[1] + v[2] * v[2]))).sum()
    radial_faces = (q[:, 1:, :] - q[:, :-1, :]) ** 2 * geometry.radial_edge[None, :, :] / 2.0
    radial_faces[1:] *= K
    radial = radial_faces.sum() + geometry.radial_boundary / 2.0 * (
        q[0, -1, :] ** 2 + K * q[1, -1, :] ** 2 + K * q[2, -1, :] ** 2
    ).sum()
    axial_faces = (q[:, :, 1:] - q[:, :, :-1]) ** 2 * geometry.axial_edge[None, :, :] / 2.0
    axial_faces[1:] *= K
    axial = axial_faces.sum()
    axial += (
        geometry.axial_edge[:, 0]
        * (q[0, :, 0] ** 2 + K * q[1, :, 0] ** 2 + K * q[2, :, 0] ** 2)
    ).sum()
    axial += (
        geometry.axial_edge[:, 0]
        * (q[0, :, -1] ** 2 + K * q[1, :, -1] ** 2 + K * q[2, :, -1] ** 2)
    ).sum()
    return {
        "mediator_potential": float(mediator),
        "carrier_potential": float(carrier),
        "kinetic_energy": float(kinetic),
        "radial_gradient": float(radial),
        "axial_gradient": float(axial),
    }


def summarize_state(
    q: np.ndarray,
    v: np.ndarray,
    geometry: Geometry,
    coupling: float,
    inner: float = 8.0,
    width: float = 4.0,
    initial_charge: float = 256.0,
    initial_energy: float | None = None,
) -> dict[str, float]:
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        rho = -2.0 * A * (q[1] * v[2] - q[2] * v[1])
        abs_rho = np.abs(rho)
        allocated = cell_energy(q, v, geometry, coupling)
        total_energy = float(allocated.sum())
        initial_energy_reference = total_energy if initial_energy is None else float(initial_energy)
        total_charge = float((geometry.volume * rho).sum())
        abs_charge = float((geometry.volume * abs_rho).sum())
        core_mask = geometry.distance2 < CORE_RADIUS**2
        core_charge = float((geometry.volume * rho * core_mask).sum())
        core_abs_charge = float((geometry.volume * abs_rho * core_mask).sum())
        core_rms = math.sqrt(
            max(0.0, float((geometry.volume * abs_rho * geometry.distance2 * core_mask).sum()) / max(core_abs_charge, 1.0e-30))
        )
        core_energy = float((allocated * core_mask).sum())
        cut = smooth_cut(geometry.distance, inner, width)
        cut_q = cut[None, :, :] * q
        cut_v = cut[None, :, :] * v
        cut_energy = float(cell_energy(cut_q, cut_v, geometry, coupling).sum())
        cut_charge = float((geometry.volume * rho * cut * cut).sum())
        dz = axial_derivative(cut_q, geometry.spacing)
        momentum = -float(
            (geometry.volume * (CPSI * cut_v[0] * dz[0] + 2.0 * A * (cut_v[1] * dz[1] + cut_v[2] * dz[2]))).sum()
        )
        radicand = cut_energy * cut_energy - (VSTAR * momentum) ** 2
        binding_ratio = math.sqrt(radicand) / (OMEGA_INF * abs(cut_charge)) if cut_charge != 0.0 and radicand >= 0.0 else math.nan
        shell_energy = float((allocated * geometry.shell_mask).sum())
        components = energy_components(cut_q, cut_v, geometry, coupling)
    return {
        "energy": total_energy,
        "charge": total_charge,
        "abs_charge": abs_charge,
        "core_charge": core_charge,
        "core_abs_charge": core_abs_charge,
        "core_fraction": core_charge / initial_charge,
        "core_abs_charge_fraction": core_abs_charge / max(abs(initial_charge), 1.0e-30),
        "core_rms": core_rms,
        "core_energy": core_energy,
        "cut_energy": cut_energy,
        "cut_charge": cut_charge,
        "cut_charge_fraction": abs(cut_charge) / max(abs(initial_charge), 1.0e-30),
        "momentum": momentum,
        "radicand": radicand,
        "binding_ratio": binding_ratio,
        "shell_energy": shell_energy,
        "shell_energy_fraction": shell_energy / max(abs(initial_energy_reference), 1.0e-30),
        "cut_mediator_potential": components["mediator_potential"],
        "cut_carrier_potential": components["carrier_potential"],
        "cut_kinetic_energy": components["kinetic_energy"],
        "cut_radial_gradient": components["radial_gradient"],
        "cut_axial_gradient": components["axial_gradient"],
    }


def radial_profile(q: np.ndarray, v: np.ndarray, geometry: Geometry, coupling: float) -> dict[str, dict[str, float]]:
    rho = -2.0 * A * (q[1] * v[2] - q[2] * v[1])
    abs_rho = np.abs(rho)
    allocated = cell_energy(q, v, geometry, coupling)
    edges = (0.0, *HARD_RADII, math.inf)
    profile: dict[str, dict[str, float]] = {}
    for left, right in zip(edges[:-1], edges[1:]):
        mask = geometry.distance >= left
        if math.isfinite(right):
            mask &= geometry.distance < right
        label = f"{left:g}_{right:g}" if math.isfinite(right) else f"{left:g}_inf"
        profile[label] = {
            "energy": float((allocated * mask).sum()),
            "signed_charge": float((geometry.volume * rho * mask).sum()),
            "abs_charge": float((geometry.volume * abs_rho * mask).sum()),
        }
    return profile


def state_path(root: Path, state: dict[str, Any]) -> Path:
    relative = Path(str(state.get("path", "")))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("state path escapes archive")
    archive = (root / "primary").resolve()
    path = (archive / relative).resolve()
    path.relative_to(archive)
    return path


def independent_state_path(root: Path, state: dict[str, Any]) -> Path:
    relative = Path(str(state.get("path", "")))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("independent state path escapes archive")
    archive = root.resolve()
    path = (archive / relative).resolve()
    path.relative_to(archive)
    return path


def load_state(path: Path, declared_time: float, declared_hash: str, radius: int, spacing: float) -> tuple[np.ndarray, np.ndarray, Geometry, float]:
    if not path.is_file() or sha256(path) != declared_hash:
        raise ValueError(f"state hash mismatch: {path}")
    with np.load(path, allow_pickle=False) as archive:
        required = {"fields", "velocities", "r", "axial", "volume", "time"}
        if set(archive.files) != required:
            raise ValueError(f"state keys mismatch: {path}")
        fields = np.array(archive["fields"], copy=True)
        velocities = np.array(archive["velocities"], copy=True)
        r = np.array(archive["r"], copy=True)
        axial = np.array(archive["axial"], copy=True)
        volume = np.array(archive["volume"], copy=True)
        time_value = float(np.asarray(archive["time"]).reshape(()))
    nr = int(round(radius / spacing))
    if fields.dtype != np.float64 or velocities.dtype != np.float64:
        raise ValueError(f"state dtype mismatch: {path}")
    if fields.shape != (3, nr, 2 * nr) or velocities.shape != fields.shape:
        raise ValueError(f"state shape mismatch: {path}")
    if r.shape != (nr,) or axial.shape != (2 * nr,) or volume.shape != (nr, 1):
        raise ValueError(f"state geometry shape mismatch: {path}")
    if not all(np.isfinite(array).all() for array in (fields, velocities, r, axial, volume, np.asarray(time_value))):
        raise ValueError(f"nonfinite state: {path}")
    if abs(time_value - float(declared_time)) > 1.0e-12:
        raise ValueError(f"state time mismatch: {path}")
    geometry = Geometry(radius, spacing, r, axial, volume)
    validate_geometry(geometry)
    return fields, velocities, geometry, time_value


def relative_error(actual: float, expected: float) -> float:
    return abs(float(actual) - float(expected)) / max(1.0, abs(float(expected)))


def receipt_row(receipt: dict[str, Any], grid: str, arm: str) -> dict[str, Any]:
    row = next((item for item in receipt.get("rows", []) if isinstance(item, dict) and item.get("grid") == grid and item.get("arm") == arm), None)
    if not isinstance(row, dict):
        raise ValueError(f"missing receipt row: {grid}_{arm}")
    return row


def trace_sample(row: dict[str, Any], time_value: float) -> dict[str, Any]:
    times = row.get("times")
    trace = row.get("trace")
    if not isinstance(times, list) or not isinstance(trace, list) or len(times) != len(trace):
        raise ValueError("malformed receipt trace")
    for index, candidate in enumerate(times):
        if abs(float(candidate) - time_value) <= 1.0e-12 and isinstance(trace[index], dict):
            return trace[index]
    raise ValueError(f"missing receipt snapshot: {row.get('grid')}_{row.get('arm')}_{time_value}")


def compare_default(actual: dict[str, float], expected: dict[str, Any]) -> dict[str, Any]:
    errors = {name: relative_error(actual[name], float(expected[name])) for name in RECONSTRUCTION_NAMES}
    return {"errors": errors, "max_relative_error": max(errors.values()), "pass": bool(max(errors.values()) <= RECONSTRUCTION_TOL)}


def late_mean(samples: list[dict[str, float]]) -> dict[str, float]:
    names = (
        "energy",
        "charge",
        "core_fraction",
        "core_abs_charge_fraction",
        "core_rms",
        "core_energy",
        "cut_energy",
        "cut_charge",
        "cut_charge_fraction",
        "binding_ratio",
        "shell_energy_fraction",
    )
    return {name: float(np.mean([float(sample[name]) for sample in samples])) for name in names}


def load_primary_snapshot(campaign: Path, row: dict[str, Any], time_value: float) -> tuple[np.ndarray, np.ndarray, Geometry, float]:
    state = next((item for item in row.get("states", []) if isinstance(item, dict) and abs(float(item.get("time")) - time_value) <= 1.0e-12), None)
    if not isinstance(state, dict):
        raise ValueError(f"missing state declaration: {row.get('grid')}_{row.get('arm')}_{time_value}")
    return load_state(state_path(campaign, state), time_value, str(state["sha256"]), int(row["R"]), float(row["spacing"]))


def load_independent_snapshot(archive: Path, item: dict[str, Any], time_value: float) -> tuple[np.ndarray, np.ndarray, Geometry, float]:
    snapshots = item.get("states", [])
    state = next((candidate for candidate in snapshots if isinstance(candidate, dict) and abs(float(candidate.get("time")) - time_value) <= 1.0e-12), None)
    if not isinstance(state, dict):
        raise ValueError(f"missing independent state: {item.get('arm')}_{time_value}")
    return load_state(independent_state_path(archive, state), time_value, str(state["sha256"]), int(item["grid"]), float(item["spacing"]))


def source_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    source_hashes = receipt.get("source_sha256")
    if not isinstance(source_hashes, dict):
        raise ValueError("missing campaign source hashes")
    return {str(key): str(value) for key, value in source_hashes.items()}


def run(campaign: Path, verification_path: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite output: {output}")
    result_path = campaign / "result.json"
    receipt = strict_json(result_path)
    verification = strict_json(verification_path)
    if receipt.get("schema") != CAMPAIGN_SCHEMA:
        raise ValueError("campaign schema mismatch")
    if verification.get("schema") != VERIFICATION_SCHEMA:
        raise ValueError("verification schema mismatch")
    if sha256(result_path) != "c9619d8e431c840b8656ec470ec411ede23614bb20d8b200fbd6f7fd8b356ae9":
        raise ValueError("campaign receipt hash mismatch")
    if sha256(verification_path) != "45755f677b83b11a65f1fb2271f6c85fa4844e068cc482e4cbb1c74a220abf64":
        raise ValueError("verification receipt hash mismatch")

    output.mkdir(parents=True)
    source_hashes = source_summary(receipt)
    baseline_checks: list[dict[str, Any]] = []
    rows_out: list[dict[str, Any]] = []
    snapshot_cache: dict[tuple[str, str, float], tuple[np.ndarray, np.ndarray, Geometry, dict[str, float]]] = {}

    for grid in TARGET_GRIDS:
        for arm in TARGET_ARMS:
            row = receipt_row(receipt, grid, arm)
            initial_charge = float(row["initial"]["charge"])
            initial_energy = float(row["initial"]["energy"])
            snapshots: list[dict[str, Any]] = []
            for time_value in SNAPSHOT_TIMES:
                q, v, geometry, embedded_time = load_primary_snapshot(campaign, row, time_value)
                default = summarize_state(
                    q,
                    v,
                    geometry,
                    HC,
                    initial_charge=initial_charge,
                    initial_energy=initial_energy,
                )
                expected = trace_sample(row, time_value)
                comparison = compare_default(default, expected)
                baseline_checks.append({"source": "primary", "grid": grid, "arm": arm, "time": time_value, **comparison})
                snapshot_cache[(grid, arm, time_value)] = (q, v, geometry, default)
                snapshots.append({
                    "time": time_value,
                    "default": default,
                    "default_reconstruction": comparison,
                    "radial_profile": radial_profile(q, v, geometry, HC),
                })
            late_defaults = [item["default"] for item in snapshots if item["time"] in LATE_TIMES]
            cut_matrix: list[dict[str, Any]] = []
            for inner in CUT_INNERS:
                for width in CUT_WIDTHS:
                    values = []
                    for time_value in LATE_TIMES:
                        q, v, geometry, _ = snapshot_cache[(grid, arm, time_value)]
                        values.append(
                            summarize_state(
                                q,
                                v,
                                geometry,
                                HC,
                                inner,
                                width,
                                initial_charge=initial_charge,
                                initial_energy=initial_energy,
                            )
                        )
                    cut_matrix.append({"inner": inner, "width": width, "late_mean": late_mean(values)})
            rows_out.append({
                "grid": grid,
                "arm": arm,
                "snapshot_count": len(snapshots),
                "snapshots": snapshots,
                "late_default_mean": late_mean(late_defaults),
                "cut_matrix": cut_matrix,
            })

    independent_checks: list[dict[str, Any]] = []
    independent_items = verification.get("independent_evolution", [])
    independent_archive = campaign / "verification_independent_states"
    independent_out: list[dict[str, Any]] = []
    for arm in TARGET_ARMS:
        item = next((candidate for candidate in independent_items if isinstance(candidate, dict) and candidate.get("arm") == arm), None)
        if not isinstance(item, dict):
            raise ValueError(f"missing independent evolution: {arm}")
        snapshots: list[dict[str, Any]] = []
        for time_value in SNAPSHOT_TIMES:
            q, v, geometry, _ = load_independent_snapshot(independent_archive, item, time_value)
            default = summarize_state(
                q,
                v,
                geometry,
                HC,
                initial_charge=float(item["charge_reference"]),
                initial_energy=float(item["energy_reference"]),
            )
            expected = item.get("snapshots", {}).get(str(time_value))
            if not isinstance(expected, dict):
                raise ValueError(f"missing independent scalar snapshot: {arm}_{time_value}")
            comparison = compare_default(default, expected)
            independent_checks.append({"source": "independent", "arm": arm, "time": time_value, **comparison})
            snapshots.append({"time": time_value, "default": default, "default_reconstruction": comparison})
        independent_out.append({"arm": arm, "grid": int(item["grid"]), "spacing": float(item["spacing"]), "snapshots": snapshots})

    matrix_pairs: list[dict[str, Any]] = []
    for arm in TARGET_ARMS:
        grid_means: dict[str, dict[str, float]] = {}
        for grid in TARGET_GRIDS:
            row = next(item for item in rows_out if item["grid"] == grid and item["arm"] == arm)
            grid_means[grid] = {key: float(value) for key, value in row["late_default_mean"].items()}
        for inner in CUT_INNERS:
            for width in CUT_WIDTHS:
                cut_means: dict[str, dict[str, float]] = {}
                for grid in TARGET_GRIDS:
                    row = next(item for item in rows_out if item["grid"] == grid and item["arm"] == arm)
                    candidate = next(item for item in row["cut_matrix"] if item["inner"] == inner and item["width"] == width)
                    cut_means[grid] = candidate["late_mean"]
                for left, right in (("S0", "S1"), ("S1", "S2")):
                    left_mean, right_mean = cut_means[left], cut_means[right]
                    initial_scale = max(
                        1.0,
                        abs(float(receipt_row(receipt, left, arm)["initial"]["energy"])),
                        abs(float(receipt_row(receipt, right, arm)["initial"]["energy"])),
                    )
                    errors = {
                        "cut_energy": abs(left_mean["cut_energy"] - right_mean["cut_energy"]) / initial_scale,
                        "cut_charge": abs(left_mean["cut_charge"] - right_mean["cut_charge"]) / 256.0,
                        "cut_charge_fraction": abs(left_mean["cut_charge_fraction"] - right_mean["cut_charge_fraction"]),
                        "binding_ratio": abs(left_mean["binding_ratio"] - right_mean["binding_ratio"]),
                    }
                    matrix_pairs.append({
                        "arm": arm,
                        "inner": inner,
                        "width": width,
                        "level_pair": f"{left}->{right}",
                        "left": left_mean,
                        "right": right_mean,
                        "errors": errors,
                        "cut_energy_disagrees": bool(
                            errors["cut_energy"] >= COMPONENT_COMPARISON_TOL
                        ),
                        "cut_charge_disagrees": bool(
                            errors["cut_charge"] >= COMPONENT_COMPARISON_TOL
                        ),
                        "binding_within_original_tolerance": bool(
                            errors["binding_ratio"] < COMPONENT_COMPARISON_TOL
                        ),
                        "components_disagree_separately": bool(
                            errors["cut_energy"] >= COMPONENT_COMPARISON_TOL
                            and errors["cut_charge"] >= COMPONENT_COMPARISON_TOL
                        ),
                    })

    reconstruction_checks = baseline_checks + independent_checks
    reconstruction_pass = bool(reconstruction_checks and all(item["pass"] is True for item in reconstruction_checks))
    default_s1_s2 = [item for item in matrix_pairs if item["level_pair"] == "S1->S2" and item["inner"] == 8.0 and item["width"] == 4.0]
    default_pair = next(item for item in rows_out if item["grid"] == "S1" and item["arm"] == "pair256")
    default_antiphase = next(item for item in rows_out if item["grid"] == "S1" and item["arm"] == "antiphase256")
    target_charge_fractions = {
        f"{item['grid']}_{item['arm']}": item["late_default_mean"]["cut_charge_fraction"]
        for item in rows_out
    }
    fixed_core_rows = {}
    for item in rows_out:
        samples = [snapshot["default"] for snapshot in item["snapshots"] if snapshot["time"] in LATE_TIMES]
        maximum = max(float(sample["core_abs_charge_fraction"]) for sample in samples)
        fixed_core_rows[f"{item['grid']}_{item['arm']}"] = {
            "max_core_abs_charge_fraction": maximum,
            "pass": bool(maximum < FIXED_CORE_CHARGE_FRACTION_MAX),
        }
    small_smooth_cut_charge = bool(
        target_charge_fractions
        and max(target_charge_fractions.values()) < FIXED_CORE_CHARGE_FRACTION_MAX
    )
    fixed_core_no_retained = bool(fixed_core_rows and all(item["pass"] for item in fixed_core_rows.values()))
    broad_cut: list[dict[str, Any]] = []
    broad_field_level = False
    if not reconstruction_pass:
        verdict = "INCONCLUSIVE—archive reconstruction failure"
    else:
        broad_cut = [
            item
            for item in matrix_pairs
            if item["level_pair"] == "S1->S2"
            and item["left"]["cut_charge_fraction"] >= FIXED_CORE_CHARGE_FRACTION_MAX
            and item["right"]["cut_charge_fraction"] >= FIXED_CORE_CHARGE_FRACTION_MAX
        ]
        default_binding_fail = any(not item["binding_within_original_tolerance"] for item in default_s1_s2)
        broad_field_level = any(
            not item["binding_within_original_tolerance"]
            and item["components_disagree_separately"]
            for item in broad_cut
        )
        if default_binding_fail and small_smooth_cut_charge and fixed_core_no_retained:
            verdict = "DISPERSIVE—binding ratio is ill-conditioned on the dispersed tail"
        elif broad_field_level:
            verdict = "FIELD-LEVEL—localized dynamics remain unresolved"
        elif max(target_charge_fractions.values()) < FIXED_CORE_CHARGE_FRACTION_MAX:
            verdict = "NO REMNANT—observable robustness does not imply formation"
        else:
            verdict = "INCONCLUSIVE—diagnostic branches do not separate"

    output_record: dict[str, Any] = {
        "schema": SCHEMA,
        "protocol_sha256": sha256(PREREG),
        "campaign": {
            "path": campaign.relative_to(ROOT).as_posix(),
            "result_sha256": sha256(campaign / "result.json"),
            "verification_path": verification_path.relative_to(ROOT).as_posix(),
            "verification_sha256": sha256(verification_path),
            "source_sha256": source_hashes,
        },
        "schedule": {
            "target_grids": list(TARGET_GRIDS),
            "target_arms": list(TARGET_ARMS),
            "snapshot_times": list(SNAPSHOT_TIMES),
            "late_snapshot_times": list(LATE_TIMES),
            "cut_inners": list(CUT_INNERS),
            "cut_widths": list(CUT_WIDTHS),
            "hard_radii": list(HARD_RADII),
        },
        "reconstruction": {
            "pass": reconstruction_pass,
            "tolerance": RECONSTRUCTION_TOL,
            "primary_checks": baseline_checks,
            "independent_checks": independent_checks,
            "max_relative_error": max(item["max_relative_error"] for item in reconstruction_checks),
        },
        "rows": rows_out,
        "independent_rows": independent_out,
        "cut_matrix_comparisons": matrix_pairs,
        "summary": {
            "default_s1_s2_comparisons": default_s1_s2,
            "target_cut_charge_fraction": target_charge_fractions,
            "small_smooth_cut_charge": small_smooth_cut_charge,
            "fixed_core_charge_fraction_threshold": FIXED_CORE_CHARGE_FRACTION_MAX,
            "component_comparison_tolerance": COMPONENT_COMPARISON_TOL,
            "substantial_charge_s1_s2_count": len(broad_cut),
            "field_level_predicate": broad_field_level,
            "fixed_core_rows": fixed_core_rows,
            "fixed_core_no_retained_localized_charge": fixed_core_no_retained,
            "pair_s1_default_late_mean": default_pair["late_default_mean"],
            "antiphase_s1_default_late_mean": default_antiphase["late_default_mean"],
        },
        "verdict": verdict,
    }
    output.joinpath("result.json").write_text(json.dumps(output_record, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return output_record


def smoke() -> None:
    r = np.linspace(0.25, 3.75, 8)
    axial = np.linspace(-3.75, 3.75, 16)
    faces = np.arange(9, dtype=np.float64) * 0.5
    volume = (math.pi * (faces[1:] ** 2 - faces[:-1] ** 2) * 0.5)[:, None]
    geometry = Geometry(4, 0.5, r, axial, volume)
    validate_geometry(geometry)
    q = np.zeros((3, 8, 16), dtype=np.float64)
    v = np.zeros_like(q)
    q[1] = np.exp(-(geometry.distance**2) / 8.0)
    v[2] = -OMEGA_INF * q[1]
    sample = summarize_state(q, v, geometry, HC)
    if not all(finite_number(value) for value in sample.values()):
        raise RuntimeError("nonfinite smoke diagnostic")
    print(json.dumps({"smoke": "PASS", "binding_ratio": sample["binding_ratio"], "cut_charge_fraction": sample["cut_charge_fraction"]}))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument("--verification", type=Path, default=DEFAULT_VERIFICATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        smoke()
        return 0
    result = run(args.campaign.resolve(), args.verification.resolve(), args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), "reconstruction_pass": result["reconstruction"]["pass"], "verdict": result["verdict"]}))
    return 0 if result["reconstruction"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
