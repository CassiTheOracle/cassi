#!/usr/bin/env python3
"""Independent symbolic and physical-time verifier for the spatial mediator pump.

The verifier has no import or execution dependency on the primary implementation.
It validates the complete primary evidence chain before evaluating symbolic or
numerical science, then reconstructs the Lamé edges and all five fundamental
matrices using an independently authored Radau calculation.
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
from scipy.special import ellipj, ellipk

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "computations" / "matter-formation-continuum-report.md"
SOURCE_ACTION_PATH = ROOT / "foundations" / "particle-stationary-action-closure.md"
DEFAULT_PUMP = ROOT / "runs" / "20260907_matter_formation_autonomous_pump"
DEFAULT_PUMP_VERIFICATION = ROOT / "runs" / "20260907_matter_formation_autonomous_pump_verification"
HEADING = "### 27.3 Spatial perturbation calculation: pre-execution criteria"
PROTOCOL_SHA256 = "244024bc6bc7a4822c9173dafc726ed0c152594ddbbdb5c43579c527bce0bdfd"
RECOVERY_HEADING = "### 27.4 Prerequisite identity recovery"
RECOVERY_SHA256 = "7ac1f1ed3375f4cb3607ed17114ae852d82a1a2a555b5d46cbf2222750bbd820"
SOURCE_ACTION_SHA256 = "f0314b16d07bfa3f8839a3e1e131ed7e0e1412719c296095db8a419f832d5c93"
PUMP_RESULT_SHA256 = "cad33ef760404c79807570be1269390dfb790574dc13bfe60d61d67c5b1bc9c5"
PUMP_VERIFY_RESULT_SHA256 = "a54c07d1a973f9a915355e26b7c23e7caa7ee75a468f09fda53e13a272959758"
PRIMARY_SCHEMA = "cassi.matter-formation.spatial-pump.v1"
VERIFY_SCHEMA = "cassi.matter-formation.spatial-pump-verification.v1"
PUMP_SCHEMA = "cassi.matter-formation.autonomous-pump.v1"
PUMP_VERIFY_SCHEMA = "cassi.matter-formation.autonomous-pump-verification.v1"

M = 2.0 / 3.0
F = math.sqrt(3.0 / 2.0)
OMEGA = math.sqrt(24.0)
C_PSI = 1.0 / 8.0
U_RHO = 4.0
P_C = math.sqrt(2.0 * math.sqrt(7.0) - 4.0)
K_CUTOFF = 4.0
SAMPLE_COUNT = 1025
DIMS = (63, 127, 255)
EDGE_TOL = 2.0e-8
DET_TOL = 1.0e-9
MATRIX_TOL = 2.0e-8
TRACE_TOL = 1.0e-8
CONTROL_TRACE_TOL = 1.0e-9
RAD_TOL = 2.0e-11
RAD_ATOL = 2.0e-13


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(path: Path) -> str:
    return sha256_bytes(canonical_bytes(path))


def protocol_section(path: Path, heading: str = HEADING) -> bytes:
    text = canonical_bytes(path).decode("utf-8")
    if text.count(heading) != 1:
        raise ValueError(f"frozen heading must occur exactly once: {heading}")
    start = text.find(heading)
    match = re.search(r"(?m)^#{1,3}\s+", text[start + len(heading):])
    end = start + len(heading) + match.start() if match else len(text)
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


def write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(safe(payload), handle, ensure_ascii=False, allow_nan=False, indent=2)
        handle.write("\n")


def mismatch(failures: list[dict[str, Any]], name: str, expected: Any, actual: Any, reason: str) -> None:
    failures.append({"name": name, "expected": safe(expected), "actual": safe(actual), "reason": reason})


def number_ok(value: Any, expected: float, tol: float = 1.0e-11) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value)) and abs(float(value) - expected) <= tol * max(1.0, abs(expected))


def array_error(actual: np.ndarray, expected: np.ndarray, denominator: float | None = None) -> float:
    if actual.shape != expected.shape:
        return math.inf
    if actual.size == 0:
        return 0.0
    if not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected)):
        return math.inf
    scale = 1.0 if denominator is None else max(1.0, denominator)
    return float(np.max(np.abs(actual - expected)) / scale)


def base_failure(failures: list[dict[str, Any]], environment: Mapping[str, Any], protocol_hash: str | None = None) -> dict[str, Any]:
    return {
        "schema": VERIFY_SCHEMA,
        "passed": False,
        "qualified": False,
        "verdict": "INCONCLUSIVE",
        "error": "; ".join(str(x["reason"]) for x in failures) if failures else "prerequisite failure",
        "protocol_sha256": protocol_hash,
        "files": {},
        "parameters": {},
        "arms": [],
        "checks": {},
        "diagnostics": {},
        "symbolic": {},
        "environment": dict(environment),
        "mismatches": failures,
    }


def expected_edges() -> np.ndarray:
    d = math.sqrt(1.0 - M + M * M)
    return np.asarray((2.0 * (1.0 + M) - 2.0 * d, 1.0 + M, 1.0 + 4.0 * M, 4.0 + M, 2.0 * (1.0 + M) + 2.0 * d), dtype=float)


def primary_witness(receipt: Mapping[str, Any], failures: list[dict[str, Any]], label: str) -> tuple[float | None, float | None]:
    if receipt.get("schema") not in (PUMP_SCHEMA, PUMP_VERIFY_SCHEMA):
        mismatch(failures, f"{label}.schema", "accepted autonomous-pump schema", receipt.get("schema"), "parent schema mismatch")
    if receipt.get("passed") is not True or receipt.get("qualified") is not True:
        mismatch(failures, f"{label}.status", {"passed": True, "qualified": True}, {"passed": receipt.get("passed"), "qualified": receipt.get("qualified")}, "parent is not accepted")
    rows = receipt.get("witnesses")
    if not isinstance(rows, list):
        mismatch(failures, f"{label}.witnesses", "list", rows, "missing parent witnesses")
        return None, None
    qualifying = [row for row in rows if isinstance(row, Mapping) and row.get("unstable") is True and row.get("passed") is True]
    if len(qualifying) != 1:
        mismatch(failures, f"{label}.witnesses", "exactly one unstable passed witness", len(qualifying), "parent witness qualification is not unique")
        return None, None
    row = qualifying[0]
    k = row.get("k")
    mu = row.get("mu")
    if not isinstance(k, (int, float, np.number)) or not math.isfinite(float(k)):
        mismatch(failures, f"{label}.k", "finite", k, "parent witness wave number invalid")
        k = None
    if not isinstance(mu, (int, float, np.number)) or not math.isfinite(float(mu)) or float(mu) <= 0:
        mismatch(failures, f"{label}.mu", "positive finite", mu, "parent carrier exponent invalid")
        mu = None
    return (float(k) if k is not None else None), (float(mu) if mu is not None else None)


def load_parent(path: Path, expected_hash: str, schema: str, failures: list[dict[str, Any]], label: str) -> tuple[dict[str, Any] | None, bytes | None]:
    if not path.is_file():
        mismatch(failures, label, "present", None, "missing parent result")
        return None, None
    actual_hash = raw_sha256(path)
    if actual_hash != expected_hash:
        mismatch(failures, f"{label}.sha256", expected_hash, actual_hash, "parent result hash mismatch")
    try:
        data = strict_json(path)
    except Exception as exc:
        mismatch(failures, label, "strict finite JSON", repr(exc), "invalid parent JSON")
        return None, None
    if not isinstance(data, Mapping) or not finite_tree(data):
        mismatch(failures, label, "finite JSON object", type(data).__name__, "invalid parent receipt tree")
        return None, None
    if data.get("schema") != schema:
        mismatch(failures, f"{label}.schema", schema, data.get("schema"), "parent schema mismatch")
    return dict(data), path.read_bytes()


def load_primary_archive(path: Path, failures: list[dict[str, Any]]) -> dict[str, np.ndarray] | None:
    required = {"t", "p", "matrices", "basis_sizes", "edges"}
    for n in DIMS:
        required.update({f"u_n{n}", f"potential_n{n}", f"fourier_n{n}"})
    if not path.is_file():
        mismatch(failures, "arrays.npz", "present", None, "missing primary array archive")
        return None
    try:
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != required:
                mismatch(failures, "arrays.keys", sorted(required), sorted(archive.files), "exact primary array key mismatch")
                return None
            arrays = {name: np.asarray(archive[name]) for name in archive.files}
    except Exception as exc:
        mismatch(failures, "arrays.npz", "readable", repr(exc), "cannot read primary archive")
        return None
    specs: dict[str, tuple[np.dtype, tuple[int, ...]]] = {
        "t": (np.dtype("float64"), (SAMPLE_COUNT,)),
        "p": (np.dtype("float64"), (5,)),
        "matrices": (np.dtype("float64"), (5, SAMPLE_COUNT, 2, 2)),
        "basis_sizes": (np.dtype("int64"), (3,)),
        "edges": (np.dtype("float64"), (3, 5)),
    }
    for n in DIMS:
        count = 8 * n
        specs[f"u_n{n}"] = (np.dtype("float64"), (count,))
        specs[f"potential_n{n}"] = (np.dtype("float64"), (count,))
        specs[f"fourier_n{n}"] = (np.dtype("complex128"), (count,))
    for name, (dtype, shape) in specs.items():
        arr = arrays[name]
        if arr.dtype != dtype:
            mismatch(failures, f"arrays.{name}.dtype", str(dtype), str(arr.dtype), "array dtype mismatch")
        if arr.shape != shape:
            mismatch(failures, f"arrays.{name}.shape", shape, arr.shape, "array shape mismatch")
        if np.issubdtype(arr.dtype, np.number) and not np.all(np.isfinite(arr)):
            mismatch(failures, f"arrays.{name}", "all finite", "nonfinite", "nonfinite primary array")
    if not np.array_equal(arrays["basis_sizes"], np.asarray(DIMS, dtype=np.int64)):
        mismatch(failures, "arrays.basis_sizes", DIMS, arrays["basis_sizes"], "basis schedule mismatch")
    return arrays if not failures else None


def validate_primary_manifest(primary_dir: Path, record: Path, pump_dir: Path, pump_verify_dir: Path, failures: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, np.ndarray] | None, dict[str, Any], bytes | None, bytes | None]:
    result_path = primary_dir / "results.json"
    if not result_path.is_file():
        mismatch(failures, "primary.results.json", "present", None, "missing spatial primary receipt")
        return None, None, {}, None, None
    try:
        primary = strict_json(result_path)
    except Exception as exc:
        mismatch(failures, "primary.results.json", "strict finite JSON", repr(exc), "invalid spatial primary JSON")
        return None, None, {}, None, None
    if not isinstance(primary, Mapping) or not finite_tree(primary):
        mismatch(failures, "primary.results.json", "finite object", type(primary).__name__, "invalid primary receipt tree")
        return None, None, {}, None, None
    required = {"schema", "passed", "qualified", "verdict", "error", "protocol_sha256", "files", "parameters", "arms", "checks", "diagnostics"}
    if not required.issubset(primary):
        mismatch(failures, "primary.results.keys", sorted(required), sorted(primary), "missing shared primary fields")
    if primary.get("schema") != PRIMARY_SCHEMA:
        mismatch(failures, "primary.schema", PRIMARY_SCHEMA, primary.get("schema"), "primary schema mismatch")
    if primary.get("passed") is not False or primary.get("verdict") != "INCONCLUSIVE—awaiting independent spatial qualification":
        mismatch(failures, "primary.provisional", {"passed": False, "verdict": "INCONCLUSIVE—awaiting independent spatial qualification"}, {"passed": primary.get("passed"), "verdict": primary.get("verdict")}, "primary provisional status mismatch")
    try:
        protocol = protocol_section(record)
        protocol_hash = sha256_bytes(protocol)
        recovery = protocol_section(record, RECOVERY_HEADING)
    except Exception as exc:
        mismatch(failures, "protocol", "frozen section", repr(exc), "cannot derive protocol")
        protocol, protocol_hash, recovery = b"", "", b""
    if protocol_hash != PROTOCOL_SHA256 or primary.get("protocol_sha256") != PROTOCOL_SHA256:
        mismatch(failures, "protocol_sha256", PROTOCOL_SHA256, (protocol_hash, primary.get("protocol_sha256")), "frozen protocol hash mismatch")
    if sha256_bytes(recovery) != RECOVERY_SHA256:
        mismatch(failures, "recovery_sha256", RECOVERY_SHA256, sha256_bytes(recovery), "frozen recovery hash mismatch")
    if not SOURCE_ACTION_PATH.is_file() or raw_sha256(SOURCE_ACTION_PATH) != SOURCE_ACTION_SHA256:
        mismatch(failures, "source_action", SOURCE_ACTION_SHA256, raw_sha256(SOURCE_ACTION_PATH) if SOURCE_ACTION_PATH.is_file() else None, "source action identity mismatch")
    files = primary.get("files") if isinstance(primary.get("files"), Mapping) else {}
    if not isinstance(primary.get("files"), Mapping):
        mismatch(failures, "primary.files", "mapping", primary.get("files"), "invalid file manifest")
    expected_names = ("source_primary.py", "source_verifier.py", "source_action.txt", "frozen_protocol.txt", "frozen_recovery.txt", "parent_primary_results.json", "parent_verification_results.json", "arrays.npz")
    expected_sources: dict[str, Path | None] = {
        "source_primary.py": ROOT / "computations" / "matter_formation_spatial_pump.py",
        "source_verifier.py": Path(__file__).resolve(),
        "source_action.txt": SOURCE_ACTION_PATH,
        "frozen_protocol.txt": record,
        "frozen_recovery.txt": record,
        "parent_primary_results.json": pump_dir / "results.json",
        "parent_verification_results.json": pump_verify_dir / "results.json",
        "arrays.npz": primary_dir / "arrays.npz",
    }
    for name in expected_names:
        target = primary_dir / name
        if not target.is_file():
            mismatch(failures, f"primary.files.{name}", "present", None, "missing primary manifest member")
            continue
        actual = raw_sha256(target)
        if files.get(name) != actual:
            mismatch(failures, f"primary.files.{name}", actual, files.get(name), "declared primary file hash mismatch")
        source = expected_sources[name]
        if name == "frozen_protocol.txt":
            expected_bytes = protocol
        elif name == "frozen_recovery.txt":
            expected_bytes = recovery
        elif source is not None and source.is_file():
            expected_bytes = source.read_bytes()
        else:
            expected_bytes = None
            if source is not None:
                mismatch(failures, f"primary.{name}", "current source present", None, "missing current source")
        if expected_bytes is not None and target.read_bytes() != expected_bytes:
            mismatch(failures, f"primary.{name}", "exact current source bytes", "different bytes", "primary source snapshot mismatch")
    arrays = load_primary_archive(primary_dir / "arrays.npz", failures)
    pbytes = result_path.read_bytes()
    return dict(primary), arrays, dict(files), pbytes, protocol


def galerk_edges(potential: np.ndarray, n: int, k_complete: float) -> np.ndarray:
    count = 8 * n
    coeff = np.fft.fft(potential) / count
    modes = np.arange(-(n // 2), n // 2 + 1, dtype=float)
    delta = (modes[:, None] - modes[None, :]).astype(int) % count
    multiplication = coeff[delta]
    out: list[float] = []
    for beta in (0.0, 0.5):
        diagonal = (2.0 * math.pi * (modes + beta) / (2.0 * k_complete)) ** 2
        values = eigh(multiplication + np.diag(diagonal), eigvals_only=True, check_finite=True)
        if beta == 0.0:
            periodic = values
        else:
            antiperiodic = values
    out.extend((periodic[0], antiperiodic[0], antiperiodic[1], periodic[1], periodic[2]))
    return np.asarray(out, dtype=float)


def arm_metrics(matrix: np.ndarray, period: float) -> dict[str, Any]:
    final = matrix[-1]
    trace = float(np.trace(final))
    determinant = float(np.linalg.det(final))
    dets = np.linalg.det(matrix)
    det_error = float(np.max(np.abs(dets - 1.0)))
    excess = abs(trace) - 2.0
    mu = float(math.acosh(abs(trace) / 2.0) / period) if abs(trace) > 2.0 else 0.0
    return {"trace": trace, "determinant": determinant, "determinant_error": det_error, "excess": excess, "mu": mu, "hundredfold_time": math.log(100.0) / mu if mu > 0.0 else None}


def physical_matrices(t: np.ndarray, p: float, equilibrium: bool, period: float) -> np.ndarray:
    def rhs(x: float, y: np.ndarray) -> np.ndarray:
        mat = y.reshape(2, 2)
        f0 = 1.0 if equilibrium else F * float(ellipj(OMEGA * x, M)[2])
        coefficient = (p * p + U_RHO * (3.0 * f0 * f0 - 1.0)) / C_PSI
        return (np.asarray(((0.0, 1.0), (-coefficient, 0.0))) @ mat).reshape(-1)

    sol = solve_ivp(rhs, (float(t[0]), float(t[-1])), np.eye(2).reshape(-1), method="Radau", t_eval=t, rtol=RAD_TOL, atol=RAD_ATOL, max_step=period / 128.0)
    if not sol.success or sol.y.shape != (4, t.size):
        raise RuntimeError(f"Radau failed: {sol.message}")
    return sol.y.T.reshape(t.size, 2, 2)


def jacobi_reduce(expr: Any, s: Any, c: Any, v: Any, m: Any) -> Any:
    import sympy as sp

    groebner = sp.groebner((c * c + s * s - 1, v * v + m * s * s - 1), c, v, s, order="lex", domain=sp.EX)
    return sp.factor(groebner.reduce(sp.expand(expr))[1])


def symbolic_checks() -> dict[str, Any]:
    import sympy as sp

    s, c, v = sp.symbols("s c v")
    m = sp.Rational(2, 3)
    p, eps, kcx, x = sp.symbols("p epsilon k_Cx x", positive=True, finite=True)
    a, uC, B, hC = sp.symbols("a u_C B h_C", nonzero=True, finite=True)
    f = sp.symbols("f", real=True)

    def D(expr: Any) -> Any:
        return sp.diff(expr, s) * c * v + sp.diff(expr, c) * (-s * v) + sp.diff(expr, v) * (-m * s * c)

    d2v_expression = D(D(v)) - ((2 - m) * v - 2 * v ** 3)
    d2v_residual = jacobi_reduce(d2v_expression, s, c, v, m)
    F2 = sp.Rational(3, 2)
    cpsi = sp.Rational(1, 8)
    urho = sp.Integer(4)
    omega2 = sp.Integer(24)
    delta, eta, eta_tt = sp.symbols("delta eta eta_tt", real=True)
    varied_force = urho * ((f + delta * eta) ** 2 - 1) * (f + delta * eta)
    linear_equation = cpsi * eta_tt + p * p * eta + sp.diff(varied_force, delta).subs(delta, 0)
    linear_target = cpsi * eta_tt + (p * p + urho * (3 * f * f - 1)) * eta
    linear_residual = sp.factor(linear_equation - linear_target)
    lambda_expr = (sp.Integer(14) + p * p) / 3
    spectral_expression = (p * p + urho * (3 * F2 * (1 - m * s * s) - 1)) / (cpsi * omega2) - (lambda_expr - 6 * m * s * s)
    spectral_residual = sp.factor(spectral_expression)
    d = sp.sqrt(1 - m + m * m)
    edges = (2 * (1 + m) - 2 * d, 1 + m, 1 + 4 * m, 4 + m, 2 * (1 + m) + 2 * d)
    eigenfunctions = (
        ("E0", edges[0], 1 - (1 + m - d) * s * s),
        ("E1", edges[1], c * v),
        ("E2", edges[2], s * v),
        ("E3", edges[3], s * c),
        ("E4", edges[4], 1 - (1 + m + d) * s * s),
    )
    eigen_rows = []
    eigen_residuals = []
    for name, eigenvalue, function in eigenfunctions:
        expression = -D(D(function)) + 6 * m * s * s * function - eigenvalue * function
        residual = jacobi_reduce(expression, s, c, v, m)
        eigen_residuals.append(residual)
        eigen_rows.append({"name": name, "eigenvalue": sp.sstr(eigenvalue), "expression": sp.sstr(expression), "residual": sp.sstr(residual), "passed": residual == 0})
    pc2 = 2 * sp.sqrt(7) - 4
    edge_wave_expression = (edges[4] - edges[3]) - pc2 / 3
    edge_wave_residual = sp.simplify(edge_wave_expression)
    lower_gap_residual = sp.simplify(lambda_expr - edges[3] - p * p / 3)
    upper_gap_residual = sp.simplify(edges[4] - lambda_expr - (pc2 - p * p) / 3)
    length = sp.symbols("L", positive=True)
    critical_length = 2 * sp.pi / sp.sqrt(pc2)
    box_prefactor = pc2 * (length + critical_length) / (3 * length ** 2)
    box_expression = edges[4] - lambda_expr.subs(p, 2 * sp.pi / length) - box_prefactor * (length - critical_length)
    box_residual = sp.simplify(box_expression)
    box_positive = box_prefactor.is_positive is True
    R, I, Rt, It, Rxx, Ixx, Rtt, Itt = sp.symbols("R I R_t I_t R_xx I_xx R_tt I_tt")
    q = B - hC + hC * f ** 2 + uC * (R ** 2 + I ** 2)
    rho_t_expression = -2 * a * (Rt * It + R * Itt - It * Rt - I * Rtt)
    current_divergence = kcx * (R * Ixx - I * Rxx)
    continuity_expression = sp.expand((rho_t_expression + current_divergence).subs({Rtt: kcx * Rxx / (2 * a) - q * R / a, Itt: kcx * Ixx / (2 * a) - q * I / a}))
    continuity_residual = sp.factor(continuity_expression)
    R0 = eps * sp.cos(p * x)
    I0 = eps * sp.cos(2 * p * x)
    initial_density_expression = -2 * a * (R0 * 0 - I0 * 0)
    initial_density_residual = sp.simplify(initial_density_expression)
    two_mode_expression = -kcx * (R0 * sp.diff(I0, x, 2) - I0 * sp.diff(R0, x, 2))
    two_mode_target = 3 * kcx * eps ** 2 * p ** 2 * sp.cos(p * x) * sp.cos(2 * p * x)
    two_mode_residual = sp.trigsimp(two_mode_expression - two_mode_target)
    y = sp.symbols("y", real=True)
    cell_integral_expression = sp.integrate(sp.cos(y) * sp.cos(2 * y), (y, 0, 2 * sp.pi))
    theta, amplitude, amplitude_t, amplitude_x = sp.symbols("theta A A_t A_x", real=True)
    common_R, common_I = amplitude * sp.cos(theta), amplitude * sp.sin(theta)
    common_rho_expression = -2 * a * (common_R * amplitude_t * sp.sin(theta) - common_I * amplitude_t * sp.cos(theta))
    common_current_expression = kcx * (common_R * amplitude_x * sp.sin(theta) - common_I * amplitude_x * sp.cos(theta))
    common_rho_residual = sp.simplify(common_rho_expression)
    common_current_residual = sp.simplify(common_current_expression)
    reduced_values = [linear_residual, d2v_residual, spectral_residual, edge_wave_residual, lower_gap_residual, upper_gap_residual, box_residual, continuity_residual, initial_density_residual, two_mode_residual, cell_integral_expression, common_rho_residual, common_current_residual] + eigen_residuals
    passed = box_positive and all(value == 0 for value in reduced_values)
    return {
        "mediator_linearization": {"equation": sp.sstr(linear_equation), "target": sp.sstr(linear_target), "expression": sp.sstr(linear_equation - linear_target), "residual": sp.sstr(linear_residual), "passed": linear_residual == 0},
        "orbit_jacobi_identity": {"expression": sp.sstr(d2v_expression), "residual": sp.sstr(d2v_residual), "passed": d2v_residual == 0},
        "spectral_map": {"lambda": sp.sstr(lambda_expr), "expression": sp.sstr(spectral_expression), "residual": sp.sstr(spectral_residual), "passed": spectral_residual == 0},
        "lame_coefficient": {"coefficient": sp.sstr(6 * m), "expression": sp.sstr(6 * m - 4), "residual": sp.sstr(sp.simplify(6 * m - 4)), "passed": sp.simplify(6 * m - 4) == 0},
        "eigenfunctions": eigen_rows,
        "edge_wave_number": {"pc_squared": sp.sstr(pc2), "expression": sp.sstr(edge_wave_expression), "residual": sp.sstr(edge_wave_residual), "lower_gap_residual": sp.sstr(lower_gap_residual), "upper_gap_residual": sp.sstr(upper_gap_residual), "passed": edge_wave_residual == 0 and lower_gap_residual == 0 and upper_gap_residual == 0},
        "box_criterion": {"critical_length": sp.sstr(critical_length), "positive_prefactor": sp.sstr(box_prefactor), "prefactor_positive": box_positive, "expression": sp.sstr(box_expression), "residual": sp.sstr(box_residual), "passed": box_positive and box_residual == 0},
        "charge_continuity": {"force": sp.sstr(q), "expression": sp.sstr(continuity_expression), "residual": sp.sstr(continuity_residual), "passed": continuity_residual == 0},
        "two_mode_datum": {"initial_density_expression": sp.sstr(initial_density_expression), "initial_density_residual": sp.sstr(initial_density_residual), "derivative_expression": sp.sstr(two_mode_expression), "derivative_target": sp.sstr(two_mode_target), "derivative_residual": sp.sstr(two_mode_residual), "cell_integral_expression": sp.sstr(cell_integral_expression), "cell_integral_residual": sp.sstr(sp.simplify(cell_integral_expression)), "passed": initial_density_residual == 0 and two_mode_residual == 0 and cell_integral_expression == 0},
        "common_phase_real": {"density_expression": sp.sstr(common_rho_expression), "density_residual": sp.sstr(common_rho_residual), "current_expression": sp.sstr(common_current_expression), "current_residual": sp.sstr(common_current_residual), "passed": common_rho_residual == 0 and common_current_residual == 0},
        "all_passed": bool(passed),
    }


def compare_metric(failures: list[dict[str, Any]], name: str, actual: Any, expected: Any, tol: float = 2.0e-11) -> None:
    if expected is None:
        if actual is not None:
            mismatch(failures, name, None, actual, "metric mismatch")
    elif not number_ok(actual, float(expected), tol):
        mismatch(failures, name, expected, actual, "metric mismatch")


def check_primary_rows(primary: Mapping[str, Any], arrays: Mapping[str, np.ndarray], period: float, k: float, carrier_mu: float, failures: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    names = ("zero_mode", "critical_edge", "spatial_witness", "high_wave_control", "equilibrium_control")
    p_expected = np.asarray((0.0, P_C, k / 4.0, 2.0 * P_C, k / 4.0))
    rows = primary.get("arms")
    if not isinstance(rows, list) or len(rows) != 5:
        mismatch(failures, "primary.arms", 5, rows, "primary arm schedule mismatch")
        return [], {"p_errors": math.inf}
    reconstructed: list[dict[str, Any]] = []
    for i, name in enumerate(names):
        row = rows[i] if isinstance(rows[i], Mapping) else {}
        if row.get("name") != name:
            mismatch(failures, f"primary.arms[{i}].name", name, row.get("name"), "arm order/name mismatch")
        if row.get("success") is not True:
            mismatch(failures, f"primary.arms[{i}].success", True, row.get("success"), "primary arm did not succeed")
        if not number_ok(row.get("p"), float(p_expected[i]), 1.0e-11):
            mismatch(failures, f"primary.arms[{i}].p", p_expected[i], row.get("p"), "arm wave number mismatch")
        expected_metrics = arm_metrics(arrays["matrices"][i], period)
        if i == 4:
            w = math.sqrt((p_expected[4] ** 2 + 8.0) / C_PSI)
            wt = w * arrays["t"]
            exact = np.empty_like(arrays["matrices"][4])
            exact[:, 0, 0], exact[:, 0, 1] = np.cos(wt), np.sin(wt) / w
            exact[:, 1, 0], exact[:, 1, 1] = -w * np.sin(wt), np.cos(wt)
            expected_metrics["equilibrium_error"] = array_error(arrays["matrices"][4], exact, float(np.max(np.abs(exact))))
        actual_metrics = row.get("metrics") if isinstance(row.get("metrics"), Mapping) else {}
        for key, expected in expected_metrics.items():
            compare_metric(failures, f"primary.arms[{i}].metrics.{key}", actual_metrics.get(key), expected)
        reconstructed.append({"name": name, "p": float(p_expected[i]), "success": True, "metrics": expected_metrics})
    return reconstructed, {"p_errors": float(np.max(np.abs(arrays["p"] - p_expected)))}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--record", type=Path, default=REPORT_PATH)
    parser.add_argument("--pump", type=Path, default=DEFAULT_PUMP)
    parser.add_argument("--pump-verification", type=Path, default=DEFAULT_PUMP_VERIFICATION)
    args = parser.parse_args(argv)
    primary_dir = args.primary_dir.resolve()
    output_dir = args.output_dir.resolve()
    record = args.record.resolve()
    pump_dir = args.pump.resolve()
    pump_verify_dir = args.pump_verification.resolve()
    environment = {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": __import__("scipy").__version__, "platform": platform.platform()}
    failures: list[dict[str, Any]] = []
    if output_dir.exists():
        print("INCONCLUSIVE: refusing to overwrite an existing output directory")
        return 1
    output_dir.mkdir(parents=True, exist_ok=False)
    protocol_hash: str | None = None
    try:
        protocol_hash = sha256_bytes(protocol_section(record))
    except Exception as exc:
        mismatch(failures, "protocol", "readable frozen section", repr(exc), "protocol prerequisite failed")
    pump, pump_bytes = load_parent(pump_dir / "results.json", PUMP_RESULT_SHA256, PUMP_SCHEMA, failures, "pump")
    pump_verify, pump_verify_bytes = load_parent(pump_verify_dir / "results.json", PUMP_VERIFY_RESULT_SHA256, PUMP_VERIFY_SCHEMA, failures, "pump_verification")
    k_primary = mu_primary = k_verify = mu_verify = None
    if pump is not None:
        k_primary, mu_primary = primary_witness(pump, failures, "pump")
    if pump_verify is not None:
        k_verify, mu_verify = primary_witness(pump_verify, failures, "pump_verification")
    if k_primary is None or k_verify is None or abs(k_primary - k_verify) >= 1.0e-10:
        mismatch(failures, "parent.k", "agreement below 1e-10", (k_primary, k_verify), "parent witness wave numbers disagree")
    k = k_primary if k_primary is not None else 0.0
    primary, arrays, declared_files, primary_bytes, protocol_bytes = validate_primary_manifest(primary_dir, record, pump_dir, pump_verify_dir, failures)
    if failures or primary is None or arrays is None or pump is None or pump_verify is None or mu_primary is None or mu_verify is None or protocol_bytes is None:
        report = base_failure(failures, environment, protocol_hash)
        write_json_exclusive(output_dir / "results.json", report)
        return 1
    files: dict[str, str] = {}
    for name in ("source_primary.py", "source_verifier.py", "source_action.txt", "frozen_protocol.txt", "frozen_recovery.txt", "parent_primary_results.json", "parent_verification_results.json"):
        destination = output_dir / name
        shutil.copyfile(primary_dir / name, destination)
        files[name] = raw_sha256(destination)
    for source_name, retained_name in (("arrays.npz", "primary_arrays.npz"), ("results.json", "primary_results.json")):
        destination = output_dir / retained_name
        shutil.copyfile(primary_dir / source_name, destination)
        files[retained_name] = raw_sha256(destination)
    # Retained source bytes are evidence only; primary code is never imported or executed.
    period = 2.0 * float(ellipk(M)) / OMEGA
    expected_p = np.asarray((0.0, P_C, k / 4.0, 2.0 * P_C, k / 4.0), dtype=float)
    expected_t = np.linspace(0.0, period, SAMPLE_COUNT, dtype=float)
    if array_error(arrays["t"], expected_t) > 1.0e-14:
        mismatch(failures, "arrays.t", expected_t, arrays["t"], "physical sample schedule mismatch")
    if array_error(arrays["p"], expected_p) > 1.0e-12:
        mismatch(failures, "arrays.p", expected_p, arrays["p"], "arm wave-number schedule mismatch")
    if failures:
        report = base_failure(failures, environment, PROTOCOL_SHA256)
        report["files"] = files
        write_json_exclusive(output_dir / "results.json", report)
        return 1
    try:
        symbolic = symbolic_checks()
    except Exception as exc:
        mismatch(failures, "symbolic", "complete exact derivation", repr(exc), "symbolic derivation failed")
        symbolic = {"all_passed": False, "error": repr(exc)}
    if not symbolic.get("all_passed", False):
        mismatch(failures, "symbolic", "all exact residuals zero", symbolic, "symbolic identity failure")
        report = base_failure(failures, environment, PROTOCOL_SHA256)
        report["symbolic"] = symbolic
        report["files"] = files
        write_json_exclusive(output_dir / "results.json", report)
        return 1
    edge_exact = expected_edges()
    galerk = np.full((3, 5), np.nan)
    edge_errors = np.full((3, 5), np.nan)
    for di, n in enumerate(DIMS):
        count = 8 * n
        u_expected = np.arange(count, dtype=float) * (2.0 * float(ellipk(M)) / count)
        potential_expected = 4.0 * ellipj(u_expected, M)[0] ** 2
        fourier_expected = np.fft.fft(potential_expected) / count
        if array_error(arrays[f"u_n{n}"], u_expected) > 1.0e-14:
            mismatch(failures, f"arrays.u_n{n}", u_expected, arrays[f"u_n{n}"], "spectral sample coordinates mismatch")
        if array_error(arrays[f"potential_n{n}"], potential_expected) > 1.0e-12:
            mismatch(failures, f"arrays.potential_n{n}", potential_expected, arrays[f"potential_n{n}"], "sampled potential mismatch")
        if array_error(arrays[f"fourier_n{n}"], fourier_expected) > 1.0e-12:
            mismatch(failures, f"arrays.fourier_n{n}", fourier_expected, arrays[f"fourier_n{n}"], "Fourier coefficient mismatch")
        try:
            galerk[di] = galerk_edges(arrays[f"potential_n{n}"], n, float(ellipk(M)))
            edge_errors[di] = np.abs(galerk[di] - arrays["edges"][di])
        except Exception as exc:
            mismatch(failures, f"edges.{n}", "reconstructible", repr(exc), "independent Galerkin eigensolve failed")
    edge_changes = (float(np.max(np.abs(arrays["edges"][1] - arrays["edges"][0]))), float(np.max(np.abs(arrays["edges"][2] - arrays["edges"][1]))))
    max_edge_error = float(np.nanmax(np.abs(arrays["edges"] - edge_exact)))
    max_galerk_error = float(np.nanmax(edge_errors))
    for i, value in np.ndenumerate(edge_errors):
        if not math.isfinite(float(value)) or value >= EDGE_TOL:
            mismatch(failures, f"edges.reconstruction[{i[0]},{i[1]}]", f"<{EDGE_TOL}", float(value), "primary edge differs from independent Galerkin reconstruction")
    if max_edge_error >= EDGE_TOL:
        mismatch(failures, "edges.exact", f"<{EDGE_TOL}", max_edge_error, "primary edges differ from exact Lamé edges")
    if max(edge_changes) >= EDGE_TOL:
        mismatch(failures, "edges.convergence", f"<{EDGE_TOL}", edge_changes, "Galerkin edge convergence failure")
    primary_arms, primary_diag = check_primary_rows(primary, arrays, period, k, mu_primary, failures)
    expected_parameters = {"m": M, "Omega": OMEGA, "P": period, "pc": P_C, "pstar": k / 4.0, "k": k, "carrier_mu": mu_primary, "critical_length": 2.0 * math.pi / P_C, "original_length": 2.0 * math.pi / k, "extended_length": 8.0 * math.pi / k}
    pparams = primary.get("parameters") if isinstance(primary.get("parameters"), Mapping) else {}
    for key, expected in expected_parameters.items():
        compare_metric(failures, f"primary.parameters.{key}", pparams.get(key), expected, 1.0e-10)
    primary_raw_stats = [arm_metrics(arrays["matrices"][i], period) for i in range(5)]
    primary_equilibrium_error = primary_arms[4]["metrics"].get("equilibrium_error", math.inf) if primary_arms else math.inf
    primary_checks_expected = {
        "prerequisites": True, "protocol": True, "parents": True, "finite_arrays": True,
        "edge_convergence": max(edge_changes) < EDGE_TOL, "exact_edges": max_edge_error < EDGE_TOL,
        "matrices_present": bool(np.all(np.isfinite(arrays["matrices"]))),
        "determinant": all(stat["determinant_error"] < DET_TOL for stat in primary_raw_stats),
        "endpoint_traces": all(abs(primary_raw_stats[i]["trace"] - 2.0) < TRACE_TOL for i in (0, 1)),
        "controls": all(abs(primary_raw_stats[i]["trace"]) <= 2.0 + CONTROL_TRACE_TOL for i in (3, 4)),
        "equilibrium": primary_equilibrium_error < MATRIX_TOL,
        "spatial_witness": primary_raw_stats[2]["excess"] > 1.0e-8,
    }
    primary_checks_expected["all_qualifications"] = bool(all(primary_checks_expected.values()))
    pchecks = primary.get("checks") if isinstance(primary.get("checks"), Mapping) else {}
    if not isinstance(primary.get("checks"), Mapping) or not all(isinstance(v, bool) for v in pchecks.values()):
        mismatch(failures, "primary.checks", "mapping of booleans", primary.get("checks"), "invalid primary checks")
    for key, value in primary_checks_expected.items():
        if pchecks.get(key) != value:
            mismatch(failures, f"primary.checks.{key}", value, pchecks.get(key), "primary check reconstruction mismatch")
    if primary.get("qualified") != primary_checks_expected["all_qualifications"]:
        mismatch(failures, "primary.qualified", primary_checks_expected["all_qualifications"], primary.get("qualified"), "primary qualification mismatch")
    pdiag = primary.get("diagnostics") if isinstance(primary.get("diagnostics"), Mapping) else {}
    primary_witness_mu = primary_raw_stats[2]["mu"]
    primary_ratio = primary_witness_mu / mu_primary if mu_primary > 0 else math.nan
    verification_ratio_for_primary = primary_witness_mu / mu_verify if mu_verify > 0 else math.nan
    expected_pdiag = {"exact_edges": edge_exact, "edge_change": max(edge_changes), "exact_edge_error": max_edge_error, "equilibrium_error": primary_equilibrium_error, "carrier_mu_primary": mu_primary, "carrier_mu_verification": mu_verify, "witness_mu": primary_witness_mu, "witness_carrier_ratio": primary_ratio, "witness_carrier_ratio_verification": verification_ratio_for_primary, "tenfold_faster": bool(primary_ratio > 10.0 and verification_ratio_for_primary > 10.0), "errors": []}
    for key, expected in expected_pdiag.items():
        if key not in pdiag:
            mismatch(failures, f"primary.diagnostics.{key}", expected, None, "missing primary diagnostic")
        elif isinstance(expected, bool):
            if pdiag[key] != expected:
                mismatch(failures, f"primary.diagnostics.{key}", expected, pdiag[key], "primary diagnostic mismatch")
        elif key == "exact_edges":
            actual = np.asarray(pdiag[key], dtype=float) if isinstance(pdiag[key], (list, tuple)) else np.asarray([], dtype=float)
            if array_error(actual, expected) > EDGE_TOL:
                mismatch(failures, f"primary.diagnostics.{key}", expected, pdiag[key], "primary exact-edge diagnostic mismatch")
        elif key == "errors":
            if pdiag[key] != expected:
                mismatch(failures, f"primary.diagnostics.{key}", expected, pdiag[key], "primary diagnostic error list mismatch")
        else:
            compare_metric(failures, f"primary.diagnostics.{key}", pdiag[key], expected, 1.0e-9)
    independent_matrices = np.full_like(arrays["matrices"], np.nan)
    independent_arms: list[dict[str, Any]] = []
    matrix_errors: list[float] = []
    for i, name in enumerate(("zero_mode", "critical_edge", "spatial_witness", "high_wave_control", "equilibrium_control")):
        try:
            independent_matrices[i] = physical_matrices(arrays["t"], float(expected_p[i]), i == 4, period)
            stats = arm_metrics(independent_matrices[i], period)
            independent_arms.append({"name": name, "p": float(expected_p[i]), "success": True, "metrics": stats})
            denominator = max(1.0, float(np.max(np.abs(independent_matrices[i]))))
            err = array_error(arrays["matrices"][i], independent_matrices[i], denominator)
            matrix_errors.append(err)
            if not math.isfinite(err) or err >= MATRIX_TOL:
                mismatch(failures, f"matrices.{name}", f"<{MATRIX_TOL}", err, "primary/independent matrix discrepancy")
            raw_stats = arm_metrics(arrays["matrices"][i], period)
            if raw_stats["determinant_error"] >= DET_TOL:
                mismatch(failures, f"matrices.{name}.determinant", f"<{DET_TOL}", raw_stats["determinant_error"], "primary determinant error")
            if stats["determinant_error"] >= DET_TOL:
                mismatch(failures, f"independent.{name}.determinant", f"<{DET_TOL}", stats["determinant_error"], "independent determinant error")
        except Exception as exc:
            mismatch(failures, f"matrices.{name}", "complete Radau result", repr(exc), "independent physical evolution failed")
            independent_arms.append({"name": name, "p": float(expected_p[i]), "success": False, "metrics": {"trace": None, "determinant": None, "determinant_error": None, "excess": None, "mu": None, "hundredfold_time": None}})
            matrix_errors.append(math.inf)
    endpoint_error = max(abs(float(np.trace(independent_matrices[0, -1])) - 2.0), abs(float(np.trace(independent_matrices[1, -1])) - 2.0)) if np.all(np.isfinite(independent_matrices[:2])) else math.inf
    controls_ok = all((abs(float(np.trace(independent_matrices[i, -1])) ) <= 2.0 + CONTROL_TRACE_TOL) if np.all(np.isfinite(independent_matrices[i])) else False for i in (3, 4))
    if endpoint_error >= TRACE_TOL:
        mismatch(failures, "endpoint_traces", f"<{TRACE_TOL}", endpoint_error, "endpoint trace is not +2")
    if not controls_ok:
        mismatch(failures, "controls", True, controls_ok, "control trace exceeds frozen bound")
    w = math.sqrt((expected_p[4] ** 2 + 8.0) / C_PSI)
    analytic = np.empty_like(independent_matrices[4])
    wt = w * arrays["t"]
    analytic[:, 0, 0] = np.cos(wt)
    analytic[:, 0, 1] = np.sin(wt) / w
    analytic[:, 1, 0] = -w * np.sin(wt)
    analytic[:, 1, 1] = np.cos(wt)
    equilibrium_error = array_error(independent_matrices[4], analytic, float(np.max(np.abs(analytic))))
    if equilibrium_error >= MATRIX_TOL:
        mismatch(failures, "equilibrium", f"<{MATRIX_TOL}", equilibrium_error, "equilibrium differs from analytic constant-frequency matrix")
    metrics = independent_arms[2]["metrics"]
    witness_mu = float(metrics["mu"]) if metrics["mu"] is not None else 0.0
    witness_ratio_primary = witness_mu / mu_primary if mu_primary > 0 else math.nan
    witness_ratio_verification = witness_mu / mu_verify if mu_verify > 0 else math.nan
    tenfold = bool(primary_ratio > 10.0 and witness_ratio_verification > 10.0)
    diagnostics = {
        "edge_change": max(edge_changes), "edge_change_63_127": edge_changes[0], "edge_change_127_255": edge_changes[1],
        "exact_edge_error": max_edge_error, "galerkin_reconstruction_error": max_galerk_error,
        "matrix_errors": matrix_errors, "max_matrix_error": max(matrix_errors, default=math.inf),
        "endpoint_trace_error": endpoint_error, "equilibrium_error": equilibrium_error,
        "carrier_mu_primary": mu_primary, "carrier_mu_verification": mu_verify,
        "witness_mu": witness_mu, "witness_carrier_ratio": witness_ratio_verification,
        "witness_carrier_ratio_primary": witness_ratio_primary,
        "witness_carrier_ratio_verification": witness_ratio_verification, "tenfold_faster": tenfold,
        "hundredfold_time": math.log(100.0) / witness_mu if witness_mu > 0 else None,
    }
    checks = {
        "primary_qualification": primary_checks_expected["all_qualifications"],
        "symbolic": bool(symbolic.get("all_passed", False)), "finite": not failures,
        "schedule": array_error(arrays["t"], expected_t) <= 1.0e-14 and array_error(arrays["p"], expected_p) <= 1.0e-12,
        "galerkin": max_galerk_error < EDGE_TOL and max(edge_changes) < EDGE_TOL,
        "exact_edges": max_edge_error < EDGE_TOL, "determinants": all(a.get("success") and a["metrics"]["determinant_error"] < DET_TOL for a in independent_arms),
        "matrices": bool(matrix_errors) and max(matrix_errors) < MATRIX_TOL, "endpoints": endpoint_error < TRACE_TOL,
        "controls": controls_ok, "equilibrium": equilibrium_error < MATRIX_TOL,
    }
    # Reconstruct semantic primary booleans when present; altered checks must not pass silently.
    pchecks = primary.get("checks") if isinstance(primary.get("checks"), Mapping) else {}
    if not isinstance(primary.get("checks"), Mapping) or not all(isinstance(v, bool) for v in pchecks.values()):
        mismatch(failures, "primary.checks", "mapping of booleans", primary.get("checks"), "invalid primary checks")
    for key, value in checks.items():
        if key in pchecks and pchecks[key] != value:
            mismatch(failures, f"primary.checks.{key}", value, pchecks[key], "primary check reconstruction mismatch")
    qualified = bool(not failures and all(checks.values()))
    diagnostics["tenfold_faster"] = bool(qualified and tenfold)
    passed = bool(qualified and independent_arms[2]["metrics"]["excess"] > 1.0e-8 and primary_arms and primary_arms[2]["metrics"]["excess"] > 1.0e-8)
    verdict = "SUPPORTS—spatial mediator instability in the supplied temporal parent" if passed else "INCONCLUSIVE"
    np.savez(output_dir / "independent_arrays.npz", t=arrays["t"], p=expected_p, matrices=independent_matrices, exact_edges=edge_exact)
    files["independent_arrays.npz"] = raw_sha256(output_dir / "independent_arrays.npz")
    parameters = {"m": M, "Omega": OMEGA, "P": period, "pc": P_C, "pstar": k / 4.0, "k": k, "carrier_mu": mu_verify, "critical_length": 2.0 * math.pi / P_C, "original_length": 2.0 * math.pi / k, "extended_length": 8.0 * math.pi / k}
    report = {"schema": VERIFY_SCHEMA, "passed": passed, "qualified": qualified, "verdict": verdict, "error": None if qualified else "; ".join(str(x["reason"]) for x in failures), "protocol_sha256": PROTOCOL_SHA256, "files": files, "parameters": parameters, "arms": independent_arms, "checks": checks, "diagnostics": diagnostics, "symbolic": symbolic, "environment": environment, "mismatches": failures}
    write_json_exclusive(output_dir / "results.json", report)
    print(json.dumps({"verdict": verdict, "passed": passed, "qualified": qualified, "mismatches": len(failures)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
