#!/usr/bin/env python3
"""Verify the temporal covariance rank-recovery time jet.

The executable checks the exact covariance-PDE derivatives at t=0 for the
published active rank-deficient control. It does not simulate Brownian paths,
integrate a generic Navier–Stokes trajectory, or claim a uniform Gramian bound.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "turbulence" / "navier-stokes-rank-deficient-temporal-recovery.md"
BOUND_CONTROL_NOTE = (
    ROOT / "turbulence" / "navier-stokes-rank-deficient-stretching.md"
)
PROTOCOL = (
    ROOT
    / "computations"
    / "navier-stokes-rank-deficient-temporal-recovery-prereg.md"
)
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_rank_deficient_temporal_recovery_20260913"
    / "verification.json"
)
EXPECTED_CHECKS = 5
EXPECTED_CHECK_NAMES = (
    "TR1 covariance first jet from rank-deficient source",
    "TR2 covariance second jet from full vorticity transport",
    "TR3 active-point first jet",
    "TR4 active-point second jet",
    "TR5 temporal determinant recovery coefficient",
)
SCHEMA = "cassi.navier-stokes.rank-deficient-temporal-recovery.verification.v1"


class CheckBook:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.failures: list[str] = []

    def record(self, name: str, passed: bool, detail: Any) -> None:
        passed = bool(passed)
        self.checks.append(
            {
                "name": name,
                "passed": passed,
                "detail": stringify(detail),
            }
        )
        if not passed:
            self.failures.append(name)


def stringify(value: Any) -> Any:
    if isinstance(value, sp.MatrixBase):
        return [[stringify(entry) for entry in row] for row in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [stringify(entry) for entry in value]
    if isinstance(value, dict):
        return {str(key): stringify(item) for key, item in value.items()}
    if isinstance(value, sp.Basic):
        return sp.sstr(value)
    return value


def reduce_exact(value: Any) -> Any:
    if isinstance(value, sp.MatrixBase):
        return value.applyfunc(
            lambda entry: sp.factor(
                sp.cancel(sp.trigsimp(sp.expand_trig(sp.simplify(entry))))
            )
        )
    if isinstance(value, sp.Basic):
        return sp.factor(
            sp.cancel(sp.trigsimp(sp.expand_trig(sp.simplify(value))))
        )
    return value


def is_zero(value: Any) -> bool:
    if isinstance(value, sp.MatrixBase):
        return all(entry == 0 for entry in value)
    return value == 0


def curl_of(vector: sp.MatrixBase, coordinates: tuple[sp.Symbol, ...]) -> sp.Matrix:
    x, y, z = coordinates
    return sp.Matrix(
        [
            sp.diff(vector[2], y) - sp.diff(vector[1], z),
            sp.diff(vector[0], z) - sp.diff(vector[2], x),
            sp.diff(vector[1], x) - sp.diff(vector[0], y),
        ]
    )


def directional_derivative(
    velocity: sp.MatrixBase,
    field: sp.MatrixBase,
    coordinates: tuple[sp.Symbol, ...],
) -> sp.Matrix:
    return sp.Matrix(
        [
            sum(
                velocity[index] * sp.diff(component, coordinates[index])
                for index in range(3)
            )
            for component in field
        ]
    )


def matrix_directional_derivative(
    velocity: sp.MatrixBase,
    field: sp.MatrixBase,
    coordinates: tuple[sp.Symbol, ...],
) -> sp.Matrix:
    return field.applyfunc(
        lambda component: sum(
            velocity[index] * sp.diff(component, coordinates[index])
            for index in range(3)
        )
    )


def laplacian(
    field: sp.MatrixBase, coordinates: tuple[sp.Symbol, ...]
) -> sp.Matrix:
    return sp.Matrix(
        [
            sum(sp.diff(component, coordinate, 2) for coordinate in coordinates)
            for component in field
        ]
    )


def matrix_laplacian(
    field: sp.MatrixBase, coordinates: tuple[sp.Symbol, ...]
) -> sp.Matrix:
    return field.applyfunc(
        lambda component: sum(
            sp.diff(component, coordinate, 2) for coordinate in coordinates
        )
    )


def verify_temporal_jet(book: CheckBook, values: dict[str, Any]) -> None:
    x, y, z, nu, t = sp.symbols("x y z nu t", real=True, positive=True)
    coordinates = (x, y, z)
    theta = sp.sin(x) + sp.cos(x) * sp.sin(y)
    velocity = sp.Matrix([-sp.sin(y), 0, theta])
    omega = reduce_exact(curl_of(velocity, coordinates))
    velocity_gradient = velocity.jacobian(coordinates)
    vorticity_gradient = reduce_exact(omega.jacobian(coordinates))
    source = reduce_exact(vorticity_gradient * vorticity_gradient.T)
    omega_t = reduce_exact(
        -directional_derivative(velocity, omega, coordinates)
        + velocity_gradient * omega
        + nu * laplacian(omega, coordinates)
    )
    momentum_rhs = reduce_exact(
        -directional_derivative(velocity, velocity, coordinates)
        + nu * laplacian(velocity, coordinates)
    )
    transport_residual = reduce_exact(
        omega_t - curl_of(momentum_rhs, coordinates)
    )
    q_t = reduce_exact(
        omega_t.jacobian(coordinates) * vorticity_gradient.T
        + vorticity_gradient * omega_t.jacobian(coordinates).T
    )
    r1 = reduce_exact(2 * nu * source)
    r2 = reduce_exact(
        -matrix_directional_derivative(velocity, r1, coordinates)
        + nu * matrix_laplacian(r1, coordinates)
        + velocity_gradient * r1
        + r1 * velocity_gradient.T
        + 2 * nu * q_t
    )

    point = {x: sp.pi / 2, y: 0}
    point_source = reduce_exact(source.subs(point))
    point_r1 = reduce_exact(r1.subs(point))
    point_r2 = reduce_exact(r2.subs(point))
    expected_source = sp.Matrix(
        [[1, -1, 0], [-1, 2, 0], [0, 0, 0]]
    )
    expected_r1 = sp.Matrix(
        [[2 * nu, -2 * nu, 0], [-2 * nu, 4 * nu, 0], [0, 0, 0]]
    )
    expected_r2 = sp.Matrix(
        [
            [8 * nu * (1 - 2 * nu), 2 * nu * (6 * nu - 5), 0],
            [2 * nu * (6 * nu - 5), 4 * nu * (1 - 6 * nu), 0],
            [0, 0, 4 * nu**2],
        ]
    )

    source_determinant = reduce_exact(source.det())
    first_jet_residual = reduce_exact(r1 - 2 * nu * source)
    second_jet_symmetry_residual = reduce_exact(r2 - r2.T)
    second_jet_residual = reduce_exact(point_r2 - expected_r2)
    book.record(
        EXPECTED_CHECK_NAMES[0],
        is_zero(vorticity_gradient[:, 2])
        and source_determinant == 0
        and is_zero(first_jet_residual),
        {
            "source": source,
            "source_third_column": vorticity_gradient[:, 2],
            "source_determinant": source_determinant,
            "first_jet_residual": first_jet_residual,
        },
    )
    book.record(
        EXPECTED_CHECK_NAMES[1],
        is_zero(transport_residual) and is_zero(second_jet_symmetry_residual),
        {
            "vorticity_transport_residual": transport_residual,
            "second_jet_symmetry_residual": second_jet_symmetry_residual,
            "q_time_derivative": q_t,
        },
    )
    book.record(
        EXPECTED_CHECK_NAMES[2],
        point_source == expected_source and point_r1 == expected_r1,
        {
            "point": point,
            "source": point_source,
            "first_jet": point_r1,
            "expected_source": expected_source,
            "expected_first_jet": expected_r1,
        },
    )
    book.record(
        EXPECTED_CHECK_NAMES[3],
        is_zero(second_jet_residual),
        {
            "point": point,
            "second_jet": point_r2,
            "expected_second_jet": expected_r2,
            "second_jet_residual": second_jet_residual,
        },
    )

    jet = point_r1 * t + point_r2 * t**2 / 2
    determinant_polynomial = sp.Poly(sp.expand(jet.det()), t)
    determinant_coefficients = {
        power: reduce_exact(determinant_polynomial.coeff_monomial(t**power))
        for power in range(5)
    }
    leading_coefficient = determinant_coefficients[4]
    book.record(
        EXPECTED_CHECK_NAMES[4],
        all(determinant_coefficients[power] == 0 for power in range(4))
        and leading_coefficient == 8 * nu**4
        and nu.is_positive is True,
        {
            "determinant_coefficients_through_t4": determinant_coefficients,
            "leading_coefficient": leading_coefficient,
            "positive_for_nu_gt_zero": nu.is_positive is True,
        },
    )

    values.update(
        {
            "control": {
                "velocity": velocity,
                "vorticity": omega,
                "vorticity_gradient": vorticity_gradient,
                "source": source,
                "vorticity_time_derivative": omega_t,
            },
            "initial_covariance_jets": {
                "R1": r1,
                "R2": r2,
                "Q_t": q_t,
            },
            "active_point": {
                "coordinates": point,
                "source": point_source,
                "R1": point_r1,
                "R2": point_r2,
                "determinant_coefficients": determinant_coefficients,
            },
        }
    )


def protocol_integrity() -> dict[str, Any]:
    text = PROTOCOL.read_text(encoding="utf-8")
    tags = re.findall(r"\\tag\{(TRS\d+)\}", text)
    expected_tags = [f"TRS{index}" for index in range(1, 10)]
    declared_names = tuple(
        re.findall(r"^\d+\. `([^`]+)`", text, flags=re.MULTILINE)
    )
    return {
        "tag_count": len(tags),
        "unique_tag_count": len(set(tags)),
        "expected_tags": expected_tags,
        "observed_tags": tags,
        "tags_match": tags == expected_tags,
        "declared_check_count": len(declared_names),
        "declared_check_names": declared_names,
        "inventory_names_match": declared_names == EXPECTED_CHECK_NAMES,
    }


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute() -> tuple[dict[str, Any], bool]:
    book = CheckBook()
    values: dict[str, Any] = {}
    verify_temporal_jet(book, values)
    integrity = protocol_integrity()
    note_text = NOTE.read_text(encoding="utf-8").lower()
    bound_note_text = BOUND_CONTROL_NOTE.read_text(encoding="utf-8").lower()
    required_note_anchors = (
        "temporal covariance rank recovery",
        r"8\nu^4t^4",
        "a separate seven-check receipt covers the base-control checks",
        "unresolved",
    )
    required_bound_note_anchors = (
        "active stretching with rank-deficient vorticity gradients",
        "two-and-a-half-dimensional",
        r"\det j_0=0",
    )
    missing_note_anchors = [
        anchor for anchor in required_note_anchors if anchor not in note_text
    ]
    missing_bound_note_anchors = [
        anchor for anchor in required_bound_note_anchors if anchor not in bound_note_text
    ]
    identities = {
        "supplement_note": {
            "path": "CassiTheory/turbulence/navier-stokes-rank-deficient-temporal-recovery.md",
            "sha256": source_hash(NOTE),
        },
        "bound_control_note": {
            "path": "CassiTheory/turbulence/navier-stokes-rank-deficient-stretching.md",
            "sha256": source_hash(BOUND_CONTROL_NOTE),
        },
        "protocol": {
            "path": "CassiTheory/computations/navier-stokes-rank-deficient-temporal-recovery-prereg.md",
            "sha256": source_hash(PROTOCOL),
        },
        "verifier": {
            "path": "CassiTheory/computations/verify_navier_stokes_rank_deficient_temporal_recovery.py",
            "sha256": source_hash(Path(__file__).resolve()),
        },
    }
    checks_ok = len(book.checks) == EXPECTED_CHECKS and not book.failures
    inventory_ok = (
        integrity["declared_check_count"] == EXPECTED_CHECKS
        and integrity["inventory_names_match"]
    )
    sources_ok = (
        not missing_note_anchors
        and not missing_bound_note_anchors
        and integrity["tags_match"]
    )
    success = checks_ok and inventory_ok and sources_ok
    result = {
        "schema": SCHEMA,
        "status": "PASS" if success else "FAIL",
        "expected_check_count": EXPECTED_CHECKS,
        "expected_check_names": EXPECTED_CHECK_NAMES,
        "checks": book.checks,
        "failures": book.failures,
        "inventory_match": inventory_ok,
        "protocol_integrity": integrity,
        "note_integrity": {
            "required_anchors": required_note_anchors,
            "missing_anchors": missing_note_anchors,
        },
        "bound_control_note_integrity": {
            "required_anchors": required_bound_note_anchors,
            "missing_anchors": missing_bound_note_anchors,
        },
        "identities": identities,
        "classifications": {
            "temporal_covariance_rank_recovery_for_active_control": (
                "SUPPORTS" if success else "UNRESOLVED"
            ),
            "instantaneous_full_rank_source_for_bound_control": (
                "CONTRADICTS" if success else "UNRESOLVED"
            ),
            "uniform_accumulated_gramian_lower_bound": "UNRESOLVED",
            "production_relative_recovery_estimate": "UNRESOLVED",
            "arbitrary_data_navier_stokes_regularity": "UNRESOLVED",
        },
        "scope": {
            "trajectory_integration": "NOT_RUN",
            "stochastic_flow_simulation": "NOT_RUN",
            "covariance_pde_time_jet": "EXACT_INITIAL_TIME_JET",
            "control_evolution": "INVARIANT_2.5D_CLASS_BOUND_BY_NOTE",
            "instantaneous_source_determinant": "ZERO_ON_CONTROL_CLASS",
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
        "sympy_version": sp.__version__,
        "python_symbolic_arithmetic": "exact",
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    for key, path in {
        "supplement_note": NOTE,
        "bound_control_note": BOUND_CONTROL_NOTE,
        "protocol": PROTOCOL,
        "verifier": Path(__file__).resolve(),
    }.items():
        (snapshot_dir / f"{key}{path.suffix}").write_bytes(path.read_bytes())
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    passed_count = sum(row["passed"] for row in result["checks"])
    print(f"{passed_count} / {EXPECTED_CHECKS} checks passed")
    print(f"inventory_match: {result['inventory_match']}")
    print(f"protocol_tags_match: {result['protocol_integrity']['tags_match']}")
    print(f"note_anchors_match: {not result['note_integrity']['missing_anchors']}")
    print(
        "bound_control_note_anchors_match: "
        f"{not result['bound_control_note_integrity']['missing_anchors']}"
    )
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
