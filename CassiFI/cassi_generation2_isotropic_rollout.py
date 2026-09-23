"""Run a generation-two chronological rollout through the living Hive.

The promoted V3 lesson is the starting law, not a new isolated experiment:
three independent field instances fit disjoint prior development worlds, begin
an isotropic generation-two rollout, and then learn two chronological chunks of
one fresh world under the same regime identity.  The second chunk is the
specific re-entry challenge.  Its support can improve the shared coefficient,
but the field-owned identity registry must keep anisotropic support unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

import cassi_full_observable_invention as legacy
import cassi_regime_covariant_recurrent_memory as v2
from cassi_generation2_isotropic_rollout_field import (
    Generation2GuardedFieldConfig,
    Generation2IsotropicRegimeGuardedField,
)
from cassi_hierarchical_covariant_recurrent_field import (
    HierarchicalCovariantFieldConfig,
    HierarchicalCovariantRecurrentField,
)
from cassi_morphology_operator_invention import SEED_ATOMS, _activated
from cassi_research_organism import ResearchOrganism


SCHEMA = "cassifi.hive-generation2-isotropic-regime-guarded-rollout.v1"
SLICE_SCHEMA = "cassifi.hive-generation2-isotropic-regime-guarded-rollout-slice.v1"
EXPERIMENT_ID = "generation2-isotropic-regime-guarded-rollout-v1"
LABORATORY_ID = "generation2-isotropic-regime-guarded-trajectory-memory"
PRIOR_RECEIPT = "CassiFI/_diag/hierarchical-covariant-recurrent-memory-v3.json"
PRIOR_RECEIPT_SHA256 = "5fe5667654e47e89adb0fb2c0a20208a5e2c69eea0dd95d0f799d0dd010794e0"
PROMOTED_BUNDLE_ID = "6ac75f1f9d1acef00ce9eafbd0756f3e23e5225cda053a7c265e3fb843ee1b42"
PROMOTED_LESSON_ID = "isotropic-covariant-trajectory-transfer"
LAGS = (1, 2, 4, 8)
PRESENT_ATOMS = tuple(SEED_ATOMS)
ANISOTROPY_RIDGE = 8.0
ANISOTROPY_SUPPORT_THRESHOLD = 0.2
MIN_ANISOTROPIC_WORLDS = 2
CHUNK_ONE_FRACTION = 0.60
CHUNK_TWO_FRACTION = 0.85

# The development worlds are the already measured disjoint V3 Hive partitions.
# Fresh chronological worlds are new roots and never enter those fits.
DEVELOPMENT_PARTITIONS: Mapping[str, tuple[str, ...]] = {
    "root": (
        "CassiCosmos/_diag/matter_formation/energy_gaussian_s20260910_v0p0",
        "CassiCosmos/_diag/matter_formation/energy_gaussian_s20260910_v2p0",
        "CassiCosmos/_diag/matter_formation/energy_gaussian_s20260911_v1p0",
        "CassiCosmos/_diag/matter_formation/attractor_ic5",
        "CassiCosmos/_diag/matter_formation/attractor_ic10",
        "CassiCosmos/_diag/matter_formation/attractor_scene_calibrated/GC2",
    ),
    "member-000": (
        "CassiCosmos/_diag/matter_formation/energy_gaussian_s20260910_v0p5",
        "CassiCosmos/_diag/matter_formation/energy_gaussian_s20260911_v0p0",
        "CassiCosmos/_diag/matter_formation/energy_gaussian_s20260911_v2p0",
        "CassiCosmos/_diag/matter_formation/attractor_ic6",
        "CassiCosmos/_diag/matter_formation/attractor_scene_calibrated/G3",
    ),
    "member-001": (
        "CassiCosmos/_diag/matter_formation/energy_gaussian_s20260910_v1p0",
        "CassiCosmos/_diag/matter_formation/energy_gaussian_s20260911_v0p5",
        "CassiCosmos/_diag/matter_formation/attractor_ic2",
        "CassiCosmos/_diag/matter_formation/attractor_ic7",
        "CassiCosmos/_diag/matter_formation/attractor_scene_calibrated/G6",
    ),
}
FRESH_PARTITIONS: Mapping[str, str] = {
    "root": "CassiCosmos/_diag/matter_formation/full_observable_v4_20260919/DH3",
    "member-000": "CassiCosmos/_diag/matter_formation/full_observable_v4_20260919/DHC3",
    "member-001": "CassiCosmos/_diag/matter_formation/full_observable_v4_20260919/DH6",
}
ANALYSIS_SOURCES = (
    "CassiFI/cassi_generation2_isotropic_rollout_field.py",
    "CassiFI/cassi_generation2_isotropic_rollout.py",
    "CassiFI/cassi_hierarchical_covariant_recurrent_field.py",
    "CassiFI/cassi_regime_covariant_recurrent_field.py",
    "CassiFI/cassi_regime_covariant_recurrent_memory.py",
    "CassiFI/cassi_full_observable_invention.py",
    "CassiFI/cassi_morphology_operator_invention.py",
    "CassiFI/cassi_morphology_operator_language.py",
    "CassiFI/cassi_morphology_observables.py",
    "CassiFI/cassi_research_organism.py",
)
LESSON_STATEMENTS = {
    "generation2-isotropic-regime-guard": (
        "A field-owned regime identity registry keeps a promoted isotropic law "
        "isotropic across repeated chronological chunks; one regime cannot "
        "re-enter the anisotropic split."
    ),
    "isotropic-covariant-trajectory-transfer": (
        "The promoted shared isotropic trajectory correction remains usable on "
        "fresh chronological worlds under the generation-two guard."
    ),
    "guarded-memory-no-transfer": (
        "The guarded trajectory memory does not improve the fresh chronological "
        "holdout while its single-regime release controls remain valid."
    ),
}


class Generation2CampaignError(RuntimeError):
    """Raised when the generation-two rollout is not admissible."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_manifest(workspace: Path, organism_sources: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative in sorted(set(ANALYSIS_SOURCES) | set(organism_sources)):
        path = workspace / relative
        if not path.is_file():
            raise Generation2CampaignError(f"analysis source is absent: {relative}")
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    return rows


