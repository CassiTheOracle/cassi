#!/usr/bin/env python3
"""Independent LSODA/Hamiltonian verifier for the frozen nonlinear transfer receipt."""
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
import scipy
from scipy.integrate import solve_ivp
from scipy.special import ellipj
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "computations" / "matter-formation-continuum-report.md"
ACTION_PATH = ROOT / "foundations" / "particle-stationary-action-closure.md"
PUMP_DIR_DEFAULT = ROOT / "runs" / "20260907_matter_formation_autonomous_pump"
PUMP_VERIFICATION_DIR_DEFAULT = ROOT / "runs" / "20260907_matter_formation_autonomous_pump_verification"
PROTOCOL_HEADING = "### 26.3 Nonlinear transfer calculation: pre-execution criteria"
PROTOCOL_SHA256 = "82c7e628f00b275fde856c2f52b11782de12dfdd686aea3568be15efbb9f6106"
PUMP_PRIMARY_SHA256 = "cad33ef760404c79807570be1269390dfb790574dc13bfe60d61d67c5b1bc9c5"
PUMP_VERIFY_SHA256 = "a54c07d1a973f9a915355e26b7c23e7caa7ee75a468f09fda53e13a272959758"
PRIMARY_SCHEMA = "cassi.matter-formation.autonomous-transfer.v1"
VERIFY_SCHEMA = "cassi.matter-formation.autonomous-transfer-verification.v1"
PUMP_SCHEMA = "cassi.matter-formation.autonomous-pump.v1"
PUMP_VERIFY_SCHEMA = "cassi.matter-formation.autonomous-pump-verification.v1"
PUMP_VERDICT = "SUPPORTS—neutral linear parametric amplification in the supplied temporal parent"
PROVISIONAL_VERDICT = "INCONCLUSIVE—awaiting independent nonlinear qualification"
SUPPORT_VERDICT = "SUPPORTS—neutral nonlinear energy transfer in the supplied temporal parent"
INCONCLUSIVE_VERDICT = "INCONCLUSIVE—no resolved nonlinear transfer in the fixed time window"
ARM_NAMES = ("full", "uncoupled", "zero_carrier", "linear_reference")
ARM_SPEC = {
    "full": (1, 2.9598260763447164, 1.0, 1.0e-6),
    "uncoupled": (0, 0.0, 1.0, 1.0e-6),
    "zero_carrier": (1, 2.9598260763447164, 1.0, 0.0),
    "linear_reference": (0, 2.9598260763447164, 0.0, 1.0e-6),
}
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
H_C = 2.9598260763447164
E_C = 0.75
A = 1.0 / 16.0
C_PSI = 1.0 / 8.0
F = math.sqrt(3.0 / 2.0)
B = E_C + 1.0 / (4.0 * A)
RTOL = 2.0e-12
ATOL = (2.0e-14, C_PSI * 2.0e-14, 2.0e-20, 2.0 * A * 2.0e-20, 2.0e-16)
MAX_BALANCE = 1.0e-7
MAX_UNCOUPLED_CHANGE = 1.0e-5
MAX_ZERO_ORBIT = 2.0e-5
MAX_EARLY = 2.0e-3
MAX_GROWTH_REL = 5.0e-3
MAX_STATE_REL = 5.0e-4
MAX_WORK_REL = 1.0e-6
MAX_PRIMARY_REL = 1.0e-10
PARAM_TOL = 1.0e-12

METRIC_KEYS = (
    "initial_total_energy", "initial_carrier_energy", "balance_scale", "total_balance_error",
    "carrier_work_error", "mediator_work_error", "peak_carrier_energy", "peak_index", "peak_time",
    "energy_gain", "transfer_fraction", "final_carrier_energy", "final_transfer_fraction", "max_abs_f",
    "max_abs_fdot", "max_abs_y", "max_abs_ydot", "max_fractional_carrier_change",
)
CHECK_KEYS = ("energy_work", "uncoupled_energy", "zero_carrier", "zero_orbit", "early_linear", "linear_growth", "complete_finite")


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def frozen_section(path: Path) -> bytes:
    text = canonical_bytes(path).decode("utf-8")
    if text.count(PROTOCOL_HEADING) != 1:
        raise ValueError("frozen nonlinear-transfer heading must occur exactly once")
    start = text.find(PROTOCOL_HEADING)
    tail = text[start + len(PROTOCOL_HEADING):]
    match = re.search(r"(?m)^#{1,3}\s+", tail)
    end = start + len(PROTOCOL_HEADING) + match.start() if match else len(text)
    return (text[start:end].rstrip() + "\n").encode("utf-8")


def strict_json(path: Path) -> Any:
    def reject_constant(value: str) -> Any:
        raise ValueError(f"nonfinite JSON constant {value}")

    def reject_duplicate(items: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in items:
            if key in output:
                raise ValueError(f"duplicate JSON key {key!r}")
            output[key] = value
        return output

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate, parse_constant=reject_constant)


def finite_tree(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and finite_tree(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_tree(item) for item in value)
    if value is None or isinstance(value, (bool, str)):
        return True
    return isinstance(value, (int, float, np.number)) and math.isfinite(float(value))


def safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return safe(value.item())
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, complex):
        return [safe(value.real), safe(value.imag)]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(safe(payload), handle, ensure_ascii=False, allow_nan=False, indent=2)
        handle.write("\n")


def mismatch(failures: list[dict[str, Any]], name: str, expected: Any, actual: Any, reason: str) -> None:
    failures.append({"name": name, "expected": safe(expected), "actual": safe(actual), "reason": reason})


