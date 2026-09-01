"""Independently verify and classify the frozen L42 harmonic age board."""

from __future__ import annotations

import argparse
import math
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.verify_l30_white_chromatic_field as l30

BOARD_SCHEMA = "cassi.l42.harmonic-age-ladder-board.v1"
TRACE_SCHEMA = "cassi.l42.harmonic-age-ladder-traces.v1"
VERIFICATION_SCHEMA = "cassi.l42.harmonic-age-ladder-verification.v1"
LAYOUT_PROFILE = "cassi.qi-cyclic-chromatic-coordinate-native.v1"
OPERATOR_PROFILE = "cassi.qi-harmonic-age-ladder.v1"
PROJECTION_PROFILE = "cassi.qi-cyclic-chromatic-projection.v1"
AGE_HARMONICS = np.asarray((1, 2, 3, 4, 5, 6, 0), dtype=np.int64)
PREREGISTRATION = ROOT / "designs" / "L42-HARMONIC-AGE-LADDER-PREREG.md"
DEFAULT_BOARD = ROOT / "_diag" / "l42-harmonic-age-ladder" / "l42-board.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "l42-harmonic-age-ladder"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L42-HARMONIC-AGE-LADDER-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l42-verification.json"
EXPECTED_SOURCES = {
    "designs/L42-HARMONIC-AGE-LADDER-PREREG.md",
    "cassi_white_chromatic_field.py",
    "cassi_cyclic_chromatic_field.py",
    "cassi_harmonic_age_field.py",
    "verification/run_l30_white_chromatic_field.py",
    "verification/verify_l30_white_chromatic_field.py",
    "verification/run_l31_cyclic_chromatic_field.py",
    "verification/verify_l31_cyclic_chromatic_field.py",
    "verification/run_l42_harmonic_age_field.py",
    "verification/verify_l42_harmonic_age_field.py",
}
L30_SOURCES = {
    "designs/L30-WHITE-CHROMATIC-FIELD-PREREG.md",
    "cassi_white_chromatic_field.py",
    "verification/run_l30_white_chromatic_field.py",
    "verification/verify_l30_white_chromatic_field.py",
}
_BASE_RECOMPUTE_READOUT = l30.recompute_readout


