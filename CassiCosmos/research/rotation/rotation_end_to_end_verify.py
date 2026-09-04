#!/usr/bin/env python3
"""Independent G97-G100 replay for the live merge-to-orientation path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = ROOT / "_diag" / "rotation_end_to_end_gpu.json"
OUT_PATH = ROOT / "_diag" / "rotation_end_to_end_verify.json"
PREREG_PATH = ROOT / "research" / "rotation" / "rotation_end_to_end_retry_prereg.md"
ORIGINAL_PREREG_PATH = ROOT / "research" / "rotation" / "rotation_end_to_end_prereg.md"
ACQUISITION_PATH = ROOT / "scripts" / "verify_rotation_end_to_end.gd"
EPS = 1.0e-30
STATE_HASH_KEYS = ("pos", "vel", "merge_spin", "orientation")
RESERVOIR_HASH_KEYS = ("reservoir_momentum", "reservoir_momentum_next")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _float_hash(values: Any) -> str:
    return hashlib.sha256(np.asarray(values, dtype="<f4").tobytes()).hexdigest()


def _norm(value: np.ndarray) -> float:
    return float(np.linalg.norm(value))


def _relative(a: np.ndarray, b: np.ndarray) -> float:
    return _norm(a - b) / max(_norm(a), _norm(b), EPS)


def _same(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (float, list)):
        try:
            return bool(
                np.allclose(
                    np.asarray(actual, dtype=np.float64),
                    np.asarray(expected, dtype=np.float64),
                    rtol=1.0e-10,
                    atol=1.0e-10,
                )
            )
        except (TypeError, ValueError):
            return False
    return actual == expected


def _require_values(name: str, actual: Any, expected: dict[str, Any]) -> None:
    if not isinstance(actual, dict):
        raise ValueError(f"{name}: mapping absent")
    missing = sorted(set(expected) - set(actual))
    if missing:
        raise ValueError(f"{name}: omitted keys {missing}")
    mismatches = {
        key: {"recorded": actual[key], "expected": value}
        for key, value in expected.items()
        if not _same(actual[key], value)
    }
    if mismatches:
        raise ValueError(f"{name}: mismatches {mismatches}")


def _state_arrays(state: dict[str, Any]) -> dict[str, np.ndarray]:
    arrays = {
        "pos": np.asarray(state["pos"], dtype=np.float64).reshape(4, 4),
        "vel": np.asarray(state["vel"], dtype=np.float64).reshape(4, 4),
        "merge_spin": np.asarray(state["merge_spin"], dtype=np.float64).reshape(4, 4),
        "orientation": np.asarray(state["orientation"], dtype=np.float64).reshape(4, 4),
        "telemetry": np.asarray(state["telemetry"], dtype=np.float64).reshape(16),
    }
    if not all(np.isfinite(array).all() for array in arrays.values()):
        raise ValueError("non-finite compact state")
    return arrays


def _validate_contract(raw: dict[str, Any], acquisition_sha256: str) -> dict[str, Any]:
    if raw.get("schema") != "cassi.rotation-end-to-end.raw.v1":
        raise ValueError("raw schema mismatch")
    expected_prereg = str(PREREG_PATH.relative_to(ROOT)).replace("\\", "/")
    if raw.get("preregistration") != expected_prereg:
        raise ValueError("preregistration path mismatch")
    if raw.get("acquisition_source_sha256") != acquisition_sha256:
        raise ValueError("producer source digest absent or stale")
    if raw.get("harness_failures"):
        raise ValueError("harness failures: " + "; ".join(raw["harness_failures"]))
    if not bool(raw.get("ok", False)):
        raise ValueError("acquisition marked invalid")
    if raw.get("pair") != [0, 1] or raw.get("environment") != [2, 3]:
        raise ValueError("particle tags mismatch")
    if int(raw.get("orientation_steps", -1)) != 16:
        raise ValueError("orientation cadence mismatch")
    _require_values(
        "field reset",
        raw.get("field_reset"),
        {
            "ey": 1.618033988749895,
            "ei": 1.0,
            "q": 1.618033988749895**2 + 1.0,
            "field_vel": 0.0,
        },
    )
    expected_config = {
        "rd_global": False,
        "owns_rd": False,
        "grid_N": 64,
        "N_particles": 4,
        "dt": 1.0e-6,
        "seed": 97100,
        "cluster_radius": 25.0,
        "box_scale": 1.0,
        "box_aspect": [1.0, 1.0, 1.0],
        "num_clusters": 1,
        "initial_radius_fraction": 0.5,
        "initial_condition": 1,
        "initial_v_circ_factor": 0.0,
        "source_strength": 0.0,
        "gravity_mode": 2,
        "river_calibrate_gn": False,
        "field_attractor_init": True,
        "freeze_field": True,
        "black_holes_enabled": False,
        "bh_accretion": False,
        "dual_grid": False,
        "meshless_mode": False,
        "meshless_gravity": False,
        "gridless_physics": False,
        "particle_merge": True,
        "merge_cadence_steps": 1,
        "merge_virial": False,
        "rotation_stress_enabled": True,
        "rotation_grid_N": 32,
        "rotation_rungs": 3,
        "rotation_field_inertia": 2.0,
        "rotation_c_t": 0.0,
        "rotation_c_l": 0.0,
        "rotation_scale_omega": 0.0,
        "rotation_attenuation": 1.0 / 1.618033988749895,
        "rotation_exchange_rate": 0.0,
        "rotation_reservoir_inertia": 3.0,
        "rotation_lower_reservoir_coupling": 0.0,
        "rotation_upper_reservoir_coupling": 0.0,
        "effective_extents": [37.5, 37.5, 37.5],
        "effective_gravity_g_n": 1.0,
        "effective_gravity_g_eff": 1.0,
    }
    _require_values("engine config", raw.get("config"), expected_config)

    zero_reservoir_sha256 = hashlib.sha256(bytes(65536 * 16)).hexdigest()
    states: dict[str, Any] = {}
    for label in ("before", "post_merge", "post_orientation"):
        state = raw.get(label)
        if not isinstance(state, dict):
            raise ValueError(f"{label}: state absent")
        _require_values(
            f"{label} metadata",
            state,
            {
                "enabled": True,
                "grid_N": 32,
                "rungs": 3,
                "cells": 32768,
                "reservoir_count": 65536,
                "reservoir_inertia": 3.0,
                "lower_reservoir_coupling": 0.0,
                "upper_reservoir_coupling": 0.0,
                "reservoir_momentum_max_abs": 0.0,
                "reservoir_momentum_next_max_abs": 0.0,
            },
        )
        arrays = _state_arrays(state)
        hashes = raw.get(f"{label}_hashes")
        if not isinstance(hashes, dict):
            raise ValueError(f"{label}: state hashes absent")
        for key in STATE_HASH_KEYS:
            if hashes.get(key) != _float_hash(state[key]):
                raise ValueError(f"{label}: {key} hash mismatch")
        for key in RESERVOIR_HASH_KEYS:
            if hashes.get(key) != zero_reservoir_sha256:
                raise ValueError(f"{label}: {key} is not byte-zero")
        states[label] = arrays

    publication = raw.get("publication")
    if not isinstance(publication, dict):
        raise ValueError("bounded publication absent")
    telemetry = np.asarray(publication.get("telemetry"), dtype=np.float64)
    orientations = np.asarray(publication.get("orientation_sample"), dtype=np.float64)
    if telemetry.shape != (16,) or orientations.shape != (16,):
        raise ValueError("bounded publication shape mismatch")
    if not np.isfinite(telemetry).all() or not np.isfinite(orientations).all():
        raise ValueError("non-finite bounded publication")
    return {"states": states, "publication": publication}


def _total_momentum_angular(state: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    pos = state["pos"]
    vel = state["vel"]
    spin = state["merge_spin"]
    live = pos[:, 3] > 0.0
    mass = pos[live, 3]
    r = pos[live, :3]
    v = vel[live, :3]
    total_mass = float(np.sum(mass))
    momentum = np.sum(mass[:, None] * v, axis=0)
    center = np.sum(mass[:, None] * r, axis=0) / total_mass
    mean_velocity = momentum / total_mass
    orbital = np.sum(np.cross(r - center, mass[:, None] * (v - mean_velocity)), axis=0)
    intrinsic = np.sum(spin[live, :3], axis=0)
    return momentum, orbital + intrinsic


def _evaluate(raw: dict[str, Any], validated: dict[str, Any]) -> tuple[dict[str, Any], str]:
    states = validated["states"]
    before = states["before"]
    post_merge = states["post_merge"]
    post_orientation = states["post_orientation"]
    pair = np.asarray(raw["pair"], dtype=np.int64)
    environment = np.asarray(raw["environment"], dtype=np.int64)
    expected_spin = np.asarray(raw["expected_pair_internal_L"], dtype=np.float64)

    initial_spin_zero = bool(np.array_equal(before["merge_spin"], np.zeros((4, 4))))
    live_merge = post_merge["pos"][:, 3] > 0.0
    pair_live = live_merge[pair]
    environment_live = live_merge[environment]
    survivor = int(pair[np.flatnonzero(pair_live)[0]]) if np.count_nonzero(pair_live) == 1 else -1
    survivor_spin = (
        post_merge["merge_spin"][survivor, :3] if survivor >= 0 else np.full(3, np.nan)
    )
    spin_error = _relative(survivor_spin, expected_spin)
    exact_merge = bool(
        np.count_nonzero(live_merge) == 3
        and np.count_nonzero(pair_live) == 1
        and np.count_nonzero(environment_live) == 2
    )
    g97 = {
        "pass": bool(initial_spin_zero and exact_merge and spin_error <= 1.0e-3),
        "initial_spin_byte_zero": initial_spin_zero,
        "live_after_merge": int(np.count_nonzero(live_merge)),
        "survivor": survivor,
        "survivor_spin": survivor_spin.tolist(),
        "expected_spin": expected_spin.tolist(),
        "spin_relative_error": spin_error,
    }

    identity = np.asarray([0.0, 0.0, 0.0, 1.0])
    if survivor >= 0:
        before_q = before["orientation"][survivor]
        merge_q = post_merge["orientation"][survivor]
        final_q = post_orientation["orientation"][survivor]
    else:
        before_q = merge_q = final_q = np.full(4, np.nan)
    initial_error = _norm(before_q - identity)
    post_merge_error = _norm(merge_q - identity)
    orientation_change = _norm(final_q - identity)
    norm_error = abs(_norm(final_q) - 1.0)
    axis_alignment = float(np.dot(final_q[:3], survivor_spin))
    orientation_finite = bool(np.isfinite(post_orientation["orientation"]).all())
    g98 = {
        "pass": bool(
            initial_error <= 1.0e-7
            and post_merge_error <= 1.0e-7
            and orientation_change > 1.0e-6
            and norm_error <= 1.0e-5
            and axis_alignment > 0.0
            and orientation_finite
        ),
        "initial_identity_error": initial_error,
        "post_merge_identity_error": post_merge_error,
        "final_orientation": final_q.tolist(),
        "orientation_change": orientation_change,
        "quaternion_norm_error": norm_error,
        "axis_alignment_dot": axis_alignment,
        "orientation_finite": orientation_finite,
    }

    publication = validated["publication"]
    published_orientation = np.asarray(
        publication["orientation_sample"], dtype=np.float64
    ).reshape(4, 4)
    publication_difference = (
        _norm(published_orientation[survivor] - final_q) if survivor >= 0 else np.inf
    )
    publication_telemetry = np.asarray(publication["telemetry"], dtype=np.float64)
    g99 = {
        "pass": bool(
            publication.get("enabled") is True
            and int(publication.get("sample_count", -1)) == 4
            and len(publication_telemetry) == 16
            and _same(publication.get("reservoir_inertia"), 3.0)
            and _same(publication.get("lower_reservoir_coupling"), 0.0)
            and _same(publication.get("upper_reservoir_coupling"), 0.0)
            and publication_difference <= 1.0e-7
            and float(publication_telemetry[7]) == 0.0
        ),
        "enabled": publication.get("enabled"),
        "sample_count": publication.get("sample_count"),
        "telemetry_count": len(publication_telemetry),
        "publication_orientation_difference": publication_difference,
        "invalid_telemetry": float(publication_telemetry[7]),
        "reservoir_inertia": publication.get("reservoir_inertia"),
        "lower_reservoir_coupling": publication.get("lower_reservoir_coupling"),
        "upper_reservoir_coupling": publication.get("upper_reservoir_coupling"),
        "reservoir_momentum_byte_zero": True,
    }

    before_momentum, before_angular = _total_momentum_angular(before)
    merge_momentum, merge_angular = _total_momentum_angular(post_merge)
    momentum_error = _relative(merge_momentum, before_momentum)
    angular_error = _relative(merge_angular, before_angular)
    before_environment = np.concatenate(
        (before["pos"][environment].ravel(), before["vel"][environment].ravel())
    )
    merge_environment = np.concatenate(
        (
            post_merge["pos"][environment].ravel(),
            post_merge["vel"][environment].ravel(),
        )
    )
    environment_change = _relative(merge_environment, before_environment)
    g100 = {
        "pass": bool(
            momentum_error <= 1.0e-3
            and angular_error <= 1.0e-3
            and environment_change <= 1.0e-5
        ),
        "before_momentum": before_momentum.tolist(),
        "post_merge_momentum": merge_momentum.tolist(),
        "momentum_relative_error": momentum_error,
        "before_total_angular": before_angular.tolist(),
        "post_merge_total_angular": merge_angular.tolist(),
        "angular_relative_error": angular_error,
        "environment_relative_state_change": environment_change,
    }

    gates = {"G97": g97, "G98": g98, "G99": g99, "G100": g100}
    verdict = (
        "PASS_LIVE_MERGE_TO_ORIENTATION"
        if all(gate["pass"] for gate in gates.values())
        else "FAIL_LIVE_MERGE_TO_ORIENTATION"
    )
    return gates, verdict


def main() -> int:
    hashes = {
        "raw_sha256": _sha256(RAW_PATH),
        "acquisition_source_sha256": _sha256(ACQUISITION_PATH),
        "verifier_source_sha256": _sha256(Path(__file__)),
        "preregistration_sha256": _sha256(PREREG_PATH),
        "original_preregistration_sha256": _sha256(ORIGINAL_PREREG_PATH),
    }
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    try:
        validated = _validate_contract(raw, hashes["acquisition_source_sha256"])
        gates, verdict = _evaluate(raw, validated)
        receipt: dict[str, Any] = {
            "schema": "cassi.rotation-end-to-end.verify.v1",
            "preregistration": str(PREREG_PATH.relative_to(ROOT)).replace("\\", "/"),
            "original_preregistration": str(
                ORIGINAL_PREREG_PATH.relative_to(ROOT)
            ).replace("\\", "/"),
            "raw_receipt": str(RAW_PATH.relative_to(ROOT)).replace("\\", "/"),
            "hashes": hashes,
            "implementation_valid": True,
            "gates": gates,
            "verdict": verdict,
        }
        exit_code = 0 if all(gate["pass"] for gate in gates.values()) else 1
    except Exception as exc:  # Preserve implementation failures verbatim.
        receipt = {
            "schema": "cassi.rotation-end-to-end.verify.v1",
            "preregistration": str(PREREG_PATH.relative_to(ROOT)).replace("\\", "/"),
            "original_preregistration": str(
                ORIGINAL_PREREG_PATH.relative_to(ROOT)
            ).replace("\\", "/"),
            "raw_receipt": str(RAW_PATH.relative_to(ROOT)).replace("\\", "/"),
            "hashes": hashes,
            "implementation_valid": False,
            "error": f"{type(exc).__name__}: {exc}",
            "gates": {},
            "verdict": "INCONCLUSIVE—IMPLEMENTATION",
        }
        exit_code = 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if receipt["implementation_valid"]:
        for name, gate in receipt["gates"].items():
            print(f"[{('PASS' if gate['pass'] else 'FAIL')}] {name}")
    else:
        print(f"[FAIL] implementation: {receipt['error']}")
    print(f"VERDICT: {receipt['verdict']}")
    print(f"WROTE: {OUT_PATH}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
