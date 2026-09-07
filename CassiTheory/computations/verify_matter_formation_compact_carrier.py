#!/usr/bin/env python3
"""Independently verify the compact-target carrier qualification receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp
from scipy.integrate import IntegrationWarning, quad
from scipy.interpolate import CubicHermiteSpline
from scipy.linalg import eigh_tridiagonal
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTE = ROOT / "computations" / "matter-formation-continuum-report.md"
PRIMARY_PATH = ROOT / "computations" / "matter_formation_compact_carrier.py"
FROZEN_HASH = "3fbb5a53a15dc9309e98c9ca08277522d96dc0aa61a534913fbc8c8f52fa8406"
BASE_HEADING = "### 18.2 Radial carrier qualification: pre-execution criteria\n"
BASE_HASH = "c13cdd8b8a3f6f704e0cb0a25f2412acdbd9f5ea7a4ad109babf4140eaca3a57"
SCHEMA = "matter-formation-compact-carrier-verification-v2"
EPSILON = 1.0e-5
RADII = (16.0, 32.0, 64.0)
SPACINGS = (0.04, 0.02)
VERDICT_SUPPORTS = "SUPPORTS—finite-domain stationary and radial energetic qualification of the declared compact-target carrier"
VERDICT_CONTRADICTS = "CONTRADICTS—radial energetic stability of the declared compact-target carrier"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"
EXACT_NAMES = ("degree", "trial_E2", "trial_E4", "trial_scale", "trial_bound_ratio", "euler_equation", "shifted_euler_equivalence")


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def source_identity(path: Path, canonical: bool = True) -> dict[str, str]:
    return {"path": repo_path(path), "sha256": canonical_sha256(path) if canonical else raw_sha256(path)}


def finite(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value))


def is_int(value: Any) -> bool:
    return isinstance(value, (int, np.integer)) and not isinstance(value, bool)


def close(a: Any, b: Any, tol: float = 1.0e-10) -> bool:
    return finite(a) and finite(b) and abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


def mismatch(rows: list[dict[str, Any]], field: str, expected: Any, actual: Any, reason: str = "mismatch") -> None:
    rows.append({"field": field, "expected": safe(expected), "actual": safe(actual), "reason": reason})


def safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [safe(v) for v in value]
    return value


def extract_protocol(note: Path, heading: str = "### 18.5 Shifted-angle precision calculation: pre-execution criteria\n") -> tuple[str, str]:
    text = canonical_bytes(note).decode("utf-8")
    if text.count(heading) != 1:
        raise ValueError("frozen section heading is not unique")
    start = text.index(heading)
    boundary = re.search(r"\n(?=#{1,3} )", text[start + len(heading) :])
    end = start + len(heading) + boundary.start() if boundary else len(text)
    section = text[start:end].rstrip() + "\n"
    return heading.rstrip(), section


def strict_json(path: Path) -> Any:
    def pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"duplicate JSON key: {key}")
            out[key] = value
        return out

    def constant(value: str) -> Any:
        raise ValueError(f"non-finite JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def beta_integral(power: int, denominator_power: int) -> sp.Expr:
    # Integral_0^infinity x^power/(1+x^2)^denominator_power dx.
    expression = sp.Rational(1, 2) * sp.beta(sp.Rational(power + 1, 2), sp.Rational(2 * denominator_power - power - 1, 2))
    return sp.simplify(sp.expand_func(expression.rewrite(sp.gamma)))


def exact_controls() -> list[dict[str, Any]]:
    r, scale, f, fp, fpp = sp.symbols("r R f fp fpp", positive=True)
    degree = sp.simplify(16 / sp.pi * beta_integral(2, 3))
    e2 = sp.simplify(12 * scale * beta_integral(2, 2))
    e4 = sp.simplify(48 / scale * beta_integral(2, 4))
    M = r**2 + 2 * sp.sin(f) ** 2
    V = 2 * sp.sin(f) ** 2 + sp.sin(f) ** 4 / r**2
    # This is the Euler residual of M(f')^2+V, independently of the stated ODE.
    total_derivative = 2 * (sp.diff(M, r) + sp.diff(M, f) * fp) * fp + 2 * M * fpp
    euler = sp.expand(total_derivative - (sp.diff(M, f) * fp**2 + sp.diff(V, f)))
    stated = 2 * (M * fpp + 2 * r * fp + sp.sin(2 * f) * (fp**2 - 1 - sp.sin(f) ** 2 / r**2))
    checks = [
        ("degree", sp.simplify(degree - 1) == 0, "beta-integral degree = 1"),
        ("trial_E2", sp.simplify(e2 - 3 * sp.pi * scale) == 0, "E2/(4*pi) = 3*pi*R"),
        ("trial_E4", sp.simplify(e4 - 3 * sp.pi / (2 * scale)) == 0, "E4/(4*pi) = 3*pi/(2*R)"),
        ("trial_scale", sp.solve(sp.diff(3 * sp.pi * scale + 3 * sp.pi / (2 * scale), scale), scale)[0] == sp.sqrt(2) / 2, "stationary R = 1/sqrt(2)"),
        ("trial_bound_ratio", sp.simplify(4 * sp.pi * (3 * sp.pi * scale + 3 * sp.pi / (2 * scale)).subs(scale, 1 / sp.sqrt(2)) / (12 * sp.pi**2) - sp.sqrt(2)) == 0, "minimum E/(12*pi^2) = sqrt(2)"),
        ("euler_equation", sp.simplify(euler - stated) == 0, "differentiated radial density equals stated Euler equation"),
        ("shifted_euler_equivalence", sp.trigsimp(stated.subs({f: sp.pi - f, fp: -fp, fpp: -fpp}, simultaneous=True) + stated) == 0, "physical and shifted Euler equations differ by an overall minus sign"),
    ]
    return [{"name": name, "pass": bool(ok), "evidence": evidence} for name, ok, evidence in checks]


def ode_rhs(r: np.ndarray | float, y0: np.ndarray | float, y1: np.ndarray | float) -> np.ndarray:
    rr = np.asarray(r, dtype=float)
    ff = np.asarray(y0, dtype=float)
    pp = np.asarray(y1, dtype=float)
    ss = np.sin(ff)
    denom = rr * rr + 2.0 * ss * ss
    fpp = (-2.0 * rr * pp - np.sin(2.0 * ff) * (pp * pp - 1.0 - ss * ss / (rr * rr))) / denom
    return np.stack((pp, fpp), axis=0)


def rms_reconstruction(x: np.ndarray, f: np.ndarray, fp: np.ndarray) -> np.ndarray:
    h = np.diff(x)
    rhs = ode_rhs(x, f, fp)
    y0 = CubicHermiteSpline(x, f, fp)
    y1 = CubicHermiteSpline(x, fp, rhs[1])
    middle = 0.5 * (np.vstack((f, fp))[:, 1:] + np.vstack((f, fp))[:, :-1]) - 0.125 * h * (rhs[:, 1:] - rhs[:, :-1])
    fm = ode_rhs(x[:-1] + 0.5 * h, middle[0], middle[1])
    col = np.vstack((f, fp))[:, 1:] - np.vstack((f, fp))[:, :-1] - h / 6.0 * (rhs[:, :-1] + rhs[:, 1:] + 4.0 * fm)
    rm = 1.5 * col / h
    xm = x[:-1] + 0.5 * h
    s = 0.5 * h * math.sqrt(3.0 / 7.0)
    x1, x2 = xm + s, xm - s
    Y1 = np.vstack((y0(x1), y1(x1)))
    Y2 = np.vstack((y0(x2), y1(x2)))
    Y1p = np.vstack((y0(x1, 1), y1(x1, 1)))
    Y2p = np.vstack((y0(x2, 1), y1(x2, 1)))
    r1 = Y1p - ode_rhs(x1, Y1[0], Y1[1])
    r2 = Y2p - ode_rhs(x2, Y2[0], Y2[1])
    rm = rm / (1.0 + np.abs(fm))
    r1 = r1 / (1.0 + np.abs(ode_rhs(x1, Y1[0], Y1[1])))
    r2 = r2 / (1.0 + np.abs(ode_rhs(x2, Y2[0], Y2[1])))
    nmid = np.sum(np.real(rm * np.conj(rm)), axis=0)
    n1 = np.sum(np.real(r1 * np.conj(r1)), axis=0)
    n2 = np.sum(np.real(r2 * np.conj(r2)), axis=0)
    return np.sqrt(0.5 * (32.0 / 45.0 * nmid + 49.0 / 90.0 * (n1 + n2)))


def physical_spline(x: np.ndarray, theta: np.ndarray, thetap: np.ndarray) -> CubicHermiteSpline:
    result = CubicHermiteSpline(x, theta, thetap)
    result.c = -result.c
    result.c[-1, :] += math.pi
    return result


def profile_measurements(x: np.ndarray, theta: np.ndarray, thetap: np.ndarray) -> dict[str, float]:
    spline = physical_spline(x, theta, thetap)
    b = -float(thetap[0])
    c = float(x[-1] ** 2 * (math.pi - theta[-1]))
    def e2_inner(r: float) -> float:
        ff = math.pi + b * r
        return r * r * b * b + 2.0 * math.sin(ff) ** 2
    def e4_inner(r: float) -> float:
        if r == 0.0:
            return 0.0
        ff = math.pi + b * r
        return 2.0 * math.sin(ff) ** 2 * b * b + math.sin(ff) ** 4 / (r * r)
    e2_core = quad(e2_inner, 0.0, float(x[0]), epsabs=1e-10, epsrel=1e-10, limit=100)[0]
    e4_core = quad(e4_inner, 0.0, float(x[0]), epsabs=1e-10, epsrel=1e-10, limit=100)[0]
    points = x[1:-1].tolist()
    e2_mid = quad(lambda rr: rr * rr * float(spline(rr, 1)) ** 2 + 2.0 * math.sin(float(spline(rr))) ** 2, float(x[0]), float(x[-1]), points=points, epsabs=1e-9, epsrel=1e-9, limit=max(100, len(x)))[0]
    e4_mid = quad(lambda rr: 2.0 * math.sin(float(spline(rr))) ** 2 * float(spline(rr, 1)) ** 2 + math.sin(float(spline(rr))) ** 4 / (rr * rr), float(x[0]), float(x[-1]), points=points, epsabs=1e-9, epsrel=1e-9, limit=max(100, len(x)))[0]
    invL = 1.0 / float(x[-1])
    e2_tail = quad(lambda z: 0.0 if z == 0.0 else 4.0 * c * c * z * z + 2.0 * math.sin(c * z * z) ** 2 / (z * z), 0.0, invL, epsabs=1e-10, epsrel=1e-10, limit=100)[0]
    e4_tail = quad(lambda z: 8.0 * c * c * z**4 * math.sin(c * z * z) ** 2 + math.sin(c * z * z) ** 4, 0.0, invL, epsabs=1e-10, epsrel=1e-10, limit=100)[0]
    e2 = 4.0 * math.pi * (e2_core + e2_mid + e2_tail)
    e4 = 4.0 * math.pi * (e4_core + e4_mid + e4_tail)
    q_core = quad(lambda rr: -(2.0 / math.pi) * b * math.sin(math.pi + b * rr) ** 2, 0.0, float(x[0]), epsabs=1e-10, epsrel=1e-10, limit=100)[0]
    q_mid = quad(lambda rr: -(2.0 / math.pi) * float(spline(rr, 1)) * math.sin(float(spline(rr))) ** 2, float(x[0]), float(x[-1]), points=points, epsabs=1e-9, epsrel=1e-9, limit=max(100, len(x)))[0]
    q_tail = quad(lambda z: (4.0 * c * z / math.pi) * math.sin(c * z * z) ** 2, 0.0, invL, epsabs=1e-10, epsrel=1e-10, limit=100)[0]
    uniform = np.linspace(float(x[0]), float(x[-1]), 10001)
    fu = np.asarray(spline(uniform), dtype=float)
    fpu = np.asarray(spline(uniform, 1), dtype=float)
    target = math.pi / 2.0
    signs = fu - target
    roots = np.flatnonzero(signs[:-1] * signs[1:] <= 0)
    if len(roots):
        j = int(roots[0])
        half = float(brentq(lambda rr: float(spline(rr)) - target, float(uniform[j]), float(uniform[j + 1]), xtol=1e-13, rtol=1e-14))
    else:
        raise ValueError("half-angle radius is not bracketed")
    degree = q_core + q_mid + q_tail
    return {
        "E2": e2, "E4": e4, "energy": e2 + e4, "normalized_energy": (e2 + e4) / (12.0 * math.pi * math.pi),
        "degree": degree, "origin_slope": b, "outer_value": float(math.pi - theta[-1]), "half_angle_radius": half,
        "virial_defect": abs(e2 - e4) / (e2 + e4), "profile_min": float(np.min(fu)), "profile_max": float(np.max(fu)),
        "derivative_max": float(np.max(fpu)), "rms_max_reconstructed": float(np.max(rms_reconstruction(x, theta, thetap))),
        "boundary_left": float(-theta[0] + x[0] * thetap[0]), "boundary_right": float(-thetap[-1] + 2.0 * (math.pi - theta[-1]) / x[-1]),
    }


def scalar_at(spline: CubicHermiteSpline, r: np.ndarray | float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ff = np.asarray(spline(r), dtype=float)
    fp = np.asarray(spline(r, 1), dtype=float)
    fpp = np.asarray(spline(r, 2), dtype=float)
    return ff, fp, fpp


def flux_operator(spline: CubicHermiteSpline, L: float, h_requested: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, np.ndarray]:
    n = int(math.ceil((L - EPSILON) / h_requested))
    dx = (L - EPSILON) / n
    nodes = EPSILON + dx * np.arange(n + 1, dtype=float)
    interior = nodes[1:-1]
    ff, fp, fpp = scalar_at(spline, interior)
    mass = interior**2 + 2.0 * np.sin(ff) ** 2
    Mff = 4.0 * np.cos(2.0 * ff)
    Mf = 4.0 * np.sin(ff) * np.cos(ff)
    Vff = 4.0 * np.cos(2.0 * ff) + 4.0 * np.sin(ff) ** 2 * (3.0 * np.cos(ff) ** 2 - np.sin(ff) ** 2) / interior**2
    W = 0.5 * Vff - 0.5 * Mff * fp**2 - Mf * fpp
    faces = EPSILON + dx * (np.arange(n, dtype=float) + 0.5)
    fface = np.asarray(spline(faces), dtype=float)
    Mface = faces**2 + 2.0 * np.sin(fface) ** 2
    upper = -Mface[1:-1] / dx**2
    diagonal = (Mface[:-1] + Mface[1:]) / dx**2 + W
    values, vectors = eigh_tridiagonal(diagonal / mass, upper / np.sqrt(mass[:-1] * mass[1:]), select="i", select_range=(0, 0))
    return nodes, mass, diagonal, float(values[0]), np.asarray(vectors[:, 0], dtype=float)


def primary_flux_residual(spline: CubicHermiteSpline, nodes: np.ndarray, eta: np.ndarray, eigenvalue: float) -> tuple[float, float, np.ndarray]:
    dx = float(nodes[1] - nodes[0])
    interior = nodes[1:-1]
    ff, fp, fpp = scalar_at(spline, interior)
    mass = interior**2 + 2.0 * np.sin(ff) ** 2
    Mff = 4.0 * np.cos(2.0 * ff)
    Mf = 4.0 * np.sin(ff) * np.cos(ff)
    Vff = 4.0 * np.cos(2.0 * ff) + 4.0 * np.sin(ff) ** 2 * (3.0 * np.cos(ff) ** 2 - np.sin(ff) ** 2) / interior**2
    W = 0.5 * Vff - 0.5 * Mff * fp**2 - Mf * fpp
    faces = 0.5 * (nodes[:-1] + nodes[1:])
    fface = np.asarray(spline(faces), dtype=float)
    Mfce = faces**2 + 2.0 * np.sin(fface) ** 2
    upper = -Mfce[1:-1] / dx**2
    diagonal = (Mfce[:-1] + Mfce[1:]) / dx**2 + W
    Hv = diagonal * eta[1:-1]
    if len(eta) > 3:
        Hv[:-1] += upper * eta[2:-1]
        Hv[1:] += upper * eta[1:-2]
    Mv = mass * eta[1:-1]
    residual = float(np.linalg.norm(Hv - eigenvalue * Mv) / (np.linalg.norm(Hv) + abs(eigenvalue) * np.linalg.norm(Mv) + 1e-30))
    return residual, float(np.min(mass)), np.asarray(mass)


def fe_operator(spline: CubicHermiteSpline, L: float, h_requested: float) -> tuple[float, float, np.ndarray]:
    n = int(math.ceil((L - EPSILON) / h_requested))
    dx = (L - EPSILON) / n
    nodes = EPSILON + dx * np.arange(n + 1, dtype=float)
    diag = np.zeros(n + 1, dtype=float)
    upper_full = np.zeros(n, dtype=float)
    lumped = np.zeros(n + 1, dtype=float)
    gauss = np.array([-math.sqrt(3.0 / 5.0), 0.0, math.sqrt(3.0 / 5.0)])
    weights = np.array([5.0 / 9.0, 8.0 / 9.0, 5.0 / 9.0])
    for cell in range(n):
        left, right = nodes[cell], nodes[cell + 1]
        rr = 0.5 * (left + right) + 0.5 * dx * gauss
        ff, fp, _ = scalar_at(spline, rr)
        ss, cc = np.sin(ff), np.cos(ff)
        M = rr**2 + 2.0 * ss**2
        Mf = 4.0 * ss * cc
        Mff = 4.0 * np.cos(2.0 * ff)
        Vff = 4.0 * np.cos(2.0 * ff) + 4.0 * ss**2 * (3.0 * cc**2 - ss**2) / rr**2
        potential = 0.5 * (Mff * fp**2 + Vff)
        N0, N1 = (1.0 - gauss) / 2.0, (1.0 + gauss) / 2.0
        d0, d1 = -np.ones(3) / dx, np.ones(3) / dx
        w = 0.5 * dx * weights
        k00 = np.sum(w * (M * d0 * d0 + Mf * fp * (N0 * d0 + d0 * N0) + potential * N0 * N0))
        k01 = np.sum(w * (M * d0 * d1 + Mf * fp * (N0 * d1 + d0 * N1) + potential * N0 * N1))
        k11 = np.sum(w * (M * d1 * d1 + Mf * fp * (N1 * d1 + d1 * N1) + potential * N1 * N1))
        diag[cell] += k00
        diag[cell + 1] += k11
        upper_full[cell] += k01
        lumped[cell] += float(np.sum(w * M * N0))
        lumped[cell + 1] += float(np.sum(w * M * N1))
    d = diag[1:-1]
    u = upper_full[1:-1]
    m = lumped[1:-1]
    if np.any(m <= 0) or not np.all(np.isfinite(m)):
        raise ValueError("non-positive FE lumped mass")
    transformed_d = d / m
    transformed_u = u / np.sqrt(m[:-1] * m[1:])
    vals, vecs = eigh_tridiagonal(transformed_d, transformed_u, select="i", select_range=(0, 0))
    lam = float(vals[0])
    z = np.asarray(vecs[:, 0], dtype=float)
    v = z / np.sqrt(m)
    kv = d * v
    if len(v) > 1:
        kv[:-1] += u * v[1:]
        kv[1:] += u * v[:-1]
    residual = float(np.linalg.norm(kv - lam * m * v) / (np.linalg.norm(kv) + abs(lam) * np.linalg.norm(m * v) + 1e-30))
    return lam, residual, v


def add_check(result: dict[str, Any], name: str, category: str, passed: bool, evidence: str) -> None:
    row = {"name": name, "category": category, "pass": bool(passed), "evidence": evidence}
    result["checks"].append(row)
    if not passed:
        result["failures"].append(name)


def safe_input(root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("artifact path is not a relative string")
    path = (root / Path(relative)).resolve()
    path.relative_to(root.resolve())
    return path


def array_float64(loaded: Any, key: str, ndim: int | None = None) -> np.ndarray:
    if key not in loaded:
        raise ValueError(f"missing NPZ array {key}")
    arr = np.asarray(loaded[key])
    if arr.dtype != np.dtype("float64") or (ndim is not None and arr.ndim != ndim) or not np.all(np.isfinite(arr)):
        raise ValueError(f"invalid float64 finite array {key}")
    return arr


def compare_field(result: dict[str, Any], name: str, expected: Any, actual: Any, tol: float = 1e-7) -> None:
    ok = close(expected, actual, tol)
    add_check(result, f"measurement_{name}", "qualification", ok, f"expected={safe(expected)!r}, reconstructed={safe(actual)!r}")


def validate_primary_shape(primary: Any, result: dict[str, Any]) -> None:
    if not isinstance(primary, dict):
        raise ValueError("primary receipt is not an object")
    required = {"schema", "identities", "exact", "profiles", "spectra", "checks", "failures", "numerical_pass", "verdict"}
    if not required.issubset(primary):
        raise ValueError("primary receipt is missing required fields")
    if primary["schema"] != "matter-formation-compact-carrier-v2":
        raise ValueError("primary schema mismatch")
    for key in ("numerical_pass",):
        if not isinstance(primary[key], bool):
            raise ValueError(f"primary {key} is not bool")
    if not isinstance(primary["identities"], dict) or not isinstance(primary["checks"], list) or not isinstance(primary["failures"], list):
        raise ValueError("primary receipt container schema mismatch")
    if not isinstance(primary["verdict"], str):
        raise ValueError("primary verdict is not string")
    if not isinstance(primary["exact"], list) or not isinstance(primary["profiles"], list) or not isinstance(primary["spectra"], list):
        raise ValueError("primary row containers are not lists")
    for row in primary["exact"] + primary["profiles"] + primary["spectra"]:
        if not isinstance(row, dict):
            raise ValueError("primary row is not object")
    for row in primary["checks"]:
        if not isinstance(row, dict) or set(row) != {"name", "category", "pass", "evidence"} or not isinstance(row["name"], str) or row["category"] not in {"qualification", "stability"} or not isinstance(row["pass"], bool) or not isinstance(row["evidence"], str):
            raise ValueError("primary check row schema mismatch")
    if not all(isinstance(item, str) for item in primary["failures"]):
        raise ValueError("primary failure row schema mismatch")


def conditioning_evidence(result: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    direct_path = ROOT / "runs/20260906_matter_formation_compact_carrier/results.json"
    reference_path = ROOT / "runs/20260906_matter_formation_compact_carrier_verification/results.json"
    direct_hash = raw_sha256(direct_path)
    reference_hash = raw_sha256(reference_path)
    if direct_hash != "91fb84409803a2a9574bbf01a733eabf30b730c8ca47ecaab78d76a77277e646" or reference_hash != "32e0d0487b6916e00e2ac5f2d6986c81deb2be012945ccca7b2b91e4ecfb4d49":
        raise ValueError("direct-angle conditioning receipts are missing or altered")
    direct, reference = strict_json(direct_path), strict_json(reference_path)
    for path in (direct_path, reference_path):
        result["artifact_identities"].append({"root": "repository", "path": repo_path(path), "sha256": raw_sha256(path)})
    locations = []
    for row in direct["profiles"]:
        path = safe_input(direct_path.parent, row["artifact"]["path"])
        if raw_sha256(path) != row["artifact"]["sha256"]:
            raise ValueError("direct-angle conditioning profile hash mismatch")
        with np.load(path, allow_pickle=False) as raw:
            x = array_float64(raw, "x", 1)
            rms = array_float64(raw, "rms_residuals", 1)
        index = int(np.argmax(rms))
        locations.append({"L": row["L"], "artifact": row["artifact"], "peak_interval": index,
                          "peak_midpoint": float(0.5 * (x[index] + x[index + 1]))})
        result["artifact_identities"].append({"root": "repository", "path": repo_path(path), "sha256": row["artifact"]["sha256"]})
    return {"primary_sha256": direct_hash, "reference_sha256": reference_hash, "profiles": locations}, reference["profiles"]


def main() -> int:
    warnings.simplefilter("error", IntegrationWarning)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note", type=Path, default=DEFAULT_NOTE)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir
    result: dict[str, Any] = {
        "schema": SCHEMA, "identities": {}, "primary_identity": {}, "artifact_identities": [],
        "exact": [], "profiles": [], "spectra": [], "checks": [], "failures": [],
        "numerical_pass": False, "verdict": VERDICT_INCONCLUSIVE,
    }
    try:
        output.mkdir(parents=True, exist_ok=False)
    except Exception as exc:
        parser.error(f"refusing non-fresh output directory: {exc}")
    try:
        result["identities"]["program"] = source_identity(Path(__file__))
        result["identities"]["primary_program"] = source_identity(PRIMARY_PATH)
        heading, protocol = extract_protocol(args.note)
        protocol_hash = hashlib.sha256(protocol.encode("utf-8")).hexdigest()
        result["identities"]["protocol"] = {"path": repo_path(args.note), "heading": heading, "sha256": protocol_hash}
        if protocol_hash != FROZEN_HASH:
            raise ValueError(f"frozen protocol hash mismatch: {protocol_hash}")
        base_heading, base_section = extract_protocol(args.note, BASE_HEADING)
        base_hash = hashlib.sha256(base_section.encode("utf-8")).hexdigest()
        if base_hash != BASE_HASH:
            raise ValueError("baseline protocol hash mismatch")
        result["identities"]["baseline_protocol"] = {"heading": base_heading, "sha256": base_hash}
        with (output / "protocol.txt").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(protocol)
        protocol_file = args.input_dir / "protocol.txt"
        if not protocol_file.is_file() or canonical_bytes(protocol_file).decode("utf-8") != protocol:
            raise ValueError("primary protocol.txt is missing or altered")
        result["artifact_identities"].append({"path": "protocol.txt", "sha256": raw_sha256(protocol_file)})
        primary_file = args.input_dir / "results.json"
        if not primary_file.is_file():
            raise ValueError("primary results.json is missing")
        result["primary_identity"] = {"path": "results.json", "sha256": raw_sha256(primary_file)}
        result["artifact_identities"].append(dict(result["primary_identity"]))
        primary = strict_json(primary_file)
        validate_primary_shape(primary, result)
        identities = primary["identities"]
        pprogram = identities.get("program") if isinstance(identities, dict) else None
        pprotocol = identities.get("protocol") if isinstance(identities, dict) else None
        if not isinstance(pprogram, dict) or pprogram.get("path") != repo_path(PRIMARY_PATH) or pprogram.get("sha256") != canonical_sha256(PRIMARY_PATH):
            raise ValueError("primary program identity mismatch")
        if not isinstance(pprotocol, dict) or pprotocol.get("path") != repo_path(args.note) or pprotocol.get("heading") != heading or pprotocol.get("sha256") != FROZEN_HASH:
            raise ValueError("primary protocol identity mismatch")
        if identities.get("baseline_protocol") != result["identities"]["baseline_protocol"]:
            raise ValueError("primary baseline identity mismatch")
        conditioning, reference_profiles = conditioning_evidence(result)
        result["identities"]["conditioning"] = conditioning
        if identities.get("conditioning") != conditioning:
            raise ValueError("primary conditioning diagnostic mismatch")
        result["exact"] = exact_controls()
        for expected, stored in zip(result["exact"], primary["exact"]):
            if set(stored) != {"name", "pass", "evidence"}:
                raise ValueError("primary exact row schema mismatch")
            if not isinstance(stored.get("pass"), bool) or not isinstance(stored.get("evidence"), str):
                raise ValueError("primary exact row field type mismatch")
        if len(primary["exact"]) != len(EXACT_NAMES) or [r.get("name") for r in primary["exact"]] != list(EXACT_NAMES):
            raise ValueError("primary exact row count/order mismatch")
        for expected, stored in zip(result["exact"], primary["exact"]):
            if stored["name"] != expected["name"]:
                raise ValueError("primary exact row name mismatch")
            add_check(result, f"exact_{expected['name']}", "qualification", bool(stored["pass"]) and expected["pass"], f"independent={expected['pass']}, primary_pass={stored['pass']}")
        if len(primary["profiles"]) != 3 or [r.get("label") for r in primary["profiles"]] != ["L16", "L32", "L64"]:
            raise ValueError("primary profile row count/order/labels mismatch")
        if len(primary["spectra"]) != 6:
            raise ValueError("primary spectrum row count mismatch")
        expected_spectrum_labels = [f"L{int(L)}_h{h:.2f}" for L in RADII for h in SPACINGS]
        if [r.get("label") for r in primary["spectra"]] != expected_spectrum_labels:
            raise ValueError("primary spectrum labels mismatch")
        profile_required = {"label", "L", "epsilon", "artifact", "solver_status", "solver_message", "node_count", "rms_max", "boundary_residuals", "profile_min", "profile_max", "derivative_max", "E2", "E4", "energy", "normalized_energy", "degree", "origin_slope", "outer_value", "half_angle_radius", "virial_defect"}
        profile_data: dict[float, tuple[Any, ...]] = {}
        for row in primary["profiles"]:
            if set(row) != profile_required:
                raise ValueError("primary profile row schema mismatch")
            if not finite(row["L"]) or not finite(row["epsilon"]):
                raise ValueError("primary profile numeric identity type mismatch")
            L = float(row["L"])
            label = f"L{int(L)}"
            if row["label"] != label or L not in RADII or row["epsilon"] != EPSILON or not isinstance(row["solver_message"], str) or not is_int(row["solver_status"]) or not is_int(row["node_count"]):
                raise ValueError(f"profile {label} identity/type mismatch")
            boundaries = row["boundary_residuals"]
            if not isinstance(boundaries, list) or len(boundaries) != 2 or not all(finite(v) for v in boundaries):
                raise ValueError(f"profile {label} boundary schema mismatch")
            artifact = row["artifact"]
            if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str) or not isinstance(artifact.get("sha256"), str):
                raise ValueError(f"profile {label} artifact identity mismatch")
            expected_name = f"profile_L{int(L)}.npz"
            if artifact["path"] != expected_name:
                raise ValueError(f"profile {label} artifact path mismatch")
            path = safe_input(args.input_dir, artifact["path"])
            if raw_sha256(path) != artifact["sha256"]:
                raise ValueError(f"profile {label} artifact hash mismatch")
            result["artifact_identities"].append({"path": artifact["path"], "sha256": artifact["sha256"]})
            with np.load(path, allow_pickle=False) as loaded:
                x = array_float64(loaded, "x", 1)
                theta = array_float64(loaded, "theta", 1)
                thetap = array_float64(loaded, "thetap", 1)
                rms = array_float64(loaded, "rms_residuals", 1)
            if len(x) < 601 or len(theta) != len(x) or len(thetap) != len(x) or len(rms) != len(x) - 1 or np.any(np.diff(x) <= 0) or not close(x[0], EPSILON, 1e-9) or not close(x[-1], L, 1e-9):
                raise ValueError(f"profile {label} array shape/endpoint schema mismatch")
            reconstructed_rms = rms_reconstruction(x, theta, thetap)
            measured = profile_measurements(x, theta, thetap)
            if not all(finite(value) for value in measured.values()):
                raise ValueError(f"profile {label} nonfinite reconstructed measurement")
            profile_data[L] = (row, x, theta, thetap, measured, physical_spline(x, theta, thetap))
            rms_error = float(np.max(np.abs(rms - reconstructed_rms)))
            add_check(result, f"profile_{label}_provenance", "qualification", int(row["node_count"]) == len(x) and isinstance(row["solver_message"], str), f"node_count={row['node_count']}, raw_nodes={len(x)}")
            add_check(result, f"profile_{label}.rms_array", "qualification", rms_error <= 1e-10, f"max absolute RMS-array difference={rms_error}")
            reconstructed = {key: row[key] for key in ("label", "L", "epsilon", "artifact", "solver_status", "solver_message", "node_count")}
            reconstructed.update({key: measured[key] for key in ("profile_min", "profile_max", "derivative_max", "E2", "E4", "energy", "normalized_energy", "degree", "origin_slope", "outer_value", "half_angle_radius", "virial_defect")})
            reconstructed["rms_max"] = measured["rms_max_reconstructed"]
            reconstructed["boundary_residuals"] = [measured["boundary_left"], measured["boundary_right"]]
            result["profiles"].append(reconstructed)
            for field in ("profile_min", "profile_max", "derivative_max", "E2", "E4", "energy", "normalized_energy", "degree", "origin_slope", "outer_value", "half_angle_radius", "virial_defect"):
                if not finite(row[field]):
                    raise ValueError(f"profile {label} stored {field} is nonfinite")
                compare_field(result, f"{label}.{field}", row[field], measured[field])
            compare_field(result, f"{label}.rms_max", row["rms_max"], measured["rms_max_reconstructed"], 1e-10)
            compare_field(result, f"{label}.boundary_left", row["boundary_residuals"][0], measured["boundary_left"], 1e-10)
            compare_field(result, f"{label}.boundary_right", row["boundary_residuals"][1], measured["boundary_right"], 1e-10)
            add_check(result, f"profile_{label}_qualification", "qualification", int(row["solver_status"]) == 0 and measured["rms_max_reconstructed"] <= 1.1e-8 and abs(measured["boundary_left"]) <= 1e-9 and abs(measured["boundary_right"]) <= 1e-9 and measured["profile_min"] >= -1e-8 and measured["profile_max"] <= math.pi + 1e-8 and measured["derivative_max"] <= 1e-8 and abs(measured["degree"] - 1.0) <= 1e-7 and 1.0 <= measured["normalized_energy"] <= math.sqrt(2.0) + 1e-7 and measured["virial_defect"] <= 1e-4, f"status={row['solver_status']}, rms={measured['rms_max_reconstructed']}, boundary=({measured['boundary_left']},{measured['boundary_right']})")
            reference = next(item for item in reference_profiles if item["L"] == L)
            for field in ("energy", "origin_slope", "half_angle_radius"):
                add_check(result, f"{label}_same_branch_{field}", "qualification",
                          close(measured[field], reference[field], 1e-6),
                          f"shifted={measured[field]}, direct-angle={reference[field]}")
        if set(profile_data) != set(RADII):
            raise ValueError("missing profile data")
        for L in RADII:
            row, x, theta, thetap, measured, spline = profile_data[L]
            for field in ("E2", "E4", "degree", "origin_slope", "half_angle_radius"):
                compare_field(result, f"{L:g}.independent_{field}", row[field], measured[field])
        p32, p64 = profile_data[32.0][4], profile_data[64.0][4]
        add_check(result, "profile_refinement", "stability", all(abs(p32[k] - p64[k]) <= 1e-4 * max(abs(p32[k]), abs(p64[k]), 1.0) for k in ("energy", "origin_slope", "half_angle_radius")), "L32/L64 energy, slope, radius refinement")
        spectrum_data: dict[tuple[float, float], dict[str, float]] = {}
        for row in primary["spectra"]:
            if set(row) != {"label", "L", "h", "cells", "artifact", "eigenvalue", "residual"}:
                raise ValueError("primary spectrum row schema mismatch")
            if not finite(row["L"]) or not finite(row["h"]):
                raise ValueError("primary spectrum numeric identity type mismatch")
            L, h = float(row["L"]), float(row["h"])
            label = f"L{int(L)}_h{h:.2f}"
            if row["label"] != label or L not in RADII or h not in SPACINGS or not is_int(row["cells"]):
                raise ValueError(f"spectrum {label} identity/type mismatch")
            if not finite(row.get("eigenvalue")) or not finite(row.get("residual")):
                raise ValueError(f"spectrum {label} nonfinite stored measurement")
            artifact = row.get("artifact")
            if not isinstance(artifact, dict) or artifact.get("path") != f"spectrum_L{int(L)}_h{h:.2f}.npz" or not isinstance(artifact.get("sha256"), str):
                raise ValueError(f"spectrum {label} artifact identity mismatch")
            path = safe_input(args.input_dir, artifact["path"])
            if raw_sha256(path) != artifact["sha256"]:
                raise ValueError(f"spectrum {label} artifact hash mismatch")
            result["artifact_identities"].append({"path": artifact["path"], "sha256": artifact["sha256"]})
            with np.load(path, allow_pickle=False) as loaded:
                nodes = array_float64(loaded, "x", 1)
                eta = array_float64(loaded, "eta", 1)
            expected_cells = int(math.ceil((L - EPSILON) / h))
            if int(row["cells"]) != expected_cells or len(nodes) != expected_cells + 1 or len(eta) != len(nodes) or not close(nodes[0], EPSILON, 1e-9) or not close(nodes[-1], L, 1e-9) or not np.allclose(np.diff(nodes), (L - EPSILON) / expected_cells, rtol=1e-10, atol=1e-12) or abs(eta[0]) > 1e-12 or abs(eta[-1]) > 1e-12:
                raise ValueError(f"spectrum {label} grid/vector schema mismatch")
            spline = profile_data[L][5]
            _, mass0, _, eig, z0 = flux_operator(spline, L, h)
            residual, minmass, _ = primary_flux_residual(spline, nodes, eta, float(row["eigenvalue"]))
            compare_field(result, f"{label}.eigenvalue", row["eigenvalue"], eig, 1e-8)
            compare_field(result, f"{label}.residual", row["residual"], residual, 1e-10)
            # eigh_tridiagonal independently identifies index zero; the stored vector must align with it.
            v0 = z0 / np.sqrt(mass0)
            corr = abs(float(np.dot(eta[1:-1], v0) / (np.linalg.norm(eta[1:-1]) * np.linalg.norm(v0)))) if np.linalg.norm(eta[1:-1]) and np.linalg.norm(v0) else 0.0
            add_check(result, f"{label}_lowest_mode", "qualification", corr >= 1.0 - 1e-6 and residual <= 1e-8 and minmass > 0, f"index0 correlation={corr}, residual={residual}")
            fe_lam, fe_res, _ = fe_operator(spline, L, h)
            add_check(result, f"{label}_independent_mode", "qualification", fe_res <= 1e-8 and finite(fe_lam), f"independent FE eigenvalue={fe_lam}, residual={fe_res}")
            spectrum_data[(L, h)] = {"primary": eig, "primary_residual": residual, "independent": fe_lam, "independent_residual": fe_res}
            result["spectra"].append({
                **{key: row[key] for key in ("label", "L", "h", "cells", "artifact")},
                "eigenvalue": fe_lam, "residual": fe_res,
                "primary_eigenvalue": eig, "primary_residual": residual,
            })
        for L in RADII:
            coarse, fine = spectrum_data[(L, 0.04)], spectrum_data[(L, 0.02)]
            scale = lambda v: 5e-3 * max(1.0, abs(v))
            add_check(result, f"{int(L)}_primary_refinement", "stability", abs(coarse["primary"] - fine["primary"]) <= scale(fine["primary"]), "primary flux coarse/fine eigenvalue")
            add_check(result, f"{int(L)}_independent_refinement", "stability", abs(coarse["independent"] - fine["independent"]) <= scale(fine["independent"]), "independent FE coarse/fine eigenvalue")
            add_check(result, f"{int(L)}_cross_discretization", "stability", abs(fine["primary"] - fine["independent"]) <= scale(fine["primary"]), "fine primary/independent eigenvalue")
        all_eigs = [v[key] for v in spectrum_data.values() for key in ("primary", "independent")]
        add_check(result, "all_twelve_nonnegative_spectra", "stability", len(all_eigs) == 12 and all(v >= -1e-6 for v in all_eigs), f"minimum eigenvalue={min(all_eigs) if all_eigs else None}")
        if all(item["pass"] for item in result["checks"]):
            primary_consistent = (
                primary["numerical_pass"] is True and not primary["failures"]
                and primary["verdict"] == "SUPPORTS—primary finite-domain radial compact-target calculation"
                and bool(primary["checks"]) and all(item["pass"] for item in primary["checks"])
            )
            add_check(result, "primary_aggregate_agreement", "qualification", primary_consistent,
                      "independently qualified data must agree with primary aggregate fields")
        qualification = all(item["pass"] for item in result["checks"] if item["category"] == "qualification")
        stability = all(item["pass"] for item in result["checks"] if item["category"] == "stability")
        stability_without_sign = all(item["pass"] for item in result["checks"] if item["category"] == "stability" and item["name"] != "all_twelve_nonnegative_spectra")
        negative_qualified = qualification and stability_without_sign and any(v < -1e-6 for v in all_eigs)
        if qualification and stability and not negative_qualified:
            result["numerical_pass"] = True
            result["verdict"] = VERDICT_SUPPORTS
        elif negative_qualified:
            result["verdict"] = VERDICT_CONTRADICTS
        else:
            result["verdict"] = VERDICT_INCONCLUSIVE
    except Exception as exc:
        result["failures"].append(f"{type(exc).__name__}: {exc}")
        result["numerical_pass"] = False
        result["verdict"] = VERDICT_INCONCLUSIVE
    result["failures"] = list(dict.fromkeys(str(item) for item in result["failures"]))
    text = json.dumps(safe(result), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    with (output / "results.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    print(json.dumps({"verdict": result["verdict"], "failures": result["failures"],
                      "profiles": len(result["profiles"]), "spectra": len(result["spectra"])},
                     ensure_ascii=False, allow_nan=False))
    return 0 if result["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
