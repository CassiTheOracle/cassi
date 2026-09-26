"""Independently verify the frozen L40 rolling ordered-relational board."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.run_l30_white_chromatic_field as l30r
import verification.verify_l30_white_chromatic_field as l30v

BOARD_SCHEMA = "cassi.l40.rolling-ordered-relational-board.v1"
TRACE_SCHEMA = "cassi.l40.rolling-ordered-relational-traces.v1"
VERIFICATION_SCHEMA = "cassi.l40.rolling-ordered-relational-verification.v1"
LAYOUT_PROFILE = "cassi.qi-cyclic-chromatic-coordinate-native.v1"
OPERATOR_PROFILE = "cassi.qi-ordered-relational-chromatic-recall.v1"
PROJECTION_PROFILE = "cassi.qi-cyclic-chromatic-projection.v1"
PREREGISTRATION = ROOT / "designs" / "L40-ROLLING-ORDERED-RELATIONAL-RECALL-PREREG.md"
RUNNER = ROOT / "verification" / "run_l40_rolling_ordered_relational_recall.py"
VERIFIER = ROOT / "verification" / "verify_l40_rolling_ordered_relational_recall.py"
DEFAULT_BOARD = ROOT / "_diag" / "l40-rolling-ordered-relational-recall" / "l40-rolling-board.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "l40-rolling-ordered-relational-recall"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L40-ROLLING-ORDERED-RELATIONAL-RECALL-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l40-rolling-verification.json"
TRACE_NAME = "l40-rolling-traces.npz"
MODE_COUNT = 2048
WIDTH = MODE_COUNT // 2
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
S0 = np.asarray((0, 37, 74, 111, 148, 185, 222, 259), dtype=np.int64)
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
EXPECTED_SOURCE_PATHS = (
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
EXPECTED_SOURCES = {
    path.relative_to(ROOT).as_posix() for path in EXPECTED_SOURCE_PATHS
}
EXPECTED_ARRAYS = {
    "schema_id",
    "checkpoint_names",
    "codebook",
    "expected_current",
    "expected_predecessor",
    "checkpoint_fields",
    "post_readout_fields",
    "emitted_symbols",
    "current_available",
    "current_scores",
    "current_symbols",
    "relational_scores",
    "relational_symbols",
    "relational_available",
    "ordered_scores",
    "clamp_counts",
    "input_energy_drift",
    "maximum_input_energy_drift",
    "maximum_absolute_field",
}


class L40RollingVerificationError(RuntimeError):
    """Rolling evidence violates its frozen mechanical contract."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise L40RollingVerificationError(message)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    need(isinstance(value, Mapping), f"{label} must be an object")
    assert isinstance(value, Mapping)
    return value


def sibling_trace(board_path: Path, value: Any) -> Path:
    item = mapping(value, "trace")
    need(item.get("path") == TRACE_NAME, "trace sibling name mismatch")
    path = board_path.parent / TRACE_NAME
    need(path.is_file(), "trace artifact missing")
    need(item.get("sha256") == l30r.sha256_file(path), "trace hash mismatch")
    need(item.get("array_count") == len(EXPECTED_ARRAYS), "trace array count mismatch")
    return path