def close_scalar(actual: Any, expected: Any, tol: float = PARAM_TOL) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual == expected
    if not isinstance(actual, (int, float, np.number)) or not isinstance(expected, (int, float, np.number)):
        return actual == expected
    return math.isfinite(float(actual)) and math.isfinite(float(expected)) and abs(float(actual) - float(expected)) <= tol * max(1.0, abs(float(expected)))


def relative_array_error(actual: np.ndarray, expected: np.ndarray, denominator: float | None = None) -> float:
    if actual.shape != expected.shape or actual.size == 0:
        return math.inf if actual.shape != expected.shape else 0.0
    if not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected)):
        return math.inf
    scale = max(1.0, float(np.max(np.abs(expected)))) if denominator is None else max(float(denominator), 1.0e-300)
    return float(np.max(np.abs(actual - expected)) / scale)

def elementwise_relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
    if actual.shape != expected.shape or actual.size == 0:
        return math.inf if actual.shape != expected.shape else 0.0
    if not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected)):
        return math.inf
    denominator = np.maximum(1.0, np.abs(expected))
    return float(np.max(np.abs(actual - expected) / denominator))


def exact_orbit(t: np.ndarray) -> np.ndarray:
    sn, cn, dn, _ = ellipj(math.sqrt(24.0) * t, 2.0 / 3.0)
    return np.column_stack((F * dn, -F * math.sqrt(24.0) * (2.0 / 3.0) * sn * cn))


def energy_from_state(state: np.ndarray, k: float, h: float, u: float) -> np.ndarray:
    f, fdot, y, ydot = state[:, 0], state[:, 1], state[:, 2], state[:, 3]
    ef = C_PSI / 2.0 * fdot * fdot + U_RHO / 4.0 * (f * f - 1.0) ** 2
    dk = K_CX * k * k / 2.0 + B - h
    ey = A * ydot * ydot + (dk + h * f * f) * y * y + u / 2.0 * y ** 4
    return np.column_stack((ef, ey, ef + ey))




def integrate_arm(t: np.ndarray, period: float, k: float, b: int, h: float, u: float, seed: float) -> tuple[np.ndarray, dict[str, Any]]:
    # Keep this wrapper explicit so the Hamiltonian state and the output velocity state
    # cannot be confused.  LSODA receives the exact frozen P/32 maximum step.
    initial = np.asarray((F, 0.0, seed, 0.0, 0.0), dtype=np.float64)
    dk = K_CX * k * k / 2.0 + B - h

    def rhs(_time: float, q: np.ndarray) -> np.ndarray:
        f, p, y, r, _work = q
        fdot = p / C_PSI
        return np.asarray((fdot, -U_RHO * (f * f - 1.0) * f - 2.0 * b * h * f * y * y,
                           r / (2.0 * A), -2.0 * (dk + h * f * f + u * y * y) * y,
                           2.0 * h * f * fdot * y * y), dtype=np.float64)

    state = np.full((t.size, 5), np.nan, dtype=np.float64)
    meta: dict[str, Any] = {"success": False, "nfev": None, "njev": None, "nlu": None, "message": None}
    try:
        result = solve_ivp(rhs, (float(t[0]), float(t[-1])), initial, method="LSODA", t_eval=t, rtol=RTOL,
                           atol=np.asarray(ATOL, dtype=np.float64), max_step=period / 32.0)
        count = min(int(result.y.shape[1]), int(t.size))
        if count:
            state[:count, 0] = result.y[0, :count]
            state[:count, 1] = result.y[1, :count] / C_PSI
            state[:count, 2] = result.y[2, :count]
            state[:count, 3] = result.y[3, :count] / (2.0 * A)
            state[:count, 4] = result.y[4, :count]
        meta.update({"success": bool(result.success and result.y.shape == (5, t.size)),
                     "nfev": int(result.nfev), "njev": int(getattr(result, "njev", 0)),
                     "nlu": int(getattr(result, "nlu", 0)), "message": str(result.message)})
    except Exception as exc:
        meta["message"] = repr(exc)
    return state, meta


def arm_metrics(t: np.ndarray, state: np.ndarray, energy: np.ndarray, name: str) -> dict[str, Any]:
    if energy.size == 0 or not np.all(np.isfinite(energy)):
        return {key: None for key in METRIC_KEYS}
    ef, ey, et = energy[:, 0], energy[:, 1], energy[:, 2]
    w = state[:, 4]
    scale = float(max(et[0], float(np.max(ey))) if name == "linear_reference" else et[0])
    y0 = float(ey[0])
    peak_index = int(np.argmax(ey))
    return {
        "initial_total_energy": float(et[0]), "initial_carrier_energy": y0, "balance_scale": scale,
        "total_balance_error": float(np.max(np.abs(et - et[0] - (0.0 if name != "linear_reference" else 1.0) * w)) / scale),
        "carrier_work_error": float(np.max(np.abs(ey - ey[0] - w)) / scale),
        "mediator_work_error": float(np.max(np.abs(ef - ef[0] + (0.0 if name == "linear_reference" or name == "uncoupled" else 1.0) * w)) / scale),
        "peak_carrier_energy": float(ey[peak_index]), "peak_index": peak_index, "peak_time": float(t[peak_index]),
        "energy_gain": None if y0 == 0.0 else float(np.max(ey) / y0),
        "transfer_fraction": float((np.max(ey) - y0) / et[0]), "final_carrier_energy": float(ey[-1]),
        "final_transfer_fraction": float((ey[-1] - y0) / et[0]), "max_abs_f": float(np.max(np.abs(state[:, 0]))),
        "max_abs_fdot": float(np.max(np.abs(state[:, 1]))), "max_abs_y": float(np.max(np.abs(state[:, 2]))),
        "max_abs_ydot": float(np.max(np.abs(state[:, 3]))),
        "max_fractional_carrier_change": None if y0 == 0.0 else float(np.max(np.abs(ey - y0)) / y0),
    }


