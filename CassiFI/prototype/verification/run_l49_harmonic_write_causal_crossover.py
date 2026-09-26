"""Run the frozen L49 harmonic-write causal crossover board."""
from __future__ import annotations

import argparse
import hashlib
import io
import math
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.run_l30_white_chromatic_field as l30
from cassi_harmonic_age_field import (
    HARMONIC_AGE_LAYOUT_PROFILE_ID,
    HARMONIC_AGE_OPERATOR_PROFILE_ID,
    HARMONIC_AGE_PROJECTION_PROFILE_ID,
    HarmonicAgeFieldConfig,
    HarmonicAgeFieldController,
)
from cassi_ordered_relational_field import (
    ORDERED_RELATIONAL_LAYOUT_PROFILE_ID,
    ORDERED_RELATIONAL_OPERATOR_PROFILE_ID,
    ORDERED_RELATIONAL_PROJECTION_PROFILE_ID,
    OrderedRelationalChromaticFieldConfig,
    OrderedRelationalChromaticFieldController,
)
from cassi_qi_field import QiFieldState
from cassi_white_chromatic_field import WhiteChromaticFieldController

BOARD_SCHEMA = "cassi.l49.harmonic-write-causal-crossover-board.v1"
TRACE_SCHEMA = "cassi.l49.harmonic-write-causal-crossover-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L49-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md"
RUNNER = ROOT / "verification" / "run_l49_harmonic_write_causal_crossover.py"
VERIFIER = ROOT / "verification" / "verify_l49_harmonic_write_causal_crossover.py"
OUTPUT_DIR = ROOT / "_diag" / "l49-harmonic-write-causal-crossover"
BOARD_NAME = "l49-board.json"
TRACE_NAME = "l49-traces.npz"
MODE_COUNT = 2048
ACTIVE_WIDTH = MODE_COUNT // 2
CHANNELS = 7
BATCH_SIZE = 8
ALPHABET_SIZE = 260
EVOLUTION_STEPS = 8
READOUT_FLOOR = 1.0e-8
MAX_MODE_AMPLITUDE = 8.0
MAX_EPSILON = 4096.0
S0 = np.asarray((0, 37, 74, 111, 148, 185, 222, 259), dtype=np.int64)
S1 = (S0 + 97) % ALPHABET_SIZE
S2 = (S0 + 181) % ALPHABET_SIZE
S3 = S1.copy()
STAGES = np.stack((S0, S1, S2, S3))
BRANCH_NAMES = ("I", "U", "W", "UW")
BRANCH_CHECKPOINT_NAMES = ("immediate", "tick-8", "tick-16", "tick-128")
SEQUENCE_CHECKPOINT_NAMES = (
    "s1-deposit", "s1-horizon", "s2-deposit", "s2-horizon",
    "s3-reversal-deposit", "s3-reversal-horizon",
)
PREFIX_FIELD_HASHES = (
    "e8370b2ebbe4d3afb155cf2a5fd3d866462f8d7b7481806536ef103c30c8a15c",
    "493a231a6606a7530b959880646b34e9142c9bdf577057e940211b33974ae1f2",
)
L40_BOARD_SHA256 = "44a0baff773c85405c35e0d92da405e8157e3617b811da75f6d2f00e88811530"
L40_TRACE_SHA256 = "21549f5bd65fd6e10247295bf59b48d6b35ed1b4d1b1a0a857fffafce32f045a"
L40_VERIFICATION_SHA256 = "b5fd0f085e876eebd589dc7cf8a6353d20b93e1616c014f13d77c11a8aca8ca7"
L40_BOARD = ROOT / "_diag" / "l40-rolling-ordered-relational-recall" / "l40-rolling-board.json"
L40_TRACE = ROOT / "_diag" / "l40-rolling-ordered-relational-recall" / "l40-rolling-traces.npz"
L40_VERIFICATION = ROOT / "artifacts" / "l40-rolling-ordered-relational-recall" / "l40-rolling-verification.json"
SOURCE_PATHS = (
    PREREGISTRATION,
    ROOT / "cassi_qi_profile.py",
    ROOT / "cassi_qi_field.py",
    ROOT / "cassi_prismatic_field.py",
    ROOT / "cassi_white_chromatic_field.py",
    ROOT / "cassi_cyclic_chromatic_field.py",
    ROOT / "cassi_relational_chromatic_field.py",
    ROOT / "cassi_ordered_relational_field.py",
    ROOT / "cassi_harmonic_age_field.py",
    ROOT / "verification" / "run_l30_white_chromatic_field.py",
    ROOT / "verification" / "verify_l30_white_chromatic_field.py",
    ROOT / "verification" / "run_l40_rolling_ordered_relational_recall.py",
    ROOT / "verification" / "verify_l40_rolling_ordered_relational_recall.py",
    ROOT / "designs" / "L46-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md",
    ROOT / "designs" / "L48-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md",
    ROOT / "tests" / "test_l49_harmonic_write_causal_crossover.py",
    RUNNER,
    VERIFIER,
)


