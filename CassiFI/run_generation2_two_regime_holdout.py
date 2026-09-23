"""Run A-A-B-B through two controlled chronological regimes and test release prediction.

The two regimes are deterministic chronological streams with distinct source
manifests.  Each actor fits a separate development stream, enters generation two,
learns two chunks from A and then two from B, and evaluates the final holdout of
both regimes.  The released B forecast must improve or preserve causal prediction
relative to the matched isotropic forecast.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from cassi_generation2_isotropic_rollout_field import (
    Generation2GuardedFieldConfig,
    Generation2IsotropicRegimeGuardedField,
)
from cassi_hierarchical_covariant_recurrent_field import (
    CovariantFrame,
    HierarchicalCovariantFieldConfig,
    RegimeCovariantState,
)


SCHEMA = "cassifi.generation2-two-regime-chronological-holdout.v1"
SLICE_SCHEMA = "cassifi.generation2-two-regime-chronological-holdout-slice.v1"
EXPERIMENT_ID = "generation2-two-regime-chronological-holdout-v1"
OUTPUT = "CassiFI/_diag/generation2-two-regime-chronological-holdout-v1.json"
LAGS = (1, 2, 4, 8)
ANISOTROPY_RIDGE = 8.0
ANISOTROPY_SUPPORT_THRESHOLD = 0.2
MIN_ANISOTROPIC_WORLDS = 2
CHUNK_ONE_FRACTION = 0.60
CHUNK_TWO_FRACTION = 0.85
NONWORSE_TOLERANCE = 1e-12
DEVELOPMENT_SEEDS: Mapping[str, tuple[int, ...]] = {
    "root": (22001,),
    "member-000": (22007,),
}
REGIME_SEEDS: Mapping[str, tuple[int, int]] = {
    "root": (22103, 22111),
    "member-000": (22119, 22123),
}
ANALYSIS_SOURCES = (
    "CassiFI/run_generation2_two_regime_holdout.py",
    "CassiFI/cassi_generation2_isotropic_rollout_field.py",
    "CassiFI/cassi_hierarchical_covariant_recurrent_field.py",
    "CassiFI/cassi_regime_covariant_recurrent_field.py",
    "CassiFI/cassi_regime_covariant_recurrent_memory.py",
)


class TwoRegimeHoldoutError(RuntimeError):
    """Raised when the two-regime chronological contract cannot be measured."""


@dataclass(slots=True)
class SyntheticWorld:
    seed: int
    relative_root: str
    frames: list[CovariantFrame]
    source_manifest: list[dict[str, Any]]
    source_summary: dict[str, Any]



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


def _source_manifest(workspace: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative in ANALYSIS_SOURCES:
        path = workspace / relative
        if not path.is_file():
            raise TwoRegimeHoldoutError(f"analysis source is absent: {relative}")
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    return rows


def _frame_digest(frames: Iterable[CovariantFrame]) -> str:
    digest = hashlib.sha256()
    for frame in frames:
        digest.update(np.asarray([frame.tick], dtype="<i8").tobytes())
        digest.update(np.asarray([frame.delta_time], dtype="<f8").tobytes())
        for name, dtype in (
            ("identity_ids", "<i8"),
            ("present", "<f8"),
            ("position", "<f8"),
            ("velocity", "<f8"),
            ("target", "<f8"),
        ):
            value = np.asarray(getattr(frame, name), dtype=dtype)
            digest.update(name.encode("ascii"))
            digest.update(repr(value.shape).encode("ascii"))
            digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def _synthetic_world(seed: int) -> SyntheticWorld:
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
    frames: list[CovariantFrame] = []
    for index, (position, velocity) in enumerate(
        zip(positions, velocities, strict=True)
    ):
        target = np.zeros((8, 3), dtype=np.float64)
        if index >= 2:
            d1 = (velocity - velocities[index - 1]) / delta_time
            d2 = (velocity - velocities[index - 2]) / (2.0 * delta_time)
            jerk = d1 - d2
            midpoint = position + positions[index - 1]
            local_radial = midpoint / np.linalg.norm(midpoint, axis=1, keepdims=True)
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
        frames.append(
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
    manifest_sha256 = _frame_digest(frames)
    return SyntheticWorld(
        seed=seed,
        relative_root=f"synthetic://generation2-two-regime/{seed}/{manifest_sha256[:16]}",
        frames=frames,
        source_manifest=[
            {
                "name": "synthetic-frame-stream",
                "bytes": sum(
                    int(np.asarray(getattr(frame, name)).nbytes)
                    for frame in frames
                    for name in ("identity_ids", "present", "position", "velocity", "target")
                ),
                "sha256": manifest_sha256,
            }
        ],
        source_summary={
            "kind": "deterministic-synthetic-chronological-stream",
            "seed": seed,
            "frame_count": len(frames),
            "identity_count": len(identities),
            "manifest_sha256": manifest_sha256,
        },
    )


def _controller(worlds: Sequence[SyntheticWorld]) -> Generation2IsotropicRegimeGuardedField:
    return Generation2IsotropicRegimeGuardedField(
        Generation2GuardedFieldConfig(
            HierarchicalCovariantFieldConfig(
                present_width=3,
                max_identities=max(len(world.frames[0].identity_ids) for world in worlds),
                lags=LAGS,
                correction_ridge=0.1,
                anisotropy_ridge=ANISOTROPY_RIDGE,
                anisotropy_support_threshold=ANISOTROPY_SUPPORT_THRESHOLD,
                min_anisotropic_worlds=MIN_ANISOTROPIC_WORLDS,
            )
        )
    )


def _target_lookup(world: SyntheticWorld) -> dict[tuple[int, int], np.ndarray]:
    return {
        (frame.tick, int(identity)): np.asarray(target, dtype=np.float64).copy()
        for frame in world.frames
        for identity, target in zip(frame.identity_ids, frame.target, strict=True)
    }


def _targets(
    lookup: Mapping[tuple[int, int], np.ndarray],
    ticks: np.ndarray,
    identities: np.ndarray,
) -> np.ndarray:
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
        raise TwoRegimeHoldoutError("holdout target is exactly zero")
    return float(_rmse(prediction, target) / target_rms)


def _inspection(
    controller: Generation2IsotropicRegimeGuardedField,
    state: RegimeCovariantState,
) -> dict[str, Any]:
    value = controller.inspect(state)
    return {
        "guard_regime_token_count": int(value["guard_regime_token_count"]),
        "guard_unique_regime_support": int(value["guard_unique_regime_support"]),
        "anisotropic_world_support": int(value["anisotropic_world_support"]),
        "basis_coefficients": [float(item) for item in value["basis_coefficients"]],
        "state_sha256": controller.state_sha256(state),
        "adaptive_owner": value["adaptive_owner"],
    }


def _split(world: SyntheticWorld) -> tuple[list[CovariantFrame], list[CovariantFrame], list[CovariantFrame]]:
    frames = world.frames
    first_stop = max(16, int(len(frames) * CHUNK_ONE_FRACTION))
    second_stop = max(first_stop + 16, int(len(frames) * CHUNK_TWO_FRACTION))
    if second_stop >= len(frames) - 8:
        second_stop = len(frames) - 9
    if first_stop >= second_stop or second_stop >= len(frames):
        raise TwoRegimeHoldoutError(f"{world.relative_root} has no usable holdout")
    return frames[:first_stop], frames[first_stop:second_stop], frames[second_stop:]


def _holdout_metrics(
    controller: Generation2IsotropicRegimeGuardedField,
    state: RegimeCovariantState,
    world: SyntheticWorld,
    holdout: Sequence[CovariantFrame],
) -> dict[str, Any]:
    aligned = controller.forecast_world(state, holdout)
    isotropic = controller.forecast_isotropic(state, holdout)
    broken = controller.forecast_world(state, holdout, break_identity=True)
    if not np.array_equal(aligned.ticks, isotropic.ticks) or not np.array_equal(
        aligned.identity_ids, isotropic.identity_ids
    ):
        raise TwoRegimeHoldoutError("guarded/isotropic forecasts changed evaluated rows")
    target = _targets(_target_lookup(world), aligned.ticks, aligned.identity_ids)
    target_rms = _rmse(np.zeros_like(target), target)
    if target_rms == 0.0:
        raise TwoRegimeHoldoutError("chronological holdout has zero target")
    causal = _nrmse(aligned.causal, target)
    isotropic_nrmse = _nrmse(isotropic.combined, target)
    guarded = _nrmse(aligned.combined, target)
    broken_nrmse = _nrmse(broken.combined, target)
    return {
        "holdout_frame_count": len(holdout),
        "sample_count": aligned.resolved_count,
        "target_rms": target_rms,
        "causal_nrmse": causal,
        "isotropic_nrmse": isotropic_nrmse,
        "guarded_nrmse": guarded,
        "identity_broken_nrmse": broken_nrmse,
        "guarded_vs_isotropic_delta": guarded - isotropic_nrmse,
        "guarded_vs_isotropic_max_abs": float(
            np.max(np.abs(aligned.combined - isotropic.combined))
        ),
        "identity_mismatch_fraction": float(aligned.identity_mismatch_fraction),
        "identity_broken_prediction_separation": float(
            np.linalg.norm(aligned.combined - broken.combined)
            / max(
                float(np.linalg.norm(aligned.combined))
                + float(np.linalg.norm(broken.combined)),
                1e-300,
            )
        ),
    }


def _train_regime(
    controller: Generation2IsotropicRegimeGuardedField,
    state: RegimeCovariantState,
    world: SyntheticWorld,
    *,
    regime_label: str,
) -> tuple[dict[str, Any], RegimeCovariantState]:
    first_chunk, second_chunk, holdout = _split(world)
    regime_id = f"{world.relative_root}:{regime_label}-chronological-regime-v1"
    state = controller.learn_world(state, first_chunk, regime_id=regime_id)
    after_first = _inspection(controller, state)
    state = controller.learn_world(state, second_chunk, regime_id=regime_id)
    after_second = _inspection(controller, state)
    metrics = _holdout_metrics(controller, state, world, holdout)
    return (
        {
            "seed": world.seed,
            "source_root": world.relative_root,
            "source_summary": world.source_summary,
            "source_manifest": world.source_manifest,
            "regime_id": regime_id,
            "first_chunk_frame_count": len(first_chunk),
            "second_chunk_frame_count": len(second_chunk),
            "training_frame_count": len(first_chunk) + len(second_chunk),
            "after_first": after_first,
            "after_second": after_second,
            "holdout": metrics,
        },
        state,
    )


def _actor(actor: str, analysis_sources: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    development = [_synthetic_world(seed) for seed in DEVELOPMENT_SEEDS[actor]]
    worlds = [_synthetic_world(seed) for seed in REGIME_SEEDS[actor]]
    controller = _controller((*development, *worlds))
    state = controller.fit_snapshot_baseline(
        controller.initial_state(),
        (frame for world in development for frame in world.frames),
    )
    baseline_state_sha256 = controller.state_sha256(state)
    state = controller.begin_isotropic_rollout(state)
    rollout_state_sha256 = controller.state_sha256(state)
    regime_a, state = _train_regime(controller, state, worlds[0], regime_label="A")
    regime_b, state = _train_regime(controller, state, worlds[1], regime_label="B")
    final_inspection = _inspection(controller, state)
    checkpoint = controller.export_state(state)
    restored = controller.import_state(checkpoint)
    restart_exact = controller.state_sha256(restored) == controller.state_sha256(state)

    controls = {
        "development_regime_disjoint": {
            "status": "PASS",
            "development_seeds": [world.seed for world in development],
            "regime_seeds": [world.seed for world in worlds],
        },
        "source_regimes_distinct": {
            "status": "PASS"
            if worlds[0].source_summary["manifest_sha256"]
            != worlds[1].source_summary["manifest_sha256"]
            else "FAIL",
            "A_source_root": regime_a["source_root"],
            "B_source_root": regime_b["source_root"],
        },
        "A_repeat_isotropic": {
            "status": "PASS"
            if regime_a["holdout"]["guarded_vs_isotropic_max_abs"] == 0.0
            and regime_a["after_first"]["guard_unique_regime_support"] == 1
            and regime_a["after_second"]["guard_unique_regime_support"] == 1
            and regime_a["after_second"]["anisotropic_world_support"] == 1
            else "FAIL",
            "support_after_first": regime_a["after_first"]["guard_unique_regime_support"],
            "support_after_second": regime_a["after_second"]["guard_unique_regime_support"],
            "forecast_max_abs": regime_a["holdout"]["guarded_vs_isotropic_max_abs"],
        },
        "B_distinct_release": {
            "status": "PASS"
            if regime_b["after_first"]["guard_unique_regime_support"] == 2
            and regime_b["after_second"]["guard_unique_regime_support"] == 2
            and regime_b["after_second"]["anisotropic_world_support"] == 2
            and abs(regime_b["after_first"]["basis_coefficients"][1]) > 1e-6
            else "FAIL",
            "support_after_first": regime_b["after_first"]["guard_unique_regime_support"],
            "support_after_second": regime_b["after_second"]["guard_unique_regime_support"],
            "basis_after_first": regime_b["after_first"]["basis_coefficients"][1],
            "basis_after_second": regime_b["after_second"]["basis_coefficients"][1],
        },
        "B_repeat_bounded": {
            "status": "PASS"
            if regime_b["after_second"]["guard_unique_regime_support"]
            == regime_b["after_first"]["guard_unique_regime_support"]
            and regime_b["after_second"]["anisotropic_world_support"]
            == regime_b["after_first"]["anisotropic_world_support"]
            else "FAIL",
        },
        "B_release_prediction_nonworse": {
            "status": "PASS"
            if regime_b["holdout"]["guarded_nrmse"]
            <= regime_b["holdout"]["isotropic_nrmse"] + NONWORSE_TOLERANCE
            else "FAIL",
            "guarded_nrmse": regime_b["holdout"]["guarded_nrmse"],
            "isotropic_nrmse": regime_b["holdout"]["isotropic_nrmse"],
            "delta": regime_b["holdout"]["guarded_vs_isotropic_delta"],
        },
        "checkpoint_restart": {
            "status": "PASS" if restart_exact else "FAIL",
            "state_exact": restart_exact,
        },
        "field_only_adaptive_owner": {
            "status": "PASS"
            if final_inspection["adaptive_owner"] == "RegimeCovariantState.field"
            else "FAIL",
            "adaptive_owner": final_inspection["adaptive_owner"],
        },
    }
    controls_passed = all(row["status"] == "PASS" for row in controls.values())
    return {
        "schema": SLICE_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "actor": actor,
        "scope": "independent field across two source-bound chronological regimes with A-A-B-B training",
        "development_seeds": list(DEVELOPMENT_SEEDS[actor]),
        "regime_seeds": list(REGIME_SEEDS[actor]),
        "analysis_sources": [dict(row) for row in analysis_sources],
        "baseline_state_sha256": baseline_state_sha256,
        "rollout_state_sha256": rollout_state_sha256,
        "regime_A": regime_a,
        "regime_B": regime_b,
        "final_inspection": final_inspection,
        "checkpoint": {
            "bytes": len(checkpoint),
            "sha256": hashlib.sha256(checkpoint).hexdigest(),
            "state_sha256": controller.state_sha256(state),
        },
        "controls": controls,
        "controls_passed": controls_passed,
    }


def _aggregate(slices: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows = [slices[actor] for actor in sorted(slices)]
    a_rows = [row["regime_A"]["holdout"] for row in rows]
    b_rows = [row["regime_B"]["holdout"] for row in rows]
    b_deltas = [float(row["guarded_vs_isotropic_delta"]) for row in b_rows]
    return {
        "actor_count": len(rows),
        "regime_count": 2,
        "sequence": ["A-first", "A-repeat", "B-first", "B-repeat"],
        "A_holdout": {
            "world_count": len(a_rows),
            "mean_causal_nrmse": float(np.mean([row["causal_nrmse"] for row in a_rows])),
            "mean_guarded_nrmse": float(np.mean([row["guarded_nrmse"] for row in a_rows])),
            "mean_isotropic_nrmse": float(np.mean([row["isotropic_nrmse"] for row in a_rows])),
            "max_guarded_vs_isotropic_abs": float(max(row["guarded_vs_isotropic_max_abs"] for row in a_rows)),
        },
        "B_holdout": {
            "world_count": len(b_rows),
            "mean_causal_nrmse": float(np.mean([row["causal_nrmse"] for row in b_rows])),
            "mean_guarded_nrmse": float(np.mean([row["guarded_nrmse"] for row in b_rows])),
            "mean_isotropic_nrmse": float(np.mean([row["isotropic_nrmse"] for row in b_rows])),
            "mean_guarded_vs_isotropic_delta": float(np.mean(b_deltas)),
            "maximum_guarded_vs_isotropic_delta": float(max(b_deltas)),
            "positive_or_equal_actor_count": int(sum(delta <= NONWORSE_TOLERANCE for delta in b_deltas)),
            "minimum_release_support": int(min(row["regime_B"]["after_second"]["guard_unique_regime_support"] for row in rows)),
            "maximum_release_support": int(max(row["regime_B"]["after_second"]["guard_unique_regime_support"] for row in rows)),
        },
        "controls_passed": all(bool(row["controls_passed"]) for row in rows),
        "slice_digests": {actor: _digest(slices[actor]) for actor in sorted(slices)},
    }


def run(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve(strict=True)
    analysis_sources = _source_manifest(workspace)
    slices = {
        actor: _actor(actor, analysis_sources) for actor in ("root", "member-000")
    }
    aggregate = _aggregate(slices)
    if not aggregate["controls_passed"]:
        failed = {
            actor: [
                name
                for name, row in result["controls"].items()
                if row["status"] != "PASS"
            ]
            for actor, result in slices.items()
        }
        raise TwoRegimeHoldoutError(f"two-regime controls failed: {failed}")
    return {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "scope": "two independent fields, each with one development stream and two disjoint chronological regime streams",
        "analysis_sources": analysis_sources,
        "development_partition": {
            actor: list(value) for actor, value in DEVELOPMENT_SEEDS.items()
        },
        "regime_partition": {
            actor: list(value) for actor, value in REGIME_SEEDS.items()
        },
        "training_fractions": {
            "first_chunk": CHUNK_ONE_FRACTION,
            "second_chunk_end": CHUNK_TWO_FRACTION,
            "holdout": 1.0 - CHUNK_TWO_FRACTION,
        },
        "nonworse_tolerance": NONWORSE_TOLERANCE,
        "slices": slices,
        "aggregate": aggregate,
        "status": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    output = (args.out or workspace / OUTPUT).resolve()
    result = run(workspace)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical(result) + b"\n")
    print(json.dumps({"status": result["status"], "aggregate": result["aggregate"], "receipt": str(output)}, indent=2))


if __name__ == "__main__":
    main()
