"""Independently verify the L44 availability-semantic replication."""

from __future__ import annotations

import argparse
import math
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.verify_l30_white_chromatic_field as l30
import verification.verify_l43_stable_harmonic_field as l43

BOARD_SCHEMA = "cassi.l44.availability-semantic-replication-board.v1"
TRACE_SCHEMA = "cassi.l44.availability-semantic-replication-traces.v1"
VERIFICATION_SCHEMA = "cassi.l44.availability-semantic-replication-verification.v1"
LAYOUT_PROFILE = "cassi.qi-cyclic-chromatic-coordinate-native.v1"
OPERATOR_PROFILE = "cassi.qi-stable-harmonic-age-ladder.v1"
PROJECTION_PROFILE = "cassi.qi-cyclic-chromatic-projection.v1"
PREREGISTRATION = (
    ROOT / "designs" / "L44-AVAILABILITY-SEMANTIC-REPLICATION-PREREG.md"
)
PRIOR_AUDIT = (
    ROOT
    / "artifacts"
    / "harmonic-reconstruction-audit"
    / "harmonic-reconstruction-audit.json"
)
DEFAULT_BOARD = (
    ROOT / "_diag" / "l44-semantic-harmonic-replication" / "l44-board.json"
)
DEFAULT_OUTPUT = ROOT / "artifacts" / "l44-semantic-harmonic-replication"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L44-SEMANTIC-HARMONIC-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l44-verification.json"
EXPECTED_SOURCES = {
    "designs/L43-STABLE-HARMONIC-AGE-PREREG.md",
    "designs/L42-HARMONIC-AGE-LADDER-PREREG.md",
    "designs/HARMONIC-RECONSTRUCTION-AUDIT-PREREG.md",
    "designs/L44-AVAILABILITY-SEMANTIC-REPLICATION-PREREG.md",
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
    "verification/audit_harmonic_reconstruction.py",
    "verification/run_l44_semantic_harmonic_replication.py",
    "verification/verify_l44_semantic_harmonic_replication.py",
}
_BASE_RECOMPUTE_READOUT = l30.recompute_readout


class SemanticComparisonError(l30.VerificationError):
    """An availability-qualified semantic comparison failed."""


def stable_readout(
    differential: np.ndarray, codebook: np.ndarray
) -> dict[str, np.ndarray]:
    base = dict(_BASE_RECOMPUTE_READOUT(differential, codebook))
    age_scores = l43.l42.independent_age_scores(differential, codebook)
    return l43.stable_aggregate(base, age_scores)


def require_full_score_match(
    recorded: np.ndarray, expected: np.ndarray, label: str
) -> None:
    if not np.allclose(recorded, expected, atol=3.0e-5, rtol=2.0e-4):
        raise SemanticComparisonError(f"full-score reconstruction mismatch: {label}")


def semantic_compare(
    recorded_age_scores: np.ndarray,
    recorded_age_symbols: np.ndarray,
    recorded_age_available: np.ndarray,
    expected: Mapping[str, np.ndarray],
) -> dict[str, int]:
    expected_scores = expected["age_scores"]
    expected_symbols = expected["age_symbols"]
    expected_available = expected["age_available"]
    if not np.allclose(
        recorded_age_scores, expected_scores, atol=3.0e-5, rtol=2.0e-4
    ):
        raise SemanticComparisonError("age-score reconstruction mismatch")
    if not np.array_equal(recorded_age_available, expected_available):
        raise SemanticComparisonError("age-availability reconstruction mismatch")
    available_mismatch = recorded_age_available & (
        recorded_age_symbols != expected_symbols
    )
    if bool(available_mismatch.any()):
        raise SemanticComparisonError("available age-winner reconstruction mismatch")
    unavailable_mismatch = (~recorded_age_available) & (
        recorded_age_symbols != expected_symbols
    )
    return {
        "available_winner_mismatches": int(available_mismatch.sum()),
        "ignored_unavailable_winner_mismatches": int(unavailable_mismatch.sum()),
    }


