#!/usr/bin/env python3
"""Build the hash-bound two-particle field fixture.

Run from the CassiCosmos repository root:
    python tools/build_field_particles_pair.py
"""

from __future__ import annotations

from collections import deque
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "field_particles" / "localized_x2_n29.f32"
SOURCE_MANIFEST = SOURCE.with_suffix(".json")
STATE_OUTPUT = ROOT / "data" / "field_particles" / "moving_pair_n57_state.f32"
VELOCITY_OUTPUT = ROOT / "data" / "field_particles" / "moving_pair_n57_velocity.f32"
MANIFEST_OUTPUT = ROOT / "data" / "field_particles" / "moving_pair_n57.json"
SOURCE_SHA256 = "5d43794099f52f4343486a2f1b38787356301153bd48d033d0d42451160ab6d3"
STATE_STRIDE = 18
VELOCITY_STRIDE = 16
CHI_RE = 7
CHI_IM = 8
PAIR_N = 57
CENTERS = (-4.0, 4.0)
DIRECTIONS = (1.0, -1.0)
SPEED = 0.25
THRESHOLD_FRACTION = 0.05


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def smooth_density(density: np.ndarray) -> np.ndarray:
    total = np.zeros_like(density, dtype=np.float64)
    samples = np.zeros_like(density, dtype=np.int16)
    n = density.shape[0]
    for dz in range(-1, 2):
        dst_z = slice(max(0, -dz), min(n, n - dz))
        src_z = slice(max(0, dz), min(n, n + dz))
        for dy in range(-1, 2):
            dst_y = slice(max(0, -dy), min(n, n - dy))
            src_y = slice(max(0, dy), min(n, n + dy))
            for dx in range(-1, 2):
                dst_x = slice(max(0, -dx), min(n, n - dx))
                src_x = slice(max(0, dx), min(n, n + dx))
                target = (dst_z, dst_y, dst_x)
                source = (src_z, src_y, src_x)
                total[target] += density[source]
                samples[target] += 1
    return total / samples


def core_centers(density: np.ndarray, extent: float) -> list[float]:
    smoothed = smooth_density(density)
    core = smoothed >= float(smoothed.max()) * THRESHOLD_FRACTION
    n = density.shape[0]
    labels = np.full(core.shape, -1, dtype=np.int32)
    centers: list[float] = []
    label = 0
    for seed in np.flatnonzero(core):
        z_raw, y_raw, x_raw = np.unravel_index(seed, core.shape)
        z, y, x = int(z_raw), int(y_raw), int(x_raw)
        if labels[z, y, x] >= 0:
            continue
        queue: deque[tuple[int, int, int]] = deque([(z, y, x)])
        labels[z, y, x] = label
        weighted_x = 0.0
        weight = 0.0
        cells = 0
        while queue:
            cz, cy, cx = queue.popleft()
            local = float(smoothed[cz, cy, cx])
            world_x = -0.5 * extent + extent * cx / float(n - 1)
            weighted_x += world_x * local
            weight += local
            cells += 1
            for nz, ny, nx in (
                (cz - 1, cy, cx), (cz + 1, cy, cx),
                (cz, cy - 1, cx), (cz, cy + 1, cx),
                (cz, cy, cx - 1), (cz, cy, cx + 1),
            ):
                if (
                    0 <= nz < n and 0 <= ny < n and 0 <= nx < n
                    and core[nz, ny, nx] and labels[nz, ny, nx] < 0
                ):
                    labels[nz, ny, nx] = label
                    queue.append((nz, ny, nx))
        if cells > 1 and weight > 0.0:
            centers.append(weighted_x / weight)
            label += 1
    return sorted(centers)