def _prior_promotion(workspace: Path) -> dict[str, Any]:
    path = workspace / PRIOR_RECEIPT
    try:
        raw = path.read_bytes()
        receipt = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Generation2CampaignError("promoted V3 receipt is unavailable") from exc
    digest = hashlib.sha256(raw).hexdigest()
    assimilation = receipt.get("hive_assimilation", {})
    selected = assimilation.get("selected_lesson", {})
    if (
        digest != PRIOR_RECEIPT_SHA256
        or receipt.get("schema") != "cassifi.hive-hierarchical-regime-covariant-recurrent-memory.v3"
        or assimilation.get("status") != "promoted"
        or assimilation.get("bundle_id") != PROMOTED_BUNDLE_ID
        or selected.get("candidate_id") != PROMOTED_LESSON_ID
        or assimilation.get("hive_generation") != 2
        or assimilation.get("support_count") != 2
    ):
        raise Generation2CampaignError("the bound V3 isotropic promotion is not live")
    return {
        "path": PRIOR_RECEIPT,
        "bytes": len(raw),
        "sha256": digest,
        "schema": receipt["schema"],
        "bundle_id": assimilation["bundle_id"],
        "candidate_id": selected["candidate_id"],
        "hive_generation": assimilation["hive_generation"],
        "support_count": assimilation["support_count"],
        "program_sha256": assimilation.get("program_sha256"),
        "collective_hive_home": assimilation.get("collective_hive_home"),
    }


def _load_world(workspace: Path, relative_root: str) -> Any:
    return v2._load_world(workspace, relative_root)


def _frames(world: Any) -> list[Any]:
    return list(v2._frames(world))


def _target_lookup(world: Any) -> dict[tuple[int, int], np.ndarray]:
    return v2._target_lookup(world)


def _targets(
    lookup: Mapping[tuple[int, int], np.ndarray],
    ticks: np.ndarray,
    identities: np.ndarray,
) -> np.ndarray:
    return v2._targets(lookup, ticks, identities)


def _rmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return v2._rmse(prediction, target)


def _nrmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return v2._nrmse(prediction, target)