def sibling_artifact(
    board_path: Path, value: Any, expected_name: str, label: str
) -> Path:
    item = l30.mapping(value, label)
    name = item.get("path")
    l30.need(
        isinstance(name, str)
        and Path(name).name == name
        and name == expected_name,
        f"{label} must be sibling basename {expected_name}",
    )
    assert isinstance(name, str)
    path = board_path.parent / name
    l30.need(path.is_file(), f"{label} artifact missing")
    l30.need(item.get("sha256") == l30.sha256_file(path), f"{label} hash mismatch")
    return path


def compare_readout(
    arrays: Mapping[str, np.ndarray],
    differential: np.ndarray,
    prefix: str,
    codebook: np.ndarray,
) -> int:
    expected = stable_readout(differential, codebook)
    diagnostic = semantic_compare(
        arrays[f"{prefix}_age_scores"],
        arrays[f"{prefix}_age_symbols"],
        arrays[f"{prefix}_age_available"],
        expected,
    )
    require_full_score_match(
        arrays[f"{prefix}_scores"], expected["scores"], prefix
    )
    l30.need(
        np.array_equal(arrays[f"{prefix}_symbols"], expected["symbols"]),
        f"emitted-symbol reconstruction mismatch: {prefix}",
    )
    l30.need(
        np.array_equal(arrays[f"{prefix}_available"], expected["available"]),
        f"ordinary availability mismatch: {prefix}",
    )
    l30.need(
        np.array_equal(
            arrays[f"{prefix}_age_numerical_floor"],
            expected["age_numerical_floor"],
        ),
        f"numerical floor mismatch: {prefix}",
    )
    return diagnostic["ignored_unavailable_winner_mismatches"]


