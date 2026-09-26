#!/usr/bin/env python3
"""Diagnose phase dependence in the nonlinear matter-formation receipts.

This analysis is explicitly post hoc and cannot alter the frozen verdict in
``matter-formation-continuum-report.md`` §28. It reconstructs Floquet-phase
stroboscopic amplitudes from both retained evolutions so that an oscillatory
coordinate crossing is not mistaken for secular carrier growth.

Run from the CassiTheory repository root after the primary and independent
§28 calculations::

    python -B computations/matter_formation_nonlinear_phase_diagnostic.py \
      --primary-arrays runs/20260907_matter_formation_nonlinear_fragmentation/arrays.npz \
      --independent-arrays runs/20260907_matter_formation_nonlinear_fragmentation_verification_prerequisite_recovery/independent_arrays.npz \
      --output runs/20260907_matter_formation_nonlinear_fragmentation_controls/phase_diagnostic_v2.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy import special

OMEGA = math.sqrt(24.0)
ELLIPTIC_PARAMETER = 2.0 / 3.0
PERIOD = 2.0 * float(special.ellipk(ELLIPTIC_PARAMETER)) / OMEGA
ACCEPTED_MEDIATOR_RATE = 0.362037120923008
ACCEPTED_CARRIER_RATE = 0.0017215449183269978
MEDIATOR_TARGET = 0.1
CARRIER_TARGET = 1.1e-6
ARMS = (
    "homogeneous_carrier",
    "mediator_only",
    "competition",
    "phase_seed",
    "equilibrium_control",
)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def interpolate_complex(
    time: np.ndarray, values: np.ndarray, targets: np.ndarray
) -> np.ndarray:
    return np.interp(targets, time, values.real) + 1j * np.interp(
        targets, time, values.imag
    )


def phase_envelope(
    time: np.ndarray,
    mode: np.ndarray,
    velocity: np.ndarray,
    targets: np.ndarray,
) -> np.ndarray:
    coordinate = interpolate_complex(time, mode, targets)
    momentum = interpolate_complex(time, velocity, targets)
    return np.sqrt(
        np.abs(coordinate) ** 2 + np.abs(momentum / OMEGA) ** 2
    )


def fitted_rate(
    time: np.ndarray, values: np.ndarray, mask: np.ndarray
) -> tuple[float, int]:
    count = int(np.count_nonzero(mask))
    if count < 2:
        raise RuntimeError("at least two phase-aligned samples are required")
    value = float(np.polyfit(time[mask], np.log(values[mask]), 1)[0])
    return value, count


def logarithmic_crossing(
    time: np.ndarray, values: np.ndarray, threshold: float
) -> float | None:
    hits = np.flatnonzero(values >= threshold)
    if hits.size == 0:
        return None
    index = int(hits[0])
    if index == 0:
        return float(time[0])
    fraction = (
        math.log(threshold) - math.log(float(values[index - 1]))
    ) / (
        math.log(float(values[index])) - math.log(float(values[index - 1]))
    )
    return float(time[index - 1] + fraction * (time[index] - time[index - 1]))


def first_raw_crossing(
    time: np.ndarray, values: np.ndarray, threshold: float
) -> float | None:
    hits = np.flatnonzero(values >= threshold)
    return None if hits.size == 0 else float(time[int(hits[0])])


def source_arrays(path: Path, prefix: str) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as source:
        def copied(name: str) -> np.ndarray:
            key = f"{prefix}{name}"
            if key not in source.files:
                raise RuntimeError(f"required array {key!r} is absent from {path}")
            value = np.array(source[key], copy=True)
            if not bool(np.all(np.isfinite(value))):
                raise RuntimeError(f"required array {key!r} contains a nonfinite value")
            return value

        return {
            "time": copied("t"),
            "f_mode": copied("f_mode1"),
            "f_velocity": copied("vf_mode1"),
            "z_mode": copied("z_mode4"),
            "z_velocity": copied("vz_mode4"),
            "raw_z_envelope": copied("z_envelope"),
        }


def analyze(path: Path, prefix: str) -> dict[str, Any]:
    arrays = source_arrays(path, prefix)
    time = arrays["time"]
    strobe_time = PERIOD * np.arange(
        int(math.floor(float(time[-1]) / PERIOD)) + 1, dtype=float
    )
    f_strobe = np.stack(
        [
            phase_envelope(
                time,
                arrays["f_mode"][index],
                arrays["f_velocity"][index],
                strobe_time,
            )
            for index in range(len(ARMS))
        ]
    )
    z_strobe = np.stack(
        [
            phase_envelope(
                time,
                arrays["z_mode"][index],
                arrays["z_velocity"][index],
                strobe_time,
            )
            for index in range(len(ARMS))
        ]
    )
    mediator = ARMS.index("mediator_only")
    competition = ARMS.index("competition")
    homogeneous = ARMS.index("homogeneous_carrier")
    mediator_mask = (f_strobe[mediator] >= 1.0e-3) & (
        f_strobe[mediator] <= 2.0e-2
    )
    carrier_mask = z_strobe[homogeneous] > 0.0
    mediator_rate, mediator_points = fitted_rate(
        strobe_time, f_strobe[mediator], mediator_mask
    )
    carrier_rate, carrier_points = fitted_rate(
        strobe_time, z_strobe[homogeneous], carrier_mask
    )
    mediator_entry = logarithmic_crossing(
        strobe_time, f_strobe[mediator], MEDIATOR_TARGET
    )
    carrier_at_entry = None
    if mediator_entry is not None:
        carrier_at_entry = float(
            np.interp(mediator_entry, strobe_time, z_strobe[competition])
        )
    return {
        "input_sha256": file_hash(path),
        "end_time": float(time[-1]),
        "strobe_count": int(strobe_time.size),
        "mediator": {
            "fitted_stroboscopic_rate": mediator_rate,
            "accepted_rate": ACCEPTED_MEDIATOR_RATE,
            "relative_error": abs(mediator_rate - ACCEPTED_MEDIATOR_RATE)
            / ACCEPTED_MEDIATOR_RATE,
            "fit_points": mediator_points,
            "stroboscopic_target_time": mediator_entry,
            "stroboscopic_initial": float(f_strobe[mediator, 0]),
            "stroboscopic_final": float(f_strobe[mediator, -1]),
        },
        "homogeneous_carrier": {
            "fitted_stroboscopic_rate": carrier_rate,
            "accepted_rate": ACCEPTED_CARRIER_RATE,
            "relative_error": abs(carrier_rate - ACCEPTED_CARRIER_RATE)
            / ACCEPTED_CARRIER_RATE,
            "fit_points": carrier_points,
            "stroboscopic_target_time": logarithmic_crossing(
                strobe_time, z_strobe[homogeneous], CARRIER_TARGET
            ),
        },
        "competition": {
            "raw_first_carrier_coordinate_crossing": first_raw_crossing(
                time, arrays["raw_z_envelope"][competition], CARRIER_TARGET
            ),
            "raw_max_carrier_coordinate_through_end": float(
                np.max(arrays["raw_z_envelope"][competition])
            ),
            "stroboscopic_max_carrier_through_end": float(
                np.max(z_strobe[competition])
            ),
            "carrier_stroboscopic_at_mediator_entry": carrier_at_entry,
        },
    }


def relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(1.0, abs(left), abs(right))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-arrays", type=Path, required=True)
    parser.add_argument("--independent-arrays", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite existing output: {args.output}")

    primary = analyze(args.primary_arrays.resolve(), "fine_")
    independent = analyze(args.independent_arrays.resolve(), "")
    compared = {
        "mediator_rate_relative_difference": relative_difference(
            primary["mediator"]["fitted_stroboscopic_rate"],
            independent["mediator"]["fitted_stroboscopic_rate"],
        ),
        "carrier_rate_relative_difference": relative_difference(
            primary["homogeneous_carrier"]["fitted_stroboscopic_rate"],
            independent["homogeneous_carrier"]["fitted_stroboscopic_rate"],
        ),
        "mediator_entry_time_relative_difference": relative_difference(
            primary["mediator"]["stroboscopic_target_time"],
            independent["mediator"]["stroboscopic_target_time"],
        ),
        "carrier_at_entry_relative_difference": relative_difference(
            primary["competition"]["carrier_stroboscopic_at_mediator_entry"],
            independent["competition"]["carrier_stroboscopic_at_mediator_entry"],
        ),
    }
    payload = {
        "schema": "cassi.matter-formation.nonlinear-fragmentation-phase-diagnostic.v2",
        "status": "POST-HOC DIAGNOSTIC—outside frozen verdict",
        "period": PERIOD,
        "primary": primary,
        "independent": independent,
        "cross_method": compared,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
