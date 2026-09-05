"""Run the frozen L40 rolling ordered-relational recall board."""

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
from cassi_ordered_relational_field import (
    ORDERED_RELATIONAL_LAYOUT_PROFILE_ID,
    ORDERED_RELATIONAL_OPERATOR_PROFILE_ID,
    ORDERED_RELATIONAL_PROJECTION_PROFILE_ID,
    OrderedRelationalChromaticFieldConfig,
    OrderedRelationalChromaticFieldController,
)

BOARD_SCHEMA = "cassi.l40.rolling-ordered-relational-board.v1"
TRACE_SCHEMA = "cassi.l40.rolling-ordered-relational-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L40-ROLLING-ORDERED-RELATIONAL-RECALL-PREREG.md"
RUNNER = ROOT / "verification" / "run_l40_rolling_ordered_relational_recall.py"
VERIFIER = ROOT / "verification" / "verify_l40_rolling_ordered_relational_recall.py"
OUTPUT_DIR = ROOT / "_diag" / "l40-rolling-ordered-relational-recall"
BOARD_NAME = "l40-rolling-board.json"
TRACE_NAME = "l40-rolling-traces.npz"
MODE_COUNT = 2048
ACTIVE_WIDTH = MODE_COUNT // 2
CHANNELS = 7
BATCH_SIZE = 8
ALPHABET_SIZE = 260
EVOLUTION_STEPS = 8
BLANK_TICKS = 16
MAX_MODE_AMPLITUDE = 8.0
MAX_EPSILON = MAX_MODE_AMPLITUDE**4
CHECKPOINT_NAMES = (
    "s0-deposit",
    "s0-horizon",
    "s1-deposit",
    "s1-horizon",
    "s2-deposit",
    "s2-horizon",
    "s3-reversal-deposit",
    "s3-reversal-horizon",
)
S0 = np.asarray(l30.TARGETS, dtype=np.int64)
STAGES = np.stack((S0, (S0 + 97) % ALPHABET_SIZE, (S0 + 181) % ALPHABET_SIZE, (S0 + 97) % ALPHABET_SIZE))
EXPECTED_CURRENT = np.repeat(STAGES, 2, axis=0)
EXPECTED_PREDECESSOR = np.repeat(
    np.stack(
        (
            np.full(BATCH_SIZE, -1, dtype=np.int64),
            STAGES[0],
            STAGES[1],
            STAGES[2],
        )
    ),
    2,
    axis=0,
)
SOURCE_PATHS = (
    PREREGISTRATION,
    ROOT / "cassi_qi_field.py",
    ROOT / "cassi_prismatic_field.py",
    ROOT / "cassi_white_chromatic_field.py",
    ROOT / "cassi_cyclic_chromatic_field.py",
    ROOT / "cassi_relational_chromatic_field.py",
    ROOT / "cassi_ordered_relational_field.py",
    ROOT / "verification" / "run_l30_white_chromatic_field.py",
    ROOT / "verification" / "verify_l30_white_chromatic_field.py",
    RUNNER,
    VERIFIER,
)


class L40RollingRunnerError(RuntimeError):
    """The canonical rolling board could not be completed."""


def _capture(
    controller: OrderedRelationalChromaticFieldController,
    state: Any,
) -> dict[str, np.ndarray]:
    before = l30.cpu(state.field.clone())
    readout = controller.white_readout(state)
    return {
        "checkpoint_fields": before,
        "post_readout_fields": l30.cpu(state.field),
        "emitted_symbols": l30.cpu(readout.symbols),
        "current_available": l30.cpu(readout.available),
        "current_scores": l30.cpu(readout.current_scores),
        "current_symbols": l30.cpu(readout.current_symbols),
        "relational_scores": l30.cpu(readout.relational_scores),
        "relational_symbols": l30.cpu(readout.relational_symbols),
        "relational_available": l30.cpu(readout.relational_available),
        "ordered_scores": l30.cpu(readout.scores),
    }