def native_coordinates_from_field(
    field: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    parts = field.reshape(l30.CHANNELS, 9, l30.MODES, field.shape[2])
    return (
        parts[:, 0, : l30.WIDTH] + 1j * parts[:, 1, : l30.WIDTH],
        parts[:, 2, : l30.WIDTH] + 1j * parts[:, 3, : l30.WIDTH],
        parts[:, 4, : l30.WIDTH] + 1j * parts[:, 5, : l30.WIDTH],
        parts[:, 6, : l30.WIDTH] + 1j * parts[:, 7, : l30.WIDTH],
    )


def independent_age_scores(
    differential: np.ndarray, codebook: np.ndarray
) -> np.ndarray:
    d = torch.from_numpy(differential)
    parts = torch.from_numpy(codebook)
    u = torch.complex(parts[..., 0], parts[..., 1])
    real_dtype = d.real.dtype
    angle = (
        2.0
        * math.pi
        * torch.arange(l30.CHANNELS, dtype=real_dtype)
        / float(l30.CHANNELS)
    )
    phase = torch.complex(torch.cos(angle), torch.sin(angle))
    harmonics = torch.tensor(AGE_HARMONICS, dtype=torch.int64)
    basis = phase.conj()[None, :].pow(harmonics[:, None]) / math.sqrt(
        l30.CHANNELS
    )
    collapsed = torch.einsum("hc,cwb->hwb", basis, d)
    coefficients = torch.einsum(
        "aw,hwb->hba", u.conj(), collapsed
    ) / float(l30.WIDTH)
    return coefficients.abs().square().permute(1, 0, 2).numpy()


def aggregate_harmonics(
    result: dict[str, np.ndarray], age_scores: np.ndarray
) -> dict[str, np.ndarray]:
    age_symbols = np.argmax(age_scores, axis=2).astype(np.int64)
    age_max = np.max(age_scores, axis=2)
    age_available = result["available"][:, None] & (
        age_max >= np.float32(1.0e-8)
    )
    scores = np.max(
        age_scores / np.maximum(age_max, np.float32(1.0e-8))[:, :, None],
        axis=1,
    ).astype(np.float32)
    for row in range(scores.shape[0]):
        if not result["available"][row]:
            scores[row] = result["scores"][row]
            continue
        for age in range(l30.CHANNELS - 1, -1, -1):
            if age_available[row, age]:
                scores[row, age_symbols[row, age]] = np.float32(8 - age)
    result.update(
        {
            "scores": scores,
            "symbols": age_symbols[:, 0],
            "age_scores": age_scores,
            "age_symbols": age_symbols,
            "age_available": age_available,
        }
    )
    return result


def harmonic_readout(
    differential: np.ndarray, codebook: np.ndarray
) -> dict[str, np.ndarray]:
    return aggregate_harmonics(
        dict(_BASE_RECOMPUTE_READOUT(differential, codebook)),
        independent_age_scores(differential, codebook),
    )


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


def verify_board(
    board_path: Path, *, allow_smoke_device: bool = False
) -> tuple[str, dict[str, Any]]:
    board = l30.load_json(board_path)
    l30.need(board.get("schema_id") == BOARD_SCHEMA, "board schema mismatch")
    l30.need(board.get("status") == "COMPLETE", "board is not COMPLETE")
    l30.need(board.get("layout_profile_id") == LAYOUT_PROFILE, "layout identity mismatch")
    l30.need(board.get("operator_profile_id") == OPERATOR_PROFILE, "operator identity mismatch")
    l30.need(
        board.get("projection_profile_id") == PROJECTION_PROFILE,
        "projection identity mismatch",
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
    constants = l30.mapping(board.get("constants"), "constants")
    l30.need(constants.get("age_harmonics") == AGE_HARMONICS.tolist(), "age harmonics mismatch")
    l30.need(
        constants.get("age_ordinal_slots") == [8, 7, 6, 5, 4, 3, 2],
        "age ordinal slots mismatch",
    )
    l30.need(constants.get("four_blank_ticks") == 8, "four-arm blank schedule mismatch")
    trace_path = sibling_artifact(
        board_path, board.get("trace"), "l42-traces.npz", "trace"
    )
    png_path = sibling_artifact(
        board_path, board.get("projection"), "l42-projection.png", "projection"
    )

    with np.load(trace_path, allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    required = {
        "task_read_age_scores": (8, 8, 7, 260),
        "task_read_age_symbols": (8, 8, 7),
        "task_read_age_available": (8, 8, 7),
        "pre_readout_age_scores": (8, 7, 260),
        "pre_readout_age_symbols": (8, 7),
        "pre_readout_age_available": (8, 7),
        "four_sequences": (8, 4),
        "four_age_harmonics": (7,),
        "four_post_d": (4, 7, 1024, 8),
        "four_post_scores": (4, 8, 260),
        "four_post_symbols": (4, 8),
        "four_post_available": (4, 8),
        "four_post_age_scores": (4, 8, 7, 260),
        "four_post_age_symbols": (4, 8, 7),
        "four_post_age_available": (4, 8, 7),
        "four_energy": (4, 7, 8),
        "four_input_energy_drift": (4, 8),
        "four_clamp_count": (4,),
        "four_blank_energy": (8, 7, 8),
        "four_blank_input_energy_drift": (8, 8),
        "four_blank_clamp_count": (8,),
        "four_blank_final_d": (7, 1024, 8),
        "four_blank_final_field": (7, 9 * 2048, 8),
        "four_blank_final_scores": (8, 260),
        "four_blank_final_symbols": (8,),
        "four_blank_final_available": (8,),
        "four_blank_final_age_scores": (8, 7, 260),
        "four_blank_final_age_symbols": (8, 7),
        "four_blank_final_age_available": (8, 7),
        "four_lift_pre_c": (7, 1024, 8),
        "four_lift_pre_d": (7, 1024, 8),
        "four_lift_pre_vc": (7, 1024, 8),
        "four_lift_pre_vd": (7, 1024, 8),
        "four_lift_post_c": (7, 1024, 8),
        "four_lift_post_d": (7, 1024, 8),
        "four_lift_post_vc": (7, 1024, 8),
        "four_lift_post_vd": (7, 1024, 8),
        "four_lift_energy_before": (7, 8),
        "four_lift_energy_after": (7, 8),
    }
    for name, shape in required.items():
        l30.need(name in arrays and arrays[name].shape == shape, f"trace shape mismatch: {name}")
    for name, value in arrays.items():
        if np.issubdtype(value.dtype, np.number):
            l30.need(bool(np.isfinite(value).all()), f"trace contains nonfinite values: {name}")
    l30.need(
        np.array_equal(arrays["four_age_harmonics"], AGE_HARMONICS),
        "trace age harmonics mismatch",
    )
    packed = arrays["four_blank_final_field"].reshape(7, 9, 2048, 8)
    l30.need(
        int(np.count_nonzero(packed[:, :, 1024:, :])) == 0,
        "four-arm inactive modes changed",
    )

    codebook = arrays["codebook"]
    for index in range(8):
        independent = independent_age_scores(arrays["task_read_d"][index], codebook)
        actual_scores = arrays["task_read_age_scores"][index]
        l30.need(
            np.allclose(actual_scores, independent, atol=3.0e-5, rtol=2.0e-4),
            f"independent task age-score mismatch: slot {index}",
        )
        expected = aggregate_harmonics(
            dict(
                _BASE_RECOMPUTE_READOUT(
                    arrays["task_read_d"][index], codebook
                )
            ),
            actual_scores,
        )
        for name in ("age_symbols", "age_available"):
            l30.need(
                np.array_equal(
                    arrays[f"task_read_{name}"][index], expected[name]
                ),
                f"task {name} mismatch: slot {index}",
            )
    independent_pre = independent_age_scores(arrays["pre_target_d"], codebook)
    l30.need(
        np.allclose(
            arrays["pre_readout_age_scores"],
            independent_pre,
            atol=3.0e-5,
            rtol=2.0e-4,
        ),
        "independent pre-target age-score mismatch",
    )
    expected_pre = aggregate_harmonics(
        dict(_BASE_RECOMPUTE_READOUT(arrays["pre_target_d"], codebook)),
        arrays["pre_readout_age_scores"],
    )
    for name in ("age_symbols", "age_available"):
        l30.need(
            np.array_equal(arrays[f"pre_readout_{name}"], expected_pre[name]),
            f"pre-target {name} mismatch",
        )

    mechanical_failures: list[str] = []
    with tempfile.TemporaryDirectory(
        prefix=".l42-verify-", dir=board_path.parent
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
                    for relative in L30_SOURCES
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
        compat_board = temporary / "l30-board.json"
        l30.atomic_write(compat_board, l30.canonical_bytes(compat))
        previous = (
            l30.TRACE_SCHEMA,
            l30.coordinates_from_field,
            l30.recompute_readout,
        )
        try:
            l30.TRACE_SCHEMA = TRACE_SCHEMA
            l30.coordinates_from_field = native_coordinates_from_field
            l30.recompute_readout = harmonic_readout
            l30.verify_board(
                compat_board, allow_smoke_device=allow_smoke_device
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
    for position in range(4):
        expected = harmonic_readout(arrays["four_post_d"][position], codebook)
        for name in (
            "scores",
            "symbols",
            "available",
            "age_scores",
            "age_symbols",
            "age_available",
        ):
            actual = arrays[f"four_post_{name}"][position]
            l30.need(
                actual.shape == expected[name].shape
                and np.allclose(actual, expected[name], atol=3.0e-5, rtol=2.0e-4),
                f"four-deposit readout mismatch: {name} position {position}",
            )
    final_expected = harmonic_readout(arrays["four_blank_final_d"], codebook)
    for name in (
        "scores",
        "symbols",
        "available",
        "age_scores",
        "age_symbols",
        "age_available",
    ):
        actual = arrays[f"four_blank_final_{name}"]
        l30.need(
            actual.shape == final_expected[name].shape
            and np.allclose(actual, final_expected[name], atol=3.0e-5, rtol=2.0e-4),
            f"four-deposit blank readout mismatch: {name}",
        )

    phase = np.exp(2j * math.pi * np.arange(7) / 7)[:, None, None]
    l30.need(
        np.array_equal(arrays["four_lift_pre_c"], arrays["four_lift_post_c"]),
        "harmonic lift changed common position",
    )
    l30.need(
        np.array_equal(arrays["four_lift_pre_vc"], arrays["four_lift_post_vc"]),
        "harmonic lift changed common velocity",
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
    l30.need(
        np.allclose(
            arrays["four_lift_energy_before"],
            arrays["four_lift_energy_after"],
            atol=3.0e-6,
            rtol=3.0e-6,
        ),
        "harmonic lift changed dynamic energy",
    )

    expected_sequences = np.column_stack(
        (
            l30.TARGETS,
            l30.DISTRACTORS,
            np.roll(l30.TARGETS, -1),
            np.roll(l30.DISTRACTORS, -1),
        )
    )
    l30.need(
        np.array_equal(arrays["four_sequences"], expected_sequences),
        "four-deposit schedule mismatch",
    )
    immediate_accuracy = float(
        np.mean(arrays["four_post_symbols"] == expected_sequences.T)
    )
    expected_reverse = np.flip(expected_sequences, axis=1)
    post_top4 = np.argsort(
        -arrays["four_post_scores"][3], axis=1, kind="stable"
    )[:, :4]
    blank_top4 = np.argsort(
        -arrays["four_blank_final_scores"], axis=1, kind="stable"
    )[:, :4]
    post_accuracy = float(np.mean(post_top4 == expected_reverse))
    blank_accuracy = float(np.mean(blank_top4 == expected_reverse))
    occupied_mask = np.zeros((8, 7), dtype=np.bool_)
    occupied_mask[:, :4] = True
    post_occupancy = np.array_equal(
        arrays["four_post_age_available"][3], occupied_mask
    )
    blank_occupancy = np.array_equal(
        arrays["four_blank_final_age_available"], occupied_mask
    )
    unused_max = float(
        max(
            arrays["four_post_age_scores"][3, :, 4:].max(),
            arrays["four_blank_final_age_scores"][:, 4:].max(),
        )
    )
    clamp_count = int(
        arrays["four_clamp_count"].sum()
        + arrays["four_blank_clamp_count"].sum()
    )
    maximum_energy = float(
        max(
            np.mean(arrays["four_energy"], axis=1).max(),
            np.mean(arrays["four_blank_energy"], axis=1).max(),
        )
    )
    maximum_drift = float(
        max(
            np.abs(arrays["four_input_energy_drift"]).max(),
            np.abs(arrays["four_blank_input_energy_drift"]).max(),
        )
    )
    l30.need(maximum_energy <= 1.05, "four-deposit energy budget gate")
    l30.need(maximum_drift <= 5.0e-5, "four-deposit input drift gate")

    pre_readout = harmonic_readout(arrays["pre_target_d"], codebook)
    target_ranks = np.stack(
        [
            l30.ranks(arrays["task_read_scores"][index], l30.TARGETS)
            for index in range(8)
        ]
    )
    distractor_ranks = np.stack(
        [
            l30.ranks(arrays["task_read_scores"][index], l30.DISTRACTORS)
            for index in range(8)
        ]
    )
    inherited_maximum_energy = float(
        max(
            np.mean(arrays["task_energy"], axis=1).max(),
            np.mean(arrays["blank_energy"], axis=1).max(),
            np.mean(arrays["stress_energy"], axis=1).max(),
        )
    )
    inherited_clamp_count = int(
        arrays["task_clamp_count"].sum()
        + arrays["blank_clamp_count"].sum()
        + arrays["stress_clamp_count"].sum()
        + int(arrays["zero_clamp_count"])
        + int(arrays["pre_target_clamp_count"])
    )
    first_dynamic = arrays["first_heartbeat_dynamic_energy"]
    first_total = float(np.mean(first_dynamic))
    values = {
        "exact_pre_target_accuracy": float(
            np.mean(pre_readout["symbols"] == l30.TARGETS)
        ),
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
        "maximum_input_energy_drift": float(
            max(
                np.abs(arrays["task_input_energy_drift"]).max(),
                np.abs(arrays["zero_drift"]).max(),
                np.abs(arrays["pre_target_drift"]).max(),
            )
        ),
        "clamp_count": inherited_clamp_count,
        "maximum_total_mean_dynamic_energy": inherited_maximum_energy,
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

    canonical = l30.mapping(
        l30.mapping(board.get("arms"), "arms").get("canonical"),
        "canonical arm",
    )
    declared = l30.mapping(
        canonical.get("four_deposit_metrics"), "four-deposit metrics"
    )
    values.update(
        {
            "immediate_emitted_symbol_accuracy": immediate_accuracy,
            "reverse_top4_accuracy_after_fourth": post_accuracy,
            "reverse_top4_accuracy_after_blank": blank_accuracy,
            "unused_age_max_score": unused_max,
            "maximum_four_arm_dynamic_energy": maximum_energy,
            "maximum_four_arm_input_energy_drift": maximum_drift,
            "four_arm_clamp_count": clamp_count,
        }
    )
    for name in (
        "immediate_emitted_symbol_accuracy",
        "reverse_top4_accuracy_after_fourth",
        "reverse_top4_accuracy_after_blank",
    ):
        l30.close(float(declared.get(name, -1.0)), values[name], f"metric consistency: {name}")
    l30.close(
        float(declared.get("maximum_total_mean_dynamic_energy", -1.0)),
        maximum_energy,
        "metric consistency: maximum four-arm energy",
    )
    l30.close(
        float(declared.get("maximum_absolute_input_energy_drift", -1.0)),
        maximum_drift,
        "metric consistency: maximum four-arm drift",
    )
    l30.need(declared.get("clamp_count") == clamp_count, "metric consistency: four-arm clamps")

    functional = {
        "exact_pre_target_accuracy": values["exact_pre_target_accuracy"] == 1.0,
        "tick0_target_accuracy": values["tick0_target_accuracy"] >= 0.875,
        "target_mrr_pre_distractor": (
            values["target_mrr_pre_distractor"] >= 0.75
        ),
        "tick8_distractor_accuracy": (
            values["tick8_distractor_accuracy"] >= 0.75
        ),
        "distractor_mrr_long": values["distractor_mrr_long"] >= 0.25,
        "original_target_mrr_long": (
            values["original_target_mrr_long"] >= 0.05
        ),
        "tick0_white_coherence": values["tick0_white_coherence"] >= 0.90,
        "blank_max_abs_d": values["blank_max_abs_d"] <= 1.0e-6,
        "stress_path": (
            values["stress_clamp_count"] == 0
            and values["maximum_total_mean_dynamic_energy"] <= 1.05
        ),
    }
    functional.update(
        {
            "immediate_emitted_symbol_accuracy": immediate_accuracy == 1.0,
            "reverse_top4_accuracy_after_fourth": post_accuracy == 1.0,
            "reverse_top4_accuracy_after_blank": blank_accuracy == 1.0,
            "four_slot_occupancy_and_safety": (
                post_occupancy
                and blank_occupancy
                and unused_max < 1.0e-8
                and clamp_count == 0
            ),
        }
    )
    l30.need(len(functional) == 13, "functional condition count mismatch")
    verdict = (
        "FAIL"
        if mechanical_failures
        else ("ADOPT" if all(functional.values()) else "REJECT")
    )
    diagnostics = {
        "expected_reverse_sequences": expected_reverse.tolist(),
        "fourth_deposit_emitted_symbols": arrays["four_post_symbols"][3].tolist(),
        "fourth_deposit_top4": post_top4.tolist(),
        "blank_top4": blank_top4.tolist(),
        "fourth_age_symbols": arrays["four_post_age_symbols"][3].tolist(),
        "fourth_age_available": arrays["four_post_age_available"][3].tolist(),
        "blank_age_symbols": arrays["four_blank_final_age_symbols"].tolist(),
        "blank_age_available": arrays["four_blank_final_age_available"].tolist(),
    }
    return verdict, {
        "schema_id": VERIFICATION_SCHEMA,
        "verdict": verdict,
        "metrics": values,
        "functional_conditions": functional,
        "diagnostics": diagnostics,
        "failures": mechanical_failures,
    }


def report_text(verdict: str, payload: Mapping[str, Any]) -> str:
    explanation = {
        "ADOPT": "All frozen mechanical and functional gates passed.",
        "REJECT": "Mechanics passed; one or more preregistered functional conditions failed.",
        "INCOMPLETE": "The canonical board was interrupted or unavailable before complete verification.",
        "FAIL": "Evidence integrity or a frozen mechanical gate failed.",
    }[verdict]
    lines = [
        "# L42 Harmonic Age Ladder — Verification",
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
                "## Four-deposit metrics",
                f"- Immediate emitted-symbol accuracy: `{metrics.get('immediate_emitted_symbol_accuracy')}`",
                f"- Reverse top-four accuracy after deposit four: `{metrics.get('reverse_top4_accuracy_after_fourth')}`",
                f"- Reverse top-four accuracy after eight blank ticks: `{metrics.get('reverse_top4_accuracy_after_blank')}`",
                f"- Maximum unused-age score: `{metrics.get('unused_age_max_score')}`",
                f"- Clamp count: `{metrics.get('four_arm_clamp_count')}`",
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
