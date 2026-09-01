"""Independently verify and classify the frozen L43 stable harmonic board."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.verify_l42_harmonic_age_field as l42

BOARD_SCHEMA = "cassi.l43.stable-harmonic-field-board.v1"
TRACE_SCHEMA = "cassi.l43.stable-harmonic-field-traces.v1"
VERIFICATION_SCHEMA = "cassi.l43.stable-harmonic-field-verification.v1"
LAYOUT_PROFILE = "cassi.qi-cyclic-chromatic-coordinate-native.v1"
OPERATOR_PROFILE = "cassi.qi-stable-harmonic-age-ladder.v1"
PROJECTION_PROFILE = "cassi.qi-cyclic-chromatic-projection.v1"
ROUND_OFF_MULTIPLIER = 128.0
PREREGISTRATION = ROOT / "designs" / "L43-STABLE-HARMONIC-AGE-PREREG.md"
DEFAULT_BOARD = ROOT / "_diag" / "l43-stable-harmonic-field" / "l43-board.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "l43-stable-harmonic-field"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L43-STABLE-HARMONIC-FIELD-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l43-verification.json"
EXPECTED_SOURCES = {
    "designs/L43-STABLE-HARMONIC-AGE-PREREG.md",
    "designs/L42-HARMONIC-AGE-LADDER-PREREG.md",
    "cassi_white_chromatic_field.py",
    "cassi_cyclic_chromatic_field.py",
    "cassi_harmonic_age_field.py",
    "cassi_stable_harmonic_field.py",
    "verification/run_l30_white_chromatic_field.py",
    "verification/verify_l30_white_chromatic_field.py",
    "verification/run_l31_cyclic_chromatic_field.py",
    "verification/verify_l31_cyclic_chromatic_field.py",
    "verification/run_l42_harmonic_age_field.py",
    "verification/verify_l42_harmonic_age_field.py",
    "verification/run_l43_stable_harmonic_field.py",
    "verification/verify_l43_stable_harmonic_field.py",
}
L42_SOURCES = l42.EXPECTED_SOURCES


def numerical_floor(age_scores: np.ndarray) -> np.ndarray:
    age_max = np.max(age_scores, axis=-1)
    row_peak = np.max(age_max, axis=-1)
    epsilon = np.finfo(age_scores.dtype).eps
    return np.maximum(
        np.asarray(1.0e-8, dtype=age_scores.dtype),
        row_peak
        * np.asarray(ROUND_OFF_MULTIPLIER * epsilon, dtype=age_scores.dtype),
    )
def stable_aggregate(
    result: dict[str, np.ndarray], age_scores: np.ndarray
) -> dict[str, np.ndarray]:
    age_symbols = np.argmax(age_scores, axis=2).astype(np.int64)
    age_max = np.max(age_scores, axis=2)
    floor = numerical_floor(age_scores)
    age_available = result["available"][:, None] & (age_max >= floor[:, None])
    normalized = np.where(
        age_available[:, :, None],
        age_scores / np.maximum(age_max, floor[:, None])[:, :, None],
        np.zeros_like(age_scores),
    ).astype(np.float32 if age_scores.dtype == np.float32 else np.float64)
    scores = np.max(normalized, axis=1)
    for row in range(scores.shape[0]):
        if not result["available"][row]:
            scores[row] = result["scores"][row]
            continue
        for age in range(l42.l30.CHANNELS - 1, -1, -1):
            if age_available[row, age]:
                scores[row, age_symbols[row, age]] = 8 - age
    result.update(
        {
            "scores": scores,
            "symbols": age_symbols[:, 0],
            "age_scores": age_scores,
            "age_symbols": age_symbols,
            "age_available": age_available,
            "age_numerical_floor": floor,
            "normalized": normalized,
        }
    )
    return result


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    return l42.l30.mapping(value, label)


def sibling_artifact(
    board_path: Path, value: Any, expected_name: str, label: str
) -> Path:
    item = mapping(value, label)
    name = item.get("path")
    l42.l30.need(
        isinstance(name, str)
        and Path(name).name == name
        and name == expected_name,
        f"{label} must be sibling basename {expected_name}",
    )
    assert isinstance(name, str)
    path = board_path.parent / name
    l42.l30.need(path.is_file(), f"{label} artifact missing")
    l42.l30.need(
        item.get("sha256") == l42.l30.sha256_file(path),
        f"{label} hash mismatch",
    )
    return path


def verify_board(
    board_path: Path, *, allow_smoke_device: bool = False
) -> tuple[str, dict[str, Any]]:
    board = l42.l30.load_json(board_path)
    l42.l30.need(board.get("schema_id") == BOARD_SCHEMA, "board schema mismatch")
    l42.l30.need(board.get("status") == "COMPLETE", "board is not COMPLETE")
    l42.l30.need(
        board.get("layout_profile_id") == LAYOUT_PROFILE, "layout identity mismatch"
    )
    l42.l30.need(
        board.get("operator_profile_id") == OPERATOR_PROFILE,
        "operator identity mismatch",
    )
    l42.l30.need(
        board.get("projection_profile_id") == PROJECTION_PROFILE,
        "projection identity mismatch",
    )
    l42.l30.need(
        board.get("trace_schema_id") == TRACE_SCHEMA, "trace schema mismatch"
    )
    source = mapping(board.get("source_sha256"), "source_sha256")
    l42.l30.need(set(source) == EXPECTED_SOURCES, "source hash path set mismatch")
    for relative in EXPECTED_SOURCES:
        path = ROOT / relative
        l42.l30.need(path.is_file(), f"source path missing: {relative}")
        l42.l30.need(
            source[relative] == l42.l30.sha256_file(path),
            f"source hash mismatch: {relative}",
        )
    prereg_relative = PREREGISTRATION.relative_to(ROOT).as_posix()
    l42.l30.need(
        board.get("preregistration_sha256") == source[prereg_relative],
        "preregistration hash mismatch",
    )
    constants = mapping(board.get("constants"), "constants")
    l42.l30.need(
        constants.get("round_off_multiplier") == ROUND_OFF_MULTIPLIER,
        "round-off multiplier mismatch",
    )
    trace_path = sibling_artifact(
        board_path, board.get("trace"), "l43-traces.npz", "trace"
    )
    png_path = sibling_artifact(
        board_path, board.get("projection"), "l43-projection.png", "projection"
    )
    with np.load(trace_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    required = {
        "task_read_age_numerical_floor": (8, 8),
        "pre_readout_age_numerical_floor": (8,),
        "four_post_age_numerical_floor": (4, 8),
        "four_blank_final_age_numerical_floor": (8,),
    }
    for name, shape in required.items():
        l42.l30.need(
            name in arrays and arrays[name].shape == shape,
            f"stable trace shape mismatch: {name}",
        )
        l42.l30.need(
            bool(np.isfinite(arrays[name]).all()),
            f"stable trace contains nonfinite values: {name}",
        )

    with tempfile.TemporaryDirectory(
        prefix=".l43-verify-", dir=board_path.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        compat_trace = temporary / "l42-traces.npz"
        compat_png = temporary / "l42-projection.png"
        shutil.copyfile(trace_path, compat_trace)
        shutil.copyfile(png_path, compat_png)
        compat = dict(board)
        compat.update(
            {
                "schema_id": l42.BOARD_SCHEMA,
                "layout_profile_id": l42.LAYOUT_PROFILE,
                "operator_profile_id": l42.OPERATOR_PROFILE,
                "projection_profile_id": l42.PROJECTION_PROFILE,
                "trace_schema_id": TRACE_SCHEMA,
                "preregistration_sha256": l42.l30.sha256_file(
                    l42.PREREGISTRATION
                ),
                "source_sha256": {
                    relative: l42.l30.sha256_file(ROOT / relative)
                    for relative in L42_SOURCES
                },
                "trace": {
                    "path": compat_trace.name,
                    "sha256": l42.l30.sha256_file(compat_trace),
                    "array_count": mapping(board.get("trace"), "trace").get(
                        "array_count"
                    ),
                },
                "projection": {
                    "path": compat_png.name,
                    "sha256": l42.l30.sha256_file(compat_png),
                },
            }
        )
        compat_board = temporary / "l42-board.json"
        l42.l30.atomic_write(compat_board, l42.l30.canonical_bytes(compat))
        previous = (l42.TRACE_SCHEMA, l42.aggregate_harmonics)
        try:
            l42.TRACE_SCHEMA = TRACE_SCHEMA
            l42.aggregate_harmonics = stable_aggregate
            inherited_verdict, inherited = l42.verify_board(
                compat_board, allow_smoke_device=allow_smoke_device
            )
        finally:
            l42.TRACE_SCHEMA, l42.aggregate_harmonics = previous

    floor_cases = (
        (
            "task_read_age_scores",
            "task_read_age_numerical_floor",
            "task_read_age_available",
            arrays["task_read_available"],
        ),
        (
            "pre_readout_age_scores",
            "pre_readout_age_numerical_floor",
            "pre_readout_age_available",
            arrays["pre_readout_available"],
        ),
        (
            "four_post_age_scores",
            "four_post_age_numerical_floor",
            "four_post_age_available",
            arrays["four_post_available"],
        ),
        (
            "four_blank_final_age_scores",
            "four_blank_final_age_numerical_floor",
            "four_blank_final_age_available",
            arrays["four_blank_final_available"],
        ),
    )
    unavailable_zero = True
    for scores_name, floor_name, available_name, base_available in floor_cases:
        scores = arrays[scores_name]
        expected_floor = numerical_floor(scores)
        l42.l30.need(
            np.array_equal(arrays[floor_name], expected_floor),
            f"numerical floor mismatch: {floor_name}",
        )
        age_max = np.max(scores, axis=-1)
        expected_available = base_available[..., None] & (
            age_max >= expected_floor[..., None]
        )
        l42.l30.need(
            np.array_equal(arrays[available_name], expected_available),
            f"stable availability mismatch: {available_name}",
        )
        denominator = np.maximum(age_max, expected_floor[..., None])
        normalized = np.where(
            expected_available[..., None],
            scores / denominator[..., None],
            np.zeros_like(scores),
        )
        unavailable_zero = unavailable_zero and bool(
            np.count_nonzero(normalized[~expected_available]) == 0
        )

    occupied = np.zeros((8, 7), dtype=np.bool_)
    occupied[:, :4] = True
    post_occupancy = np.array_equal(
        arrays["four_post_age_available"][3], occupied
    )
    blank_occupancy = np.array_equal(
        arrays["four_blank_final_age_available"], occupied
    )
    conditions = dict(
        mapping(inherited.get("functional_conditions"), "inherited conditions")
    )
    conditions["four_slot_occupancy_and_safety"] = bool(
        post_occupancy
        and blank_occupancy
        and unavailable_zero
        and inherited["metrics"].get("four_arm_clamp_count") == 0
    )
    l42.l30.need(len(conditions) == 13, "functional condition count mismatch")
    metrics = dict(mapping(inherited.get("metrics"), "inherited metrics"))
    metrics.update(
        {
            "minimum_age_numerical_floor": float(
                min(np.min(arrays[name]) for name in required)
            ),
            "maximum_age_numerical_floor": float(
                max(np.max(arrays[name]) for name in required)
            ),
            "post_four_exact_occupancy": post_occupancy,
            "blank_exact_occupancy": blank_occupancy,
            "unavailable_normalized_remainder_exact_zero": unavailable_zero,
        }
    )
    failures = list(inherited.get("failures", []))
    if inherited_verdict == "FAIL" and not failures:
        failures.append("inherited verifier returned FAIL")
    verdict = (
        "FAIL"
        if failures
        else ("ADOPT" if all(conditions.values()) else "REJECT")
    )
    return verdict, {
        "schema_id": VERIFICATION_SCHEMA,
        "verdict": verdict,
        "metrics": metrics,
        "functional_conditions": conditions,
        "diagnostics": inherited.get("diagnostics", {}),
        "failures": failures,
    }


def report_text(verdict: str, payload: Mapping[str, Any]) -> str:
    explanation = {
        "ADOPT": "All frozen mechanical and functional gates passed.",
        "REJECT": "Mechanics passed; one or more preregistered functional conditions failed.",
        "INCOMPLETE": "The canonical board was unavailable or incomplete.",
        "FAIL": "Evidence integrity or a frozen mechanical gate failed.",
    }[verdict]
    lines = [
        "# L43 Stable Harmonic Field — Verification",
        "",
        f"**Verdict: `{verdict}`**",
        "",
        explanation,
    ]
    conditions = payload.get("functional_conditions")
    if isinstance(conditions, Mapping) and conditions:
        lines.extend(
            [
                "",
                "## Functional conditions",
                *[
                    f"- `{'PASS' if bool(value) else 'FAIL'}` — `{name}`"
                    for name, value in conditions.items()
                ],
            ]
        )
    metrics = payload.get("metrics")
    if isinstance(metrics, Mapping) and metrics:
        lines.extend(
            [
                "",
                "## Stable readout metrics",
                f"- Immediate emitted-symbol accuracy: `{metrics.get('immediate_emitted_symbol_accuracy')}`",
                f"- Reverse top-four accuracy after deposit four: `{metrics.get('reverse_top4_accuracy_after_fourth')}`",
                f"- Reverse top-four accuracy after eight blank ticks: `{metrics.get('reverse_top4_accuracy_after_blank')}`",
                f"- Maximum numerical floor: `{metrics.get('maximum_age_numerical_floor')}`",
                f"- Stress clamps: `{metrics.get('stress_clamp_count')}`",
            ]
        )
    if payload.get("failures"):
        lines.extend(
            ["", "## Failures", *[f"- {item}" for item in payload["failures"]]]
        )
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
            "board_sha256": (
                l42.l30.sha256_file(board_path) if board_path.is_file() else None
            ),
        }
    )
    l42.l30.atomic_write(args.json.resolve(), l42.l30.canonical_bytes(payload))
    l42.l30.atomic_write(
        args.report.resolve(), report_text(verdict, payload).encode("utf-8")
    )
    print(verdict)
    print(args.report.resolve())
    print(args.json.resolve())
    return 0 if verdict == "ADOPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
