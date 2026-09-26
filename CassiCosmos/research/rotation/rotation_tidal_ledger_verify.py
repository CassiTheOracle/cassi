#!/usr/bin/env python3
"""Independent replay of the preregistered G86-G91 rotation ledger gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = ROOT / "_diag" / "rotation_tidal_ledger_gpu_integrity.json"
OUT_PATH = ROOT / "_diag" / "rotation_tidal_ledger_verify_integrity.json"
PREREG_PATH = (
    ROOT / "research" / "rotation" / "rotation_tidal_ledger_integrity_prereg.md"
)
PHYSICS_PREREG_PATH = (
    ROOT / "research" / "rotation" / "rotation_tidal_ledger_prereg.md"
)
ACQUISITION_PATH = ROOT / "scripts" / "verify_rotation_tidal_ledger.gd"
EPS = 1.0e-30
REQUIRED_CASES = {
    "sphere_g64_dt005",
    "aligned_g64_dt005",
    "plus_g64_dt010",
    "plus_g64_dt005",
    "plus_g64_dt0025",
    "minus_g64_dt005",
    "plus_g128_dt005",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _norm(value: np.ndarray) -> float:
    return float(np.linalg.norm(value))


def _relative_vector(a: np.ndarray, b: np.ndarray) -> float:
    return _norm(a - b) / max(_norm(a), _norm(b), EPS)


def _state_arrays(state: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pos = np.asarray(state["pos"], dtype=np.float64).reshape(-1, 4)
    vel = np.asarray(state["vel"], dtype=np.float64).reshape(-1, 4)
    acc = np.asarray(state["acc"], dtype=np.float64).reshape(-1, 4)
    if pos.shape != vel.shape or pos.shape != acc.shape:
        raise ValueError(f"particle buffer shape mismatch: {pos.shape}, {vel.shape}, {acc.shape}")
    if not np.isfinite(pos).all() or not np.isfinite(vel).all() or not np.isfinite(acc).all():
        raise ValueError("non-finite particle state")
    if np.any(pos[:, 3] < 0.0):
        raise ValueError("negative particle mass")
    return pos, vel, acc


def _group(
    r: np.ndarray,
    v: np.ndarray,
    a: np.ndarray,
    mass: np.ndarray,
    indices: np.ndarray,
) -> dict[str, np.ndarray | float]:
    m = mass[indices]
    total_mass = float(np.sum(m))
    if total_mass <= 0.0:
        raise ValueError("empty ledger group")
    rr = r[indices]
    vv = v[indices]
    aa = a[indices]
    center = np.sum(m[:, None] * rr, axis=0) / total_mass
    mean_velocity = np.sum(m[:, None] * vv, axis=0) / total_mass
    mean_acceleration = np.sum(m[:, None] * aa, axis=0) / total_mass
    internal = np.sum(
        np.cross(rr - center, m[:, None] * (vv - mean_velocity)), axis=0
    )
    torque = np.sum(
        np.cross(rr - center, m[:, None] * (aa - mean_acceleration)), axis=0
    )
    return {
        "mass": total_mass,
        "center": center,
        "velocity": mean_velocity,
        "acceleration": mean_acceleration,
        "internal": internal,
        "torque": torque,
    }


def _ledger_state(
    state: dict[str, Any], cloud_indices: np.ndarray, environment_indices: np.ndarray
) -> dict[str, np.ndarray]:
    pos, vel, acc = _state_arrays(state)
    r = pos[:, :3]
    v = vel[:, :3]
    a = acc[:, :3]
    mass = pos[:, 3]
    cloud = _group(r, v, a, mass, cloud_indices)
    environment = _group(r, v, a, mass, environment_indices)

    total_mass = float(cloud["mass"]) + float(environment["mass"])
    center = (
        float(cloud["mass"]) * np.asarray(cloud["center"])
        + float(environment["mass"]) * np.asarray(environment["center"])
    ) / total_mass
    mean_velocity = (
        float(cloud["mass"]) * np.asarray(cloud["velocity"])
        + float(environment["mass"]) * np.asarray(environment["velocity"])
    ) / total_mass
    mean_acceleration = (
        float(cloud["mass"]) * np.asarray(cloud["acceleration"])
        + float(environment["mass"]) * np.asarray(environment["acceleration"])
    ) / total_mass

    orbital = np.zeros(3, dtype=np.float64)
    orbital_torque = np.zeros(3, dtype=np.float64)
    for group in (cloud, environment):
        group_mass = float(group["mass"])
        orbital += np.cross(
            np.asarray(group["center"]) - center,
            group_mass * (np.asarray(group["velocity"]) - mean_velocity),
        )
        orbital_torque += np.cross(
            np.asarray(group["center"]) - center,
            group_mass * (np.asarray(group["acceleration"]) - mean_acceleration),
        )

    cloud_internal = np.asarray(cloud["internal"])
    environment_internal = np.asarray(environment["internal"])
    return {
        "cloud_internal": cloud_internal,
        "environment_internal": environment_internal,
        "orbital": orbital,
        "cloud_torque": np.asarray(cloud["torque"]),
        "environment_torque": np.asarray(environment["torque"]),
        "orbital_torque": orbital_torque,
        "total": cloud_internal + environment_internal + orbital,
    }


def _closure(delta: np.ndarray, impulse: np.ndarray) -> float:
    return _norm(delta - impulse) / max(_norm(delta), _norm(impulse), EPS)


def _case_summary(
    case: dict[str, Any], cloud_indices: np.ndarray, environment_indices: np.ndarray
) -> dict[str, Any]:
    states = case["states"]
    intervals = int(case["intervals"])
    if len(states) != intervals + 1:
        raise ValueError(f"{case['label']}: expected {intervals + 1} states, got {len(states)}")
    dt = float(case["dt"])
    ledgers = [_ledger_state(state, cloud_indices, environment_indices) for state in states]

    def series(key: str) -> np.ndarray:
        return np.stack([ledger[key] for ledger in ledgers])

    cloud_internal = series("cloud_internal")
    environment_internal = series("environment_internal")
    orbital = series("orbital")
    total = series("total")
    cloud_torque = series("cloud_torque")
    environment_torque = series("environment_torque")
    orbital_torque = series("orbital_torque")

    cloud_delta = cloud_internal[-1] - cloud_internal[0]
    environment_delta = environment_internal[-1] - environment_internal[0]
    orbital_delta = orbital[-1] - orbital[0]
    total_delta = total[-1] - total[0]
    cloud_impulse = np.sum(0.5 * dt * (cloud_torque[:-1] + cloud_torque[1:]), axis=0)
    environment_impulse = np.sum(
        0.5 * dt * (environment_torque[:-1] + environment_torque[1:]), axis=0
    )
    orbital_impulse = np.sum(
        0.5 * dt * (orbital_torque[:-1] + orbital_torque[1:]), axis=0
    )

    return {
        "label": str(case["label"]),
        "grid_N": int(case["grid_N"]),
        "dt": dt,
        "intervals": intervals,
        "cloud_delta": cloud_delta.tolist(),
        "environment_delta": environment_delta.tolist(),
        "orbital_delta": orbital_delta.tolist(),
        "total_delta": total_delta.tolist(),
        "cloud_impulse": cloud_impulse.tolist(),
        "environment_impulse": environment_impulse.tolist(),
        "orbital_impulse": orbital_impulse.tolist(),
        "cloud_closure": _closure(cloud_delta, cloud_impulse),
        "environment_closure": _closure(environment_delta, environment_impulse),
        "orbital_closure": _closure(orbital_delta, orbital_impulse),
    }


def _total_momentum_and_angular(state: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    pos, vel, _ = _state_arrays(state)
    spin = np.asarray(state["merge_spin"], dtype=np.float64).reshape(-1, 4)
    if spin.shape != pos.shape or not np.isfinite(spin).all():
        raise ValueError("invalid merge-spin buffer")
    live = pos[:, 3] > 0.0
    mass = pos[live, 3]
    if mass.size == 0:
        raise ValueError("merge state has no live particles")
    r = pos[live, :3]
    v = vel[live, :3]
    total_mass = float(np.sum(mass))
    momentum = np.sum(mass[:, None] * v, axis=0)
    center = np.sum(mass[:, None] * r, axis=0) / total_mass
    mean_velocity = momentum / total_mass
    orbital = np.sum(np.cross(r - center, mass[:, None] * (v - mean_velocity)), axis=0)
    intrinsic = np.sum(spin[live, :3], axis=0)
    return momentum, orbital + intrinsic


def _merge_summary(merge: dict[str, Any]) -> dict[str, Any]:
    before = merge["before"]
    after = merge["after"]
    before_pos, before_vel, _ = _state_arrays(before)
    after_pos, after_vel, _ = _state_arrays(after)
    if before_pos.shape != after_pos.shape:
        raise ValueError("merge particle count changed")

    before_momentum, before_angular = _total_momentum_and_angular(before)
    after_momentum, after_angular = _total_momentum_and_angular(after)
    pair = np.asarray(merge["pair"], dtype=np.int64)
    environment = np.asarray(merge["environment"], dtype=np.int64)
    after_spin = np.asarray(after["merge_spin"], dtype=np.float64).reshape(-1, 4)
    expected_spin = np.asarray(merge["expected_pair_internal_L"], dtype=np.float64)
    pair_live = after_pos[pair, 3] > 0.0
    environment_live = after_pos[environment, 3] > 0.0
    survivor_spin = np.sum(after_spin[pair[pair_live], :3], axis=0)

    before_environment = np.concatenate(
        (before_pos[environment].ravel(), before_vel[environment].ravel())
    )
    after_environment = np.concatenate(
        (after_pos[environment].ravel(), after_vel[environment].ravel())
    )
    environment_change = _relative_vector(after_environment, before_environment)
    live_after = int(np.count_nonzero(after_pos[:, 3] > 0.0))
    exactly_one_pair = bool(
        live_after == 3
        and np.count_nonzero(pair_live) == 1
        and np.count_nonzero(environment_live) == len(environment)
    )

    return {
        "live_after": live_after,
        "exactly_one_pair_merged": exactly_one_pair,
        "before_momentum": before_momentum.tolist(),
        "after_momentum": after_momentum.tolist(),
        "momentum_relative_error": _relative_vector(after_momentum, before_momentum),
        "before_total_angular": before_angular.tolist(),
        "after_total_angular": after_angular.tolist(),
        "angular_relative_error": _relative_vector(after_angular, before_angular),
        "survivor_spin": survivor_spin.tolist(),
        "expected_spin": expected_spin.tolist(),
        "spin_relative_error": _relative_vector(survivor_spin, expected_spin),
        "environment_relative_state_change": environment_change,
    }


def _gate(passed: bool, **metrics: Any) -> dict[str, Any]:
    return {"pass": bool(passed), **metrics}


def _same_config_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (float, list)):
        try:
            return bool(
                np.allclose(
                    np.asarray(actual, dtype=np.float64),
                    np.asarray(expected, dtype=np.float64),
                    rtol=1.0e-12,
                    atol=1.0e-12,
                )
            )
        except (TypeError, ValueError):
            return False
    return actual == expected


def _require_config(name: str, config: Any, expected: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError(f"{name}: complete engine config is absent")
    missing = sorted(set(expected) - set(config))
    if missing:
        raise ValueError(f"{name}: engine config omits {missing}")
    mismatches = {
        key: {"recorded": config[key], "expected": value}
        for key, value in expected.items()
        if not _same_config_value(config[key], value)
    }
    if mismatches:
        raise ValueError(f"{name}: engine config mismatch: {mismatches}")


def _validate_receipt_contract(raw: dict[str, Any], acquisition_sha256: str) -> None:
    expected_prereg = str(PREREG_PATH.relative_to(ROOT)).replace("\\", "/")
    expected_physics_prereg = str(PHYSICS_PREREG_PATH.relative_to(ROOT)).replace("\\", "/")
    if raw.get("preregistration") != expected_prereg:
        raise ValueError("integrity preregistration path mismatch")
    if raw.get("physics_preregistration") != expected_physics_prereg:
        raise ValueError("physics preregistration path mismatch")
    recorded_sha256 = raw.get("acquisition_source_sha256")
    if recorded_sha256 != acquisition_sha256:
        raise ValueError(
            "raw acquisition-source binding is absent or does not match the verifier source"
        )
    expected_field = {
        "ey": 1.618033988749895,
        "ei": 1.0,
        "q": 1.618033988749895**2 + 1.0,
        "field_vel": 0.0,
    }
    _require_config("field reset", raw.get("field_reset"), expected_field)

    common = {
        "rd_global": False,
        "owns_rd": False,
        "seed": 86091,
        "box_scale": 1.0,
        "box_aspect": [1.0, 1.0, 1.0],
        "num_clusters": 1,
        "initial_radius_fraction": 0.5,
        "initial_condition": 1,
        "initial_v_circ_factor": 0.0,
        "source_strength": 0.0,
        "river_calibrate_gn": False,
        "field_attractor_init": True,
        "freeze_field": True,
        "black_holes_enabled": False,
        "bh_accretion": False,
        "dual_grid": False,
        "meshless_mode": False,
        "meshless_gravity": False,
        "gridless_physics": False,
        "rotation_stress_enabled": False,
        "effective_gravity_g_n": 1.0,
        "effective_gravity_g_eff": 1.0,
    }
    for case in raw["cases"]:
        expected = {
            **common,
            "grid_N": int(case["grid_N"]),
            "N_particles": 6,
            "dt": float(case["dt"]),
            "cluster_radius": 20.0 / 1.5,
            "gravity_mode": 3,
            "particle_merge": False,
            "effective_extents": [20.0, 20.0, 20.0],
        }
        _require_config(str(case["label"]), case.get("config"), expected)

    merge = raw["merge"]
    merge_expected = {
        **common,
        "grid_N": 64,
        "N_particles": 4,
        "dt": 1.0e-6,
        "cluster_radius": 25.0,
        "gravity_mode": 2,
        "particle_merge": True,
        "merge_cadence_steps": 1,
        "merge_virial": False,
        "effective_extents": [37.5, 37.5, 37.5],
    }
    _require_config("merge", merge.get("config"), merge_expected)


def _evaluate(
    raw: dict[str, Any],
    acquisition_sha256: str,
    *,
    require_contract: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    if raw.get("schema") != "cassi.rotation-tidal-ledger.raw.v1":
        raise ValueError("raw schema mismatch")
    if raw.get("harness_failures"):
        raise ValueError("raw harness reported failures: " + "; ".join(raw["harness_failures"]))
    if require_contract:
        _validate_receipt_contract(raw, acquisition_sha256)

    tags = raw["group_tags"]
    cloud_indices = np.asarray(tags["cloud"], dtype=np.int64)
    environment_indices = np.asarray(tags["environment"], dtype=np.int64)
    cases_raw = raw["cases"]
    cases_by_label = {str(case["label"]): case for case in cases_raw}
    if set(cases_by_label) != REQUIRED_CASES:
        raise ValueError(
            f"case set mismatch: expected {sorted(REQUIRED_CASES)}, got {sorted(cases_by_label)}"
        )
    if not all(bool(case.get("ok", False)) for case in cases_raw):
        raise ValueError("one or more tidal acquisitions are invalid")
    if not bool(raw["merge"].get("ok", False)):
        raise ValueError("merge acquisition is invalid")

    summaries = {
        label: _case_summary(case, cloud_indices, environment_indices)
        for label, case in cases_by_label.items()
    }
    merge = _merge_summary(raw["merge"])

    primary = summaries["plus_g64_dt005"]
    sphere = summaries["sphere_g64_dt005"]
    aligned = summaries["aligned_g64_dt005"]
    minus = summaries["minus_g64_dt005"]
    coarse = summaries["plus_g64_dt010"]
    fine = summaries["plus_g64_dt0025"]
    spatial = summaries["plus_g128_dt005"]

    primary_delta = np.asarray(primary["cloud_delta"])
    primary_signal = _norm(primary_delta)
    total_drift_ratio = _norm(np.asarray(primary["total_delta"])) / max(primary_signal, EPS)
    g86_pass = bool(
        primary_signal >= 1.0e-6
        and primary["cloud_closure"] <= 0.10
        and primary["environment_closure"] <= 0.10
        and primary["orbital_closure"] <= 0.10
        and total_drift_ratio <= 0.10
    )

    null_ratio = max(
        _norm(np.asarray(sphere["cloud_delta"])),
        _norm(np.asarray(aligned["cloud_delta"])),
    ) / max(primary_signal, EPS)
    g87_pass = bool(null_ratio <= 0.25)

    minus_delta = np.asarray(minus["cloud_delta"])
    plus_z = float(primary_delta[2])
    minus_z = float(minus_delta[2])
    mirror_mismatch = abs(abs(plus_z) - abs(minus_z)) / max(
        0.5 * (abs(plus_z) + abs(minus_z)), EPS
    )
    plus_transverse = _norm(primary_delta[:2]) / max(abs(plus_z), EPS)
    minus_transverse = _norm(minus_delta[:2]) / max(abs(minus_z), EPS)
    g88_pass = bool(
        plus_z * minus_z < 0.0
        and mirror_mismatch <= 0.25
        and plus_transverse <= 0.20
        and minus_transverse <= 0.20
    )

    coarse_delta = np.asarray(coarse["cloud_delta"])
    fine_delta = np.asarray(fine["cloud_delta"])
    medium_fine_difference = _relative_vector(primary_delta, fine_delta)
    coarse_medium_difference = _relative_vector(coarse_delta, primary_delta)
    g89_pass = bool(
        medium_fine_difference <= 0.10
        and coarse_medium_difference >= medium_fine_difference - 1.0e-4
        and fine["cloud_closure"] <= primary["cloud_closure"] + 0.01
    )

    spatial_delta = np.asarray(spatial["cloud_delta"])
    spatial_difference = _relative_vector(primary_delta, spatial_delta)
    g90_pass = bool(
        float(primary_delta[2]) * float(spatial_delta[2]) > 0.0
        and spatial_difference <= 0.50
    )

    g91_pass = bool(
        merge["exactly_one_pair_merged"]
        and merge["momentum_relative_error"] <= 1.0e-3
        and merge["angular_relative_error"] <= 1.0e-3
        and merge["spin_relative_error"] <= 1.0e-3
        and merge["environment_relative_state_change"] <= 1.0e-5
    )

    gates = {
        "G86": _gate(
            g86_pass,
            primary_signal=primary_signal,
            cloud_closure=primary["cloud_closure"],
            environment_closure=primary["environment_closure"],
            orbital_closure=primary["orbital_closure"],
            total_drift_over_cloud_signal=total_drift_ratio,
        ),
        "G87": _gate(g87_pass, null_over_primary=null_ratio),
        "G88": _gate(
            g88_pass,
            plus_delta_z=plus_z,
            minus_delta_z=minus_z,
            magnitude_mismatch=mirror_mismatch,
            plus_transverse_over_z=plus_transverse,
            minus_transverse_over_z=minus_transverse,
        ),
        "G89": _gate(
            g89_pass,
            medium_fine_relative_difference=medium_fine_difference,
            coarse_medium_relative_difference=coarse_medium_difference,
            medium_cloud_closure=primary["cloud_closure"],
            fine_cloud_closure=fine["cloud_closure"],
        ),
        "G90": _gate(
            g90_pass,
            grid64_delta_z=float(primary_delta[2]),
            grid128_delta_z=float(spatial_delta[2]),
            relative_vector_difference=spatial_difference,
        ),
        "G91": _gate(
            g91_pass,
            live_after=merge["live_after"],
            exactly_one_pair_merged=merge["exactly_one_pair_merged"],
            momentum_relative_error=merge["momentum_relative_error"],
            angular_relative_error=merge["angular_relative_error"],
            spin_relative_error=merge["spin_relative_error"],
            environment_relative_state_change=merge["environment_relative_state_change"],
        ),
    }
    all_pass = all(gate["pass"] for gate in gates.values())
    verdict = (
        "SUPPORTS_LIVE_TIDAL_ACQUISITION_AND_MERGE_PARTITION"
        if all_pass
        else "DOES_NOT_SUPPORT_REGISTERED_TIDAL_LEDGER"
    )
    return summaries, {"merge": merge, "gates": gates}, verdict


def main() -> int:
    hashes = {
        "raw_sha256": _sha256(RAW_PATH),
        "acquisition_source_sha256": _sha256(ACQUISITION_PATH),
        "verifier_source_sha256": _sha256(Path(__file__)),
        "preregistration_sha256": _sha256(PREREG_PATH),
        "physics_preregistration_sha256": _sha256(PHYSICS_PREREG_PATH),
    }
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    try:
        cases, evaluation, verdict = _evaluate(
            raw, hashes["acquisition_source_sha256"]
        )
        receipt: dict[str, Any] = {
            "schema": "cassi.rotation-tidal-ledger.verify.v1",
            "preregistration": str(PREREG_PATH.relative_to(ROOT)).replace("\\", "/"),
            "physics_preregistration": str(PHYSICS_PREREG_PATH.relative_to(ROOT)).replace(
                "\\", "/"
            ),
            "raw_receipt": str(RAW_PATH.relative_to(ROOT)).replace("\\", "/"),
            "hashes": hashes,
            "implementation_valid": True,
            "cases": cases,
            **evaluation,
            "verdict": verdict,
        }
        exit_code = 0 if all(gate["pass"] for gate in evaluation["gates"].values()) else 1
    except Exception as exc:  # The receipt must retain implementation failures verbatim.
        receipt = {
            "schema": "cassi.rotation-tidal-ledger.verify.v1",
            "preregistration": str(PREREG_PATH.relative_to(ROOT)).replace("\\", "/"),
            "raw_receipt": str(RAW_PATH.relative_to(ROOT)).replace("\\", "/"),
            "hashes": hashes,
            "implementation_valid": False,
            "error": f"{type(exc).__name__}: {exc}",
            "physics_preregistration": str(PHYSICS_PREREG_PATH.relative_to(ROOT)).replace(
                "\\", "/"
            ),
            "gates": {},
            "verdict": "INCONCLUSIVE—IMPLEMENTATION",
            "non_authoritative_precheck": {},
        }
        try:
            precheck_cases, precheck_evaluation, precheck_verdict = _evaluate(
                raw,
                hashes["acquisition_source_sha256"],
                require_contract=False,
            )
            receipt["non_authoritative_precheck"] = {
                "reason": "Physics replay retained for diagnosis only; receipt contract failed.",
                "cases": precheck_cases,
                **precheck_evaluation,
                "verdict_if_bound": precheck_verdict,
            }
        except Exception as precheck_exc:
            receipt["non_authoritative_precheck"] = {
                "error": f"{type(precheck_exc).__name__}: {precheck_exc}"
            }
        exit_code = 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if receipt["implementation_valid"]:
        for gate_name, gate in receipt["gates"].items():
            metrics = ", ".join(
                f"{key}={value:.6g}" if isinstance(value, float) else f"{key}={value}"
                for key, value in gate.items()
                if key != "pass"
            )
            print(f"[{('PASS' if gate['pass'] else 'FAIL')}] {gate_name}: {metrics}")
    else:
        print(f"[FAIL] implementation: {receipt['error']}")
    print(f"VERDICT: {receipt['verdict']}")
    print(f"WROTE: {OUT_PATH}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
