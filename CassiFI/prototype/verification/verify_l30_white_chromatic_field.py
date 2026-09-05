"""Independently verify and classify the frozen L30 white-chromatic board."""
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

BOARD_SCHEMA = "cassi.l30.white-chromatic-board.v1"
TRACE_SCHEMA = "cassi.l30.white-chromatic-traces.v1"
VERIFICATION_SCHEMA = "cassi.l30.white-chromatic-verification.v1"
LAYOUT_PROFILE = "cassi.qi-white-chromatic-shared-coordinate.v1"
OPERATOR_PROFILE = "cassi.qi-white-chromatic-heartbeat.v1"
PROJECTION_PROFILE = "cassi.qi-white-chromatic-projection.v1"
PREREGISTRATION = ROOT / "designs" / "L30-WHITE-CHROMATIC-FIELD-PREREG.md"
MODULE = ROOT / "cassi_white_chromatic_field.py"
RUNNER = ROOT / "verification" / "run_l30_white_chromatic_field.py"
VERIFIER = ROOT / "verification" / "verify_l30_white_chromatic_field.py"
DEFAULT_BOARD = ROOT / "_diag" / "l30-white-chromatic-field" / "l30-board.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "l30-white-chromatic-field"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L30-WHITE-CHROMATIC-FIELD-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l30-verification.json"
TARGETS = np.asarray((0, 37, 74, 111, 148, 185, 222, 259), dtype=np.int64)
DISTRACTORS = (TARGETS + 97) % 260
READ_TICKS = np.asarray((0, 1, 2, 4, 8, 16, 32, 64), dtype=np.int64)
LONG_TICKS = np.asarray((16, 32, 64), dtype=np.int64)
PHI = (1.0 + math.sqrt(5.0)) / 2.0
CHANNELS, MODES, WIDTH, ALPHABET, BATCH = 7, 2048, 1024, 260, 8


