"""Run the frozen L29 resource-matched phi-prismatic heartbeat board."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_prismatic_field import (
    PHI,
    PRISMATIC_LAYOUT_PROFILE_ID,
    PRISMATIC_OPERATOR_PROFILE_ID,
    PrismaticFieldConfig,
    PrismaticFieldController,
)
from cassi_qi_field import QiFieldState

BOARD_SCHEMA = "cassi.l29.phi-prismatic-heartbeat-board.v1"
TRACE_SCHEMA = "cassi.l29.phi-prismatic-heartbeat-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L29-PHI-PRISMATIC-HEARTBEAT-PREREG.md"
OUTPUT_DIR = ROOT / "_diag" / "l29-phi-prismatic-heartbeat"
BOARD_NAME = "l29-board.json"
TRACE_NAME = "l29-traces.npz"
TARGETS = (0, 37, 74, 111, 148, 185, 222, 259)
DISTRACTORS = tuple((value + 97) % 260 for value in TARGETS)
READ_TICKS = (0, 1, 2, 4, 8, 16, 32, 64)
LONG_TICKS = (16, 32, 64)
WARM_TICKS = 128
BEATING_TICKS = 128
TASK_TICKS = 65
EVOLUTION_STEPS = 16
SOURCE_PATHS = (
    PREREGISTRATION,
    ROOT / "cassi_prismatic_field.py",
    ROOT / "verification" / "run_l29_phi_prismatic_heartbeat.py",
    ROOT / "verification" / "verify_l29_phi_prismatic_heartbeat.py",
)


class L29RunnerError(RuntimeError):
    """The frozen board cannot produce a complete canonical artifact."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def atomic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            np.savez(handle, **arrays)  # type: ignore[arg-type]
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def arm_declarations() -> dict[str, dict[str, Any]]:
    slow = PHI**6
    return {
        "phi-7": {
            "mode_count": 3512,
            "timescales": tuple(PHI**index for index in range(7)),
        },
        "linear-time-7": {
            "mode_count": 3512,
            "timescales": tuple(
                1.0 + index * (slow - 1.0) / 6.0 for index in range(7)
            ),
        },
        "linear-frequency-7": {
            "mode_count": 3512,
            "timescales": tuple(
                1.0 / (1.0 - index * (1.0 - PHI**-6) / 6.0)
                for index in range(7)
            ),
        },
        "geometric-4": {
            "mode_count": 6146,
            "timescales": (1.0, PHI**2, PHI**4, PHI**6),
        },
    }


def active_coordinates(
    state: QiFieldState, mode_count: int
) -> tuple[Tensor, Tensor, Tensor, Tensor]:
    bank_count, _, batch_size = state.field.shape
    width = mode_count // 2
    parts = state.field.reshape(bank_count, 9, mode_count, batch_size)
    y = torch.complex(parts[:, 0, :width], parts[:, 1, :width])
    yin = torch.complex(parts[:, 2, :width], parts[:, 3, :width])
    vy = torch.complex(parts[:, 4, :width], parts[:, 5, :width])
    vi = torch.complex(parts[:, 6, :width], parts[:, 7, :width])
    return PHI * y + yin, y - PHI * yin, PHI * vy + vi, vy - PHI * vi


def cpu(value: Tensor) -> np.ndarray:
    return value.detach().cpu().numpy()


def store_coordinates(
    arrays: dict[str, np.ndarray], prefix: str, state: QiFieldState, mode_count: int
) -> None:
    common, differential, common_velocity, differential_velocity = (
        active_coordinates(state, mode_count)
    )
    arrays[f"{prefix}_c"] = cpu(common)
    arrays[f"{prefix}_d"] = cpu(differential)
    arrays[f"{prefix}_vc"] = cpu(common_velocity)
    arrays[f"{prefix}_vd"] = cpu(differential_velocity)


