"""Run the frozen L30 white-chromatic field board."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_qi_field import QiFieldState
from cassi_white_chromatic_field import (
    WHITE_CHROMATIC_LAYOUT_PROFILE_ID,
    WHITE_CHROMATIC_OPERATOR_PROFILE_ID,
    WHITE_CHROMATIC_PROJECTION_PROFILE_ID,
    PsychedelicProjection,
    WhiteChromaticFieldConfig,
    WhiteChromaticFieldController,
)

BOARD_SCHEMA = "cassi.l30.white-chromatic-board.v1"
TRACE_SCHEMA = "cassi.l30.white-chromatic-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L30-WHITE-CHROMATIC-FIELD-PREREG.md"
MODULE = ROOT / "cassi_white_chromatic_field.py"
RUNNER = ROOT / "verification" / "run_l30_white_chromatic_field.py"
VERIFIER = ROOT / "verification" / "verify_l30_white_chromatic_field.py"
OUTPUT_DIR = ROOT / "_diag" / "l30-white-chromatic-field"
BOARD_NAME = "l30-board.json"
TRACE_NAME = "l30-traces.npz"
PNG_NAME = "l30-projection.png"
TARGETS = (0, 37, 74, 111, 148, 185, 222, 259)
DISTRACTORS = tuple((x + 97) % 260 for x in TARGETS)
READ_TICKS = (0, 1, 2, 4, 8, 16, 32, 64)
LONG_TICKS = (16, 32, 64)
PRE_TICKS = (1, 2, 4)
MODE_COUNT = 2048
ACTIVE_WIDTH = MODE_COUNT // 2
CHANNELS = 7
BATCH_SIZE = 8
ALPHABET_SIZE = 260
TASK_TICKS = 65
LONG_TICKS_COUNT = 128
EVOLUTION_STEPS = 8
PHI = (1.0 + math.sqrt(5.0)) / 2.0


class L30RunnerError(RuntimeError):
    """The canonical L30 board could not be completed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def atomic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            savez: Any = np.savez
            savez(handle, **arrays)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def cpu(value: Any) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().numpy()
    return np.asarray(value)


def state_of(value: Any) -> QiFieldState:
    if isinstance(value, QiFieldState):
        return value
    if isinstance(value, tuple) and value and isinstance(value[0], QiFieldState):
        return value[0]
    candidate = getattr(value, "state", None)
    if isinstance(candidate, QiFieldState):
        return candidate
    raise L30RunnerError(f"controller returned no QiFieldState ({type(value).__name__})")


def tick_receipt(value: Any) -> Any:
    return value[1] if isinstance(value, tuple) and len(value) > 1 else value


def heartbeat_receipt(value: Any) -> Any:
    if isinstance(value, tuple) and len(value) > 1:
        return value[1]
    return getattr(value, "heartbeat", value)

def attr(value: Any, name: str, default: Any = None) -> Any:
    return getattr(value, name, default)




def coordinates(state: QiFieldState, mode_count: int = MODE_COUNT) -> tuple[torch.Tensor, ...]:
    parts = state.field.reshape(CHANNELS, 9, mode_count, state.field.shape[2])
    width = mode_count // 2
    y = torch.complex(parts[:, 0, :width], parts[:, 1, :width])
    yin = torch.complex(parts[:, 2, :width], parts[:, 3, :width])
    vy = torch.complex(parts[:, 4, :width], parts[:, 5, :width])
    vi = torch.complex(parts[:, 6, :width], parts[:, 7, :width])
    return PHI * y + yin, y - PHI * yin, PHI * vy + vi, vy - PHI * vi


def store_coordinates(arrays: dict[str, np.ndarray], prefix: str, state: QiFieldState) -> None:
    common, differential, common_velocity, differential_velocity = coordinates(state)
    arrays[f"{prefix}_c"] = cpu(common)
    arrays[f"{prefix}_d"] = cpu(differential)
    arrays[f"{prefix}_vc"] = cpu(common_velocity)
    arrays[f"{prefix}_vd"] = cpu(differential_velocity)
def store_field(arrays: dict[str, np.ndarray], prefix: str, state: QiFieldState) -> None:
    arrays[f"{prefix}_field"] = cpu(state.field)
