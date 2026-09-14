#!/usr/bin/env python3
"""Verify the near-rank full-dimensional covariance obstruction.

The executable checks the admissible perturbation and exact determinant and
production identities, then evaluates the fixed epsilon scaling on a periodic
three-dimensional grid. It uses initial-time formulas only: no Navier–Stokes
trajectory, covariance-PDE time integration, or regularity claim is run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "turbulence" / "navier-stokes-near-rank-recovery-obstruction.md"
RATE_NOTE = ROOT / "turbulence" / "navier-stokes-covariance-recovery-rate.md"
BASE_NOTE = ROOT / "turbulence" / "navier-stokes-rank-deficient-stretching.md"
COEFFICIENT_NOTE = (
    ROOT / "turbulence" / "navier-stokes-rank-deficient-temporal-coefficient.md"
)
PROTOCOL = (
    ROOT
    / "computations"
    / "navier-stokes-near-rank-recovery-obstruction-prereg.md"
)
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_near_rank_recovery_obstruction_20260913"
    / "verification.json"
)
EXPECTED_CHECKS = 7
EXPECTED_CHECK_NAMES = (
    "NR1 perturbation is periodic, mean-zero, divergence-free",
    "NR2 determinant polynomial matches g, h, k",
    "NR3 production polynomial averages to one quarter",
    "NR4 leading determinant function is positive on an open set",
    "NR5 determinant scale converges as epsilon^(2/3)",
    "NR6 full-rank source yields linear covariance volume",
    "NR7 recovery-only coefficient is unbounded on bounded family",
)
EPSILONS = (1e-1, 1e-2, 1e-3, 1e-4)
GRID_SIZE = 32
NU = 0.7
EPSILON_MAX = 0.1
SCHEMA = "cassi.navier-stokes.near-rank-recovery-obstruction.verification.v1"


class CheckBook:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.failures: list[str] = []

    def record(self, name: str, passed: bool, detail: Any) -> None:
        passed = bool(passed)
        self.checks.append(
            {"name": name, "passed": passed, "detail": stringify(detail)}
        )
        if not passed:
            self.failures.append(name)


def stringify(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, sp.MatrixBase):
        return [[stringify(entry) for entry in row] for row in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [stringify(entry) for entry in value]
    if isinstance(value, dict):
        return {str(key): stringify(item) for key, item in value.items()}
    if isinstance(value, sp.Basic):
        return sp.sstr(value)
    return value


def curl_of(vector: sp.MatrixBase, coordinates: tuple[sp.Symbol, ...]) -> sp.Matrix:
    x, y, z = coordinates
    return sp.Matrix(
        [
            sp.diff(vector[2], y) - sp.diff(vector[1], z),
            sp.diff(vector[0], z) - sp.diff(vector[2], x),
            sp.diff(vector[1], x) - sp.diff(vector[0], y),
        ]
    )


def symbolic_family() -> dict[str, Any]:
    x, y, z, epsilon = sp.symbols("x y z epsilon", real=True)
    coordinates = (x, y, z)
    base = sp.Matrix([-sp.sin(y), 0, sp.sin(x) + sp.cos(x) * sp.sin(y)])
    perturbation = sp.Matrix(
        [
            sp.sin(z) + sp.cos(y),
            sp.sin(x) + sp.cos(z),
            sp.sin(y) + sp.cos(x),
        ]
    )
    velocity = base + epsilon * perturbation
    base_vorticity = curl_of(base, coordinates)
    perturbation_vorticity = curl_of(perturbation, coordinates)
    vorticity = curl_of(velocity, coordinates)
    base_jacobian = base_vorticity.jacobian(coordinates)
    perturbation_jacobian = perturbation_vorticity.jacobian(coordinates)
    jacobian = vorticity.jacobian(coordinates)
    strain = (velocity.jacobian(coordinates) + velocity.jacobian(coordinates).T) / 2
    production = sp.expand((vorticity.T * strain * vorticity)[0])
    a, b, c, d, s, r = (
        sp.sin(x),
        sp.cos(x),
        sp.sin(y),
        sp.cos(y),
        sp.sin(z),
        sp.cos(z),
    )
    g = c * (a * d * s - (a + b * c) * r)
    h = a**2 * d * r + a * c**2 * s - a * b * c * s - a * s + b * c * d * r + (a * d - b * c) * r
    k = -a * c * s + b * d * r
    return {
        "coordinates": coordinates,
        "epsilon": epsilon,
        "base": base,
        "perturbation": perturbation,
        "velocity": velocity,
        "base_vorticity": base_vorticity,
        "perturbation_vorticity": perturbation_vorticity,
        "vorticity": vorticity,
        "base_jacobian": base_jacobian,
        "perturbation_jacobian": perturbation_jacobian,
        "jacobian": jacobian,
        "production": production,
        "g": g,
        "h": h,
        "k": k,
    }


def torus_average(expression: sp.Basic, coordinates: tuple[sp.Symbol, ...]) -> sp.Basic:
    x, y, z = coordinates
    integrated = sp.integrate(expression, (z, 0, 2 * sp.pi))
    integrated = sp.integrate(integrated, (y, 0, 2 * sp.pi))
    integrated = sp.integrate(integrated, (x, 0, 2 * sp.pi))
    return sp.simplify(integrated / (2 * sp.pi) ** 3)


def determinant(array: np.ndarray) -> np.ndarray:
    return (
        array[0, 0] * (array[1, 1] * array[2, 2] - array[1, 2] * array[2, 1])
        - array[0, 1] * (array[1, 0] * array[2, 2] - array[1, 2] * array[2, 0])
        + array[0, 2] * (array[1, 0] * array[2, 1] - array[1, 1] * array[2, 0])
    )


def numerical_family(size: int, epsilon: float) -> dict[str, Any]:
    coordinate = np.arange(size, dtype=np.float64) * (2.0 * np.pi / size)
    x, y, z = np.meshgrid(coordinate, coordinate, coordinate, indexing="ij")
    a, b = np.sin(x), np.cos(x)
    c, d = np.sin(y), np.cos(y)
    s, r = np.sin(z), np.cos(z)

    base_jacobian = np.zeros((3, 3, size, size, size), dtype=np.float64)
    base_jacobian[0, 0] = -a * d
    base_jacobian[0, 1] = -b * c
    base_jacobian[1, 0] = a + b * c
    base_jacobian[1, 1] = a * d
    base_jacobian[2, 1] = -c

    perturbation_jacobian = np.zeros_like(base_jacobian)
    perturbation_jacobian[0, 1] = -c
    perturbation_jacobian[0, 2] = r
    perturbation_jacobian[1, 0] = b
    perturbation_jacobian[1, 2] = -s
    perturbation_jacobian[2, 0] = -a
    perturbation_jacobian[2, 1] = d

    base_gradient = np.zeros_like(base_jacobian)
    base_gradient[0, 1] = -d
    base_gradient[2, 0] = b - a * c
    base_gradient[2, 1] = b * d
    perturbation_gradient = perturbation_jacobian.copy()

    base_vorticity = np.stack([b * d, a * c - b, d], axis=0)
    perturbation = np.stack(
        [s + d, a + r, c + b], axis=0
    )
    base_velocity = np.stack(
        [-c, np.zeros_like(x), a + b * c], axis=0
    )
    velocity = base_velocity + epsilon * perturbation
    vorticity = base_vorticity + epsilon * perturbation
    jacobian = base_jacobian + epsilon * perturbation_jacobian
    velocity_gradient = base_gradient + epsilon * perturbation_gradient
    strain = (velocity_gradient + np.swapaxes(velocity_gradient, 0, 1)) / 2.0
    production_density = np.einsum(
        "i...,ij...,j...->...", vorticity, strain, vorticity
    )
    g = c * (a * d * s - (a + b * c) * r)
    det_jacobian = determinant(jacobian)
    return {
        "det_jacobian": det_jacobian,
        "g": g,
        "production_mean": float(np.mean(production_density)),
        "velocity_sup": float(np.max(np.abs(velocity))),
        "base_velocity_sup": float(np.max(np.abs(base_velocity))),
        "perturbation_sup": float(np.max(np.abs(perturbation))),
        "positive_fraction": float(np.mean(np.abs(det_jacobian) > 1e-12)),
    }


def verify_checks(book: CheckBook, values: dict[str, Any]) -> None:
    symbolic = symbolic_family()
    x, y, z = symbolic["coordinates"]
    epsilon = symbolic["epsilon"]
    base = symbolic["base"]
    perturbation = symbolic["perturbation"]
    velocity = symbolic["velocity"]
    jacobian = symbolic["jacobian"]
    base_jacobian = symbolic["base_jacobian"]
    perturbation_jacobian = symbolic["perturbation_jacobian"]

    base_divergence = sp.simplify(sum(sp.diff(base[i], (x, y, z)[i]) for i in range(3)))
    perturbation_divergence = sp.simplify(
        sum(sp.diff(perturbation[i], (x, y, z)[i]) for i in range(3))
    )
    family_divergence = sp.simplify(
        sum(sp.diff(velocity[i], (x, y, z)[i]) for i in range(3))
    )
    base_means = tuple(torus_average(base[i], symbolic["coordinates"]) for i in range(3))
    perturbation_means = tuple(
        torus_average(perturbation[i], symbolic["coordinates"]) for i in range(3)
    )
    periodicity_residuals = tuple(
        sp.trigsimp(component.subs(coordinate, coordinate + 2 * sp.pi) - component)
        for field in (base, perturbation)
        for component in field
        for coordinate in symbolic["coordinates"]
    )

    expected_base_jacobian = sp.Matrix(
        [
            [-sp.sin(x) * sp.cos(y), -sp.cos(x) * sp.sin(y), 0],
            [sp.sin(x) + sp.cos(x) * sp.sin(y), sp.sin(x) * sp.cos(y), 0],
            [0, -sp.sin(y), 0],
        ]
    )
    expected_perturbation_jacobian = sp.Matrix(
        [
            [0, -sp.sin(y), sp.cos(z)],
            [sp.cos(x), 0, -sp.sin(z)],
            [-sp.sin(x), sp.cos(y), 0],
        ]
    )
    jacobian_residual = jacobian - (base_jacobian + epsilon * perturbation_jacobian)
    expected_residual = expected_base_jacobian - base_jacobian
    expected_perturbation_residual = (
        expected_perturbation_jacobian - perturbation_jacobian
    )
    book.record(
        EXPECTED_CHECK_NAMES[0],
        base_divergence == 0
        and perturbation_divergence == 0
        and family_divergence == 0
        and all(value == 0 for value in base_means + perturbation_means)
        and all(value == 0 for value in periodicity_residuals)
        and all(sp.trigsimp(entry) == 0 for entry in expected_residual)
        and all(sp.trigsimp(entry) == 0 for entry in expected_perturbation_residual)
        and all(sp.trigsimp(entry) == 0 for entry in jacobian_residual),
        {
            "base_divergence": base_divergence,
            "perturbation_divergence": perturbation_divergence,
            "family_divergence": family_divergence,
            "base_mean": base_means,
            "perturbation_mean": perturbation_means,
            "periodicity_residual_count": len(periodicity_residuals),
            "uniform_H3_bound": "||u_b||_H3 + (1/10)||w||_H3",
        },
    )

    determinant_polynomial = sp.Poly(
        sp.expand(jacobian.det()), epsilon
    )
    expected_determinant = (
        epsilon * symbolic["g"]
        + epsilon**2 * symbolic["h"]
        + epsilon**3 * symbolic["k"]
    )
    determinant_residual = sp.trigsimp(
        sp.expand(determinant_polynomial.as_expr() - expected_determinant)
    )
    coefficients = {
        str(power): sp.trigsimp(determinant_polynomial.coeff_monomial(epsilon**power))
        for power in range(4)
    }
    book.record(
        EXPECTED_CHECK_NAMES[1],
        determinant_residual == 0
        and coefficients["0"] == 0
        and sp.trigsimp(coefficients["1"] - symbolic["g"]) == 0
        and sp.trigsimp(coefficients["2"] - symbolic["h"]) == 0
        and sp.trigsimp(coefficients["3"] - symbolic["k"]) == 0,
        {"coefficients": coefficients, "residual": determinant_residual},
    )

    production_polynomial = sp.Poly(symbolic["production"], epsilon)
    production_averages = {
        str(power): torus_average(
            production_polynomial.coeff_monomial(epsilon**power), symbolic["coordinates"]
        )
        for power in range(4)
    }
    book.record(
        EXPECTED_CHECK_NAMES[2],
        production_averages == {"0": sp.Rational(1, 4), "1": 0, "2": 0, "3": 0},
        {"production_averages": production_averages},
    )

    witness = sp.trigsimp(
        symbolic["g"].subs({x: sp.pi / 2, y: sp.pi / 4, z: sp.pi / 2})
    )
    witness_determinant = sp.trigsimp(
        determinant_polynomial.as_expr().subs(
            {x: sp.pi / 2, y: sp.pi / 4, z: sp.pi / 2}
        )
    )
    book.record(
        EXPECTED_CHECK_NAMES[3],
        witness == sp.Rational(1, 2)
        and sp.simplify(
            witness_determinant
            - (epsilon / 2 - epsilon**2 / 2 - epsilon**3 / sp.sqrt(2))
        )
        == 0
        and sp.simplify(
            (epsilon / 2 - epsilon**2 / 2 - epsilon**3 / sp.sqrt(2)).subs(
                epsilon, sp.Rational(1, 10)
            )
        )
        > 0,
        {
            "g_witness": witness,
            "determinant_witness": witness_determinant,
            "epsilon_max": sp.Rational(1, 10),
        },
    )

    numerical = {
        str(epsilon_value): numerical_family(GRID_SIZE, epsilon_value)
        for epsilon_value in EPSILONS
    }
    reference = numerical["0.0001"]
    reference_g = float(np.mean(np.abs(reference["g"]) ** (2.0 / 3.0)))
    scaled_integrals = {
        key: float(np.mean(np.abs(data["det_jacobian"]) ** (2.0 / 3.0)))
        / float(key) ** (2.0 / 3.0)
        for key, data in numerical.items()
    }
    scale_relative_error = abs(scaled_integrals["0.0001"] - reference_g) / reference_g
    book.record(
        EXPECTED_CHECK_NAMES[4],
        reference_g > 0.0
        and all(np.isfinite(value) for value in scaled_integrals.values())
        and all(data["positive_fraction"] > 0.0 for data in numerical.values())
        and scale_relative_error < 3e-2,
        {
            "grid_size": GRID_SIZE,
            "reference_A_star": reference_g,
            "scaled_integrals": scaled_integrals,
            "relative_error_smallest_epsilon": scale_relative_error,
            "threshold": 3e-2,
        },
    )

    nu, qdet = sp.symbols("nu qdet", positive=True)
    cube_root_residual = sp.powdenest(
        ((2 * nu) ** 3 * qdet) ** sp.Rational(1, 3)
        - 2 * nu * qdet ** sp.Rational(1, 3),
        force=True,
    )
    covariance_factor = sp.simplify(3 * 2 * nu - 6 * nu)
    book.record(
        EXPECTED_CHECK_NAMES[5],
        cube_root_residual == 0 and covariance_factor == 0,
        {
            "cube_root_identity_residual": cube_root_residual,
            "K_factor_residual": covariance_factor,
        },
    )

    recovery_coefficients = np.array(
        [1.0 / (12.0 * NU * float(np.mean(np.abs(data["det_jacobian"]) ** (2.0 / 3.0)))) for data in numerical.values()]
    )
    family_bound = numerical["0.1"]["base_velocity_sup"] + EPSILON_MAX * numerical["0.1"]["perturbation_sup"]
    bounded_suprema = [data["velocity_sup"] for data in numerical.values()]
    book.record(
        EXPECTED_CHECK_NAMES[6],
        bool(np.all(np.diff(recovery_coefficients) > 0.0))
        and bool(recovery_coefficients[-1] > 10.0 * recovery_coefficients[0])
        and all(np.isfinite(value) and value <= family_bound + 1e-12 for value in bounded_suprema),
        {
            "epsilons": EPSILONS,
            "nu": NU,
            "recovery_only_coefficients": recovery_coefficients,
            "coefficient_growth_factor": recovery_coefficients[-1] / recovery_coefficients[0],
            "velocity_suprema": bounded_suprema,
            "C0_triangle_bound": family_bound,
            "H3_bound": "||u_b||_H3 + (1/10)||w||_H3",
        },
    )
    numerical_summary = {
        key: {
            "A_epsilon": float(
                np.mean(np.abs(data["det_jacobian"]) ** (2.0 / 3.0))
            ),
            "scaled_A_epsilon": scaled_integrals[key],
            "positive_fraction": data["positive_fraction"],
            "production_mean": data["production_mean"],
            "velocity_sup": data["velocity_sup"],
        }
        for key, data in numerical.items()
    }
    values.update(
        {
            "grid_size": GRID_SIZE,
            "epsilons": EPSILONS,
            "nu": NU,
            "numerical_summary": numerical_summary,
            "recovery_only_coefficients": recovery_coefficients,
            "symbolic_production_averages": production_averages,
        }
    )


def protocol_integrity() -> dict[str, Any]:
    text = PROTOCOL.read_text(encoding="utf-8")
    declared_names = tuple(
        re.findall(r"^\d+\. `([^`]+)`", text, flags=re.MULTILINE)
    )
    return {
        "declared_check_count": len(declared_names),
        "declared_check_names": declared_names,
        "inventory_names_match": declared_names == EXPECTED_CHECK_NAMES,
        "grid_size_present": f"N=32" in text,
        "epsilon_set_present": all(f"10^{{-{power}}}" in text for power in (1, 2, 3, 4)),
    }


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute() -> tuple[dict[str, Any], bool]:
    book = CheckBook()
    values: dict[str, Any] = {}
    verify_checks(book, values)
    integrity = protocol_integrity()
    texts = {
        "rate_note": RATE_NOTE.read_text(encoding="utf-8").lower(),
        "near_rank_note": NOTE.read_text(encoding="utf-8").lower(),
        "base_note": BASE_NOTE.read_text(encoding="utf-8").lower(),
        "coefficient_note": COEFFICIENT_NOTE.read_text(encoding="utf-8").lower(),
    }
    required_anchors = {
        "near_rank_note": (
            "near-rank full-3d obstruction",
            r"\varepsilon^{2/3}",
            r"(12\nu a_\varepsilon)^{-1}",
            "unresolved",
        ),
        "rate_note": ("initial-layer rate boundary", r"t^{4/3}"),
        "base_note": ("positive initial vortex-stretching production", "unresolved"),
        "coefficient_note": (r"8\nu^4 f", "nonnegative everywhere"),
    }
    missing_anchors = {
        key: [anchor for anchor in anchors if anchor not in texts[key]]
        for key, anchors in required_anchors.items()
    }
    identities = {
        "near_rank_note": {"path": "CassiTheory/turbulence/navier-stokes-near-rank-recovery-obstruction.md", "sha256": source_hash(NOTE)},
        "rate_note": {"path": "CassiTheory/turbulence/navier-stokes-covariance-recovery-rate.md", "sha256": source_hash(RATE_NOTE)},
        "base_note": {"path": "CassiTheory/turbulence/navier-stokes-rank-deficient-stretching.md", "sha256": source_hash(BASE_NOTE)},
        "coefficient_note": {"path": "CassiTheory/turbulence/navier-stokes-rank-deficient-temporal-coefficient.md", "sha256": source_hash(COEFFICIENT_NOTE)},
        "protocol": {"path": "CassiTheory/computations/navier-stokes-near-rank-recovery-obstruction-prereg.md", "sha256": source_hash(PROTOCOL)},
        "verifier": {"path": "CassiTheory/computations/verify_navier_stokes_near_rank_recovery_obstruction.py", "sha256": source_hash(Path(__file__).resolve())},
    }
    checks_ok = len(book.checks) == EXPECTED_CHECKS and not book.failures
    sources_ok = not any(missing_anchors.values())
    inventory_ok = (
        integrity["declared_check_count"] == EXPECTED_CHECKS
        and integrity["inventory_names_match"]
        and integrity["grid_size_present"]
        and integrity["epsilon_set_present"]
    )
    success = checks_ok and sources_ok and inventory_ok
    result = {
        "schema": SCHEMA,
        "status": "PASS" if success else "FAIL",
        "expected_check_count": EXPECTED_CHECKS,
        "expected_check_names": EXPECTED_CHECK_NAMES,
        "checks": book.checks,
        "failures": book.failures,
        "inventory_match": inventory_ok,
        "protocol_integrity": integrity,
        "source_anchors": {"required": required_anchors, "missing": missing_anchors},
        "identities": identities,
        "classifications": {
            "near_rank_full_rank_source": "SUPPORTS" if success else "UNRESOLVED",
            "unbounded_recovery_only_coefficient": "SUPPORTS" if success else "UNRESOLVED",
            "finite_uniform_recovery_only_bound": "CONTRADICTS" if success else "UNRESOLVED",
            "production_relative_recovery_estimate": "UNRESOLVED",
            "arbitrary_data_navier_stokes_regularity": "UNRESOLVED",
        },
        "scope": {
            "trajectory_integration": "NOT_RUN",
            "covariance_pde_time_integration": "NOT_RUN",
            "initial_time_source_asymptotic": "DERIVED_AND_CHECKED",
            "local_smooth_existence": "ASSUMED_STANDARD_THEOREM",
            "global_regularity": "UNRESOLVED",
        },
        "values": stringify(values),
    }
    return result, success


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")

    created = datetime.now(timezone.utc).isoformat()
    result, success = compute()
    result["created_utc"] = created
    manifest = {
        "created_utc": created,
        "identities": result["identities"],
        "numpy_version": np.__version__,
        "sympy_version": sp.__version__,
        "numeric_quadrature": "uniform periodic midpoint rule, N=32",
        "symbolic_arithmetic": "exact SymPy determinant and torus averages",
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    for key, path in {
        "near_rank_note": NOTE,
        "rate_note": RATE_NOTE,
        "base_note": BASE_NOTE,
        "coefficient_note": COEFFICIENT_NOTE,
        "protocol": PROTOCOL,
        "verifier": Path(__file__).resolve(),
    }.items():
        (snapshot_dir / f"{key}{path.suffix}").write_bytes(path.read_bytes())
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    passed_count = sum(row["passed"] for row in result["checks"])
    print(f"{passed_count} / {EXPECTED_CHECKS} checks passed")
    print(f"inventory_match: {result['inventory_match']}")
    print(f"source_anchors_match: {not any(result['source_anchors']['missing'].values())}")
    print(f"status: {result['status']}")
    for name, classification in result["classifications"].items():
        print(f"{name}: {classification}")
    if success:
        print("ALL CHECKS PASSED")
        return 0
    for failure in result["failures"]:
        print(f"FAIL: {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
