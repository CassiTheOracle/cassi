#!/usr/bin/env python3
"""Verify the global sign of an active temporal covariance coefficient.

The executable reconstructs explicit vorticity-gradient source vectors, forms
the exact covariance-PDE time jet, and checks the first determinant coefficient
and its sum-of-squares reduction. It does not integrate a Navier–Stokes
trajectory, simulate stochastic paths, or claim a uniform continuation bound.
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
NOTE = ROOT / "turbulence" / "navier-stokes-rank-deficient-temporal-coefficient.md"
BOUND_TEMPORAL_NOTE = (
    ROOT / "turbulence" / "navier-stokes-rank-deficient-temporal-recovery.md"
)
BOUND_CONTROL_NOTE = (
    ROOT / "turbulence" / "navier-stokes-rank-deficient-stretching.md"
)
PROTOCOL = (
    ROOT
    / "computations"
    / "navier-stokes-rank-deficient-temporal-coefficient-prereg.md"
)
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_rank_deficient_temporal_coefficient_20260913"
    / "verification.json"
)
EXPECTED_CHECKS = 6
EXPECTED_CHECK_NAMES = (
    "GC1 source-vector outer products and dimensions",
    "GC2 full transport and covariance-jet symmetry",
    "GC3 adjugate determinant-coefficient identity",
    "GC4 global trigonometric coefficient reduction",
    "GC5 sum-of-squares and nonnegativity structure",
    "GC6 branch identities and positive-region witnesses",
)
SCHEMA = "cassi.navier-stokes.rank-deficient-temporal-coefficient.verification.v1"
TRIG_A, TRIG_B, TRIG_C, TRIG_D = sp.symbols(
    "a b c d", real=True
)
TRIG_BASIS = sp.groebner(
    (
        TRIG_A**2 + TRIG_B**2 - 1,
        TRIG_C**2 + TRIG_D**2 - 1,
    ),
    TRIG_A,
    TRIG_B,
    TRIG_C,
    TRIG_D,
    order="lex",
    domain=sp.EX,
)


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
def trig_normal_form(
    value: sp.Basic, x: sp.Symbol, y: sp.Symbol
) -> sp.Basic:
    """Reduce a trig polynomial modulo both unit-circle identities."""
    value = sp.sympify(value)
    replaced = sp.expand(
        sp.expand_trig(value).xreplace(
            {
                sp.sin(x): TRIG_A,
                sp.cos(x): TRIG_B,
                sp.sin(y): TRIG_C,
                sp.cos(y): TRIG_D,
            }
        )
    )
    _, remainder = TRIG_BASIS.reduce(replaced)
    return sp.factor(remainder)
def algebraic_normal_form(value: Any) -> sp.Basic:
    """Reduce an abstract a,b,c,d polynomial modulo both circles."""
    _, remainder = TRIG_BASIS.reduce(sp.expand(sp.sympify(value)))
    return sp.factor(remainder)


def algebraic_matrix_normal_form(matrix: sp.MatrixBase) -> sp.Matrix:
    return matrix.applyfunc(algebraic_normal_form)


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
def determinant_t4_coefficient(
    first_jet: sp.MatrixBase, second_jet: sp.MatrixBase
) -> sp.Basic:
    """Extract [t^4] det(t*R1 + t^2*R2/2) without higher powers."""
    signed_permutations = (
        (1, (0, 1, 2)),
        (-1, (0, 2, 1)),
        (-1, (1, 0, 2)),
        (1, (1, 2, 0)),
        (1, (2, 0, 1)),
        (-1, (2, 1, 0)),
    )
    coefficient = sp.Integer(0)
    for sign, permutation in signed_permutations:
        first_entries = [
            first_jet[row, permutation[row]] for row in range(3)
        ]
        second_entries = [
            second_jet[row, permutation[row]] for row in range(3)
        ]
        coefficient += sign * (
            second_entries[0] * first_entries[1] * first_entries[2]
            + first_entries[0] * second_entries[1] * first_entries[2]
            + first_entries[0] * first_entries[1] * second_entries[2]
        ) / 2
    return coefficient


def verify_coefficient(book: CheckBook, values: dict[str, Any]) -> None:
    x, y, z, nu, t = sp.symbols("x y z nu t", real=True, positive=True)
    coordinates = (x, y, z)
    theta = sp.sin(x) + sp.cos(x) * sp.sin(y)
    velocity = sp.Matrix([-sp.sin(y), 0, theta])
    omega = reduce_exact(curl_of(velocity, coordinates))
    velocity_gradient = velocity.jacobian(coordinates)
    vorticity_gradient = reduce_exact(omega.jacobian(coordinates))
    source_vectors = [vorticity_gradient[:, index] for index in range(3)]
    source_from_outer_products = sum(
        (vector * vector.T for vector in source_vectors), sp.zeros(3)
    )
    source_from_matrix_product = vorticity_gradient * vorticity_gradient.T
    source = reduce_exact(source_from_outer_products)

    omega_t = reduce_exact(
        -directional_derivative(velocity, omega, coordinates)
        + velocity_gradient * omega
        + nu * laplacian(omega, coordinates)
    )
    omega_t_gradient = reduce_exact(omega_t.jacobian(coordinates))
    momentum_rhs = reduce_exact(
        -directional_derivative(velocity, velocity, coordinates)
        + nu * laplacian(velocity, coordinates)
    )
    transport_residual = reduce_exact(
        omega_t - curl_of(momentum_rhs, coordinates)
    )
    source_time_vectors = [
        omega_t_gradient[:, index] for index in range(3)
    ]
    q_t = reduce_exact(
        sum(
            (
                time_vector * source_vector.T
                + source_vector * time_vector.T
                for source_vector, time_vector in zip(
                    source_vectors, source_time_vectors
                )
            ),
            sp.zeros(3),
        )
    )
    r1 = reduce_exact(2 * nu * source)
    r2 = reduce_exact(
        -matrix_directional_derivative(velocity, r1, coordinates)
        + nu * matrix_laplacian(r1, coordinates)
        + velocity_gradient * r1
        + r1 * velocity_gradient.T
        + 2 * nu * q_t
    )

    source_vector_shapes = tuple(vector.shape for vector in source_vectors)
    source_time_vector_shapes = tuple(
        vector.shape for vector in source_time_vectors
    )
    dimensions = {
        "source_vectors": source_vector_shapes,
        "source_time_vectors": source_time_vector_shapes,
        "vorticity_gradient": vorticity_gradient.shape,
        "source_outer_sum": source.shape,
        "source_matrix_product": source_from_matrix_product.shape,
        "q_time": q_t.shape,
        "R1": r1.shape,
        "R2": r2.shape,
    }
    dimension_contract = (
        source_vector_shapes == ((3, 1), (3, 1), (3, 1))
        and source_time_vector_shapes == ((3, 1), (3, 1), (3, 1))
        and vorticity_gradient.shape == (3, 3)
        and source.shape == (3, 3)
        and source_from_matrix_product.shape == (3, 3)
        and q_t.shape == (3, 3)
        and r1.shape == (3, 3)
        and r2.shape == (3, 3)
    )
    source_factorization_residual = reduce_exact(
        source_from_outer_products - source_from_matrix_product
    )
    book.record(
        EXPECTED_CHECK_NAMES[0],
        dimension_contract
        and is_zero(vorticity_gradient[:, 2])
        and is_zero(source_factorization_residual),
        {
            "dimensions": dimensions,
            "source_vectors": source_vectors,
            "source_factorization_residual": source_factorization_residual,
        },
    )

    second_jet_symmetry_residual = reduce_exact(r2 - r2.T)
    book.record(
        EXPECTED_CHECK_NAMES[1],
        is_zero(transport_residual) and is_zero(second_jet_symmetry_residual),
        {
            "vorticity_transport_residual": transport_residual,
            "second_jet_symmetry_residual": second_jet_symmetry_residual,
            "q_time_derivative": q_t,
        },
    )
    point = {x: sp.pi / 2, y: 0}
    normal_vorticity_gradient = vorticity_gradient.applyfunc(
        lambda entry: trig_normal_form(entry, x, y)
    )
    normal_source_vectors = [
        normal_vorticity_gradient[:, index] for index in range(3)
    ]
    normal_source_from_outer_products = sum(
        (vector * vector.T for vector in normal_source_vectors),
        sp.zeros(3),
    )
    normal_source = normal_source_from_outer_products
    normal_r1 = r1.applyfunc(
        lambda entry: trig_normal_form(entry, x, y)
    )
    normal_r2 = r2.applyfunc(
        lambda entry: trig_normal_form(entry, x, y)
    )
    normal_n = normal_source_vectors[0].cross(normal_source_vectors[1])
    direct_coefficient = algebraic_normal_form(
        determinant_t4_coefficient(normal_r1, normal_r2)
    )
    adjugate_residual = algebraic_matrix_normal_form(
        normal_source.adjugate() - normal_n * normal_n.T
    )
    adjugate_coefficient = algebraic_normal_form(
        sp.trace(normal_r1.adjugate() * normal_r2) / 2
    )
    null_contraction_coefficient = algebraic_normal_form(
        2 * nu**2 * (normal_n.T * normal_r2 * normal_n)[0]
    )
    adjugate_coefficient_residual = algebraic_normal_form(
        direct_coefficient - adjugate_coefficient
    )
    null_contraction_coefficient_residual = algebraic_normal_form(
        direct_coefficient - null_contraction_coefficient
    )
    book.record(
        EXPECTED_CHECK_NAMES[2],
        is_zero(adjugate_residual)
        and is_zero(adjugate_coefficient_residual)
        and is_zero(null_contraction_coefficient_residual),
        {
            "adjugate_residual": adjugate_residual,
            "direct_coefficient": direct_coefficient,
            "adjugate_coefficient": adjugate_coefficient,
            "adjugate_coefficient_residual": adjugate_coefficient_residual,
            "null_contraction_coefficient": null_contraction_coefficient,
            "null_contraction_coefficient_residual": (
                null_contraction_coefficient_residual
            ),
        },
    )

    a, b, c, d = TRIG_A, TRIG_B, TRIG_C, TRIG_D
    expanded_f = (
        a**4 * c**6
        - a**4 * c**4
        + a**4 * d**6
        + 4 * a**3 * b * c**3
        + 2 * a**2 * c**2
        - c**6
        + c**4
    )
    sos_f = d**2 * (
        (c**2 - a**2) ** 2 + 4 * a**2 * b**2 * c**2
    ) + 2 * a**2 * c**2 * (a + b * c) ** 2
    expanded_residual = algebraic_normal_form(
        direct_coefficient - 8 * nu**4 * expanded_f
    )
    coefficient_identity_residual = algebraic_normal_form(
        direct_coefficient - 8 * nu**4 * sos_f
    )
    book.record(
        EXPECTED_CHECK_NAMES[3],
        is_zero(expanded_residual),
        {
            "expanded_coefficient_residual": expanded_residual,
            "expanded_f": expanded_f,
            "direct_coefficient": direct_coefficient,
        },
    )
    book.record(
        EXPECTED_CHECK_NAMES[4],
        is_zero(coefficient_identity_residual),
        {
            "sum_of_squares_residual": coefficient_identity_residual,
            "sos_f": sos_f,
            "coefficient": direct_coefficient,
        },
    )

    sos_trig = sos_f.subs(
        {
            a: sp.sin(x),
            b: sp.cos(x),
            c: sp.sin(y),
            d: sp.cos(y),
        }
    )
    plus_boundary_residual = reduce_exact(
        sos_trig.subs(y, sp.pi / 2)
        - 2 * sp.sin(x) ** 2 * (sp.sin(x) + sp.cos(x)) ** 2
    )
    minus_boundary_residual = reduce_exact(
        sos_trig.subs(y, 3 * sp.pi / 2)
        - 2 * sp.sin(x) ** 2 * (sp.sin(x) - sp.cos(x)) ** 2
    )
    origin_zero = reduce_exact(sos_trig.subs({x: 0, y: 0}))
    active_value = reduce_exact(sos_trig.subs(point))
    normal_point = {a: 1, b: 0, c: 0, d: 1}
    active_coefficient = sp.factor(direct_coefficient.subs(normal_point))
    off_branch_points = {
        "(pi/2, pi/4)": (sp.pi / 2, sp.pi / 4),
        "(0, pi/4)": (0, sp.pi / 4),
    }
    off_branch_values = {
        label: reduce_exact(
            sos_trig.subs({x: point_coordinates[0], y: point_coordinates[1]})
        )
        for label, point_coordinates in off_branch_points.items()
    }
    branch_zero_points = {
        "a_equals_c_equals_zero": {x: 0, y: 0},
        "d_equals_zero_a_equals_zero": {x: 0, y: sp.pi / 2},
        "d_equals_zero_a_plus_bc_equals_zero": {
            x: 3 * sp.pi / 4,
            y: sp.pi / 2,
        },
    }
    branch_zero_values = {
        label: reduce_exact(sos_trig.subs(point_coordinates))
        for label, point_coordinates in branch_zero_points.items()
    }
    branch_zero_ok = all(value == 0 for value in branch_zero_values.values())
    book.record(
        EXPECTED_CHECK_NAMES[5],
        is_zero(plus_boundary_residual)
        and is_zero(minus_boundary_residual)
        and origin_zero == 0
        and active_value == 1
        and active_coefficient == 8 * nu**4
        and all(bool(value > 0) for value in off_branch_values.values())
        and branch_zero_ok,
        {
            "y_pi_over_2_branch_residual": plus_boundary_residual,
            "y_three_pi_over_2_branch_residual": minus_boundary_residual,
            "branch_zero_points": branch_zero_points,
            "branch_zero_values": branch_zero_values,
            "branch_zero_ok": branch_zero_ok,
            "origin_zero": origin_zero,
            "active_f": active_value,
            "active_coefficient": active_coefficient,
            "off_branch_positive_values": off_branch_values,
            "zero_set_branches": (
                "a=c=0, or d=0 with a=0, or d=0 with a+b*c=0; "
                "this check exercises representatives, not an iff proof"
            ),
        },
    )

    values.update(
        {
            "control": {
                "velocity": velocity,
                "vorticity": omega,
                "source_vectors": source_vectors,
                "source": source,
                "vorticity_time_derivative": omega_t,
            },
            "covariance_jets": {
                "R1": r1,
                "R2": r2,
                "Q_t": q_t,
            },
            "coefficient": {
                "direct": direct_coefficient,
                "expanded_f": expanded_f,
                "sos_f": sos_f,
                "active_point": point,
            },
        }
    )


def protocol_integrity() -> dict[str, Any]:
    text = PROTOCOL.read_text(encoding="utf-8")
    tags = re.findall(r"\\tag\{(GCS\d+)\}", text)
    expected_tags = [f"GCS{index}" for index in range(1, 10)]
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
    verify_coefficient(book, values)
    integrity = protocol_integrity()
    note_text = NOTE.read_text(encoding="utf-8").lower()
    temporal_text = BOUND_TEMPORAL_NOTE.read_text(encoding="utf-8").lower()
    control_text = BOUND_CONTROL_NOTE.read_text(encoding="utf-8").lower()
    required_note_anchors = (
        "global sign of the temporal covariance determinant coefficient",
        r"8\nu^4 f",
        "nonnegative everywhere",
        "unresolved",
    )
    required_temporal_anchors = (
        "temporal covariance rank recovery",
        r"8\nu^4t^4",
        "unresolved",
    )
    required_control_anchors = (
        "active stretching with rank-deficient vorticity gradients",
        "two-and-a-half-dimensional",
        r"\det j_0=0",
    )
    missing_note_anchors = [
        anchor for anchor in required_note_anchors if anchor not in note_text
    ]
    missing_temporal_anchors = [
        anchor for anchor in required_temporal_anchors if anchor not in temporal_text
    ]
    missing_control_anchors = [
        anchor for anchor in required_control_anchors if anchor not in control_text
    ]
    identities = {
        "coefficient_note": {
            "path": "CassiTheory/turbulence/navier-stokes-rank-deficient-temporal-coefficient.md",
            "sha256": source_hash(NOTE),
        },
        "temporal_recovery_note": {
            "path": "CassiTheory/turbulence/navier-stokes-rank-deficient-temporal-recovery.md",
            "sha256": source_hash(BOUND_TEMPORAL_NOTE),
        },
        "bound_control_note": {
            "path": "CassiTheory/turbulence/navier-stokes-rank-deficient-stretching.md",
            "sha256": source_hash(BOUND_CONTROL_NOTE),
        },
        "protocol": {
            "path": "CassiTheory/computations/navier-stokes-rank-deficient-temporal-coefficient-prereg.md",
            "sha256": source_hash(PROTOCOL),
        },
        "verifier": {
            "path": "CassiTheory/computations/verify_navier_stokes_rank_deficient_temporal_coefficient.py",
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
        and not missing_temporal_anchors
        and not missing_control_anchors
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
        "temporal_recovery_note_integrity": {
            "required_anchors": required_temporal_anchors,
            "missing_anchors": missing_temporal_anchors,
        },
        "bound_control_note_integrity": {
            "required_anchors": required_control_anchors,
            "missing_anchors": missing_control_anchors,
        },
        "identities": identities,
        "classifications": {
            "global_leading_coefficient_sign": (
                "SUPPORTS" if success else "UNRESOLVED"
            ),
            "positive_coefficient_open_region": (
                "SUPPORTS" if success else "UNRESOLVED"
            ),
            "instantaneous_full_rank_source": (
                "CONTRADICTS" if success else "UNRESOLVED"
            ),
            "uniform_exact_covariance_lower_bound": "UNRESOLVED",
            "production_relative_recovery_estimate": "UNRESOLVED",
            "arbitrary_data_navier_stokes_regularity": "UNRESOLVED",
        },
        "scope": {
            "trajectory_integration": "NOT_RUN",
            "stochastic_flow_simulation": "NOT_RUN",
            "covariance_pde_time_integration": "NOT_RUN",
            "initial_time_jet": "EXACT",
            "coefficient_sign": "GLOBAL_LEADING_COEFFICIENT_ONLY",
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
        "coefficient_note": NOTE,
        "temporal_recovery_note": BOUND_TEMPORAL_NOTE,
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
        "temporal_recovery_note_anchors_match: "
        f"{not result['temporal_recovery_note_integrity']['missing_anchors']}"
    )
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
