"""Independently verify and classify the frozen L29 prismatic board."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_qi_field import QiFieldConfig, QiFieldController

BOARD_SCHEMA = "cassi.l29.phi-prismatic-heartbeat-board.v1"
TRACE_SCHEMA = "cassi.l29.phi-prismatic-heartbeat-traces.v1"
VERIFICATION_SCHEMA = "cassi.l29.phi-prismatic-heartbeat-verification.v1"
LAYOUT_PROFILE = "cassi.qi-prismatic-shared-coordinate.v1"
OPERATOR_PROFILE = "cassi.qi-prismatic-heartbeat.v1"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
TARGETS = np.asarray((0, 37, 74, 111, 148, 185, 222, 259), dtype=np.int64)
DISTRACTORS = (TARGETS + 97) % 260
READ_TICKS = np.asarray((0, 1, 2, 4, 8, 16, 32, 64), dtype=np.int64)
LONG_TICKS = np.asarray((16, 32, 64), dtype=np.int64)
WARM_TICKS = 128
BEATING_TICKS = 128
TASK_TICKS = 65
EVOLUTION_STEPS = 16
READOUT_FLOOR = 1.0e-8
DEFAULT_BOARD = ROOT / "_diag" / "l29-phi-prismatic-heartbeat" / "l29-board.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "l29-phi-prismatic-heartbeat"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L29-PHI-PRISMATIC-HEARTBEAT-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l29-verification.json"
EXPECTED_SOURCE_PATHS = {
    "designs/L29-PHI-PRISMATIC-HEARTBEAT-PREREG.md",
    "cassi_prismatic_field.py",
    "verification/run_l29_phi_prismatic_heartbeat.py",
    "verification/verify_l29_phi_prismatic_heartbeat.py",
}
EXPECTED_ARMS = {
    "phi-7": (7, 3512, tuple(PHI**index for index in range(7))),
    "linear-time-7": (
        7,
        3512,
        tuple(1.0 + index * (PHI**6 - 1.0) / 6.0 for index in range(7)),
    ),
    "linear-frequency-7": (
        7,
        3512,
        tuple(
            1.0 / (1.0 - index * (1.0 - PHI**-6) / 6.0)
            for index in range(7)
        ),
    ),
    "geometric-4": (4, 6146, (1.0, PHI**2, PHI**4, PHI**6)),
}


class L29VerificationError(RuntimeError):
    """One canonical evidence-integrity requirement failed."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise L29VerificationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha(value: Any, label: str) -> str:
    need(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        f"{label} must be lowercase SHA-256",
    )
    return value


