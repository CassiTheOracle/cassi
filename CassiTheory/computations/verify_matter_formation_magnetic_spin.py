#!/usr/bin/env python3
"""Independent component-basis qualification of notebook section 52.

Run from the repository root after sealing the source manifest:
python computations/verify_matter_formation_magnetic_spin.py --manifest PATH --input PRIMARY_DIR --output FRESH_DIR

The Legendre recurrence, direct covariant derivatives and generalized eigenvalue
method are independent of the primary Jacobi calculation. No primary module is
imported. This qualifies angular kinematics and the algebraic inputs to the
smooth-vacuum section obstruction; it supplies no radial bound state, exchange
statistics, quantum state or formation dynamics.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import eigh
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
REPORT = "computations/matter-formation-continuum-report.md"
PRIMARY = "computations/matter_formation_magnetic_spin.py"
HEADING = "## 52. Working notes: magnetic rotation and isolated charged sectors"
MANIFEST_SCHEMA = "matter-formation-magnetic-spin-manifest-v1"
PRIMARY_SCHEMA = "matter-formation-magnetic-spin-primary-v1"
SCHEMA = "matter-formation-magnetic-spin-verification-v1"
SUPPORTS = "SUPPORTS-conditional magnetic rotation and isolation boundary"
SOURCES = {PRIMARY, "computations/verify_matter_formation_magnetic_spin.py",
           "foundations/particle-stationary-action-closure.md", "foundations/nonabelian-magnetic-core-boundary.md"}
P_VALUES = (-4, -2, -1, 0, 1, 2, 4)
ORDERS = (16, 24)
CASES = tuple((p, m2) for p in P_VALUES for m2 in range(-abs(p) - 4, abs(p) + 5, 2))
TOL = 1.0e-10
PHI = (1 + sp.sqrt(5)) / 2


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path, *, binary: bool = False) -> str:
    return hashlib.sha256(path.read_bytes() if binary else canonical(path)).hexdigest()


def load(path: Path) -> dict[str, Any]:
    def reject_constant(token: str):
        raise ValueError(f"nonfinite JSON constant: {token}")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    json.dumps(value, allow_nan=False)
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def validate_manifest(path: Path) -> str:
    manifest = load(path)
    require(manifest.get("schema") == MANIFEST_SCHEMA, "unexpected manifest schema")
    section = manifest["section"]
    require(section["path"] == REPORT and section["heading"] == HEADING, "wrong notebook section")
    frozen = canonical(path.parent / section["snapshot"])
    require(hashlib.sha256(frozen).hexdigest() == section["sha256"], "section snapshot hash mismatch")
    lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.rstrip() == HEADING]
    require(len(starts) == 1, "section 52 must occur exactly once")
    first = starts[0]
    last = next((index for index in range(first + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    current = ("".join(lines[first:last]).rstrip() + "\n").encode("utf-8")
    require(current == frozen, "current section differs from frozen section")
    sources = manifest["sources"]
    require(len(sources) == len(SOURCES) and {row["path"] for row in sources} == SOURCES, "wrong source set")
    for source in sources:
        require(digest(ROOT / source["path"]) == source["sha256"], f"live source mismatch: {source['path']}")
        require(digest(path.parent / source["snapshot"]) == source["sha256"], f"snapshot mismatch: {source['path']}")
    review = manifest["mathematical_review"]
    require(review.get("accepted") is True, "mathematical review not accepted")
    require(digest(path.parent / review["snapshot"]) == review["sha256"], "mathematical review hash mismatch")
    return digest(path)


def validate_primary(path: Path, manifest_hash: str) -> dict[str, Any]:
    primary = load(path)
    require(primary.get("schema") == PRIMARY_SCHEMA, "wrong primary schema")
    require(primary.get("manifest_sha256") == manifest_hash, "primary manifest mismatch")
    require(primary.get("source_sha256") == digest(ROOT / PRIMARY), "primary source mismatch")
    require(primary.get("numeric_pass") is True and primary.get("verdict") == "PASS", "primary did not pass")
    require(primary.get("complete_physical_matter_formation") is False, "invalid physical completion flag")
    checks = primary.get("checks")
    require(isinstance(checks, dict) and bool(checks) and all(value is True for value in checks.values()),
            "every primary check must be true")
    expected = {(p, m2, k) for p, m2 in CASES for k in range(4)}
    rows = primary["spectral_rows"]
    by_key = {(row["p"], row["twice_m"], row["k"]): row for row in rows}
    require(len(rows) == len(by_key) == 196 and set(by_key) == expected, "primary spectrum schedule mismatch")
    for (p, m2, k), row in by_key.items():
        j2 = 2 * k + max(abs(m2), abs(p))
        eigenvalue = Fraction(j2 * (j2 + 2) - p * p, 4)
        require(row["twice_j"] == j2, "incorrect primary angular label")
        require(Fraction(row["exact_eigenvalue"]) == eigenvalue, "incorrect exact primary eigenvalue")
        require(abs(row["eigenvalue"] - float(eigenvalue)) / max(1.0, abs(float(eigenvalue))) < TOL,
                "incorrect primary consumer eigenvalue")
        require(Fraction(row["exact_residual"]) == 0 and Fraction(row["exact_norm_residual"]) == 0,
                "primary exact residual is nonzero")
        require(Fraction(row["exact_norm"]) > 0, "primary norm is not positive")
        coefficients = row["jacobi_coefficients"]
        require(len(coefficients) == k + 1 and Fraction(coefficients[-1]) != 0, "invalid Jacobi polynomial degree")
        for coefficient in coefficients:
            Fraction(coefficient)
    charges = primary["charge_rows"]
    charge_keys = {(row["nu"], row["twice_t"]) for row in charges}
    require(len(charges) == len(charge_keys) == 25 and charge_keys == {(nu, t2) for nu in range(-2, 3) for t2 in range(-2, 3)},
            "primary charge schedule mismatch")
    controls = primary["control_rows"]
    require(len(controls) == 4 and {row["label"] for row in controls} == {"registered", "aligned_plus", "aligned_minus", "adjoint_only"},
            "primary control schedule mismatch")
    require(len(primary["vacuum_ratios"]) == 2, "primary vacuum ratios missing")
    return primary


def algebra(primary: dict[str, Any]) -> tuple[dict[str, bool], list[dict[str, Any]], list[dict[str, Any]]]:
    rho, phase = sp.symbols("rho phase", positive=True)
    sigma3 = sp.diag(1, -1)
    plus, minus = (sp.eye(2) + sigma3) / 2, (sp.eye(2) - sigma3) / 2
    controls = {
        "registered": sp.Matrix([sp.sqrt(rho / PHI), sp.exp(sp.I * phase) * sp.sqrt(rho / PHI ** 2)]),
        "aligned_plus": sp.Matrix([sp.sqrt(rho), 0]),
        "aligned_minus": sp.Matrix([0, sp.sqrt(rho)]),
        "adjoint_only": sp.zeros(2, 1),
    }
    check = lambda expression: sp.simplify(expression) == 0
    checks = {"component_projectors": plus * plus == plus and minus * minus == minus and plus * minus == sp.zeros(2),
              "component_resolution": plus + minus == sp.eye(2)}
    projection_rows = []
    primary_controls = {row["label"]: row for row in primary["control_rows"]}
    for name, spinor in controls.items():
        norms = [sp.simplify(((projector * spinor).adjoint() * (projector * spinor))[0] / rho) for projector in (plus, minus)]
        count = sum(norm.is_positive is True for norm in norms)
        compatible = check(sum(norms) - 1) and check(norms[0] - norms[1] - PHI ** -3)
        supplied = primary_controls[name]
        supplied_norms = np.asarray(supplied["projected_norm_values"], dtype=np.float64)
        expected_norms = np.array([float(norm) for norm in norms])
        checks[f"{name}_norms"] = supplied_norms.shape == (2,) and bool(np.isfinite(supplied_norms).all()) and bool(np.max(np.abs(supplied_norms - expected_norms)) < TOL)
        checks[f"{name}_sections"] = supplied["nonvanishing_sections"] == count and supplied["section_obstruction_applies"] is (count > 0)
        checks[f"{name}_vacuum"] = supplied["registered_vacuum"] is bool(compatible)
        projection_rows.append({"label": name, "exact_norms": [str(norm) for norm in norms],
                                "norm_values": expected_norms.tolist(), "nonvanishing_sections": count,
                                "registered_vacuum": bool(compatible)})
        if name == "registered":
            checks["vacuum_composition_exact"] = check(norms[0] + norms[1] - 1) and check(norms[0] - norms[1] - PHI ** -3)
            checks["vacuum_projector_ratios_exact"] = check(norms[0] - (1 + PHI ** -3) / 2) and check(norms[1] - (1 - PHI ** -3) / 2)
            checks["vacuum_ratio_comparison"] = bool(np.max(np.abs(np.asarray(primary["vacuum_ratios"]) - expected_norms)) < TOL)
    theta, azimuth = sp.symbols("theta azimuth", real=True)
    charge_rows = []
    for row in primary["charge_rows"]:
        nu, t2 = row["nu"], row["twice_t"]
        s = sp.Rational(nu * t2, 2)
        north, south = s * (1 - sp.cos(theta)), -s * (1 + sp.cos(theta))
        winding = sp.integrate(north - south, (azimuth, 0, 2 * sp.pi)) / (2 * sp.pi)
        flux = sp.integrate(sp.diff(north, theta), (theta, 0, sp.pi))
        transition_phase = sp.exp(sp.I * sp.pi * winding)
        checks[f"charge_{nu}_{t2}"] = (check(winding - row["p"]) and check(flux - winding)
                                        and check(transition_phase - row["rotation_phase"])
                                        and row["full_vacuum_compatible"] is (nu == 0))
        charge_rows.append({"nu": nu, "twice_t": t2, "p": int(winding), "rotation_phase": int(transition_phase)})
    return {name: bool(value) for name, value in checks.items()}, projection_rows, charge_rows


def legendre_basis(nodes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Independently authored recurrence for P_0..P_3 and their derivatives."""
    values = np.zeros((4, nodes.size), dtype=np.float64)
    derivatives = np.zeros((4, nodes.size), dtype=np.float64)
    values[0], values[1], derivatives[1] = 1.0, nodes, 1.0
    for order in range(1, 3):
        values[order + 1] = ((2 * order + 1) * nodes * values[order] - order * values[order - 1]) / (order + 1)
        derivatives[order + 1] = derivatives[order - 1] + (2 * order + 1) * values[order]
    return values, derivatives


