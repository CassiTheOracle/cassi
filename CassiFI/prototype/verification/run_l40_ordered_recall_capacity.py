"""Run the frozen L40 ordered-recall held-out capacity board."""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path
from typing import Any, Callable

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
from cassi_ordered_relational_field import (
    ORDERED_RELATIONAL_LAYOUT_PROFILE_ID,
    ORDERED_RELATIONAL_OPERATOR_PROFILE_ID,
    ORDERED_RELATIONAL_PROJECTION_PROFILE_ID,
    OrderedRelationalChromaticFieldConfig,
    OrderedRelationalChromaticFieldController,
)

BOARD_SCHEMA = "cassi.l40.ordered-recall-capacity-board.v1"
TRACE_SCHEMA = "cassi.l40.ordered-recall-capacity-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L40-ORDERED-RECALL-CAPACITY-PREREG.md"
RUNNER = ROOT / "verification" / "run_l40_ordered_recall_capacity.py"
VERIFIER = ROOT / "verification" / "verify_l40_ordered_recall_capacity.py"
OUTPUT_DIR = ROOT / "_diag" / "l40-ordered-recall-capacity"
BOARD_NAME = "l40-board.json"
TRACE_NAME = "l40-traces.npz"
DOMAIN = b"cassi-l40-ordered-recall-capacity.v1"
DEPTHS = (1, 2, 4, 8, 16)
BATCH_SIZE = 16
MAX_DEPTH = max(DEPTHS)
MODE_COUNT = 2048
ALPHABET_SIZE = 260
EVOLUTION_STEPS = 8
EXPOSED = frozenset(
    (0, 22, 37, 59, 74, 96, 97, 111, 134, 148, 171, 185, 208, 222, 245, 259)
)
POOL = tuple(symbol for symbol in range(ALPHABET_SIZE) if symbol not in EXPOSED)
PROFILE_IDENTITIES = (
    {
        "name": "l31-cyclic",
        "layout_profile_id": CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID,
        "operator_profile_id": CYCLIC_CHROMATIC_OPERATOR_PROFILE_ID,
        "projection_profile_id": CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID,
    },
    {
        "name": "l39-ordered",
        "layout_profile_id": ORDERED_RELATIONAL_LAYOUT_PROFILE_ID,
        "operator_profile_id": ORDERED_RELATIONAL_OPERATOR_PROFILE_ID,
        "projection_profile_id": ORDERED_RELATIONAL_PROJECTION_PROFILE_ID,
    },
)
PROFILE_FACTORIES: tuple[tuple[str, Callable[[], Any]], ...] = (
    (
        "l31-cyclic",
        lambda: CyclicChromaticFieldController(
            CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
    ),
    (
        "l39-ordered",
        lambda: OrderedRelationalChromaticFieldController(
            OrderedRelationalChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
    ),
)
SOURCE_PATHS = (
    PREREGISTRATION,
    ROOT / "cassi_white_chromatic_field.py",
    ROOT / "cassi_cyclic_chromatic_field.py",
    ROOT / "cassi_relational_chromatic_field.py",
    ROOT / "cassi_ordered_relational_field.py",
    ROOT / "verification" / "run_l30_white_chromatic_field.py",
    RUNNER,
    VERIFIER,
)


class L40RunnerError(RuntimeError):
    """The canonical L40 capacity board could not be completed."""


def _draw(parts: tuple[object, ...], used: set[int]) -> int:
    attempt = 0
    while True:
        payload = b"\0".join(
            (
                DOMAIN,
                *(str(part).encode("ascii") for part in parts),
                str(attempt).encode("ascii"),
            )
        )
        candidate = POOL[
            int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % len(POOL)
        ]
        if candidate not in used:
            return candidate
        attempt += 1


def heldout_sequences() -> np.ndarray:
    sequences = np.full(
        (len(DEPTHS), BATCH_SIZE, MAX_DEPTH), -1, dtype=np.int64
    )
    for depth_index, depth in enumerate(DEPTHS):
        for pair in range(BATCH_SIZE // 2):
            tail = _draw((depth, pair, "final"), set())
            for history in (2 * pair, 2 * pair + 1):
                used = {tail}
                prefix: list[int] = []
                for position in range(depth - 1):
                    symbol = _draw((depth, history, position), used)
                    prefix.append(symbol)
                    used.add(symbol)
                sequences[depth_index, history, :depth] = (*prefix, tail)
    return sequences


def run_board(
    device: torch.device, dtype: torch.dtype
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    sequences = heldout_sequences()
    profile_count = len(PROFILE_FACTORIES)
    depth_count = len(DEPTHS)
    step_shape = (profile_count, depth_count, BATCH_SIZE, MAX_DEPTH)
    scores = np.zeros((*step_shape, ALPHABET_SIZE), dtype=np.float32)
    available = np.zeros(step_shape, dtype=np.bool_)
    coherence = np.zeros(step_shape, dtype=np.float32)
    energy = np.zeros(step_shape, dtype=np.float32)
    input_drift = np.zeros(step_shape, dtype=np.float32)
    clamp_counts = np.zeros((profile_count, depth_count), dtype=np.int64)

    for profile_index, (_, factory) in enumerate(PROFILE_FACTORIES):
        controller = factory()
        for depth_index, depth in enumerate(DEPTHS):
            state = controller.new_state(
                batch_size=BATCH_SIZE, device=device, dtype=dtype
            )
            for position in range(depth):
                symbols = torch.as_tensor(
                    sequences[depth_index, :, position],
                    device=device,
                    dtype=torch.int64,
                )
                tick = controller.tick(
                    state, symbols=symbols, steps=EVOLUTION_STEPS, trust=1.0
                )
                state = tick.state
                scores[profile_index, depth_index, :, position] = l30.cpu(
                    tick.readout.scores
                )
                available[profile_index, depth_index, :, position] = l30.cpu(
                    tick.readout.available
                )
                coherence[profile_index, depth_index, :, position] = l30.cpu(
                    tick.readout.white_coherence
                )
                energy[profile_index, depth_index, :, position] = l30.cpu(
                    controller.dynamic_energy(state)
                )
                input_drift[profile_index, depth_index, :, position] = l30.cpu(
                    tick.input_energy_drift
                )
                clamp_counts[profile_index, depth_index] += tick.clamp_count

    arrays = {
        "schema_id": np.asarray(TRACE_SCHEMA),
        "profile_names": np.asarray(
            [name for name, _ in PROFILE_FACTORIES], dtype="<U32"
        ),
        "depths": np.asarray(DEPTHS, dtype=np.int64),
        "sequences": sequences,
        "scores": scores,
        "available": available,
        "white_coherence": coherence,
        "dynamic_energy": energy,
        "input_energy_drift": input_drift,
        "clamp_counts": clamp_counts,
    }
    return {
        "profile_count": profile_count,
        "history_count_per_depth": BATCH_SIZE,
        "maximum_dynamic_energy": float(energy.max()),
        "maximum_absolute_input_energy_drift": float(np.abs(input_drift).max()),
        "clamp_count": int(clamp_counts.sum()),
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
    missing = [str(path) for path in SOURCE_PATHS if not path.is_file()]
    if missing:
        raise L40RunnerError(f"missing bound source files: {missing!r}")
    hashes = {
        path.relative_to(ROOT).as_posix(): l30.sha256_file(path)
        for path in SOURCE_PATHS
    }
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA,
        "status": "INCOMPLETE",
        "trace_schema_id": TRACE_SCHEMA,
        "preregistration_sha256": hashes[
            PREREGISTRATION.relative_to(ROOT).as_posix()
        ],
        "source_sha256": hashes,
        "profiles": list(PROFILE_IDENTITIES),
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
            "alphabet_size": ALPHABET_SIZE,
            "batch_size": BATCH_SIZE,
            "depths": list(DEPTHS),
            "evolution_steps": EVOLUTION_STEPS,
            "retained_mrr_floor": 0.05,
            "paired_distance_floor": 0.01,
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