def symbolic_checks() -> dict[str, Any]:
    f, fd, y, yd, p, r = sp.symbols("f fd y yd p r", real=True)
    b, h, u, c, a, ur, D = sp.symbols("b h u c a ur D", real=True)
    fdd = (-ur * (f ** 2 - 1) * f - 2 * b * h * f * y ** 2) / c
    ydd = -(D + h * f ** 2 + u * y ** 2) * y / a
    ef = c * fd ** 2 / 2 + ur * (f ** 2 - 1) ** 2 / 4
    ey = a * yd ** 2 + (D + h * f ** 2) * y ** 2 + u * y ** 4 / 2
    work = 2 * h * f * fd * y ** 2
    d_ef = sp.diff(ef, f) * fd + sp.diff(ef, fd) * fdd
    d_ey = sp.diff(ey, f) * fd + sp.diff(ey, y) * yd + sp.diff(ey, yd) * ydd
    tests: dict[str, Any] = {}

    def put(name: str, expression: Any, details: Mapping[str, Any] | None = None) -> None:
        reduced = sp.simplify(sp.expand(expression))
        tests[name] = {"expression": str(reduced), "passed": bool(reduced == 0), **dict(details or {})}

    put("energy_work", d_ey - work)
    put("mediator_work", d_ef + b * work)
    put("total_work", d_ef + d_ey - (1 - b) * work)
    H = p ** 2 / (2 * c) + ur * (f ** 2 - 1) ** 2 / 4 + r ** 2 / (4 * a) + (D + h * f ** 2) * y ** 2 + u * y ** 4 / 2
    put("hamiltonian_f", p / c - sp.diff(H, p), {"case": "b=1"})
    put("hamiltonian_p", (-ur * (f ** 2 - 1) * f - 2 * h * f * y ** 2) + sp.diff(H, f), {"case": "b=1"})
    put("hamiltonian_y", r / (2 * a) - sp.diff(H, r), {"case": "b=1"})
    put("hamiltonian_r", -2 * (D + h * f ** 2 + u * y ** 2) * y + sp.diff(H, y), {"case": "b=1"})
    put("force_correction", (-ur * (f ** 2 - 1) * f - 2 * b * h * f * y ** 2) - (-sp.diff(H, f) + 2 * (1 - b) * h * f * y ** 2), {"case": "general b"})
    x, transverse_y, transverse_z, ksym, ys, yds = sp.symbols("x transverse_y transverse_z k ys yds", real=True)
    z = ys * sp.exp(sp.I * ksym * x)
    zd = yds * sp.exp(sp.I * ksym * x)
    modulus = sp.conjugate(z) * z
    put("plane_wave_laplacian", sp.diff(z, x, 2) + ksym ** 2 * z)
    put("plane_wave_modulus", modulus - ys ** 2)
    put("zero_local_signed_charge", sp.simplify(sp.expand_complex(-2 * a * sp.im(sp.conjugate(z) * zd))))
    put("uniform_spatial_density_x", sp.diff(modulus, x))
    put("uniform_spatial_density_y", sp.diff(modulus, transverse_y))
    put("uniform_spatial_density_z", sp.diff(modulus, transverse_z))
    tests["passed"] = bool(all(item.get("passed", False) for item in tests.values()))
    return tests


def load_transfer_arrays(path: Path, failures: list[dict[str, Any]], expected_n: int | None = None) -> dict[str, np.ndarray] | None:
    required = {"t"} | {f"state_{name}" for name in ARM_NAMES} | {f"energy_{name}" for name in ARM_NAMES}
    if not path.is_file():
        mismatch(failures, str(path.name), "present", None, "missing array archive")
        return None
    try:
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != required:
                mismatch(failures, f"{path.name}.keys", sorted(required), sorted(archive.files), "exact NPZ key set mismatch")
                return None
            arrays = {name: np.asarray(archive[name]) for name in archive.files}
    except Exception as exc:
        mismatch(failures, str(path.name), "readable NPZ", repr(exc), "cannot read array archive")
        return None
    n = arrays["t"].size
    if expected_n is not None and n != expected_n:
        mismatch(failures, f"{path.name}.t.shape", (expected_n,), arrays["t"].shape, "sample count mismatch")
    if arrays["t"].dtype != np.dtype("float64") or arrays["t"].ndim != 1:
        mismatch(failures, f"{path.name}.t", "float64 vector", arrays["t"].dtype.str, "invalid time array")
    for name in ARM_NAMES:
        for prefix, shape in (("state", (n, 5)), ("energy", (n, 3))):
            key = f"{prefix}_{name}"
            if arrays[key].dtype != np.dtype("float64") or arrays[key].shape != shape:
                mismatch(failures, f"{path.name}.{key}", ("float64", shape), (arrays[key].dtype.str, arrays[key].shape), "invalid array dtype or shape")
    for key, array in arrays.items():
        if not np.all(np.isfinite(array)):
            mismatch(failures, f"{path.name}.{key}", "finite", "nonfinite", "nonfinite prerequisite array")
    return arrays if not failures else None


def validate_manifest(root: Path, receipt: Mapping[str, Any], failures: list[dict[str, Any]], label: str) -> None:
    files = receipt.get("files")
    if not isinstance(files, Mapping):
        mismatch(failures, f"{label}.files", "mapping", files, "invalid file manifest")
        return
    for rel, declared in files.items():
        if not isinstance(rel, str) or Path(rel).is_absolute() or ".." in Path(rel).parts:
            mismatch(failures, f"{label}.files.{rel}", "safe relative path", rel, "unsafe manifest path")
            continue
        path = root / rel
        actual = raw_sha256(path) if path.is_file() else None
        if actual != declared:
            mismatch(failures, f"{label}.files.{rel}", declared, actual, "manifest identity mismatch")


