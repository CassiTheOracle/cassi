#!/usr/bin/env python3
"""Primary adaptive collocation receipt for the charged interface in report §34."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy.integrate import solve_bvp
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "computations" / "matter-formation-continuum-report.md"
PARENT = ROOT / "foundations" / "particle-stationary-action-closure.md"
PROTOCOL_HEADING = "### 34.4 Charged-interface calculation: pre-execution criteria\n"
DERIVATION_HEADING = "### 34.1 Carrier loading and mediator nodes\n"
PROTOCOL_SHA256 = "710b17d73ef225acde87dad2b45e16eb40aebe2fe2c7d223cd94430c49bf8300"
DERIVATION_SHA256 = "c235c44d800281b5c08a706179d64349d6055001b0bf27683e909a10307666a8"
PARENT_SHA256 = "4b00696501134487757f174eb08e4022609ceefe39f32e169d294f99a79f8956"
SCHEMA = "matter-formation-charged-interface-v1"
SUPPORTS = "SUPPORTS-conditional charged coexistence interface"
INCONCLUSIVE = "INCONCLUSIVE"
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
E_C = 3.0 / 4.0
H_C = 2.9598260763447164
A = 1.0 / 16.0
DOMAINS = ((6.0, 2048, 129), (9.0, 3072, 193), (12.0, 4096, 257))
BVP_TOL = 1.0e-8
BVP_MAX_NODES = 32768
DERIVATIVE_TOL = 1.0e-6
FIRST_INTEGRAL_TOL = 1.0e-6
AMPLITUDE_EPS = 1.0e-9
SIGMA_EPS = 1.0e-6
DOMAIN_SIGMA_TOL = 1.0e-5


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def raw_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def frozen_section(path: Path, heading: str, stop_heading: str | None = None) -> str:
    text = canonical_bytes(path).decode("utf-8")
    if text.count(heading) != 1:
        raise ValueError(f"frozen heading is not unique: {heading.strip()}")
    start = text.find(heading)
    if start < 0:
        raise ValueError(f"missing frozen heading: {heading.strip()}")
    end = len(text)
    if stop_heading is not None:
        if text.count(stop_heading) != 1:
            raise ValueError(f"frozen stop heading is not unique: {stop_heading.strip()}")
        stop = text.find(stop_heading, start + len(heading))
        if stop < 0:
            raise ValueError(f"missing frozen stop heading: {stop_heading.strip()}")
        end = stop
    else:
        lines = text[start:].splitlines(keepends=True)
        consumed = len(lines[0])
        for line in lines[1:]:
            stripped = line.lstrip()
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                if level <= 3:
                    break
            consumed += len(line)
        end = start + consumed
    return text[start:end].rstrip() + "\n"


def exact_text(value: Any) -> str:
    return sp.sstr(sp.factor(value))


def decimal_text(value: Any) -> str:
    return str(sp.N(value, 50))


def finite_float(value: Any) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"nonfinite value: {value}")
    return out


def finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(isinstance(k, str) and finite_tree(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_tree(v) for v in value)
    return True


def check(checks: list[dict[str, Any]], name: str, passed: bool, evidence: Any) -> None:
    checks.append({"name": name, "pass": bool(passed), "exact_evidence": evidence})

def algebra() -> tuple[list[dict[str, Any]], dict[str, str], dict[str, float], dict[str, str]]:
    """Perform only the declared symbolic identities, returning their witnesses."""
    f, c = sp.symbols("f c", real=True)
    ur, uc, k, e, h, a = (sp.Symbol(name, positive=True, real=True) for name in ("u_rho", "u_C", "k_Cx", "e_C", "h_C", "a"))
    B = e + 1 / (4 * a)
    S = sp.sqrt(ur * uc / 2)
    D = h - S
    n0 = sp.sqrt(ur / (2 * uc))
    omega2 = (B - h + S) / a
    q0 = 2 * a * sp.sqrt(omega2) * n0
    V = ur * (f**2 - 1) ** 2 / 4 + (B - h * (1 - f**2)) * c**2 + uc * c**4 / 2
    U = V - a * omega2 * c**2
    factor_rhs = (sp.sqrt(ur) * (1 - f**2) / 2 - sp.sqrt(uc / 2) * c**2) ** 2 + D * f**2 * c**2
    checks: list[dict[str, Any]] = []
    expressions: dict[str, str] = {}
    check(checks, "coexistence_factorization", sp.simplify(U - factor_rhs) == 0, exact_text(U - factor_rhs))
    expressions["V_a"] = exact_text(V)
    expressions["U_0"] = exact_text(U)
    x, y, xd, yd, om = sp.symbols("x y xdot ydot Omega", real=True)
    imag = x * yd - y * xd
    temporal_lhs = a * (xd**2 + yd**2) + 2 * a * om * imag + V
    temporal_rhs = a * ((xd - om * y) ** 2 + (yd + om * x) ** 2) + V - a * om**2 * (x**2 + y**2)
    temporal_residual = sp.simplify(temporal_lhs - temporal_rhs)
    check(checks, "temporal_charge_square", temporal_residual == 0, exact_text(temporal_residual))
    expressions["temporal_charge_square_residual"] = exact_text(temporal_residual)

    points = ((sp.Integer(1), sp.Integer(0)), (sp.Integer(0), sp.sqrt(n0)))
    for label, point in (("vacuum", points[0]), ("populated", points[1])):
        gradient = (sp.diff(U, f).subs({f: point[0], c: point[1]}), sp.diff(U, c).subs({f: point[0], c: point[1]}))
        check(checks, f"homogeneous_{label}_stationary", all(sp.simplify(v) == 0 for v in gradient), [exact_text(v) for v in gradient])
        check(checks, f"homogeneous_{label}_grand_potential_zero", sp.simplify(U.subs({f: point[0], c: point[1]})) == 0, exact_text(U.subs({f: point[0], c: point[1]})))
    energy_pop = sp.simplify(a * omega2 * n0 + V.subs({f: 0, c: sp.sqrt(n0)}))
    charge_energy_residual = sp.simplify(energy_pop - sp.sqrt(omega2) * q0)
    check(checks, "bulk_energy_charge_relation", charge_energy_residual == 0, exact_text(charge_energy_residual))
    expressions["bulk_energy_density"] = exact_text(energy_pop)
    expressions["bulk_charge_density"] = exact_text(q0)

    r = sp.symbols("r", real=True)
    ff = sp.Function("f")(r)
    cc = sp.Function("c")(r)
    eta = sp.Function("eta")(r)
    etac = sp.Function("etac")(r)
    hf_identity = sp.simplify((-sp.diff(eta, r, 2) + sp.diff(ff, r, 2) / ff * eta) * eta - ff**2 * sp.diff(eta / ff, r) ** 2 - sp.diff(eta**2 * sp.diff(ff, r) / ff - eta * sp.diff(eta, r), r))
    hc_identity = sp.simplify(k * ((-sp.diff(etac, r, 2) + sp.diff(cc, r, 2) / cc * etac) * etac - cc**2 * sp.diff(etac / cc, r) ** 2 - sp.diff(etac**2 * sp.diff(cc, r) / cc - etac * sp.diff(etac, r), r)))
    check(checks, "phase_ground_state_identity_f", hf_identity == 0, exact_text(hf_identity))
    check(checks, "phase_ground_state_identity_c", hc_identity == 0, exact_text(hc_identity))
    expressions["phase_f_remainder_derivative"] = exact_text(sp.diff(eta**2 * sp.diff(ff, r) / ff - eta * sp.diff(eta, r), r))
    expressions["phase_c_remainder_derivative"] = exact_text(k * sp.diff(etac**2 * sp.diff(cc, r) / cc - etac * sp.diff(etac, r), r))

    alpha = sp.sqrt(D * k / (2 * uc))
    p = sp.sqrt(ur) * (1 - f**2) / 2
    q = sp.sqrt(uc / 2) * c**2
    fp, cp = sp.symbols("f_prime c_prime", real=True)
    Wprime = sp.sqrt(2) * alpha * ((p - q) * fp - 2 * sp.sqrt(uc / 2) * f * c * cp)
    surface_remainder = sp.simplify(fp**2 / 2 + k * cp**2 / 2 + (p - q) ** 2 + D * f**2 * c**2 - Wprime - (fp - sp.sqrt(2) * alpha * (p - q)) ** 2 / 2 - k * (cp + 2 * alpha * sp.sqrt(uc) * f * c / k) ** 2 / 2)
    expected_remainder = sp.simplify((1 - alpha**2) * (p - q) ** 2 + (D - 2 * alpha**2 * uc / k) * f**2 * c**2)
    check(checks, "surface_lower_bound_remainder_identity", sp.simplify(surface_remainder - expected_remainder) == 0, {"remainder": exact_text(surface_remainder), "expected": exact_text(expected_remainder)})
    expressions["surface_W"] = exact_text(sp.sqrt(2) * alpha * (sp.sqrt(ur) * (f - f**3 / 3) / 2 - sp.sqrt(uc / 2) * f * c**2))
    expressions["surface_remainder"] = exact_text(expected_remainder)

    substitutions = {ur: sp.Integer(4), uc: sp.Integer(1), k: sp.Integer(1), e: sp.Rational(3, 4), h: sp.Rational("2.9598260763447164"), a: sp.Rational(1, 16)}
    values = {
        "B": sp.simplify(B.subs(substitutions)), "S": sp.simplify(S.subs(substitutions)), "D": sp.simplify(D.subs(substitutions)),
        "n0": sp.simplify(n0.subs(substitutions)), "Omega0": sp.sqrt(sp.simplify(omega2.subs(substitutions))), "q0": sp.simplify(q0.subs(substitutions)),
        "alpha": sp.simplify(alpha.subs(substitutions)),
    }
    values["sigma_lower"] = sp.sqrt(2 * ur).subs(substitutions) * values["alpha"] / 3
    m = sp.simplify(k.subs(substitutions) * values["n0"])
    quotient = sp.Piecewise((sp.Rational(1, 2), sp.Eq(m, 1)), ((m ** sp.Rational(3, 2) - 1) / (3 * (m - 1)), True))
    values["sigma_upper"] = sp.sqrt(2 * values["D"] * values["n0"]) * quotient
    check(checks, "coexistence_D_positive", bool(sp.N(D.subs(substitutions), 50) > 0), exact_text(D.subs(substitutions)))
    check(checks, "coexistence_frequency_squared_positive", bool(sp.N(omega2.subs(substitutions), 50) > 0), exact_text(omega2.subs(substitutions)))
    check(checks, "lower_bound_regime_Dk_lt_2uC", bool(sp.N((D * k - 2 * uc).subs(substitutions), 50) < 0), exact_text((D * k - 2 * uc).subs(substitutions)))
    remainder_coeff = sp.simplify((D - 2 * alpha**2 * uc / k).subs(substitutions))
    remainder_square_coeff = sp.simplify((1 - alpha**2).subs(substitutions))
    check(checks, "surface_lower_bound_remainder_nonnegative", bool(sp.N(remainder_coeff, 50) >= 0 and sp.N(remainder_square_coeff, 50) >= 0), {"square_coefficient": exact_text(remainder_square_coeff), "coupled_coefficient": exact_text(remainder_coeff)})
    check(checks, "surface_lower_bound_remainder_coupling_cancels", remainder_coeff == 0, exact_text(remainder_coeff))
    coefficient_checks = {name: exact_text(value) for name, value in values.items()}
    scalar_values = {name: finite_float(sp.N(value, 50)) for name, value in values.items()}
    return checks, expressions, scalar_values, coefficient_checks


def library_versions() -> dict[str, str]:
    versions: dict[str, str] = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "sympy": sp.__version__}
    for name in ("pip",):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return versions


def empty_receipt() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "identities": {},
        "artifacts": [],
        "scalars": {},
        "scalars_exact": {},
        "scalars_decimal": {},
        "rows": [],
        "checks": [],
        "failures": [],
        "attempts": [],
        "numerical_pass": False,
        "verdict": INCONCLUSIVE,
        "qualification_scope": "Primary stationary-interface calculation only; joint evidence requires the independent verifier and analytical review.",
        "complete_physical_matter_formation": False,
        "library_versions": {},
        "exact_expressions": {},
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.open("xb").write((json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))


def artifact(path: Path, output: Path) -> dict[str, Any]:
    digest = raw_sha256(path)
    return {"path": path.relative_to(output).as_posix(), "raw_sha256": digest, "sha256": digest, "bytes": path.stat().st_size}


def source_identity(path: Path, canonical_hash: str | None = None) -> dict[str, Any]:
    canonical = canonical_bytes(path)
    digest = canonical_hash or sha256_bytes(canonical)
    return {"path": relpath(path), "canonical_sha256": digest, "sha256": digest, "raw_sha256": raw_sha256(path)}


def initial_profile(r: np.ndarray, side: str, n0: float) -> np.ndarray:
    x = -r if side == "left" else r
    tanh = np.tanh(x)
    sech2 = 1.0 / np.cosh(x) ** 2
    f2 = (1.0 + tanh) / 2.0
    c2 = n0 * (1.0 - tanh) / 2.0
    f = np.sqrt(f2)
    c = np.sqrt(c2)
    fx = sech2 / (4.0 * f)
    cx = -n0 * sech2 / (4.0 * c)
    fr = -fx if side == "left" else fx
    cr = -cx if side == "left" else cx
    return np.vstack((f, c, fr, cr))


def solve_domain(L: float, intervals: int, initial_nodes: int, n0: float, omega0: float, output: Path) -> dict[str, Any]:
    row: dict[str, Any] = {"L": L, "intervals": intervals, "initial_nodes_per_half": initial_nodes, "fields_file": f"fields_L{int(L)}.npz", "pass": False}
    try:
        r = np.linspace(0.0, L, initial_nodes)
        guess = np.vstack((initial_profile(r, "left", n0), initial_profile(r, "right", n0)))

        def fun(rr: np.ndarray, yy: np.ndarray) -> np.ndarray:
            out = np.empty_like(yy)
            for offset in (0, 4):
                f, c, fp, cp = yy[offset : offset + 4]
                out[offset] = fp
                out[offset + 1] = cp
                out[offset + 2] = U_RHO * (f * f - 1.0) * f + 2.0 * H_C * f * c * c
                out[offset + 3] = 2.0 * (H_C * f * f - math.sqrt(U_RHO * U_C / 2.0) + U_C * c * c) * c / K_CX
            return out

        root = 1.0 / math.sqrt(2.0)
        c0 = math.sqrt(n0)

        def bc(ya: np.ndarray, yb: np.ndarray) -> np.ndarray:
            return np.array((ya[0] - root, ya[4] - root, ya[1] - ya[5], ya[3] + ya[7], yb[0], yb[1] - c0, yb[4] - 1.0, yb[5]))

        solution = solve_bvp(fun, bc, r, guess, tol=BVP_TOL, max_nodes=BVP_MAX_NODES, verbose=0)
        x = np.linspace(-L, L, intervals + 1)
        rr = np.abs(x)
        values = solution.sol(rr)
        left = values[:4]
        right = values[4:]
        use_left = x < 0.0
        f = np.where(use_left, left[0], right[0])
        c = np.where(use_left, left[1], right[1])
        fx = np.where(use_left, -left[2], right[2])
        cx = np.where(use_left, -left[3], right[3])
        center = x == 0.0
        if np.any(center):
            f[center] = 0.5 * (left[0, center] + right[0, center])
            c[center] = 0.5 * (left[1, center] + right[1, center])
            fx[center] = 0.5 * (-left[2, center] + right[2, center])
            cx[center] = 0.5 * (-left[3, center] + right[3, center])
        S = math.sqrt(U_RHO * U_C / 2.0)
        B = E_C + 1.0 / (4.0 * A)
        D = H_C - S
        U = U_RHO * (f * f - 1.0) ** 2 / 4.0 + (B - H_C * (1.0 - f * f)) * c * c + U_C * c**4 / 2.0 - A * omega0**2 * c * c
        kinetic = 0.5 * fx**2 + 0.5 * K_CX * cx**2
        first_residual = kinetic - U
        sigma_value = float(np.trapezoid(kinetic + U, x))
        sigma = sigma_value if math.isfinite(sigma_value) else None
        bvp_rms_value = float(np.max(solution.rms_residuals)) if solution.rms_residuals.size else 0.0
        bvp_rms = bvp_rms_value if math.isfinite(bvp_rms_value) else None
        boundary_value = float(np.max(np.abs(bc(solution.sol(0.0), solution.sol(L)))))
        boundary_rms = boundary_value if math.isfinite(boundary_value) else None
        finite_arrays = bool(np.all(np.isfinite(np.stack((x, f, c, fx, cx)))) and sigma is not None and bvp_rms is not None and boundary_rms is not None)
        radial_f_left_prime = float(solution.y[2, 0])
        radial_f_right_prime = float(solution.y[6, 0])
        physical_f_left_prime = -radial_f_left_prime
        physical_f_right_prime = radial_f_right_prime
        derivative_jump = radial_f_left_prime + radial_f_right_prime
        stats = (float(np.min(f)), float(np.max(f)), float(np.min(c)), float(np.max(c)))
        fmin, fmax, cmin, cmax = stats if all(math.isfinite(value) for value in stats) else (None, None, None, None)
        amp_pass = bool(fmin is not None and fmax is not None and cmin is not None and cmax is not None and fmin >= -AMPLITUDE_EPS and fmax <= 1.0 + AMPLITUDE_EPS and cmin >= -AMPLITUDE_EPS and cmax <= c0 + AMPLITUDE_EPS)
        max_first_value = float(np.max(np.abs(first_residual)))
        max_first = max_first_value if math.isfinite(max_first_value) else None
        fields_path = output / row["fields_file"]
        np.savez(fields_path, x=x, f=f, c=c, fx=fx, cx=cx)
        row.update({"bvp_success": bool(solution.success), "bvp_status": int(solution.status), "bvp_message": str(solution.message), "n_nodes_per_half": int(solution.x.size), "max_bvp_rms_residual": bvp_rms, "boundary_residual_max": boundary_rms, "radial_f_left_prime": radial_f_left_prime, "radial_f_right_prime": radial_f_right_prime, "physical_f_left_prime": physical_f_left_prime, "physical_f_right_prime": physical_f_right_prime, "physical_derivative_jump": physical_f_right_prime - physical_f_left_prime, "max_first_integral_residual": max_first, "sigma": sigma, "derivative_jump": derivative_jump, "derivative_jump_abs": abs(derivative_jump), "f_min": fmin, "f_max": fmax, "c_min": cmin, "c_max": cmax, "finite_arrays": finite_arrays, "amplitude_bounds_pass": amp_pass, "surface_bound_pass": False})
        row["pass"] = bool(solution.success and finite_arrays and amp_pass and math.isfinite(derivative_jump) and abs(derivative_jump) < DERIVATIVE_TOL and max_first is not None and max_first < FIRST_INTEGRAL_TOL)
        if not finite_arrays:
            for key, value in row.items():
                if isinstance(value, float) and not math.isfinite(value):
                    row[key] = None
        return row
    except Exception as exc:  # preserve this attempted row and continue the schedule
        row.update({"error": f"{type(exc).__name__}: {exc}", "bvp_success": False, "finite_arrays": False})
        return row


def run(note: Path, output: Path) -> int:
    receipt = empty_receipt()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except Exception as exc:
        return 1
    try:
        if not note.is_file() or not PARENT.is_file():
            raise FileNotFoundError("missing report or parent source")
        protocol = frozen_section(note, PROTOCOL_HEADING)
        derivation = frozen_section(note, DERIVATION_HEADING, PROTOCOL_HEADING)
        parent = canonical_bytes(PARENT).decode("utf-8")
        protocol_hash = sha256_bytes(protocol.encode("utf-8"))
        derivation_hash = sha256_bytes(derivation.encode("utf-8"))
        parent_hash = sha256_bytes(parent.encode("utf-8"))
        if protocol_hash != PROTOCOL_SHA256 or derivation_hash != DERIVATION_SHA256 or parent_hash != PARENT_SHA256:
            raise ValueError("altered frozen input identity")
    except Exception as exc:
        receipt["failures"] = [f"frozen_inputs: {type(exc).__name__}: {exc}"]
        receipt["library_versions"] = library_versions()
        receipt["attempts"] = [{"stage": "prerequisite_validation", "pass": False, "error": receipt["failures"][0]}]
        write_json(output / "results.json", receipt)
        print(json.dumps(receipt, ensure_ascii=False, allow_nan=False))
        return 1

    try:
        checks, expressions, scalars, exact_scalars = algebra()
        receipt["checks"] = checks
        receipt["exact_expressions"] = expressions
        receipt["scalars"] = {name: finite_float(value) for name, value in scalars.items()}
        receipt["scalars_exact"] = exact_scalars
        receipt["scalars_decimal"] = {name: decimal_text(value) for name, value in scalars.items()}
        receipt["library_versions"] = library_versions()
        report_raw = raw_sha256(note)
        receipt["identities"] = {
            "protocol": {"path": relpath(note), "canonical_sha256": PROTOCOL_SHA256, "sha256": PROTOCOL_SHA256, "raw_sha256": report_raw},
            "derivation": {"path": relpath(note), "canonical_sha256": DERIVATION_SHA256, "sha256": DERIVATION_SHA256, "raw_sha256": report_raw},
            "parent": source_identity(PARENT, PARENT_SHA256),
            "program": source_identity(Path(__file__)),
        }
        snapshots = {
            "protocol.txt": protocol.encode("utf-8"),
            "derivation.txt": derivation.encode("utf-8"),
            "report_source.md": canonical_bytes(note),
            "parent_source.md": canonical_bytes(PARENT),
            "program_source.py": canonical_bytes(Path(__file__)),
        }
        for name, data in snapshots.items():
            path = output / name
            path.open("xb").write(data)
            receipt["artifacts"].append(artifact(path, output))
        # The report itself is bound by the protocol/derivation identities;
        # all artifact paths remain relative to this fresh output directory.

        n0 = receipt["scalars"]["n0"]
        omega0 = receipt["scalars"]["Omega0"]
        rows: list[dict[str, Any]] = []
        for L, intervals, nodes in DOMAINS:
            row = solve_domain(L, intervals, nodes, n0, omega0, output)
            row["sigma_lower"] = receipt["scalars"]["sigma_lower"]
            row["sigma_upper"] = receipt["scalars"]["sigma_upper"]
            sigma_value = row.get("sigma")
            if isinstance(sigma_value, (int, float)) and math.isfinite(float(sigma_value)):
                row["surface_bound_pass"] = bool(sigma_value >= row["sigma_lower"] - SIGMA_EPS and sigma_value <= row["sigma_upper"] + SIGMA_EPS)
                row["pass"] = bool(row.get("pass", False) and row["surface_bound_pass"])
            else:
                row["surface_bound_pass"] = False
                row["pass"] = False
            if row.get("fields_file") and (output / row["fields_file"]).is_file():
                receipt["artifacts"].append(artifact(output / row["fields_file"], output))
            rows.append(row)
        receipt["rows"] = rows
        for row in rows:
            check(receipt["checks"], f"domain_L{int(row['L'])}_successful_finite", bool(row.get("bvp_success", False) and row.get("finite_arrays", False)), {"bvp_success": row.get("bvp_success", False), "finite_arrays": row.get("finite_arrays", False)})
        finest = {int(row["L"]): row for row in rows if "L" in row}
        finest12 = finest.get(12, {})
        jump_value = finest12.get("derivative_jump_abs")
        first_value = finest12.get("max_first_integral_residual")
        jump_pass = isinstance(jump_value, (int, float)) and math.isfinite(float(jump_value)) and float(jump_value) < DERIVATIVE_TOL
        first_pass = isinstance(first_value, (int, float)) and math.isfinite(float(first_value)) and float(first_value) < FIRST_INTEGRAL_TOL
        amp_pass = bool(finest12.get("amplitude_bounds_pass", False))
        check(receipt["checks"], "finest_L12_derivative_jump", jump_pass, {"absolute_jump": jump_value, "tolerance": DERIVATIVE_TOL})
        check(receipt["checks"], "finest_L12_first_integral", first_pass, {"maximum_absolute_residual": first_value, "tolerance": FIRST_INTEGRAL_TOL})
        check(receipt["checks"], "finest_L12_amplitudes", amp_pass, {"f_min": finest12.get("f_min"), "f_max": finest12.get("f_max"), "c_min": finest12.get("c_min"), "c_max": finest12.get("c_max")})
        for domain in (9, 12):
            row = finest.get(domain, {})
            passed = bool(row.get("surface_bound_pass", False))
            check(receipt["checks"], f"surface_bounds_L{domain}", passed, {"sigma": row.get("sigma"), "lower": row.get("sigma_lower"), "upper": row.get("sigma_upper"), "absolute_tolerance": SIGMA_EPS})
        sigma9 = finest.get(9, {}).get("sigma")
        sigma12 = finest.get(12, {}).get("sigma")
        if isinstance(sigma9, (int, float)) and isinstance(sigma12, (int, float)) and math.isfinite(float(sigma9)) and math.isfinite(float(sigma12)):
            domain_delta = abs(float(sigma9) - float(sigma12))
            delta_pass = domain_delta < DOMAIN_SIGMA_TOL
            check(receipt["checks"], "L9_L12_surface_cost_difference", delta_pass, {"absolute_difference": domain_delta, "tolerance": DOMAIN_SIGMA_TOL})
        else:
            delta_pass = False
            check(receipt["checks"], "L9_L12_surface_cost_difference", False, "missing finite surface costs")
        receipt["numerical_pass"] = all(item["pass"] for item in receipt["checks"])
        receipt["verdict"] = SUPPORTS if receipt["numerical_pass"] else INCONCLUSIVE
        receipt["failures"] = [item["name"] for item in receipt["checks"] if not item["pass"]]
        receipt["attempts"] = [{"L": row.get("L"), "pass": bool(row.get("pass", False)), "error": row.get("error")} for row in rows]
        if not finite_tree(receipt):
            raise ValueError("receipt contains nonfinite value")
    except Exception as exc:
        receipt["numerical_pass"] = False
        receipt["verdict"] = INCONCLUSIVE
        receipt["failures"].append(f"execution: {type(exc).__name__}: {exc}")
    write_json(output / "results.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, allow_nan=False))
    return 0 if receipt["numerical_pass"] else 1
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--note", type=Path, default=REPORT)
    args = parser.parse_args()
    return run(args.note.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
