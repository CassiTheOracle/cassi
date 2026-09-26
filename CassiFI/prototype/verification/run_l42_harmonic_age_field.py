"""Run the frozen L42 harmonic age ladder board."""

from __future__ import annotations

import argparse
import sys
import time
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.run_l30_white_chromatic_field as l30
import verification.run_l31_cyclic_chromatic_field as l31
from cassi_harmonic_age_field import (
    HARMONIC_AGE_INDICES,
    HARMONIC_AGE_LAYOUT_PROFILE_ID,
    HARMONIC_AGE_OPERATOR_PROFILE_ID,
    HARMONIC_AGE_PROJECTION_PROFILE_ID,
    HarmonicAgeFieldConfig,
    HarmonicAgeFieldController,
)

BOARD_SCHEMA = "cassi.l42.harmonic-age-ladder-board.v1"
TRACE_SCHEMA = "cassi.l42.harmonic-age-ladder-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L42-HARMONIC-AGE-LADDER-PREREG.md"
L30_MODULE = ROOT / "cassi_white_chromatic_field.py"
L31_MODULE = ROOT / "cassi_cyclic_chromatic_field.py"
MODULE = ROOT / "cassi_harmonic_age_field.py"
L30_RUNNER = ROOT / "verification" / "run_l30_white_chromatic_field.py"
L30_VERIFIER = ROOT / "verification" / "verify_l30_white_chromatic_field.py"
L31_RUNNER = ROOT / "verification" / "run_l31_cyclic_chromatic_field.py"
L31_VERIFIER = ROOT / "verification" / "verify_l31_cyclic_chromatic_field.py"
RUNNER = ROOT / "verification" / "run_l42_harmonic_age_field.py"
VERIFIER = ROOT / "verification" / "verify_l42_harmonic_age_field.py"
OUTPUT_DIR = ROOT / "_diag" / "l42-harmonic-age-ladder"
BOARD_NAME = "l42-board.json"
TRACE_NAME = "l42-traces.npz"
PNG_NAME = "l42-projection.png"


class L42RunnerError(RuntimeError):
    """The frozen L42 board could not be completed."""


def inherited_age_traces(
    arrays: dict[str, np.ndarray], device: torch.device, dtype: torch.dtype
) -> None:
    controller = HarmonicAgeFieldController(
        HarmonicAgeFieldConfig(mode_count=l30.MODE_COUNT)
    )
    reference = controller.new_state(device=device, dtype=dtype)
    phase = controller._constants(reference)["channel_phase"]
    harmonics = torch.tensor(
        HARMONIC_AGE_INDICES, device=device, dtype=torch.int64
    )
    basis = phase.conj()[None, :].pow(harmonics[:, None]) / math.sqrt(
        l30.CHANNELS
    )
    phase_parts = controller.codebook(0, device=device, dtype=dtype)
    codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])

    task_d = torch.as_tensor(arrays["task_read_d"], device=device)
    task_collapsed = torch.einsum("hc,rcwb->rhwb", basis, task_d)
    task_coefficients = torch.einsum(
        "aw,rhwb->rhba", codebook.conj(), task_collapsed
    ) / float(l30.ACTIVE_WIDTH)
    task_scores = task_coefficients.abs().square().permute(0, 2, 1, 3)
    task_available = torch.as_tensor(
        arrays["task_read_available"], device=device
    )[:, :, None] & (
        task_scores.amax(dim=3) >= controller.config.readout_energy_floor
    )
    arrays["task_read_age_scores"] = l30.cpu(task_scores)
    arrays["task_read_age_symbols"] = l30.cpu(torch.argmax(task_scores, dim=3))
    arrays["task_read_age_available"] = l30.cpu(task_available)

    pre_d = torch.as_tensor(arrays["pre_target_d"], device=device)
    pre_collapsed = torch.einsum("hc,cwb->hwb", basis, pre_d)
    pre_coefficients = torch.einsum(
        "aw,hwb->hba", codebook.conj(), pre_collapsed
    ) / float(l30.ACTIVE_WIDTH)
    pre_scores = pre_coefficients.abs().square().permute(1, 0, 2)
    pre_available = torch.as_tensor(
        arrays["pre_readout_available"], device=device
    )[:, None] & (
        pre_scores.amax(dim=2) >= controller.config.readout_energy_floor
    )
    arrays["pre_readout_age_scores"] = l30.cpu(pre_scores)
    arrays["pre_readout_age_symbols"] = l30.cpu(torch.argmax(pre_scores, dim=2))
    arrays["pre_readout_age_available"] = l30.cpu(pre_available)


