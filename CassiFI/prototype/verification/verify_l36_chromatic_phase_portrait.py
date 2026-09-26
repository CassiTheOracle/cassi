"""Independently verify the frozen L36 chromatic phase portrait."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.run_l30_white_chromatic_field as l30

BOARD_SCHEMA = "cassi.l36.chromatic-phase-portrait-board.v1"
TRACE_SCHEMA = "cassi.l36.chromatic-phase-portrait-traces.v1"
VERIFICATION_SCHEMA = "cassi.l36.chromatic-phase-portrait-verification.v1"
LAYOUT_PROFILE = "cassi.qi-cyclic-chromatic-coordinate-native.v1"
OPERATOR_PROFILE = "cassi.qi-cyclic-chromatic-heartbeat.v1"
PROJECTION_PROFILE = "cassi.qi-chromatic-phase-portrait.v1"
PREREGISTRATION = ROOT / "designs" / "L36-CHROMATIC-PHASE-PORTRAIT-PREREG.md"
DEFAULT_BOARD = ROOT / "_diag" / "l36-chromatic-phase-portrait" / "l36-board.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "l36-chromatic-phase-portrait"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L36-CHROMATIC-PHASE-PORTRAIT-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l36-verification.json"
MODE_COUNT = 2048
WIDTH = MODE_COUNT // 2
CHANNELS = 7
PANEL_SIDE = 16
SIDE = 2 * PANEL_SIDE + 1
HISTORIES = np.asarray(((252, 139), (132, 139)), dtype=np.int64)
EXPECTED_SOURCES = {
    "designs/L36-CHROMATIC-PHASE-PORTRAIT-PREREG.md",
    "cassi_white_chromatic_field.py",
    "cassi_cyclic_chromatic_field.py",
    "cassi_chromatic_phase_portrait.py",
    "verification/run_l30_white_chromatic_field.py",
    "verification/run_l36_chromatic_phase_portrait.py",
    "verification/verify_l36_chromatic_phase_portrait.py",
}
EXPECTED_ARRAYS = {
    "schema_id",
    "histories",
    "first_field",
    "after_field",
    "comparison_rgb",
    "read_only_equal",
    "first_rgb",
    "first_amplitude",
    "first_phase",
    "first_peak",
    "after_rgb",
    "after_amplitude",
    "after_phase",
    "after_peak",
    "dynamic_energy",
    "input_energy_drift",
    "clamp_count",
}


class L36VerificationError(RuntimeError):
    """L36 evidence violates its frozen contract."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise L36VerificationError(message)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    need(isinstance(value, Mapping), f"{label} must be an object")
    assert isinstance(value, Mapping)
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    need(isinstance(value, dict), "board root must be an object")
    return value


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def sibling_artifact(
    board_path: Path, value: Any, expected_name: str, label: str
) -> Path:
    item = mapping(value, label)
    name = item.get("path")
    need(isinstance(name, str) and name == expected_name, f"{label} sibling name mismatch")
    path = board_path.parent / expected_name
    need(path.is_file(), f"{label} artifact missing")
    need(item.get("sha256") == l30.sha256_file(path), f"{label} hash mismatch")
    return path


