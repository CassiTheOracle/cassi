"""Run the L47 absorbing harmonic-age shift causal board."""
from __future__ import annotations

import argparse
import hashlib
import io
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
from cassi_absorbing_harmonic_age_field import (
    ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID,
    ABSORBING_HARMONIC_AGE_OPERATOR_PROFILE_ID,
    ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID,
    AbsorbingHarmonicAgeFieldConfig,
    AbsorbingHarmonicAgeFieldController,
)
from cassi_harmonic_age_field import HarmonicAgeFieldController, HarmonicAgeFieldConfig
from cassi_qi_field import QiFieldState
from cassi_white_chromatic_field import WhiteChromaticFieldController

BOARD_SCHEMA = "cassi.l47.absorbing-harmonic-age-shift-board.v1"
TRACE_SCHEMA = "cassi.l47.absorbing-harmonic-age-shift-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L47-ABSORBING-HARMONIC-AGE-SHIFT-PREREG.md"
RUNNER = ROOT / "verification" / "run_l47_absorbing_harmonic_age_shift.py"
VERIFIER = ROOT / "verification" / "verify_l47_absorbing_harmonic_age_shift.py"
OUTPUT_DIR = ROOT / "_diag" / "l47-absorbing-harmonic-age-shift"
BOARD_NAME = "l47-board.json"
TRACE_NAME = "l47-traces.npz"
MODE_COUNT = 2048
SMOKE_MODE_COUNT = 520
CHANNELS = 7
BATCH_SIZE = 8
ALPHABET_SIZE = 260
EVOLUTION_STEPS = 8
READOUT_FLOOR = 1.0e-8
MAX_MODE_AMPLITUDE = 8.0
MAX_EPSILON = 4096.0
BASE_SYMBOLS = np.asarray((0, 37, 74, 111, 148, 185, 222, 259), dtype=np.int64)
AGE_OFFSETS = {0: 0, 1: 53, 2: 97, 3: 149, 6: 223}
DEPOSIT_OFFSET = 181
AGE_AMPLITUDES = {0: 0.08, 1: 0.07, 2: 0.06, 3: 0.05, 6: 0.09}
AGE_HARMONICS = (1, 2, 3, 4, 5, 6, 0)
ENERGY_DENOMINATOR = 1.0 + ((1.0 + np.sqrt(5.0)) / 2.0) ** 2

SOURCE_PATHS = (
    PREREGISTRATION,
    ROOT / "cassi_qi_profile.py",
    ROOT / "cassi_qi_field.py",
    ROOT / "cassi_prismatic_field.py",
    ROOT / "cassi_white_chromatic_field.py",
    ROOT / "cassi_cyclic_chromatic_field.py",
    ROOT / "cassi_harmonic_age_field.py",
    ROOT / "cassi_absorbing_harmonic_age_field.py",
    RUNNER,
    VERIFIER,
)


