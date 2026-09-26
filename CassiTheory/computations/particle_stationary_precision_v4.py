#!/usr/bin/env python3
"""Run the frozen v4 higher-precision particle continuation campaign."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

import particle_stationary_precision_v3 as campaign


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "20260902_particle_stationary_precision_v4"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
MANIFEST_PATH = ROOT / "computations" / "particle_stationary_precision_v4_manifest.json"
ABS_TOL = 1.0e-8
REL_TOL = 1.0e-6


class PrecisionV4Failure(RuntimeError):
    """Raised when a frozen v4 source requirement fails."""


def load_source(device: torch.device) -> tuple[dict[str, torch.nn.Parameter], dict[str, Any]]:
    if campaign.sha256_file(campaign.SOURCE_ARTIFACT) != campaign.SOURCE_ARTIFACT_SHA256:
        raise PrecisionV4Failure("source artifact hash mismatch")
    source_results = campaign.read_json(campaign.SOURCE_RESULTS)
    source_verification = campaign.read_json(campaign.SOURCE_VERIFICATION)
    source_arm = source_results.get("arms", {}).get(f"P:{campaign.SOURCE_BASIN}")
    if not isinstance(source_arm, dict):
        raise PrecisionV4Failure("selected source arm is absent")
    if source_arm.get("artifact_sha256") != campaign.SOURCE_ARTIFACT_SHA256:
        raise PrecisionV4Failure("selected source receipt hash mismatch")
    if source_results.get("primary_verdict") != "PASS—Q2-QUALIFIED PRIMARY BACKGROUND":
        raise PrecisionV4Failure("selected source receipt verdict mismatch")
    if source_verification.get("pass") is not True or source_verification.get("mismatches"):
        raise PrecisionV4Failure("selected source verification is not clean")

    arrays = campaign.recovery.load_arrays(campaign.SOURCE_ARTIFACT)
    schema_failures = campaign.recovery.validate_npz_arrays(arrays, "P")
    if schema_failures:
        raise PrecisionV4Failure(f"source artifact schema failure: {schema_failures}")
    grid = campaign.stationary.make_grid("P", device)
    raw, reconstruction = campaign.recovery.reconstruct_raw(arrays, grid)
    if (
        not reconstruction["raw_finite"]
        or reconstruction["maximum_relative_inf"] > campaign.recovery.ROUNDTRIP_TOL
    ):
        raise PrecisionV4Failure(f"source reconstruction failure: {reconstruction}")
    diagnostics, _ = campaign.stationary.diagnostics(raw, grid)
    scalar_checks: dict[str, Any] = {}
    for name, frozen in campaign.SOURCE_SCALARS.items():
        measured = float(diagnostics[name])
        tolerance = ABS_TOL + REL_TOL * abs(frozen)
        error = abs(measured - frozen)
        scalar_checks[name] = {
            "measured": measured,
            "frozen": frozen,
            "error": error,
            "tolerance": tolerance,
            "pass": error <= tolerance,
        }
    if not all(row["pass"] for row in scalar_checks.values()):
        raise PrecisionV4Failure(f"source scalar mismatch: {scalar_checks}")
    return raw, {
        "artifact": str(campaign.SOURCE_ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": campaign.SOURCE_ARTIFACT_SHA256,
        "schema": {
            name: {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "c_contiguous": bool(value.flags.c_contiguous),
                "finite": bool(np.all(np.isfinite(value))),
            }
            for name, value in arrays.items()
        },
        "reconstruction": reconstruction,
        "scalars": scalar_checks,
    }


def configure_campaign() -> None:
    campaign.RUN_DIR = RUN_DIR
    campaign.PREFLIGHT_PATH = PREFLIGHT_PATH
    campaign.RESULTS_PATH = RESULTS_PATH
    campaign.MANIFEST_PATH = MANIFEST_PATH
    campaign.load_source = load_source


def main() -> int:
    configure_campaign()
    return campaign.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            json.dumps(
                {
                    "verdict": "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT",
                    "error": f"{type(error).__name__}: {error}",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        raise SystemExit(1)