def clone_batch(state: QiFieldState, batch_size: int) -> QiFieldState:
    if state.field.shape[2] == batch_size:
        return state.clone()
    return QiFieldState(state.field.expand(-1, -1, batch_size).clone())

def energy_array(controller: Any, state: QiFieldState) -> np.ndarray:
    return cpu(controller.dynamic_energy(state))


def channel_energy(state: QiFieldState, receipt: Any = None) -> np.ndarray:
    value = receipt_value(receipt, "bank_energy", None) if receipt is not None else None
    if value is not None:
        return np.asarray(cpu(value))
    packed = state.field.reshape(CHANNELS, 9, MODE_COUNT, state.field.shape[2])
    return cpu(packed[:, :8, :ACTIVE_WIDTH].square().sum(dim=1).mean(dim=1))


def call_modulate(controller: Any, state: QiFieldState, symbols: torch.Tensor) -> tuple[QiFieldState, torch.Tensor, int]:
    before = energy_array(controller, state)
    result = controller.modulate_symbols(state, symbols, trust=1.0)
    out = state_of(result)
    drift = cpu(result[1]) if isinstance(result, tuple) and len(result) > 1 else energy_array(controller, out) - before
    clamps = int(result[2]) if isinstance(result, tuple) and len(result) > 2 else int(getattr(result, "clamp_count", 0))
    return out, torch.as_tensor(drift, device=state.field.device, dtype=state.field.dtype), clamps


def call_evolve(controller: Any, state: QiFieldState) -> tuple[QiFieldState, int]:
    result = controller.evolve(state, steps=EVOLUTION_STEPS)
    out = state_of(result)
    clamps = int(result[1]) if isinstance(result, tuple) and len(result) > 1 and isinstance(result[1], (int, np.integer)) else int(getattr(result, "clamp_count", 0))
    return out, clamps


def receipt_value(receipt: Any, name: str, fallback: Any) -> Any:
    value = getattr(receipt, name, None)
    return fallback if value is None else value


def capture_heartbeat(arrays: dict[str, np.ndarray], prefix: str, receipt: Any) -> None:
    for name in ("source_weights", "source_energy_before", "source_energy_after", "total_energy_before", "total_energy_after", "injected_energy", "dissipated_energy"):
        value = getattr(receipt, name, None)
        if value is not None:
            arrays[f"{prefix}_{name}"] = cpu(value)
    arrays[f"{prefix}_clamp_count"] = np.asarray(int(receipt_value(receipt, "clamp_count", 0)), dtype=np.int64)


def readout_arrays(arrays: dict[str, np.ndarray], prefix: str, readout: Any) -> None:
    for name in ("bank_scores", "scores", "symbols", "available", "contributions", "differential_rms", "bank_energy", "active_bank_count", "white_coherence"):
        value = getattr(readout, name, None)
        if value is not None:
            arrays[f"{prefix}_{name}"] = cpu(value)


def projection_arrays(arrays: dict[str, np.ndarray], prefix: str, projection: PsychedelicProjection) -> None:
    for name in ("rgb", "common_intensity", "channel_intensity", "side"):
        value = getattr(projection, name)
        arrays[f"{prefix}_{name}"] = cpu(value) if name != "side" else np.asarray(int(value), dtype=np.int64)


def ranks(scores: np.ndarray, symbols: np.ndarray) -> np.ndarray:
    chosen = np.take_along_axis(scores, symbols[..., None], axis=-1)[..., 0]
    ids = np.arange(scores.shape[-1], dtype=np.int64)
    return (1 + (scores > chosen[..., None]).sum(axis=-1) + ((scores == chosen[..., None]) & (ids < symbols[..., None])).sum(axis=-1)).astype(np.int64)


