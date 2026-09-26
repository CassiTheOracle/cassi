#!/usr/bin/env python3
"""Exact magnetic-bundle and angular identities for notebook section 52.

Run from the repository root after sealing the source manifest:
python computations/matter_formation_magnetic_spin.py --manifest PATH --output FRESH_DIR

This computes conditional angular kinematics and vacuum-section constraints.
It performs no field evolution and supplies no physical particle assignment.
The full_vacuum_compatible column encodes the derived section obstruction;
it is not a separately measured observable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = "## 52. Working notes: magnetic rotation and isolated charged sectors"
MANIFEST_SCHEMA = "matter-formation-magnetic-spin-manifest-v1"
SCHEMA = "matter-formation-magnetic-spin-primary-v1"
SOURCES = {
    "computations/matter_formation_magnetic_spin.py",
    "computations/verify_matter_formation_magnetic_spin.py",
    "foundations/particle-stationary-action-closure.md",
    "foundations/nonabelian-magnetic-core-boundary.md",
}
BUNDLE_INTEGERS = (-4, -2, -1, 0, 1, 2, 4)
PHI = (1 + sp.sqrt(5)) / 2


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def section_bytes(path: Path) -> bytes:
    lines = canonical_bytes(path).decode("utf-8").splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.rstrip() == HEADING]
    if len(matches) != 1:
        raise ValueError("section 52 must occur exactly once")
    first = matches[0]
    last = next((i for i in range(first + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return ("".join(lines[first:last]).rstrip() + "\n").encode("utf-8")


def validate_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    record = manifest["section"]
    if record["path"] != REPORT or record["heading"] != HEADING:
        raise ValueError("unexpected notebook section")
    frozen = canonical_bytes(path.parent / record["snapshot"])
    if hashlib.sha256(frozen).hexdigest() != record["sha256"] or section_bytes(ROOT / REPORT) != frozen:
        raise ValueError("frozen or current section mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {item["path"] for item in sources} != SOURCES:
        raise ValueError("incomplete source bindings")
    for item in sources:
        if sha(ROOT / item["path"]) != item["sha256"] or sha(path.parent / item["snapshot"]) != item["sha256"]:
            raise ValueError(f"source mismatch: {item['path']}")
    review = manifest["mathematical_review"]
    if review.get("accepted") is not True or sha(path.parent / review["snapshot"]) != review["sha256"]:
        raise ValueError("mathematical review is not qualified")
    return manifest


def is_zero(expression: sp.Expr | sp.MatrixBase) -> bool:
    if isinstance(expression, sp.MatrixBase):
        return all(sp.simplify(value) == 0 for value in expression)
    return sp.simplify(expression) == 0


def bundle_identities() -> tuple[dict[str, bool], dict[str, Any]]:
    theta, azimuth = sp.symbols("theta azimuth", real=True)
    nu = sp.symbols("nu", integer=True)
    g = sp.symbols("g", positive=True)
    weight = sp.symbols("weight", real=True)
    north = nu * (1 - sp.cos(theta)) / g
    south = -nu * (1 + sp.cos(theta)) / g
    t3 = sp.diag(sp.Rational(1, 2), -sp.Rational(1, 2))
    transition = sp.diag(sp.exp(sp.I * nu * azimuth), sp.exp(-sp.I * nu * azimuth))
    gauge_shift = -sp.I * transition.diff(azimuth) * transition.conjugate().T / g
    charged_transition = sp.exp(2 * sp.I * nu * weight * azimuth)
    winding = sp.simplify(charged_transition.diff(azimuth) / (sp.I * charged_transition))
    flux = sp.integrate(sp.diff(north, theta), (theta, 0, sp.pi)) * 2 * sp.pi
    checks = {
        "patch_gauge_covariance": is_zero((north - south) * t3 - gauge_shift),
        "matching_patch_curvatures": is_zero(sp.diff(north - south, theta)),
        "flux_normalization": is_zero(flux - 4 * sp.pi * nu / g),
        "charged_transition_winding": is_zero(winding - 2 * nu * weight),
    }
    return checks, {"north_potential": str(north), "south_potential": str(south),
                    "magnetic_flux": str(flux), "line_bundle_winding": str(winding)}


def rotation_identities() -> dict[str, bool]:
    x, azimuth, s = sp.symbols("x azimuth s", real=True)
    factor = 1 - x ** 2
    root = sp.sqrt(factor)
    field = sp.Function("field")(x, azimuth)
    z = (sp.Integer(0), -sp.I, -s)
    plus = tuple(sp.exp(sp.I * azimuth) * value for value in (-root, sp.I * x / root, -s * (1 - x) / root))
    minus = tuple(sp.exp(-sp.I * azimuth) * value for value in (root, sp.I * x / root, -s * (1 - x) / root))

    def apply(operator: tuple[sp.Expr, ...], argument: sp.Expr) -> sp.Expr:
        return operator[0] * sp.diff(argument, x) + operator[1] * sp.diff(argument, azimuth) + operator[2] * argument

    def commutator(left: tuple[sp.Expr, ...], right: tuple[sp.Expr, ...]) -> sp.Expr:
        return apply(left, apply(right, field)) - apply(right, apply(left, field))

    covariant_azimuth = lambda argument: sp.diff(argument, azimuth) - sp.I * s * (1 - x) * argument
    angular = -sp.diff(factor * sp.diff(field, x), x) - covariant_azimuth(covariant_azimuth(field)) / factor
    casimir = apply(z, apply(z, field)) + (apply(plus, apply(minus, field)) + apply(minus, apply(plus, field))) / 2
    return {
        "rotation_z_plus_commutator": is_zero(commutator(z, plus) - apply(plus, field)),
        "rotation_z_minus_commutator": is_zero(commutator(z, minus) + apply(minus, field)),
        "rotation_ladder_commutator": is_zero(commutator(plus, minus) - 2 * apply(z, field)),
        "rotation_covariant_casimir": is_zero(casimir - angular - s ** 2 * field),
    }


def projector_identities() -> tuple[dict[str, bool], list[float], list[dict[str, Any]]]:
    nx, ny, nz, yr, yi, ir, ii = sp.symbols("nx ny nz yr yi ir ii", real=True)
    pauli = (
        sp.Matrix([[0, 1], [1, 0]]),
        sp.Matrix([[0, -sp.I], [sp.I, 0]]),
        sp.diag(1, -1),
    )
    direction = (nx, ny, nz)
    matrix = sum((component * sigma for component, sigma in zip(direction, pauli)), sp.zeros(2))
    unit_constraint = nx ** 2 + ny ** 2 + nz ** 2 - 1
    plus, minus = (sp.eye(2) + matrix) / 2, (sp.eye(2) - matrix) / 2
    psi = sp.Matrix([yr + sp.I * yi, ir + sp.I * ii])
    rho = (psi.conjugate().T * psi)[0]
    projection = sum(component * (psi.conjugate().T * sigma * psi)[0]
                     for component, sigma in zip(direction, pauli))
    eta = sp.simplify((PHI - 1) / (PHI + 1))
    ratios = (sp.simplify((1 + eta) / 2), sp.simplify((1 - eta) / 2))
    checks = {
        "pauli_projector_hermiticity": is_zero(plus - plus.conjugate().T) and is_zero(minus - minus.conjugate().T),
        "pauli_projector_idempotence": is_zero(plus * plus - plus - unit_constraint * sp.eye(2) / 4)
            and is_zero(minus * minus - minus - unit_constraint * sp.eye(2) / 4),
        "pauli_projector_completeness": is_zero(plus + minus - sp.eye(2)),
        "pauli_projector_orthogonality": is_zero(plus * minus + unit_constraint * sp.eye(2) / 4),
        "projected_component_norms": is_zero((psi.conjugate().T * plus * psi)[0] - (rho + projection) / 2)
            and is_zero((psi.conjugate().T * minus * psi)[0] - (rho - projection) / 2),
        "vacuum_composition": is_zero(eta - PHI ** -3),
        "vacuum_projector_ratios": is_zero(ratios[0] - 1 / PHI) and is_zero(ratios[1] - 1 / PHI ** 2),
        "nonzero_vacuum_sections": all(value.is_positive is True for value in ratios),
    }
    controls = []
    for label, density, alignment in (("registered", 1, eta), ("aligned_plus", 1, sp.Integer(1)),
                                      ("aligned_minus", 1, sp.Integer(-1)), ("adjoint_only", 0, eta)):
        norms = [sp.simplify(density * (1 + sign * alignment) / 2) for sign in (1, -1)]
        controls.append({"label": label, "projected_norms_in_reference_density_units": [str(v) for v in norms],
                         "projected_norm_values": [float(v) for v in norms],
                         "nonvanishing_sections": sum(v.is_positive is True for v in norms),
                         "section_obstruction_applies": any(v.is_positive is True for v in norms),
                         "registered_vacuum": label == "registered"})
    return checks, [float(value) for value in ratios], controls


def integrate_polynomial(expression: sp.Expr, variable: sp.Symbol) -> sp.Expr:
    polynomial = sp.Poly(sp.expand(expression), variable)
    return sp.simplify(sum(coefficient * sp.Rational(1 - (-1) ** (power[0] + 1), power[0] + 1)
                           for power, coefficient in polynomial.terms()))


def angular_spectrum() -> tuple[dict[str, bool], list[dict[str, Any]], list[dict[str, Any]]]:
    x = sp.symbols("x", real=True)
    factor = 1 - x ** 2
    rows = []
    for p in BUNDLE_INTEGERS:
        s = sp.Rational(p, 2)
        for twice_m in range(-abs(p) - 4, abs(p) + 5, 2):
            m = sp.Rational(twice_m, 2)
            alpha, beta = abs(m + s), abs(m - s)
            logarithmic_derivative = -alpha / (2 * (1 - x)) + beta / (2 * (1 + x))
            first_coefficient = sp.cancel(2 * x - 2 * factor * logarithmic_derivative)
            zeroth_coefficient = sp.cancel(-factor * (sp.diff(logarithmic_derivative, x) + logarithmic_derivative ** 2)
                                            + 2 * x * logarithmic_derivative + (m + s * x) ** 2 / factor)
            for degree in range(4):
                polynomial = sp.jacobi(degree, alpha, beta, x)
                j = degree + (alpha + beta) / 2
                eigenvalue = j * (j + 1) - s ** 2
                residual = sp.cancel(-factor * sp.diff(polynomial, x, 2)
                                     + first_coefficient * sp.diff(polynomial, x)
                                     + (zeroth_coefficient - eigenvalue) * polynomial)
                norm = integrate_polynomial((1 - x) ** alpha * (1 + x) ** beta * polynomial ** 2, x)
                norm_formula = (2 ** (alpha + beta + 1) * sp.factorial(degree + alpha) * sp.factorial(degree + beta)
                                / ((2 * degree + alpha + beta + 1) * sp.factorial(degree)
                                   * sp.factorial(degree + alpha + beta)))
                coefficients = list(reversed(sp.Poly(polynomial, x).all_coeffs()))
                rows.append({"p": p, "twice_m": twice_m, "k": degree, "twice_j": int(2 * j),
                             "eigenvalue": float(eigenvalue), "exact_eigenvalue": str(eigenvalue),
                             "jacobi_coefficients": [str(value) for value in coefficients],
                             "exact_residual": str(residual), "exact_norm": str(norm),
                             "exact_norm_residual": str(sp.simplify(norm - norm_formula)),
                             "regular_patch_exponents": [int(m + s), int(m - s)],
                             "rotation_phase": int(sp.simplify(sp.exp(-2 * sp.pi * sp.I * m)))})
    bands = []
    for p in BUNDLE_INTEGERS:
        for level in range(3):
            twice_j = abs(p) + 2 * level
            selected = [row for row in rows if row["p"] == p and row["twice_j"] == twice_j]
            measured_m = sorted(row["twice_m"] for row in selected)
            expected_m = list(range(-twice_j, twice_j + 1, 2))
            bands.append({"p": p, "twice_j": twice_j, "multiplicity": len(selected),
                          "expected_multiplicity": twice_j + 1, "twice_m": measured_m,
                          "complete": measured_m == expected_m})
    checks = {
        "complete_symbolic_schedule": len(rows) == 196,
        "covariant_angular_eigenfunctions": all(row["exact_residual"] == "0" for row in rows),
        "weighted_jacobi_norms": all(row["exact_norm_residual"] == "0" and sp.Rational(row["exact_norm"]) > 0 for row in rows),
        "monopole_rotation_character": all(row["rotation_phase"] == (1 if row["p"] % 2 == 0 else -1) for row in rows),
        "complete_low_angular_bands": all(row["complete"] for row in bands),
    }
    return {name: bool(value) for name, value in checks.items()}, rows, bands


def calculate() -> dict[str, Any]:
    patch_checks, patch = bundle_identities()
    projector_checks, ratios, controls = projector_identities()
    angular_checks, rows, bands = angular_spectrum()
    charges = []
    for nu in (-2, -1, 0, 1, 2):
        for twice_t in (-2, -1, 0, 1, 2):
            p = nu * twice_t
            phase = sp.simplify(sp.exp(-sp.I * sp.pi * p))
            charges.append({"nu": nu, "twice_t": twice_t, "p": p, "rotation_phase": int(phase),
                            "full_vacuum_compatible": nu == 0})
    checks = {**patch_checks, **projector_checks, **rotation_identities(), **angular_checks,
              "single_valued_charged_transitions": all(sp.exp(2 * sp.pi * sp.I * row["p"]) == 1 for row in charges),
              "neutral_carrier_integer_rotation": all(row["rotation_phase"] == 1 for row in charges if row["twice_t"] == 0),
              "adjoint_integer_rotation": all(row["rotation_phase"] == 1 for row in charges if row["twice_t"] in (-2, 0, 2))}
    checks = {name: bool(value) for name, value in checks.items()}
    passed = all(checks.values())
    return {"schema": SCHEMA, "numeric_pass": passed, "verdict": "PASS" if passed else "INCONCLUSIVE",
            "checks": checks, "patch": patch, "spectral_rows": rows, "bands": bands,
            "charge_rows": charges, "vacuum_ratios": ratios, "control_rows": controls,
            "scope": "Conditional monopole-bundle angular spectrum and full-vacuum section obstruction; no quantum state, exchange statistics, radial bound state or formation result is supplied.",
            "complete_physical_matter_formation": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    created = False
    try:
        output.mkdir(parents=True, exist_ok=False)
        created = True
        validate_manifest(args.manifest.resolve())
        result = calculate()
        result.update(manifest_sha256=sha(args.manifest.resolve()), source_sha256=sha(SELF))
    except Exception as exc:
        result = {"schema": SCHEMA, "numeric_pass": False, "verdict": "INCONCLUSIVE",
                  "error": f"{type(exc).__name__}: {exc}", "complete_physical_matter_formation": False}
    if created:
        try:
            with (output / "result.json").open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(result, stream, indent=2, allow_nan=False)
                stream.write("\n")
        except Exception as exc:
            result = {"schema": SCHEMA, "numeric_pass": False, "verdict": "INCONCLUSIVE",
                      "error": f"receipt {type(exc).__name__}: {exc}", "complete_physical_matter_formation": False}
    print(json.dumps({"verdict": result["verdict"], "numeric_pass": result["numeric_pass"],
                      "checks": len(result.get("checks", {})), "spectral_rows": len(result.get("spectral_rows", [])),
                      "errors": result.get("error"), "complete_physical_matter_formation": False}, allow_nan=False), flush=True)
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
