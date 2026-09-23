"""Independently reproduce and verify the generation-two guarded rollout.

This verifier does not import the campaign runner.  It reads the persisted
receipt, rebuilds every actor's field from the recorded disjoint worlds, checks
the repeated-regime support transition and checkpoint bytes, compares measured
values, and validates the promoted live-Hive object by content digest.
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


SCHEMA = "cassifi.hive-generation2-isotropic-regime-guarded-rollout.v1"
SLICE_SCHEMA = "cassifi.hive-generation2-isotropic-regime-guarded-rollout-slice.v1"
EXPERIMENT_ID = "generation2-isotropic-regime-guarded-rollout-v1"
PRIOR_RECEIPT = "CassiFI/_diag/hierarchical-covariant-recurrent-memory-v3.json"
PRIOR_RECEIPT_SHA256 = "5fe5667654e47e89adb0fb2c0a20208a5e2c69eea0dd95d0f799d0dd010794e0"
PROMOTED_BUNDLE_ID = "6ac75f1f9d1acef00ce9eafbd0756f3e23e5225cda053a7c265e3fb843ee1b42"
LAGS = (1, 2, 4, 8)
PRESENT_ATOMS = tuple(SEED_ATOMS)
ANISOTROPY_RIDGE = 8.0
ANISOTROPY_SUPPORT_THRESHOLD = 0.2
MIN_ANISOTROPIC_WORLDS = 2
CHUNK_ONE_FRACTION = 0.60
CHUNK_TWO_FRACTION = 0.85
BUNDLE_SCHEMA = "cassifi.hive.bundle.v1"


class Generation2VerificationError(RuntimeError):
    """Raised when a persisted generation-two claim cannot be reproduced."""


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


def _same(expected: Any, actual: Any, path: str = "") -> list[str]:
    errors: list[str] = []
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        if set(expected) != set(actual):
            return [f"{path}: key sets differ"]
        for key in expected:
            errors.extend(_same(expected[key], actual[key], f"{path}.{key}"))
        return errors
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{path}: list lengths differ"]
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            errors.extend(_same(left, right, f"{path}[{index}]"))
        return errors
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not _close(expected, actual):
            errors.append(f"{path}: {expected!r} != {actual!r}")
        return errors
    if expected != actual:
        errors.append(f"{path}: {expected!r} != {actual!r}")
    return errors


def _load_world(workspace: Path, relative_root: str) -> Any:
    return v2._load_world(workspace, relative_root)


def _frames(world: Any) -> list[Any]:
    return list(v2._frames(world))


def _target_lookup(world: Any) -> dict[tuple[int, int], np.ndarray]:
    return v2._target_lookup(world)


def _targets(
    lookup: Mapping[tuple[int, int], np.ndarray],
    ticks: np.ndarray, identities: np.ndarray
) -> np.ndarray:
    return v2._targets(lookup, ticks, identities)


def _rmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return v2._rmse(prediction, target)


def _nrmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return v2._nrmse(prediction, target)


def _controller(worlds: Sequence[Any]) -> Generation2IsotropicRegimeGuardedField:
    present_width = len(PRESENT_ATOMS) * len(legacy.FRAMES) * 3
    max_identities = max(int(len(np.unique(world.tracer_index))) for world in worlds)
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
    guarded_state = guarded.learn_world(guarded_state, world, regime_id="one-chronological-regime")
    support_first = guarded.inspect(guarded_state)["guard_unique_regime_support"]
    guarded_state = guarded.learn_world(guarded_state, world, regime_id="one-chronological-regime")
    guarded_inspection = guarded.inspect(guarded_state)
    bare_state = bare.learn_world(bare_state, world)
    bare_state = bare.learn_world(bare_state, world)
    bare_inspection = bare.inspect(bare_state)
    aligned = guarded.forecast_world(guarded_state, world)
    isotropic = guarded.forecast_isotropic(guarded_state, world)
    guarded_blocked = (
        support_first == 1
        and guarded_inspection["guard_unique_regime_support"] == 1
        and guarded_inspection["anisotropic_world_support"] == 1
        and np.array_equal(aligned.combined, isotropic.combined)
    )
    bare_fired = (
        bare_inspection["anisotropic_world_support"] == 2
        and abs(float(bare_inspection["basis_coefficients"][1])) > 1e-6
    )
    return {
        "status": "PASS" if guarded_blocked and bare_fired else "FAIL",
        "guarded_support_after_first_chunk": support_first,
        "guarded_support_after_second_chunk": guarded_inspection[
            "guard_unique_regime_support"
        ],
        "guarded_anisotropic_world_support": guarded_inspection[
            "anisotropic_world_support"
        ],
        "unguarded_anisotropic_world_support": bare_inspection[
            "anisotropic_world_support"
        ],
        "guarded_reentry_blocked": guarded_blocked,
        "unguarded_release_fired": bare_fired,
    }


def _reproduce_actor(
    workspace: Path,
    development_roots: Sequence[str],
    fresh_root: str,
) -> dict[str, Any]:
    development = [_load_world(workspace, root) for root in development_roots]
    fresh = _load_world(workspace, fresh_root)
    controller = _controller((*development, fresh))
    state = controller.fit_snapshot_baseline(
        controller.initial_state(),
        (frame for world in development for frame in _frames(world)),
    )
    baseline_state_sha256 = controller.state_sha256(state)
    state = controller.begin_isotropic_rollout(state)
    frames = _frames(fresh)
    first_stop = max(16, int(len(frames) * CHUNK_ONE_FRACTION))
    second_stop = max(first_stop + 16, int(len(frames) * CHUNK_TWO_FRACTION))
    if second_stop >= len(frames) - 8:
        second_stop = len(frames) - 9
    regime_id = f"{fresh.relative_root}:chronological-regime-v1"
    state = controller.learn_world(state, frames[:first_stop], regime_id=regime_id)
    after_first = controller.inspect(state)
    state = controller.learn_world(state, frames[first_stop:second_stop], regime_id=regime_id)
    after_second = controller.inspect(state)
    trained_state_sha256 = controller.state_sha256(state)
    holdout = frames[second_stop:]
    aligned = controller.forecast_world(state, holdout)
    isotropic = controller.forecast_isotropic(state, holdout)
    broken = controller.forecast_world(state, holdout, break_identity=True)
    target = _targets(_target_lookup(fresh), aligned.ticks, aligned.identity_ids)
    target_rms = _rmse(np.zeros_like(target), target)
    if target_rms == 0.0:
        raise Generation2VerificationError(f"fresh holdout target is zero: {fresh_root}")
    causal = _nrmse(aligned.causal, target)
    iso = _nrmse(isotropic.combined, target)
    guarded = _nrmse(aligned.combined, target)
    broken_nrmse = _nrmse(broken.combined, target)
    checkpoint = controller.export_state(state)
    restarted = controller.import_state(checkpoint)
    restart_forecast = controller.forecast_world(restarted, holdout)
    state_before = controller.state_sha256(state)
    controller.forecast_world(state, holdout)
    controller.forecast_isotropic(state, holdout)
    forecast_immutable = controller.state_sha256(state) == state_before
    controls = {
        "same_regime_support_unchanged": (
            after_first["guard_unique_regime_support"]
            == after_second["guard_unique_regime_support"]
            and after_second["guard_unique_regime_support"] <= 1
            and after_second["anisotropic_world_support"] <= 1
        ),
        "guarded_forecast_isotropic_exact": np.array_equal(
            aligned.combined, isotropic.combined
        ),
        "checkpoint_restart": (
            controller.state_sha256(restarted) == trained_state_sha256
            and np.array_equal(aligned.combined, restart_forecast.combined)
        ),
        "forecast_immutability": forecast_immutable,
        "identity_break_fired": (
            broken.identity_mismatch_fraction >= 0.99
            and not np.array_equal(aligned.combined, broken.combined)
        ),
        "field_only_adaptive_owner": after_second["adaptive_owner"]
        == "RegimeCovariantState.field",
    }
    return {
        "source_root": fresh.relative_root,
        "arm_id": fresh.bundle.arm_id,
        "source_manifest": fresh.source_manifest,
        "regime_id": regime_id,
        "regime_token_count": after_second["guard_regime_token_count"],
        "training_frame_count": first_stop + (second_stop - first_stop),
        "first_chunk_frame_count": first_stop,
        "second_chunk_frame_count": second_stop - first_stop,
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
        "baseline_state_sha256": baseline_state_sha256,
        "trained_state_sha256": trained_state_sha256,
        "checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
        "inspection": after_second,
        "controls": controls,
    }


def _extract_bundle_candidate(value: Any, candidates: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {"lesson_id", "candidate_id"} and isinstance(child, str):
                if child in candidates:
                    found.add(child)
            found.update(_extract_bundle_candidate(child, candidates))
    elif isinstance(value, list):
        for child in value:
            found.update(_extract_bundle_candidate(child, candidates))
    return found


def _verify_live_bundle(receipt: Mapping[str, Any], prior: Mapping[str, Any]) -> dict[str, Any]:
    assimilation = receipt.get("hive_assimilation", {})
    bundle_id = assimilation.get("bundle_id")
    if not isinstance(bundle_id, str) or not bundle_id:
        raise Generation2VerificationError("receipt has no promoted bundle id")
    if bundle_id == PROMOTED_BUNDLE_ID:
        raise Generation2VerificationError("generation two did not advance the Hive bundle")
    home = Path(str(receipt["collective_hive_home"]))
    path = home / "objects" / bundle_id
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Generation2VerificationError("promoted bundle object is unreadable") from exc
    if bundle.get("schema") != BUNDLE_SCHEMA or bundle.get("object_id") != bundle_id:
        raise Generation2VerificationError("promoted bundle schema or object id differs")
    content_digest = hashlib.sha256(
        _canonical({"schema": BUNDLE_SCHEMA, "content": bundle.get("content")})
    ).hexdigest()
    if bundle.get("content_sha256") != content_digest or content_digest != bundle_id:
        raise Generation2VerificationError("promoted bundle content digest differs")
    candidates = {
        "generation2-isotropic-regime-guard",
        "isotropic-covariant-trajectory-transfer",
    }
    found = _extract_bundle_candidate(bundle, candidates)
    if not found:
        raise Generation2VerificationError("promoted bundle does not carry the guarded lesson")
    adoptions = assimilation.get("adoptions", {})
    expected_residents = {"root", "member-000", "member-001"}
    if not isinstance(adoptions, Mapping) or set(adoptions) != expected_residents:
        raise Generation2VerificationError("Hive adoption population is incomplete")
    program_sha256 = assimilation.get("program_sha256")
    adoption_programs: dict[str, str] = {}
    for actor, row in adoptions.items():
        if not isinstance(row, Mapping):
            raise Generation2VerificationError(f"{actor}: adoption row is malformed")
        if row.get("program_sha256") != program_sha256:
            raise Generation2VerificationError(f"{actor}: adopted program bytes differ")
        sync = row.get("sync", {})
        if not isinstance(sync, Mapping) or sync.get("errors"):
            raise Generation2VerificationError(f"{actor}: Hive sync reported errors")
        adoption_programs[str(actor)] = str(row["program_sha256"])
    if not program_sha256:
        raise Generation2VerificationError("Hive program digest is absent")
    return {
        "bundle_id": bundle_id,
        "object_sha256": _file_sha256(path),
        "content_sha256": content_digest,
        "carried_lesson_ids": sorted(found),
        "adoption_program_sha256": adoption_programs,
        "hive_generation": assimilation.get("hive_generation"),
        "prior_hive_generation": prior.get("hive_generation"),
    }


def verify(workspace: Path, receipt_path: Path) -> dict[str, Any]:
    workspace = Path(workspace).resolve(strict=True)
    receipt_path = Path(receipt_path).resolve(strict=True)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Generation2VerificationError("generation-two receipt is unreadable") from exc
    if receipt.get("schema") != SCHEMA or receipt.get("experiment_id") != EXPERIMENT_ID:
        raise Generation2VerificationError("generation-two receipt identity differs")
    prior_path = workspace / PRIOR_RECEIPT
    prior_raw = prior_path.read_bytes()
    prior = receipt.get("prior_promotion", {})
    if hashlib.sha256(prior_raw).hexdigest() != PRIOR_RECEIPT_SHA256:
        raise Generation2VerificationError("bound V3 receipt changed")
    if prior.get("sha256") != PRIOR_RECEIPT_SHA256 or prior.get("bundle_id") != PROMOTED_BUNDLE_ID:
        raise Generation2VerificationError("receipt prior promotion binding differs")
    source_errors: list[str] = []
    for row in receipt.get("analysis_sources", []):
        path = workspace / str(row["path"])
        if not path.is_file():
            source_errors.append(f"missing source: {path}")
            continue
        if path.stat().st_size != int(row["bytes"]):
            source_errors.append(f"source bytes drift: {path}")
        if _file_sha256(path) != row["sha256"]:
            source_errors.append(f"source digest drift: {path}")
    if source_errors:
        raise Generation2VerificationError("; ".join(source_errors))
    firing = _firing_control()
    if firing["status"] != "PASS":
        raise Generation2VerificationError("independent firing control failed")
    slices = receipt.get("slices", {})
    if set(slices) != {"root", "member-000", "member-001"}:
        raise Generation2VerificationError("receipt does not contain the complete Hive population")
    actual_slices: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    with _activated():
        for actor in ("root", "member-000", "member-001"):
            recorded = slices[actor]
            reproduced = _reproduce_actor(
                workspace,
                recorded["assigned_development_roots"],
                recorded["assigned_fresh_root"],
            )
            actual_slices[actor] = reproduced
            expected = recorded["per_world"][
                next(iter(recorded["per_world"]))
            ]
            fields = {
                key: reproduced[key]
                for key in (
                    "source_root",
                    "source_manifest",
                    "regime_id",
                    "regime_token_count",
                    "training_frame_count",
                    "first_chunk_frame_count",
                    "second_chunk_frame_count",
                    "holdout_frame_count",
                    "sample_count",
                    "target_rms",
                    "causal_nrmse",
                    "isotropic_nrmse",
                    "guarded_nrmse",
                    "identity_broken_nrmse",
                    "isotropic_correction_fractional_rmse_reduction",
                    "guarded_correction_fractional_rmse_reduction",
                    "guarded_vs_isotropic_fractional_difference",
                    "guarded_vs_isotropic_max_abs",
                    "guarded_support_after_first_chunk",
                    "guarded_support_after_second_chunk",
                )
            }
            expected_fields = {key: expected[key] for key in fields}
            errors.extend(_same(expected_fields, fields, f"{actor}.per_world"))
            errors.extend(
                _same(
                    {
                        "baseline_state_sha256": reproduced["baseline_state_sha256"],
                        "trained_state_sha256": reproduced["trained_state_sha256"],
                        "checkpoint_sha256": reproduced["checkpoint_sha256"],
                    },
                    {
                        "baseline_state_sha256": recorded["field"][
                            "baseline_state_sha256"
                        ],
                        "trained_state_sha256": recorded["field"][
                            "trained_state_sha256"
                        ],
                        "checkpoint_sha256": expected["field"]["checkpoint_sha256"],
                    },
                    f"{actor}.field",
                )
            )
            if not all(reproduced["controls"].values()):
                errors.append(f"{actor}: reproduced controls failed")
        if errors:
            raise Generation2VerificationError("; ".join(errors[:20]))
    bundle = _verify_live_bundle(receipt, prior)
    return {
        "schema": "cassifi.generation2-isotropic-regime-guarded-rollout-verification.v1",
        "receipt": str(receipt_path),
        "experiment_id": EXPERIMENT_ID,
        "firing_control": firing,
        "actor_count": len(actual_slices),
        "reproduced_slices": {
            actor: {
                "source_root": row["source_root"],
                "guarded_support_after_second_chunk": row[
                    "guarded_support_after_second_chunk"
                ],
                "guarded_vs_isotropic_max_abs": row[
                    "guarded_vs_isotropic_max_abs"
                ],
                "controls_passed": all(row["controls"].values()),
            }
            for actor, row in actual_slices.items()
        },
        "live_bundle": bundle,
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.workspace, args.receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
