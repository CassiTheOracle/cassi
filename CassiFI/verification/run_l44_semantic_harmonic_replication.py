"""Run the frozen L44 availability-semantic harmonic replication."""

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
import verification.run_l43_stable_harmonic_field as l43
from cassi_stable_harmonic_field import (
    ROUND_OFF_MULTIPLIER,
    STABLE_HARMONIC_LAYOUT_PROFILE_ID,
    STABLE_HARMONIC_OPERATOR_PROFILE_ID,
    STABLE_HARMONIC_PROJECTION_PROFILE_ID,
)

BOARD_SCHEMA = "cassi.l44.availability-semantic-replication-board.v1"
TRACE_SCHEMA = "cassi.l44.availability-semantic-replication-traces.v1"
PREREGISTRATION = (
    ROOT / "designs" / "L44-AVAILABILITY-SEMANTIC-REPLICATION-PREREG.md"
)
PRIOR_AUDIT = (
    ROOT
    / "artifacts"
    / "harmonic-reconstruction-audit"
    / "harmonic-reconstruction-audit.json"
)
OUTPUT_DIR = ROOT / "_diag" / "l44-semantic-harmonic-replication"
BOARD_NAME = "l44-board.json"
TRACE_NAME = "l44-traces.npz"
PNG_NAME = "l44-projection.png"
SOURCE_PATHS = (
    *l43.SOURCE_PATHS,
    ROOT / "designs" / "HARMONIC-RECONSTRUCTION-AUDIT-PREREG.md",
    ROOT / "verification" / "audit_harmonic_reconstruction.py",
    PREREGISTRATION,
    ROOT / "verification" / "run_l44_semantic_harmonic_replication.py",
    ROOT / "verification" / "verify_l44_semantic_harmonic_replication.py",
)


class L44RunnerError(RuntimeError):
    """The frozen L44 replication could not be completed."""


def run_board(
    device: torch.device, dtype: torch.dtype
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    previous = l43.TRACE_SCHEMA
    try:
        l43.TRACE_SCHEMA = TRACE_SCHEMA
        return l43.run_board(device, dtype)
    finally:
        l43.TRACE_SCHEMA = previous


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

    missing = [str(path) for path in (*SOURCE_PATHS, PRIOR_AUDIT) if not path.is_file()]
    if missing:
        raise L44RunnerError(f"missing bound files: {missing!r}")
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
        "prior_audit": {
            "path": PRIOR_AUDIT.relative_to(ROOT).as_posix(),
            "sha256": l30.sha256_file(PRIOR_AUDIT),
        },
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
            "age_winner_comparison": "available-only",
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
