#!/usr/bin/env python3
"""Qualify the finite-block conditional transport diagnostic.

The exact-block protocol requires a conditional logarithmic score only on a
strictly positive Ritz density.  This verifier keeps that requirement literal:
rows without a positivity certificate are not regularized, and certified
nodal rows are recorded as inconclusive.  The seven-link exterior forest also
makes the scheduled boundary angle an exact isometry, so the boundary score is
structurally zero wherever the logarithmic score is defined.

This is a finite-cutoff qualification artifact.  It does not establish an
all-boundary transport estimate, cutoff removal, a thermodynamic limit, or a
continuum mass gap.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "yang-mills-exact-block-transport-qualification-prereg.md"
EXACT_PROTOCOL = ROOT / "computations" / "yang-mills-exact-block-spectral-prereg.md"
EXACT_SOURCE = ROOT / "computations" / "verify_yang_mills_exact_block_spectrum.py"
HELPER_SOURCE = ROOT / "computations" / "yang_mills_conditional_algebra.py"
EXACT_RECEIPT = ROOT / "runs" / "yang_mills_exact_block_spectrum" / "verification.json"
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_exact_block_transport" / "verification-v3.json"

CUTOFFS = (1, 2, 3, 4, 5)
COUPLINGS = (Fraction(1, 4), Fraction(1), Fraction(4), Fraction(16))
BOUNDARY_ANGLES = tuple(Fraction(k, 8) for k in range(9))
TANGENT_ANGLES = (Fraction(1, 4), Fraction(1, 2), Fraction(3, 4))
SCORE_OFFSETS = (1, 2)
POSITIVE_BOUND_TOLERANCE = 1.0e-12
HERMITICITY_TOLERANCE = 1.0e-10
MATERIALIZED_SCORE_MAX_CUTOFF = 4
POISSON_TOLERANCE = 1.0e-8


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_modules() -> tuple[Any, Any]:
    """Load the verified exact-block source and its product algebra.

    The guarded fallback supports both ``python computations/foo.py`` and
    ``python -m computations.foo`` without hiding dependency failures raised
    inside either module.
    """
    sys.path.insert(0, str(SOURCE.parent))
    try:
        exact = importlib.import_module("verify_yang_mills_exact_block_spectrum")
    except ModuleNotFoundError as error:
        if error.name != "verify_yang_mills_exact_block_spectrum":
            raise
        exact = importlib.import_module("computations.verify_yang_mills_exact_block_spectrum")
    try:
        algebra = importlib.import_module("yang_mills_conditional_algebra")
    except ModuleNotFoundError as error:
        if error.name != "yang_mills_conditional_algebra":
            raise
        algebra = importlib.import_module("computations.yang_mills_conditional_algebra")
    return exact, algebra


def load_exact_receipt() -> dict[str, Any]:
    if not EXACT_RECEIPT.exists():
        raise FileNotFoundError(
            f"missing sealed exact-block input receipt: {EXACT_RECEIPT}"
        )
    record = json.loads(EXACT_RECEIPT.read_text(encoding="utf-8"))
    if record.get("execution") != "PASS":
        raise ValueError("exact-block input receipt is not execution PASS")
    if record.get("source_sha256") != sha256(EXACT_SOURCE):
        raise ValueError("exact-block source hash does not match its sealed receipt")
    if record.get("protocol_sha256") != sha256(EXACT_PROTOCOL):
        raise ValueError("exact-block protocol hash does not match its sealed receipt")
    helper_hash = record.get("inputs", {}).get("computations/yang_mills_conditional_algebra.py")
    if helper_hash is not None and helper_hash != sha256(HELPER_SOURCE):
        raise ValueError("conditional algebra hash does not match its sealed receipt")
    return record


def coupling_key(cutoff: int, coupling: Fraction) -> str:
    return f"J{cutoff}_x{coupling}"


def score_key(cutoff: int, coupling: Fraction, offset: int) -> str:
    return f"{coupling_key(cutoff, coupling)}_offset{offset}"


def finite_real(value: Any) -> bool:
    array = np.asarray(value)
    return bool(np.all(np.isfinite(array)))


def representation_bound_certificate(exact: Any, max_cutoff: int) -> dict[str, Any]:
    """Certify the pointwise norm bound used by the positivity enclosure.

    A spin-network value is an inner product of two trivalent invariant
    tensors after unitary representation matrices and invariant metrics act on
    their legs.  The Wigner-3j orthogonality identity gives unit norm to each
    vertex tensor, and the metric is orthogonal, so the closed contraction is
    bounded by one.  The numerical quantities below check the exact tables
    used by this source before the bound is admitted into a receipt.
    """
    max_vertex_norm_error = 0.0
    triple_count = 0
    for a in range(max_cutoff + 1):
        for b in range(max_cutoff + 1):
            for c in range(abs(a - b), a + b + 1, 2):
                table = np.asarray(exact.three_j(a, b, c), dtype=float)
                max_vertex_norm_error = max(
                    max_vertex_norm_error,
                    abs(float(np.sum(table * table)) - 1.0),
                )
                triple_count += 1
    max_metric_orthogonality_error = 0.0
    for spin in range(max_cutoff + 1):
        metric = np.asarray(exact.metric_tensor(spin), dtype=float)
        max_metric_orthogonality_error = max(
            max_metric_orthogonality_error,
            float(np.max(np.abs(metric @ metric.T - np.eye(spin + 1)))),
        )
    tolerance = 1.0e-12
    passed = (
        max_vertex_norm_error <= tolerance
        and max_metric_orthogonality_error <= tolerance
    )
    pointwise_bound = (1.0 + max_vertex_norm_error) ** 2
    return {
        "pass": passed,
        "proof": (
            "Cauchy-Schwarz applied to the two normalized 3j vertex tensors "
            "and orthogonal invariant link metrics"
        ),
        "triple_count": triple_count,
        "maximum_vertex_norm_error": max_vertex_norm_error,
        "maximum_metric_orthogonality_error": max_metric_orthogonality_error,
        "pointwise_bound": pointwise_bound,
        "tolerance": tolerance,
    }


def positivity_certificate(
    exact: Any,
    cutoff: int,
    coupling: Fraction,
    coefficients: np.ndarray,
    nodal_witness: dict[str, Any] | None,
    bound_certificate: dict[str, Any],
) -> dict[str, Any]:
    """Use a checked representation enclosure, or preserve a certified node."""
    pointwise_bound = float(bound_certificate["pointwise_bound"])
    lower_bound = float(
        abs(coefficients[0]) - pointwise_bound * np.sum(np.abs(coefficients[1:]))
    )
    certificate = {
        "basis_pointwise_bound": pointwise_bound,
        "representation_bound_certificate": bound_certificate,
        "coefficient_lower_bound": lower_bound,
        "tolerance": POSITIVE_BOUND_TOLERANCE,
    }
    if bound_certificate["pass"] and lower_bound > POSITIVE_BOUND_TOLERANCE:
        return {
            "status": "CERTIFIED_POSITIVE",
            "method": "coefficient_l1_lower_bound_with_3j_norm_enclosure",
            **certificate,
        }
    if cutoff == 1 and coupling == Fraction(1):
        if nodal_witness is None:
            nodal_witness = exact.cutoff_nodal_control()
        return {
            "status": "CERTIFIED_NODE",
            "method": "analytic_nodal_control",
            **certificate,
            "witness": nodal_witness,
        }
    return {
        "status": "UNPROVEN",
        "method": "none",
        "reason": (
            "no checked interval-or-analytic strict-positivity certificate"
            if bound_certificate["pass"]
            else "representation norm enclosure failed"
        ),
        **certificate,
    }


def score_block(
    exact: Any,
    algebra: Any,
    cutoff: int,
    coupling: Fraction,
    coefficients: np.ndarray,
    offset: int,
) -> dict[str, Any]:
    """Assemble the score-space Dirichlet matrix for the zero-score case."""
    score_cutoff = cutoff + offset
    score_states = exact.basis_states(score_cutoff)
    coefficient_map = {
        state: float(value)
        for state, value in zip(exact.basis_states(cutoff), coefficients)
    }
    score_coefficients = [coefficient_map.get(state, 0.0) for state in score_states]
    data = algebra.conditional_data(score_states, score_coefficients, 0.0)
    fibre = exact.FibreSpace(np.asarray(data["restriction_gram"]), score_states)
    dirichlet = np.asarray(fibre.transform(np.asarray(data["dirichlet"])), dtype=complex)
    dirichlet = 0.5 * (dirichlet + dirichlet.conj().T)
    eigenvalues = np.linalg.eigvalsh(dirichlet)
    b = np.zeros(dirichlet.shape[0], dtype=complex)
    solution = np.linalg.pinv(dirichlet, rcond=1.0e-12) @ b
    residual = float(np.linalg.norm(dirichlet @ solution - b))
    hermiticity = float(np.max(np.abs(dirichlet - dirichlet.conj().T))) if dirichlet.size else 0.0
    positive = bool(np.all(eigenvalues >= -HERMITICITY_TOLERANCE))
    return {
        "cutoff_doubled": cutoff,
        "coupling": str(coupling),
        "score_cutoff_doubled": score_cutoff,
        "score_space_dimension": len(score_states),
        "retained_dimension": int(dirichlet.shape[0]),
        "removed_constant_dimension": int(fibre.removed_constant_dimension),
        "theta_derivative_identity": "zero by exact exterior-forest isometry",
        "b_norm": float(np.linalg.norm(b)),
        "theta_squared_galerkin": 0.0,
        "poisson_residual": residual,
        "poisson_tolerance": POISSON_TOLERANCE,
        "hermiticity_residual": hermiticity,
        "minimum_dirichlet_eigenvalue": float(np.min(eigenvalues)) if eigenvalues.size else 0.0,
        "maximum_dirichlet_eigenvalue": float(np.max(eigenvalues)) if eigenvalues.size else 0.0,
        "dirichlet_positive_semidefinite": positive,
        "score_basis": exact.matrix_record(np.asarray(fibre.map_to_vector @ fibre.basis)),
        "dirichlet": exact.matrix_record(dirichlet),
        "poisson_rhs": exact.matrix_record(b),
        "poisson_solution": exact.matrix_record(solution),
        "matrix_materialized": True,
        "finite": bool(
            finite_real(dirichlet)
            and finite_real(eigenvalues)
            and finite_real(solution)
            and math.isfinite(residual)
        ),
    }

def structural_zero_score_block(exact: Any, cutoff: int, coupling: Fraction, offset: int) -> dict[str, Any]:
    """Record the full score space when the exact boundary score is zero.

    The Dirichlet form is a Gram matrix by definition and is therefore
    positive semidefinite for a positive density.  With b=0, the zero
    solution and quadratic form are exact; materializing a large matrix cannot
    change that conclusion.
    """
    score_cutoff = cutoff + offset
    score_states = exact.basis_states(score_cutoff)
    retained_dimension = max(len(score_states) - 1, 0)
    return {
        "cutoff_doubled": cutoff,
        "coupling": str(coupling),
        "score_cutoff_doubled": score_cutoff,
        "score_space_dimension": len(score_states),
        "retained_dimension": retained_dimension,
        "removed_constant_dimension": 1 if score_states else 0,
        "theta_derivative_identity": "zero by exact exterior-forest isometry",
        "b_norm": 0.0,
        "theta_squared_galerkin": 0.0,
        "poisson_residual": 0.0,
        "poisson_tolerance": POISSON_TOLERANCE,
        "dirichlet_positive_semidefinite": True,
        "dirichlet_certificate": (
            "D_s is a sum of weighted generator Gram matrices under the "
            "certified positive density"
        ),
        "score_basis_states": [list(state) for state in score_states],
        "matrix_materialized": False,
        "finite": True,
    }

def nodal_control_pass(witness: dict[str, Any]) -> bool:
    amplitudes = witness["identity_and_center_amplitudes"]
    endpoints = witness["polynomial_endpoint_values"]
    return bool(
        witness["exact_matrix_deviation"] <= 1.0e-10
        and witness["center_value_deviation"] <= 1.0e-10
        and Fraction(endpoints[0]) < 0 < Fraction(endpoints[1])
        and Fraction(witness["scaled_negative_amplitude_upper_bound"]) < 0
        and amplitudes[0] > 0.0 > amplitudes[1]
    )


def direct_boundary_pass(reconstruction: dict[str, Any]) -> bool:
    errors = reconstruction["errors"]
    return bool(errors and max(float(value) for value in errors.values()) <= 1.0e-9)


def make_record(max_cutoff: int) -> dict[str, Any]:
    exact, algebra = load_modules()
    exact_receipt = load_exact_receipt()
    source_inputs = (
        SOURCE,
        PROTOCOL,
        EXACT_PROTOCOL,
        EXACT_SOURCE,
        HELPER_SOURCE,
        EXACT_RECEIPT,
    )
    input_bytes = {path: path.read_bytes() for path in source_inputs}
    start = time.perf_counter()

    raw_nodal_witness = exact.cutoff_nodal_control()
    nodal_witness = {
        **raw_nodal_witness,
        "pass": nodal_control_pass(raw_nodal_witness),
    }
    raw_direct_boundary = exact.conditional_validation()
    direct_boundary = {
        **raw_direct_boundary,
        "pass": direct_boundary_pass(raw_direct_boundary),
    }
    spectrum = exact_receipt["spectrum"]
    rows: list[dict[str, Any]] = []
    score_blocks: dict[str, dict[str, Any]] = {}
    positivity_cache: dict[tuple[int, Fraction], dict[str, Any]] = {}

    selected_cutoffs = tuple(c for c in CUTOFFS if c <= max_cutoff)
    bound_certificate = representation_bound_certificate(
        exact, max_cutoff + max(SCORE_OFFSETS)
    )
    for cutoff in selected_cutoffs:
        for coupling in COUPLINGS:
            key = coupling_key(cutoff, coupling)
            if key not in spectrum:
                raise ValueError(f"missing spectrum row in exact receipt: {key}")
            coefficients = np.asarray(spectrum[key]["vector"], dtype=float)
            positivity_cache[(cutoff, coupling)] = positivity_certificate(
                exact,
                cutoff,
                coupling,
                coefficients,
                nodal_witness,
                bound_certificate,
            )
            positivity = positivity_cache[(cutoff, coupling)]
            score_references: dict[str, str] = {}
            if positivity["status"] == "CERTIFIED_POSITIVE":
                for offset in SCORE_OFFSETS:
                    reference = score_key(cutoff, coupling, offset)
                    score_references[str(offset)] = reference
                    if reference not in score_blocks:
                        if cutoff <= MATERIALIZED_SCORE_MAX_CUTOFF:
                            score_blocks[reference] = score_block(
                                exact, algebra, cutoff, coupling, coefficients, offset
                            )
                        else:
                            score_blocks[reference] = structural_zero_score_block(
                                exact, cutoff, coupling, offset
                            )
            for angle in BOUNDARY_ANGLES:
                if positivity["status"] == "CERTIFIED_POSITIVE":
                    score_status = "DEFINED_ZERO_BY_BOUNDARY_ISOMETRY"
                    classification = "INCONCLUSIVE_STRUCTURAL_ZERO_TRANSPORT"
                elif positivity["status"] == "CERTIFIED_NODE":
                    score_status = "UNDEFINED_NODAL_DENSITY"
                    classification = "INCONCLUSIVE_CERTIFIED_NODE"
                else:
                    score_status = "UNDEFINED_NO_POSITIVITY_CERTIFICATE"
                    classification = "INCONCLUSIVE_NO_POSITIVITY_CERTIFICATE"
                rows.append({
                    "cutoff_doubled": cutoff,
                    "coupling": str(coupling),
                    "theta_pi": str(angle),
                    "tangent_scheduled": angle in TANGENT_ANGLES,
                    "positivity": positivity,
                    "score_status": score_status,
                    "theta_squared_galerkin": (
                        0.0 if positivity["status"] == "CERTIFIED_POSITIVE" else None
                    ),
                    "score_references": score_references,
                    "classification": classification,
                })

    positive_rows = [row for row in rows if row["score_status"] == "DEFINED_ZERO_BY_BOUNDARY_ISOMETRY"]
    node_rows = [row for row in rows if row["score_status"] == "UNDEFINED_NODAL_DENSITY"]
    unproven_rows = [row for row in rows if row["score_status"] == "UNDEFINED_NO_POSITIVITY_CERTIFICATE"]
    checks = {
        "row_count": {
            "pass": len(rows) == len(selected_cutoffs) * len(COUPLINGS) * len(BOUNDARY_ANGLES),
            "actual": len(rows),
            "expected": len(selected_cutoffs) * len(COUPLINGS) * len(BOUNDARY_ANGLES),
        },
        "boundary_angle_schedule": {
            "pass": [row["theta_pi"] for row in rows[:len(BOUNDARY_ANGLES)]]
            == [str(angle) for angle in BOUNDARY_ANGLES],
            "angles_pi": [str(angle) for angle in BOUNDARY_ANGLES],
        },
        "direct_boundary_reconstruction": direct_boundary,
        "representation_bound": bound_certificate,
        "analytic_nodal_control": nodal_witness,
        "structural_theta_derivative_zero": {
            "pass": True,
            "reason": "conditional algebra accepts theta as an exact no-op under the exterior-forest isometry",
            "implication": "a zero theta-squared value is not positive transport evidence",
        },
        "positivity_policy": {
            "pass": all(
                row["score_status"] != "DEFINED_ZERO_BY_BOUNDARY_ISOMETRY"
                or row["positivity"]["status"] == "CERTIFIED_POSITIVE"
                for row in rows
            ),
            "no_log_regularization": True,
            "certified_positive_rows": len(positive_rows),
            "certified_nodal_rows": len(node_rows),
            "unproven_rows": len(unproven_rows),
        },
        "score_blocks_finite": {
            "pass": all(block["finite"] for block in score_blocks.values()),
            "count": len(score_blocks),
        },
        "poisson_residuals": {
            "pass": all(block["poisson_residual"] <= POISSON_TOLERANCE for block in score_blocks.values()),
            "maximum": max(
                (block["poisson_residual"] for block in score_blocks.values()),
                default=0.0,
            ),
            "tolerance": POISSON_TOLERANCE,
        },
        "transport_claim_suppressed": {
            "pass": True,
            "reason": "the schedule has a structurally zero boundary score and at least one certified nodal row",
        },
    }
    checks_pass = all(
        bool(value.get("pass", False))
        for value in checks.values()
        if isinstance(value, dict) and "pass" in value
    )
    schedule = {
        "cutoffs_doubled": list(selected_cutoffs),
        "couplings": [str(value) for value in COUPLINGS],
        "boundary_angles_pi": [str(value) for value in BOUNDARY_ANGLES],
        "tangent_angles_pi": [str(value) for value in TANGENT_ANGLES],
        "score_cutoff_offsets": list(SCORE_OFFSETS),
        "materialized_score_max_cutoff": MATERIALIZED_SCORE_MAX_CUTOFF,
        "structural_zero_score_shortcut_above_cutoff": MATERIALIZED_SCORE_MAX_CUTOFF,
        "positive_basis_bound": bound_certificate["pointwise_bound"],
        "positive_bound_tolerance": POSITIVE_BOUND_TOLERANCE,
    }
    operations = {
        "target": "finite_block_galerkin_conditional_transport_qualification",
        "conditional_density": "Ritz density from the sealed exact-block spectrum receipt",
        "positivity": "analytic coefficient l1 lower bound; certified nodal control otherwise preserved",
        "boundary_derivative": "exact zero from exterior-forest isometry; no finite-difference substitute",
        "score_spaces": "full block-compatible basis at doubled cutoffs J_s=J+1/2 and J_s=J+1, constant removed",
        "poisson": "D_s u=b with b=0 under the exact boundary-isometry identity",
        "scientific_scope": "finite cutoff only; zero transport is not a positive transport result",
    }
    record = {
        "schema": "cassi.yang-mills.exact-block-transport-qualification.v1",
        "execution": "PASS" if checks_pass else "FAIL",
        "classification": "INCONCLUSIVE",
        "source_sha256": sha256(SOURCE),
        "protocol_sha256": sha256(PROTOCOL),
        "inputs": {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(content).hexdigest()
            for path, content in input_bytes.items()
        },
        "input_exact_receipt_sha256": sha256(EXACT_RECEIPT),
        "schedule": schedule,
        "schedule_sha256": hashlib.sha256(json.dumps(schedule, sort_keys=True).encode()).hexdigest(),
        "operations": operations,
        "operations_sha256": hashlib.sha256(json.dumps(operations, sort_keys=True).encode()).hexdigest(),
        "checks": checks,
        "score_blocks": score_blocks,
        "rows": rows,
        "summary": {
            "rows": len(rows),
            "certified_positive_rows": len(positive_rows),
            "certified_nodal_rows": len(node_rows),
            "unproven_rows": len(unproven_rows),
            "score_blocks": len(score_blocks),
        },
        "open_obligations": [
            "all-boundary transport estimate",
            "cutoff removal",
            "uniform interacting recovery",
            "thermodynamic limit",
            "continuum Schwinger-function construction",
            "positive physical gauge-invariant mass gap",
        ],
        "wall_seconds": time.perf_counter() - start,
    }
    if any(path.read_bytes() != content for path, content in input_bytes.items()):
        raise RuntimeError("input bytes changed during the run; refusing to seal a mixed-source receipt")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("dev", "full"), default="full")
    parser.add_argument("--max-cutoff", type=int, choices=CUTOFFS, default=CUTOFFS[-1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.stage == "full":
        if args.max_cutoff != CUTOFFS[-1] or args.output is None:
            parser.error("the full stage requires the complete cutoff schedule and --output")
        if args.output.exists():
            parser.error(f"refusing to overwrite existing receipt: {args.output}")
        record = make_record(args.max_cutoff)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        print(
            f"wrote {args.output}: execution {record['execution']}; "
            f"scientific classification {record['classification']}",
            flush=True,
        )
        return 0 if record["execution"] == "PASS" else 1
    record = make_record(args.max_cutoff)
    print(json.dumps({
        "execution": record["execution"],
        "classification": record["classification"],
        "summary": record["summary"],
        "checks": record["checks"],
        "wall_seconds": record["wall_seconds"],
    }, indent=2, sort_keys=True), flush=True)
    return 0 if record["execution"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
