#!/usr/bin/env python3
"""Verify the frozen Yang–Mills Poincaré-geometry identities and recurrence."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-poincare-geometry-prereg.md"
SOURCE = Path(__file__).resolve()
OUT_DIR = ROOT / "runs" / "yang_mills_poincare_geometry"
OUT_PATH = OUT_DIR / "verification.json"
ALG_TOL = 1.0e-12
FD_TOL = 5.0e-6


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def norm2(a: list[float]) -> float:
    return dot(a, a)


def scale(c: float, a: list[float]) -> list[float]:
    return [c * x for x in a]


def add(a: list[float], b: list[float]) -> list[float]:
    return [x + y for x, y in zip(a, b, strict=True)]


def sub(a: list[float], b: list[float]) -> list[float]:
    return [x - y for x, y in zip(a, b, strict=True)]


def normalize(a: list[float]) -> list[float]:
    n = math.sqrt(norm2(a))
    if n == 0.0:
        raise ValueError("cannot normalize the zero vector")
    return scale(1.0 / n, a)


def tangent(q: list[float], raw: list[float]) -> list[float]:
    return sub(raw, scale(dot(raw, q), q))


def quat_rotation(q: list[float]) -> list[list[float]]:
    """Adjoint action of a unit SU(2) quaternion on its Lie algebra."""
    w, x, y, z = q
    return [
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - w * z), 2.0 * (x * z + w * y)],
        [2.0 * (x * y + w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - w * x)],
        [2.0 * (x * z - w * y), 2.0 * (y * z + w * x), 1.0 - 2.0 * (x * x + y * y)],
    ]


def mat_vec(m: list[list[float]], v: list[float]) -> list[float]:
    return [dot(row, v) for row in m]


def transpose(m: list[list[float]]) -> list[list[float]]:
    return [list(row) for row in zip(*m, strict=True)]


def recurrence(lam: float, lambda_fib: float, kappa: float) -> dict[str, float]:
    a = 1.0 / (2.0 * lam)
    b = kappa / (lam * math.sqrt(lambda_fib))
    d = 2.0 / lambda_fib * (1.0 + kappa * kappa / lam)
    disc = math.sqrt((a - d) ** 2 + 4.0 * b * b)
    c_star = 0.5 * (a + d + disc)
    return {"A": a, "B": b, "D": d, "C_star": c_star, "lower_bound": 1.0 / c_star}


def max_symmetric_eigenvalue(a: float, b: float, d: float) -> float:
    trace = a + d
    determinant = a * d - b * b
    discriminant = max(0.0, trace * trace - 4.0 * determinant)
    return 0.5 * (trace + math.sqrt(discriminant))


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, **details: Any) -> None:
        checks.append({"name": name, "pass": bool(passed), **details})

    spectrum_expected = {
        1.0: [4.0, 9.0, 16.0, 25.0],
        2.0: [1.0, 2.25, 4.0, 6.25],
        5.0: [0.16, 0.36, 0.64, 1.0],
    }
    spectrum_rows: list[dict[str, Any]] = []
    for radius, expected_values in spectrum_expected.items():
        for k, expected in enumerate(expected_values, start=1):
            measured = ((k + 1) / radius) ** 2
            error = abs(measured - expected)
            spectrum_rows.append(
                {"radius": radius, "k": k, "measured": measured, "expected": expected, "abs_error": error}
            )
            check(f"spectrum_R{radius:g}_k{k}", error <= ALG_TOL, abs_error=error)
    link_character_expected = [0.0, 0.75, 2.0, 3.75, 6.0]
    link_character_rows: list[dict[str, Any]] = []
    for n, expected in enumerate(link_character_expected):
        measured = n * (n + 2) / 4.0
        error = abs(measured - expected)
        link_character_rows.append(
            {"n": n, "spin": n / 2.0, "measured": measured, "expected": expected, "abs_error": error}
        )
        check(f"link_character_casimir_n{n}", error <= ALG_TOL, abs_error=error)


    raw_pairs = [
        ([1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 2.0, -1.0]),
        ([-1.0, 0.0, 0.0, 0.0], [0.0, 2.0, -1.0, 0.5]),
        ([1.0, 2.0, 3.0, 4.0], [2.0, -1.0, 0.5, 3.0]),
        ([-2.0, 1.0, -3.0, 0.5], [1.0, 4.0, -2.0, 0.75]),
        ([0.25, -1.0, 0.5, 2.0], [3.0, 0.5, -1.0, 1.0]),
        ([0.0, 1.0, 1.0, 1.0], [2.0, -3.0, 0.5, 1.25]),
    ]
    h_values = [1.0e-3, 5.0e-4, 2.5e-4]
    hessian_rows: list[dict[str, Any]] = []
    max_hessian_error = 0.0
    for pair_index, (q_raw, v_raw) in enumerate(raw_pairs):
        q = normalize(q_raw)
        projected = tangent(q, v_raw)
        if norm2(projected) == 0.0:
            raise AssertionError("frozen tangent sample became zero")
        v = scale(0.5, normalize(projected))
        speed = math.sqrt(norm2(v))
        casimir_norm2 = 4.0 * norm2(v)
        expected = 0.25 * q[0] * casimir_norm2
        for h in h_values:
            direction = scale(1.0 / speed, v)
            q_plus = add(scale(math.cos(speed * h), q), scale(math.sin(speed * h), direction))
            q_minus = add(scale(math.cos(speed * h), q), scale(-math.sin(speed * h), direction))
            w0 = 1.0 - q[0]
            wp = 1.0 - q_plus[0]
            wm = 1.0 - q_minus[0]
            measured = (wp + wm - 2.0 * w0) / (h * h)
            error = abs(measured - expected)
            max_hessian_error = max(max_hessian_error, error)
            hessian_rows.append(
                {
                    "pair": pair_index,
                    "q": q,
                    "v": v,
                    "h": h,
                    "measured": measured,
                    "expected": expected,
                    "casimir_norm2": casimir_norm2,
                    "abs_error": error,
                }
            )
            check(f"wilson_hessian_pair{pair_index}_h{h:.1e}", error <= FD_TOL, abs_error=error)

    geometry_seeds = [
        ([1.0, 0.0, 0.0, 0.0], [1.0, 2.0, -1.0], [-0.5, 1.0, 3.0], [2.0, -1.0, 0.5], [1.0, 0.25, -2.0]),
        ([1.0, 1.0, 0.0, 0.0], [-2.0, 1.0, 0.5], [1.5, -1.0, 2.0], [-0.5, 2.0, 1.0], [3.0, -1.0, 0.25]),
        ([1.0, 2.0, 3.0, 4.0], [0.25, -3.0, 1.0], [2.0, 0.5, -1.5], [1.0, 1.0, -2.0], [-1.0, 0.75, 2.5]),
        ([-2.0, 1.0, -0.5, 3.0], [4.0, -1.0, 0.5], [-2.0, 3.0, 1.0], [0.5, -1.5, 3.0], [2.0, 2.5, -0.5]),
        ([0.0, 1.0, 1.0, 1.0], [-1.0, -2.0, 4.0], [3.0, 0.25, -1.0], [-2.0, 0.5, 1.0], [1.0, -3.0, 2.0]),
        ([0.5, -2.0, 1.0, 0.25], [1.5, 0.5, -2.5], [-0.75, 2.0, 1.25], [3.0, -0.5, -1.0], [-2.0, 1.0, 0.5]),
        ([-1.0, -1.0, 2.0, 0.5], [2.25, -0.75, 1.5], [0.5, 3.0, -2.0], [-1.0, 2.0, 2.0], [0.75, -1.25, 3.5]),
        ([3.0, 0.5, -1.0, 2.0], [-0.5, 1.5, 2.5], [2.0, -2.0, 0.75], [1.25, 0.5, -3.0], [-0.25, 2.5, 1.0]),
    ]
    geometry_rows: list[dict[str, Any]] = []
    max_orthogonality_error = 0.0
    max_energy_error = 0.0
    for index, (q_raw, eta, zeta, p1, p2) in enumerate(geometry_seeds):
        q = normalize(q_raw)
        rotation = quat_rotation(q)
        rotation_inv = transpose(rotation)
        ad_inv_eta = mat_vec(rotation_inv, eta)
        ad_inv_zeta = mat_vec(rotation_inv, zeta)
        h1 = scale(0.5, eta)
        h2 = scale(0.5, ad_inv_eta)
        z1 = zeta
        z2 = scale(-1.0, ad_inv_zeta)
        h_norm2 = norm2(h1) + norm2(h2)
        z_norm2 = norm2(z1) + norm2(z2)
        hz_inner = dot(h1, z1) + dot(h2, z2)
        fixed1 = [0.0, 0.0, 0.0]
        fixed2 = ad_inv_eta
        connection1 = sub(fixed1, h1)
        connection2 = sub(fixed2, h2)
        expected_connection1 = scale(-0.5, eta)
        expected_connection2 = scale(0.5, ad_inv_eta)
        connection_error = math.sqrt(
            norm2(sub(connection1, expected_connection1))
            + norm2(sub(connection2, expected_connection2))
        )
        ad_p2 = mat_vec(rotation, p2)
        grad_h = scale(0.5, add(p1, ad_p2))
        grad_v = sub(p1, ad_p2)
        original_energy = norm2(p1) + norm2(p2)
        reconstructed_energy = 2.0 * norm2(grad_h) + 0.5 * norm2(grad_v)
        orth_error = abs(hz_inner)
        energy_error = abs(original_energy - reconstructed_energy)
        max_orthogonality_error = max(max_orthogonality_error, orth_error)
        max_energy_error = max(max_energy_error, energy_error)
        row = {
            "sample": index,
            "q": q,
            "eta": eta,
            "zeta": zeta,
            "p1": p1,
            "p2": p2,
            "horizontal_norm2": h_norm2,
            "horizontal_expected": 0.5 * norm2(eta),
            "vertical_norm2": z_norm2,
            "vertical_expected": 2.0 * norm2(zeta),
            "orthogonality": hz_inner,
            "connection_error": connection_error,
            "original_energy": original_energy,
            "reconstructed_energy": reconstructed_energy,
        }
        geometry_rows.append(row)
        check(f"horizontal_norm_{index}", abs(h_norm2 - 0.5 * norm2(eta)) <= ALG_TOL)
        check(f"vertical_norm_{index}", abs(z_norm2 - 2.0 * norm2(zeta)) <= ALG_TOL)
        check(f"horizontal_vertical_orthogonality_{index}", orth_error <= ALG_TOL, abs_error=orth_error)
        check(f"fixed_coordinate_connection_{index}", connection_error <= ALG_TOL, abs_error=connection_error)
        check(f"energy_reconstruction_{index}", energy_error <= ALG_TOL, abs_error=energy_error)

    c_minus = 0.5 * (3.0 - math.sqrt(5.0))
    c_plus = 0.5 * (3.0 + math.sqrt(5.0))
    coordinate_samples = [
        (-3.0, 1.0),
        (-1.0, -2.0),
        (0.0, 4.0),
        (1.0, 0.0),
        (2.5, -0.75),
        (math.sqrt(2.0), math.pi),
        (-math.e, math.sqrt(3.0)),
        (5.0, 5.0),
    ]
    coordinate_rows: list[dict[str, Any]] = []
    for x, y in coordinate_samples:
        euclidean = x * x + y * y
        quadratic = x * x - 2.0 * x * y + 2.0 * y * y
        row = {"x": x, "y": y, "euclidean": euclidean, "quadratic": quadratic}
        coordinate_rows.append(row)
        check(f"coordinate_lower_{len(coordinate_rows)-1}", quadratic + ALG_TOL >= c_minus * euclidean)
        check(f"coordinate_upper_{len(coordinate_rows)-1}", quadratic <= c_plus * euclidean + ALG_TOL)
    check("coordinate_trace", abs((c_minus + c_plus) - 3.0) <= ALG_TOL)
    check("coordinate_determinant", abs(c_minus * c_plus - 1.0) <= ALG_TOL)

    recurrence_inputs = [
        (1.0, 4.0, 0.0),
        (0.2, 1.0, 0.0),
        (2.0, 8.0, 0.1),
        (0.5, 3.0, 0.2),
        (5.0, 1.0, 0.4),
        (0.05, 2.0, 0.01),
        (1.5, 6.0, 1.0),
        (0.3, 0.8, 0.5),
    ]
    recurrence_rows: list[dict[str, Any]] = []
    max_recurrence_error = 0.0
    for index, (lam, lambda_fib, kappa) in enumerate(recurrence_inputs):
        row = {
            "lambda_c": lam,
            "lambda_fib": lambda_fib,
            "kappa": kappa,
            **recurrence(lam, lambda_fib, kappa),
        }
        direct = max_symmetric_eigenvalue(row["A"], row["B"], row["D"])
        error = abs(row["C_star"] - direct)
        max_recurrence_error = max(max_recurrence_error, error)
        row["direct_C_star"] = direct
        row["abs_error"] = error
        if kappa == 0.0:
            row["zero_score_expected"] = min(2.0 * lam, lambda_fib / 2.0)
            check(
                f"zero_score_reduction_{index}",
                abs(row["lower_bound"] - row["zero_score_expected"]) <= ALG_TOL,
            )
        recurrence_rows.append(row)
        check(f"recurrence_generalized_eigenvalue_{index}", error <= ALG_TOL, abs_error=error)

    scaling_inputs = [
        (0.01, 0.5, 1.0),
        (0.125, 1.75, 0.3),
        (2.0, 0.2, 4.5),
    ]
    scaling_rows: list[dict[str, Any]] = []
    for index, (a_f, g_f, mass) in enumerate(scaling_inputs):
        a_c = 2.0 * a_f
        g_c = 2.0 * g_f
        r_f = 2.0 * a_f * mass / (g_f * g_f)
        r_c = 2.0 * a_c * mass / (g_c * g_c)
        error = abs(r_c - 0.5 * r_f)
        scaling_rows.append(
            {"a_f": a_f, "g_f": g_f, "mass": mass, "a_c": a_c, "g_c": g_c, "r_f": r_f, "r_c": r_c, "abs_error": error}
        )
        check(f"factor_two_physical_scaling_{index}", error <= ALG_TOL, abs_error=error)

    induction_inputs = [
        {"r_f": 0.1, "lambda_c": 0.05, "lambda_fib": 0.2, "kappa": 0.0, "expected": True},
        {"r_f": 0.1, "lambda_c": 0.06, "lambda_fib": 0.3, "kappa": 0.005, "expected": True},
        {"r_f": 0.1, "lambda_c": 0.05, "lambda_fib": 0.3, "kappa": 0.001, "expected": False},
        {"r_f": 0.1, "lambda_c": 0.06, "lambda_fib": 0.15, "kappa": 0.0, "expected": False},
        {"r_f": 0.1, "lambda_c": 0.07, "lambda_fib": 0.4, "kappa": 0.2, "expected": False},
        {"r_f": 0.04, "lambda_c": 0.03, "lambda_fib": 0.15, "kappa": 0.002, "expected": True},
    ]
    induction_rows: list[dict[str, Any]] = []
    for index, item in enumerate(induction_inputs):
        rec = recurrence(item["lambda_c"], item["lambda_fib"], item["kappa"])
        threshold = 1.0 / item["r_f"]
        scalar_pass = (
            rec["A"] <= threshold + ALG_TOL
            and rec["D"] <= threshold + ALG_TOL
            and rec["B"] ** 2
            <= (threshold - rec["A"]) * (threshold - rec["D"]) + ALG_TOL
        )
        eigen_pass = rec["C_star"] <= threshold + ALG_TOL
        measured = scalar_pass and eigen_pass
        row = {**item, **rec, "threshold": threshold, "scalar_pass": scalar_pass, "eigen_pass": eigen_pass}
        induction_rows.append(row)
        check(f"induction_equivalence_{index}", scalar_pass == eigen_pass)
        check(f"induction_expected_{index}", measured == item["expected"], measured=measured, expected=item["expected"])

    passed = all(item["pass"] for item in checks)
    receipt = {
        "schema": "cassi.yang-mills-poincare-geometry.verification.v1",
        "verdict": "PASS" if passed else "FAIL",
        "protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "protocol_sha256": sha256(PROTOCOL),
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(SOURCE),
        "python": platform.python_version(),
        "tolerances": {"algebraic": ALG_TOL, "finite_difference": FD_TOL},
        "summary": {
            "checks": len(checks),
            "passed": sum(1 for item in checks if item["pass"]),
            "failed": sum(1 for item in checks if not item["pass"]),
            "spectrum_rows": len(spectrum_rows),
            "hessian_rows": len(hessian_rows),
            "geometry_rows": len(geometry_rows),
            "recurrence_rows": len(recurrence_rows),
            "link_character_rows": len(link_character_rows),
            "scaling_rows": len(scaling_rows),
            "induction_rows": len(induction_rows),
            "max_hessian_abs_error": max_hessian_error,
            "max_orthogonality_abs_error": max_orthogonality_error,
            "max_energy_abs_error": max_energy_error,
            "max_recurrence_abs_error": max_recurrence_error,
        },
        "constants": {"c_minus": c_minus, "c_plus": c_plus},
        "spectrum_rows": spectrum_rows,
        "hessian_rows": hessian_rows,
        "geometry_rows": geometry_rows,
        "link_character_rows": link_character_rows,
        "coordinate_rows": coordinate_rows,
        "recurrence_rows": recurrence_rows,
        "scaling_rows": scaling_rows,
        "induction_rows": induction_rows,
        "checks": checks,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": receipt["verdict"], **receipt["summary"]}, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
