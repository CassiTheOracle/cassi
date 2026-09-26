#!/usr/bin/env python3
"""Compile the qualified PA42 localized field into CassiCosmos' GPU layout.

Run from the CassiCosmos repository root:
    python tools/build_field_particle_seed.py

The source hash is pinned deliberately. A different Theory artifact must be
reviewed and adopted explicitly rather than entering the runtime by accident.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "CassiTheory" / "runs" / "20260902_particle_carrier_resolution_recovery" / "fields_resolution_X2_block01.npz"
OUTPUT = ROOT / "data" / "field_particles" / "localized_x2_n29.f32"
MANIFEST = OUTPUT.with_suffix(".json")
SOURCE_SHA256 = "db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0"

FIELD_ORDER = (
    "psi_0_real",
    "psi_0_imag",
    "psi_1_real",
    "psi_1_imag",
    "h_1",
    "h_2",
    "h_3",
    "chi_real",
    "chi_imag",
    "a_x_1",
    "a_x_2",
    "a_x_3",
    "a_y_1",
    "a_y_2",
    "a_y_3",
    "a_z_1",
    "a_z_2",
    "a_z_3",
)
COEFFICIENTS = {
    "phi": 1.618033988749895,
    "u_rho": 4.0,
    "u_phi": 4.0,
    "gamma_x": 1.0,
    "u_H": 4.0,
    "k_Cx": 1.0,
    "e_C": 0.75,
    "h_C": 2.9598260763447164,
    "u_C": 1.0,
    "q_C": 4.0,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    actual_source_hash = sha256(SOURCE)
    if actual_source_hash != SOURCE_SHA256:
        raise SystemExit(
            f"refusing unreviewed seed: {SOURCE}\n"
            f"expected {SOURCE_SHA256}\nactual   {actual_source_hash}"
        )

    with np.load(SOURCE, allow_pickle=False) as source:
        required = {"x", "psi_real", "psi_imag", "h", "a", "c"}
        if set(source.files) != required:
            raise SystemExit(f"unexpected source fields: {sorted(source.files)}")
        x = np.asarray(source["x"], dtype=np.float64)
        psi_real = np.asarray(source["psi_real"], dtype=np.float64)
        psi_imag = np.asarray(source["psi_imag"], dtype=np.float64)
        h = np.asarray(source["h"], dtype=np.float64)
        a = np.asarray(source["a"], dtype=np.float64)
        carrier = np.asarray(source["c"], dtype=np.float64)

    n = x.size
    expected_shapes = {
        "psi_real": (n, n, n, 2),
        "psi_imag": (n, n, n, 2),
        "h": (n, n, n, 3),
        "a": (n, n, n, 3, 3),
        "c": (n, n, n),
    }
    actual_shapes = {
        "psi_real": psi_real.shape,
        "psi_imag": psi_imag.shape,
        "h": h.shape,
        "a": a.shape,
        "c": carrier.shape,
    }
    if actual_shapes != expected_shapes:
        raise SystemExit(f"unexpected source shapes: {actual_shapes}")
    if n < 3 or not np.allclose(np.diff(x), x[1] - x[0], rtol=0.0, atol=1e-14):
        raise SystemExit("source grid is not uniformly spaced")

    # Theory arrays are indexed [x,y,z]. Flattening in Fortran order makes x
    # the fastest coordinate, matching id = x + N*(y + N*z) in GLSL/GDScript.
    state = np.stack(
        (
            psi_real[..., 0],
            psi_imag[..., 0],
            psi_real[..., 1],
            psi_imag[..., 1],
            h[..., 0],
            h[..., 1],
            h[..., 2],
            carrier,
            np.zeros_like(carrier),
            a[..., 0, 0],
            a[..., 0, 1],
            a[..., 0, 2],
            a[..., 1, 0],
            a[..., 1, 1],
            a[..., 1, 2],
            a[..., 2, 0],
            a[..., 2, 1],
            a[..., 2, 2],
        ),
        axis=-1,
    )
    state = np.ascontiguousarray(state.transpose(2, 1, 0, 3), dtype="<f4")
    if not np.isfinite(state).all():
        raise SystemExit("source contains non-finite values")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(state.tobytes(order="C"))
    output_hash = sha256(OUTPUT)
    dx = float(x[1] - x[0])
    dv = dx**3
    charge_f32 = float(np.sum(state[..., 7].astype(np.float64) ** 2) * dv)
    manifest = {
        "schema": "cassi.field-particle-seed.v1",
        "source": str(SOURCE.relative_to(ROOT.parent)).replace("\\", "/"),
        "source_sha256": actual_source_hash,
        "output": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "output_sha256": output_hash,
        "dtype": "little-endian float32",
        "layout": "z,y,x,component; x-fast cells; 18 interleaved scalars per cell",
        "field_order": list(FIELD_ORDER),
        "grid_n": n,
        "radius": float(max(abs(x[0]), abs(x[-1]))),
        "extent": float(x[-1] - x[0]),
        "dx": dx,
        "cells": n**3,
        "bytes": OUTPUT.stat().st_size,
        "charge_float32": charge_f32,
        "omega_c": 0.0034164531971490053,
        "physical_energy_float64": 1.5251878559994063,
        "outer_carrier_fraction_float64": 0.00010708172350337447,
        "coefficients": COEFFICIENTS,
        "temporal_coefficients": {
            "c_psi": 1.0,
            "c_h": 1.0,
            "e_tx": 1.0,
            "status": "experimental unit normalization; PA43 selection remains open",
        },
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size} bytes)")
    print(f"sha256 {output_hash}")
    print(f"float32 charge {charge_f32:.12f}")


if __name__ == "__main__":
    main()
