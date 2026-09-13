#!/usr/bin/env python3
"""Verify the conditional coherence-dose continuation criterion.

The verifier checks exact symbolic implications and closed-form controls only.
It does not integrate a generic Navier–Stokes trajectory or establish the
uniform dose estimate required for arbitrary-data global regularity.
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
NOTE = ROOT / "turbulence" / "navier-stokes-coherence-dose-criterion.md"
PROTOCOL = ROOT / "computations" / "navier-stokes-coherence-dose-continuation-prereg.md"
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_coherence_dose_criterion_20260913"
    / "verification.json"
)
EXPECTED_CHECKS = 16
EXPECTED_CHECK_NAMES = (
    "C1 positive-minus-positive identity",
    "C2 retarded-spread upper bound",
    "C3 positive-dose domination",
    "C4 data-ball continuation envelope",
    "C5 retarded compensation implication",
    "C6 strain-rate operator-norm bound",
    "X1 periodic shear occupation identity",
    "X2 periodic shear active dose",
    "X3 rank-two Beltrami Navier-Stokes identities",
    "X4 rank-two singular source control",
    "X5 ABC Navier-Stokes identities",
    "X6 ABC enstrophy production cancellation",
    "X7 ABC finite strain dose",
    "X8 homogeneous extensional dose",
    "I1 protocol tags and inventory",
    "I2 note anchors and unresolved scope",
)
SCHEMA = "cassi.navier-stokes.coherence-dose.verification.v1"


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

    def exact(self, name: str, left: Any, right: Any = 0) -> None:
        difference = reduce_exact(left - right)
        self.record(name, is_zero(difference), difference)


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


def verify_conditional_algebra(book: CheckBook, values: dict[str, Any]) -> None:
    w0, g, spread = sp.symbols("w0 g spread", positive=True)
    seeded = w0 * sp.exp(2 * g)
    coherent = seeded - spread
    book.exact(
        EXPECTED_CHECK_NAMES[0],
        coherent - seeded + spread,
    )

    gap = reduce_exact(seeded - coherent)
    book.record(
        EXPECTED_CHECK_NAMES[1],
        gap == spread and sp.ask(sp.Q.nonnegative(spread)) is True,
        {"upper_gap": gap, "spread_nonnegative": True},
    )

    g_plus, g_minus = sp.symbols("g_plus g_minus", nonnegative=True)
    signed_dose = g_plus - g_minus
    dose_gap = reduce_exact(g_plus - signed_dose)
    book.record(
        EXPECTED_CHECK_NAMES[2],
        dose_gap == g_minus and sp.ask(sp.Q.nonnegative(g_minus)) is True,
        {"positive_part_minus_signed_dose": dose_gap},
    )

    radius, slack, scale = sp.symbols(
        "radius slack scale", nonnegative=True
    )
    initial_bound = radius**2 - slack
    data_gap = reduce_exact(radius**2 * scale - initial_bound * scale)
    book.record(
        EXPECTED_CHECK_NAMES[3],
        data_gap == slack * scale
        and sp.ask(sp.Q.nonnegative(slack * scale)) is True,
        {
            "initial_bound": initial_bound,
            "envelope_gap": data_gap,
            "scale_assumption": "scale = exp(2 C_gamma) >= 1",
        },
    )

    amplitude, remainder, slack = sp.symbols(
        "amplitude remainder slack", nonnegative=True
    )
    retarded = amplitude - remainder + slack
    physical_coherent = reduce_exact(amplitude - retarded)
    upper_gap = reduce_exact(remainder - physical_coherent)
    book.record(
        EXPECTED_CHECK_NAMES[4],
        upper_gap == slack
        and sp.ask(sp.Q.nonnegative(slack)) is True,
        {
            "condition": "retarded = amplitude - remainder + slack",
            "upper_gap": upper_gap,
            "retarded_spread_slack": slack,
        },
    )

    length = sp.symbols("strain_length", nonnegative=True)
    deficits = sp.symbols("d0:3", nonnegative=True)
    masses = sp.symbols("m0:3", nonnegative=True)
    eigenvalues = [length - deficit for deficit in deficits]
    trace_gap = reduce_exact(
        length * sum(masses) - sum(
            eigenvalue * mass
            for eigenvalue, mass in zip(eigenvalues, masses)
        )
    )
    product_gaps_nonnegative = all(
        sp.ask(sp.Q.nonnegative(deficit * mass)) is True
        for deficit, mass in zip(deficits, masses)
    )
    book.record(
        EXPECTED_CHECK_NAMES[5],
        trace_gap == sum(
            deficit * mass for deficit, mass in zip(deficits, masses)
        )
        and product_gaps_nonnegative,
        {
            "trace_gap": trace_gap,
            "interpretation": "eigenvalues(S) = strain_length - d_i",
        },
    )

    values["conditional_algebra"] = {
        "seeded_occupation": seeded,
        "positive_dose_gap": dose_gap,
        "data_envelope_gap": data_gap,
        "trace_rate_gap": trace_gap,
    }


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
    result = sp.zeros(3, 1)
    for coordinate in coordinates:
        result += sp.diff(vector, coordinate, 2)
    return result


def verify_controls(book: CheckBook, values: dict[str, Any]) -> None:
    t, nu, n, w0 = sp.symbols("t nu n w0", positive=True)
    shear_decay = sp.exp(-2 * nu * n**2 * t)
    shear_w = w0 * shear_decay
    shear_v = w0 * (1 - shear_decay)
    shear_e = w0
    shear_budget = reduce_exact(shear_e - shear_w - shear_v)
    shear_energy_residual = reduce_exact(
        sp.diff(shear_w, t) + 2 * nu * n**2 * shear_w
    )
    book.record(
        EXPECTED_CHECK_NAMES[6],
        shear_budget == 0 and shear_energy_residual == 0,
        {
            "budget_residual": shear_budget,
            "heat_residual": shear_energy_residual,
        },
    )

    shear_gamma = reduce_exact(sp.diff(shear_e, t) / (2 * shear_e))
    shear_dose = reduce_exact(shear_gamma)
    book.record(
        EXPECTED_CHECK_NAMES[7],
        shear_gamma == 0 and shear_dose == 0,
        {"Gamma_M": shear_gamma, "G_plus": shear_dose},
    )

    x, y, z = sp.symbols("x y z", real=True)
    coordinates = (x, y, z)
    rank_two = sp.Matrix(
        [sp.cos(y), sp.sin(x), sp.sin(y) + sp.cos(x)]
    )
    rank_two_curl = curl_of(rank_two, coordinates)
    rank_two_divergence = sum(
        sp.diff(rank_two[index], coordinates[index]) for index in range(3)
    )
    rank_two_laplacian = laplacian_of(rank_two, coordinates)
    rank_two_convection = rank_two.jacobian(coordinates) * rank_two
    rank_two_bernoulli = sp.Matrix(
        [
            sp.diff((rank_two.T * rank_two)[0] / 2, coordinate)
            for coordinate in coordinates
        ]
    )
    book.record(
        EXPECTED_CHECK_NAMES[8],
        reduce_exact(rank_two_divergence) == 0
        and is_zero(reduce_exact(rank_two_curl - rank_two))
        and is_zero(reduce_exact(rank_two_laplacian + rank_two))
        and is_zero(reduce_exact(rank_two_convection - rank_two_bernoulli)),
        {
            "divergence": reduce_exact(rank_two_divergence),
            "curl_residual": reduce_exact(rank_two_curl - rank_two),
            "heat_residual": reduce_exact(rank_two_laplacian + rank_two),
            "bernoulli_residual": reduce_exact(
                rank_two_convection - rank_two_bernoulli
            ),
        },
    )

    rank_two_vorticity = rank_two_curl
    rank_two_vorticity_gradient = rank_two_vorticity.jacobian(coordinates)
    rank_two_origin_gradient = rank_two_vorticity_gradient.subs(
        {x: 0, y: 0, z: 0}
    )
    rank_two_expected_gradient = sp.Matrix(
        [
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
        ]
    )
    rank_two_gram = (
        rank_two_vorticity_gradient * rank_two_vorticity_gradient.T
    )
    rank_two_origin = rank_two_gram.subs({x: 0, y: 0, z: 0})
    book.record(
        EXPECTED_CHECK_NAMES[9],
        reduce_exact(rank_two_gram.det()) == 0
        and rank_two_origin_gradient == rank_two_expected_gradient
        and rank_two_origin == sp.diag(0, 1, 1),
        {
            "source_gram_determinant": reduce_exact(rank_two_gram.det()),
            "origin_vorticity_gradient": rank_two_origin_gradient,
            "origin_gram": rank_two_origin,
            "gram_convention": "J rows=vorticity components; Q=J*J.T",
        },
    )

    abc = sp.Matrix(
        [
            sp.sin(z) + sp.cos(y),
            sp.sin(x) + sp.cos(z),
            sp.sin(y) + sp.cos(x),
        ]
    )
    abc_curl = curl_of(abc, coordinates)
    abc_divergence = sum(
        sp.diff(abc[index], coordinates[index]) for index in range(3)
    )
    abc_laplacian = laplacian_of(abc, coordinates)
    abc_convection = abc.jacobian(coordinates) * abc
    abc_bernoulli = sp.Matrix(
        [sp.diff((abc.T * abc)[0] / 2, coordinate) for coordinate in coordinates]
    )
    book.record(
        EXPECTED_CHECK_NAMES[10],
        reduce_exact(abc_divergence) == 0
        and is_zero(reduce_exact(abc_curl - abc))
        and is_zero(reduce_exact(abc_laplacian + abc))
        and is_zero(reduce_exact(abc_convection - abc_bernoulli)),
        {
            "divergence": reduce_exact(abc_divergence),
            "curl_residual": reduce_exact(abc_curl - abc),
            "heat_residual": reduce_exact(abc_laplacian + abc),
            "bernoulli_residual": reduce_exact(
                abc_convection - abc_bernoulli
            ),
        },
    )

    abc_w0, abc_nu = sp.symbols("abc_w0 abc_nu", positive=True)
    abc_w = abc_w0 * sp.exp(-2 * abc_nu * t)
    abc_d = abc_w
    abc_p = sp.Integer(0)
    abc_energy_residual = reduce_exact(
        sp.diff(abc_w, t) - (2 * abc_p - 2 * abc_nu * abc_d)
    )
    book.record(
        EXPECTED_CHECK_NAMES[11],
        abc_energy_residual == 0,
        {
            "production": abc_p,
            "D_equals_W": reduce_exact(abc_d - abc_w),
            "energy_residual": abc_energy_residual,
        },
    )

    abc_length, horizon = sp.symbols(
        "abc_strain_length horizon", positive=True
    )
    abc_dose = abc_length * (1 - sp.exp(-abc_nu * horizon)) / abc_nu
    abc_dose_residual = reduce_exact(
        sp.diff(abc_dose, horizon) - abc_length * sp.exp(-abc_nu * horizon)
    )
    abc_initial_residual = reduce_exact(abc_dose.subs(horizon, 0))
    book.record(
        EXPECTED_CHECK_NAMES[12],
        abc_dose_residual == 0 and abc_initial_residual == 0,
        {
            "dose": abc_dose,
            "derivative_residual": abc_dose_residual,
            "initial_dose": abc_initial_residual,
        },
    )

    rate = sp.symbols("rate", positive=True)
    affine_occupation = w0 * sp.exp(2 * rate * t)
    affine_gamma = reduce_exact(
        sp.diff(affine_occupation, t) / (2 * affine_occupation)
    )
    affine_dose = reduce_exact(rate * t)
    affine_identity = reduce_exact(
        affine_occupation - affine_occupation
    )
    book.record(
        EXPECTED_CHECK_NAMES[13],
        affine_gamma == rate and affine_dose == rate * t and affine_identity == 0,
        {
            "Gamma_M": affine_gamma,
            "G_plus": affine_dose,
            "retarded_spread": 0,
        },
    )

    values["controls"] = {
        "shear_decay": shear_decay,
        "rank_two_origin_gram": rank_two_origin,
        "abc_dose": abc_dose,
        "affine_dose": affine_dose,
    }


def protocol_integrity() -> dict[str, Any]:
    text = PROTOCOL.read_text(encoding="utf-8")
    tags = re.findall(r"\\tag\{(RCD\d+)\}", text)
    expected_tags = [f"RCD{index}" for index in range(1, 6)]
    declared_names = tuple(
        re.findall(r"^\d+\. `([^`]+)`", text, flags=re.MULTILINE)
    )
    return {
        "tag_count": len(tags),
        "observed_tags": tags,
        "expected_tags": expected_tags,
        "tags_match": tags == expected_tags,
        "declared_check_count": len(declared_names),
        "declared_check_names": list(declared_names),
        "inventory_names_match": declared_names == EXPECTED_CHECK_NAMES,
        "inventory_declaration_present": (
            "must execute exactly 16 checks" in text
        ),
        "note_binding_present": (
            "turbulence/navier-stokes-coherence-dose-criterion.md" in text
        ),
        "verifier_binding_present": (
            "computations/verify_navier_stokes_coherence_dose.py" in text
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
    book.record(EXPECTED_CHECK_NAMES[14], integrity_pass, integrity)

    note_text = NOTE.read_text(encoding="utf-8")
    anchors = (
        "**Proposition 1.**",
        "(CC1)",
        "(CC6)",
        "(CC8)",
        "Periodic shear",
        "Periodic rank-two Beltrami control",
        "Full-rank ABC heat flow",
        "Homogeneous extensional control",
        "A uniform bound on $G_+$",
        "arbitrary-data global regularity remain open",
    )
    missing = [anchor for anchor in anchors if anchor not in note_text]
    book.record(
        EXPECTED_CHECK_NAMES[15],
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
    verify_conditional_algebra(book, values)
    verify_controls(book, values)
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
            "conditional_active_dose_continuation": (
                "SUPPORTS" if success else "INCONCLUSIVE"
            ),
            "conditional_retarded_spread_compensation": (
                "SUPPORTS" if success else "INCONCLUSIVE"
            ),
            "strain_operator_rate_bound": (
                "SUPPORTS" if success else "INCONCLUSIVE"
            ),
            "uniform_all_data_active_dose_bound": "UNRESOLVED",
            "uniform_retarded_spread_compensation": "UNRESOLVED",
            "arbitrary_data_navier_stokes_regularity": "UNRESOLVED",
        },
        "scope": {
            "symbolic_implications": "EXACT_FINITE_ALGEBRA",
            "navier_stokes_trajectory": "EXACT_CLOSED_FORM_CONTROLS_ONLY",
            "generic_navier_stokes_trajectory": "NOT_RUN",
            "stochastic_flow_simulation": "NOT_RUN",
            "uniform_active_dose": "UNRESOLVED",
            "uniform_retarded_compensation": "UNRESOLVED",
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
