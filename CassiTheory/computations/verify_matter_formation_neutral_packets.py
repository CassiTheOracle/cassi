#!/usr/bin/env python3
"""Independent sparse finite-volume RK4 verifier for notebook section 50.

This program deliberately does not import the primary implementation or the
radial-cloud implementation.  It reconstructs the cylindrical operator,
trajectory, Hamiltonian, charge diagnostics, compact comparisons, and all
frozen qualification comparisons from the manifest-bound raw evidence.
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
from typing import Any

import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
SECTION_HEADING = "## 50. Working notes: charge-neutral packet condensation"
MANIFEST_SCHEMA = "matter-formation-neutral-packets-manifest-v1"
PRIMARY_SCHEMA = "matter-formation-neutral-packets-primary-v1"
SCHEMA = "matter-formation-neutral-packets-verification-v1"
INCONCLUSIVE = "INCONCLUSIVE"
EMERGES = "EMERGES—conditional charge-separated packet condensation"
NO_EMERGENCE = "DOES NOT EMERGE in the specified packet calculation"

A = 1.0 / 16.0
C_PSI = 1.0 / 8.0
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
E_C = 3.0 / 4.0
H_C = 2.9598260763447164
B = 4.75
OMEGA = math.sqrt(B / A)
M0 = 1024.0
WIDTH = 8.0
KAPPA = 0.5
QREF = A * OMEGA * M0 / 2.0
T_FINAL = 48.0
SAMPLE_DT = 1.0 / 32.0
CORE_RADIUS = 8.0

GRID_SPECS = {
    "G0": (192.0, 0.5, 1.0 / 128.0, ("coupled", "uncoupled", "common_phase", "conjugate", "vacuum")),
    "G1": (192.0, 0.25, 1.0 / 128.0, ("coupled", "uncoupled")),
    "G2": (256.0, 0.5, 1.0 / 128.0, ("coupled", "uncoupled")),
    "T1": (192.0, 0.25, 1.0 / 256.0, ("coupled", "uncoupled")),
}
DIAGNOSTIC_NAMES = (
    "energy", "charge", "charge_l1", "half_charge", "half_derivative", "half_current",
    "continuity_residual", "reflection_error", "right_mass", "right_center",
    "right_core_charge", "right_core_fraction", "right_core_rms", "right_core_f2",
    "right_cut_energy", "right_cut_charge", "left_mass", "left_center", "left_core_charge",
    "left_core_fraction", "left_core_rms", "left_core_f2", "left_cut_energy", "left_cut_charge",
)
DIAG_INDEX = {name: i for i, name in enumerate(DIAGNOSTIC_NAMES)}
SNAPSHOT_STEPS = (0, 32, 40, 48)
LATE_TIME_START = 32.0
REQUIRED_SOURCES = {
    "computations/matter_formation_neutral_packets.py",
    "computations/verify_matter_formation_neutral_packets.py",
    "computations/matter_formation_radial_cloud.py",
    "foundations/particle-stationary-action-closure.md",
}


class ContractError(RuntimeError):
    pass


def raw_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def finite(value: Any) -> bool:
    if isinstance(value, np.ndarray):
        return bool(np.all(np.isfinite(value)))
    if isinstance(value, (list, tuple)):
        return all(finite(v) for v in value)
    if isinstance(value, dict):
        return all(finite(v) for v in value.values())
    if isinstance(value, (bool, np.bool_)) or value is None:
        return True
    if isinstance(value, (int, float, np.number)):
        return math.isfinite(float(value))
    return True


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [jsonable(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(jsonable(value), stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def strict_json(path: Path) -> dict[str, Any]:
    def reject(token: str) -> None:
        raise ContractError(f"nonfinite JSON token {token}")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise ContractError(f"duplicate JSON key {key}")
            out[key] = value
        return out

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=reject)
    if not isinstance(value, dict) or not finite(value):
        raise ContractError("JSON receipt must be a finite object")
    return value


def safe_relative(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ContractError(f"invalid relative path {value!r}")
    path = (root / value).resolve()
    root = root.resolve()
    if path != root and root not in path.parents:
        raise ContractError(f"path escapes root: {value}")
    return path


def extract_section(text: str, heading: str) -> bytes:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(re.finditer(r"(?m)^" + re.escape(heading) + r"\s*$", normalized))
    if len(matches) != 1:
        raise ContractError(f"section heading count is {len(matches)}")
    start = matches[0].start()
    close = re.search(r"(?m)^##\s+.+$", normalized[matches[0].end():])
    end = len(normalized) if close is None else matches[0].end() + close.start()
    return (normalized[start:end].rstrip() + "\n").encode("utf-8")


def verify_manifest(path: Path) -> tuple[dict[str, Any], str]:
    manifest = strict_json(path)
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ContractError("manifest schema mismatch")
    section = manifest.get("section")
    if not isinstance(section, dict) or section.get("path") != REPORT or section.get("heading") != SECTION_HEADING:
        raise ContractError("manifest section identity mismatch")
    section_snapshot = safe_relative(path.parent, section.get("snapshot"))
    section_live = safe_relative(ROOT, section.get("path"))
    expected_section = section.get("sha256")
    if not isinstance(expected_section, str) or raw_sha256(section_snapshot) != expected_section:
        raise ContractError("section snapshot hash mismatch")
    if hashlib.sha256(extract_section(section_live.read_text(encoding="utf-8"), SECTION_HEADING)).hexdigest() != expected_section:
        raise ContractError("live section differs from frozen section")
    if section_snapshot.read_bytes() != extract_section(section_live.read_text(encoding="utf-8"), SECTION_HEADING):
        raise ContractError("section snapshot bytes differ from live frozen section")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or {x.get("path") for x in sources if isinstance(x, dict)} != REQUIRED_SOURCES:
        raise ContractError("manifest source set mismatch")
    for item in sources:
        if not isinstance(item, dict):
            raise ContractError("malformed source receipt")
        live = safe_relative(ROOT, item.get("path"))
        snap = safe_relative(path.parent, item.get("snapshot"))
        expected = item.get("sha256")
        if not isinstance(expected, str) or raw_sha256(live) != expected or raw_sha256(snap) != expected:
            raise ContractError(f"source identity mismatch: {item.get('path')}")
    review = manifest.get("mathematical_review")
    if not isinstance(review, dict) or review.get("accepted") is not True:
        raise ContractError("accepted mathematical review is required")
    review_snapshot = safe_relative(path.parent, review.get("snapshot"))
    if not isinstance(review.get("sha256"), str) or raw_sha256(review_snapshot) != review["sha256"]:
        raise ContractError("mathematical review hash mismatch")
    return manifest, raw_sha256(path)


def make_grid(R: float, spacing: float) -> dict[str, Any]:
    nr = int(round(R / spacing))
    nz = 2 * nr
    faces = np.arange(nr + 1, dtype=np.float64) * spacing
    radial = (faces[:-1] + faces[1:]) / 2.0
    axial = -R + (np.arange(nz, dtype=np.float64) + 0.5) * spacing
    radial_volume = math.pi * (faces[1:] ** 2 - faces[:-1] ** 2)
    volume = np.repeat(radial_volume * spacing, nz).astype(np.float64)
    rflat = np.repeat(radial, nz).astype(np.float64)
    zflat = np.tile(axial, nr).astype(np.float64)

    # Radial conductance is 2*pi*r_face; both outer faces use a half-cell
    # Dirichlet distance.  Axial conductance is shell area / spacing.
    gr = 2.0 * math.pi * faces[1:-1]
    gr_outer = 4.0 * math.pi * R
    vr = radial_volume * spacing
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for i in range(nr):
        diag = 0.0
        if i > 0:
            g = float(gr[i - 1] / vr[i])
            rows.append(i); cols.append(i - 1); data.append(g); diag -= g
        if i + 1 < nr:
            g = float(gr[i] / vr[i])
            rows.append(i); cols.append(i + 1); data.append(g); diag -= g
        else:
            diag -= gr_outer / vr[i]
        rows.append(i); cols.append(i); data.append(diag)
    lr = sparse.coo_matrix((data, (rows, cols)), shape=(nr, nr), dtype=np.float64).tocsr()

    rows = []
    cols = []
    data = []
    invh2 = 1.0 / (spacing * spacing)
    for j in range(nz):
        diag = -2.0 * invh2
        if j > 0:
            rows.append(j); cols.append(j - 1); data.append(invh2)
        else:
            diag -= invh2
        if j + 1 < nz:
            rows.append(j); cols.append(j + 1); data.append(invh2)
        else:
            diag -= invh2
        rows.append(j); cols.append(j); data.append(diag)
    lz = sparse.coo_matrix((data, (rows, cols)), shape=(nz, nz), dtype=np.float64).tocsr()
    laplacian = (sparse.kron(sparse.eye(nr, format="csr"), lz, format="csr") + sparse.kron(lr, sparse.eye(nz, format="csr"), format="csr")).tocsr()
    return {"R": R, "spacing": spacing, "nr": nr, "nz": nz, "radial": radial, "axial": axial,
            "rflat": rflat, "zflat": zflat, "volume": volume, "laplacian": laplacian}


def initial_state(grid: dict[str, Any], arm: str) -> tuple[np.ndarray, np.ndarray]:
    r = grid["rflat"]
    zeta = grid["zflat"]
    volume = grid["volume"]
    q = np.zeros((r.size, 3), dtype=np.float64)
    v = np.zeros_like(q)
    if arm == "vacuum":
        return q, v
    kappa = 0.0 if arm == "common_phase" else (-KAPPA if arm == "conjugate" else KAPPA)
    gaussian = np.exp(-(r * r + zeta * zeta) / (2.0 * WIDTH * WIDTH))
    amplitude = math.sqrt(M0 / float(np.dot(volume, gaussian * gaussian)))
    carrier = amplitude * gaussian
    q[:, 1] = carrier * np.cos(kappa * zeta)
    q[:, 2] = carrier * np.sin(kappa * zeta)
    return q, v


def rhs(q: np.ndarray, v: np.ndarray, out_q: np.ndarray, out_v: np.ndarray,
        laplacian: sparse.csr_matrix, coupling: float) -> None:
    f = 1.0 + q[:, 0]
    zr = q[:, 1]
    zi = q[:, 2]
    n = zr * zr + zi * zi
    out_q[...] = v
    spatial = laplacian @ q
    out_v[:, 0] = (spatial[:, 0] - U_RHO * (f * f - 1.0) * f - 2.0 * coupling * f * n) / C_PSI
    coefficient = B - coupling + coupling * f * f + U_C * n
    out_v[:, 1] = (0.5 * K_CX * spatial[:, 1] - coefficient * zr) / A
    out_v[:, 2] = (0.5 * K_CX * spatial[:, 2] - coefficient * zi) / A


class RK4Workspace:
    def __init__(self, shape: tuple[int, int]) -> None:
        self.kq1 = np.empty(shape, dtype=np.float64); self.kv1 = np.empty(shape, dtype=np.float64)
        self.kq2 = np.empty(shape, dtype=np.float64); self.kv2 = np.empty(shape, dtype=np.float64)
        self.kq3 = np.empty(shape, dtype=np.float64); self.kv3 = np.empty(shape, dtype=np.float64)
        self.kq4 = np.empty(shape, dtype=np.float64); self.kv4 = np.empty(shape, dtype=np.float64)
        self.qt = np.empty(shape, dtype=np.float64); self.vt = np.empty(shape, dtype=np.float64)


def rk4_step(q: np.ndarray, v: np.ndarray, dt: float, laplacian: sparse.csr_matrix,
             coupling: float, work: RK4Workspace) -> None:
    kq1, kv1 = work.kq1, work.kv1
    kq2, kv2 = work.kq2, work.kv2
    kq3, kv3 = work.kq3, work.kv3
    kq4, kv4 = work.kq4, work.kv4
    qt, vt = work.qt, work.vt
    rhs(q, v, kq1, kv1, laplacian, coupling)
    np.multiply(kq1, 0.5 * dt, out=qt); qt += q
    np.multiply(kv1, 0.5 * dt, out=vt); vt += v
    rhs(qt, vt, kq2, kv2, laplacian, coupling)
    np.multiply(kq2, 0.5 * dt, out=qt); qt += q
    np.multiply(kv2, 0.5 * dt, out=vt); vt += v
    rhs(qt, vt, kq3, kv3, laplacian, coupling)
    np.multiply(kq3, dt, out=qt); qt += q
    np.multiply(kv3, dt, out=vt); vt += v
    rhs(qt, vt, kq4, kv4, laplacian, coupling)
    q += (dt / 6.0) * (kq1 + 2.0 * kq2 + 2.0 * kq3 + kq4)
    v += (dt / 6.0) * (kv1 + 2.0 * kv2 + 2.0 * kv3 + kv4)




def hamiltonian(q: np.ndarray, v: np.ndarray, grid: dict[str, Any], coupling: float) -> float:
    volume = grid["volume"]
    lap = grid["laplacian"]
    f = 1.0 + q[:, 0]
    zr, zi = q[:, 1], q[:, 2]
    n = zr * zr + zi * zi
    kinetic = 0.5 * C_PSI * float(np.dot(volume, v[:, 0] * v[:, 0])) + A * float(np.dot(volume, v[:, 1] * v[:, 1] + v[:, 2] * v[:, 2]))
    spatial = lap @ q
    gradient = -0.5 * float(np.dot(q[:, 0] * volume, spatial[:, 0]))
    gradient -= 0.5 * K_CX * float(np.dot(zr * volume, spatial[:, 1]) + np.dot(zi * volume, spatial[:, 2]))
    potential = U_RHO * 0.25 * (f * f - 1.0) ** 2 + (B - coupling + coupling * f * f) * n + 0.5 * U_C * n * n
    return kinetic + gradient + float(np.dot(volume, potential))


def compact_energy(q: np.ndarray, v: np.ndarray, theta: np.ndarray, grid: dict[str, Any], coupling: float) -> float:
    return hamiltonian(q * theta[:, None], v * theta[:, None], grid, coupling)


def diagnostics(q: np.ndarray, v: np.ndarray, grid: dict[str, Any], coupling: float, sign_kappa: float) -> np.ndarray:
    volume = grid["volume"]
    r = grid["rflat"]
    zeta = grid["zflat"]
    nr, nz = grid["nr"], grid["nz"]
    f = 1.0 + q[:, 0]
    zr, zi = q[:, 1], q[:, 2]
    rho = -2.0 * A * (zr * v[:, 2] - zi * v[:, 1])
    energy = hamiltonian(q, v, grid, coupling)
    charge = float(np.dot(volume, rho))
    charge_l1 = float(np.dot(volume, np.abs(rho)))
    acc_q = np.empty_like(q); acc_v = np.empty_like(v)
    rhs(q, v, acc_q, acc_v, grid["laplacian"], coupling)
    rho_dot = -2.0 * A * (zr * acc_v[:, 2] - zi * acc_v[:, 1])
    right = zeta > 0.0
    half_charge = float(np.dot(volume[right], rho[right]))
    half_derivative = float(np.dot(volume[right], rho_dot[right]))
    zmat_r = zr.reshape(nr, nz); zmat_i = zi.reshape(nr, nz)
    mid_l = nz // 2 - 1
    mid_r = nz // 2
    area = (grid["volume"].reshape(nr, nz)[:, 0] / grid["spacing"])
    current = float(np.dot(area, K_CX * (zmat_r[:, mid_l] * zmat_i[:, mid_r] - zmat_i[:, mid_l] * zmat_r[:, mid_r]) / grid["spacing"]))
    residual = abs(half_derivative - current) / max(1.0, abs(half_derivative), abs(current))

    qmat = q.reshape(nr, nz, 3)
    vmat = v.reshape(nr, nz, 3)
    qref = np.empty_like(qmat); vref = np.empty_like(vmat)
    qref[:, :, 0] = qmat[:, ::-1, 0]
    qref[:, :, 1] = qmat[:, ::-1, 1]
    qref[:, :, 2] = -qmat[:, ::-1, 2]
    vref[:, :, 0] = vmat[:, ::-1, 0]
    vref[:, :, 1] = vmat[:, ::-1, 1]
    vref[:, :, 2] = -vmat[:, ::-1, 2]
    diff = np.empty_like(qmat)
    diff[:, :, :] = qmat - qref
    vdiff = vmat - vref
    state_norm = math.sqrt(max(0.0, float(np.dot(volume, q[:, 0] ** 2 + q[:, 1] ** 2 + q[:, 2] ** 2 + (v[:, 0] ** 2 + v[:, 1] ** 2 + v[:, 2] ** 2) / (OMEGA * OMEGA)))))
    refl_num = math.sqrt(max(0.0, float(np.dot(volume, np.sum(diff.reshape(-1, 3) ** 2, axis=1) + np.sum(vdiff.reshape(-1, 3) ** 2, axis=1) / (OMEGA * OMEGA)))))
    reflection = refl_num / max(1.0, math.sqrt(M0), state_norm)

    values: list[float] = [energy, charge, charge_l1, half_charge, half_derivative, current, residual, reflection]
    for cap, cap_sign in (("right", 1.0), ("left", -1.0)):
        own = right if cap == "right" else ~right
        positive = np.maximum(cap_sign * sign_kappa * rho, 0.0) * own
        mass = float(np.dot(volume, positive))
        if mass > 0.0 and math.isfinite(mass):
            center = float(np.dot(volume, positive * zeta) / mass)
            distance = np.sqrt(r * r + (zeta - center) ** 2)
            core = distance < CORE_RADIUS
            core_charge = float(np.dot(volume, positive * core))
            if core_charge > 0.0:
                fraction = core_charge / mass
                rms = math.sqrt(max(0.0, float(np.dot(volume, positive * core * distance * distance) / core_charge)))
                core_f2 = float(np.dot(volume, positive * core * f * f) / core_charge)
            else:
                fraction = rms = core_f2 = 0.0
        else:
            center = core_charge = fraction = rms = core_f2 = 0.0
            distance = np.sqrt(r * r + zeta * zeta)
        s = np.clip((distance - 8.0) / 4.0, 0.0, 1.0)
        theta = np.where(distance <= 8.0, 1.0, np.where(distance >= 12.0, 0.0, 1.0 - 3.0 * s * s + 2.0 * s * s * s))
        cut_energy = compact_energy(q, v, theta, grid, coupling)
        cut_charge = float(np.dot(volume, theta * theta * rho))
        values.extend((mass, center, core_charge, fraction, rms, core_f2, cut_energy, cut_charge))
    return np.asarray(values, dtype=np.float64)


def state_arrays(q: np.ndarray, v: np.ndarray, grid: dict[str, Any], time: float) -> dict[str, np.ndarray]:
    radial_volume = grid["volume"][:: grid["nz"]]
    return {
        "fields": np.asarray(q.T.reshape(3, grid["nr"], grid["nz"]), dtype=np.float64),
        "velocities": np.asarray(v.T.reshape(3, grid["nr"], grid["nz"]), dtype=np.float64),
        "r": np.asarray(grid["radial"], dtype=np.float64),
        "axial": np.asarray(grid["axial"], dtype=np.float64),
        "volume": np.asarray(radial_volume.reshape(grid["nr"], 1), dtype=np.float64),
        "time": np.asarray(time, dtype=np.float64),
    }


def run_arm(grid_name: str, arm: str, grid: dict[str, Any], dt: float, output: Path) -> dict[str, Any]:
    prefix = f"{grid_name}_{arm}"
    q, v = initial_state(grid, arm)
    work = RK4Workspace(q.shape)
    coupling = 0.0 if arm == "uncoupled" else H_C
    sign_kappa = -1.0 if arm == "conjugate" else 1.0
    times: list[float] = []
    records: list[np.ndarray] = []
    states: list[str] = []
    failures: list[str] = []
    initial_energy = None
    trace_name = f"{prefix}_trace.npz"
    try:
        initial_energy = hamiltonian(q, v, grid, coupling)
        sample_stride = int(round(SAMPLE_DT / dt))
        total_steps = int(round(T_FINAL / dt))
        snapshot_steps = {int(round(t / dt)): int(t) for t in SNAPSHOT_STEPS}
        for step in range(total_steps + 1):
            if step % sample_stride == 0:
                t = float(step * dt)
                diag = diagnostics(q, v, grid, coupling, sign_kappa)
                if not finite(diag) or not finite(q) or not finite(v):
                    failures.append(f"nonfinite trajectory at t={t:.17g}")
                    break
                times.append(t)
                records.append(np.asarray(diag, dtype=np.float64))
                if step in snapshot_steps:
                    filename = f"{prefix}_t{snapshot_steps[step]:03d}.npz"
                    with (output / filename).open("xb") as stream:
                        np.savez_compressed(stream, **state_arrays(q, v, grid, t))
                    states.append(filename)
                if t > 0.0 and t % 8.0 == 0.0:
                    print(json.dumps({"grid": grid_name, "arm": arm, "time": t}), flush=True)
            if step < total_steps:
                rk4_step(q, v, dt, grid["laplacian"], coupling, work)
                if not finite(q) or not finite(v):
                    failures.append(f"nonfinite trajectory after step {step + 1}")
                    break
        with (output / trace_name).open("xb") as stream:
            np.savez_compressed(stream, time=np.asarray(times, dtype=np.float64), diagnostics=np.asarray(records, dtype=np.float64).reshape(-1, 24), names=np.asarray(DIAGNOSTIC_NAMES, dtype="U32"))
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
        if not times:
            trace_name = ""
        else:
            if not (output / trace_name).exists():
                with (output / trace_name).open("xb") as stream:
                    np.savez_compressed(stream, time=np.asarray(times, dtype=np.float64), diagnostics=np.asarray(records, dtype=np.float64).reshape(-1, 24), names=np.asarray(DIAGNOSTIC_NAMES, dtype="U32"))
    row = {"grid": grid_name, "arm": arm, "R": grid["R"], "spacing": grid["spacing"], "dt": dt,
           "initial_energy": initial_energy, "trace": trace_name, "states": states, "files": [],
           "qualified": False, "failures": failures, "energy_drift": None, "charge_drift": None,
           "late_means": [], "formation": False}
    return row


def load_trace(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        time = np.asarray(data["time"], dtype=np.float64)
        diagnostics_array = np.asarray(data["diagnostics"], dtype=np.float64)
        names = tuple(str(x) for x in data["names"].tolist())
    if names != DIAGNOSTIC_NAMES or diagnostics_array.ndim != 2 or diagnostics_array.shape[1] != 24:
        raise ContractError(f"invalid trace columns in {path.name}")
    return time, diagnostics_array


def row_checks(row: dict[str, Any], trace_path: Path, input_dir: Path, grid: dict[str, Any]) -> tuple[bool, bool, list[str], np.ndarray, np.ndarray]:
    failures = list(row.get("failures", []))
    time, diag = load_trace(trace_path)
    if not finite((time, diag)) or diag.shape != (time.size, 24) or time.size == 0:
        raise ContractError("missing, nonfinite or malformed trace")
    if not np.array_equal(time, np.arange(1537, dtype=np.float64) / 32.0):
        failures.append("incomplete sample schedule")
    e0 = float(diag[0, 0])
    scales = np.asarray([diagnostic_scale(i, e0) for i in range(24)])
    prefix = f"{row['grid']}_{row['arm']}"
    expected_states = [f"{prefix}_t{t:03d}.npz" for t in SNAPSHOT_STEPS]
    if row.get("states") != expected_states:
        failures.append("incomplete state schedule")
    coupling = 0.0 if row["arm"] == "uncoupled" else H_C
    orientation = -1.0 if row["arm"] == "conjugate" else 1.0
    snapshot_errors = []
    for state_time, name in zip(SNAPSHOT_STEPS, expected_states):
        try:
            with np.load(input_dir / name, allow_pickle=False) as data:
                fields = np.asarray(data["fields"], dtype=np.float64)
                velocities = np.asarray(data["velocities"], dtype=np.float64)
                if fields.shape != (3, grid["nr"], grid["nz"]) or velocities.shape != fields.shape:
                    raise ContractError("state shape mismatch")
                if not finite((fields, velocities, data["r"], data["axial"], data["volume"], data["time"])):
                    raise ContractError("nonfinite state")
                if float(data["time"]) != state_time:
                    raise ContractError("snapshot time mismatch")
                if not np.array_equal(data["r"], grid["radial"]) or not np.array_equal(data["axial"], grid["axial"]):
                    raise ContractError("state coordinates mismatch")
                if not np.array_equal(data["volume"], grid["volume"][::grid["nz"], None]):
                    raise ContractError("state volume mismatch")
                q = np.ascontiguousarray(fields.reshape(3, -1).T)
                v = np.ascontiguousarray(velocities.reshape(3, -1).T)
                reconstructed = diagnostics(q, v, grid, coupling, orientation)
                index = state_time * 32
                if index >= time.size or time[index] != state_time:
                    raise ContractError("snapshot has no matching trace time")
                error = float(np.max(np.abs(reconstructed - diag[index]) / scales))
                snapshot_errors.append(error)
                if error >= 1.0e-10:
                    failures.append(f"snapshot diagnostics:{name}")
                if row["arm"] == "vacuum" and (np.any(fields != 0.0) or np.any(velocities != 0.0)):
                    failures.append(f"vacuum state:{name}")
        except Exception as exc:
            failures.append(f"state:{name}:{type(exc).__name__}:{exc}")
    energy_drift = float(np.max(np.abs(diag[:, 0] - e0)) / max(1.0, abs(e0)))
    charge_drift = float(np.max(np.abs(diag[:, 1])) / QREF)
    if energy_drift >= 2e-4:
        failures.append("energy drift")
    if charge_drift >= 1e-8:
        failures.append("global charge")
    if float(np.max(diag[:, 6])) >= 1e-10:
        failures.append("continuity residual")
    if float(np.max(diag[:, 7])) >= 1e-10:
        failures.append("reflection error")
    if row["arm"] == "common_phase" and float(np.max(diag[:, 2])) / QREF >= 1e-10:
        failures.append("common-phase charge")
    if row["arm"] == "vacuum" and np.any(diag != 0.0):
        failures.append("vacuum nonzero diagnostics")
    if row["arm"] == "uncoupled":
        for energy_col, charge_col in ((14, 15), (22, 23)):
            bound = OMEGA * np.abs(diag[:, charge_col]) - 1e-10 * max(1.0, abs(e0))
            if np.any(diag[:, energy_col] < bound):
                failures.append(f"uncoupled compact energy bound:{energy_col}")
    late = time >= LATE_TIME_START
    late_mean = np.mean(diag[late], axis=0).tolist() if np.any(late) else []
    formation = False
    if row["arm"] == "coupled" and np.any(late):
        rd = diag[late]
        R = float(row["R"])
        formation = bool(np.all(
            (rd[:, 9] > 12.0) & (rd[:, 9] < R - 12.0)
            & (rd[:, 17] < -12.0) & (rd[:, 17] > -R + 12.0)
            & (rd[:, 15] >= QREF / 2.0) & (rd[:, 23] <= -QREF / 2.0)
            & (rd[:, 11] >= 0.6) & (rd[:, 19] >= 0.6)
            & (rd[:, 13] <= 0.5) & (rd[:, 21] <= 0.5)
            & (rd[:, 14] <= 0.98 * OMEGA * np.abs(rd[:, 15]))
            & (rd[:, 22] <= 0.98 * OMEGA * np.abs(rd[:, 23]))
        ))
    row.update({"qualified": not failures, "failures": failures, "energy_drift": energy_drift,
                "charge_drift": charge_drift, "late_means": late_mean, "formation": formation,
                "snapshot_diagnostic_errors": snapshot_errors})
    return not failures, formation, failures, time, diag


def weighted_field_error(primary: dict[str, np.ndarray], independent: dict[str, np.ndarray], volume: np.ndarray) -> float:
    pf = np.asarray(primary["fields"], dtype=np.float64).reshape(3, -1).T
    pv = np.asarray(primary["velocities"], dtype=np.float64).reshape(3, -1).T / OMEGA
    inf = np.asarray(independent["fields"], dtype=np.float64).reshape(3, -1).T
    inv = np.asarray(independent["velocities"], dtype=np.float64).reshape(3, -1).T / OMEGA
    if pf.shape != inf.shape or pv.shape != inv.shape or volume.size != pf.shape[0] or not finite((pf, pv, inf, inv)):
        raise ContractError("nonfinite or mismatched fields")
    dn = np.sqrt(max(0.0, float(np.dot(volume, np.sum((pf - inf) ** 2, axis=1) + np.sum((pv - inv) ** 2, axis=1)))))
    norm = np.sqrt(max(0.0, float(np.dot(volume, np.sum(inf ** 2, axis=1) + np.sum(inv ** 2, axis=1)))))
    return dn / max(1.0, math.sqrt(M0), norm)


def diagnostic_scale(index: int, e0: float) -> float:
    if index in (0, 14, 22): return max(1.0, abs(e0))
    if index in (1, 2, 3, 4, 5, 8, 10, 15, 16, 18, 23): return QREF
    if index in (9, 12, 17, 20): return WIDTH
    return 1.0


def bind_primary(primary_dir: Path, manifest_hash: str) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    results_path = primary_dir / "summary.json"
    if not results_path.is_file():
        raise ContractError("primary summary.json missing")
    receipt = strict_json(results_path)
    if receipt.get("schema") != PRIMARY_SCHEMA or receipt.get("manifest_sha256") != manifest_hash:
        raise ContractError("primary receipt identity mismatch")
    rows = receipt.get("rows")
    if not isinstance(rows, list): raise ContractError("primary rows missing")
    bound: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("grid"), str) or not isinstance(row.get("arm"), str):
            raise ContractError("malformed primary row")
        key = (row["grid"], row["arm"])
        if key in bound: raise ContractError(f"duplicate primary row {key}")
        files = row.get("files")
        if not isinstance(files, list): raise ContractError(f"primary files missing for {key}")
        expected_files = {row.get("trace"), *row.get("states", [])}
        if len(files) != 5 or {item.get("path") for item in files} != expected_files:
            raise ContractError(f"incomplete primary raw-file binding: {key}")
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
                raise ContractError(f"malformed primary file receipt {key}")
            file_path = safe_relative(primary_dir, item["path"])
            if not file_path.is_file() or raw_sha256(file_path) != item["sha256"]:
                raise ContractError(f"primary file hash mismatch {item['path']}")
        bound[key] = row
    expected = {(g, a) for g, (_, _, _, arms) in GRID_SPECS.items() for a in arms}
    if set(bound) != expected: raise ContractError("primary row schedule incomplete")
    return receipt, bound


def compare_inputs(primary_dir: Path, primary_rows: dict[tuple[str, str], dict[str, Any]], independent_rows: dict[tuple[str, str], dict[str, Any]], output: Path, grids: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons = []
    for key, prow in primary_rows.items():
        irow = independent_rows[key]
        try:
            pt, pd = load_trace(primary_dir / prow["trace"])
            it, idg = load_trace(output / irow["trace"])
            if not np.array_equal(pt, np.arange(1537) / 32.0) or not np.array_equal(pt, it) or pd.shape != idg.shape or not finite((pd, idg)):
                raise ContractError("incomplete, nonfinite or mismatched traces")
            scales = np.asarray([diagnostic_scale(col, float(pd[0, 0])) for col in range(24)])
            errors = np.abs(pd[pt >= 32.0] - idg[it >= 32.0]) / scales
            comparisons.append({"type": "same_row_diagnostics", "grid": key[0], "arm": key[1],
                                "max_error": float(errors.max()), "column_errors": errors.max(axis=0).tolist(),
                                "pass": bool(np.all(errors < 1.0e-2))})
            for state_time in SNAPSHOT_STEPS:
                name = f"{key[0]}_{key[1]}_t{state_time:03d}.npz"
                with np.load(primary_dir / name, allow_pickle=False) as p, np.load(output / name, allow_pickle=False) as q:
                    if float(p["time"]) != state_time or float(q["time"]) != state_time:
                        raise ContractError("state time mismatch")
                    error = weighted_field_error(p, q, grids[key[0]]["volume"])
                    comparisons.append({"type": "same_state", "grid": key[0], "arm": key[1],
                                        "time": state_time, "max_error": float(error), "pass": bool(error < 1.0e-2)})
        except Exception as exc:
            comparisons.append({"type": "same_row_error", "grid": key[0], "arm": key[1],
                                "pass": False, "error": f"{type(exc).__name__}: {exc}"})
    for implementation, rows in (("primary", primary_rows), ("independent", independent_rows)):
        for arm in ("coupled", "uncoupled"):
            for g1, g2, tolerance in (("G0", "G1", 0.05), ("G0", "G2", 0.05), ("G1", "T1", 0.01)):
                record = {"type": "cross_grid_late_means", "implementation": implementation,
                          "arm": arm, "grids": [g1, g2], "threshold": tolerance}
                try:
                    arow, brow = rows[g1, arm], rows[g2, arm]
                    left = np.asarray(arow["late_means"], dtype=np.float64)
                    right = np.asarray(brow["late_means"], dtype=np.float64)
                    if left.shape != (24,) or right.shape != (24,) or not finite((left, right)):
                        raise ContractError("missing late means")
                    scales = np.asarray([diagnostic_scale(i, float(arow["initial_energy"])) for i in range(24)])
                    errors = np.abs(left - right) / scales
                    record.update({"max_error": float(errors.max()), "column_errors": errors.tolist(),
                                   "pass": bool(np.all(errors < tolerance))})
                except Exception as exc:
                    record.update({"pass": False, "error": f"{type(exc).__name__}: {exc}"})
                comparisons.append(record)
    return comparisons


def conjugate_check(output: Path, independent_rows: dict[tuple[str, str], dict[str, Any]], grid: dict[str, Any]) -> dict[str, Any]:
    errors: list[float] = []
    coupled = independent_rows[("G0", "coupled")]
    conjugate = independent_rows[("G0", "conjugate")]
    for step in SNAPSHOT_STEPS:
        with np.load(output / f"G0_coupled_t{step:03d}.npz", allow_pickle=False) as c, np.load(output / f"G0_conjugate_t{step:03d}.npz", allow_pickle=False) as d:
            cf = np.asarray(c["fields"], dtype=np.float64); cv = np.asarray(c["velocities"], dtype=np.float64)
            df = np.asarray(d["fields"], dtype=np.float64); dv = np.asarray(d["velocities"], dtype=np.float64)
            target_f = cf.copy(); target_v = cv.copy(); target_f[2] *= -1.0; target_v[2] *= -1.0
            errors.append(weighted_field_error({"fields": target_f, "velocities": target_v}, {"fields": df, "velocities": dv}, grid["volume"]))
    err = max(errors) if errors else math.inf
    return {"type": "conjugate_identity", "max_error": err, "pass": bool(math.isfinite(err) and err < 1e-10)}


def make_failure(output: Path, manifest_hash: str, error: str) -> int:
    payload = {"schema": SCHEMA, "manifest_sha256": manifest_hash, "rows": [], "comparisons": [], "numeric_pass": False, "verdict": INCONCLUSIVE, "complete_physical_matter_formation": False, "error": error, "environment": {"python": platform.python_version(), "numpy": np.__version__}}
    write_json(output / "summary.json", payload)
    print(json.dumps({"verdict": INCONCLUSIVE, "error": error}, ensure_ascii=False), flush=True)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        print(f"refusing existing output directory: {output}", file=sys.stderr)
        return 2
    output.mkdir(parents=True, exist_ok=False)
    manifest_hash = ""
    try:
        _, manifest_hash = verify_manifest(args.manifest.resolve())
        primary_dir = args.input.resolve()
        primary_receipt, primary_rows = bind_primary(primary_dir, manifest_hash)
        grids: dict[str, dict[str, Any]] = {}
        independent_rows: dict[tuple[str, str], dict[str, Any]] = {}
        primary_reconstructions = []
        for grid_name, (R, spacing, dt, arms) in GRID_SPECS.items():
            grid = grids.setdefault(grid_name, make_grid(R, spacing))
            for arm in arms:
                copied_row = dict(primary_rows[grid_name, arm])
                try:
                    passed, _, failures, _, _ = row_checks(copied_row, primary_dir / copied_row["trace"], primary_dir, grid)
                    primary_reconstructions.append({"type": "primary_raw_reconstruction", "grid": grid_name,
                                                    "arm": arm, "pass": passed, "failures": failures,
                                                    "snapshot_errors": copied_row["snapshot_diagnostic_errors"]})
                except Exception as exc:
                    primary_reconstructions.append({"type": "primary_raw_reconstruction", "grid": grid_name,
                                                    "arm": arm, "pass": False, "error": f"{type(exc).__name__}: {exc}"})
            for arm in arms:
                row = run_arm(grid_name, arm, grid, dt, output)
                trace_path = output / row["trace"] if row["trace"] else None
                if trace_path and trace_path.exists():
                    try:
                        _, _, failures, _, _ = row_checks(row, trace_path, output, grid)
                        row["failures"] = failures
                        row["qualified"] = not failures
                    except Exception as exc:
                        row["failures"].append(f"qualification: {type(exc).__name__}: {exc}")
                        row["qualified"] = False
                for filename in [row["trace"], *row["states"]]:
                    if filename:
                        row["files"].append({"path": filename, "sha256": raw_sha256(output / filename)})
                independent_rows[(grid_name, arm)] = row
                print(json.dumps({"grid": grid_name, "arm": arm, "qualified": row["qualified"], "failures": row["failures"]}, ensure_ascii=False, allow_nan=False), flush=True)
        comparisons = primary_reconstructions + compare_inputs(primary_dir, primary_rows, independent_rows, output, grids)
        try:
            comparisons.append(conjugate_check(output, independent_rows, grids["G0"]))
        except Exception as exc:
            comparisons.append({"type": "conjugate_identity", "pass": False, "error": f"{type(exc).__name__}: {exc}"})
        numeric_pass = primary_receipt.get("numeric_pass") is True and len(independent_rows) == 11 and all(row["qualified"] for row in independent_rows.values()) and all(item["pass"] for item in comparisons)
        formation_pass = all(bool(row["formation"]) for key, row in independent_rows.items() if key[1] == "coupled") and all(bool(primary_rows[key].get("formation")) for key in primary_rows if key[1] == "coupled")
        verdict = INCONCLUSIVE if not numeric_pass else (EMERGES if formation_pass else NO_EMERGENCE)
        receipt = {"schema": SCHEMA, "manifest_sha256": manifest_hash, "rows": list(independent_rows.values()), "comparisons": comparisons,
                   "numeric_pass": numeric_pass, "verdict": verdict, "complete_physical_matter_formation": False,
                   "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": __import__("scipy").__version__}}
        write_json(output / "summary.json", receipt)
        print(json.dumps({"verdict": verdict, "numeric_pass": numeric_pass, "rows": len(independent_rows), "comparisons": len(comparisons)}, ensure_ascii=False, allow_nan=False), flush=True)
        return 0 if numeric_pass else 1
    except Exception as exc:
        return make_failure(output, manifest_hash, f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