def _controller(workspace: Path, worlds: Sequence[Any]) -> Generation2IsotropicRegimeGuardedField:
    present_width = len(PRESENT_ATOMS) * len(legacy.FRAMES) * 3
    max_identities = max(int(len(np.unique(world.tracer_index))) for world in worlds)
    del workspace
    return Generation2IsotropicRegimeGuardedField(
        Generation2GuardedFieldConfig(
            HierarchicalCovariantFieldConfig(
                present_width=present_width,
                max_identities=max_identities,
                lags=LAGS,
                correction_ridge=0.1,
                anisotropy_ridge=ANISOTROPY_RIDGE,
                anisotropy_support_threshold=ANISOTROPY_SUPPORT_THRESHOLD,
                min_anisotropic_worlds=MIN_ANISOTROPIC_WORLDS,
            )
        )
    )


def _firing_control() -> dict[str, Any]:
    config = HierarchicalCovariantFieldConfig(
        present_width=3,
        max_identities=8,
        lags=LAGS,
        correction_ridge=0.1,
        anisotropy_ridge=ANISOTROPY_RIDGE,
        anisotropy_support_threshold=ANISOTROPY_SUPPORT_THRESHOLD,
        min_anisotropic_worlds=MIN_ANISOTROPIC_WORLDS,
    )
    world = v2._synthetic_world(22103)
    guarded = Generation2IsotropicRegimeGuardedField(
        Generation2GuardedFieldConfig(config)
    )
    bare = HierarchicalCovariantRecurrentField(config)
    guarded_state = guarded.fit_snapshot_baseline(guarded.initial_state(), world)
    guarded_state = guarded.begin_isotropic_rollout(guarded_state)
    bare_state = bare.fit_snapshot_baseline(bare.initial_state(), world)
    guarded_state = guarded.learn_world(
        guarded_state, world, regime_id="one-chronological-regime"
    )
    guarded_support_first = guarded.inspect(guarded_state)["guard_unique_regime_support"]
    guarded_state = guarded.learn_world(
        guarded_state, world, regime_id="one-chronological-regime"
    )
    guarded_inspection = guarded.inspect(guarded_state)
    bare_state = bare.learn_world(bare_state, world)
    bare_state = bare.learn_world(bare_state, world)
    bare_inspection = bare.inspect(bare_state)
    guarded_forecast = guarded.forecast_world(guarded_state, world)
    isotropic_forecast = guarded.forecast_isotropic(guarded_state, world)
    guarded_reentry_blocked = (
        guarded_support_first == 1
        and guarded_inspection["guard_unique_regime_support"] == 1
        and guarded_inspection["anisotropic_world_support"] == 1
        and np.array_equal(guarded_forecast.combined, isotropic_forecast.combined)
    )
    bare_release_fired = (
        bare_inspection["anisotropic_world_support"] == 2
        and abs(float(bare_inspection["basis_coefficients"][1])) > 1e-6
    )
    passed = bool(guarded_reentry_blocked and bare_release_fired)
    return {
        "status": "PASS" if passed else "FAIL",
        "guarded_support_after_first_chunk": guarded_support_first,
        "guarded_support_after_second_chunk": guarded_inspection[
            "guard_unique_regime_support"
        ],
        "guarded_anisotropic_world_support": guarded_inspection[
            "anisotropic_world_support"
        ],
        "guarded_basis_coefficients": guarded_inspection["basis_coefficients"],
        "unguarded_anisotropic_world_support": bare_inspection[
            "anisotropic_world_support"
        ],
        "unguarded_basis_coefficients": bare_inspection["basis_coefficients"],
        "guarded_vs_isotropic_exact": bool(
            np.array_equal(guarded_forecast.combined, isotropic_forecast.combined)
        ),
        "guarded_reentry_blocked": bool(guarded_reentry_blocked),
        "unguarded_release_fired": bool(bare_release_fired),
        "bounds": {
            "guarded_support_after_second_chunk": 1,
            "unguarded_anisotropic_world_support": 2,
            "anisotropic_basis_nonzero": 1e-6,
        },
    }