class L49RunnerError(RuntimeError):
    """The canonical L49 board could not be completed."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tensor_sha256(value: Any) -> str:
    array = np.ascontiguousarray(l30.cpu(value))
    return _sha256_bytes(array.tobytes(order="C"))


def atomic_json(path: Path, value: Any) -> None:
    l30.atomic_json(path, value)


def atomic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    l30.atomic_npz(path, arrays)


def _state(value: Any) -> QiFieldState:
    if isinstance(value, QiFieldState):
        return value
    if isinstance(value, tuple) and value and isinstance(value[0], QiFieldState):
        return value[0]
    raise L49RunnerError(f"expected QiFieldState, got {type(value).__name__}")


def _new_controllers(mode_count: int) -> tuple[OrderedRelationalChromaticFieldController, HarmonicAgeFieldController]:
    return (
        OrderedRelationalChromaticFieldController(OrderedRelationalChromaticFieldConfig(mode_count=mode_count)),
        HarmonicAgeFieldController(HarmonicAgeFieldConfig(mode_count=mode_count)),
    )


def bare_write(
    ordered_controller: OrderedRelationalChromaticFieldController,
    state: QiFieldState,
    symbols: torch.Tensor | Sequence[int],
) -> tuple[QiFieldState, torch.Tensor, int]:
    """Apply exactly the inherited WhiteChromatic bare Givens operator."""
    result = WhiteChromaticFieldController._modulate_unchecked(
        ordered_controller, state, symbols, 1.0
    )
    return _state(result), result[1], int(result[2])


def lift_then_bare_write(
    ordered_controller: OrderedRelationalChromaticFieldController,
    harmonic_controller: HarmonicAgeFieldController,
    state: QiFieldState,
    symbols: torch.Tensor | Sequence[int],
) -> tuple[QiFieldState, torch.Tensor, int]:
    """Apply one L42 lift and then the shared inherited bare write."""
    lifted = harmonic_controller.lift_harmonics(state)
    return bare_write(ordered_controller, lifted, symbols)


def frozen_style_state(
    device: torch.device, dtype: torch.dtype, mode_count: int = 520
) -> tuple[OrderedRelationalChromaticFieldController, HarmonicAgeFieldController, QiFieldState]:
    """Construct the focused-test state at the end of the frozen S0 prefix."""
    ordered, harmonic = _new_controllers(mode_count)
    state = ordered.new_state(batch_size=BATCH_SIZE, device=device, dtype=dtype)
    state, _ = ordered.heartbeat(state)
    state = ordered.tick(
        state, symbols=torch.as_tensor(S0, device=device, dtype=torch.int64),
        steps=EVOLUTION_STEPS, trust=1.0,
    ).state
    for _ in range(16):
        state = ordered.tick(state, steps=EVOLUTION_STEPS).state
    return ordered, harmonic, state


def _native(state: QiFieldState, controller: Any) -> tuple[torch.Tensor, ...]:
    return controller._active_coordinates(state)


def _harmonic_values(
    controller: HarmonicAgeFieldController, state: QiFieldState
) -> tuple[torch.Tensor, torch.Tensor]:
    _, differential, _, differential_velocity = _native(state, controller)
    phase = controller._constants(state)["channel_phase"]
    harmonics = torch.arange(CHANNELS, device=state.field.device, dtype=torch.int64)
    basis = phase.conj()[None, :].pow(harmonics[:, None]) / math.sqrt(CHANNELS)
    harmonic_d = torch.einsum("kj,jwb->kwb", basis, differential)
    harmonic_vd = torch.einsum("kj,jwb->kwb", basis, differential_velocity)
    return harmonic_d, harmonic_vd


def _harmonic_coefficients(
    controller: HarmonicAgeFieldController, state: QiFieldState, harmonic_d: torch.Tensor
) -> torch.Tensor:
    phase_parts = controller.codebook(0, device=state.field.device, dtype=state.field.dtype)
    codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
    age_indices = torch.as_tensor((1, 2, 3, 4, 5, 6, 0), device=state.field.device)
    collapsed = harmonic_d.index_select(0, age_indices)
    return torch.einsum("aw,hwb->hba", codebook.conj(), collapsed).div_(float(controller.config.wave_mode_count)).permute(1, 0, 2)


def _ordered_capture(ordered: Any, state: QiFieldState) -> dict[str, np.ndarray]:
    before = l30.cpu(state.field.clone())
    readout = ordered.white_readout(state)
    after = l30.cpu(state.field)
    return {
        "field": before,
        "post_field": after,
        "emitted": l30.cpu(readout.symbols).reshape(-1),
        "current_symbols": l30.cpu(readout.current_symbols).reshape(-1),
        "current_available": l30.cpu(readout.available).reshape(-1).astype(bool),
        "current_scores": l30.cpu(readout.current_scores).astype(np.float32),
        "relational_symbols": l30.cpu(readout.relational_symbols).reshape(-1),
        "relational_available": l30.cpu(readout.relational_available).reshape(-1).astype(bool),
        "relational_scores": l30.cpu(readout.relational_scores).astype(np.float32),
        "ordered_scores": l30.cpu(readout.scores).astype(np.float32),
    }


def _full_capture(
    ordered: Any, harmonic: HarmonicAgeFieldController, state: QiFieldState
) -> dict[str, np.ndarray]:
    result = _ordered_capture(ordered, state)
    harmonic_readout = harmonic.white_readout(state)
    result["post_field"] = l30.cpu(state.field)
    harmonic_d, harmonic_vd = _harmonic_values(harmonic, state)
    coefficients = _harmonic_coefficients(harmonic, state, harmonic_d)
    age_scores = coefficients.abs().square()
    age_symbols = torch.argmax(age_scores, dim=2)
    age_energies = harmonic_d.index_select(
        0,
        torch.as_tensor(
            (1, 2, 3, 4, 5, 6, 0),
            device=state.field.device,
            dtype=torch.int64,
        ),
    ).abs().square().mean(dim=1).transpose(0, 1)
    result.update({
        "harmonic_d": l30.cpu(harmonic_d),
        "harmonic_vd": l30.cpu(harmonic_vd),
        "coefficients": l30.cpu(coefficients),
        "age_scores": l30.cpu(age_scores),
        "age_energies": l30.cpu(age_energies),
        "age_symbols": l30.cpu(age_symbols),
        "age_available": l30.cpu(harmonic_readout.age_available).astype(bool),
    })
    current = np.stack(
        (result["age_symbols"][:, 0], result["age_symbols"][:, 1]), axis=1
    ).astype(np.int64)
    current[~result["age_available"][:, 0], 0] = -1
    current[~result["age_available"][:, 1], 1] = -1
    result["current_predecessor"] = current
    result["dynamic_energy"] = l30.cpu(
        ordered._dynamic_energy_unchecked(state)
    ).astype(np.float32)
    packed = result["field"].reshape(
        ordered.config.bank_count,
        9,
        ordered.config.mode_count,
        state.batch_size,
    )
    result["maximum_absolute_field"] = np.asarray(
        np.abs(packed[:, :8, : ordered.config.wave_mode_count]).max(),
        dtype=np.float32,
    )
    return result

def _serialize_state(controller: Any, state: QiFieldState) -> bytes:
    harmonic = isinstance(controller, HarmonicAgeFieldController)
    payload = {
        "field": state.field.detach().cpu(),
        "config": controller.config.to_dict(),
        "config_fingerprint": getattr(controller, "config_fingerprint", ""),
        "layout_profile_id": HARMONIC_AGE_LAYOUT_PROFILE_ID if harmonic else ORDERED_RELATIONAL_LAYOUT_PROFILE_ID,
        "operator_profile_id": HARMONIC_AGE_OPERATOR_PROFILE_ID if harmonic else ORDERED_RELATIONAL_OPERATOR_PROFILE_ID,
        "projection_profile_id": HARMONIC_AGE_PROJECTION_PROFILE_ID if harmonic else ORDERED_RELATIONAL_PROJECTION_PROFILE_ID,
    }
    stream = io.BytesIO()
    torch.save(payload, stream)
    return stream.getvalue()


def _restore_state(
    payload: bytes, controller: Any, *, device: torch.device, dtype: torch.dtype
) -> QiFieldState:
    loaded = torch.load(io.BytesIO(payload), map_location=device, weights_only=True)
    harmonic = isinstance(controller, HarmonicAgeFieldController)
    expected_profiles = {
        "layout_profile_id": (
            HARMONIC_AGE_LAYOUT_PROFILE_ID
            if harmonic
            else ORDERED_RELATIONAL_LAYOUT_PROFILE_ID
        ),
        "operator_profile_id": (
            HARMONIC_AGE_OPERATOR_PROFILE_ID
            if harmonic
            else ORDERED_RELATIONAL_OPERATOR_PROFILE_ID
        ),
        "projection_profile_id": (
            HARMONIC_AGE_PROJECTION_PROFILE_ID
            if harmonic
            else ORDERED_RELATIONAL_PROJECTION_PROFILE_ID
        ),
    }
    if (
        loaded.get("config") != controller.config.to_dict()
        or loaded.get("config_fingerprint")
        != getattr(controller, "config_fingerprint", "")
        or any(loaded.get(name) != value for name, value in expected_profiles.items())
    ):
        raise L49RunnerError("persistence profile/configuration identity mismatch")
    field = loaded.get("field")
    if not torch.is_tensor(field):
        raise L49RunnerError("persistence payload has no native field tensor")
    state = QiFieldState(field.to(device=device, dtype=dtype).clone())
    controller._validate_state(state)
    return state


def _zero_drift(device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    return torch.zeros(BATCH_SIZE, device=device, dtype=dtype)


def _prefix(
    ordered: OrderedRelationalChromaticFieldController,
    state: QiFieldState,
    *, blank_ticks: int, device: torch.device, dtype: torch.dtype,
) -> tuple[QiFieldState, dict[str, dict[str, np.ndarray]], list[int], list[np.ndarray]]:
    state, heartbeat = ordered.heartbeat(state)
    clamp_counts = [int(heartbeat.clamp_count)]
    tick = ordered.tick(state, symbols=torch.as_tensor(S0, device=device), steps=EVOLUTION_STEPS, trust=1.0)
    state = tick.state
    clamp_counts.append(int(tick.clamp_count))
    drifts = [l30.cpu(tick.input_energy_drift).reshape(-1)]
    captures = [_ordered_capture(ordered, state)]
    for _ in range(blank_ticks):
        tick = ordered.tick(state, steps=EVOLUTION_STEPS)
        state = tick.state
        clamp_counts.append(int(tick.clamp_count))
        drifts.append(l30.cpu(tick.input_energy_drift).reshape(-1))
    captures.append(_ordered_capture(ordered, state))
    return state, {"deposit": captures[0], "horizon": captures[1]}, clamp_counts, drifts


def _branch_path(
    ordered: OrderedRelationalChromaticFieldController,
    harmonic: HarmonicAgeFieldController,
    source: QiFieldState,
    *,
    name: str,
    horizons: tuple[int, ...],
    symbols: torch.Tensor,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[list[QiFieldState], list[dict[str, np.ndarray]], list[int], list[np.ndarray]]:
    state = source.clone()
    if name == "I":
        drift, clamp = _zero_drift(device, dtype), 0
    elif name == "U":
        state, drift, clamp = harmonic.lift_harmonics(state), _zero_drift(device, dtype), 0
    elif name == "W":
        state, drift, clamp = bare_write(ordered, state, symbols)
    else:
        state, drift, clamp = lift_then_bare_write(ordered, harmonic, state, symbols)
    checkpoints = [_full_capture(ordered, harmonic, state)]
    states = [state.clone()]
    clamps = [int(clamp)]
    drifts = [l30.cpu(drift).reshape(-1)]
    previous = 0
    for horizon in horizons[1:]:
        for _ in range(horizon - previous):
            tick = ordered.tick(state, steps=EVOLUTION_STEPS)
            state = tick.state
            clamps.append(int(tick.clamp_count))
            drifts.append(l30.cpu(tick.input_energy_drift).reshape(-1))
        checkpoints.append(_full_capture(ordered, harmonic, state))
        states.append(state.clone())
        previous = horizon
    return states, checkpoints, clamps, drifts


def _sequence_path(
    ordered: OrderedRelationalChromaticFieldController,
    harmonic: HarmonicAgeFieldController,
    source: QiFieldState,
    *,
    blank_ticks: int,
    symbols: tuple[torch.Tensor, torch.Tensor],
    device: torch.device,
    dtype: torch.dtype,
    initial_clamp: int,
    initial_drift: np.ndarray,
) -> tuple[list[dict[str, np.ndarray]], list[int], list[np.ndarray], list[str], list[str]]:
    state = source.clone()
    captures = [_full_capture(ordered, harmonic, state)]
    clamps = [int(initial_clamp)]
    drifts = [np.asarray(initial_drift, dtype=np.float32).copy()]
    for _ in range(blank_ticks):
        tick = ordered.tick(state, steps=EVOLUTION_STEPS)
        state = tick.state
        clamps.append(int(tick.clamp_count))
        drifts.append(l30.cpu(tick.input_energy_drift).reshape(-1))
    captures.append(_full_capture(ordered, harmonic, state))

    ordered_payload = _serialize_state(ordered, state)
    harmonic_payload = _serialize_state(harmonic, state)
    uninterrupted_hashes: list[str] = []
    reloaded_hashes: list[str] = []
    resumed_ordered, resumed_harmonic = _new_controllers(ordered.config.mode_count)
    resumed_state = _restore_state(ordered_payload, resumed_ordered, device=device, dtype=dtype)
    resumed_harmonic_state = _restore_state(harmonic_payload, resumed_harmonic, device=device, dtype=dtype)
    if not torch.equal(resumed_state.field, state.field) or not torch.equal(resumed_harmonic_state.field, state.field):
        raise L49RunnerError("persistence changed s1-horizon field")

    def event_hash() -> None:
        uninterrupted_hashes.append(tensor_sha256(state.field))
        reloaded_hashes.append(tensor_sha256(resumed_state.field))
        if not torch.equal(state.field, resumed_state.field):
            raise L49RunnerError("save/reload continuation diverged")

    def blank_event() -> None:
        nonlocal state, resumed_state
        tick = ordered.tick(state, steps=EVOLUTION_STEPS)
        state = tick.state
        rtick = resumed_ordered.tick(resumed_state, steps=EVOLUTION_STEPS)
        resumed_state = rtick.state
        clamps.append(int(tick.clamp_count))
        drifts.append(l30.cpu(tick.input_energy_drift).reshape(-1))
        event_hash()

    state, drift, clamp = lift_then_bare_write(ordered, harmonic, state, symbols[0])
    clamps.append(int(clamp))
    drifts.append(l30.cpu(drift).reshape(-1))
    resumed_state, _, _ = lift_then_bare_write(
        resumed_ordered, resumed_harmonic, resumed_state, symbols[0]
    )
    event_hash()
    captures.append(_full_capture(ordered, harmonic, state))
    for _ in range(blank_ticks):
        blank_event()
    captures.append(_full_capture(ordered, harmonic, state))
    state, drift, clamp = lift_then_bare_write(ordered, harmonic, state, symbols[1])
    clamps.append(int(clamp))
    drifts.append(l30.cpu(drift).reshape(-1))
    resumed_state, _, _ = lift_then_bare_write(
        resumed_ordered, resumed_harmonic, resumed_state, symbols[1]
    )
    event_hash()
    captures.append(_full_capture(ordered, harmonic, state))
    for _ in range(blank_ticks):
        blank_event()
    captures.append(_full_capture(ordered, harmonic, state))
    return captures, clamps, drifts, uninterrupted_hashes, reloaded_hashes


def _pack_capture(captures: list[dict[str, np.ndarray]], key: str) -> np.ndarray:
    return np.stack([capture[key] for capture in captures])


def run_board(
    device: torch.device, dtype: torch.dtype, *, smoke: bool = False
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    mode_count = 520 if smoke else MODE_COUNT
    branch_horizons = (0, 1, 2, 4) if smoke else (0, 8, 16, 128)
    sequence_blanks = 2 if smoke else 16
    if not smoke:
        bound_inputs = (
            (L40_BOARD, L40_BOARD_SHA256),
            (L40_TRACE, L40_TRACE_SHA256),
            (L40_VERIFICATION, L40_VERIFICATION_SHA256),
        )
        mismatches = [
            f"{path}: missing"
            if not path.is_file()
            else f"{path}: {sha256_file(path)}"
            for path, expected in bound_inputs
            if not path.is_file() or sha256_file(path) != expected
        ]
        if mismatches:
            raise L49RunnerError(f"L40 input hash mismatch: {mismatches!r}")
    ordered, harmonic = _new_controllers(mode_count)
    state = ordered.new_state(batch_size=BATCH_SIZE, device=device, dtype=dtype)
    state, prefix, prefix_clamps, prefix_drifts = _prefix(
        ordered, state, blank_ticks=2 if smoke else 16, device=device, dtype=dtype
    )
    if not smoke:
        observed = [tensor_sha256(prefix[name]["field"]) for name in ("deposit", "horizon")]
        if tuple(observed) != PREFIX_FIELD_HASHES:
            raise L49RunnerError(f"L40 prefix field hash mismatch: {observed!r}")
        horizon = prefix["horizon"]
        if not np.all(horizon["current_available"]) or not np.all(horizon["relational_available"]):
            raise L49RunnerError("L40 contaminated horizon availability mismatch")
        if not np.array_equal(horizon["current_symbols"], S0) or not np.array_equal(horizon["relational_symbols"], S0):
            raise L49RunnerError("L40 contaminated horizon symbol mismatch")

    s1_tensor = torch.as_tensor(S1, device=device, dtype=torch.int64)
    branch_states: list[list[QiFieldState]] = []
    branch_captures: list[list[dict[str, np.ndarray]]] = []
    branch_clamps: list[list[int]] = []
    branch_drifts: list[list[np.ndarray]] = []
    pre_state = QiFieldState(torch.as_tensor(prefix["horizon"]["field"], device=device, dtype=dtype))
    for name in BRANCH_NAMES:
        states, captures, clamps, drifts = _branch_path(
            ordered, harmonic, pre_state, name=name, horizons=branch_horizons,
            symbols=s1_tensor, device=device, dtype=dtype,
        )
        branch_states.append(states)
        branch_captures.append(captures)
        branch_clamps.append(clamps)
        branch_drifts.append(drifts)

    sequence_source = branch_states[3][0].clone()
    sequence_captures, sequence_clamps, sequence_drifts, resume_u, resume_r = _sequence_path(
        ordered,
        harmonic,
        sequence_source,
        blank_ticks=sequence_blanks,
        symbols=(torch.as_tensor(S2, device=device), torch.as_tensor(S3, device=device)),
        device=device,
        dtype=dtype,
        initial_clamp=branch_clamps[3][0],
        initial_drift=branch_drifts[3][0],
    )
    prefix_fields = [prefix["deposit"]["field"], prefix["horizon"]["field"]]
    prefix_post = [prefix["deposit"]["post_field"], prefix["horizon"]["post_field"]]
    arrays: dict[str, np.ndarray] = {
        "schema_id": np.asarray(TRACE_SCHEMA),
        "branch_names": np.asarray(BRANCH_NAMES, dtype="<U2"),
        "branch_checkpoint_names": np.asarray(BRANCH_CHECKPOINT_NAMES, dtype="<U16"),
        "sequence_checkpoint_names": np.asarray(SEQUENCE_CHECKPOINT_NAMES, dtype="<U24"),
        "stage_symbols": STAGES.copy(),
        "codebook": l30.cpu(ordered.codebook(device=device, dtype=dtype)),
        "channel_phase": np.stack((l30.cpu(ordered._constants(state)["channel_phase"].real), l30.cpu(ordered._constants(state)["channel_phase"].imag)), axis=-1).astype(np.float32),
        "prefix_field_sha256": np.asarray([tensor_sha256(x) for x in prefix_fields], dtype="<U64"),
        "fork_field_sha256": np.asarray([tensor_sha256(prefix["horizon"]["field"])] * 4, dtype="<U64"),
        "s1_symbol_sha256": np.asarray(tensor_sha256(S1), dtype="<U64"),
        "prefix_checkpoint_fields": np.stack(prefix_fields),
        "prefix_post_readout_fields": np.stack(prefix_post),
        "prefix_emitted_symbols": np.stack([prefix[n]["emitted"] for n in ("deposit", "horizon")]),
        "prefix_current_symbols": np.stack([prefix[n]["current_symbols"] for n in ("deposit", "horizon")]),
        "prefix_relational_symbols": np.stack([prefix[n]["relational_symbols"] for n in ("deposit", "horizon")]),
        "prefix_current_available": np.stack([prefix[n]["current_available"] for n in ("deposit", "horizon")]),
        "prefix_relational_available": np.stack([prefix[n]["relational_available"] for n in ("deposit", "horizon")]),
        "prefix_current_scores": np.stack([prefix[n]["current_scores"] for n in ("deposit", "horizon")]),
        "prefix_relational_scores": np.stack([prefix[n]["relational_scores"] for n in ("deposit", "horizon")]),
        "prefix_ordered_scores": np.stack([prefix[n]["ordered_scores"] for n in ("deposit", "horizon")]),
        "prefix_clamp_counts": np.asarray(prefix_clamps, dtype=np.int64),
        "prefix_input_energy_drift": np.stack(prefix_drifts).astype(np.float32),
    }
    arrays.update({
        "branch_pre_fields": np.stack([prefix["horizon"]["field"] for _ in range(4)]),
        "branch_checkpoint_fields": np.stack([_pack_capture(branch_captures[i], "field") for i in range(4)]),
        "branch_post_readout_fields": np.stack([_pack_capture(branch_captures[i], "post_field") for i in range(4)]),
        "branch_harmonic_d": np.stack([_pack_capture(branch_captures[i], "harmonic_d") for i in range(4)]),
        "branch_harmonic_vd": np.stack([_pack_capture(branch_captures[i], "harmonic_vd") for i in range(4)]),
        "branch_codebook_coefficients": np.stack([_pack_capture(branch_captures[i], "coefficients") for i in range(4)]),
        "branch_age_scores": np.stack([_pack_capture(branch_captures[i], "age_scores") for i in range(4)]),
        "branch_age_energies": np.stack([_pack_capture(branch_captures[i], "age_energies") for i in range(4)]),
        "branch_age_symbols": np.stack([_pack_capture(branch_captures[i], "age_symbols") for i in range(4)]),
        "branch_age_available": np.stack([_pack_capture(branch_captures[i], "age_available") for i in range(4)]),
        "branch_current_predecessor": np.stack([_pack_capture(branch_captures[i], "current_predecessor") for i in range(4)]),
        "branch_ordered_current_symbols": np.stack([_pack_capture(branch_captures[i], "current_symbols") for i in range(4)]),
        "branch_ordered_relational_symbols": np.stack([_pack_capture(branch_captures[i], "relational_symbols") for i in range(4)]),
        "branch_ordered_current_available": np.stack([_pack_capture(branch_captures[i], "current_available") for i in range(4)]),
        "branch_ordered_relational_available": np.stack([_pack_capture(branch_captures[i], "relational_available") for i in range(4)]),
        "branch_ordered_scores": np.stack([_pack_capture(branch_captures[i], "ordered_scores") for i in range(4)]),
        "branch_clamp_counts": np.asarray([clamps + [0] * (129 - len(clamps)) for clamps in branch_clamps], dtype=np.int64) if not smoke else np.asarray(branch_clamps, dtype=np.int64),
        "branch_input_energy_drift": np.asarray([drifts + [np.zeros(BATCH_SIZE)] * (129 - len(drifts)) for drifts in branch_drifts], dtype=np.float32) if not smoke else np.asarray(branch_drifts, dtype=np.float32),
        "branch_dynamic_energy": np.stack([_pack_capture(branch_captures[i], "dynamic_energy") for i in range(4)]),
        "branch_maximum_absolute_field": np.stack([_pack_capture(branch_captures[i], "maximum_absolute_field") for i in range(4)]).astype(np.float32),
        "sequence_fields": _pack_capture(sequence_captures, "field"),
        "sequence_post_readout_fields": _pack_capture(sequence_captures, "post_field"),
        "sequence_harmonic_d": _pack_capture(sequence_captures, "harmonic_d"),
        "sequence_harmonic_vd": _pack_capture(sequence_captures, "harmonic_vd"),
        "sequence_codebook_coefficients": _pack_capture(sequence_captures, "coefficients"),
        "sequence_age_scores": _pack_capture(sequence_captures, "age_scores"),
        "sequence_age_energies": _pack_capture(sequence_captures, "age_energies"),
        "sequence_age_symbols": _pack_capture(sequence_captures, "age_symbols"),
        "sequence_age_available": _pack_capture(sequence_captures, "age_available"),
        "sequence_current_predecessor": _pack_capture(sequence_captures, "current_predecessor"),
        "sequence_ordered_current_symbols": _pack_capture(sequence_captures, "current_symbols"),
        "sequence_ordered_relational_symbols": _pack_capture(sequence_captures, "relational_symbols"),
        "sequence_ordered_current_available": _pack_capture(sequence_captures, "current_available"),
        "sequence_ordered_relational_available": _pack_capture(sequence_captures, "relational_available"),
        "sequence_ordered_scores": _pack_capture(sequence_captures, "ordered_scores"),
        "sequence_clamp_counts": np.asarray(sequence_clamps, dtype=np.int64),
        "sequence_input_energy_drift": np.asarray(sequence_drifts, dtype=np.float32),
        "resume_uninterrupted_sha256": np.asarray(resume_u, dtype="<U64"),
        "resume_reloaded_sha256": np.asarray(resume_r, dtype="<U64"),
    })
    metrics = {
        "mode_count": mode_count,
        "canonical": not smoke,
        "prefix_clamp_count": int(sum(prefix_clamps)),
        "branch_clamp_count": int(sum(sum(x) for x in branch_clamps)),
        "sequence_clamp_count": int(sum(sequence_clamps)),
        "maximum_input_energy_drift": float(max(
            np.abs(arrays["prefix_input_energy_drift"]).max(),
            np.abs(arrays["branch_input_energy_drift"]).max(),
            np.abs(arrays["sequence_input_energy_drift"]).max(),
        )),
        "maximum_absolute_field": float(arrays["branch_maximum_absolute_field"].max()),
        "resume_event_count": len(resume_u),
    }
    return metrics, arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="float32", choices=("float32", "float64"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    device = torch.device(args.device)
    dtype = torch.float64 if args.dtype == "float64" else torch.float32
    output_dir = args.output_dir.resolve() if args.output_dir is not None else (Path(tempfile.mkdtemp(prefix="l49-smoke-") ) if args.smoke else OUTPUT_DIR)
    board_path, trace_path = output_dir / BOARD_NAME, output_dir / TRACE_NAME
    hashes = {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in SOURCE_PATHS if p.is_file()}
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA, "protocol_id": "cassi.l49.harmonic-write-causal-crossover-protocol.v1", "status": "INCOMPLETE", "execution": {"canonical": not args.smoke, "smoke": args.smoke},
        "layout_profile_id": ORDERED_RELATIONAL_LAYOUT_PROFILE_ID,
        "operator_profile_id": ORDERED_RELATIONAL_OPERATOR_PROFILE_ID,
        "harmonic_layout_profile_id": HARMONIC_AGE_LAYOUT_PROFILE_ID,
        "harmonic_operator_profile_id": HARMONIC_AGE_OPERATOR_PROFILE_ID,
        "harmonic_projection_profile_id": HARMONIC_AGE_PROJECTION_PROFILE_ID,
        "projection_profile_id": ORDERED_RELATIONAL_PROJECTION_PROFILE_ID,
        "trace_schema_id": TRACE_SCHEMA,
        "preregistration_sha256": hashes.get(PREREGISTRATION.relative_to(ROOT).as_posix()),
        "source_sha256": hashes,
        "device": {"requested": str(device), "type": device.type, "name": torch.cuda.get_device_name(device) if device.type == "cuda" and torch.cuda.is_available() else str(device), "torch_version": torch.__version__, "hip_version": torch.version.hip, "dtype": args.dtype},
        "constants": {
            "channels": CHANNELS,
            "mode_count": MODE_COUNT if not args.smoke else 520,
            "active_modes": (MODE_COUNT if not args.smoke else 520) // 2,
            "alphabet_size": ALPHABET_SIZE,
            "batch_size": BATCH_SIZE,
            "evolution_steps": EVOLUTION_STEPS,
            "blank_ticks": 128 if not args.smoke else 4,
            "readout_energy_floor": READOUT_FLOOR,
            "max_mode_amplitude": MAX_MODE_AMPLITUDE,
            "max_epsilon": MAX_EPSILON,
            "maximum_input_energy_drift": 2.0e-6,
            "age_harmonics": [1, 2, 3, 4, 5, 6, 0],
            "stage_symbols": STAGES.tolist(),
            "branch_checkpoints": list(BRANCH_CHECKPOINT_NAMES),
            "sequence_checkpoints": list(SEQUENCE_CHECKPOINT_NAMES),
        },
        "prefix": {"l40_board_sha256": L40_BOARD_SHA256, "l40_trace_sha256": L40_TRACE_SHA256, "l40_verification_sha256": L40_VERIFICATION_SHA256, "field_sha256": list(PREFIX_FIELD_HASHES)},
        "trace": {"path": TRACE_NAME, "sha256": None}, "arms": {},
    }
    atomic_json(board_path, board)
    try:
        if not args.smoke and (device.type != "cuda" or dtype is not torch.float32 or not torch.cuda.is_available()):
            raise L49RunnerError("canonical L49 execution requires CUDA and float32")
        missing = [str(p) for p in SOURCE_PATHS if not p.is_file()]
        if missing:
            raise L49RunnerError(f"missing bound source files: {missing!r}")
        started = time.perf_counter()
        metrics, arrays = run_board(device, dtype, smoke=args.smoke)
        atomic_npz(trace_path, arrays)
        board["arms"]["smoke" if args.smoke else "canonical"] = metrics
        board["trace"] = {"path": TRACE_NAME, "sha256": sha256_file(trace_path), "array_count": len(arrays)}
        board["resources"] = {"wall_seconds": float(time.perf_counter() - started), "peak_allocated_bytes": int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" and torch.cuda.is_available() else 0}
        board["status"] = "COMPLETE"
        atomic_json(board_path, board)
    except Exception as exc:
        board["status"] = "INCOMPLETE"; board["error"] = f"{type(exc).__name__}: {exc}"; atomic_json(board_path, board)
        raise
    print(board_path)
    print(trace_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
