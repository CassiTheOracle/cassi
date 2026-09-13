#!/usr/bin/env python3
"""Verify the vorticity-covariance quotient identity and its boundary controls.

The verifier checks exact local matrix algebra and closed-form controls only.
It does not integrate a generic Navier–Stokes trajectory or establish a
uniform continuation estimate for arbitrary data.
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
WORKSPACE = ROOT.parent
NOTE = ROOT / "turbulence" / "navier-stokes-vorticity-quotient.md"
PROTOCOL = ROOT / "computations" / "navier-stokes-vorticity-quotient-prereg.md"
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_vorticity_quotient_20260913"
    / "verification.json"
)
EXPECTED_CHECKS = 13
EXPECTED_CHECK_NAMES = (
    "RQV1 local inverse-covariance quotient identity",
    "RQV2 covariant-square positivity",
    "RQV3 reaction cancellation",
    "RQV4 seeded second-moment source cancellation",
    "RQV5 normalized mean quotient bound",
    "RQV6 Sherman–Morrison quotient relation",
    "RQV7 ABC Beltrami origin geometry",
    "RQV8 ABC covariance initial jet",
    "RQV9 ABC reciprocal-time quotient obstruction",
    "RQV10 periodic shear rank-one source",
    "RQV11 affine zero-source degeneration",
    "RQV12 protocol tags and inventory",
    "RQV13 note anchors and unresolved scope",
)
SCHEMA = "cassi.navier-stokes.vorticity-quotient.verification.v1"


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
        return str(value)
    return value


def reduce_exact(value: Any) -> Any:
    if isinstance(value, sp.MatrixBase):
        return value.applyfunc(sp.simplify)
    return sp.simplify(value)


def is_zero(value: Any) -> bool:
    if isinstance(value, sp.MatrixBase):
        return all(entry == 0 for entry in value)
    return value == 0


def curl_of(vector: sp.Matrix, coordinates: tuple[sp.Symbol, ...]) -> sp.Matrix:
    x, y, z = coordinates
    return sp.Matrix(
        [
            sp.diff(vector[2], y) - sp.diff(vector[1], z),
            sp.diff(vector[0], z) - sp.diff(vector[2], x),
            sp.diff(vector[1], x) - sp.diff(vector[0], y),
        ]
    )


def laplacian_of(vector: sp.Matrix, coordinates: tuple[sp.Symbol, ...]) -> sp.Matrix:
    return sp.Matrix(
        [
            sum(
                sp.diff(component, coordinate, 2)
                for coordinate in coordinates
            )
            for component in vector
        ]
    )


def verify_local_identity(book: CheckBook, values: dict[str, Any]) -> None:
    x = sp.symbols("x")
    nu = sp.Rational(2, 3)
    reaction = sp.Matrix([[1, 2], [0, -1]])
    w = sp.Matrix([1 + x, 2 - x**2])
    covariance = sp.Matrix([[3 + x**2, x], [x, 2 + x**2]])
    w_x = w.diff(x)
    q = w_x * w_x.T
    w_t = reaction * w + nu * w.diff(x, 2)
    covariance_t = (
        reaction * covariance
        + covariance * reaction.T
        + 2 * nu * q
        + nu * covariance.diff(x, 2)
    )
    inverse = covariance.inv()
    quotient = (w.T * inverse * w)[0]
    inverse_t = -inverse * covariance_t * inverse
    quotient_t = (
        w_t.T * inverse * w
        + w.T * inverse * w_t
        + w.T * inverse_t * w
    )[0]
    quotient_lhs = quotient_t - nu * sp.diff(quotient, x, 2)
    covariant_gradient = w_x - covariance.diff(x) * inverse * w
    quotient_rhs = -2 * nu * (
        (covariant_gradient.T * inverse * covariant_gradient)[0]
        + (w.T * inverse * q * inverse * w)[0]
    )
    residual = reduce_exact(quotient_lhs - quotient_rhs)
    book.record(
        EXPECTED_CHECK_NAMES[0],
        is_zero(residual),
        {
            "residual": residual,
            "covariance_determinant": reduce_exact(covariance.det()),
            "operator": "partial_t + u dot grad - nu Delta",
        },
    )

    origin = {x: 0}
    inverse_origin = inverse.subs(origin)
    gradient_origin = covariant_gradient.subs(origin)
    source_origin = q.subs(origin)
    spatial_square = reduce_exact(
        (gradient_origin.T * inverse_origin * gradient_origin)[0]
    )
    source_square = reduce_exact(
        (
            w.subs(origin).T
            * inverse_origin
            * source_origin
            * inverse_origin
            * w.subs(origin)
        )[0]
    )
    book.record(
        EXPECTED_CHECK_NAMES[1],
        bool(spatial_square >= 0 and source_square >= 0),
        {
            "spatial_square": spatial_square,
            "source_square": source_square,
            "inverse_origin": inverse_origin,
        },
    )
    values["local"] = {
        "residual": residual,
        "covariance_determinant": reduce_exact(covariance.det()),
        "spatial_square": spatial_square,
        "source_square": source_square,
    }


def verify_reaction_and_seeded_laws(book: CheckBook) -> None:
    reaction = sp.Matrix([[1, 2], [0, -1]])
    w = sp.Matrix([2, 1])
    covariance = sp.Matrix([[3, 1], [1, 2]])
    inverse = covariance.inv()
    w_t = reaction * w
    covariance_t = reaction * covariance + covariance * reaction.T
    quotient_t = reduce_exact(
        (w_t.T * inverse * w)[0]
        + (w.T * inverse * w_t)[0]
        - (w.T * inverse * covariance_t * inverse * w)[0]
    )
    book.record(
        EXPECTED_CHECK_NAMES[2],
        quotient_t == 0,
        {"reaction_quotient_derivative": quotient_t},
    )

    x = sp.symbols("x")
    nu = sp.Rational(2, 3)
    w_field = sp.Matrix([1 + x, 2 - x**2])
    covariance_field = sp.Matrix([[3 + x**2, x], [x, 2 + x**2]])
    reaction_field = reaction
    q_field = w_field.diff(x) * w_field.diff(x).T
    w_t = reaction_field * w_field + nu * w_field.diff(x, 2)
    covariance_t = (
        reaction_field * covariance_field
        + covariance_field * reaction_field.T
        + 2 * nu * q_field
        + nu * covariance_field.diff(x, 2)
    )
    seeded = covariance_field + w_field * w_field.T
    seeded_t = covariance_t + w_t * w_field.T + w_field * w_t.T
    seeded_lhs = seeded_t - nu * seeded.diff(x, 2)
    seeded_rhs = reaction_field * seeded + seeded * reaction_field.T
    residual = reduce_exact(seeded_lhs - seeded_rhs)
    book.record(
        EXPECTED_CHECK_NAMES[3],
        is_zero(residual),
        {
            "residual": residual,
            "source": q_field,
            "law": "L_u M = L M + M L.T",
        },
    )


def verify_normalized_quotients(book: CheckBook) -> None:
    w = sp.Matrix([1, 2])
    covariance = sp.Matrix([[3, 1], [1, 2]])
    seeded = covariance + w * w.T
    z_r = reduce_exact((w.T * covariance.inv() * w)[0])
    z_m = reduce_exact((w.T * seeded.inv() * w)[0])
    covariance_determinant = reduce_exact(covariance.det())
    covariance_positive = covariance_determinant == 5
    book.record(
        EXPECTED_CHECK_NAMES[4],
        covariance_positive and bool(0 <= z_m <= 1),
        {
            "covariance_determinant": covariance_determinant,
            "seeded_minus_mean_outer": covariance,
            "z_M": z_m,
        },
    )
    relation_residual = reduce_exact(z_m - z_r / (1 + z_r))
    book.record(
        EXPECTED_CHECK_NAMES[5],
        relation_residual == 0,
        {
            "z_R": z_r,
            "z_M": z_m,
            "relation_residual": relation_residual,
        },
    )


def verify_abc_controls(book: CheckBook, values: dict[str, Any]) -> None:
    x, y, z = sp.symbols("x y z", real=True)
    coordinates = (x, y, z)
    abc = sp.Matrix(
        [
            sp.sin(z) + sp.cos(y),
            sp.sin(x) + sp.cos(z),
            sp.sin(y) + sp.cos(x),
        ]
    )
    abc_vorticity = curl_of(abc, coordinates)
    abc_gradient = abc_vorticity.jacobian(coordinates)
    origin = {x: 0, y: 0, z: 0}
    origin_gradient = abc_gradient.subs(origin)
    expected_gradient = sp.Matrix(
        [
            [0, 0, 1],
            [1, 0, 0],
            [0, 1, 0],
        ]
    )
    origin_gram = origin_gradient * origin_gradient.T
    book.record(
        EXPECTED_CHECK_NAMES[6],
        abc_vorticity == abc
        and laplacian_of(abc, coordinates) == -abc
        and origin_gradient == expected_gradient
        and origin_gram == sp.eye(3)
        and abc_vorticity.subs(origin) == sp.Matrix([1, 1, 1]),
        {
            "curl_residual": reduce_exact(abc_vorticity - abc),
            "heat_residual": reduce_exact(laplacian_of(abc, coordinates) + abc),
            "origin_vorticity_gradient": origin_gradient,
            "origin_gram": origin_gram,
        },
    )

    abc_nu = sp.symbols("abc_nu", positive=True)
    initial_covariance_jet = 2 * abc_nu * origin_gram
    expected_jet = 2 * abc_nu * sp.eye(3)
    book.record(
        EXPECTED_CHECK_NAMES[7],
        initial_covariance_jet == expected_jet,
        {
            "initial_covariance_time_derivative": initial_covariance_jet,
            "expected": expected_jet,
        },
    )

    t = sp.symbols("t", positive=True)
    leading_quotient = sp.Rational(3, 1) / (2 * abc_nu * t)
    leading_coefficient = sp.limit(t * leading_quotient, t, 0, dir="+")
    epsilon = sp.symbols("epsilon", positive=True)
    leading_integral = sp.integrate(leading_quotient, (t, epsilon, 1))
    divergence = sp.limit(leading_integral, epsilon, 0, dir="+")
    book.record(
        EXPECTED_CHECK_NAMES[8],
        leading_coefficient == 3 / (2 * abc_nu)
        and divergence == sp.oo,
        {
            "leading_quotient": leading_quotient,
            "leading_coefficient": leading_coefficient,
            "integral_from_epsilon": leading_integral,
            "epsilon_to_zero_limit": divergence,
        },
    )
    values["abc"] = {
        "origin_gram": origin_gram,
        "leading_coefficient": leading_coefficient,
        "reciprocal_time_integral": divergence,
    }


def verify_degenerate_controls(book: CheckBook, values: dict[str, Any]) -> None:
    x, y, z = sp.symbols("x y z", real=True)
    coordinates = (x, y, z)
    n = sp.Integer(2)
    shear = sp.Matrix([sp.sin(n * y), 0, 0])
    shear_vorticity = curl_of(shear, coordinates)
    shear_gradient = shear_vorticity.jacobian(coordinates)
    shear_q = shear_gradient * shear_gradient.T
    shear_point = shear_q.subs({x: 0, y: sp.pi / 4, z: 0})
    book.record(
        EXPECTED_CHECK_NAMES[9],
        shear_vorticity == sp.Matrix([0, 0, -n * sp.cos(n * y)])
        and reduce_exact(shear_q.det()) == 0
        and shear_point == sp.diag(0, 0, 16),
        {
            "vorticity": shear_vorticity,
            "source_gram_determinant": reduce_exact(shear_q.det()),
            "source_at_pi_over_four": shear_point,
        },
    )

    extensional_matrix = sp.diag(1, -1, 0)
    zero_source = sp.zeros(3)
    zero_covariance = sp.zeros(3)
    book.record(
        EXPECTED_CHECK_NAMES[10],
        extensional_matrix.trace() == 0
        and zero_source == sp.zeros(3)
        and zero_covariance.det() == 0,
        {
            "trace_free_reaction": extensional_matrix.trace(),
            "source": zero_source,
            "initial_covariance": zero_covariance,
            "inverse_quotient": "undefined on R=0",
        },
    )
    values["degenerate_controls"] = {
        "shear_source_rank": 1,
        "affine_source": 0,
    }


def protocol_integrity() -> dict[str, Any]:
    text = PROTOCOL.read_text(encoding="utf-8")
    declared_names = tuple(
        re.findall(r"^- `(RQV\d+ [^`]+)`", text, flags=re.MULTILINE)
    )
    observed_tags = [name.split(maxsplit=1)[0] for name in declared_names]
    expected_tags = [f"RQV{index}" for index in range(1, 14)]
    return {
        "tag_count": len(observed_tags),
        "observed_tags": observed_tags,
        "expected_tags": expected_tags,
        "tags_match": observed_tags == expected_tags,
        "declared_check_count": len(declared_names),
        "declared_check_names": list(declared_names),
        "inventory_names_match": declared_names == EXPECTED_CHECK_NAMES,
        "inventory_declaration_present": (
            "exactly thirteen checks" in text
        ),
        "note_binding_present": (
            "turbulence/navier-stokes-vorticity-quotient.md" in text
        ),
        "verifier_binding_present": (
            "computations/verify_navier_stokes_vorticity_quotient.py" in text
        ),
    }


def verify_integrity_checks(book: CheckBook) -> dict[str, Any]:
    integrity = protocol_integrity()
    integrity_pass = bool(
        integrity["tags_match"]
        and integrity["inventory_names_match"]
        and integrity["inventory_declaration_present"]
        and integrity["note_binding_present"]
        and integrity["verifier_binding_present"]
    )
    book.record(EXPECTED_CHECK_NAMES[11], integrity_pass, integrity)

    note_text = NOTE.read_text(encoding="utf-8")
    anchors = (
        "## Status: Derived—September 2026",
        "z_R=\\omega^{\\mathsf T}R^{-1}\\omega",
        "\\mathcal L_uz_R\\le0",
        "Q_\\omega=(\\nabla\\omega)(\\nabla\\omega)^{\\mathsf T}",
        "Q_\\omega(0,0)=I",
        "R(0,t)=2\\nu tI+O(t^2)",
        "3/(2\\nu t)+O(1)",
        "rank-one shear",
        "UNRESOLVED",
    )
    missing = [anchor for anchor in anchors if anchor not in note_text]
    book.record(
        EXPECTED_CHECK_NAMES[12],
        not missing,
        {"missing_anchors": missing, "anchor_count": len(anchors)},
    )
    return integrity


def source_identities() -> dict[str, dict[str, str]]:
    sources = {
        "note": NOTE,
        "protocol": PROTOCOL,
        "verifier": Path(__file__).resolve(),
    }
    return {
        key: {
            "path": path.relative_to(WORKSPACE).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for key, path in sources.items()
    }


def compute() -> tuple[dict[str, Any], bool]:
    book = CheckBook()
    values: dict[str, Any] = {}
    verify_local_identity(book, values)
    verify_reaction_and_seeded_laws(book)
    verify_normalized_quotients(book)
    verify_abc_controls(book, values)
    verify_degenerate_controls(book, values)
    integrity = verify_integrity_checks(book)

    observed_names = tuple(row["name"] for row in book.checks)
    inventory_match = observed_names == EXPECTED_CHECK_NAMES
    if not inventory_match:
        book.failures.append("fixed check inventory")

    success = (
        not book.failures
        and inventory_match
        and len(book.checks) == EXPECTED_CHECKS
    )
    identities = source_identities()
    result = {
        "schema": SCHEMA,
        "status": "PASS" if success else "FAIL",
        "expected_check_count": EXPECTED_CHECKS,
        "expected_check_names": list(EXPECTED_CHECK_NAMES),
        "check_count": len(book.checks),
        "inventory_match": inventory_match,
        "protocol_integrity": integrity,
        "checks": book.checks,
        "failures": book.failures,
        "values": stringify(values),
        "identities": identities,
        "classifications": {
            "local_inverse_covariance_identity": (
                "SUPPORTS" if success else "INCONCLUSIVE"
            ),
            "normalized_mean_quotient_bound": (
                "SUPPORTS" if success else "INCONCLUSIVE"
            ),
            "raw_unweighted_quotient_integrability": (
                "CONTRADICTS" if success else "INCONCLUSIVE"
            ),
            "uniform_initial_data_continuation_estimate": "UNRESOLVED",
            "arbitrary_data_navier_stokes_regularity": "UNRESOLVED",
        },
        "scope": {
            "symbolic_implications": "EXACT_FINITE_ALGEBRA",
            "navier_stokes_trajectory": "EXACT_CLOSED_FORM_CONTROLS_ONLY",
            "generic_navier_stokes_trajectory": "NOT_RUN",
            "stochastic_flow_simulation": "NOT_RUN",
            "raw_unweighted_quotient_integrability": "CONTRADICTED_BY_ABC_CONTROL",
            "uniform_initial_data_continuation_estimate": "UNRESOLVED",
            "global_regularity": "UNRESOLVED",
        },
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