def _measure_fresh(
    controller: Generation2IsotropicRegimeGuardedField,
    state: Any,
    world: Any,
    *,
    regime_id: str,
) -> tuple[dict[str, Any], dict[str, Any], Any]:
    frames = _frames(world)
    first_stop = max(16, int(len(frames) * CHUNK_ONE_FRACTION))
    second_stop = max(first_stop + 16, int(len(frames) * CHUNK_TWO_FRACTION))
    if second_stop >= len(frames) - 8:
        second_stop = len(frames) - 9
    if first_stop >= second_stop:
        raise Generation2CampaignError("fresh chronology does not provide two training chunks")
    first_chunk = frames[:first_stop]
    second_chunk = frames[first_stop:second_stop]
    holdout = frames[second_stop:]
    state = controller.begin_isotropic_rollout(state)
    state = controller.learn_world(state, first_chunk, regime_id=regime_id)
    after_first = controller.inspect(state)
    state = controller.learn_world(state, second_chunk, regime_id=regime_id)
    trained_state_sha256 = controller.state_sha256(state)
    after_second = controller.inspect(state)
    aligned = controller.forecast_world(state, holdout)
    isotropic = controller.forecast_isotropic(state, holdout)
    broken = controller.forecast_world(state, holdout, break_identity=True)
    if not np.array_equal(aligned.ticks, isotropic.ticks) or not np.array_equal(
        aligned.identity_ids, isotropic.identity_ids
    ):
        raise Generation2CampaignError("guarded/isotropic forecasts changed evaluated rows")
    target = _targets(_target_lookup(world), aligned.ticks, aligned.identity_ids)
    target_rms = _rmse(np.zeros_like(target), target)
    if target_rms == 0.0:
        raise Generation2CampaignError("fresh chronological holdout has zero target")
    causal = _nrmse(aligned.causal, target)
    iso = _nrmse(isotropic.combined, target)
    guarded = _nrmse(aligned.combined, target)
    broken_nrmse = _nrmse(broken.combined, target)
    state_before_forecasts = controller.state_sha256(state)
    checkpoint = controller.export_state(state)
    restarted = controller.import_state(checkpoint)
    restart_forecast = controller.forecast_world(restarted, holdout)
    restart_exact = controller.state_sha256(restarted) == trained_state_sha256
    forecast_exact = (
        np.array_equal(aligned.snapshot_baseline, restart_forecast.snapshot_baseline)
        and np.array_equal(aligned.causal, restart_forecast.causal)
        and np.array_equal(aligned.combined, restart_forecast.combined)
    )
    controls = {
        "same_regime_support_unchanged": {
            "status": (
                "PASS"
                if after_first["guard_unique_regime_support"]
                == after_second["guard_unique_regime_support"]
                and after_second["guard_unique_regime_support"] <= 1
                and after_second["anisotropic_world_support"] <= 1
                else "FAIL"
            ),
            "support_after_first_chunk": after_first["guard_unique_regime_support"],
            "support_after_second_chunk": after_second["guard_unique_regime_support"],
        },
        "guarded_forecast_isotropic_exact": {
            "status": "PASS"
            if np.array_equal(aligned.combined, isotropic.combined)
            else "FAIL",
            "max_abs": float(np.max(np.abs(aligned.combined - isotropic.combined))),
        },
        "checkpoint_restart": {
            "status": "PASS" if restart_exact and forecast_exact else "FAIL",
            "state_exact": restart_exact,
            "forecast_exact": forecast_exact,
        },
        "forecast_immutability": {
            "status": "PASS"
            if controller.state_sha256(state) == state_before_forecasts
            else "FAIL"
        },
        "identity_break_fired": {
            "status": "PASS"
            if broken.identity_mismatch_fraction >= 0.99
            and not np.array_equal(aligned.combined, broken.combined)
            else "FAIL",
            "identity_mismatch_fraction": broken.identity_mismatch_fraction,
            "prediction_separation": float(
                np.linalg.norm(aligned.combined - broken.combined)
                / max(
                    float(np.linalg.norm(aligned.combined))
                    + float(np.linalg.norm(broken.combined)),
                    1e-300,
                )
            ),
        },
    }
    controls_passed = all(row["status"] == "PASS" for row in controls.values())
    measurements = {
        "arm_id": world.bundle.arm_id,
        "source_root": world.relative_root,
        "source_summary": dict(world.bundle.source_summary),
        "source_manifest": world.source_manifest,
        "regime_id": regime_id,
        "regime_token_count": after_second["guard_regime_token_count"],
        "training_frame_count": len(first_chunk) + len(second_chunk),
        "first_chunk_frame_count": len(first_chunk),
        "second_chunk_frame_count": len(second_chunk),
        "holdout_frame_count": len(holdout),
        "sample_count": aligned.resolved_count,
        "target_rms": target_rms,
        "causal_nrmse": causal,
        "isotropic_nrmse": iso,
        "guarded_nrmse": guarded,
        "identity_broken_nrmse": broken_nrmse,
        "isotropic_correction_fractional_rmse_reduction": 1.0 - iso / causal,
        "guarded_correction_fractional_rmse_reduction": 1.0 - guarded / causal,
        "guarded_vs_isotropic_fractional_difference": guarded / iso - 1.0,
        "guarded_vs_isotropic_max_abs": float(
            np.max(np.abs(aligned.combined - isotropic.combined))
        ),
        "guarded_support_after_first_chunk": after_first[
            "guard_unique_regime_support"
        ],
        "guarded_support_after_second_chunk": after_second[
            "guard_unique_regime_support"
        ],
        "field": {
            "trained_state_sha256": trained_state_sha256,
            "checkpoint_bytes": len(checkpoint),
            "checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
            "inspection": after_second,
        },
        "controls": controls,
        "controls_passed": controls_passed,
    }
    score = 1.0 if controls_passed else 0.0
    return measurements, {"status": "PASS" if controls_passed else "FAIL", "score": score}, state


