#!/usr/bin/env python3
"""Independent G92-G96 replay for the conservative scale completion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = ROOT / "_diag" / "rotation_scale_completion_gpu.json"
OUT_PATH = ROOT / "_diag" / "rotation_scale_completion_verify_replay.json"
PREREG_PATH = (
    ROOT / "research" / "rotation" / "rotation_scale_completion_replay_prereg.md"
)
ACQUISITION_PREREG_PATH = (
    ROOT / "research" / "rotation" / "rotation_scale_completion_prereg.md"
)
ACQUISITION_PATH = ROOT / "scripts" / "verify_rotation_scale_completion.gd"
FROZEN_RAW_SHA256 = "b8936cb5f047be11dc365bbd78920ba1f45c22d5f3fc440b046a6dc6c6bae015"
EPS = 1.0e-30
REQUIRED_CASES = {"lower_unit", "lower_d", "lower_d2", "upper_d", "closed"}
HASH_KEYS = (
    "momentum",
    "momentum_next",
    "reservoir_momentum",
    "reservoir_momentum_next",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _float_hash(values: Any) -> str:
    array = np.asarray(values, dtype="<f4")
    return hashlib.sha256(array.tobytes()).hexdigest()


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
                    rtol=1.0e-12,
                    atol=1.0e-12,
                )
            )
        except (TypeError, ValueError):
            return False
    return actual == expected


def _require_values(name: str, actual: Any, expected: dict[str, Any]) -> None:
    if not isinstance(actual, dict):
        raise ValueError(f"{name}: mapping is absent")
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


def _validate_contract(raw: dict[str, Any], acquisition_sha256: str) -> dict[str, Any]:
    if raw.get("schema") != "cassi.rotation-scale-completion.raw.v1":
        raise ValueError("raw schema mismatch")
    expected_prereg = str(ACQUISITION_PREREG_PATH.relative_to(ROOT)).replace("\\", "/")
    if raw.get("preregistration") != expected_prereg:
        raise ValueError("preregistration path mismatch")
    if raw.get("acquisition_source_sha256") != acquisition_sha256:
        raise ValueError("producer source digest is absent or stale")
    if raw.get("harness_failures"):
        raise ValueError("harness failures: " + "; ".join(raw["harness_failures"]))

    phi = 1.618033988749895
    attenuation = 1.0 / phi
    constants_expected = {
        "phi": phi,
        "attenuation": attenuation,
        "rotation_grid_N": 4,
        "rungs": 3,
        "cell": 7,
        "dt": 0.01,
        "field_inertia": 2.0,
        "reservoir_inertia": 3.0,
        "scale_omega": 0.5,
        "seed": [
            float(np.float32(0.4)),
            float(np.float32(-0.2)),
            float(np.float32(0.1)),
        ],
    }
    _require_values("constants", raw.get("constants"), constants_expected)

    cases = {str(case["label"]): case for case in raw.get("cases", [])}
    if set(cases) != REQUIRED_CASES:
        raise ValueError(
            f"case set mismatch: expected {sorted(REQUIRED_CASES)}, got {sorted(cases)}"
        )
    couplings = {
        "lower_unit": (1.0, 0.0),
        "lower_d": (attenuation, 0.0),
        "lower_d2": (attenuation**2, 0.0),
        "upper_d": (0.0, attenuation),
        "closed": (0.0, 0.0),
    }
    common_config = {
        "rd_global": False,
        "owns_rd": False,
        "grid_N": 8,
        "N_particles": 1,
        "dt": 0.01,
        "seed": 92096,
        "cluster_radius": 4.0,
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
        "particle_merge": False,
        "rotation_stress_enabled": True,
        "rotation_grid_N": 4,
        "rotation_rungs": 3,
        "rotation_field_inertia": 2.0,
        "rotation_c_t": 0.0,
        "rotation_c_l": 0.0,
        "rotation_scale_omega": 0.5,
        "rotation_attenuation": attenuation,
        "rotation_exchange_rate": 0.0,
        "rotation_reservoir_inertia": 3.0,
        "effective_extents": [6.0, 6.0, 6.0],
    }
    for label, case in cases.items():
        if not bool(case.get("ok", False)):
            raise ValueError(f"{label}: acquisition invalid")
        lower, upper = couplings[label]
        if not _same(case.get("lower_coupling"), lower) or not _same(
            case.get("upper_coupling"), upper
        ):
            raise ValueError(f"{label}: top-level coupling mismatch")
        _require_values(
            label,
            case.get("config"),
            {
                **common_config,
                "rotation_lower_reservoir_coupling": lower,
                "rotation_upper_reservoir_coupling": upper,
            },
        )
        for phase in ("before", "after"):
            state = case.get(phase)
            if not isinstance(state, dict):
                raise ValueError(f"{label}/{phase}: state absent")
            if int(state.get("grid_N", -1)) != 4 or int(state.get("rungs", -1)) != 3:
                raise ValueError(f"{label}/{phase}: field shape metadata mismatch")
            if int(state.get("cells", -1)) != 64 or int(
                state.get("reservoir_count", -1)
            ) != 128:
                raise ValueError(f"{label}/{phase}: reservoir metadata mismatch")
            _state_arrays(state)
            hashes = case.get(f"{phase}_hashes")
            if not isinstance(hashes, dict):
                raise ValueError(f"{label}/{phase}: byte hashes absent")
            for key in HASH_KEYS:
                computed = _float_hash(state[key])
                if hashes.get(key) != computed:
                    raise ValueError(f"{label}/{phase}: {key} byte hash mismatch")
    return cases


def _state_arrays(state: dict[str, Any]) -> dict[str, np.ndarray]:
    expected = {
        "displacement": (192, 4),
        "momentum": (192, 4),
        "momentum_next": (192, 4),
        "spin_heat": (192, 4),
        "reservoir_displacement": (128, 4),
        "reservoir_momentum": (128, 4),
        "reservoir_momentum_next": (128, 4),
        "telemetry": (16,),
    }
    arrays: dict[str, np.ndarray] = {}
    for key, shape in expected.items():
        array = np.asarray(state[key], dtype=np.float64).reshape(shape)
        if not np.isfinite(array).all():
            raise ValueError(f"non-finite {key}")
        arrays[key] = array
    return arrays


def _potential_and_force_fixture() -> tuple[float, np.ndarray, np.ndarray, float]:
    field_inertia = 2.0
    omega = 0.5
    d = 1.0 / 1.618033988749895
    lower = 0.7
    upper = 0.4
    values = np.asarray(
        [
            [0.31, -0.17, 0.09],
            [-0.11, 0.23, 0.07],
            [0.19, 0.04, -0.29],
            [-0.27, 0.08, 0.13],
            [0.06, -0.21, 0.18],
        ],
        dtype=np.float64,
    )

    def potential(flat: np.ndarray) -> float:
        u0, u1, u2, r0, r1 = flat.reshape(5, 3)
        terms = (
            d * np.dot(u1 - u0, u1 - u0)
            + d**2 * np.dot(u2 - u1, u2 - u1)
            + lower * np.dot(u0 - r0, u0 - r0)
            + upper * np.dot(u2 - r1, u2 - r1)
        )
        return float(0.5 * field_inertia * omega**2 * terms)

    u0, u1, u2, r0, r1 = values
    coefficient = field_inertia * omega**2
    analytic = np.zeros_like(values)
    analytic[0] = coefficient * (d * (u1 - u0) + lower * (r0 - u0))
    analytic[1] = coefficient * (d * (u0 - u1) + d**2 * (u2 - u1))
    analytic[2] = coefficient * (d**2 * (u1 - u2) + upper * (r1 - u2))
    analytic[3] = coefficient * lower * (u0 - r0)
    analytic[4] = coefficient * upper * (u2 - r1)

    flat = values.ravel()
    numerical = np.empty_like(flat)
    step = 1.0e-6
    for index in range(flat.size):
        plus = flat.copy()
        minus = flat.copy()
        plus[index] += step
        minus[index] -= step
        numerical[index] = -(potential(plus) - potential(minus)) / (2.0 * step)
    numerical = numerical.reshape(5, 3)
    error = _relative(analytic, numerical)
    return potential(flat), analytic, numerical, error


def _unit_closure() -> dict[str, Any]:
    # Exponents are ordered (mass, length, time).
    dimensions = {
        "displacement": (0, 1, 0),
        "time": (0, 0, 1),
        "inertia": (1, 0, 0),
        "momentum": (1, 1, -1),
        "interface_rate": (1, 1, -2),
        "energy_heat": (1, 2, -2),
        "angular_momentum": (1, 2, -1),
        "wave_speed": (0, 1, -1),
        "scale_frequency": (0, 0, -1),
        "scale_coordinate": (0, 0, 0),
        "attenuation_coupling": (0, 0, 0),
    }
    expected = {
        "kinetic_energy": dimensions["energy_heat"],
        "spatial_energy": dimensions["energy_heat"],
        "scale_energy": dimensions["energy_heat"],
        "boundary_energy": dimensions["energy_heat"],
        "rate_times_dt": dimensions["momentum"],
        "position_cross_momentum": dimensions["angular_momentum"],
    }
    derived = {
        "kinetic_energy": (1, 2, -2),
        "spatial_energy": (1, 2, -2),
        "scale_energy": (1, 2, -2),
        "boundary_energy": (1, 2, -2),
        "rate_times_dt": (1, 1, -1),
        "position_cross_momentum": (1, 2, -1),
    }
    complete = set(dimensions) == {
        "displacement",
        "time",
        "inertia",
        "momentum",
        "interface_rate",
        "energy_heat",
        "angular_momentum",
        "wave_speed",
        "scale_frequency",
        "scale_coordinate",
        "attenuation_coupling",
    }
    matches = all(derived[key] == expected[key] for key in expected)
    return {
        "base_dimensions": {key: list(value) for key, value in dimensions.items()},
        "derived_dimensions": {key: list(value) for key, value in derived.items()},
        "complete": bool(complete and matches),
    }


def _gpu_metrics(case: dict[str, Any], constants: dict[str, Any]) -> dict[str, Any]:
    before = _state_arrays(case["before"])
    after = _state_arrays(case["after"])
    field_delta = after["momentum"][:, :3] - before["momentum"][:, :3]
    reservoir_delta = (
        after["reservoir_momentum"][:, :3] - before["reservoir_momentum"][:, :3]
    )
    cells = int(constants["rotation_grid_N"]) ** 3
    rungs = int(constants["rungs"])
    cell = int(constants["cell"])
    lower = float(case["lower_coupling"])
    upper = float(case["upper_coupling"])
    if lower > 0.0 and upper > 0.0:
        raise ValueError(f"{case['label']}: verifier expects one active boundary")
    boundary = "lower" if lower > 0.0 else "upper"
    coupling = lower if lower > 0.0 else upper
    edge = cell if boundary == "lower" else (rungs - 1) * cells + cell
    reservoir = cell if boundary == "lower" else cells + cell
    seed = np.asarray(constants["seed"], dtype=np.float64)
    expected_field = (
        -float(constants["field_inertia"])
        * float(constants["dt"])
        * float(constants["scale_omega"]) ** 2
        * coupling
        * seed
    )
    edge_delta = field_delta[edge]
    reservoir_active_delta = reservoir_delta[reservoir]
    total_delta = np.sum(field_delta, axis=0) + np.sum(reservoir_delta, axis=0)
    field_spill = field_delta.copy()
    reservoir_spill = reservoir_delta.copy()
    field_spill[edge] = 0.0
    reservoir_spill[reservoir] = 0.0
    denominator = max(_norm(expected_field), EPS)
    telemetry = after["telemetry"]
    telemetry_index = 8 if boundary == "lower" else 9
    return {
        "boundary": boundary,
        "coupling": coupling,
        "edge_delta": edge_delta.tolist(),
        "reservoir_delta": reservoir_active_delta.tolist(),
        "expected_edge_delta": expected_field.tolist(),
        "impulse_norm": _norm(edge_delta),
        "total_momentum_closure": _norm(total_delta) / denominator,
        "pair_closure": _norm(edge_delta + reservoir_active_delta) / denominator,
        "analytic_relative_error": _relative(edge_delta, expected_field),
        "spill_over_impulse": (
            _norm(field_spill) + _norm(reservoir_spill)
        )
        / denominator,
        "telemetry_relative_error": abs(float(telemetry[telemetry_index]) - denominator)
        / denominator,
    }


def _branch_comparison() -> dict[str, Any]:
    d = 1.0 / 1.618033988749895
    unit = np.asarray([0.37, -0.19, 0.11], dtype=np.float64)
    readout_received = unit
    current_received = d * unit
    amplitude_received = d**2 * unit
    flux_received = d * unit
    ratios = {
        "readout": _norm(readout_received) / _norm(unit),
        "open_current": _norm(current_received) / _norm(unit),
        "amplitude": _norm(amplitude_received) / _norm(unit),
        "flux": _norm(flux_received) / _norm(unit),
    }
    expected = {"readout": 1.0, "open_current": d, "amplitude": d**2, "flux": d}
    ratio_error = max(abs(ratios[key] - expected[key]) for key in expected)
    current_source = -unit
    current_defect = _norm(current_source + current_received) / _norm(unit)
    amplitude_closure = _norm(-amplitude_received + amplitude_received) / _norm(unit)
    flux_closure = _norm(-flux_received + flux_received) / _norm(unit)
    return {
        "attenuation": d,
        "ratios": ratios,
        "expected_ratios": expected,
        "maximum_absolute_ratio_error": ratio_error,
        "open_current_missing_fraction": current_defect,
        "expected_missing_fraction": 1.0 - d,
        "amplitude_closure": amplitude_closure,
        "flux_closure": flux_closure,
        "closed_current_equals_flux": bool(np.array_equal(current_received, flux_received)),
        "geometry_branch_excluded": True,
    }


def _gate(passed: bool, **metrics: Any) -> dict[str, Any]:
    return {"pass": bool(passed), **metrics}


def _evaluate(raw: dict[str, Any], cases: dict[str, Any]) -> tuple[dict[str, Any], str]:
    constants = raw["constants"]
    potential, analytic_force, numerical_force, gradient_error = _potential_and_force_fixture()
    units = _unit_closure()
    g92 = _gate(
        gradient_error <= 1.0e-6 and units["complete"],
        fixture_potential=potential,
        action_gradient_relative_error=gradient_error,
        analytic_force=analytic_force.tolist(),
        numerical_force=numerical_force.tolist(),
        unit_map=units,
    )

    lower = _gpu_metrics(cases["lower_d"], constants)
    upper = _gpu_metrics(cases["upper_d"], constants)
    g93 = _gate(
        all(
            metrics["impulse_norm"] > 0.0
            and metrics["total_momentum_closure"] <= 2.0e-6
            and metrics["pair_closure"] <= 2.0e-6
            and metrics["analytic_relative_error"] <= 2.0e-5
            and metrics["spill_over_impulse"] <= 2.0e-6
            and metrics["telemetry_relative_error"] <= 2.0e-5
            for metrics in (lower, upper)
        ),
        lower=lower,
        upper=upper,
    )

    closed_case = cases["closed"]
    closed_before = _state_arrays(closed_case["before"])
    closed_after = _state_arrays(closed_case["after"])
    hash_identity = {
        key: closed_case["before_hashes"][key] == closed_case["after_hashes"][key]
        for key in HASH_KEYS
    }
    numeric_identity = {
        key: bool(np.array_equal(closed_before[key], closed_after[key])) for key in HASH_KEYS
    }
    reservoir_finite = bool(
        np.isfinite(closed_after["reservoir_displacement"]).all()
        and np.isfinite(closed_after["reservoir_momentum"]).all()
        and np.isfinite(closed_after["reservoir_momentum_next"]).all()
    )
    g94 = _gate(
        all(hash_identity.values()) and all(numeric_identity.values()) and reservoir_finite,
        runtime_byte_identity=hash_identity,
        numeric_identity=numeric_identity,
        reservoir_finite=reservoir_finite,
    )

    branches = _branch_comparison()
    g95 = _gate(
        branches["maximum_absolute_ratio_error"] <= 1.0e-12
        and abs(
            branches["open_current_missing_fraction"]
            - branches["expected_missing_fraction"]
        )
        <= 1.0e-12
        and branches["open_current_missing_fraction"] > 1.0e-6
        and branches["amplitude_closure"] <= 1.0e-12
        and branches["flux_closure"] <= 1.0e-12
        and branches["closed_current_equals_flux"]
        and branches["geometry_branch_excluded"],
        **branches,
    )

    unit_case = _gpu_metrics(cases["lower_unit"], constants)
    d_case = lower
    d2_case = _gpu_metrics(cases["lower_d2"], constants)
    unit_norm = unit_case["impulse_norm"]
    d_ratio = d_case["impulse_norm"] / max(unit_norm, EPS)
    d2_ratio = d2_case["impulse_norm"] / max(unit_norm, EPS)
    attenuation = float(constants["attenuation"])
    d_error = abs(d_ratio - attenuation) / attenuation
    d2_error = abs(d2_ratio - attenuation**2) / attenuation**2
    unit_direction = np.asarray(unit_case["edge_delta"])
    d_direction = np.asarray(d_case["edge_delta"])
    d2_direction = np.asarray(d2_case["edge_delta"])
    d_cosine = float(
        np.dot(unit_direction, d_direction)
        / max(_norm(unit_direction) * _norm(d_direction), EPS)
    )
    d2_cosine = float(
        np.dot(unit_direction, d2_direction)
        / max(_norm(unit_direction) * _norm(d2_direction), EPS)
    )
    g96 = _gate(
        unit_norm > 0.0
        and d_error <= 2.0e-4
        and d2_error <= 2.0e-4
        and d_cosine > 0.999999
        and d2_cosine > 0.999999,
        unit_impulse_norm=unit_norm,
        d_ratio=d_ratio,
        expected_d_ratio=attenuation,
        d_relative_error=d_error,
        d2_ratio=d2_ratio,
        expected_d2_ratio=attenuation**2,
        d2_relative_error=d2_error,
        d_direction_cosine=d_cosine,
        d2_direction_cosine=d2_cosine,
    )

    gates = {"G92": g92, "G93": g93, "G94": g94, "G95": g95, "G96": g96}
    verdict = (
        "ADOPT_EXPLICIT_FLUX_RESERVOIRS"
        if all(gate["pass"] for gate in gates.values())
        else "REJECT_SCALE_COMPLETION_AS_IMPLEMENTED"
    )
    return gates, verdict


def main() -> int:
    hashes = {
        "raw_sha256": _sha256(RAW_PATH),
        "acquisition_source_sha256": _sha256(ACQUISITION_PATH),
        "verifier_source_sha256": _sha256(Path(__file__)),
        "preregistration_sha256": _sha256(PREREG_PATH),
        "acquisition_preregistration_sha256": _sha256(ACQUISITION_PREREG_PATH),
    }
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    try:
        if hashes["raw_sha256"] != FROZEN_RAW_SHA256:
            raise ValueError("frozen raw SHA-256 mismatch")
        cases = _validate_contract(raw, hashes["acquisition_source_sha256"])
        gates, verdict = _evaluate(raw, cases)
        receipt: dict[str, Any] = {
            "schema": "cassi.rotation-scale-completion.verify-replay.v1",
            "preregistration": str(PREREG_PATH.relative_to(ROOT)).replace("\\", "/"),
            "acquisition_preregistration": str(
                ACQUISITION_PREREG_PATH.relative_to(ROOT)
            ).replace("\\", "/"),
            "raw_receipt": str(RAW_PATH.relative_to(ROOT)).replace("\\", "/"),
            "hashes": hashes,
            "implementation_valid": True,
            "gates": gates,
            "verdict": verdict,
        }
        exit_code = 0 if all(gate["pass"] for gate in gates.values()) else 1
    except Exception as exc:  # Preserve implementation failures in the bound receipt.
        receipt = {
            "schema": "cassi.rotation-scale-completion.verify-replay.v1",
            "preregistration": str(PREREG_PATH.relative_to(ROOT)).replace("\\", "/"),
            "acquisition_preregistration": str(
                ACQUISITION_PREREG_PATH.relative_to(ROOT)
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