def load_inherited(root: Path, expected_hash: str, schema: str, failures: list[dict[str, Any]], label: str) -> Mapping[str, Any] | None:
    path = root / "results.json"
    if not path.is_file():
        mismatch(failures, f"{label}.results.json", "present", None, "missing inherited receipt")
        return None
    actual_hash = raw_sha256(path)
    if actual_hash != expected_hash:
        mismatch(failures, f"{label}.results.json", expected_hash, actual_hash, "pinned inherited receipt hash mismatch")
    try:
        receipt = strict_json(path)
    except Exception as exc:
        mismatch(failures, f"{label}.results.json", "strict JSON", repr(exc), "invalid inherited receipt")
        return None
    if not isinstance(receipt, Mapping) or not finite_tree(receipt):
        mismatch(failures, f"{label}.results.json", "finite JSON object", type(receipt).__name__, "invalid inherited receipt tree")
        return None
    if receipt.get("schema") != schema or receipt.get("qualified") is not True or receipt.get("passed") is not True or receipt.get("verdict") != PUMP_VERDICT:
        mismatch(failures, label, {"schema": schema, "qualified": True, "passed": True, "verdict": PUMP_VERDICT}, {key: receipt.get(key) for key in ("schema", "qualified", "passed", "verdict")}, "inherited qualification status mismatch")
    if label.endswith("verification") and receipt.get("mismatches") != []:
        mismatch(failures, f"{label}.mismatches", [], receipt.get("mismatches"), "inherited independent mismatches are not empty")
    validate_manifest(root, receipt, failures, label)
    return receipt


def witness_parameter(primary_parent: Mapping[str, Any], independent_parent: Mapping[str, Any], failures: list[dict[str, Any]]) -> tuple[float, float, float] | None:
    def find(receipt: Mapping[str, Any], label: str) -> Mapping[str, Any] | None:
        rows = receipt.get("witnesses")
        selected = [row for row in rows if isinstance(row, Mapping) and row.get("j") == 3] if isinstance(rows, list) else []
        if len(selected) != 1:
            mismatch(failures, f"{label}.witnesses.j3", "exactly one resolved witness", selected, "missing or nonunique third-gap witness")
            return None
        row = selected[0]
        if row.get("unstable") is not True or row.get("passed") is not True or not all(isinstance(row.get(key), (int, float)) and math.isfinite(float(row[key])) for key in ("k", "mu")):
            mismatch(failures, f"{label}.witnesses.j3", "resolved finite witness", row, "third-gap witness is not resolved")
        return row

    p = find(primary_parent, "pump_primary")
    q = find(independent_parent, "pump_verification")
    if p is None or q is None:
        return None
    for key in ("k", "mu"):
        if not close_scalar(p.get(key), q.get(key), 2.0e-8):
            mismatch(f"witness.j3.{key}", p.get(key), q.get(key), "inherited witness disagreement")
    po = primary_parent.get("orbit")
    qo = independent_parent.get("orbit")
    if not isinstance(po, Mapping) or not isinstance(qo, Mapping) or not close_scalar(po.get("period"), qo.get("period"), 2.0e-12):
        mismatch(failures, "witness.period", po.get("period") if isinstance(po, Mapping) else None, qo.get("period") if isinstance(qo, Mapping) else None, "inherited period disagreement")
        return None
    return float(p["k"]), float(p["mu"]), float(po["period"])


