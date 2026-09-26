#!/usr/bin/env python3
"""Run the serialization-safe PA42 campaign on the precision background."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

import particle_physical_hessian as campaign


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "runs/20260902_particle_stationary_precision_v5/fields_block01.npz"
RUN_DIR = ROOT / "runs/20260903_particle_physical_hessian_precision_v2"
RESULTS_PATH = RUN_DIR / "results.json"
MODES_PATH = RUN_DIR / "eigenmodes.npz"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
MANIFEST_PATH = ROOT / "computations/particle_physical_hessian_precision_v2_manifest.json"
ARTIFACT_SHA256 = "ac4c54fa0e5ed61f73cb86b5e83d0061806fc2e5d1725894bad9e8e89457a61e"
OMEGA_C = 0.9619139451720476
FROZEN_BACKGROUND = {
    "physical_energy": 3.854183410304054,
    "physical_gradient_rms": 5.4712481264035785e-5,
    "cutoff_virial": 1.348199173228824e-4,
    "omega_c": OMEGA_C,
    "charge": 4.0,
}


def json_ready(value: Any) -> Any:
    """Convert scientific scalar leaves into strict-JSON values."""
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, np.ndarray):
        if value.ndim != 0:
            raise TypeError(f"non-scalar NumPy array at JSON boundary: {value.shape}")
        return json_ready(value.item())
    if isinstance(value, torch.Tensor):
        if value.ndim != 0:
            raise TypeError(f"non-scalar tensor at JSON boundary: {tuple(value.shape)}")
        return json_ready(value.detach().cpu().item())
    return value


def write_json_safe(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def configure_campaign() -> None:
    campaign.ARTIFACT = ARTIFACT
    campaign.RUN_DIR = RUN_DIR
    campaign.RESULTS_PATH = RESULTS_PATH
    campaign.MODES_PATH = MODES_PATH
    campaign.PREFLIGHT_PATH = PREFLIGHT_PATH
    campaign.MANIFEST_PATH = MANIFEST_PATH
    campaign.ARTIFACT_SHA256 = ARTIFACT_SHA256
    campaign.OMEGA_C = OMEGA_C
    campaign.FROZEN_BACKGROUND = dict(FROZEN_BACKGROUND)
    campaign.write_json = write_json_safe


def main() -> int:
    configure_campaign()
    return campaign.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except campaign.HessianFailure as error:
        write_json_safe(
            RESULTS_PATH,
            {
                "schema": "cassi.particle-physical-hessian.results.v1",
                "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "primary_status": "INCONCLUSIVE—IMPLEMENTATION OR HESSIAN PREFLIGHT",
                "error": str(error),
            },
        )
        print(f"HESSIAN FAILURE: {error}", file=sys.stderr)
        raise SystemExit(1)
