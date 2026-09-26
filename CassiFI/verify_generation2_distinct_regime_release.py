"""Independently reproduce the distinct-regime generation-two release receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
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


SCHEMA = "cassifi.generation2-distinct-regime-release-verification.v1"
EXPERIMENT_ID = "generation2-distinct-regime-release-v1"
RECEIPT = "CassiFI/_diag/generation2-distinct-regime-release-v1.json"
OUTPUT = "CassiFI/_diag/generation2-distinct-regime-release-verification-v1.json"
LAGS = (1, 2, 4, 8)
EXPECTED_CONFIG = {
    "present_width": 3,
    "max_identities": 8,
    "lags": [1, 2, 4, 8],
    "correction_ridge": 0.1,
    "anisotropy_ridge": 8.0,
    "anisotropy_support_threshold": 0.2,
    "min_anisotropic_worlds": 2,
    "regime_slots": 8,
}
EXPECTED_SOURCES = (
    "CassiFI/run_generation2_distinct_regime_release.py",
    "CassiFI/cassi_generation2_isotropic_rollout_field.py",
    "CassiFI/cassi_hierarchical_covariant_recurrent_field.py",
    "CassiFI/cassi_regime_covariant_recurrent_memory.py",
)


class ReleaseVerificationError(RuntimeError):
    """Raised when an independently rebuilt release path differs."""


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
                present_width=3,
                max_identities=8,
                lags=LAGS,
                correction_ridge=0.1,
                anisotropy_ridge=8.0,
                anisotropy_support_threshold=0.2,
                min_anisotropic_worlds=2,
            ),
            regime_slots=8,
        )
    )


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
    }


def _max_abs(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.max(np.abs(left - right)))


def _assert_close(expected: float, actual: float, label: str) -> None:
    if not math.isclose(expected, actual, rel_tol=2e-12, abs_tol=2e-14):
        raise ReleaseVerificationError(
            f"{label} differs: expected {expected!r}, actual {actual!r}"
        )


def _assert_stage(expected: dict[str, Any], actual: dict[str, Any], label: str) -> None:
    for key in (
        "guard_regime_token_count",
        "guard_unique_regime_support",
        "anisotropic_world_support",
        "state_sha256",
    ):
        if expected[key] != actual[key]:
            raise ReleaseVerificationError(
                f"{label}.{key} differs: expected {expected[key]!r}, actual {actual[key]!r}"
            )
    if len(expected["basis_coefficients"]) != len(actual["basis_coefficients"]):
        raise ReleaseVerificationError(f"{label}.basis_coefficients width differs")
    for index, (left, right) in enumerate(
        zip(expected["basis_coefficients"], actual["basis_coefficients"], strict=True)
    ):
        _assert_close(float(left), float(right), f"{label}.basis_coefficients[{index}]")


def _verify_source_manifest(workspace: Path, receipt: dict[str, Any]) -> None:
    rows = receipt.get("source_manifest")
    if not isinstance(rows, list) or [row.get("path") for row in rows] != list(EXPECTED_SOURCES):
        raise ReleaseVerificationError("source manifest paths differ")
    for row in rows:
        path = workspace / str(row["path"])
        if not path.is_file():
            raise ReleaseVerificationError(f"source is absent: {path}")
        if int(row["bytes"]) != path.stat().st_size:
            raise ReleaseVerificationError(f"source byte count differs: {path}")
        if str(row["sha256"]) != _file_sha256(path):
            raise ReleaseVerificationError(f"source digest differs: {path}")


def verify(workspace: Path, receipt_path: Path) -> dict[str, Any]:
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    if receipt.get("schema") != "cassifi.generation2-distinct-regime-release.v1":
        raise ReleaseVerificationError("receipt schema differs")
    if receipt.get("experiment_id") != EXPERIMENT_ID or receipt.get("status") != "PASS":
        raise ReleaseVerificationError("receipt identity or status differs")
    if receipt.get("config") != EXPECTED_CONFIG:
        raise ReleaseVerificationError("receipt configuration differs")
    _verify_source_manifest(workspace, receipt)

    regimes = receipt.get("regimes")
    if not isinstance(regimes, dict) or set(regimes) != {"A", "B"}:
        raise ReleaseVerificationError("receipt regime set differs")
    worlds: dict[str, list[Any]] = {}
    for key in ("A", "B"):
        regime = regimes[key]
        seed = int(regime["seed"])
        worlds[key] = list(v2._synthetic_world(seed))
        manifest_sha256 = _frame_digest(worlds[key])
        expected_id = f"synthetic://generation2-distinct/{seed}/{manifest_sha256[:16]}"
        if int(regime["frame_count"]) != len(worlds[key]):
            raise ReleaseVerificationError(f"{key} frame count differs")
        if regime["manifest_sha256"] != manifest_sha256:
            raise ReleaseVerificationError(f"{key} source manifest differs")
        if regime["regime_id"] != expected_id:
            raise ReleaseVerificationError(f"{key} regime identity is not source-bound")
    if regimes["A"]["manifest_sha256"] == regimes["B"]["manifest_sha256"]:
        raise ReleaseVerificationError("distinct regime manifests collapsed")

    controller = _controller()
    state = controller.fit_snapshot_baseline(controller.initial_state(), worlds["A"])
    baseline_sha256 = controller.state_sha256(state)
    state = controller.begin_isotropic_rollout(state)
    rollout_sha256 = controller.state_sha256(state)
    if baseline_sha256 != receipt["observables"]["baseline_state_sha256"]:
        raise ReleaseVerificationError("baseline state digest differs")
    if rollout_sha256 != receipt["observables"]["rollout_state_sha256"]:
        raise ReleaseVerificationError("rollout state digest differs")

    stages: dict[str, dict[str, Any]] = {}
    state = controller.learn_world(state, worlds["A"], regime_id=regimes["A"]["regime_id"])
    stages["A-first"] = _inspection(controller, state)
    state = controller.learn_world(state, worlds["A"], regime_id=regimes["A"]["regime_id"])
    stages["A-repeat"] = _inspection(controller, state)
    a_guarded = controller.forecast_world(state, worlds["A"])
    a_isotropic = controller.forecast_isotropic(state, worlds["A"])
    a_repeat_max_abs = _max_abs(a_guarded.combined, a_isotropic.combined)
    if not np.array_equal(a_guarded.combined, a_isotropic.combined):
        raise ReleaseVerificationError("same-regime repeat released before distinct support")

    state = controller.learn_world(state, worlds["B"], regime_id=regimes["B"]["regime_id"])
    stages["B-first"] = _inspection(controller, state)
    b_guarded = controller.forecast_world(state, worlds["B"])
    b_isotropic = controller.forecast_isotropic(state, worlds["B"])
    b_release_max_abs = _max_abs(b_guarded.combined, b_isotropic.combined)

    state = controller.learn_world(state, worlds["B"], regime_id=regimes["B"]["regime_id"])
    stages["B-repeat"] = _inspection(controller, state)
    b_repeat_guarded = controller.forecast_world(state, worlds["B"])
    b_repeat_isotropic = controller.forecast_isotropic(state, worlds["B"])
    b_repeat_max_abs = _max_abs(
        b_repeat_guarded.combined, b_repeat_isotropic.combined
    )

    for label in ("A-first", "A-repeat", "B-first", "B-repeat"):
        _assert_stage(receipt["stages"][label], stages[label], label)

    expected_observables = receipt["observables"]
    _assert_close(
        float(expected_observables["A_repeat_guarded_vs_isotropic_max_abs"]),
        a_repeat_max_abs,
        "A repeat forecast difference",
    )
    _assert_close(
        float(expected_observables["B_first_guarded_vs_isotropic_max_abs"]),
        b_release_max_abs,
        "B first forecast difference",
    )
    _assert_close(
        float(expected_observables["B_repeat_guarded_vs_isotropic_max_abs"]),
        b_repeat_max_abs,
        "B repeat forecast difference",
    )

    checkpoint = controller.export_state(state)
    restored = controller.import_state(checkpoint)
    final_sha256 = controller.state_sha256(state)
    checkpoint_sha256 = hashlib.sha256(checkpoint).hexdigest()
    restored_sha256 = controller.state_sha256(restored)
    if final_sha256 != expected_observables["final_state_sha256"]:
        raise ReleaseVerificationError("final state digest differs")
    if checkpoint_sha256 != expected_observables["checkpoint_sha256"]:
        raise ReleaseVerificationError("checkpoint digest differs")
    if restored_sha256 != expected_observables["restored_state_sha256"]:
        raise ReleaseVerificationError("restored state digest differs")

    controls = {
        "distinct_manifest_digests": regimes["A"]["manifest_sha256"] != regimes["B"]["manifest_sha256"],
        "first_regime_support_one": stages["A-first"]["guard_unique_regime_support"] == 1,
        "first_repeat_does_not_add_support": stages["A-repeat"]["guard_unique_regime_support"] == 1,
        "second_regime_releases_support_two": (
            stages["B-first"]["guard_unique_regime_support"] == 2
            and stages["B-first"]["anisotropic_world_support"] == 2
        ),
        "second_repeat_does_not_add_support": (
            stages["B-repeat"]["guard_unique_regime_support"] == 2
            and stages["B-repeat"]["anisotropic_world_support"] == 2
        ),
        "pre_release_isotropic": a_repeat_max_abs == 0.0,
        "release_has_nonzero_anisotropic_basis": abs(stages["B-first"]["basis_coefficients"][1]) > 1e-6,
        "release_changes_forecast": b_release_max_abs > 1e-12,
        "repeated_release_remains_anisotropic": b_repeat_max_abs > 1e-12,
        "checkpoint_roundtrip_exact": checkpoint_sha256 == final_sha256 == restored_sha256,
    }
    if controls != receipt["controls"]:
        raise ReleaseVerificationError("recomputed controls differ")

    return {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "status": "PASS",
        "receipt": str(receipt_path),
        "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "source_manifest_verified": True,
        "recomputed_stages": stages,
        "recomputed_controls": controls,
        "recomputed_observables": {
            "A_repeat_guarded_vs_isotropic_max_abs": a_repeat_max_abs,
            "B_first_guarded_vs_isotropic_max_abs": b_release_max_abs,
            "B_repeat_guarded_vs_isotropic_max_abs": b_repeat_max_abs,
            "final_unique_regime_support": stages["B-repeat"]["guard_unique_regime_support"],
            "final_anisotropic_world_support": stages["B-repeat"]["anisotropic_world_support"],
        },
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
