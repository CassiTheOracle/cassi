"""Independently reproduce the real generation-two chronological receipt.

This verifier does not import the campaign runner.  It rebuilds the source-bound
trajectory frames, guarded field operations, forecasts, controls, and digests
from the recorded CassiCosmos bundles and compares them with the receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

import cassi_regime_covariant_recurrent_memory as real_loader
from cassi_generation2_isotropic_rollout_field import (
    Generation2GuardedFieldConfig,
    Generation2IsotropicRegimeGuardedField,
)
from cassi_hierarchical_covariant_recurrent_field import (
    CovariantFrame,
    HierarchicalCovariantFieldConfig,
    RegimeCovariantState,
)
from cassi_morphology_operator_invention import _activated


SCHEMA = "cassifi.generation2-real-chronological-holdout-verification.v1"
EXPERIMENT_ID = "generation2-real-chronological-holdout-v1"
RECEIPT = "CassiFI/_diag/generation2-real-chronological-holdout-v1.json"
OUTPUT = "CassiFI/_diag/generation2-real-chronological-holdout-verification-v1.json"
SOURCE_ROOT = "CassiCosmos/_diag/matter_formation"
DEVELOPMENT_ROOT = f"{SOURCE_ROOT}/attractor_ic10"
REGIME_A_ROOT = f"{SOURCE_ROOT}/attractor_ic5"
REGIME_B_ROOT = f"{SOURCE_ROOT}/attractor_ic6"
LAGS = (1, 2, 4, 8)
ANISOTROPY_RIDGE = 8.0
ANISOTROPY_SUPPORT_THRESHOLD = 0.2
MIN_ANISOTROPIC_WORLDS = 2
CHUNK_ONE_FRACTION = 0.60
CHUNK_TWO_FRACTION = 0.85
NONWORSE_TOLERANCE = 1e-12
EXPECTED_SOURCES = tuple(
    sorted(
        set(real_loader.ANALYSIS_SOURCES)
        | {
            "CassiFI/cassi_generation2_isotropic_rollout_field.py",
            "CassiFI/cassi_hierarchical_covariant_recurrent_field.py",
            "CassiFI/run_generation2_real_chronological_holdout.py",
        }
    )
)


class RealHoldoutVerificationError(RuntimeError):
    """Raised when an independent receipt reconstruction differs."""


@dataclass(slots=True)
class RealWorld:
    relative_root: str
    arm_id: str
    frames: tuple[CovariantFrame, ...]
    target_lookup: dict[tuple[int, int], np.ndarray]
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
    for relative in EXPECTED_SOURCES:
        path = workspace / relative
        if not path.is_file():
            raise RealHoldoutVerificationError(f"source is absent: {relative}")
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



def _load_world(workspace: Path, relative_root: str) -> RealWorld:
    with _activated():
        world = real_loader._load_world(workspace, relative_root)
        frames = tuple(real_loader._frames(world))
        target_lookup = real_loader._target_lookup(world)
    if not frames or any(frame.target is None for frame in frames):
        raise RealHoldoutVerificationError(f"invalid frame stream: {relative_root}")
    source_manifest = [dict(row) for row in world.source_manifest]
    source_summary = dict(world.bundle.source_summary)
    source_summary.update(
        {
            "kind": "receipt-backed-cassicosmos-attractor-trajectory",
            "relative_root": relative_root,
            "arm_id": world.bundle.arm_id,
            "frame_count": len(frames),
            "identity_count": len(np.unique(world.tracer_index)),
            "target_rms": float(
                np.sqrt(
                    np.mean(
                        np.asarray(world.bundle.target, dtype=np.float64)
                        * np.asarray(world.bundle.target, dtype=np.float64)
                    )
                )
            ),
            "source_manifest_sha256": _digest(source_manifest),
            "frame_sha256": _frame_digest(frames),
        }
    )
    return RealWorld(
        relative_root=relative_root,
        arm_id=str(world.bundle.arm_id),
        frames=frames,
        target_lookup=target_lookup,
        source_manifest=source_manifest,
        source_summary=source_summary,
    )



def _controller(worlds: Sequence[RealWorld]) -> Generation2IsotropicRegimeGuardedField:
    present_width = len(real_loader.PRESENT_ATOMS) * len(real_loader.legacy.FRAMES) * 3
    max_identities = max(
        len({int(identity) for frame in world.frames for identity in frame.identity_ids})
        for world in worlds
    )
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
        raise RealHoldoutVerificationError("holdout target is exactly zero")
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



def _split(
    world: RealWorld,
) -> tuple[list[CovariantFrame], list[CovariantFrame], list[CovariantFrame]]:
    frames = list(world.frames)
    first_stop = max(16, int(len(frames) * CHUNK_ONE_FRACTION))
    second_stop = max(first_stop + 16, int(len(frames) * CHUNK_TWO_FRACTION))
    if second_stop >= len(frames) - 8:
        second_stop = len(frames) - 9
    return frames[:first_stop], frames[first_stop:second_stop], frames[second_stop:]



def _holdout_metrics(
    controller: Generation2IsotropicRegimeGuardedField,
    state: RegimeCovariantState,
    world: RealWorld,
    holdout: Sequence[CovariantFrame],
) -> dict[str, Any]:
    aligned = controller.forecast_world(state, holdout)
    isotropic = controller.forecast_isotropic(state, holdout)
    broken = controller.forecast_world(state, holdout, break_identity=True)
    target = _targets(world.target_lookup, aligned.ticks, aligned.identity_ids)
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



def _train_regime(
    controller: Generation2IsotropicRegimeGuardedField,
    state: RegimeCovariantState,
    world: RealWorld,
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
            "arm_id": world.arm_id,
            "source_root": world.relative_root,
            "source_summary": world.source_summary,
            "source_manifest": world.source_manifest,
            "regime_id": regime_id,
            "first_chunk_frame_count": len(first_chunk),
            "second_chunk_frame_count": len(second_chunk),
            "holdout_frame_count": len(holdout),
            "training_frame_count": len(first_chunk) + len(second_chunk),
            "chronological_ticks": {
                "first": [first_chunk[0].tick, first_chunk[-1].tick],
                "second": [second_chunk[0].tick, second_chunk[-1].tick],
                "holdout": [holdout[0].tick, holdout[-1].tick],
            },
            "after_first": after_first,
            "after_second": after_second,
            "holdout": metrics,
        },
        state,
    )



def _reproduce_slice(
    workspace: Path,
    analysis_sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    development = _load_world(workspace, DEVELOPMENT_ROOT)
    regime_a_world = _load_world(workspace, REGIME_A_ROOT)
    regime_b_world = _load_world(workspace, REGIME_B_ROOT)
    worlds = (development, regime_a_world, regime_b_world)
    controller = _controller(worlds)
    state = controller.fit_snapshot_baseline(controller.initial_state(), development.frames)
    baseline_state_sha256 = controller.state_sha256(state)
    state = controller.begin_isotropic_rollout(state)
    rollout_state_sha256 = controller.state_sha256(state)
    regime_a, state = _train_regime(controller, state, regime_a_world, regime_label="A")
    regime_b, state = _train_regime(controller, state, regime_b_world, regime_label="B")
    final_inspection = _inspection(controller, state)
    checkpoint = controller.export_state(state)
    restored = controller.import_state(checkpoint)
    restart_exact = controller.state_sha256(restored) == controller.state_sha256(state)
    controls = {
        "real_source_integrity": {
            "status": (
                "PASS"
                if all(
                    world.source_summary["domain_status"] == "BOUNDED"
                    and world.source_summary["target_rms"] > 0.0
                    and len(world.source_manifest) >= 5
                    for world in worlds
                )
                else "FAIL"
            ),
            "development_root": development.relative_root,
            "A_root": regime_a_world.relative_root,
            "B_root": regime_b_world.relative_root,
            "source_manifest_sha256": {
                "development": development.source_summary["source_manifest_sha256"],
                "A": regime_a_world.source_summary["source_manifest_sha256"],
                "B": regime_b_world.source_summary["source_manifest_sha256"],
            },
        },
        "development_regime_disjoint": {
            "status": (
                "PASS"
                if development.relative_root
                not in {regime_a_world.relative_root, regime_b_world.relative_root}
                else "FAIL"
            ),
        },
        "source_regimes_distinct": {
            "status": (
                "PASS"
                if regime_a_world.source_summary["frame_sha256"]
                != regime_b_world.source_summary["frame_sha256"]
                else "FAIL"
            ),
            "A_source_root": regime_a_world.relative_root,
            "B_source_root": regime_b_world.relative_root,
        },
        "A_repeat_isotropic": {
            "status": (
                "PASS"
                if regime_a["holdout"]["guarded_vs_isotropic_max_abs"] == 0.0
                and regime_a["after_first"]["guard_unique_regime_support"] == 1
                and regime_a["after_second"]["guard_unique_regime_support"] == 1
                and regime_a["after_second"]["anisotropic_world_support"] == 1
                else "FAIL"
            ),
            "support_after_first": regime_a["after_first"]["guard_unique_regime_support"],
            "support_after_second": regime_a["after_second"]["guard_unique_regime_support"],
            "forecast_max_abs": regime_a["holdout"]["guarded_vs_isotropic_max_abs"],
        },
        "B_distinct_release": {
            "status": (
                "PASS"
                if regime_b["after_first"]["guard_unique_regime_support"] == 2
                and regime_b["after_second"]["guard_unique_regime_support"] == 2
                and regime_b["after_second"]["anisotropic_world_support"] == 2
                and abs(regime_b["after_first"]["basis_coefficients"][1]) > 1e-6
                else "FAIL"
            ),
            "support_after_first": regime_b["after_first"]["guard_unique_regime_support"],
            "support_after_second": regime_b["after_second"]["guard_unique_regime_support"],
            "basis_after_first": regime_b["after_first"]["basis_coefficients"][1],
            "basis_after_second": regime_b["after_second"]["basis_coefficients"][1],
        },
        "B_repeat_bounded": {
            "status": (
                "PASS"
                if regime_b["after_second"]["guard_unique_regime_support"]
                == regime_b["after_first"]["guard_unique_regime_support"]
                and regime_b["after_second"]["anisotropic_world_support"]
                == regime_b["after_first"]["anisotropic_world_support"]
                else "FAIL"
            ),
        },
        "B_release_prediction_nonworse": {
            "status": (
                "PASS"
                if regime_b["holdout"]["guarded_nrmse"]
                <= regime_b["holdout"]["isotropic_nrmse"] + NONWORSE_TOLERANCE
                else "FAIL"
            ),
            "guarded_nrmse": regime_b["holdout"]["guarded_nrmse"],
            "isotropic_nrmse": regime_b["holdout"]["isotropic_nrmse"],
            "delta": regime_b["holdout"]["guarded_vs_isotropic_delta"],
        },
        "checkpoint_restart": {
            "status": "PASS" if restart_exact else "FAIL",
            "state_exact": restart_exact,
        },
        "field_only_adaptive_owner": {
            "status": (
                "PASS"
                if final_inspection["adaptive_owner"] == "RegimeCovariantState.field"
                else "FAIL"
            ),
            "adaptive_owner": final_inspection["adaptive_owner"],
        },
    }
    return {
        "schema": "cassifi.generation2-real-chronological-holdout-slice.v1",
        "experiment_id": EXPERIMENT_ID,
        "actor": "real-attractor-root",
        "scope": "one independent field over receipt-backed CassiCosmos chronology with A-A-B-B training",
        "analysis_sources": [dict(row) for row in analysis_sources],
        "development_root": development.relative_root,
        "regime_roots": [regime_a_world.relative_root, regime_b_world.relative_root],
        "configuration": {
            "present_width": controller.config.present_width,
            "max_identities": controller.config.max_identities,
            "lags": list(LAGS),
            "correction_ridge": 0.1,
            "anisotropy_ridge": ANISOTROPY_RIDGE,
            "anisotropy_support_threshold": ANISOTROPY_SUPPORT_THRESHOLD,
            "min_anisotropic_worlds": MIN_ANISOTROPIC_WORLDS,
        },
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
        "controls_passed": all(row["status"] == "PASS" for row in controls.values()),
    }



def _assert_equal(expected: Any, actual: Any, path: str = "root") -> None:
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        if set(expected) != set(actual):
            raise RealHoldoutVerificationError(
                f"{path} keys differ: {sorted(set(expected) ^ set(actual))}"
            )
        for key in expected:
            _assert_equal(expected[key], actual[key], f"{path}.{key}")
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            raise RealHoldoutVerificationError(f"{path} lengths differ")
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            _assert_equal(left, right, f"{path}[{index}]")
        return
    if isinstance(expected, float) or isinstance(actual, float):
        if not math.isclose(float(expected), float(actual), rel_tol=2e-12, abs_tol=2e-12):
            raise RealHoldoutVerificationError(
                f"{path} differs: expected {expected!r}, actual {actual!r}"
            )
        return
    if expected != actual:
        raise RealHoldoutVerificationError(
            f"{path} differs: expected {expected!r}, actual {actual!r}"
        )



def run(workspace: Path, receipt_path: Path) -> dict[str, Any]:
    workspace = workspace.resolve(strict=True)
    receipt_path = receipt_path.resolve(strict=True)
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    if receipt.get("schema") != "cassifi.generation2-real-chronological-holdout.v1":
        raise RealHoldoutVerificationError("receipt schema differs")
    if receipt.get("experiment_id") != EXPERIMENT_ID or receipt.get("status") != "PASS":
        raise RealHoldoutVerificationError("receipt identity or status differs")
    expected_sources = _source_manifest(workspace)
    if receipt.get("analysis_sources") != expected_sources:
        raise RealHoldoutVerificationError("analysis source manifest differs")
    if receipt.get("source_partition") != {
        "development": DEVELOPMENT_ROOT,
        "A": REGIME_A_ROOT,
        "B": REGIME_B_ROOT,
    }:
        raise RealHoldoutVerificationError("source partition differs")
    if receipt.get("training_fractions") != {
        "first_chunk": CHUNK_ONE_FRACTION,
        "second_chunk_end": CHUNK_TWO_FRACTION,
        "holdout": 1.0 - CHUNK_TWO_FRACTION,
    }:
        raise RealHoldoutVerificationError("training fractions differ")
    if receipt.get("configuration") != {
        "anisotropy_ridge": ANISOTROPY_RIDGE,
        "anisotropy_support_threshold": ANISOTROPY_SUPPORT_THRESHOLD,
        "min_anisotropic_worlds": MIN_ANISOTROPIC_WORLDS,
        "nonworse_tolerance": NONWORSE_TOLERANCE,
    }:
        raise RealHoldoutVerificationError("protocol configuration differs")
    reproduced_slice = _reproduce_slice(workspace, expected_sources)
    _assert_equal(receipt["slice"], reproduced_slice, "slice")
    reproduced_aggregate = {
        "actor_count": 1,
        "regime_count": 2,
        "sequence": ["A-first", "A-repeat", "B-first", "B-repeat"],
        "A_holdout": {
            "world_count": 1,
            "source_root": reproduced_slice["regime_A"]["source_root"],
            "causal_nrmse": float(reproduced_slice["regime_A"]["holdout"]["causal_nrmse"]),
            "guarded_nrmse": float(reproduced_slice["regime_A"]["holdout"]["guarded_nrmse"]),
            "isotropic_nrmse": float(reproduced_slice["regime_A"]["holdout"]["isotropic_nrmse"]),
            "guarded_vs_isotropic_max_abs": float(
                reproduced_slice["regime_A"]["holdout"]["guarded_vs_isotropic_max_abs"]
            ),
        },
        "B_holdout": {
            "world_count": 1,
            "source_root": reproduced_slice["regime_B"]["source_root"],
            "causal_nrmse": float(reproduced_slice["regime_B"]["holdout"]["causal_nrmse"]),
            "guarded_nrmse": float(reproduced_slice["regime_B"]["holdout"]["guarded_nrmse"]),
            "isotropic_nrmse": float(reproduced_slice["regime_B"]["holdout"]["isotropic_nrmse"]),
            "guarded_vs_isotropic_delta": float(
                reproduced_slice["regime_B"]["holdout"]["guarded_vs_isotropic_delta"]
            ),
            "positive_or_equal": reproduced_slice["regime_B"]["holdout"][
                "guarded_vs_isotropic_delta"
            ]
            <= NONWORSE_TOLERANCE,
            "release_support": int(
                reproduced_slice["regime_B"]["after_second"]["guard_unique_regime_support"]
            ),
            "anisotropic_basis_after_first": float(
                reproduced_slice["regime_B"]["after_first"]["basis_coefficients"][1]
            ),
            "anisotropic_basis_after_second": float(
                reproduced_slice["regime_B"]["after_second"]["basis_coefficients"][1]
            ),
        },
        "controls_passed": bool(reproduced_slice["controls_passed"]),
        "slice_digest": _digest(reproduced_slice),
    }
    _assert_equal(receipt["aggregate"], reproduced_aggregate, "aggregate")
    return {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "status": "VERIFIED",
        "receipt": str(receipt_path),
        "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "source_manifest_verified": True,
        "reconstructed_slice": True,
        "reconstructed_aggregate": True,
        "controls_passed": bool(reproduced_slice["controls_passed"]),
    }



def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--receipt", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    receipt = (args.receipt or workspace / RECEIPT).resolve()
    output = (args.out or workspace / OUTPUT).resolve()
    result = run(workspace, receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical(result) + b"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