class L47RunnerError(RuntimeError):
    """The L47 board could not be completed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tensor_sha256(value: Any) -> str:
    array = np.ascontiguousarray(l30.cpu(value))
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()




def _native(controller: Any, state: QiFieldState) -> tuple[torch.Tensor, ...]:
    return controller._active_coordinates(state)


def _harmonics(controller: Any, state: QiFieldState, differential: torch.Tensor) -> torch.Tensor:
    phase = controller._constants(state)["channel_phase"]
    harmonics = torch.arange(CHANNELS, device=state.field.device, dtype=torch.int64)
    basis = phase.conj()[None, :].pow(harmonics[:, None]) / np.sqrt(CHANNELS)
    return torch.einsum("kj,jwb->kwb", basis, differential)


def _coefficients(controller: Any, state: QiFieldState, harmonic_d: torch.Tensor) -> torch.Tensor:
    parts = controller.codebook(0, device=state.field.device, dtype=state.field.dtype)
    codebook = torch.complex(parts[..., 0], parts[..., 1])
    collapsed = harmonic_d.index_select(
        0, torch.as_tensor(AGE_HARMONICS, device=state.field.device, dtype=torch.int64)
    )
    return (
        torch.einsum(
            "aw,hwb->hba", codebook.conj(), collapsed
        )
        .div_(float(controller.config.wave_mode_count))
        .permute(1, 0, 2)
    )


def _active_capture(controller: Any, state: QiFieldState) -> dict[str, np.ndarray]:
    common, differential, common_velocity, differential_velocity = _native(controller, state)
    harmonic_d = _harmonics(controller, state, differential)
    harmonic_vd = _harmonics(controller, state, differential_velocity)
    coefficients = _coefficients(controller, state, harmonic_d)
    readout = controller.white_readout(state)
    packed = state.field.reshape(controller.config.bank_count, 9, controller.config.mode_count, state.batch_size)
    width = controller.config.wave_mode_count
    active = packed[:, :8, :width]
    tail = packed[:, :, width:]
    return {
        "field": l30.cpu(state.field),
        "c": l30.cpu(common),
        "d": l30.cpu(differential),
        "vc": l30.cpu(common_velocity),
        "vd": l30.cpu(differential_velocity),
        "epsilon": l30.cpu(packed[:, 8, :width]),
        "inactive_tail": l30.cpu(tail),
        "harmonic_d": l30.cpu(harmonic_d),
        "harmonic_vd": l30.cpu(harmonic_vd),
        "coefficients": l30.cpu(coefficients),
        "dynamic_energy": l30.cpu(controller._dynamic_energy_unchecked(state)),
        "maximum_amplitude": np.asarray(float(active.abs().max().item()), dtype=np.float32),
        "age_scores": l30.cpu(readout.age_scores),
        "age_symbols": l30.cpu(readout.age_symbols),
        "age_available": l30.cpu(readout.age_available).astype(bool),
        "readout_symbols": l30.cpu(readout.symbols).reshape(-1),
        "readout_available": l30.cpu(readout.available).reshape(-1).astype(bool),
        "readout_scores": l30.cpu(readout.scores),
    }


def _merge(prefix: str, capture: dict[str, np.ndarray], arrays: dict[str, np.ndarray]) -> None:
    for key, value in capture.items():
        arrays[f"{prefix}_{key}"] = value
def _analytic_state(
    controller: AbsorbingHarmonicAgeFieldController,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[QiFieldState, dict[int, torch.Tensor]]:
    state = controller.new_state(batch_size=BATCH_SIZE, device=device, dtype=dtype)
    width = controller.config.wave_mode_count
    symbols: dict[int, torch.Tensor] = {
        age: torch.as_tensor(
            (BASE_SYMBOLS + offset) % ALPHABET_SIZE,
            device=device,
            dtype=torch.int64,
        )
        for age, offset in AGE_OFFSETS.items()
    }
    parts = controller.codebook(0, device=device, dtype=dtype)
    codebook = torch.complex(parts[..., 0], parts[..., 1])
    complex_dtype = torch.complex128 if dtype is torch.float64 else torch.complex64
    z_d = torch.zeros(CHANNELS, width, BATCH_SIZE, device=device, dtype=complex_dtype)
    z_vd = torch.zeros_like(z_d)
    for age, amplitude in AGE_AMPLITUDES.items():
        harmonic = AGE_HARMONICS[age]
        vector = codebook.index_select(0, symbols[age]).transpose(0, 1)
        z_d[harmonic] = float(amplitude) * vector
        z_vd[harmonic] = 0.5j * float(amplitude) * vector
    phase = controller._constants(state)["channel_phase"]
    inverse_basis = phase[None, :].pow(
        torch.arange(CHANNELS, device=device, dtype=torch.int64)[:, None]
    )
    differential = torch.einsum("jk,kwb->jwb", inverse_basis, z_d) / np.sqrt(CHANNELS)
    differential_velocity = torch.einsum("jk,kwb->jwb", inverse_basis, z_vd) / np.sqrt(CHANNELS)
    white = torch.full((CHANNELS,), 1.0 / np.sqrt(CHANNELS), device=device, dtype=dtype)
    common = (white[:, None, None] * torch.as_tensor(0.02 + 0.0j, device=device, dtype=complex_dtype)).expand(CHANNELS, width, BATCH_SIZE).clone()
    common_velocity = (white[:, None, None] * torch.as_tensor(0.0 + 0.01j, device=device, dtype=complex_dtype)).expand(CHANNELS, width, BATCH_SIZE).clone()
    epsilon = torch.arange(1, CHANNELS + 1, device=device, dtype=dtype).reshape(CHANNELS, 1, 1).expand(CHANNELS, width, BATCH_SIZE) * (1.0e-4 / CHANNELS)
    state = controller._replace_coordinates(state, common, differential, common_velocity, differential_velocity, epsilon=epsilon)
    return state, symbols


def _direct_write(controller: Any, state: QiFieldState, symbols: torch.Tensor, *, absorbing: bool) -> tuple[QiFieldState, torch.Tensor, int]:
    if absorbing:
        shifted = controller._absorb_harmonics_unchecked(state)
    else:
        shifted = controller._lift_harmonics_unchecked(state)
    result, drift, clamp_count = (
        WhiteChromaticFieldController._modulate_unchecked(
            controller, shifted, symbols, 1.0
        )
    )
    return result, drift, int(clamp_count)


def _serialize(controller: Any, state: QiFieldState) -> bytes:
    payload = {
        "field": state.field.detach().cpu(),
        "config": controller.config.to_dict(),
        "config_fingerprint": getattr(controller, "config_fingerprint", ""),
        "layout_profile_id": ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID,
        "operator_profile_id": ABSORBING_HARMONIC_AGE_OPERATOR_PROFILE_ID,
        "projection_profile_id": ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID,
    }
    stream = io.BytesIO()
    torch.save(payload, stream)
    return stream.getvalue()


def _restore(payload: bytes, controller: AbsorbingHarmonicAgeFieldController, *, device: torch.device, dtype: torch.dtype) -> QiFieldState:
    loaded = torch.load(io.BytesIO(payload), map_location=device, weights_only=True)
    expected = {
        "layout_profile_id": ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID,
        "operator_profile_id": ABSORBING_HARMONIC_AGE_OPERATOR_PROFILE_ID,
        "projection_profile_id": ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID,
    }
    if loaded.get("config") != controller.config.to_dict() or loaded.get("config_fingerprint") != getattr(controller, "config_fingerprint", "") or any(loaded.get(k) != v for k, v in expected.items()):
        raise L47RunnerError("persistence profile/configuration identity mismatch")
    field = loaded.get("field")
    if not torch.is_tensor(field):
        raise L47RunnerError("persistence payload has no field tensor")
    restored = QiFieldState(field.to(device=device, dtype=dtype).clone())
    controller._validate_state(restored)
    return restored


def _run_operator_and_write(
    state: QiFieldState,
    symbols: torch.Tensor,
    harmonic: HarmonicAgeFieldController,
    absorbing: AbsorbingHarmonicAgeFieldController,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    arrays: dict[str, np.ndarray] = {}
    pre = _active_capture(absorbing, state)
    identity = state.clone()
    shifted = absorbing.absorb_harmonics(state)
    post = _active_capture(absorbing, shifted)
    _merge("operator_pre", pre, arrays)
    _merge("operator_identity", _active_capture(absorbing, identity), arrays)
    _merge("operator_post", post, arrays)
    pre_harmonic_d = torch.as_tensor(pre["harmonic_d"], device=state.field.device)
    pre_harmonic_vd = torch.as_tensor(pre["harmonic_vd"], device=state.field.device)
    discarded = pre_harmonic_d[0].abs().square() + pre_harmonic_vd[0].abs().square()
    predicted = discarded.mean(dim=0) / (
        CHANNELS * ENERGY_DENOMINATOR
    )
    arrays["operator_predicted_removed_energy"] = l30.cpu(predicted)
    arrays["operator_removed_energy"] = l30.cpu(
        (
            torch.as_tensor(pre["dynamic_energy"], device=state.field.device)
            - torch.as_tensor(post["dynamic_energy"], device=state.field.device)
        ).mean(dim=0)
    )
    write: dict[str, np.ndarray] = {}
    for name, controller, use_absorbing in (("cyclic_write", harmonic, False), ("absorbing_write", absorbing, True)):
        before = _active_capture(controller, state.clone())
        post_shift = absorbing._absorb_harmonics_unchecked(state.clone()) if use_absorbing else harmonic._lift_harmonics_unchecked(state.clone())
        post_shift_capture = _active_capture(controller, post_shift)
        post, drift, clamp = _direct_write(controller, state.clone(), symbols, absorbing=use_absorbing)
        post_capture = _active_capture(controller, post)
        _merge(f"{name}_pre", before, arrays)
        _merge(f"{name}_post_shift", post_shift_capture, arrays)
        _merge(f"{name}_post", post_capture, arrays)
        arrays[f"{name}_drift"] = l30.cpu(drift).reshape(-1)
        arrays[f"{name}_clamp_count"] = np.asarray(clamp, dtype=np.int64)
    write["done"] = np.asarray(True)
    return arrays, write


def _run_stress(
    source: QiFieldState,
    symbols_for: Sequence[torch.Tensor],
    harmonic: HarmonicAgeFieldController,
    absorbing: AbsorbingHarmonicAgeFieldController,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {
        "stress_symbols": np.stack([l30.cpu(s) for s in symbols_for])
    }
    branches: dict[str, tuple[Any, bool]] = {
        "cyclic": (harmonic, False),
        "absorbing": (absorbing, True),
    }
    arrays["stress_initial_field"] = l30.cpu(source.field)
    arrays["stress_initial_field_sha256"] = np.asarray(
        tensor_sha256(source.field), dtype="<U64"
    )
    captures: dict[str, list[dict[str, np.ndarray]]] = {
        f"stress_{name}_{stage}": []
        for name in branches
        for stage in ("post_heartbeat", "post_shift", "post_write")
    }
    receipt_names = (
        "source_energy_before", "source_energy_after",
        "total_energy_before", "total_energy_after",
        "injected_energy", "dissipated_energy",
    )
    receipts: dict[str, list[np.ndarray]] = {
        f"stress_{name}_heartbeat_{field}": []
        for name in branches
        for field in receipt_names
    }
    heartbeat_clamps = {name: [] for name in branches}
    drifts = {name: [] for name in branches}
    clamps = {name: [] for name in branches}
    hashes = {name: [] for name in branches}
    states = {name: source.clone() for name in branches}
    resumed: QiFieldState | None = None
    resumed_controller: AbsorbingHarmonicAgeFieldController | None = None
    resume_hashes: list[str] = []
    checkpoint_payload = b""
    for index, symbols in enumerate(symbols_for):
        for name, (controller, use_absorbing) in branches.items():
            current, receipt = controller.heartbeat(states[name])
            capture = _active_capture(controller, current)
            capture.pop("field")
            captures[f"stress_{name}_post_heartbeat"].append(capture)
            for field in receipt_names:
                receipts[f"stress_{name}_heartbeat_{field}"].append(
                    l30.cpu(getattr(receipt, field)).reshape(-1)
                )
            heartbeat_clamps[name].append(int(receipt.clamp_count))
            shifted = (
                absorbing._absorb_harmonics_unchecked(current)
                if use_absorbing
                else harmonic._lift_harmonics_unchecked(current)
            )
            capture = _active_capture(controller, shifted)
            captures[f"stress_{name}_post_shift"].append(capture)
            written, drift, clamp = _direct_write(
                controller, current, symbols, absorbing=use_absorbing
            )
            capture = _active_capture(controller, written)
            captures[f"stress_{name}_post_write"].append(capture)
            states[name] = written
            drifts[name].append(l30.cpu(drift).reshape(-1))
            clamps[name].append(clamp + int(receipt.clamp_count))
            hashes[name].append(tensor_sha256(written.field))
            if name == "absorbing" and index == 63:
                checkpoint_payload = _serialize(absorbing, written)
                resumed_controller = AbsorbingHarmonicAgeFieldController(
                    AbsorbingHarmonicAgeFieldConfig(mode_count=absorbing.config.mode_count)
                )
                resumed = _restore(
                    checkpoint_payload,
                    resumed_controller,
                    device=device,
                    dtype=dtype,
                )
        if index >= 64:
            if resumed is None or resumed_controller is None:
                raise L47RunnerError("resume state missing after write 63")
            resumed, _ = resumed_controller.heartbeat(resumed)
            resumed, _, _ = _direct_write(
                resumed_controller, resumed, symbols, absorbing=True
            )
            resume_hashes.append(tensor_sha256(resumed.field))
            if not torch.equal(resumed.field, states["absorbing"].field):
                raise L47RunnerError(f"save/reload divergence after write {index}")
    for key, values in captures.items():
        for field in values[0]:
            arrays[f"{key}_{field}"] = np.stack([value[field] for value in values])
    for name in branches:
        for field in receipt_names:
            arrays[f"stress_{name}_heartbeat_{field}"] = np.stack(
                receipts[f"stress_{name}_heartbeat_{field}"]
            )
        arrays[f"stress_{name}_heartbeat_clamp_count"] = np.asarray(
            heartbeat_clamps[name], dtype=np.int64
        )
        arrays[f"stress_{name}_drift"] = np.stack(drifts[name]).astype(np.float32)
        arrays[f"stress_{name}_clamp_count"] = np.asarray(clamps[name], dtype=np.int64)
        arrays[f"stress_{name}_state_sha256"] = np.asarray(
            hashes[name], dtype="<U64"
        )
    arrays["stress_absorbing_resume_sha256"] = np.asarray(resume_hashes, dtype="<U64")
    arrays["stress_absorbing_checkpoint_payload"] = np.frombuffer(
        checkpoint_payload, dtype=np.uint8
    ).copy()
    arrays["stress_absorbing_checkpoint_sha256"] = np.asarray(
        hashlib.sha256(checkpoint_payload).hexdigest(), dtype="<U64"
    )
    return arrays


def run_board(device: torch.device, dtype: torch.dtype, *, smoke: bool = False) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    mode_count = SMOKE_MODE_COUNT if smoke else MODE_COUNT
    absorbing = AbsorbingHarmonicAgeFieldController(AbsorbingHarmonicAgeFieldConfig(mode_count=mode_count))
    harmonic = HarmonicAgeFieldController(HarmonicAgeFieldConfig(mode_count=mode_count))
    state, symbols = _analytic_state(absorbing, device=device, dtype=dtype)
    pre_hash = tensor_sha256(state.field)
    deposit = torch.as_tensor((BASE_SYMBOLS + DEPOSIT_OFFSET) % ALPHABET_SIZE, device=device, dtype=torch.int64)
    arrays, _ = _run_operator_and_write(state, deposit, harmonic, absorbing)
    stress_symbols = [torch.as_tensor((BASE_SYMBOLS + 37 * t) % ALPHABET_SIZE, device=device, dtype=torch.int64) for t in range(128 if not smoke else 12)]
    stress = _run_stress(absorbing.new_state(batch_size=BATCH_SIZE, device=device, dtype=dtype), stress_symbols, harmonic, absorbing, device=device, dtype=dtype)
    codebook = absorbing.codebook(0, device=device, dtype=dtype)
    arrays.update(stress)
    arrays.update({
        "schema_id": np.asarray(TRACE_SCHEMA),
        "codebook": l30.cpu(codebook),
        "channel_phase": np.stack((l30.cpu(absorbing._constants(state)["channel_phase"].real), l30.cpu(absorbing._constants(state)["channel_phase"].imag)), axis=-1),
        "age_harmonics": np.asarray(AGE_HARMONICS, dtype=np.int64),
        "age_symbols": np.stack([l30.cpu(symbols[a]) for a in (0, 1, 2, 3, 6)]),
        "analytic_amplitudes": np.asarray([AGE_AMPLITUDES[int(a)] for a in (0, 1, 2, 3, 6)], dtype=np.float64),
        "deposit_symbols": l30.cpu(deposit),
        "pre_field_sha256": np.asarray(pre_hash, dtype="<U64"),
        "operator_identity_field_sha256": np.asarray(tensor_sha256(arrays["operator_identity_field"]), dtype="<U64"),
        "operator_absorbing_field_sha256": np.asarray(tensor_sha256(arrays["operator_post_field"]), dtype="<U64"),
    })
    metrics = {
        "mode_count": mode_count,
        "canonical": not smoke,
        "write_count": len(stress_symbols),
        "pre_field_sha256": pre_hash,
        "maximum_input_energy_drift": float(max(np.abs(arrays["cyclic_write_drift"]).max(), np.abs(arrays["absorbing_write_drift"]).max(), np.abs(arrays["stress_cyclic_drift"]).max(), np.abs(arrays["stress_absorbing_drift"]).max())),
        "clamp_count": int(arrays["cyclic_write_clamp_count"] + arrays["absorbing_write_clamp_count"] + arrays["stress_cyclic_clamp_count"].sum() + arrays["stress_absorbing_clamp_count"].sum()),
        "maximum_absolute_field": float(max(arrays["operator_pre_maximum_amplitude"].max(), arrays["stress_absorbing_post_write_maximum_amplitude"].max())),
        "resume_event_count": int(arrays["stress_absorbing_resume_sha256"].size),
    }
    return metrics, arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="float32", choices=("float32", "float64"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--smoke", action="store_true", help="run the reduced disposable smoke board")
    parser.add_argument("--cpu-smoke", action="store_true", help="run reduced CPU float64 smoke")
    args = parser.parse_args()
    smoke = bool(args.smoke or args.cpu_smoke)
    if args.cpu_smoke:
        args.device, args.dtype = "cpu", "float64"
    device = torch.device(args.device)
    dtype = torch.float64 if args.dtype == "float64" else torch.float32
    output_dir = args.output_dir.resolve() if args.output_dir is not None else (Path(tempfile.mkdtemp(prefix="l47-smoke-") ) if smoke else OUTPUT_DIR)
    board_path, trace_path = output_dir / BOARD_NAME, output_dir / TRACE_NAME
    hashes = {path.relative_to(ROOT).as_posix(): sha256_file(path) for path in SOURCE_PATHS if path.is_file()}
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA,
        "status": "INCOMPLETE",
        "layout_profile_id": ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID,
        "operator_profile_id": ABSORBING_HARMONIC_AGE_OPERATOR_PROFILE_ID,
        "projection_profile_id": ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID,
        "trace_schema_id": TRACE_SCHEMA,
        "preregistration_sha256": hashes.get(PREREGISTRATION.relative_to(ROOT).as_posix()),
        "source_sha256": hashes,
        "device": {"requested": str(device), "type": device.type, "name": torch.cuda.get_device_name(device) if device.type == "cuda" and torch.cuda.is_available() else str(device), "torch_version": torch.__version__, "hip_version": torch.version.hip, "dtype": args.dtype},
        "execution": {"canonical": not smoke, "smoke": smoke, "cpu_smoke": bool(args.cpu_smoke)},
        "constants": {"mode_count": MODE_COUNT if not smoke else SMOKE_MODE_COUNT, "active_modes": (MODE_COUNT if not smoke else SMOKE_MODE_COUNT) // 2, "channels": CHANNELS, "batch_size": BATCH_SIZE, "alphabet_size": ALPHABET_SIZE, "evolution_steps": EVOLUTION_STEPS, "readout_energy_floor": READOUT_FLOOR, "max_mode_amplitude": MAX_MODE_AMPLITUDE, "max_epsilon": MAX_EPSILON, "write_count": 128 if not smoke else 12, "save_write_index": 63, "age_harmonics": list(AGE_HARMONICS), "age_offsets": {str(k): v for k, v in AGE_OFFSETS.items()}, "age_amplitudes": {str(k): v for k, v in AGE_AMPLITUDES.items()}, "deposit_offset": DEPOSIT_OFFSET},
        "trace": {"path": TRACE_NAME, "sha256": None},
        "arms": {},
    }
    l30.atomic_json(board_path, board)
    try:
        if not smoke and (device.type != "cuda" or dtype is not torch.float32 or not torch.cuda.is_available()):
            raise L47RunnerError("canonical L47 execution requires CUDA and float32")
        missing = [str(path) for path in SOURCE_PATHS if not path.is_file()]
        if missing:
            raise L47RunnerError(f"missing bound source files: {missing!r}")
        started = time.perf_counter()
        metrics, arrays = run_board(device, dtype, smoke=smoke)
        l30.atomic_npz(trace_path, arrays)
        board["arms"]["smoke" if smoke else "canonical"] = metrics
        board["trace"] = {"path": TRACE_NAME, "sha256": sha256_file(trace_path), "array_count": len(arrays)}
        board["resources"] = {"wall_seconds": float(time.perf_counter() - started), "peak_allocated_bytes": int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" and torch.cuda.is_available() else 0}
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
