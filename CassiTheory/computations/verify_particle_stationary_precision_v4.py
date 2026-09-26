#!/usr/bin/env python3
"""Independently verify the frozen v4 precision continuation campaign."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import verify_particle_stationary_precision_v3 as verifier


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "20260902_particle_stationary_precision_v4"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
VERIFICATION_PATH = RUN_DIR / "verification.json"
MANIFEST_PATH = ROOT / "computations" / "particle_stationary_precision_v4_manifest.json"


def configure_verifier() -> None:
    verifier.RUN_DIR = RUN_DIR
    verifier.PREFLIGHT_PATH = PREFLIGHT_PATH
    verifier.RESULTS_PATH = RESULTS_PATH
    verifier.VERIFICATION_PATH = VERIFICATION_PATH
    verifier.MANIFEST_PATH = MANIFEST_PATH


def main(argv: Sequence[str] | None = None) -> int:
    configure_verifier()
    return verifier.main(argv)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            json.dumps(
                {
                    "pass": False,
                    "verdict": "INCONCLUSIVE—EXECUTION OR VERIFICATION",
                    "error": f"{type(error).__name__}: {error}",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        raise SystemExit(1)
