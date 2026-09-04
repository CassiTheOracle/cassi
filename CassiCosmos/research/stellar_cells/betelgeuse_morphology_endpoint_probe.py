#!/usr/bin/env python3
"""Successor check for the near-white endpoint of the ALMA false-color panels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


PARENT = Path("_diag/stellar_cells/betelgeuse_morphology.json")
OUTPUT = Path("_diag/stellar_cells/betelgeuse_morphology_v2.json")
PRIOR_RECEIPT_SHA256 = "1a0fbaf6e0a0ec2155f88cf777b187b45fb0449cad8d7729ecb6a17150333095"
SOURCE_SIZE = (1320, 1020)
CROP = (174, 7, 1125, 958)
GRID_N = 951
SKY_HALF_WIDTH_MAS = 45.0
DISK_RADIUS_MAS = 21.0
ENDPOINT_CHANNEL_MIN = 254
ENDPOINT_FRACTION_LIMIT = 0.10


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    prior_receipt_digest = digest(OUTPUT)
    if prior_receipt_digest != PRIOR_RECEIPT_SHA256:
        raise ValueError("unexpected prior endpoint receipt")
    prior_receipt = json.loads(OUTPUT.read_text(encoding="utf-8"))
    parent_digest = digest(PARENT)
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    if parent.get("schema") != "cassi.betelgeuse-morphology.v1":
        raise ValueError("unexpected parent schema")
    expected_parent_constants = {
        "grid_n": GRID_N,
        "sky_half_width_mas": SKY_HALF_WIDTH_MAS,
        "disk_radius_mas": DISK_RADIUS_MAS,
    }
    parent_constants = {
        key: parent.get("constants", {}).get(key)
        for key in expected_parent_constants
    }
    if parent_constants != expected_parent_constants:
        raise ValueError(f"parent grid/mask constants changed: {parent_constants}")

    axis = np.linspace(SKY_HALF_WIDTH_MAS, -SKY_HALF_WIDTH_MAS, GRID_N)
    x, y = np.meshgrid(axis, axis)
    disk = np.hypot(x, y) <= DISK_RADIUS_MAS
    x0, y0, x1, y1 = CROP

    source_checks: dict[str, object] = {}
    fractions: dict[str, float] = {}
    for band in ("B6", "B7", "B8"):
        frozen = parent["provenance"][band]
        parent_crop = frozen.get("sky_panel_bbox_xyxy")
        if parent_crop != list(CROP):
            raise ValueError(f"{band} parent crop changed: {parent_crop}")
        path = Path(frozen["saved_path"])
        actual_digest = digest(path)
        if actual_digest != frozen["sha256"]:
            raise ValueError(f"{band} source digest changed")
        with Image.open(path) as source:
            if source.size != SOURCE_SIZE:
                raise ValueError(f"{band} raster geometry changed: {source.size}")
            rgb = np.asarray(source.convert("RGB"), dtype=np.uint8)
        panel = rgb[y0:y1, x0:x1]
        if panel.shape[:2] != (GRID_N, GRID_N):
            raise ValueError(f"{band} crop geometry changed: {panel.shape[:2]}")
        endpoint = np.min(panel, axis=2) >= ENDPOINT_CHANNEL_MIN
        fractions[band] = float(np.mean(endpoint[disk]))
        source_checks[band] = {
            "path": path.as_posix(),
            "sha256": actual_digest,
            "matches_parent": True,
            "parent_crop_xyxy": parent_crop,
            "crop_matches_parent": True,
            "raster_size": list(source.size),
        }

    acceptable = max(fractions.values()) <= ENDPOINT_FRACTION_LIMIT
    parent_conditions = parent["gates"]["o1_conditions"]
    carried_conditions = {
        key: bool(parent_conditions[key])
        for key in (
            "all_pair_correlations_at_least_floor",
            "registered_mean_above_rotation_null_p95",
            "component_in_every_band",
        )
    }
    if not acceptable:
        o1 = "INCONCLUSIVE_RASTER_ENDPOINT_SATURATION"
    elif all(carried_conditions.values()):
        o1 = "SUPPORTS_RESOLUTION_STABLE_NONAXISYMMETRY"
    else:
        o1 = "DOES_NOT_SUPPORT_RESOLUTION_STABLE_NONAXISYMMETRY"

    report = {
        "schema": "cassi.betelgeuse-morphology-endpoint.v1",
        "preregistration": "research/stellar_cells/betelgeuse_morphology_endpoint_prereg.md",
        "integrity_replay": {
            "prior_receipt_sha256": prior_receipt_digest,
            "prior_integrity_replay": prior_receipt.get("integrity_replay"),
            "repair": "bind parent crop, grid, sky extent, and disk mask",
            "parent_constants": parent_constants,
            "statistics_changed": False,
        },
        "parent": {
            "path": PARENT.as_posix(),
            "sha256": parent_digest,
            "schema": parent["schema"],
            "verdicts": parent["verdicts"],
        },
        "frozen_constants": {
            "source_size": SOURCE_SIZE,
            "crop_xyxy": CROP,
            "grid_n": GRID_N,
            "sky_half_width_mas": SKY_HALF_WIDTH_MAS,
            "disk_radius_mas": DISK_RADIUS_MAS,
            "endpoint_all_channels_min_u8": ENDPOINT_CHANNEL_MIN,
            "endpoint_fraction_limit": ENDPOINT_FRACTION_LIMIT,
        },
        "source_checks": source_checks,
        "endpoint_fraction_in_nominal_disk": fractions,
        "gates": {
            "source_integrity": True,
            "endpoint_acceptable": acceptable,
            "carried_parent_o1_conditions": carried_conditions,
        },
        "verdicts": {
            "endpoint": "ENDPOINT_ACCEPTABLE" if acceptable else "ENDPOINT_EXCESSIVE",
            "O1_cross_band_nonaxisymmetry": o1,
            "O2_cassi_specific_cellular_grid": parent["verdicts"]["O2_cassi_specific_cellular_grid"],
            "O3_proton_star_identity": parent["verdicts"]["O3_proton_star_identity"],
        },
        "carried_parent_statistics": {
            "pair_correlations": parent["statistics"]["pair_correlations"],
            "mean_pair_correlation": parent["statistics"]["mean_pair_correlation"],
            "rotation_null_p95": parent["statistics"]["rotation_null_p95"],
            "positive_components": parent["statistics"]["positive_components"],
            "common_resolution_independent_beam_areas": parent["resolution_match"][
                "common_resolution_independent_beam_areas"
            ],
        },
        "limitations": [
            "This successor changes only the false-color endpoint sentinel; the original raster verdict remains frozen.",
            "Rendered Figure 1 rasters are not calibrated FITS brightness maps.",
            "The common B6 beam yields too few independent morphology elements for a Cassi-specific grid test.",
            "Cross-band non-axisymmetry does not identify a mechanism or test proton/star identity.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("GATE PARENT_AND_SOURCE_INTEGRITY PASS")
    print(f"GATE COLOR_MAP_ENDPOINT {'PASS' if acceptable else 'FAIL'}")
    print(f"VERDICT O1 {o1}")
    print(f"VERDICT O2 {report['verdicts']['O2_cassi_specific_cellular_grid']}")
    print(f"VERDICT O3 {report['verdicts']['O3_proton_star_identity']}")
    print("GATE REPORT_WRITTEN PASS")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