class VerificationError(RuntimeError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def finite_tree(value: Any, label: str = "JSON") -> None:
    if value is None or isinstance(value, (bool, str, int)):
        return
    if isinstance(value, float):
        need(math.isfinite(value), f"{label} is nonfinite")
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            finite_tree(item, f"{label}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            need(isinstance(key, str), f"{label} has a non-string key")
            finite_tree(item, f"{label}.{key}")
        return
    raise VerificationError(f"{label} has unsupported JSON value")


def load_json(path: Path) -> Mapping[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    need(isinstance(value, Mapping), "board must be an object")
    finite_tree(value)
    need(raw == canonical_bytes(value), "board JSON is not canonical")
    return value


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    need(isinstance(value, Mapping), f"{label} must be an object")
    return value


def close(actual: float, expected: float, label: str, atol: float = 1e-6, rtol: float = 1e-5) -> None:
    need(math.isclose(float(actual), float(expected), abs_tol=atol, rel_tol=rtol), f"{label}: {actual!r} != {expected!r}")


def ranks(scores: np.ndarray, symbols: np.ndarray) -> np.ndarray:
    chosen = np.take_along_axis(scores, symbols[..., None], axis=-1)[..., 0]
    ids = np.arange(scores.shape[-1], dtype=np.int64)
    return 1 + (scores > chosen[..., None]).sum(axis=-1) + ((scores == chosen[..., None]) & (ids < symbols[..., None])).sum(axis=-1)


def coordinates_from_field(field: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    parts = field.reshape(CHANNELS, 9, MODES, field.shape[2])
    y = parts[:, 0, :WIDTH] + 1j * parts[:, 1, :WIDTH]
    yin = parts[:, 2, :WIDTH] + 1j * parts[:, 3, :WIDTH]
    vy = parts[:, 4, :WIDTH] + 1j * parts[:, 5, :WIDTH]
    vi = parts[:, 6, :WIDTH] + 1j * parts[:, 7, :WIDTH]
    return PHI * y + yin, y - PHI * yin, PHI * vy + vi, vy - PHI * vi


def recompute_readout(differential: np.ndarray, codebook: np.ndarray) -> dict[str, np.ndarray]:
    u = codebook[..., 0] + 1j * codebook[..., 1]
    h = np.exp(2j * np.pi * np.arange(CHANNELS) / CHANNELS)
    a = np.einsum("aw,swb->sba", np.conjugate(u), differential, optimize=True) / WIDTH
    compensated = np.conjugate(h)[:, None, None] * a
    global_a = compensated.sum(axis=0) / math.sqrt(CHANNELS)
    scores = (np.abs(global_a) ** 2).astype(np.float32)
    bank_scores = (np.abs(a) ** 2).astype(np.float32)
    rms = np.sqrt(np.mean(np.abs(differential) ** 2, axis=1)).astype(np.float32)
    active = rms >= 1.0e-8
    available = ((np.mean(np.abs(differential) ** 2, axis=(0, 1)) >= 1.0e-8) & (active.sum(axis=0) >= 2))
    symbols = np.argmax(scores, axis=1).astype(np.int64)
    contributions = compensated.transpose(1, 0, 2)
    winning = np.take_along_axis(
        contributions, symbols[:, None, None], axis=2
    )[:, :, 0]
    coherence = (np.abs(winning.sum(axis=1)) ** 2 / (active.sum(axis=0) * np.sum(np.abs(winning) ** 2, axis=1) + 1e-12)).astype(np.float32)
    return {"scores": scores, "bank_scores": bank_scores, "symbols": symbols, "available": available, "contributions": contributions, "differential_rms": rms, "bank_energy": np.mean(np.abs(differential) ** 2, axis=1).astype(np.float32), "active_bank_count": active.sum(axis=0).astype(np.int64), "white_coherence": coherence}


def recompute_projection(common: np.ndarray, differential: np.ndarray, side: int) -> dict[str, np.ndarray | int]:
    # Inputs are [width,batch] and [channels,width,batch].
    modes = common.shape[0]
    selected = np.floor(np.arange(side * side, dtype=np.float64) * modes / (side * side)).astype(np.int64)
    common_wave = np.fft.ifft2(common[selected].T.reshape(-1, side, side), axes=(-2, -1), norm="ortho")
    channel_wave = np.fft.ifft2(differential[:, selected].transpose(2, 0, 1).reshape(-1, CHANNELS, side, side), axes=(-2, -1), norm="ortho")
    common_intensity = (np.abs(common_wave) ** 2).astype(np.float32)
    channel_intensity = (np.real(channel_wave) ** 2).astype(np.float32)
    rgb_vectors = np.asarray(((1., 0., 0.), (1., .35, 0.), (1., 1., 0.), (0., 1., .2), (0., .25, 1.), (.25, 0., .75), (.65, 0., 1.)), dtype=np.float32)
    raw = common_intensity[:, None, :, :] + np.einsum("sc,bsxy->bcxy", rgb_vectors, channel_intensity)
    rgb = (raw / (1.0 + raw)).astype(np.float32)
    return {"rgb": rgb, "common_intensity": common_intensity, "channel_intensity": channel_intensity.transpose(1, 0, 2, 3), "side": side}


def verify_board(board_path: Path, *, allow_smoke_device: bool = False) -> tuple[str, dict[str, Any]]:
    board = load_json(board_path)
    need(board.get("schema_id") == BOARD_SCHEMA, "board schema mismatch")
    need(board.get("status") == "COMPLETE", "board is not COMPLETE")
    need(board.get("layout_profile_id") == LAYOUT_PROFILE, "layout identity mismatch")
    need(board.get("operator_profile_id") == OPERATOR_PROFILE, "operator identity mismatch")
    need(board.get("projection_profile_id") == PROJECTION_PROFILE, "projection identity mismatch")
    need(board.get("trace_schema_id") == TRACE_SCHEMA, "trace schema mismatch")
    source = mapping(board.get("source_sha256"), "source_sha256")
    expected = {"designs/L30-WHITE-CHROMATIC-FIELD-PREREG.md", "cassi_white_chromatic_field.py", "verification/run_l30_white_chromatic_field.py", "verification/verify_l30_white_chromatic_field.py"}
    need(set(source) == expected, "source hash path set mismatch")
    for rel in expected:
        path = (ROOT / rel).resolve()
        need(path.is_file(), f"source path missing: {rel}")
        need(source[rel] == sha256_file(path), f"source hash mismatch: {rel}")
    need(board.get("preregistration_sha256") == source["designs/L30-WHITE-CHROMATIC-FIELD-PREREG.md"], "preregistration hash mismatch")
    constants = mapping(board.get("constants"), "constants")
    for key, expected_value in (("channels", 7), ("mode_count", 2048), ("active_modes", 1024), ("alphabet_size", 260), ("batch_size", 8), ("evolution_steps", 8), ("task_ticks", 65), ("long_ticks", 128)):
        need(constants.get(key) == expected_value, f"constant {key} mismatch")
    need(constants.get("targets") == TARGETS.tolist(), "targets mismatch")
    need(constants.get("distractors") == DISTRACTORS.tolist(), "distractors mismatch")
    need(constants.get("read_ticks") == READ_TICKS.tolist(), "read ticks mismatch")
    canonical_arm = mapping(mapping(board.get("arms"), "arms").get("canonical"), "canonical arm")
    declaration = mapping(canonical_arm.get("declaration"), "canonical declaration")
    expected_config = {
        "mode_count": 2048,
        "alphabet_size": 260,
        "dt": 0.05,
        "base_omega2": 1.0,
        "base_damping": 0.2,
        "nonlinear_gain": 0.002,
        "coupling_omega2": 0.05,
        "epsilon_tau": 0.05,
        "heartbeat_carrier_energy": 0.5,
        "field_energy_budget": 1.0,
        "readout_energy_floor": 1.0e-8,
        "max_mode_amplitude": 8.0,
        "max_mean_energy": 4.0,
    }
    need(declaration.get("config") == expected_config, "canonical configuration mismatch")
    for key in ("config_fingerprint", "codebook_fingerprint"):
        value = declaration.get(key)
        need(isinstance(value, str) and len(value) == 64, f"{key} missing")
    device = mapping(board.get("device"), "device")
    if not allow_smoke_device:
        need(device.get("dtype") == "float32", "canonical dtype mismatch")
        need(device.get("type") == "cuda", "canonical device must be CUDA/ROCm")
        need(isinstance(device.get("hip_version"), str) and device["hip_version"], "canonical ROCm identity missing")
    trace = mapping(board.get("trace"), "trace")
    trace_name = trace.get("path")
    if not isinstance(trace_name, str) or Path(trace_name).name != trace_name or trace_name != "l30-traces.npz":
        raise VerificationError("trace must be sibling basename")
    trace_path = board_path.parent / trace_name
    need(trace_path.is_file(), "trace artifact missing")
    need(trace.get("sha256") == sha256_file(trace_path), "trace hash mismatch")
    projection = mapping(board.get("projection"), "projection")
    png_name = projection.get("path")
    if not isinstance(png_name, str) or Path(png_name).name != png_name or png_name != "l30-projection.png":
        raise VerificationError("projection must be sibling basename")
    png_path = board_path.parent / png_name
    need(png_path.is_file() and projection.get("sha256") == sha256_file(png_path), "projection hash mismatch")
    with np.load(trace_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    canonical_controller = QiFieldController(QiFieldConfig(scale_count=1, mode_count=MODES, alphabet_size=ALPHABET, primes=(4093,), settle_steps=1))
    expected_codebook = canonical_controller.codebook(0, dtype=torch.float32).cpu().numpy()
    need(arrays["codebook"].shape == expected_codebook.shape and np.allclose(arrays["codebook"], expected_codebook, atol=2e-6, rtol=1e-6), "immutable codebook mismatch")
    need("schema_id" in arrays and str(arrays["schema_id"].item()) == TRACE_SCHEMA, "trace schema payload mismatch")
    for name, value in arrays.items():
        if np.issubdtype(value.dtype, np.number):
            need(bool(np.isfinite(value).all()), f"trace contains nonfinite values: {name}")
    required = {"targets": (8,), "distractors": (8,), "read_ticks": (8,), "codebook": (260, 1024, 2), "pre_target_d": (7, 1024, 8), "pre_readout_symbols": (8,), "pre_readout_state_before_field": (7, 9 * MODES, 8), "pre_readout_state_after_field": (7, 9 * MODES, 8), "zero_post_field": (7, 9 * MODES, 1), "pre_target_clamp_count": (), "zero_clamp_count": (), "first_heartbeat_dynamic_energy": (7, 1), "first_heartbeat_carrier_energy": (1,), "task_read_d": (8, 7, 1024, 8), "task_read_c": (8, 7, 1024, 8), "task_read_scores": (8, 8, 260), "task_read_bank_scores": (8, 7, 8, 260), "task_read_symbols": (8, 8), "task_energy": (65, 7, 8), "task_input_energy_drift": (65, 8), "task_clamp_count": (65,), "blank_energy": (128, 7), "stress_energy": (128, 7), "counter_projection_state_field": (7, 9 * MODES, 8), "projection_state_before_field": (7, 9 * MODES, 8), "projection_state_after_first_field": (7, 9 * MODES, 8), "projection_state_after_second_field": (7, 9 * MODES, 8)}
    for key, shape in required.items():
        need(key in arrays and arrays[key].shape == shape, f"trace shape mismatch: {key}")
    for field_name in ("zero_post_field", "first_heartbeat_post_field", "blank_final_field", "stress_final_field", "pre_readout_state_before_field", "pre_readout_state_after_field", "counter_projection_state_field", "projection_state_before_field", "projection_state_after_first_field", "projection_state_after_second_field"):
        if field_name in arrays:
            field = arrays[field_name]
            need(field.ndim == 3 and field.shape[:2] == (CHANNELS, 9 * MODES), f"state shape mismatch: {field_name}")
            packed = field.reshape(CHANNELS, 9, MODES, field.shape[2])
            need(int(np.count_nonzero(packed[:, :, WIDTH:, :])) == 0, f"inactive modes changed: {field_name}")
    need(np.array_equal(arrays["targets"], TARGETS) and np.array_equal(arrays["distractors"], DISTRACTORS) and np.array_equal(arrays["read_ticks"], READ_TICKS), "trace schedule mismatch")
    recomputed = [recompute_readout(arrays["task_read_d"][i], arrays["codebook"]) for i in range(8)]
    for i, expected_read in enumerate(recomputed):
        for name in ("scores", "bank_scores", "symbols", "available", "differential_rms", "bank_energy", "active_bank_count", "white_coherence"):
            actual = arrays.get(f"task_read_{name}")
            if actual is None:
                continue
            need(actual[i].shape == expected_read[name].shape, f"readout shape mismatch: {name}")
            need(np.allclose(actual[i], expected_read[name], atol=3e-5, rtol=2e-4), f"readout mismatch: {name} slot {i}")
    pre_recomputed = recompute_readout(arrays["pre_target_d"], arrays["codebook"])
    need(np.array_equal(arrays["pre_readout_symbols"], pre_recomputed["symbols"]), "pre-evolution readout mismatch")
    pre_accuracy = float(np.mean(pre_recomputed["symbols"] == TARGETS))
    target_ranks = np.stack([ranks(arrays["task_read_scores"][i], TARGETS) for i in range(8)])
    distractor_ranks = np.stack([ranks(arrays["task_read_scores"][i], DISTRACTORS) for i in range(8)])
    need(np.array_equal(arrays["task_target_ranks"], target_ranks), "target ranks mismatch")
    need(np.array_equal(arrays["task_distractor_ranks"], distractor_ranks), "distractor ranks mismatch")
    metrics = mapping(canonical_arm.get("metrics"), "canonical metrics")
    first_dynamic = arrays["first_heartbeat_dynamic_energy"]
    first_total = float(np.mean(first_dynamic))
    first_spread = float(np.ptp(first_dynamic, axis=0).max() / max(float(np.mean(first_dynamic)), 1e-12))
    values = {
        "exact_pre_target_accuracy": pre_accuracy,
        "tick0_target_accuracy": float(np.mean(arrays["task_read_symbols"][0] == TARGETS)),
        "target_mrr_pre_distractor": float(np.mean(1.0 / target_ranks[[1, 2, 3]])),
        "tick8_distractor_accuracy": float(np.mean(arrays["task_read_symbols"][4] == DISTRACTORS)),
        "distractor_mrr_long": float(np.mean(1.0 / distractor_ranks[[5, 6, 7]])),
        "original_target_mrr_long": float(np.mean(1.0 / target_ranks[[5, 6, 7]])),
        "tick0_white_coherence": float(np.mean(arrays["task_read_coherence"][0])),
        "blank_max_abs_d": float(np.max(arrays["blank_max_abs_d"])),
        "stress_clamp_count": int(np.sum(arrays["stress_clamp_count"])),
        "maximum_input_energy_drift": float(max(np.max(np.abs(arrays["task_input_energy_drift"])), np.max(np.abs(arrays["zero_drift"])), np.max(np.abs(arrays["pre_target_drift"])))),
        "clamp_count": int(np.sum(arrays["task_clamp_count"]) + np.sum(arrays["blank_clamp_count"]) + np.sum(arrays["stress_clamp_count"]) + int(arrays["zero_clamp_count"]) + int(arrays["pre_target_clamp_count"])),
        "maximum_total_mean_dynamic_energy": float(max(np.mean(arrays["task_energy"], axis=1).max(), np.mean(arrays["blank_energy"], axis=1).max(), np.mean(arrays["stress_energy"], axis=1).max())),
        "first_heartbeat_max_abs_d": float(np.max(np.abs(arrays["first_heartbeat_post_d"]))),
        "first_heartbeat_total_energy": first_total,
        "first_heartbeat_channel_energy_spread": first_spread,
        "first_heartbeat_carrier_energy": float(np.mean(arrays["first_heartbeat_carrier_energy"])),
    }
    for name, value in values.items():
        if name in metrics:
            close(float(metrics[name]), value, f"metric consistency: {name}", atol=3e-5, rtol=3e-4)
    need(float(metrics.get("zero_input_max_abs", 1.0)) == 0.0, "zero input changed state")
    need("projection_state_before_field" in arrays and arrays["projection_state_before_field"].shape[0:2] == (CHANNELS, 9 * MODES), "projection state missing")
    common_channels, differential, _, _ = coordinates_from_field(arrays["projection_state_before_field"])
    projection_expected = recompute_projection(common_channels.sum(axis=0) / math.sqrt(CHANNELS), differential, int(arrays["projection_side"].item()))
    need(int(arrays["projection_side"].item()) == 32, "canonical projection side mismatch")
    for name in ("rgb", "common_intensity", "channel_intensity"):
        need(f"projection_{name}" in arrays and np.allclose(arrays[f"projection_{name}"], projection_expected[name], atol=3e-5, rtol=3e-4), f"projection recomputation mismatch: {name}")
    counter_common, counter_differential, _, _ = coordinates_from_field(arrays["counter_projection_state_field"])
    counter_expected = recompute_projection(counter_common.sum(axis=0) / math.sqrt(CHANNELS), counter_differential, 32)
    need(np.allclose(arrays["counter_projection_rgb"], counter_expected["rgb"], atol=3e-5, rtol=3e-4), "counterfactual projection recomputation mismatch")
    need(np.allclose(arrays["projection_again_rgb"], projection_expected["rgb"], atol=3e-5, rtol=3e-4), "repeated projection recomputation mismatch")
    need(abs(float(metrics.get("first_heartbeat_carrier_energy", -1.0)) - .5) / .5 <= 1e-5, "first heartbeat carrier gate")
    need(abs(float(metrics.get("first_heartbeat_total_energy", -1.0)) - .5) <= 1e-5, "first heartbeat total-energy gate")
    need(float(metrics.get("first_heartbeat_channel_energy_spread", 1.0)) <= 1e-5, "first heartbeat channel spread gate")
    need(values["first_heartbeat_max_abs_d"] <= 1e-6, "first heartbeat differential leakage gate")
    need(values["maximum_input_energy_drift"] <= 5e-5, "input energy drift gate")
    need(values["clamp_count"] == 0 and values["stress_clamp_count"] == 0, "component clamp or safety rescale occurred")
    need(values["maximum_total_mean_dynamic_energy"] <= 1.05, "energy budget gate")
    for key in ("projection_rgb", "projection_again_rgb", "counter_projection_rgb"):
        need(key in arrays and bool(np.isfinite(arrays[key]).all()) and float(arrays[key].min()) >= 0 and float(arrays[key].max()) <= 1, f"projection bounds: {key}")
    need(np.array_equal(arrays["projection_rgb"], arrays["projection_again_rgb"]), "repeated projection is not bitwise identical")
    need(float(np.std(arrays["projection_rgb"])) >= 1e-4, "projection has insufficient RGB variation")
    need(float(np.sqrt(np.mean((arrays["projection_rgb"] - arrays["counter_projection_rgb"]) ** 2))) > 1e-4, "counterfactual projection is indistinguishable")
    if "projection_state_before_field" in arrays:
        need(np.array_equal(arrays["projection_state_before_field"], arrays["projection_state_after_first_field"]) and np.array_equal(arrays["projection_state_before_field"], arrays["projection_state_after_second_field"]), "projection mutated state")
    need(np.array_equal(arrays["pre_readout_state_before_field"], arrays["pre_readout_state_after_field"]), "readout mutated state")
    functional = {"exact_pre_target_accuracy": float(metrics.get("exact_pre_target_accuracy", 0.0)) == 1.0, "tick0_target_accuracy": values["tick0_target_accuracy"] >= .875, "target_mrr_pre_distractor": values["target_mrr_pre_distractor"] >= .75, "tick8_distractor_accuracy": values["tick8_distractor_accuracy"] >= .75, "distractor_mrr_long": values["distractor_mrr_long"] >= .25, "original_target_mrr_long": values["original_target_mrr_long"] >= .05, "tick0_white_coherence": values["tick0_white_coherence"] >= .90, "blank_max_abs_d": values["blank_max_abs_d"] <= 1e-6, "stress_path": values["stress_clamp_count"] == 0 and values["maximum_total_mean_dynamic_energy"] <= 1.05}
    verdict = "ADOPT" if all(functional.values()) else "REJECT"
    return verdict, {"schema_id": VERIFICATION_SCHEMA, "verdict": verdict, "metrics": values, "functional_conditions": functional, "failures": []}


def report_text(verdict: str, payload: Mapping[str, Any]) -> str:
    lines = ["# L30 White-Chromatic Field — Verification", "", f"**Verdict: `{verdict}`**", ""]
    lines.append({"ADOPT": "All frozen mechanical and functional gates passed.", "REJECT": "Mechanics passed; one or more preregistered functional conditions failed.", "INCOMPLETE": "The canonical board was interrupted or unavailable before complete verification.", "FAIL": "Evidence integrity or a frozen mechanical gate failed."}[verdict])
    if payload.get("failures"):
        lines.extend(["", "## Failures", *[f"- {item}" for item in payload["failures"]]])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--allow-smoke-device", action="store_true")
    args = parser.parse_args()
    board_path = args.board.resolve()
    if not board_path.is_file():
        verdict, payload = "INCOMPLETE", {"schema_id": VERIFICATION_SCHEMA, "verdict": "INCOMPLETE", "metrics": {}, "functional_conditions": {}, "failures": ["board artifact is unavailable"]}
    else:
        try:
            verdict, payload = verify_board(board_path, allow_smoke_device=args.allow_smoke_device)
        except Exception as exc:
            verdict, payload = "FAIL", {"schema_id": VERIFICATION_SCHEMA, "verdict": "FAIL", "metrics": {}, "functional_conditions": {}, "failures": [f"{type(exc).__name__}: {exc}"]}
    payload = dict(payload)
    payload.update({"board_path": board_path.relative_to(ROOT).as_posix() if board_path.is_relative_to(ROOT) else str(board_path), "board_sha256": sha256_file(board_path) if board_path.is_file() else None})
    atomic_write(args.json.resolve(), canonical_bytes(payload))
    atomic_write(args.report.resolve(), report_text(verdict, payload).encode("utf-8"))
    print(verdict)
    print(args.report.resolve())
    print(args.json.resolve())
    return 0 if verdict == "ADOPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
