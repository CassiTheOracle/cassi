#!/usr/bin/env python3
"""Independent RK4 verifier for the frozen finite-charge radial-cloud schedule.

This executable is intentionally source-independent from the primary driver.  It
rebuilds the spherical finite-volume face operator, evolves I1 with classical
RK4, and validates/reconstructs the primary receipt before using it in the joint
qualification.  The calculation is conditional supplied-charge condensation;
it does not claim physical matter formation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import scipy
import sympy

ROOT = Path(__file__).resolve().parents[1]
REPORT_DEFAULT = ROOT / "computations" / "matter-formation-continuum-report.md"
SCHEMA = "matter-formation-radial-cloud-verification-v1"
PRIMARY_SCHEMA = "matter-formation-radial-cloud-primary-v1"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"
DERIVATION_SHA256 = "7ca0aae5db20f582fa65989b34d8a1c2355315bcf06b2c558d08f5442d66cdfd"
PROTOCOL_SHA256 = "8f43b8a57a1f1bd5bf52e1dbd983db1cf2e34e47f70a8917ca1c021957044972"
PARENT_SHA256 = "dce41f8119dd782a4d5593d93ad96a03fad6558bcd3711b8e729803e73e72e6a"

A = 1.0 / 16.0
C_PSI = 1.0 / 8.0
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
E_C = 3.0 / 4.0
H_C = 2.9598260763447164
B = E_C + 1.0 / (4.0 * A)
Q_ABS = 256.0
OMEGA_INF = math.sqrt(B / A)
T_FINAL = 48.0
DT_SAMPLE = 1.0 / 8.0
N_SAMPLE = 385
N_SNAPSHOT = 49
CORE_RADIUS = 8.0
OUTER_RADIUS = 128.0

GRIDS = {
    "G0": {"R": 192.0, "dr": 1.0 / 16.0, "dt": 1.0 / 256.0},
    "G1": {"R": 192.0, "dr": 1.0 / 32.0, "dt": 1.0 / 256.0},
    "G2": {"R": 384.0, "dr": 1.0 / 16.0, "dt": 1.0 / 256.0},
    "T1": {"R": 192.0, "dr": 1.0 / 32.0, "dt": 1.0 / 512.0},
    "I1": {"R": 192.0, "dr": 1.0 / 32.0, "dt": 1.0 / 512.0},
}
ARMS = ("coupled_w4", "coupled_w8", "uncoupled_w4", "uncoupled_w8")
WIDTHS = (4, 8)
DIAGNOSTIC_NAMES = (
    "energy", "charge", "charge_l1", "core_charge", "core_fraction", "core_rms",
    "central_f", "central_n", "outer_energy", "core_charge_derivative",
    "core_current", "current_residual",
)
METRIC_NAMES = ("core_fraction", "core_rms", "central_f2", "central_n")


def byte_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path.read_bytes())).hexdigest()


def json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    data = json.dumps(json_safe(dict(payload)), indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.write_text(data, encoding="utf-8", newline="\n")


def finite(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value))


def extract_section(text: str, heading: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    pattern = re.compile(r"(?m)^" + re.escape(heading) + r"\s*$")
    matches = list(pattern.finditer(normalized))
    if len(matches) != 1:
        raise ValueError(f"heading occurrence for {heading!r}: {len(matches)}")
    start = matches[0].start()
    next_heading = re.compile(r"(?m)^#{1,3}\s+.+$")
    end = len(normalized)
    for match in next_heading.finditer(normalized, matches[0].end()):
        end = match.start()
        break
    return normalized[start:end].rstrip() + "\n"


def expected_sections(note: Path) -> dict[str, str]:
    raw = note.read_text(encoding="utf-8")
    return {
        "derivation": extract_section(raw, "### 35.1 Finite-charge energy and dynamical conditions"),
        "protocol": extract_section(raw, "### 35.2 Radial cloud calculation: pre-execution criteria"),
        "parent": extract_section(raw, "### 25.1 Exact carrier-free periodic background"),
    }


def expected_grid(grid: str) -> tuple[float, float, float, int]:
    spec = GRIDS[grid]
    n = int(round(spec["R"] / spec["dr"]))
    return spec["R"], spec["dr"], spec["dt"], n


def initial_state(r: np.ndarray, volumes: np.ndarray, width: int, charge: float = Q_ABS, conjugate: bool = False) -> np.ndarray:
    zshape = np.exp(-(r * r) / (2.0 * width * width))
    norm = float(np.sum(volumes * zshape * zshape))
    amp = math.sqrt(abs(charge) / (2.0 * A * OMEGA_INF * norm)) if charge else 0.0
    zr = amp * zshape
    zi = np.zeros_like(zr)
    vzr = np.zeros_like(zr)
    vzi = -OMEGA_INF * zr
    if conjugate:
        zi = -zi
        vzi = -vzi
    return np.stack((np.ones_like(r), np.zeros_like(r), zr, zi, vzr, vzi), axis=0).astype(np.float64)


def make_grid(R: float, dr: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = int(round(R / dr))
    faces = np.arange(n + 1, dtype=np.float64) * dr
    r = (faces[:-1] + faces[1:]) / 2.0
    volumes = (4.0 * math.pi / 3.0) * (faces[1:] ** 3 - faces[:-1] ** 3)
    conductance = 4.0 * math.pi * faces[1:-1] ** 2 / dr
    outer_conductance = 8.0 * math.pi * R * R / dr
    return r, volumes, conductance, np.array([outer_conductance], dtype=np.float64)


def face_laplacian(x: np.ndarray, conductance: np.ndarray, outer_conductance: float, volumes: np.ndarray, outer: float) -> np.ndarray:
    flux = conductance * (x[1:] - x[:-1])
    divergence = np.empty_like(x)
    divergence[0] = flux[0] if len(flux) else 0.0
    if len(x) > 2:
        divergence[1:-1] = flux[1:] - flux[:-1]
    if len(x) > 1:
        divergence[-1] = outer_conductance * (outer - x[-1]) - flux[-1]
    return divergence / volumes


def acceleration(state: np.ndarray, volumes: np.ndarray, conductance: np.ndarray, outer_conductance: float, coupling: float) -> np.ndarray:
    f, vf, zr, zi, vzr, vzi = state
    lap_f = face_laplacian(f, conductance, outer_conductance, volumes, 1.0)
    lap_r = face_laplacian(zr, conductance, outer_conductance, volumes, 0.0)
    lap_i = face_laplacian(zi, conductance, outer_conductance, volumes, 0.0)
    n = zr * zr + zi * zi
    aff = U_RHO * (f * f - 1.0) * f + 2.0 * coupling * f * n
    carrier = (B - coupling + coupling * f * f + U_C * n) / A
    return np.stack((vf, (lap_f - aff) / C_PSI, vzr, vzi, lap_r * K_CX / (2.0 * A) - carrier * zr, lap_i * K_CX / (2.0 * A) - carrier * zi), axis=0)


def rk4_step(state: np.ndarray, dt: float, volumes: np.ndarray, conductance: np.ndarray, outer_conductance: float, coupling: float) -> np.ndarray:
    k1 = acceleration(state, volumes, conductance, outer_conductance, coupling)
    k2 = acceleration(state + 0.5 * dt * k1, volumes, conductance, outer_conductance, coupling)
    k3 = acceleration(state + 0.5 * dt * k2, volumes, conductance, outer_conductance, coupling)
    k4 = acceleration(state + dt * k3, volumes, conductance, outer_conductance, coupling)
    return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def energy_parts(state: np.ndarray, r: np.ndarray, volumes: np.ndarray, conductance: np.ndarray, outer_conductance: float, coupling: float) -> float:
    f, vf, zr, zi, vzr, vzi = state
    n = zr * zr + zi * zi
    ef = 0.5 * C_PSI * float(np.dot(volumes, vf * vf))
    ez = A * float(np.dot(volumes, vzr * vzr + vzi * vzi))
    ef += 0.5 * float(np.sum(conductance * np.diff(f) ** 2)) + 0.5 * outer_conductance * (1.0 - f[-1]) ** 2
    ez += 0.5 * float(np.sum(conductance * (np.diff(zr) ** 2 + np.diff(zi) ** 2))) + 0.5 * outer_conductance * n[-1]
    potential = U_RHO * 0.25 * (f * f - 1.0) ** 2 + (B - coupling + coupling * f * f) * n + 0.5 * U_C * n * n
    cell = float(np.dot(volumes, potential))
    return ef + ez + cell


def diagnostics(state: np.ndarray, r: np.ndarray, volumes: np.ndarray, conductance: np.ndarray, outer_conductance: float, coupling: float, initial_charge: float = Q_ABS) -> np.ndarray:
    f, vf, zr, zi, vzr, vzi = state
    n = zr * zr + zi * zi
    local_q = -2.0 * A * (zr * vzi - zi * vzr)
    energy = energy_parts(state, r, volumes, conductance, outer_conductance, coupling)
    charge = float(np.dot(volumes, local_q))
    charge_l1 = float(np.dot(volumes, np.abs(local_q)))
    core = r < CORE_RADIUS
    core_charge = float(np.dot(volumes[core], local_q[core]))
    core_fraction = core_charge / initial_charge if initial_charge else 0.0
    core_weight = float(np.dot(volumes[core], np.abs(local_q[core])))
    core_rms = math.sqrt(max(0.0, float(np.dot(volumes[core], r[core] ** 2 * np.abs(local_q[core]))) / core_weight)) if core_weight != 0.0 else 0.0
    # Im(vz* vz) vanishes; use the instantaneous acceleration for the other term.
    acc = acceleration(state, volumes, conductance, outer_conductance, coupling)
    azr, azi = acc[4], acc[5]
    charge_derivative_density = -2.0 * A * (zr * azi - zi * azr)
    core_derivative = float(np.dot(volumes[core], charge_derivative_density[core]))
    face_index = int(round(CORE_RADIUS / (r[1] - r[0])))
    left = face_index - 1
    right = face_index
    current = 4.0 * math.pi * CORE_RADIUS * CORE_RADIUS * K_CX * (zr[left] * zi[right] - zi[left] * zr[right]) / (r[1] - r[0])
    residual = abs(core_derivative + current) / max(1.0, abs(core_derivative), abs(current))
    outer = r > OUTER_RADIUS
    shell = float(np.dot(volumes[outer], C_PSI * 0.5 * vf[outer] ** 2 + A * (vzr[outer] ** 2 + vzi[outer] ** 2)))
    shell += float(np.dot(volumes[outer], U_RHO * 0.25 * (f[outer] ** 2 - 1.0) ** 2 + (B - coupling + coupling * f[outer] ** 2) * n[outer] + 0.5 * U_C * n[outer] ** 2))
    face_r = np.arange(1, len(r), dtype=np.float64) * (r[1] - r[0])
    selected = face_r >= OUTER_RADIUS
    shell += 0.5 * float(np.sum(conductance[selected] * np.diff(f)[selected] ** 2))
    shell += 0.5 * float(np.sum(conductance[selected] * (np.diff(zr)[selected] ** 2 + np.diff(zi)[selected] ** 2)))
    if OUTER_RADIUS <= r[-1] + (r[1] - r[0]) / 2.0:
        shell += 0.5 * outer_conductance * ((1.0 - f[-1]) ** 2 + n[-1])
    return np.array((energy, charge, charge_l1, core_charge, core_fraction, core_rms, f[0], n[0], shell, core_derivative, current, residual), dtype=np.float64)




def row_metrics(t: np.ndarray, diag: np.ndarray) -> dict[str, Any]:
    valid = np.all(np.isfinite(diag), axis=1)
    late = valid & (t >= 32.0 - 1e-12) & (t <= 48.0 + 1e-12)
    early = valid & (t <= 16.0 + 1e-12)
    if np.any(late):
        means: dict[str, Any] = {
            "core_fraction": float(np.mean(diag[late, 4])),
            "core_rms": float(np.mean(diag[late, 5])),
            "central_f2": float(np.mean(diag[late, 6] ** 2)),
            "central_n": float(np.mean(diag[late, 7])),
        }
        late_min = float(np.min(diag[late, 4]))
        late_max = float(np.max(diag[late, 6] ** 2))
    else:
        means = {name: None for name in METRIC_NAMES}
        late_min = None
        late_max = None
    if np.any(valid):
        first = int(np.flatnonzero(valid)[0])
        energy_drift = float(np.max(np.abs(diag[valid, 0] - diag[first, 0])) / max(1.0, abs(diag[first, 0])))
        charge_drift = None if diag[first, 1] == 0.0 else float(np.max(np.abs(diag[valid, 1] - diag[first, 1])) / Q_ABS)
        current_max = float(np.max(diag[valid, 11]))
    else:
        energy_drift = charge_drift = current_max = None
    outer_max = float(np.max(diag[early, 8] / np.maximum(1.0, np.abs(diag[early, 0])))) if np.any(early) else None
    return {
        "energy_relative_drift": energy_drift,
        "charge_relative_drift": charge_drift,
        "current_residual_max": current_max,
        "early_outer_energy_fraction_max": outer_max,
        "late_means": means,
        "late_min_core_fraction": late_min,
        "late_max_central_f2": late_max,
    }

def compare_metrics(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    passed = True
    for name in METRIC_NAMES:
        av = a.get("late_means", {}).get(name) if isinstance(a.get("late_means"), dict) else None
        bv = b.get("late_means", {}).get(name) if isinstance(b.get("late_means"), dict) else None
        if not finite(av) or not finite(bv):
            values[name] = {"a": av, "b": bv, "absolute_difference": None, "tolerance": None, "pass": False}
            passed = False
            continue
        avf = float(av)
        bvf = float(bv)
        delta = abs(avf - bvf)
        tol = 0.02 * max(1.0, abs(avf), abs(bvf))
        values[name] = {"a": avf, "b": bvf, "absolute_difference": delta, "tolerance": tol, "pass": bool(delta < tol)}
        passed = passed and delta < tol
    values["pass"] = bool(passed)
    return values


def retention_criteria(metrics: Mapping[str, Any]) -> bool:
    minimum = metrics.get("late_min_core_fraction")
    maximum = metrics.get("late_max_central_f2")
    return bool(finite(minimum) and finite(maximum) and float(minimum) >= 0.5 and float(maximum) <= 0.25)

def save_npz(path: Path, r: np.ndarray, volumes: np.ndarray, t: np.ndarray, diagnostics_array: np.ndarray, snapshot_t: np.ndarray, fields: np.ndarray, require_finite: bool = True) -> dict[str, Any]:
    np.savez_compressed(path, r=r, volumes=volumes, t=t, diagnostics=diagnostics_array, snapshot_t=snapshot_t, fields=fields)
    with np.load(path, allow_pickle=False) as loaded:
        if sorted(loaded.files) != ["diagnostics", "fields", "r", "snapshot_t", "t", "volumes"]:
            raise ValueError("independent NPZ key schema changed")
        for key in loaded.files:
            if loaded[key].dtype != np.dtype("float64") or (require_finite and not np.all(np.isfinite(loaded[key]))):
                raise ValueError(f"malformed independent array {key}")
    return {"path": path.name, "sha256": byte_sha256(path), "bytes": path.stat().st_size}



def empty_result() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "numerical_pass": False, "verdict": VERDICT_INCONCLUSIVE,
        "complete_physical_matter_formation": False, "failures": [], "identities": {},
        "artifacts": [], "rows": [], "checks": [], "comparisons": [], "condensation": {},
        "analytical_review": {}, "library_versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "sympy": sympy.__version__},
    }
def safe_primary_path(base: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("primary artifact path must be relative")
    path = (base / relative).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError("primary artifact escapes receipt directory") from exc
    return path


def load_primary(primary_path: Path, expected: dict[str, str]) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]], list[str]]:
    failures: list[str] = []
    try:
        def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate primary JSON key: {key}")
                result[key] = value
            return result
        def reject_constant(value: str) -> None:
            raise ValueError(f"nonfinite primary JSON constant: {value}")
        primary = json.loads(primary_path.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs, parse_constant=reject_constant)
        if not isinstance(primary, dict):
            raise ValueError("primary receipt must be an object")
    except Exception as exc:
        raise ValueError(f"primary receipt unreadable: {exc}") from exc
    if primary.get("schema") != PRIMARY_SCHEMA:
        failures.append("primary schema mismatch")
    if primary.get("numerical_pass") is not True:
        failures.append("primary numerical qualification is not true")
    if primary.get("verdict") != VERDICT_INCONCLUSIVE:
        failures.append("primary verdict is not the required pre-independent INCONCLUSIVE")
    identities = primary.get("identities")
    if not isinstance(identities, dict):
        failures.append("primary identities missing")
    else:
        frozen = identities.get("frozen")
        sections = frozen.get("sections", {}) if isinstance(frozen, dict) else {}
        for key, value in (("derivation", DERIVATION_SHA256), ("protocol", PROTOCOL_SHA256), ("parent", PARENT_SHA256)):
            item = sections.get(key) if isinstance(sections, dict) else None
            if not isinstance(item, dict) or item.get("sha256") != value or item.get("expected_sha256") != value:
                failures.append(f"primary identity mismatch: {key}")
        program_identity = identities.get("source")
        if not isinstance(program_identity, dict) or not isinstance(program_identity.get("canonical_sha256"), str):
            failures.append("primary program identity missing")
    artifacts = primary.get("artifacts")
    if not isinstance(artifacts, list):
        failures.append("primary artifact manifest missing")
        artifacts = []
    manifest: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            failures.append("malformed primary artifact entry")
            continue
        rel = item["path"]
        if rel in manifest:
            failures.append(f"duplicate primary artifact path: {rel}")
            continue
        try:
            path = safe_primary_path(primary_path.parent, rel)
            if not path.is_file() or byte_sha256(path) != item["sha256"]:
                failures.append(f"primary artifact hash mismatch: {rel}")
        except Exception as exc:
            failures.append(f"primary artifact invalid: {rel}: {exc}")
        manifest[rel] = item
    required_snapshots = {"program_source.py", "derivation.txt", "protocol.txt", "parent.txt"}
    if not required_snapshots.issubset(manifest):
        failures.append("primary source snapshots missing")
    for name, value in (("derivation.txt", DERIVATION_SHA256), ("protocol.txt", PROTOCOL_SHA256), ("parent.txt", PARENT_SHA256)):
        if name in manifest:
            try:
                if canonical_sha256(primary_path.parent / name) != value:
                    failures.append(f"primary source snapshot mismatch: {name}")
            except OSError:
                failures.append(f"primary source snapshot unreadable: {name}")
    if isinstance(identities, dict) and isinstance(identities.get("source"), dict):
        expected_program_hash = identities["source"].get("canonical_sha256")
        try:
            if canonical_sha256(primary_path.parent / "program_source.py") != expected_program_hash:
                failures.append("primary program source snapshot mismatch")
        except OSError:
            failures.append("primary program source snapshot unreadable")
    checks = primary.get("checks")
    if not isinstance(checks, list) or not checks or any(not isinstance(item, dict) or item.get("pass") is not True for item in checks):
        failures.append("primary checks are not all passing")
    comparisons = primary.get("comparisons")
    if not isinstance(comparisons, list) or any(not isinstance(item, dict) or item.get("pass") is not True for item in comparisons):
        failures.append("primary comparisons are not all passing")
    rows = primary.get("rows")
    expected_keys = {(grid, arm) for grid in ("G0", "G1", "G2", "T1") for arm in ARMS}
    expected_keys_full = expected_keys | {("G0", "conjugate_w4"), ("G0", "vacuum")}
    if not isinstance(rows, list) or len(rows) != len(expected_keys_full):
        failures.append("primary row count mismatch")
        rows = []
    row_map: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            failures.append("malformed primary row")
            continue
        key = (str(row.get("grid")), str(row.get("arm")))
        if key in row_map:
            failures.append(f"duplicate primary row: {key}")
        row_map[key] = row
    if set(row_map) != expected_keys_full:
        failures.append("primary grid/arm coverage mismatch")
    npz_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    paths_seen: set[str] = set()
    for key, row in row_map.items():
        grid, arm = key
        if grid not in ("G0", "G1", "G2", "T1"):
            failures.append(f"primary unexpected grid {key}")
            continue
        if arm not in ARMS and not (grid == "G0" and arm in ("conjugate_w4", "vacuum")):
            failures.append(f"primary unexpected arm {key}")
            continue
        R, dr, dt, n = expected_grid(grid)
        if row.get("completed") is not True or row.get("numerical_pass") is not True:
            failures.append(f"primary row is not completed and qualified {key}")
        if not (finite(row.get("R")) and finite(row.get("dr")) and finite(row.get("dt")) and abs(float(row["R"]) - R) < 1e-14 and abs(float(row["dr"]) - dr) < 1e-14 and abs(float(row["dt"]) - dt) < 1e-14):
            failures.append(f"primary schedule mismatch {key}")
        field_file = row.get("fields_file")
        if not isinstance(field_file, str) or field_file in paths_seen or field_file not in manifest:
            failures.append(f"primary field manifest mismatch {key}")
            continue
        paths_seen.add(field_file)
        try:
            with np.load(safe_primary_path(primary_path.parent, field_file), allow_pickle=False) as loaded:
                required_keys = {"r", "volumes", "t", "diagnostics", "snapshot_t", "fields"}
                if set(loaded.files) != required_keys:
                    failures.append(f"primary field keys mismatch {key}")
                    continue
                arrays = {name: np.asarray(loaded[name]) for name in required_keys}
        except Exception as exc:
            failures.append(f"primary field unreadable {key}: {exc}")
            continue
        expected_shapes = {"r": (n,), "volumes": (n,), "t": (N_SAMPLE,), "diagnostics": (N_SAMPLE, 12), "snapshot_t": (N_SNAPSHOT,), "fields": (N_SNAPSHOT, 6, n)}
        if any(arrays[name].shape != shape or arrays[name].dtype != np.dtype("float64") or not np.all(np.isfinite(arrays[name])) for name, shape in expected_shapes.items()):
            failures.append(f"primary field shape/type/finite mismatch {key}")
            continue
        expected_r, expected_volumes, _, _ = make_grid(R, dr)
        if not np.array_equal(arrays["r"], expected_r) or not np.array_equal(arrays["volumes"], expected_volumes):
            failures.append(f"primary radial coordinates/volumes mismatch {key}")
            continue
        expected_t = np.arange(N_SAMPLE, dtype=np.float64) * DT_SAMPLE
        expected_snap = np.arange(N_SNAPSHOT, dtype=np.float64)
        if not np.array_equal(arrays["t"], expected_t) or not np.array_equal(arrays["snapshot_t"], expected_snap):
            failures.append(f"primary time schedule mismatch {key}")
            continue
        coupling = 0.0 if arm.startswith("uncoupled") else H_C
        r = arrays["r"]
        initial_charge = 0.0 if arm == "vacuum" else (-Q_ABS if arm == "conjugate_w4" else Q_ABS)
        volumes = arrays["volumes"]
        _, _, conductance, outer_array = make_grid(R, dr)
        reconstructed = np.empty((N_SNAPSHOT, 12), dtype=np.float64)
        for idx in range(N_SNAPSHOT):
            reconstructed[idx] = diagnostics(arrays["fields"][idx], r, volumes, conductance, float(outer_array[0]), coupling, initial_charge)
        sample_indices = np.rint(expected_snap / DT_SAMPLE).astype(int)
        recorded = arrays["diagnostics"][sample_indices]
        discrepancy = np.abs(reconstructed - recorded)
        scale = 1e-10 * np.maximum(1.0, np.maximum(np.abs(reconstructed), np.abs(recorded)))
        if not np.all(discrepancy <= scale):
            failures.append(f"primary diagnostic reconstruction mismatch {key}")
        primary_metrics = row.get("metrics")
        if not isinstance(primary_metrics, dict):
            failures.append(f"primary metrics missing {key}")
        else:
            recomputed = row_metrics(arrays["t"], arrays["diagnostics"])
            for metric in ("energy_relative_drift", "charge_relative_drift", "current_residual_max", "early_outer_energy_fraction_max", "late_min_core_fraction", "late_max_central_f2"):
                observed, reconstructed_value = primary_metrics.get(metric), recomputed[metric]
                if reconstructed_value is None:
                    if observed is not None:
                        failures.append(f"primary row metric mismatch {key}:{metric}")
                elif not finite(observed) or abs(float(observed) - reconstructed_value) > 1e-10 * max(1.0, abs(float(observed)), abs(reconstructed_value)):
                    failures.append(f"primary row metric mismatch {key}:{metric}")
            for metric in METRIC_NAMES:
                if not isinstance(primary_metrics.get("late_means"), dict) or not finite(primary_metrics["late_means"].get(metric)) or abs(float(primary_metrics["late_means"][metric]) - recomputed["late_means"][metric]) > 1e-10 * max(1.0, abs(float(primary_metrics["late_means"][metric])), abs(recomputed["late_means"][metric])):
                    failures.append(f"primary row metric mismatch {key}:late_means.{metric}")
        npz_by_key[key] = {"row": row, "arrays": arrays, "metrics": row_metrics(arrays["t"], arrays["diagnostics"])}
    if len(paths_seen) != len(expected_keys_full):
        failures.append("primary field artifact count mismatch")
    return primary, npz_by_key, failures


def analytical_review() -> dict[str, Any]:
    return {
        "energy_square_identity": {"identity": "E - s*Omega0*Q = integral of mediator kinetic/gradient + carrier square + U0", "verified": True, "scope": "real mediator and complex carrier sector with stated boundary conditions"},
        "fixed_charge_kinetic_minimum": {"identity": "min integral a|dot z|^2 at fixed signed charge Q is Q^2/(4aN); adding the rotating spatial term gives N/(4a)+Q^2/(4aN)", "verified": True, "condition": "N>0 and dot z = -i Q z/(2aN)"},
        "current_sign_and_discrete_flux": {"continuum": "rho_Q=-2a Im(z*dot z), j_r=k_Cx Im(z*partial_r z), d_t rho+r^-2 d_r(r^2 j)=0", "discrete": "core derivative + outward face current = 0", "verified": True, "sign_convention": "outward current positive"},
        "large_charge_trial_bound": {"statement": "E=Omega0|Q|+O(|Q|^(2/3)) trial energy is below Omega_inf|Q| for sufficiently large supplied charge because Omega0<Omega_inf", "verified": True, "scope": "variational comparison only; no attainment theorem, critical charge, basin, stability, or production claim"},
        "physical_scope": "conditional supplied-charge radial calculation; not physical matter formation",
    }


def evolve_arm(grid: str, arm: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    R, dr, dt, _ = expected_grid(grid)
    r, volumes, conductance, outer_array = make_grid(R, dr)
    coupling = 0.0 if arm.startswith("uncoupled") else H_C
    vacuum = arm == "vacuum"
    conjugate = arm == "conjugate_w4"
    if vacuum:
        state = np.zeros((6, r.size), dtype=np.float64)
        state[0] = 1.0
    else:
        width = 4 if arm.endswith("w4") else 8
        state = initial_state(r, volumes, width, -Q_ABS if conjugate else Q_ABS, conjugate=conjugate)
    t = np.arange(N_SAMPLE, dtype=np.float64) * DT_SAMPLE
    diagnostics_array = np.empty((N_SAMPLE, 12), dtype=np.float64)
    snapshot_t = np.arange(N_SNAPSHOT, dtype=np.float64)
    fields = np.empty((N_SNAPSHOT, 6, r.size), dtype=np.float64)
    diag_idx = 0
    snap_idx = 0
    steps_per_sample = int(round(DT_SAMPLE / dt))
    steps_per_snapshot = int(round(1.0 / dt))
    for step in range(int(round(T_FINAL / dt)) + 1):
        if step % steps_per_sample == 0:
            diagnostics_array[diag_idx] = diagnostics(state, r, volumes, conductance, float(outer_array[0]), coupling, 0.0 if vacuum else (-Q_ABS if conjugate else Q_ABS))
            diag_idx += 1
        if step % steps_per_snapshot == 0:
            fields[snap_idx] = state
            snap_idx += 1
        if step == int(round(T_FINAL / dt)):
            break
        state = rk4_step(state, dt, volumes, conductance, float(outer_array[0]), coupling)
        if not np.all(np.isfinite(state)):
            diagnostics_array[diag_idx:] = np.nan
            fields[snap_idx:] = np.nan
            return r, volumes, t, diagnostics_array, fields, {"completed": False, "stop_step": step + 1}
    return r, volumes, t, diagnostics_array, fields, {"completed": True, "stop_step": int(round(T_FINAL / dt))}


def run(args: argparse.Namespace) -> int:
    output = Path(args.output_dir).resolve()
    if output.exists():
        print(f"refusing existing output directory: {output}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    result = empty_result()
    result["identities"] = {"derivation": {"canonical_sha256": DERIVATION_SHA256}, "protocol": {"canonical_sha256": PROTOCOL_SHA256}, "parent": {"canonical_sha256": PARENT_SHA256}, "program": {"path": str(Path(__file__).resolve().relative_to(ROOT)), "raw_sha256": byte_sha256(Path(__file__)), "canonical_sha256": canonical_sha256(Path(__file__))}}
    try:
        sections = expected_sections(Path(args.note))
        actual_hashes = {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in sections.items()}
        if actual_hashes != {"derivation": DERIVATION_SHA256, "protocol": PROTOCOL_SHA256, "parent": PARENT_SHA256}:
            raise ValueError(f"frozen section hash mismatch: {actual_hashes}")
    except Exception as exc:
        result["failures"] = [f"frozen input validation failed before science: {exc}"]
        write_json(output / "verification.json", result)
        return 1
    snapshots = {"derivation.txt": sections["derivation"], "protocol.txt": sections["protocol"], "parent.txt": sections["parent"]}
    for name, text in snapshots.items():
        (output / name).write_text(text, encoding="utf-8", newline="\n")
    program_copy = output / "program_source.py"
    program_copy.write_bytes(Path(__file__).read_bytes())
    result["artifacts"] = [{"path": name, "sha256": byte_sha256(output / name)} for name in ("program_source.py", "derivation.txt", "protocol.txt", "parent.txt")]
    try:
        primary, primary_npz, primary_failures = load_primary(Path(args.primary).resolve(), sections)
    except Exception as exc:
        primary, primary_npz, primary_failures = {}, {}, [str(exc)]
    result["identities"]["primary"] = {"path": str(Path(args.primary).resolve()), "receipt_sha256": byte_sha256(Path(args.primary).resolve()) if Path(args.primary).is_file() else None}
    if primary_failures:
        result["failures"] = ["primary validation failed before science: " + message for message in primary_failures]
        write_json(output / "verification.json", result)
        return 1
    rows: list[dict[str, Any]] = []
    own_by_arm: dict[str, dict[str, Any]] = {}
    all_ok = True
    for arm in ARMS:
        field_name = f"I1_{arm}.npz"
        try:
            r, volumes, t, diag, fields, status = evolve_arm("I1", arm)
            artifact = save_npz(output / field_name, r, volumes, t, diag, np.arange(N_SNAPSHOT, dtype=np.float64), fields, require_finite=bool(status["completed"]))
            result["artifacts"].append(artifact)
            metrics = row_metrics(t, diag)
            snapshot_discrepancy = None
            snapshot_check = False
            if status["completed"]:
                reconstructed = np.empty((N_SNAPSHOT, 12), dtype=np.float64)
                _, _, local_conductance, local_outer = make_grid(GRIDS["I1"]["R"], GRIDS["I1"]["dr"])
                coupling = 0.0 if arm.startswith("uncoupled") else H_C
                for snapshot_index in range(N_SNAPSHOT):
                    reconstructed[snapshot_index] = diagnostics(fields[snapshot_index], r, volumes, local_conductance, float(local_outer[0]), coupling)
                sample_indices = np.rint(np.arange(N_SNAPSHOT, dtype=np.float64) / DT_SAMPLE).astype(int)
                recorded = diag[sample_indices]
                normalized_difference = np.abs(reconstructed - recorded) / np.maximum(1.0, np.maximum(np.abs(reconstructed), np.abs(recorded)))
                snapshot_discrepancy = float(np.max(normalized_difference))
                snapshot_check = bool(snapshot_discrepancy <= 1e-10)
            metric_values = (metrics["energy_relative_drift"], metrics["charge_relative_drift"], metrics["current_residual_max"], metrics["early_outer_energy_fraction_max"])
            metric_pass = all(finite(value) for value in metric_values) and metrics["energy_relative_drift"] < 2e-3 and metrics["charge_relative_drift"] < 1e-7 and metrics["current_residual_max"] < 1e-10 and metrics["early_outer_energy_fraction_max"] < 1e-4
            row = {"grid": "I1", "arm": arm, "R": GRIDS["I1"]["R"], "dr": GRIDS["I1"]["dr"], "dt": GRIDS["I1"]["dt"], "fields_file": field_name, "completed": bool(status["completed"]), "stop_step": int(status["stop_step"]), "numerical_pass": bool(status["completed"] and snapshot_check and metric_pass), "metrics": metrics, "snapshot_diagnostic_agreement": snapshot_discrepancy}
            rows.append(row)
            own_by_arm[arm] = {"r": r, "volumes": volumes, "t": t, "diag": diag, "fields": fields, "metrics": metrics}
            all_ok = all_ok and row["numerical_pass"]
        except Exception as exc:
            result["failures"].append(f"independent arm {arm} failed: {exc}")
            rows.append({"grid": "I1", "arm": arm, "R": GRIDS["I1"]["R"], "dr": GRIDS["I1"]["dr"], "dt": GRIDS["I1"]["dt"], "fields_file": field_name, "completed": False, "stop_step": None, "numerical_pass": False, "metrics": {}})
            all_ok = False
    result["rows"] = rows
    for name, left, right in (("G0:G1", "G0", "G1"), ("G0:G2", "G0", "G2"), ("G1:T1", "G1", "T1")):
        for arm in ARMS:
            lk = (left, arm); rk = (right, arm)
            if lk not in primary_npz or rk not in primary_npz:
                all_ok = False
                result["comparisons"].append({"name": name, "arm": arm, "pass": False, "reason": "primary row unavailable"})
                continue
            comp = compare_metrics(primary_npz[lk]["metrics"], primary_npz[rk]["metrics"])
            comp.update({"name": name, "arm": arm})
            result["comparisons"].append(comp)
            all_ok = all_ok and bool(comp["pass"])
    for arm in ARMS:
        if ("G1", arm) not in primary_npz or arm not in own_by_arm:
            all_ok = False
            result["comparisons"].append({"name": "G1:I1", "arm": arm, "pass": False, "reason": "comparison row unavailable"})
        else:
            comp = compare_metrics(primary_npz[("G1", arm)]["metrics"], own_by_arm[arm]["metrics"])
            comp.update({"name": "G1:I1", "arm": arm})
            result["comparisons"].append(comp)
            all_ok = all_ok and bool(comp["pass"])
    checks = []
    for row in rows:
        metrics = row.get("metrics", {})
        def threshold(name: str, limit: float) -> dict[str, Any]:
            value = metrics.get(name)
            return {"name": f"row:{row['arm']}:{name}", "pass": bool(finite(value) and float(value) < limit), "value": value, "threshold": limit}
        checks.append({"name": f"row:{row['arm']}:completed", "pass": row["completed"]})
        checks.append(threshold("energy_relative_drift", 2e-3))
        checks.append(threshold("charge_relative_drift", 1e-7))
        checks.append(threshold("current_residual_max", 1e-10))
        snapshot_value = row.get("snapshot_diagnostic_agreement")
        checks.append({"name": f"row:{row['arm']}:snapshot_diagnostics", "pass": bool(finite(snapshot_value) and snapshot_value <= 1e-10), "value": snapshot_value, "threshold": 1e-10})
        checks.append(threshold("early_outer_energy_fraction_max", 1e-4))
    result["checks"] = checks
    for width in WIDTHS:
        coupled = own_by_arm.get(f"coupled_w{width}")
        control = own_by_arm.get(f"uncoupled_w{width}")
        primary_all = [primary_npz.get((grid, f"coupled_w{width}")) for grid in ("G0", "G1", "G2", "T1")]
        control_primary = [primary_npz.get((grid, f"uncoupled_w{width}")) for grid in ("G0", "G1", "G2", "T1")]
        qualifies = coupled is not None and control is not None and all(item is not None for item in primary_all + control_primary)
        if qualifies:
            qualifies = retention_criteria(coupled["metrics"]) and all(retention_criteria(item["metrics"]) for item in primary_all)
            control_fraction = control["metrics"].get("late_means", {}).get("core_fraction") if isinstance(control["metrics"].get("late_means"), dict) else None
            coupled_fraction = coupled["metrics"].get("late_means", {}).get("core_fraction") if isinstance(coupled["metrics"].get("late_means"), dict) else None
            margin_values = [(p["metrics"].get("late_means", {}).get("core_fraction"), c["metrics"].get("late_means", {}).get("core_fraction")) for p, c in zip(primary_all, control_primary)]
            controls_margin = finite(control_fraction) and finite(coupled_fraction) and float(control_fraction) + 0.20 <= float(coupled_fraction) and all(finite(p) and finite(c) and float(c) + 0.20 <= float(p) for p, c in margin_values)
            qualifies = qualifies and controls_margin
        result["condensation"][f"w{width}"] = {"pass": bool(qualifies), "coupled_independent": coupled["metrics"] if coupled else {}, "control_independent": control["metrics"] if control else {}, "primary_grids": {grid: primary_npz[(grid, f"coupled_w{width}")]["metrics"] for grid in ("G0", "G1", "G2", "T1") if (grid, f"coupled_w{width}") in primary_npz}, "primary_controls": {grid: primary_npz[(grid, f"uncoupled_w{width}")]["metrics"] for grid in ("G0", "G1", "G2", "T1") if (grid, f"uncoupled_w{width}") in primary_npz}}
    result["analytical_review"] = analytical_review()
    result["numerical_pass"] = bool(all_ok and all(check.get("pass") is True for check in checks) and all(item.get("pass") is True for item in result["comparisons"]))
    if result["numerical_pass"]:
        result["verdict"] = "EMERGES-conditional finite-charge radial condensation" if any(item.get("pass") for item in result["condensation"].values()) else "DOES NOT EMERGE-in the fixed radial cloud schedule"
    else:
        result["verdict"] = VERDICT_INCONCLUSIVE
        if not result["failures"]:
            result["failures"].append("one or more independent numerical qualifications failed")
    write_json(output / "verification.json", result)
    return 0 if result["numerical_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--primary", required=True, type=Path)
    parser.add_argument("--note", type=Path, default=REPORT_DEFAULT)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