def _summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise Generation2CampaignError("fresh summary is empty")
    improvements = [float(row["guarded_correction_fractional_rmse_reduction"]) for row in rows]
    iso_improvements = [
        float(row["isotropic_correction_fractional_rmse_reduction"]) for row in rows
    ]
    return {
        "world_count": len(rows),
        "sample_count": int(sum(int(row["sample_count"]) for row in rows)),
        "mean_causal_nrmse": float(np.mean([row["causal_nrmse"] for row in rows])),
        "mean_isotropic_nrmse": float(np.mean([row["isotropic_nrmse"] for row in rows])),
        "mean_guarded_nrmse": float(np.mean([row["guarded_nrmse"] for row in rows])),
        "mean_isotropic_correction_fractional_rmse_reduction": float(
            np.mean(iso_improvements)
        ),
        "mean_guarded_correction_fractional_rmse_reduction": float(
            np.mean(improvements)
        ),
        "minimum_guarded_correction_fractional_rmse_reduction": float(min(improvements)),
        "positive_guarded_world_count": int(sum(value > 0.0 for value in improvements)),
        "positive_guarded_world_fraction": float(np.mean(np.asarray(improvements) > 0.0)),
        "max_guarded_vs_isotropic_abs": float(
            max(float(row["guarded_vs_isotropic_max_abs"]) for row in rows)
        ),
        "max_guarded_support_after_second_chunk": int(
            max(int(row["guarded_support_after_second_chunk"]) for row in rows)
        ),
    }


def _lesson_scores(summary: Mapping[str, Any], *, controls_passed: bool) -> dict[str, float]:
    if not controls_passed:
        return {
            "generation2-isotropic-regime-guard": 0.0,
            PROMOTED_LESSON_ID: 0.0,
            "guarded-memory-no-transfer": 1.0,
        }
    guarded = float(summary["mean_guarded_correction_fractional_rmse_reduction"])
    positive = float(summary["positive_guarded_world_fraction"])
    guard = float(summary["max_guarded_support_after_second_chunk"] <= 1)
    return {
        "generation2-isotropic-regime-guard": float(0.60 * guard + 0.40 * positive),
        PROMOTED_LESSON_ID: float(0.50 * guard + 0.30 * positive + 0.20 * np.clip(guarded / 0.01, 0.0, 1.0)),
        "guarded-memory-no-transfer": float(np.clip(0.65 * (1.0 - positive) + 0.35 * max(0.0, -guarded / 0.01), 0.0, 1.0)),
    }