def ranks(scores: np.ndarray, symbols: np.ndarray) -> np.ndarray:
    """One-based descending ranks with smaller symbol IDs winning exact ties."""

    selected = np.take_along_axis(scores, symbols[:, None], axis=1)[:, 0]
    ids = np.arange(scores.shape[1], dtype=np.int64)[None, :]
    return (
        1
        + (scores > selected[:, None]).sum(axis=1)
        + ((scores == selected[:, None]) & (ids < symbols[:, None])).sum(axis=1)
    ).astype(np.int64)


def beating_metrics(values: np.ndarray) -> tuple[float, list[dict[str, float | int]]]:
    median = float(np.median(values))
    beating = float(
        (np.quantile(values, 0.99, method="linear") - np.quantile(values, 0.01, method="linear"))
        / median
    )
    spectrum = np.abs(np.fft.rfft(values - values.mean()))
    candidates = list(range(1, spectrum.size))
    candidates.sort(key=lambda index: (-float(spectrum[index]), index))
    top = [
        {"bin": int(index), "amplitude": float(spectrum[index])}
        for index in candidates[:3]
    ]
    return beating, top


def clone_batch(state: QiFieldState, batch_size: int) -> QiFieldState:
    return QiFieldState(state.field.expand(-1, -1, batch_size).clone())