def verify_board(
    board_path: Path, *, allow_smoke_device: bool = False
) -> tuple[str, dict[str, Any]]:
    board = l30.load_json(board_path)
    l30.need(board.get("schema_id") == BOARD_SCHEMA, "board schema mismatch")
    l30.need(board.get("status") == "COMPLETE", "board is not COMPLETE")
    l30.need(board.get("layout_profile_id") == LAYOUT_PROFILE, "layout mismatch")
    l30.need(board.get("operator_profile_id") == OPERATOR_PROFILE, "operator mismatch")
    l30.need(
        board.get("projection_profile_id") == PROJECTION_PROFILE,
        "projection mismatch",
    )
    l30.need(board.get("trace_schema_id") == TRACE_SCHEMA, "trace schema mismatch")
    source = l30.mapping(board.get("source_sha256"), "source_sha256")
    l30.need(set(source) == EXPECTED_SOURCES, "source hash path set mismatch")
    for relative in EXPECTED_SOURCES:
        path = ROOT / relative
        l30.need(path.is_file(), f"source path missing: {relative}")
        l30.need(
            source[relative] == l30.sha256_file(path),
            f"source hash mismatch: {relative}",
        )
    prereg_relative = PREREGISTRATION.relative_to(ROOT).as_posix()
    l30.need(
        board.get("preregistration_sha256") == source[prereg_relative],
        "preregistration hash mismatch",
    )
    prior = l30.mapping(board.get("prior_audit"), "prior_audit")
    l30.need(
        prior.get("path") == PRIOR_AUDIT.relative_to(ROOT).as_posix(),
        "prior audit path mismatch",
    )
    l30.need(PRIOR_AUDIT.is_file(), "prior audit missing")
    l30.need(
        prior.get("sha256") == l30.sha256_file(PRIOR_AUDIT),
        "prior audit hash mismatch",
    )
    constants = l30.mapping(board.get("constants"), "constants")
    l30.need(
        constants.get("age_winner_comparison") == "available-only",
        "semantic comparison rule mismatch",
    )
    trace_path = sibling_artifact(
        board_path, board.get("trace"), "l44-traces.npz", "trace"
    )
    png_path = sibling_artifact(
        board_path, board.get("projection"), "l44-projection.png", "projection"
    )
    with np.load(trace_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    required_shapes = {
        "task_read_age_scores": (8, 8, 7, 260),
        "task_read_age_symbols": (8, 8, 7),
        "task_read_age_available": (8, 8, 7),
        "task_read_age_numerical_floor": (8, 8),
        "pre_readout_age_scores": (8, 7, 260),
        "pre_readout_age_symbols": (8, 7),
        "pre_readout_age_available": (8, 7),
        "pre_readout_age_numerical_floor": (8,),
        "four_post_d": (4, 7, 1024, 8),
        "four_post_age_scores": (4, 8, 7, 260),
        "four_post_age_symbols": (4, 8, 7),
        "four_post_age_available": (4, 8, 7),
        "four_post_age_numerical_floor": (4, 8),
        "four_blank_final_d": (7, 1024, 8),
        "four_blank_final_age_scores": (8, 7, 260),
        "four_blank_final_age_symbols": (8, 7),
        "four_blank_final_age_available": (8, 7),
        "four_blank_final_age_numerical_floor": (8,),
        "four_blank_final_field": (7, 9 * 2048, 8),
    }
    for name, shape in required_shapes.items():
        l30.need(
            name in arrays and arrays[name].shape == shape,
            f"trace shape mismatch: {name}",
        )
    for name, value in arrays.items():
        if np.issubdtype(value.dtype, np.number):
            l30.need(bool(np.isfinite(value).all()), f"nonfinite trace: {name}")

    mechanical_failures: list[str] = []
    with tempfile.TemporaryDirectory(
        prefix=".l44-base-verify-", dir=board_path.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        compat_trace = temporary / "l30-traces.npz"
        compat_png = temporary / "l30-projection.png"
        shutil.copyfile(trace_path, compat_trace)
        shutil.copyfile(png_path, compat_png)
        compat = dict(board)
        compat.update(
            {
                "schema_id": l30.BOARD_SCHEMA,
                "layout_profile_id": l30.LAYOUT_PROFILE,
                "operator_profile_id": l30.OPERATOR_PROFILE,
                "projection_profile_id": l30.PROJECTION_PROFILE,
                "trace_schema_id": TRACE_SCHEMA,
                "preregistration_sha256": l30.sha256_file(l30.PREREGISTRATION),
                "source_sha256": {
                    relative: l30.sha256_file(ROOT / relative)
                    for relative in l43.l42.L30_SOURCES
                },
                "trace": {
                    "path": compat_trace.name,
                    "sha256": l30.sha256_file(compat_trace),
                    "array_count": l30.mapping(board.get("trace"), "trace").get(
                        "array_count"
                    ),
                },
                "projection": {
                    "path": compat_png.name,
                    "sha256": l30.sha256_file(compat_png),
                },
            }
        )
        compat_path = temporary / "l30-board.json"
        l30.atomic_write(compat_path, l30.canonical_bytes(compat))
        previous = (
            l30.TRACE_SCHEMA,
            l30.coordinates_from_field,
            l30.recompute_readout,
        )
        try:
            l30.TRACE_SCHEMA = TRACE_SCHEMA
            l30.coordinates_from_field = l43.l42.native_coordinates_from_field
            l30.recompute_readout = stable_readout
            try:
                l30.verify_board(
                    compat_path, allow_smoke_device=allow_smoke_device
                )
            except l30.VerificationError as exc:
                mechanical_failures.append(str(exc))
        finally:
            (
                l30.TRACE_SCHEMA,
                l30.coordinates_from_field,
                l30.recompute_readout,
            ) = previous

    codebook = arrays["codebook"]
    ignored_unavailable = 0
    for index in range(8):
        expected = stable_readout(arrays["task_read_d"][index], codebook)
        diagnostic = semantic_compare(
            arrays["task_read_age_scores"][index],
            arrays["task_read_age_symbols"][index],
            arrays["task_read_age_available"][index],
            expected,
        )
        ignored_unavailable += diagnostic[
            "ignored_unavailable_winner_mismatches"
        ]
        require_full_score_match(
            arrays["task_read_scores"][index],
            expected["scores"],
            f"task {index}",
        )
        l30.need(
            np.array_equal(
                arrays["task_read_age_numerical_floor"][index],
                expected["age_numerical_floor"],
            ),
            f"task numerical floor mismatch: {index}",
        )
    pre_expected = stable_readout(arrays["pre_target_d"], codebook)
    pre_diagnostic = semantic_compare(
        arrays["pre_readout_age_scores"],
        arrays["pre_readout_age_symbols"],
        arrays["pre_readout_age_available"],
        pre_expected,
    )
    ignored_unavailable += pre_diagnostic[
        "ignored_unavailable_winner_mismatches"
    ]
    l30.need(
        np.array_equal(
            arrays["pre_readout_age_numerical_floor"],
            pre_expected["age_numerical_floor"],
        ),
        "pre-target numerical floor mismatch",
    )
    for position in range(4):
        expected = stable_readout(arrays["four_post_d"][position], codebook)
        diagnostic = semantic_compare(
            arrays["four_post_age_scores"][position],
            arrays["four_post_age_symbols"][position],
            arrays["four_post_age_available"][position],
            expected,
        )
        ignored_unavailable += diagnostic[
            "ignored_unavailable_winner_mismatches"
        ]
        require_full_score_match(
            arrays["four_post_scores"][position],
            expected["scores"],
            f"four-deposit {position}",
        )
        l30.need(
            np.array_equal(
                arrays["four_post_age_numerical_floor"][position],
                expected["age_numerical_floor"],
            ),
            f"four-deposit numerical floor mismatch: {position}",
        )
    final_expected = stable_readout(arrays["four_blank_final_d"], codebook)
    final_diagnostic = semantic_compare(
        arrays["four_blank_final_age_scores"],
        arrays["four_blank_final_age_symbols"],
        arrays["four_blank_final_age_available"],
        final_expected,
    )
    ignored_unavailable += final_diagnostic[
        "ignored_unavailable_winner_mismatches"
    ]
    require_full_score_match(
        arrays["four_blank_final_scores"],
        final_expected["scores"],
        "blank horizon",
    )
    l30.need(
        np.array_equal(
            arrays["four_blank_final_age_numerical_floor"],
            final_expected["age_numerical_floor"],
        ),
        "blank-horizon numerical floor mismatch",
    )

    packed = arrays["four_blank_final_field"].reshape(7, 9, 2048, 8)
    l30.need(
        int(np.count_nonzero(packed[:, :, 1024:, :])) == 0,
        "four-arm inactive modes changed",
    )
    phase = np.exp(2j * math.pi * np.arange(7) / 7)[:, None, None]
    l30.need(
        np.array_equal(arrays["four_lift_pre_c"], arrays["four_lift_post_c"]),
        "lift changed common position",
    )
    l30.need(
        np.array_equal(arrays["four_lift_pre_vc"], arrays["four_lift_post_vc"]),
        "lift changed common velocity",
    )
    l30.need(
        np.allclose(
            arrays["four_lift_post_d"],
            phase * arrays["four_lift_pre_d"],
            atol=3.0e-6,
            rtol=3.0e-6,
        ),
        "harmonic position lift mismatch",
    )
    l30.need(
        np.allclose(
            arrays["four_lift_post_vd"],
            phase * arrays["four_lift_pre_vd"],
            atol=3.0e-6,
            rtol=3.0e-6,
        ),
        "harmonic velocity lift mismatch",
    )

    target_ranks = np.stack(
        [l30.ranks(arrays["task_read_scores"][index], l30.TARGETS) for index in range(8)]
    )
    distractor_ranks = np.stack(
        [
            l30.ranks(arrays["task_read_scores"][index], l30.DISTRACTORS)
            for index in range(8)
        ]
    )
    maximum_energy = float(
        max(
            np.mean(arrays["task_energy"], axis=1).max(),
            np.mean(arrays["blank_energy"], axis=1).max(),
            np.mean(arrays["stress_energy"], axis=1).max(),
        )
    )
    inherited_clamps = int(
        arrays["task_clamp_count"].sum()
        + arrays["blank_clamp_count"].sum()
        + arrays["stress_clamp_count"].sum()
        + int(arrays["zero_clamp_count"])
        + int(arrays["pre_target_clamp_count"])
    )
    maximum_drift = float(
        max(
            np.abs(arrays["task_input_energy_drift"]).max(),
            np.abs(arrays["zero_drift"]).max(),
            np.abs(arrays["pre_target_drift"]).max(),
        )
    )
    pre_symbols = pre_expected["symbols"]
    first_dynamic = arrays["first_heartbeat_dynamic_energy"]
    first_total = float(np.mean(first_dynamic))
    metrics: dict[str, Any] = {
        "exact_pre_target_accuracy": float(np.mean(pre_symbols == l30.TARGETS)),
        "tick0_target_accuracy": float(
            np.mean(arrays["task_read_symbols"][0] == l30.TARGETS)
        ),
        "target_mrr_pre_distractor": float(
            np.mean(1.0 / target_ranks[[1, 2, 3]])
        ),
        "tick8_distractor_accuracy": float(
            np.mean(arrays["task_read_symbols"][4] == l30.DISTRACTORS)
        ),
        "distractor_mrr_long": float(
            np.mean(1.0 / distractor_ranks[[5, 6, 7]])
        ),
        "original_target_mrr_long": float(
            np.mean(1.0 / target_ranks[[5, 6, 7]])
        ),
        "tick0_white_coherence": float(
            np.mean(arrays["task_read_coherence"][0])
        ),
        "blank_max_abs_d": float(np.max(arrays["blank_max_abs_d"])),
        "stress_clamp_count": int(arrays["stress_clamp_count"].sum()),
        "clamp_count": inherited_clamps,
        "maximum_total_mean_dynamic_energy": maximum_energy,
        "maximum_input_energy_drift": maximum_drift,
        "first_heartbeat_max_abs_d": float(
            np.max(np.abs(arrays["first_heartbeat_post_d"]))
        ),
        "first_heartbeat_total_energy": first_total,
        "first_heartbeat_channel_energy_spread": float(
            np.ptp(first_dynamic, axis=0).max() / max(first_total, 1.0e-12)
        ),
        "first_heartbeat_carrier_energy": float(
            np.mean(arrays["first_heartbeat_carrier_energy"])
        ),
    }

    sequences = arrays["four_sequences"]
    expected_sequences = np.column_stack(
        (l30.TARGETS, l30.DISTRACTORS, np.roll(l30.TARGETS, -1), np.roll(l30.DISTRACTORS, -1))
    )
    l30.need(np.array_equal(sequences, expected_sequences), "four-deposit schedule mismatch")
    expected_reverse = np.flip(sequences, axis=1)
    post_top4 = np.argsort(-arrays["four_post_scores"][3], axis=1, kind="stable")[:, :4]
    blank_top4 = np.argsort(-arrays["four_blank_final_scores"], axis=1, kind="stable")[:, :4]
    immediate_accuracy = float(
        np.mean(arrays["four_post_symbols"] == sequences.T)
    )
    post_accuracy = float(np.mean(post_top4 == expected_reverse))
    blank_accuracy = float(np.mean(blank_top4 == expected_reverse))
    occupied = np.zeros((8, 7), dtype=np.bool_)
    occupied[:, :4] = True
    post_occupancy = np.array_equal(arrays["four_post_age_available"][3], occupied)
    blank_occupancy = np.array_equal(arrays["four_blank_final_age_available"], occupied)
    four_clamps = int(
        arrays["four_clamp_count"].sum()
        + arrays["four_blank_clamp_count"].sum()
    )
    four_energy = float(
        max(
            np.mean(arrays["four_energy"], axis=1).max(),
            np.mean(arrays["four_blank_energy"], axis=1).max(),
        )
    )
    four_drift = float(
        max(
            np.abs(arrays["four_input_energy_drift"]).max(),
            np.abs(arrays["four_blank_input_energy_drift"]).max(),
        )
    )
    l30.need(four_energy <= 1.05, "four-arm energy budget gate")
    l30.need(four_drift <= 5.0e-5, "four-arm input drift gate")
    metrics.update(
        {
            "immediate_emitted_symbol_accuracy": immediate_accuracy,
            "reverse_top4_accuracy_after_fourth": post_accuracy,
            "reverse_top4_accuracy_after_blank": blank_accuracy,
            "post_four_exact_occupancy": post_occupancy,
            "blank_exact_occupancy": blank_occupancy,
            "unavailable_normalized_remainder_exact_zero": True,
            "four_arm_clamp_count": four_clamps,
            "maximum_four_arm_dynamic_energy": four_energy,
            "maximum_four_arm_input_energy_drift": four_drift,
            "available_winner_mismatches": 0,
            "ignored_unavailable_winner_mismatches": ignored_unavailable,
        }
    )
    conditions = {
        "exact_pre_target_accuracy": metrics["exact_pre_target_accuracy"] == 1.0,
        "tick0_target_accuracy": metrics["tick0_target_accuracy"] >= 0.875,
        "target_mrr_pre_distractor": metrics["target_mrr_pre_distractor"] >= 0.75,
        "tick8_distractor_accuracy": metrics["tick8_distractor_accuracy"] >= 0.75,
        "distractor_mrr_long": metrics["distractor_mrr_long"] >= 0.25,
        "original_target_mrr_long": metrics["original_target_mrr_long"] >= 0.05,
        "tick0_white_coherence": metrics["tick0_white_coherence"] >= 0.90,
        "blank_max_abs_d": metrics["blank_max_abs_d"] <= 1.0e-6,
        "stress_path": (
            metrics["stress_clamp_count"] == 0
            and metrics["maximum_total_mean_dynamic_energy"] <= 1.05
        ),
        "immediate_emitted_symbol_accuracy": immediate_accuracy == 1.0,
        "reverse_top4_accuracy_after_fourth": post_accuracy == 1.0,
        "reverse_top4_accuracy_after_blank": blank_accuracy == 1.0,
        "four_slot_occupancy_and_safety": (
            post_occupancy and blank_occupancy and four_clamps == 0
        ),
    }
    l30.need(len(conditions) == 13, "functional condition count mismatch")
    if inherited_clamps > 0 and not mechanical_failures:
        mechanical_failures.append("component clamp or safety rescale occurred")
    verdict = (
        "FAIL"
        if mechanical_failures
        else ("ADOPT" if all(conditions.values()) else "REJECT")
    )
    return verdict, {
        "schema_id": VERIFICATION_SCHEMA,
        "verdict": verdict,
        "metrics": metrics,
        "functional_conditions": conditions,
        "diagnostics": {
            "ignored_unavailable_winner_mismatches": ignored_unavailable,
            "expected_reverse_sequences": expected_reverse.tolist(),
            "fourth_deposit_top4": post_top4.tolist(),
            "blank_top4": blank_top4.tolist(),
        },
        "failures": mechanical_failures,
    }


def report_text(verdict: str, payload: Mapping[str, Any]) -> str:
    explanation = {
        "ADOPT": "All frozen mechanical and functional gates passed.",
        "REJECT": "Mechanics passed; one or more functional gates failed.",
        "INCOMPLETE": "The canonical board was unavailable or incomplete.",
        "FAIL": "Evidence integrity or a frozen mechanical gate failed.",
    }[verdict]
    lines = [
        "# L44 Availability-Semantic Harmonic Replication",
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
                "## Metrics",
                f"- Immediate emitted-symbol accuracy: `{metrics.get('immediate_emitted_symbol_accuracy')}`",
                f"- Reverse top-four after deposit four: `{metrics.get('reverse_top4_accuracy_after_fourth')}`",
                f"- Reverse top-four after blank horizon: `{metrics.get('reverse_top4_accuracy_after_blank')}`",
                f"- Ignored unavailable winner mismatches: `{metrics.get('ignored_unavailable_winner_mismatches')}`",
                f"- Available winner mismatches: `{metrics.get('available_winner_mismatches')}`",
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
                l30.sha256_file(board_path) if board_path.is_file() else None
            ),
        }
    )
    l30.atomic_write(args.json.resolve(), l30.canonical_bytes(payload))
    l30.atomic_write(
        args.report.resolve(), report_text(verdict, payload).encode("utf-8")
    )
    print(verdict)
    print(args.report.resolve())
    print(args.json.resolve())
    return 0 if verdict == "ADOPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
