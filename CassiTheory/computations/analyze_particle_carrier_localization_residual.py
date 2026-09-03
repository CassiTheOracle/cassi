#!/usr/bin/env python3
"""Decompose physical stationarity residuals in the frozen localization scan."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch

import particle_stationary_bvp as stationary  # pyright: ignore[reportMissingImports]


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "runs" / "20260902_particle_carrier_localization"
OUTPUT_DIR = ROOT / "runs" / "20260902_particle_carrier_localization_residual_analysis"
OUTPUT_PATH = OUTPUT_DIR / "analysis.json"
RESULTS_PATH = SOURCE_DIR / "results.json"
VERIFICATION_PATH = SOURCE_DIR / "verification.json"
RESULTS_SHA256 = "5a90e405d9d6851a1e445633adc0523de9c94d64e9ed27c139f177f92432a2d0"
VERIFICATION_SHA256 = "f30f95e71ab8a66b6aac1fd84001dba82771257a3ead73e200fd32c85eb5d4ad"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def field_statistics(field: torch.Tensor, mask: torch.Tensor) -> dict[str, float]:
    values = field[mask].detach()
    return {
        "rms": float(torch.sqrt(torch.mean(values**2))),
        "maximum_absolute": float(torch.max(torch.abs(values))),
        "sum_of_squares": float(torch.sum(values**2)),
    }


def analyze_artifact(path: Path, family: str, h_c: float) -> dict[str, Any]:
    stationary.COEFFICIENTS["h_C"] = h_c
    with np.load(path, allow_pickle=False) as archive:
        arrays = {name: np.array(archive[name], copy=True) for name in archive.files}
    grid = stationary.make_grid(family, torch.device("cpu"))
    names = ("psi_real", "psi_imag", "h", "a", "c")
    fields = {
        name: torch.tensor(arrays[name], dtype=torch.float64, requires_grad=True)
        for name in names
    }
    components, _, _ = stationary.energy_components(fields, grid)
    energy = torch.stack(tuple(components.values())).sum()
    gradients = torch.autograd.grad(energy, tuple(fields.values()))
    mask = grid.mask.to(torch.bool)
    projected = {
        "psi_real": stationary.project_scalar(
            grid.mask[..., None] * gradients[0] / grid.dv
        ),
        "psi_imag": stationary.project_scalar(
            grid.mask[..., None] * gradients[1] / grid.dv
        ),
        "h": stationary.project_scalar(
            grid.mask[..., None] * gradients[2] / grid.dv
        ),
        "a": stationary.project_vector(
            grid.mask[..., None, None] * gradients[3] / grid.dv,
            grid.rotations,
        ),
    }
    carrier_gradient = gradients[4] / grid.dv
    charge_direction = torch.sum(fields["c"] * carrier_gradient) * grid.dv
    carrier_norm = torch.sum(fields["c"] ** 2) * grid.dv
    projected["c"] = stationary.project_scalar(
        grid.mask
        * (
            carrier_gradient
            - fields["c"] * charge_direction / carrier_norm
        )
    )
    denominator = int(torch.sum(grid.mask).item()) * 17
    aggregate = math.sqrt(
        sum(float(torch.sum(value.detach() ** 2)) for value in projected.values())
        / denominator
    )
    carrier = fields["c"].detach()
    carrier_residual = projected["c"].detach()
    zero = mask & (carrier == 0.0)
    negative_zero = zero & (carrier_residual < 0.0)
    kkt_residual = torch.where(
        zero,
        torch.minimum(carrier_residual, torch.zeros_like(carrier_residual)),
        carrier_residual,
    )[mask]
    return {
        "physical_gradient_rms": aggregate,
        "field_residuals": {
            name: field_statistics(value, mask) for name, value in projected.items()
        },
        "carrier_interior": {
            "cell_count": int(torch.sum(mask).item()),
            "exact_zero_count": int(torch.sum(zero).item()),
            "negative_residual_zero_count": int(torch.sum(negative_zero).item()),
            "minimum": float(torch.min(carrier[mask])),
            "maximum": float(torch.max(carrier[mask])),
        },
        "nonnegative_kkt_residual": {
            "rms": float(torch.sqrt(torch.mean(kkt_residual**2))),
            "maximum_absolute": float(torch.max(torch.abs(kkt_residual))),
        },
    }


def main() -> int:
    if sha256_file(RESULTS_PATH) != RESULTS_SHA256:
        raise RuntimeError("localization result receipt hash mismatch")
    if sha256_file(VERIFICATION_PATH) != VERIFICATION_SHA256:
        raise RuntimeError("localization verification receipt hash mismatch")
    results = read_json(RESULTS_PATH)
    verification = read_json(VERIFICATION_PATH)
    if verification.get("pass") is not True or verification.get("mismatches"):
        raise RuntimeError("localization verification receipt is not clean")
    analyses = []
    for arm in results["primary_scan"]:
        artifact = SOURCE_DIR / arm["terminal_artifact"]
        if sha256_file(artifact) != arm["terminal_artifact_sha256"]:
            raise RuntimeError(f"artifact hash mismatch: {artifact.name}")
        analysis = analyze_artifact(artifact, arm["family"], float(arm["h_C"]))
        reported = float(arm["diagnostics"]["physical_gradient_rms"])
        if not math.isclose(
            analysis["physical_gradient_rms"], reported, rel_tol=1.0e-12, abs_tol=1.0e-14
        ):
            raise RuntimeError(f"physical gradient mismatch: {arm['label']}")
        analyses.append(
            {
                "label": arm["label"],
                "h_C": arm["h_C"],
                "artifact": arm["terminal_artifact"],
                "artifact_sha256": arm["terminal_artifact_sha256"],
                **analysis,
            }
        )
    output = {
        "schema": "cassi.particle-carrier-localization-residual-analysis.v1",
        "source_results_sha256": RESULTS_SHA256,
        "source_verification_sha256": VERIFICATION_SHA256,
        "source_verification_pass": True,
        "primary_verdict": results["primary_verdict"],
        "analyses": analyses,
    }
    write_json(OUTPUT_PATH, output)
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH),
                "arms": len(analyses),
                "all_aggregate_residuals_matched": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
