#!/usr/bin/env python3
"""Primary finite-charge radial-cloud campaign (frozen report §§25.1, 35.1–35.2)."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "computations" / "matter-formation-continuum-report.md"
SCHEMA = "matter-formation-radial-cloud-primary-v1"
EXPECTED_SECTION_HASHES = {
    "derivation": "7ca0aae5db20f582fa65989b34d8a1c2355315bcf06b2c558d08f5442d66cdfd",
    "protocol": "8f43b8a57a1f1bd5bf52e1dbd983db1cf2e34e47f70a8917ca1c021957044972",
    "parent": "dce41f8119dd782a4d5593d93ad96a03fad6558bcd3711b8e729803e73e72e6a",
}
HEADINGS = {
    "derivation": "### 35.1 Finite-charge energy and dynamical conditions",
    "protocol": "### 35.2 Radial cloud calculation: pre-execution criteria",
    "parent": "### 25.1 Exact carrier-free periodic background",
}
CONSTANTS = {
    "a": 1.0 / 16.0,
    "c_psi": 1.0 / 8.0,
    "u_rho": 4.0,
    "u_C": 1.0,
    "k_Cx": 1.0,
    "e_C": 3.0 / 4.0,
    "h_C": 2.9598260763447164,
    "charge": 256.0,
}
B = CONSTANTS["e_C"] + 1.0 / (4.0 * CONSTANTS["a"])
OMEGA_INF = math.sqrt(B / CONSTANTS["a"])
GRID_SCHEDULE = (
    ("G0", 192, 1.0 / 16.0, 1.0 / 256.0),
    ("G1", 192, 1.0 / 32.0, 1.0 / 256.0),
    ("G2", 384, 1.0 / 16.0, 1.0 / 256.0),
    ("T1", 192, 1.0 / 32.0, 1.0 / 512.0),
)
BASE_ARMS = ("coupled_w4", "coupled_w8", "uncoupled_w4", "uncoupled_w8")
ALL_ARMS = {
    "G0": BASE_ARMS + ("conjugate_w4", "vacuum"),
    "G1": BASE_ARMS,
    "G2": BASE_ARMS,
    "T1": BASE_ARMS,
}
DIAGNOSTIC_NAMES = (
    "energy", "charge", "charge_l1", "core_charge", "core_fraction", "core_rms",
    "central_f", "central_n", "outer_energy", "core_charge_derivative",
    "core_current", "current_residual",
)


def raw_sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_sha_bytes(data: bytes) -> str:
    return raw_sha_bytes(canonical_bytes(data))


def raw_sha(path: Path) -> str:
    return raw_sha_bytes(path.read_bytes())


def finite_json(value: Any) -> bool:
    if isinstance(value, (float, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, (int, np.integer, str, bool)) or value is None:
        return True
    if isinstance(value, dict):
        return all(isinstance(k, str) and finite_json(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_json(v) for v in value)
    return False


def write_exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)


def write_json(path: Path, value: dict[str, Any]) -> None:
    if not finite_json(value):
        raise ValueError(f"non-finite JSON payload at {path}")
    write_exclusive(path, (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"))


def extract_section(data: bytes, heading: str) -> tuple[str, str]:
    text = canonical_bytes(data).decode("utf-8")
    lines = text.splitlines()
    matches = [i for i, line in enumerate(lines) if line.rstrip() == heading]
    if len(matches) != 1:
        raise ValueError(f"heading occurs {len(matches)} times: {heading}")
    start = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.match(r"^#{1,3}\s", lines[index]):
            end = index
            break
    section = "\n".join(lines[start:end]).rstrip() + "\n"
    return section, raw_sha_bytes(section.encode("utf-8"))


def library_versions() -> dict[str, str]:
    versions: dict[str, str] = {"python": platform.python_version(), "numpy": np.__version__}
    for package in ("scipy", "sympy"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "unavailable"
    return versions


def source_identity() -> dict[str, str]:
    data = Path(__file__).read_bytes()
    return {
        "path": Path(__file__).resolve().relative_to(ROOT.resolve()).as_posix(),
        "sha256": raw_sha_bytes(data),
        "canonical_sha256": canonical_sha_bytes(data),
    }


def freeze_inputs(note: Path) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    failures: list[str] = []
    sections: dict[str, str] = {}
    actual: dict[str, str] = {}
    if not note.is_file():
        failures.append(f"missing note: {note}")
        return {"note": str(note), "note_raw_sha256": None, "sections": {}}, sections, failures
    data = note.read_bytes()
    frozen: dict[str, Any] = {
        "note": str(note.resolve().relative_to(ROOT.resolve()).as_posix()) if note.resolve().is_relative_to(ROOT.resolve()) else str(note.resolve()),
        "note_raw_sha256": raw_sha_bytes(data),
        "note_canonical_sha256": canonical_sha_bytes(data),
        "sections": {},
    }
    for key, heading in HEADINGS.items():
        try:
            section, digest = extract_section(data, heading)
            sections[key] = section
            actual[key] = digest
            frozen["sections"][key] = {"heading": heading, "sha256": digest, "expected_sha256": EXPECTED_SECTION_HASHES[key]}
            if digest != EXPECTED_SECTION_HASHES[key]:
                failures.append(f"altered frozen section: {key}")
        except (UnicodeDecodeError, ValueError) as exc:
            frozen["sections"][key] = {"heading": heading, "sha256": None, "expected_sha256": EXPECTED_SECTION_HASHES[key]}
            failures.append(str(exc))
    return frozen, sections, failures


def grid_arrays(R: int, dr: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = int(round(R / dr))
    face = np.arange(n + 1, dtype=np.float64) * dr
    r = (np.arange(n, dtype=np.float64) + 0.5) * dr
    volumes = (4.0 * math.pi / 3.0) * (face[1:] ** 3 - face[:-1] ** 3)
    internal_w = 4.0 * math.pi * face[1:-1] ** 2 / dr
    outer_w = 8.0 * math.pi * float(R) ** 2 / dr
    return r, volumes, face, internal_w, np.array([outer_w], dtype=np.float64)


def spatial_gradient(q: np.ndarray, internal_w: np.ndarray, outer_w: float, boundary: float) -> np.ndarray:
    result = np.zeros_like(q)
    diff = q[:, :-1] - q[:, 1:]
    result[:, :-1] += diff * internal_w[None, :]
    result[:, 1:] -= diff * internal_w[None, :]
    result[:, -1] += (q[:, -1] - boundary) * outer_w
    return result


def accelerations(
    f: np.ndarray, zr: np.ndarray, zi: np.ndarray, internal_w: np.ndarray, outer_w: float,
    volumes: np.ndarray, h_value: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        n = zr * zr + zi * zi
        gf = spatial_gradient(f, internal_w, outer_w, 1.0)
        gz_r = spatial_gradient(zr, internal_w, outer_w, 0.0)
        gz_i = spatial_gradient(zi, internal_w, outer_w, 0.0)
        af = -(gf / volumes[None, :] + CONSTANTS["u_rho"] * (f * f - 1.0) * f + 2.0 * h_value[:, None] * f * n) / CONSTANTS["c_psi"]
        coeff = B - h_value[:, None] + h_value[:, None] * f * f + CONSTANTS["u_C"] * n
        azr = -(gz_r / (2.0 * CONSTANTS["a"] * volumes[None, :]) + coeff * zr / CONSTANTS["a"])
        azi = -(gz_i / (2.0 * CONSTANTS["a"] * volumes[None, :]) + coeff * zi / CONSTANTS["a"])
    return af, azr, azi


def all_finite(*arrays: np.ndarray) -> np.ndarray:
    good = np.ones(arrays[0].shape[0], dtype=bool)
    for array in arrays:
        good &= np.all(np.isfinite(array), axis=1)
    return good


def diagnostics(
    f: np.ndarray, zr: np.ndarray, zi: np.ndarray, vf: np.ndarray, vzr: np.ndarray, vzi: np.ndarray,
    af: np.ndarray, azr: np.ndarray, azi: np.ndarray, r: np.ndarray, volumes: np.ndarray,
    face: np.ndarray, internal_w: np.ndarray, outer_w: float, h_value: np.ndarray,
    initial_charge: np.ndarray,
) -> np.ndarray:
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        n = zr * zr + zi * zi
        rho = -2.0 * CONSTANTS["a"] * (zr * vzi - zi * vzr)
        cell_potential = (
            CONSTANTS["u_rho"] / 4.0 * (f * f - 1.0) ** 2
            + (B - h_value[:, None] + h_value[:, None] * f * f) * n
            + CONSTANTS["u_C"] / 2.0 * n * n
        )
        cell_kinetic = CONSTANTS["c_psi"] / 2.0 * vf * vf + CONSTANTS["a"] * (vzr * vzr + vzi * vzi)
        grad_f = 0.5 * np.sum(internal_w[None, :] * (f[:, :-1] - f[:, 1:]) ** 2, axis=1) + 0.5 * outer_w * (f[:, -1] - 1.0) ** 2
        grad_z = 0.5 * np.sum(internal_w[None, :] * ((zr[:, :-1] - zr[:, 1:]) ** 2 + (zi[:, :-1] - zi[:, 1:]) ** 2), axis=1) + 0.5 * outer_w * (zr[:, -1] ** 2 + zi[:, -1] ** 2)
        energy = np.sum(volumes[None, :] * (cell_potential + cell_kinetic), axis=1) + grad_f + CONSTANTS["k_Cx"] * grad_z
        charge = np.sum(volumes[None, :] * rho, axis=1)
        charge_l1 = np.sum(volumes[None, :] * np.abs(rho), axis=1)
        core = r < 8.0
        abs_core = np.sum(volumes[None, core] * np.abs(rho[:, core]), axis=1)
        core_charge = np.sum(volumes[None, core] * rho[:, core], axis=1)
        core_rms = np.sqrt(np.divide(np.sum(volumes[None, core] * np.abs(rho[:, core]) * r[None, core] ** 2, axis=1), abs_core, out=np.zeros_like(abs_core), where=abs_core != 0.0))
        core_derivative = np.sum(volumes[None, core] * (-2.0 * CONSTANTS["a"] * (zr[:, core] * azi[:, core] - zi[:, core] * azr[:, core])), axis=1)
        face_index = int(round(8.0 / (face[1] - face[0])))
        current = 4.0 * math.pi * 8.0 ** 2 * CONSTANTS["k_Cx"] * (zr[:, face_index - 1] * zi[:, face_index] - zi[:, face_index - 1] * zr[:, face_index]) / (face[1] - face[0])
        current_residual = np.abs(core_derivative + current) / np.maximum(1.0, np.maximum(np.abs(core_derivative), np.abs(current)))
        outer = r > 128.0
        outer_energy = np.sum(volumes[None, outer] * (cell_potential[:, outer] + cell_kinetic[:, outer]), axis=1)
        outer_faces = face[1:] >= 128.0
        face_f = 0.5 * internal_w[None, :] * (f[:, :-1] - f[:, 1:]) ** 2
        face_z = 0.5 * CONSTANTS["k_Cx"] * internal_w[None, :] * ((zr[:, :-1] - zr[:, 1:]) ** 2 + (zi[:, :-1] - zi[:, 1:]) ** 2)
        outer_energy += np.sum((face_f + face_z)[:, outer_faces[:-1]], axis=1)
        if outer_faces[-1]:
            outer_energy += 0.5 * outer_w * ((f[:, -1] - 1.0) ** 2 + CONSTANTS["k_Cx"] * (zr[:, -1] ** 2 + zi[:, -1] ** 2))
        core_fraction = np.divide(core_charge, initial_charge, out=np.zeros_like(core_charge), where=initial_charge != 0.0)
        result = np.column_stack((
            energy, charge, charge_l1, core_charge, core_fraction, core_rms,
            f[:, 0], n[:, 0], outer_energy, core_derivative, current, current_residual,
        ))
    return result


def initial_state(r: np.ndarray, volumes: np.ndarray, arms: tuple[str, ...]) -> tuple[np.ndarray, ...]:
    count, n = len(arms), r.size
    f = np.ones((count, n), dtype=np.float64)
    vf = np.zeros_like(f)
    zr = np.zeros_like(f)
    zi = np.zeros_like(f)
    vzr = np.zeros_like(f)
    vzi = np.zeros_like(f)
    norm_factor = 256.0 / (2.0 * CONSTANTS["a"] * OMEGA_INF)
    for arm_index, arm in enumerate(arms):
        if arm == "vacuum":
            continue
        width = 8.0 if arm.endswith("w8") else 4.0
        shape = np.exp(-r * r / (2.0 * width * width))
        amplitude = math.sqrt(norm_factor / float(np.sum(volumes * shape * shape)))
        zr[arm_index] = amplitude * shape
        sign = 1.0
        if arm == "conjugate_w4":
            sign = -1.0
        vzi[arm_index] = -sign * OMEGA_INF * zr[arm_index]
    return f, vf, zr, zi, vzr, vzi


def row_metrics(diag: np.ndarray, t: np.ndarray, completed: bool) -> dict[str, Any]:
    finite = np.all(np.isfinite(diag), axis=1)
    valid = diag[finite]
    if valid.size == 0:
        return {
            "energy_relative_drift": None, "charge_relative_drift": None, "current_residual_max": None,
            "early_outer_energy_fraction_max": None,
            "late_means": {"core_fraction": None, "core_rms": None, "central_f2": None, "central_n": None},
            "late_min_core_fraction": None, "late_max_central_f2": None,
        }
    e0, q0 = float(valid[0, 0]), float(valid[0, 1])
    energy_drift = float(np.max(np.abs(valid[:, 0] - e0)) / max(1.0, abs(e0)))
    charge_drift = None if abs(q0) < 1.0e-30 else float(np.max(np.abs(valid[:, 1] - q0)) / 256.0)
    early = finite & (t <= 16.0 + 1.0e-12)
    early_fraction = float(np.max(np.abs(diag[early, 8]) / np.maximum(1.0, np.abs(diag[early, 0])))) if np.any(early) else None
    late = finite & (t >= 32.0 - 1.0e-12) & (t <= 48.0 + 1.0e-12)
    if np.any(late):
        late_means = {
            "core_fraction": float(np.mean(diag[late, 4])), "core_rms": float(np.mean(diag[late, 5])),
            "central_f2": float(np.mean(diag[late, 6] ** 2)), "central_n": float(np.mean(diag[late, 7])),
        }
        late_min = float(np.min(diag[late, 4]))
        late_max = float(np.max(diag[late, 6] ** 2))
    else:
        late_means = {"core_fraction": None, "core_rms": None, "central_f2": None, "central_n": None}
        late_min, late_max = None, None
    return {
        "energy_relative_drift": energy_drift,
        "charge_relative_drift": charge_drift,
        "current_residual_max": float(np.nanmax(diag[:, 11])) if np.any(np.isfinite(diag[:, 11])) else None,
        "early_outer_energy_fraction_max": early_fraction,
        "late_means": late_means,
        "late_min_core_fraction": late_min,
        "late_max_central_f2": late_max,
        "completed": bool(completed),
    }


def evolve_grid(grid: tuple[str, int, float, float], arms: tuple[str, ...], output: Path) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    tag, R, dr, dt = grid
    r, volumes, face, internal_w, outer_array = grid_arrays(R, dr)
    outer_w = float(outer_array[0])
    count, n = len(arms), r.size
    f, vf, zr, zi, vzr, vzi = initial_state(r, volumes, arms)
    initial_charge = np.array([0.0 if arm == "vacuum" else (-CONSTANTS["charge"] if arm == "conjugate_w4" else CONSTANTS["charge"]) for arm in arms], dtype=np.float64)
    h_value = np.array([0.0 if arm.startswith("uncoupled") else CONSTANTS["h_C"] for arm in arms], dtype=np.float64)
    t = np.arange(385, dtype=np.float64) / 8.0
    diag = np.full((count, 385, 12), np.nan, dtype=np.float64)
    fields = np.full((count, 49, 6, n), np.nan, dtype=np.float64)
    af, azr, azi = accelerations(f, zr, zi, internal_w, outer_w, volumes, h_value)
    active = all_finite(f, vf, zr, zi, vzr, vzi, af, azr, azi)
    d0 = diagnostics(f, zr, zi, vf, vzr, vzi, af, azr, azi, r, volumes, face, internal_w, outer_w, h_value, initial_charge)
    diag[:, 0, :] = d0
    fields[:, 0, 0] = f
    fields[:, 0, 1] = vf
    fields[:, 0, 2] = zr
    fields[:, 0, 3] = zi
    fields[:, 0, 4] = vzr
    fields[:, 0, 5] = vzi
    steps = int(round(48.0 / dt))
    diag_stride = int(round((1.0 / 8.0) / dt))
    snap_stride = int(round(1.0 / dt))
    for step in range(1, steps + 1):
        old_active = active.copy()
        vf_trial = vf + 0.5 * dt * af
        vzr_trial = vzr + 0.5 * dt * azr
        vzi_trial = vzi + 0.5 * dt * azi
        f_trial = f + dt * vf_trial
        zr_trial = zr + dt * vzr_trial
        zi_trial = zi + dt * vzi_trial
        af_trial, azr_trial, azi_trial = accelerations(f_trial, zr_trial, zi_trial, internal_w, outer_w, volumes, h_value)
        good = old_active & all_finite(f_trial, zr_trial, zi_trial, vf_trial, vzr_trial, vzi_trial, af_trial, azr_trial, azi_trial)
        failed = old_active & ~good
        active[failed] = False
        f[good], zr[good], zi[good] = f_trial[good], zr_trial[good], zi_trial[good]
        vf[good] = vf_trial[good] + 0.5 * dt * af_trial[good]
        vzr[good] = vzr_trial[good] + 0.5 * dt * azr_trial[good]
        vzi[good] = vzi_trial[good] + 0.5 * dt * azi_trial[good]
        af[good], azr[good], azi[good] = af_trial[good], azr_trial[good], azi_trial[good]
        active &= all_finite(vf, vzr, vzi)
        if step % diag_stride == 0:
            index = step // diag_stride
            d = diagnostics(f, zr, zi, vf, vzr, vzi, af, azr, azi, r, volumes, face, internal_w, outer_w, h_value, initial_charge)
            diag[active, index, :] = d[active]
        if step % snap_stride == 0:
            index = step // snap_stride
            fields[active, index, 0] = f[active]
            fields[active, index, 1] = vf[active]
            fields[active, index, 2] = zr[active]
            fields[active, index, 3] = zi[active]
            fields[active, index, 4] = vzr[active]
            fields[active, index, 5] = vzi[active]
    records: list[dict[str, Any]] = []
    arrays: dict[str, np.ndarray] = {}
    for arm_index, arm in enumerate(arms):
        filename = f"{tag}_{arm}.npz"
        archive = output / filename
        payload = {"r": r, "volumes": volumes, "t": t, "diagnostics": diag[arm_index], "snapshot_t": np.arange(49, dtype=np.float64), "fields": fields[arm_index]}
        with archive.open("xb") as stream:
            np.savez_compressed(stream, **payload)
        completed = bool(active[arm_index])
        metrics = row_metrics(diag[arm_index], t, completed)
        records.append({"grid": tag, "arm": arm, "R": int(R), "dr": float(dr), "dt": float(dt), "fields_file": filename, "completed": completed, "numerical_pass": False, "metrics": metrics})
        arrays[f"{tag}:{arm}"] = diag[arm_index]
    return records, arrays


def compare_rows(rows: list[dict[str, Any]], left_grid: str, right_grid: str, arms: tuple[str, ...]) -> list[dict[str, Any]]:
    metrics = ("core_fraction", "core_rms", "central_f2", "central_n")
    result: list[dict[str, Any]] = []
    for arm in arms:
        left = next((row for row in rows if row["grid"] == left_grid and row["arm"] == arm), None)
        right = next((row for row in rows if row["grid"] == right_grid and row["arm"] == arm), None)
        for metric in metrics:
            x = left["metrics"]["late_means"].get(metric) if left else None
            y = right["metrics"]["late_means"].get(metric) if right else None
            passed = x is not None and y is not None and math.isfinite(float(x)) and math.isfinite(float(y)) and abs(float(x) - float(y)) < 0.02 * max(1.0, abs(float(x)), abs(float(y)))
            result.append({"name": f"{left_grid}:{right_grid}:{arm}:{metric}", "pass": bool(passed), "left": x, "right": y, "absolute_difference": None if x is None or y is None else abs(float(x) - float(y)), "tolerance": None if x is None or y is None else 0.02 * max(1.0, abs(float(x)), abs(float(y)))})
    return result


def empty_receipt(identity: dict[str, Any], failures: list[str], checks: list[dict[str, Any]], artifacts: list[dict[str, str]]) -> dict[str, Any]:
    return {"schema": SCHEMA, "numerical_pass": False, "verdict": "INCONCLUSIVE", "complete_physical_matter_formation": False, "failures": failures, "identities": identity, "artifacts": artifacts, "rows": [], "checks": checks, "comparisons": [], "condensation": {}, "library_versions": library_versions()}


def run(args: argparse.Namespace) -> int:
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing existing output directory: {output}")
    output.mkdir(parents=True, exist_ok=False)
    note = args.note.resolve()
    frozen, sections, freeze_failures = freeze_inputs(note)
    identities: dict[str, Any] = {"source": source_identity(), "frozen": frozen, "expected_section_hashes": EXPECTED_SECTION_HASHES, "constants": CONSTANTS, "B": B, "omega_inf": OMEGA_INF, "schedule": [{"grid": g, "R": R, "dr": dr, "dt": dt, "arms": ALL_ARMS[g]} for g, R, dr, dt in GRID_SCHEDULE]}
    artifacts: list[dict[str, str]] = []
    source_data = Path(__file__).read_bytes()
    write_exclusive(output / "program_source.py", source_data)
    artifacts.append({"path": "program_source.py", "sha256": raw_sha(output / "program_source.py")})
    for key, filename in (("derivation", "derivation.txt"), ("protocol", "protocol.txt"), ("parent", "parent.txt")):
        if key in sections:
            write_exclusive(output / filename, sections[key].encode("utf-8"))
            artifacts.append({"path": filename, "sha256": raw_sha(output / filename)})
    checks: list[dict[str, Any]] = [{"name": "frozen_inputs", "pass": not freeze_failures, "failures": freeze_failures}]
    if freeze_failures:
        receipt = empty_receipt(identities, freeze_failures, checks, artifacts)
        write_json(output / "results.json", receipt)
        return 1
    rows: list[dict[str, Any]] = []
    by_grid: dict[str, list[dict[str, Any]]] = {}
    for grid in GRID_SCHEDULE:
        grid_rows, _ = evolve_grid(grid, ALL_ARMS[grid[0]], output)
        by_grid[grid[0]] = grid_rows
        rows.extend(grid_rows)
        for row in grid_rows:
            archive = output / row["fields_file"]
            artifacts.append({"path": row["fields_file"], "sha256": raw_sha(archive)})
    for row in rows:
        limits = (
            ("energy_relative_drift", 2.0e-3),
            ("charge_relative_drift", 1.0e-7),
            ("current_residual_max", 1.0e-10),
            ("early_outer_energy_fraction_max", 1.0e-4),
        )
        row["numerical_pass"] = bool(row["completed"] and (
            row["arm"] == "vacuum" or all(
                row["metrics"][key] is not None and row["metrics"][key] < limit
                for key, limit in limits
            )
        ))
    charged_rows = [row for row in rows if row["arm"] != "vacuum"]
    complete_pass = all(row["completed"] for row in rows)
    energy_pass = all(row["metrics"]["energy_relative_drift"] is not None and row["metrics"]["energy_relative_drift"] < 2.0e-3 for row in charged_rows)
    charge_pass = all(row["metrics"]["charge_relative_drift"] is not None and row["metrics"]["charge_relative_drift"] < 1.0e-7 for row in charged_rows)
    current_pass = all(row["metrics"]["current_residual_max"] is not None and row["metrics"]["current_residual_max"] < 1.0e-10 for row in charged_rows)
    outer_pass = all(row["metrics"]["early_outer_energy_fraction_max"] is not None and row["metrics"]["early_outer_energy_fraction_max"] < 1.0e-4 for row in charged_rows)
    checks.extend([
        {"name": "all_rows_completed", "pass": complete_pass, "count": len(rows), "completed": sum(bool(row["completed"]) for row in rows)},
        {"name": "energy_drift", "pass": energy_pass, "maximum": max((row["metrics"]["energy_relative_drift"] for row in charged_rows if row["metrics"]["energy_relative_drift"] is not None), default=None), "threshold": 2.0e-3},
        {"name": "charge_drift", "pass": charge_pass, "maximum": max((row["metrics"]["charge_relative_drift"] for row in charged_rows if row["metrics"]["charge_relative_drift"] is not None), default=None), "threshold": 1.0e-7},
        {"name": "current_identity", "pass": current_pass, "maximum": max((row["metrics"]["current_residual_max"] for row in charged_rows if row["metrics"]["current_residual_max"] is not None), default=None), "threshold": 1.0e-10},
        {"name": "early_outer_energy", "pass": outer_pass, "maximum": max((row["metrics"]["early_outer_energy_fraction_max"] for row in charged_rows if row["metrics"]["early_outer_energy_fraction_max"] is not None), default=None), "threshold": 1.0e-4},
    ])
    vacuum = next(row for row in rows if row["arm"] == "vacuum")
    with np.load(output / vacuum["fields_file"], allow_pickle=False) as archive:
        vacuum_fields = archive["fields"]
        vacuum_diag = archive["diagnostics"]
    vacuum_finite = bool(np.all(np.isfinite(vacuum_fields)) and np.all(np.isfinite(vacuum_diag)))
    vacuum_field_error = max(float(np.max(np.abs(vacuum_fields[:, 0] - 1.0))), float(np.max(np.abs(vacuum_fields[:, 1:])))) if vacuum_finite else None
    vacuum_energy_error = float(np.max(np.abs(vacuum_diag[:, 0]))) if vacuum_finite else None
    vacuum_pass = bool(vacuum_finite and vacuum_field_error < 1.0e-12 and vacuum_energy_error < 1.0e-12)
    vacuum["numerical_pass"] = bool(vacuum["completed"] and vacuum_pass)
    checks.append({"name": "vacuum_control", "pass": vacuum_pass, "maximum_field_error": vacuum_field_error, "maximum_energy_error": vacuum_energy_error, "threshold": 1.0e-12})
    conjugate_pass = False
    with np.load(output / "G0_coupled_w4.npz", allow_pickle=False) as coupled, np.load(output / "G0_conjugate_w4.npz", allow_pickle=False) as conjugate:
        lhs, rhs = coupled["fields"], conjugate["fields"].copy()
        rhs[:, 3] *= -1.0
        rhs[:, 5] *= -1.0
        conjugate_finite = bool(np.all(np.isfinite(lhs)) and np.all(np.isfinite(rhs)))
        if conjugate_finite:
            scales = np.maximum(1.0, np.max(np.abs(lhs), axis=(0, 2)))
            errors = np.max(np.abs(lhs - rhs), axis=(0, 2))
            conjugate_error = float(np.max(errors))
            conjugate_pass = bool(np.all(errors <= 1.0e-11 * scales))
        else:
            conjugate_error = None
    checks.append({"name": "charge_conjugation", "pass": conjugate_pass, "maximum_error": conjugate_error, "threshold_scale": 1.0e-11})
    comparisons = compare_rows(rows, "G0", "G1", BASE_ARMS) + compare_rows(rows, "G0", "G2", BASE_ARMS) + compare_rows(rows, "G1", "T1", BASE_ARMS)
    checks.append({"name": "scheduled_comparisons", "pass": all(item["pass"] for item in comparisons), "count": len(comparisons), "passed": sum(bool(item["pass"]) for item in comparisons)})
    coupled_by_width: dict[str, dict[str, Any]] = {}
    for width in (4, 8):
        selected = [row for row in rows if row["arm"] == f"coupled_w{width}"]
        controls = [row for row in rows if row["arm"] == f"uncoupled_w{width}"]
        criteria = all(row["metrics"]["late_min_core_fraction"] is not None and row["metrics"]["late_min_core_fraction"] >= 0.5 and row["metrics"]["late_max_central_f2"] is not None and row["metrics"]["late_max_central_f2"] <= 0.25 for row in selected)
        control_gap = all(row["metrics"]["late_means"]["core_fraction"] is not None and selected[i]["metrics"]["late_means"]["core_fraction"] is not None and selected[i]["metrics"]["late_means"]["core_fraction"] - row["metrics"]["late_means"]["core_fraction"] >= 0.20 for i, row in enumerate(controls))
        coupled_by_width[str(width)] = {"primary_criteria_pass": bool(criteria), "control_gap_pass": bool(control_gap), "coupled_rows": [row["grid"] for row in selected], "control_rows": [row["grid"] for row in controls], "scope": "primary-only; joint verdict requires independent evolution"}
    all_checks_pass = all(bool(item["pass"]) for item in checks)
    failures = [item["name"] for item in checks if not item["pass"]]
    receipt = {"schema": SCHEMA, "numerical_pass": bool(all_checks_pass), "verdict": "INCONCLUSIVE", "complete_physical_matter_formation": False, "failures": failures, "identities": identities, "artifacts": artifacts, "rows": rows, "checks": checks, "comparisons": comparisons, "condensation": coupled_by_width, "library_versions": library_versions()}
    write_json(output / "results.json", receipt)
    return 0 if all_checks_pass else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--note", type=Path, default=REPORT)
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"radial-cloud primary failed before receipt: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