def validate_primary(primary_dir: Path, record: Path, pump: Mapping[str, Any], pump_verify: Mapping[str, Any], failures: list[dict[str, Any]]) -> tuple[Mapping[str, Any] | None, dict[str, np.ndarray] | None, dict[str, Any] | None]:
    result_path = primary_dir / "results.json"
    if not result_path.is_file():
        mismatch(failures, "primary.results.json", "present", None, "missing primary receipt")
        return None, None, None
    try:
        primary = strict_json(result_path)
    except Exception as exc:
        mismatch(failures, "primary.results.json", "strict JSON", repr(exc), "invalid primary JSON")
        return None, None, None
    if not isinstance(primary, Mapping) or not finite_tree(primary):
        mismatch(failures, "primary.results.json", "finite JSON object", type(primary).__name__, "invalid primary receipt tree")
        return None, None, None
    required = {"schema", "passed", "qualified", "verdict", "error", "protocol_sha256", "files", "parameters", "arms", "checks", "diagnostics"}
    if not required <= set(primary):
        mismatch(failures, "primary.results.keys", sorted(required), sorted(primary), "missing required primary keys")
    if primary.get("schema") != PRIMARY_SCHEMA:
        mismatch(failures, "primary.schema", PRIMARY_SCHEMA, primary.get("schema"), "primary schema mismatch")
    if primary.get("qualified") is not True or primary.get("passed") is not False or primary.get("verdict") != PROVISIONAL_VERDICT:
        mismatch(failures, "primary.status", {"qualified": True, "passed": False, "verdict": PROVISIONAL_VERDICT}, {key: primary.get(key) for key in ("qualified", "passed", "verdict")}, "primary provisional status mismatch")
    try:
        protocol = frozen_section(record)
        if sha256_bytes(protocol) != PROTOCOL_SHA256 or primary.get("protocol_sha256") != PROTOCOL_SHA256:
            mismatch(failures, "protocol_sha256", PROTOCOL_SHA256, (sha256_bytes(protocol), primary.get("protocol_sha256")), "frozen protocol hash mismatch")
    except Exception as exc:
        mismatch(failures, "protocol", "frozen §26.3", repr(exc), "cannot derive frozen protocol")
        protocol = b""
    validate_manifest(primary_dir, primary, failures, "primary")
    files = primary.get("files") if isinstance(primary.get("files"), Mapping) else {}
    required_files = ("source_primary.py", "source_verifier.py", "frozen_protocol.txt", "source_action.txt", "parent_results.json", "parent_verification_results.json", "arrays.npz")
    for name in required_files:
        if name not in files:
            mismatch(failures, f"primary.files.{name}", "declared", files, "required retained identity missing")
    for name in required_files:
        path = primary_dir / name
        if not path.is_file():
            mismatch(failures, f"primary.{name}", "present", None, "required retained evidence missing")
    if (primary_dir / "frozen_protocol.txt").is_file() and (primary_dir / "frozen_protocol.txt").read_bytes() != protocol:
        mismatch(failures, "primary.frozen_protocol.txt", "exact frozen bytes", "different bytes", "primary protocol snapshot mismatch")
    if (primary_dir / "source_action.txt").is_file() and ACTION_PATH.is_file() and (primary_dir / "source_action.txt").read_bytes() != ACTION_PATH.read_bytes():
        mismatch(failures, "primary.source_action.txt", "exact action bytes", "different bytes", "source action snapshot mismatch")
    witness = witness_parameter(pump, pump_verify, failures)
    if witness is None:
        return primary, None, None
    k, mu, period = witness
    J = int(math.ceil(16.0 / (mu * period)))
    expected_n = 16 * J + 1
    params = primary.get("parameters")
    expected_params = {"k": k, "mu": mu, "period": period, "period_count": J, "sample_count": expected_n,
                       "early_end_index": 16 * math.floor(2.0 / (mu * period)),
                       "slope_indices": [16 * math.floor(4.0 / (mu * period)), 16 * math.floor(6.0 / (mu * period))],
                       "carrier_seed": 1.0e-6, "u_rho": U_RHO, "u_C": U_C, "k_Cx": K_CX, "h_C": H_C,
                       "e_C": E_C, "a": A, "c_psi": C_PSI, "F": F}
    if not isinstance(params, Mapping):
        mismatch(failures, "primary.parameters", expected_params, params, "missing primary parameter ledger")
    else:
        for key, expected in expected_params.items():
            actual = params.get(key)
            if isinstance(expected, list):
                if actual != expected:
                    mismatch(failures, f"primary.parameters.{key}", expected, actual, "frozen index schedule mismatch")
            elif not close_scalar(actual, expected, 2.0e-10 if key in ("k", "mu", "period") else PARAM_TOL):
                mismatch(failures, f"primary.parameters.{key}", expected, actual, "frozen parameter mismatch")
    arrays = load_transfer_arrays(primary_dir / "arrays.npz", failures, expected_n)
    if (primary_dir / "source_verifier.py").is_file() and (primary_dir / "source_verifier.py").read_bytes() != Path(__file__).read_bytes():
        mismatch(failures, "primary.source_verifier.py", "exact current verifier bytes", "different bytes", "primary verifier snapshot differs from this implementation")
    if arrays is None:
        return primary, None, {"k": k, "mu": mu, "period": period, "J": J, "n": expected_n, "early": expected_params["early_end_index"], "slope": expected_params["slope_indices"]}
    expected_t = np.arange(expected_n, dtype=np.float64) * period / 16.0
    if relative_array_error(arrays["t"], expected_t, 1.0) > 1.0e-14:
        mismatch(failures, "primary.arrays.t", expected_t, arrays["t"], "frozen sample schedule mismatch")
    rows = primary.get("arms")
    if not isinstance(rows, list) or len(rows) != 4:
        mismatch(failures, "primary.arms", "four rows", rows, "invalid primary arm schedule")
    else:
        for index, name in enumerate(ARM_NAMES):
            row = rows[index]
            if not isinstance(row, Mapping) or row.get("name") != name or not {"name", "method", "success", "nfev", "njev", "nlu", "metrics"} <= set(row):
                mismatch(failures, f"primary.arms[{index}]", name, row, "invalid fixed arm row")
            elif not isinstance(row.get("metrics"), Mapping) or not set(METRIC_KEYS) <= set(row["metrics"]):
                mismatch(failures, f"primary.arms[{index}].metrics", METRIC_KEYS, row.get("metrics"), "incomplete arm metrics")
    return primary, arrays, {"k": k, "mu": mu, "period": period, "J": J, "n": expected_n, "early": expected_params["early_end_index"], "slope": expected_params["slope_indices"]}


