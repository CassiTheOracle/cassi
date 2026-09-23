"""Independent reproduction verifier for regime-covariant recurrent memory V2.

This module deliberately does not import the campaign runner.  It rebuilds each
actor's sole adaptive field from the raw disjoint worlds, recomputes every
unseen reading, checks all content bindings, and inspects the live Hive for the
quorum disposition and exact program adoption (or exact non-adoption).
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
from cassi_morphology_operator_invention import CAMPAIGN, SEED_ATOMS, _activated
from cassi_regime_covariant_recurrent_field import (
    CovariantFieldConfig,
    CovariantFrame,
    RegimeCovariantRecurrentField,
)
from cassi_research_organism import ResearchOrganism


SCHEMA = "cassifi.hive-regime-covariant-recurrent-memory.v2"
SLICE_SCHEMA = "cassifi.hive-regime-covariant-recurrent-memory-slice.v2"
LAGS = (1, 2, 4, 8)
PRESENT_ATOMS = tuple(SEED_ATOMS)


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


def _load_world(workspace: Path, relative_root: str) -> v1._World:
    return v1._load_world(workspace, relative_root)


def _delta_time(world: v1._World, slot: int) -> float:
    return float(
        (world.steps[slot] - world.steps[slot - 1])
        * world.dt
        * float(world.bundle.scales["velocity"])
        / float(world.bundle.scales["radius"])
    )


def _frames(world: v1._World) -> Iterator[CovariantFrame]:
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
                    * np.asarray(world.bundle.atoms[atom], dtype=np.float64)[
                        rows, None
                    ]
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


def _rmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((prediction - target) ** 2)))


def _measure(
    controller: RegimeCovariantRecurrentField, state: Any, world: v1._World
) -> dict[str, Any]:
    aligned = controller.forecast_world(state, _frames(world))
    broken = controller.forecast_world(state, _frames(world), break_identity=True)
    lookup = _target_map(world)
    target = np.stack(
        [
            lookup[(int(tick), int(identity))]
            for tick, identity in zip(
                aligned.ticks.tolist(), aligned.identity_ids.tolist(), strict=True
            )
        ]
    )
    target_rms = _rmse(np.zeros_like(target), target)
    separation = float(
        np.linalg.norm(aligned.combined - broken.combined)
        / max(
            float(np.linalg.norm(aligned.combined))
            + float(np.linalg.norm(broken.combined)),
            1e-300,
        )
    )
    result: dict[str, Any] = {
        "sample_count": aligned.resolved_count,
        "target_rms": target_rms,
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
        snapshot = _rmse(aligned.snapshot_baseline, target) / target_rms
        causal = _rmse(aligned.causal, target) / target_rms
        covariant = _rmse(aligned.combined, target) / target_rms
        identity_broken = _rmse(broken.combined, target) / target_rms
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
    return result


def _summary(worlds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    scored = [row for row in worlds if row.get("status") == "SCORED"]
    null = [row for row in worlds if row.get("status") == "NULL_ZERO_TARGET"]
    learned = [
        float(row["learned_correction_fractional_rmse_reduction"])
        for row in scored
    ]

    def mean(key: str) -> float:
        return float(np.mean([float(row[key]) for row in scored]))

    return {
        "world_count": len(worlds),
        "scored_world_count": len(scored),
        "null_zero_target_world_count": len(null),
        "sample_count": sum(int(row["sample_count"]) for row in worlds),
        "mean_snapshot_nrmse": mean("snapshot_nrmse"),
        "mean_causal_nrmse": mean("causal_nrmse"),
        "mean_covariant_nrmse": mean("covariant_nrmse"),
        "mean_causal_vs_snapshot_fractional_rmse_reduction": mean(
            "causal_vs_snapshot_fractional_rmse_reduction"
        ),
        "mean_learned_correction_fractional_rmse_reduction": float(
            np.mean(learned)
        ),
        "minimum_learned_correction_fractional_rmse_reduction": min(learned),
        "positive_learned_world_count": sum(value > 0.0 for value in learned),
        "positive_learned_world_fraction": float(
            np.mean(np.asarray(learned) > 0.0)
        ),
        "mean_total_memory_fractional_rmse_reduction": mean(
            "total_memory_fractional_rmse_reduction"
        ),
        "mean_identity_advantage": mean("identity_advantage"),
    }


def _scores(summary: Mapping[str, Any], controls_passed: bool) -> dict[str, float]:
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


def _same_metrics(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, value in actual.items():
        if isinstance(value, (str, bool, int)):
            if expected.get(key) != value:
                errors.append(f"{key}: {expected.get(key)!r} != {value!r}")
        elif not _close(expected.get(key), value):
            errors.append(f"{key}: {expected.get(key)!r} != {value!r}")
    return errors


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
    ):
        errors.append("bound V1 receipt drift")
    return errors


def _verify_partitions(receipt: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    development_partition = receipt.get("development_partition", {})
    holdout_partition = receipt.get("unseen_partition", {})
    development = [row for rows in development_partition.values() for row in rows]
    holdout = [row for rows in holdout_partition.values() for row in rows]
    if sorted(development) != sorted(CAMPAIGN.development_roots) or len(
        development
    ) != len(set(development)):
        errors.append("development partition is not unique and complete")
    if sorted(holdout) != sorted(CAMPAIGN.hidden_holdout) or len(holdout) != len(
        set(holdout)
    ):
        errors.append("unseen partition is not unique and complete")
    if set(development).intersection(holdout):
        errors.append("development and unseen partitions overlap")
    for actor, slice_value in receipt.get("slices", {}).items():
        if slice_value.get("schema") != SLICE_SCHEMA or slice_value.get("actor") != actor:
            errors.append(f"slice identity mismatch: {actor}")
        if list(development_partition.get(actor, [])) != slice_value.get(
            "assigned_development_roots"
        ):
            errors.append(f"development slice mismatch: {actor}")
        if list(holdout_partition.get(actor, [])) != slice_value.get(
            "assigned_holdout_roots"
        ):
            errors.append(f"unseen slice mismatch: {actor}")
        if receipt.get("aggregate", {}).get("slice_digests", {}).get(actor) != _digest(
            slice_value
        ):
            errors.append(f"slice digest mismatch: {actor}")
    return errors


def _reproduce_slices(
    receipt: Mapping[str, Any], workspace: Path
) -> tuple[list[str], dict[str, Mapping[str, Any]]]:
    errors: list[str] = []
    reproduced: dict[str, Mapping[str, Any]] = {}
    with _activated():
        for actor, recorded in receipt.get("slices", {}).items():
            development = [
                _load_world(workspace, root)
                for root in recorded["assigned_development_roots"]
            ]
            holdout = [
                _load_world(workspace, root)
                for root in recorded["assigned_holdout_roots"]
            ]
            controller = RegimeCovariantRecurrentField(
                CovariantFieldConfig(
                    present_width=len(PRESENT_ATOMS) * len(legacy.FRAMES) * 3,
                    max_identities=max(
                        len(np.unique(world.tracer_index))
                        for world in (*development, *holdout)
                    ),
                    lags=LAGS,
                    correction_ridge=0.1,
                )
            )
            state = controller.fit_snapshot_baseline(
                controller.initial_state(),
                (frame for world in development for frame in _frames(world)),
            )
            if controller.state_sha256(state) != recorded["field"][
                "baseline_state_sha256"
            ]:
                errors.append(f"{actor}: snapshot field digest mismatch")
            for world in development:
                state = controller.learn_world(state, _frames(world))
            raw = controller.export_state(state)
            if controller.state_sha256(state) != recorded["field"][
                "trained_state_sha256"
            ]:
                errors.append(f"{actor}: trained field digest mismatch")
            if len(raw) != recorded["field"]["checkpoint_bytes"] or hashlib.sha256(
                raw
            ).hexdigest() != recorded["field"]["checkpoint_sha256"]:
                errors.append(f"{actor}: checkpoint envelope mismatch")
            if controller.inspect(state) != recorded["field"]["inspection"]:
                errors.append(f"{actor}: field inspection mismatch")
            actor_worlds: list[Mapping[str, Any]] = []
            for world in holdout:
                metrics = _measure(controller, state, world)
                expected = recorded["per_world"].get(world.bundle.arm_id)
                if not isinstance(expected, Mapping):
                    errors.append(f"{actor}: missing world {world.bundle.arm_id}")
                    continue
                errors.extend(
                    f"{actor}/{world.bundle.arm_id}: {difference}"
                    for difference in _same_metrics(expected, metrics)
                )
                actor_worlds.append(metrics)
                reproduced[world.bundle.arm_id] = metrics
            actor_summary = _summary(actor_worlds)
            errors.extend(
                f"{actor}/summary: {difference}"
                for difference in _same_metrics(recorded["summary"], actor_summary)
            )
            for key, value in _scores(
                actor_summary, bool(recorded["controls_passed"])
            ).items():
                if not _close(recorded["lesson_scores"].get(key), value):
                    errors.append(f"{actor}: lesson score mismatch for {key}")
            legacy._load_bundle.cache_clear()
    return errors, reproduced


def _verify_hive(receipt: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    assimilation = receipt.get("hive_assimilation", {})
    selected = assimilation.get("selected_lesson", {}).get("lesson_id")
    root_slice = receipt.get("slices", {}).get("root", {})
    if selected != max(
        root_slice.get("lesson_scores", {}),
        key=root_slice.get("lesson_scores", {}).get,
        default=None,
    ):
        errors.append("root-selected lesson is not its highest-scoring result")
    if assimilation.get("root_result_sha256") != _digest(root_slice):
        errors.append("root result digest mismatch")
    support = 0
    for row in assimilation.get("reviews", []):
        member_id = row.get("member_id")
        member_slice = receipt.get("slices", {}).get(member_id, {})
        member_selected = max(
            member_slice.get("lesson_scores", {}),
            key=member_slice.get("lesson_scores", {}).get,
            default=None,
        )
        if row.get("selection", {}).get("lesson_id") != member_selected:
            errors.append(f"{member_id}: selected lesson is not its highest score")
        expected_review = "supports" if member_selected == selected else "refutes"
        if row.get("review", {}).get("result") != expected_review:
            errors.append(f"{member_id}: review verdict is inconsistent with selection")
        if row.get("result_sha256") != receipt.get("aggregate", {}).get(
            "slice_digests", {}
        ).get(member_id):
            errors.append(f"{member_id}: reviewed result digest mismatch")
        support += int(expected_review == "supports")
    if assimilation.get("support_count") != support:
        errors.append("Hive support count mismatch")
    promoted = support >= int(assimilation.get("quorum", 2))
    if assimilation.get("status") != ("promoted" if promoted else "contested"):
        errors.append("Hive disposition does not follow quorum")
    organism = ResearchOrganism(Path(str(receipt.get("organism_home"))))
    with organism._open_residencies(include_members=True) as (root, members):
        residents = {"root": root, **members}
        generations = {
            residency.session.status()["common_generation"]
            for residency in residents.values()
        }
        if generations != {assimilation.get("hive_generation")}:
            errors.append("live residents do not share the recorded generation")
        bundle_ids = {bundle.object_id for bundle in root.session.hive.list_bundles()}
        learned = {
            resident_id: next(
                (
                    program
                    for program in residency.owner.state.programs
                    if program.program_id == assimilation.get("program_id")
                ),
                None,
            )
            for resident_id, residency in residents.items()
        }
        if promoted:
            if set(assimilation.get("adoptions", {})) != set(residents):
                errors.append("promoted adoption population is incomplete")
            if assimilation.get("bundle_id") not in bundle_ids:
                errors.append("promoted bundle is absent from collective Hive")
            for resident_id, program in learned.items():
                if program is None or sha256_value(program.as_dict()) != assimilation.get(
                    "program_sha256"
                ):
                    errors.append(f"{resident_id}: adopted program bytes mismatch")
        else:
            if assimilation.get("bundle_id") is not None or assimilation.get("adoptions"):
                errors.append("contested lesson produced adoption artifacts")
            if any(program is not None for program in learned.values()):
                errors.append("contested lesson was installed in a resident")
    return errors


def verify(
    receipt: Mapping[str, Any], *, workspace: Path, reproduce: bool = True
) -> dict[str, Any]:
    errors: list[str] = []
    if receipt.get("schema") != SCHEMA:
        errors.append("receipt schema mismatch")
    errors.extend(_verify_sources(receipt, workspace))
    errors.extend(_verify_partitions(receipt))
    reproduced: dict[str, Mapping[str, Any]] = {}
    if reproduce and not errors:
        reproduction_errors, reproduced = _reproduce_slices(receipt, workspace)
        errors.extend(reproduction_errors)
    recorded_worlds = [
        world
        for slice_value in receipt.get("slices", {}).values()
        for world in slice_value.get("per_world", {}).values()
    ]
    if recorded_worlds:
        aggregate_summary = _summary(recorded_worlds)
        errors.extend(
            f"aggregate: {difference}"
            for difference in _same_metrics(
                receipt.get("aggregate", {}).get("summary", {}), aggregate_summary
            )
        )
        controls_passed = all(
            bool(value.get("controls_passed"))
            for value in receipt.get("slices", {}).values()
        )
        if controls_passed != receipt.get("aggregate", {}).get("controls_passed"):
            errors.append("aggregate control status mismatch")
        for key, value in _scores(aggregate_summary, controls_passed).items():
            if not _close(
                receipt.get("aggregate", {}).get("lesson_scores", {}).get(key), value
            ):
                errors.append(f"aggregate lesson score mismatch for {key}")
    errors.extend(_verify_hive(receipt))
    return {
        "status": "verified" if not errors else "failed",
        "errors": errors,
        "analysis_source_count": len(receipt.get("analysis_sources", [])),
        "trajectory_file_count": sum(
            len(world.get("source_manifest", [])) for world in recorded_worlds
        ),
        "reproduced_world_count": len(reproduced),
        "receipt_sha256": hashlib.sha256(_canonical(receipt)).hexdigest(),
        "bundle_id": receipt.get("hive_assimilation", {}).get("bundle_id"),
        "hive_generation": receipt.get("hive_assimilation", {}).get(
            "hive_generation"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--no-reproduce", action="store_true")
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = verify(
        receipt,
        workspace=args.workspace.resolve(strict=True),
        reproduce=not args.no_reproduce,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
