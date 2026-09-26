"""Independently verify the second disjoint real chronological receipt.

The reconstruction kernel is the previously independent verifier, not either
campaign runner.  This module binds it to the second source partition and its
own receipt schema, then rebuilds the slice and aggregate before accepting it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import verify_generation2_real_chronological_holdout as base


base.SCHEMA = "cassifi.generation2-real-chronological-holdout-pair2-verification.v1"
base.EXPERIMENT_ID = "generation2-real-chronological-holdout-pair2-v1"
base.RECEIPT = "CassiFI/_diag/generation2-real-chronological-holdout-pair2-v1.json"
base.OUTPUT = "CassiFI/_diag/generation2-real-chronological-holdout-pair2-verification-v1.json"
base.DEVELOPMENT_ROOT = (
    "CassiCosmos/_diag/matter_formation/energy_gaussian_s20260910_v0p5"
)
base.REGIME_A_ROOT = "CassiCosmos/_diag/matter_formation/attractor_ic2"
base.REGIME_B_ROOT = "CassiCosmos/_diag/matter_formation/attractor_ic7"
base.EXPECTED_SOURCES = tuple(
    sorted(
        set(base.EXPECTED_SOURCES)
        | {"CassiFI/run_generation2_real_chronological_holdout_pair2.py"}
    )
)


def _aggregate(reproduced: dict[str, object]) -> dict[str, object]:
    a = reproduced["regime_A"]
    b = reproduced["regime_B"]
    assert isinstance(a, dict) and isinstance(b, dict)
    a_holdout = a["holdout"]
    b_holdout = b["holdout"]
    assert isinstance(a_holdout, dict) and isinstance(b_holdout, dict)
    b_delta = float(b_holdout["guarded_vs_isotropic_delta"])
    return {
        "actor_count": 1,
        "regime_count": 2,
        "sequence": ["A-first", "A-repeat", "B-first", "B-repeat"],
        "A_holdout": {
            "world_count": 1,
            "source_root": a["source_root"],
            "causal_nrmse": float(a_holdout["causal_nrmse"]),
            "guarded_nrmse": float(a_holdout["guarded_nrmse"]),
            "isotropic_nrmse": float(a_holdout["isotropic_nrmse"]),
            "guarded_vs_isotropic_max_abs": float(
                a_holdout["guarded_vs_isotropic_max_abs"]
            ),
        },
        "B_holdout": {
            "world_count": 1,
            "source_root": b["source_root"],
            "causal_nrmse": float(b_holdout["causal_nrmse"]),
            "guarded_nrmse": float(b_holdout["guarded_nrmse"]),
            "isotropic_nrmse": float(b_holdout["isotropic_nrmse"]),
            "guarded_vs_isotropic_delta": b_delta,
            "positive_or_equal": b_delta <= base.NONWORSE_TOLERANCE,
            "release_support": int(b["after_second"]["guard_unique_regime_support"]),
            "anisotropic_basis_after_first": float(
                b["after_first"]["basis_coefficients"][1]
            ),
            "anisotropic_basis_after_second": float(
                b["after_second"]["basis_coefficients"][1]
            ),
        },
        "controls_passed": bool(reproduced["controls_passed"]),
        "slice_digest": base._digest(reproduced),
    }


def run(workspace: Path, receipt_path: Path) -> dict[str, object]:
    workspace = workspace.resolve(strict=True)
    receipt_path = receipt_path.resolve(strict=True)
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    if receipt.get("schema") != "cassifi.generation2-real-chronological-holdout-pair2.v1":
        raise base.RealHoldoutVerificationError("pair2 receipt schema differs")
    if receipt.get("experiment_id") != base.EXPERIMENT_ID or receipt.get("status") != "PASS":
        raise base.RealHoldoutVerificationError("pair2 receipt identity or status differs")
    expected_sources = base._source_manifest(workspace)
    if receipt.get("analysis_sources") != expected_sources:
        raise base.RealHoldoutVerificationError("pair2 source manifest differs")
    expected_partition = {
        "development": base.DEVELOPMENT_ROOT,
        "A": base.REGIME_A_ROOT,
        "B": base.REGIME_B_ROOT,
    }
    if receipt.get("source_partition") != expected_partition:
        raise base.RealHoldoutVerificationError("pair2 source partition differs")
    expected_fractions = {
        "first_chunk": base.CHUNK_ONE_FRACTION,
        "second_chunk_end": base.CHUNK_TWO_FRACTION,
        "holdout": 1.0 - base.CHUNK_TWO_FRACTION,
    }
    if receipt.get("training_fractions") != expected_fractions:
        raise base.RealHoldoutVerificationError("pair2 training fractions differ")
    expected_configuration = {
        "anisotropy_ridge": base.ANISOTROPY_RIDGE,
        "anisotropy_support_threshold": base.ANISOTROPY_SUPPORT_THRESHOLD,
        "min_anisotropic_worlds": base.MIN_ANISOTROPIC_WORLDS,
        "nonworse_tolerance": base.NONWORSE_TOLERANCE,
    }
    if receipt.get("configuration") != expected_configuration:
        raise base.RealHoldoutVerificationError("pair2 protocol differs")
    reproduced_slice = base._reproduce_slice(workspace, expected_sources)
    reproduced_slice["schema"] = (
        "cassifi.generation2-real-chronological-holdout-pair2-slice.v1"
    )
    base._assert_equal(receipt["slice"], reproduced_slice, "pair2.slice")
    reproduced_aggregate = _aggregate(reproduced_slice)
    base._assert_equal(receipt["aggregate"], reproduced_aggregate, "pair2.aggregate")
    return {
        "schema": base.SCHEMA,
        "experiment_id": base.EXPERIMENT_ID,
        "status": "VERIFIED",
        "receipt": str(receipt_path),
        "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "source_manifest_verified": True,
        "reconstructed_slice": True,
        "reconstructed_aggregate": True,
        "controls_passed": bool(reproduced_slice["controls_passed"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--receipt", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    receipt = (args.receipt or workspace / base.RECEIPT).resolve()
    output = (args.out or workspace / base.OUTPUT).resolve()
    result = run(workspace, receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(base._canonical(result) + b"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
