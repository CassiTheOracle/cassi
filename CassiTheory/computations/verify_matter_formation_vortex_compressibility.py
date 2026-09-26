#!/usr/bin/env python3
"""Independent finite-difference verifier for the constrained vortex response."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

import verify_matter_formation_vortex_core as core_verify

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = "computations/matter-formation-continuum-report.md"
HEADING = "## 47. Working notes:"
SCHEMA = "matter-formation-vortex-compressibility-verification-v1"
MANIFEST_SCHEMA = "matter-formation-vortex-compressibility-manifest-v1"
PARENT_SUMMARY = "runs/20260908_matter_formation_vortex_loaded/primary/summary.json"
PARENT_VERIFICATION = "runs/20260908_matter_formation_vortex_loaded/verification/verification.json"
CAPS = ("plus", "minus")
EPS = {"plus": 1, "minus": -1}
POPULATIONS = (1.0, 16.0, 64.0)
GRIDS = ((32.0, 256), (32.0, 512), (64.0, 512), (64.0, 1024))
STEPS = (2.0 ** -12, 2.0 ** -13, 2.0 ** -14)
LAMBDA_C = 1.0
K_CX = 1.0
ETA_C = 1.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value: Any) -> bool:
    if value is None or isinstance(value, (bool, np.bool_)):
        return False
    try:
        return bool(math.isfinite(float(value)))
    except (TypeError, ValueError, OverflowError):
        return False


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, (np.integer, np.floating)):
        return jsonable(value.item())
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def strict_json(path: Path) -> dict[str, Any]:
    def reject(value: Any) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"nonfinite JSON number in {path}")
        return value

    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)), object_hook=lambda d: d)
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    def walk(v: Any) -> None:
        if isinstance(v, float):
            reject(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(value)
    return value


def safe_path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"invalid relative path: {value!r}")
    path = (root / value).resolve()
    if path != root.resolve() and root.resolve() not in path.parents:
        raise ValueError(f"path escapes root: {value}")
    return path


def check(bucket: dict[str, Any], name: str, passed: bool, evidence: Any = None) -> None:
    bucket.setdefault("checks", []).append({"name": name, "pass": bool(passed), "evidence": jsonable(evidence)})
    if not passed:
        bucket.setdefault("failures", []).append(name)


def relerr(actual: float, expected: float, floor: float = 1.0) -> float:
    if not finite(actual) or not finite(expected):
        return math.inf
    return abs(float(actual) - float(expected)) / max(floor, abs(float(expected)))


def array_relerr(actual: np.ndarray, expected: np.ndarray, floor: float = 1.0) -> float:
    if actual.shape != expected.shape or np.iscomplexobj(actual) or np.iscomplexobj(expected):
        return math.inf
    if not (np.all(np.isfinite(actual)) and np.all(np.isfinite(expected))):
        return math.inf
    return float(np.max(np.abs(actual - expected) / np.maximum(floor, np.abs(expected)))) if actual.size else 0.0


def expected_rows() -> list[tuple[str, int, float, int, float]]:
    return [(cap, EPS[cap], int(n), int(R), int(N)) for cap in CAPS for n in POPULATIONS for R, N in GRIDS]


def verify_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = strict_json(manifest_path)
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("manifest schema mismatch")
    section = manifest.get("section")
    if not isinstance(section, dict) or section.get("path") != NOTEBOOK or section.get("heading") != HEADING:
        raise ValueError("manifest section identity mismatch")
    snapshot = safe_path(manifest_path.parent, section.get("snapshot"))
    live = safe_path(ROOT, NOTEBOOK)
    if section.get("sha256") != sha256(snapshot):
        raise ValueError("section snapshot hash mismatch")
    frozen = snapshot.read_text(encoding="utf-8")
    live_text = live.read_text(encoding="utf-8")
    at = live_text.find(HEADING)
    if at < 0 or live_text[at : at + len(frozen)] != frozen:
        raise ValueError("live report does not contain exact frozen section prefix")

    required_sources = {
        "computations/matter_formation_vortex_core.py",
        "computations/verify_matter_formation_vortex_core.py",
        "computations/matter_formation_vortex_loaded.py",
        "computations/verify_matter_formation_vortex_loaded.py",
        "computations/matter_formation_vortex_compressibility.py",
        "computations/verify_matter_formation_vortex_compressibility.py",
    }
    sources = manifest.get("sources")
    if not isinstance(sources, list) or {x.get("path") for x in sources if isinstance(x, dict)} != required_sources:
        raise ValueError("manifest sources differ from six required programs")
    source_receipts = []
    for item in sources:
        if not isinstance(item, dict):
            raise ValueError("invalid source receipt")
        path = safe_path(ROOT, item.get("path"))
        snap = safe_path(manifest_path.parent, item.get("snapshot"))
        expected = item.get("sha256")
        if not isinstance(expected, str) or sha256(path) != expected or sha256(snap) != expected:
            raise ValueError(f"source hash mismatch: {item.get('path')}")
        source_receipts.append({"path": item["path"], "snapshot": item["snapshot"], "sha256": expected})

    inputs = manifest.get("inputs")
    if not isinstance(inputs, list) or len(inputs) != 24:
        raise ValueError("manifest must contain exactly 24 inputs")
    input_receipts = []
    expected_identities = {(cap, eps, n, R, N) for cap, eps, n, R, N in expected_rows()}
    actual_identities = set()
    for item in inputs:
        if not isinstance(item, dict):
            raise ValueError("invalid input receipt")
        path = safe_path(ROOT, item.get("path"))
        identity = (item.get("cap"), item.get("epsilon"), item.get("n"), item.get("R"), item.get("N"))
        actual_identities.add(identity)
        expected = item.get("sha256")
        if not isinstance(expected, str) or sha256(path) != expected:
            raise ValueError(f"input hash mismatch: {item.get('path')}")
        input_receipts.append({"path": item["path"], "sha256": expected, "cap": item.get("cap"), "epsilon": item.get("epsilon"), "n": item.get("n"), "R": item.get("R"), "N": item.get("N")})
    if actual_identities != expected_identities:
        raise ValueError("manifest inputs do not cover exact 24-row schedule")

    evidence = manifest.get("evidence")
    required_evidence = {PARENT_SUMMARY, PARENT_VERIFICATION}
    if not isinstance(evidence, list) or {x.get("path") for x in evidence if isinstance(x, dict)} != required_evidence:
        raise ValueError("manifest evidence must contain accepted parent summary and verification")
    evidence_receipts = []
    for item in evidence:
        path = safe_path(ROOT, item.get("path"))
        expected = item.get("sha256")
        if not isinstance(expected, str) or sha256(path) != expected:
            raise ValueError(f"evidence hash mismatch: {item.get('path')}")
        evidence_receipts.append({"path": item["path"], "sha256": expected})
    return {"section": section, "sources": source_receipts, "inputs": input_receipts, "evidence": evidence_receipts}


def parent_acceptance() -> tuple[dict[str, Any], dict[str, Any]]:
    summary = strict_json(ROOT / PARENT_SUMMARY)
    verification = strict_json(ROOT / PARENT_VERIFICATION)
    if summary.get("complete_physical_matter_formation") is not False or not summary.get("all_rows_numerically_qualified"):
        raise ValueError("parent summary is not accepted or is marked complete")
    if verification.get("complete_physical_matter_formation") is not False or verification.get("numerical_pass") is not True:
        raise ValueError("parent verification is not accepted or is marked complete")
    rows = summary.get("rows")
    if not isinstance(rows, list) or len(rows) != 24:
        raise ValueError("parent summary must contain exactly 24 rows")
    if not all(isinstance(row, dict) and row.get("complete_physical_matter_formation") is False for row in rows):
        raise ValueError("parent rows must all retain complete_physical_matter_formation=false")
    identities = {(row.get("cap"), int(row.get("n", -1)), float(row.get("R", -1)), int(row.get("N", -1))) for row in rows}
    if identities != {(cap, n, R, N) for cap, _, n, R, N in expected_rows()}:
        raise ValueError("parent summary rows do not cover exact schedule")
    return summary, verification


def quadrature(r: np.ndarray, y: np.ndarray, epsilon: int) -> dict[str, np.ndarray]:
    xi = np.asarray(core_verify.GAUSS_X, dtype=np.float64)
    n = r.size - 1
    dr = np.diff(r)
    t0 = (1.0 - xi) / 2.0
    t1 = (1.0 + xi) / 2.0
    rq = 0.5 * (r[:-1] + r[1:])[:, None] + 0.5 * dr[:, None] * xi[None, :]
    yq = t0[None, :, None] * y[:-1, None, :] + t1[None, :, None] * y[1:, None, :]
    ydq = (y[1:] - y[:-1])[:, None, :] / dr[:, None, None]
    flat = core_verify.reconstruct_profiles(rq.reshape(-1), yq.reshape(-1, 5), epsilon)
    fields = flat["physical"].reshape(n, 2, 5)
    weights = flat["weights"].reshape(n, 2, 5)
    weight_derivatives = flat["weight_derivatives"].reshape(n, 2, 5)
    derivs = weight_derivatives * yq + weights * ydq
    qweight = 2.0 * math.pi * rq * dr[:, None] / 2.0
    return {"rq": rq, "yq": yq, "fields": fields, "derivs": derivs, "weights": weights, "weight_derivatives": weight_derivatives, "qweight": qweight, "t0": t0, "t1": t1, "dr": dr}


def lumped_mass(r: np.ndarray) -> np.ndarray:
    xi = np.asarray(core_verify.GAUSS_X, dtype=np.float64)
    lump = np.zeros(r.size, dtype=np.float64)
    for e, dr in enumerate(np.diff(r)):
        rq = 0.5 * (r[e] + r[e + 1]) + 0.5 * dr * xi
        w = 2.0 * math.pi * rq * dr / 2.0
        shape = np.column_stack(((1.0 - xi) / 2.0, (1.0 + xi) / 2.0))
        lump[e : e + 2] += shape.T @ w
    return lump


def reconstruct(r: np.ndarray, y: np.ndarray, f: np.ndarray, epsilon: int, mu: float, lump: np.ndarray | None = None) -> dict[str, Any]:
    q = quadrature(r, y, epsilon)
    vals = q["fields"].reshape(-1, 5)
    ders = q["derivs"].reshape(-1, 5)
    rq = q["rq"].reshape(-1)
    funcs = core_verify.local_lambdas(epsilon)
    zero_h = np.zeros_like(rq)
    args0 = tuple(vals[:, j] for j in range(5)) + tuple(ders[:, j] for j in range(5)) + (zero_h, rq)
    hcoef = np.asarray(funcs["H"](*args0), dtype=np.float64).reshape(-1)
    lcoef = np.asarray(funcs["L"](*args0), dtype=np.float64).reshape(-1)
    h = -lcoef / hcoef
    args = tuple(vals[:, j] for j in range(5)) + tuple(ders[:, j] for j in range(5)) + (h, rq)
    density = np.asarray(funcs["energy"](*args), dtype=np.float64).reshape(-1)
    n = r.size - 1
    energy_core = float(np.sum(q["qweight"].reshape(-1) * density))
    t0, t1 = q["t0"], q["t1"]
    fq = t0[None, :] * f[:-1, None] + t1[None, :] * f[1:, None]
    dfq = np.broadcast_to(((f[1:] - f[:-1]) / q["dr"])[:, None], (n, 2))
    rho = np.sum(q["fields"][..., :2] ** 2, axis=-1)
    carrier_density = K_CX * dfq * dfq / 2.0 - ETA_C * (core_verify.RHO0 - rho) * fq * fq + LAMBDA_C * fq**4 / 2.0
    energy = energy_core + float(np.sum(q["qweight"] * carrier_density))
    core_grad = np.zeros((n + 1, 5), dtype=np.float64)
    f_grad = np.zeros(n + 1, dtype=np.float64)
    pop_grad = np.zeros(n + 1, dtype=np.float64)
    partials = np.stack([np.asarray(fn(*args), dtype=np.float64).reshape(n, 2) for fn in funcs["partials"]], axis=-1)
    dpartials = np.stack([np.asarray(fn(*args), dtype=np.float64).reshape(n, 2) for fn in funcs["dpartials"]], axis=-1)
    pvals = partials.reshape(-1, 5)
    pdvals = dpartials.reshape(-1, 5)
    sh0 = np.broadcast_to(t0[None, :], (n, 2))
    sh1 = np.broadcast_to(t1[None, :], (n, 2))
    dshape0 = -1.0 / q["dr"][:, None]
    dshape1 = 1.0 / q["dr"][:, None]
    carrier_y = np.zeros((n, 2, 5), dtype=np.float64)
    carrier_y[..., 0] = 2.0 * ETA_C * q["fields"][..., 0] * fq * fq
    carrier_y[..., 1] = 2.0 * ETA_C * q["fields"][..., 1] * fq * fq
    local_f = -2.0 * ETA_C * (core_verify.RHO0 - rho) * fq + 2.0 * LAMBDA_C * fq**3
    for j in range(5):
        c0 = q["qweight"] * (pvals[:, j].reshape(n, 2) * q["weights"][..., j] * sh0 + pdvals[:, j].reshape(n, 2) * (q["weight_derivatives"][..., j] * sh0 + q["weights"][..., j] * dshape0))
        c1 = q["qweight"] * (pvals[:, j].reshape(n, 2) * q["weights"][..., j] * sh1 + pdvals[:, j].reshape(n, 2) * (q["weight_derivatives"][..., j] * sh1 + q["weights"][..., j] * dshape1))
        core_grad[:-1, j] += np.sum(c0, axis=1)
        core_grad[1:, j] += np.sum(c1, axis=1)
    for j in range(5):
        c0 = q["qweight"] * carrier_y[..., j] * q["weights"][..., j] * sh0
        c1 = q["qweight"] * carrier_y[..., j] * q["weights"][..., j] * sh1
        core_grad[:-1, j] += np.sum(c0, axis=1)
        core_grad[1:, j] += np.sum(c1, axis=1)
    f_grad[:-1] += np.sum(q["qweight"] * (K_CX * dfq * dshape0 + local_f * sh0), axis=1)
    f_grad[1:] += np.sum(q["qweight"] * (K_CX * dfq * dshape1 + local_f * sh1), axis=1)
    pop_grad[:-1] += np.sum(q["qweight"] * 2.0 * fq * sh0, axis=1)
    pop_grad[1:] += np.sum(q["qweight"] * 2.0 * fq * sh1, axis=1)
    population = float(np.sum(q["qweight"] * fq * fq))
    grad_energy_x = np.column_stack((core_grad[:-1], f_grad[:-1])).reshape(-1)
    b_x = np.column_stack((np.zeros((n, 5)), pop_grad[:-1])).reshape(-1)
    grad_lagrangian_x = grad_energy_x - mu * b_x
    if lump is None:
        lump = lumped_mass(r)
    scale = np.repeat(np.sqrt(lump[:-1]), 6)
    grad_energy_z = grad_energy_x / scale
    b_z = b_x / scale
    return {"energy": energy, "population": population, "grad_energy_x": grad_energy_x, "grad_energy_z": grad_energy_z, "b_x": b_x, "b_z": b_z, "grad_lagrangian_x": grad_lagrangian_x, "h": h.reshape(n, 2), "hcoef": hcoef.reshape(n, 2), "lcoef": lcoef.reshape(n, 2), "lump": lump, "q": q}


def csr_pattern(n: int) -> tuple[np.ndarray, np.ndarray, dict[tuple[int, int], int]]:
    d = 6 * n
    indices: list[int] = []
    indptr = [0]
    for row in range(d):
        node, comp = divmod(row, 6)
        cols = [6 * j + c for j in range(max(0, node - 1), min(n, node + 2)) for c in range(6)]
        indices.extend(cols)
        indptr.append(len(indices))
    idx = np.asarray(indices, dtype=np.int64)
    ip = np.asarray(indptr, dtype=np.int64)
    lookup = {(row, col): k for row in range(d) for k, col in enumerate(idx[ip[row] : ip[row + 1]], start=ip[row])}
    return ip, idx, lookup


def finite_difference_hessian(r: np.ndarray, y: np.ndarray, f: np.ndarray, epsilon: int, mu: float, base: dict[str, Any], step: float, ip: np.ndarray, idx: np.ndarray, lookup: dict[tuple[int, int], int]) -> tuple[sparse.csr_matrix, np.ndarray, dict[str, Any]]:
    n = r.size - 1
    x = np.column_stack((y[:-1], f[:-1])).reshape(-1)
    data = np.zeros(idx.size, dtype=np.float64)
    for component in range(6):
        for color in range(3):
            plus = x.copy()
            minus = x.copy()
            columns = np.arange(color, n, 3, dtype=np.int64) * 6 + component
            plus[columns] += step
            minus[columns] -= step
            yp = np.zeros_like(y); fp = np.zeros_like(f); yp[:-1] = plus.reshape(n, 6)[:, :5]; fp[:-1] = plus.reshape(n, 6)[:, 5]; yp[-1] = y[-1]; fp[-1] = f[-1]
            ym = np.zeros_like(y); fm = np.zeros_like(f); ym[:-1] = minus.reshape(n, 6)[:, :5]; fm[:-1] = minus.reshape(n, 6)[:, 5]; ym[-1] = y[-1]; fm[-1] = f[-1]
            gp = reconstruct(r, yp, fp, epsilon, mu, base["lump"])["grad_lagrangian_x"]
            gm = reconstruct(r, ym, fm, epsilon, mu, base["lump"])["grad_lagrangian_x"]
            delta = (gp - gm) / (2.0 * step)
            for col in columns:
                node = int(col // 6)
                for row_node in range(max(0, node - 1), min(n, node + 2)):
                    mass_row = base["lump"][row_node]
                    for row_comp in range(6):
                        row = 6 * row_node + row_comp
                        k = lookup[(row, int(col))]
                        data[k] = delta[row] / math.sqrt(mass_row * base["lump"][node])
    matrix = sparse.csr_matrix((data, idx, ip), shape=(6 * n, 6 * n))
    return matrix, base["b_z"], {"step": step, "symmetry_error": float(np.max(np.abs(matrix - matrix.T)) / max(1.0, float(np.max(np.abs(matrix.data))) if matrix.nnz else 1.0))}


def solve_response(matrix: sparse.csr_matrix, b: np.ndarray) -> tuple[np.ndarray, float, dict[str, float]]:
    d = matrix.shape[0]
    bordered = sparse.bmat([[matrix, -sparse.csr_matrix(b[:, None])], [sparse.csr_matrix(b[None, :]), None]], format="csr")
    rhs = np.zeros(d + 1, dtype=np.float64)
    rhs[-1] = 1.0
    sol = np.asarray(spsolve(bordered, rhs), dtype=np.float64)
    u, zeta = sol[:-1], float(sol[-1])
    eq = float(np.linalg.norm(matrix @ u - b * zeta) / max(1.0, float(np.linalg.norm(b * zeta))))
    constraint = abs(float(b @ u) - 1.0)
    curvature = abs(float(u @ (matrix @ u)) - zeta) / max(1.0, abs(zeta))
    return u, zeta, {"kkt_residual": eq, "constraint_residual": constraint, "curvature_residual": curvature}


def toy_controls() -> dict[str, Any]:
    rows = []
    for lam in (0.5, 1.0, 2.0):
        x, f = -3.0, math.sqrt(3.0)
        mu = x + lam * f * f
        H = np.array([[1.0, 2.0 * f], [2.0 * f, 2.0 * x + 6.0 * lam * f * f - 2.0 * mu]], dtype=np.float64)
        b = np.array([0.0, 2.0 * f], dtype=np.float64)
        bordered = np.block([[H, -b[:, None]], [b[None, :], np.zeros((1, 1))]])
        sol = np.linalg.solve(bordered, np.array([0.0, 0.0, 1.0]))
        expected = lam - 1.0
        error = abs(float(sol[-1]) - expected) / max(1.0, abs(expected))
        rows.append({"lambda": lam, "zeta": float(sol[-1]), "expected": expected, "normalized_error": error, "pass": bool(error < 1e-10)})
    return {"checks": rows, "pass": all(row["pass"] for row in rows)}


def primary_matrix(path: Path) -> tuple[sparse.csr_matrix, np.ndarray, dict[str, Any]]:
    with np.load(path, allow_pickle=False) as data:
        required = ("H_data", "H_indices", "H_indptr", "H_shape", "response", "gradient_energy", "b", "energy", "population", "mu_relative", "zeta")
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"primary response NPZ missing {missing}")
        shape = tuple(np.asarray(data["H_shape"], dtype=np.int64).tolist())
        matrix = sparse.csr_matrix((np.asarray(data["H_data"], dtype=np.float64), np.asarray(data["H_indices"], dtype=np.int64), np.asarray(data["H_indptr"], dtype=np.int64)), shape=shape)
        arrays = {key: np.asarray(data[key], dtype=np.float64) for key in ("response", "gradient_energy", "b")}
        scalars = {key: float(np.asarray(data[key]).reshape(-1)[0]) for key in ("energy", "population", "mu_relative", "zeta")}
    return matrix, arrays["response"], {**arrays, **scalars}

def verify_row(parent_row: dict[str, Any], response_row: dict[str, Any] | None, input_path: Path, response_path: Path, outdir: Path) -> dict[str, Any]:
    cap, epsilon, n, R, N = parent_row["cap"], int(parent_row["epsilon"]), int(parent_row["n"]), float(parent_row["R"]), int(parent_row["N"])
    out: dict[str, Any] = {"cap": cap, "epsilon": epsilon, "n": n, "R": R, "N": N, "input_npz": str(input_path.relative_to(ROOT)).replace("\\", "/"), "npz": response_path.name, "checks": [], "failures": [], "fd": [], "complete_physical_matter_formation": False}
    try:
        with np.load(input_path, allow_pickle=False) as data:
            for key in ("r", "y", "f"):
                check(out, f"input_{key}_present", key in data)
            if out["failures"]:
                return out
            r, y, f = (np.asarray(data[key], dtype=np.float64) for key in ("r", "y", "f"))
        check(out, "input_shapes", r.shape == (N + 1,) and y.shape == (N + 1, 5) and f.shape == (N + 1,), {"r": r.shape, "y": y.shape, "f": f.shape})
        check(out, "input_finite", np.all(np.isfinite(r)) and np.all(np.isfinite(y)) and np.all(np.isfinite(f)))
        check(out, "input_grid", array_relerr(r, np.linspace(0.0, R, N + 1), 1e-11) <= 0.0)
        check(out, "input_outer_carrier", abs(float(f[-1])) <= 1e-11, f[-1])
        if out["failures"]:
            return out
        mu = float(parent_row["mu_relative"])
        base = reconstruct(r, y, f, epsilon, mu)
        check(out, "base_finite", all(np.all(np.isfinite(base[key])) if isinstance(base[key], np.ndarray) else finite(base[key]) for key in ("energy", "population", "grad_energy_z", "b_z", "lump")))
        check(out, "positive_radial_connection_coefficient", np.all(np.isfinite(base["hcoef"])) and np.all(base["hcoef"] > 0.0), float(np.min(base["hcoef"])))
        check(out, "base_energy", relerr(base["energy"], float(parent_row["energy"]), 1.0) <= 1e-8, {"derived": base["energy"], "parent": parent_row["energy"]})
        check(out, "base_population", relerr(base["population"], float(parent_row["population"]), 1.0) <= 1e-8, {"derived": base["population"], "parent": parent_row["population"]})
        if response_row is None:
            raise ValueError("response summary row missing")
        check(out, "response_row_complete_flag", response_row.get("complete_physical_matter_formation") is False, response_row.get("complete_physical_matter_formation"))
        check(out, "response_row_exception_absent", response_row.get("exception") is None, response_row.get("exception"))
        check(out, "response_row_qualified", response_row.get("qualified") is True, response_row.get("qualified"))
        primary_matrix_data, primary_response, primary = primary_matrix(response_path)
        check(out, "response_row_identity", response_row.get("cap") == cap and int(response_row.get("epsilon", epsilon)) == epsilon and int(response_row.get("n", n)) == n and float(response_row.get("R", R)) == R and int(response_row.get("N", N)) == N, response_row)
        check(out, "response_row_zeta", relerr(float(primary["zeta"]), float(response_row.get("zeta")), 1e-8) <= 1e-8, {"npz": primary["zeta"], "summary": response_row.get("zeta")})
        check(out, "primary_matrix_shape", primary_matrix_data.shape == (6 * N, 6 * N), primary_matrix_data.shape)
        ge = np.asarray(primary["gradient_energy"], dtype=np.float64).reshape(-1)
        bb = np.asarray(primary["b"], dtype=np.float64).reshape(-1)
        check(out, "energy_gradient_match", array_relerr(base["grad_energy_z"], ge) < 1e-8, {"max_normalized_error": array_relerr(base["grad_energy_z"], ge)})
        check(out, "population_gradient_match", array_relerr(base["b_z"], bb) < 1e-8, {"max_normalized_error": array_relerr(base["b_z"], bb)})
        ip, idx, lookup = csr_pattern(N)
        primary_lookup = {(row, int(col)): float(primary_matrix_data.data[k]) for row in range(primary_matrix_data.shape[0]) for k, col in enumerate(primary_matrix_data.indices[primary_matrix_data.indptr[row] : primary_matrix_data.indptr[row + 1]], start=primary_matrix_data.indptr[row])}
        response_dir = outdir / "rows"
        response_dir.mkdir(parents=True, exist_ok=True)
        for index, step in enumerate(STEPS):
            matrix, b, fdmeta = finite_difference_hessian(r, y, f, epsilon, mu, base, step, ip, idx, lookup)
            ours = {(row, int(col)): float(matrix.data[k]) for row in range(matrix.shape[0]) for k, col in enumerate(matrix.indices[matrix.indptr[row] : matrix.indptr[row + 1]], start=matrix.indptr[row])}
            errors = []
            for key, value in primary_lookup.items():
                if key not in ours:
                    errors.append(math.inf)
                else:
                    errors.append(abs(ours[key] - value) / max(1.0, abs(value)))
            matrix_error = max(errors) if errors else math.inf
            response, zeta, residuals = solve_response(matrix, b)
            zeta_primary = float(primary["zeta"])
            zeta_error = relerr(zeta, zeta_primary, 1.0)
            fdmeta.update({"matrix_error": matrix_error, "zeta": zeta, "primary_zeta": zeta_primary, "zeta_error": zeta_error, **residuals, "pass": bool(matrix_error < 1e-6 and zeta_error < 1e-6 and residuals["kkt_residual"] < 1e-8 and residuals["constraint_residual"] < 1e-10 and residuals["curvature_residual"] < 1e-8)})
            out["fd"].append(fdmeta)
            if not fdmeta["pass"]:
                out["failures"].append(f"finite_difference_{index}")
            np.savez_compressed(response_dir / f"{response_path.stem}_fd{index}.npz", H_data=matrix.data, H_indices=matrix.indices, H_indptr=matrix.indptr, H_shape=np.asarray(matrix.shape, dtype=np.int64), response=response, b=b, step=np.asarray(step), zeta=np.asarray(zeta), matrix_error=np.asarray(matrix_error), zeta_error=np.asarray(zeta_error))
        out["derived"] = {"energy": base["energy"], "population": base["population"], "mu_relative": mu, "zeta": float(primary["zeta"]), "energy_gradient": base["grad_energy_z"], "population_gradient": base["b_z"]}
        out["pass"] = not out["failures"] and all(item["pass"] for item in out["fd"])
    except Exception as exc:
        check(out, "row_execution", False, f"{type(exc).__name__}: {exc}")
    return out


def compare_refinements(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    refinements, domains = [], []
    for cap in CAPS:
        for n in POPULATIONS:
            for R, coarse, fine in ((32.0, 256, 512), (64.0, 512, 1024)):
                pair = [x for x in rows if x.get("cap") == cap and x.get("n") == int(n) and x.get("R") == R and x.get("N") in (coarse, fine)]
                pair.sort(key=lambda x: x.get("N", 0))
                checks = []
                if len(pair) == 2 and all("derived" in x for x in pair):
                    for key in ("zeta",):
                        err = relerr(pair[0]["derived"][key], pair[1]["derived"][key], 1e-8)
                        checks.append({"quantity": key, "pass": err <= 0.02, "normalized_error": err})
                refinements.append({"cap": cap, "n": n, "R": R, "coarse_N": coarse, "fine_N": fine, "checks": checks, "pass": bool(checks) and all(x["pass"] for x in checks)})
            pair = [x for x in rows if x.get("cap") == cap and x.get("n") == int(n) and (x.get("R"), x.get("N")) in ((32.0, 512), (64.0, 1024))]
            pair.sort(key=lambda x: x.get("R", 0))
            checks = []
            if len(pair) == 2 and all("derived" in x for x in pair):
                err = relerr(pair[0]["derived"]["zeta"], pair[1]["derived"]["zeta"], 1e-8)
                checks.append({"quantity": "zeta", "pass": err <= 0.02, "normalized_error": err})
            domains.append({"cap": cap, "n": n, "checks": checks, "pass": bool(checks) and all(x["pass"] for x in checks)})
    return refinements, domains


def calculate(manifest_path: Path, input_dir: Path, output: Path) -> dict[str, Any]:
    manifest = verify_manifest(manifest_path)
    parent_summary, parent_verification = parent_acceptance()
    response_summary_path = input_dir / "summary.json"
    if not response_summary_path.exists():
        raise ValueError("primary response summary.json is missing")
    response_summary = strict_json(response_summary_path)
    if response_summary.get("schema") != "matter-formation-vortex-compressibility-v1" or response_summary.get("complete_physical_matter_formation") is not False or response_summary.get("numerical_pass") is not True:
        raise ValueError("primary response summary is not accepted or is marked complete")
    if not isinstance(response_summary.get("rows"), list) or len(response_summary["rows"]) != 24:
        raise ValueError("primary response summary must contain exactly 24 rows")
    response_rows = {(row.get("cap"), int(row.get("n", -1)), float(row.get("R", -1)), int(row.get("N", -1))): row for row in response_summary["rows"]}
    if set(response_rows) != {(cap, n, R, N) for cap, _, n, R, N in expected_rows()}:
        raise ValueError("primary response summary rows do not cover exact schedule")
    parent_rows = {(row.get("cap"), int(row.get("n", -1)), float(row.get("R", -1)), int(row.get("N", -1))): row for row in parent_summary["rows"]}
    manifest_inputs = {(item["cap"], int(item["n"]), float(item["R"]), int(item["N"])): item for item in manifest["inputs"]}
    for key, row in parent_rows.items():
        item = manifest_inputs.get(key)
        expected_path = f"runs/20260908_matter_formation_vortex_loaded/primary/{row.get('npz')}"
        if item is None or item.get("path") != expected_path or int(item.get("epsilon", 0)) != int(row.get("epsilon")):
            raise ValueError(f"manifest input does not match parent row {key}")
    rows = []
    for cap, epsilon, n, R, N in expected_rows():
        parent_row = parent_rows.get((cap, n, R, N))
        if parent_row is None:
            rows.append({"cap": cap, "epsilon": epsilon, "n": n, "R": R, "N": N, "checks": [], "failures": ["parent_row_missing"], "pass": False})
            continue
        source = ROOT / "runs/20260908_matter_formation_vortex_loaded/primary" / str(parent_row.get("npz"))
        response_path = input_dir / f"{Path(str(parent_row.get('npz'))).stem}_response.npz"
        response_row = response_rows.get((cap, n, R, N))
        rows.append(verify_row(parent_row, response_row, source, response_path, output))
    refinements, domains = compare_refinements(rows)
    toy = toy_controls()
    all_checks = all(row.get("pass", False) for row in rows) and all(item["pass"] for item in refinements) and all(item["pass"] for item in domains) and toy["pass"]
    finest = {(row.get("cap"), row.get("n"), row.get("R")): row.get("derived", {}).get("zeta") for row in rows if (row.get("R"), row.get("N")) in ((32.0, 512), (64.0, 1024))}
    negative = any(all(finite(finest.get((cap, 64, R))) and finest[(cap, 64, R)] < -1e-6 for R in (32.0, 64.0)) for cap in CAPS)
    positive = all(finite(finest.get((cap, 64, R))) and finest[(cap, 64, R)] > 1e-6 for cap in CAPS for R in (32.0, 64.0))
    verdict = "INCONCLUSIVE"
    if all_checks and negative:
        verdict = "CONTRADICTS-uniform loaded-line energetic stability"
    elif all_checks and positive:
        verdict = "SUPPORTS-positive loaded-line compressibility"
    failures = [f"{row.get('cap')}-n{row.get('n')}-R{row.get('R')}-N{row.get('N')}:{name}" for row in rows for name in row.get("failures", [])]
    failures.extend(f"refinement:{i}" for i, item in enumerate(refinements) if not item["pass"])
    failures.extend(f"domain:{i}" for i, item in enumerate(domains) if not item["pass"])
    if not toy["pass"]:
        failures.append("toy_controls")
    return {"schema": SCHEMA, "manifest": manifest, "rows": rows, "refinements": refinements, "domains": domains, "toy_controls": toy, "failures": failures, "numerical_pass": bool(all_checks), "verdict": verdict, "complete_physical_matter_formation": False, "controls": {"steps": list(STEPS), "lambda_C": LAMBDA_C, "parent_summary": PARENT_SUMMARY, "parent_verification": PARENT_VERIFICATION, "parent_summary_sha256": sha256(ROOT / PARENT_SUMMARY), "parent_verification_sha256": sha256(ROOT / PARENT_VERIFICATION)}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        args.output.resolve().mkdir(parents=True, exist_ok=False)
        result = calculate(args.manifest.resolve(), args.input.resolve(), args.output.resolve())
        with (args.output.resolve() / "verification.json").open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(jsonable(result), handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        print(json.dumps({"schema": result["schema"], "numerical_pass": result["numerical_pass"], "verdict": result["verdict"], "complete_physical_matter_formation": False}, sort_keys=True))
        return 0 if result["numerical_pass"] else 1
    except Exception as exc:
        print(json.dumps({"schema": SCHEMA, "numerical_pass": False, "verdict": "INCONCLUSIVE", "complete_physical_matter_formation": False, "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
