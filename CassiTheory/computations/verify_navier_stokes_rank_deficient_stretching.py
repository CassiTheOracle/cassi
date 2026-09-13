#!/usr/bin/env python3
"""Verify the active rank-deficient vorticity-gradient control.

The executable checks exact initial-time trigonometric identities and the
structural two-and-a-half-dimensional reduction. It does not integrate a
generic Navier–Stokes trajectory, simulate Brownian paths, or evaluate an
accumulated covariance Gramian.
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
NOTE = ROOT / "turbulence" / "navier-stokes-rank-deficient-stretching.md"
PROTOCOL = (
    ROOT / "computations" / "navier-stokes-rank-deficient-stretching-prereg.md"
)
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_rank_deficient_stretching_20260913"
    / "verification.json"
)
EXPECTED_CHECKS = 7
EXPECTED_CHECK_NAMES = (
    "RD1 mean-zero divergence-free control",
    "RD2 curl reconstruction",
    "RD3 full vorticity transport identity",
    "RD4 rank-deficient source determinant",
    "RD5 generic rank-two source witness",
    "RD6 positive initial stretching average",
    "RD7 invariant 2.5D determinant boundary",
)
SCHEMA = "cassi.navier-stokes.rank-deficient-stretching.verification.v1"


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


def laplacian(
    field: sp.MatrixBase, coordinates: tuple[sp.Symbol, ...]
) -> sp.Matrix:
    return sp.Matrix(
        [
            sum(sp.diff(component, coordinate, 2) for coordinate in coordinates)
            for component in field
        ]
    )


def spatial_average(
    expression: Any,
    x: sp.Symbol,
    y: sp.Symbol,
    z: sp.Symbol,
) -> Any:
    return reduce_exact(
        sp.integrate(
            sp.integrate(sp.integrate(expression, (x, 0, 2 * sp.pi)), (y, 0, 2 * sp.pi)),
            (z, 0, 2 * sp.pi),
        )
        / (2 * sp.pi) ** 3
    )


def verify_control(book: CheckBook, values: dict[str, Any]) -> None:
    x, y, z, nu = sp.symbols("x y z nu", real=True)
    coordinates = (x, y, z)
    theta = sp.sin(x) + sp.cos(x) * sp.sin(y)
    velocity = sp.Matrix([-sp.sin(y), 0, theta])
    divergence = reduce_exact(sum(sp.diff(velocity[i], coordinates[i]) for i in range(3)))
    means = tuple(spatial_average(component, x, y, z) for component in velocity)
    book.record(
        EXPECTED_CHECK_NAMES[0],
        divergence == 0 and all(mean == 0 for mean in means),
        {"divergence": divergence, "component_means": means},
    )

    omega = reduce_exact(curl_of(velocity, coordinates))
    expected_omega = sp.Matrix(
        [
            sp.cos(x) * sp.cos(y),
            sp.sin(x) * sp.sin(y) - sp.cos(x),
            sp.cos(y),
        ]
    )
    curl_residual = reduce_exact(omega - expected_omega)
    book.record(
        EXPECTED_CHECK_NAMES[1],
        is_zero(curl_residual),
        {"omega": omega, "residual": curl_residual},
    )

    velocity_gradient = velocity.jacobian(coordinates)
    advective_vorticity = reduce_exact(
        directional_derivative(velocity, omega, coordinates)
    )
    reaction_vorticity = reduce_exact(velocity_gradient * omega)
    diffusive_vorticity = reduce_exact(nu * laplacian(omega, coordinates))
    vorticity_rhs = reduce_exact(
        -advective_vorticity + reaction_vorticity + diffusive_vorticity
    )
    nonlinear_momentum = directional_derivative(velocity, velocity, coordinates)
    curl_momentum_rhs = reduce_exact(
        curl_of(-nonlinear_momentum + nu * laplacian(velocity, coordinates), coordinates)
    )
    transport_residual = reduce_exact(vorticity_rhs - curl_momentum_rhs)
    book.record(
        EXPECTED_CHECK_NAMES[2],
        is_zero(transport_residual),
        {
            "advection": advective_vorticity,
            "reaction": reaction_vorticity,
            "diffusion": diffusive_vorticity,
            "curl_momentum_rhs": curl_momentum_rhs,
            "residual": transport_residual,
        },
    )

    vorticity_gradient = reduce_exact(omega.jacobian(coordinates))
    source = reduce_exact(vorticity_gradient * vorticity_gradient.T)
    third_column = vorticity_gradient[:, 2]
    determinant_gradient = reduce_exact(vorticity_gradient.det())
    determinant_source = reduce_exact(source.det())
    book.record(
        EXPECTED_CHECK_NAMES[3],
        is_zero(third_column)
        and determinant_gradient == 0
        and determinant_source == 0,
        {
            "gradient": vorticity_gradient,
            "third_column": third_column,
            "determinant_gradient": determinant_gradient,
            "determinant_source": determinant_source,
        },
    )

    rank_point = {x: sp.pi / 2, y: 0}
    point_gradient = vorticity_gradient.subs(rank_point)
    point_source = source.subs(rank_point)
    book.record(
        EXPECTED_CHECK_NAMES[4],
        point_gradient.rank() == 2 and point_source.rank() == 2,
        {
            "point": rank_point,
            "gradient": point_gradient,
            "source": point_source,
            "gradient_rank": point_gradient.rank(),
            "source_rank": point_source.rank(),
        },
    )

    strain = reduce_exact((velocity_gradient + velocity_gradient.T) / 2)
    stretching_density = reduce_exact((omega.T * strain * omega)[0])
    stretching_average = spatial_average(stretching_density, x, y, z)
    book.record(
        EXPECTED_CHECK_NAMES[5],
        stretching_average == sp.Rational(1, 4),
        {
            "density": stretching_density,
            "average": stretching_average,
        },
    )

    v1 = sp.Function("v1")(x, y)
    v2 = sp.Function("v2")(x, y)
    scalar = sp.Function("vartheta")(x, y)
    class_velocity = sp.Matrix([v1, v2, scalar])
    class_vorticity = curl_of(class_velocity, coordinates)
    z_gradient = reduce_exact(
        sp.Matrix([sp.diff(component, z) for component in class_vorticity])
    )
    vertical_advection = reduce_exact(
        directional_derivative(class_velocity, sp.Matrix([scalar, 0, 0]), coordinates)[0]
        - (v1 * sp.diff(scalar, x) + v2 * sp.diff(scalar, y))
    )
    scalar_laplacian = reduce_exact(
        laplacian(sp.Matrix([scalar]), coordinates)[0]
        - (sp.diff(scalar, x, 2) + sp.diff(scalar, y, 2))
    )
    book.record(
        EXPECTED_CHECK_NAMES[6],
        is_zero(z_gradient)
        and vertical_advection == 0
        and scalar_laplacian == 0,
        {
            "class_vorticity": class_vorticity,
            "z_gradient": z_gradient,
            "vertical_advection_residual": vertical_advection,
            "scalar_laplacian_residual": scalar_laplacian,
            "instantaneous_determinant_functional": 0,
        },
    )

    values.update(
        {
            "control": {
                "velocity": velocity,
                "vorticity": omega,
                "vorticity_gradient": vorticity_gradient,
                "source": source,
                "stretching_density": stretching_density,
            },
            "initial_stretching_average": stretching_average,
            "rank_two_point": {
                "gradient": point_gradient,
                "source": point_source,
            },
            "full_vorticity_rhs": vorticity_rhs,
        }
    )


def protocol_integrity() -> dict[str, Any]:
    text = PROTOCOL.read_text(encoding="utf-8")
    tags = re.findall(r"\\tag\{(RDS\d+)\}", text)
    expected_tags = [f"RDS{index}" for index in range(1, 9)]
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
    verify_control(book, values)
    integrity = protocol_integrity()
    note_text = NOTE.read_text(encoding="utf-8").lower()
    required_note_anchors = (
        "active stretching with rank-deficient vorticity gradients",
        "two-and-a-half-dimensional",
        r"\det j_0=0",
        "unresolved",
    )
    missing_note_anchors = [
        anchor for anchor in required_note_anchors if anchor not in note_text
    ]
    identities = {
        "note": {
            "path": "CassiTheory/turbulence/navier-stokes-rank-deficient-stretching.md",
            "sha256": source_hash(NOTE),
        },
        "protocol": {
            "path": "CassiTheory/computations/navier-stokes-rank-deficient-stretching-prereg.md",
            "sha256": source_hash(PROTOCOL),
        },
        "verifier": {
            "path": "CassiTheory/computations/verify_navier_stokes_rank_deficient_stretching.py",
            "sha256": source_hash(Path(__file__).resolve()),
        },
    }
    checks_ok = len(book.checks) == EXPECTED_CHECKS and not book.failures
    inventory_ok = (
        integrity["declared_check_count"] == EXPECTED_CHECKS
        and integrity["inventory_names_match"]
    )
    sources_ok = not missing_note_anchors and integrity["tags_match"]
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
        "identities": identities,
        "classifications": {
            "initial_control_validity": (
                "SUPPORTS" if success else "UNRESOLVED"
            ),
            "rank_deficient_source_with_active_stretching": (
                "SUPPORTS" if success else "UNRESOLVED"
            ),
            "instantaneous_determinant_recovery_for_all_data": (
                "CONTRADICTS" if success else "UNRESOLVED"
            ),
            "accumulated_rank_recovery": "UNRESOLVED",
            "arbitrary_data_navier_stokes_regularity": "UNRESOLVED",
        },
        "scope": {
            "trajectory_integration": "NOT_RUN",
            "stochastic_flow_simulation": "NOT_RUN",
            "accumulated_covariance_gramian": "NOT_RUN",
            "control_evolution": "INVARIANT_2.5D_CLASS_ANALYTICAL",
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
        "note": NOTE,
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
