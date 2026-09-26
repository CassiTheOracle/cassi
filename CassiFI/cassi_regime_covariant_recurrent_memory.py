"""Living-Hive challenge for regime-covariant recurrent trajectory memory.

Each actor fits one field on disjoint development worlds.  The field converts
same-identity position, velocity, acceleration, and elapsed time into local
radial/transverse coordinates, then learns a dimensionless correction beyond a
causal finite-difference forecast.  Disjoint unseen worlds are measured before
one quorum-reviewed lesson can enter the existing research organism.  There is
no isolated experiment entry point.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import numpy as np

import cassi_full_observable_invention as legacy
import cassi_lagrangian_recurrent_memory as v1
from cassi_morphology_operator_invention import CAMPAIGN, SEED_ATOMS, _activated
from cassi_regime_covariant_recurrent_field import (
    CovariantFieldConfig,
    CovariantFrame,
    RegimeCovariantRecurrentField,
    RegimeCovariantState,
)
from cassi_research_organism import ResearchOrganism


SCHEMA = "cassifi.hive-regime-covariant-recurrent-memory.v2"
SLICE_SCHEMA = "cassifi.hive-regime-covariant-recurrent-memory-slice.v2"
EXPERIMENT_ID = "regime-covariant-recurrent-memory-v2"
LABORATORY_ID = "regime-covariant-trajectory-memory"
PRIOR_RECEIPT = "CassiFI/_diag/lagrangian-recurrent-memory-v1.json"
PRIOR_RECEIPT_SHA256 = "75769b203e539b58b8c04aceef7a3137929bc425b7a040eb4711fba77e503528"
LAGS = (1, 2, 4, 8)
PRESENT_ATOMS = tuple(SEED_ATOMS)
ANALYSIS_SOURCES = (
    "CassiFI/cassi_regime_covariant_recurrent_field.py",
    "CassiFI/cassi_regime_covariant_recurrent_memory.py",
    "CassiFI/cassi_lagrangian_recurrent_field.py",
    "CassiFI/cassi_lagrangian_recurrent_memory.py",
    "CassiFI/cassi_temporal_residual_authority.py",
    "CassiFI/cassi_morphology_residual_authority.py",
    "CassiFI/cassi_morphology_operator_invention.py",
    "CassiFI/cassi_morphology_operator_language.py",
    "CassiFI/cassi_morphology_observables.py",
    "CassiFI/cassi_full_observable_invention.py",
    "CassiFI/cassi_research_organism.py",
)

LESSON_STATEMENTS = {
    "regime-covariant-trajectory-transfer": (
        "A position-resolved, time-normalized, identity-bound recurrent field "
        "transfers a learned trajectory correction beyond causal finite differences "
        "in worlds excluded from its fit."
    ),
    "causal-kinematics-only": (
        "Identity-bound causal kinematics transfer across worlds, but the field-learned "
        "radial/transverse correction adds no stable improvement."
    ),
    "covariant-memory-no-transfer": (
        "Regime-covariant recurrent construction does not improve acceleration "
        "forecasts in worlds excluded from its fit."
    ),
}


class CovariantCampaignError(RuntimeError):
    """Raised when the V2 population challenge is not admissible."""


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


def _source_manifest(
    workspace: Path, organism_sources: Sequence[str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative in sorted(set(ANALYSIS_SOURCES) | set(organism_sources)):
        path = workspace / relative
        if not path.is_file():
            raise CovariantCampaignError(f"analysis source is absent: {relative}")
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    return rows


def _prior_finding(workspace: Path) -> dict[str, Any]:
    path = workspace / PRIOR_RECEIPT
    try:
        raw = path.read_bytes()
        receipt = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CovariantCampaignError("V1 recurrent finding is unavailable") from exc
    digest = hashlib.sha256(raw).hexdigest()
    assimilation = receipt.get("hive_assimilation", {})
    summary = receipt.get("aggregate", {}).get("summary", {})
    if (
        digest != PRIOR_RECEIPT_SHA256
        or receipt.get("schema") != "cassifi.hive-lagrangian-recurrent-memory.v1"
        or receipt.get("aggregate", {}).get("unseen_world_count") != 4
        or summary.get("scored_world_count") != 3
        or assimilation.get("status") != "contested"
        or assimilation.get("support_count") != 1
        or assimilation.get("bundle_id") is not None
    ):
        raise CovariantCampaignError("V1 recurrent finding is not the bound failed transfer")
    return {
        "path": PRIOR_RECEIPT,
        "bytes": len(raw),
        "sha256": digest,
        "experiment_id": receipt["experiment_id"],
        "status": assimilation["status"],
        "support_count": assimilation["support_count"],
        "quorum": assimilation["quorum"],
        "hive_generation": assimilation["hive_generation"],
        "mean_fractional_rmse_reduction": summary[
            "mean_aligned_fractional_rmse_reduction"
        ],
        "positive_world_fraction": summary["positive_world_fraction"],
        "conclusion": (
            "absolute-coordinate recurrent coefficients were identity-sensitive but "
            "did not transfer consistently across force regimes"
        ),
    }


def _load_world(workspace: Path, relative_root: str) -> v1._World:
    return v1._load_world(workspace, relative_root)


def _dimensionless_delta(world: v1._World, slot: int) -> float:
    if slot <= 0 or slot >= len(world.steps):
        raise CovariantCampaignError("trajectory slot has no causal predecessor")
    delta = (
        (world.steps[slot] - world.steps[slot - 1])
        * world.dt
        * float(world.bundle.scales["velocity"])
        / float(world.bundle.scales["radius"])
    )
    if not math.isfinite(delta) or delta <= 0.0:
        raise CovariantCampaignError("trajectory has an invalid dimensionless interval")
    return float(delta)


def _frames(
    world: v1._World, *, reverse_rows: bool = False
) -> Iterator[CovariantFrame]:
    middle = np.asarray(world.bundle.middle_index, dtype=np.int64)
    if len(middle) == 0 or np.any(np.diff(middle) < 0):
        raise CovariantCampaignError(
            f"trajectory rows are not chronologically grouped: {world.relative_root}"
        )
    starts = np.r_[0, np.flatnonzero(np.diff(middle)) + 1]
    stops = np.r_[starts[1:], len(middle)]
    target = np.asarray(world.bundle.target, dtype=np.float64)
    radial = np.asarray(world.bundle.frames["radial"], dtype=np.float64)
    flow = np.asarray(world.bundle.frames["flow"], dtype=np.float64)
    q = np.asarray(world.bundle.atoms["q"], dtype=np.float64)
    speed = np.asarray(world.bundle.atoms["speed"], dtype=np.float64)
    for start, stop in zip(starts.tolist(), stops.tolist(), strict=True):
        rows = slice(start, stop)
        slot = int(middle[start]) + 1
        identities = np.asarray(world.tracer_index[rows], dtype=np.int64)
        present = v1._present_rows(world.bundle, rows)
        position = radial[rows] * q[rows, None]
        velocity = flow[rows] * speed[rows, None]
        frame_target = target[rows]
        if reverse_rows:
            identities = identities[::-1]
            present = present[::-1]
            position = position[::-1]
            velocity = velocity[::-1]
            frame_target = frame_target[::-1]
        yield CovariantFrame(
            tick=slot,
            identity_ids=identities,
            present=present,
            position=position,
            velocity=velocity,
            delta_time=_dimensionless_delta(world, slot),
            target=frame_target,
        )


def _target_lookup(world: v1._World) -> dict[tuple[int, int], np.ndarray]:
    return v1._target_lookup(world)


def _targets(
    lookup: Mapping[tuple[int, int], np.ndarray],
    ticks: np.ndarray,
    identities: np.ndarray,
) -> np.ndarray:
    return v1._targets(lookup, ticks, identities)


def _rmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((prediction - target) ** 2)))


def _nrmse(prediction: np.ndarray, target: np.ndarray) -> float:
    target_rms = _rmse(np.zeros_like(target), target)
    if target_rms == 0.0:
        raise CovariantCampaignError("holdout acceleration target is exactly zero")
    return float(_rmse(prediction, target) / target_rms)


def _synthetic_world(seed: int) -> list[CovariantFrame]:
    rng = np.random.default_rng(seed)
    identities = np.arange(8, dtype=np.int64)
    phase = rng.uniform(-np.pi, np.pi, size=(8, 3))
    direction = rng.normal(size=(8, 3))
    direction /= np.linalg.norm(direction, axis=1, keepdims=True)
    delta_time = 0.4
    positions: list[np.ndarray] = []
    velocities: list[np.ndarray] = []
    for tick in range(1, 73):
        time = tick * delta_time
        velocities.append(
            0.7 * np.sin(0.31 * time + phase)
            + 0.25 * np.cos(0.11 * time - 0.5 * phase)
            + 0.002 * tick * direction
        )
        positions.append(
            2.0 * direction
            + 0.18 * time * direction
            + 0.12 * np.sin(0.17 * time + phase)
        )
    result: list[CovariantFrame] = []
    for index, (position, velocity) in enumerate(
        zip(positions, velocities, strict=True)
    ):
        target = np.zeros((8, 3), dtype=np.float64)
        if index >= 2:
            d1 = (velocity - velocities[index - 1]) / delta_time
            d2 = (velocity - velocities[index - 2]) / (2.0 * delta_time)
            jerk = d1 - d2
            midpoint = position + positions[index - 1]
            local_radial = midpoint / np.linalg.norm(
                midpoint, axis=1, keepdims=True
            )
            radial_jerk = local_radial * np.einsum(
                "ni,ni->n", jerk, local_radial
            )[:, None]
            target = d1 + 0.45 * radial_jerk - 0.30 * (jerk - radial_jerk)
        present = np.column_stack(
            (
                np.linalg.norm(position, axis=1),
                np.linalg.norm(velocity, axis=1),
                np.einsum("ni,ni->n", position, velocity),
            )
        )
        result.append(
            CovariantFrame(
                tick=index + 1,
                identity_ids=identities.copy(),
                present=present,
                position=position,
                velocity=velocity,
                delta_time=delta_time,
                target=target,
            )
        )
    return result


def _firing_control() -> dict[str, Any]:
    controller = RegimeCovariantRecurrentField(
        CovariantFieldConfig(
            present_width=3,
            max_identities=8,
            lags=LAGS,
            correction_ridge=0.1,
        )
    )
    training = _synthetic_world(22103)
    holdout = _synthetic_world(22109)
    state = controller.fit_snapshot_baseline(controller.initial_state(), training)
    state = controller.learn_world(state, training)
    aligned = controller.forecast_world(state, holdout)
    broken = controller.forecast_world(state, holdout, break_identity=True)
    target = _targets(
        {
            (frame.tick, int(identity)): frame.target[index]
            for frame in holdout
            for index, identity in enumerate(frame.identity_ids)
        },
        aligned.ticks,
        aligned.identity_ids,
    )
    causal_error = _rmse(aligned.causal, target)
    enriched_error = _rmse(aligned.combined, target)
    broken_error = _rmse(broken.combined, target)
    length_scale = 5.5
    velocity_scale = 2.25
    acceleration_scale = velocity_scale**2 / length_scale
    angle = 0.61
    rotation = np.array(
        (
            (math.cos(angle), -math.sin(angle), 0.0),
            (math.sin(angle), math.cos(angle), 0.0),
            (0.0, 0.0, 1.0),
        )
    )
    transformed = [
        CovariantFrame(
            tick=frame.tick,
            identity_ids=frame.identity_ids.copy(),
            present=frame.present.copy(),
            position=length_scale * (frame.position @ rotation.T),
            velocity=velocity_scale * (frame.velocity @ rotation.T),
            delta_time=frame.delta_time * length_scale / velocity_scale,
            target=None,
        )
        for frame in holdout
    ]
    transformed_forecast = controller.forecast_world(state, transformed)
    expected = acceleration_scale * (aligned.combined @ rotation.T)
    covariance_error = float(np.max(np.abs(transformed_forecast.combined - expected)))
    reduction = 1.0 - enriched_error / causal_error
    passed = (
        reduction > 0.5
        and broken_error > 5.0 * enriched_error
        and broken.identity_mismatch_fraction == 1.0
        and covariance_error <= 2e-12
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "causal_rmse": causal_error,
        "enriched_rmse": enriched_error,
        "fractional_rmse_reduction": reduction,
        "identity_broken_rmse": broken_error,
        "identity_mismatch_fraction": broken.identity_mismatch_fraction,
        "scale_rotation_covariance_max_abs": covariance_error,
        "bounds": {
            "fractional_rmse_reduction": 0.5,
            "identity_error_ratio": 5.0,
            "scale_rotation_covariance_max_abs": 2e-12,
        },
    }


def _measure_world(
    controller: RegimeCovariantRecurrentField,
    trained: RegimeCovariantState,
    world: v1._World,
) -> tuple[dict[str, Any], dict[str, bool]]:
    state_before = controller.state_sha256(trained)
    aligned = controller.forecast_world(trained, _frames(world))
    broken = controller.forecast_world(
        trained, _frames(world), break_identity=True
    )
    if not np.array_equal(aligned.ticks, broken.ticks) or not np.array_equal(
        aligned.identity_ids, broken.identity_ids
    ):
        raise CovariantCampaignError("identity control changed evaluated population")
    target = _targets(_target_lookup(world), aligned.ticks, aligned.identity_ids)
    target_rms = _rmse(np.zeros_like(target), target)
    separation = float(
        np.linalg.norm(aligned.combined - broken.combined)
        / max(
            float(np.linalg.norm(aligned.combined))
            + float(np.linalg.norm(broken.combined)),
            1e-300,
        )
    )
    dimensionless_step = float(
        np.median(
            np.diff(world.steps)
            * world.dt
            * float(world.bundle.scales["velocity"])
            / float(world.bundle.scales["radius"])
        )
    )
    result: dict[str, Any] = {
        "arm_id": world.bundle.arm_id,
        "source_root": world.relative_root,
        "source_summary": dict(world.bundle.source_summary),
        "source_manifest": world.source_manifest,
        "sample_count": aligned.resolved_count,
        "target_rms": target_rms,
        "dimensionless_step": dimensionless_step,
        "physical_lags": {
            str(lag): float(
                np.median(
                    (world.steps[1 + lag :] - world.steps[1 : -lag]) * world.dt
                )
            )
            for lag in LAGS
        },
        "dimensionless_lags": {
            str(lag): dimensionless_step * lag for lag in LAGS
        },
        "identity_mismatch_fraction": broken.identity_mismatch_fraction,
        "identity_prediction_separation": separation,
    }
    if target_rms == 0.0:
        result.update(
            {
                "status": "NULL_ZERO_TARGET",
                "snapshot_rmse": _rmse(aligned.snapshot_baseline, target),
                "causal_rmse": _rmse(aligned.causal, target),
                "covariant_rmse": _rmse(aligned.combined, target),
                "identity_broken_rmse": _rmse(broken.combined, target),
            }
        )
    else:
        snapshot = _nrmse(aligned.snapshot_baseline, target)
        causal = _nrmse(aligned.causal, target)
        covariant = _nrmse(aligned.combined, target)
        identity_broken = _nrmse(broken.combined, target)
        result.update(
            {
                "status": "SCORED",
                "snapshot_nrmse": snapshot,
                "causal_nrmse": causal,
                "covariant_nrmse": covariant,
                "identity_broken_nrmse": identity_broken,
                "causal_vs_snapshot_fractional_rmse_reduction": 1.0
                - causal / snapshot,
                "learned_correction_fractional_rmse_reduction": 1.0
                - covariant / causal,
                "total_memory_fractional_rmse_reduction": 1.0
                - covariant / snapshot,
                "identity_advantage": (identity_broken - covariant) / causal,
            }
        )
    controls = {
        "forecast_preserved_training_state": controller.state_sha256(trained)
        == state_before,
        "identity_break_fired": broken.identity_mismatch_fraction >= 0.99
        and separation > 1e-6,
    }
    return result, controls


def _mean(values: Iterable[float]) -> float:
    rows = [float(value) for value in values]
    if not rows:
        raise CovariantCampaignError("cannot summarize an empty scored population")
    return float(np.mean(rows))


def _summary(worlds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    scored = [row for row in worlds if row.get("status") == "SCORED"]
    null = [row for row in worlds if row.get("status") == "NULL_ZERO_TARGET"]
    if len(scored) + len(null) != len(worlds):
        raise CovariantCampaignError("unseen world has unsupported scoring status")
    learned = [
        float(row["learned_correction_fractional_rmse_reduction"])
        for row in scored
    ]
    return {
        "world_count": len(worlds),
        "scored_world_count": len(scored),
        "null_zero_target_world_count": len(null),
        "sample_count": int(sum(int(row["sample_count"]) for row in worlds)),
        "mean_snapshot_nrmse": _mean(row["snapshot_nrmse"] for row in scored),
        "mean_causal_nrmse": _mean(row["causal_nrmse"] for row in scored),
        "mean_covariant_nrmse": _mean(row["covariant_nrmse"] for row in scored),
        "mean_causal_vs_snapshot_fractional_rmse_reduction": _mean(
            row["causal_vs_snapshot_fractional_rmse_reduction"] for row in scored
        ),
        "mean_learned_correction_fractional_rmse_reduction": _mean(learned),
        "minimum_learned_correction_fractional_rmse_reduction": min(learned),
        "positive_learned_world_count": int(sum(value > 0.0 for value in learned)),
        "positive_learned_world_fraction": float(
            np.mean(np.asarray(learned) > 0.0)
        ),
        "mean_total_memory_fractional_rmse_reduction": _mean(
            row["total_memory_fractional_rmse_reduction"] for row in scored
        ),
        "mean_identity_advantage": _mean(
            row["identity_advantage"] for row in scored
        ),
    }


def _lesson_scores(
    summary: Mapping[str, Any], *, controls_passed: bool
) -> dict[str, float]:
    if not controls_passed:
        return {
            "regime-covariant-trajectory-transfer": 0.0,
            "causal-kinematics-only": 0.0,
            "covariant-memory-no-transfer": 1.0,
        }
    effect = float(
        np.clip(
            max(
                float(summary["mean_learned_correction_fractional_rmse_reduction"]),
                0.0,
            )
            / 0.01,
            0.0,
            1.0,
        )
    )
    positive = float(
        np.clip(summary["positive_learned_world_fraction"], 0.0, 1.0)
    )
    identity = float(
        np.clip(max(float(summary["mean_identity_advantage"]), 0.0) / 0.25, 0.0, 1.0)
    )
    return {
        "regime-covariant-trajectory-transfer": float(
            np.clip(0.50 * effect + 0.25 * positive + 0.25 * identity, 0.0, 1.0)
        ),
        "causal-kinematics-only": float(
            np.clip(
                0.55 * (1.0 - effect) + 0.25 * positive + 0.20 * identity,
                0.0,
                1.0,
            )
        ),
        "covariant-memory-no-transfer": float(
            np.clip(
                0.65 * (1.0 - positive) + 0.35 * (1.0 - effect),
                0.0,
                1.0,
            )
        ),
    }


def _scan_actor(
    workspace: Path,
    *,
    actor: str,
    development_roots: Sequence[str],
    holdout_roots: Sequence[str],
    prior: Mapping[str, Any],
    analysis_sources: Sequence[Mapping[str, Any]],
    firing_control: Mapping[str, Any],
) -> dict[str, Any]:
    if not development_roots or not holdout_roots:
        raise CovariantCampaignError(f"actor lacks a complete assignment: {actor}")
    if set(development_roots).intersection(holdout_roots):
        raise CovariantCampaignError("development and unseen worlds overlap")
    development = [_load_world(workspace, root) for root in development_roots]
    holdout = [_load_world(workspace, root) for root in holdout_roots]
    present_width = len(PRESENT_ATOMS) * len(legacy.FRAMES) * 3
    max_identities = max(
        int(len(np.unique(world.tracer_index)))
        for world in (*development, *holdout)
    )
    controller = RegimeCovariantRecurrentField(
        CovariantFieldConfig(
            present_width=present_width,
            max_identities=max_identities,
            lags=LAGS,
            correction_ridge=0.1,
        )
    )
    state = controller.fit_snapshot_baseline(
        controller.initial_state(),
        (frame for world in development for frame in _frames(world)),
    )
    baseline_state_sha256 = controller.state_sha256(state)
    for world in development:
        state = controller.learn_world(state, _frames(world))
    trained_state_sha256 = controller.state_sha256(state)
    checkpoint = controller.export_state(state)
    restarted = controller.import_state(checkpoint)

    per_world: dict[str, dict[str, Any]] = {}
    control_rows: list[dict[str, bool]] = []
    for world in holdout:
        measured, measured_controls = _measure_world(controller, state, world)
        per_world[measured["arm_id"]] = measured
        control_rows.append(measured_controls)
    first = holdout[0]
    canonical = controller.forecast_world(state, _frames(first))
    restart_forecast = controller.forecast_world(restarted, _frames(first))
    reordered = controller.forecast_world(state, _frames(first, reverse_rows=True))
    restart_exact = controller.state_sha256(restarted) == trained_state_sha256
    restart_forecast_exact = (
        np.array_equal(canonical.snapshot_baseline, restart_forecast.snapshot_baseline)
        and np.array_equal(canonical.causal, restart_forecast.causal)
        and np.array_equal(canonical.combined, restart_forecast.combined)
    )
    row_order_exact = (
        np.array_equal(canonical.identity_ids, reordered.identity_ids)
        and np.array_equal(canonical.causal, reordered.causal)
        and np.array_equal(canonical.combined, reordered.combined)
    )
    summary = _summary(list(per_world.values()))
    inspection = controller.inspect(state)
    controls = {
        "development_holdout_disjoint": {
            "status": "PASS",
            "development_world_count": len(development_roots),
            "holdout_world_count": len(holdout_roots),
        },
        "synthetic_covariant_firing": dict(firing_control),
        "field_only_adaptive_owner": {
            "status": (
                "PASS"
                if inspection["adaptive_owner"] == "RegimeCovariantState.field"
                else "FAIL"
            ),
            "adaptive_owner": inspection["adaptive_owner"],
        },
        "checkpoint_restart": {
            "status": "PASS"
            if restart_exact and restart_forecast_exact
            else "FAIL",
            "state_exact": restart_exact,
            "forecast_exact": restart_forecast_exact,
        },
        "identity_row_order": {
            "status": "PASS" if row_order_exact else "FAIL",
            "forecast_exact": row_order_exact,
        },
        "forecast_immutability": {
            "status": (
                "PASS"
                if all(
                    row["forecast_preserved_training_state"] for row in control_rows
                )
                else "FAIL"
            )
        },
        "identity_break_fired": {
            "status": (
                "PASS"
                if all(row["identity_break_fired"] for row in control_rows)
                else "FAIL"
            ),
            "minimum_mismatch_fraction": min(
                row["identity_mismatch_fraction"] for row in per_world.values()
            ),
            "minimum_prediction_separation": min(
                row["identity_prediction_separation"] for row in per_world.values()
            ),
        },
    }
    controls_passed = all(row["status"] == "PASS" for row in controls.values())
    result = {
        "schema": SLICE_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "actor": actor,
        "scope": (
            "independently fitted covariant field; disjoint development worlds and "
            "disjoint unseen physical holdouts"
        ),
        "assigned_development_roots": list(development_roots),
        "assigned_holdout_roots": list(holdout_roots),
        "prior_finding": dict(prior),
        "analysis_sources": [dict(row) for row in analysis_sources],
        "memory_contract": {
            "present_atoms": list(PRESENT_ATOMS),
            "present_frames": list(legacy.FRAMES),
            "lags": list(LAGS),
            "coordinates": (
                "dimensionless position/velocity/time; d1 causal acceleration; "
                "radial/transverse decomposition of d1-d2"
            ),
            "normalization": "per-row causal acceleration RMS during field fitting",
            "prediction_order": (
                "read identity-bound coordinates, forecast, then admit current observation"
            ),
            "adaptive_owner": "RegimeCovariantState.field",
        },
        "field": {
            "baseline_state_sha256": baseline_state_sha256,
            "trained_state_sha256": trained_state_sha256,
            "checkpoint_bytes": len(checkpoint),
            "checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
            "inspection": inspection,
        },
        "per_world": per_world,
        "summary": summary,
        "controls": controls,
        "controls_passed": controls_passed,
    }
    result["lesson_scores"] = _lesson_scores(
        summary, controls_passed=controls_passed
    )
    return result


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
                "unseen_world_count": summary["world_count"],
                "mean_learned_correction_fractional_rmse_reduction": summary[
                    "mean_learned_correction_fractional_rmse_reduction"
                ],
                "positive_learned_world_fraction": summary[
                    "positive_learned_world_fraction"
                ],
                "mean_identity_advantage": summary["mean_identity_advantage"],
                "controls_passed": root_slice["controls_passed"],
            },
        }
        for lesson_id, statement in LESSON_STATEMENTS.items()
    ]


def _aggregate(
    slices: Mapping[str, Mapping[str, Any]],
    *,
    expected_development: Sequence[str],
    expected_holdout: Sequence[str],
) -> dict[str, Any]:
    development: list[str] = []
    holdout: list[str] = []
    worlds: list[Mapping[str, Any]] = []
    for actor, result in slices.items():
        if result.get("actor") != actor:
            raise CovariantCampaignError("slice actor differs from its assignment")
        development.extend(result["assigned_development_roots"])
        holdout.extend(result["assigned_holdout_roots"])
        worlds.extend(result["per_world"].values())
    if sorted(development) != sorted(expected_development) or len(development) != len(
        expected_development
    ):
        raise CovariantCampaignError(
            "development population is not disjoint and complete"
        )
    if sorted(holdout) != sorted(expected_holdout) or len(holdout) != len(
        expected_holdout
    ):
        raise CovariantCampaignError("unseen population is not disjoint and complete")
    summary = _summary(worlds)
    controls_passed = all(
        bool(result["controls_passed"]) for result in slices.values()
    )
    return {
        "actor_count": len(slices),
        "development_world_count": len(development),
        "unseen_world_count": len(holdout),
        "summary": summary,
        "controls_passed": controls_passed,
        "lesson_scores": _lesson_scores(
            summary, controls_passed=controls_passed
        ),
        "slice_digests": {
            actor: _digest(result) for actor, result in slices.items()
        },
    }


def run_hive_campaign(workspace: Path, organism_home: Path) -> dict[str, Any]:
    """Run the complete covariant population challenge and Hive assimilation."""

    workspace = Path(workspace).resolve(strict=True)
    organism_home = Path(organism_home).resolve()
    organism = ResearchOrganism(organism_home, workspace=workspace)
    if not organism.manifest_path.is_file():
        raise CovariantCampaignError(
            "covariant memory requires an initialized living research organism"
        )
    manifest = organism._load_manifest()
    member_ids = tuple(str(value) for value in manifest["member_ids"])
    if len(member_ids) < 2:
        raise CovariantCampaignError(
            "covariant memory requires at least two independent Hive reviewers"
        )
    actors = ("root", *member_ids)
    development = tuple(CAMPAIGN.development_roots)
    holdout = tuple(CAMPAIGN.hidden_holdout)
    development_partitions = {
        actor: tuple(development[index:: len(actors)])
        for index, actor in enumerate(actors)
    }
    holdout_partitions = {
        actor: tuple(holdout[index:: len(actors)])
        for index, actor in enumerate(actors)
    }
    if any(
        not rows
        for rows in (*development_partitions.values(), *holdout_partitions.values())
    ):
        raise CovariantCampaignError("population exceeds the available world count")

    prior = _prior_finding(workspace)
    analysis_sources = _source_manifest(workspace, manifest["source_paths"])
    firing = _firing_control()
    if firing["status"] != "PASS":
        raise CovariantCampaignError("synthetic covariant firing control failed")
    slices: dict[str, dict[str, Any]] = {}
    with _activated():
        for actor in actors:
            print(
                f"[{actor}] fitting {len(development_partitions[actor])} worlds; "
                f"forecasting {len(holdout_partitions[actor])} unseen worlds",
                flush=True,
            )
            slices[actor] = _scan_actor(
                workspace,
                actor=actor,
                development_roots=development_partitions[actor],
                holdout_roots=holdout_partitions[actor],
                prior=prior,
                analysis_sources=analysis_sources,
                firing_control=firing,
            )
            legacy._load_bundle.cache_clear()
    aggregate = _aggregate(
        slices,
        expected_development=development,
        expected_holdout=holdout,
    )
    assimilation = organism.assimilate_experiment(
        experiment_id=EXPERIMENT_ID,
        laboratory_id=LABORATORY_ID,
        objective=(
            "replace absolute trajectory calibration with position-resolved, "
            "time-normalized, identity-bound recurrent coordinates and test whether "
            "the learned correction transfers to unseen physical worlds"
        ),
        root_result=slices["root"],
        lessons=_lessons(slices["root"]),
        member_results={member_id: slices[member_id] for member_id in member_ids},
    )
    return {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "scope": (
            "one integrated disjoint-world Hive population campaign; no isolated "
            "experiment path"
        ),
        "organism_home": str(organism_home),
        "collective_hive_home": str(organism.collective_hive_home),
        "prior_finding": prior,
        "analysis_sources": analysis_sources,
        "development_partition": {
            actor: list(rows) for actor, rows in development_partitions.items()
        },
        "unseen_partition": {
            actor: list(rows) for actor, rows in holdout_partitions.items()
        },
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
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite integrated Hive receipt: {args.out}")
    result = run_hive_campaign(args.workspace, args.organism_home)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "schema": result["schema"],
                "experiment_id": result["experiment_id"],
                "aggregate": result["aggregate"],
                "hive_assimilation": result["hive_assimilation"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