def inherited_board(
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
        l30.WhiteChromaticFieldConfig = HarmonicAgeFieldConfig
        l30.WhiteChromaticFieldController = HarmonicAgeFieldController
        l30.TRACE_SCHEMA = TRACE_SCHEMA
        l30.coordinates = l31.native_coordinates
        l30.channel_energy = l31.native_channel_energy
        result, arrays = l30.run_board(device, dtype)
        inherited_age_traces(arrays, device, dtype)
        return result, arrays
    finally:
        (
            l30.WhiteChromaticFieldConfig,
            l30.WhiteChromaticFieldController,
            l30.TRACE_SCHEMA,
            l30.coordinates,
            l30.channel_energy,
        ) = previous


def four_deposit_arm(
    device: torch.device, dtype: torch.dtype
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    controller = HarmonicAgeFieldController(
        HarmonicAgeFieldConfig(mode_count=l30.MODE_COUNT)
    )
    sequences = np.column_stack(
        (
            np.asarray(l30.TARGETS, dtype=np.int64),
            np.asarray(l30.DISTRACTORS, dtype=np.int64),
            np.roll(np.asarray(l30.TARGETS, dtype=np.int64), -1),
            np.roll(np.asarray(l30.DISTRACTORS, dtype=np.int64), -1),
        )
    )
    state = controller.new_state(
        batch_size=l30.BATCH_SIZE, device=device, dtype=dtype
    )
    shape = (4, l30.BATCH_SIZE)
    post_d = np.empty(
        (4, l30.CHANNELS, l30.ACTIVE_WIDTH, l30.BATCH_SIZE),
        dtype=np.complex64 if dtype == torch.float32 else np.complex128,
    )
    post_scores = np.empty((*shape, l30.ALPHABET_SIZE), dtype=np.float32)
    post_symbols = np.empty(shape, dtype=np.int64)
    post_available = np.zeros(shape, dtype=np.bool_)
    post_age_scores = np.empty(
        (*shape, l30.CHANNELS, l30.ALPHABET_SIZE), dtype=np.float32
    )
    post_age_symbols = np.empty((*shape, l30.CHANNELS), dtype=np.int64)
    post_age_available = np.zeros((*shape, l30.CHANNELS), dtype=np.bool_)
    energy = np.empty((4, l30.CHANNELS, l30.BATCH_SIZE), dtype=np.float32)
    input_drift = np.empty(shape, dtype=np.float32)
    clamp_count = np.zeros(4, dtype=np.int64)
    lift_arrays: dict[str, np.ndarray] = {}

    for position in range(4):
        symbols = torch.as_tensor(
            sequences[:, position], device=device, dtype=torch.int64
        )
        tick = controller.tick(
            state,
            symbols=symbols,
            steps=l30.EVOLUTION_STEPS,
            trust=1.0,
        )
        state = tick.state
        readout = controller.white_readout(state)
        post_d[position] = l30.cpu(l31.native_coordinates(state)[1])
        post_scores[position] = l30.cpu(readout.scores)
        post_symbols[position] = l30.cpu(readout.symbols)
        post_available[position] = l30.cpu(readout.available)
        post_age_scores[position] = l30.cpu(readout.age_scores)
        post_age_symbols[position] = l30.cpu(readout.age_symbols)
        post_age_available[position] = l30.cpu(readout.age_available)
        energy[position] = l30.cpu(controller._dynamic_energy_unchecked(state))
        input_drift[position] = l30.cpu(tick.input_energy_drift)
        clamp_count[position] = tick.clamp_count
        if position == 0:
            lifted = controller.lift_harmonics(state)
            for prefix, candidate in (("pre", state), ("post", lifted)):
                common, differential, common_velocity, differential_velocity = (
                    l31.native_coordinates(candidate)
                )
                lift_arrays[f"four_lift_{prefix}_c"] = l30.cpu(common)
                lift_arrays[f"four_lift_{prefix}_d"] = l30.cpu(differential)
                lift_arrays[f"four_lift_{prefix}_vc"] = l30.cpu(common_velocity)
                lift_arrays[f"four_lift_{prefix}_vd"] = l30.cpu(
                    differential_velocity
                )
            lift_arrays["four_lift_energy_before"] = l30.cpu(
                controller._dynamic_energy_unchecked(state)
            )
            lift_arrays["four_lift_energy_after"] = l30.cpu(
                controller._dynamic_energy_unchecked(lifted)
            )

    blank_energy = np.empty(
        (8, l30.CHANNELS, l30.BATCH_SIZE), dtype=np.float32
    )
    blank_drift = np.empty((8, l30.BATCH_SIZE), dtype=np.float32)
    blank_clamp_count = np.zeros(8, dtype=np.int64)
    for tick_index in range(8):
        tick = controller.tick(
            state, symbols=None, steps=l30.EVOLUTION_STEPS, trust=1.0
        )
        state = tick.state
        blank_energy[tick_index] = l30.cpu(
            controller._dynamic_energy_unchecked(state)
        )
        blank_drift[tick_index] = l30.cpu(tick.input_energy_drift)
        blank_clamp_count[tick_index] = tick.clamp_count
    final = controller.white_readout(state)
    final_d = l30.cpu(l31.native_coordinates(state)[1])

    arrays = {
        "four_sequences": sequences,
        "four_age_harmonics": np.asarray(HARMONIC_AGE_INDICES, dtype=np.int64),
        "four_post_d": post_d,
        "four_post_scores": post_scores,
        "four_post_symbols": post_symbols,
        "four_post_available": post_available,
        "four_post_age_scores": post_age_scores,
        "four_post_age_symbols": post_age_symbols,
        "four_post_age_available": post_age_available,
        "four_energy": energy,
        "four_input_energy_drift": input_drift,
        "four_clamp_count": clamp_count,
        "four_blank_energy": blank_energy,
        "four_blank_input_energy_drift": blank_drift,
        "four_blank_clamp_count": blank_clamp_count,
        "four_blank_final_d": final_d,
        "four_blank_final_field": l30.cpu(state.field),
        "four_blank_final_scores": l30.cpu(final.scores),
        "four_blank_final_symbols": l30.cpu(final.symbols),
        "four_blank_final_available": l30.cpu(final.available),
        "four_blank_final_age_scores": l30.cpu(final.age_scores),
        "four_blank_final_age_symbols": l30.cpu(final.age_symbols),
        "four_blank_final_age_available": l30.cpu(final.age_available),
        **lift_arrays,
    }
    expected = np.flip(sequences, axis=1)
    post_top4 = np.argsort(-post_scores[3], axis=1, kind="stable")[:, :4]
    blank_top4 = np.argsort(
        -arrays["four_blank_final_scores"], axis=1, kind="stable"
    )[:, :4]
    metrics = {
        "immediate_emitted_symbol_accuracy": float(
            np.mean(post_symbols == sequences.T)
        ),
        "reverse_top4_accuracy_after_fourth": float(np.mean(post_top4 == expected)),
        "reverse_top4_accuracy_after_blank": float(np.mean(blank_top4 == expected)),
        "maximum_total_mean_dynamic_energy": float(
            max(np.mean(energy, axis=1).max(), np.mean(blank_energy, axis=1).max())
        ),
        "maximum_absolute_input_energy_drift": float(
            max(np.abs(input_drift).max(), np.abs(blank_drift).max())
        ),
        "clamp_count": int(clamp_count.sum() + blank_clamp_count.sum()),
    }
    return metrics, arrays


def run_board(
    device: torch.device, dtype: torch.dtype
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    inherited, arrays = inherited_board(device, dtype)
    four_metrics, four_arrays = four_deposit_arm(device, dtype)
    arrays.update(four_arrays)
    return {
        "declaration": inherited["declaration"],
        "metrics": inherited["metrics"],
        "four_deposit_metrics": four_metrics,
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
        raise L42RunnerError(f"missing bound source files: {missing!r}")
    hashes = {
        path.relative_to(ROOT).as_posix(): l30.sha256_file(path)
        for path in source_paths
    }
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA,
        "status": "INCOMPLETE",
        "layout_profile_id": HARMONIC_AGE_LAYOUT_PROFILE_ID,
        "operator_profile_id": HARMONIC_AGE_OPERATOR_PROFILE_ID,
        "projection_profile_id": HARMONIC_AGE_PROJECTION_PROFILE_ID,
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
            "age_harmonics": list(HARMONIC_AGE_INDICES),
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
