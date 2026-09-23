"""Independent reproduction verifier for hierarchical recurrent memory V3.

This module does not import the V3 campaign runner.  It rebuilds every actor's
field from raw disjoint worlds, recomputes the isotropic and hierarchical
readings, checks source and checkpoint bindings, and verifies the live Hive's
quorum disposition and exact adoption or non-adoption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import numpy as np

import cassi_full_observable_invention as legacy
import cassi_lagrangian_recurrent_memory as v1
from cassi_field_atlas import sha256_value
from cassi_hierarchical_covariant_recurrent_field import (
    HierarchicalCovariantFieldConfig,
    HierarchicalCovariantRecurrentField,
)
from cassi_morphology_operator_invention import CAMPAIGN, SEED_ATOMS, _activated
from cassi_research_organism import ResearchOrganism


SCHEMA = "cassifi.hive-hierarchical-regime-covariant-recurrent-memory.v3"
SLICE_SCHEMA = "cassifi.hive-hierarchical-regime-covariant-recurrent-memory-slice.v3"
LAGS = (1, 2, 4, 8)
PRESENT_ATOMS = tuple(SEED_ATOMS)
ANISOTROPY_RIDGE = 8.0
ANISOTROPY_SUPPORT_THRESHOLD = 0.2
MIN_ANISOTROPIC_WORLDS = 2
PRIOR_RECEIPT = "CassiFI/_diag/regime-covariant-recurrent-memory-v2.json"
PRIOR_RECEIPT_SHA256 = "d2934f88f9811ffe3dc3c051600242d744dd734e668a8cf97ec0fa3ccb41b813"


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


def _close(left: Any, right: Any, *, tolerance: float = 2e-12) -> bool:
    try:
        a, b = float(left), float(right)
    except (TypeError, ValueError):
        return False
    return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= tolerance * max(
        1.0, abs(a), abs(b)
    )


def _same_metrics(expected: Any, actual: Any, path: str = "") -> list[str]:
    errors: list[str] = []
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        if set(expected) != set(actual):
            errors.append(f"{path}: key sets differ")
            return errors
        for key in expected:
            errors.extend(_same_metrics(expected[key], actual[key], f"{path}.{key}"))
        return errors
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{path}: list lengths differ"]
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            errors.extend(_same_metrics(left, right, f"{path}[{index}]"))
        return errors
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not _close(expected, actual):
            errors.append(f"{path}: {expected!r} != {actual!r}")
        return errors
    if expected != actual:
        errors.append(f"{path}: {expected!r} != {actual!r}")
    return errors


def _load_world(workspace: Path, relative_root: str) -> v1._World:
    return v1._load_world(workspace, relative_root)


def _delta_time(world: v1._World, slot: int) -> float:
    return float(
        (world.steps[slot] - world.steps[slot - 1])
        * world.dt
        * float(world.bundle.scales["velocity"])
        / float(world.bundle.scales["radius"])
    )


def _frames(world: v1._World) -> Iterator[Any]:
    from cassi_regime_covariant_recurrent_field import CovariantFrame

    middle = np.asarray(world.bundle.middle_index, dtype=np.int64)
    starts = np.r_[0, np.flatnonzero(np.diff(middle)) + 1]
    stops = np.r_[starts[1:], len(middle)]
    radial = np.asarray(world.bundle.frames["radial"], dtype=np.float64)
    flow = np.asarray(world.bundle.frames["flow"], dtype=np.float64)
    q = np.asarray(world.bundle.atoms["q"], dtype=np.float64)
    speed = np.asarray(world.bundle.atoms["speed"], dtype=np.float64)
    target = np.asarray(world.bundle.target, dtype=np.float64)
    for start, stop in zip(starts.tolist(), stops.tolist(), strict=True):
        rows = slice(start, stop)
        slot = int(middle[start]) + 1
        yield CovariantFrame(
            tick=slot,
            identity_ids=np.asarray(world.tracer_index[rows], dtype=np.int64),
            present=np.concatenate(
                [
                    np.asarray(world.bundle.frames[frame], dtype=np.float64)[rows]
                    * np.asarray(world.bundle.atoms[atom], dtype=np.float64)[rows, None]
                    for atom in PRESENT_ATOMS
                    for frame in legacy.FRAMES
                ],
                axis=1,
            ),
            position=radial[rows] * q[rows, None],
            velocity=flow[rows] * speed[rows, None],
            delta_time=_delta_time(world, slot),
            target=target[rows],
        )


def _target_map(world: v1._World) -> dict[tuple[int, int], np.ndarray]:
    middle = np.asarray(world.bundle.middle_index, dtype=np.int64)
    target = np.asarray(world.bundle.target, dtype=np.float64)
    return {
        (int(slot) + 1, int(identity)): target[index].copy()
        for index, (slot, identity) in enumerate(
            zip(middle.tolist(), world.tracer_index.tolist(), strict=True)
        )
    }


def _targets(world: v1._World, ticks: np.ndarray, identities: np.ndarray) -> np.ndarray:
    lookup = _target_map(world)
    return np.stack(
        [
            lookup[(int(tick), int(identity))]
            for tick, identity in zip(ticks.tolist(), identities.tolist(), strict=True)
        ]
    )


def _rmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((prediction - target) ** 2)))


def _nrmse(prediction: np.ndarray, target: np.ndarray) -> float:
    target_rms = _rmse(np.zeros_like(target), target)
    if target_rms == 0.0:
        raise RuntimeError("zero target passed to NRMSE")
    return _rmse(prediction, target) / target_rms


def _measure(
    controller: HierarchicalCovariantRecurrentField,
    state: Any,
    world: v1._World,
) -> dict[str, Any]:
    aligned = controller.forecast_world(state, _frames(world))
    isotropic = controller.forecast_isotropic(state, _frames(world))
    broken = controller.forecast_world(state, _frames(world), break_identity=True)
    target = _targets(world, aligned.ticks, aligned.identity_ids)
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
        "dimensionless_lags": {str(lag): dimensionless_step * lag for lag in LAGS},
        "identity_mismatch_fraction": broken.identity_mismatch_fraction,
        "identity_prediction_separation": separation,
    }
    if target_rms == 0.0:
        result.update(
            {
                "status": "NULL_ZERO_TARGET",
                "snapshot_rmse": _rmse(aligned.snapshot_baseline, target),
                "causal_rmse": _rmse(aligned.causal, target),
                "isotropic_rmse": _rmse(isotropic.combined, target),
                "hierarchical_rmse": _rmse(aligned.combined, target),
                "identity_broken_rmse": _rmse(broken.combined, target),
            }
        )
    else:
        snapshot = _nrmse(aligned.snapshot_baseline, target)
        causal = _nrmse(aligned.causal, target)
        isotropic_nrmse = _nrmse(isotropic.combined, target)
        hierarchical = _nrmse(aligned.combined, target)
        identity_broken = _nrmse(broken.combined, target)
        result.update(
            {
                "status": "SCORED",
                "snapshot_nrmse": snapshot,
                "causal_nrmse": causal,
                "isotropic_nrmse": isotropic_nrmse,
                "hierarchical_nrmse": hierarchical,
                "identity_broken_nrmse": identity_broken,
                "causal_vs_snapshot_fractional_rmse_reduction": 1.0
                - causal / snapshot,
                "isotropic_correction_fractional_rmse_reduction": 1.0
                - isotropic_nrmse / causal,
                "hierarchical_correction_fractional_rmse_reduction": 1.0
                - hierarchical / causal,
                "hierarchical_vs_isotropic_fractional_rmse_reduction": 1.0
                - hierarchical / isotropic_nrmse,
                "total_memory_fractional_rmse_reduction": 1.0
                - hierarchical / snapshot,
                "identity_advantage": (identity_broken - hierarchical) / causal,
            }
        )
    return result


def _summary(worlds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    scored = [row for row in worlds if row.get("status") == "SCORED"]
    null = [row for row in worlds if row.get("status") == "NULL_ZERO_TARGET"]
    if len(scored) + len(null) != len(worlds) or not scored:
        raise RuntimeError("unsupported or empty world score set")

    def mean(key: str) -> float:
        return float(np.mean([float(row[key]) for row in scored]))

    isotropic = [
        float(row["isotropic_correction_fractional_rmse_reduction"])
        for row in scored
    ]
    hierarchical = [
        float(row["hierarchical_correction_fractional_rmse_reduction"])
        for row in scored
    ]
    return {
        "world_count": len(worlds),
        "scored_world_count": len(scored),
        "null_zero_target_world_count": len(null),
        "sample_count": sum(int(row["sample_count"]) for row in worlds),
        "mean_snapshot_nrmse": mean("snapshot_nrmse"),
        "mean_causal_nrmse": mean("causal_nrmse"),
        "mean_isotropic_nrmse": mean("isotropic_nrmse"),
        "mean_hierarchical_nrmse": mean("hierarchical_nrmse"),
        "mean_causal_vs_snapshot_fractional_rmse_reduction": mean(
            "causal_vs_snapshot_fractional_rmse_reduction"
        ),
        "mean_isotropic_correction_fractional_rmse_reduction": float(
            np.mean(isotropic)
        ),
        "mean_hierarchical_correction_fractional_rmse_reduction": float(
            np.mean(hierarchical)
        ),
        "mean_hierarchical_vs_isotropic_fractional_rmse_reduction": mean(
            "hierarchical_vs_isotropic_fractional_rmse_reduction"
        ),
        "minimum_isotropic_correction_fractional_rmse_reduction": min(isotropic),
        "minimum_hierarchical_correction_fractional_rmse_reduction": min(hierarchical),
        "positive_isotropic_world_count": sum(value > 0.0 for value in isotropic),
        "positive_hierarchical_world_count": sum(value > 0.0 for value in hierarchical),
        "positive_isotropic_world_fraction": float(
            np.mean(np.asarray(isotropic) > 0.0)
        ),
        "positive_hierarchical_world_fraction": float(
            np.mean(np.asarray(hierarchical) > 0.0)
        ),
        "mean_total_memory_fractional_rmse_reduction": mean(
            "total_memory_fractional_rmse_reduction"
        ),
        "mean_identity_advantage": mean("identity_advantage"),
    }


def _scores(summary: Mapping[str, Any], controls_passed: bool) -> dict[str, float]:
    if not controls_passed:
        return {
            "hierarchical-covariant-trajectory-transfer": 0.0,
            "isotropic-covariant-trajectory-transfer": 0.0,
            "covariant-memory-no-transfer": 1.0,
        }
    hierarchical_effect = float(
        np.clip(
            max(float(summary["mean_hierarchical_correction_fractional_rmse_reduction"]), 0.0)
            / 0.01,
            0.0,
            1.0,
        )
    )
    isotropic_effect = float(
        np.clip(
            max(float(summary["mean_isotropic_correction_fractional_rmse_reduction"]), 0.0)
            / 0.01,
            0.0,
            1.0,
        )
    )
    hierarchical_positive = float(summary["positive_hierarchical_world_fraction"])
    isotropic_positive = float(summary["positive_isotropic_world_fraction"])
    identity = float(
        np.clip(max(float(summary["mean_identity_advantage"]), 0.0) / 0.25, 0.0, 1.0)
    )
    departure = float(
        np.clip(
            max(float(summary["mean_hierarchical_vs_isotropic_fractional_rmse_reduction"]), 0.0)
            / 0.01,
            0.0,
            1.0,
        )
    )
    return {
        "hierarchical-covariant-trajectory-transfer": float(
            np.clip(
                0.50 * hierarchical_effect
                + 0.25 * hierarchical_positive
                + 0.15 * identity
                + 0.10 * departure,
                0.0,
                1.0,
            )
        ),
        "isotropic-covariant-trajectory-transfer": float(
            np.clip(
                0.50 * isotropic_effect + 0.25 * isotropic_positive + 0.25 * identity,
                0.0,
                1.0,
            )
        ),
        "covariant-memory-no-transfer": float(
            np.clip(
                0.65 * (1.0 - max(hierarchical_positive, isotropic_positive))
                + 0.35 * (1.0 - max(hierarchical_effect, isotropic_effect)),
                0.0,
                1.0,
            )
        ),
    }


def _synthetic_world(seed: int) -> list[Any]:
    from cassi_regime_covariant_recurrent_field import CovariantFrame

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
    for index, (position, velocity) in enumerate(zip(positions, velocities, strict=True)):
        target = np.zeros((8, 3), dtype=np.float64)
        if index >= 2:
            d1 = (velocity - velocities[index - 1]) / delta_time
            d2 = (velocity - velocities[index - 2]) / (2.0 * delta_time)
            jerk = d1 - d2
            midpoint = position + positions[index - 1]
            radial = midpoint / np.linalg.norm(midpoint, axis=1, keepdims=True)
            radial_jerk = radial * np.einsum("ni,ni->n", jerk, radial)[:, None]
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
    controller = HierarchicalCovariantRecurrentField(
        HierarchicalCovariantFieldConfig(
            present_width=3,
            max_identities=8,
            lags=LAGS,
            correction_ridge=0.1,
            anisotropy_ridge=ANISOTROPY_RIDGE,
            anisotropy_support_threshold=ANISOTROPY_SUPPORT_THRESHOLD,
            min_anisotropic_worlds=MIN_ANISOTROPIC_WORLDS,
        )
    )
    training = (_synthetic_world(22103), _synthetic_world(22111))
    holdout = _synthetic_world(22109)
    state = controller.fit_snapshot_baseline(
        controller.initial_state(),
        (frame for world in training for frame in world),
    )
    for world in training:
        state = controller.learn_world(state, world)
    aligned = controller.forecast_world(state, holdout)
    isotropic = controller.forecast_isotropic(state, holdout)
    broken = controller.forecast_world(state, holdout, break_identity=True)
    target_lookup = {
        (frame.tick, int(identity)): frame.target[index]
        for frame in holdout
        for index, identity in enumerate(frame.identity_ids)
    }
    target = np.stack(
        [
            target_lookup[(int(tick), int(identity))]
            for tick, identity in zip(
                aligned.ticks.tolist(), aligned.identity_ids.tolist(), strict=True
            )
        ]
    )
    causal_error = _rmse(aligned.causal, target)
    isotropic_error = _rmse(isotropic.combined, target)
    hierarchical_error = _rmse(aligned.combined, target)
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
        type(frame)(
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
    covariance_error = float(
        np.max(
            np.abs(
                transformed_forecast.combined
                - acceleration_scale * (aligned.combined @ rotation.T)
            )
        )
    )
    inspection = controller.inspect(state)
    hierarchical_reduction = 1.0 - hierarchical_error / causal_error
    isotropic_reduction = 1.0 - isotropic_error / causal_error
    return {
        "status": "PASS"
        if (
            hierarchical_reduction > 0.1
            and hierarchical_error < isotropic_error
            and isotropic_reduction > 0.0
            and inspection["anisotropic_world_support"] >= MIN_ANISOTROPIC_WORLDS
            and abs(float(inspection["basis_coefficients"][1])) > 1e-6
            and broken_error > 2.0 * hierarchical_error
            and broken.identity_mismatch_fraction == 1.0
            and covariance_error <= 2e-12
        )
        else "FAIL",
        "causal_rmse": causal_error,
        "isotropic_rmse": isotropic_error,
        "hierarchical_rmse": hierarchical_error,
        "isotropic_fractional_rmse_reduction": isotropic_reduction,
        "hierarchical_fractional_rmse_reduction": hierarchical_reduction,
        "identity_broken_rmse": broken_error,
        "identity_mismatch_fraction": broken.identity_mismatch_fraction,
        "anisotropic_world_support": inspection["anisotropic_world_support"],
        "basis_coefficients": inspection["basis_coefficients"],
        "scale_rotation_covariance_max_abs": covariance_error,
        "bounds": {
            "hierarchical_fractional_rmse_reduction": 0.1,
            "isotropic_fractional_rmse_reduction": 0.0,
            "identity_error_ratio": 2.0,
            "scale_rotation_covariance_max_abs": 2e-12,
            "minimum_anisotropic_world_support": MIN_ANISOTROPIC_WORLDS,
        },
    }

def _verify_sources(receipt: Mapping[str, Any], workspace: Path) -> list[str]:
    errors: list[str] = []
    for row in receipt.get("analysis_sources", []):
        path = workspace / str(row.get("path"))
        if not path.is_file():
            errors.append(f"missing analysis source: {row.get('path')}")
        elif path.stat().st_size != row.get("bytes") or _file_sha256(path) != row.get(
            "sha256"
        ):
            errors.append(f"analysis source drift: {row.get('path')}")
    for slice_value in receipt.get("slices", {}).values():
        for world in slice_value.get("per_world", {}).values():
            root = workspace / str(world.get("source_root"))
            for row in world.get("source_manifest", []):
                path = root / str(row.get("name"))
                if not path.is_file():
                    errors.append(f"missing trajectory source: {path}")
                elif path.stat().st_size != row.get("bytes") or _file_sha256(path) != row.get(
                    "sha256"
                ):
                    errors.append(f"trajectory source drift: {path}")
    prior = receipt.get("prior_finding", {})
    prior_path = workspace / str(prior.get("path"))
    if (
        not prior_path.is_file()
        or prior_path.stat().st_size != prior.get("bytes")
        or _file_sha256(prior_path) != prior.get("sha256")
        or prior.get("sha256") != PRIOR_RECEIPT_SHA256
    ):
        errors.append("bound V2 receipt drift")
    return errors


def _verify_partitions(receipt: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    development = [
        root
        for rows in receipt.get("development_partition", {}).values()
        for root in rows
    ]
    holdout = [
        root
        for rows in receipt.get("unseen_partition", {}).values()
        for root in rows
    ]
    if sorted(development) != sorted(CAMPAIGN.development_roots) or len(development) != len(
        set(development)
    ):
        errors.append("development partition is not unique and complete")
    if sorted(holdout) != sorted(CAMPAIGN.hidden_holdout) or len(holdout) != len(
        set(holdout)
    ):
        errors.append("unseen partition is not unique and complete")
    if set(development).intersection(holdout):
        errors.append("development and unseen partitions overlap")
    return errors


def _reproduce_slices(
    receipt: Mapping[str, Any], workspace: Path
) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    errors: list[str] = []
    reproduced: dict[str, Mapping[str, Any]] = {}
    with _activated():
        for actor, recorded in receipt.get("slices", {}).items():
            development = [_load_world(workspace, root) for root in recorded["assigned_development_roots"]]
            holdout = [_load_world(workspace, root) for root in recorded["assigned_holdout_roots"]]
            present_width = len(PRESENT_ATOMS) * len(legacy.FRAMES) * 3
            max_identities = max(
                int(len(np.unique(world.tracer_index)))
                for world in (*development, *holdout)
            )
            controller = HierarchicalCovariantRecurrentField(
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
            state = controller.fit_snapshot_baseline(
                controller.initial_state(),
                (frame for world in development for frame in _frames(world)),
            )
            if controller.state_sha256(state) != recorded["field"]["baseline_state_sha256"]:
                errors.append(f"{actor}: snapshot field digest mismatch")
            for world in development:
                state = controller.learn_world(state, _frames(world))
            if controller.state_sha256(state) != recorded["field"]["trained_state_sha256"]:
                errors.append(f"{actor}: trained field digest mismatch")
            raw = controller.export_state(state)
            field_record = recorded["field"]
            if len(raw) != field_record["checkpoint_bytes"] or hashlib.sha256(raw).hexdigest() != field_record[
                "checkpoint_sha256"
            ]:
                errors.append(f"{actor}: checkpoint envelope mismatch")
            if controller.inspect(state) != field_record["inspection"]:
                errors.append(f"{actor}: field inspection mismatch")
            actual_worlds: dict[str, Mapping[str, Any]] = {}
            controls: list[dict[str, bool]] = []
            for world in holdout:
                state_before = controller.state_sha256(state)
                measured = _measure(controller, state, world)
                actual_worlds[world.bundle.arm_id] = measured
                controls.append(
                    {
                        "forecast_preserved_training_state": controller.state_sha256(state)
                        == state_before,
                        "identity_break_fired": measured["identity_mismatch_fraction"] >= 0.99
                        and measured["identity_prediction_separation"] > 1e-6,
                    }
                )
            for arm_id, actual in actual_worlds.items():
                expected = recorded["per_world"].get(arm_id)
                if expected is None:
                    errors.append(f"{actor}/{arm_id}: missing recorded world")
                else:
                    errors.extend(_same_metrics(expected, actual, f"{actor}/{arm_id}"))
            if set(actual_worlds) != set(recorded.get("per_world", {})):
                errors.append(f"{actor}: world arm set mismatch")
            actor_summary = _summary(list(actual_worlds.values()))
            errors.extend(_same_metrics(recorded["summary"], actor_summary, f"{actor}.summary"))
            actual_scores = _scores(actor_summary, bool(recorded["controls_passed"]))
            errors.extend(_same_metrics(recorded["lesson_scores"], actual_scores, f"{actor}.scores"))
            inspection = controller.inspect(state)
            checkpoint = controller.import_state(raw)
            first = holdout[0]
            canonical = controller.forecast_world(state, _frames(first))
            restarted = controller.forecast_world(checkpoint, _frames(first))
            # The reversed list is not a valid chronological stream; verify the
            # campaign's actual row-order control by rebuilding each frame row.
            ordered_frames = list(_frames(first))
            reverse_frames = [
                type(frame)(
                    tick=frame.tick,
                    identity_ids=frame.identity_ids[::-1],
                    present=frame.present[::-1],
                    position=frame.position[::-1],
                    velocity=frame.velocity[::-1],
                    delta_time=frame.delta_time,
                    target=frame.target[::-1],
                )
                for frame in ordered_frames
            ]
            reordered = controller.forecast_world(state, reverse_frames)
            row_order_exact = (
                np.array_equal(canonical.identity_ids, reordered.identity_ids)
                and np.array_equal(canonical.causal, reordered.causal)
                and np.array_equal(canonical.combined, reordered.combined)
            )
            restart_exact = controller.state_sha256(checkpoint) == recorded["field"][
                "trained_state_sha256"
            ]
            restart_forecast_exact = (
                np.array_equal(canonical.snapshot_baseline, restarted.snapshot_baseline)
                and np.array_equal(canonical.causal, restarted.causal)
                and np.array_equal(canonical.combined, restarted.combined)
            )
            actual_controls = {
                "development_holdout_disjoint": recorded["controls"][
                    "development_holdout_disjoint"
                ],
                "synthetic_hierarchical_firing": _firing_control(),
                "field_only_adaptive_owner": {
                    "status": "PASS"
                    if inspection["adaptive_owner"] == "RegimeCovariantState.field"
                    else "FAIL",
                    "adaptive_owner": inspection["adaptive_owner"],
                },
                "checkpoint_restart": {
                    "status": "PASS" if restart_exact and restart_forecast_exact else "FAIL",
                    "state_exact": restart_exact,
                    "forecast_exact": restart_forecast_exact,
                },
                "identity_row_order": {
                    "status": "PASS" if row_order_exact else "FAIL",
                    "forecast_exact": row_order_exact,
                },
                "forecast_immutability": {
                    "status": "PASS"
                    if all(row["forecast_preserved_training_state"] for row in controls)
                    else "FAIL"
                },
                "identity_break_fired": {
                    "status": "PASS"
                    if all(row["identity_break_fired"] for row in controls)
                    else "FAIL",
                    "minimum_mismatch_fraction": min(
                        row["identity_mismatch_fraction"]
                        for row in actual_worlds.values()
                    ),
                    "minimum_prediction_separation": min(
                        row["identity_prediction_separation"]
                        for row in actual_worlds.values()
                    ),
                },
            }
            errors.extend(_same_metrics(recorded["controls"], actual_controls, f"{actor}.controls"))
            controls_passed = all(row["status"] == "PASS" for row in actual_controls.values())
            if controls_passed != bool(recorded["controls_passed"]):
                errors.append(f"{actor}: controls aggregate mismatch")
            reproduced[actor] = {
                "per_world": actual_worlds,
                "summary": actor_summary,
                "lesson_scores": actual_scores,
                "controls": actual_controls,
                "controls_passed": controls_passed,
            }
            legacy._load_bundle.cache_clear()
    return reproduced, errors


def _verify_hive(receipt: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    assimilation = receipt.get("hive_assimilation", {})
    selected = assimilation.get("selected_lesson", {}).get("lesson_id")
    root_slice = receipt.get("slices", {}).get("root", {})
    scores = root_slice.get("lesson_scores", {})
    if selected != max(scores, key=scores.get):
        errors.append("root selected lesson is not its highest-scoring result")
    if assimilation.get("root_result_sha256") != _digest(root_slice):
        errors.append("root result digest mismatch")
    support = 0
    for row in assimilation.get("reviews", []):
        member_id = row.get("member_id")
        member_slice = receipt.get("slices", {}).get(member_id, {})
        member_selected = max(
            member_slice.get("lesson_scores", {}),
            key=member_slice.get("lesson_scores", {}).get,
        )
        expected_review = "supports" if member_selected == selected else "refutes"
        if row.get("review", {}).get("result") != expected_review:
            errors.append(f"{member_id}: review verdict disagrees with selection")
        if row.get("result_sha256") != receipt.get("aggregate", {}).get("slice_digests", {}).get(member_id):
            errors.append(f"{member_id}: reviewed result digest mismatch")
        if expected_review == "supports":
            support += 1
    if assimilation.get("support_count") != support:
        errors.append("Hive support count mismatch")
    promoted = support >= int(assimilation.get("quorum", 2))
    if assimilation.get("status") != ("promoted" if promoted else "contested"):
        errors.append("Hive disposition does not follow quorum")
    organism = ResearchOrganism(Path(str(receipt.get("organism_home"))))
    with organism._open_residencies(include_members=True) as (root, members):
        residents = {"root": root, **members}
        generations = {
            resident.session.status()["common_generation"]
            for resident in residents.values()
        }
        if generations != {assimilation.get("hive_generation")}:
            errors.append("live residents do not share the recorded generation")
        bundles = {bundle.object_id for bundle in root.session.hive.list_bundles()}
        learned: dict[str, Any] = {}
        for resident_id, resident in residents.items():
            learned[resident_id] = next(
                (
                    program
                    for program in resident.owner.state.programs
                    if program.program_id == assimilation.get("program_id")
                ),
                None,
            )
        if promoted:
            if assimilation.get("bundle_id") not in bundles:
                errors.append("promoted bundle is absent from collective Hive")
            if set(assimilation.get("adoptions", {})) != set(residents):
                errors.append("promoted adoption population is incomplete")
            for resident_id, program in learned.items():
                if program is None:
                    errors.append(f"{resident_id}: adopted program is absent")
                elif sha256_value(program.as_dict()) != assimilation.get("program_sha256"):
                    errors.append(f"{resident_id}: adopted program bytes mismatch")
        else:
            if assimilation.get("bundle_id") is not None or assimilation.get("adoptions"):
                errors.append("contested lesson produced adoption artifacts")
            if any(program is not None for program in learned.values()):
                errors.append("contested lesson installed a program")
    return errors


def verify(receipt: Mapping[str, Any], workspace: Path) -> dict[str, Any]:
    errors: list[str] = []
    if receipt.get("schema") != SCHEMA:
        errors.append("receipt schema mismatch")
    errors.extend(_verify_sources(receipt, workspace))
    errors.extend(_verify_partitions(receipt))
    reproduced, reproduction_errors = _reproduce_slices(receipt, workspace)
    errors.extend(reproduction_errors)
    errors.extend(_verify_hive(receipt))
    recorded_worlds = [
        world
        for slice_value in receipt.get("slices", {}).values()
        for world in slice_value.get("per_world", {}).values()
    ]
    actual_worlds = [
        world
        for slice_value in reproduced.values()
        for world in slice_value["per_world"].values()
    ]
    aggregate_summary = _summary(recorded_worlds)
    errors.extend(
        _same_metrics(
            receipt.get("aggregate", {}).get("summary", {}),
            aggregate_summary,
            "aggregate.summary",
        )
    )
    controls_passed = all(
        bool(value.get("controls_passed")) for value in receipt.get("slices", {}).values()
    )
    if controls_passed != bool(receipt.get("aggregate", {}).get("controls_passed")):
        errors.append("aggregate control status mismatch")
    aggregate_scores = _scores(aggregate_summary, controls_passed)
    errors.extend(
        _same_metrics(
            receipt.get("aggregate", {}).get("lesson_scores", {}),
            aggregate_scores,
            "aggregate.lesson_scores",
        )
    )
    return {
        "status": "verified" if not errors else "failed",
        "errors": errors,
        "analysis_source_count": len(receipt.get("analysis_sources", [])),
        "trajectory_file_count": sum(
            len(world.get("source_manifest", [])) for world in recorded_worlds
        ),
        "reproduced_world_count": len(actual_worlds),
        "receipt_sha256": hashlib.sha256(_canonical(receipt)).hexdigest(),
        "bundle_id": receipt.get("hive_assimilation", {}).get("bundle_id"),
        "hive_generation": receipt.get("hive_assimilation", {}).get("hive_generation"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve(strict=True)
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = verify(receipt, workspace)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
