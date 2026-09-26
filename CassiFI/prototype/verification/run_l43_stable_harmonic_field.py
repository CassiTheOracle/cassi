"""Run the frozen L43 precision-stable harmonic age board."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.run_l30_white_chromatic_field as l30
import verification.run_l42_harmonic_age_field as l42
from cassi_stable_harmonic_field import (
    ROUND_OFF_MULTIPLIER,
    STABLE_HARMONIC_LAYOUT_PROFILE_ID,
    STABLE_HARMONIC_OPERATOR_PROFILE_ID,
    STABLE_HARMONIC_PROJECTION_PROFILE_ID,
    StableHarmonicFieldConfig,
    StableHarmonicFieldController,
)

BOARD_SCHEMA = "cassi.l43.stable-harmonic-field-board.v1"
TRACE_SCHEMA = "cassi.l43.stable-harmonic-field-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L43-STABLE-HARMONIC-AGE-PREREG.md"
OUTPUT_DIR = ROOT / "_diag" / "l43-stable-harmonic-field"
BOARD_NAME = "l43-board.json"
TRACE_NAME = "l43-traces.npz"
PNG_NAME = "l43-projection.png"
SOURCE_PATHS = (
    PREREGISTRATION,
    ROOT / "designs" / "L42-HARMONIC-AGE-LADDER-PREREG.md",
    ROOT / "cassi_white_chromatic_field.py",
    ROOT / "cassi_cyclic_chromatic_field.py",
    ROOT / "cassi_harmonic_age_field.py",
    ROOT / "cassi_stable_harmonic_field.py",
    ROOT / "verification" / "run_l30_white_chromatic_field.py",
    ROOT / "verification" / "verify_l30_white_chromatic_field.py",
    ROOT / "verification" / "run_l31_cyclic_chromatic_field.py",
    ROOT / "verification" / "verify_l31_cyclic_chromatic_field.py",
    ROOT / "verification" / "run_l42_harmonic_age_field.py",
    ROOT / "verification" / "verify_l42_harmonic_age_field.py",
    ROOT / "verification" / "run_l43_stable_harmonic_field.py",
    ROOT / "verification" / "verify_l43_stable_harmonic_field.py",
)


class L43RunnerError(RuntimeError):
    """The frozen L43 board could not be completed."""


def numerical_floor(scores: np.ndarray) -> np.ndarray:
    age_max = np.max(scores, axis=-1)
    row_peak = np.max(age_max, axis=-1)
    epsilon = np.finfo(scores.dtype).eps
    return np.maximum(
        np.asarray(1.0e-8, dtype=scores.dtype),
        row_peak * np.asarray(ROUND_OFF_MULTIPLIER * epsilon, dtype=scores.dtype),
    )


def attach_stable_floor_traces(arrays: dict[str, np.ndarray]) -> None:
    task_floor = numerical_floor(arrays["task_read_age_scores"])
    arrays["task_read_age_numerical_floor"] = task_floor
    arrays["task_read_age_available"] = arrays["task_read_available"][
        :, :, None
    ] & (
        np.max(arrays["task_read_age_scores"], axis=-1) >= task_floor[:, :, None]
    )

    pre_floor = numerical_floor(arrays["pre_readout_age_scores"])
    arrays["pre_readout_age_numerical_floor"] = pre_floor
    arrays["pre_readout_age_available"] = arrays["pre_readout_available"][
        :, None
    ] & (
        np.max(arrays["pre_readout_age_scores"], axis=-1) >= pre_floor[:, None]
    )

    four_floor = numerical_floor(arrays["four_post_age_scores"])
    arrays["four_post_age_numerical_floor"] = four_floor
    final_floor = numerical_floor(arrays["four_blank_final_age_scores"])
    arrays["four_blank_final_age_numerical_floor"] = final_floor


def run_board(
    device: torch.device, dtype: torch.dtype
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    previous = (
        l42.HarmonicAgeFieldConfig,
        l42.HarmonicAgeFieldController,
        l42.TRACE_SCHEMA,
    )
    try:
        l42.HarmonicAgeFieldConfig = StableHarmonicFieldConfig
        l42.HarmonicAgeFieldController = StableHarmonicFieldController
        l42.TRACE_SCHEMA = TRACE_SCHEMA
        result, arrays = l42.run_board(device, dtype)
    finally:
        (
            l42.HarmonicAgeFieldConfig,
            l42.HarmonicAgeFieldController,
            l42.TRACE_SCHEMA,
        ) = previous
    attach_stable_floor_traces(arrays)
    return result, arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda")
    parser.add_argument(
        "--dtype", default="float32", choices=("float32", "float64")
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    device = torch.device(args.device)
    dtype = torch.float64 if args.dtype == "float64" else torch.float32
    output_dir = args.output_dir.resolve()
    board_path = output_dir / BOARD_NAME
    trace_path = output_dir / TRACE_NAME
    png_path = output_dir / PNG_NAME

    missing = [str(path) for path in SOURCE_PATHS if not path.is_file()]
    if missing:
        raise L43RunnerError(f"missing bound source files: {missing!r}")
    hashes = {
        path.relative_to(ROOT).as_posix(): l30.sha256_file(path)
        for path in SOURCE_PATHS
    }
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA,
        "status": "INCOMPLETE",
        "layout_profile_id": STABLE_HARMONIC_LAYOUT_PROFILE_ID,
        "operator_profile_id": STABLE_HARMONIC_OPERATOR_PROFILE_ID,
        "projection_profile_id": STABLE_HARMONIC_PROJECTION_PROFILE_ID,
        "trace_schema_id": TRACE_SCHEMA,
        "preregistration_sha256": hashes[
            PREREGISTRATION.relative_to(ROOT).as_posix()
        ],
        "source_sha256": hashes,
        "device": {
            "requested": str(device),
            "type": device.type,
            "name": (
                torch.cuda.get_device_name(device)
                if device.type == "cuda" and torch.cuda.is_available()
                else str(device)
            ),
            "torch_version": torch.__version__,
            "hip_version": torch.version.hip,
            "dtype": args.dtype,
        },
        "constants": {
            "phi": l30.PHI,
            "channels": l30.CHANNELS,
            "mode_count": l30.MODE_COUNT,
            "active_modes": l30.ACTIVE_WIDTH,
            "alphabet_size": l30.ALPHABET_SIZE,
            "batch_size": l30.BATCH_SIZE,
            "targets": list(l30.TARGETS),
            "distractors": list(l30.DISTRACTORS),
            "read_ticks": list(l30.READ_TICKS),
            "long_horizon_ticks": list(l30.LONG_TICKS),
            "pre_distractor_ticks": list(l30.PRE_TICKS),
            "task_ticks": l30.TASK_TICKS,
            "long_ticks": l30.LONG_TICKS_COUNT,
            "evolution_steps": l30.EVOLUTION_STEPS,
            "heartbeat_carrier_energy": 0.5,
            "field_energy_budget": 1.0,
            "readout_energy_floor": 1.0e-8,
            "round_off_multiplier": ROUND_OFF_MULTIPLIER,
            "age_harmonics": [1, 2, 3, 4, 5, 6, 0],
            "age_ordinal_slots": [8, 7, 6, 5, 4, 3, 2],
            "four_blank_ticks": 8,
        },
        "trace": {"path": TRACE_NAME, "sha256": None},
        "projection": {"path": PNG_NAME, "sha256": None},
        "arms": {},
    }
    l30.atomic_json(board_path, board)
    try:
        started = time.perf_counter()
        result, arrays = run_board(device, dtype)
        l30.atomic_npz(trace_path, arrays)
        l30.write_projection_png(png_path, arrays["projection_rgb"])
        board["arms"]["canonical"] = result
        board["trace"] = {
            "path": TRACE_NAME,
            "sha256": l30.sha256_file(trace_path),
            "array_count": len(arrays),
        }
        board["projection"] = {
            "path": PNG_NAME,
            "sha256": l30.sha256_file(png_path),
        }
        board["resources"] = {
            "wall_seconds": float(time.perf_counter() - started),
            "peak_allocated_bytes": (
                int(torch.cuda.max_memory_allocated(device))
                if device.type == "cuda" and torch.cuda.is_available()
                else 0
            ),
        }
        board["status"] = "COMPLETE"
        l30.atomic_json(board_path, board)
    except Exception as exc:
        board["error"] = f"{type(exc).__name__}: {exc}"
        l30.atomic_json(board_path, board)
        raise
    print(board_path)
    print(trace_path)
    print(png_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