def load_trace(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        need(set(archive.files) == EXPECTED_ARRAYS, "trace array set mismatch")
        return {name: archive[name] for name in archive.files}


def native_coordinates(field: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    parts = field.reshape(CHANNELS, 9, MODE_COUNT, field.shape[2])
    common = parts[:, 0, :WIDTH] + 1j * parts[:, 1, :WIDTH]
    differential = parts[:, 2, :WIDTH] + 1j * parts[:, 3, :WIDTH]
    return common, differential


def reconstruct_readout(field: np.ndarray, codebook: np.ndarray) -> dict[str, np.ndarray]:
    common, differential = native_coordinates(field)
    current = l30v.recompute_readout(differential, codebook)
    current_scores = current["scores"]
    current_symbols = current["symbols"]
    u = codebook[..., 0] + 1j * codebook[..., 1]
    harmonic = np.exp(2j * math.pi * np.arange(CHANNELS) / CHANNELS)
    common_carrier = common.sum(axis=0) / math.sqrt(CHANNELS)
    differential_carrier = (
        np.conjugate(harmonic)[:, None, None] * differential
    ).sum(axis=0) / math.sqrt(CHANNELS)
    relational_trace = -common_carrier * differential_carrier
    coefficient = np.einsum(
        "aw,wb->ab", np.conjugate(u), relational_trace, optimize=True
    ) / WIDTH
    relational_scores = (np.abs(coefficient) ** 2).T.astype(np.float32)
    relational_symbols = np.argmax(relational_scores, axis=1).astype(np.int64)
    floor = np.float32(1.0e-8)
    current_scale = np.maximum(
        np.max(current_scores, axis=1, keepdims=True), floor
    )
    relational_max = np.max(relational_scores, axis=1, keepdims=True)
    relational_scale = np.maximum(relational_max, floor)
    ordered_scores = np.maximum(
        current_scores / current_scale,
        relational_scores / relational_scale,
    ).astype(np.float32)
    relational_available = current["available"] & (relational_max[:, 0] >= floor)
    for row in range(BATCH_SIZE):
        if not current["available"][row]:
            ordered_scores[row] = current_scores[row]
            continue
        if relational_available[row] and relational_symbols[row] != current_symbols[row]:
            ordered_scores[row, relational_symbols[row]] = np.float32(2.0)
        ordered_scores[row, current_symbols[row]] = np.float32(3.0)
    return {
        "current_available": current["available"],
        "current_scores": current_scores,
        "current_symbols": current_symbols,
        "relational_scores": relational_scores,
        "relational_symbols": relational_symbols,
        "relational_available": relational_available,
        "ordered_scores": ordered_scores,
    }


def _failed_rows(condition: np.ndarray) -> list[int]:
    return np.flatnonzero(~np.asarray(condition, dtype=np.bool_)).astype(int).tolist()


def analyze_function(
    arrays: Mapping[str, np.ndarray],
) -> tuple[list[str], list[dict[str, Any]]]:
    failures: list[str] = []
    checkpoints: list[dict[str, Any]] = []
    scores = arrays["ordered_scores"]
    for checkpoint, name in enumerate(CHECKPOINT_NAMES):
        stage = checkpoint // 2
        current = EXPECTED_CURRENT[checkpoint]
        predecessor = EXPECTED_PREDECESSOR[checkpoint]
        emitted_rows = _failed_rows(arrays["emitted_symbols"][checkpoint] == current)
        current_rows = _failed_rows(arrays["current_symbols"][checkpoint] == current)
        available_rows = _failed_rows(arrays["current_available"][checkpoint])
        if emitted_rows:
            failures.append(f"{name}: emitted current mismatch rows {emitted_rows}")
        if current_rows:
            failures.append(f"{name}: diagnostic current mismatch rows {current_rows}")
        if available_rows:
            failures.append(f"{name}: current unavailable rows {available_rows}")

        current_score = np.take_along_axis(
            scores[checkpoint], current[:, None], axis=1
        )[:, 0]
        current_slot_rows = _failed_rows(current_score == np.float32(3.0))
        if current_slot_rows:
            failures.append(f"{name}: current slot mismatch rows {current_slot_rows}")

        if stage == 0:
            predecessor_rows = _failed_rows(~arrays["relational_available"][checkpoint])
            top_rows = _failed_rows((scores[checkpoint] >= 2.0).sum(axis=1) == 1)
        else:
            predecessor_rows = _failed_rows(
                arrays["relational_available"][checkpoint]
                & (arrays["relational_symbols"][checkpoint] == predecessor)
            )
            predecessor_score = np.take_along_axis(
                scores[checkpoint], predecessor[:, None], axis=1
            )[:, 0]
            slot_rows = _failed_rows(predecessor_score == np.float32(2.0))
            if slot_rows:
                failures.append(f"{name}: predecessor slot mismatch rows {slot_rows}")
            top_two = np.argsort(-scores[checkpoint], axis=1, kind="stable")[:, :2]
            expected_top_two = np.stack((current, predecessor), axis=1)
            top_rows = _failed_rows(np.all(top_two == expected_top_two, axis=1))
            count_rows = _failed_rows((scores[checkpoint] >= 2.0).sum(axis=1) == 2)
            if count_rows:
                failures.append(f"{name}: non-categorical score rows {count_rows}")
            if stage >= 2:
                stale_symbol = S0
                stale_score = np.take_along_axis(
                    scores[checkpoint], stale_symbol[:, None], axis=1
                )[:, 0]
                stale_rows = np.flatnonzero(
                    (arrays["relational_symbols"][checkpoint] == stale_symbol)
                    & (stale_score >= 2.0)
                    & (current != stale_symbol)
                ).astype(int).tolist()
                if stale_rows:
                    failures.append(f"{name}: stale S0 predecessor rows {stale_rows}")

        if predecessor_rows:
            failures.append(f"{name}: predecessor mismatch rows {predecessor_rows}")
        if top_rows:
            failures.append(f"{name}: ordered top-slot mismatch rows {top_rows}")
        checkpoints.append(
            {
                "name": name,
                "emitted_rows_passed": BATCH_SIZE - len(emitted_rows),
                "current_rows_passed": BATCH_SIZE - len(current_rows),
                "predecessor_rows_passed": BATCH_SIZE - len(predecessor_rows),
                "ordered_rows_passed": BATCH_SIZE - len(top_rows),
            }
        )
    return failures, checkpoints


def verify_board(
    board_path: Path, *, allow_smoke_device: bool = False
) -> tuple[str, dict[str, Any]]:
    board = l30v.load_json(board_path)
    need(board.get("schema_id") == BOARD_SCHEMA, "board schema mismatch")
    need(board.get("status") == "COMPLETE", "board is not COMPLETE")
    need(board.get("trace_schema_id") == TRACE_SCHEMA, "trace schema mismatch")
    need(board.get("layout_profile_id") == LAYOUT_PROFILE, "layout identity mismatch")
    need(board.get("operator_profile_id") == OPERATOR_PROFILE, "operator identity mismatch")
    need(board.get("projection_profile_id") == PROJECTION_PROFILE, "projection identity mismatch")

    source = mapping(board.get("source_sha256"), "source_sha256")
    need(set(source) == EXPECTED_SOURCES, "source hash path set mismatch")
    for relative in EXPECTED_SOURCES:
        path = ROOT / relative
        need(path.is_file(), f"source path missing: {relative}")
        need(source[relative] == l30r.sha256_file(path), f"source hash mismatch: {relative}")
    prereg_relative = PREREGISTRATION.relative_to(ROOT).as_posix()
    need(
        board.get("preregistration_sha256") == source[prereg_relative],
        "preregistration hash mismatch",
    )

    constants = mapping(board.get("constants"), "constants")
    expected_constants = {
        "channels": CHANNELS,
        "mode_count": MODE_COUNT,
        "active_modes": WIDTH,
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
    }
    need(dict(constants) == expected_constants, "frozen constants mismatch")

    device = mapping(board.get("device"), "device")
    need(device.get("dtype") == "float32", "canonical dtype must be float32")
    if not allow_smoke_device:
        need(device.get("type") == "cuda", "canonical device type must be cuda")
        need(device.get("name") == "AMD Radeon RX 7900 XTX", "canonical GPU mismatch")
        need(isinstance(device.get("hip_version"), str), "HIP version missing")

    trace_path = sibling_trace(board_path, board.get("trace"))
    arrays = load_trace(trace_path)
    need(str(arrays["schema_id"].item()) == TRACE_SCHEMA, "trace schema mismatch")
    need(
        arrays["checkpoint_names"].dtype == np.dtype("<U24")
        and np.array_equal(arrays["checkpoint_names"], CHECKPOINT_NAMES),
        "checkpoint identity mismatch",
    )
    field_shape = (len(CHECKPOINT_NAMES), CHANNELS, 9 * MODE_COUNT, BATCH_SIZE)
    score_shape = (len(CHECKPOINT_NAMES), BATCH_SIZE, ALPHABET_SIZE)
    symbol_shape = (len(CHECKPOINT_NAMES), BATCH_SIZE)
    need(arrays["codebook"].shape == (ALPHABET_SIZE, WIDTH, 2), "codebook shape mismatch")
    need(arrays["checkpoint_fields"].shape == field_shape, "field shape mismatch")
    need(arrays["post_readout_fields"].shape == field_shape, "post-readout field shape mismatch")
    for name in ("current_scores", "relational_scores", "ordered_scores"):
        need(arrays[name].shape == score_shape, f"{name} shape mismatch")
    for name in (
        "expected_current",
        "expected_predecessor",
        "emitted_symbols",
        "current_symbols",
        "relational_symbols",
        "current_available",
        "relational_available",
    ):
        need(arrays[name].shape == symbol_shape, f"{name} shape mismatch")
    need(arrays["clamp_counts"].shape == (69,), "clamp shape mismatch")
    need(arrays["input_energy_drift"].shape == (68, BATCH_SIZE), "drift shape mismatch")
    need(arrays["maximum_input_energy_drift"].shape == (), "maximum drift shape mismatch")
    need(arrays["maximum_absolute_field"].shape == (), "maximum field shape mismatch")

    float32_names = (
        "codebook",
        "checkpoint_fields",
        "post_readout_fields",
        "current_scores",
        "relational_scores",
        "ordered_scores",
        "input_energy_drift",
        "maximum_input_energy_drift",
        "maximum_absolute_field",
    )
    int64_names = (
        "expected_current",
        "expected_predecessor",
        "emitted_symbols",
        "current_symbols",
        "relational_symbols",
        "clamp_counts",
    )
    for name in float32_names:
        need(arrays[name].dtype == np.float32, f"{name} dtype mismatch")
        need(bool(np.isfinite(arrays[name]).all()), f"{name} contains non-finite values")
    for name in int64_names:
        need(arrays[name].dtype == np.int64, f"{name} dtype mismatch")
    for name in ("current_available", "relational_available"):
        need(arrays[name].dtype == np.bool_, f"{name} dtype mismatch")
    need(np.array_equal(arrays["expected_current"], EXPECTED_CURRENT), "expected current mismatch")
    need(
        np.array_equal(arrays["expected_predecessor"], EXPECTED_PREDECESSOR),
        "expected predecessor mismatch",
    )
    need(
        np.array_equal(arrays["checkpoint_fields"], arrays["post_readout_fields"]),
        "readout mutated field state",
    )

    for checkpoint in range(len(CHECKPOINT_NAMES)):
        reconstructed = reconstruct_readout(
            arrays["checkpoint_fields"][checkpoint], arrays["codebook"]
        )
        for name in ("current_scores", "relational_scores", "ordered_scores"):
            need(
                np.allclose(
                    arrays[name][checkpoint],
                    reconstructed[name],
                    rtol=2.0e-5,
                    atol=2.0e-6,
                ),
                f"{CHECKPOINT_NAMES[checkpoint]} {name} reconstruction mismatch",
            )
        for name in (
            "current_available",
            "current_symbols",
            "relational_symbols",
            "relational_available",
        ):
            need(
                np.array_equal(arrays[name][checkpoint], reconstructed[name]),
                f"{CHECKPOINT_NAMES[checkpoint]} {name} reconstruction mismatch",
            )
        need(
            np.array_equal(
                arrays["emitted_symbols"][checkpoint], reconstructed["current_symbols"]
            ),
            f"{CHECKPOINT_NAMES[checkpoint]} emitted-symbol reconstruction mismatch",
        )

    clamp_count = int(arrays["clamp_counts"].sum())
    maximum_drift = float(np.abs(arrays["input_energy_drift"]).max())
    declared_drift = float(arrays["maximum_input_energy_drift"])
    maximum_field = float(arrays["maximum_absolute_field"])
    checkpoint_maximum = float(np.abs(arrays["checkpoint_fields"]).max())
    parts = arrays["checkpoint_fields"].reshape(
        len(CHECKPOINT_NAMES), CHANNELS, 9, MODE_COUNT, BATCH_SIZE
    )
    active = parts[:, :, :8, :WIDTH]
    epsilon = parts[:, :, 8, :WIDTH]
    inactive = parts[:, :, :, WIDTH:]
    need(clamp_count == 0, "clamps occurred")
    need(maximum_drift <= 2.0e-6, "input-energy drift exceeds frozen bound")
    need(maximum_drift == declared_drift, "maximum input-energy drift mismatch")
    need(checkpoint_maximum <= maximum_field, "maximum field omits a checkpoint")
    need(bool((np.abs(active) <= MAX_MODE_AMPLITUDE).all()), "active field amplitude exceeds immutable bound")
    need(bool((epsilon >= 0.0).all()), "epsilon field contains negative values")
    need(bool((epsilon <= MAX_EPSILON).all()), "epsilon field exceeds immutable bound")
    need(bool((inactive == 0.0).all()), "inactive field modes are nonzero")
    need(maximum_field <= MAX_EPSILON, "field value exceeds immutable bound")

    arm = mapping(mapping(board.get("arms"), "arms").get("canonical"), "canonical arm")
    expected_arm = {
        "checkpoint_count": len(CHECKPOINT_NAMES),
        "tick_count": 68,
        "clamp_count": clamp_count,
        "maximum_input_energy_drift": declared_drift,
        "maximum_absolute_field": maximum_field,
        "readout_mutation_count": 0,
    }
    need(dict(arm) == expected_arm, "canonical arm declaration mismatch")

    failures, checkpoint_metrics = analyze_function(arrays)
    verdict = "ADOPT" if not failures else "REJECT"
    return verdict, {
        "schema_id": VERIFICATION_SCHEMA,
        "verdict": verdict,
        "mechanical_gates": {
            "source_and_artifact_integrity": True,
            "canonical_device": True,
            "shape_dtype_and_finiteness": True,
            "independent_readout_reconstruction": True,
            "readout_state_immutability": True,
            "bounded_dynamics": True,
        },
        "metrics": {
            "clamp_count": clamp_count,
            "maximum_input_energy_drift": maximum_drift,
            "maximum_absolute_field": maximum_field,
            "checkpoints": checkpoint_metrics,
        },
        "failures": failures,
    }


def report_text(verdict: str, payload: Mapping[str, Any]) -> str:
    lines = [
        "# L40 Rolling Ordered Relational Recall — Verification",
        "",
        f"**Verdict: `{verdict}`**",
    ]
    metrics = payload.get("metrics", {})
    checkpoints = metrics.get("checkpoints", []) if isinstance(metrics, Mapping) else []
    if isinstance(checkpoints, list) and checkpoints:
        lines.extend(
            [
                "",
                "| Checkpoint | Emitted | Current | Predecessor | Ordered |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for item in checkpoints:
            lines.append(
                f"| `{item['name']}` | {item['emitted_rows_passed']}/8 | "
                f"{item['current_rows_passed']}/8 | {item['predecessor_rows_passed']}/8 | "
                f"{item['ordered_rows_passed']}/8 |"
            )
    failures = payload.get("failures", [])
    if failures:
        lines.extend(["", "## Failures", *[f"- {failure}" for failure in failures]])
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
            "mechanical_gates": {},
            "metrics": {},
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
                "mechanical_gates": {},
                "metrics": {},
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
            "board_sha256": l30r.sha256_file(board_path) if board_path.is_file() else None,
        }
    )
    l30v.atomic_write(args.json.resolve(), l30v.canonical_bytes(payload))
    l30v.atomic_write(
        args.report.resolve(), report_text(verdict, payload).encode("utf-8")
    )
    print(verdict)
    print(args.report.resolve())
    print(args.json.resolve())
    return 1 if verdict in {"FAIL", "INCOMPLETE"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
