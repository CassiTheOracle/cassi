#!/usr/bin/env python3
"""Independently decode and verify the field-particle runtime state.

The verifier does not import the converter or Godot implementation. It rebuilds
PA12 directly with NumPy and can compare selected GPU Hamiltonian gradients to
whole-Hamiltonian central differences.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
THEORY_ROOT = ROOT.parent / "CassiTheory"
SEED = ROOT / "data" / "field_particles" / "localized_x2_n29.f32"
MANIFEST = SEED.with_suffix(".json")
SOURCE = THEORY_ROOT / "runs" / "20260902_particle_carrier_resolution_recovery" / "fields_resolution_X2_block01.npz"
EXPECTED_SOURCE_SHA256 = "db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0"
EXPECTED_SEED_SHA256 = "5d43794099f52f4343486a2f1b38787356301153bd48d033d0d42451160ab6d3"
EXPECTED_MANIFEST_SHA256 = "280b44e7962e228a4791c6bb3506479395ccefe5068c1f0e4aa8a1a2c245ae8c"
EXPECTED_ENERGY = 1.5251878559994063
EXPECTED_ORDER = (
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    checks = {
        "manifest_sha256": sha256(MANIFEST) == EXPECTED_MANIFEST_SHA256,
        "source_sha256": sha256(SOURCE) == EXPECTED_SOURCE_SHA256,
        "seed_sha256": sha256(SEED) == EXPECTED_SEED_SHA256,
        "schema": manifest.get("schema") == "cassi.field-particle-seed.v1",
        "field_order": tuple(manifest.get("field_order", ())) == EXPECTED_ORDER,
        "grid": manifest.get("grid_n") == 29
        and manifest.get("radius") == 4.0
        and abs(manifest.get("dx", math.nan) - 2.0 / 7.0) <= 1e-15,
        "particle_parameters": manifest.get("coefficients", {}).get("h_C")
        == 2.9598260763447164
        and manifest.get("coefficients", {}).get("q_C") == 4.0
        and manifest.get("omega_c") == 0.0034164531971490053,
    }
    if not all(checks.values()):
        raise ValueError(f"manifest/provenance failure: {checks}")
    return manifest


def decode(path: Path, n: int) -> np.ndarray:
    values = np.fromfile(path, dtype="<f4")
    expected = n**3 * len(EXPECTED_ORDER)
    if values.size != expected:
        raise ValueError(f"{path}: expected {expected} floats, found {values.size}")
    # Runtime order is z,y,x,component with x-fast cells. Convert to the source
    # x,y,z,component convention for all independent calculations.
    return values.reshape(n, n, n, len(EXPECTED_ORDER)).transpose(2, 1, 0, 3)


def compile_source_f32() -> np.ndarray:
    with np.load(SOURCE, allow_pickle=False) as source:
        psi_real = source["psi_real"]
        psi_imag = source["psi_imag"]
        h = source["h"]
        a = source["a"]
        carrier = source["c"]
    return np.stack(
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
    ).astype(np.float32)


def derivatives(field: np.ndarray, dx: float) -> tuple[np.ndarray, ...]:
    return tuple(np.gradient(field, dx, axis=axis, edge_order=2) for axis in range(3))


def energy_components(
    state: np.ndarray, manifest: dict[str, Any]
) -> dict[str, float]:
    coefficients = manifest["coefficients"]
    phi = coefficients["phi"]
    dx = manifest["dx"]
    dv = dx**3
    psi = np.stack(
        (state[..., 0] + 1j * state[..., 1], state[..., 2] + 1j * state[..., 3]),
        axis=-1,
    ).astype(np.complex128)
    h = state[..., 4:7].astype(np.float64)
    carrier = (state[..., 7] + 1j * state[..., 8]).astype(np.complex128)
    gauge = state[..., 9:18].reshape(*state.shape[:3], 3, 3).astype(np.float64)
    sigma = np.asarray(
        (
            ((0.0, 1.0), (1.0, 0.0)),
            ((0.0, -1.0j), (1.0j, 0.0)),
            ((1.0, 0.0), (0.0, -1.0)),
        ),
        dtype=np.complex128,
    )
    generators = sigma / 2.0

    dpsi = np.stack(derivatives(psi, dx), axis=-2)
    gauge_psi = np.einsum("...ia,abc,...c->...ib", gauge, generators, psi)
    covariant_psi = dpsi - 1j * gauge_psi
    rho = np.sum(np.abs(psi) ** 2, axis=-1)
    spin = np.einsum("...b,abc,...c->...a", psi.conj(), sigma, psi).real
    delta_phi = 0.5 * (
        (1.0 - phi) * rho + (1.0 + phi) * np.sum(h * spin, axis=-1)
    )

    da = derivatives(gauge, dx)
    curvature = np.empty((*state.shape[:3], 3, 3, 3), dtype=np.float64)
    for i in range(3):
        for j in range(3):
            curvature[..., i, j, :] = (
                da[i][..., j, :]
                - da[j][..., i, :]
                + np.cross(gauge[..., i, :], gauge[..., j, :])
            )
    dh = np.stack(derivatives(h, dx), axis=-2)
    covariant_h = dh + np.cross(gauge, h[..., None, :])
    dc = np.stack(derivatives(carrier, dx), axis=-1)
    carrier_density = np.abs(carrier) ** 2

    return {
        "psi_gradient": float(0.5 * np.sum(np.abs(covariant_psi) ** 2) * dv),
        "rho_potential": float(
            coefficients["u_rho"] / 4.0 * np.sum((rho - 1.0) ** 2) * dv
        ),
        "composition_potential": float(
            coefficients["u_phi"] / 2.0 * np.sum(delta_phi**2) * dv
        ),
        "curvature": float(
            coefficients["gamma_x"] / 4.0 * np.sum(curvature**2) * dv
        ),
        "h_gradient": float(
            coefficients["gamma_x"] / 2.0 * np.sum(covariant_h**2) * dv
        ),
        "h_potential": float(
            coefficients["u_H"]
            / 4.0
            * np.sum((np.sum(h**2, axis=-1) - 1.0) ** 2)
            * dv
        ),
        "carrier_gradient": float(
            coefficients["k_Cx"] / 2.0 * np.sum(np.abs(dc) ** 2) * dv
        ),
        "carrier_quadratic": float(
            np.sum(
                (coefficients["e_C"] - coefficients["h_C"] * (1.0 - rho))
                * carrier_density
            )
            * dv
        ),
        "carrier_quartic": float(
            coefficients["u_C"] / 2.0 * np.sum(carrier_density**2) * dv
        ),
    }


def observables(state: np.ndarray, manifest: dict[str, Any]) -> dict[str, Any]:
    n = manifest["grid_n"]
    dx = manifest["dx"]
    dv = dx**3
    coordinate = np.arange(n, dtype=np.float64) * dx - manifest["radius"]
    x, y, z = np.meshgrid(coordinate, coordinate, coordinate, indexing="ij")
    density = state[..., 7].astype(np.float64) ** 2 + state[..., 8].astype(np.float64) ** 2
    charge = float(density.sum() * dv)
    center = np.asarray(
        [(density * axis).sum() * dv / charge for axis in (x, y, z)],
        dtype=np.float64,
    )
    radius = math.sqrt(
        float(
            (density * ((x - center[0]) ** 2 + (y - center[1]) ** 2 + (z - center[2]) ** 2)).sum()
            * dv
            / charge
        )
    )
    shell2 = np.zeros((n, n, n), dtype=bool)
    shell2[:2, :, :] = True
    shell2[-2:, :, :] = True
    shell2[:, :2, :] = True
    shell2[:, -2:, :] = True
    shell2[:, :, :2] = True
    shell2[:, :, -2:] = True
    components = energy_components(state, manifest)
    return {
        "charge": charge,
        "charge_relative_error": abs(charge - 4.0) / 4.0,
        "center": center.tolist(),
        "center_norm": float(np.linalg.norm(center)),
        "radius": radius,
        "outer_carrier_fraction": float(density[shell2].sum() / density.sum()),
        "physical_energy": sum(components.values()),
        "energy_components": components,
        "finite": bool(np.isfinite(state).all()),
    }


def selected_gradient_checks(
    state: np.ndarray,
    gradient_path: Path,
    manifest: dict[str, Any],
    fd_epsilon: float,
) -> list[dict[str, Any]]:
    n = manifest["grid_n"]
    runtime_gradient = (
        np.fromfile(gradient_path, dtype="<f4")
        .reshape(n, n, n, len(EXPECTED_ORDER))
        .transpose(2, 1, 0, 3)
    )
    selected = (
        (14, 14, 14, 0),
        (14, 14, 14, 2),
        (14, 14, 14, 4),
        (14, 14, 14, 6),
        (14, 14, 14, 7),
        (14, 14, 14, 8),
        (14, 14, 14, 9),
        (14, 14, 14, 14),
        (14, 14, 14, 17),
        (11, 14, 14, 7),
        (14, 14, 18, 0),
        (2, 14, 14, 7),
    )
    checks: list[dict[str, Any]] = []
    for x, y, z, component in selected:
        epsilon = fd_epsilon * max(1.0, abs(float(state[x, y, z, component])))
        original = float(state[x, y, z, component])
        state[x, y, z, component] = original + 2.0 * epsilon
        plus_two = sum(energy_components(state, manifest).values())
        state[x, y, z, component] = original + epsilon
        plus_one = sum(energy_components(state, manifest).values())
        state[x, y, z, component] = original - epsilon
        minus_one = sum(energy_components(state, manifest).values())
        state[x, y, z, component] = original - 2.0 * epsilon
        minus_two = sum(energy_components(state, manifest).values())
        state[x, y, z, component] = original
        reference = (-plus_two + 8.0 * plus_one - 8.0 * minus_one + minus_two) / (
            12.0 * epsilon
        )
        runtime = float(runtime_gradient[x, y, z, component])
        absolute_error = abs(runtime - reference)
        scale = max(abs(reference), 2.0e-4)
        tolerance = 6.0e-5 + 0.08 * scale
        checks.append(
            {
                "index": [x, y, z, component],
                "component": EXPECTED_ORDER[component],
                "reference": reference,
                "runtime": runtime,
                "absolute_error": absolute_error,
                "tolerance": tolerance,
                "pass": absolute_error <= tolerance,
            }
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, default=SEED)
    parser.add_argument("--gradient", type=Path)
    parser.add_argument("--expect-seed-exact", action="store_true")
    parser.add_argument("--fd-epsilon", type=float, default=1.0 / 32.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest = load_manifest()
    state = decode(args.state, manifest["grid_n"])
    source_state = compile_source_f32()
    metrics = observables(state, manifest)
    vacuum = np.asarray(
        (manifest["coefficients"]["phi"] ** -0.5, manifest["coefficients"]["phi"] ** -1.0),
        dtype=np.float32,
    )
    shell = np.zeros(state.shape[:3], dtype=bool)
    shell[[0, -1], :, :] = True
    shell[:, [0, -1], :] = True
    shell[:, :, [0, -1]] = True
    expected_shell = np.zeros((int(shell.sum()), len(EXPECTED_ORDER)), dtype=np.float32)
    expected_shell[:, 0] = vacuum[0]
    expected_shell[:, 2] = vacuum[1]
    expected_shell[:, 6] = 1.0

    checks: dict[str, bool] = {
        "source_to_seed_byte_identity": np.array_equal(decode(SEED, 29), source_state),
        "requested_state_seed_identity": (
            np.array_equal(state, source_state) if args.expect_seed_exact else True
        ),
        "outer_shell_exact": np.array_equal(state[shell], expected_shell),
        "all_values_finite": metrics["finite"],
        "charge": metrics["charge_relative_error"] <= 2.0e-5,
        "center": metrics["center_norm"] <= manifest["dx"],
        "outer_fraction": metrics["outer_carrier_fraction"] <= 2.0e-4,
        "energy": abs(metrics["physical_energy"] - EXPECTED_ENERGY) / EXPECTED_ENERGY
        <= 5.0e-4,
    }
    gradient_checks: list[dict[str, Any]] = []
    if args.gradient is not None:
        gradient_checks = selected_gradient_checks(
            state.copy(), args.gradient, manifest, args.fd_epsilon
        )
        checks["selected_hamiltonian_gradients"] = all(
            item["pass"] for item in gradient_checks
        )

    result = {
        "schema": "cassi.field-particle-runtime-verification.v1",
        "state": str(args.state),
        "checks": checks,
        "metrics": metrics,
        "gradient_checks": gradient_checks,
        "pass": all(checks.values()),
    }
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