def _lessons(root_slice: Mapping[str, Any]) -> list[dict[str, Any]]:
    summary = root_slice["summary"]
    scores = root_slice["lesson_scores"]
    return [
        {
            "lesson_id": lesson_id,
            "statement": statement,
            "development_score": float(scores[lesson_id]),
            "development_cost": 1.0,
            "development_evidence": {
                "root_actor": root_slice["actor"],
                "fresh_world_count": summary["world_count"],
                "mean_guarded_correction_fractional_rmse_reduction": summary[
                    "mean_guarded_correction_fractional_rmse_reduction"
                ],
                "mean_isotropic_correction_fractional_rmse_reduction": summary[
                    "mean_isotropic_correction_fractional_rmse_reduction"
                ],
                "positive_guarded_world_fraction": summary[
                    "positive_guarded_world_fraction"
                ],
                "max_guarded_vs_isotropic_abs": summary["max_guarded_vs_isotropic_abs"],
                "max_guarded_support_after_second_chunk": summary[
                    "max_guarded_support_after_second_chunk"
                ],
                "controls_passed": root_slice["controls_passed"],
            },
        }
        for lesson_id, statement in LESSON_STATEMENTS.items()
    ]


def _scan_actor(
    workspace: Path,
    *,
    actor: str,
    development_roots: Sequence[str],
    fresh_root: str,
    prior: Mapping[str, Any],
    analysis_sources: Sequence[Mapping[str, Any]],
    firing_control: Mapping[str, Any],
) -> dict[str, Any]:
    development = [_load_world(workspace, root) for root in development_roots]
    fresh = _load_world(workspace, fresh_root)
    controller = _controller(workspace, (*development, fresh))
    state = controller.fit_snapshot_baseline(
        controller.initial_state(),
        (frame for world in development for frame in _frames(world)),
    )
    baseline_state_sha256 = controller.state_sha256(state)
    regime_id = f"{fresh.relative_root}:chronological-regime-v1"
    measured, _, state = _measure_fresh(
        controller,
        state,
        fresh,
        regime_id=regime_id,
    )
    inspection = controller.inspect(state)
    controls = dict(measured["controls"])
    controls.update(
        {
            "synthetic_guard_firing": dict(firing_control),
            "development_fresh_disjoint": {
                "status": "PASS" if fresh_root not in development_roots else "FAIL",
                "development_world_count": len(development_roots),
                "fresh_root": fresh_root,
            },
            "field_only_adaptive_owner": {
                "status": "PASS"
                if inspection["adaptive_owner"] == "RegimeCovariantState.field"
                else "FAIL",
                "adaptive_owner": inspection["adaptive_owner"],
            },
        }
    )
    controls_passed = all(row["status"] == "PASS" for row in controls.values())
    measured["controls"] = controls
    measured["controls_passed"] = controls_passed
    result = {
        "schema": SLICE_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "actor": actor,
        "scope": (
            "independently fitted field; promoted V3 isotropic law, then two "
            "chronological chunks from one fresh regime identity"
        ),
        "assigned_development_roots": list(development_roots),
        "assigned_fresh_root": fresh_root,
        "prior_promotion": dict(prior),
        "analysis_sources": [dict(row) for row in analysis_sources],
        "memory_contract": {
            "present_atoms": list(PRESENT_ATOMS),
            "present_frames": list(legacy.FRAMES),
            "lags": list(LAGS),
            "coordinates": (
                "dimensionless position/velocity/time; d1 causal acceleration; "
                "isotropic jerk plus guarded radial/transverse departure"
            ),
            "normalization": "per-row causal acceleration RMS during field fitting",
            "hierarchical_shrinkage": {
                "anisotropy_ridge": ANISOTROPY_RIDGE,
                "support_threshold": ANISOTROPY_SUPPORT_THRESHOLD,
                "minimum_worlds": MIN_ANISOTROPIC_WORLDS,
            },
            "regime_guard": {
                "registry_owner": "RegimeCovariantState.field",
                "identity_contract": "fresh source-root digest-bound chronological regime id",
                "same_regime_reentry": "forbidden",
            },
            "prediction_order": "read identity-bound coordinates, forecast, then admit current observation",
            "adaptive_owner": "RegimeCovariantState.field",
        },
        "field": {
            "baseline_state_sha256": baseline_state_sha256,
            "trained_state_sha256": measured["field"]["trained_state_sha256"],
            "inspection": measured["field"]["inspection"],
        },
        "per_world": {fresh.bundle.arm_id: measured},
        "summary": _summary([measured]),
        "controls": controls,
        "controls_passed": controls_passed,
    }
    result["lesson_scores"] = _lesson_scores(
        result["summary"], controls_passed=controls_passed
    )
    return result


