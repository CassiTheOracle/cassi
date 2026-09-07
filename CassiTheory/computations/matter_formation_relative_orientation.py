#!/usr/bin/env python3
"""Qualify exact relative-orientation and screening boundaries of the gauge energy.

Run from the repository root:
python computations/matter_formation_relative_orientation.py --output-dir runs/<fresh-name>

The eight algebra groups and their interpretation are frozen in working-record
section 19.5. This program performs no field relaxation or physical parameter fit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "computations/matter-formation-continuum-report.md"
HEADING = "### 19.5 Relative-orientation algebra: pre-execution criteria\n"
PROTOCOL_SHA = "a78ae4c50977abcdd5803b94bfefa00eeb5bdfe542db492441af508c675c2c7c"
VERDICT = "SUPPORTS—relative-target, screening-scale and collapse boundaries of the declared fixed-norm gauge energy"
SIGMA = (
    sp.Matrix([[0, 1], [1, 0]]),
    sp.Matrix([[0, -sp.I], [sp.I, 0]]),
    sp.Matrix([[1, 0], [0, -1]]),
)
IDENTITY = sp.eye(2)
E1 = sp.Matrix([1, 0])


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frozen_section(note: Path) -> str:
    text = note.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(HEADING) != 1:
        raise ValueError("exactly one frozen heading is required")
    after = text.split(HEADING, 1)[1]
    end = re.search(r"\n#{1,3} ", after)
    return (HEADING + (after[:end.start()] if end else after)).rstrip() + "\n"


def reduce_exact(expression):
    if isinstance(expression, sp.MatrixBase):
        return expression.applyfunc(lambda value: sp.factor(sp.cancel(value)))
    return sp.factor(sp.cancel(expression))


def is_zero(expression) -> bool:
    result = reduce_exact(expression)
    if isinstance(result, sp.MatrixBase):
        return all(value == 0 for value in result)
    return result == 0


def spin_matrix(vector):
    return sum((value * matrix for value, matrix in zip(vector, SIGMA)), sp.zeros(2))


def representative(z):
    return sp.Matrix([[z[0], -sp.conjugate(z[1])], [z[1], sp.conjugate(z[0])]])


def exact_checks() -> list[dict]:
    checks = []

    def group(name: str, residuals: dict, predicates: dict, evidence: dict) -> None:
        reduced = {key: reduce_exact(value) for key, value in residuals.items()}
        zero_flags = {key: is_zero(value) for key, value in reduced.items()}
        flags = {key: bool(value) for key, value in predicates.items()}
        checks.append({
            "name": name,
            "pass": all(zero_flags.values()) and all(flags.values()),
            "identities": {key: {"pass": zero_flags[key], "residual": str(value)}
                           for key, value in reduced.items()},
            "predicates": flags,
            "exact_evidence": {key: str(value) for key, value in evidence.items()},
        })

    zr = sp.symbols("zr0:4", real=True)
    hr = sp.symbols("hr0:4", real=True)
    z = sp.Matrix([zr[0] + sp.I * zr[1], zr[2] + sp.I * zr[3]])
    h = representative(sp.Matrix([hr[0] + sp.I * hr[1], hr[2] + sp.I * hr[3]]))
    gz = representative(z)
    znorm = sum(value**2 for value in zr)
    hnorm = sum(value**2 for value in hr)
    group("doublet_representative", {
        "gram": gz.H * gz - znorm * IDENTITY,
        "determinant": gz.det() - znorm,
        "equivariance": representative(h * z) - h * gz,
    }, {}, {"normalized_target": "znorm=1 gives SU(2)", "first_column": gz * E1})

    n = sp.Matrix(sp.symbols("n0:3", real=True))
    nmat = spin_matrix(n)
    relative = gz.H * nmat * gz
    transformed = representative(h * z).H * (h * nmat * h.H) * representative(h * z)
    phi = (1 + sp.sqrt(5)) / 2
    cphi = sp.simplify((phi - 1) / (phi + 1))
    group("relative_quotient", {
        "gauge_invariance_with_norm_factors": transformed - hnorm**2 * relative,
        "traceless": sp.trace(relative),
        "relative_norm": relative * relative - znorm**2 * n.dot(n) * IDENTITY,
        "third_component": sp.trace(SIGMA[2] * relative) / 2 - (z.H * nmat * z)[0],
        "global_section": representative(E1).H * nmat * representative(E1) - nmat,
        "composition_minimum": cphi - phi**-3,
    }, {}, {"unit_norm_assumptions": "znorm=hnorm=n.dot(n)=1",
            "quotient_section": "(e1,N)", "vacuum_latitude": cphi})

    xyz = sp.Matrix(sp.symbols("x y z", real=True))
    radius2 = xyz.dot(xyz)
    rational_h = ((radius2 - 1) * IDENTITY + 2 * sp.I * spin_matrix(xyz)) / (radius2 + 1)
    connection = [reduce_exact(-sp.I * rational_h.diff(coord) * rational_h.H) for coord in xyz]
    c, d = sp.symbols("c d", real=True)
    reference_adjoint = c * SIGMA[2] + d * SIGMA[0]
    psi = rational_h * E1
    adjoint = reduce_exact(rational_h * reference_adjoint * rational_h.H)
    screening = {
        "unitarity": rational_h.H * rational_h - IDENTITY,
        "fundamental_section": representative(psi) - rational_h,
        "constant_relative_matrix": representative(psi).H * adjoint * representative(psi) - reference_adjoint,
        "outer_distance": sp.trace((rational_h - IDENTITY).H * (rational_h - IDENTITY)) - 8 / (1 + radius2),
    }
    for i, coord in enumerate(xyz):
        screening[f"Dpsi_{i}"] = psi.diff(coord) - sp.I * connection[i] * psi
        screening[f"Dphi_{i}"] = adjoint.diff(coord) - sp.I * (connection[i] * adjoint - adjoint * connection[i])
        for j in range(i + 1, 3):
            screening[f"F_{i}{j}"] = (connection[j].diff(coord) - connection[i].diff(xyz[j])
                                      - sp.I * (connection[i] * connection[j] - connection[j] * connection[i]))
    origin = dict.fromkeys(xyz, 0)
    ordinary_cost = sp.simplify(sum((psi.diff(coord).H * psi.diff(coord))[0] for coord in xyz).subs(origin))
    group("joint_gauge_screening", screening, {"omitted_connection_cost_positive": ordinary_cost > 0},
          {"ordinary_gradient_cost_at_origin": ordinary_cost,
           "outer_matrix_distance_squared": 8 / (1 + radius2),
           "relative_field": reference_adjoint})

    p, q, gamma = sp.symbols("p q gamma", positive=True)
    t = sp.symbols("t", positive=True)
    av = sp.Matrix(sp.symbols("a0:3", real=True))
    v1, v2, u1, u2 = sp.symbols("v1 v2 u1 u2", real=True)
    unit = sp.Matrix([0, 0, 1])
    tangent = sp.Matrix([v1, v2, 0])
    covariant = tangent + av.cross(unit)
    quadratic = p * av.dot(av) + q * covariant.dot(covariant)
    solved = sp.solve([sp.diff(quadratic, component) for component in av], list(av), dict=True)[0]
    solved_vector = sp.Matrix([solved[component] for component in av])
    stiffness = sp.hessian(quadratic, list(av)) / 2
    alpha = p * q / (p + q)
    rho = sp.symbols("rho", positive=True)
    dpsi = -sp.I * spin_matrix(av) * sp.sqrt(rho) * E1 / 2
    group("algebraic_connection_elimination", {
        "stationary_connection": solved_vector + q / (p + q) * unit.cross(tangent),
        "effective_gradient": quadratic.subs(solved) - alpha * tangent.dot(tangent),
        "quadratic_stiffness": stiffness - sp.diag(p + q, p + q, p),
        "fundamental_generator_normalization": (dpsi.H * dpsi)[0] - rho * av.dot(av) / 4,
    }, {}, {"connection": solved_vector, "alpha": alpha,
            "screening_masses_squared": (p / gamma, (p + q) / gamma)})

    other = sp.Matrix([u1, u2, 0])
    hij = unit.dot(tangent.cross(other))
    derivative_piece = -2 * t * tangent.cross(other)
    commutator_piece = t**2 * unit.cross(tangent).cross(unit.cross(other))
    curvature = derivative_piece + commutator_piece
    wrong_residual = reduce_exact(derivative_piece - curvature)
    group("induced_curvature", {
        "curvature_coefficient": curvature + t * (2 - t) * unit * hij,
        "curvature_square": curvature.dot(curvature) - t**2 * (2 - t)**2 * hij**2,
    }, {"omitted_commutator_rejected": not is_zero(wrong_residual)},
          {"derivative_piece": derivative_piece, "commutator_piece": commutator_piece,
           "omission_residual": wrong_residual})

    length, A, B = sp.symbols("L A B", positive=True)
    E2, E4, V = sp.symbols("E2 E4 V", nonnegative=True)
    local_scale = length * E2 + E4 / length + length**3 * V
    virial = sp.diff(local_scale, length).subs(length, 1)
    stationary_b = sp.solve(sp.Eq(gamma * t**2 * (2 - t)**2 * B, p * t * A + 3 * V), B)[0]
    ratio_squared = sp.factor(gamma * stationary_b / (p * A))
    ratio_gap = 3 * V / (p * A * t**2 * (2 - t)**2)
    envelope = (t - sp.Rational(2, 3))**2 * (sp.Rational(8, 3) - t)
    group("screening_scale_boundary", {
        "dilation_identity": virial - (E2 - E4 + 3 * V),
        "ratio_lower_bound_gap": ratio_squared - 1 / (t * (2 - t)**2) - ratio_gap,
        "stiffness_envelope": sp.Rational(32, 27) - t * (2 - t)**2 - envelope,
        "envelope_saturation": (t * (2 - t)**2).subs(t, sp.Rational(2, 3)) - sp.Rational(32, 27),
    }, {}, {"ratio_squared": ratio_squared, "nonnegative_gap_for_0_t_1": ratio_gap,
            "envelope_for_0_t_1": envelope,
            "minimum_inverse_length_ratio": sp.sqrt(sp.Rational(27, 32))})

    derivative_order = sp.symbols("derivative_order", integer=True, nonnegative=True)
    measure_gradient_weight = length**3 * (1 / length)**(2 * derivative_order)
    collapse_weights = [measure_gradient_weight.subs(derivative_order, order) for order in (1, 0)]
    collapse_energy = sum(coefficient * weight for coefficient, weight in zip((q * A, V), collapse_weights))
    collapse_slope = sp.diff(collapse_energy, length)
    group("full_energy_collapse", {
        "gradient_weight": collapse_weights[0] - length,
        "potential_weight": collapse_weights[1] - length**3,
        "zero_energy_infimum": sp.limit(collapse_energy, length, 0, dir="+"),
        "scaling_derivative": collapse_slope - (q * A + 3 * V * length**2),
    }, {"strict_increasing_size": collapse_slope.is_positive is True},
          {"energy": collapse_energy, "derivative": collapse_slope,
           "boundary": "each L>0 is smooth; the singular L=0 limit is excluded"})

    x, s, kappa = sp.symbols("x s kappa", positive=True)
    M = s**2 - 2 * t * s + t
    F = s**2 * (2 - s)**2
    energy = x * M + F / x + kappa * x**3
    tw, sw = sp.Rational(99, 100), sp.Rational(19, 20)
    point = {t: tw, s: sw}
    x2 = sp.factor((-sp.diff(F, s) / sp.diff(M, s)).subs(point))
    kw = sp.factor(((F - M * x2) / (3 * x2**2)).subs(point))
    point.update({x: sp.sqrt(x2), kappa: kw})
    gradient = sp.Matrix([sp.diff(energy, coordinate) for coordinate in (x, s)])
    hessian = sp.simplify(sp.hessian(energy, (x, s)).subs(point))
    principal1 = sp.simplify(hessian[0, 0])
    determinant = sp.factor(hessian.det())
    generalized_connection_energy = quadratic.subs(dict(zip(av, -s * unit.cross(tangent))))
    group("two_coordinate_metastability_scope", {
        "connection_family_gradient": generalized_connection_energy - (p + q) * M.subs(t, q / (p + q)) * tangent.dot(tangent),
        "stationary_gradient": gradient.subs(point),
        "collapse_family": energy.subs(s, 0) - (t * x + kappa * x**3),
    }, {"positive_size_squared": x2 > 0, "positive_composition_coefficient": kw > 0,
        "first_hessian_minor_positive": principal1 > 0, "hessian_determinant_positive": determinant > 0},
          {"t": tw, "s": sw, "x_squared": x2, "kappa": kw,
           "hessian": hessian, "first_principal_minor": principal1, "determinant": determinant,
           "scope": "two-coordinate trial minimum only; no field equation or full stability qualification"})
    return checks


def run(note: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "matter-formation-relative-orientation-v1", "checks": [],
               "numerical_pass": False, "verdict": "INCONCLUSIVE", "failures": [],
               "identities": {}, "environment": {"sympy": sp.__version__}}
    try:
        section = frozen_section(note)
        section_sha = digest(section.encode("utf-8"))
        if section_sha != PROTOCOL_SHA:
            raise ValueError("frozen relative-orientation section hash mismatch")
        receipt["identities"] = {
            "program": {"path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
                        "sha256": digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n"))},
            "protocol": {"path": note.relative_to(ROOT).as_posix(), "heading": HEADING.strip(),
                         "sha256": section_sha},
        }
        with (output / "protocol.txt").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(section)
        receipt["checks"] = exact_checks()
        receipt["failures"] = [row["name"] for row in receipt["checks"] if not row["pass"]]
        if len(receipt["checks"]) != 8:
            receipt["failures"].append("frozen exact-check count mismatch")
        receipt["numerical_pass"] = not receipt["failures"]
        if receipt["numerical_pass"]:
            receipt["verdict"] = VERDICT
    except Exception as error:
        receipt["failures"].append(f"{type(error).__name__}: {error}")
    with (output / "results.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps(receipt, ensure_ascii=False, allow_nan=False))
    return 0 if receipt["numerical_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note", type=Path, default=NOTE)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "runs/20260906_matter_formation_relative_orientation")
    args = parser.parse_args()
    return run(args.note.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