def reconstruct_and_qualify(primary: Mapping[str, Any], primary_arrays: Mapping[str, np.ndarray], cfg: Mapping[str, Any], failures: list[dict[str, Any]]) -> tuple[dict[str, np.ndarray], dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], bool]:
    t = primary_arrays["t"]
    independent_states: dict[str, np.ndarray] = {}
    independent_energies: dict[str, np.ndarray] = {}
    primary_energies: dict[str, np.ndarray] = {}
    independent_rows: list[dict[str, Any]] = []
    primary_rows = primary.get("arms") if isinstance(primary.get("arms"), list) else []
    for index, name in enumerate(ARM_NAMES):
        b, h, u, seed = ARM_SPEC[name]
        state, solver = integrate_arm(t, float(cfg["period"]), float(cfg["k"]), b, h, u, seed)
        energy = energy_from_state(state, float(cfg["k"]), h, u)
        independent_states[name] = state
        independent_energies[name] = energy
        independent_rows.append({"name": name, "method": "LSODA-Hamiltonian", **solver, "metrics": arm_metrics(t, state, energy, name)})
        print(json.dumps({"arm": name, "method": "LSODA-Hamiltonian", "success": solver["success"]}, ensure_ascii=False), flush=True)
        if not solver["success"]:
            mismatch(failures, f"solver.{name}", "complete successful LSODA trajectory", solver, "independent evolution failed")
        pstate = primary_arrays[f"state_{name}"]
        pener = primary_arrays[f"energy_{name}"]
        recomputed = energy_from_state(pstate, float(cfg["k"]), h, u)
        primary_energies[name] = recomputed
        energy_error = elementwise_relative_error(pener, recomputed)
        if energy_error >= MAX_PRIMARY_REL:
            mismatch(failures, f"primary.energy_{name}", f"<{MAX_PRIMARY_REL}", energy_error, "primary energy array reconstruction mismatch")
        if index < len(primary_rows) and isinstance(primary_rows[index], Mapping):
            expected_metrics = arm_metrics(t, pstate, recomputed, name)
            actual_metrics = primary_rows[index].get("metrics") if isinstance(primary_rows[index].get("metrics"), Mapping) else {}
            for key in METRIC_KEYS:
                expected = expected_metrics.get(key)
                actual = actual_metrics.get(key)
                if expected is None:
                    if actual is not None:
                        mismatch(failures, f"primary.arms[{index}].metrics.{key}", None, actual, "null metric contract mismatch")
                elif not close_scalar(actual, expected, MAX_PRIMARY_REL):
                    mismatch(failures, f"primary.arms[{index}].metrics.{key}", expected, actual, "primary summary reconstruction mismatch")
    primary_states = {name: primary_arrays[f"state_{name}"] for name in ARM_NAMES}
    primary_checks, primary_diag = qualification(primary_energies, primary_states, t, cfg, failures, "primary")
    independent_checks, independent_diag = qualification(independent_energies, independent_states, t, cfg, failures, "independent")
    for label, checks in (("primary", primary_checks), ("independent", independent_checks)):
        for key, passed in checks.items():
            if not passed:
                mismatch(failures, f"{label}.qualification.{key}", True, passed, "numerical qualification failed")
    for key in CHECK_KEYS:
        if isinstance(primary.get("checks"), Mapping) and primary["checks"].get(key) != primary_checks[key]:
            mismatch(failures, f"primary.checks.{key}", primary_checks[key], primary["checks"].get(key), "primary qualification flag mismatch")
    if isinstance(primary.get("diagnostics"), Mapping):
        compare_diagnostics(primary["diagnostics"], primary_diag, failures)
    states_for_archive: dict[str, np.ndarray] = {"t": t}
    for name in ARM_NAMES:
        states_for_archive[f"state_{name}"] = independent_states[name]
        states_for_archive[f"energy_{name}"] = independent_energies[name]
    both_qualified = bool(not failures and all(primary_checks.values()) and all(independent_checks.values()))
    return states_for_archive, {"checks": independent_checks, "diagnostics": independent_diag}, {"checks": primary_checks, "diagnostics": primary_diag}, independent_rows, primary_energies, both_qualified


def qualification(energies: Mapping[str, np.ndarray], states: Mapping[str, np.ndarray], t: np.ndarray, cfg: Mapping[str, Any], failures: list[dict[str, Any]], label: str) -> tuple[dict[str, bool], dict[str, Any]]:
    finite = all(np.all(np.isfinite(energies[name])) and np.all(np.isfinite(states[name])) for name in ARM_NAMES)
    metrics = {name: arm_metrics(t, states[name], energies[name], name) for name in ARM_NAMES}
    balance = all(all(float(metrics[name][key]) < MAX_BALANCE for key in ("total_balance_error", "carrier_work_error", "mediator_work_error")) for name in ARM_NAMES) if finite else False
    uncoupled = finite and float(metrics["uncoupled"]["max_fractional_carrier_change"]) < MAX_UNCOUPLED_CHANGE
    zero = finite and np.array_equal(states["zero_carrier"][:, 2:], np.zeros_like(states["zero_carrier"][:, 2:]))
    exact = exact_orbit(t)
    zero_orbit_errors = [relative_array_error(states["zero_carrier"][:, component], exact[:, component], max(1.0, float(np.max(np.abs(exact[:, component]))))) for component in (0, 1)] if finite else [math.inf, math.inf]
    zero_orbit = finite and all(error < MAX_ZERO_ORBIT for error in zero_orbit_errors)
    end = min(int(cfg["early"]), t.size - 1)
    early_errors = []
    if finite:
        for component in (2, 3):
            denominator = max(1.0e-6, float(np.max(np.abs(states["linear_reference"][:end + 1, component]))))
            early_errors.append(float(np.max(np.abs(states["full"][:end + 1, component] - states["linear_reference"][:end + 1, component])) / denominator))
    else:
        early_errors = [math.inf, math.inf]
    early = finite and all(error < MAX_EARLY for error in early_errors)
    lo, hi = map(int, cfg["slope"])
    omega0 = math.sqrt((K_CX * float(cfg["k"]) ** 2 / 2.0 + B - H_C + H_C * F * F) / A)
    amplitude = np.sqrt(states["linear_reference"][:, 2] ** 2 + (states["linear_reference"][:, 3] / omega0) ** 2) if finite else np.full(t.size, np.nan)
    rate = float((math.log(amplitude[hi]) - math.log(amplitude[lo])) / (t[hi] - t[lo])) if finite and amplitude[lo] > 0 and amplitude[hi] > 0 else math.nan
    growth_rel = abs(rate - float(cfg["mu"])) / float(cfg["mu"]) if math.isfinite(rate) else math.inf
    growth = finite and growth_rel < MAX_GROWTH_REL
    exceed = np.flatnonzero(energies["linear_reference"][:, 1] > energies["full"][0, 2]) if finite else np.asarray([], dtype=int)
    exceed_index = int(exceed[0]) if exceed.size else None
    diagnostics = {"zero_orbit_errors": zero_orbit_errors, "early_linear_errors": early_errors, "linear_growth_rate": rate,
                   "linear_growth_relative_error": growth_rel, "linear_reference_exceedance_index": exceed_index,
                   "linear_reference_exceedance_time": None if exceed_index is None else float(t[exceed_index])}
    checks = {"energy_work": balance, "uncoupled_energy": uncoupled, "zero_carrier": zero, "zero_orbit": zero_orbit,
              "early_linear": early, "linear_growth": growth, "complete_finite": finite}
    return checks, diagnostics

