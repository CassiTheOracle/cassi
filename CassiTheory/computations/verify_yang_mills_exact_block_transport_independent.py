#!/usr/bin/env python3
"""Independently qualify the finite-block conditional transport receipt."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "yang-mills-exact-block-transport-qualification-prereg.md"
PRIMARY_SOURCE = ROOT / "computations" / "verify_yang_mills_exact_block_transport.py"
PRIMARY_RECEIPT = ROOT / "runs" / "yang_mills_exact_block_transport" / "verification-v3.json"
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_exact_block_transport" / "verification-independent-v3.json"

CUTOFFS = (1, 2, 3, 4, 5)
COUPLINGS = (0.25, 1.0, 4.0, 16.0)
BOUNDARY_ANGLES = tuple(k / 8.0 for k in range(9))
SCORE_OFFSETS = (1, 2)
TOLERANCE = 1.0e-9


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_independent_module() -> Any:
    sys.path.insert(0, str(SOURCE.parent))
    try:
        return importlib.import_module("verify_yang_mills_exact_block_spectrum_independent")
    except ModuleNotFoundError as error:
        if error.name != "verify_yang_mills_exact_block_spectrum_independent":
            raise
        return importlib.import_module("computations.verify_yang_mills_exact_block_spectrum_independent")


def load_primary_receipt() -> dict[str, Any]:
    if not PRIMARY_RECEIPT.exists():
        raise FileNotFoundError(f"missing primary transport receipt: {PRIMARY_RECEIPT}")
    record = json.loads(PRIMARY_RECEIPT.read_text(encoding="utf-8"))
    if record.get("execution") != "PASS":
        raise ValueError("primary transport receipt is not execution PASS")
    if record.get("source_sha256") != sha256(PRIMARY_SOURCE):
        raise ValueError("primary transport source hash does not match its receipt")
    if record.get("protocol_sha256") != sha256(PROTOCOL):
        raise ValueError("transport protocol hash does not match its receipt")
    return record


def independent_representation_bound(module: Any, max_cutoff: int) -> dict[str, Any]:
    max_vertex_norm_error = 0.0
    triple_count = 0
    for a in range(max_cutoff + 1):
        for b in range(max_cutoff + 1):
            for c in range(abs(a - b), a + b + 1, 2):
                table = np.asarray([
                    [
                        [module._three_j(a, b, c, ma, mb, mc)
                         for mc in module._doubled_range(c)]
                        for mb in module._doubled_range(b)
                    ]
                    for ma in module._doubled_range(a)
                ], dtype=float)
                max_vertex_norm_error = max(
                    max_vertex_norm_error,
                    abs(float(np.sum(table * table)) - 1.0),
                )
                triple_count += 1
    max_metric_error = 0.0
    for spin in range(max_cutoff + 1):
        labels = tuple(module._doubled_range(spin))
        metric = np.asarray([
            [module._metric(spin, m, n) for n in labels]
            for m in labels
        ], dtype=float)
        max_metric_error = max(
            max_metric_error,
            float(np.max(np.abs(metric @ metric.T - np.eye(spin + 1)))),
        )
    return {
        "pass": max_vertex_norm_error <= 1.0e-12 and max_metric_error <= 1.0e-12,
        "triple_count": triple_count,
        "maximum_vertex_norm_error": max_vertex_norm_error,
        "maximum_metric_orthogonality_error": max_metric_error,
        "pointwise_bound": (1.0 + max_vertex_norm_error) ** 2,
    }


def make_record() -> dict[str, Any]:
    primary = load_primary_receipt()
    independent = load_independent_module()
    schedule = primary["schedule"]
    max_cutoff = max(int(value) for value in schedule["cutoffs_doubled"])
    checks: dict[str, Any] = {}

    independent_bound = independent_representation_bound(independent, max_cutoff + max(SCORE_OFFSETS))
    primary_bound = primary["checks"]["representation_bound"]
    checks["independent_representation_bound"] = {
        **independent_bound,
        "matches_primary_bound": abs(
            independent_bound["pointwise_bound"] - primary_bound["pointwise_bound"]
        ) <= 1.0e-12,
    }

    nodal = independent.nodal_control()
    nodal_family = independent.nodal_family_endpoint_check()
    primary_nodal = primary["checks"]["analytic_nodal_control"]
    nodal_pass = bool(
        nodal["exact_matrix_deviation"] <= 1.0e-9
        and nodal["identity_deviation"] <= 1.0e-9
        and nodal["center_deviation"] <= 1.0e-9
        and nodal["center_sign_negative"]
        and nodal["analytic_root_residual"] <= 1.0e-12
        and nodal["ground_energy_deviation"] <= 1.0e-9
        and nodal["basis_unit_deviation"] <= 1.0e-9
        and nodal_family["passed"]
    )
    checks["independent_nodal_control"] = {
        "pass": nodal_pass,
        "nodal_control": nodal,
        "nodal_family": nodal_family,
        "primary_center_amplitude_deviation": abs(
            nodal["center_amplitude"] - primary_nodal["identity_and_center_amplitudes"][1]
        ),
    }

    reference = independent._ritz(1, 0.25)
    # The primary receipt does not duplicate vectors in every row; compare the
    # independent eigenvector against the sealed exact-block input instead.
    exact_receipt_path = ROOT / "runs" / "yang_mills_exact_block_spectrum" / "verification.json"
    exact_receipt = json.loads(exact_receipt_path.read_text(encoding="utf-8"))
    exact_vector = np.asarray(exact_receipt["spectrum"]["J1_x1/4"]["vector"], dtype=float)
    phase_aligned_error = float(np.max(np.abs(reference["alpha"] - exact_vector)))
    independent_lower_bound = float(
        abs(reference["alpha"][0])
        - independent_bound["pointwise_bound"] * np.sum(np.abs(reference["alpha"][1:]))
    )
    primary_lower_bound = float(
        primary["rows"][0]["positivity"]["coefficient_lower_bound"]
    )
    checks["independent_ritz_positive_row"] = {
        "pass": phase_aligned_error <= TOLERANCE and independent_lower_bound > 0.0,
        "vector_max_error": phase_aligned_error,
        "independent_coefficient_lower_bound": independent_lower_bound,
        "primary_coefficient_lower_bound": primary_lower_bound,
    }

    rows = primary["rows"]
    expected_rows = len(CUTOFFS) * len(COUPLINGS) * len(BOUNDARY_ANGLES)
    nodal_rows = [
        row for row in rows
        if row["cutoff_doubled"] == 1
        and row["coupling"] == "1"
    ]
    positive_rows = [
        row for row in rows
        if row["score_status"] == "DEFINED_ZERO_BY_BOUNDARY_ISOMETRY"
    ]
    unproven_rows = [
        row for row in rows
        if row["score_status"] == "UNDEFINED_NO_POSITIVITY_CERTIFICATE"
    ]
    checks["row_partition"] = {
        "pass": (
            len(rows) == expected_rows
            and len(nodal_rows) == len(BOUNDARY_ANGLES)
            and len(positive_rows) + len(nodal_rows) + len(unproven_rows) == len(rows)
            and all(row["theta_squared_galerkin"] is None for row in nodal_rows + unproven_rows)
        ),
        "actual_rows": len(rows),
        "expected_rows": expected_rows,
        "certified_positive_rows": len(positive_rows),
        "certified_nodal_rows": len(nodal_rows),
        "unproven_rows": len(unproven_rows),
    }

    score_blocks = primary["score_blocks"]
    checks["zero_score_blocks"] = {
        "pass": all(
            block["b_norm"] == 0.0
            and block["theta_squared_galerkin"] == 0.0
            and block["poisson_residual"] <= 1.0e-8
            for block in score_blocks.values()
        ),
        "count": len(score_blocks),
    }
    checks["classification_guard"] = {
        "pass": primary["classification"] == "INCONCLUSIVE",
        "primary_classification": primary["classification"],
        "reason": "zero boundary score and nodal/unproven positivity rows cannot support a positive transport claim",
    }
    checks_pass = all(bool(value.get("pass", False)) for value in checks.values())
    source_inputs = (SOURCE, PROTOCOL, PRIMARY_SOURCE, PRIMARY_RECEIPT, exact_receipt_path)
    return {
        "schema": "cassi.yang-mills.exact-block-transport-independent.v1",
        "execution": "PASS" if checks_pass else "FAIL",
        "classification": "INCONCLUSIVE",
        "source_sha256": sha256(SOURCE),
        "protocol_sha256": sha256(PROTOCOL),
        "inputs": {
            path.relative_to(ROOT).as_posix(): sha256(path)
            for path in source_inputs
        },
        "checks": checks,
        "summary": {
            "primary_rows": len(rows),
            "primary_score_blocks": len(score_blocks),
            "independent_checks": len(checks),
        },
        "scope": (
            "independent finite-cutoff qualification only; no positive transport, "
            "cutoff-removal, thermodynamic, continuum, or mass-gap claim"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or DEFAULT_OUTPUT
    if output.exists():
        parser.error(f"refusing to overwrite existing receipt: {output}")
    record = make_record()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(
        f"wrote {output}: execution {record['execution']}; "
        f"scientific classification {record['classification']}",
        flush=True,
    )
    return 0 if record["execution"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
