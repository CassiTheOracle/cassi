#!/usr/bin/env python3
"""Independent Radau verifier for the frozen autonomous mediator pump receipt.

This program intentionally contains no import or execution of the primary
implementation.  It validates the primary receipt and all frozen evidence
before doing any numerical reconstruction, then recomputes the orbit, Fourier
edges, separated-boundary edges, and physical-time monodromies independently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import eigh
from scipy.optimize import brentq
from scipy.special import ellipj, ellipk

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "computations" / "matter-formation-continuum-report.md"
CONTRACT_PATH = ROOT / "runs" / "20260907_matter_formation_autonomous_pump_review" / "implementation_contract.json"
REVIEW_DIR = ROOT / "runs" / "20260907_matter_formation_autonomous_pump_review"
PRIMARY_PATH = ROOT / "computations" / "matter_formation_autonomous_pump.py"
SOURCE_ACTION_PATH = ROOT / "foundations" / "particle-stationary-action-closure.md"
HEADING = "### 25.3 Autonomous pump calculation: pre-execution criteria"
PROTOCOL_SHA256 = "4c2366c8b0ea8f096b866cff48d0792d6788d820f333be7a8747eb6251cc2648"
REVIEW_HASHES = {
    "ParentPumpMath.json": "7df30d02fa4abc533b342192edf09932e37b107b7669feb416976001d6a9e81d",
    "ParentPumpScope.json": "ea3830047b555e22f97e5db1d67ea12c8ffb74597bec3b7a119c78d3dcc6cc25",
}
SCHEMA = "cassi.matter-formation.autonomous-pump.v1"
VERIFY_SCHEMA = "cassi.matter-formation.autonomous-pump-verification.v1"
U_RHO = 4.0
U_C = 1.0
H_C = 2.9598260763447164
K_CX = 1.0
E_C = 0.75
A = 1.0 / 16.0
C_PSI = 1.0 / 8.0
M = 2.0 / 3.0
F = math.sqrt(3.0 / 2.0)
OMEGA = math.sqrt(24.0)
PERIOD = 2.0 * ellipk(M) / OMEGA
K_COMPLETE = ellipk(M)
LAME_POTENTIAL = H_C * M
H0 = 1.0 / (6.0 * A) + 0.5 + H_C / 3.0
DIMS = (63, 127, 255)
SAMPLE_COUNT = 1025
EDGE_TOL = 2.0e-8
DET_TOL = 1.0e-9
MATRIX_TOL = 2.0e-8
ORBIT_TOL = 1.0e-9
ROOT_RTOL = 2.0e-11
ROOT_ATOL = 2.0e-13
RAD_TOL = 2.0e-11
RAD_ATOL = 2.0e-13

REQUIRED_NPZ = {
    "orbit_t", "orbit_exact", "orbit_numeric", "orbit_energy", "edges",
    "eigenvalues", "u_n63", "u_n127", "u_n255", "potential_n63",
    "potential_n127", "potential_n255", "fourier_n63", "fourier_n127",
    "fourier_n255", "witness_gaps", "witness_k", "fundamental_t", "fundamental",
}
NPZ_SPECS: dict[str, tuple[np.dtype, tuple[int, ...] | None]] = {
    "orbit_t": (np.dtype("float64"), (SAMPLE_COUNT,)),
    "orbit_exact": (np.dtype("float64"), (SAMPLE_COUNT, 2)),
    "orbit_numeric": (np.dtype("float64"), (SAMPLE_COUNT, 2)),
    "orbit_energy": (np.dtype("float64"), (SAMPLE_COUNT,)),
    "edges": (np.dtype("float64"), (3, 6, 2)),
    "eigenvalues": (np.dtype("float64"), (3, 2, 7)),
    "witness_gaps": (np.dtype("int64"), None),
    "witness_k": (np.dtype("float64"), None),
    "fundamental_t": (np.dtype("float64"), (SAMPLE_COUNT,)),
    "fundamental": (np.dtype("float64"), None),
}


for _n in DIMS:
    NPZ_SPECS[f"u_n{_n}"] = (np.dtype("float64"), (8 * _n,))
    NPZ_SPECS[f"potential_n{_n}"] = (np.dtype("float64"), (8 * _n,))
    NPZ_SPECS[f"fourier_n{_n}"] = (np.dtype("complex128"), (8 * _n,))


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(path: Path) -> str:
    return sha256_bytes(canonical_bytes(path))


def protocol_section(path: Path) -> bytes:
    text = canonical_bytes(path).decode("utf-8")
    if text.count(HEADING) != 1:
        raise ValueError("frozen autonomous-pump heading must occur exactly once")
    start = text.find(HEADING)
    if start < 0:
        raise ValueError(f"missing frozen heading: {HEADING}")
    match = re.search(r"(?m)^#{1,3}\s+", text[start + len(HEADING):])
    end = start + len(HEADING) + match.start() if match else len(text)
    return (text[start:end].rstrip() + "\n").encode("utf-8")


def strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> Any:
        raise ValueError(f"nonfinite JSON constant {value}")

    def reject_duplicate(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate JSON key {key!r}")
            out[key] = value
        return out

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate, parse_constant=reject_constant)


def finite_tree(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(k, str) and finite_tree(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_tree(v) for v in value)
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    return isinstance(value, (int, float, np.number)) and math.isfinite(float(value))


def safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [safe(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return safe(value.item())
    if isinstance(value, complex):
        return [safe(value.real), safe(value.imag)]
    if isinstance(value, Mapping):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    return value


def number_ok(value: Any, expected: float, tol: float) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value)) and abs(float(value) - expected) <= tol * max(1.0, abs(expected))


def write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(safe(payload), handle, ensure_ascii=False, allow_nan=False, indent=2)
        handle.write("\n")


def mismatch(failures: list[dict[str, Any]], name: str, expected: Any, actual: Any, reason: str) -> None:
    failures.append({"name": name, "expected": safe(expected), "actual": safe(actual), "reason": reason})


def array_error(actual: np.ndarray, expected: np.ndarray, denominator: float | None = None) -> float:
    if actual.shape != expected.shape or actual.size == 0:
        return math.inf if actual.shape != expected.shape else 0.0
    if not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected)):
        return math.inf
    scale = 1.0 if denominator is None else denominator
    return float(np.max(np.abs(actual - expected)) / max(1.0, scale))


def orbit_exact(t: np.ndarray) -> np.ndarray:
    sn, cn, dn, _ = ellipj(OMEGA * t, M)
    return np.column_stack((F * dn, -F * OMEGA * M * sn * cn))


def mediator_radau(t: np.ndarray) -> np.ndarray:
    def rhs(x: float, y: np.ndarray) -> np.ndarray:
        return np.asarray((y[1], -(U_RHO / C_PSI) * (y[0] * y[0] - 1.0) * y[0]), dtype=float)

    sol = solve_ivp(rhs, (float(t[0]), float(t[-1])), np.asarray((F, 0.0)), method="Radau", t_eval=t, rtol=RAD_TOL, atol=RAD_ATOL)
    if not sol.success or sol.y.shape != (2, t.size):
        raise RuntimeError(f"mediator Radau failed: {sol.message}")
    return sol.y.T


def energy_density(orbit: np.ndarray) -> np.ndarray:
    return C_PSI / 2.0 * orbit[:, 1] ** 2 + U_RHO / 4.0 * (orbit[:, 0] ** 2 - 1.0) ** 2


def potential_samples(u: np.ndarray) -> np.ndarray:
    sn, _, _, _ = ellipj(u, M)
    return LAME_POTENTIAL * sn * sn


def galerk_eigenvalues(potential: np.ndarray, n: int, beta: float) -> np.ndarray:
    count = 8 * n
    if potential.shape != (count,):
        raise ValueError(f"potential sample shape {potential.shape}, expected {(count,)}")
    coeff = np.fft.fft(potential) / count
    modes = np.arange(-(n // 2), n // 2 + 1, dtype=float)
    delta = (modes[:, None] - modes[None, :]).astype(int) % count
    matrix = coeff[delta].astype(complex)
    diagonal = (2.0 * math.pi * (modes + beta) / (2.0 * K_COMPLETE)) ** 2
    matrix[np.diag_indices(n)] += diagonal
    values = eigh(matrix, subset_by_index=(0, 6), check_finite=True, driver="evr", eigvals_only=True)
    return np.asarray(values, dtype=float)


def edge_from_eigenvalues(values: np.ndarray) -> np.ndarray:
    edges = np.empty((6, 2), dtype=float)
    for j in range(1, 7):
        beta = 1 if j % 2 else 0
        edges[j - 1] = values[beta, j - 1:j + 1]
    return edges


def shoot_value(lam: float, boundary: str) -> float:
    def rhs(u: float, y: np.ndarray) -> np.ndarray:
        sn = float(ellipj(u, M)[0])
        return np.asarray((y[1], (LAME_POTENTIAL * sn * sn - lam) * y[0]), dtype=float)

    initial = np.asarray((1.0, 0.0)) if boundary in ("ND", "NN") else np.asarray((0.0, 1.0))
    sol = solve_ivp(rhs, (0.0, K_COMPLETE), initial, method="Radau", rtol=ROOT_RTOL, atol=ROOT_ATOL)
    if not sol.success:
        raise RuntimeError(f"shooting failed at {lam}: {sol.message}")
    terminal = sol.y[:, -1]
    return float(terminal[0] if boundary in ("ND", "DD") else terminal[1])


def independent_edges(failures: list[dict[str, Any]]) -> np.ndarray:
    result = np.full((6, 2), np.nan, dtype=float)
    for j in range(1, 7):
        lower = (j * math.pi / (2.0 * K_COMPLETE)) ** 2
        upper = lower + 2.0 * H_C / 3.0
        boundaries = ("ND", "DN") if j % 2 else ("NN", "DD")
        roots: list[float] = []
        for boundary in boundaries:
            try:
                lo = shoot_value(lower, boundary)
                hi = shoot_value(upper, boundary)
                if lo == 0.0:
                    root = lower
                elif hi == 0.0:
                    root = upper
                elif lo * hi > 0.0:
                    raise RuntimeError(f"no bracketed {boundary} root for gap {j}: [{lower}, {upper}]")
                else:
                    root = brentq(lambda x: shoot_value(x, boundary), lower, upper, xtol=1.0e-12, rtol=1.0e-14, maxiter=200)
                roots.append(float(root))
            except Exception as exc:
                mismatch(failures, f"shooting.{j}.{boundary}", "root in frozen bracket", repr(exc), "independent edge solve failed")
                roots.append(math.nan)
        result[j - 1] = sorted(roots)
    return result


def physical_matrix(t: np.ndarray, k: float, mode: str) -> np.ndarray:
    def rhs(x: float, y: np.ndarray) -> np.ndarray:
        mat = y.reshape(2, 2)
        if mode == "pump":
            _, _, dn, _ = ellipj(OMEGA * x, M)
            ff = F * dn
            cc = E_C - H_C + H_C * ff * ff
        elif mode in ("constant_mediator", "disabled_coupling"):
            cc = E_C
        else:
            raise ValueError(mode)
        om = 8.0 * k * k + 64.0 + 16.0 * cc
        return (np.asarray(((0.0, 1.0), (-om, 0.0))) @ mat).reshape(-1)

    sol = solve_ivp(rhs, (float(t[0]), float(t[-1])), np.eye(2).reshape(-1), method="Radau", t_eval=t, rtol=RAD_TOL, atol=RAD_ATOL)
    if not sol.success or sol.y.shape != (4, t.size):
        raise RuntimeError(f"physical {mode} Radau failed: {sol.message}")
    return sol.y.T.reshape(t.size, 2, 2)

def mismatch_stats(matrix: np.ndarray) -> dict[str, float | bool]:
    final = matrix[-1]
    trace = float(np.trace(final))
    determinant = float(np.linalg.det(final))
    excess = abs(trace) - 2.0
    mu = float(math.acosh(abs(trace) / 2.0) / PERIOD) if excess > 0.0 else 0.0
    return {"trace": trace, "determinant": determinant, "excess": excess, "mu": mu, "unstable": bool(excess > 1.0e-8)}


def base_failure(failures: list[dict[str, Any]], environment: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": VERIFY_SCHEMA, "verdict": "INCONCLUSIVE", "passed": False, "qualified": False,
        "error": "; ".join(str(x["reason"]) for x in failures) if failures else "prerequisite failure",
        "environment": dict(environment), "files": {}, "protocol_sha256": None, "review_hashes": {},
        "gaps": [], "witnesses": [], "orbit": {}, "spectral": {}, "mismatches": failures,
    }


def load_arrays(path: Path, failures: list[dict[str, Any]]) -> dict[str, np.ndarray] | None:
    if not path.is_file():
        mismatch(failures, "arrays.npz", "present", None, "missing primary array archive")
        return None
    try:
        with np.load(path, allow_pickle=False) as archive:
            names = set(archive.files)
            if names != REQUIRED_NPZ:
                mismatch(failures, "arrays.keys", sorted(REQUIRED_NPZ), sorted(names), "exact NPZ key set mismatch")
                return None
            arrays = {name: np.asarray(archive[name]) for name in archive.files}
    except Exception as exc:
        mismatch(failures, "arrays.npz", "readable", repr(exc), "cannot read NPZ")
        return None
    for name, (dtype, shape) in NPZ_SPECS.items():
        arr = arrays[name]
        if arr.dtype != dtype:
            mismatch(failures, f"arrays.{name}.dtype", str(dtype), str(arr.dtype), "dtype mismatch")
        if shape is not None and arr.shape != shape:
            mismatch(failures, f"arrays.{name}.shape", shape, arr.shape, "shape mismatch")
        if name == "witness_gaps" and (arr.ndim != 1 or arr.size > 6):
            mismatch(failures, f"arrays.{name}.shape", "(W,), 0<=W<=6", arr.shape, "witness shape mismatch")
        if name == "witness_k" and (arr.ndim != 1 or arr.size > 6):
            mismatch(failures, f"arrays.{name}.shape", "(W,), 0<=W<=6", arr.shape, "witness shape mismatch")
        if name == "fundamental" and (arr.ndim != 5 or arr.shape != (arr.shape[0], 3, SAMPLE_COUNT, 2, 2)):
            mismatch(failures, f"arrays.{name}.shape", "(W,3,1025,2,2)", arr.shape, "fundamental shape mismatch")
        if np.issubdtype(arr.dtype, np.number) and not np.all(np.isfinite(arr)):
            mismatch(failures, f"arrays.{name}", "all finite", "nonfinite", "nonfinite array data")
    if arrays["witness_gaps"].shape != arrays["witness_k"].shape or arrays["fundamental"].shape[0] != arrays["witness_gaps"].size:
        mismatch(failures, "arrays.witness_count", "matching W", (arrays["witness_gaps"].shape, arrays["witness_k"].shape, arrays["fundamental"].shape), "witness array count mismatch")
    return arrays if not failures else None




def validate_json_schedule(primary: Mapping[str, Any], arrays: Mapping[str, np.ndarray], failures: list[dict[str, Any]]) -> None:
    gaps = primary.get("gaps")
    if not isinstance(gaps, list) or len(gaps) != 6:
        mismatch(failures, "gaps", "exactly six rows", gaps, "invalid frozen gap schedule")
    else:
        required = {"j", "edges", "width", "midpoint", "accessible", "retained", "k", "reason"}
        for index, row in enumerate(gaps):
            if not isinstance(row, Mapping) or set(row) != required or row.get("j") != index + 1:
                mismatch(failures, f"gaps[{index}]", required, row, "invalid exact gap row schema/order")
    witnesses = primary.get("witnesses")
    if not isinstance(witnesses, list) or len(witnesses) != arrays["witness_gaps"].size:
        mismatch(failures, "witnesses", int(arrays["witness_gaps"].size), witnesses, "witness row count does not match raw witness schedule")
    else:
        for index, row in enumerate(witnesses):
            if not isinstance(row, Mapping) or not {"j", "k", "trace", "determinant", "excess", "mu", "unstable", "controls", "determinant_error"} <= set(row):
                mismatch(failures, f"witnesses[{index}]", "complete witness schema", row, "invalid witness row schema")
            elif not isinstance(row.get("controls"), list) or [c.get("name") for c in row["controls"] if isinstance(c, Mapping)] != ["constant_mediator", "disabled_coupling"]:
                mismatch(failures, f"witnesses[{index}].controls", ["constant_mediator", "disabled_coupling"], row.get("controls"), "invalid control schedule/order")
def validate_prerequisites(primary_dir: Path, record: Path, contract: Mapping[str, Any], failures: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, np.ndarray] | None, dict[str, str]]:
    result_path = primary_dir / "results.json"
    if not result_path.is_file():
        result_path = primary_dir / "report.json"
    if not result_path.is_file():
        mismatch(failures, "results.json", "present", None, "missing primary receipt")
        return None, None, {}
    try:
        primary = strict_json(result_path)
    except Exception as exc:
        mismatch(failures, "results.json", "strict JSON", repr(exc), "invalid primary JSON")
        return None, None, {}
    if not isinstance(primary, Mapping) or not finite_tree(primary):
        mismatch(failures, "results.json", "finite JSON object", type(primary).__name__, "invalid primary receipt tree")
        return None, None, {}
    required_top = {"schema", "verdict", "passed", "qualified", "error", "environment", "files", "protocol_sha256", "review_hashes", "gaps", "witnesses", "orbit", "spectral"}
    missing = sorted(required_top - set(primary))
    if missing:
        mismatch(failures, "results.keys", sorted(required_top), sorted(primary), f"missing required keys {missing}")
    if primary.get("schema") != SCHEMA:
        mismatch(failures, "schema", SCHEMA, primary.get("schema"), "primary schema mismatch")
    try:
        protocol = protocol_section(record)
        protocol_hash = sha256_bytes(protocol)
    except Exception as exc:
        mismatch(failures, "protocol", "frozen section", repr(exc), "cannot derive frozen protocol")
        protocol = b""
        protocol_hash = ""
    expected_hash = PROTOCOL_SHA256
    if contract.get("protocol_sha256") != PROTOCOL_SHA256 or contract.get("verifier_path") != "computations/verify_matter_formation_autonomous_pump.py" or contract.get("primary_path") != "computations/matter_formation_autonomous_pump.py":
        mismatch(failures, "implementation_contract", "frozen path/hash identities", contract, "implementation contract identity mismatch")
    if protocol_hash != expected_hash or primary.get("protocol_sha256") != expected_hash:
        mismatch(failures, "protocol_sha256", expected_hash, (protocol_hash, primary.get("protocol_sha256")), "frozen protocol hash mismatch")
    review_hashes = REVIEW_HASHES
    if contract.get("review_hashes") != REVIEW_HASHES:
        mismatch(failures, "implementation_contract.review_hashes", REVIEW_HASHES, contract.get("review_hashes"), "review hash schedule mismatch")
    if not isinstance(review_hashes, Mapping):
        mismatch(failures, "review_hashes", "mapping", review_hashes, "invalid contract review hashes")
        review_hashes = {}
    for name, expected in review_hashes.items():
        path = REVIEW_DIR / str(name)
        if not path.is_file() or raw_sha256(path) != str(expected):
            mismatch(failures, f"review_hashes.{name}", expected, raw_sha256(path) if path.is_file() else None, "review identity mismatch")
        else:
            try:
                review = strict_json(path)
                if not isinstance(review, Mapping) or not finite_tree(review):
                    mismatch(failures, str(name), "finite JSON object", type(review).__name__, "invalid review JSON")
            except Exception as exc:
                mismatch(failures, str(name), "strict JSON", repr(exc), "invalid review JSON")
    files = primary.get("files")
    if not isinstance(files, Mapping):
        mismatch(failures, "files", "mapping", files, "invalid primary file identities")
        files = {}
    expected_files = ("source_primary.py", "source_verifier.py", "frozen_protocol.txt", "ParentPumpMath.json", "ParentPumpScope.json", "source_action.txt", "arrays.npz")
    for name in expected_files:
        path = primary_dir / name
        if not path.is_file():
            mismatch(failures, f"files.{name}", "present", None, "missing declared source snapshot")
            continue
        actual = raw_sha256(path)
        declared = files.get(name)
        if declared != actual:
            mismatch(failures, f"files.{name}", actual, declared, "declared primary identity mismatch")
    if (primary_dir / "source_primary.py").is_file() and raw_sha256(primary_dir / "source_primary.py") != raw_sha256(PRIMARY_PATH):
        mismatch(failures, "source_primary.py", raw_sha256(PRIMARY_PATH) if PRIMARY_PATH.is_file() else None, raw_sha256(primary_dir / "source_primary.py"), "primary source snapshot differs from declared source")
    if (primary_dir / "frozen_protocol.txt").is_file() and (primary_dir / "frozen_protocol.txt").read_bytes() != protocol:
        mismatch(failures, "frozen_protocol.txt", "exact frozen section", "different bytes", "protocol snapshot mismatch")
    for name, source in (("ParentPumpMath.json", REVIEW_DIR / "ParentPumpMath.json"), ("ParentPumpScope.json", REVIEW_DIR / "ParentPumpScope.json")):
        if (primary_dir / name).is_file() and source.is_file() and (primary_dir / name).read_bytes() != source.read_bytes():
            mismatch(failures, name, "exact review bytes", "different bytes", "review snapshot mismatch")
    if (primary_dir / "source_action.txt").is_file() and SOURCE_ACTION_PATH.is_file() and (primary_dir / "source_action.txt").read_bytes() != SOURCE_ACTION_PATH.read_bytes():
        mismatch(failures, "source_action.txt", "exact source bytes", "different bytes", "source action snapshot mismatch")
    arrays = load_arrays(primary_dir / "arrays.npz", failures)
    if arrays is not None and not failures:
        validate_json_schedule(primary, arrays, failures)
    return primary, arrays, {str(k): str(v) for k, v in files.items()}
def verify_science(primary: Mapping[str, Any], arrays: Mapping[str, np.ndarray], failures: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], np.ndarray]:
    t = arrays["orbit_t"]
    expected_t = np.linspace(0.0, PERIOD, SAMPLE_COUNT, dtype=float)
    exact = orbit_exact(t)
    numeric = np.full_like(exact, np.nan)
    try:
        numeric[:] = mediator_radau(t)
    except Exception as exc:
        mismatch(failures, "orbit_numeric.radau", "complete orbit", repr(exc), "independent mediator integration failed")
    orbit = primary.get("orbit") if isinstance(primary.get("orbit"), Mapping) else {}
    orbit_energy = energy_density(numeric)
    primary_energy = energy_density(arrays["orbit_numeric"])
    denominator = max(1.0, float(np.max(np.abs(exact[:, 1]))))
    exact_error = array_error(arrays["orbit_exact"], exact, denominator)
    field_error = array_error(arrays["orbit_numeric"][:, 0], exact[:, 0], denominator)
    velocity_error = array_error(arrays["orbit_numeric"][:, 1], exact[:, 1], denominator)
    numeric_field_error = array_error(numeric[:, 0], exact[:, 0], denominator)
    numeric_velocity_error = array_error(numeric[:, 1], exact[:, 1], denominator)
    primary_numeric_field_error = array_error(arrays["orbit_numeric"][:, 0], numeric[:, 0], denominator)
    primary_numeric_velocity_error = array_error(arrays["orbit_numeric"][:, 1], numeric[:, 1], denominator)
    energy_drift = array_error(orbit_energy, np.full(SAMPLE_COUNT, 0.25))
    primary_energy_drift = array_error(primary_energy, np.full(SAMPLE_COUNT, 0.25))
    if array_error(t, expected_t) > 1.0e-14:
        mismatch(failures, "orbit_t", expected_t, t, "sample schedule mismatch")
    if array_error(arrays["fundamental_t"], t) > 1.0e-14:
        mismatch(failures, "fundamental_t", t, arrays["fundamental_t"], "fundamental sample schedule mismatch")
    for n in DIMS:
        count = 8 * n
        expected_u = np.arange(count, dtype=float) * (2.0 * K_COMPLETE / count)
        expected_potential = potential_samples(expected_u)
        expected_fourier = np.fft.fft(expected_potential) / count
        if array_error(arrays[f"u_n{n}"], expected_u) > 1.0e-14:
            mismatch(failures, f"u_n{n}", expected_u, arrays[f"u_n{n}"], "spectral sample nodes mismatch")
        if array_error(arrays[f"potential_n{n}"], expected_potential) > 1.0e-12:
            mismatch(failures, f"potential_n{n}", expected_potential, arrays[f"potential_n{n}"], "raw multiplication potential mismatch")
        if array_error(arrays[f"fourier_n{n}"], expected_fourier) > 1.0e-12:
            mismatch(failures, f"fourier_n{n}", expected_fourier, arrays[f"fourier_n{n}"], "raw Fourier coefficient mismatch")
    orbit_metrics = {"exact": exact_error, "primary_field": field_error, "primary_velocity": velocity_error, "radau_field": numeric_field_error, "radau_velocity": numeric_velocity_error, "primary_energy_drift": primary_energy_drift, "radau_energy_drift": energy_drift}
    for name, error in orbit_metrics.items():
        if error >= ORBIT_TOL:
            mismatch(failures, f"orbit.{name}", f"<{ORBIT_TOL}", error, "orbit qualification failure")
    if array_error(arrays["orbit_energy"], primary_energy) > 1.0e-13:
        mismatch(failures, "orbit_energy", "energy from raw primary orbit", array_error(arrays["orbit_energy"], primary_energy), "primary energy reconstruction mismatch")
    for key, expected in (("period", PERIOD), ("field_error", field_error), ("velocity_error", velocity_error), ("max_normalized_field_error", field_error), ("max_normalized_velocity_error", velocity_error), ("energy_density_drift", primary_energy_drift), ("absolute_energy_density_drift", primary_energy_drift)):
        if key not in orbit or not number_ok(orbit[key], expected, 1.0e-13):
            mismatch(failures, f"orbit.{key}", expected, orbit.get(key), "reported orbit statistic mismatch")
    spectral: dict[str, Any] = {}
    eigen = np.full((3, 2, 7), np.nan, dtype=float)
    for di, n in enumerate(DIMS):
        for bi, beta in enumerate((0.0, 0.5)):
            potential = arrays[f"potential_n{n}"]
            try:
                eigen[di, bi] = galerk_eigenvalues(potential, n, beta)
            except Exception as exc:
                mismatch(failures, f"eigenvalues.{n}.{beta}", "reconstructible", repr(exc), "independent Fourier eigensolve failed")
    if array_error(arrays["eigenvalues"], eigen) > EDGE_TOL:
        mismatch(failures, "eigenvalues", EDGE_TOL, array_error(arrays["eigenvalues"], eigen), "primary eigenvalues disagree with raw potential")
    edge_levels = np.stack([edge_from_eigenvalues(eigen[d]) for d in range(3)])
    edge_raw = arrays["edges"]
    if array_error(edge_raw, edge_levels) > EDGE_TOL:
        mismatch(failures, "edges", edge_levels, edge_raw, "raw primary edges disagree with eigenvalues")
    changes = (float(np.max(np.abs(edge_raw[1] - edge_raw[0]))), float(np.max(np.abs(edge_raw[2] - edge_raw[1]))))
    for idx, key in enumerate(("edge_change_63_127", "edge_change_127_255")):
        if key in (primary.get("spectral") or {}) and not number_ok(primary["spectral"][key], changes[idx], 1.0e-8):
            mismatch(failures, f"spectral.{key}", changes[idx], primary["spectral"][key], "edge-change statistic mismatch")
    if max(changes) >= EDGE_TOL:
        mismatch(failures, "spectral.edge_changes", f"<{EDGE_TOL}", changes, "Galerkin edge convergence failure")
    gaps: list[dict[str, Any]] = []
    primary_gaps = primary.get("gaps") if isinstance(primary.get("gaps"), list) else []
    for j in range(1, 7):
        lo, hi = map(float, edge_raw[2, j - 1])
        width = hi - lo
        midpoint = (hi + lo) / 2.0
        accessible = midpoint >= H0
        retained = accessible and width >= 1.0e-5
        row = {"j": j, "edges": [lo, hi], "width": width, "midpoint": midpoint, "accessible": accessible, "retained": retained, "k": math.sqrt(3.0 * (midpoint - H0)) if accessible else None, "reason": "retained" if retained else ("inaccessible" if not accessible else "narrow")}
        gaps.append(row)
        if j > len(primary_gaps) or not isinstance(primary_gaps[j - 1], Mapping):
            mismatch(failures, f"gaps[{j - 1}]", row, None, "missing primary gap row")
        else:
            for key in row:
                actual = primary_gaps[j - 1].get(key)
                if key == "k" and row[key] is None and actual is None:
                    continue
                if isinstance(row[key], float):
                    ok = number_ok(actual, row[key], 1.0e-8)
                else:
                    ok = actual == row[key]
                if not ok:
                    mismatch(failures, f"gaps[{j - 1}].{key}", row[key], actual, "gap value or classification mismatch")
    try:
        independent = independent_edges(failures)
    except Exception as exc:
        mismatch(failures, "independent_edges", "all twelve roots", repr(exc), "independent separated-boundary shooting failed")
        independent = np.full((6, 2), np.nan)
    edge_diffs = np.abs(independent - edge_raw[2])
    for idx, diff in np.ndenumerate(edge_diffs):
        if not math.isfinite(float(diff)) or diff >= EDGE_TOL:
            mismatch(failures, f"independent_edges[{idx[0]},{idx[1]}]", f"<{EDGE_TOL}", float(diff), "independent edge mismatch")
    spectral["eigenvalues"] = eigen
    spectral["independent_edges"] = independent
    spectral["max_edge_error"] = float(np.nanmax(edge_diffs)) if np.any(np.isfinite(edge_diffs)) else math.inf
    spectral["edge_change_63_127"] = changes[0]
    spectral["edge_change_127_255"] = changes[1]
    return {"period": PERIOD, "field_error": numeric_field_error, "velocity_error": numeric_velocity_error, "primary_field_error": field_error, "primary_velocity_error": velocity_error, "primary_radau_field_error": primary_numeric_field_error, "primary_radau_velocity_error": primary_numeric_velocity_error, "energy_density_drift": energy_drift, "primary_energy_density_drift": primary_energy_drift, "passed": bool(all(error < ORBIT_TOL for error in orbit_metrics.values()))}, gaps, spectral, numeric


def verify_witnesses(primary: Mapping[str, Any], arrays: Mapping[str, np.ndarray], gaps: list[dict[str, Any]], failures: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], np.ndarray]:
    selected = [row for row in gaps if row["retained"]]
    wg = arrays["witness_gaps"]
    wk = arrays["witness_k"]
    expected_wg = np.asarray([row["j"] for row in selected], dtype=np.int64)
    if not np.array_equal(wg, expected_wg):
        mismatch(failures, "witness_gaps", expected_wg, wg, "witness schedule mismatch")
    if wk.size != len(selected):
        mismatch(failures, "witness_k", len(selected), wk.size, "witness k count mismatch")
    independent = np.full((len(selected), 3, SAMPLE_COUNT, 2, 2), np.nan, dtype=float)
    primary_fund = arrays["fundamental"]
    rows: list[dict[str, Any]] = []
    p_rows = primary.get("witnesses") if isinstance(primary.get("witnesses"), list) else []
    modes = ("pump", "constant_mediator", "disabled_coupling")
    for wi, row in enumerate(selected):
        j = row["j"]
        k = float(row["k"])
        if wi < wk.size and not number_ok(wk[wi], k, 1.0e-10):
            mismatch(failures, f"witness_k[{wi}]", k, wk[wi], "primary witness k mismatch")
        controls: list[dict[str, Any]] = []
        all_stats: list[dict[str, Any]] = []
        raw_stats_by_mode: list[dict[str, Any]] = []
        for mi, mode in enumerate(modes):
            try:
                independent[wi, mi] = physical_matrix(arrays["fundamental_t"], k, mode)
            except Exception as exc:
                mismatch(failures, f"fundamental.{j}.{mode}", "Radau matrix", repr(exc), "independent matrix integration failed")
                independent[wi, mi] = np.nan
            if wi < primary_fund.shape[0]:
                rel = array_error(primary_fund[wi, mi], independent[wi, mi], float(np.max(np.abs(primary_fund[wi, mi]))))
                if not math.isfinite(rel) or rel >= MATRIX_TOL:
                    mismatch(failures, f"fundamental[{wi},{mi}]", f"<{MATRIX_TOL}", rel, "primary/independent matrix mismatch")
                if np.any(np.abs(primary_fund[wi, mi, 0] - np.eye(2)) > 1.0e-12):
                    mismatch(failures, f"fundamental[{wi},{mi},0]", "identity", primary_fund[wi, mi, 0], "fundamental initial matrix mismatch")
            if np.all(np.isfinite(independent[wi, mi])):
                stats = mismatch_stats(independent[wi, mi])
                stats["determinant_error"] = abs(float(stats["determinant"]) - 1.0)
                stats["passed"] = bool(stats["determinant_error"] < DET_TOL and (mode == "pump" or abs(float(stats["trace"])) <= 2.0 + 1.0e-9))
            else:
                stats = {"trace": None, "determinant": None, "excess": None, "mu": None, "unstable": False, "determinant_error": None, "passed": False}
            all_stats.append(stats)
            if mode != "pump":
                controls.append({"name": mode, "trace": stats["trace"], "determinant": stats["determinant"], "determinant_error": stats["determinant_error"], "passed": stats["passed"]})
            if not stats["passed"]:
                mismatch(failures, f"witnesses[{wi}].{mode}", "qualified determinant and control trace", stats, "matrix qualification failure")
            raw_stats = mismatch_stats(primary_fund[wi, mi])
            raw_det_error = abs(raw_stats["determinant"] - 1.0)
            raw_stats["determinant_error"] = raw_det_error
            raw_stats["passed"] = bool(raw_det_error < DET_TOL and (mode == "pump" or abs(raw_stats["trace"]) <= 2.0 + 1.0e-9))
            raw_stats_by_mode.append(raw_stats)
            if raw_det_error >= DET_TOL or (mode != "pump" and abs(raw_stats["trace"]) > 2.0 + 1.0e-9):
                mismatch(failures, f"primary.witnesses[{wi}].{mode}", "qualified raw determinant and control trace", raw_stats, "raw primary matrix qualification failure")
            if mode == "pump" and raw_stats["unstable"] != stats["unstable"]:
                mismatch(failures, f"witnesses[{wi}].unstable", raw_stats["unstable"], stats["unstable"], "independent instability classifications disagree")
        stats = all_stats[0]
        stats["passed"] = bool(stats["passed"] and all(control["passed"] for control in controls))
        if wi >= len(p_rows) or not isinstance(p_rows[wi], Mapping):
            mismatch(failures, f"witnesses[{wi}]", "present", None, "missing primary witness row")
        else:
            prow = p_rows[wi]
            for key in ("j", "k", "trace", "determinant", "excess", "mu", "unstable", "determinant_error"):
                expected = j if key == "j" else k if key == "k" else raw_stats_by_mode[0][key]
                actual = prow.get(key)
                ok = actual == expected if key in ("j", "unstable") else (expected is not None and number_ok(actual, float(expected), 1.0e-12))
                if not ok:
                    mismatch(failures, f"witnesses[{wi}].{key}", expected, actual, "primary witness statistic mismatch")
            pcontrols = prow.get("controls")
            if not isinstance(pcontrols, list) or len(pcontrols) != len(controls):
                mismatch(failures, f"witnesses[{wi}].controls", len(controls), pcontrols, "primary control count mismatch")
            else:
                for ci, control in enumerate(controls):
                    pcontrol = pcontrols[ci]
                    if not isinstance(pcontrol, Mapping):
                        mismatch(failures, f"witnesses[{wi}].controls[{ci}]", control, pcontrol, "invalid primary control")
                        continue
                    for key in ("name", "trace", "determinant", "determinant_error", "passed"):
                        expected = control["name"] if key == "name" else raw_stats_by_mode[ci + 1][key]
                        actual = pcontrol.get(key)
                        ok = actual == expected if key in ("name", "passed") else (expected is not None and number_ok(actual, float(expected), 1.0e-12))
                        if not ok:
                            mismatch(failures, f"witnesses[{wi}].controls[{ci}].{key}", expected, actual, "primary control mismatch")
        rows.append({"j": j, "k": k, **stats, "controls": controls})
    if len(p_rows) != len(selected):
        mismatch(failures, "witnesses", len(selected), len(p_rows), "primary witness row count mismatch")
    return rows, independent




def analytical_checks() -> dict[str, Any]:
    orbit_force_1 = C_PSI * OMEGA * OMEGA * (2.0 - M)
    orbit_force_2 = 2.0 * C_PSI * OMEGA * OMEGA / (F * F)
    cone_rhs = 2.0 * A / K_CX
    lame_coefficient = H_C * F * F * M / (A * OMEGA * OMEGA)
    return {
        "orbit_equation": {"cPsi_Omega2_2minusm": orbit_force_1, "uRho": U_RHO, "two_cPsi_Omega2_over_F2": orbit_force_2, "passed": bool(abs(orbit_force_1 - U_RHO) < 1.0e-14 and abs(orbit_force_2 - U_RHO) < 1.0e-14)},
        "common_cone": {"cPsi": C_PSI, "two_a_over_kCx": cone_rhs, "passed": bool(abs(C_PSI - cone_rhs) < 1.0e-14)},
        "spectral_map": {"lambda0": H0, "sn2_coefficient": lame_coefficient, "expected_sn2_coefficient": H_C * M, "passed": bool(abs(lame_coefficient - H_C * M) < 1.0e-14)},
        "energy_exchange": {"identity": "dE_z/dt = 2*hC*integral(f*f_t*|z|^2) = -dE_f/dt", "review": "ParentPumpMath.json"},
        "zero_charge_real_mode": {"identity": "Im(y*y_t)=0 for real y,y_t", "review": "ParentPumpScope.json"},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--record", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    primary_dir = args.primary_dir.resolve()
    output_dir = args.output_dir.resolve()
    record = args.record.resolve()
    result_path = output_dir / "results.json"
    environment = {"python": sys.version.split()[0], "numpy": np.__version__, "platform": platform.platform()}
    failures: list[dict[str, Any]] = []
    if output_dir.exists():
        print("INCONCLUSIVE: refusing to overwrite an existing output directory")
        return 1
    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        contract = strict_json(CONTRACT_PATH)
        if not isinstance(contract, Mapping) or not finite_tree(contract):
            raise ValueError("invalid implementation contract")
    except Exception as exc:
        mismatch(failures, "implementation_contract.json", "strict finite JSON", repr(exc), "cannot load implementation contract")
        report = base_failure(failures, environment)
        write_json_exclusive(result_path, report)
        return 1
    primary, arrays, declared_files = validate_prerequisites(primary_dir, record, contract, failures)
    if failures or primary is None or arrays is None:
        report = base_failure(failures, environment)
        report["protocol_sha256"] = contract.get("protocol_sha256")
        report["review_hashes"] = contract.get("review_hashes", {})
        write_json_exclusive(result_path, report)
        return 1
    # All prerequisite checks are complete; only now begin numerical science.
    orbit, gaps, spectral, witness_rows = {}, [], {}, []
    numeric_orbit = np.full((SAMPLE_COUNT, 2), np.nan, dtype=float)
    independent_fundamental = np.full_like(arrays["fundamental"], np.nan)
    try:
        orbit, gaps, spectral, numeric_orbit = verify_science(primary, arrays, failures)
        witness_rows, independent_fundamental = verify_witnesses(primary, arrays, gaps, failures)
    except Exception as exc:
        mismatch(failures, "science", "complete finite reconstruction", repr(exc), "scientific verifier failure")
    expected_orbit_pass = bool(orbit.get("passed", False))
    if isinstance(primary.get("orbit"), Mapping) and primary["orbit"].get("passed") != expected_orbit_pass:
        mismatch(failures, "primary.orbit.passed", expected_orbit_pass, primary["orbit"].get("passed"), "primary orbit flag mismatch")
    edge_pass = bool(spectral.get("max_edge_error", math.inf) < EDGE_TOL and spectral.get("edge_change_63_127", math.inf) < EDGE_TOL and spectral.get("edge_change_127_255", math.inf) < EDGE_TOL)
    if isinstance(primary.get("spectral"), Mapping) and primary["spectral"].get("passed") != edge_pass:
        mismatch(failures, "primary.spectral.passed", edge_pass, primary["spectral"].get("passed"), "primary spectral flag mismatch")
    matrix_errors = [[array_error(arrays["fundamental"][wi, mi], independent_fundamental[wi, mi], float(np.max(np.abs(arrays["fundamental"][wi, mi])))) for mi in range(3)] for wi in range(independent_fundamental.shape[0])]
    spectral["matrix_errors"] = matrix_errors
    spectral["edge_errors"] = np.abs(spectral.get("independent_edges", np.full((6, 2), np.nan)) - arrays["edges"][2])
    spectral["max_matrix_error"] = float(max((error for row in matrix_errors for error in row), default=0.0))
    spectral["edge_change_63_127"] = float(np.max(np.abs(arrays["edges"][1] - arrays["edges"][0])))
    spectral["edge_change_127_255"] = float(np.max(np.abs(arrays["edges"][2] - arrays["edges"][1])))
    spectral["qualifications"] = {"edge_convergence": edge_pass, "all_edge_differences": bool(spectral.get("max_edge_error", math.inf) < EDGE_TOL), "full_matrix_discrepancies": bool(spectral["max_matrix_error"] < MATRIX_TOL), "orbit": expected_orbit_pass, "witnesses": bool(all(row.get("passed", False) and all(control.get("passed", False) for control in row["controls"]) for row in witness_rows))}
    algebra = analytical_checks()
    if not all(bool(item["passed"]) for item in algebra.values() if "passed" in item):
        mismatch(failures, "algebra", "all analytical identities", algebra, "analytical identity failure")
    qualified = not failures and all(spectral["qualifications"].values())
    if primary.get("qualified") != qualified:
        mismatch(failures, "primary.qualified", qualified, primary.get("qualified"), "primary qualification flag mismatch")
    qualified = qualified and not failures
    passed = bool(qualified and any(row.get("unstable", False) for row in witness_rows))
    verdict = "SUPPORTS—neutral linear parametric amplification in the supplied temporal parent" if passed else "INCONCLUSIVE—no resolved unstable witness in the fixed gap schedule" if qualified else "INCONCLUSIVE"
    if primary.get("passed") != passed or primary.get("verdict") != verdict:
        mismatch(failures, "primary.verdict", {"passed": passed, "verdict": verdict}, {"passed": primary.get("passed"), "verdict": primary.get("verdict")}, "primary verdict disagrees with reconstructed qualifications")
        qualified = passed = False
        verdict = "INCONCLUSIVE"
    report = {
        "schema": VERIFY_SCHEMA, "verdict": verdict, "passed": passed, "qualified": qualified,
        "error": None if qualified else "; ".join(str(row["reason"]) for row in failures),
        "environment": environment, "files": {}, "protocol_sha256": contract.get("protocol_sha256"),
        "review_hashes": contract.get("review_hashes", {}), "gaps": gaps, "witnesses": witness_rows,
        "orbit": orbit, "spectral": spectral, "algebra": algebra, "mismatches": failures,
    }
    # Retain the complete evidence chain and raw independent arrays.
    copies = {"source_primary.py": primary_dir / "source_primary.py", "frozen_protocol.txt": primary_dir / "frozen_protocol.txt", "ParentPumpMath.json": primary_dir / "ParentPumpMath.json", "ParentPumpScope.json": primary_dir / "ParentPumpScope.json", "source_action.txt": primary_dir / "source_action.txt", "arrays.npz": primary_dir / "arrays.npz"}
    for name, source in copies.items():
        destination = output_dir / name
        shutil.copyfile(source, destination)
        report["files"][name] = raw_sha256(destination)
    primary_result_path = output_dir / "primary_results.json"
    shutil.copyfile(primary_dir / "results.json" if (primary_dir / "results.json").is_file() else primary_dir / "report.json", primary_result_path)
    report["files"]["primary_results.json"] = raw_sha256(primary_result_path)
    verifier_snapshot = output_dir / "source_verifier.py"
    shutil.copyfile(Path(__file__), verifier_snapshot)
    report["files"]["source_verifier.py"] = raw_sha256(verifier_snapshot)
    independent_path = output_dir / "independent_arrays.npz"
    np.savez(independent_path, orbit_t=arrays["orbit_t"], orbit_exact=orbit_exact(arrays["orbit_t"]), orbit_numeric=numeric_orbit, orbit_energy=energy_density(numeric_orbit), edges=spectral.get("independent_edges", np.full((6, 2), np.nan)), witness_gaps=arrays["witness_gaps"], witness_k=arrays["witness_k"], fundamental_t=arrays["fundamental_t"], fundamental=independent_fundamental)
    report["files"]["independent_arrays.npz"] = raw_sha256(independent_path)
    write_json_exclusive(result_path, report)
    print(json.dumps({"verdict": verdict, "qualified": qualified, "witnesses": len(witness_rows), "mismatches": len(failures)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