def compare_diagnostics(actual: Mapping[str, Any], expected: Mapping[str, Any], failures: list[dict[str, Any]]) -> None:
    for key in ("zero_orbit_errors", "early_linear_errors"):
        av, ev = actual.get(key), expected[key]
        if not isinstance(av, list) or len(av) != 2 or any(not close_scalar(a, e, MAX_PRIMARY_REL) for a, e in zip(av, ev)):
            mismatch(failures, f"primary.diagnostics.{key}", ev, av, "diagnostic reconstruction mismatch")
    for key in ("linear_growth_rate", "linear_growth_relative_error", "linear_reference_exceedance_index", "linear_reference_exceedance_time"):
        if not close_scalar(actual.get(key), expected[key], MAX_PRIMARY_REL):
            mismatch(failures, f"primary.diagnostics.{key}", expected[key], actual.get(key), "diagnostic reconstruction mismatch")


def compare_states(primary_arrays: Mapping[str, np.ndarray], independent_arrays: Mapping[str, np.ndarray], metrics: Mapping[str, Any], failures: list[dict[str, Any]]) -> dict[str, Any]:
    errors: dict[str, Any] = {}
    for name in ARM_NAMES:
        row: dict[str, Any] = {}
        scale_work = float(metrics[name].get("balance_scale") or math.nan)
        for component in range(4):
            denominator = max(1.0e-6, float(np.max(np.abs(primary_arrays[f"state_{name}"][:, component]))))
            row[str(component)] = relative_array_error(independent_arrays[f"state_{name}"][:, component], primary_arrays[f"state_{name}"][:, component], denominator)
            if not math.isfinite(row[str(component)]) or row[str(component)] >= MAX_STATE_REL:
                mismatch(failures, f"state.{name}.{component}", f"<{MAX_STATE_REL}", row[str(component)], "independent trajectory mismatch")
        row["W"] = relative_array_error(independent_arrays[f"state_{name}"][:, 4], primary_arrays[f"state_{name}"][:, 4], scale_work)
        if not math.isfinite(row["W"]) or row["W"] >= MAX_WORK_REL:
            mismatch(failures, f"state.{name}.W", f"<{MAX_WORK_REL}", row["W"], "independent work mismatch")
        errors[name] = row
    return errors


def base_failure(failures: list[dict[str, Any]], environment: Mapping[str, Any]) -> dict[str, Any]:
    return {"schema": VERIFY_SCHEMA, "passed": False, "qualified": False, "verdict": "INCONCLUSIVE",
            "error": "; ".join(str(row["reason"]) for row in failures) if failures else "prerequisite failure",
            "protocol_sha256": None, "parameters": {}, "files": {}, "arms": [],
            "checks": {key: False for key in CHECK_KEYS},
            "diagnostics": {"zero_orbit_errors": [], "early_linear_errors": [], "linear_growth_rate": None,
                            "linear_growth_relative_error": None, "linear_reference_exceedance_index": None,
                            "linear_reference_exceedance_time": None}, "mismatches": failures,
            "environment": dict(environment)}


def retain_file(output: Path, name: str, source: Path, files: dict[str, str]) -> None:
    destination = output / name
    with source.open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    files[name] = raw_sha256(destination)