def run_board(device: torch.device, dtype: torch.dtype) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    config = WhiteChromaticFieldConfig(mode_count=MODE_COUNT)
    controller = WhiteChromaticFieldController(config)
    arrays: dict[str, np.ndarray] = {
        "schema_id": np.asarray(TRACE_SCHEMA),
        "targets": np.asarray(TARGETS, dtype=np.int64),
        "distractors": np.asarray(DISTRACTORS, dtype=np.int64),
        "read_ticks": np.asarray(READ_TICKS, dtype=np.int64),
    }
    target_tensor = torch.tensor(TARGETS, device=device, dtype=torch.int64)
    distractor_tensor = torch.tensor(DISTRACTORS, device=device, dtype=torch.int64)

    zero = controller.new_state(device=device, dtype=dtype)
    store_coordinates(arrays, "zero_pre", zero)
    zero_post, zero_drift, zero_clamp = call_modulate(controller, zero.clone(), target_tensor[:1])
    store_coordinates(arrays, "zero_post", zero_post)
    store_field(arrays, "zero_post", zero_post)
    arrays["zero_drift"] = cpu(zero_drift)
    arrays["zero_clamp_count"] = np.asarray(zero_clamp, dtype=np.int64)

    first = controller.new_state(device=device, dtype=dtype)
    store_coordinates(arrays, "first_heartbeat_pre", first)
    store_field(arrays, "first_heartbeat_pre", first)
    first_result = controller.heartbeat(first)
    first_state, first_receipt = state_of(first_result), heartbeat_receipt(first_result)
    store_coordinates(arrays, "first_heartbeat_post", first_state)
    store_field(arrays, "first_heartbeat_post", first_state)
    capture_heartbeat(arrays, "first_heartbeat", first_receipt)
    arrays["first_heartbeat_dynamic_energy"] = channel_energy(first_state, first_receipt)
    arrays["first_heartbeat_carrier_energy"] = cpu(controller.carrier_energy(first_state))
    codebook = controller.codebook(0, device=device, dtype=dtype)
    arrays["codebook"] = cpu(codebook)

    pre = controller.new_state(device=device, dtype=dtype)
    pre_result = controller.heartbeat(pre)
    pre_state, pre_heartbeat = clone_batch(state_of(pre_result), BATCH_SIZE), heartbeat_receipt(pre_result)
    pre_state, pre_drift, pre_clamp = call_modulate(controller, pre_state, target_tensor)
    store_field(arrays, "pre_target", pre_state)
    store_coordinates(arrays, "pre_target", pre_state)
    arrays["pre_target_drift"] = cpu(pre_drift)
    arrays["pre_target_clamp_count"] = np.asarray(pre_clamp, dtype=np.int64)
    readout_state_before = pre_state.field.clone()
    pre_readout = controller.white_readout(pre_state)
    arrays["pre_readout_state_before_field"] = cpu(readout_state_before)
    arrays["pre_readout_state_after_field"] = cpu(pre_state.field)
    readout_arrays(arrays, "pre_readout", pre_readout)
    arrays["pre_heartbeat_total_energy_after"] = cpu(receipt_value(pre_heartbeat, "total_energy_after", energy_array(controller, pre_state)))

    # Public tick board.
    task_state = clone_batch(controller.new_state(device=device, dtype=dtype), BATCH_SIZE)
    task_energy = np.empty((TASK_TICKS, CHANNELS, BATCH_SIZE), dtype=np.float32)
    task_carrier = np.empty((TASK_TICKS, BATCH_SIZE), dtype=np.float32)
    task_drift = np.zeros((TASK_TICKS, BATCH_SIZE), dtype=np.float32)
    task_clamp = np.zeros(TASK_TICKS, dtype=np.int64)
    task_hamiltonian = np.zeros((TASK_TICKS, BATCH_SIZE), dtype=np.float32)
    task_read_d = np.empty((len(READ_TICKS), CHANNELS, ACTIVE_WIDTH, BATCH_SIZE), dtype=np.complex64)
    task_read_c = np.empty_like(task_read_d)
    task_read_scores = np.empty((len(READ_TICKS), BATCH_SIZE, ALPHABET_SIZE), dtype=np.float32)
    task_read_bank_scores = np.empty((len(READ_TICKS), CHANNELS, BATCH_SIZE, ALPHABET_SIZE), dtype=np.float32)
    task_read_symbols = np.empty((len(READ_TICKS), BATCH_SIZE), dtype=np.int64)
    task_read_available = np.zeros((len(READ_TICKS), BATCH_SIZE), dtype=np.bool_)
    task_read_coherence = np.zeros((len(READ_TICKS), BATCH_SIZE), dtype=np.float32)
    task_read_differential_rms = np.zeros((len(READ_TICKS), CHANNELS, BATCH_SIZE), dtype=np.float32)
    projection_state = None
    read_index = {tick: index for index, tick in enumerate(READ_TICKS)}
    for tick in range(TASK_TICKS):
        symbols = target_tensor if tick == 0 else distractor_tensor if tick == 8 else None
        result = controller.tick(task_state, symbols=symbols, trust=1.0)
        task_state, tick_record = state_of(result), tick_receipt(result)
        drift = receipt_value(tick_record, "input_energy_drift", np.zeros(BATCH_SIZE, dtype=np.float32))
        task_drift[tick] = cpu(drift).reshape(-1)
        task_energy[tick] = channel_energy(task_state, tick_record).astype(np.float32)
        task_carrier[tick] = cpu(controller.carrier_energy(task_state)).reshape(-1)
        task_clamp[tick] = int(receipt_value(tick_record, "clamp_count", 0))
        hamiltonian = receipt_value(tick_record, "hamiltonian", None)
        if hamiltonian is not None:
            task_hamiltonian[tick] = cpu(hamiltonian).reshape(-1)
        if tick in read_index:
            slot = read_index[tick]
            common, differential, _, _ = coordinates(task_state)
            task_read_c[slot] = cpu(common)
            if tick == 8:
                projection_state = task_state.clone()
            task_read_d[slot] = cpu(differential)
            ro = receipt_value(tick_record, "readout", None) or controller.white_readout(task_state)
            readout_arrays(arrays, f"task_read_{tick}", ro)
            task_read_scores[slot] = cpu(ro.scores).T if cpu(ro.scores).shape == (ALPHABET_SIZE, BATCH_SIZE) else cpu(ro.scores)
            bs = cpu(ro.bank_scores)
            task_read_bank_scores[slot] = bs.transpose(0, 2, 1) if bs.shape == (CHANNELS, ALPHABET_SIZE, BATCH_SIZE) else bs
            sy = cpu(ro.symbols).reshape(-1)
            task_read_symbols[slot] = sy
            task_read_available[slot] = cpu(ro.available).reshape(-1)
            task_read_coherence[slot] = cpu(ro.white_coherence).reshape(-1)
            rms = cpu(ro.differential_rms)
            task_read_differential_rms[slot] = rms if rms.shape == (CHANNELS, BATCH_SIZE) else rms.T
    arrays.update({
        "task_read_c": task_read_c, "task_read_d": task_read_d,
        "task_read_scores": task_read_scores, "task_read_bank_scores": task_read_bank_scores,
        "task_read_symbols": task_read_symbols, "task_read_available": task_read_available,
        "task_read_coherence": task_read_coherence, "task_read_differential_rms": task_read_differential_rms,
        "task_energy": task_energy, "task_carrier_energy": task_carrier,
        "task_input_energy_drift": task_drift, "task_clamp_count": task_clamp,
        "task_hamiltonian": task_hamiltonian,
    })
    target_array = np.asarray(TARGETS, dtype=np.int64)
    distractor_array = np.asarray(DISTRACTORS, dtype=np.int64)
    target_ranks = np.stack([ranks(task_read_scores[i], target_array) for i in range(len(READ_TICKS))])
    distractor_ranks = np.stack([ranks(task_read_scores[i], distractor_array) for i in range(len(READ_TICKS))])
    arrays["task_target_ranks"] = target_ranks
    arrays["task_distractor_ranks"] = distractor_ranks

    def long_path(cyclic: bool, prefix: str) -> tuple[QiFieldState, int]:
        state = controller.new_state(device=device, dtype=dtype)
        energies = np.empty((LONG_TICKS_COUNT, CHANNELS), dtype=np.float32)
        carriers = np.empty(LONG_TICKS_COUNT, dtype=np.float32)
        max_d = np.empty(LONG_TICKS_COUNT, dtype=np.float32)
        clamps = np.empty(LONG_TICKS_COUNT, dtype=np.int64)
        for tick in range(LONG_TICKS_COUNT):
            symbols = torch.tensor((TARGETS[tick % len(TARGETS)],), device=device, dtype=torch.int64) if cyclic else None
            result = controller.tick(state, symbols=symbols, trust=1.0)
            state, receipt = state_of(result), tick_receipt(result)
            energies[tick] = channel_energy(state, receipt).reshape(CHANNELS, -1)[:, 0]
            carriers[tick] = cpu(controller.carrier_energy(state)).reshape(-1)[0]
            max_d[tick] = float(torch.abs(coordinates(state)[1]).max().item())
            clamps[tick] = int(receipt_value(receipt, "clamp_count", 0))
        arrays[f"{prefix}_energy"] = energies
        arrays[f"{prefix}_carrier_energy"] = carriers
        arrays[f"{prefix}_max_abs_d"] = max_d
        arrays[f"{prefix}_clamp_count"] = clamps
        store_field(arrays, f"{prefix}_final", state)
        return state, int(clamps.sum())

    _, blank_clamps = long_path(False, "blank")
    _, stress_clamps = long_path(True, "stress")
    store_field(arrays, "counter_projection_state", pre_state)

    if projection_state is None:
        raise L30RunnerError("tick-8 projection state was not captured")
    arrays["projection_state_before_field"] = cpu(projection_state.field.clone())
    projection = controller.psychedelic_projection(projection_state, max_side=32)
    arrays["projection_state_after_first_field"] = cpu(projection_state.field)
    projection_again = controller.psychedelic_projection(projection_state, max_side=32)
    arrays["projection_state_after_second_field"] = cpu(projection_state.field)
    counter_projection = controller.psychedelic_projection(pre_state, max_side=32)
    projection_arrays(arrays, "projection", projection)
    projection_arrays(arrays, "projection_again", projection_again)
    projection_arrays(arrays, "counter_projection", counter_projection)

    first_energy = energy_array(controller, first_state)
    first_total = float(np.mean(first_energy))
    first_channel_spread = float(np.ptp(first_energy, axis=0).max() / max(float(np.mean(first_energy)), 1e-12)) if first_energy.ndim > 1 else 0.0
    metrics = {
        "first_heartbeat_carrier_energy": float(np.mean(arrays.get("first_heartbeat_carrier_energy", [0.0]))),
        "zero_input_max_abs": float(np.max(np.abs(arrays["zero_post_field"])) if arrays["zero_post_field"].size else 0.0),
        "first_heartbeat_total_energy": first_total,
        "first_heartbeat_channel_energy_spread": first_channel_spread,
        "first_heartbeat_max_abs_d": float(np.max(np.abs(arrays["first_heartbeat_post_d"]))),
        "maximum_input_energy_drift": float(max(np.max(np.abs(task_drift)), np.max(np.abs(arrays["zero_drift"])), np.max(np.abs(arrays["pre_target_drift"])))),
        "clamp_count": int(task_clamp.sum() + blank_clamps + stress_clamps + zero_clamp + pre_clamp),
        "maximum_total_mean_dynamic_energy": float(max(np.mean(task_energy, axis=1).max(), blank_energy_sum(arrays), stress_energy_sum(arrays))),
        "exact_pre_target_accuracy": float(np.mean(cpu(pre_readout.symbols).reshape(-1) == target_array)),
        "tick0_target_accuracy": float(np.mean(task_read_symbols[0] == target_array)),
        "tick8_distractor_accuracy": float(np.mean(task_read_symbols[4] == distractor_array)),
        "blank_max_abs_d": float(np.max(arrays["blank_max_abs_d"])),
        "stress_max_abs_d": float(np.max(arrays["stress_max_abs_d"])),
        "stress_clamp_count": int(stress_clamps),
    }
    metrics["target_mrr_pre_distractor"] = float(np.mean(1.0 / target_ranks[[READ_TICKS.index(x) for x in PRE_TICKS]]))
    metrics["distractor_mrr_long"] = float(np.mean(1.0 / distractor_ranks[[READ_TICKS.index(x) for x in LONG_TICKS]]))
    metrics["original_target_mrr_long"] = float(np.mean(1.0 / target_ranks[[READ_TICKS.index(x) for x in LONG_TICKS]]))
    metrics["tick0_white_coherence"] = float(np.mean(task_read_coherence[0]))
    metrics["projection_rgb_std"] = float(np.std(arrays["projection_rgb"]))
    metrics["projection_target_rms"] = float(np.sqrt(np.mean((arrays["projection_rgb"] - arrays["counter_projection_rgb"]) ** 2)))
    declaration = {
        "channels": CHANNELS, "mode_count": MODE_COUNT, "active_modes": ACTIVE_WIDTH,
        "alphabet_size": ALPHABET_SIZE, "batch_size": BATCH_SIZE,
        "evolution_steps_per_tick": EVOLUTION_STEPS, "targets": list(TARGETS),
        "distractors": list(DISTRACTORS), "read_ticks": list(READ_TICKS),
        "config": config.to_dict() if hasattr(config, "to_dict") else dict(config.__dict__),
        "config_fingerprint": getattr(controller, "config_fingerprint", ""),
        "codebook_fingerprint": getattr(controller, "codebook_fingerprint", ""),
        "trace_prefix": "task",
    }
    return {"declaration": declaration, "metrics": metrics}, arrays

