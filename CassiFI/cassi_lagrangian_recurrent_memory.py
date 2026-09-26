"""Hive population challenge for native identity-bound trajectory memory.

The root and every independent member learn their own recurrent field from
disjoint development worlds, then forecast disjoint worlds that were absent from
the temporal-authority experiment.  Results can only enter the living research
organism through quorum-reviewed Hive assimilation; no isolated experiment entry
point exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import numpy as np

import cassi_full_observable_invention as legacy
import cassi_temporal_residual_authority as temporal
from cassi_lagrangian_recurrent_field import (
    LagrangianFieldConfig,
    LagrangianFrame,
    LagrangianRecurrentField,
    LagrangianRecurrentState,
)
from cassi_morphology_operator_invention import CAMPAIGN, SEED_ATOMS, _activated
from cassi_research_organism import ResearchOrganism


SCHEMA = "cassifi.hive-lagrangian-recurrent-memory.v1"
SLICE_SCHEMA = "cassifi.hive-lagrangian-recurrent-memory-slice.v1"
EXPERIMENT_ID = "lagrangian-recurrent-memory-v1"
LABORATORY_ID = "lagrangian-trajectory-memory"
PRIOR_RECEIPT = "CassiFI/_diag/temporal-residual-authority-v2.json"
LAGS = (1, 2, 4, 8)
PRESENT_ATOMS = tuple(SEED_ATOMS)
CHANNELS = temporal.CHANNELS
ANALYSIS_SOURCES = (
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
    "native-lagrangian-memory-transfer": (
        "A field-owned identity-bound recurrent trajectory memory improves "
        "acceleration forecasts in worlds excluded from its fit."
    ),
    "native-regime-memory-transfer": (
        "Recurrent history transfers across worlds, but bound tracer identity "
        "does not materially strengthen the forecast."
    ),
    "native-memory-no-transfer": (
        "The executable recurrent field does not improve acceleration forecasts "
        "in worlds excluded from its fit."
    ),
}


class LagrangianCampaignError(RuntimeError):
    """Raised when the integrated population challenge is not admissible."""


@dataclass(slots=True)
class _World:
    relative_root: str
    bundle: legacy.FeatureBundle
    tracer_index: np.ndarray
    source_manifest: list[dict[str, Any]]
    steps: np.ndarray
    dt: float


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
            raise LagrangianCampaignError(f"analysis source is absent: {relative}")
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
        raise LagrangianCampaignError("promoted temporal finding is unavailable") from exc
    assimilation = receipt.get("hive_assimilation", {})
    if (
        receipt.get("schema") != "cassifi.hive-temporal-residual-authority.v2"
        or receipt.get("aggregate", {}).get("arm_count") != 16
        or assimilation.get("selected_lesson", {}).get("lesson_id")
        != "trajectory-history-authority"
        or assimilation.get("support_count", 0) < assimilation.get("quorum", 2)
        or not isinstance(assimilation.get("bundle_id"), str)
    ):
        raise LagrangianCampaignError("promoted temporal finding is not admissible")
    return {
        "path": PRIOR_RECEIPT,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "experiment_id": receipt["experiment_id"],
        "selected_lesson_id": assimilation["selected_lesson"]["lesson_id"],
        "bundle_id": assimilation["bundle_id"],
        "mean_history_fractional_rmse_reduction": receipt["aggregate"]["summary"][
            "mean_all_history_fractional_rmse_reduction"
        ],
        "mean_identity_advantage": receipt["aggregate"]["summary"][
            "mean_identity_advantage"
        ],
    }


def _load_world(workspace: Path, relative_root: str) -> _World:
    root = (workspace / relative_root).resolve(strict=True)
    bundle = legacy._load_bundle(str(root))
    tracer_index, steps, dt, source_manifest = temporal._trajectory_rows(root, bundle)
    return _World(
        relative_root=relative_root,
        bundle=bundle,
        tracer_index=tracer_index,
        source_manifest=source_manifest,
        steps=steps,
        dt=dt,
    )


def _present_rows(bundle: legacy.FeatureBundle, rows: slice) -> np.ndarray:
    return np.concatenate(
        [
            np.asarray(bundle.frames[frame], dtype=np.float64)[rows]
            * np.asarray(bundle.atoms[atom], dtype=np.float64)[rows, None]
            for atom in PRESENT_ATOMS
            for frame in legacy.FRAMES
        ],
        axis=1,
    )


def _history_rows(bundle: legacy.FeatureBundle, rows: slice) -> np.ndarray:
    return np.concatenate(
        [
            np.asarray(bundle.frames[channel.frame], dtype=np.float64)[rows]
            * np.asarray(bundle.atoms[channel.atom], dtype=np.float64)[rows, None]
            for channel in CHANNELS
        ],
        axis=1,
    )


def _frames(world: _World, *, reverse_rows: bool = False) -> Iterator[LagrangianFrame]:
    middle = np.asarray(world.bundle.middle_index, dtype=np.int64)
    if len(middle) == 0 or np.any(np.diff(middle) < 0):
        raise LagrangianCampaignError(
            f"trajectory rows are not chronologically grouped: {world.relative_root}"
        )
    starts = np.r_[0, np.flatnonzero(np.diff(middle)) + 1]
    stops = np.r_[starts[1:], len(middle)]
    for start, stop in zip(starts.tolist(), stops.tolist(), strict=True):
        rows = slice(start, stop)
        identities = np.asarray(world.tracer_index[rows], dtype=np.int64)
        present = _present_rows(world.bundle, rows)
        history = _history_rows(world.bundle, rows)
        target = np.asarray(world.bundle.target, dtype=np.float64)[rows]
        if reverse_rows:
            identities = identities[::-1]
            present = present[::-1]
            history = history[::-1]
            target = target[::-1]
        yield LagrangianFrame(
            tick=int(middle[start]) + 1,
            identity_ids=identities,
            present=present,
            history=history,
            target=target,
        )


def _target_lookup(world: _World) -> dict[tuple[int, int], np.ndarray]:
    middle = np.asarray(world.bundle.middle_index, dtype=np.int64)
    target = np.asarray(world.bundle.target, dtype=np.float64)
    return {
        (int(slot) + 1, int(identity)): target[index].copy()
        for index, (slot, identity) in enumerate(
            zip(middle.tolist(), world.tracer_index.tolist(), strict=True)
        )
    }


def _targets(
    lookup: Mapping[tuple[int, int], np.ndarray],
    ticks: np.ndarray,
    identities: np.ndarray,
) -> np.ndarray:
    try:
        return np.stack(
            [
                lookup[(int(tick), int(identity))]
                for tick, identity in zip(ticks.tolist(), identities.tolist(), strict=True)
            ]
        )
    except KeyError as exc:
        raise LagrangianCampaignError("forecast identity is absent from its world target") from exc


def _rmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((prediction - target) ** 2)))


def _nrmse(prediction: np.ndarray, target: np.ndarray) -> float:
    target_rms = _rmse(np.zeros_like(target), target)
    if not math.isfinite(target_rms) or target_rms == 0.0:
        raise LagrangianCampaignError("holdout acceleration target is exactly zero")
    return float(_rmse(prediction, target) / target_rms)


def _firing_control() -> dict[str, Any]:
    controller = LagrangianRecurrentField(
        LagrangianFieldConfig(
            present_width=1,
            history_width=1,
            target_width=1,
            lags=(1,),
            max_identities=4,
        )
    )

    def world(seed: int) -> list[LagrangianFrame]:
        rng = np.random.default_rng(seed)
        ids = np.arange(4, dtype=np.int64)
        previous = rng.normal(size=4)
        result: list[LagrangianFrame] = []
        for tick in range(1, 49):
            current = rng.normal(size=4)
            target = (1.75 * previous)[:, None]
            result.append(
                LagrangianFrame(
                    tick=tick,
                    identity_ids=ids,
                    present=np.zeros((4, 1), dtype=np.float64),
                    history=current[:, None],
                    target=target,
                )
            )
            previous = current
        return result

    training = world(7103)
    holdout = world(7109)
    state = controller.fit_baseline(controller.initial_state(), training)
    state = controller.learn_world(state, training)
    forecast = controller.forecast_world(state, holdout)
    target = _targets(
        {
            (frame.tick, int(identity)): frame.target[index]
            for frame in holdout
            for index, identity in enumerate(frame.identity_ids)
        },
        forecast.ticks,
        forecast.identity_ids,
    )
    baseline = _nrmse(forecast.baseline, target)
    enriched = _nrmse(forecast.combined, target)
    reduction = float(1.0 - enriched / baseline)
    return {
        "status": "PASS" if reduction > 0.95 else "FAIL",
        "baseline_nrmse": baseline,
        "enriched_nrmse": enriched,
        "fractional_rmse_reduction": reduction,
        "bound": 0.95,
    }


def _measure_world(
    controller: LagrangianRecurrentField,
    trained: LagrangianRecurrentState,
    world: _World,
) -> tuple[dict[str, Any], dict[str, bool]]:
    state_before = controller.state_sha256(trained)
    aligned = controller.forecast_world(trained, _frames(world))
    broken = controller.forecast_world(trained, _frames(world), break_identity=True)
    if not np.array_equal(aligned.ticks, broken.ticks) or not np.array_equal(
        aligned.identity_ids, broken.identity_ids
    ):
        raise LagrangianCampaignError("identity control changed the evaluated population")
    target = _targets(_target_lookup(world), aligned.ticks, aligned.identity_ids)
    target_rms = _rmse(np.zeros_like(target), target)
    separation = float(
        np.linalg.norm(aligned.combined - broken.combined)
        / max(
            float(np.linalg.norm(aligned.combined))
            + float(np.linalg.norm(broken.combined)),
            1e-12,
        )
    )
    result = {
        "arm_id": world.bundle.arm_id,
        "source_root": world.relative_root,
        "source_summary": dict(world.bundle.source_summary),
        "source_manifest": world.source_manifest,
        "sample_count": aligned.resolved_count,
        "target_rms": target_rms,
        "physical_lags": {
            str(lag): float(
                np.median(
                    (world.steps[1 + lag :] - world.steps[1 : -lag]) * world.dt
                )
            )
            for lag in LAGS
        },
        "identity_mismatch_fraction": broken.identity_mismatch_fraction,
        "identity_prediction_separation": separation,
    }
    if target_rms == 0.0:
        result.update({
            "status": "NULL_ZERO_TARGET",
            "baseline_rmse": _rmse(aligned.baseline, target),
            "aligned_memory_rmse": _rmse(aligned.combined, target),
            "identity_broken_memory_rmse": _rmse(broken.combined, target),
        })
    else:
        baseline_nrmse = _nrmse(aligned.baseline, target)
        aligned_nrmse = _nrmse(aligned.combined, target)
        broken_nrmse = _nrmse(broken.combined, target)
        result.update({
            "status": "SCORED",
            "baseline_nrmse": baseline_nrmse,
            "aligned_memory_nrmse": aligned_nrmse,
            "identity_broken_memory_nrmse": broken_nrmse,
            "aligned_fractional_rmse_reduction": float(
                1.0 - aligned_nrmse / baseline_nrmse
            ),
            "identity_broken_fractional_rmse_reduction": float(
                1.0 - broken_nrmse / baseline_nrmse
            ),
            "identity_advantage": float(
                (broken_nrmse - aligned_nrmse) / baseline_nrmse
            ),
        })
    controls = {
        "forecast_preserved_training_state": controller.state_sha256(trained)
        == state_before,
        "identity_break_fired": broken.identity_mismatch_fraction >= 0.99
        and separation > 1e-6,
    }
    return result, controls


def _mean(rows: Iterable[float]) -> float:
    values = [float(row) for row in rows]
    if not values:
        raise LagrangianCampaignError("cannot summarize an empty population")
    return float(np.mean(values))


def _summary(worlds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    scored = [row for row in worlds if row.get("status") == "SCORED"]
    null = [row for row in worlds if row.get("status") == "NULL_ZERO_TARGET"]
    if len(scored) + len(null) != len(worlds):
        raise LagrangianCampaignError("unseen world has an unsupported scoring status")
    aligned = [
        float(row["aligned_fractional_rmse_reduction"]) for row in scored
    ]
    broken = [
        float(row["identity_broken_fractional_rmse_reduction"]) for row in scored
    ]
    return {
        "world_count": len(worlds),
        "scored_world_count": len(scored),
        "null_zero_target_world_count": len(null),
        "sample_count": int(sum(int(row["sample_count"]) for row in worlds)),
        "mean_aligned_fractional_rmse_reduction": _mean(aligned),
        "mean_identity_broken_fractional_rmse_reduction": _mean(broken),
        "mean_identity_advantage": _mean(
            float(row["identity_advantage"]) for row in scored
        ),
        "positive_world_count": int(sum(value > 0.0 for value in aligned)),
        "positive_world_fraction": float(np.mean(np.asarray(aligned) > 0.0)),
        "minimum_aligned_fractional_rmse_reduction": min(aligned),
    }


def _lesson_scores(summary: Mapping[str, Any], *, controls_passed: bool) -> dict[str, float]:
    if not controls_passed:
        return {
            "native-lagrangian-memory-transfer": 0.0,
            "native-regime-memory-transfer": 0.0,
            "native-memory-no-transfer": 1.0,
        }
    effect = float(
        np.clip(
            max(float(summary["mean_aligned_fractional_rmse_reduction"]), 0.0)
            / 0.02,
            0.0,
            1.0,
        )
    )
    positive = float(np.clip(summary["positive_world_fraction"], 0.0, 1.0))
    identity = float(
        np.clip(max(float(summary["mean_identity_advantage"]), 0.0) / 0.01, 0.0, 1.0)
    )
    return {
        "native-lagrangian-memory-transfer": float(
            np.clip(0.45 * effect + 0.25 * positive + 0.30 * identity, 0.0, 1.0)
        ),
        "native-regime-memory-transfer": float(
            np.clip(0.50 * effect + 0.25 * positive + 0.25 * (1.0 - identity), 0.0, 1.0)
        ),
        "native-memory-no-transfer": float(
            np.clip(0.65 * (1.0 - effect) + 0.35 * (1.0 - positive), 0.0, 1.0)
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
        raise LagrangianCampaignError(f"actor lacks a complete assignment: {actor}")
    if set(development_roots).intersection(holdout_roots):
        raise LagrangianCampaignError("development and unseen worlds overlap")
    development = [_load_world(workspace, root) for root in development_roots]
    holdout = [_load_world(workspace, root) for root in holdout_roots]
    present_width = len(PRESENT_ATOMS) * len(legacy.FRAMES) * 3
    history_width = len(CHANNELS) * 3
    max_identities = max(
        int(len(np.unique(world.tracer_index)))
        for world in (*development, *holdout)
    )
    controller = LagrangianRecurrentField(
        LagrangianFieldConfig(
            present_width=present_width,
            history_width=history_width,
            target_width=3,
            lags=LAGS,
            max_identities=max_identities,
        )
    )
    state = controller.fit_baseline(
        controller.initial_state(),
        (frame for world in development for frame in _frames(world)),
    )
    baseline_state_sha256 = controller.state_sha256(state)
    for world in development:
        state = controller.learn_world(state, _frames(world))
    trained_state_sha256 = controller.state_sha256(state)
    checkpoint = controller.export_state(state)
    restarted = controller.import_state(checkpoint)
    restart_exact = controller.state_sha256(restarted) == trained_state_sha256

    per_world: dict[str, dict[str, Any]] = {}
    control_rows: list[dict[str, bool]] = []
    for world in holdout:
        measured, controls = _measure_world(controller, state, world)
        per_world[measured["arm_id"]] = measured
        control_rows.append(controls)
    first = holdout[0]
    canonical = controller.forecast_world(state, _frames(first))
    restart_forecast = controller.forecast_world(restarted, _frames(first))
    reordered = controller.forecast_world(state, _frames(first, reverse_rows=True))
    restart_forecast_exact = np.array_equal(
        canonical.combined, restart_forecast.combined
    ) and np.array_equal(canonical.baseline, restart_forecast.baseline)
    row_order_exact = np.array_equal(
        canonical.combined, reordered.combined
    ) and np.array_equal(canonical.identity_ids, reordered.identity_ids)

    summary = _summary(list(per_world.values()))
    controls = {
        "development_holdout_disjoint": {
            "status": "PASS",
            "development_world_count": len(development_roots),
            "holdout_world_count": len(holdout_roots),
        },
        "synthetic_lag_firing": dict(firing_control),
        "field_only_adaptive_owner": {
            "status": (
                "PASS"
                if controller.inspect(state)["adaptive_owner"]
                == "LagrangianRecurrentState.field"
                else "FAIL"
            ),
            "adaptive_owner": controller.inspect(state)["adaptive_owner"],
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
            "status": (
                "PASS"
                if all(row["forecast_preserved_training_state"] for row in control_rows)
                else "FAIL"
            ),
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
            "independently fitted field; disjoint development worlds and disjoint "
            "unseen physical holdouts"
        ),
        "assigned_development_roots": list(development_roots),
        "assigned_holdout_roots": list(holdout_roots),
        "prior_finding": dict(prior),
        "analysis_sources": [dict(row) for row in analysis_sources],
        "memory_contract": {
            "present_atoms": list(PRESENT_ATOMS),
            "present_frames": list(legacy.FRAMES),
            "history_channels": [channel.as_dict() for channel in CHANNELS],
            "lags": list(LAGS),
            "prediction_order": "read identity-bound lags, forecast, then admit current observation",
            "adaptive_owner": "LagrangianRecurrentState.field",
        },
        "field": {
            "baseline_state_sha256": baseline_state_sha256,
            "trained_state_sha256": trained_state_sha256,
            "checkpoint_bytes": len(checkpoint),
            "checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
            "inspection": controller.inspect(state),
        },
        "per_world": per_world,
        "summary": summary,
        "controls": controls,
        "controls_passed": controls_passed,
    }
    result["lesson_scores"] = _lesson_scores(summary, controls_passed=controls_passed)
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
                "mean_aligned_fractional_rmse_reduction": summary[
                    "mean_aligned_fractional_rmse_reduction"
                ],
                "mean_identity_advantage": summary["mean_identity_advantage"],
                "positive_world_fraction": summary["positive_world_fraction"],
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
            raise LagrangianCampaignError("slice actor differs from its assignment")
        development.extend(result["assigned_development_roots"])
        holdout.extend(result["assigned_holdout_roots"])
        worlds.extend(result["per_world"].values())
    if sorted(development) != sorted(expected_development) or len(development) != len(
        expected_development
    ):
        raise LagrangianCampaignError("development population is not disjoint and complete")
    if sorted(holdout) != sorted(expected_holdout) or len(holdout) != len(expected_holdout):
        raise LagrangianCampaignError("unseen population is not disjoint and complete")
    summary = _summary(worlds)
    controls_passed = all(bool(result["controls_passed"]) for result in slices.values())
    return {
        "actor_count": len(slices),
        "development_world_count": len(development),
        "unseen_world_count": len(holdout),
        "summary": summary,
        "controls_passed": controls_passed,
        "lesson_scores": _lesson_scores(summary, controls_passed=controls_passed),
        "slice_digests": {actor: _digest(result) for actor, result in slices.items()},
    }


def run_hive_campaign(workspace: Path, organism_home: Path) -> dict[str, Any]:
    """Run the complete population challenge and assimilate its selected lesson."""

    workspace = Path(workspace).resolve(strict=True)
    organism_home = Path(organism_home).resolve()
    organism = ResearchOrganism(organism_home, workspace=workspace)
    if not organism.manifest_path.is_file():
        raise LagrangianCampaignError(
            "Lagrangian memory requires an initialized living research organism"
        )
    manifest = organism._load_manifest()
    member_ids = tuple(str(value) for value in manifest["member_ids"])
    if len(member_ids) < 2:
        raise LagrangianCampaignError(
            "Lagrangian memory requires at least two independent Hive reviewers"
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
    if any(not rows for rows in (*development_partitions.values(), *holdout_partitions.values())):
        raise LagrangianCampaignError("population exceeds the available world count")

    prior = _prior_finding(workspace)
    analysis_sources = _source_manifest(workspace, manifest["source_paths"])
    firing = _firing_control()
    if firing["status"] != "PASS":
        raise LagrangianCampaignError("native lag firing control failed")
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
    member_results = {member_id: slices[member_id] for member_id in member_ids}
    assimilation = organism.assimilate_experiment(
        experiment_id=EXPERIMENT_ID,
        laboratory_id=LABORATORY_ID,
        objective=(
            "make identity-aligned trajectory history executable as a field-owned "
            "recurrent memory and test transfer to worlds excluded from fitting"
        ),
        root_result=slices["root"],
        lessons=_lessons(slices["root"]),
        member_results=member_results,
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
