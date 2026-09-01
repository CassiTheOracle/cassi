"""Run the frozen L36 chromatic phase-portrait board."""

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
from cassi_chromatic_phase_portrait import (
    CHROMATIC_PHASE_PORTRAIT_PROFILE_ID,
    ChromaticPhasePortrait,
    chromatic_phase_portrait,
)
from cassi_cyclic_chromatic_field import (
    CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID,
    CYCLIC_CHROMATIC_OPERATOR_PROFILE_ID,
    CyclicChromaticFieldConfig,
    CyclicChromaticFieldController,
)

BOARD_SCHEMA = "cassi.l36.chromatic-phase-portrait-board.v1"
TRACE_SCHEMA = "cassi.l36.chromatic-phase-portrait-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L36-CHROMATIC-PHASE-PORTRAIT-PREREG.md"
RUNNER = ROOT / "verification" / "run_l36_chromatic_phase_portrait.py"
VERIFIER = ROOT / "verification" / "verify_l36_chromatic_phase_portrait.py"
OUTPUT_DIR = ROOT / "_diag" / "l36-chromatic-phase-portrait"
BOARD_NAME = "l36-board.json"
TRACE_NAME = "l36-traces.npz"
PNG_NAME = "l36-comparison.png"
MODE_COUNT = 2048
PANEL_SIDE = 16
HISTORIES = ((252, 139), (132, 139))
SOURCE_PATHS = (
    PREREGISTRATION,
    ROOT / "cassi_white_chromatic_field.py",
    ROOT / "cassi_cyclic_chromatic_field.py",
    ROOT / "cassi_chromatic_phase_portrait.py",
    ROOT / "verification" / "run_l30_white_chromatic_field.py",
    RUNNER,
    VERIFIER,
)


class L36RunnerError(RuntimeError):
    """The canonical L36 portrait board could not be completed."""


def portrait_arrays(
    arrays: dict[str, np.ndarray], prefix: str, portrait: ChromaticPhasePortrait
) -> None:
    arrays[f"{prefix}_rgb"] = l30.cpu(portrait.rgb)
    arrays[f"{prefix}_amplitude"] = l30.cpu(portrait.panel_amplitude)
    arrays[f"{prefix}_phase"] = l30.cpu(portrait.panel_phase)
    arrays[f"{prefix}_peak"] = l30.cpu(portrait.panel_peak_amplitude)


def comparison_mosaic(first: torch.Tensor, after: torch.Tensor) -> torch.Tensor:
    side = first.shape[-1]
    vertical = first.new_zeros(3, side, 1)
    top = torch.cat((first[0], vertical, first[1]), dim=2)
    bottom = torch.cat((after[0], vertical, after[1]), dim=2)
    horizontal = first.new_zeros(3, 1, 2 * side + 1)
    return torch.cat((top, horizontal, bottom), dim=1)


def run_board(
    device: torch.device, dtype: torch.dtype
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    controller = CyclicChromaticFieldController(
        CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
    )
    state = controller.new_state(batch_size=2, device=device, dtype=dtype)
    first_symbols = torch.tensor((252, 132), device=device, dtype=torch.int64)
    first_tick = controller.tick(state, symbols=first_symbols, steps=8, trust=1.0)
    first_state = first_tick.state
    first_before = first_state.field.clone()
    first = chromatic_phase_portrait(
        controller, first_state, panel_side=PANEL_SIDE
    )
    first_read_only = torch.equal(first_state.field, first_before)

    tail_symbols = torch.tensor((139, 139), device=device, dtype=torch.int64)
    after_tick = controller.tick(
        first_state, symbols=tail_symbols, steps=8, trust=1.0
    )
    after_state = after_tick.state
    after_before = after_state.field.clone()
    after = chromatic_phase_portrait(
        controller, after_state, panel_side=PANEL_SIDE
    )
    after_read_only = torch.equal(after_state.field, after_before)
    comparison = comparison_mosaic(first.rgb, after.rgb)

    arrays: dict[str, np.ndarray] = {
        "schema_id": np.asarray(TRACE_SCHEMA),
        "histories": np.asarray(HISTORIES, dtype=np.int64),
        "first_field": l30.cpu(first_state.field),
        "after_field": l30.cpu(after_state.field),
        "comparison_rgb": l30.cpu(comparison),
        "read_only_equal": np.asarray(
            first_read_only and after_read_only, dtype=np.bool_
        ),
    }
    portrait_arrays(arrays, "first", first)
    portrait_arrays(arrays, "after", after)
    energy = torch.stack(
        (
            controller.dynamic_energy(first_state),
            controller.dynamic_energy(after_state),
        )
    )
    drift = torch.stack(
        (first_tick.input_energy_drift, after_tick.input_energy_drift)
    )
    arrays["dynamic_energy"] = l30.cpu(energy)
    arrays["input_energy_drift"] = l30.cpu(drift)
    arrays["clamp_count"] = np.asarray(
        first_tick.clamp_count + after_tick.clamp_count, dtype=np.int64
    )
    return {
        "maximum_dynamic_energy": float(energy.max().item()),
        "maximum_absolute_input_energy_drift": float(drift.abs().max().item()),
        "clamp_count": int(arrays["clamp_count"].item()),
        "read_only_equal": bool(arrays["read_only_equal"].item()),
    }, arrays


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
        raise L36RunnerError(f"missing bound source files: {missing!r}")
    hashes = {
        path.relative_to(ROOT).as_posix(): l30.sha256_file(path)
        for path in SOURCE_PATHS
    }
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA,
        "status": "INCOMPLETE",
        "layout_profile_id": CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID,
        "operator_profile_id": CYCLIC_CHROMATIC_OPERATOR_PROFILE_ID,
        "projection_profile_id": CHROMATIC_PHASE_PORTRAIT_PROFILE_ID,
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
            "mode_count": MODE_COUNT,
            "batch_size": 2,
            "panel_side": PANEL_SIDE,
            "output_side": 2 * PANEL_SIDE + 1,
            "histories": [list(history) for history in HISTORIES],
            "evolution_steps": 8,
            "oracle_error_ceiling": 5.0e-5,
            "rgb_range_floor": 0.50,
            "rgb_std_floor": 0.05,
        },
        "trace": {"path": TRACE_NAME, "sha256": None},
        "projection": {"path": PNG_NAME, "sha256": None},
        "arms": {},
    }
    l30.atomic_json(board_path, board)
    try:
        started = time.perf_counter()
        metrics, arrays = run_board(device, dtype)
        l30.atomic_npz(trace_path, arrays)
        l30.write_projection_png(png_path, arrays["comparison_rgb"])
        board["arms"]["canonical"] = metrics
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