def patch_forms(s: float, m: float, quadrature: tuple) -> tuple[np.ndarray, np.ndarray]:
    nodes, weights, values, derivatives = quadrature
    alpha, beta = abs(m + s), abs(m - s)
    one_minus, one_plus = 1.0 - nodes, 1.0 + nodes
    weight = np.power(one_minus, alpha / 2.0) * np.power(one_plus, beta / 2.0)
    weight_derivative = weight * (-alpha / (2.0 * one_minus) + beta / (2.0 * one_plus))
    basis = weight[None, :] * values
    basis_derivative = weight_derivative[None, :] * values + weight[None, :] * derivatives
    potential = np.square(m + s * nodes) / (1.0 - nodes * nodes)
    mass = (basis * weights) @ basis.T
    gradient = (basis_derivative * (weights * (1.0 - nodes * nodes))) @ basis_derivative.T
    gradient += (basis * (weights * potential)) @ basis.T
    return mass, gradient


def diagnose(mass: np.ndarray, gradient: np.ndarray, vectors: np.ndarray, values: np.ndarray,
             expected: np.ndarray, supplied: np.ndarray) -> dict[str, Any]:
    left, right = gradient @ vectors, (mass @ vectors) * values[None, :]
    return {
        "analytic_errors": (np.abs(values - expected) / np.maximum(1.0, np.abs(expected))).tolist(),
        "primary_errors": (np.abs(values - supplied) / np.maximum(1.0, np.abs(supplied))).tolist(),
        "eigenvector_residuals": (np.linalg.norm(left - right, axis=0) / np.maximum(1.0, np.linalg.norm(left, axis=0) + np.linalg.norm(right, axis=0))).tolist(),
        "mass_orthonormality_error": float(np.max(np.abs(vectors.T @ mass @ vectors - np.eye(4)))),
        "mass_symmetry_error": float(np.max(np.abs(mass - mass.T))) / max(1.0, float(np.max(np.abs(mass)))),
        "gradient_symmetry_error": float(np.max(np.abs(gradient - gradient.T))) / max(1.0, float(np.max(np.abs(gradient)))),
        "mass_min_eigenvalue": float(eigh(mass, eigvals_only=True)[0]),
        "gradient_min_eigenvalue": float(eigh(gradient, eigvals_only=True)[0]),
    }


