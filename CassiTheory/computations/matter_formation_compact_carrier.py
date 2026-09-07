#!/usr/bin/env python3
"""Primary radial compact-target carrier qualification.

This file intentionally owns its numerical implementation.  It emits one
self-contained receipt and raw arrays for the independent verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp
from scipy.integrate import quad, solve_bvp
from scipy.interpolate import CubicHermiteSpline
from scipy.linalg import eigh_tridiagonal
from scipy.optimize import brentq

SCHEMA = "matter-formation-compact-carrier-v1"
EXPECTED_PROTOCOL_SHA = "c13cdd8b8a3f6f704e0cb0a25f2412acdbd9f5ea7a4ad109babf4140eaca3a57"
HEADING = "### 18.2 Radial carrier qualification: pre-execution criteria\n"
EPSILON = 1.0e-5


def canonical_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_identity(root: Path, source: Path) -> dict[str, str]:
    raw = source.read_bytes()
    rel = source.resolve().relative_to(root.resolve()).as_posix()
    return {"path": rel, "sha256": sha256_bytes(canonical_bytes(raw))}


def finite_float(value: Any) -> bool:
    return isinstance(value, (float, int, np.floating, np.integer)) and math.isfinite(float(value))


def write_exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)


def write_json_exclusive(path: Path, obj: dict[str, Any]) -> None:
    payload = json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    write_exclusive(path, payload.encode("utf-8"))


def extract_protocol(note: Path) -> tuple[str, str]:
    text = note.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    if text.count(HEADING) != 1:
        raise ValueError("frozen section heading is missing or not unique")
    start = text.index(HEADING)
    rest = text[start:]
    if len(rest) == len(HEADING):
        section = rest
    else:
        import re

        match = re.search(r"\n#{1,3} ", rest[len(HEADING) :])
        section = rest if match is None else rest[: len(HEADING) + match.start() + 1]
    section = section.rstrip() + "\n"
    return section, sha256_bytes(section.encode("utf-8"))


def empty_receipt(identity: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "identities": identity,
        "exact": [],
        "profiles": [],
        "spectra": [],
        "checks": [],
        "failures": failures,
        "numerical_pass": False,
        "verdict": "INCONCLUSIVE",
    }


def exact_controls() -> list[dict[str, Any]]:
    s, R = sp.symbols("s R", positive=True)
    f = 2 * sp.atan(1 / s)
    fs = sp.diff(f, s)
    sinf = sp.sin(f)
    # r=R*s and f_r=f_s/R.  These are the radial E2 and E4 integrands.
    e2s = sp.simplify(((R * s) ** 2 * (fs / R) ** 2 + 2 * sinf**2) * R)
    e4s = sp.simplify((2 * sinf**2 * (fs / R) ** 2 + sinf**4 / (R * s) ** 2) * R)
    degree_s = sp.simplify(-(2 / sp.pi) * (fs / R) * sinf**2 * R)
    degree = sp.simplify(sp.integrate(degree_s, (s, 0, sp.oo)))
    e2 = sp.simplify(sp.integrate(e2s, (s, 0, sp.oo)))
    e4 = sp.simplify(sp.integrate(e4s, (s, 0, sp.oo)))
    A = sp.simplify(e2.subs(R, 1))
    C = sp.simplify((e4 * R).subs(R, 1))
    stationary = sp.simplify(sp.sqrt(C / A))
    normalized = sp.simplify((4 * sp.pi * (A * stationary + C / stationary)) / (12 * sp.pi**2))

    r, ff, p, q = sp.symbols("r f p q", positive=True)
    M = r**2 + 2 * sp.sin(ff) ** 2
    V = 2 * sp.sin(ff) ** 2 + sp.sin(ff) ** 4 / r**2
    lagrangian = M * p**2 + V
    # Total derivative d/dr with f'=p and p'=q.
    d_dp = 2 * M * q + 2 * (sp.diff(M, r) + sp.diff(M, ff) * p) * p
    residual = sp.simplify(d_dp - sp.diff(lagrangian, ff))
    declared = sp.simplify(2 * (M * q + 2 * r * p + sp.sin(2 * ff) * (p**2 - 1 - sp.sin(ff) ** 2 / r**2)))
    euler_residual = sp.simplify(residual - declared)

    rows = [
        {"name": "degree", "pass": bool(sp.simplify(degree - 1) == 0), "evidence": f"symbolic degree = {degree}"},
        {"name": "trial_E2", "pass": bool(sp.simplify(e2 - A * R) == 0 and A == 3 * sp.pi), "evidence": f"E2(R) = {sp.simplify(e2)}"},
        {"name": "trial_E4", "pass": bool(sp.simplify(e4 - C / R) == 0 and C == 3 * sp.pi / 2), "evidence": f"E4(R) = {sp.simplify(e4)}"},
        {"name": "trial_scale", "pass": bool(sp.simplify(stationary - 1 / sp.sqrt(2)) == 0), "evidence": f"stationary R = {stationary}"},
        {"name": "trial_bound_ratio", "pass": bool(sp.simplify(normalized - sp.sqrt(2)) == 0), "evidence": f"normalized minimum = {normalized}"},
        {"name": "euler_equation", "pass": bool(euler_residual == 0), "evidence": f"Euler residual after differentiation = {euler_residual}"},
    ]
    return rows


def ode_values(r: np.ndarray, f: np.ndarray, fp: np.ndarray) -> np.ndarray:
    sinf = np.sin(f)
    M = r * r + 2.0 * sinf * sinf
    return (-2.0 * r * fp - np.sin(2.0 * f) * (fp * fp - 1.0 - sinf * sinf / (r * r))) / M


def solve_profile(L: float) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray, CubicHermiteSpline, np.ndarray]:
    x0 = np.geomspace(EPSILON, L, 601)
    trial_R = 1.0 / math.sqrt(2.0)
    y0 = np.vstack((2.0 * np.arctan(trial_R / x0), -2.0 * trial_R / (x0 * x0 + trial_R * trial_R)))

    def fun(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return np.vstack((y[1], ode_values(x, y[0], y[1])))

    def bc(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        return np.array([left[0] - math.pi - EPSILON * left[1], right[1] + 2.0 * right[0] / L])

    sol = solve_bvp(fun, bc, x0, y0, tol=1.0e-8, max_nodes=50000, verbose=0)
    x, f, fp = (np.asarray(sol.x, dtype=np.float64), np.asarray(sol.y[0], dtype=np.float64), np.asarray(sol.y[1], dtype=np.float64))
    rms = np.asarray(sol.rms_residuals, dtype=np.float64)
    status = int(sol.status)
    message = str(sol.message)
    if x.ndim != 1 or f.ndim != 1 or fp.ndim != 1 or rms.ndim != 1 or len(rms) != len(x) - 1:
        raise ValueError("solve_bvp returned malformed profile arrays")
    if not all(np.all(np.isfinite(values)) for values in (x, f, fp, rms)):
        raise ValueError("solve_bvp returned nonfinite profile data")
    spline = CubicHermiteSpline(x, f, fp)
    return {"solver_status": status, "solver_message": message}, x, f, fp, spline, rms


def radial_integrals(L: float, x: np.ndarray, f: np.ndarray, fp: np.ndarray, spline: CubicHermiteSpline) -> dict[str, float]:
    b = float(fp[0])
    c = float(L * L * f[-1])

    def density(r: float, fv: float, pv: float) -> tuple[float, float, float]:
        s = math.sin(fv)
        e2 = r * r * pv * pv + 2.0 * s * s
        e4 = 2.0 * s * s * pv * pv + (s**4 / (r * r) if r else 0.0)
        degree = -(2.0 / math.pi) * pv * s * s
        return e2, e4, degree

    def inner(which: int, r: float) -> float:
        fv, pv = math.pi + b * r, b
        return density(r, fv, pv)[which]

    def middle(which: int, r: float) -> float:
        fv, pv = float(spline(r)), float(spline(r, 1))
        return density(r, fv, pv)[which]

    def outer(which: int, invr: float) -> float:
        if invr == 0.0:
            return 0.0
        r = 1.0 / invr
        fv, pv = c * invr * invr, -2.0 * c * invr**3
        return density(r, fv, pv)[which] / (invr * invr)

    vals: list[float] = []
    for which in range(3):
        val = quad(lambda z: inner(which, z), 0.0, EPSILON, epsabs=1.0e-10, epsrel=1.0e-10, limit=200)[0]
        val += quad(lambda z: middle(which, z), EPSILON, L, epsabs=1.0e-10, epsrel=1.0e-10, limit=500)[0]
        val += quad(lambda z: outer(which, z), 0.0, 1.0 / L, epsabs=1.0e-10, epsrel=1.0e-10, limit=200)[0]
        vals.append(float(val))
    half = float(brentq(lambda z: float(spline(z)) - math.pi / 2.0, EPSILON, L))
    return {"E2": 4.0 * math.pi * vals[0], "E4": 4.0 * math.pi * vals[1], "degree": vals[2], "origin_slope": b, "outer_value": float(f[-1]), "half_angle_radius": half}


def profile_row(L: int, output_dir: Path) -> tuple[dict[str, Any], CubicHermiteSpline, np.ndarray, np.ndarray, np.ndarray]:
    info, x, f, fp, spline, rms = solve_profile(float(L))
    path = output_dir / f"profile_L{L}.npz"
    with path.open("xb") as handle:
        np.savez(handle, x=np.asarray(x, dtype=np.float64), f=np.asarray(f, dtype=np.float64), fp=np.asarray(fp, dtype=np.float64), rms_residuals=np.asarray(rms, dtype=np.float64))
    raw_hash = sha256_bytes(path.read_bytes())
    uniform = np.linspace(EPSILON, float(L), 10001)
    fu = np.asarray(spline(uniform), dtype=np.float64)
    fpu = np.asarray(spline(uniform, 1), dtype=np.float64)
    if not np.all(np.isfinite(fu)) or not np.all(np.isfinite(fpu)):
        raise ValueError("interpolated profile is nonfinite")
    stats = radial_integrals(float(L), x, f, fp, spline)
    if not all(math.isfinite(value) for value in stats.values()):
        raise ValueError("profile measurement is nonfinite")
    E2, E4 = stats["E2"], stats["E4"]
    row: dict[str, Any] = {
        "label": f"L{L}", "L": int(L), "epsilon": EPSILON,
        "artifact": {"path": path.name, "sha256": raw_hash},
        "solver_status": int(info["solver_status"]), "solver_message": info["solver_message"],
        "node_count": int(len(x)), "rms_max": float(np.max(rms)),
        "boundary_residuals": [abs(float(f[0] - math.pi - EPSILON * fp[0])), abs(float(fp[-1] + 2.0 * f[-1] / L))],
        "profile_min": float(np.min(fu)), "profile_max": float(np.max(fu)), "derivative_max": float(np.max(fpu)),
        "E2": float(E2), "E4": float(E4), "energy": float(E2 + E4), "normalized_energy": float((E2 + E4) / (12.0 * math.pi * math.pi)),
        "degree": float(stats["degree"]), "origin_slope": float(stats["origin_slope"]), "outer_value": float(stats["outer_value"]),
        "half_angle_radius": float(stats["half_angle_radius"]), "virial_defect": float(abs(E2 - E4) / (E2 + E4)),
    }
    return row, spline, x, f, fp


def spectrum_row(L: int, h: float, spline: CubicHermiteSpline, output_dir: Path) -> dict[str, Any]:
    n = int(math.ceil((float(L) - EPSILON) / h))
    dx = (float(L) - EPSILON) / n
    x = np.linspace(EPSILON, float(L), n + 1, dtype=np.float64)
    interior = x[1:-1]
    fv = np.asarray(spline(interior), dtype=np.float64)
    fpv = np.asarray(spline(interior, 1), dtype=np.float64)
    fppv = np.asarray(spline(interior, 2), dtype=np.float64)
    M = interior * interior + 2.0 * np.sin(fv) ** 2
    Mf = 4.0 * np.sin(fv) * np.cos(fv)
    Mff = 4.0 * np.cos(2.0 * fv)
    Vff = 4.0 * np.cos(2.0 * fv) + 4.0 * np.sin(fv) ** 2 * (3.0 * np.cos(fv) ** 2 - np.sin(fv) ** 2) / (interior * interior)
    W = Vff / 2.0 - Mff * fpv * fpv / 2.0 - Mf * fppv
    face = (x[:-1] + x[1:]) * 0.5
    Mfacing = face * face + 2.0 * np.sin(np.asarray(spline(face), dtype=np.float64)) ** 2
    mass = M
    diag = (Mfacing[:-1] + Mfacing[1:]) / (dx * dx) + W
    upper = -Mfacing[1:-1] / (dx * dx)
    transformed_diag = diag / mass
    transformed_upper = upper / np.sqrt(mass[:-1] * mass[1:])
    eig, vec = eigh_tridiagonal(transformed_diag, transformed_upper, select="i", select_range=(0, 0))
    value = float(eig[0])
    z = np.asarray(vec[:, 0], dtype=np.float64)
    eta_interior = z / np.sqrt(mass)
    eta = np.concatenate((np.array([0.0]), eta_interior, np.array([0.0]))).astype(np.float64)
    Heta = diag * eta_interior
    Heta[:-1] += upper * eta_interior[1:]
    Heta[1:] += upper * eta_interior[:-1]
    Meta = mass * eta_interior
    residual = float(np.linalg.norm(Heta - value * Meta) / (np.linalg.norm(Heta) + abs(value) * np.linalg.norm(Meta) + 1.0e-30))
    if not math.isfinite(value) or not math.isfinite(residual) or not np.all(np.isfinite(eta)):
        raise ValueError("radial eigenpair is nonfinite")
    path = output_dir / f"spectrum_L{L}_h{h:.2f}.npz"
    with path.open("xb") as handle:
        np.savez(handle, x=x, eta=eta)
    return {"label": f"L{L}_h{h:.2f}", "L": int(L), "h": float(h), "cells": n, "artifact": {"path": path.name, "sha256": sha256_bytes(path.read_bytes())}, "eigenvalue": value, "residual": residual}


def add_check(checks: list[dict[str, Any]], failures: list[str], name: str, category: str, passed: bool, evidence: str) -> None:
    row = {"name": name, "category": category, "pass": bool(passed), "evidence": evidence}
    checks.append(row)
    if not passed:
        failures.append(name)

def build_receipt(root: Path, note: Path, output_dir: Path, source: Path) -> dict[str, Any]:
    program_id = source_identity(root, source)
    identities: dict[str, Any] = {"program": program_id}
    try:
        section, protocol_hash = extract_protocol(note)
        protocol_path = note.resolve().relative_to(root.resolve()).as_posix()
        identities["protocol"] = {"path": protocol_path, "heading": HEADING.rstrip("\n"), "sha256": protocol_hash}
        write_exclusive(output_dir / "protocol.txt", section.encode("utf-8"))
        if protocol_hash != EXPECTED_PROTOCOL_SHA:
            return empty_receipt(identities, ["protocol_hash_mismatch"])
    except Exception as exc:
        return empty_receipt(identities, [f"missing_or_invalid_frozen_record: {exc}"])

    exact = exact_controls()
    profiles: list[dict[str, Any]] = []
    splines: dict[int, CubicHermiteSpline] = {}
    failures: list[str] = []
    checks: list[dict[str, Any]] = []
    try:
        for L in (16, 32, 64):
            row, spline, _, _, _ = profile_row(L, output_dir)
            profiles.append(row)
            splines[L] = spline
    except Exception as exc:
        failures.append(f"profile_execution: {exc}")
        return {"schema": SCHEMA, "identities": identities, "exact": exact, "profiles": profiles, "spectra": [], "checks": checks, "failures": failures, "numerical_pass": False, "verdict": "INCONCLUSIVE"}

    spectra: list[dict[str, Any]] = []
    try:
        for L in (16, 32, 64):
            for h in (0.04, 0.02):
                spectra.append(spectrum_row(L, h, splines[L], output_dir))
    except Exception as exc:
        failures.append(f"spectrum_execution: {exc}")
        return {"schema": SCHEMA, "identities": identities, "exact": exact, "profiles": profiles, "spectra": spectra, "checks": checks, "failures": failures, "numerical_pass": False, "verdict": "INCONCLUSIVE"}

    add_check(checks, failures, "exact_controls", "qualification", all(bool(row["pass"]) for row in exact), "all six symbolic controls pass")
    for row in profiles:
        prefix = row["label"]
        finite = all(finite_float(row[k]) for k in ("rms_max", "profile_min", "profile_max", "derivative_max", "E2", "E4", "energy", "normalized_energy", "degree", "origin_slope", "outer_value", "half_angle_radius", "virial_defect"))
        good = bool(row["solver_status"] == 0 and finite and row["node_count"] >= 601 and row["rms_max"] <= 1.1e-8 and max(row["boundary_residuals"]) <= 1.0e-9 and row["profile_min"] >= -1.0e-8 and row["profile_max"] <= math.pi + 1.0e-8 and row["derivative_max"] <= 1.0e-8)
        add_check(checks, failures, f"{prefix}_solve", "qualification", good, f"status={row['solver_status']}, rms_max={row['rms_max']:.17g}, boundary={row['boundary_residuals']}")
        energy_ok = bool(abs(row["degree"] - 1.0) <= 1.0e-7 and 1.0 <= row["normalized_energy"] <= math.sqrt(2.0) + 1.0e-7 and row["virial_defect"] <= 1.0e-4)
        add_check(checks, failures, f"{prefix}_energy_degree", "qualification", energy_ok, f"degree={row['degree']:.17g}, normalized_energy={row['normalized_energy']:.17g}, virial_defect={row['virial_defect']:.17g}")
    p32, p64 = profiles[1], profiles[2]
    for field in ("energy", "origin_slope", "half_angle_radius"):
        delta = abs(p32[field] - p64[field]) / max(1.0, abs(p32[field]), abs(p64[field]))
        add_check(checks, failures, f"L32_L64_{field}_stability", "qualification", delta <= 1.0e-4, f"relative_change={delta:.17g}")

    by_label = {row["label"]: row for row in spectra}
    nonnegative = True
    for row in spectra:
        nonnegative = nonnegative and row["eigenvalue"] >= -1.0e-6
        add_check(checks, failures, f"{row['label']}_residual", "stability", row["residual"] <= 1.0e-8, f"eigenvalue={row['eigenvalue']:.17g}, residual={row['residual']:.17g}")
        add_check(checks, failures, f"{row['label']}_nonnegative", "stability", row["eigenvalue"] >= -1.0e-6, f"eigenvalue={row['eigenvalue']:.17g}")
    for L in (16, 32, 64):
        coarse, fine = by_label[f"L{L}_h0.04"], by_label[f"L{L}_h0.02"]
        bound = 5.0e-3 * max(1.0, abs(fine["eigenvalue"]))
        add_check(checks, failures, f"L{L}_primary_refinement", "stability", abs(coarse["eigenvalue"] - fine["eigenvalue"]) <= bound, f"difference={abs(coarse['eigenvalue'] - fine['eigenvalue']):.17g}, bound={bound:.17g}")
    qualification_pass = all(bool(c["pass"]) for c in checks if c["category"] == "qualification")
    stability_other_pass = all(bool(c["pass"]) for c in checks if c["category"] == "stability" and not c["name"].endswith("_nonnegative"))
    if qualification_pass and stability_other_pass and not nonnegative:
        verdict = "CONTRADICTS—radial energetic stability of the declared compact-target carrier"
    elif all(bool(c["pass"]) for c in checks):
        verdict = "SUPPORTS—primary finite-domain radial compact-target calculation"
    else:
        verdict = "INCONCLUSIVE"
    return {"schema": SCHEMA, "identities": identities, "exact": exact, "profiles": profiles, "spectra": spectra, "checks": checks, "failures": failures, "numerical_pass": bool(all(bool(c["pass"]) for c in checks)), "verdict": verdict}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--note", type=Path, default=root / "computations" / "matter-formation-continuum-report.md")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output_dir = args.output_dir.resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except Exception as exc:
        print(f"Cannot create fresh output directory: {exc}", file=sys.stderr)
        return 2
    try:
        receipt = build_receipt(root, args.note.resolve(), output_dir, Path(__file__).resolve())
    except Exception as exc:
        receipt = empty_receipt({"program": source_identity(root, Path(__file__).resolve())}, [f"unexpected_failure: {exc}"])
    try:
        write_json_exclusive(output_dir / "results.json", receipt)
    except Exception as exc:
        print(f"Cannot write receipt: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"verdict": receipt["verdict"], "failures": receipt["failures"],
                      "profiles": [{"L": row["L"], "normalized_energy": row["normalized_energy"],
                                    "degree": row["degree"]} for row in receipt["profiles"]]},
                     ensure_ascii=False, allow_nan=False))
    return 0 if bool(receipt.get("numerical_pass")) else 1


if __name__ == "__main__":
    sys.exit(main())
