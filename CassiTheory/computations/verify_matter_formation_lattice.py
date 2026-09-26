#!/usr/bin/env python3
"""Independent receipt verifier for the frozen matter-formation lattice diagnostic.

This module deliberately does not import the primary lattice driver.  It rebuilds
all carrier-only diagnostics from the byte-bound NPZ arrays, including the
second-order boundary stencil, Fourier mask, parity classes, and edge sum.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMPAIGN = ROOT / "runs" / "20260906_matter_formation"
DEFAULT_RESULT = DEFAULT_CAMPAIGN / "lattice.json"
DEFAULT_OUTPUT = DEFAULT_CAMPAIGN / "verification.json"
PREREG = ROOT / "computations" / "matter-formation-continuum-prereg.md"
PRIMARY_SOURCE = ROOT / "computations" / "matter_formation_lattice.py"

# These four paths and hashes are immutable inputs declared in the frozen
# preregistration.  They are intentionally not discovered from a primary receipt.
SOURCE_ARTIFACTS: tuple[dict[str, Any], ...] = (
    {
        "N": 17,
        "dx": 0.5,
        "artifact": "runs/20260902_particle_carrier_direct_coordinate_v2/fields_primary_half_reference_block01.npz",
        "sha256": "c32beb4ee7bc7746a4fc18b63bc04ef7db12cc18505c9bee8ce2d298ddc25837",
    },
    {
        "N": 21,
        "dx": 0.4,
        "artifact": "runs/20260902_particle_carrier_direct_coordinate_v2/fields_comparison_H_block01.npz",
        "sha256": "8aa65f3c08167c902660f9e8d09c0ce921d43c7f0af152b31aae79db6875810f",
    },
    {
        "N": 25,
        "dx": 1.0 / 3.0,
        "artifact": "runs/20260902_particle_carrier_resolution_recovery/fields_resolution_X1_block01.npz",
        "sha256": "c75a4255da2008a90268fcda83fcdbdca5a8386f9f580f854737668b664e8393",
    },
    {
        "N": 29,
        "dx": 2.0 / 7.0,
        "artifact": "runs/20260902_particle_carrier_resolution_recovery/fields_resolution_X2_block01.npz",
        "sha256": "db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0",
    },
)

BOUNDARY_SHELL_TOL = 1.0e-12
REL_TOL = 1.0e-10
HF_REFERENCE = 0.8744032081
HF_REFERENCE_TOL = 1.0e-8
UV_HF_LIMIT = 0.20
UV_RATIO_LIMIT = 4.0
UV_SCALED_DRIFT_LIMIT = 0.20


def canonical_sha256(path: Path) -> str:
    """Hash source text with CRLF normalized to LF, as required by the prereg."""
    digest = hashlib.sha256()
    data = path.read_bytes()
    digest.update(data.replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def byte_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def relative_close(actual: float, expected: float, tolerance: float = REL_TOL) -> bool:
    denominator = max(1.0, abs(float(actual)), abs(float(expected)))
    return abs(float(actual) - float(expected)) / denominator <= tolerance


def central_stencil(field: np.ndarray, axis: int, dx: float) -> np.ndarray:
    """Second-order centered interior and one-sided boundary derivative.

    The slices are explicit rather than delegated to np.gradient, so the
    boundary convention remains visible and independently auditable.
    """
    moved = np.moveaxis(np.asarray(field, dtype=np.float64), axis, 0)
    derivative = np.empty_like(moved)
    derivative[0] = (-3.0 * moved[0] + 4.0 * moved[1] - moved[2]) / (2.0 * dx)
    derivative[1:-1] = (moved[2:] - moved[:-2]) / (2.0 * dx)
    derivative[-1] = (3.0 * moved[-1] - 4.0 * moved[-2] + moved[-3]) / (2.0 * dx)
    return np.moveaxis(derivative, 0, axis)


def diagnostics(c: np.ndarray, dx: float) -> dict[str, Any]:
    c = np.asarray(c, dtype=np.float64)
    if c.ndim != 3 or c.shape[0] != c.shape[1] or c.shape[1] != c.shape[2]:
        raise ValueError(f"carrier must be a cubic 3-D array, got {c.shape}")
    if not np.all(np.isfinite(c)) or not math.isfinite(float(dx)) or dx <= 0.0:
        raise ValueError("non-finite carrier or non-positive spacing")
    n = int(c.shape[0])
    volume = dx**3
    charge = float(np.sum(c * c, dtype=np.float64) * volume)
    if charge <= 0.0 or not math.isfinite(charge):
        raise ValueError("carrier charge is not positive and finite")

    frequencies = np.fft.fftfreq(n, d=dx)
    nyquist = 1.0 / (2.0 * dx)
    high_axis = np.abs(frequencies) >= 0.75 * nyquist
    high_mask = (
        high_axis[:, None, None]
        | high_axis[None, :, None]
        | high_axis[None, None, :]
    )
    spectrum = np.fft.fftn(c)
    power = np.abs(spectrum) ** 2
    total_power = float(np.sum(power, dtype=np.float64))
    high_power = float(np.sum(power[high_mask], dtype=np.float64))
    high_fraction = high_power / total_power if total_power > 0.0 else float("nan")

    parity = []
    for i in range(2):
        for j in range(2):
            for k in range(2):
                block = c[i::2, j::2, k::2]
                parity.append(float(np.sum(block * block, dtype=np.float64) * volume / charge))

    derivatives = tuple(central_stencil(c, axis, dx) for axis in range(3))
    centered = 0.5 * volume * sum(
        float(np.sum(derivative * derivative, dtype=np.float64))
        for derivative in derivatives
    )
    edge_sum = sum(
        float(np.sum(np.diff(c, axis=axis) ** 2, dtype=np.float64))
        for axis in range(3)
    )
    edge = 0.5 * dx * edge_sum
    return {
        "charge": charge,
        "high_frequency_fraction": float(high_fraction),
        "parity_fractions": parity,
        "centered_kinetic": float(centered),
        "edge_kinetic": float(edge),
        "scaled_edge_kinetic": float(dx * dx * edge),
        "edge_to_centered": float(edge / centered) if centered > 0.0 else float("inf"),
    }


def gaussian_control(n: int, dx: float, q: float = 4.0) -> dict[str, Any]:
    x = (np.arange(n, dtype=np.float64) - (n - 1) / 2.0) * dx
    radius2 = (
        x[:, None, None] ** 2
        + x[None, :, None] ** 2
        + x[None, None, :] ** 2
    )
    c = np.exp(-radius2 / 2.0)
    c[0, :, :] = 0.0
    c[-1, :, :] = 0.0
    c[:, 0, :] = 0.0
    c[:, -1, :] = 0.0
    c[:, :, 0] = 0.0
    c[:, :, -1] = 0.0
    norm = math.sqrt(float(np.sum(c * c, dtype=np.float64) * dx**3))
    return {"N": n, "dx": dx, **diagnostics(c * math.sqrt(q) / norm, dx)}


def periodic_control() -> dict[str, Any]:
    """Periodic even-grid alternating-in-one-axis control.

    This control is intentionally evaluated with periodic ``roll`` stencils,
    unlike the stored finite-box fields.  For c_i=(-1)^i, the centered
    periodic derivative is identically zero while the periodic edge sum is
    nonzero (the frozen reference is centered=0 and edge=8192).
    """
    n = 16
    dx = 1.0
    indices = np.indices((n, n, n), dtype=np.int64)
    c = np.where(indices[0] % 2 == 0, 1.0, -1.0)
    periodic_derivatives = tuple(
        (np.roll(c, -1, axis=axis) - np.roll(c, 1, axis=axis)) / (2.0 * dx)
        for axis in range(3)
    )
    centered = 0.5 * dx**3 * sum(
        float(np.sum(derivative * derivative, dtype=np.float64))
        for derivative in periodic_derivatives
    )
    edge = 0.5 * dx * sum(
        float(np.sum((np.roll(c, -1, axis=axis) - c) ** 2, dtype=np.float64))
        for axis in range(3)
    )
    return {
        "N": n,
        "dx": dx,
        "centered_kinetic": float(centered),
        "edge_kinetic": float(edge),
    }


def load_primary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("lattice result is not a JSON object")
    return payload


def add_mismatch(
    mismatches: list[dict[str, Any]], path: str, expected: Any, actual: Any
) -> None:
    mismatches.append({"path": path, "expected": expected, "actual": actual})


def compare_value(
    mismatches: list[dict[str, Any]], path: str, actual: Any, expected: Any
) -> None:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not relative_close(float(actual), float(expected)):
            add_mismatch(mismatches, path, expected, actual)
    elif actual != expected:
        add_mismatch(mismatches, path, expected, actual)


def compare_diagnostics(
    mismatches: list[dict[str, Any]], prefix: str, actual: Mapping[str, Any], expected: Mapping[str, Any]
) -> None:
    for key in (
        "charge",
        "high_frequency_fraction",
        "centered_kinetic",
        "edge_kinetic",
        "scaled_edge_kinetic",
        "edge_to_centered",
    ):
        compare_value(mismatches, f"{prefix}.{key}", actual.get(key), expected[key])
    got_parity = actual.get("parity_fractions")
    if not isinstance(got_parity, list) or len(got_parity) != 8:
        add_mismatch(mismatches, f"{prefix}.parity_fractions", expected["parity_fractions"], got_parity)
    else:
        for index, value in enumerate(expected["parity_fractions"]):
            compare_value(mismatches, f"{prefix}.parity_fractions[{index}]", got_parity[index], value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    result_path = args.result if args.result.is_absolute() else ROOT / args.result
    output_path = (
        (args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir) / "verification.json"
        if args.output_dir is not None
        else DEFAULT_OUTPUT
    )
    # A second receipt is allowed only when the caller explicitly names a
    # separate output directory.  Never replace a first execution silently.
    if output_path.exists():
        print(f"refusing to replace existing verification receipt: {output_path}")
        return 1

    mismatches: list[dict[str, Any]] = []
    infrastructure: list[str] = []
    derived_rows: list[dict[str, Any]] = []
    boundary_shell_checks: list[dict[str, Any]] = []
    try:
        if not result_path.is_file():
            raise FileNotFoundError(result_path)
        primary = load_primary(result_path)
        if not PREREG.is_file() or not PRIMARY_SOURCE.is_file():
            raise FileNotFoundError("preregistration or primary source is missing")
        prereg_hash = canonical_sha256(PREREG)
        source_hash = canonical_sha256(PRIMARY_SOURCE)
        compare_value(mismatches, "prereg_sha256", primary.get("prereg_sha256"), prereg_hash)
        compare_value(mismatches, "source_sha256", primary.get("source_sha256"), source_hash)

        rows = primary.get("rows")
        if not isinstance(rows, list):
            raise ValueError("lattice result rows is not a list")
        if len(rows) != len(SOURCE_ARTIFACTS):
            add_mismatch(mismatches, "rows.length", len(SOURCE_ARTIFACTS), len(rows))
        normalized_artifacts: list[str] = []
        raw_rows: dict[str, Mapping[str, Any]] = {}
        for index, row in enumerate(rows):
            if isinstance(row, dict) and isinstance(row.get("artifact"), str):
                artifact = row["artifact"].replace("\\", "/")
                normalized_artifacts.append(artifact)
                if artifact in raw_rows:
                    add_mismatch(mismatches, f"rows[{index}].artifact", "unique artifact", artifact)
                else:
                    raw_rows[artifact] = row
            else:
                add_mismatch(mismatches, f"rows[{index}]", "object with artifact", row)
        if len(normalized_artifacts) != len(set(normalized_artifacts)):
            add_mismatch(
                mismatches,
                "rows.artifacts",
                "four unique artifact paths",
                normalized_artifacts,
            )
        expected_artifacts = {spec["artifact"] for spec in SOURCE_ARTIFACTS}
        if set(raw_rows) != expected_artifacts:
            add_mismatch(
                mismatches,
                "rows.artifacts",
                sorted(expected_artifacts),
                sorted(raw_rows),
            )

        for index, spec in enumerate(SOURCE_ARTIFACTS):
            artifact_path = ROOT / spec["artifact"]
            if not artifact_path.is_file():
                raise FileNotFoundError(artifact_path)
            actual_hash = byte_sha256(artifact_path)
            if actual_hash != spec["sha256"]:
                raise ValueError(f"immutable artifact hash mismatch: {spec['artifact']}")
            with np.load(artifact_path, allow_pickle=False) as fields:
                if "c" not in fields or "x" not in fields:
                    raise ValueError(f"missing x/c arrays: {spec['artifact']}")
                x = np.asarray(fields["x"], dtype=np.float64)
                c = np.asarray(fields["c"], dtype=np.float64)
            shell_values = np.concatenate(
                (
                    c[0].ravel(),
                    c[-1].ravel(),
                    c[:, 0, :].ravel(),
                    c[:, -1, :].ravel(),
                    c[:, :, 0].ravel(),
                    c[:, :, -1].ravel(),
                )
            )
            shell_max = float(np.max(np.abs(shell_values)))
            shell_receipt = {
                "artifact": spec["artifact"],
                "max_abs": shell_max,
                "tolerance": BOUNDARY_SHELL_TOL,
                "pass": shell_max <= BOUNDARY_SHELL_TOL,
            }
            boundary_shell_checks.append(shell_receipt)
            if not shell_receipt["pass"]:
                add_mismatch(
                    mismatches,
                    f"rows[{index}].outer_shell",
                    f"max_abs <= {BOUNDARY_SHELL_TOL}",
                    shell_max,
                )
            if x.ndim != 1 or x.size != spec["N"]:
                raise ValueError(f"unexpected x shape: {spec['artifact']}")
            dx = float(x[1] - x[0])
            if not relative_close(dx, spec["dx"]):
                raise ValueError(f"unexpected spacing: {spec['artifact']}")
            fresh = diagnostics(c, dx)
            row = {"N": spec["N"], "dx": dx, "artifact": spec["artifact"], "sha256": actual_hash, **fresh}
            derived_rows.append(row)
            recorded = raw_rows.get(spec["artifact"])
            if recorded is None:
                add_mismatch(mismatches, f"rows[{index}]", spec["artifact"], None)
            else:
                for key in ("N", "dx", "artifact", "sha256"):
                    compare_value(mismatches, f"rows[{index}].{key}", recorded.get(key), row[key])
                compare_diagnostics(mismatches, f"rows[{index}]", recorded, fresh)

        controls = {
            "gaussians": [gaussian_control(spec["N"], spec["dx"]) for spec in SOURCE_ARTIFACTS],
            "periodic": periodic_control(),
        }
        recorded_controls = primary.get("controls")
        if not isinstance(recorded_controls, dict):
            add_mismatch(mismatches, "controls", controls, recorded_controls)
        else:
            recorded_gaussians = recorded_controls.get("gaussians")
            if not isinstance(recorded_gaussians, list) or len(recorded_gaussians) != len(controls["gaussians"]):
                add_mismatch(mismatches, "controls.gaussians", controls["gaussians"], recorded_gaussians)
            else:
                for index, expected in enumerate(controls["gaussians"]):
                    actual = recorded_gaussians[index]
                    if not isinstance(actual, dict):
                        add_mismatch(mismatches, f"controls.gaussians[{index}]", expected, actual)
                    else:
                        for key in ("N", "dx"):
                            compare_value(mismatches, f"controls.gaussians[{index}].{key}", actual.get(key), expected[key])
                        compare_diagnostics(mismatches, f"controls.gaussians[{index}]", actual, expected)
            actual_periodic = recorded_controls.get("periodic")
            if not isinstance(actual_periodic, dict):
                add_mismatch(mismatches, "controls.periodic", controls["periodic"], actual_periodic)
            else:
                for key, expected in controls["periodic"].items():
                    compare_value(mismatches, f"controls.periodic.{key}", actual_periodic.get(key), expected)

        finest = derived_rows[-2:]
        scaled = [float(row["scaled_edge_kinetic"]) for row in finest]
        scaled_drift = abs(scaled[1] - scaled[0]) / max(abs(scaled[0]), abs(scaled[1]), 1.0e-300)
        scientific_rejection = (
            all(row["high_frequency_fraction"] > UV_HF_LIMIT for row in finest)
            and all(row["edge_to_centered"] > UV_RATIO_LIMIT for row in finest)
            and scaled_drift < UV_SCALED_DRIFT_LIMIT
        )
        scientific_verdict = "CONTRADICTS" if scientific_rejection else "INCONCLUSIVE"
        if abs(derived_rows[-1]["high_frequency_fraction"] - HF_REFERENCE) > HF_REFERENCE_TOL:
            add_mismatch(mismatches, "finest.high_frequency_fraction_reference", HF_REFERENCE, derived_rows[-1]["high_frequency_fraction"])
        output: dict[str, Any] = {
            "schema": "cassi.matter-formation.lattice.verification.v1",
            "verifier_sha256": canonical_sha256(Path(__file__)),
            "prereg_sha256": canonical_sha256(PREREG),
            "source_sha256": canonical_sha256(PRIMARY_SOURCE),
            "rows": derived_rows,
            "scalar_mismatches": mismatches,
            "boundary_shell_checks": boundary_shell_checks,
            "controls": controls,
            "scientific_verdict": scientific_verdict,
            "scientific_gate": {
                "high_frequency_limit": UV_HF_LIMIT,
                "edge_to_centered_limit": UV_RATIO_LIMIT,
                "scaled_edge_relative_drift_limit": UV_SCALED_DRIFT_LIMIT,
                "finest_scaled_edge_relative_drift": scaled_drift,
                "pass": scientific_rejection,
            },
            "infrastructure_errors": infrastructure,
            "pass": not mismatches and not infrastructure,
        }
    except Exception as error:
        infrastructure.append(repr(error))
        output = {
            "schema": "cassi.matter-formation.lattice.verification.v1",
            "prereg_sha256": canonical_sha256(PREREG) if PREREG.is_file() else None,
            "source_sha256": canonical_sha256(PRIMARY_SOURCE) if PRIMARY_SOURCE.is_file() else None,
            "rows": derived_rows,
            "scalar_mismatches": mismatches,
            "boundary_shell_checks": boundary_shell_checks,
            "controls": {},
            "scientific_verdict": "INCONCLUSIVE",
            "scientific_gate": {"pass": False},
            "infrastructure_errors": infrastructure,
            "pass": False,
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, output_path)
    print(json.dumps({"pass": output["pass"], "scientific_verdict": output["scientific_verdict"], "mismatches": len(output["scalar_mismatches"]), "infrastructure_errors": len(output["infrastructure_errors"])}, sort_keys=True))
    return 0 if output["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