def finite_tree(value: Any, label: str = "JSON") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        need(math.isfinite(value), f"{label} contains a nonfinite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            finite_tree(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        need(all(isinstance(key, str) for key in value), f"{label} has a non-string key")
        for key, item in value.items():
            finite_tree(item, f"{label}.{key}")
        return
    raise L29VerificationError(f"{label} contains unsupported value {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def finite_canonical_json(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"nonfinite JSON token {token}")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise L29VerificationError(f"cannot read finite JSON board: {exc}") from exc
    need(isinstance(value, Mapping), "board must be a JSON object")
    finite_tree(value)
    need(raw == canonical_bytes(value), "board JSON is not canonical")
    return value


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    need(isinstance(value, Mapping), f"{label} must be an object")
    return value


def sequence(value: Any, label: str, length: int | None = None) -> list[Any]:
    need(isinstance(value, list), f"{label} must be an array")
    if length is not None:
        need(len(value) == length, f"{label} must have length {length}")
    return value


def close(actual: float, expected: float, label: str, *, atol: float = 1.0e-7, rtol: float = 1.0e-6) -> None:
    need(
        math.isclose(float(actual), float(expected), abs_tol=atol, rel_tol=rtol),
        f"{label} differs: {actual!r} != {expected!r}",
    )


def array_close(
    actual: np.ndarray,
    expected: np.ndarray,
    label: str,
    *,
    atol: float = 1.0e-6,
    rtol: float = 1.0e-5,
) -> None:
    need(
        actual.shape == expected.shape
        and np.allclose(actual, expected, atol=atol, rtol=rtol),
        f"{label} differs",
    )


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def expected_array_contract(slug: str, banks: int, mode_count: int) -> dict[str, tuple[tuple[int, ...], np.dtype[Any]]]:
    key = slug.replace("-", "_")
    width = mode_count // 2
    batch = len(TARGETS)
    contract: dict[str, tuple[tuple[int, ...], np.dtype[Any]]] = {}
    for probe in ("zero_pre", "zero_post", "first_heartbeat_pre", "first_heartbeat_post"):
        for coordinate in ("c", "d", "vc", "vd"):
            contract[f"{key}_{probe}_{coordinate}"] = ((banks, width, 1), np.dtype(np.complex64))
    contract.update(
        {
            f"{key}_zero_drift": ((1,), np.dtype(np.float32)),
            f"{key}_first_heartbeat_source_weights": ((banks,), np.dtype(np.float32)),
            f"{key}_first_heartbeat_energy_before": ((1,), np.dtype(np.float32)),
            f"{key}_first_heartbeat_energy_after": ((1,), np.dtype(np.float32)),
            f"{key}_first_heartbeat_injection": ((1,), np.dtype(np.float32)),
            f"{key}_first_heartbeat_clamp": ((), np.dtype(np.int64)),
            f"{key}_codebook": ((260, width, 2), np.dtype(np.float32)),
        }
    )
    for phase, ticks in (("warm", WARM_TICKS), ("beat", BEATING_TICKS)):
        contract[f"{key}_{phase}_energy"] = ((ticks, banks), np.dtype(np.float32))
        contract[f"{key}_{phase}_hamiltonian"] = ((ticks,), np.dtype(np.float32))
        contract[f"{key}_{phase}_injection"] = ((ticks,), np.dtype(np.float32))
        contract[f"{key}_{phase}_clamp"] = ((ticks,), np.dtype(np.int64))
        contract[f"{key}_{phase}_leakage"] = ((ticks,), np.dtype(np.float32))
    for event in ("target", "distractor"):
        for coordinate in ("c", "d", "vc", "vd"):
            contract[f"{key}_{event}_pre_{coordinate}"] = ((banks, width, batch), np.dtype(np.complex64))
            contract[f"{key}_{event}_post_{coordinate}"] = ((banks, width, batch), np.dtype(np.complex64))
    contract.update(
        {
            f"{key}_task_read_c": ((len(READ_TICKS), banks, width, batch), np.dtype(np.complex64)),
            f"{key}_task_read_d": ((len(READ_TICKS), banks, width, batch), np.dtype(np.complex64)),
            f"{key}_task_read_scores": ((len(READ_TICKS), batch, 260), np.dtype(np.float32)),
            f"{key}_task_read_bank_scores": ((len(READ_TICKS), banks, batch, 260), np.dtype(np.float32)),
            f"{key}_task_read_coherence": ((len(READ_TICKS), batch), np.dtype(np.float32)),
            f"{key}_task_read_available": ((len(READ_TICKS), batch), np.dtype(np.bool_)),
            f"{key}_task_read_predictions": ((len(READ_TICKS), batch), np.dtype(np.int64)),
            f"{key}_task_energy": ((TASK_TICKS, banks, batch), np.dtype(np.float32)),
            f"{key}_task_hamiltonian": ((TASK_TICKS, batch), np.dtype(np.float32)),
            f"{key}_task_injection": ((TASK_TICKS, batch), np.dtype(np.float32)),
            f"{key}_task_clamp": ((TASK_TICKS,), np.dtype(np.int64)),
            f"{key}_task_input_energy_drift": ((TASK_TICKS, batch), np.dtype(np.float32)),
            f"{key}_task_target_ranks": ((len(READ_TICKS), batch), np.dtype(np.int64)),
            f"{key}_task_distractor_ranks": ((len(READ_TICKS), batch), np.dtype(np.int64)),
            f"{key}_task_bank_target_ranks": ((len(READ_TICKS), banks, batch), np.dtype(np.int64)),
        }
    )
    return contract


def ranks(scores: np.ndarray, symbols: np.ndarray) -> np.ndarray:
    selected = np.take_along_axis(scores, symbols[:, None], axis=1)[:, 0]
    ids = np.arange(scores.shape[1], dtype=np.int64)[None, :]
    return (
        1
        + (scores > selected[:, None]).sum(axis=1)
        + ((scores == selected[:, None]) & (ids < symbols[:, None])).sum(axis=1)
    ).astype(np.int64)


def coordinate_energy(
    common: np.ndarray,
    differential: np.ndarray,
    common_velocity: np.ndarray,
    differential_velocity: np.ndarray,
) -> np.ndarray:
    return np.mean(
        np.abs(common) ** 2
        + np.abs(differential) ** 2
        + np.abs(common_velocity) ** 2
        + np.abs(differential_velocity) ** 2,
        axis=1,
    ) / (1.0 + PHI * PHI)


def modulation_drift(data: Mapping[str, np.ndarray], key: str, event: str) -> np.ndarray:
    before = coordinate_energy(
        data[f"{key}_{event}_pre_c"],
        data[f"{key}_{event}_pre_d"],
        data[f"{key}_{event}_pre_vc"],
        data[f"{key}_{event}_pre_vd"],
    )[0]
    after = coordinate_energy(
        data[f"{key}_{event}_post_c"],
        data[f"{key}_{event}_post_d"],
        data[f"{key}_{event}_post_vc"],
        data[f"{key}_{event}_post_vd"],
    )[0]
    denominator = np.maximum(np.abs(before), np.finfo(np.float32).eps)
    return np.where((before == 0.0) & (after == 0.0), 0.0, (after - before) / denominator)


def recompute_readout(
    differential: np.ndarray,
    bank_energy: np.ndarray,
    codebook_parts: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    codebook = codebook_parts[..., 0] + 1j * codebook_parts[..., 1]
    width = differential.shape[1]
    rms = np.sqrt(np.mean(np.abs(differential) ** 2, axis=1))
    coefficients = np.einsum(
        "aw,swb->sab", np.conj(codebook), differential, optimize=True
    ) / float(width)
    coefficients = coefficients / np.maximum(
        rms[:, None, :], np.finfo(np.float32).eps
    )
    active = bank_energy >= READOUT_FLOOR
    contributions = np.where(active[:, None, :], coefficients, 0.0)
    white = contributions.sum(axis=0)
    scores = (np.abs(white) ** 2).T.astype(np.float32)
    bank_scores = np.transpose(np.abs(contributions) ** 2, (0, 2, 1)).astype(np.float32)
    predictions = np.argmax(scores, axis=1).astype(np.int64)
    active_count = active.sum(axis=0)
    available = (bank_energy[-1] >= READOUT_FLOOR) & (active_count >= 2)
    winning = np.transpose(contributions, (2, 0, 1))[
        np.arange(differential.shape[2]), :, predictions
    ]
    winning_scores = scores[np.arange(scores.shape[0]), predictions]
    coherence = winning_scores / (
        active_count.astype(np.float32) * np.sum(np.abs(winning) ** 2, axis=1)
        + 1.0e-12
    )
    coherence = np.where(available, coherence, 0.0).astype(np.float32)
    return scores, bank_scores, predictions, available, coherence


def beating_index(values: np.ndarray) -> float:
    return float(
        (
            np.quantile(values, 0.99, method="linear")
            - np.quantile(values, 0.01, method="linear")
        )
        / np.median(values)
    )


def fft_top(values: np.ndarray) -> list[dict[str, float | int]]:
    spectrum = np.abs(np.fft.rfft(values - values.mean()))
    candidates = list(range(1, spectrum.size))
    candidates.sort(key=lambda index: (-float(spectrum[index]), index))
    return [
        {"bin": int(index), "amplitude": float(spectrum[index])}
        for index in candidates[:3]
    ]


def config_fingerprint(config: Mapping[str, Any], codebook_fingerprint: str) -> str:
    payload = {
        "layout_profile_id": LAYOUT_PROFILE,
        "operator_profile_id": OPERATOR_PROFILE,
        "shared_codebook_fingerprint": codebook_fingerprint,
        "config": dict(config),
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def verify_arm(
    slug: str,
    arm: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    banks, mode_count, expected_timescales = EXPECTED_ARMS[slug]
    width = mode_count // 2
    key = slug.replace("-", "_")
    declaration = mapping(arm.get("declaration"), f"{slug} declaration")
    reported = mapping(arm.get("metrics"), f"{slug} metrics")
    resources = mapping(arm.get("resources"), f"{slug} resources")
    need(int(declaration.get("bank_count", -1)) == banks, f"{slug} bank count differs")
    need(int(declaration.get("mode_count", -1)) == mode_count, f"{slug} mode count differs")
    need(int(declaration.get("active_width", -1)) == width, f"{slug} active width differs")
    timescales = np.asarray(
        sequence(declaration.get("timescales"), f"{slug} timescales", banks),
        dtype=np.float64,
    )
    array_close(timescales, np.asarray(expected_timescales), f"{slug} timescales", atol=1.0e-12, rtol=1.0e-12)
    damping = np.asarray(
        sequence(declaration.get("damping"), f"{slug} damping", banks),
        dtype=np.float64,
    )
    array_close(damping, 0.2 / timescales, f"{slug} damping law", atol=1.0e-12, rtol=1.0e-12)
    close(float(declaration.get("fastest_timescale", -1.0)), 1.0, f"{slug} fastest timescale", atol=1.0e-12, rtol=1.0e-12)
    close(float(declaration.get("slowest_timescale", -1.0)), PHI**6, f"{slug} slowest timescale", atol=1.0e-12, rtol=1.0e-12)
    need(declaration.get("modal_profile_endpoints") == [1.0, 1.25], f"{slug} modal bandwidth differs")
    need(int(declaration.get("state_values_per_batch", -1)) == 221256, f"{slug} state budget differs")
    need(int(declaration.get("active_dynamic_values_per_batch", -1)) == 98336, f"{slug} active budget differs")
    need(int(declaration.get("logical_ticks", -1)) == WARM_TICKS + BEATING_TICKS + TASK_TICKS, f"{slug} logical tick budget differs")
    batch_weighted_ticks = WARM_TICKS + BEATING_TICKS + TASK_TICKS * len(TARGETS)
    need(int(declaration.get("batch_weighted_evolution_ticks", -1)) == batch_weighted_ticks, f"{slug} batch-weighted tick budget differs")
    need(int(declaration.get("evolution_steps_per_tick", -1)) == EVOLUTION_STEPS, f"{slug} evolution steps differ")
    need(int(declaration.get("evolution_element_updates", -1)) == 98336 * EVOLUTION_STEPS * batch_weighted_ticks, f"{slug} element-update budget differs")
    expected_edge_updates = (banks - 1) * width * 2 * 2 * EVOLUTION_STEPS * batch_weighted_ticks
    need(int(declaration.get("edge_complex_endpoint_updates", -1)) == expected_edge_updates, f"{slug} edge-update receipt differs")
    need(isinstance(resources.get("wall_seconds"), (int, float)) and float(resources["wall_seconds"]) > 0.0, f"{slug} wall time is invalid")
    need(isinstance(resources.get("peak_allocated_bytes"), int) and int(resources["peak_allocated_bytes"]) > 0, f"{slug} peak allocation is invalid")
    need(declaration.get("trace_prefix") == key, f"{slug} trace prefix differs")

    config = mapping(declaration.get("config"), f"{slug} config")
    need(tuple(config) == (
        "alphabet_size",
        "bank_timescales",
        "base_damping",
        "base_omega2",
        "coupling_omega2",
        "dt",
        "epsilon_tau",
        "heartbeat_target_energy",
        "max_mean_energy",
        "max_mode_amplitude",
        "mode_count",
        "nonlinear_gain",
        "readout_energy_floor",
    ) or set(config) == {
        "alphabet_size",
        "bank_timescales",
        "base_damping",
        "base_omega2",
        "coupling_omega2",
        "dt",
        "epsilon_tau",
        "heartbeat_target_energy",
        "max_mean_energy",
        "max_mode_amplitude",
        "mode_count",
        "nonlinear_gain",
        "readout_energy_floor",
    }, f"{slug} config fields differ")
    expected_config = {
        "bank_timescales": [float(value) for value in expected_timescales],
        "mode_count": mode_count,
        "alphabet_size": 260,
        "dt": 0.05,
        "base_omega2": 1.0,
        "base_damping": 0.2,
        "nonlinear_gain": 0.002,
        "coupling_omega2": 0.25,
        "epsilon_tau": 0.05,
        "heartbeat_target_energy": 1.0,
        "readout_energy_floor": 1.0e-8,
        "max_mode_amplitude": 8.0,
        "max_mean_energy": 32.0,
    }
    need(dict(config) == expected_config, f"{slug} frozen config differs")
    codebook_controller = QiFieldController(
        QiFieldConfig(
            scale_count=1,
            mode_count=mode_count,
            alphabet_size=260,
            primes=(4093,),
            settle_steps=1,
        )
    )
    need(declaration.get("codebook_fingerprint") == codebook_controller.codebook_fingerprint, f"{slug} codebook fingerprint differs")
    need(declaration.get("config_fingerprint") == config_fingerprint(config, codebook_controller.codebook_fingerprint), f"{slug} config fingerprint differs")
    reconstructed_codebook = codebook_controller.codebook(0, dtype=torch.float32).numpy()
    array_close(arrays[f"{key}_codebook"], reconstructed_codebook, f"{slug} reconstructed codebook", atol=2.0e-6, rtol=1.0e-6)

    zero_arrays = [
        arrays[f"{key}_zero_{phase}_{coordinate}"]
        for phase in ("pre", "post")
        for coordinate in ("c", "d", "vc", "vd")
    ]
    zero_max = float(max(np.max(np.abs(value)) for value in zero_arrays))
    need(zero_max == 0.0, f"{slug} input changed the all-zero state")
    need(float(np.max(np.abs(arrays[f"{key}_zero_drift"]))) == 0.0, f"{slug} zero-state drift is nonzero")

    weights = arrays[f"{key}_first_heartbeat_source_weights"]
    expected_weights = np.zeros(banks, dtype=np.float32)
    if banks % 2:
        expected_weights[banks // 2] = 1.0
    else:
        expected_weights[banks // 2 - 1 : banks // 2 + 1] = 0.5
    array_close(weights, expected_weights, f"{slug} heartbeat source weights", atol=0.0, rtol=0.0)
    first_energy_by_bank = coordinate_energy(
        arrays[f"{key}_first_heartbeat_post_c"],
        arrays[f"{key}_first_heartbeat_post_d"],
        arrays[f"{key}_first_heartbeat_post_vc"],
        arrays[f"{key}_first_heartbeat_post_vd"],
    )
    first_energy = np.sum(first_energy_by_bank * weights[:, None], axis=0)
    array_close(first_energy, arrays[f"{key}_first_heartbeat_energy_after"], f"{slug} first heartbeat receipt", atol=2.0e-6, rtol=2.0e-6)
    first_error = float(np.max(np.abs(first_energy - 1.0)))

    target_drift = modulation_drift(arrays, key, "target")
    distractor_drift = modulation_drift(arrays, key, "distractor")
    drift_trace = arrays[f"{key}_task_input_energy_drift"]
    array_close(drift_trace[0], target_drift, f"{slug} target modulation drift", atol=2.0e-6, rtol=2.0e-5)
    array_close(drift_trace[8], distractor_drift, f"{slug} distractor modulation drift", atol=2.0e-6, rtol=2.0e-5)
    need(np.count_nonzero(np.delete(drift_trace, (0, 8), axis=0)) == 0, f"{slug} reports drift on an input-free tick")
    maximum_drift = float(max(np.max(np.abs(target_drift)), np.max(np.abs(distractor_drift))))

    warm_energy = arrays[f"{key}_warm_energy"]
    beat_hamiltonian = arrays[f"{key}_beat_hamiltonian"].astype(np.float64)
    need(bool(np.all(warm_energy >= 0.0)), f"{slug} warm energy is negative")
    need(bool(np.all(beat_hamiltonian > 0.0)), f"{slug} beating Hamiltonian is not positive")
    total_energy = float(warm_energy[-1].sum())
    root_fraction = float(warm_energy[-1, 0] / total_energy)
    crown_fraction = float(warm_energy[-1, -1] / total_energy)
    beat = beating_index(beat_hamiltonian)
    top_fft = fft_top(beat_hamiltonian)
    leakage = float(
        max(
            np.max(np.abs(arrays[f"{key}_first_heartbeat_post_d"])),
            np.max(arrays[f"{key}_warm_leakage"]),
            np.max(arrays[f"{key}_beat_leakage"]),
        )
    )
    clamp_count = int(
        arrays[f"{key}_first_heartbeat_clamp"].item()
        + arrays[f"{key}_warm_clamp"].sum()
        + arrays[f"{key}_beat_clamp"].sum()
        + arrays[f"{key}_task_clamp"].sum()
    )

    recomputed_scores = []
    recomputed_bank_scores = []
    recomputed_predictions = []
    recomputed_available = []
    recomputed_coherence = []
    for slot, tick in enumerate(READ_TICKS):
        values = recompute_readout(
            arrays[f"{key}_task_read_d"][slot],
            arrays[f"{key}_task_energy"][int(tick)],
            arrays[f"{key}_codebook"],
        )
        score, bank_score, prediction, available, coherence = values
        recomputed_scores.append(score)
        recomputed_bank_scores.append(bank_score)
        recomputed_predictions.append(prediction)
        recomputed_available.append(available)
        recomputed_coherence.append(coherence)
    scores = np.stack(recomputed_scores)
    bank_scores = np.stack(recomputed_bank_scores)
    predictions = np.stack(recomputed_predictions)
    availability = np.stack(recomputed_available)
    coherence = np.stack(recomputed_coherence)
    array_close(arrays[f"{key}_task_read_scores"], scores, f"{slug} white scores", atol=3.0e-5, rtol=2.0e-4)
    array_close(arrays[f"{key}_task_read_bank_scores"], bank_scores, f"{slug} bank scores", atol=3.0e-5, rtol=2.0e-4)
    need(np.array_equal(arrays[f"{key}_task_read_predictions"], predictions), f"{slug} white predictions differ")
    need(np.array_equal(arrays[f"{key}_task_read_available"], availability), f"{slug} availability differs")
    array_close(arrays[f"{key}_task_read_coherence"], coherence, f"{slug} white coherence", atol=3.0e-5, rtol=2.0e-4)

    target_ranks = np.stack([ranks(value, TARGETS) for value in scores])
    distractor_ranks = np.stack([ranks(value, DISTRACTORS) for value in scores])
    bank_target_ranks = np.empty((len(READ_TICKS), banks, len(TARGETS)), dtype=np.int64)
    for slot in range(len(READ_TICKS)):
        for bank in range(banks):
            bank_target_ranks[slot, bank] = ranks(bank_scores[slot, bank], TARGETS)
    need(np.array_equal(arrays[f"{key}_task_target_ranks"], target_ranks), f"{slug} target ranks differ")
    need(np.array_equal(arrays[f"{key}_task_distractor_ranks"], distractor_ranks), f"{slug} distractor ranks differ")
    need(np.array_equal(arrays[f"{key}_task_bank_target_ranks"], bank_target_ranks), f"{slug} bank ranks differ")

    tick8_slot = int(np.where(READ_TICKS == 8)[0][0])
    long_slots = np.where(np.isin(READ_TICKS, LONG_TICKS))[0]
    tick8_accuracy = float(np.mean(predictions[tick8_slot] == DISTRACTORS))
    long_white_mrr = float(np.mean(1.0 / target_ranks[long_slots].astype(np.float64)))
    bank_mrr = np.mean(1.0 / bank_target_ranks[long_slots].astype(np.float64), axis=(0, 2))
    best_bank = int(np.argmax(bank_mrr))
    mean_coherence = float(coherence.mean())

    close(float(reported.get("zero_input_max_abs", -1.0)), zero_max, f"{slug} reported zero-input metric", atol=0.0, rtol=0.0)
    close(float(reported.get("first_heartbeat_relative_error", -1.0)), first_error, f"{slug} reported heartbeat error", atol=2.0e-6, rtol=2.0e-5)
    close(float(reported.get("heartbeat_only_max_abs_d", -1.0)), leakage, f"{slug} reported leakage", atol=2.0e-7, rtol=2.0e-5)
    close(float(reported.get("maximum_input_energy_drift", -1.0)), maximum_drift, f"{slug} reported modulation drift", atol=2.0e-6, rtol=2.0e-5)
    need(int(reported.get("clamp_count", -1)) == clamp_count, f"{slug} reported clamp count differs")
    array_close(np.asarray(reported.get("warm_final_bank_energy"), dtype=np.float64), warm_energy[-1].astype(np.float64), f"{slug} reported final energy", atol=1.0e-7, rtol=1.0e-6)
    close(float(reported.get("warm_final_root_fraction", -1.0)), root_fraction, f"{slug} reported root propagation")
    close(float(reported.get("warm_final_crown_fraction", -1.0)), crown_fraction, f"{slug} reported crown propagation")
    close(float(reported.get("beating_index", -1.0)), beat, f"{slug} reported beating index")
    reported_fft = sequence(reported.get("fft_top_non_dc"), f"{slug} FFT receipt", 3)
    for index, expected in enumerate(top_fft):
        value = mapping(reported_fft[index], f"{slug} FFT bin {index}")
        need(int(value.get("bin", -1)) == expected["bin"], f"{slug} FFT bin differs")
        close(float(value.get("amplitude", -1.0)), float(expected["amplitude"]), f"{slug} FFT amplitude")
    close(float(reported.get("tick8_distractor_accuracy", -1.0)), tick8_accuracy, f"{slug} tick-8 accuracy", atol=0.0, rtol=0.0)
    need(reported.get("tick8_predictions") == [int(value) for value in predictions[tick8_slot]], f"{slug} tick-8 predictions differ")
    close(float(reported.get("long_horizon_white_mrr", -1.0)), long_white_mrr, f"{slug} white MRR")
    close(float(reported.get("best_bank_long_horizon_mrr", -1.0)), float(bank_mrr[best_bank]), f"{slug} best-bank MRR")
    need(int(reported.get("best_bank_index", -1)) == best_bank, f"{slug} best-bank index differs")
    array_close(np.asarray(reported.get("bank_long_horizon_mrr"), dtype=np.float64), bank_mrr.astype(np.float64), f"{slug} bank MRR")
    reciprocal_receipt = mapping(reported.get("target_reciprocal_ranks"), f"{slug} reciprocal-rank receipt")
    for tick in LONG_TICKS:
        slot = int(np.where(READ_TICKS == tick)[0][0])
        array_close(np.asarray(reciprocal_receipt.get(str(int(tick))), dtype=np.float64), 1.0 / target_ranks[slot].astype(np.float64), f"{slug} reciprocal ranks tick {tick}")
    close(float(reported.get("mean_white_coherence", -1.0)), mean_coherence, f"{slug} mean coherence")

    return {
        "first_heartbeat_relative_error": first_error,
        "heartbeat_only_max_abs_d": leakage,
        "maximum_input_energy_drift": maximum_drift,
        "clamp_count": clamp_count,
        "warm_final_root_fraction": root_fraction,
        "warm_final_crown_fraction": crown_fraction,
        "beating_index": beat,
        "tick8_distractor_accuracy": tick8_accuracy,
        "tick8_predictions": [int(value) for value in predictions[tick8_slot]],
        "long_horizon_white_mrr": long_white_mrr,
        "best_bank_long_horizon_mrr": float(bank_mrr[best_bank]),
        "best_bank_index": best_bank,
        "target_reciprocal_ranks": {
            str(int(tick)): [
                float(value)
                for value in (
                    1.0
                    / target_ranks[int(np.where(READ_TICKS == tick)[0][0])].astype(np.float64)
                )
            ]
            for tick in LONG_TICKS
        },
        "mean_white_coherence": mean_coherence,
    }


def load_incomplete_board(board_path: Path) -> tuple[Mapping[str, Any], str]:
    """Validate a canonical hardware-aborted receipt without inventing evidence."""

    board_path = board_path.resolve()
    board = finite_canonical_json(board_path)
    need(board.get("schema_id") == BOARD_SCHEMA, "board schema differs")
    need(board.get("status") == "INCOMPLETE", "board status is not INCOMPLETE")
    need(board.get("layout_profile_id") == LAYOUT_PROFILE, "layout profile differs")
    need(board.get("operator_profile_id") == OPERATOR_PROFILE, "operator profile differs")
    need(board.get("trace_schema_id") == TRACE_SCHEMA, "trace schema differs")
    error = board.get("error")
    need(isinstance(error, str) and bool(error.strip()), "incomplete board has no runtime error")
    assert isinstance(error, str)

    device = mapping(board.get("device"), "device receipt")
    need(device.get("type") == "cuda", "canonical device is not CUDA/ROCm")
    need(device.get("dtype") == "torch.float32", "canonical dtype is not torch.float32")
    need(isinstance(device.get("name"), str) and bool(device["name"]), "device name is missing")

    constants = mapping(board.get("constants"), "board constants")
    need(constants.get("targets") == TARGETS.tolist(), "targets differ")
    need(constants.get("distractors") == DISTRACTORS.tolist(), "distractors differ")
    need(constants.get("read_ticks") == READ_TICKS.tolist(), "read ticks differ")
    need(constants.get("long_horizon_ticks") == LONG_TICKS.tolist(), "long ticks differ")
    need(int(constants.get("warm_ticks", -1)) == WARM_TICKS, "warm tick count differs")
    need(int(constants.get("beating_ticks", -1)) == BEATING_TICKS, "beating tick count differs")
    need(int(constants.get("task_ticks", -1)) == TASK_TICKS, "task tick count differs")
    need(int(constants.get("evolution_steps", -1)) == EVOLUTION_STEPS, "evolution steps differ")
    close(float(constants.get("phi", -1.0)), PHI, "phi constant", atol=0.0, rtol=0.0)

    arms = mapping(board.get("arms"), "board arms")
    need(set(arms).issubset(EXPECTED_ARMS), "incomplete board has an unknown arm")
    source_hashes = mapping(board.get("source_sha256"), "source hashes")
    need(set(source_hashes) == EXPECTED_SOURCE_PATHS, "source hash path set differs")
    for relative in EXPECTED_SOURCE_PATHS:
        sha(source_hashes.get(relative), f"source hash {relative}")
    for relative in EXPECTED_SOURCE_PATHS - {
        "verification/verify_l29_phi_prismatic_heartbeat.py"
    }:
        path = (ROOT / relative).resolve()
        need(path.is_file() and path.is_relative_to(ROOT.resolve()), f"source path is missing or outside root: {relative}")
        need(sha256_file(path) == source_hashes[relative], f"source hash mismatch: {relative}")
    prereg_hash = source_hashes["designs/L29-PHI-PRISMATIC-HEARTBEAT-PREREG.md"]
    need(board.get("preregistration_sha256") == prereg_hash, "preregistration hash differs")

    trace = mapping(board.get("trace"), "trace receipt")
    trace_name = trace.get("path")
    need(
        isinstance(trace_name, str)
        and trace_name == Path(trace_name).name
        and trace_name == "l29-traces.npz",
        "trace path is not the canonical sibling basename",
    )
    need(trace.get("sha256") is None, "incomplete board must not claim a trace hash")
    return board, error


def load_and_verify(board_path: Path) -> tuple[Mapping[str, Any], dict[str, dict[str, Any]], str]:
    board_path = board_path.resolve()
    board = finite_canonical_json(board_path)
    need(board.get("schema_id") == BOARD_SCHEMA, "board schema differs")
    need(board.get("status") == "COMPLETE", "board status is not COMPLETE")
    need(board.get("layout_profile_id") == LAYOUT_PROFILE, "layout profile differs")
    need(board.get("operator_profile_id") == OPERATOR_PROFILE, "operator profile differs")
    need(board.get("trace_schema_id") == TRACE_SCHEMA, "trace schema differs")
    device = mapping(board.get("device"), "device receipt")
    need(device.get("type") == "cuda", "canonical device is not CUDA/ROCm")
    need(device.get("dtype") == "torch.float32", "canonical dtype is not torch.float32")

    constants = mapping(board.get("constants"), "board constants")
    need(constants.get("targets") == TARGETS.tolist(), "targets differ")
    need(constants.get("distractors") == DISTRACTORS.tolist(), "distractors differ")
    need(constants.get("read_ticks") == READ_TICKS.tolist(), "read ticks differ")
    need(constants.get("long_horizon_ticks") == LONG_TICKS.tolist(), "long ticks differ")
    need(int(constants.get("warm_ticks", -1)) == WARM_TICKS, "warm tick count differs")
    need(int(constants.get("beating_ticks", -1)) == BEATING_TICKS, "beating tick count differs")
    need(int(constants.get("task_ticks", -1)) == TASK_TICKS, "task tick count differs")
    need(int(constants.get("evolution_steps", -1)) == EVOLUTION_STEPS, "evolution steps differ")
    close(float(constants.get("phi", -1.0)), PHI, "phi constant", atol=0.0, rtol=0.0)

    source_hashes = mapping(board.get("source_sha256"), "source hashes")
    need(set(source_hashes) == EXPECTED_SOURCE_PATHS, "source hash path set differs")
    for relative in EXPECTED_SOURCE_PATHS:
        expected = sha(source_hashes.get(relative), f"source hash {relative}")
        path = (ROOT / relative).resolve()
        need(path.is_file() and path.is_relative_to(ROOT.resolve()), f"source path is missing or outside root: {relative}")
        need(sha256_file(path) == expected, f"source hash mismatch: {relative}")
    prereg_hash = source_hashes["designs/L29-PHI-PRISMATIC-HEARTBEAT-PREREG.md"]
    need(board.get("preregistration_sha256") == prereg_hash, "preregistration hash differs")

    trace = mapping(board.get("trace"), "trace receipt")
    trace_name = trace.get("path")
    need(isinstance(trace_name, str), "trace path is not text")
    assert isinstance(trace_name, str)
    need(trace_name == Path(trace_name).name and trace_name == "l29-traces.npz", "trace path is not the canonical sibling basename")
    trace_path = (board_path.parent / trace_name).resolve()
    need(trace_path.parent == board_path.parent and trace_path.is_file(), "trace is not a board sibling")
    trace_hash = sha(trace.get("sha256"), "trace hash")
    need(sha256_file(trace_path) == trace_hash, "trace hash mismatch")

    global_contract = {
        "schema_id": ((), np.dtype("<U48")),
        "targets": ((8,), np.dtype(np.int64)),
        "distractors": ((8,), np.dtype(np.int64)),
        "read_ticks": ((8,), np.dtype(np.int64)),
        "long_horizon_ticks": ((3,), np.dtype(np.int64)),
    }
    expected_contract = dict(global_contract)
    for slug, (banks, mode_count, _) in EXPECTED_ARMS.items():
        expected_contract.update(expected_array_contract(slug, banks, mode_count))
    try:
        with np.load(trace_path, allow_pickle=False) as archive:
            need(set(archive.files) == set(expected_contract), "trace array set differs")
            arrays = {name: archive[name] for name in archive.files}
    except (OSError, ValueError) as exc:
        raise L29VerificationError(f"cannot load finite trace NPZ: {exc}") from exc
    need(str(arrays["schema_id"].item()) == TRACE_SCHEMA, "trace schema payload differs")
    need(np.array_equal(arrays["targets"], TARGETS), "trace targets differ")
    need(np.array_equal(arrays["distractors"], DISTRACTORS), "trace distractors differ")
    need(np.array_equal(arrays["read_ticks"], READ_TICKS), "trace read ticks differ")
    need(np.array_equal(arrays["long_horizon_ticks"], LONG_TICKS), "trace long ticks differ")
    for name, (shape, dtype) in expected_contract.items():
        value = arrays[name]
        need(value.shape == shape, f"trace shape differs: {name}")
        if name != "schema_id":
            need(value.dtype == dtype, f"trace dtype differs: {name}")
            if np.issubdtype(value.dtype, np.number):
                need(bool(np.isfinite(value).all()), f"trace contains nonfinite values: {name}")

    arms = mapping(board.get("arms"), "board arms")
    need(set(arms) == set(EXPECTED_ARMS), "arm name set differs")
    metrics = {
        slug: verify_arm(slug, mapping(arms[slug], f"arm {slug}"), arrays)
        for slug in EXPECTED_ARMS
    }
    element_budgets = {
        int(mapping(mapping(arms[slug], slug).get("declaration"), f"{slug} declaration").get("evolution_element_updates", -1))
        for slug in EXPECTED_ARMS
    }
    need(len(element_budgets) == 1, "element-update budgets are unequal")
    return board, metrics, trace_hash


def scientific_verdict(metrics: Mapping[str, Mapping[str, Any]]) -> tuple[str, dict[str, bool]]:
    phi = metrics["phi-7"]
    geometric = metrics["geometric-4"]
    linear_time = metrics["linear-time-7"]
    linear_frequency = metrics["linear-frequency-7"]
    phi_mrr = float(phi["long_horizon_white_mrr"])
    better_nongeometric = max(
        float(linear_time["long_horizon_white_mrr"]),
        float(linear_frequency["long_horizon_white_mrr"]),
    )
    supports = {
        "tick8_accuracy_at_least_0_75": float(phi["tick8_distractor_accuracy"]) >= 0.75,
        "beats_geometric_4_by_1_05": phi_mrr >= 1.05 * float(geometric["long_horizon_white_mrr"]),
        "beats_linear_time_7_by_1_02": phi_mrr >= 1.02 * float(linear_time["long_horizon_white_mrr"]),
        "beats_linear_frequency_7_by_1_02": phi_mrr >= 1.02 * float(linear_frequency["long_horizon_white_mrr"]),
        "beats_best_phi_bank_by_1_02": phi_mrr >= 1.02 * float(phi["best_bank_long_horizon_mrr"]),
    }
    contradicts = {
        "loses_to_geometric_or_best_nongeometric_by_0_95": (
            phi_mrr <= 0.95 * float(geometric["long_horizon_white_mrr"])
            or phi_mrr <= 0.95 * better_nongeometric
        ),
        "loses_to_best_phi_bank_by_0_95": phi_mrr <= 0.95 * float(phi["best_bank_long_horizon_mrr"]),
        "beating_exceeds_both_nongeometric_by_1_25": (
            float(phi["beating_index"]) > 1.25 * float(linear_time["beating_index"])
            and float(phi["beating_index"]) > 1.25 * float(linear_frequency["beating_index"])
        ),
    }
    conditions = {**{f"supports.{key}": value for key, value in supports.items()}, **{f"contradicts.{key}": value for key, value in contradicts.items()}}
    if all(supports.values()):
        return "SUPPORTS", conditions
    if any(contradicts.values()):
        return "CONTRADICTS", conditions
    return "NULL", conditions


def mechanical_failures(metrics: Mapping[str, Mapping[str, Any]]) -> list[str]:
    failures: list[str] = []
    for slug, values in metrics.items():
        if float(values["first_heartbeat_relative_error"]) > 1.0e-5:
            failures.append(f"{slug}: first-heartbeat error exceeds 1e-5")
        if float(values["heartbeat_only_max_abs_d"]) > 1.0e-6:
            failures.append(f"{slug}: heartbeat-only differential leakage exceeds 1e-6")
        if float(values["maximum_input_energy_drift"]) > 5.0e-5:
            failures.append(f"{slug}: input energy drift exceeds 5e-5")
        if int(values["clamp_count"]) != 0:
            failures.append(f"{slug}: canonical state clamped")
        if float(values["warm_final_root_fraction"]) < 1.0e-4:
            failures.append(f"{slug}: warm root energy is below 1e-4 of total")
        if float(values["warm_final_crown_fraction"]) < 1.0e-4:
            failures.append(f"{slug}: warm crown energy is below 1e-4 of total")
        if float(values["beating_index"]) > 1.0:
            failures.append(f"{slug}: beating index exceeds 1.0")
    return failures


def report_text(verdict: str, payload: Mapping[str, Any]) -> str:
    metrics = mapping(payload.get("arms", {}), "verification arm metrics")
    lines = [
        "# L29 Phi-Prismatic Heartbeat Field — Verification Report",
        "",
        "## Behavior first",
        "",
        f"- Targets: `{TARGETS.tolist()}`",
        f"- Distractors: `{DISTRACTORS.tolist()}`",
    ]
    if metrics:
        lines.extend(
            [
                f"- `phi-7` tick-8 predictions: `{metrics['phi-7']['tick8_predictions']}`",
                "- Original-target reciprocal ranks at ticks 16/32/64:",
            ]
        )
        for slug in EXPECTED_ARMS:
            values = metrics[slug]
            rr = values["target_reciprocal_ranks"]
            lines.append(f"  - `{slug}`: tick 16 `{rr['16']}`, tick 32 `{rr['32']}`, tick 64 `{rr['64']}`")
        lines.append("- Beating index and white-vs-best-bank long-horizon MRR:")
        for slug in EXPECTED_ARMS:
            values = metrics[slug]
            lines.append(
                f"  - `{slug}`: beat `{values['beating_index']:.9g}`, white `{values['long_horizon_white_mrr']:.9g}`, best bank `{values['best_bank_long_horizon_mrr']:.9g}`"
            )
    elif verdict == "INCOMPLETE":
        lines.append(
            "- Behavior unavailable: the canonical GPU runtime aborted before any arm completed."
        )
    else:
        lines.append("- Behavior unavailable because evidence integrity failed before recomputation.")
    lines.extend(
        [
            "",
            f"## Verdict: {verdict}",
            "",
            "## Mechanical verification",
            "",
        ]
    )
    failures = payload.get("failures", [])
    if verdict == "INCOMPLETE":
        lines.append(f"- INCOMPLETE: {payload.get('incomplete_reason')}")
    elif failures:
        lines.extend(f"- FAIL: {failure}" for failure in failures)
    else:
        lines.append("- PASS: artifact integrity and all frozen mechanical gates passed.")
    conditions = payload.get("scientific_conditions", {})
    if conditions:
        lines.extend(["", "## Scientific conditions", ""])
        lines.extend(
            f"- {'PASS' if passed else 'MISS'}: `{name}`"
            for name, passed in conditions.items()
        )
    lines.extend(
        [
            "",
            "## Evidence inventory",
            "",
            f"- Board: `{payload.get('board_path')}`",
            f"- Board SHA-256: `{payload.get('board_sha256')}`",
            f"- Trace SHA-256: `{payload.get('trace_sha256')}`",
            "",
        ]
    )
    return "\n".join(lines)


def verify(
    board_path: Path = DEFAULT_BOARD,
    report_path: Path = DEFAULT_REPORT,
    json_path: Path = DEFAULT_JSON,
) -> tuple[str, dict[str, Any]]:
    board_path = board_path.resolve()
    metrics: dict[str, dict[str, Any]] = {}
    trace_hash: str | None = None
    failures: list[str] = []
    incomplete_reason: str | None = None
    try:
        board = finite_canonical_json(board_path)
        if board.get("status") == "INCOMPLETE":
            _, incomplete_reason = load_incomplete_board(board_path)
        else:
            _, metrics, trace_hash = load_and_verify(board_path)
            failures.extend(mechanical_failures(metrics))
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")

    conditions: dict[str, bool] = {}
    if failures:
        verdict = "FAIL"
    elif incomplete_reason is not None:
        verdict = "INCOMPLETE"
    else:
        verdict, conditions = scientific_verdict(metrics)
    payload: dict[str, Any] = {
        "schema_id": VERIFICATION_SCHEMA,
        "verdict": verdict,
        "targets": TARGETS.tolist(),
        "distractors": DISTRACTORS.tolist(),
        "read_ticks": READ_TICKS.tolist(),
        "long_horizon_ticks": LONG_TICKS.tolist(),
        "failures": failures,
        "scientific_conditions": conditions,
        "arms": metrics,
        "board_path": board_path.relative_to(ROOT).as_posix()
        if board_path.is_relative_to(ROOT)
        else str(board_path),
        "board_sha256": sha256_file(board_path) if board_path.is_file() else None,
        "trace_sha256": trace_hash,
        "incomplete_reason": incomplete_reason,
    }
    finite_tree(payload, "verification payload")
    atomic_write(json_path.resolve(), canonical_bytes(payload))
    atomic_write(report_path.resolve(), report_text(verdict, payload).encode("utf-8"))
    return verdict, payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()
    verdict, payload = verify(args.board, args.report, args.json)
    print(f"L29 verdict: {verdict}")
    if verdict == "INCOMPLETE":
        print(f"INCOMPLETE: {payload['incomplete_reason']}")
    elif payload["failures"]:
        for failure in payload["failures"]:
            print(f"FAIL: {failure}")
    else:
        for slug, values in payload["arms"].items():
            print(
                f"{slug}: tick8={values['tick8_distractor_accuracy']:.3f} "
                f"long_mrr={values['long_horizon_white_mrr']:.6f} "
                f"best_bank={values['best_bank_long_horizon_mrr']:.6f} "
                f"beat={values['beating_index']:.6f}"
            )
    print(args.report)
    print(args.json)
    return 1 if verdict == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