def blank_energy_sum(arrays: dict[str, np.ndarray]) -> float:
    return float(np.mean(arrays["blank_energy"], axis=1).max())


def stress_energy_sum(arrays: dict[str, np.ndarray]) -> float:
    return float(np.mean(arrays["stress_energy"], axis=1).max())


def write_projection_png(path: Path, rgb: np.ndarray) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        image = np.asarray(rgb, dtype=np.float32)
        if image.ndim == 4:
            image = np.transpose(image[0], (1, 2, 0))
        elif image.ndim == 3 and image.shape[0] == 3:
            image = np.transpose(image, (1, 2, 0))
        plt.imsave(temporary, image, vmin=0.0, vmax=1.0, format="png")
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="float32", choices=("float32", "float64"))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    device = torch.device(args.device)
    dtype = torch.float64 if args.dtype == "float64" else torch.float32
    output_dir = args.output_dir.resolve()
    board_path, trace_path, png_path = output_dir / BOARD_NAME, output_dir / TRACE_NAME, output_dir / PNG_NAME
    source_paths = (PREREGISTRATION, MODULE, RUNNER, VERIFIER)
    missing = [str(p) for p in source_paths if not p.is_file()]
    if missing:
        raise L30RunnerError(f"missing bound source files: {missing!r}")
    hashes = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in source_paths}
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA, "status": "INCOMPLETE",
        "layout_profile_id": WHITE_CHROMATIC_LAYOUT_PROFILE_ID,
        "operator_profile_id": WHITE_CHROMATIC_OPERATOR_PROFILE_ID,
        "projection_profile_id": WHITE_CHROMATIC_PROJECTION_PROFILE_ID,
        "trace_schema_id": TRACE_SCHEMA,
        "preregistration_sha256": hashes[PREREGISTRATION.relative_to(ROOT).as_posix()],
        "source_sha256": hashes,
        "device": {"requested": str(device), "type": device.type, "name": torch.cuda.get_device_name(device) if device.type == "cuda" and torch.cuda.is_available() else str(device), "torch_version": torch.__version__, "hip_version": torch.version.hip, "dtype": args.dtype},
        "constants": {"phi": PHI, "channels": CHANNELS, "mode_count": MODE_COUNT, "active_modes": ACTIVE_WIDTH, "alphabet_size": ALPHABET_SIZE, "batch_size": BATCH_SIZE, "targets": list(TARGETS), "distractors": list(DISTRACTORS), "read_ticks": list(READ_TICKS), "long_horizon_ticks": list(LONG_TICKS), "pre_distractor_ticks": list(PRE_TICKS), "task_ticks": TASK_TICKS, "long_ticks": LONG_TICKS_COUNT, "evolution_steps": EVOLUTION_STEPS, "heartbeat_carrier_energy": 0.5, "field_energy_budget": 1.0, "readout_energy_floor": 1e-8},
        "trace": {"path": TRACE_NAME, "sha256": None}, "projection": {"path": PNG_NAME, "sha256": None}, "arms": {},
    }
    atomic_json(board_path, board)
    try:
        started = time.perf_counter()
        result, arrays = run_board(device, dtype)
        atomic_npz(trace_path, arrays)
        write_projection_png(png_path, arrays["projection_rgb"])
        board["arms"]["canonical"] = result
        board["trace"] = {"path": TRACE_NAME, "sha256": sha256_file(trace_path), "array_count": len(arrays)}
        board["projection"] = {"path": PNG_NAME, "sha256": sha256_file(png_path)}
        board["resources"] = {"wall_seconds": float(time.perf_counter() - started), "peak_allocated_bytes": int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" and torch.cuda.is_available() else 0}
        board["status"] = "COMPLETE"
        atomic_json(board_path, board)
    except Exception as exc:
        board["status"] = "INCOMPLETE"
        board["error"] = f"{type(exc).__name__}: {exc}"
        atomic_json(board_path, board)
        raise
    print(board_path)
    print(trace_path)
    print(png_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
