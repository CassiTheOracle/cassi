"""Run the frozen L32 quadrature-chromatic recall board."""

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
import verification.run_l31_cyclic_chromatic_field as l31
from cassi_quadrature_chromatic_field import (
    QUADRATURE_CHROMATIC_LAYOUT_PROFILE_ID,
    QUADRATURE_CHROMATIC_OPERATOR_PROFILE_ID,
    QUADRATURE_CHROMATIC_PROJECTION_PROFILE_ID,
    QuadratureChromaticFieldConfig,
    QuadratureChromaticFieldController,
)

BOARD_SCHEMA = "cassi.l32.quadrature-chromatic-board.v1"
TRACE_SCHEMA = "cassi.l32.quadrature-chromatic-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L32-QUADRATURE-CHROMATIC-RECALL-PREREG.md"
L30_MODULE = ROOT / "cassi_white_chromatic_field.py"
L31_MODULE = ROOT / "cassi_cyclic_chromatic_field.py"
MODULE = ROOT / "cassi_quadrature_chromatic_field.py"
L30_RUNNER = ROOT / "verification" / "run_l30_white_chromatic_field.py"
L30_VERIFIER = ROOT / "verification" / "verify_l30_white_chromatic_field.py"
L31_RUNNER = ROOT / "verification" / "run_l31_cyclic_chromatic_field.py"
L31_VERIFIER = ROOT / "verification" / "verify_l31_cyclic_chromatic_field.py"
RUNNER = ROOT / "verification" / "run_l32_quadrature_chromatic_field.py"
VERIFIER = ROOT / "verification" / "verify_l32_quadrature_chromatic_field.py"
OUTPUT_DIR = ROOT / "_diag" / "l32-quadrature-chromatic-field"
BOARD_NAME = "l32-board.json"
TRACE_NAME = "l32-traces.npz"
PNG_NAME = "l32-projection.png"


class L32RunnerError(RuntimeError):
    """The canonical L32 board could not be completed."""


def capture_readout_arrays(
    arrays: dict[str, np.ndarray], prefix: str, readout: Any
) -> None:
    _BASE_READOUT_ARRAYS(arrays, prefix, readout)
    velocity = getattr(readout, "normalized_differential_velocity", None)
    if velocity is not None:
        arrays[f"{prefix}_normalized_vd"] = l30.cpu(velocity)


_BASE_READOUT_ARRAYS = l30.readout_arrays


def run_board(
    device: torch.device, dtype: torch.dtype
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    previous = (
        l31.CyclicChromaticFieldConfig,
        l31.CyclicChromaticFieldController,
        l31.TRACE_SCHEMA,
        l30.readout_arrays,
    )
    try:
        l31.CyclicChromaticFieldConfig = QuadratureChromaticFieldConfig
        l31.CyclicChromaticFieldController = QuadratureChromaticFieldController
        l31.TRACE_SCHEMA = TRACE_SCHEMA
        l30.readout_arrays = capture_readout_arrays
        result, arrays = l31.run_board(device, dtype)
        arrays["task_read_normalized_vd"] = np.stack(
            [
                arrays.pop(f"task_read_{tick}_normalized_vd")
                for tick in l30.READ_TICKS
            ]
        )
        arrays["pre_read_normalized_vd"] = arrays.pop(
            "pre_readout_normalized_vd"
        )
        return result, arrays
    finally:
        (
            l31.CyclicChromaticFieldConfig,
            l31.CyclicChromaticFieldController,
            l31.TRACE_SCHEMA,
            l30.readout_arrays,
        ) = previous


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
    source_paths = (
        PREREGISTRATION,
        L30_MODULE,
        L31_MODULE,
        MODULE,
        L30_RUNNER,
        L30_VERIFIER,
        L31_RUNNER,
        L31_VERIFIER,
        RUNNER,
        VERIFIER,
    )
    missing = [str(path) for path in source_paths if not path.is_file()]
    if missing:
        raise L32RunnerError(f"missing bound source files: {missing!r}")
    hashes = {
        path.relative_to(ROOT).as_posix(): l30.sha256_file(path)
        for path in source_paths
    }
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA,
        "status": "INCOMPLETE",
        "layout_profile_id": QUADRATURE_CHROMATIC_LAYOUT_PROFILE_ID,
        "operator_profile_id": QUADRATURE_CHROMATIC_OPERATOR_PROFILE_ID,
        "projection_profile_id": QUADRATURE_CHROMATIC_PROJECTION_PROFILE_ID,
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