def run_board(
    device: torch.device, dtype: torch.dtype
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    config = OrderedRelationalChromaticFieldConfig(mode_count=MODE_COUNT)
    controller = OrderedRelationalChromaticFieldController(config)
    state = controller.new_state(batch_size=BATCH_SIZE, device=device, dtype=dtype)
    state, heartbeat = controller.heartbeat(state)
    clamp_counts = [int(heartbeat.clamp_count)]
    input_drifts: list[np.ndarray] = []
    checkpoints: list[dict[str, np.ndarray]] = []
    maximum_absolute_field = float(state.field.abs().max().item())

    for symbols in STAGES:
        tick = controller.tick(
            state,
            symbols=torch.as_tensor(symbols, device=device, dtype=torch.int64),
            steps=EVOLUTION_STEPS,
            trust=1.0,
        )
        state = tick.state
        clamp_counts.append(int(tick.clamp_count))
        input_drifts.append(l30.cpu(tick.input_energy_drift))
        maximum_absolute_field = max(
            maximum_absolute_field, float(state.field.abs().max().item())
        )
        checkpoints.append(_capture(controller, state))

        for _ in range(BLANK_TICKS):
            tick = controller.tick(state, steps=EVOLUTION_STEPS)
            state = tick.state
            clamp_counts.append(int(tick.clamp_count))
            input_drifts.append(l30.cpu(tick.input_energy_drift))
            maximum_absolute_field = max(
                maximum_absolute_field, float(state.field.abs().max().item())
            )
        checkpoints.append(_capture(controller, state))

    arrays: dict[str, np.ndarray] = {
        "schema_id": np.asarray(TRACE_SCHEMA),
        "checkpoint_names": np.asarray(CHECKPOINT_NAMES, dtype="<U24"),
        "codebook": l30.cpu(controller.codebook(device=device, dtype=dtype)),
        "expected_current": EXPECTED_CURRENT,
        "expected_predecessor": EXPECTED_PREDECESSOR,
        "clamp_counts": np.asarray(clamp_counts, dtype=np.int64),
        "input_energy_drift": np.stack(input_drifts).astype(np.float32, copy=False),
        "maximum_input_energy_drift": np.asarray(
            np.abs(np.stack(input_drifts)).max(), dtype=np.float32
        ),
        "maximum_absolute_field": np.asarray(
            maximum_absolute_field, dtype=np.float32
        ),
    }
    for name in checkpoints[0]:
        arrays[name] = np.stack([checkpoint[name] for checkpoint in checkpoints])

    mutation_count = int(
        np.count_nonzero(arrays["checkpoint_fields"] != arrays["post_readout_fields"])
    )
    metrics = {
        "checkpoint_count": len(checkpoints),
        "tick_count": len(input_drifts),
        "clamp_count": int(arrays["clamp_counts"].sum()),
        "maximum_input_energy_drift": float(arrays["maximum_input_energy_drift"]),
        "maximum_absolute_field": float(arrays["maximum_absolute_field"]),
        "readout_mutation_count": mutation_count,
    }
    return metrics, arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="float32", choices=("float32", "float64"))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    device = torch.device(args.device)
    dtype = torch.float64 if args.dtype == "float64" else torch.float32
    output_dir = args.output_dir.resolve()
    board_path = output_dir / BOARD_NAME
    trace_path = output_dir / TRACE_NAME
    missing = [str(path) for path in SOURCE_PATHS if not path.is_file()]
    if missing:
        raise L40RollingRunnerError(f"missing bound source files: {missing!r}")
    hashes = {
        path.relative_to(ROOT).as_posix(): l30.sha256_file(path)
        for path in SOURCE_PATHS
    }
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA,
        "status": "INCOMPLETE",
        "layout_profile_id": ORDERED_RELATIONAL_LAYOUT_PROFILE_ID,
        "operator_profile_id": ORDERED_RELATIONAL_OPERATOR_PROFILE_ID,
        "projection_profile_id": ORDERED_RELATIONAL_PROJECTION_PROFILE_ID,
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
            "channels": CHANNELS,
            "mode_count": MODE_COUNT,
            "active_modes": ACTIVE_WIDTH,
            "alphabet_size": ALPHABET_SIZE,
            "batch_size": BATCH_SIZE,
            "evolution_steps": EVOLUTION_STEPS,
            "blank_ticks": BLANK_TICKS,
            "checkpoints": list(CHECKPOINT_NAMES),
            "stage_symbols": STAGES.tolist(),
            "current_slot": 3.0,
            "predecessor_slot": 2.0,
            "readout_energy_floor": 1.0e-8,
            "maximum_input_energy_drift": 2.0e-6,
            "max_mode_amplitude": MAX_MODE_AMPLITUDE,
            "max_epsilon": MAX_EPSILON,
        },
        "trace": {"path": TRACE_NAME, "sha256": None},
        "arms": {},
    }
    l30.atomic_json(board_path, board)
    try:
        started = time.perf_counter()
        metrics, arrays = run_board(device, dtype)
        l30.atomic_npz(trace_path, arrays)
        board["arms"]["canonical"] = metrics
        board["trace"] = {
            "path": TRACE_NAME,
            "sha256": l30.sha256_file(trace_path),
            "array_count": len(arrays),
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
