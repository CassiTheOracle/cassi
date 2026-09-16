#!/usr/bin/env python3
"""Build and verify the conditional H/H+ physical-matter bundle.

The runtime consumes only the generated, hash-bound JSON.  This generator keeps
external atomic provenance and the CPU constitutive oracle in one place.  It
never imports or mutates Godot state.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "research/presentation/reference/cassi_physical_matter_model.json"
DEFAULT_RECEIPT = ROOT / "_diag/physical_matter/model_reference_receipt.json"
CIE_PATH = ROOT / "research/presentation/reference/CIE_xyz_1931_2deg.csv"

C_LIGHT = 299_792_458.0
H_PLANCK = 6.626_070_15e-34
K_BOLTZMANN = 1.380_649e-23
M_HYDROGEN = 1.673_557_5e-27
M_ELECTRON = 9.109_383_7139e-31
E_CHARGE = 1.602_176_634e-19
EPSILON_0 = 8.854_187_8188e-12
SIGMA_T = 6.652_458_7051e-29
EV_J = E_CHARGE
PI = math.pi

NIST_LINE_URL = (
    "https://physics.nist.gov/cgi-bin/ASD/lines1.pl?A_out=0&I_scale_type=1&"
    "J_out=on&allowed_out=1&bibrefs=1&conf_out=on&de=0&en_unit=0&enrg_out=on&"
    "f_out=on&forbid_out=1&format=0&g_out=on&intens_out=on&limits_type=0&"
    "line_out=0&low_w=90&max_low_enrg=&max_str=&max_upp_enrg=&min_accur=&"
    "min_intens=&min_str=&order_out=0&output=0&output_type=2&page_size=2000&"
    "plot_out=0&show_av=2&show_calc_wl=1&show_obs_wl=1&spectra=H%20I&"
    "submit=Retrieve%20Data&term_out=on&tsb_value=0&unc_out=1&unit=1&upp_w=20000"
)
NIST_LEVEL_URL = (
    "https://physics.nist.gov/cgi-bin/ASD/energy1.pl?biblio=1&conf_out=1&j_out=1&"
    "lande_out=1&level_out=1&perc_out=1&spectrum=H%20I&term_out=1&format=2&"
    "output=0&page_size=500"
)
NIST_LINE_RESPONSE_SHA256 = "e27f970b38357b7b928d8183db4d532816b7cf0734a1d26561f65a948a7e6c3a"
NIST_LEVEL_RESPONSE_SHA256 = "991a4b1d780b1b2f82ba5379414d35fce097e7e01a0308e841a1dc23deb77d6f"
NIST_ASD_VERSION = "5.12"
NIST_ACCESS_DATE = "2026-09-10"

# Unresolved shell-to-shell H I records selected from the source query above.
# Wavelengths follow the NIST query convention (vacuum below 200 nm, air from
# 200 to 2000 nm, vacuum above 2000 nm). Runtime frequencies instead use the
# consistent NIST shell-centre level differences below.
# lower_n, upper_n, displayed wavelength nm, A_ki s^-1, f_ik
NIST_TRANSITIONS = (
    (1, 2, 121.56701, 4.6986e8, 4.1641e-1),
    (1, 3, 102.57220, 5.5751e7, 7.9142e-2),
    (1, 4, 97.253650, 1.2785e7, 2.9006e-2),
    (1, 5, 94.974287, 4.1250e6, 1.3945e-2),
    (1, 6, 93.780331, 1.6440e6, 7.8035e-3),
    (2, 3, 656.2819, 4.4101e7, 6.4108e-1),
    (2, 4, 486.1333, 8.4193e6, 1.1938e-1),
    (2, 5, 434.0471, 2.5304e6, 4.4694e-2),
    (2, 6, 410.17415, 9.7320e5, 2.2105e-2),
    (3, 4, 1875.0976, 8.9860e6, 8.4254e-1),
    (3, 5, 1281.8070, 2.2008e6, 1.5066e-1),
    (3, 6, 1093.8086, 7.7829e5, 5.5870e-2),
    (4, 5, 4052.269, 2.6993e6, 1.0383),
    (4, 6, 2625.868, 7.7110e5, 1.7935e-1),
    (5, 6, 7459.84, 1.0254e6, 1.2319),
)

# NIST ASD shell-centre levels, cm^-1. The continuum limit is from HDEL.
SHELL_LEVEL_CM_INV = (0.0, 82_259.158, 97_492.304, 102_823.904, 105_291.657, 106_632.1681)
IONIZATION_LIMIT_CM_INV = 109_678.771_743_07
LEVEL_DEGENERACIES = (2.0, 8.0, 18.0, 32.0, 50.0, 72.0)

# Exactly 24 group intervals. Edges isolate every visible Balmer line and the
# important hydrogen continuum neighborhoods while retaining radio-to-X-ray
# bolometric coverage.
FREQUENCY_EDGES_HZ = (
    1.0e12, 2.0e13, 5.0e13, 8.0e13, 1.0e14,
    1.25e14, 1.50e14, 1.90e14, 2.25e14, 2.55e14,
    3.10e14, 3.65e14, 4.00e14, 5.20e14, 6.50e14,
    7.10e14, 7.60e14, 8.225e14, 1.20e15, 2.20e15,
    2.70e15, 3.00e15, 3.12e15, 3.24e15, 1.00e18,
)
TEMPERATURE_GRID_K = np.geomspace(10.0, 1.0e8, 96)
RATE_TEMPERATURE_MIN_K = 10.0
RATE_TEMPERATURE_MAX_K = 1.0e8


def _validated_rate_temperature(temperature_k: np.ndarray | float) -> np.ndarray:
    """Validate the finite temperature domain used by all tabulated rates."""
    temperature = np.asarray(temperature_k, dtype=np.float64)
    if (
        not np.all(np.isfinite(temperature))
        or np.any(temperature < RATE_TEMPERATURE_MIN_K)
        or np.any(temperature > RATE_TEMPERATURE_MAX_K)
    ):
        raise ValueError("temperature must be finite and within the tabulated rate domain")
    return temperature




def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def group_index(frequency_hz: float) -> int:
    edges = FREQUENCY_EDGES_HZ
    if frequency_hz < edges[0] or frequency_hz > edges[-1]:
        raise ValueError(f"frequency outside group layout: {frequency_hz:.9e}")
    if frequency_hz == edges[-1]:
        return len(edges) - 2
    return int(np.searchsorted(np.asarray(edges), frequency_hz, side="right") - 1)


def planck_nu(frequency_hz: np.ndarray | float, temperature_k: float) -> np.ndarray:
    nu = np.asarray(frequency_hz, dtype=np.float64)
    x = H_PLANCK * nu / (K_BOLTZMANN * float(temperature_k))
    denominator = np.expm1(np.minimum(x, 700.0))
    return np.where(x < 700.0, 2.0 * H_PLANCK * nu**3 / C_LIGHT**2 / denominator, 0.0)


def saha_ion_fraction(temperature_k: float, hydrogen_number_density_m3: float) -> float:
    temperature = float(temperature_k)
    density = float(hydrogen_number_density_m3)
    if not math.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("temperature must be finite and positive")
    if not math.isfinite(density) or density <= 0.0:
        raise ValueError("hydrogen density must be finite and positive")
    chi = H_PLANCK * C_LIGHT * IONIZATION_LIMIT_CM_INV * 100.0
    saha = 2.0 * (2.0 * PI * M_ELECTRON * K_BOLTZMANN * temperature / H_PLANCK**2) ** 1.5
    ratio = saha * math.exp(-chi / (K_BOLTZMANN * temperature)) / density
    # Stable positive root of x^2/(1-x)=ratio.
    return 2.0 * ratio / (ratio + math.sqrt(ratio * ratio + 4.0 * ratio)) if ratio > 0.0 else 0.0


def neutral_boltzmann_fractions(temperature_k: float) -> np.ndarray:
    energy = np.asarray(SHELL_LEVEL_CM_INV, dtype=np.float64) * H_PLANCK * C_LIGHT * 100.0
    weights = np.asarray(LEVEL_DEGENERACIES, dtype=np.float64) * np.exp(
        -energy / (K_BOLTZMANN * float(temperature_k))
    )
    return weights / np.sum(weights)


def collisional_ionization_m3_s(temperature_k: np.ndarray | float) -> np.ndarray:
    """Voronov-form H I electron-impact ionization coefficient."""
    temperature = _validated_rate_temperature(temperature_k)
    ionization_temperature = H_PLANCK * C_LIGHT * IONIZATION_LIMIT_CM_INV * 100.0 / K_BOLTZMANN
    u = ionization_temperature / temperature
    # Voronov (1997) H I: A=2.91e-8 cm3/s, P=0, X=0.232, K=0.39.
    return 2.91e-14 * np.power(u, 0.39) * np.exp(-u) / (0.232 + u)


def case_a_recombination_m3_s(temperature_k: np.ndarray | float) -> np.ndarray:
    """Hui-Gnedin case-A hydrogen radiative recombination fit."""
    temperature = _validated_rate_temperature(temperature_k)
    lam = 315_614.0 / temperature
    return 1.269e-19 * np.power(lam, 1.503) / np.power(1.0 + np.power(lam / 0.522, 0.47), 1.923)


def collisional_excitation_m3_s(
    lower_n: int, upper_n: int, oscillator_strength: float, temperature_k: np.ndarray | float
) -> np.ndarray:
    """Declared van-Regemorter shell-averaged excitation approximation."""
    temperature = _validated_rate_temperature(temperature_k)
    lower_energy = SHELL_LEVEL_CM_INV[lower_n - 1]
    upper_energy = SHELL_LEVEL_CM_INV[upper_n - 1]
    delta_j = H_PLANCK * C_LIGHT * (upper_energy - lower_energy) * 100.0
    u = delta_j / (K_BOLTZMANN * temperature)
    g_lower = LEVEL_DEGENERACIES[lower_n - 1]
    rydberg_ratio = (H_PLANCK * C_LIGHT * IONIZATION_LIMIT_CM_INV * 100.0) / delta_j
    gaunt = np.where(u < 1.0, 0.7, 0.2)
    omega = np.maximum(1.0e-4, gaunt * oscillator_strength * g_lower * rydberg_ratio**2)
    # 8.629e-6 cm3/s -> 8.629e-12 m3/s.
    return 8.629e-12 * omega * np.exp(-u) / (g_lower * np.sqrt(temperature))


def collisional_deexcitation_m3_s(
    lower_n: int, upper_n: int, oscillator_strength: float, temperature_k: np.ndarray | float
) -> np.ndarray:
    """Detailed-balance partner evaluated without an overflow-prone exp(+u)."""
    temperature = _validated_rate_temperature(temperature_k)
    lower_energy = SHELL_LEVEL_CM_INV[lower_n - 1]
    upper_energy = SHELL_LEVEL_CM_INV[upper_n - 1]
    delta_j = H_PLANCK * C_LIGHT * (upper_energy - lower_energy) * 100.0
    u = delta_j / (K_BOLTZMANN * temperature)
    g_lower = LEVEL_DEGENERACIES[lower_n - 1]
    g_upper = LEVEL_DEGENERACIES[upper_n - 1]
    rydberg_ratio = (H_PLANCK * C_LIGHT * IONIZATION_LIMIT_CM_INV * 100.0) / delta_j
    gaunt = np.where(u < 1.0, 0.7, 0.2)
    omega = np.maximum(1.0e-4, gaunt * oscillator_strength * g_lower * rydberg_ratio**2)
    return 8.629e-12 * omega / (g_upper * np.sqrt(temperature))



def _rate_lattice(
    temperature_grid_k: np.ndarray, temperature_k: float
) -> tuple[int, int, float, float]:
    """Return the shader-equivalent log-temperature interpolation coordinate."""
    grid = np.asarray(temperature_grid_k, dtype=np.float64)
    if grid.ndim != 1 or grid.size < 2 or not np.all(np.isfinite(grid)):
        raise ValueError("temperature grid must contain at least two finite samples")
    if np.any(grid <= 0.0) or np.any(np.diff(grid) <= 0.0):
        raise ValueError("temperature grid must be positive and increasing")
    if not math.isfinite(float(temperature_k)) or float(temperature_k) <= 0.0:
        raise ValueError("temperature must be finite and positive")
    temperature = float(np.clip(temperature_k, grid[0], grid[-1]))
    coordinate = (
        (math.log(temperature) - math.log(float(grid[0])))
        / (math.log(float(grid[-1])) - math.log(float(grid[0])))
        * float(grid.size - 1)
    )
    lower = min(max(int(math.floor(coordinate)), 0), int(grid.size - 1))
    upper = min(lower + 1, int(grid.size - 1))
    return lower, upper, coordinate - float(lower), temperature


def interpolated_collisional_transition_rates(
    pair: dict[str, object],
    transition: dict[str, object],
    temperature_grid_k: np.ndarray,
    temperature_k: float,
) -> tuple[float, float]:
    """Interpolate the collisional pair while enforcing detailed balance.

    The deexcitation table is the well-conditioned direction over the
    temperature domain.  Excitation is derived from it at the actual
    temperature, so low-temperature excitation may underflow to zero without
    losing the finite deexcitation rate.
    """
    lower, upper, fraction, temperature = _rate_lattice(temperature_grid_k, temperature_k)
    deexcitation_values = np.asarray(pair["deexcitation_m3_s"], dtype=np.float64)
    if deexcitation_values.ndim != 1 or deexcitation_values.size != len(temperature_grid_k):
        raise ValueError("deexcitation table shape does not match temperature grid")
    first = float(deexcitation_values[lower])
    second = float(deexcitation_values[upper])
    if lower == upper or fraction <= 0.0:
        deexcitation = first
    elif first > 0.0 and second > 0.0:
        deexcitation = math.exp(
            (1.0 - fraction) * math.log(first) + fraction * math.log(second)
        )
    else:
        deexcitation = 0.0
    if not math.isfinite(deexcitation) or deexcitation <= 0.0:
        return 0.0, max(deexcitation, 0.0)
    lower_n = int(transition["lower_n"])
    upper_n = int(transition["upper_n"])
    delta_j = (
        H_PLANCK
        * C_LIGHT
        * (SHELL_LEVEL_CM_INV[upper_n - 1] - SHELL_LEVEL_CM_INV[lower_n - 1])
        * 100.0
    )
    lower_degeneracy = float(LEVEL_DEGENERACIES[lower_n - 1])
    upper_degeneracy = float(LEVEL_DEGENERACIES[upper_n - 1])
    log_excitation = (
        math.log(deexcitation)
        + math.log(upper_degeneracy / lower_degeneracy)
        - delta_j / (K_BOLTZMANN * temperature)
    )
    excitation = float(np.exp(log_excitation))
    return excitation, deexcitation


def collisional_interpolation_invariant(model: dict[str, object]) -> dict[str, object]:
    """Check paired interpolation at every knot and geometric cell midpoint."""
    kinetics_value = model.get("kinetics", {})
    transitions_value = model.get("transitions", [])
    if not isinstance(kinetics_value, dict) or not isinstance(transitions_value, list):
        return {"passed": False, "reason": "kinetics or transitions are malformed"}
    grid = np.asarray(kinetics_value.get("temperature_grid_K", []), dtype=np.float64)
    pairs = kinetics_value.get("collisional_transition_rates", [])
    if (
        grid.ndim != 1
        or grid.size < 2
        or not np.all(np.isfinite(grid))
        or np.any(grid <= 0.0)
        or np.any(np.diff(grid) <= 0.0)
        or not isinstance(pairs, list)
        or len(pairs) != len(transitions_value)
    ):
        return {"passed": False, "reason": "paired interpolation inputs are malformed"}
    interpolation_points = np.concatenate((grid, np.sqrt(grid[:-1] * grid[1:])))
    normal_min = float(np.finfo(np.float64).tiny)
    subnormal_min = float(np.nextafter(0.0, 1.0))
    log_normal_min = math.log(normal_min)
    log_subnormal_min = math.log(subnormal_min)
    max_log_balance_error = 0.0
    max_endpoint_relative_error = 0.0
    max_excitation_endpoint_relative_error = 0.0
    subnormal_excitation_count = 0
    underflowed_excitation_count = 0
    compared = 0
    passed = True
    for transition_value, pair_value in zip(transitions_value, pairs):
        if not isinstance(transition_value, dict) or not isinstance(pair_value, dict):
            passed = False
            continue
        try:
            lower_n = int(transition_value["lower_n"])
            upper_n = int(transition_value["upper_n"])
            oscillator = float(transition_value["oscillator_strength"])
            direct_up = np.asarray(
                collisional_excitation_m3_s(lower_n, upper_n, oscillator, grid),
                dtype=np.float64,
            )
            direct_down = np.asarray(
                collisional_deexcitation_m3_s(lower_n, upper_n, oscillator, grid),
                dtype=np.float64,
            )
            stored_up = np.asarray(pair_value["excitation_m3_s"], dtype=np.float64)
            stored_down = np.asarray(pair_value["deexcitation_m3_s"], dtype=np.float64)
            if (
                stored_up.ndim != 1
                or stored_down.ndim != 1
                or stored_up.size != grid.size
                or stored_down.size != grid.size
            ):
                passed = False
                continue
            max_endpoint_relative_error = max(
                max_endpoint_relative_error,
                float(
                    np.max(
                        np.abs(stored_down - direct_down)
                        / np.maximum(np.abs(direct_down), 1.0e-300)
                    )
                ),
            )
            for stored, expected in zip(stored_up, direct_up):
                stored_value = float(stored)
                expected_value = float(expected)
                if expected_value == 0.0:
                    passed = passed and stored_value == 0.0
                elif expected_value < subnormal_min:
                    passed = passed and stored_value == 0.0
                else:
                    endpoint_error = abs(stored_value - expected_value) / max(
                        abs(expected_value), subnormal_min
                    )
                    max_excitation_endpoint_relative_error = max(
                        max_excitation_endpoint_relative_error, endpoint_error
                    )
                    passed = passed and endpoint_error <= 2.0e-6
            delta_j = (
                H_PLANCK
                * C_LIGHT
                * (SHELL_LEVEL_CM_INV[upper_n - 1] - SHELL_LEVEL_CM_INV[lower_n - 1])
                * 100.0
            )
            expected_log_degeneracy_ratio = math.log(
                LEVEL_DEGENERACIES[upper_n - 1] / LEVEL_DEGENERACIES[lower_n - 1]
            )
            for temperature in interpolation_points:
                excitation, deexcitation = interpolated_collisional_transition_rates(
                    pair_value, transition_value, grid, float(temperature)
                )
                _, _, _, clamped_temperature = _rate_lattice(grid, float(temperature))
                if (
                    not math.isfinite(excitation)
                    or not math.isfinite(deexcitation)
                    or deexcitation <= 0.0
                    or excitation < 0.0
                ):
                    passed = False
                    continue
                expected_log_ratio = expected_log_degeneracy_ratio - delta_j / (
                    K_BOLTZMANN * clamped_temperature
                )
                log_target = expected_log_ratio + math.log(deexcitation)
                compared += 1
                if log_target < log_subnormal_min:
                    underflowed_excitation_count += 1
                    passed = passed and excitation == 0.0
                    continue
                if log_target <= log_normal_min:
                    subnormal_excitation_count += 1
                    passed = passed and excitation <= normal_min
                    continue
                if excitation <= 0.0:
                    passed = False
                    continue
                log_balance_error = abs(
                    math.log(excitation / deexcitation) - expected_log_ratio
                )
                max_log_balance_error = max(max_log_balance_error, log_balance_error)
                passed = passed and log_balance_error <= 2.0e-12
        except (KeyError, TypeError, ValueError, OverflowError):
            passed = False
    passed = (
        passed
        and compared > 0
        and max_endpoint_relative_error <= 2.0e-6
        and max_excitation_endpoint_relative_error <= 2.0e-6
    )
    return {
        "passed": passed,
        "temperature_points": int(interpolation_points.size),
        "transition_count": len(transitions_value),
        "compared_pairs": compared,
        "max_log_balance_error": max_log_balance_error,
        "max_endpoint_relative_error": max_endpoint_relative_error,
        "max_excitation_endpoint_relative_error": max_excitation_endpoint_relative_error,
        "subnormal_excitation_count": subnormal_excitation_count,
        "underflowed_excitation_count": underflowed_excitation_count,
    }


def free_free_emissivity_w_m3_hz(
    frequency_hz: np.ndarray | float, temperature_k: float, electron_m3: float, ion_m3: float
) -> np.ndarray:
    """Angle-integrated thermal bremsstrahlung, Rybicki-Lightman form."""
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    temperature = float(temperature_k)
    # Smooth nonrelativistic Gaunt approximation, bounded in its declared use.
    gaunt = np.clip(
        (math.sqrt(3.0) / PI)
        * np.log(np.maximum(2.25 * K_BOLTZMANN * temperature / (H_PLANCK * frequency), 1.000001)),
        1.0,
        5.0,
    )
    # 6.8e-38 erg s^-1 cm^-3 Hz^-1 with both number densities in cm^-3:
    # (1e-6)^2 converts m^-3 inputs; 1e-1 converts erg cm^-3 to J m^-3.
    return (
        6.8e-51
        * float(electron_m3)
        * float(ion_m3)
        * np.power(temperature, -0.5)
        * np.exp(-H_PLANCK * frequency / (K_BOLTZMANN * temperature))
        * gaunt
    )


def line_group_fraction(
    center_hz: float, a_s_inv: float, low_hz: float, high_hz: float, temperature_k: float
) -> float:
    thermal_sigma = center_hz * math.sqrt(
        2.0 * K_BOLTZMANN * temperature_k / (M_HYDROGEN * C_LIGHT**2)
    )
    natural_width = a_s_inv / (4.0 * PI)
    width = math.sqrt(thermal_sigma**2 + natural_width**2)
    if width <= 0.0:
        return 1.0 if low_hz <= center_hz < high_hz else 0.0
    inv = 1.0 / (math.sqrt(2.0) * width)
    return min(1.0, max(0.0, 0.5 * (
        math.erf((high_hz - center_hz) * inv)
        - math.erf((low_hz - center_hz) * inv)
    )))


def free_bound_group_fraction(
    threshold_hz: float, low_hz: float, high_hz: float, temperature_k: float
) -> float:
    if high_hz <= threshold_hz:
        return 0.0
    thermal_hz = K_BOLTZMANN * temperature_k / H_PLANCK
    lower_hz = max(low_hz, threshold_hz)
    low_exponent = min((lower_hz - threshold_hz) / thermal_hz, 80.0)
    high_exponent = min((high_hz - threshold_hz) / thermal_hz, 80.0)
    return max(0.0, math.exp(-low_exponent) - math.exp(-high_exponent))
def two_photon_group_weight(low_hz: float, high_hz: float, lyman_alpha_hz: float) -> float:
    low = min(1.0, max(0.0, low_hz / lyman_alpha_hz))
    high = min(1.0, max(0.0, high_hz / lyman_alpha_hz))
    if high <= low:
        return 0.0
    midpoint = 0.5 * (low + high)
    return (midpoint * (1.0 - midpoint)) ** 3 * (high - low)


def hllc_flux(primitive_left: Iterable[float], primitive_right: Iterable[float], gamma: float = 5.0 / 3.0) -> np.ndarray:
    """One-dimensional Euler HLLC reference flux [rho, rho*u, E]."""
    rho_l, velocity_l, pressure_l = (float(v) for v in primitive_left)
    rho_r, velocity_r, pressure_r = (float(v) for v in primitive_right)
    if min(rho_l, rho_r, pressure_l, pressure_r) <= 0.0:
        raise ValueError("HLLC primitive state must be positive")
    energy_l = pressure_l / (gamma - 1.0) + 0.5 * rho_l * velocity_l**2
    energy_r = pressure_r / (gamma - 1.0) + 0.5 * rho_r * velocity_r**2
    sound_l = math.sqrt(gamma * pressure_l / rho_l)
    sound_r = math.sqrt(gamma * pressure_r / rho_r)
    s_l = min(velocity_l - sound_l, velocity_r - sound_r)
    s_r = max(velocity_l + sound_l, velocity_r + sound_r)
    numerator = pressure_r - pressure_l + rho_l * velocity_l * (s_l - velocity_l) - rho_r * velocity_r * (s_r - velocity_r)
    denominator = rho_l * (s_l - velocity_l) - rho_r * (s_r - velocity_r)
    s_star = numerator / denominator
    flux_l = np.array([rho_l * velocity_l, rho_l * velocity_l**2 + pressure_l, velocity_l * (energy_l + pressure_l)])
    flux_r = np.array([rho_r * velocity_r, rho_r * velocity_r**2 + pressure_r, velocity_r * (energy_r + pressure_r)])
    if 0.0 <= s_l:
        return flux_l
    if s_l <= 0.0 <= s_star:
        factor = rho_l * (s_l - velocity_l) / (s_l - s_star)
        star = factor * np.array([1.0, s_star, energy_l / rho_l + (s_star - velocity_l) * (s_star + pressure_l / (rho_l * (s_l - velocity_l)))])
        return flux_l + s_l * (star - np.array([rho_l, rho_l * velocity_l, energy_l]))
    if s_star <= 0.0 <= s_r:
        factor = rho_r * (s_r - velocity_r) / (s_r - s_star)
        star = factor * np.array([1.0, s_star, energy_r / rho_r + (s_star - velocity_r) * (s_star + pressure_r / (rho_r * (s_r - velocity_r)))])
        return flux_r + s_r * (star - np.array([rho_r, rho_r * velocity_r, energy_r]))
    return flux_r


def integrate_sod(cells: int = 128, final_time: float = 0.2, gamma: float = 5.0 / 3.0) -> dict[str, list[float]]:
    """Frozen first-order HLLC shock reference used by the GPU verifier."""
    dx = 1.0 / cells
    x = (np.arange(cells, dtype=np.float64) + 0.5) * dx
    rho = np.where(x < 0.5, 1.0, 0.125)
    velocity = np.zeros(cells, dtype=np.float64)
    pressure = np.where(x < 0.5, 1.0, 0.1)
    conserved = np.stack((rho, rho * velocity, pressure / (gamma - 1.0) + 0.5 * rho * velocity**2), axis=1)
    time = 0.0
    while time < final_time - 1.0e-14:
        rho = conserved[:, 0]
        velocity = conserved[:, 1] / rho
        pressure = (gamma - 1.0) * (conserved[:, 2] - 0.5 * rho * velocity**2)
        dt = min(0.42 * dx / np.max(np.abs(velocity) + np.sqrt(gamma * pressure / rho)), final_time - time)
        fluxes = np.empty((cells + 1, 3), dtype=np.float64)
        fluxes[0] = hllc_flux((rho[0], velocity[0], pressure[0]), (rho[0], velocity[0], pressure[0]), gamma)
        for face in range(1, cells):
            fluxes[face] = hllc_flux(
                (rho[face - 1], velocity[face - 1], pressure[face - 1]),
                (rho[face], velocity[face], pressure[face]), gamma,
            )
        fluxes[-1] = hllc_flux((rho[-1], velocity[-1], pressure[-1]), (rho[-1], velocity[-1], pressure[-1]), gamma)
        conserved -= (dt / dx) * (fluxes[1:] - fluxes[:-1])
        time += dt
    rho = conserved[:, 0]
    velocity = conserved[:, 1] / rho
    pressure = (gamma - 1.0) * (conserved[:, 2] - 0.5 * rho * velocity**2)
    return {"x": x.tolist(), "density": rho.tolist(), "velocity": velocity.tolist(), "pressure": pressure.tolist()}


def load_cie() -> tuple[np.ndarray, np.ndarray]:
    values: list[list[float]] = []
    with CIE_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            values.append([float(value) for value in row])
    array = np.asarray(values, dtype=np.float64)
    return array[:, 0] * 1.0e-9, array[:, 1:4]


def observer_group_weights() -> list[list[float]]:
    wavelength_m, xyz = load_cie()
    frequency = C_LIGHT / wavelength_m
    order = np.argsort(frequency)
    frequency = frequency[order]
    xyz = xyz[order]
    result: list[list[float]] = []
    for lower, upper in zip(FREQUENCY_EDGES_HZ[:-1], FREQUENCY_EDGES_HZ[1:]):
        samples = np.geomspace(lower, upper, 257)
        interpolated = np.column_stack(
            [np.interp(samples, frequency, xyz[:, channel], left=0.0, right=0.0) for channel in range(3)]
        )
        average = np.asarray(np.trapezoid(interpolated, samples, axis=0) / (upper - lower), dtype=np.float64)
        result.append([float(value) for value in average])
    return result


def lebedev_26() -> tuple[list[list[float]], list[float]]:
    """Lebedev degree-7 26-direction sphere rule in deterministic order."""
    directions: list[list[float]] = []
    weights: list[float] = []
    axis_weight = 4.0 * PI * (1.0 / 21.0)
    edge_weight = 4.0 * PI * (4.0 / 105.0)
    corner_weight = 4.0 * PI * (9.0 / 280.0)
    for axis in range(3):
        for sign in (-1.0, 1.0):
            direction = [0.0, 0.0, 0.0]
            direction[axis] = sign
            directions.append(direction)
            weights.append(axis_weight)
    edge_coordinate = 1.0 / math.sqrt(2.0)
    for zero_axis in range(3):
        active = [axis for axis in range(3) if axis != zero_axis]
        for first_sign in (-1.0, 1.0):
            for second_sign in (-1.0, 1.0):
                direction = [0.0, 0.0, 0.0]
                direction[active[0]] = first_sign * edge_coordinate
                direction[active[1]] = second_sign * edge_coordinate
                directions.append(direction)
                weights.append(edge_weight)
    corner_coordinate = 1.0 / math.sqrt(3.0)
    for x_sign in (-1.0, 1.0):
        for y_sign in (-1.0, 1.0):
            for z_sign in (-1.0, 1.0):
                directions.append([
                    x_sign * corner_coordinate,
                    y_sign * corner_coordinate,
                    z_sign * corner_coordinate,
                ])
                weights.append(corner_weight)
    return directions, weights


def build_model() -> dict[str, object]:
    levels = []
    for index, (wavenumber, degeneracy) in enumerate(zip(SHELL_LEVEL_CM_INV, LEVEL_DEGENERACIES), start=1):
        levels.append(
            {
                "state_index": index - 1,
                "species": "H_I",
                "principal_n": index,
                "degeneracy": degeneracy,
                "energy_cm_inv": wavenumber,
                "excitation_energy_J": H_PLANCK * C_LIGHT * wavenumber * 100.0,
            }
        )
    levels.append(
        {
            "state_index": 6,
            "species": "H_II",
            "principal_n": 0,
            "degeneracy": 1.0,
            "energy_cm_inv": IONIZATION_LIMIT_CM_INV,
            "excitation_energy_J": H_PLANCK * C_LIGHT * IONIZATION_LIMIT_CM_INV * 100.0,
        }
    )

    transitions = []
    for lower_n, upper_n, displayed_nm, a_s, oscillator in NIST_TRANSITIONS:
        delta_cm = SHELL_LEVEL_CM_INV[upper_n - 1] - SHELL_LEVEL_CM_INV[lower_n - 1]
        frequency = C_LIGHT * delta_cm * 100.0
        transitions.append(
            {
                "lower_state": lower_n - 1,
                "upper_state": upper_n - 1,
                "lower_n": lower_n,
                "upper_n": upper_n,
                "frequency_Hz": frequency,
                "vacuum_wavelength_nm_from_levels": C_LIGHT / frequency * 1.0e9,
                "nist_query_wavelength_nm": displayed_nm,
                "A_s_inv": a_s,
                "oscillator_strength": oscillator,
                "lower_degeneracy": LEVEL_DEGENERACIES[lower_n - 1],
                "upper_degeneracy": LEVEL_DEGENERACIES[upper_n - 1],
                "group_index": group_index(frequency),
            }
        )

    rate_table: list[dict[str, object]] = []
    for transition in transitions:
        up = collisional_excitation_m3_s(
            int(transition["lower_n"]), int(transition["upper_n"]),
            float(transition["oscillator_strength"]), TEMPERATURE_GRID_K,
        )
        down = collisional_deexcitation_m3_s(
            int(transition["lower_n"]), int(transition["upper_n"]),
            float(transition["oscillator_strength"]), TEMPERATURE_GRID_K,
        )
        rate_table.append({"excitation_m3_s": up.tolist(), "deexcitation_m3_s": down.tolist()})

    constants = {
        "c_m_s": C_LIGHT,
        "h_J_s": H_PLANCK,
        "k_B_J_K": K_BOLTZMANN,
        "m_H_kg": M_HYDROGEN,
        "m_e_kg": M_ELECTRON,
        "electron_charge_C": E_CHARGE,
        "epsilon_0_F_m": EPSILON_0,
        "sigma_T_m2": SIGMA_T,
    }
    source = {
        "atomic_species": "hydrogen",
        "line_database": "NIST ASD",
        "line_database_version": NIST_ASD_VERSION,
        "line_query": NIST_LINE_URL,
        "line_response_sha256": NIST_LINE_RESPONSE_SHA256,
        "level_query": NIST_LEVEL_URL,
        "level_response_sha256": NIST_LEVEL_RESPONSE_SHA256,
        "access_date": NIST_ACCESS_DATE,
        "transition_probability_sources": ["Wiese & Fuhr 2009", "Jitrik & Bunge 2004"],
        "collisional_excitation": "van Regemorter shell-averaged approximation",
        "collisional_ionization": "Voronov 1997 H I fit",
        "radiative_recombination": "Hui & Gnedin 1997 case-A fit",
        "free_free": "Rybicki & Lightman nonrelativistic thermal bremsstrahlung",
        "two_photon_rate_s_inv": 8.2206,
        "limitations": [
            "principal-shell populations n=1..6; fine structure is unresolved",
            "hydrogen only; no metals, molecules, dust, nuclear reactions, or invented Cassi chemistry",
            "case-A recombination and approximate shell-averaged electron collision strengths",
        ],
    }
    unit_defaults = {
        "length_m_per_sim": 1.0e12,
        "time_s_per_physics_sim": 1.0e8,
        "target_total_baryonic_mass_kg": 1.98847e30,
        "temperature_K_per_value": 1.0,
        "initial_temperature_K": 8_000.0,
        "initial_ionization": "local_saha",
        "reduced_light_fraction": 1.0e-2,
        "c_gamma_sim": C_LIGHT * 1.0e8 / 1.0e12 * 1.0e-2,
    }
    frequency_grid = {
        "frame": "material",
        "group_count": len(FREQUENCY_EDGES_HZ) - 1,
        "frequency_edges_Hz": list(FREQUENCY_EDGES_HZ),
        "group_midpoint_Hz": [math.sqrt(a * b) for a, b in zip(FREQUENCY_EDGES_HZ[:-1], FREQUENCY_EDGES_HZ[1:])],
        "group_width_Hz": [b - a for a, b in zip(FREQUENCY_EDGES_HZ[:-1], FREQUENCY_EDGES_HZ[1:])],
        "observer_xyz_average": observer_group_weights(),
        "ordinates": lebedev_26()[0],
        "ordinate_weights_sr": lebedev_26()[1],
        "angular_quadrature": "Lebedev-26 degree-7",
        "spatial_boundary": "open_outflow",
        "frequency_boundary": "escaped_energy_ledgers",
    }
    kinetics = {
        "temperature_grid_K": TEMPERATURE_GRID_K.tolist(),
        "collisional_transition_rates": rate_table,
        "collisional_ionization_m3_s": collisional_ionization_m3_s(TEMPERATURE_GRID_K).tolist(),
        "case_a_recombination_m3_s": case_a_recombination_m3_s(TEMPERATURE_GRID_K).tolist(),
        "photoionization_threshold_m2": [6.30e-22 * float(n**5) for n in range(1, 7)],
        "photoionization_frequency_power": -3.0,
        "free_free_gaunt_min": 1.0,
        "free_free_gaunt_max": 5.0,
    }
    model: dict[str, object] = {
        "schema_version": "1.0.0",
        "model_id": "cassi-conditional-hydrogen-plasma-n6",
        "model_revision": "2026-09-10",
        "source_kind": "conditional_hydrogen_plasma",
        "coupling": "live_cassi_mass_motion_gravity",
        "qualification_scope": [
            "conservative_particle_initialization",
            "finite_volume_hllc_hydrodynamics",
            "time_dependent_hydrogen_kinetics",
            "lebedev26_multigroup_transport",
            "paired_matter_radiation_exchange",
            "physical_xyz_observation",
        ],
        "constants": constants,
        "source_record": source,
        "unit_defaults": unit_defaults,
        "levels": levels,
        "transitions": transitions,
        "frequency_grid": frequency_grid,
        "kinetics": kinetics,
        "eos": {
            "kind": "ideal_monatomic_H_Hplus",
            "gamma": 5.0 / 3.0,
            "temperature_min_K": 10.0,
            "temperature_max_K": 1.0e8,
            "chemical_energy_in_total_material_energy": True,
        },
        "transport": {
            "hydro": "dimensionally_split_hllc_mc_with_first_order_positivity_fallback",
            "radiation": "lebedev26_upwind_reduced_light_speed",
            "frequency": "first_order_conservative_material_frame",
            "scattering": "thomson_isotropic_column_stochastic",
            "cfl": 0.42,
            "maximum_v_over_c_reduced": 0.05,
        },
    }
    for key in ("constants", "source_record", "unit_defaults", "frequency_grid", "kinetics"):
        value = model[key]
        assert isinstance(value, dict)
        value[f"{key}_sha256"] = digest(value)
    model["model_sha256"] = digest(model)
    return model


RATE_STEP_DT_SIM = 1.0e-3
RATE_STEP_TIME_S_PER_SIM = 1.0e-4
RATE_STEP_DT_S = RATE_STEP_DT_SIM * RATE_STEP_TIME_S_PER_SIM
RATE_STEP_VELOCITY_M_S_PER_SIM = 1.0 / RATE_STEP_TIME_S_PER_SIM
RATE_STEP_GAMMA = 5.0 / 3.0
RATE_STEP_PRESSURE_FLOOR_SIM = 1.0e-24
RATE_STEP_DENSITY_FLOOR_SIM = 1.0e-20
RATE_STEP_TWO_PHOTON_A_S_INV = 8.2206


def _linear_rate_at(values: object, temperature_grid_k: np.ndarray, temperature_k: float) -> float:
    lower, upper, fraction, _ = _rate_lattice(temperature_grid_k, temperature_k)
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size != temperature_grid_k.size:
        raise ValueError("rate table shape does not match temperature grid")
    return float((1.0 - fraction) * array[lower] + fraction * array[upper])


def _state_emissivity(
    model: dict[str, object],
    populations_m3: np.ndarray,
    temperature_k: float,
    recombination_coefficient_m3_s: float | None = None,
) -> dict[str, object]:
    """Compute the published group emissivities from one solved seven-state vector."""
    transitions = model["transitions"]
    levels = model["levels"]
    assert isinstance(transitions, list)
    assert isinstance(levels, list)
    edges = np.asarray(FREQUENCY_EDGES_HZ, dtype=np.float64)
    midpoints = np.sqrt(edges[:-1] * edges[1:])
    density = float(np.sum(populations_m3))
    ion_density = max(float(populations_m3[6]), 0.0)
    continuum: list[float] = []
    for lower, upper in zip(edges[:-1], edges[1:]):
        samples = np.geomspace(lower, upper, 129)
        spectrum = free_free_emissivity_w_m3_hz(
            samples, temperature_k, ion_density, ion_density
        )
        continuum.append(float(np.trapezoid(spectrum, samples)))
    lines: list[float] = []
    line_groups = np.zeros(len(edges) - 1, dtype=np.float64)
    for record in transitions:
        assert isinstance(record, dict)
        branch = 0.75 if (
            int(record["lower_state"]) == 0 and int(record["upper_state"]) == 1
        ) else 1.0
        luminosity = (
            float(populations_m3[int(record["upper_state"])])
            * float(record["A_s_inv"])
            * H_PLANCK
            * float(record["frequency_Hz"])
            * branch
        )
        lines.append(luminosity)
        for group, (lower, upper) in enumerate(zip(edges[:-1], edges[1:])):
            line_groups[group] += luminosity * line_group_fraction(
                float(record["frequency_Hz"]), float(record["A_s_inv"]),
                float(lower), float(upper), temperature_k,
            )
    free_bound_groups = np.zeros(len(edges) - 1, dtype=np.float64)
    if recombination_coefficient_m3_s is None:
        recombination = float(case_a_recombination_m3_s(temperature_k))
    else:
        recombination = float(recombination_coefficient_m3_s)
    branch_weights = np.asarray(
        [1.0 / float(n**3) for n in range(1, 7)], dtype=np.float64
    )
    branch_weights /= np.sum(branch_weights)
    for level, branch in zip(levels, branch_weights):
        assert isinstance(level, dict)
        threshold = (
            H_PLANCK * C_LIGHT * IONIZATION_LIMIT_CM_INV * 100.0
            - float(level["excitation_energy_J"])
        ) / H_PLANCK
        for group, (lower, upper) in enumerate(zip(edges[:-1], edges[1:])):
            fraction = free_bound_group_fraction(
                threshold, float(lower), float(upper), temperature_k
            )
            free_bound_groups[group] += (
                recombination * ion_density**2 * float(branch) * fraction
                * H_PLANCK * midpoints[group]
            )
    lyman_alpha = float(transitions[0]["frequency_Hz"])
    two_weights = np.asarray([
        two_photon_group_weight(float(lower), float(upper), lyman_alpha)
        for lower, upper in zip(edges[:-1], edges[1:])
    ], dtype=np.float64)
    if np.sum(two_weights) > 0.0:
        two_weights /= np.sum(two_weights)
    two_photon_groups = (
        float(populations_m3[1]) * 0.25 * RATE_STEP_TWO_PHOTON_A_S_INV
        * H_PLANCK * lyman_alpha * two_weights
    )
    total_groups = (
        np.asarray(continuum) + line_groups + free_bound_groups + two_photon_groups
    )
    return {
        "free_free_group_emissivity_W_m3": continuum,
        "line_emissivity_W_m3": lines,
        "line_group_emissivity_W_m3": line_groups.tolist(),
        "free_bound_group_emissivity_W_m3": free_bound_groups.tolist(),
        "two_photon_group_emissivity_W_m3": two_photon_groups.tolist(),
        "total_group_emissivity_W_m3": total_groups.tolist(),
        "bolometric_emissivity_W_m3": float(np.sum(total_groups)),
        "population_sum_m3": density,
    }


def _rate_step_oracle(
    model: dict[str, object],
    temperature_k: float,
    hydrogen_number_density_m3: float,
    old_populations_m3: np.ndarray,
) -> dict[str, object]:
    """Independent float64 counterpart of atomic.glsl's seven-state source step.

    The fixture deliberately has no radiation energy, so only collisional,
    radiative bound-bound, ionization, and branch-normalized recombination
    channels are active.  The matrix orientation and limiter follow the shader
    contract, but the implementation does not import or translate GDScript/GLSL.
    """
    kinetics = model["kinetics"]
    transitions = model["transitions"]
    levels = model["levels"]
    assert isinstance(kinetics, dict)
    assert isinstance(transitions, list)
    assert isinstance(levels, list)
    grid = np.asarray(kinetics["temperature_grid_K"], dtype=np.float64)
    pairs = kinetics["collisional_transition_rates"]
    ion_table = kinetics["collisional_ionization_m3_s"]
    recombination_table = kinetics["case_a_recombination_m3_s"]
    old = np.maximum(np.asarray(old_populations_m3, dtype=np.float64), 0.0)
    if old.shape != (7,) or not np.all(np.isfinite(old)):
        raise ValueError("rate-step old populations must be seven finite states")
    density = float(hydrogen_number_density_m3)
    electron_density = float(old[6])
    generator = np.zeros((7, 7), dtype=np.float64)

    def add_transition(source: int, target: int, rate_s_inv: float) -> None:
        if math.isfinite(rate_s_inv) and rate_s_inv > 0.0:
            generator[target, source] += rate_s_inv
            generator[source, source] -= rate_s_inv

    for line, record in enumerate(transitions):
        assert isinstance(record, dict)
        lower = int(record["lower_state"])
        upper = int(record["upper_state"])
        coll_up_coeff, coll_down_coeff = interpolated_collisional_transition_rates(
            pairs[line], record, grid, temperature_k
        )
        radiative_down = float(record["A_s_inv"])
        if lower == 0 and upper == 1:
            radiative_down = (
                0.75 * radiative_down + 0.25 * RATE_STEP_TWO_PHOTON_A_S_INV
            )
        add_transition(lower, upper, coll_up_coeff * electron_density)
        add_transition(
            upper, lower, coll_down_coeff * electron_density + radiative_down
        )
    ion_rate = _linear_rate_at(ion_table, grid, temperature_k) * electron_density
    recombination_coefficient = _linear_rate_at(
        recombination_table, grid, temperature_k
    )
    recombination = recombination_coefficient * electron_density
    branch_norm = float(np.sum([1.0 / float(n**3) for n in range(1, 7)]))
    for level in range(6):
        add_transition(level, 6, ion_rate)
        add_transition(
            6, level, recombination / (float((level + 1) ** 3) * branch_norm)
        )

    matrix = np.eye(7, dtype=np.float64) - RATE_STEP_DT_S * generator
    solved = np.linalg.solve(matrix, old)
    solved = np.maximum(solved, 0.0)
    solved *= density / max(float(np.sum(solved)), np.finfo(np.float64).tiny)
    unlimited_solved = solved.copy()

    velocity_squared = RATE_STEP_VELOCITY_M_S_PER_SIM**2
    old_fraction = old / density
    old_chemical_sim = float(np.sum([
        old_fraction[state] * float(levels[state]["excitation_energy_J"])
        / (M_HYDROGEN * velocity_squared)
        for state in range(7)
    ]))
    unlimited_fraction = unlimited_solved / density
    unlimited_chemical_sim = float(np.sum([
        unlimited_fraction[state] * float(levels[state]["excitation_energy_J"])
        / (M_HYDROGEN * velocity_squared)
        for state in range(7)
    ]))
    ion_fraction = float(old[6] / density)
    pressure_pa = (density + old[6]) * K_BOLTZMANN * temperature_k
    energy_density = M_HYDROGEN * density * velocity_squared
    pressure_sim = pressure_pa / energy_density
    total_material_energy_sim = pressure_sim / (RATE_STEP_GAMMA - 1.0) + old_chemical_sim
    energy_scale = max(abs(total_material_energy_sim), abs(old_chemical_sim))
    thermal_floor_sim = max(
        RATE_STEP_PRESSURE_FLOOR_SIM / (RATE_STEP_GAMMA - 1.0),
        1024.0 * np.finfo(np.float32).eps * energy_scale,
    )
    chemical_limit_sim = max(total_material_energy_sim - thermal_floor_sim, 0.0)
    limiter_lambda = 1.0
    limited = False
    if unlimited_chemical_sim > chemical_limit_sim and unlimited_chemical_sim > old_chemical_sim:
        limiter_lambda = float(np.clip(
            (chemical_limit_sim - old_chemical_sim)
            / (unlimited_chemical_sim - old_chemical_sim), 0.0, 1.0
        ))
        solved = old + limiter_lambda * (solved - old)
        limited = True
    post_fraction = solved / density
    post_chemical_sim = float(np.sum([
        post_fraction[state] * float(levels[state]["excitation_energy_J"])
        / (M_HYDROGEN * velocity_squared)
        for state in range(7)
    ]))
    post_ion_fraction = float(np.clip(post_fraction[6], 0.0, 1.0))
    post_thermal_sim = total_material_energy_sim - post_chemical_sim
    post_temperature = float(np.clip(
        (RATE_STEP_GAMMA - 1.0) * M_HYDROGEN * velocity_squared * post_thermal_sim
        / (K_BOLTZMANN * (1.0 + post_ion_fraction)),
        RATE_TEMPERATURE_MIN_K, RATE_TEMPERATURE_MAX_K,
    ))
    post_pressure = (RATE_STEP_GAMMA - 1.0) * post_thermal_sim * energy_density
    post_recombination_coefficient = _linear_rate_at(
        recombination_table, grid, post_temperature
    )
    post_emissivity = _state_emissivity(
        model, solved, post_temperature, post_recombination_coefficient
    )
    return {
        "populations_m3": solved,
        "unlimited_populations_m3": unlimited_solved,
        "ion_fraction": post_ion_fraction,
        "temperature_K": post_temperature,
        "pressure_Pa": post_pressure,
        "emissivity": post_emissivity,
        "metadata": {
            "electron_number_density_m3": electron_density,
            "recombination_coefficient_m3_s": recombination_coefficient,
            "post_emissivity_recombination_coefficient_m3_s": post_recombination_coefficient,
            "old_chemical_energy_sim": old_chemical_sim,
            "unlimited_chemical_energy_sim": unlimited_chemical_sim,
            "post_chemical_energy_sim": post_chemical_sim,
            "total_material_energy_sim": total_material_energy_sim,
            "thermal_floor_sim": thermal_floor_sim,
            "chemical_limit_sim": chemical_limit_sim,
            "chemical_limiter_lambda": limiter_lambda,
            "chemical_energy_limiter_applied": limited,
            "population_sum_m3": float(np.sum(solved)),
            "matrix_policy": "backward_euler_normalized_column_generator",
            "rate_policy": "log_temperature_deexcitation_then_detailed_balance",
            "radiation_policy": "zero_group_energy_no_photoionization_or_line_absorption",
        },
    }


def reference_cases(model: dict[str, object]) -> dict[str, object]:
    density_cases = (1.0e6, 1.0e12, 1.0e18)
    temperature_cases = (100.0, 3_000.0, 10_000.0, 100_000.0)
    transitions = model["transitions"]
    levels = model["levels"]
    assert isinstance(transitions, list)
    assert isinstance(levels, list)
    edges = np.asarray(FREQUENCY_EDGES_HZ, dtype=np.float64)
    midpoints = np.sqrt(edges[:-1] * edges[1:])
    thermo = []
    for temperature in temperature_cases:
        for density in density_cases:
            ion = saha_ion_fraction(temperature, density)
            boltzmann = neutral_boltzmann_fractions(temperature)
            populations = np.concatenate(((1.0 - ion) * density * boltzmann, [ion * density]))
            pressure = (density + ion * density) * K_BOLTZMANN * temperature
            initial_emissivity = _state_emissivity(model, populations, temperature)
            rate_step = _rate_step_oracle(model, temperature, density, populations)
            post_populations = np.asarray(rate_step["populations_m3"], dtype=np.float64)
            post_emissivity = rate_step["emissivity"]
            post_metadata = rate_step["metadata"]
            assert isinstance(post_emissivity, dict)
            assert isinstance(post_metadata, dict)
            thermo.append(
                {
                    "temperature_K": temperature,
                    "hydrogen_number_density_m3": density,
                    "ion_fraction": ion,
                    "pressure_Pa": pressure,
                    "population_number_density_m3": populations.tolist(),
                    "free_free_group_emissivity_W_m3": initial_emissivity["free_free_group_emissivity_W_m3"],
                    "line_emissivity_W_m3": initial_emissivity["line_emissivity_W_m3"],
                    "line_group_emissivity_W_m3": initial_emissivity["line_group_emissivity_W_m3"],
                    "free_bound_group_emissivity_W_m3": initial_emissivity["free_bound_group_emissivity_W_m3"],
                    "two_photon_group_emissivity_W_m3": initial_emissivity["two_photon_group_emissivity_W_m3"],
                    "total_group_emissivity_W_m3": initial_emissivity["total_group_emissivity_W_m3"],
                    "rate_step_controls": {
                        "dt_sim": RATE_STEP_DT_SIM,
                        "time_s_per_sim": RATE_STEP_TIME_S_PER_SIM,
                        "dt_s": RATE_STEP_DT_S,
                        "source_enabled": True,
                        "radiation_enabled": False,
                        "radiation_energy_density_group_J_m3": [0.0] * (len(edges) - 1),
                        "initial_population_policy": "case_lte_saha_ion_fraction_and_neutral_boltzmann",
                        "temperature_density_policy": "case_temperature_and_hydrogen_number_density",
                        "chemical_energy_policy": "same_packed_thermal_reservoir_limiter",
                    },
                    "rate_step_metadata": {
                        **post_metadata,
                        "mass_kg_per_sim": M_HYDROGEN * density,
                        "length_m_per_sim": 1.0,
                        "velocity_m_s_per_sim": RATE_STEP_VELOCITY_M_S_PER_SIM,
                        "energy_density_J_m3_per_sim": M_HYDROGEN * density * RATE_STEP_VELOCITY_M_S_PER_SIM**2,
                        "old_temperature_K": temperature,
                        "old_ion_fraction": ion,
                        "old_population_number_density_m3": populations.tolist(),
                        "unlimited_post_population_number_density_m3": (
                            np.asarray(rate_step["unlimited_populations_m3"], dtype=np.float64)
                            .tolist()
                        ),
                    },
                    "post_step_population_number_density_m3": post_populations.tolist(),
                    "post_step_ion_fraction": float(rate_step["ion_fraction"]),
                    "post_step_temperature_K": float(rate_step["temperature_K"]),
                    "post_step_pressure_Pa": float(rate_step["pressure_Pa"]),
                    "post_step_free_free_group_emissivity_W_m3": post_emissivity["free_free_group_emissivity_W_m3"],
                    "post_step_line_emissivity_W_m3": post_emissivity["line_emissivity_W_m3"],
                    "post_step_line_group_emissivity_W_m3": post_emissivity["line_group_emissivity_W_m3"],
                    "post_step_free_bound_group_emissivity_W_m3": post_emissivity["free_bound_group_emissivity_W_m3"],
                    "post_step_two_photon_group_emissivity_W_m3": post_emissivity["two_photon_group_emissivity_W_m3"],
                    "post_step_total_group_emissivity_W_m3": post_emissivity["total_group_emissivity_W_m3"],
                    "post_step_bolometric_emissivity_W_m3": float(post_emissivity["bolometric_emissivity_W_m3"]),
                }
            )
    return {
        "thermo_atomic": thermo,
        "hllc_flux_cases": [
            {"left": [1.0, 0.0, 1.0], "right": [0.125, 0.0, 0.1], "flux": hllc_flux((1, 0, 1), (0.125, 0, 0.1)).tolist()},
            {"left": [1.0, 1.5, 0.5], "right": [0.8, -0.2, 0.7], "flux": hllc_flux((1, 1.5, 0.5), (0.8, -0.2, 0.7)).tolist()},
        ],
        "sod_128_t0p2": integrate_sod(),
    }


def reference_corpus_parity(
    model: dict[str, object], corpus: object, tolerance: float = 1.0e-9
) -> list[dict[str, object]]:
    """Golden-corpus parity between the Python constitutive oracle and the model JSON.

    ``model["reference_cases"]`` is the committed, hash-bound corpus that the
    runtime consumes.  This recomputes the constitutive outputs from the stored
    per-case inputs and compares them against that corpus, so an edit to
    line_group_fraction / free_bound_group_fraction / two_photon_group_weight /
    free_free_emissivity_w_m3_hz / hllc_flux that is not reflected in the model
    JSON fails here instead of leaving two uncompared implementations.
    """
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, **evidence: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "evidence": evidence})

    if not isinstance(corpus, dict):
        check("golden_corpus_present", False, reason="model JSON carries no reference_cases corpus")
        return checks

    recomputed = reference_cases(model)
    fresh_cases = recomputed["thermo_atomic"]
    fresh_keys = {
        (float(case["temperature_K"]), float(case["hydrogen_number_density_m3"]))
        for case in fresh_cases
    }
    stored_rows = corpus.get("thermo_atomic", [])
    if not isinstance(stored_rows, list):
        stored_rows = []
    stored_cases: dict[tuple[float, float], dict[str, object]] = {}
    malformed_rows = 0
    for case in stored_rows:
        if not isinstance(case, dict):
            malformed_rows += 1
            continue
        try:
            key = (float(case["temperature_K"]), float(case["hydrogen_number_density_m3"]))
        except (KeyError, TypeError, ValueError):
            malformed_rows += 1
            continue
        stored_cases[key] = case
    check(
        "golden_thermo_case_index",
        malformed_rows == 0
        and len(stored_rows) == len(stored_cases) == len(fresh_cases)
        and len(fresh_keys) == len(fresh_cases)
        and len(fresh_cases) > 0,
        stored_rows=len(stored_rows),
        stored_unique_cases=len(stored_cases),
        recomputed_cases=len(fresh_cases),
        recomputed_unique_cases=len(fresh_keys),
        malformed_rows=malformed_rows,
    )
    surfaces = (
        ("golden_line_group_emissivity", "line_group_emissivity_W_m3"),
        ("golden_free_bound_group_emissivity", "free_bound_group_emissivity_W_m3"),
        ("golden_two_photon_group_emissivity", "two_photon_group_emissivity_W_m3"),
        ("golden_free_free_group_emissivity", "free_free_group_emissivity_W_m3"),
        ("golden_total_group_emissivity", "total_group_emissivity_W_m3"),
        ("golden_ion_fraction", "ion_fraction"),
        ("golden_pressure_Pa", "pressure_Pa"),
    )
    for name, key in surfaces:
        worst_abs = 0.0
        worst_rel = 0.0
        compared = 0
        for case in fresh_cases:
            stored = stored_cases.get(
                (float(case["temperature_K"]), float(case["hydrogen_number_density_m3"]))
            )
            if stored is None or key not in stored:
                continue
            try:
                actual = np.asarray(case[key], dtype=np.float64)
                expected = np.asarray(stored[key], dtype=np.float64)
            except (TypeError, ValueError):
                worst_abs = math.inf
                worst_rel = math.inf
                continue
            if actual.shape != expected.shape:
                worst_abs = math.inf
                worst_rel = math.inf
                continue
            difference = np.abs(actual - expected)
            if difference.size:
                worst_abs = max(worst_abs, float(np.max(difference)))
                worst_rel = max(worst_rel, float(np.max(difference / np.maximum(np.abs(expected), 1.0e-30))))
            compared += 1
        check(
            name,
            compared == len(fresh_cases) and worst_rel <= tolerance,
            compared_cases=compared,
            expected_cases=len(fresh_cases),
            max_abs_error=worst_abs,
            max_rel_error=worst_rel,
            tolerance=tolerance,
        )

    hllc_stored = corpus.get("hllc_flux_cases", [])
    hllc_fresh = recomputed["hllc_flux_cases"]
    hllc_ok = isinstance(hllc_stored, list) and len(hllc_stored) == len(hllc_fresh)
    hllc_worst = 0.0
    if hllc_ok:
        for fresh, stored in zip(hllc_fresh, hllc_stored):
            actual = np.asarray(fresh["flux"], dtype=np.float64)
            expected = np.asarray(stored.get("flux", []), dtype=np.float64)
            if actual.shape != expected.shape:
                hllc_worst = math.inf
                continue
            hllc_worst = max(hllc_worst, float(np.max(np.abs(actual - expected))))
    else:
        hllc_worst = math.inf
    check(
        "golden_hllc_flux_cases",
        bool(hllc_ok and hllc_worst <= tolerance),
        cases=len(hllc_fresh),
        max_abs_error=hllc_worst,
        tolerance=tolerance,
    )

    sod_stored = corpus.get("sod_128_t0p2", {})
    sod_fresh = recomputed["sod_128_t0p2"]
    sod_keys = ("density", "velocity", "pressure", "x")
    sod_ok = isinstance(sod_stored, dict) and all(
        len(sod_stored.get(key, [])) == len(sod_fresh[key]) for key in sod_keys
    )
    sod_worst = 0.0
    if sod_ok:
        for key in sod_keys:
            actual = np.asarray(sod_fresh[key], dtype=np.float64)
            expected = np.asarray(sod_stored[key], dtype=np.float64)
            sod_worst = max(sod_worst, float(np.max(np.abs(actual - expected))))
    else:
        sod_worst = math.inf
    check(
        "golden_sod_128_t0p2",
        bool(sod_ok and sod_worst <= tolerance),
        cells=len(sod_fresh["density"]),
        max_abs_error=sod_worst,
        tolerance=tolerance,
    )
    return checks


def validate_model(model: dict[str, object], golden_corpus: object | None = None) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, **evidence: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "evidence": evidence})

    grid = model["frequency_grid"]
    assert isinstance(grid, dict)
    edges = np.asarray(grid["frequency_edges_Hz"], dtype=np.float64)
    check("frequency_edges_increasing", bool(np.all(np.isfinite(edges)) and np.all(np.diff(edges) > 0.0)), count=len(edges))
    transitions = model["transitions"]
    assert isinstance(transitions, list)
    unique_groups = True
    for record in transitions:
        assert isinstance(record, dict)
        frequency = float(record["frequency_Hz"])
        index = int(record["group_index"])
        unique_groups = unique_groups and edges[index] <= frequency < edges[index + 1]
    check("all_lines_have_exact_group", unique_groups, line_count=len(transitions))
    check("all_shell_transitions_present", len(transitions) == 15, expected=15, actual=len(transitions))
    weights = np.asarray(grid["observer_xyz_average"], dtype=np.float64)
    directions = np.asarray(grid["ordinates"], dtype=np.float64)
    angular_weights = np.asarray(grid["ordinate_weights_sr"], dtype=np.float64)
    angular_norm = float(np.sum(angular_weights))
    angular_first = np.sum(angular_weights[:, None] * directions, axis=0)
    angular_second = np.einsum("m,mi,mj->ij", angular_weights, directions, directions)
    check(
        "lebedev26_quadrature",
        bool(
            directions.shape == (26, 3)
            and angular_weights.shape == (26,)
            and np.max(np.abs(np.linalg.norm(directions, axis=1) - 1.0)) <= 2.0e-15
            and abs(angular_norm - 4.0 * PI) <= 2.0e-14
            and np.max(np.abs(angular_first)) <= 2.0e-15
            and np.max(np.abs(angular_second - np.eye(3) * (4.0 * PI / 3.0))) <= 2.0e-14
        ),
        direction_count=int(directions.shape[0]),
        weight_sum=angular_norm,
        first_moment=angular_first.tolist(),
    )
    check("observer_weights_finite_nonnegative", bool(weights.shape == (24, 3) and np.all(np.isfinite(weights)) and np.all(weights >= 0.0)), shape=list(weights.shape))
    rates = model["kinetics"]
    assert isinstance(rates, dict)
    rate_arrays = [np.asarray(rates["collisional_ionization_m3_s"]), np.asarray(rates["case_a_recombination_m3_s"])]
    for pair in rates["collisional_transition_rates"]:  # type: ignore[union-attr]
        rate_arrays.extend((np.asarray(pair["excitation_m3_s"]), np.asarray(pair["deexcitation_m3_s"])))
    check("rate_tables_finite_nonnegative", all(np.all(np.isfinite(values)) and np.all(values >= 0.0) for values in rate_arrays), arrays=len(rate_arrays))
    interpolation = collisional_interpolation_invariant(model)
    check(
        "collisional_rate_interpolation_detailed_balance",
        bool(interpolation.get("passed", False)),
        **{key: value for key, value in interpolation.items() if key != "passed"},
    )
    reference_frequency = 1.0e12
    reference_temperature = 1.0e4
    reference_electron_m3 = 3.0e8
    reference_ion_m3 = 2.0e8
    reference_gaunt = float(np.clip(
        (math.sqrt(3.0) / PI)
        * math.log(max(2.25 * K_BOLTZMANN * reference_temperature
                       / (H_PLANCK * reference_frequency), 1.000001)),
        1.0, 5.0,
    ))
    reference_cgs = (
        6.8e-38 * (reference_electron_m3 * 1.0e-6)
        * (reference_ion_m3 * 1.0e-6) * reference_temperature**-0.5
        * math.exp(-H_PLANCK * reference_frequency
                   / (K_BOLTZMANN * reference_temperature))
        * reference_gaunt
    )
    reference_si = reference_cgs * 1.0e-1
    actual_si = float(free_free_emissivity_w_m3_hz(
        reference_frequency, reference_temperature,
        reference_electron_m3, reference_ion_m3,
    ))
    check(
        "free_free_cgs_to_si",
        math.isclose(actual_si, reference_si, rel_tol=2.0e-15),
        actual_W_m3_Hz=actual_si,
        expected_W_m3_Hz=reference_si,
    )
    source = model["source_record"]
    assert isinstance(source, dict)
    check(
        "external_source_identities_pinned",
        source["line_response_sha256"] == NIST_LINE_RESPONSE_SHA256 and source["level_response_sha256"] == NIST_LEVEL_RESPONSE_SHA256,
        line_sha256=source["line_response_sha256"], level_sha256=source["level_response_sha256"],
    )
    checksums_valid = True
    for key in ("constants", "source_record", "unit_defaults", "frequency_grid", "kinetics"):
        nested = model[key]
        assert isinstance(nested, dict)
        value: dict[str, object] = dict(nested)
        expected = value.pop(f"{key}_sha256")
        checksums_valid = checksums_valid and digest(value) == expected
    whole = dict(model)
    expected_model = whole.pop("model_sha256")
    check("nested_hashes_valid", checksums_valid)
    check("model_hash_valid", digest(whole) == expected_model, model_sha256=expected_model)
    if golden_corpus is not None:
        checks.extend(reference_corpus_parity(model, golden_corpus))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the existing model JSON at --output in place (golden-corpus parity included) without regenerating it",
    )
    args = parser.parse_args()

    if args.check:
        if not args.output.is_file():
            print(f"model JSON not found: {args.output}")
            return 1
        loaded = json.loads(args.output.read_text(encoding="utf-8"))
        checks = validate_model(loaded, golden_corpus=loaded.get("reference_cases"))
        passed = all(bool(item["passed"]) for item in checks)
        receipt = {
            "schema": "cassi-physical-matter-reference-v1",
            "mode": "check",
            "model_sha256": str(loaded.get("model_sha256", "")),
            "checks": checks,
            "passed": passed,
            "expected_total": len(checks),
            "failed": [item["name"] for item in checks if not item["passed"]],
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"PHYSICAL MATTER REFERENCE (check): {'PASS' if passed else 'FAIL'} ({len(checks) - len(receipt['failed'])}/{len(checks)})")
        print(f"model_sha256={receipt['model_sha256']}")
        print(f"source={args.output}")
        return 0 if passed else 1

    model = build_model()
    cases = reference_cases(model)
    model["reference_cases"] = cases
    # Reference cases are part of the final identity.
    model["model_sha256"] = digest({key: value for key, value in model.items() if key != "model_sha256"})
    checks = validate_model(model)
    passed = all(bool(item["passed"]) for item in checks)
    receipt = {
        "schema": "cassi-physical-matter-reference-v1",
        "model_sha256": model["model_sha256"],
        "checks": checks,
        "passed": passed,
        "expected_total": len(checks),
        "failed": [item["name"] for item in checks if not item["passed"]],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PHYSICAL MATTER REFERENCE: {'PASS' if passed else 'FAIL'} ({len(checks) - len(receipt['failed'])}/{len(checks)})")
    print(f"model_sha256={model['model_sha256']}")
    print(f"output={args.output}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