def calculate(primary: dict[str, Any], output: Path) -> dict[str, Any]:
    checks, projections, charges = algebra(primary)
    primary_rows = {(row["p"], row["twice_m"], row["k"]): row for row in primary["spectral_rows"]}
    quadratures = {}
    for order in ORDERS:
        nodes, weights = np.polynomial.legendre.leggauss(order)
        quadratures[order] = (nodes, weights, *legendre_basis(nodes))
    arrays = {"p": np.empty(98, dtype=np.int64), "twice_m": np.empty(98, dtype=np.int64),
              "quadrature_order": np.empty(98, dtype=np.int64), "mass": np.empty((98, 4, 4)),
              "gradient": np.empty((98, 4, 4)), "eigenvectors": np.empty((98, 4, 4)), "eigenvalues": np.empty((98, 4))}
    rows = []
    for p, m2 in CASES:
        j2 = np.array([2 * k + max(abs(m2), abs(p)) for k in range(4)])
        expected = (j2 * (j2 + 2) - p * p) / 4.0
        supplied = np.array([primary_rows[p, m2, k]["eigenvalue"] for k in range(4)])
        for order in ORDERS:
            mass, gradient = patch_forms(p / 2, m2 / 2, quadratures[order])
            require(bool(np.isfinite(mass).all() and np.isfinite(gradient).all()), "nonfinite component matrix")
            values, vectors = eigh(gradient, mass)
            require(bool(np.isfinite(values).all() and np.isfinite(vectors).all()), "nonfinite eigenpair")
            diagnostics = diagnose(mass, gradient, vectors, values, expected, supplied)
            index = len(rows)
            for name, value in (("p", p), ("twice_m", m2), ("quadrature_order", order),
                                ("mass", mass), ("gradient", gradient), ("eigenvectors", vectors), ("eigenvalues", values)):
                arrays[name][index] = value
            row = {"p": p, "twice_m": m2, "quadrature_order": order, "eigenvalues": values.tolist(), **diagnostics}
            rows.append(row)
            checks[f"spectrum_{index}"] = (all(value < TOL for key in ("analytic_errors", "primary_errors", "eigenvector_residuals") for value in diagnostics[key])
                                             and all(diagnostics[key] < TOL for key in ("mass_orthonormality_error", "mass_symmetry_error", "gradient_symmetry_error"))
                                             and diagnostics["mass_min_eigenvalue"] > 0 and diagnostics["gradient_min_eigenvalue"] >= -TOL)
    require(len(rows) == 98, "incomplete independent spectrum")
    comparisons = []
    for index, (p, m2) in enumerate(CASES):
        first, second = arrays["eigenvalues"][2 * index:2 * index + 2]
        error = float(np.max(np.abs(first - second) / np.maximum(1.0, np.abs(second))))
        comparisons.append({"p": p, "twice_m": m2, "normalized_error": error})
    checks["quadrature_comparisons"] = all(row["normalized_error"] < TOL for row in comparisons)
    bands = []
    for p in P_VALUES:
        for level in range(3):
            j2 = abs(p) + 2 * level
            members = [(m2, k) for case_p, m2 in CASES if case_p == p for k in range(4) if 2 * k + max(abs(m2), abs(p)) == j2]
            expected_m = list(range(-j2, j2 + 1, 2))
            bands.append({"p": p, "twice_j": j2, "multiplicity": len(members), "twice_m": sorted(m2 for m2, _ in members)})
            checks[f"band_{p}_{level}"] = sorted(m2 for m2, _ in members) == expected_m
    primary_bands = {(row["p"], row["twice_j"]): row for row in primary["bands"]}
    require(len(primary["bands"]) == len(primary_bands) == 21, "primary band schedule mismatch")
    checks["primary_band_comparison"] = all(primary_bands[row["p"], row["twice_j"]]["multiplicity"] == row["multiplicity"]
                                              and primary_bands[row["p"], row["twice_j"]]["twice_m"] == row["twice_m"] for row in bands)
    arrays_path = output / "arrays.npz"
    np.savez(arrays_path, **arrays)
    with np.load(arrays_path, allow_pickle=False) as saved:
        require(set(saved.files) == set(arrays), "retained array keys mismatch")
        checks["raw_arrays_retained"] = all(np.array_equal(saved[name], value) for name, value in arrays.items())
        errors = []
        for index, row in enumerate(rows):
            p, m2 = row["p"], row["twice_m"]
            expected = np.array([float(Fraction(primary_rows[p, m2, k]["exact_eigenvalue"])) for k in range(4)])
            supplied = np.array([primary_rows[p, m2, k]["eigenvalue"] for k in range(4)])
            recovered = diagnose(saved["mass"][index], saved["gradient"][index], saved["eigenvectors"][index], saved["eigenvalues"][index], expected, supplied)
            for name, value in recovered.items():
                errors.append(float(np.max(np.abs(np.asarray(value) - row[name]) / np.maximum(1.0, np.abs(row[name])))))
            errors.append(float(np.max(np.abs(saved["eigenvalues"][index] - row["eigenvalues"]))))
        checks["raw_diagnostics_match_rows"] = max(errors) < TOL
    passed = all(checks.values())
    return {"schema": SCHEMA, "numeric_pass": passed, "verdict": SUPPORTS if passed else "INCONCLUSIVE",
            "checks": checks, "spectral_rows": rows, "quadrature_comparisons": comparisons, "band_rows": bands,
            "vacuum_projection_rows": projections, "charge_sector_rows": charges, "arrays_sha256": digest(arrays_path, binary=True),
            "worst_errors": {"analytic_eigenvalue": max(max(row["analytic_errors"]) for row in rows),
                             "primary_eigenvalue": max(max(row["primary_errors"]) for row in rows),
                             "generalized_residual": max(max(row["eigenvector_residuals"]) for row in rows),
                             "mass_orthonormality": max(row["mass_orthonormality_error"] for row in rows),
                             "quadrature_agreement": max(row["normalized_error"] for row in comparisons),
                             "raw_serialized_comparison": max(errors)},
            "complete_physical_matter_formation": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    created = False
    binding = {}
    try:
        output.mkdir(parents=True, exist_ok=False)
        created = True
        manifest_hash = validate_manifest(args.manifest.resolve())
        binding["manifest_sha256"] = manifest_hash
        primary_path = args.input.resolve() / "result.json"
        primary = validate_primary(primary_path, manifest_hash)
        binding["primary_result_sha256"] = digest(primary_path)
        result = calculate(primary, output)
        result.update(binding, source_sha256=digest(SELF))
    except Exception as exc:
        result = {"schema": SCHEMA, "numeric_pass": False, "verdict": "INCONCLUSIVE", **binding,
                  "source_sha256": digest(SELF), "error": f"{type(exc).__name__}: {exc}", "complete_physical_matter_formation": False}
    if created:
        try:
            text = json.dumps(result, indent=2, allow_nan=False) + "\n"
            with (output / "result.json").open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
        except Exception as exc:
            result = {"schema": SCHEMA, "numeric_pass": False, "verdict": "INCONCLUSIVE",
                      "error": f"receipt {type(exc).__name__}: {exc}", "complete_physical_matter_formation": False}
    print(json.dumps({"verdict": result["verdict"], "numeric_pass": result["numeric_pass"],
                      "spectral_rows": len(result.get("spectral_rows", [])), "errors": result.get("error"),
                      "failed_checks": [name for name, value in result.get("checks", {}).items() if value is not True],
                      "complete_physical_matter_formation": False}, allow_nan=False), flush=True)
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