def main() -> None:
    if sha256(SOURCE) != SOURCE_SHA256:
        raise SystemExit("refusing unreviewed field-particle source")
    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    source_n = int(source_manifest["grid_n"])
    dx = float(source_manifest["dx"])
    if source_n != 29 or PAIR_N != 2 * source_n - 1:
        raise SystemExit("unexpected source or pair grid")
    source = np.fromfile(SOURCE, dtype="<f4")
    expected_values = source_n**3 * STATE_STRIDE
    if source.size != expected_values:
        raise SystemExit(f"unexpected source size: {source.size}")
    source = source.reshape(source_n, source_n, source_n, STATE_STRIDE)
    source64 = source.astype(np.float64)
    vacuum = source64[0, 0, 0].copy()
    source_charge = float(
        np.sum(source64[..., CHI_RE] ** 2 + source64[..., CHI_IM] ** 2) * dx**3
    )

    pair = np.broadcast_to(
        vacuum, (PAIR_N, PAIR_N, PAIR_N, STATE_STRIDE)
    ).copy()
    velocity = np.zeros((PAIR_N, PAIR_N, PAIR_N, VELOCITY_STRIDE), dtype=np.float64)
    source_dx = np.gradient(source64, dx, axis=2, edge_order=2)
    local_x = np.linspace(-4.0, 4.0, source_n, dtype=np.float64)
    middle = (PAIR_N - source_n) // 2
    yz = slice(middle, middle + source_n)
    velocity_components = tuple(range(7)) + tuple(range(9, 18))
    copy_charges: list[float] = []

    for x_start, direction in zip(
        (0, source_n - 1), DIRECTIONS, strict=True
    ):
        copy = source64.copy()
        phase = SPEED * direction * local_x[None, None, :]
        carrier = (
            copy[..., CHI_RE] + 1j * copy[..., CHI_IM]
        ) * np.exp(1j * phase)
        copy[..., CHI_RE] = carrier.real
        copy[..., CHI_IM] = carrier.imag
        copy_charge = float(
            np.sum(copy[..., CHI_RE] ** 2 + copy[..., CHI_IM] ** 2) * dx**3
        )
        copy_charges.append(copy_charge)
        target = (yz, yz, slice(x_start, x_start + source_n))
        pair[target] += copy - vacuum
        for component in velocity_components:
            velocity_component = component if component <= 6 else component - 2
            velocity[target + (velocity_component,)] += (
                -direction * SPEED * source_dx[..., component]
            )

    boundary = np.zeros((PAIR_N, PAIR_N, PAIR_N), dtype=bool)
    boundary[[0, -1], :, :] = True
    boundary[:, [0, -1], :] = True
    boundary[:, :, [0, -1]] = True
    pair[boundary] = vacuum
    velocity[boundary] = 0.0
    pair = np.ascontiguousarray(pair, dtype="<f4")
    velocity = np.ascontiguousarray(velocity, dtype="<f4")
    if not np.isfinite(pair).all() or not np.isfinite(velocity).all():
        raise SystemExit("pair fixture contains non-finite values")
    if not np.array_equal(pair[boundary], np.broadcast_to(vacuum.astype("<f4"), pair[boundary].shape)):
        raise SystemExit("pair fixture outer shell is not the exact vacuum")

    pair_charge = float(
        np.sum(
            pair[..., CHI_RE].astype(np.float64) ** 2
            + pair[..., CHI_IM].astype(np.float64) ** 2
        ) * dx**3
    )
    for charge in copy_charges:
        if abs(charge - source_charge) > 2.0e-7:
            raise SystemExit(f"embedded copy charge mismatch: {charge} vs {source_charge}")
    if abs(sum(copy_charges) - 2.0 * source_charge) > 4.0e-7:
        raise SystemExit("pre-serialization pair charge mismatch")
    if abs(pair_charge - 2.0 * source_charge) > 2.0e-6:
        raise SystemExit(f"serialized pair charge mismatch: {pair_charge}")

    density = (
        pair[..., CHI_RE].astype(np.float64) ** 2
        + pair[..., CHI_IM].astype(np.float64) ** 2
    )
    centers = core_centers(density, dx * (PAIR_N - 1))
    if len(centers) != 2:
        raise SystemExit(f"expected two carrier cores, found {len(centers)}")
    if any(abs(actual - expected) > dx for actual, expected in zip(centers, CENTERS, strict=True)):
        raise SystemExit(f"carrier centers do not match placement: {centers}")

    STATE_OUTPUT.write_bytes(pair.tobytes(order="C"))
    VELOCITY_OUTPUT.write_bytes(velocity.tobytes(order="C"))
    manifest = {
        "schema": "cassi.field-particles-pair.v1",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": SOURCE_SHA256,
        "state": str(STATE_OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "state_sha256": sha256(STATE_OUTPUT),
        "velocity": str(VELOCITY_OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "velocity_sha256": sha256(VELOCITY_OUTPUT),
        "dtype": "little-endian float32",
        "state_layout": "z,y,x,component; 18 interleaved scalars per cell",
        "velocity_layout": "z,y,x,component; 16 interleaved scalars per cell",
        "field_order": source_manifest["field_order"],
        "grid_n": PAIR_N,
        "cells": PAIR_N**3,
        "radius": 0.5 * dx * (PAIR_N - 1),
        "extent": dx * (PAIR_N - 1),
        "dx": dx,
        "omega_c": source_manifest["omega_c"],
        "coefficients": source_manifest["coefficients"],
        "temporal_coefficients": source_manifest["temporal_coefficients"],
        "centers": list(CENTERS),
        "directions": list(DIRECTIONS),
        "speed": SPEED,
        "source_charge_float32": source_charge,
        "copy_charges_float64": copy_charges,
        "pair_charge_float32": pair_charge,
        "catalog_core_centers": centers,
        "state_bytes": STATE_OUTPUT.stat().st_size,
        "bytes": STATE_OUTPUT.stat().st_size,
        "velocity_bytes": VELOCITY_OUTPUT.stat().st_size,
    }
    MANIFEST_OUTPUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {STATE_OUTPUT.relative_to(ROOT)} ({STATE_OUTPUT.stat().st_size} bytes)")
    print(f"state sha256 {manifest['state_sha256']}")
    print(f"velocity sha256 {manifest['velocity_sha256']}")
    print(f"source charge {source_charge:.12f}")
    print(f"copy charges {copy_charges}")
    print(f"pair charge {pair_charge:.12f}")
    print(f"catalog centers {centers}")


if __name__ == "__main__":
    main()
