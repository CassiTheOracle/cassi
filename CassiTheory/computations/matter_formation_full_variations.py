#!/usr/bin/env python3
"""Qualify full gauge variations and the soft-adjoint amplitude obstruction.

Run from the repository root:
    python computations/matter_formation_full_variations.py --output-dir runs/<fresh-name>

This is exact algebra for the declared conditional energy, not a field evolution,
a numerical homotopy calculation, or a physical matter-formation solution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
from pathlib import Path

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "computations/matter-formation-continuum-report.md"
HEADING = "### 20.5 Full-variation algebra: pre-execution criteria"
PROTOCOL_SHA = "71939d995e06933f75fb8d53902a32a1388cbf696f692f9a5bc9b7a9309ca6f2"
SCHEMA = "matter-formation-full-variations-v1"
VERDICT = "SUPPORTS—full-variation identities and the hard-Hopf soft-amplitude obstruction"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frozen_section(note: Path) -> str:
    text = note.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(HEADING) != 1:
        raise ValueError("Frozen full-variation heading must occur exactly once")
    after = text.split(HEADING, 1)[1]
    end = re.search(r"\n#{1,3} ", after)
    return (HEADING + (after[:end.start()] if end else after)).rstrip() + "\n"


def vector(name: str) -> sp.Matrix:
    return sp.Matrix(sp.symbols(f"{name}0:3", real=True))


def reduced(value):
    if isinstance(value, sp.MatrixBase):
        return value.applyfunc(lambda entry: sp.factor(sp.expand(entry)))
    return sp.factor(sp.expand(value))


def group(name: str, identities: dict, predicates: dict | None = None,
          evidence: dict | None = None) -> dict:
    rows = {}
    for key, expression in identities.items():
        residual = reduced(expression)
        values = list(residual) if isinstance(residual, sp.MatrixBase) else [residual]
        rows[key] = {"pass": all(entry == 0 for entry in values), "residual": str(residual)}
    signs = {key: {"pass": value is True or value == sp.true, "value": str(value)}
             for key, value in (predicates or {}).items()}
    return {
        "name": name,
        "pass": all(row["pass"] for row in rows.values())
        and all(row["pass"] for row in signs.values()),
        "identities": rows,
        "predicates": signs,
        "exact_evidence": {key: str(value) for key, value in (evidence or {}).items()},
    }


def exact_checks() -> list[dict]:
    checks = []
    eps = sp.Symbol("epsilon", real=True)
    p, q, gamma, w = sp.symbols("p q gamma w", positive=True)
    c = sp.Symbol("c", real=True)
    a, b, n, xi = (vector(name) for name in ("a", "b", "n", "xi"))
    dn, dxi, axis = (vector(name) for name in ("dn", "dxi", "axis"))
    aj, bj, da_pair, db_pair = (vector(name) for name in ("aj", "bj", "da", "db"))
    un = dn + a.cross(n)
    linear_un = dxi + a.cross(xi) + b.cross(n)
    un_eps = dn + eps * dxi + (a + eps * b).cross(n + eps * xi)
    curvature = da_pair + a.cross(aj)
    curvature_eps = da_pair + eps * db_pair + (a + eps * b).cross(aj + eps * bj)
    linear_f = db_pair + a.cross(bj) - aj.cross(b)
    mass_eps = p * (a + eps * b).dot(a + eps * b)
    gradient_eps = q * un_eps.dot(un_eps)
    magnetic_eps = gamma * curvature_eps.dot(curvature_eps)
    potential_eps = w * (axis.dot(n + eps * xi) - c) ** 2
    u, du, f, fi, fj = (vector(name) for name in ("u", "du", "f", "fi", "fj"))
    scalar_divergence = du.dot(xi) + u.dot(dxi)
    pair_divergence = f.dot(db_pair) + fi.dot(bj) - fj.dot(b)
    pair_euler = (fj + aj.cross(f)).dot(b) - (fi + a.cross(f)).dot(bj)
    fmat = sp.Matrix([[0, *sp.symbols("f01 f02")],
                      [-sp.Symbol("f01"), 0, sp.Symbol("f12")],
                      [-sp.Symbol("f02"), -sp.Symbol("f12"), 0]])
    dbmat = sp.Matrix(3, 3, sp.symbols("dbij0:9"))
    unordered = sum(fmat[i, j] * (dbmat[i, j] - dbmat[j, i])
                    for i in range(3) for j in range(i + 1, 3))
    ordered = sum(fmat[i, j] * dbmat[i, j] for i in range(3) for j in range(3))
    checks.append(group("first_variations", {
        "fundamental_mass": sp.diff(mass_eps, eps).subs(eps, 0) - 2 * p * a.dot(b),
        "covariant_gradient": sp.diff(gradient_eps, eps).subs(eps, 0)
        - 2 * q * un.dot(linear_un),
        "curvature": sp.diff(magnetic_eps, eps).subs(eps, 0)
        - 2 * gamma * curvature.dot(linear_f),
        "composition": sp.diff(potential_eps, eps).subs(eps, 0)
        - 2 * w * (axis.dot(n) - c) * axis.dot(xi),
        "connection_gradient_current": un.dot(b.cross(n)) - b.dot(n.cross(un)),
        "covariant_integration_by_parts": u.dot(dxi + a.cross(xi))
        + (du + a.cross(u)).dot(xi) - scalar_divergence,
        "curvature_pair_integration_by_parts": f.dot(linear_f)
        - pair_divergence - pair_euler,
        "unordered_curvature_sum": unordered - ordered,
        "curvature_index_antisymmetry": fmat + fmat.T,
    }, evidence={"boundary": "compact variations or vanishing surface flux",
                 "potential_axis": "arbitrary vector; e3 in the original target frame"}))

    # A pointwise orthonormal target frame loses no generality: the fixed
    # potential axis is transformed too and remains arbitrary above/below.
    x, y, ux, uy, dx, dy = sp.symbols("x y ux uy dx dy", real=True)
    nn = sp.Matrix([0, 0, 1])
    xx = sp.Matrix([x, y, 0])
    dnn = sp.Matrix([ux, uy, 0])
    dxx = sp.Matrix([dx, dy, -ux * x - uy * y])
    radius = xx.dot(xx)
    dradius = 2 * xx.dot(dxx)
    nn_eps = nn + eps * xx - eps ** 2 * radius * nn / 2
    dnn_eps = dnn + eps * dxx - eps ** 2 * (dradius * nn + radius * dnn) / 2
    d0 = dnn + a.cross(nn)
    d1 = dxx + a.cross(xx) + b.cross(nn)
    geodesic_gradient = dnn_eps + (a + eps * b).cross(nn_eps)
    geodesic_densities = {
        "mass": mass_eps,
        "gradient": q * geodesic_gradient.dot(geodesic_gradient),
        "curvature": magnetic_eps,
        "composition": w * (axis.dot(nn_eps) - c) ** 2,
    }
    expected_quadratics = {
        "mass": p * b.dot(b),
        "gradient": q * (d1.dot(d1) + 2 * d0.dot(b.cross(xx)) - radius * d0.dot(d0)),
        "curvature": gamma * (linear_f.dot(linear_f) + 2 * curvature.dot(b.cross(bj))),
        "composition": w * (axis.dot(xx) ** 2
                            - (axis.dot(nn) - c) * axis.dot(nn) * radius),
    }
    second = {
        "tangent": nn.dot(xx),
        "differentiated_tangency": dnn.dot(xx) + nn.dot(dxx),
        "covariant_tangency": nn.dot(d0),
        "geodesic_norm_first": sp.expand(nn_eps.dot(nn_eps)).coeff(eps, 1),
        "geodesic_norm_second": sp.expand(nn_eps.dot(nn_eps)).coeff(eps, 2),
    }
    for name, density in geodesic_densities.items():
        second[name + "_coefficient"] = sp.expand(density).coeff(eps, 2) - expected_quadratics[name]
        second[name + "_second_derivative"] = (sp.diff(density, eps, 2).subs(eps, 0)
                                               - 2 * expected_quadratics[name])
    checks.append(group("geodesic_second_variation", second,
                        evidence={"meaning": "Q is the epsilon-squared coefficient; d2E=2Q"}))

    length = sp.Symbol("L", positive=True)
    amplitude = sp.Symbol("s", real=True)
    t0, t1, t2, u2, u3, u4, vv = sp.symbols("T0 T1 T2 U2 U3 U4 V", real=True)
    # (integrated coefficient, number of ordinary derivatives, powers of a)
    weights = [(t0, 2, 0), (t1, 1, 1), (t2, 0, 2), (u2, 2, 2),
               (u3, 1, 3), (u4, 0, 4), (vv, 0, 0)]
    scaled = sum(coef * length ** (3 - derivatives - connections) * amplitude ** connections
                 for coef, derivatives, connections in weights)
    stated = length * (t0 + amplitude * t1 + amplitude ** 2 * t2) + (
        amplitude ** 2 * u2 + amplitude ** 3 * u3 + amplitude ** 4 * u4) / length + length ** 3 * vv
    origin = {length: 1, amplitude: 1}
    total_t, total_u, bb = t0 + t1 + t2, u2 + u3 + u4, t1 + 2 * t2
    station_l = total_t - total_u + 3 * vv
    station_s = bb + 2 * u2 + 3 * u3 + 4 * u4
    hessian = sp.hessian(scaled, (length, amplitude)).subs(origin)
    checks.append(group("general_virial_family", {
        "volume_derivative_scaling": scaled - stated,
        "dilation_stationarity": sp.diff(scaled, length).subs(origin) - station_l,
        "connection_stationarity": sp.diff(scaled, amplitude).subs(origin) - station_s,
        "hessian_LL": hessian[0, 0] - (2 * total_u + 6 * vv),
        "hessian_Ls_on_stationarity": hessian[0, 1] - 2 * bb + station_s,
        "hessian_ss": hessian[1, 1] - (2 * t2 + 2 * u2 + 6 * u3 + 12 * u4),
        "dilation_on_stationarity": hessian[0, 0] - (2 * total_t + 12 * vv) + 2 * station_l,
    }, evidence={"scaled_energy": scaled,
                 "admissibility": "whole-space dilation with fixed asymptotic vacuum"}))

    witness = {t0: 1, t1: -1, t2: 1, u2: 113, u3: -209, u4: 100, vv: 1}
    witness_hessian = hessian.subs(witness)
    gram_t = (4 * sp.Rational(4, 5) * t0 * t2 - t1 ** 2).subs(witness)
    gram_u = (4 * u2 * u4 - u3 ** 2).subs(witness)
    checks.append(group("virial_scope_control", {
        "dilation_stationarity": station_l.subs(witness),
        "connection_stationarity": station_s.subs(witness),
    }, {
        "positive_diagonal_coefficients": all(witness[key] > 0 for key in (t0, t2, u2, u4, vv)),
        "strict_gradient_gram": gram_t > 0,
        "strict_curvature_gram": gram_u > 0,
        "positive_first_hessian_minor": witness_hessian[0, 0] > 0,
        "positive_hessian_determinant": witness_hessian.det() > 0,
    }, {"coefficient_tuple": tuple(witness[key] for key in (t0, t1, t2, u2, u3, u4, vv)),
        "gradient_gram_gap": gram_t, "curvature_gram_gap": gram_u,
        "hessian": witness_hessian, "determinant": witness_hessian.det(),
        "scope": "coefficient consistency only; no field realization"}))

    tau = sp.Symbol("tau", real=True)
    kk = 1 - tau
    hh, ni, dh, hb, ab = (vector(name) for name in ("h", "ni", "dh", "hb", "ab"))
    ht = kk * hh + tau * ni
    at, ajt = kk * a, kk * aj
    dt_ht = kk * dh + at.cross(ht)
    ft = kk * da_pair + at.cross(ajt)
    hnorm, pairing, zn = sp.symbols("h_squared h_dot_vacuum h3", real=True)
    general_norm = kk ** 2 * hnorm + 2 * kk * tau * pairing + tau ** 2
    unit_defect = general_norm.subs(hnorm, 1) - 1
    phi = (1 + sp.sqrt(5)) / 2
    phi_c = (phi - 1) / (phi + 1)
    rho0, lambda_phi, lambda_h, vq = sp.symbols("rho0 lambda_phi lambda_h vq", positive=True)
    delta = rho0 * ((1 - phi) + (1 + phi) * zn) / 2
    composition_weight = lambda_phi * rho0 ** 2 * (1 + phi) ** 2 / 8
    hb_loop = kk * hh + tau * hb
    ab_loop = kk * a + tau * ab
    contraction = {
        "phi_composition_ratio": sp.simplify(phi_c - phi ** -3),
        "PA2_scalar": sp.simplify(delta - rho0 * (1 + phi) * (zn - phi_c) / 2),
        "composition_weight": sp.simplify(lambda_phi * delta ** 2 / 2
                                            - composition_weight * (zn - phi_c) ** 2),
        "norm_potential_weight": lambda_h * (vq ** 2 * hnorm - vq ** 2) ** 2 / 4
        - lambda_h * vq ** 4 * (hnorm - 1) ** 2 / 4,
        "covariant_gradient": dt_ht - kk * (dh + a.cross(ni) + kk * a.cross(hh - ni)),
        "nonabelian_curvature": ft - (kk * da_pair + kk ** 2 * a.cross(aj)),
        "curvature_relative_to_initial": ft - (kk * curvature - kk * tau * a.cross(aj)),
        "general_norm": ht.dot(ht) - (kk ** 2 * hh.dot(hh)
                                        + 2 * kk * tau * hh.dot(ni) + tau ** 2 * ni.dot(ni)),
        "unit_norm_defect": unit_defect + 2 * tau * kk * (1 - pairing),
        "composition_contraction": kk * zn + tau * c - c - kk * (zn - c),
        "initial_adjoint": ht.subs(tau, 0) - hh,
        "final_adjoint": ht.subs(tau, 1) - ni,
        "initial_connection": at.subs(tau, 0) - a,
        "final_connection": at.subs(tau, 1),
        "antipodal_midpoint_zero": (ht.subs(dict(zip(hh, -ni)), simultaneous=True)).subs(tau, sp.Rational(1, 2)),
        "based_loop_initial_adjoint": hb_loop.subs(tau, 0) - hh,
        "based_loop_final_adjoint": hb_loop.subs(tau, 1) - hb,
        "based_loop_fixed_adjoint": hb_loop.subs(dict(zip(hh, hb)), simultaneous=True) - hb,
        "based_loop_initial_connection": ab_loop.subs(tau, 0) - a,
        "based_loop_final_connection": ab_loop.subs(tau, 1) - ab,
        "based_loop_fixed_connection": ab_loop.subs(dict(zip(a, ab)), simultaneous=True) - ab,
    }
    checks.append(group("soft_adjoint_contraction", contraction,
                        evidence={"phi_c": sp.simplify(phi_c),
                                  "unit_norm_defect": sp.factor(unit_defect),
                                  "domain": "affine H3; topology established analytically"}))

    eta, cc, offset = sp.symbols("eta c_positive N3_minus_c", positive=True)
    ss, cutoff_gradient, norm_weight = sp.symbols("DN_squared deta_squared u", nonnegative=True)
    zz = sp.Symbol("N3", real=True)
    radial_factor = 1 - eps * eta
    density_difference = q * ((radial_factor ** 2 - 1) * ss + eps ** 2 * cutoff_gradient)
    density_difference += w * ((radial_factor * zz - c) ** 2 - (zz - c) ** 2)
    density_difference += norm_weight * (radial_factor ** 2 - 1) ** 2
    expected_linear = -2 * eta * (q * ss + w * zz * (zz - c))
    expected_second = q * (eta ** 2 * ss + cutoff_gradient) + w * eta ** 2 * zz ** 2 + 4 * norm_weight * eta ** 2
    strictly_signed = expected_linear.subs({zz: cc + offset, c: cc}, simultaneous=True)
    soft_euler_normal = q * ss + w * zz * (zz - c)
    checks.append(group("soft_amplitude_descent", {
        "linear_energy_change": sp.diff(density_difference, eps).subs(eps, 0) - expected_linear,
        "quadratic_energy_change": sp.expand(density_difference).coeff(eps, 2) - expected_second,
        "cubic_norm_change": sp.expand(density_difference).coeff(eps, 3) + 4 * norm_weight * eta ** 3,
        "quartic_norm_change": sp.expand(density_difference).coeff(eps, 4) - norm_weight * eta ** 4,
        "norm_potential_first_derivative": sp.diff(norm_weight * (radial_factor ** 2 - 1) ** 2, eps).subs(eps, 0),
        "full_polynomial_reconstruction": density_difference - (eps * expected_linear + eps ** 2 * expected_second
                                                                  - 4 * norm_weight * eta ** 3 * eps ** 3
                                                                  + norm_weight * eta ** 4 * eps ** 4),
        "normal_Euler_consistency": expected_linear + 2 * eta * soft_euler_normal,
    }, {"strict_descent_where_N3_exceeds_c": strictly_signed.is_negative is True,
        "positive_quadratic_coefficient_on_support": expected_second.subs(zz, cc + offset).is_positive is True,
        "registered_composition_in_zero_one": bool(0 < phi_c < 1)},
        {"linear_coefficient": expected_linear, "quadratic_coefficient": expected_second,
         "strict_sign_parameterization": strictly_signed,
         "scope": "smooth unit nonzero-Hopf field; finite norm penalty; arbitrary fixed connection"}))
    return checks


def run(note: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": SCHEMA, "checks": [], "numerical_pass": False,
               "verdict": "INCONCLUSIVE", "failures": [],
               "program": {"path": str(Path(__file__).resolve().relative_to(ROOT)),
                           "sha256": digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n"))},
               "protocol": {"path": str(note), "heading": HEADING},
               "environment": {"python": platform.python_version(), "sympy": sp.__version__}}
    try:
        protocol = frozen_section(note)
        receipt["protocol"]["sha256"] = digest(protocol.encode("utf-8"))
        if receipt["protocol"]["sha256"] != PROTOCOL_SHA:
            raise ValueError("Frozen full-variation section hash mismatch")
        (output / "protocol.txt").write_text(protocol, encoding="utf-8", newline="\n")
        receipt["checks"] = exact_checks()
        if len(receipt["checks"]) != 6:
            receipt["failures"].append("Frozen six-group schedule mismatch")
        receipt["failures"].extend(row["name"] for row in receipt["checks"] if not row["pass"])
        receipt["numerical_pass"] = not receipt["failures"]
        if receipt["numerical_pass"]:
            receipt["verdict"] = VERDICT
    except Exception as error:
        receipt["failures"].append(f"{type(error).__name__}: {error}")
    with (output / "results.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
    print(json.dumps({"numerical_pass": receipt["numerical_pass"], "verdict": receipt["verdict"],
                      "groups": len(receipt["checks"]),
                      "identities": sum(len(row["identities"]) for row in receipt["checks"]),
                      "predicates": sum(len(row["predicates"]) for row in receipt["checks"]),
                      "failures": receipt["failures"], "receipt": str(output / "results.json")},
                     ensure_ascii=False, allow_nan=False, indent=2))
    return 0 if receipt["numerical_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note", type=Path, default=NOTE)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs/20260907_matter_formation_full_variations")
    args = parser.parse_args()
    return run(args.note.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