def retain_bytes(output: Path, name: str, data: bytes, files: dict[str, str]) -> None:
    destination = output / name
    with destination.open("xb") as handle:
        handle.write(data)
    files[name] = raw_sha256(destination)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--record", type=Path, default=REPORT_PATH)
    parser.add_argument("--pump-dir", type=Path, default=PUMP_DIR_DEFAULT)
    parser.add_argument("--pump-verification-dir", type=Path, default=PUMP_VERIFICATION_DIR_DEFAULT)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    failures: list[dict[str, Any]] = []
    environment = {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__, "platform": platform.platform()}
    if output.exists():
        print("INCONCLUSIVE: refusing to overwrite an existing output directory")
        return 1
    output.mkdir(parents=True, exist_ok=False)
    pump = load_inherited(args.pump_dir.resolve(), PUMP_PRIMARY_SHA256, PUMP_SCHEMA, failures, "pump_primary")
    pump_verify = load_inherited(args.pump_verification_dir.resolve(), PUMP_VERIFY_SHA256, PUMP_VERIFY_SCHEMA, failures, "pump_verification")
    primary, primary_arrays, cfg = (None, None, None)
    if pump is not None and pump_verify is not None:
        primary, primary_arrays, cfg = validate_primary(args.primary_dir.resolve(), args.record.resolve(), pump, pump_verify, failures)
    if not ACTION_PATH.is_file():
        mismatch(failures, "source_action", "present", None, "missing stationary-action source")
    if failures or primary is None or primary_arrays is None or cfg is None:
        report = base_failure(failures, environment)
        try:
            report["protocol_sha256"] = sha256_bytes(frozen_section(args.record.resolve()))
        except Exception:
            pass
        write_json_exclusive(output / "results.json", report)
        return 1

    # No symbolic or numerical work occurs before this point.  All following data
    # are generated independently from the primary raw states and frozen constants.
    try:
        symbolic = symbolic_checks()
    except Exception as exc:
        symbolic = {"passed": False, "error": repr(exc)}
    if not symbolic.get("passed", False):
        mismatch(failures, "symbolic", "all exact reductions", symbolic, "symbolic identity failure")
        report = base_failure(failures, environment)
        report.update({"protocol_sha256": PROTOCOL_SHA256, "symbolic": symbolic})
        write_json_exclusive(output / "results.json", report)
        return 1
    independent_arrays, independent_summary, primary_summary, independent_rows, reconstructed_primary, qualified = reconstruct_and_qualify(primary, primary_arrays, cfg, failures)
    primary_metrics = {row["name"]: row["metrics"] for row in primary.get("arms", []) if isinstance(row, Mapping) and isinstance(row.get("metrics"), Mapping)}
    state_errors = compare_states(primary_arrays, independent_arrays, primary_metrics, failures)
    checks = independent_summary["checks"]
    checks["complete_finite"] = bool(checks["complete_finite"] and all(np.all(np.isfinite(array)) for array in independent_arrays.values()))
    gain_primary = float(primary_metrics.get("full", {}).get("energy_gain")) if primary_metrics.get("full", {}).get("energy_gain") is not None else math.nan
    gain_independent = float(independent_rows[0]["metrics"].get("energy_gain")) if independent_rows and independent_rows[0]["metrics"].get("energy_gain") is not None else math.nan
    transfer_primary = float(primary_metrics.get("full", {}).get("transfer_fraction")) if primary_metrics.get("full", {}).get("transfer_fraction") is not None else math.nan
    transfer_independent = float(independent_rows[0]["metrics"].get("transfer_fraction")) if independent_rows and independent_rows[0]["metrics"].get("transfer_fraction") is not None else math.nan
    for key, expected in (("G", gain_primary), ("R", transfer_primary)):
        for label, container in (("primary", primary), ("primary.diagnostics", primary["diagnostics"])):
            if not close_scalar(container.get(key), expected, MAX_PRIMARY_REL):
                mismatch(failures, f"{label}.{key}", expected, container.get(key), "primary transfer summary mismatch")
    candidate = bool(primary.get("qualified") is True and gain_primary >= 100.0 and transfer_primary >= 1.0e-5)
    if primary.get("candidate_support") is not None and primary.get("candidate_support") != candidate:
        mismatch(failures, "primary.candidate_support", candidate, primary.get("candidate_support"), "primary candidate threshold mismatch")
    state_errors["summary_reconstruction"] = {"primary_energy_arrays": {name: elementwise_relative_error(primary_arrays[f"energy_{name}"], reconstructed_primary[name]) for name in ARM_NAMES}}
    all_qualified = bool(not failures and symbolic.get("passed", False) and all(checks.values()) and all(primary_summary["checks"].values()) and qualified)
    passed = bool(all_qualified and gain_primary >= 100.0 and gain_independent >= 100.0 and transfer_primary >= 1.0e-5 and transfer_independent >= 1.0e-5)
    verdict = SUPPORT_VERDICT if passed else INCONCLUSIVE_VERDICT if all_qualified else "INCONCLUSIVE"
    files: dict[str, str] = {}
    retain_file(output, "source_verifier.py", Path(__file__), files)
    retain_file(output, "source_primary.py", args.primary_dir.resolve() / "source_primary.py", files)
    retain_bytes(output, "frozen_protocol.txt", frozen_section(args.record.resolve()), files)
    retain_file(output, "source_action.txt", ACTION_PATH, files)
    retain_file(output, "parent_results.json", args.pump_dir.resolve() / "results.json", files)
    retain_file(output, "parent_verification_results.json", args.pump_verification_dir.resolve() / "results.json", files)
    retain_file(output, "primary_results.json", args.primary_dir.resolve() / "results.json", files)
    retain_file(output, "primary_arrays.npz", args.primary_dir.resolve() / "arrays.npz", files)
    np.savez(output / "independent_arrays.npz", **independent_arrays)
    files["independent_arrays.npz"] = raw_sha256(output / "independent_arrays.npz")
    reconstructed_archive = {"t": primary_arrays["t"]}
    reconstructed_archive.update({f"energy_{name}": reconstructed_primary[name] for name in ARM_NAMES})
    np.savez(output / "reconstructed_primary_arrays.npz", **reconstructed_archive)
    files["reconstructed_primary_arrays.npz"] = raw_sha256(output / "reconstructed_primary_arrays.npz")
    report = {"schema": VERIFY_SCHEMA, "passed": passed, "qualified": all_qualified, "verdict": verdict,
              "error": None if all_qualified else "; ".join(str(row["reason"]) for row in failures),
              "protocol_sha256": PROTOCOL_SHA256, "parameters": {"k": cfg["k"], "mu": cfg["mu"], "period": cfg["period"], "period_count": cfg["J"], "sample_count": cfg["n"], "early_end_index": cfg["early"], "slope_indices": cfg["slope"], "carrier_seed": 1.0e-6, "u_rho": U_RHO, "u_C": U_C, "k_Cx": K_CX, "h_C": H_C, "e_C": E_C, "a": A, "c_psi": C_PSI, "F": F},
              "files": files, "arms": independent_rows, "checks": checks,
              "diagnostics": independent_summary["diagnostics"], "symbolic": symbolic, "state_errors": state_errors,
              "primary_reconstructed_checks": primary_summary["checks"], "primary_reconstructed_diagnostics": primary_summary["diagnostics"],
              "primary_candidate_support": candidate, "primary_gain": gain_primary, "primary_transfer_fraction": transfer_primary,
              "independent_gain": gain_independent, "independent_transfer_fraction": transfer_independent,
              "mismatches": failures, "environment": environment}
    write_json_exclusive(output / "results.json", report)
    print(json.dumps({"verdict": verdict, "qualified": all_qualified, "passed": passed, "mismatches": len(failures)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
