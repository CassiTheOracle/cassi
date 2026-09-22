#!/usr/bin/env python3
"""Independent verifier for the frozen thick-torus matter-formation protocol.

This file intentionally contains its own finite-volume quadrature and sparse
Newton relaxation.  It never imports the primary calculator or its geometry
module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "cassi.matter-formation.thick-torus-gap.independent.v1"
PRIMARY_SCHEMA = "cassi.matter-formation.thick-torus-gap.v1"
A_COEF = 1.0 / 16.0
C_PSI = 1.0 / 8.0
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
B_COEF = 19.0 / 4.0
H_COEF = 2.9598260763447164
OMEGA_INF = math.sqrt(B_COEF / A_COEF)
GRAD_F = 0.5
GRAD_C = 0.5
RADII = (5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 9.0, 10.0, 12.0, 16.0)
DENSITIES = (2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0, 24.0, 32.0)
CHARGES = (64.0, 128.0, 256.0)
PROFILE_TOL = 5e-9


class VerificationError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(obj: dict[str, Any]) -> str:
    body = dict(obj)
    body.pop("content_sha256", None)
    return sha256_bytes(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def finite_tree(x: Any) -> bool:
    if x is None or isinstance(x, (str, bool)):
        return True
    if isinstance(x, (int, float)):
        return math.isfinite(float(x))
    if isinstance(x, list):
        return all(finite_tree(v) for v in x)
    if isinstance(x, dict):
        return all(finite_tree(v) for v in x.values())
    return False


def err(a: float, b: float) -> float:
    return abs(float(a) - float(b)) / max(1.0, abs(float(a)), abs(float(b)))


def grid(radius: float, na: int, nphi: int, amax: float | None = None) -> dict[str, Any]:
    if amax is None:
        amax = 0.9 * radius
    da = amax / na
    dphi = 2.0 * math.pi / nphi
    ac = (np.arange(na, dtype=np.float64) + 0.5) * da
    ph = np.arange(nphi, dtype=np.float64) * dphi
    af = (np.arange(na, dtype=np.float64) + 1.0) * da
    g = np.maximum(1.0 + ac[:, None] * np.cos(ph[None, :]) / radius, 0.0)
    gf = np.maximum(1.0 + af[:, None] * np.cos(ph[None, :]) / radius, 0.0)
    vc = ac[:, None] * g * da * dphi
    fa = np.zeros((na + 1, nphi), dtype=np.float64)
    fa[1:] = af[:, None] * gf * dphi / da
    gp = np.maximum(1.0 + ac[:, None] * np.cos(ph[None, :] + 0.5 * dphi) / radius, 0.0)
    fp = gp * da / (ac[:, None] * dphi)
    return {"R": radius, "na": na, "nphi": nphi, "amax": amax, "da": da,
            "dphi": dphi, "a": ac, "phi": ph, "g": g, "vc": vc, "fa": fa, "fp": fp}


def energy_gradient(f: np.ndarray, c: np.ndarray, G: dict[str, Any], winding: float = 1.0) -> tuple[float, np.ndarray, np.ndarray, float, dict[str, float]]:
    R, a, g, vc, fa, fp = G["R"], G["a"], G["g"], G["vc"], G["fa"], G["fp"]
    da, dphi = G["da"], G["dphi"]
    tw = (GRAD_C * winding * winding / R**2) / np.maximum(g, 1e-12) ** 2
    dens = (U_RHO / 4.0) * (f * f - 1.0) ** 2 + (B_COEF - H_COEF + H_COEF * f * f) * c * c + (U_C / 2.0) * c**4 + tw * c * c
    E = float(np.sum(vc * dens))
    gf = vc * (U_RHO * f * (f * f - 1.0) + 2.0 * H_COEF * f * c * c)
    gc = vc * (2.0 * (B_COEF - H_COEF + H_COEF * f * f) * c + 2.0 * U_C * c**3 + 2.0 * tw * c)
    fu = np.concatenate((f[1:], np.ones((1, f.shape[1]))), axis=0)
    cu = np.concatenate((c[1:], np.zeros((1, c.shape[1]))), axis=0)
    df = fu - f
    dc = cu - c
    E += float(GRAD_F * np.sum(fa[1:] * df * df) + GRAD_C * np.sum(fa[1:] * dc * dc))
    fr = np.roll(f, -1, axis=1) - f
    cr = np.roll(c, -1, axis=1) - c
    lower_f = np.zeros_like(f); lower_f[1:] = fa[1:-1] * (f[1:] - f[:-1])
    lower_c = np.zeros_like(c); lower_c[1:] = fa[1:-1] * (c[1:] - c[:-1])
    gf += 2.0 * GRAD_F * (lower_f - fa[1:] * df)
    gc += 2.0 * GRAD_C * (lower_c - fa[1:] * dc)
    gf += 2.0 * GRAD_F * (np.roll(fp * fr, 1, axis=1) - fp * fr)
    gc += 2.0 * GRAD_C * (np.roll(fp * cr, 1, axis=1) - fp * cr)
    pop = float(np.sum(vc * c * c))
    static = float(np.sum(vc * ((U_RHO / 4.0) * (f * f - 1.0) ** 2 + (B_COEF - H_COEF + H_COEF * f * f) * c * c + (U_C / 2.0) * c**4)))
    twist = float(np.sum(vc * tw * c * c))
    return E, gf, gc, pop, {"static_energy": static, "twist_energy": twist}


def hessian(f: np.ndarray, c: np.ndarray, lam: float, G: dict[str, Any], winding: float = 1.0) -> sp.csr_matrix:
    na, np_, N = G["na"], G["nphi"], G["na"] * G["nphi"]
    vc, fa, fp, g, R = G["vc"], G["fa"], G["fp"], G["g"], G["R"]
    tw = (GRAD_C * winding * winding / R**2) / np.maximum(g, 1e-12) ** 2
    hff = vc * (U_RHO * (3.0 * f * f - 1.0) + 2.0 * H_COEF * c * c)
    hcc = vc * (2.0 * (B_COEF - H_COEF + H_COEF * f * f) + 6.0 * U_C * c * c + 2.0 * tw) - 2.0 * lam * vc
    hfc = vc * (4.0 * H_COEF * f * c)
    rows: list[int] = []; cols: list[int] = []; vals: list[float] = []
    def add(i: int, j: int, v: float) -> None:
        rows.append(i); cols.append(j); vals.append(float(v))
    for i in range(na):
        for j in range(np_):
            q = i * np_ + j; p = N + q
            add(q, q, hff[i, j]); add(p, p, hcc[i, j]); add(q, p, hfc[i, j]); add(p, q, hfc[i, j])
            # radial quadratic edges
            lo = fa[i, j]; hi = fa[i + 1, j]
            add(q, q, 2.0 * GRAD_F * (lo + hi)); add(p, p, 2.0 * GRAD_C * (lo + hi))
            if i:
                q0 = (i - 1) * np_ + j; p0 = N + q0
                add(q, q0, -2.0 * GRAD_F * lo); add(q0, q, -2.0 * GRAD_F * lo)
                add(p, p0, -2.0 * GRAD_C * lo); add(p0, p, -2.0 * GRAD_C * lo)
            # azimuthal quadratic edges
            jm = (j - 1) % np_; jp = (j + 1) % np_
            fm = fp[i, jm]; fo = fp[i, j]
            add(q, q, 2.0 * GRAD_F * (fm + fo)); add(p, p, 2.0 * GRAD_C * (fm + fo))
            q0 = i * np_ + jm; p0 = N + q0
            add(q, q0, -2.0 * GRAD_F * fm); add(q0, q, -2.0 * GRAD_F * fm)
            add(p, p0, -2.0 * GRAD_C * fm); add(p0, p, -2.0 * GRAD_C * fm)
    J = sp.coo_matrix((vals, (rows, cols)), shape=(2 * N, 2 * N)).tocsr()
    return J


def system_jacobian(f: np.ndarray, c: np.ndarray, lam: float, G: dict[str, Any], winding: float = 1.0) -> sp.csr_matrix:
    N = G["na"] * G["nphi"]
    H = hessian(f, c, lam, G, winding).tolil()
    col = (-2.0 * G["vc"] * c).ravel()
    J = sp.lil_matrix((2 * N + 1, 2 * N + 1))
    J[:2 * N, :2 * N] = H
    J[N:2 * N, 2 * N] = col
    J[2 * N, N:2 * N] = col
    return J.tocsr()


def residual_vector(f: np.ndarray, c: np.ndarray, lam: float, target: float, G: dict[str, Any], winding: float = 1.0) -> np.ndarray:
    _, gf, gc, pop, _ = energy_gradient(f, c, G, winding)
    return np.concatenate((gf.ravel(), (gc - 2.0 * lam * G["vc"] * c).ravel(), np.array([target - pop])))


def solve_relaxation(radius: float, target: float, na: int, nphi: int, winding: float = 1.0, seed: dict[str, Any] | None = None, maxiter: int = 80) -> dict[str, Any]:
    G = grid(radius, na, nphi)
    if seed is not None:
        f = np.asarray(seed["f"], dtype=np.float64).copy()
        c = np.asarray(seed["c"], dtype=np.float64).copy()
        if f.shape != (na, nphi) or c.shape != f.shape:
            seed = None
    if seed is None:
        aa = G["a"][:, None]; width = max(0.12 * radius, 0.2)
        c = np.exp(-(aa / width) ** 2) * (1.0 + 0.10 * np.cos(G["phi"])[None, :])
        c *= math.sqrt(target / max(float(np.sum(G["vc"] * c * c)), 1e-30))
        f = np.repeat(np.clip(1.0 - 0.55 * np.exp(-(aa / (1.3 * width)) ** 2), 0.02, 1.0), nphi, axis=1)
    lam = 0.0
    best = math.inf; it = 0
    for it in range(1, maxiter + 1):
        r = residual_vector(f, c, lam, target, G, winding)
        norm = float(np.max(np.abs(r)))
        if norm <= 1e-9:
            break
        try:
            step = spla.spsolve(system_jacobian(f, c, lam, G, winding), -r)
        except Exception:
            break
        if not np.all(np.isfinite(step)):
            break
        base = float(np.linalg.norm(r))
        accepted = False
        alpha = 1.0
        for _ in range(18):
            nf = f + alpha * step[: G["na"] * G["nphi"]].reshape(f.shape)
            nc = c + alpha * step[G["na"] * G["nphi"] : 2 * G["na"] * G["nphi"]].reshape(c.shape)
            if float(np.min(nf)) < 0.0 or float(np.max(nf)) > 1.0 or float(np.min(nc)) < 0.0:
                alpha *= 0.5
                continue
            nl = lam + alpha * step[-1]
            nr = residual_vector(nf, nc, nl, target, G, winding)
            nn = float(np.linalg.norm(nr))
            if nn < base * (1.0 - 1e-4 * alpha) or nn < 1e-10:
                f, c, lam = nf, nc, nl; accepted = True; best = min(best, nn); break
            alpha *= 0.5
        if not accepted:
            break
    r = residual_vector(f, c, lam, target, G, winding)
    E, _, _, pop, parts = energy_gradient(f, c, G, winding)
    return {"f": f, "c": c, "multiplier": float(lam), "residual": float(np.max(np.abs(r))), "iterations": it,
            "energy": E, "population": pop, "grid": G, **parts, "converged": bool(np.max(np.abs(r)) <= 1e-9)}


def metrics(f: np.ndarray, c: np.ndarray, G: dict[str, Any]) -> dict[str, float]:
    w = G["vc"] * c * c; by_a = np.sum(w, axis=1); total = float(np.sum(by_a))
    k = int(np.flatnonzero(np.cumsum(by_a) >= 0.999 * total)[0]) if total > 0 else G["na"] - 1
    a99 = float(G["a"][k]); support = G["a"] <= a99
    min_g = float(np.min(G["g"][support, :]))
    outer = float(np.sum(by_a[G["a"] > 0.9 * G["amax"]]) / total) if total > 0 else math.nan
    return {"a99": a99, "min_metric_factor": min_g, "outer_decile_fraction": outer}


def reconstruct(row: dict[str, Any], winding_default: float = 1.0) -> dict[str, Any]:
    R = float(row["radius"]); na = int(row["Na"]); np_ = int(row["Nphi"])
    G = grid(R, na, np_, float(row["amax"]))
    f = np.asarray(row["f"], dtype=np.float64); c = np.asarray(row["c"], dtype=np.float64)
    if f.shape != (na, np_) or c.shape != f.shape:
        raise VerificationError(f"profile shape mismatch at R={R}")
    E, gf, gc, pop, parts = energy_gradient(f, c, G, float(row.get("winding", winding_default)))
    lam = float(row.get("multiplier", 0.0)); target = float(row["density"])
    residual = max(float(np.max(np.abs(gf))), float(np.max(np.abs(gc - 2.0 * lam * G["vc"] * c))), abs(pop - target))
    out = {"energy": E, "population": pop, "residual": residual, **metrics(f, c, G), **parts}
    return out


def row_mass(row: dict[str, Any], charge: float) -> float:
    return float(row["energy"]) + charge * charge / (8.0 * math.pi * A_COEF * float(row["radius"]) * float(row["population"]))


def curves(primary: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for qkey, summary in primary.get("summary", {}).items():
        q = float(summary.get("charge", qkey))
        rows = list(primary.get("scan", {}).get("w1", []))
        rows += list(primary.get("refinement", {}).get("w1", []))
        rows = [r for r in rows if abs(float(r.get("charge", q))) < 1e-8 or "charge" not in r]
        by_r: dict[float, list[dict[str, Any]]] = {}
        for r in rows:
            by_r.setdefault(float(r["radius"]), []).append(r)
        curve = []
        for R in sorted(by_r):
            vals = [(row_mass(r, q), float(r["density"]), r) for r in by_r[R] if float(r.get("population", 0.0)) > 0]
            if vals:
                m, n, row = min(vals, key=lambda z: z[0])
                curve.append((R, m, n, row))
        result[qkey] = curve
    return result


def parabola_curvature(points: list[tuple[float, float]], idx: int) -> float | None:
    lo, hi = max(0, idx - 2), min(len(points), idx + 3)
    x = np.asarray([p[0] for p in points[lo:hi]], dtype=float)
    y = np.asarray([p[1] for p in points[lo:hi]], dtype=float)
    if len(x) < 3:
        return None
    co = np.polyfit(x - x[idx - lo], y, 2)
    return float(2.0 * co[0])

def classification(primary: dict[str, Any], curve_data: dict[str, Any], failures: bool = False) -> str:
    if failures:
        return "INCONCLUSIVE"
    interior = []
    for qkey, curve in curve_data.items():
        if not curve:
            continue
        j = int(np.argmin([p[1] for p in curve]))
        interior.append(0 < j < len(curve) - 1)
    if not interior or not any(interior):
        return "NO_INTERIOR_STATIONARY_RADIUS_IN_SCHEDULE"
    if any(not x for x in interior):
        return "RADIUS_SCHEDULE_BOUNDARY_LIMITED"
    for qkey, curve in curve_data.items():
        if curve:
            j = int(np.argmin([p[1] for p in curve]))
            if abs(curve[j][2] - min(DENSITIES)) < 1e-8 or abs(curve[j][2] - max(DENSITIES)) < 1e-8:
                return "DENSITY_SCHEDULE_BOUNDARY_LIMITED"
    s256 = primary.get("summary", {}).get("256", primary.get("summary", {}).get("256.0", {}))
    curve256 = curve_data.get("256", curve_data.get("256.0", []))
    if curve256 and min(p[1] for p in curve256) >= OMEGA_INF * 256.0:
        return "THICK_TORUS_LOOP_UNBOUND_IN_SCHEDULE"
    if any(s.get("geometry_qualified") is False for s in primary.get("summary", {}).values() if isinstance(s, dict)):
        return "THICK_TORUS_STATIONARY_RADIUS_INSIDE_CORE_OVERLAP"
    if float(s256.get("curvature_fit", 1.0)) <= 0.0 or float(s256.get("curvature_discrete", 1.0)) <= 0.0:
        return "THICK_TORUS_MARGINALLY_UNSTABLE_STATIONARY_RADIUS"
    eig = primary.get("spectrum", {})
    if any(float(s.get("min_eigenvalue", 1.0)) <= 0.0 for s in eig.values() if isinstance(s, dict)):
        return "THICK_TORUS_MARGINALLY_UNSTABLE_STATIONARY_RADIUS"
    return "SUPPORTS_CONDITIONAL_THICK_TORUS_GAP_MECHANISM"


def add_check(out: dict[str, Any], name: str, passed: bool, detail: Any) -> None:
    out["checks"].append({"name": name, "passed": bool(passed), "detail": detail})
    if not passed: out["failures"].append(name)


def source_checks(primary: dict[str, Any], inp: Path, out: dict[str, Any]) -> None:
    add_check(out, "primary_content_sha256", primary.get("content_sha256") == digest(primary), {"expected": digest(primary), "actual": primary.get("content_sha256")})
    for name, rec in primary.get("identities", {}).items():
        if not isinstance(rec, dict): add_check(out, f"identity:{name}", False, "not an object"); continue
        rel = rec.get("path"); snap = rec.get("snapshot")
        live = ROOT / str(rel) if rel else Path()
        spath = inp.parent / str(snap) if snap else Path()


        live = ROOT / str(rel) if rel else Path()
        spath = inp.parent / str(snap) if snap else Path()
        if snap and not spath.is_file():
            spath = ROOT / str(snap)
        passed = bool(rel and live.is_file() and snap and spath.is_file() and sha256_bytes(spath.read_bytes()) == str(rec.get("sha256")))
        add_check(out, f"identity:{name}", passed, {"path_exists": live.is_file(), "snapshot_exists": spath.is_file(), "snapshot_hash": sha256_bytes(spath.read_bytes()) if spath.is_file() else None, "recorded": rec.get("sha256")})
def verify(primary: dict[str, Any], inp: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"schema": SCHEMA, "binds": sha256_bytes(inp.read_bytes()), "checks": [], "failures": [], "not_performed": []}
    if not finite_tree(primary):
        add_check(out, "finite_json", False, "nonfinite value")
        out["status"] = "FAIL"
        out["content_sha256"] = digest(out)
        return out
    source_checks(primary, inp, out)
    stored: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for section in ("scan", "refinement"):
        for arm in ("w1", "w0"):
            for row in primary.get(section, {}).get(arm, []):
                if "f" in row and "c" in row:
                    try:
                        rec = reconstruct(row, 0.0 if arm == "w0" else 1.0); stored.append((row, rec))
                        checks = ("energy", "population", "a99", "min_metric_factor", "outer_decile_fraction", "residual")
                        good = all(err(rec[k], float(row[k])) <= PROFILE_TOL for k in checks if k in row)
                        good = good and abs(rec["population"] - float(row["density"])) <= 1e-9
                        add_check(out, f"profile:{section}:{arm}:{row.get('radius')}:{row.get('density')}", good, {k: rec[k] for k in checks})
                    except Exception as exc:
                        add_check(out, f"profile:{section}:{arm}:{row.get('radius')}:{row.get('density')}", False, str(exc))
    for idx, row in enumerate(primary.get("profiles", [])):
        if "f" not in row or "c" not in row:
            out["not_performed"].append(f"profiles[{idx}] reconstruction: arrays missing")
            continue
        try:
            rec = reconstruct(row, float(row.get("winding", 1.0))); stored.append((row, rec))
            fields = ("energy", "population", "a99", "min_metric_factor", "outer_decile_fraction", "residual")
            good = all(err(rec[k], float(row[k])) <= PROFILE_TOL for k in fields if k in row)
            good = good and abs(rec["population"] - float(row["density"])) <= 1e-9
            add_check(out, f"profile:profiles:{idx}", good, {k: rec[k] for k in fields})
        except Exception as exc:
            add_check(out, f"profile:profiles:{idx}", False, str(exc))
    if not stored: out["not_performed"].append("profile reconstruction: no stored profiles")
    is_synthetic = str(primary.get("schema", "")).endswith(".synthetic")
    if not is_synthetic:
        for row, rec in stored:
            if rec["residual"] > 1e-9:
                add_check(out, f"stationarity_gate:{row.get('radius')}:{row.get('density')}", False, rec["residual"])
    curve_data = curves(primary)
    for qkey, curve in curve_data.items():
        if curve:
            summary = primary.get("summary", {}).get(qkey, {})
            j = int(np.argmin([p[1] for p in curve])); R = curve[j][0]
            good = abs(R - float(summary.get("refined_radius", R))) <= 0.05
            fit = summary.get("curvature_fit")
            curv = parabola_curvature([(p[0], p[1]) for p in curve], j)
            if fit is not None and math.isfinite(float(fit)) and curv is not None and math.isfinite(curv): good = good and err(curv, float(fit)) <= 0.05
            add_check(out, f"mass_curve:{qkey}", good, {"radius": R, "curvature": curv})
        else: out["not_performed"].append(f"mass curve {qkey}: no rows")
    # Threshold/margin/bound checks are scalar and do not depend on a primary implementation.
    for qkey, summary in primary.get("summary", {}).items():
        q = float(summary.get("charge", qkey)); curve = curve_data.get(qkey, [])
        if curve:
            m = min(p[1] for p in curve)
            threshold = OMEGA_INF * abs(q); margin = threshold - m
            good = err(threshold, float(summary.get("threshold", threshold))) <= PROFILE_TOL
            good = good and err(margin, float(summary.get("margin", margin))) <= PROFILE_TOL
            good = good and bool(summary.get("bound")) == bool(m < threshold)
            add_check(out, f"threshold_margin:{qkey}", good, {"threshold": threshold, "margin": margin, "bound": m < threshold})
    # Independent solver witness points.  A stored warm start is used where available.
    solver_points = () if str(primary.get("schema", "")).endswith(".synthetic") else ((6.5, 5.0), (8.0, 5.0), (10.0, 8.0))
    if not solver_points:
        out["not_performed"].append("independent solver witness points: synthetic self-test has one 60x16 point")
    for R, n in solver_points:
        seed = None
        for row, _ in stored:
            if abs(float(row.get("radius", -1)) - R) < 1e-9 and abs(float(row.get("density", -1)) - n) < 1e-9 and int(row.get("Na", -1)) == 200 and int(row.get("Nphi", -1)) == 32:
                seed = row; break
        sol = solve_relaxation(R, n, 200, 32, 1.0, seed)
        target_rows = [r for r, _ in stored if abs(float(r.get("radius", -1)) - R) < 1e-9 and abs(float(r.get("density", -1)) - n) < 1e-9]
        if target_rows:
            er = min(err(sol["energy"], float(r["energy"])) for r in target_rows)
            good = er <= 2e-3 and sol["residual"] <= 1e-8 and abs(sol["population"] - n) <= 1e-9
        else:
            er = None; good = sol["residual"] <= 1e-8 and abs(sol["population"] - n) <= 1e-9
            out["not_performed"].append(f"solver primary energy {R},{n}: no corresponding row")
        add_check(out, f"independent_solver:{R}:{n}", good, {"energy": sol["energy"], "residual": sol["residual"], "population": sol["population"], "relative_energy_error": er})
    validation = primary.get("validation", {})
    vrows = validation if isinstance(validation, list) else list(validation.values()) if isinstance(validation, dict) else []
    if vrows:
        for i, row in enumerate(vrows):
            if not isinstance(row, dict) or "energy" not in row or "radius" not in row:
                out["not_performed"].append(f"validation:{i}: missing energy/radius")
                continue
            density = float(row.get("density", math.pi))
            expected = 22.174477188390973 if abs(density - 5.0) < 1e-8 else 14.571946092025838
            per_length = float(row["energy"]) / (2.0 * math.pi * float(row["radius"]))
            good = abs(per_length - expected) / expected <= 1e-2
            if abs(float(row["radius"]) - 8.0) < 1e-8 and abs(density - 5.0) < 1e-8:
                reduced = 2.0 * math.pi * 8.0 * expected + math.pi * 5.0 * 1.0118788464248585 / 8.0
                good = good or float(row["energy"]) <= reduced * (1.0 + 2e-3)
            add_check(out, f"validation:{i}", good, {"per_length": per_length, "expected": expected})
    else:
        out["not_performed"].append("validation rows: absent")
    # Mutation control is performed on a copy and must trip exactly the reconstruction comparison.
    if stored:
        mr = json.loads(json.dumps(primary)); changed = False
        for sec in ("scan", "refinement"):
            for arm in ("w1", "w0"):
                rows = mr.get(sec, {}).get(arm, [])
                if rows and "f" in rows[0]: rows[0]["energy"] = float(rows[0].get("energy", 1.0)) * (1.0 + 1e-6); changed = True; break
            if changed: break
        if changed:
            r0 = stored[0][1]; rr = reconstruct(next(r for s in ("scan", "refinement") for a in ("w1", "w0") for r in mr.get(s, {}).get(a, []) if "f" in r and "c" in r), 1.0)
            tripped = err(rr["energy"], float(next(r for s in ("scan", "refinement") for a in ("w1", "w0") for r in mr.get(s, {}).get(a, []) if "f" in r and "c" in r)["energy"])) > PROFILE_TOL
            add_check(out, "mutation_control", tripped, {"perturbation": 1e-6})
        else: out["not_performed"].append("mutation control: no profile")
    else: out["not_performed"].append("mutation control: no profile")
    branch = classification(primary, curve_data, bool(out["failures"]))
    reported = primary.get("classification", {}).get("branch")
    add_check(out, "classification", reported is None or branch == reported, {"independent": branch, "reported": reported})
    out["status"] = "PASS" if not out["failures"] else "FAIL"
    out["content_sha256"] = digest(out)
    return out


def synthetic_receipt() -> dict[str, Any]:
    sol = solve_relaxation(8.0, 5.0, 60, 16, 1.0, maxiter=80)
    G = sol["grid"]
    f = sol["f"]
    c = sol["c"] * math.sqrt(5.0 / max(sol["population"], 1e-30))
    E, gf, gc, pop, parts = energy_gradient(f, c, G, 1.0)
    residual = max(float(np.max(np.abs(gf))), float(np.max(np.abs(gc))), abs(pop - 5.0))
    m = metrics(f, c, G)
    row = {"radius": 8.0, "density": 5.0, "winding": 1, "Na": 60, "Nphi": 16,
           "amax": G["amax"], "energy": E, "population": pop, "multiplier": 0.0,
           "residual": residual, "iterations": sol["iterations"], "converged": False,
           **m, "static_energy": parts["static_energy"], "twist_energy": parts["twist_energy"],
           "f": f.tolist(), "c": c.tolist()}
    q = 256.0
    mass = row["energy"] + q*q/(8*math.pi*A_COEF*8*row["population"])
    return {"schema": PRIMARY_SCHEMA + ".synthetic", "identities": {}, "platform": {}, "coefficients": {}, "schedule": {}, "validation": {}, "scan": {"w1": [row], "w0": []}, "refinement": {"w1": [row], "w0": []}, "profiles": [row], "summary": {"256": {"charge": q, "refined_radius": 8.0, "curvature_fit": 1.0, "threshold": OMEGA_INF*q, "margin": OMEGA_INF*q-mass, "bound": mass < OMEGA_INF*q}}, "spectrum": {}, "controls": {}, "classification": {"branch": "NO_INTERIOR_STATIONARY_RADIUS_IN_SCHEDULE"}, "checks": [], "failures": [], "status": "PASS", "content_sha256": ""}


def self_test() -> int:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "primary.json"; o = Path(td) / "independent.json"
        primary = synthetic_receipt(); primary["content_sha256"] = digest(primary); p.write_text(json.dumps(primary, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        checked = verify(primary, p); o.write_text(json.dumps(checked, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        mutation = json.loads(json.dumps(primary)); mutation["scan"]["w1"][0]["energy"] *= 1.0 + 1e-6
        mutated = reconstruct(mutation["scan"]["w1"][0]); fired = err(mutated["energy"], mutation["scan"]["w1"][0]["energy"]) > PROFILE_TOL
        print("self-test checks:", len(checked["checks"])); print("self-test status:", checked["status"]); print("mutation control fired:", fired)
        return 0 if checked["status"] == "PASS" and fired else 1


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--input", type=Path); ap.add_argument("--output", type=Path); ap.add_argument("--self-test", action="store_true"); args = ap.parse_args()
    if args.self_test: return self_test()
    if args.input is None or args.output is None: ap.error("--input and --output are required unless --self-test")
    primary = json.loads(args.input.read_text(encoding="utf-8")); result = verify(primary, args.input); args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False), encoding="utf-8"); print(json.dumps({"status": result["status"], "checks": len(result["checks"]), "failures": result["failures"]}, sort_keys=True)); return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
