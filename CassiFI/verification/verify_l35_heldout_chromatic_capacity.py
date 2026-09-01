"""Independently verify the frozen L35 held-out sequence-capacity board."""

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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.run_l30_white_chromatic_field as l30

BOARD_SCHEMA = "cassi.l35.heldout-chromatic-capacity-board.v1"
TRACE_SCHEMA = "cassi.l35.heldout-chromatic-capacity-traces.v1"
VERIFICATION_SCHEMA = "cassi.l35.heldout-chromatic-capacity-verification.v1"
PREREGISTRATION = ROOT / "designs" / "L35-HELDOUT-CHROMATIC-CAPACITY-PREREG.md"
DEFAULT_BOARD = ROOT / "_diag" / "l35-heldout-chromatic-capacity" / "l35-board.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "l35-heldout-chromatic-capacity"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L35-HELDOUT-CHROMATIC-CAPACITY-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l35-verification.json"
DOMAIN = b"cassi-l35-heldout-sequence-capacity.v1"
DEPTHS = (1, 2, 4, 8, 16)
BATCH_SIZE = 16
MAX_DEPTH = max(DEPTHS)
MODE_COUNT = 2048
ALPHABET_SIZE = 260
EXPOSED = frozenset((0, 22, 37, 59, 74, 96, 97, 111, 134, 148, 171, 185, 208, 222, 245, 259))
POOL = tuple(symbol for symbol in range(ALPHABET_SIZE) if symbol not in EXPOSED)
PROFILE_NAMES = ("l31-cyclic", "l32-quadrature", "l34-exact")
PROFILE_IDENTITIES = (
    {
        "name": "l31-cyclic",
        "layout_profile_id": "cassi.qi-cyclic-chromatic-coordinate-native.v1",
        "operator_profile_id": "cassi.qi-cyclic-chromatic-heartbeat.v1",
        "projection_profile_id": "cassi.qi-cyclic-chromatic-projection.v1",
    },
    {
        "name": "l32-quadrature",
        "layout_profile_id": "cassi.qi-cyclic-chromatic-coordinate-native.v1",
        "operator_profile_id": "cassi.qi-quadrature-chromatic-recall.v1",
        "projection_profile_id": "cassi.qi-cyclic-chromatic-projection.v1",
    },
    {
        "name": "l34-exact",
        "layout_profile_id": "cassi.qi-cyclic-chromatic-coordinate-native.v1",
        "operator_profile_id": "cassi.qi-exact-cyclic-strang.v1",
        "projection_profile_id": "cassi.qi-cyclic-chromatic-projection.v1",
    },
)
EXPECTED_SOURCES = {
    "designs/L35-HELDOUT-CHROMATIC-CAPACITY-PREREG.md",
    "cassi_white_chromatic_field.py",
    "cassi_cyclic_chromatic_field.py",
    "cassi_quadrature_chromatic_field.py",
    "cassi_exact_cyclic_field.py",
    "verification/run_l30_white_chromatic_field.py",
    "verification/run_l35_heldout_chromatic_capacity.py",
    "verification/verify_l35_heldout_chromatic_capacity.py",
}
EXPECTED_ARRAYS = {
    "schema_id",
    "profile_names",
    "depths",
    "sequences",
    "scores",
    "available",
    "white_coherence",
    "dynamic_energy",
    "input_energy_drift",
    "clamp_counts",
}


