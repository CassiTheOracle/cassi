#!/usr/bin/env python
"""Replay G75-G82 from exact raw rotation-stress state receipts."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
REFERENCE_REL_TOL = 1.0e-12
REFERENCE_ABS_TOL = 1.0e-12
GPU_REL_TOL = 1.0e-5
GPU_ABS_TOL = 1.0e-6
CONTRACT_KEYS = ("pos", "pvel", "acc", "ey", "ei", "q")
FIELD_KEYS = ("displacement", "momentum", "momentum_next", "spin_heat")


def load(path: str, schema: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != schema:
        raise ValueError(f"{path}: expected schema {schema!r}, got {data.get('schema')!r}")
    return data


def finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def decode_receipt(receipt: Any, name: str) -> np.ndarray:
    if not isinstance(receipt, dict):
        raise ValueError(f"{name}: receipt must be an object")
    dtype_name = receipt.get("dtype")
    if dtype_name not in ("<f4", "<f8"):
        raise ValueError(f"{name}: unsupported dtype {dtype_name!r}")
    shape = receipt.get("shape")
    if not isinstance(shape, list) or any(
        not isinstance(size, int) or isinstance(size, bool) or size < 0 for size in shape
    ):
        raise ValueError(f"{name}: invalid shape {shape!r}")
    encoded = receipt.get("base64")
    if not isinstance(encoded, str):
        raise ValueError(f"{name}: base64 payload must be a string")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"{name}: invalid base64 payload") from exc
    dtype = np.dtype(dtype_name)
    expected_bytes = math.prod(shape) * dtype.itemsize
    if len(payload) != expected_bytes:
        raise ValueError(
            f"{name}: byte length {len(payload)} does not match "
            f"{shape} × {dtype.itemsize} = {expected_bytes}"
        )
    return np.frombuffer(payload, dtype=dtype).reshape(shape)


def decode_group(group: Any, name: str) -> dict[str, np.ndarray]:
    if not isinstance(group, dict):
        raise ValueError(f"{name}: receipt group must be an object")
    return {
        key: decode_receipt(receipt, f"{name}.{key}")
        for key, receipt in group.items()
    }


def require_shape(
    array: np.ndarray,
    shape: tuple[int, ...],
    name: str,
    dtype: str,
) -> None:
    if array.shape != shape:
        raise ValueError(f"{name}: expected shape {shape}, got {array.shape}")
    if array.dtype.str != dtype:
        raise ValueError(f"{name}: expected dtype {dtype}, got {array.dtype.str}")


def require_parameters(
    data: dict[str, Any],
    expected: dict[str, int | float | list[float]],
    label: str,
) -> dict[str, Any]:
    parameters = data.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError(f"{label}: missing parameters")
    for key, frozen in expected.items():
        actual = parameters.get(key)
        if isinstance(frozen, list):
            if (
                not isinstance(actual, list)
                or len(actual) != len(frozen)
                or any(
                    not finite_number(item)
                    or not math.isclose(
                        float(item), wanted, rel_tol=0.0, abs_tol=1.0e-15
                    )
                    for item, wanted in zip(actual, frozen, strict=True)
                )
            ):
                raise ValueError(f"{label}: parameter {key!r} is not frozen value {frozen}")
        elif isinstance(frozen, int):
            if not isinstance(actual, int) or isinstance(actual, bool) or actual != frozen:
                raise ValueError(f"{label}: parameter {key!r} is not frozen value {frozen}")
        elif (
            not finite_number(actual)
            or not math.isclose(
                float(actual), frozen, rel_tol=0.0, abs_tol=1.0e-15
            )
        ):
            raise ValueError(f"{label}: parameter {key!r} is not frozen value {frozen}")
    return parameters


def relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(expected)), 1.0e-30)
    return float(np.linalg.norm(actual - expected) / denominator)


def cell_centers(n: int, extents: np.ndarray) -> np.ndarray:
    axes = [
        -extent + (np.arange(n, dtype=np.float64) + 0.5) * (2.0 * extent / n)
        for extent in extents
    ]
    return np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1)


def particle_angular(
    positions: np.ndarray,
    velocities: np.ndarray,
    masses: np.ndarray,
) -> np.ndarray:
    momenta = masses[:, None] * velocities
    return np.sum(np.cross(positions, momenta), axis=0, dtype=np.float64)


def ledger(
    positions: np.ndarray,
    velocities: np.ndarray,
    masses: np.ndarray,
    momentum: np.ndarray,
    spin: np.ndarray,
    extents: np.ndarray,
    *,
    include_spin: bool,
) -> tuple[np.ndarray, np.ndarray]:
    alive = masses > 0.0
    particle_momenta = (
        masses[alive, None].astype(np.float64)
        * velocities[alive, :3].astype(np.float64)
    )
    total_p = np.sum(particle_momenta, axis=0, dtype=np.float64)
    total_l = np.sum(
        np.cross(positions[alive, :3].astype(np.float64), particle_momenta),
        axis=0,
        dtype=np.float64,
    )

    field_momenta = momentum[..., :3].astype(np.float64)
    total_p += np.sum(field_momenta, axis=(0, 1, 2, 3), dtype=np.float64)
    centers = cell_centers(momentum.shape[1], extents)
    total_l += np.sum(
        np.cross(centers[None, ...], field_momenta),
        axis=(0, 1, 2, 3),
        dtype=np.float64,
    )
    if include_spin:
        total_l += np.sum(
            spin[..., :3].astype(np.float64),
            axis=(0, 1, 2, 3),
            dtype=np.float64,
        )
    return total_p, total_l


def arrays_finite(arrays: Any) -> bool:
    return all(bool(np.all(np.isfinite(array))) for array in arrays)


def metrics_match(
    reported: dict[str, Any],
    recomputed: dict[str, float | bool],
    *,
    rel_tol: float,
    abs_tol: float,
) -> bool:
    for key, expected in recomputed.items():
        actual = reported.get(key)
        if isinstance(expected, bool):
            if not isinstance(actual, bool) or actual is not expected:
                return False
        elif (
            not finite_number(actual)
            or not math.isfinite(float(expected))
            or not math.isclose(
                float(actual), float(expected), rel_tol=rel_tol, abs_tol=abs_tol
            )
        ):
            return False
    return True


def audit(
    reported: dict[str, Any],
    metrics: dict[str, float | bool],
    threshold_pass: bool,
    *,
    rel_tol: float,
    abs_tol: float,
) -> dict[str, Any]:
    consistent = metrics_match(
        reported, metrics, rel_tol=rel_tol, abs_tol=abs_tol
    )
    if "pass" in reported:
        consistent = (
            consistent
            and isinstance(reported["pass"], bool)
            and reported["pass"] is threshold_pass
        )
    return {
        "pass": threshold_pass and consistent,
        "threshold_pass": threshold_pass,
        "producer_consistent": consistent,
        "metrics": metrics,
    }


def verify_reference(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    frozen = {
        "grid_n": 4,
        "rungs": 3,
        "dt": 0.01,
        "extents": [2.0, 2.0, 2.0],
        "field_inertia": 2.0,
        "c_t": 0.4,
        "c_l": 0.7,
        "scale_omega": 0.5,
        "attenuation": 1.0 / PHI,
        "exchange_rate": 1.5,
    }
    parameters = require_parameters(data, frozen, "reference")
    n = int(parameters["grid_n"])
    rungs = int(parameters["rungs"])
    dt = float(parameters["dt"])
    extents = np.asarray(parameters["extents"], dtype=np.float64)
    field_inertia = float(parameters["field_inertia"])
    attenuation = float(parameters["attenuation"])
    gates = data["gates"]
    receipts = data["receipts"]
    results: dict[str, dict[str, Any]] = {}

    g75 = decode_group(receipts["G75"], "reference.G75")
    g75_shapes = {
        "positions": (4, 3),
        "masses": (4,),
        "velocities_before": (4, 3),
        "accelerations": (4, 3),
        "positions_after": (4, 3),
        "velocities_after": (4, 3),
        "mirror": (3, 3),
        "mirrored_positions_after": (4, 3),
        "mirrored_velocities_after": (4, 3),
        "aligned_positions_after": (4, 3),
        "aligned_velocities_after": (4, 3),
        "aligned_masses": (4,),
    }
    for key, shape in g75_shapes.items():
        require_shape(g75[key], shape, f"reference.G75.{key}", "<f8")
    torque = np.sum(
        np.cross(
            g75["positions"],
            g75["masses"][:, None] * g75["accelerations"],
        ),
        axis=0,
        dtype=np.float64,
    )
    before_l = particle_angular(
        g75["positions"], g75["velocities_before"], g75["masses"]
    )
    after_l = particle_angular(
        g75["positions_after"], g75["velocities_after"], g75["masses"]
    )
    mirrored_l = particle_angular(
        g75["mirrored_positions_after"],
        g75["mirrored_velocities_after"],
        g75["masses"],
    )
    mirrored_expected = (
        np.linalg.det(g75["mirror"]) * g75["mirror"] @ after_l
    )
    aligned_l = particle_angular(
        g75["aligned_positions_after"],
        g75["aligned_velocities_after"],
        g75["aligned_masses"],
    )
    g75_metrics: dict[str, float | bool] = {
        "tidal_relative_error": relative_error(after_l - before_l, dt * torque),
        "mirror_relative_error": relative_error(mirrored_l, mirrored_expected),
        "null_absolute_change": float(np.linalg.norm(aligned_l)),
    }
    g75_pass = (
        arrays_finite(g75.values())
        and g75_metrics["tidal_relative_error"] <= 1.0e-10
        and g75_metrics["mirror_relative_error"] <= 1.0e-10
        and g75_metrics["null_absolute_change"] <= 1.0e-12
    )
    results["G75"] = audit(
        gates["G75"],
        g75_metrics,
        bool(g75_pass),
        rel_tol=REFERENCE_REL_TOL,
        abs_tol=REFERENCE_ABS_TOL,
    )

    g76 = decode_group(receipts["G76"], "reference.G76")
    field_shape3 = (rungs, n, n, n, 3)
    heat_shape = (rungs, n, n, n)
    g76_shapes = {
        "positions": (4, 3),
        "masses": (4,),
        "velocities_before": (4, 3),
        "momentum_before": field_shape3,
        "spin_before": field_shape3,
        "heat_before": heat_shape,
        "velocities_after": (4, 3),
        "momentum_after": field_shape3,
        "spin_after": field_shape3,
        "heat_after": heat_shape,
    }
    for key, shape in g76_shapes.items():
        require_shape(g76[key], shape, f"reference.G76.{key}", "<f8")
    before_p, before_l = ledger(
        g76["positions"],
        g76["velocities_before"],
        g76["masses"],
        g76["momentum_before"],
        g76["spin_before"],
        extents,
        include_spin=True,
    )
    after_p, after_l = ledger(
        g76["positions"],
        g76["velocities_after"],
        g76["masses"],
        g76["momentum_after"],
        g76["spin_after"],
        extents,
        include_spin=True,
    )
    _, after_without_spin_l = ledger(
        g76["positions"],
        g76["velocities_after"],
        g76["masses"],
        g76["momentum_after"],
        g76["spin_after"],
        extents,
        include_spin=False,
    )
    linear_error = relative_error(after_p, before_p)
    angular_error = relative_error(after_l, before_l)
    without_spin_error = relative_error(after_without_spin_l, before_l)
    heat_increment = float(np.sum(g76["heat_after"] - g76["heat_before"]))
    separation = without_spin_error / max(angular_error, 1.0e-30)
    g76_metrics = {
        "linear_relative_error": linear_error,
        "angular_relative_error": angular_error,
        "without_spin_relative_error": without_spin_error,
        "spin_error_separation": separation,
        "heat_increment": heat_increment,
    }
    g76_pass = (
        arrays_finite(g76.values())
        and linear_error <= 1.0e-12
        and angular_error <= 1.0e-12
        and heat_increment >= 0.0
        and separation >= 1.0e4
    )
    results["G76"] = audit(
        gates["G76"],
        g76_metrics,
        bool(g76_pass),
        rel_tol=REFERENCE_REL_TOL,
        abs_tol=REFERENCE_ABS_TOL,
    )

    g77 = decode_group(receipts["G77"], "reference.G77")
    g77_shapes = {
        "scale_attenuated": field_shape3,
        "scale_unit": field_shape3,
        "scale_zero": field_shape3,
        "scale_equal": field_shape3,
        "displacement_after_64": field_shape3,
        "momentum_after_64": field_shape3,
        "spin_after_64": field_shape3,
        "heat_after_64": heat_shape,
        "velocities_after_64": (2, 3),
    }
    for key, shape in g77_shapes.items():
        require_shape(g77[key], shape, f"reference.G77.{key}", "<f8")
    impulse_attenuated = field_inertia * dt * g77["scale_attenuated"][0]
    impulse_unit = field_inertia * dt * g77["scale_unit"][0]
    unit_norm = float(np.linalg.norm(impulse_unit))
    attenuation_ratio = (
        float(np.linalg.norm(impulse_attenuated)) / unit_norm
        if unit_norm > 0.0
        else math.inf
    )
    attenuation_error = abs(attenuation_ratio - attenuation) / attenuation
    summed_scale = float(
        np.linalg.norm(
            np.sum(
                g77["scale_attenuated"],
                axis=(0, 1, 2, 3),
                dtype=np.float64,
            )
        )
    )
    null_max = max(
        float(np.max(np.abs(g77["scale_zero"]))),
        float(np.max(np.abs(g77["scale_equal"]))),
    )
    final_arrays = (
        g77["displacement_after_64"],
        g77["momentum_after_64"],
        g77["spin_after_64"],
        g77["heat_after_64"],
        g77["velocities_after_64"],
    )
    finite_64 = arrays_finite(final_arrays)
    g77_metrics = {
        "summed_scale_momentum_norm": summed_scale,
        "attenuation_ratio": attenuation_ratio,
        "attenuation_relative_error": attenuation_error,
        "null_max_abs": null_max,
        "finite_64_steps": finite_64,
        "heat_after_64_steps": float(np.sum(g77["heat_after_64"])),
    }
    g77_pass = (
        summed_scale <= 1.0e-12
        and attenuation_error <= 1.0e-12
        and null_max <= 1.0e-12
        and finite_64
    )
    results["G77"] = audit(
        gates["G77"],
        g77_metrics,
        bool(g77_pass),
        rel_tol=REFERENCE_REL_TOL,
        abs_tol=REFERENCE_ABS_TOL,
    )

    expected_verdict = (
        "PASS" if all(result["threshold_pass"] for result in results.values()) else "FAIL"
    )
    if data.get("verdict") != expected_verdict:
        raise ValueError(
            f"reference: producer verdict {data.get('verdict')!r} "
            f"does not match replay {expected_verdict!r}"
        )
    return results


def decode_gpu_state(
    group: Any,
    name: str,
    *,
    n: int,
    rungs: int,
    particles: int,
    include_particles: bool,
) -> dict[str, np.ndarray]:
    state = decode_group(group, name)
    field_shape = (rungs, n, n, n, 4)
    for key in FIELD_KEYS:
        require_shape(state[key], field_shape, f"{name}.{key}", "<f4")
    require_shape(state["orientation"], (particles, 4), f"{name}.orientation", "<f4")
    require_shape(state["telemetry"], (16,), f"{name}.telemetry", "<f4")
    if include_particles:
        for key in ("pos", "vel", "merge_spin"):
            require_shape(state[key], (particles, 4), f"{name}.{key}", "<f4")
    return state


def gpu_cross(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.array(
        [
            np.float32(a[1] * b[2] - a[2] * b[1]),
            np.float32(a[2] * b[0] - a[0] * b[2]),
            np.float32(a[0] * b[1] - a[1] * b[0]),
        ],
        dtype=np.float32,
    )


def gpu_length(vector: np.ndarray) -> float:
    values = vector.astype(np.float32, copy=False)
    squared = np.float32(values[0] * values[0] + values[1] * values[1])
    squared = np.float32(squared + values[2] * values[2])
    return float(np.sqrt(squared))


def gpu_relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
    delta = np.asarray(actual - expected, dtype=np.float32)
    return gpu_length(delta) / max(gpu_length(expected), 1.0e-30)


def gpu_ledger(
    state: dict[str, np.ndarray],
    extents: np.ndarray,
    *,
    include_spin: bool,
) -> tuple[np.ndarray, np.ndarray]:
    # Replay Godot's sequential float32 Vector3 ledger. A float64/vectorized
    # reduction changes the roundoff denominator of the deliberately sensitive
    # G80 spin-separation diagnostic even though both ledgers pass its threshold.
    total_p = np.zeros(3, dtype=np.float32)
    total_l = np.zeros(3, dtype=np.float32)
    positions = state["pos"]
    velocities = state["vel"]
    for particle in range(positions.shape[0]):
        mass = np.float32(positions[particle, 3])
        if mass <= 0.0:
            continue
        particle_p = np.asarray(mass * velocities[particle, :3], dtype=np.float32)
        total_p += particle_p
        total_l += gpu_cross(positions[particle, :3], particle_p)

    n = state["momentum"].shape[1]
    cells = n * n * n
    field_momentum = state["momentum"].reshape(-1, 4)
    spin_heat = state["spin_heat"].reshape(-1, 4)
    for field_index in range(field_momentum.shape[0]):
        field_p = field_momentum[field_index, :3]
        total_p += field_p
        cell = field_index % cells
        x = cell // (n * n)
        remainder = cell - x * n * n
        y = remainder // n
        z = remainder - y * n
        center = np.array(
            [
                -extents[0] + (x + 0.5) * (2.0 * extents[0] / n),
                -extents[1] + (y + 0.5) * (2.0 * extents[1] / n),
                -extents[2] + (z + 0.5) * (2.0 * extents[2] / n),
            ],
            dtype=np.float32,
        )
        total_l += gpu_cross(center, field_p)
        if include_spin:
            total_l += spin_heat[field_index, :3]
    return total_p, total_l


def gpu_heat(state: dict[str, np.ndarray]) -> float:
    return float(np.sum(state["spin_heat"][..., 3], dtype=np.float64))


def verify_gpu(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    frozen = {
        "grid_n": 4,
        "rungs": 3,
        "particle_count": 8,
        "workbench_grid_n": 64,
        "dt": 0.01,
        "extents": [2.0, 2.0, 2.0],
        "field_inertia": 2.0,
        "c_t": 0.4,
        "c_l": 0.7,
        "scale_omega": 0.5,
        "exchange_rate": 1.5,
        "attenuation": 1.0 / PHI,
    }
    parameters = require_parameters(data, frozen, "gpu")
    n = int(parameters["grid_n"])
    rungs = int(parameters["rungs"])
    particles = int(parameters["particle_count"])
    workbench_n = int(parameters["workbench_grid_n"])
    attenuation = float(parameters["attenuation"])
    extents = np.asarray(parameters["extents"], dtype=np.float64)
    gates = data["gates"]
    receipts = data["receipts"]
    results: dict[str, dict[str, Any]] = {}

    g78 = receipts["G78"]
    baseline_group = g78["baseline"]
    explicit_group = g78["explicit_off"]
    observations = g78["observations"]
    if not isinstance(observations, dict):
        raise ValueError("gpu.G78.observations must be an object")
    contract_shapes = {
        "pos": (particles, 4),
        "pvel": (particles, 4),
        "acc": (particles, 4),
        "ey": (workbench_n, workbench_n, workbench_n),
        "ei": (workbench_n, workbench_n, workbench_n),
        "q": (workbench_n, workbench_n, workbench_n),
    }
    byte_identical = True
    for key in CONTRACT_KEYS:
        baseline = decode_receipt(baseline_group[key], f"gpu.G78.baseline.{key}")
        explicit = decode_receipt(explicit_group[key], f"gpu.G78.explicit_off.{key}")
        require_shape(baseline, contract_shapes[key], f"gpu.G78.baseline.{key}", "<f4")
        require_shape(explicit, contract_shapes[key], f"gpu.G78.explicit_off.{key}", "<f4")
        byte_identical = byte_identical and baseline.tobytes() == explicit.tobytes()
    for key in (
        "baseline_ready",
        "explicit_off_ready",
        "baseline_disabled",
        "explicit_off_disabled",
    ):
        if not isinstance(observations.get(key), bool):
            raise ValueError(f"gpu.G78.observations.{key} must be boolean")
    for key in ("baseline_grid_n", "explicit_off_grid_n"):
        observed_grid = observations.get(key)
        if (
            not isinstance(observed_grid, int)
            or isinstance(observed_grid, bool)
            or observed_grid != workbench_n
        ):
            raise ValueError(
                f"gpu.G78.observations.{key} must equal frozen grid {workbench_n}"
            )
    g78_metrics: dict[str, float | bool] = {
        "byte_identical": byte_identical,
        "disabled_readback": (
            observations["baseline_disabled"]
            and observations["explicit_off_disabled"]
        ),
        "baseline_ready": observations["baseline_ready"],
        "explicit_off_ready": observations["explicit_off_ready"],
    }
    g78_pass = all(bool(value) for value in g78_metrics.values())
    results["G78"] = audit(
        gates["G78"],
        g78_metrics,
        g78_pass,
        rel_tol=GPU_REL_TOL,
        abs_tol=GPU_ABS_TOL,
    )

    enabled = receipts["enabled"]
    before = decode_gpu_state(
        enabled["before"],
        "gpu.enabled.before",
        n=n,
        rungs=rungs,
        particles=particles,
        include_particles=True,
    )
    after_one = decode_gpu_state(
        enabled["after_one"],
        "gpu.enabled.after_one",
        n=n,
        rungs=rungs,
        particles=particles,
        include_particles=True,
    )
    after_64 = decode_gpu_state(
        enabled["after_64"],
        "gpu.enabled.after_64",
        n=n,
        rungs=rungs,
        particles=particles,
        include_particles=True,
    )
    before_p, before_l = gpu_ledger(before, extents, include_spin=True)
    after_p, after_l = gpu_ledger(after_one, extents, include_spin=True)
    _, after_without_spin_l = gpu_ledger(
        after_one, extents, include_spin=False
    )
    linear_error = gpu_relative_error(after_p, before_p)
    angular_error = gpu_relative_error(after_l, before_l)
    without_spin_error = gpu_relative_error(after_without_spin_l, before_l)
    separation = without_spin_error / max(angular_error, 1.0e-30)
    heat_increment = gpu_heat(after_one) - gpu_heat(before)

    g79_metrics = {
        "linear_relative_error": linear_error,
        "heat_increment": heat_increment,
    }
    g79_pass = (
        math.isfinite(linear_error)
        and linear_error <= 2.0e-5
        and math.isfinite(heat_increment)
        and heat_increment >= 0.0
    )
    results["G79"] = audit(
        gates["G79"],
        g79_metrics,
        g79_pass,
        rel_tol=GPU_REL_TOL,
        abs_tol=GPU_ABS_TOL,
    )

    g80_metrics = {
        "angular_relative_error": angular_error,
        "spin_error_separation": separation,
    }
    g80_pass = (
        math.isfinite(angular_error)
        and angular_error <= 5.0e-4
        and math.isfinite(separation)
        and separation >= 10.0
    )
    results["G80"] = audit(
        gates["G80"],
        g80_metrics,
        g80_pass,
        rel_tol=GPU_REL_TOL,
        abs_tol=GPU_ABS_TOL,
    )

    g81_receipts = receipts["G81"]
    scale_states = {
        key: decode_gpu_state(
            g81_receipts[key],
            f"gpu.G81.{key}",
            n=n,
            rungs=rungs,
            particles=particles,
            include_particles=False,
        )
        for key in ("attenuated", "unit", "zero", "equal")
    }
    attenuated_norm = float(
        np.linalg.norm(scale_states["attenuated"]["momentum"][0, ..., :3])
    )
    unit_norm = float(np.linalg.norm(scale_states["unit"]["momentum"][0, ..., :3]))
    attenuation_ratio = attenuated_norm / unit_norm if unit_norm > 0.0 else math.inf
    attenuation_error = abs(attenuation_ratio - attenuation) / attenuation
    null_max = max(
        float(np.max(np.abs(scale_states["zero"]["momentum"]))),
        float(np.max(np.abs(scale_states["equal"]["momentum"]))),
    )
    scale_finite = all(arrays_finite(state.values()) for state in scale_states.values())
    g81_metrics = {
        "attenuation_relative_error": attenuation_error,
        "null_max_abs": null_max,
        "finite": scale_finite,
    }
    g81_pass = (
        math.isfinite(attenuation_error)
        and attenuation_error <= 2.0e-4
        and math.isfinite(null_max)
        and null_max <= 1.0e-6
        and scale_finite
    )
    results["G81"] = audit(
        gates["G81"],
        g81_metrics,
        g81_pass,
        rel_tol=GPU_REL_TOL,
        abs_tol=GPU_ABS_TOL,
    )

    final_p, final_l = gpu_ledger(after_64, extents, include_spin=True)
    before_orientation = before["orientation"][0].astype(np.float64)
    after_orientation = after_one["orientation"][0].astype(np.float64)
    zero_spin_orientation = after_one["orientation"][1].astype(np.float64)
    identity = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    orientation_delta = float(np.linalg.norm(after_orientation - before_orientation))
    quaternion_norm_error = abs(float(np.linalg.norm(after_orientation)) - 1.0)
    zero_spin_identity_error = float(
        np.linalg.norm(zero_spin_orientation - identity)
    )
    finite_64 = arrays_finite(after_64.values())
    linear_drift = gpu_relative_error(final_p, before_p)
    angular_drift = gpu_relative_error(final_l, before_l)
    g82_metrics = {
        "orientation_delta": orientation_delta,
        "quaternion_norm_error": quaternion_norm_error,
        "zero_spin_identity_error": zero_spin_identity_error,
        "finite_64_steps": finite_64,
        "linear_momentum_drift": linear_drift,
        "angular_momentum_drift": angular_drift,
    }
    g82_pass = (
        math.isfinite(orientation_delta)
        and orientation_delta > 1.0e-6
        and math.isfinite(quaternion_norm_error)
        and quaternion_norm_error <= 1.0e-5
        and math.isfinite(zero_spin_identity_error)
        and zero_spin_identity_error <= 1.0e-6
        and finite_64
        and math.isfinite(linear_drift)
        and linear_drift <= 5.0e-4
        and math.isfinite(angular_drift)
        and angular_drift <= 5.0e-3
    )
    results["G82"] = audit(
        gates["G82"],
        g82_metrics,
        g82_pass,
        rel_tol=GPU_REL_TOL,
        abs_tol=GPU_ABS_TOL,
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default="_diag/rotation_reference.json")
    parser.add_argument("--gpu", default="_diag/rotation_stress_gpu.json")
    parser.add_argument("--reference-only", action="store_true")
    args = parser.parse_args()

    try:
        results = verify_reference(
            load(args.reference, "cassi.rotation.reference.v2")
        )
        if not args.reference_only:
            results.update(verify_gpu(load(args.gpu, "cassi.rotation.gpu.v2")))
    except (KeyError, OSError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        print("RESULT: FAIL")
        raise SystemExit(1) from exc

    for name in sorted(results):
        result = results[name]
        print(f"{name}: {'PASS' if result['pass'] else 'FAIL'}")
        for metric, value in result["metrics"].items():
            print(f"  replay_{metric}: {value}")
        print(f"  threshold_pass: {result['threshold_pass']}")
        print(f"  producer_consistent: {result['producer_consistent']}")
    passed = all(result["pass"] for result in results.values())
    print(f"RESULT: {'PASS' if passed else 'FAIL'}")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
