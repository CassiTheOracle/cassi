#!/usr/bin/env python3
"""Measure carrier ultraviolet structure without changing the source fields.

Run from repository root: python computations/matter_formation_lattice.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "computations/matter-formation-continuum-prereg.md"
SOURCES = (
    (17, "runs/20260902_particle_carrier_direct_coordinate_v2/fields_primary_half_reference_block01.npz", "c32beb4ee7bc7746a4fc18b63bc04ef7db12cc18505c9bee8ce2d298ddc25837"),
    (21, "runs/20260902_particle_carrier_direct_coordinate_v2/fields_comparison_H_block01.npz", "8aa65f3c08167c902660f9e8d09c0ce921d43c7f0af152b31aae79db6875810f"),
    (25, "runs/20260902_particle_carrier_resolution_recovery/fields_resolution_X1_block01.npz", "c75a4255da2008a90268fcda83fcdbdca5a8386f9f580f854737668b664e8393"),
    (29, "runs/20260902_particle_carrier_resolution_recovery/fields_resolution_X2_block01.npz", "db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0"),
)


def source_hash(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix in {".py", ".md", ".json"}:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def measure(carrier: np.ndarray, dx: float) -> dict:
    n = carrier.shape[0]
    if carrier.shape != (n, n, n) or not np.isfinite(carrier).all():
        raise ValueError("Carrier must be a finite cubic scalar field")
    norm = float(np.sum(carrier**2))
    if norm <= 0:
        raise ValueError("A zero field has no normalized spatial diagnostic")
    gradient = np.gradient(carrier, dx, edge_order=2)
    centered = 0.5 * dx**3 * sum(float(np.sum(d**2)) for d in gradient)
    edge = 0.5 * dx * sum(float(np.sum(np.diff(carrier, axis=a)**2)) for a in range(3))
    frequencies = np.fft.fftfreq(n, d=dx)
    high = np.abs(frequencies) >= 0.75 / (2.0 * dx)
    mask = high[:, None, None] | high[None, :, None] | high[None, None, :]
    power = np.abs(np.fft.fftn(carrier))**2
    parity = [float(np.sum(carrier[i::2, j::2, k::2]**2) / norm)
              for i in range(2) for j in range(2) for k in range(2)]
    return {
        "N": n,
        "dx": dx,
        "charge": norm * dx**3,
        "high_frequency_fraction": float(np.sum(power[mask]) / np.sum(power)),
        "parity_fractions": parity,
        "centered_kinetic": centered,
        "edge_kinetic": edge,
        "scaled_edge_kinetic": dx**2 * edge,
        "edge_to_centered": edge / centered,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs/20260906_matter_formation")
    args = parser.parse_args()
    directory = args.output_dir.resolve()
    destination = directory / "lattice.json"
    if destination.exists():
        raise FileExistsError(f"Refusing to replace first-execution receipt: {destination}")
    rows = []
    gaussians = []
    for n, relative, digest in SOURCES:
        path = ROOT / relative
        actual = source_hash(path)
        if actual != digest:
            raise ValueError(f"Source identity mismatch: {relative}")
        dx = 8.0 / (n - 1)
        with np.load(path, allow_pickle=False) as arrays:
            carrier = np.asarray(arrays["c"], dtype=np.float64)
            if carrier.shape != (n, n, n):
                raise ValueError(f"Unexpected source grid: {relative}")
            row = measure(carrier, dx)
        if abs(row["charge"] - 4.0) > 4e-10:
            raise ValueError(f"Source charge mismatch: {relative}")
        if not all(np.count_nonzero(np.take(carrier, i, axis=a)) == 0
                   for a in range(3) for i in (0, n - 1)):
            raise ValueError(f"Source carrier boundary mismatch: {relative}")
        row.update(artifact=relative, sha256=actual)
        rows.append(row)
        x = np.linspace(-4.0, 4.0, n)
        r2 = x[:, None, None]**2 + x[None, :, None]**2 + x[None, None, :]**2
        gaussian = np.exp(-r2 / 2.0)
        for axis in range(3):
            low = [slice(None)] * 3
            high = [slice(None)] * 3
            low[axis], high[axis] = 0, n - 1
            gaussian[tuple(low)] = gaussian[tuple(high)] = 0.0
        gaussian *= np.sqrt(4.0 / (np.sum(gaussian**2) * dx**3))
        gaussians.append(measure(gaussian, dx))

    alternating = np.broadcast_to((-1.0)**np.arange(16)[:, None, None], (16, 16, 16))
    central_periodic = 0.5 * sum(float(np.sum(((np.roll(alternating, -1, a) -
                                              np.roll(alternating, 1, a)) / 2.0)**2))
                                 for a in range(3))
    edge_periodic = 0.5 * sum(float(np.sum((np.roll(alternating, -1, a) - alternating)**2))
                              for a in range(3))
    controls_pass = central_periodic == 0.0 and edge_periodic == 8192.0 and all(
        g["high_frequency_fraction"] < 0.20 and g["edge_to_centered"] < 4.0 for g in gaussians)
    last = rows[-2:]
    scaled_change = abs(last[1]["scaled_edge_kinetic"] - last[0]["scaled_edge_kinetic"]) / max(
        abs(last[0]["scaled_edge_kinetic"]), abs(last[1]["scaled_edge_kinetic"]))
    rejected = all(r["high_frequency_fraction"] > 0.20 and r["edge_to_centered"] > 4.0
                   for r in last) and scaled_change < 0.20
    finest_matches = abs(rows[-1]["high_frequency_fraction"] - 0.8744032081) < 1e-8
    verdict = "CONTRADICTS" if controls_pass and finest_matches and rejected else "INCONCLUSIVE"
    result = {
        "schema": "cassi.matter-formation.lattice.v1",
        "prereg_sha256": source_hash(PREREG),
        "source_sha256": source_hash(Path(__file__)),
        "rows": rows,
        "controls": {"gaussians": gaussians, "periodic": {
            "N": 16, "dx": 1.0, "centered_kinetic": central_periodic, "edge_kinetic": edge_periodic}},
        "controls_pass": controls_pass,
        "finest_hessian_diagnostic_matches": finest_matches,
        "finest_scaled_edge_relative_change": scaled_change,
        "verdict": verdict,
        "scope": "Immutable carrier-only ultraviolet diagnostic; no relaxed full gauge energy or infinite-sequence theorem.",
    }
    directory.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("N   high-frequency   T_centered      T_edge        dx^2 T_edge   max parity")
    for row in rows:
        print(f'{row["N"]:2d}  {row["high_frequency_fraction"]:.10f}   '
              f'{row["centered_kinetic"]:12.7f}  {row["edge_kinetic"]:12.7f}  '
              f'{row["scaled_edge_kinetic"]:12.7f}  {max(row["parity_fractions"]):.10f}')
    print(verdict)
    print(f"Receipt: {destination}")
    return 0 if controls_pass and finest_matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
