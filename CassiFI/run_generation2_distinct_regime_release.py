"""Measure the complementary generation-two regime-release path.

Two distinct source-bound regime identities must accumulate the two independent
supports needed for anisotropy, while a repeated chunk within either identity
must not add another support.  The receipt is deliberately small and synthetic:
it isolates the guard transition from the chronological holdout campaign.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

import cassi_regime_covariant_recurrent_memory as v2
from cassi_generation2_isotropic_rollout_field import (
    Generation2GuardedFieldConfig,
    Generation2IsotropicRegimeGuardedField,
)
from cassi_hierarchical_covariant_recurrent_field import (
    HierarchicalCovariantFieldConfig,
    RegimeCovariantState,
)


SCHEMA = "cassifi.generation2-distinct-regime-release.v1"
EXPERIMENT_ID = "generation2-distinct-regime-release-v1"
OUTPUT = "CassiFI/_diag/generation2-distinct-regime-release-v1.json"
LAGS = (1, 2, 4, 8)
CONFIG = {
    "present_width": 3,
    "max_identities": 8,
    "lags": list(LAGS),
    "correction_ridge": 0.1,
    "anisotropy_ridge": 8.0,
    "anisotropy_support_threshold": 0.2,
    "min_anisotropic_worlds": 2,
    "regime_slots": 8,
}
REGIME_SEEDS = {"A": 22103, "B": 22111}
ANALYSIS_SOURCES = (
    "CassiFI/run_generation2_distinct_regime_release.py",
    "CassiFI/cassi_generation2_isotropic_rollout_field.py",
    "CassiFI/cassi_hierarchical_covariant_recurrent_field.py",
    "CassiFI/cassi_regime_covariant_recurrent_memory.py",
)


class DistinctRegimeReleaseError(RuntimeError):
    """Raised when the complementary release control cannot be measured."""


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


def _source_manifest(workspace: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative in ANALYSIS_SOURCES:
        path = workspace / relative
        if not path.is_file():
            raise DistinctRegimeReleaseError(f"source is absent: {relative}")
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    return rows


def _frames(seed: int) -> list[Any]:
    return list(v2._synthetic_world(seed))


def _frame_digest(frames: Iterable[Any]) -> str:
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
            array = np.asarray(getattr(frame, name), dtype=dtype)
            digest.update(name.encode("ascii"))
            digest.update(repr(array.shape).encode("ascii"))
            digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _controller() -> Generation2IsotropicRegimeGuardedField:
    return Generation2IsotropicRegimeGuardedField(
        Generation2GuardedFieldConfig(
            HierarchicalCovariantFieldConfig(
                present_width=CONFIG["present_width"],
                max_identities=CONFIG["max_identities"],
                lags=LAGS,
                correction_ridge=CONFIG["correction_ridge"],
                anisotropy_ridge=CONFIG["anisotropy_ridge"],
                anisotropy_support_threshold=CONFIG["anisotropy_support_threshold"],
                min_anisotropic_worlds=CONFIG["min_anisotropic_worlds"],
            ),
            regime_slots=CONFIG["regime_slots"],
        )
    )


def _regime(seed: int, frames: list[Any]) -> dict[str, Any]:
    manifest_sha256 = _frame_digest(frames)
    return {
        "seed": seed,
        "frame_count": len(frames),
        "manifest_sha256": manifest_sha256,
        "regime_id": f"synthetic://generation2-distinct/{seed}/{manifest_sha256[:16]}",
    }


def _inspection(controller: Generation2IsotropicRegimeGuardedField, state: RegimeCovariantState) -> dict[str, Any]:
    value = controller.inspect(state)
    return {
        "guard_regime_token_count": int(value["guard_regime_token_count"]),
        "guard_unique_regime_support": int(value["guard_unique_regime_support"]),
        "anisotropic_world_support": int(value["anisotropic_world_support"]),
        "basis_coefficients": [float(item) for item in value["basis_coefficients"]],
        "state_sha256": controller.state_sha256(state),
    }


def _max_abs(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.max(np.abs(left - right)))


def run(workspace: Path) -> dict[str, Any]:
    source_manifest = _source_manifest(workspace)
    worlds = {key: _frames(seed) for key, seed in REGIME_SEEDS.items()}
    regimes = {key: _regime(REGIME_SEEDS[key], worlds[key]) for key in ("A", "B")}
    controller = _controller()

    state = controller.fit_snapshot_baseline(controller.initial_state(), worlds["A"])
    baseline_state_sha256 = controller.state_sha256(state)
    state = controller.begin_isotropic_rollout(state)
    rollout_state_sha256 = controller.state_sha256(state)

    stages: dict[str, dict[str, Any]] = {}

    state = controller.learn_world(
        state, worlds["A"], regime_id=regimes["A"]["regime_id"]
    )
    stages["A-first"] = _inspection(controller, state)

    state = controller.learn_world(
        state, worlds["A"], regime_id=regimes["A"]["regime_id"]
    )
    stages["A-repeat"] = _inspection(controller, state)
    a_guarded = controller.forecast_world(state, worlds["A"])
    a_isotropic = controller.forecast_isotropic(state, worlds["A"])
    a_repeat_max_abs = _max_abs(a_guarded.combined, a_isotropic.combined)

    state = controller.learn_world(
        state, worlds["B"], regime_id=regimes["B"]["regime_id"]
    )
    stages["B-first"] = _inspection(controller, state)
    b_guarded = controller.forecast_world(state, worlds["B"])
    b_isotropic = controller.forecast_isotropic(state, worlds["B"])
    b_release_max_abs = _max_abs(b_guarded.combined, b_isotropic.combined)

    state = controller.learn_world(
        state, worlds["B"], regime_id=regimes["B"]["regime_id"]
    )
    stages["B-repeat"] = _inspection(controller, state)
    b_repeat_guarded = controller.forecast_world(state, worlds["B"])
    b_repeat_isotropic = controller.forecast_isotropic(state, worlds["B"])
    b_repeat_max_abs = _max_abs(
        b_repeat_guarded.combined, b_repeat_isotropic.combined
    )

    checkpoint = controller.export_state(state)
    restored = controller.import_state(checkpoint)
    final_sha256 = controller.state_sha256(state)
    checkpoint_sha256 = hashlib.sha256(checkpoint).hexdigest()
    restored_sha256 = controller.state_sha256(restored)

    controls = {
        "distinct_manifest_digests": (
            regimes["A"]["manifest_sha256"] != regimes["B"]["manifest_sha256"]
        ),
        "first_regime_support_one": stages["A-first"]["guard_unique_regime_support"] == 1,
        "first_repeat_does_not_add_support": (
            stages["A-repeat"]["guard_unique_regime_support"] == 1
        ),
        "second_regime_releases_support_two": (
            stages["B-first"]["guard_unique_regime_support"] == 2
            and stages["B-first"]["anisotropic_world_support"] == 2
        ),
        "second_repeat_does_not_add_support": (
            stages["B-repeat"]["guard_unique_regime_support"] == 2
            and stages["B-repeat"]["anisotropic_world_support"] == 2
        ),
        "pre_release_isotropic": a_repeat_max_abs == 0.0,
        "release_has_nonzero_anisotropic_basis": (
            abs(stages["B-first"]["basis_coefficients"][1]) > 1e-6
        ),
        "release_changes_forecast": b_release_max_abs > 1e-12,
        "repeated_release_remains_anisotropic": b_repeat_max_abs > 1e-12,
        "checkpoint_roundtrip_exact": (
            checkpoint_sha256 == final_sha256
            and restored_sha256 == final_sha256
        ),
    }
    if not all(controls.values()):
        failed = [name for name, passed in controls.items() if not passed]
        raise DistinctRegimeReleaseError(
            "distinct-regime release control failed: " + ", ".join(failed)
        )

    return {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "status": "PASS",
        "source_manifest": source_manifest,
        "config": CONFIG,
        "regimes": regimes,
        "sequence": ["A-first", "A-repeat", "B-first", "B-repeat"],
        "stages": stages,
        "observables": {
            "A_repeat_guarded_vs_isotropic_max_abs": a_repeat_max_abs,
            "B_first_guarded_vs_isotropic_max_abs": b_release_max_abs,
            "B_repeat_guarded_vs_isotropic_max_abs": b_repeat_max_abs,
            "B_first_anisotropic_basis": stages["B-first"]["basis_coefficients"][1],
            "final_regime_token_count": stages["B-repeat"]["guard_regime_token_count"],
            "final_unique_regime_support": stages["B-repeat"]["guard_unique_regime_support"],
            "final_anisotropic_world_support": stages["B-repeat"]["anisotropic_world_support"],
            "baseline_state_sha256": baseline_state_sha256,
            "rollout_state_sha256": rollout_state_sha256,
            "final_state_sha256": final_sha256,
            "checkpoint_sha256": checkpoint_sha256,
            "restored_state_sha256": restored_sha256,
        },
        "controls": controls,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    output = (args.out or workspace / OUTPUT).resolve()
    receipt = run(workspace)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical(receipt) + b"\n")
    print(json.dumps({"status": receipt["status"], "receipt": str(output)}, indent=2))


if __name__ == "__main__":
    main()
