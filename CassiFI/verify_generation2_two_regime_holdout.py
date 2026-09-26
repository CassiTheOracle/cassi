"""Independently reproduce the two-regime chronological holdout receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
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


SCHEMA = "cassifi.generation2-two-regime-chronological-holdout-verification.v1"
EXPERIMENT_ID = "generation2-two-regime-chronological-holdout-v1"
RECEIPT = "CassiFI/_diag/generation2-two-regime-chronological-holdout-v1.json"
OUTPUT = "CassiFI/_diag/generation2-two-regime-chronological-holdout-verification-v1.json"
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
EXPECTED_SOURCES = (
    "CassiFI/run_generation2_two_regime_holdout.py",
    "CassiFI/cassi_generation2_isotropic_rollout_field.py",
    "CassiFI/cassi_hierarchical_covariant_recurrent_field.py",
    "CassiFI/cassi_regime_covariant_recurrent_field.py",
    "CassiFI/cassi_regime_covariant_recurrent_memory.py",
)


class TwoRegimeVerificationError(RuntimeError):
    """Raised when an independent reconstruction differs from the receipt."""


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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    ticks: np.ndarray, identities: np.ndarray
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
        raise TwoRegimeVerificationError("holdout target is exactly zero")
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
    first_stop = max(16, int(len(world.frames) * CHUNK_ONE_FRACTION))
    second_stop = max(first_stop + 16, int(len(world.frames) * CHUNK_TWO_FRACTION))
    if second_stop >= len(world.frames) - 8:
        second_stop = len(world.frames) - 9
    return world.frames[:first_stop], world.frames[first_stop:second_stop], world.frames[second_stop:]


def _holdout_metrics(
    controller: Generation2IsotropicRegimeGuardedField,
    state: RegimeCovariantState,
    world: SyntheticWorld,
    holdout: Sequence[CovariantFrame],
) -> dict[str, Any]:
    aligned = controller.forecast_world(state, holdout)
    isotropic = controller.forecast_isotropic(state, holdout)
    broken = controller.forecast_world(state, holdout, break_identity=True)
    target = _targets(_target_lookup(world), aligned.ticks, aligned.identity_ids)
    causal = _nrmse(aligned.causal, target)
    isotropic_nrmse = _nrmse(isotropic.combined, target)
    guarded = _nrmse(aligned.combined, target)
    broken_nrmse = _nrmse(broken.combined, target)
    return {
        "holdout_frame_count": len(holdout),
        "sample_count": aligned.resolved_count,
        "target_rms": _rmse(np.zeros_like(target), target),
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


def _assert_close(expected: float, actual: float, label: str) -> None:
    if not math.isclose(expected, actual, rel_tol=2e-12, abs_tol=2e-14):
        raise TwoRegimeVerificationError(
            f"{label} differs: expected {expected!r}, actual {actual!r}"
        )


def _assert_stage(expected: Mapping[str, Any], actual: Mapping[str, Any], label: str) -> None:
    for key in (
        "guard_regime_token_count",
        "guard_unique_regime_support",
        "anisotropic_world_support",
        "state_sha256",
        "adaptive_owner",
    ):
        if expected[key] != actual[key]:
            raise TwoRegimeVerificationError(
                f"{label}.{key} differs: expected {expected[key]!r}, actual {actual[key]!r}"
            )
    for index, (left, right) in enumerate(
        zip(expected["basis_coefficients"], actual["basis_coefficients"], strict=True)
    ):
        _assert_close(float(left), float(right), f"{label}.basis_coefficients[{index}]")


def _assert_holdout(expected: Mapping[str, Any], actual: Mapping[str, Any], label: str) -> None:
    for key in (
        "holdout_frame_count",
        "sample_count",
        "identity_mismatch_fraction",
    ):
        if expected[key] != actual[key]:
            raise TwoRegimeVerificationError(
                f"{label}.{key} differs: expected {expected[key]!r}, actual {actual[key]!r}"
            )
    for key in (
        "target_rms",
        "causal_nrmse",
        "isotropic_nrmse",
        "guarded_nrmse",
        "identity_broken_nrmse",
        "guarded_vs_isotropic_delta",
        "guarded_vs_isotropic_max_abs",
        "identity_broken_prediction_separation",
    ):
        _assert_close(float(expected[key]), float(actual[key]), f"{label}.{key}")


def _verify_sources(workspace: Path, receipt: Mapping[str, Any]) -> None:
    rows = receipt.get("analysis_sources")
    if not isinstance(rows, list) or [row.get("path") for row in rows] != list(EXPECTED_SOURCES):
        raise TwoRegimeVerificationError("analysis source paths differ")
    for row in rows:
        path = workspace / str(row["path"])
        if not path.is_file():
            raise TwoRegimeVerificationError(f"analysis source is absent: {path}")
        if int(row["bytes"]) != path.stat().st_size:
            raise TwoRegimeVerificationError(f"analysis source byte count differs: {path}")
        if str(row["sha256"]) != _file_sha256(path):
            raise TwoRegimeVerificationError(f"analysis source digest differs: {path}")


def _reproduce_actor(actor: str, recorded: Mapping[str, Any]) -> dict[str, Any]:
    development = [_synthetic_world(seed) for seed in DEVELOPMENT_SEEDS[actor]]
    worlds = [_synthetic_world(seed) for seed in REGIME_SEEDS[actor]]
    if recorded["development_seeds"] != list(DEVELOPMENT_SEEDS[actor]):
        raise TwoRegimeVerificationError(f"{actor} development seeds differ")
    if recorded["regime_seeds"] != list(REGIME_SEEDS[actor]):
        raise TwoRegimeVerificationError(f"{actor} regime seeds differ")
    controller = _controller((*development, *worlds))
    state = controller.fit_snapshot_baseline(
        controller.initial_state(),
        (frame for world in development for frame in world.frames),
    )
    if controller.state_sha256(state) != recorded["baseline_state_sha256"]:
        raise TwoRegimeVerificationError(f"{actor} baseline state differs")
    state = controller.begin_isotropic_rollout(state)
    if controller.state_sha256(state) != recorded["rollout_state_sha256"]:
        raise TwoRegimeVerificationError(f"{actor} rollout state differs")

    reproduced: dict[str, dict[str, Any]] = {}
    for label, world in zip(("A", "B"), worlds, strict=True):
        first, second, holdout = _split(world)
        regime_id = f"{world.relative_root}:{label}-chronological-regime-v1"
        state = controller.learn_world(state, first, regime_id=regime_id)
        after_first = _inspection(controller, state)
        state = controller.learn_world(state, second, regime_id=regime_id)
        after_second = _inspection(controller, state)
        metrics = _holdout_metrics(controller, state, world, holdout)
        reproduced[f"regime_{label}"] = {
            "seed": world.seed,
            "source_root": world.relative_root,
            "source_summary": world.source_summary,
            "source_manifest": world.source_manifest,
            "regime_id": regime_id,
            "first_chunk_frame_count": len(first),
            "second_chunk_frame_count": len(second),
            "training_frame_count": len(first) + len(second),
            "after_first": after_first,
            "after_second": after_second,
            "holdout": metrics,
        }
    final_inspection = _inspection(controller, state)
    checkpoint = controller.export_state(state)
    restored = controller.import_state(checkpoint)
    reproduced["final_inspection"] = final_inspection
    reproduced["checkpoint"] = {
        "bytes": len(checkpoint),
        "sha256": hashlib.sha256(checkpoint).hexdigest(),
        "state_sha256": controller.state_sha256(state),
    }
    if controller.state_sha256(restored) != reproduced["checkpoint"]["state_sha256"]:
        raise TwoRegimeVerificationError(f"{actor} checkpoint restart differs")
    for label in ("regime_A", "regime_B"):
        expected = recorded[label]
        actual = reproduced[label]
        for key in ("seed", "source_root", "regime_id", "first_chunk_frame_count", "second_chunk_frame_count", "training_frame_count"):
            if expected[key] != actual[key]:
                raise TwoRegimeVerificationError(f"{actor}.{label}.{key} differs")
        if expected["source_summary"] != actual["source_summary"] or expected["source_manifest"] != actual["source_manifest"]:
            raise TwoRegimeVerificationError(f"{actor}.{label} source evidence differs")
        _assert_stage(expected["after_first"], actual["after_first"], f"{actor}.{label}.after_first")
        _assert_stage(expected["after_second"], actual["after_second"], f"{actor}.{label}.after_second")
        _assert_holdout(expected["holdout"], actual["holdout"], f"{actor}.{label}.holdout")
    if recorded["final_inspection"] != reproduced["final_inspection"]:
        raise TwoRegimeVerificationError(f"{actor} final inspection differs")
    if recorded["checkpoint"] != reproduced["checkpoint"]:
        raise TwoRegimeVerificationError(f"{actor} checkpoint evidence differs")
    controls = _controls_from_reproduction(
        actor=actor,
        development_seeds=list(DEVELOPMENT_SEEDS[actor]),
        regime_seeds=list(REGIME_SEEDS[actor]),
        reproduced=reproduced,
        restart_exact=controller.state_sha256(restored)
        == reproduced["checkpoint"]["state_sha256"],
    )
    if recorded["controls"] != controls:
        raise TwoRegimeVerificationError(f"{actor} recorded controls differ")
    if not recorded["controls_passed"] or not all(
        row["status"] == "PASS" for row in controls.values()
    ):
        raise TwoRegimeVerificationError(f"{actor} controls are not all PASS")
    reproduced["controls"] = controls
    reproduced["controls_passed"] = True
    return reproduced


def _controls_from_reproduction(
    *,
    actor: str,
    development_seeds: list[int],
    regime_seeds: list[int],
    reproduced: Mapping[str, Any],
    restart_exact: bool,
) -> dict[str, Any]:
    del actor
    a = reproduced["regime_A"]
    b = reproduced["regime_B"]
    return {
        "development_regime_disjoint": {
            "status": "PASS"
            if not (set(development_seeds) & set(regime_seeds))
            else "FAIL",
            "development_seeds": development_seeds,
            "regime_seeds": regime_seeds,
        },
        "source_regimes_distinct": {
            "status": "PASS"
            if a["source_summary"]["manifest_sha256"]
            != b["source_summary"]["manifest_sha256"]
            else "FAIL",
            "A_source_root": a["source_root"],
            "B_source_root": b["source_root"],
        },
        "A_repeat_isotropic": {
            "status": "PASS"
            if a["holdout"]["guarded_vs_isotropic_max_abs"] == 0.0
            and a["after_first"]["guard_unique_regime_support"] == 1
            and a["after_second"]["guard_unique_regime_support"] == 1
            and a["after_second"]["anisotropic_world_support"] == 1
            else "FAIL",
            "support_after_first": a["after_first"]["guard_unique_regime_support"],
            "support_after_second": a["after_second"]["guard_unique_regime_support"],
            "forecast_max_abs": a["holdout"]["guarded_vs_isotropic_max_abs"],
        },
        "B_distinct_release": {
            "status": "PASS"
            if b["after_first"]["guard_unique_regime_support"] == 2
            and b["after_second"]["guard_unique_regime_support"] == 2
            and b["after_second"]["anisotropic_world_support"] == 2
            and abs(b["after_first"]["basis_coefficients"][1]) > 1e-6
            else "FAIL",
            "support_after_first": b["after_first"]["guard_unique_regime_support"],
            "support_after_second": b["after_second"]["guard_unique_regime_support"],
            "basis_after_first": b["after_first"]["basis_coefficients"][1],
            "basis_after_second": b["after_second"]["basis_coefficients"][1],
        },
        "B_repeat_bounded": {
            "status": "PASS"
            if b["after_second"]["guard_unique_regime_support"]
            == b["after_first"]["guard_unique_regime_support"]
            and b["after_second"]["anisotropic_world_support"]
            == b["after_first"]["anisotropic_world_support"]
            else "FAIL",
        },
        "B_release_prediction_nonworse": {
            "status": "PASS"
            if b["holdout"]["guarded_nrmse"]
            <= b["holdout"]["isotropic_nrmse"] + NONWORSE_TOLERANCE
            else "FAIL",
            "guarded_nrmse": b["holdout"]["guarded_nrmse"],
            "isotropic_nrmse": b["holdout"]["isotropic_nrmse"],
            "delta": b["holdout"]["guarded_vs_isotropic_delta"],
        },
        "checkpoint_restart": {
            "status": "PASS" if restart_exact else "FAIL",
            "state_exact": restart_exact,
        },
        "field_only_adaptive_owner": {
            "status": "PASS"
            if reproduced["final_inspection"]["adaptive_owner"]
            == "RegimeCovariantState.field"
            else "FAIL",
            "adaptive_owner": reproduced["final_inspection"]["adaptive_owner"],
        },
    }
    return reproduced


def verify(workspace: Path, receipt_path: Path) -> dict[str, Any]:
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    if receipt.get("schema") != "cassifi.generation2-two-regime-chronological-holdout.v1":
        raise TwoRegimeVerificationError("receipt schema differs")
    if receipt.get("experiment_id") != EXPERIMENT_ID or receipt.get("status") != "PASS":
        raise TwoRegimeVerificationError("receipt identity or status differs")
    if receipt.get("training_fractions") != {
        "first_chunk": CHUNK_ONE_FRACTION,
        "second_chunk_end": CHUNK_TWO_FRACTION,
        "holdout": 1.0 - CHUNK_TWO_FRACTION,
    }:
        raise TwoRegimeVerificationError("training fractions differ")
    if float(receipt.get("nonworse_tolerance")) != NONWORSE_TOLERANCE:
        raise TwoRegimeVerificationError("non-worse tolerance differs")
    _verify_sources(workspace, receipt)
    if receipt.get("development_partition") != {
        actor: list(seeds) for actor, seeds in DEVELOPMENT_SEEDS.items()
    } or receipt.get("regime_partition") != {
        actor: list(seeds) for actor, seeds in REGIME_SEEDS.items()
    }:
        raise TwoRegimeVerificationError("source seed partitions differ")

    slices = receipt.get("slices")
    if not isinstance(slices, dict) or set(slices) != set(DEVELOPMENT_SEEDS):
        raise TwoRegimeVerificationError("actor set differs")
    reproduced = {
        actor: _reproduce_actor(actor, slices[actor]) for actor in sorted(slices)
    }

    a_rows = [reproduced[actor]["regime_A"]["holdout"] for actor in sorted(reproduced)]
    b_rows = [reproduced[actor]["regime_B"]["holdout"] for actor in sorted(reproduced)]
    b_deltas = [float(row["guarded_vs_isotropic_delta"]) for row in b_rows]
    expected_aggregate = {
        "actor_count": len(reproduced),
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
            "minimum_release_support": 2,
            "maximum_release_support": 2,
        },
        "controls_passed": True,
        "slice_digests": {
            actor: hashlib.sha256(_canonical(receipt["slices"][actor])).hexdigest()
            for actor in sorted(reproduced)
        },
    }
    recorded_aggregate = receipt["aggregate"]
    if recorded_aggregate["actor_count"] != expected_aggregate["actor_count"] or recorded_aggregate["sequence"] != expected_aggregate["sequence"]:
        raise TwoRegimeVerificationError("aggregate identity differs")
    for section in ("A_holdout", "B_holdout"):
        for key, actual in expected_aggregate[section].items():
            expected = recorded_aggregate[section][key]
            if isinstance(actual, float):
                _assert_close(float(expected), actual, f"aggregate.{section}.{key}")
            elif expected != actual:
                raise TwoRegimeVerificationError(f"aggregate.{section}.{key} differs")
    if recorded_aggregate["slice_digests"] != expected_aggregate["slice_digests"]:
        raise TwoRegimeVerificationError("aggregate slice digests differ")
    return {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "status": "PASS",
        "receipt": str(receipt_path),
        "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "source_manifest_verified": True,
        "actor_count": len(reproduced),
        "sequence": ["A-first", "A-repeat", "B-first", "B-repeat"],
        "release_holdout": {
            "mean_guarded_vs_isotropic_delta": expected_aggregate["B_holdout"]["mean_guarded_vs_isotropic_delta"],
            "maximum_guarded_vs_isotropic_delta": expected_aggregate["B_holdout"]["maximum_guarded_vs_isotropic_delta"],
            "positive_or_equal_actor_count": expected_aggregate["B_holdout"]["positive_or_equal_actor_count"],
        },
        "recomputed_slice_digests": expected_aggregate["slice_digests"],
    }




def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--receipt", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    receipt = (args.receipt or workspace / RECEIPT).resolve()
    output = (args.out or workspace / OUTPUT).resolve()
    result = verify(workspace, receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical(result) + b"\n")
    print(json.dumps({"status": result["status"], "verification": str(output)}, indent=2))


if __name__ == "__main__":
    main()
