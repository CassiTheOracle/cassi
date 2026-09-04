#!/usr/bin/env python
"""G75-G77 conservative rotation-stress reference model.

Run from the CassiCosmos repository root:
    python research/rotation/rotation_reference.py
"""

from __future__ import annotations

import base64
import argparse
import json
import math
from pathlib import Path

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0

def array_receipt(values: np.ndarray) -> dict[str, object]:
    array = np.ascontiguousarray(values)
    return {
        "dtype": array.dtype.str,
        "shape": list(array.shape),
        "base64": base64.b64encode(array.tobytes()).decode("ascii"),
    }


def _plus(a: np.ndarray, axis: int) -> np.ndarray:
    return np.roll(a, -1, axis=axis)


def _minus(a: np.ndarray, axis: int) -> np.ndarray:
    return np.roll(a, 1, axis=axis)


def _second(a: np.ndarray, axis: int, h: float) -> np.ndarray:
    return (_plus(a, axis) - 2.0 * a + _minus(a, axis)) / (h * h)


def _mixed(a: np.ndarray, axis_a: int, axis_b: int, ha: float, hb: float) -> np.ndarray:
    pp = np.roll(np.roll(a, -1, axis=axis_a), -1, axis=axis_b)
    pm = np.roll(np.roll(a, -1, axis=axis_a), 1, axis=axis_b)
    mp = np.roll(np.roll(a, 1, axis=axis_a), -1, axis=axis_b)
    mm = np.roll(np.roll(a, 1, axis=axis_a), 1, axis=axis_b)
    return (pp - pm - mp + mm) / (4.0 * ha * hb)


def cell_centers(n: int, extents: np.ndarray) -> np.ndarray:
    axes = [np.linspace(-e, e, n, endpoint=False) + e / n for e in extents]
    return np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1)


