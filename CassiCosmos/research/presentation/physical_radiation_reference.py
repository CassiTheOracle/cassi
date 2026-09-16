#!/usr/bin/env python3
"""Independent P0/P1 spectral reference and immutable fixture generator.

This script is never imported by Godot.  It verifies the official observer
bytes, evaluates double-precision Planck/slab controls, selects the smallest
frozen group layout that passes, and writes a data-only JSON fixture.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / "reference"
CIE_PATH = REFERENCE / "CIE_xyz_1931_2deg.csv"
CIE_METADATA_PATH = REFERENCE / "CIE_xyz_1931_2deg.metadata.json"
OUTPUT_PATH = REFERENCE / "physical_radiation_reference.json"
CIE_SHA256 = "fa663e3535a7e0763a745993a1f0a192eb0275ac46ad2d1befd7626841e713c1"

C_LIGHT = 299_792_458.0
H_PLANCK = 6.626_070_15e-34
K_BOLTZMANN = 1.380_649e-23
SIGMA_SB = 5.670_374_419e-8
TEMPERATURES_K = (2500.0, 4000.0, 6500.0, 10_000.0, 20_000.0)
GROUP_CANDIDATES = (16, 32, 64)
CHROMATICITY_TOLERANCE = 0.006
POWER_TOLERANCE = 5e-8


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_observer() -> tuple[list[float], list[list[float]], dict]:
    raw = CIE_PATH.read_bytes()
    actual = sha256_bytes(raw)
    if actual != CIE_SHA256:
        raise ValueError(f"observer SHA-256 mismatch: {actual}")
    metadata = json.loads(CIE_METADATA_PATH.read_text(encoding="utf-8"))
    declared = next(row["checksum"] for row in metadata["checksums"] if row["hashMethod"] == "sha256")
    if declared != CIE_SHA256:
        raise ValueError(f"observer metadata SHA-256 mismatch: {declared}")
    wavelengths: list[float] = []
    xyz: list[list[float]] = []
    with CIE_PATH.open(newline="", encoding="ascii") as handle:
        for row in csv.reader(handle):
            if len(row) != 4:
                raise ValueError("observer row must contain wavelength,x_bar,y_bar,z_bar")
            wavelengths.append(float(row[0]))
            xyz.append([float(row[1]), float(row[2]), float(row[3])])
    if wavelengths != [float(value) for value in range(360, 831)]:
        raise ValueError("observer wavelength coverage must be 360..830 nm at 1 nm")
    if any(not math.isfinite(value) or value < 0.0 for row in xyz for value in row):
        raise ValueError("observer contains invalid colour-matching values")
    return wavelengths, xyz, metadata


def planck_lambda(wavelength_m: float, temperature_k: float) -> float:
    exponent = H_PLANCK * C_LIGHT / (wavelength_m * K_BOLTZMANN * temperature_k)
    if exponent > 700.0:
        return 0.0
    return (2.0 * H_PLANCK * C_LIGHT * C_LIGHT) / (wavelength_m ** 5 * math.expm1(exponent))


def trapezoid(xs: Iterable[float], ys: Iterable[float]) -> float:
    x = list(xs)
    y = list(ys)
    return sum(0.5 * (y[i] + y[i + 1]) * (x[i + 1] - x[i]) for i in range(len(x) - 1))


def segment_integral(wavelength_nm: list[float], values: list[float], lo_nm: float, hi_nm: float) -> float:
    if not (lo_nm < hi_nm):
        raise ValueError("invalid integration segment")
    points = [lo_nm]
    points.extend(value for value in wavelength_nm if lo_nm < value < hi_nm)
    points.append(hi_nm)

    def sample(x: float) -> float:
        if x <= wavelength_nm[0]:
            return values[0]
        if x >= wavelength_nm[-1]:
            return values[-1]
        lower = int(math.floor(x - wavelength_nm[0]))
        fraction = x - wavelength_nm[lower]
        return values[lower] * (1.0 - fraction) + values[lower + 1] * fraction

    return trapezoid((value * 1e-9 for value in points), (sample(value) for value in points))


def group_edges(group_count: int) -> list[float]:
    indices = [round(index * 470 / group_count) for index in range(group_count + 1)]
    if len(set(indices)) != len(indices):
        raise ValueError("group boundaries collapsed")
    return [360.0 + float(index) for index in indices]


def chromaticity(xyz: list[float]) -> list[float]:
    total = sum(xyz)
    return [xyz[0] / total, xyz[1] / total] if total > 0.0 else [0.0, 0.0]


def build_group_layout(group_count: int, wavelengths_nm: list[float], cmf: list[list[float]]) -> dict:
    edges_nm = group_edges(group_count)
    visible: list[dict] = []
    for index, (lo_nm, hi_nm) in enumerate(zip(edges_nm, edges_nm[1:])):
        cmf_integrals = [
            segment_integral(wavelengths_nm, [row[channel] for row in cmf], lo_nm, hi_nm)
            for channel in range(3)
        ]
        visible.append({
            "index": index + 1,
            "kind": "visible",
            "wavelength_lo_nm": lo_nm,
            "wavelength_hi_nm": hi_nm,
            "frequency_lo_hz": C_LIGHT / (hi_nm * 1e-9),
            "frequency_hi_hz": C_LIGHT / (lo_nm * 1e-9),
            "observer_xyz_integral_m": cmf_integrals,
        })
    groups = [
        {
            "index": 0,
            "kind": "ultraviolet_tail",
            "wavelength_hi_nm": 360.0,
            "frequency_lo_hz": C_LIGHT / (360e-9),
            "frequency_hi_semantic": "infinity",
        },
        *visible,
        {
            "index": group_count + 1,
            "kind": "infrared_tail",
            "wavelength_lo_nm": 830.0,
            "frequency_lo_hz": 0.0,
            "frequency_hi_hz": C_LIGHT / (830e-9),
        },
    ]
    identity = {
        "schema_version": "1.0.0",
        "layout_id": f"cie1931-visible-{group_count}-plus-bolometric-tails",
        "visible_group_count": group_count,
        "total_group_count": group_count + 2,
        "frequency_frame": "material_rest_frame_prescribed",
        "integration": "group-integrated wavelength radiance; CIE piecewise-linear 1 nm observer",
        "reconstruction": "constant spectral radiance per wavelength within each visible interval",
        "observer_sha256": CIE_SHA256,
        "groups": groups,
    }
    identity["layout_sha256"] = sha256_bytes(canonical_bytes(identity))
    return identity


def integrate_temperature(temperature_k: float, layout: dict, wavelengths_nm: list[float], cmf: list[list[float]]) -> dict:
    spectral = [planck_lambda(value * 1e-9, temperature_k) for value in wavelengths_nm]
    exact_xyz = [
        trapezoid((value * 1e-9 for value in wavelengths_nm),
                  (spectral[i] * cmf[i][channel] for i in range(len(wavelengths_nm))))
        for channel in range(3)
    ]
    visible_groups: list[float] = []
    grouped_xyz = [0.0, 0.0, 0.0]
    for group in layout["groups"][1:-1]:
        lo_nm = group["wavelength_lo_nm"]
        hi_nm = group["wavelength_hi_nm"]
        radiance = segment_integral(wavelengths_nm, spectral, lo_nm, hi_nm)
        visible_groups.append(radiance)
        width_m = (hi_nm - lo_nm) * 1e-9
        average = radiance / width_m
        for channel in range(3):
            grouped_xyz[channel] += average * group["observer_xyz_integral_m"][channel]
    bolometric = SIGMA_SB * temperature_k ** 4 / math.pi
    visible = sum(visible_groups)
    # The observer interval partitions the finite visible integral.  The two
    # positive bolometric tails are evaluated by a wide log-wavelength
    # quadrature and closed by the exact Stefan-Boltzmann total.
    log_lo = math.log(1e-11)
    log_360 = math.log(360e-9)
    log_830 = math.log(830e-9)
    log_hi = math.log(1.0)

    def log_integral(a: float, b: float, count: int = 20000) -> float:
        step = (b - a) / count
        total = 0.0
        previous_x = a
        previous = planck_lambda(math.exp(a), temperature_k) * math.exp(a)
        for index in range(1, count + 1):
            current_x = a + index * step
            current = planck_lambda(math.exp(current_x), temperature_k) * math.exp(current_x)
            total += 0.5 * (previous + current) * (current_x - previous_x)
            previous_x = current_x
            previous = current
        return total

    ultraviolet = log_integral(log_lo, log_360)
    infrared_raw = log_integral(log_830, log_hi)
    tail_sum = max(0.0, bolometric - visible)
    tail_ratio = ultraviolet / max(ultraviolet + infrared_raw, 1e-300)
    ultraviolet = tail_sum * tail_ratio
    infrared = tail_sum - ultraviolet
    group_values = [ultraviolet, *visible_groups, infrared]
    power_error = abs(sum(group_values) / bolometric - 1.0)
    exact_xy = chromaticity(exact_xyz)
    grouped_xy = chromaticity(grouped_xyz)
    chromaticity_error = max(abs(exact_xy[i] - grouped_xy[i]) for i in range(2))
    return {
        "temperature_K": temperature_k,
        "bolometric_radiance_W_m2_sr": bolometric,
        "group_radiance_W_m2_sr": group_values,
        "exact_XYZ_W_m2_sr": exact_xyz,
        "group_XYZ_W_m2_sr": grouped_xyz,
        "exact_xy": exact_xy,
        "group_xy": grouped_xy,
        "relative_power_error": power_error,
        "max_chromaticity_error": chromaticity_error,
    }


def transfer(intensity_in: float, source: float, alpha: float, distance: float) -> float:
    if alpha < 0.0 or distance < 0.0:
        raise ValueError("alpha and distance must be nonnegative")
    tau = alpha * distance
    if tau == 0.0:
        return intensity_in + (source * alpha) * distance
    absorbed = -math.expm1(-tau)
    return intensity_in * math.exp(-tau) + source * absorbed


def build_fixture() -> tuple[dict, list[str]]:
    wavelengths, cmf, metadata = load_observer()
    layouts: list[dict] = []
    failures: list[str] = []
    selected: dict | None = None
    selected_cases: list[dict] = []
    candidate_receipts: list[dict] = []
    for count in GROUP_CANDIDATES:
        layout = build_group_layout(count, wavelengths, cmf)
        cases = [integrate_temperature(value, layout, wavelengths, cmf) for value in TEMPERATURES_K]
        maximum_colour = max(row["max_chromaticity_error"] for row in cases)
        maximum_power = max(row["relative_power_error"] for row in cases)
        passed = maximum_colour <= CHROMATICITY_TOLERANCE and maximum_power <= POWER_TOLERANCE
        candidate_receipts.append({
            "visible_group_count": count,
            "layout_sha256": layout["layout_sha256"],
            "max_chromaticity_error": maximum_colour,
            "max_relative_power_error": maximum_power,
            "passed": passed,
        })
        layouts.append(layout)
        if selected is None and passed:
            selected = layout
            selected_cases = cases
    if selected is None:
        failures.append("no spectral group candidate passed")
        selected = layouts[-1]
        selected_cases = [integrate_temperature(value, selected, wavelengths, cmf) for value in TEMPERATURES_K]

    slab_cases = []
    for tau in (0.0, 1e-8, 0.1, 1.0, 10.0):
        alpha = tau
        measured = transfer(0.25, 2.0, alpha, 1.0)
        exact = 0.25 if tau == 0.0 else 0.25 * math.exp(-tau) + 2.0 * (1.0 - math.exp(-tau))
        error = abs(measured - exact) / max(abs(exact), 1e-300)
        slab_cases.append({"tau": tau, "computed": measured, "exact": exact, "relative_error": error})
        if error > 2e-12:
            failures.append(f"slab tau={tau} failed: {error}")

    model = {
        "schema_version": "1.0.0",
        "model_id": "prescribed-homogeneous-lte-continuum",
        "model_revision": 1,
        "source_kind": "prescribed",
        "coupling": "prescribed",
        "qualification_scope": ["one_way_emission_absorption", "frozen_state_formal_solution"],
        "unsupported_capabilities": [
            "native_material_mapping", "coupled_thermal_state", "radiation_feedback",
            "moving_multigroup_transport", "non_lte_populations", "line_radiation",
            "physical_unresolved_emitters",
        ],
        "equation_references": [
            "research/presentation/physical_radiation_design.md#51-one-way-observation",
            "../CassiTheory/turbulence/cassi-radiative-material-closure.md",
        ],
        "unit_map": {
            "schema_version": "1.0.0",
            "length_m_per_sim": 1.0,
            "time_s_per_physics_sim": 1.0,
            "mass_kg_per_sim": 1.0,
            "temperature_K_per_value": 1.0,
            "radiance_scale_W_m2_sr": 100_000_000.0,
            "c_gamma_sim": C_LIGHT,
        },
        "material": {
            "temperature_K": 6500.0,
            "absorption_m_inv": 0.06,
            "scattering_m_inv": 0.0,
            "boundary_radiance_W_m2_sr": 0.0,
            "geometry": "homogeneous sphere on a supplied observation bounds snapshot",
        },
        "observer": {
            "id": "CIE-1931-2deg",
            "doi": metadata["identifier"]["identifier"],
            "sha256": CIE_SHA256,
            "license": metadata["rightsList"][0]["rightsIdentifier"],
            "wavelength_nm": [360.0, 830.0, 1.0],
            "white_point": "CIE-D65",
            "xyz_to_linear_rgb": "IEC-61966-2-1-sRGB",
            "gamut_map": "clip-negative-linear-components-after-preserving-raw-XYZ",
            "photometric_normalization": "absolute spectral radiance; no source white normalization",
        },
    }
    model["unit_map"]["unit_map_sha256"] = sha256_bytes(canonical_bytes(model["unit_map"]))
    model["model_sha256"] = sha256_bytes(canonical_bytes(model))
    snapshot = {
        "schema_version": "1.0.0",
        "producer": "physical_radiation_reference.py",
        "source_kind": "prescribed",
        "coupling": "prescribed",
        "model_sha256": model["model_sha256"],
        "unit_map_sha256": model["unit_map"]["unit_map_sha256"],
        "group_layout_sha256": selected["layout_sha256"],
        "state_epoch": 1,
        "reset_epoch": 1,
        "executed_step": 0,
        "physical_time_s": 0.0,
        "integration_interval_s": 0.0,
        "coordinate_frame": "simulation_world_relative_to_frame_origin",
        "frame_origin_sim": [0.0, 0.0, 0.0],
        "geometry_kind": "homogeneous_sphere",
        "center_sim": [0.0, 0.0, 0.0],
        "radius_sim": 25.0,
        "temperature_K": 6500.0,
        "absorption_m_inv": 0.06,
        "scattering_m_inv": 0.0,
        "boundary_radiance_W_m2_sr": 0.0,
        "valid": True,
        "readiness": "ready_prescribed_preview",
        "unavailable_capabilities": model["unsupported_capabilities"],
    }
    snapshot["snapshot_sha256"] = sha256_bytes(canonical_bytes(snapshot))
    fixture = {
        "schema_version": "1.0.0",
        "generated_by": "physical_radiation_reference.py",
        "observer_asset": {
            "path": "research/presentation/reference/CIE_xyz_1931_2deg.csv",
            "metadata_path": "research/presentation/reference/CIE_xyz_1931_2deg.metadata.json",
            "sha256": CIE_SHA256,
        },
        "candidate_receipts": candidate_receipts,
        "selected_layout": selected,
        "model": model,
        "prescribed_snapshot": snapshot,
        "temperature_controls": selected_cases,
        "slab_controls": slab_cases,
    }
    fixture["fixture_sha256"] = sha256_bytes(canonical_bytes(fixture))
    return fixture, failures


def verify_fixture(fixture: dict) -> list[str]:
    failures: list[str] = []
    selected = fixture["selected_layout"]
    for row in fixture["temperature_controls"]:
        if row["relative_power_error"] > POWER_TOLERANCE:
            failures.append(f"power T={row['temperature_K']}: {row['relative_power_error']}")
        if row["max_chromaticity_error"] > CHROMATICITY_TOLERANCE:
            failures.append(f"colour T={row['temperature_K']}: {row['max_chromaticity_error']}")
        values = row["group_radiance_W_m2_sr"] + row["exact_XYZ_W_m2_sr"] + row["group_XYZ_W_m2_sr"]
        if any(not math.isfinite(value) or value < 0.0 for value in values):
            failures.append(f"nonfinite/negative spectral value T={row['temperature_K']}")
    if selected["visible_group_count"] not in GROUP_CANDIDATES:
        failures.append("selected unsupported group count")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true", help="verify and print the frozen control receipt")
    parser.add_argument("--write", action="store_true", help="write the immutable JSON fixture")
    args = parser.parse_args()
    fixture, failures = build_fixture()
    failures.extend(verify_fixture(fixture))
    if args.write:
        OUTPUT_PATH.write_text(json.dumps(fixture, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    receipt = {
        "result": "PASS" if not failures else "FAIL",
        "observer_sha256": CIE_SHA256,
        "fixture_sha256": fixture["fixture_sha256"],
        "selected_visible_groups": fixture["selected_layout"]["visible_group_count"],
        "candidates": fixture["candidate_receipts"],
        "maximum_slab_relative_error": max(row["relative_error"] for row in fixture["slab_controls"]),
        "failures": failures,
    }
    if args.verify or not args.write:
        print(json.dumps(receipt, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