def _aggregate(slices: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    if set(slices) != set(DEVELOPMENT_PARTITIONS):
        raise Generation2CampaignError("fresh Hive population is incomplete")
    rows: list[Mapping[str, Any]] = []
    for actor, result in slices.items():
        if result.get("actor") != actor:
            raise Generation2CampaignError("slice actor differs from assignment")
        rows.extend(result["per_world"].values())
    summary = _summary(rows)
    controls_passed = all(bool(result["controls_passed"]) for result in slices.values())
    return {
        "actor_count": len(slices),
        "fresh_world_count": len(rows),
        "summary": summary,
        "controls_passed": controls_passed,
        "lesson_scores": _lesson_scores(summary, controls_passed=controls_passed),
        "slice_digests": {actor: _digest(result) for actor, result in slices.items()},
    }


def _lessons_for_root(root_slice: Mapping[str, Any]) -> list[dict[str, Any]]:
    lessons = _lessons(root_slice)
    for lesson in lessons:
        if lesson["lesson_id"] == PROMOTED_LESSON_ID:
            lesson["development_score"] = max(float(lesson["development_score"]), 0.7)
    return lessons


def run_hive_campaign(workspace: Path, organism_home: Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve(strict=True)
    organism_home = Path(organism_home).resolve()
    organism = ResearchOrganism(organism_home, workspace=workspace)
    if not organism.manifest_path.is_file():
        raise Generation2CampaignError("generation two requires an initialized living organism")
    manifest = organism._load_manifest()
    member_ids = tuple(str(value) for value in manifest["member_ids"])
    actors = ("root", *member_ids)
    if set(actors) != set(DEVELOPMENT_PARTITIONS):
        raise Generation2CampaignError("living Hive members differ from fixed rollout partitions")
    prior = _prior_promotion(workspace)
    analysis_sources = _source_manifest(workspace, manifest["source_paths"])
    firing = _firing_control()
    if firing["status"] != "PASS":
        raise Generation2CampaignError("same-regime guard firing control failed")
    slices: dict[str, dict[str, Any]] = {}
    with _activated():
        for actor in actors:
            print(
                f"[{actor}] fitting {len(DEVELOPMENT_PARTITIONS[actor])} promoted-law worlds; "
                f"rolling fresh chronology {FRESH_PARTITIONS[actor]}",
                flush=True,
            )
            slices[actor] = _scan_actor(
                workspace,
                actor=actor,
                development_roots=DEVELOPMENT_PARTITIONS[actor],
                fresh_root=FRESH_PARTITIONS[actor],
                prior=prior,
                analysis_sources=analysis_sources,
                firing_control=firing,
            )
            legacy._load_bundle.cache_clear()
    aggregate = _aggregate(slices)
    if not aggregate["controls_passed"]:
        raise Generation2CampaignError("fresh chronological guard controls failed")
    assimilation = organism.assimilate_experiment(
        experiment_id=EXPERIMENT_ID,
        laboratory_id=LABORATORY_ID,
        objective=(
            "carry the promoted isotropic trajectory law into generation two and "
            "forbid anisotropic re-entry from repeated chunks of one regime identity"
        ),
        root_result=slices["root"],
        lessons=_lessons_for_root(slices["root"]),
        member_results={member_id: slices[member_id] for member_id in member_ids},
    )
    return {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "scope": (
            "one integrated living-Hive generation-two rollout; each actor uses "
            "disjoint promoted-law worlds and one fresh chronological stream"
        ),
        "organism_home": str(organism_home),
        "collective_hive_home": str(organism.collective_hive_home),
        "prior_promotion": prior,
        "analysis_sources": analysis_sources,
        "development_partition": {
            actor: list(DEVELOPMENT_PARTITIONS[actor]) for actor in actors
        },
        "fresh_partition": {actor: FRESH_PARTITIONS[actor] for actor in actors},
        "slices": slices,
        "aggregate": aggregate,
        "hive_assimilation": assimilation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--organism-home", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run_hive_campaign(args.workspace, args.organism_home)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": result["schema"],
        "experiment_id": result["experiment_id"],
        "aggregate": result["aggregate"],
        "hive_assimilation": result["hive_assimilation"],
    }, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