def elastic_acceleration(
    displacement: np.ndarray,
    extents: np.ndarray,
    c_t: float,
    c_l: float,
    scale_omega: float,
    attenuation: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return spatial and interscale acceleration for [rung,x,y,z,xyz]."""
    n = displacement.shape[1]
    hx, hy, hz = 2.0 * extents / n
    spatial = np.zeros_like(displacement)

    for rung in range(displacement.shape[0]):
        u = displacement[rung]
        lap = (
            _second(u, 0, hx)
            + _second(u, 1, hy)
            + _second(u, 2, hz)
        )
        ux, uy, uz = u[..., 0], u[..., 1], u[..., 2]
        grad_div = np.stack(
            [
                _second(ux, 0, hx)
                + _mixed(uy, 0, 1, hx, hy)
                + _mixed(uz, 0, 2, hx, hz),
                _mixed(ux, 0, 1, hx, hy)
                + _second(uy, 1, hy)
                + _mixed(uz, 1, 2, hy, hz),
                _mixed(ux, 0, 2, hx, hz)
                + _mixed(uy, 1, 2, hy, hz)
                + _second(uz, 2, hz),
            ],
            axis=-1,
        )
        spatial[rung] = c_t * c_t * lap + (c_l * c_l - c_t * c_t) * grad_div

    scale = np.zeros_like(displacement)
    for rung in range(displacement.shape[0] - 1):
        conductance = attenuation ** (rung + 1)
        pair_acceleration = scale_omega * scale_omega * conductance * (
            displacement[rung + 1] - displacement[rung]
        )
        scale[rung] += pair_acceleration
        scale[rung + 1] -= pair_acceleration
    return spatial, scale


def field_step(
    displacement: np.ndarray,
    momentum: np.ndarray,
    spin: np.ndarray,
    *,
    dt: float,
    extents: np.ndarray,
    field_inertia: float,
    c_t: float,
    c_l: float,
    scale_omega: float,
    attenuation: float,
) -> tuple[np.ndarray, np.ndarray]:
    spatial, scale = elastic_acceleration(
        displacement, extents, c_t, c_l, scale_omega, attenuation
    )
    delta_momentum = field_inertia * dt * (spatial + scale)
    momentum += delta_momentum

    centers = cell_centers(displacement.shape[1], extents)
    spin -= np.cross(centers[None, ...], delta_momentum)
    displacement += dt * momentum / field_inertia
    return spatial, scale


def particle_cells(positions: np.ndarray, n: int, extents: np.ndarray) -> np.ndarray:
    unit = np.mod((positions + extents) / (2.0 * extents), 1.0)
    return np.floor(unit * n).astype(np.int64) % n


def matter_field_exchange(
    positions: np.ndarray,
    velocities: np.ndarray,
    masses: np.ndarray,
    momentum: np.ndarray,
    spin: np.ndarray,
    heat: np.ndarray,
    *,
    dt: float,
    extents: np.ndarray,
    field_inertia: float,
    exchange_rate: float,
) -> np.ndarray:
    """Apply the registered cell exchange and return the cell impulses."""
    n = momentum.shape[1]
    cells = particle_cells(positions, n, extents)
    matter_mass = np.zeros((n, n, n), dtype=np.float64)
    matter_momentum = np.zeros((n, n, n, 3), dtype=np.float64)
    for index, cell in enumerate(cells):
        key = tuple(cell)
        matter_mass[key] += masses[index]
        matter_momentum[key] += masses[index] * velocities[index]

    eta = 1.0 - math.exp(-exchange_rate * dt)
    impulse = np.zeros((n, n, n, 3), dtype=np.float64)
    occupied = matter_mass > 0.0
    matter_velocity = np.zeros_like(matter_momentum)
    matter_velocity[occupied] = matter_momentum[occupied] / matter_mass[occupied, None]
    field_velocity = momentum[0] / field_inertia
    reduced_mass = np.zeros_like(matter_mass)
    reduced_mass[occupied] = (
        matter_mass[occupied]
        * field_inertia
        / (matter_mass[occupied] + field_inertia)
    )
    relative_velocity = matter_velocity - field_velocity
    impulse[occupied] = (
        eta * reduced_mass[occupied, None] * relative_velocity[occupied]
    )
    momentum[0] += impulse
    heat[0, occupied] += (
        0.5
        * eta
        * (2.0 - eta)
        * reduced_mass[occupied]
        * np.einsum("ij,ij->i", relative_velocity[occupied], relative_velocity[occupied])
    )

    centers = cell_centers(n, extents)
    period = 2.0 * extents
    for index, cell in enumerate(cells):
        key = tuple(cell)
        total_mass = matter_mass[key]
        particle_impulse = masses[index] / total_mass * impulse[key]
        velocities[index] -= particle_impulse / masses[index]
        offset = positions[index] - centers[key]
        offset -= np.round(offset / period) * period
        spin[(0,) + key] += np.cross(offset, particle_impulse)
    return impulse


def ledger(
    positions: np.ndarray,
    velocities: np.ndarray,
    masses: np.ndarray,
    momentum: np.ndarray,
    spin: np.ndarray,
    extents: np.ndarray,
    *,
    include_spin: bool = True,
) -> dict[str, np.ndarray]:
    particle_p = np.sum(masses[:, None] * velocities, axis=0)
    particle_l = np.sum(np.cross(positions, masses[:, None] * velocities), axis=0)
    field_p = np.sum(momentum, axis=(0, 1, 2, 3))
    centers = cell_centers(momentum.shape[1], extents)
    field_l = np.sum(np.cross(centers[None, ...], momentum), axis=(0, 1, 2, 3))
    intrinsic = np.sum(spin, axis=(0, 1, 2, 3)) if include_spin else np.zeros(3)
    return {
        "particle_p": particle_p,
        "field_p": field_p,
        "total_p": particle_p + field_p,
        "particle_l": particle_l,
        "field_l": field_l,
        "intrinsic_l": intrinsic,
        "total_l": particle_l + field_l + intrinsic,
    }


def relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
    return float(np.linalg.norm(actual - expected) / max(np.linalg.norm(expected), 1.0e-30))


def gate_75(dt: float) -> dict[str, object]:
    positions = np.array(
        [
            [-1.4, -0.3, 0.0],
            [-0.6, 0.7, 0.0],
            [0.8, -0.8, 0.0],
            [1.2, 0.4, 0.0],
        ],
        dtype=np.float64,
    )
    masses = np.array([1.0, 2.0, 1.5, 0.75], dtype=np.float64)
    velocities = np.zeros_like(positions)
    angle = math.radians(31.0)
    rotation = np.array(
        [
            [math.cos(angle), -math.sin(angle), 0.0],
            [math.sin(angle), math.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    tidal = rotation @ np.diag([0.18, -0.11, -0.07]) @ rotation.T
    acceleration = positions @ tidal.T
    torque = np.sum(np.cross(positions, masses[:, None] * acceleration), axis=0)
    before = np.sum(np.cross(positions, masses[:, None] * velocities), axis=0)
    velocities_after = velocities + dt * acceleration
    positions_after = positions + dt * velocities_after
    after = np.sum(np.cross(positions_after, masses[:, None] * velocities_after), axis=0)
    tidal_error = relative_error(after - before, dt * torque)

    mirror = np.diag([-1.0, 1.0, 1.0])
    mirrored_positions = positions @ mirror.T
    mirrored_tidal = mirror @ tidal @ mirror.T
    mirrored_acceleration = mirrored_positions @ mirrored_tidal.T
    mirrored_velocity = dt * mirrored_acceleration
    mirrored_position_after = mirrored_positions + dt * mirrored_velocity
    mirrored_l = np.sum(
        np.cross(mirrored_position_after, masses[:, None] * mirrored_velocity), axis=0
    )
    mirrored_expected = np.linalg.det(mirror) * mirror @ after
    mirror_error = relative_error(mirrored_l, mirrored_expected)

    aligned_positions = np.array(
        [
            [-1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, -0.5, 0.0],
            [0.0, 0.5, 0.0],
        ]
    )
    aligned_masses = np.ones(4)
    aligned_tidal = np.diag([0.2, -0.1, -0.1])
    aligned_acceleration = aligned_positions @ aligned_tidal.T
    aligned_velocity = dt * aligned_acceleration
    aligned_after = aligned_positions + dt * aligned_velocity
    aligned_l = np.sum(
        np.cross(aligned_after, aligned_masses[:, None] * aligned_velocity), axis=0
    )
    null_change = float(np.linalg.norm(aligned_l))

    passed = tidal_error <= 1.0e-10 and mirror_error <= 1.0e-10 and null_change <= 1.0e-12
    return {
        "pass": passed,
        "tidal_relative_error": tidal_error,
        "mirror_relative_error": mirror_error,
        "null_absolute_change": null_change,
        "torque": torque.tolist(),
        "delta_l": (after - before).tolist(),
        "mirrored_l": mirrored_l.tolist(),
        "raw": {
            "positions": array_receipt(positions),
            "masses": array_receipt(masses),
            "velocities_before": array_receipt(velocities),
            "accelerations": array_receipt(acceleration),
            "positions_after": array_receipt(positions_after),
            "velocities_after": array_receipt(velocities_after),
            "mirror": array_receipt(mirror),
            "mirrored_positions_after": array_receipt(mirrored_position_after),
            "mirrored_velocities_after": array_receipt(mirrored_velocity),
            "aligned_positions_after": array_receipt(aligned_after),
            "aligned_velocities_after": array_receipt(aligned_velocity),
            "aligned_masses": array_receipt(aligned_masses),
        },
    }


def gate_76(
    n: int,
    rungs: int,
    dt: float,
    extents: np.ndarray,
    field_inertia: float,
    exchange_rate: float,
) -> dict[str, object]:
    positions = np.array(
        [
            [-1.45, -1.15, -0.35],
            [-1.10, -0.72, 0.25],
            [0.42, 0.83, -0.55],
            [0.78, 1.18, 0.65],
        ],
        dtype=np.float64,
    )
    velocities = np.array(
        [
            [0.42, -0.15, 0.08],
            [-0.11, 0.36, -0.04],
            [0.25, 0.18, -0.17],
            [-0.31, -0.09, 0.22],
        ],
        dtype=np.float64,
    )
    masses = np.array([1.0, 2.0, 1.5, 0.75], dtype=np.float64)
    displacement = np.zeros((rungs, n, n, n, 3), dtype=np.float64)
    momentum = np.zeros_like(displacement)
    momentum[0, 0, 0, 0] = np.array([0.14, -0.09, 0.03])
    spin = np.zeros_like(displacement)
    heat = np.zeros(displacement.shape[:-1], dtype=np.float64)
    velocities_before = velocities.copy()
    momentum_before = momentum.copy()
    spin_before = spin.copy()
    heat_before = heat.copy()

    before = ledger(positions, velocities, masses, momentum, spin, extents)
    matter_field_exchange(
        positions,
        velocities,
        masses,
        momentum,
        spin,
        heat,
        dt=dt,
        extents=extents,
        field_inertia=field_inertia,
        exchange_rate=exchange_rate,
    )
    after = ledger(positions, velocities, masses, momentum, spin, extents)
    after_without_spin = ledger(
        positions, velocities, masses, momentum, spin, extents, include_spin=False
    )
    linear_error = relative_error(after["total_p"], before["total_p"])
    angular_error = relative_error(after["total_l"], before["total_l"])
    no_spin_error = relative_error(after_without_spin["total_l"], before["total_l"])
    heat_increment = float(np.sum(heat))
    separation = no_spin_error / max(angular_error, 1.0e-30)
    passed = (
        linear_error <= 1.0e-12
        and angular_error <= 1.0e-12
        and math.isfinite(heat_increment)
        and heat_increment >= 0.0
        and separation >= 1.0e4
    )
    return {
        "pass": passed,
        "linear_relative_error": linear_error,
        "angular_relative_error": angular_error,
        "without_spin_relative_error": no_spin_error,
        "spin_error_separation": separation,
        "heat_increment": heat_increment,
        "total_p_before": before["total_p"].tolist(),
        "total_p_after": after["total_p"].tolist(),
        "total_l_before": before["total_l"].tolist(),
        "total_l_after": after["total_l"].tolist(),
        "raw": {
            "positions": array_receipt(positions),
            "masses": array_receipt(masses),
            "velocities_before": array_receipt(velocities_before),
            "momentum_before": array_receipt(momentum_before),
            "spin_before": array_receipt(spin_before),
            "heat_before": array_receipt(heat_before),
            "velocities_after": array_receipt(velocities),
            "momentum_after": array_receipt(momentum),
            "spin_after": array_receipt(spin),
            "heat_after": array_receipt(heat),
        },
    }


def gate_77(
    n: int,
    rungs: int,
    dt: float,
    extents: np.ndarray,
    field_inertia: float,
    c_t: float,
    c_l: float,
    scale_omega: float,
    attenuation: float,
    exchange_rate: float,
) -> dict[str, object]:
    shape = (rungs, n, n, n, 3)
    contrast = np.zeros(shape, dtype=np.float64)
    contrast[0, ..., 0] = 0.2
    _, scale_d = elastic_acceleration(
        contrast, extents, c_t, c_l, scale_omega, attenuation
    )
    _, scale_one = elastic_acceleration(contrast, extents, c_t, c_l, scale_omega, 1.0)
    impulse_d = field_inertia * dt * scale_d[0]
    impulse_one = field_inertia * dt * scale_one[0]
    attenuation_ratio = float(np.linalg.norm(impulse_d) / np.linalg.norm(impulse_one))
    attenuation_error = abs(attenuation_ratio - attenuation) / attenuation
    summed_scale_momentum = float(np.linalg.norm(np.sum(scale_d, axis=(0, 1, 2, 3))))

    zero = np.zeros(shape, dtype=np.float64)
    _, zero_scale = elastic_acceleration(zero, extents, c_t, c_l, scale_omega, attenuation)
    equal = np.full(shape, 0.125, dtype=np.float64)
    _, equal_scale = elastic_acceleration(equal, extents, c_t, c_l, scale_omega, attenuation)
    null_max = max(float(np.max(np.abs(zero_scale))), float(np.max(np.abs(equal_scale))))

    axes = [np.linspace(-e, e, n, endpoint=False) + e / n for e in extents]
    x, y, z = np.meshgrid(*axes, indexing="ij")
    displacement = np.zeros(shape, dtype=np.float64)
    displacement[0, ..., 0] = 0.03 * np.sin(math.pi * x / extents[0])
    displacement[1, ..., 1] = 0.02 * np.cos(math.pi * y / extents[1])
    displacement[2, ..., 2] = 0.01 * np.sin(math.pi * z / extents[2])
    momentum = np.zeros_like(displacement)
    spin = np.zeros_like(displacement)
    heat = np.zeros(shape[:-1], dtype=np.float64)
    positions = np.array([[-1.2, -0.8, 0.1], [0.9, 0.7, -0.2]], dtype=np.float64)
    velocities = np.array([[0.2, -0.1, 0.05], [-0.15, 0.12, -0.04]], dtype=np.float64)
    masses = np.array([1.0, 1.5], dtype=np.float64)
    finite = True
    for _ in range(64):
        field_step(
            displacement,
            momentum,
            spin,
            dt=dt,
            extents=extents,
            field_inertia=field_inertia,
            c_t=c_t,
            c_l=c_l,
            scale_omega=scale_omega,
            attenuation=attenuation,
        )
        matter_field_exchange(
            positions,
            velocities,
            masses,
            momentum,
            spin,
            heat,
            dt=dt,
            extents=extents,
            field_inertia=field_inertia,
            exchange_rate=exchange_rate,
        )
        finite = finite and all(
            np.all(np.isfinite(values))
            for values in (displacement, momentum, spin, heat, velocities)
        )

    passed = (
        summed_scale_momentum <= 1.0e-12
        and attenuation_error <= 1.0e-12
        and null_max <= 1.0e-12
        and finite
    )
    return {
        "pass": passed,
        "summed_scale_momentum_norm": summed_scale_momentum,
        "attenuation_ratio": attenuation_ratio,
        "attenuation_relative_error": attenuation_error,
        "null_max_abs": null_max,
        "finite_64_steps": finite,
        "heat_after_64_steps": float(np.sum(heat)),
        "raw": {
            "scale_attenuated": array_receipt(scale_d),
            "scale_unit": array_receipt(scale_one),
            "scale_zero": array_receipt(zero_scale),
            "scale_equal": array_receipt(equal_scale),
            "displacement_after_64": array_receipt(displacement),
            "momentum_after_64": array_receipt(momentum),
            "spin_after_64": array_receipt(spin),
            "heat_after_64": array_receipt(heat),
            "velocities_after_64": array_receipt(velocities),
        },
    }


def run() -> dict[str, object]:
    n = 4
    rungs = 3
    dt = 0.01
    extents = np.array([2.0, 2.0, 2.0], dtype=np.float64)
    field_inertia = 2.0
    c_t = 0.4
    c_l = 0.7
    scale_omega = 0.5
    attenuation = 1.0 / PHI
    exchange_rate = 1.5

    gates = {
        "G75": gate_75(dt),
        "G76": gate_76(n, rungs, dt, extents, field_inertia, exchange_rate),
        "G77": gate_77(
            n,
            rungs,
            dt,
            extents,
            field_inertia,
            c_t,
            c_l,
            scale_omega,
            attenuation,
            exchange_rate,
        ),
    }
    receipts = {name: gate.pop("raw") for name, gate in gates.items()}
    return {
        "schema": "cassi.rotation.reference.v2",
        "parameters": {
            "grid_n": n,
            "rungs": rungs,
            "dt": dt,
            "extents": extents.tolist(),
            "field_inertia": field_inertia,
            "c_t": c_t,
            "c_l": c_l,
            "scale_omega": scale_omega,
            "attenuation": attenuation,
            "exchange_rate": exchange_rate,
        },
        "gates": gates,
        "receipts": receipts,
        "verdict": "PASS" if all(bool(gate["pass"]) for gate in gates.values()) else "FAIL",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="_diag/rotation_reference.json")
    args = parser.parse_args()
    result = run()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, gate in result["gates"].items():
        print(f"{name}: {'PASS' if gate['pass'] else 'FAIL'}")
        for key, value in gate.items():
            if key != "pass":
                print(f"  {key}: {value}")
    print(f"RESULT: {result['verdict']}")
    print(f"artifact: {output.as_posix()}")
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