def load_trace(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        need(set(archive.files) == EXPECTED_ARRAYS, "trace array set mismatch")
        return {name: archive[name] for name in archive.files}


def portrait_oracle(field: np.ndarray) -> dict[str, np.ndarray]:
    batch_size = field.shape[2]
    parts = field.reshape(CHANNELS, 9, MODE_COUNT, batch_size)
    coordinates = (
        parts[:, 0, :WIDTH] + 1j * parts[:, 1, :WIDTH],
        parts[:, 2, :WIDTH] + 1j * parts[:, 3, :WIDTH],
        parts[:, 4, :WIDTH] + 1j * parts[:, 5, :WIDTH],
        parts[:, 6, :WIDTH] + 1j * parts[:, 7, :WIDTH],
    )
    white = np.ones(CHANNELS, dtype=np.float64) / math.sqrt(CHANNELS)
    channel = np.exp(2j * math.pi * np.arange(CHANNELS) / CHANNELS)
    spectra = np.stack(
        (
            np.sum(white[:, None, None] * coordinates[0], axis=0),
            np.sum(np.conjugate(channel)[:, None, None] * coordinates[1], axis=0)
            / math.sqrt(CHANNELS),
            np.sum(white[:, None, None] * coordinates[2], axis=0),
            np.sum(np.conjugate(channel)[:, None, None] * coordinates[3], axis=0)
            / math.sqrt(CHANNELS),
        ),
        axis=0,
    )
    count = PANEL_SIDE * PANEL_SIDE
    indices = np.floor(np.arange(count) * WIDTH / count).astype(np.int64)
    selected = spectra[:, indices].transpose(2, 0, 1).reshape(
        batch_size, 4, PANEL_SIDE, PANEL_SIDE
    )
    wave = np.fft.ifft2(selected, norm="ortho")
    amplitude = np.abs(wave)
    phase = np.angle(wave)
    peak = amplitude.max(axis=(-2, -1))
    scale = np.maximum(peak, np.finfo(np.float32).tiny)
    brightness = np.sqrt(amplitude / scale[:, :, None, None])
    hue = phase / (2.0 * math.pi)
    offsets = np.asarray((0.0, -1.0 / 3.0, 1.0 / 3.0), dtype=np.float64)
    hue_rgb = 0.5 + 0.5 * np.cos(
        2.0
        * math.pi
        * (hue[:, :, None] + offsets[None, None, :, None, None])
    )
    panels = np.clip(brightness[:, :, None] * hue_rgb, 0.0, 1.0)
    separator = np.zeros((batch_size, 3, PANEL_SIDE, 1), dtype=np.float64)
    top = np.concatenate((panels[:, 0], separator, panels[:, 1]), axis=3)
    bottom = np.concatenate((panels[:, 2], separator, panels[:, 3]), axis=3)
    horizontal = np.zeros((batch_size, 3, 1, SIDE), dtype=np.float64)
    rgb = np.concatenate((top, horizontal, bottom), axis=2)
    return {"rgb": rgb, "amplitude": amplitude, "phase": phase, "peak": peak}


def comparison_oracle(first: np.ndarray, after: np.ndarray) -> np.ndarray:
    vertical = np.zeros((3, SIDE, 1), dtype=np.float64)
    top = np.concatenate((first[0], vertical, first[1]), axis=2)
    bottom = np.concatenate((after[0], vertical, after[1]), axis=2)
    horizontal = np.zeros((3, 1, 2 * SIDE + 1), dtype=np.float64)
    return np.concatenate((top, horizontal, bottom), axis=1)


def verify_board(
    board_path: Path, *, allow_smoke_device: bool = False
) -> tuple[str, dict[str, Any]]:
    board = load_json(board_path)
    need(board.get("schema_id") == BOARD_SCHEMA, "board schema mismatch")
    need(board.get("status") == "COMPLETE", "board is not COMPLETE")
    need(board.get("layout_profile_id") == LAYOUT_PROFILE, "layout identity mismatch")
    need(board.get("operator_profile_id") == OPERATOR_PROFILE, "operator identity mismatch")
    need(board.get("projection_profile_id") == PROJECTION_PROFILE, "projection identity mismatch")
    need(board.get("trace_schema_id") == TRACE_SCHEMA, "trace schema mismatch")
    constants = mapping(board.get("constants"), "constants")
    expected_constants = {
        "mode_count": MODE_COUNT,
        "batch_size": 2,
        "panel_side": PANEL_SIDE,
        "output_side": SIDE,
        "histories": HISTORIES.tolist(),
        "evolution_steps": 8,
        "oracle_error_ceiling": 5.0e-5,
        "rgb_range_floor": 0.50,
        "rgb_std_floor": 0.05,
    }
    need(dict(constants) == expected_constants, "frozen constants mismatch")

    source = mapping(board.get("source_sha256"), "source_sha256")
    need(set(source) == EXPECTED_SOURCES, "source hash path set mismatch")
    for relative in EXPECTED_SOURCES:
        path = ROOT / relative
        need(path.is_file(), f"source path missing: {relative}")
        need(source[relative] == l30.sha256_file(path), f"source hash mismatch: {relative}")
    prereg_relative = PREREGISTRATION.relative_to(ROOT).as_posix()
    need(
        board.get("preregistration_sha256") == source[prereg_relative],
        "preregistration hash mismatch",
    )
    device = mapping(board.get("device"), "device")
    need(device.get("dtype") == "float32", "canonical dtype must be float32")
    if not allow_smoke_device:
        need(device.get("type") == "cuda", "canonical device type must be cuda")
        need(device.get("name") == "AMD Radeon RX 7900 XTX", "canonical GPU mismatch")
        need(isinstance(device.get("hip_version"), str), "HIP version missing")

    trace_path = sibling_artifact(board_path, board.get("trace"), "l36-traces.npz", "trace")
    sibling_artifact(board_path, board.get("projection"), "l36-comparison.png", "projection")
    arrays = load_trace(trace_path)
    need(str(arrays["schema_id"].item()) == TRACE_SCHEMA, "trace schema identity mismatch")
    need(np.array_equal(arrays["histories"], HISTORIES), "history fixture mismatch")
    need(arrays["first_field"].shape == (CHANNELS, 9 * MODE_COUNT, 2), "first field shape mismatch")
    need(arrays["after_field"].shape == arrays["first_field"].shape, "after field shape mismatch")
    need(arrays["first_rgb"].shape == (2, 3, SIDE, SIDE), "first RGB shape mismatch")
    need(arrays["after_rgb"].shape == arrays["first_rgb"].shape, "after RGB shape mismatch")
    need(arrays["comparison_rgb"].shape == (3, 2 * SIDE + 1, 2 * SIDE + 1), "comparison shape mismatch")
    for prefix in ("first", "after"):
        need(arrays[f"{prefix}_amplitude"].shape == (2, 4, PANEL_SIDE, PANEL_SIDE), f"{prefix} amplitude shape mismatch")
        need(arrays[f"{prefix}_phase"].shape == (2, 4, PANEL_SIDE, PANEL_SIDE), f"{prefix} phase shape mismatch")
        need(arrays[f"{prefix}_peak"].shape == (2, 4), f"{prefix} peak shape mismatch")
    need(arrays["dynamic_energy"].shape == (2, 2), "energy shape mismatch")
    need(arrays["input_energy_drift"].shape == (2, 2), "drift shape mismatch")
    need(bool(arrays["read_only_equal"].item()), "projection mutated its source state")
    need(int(arrays["clamp_count"].item()) == 0, "field clamps occurred")

    for name, value in arrays.items():
        if value.dtype.kind in "fci":
            need(bool(np.isfinite(value).all()), f"{name} contains non-finite values")
    for prefix in ("first", "after"):
        rgb = arrays[f"{prefix}_rgb"]
        phase = arrays[f"{prefix}_phase"]
        need(bool(((rgb >= 0.0) & (rgb <= 1.0)).all()), f"{prefix} RGB outside [0,1]")
        need(bool(((phase >= -math.pi) & (phase <= math.pi)).all()), f"{prefix} phase outside range")
        need(bool((rgb[:, :, PANEL_SIDE, :] == 0.0).all()), f"{prefix} horizontal separator is nonzero")
        need(bool((rgb[:, :, :, PANEL_SIDE] == 0.0).all()), f"{prefix} vertical separator is nonzero")
    comparison = arrays["comparison_rgb"]
    need(bool((comparison[:, SIDE, :] == 0.0).all()), "comparison horizontal separator is nonzero")
    need(bool((comparison[:, :, SIDE] == 0.0).all()), "comparison vertical separator is nonzero")

    first_oracle = portrait_oracle(arrays["first_field"])
    after_oracle = portrait_oracle(arrays["after_field"])
    errors: dict[str, float] = {}
    for prefix, oracle in (("first", first_oracle), ("after", after_oracle)):
        for name in ("rgb", "amplitude", "peak"):
            errors[f"{prefix}_{name}"] = float(
                np.max(np.abs(arrays[f"{prefix}_{name}"] - oracle[name]))
            )
        errors[f"{prefix}_phase"] = float(
            np.max(
                np.abs(
                    np.angle(
                        np.exp(
                            1j
                            * (arrays[f"{prefix}_phase"] - oracle["phase"])
                        )
                    )
                )
            )
        )
    expected_comparison = comparison_oracle(
        first_oracle["rgb"], after_oracle["rgb"]
    )
    errors["comparison_rgb"] = float(
        np.max(np.abs(comparison - expected_comparison))
    )
    maximum_oracle_error = max(errors.values())
    need(maximum_oracle_error <= 5.0e-5, "independent projection oracle mismatch")

    maximum_energy = float(arrays["dynamic_energy"].max())
    maximum_drift = float(np.abs(arrays["input_energy_drift"]).max())
    need(maximum_energy <= 1.05, "dynamic energy exceeds frozen bound")
    arm = mapping(mapping(board.get("arms"), "arms").get("canonical"), "canonical arm")
    declared_energy = arm.get("maximum_dynamic_energy")
    declared_drift = arm.get("maximum_absolute_input_energy_drift")
    need(isinstance(declared_energy, (int, float)), "maximum energy declaration missing")
    need(isinstance(declared_drift, (int, float)), "maximum drift declaration missing")
    assert isinstance(declared_energy, (int, float))
    assert isinstance(declared_drift, (int, float))
    need(math.isclose(float(declared_energy), maximum_energy, rel_tol=0.0, abs_tol=0.0), "maximum energy declaration mismatch")
    need(math.isclose(float(declared_drift), maximum_drift, rel_tol=0.0, abs_tol=0.0), "maximum drift declaration mismatch")
    need(arm.get("clamp_count") == 0, "clamp declaration mismatch")
    need(arm.get("read_only_equal") is True, "read-only declaration mismatch")

    portraits = np.concatenate((arrays["first_rgb"], arrays["after_rgb"]), axis=0)
    peaks = np.concatenate((arrays["first_peak"], arrays["after_peak"]), axis=0)
    rgb_range = float(portraits.max() - portraits.min())
    portrait_std = portraits.reshape(4, -1).std(axis=1)
    coordinate_nonzero = (peaks.max(axis=0) > 0.0).tolist()
    after_left = arrays["after_rgb"][0]
    after_right = arrays["after_rgb"][1]
    after_pair_distance = float(
        np.linalg.norm(after_left - after_right)
        / max(np.linalg.norm(after_left) + np.linalg.norm(after_right), 1.0e-12)
    )
    conditions = {
        "rgb_global_range": rgb_range >= 0.50,
        "minimum_portrait_standard_deviation": float(portrait_std.min()) >= 0.05,
        "all_coordinate_panels_nonzero": all(bool(value) for value in coordinate_nonzero),
    }
    verdict = "ADOPT" if all(conditions.values()) else "REJECT"
    return verdict, {
        "schema_id": VERIFICATION_SCHEMA,
        "verdict": verdict,
        "metrics": {
            "maximum_oracle_absolute_error": maximum_oracle_error,
            "oracle_errors": errors,
            "maximum_dynamic_energy": maximum_energy,
            "maximum_absolute_input_energy_drift": maximum_drift,
            "rgb_global_range": rgb_range,
            "portrait_standard_deviation": [float(value) for value in portrait_std],
            "coordinate_panel_nonzero": coordinate_nonzero,
            "after_tail_paired_image_distance": after_pair_distance,
            "clamp_count": 0,
        },
        "functional_conditions": conditions,
        "failures": [],
    }


def report_text(verdict: str, payload: Mapping[str, Any]) -> str:
    lines = [
        "# L36 Chromatic Phase Portrait — Verification",
        "",
        f"**Verdict: `{verdict}`**",
    ]
    metrics = mapping(payload.get("metrics", {}), "metrics")
    if metrics:
        lines.extend(
            [
                "",
                f"- RGB range: `{float(metrics['rgb_global_range']):.9f}`",
                f"- Minimum portrait standard deviation: `{min(float(value) for value in metrics['portrait_standard_deviation']):.9f}`",
                f"- Maximum independent-oracle error: `{float(metrics['maximum_oracle_absolute_error']):.9g}`",
                f"- After-tail paired image distance: `{float(metrics['after_tail_paired_image_distance']):.9g}`",
            ]
        )
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
        verdict = "INCOMPLETE"
        payload: dict[str, Any] = {
            "schema_id": VERIFICATION_SCHEMA,
            "verdict": verdict,
            "metrics": {},
            "functional_conditions": {},
            "failures": ["board artifact is unavailable"],
        }
    else:
        try:
            verdict, payload = verify_board(
                board_path, allow_smoke_device=args.allow_smoke_device
            )
        except Exception as exc:
            verdict = "FAIL"
            payload = {
                "schema_id": VERIFICATION_SCHEMA,
                "verdict": verdict,
                "metrics": {},
                "functional_conditions": {},
                "failures": [f"{type(exc).__name__}: {exc}"],
            }
    payload = dict(payload)
    payload.update(
        {
            "board_path": (
                board_path.relative_to(ROOT).as_posix()
                if board_path.is_relative_to(ROOT)
                else str(board_path)
            ),
            "board_sha256": l30.sha256_file(board_path) if board_path.is_file() else None,
        }
    )
    atomic_write(args.json.resolve(), l30.canonical_bytes(payload))
    atomic_write(args.report.resolve(), report_text(verdict, payload).encode("utf-8"))
    print(verdict)
    print(args.report.resolve())
    print(args.json.resolve())
    return 0 if verdict == "ADOPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
