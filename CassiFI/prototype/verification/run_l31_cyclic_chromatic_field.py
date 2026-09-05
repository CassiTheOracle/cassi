"""Run the frozen L31 cyclic-chromatic field board."""

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
from cassi_cyclic_chromatic_field import (
    CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID,
    CYCLIC_CHROMATIC_OPERATOR_PROFILE_ID,
    CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID,
    CyclicChromaticFieldConfig,
    CyclicChromaticFieldController,
)
from cassi_qi_field import QiFieldState

BOARD_SCHEMA = "cassi.l31.cyclic-chromatic-board.v1"
TRACE_SCHEMA = "cassi.l31.cyclic-chromatic-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L31-CYCLIC-CHROMATIC-FIELD-PREREG.md"
L30_MODULE = ROOT / "cassi_white_chromatic_field.py"
MODULE = ROOT / "cassi_cyclic_chromatic_field.py"
L30_RUNNER = ROOT / "verification" / "run_l30_white_chromatic_field.py"
L30_VERIFIER = ROOT / "verification" / "verify_l30_white_chromatic_field.py"
RUNNER = ROOT / "verification" / "run_l31_cyclic_chromatic_field.py"
VERIFIER = ROOT / "verification" / "verify_l31_cyclic_chromatic_field.py"
OUTPUT_DIR = ROOT / "_diag" / "l31-cyclic-chromatic-field"
BOARD_NAME = "l31-board.json"
TRACE_NAME = "l31-traces.npz"
PNG_NAME = "l31-projection.png"
DENOMINATOR = 1.0 + l30.PHI * l30.PHI


class L31RunnerError(RuntimeError):
    """The canonical L31 board could not be completed."""


def native_coordinates(
    state: QiFieldState, mode_count: int = l30.MODE_COUNT
) -> tuple[torch.Tensor, ...]:
    parts = state.field.reshape(
        l30.CHANNELS, 9, mode_count, state.field.shape[2]
    )
    width = mode_count // 2
    return tuple(
        torch.complex(parts[:, real, :width], parts[:, real + 1, :width])
        for real in (0, 2, 4, 6)
    )


def native_channel_energy(state: QiFieldState, receipt: Any = None) -> np.ndarray:
    value = l30.receipt_value(receipt, "bank_energy", None)
    if value is not None:
        return np.asarray(l30.cpu(value))
    packed = state.field.reshape(
        l30.CHANNELS, 9, l30.MODE_COUNT, state.field.shape[2]
    )
    energy = (
        packed[:, :8, : l30.ACTIVE_WIDTH].square().sum(dim=1).mean(dim=1)
        / DENOMINATOR
    )
    return l30.cpu(energy)


def run_board(
    device: torch.device, dtype: torch.dtype
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    previous = (
        l30.WhiteChromaticFieldConfig,
        l30.WhiteChromaticFieldController,
        l30.TRACE_SCHEMA,
        l30.coordinates,
        l30.channel_energy,
    )
    try:
        l30.WhiteChromaticFieldConfig = CyclicChromaticFieldConfig
        l30.WhiteChromaticFieldController = CyclicChromaticFieldController
        l30.TRACE_SCHEMA = TRACE_SCHEMA
        l30.coordinates = native_coordinates
        l30.channel_energy = native_channel_energy
        return l30.run_board(device, dtype)
    finally:
        (
            l30.WhiteChromaticFieldConfig,
            l30.WhiteChromaticFieldController,
            l30.TRACE_SCHEMA,
            l30.coordinates,
            l30.channel_energy,
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
        MODULE,
        L30_RUNNER,
        L30_VERIFIER,
        RUNNER,
        VERIFIER,
    )
    missing = [str(path) for path in source_paths if not path.is_file()]
    if missing:
        raise L31RunnerError(f"missing bound source files: {missing!r}")
    hashes = {
        path.relative_to(ROOT).as_posix(): l30.sha256_file(path)
        for path in source_paths
    }
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA,
        "status": "INCOMPLETE",
        "layout_profile_id": CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID,
        "operator_profile_id": CYCLIC_CHROMATIC_OPERATOR_PROFILE_ID,
        "projection_profile_id": CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID,
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