def run_arm(
    slug: str,
    declaration: dict[str, Any],
    device: torch.device,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    config = PrismaticFieldConfig(
        bank_timescales=tuple(declaration["timescales"]),
        mode_count=int(declaration["mode_count"]),
    )
    controller = PrismaticFieldController(config)
    mode_count = config.mode_count
    width = config.wave_mode_count
    bank_count = config.bank_count
    key = slug.replace("-", "_")
    arrays: dict[str, np.ndarray] = {}

    zero = controller.new_state(device=device, dtype=torch.float32)
    store_coordinates(arrays, f"{key}_zero_pre", zero, mode_count)
    zero_post, zero_drift = controller.modulate_symbols(zero.clone(), (0,))
    store_coordinates(arrays, f"{key}_zero_post", zero_post, mode_count)
    arrays[f"{key}_zero_drift"] = cpu(zero_drift)

    first = controller.new_state(device=device, dtype=torch.float32)
    store_coordinates(arrays, f"{key}_first_heartbeat_pre", first, mode_count)
    first, first_receipt = controller.heartbeat(first)
    store_coordinates(arrays, f"{key}_first_heartbeat_post", first, mode_count)
    arrays[f"{key}_first_heartbeat_source_weights"] = cpu(
        first_receipt.source_weights
    )
    arrays[f"{key}_first_heartbeat_energy_before"] = cpu(
        first_receipt.source_energy_before
    )
    arrays[f"{key}_first_heartbeat_energy_after"] = cpu(
        first_receipt.source_energy_after
    )
    arrays[f"{key}_first_heartbeat_injection"] = cpu(
        first_receipt.injected_energy
    )
    arrays[f"{key}_first_heartbeat_clamp"] = np.asarray(
        first_receipt.clamp_count, dtype=np.int64
    )
    arrays[f"{key}_codebook"] = cpu(
        controller._codebook_source.codebook(  # shared immutable boundary constant
            0, device=device, dtype=torch.float32
        )
    )

    warm_state = controller.new_state(device=device, dtype=torch.float32)
    warm_energy = np.empty((WARM_TICKS, bank_count), dtype=np.float32)
    warm_hamiltonian = np.empty(WARM_TICKS, dtype=np.float32)
    warm_injection = np.empty(WARM_TICKS, dtype=np.float32)
    warm_clamp = np.empty(WARM_TICKS, dtype=np.int64)
    warm_leakage = np.empty(WARM_TICKS, dtype=np.float32)
    for tick in range(WARM_TICKS):
        warm_state, receipt = controller._heartbeat_unchecked(warm_state)
        warm_state, evolve_clamps = controller._evolve_unchecked(
            warm_state, EVOLUTION_STEPS
        )
        warm_energy[tick] = cpu(controller._dynamic_energy_unchecked(warm_state))[:, 0]
        warm_hamiltonian[tick] = float(
            controller._hamiltonian_unchecked(warm_state)[0].item()
        )
        warm_injection[tick] = float(receipt.injected_energy[0].item())
        warm_clamp[tick] = receipt.clamp_count + evolve_clamps
        warm_leakage[tick] = float(
            active_coordinates(warm_state, mode_count)[1].abs().max().item()
        )
    warmed = warm_state.clone()

    beat_state = warmed.clone()
    beat_energy = np.empty((BEATING_TICKS, bank_count), dtype=np.float32)
    beat_hamiltonian = np.empty(BEATING_TICKS, dtype=np.float32)
    beat_injection = np.empty(BEATING_TICKS, dtype=np.float32)
    beat_clamp = np.empty(BEATING_TICKS, dtype=np.int64)
    beat_leakage = np.empty(BEATING_TICKS, dtype=np.float32)
    for tick in range(BEATING_TICKS):
        beat_state, receipt = controller._heartbeat_unchecked(beat_state)
        beat_state, evolve_clamps = controller._evolve_unchecked(
            beat_state, EVOLUTION_STEPS
        )
        beat_energy[tick] = cpu(controller._dynamic_energy_unchecked(beat_state))[:, 0]
        beat_hamiltonian[tick] = float(
            controller._hamiltonian_unchecked(beat_state)[0].item()
        )
        beat_injection[tick] = float(receipt.injected_energy[0].item())
        beat_clamp[tick] = receipt.clamp_count + evolve_clamps
        beat_leakage[tick] = float(
            active_coordinates(beat_state, mode_count)[1].abs().max().item()
        )

    arrays[f"{key}_warm_energy"] = warm_energy
    arrays[f"{key}_warm_hamiltonian"] = warm_hamiltonian
    arrays[f"{key}_warm_injection"] = warm_injection
    arrays[f"{key}_warm_clamp"] = warm_clamp
    arrays[f"{key}_warm_leakage"] = warm_leakage
    arrays[f"{key}_beat_energy"] = beat_energy
    arrays[f"{key}_beat_hamiltonian"] = beat_hamiltonian
    arrays[f"{key}_beat_injection"] = beat_injection
    arrays[f"{key}_beat_clamp"] = beat_clamp
    arrays[f"{key}_beat_leakage"] = beat_leakage

    task_state = clone_batch(warmed, len(TARGETS))
    target_tensor = torch.tensor(TARGETS, device=device, dtype=torch.int64)
    distractor_tensor = torch.tensor(DISTRACTORS, device=device, dtype=torch.int64)
    task_energy = np.empty(
        (TASK_TICKS, bank_count, len(TARGETS)), dtype=np.float32
    )
    task_hamiltonian = np.empty((TASK_TICKS, len(TARGETS)), dtype=np.float32)
    task_injection = np.empty((TASK_TICKS, len(TARGETS)), dtype=np.float32)
    task_clamp = np.empty(TASK_TICKS, dtype=np.int64)
    task_drift = np.zeros((TASK_TICKS, len(TARGETS)), dtype=np.float32)
    read_c = np.empty(
        (len(READ_TICKS), bank_count, width, len(TARGETS)), dtype=np.complex64
    )
    read_d = np.empty_like(read_c)
    read_scores = np.empty(
        (len(READ_TICKS), len(TARGETS), config.alphabet_size), dtype=np.float32
    )
    read_bank_scores = np.empty(
        (
            len(READ_TICKS),
            bank_count,
            len(TARGETS),
            config.alphabet_size,
        ),
        dtype=np.float32,
    )
    read_coherence = np.empty(
        (len(READ_TICKS), len(TARGETS)), dtype=np.float32
    )
    read_available = np.empty(
        (len(READ_TICKS), len(TARGETS)), dtype=np.bool_
    )
    read_predictions = np.empty(
        (len(READ_TICKS), len(TARGETS)), dtype=np.int64
    )
    read_index = {tick: index for index, tick in enumerate(READ_TICKS)}

    for tick in range(TASK_TICKS):
        task_state, receipt = controller._heartbeat_unchecked(task_state)
        input_clamps = 0
        if tick == 0:
            store_coordinates(arrays, f"{key}_target_pre", task_state, mode_count)
            task_state, drift, input_clamps = controller._modulate_unchecked(
                task_state, target_tensor, 1.0
            )
            store_coordinates(arrays, f"{key}_target_post", task_state, mode_count)
            task_drift[tick] = cpu(drift)
        elif tick == 8:
            store_coordinates(arrays, f"{key}_distractor_pre", task_state, mode_count)
            task_state, drift, input_clamps = controller._modulate_unchecked(
                task_state, distractor_tensor, 1.0
            )
            store_coordinates(arrays, f"{key}_distractor_post", task_state, mode_count)
            task_drift[tick] = cpu(drift)
        task_state, evolve_clamps = controller._evolve_unchecked(
            task_state, EVOLUTION_STEPS
        )
        task_energy[tick] = cpu(controller._dynamic_energy_unchecked(task_state))
        task_hamiltonian[tick] = cpu(
            controller._hamiltonian_unchecked(task_state)
        )
        task_injection[tick] = cpu(receipt.injected_energy)
        task_clamp[tick] = (
            receipt.clamp_count + input_clamps + evolve_clamps
        )
        if tick in read_index:
            index = read_index[tick]
            common, differential, _, _ = active_coordinates(task_state, mode_count)
            read_c[index] = cpu(common)
            read_d[index] = cpu(differential)
            readout = controller._white_readout_unchecked(task_state, None)
            read_scores[index] = cpu(readout.scores)
            read_bank_scores[index] = cpu(readout.bank_scores)
            read_coherence[index] = cpu(readout.white_coherence)
            read_available[index] = cpu(readout.available)
            read_predictions[index] = cpu(readout.symbols)

    arrays[f"{key}_task_read_c"] = read_c
    arrays[f"{key}_task_read_d"] = read_d
    arrays[f"{key}_task_read_scores"] = read_scores
    arrays[f"{key}_task_read_bank_scores"] = read_bank_scores
    arrays[f"{key}_task_read_coherence"] = read_coherence
    arrays[f"{key}_task_read_available"] = read_available
    arrays[f"{key}_task_read_predictions"] = read_predictions
    arrays[f"{key}_task_energy"] = task_energy
    arrays[f"{key}_task_hamiltonian"] = task_hamiltonian
    arrays[f"{key}_task_injection"] = task_injection
    arrays[f"{key}_task_clamp"] = task_clamp
    arrays[f"{key}_task_input_energy_drift"] = task_drift

    target_array = np.asarray(TARGETS, dtype=np.int64)
    distractor_array = np.asarray(DISTRACTORS, dtype=np.int64)
    tick8_index = READ_TICKS.index(8)
    long_indices = [READ_TICKS.index(tick) for tick in LONG_TICKS]
    target_ranks = np.stack(
        [ranks(read_scores[index], target_array) for index in range(len(READ_TICKS))]
    )
    distractor_ranks = np.stack(
        [
            ranks(read_scores[index], distractor_array)
            for index in range(len(READ_TICKS))
        ]
    )
    bank_target_ranks = np.empty(
        (len(READ_TICKS), bank_count, len(TARGETS)), dtype=np.int64
    )
    for read_slot in range(len(READ_TICKS)):
        for bank in range(bank_count):
            bank_target_ranks[read_slot, bank] = ranks(
                read_bank_scores[read_slot, bank], target_array
            )
    arrays[f"{key}_task_target_ranks"] = target_ranks
    arrays[f"{key}_task_distractor_ranks"] = distractor_ranks
    arrays[f"{key}_task_bank_target_ranks"] = bank_target_ranks

    long_white_mrr = float(
        np.mean(1.0 / target_ranks[long_indices].astype(np.float64))
    )
    bank_mrr = np.mean(
        1.0 / bank_target_ranks[long_indices].astype(np.float64), axis=(0, 2)
    )
    best_bank = int(np.argmax(bank_mrr))
    beating_index, fft_top = beating_metrics(beat_hamiltonian.astype(np.float64))
    total_warm_energy = float(warm_energy[-1].sum())
    all_clamps = int(
        first_receipt.clamp_count
        + warm_clamp.sum()
        + beat_clamp.sum()
        + task_clamp.sum()
    )
    maximum_leakage = float(
        max(
            np.max(np.abs(arrays[f"{key}_first_heartbeat_post_d"])),
            warm_leakage.max(),
            beat_leakage.max(),
        )
    )
    state_values = bank_count * 9 * mode_count
    active_values = bank_count * 8 * width
    batch_weighted_ticks = WARM_TICKS + BEATING_TICKS + TASK_TICKS * len(TARGETS)
    evolution_element_updates = (
        active_values * EVOLUTION_STEPS * batch_weighted_ticks
    )
    edge_complex_updates = (
        (bank_count - 1)
        * width
        * 2
        * 2
        * EVOLUTION_STEPS
        * batch_weighted_ticks
    )
    metrics: dict[str, Any] = {
        "zero_input_max_abs": float(np.max(np.abs(zero_post.field.detach().cpu().numpy()))),
        "first_heartbeat_relative_error": float(
            np.max(
                np.abs(cpu(first_receipt.source_energy_after) - config.heartbeat_target_energy)
                / config.heartbeat_target_energy
            )
        ),
        "heartbeat_only_max_abs_d": maximum_leakage,
        "maximum_input_energy_drift": float(
            max(np.max(np.abs(task_drift)), np.max(np.abs(cpu(zero_drift))))
        ),
        "clamp_count": all_clamps,
        "warm_final_bank_energy": [float(value) for value in warm_energy[-1]],
        "warm_final_root_fraction": float(warm_energy[-1, 0] / total_warm_energy),
        "warm_final_crown_fraction": float(warm_energy[-1, -1] / total_warm_energy),
        "beating_index": beating_index,
        "fft_top_non_dc": fft_top,
        "tick8_distractor_accuracy": float(
            np.mean(read_predictions[tick8_index] == distractor_array)
        ),
        "tick8_predictions": [int(value) for value in read_predictions[tick8_index]],
        "long_horizon_white_mrr": long_white_mrr,
        "best_bank_long_horizon_mrr": float(bank_mrr[best_bank]),
        "best_bank_index": best_bank,
        "bank_long_horizon_mrr": [float(value) for value in bank_mrr],
        "target_reciprocal_ranks": {
            str(tick): [
                float(value)
                for value in (1.0 / target_ranks[READ_TICKS.index(tick)])
            ]
            for tick in LONG_TICKS
        },
        "mean_white_coherence": float(read_coherence.mean()),
    }
    declaration_payload = {
        "bank_count": bank_count,
        "mode_count": mode_count,
        "active_width": width,
        "timescales": [float(value) for value in config.bank_timescales],
        "damping": [
            float(config.base_damping / value) for value in config.bank_timescales
        ],
        "fastest_timescale": float(config.bank_timescales[0]),
        "slowest_timescale": float(config.bank_timescales[-1]),
        "modal_profile_endpoints": [1.0, 1.25],
        "state_values_per_batch": state_values,
        "active_dynamic_values_per_batch": active_values,
        "logical_ticks": WARM_TICKS + BEATING_TICKS + TASK_TICKS,
        "batch_weighted_evolution_ticks": batch_weighted_ticks,
        "evolution_steps_per_tick": EVOLUTION_STEPS,
        "evolution_element_updates": evolution_element_updates,
        "edge_complex_endpoint_updates": edge_complex_updates,
        "config": config.to_dict(),
        "config_fingerprint": controller.config_fingerprint,
        "codebook_fingerprint": controller.codebook_fingerprint,
        "trace_prefix": key,
    }
    return {
        "declaration": declaration_payload,
        "metrics": metrics,
    }, arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    device = torch.device(args.device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise L29RunnerError("canonical L29 requires an available CUDA/ROCm device")
    output_dir = args.output_dir.resolve()
    board_path = output_dir / BOARD_NAME
    trace_path = output_dir / TRACE_NAME
    if board_path.exists():
        try:
            prior = json.loads(board_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prior = None
        if isinstance(prior, dict) and prior.get("status") == "COMPLETE":
            raise L29RunnerError("a COMPLETE canonical L29 board already exists")
    missing_sources = [str(path) for path in SOURCE_PATHS if not path.is_file()]
    if missing_sources:
        raise L29RunnerError(f"canonical source files are missing: {missing_sources!r}")

    source_hashes = {
        path.relative_to(ROOT).as_posix(): sha256_file(path) for path in SOURCE_PATHS
    }
    declarations = arm_declarations()
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA,
        "status": "INCOMPLETE",
        "layout_profile_id": PRISMATIC_LAYOUT_PROFILE_ID,
        "operator_profile_id": PRISMATIC_OPERATOR_PROFILE_ID,
        "trace_schema_id": TRACE_SCHEMA,
        "preregistration_sha256": source_hashes[
            PREREGISTRATION.relative_to(ROOT).as_posix()
        ],
        "source_sha256": source_hashes,
        "device": {
            "requested": str(device),
            "type": device.type,
            "name": torch.cuda.get_device_name(device),
            "torch_version": torch.__version__,
            "hip_version": torch.version.hip,
            "dtype": "torch.float32",
        },
        "constants": {
            "phi": PHI,
            "targets": list(TARGETS),
            "distractors": list(DISTRACTORS),
            "read_ticks": list(READ_TICKS),
            "long_horizon_ticks": list(LONG_TICKS),
            "warm_ticks": WARM_TICKS,
            "beating_ticks": BEATING_TICKS,
            "task_ticks": TASK_TICKS,
            "evolution_steps": EVOLUTION_STEPS,
            "alphabet_size": 260,
            "heartbeat_target_energy": 1.0,
            "readout_energy_floor": 1.0e-8,
            "batch_weighted_budget_formula": "warm + beating + task * target_count",
            "element_update_formula": "active_dynamic_values * evolution_steps * batch_weighted_ticks",
            "edge_update_formula": "edges * active_width * common_and_differential * endpoints * evolution_steps * batch_weighted_ticks",
        },
        "trace": {"path": TRACE_NAME, "sha256": None},
        "arms": {},
    }
    atomic_json(board_path, board)

    arrays: dict[str, np.ndarray] = {
        "schema_id": np.asarray(TRACE_SCHEMA),
        "targets": np.asarray(TARGETS, dtype=np.int64),
        "distractors": np.asarray(DISTRACTORS, dtype=np.int64),
        "read_ticks": np.asarray(READ_TICKS, dtype=np.int64),
        "long_horizon_ticks": np.asarray(LONG_TICKS, dtype=np.int64),
    }
    try:
        for slug, declaration in declarations.items():
            torch.cuda.synchronize(device)
            torch.cuda.reset_peak_memory_stats(device)
            started = time.perf_counter()
            result, arm_arrays = run_arm(slug, declaration, device)
            torch.cuda.synchronize(device)
            result["resources"] = {
                "wall_seconds": float(time.perf_counter() - started),
                "peak_allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
            }
            board["arms"][slug] = result
            arrays.update(arm_arrays)
            atomic_json(board_path, board)
            print(
                f"{slug}: tick8={result['metrics']['tick8_distractor_accuracy']:.3f} "
                f"long_mrr={result['metrics']['long_horizon_white_mrr']:.6f} "
                f"beat={result['metrics']['beating_index']:.6f}"
            )
        atomic_npz(trace_path, arrays)
        board["trace"] = {
            "path": TRACE_NAME,
            "sha256": sha256_file(trace_path),
            "array_count": len(arrays),
        }
        board["status"] = "COMPLETE"
        atomic_json(board_path, board)
    except Exception as exc:
        board["status"] = "INCOMPLETE"
        board["error"] = f"{type(exc).__name__}: {exc}"
        atomic_json(board_path, board)
        raise

    print(board_path)
    print(trace_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