class L35VerificationError(RuntimeError):
    """L35 evidence violates its frozen contract."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise L35VerificationError(message)


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


def _draw(parts: tuple[object, ...], used: set[int]) -> int:
    attempt = 0
    while True:
        payload = b"\0".join(
            (DOMAIN, *(str(part).encode("ascii") for part in parts), str(attempt).encode("ascii"))
        )
        candidate = POOL[
            int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % len(POOL)
        ]
        if candidate not in used:
            return candidate
        attempt += 1


def heldout_sequences() -> np.ndarray:
    sequences = np.full((len(DEPTHS), BATCH_SIZE, MAX_DEPTH), -1, dtype=np.int64)
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


def ranks(scores: np.ndarray, targets: np.ndarray) -> np.ndarray:
    expanded = scores[:, None, :]
    chosen = np.take_along_axis(expanded, targets[..., None], axis=2)[..., 0]
    ids = np.arange(scores.shape[1], dtype=np.int64)
    return (
        1
        + (expanded > chosen[..., None]).sum(axis=2)
        + ((expanded == chosen[..., None]) & (ids < targets[..., None])).sum(axis=2)
    ).astype(np.int64)


def verify_histories(sequences: np.ndarray) -> None:
    need(np.array_equal(sequences, heldout_sequences()), "held-out history tensor mismatch")
    for depth_index, depth in enumerate(DEPTHS):
        for history in range(BATCH_SIZE):
            active = sequences[depth_index, history, :depth]
            need(len(set(int(value) for value in active)) == depth, "history repeats a symbol")
            need(not any(int(value) in EXPOSED for value in active), "history uses exposed symbol")
            need(bool(np.all(sequences[depth_index, history, depth:] == -1)), "history padding mismatch")
        for history in range(0, BATCH_SIZE, 2):
            even = sequences[depth_index, history, :depth]
            odd = sequences[depth_index, history + 1, :depth]
            need(bool(even[-1] == odd[-1]), "paired histories do not share their tail")
            if depth > 1:
                need(not np.array_equal(even[:-1], odd[:-1]), "paired prefixes collide")


def sibling_trace(board_path: Path, value: Any) -> Path:
    item = mapping(value, "trace")
    name = item.get("path")
    need(isinstance(name, str) and name == "l35-traces.npz", "trace sibling name mismatch")
    path = board_path.parent / "l35-traces.npz"
    need(path.is_file(), "trace artifact missing")
    need(item.get("sha256") == l30.sha256_file(path), "trace hash mismatch")
    return path


def load_trace(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        need(set(archive.files) == EXPECTED_ARRAYS, "trace array set mismatch")
        return {name: archive[name] for name in archive.files}


def analyze(arrays: Mapping[str, np.ndarray]) -> tuple[dict[str, Any], str]:
    profile_metrics: dict[str, Any] = {}
    for profile_index, profile_name in enumerate(PROFILE_NAMES):
        by_depth: dict[str, Any] = {}
        retained_capacity = 0
        history_capacity = 0
        for depth_index, depth in enumerate(DEPTHS):
            sequence = arrays["sequences"][depth_index, :, :depth]
            step_scores = arrays["scores"][profile_index, depth_index, :, :depth]
            immediate_predictions = np.argmax(step_scores, axis=2)
            immediate_accuracy = float(np.mean(immediate_predictions == sequence))
            final_scores = step_scores[:, -1]
            final_ranks = ranks(final_scores, sequence)
            reciprocal_rank_by_age = np.mean(
                1.0 / final_ranks[:, ::-1].astype(np.float64), axis=0
            )
            newest_accuracy = float(
                np.mean(np.argmax(final_scores, axis=1) == sequence[:, -1])
            )
            left = final_scores[0::2]
            right = final_scores[1::2]
            distances = np.linalg.norm(left - right, axis=1) / np.maximum(
                np.linalg.norm(left, axis=1) + np.linalg.norm(right, axis=1),
                1.0e-12,
            )
            median_distance = float(np.median(distances))
            retained = (
                immediate_accuracy == 1.0
                and newest_accuracy == 1.0
                and bool(np.all(reciprocal_rank_by_age >= 0.05))
            )
            history_observable = retained and median_distance >= 0.01
            if retained:
                retained_capacity = max(retained_capacity, depth)
            if history_observable:
                history_capacity = max(history_capacity, depth)
            by_depth[str(depth)] = {
                "immediate_top1_accuracy": immediate_accuracy,
                "newest_final_top1_accuracy": newest_accuracy,
                "mean_reciprocal_rank_by_age": [
                    float(value) for value in reciprocal_rank_by_age
                ],
                "oldest_mean_reciprocal_rank": float(reciprocal_rank_by_age[-1]),
                "paired_same_tail_distance_median": median_distance,
                "available_fraction": float(
                    arrays["available"][profile_index, depth_index, :, :depth].mean()
                ),
                "retained": retained,
                "history_observable": history_observable,
            }
        profile_metrics[profile_name] = {
            "retained_capacity": retained_capacity,
            "history_observable_capacity": history_capacity,
            "depths": by_depth,
        }

    if any(
        values["history_observable_capacity"] >= 2
        for values in profile_metrics.values()
    ):
        outcome = "SUPPORTS"
    elif all(
        values["retained_capacity"] <= 1
        and values["depths"]["2"]["oldest_mean_reciprocal_rank"] < 0.05
        and values["depths"]["2"]["paired_same_tail_distance_median"] < 0.01
        for values in profile_metrics.values()
    ):
        outcome = "CONTRADICTS"
    else:
        outcome = "INCONCLUSIVE"
    return profile_metrics, outcome


def verify_board(
    board_path: Path, *, allow_smoke_device: bool = False
) -> tuple[str, dict[str, Any]]:
    board = load_json(board_path)
    need(board.get("schema_id") == BOARD_SCHEMA, "board schema mismatch")
    need(board.get("status") == "COMPLETE", "board is not COMPLETE")
    need(board.get("trace_schema_id") == TRACE_SCHEMA, "trace schema mismatch")
    need(board.get("profiles") == list(PROFILE_IDENTITIES), "profile identities mismatch")
    constants = mapping(board.get("constants"), "constants")
    need(constants.get("mode_count") == MODE_COUNT, "mode count mismatch")
    need(constants.get("alphabet_size") == ALPHABET_SIZE, "alphabet size mismatch")
    need(constants.get("batch_size") == BATCH_SIZE, "batch size mismatch")
    need(constants.get("depths") == list(DEPTHS), "depth schedule mismatch")
    need(constants.get("evolution_steps") == 8, "evolution step mismatch")
    need(constants.get("retained_mrr_floor") == 0.05, "MRR floor mismatch")
    need(constants.get("paired_distance_floor") == 0.01, "distance floor mismatch")

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

    trace_path = sibling_trace(board_path, board.get("trace"))
    arrays = load_trace(trace_path)
    need(str(arrays["schema_id"].item()) == TRACE_SCHEMA, "trace schema identity mismatch")
    need(np.array_equal(arrays["profile_names"], np.asarray(PROFILE_NAMES)), "profile order mismatch")
    need(np.array_equal(arrays["depths"], np.asarray(DEPTHS)), "trace depths mismatch")
    need(arrays["sequences"].shape == (len(DEPTHS), BATCH_SIZE, MAX_DEPTH), "sequence shape mismatch")
    step_shape = (len(PROFILE_NAMES), len(DEPTHS), BATCH_SIZE, MAX_DEPTH)
    need(arrays["scores"].shape == (*step_shape, ALPHABET_SIZE), "score shape mismatch")
    for name in ("available", "white_coherence", "dynamic_energy", "input_energy_drift"):
        need(arrays[name].shape == step_shape, f"{name} shape mismatch")
    need(arrays["clamp_counts"].shape == (len(PROFILE_NAMES), len(DEPTHS)), "clamp shape mismatch")
    verify_histories(arrays["sequences"])

    for name in ("scores", "white_coherence", "dynamic_energy", "input_energy_drift"):
        need(bool(np.isfinite(arrays[name]).all()), f"{name} contains non-finite values")
    need(bool((arrays["scores"] >= 0.0).all()), "scores contain negative values")
    need(bool((arrays["dynamic_energy"] >= 0.0).all()), "energy contains negative values")
    for depth_index, depth in enumerate(DEPTHS):
        need(bool((arrays["scores"][:, depth_index, :, depth:] == 0.0).all()), "score padding is nonzero")
        need(bool((arrays["available"][:, depth_index, :, depth:] == 0).all()), "availability padding is nonzero")
        need(bool((arrays["white_coherence"][:, depth_index, :, depth:] == 0.0).all()), "coherence padding is nonzero")
        need(bool((arrays["dynamic_energy"][:, depth_index, :, depth:] == 0.0).all()), "energy padding is nonzero")
        need(bool((arrays["input_energy_drift"][:, depth_index, :, depth:] == 0.0).all()), "drift padding is nonzero")

    maximum_energy = float(arrays["dynamic_energy"].max())
    maximum_drift = float(np.abs(arrays["input_energy_drift"]).max())
    clamp_count = int(arrays["clamp_counts"].sum())
    need(maximum_energy <= 1.05, "dynamic energy exceeds frozen bound")
    need(maximum_drift <= 2.0e-5, "input energy drift exceeds frozen bound")
    need(clamp_count == 0, "clamps occurred")
    arm = mapping(mapping(board.get("arms"), "arms").get("canonical"), "canonical arm")
    need(arm.get("profile_count") == len(PROFILE_NAMES), "profile count declaration mismatch")
    need(arm.get("history_count_per_depth") == BATCH_SIZE, "history count declaration mismatch")
    declared_energy = arm.get("maximum_dynamic_energy")
    declared_drift = arm.get("maximum_absolute_input_energy_drift")
    need(isinstance(declared_energy, (int, float)), "maximum energy declaration missing")
    need(isinstance(declared_drift, (int, float)), "maximum drift declaration missing")
    assert isinstance(declared_energy, (int, float))
    assert isinstance(declared_drift, (int, float))
    need(math.isclose(float(declared_energy), maximum_energy, rel_tol=0.0, abs_tol=0.0), "maximum energy declaration mismatch")
    need(math.isclose(float(declared_drift), maximum_drift, rel_tol=0.0, abs_tol=0.0), "maximum drift declaration mismatch")
    need(arm.get("clamp_count") == clamp_count, "clamp declaration mismatch")

    profile_metrics, outcome = analyze(arrays)
    return outcome, {
        "schema_id": VERIFICATION_SCHEMA,
        "verdict": outcome,
        "metrics": {
            "maximum_dynamic_energy": maximum_energy,
            "maximum_absolute_input_energy_drift": maximum_drift,
            "clamp_count": clamp_count,
            "profiles": profile_metrics,
        },
        "failures": [],
    }


def report_text(verdict: str, payload: Mapping[str, Any]) -> str:
    lines = [
        "# L35 Held-Out Chromatic Capacity — Verification",
        "",
        f"**Outcome: `{verdict}`**",
    ]
    profiles = mapping(mapping(payload.get("metrics", {}), "metrics").get("profiles", {}), "profiles")
    if profiles:
        lines.extend(["", "| Profile | Retained depth | History-observable depth | Depth-2 oldest MRR | Depth-2 paired distance |", "|---|---:|---:|---:|---:|"])
        for name in PROFILE_NAMES:
            values = mapping(profiles[name], name)
            depth2 = mapping(mapping(values.get("depths"), "depths").get("2"), "depth 2")
            lines.append(
                f"| `{name}` | {values['retained_capacity']} | {values['history_observable_capacity']} | "
                f"{float(depth2['oldest_mean_reciprocal_rank']):.9f} | "
                f"{float(depth2['paired_same_tail_distance_median']):.9f} |"
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
    return 1 if verdict in {"FAIL", "INCOMPLETE"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
