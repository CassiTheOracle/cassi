"""Independent reproduction and Hive-adoption verifier for recurrent memory V1.

The verifier does not import the campaign runner.  It checks every bound source,
rebuilds each actor's field from the raw trajectory worlds, recomputes all held-out
readings, and then inspects the live population for exact program adoption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import numpy as np

import cassi_full_observable_invention as legacy
import cassi_temporal_residual_authority as temporal
from cassi_field_atlas import sha256_value
from cassi_lagrangian_recurrent_field import (
    LagrangianFieldConfig,
    LagrangianFrame,
    LagrangianRecurrentField,
)
from cassi_morphology_operator_invention import CAMPAIGN, SEED_ATOMS, _activated
from cassi_research_organism import ResearchOrganism

SCHEMA = "cassifi.hive-lagrangian-recurrent-memory.v1"
SLICE_SCHEMA = "cassifi.hive-lagrangian-recurrent-memory-slice.v1"
LAGS = (1, 2, 4, 8)
PRESENT_ATOMS = tuple(SEED_ATOMS)
CHANNELS = temporal.CHANNELS


@dataclass(slots=True)
class _World:
    root: str
    bundle: legacy.FeatureBundle
    tracer_index: np.ndarray


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


def _load_world(workspace: Path, root: str) -> _World:
    resolved = (workspace / root).resolve(strict=True)
    bundle = legacy._load_bundle(str(resolved))
    tracer_index, _, _, _ = temporal._trajectory_rows(resolved, bundle)
    return _World(root=root, bundle=bundle, tracer_index=tracer_index)


def _present(bundle: legacy.FeatureBundle, rows: slice) -> np.ndarray:
    return np.concatenate(
        [
            np.asarray(bundle.frames[frame], dtype=np.float64)[rows]
            * np.asarray(bundle.atoms[atom], dtype=np.float64)[rows, None]
            for atom in PRESENT_ATOMS
            for frame in legacy.FRAMES
        ],
        axis=1,
    )


def _history(bundle: legacy.FeatureBundle, rows: slice) -> np.ndarray:
    return np.concatenate(
        [
            np.asarray(bundle.frames[channel.frame], dtype=np.float64)[rows]
            * np.asarray(bundle.atoms[channel.atom], dtype=np.float64)[rows, None]
            for channel in CHANNELS
        ],
        axis=1,
    )


def _frames(world: _World) -> Iterator[LagrangianFrame]:
    middle = np.asarray(world.bundle.middle_index, dtype=np.int64)
    starts = np.r_[0, np.flatnonzero(np.diff(middle)) + 1]
    stops = np.r_[starts[1:], len(middle)]
    for start, stop in zip(starts.tolist(), stops.tolist(), strict=True):
        rows = slice(start, stop)
        yield LagrangianFrame(
            tick=int(middle[start]) + 1,
            identity_ids=np.asarray(world.tracer_index[rows], dtype=np.int64),
            present=_present(world.bundle, rows),
            history=_history(world.bundle, rows),
            target=np.asarray(world.bundle.target, dtype=np.float64)[rows],
        )


def _target_map(world: _World) -> dict[tuple[int, int], np.ndarray]:
    return {
        (int(slot) + 1, int(identity)): np.asarray(world.bundle.target[index], dtype=np.float64)
        for index, (slot, identity) in enumerate(
            zip(
                np.asarray(world.bundle.middle_index).tolist(),
                world.tracer_index.tolist(),
                strict=True,
            )
        )
    }


def _rmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((prediction - target) ** 2)))


def _nrmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(_rmse(prediction, target) / _rmse(np.zeros_like(target), target))


def _measure(controller: LagrangianRecurrentField, state: Any, world: _World) -> dict[str, Any]:
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
            1e-12,
        )
    )
    result = {
        "sample_count": aligned.resolved_count,
        "target_rms": target_rms,
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
        baseline = _nrmse(aligned.baseline, target)
        enriched = _nrmse(aligned.combined, target)
        broken_error = _nrmse(broken.combined, target)
        result.update({
            "status": "SCORED",
            "baseline_nrmse": baseline,
            "aligned_memory_nrmse": enriched,
            "identity_broken_memory_nrmse": broken_error,
            "aligned_fractional_rmse_reduction": 1.0 - enriched / baseline,
            "identity_broken_fractional_rmse_reduction": 1.0 - broken_error / baseline,
            "identity_advantage": (broken_error - enriched) / baseline,
        })
    return result


def _scores(summary: Mapping[str, Any], controls_passed: bool) -> dict[str, float]:
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


def _summary(worlds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    scored = [row for row in worlds if row.get("status") == "SCORED"]
    null = [row for row in worlds if row.get("status") == "NULL_ZERO_TARGET"]
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
        "sample_count": sum(int(row["sample_count"]) for row in worlds),
        "mean_aligned_fractional_rmse_reduction": float(np.mean(aligned)),
        "mean_identity_broken_fractional_rmse_reduction": float(np.mean(broken)),
        "mean_identity_advantage": float(
            np.mean([float(row["identity_advantage"]) for row in scored])
        ),
        "positive_world_count": sum(value > 0.0 for value in aligned),
        "positive_world_fraction": float(np.mean(np.asarray(aligned) > 0.0)),
        "minimum_aligned_fractional_rmse_reduction": min(aligned),
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
            continue
        if path.stat().st_size != row.get("bytes") or _file_sha256(path) != row.get(
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
    if not prior_path.is_file() or prior_path.stat().st_size != prior.get("bytes") or _file_sha256(
        prior_path
    ) != prior.get("sha256"):
        errors.append("promoted prior receipt drift")
    return errors


def _reproduce_slices(
    receipt: Mapping[str, Any], workspace: Path
) -> tuple[list[str], dict[str, Mapping[str, Any]]]:
    errors: list[str] = []
    reproduced_worlds: dict[str, Mapping[str, Any]] = {}
    slices = receipt.get("slices", {})
    with _activated():
        for actor, recorded in slices.items():
            development = [
                _load_world(workspace, root)
                for root in recorded["assigned_development_roots"]
            ]
            holdout = [
                _load_world(workspace, root)
                for root in recorded["assigned_holdout_roots"]
            ]
            max_identities = max(
                len(np.unique(world.tracer_index))
                for world in (*development, *holdout)
            )
            controller = LagrangianRecurrentField(
                LagrangianFieldConfig(
                    present_width=len(PRESENT_ATOMS) * len(legacy.FRAMES) * 3,
                    history_width=len(CHANNELS) * 3,
                    target_width=3,
                    lags=LAGS,
                    max_identities=max_identities,
                )
            )
            state = controller.fit_baseline(
                controller.initial_state(),
                (frame for world in development for frame in _frames(world)),
            )
            if controller.state_sha256(state) != recorded["field"][
                "baseline_state_sha256"
            ]:
                errors.append(f"{actor}: baseline field digest mismatch")
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
                differences = _same_metrics(expected, metrics)
                errors.extend(
                    f"{actor}/{world.bundle.arm_id}: {difference}"
                    for difference in differences
                )
                actor_worlds.append(metrics)
                reproduced_worlds[world.bundle.arm_id] = metrics
            actor_summary = _summary(actor_worlds)
            errors.extend(
                f"{actor}/summary: {difference}"
                for difference in _same_metrics(recorded["summary"], actor_summary)
            )
            expected_scores = _scores(actor_summary, bool(recorded["controls_passed"]))
            for key, value in expected_scores.items():
                if not _close(recorded["lesson_scores"].get(key), value):
                    errors.append(f"{actor}: lesson score mismatch for {key}")
            legacy._load_bundle.cache_clear()
    return errors, reproduced_worlds


def _verify_partitions(receipt: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    development_partition = receipt.get("development_partition", {})
    holdout_partition = receipt.get("unseen_partition", {})
    development = [row for rows in development_partition.values() for row in rows]
    holdout = [row for rows in holdout_partition.values() for row in rows]
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
        digest = receipt.get("aggregate", {}).get("slice_digests", {}).get(actor)
        if digest != _digest(slice_value):
            errors.append(f"slice digest mismatch: {actor}")
    return errors


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
    reviews = assimilation.get("reviews", [])
    supported = 0
    for row in reviews:
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
        supported += int(expected_review == "supports")
    if assimilation.get("support_count") != supported:
        errors.append("Hive support count mismatch")
    promoted = supported >= int(assimilation.get("quorum", 2))
    expected_status = "promoted" if promoted else "contested"
    if assimilation.get("status") != expected_status:
        errors.append("Hive disposition does not follow its quorum")
    organism = ResearchOrganism(Path(str(receipt.get("organism_home"))))
    with organism._open_residencies(include_members=True) as (root, members):
        residents = {"root": root, **members}
        generations = {
            residency.session.status()["common_generation"]
            for residency in residents.values()
        }
        if generations != {assimilation.get("hive_generation")}:
            errors.append("live residents do not share the recorded Hive generation")
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
                errors.append("Hive adoption population is incomplete")
            if assimilation.get("bundle_id") not in bundle_ids:
                errors.append("promoted bundle is absent from collective Hive")
            for resident_id, program in learned.items():
                if program is None or sha256_value(program.as_dict()) != assimilation.get(
                    "program_sha256"
                ):
                    errors.append(f"{resident_id}: adopted program bytes mismatch")
        else:
            if assimilation.get("bundle_id") is not None or assimilation.get("adoptions"):
                errors.append("contested lesson incorrectly produced adoption artifacts")
            if any(program is not None for program in learned.values()):
                errors.append("contested lesson was installed in a resident")
    return errors


def verify(receipt: Mapping[str, Any], *, workspace: Path, reproduce: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    if receipt.get("schema") != SCHEMA:
        errors.append("receipt schema mismatch")
    errors.extend(_verify_sources(receipt, workspace))
    errors.extend(_verify_partitions(receipt))
    reproduced_worlds: dict[str, Mapping[str, Any]] = {}
    if reproduce and not errors:
        reproduction_errors, reproduced_worlds = _reproduce_slices(receipt, workspace)
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
        "reproduced_world_count": len(reproduced_worlds),
        "receipt_sha256": hashlib.sha256(_canonical(receipt)).hexdigest(),
        "bundle_id": receipt.get("hive_assimilation", {}).get("bundle_id"),
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
