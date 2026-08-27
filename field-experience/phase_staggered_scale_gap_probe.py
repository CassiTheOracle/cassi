#!/usr/bin/env python3
"""Single-run probe for phase-staggered radial layers and scale gaps.

Protocol: field-experience/phase-staggered-scale-gap-pre-registration.md
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


PHI = (1.0 + math.sqrt(5.0)) / 2.0
TAU = 2.0 * math.pi
TOL = 1.0e-12

R_MAX = 60.0
DR = 0.025
DT = 0.01
T_END = 220.0
T_RAMP = 20.0
PHASOR_START = 190.0
ABSORBER_START = 48.0
ABSORBER_MAX = 2.0
FIT_R_MIN = 10.0
FIT_R_MAX = 40.0
SOURCE_SIGMA = 0.4


class ProbeFailure(RuntimeError):
    pass


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    return value


def _relative_error(measured: float, expected: float) -> float:
    return abs(measured - expected) / max(abs(expected), 1.0e-300)


def beat_stage() -> dict[str, Any]:
    ell_n = 1.0
    ell_prev = 1.0 / PHI
    ell_next = PHI
    k_y = TAU / ell_n
    k_i = TAU / ell_prev
    delta_k = k_i - k_y

    antinodes = np.arange(8, dtype=np.float64) * ell_next
    nodes = (np.arange(8, dtype=np.float64) + 0.5) * ell_next
    k_mean = 0.5 * (k_y + k_i)

    z_antinode = np.exp(1j * k_y * antinodes) + np.exp(1j * k_i * antinodes)
    envelope_antinode = np.exp(-1j * k_mean * antinodes) * z_antinode
    normalized = np.real(envelope_antinode) / 2.0
    parity_expected = (-1.0) ** np.arange(8)

    z_node = np.exp(1j * k_y * nodes) + np.exp(1j * k_i * nodes)
    envelope_node = np.exp(-1j * k_mean * nodes) * z_node

    adjacent = envelope_antinode[1:] * np.conj(envelope_antinode[:-1])
    next_nearest = envelope_antinode[2:] * np.conj(envelope_antinode[:-2])
    adjacent_corr = np.real(adjacent) / np.abs(adjacent)
    next_corr = np.real(next_nearest) / np.abs(next_nearest)

    gates = {
        "A1_scale_closure": abs(delta_k - TAU / ell_next) < TOL,
        "A2_phase_parity": float(np.max(np.abs(normalized - parity_expected))) < TOL,
        "A3_nodes": float(np.max(np.abs(envelope_node))) < TOL,
        "A4_two_rung_return": (
            float(np.max(np.abs(adjacent_corr + 1.0))) < TOL
            and float(np.max(np.abs(next_corr - 1.0))) < TOL
        ),
    }

    contrasts: list[dict[str, float]] = []
    for eta in (1.0, 0.8, 0.5):
        a_y = 1.0
        a_i = eta
        z_max = a_y + a_i
        z_min = 1j * (a_i - a_y)
        i_max = abs(z_max) ** 2
        i_min = abs(z_min) ** 2
        measured = (i_max - i_min) / (i_max + i_min)
        predicted = 2.0 * a_y * a_i / (a_y * a_y + a_i * a_i)
        contrasts.append(
            {
                "eta": eta,
                "i_max": i_max,
                "i_min": i_min,
                "contrast_measured": measured,
                "contrast_predicted": predicted,
                "residual": abs(measured - predicted),
            }
        )

    contrast_values = [row["contrast_measured"] for row in contrasts]
    b1_residual = max(
        max(abs(row["i_max"] - (1.0 + row["eta"]) ** 2) for row in contrasts),
        max(abs(row["i_min"] - (1.0 - row["eta"]) ** 2) for row in contrasts),
    )
    gates.update(
        {
            "B1_extrema": b1_residual < TOL,
            "B2_contrast_formula": max(row["residual"] for row in contrasts) < TOL,
            "B3_monotone_contrast": contrast_values[0] > contrast_values[1] > contrast_values[2],
        }
    )

    return {
        "ell_n": ell_n,
        "ell_previous": ell_prev,
        "ell_next": ell_next,
        "k_y": k_y,
        "k_i": k_i,
        "delta_k": delta_k,
        "closure_residual": abs(delta_k - TAU / ell_next),
        "phase_parity_residual": float(np.max(np.abs(normalized - parity_expected))),
        "node_max": float(np.max(np.abs(envelope_node))),
        "adjacent_correlation": float(np.mean(adjacent_corr)),
        "next_nearest_correlation": float(np.mean(next_corr)),
        "contrasts": contrasts,
        "gates": gates,
    }


def spacing_stage() -> dict[str, Any]:
    additive = np.arange(1, 8, dtype=np.float64) * PHI
    additive_steps = np.diff(additive)
    r_add = float(np.max(np.abs(additive_steps / PHI - 1.0)))
    log_steps = np.log(additive[1:] / additive[:-1]) / math.log(PHI)
    r_log = float(np.sqrt(np.mean((log_steps - 1.0) ** 2)))

    multiplicative = PHI ** np.arange(8, dtype=np.float64)
    ratios = multiplicative[1:] / multiplicative[:-1]
    values = np.cos(math.pi * np.arange(8, dtype=np.float64))
    ratio_residual = float(np.max(np.abs(ratios / PHI - 1.0)))
    parity_residual = float(np.max(np.abs(values[1:] + values[:-1])))

    sample_r = PHI ** 2.5
    c_u = 1.0
    analytic_speed = c_u * math.log(PHI) * sample_r
    finite_speed = (
        PHI ** (2.5 + c_u * 1.0e-6) - PHI ** (2.5 - c_u * 1.0e-6)
    ) / (2.0e-6)
    speed_residual = _relative_error(finite_speed, analytic_speed)

    gates = {
        "C1_additive_classification": r_add < TOL and r_log > 0.25,
        "C2_multiplicative_ratio": ratio_residual < TOL,
        "C3_log_phase_parity": parity_residual < TOL,
        "C4_log_surface_speed": speed_residual < TOL,
    }

    return {
        "ordinary_additive_residual": r_add,
        "ordinary_log_rms": r_log,
        "log_ratio_residual": ratio_residual,
        "log_phase_parity_residual": parity_residual,
        "log_surface_speed_relative_residual": speed_residual,
        "gates": gates,
    }


def _source_ramp(t: float) -> float:
    if t >= T_RAMP:
        return 1.0
    return 0.5 * (1.0 - math.cos(math.pi * t / T_RAMP))


def _simulate_mode(omega: float, mass: float, source_amplitude: float) -> dict[str, Any]:
    n = int(round(R_MAX / DR)) + 1
    r = np.linspace(0.0, R_MAX, n, dtype=np.float64)
    damping = np.zeros_like(r)
    absorber = r >= ABSORBER_START
    damping[absorber] = ABSORBER_MAX * (
        (r[absorber] - ABSORBER_START) / (R_MAX - ABSORBER_START)
    ) ** 2
    source_profile = r * np.exp(-(r * r) / (2.0 * SOURCE_SIGMA * SOURCE_SIGMA))
    source_profile /= float(np.max(source_profile))

    u_previous = np.zeros_like(r)
    u = np.zeros_like(r)
    phasor = np.zeros(n, dtype=np.complex128)
    samples = 0
    dt2 = DT * DT
    damp_minus = 1.0 - 0.5 * damping * DT
    damp_plus = 1.0 + 0.5 * damping * DT
    mass2 = mass * mass
    n_steps = int(round(T_END / DT))

    for step in range(n_steps):
        t = step * DT
        if t >= PHASOR_START:
            phasor += u * np.exp(-1j * omega * t) * DT
            samples += 1

        laplacian = np.zeros_like(u)
        laplacian[1:-1] = (u[2:] - 2.0 * u[1:-1] + u[:-2]) / (DR * DR)
        drive = source_amplitude * source_profile * _source_ramp(t) * math.cos(omega * t)
        rhs = laplacian - mass2 * u + drive
        u_next = (2.0 * u - damp_minus * u_previous + dt2 * rhs) / damp_plus
        u_next[0] = 0.0
        u_next[-1] = 0.0
        u_previous, u = u, u_next

    phasor *= 2.0 / (T_END - PHASOR_START)
    return {
        "r": r,
        "phasor": phasor,
        "samples": samples,
        "finite": bool(np.all(np.isfinite(u)) and np.all(np.isfinite(phasor))),
        "max_abs": float(np.max(np.abs(u))),
    }


def _phase_fit(r: np.ndarray, phasor: np.ndarray) -> dict[str, float]:
    mask = (r >= FIT_R_MIN) & (r <= FIT_R_MAX)
    amplitudes = np.abs(phasor[mask])
    if float(np.median(amplitudes)) <= 1.0e-12:
        return {
            "k": float("nan"),
            "slope": float("nan"),
            "intercept": float("nan"),
            "r2": float("nan"),
            "median_amplitude": float(np.median(amplitudes)),
        }
    phases = np.unwrap(np.angle(phasor[mask]))
    x = r[mask]
    slope, intercept = np.polyfit(x, phases, 1)
    fitted = slope * x + intercept
    residual = float(np.sum((phases - fitted) ** 2))
    total = float(np.sum((phases - np.mean(phases)) ** 2))
    r2 = 1.0 if total == 0.0 else 1.0 - residual / total
    return {
        "k": abs(float(slope)),
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": r2,
        "median_amplitude": float(np.median(amplitudes)),
    }


def _linear_complex(r: np.ndarray, values: np.ndarray, points: np.ndarray) -> np.ndarray:
    real = np.interp(points, r, np.real(values))
    imag = np.interp(points, r, np.imag(values))
    return real + 1j * imag


def _phase_surfaces(slope: float, intercept: float, offset: float) -> np.ndarray:
    phase_a = slope * FIT_R_MIN + intercept
    phase_b = slope * FIT_R_MAX + intercept
    lower = min(phase_a, phase_b)
    upper = max(phase_a, phase_b)
    m_min = math.ceil((lower - offset) / TAU)
    m_max = math.floor((upper - offset) / TAU)
    if m_max < m_min:
        return np.empty(0, dtype=np.float64)
    targets = offset + TAU * np.arange(m_min, m_max + 1, dtype=np.float64)
    points = (targets - intercept) / slope
    return np.sort(points[(points >= FIT_R_MIN) & (points <= FIT_R_MAX)])


def radial_stage() -> dict[str, Any]:
    omega_gap = PHI
    omega_tuned = PHI ** 1.5
    arm_specs = {
        "D0_subgap": {"omega": 0.9 * PHI, "source_rho": 1.0, "source_epsilon": 1.0},
        "D1_tuned": {"omega": omega_tuned, "source_rho": 1.0, "source_epsilon": 1.0},
        "D2_generic": {"omega": 2.5, "source_rho": 1.0, "source_epsilon": 1.0},
        "D3_rho_only": {"omega": omega_tuned, "source_rho": 1.0, "source_epsilon": 0.0},
    }

    arms: dict[str, Any] = {}
    for name, spec in arm_specs.items():
        omega = spec["omega"]
        rho = _simulate_mode(omega, 0.0, spec["source_rho"])
        epsilon = _simulate_mode(omega, omega_gap, spec["source_epsilon"])
        fit_rho = _phase_fit(rho["r"], rho["phasor"])
        fit_epsilon = _phase_fit(epsilon["r"], epsilon["phasor"])
        expected_k_rho = omega
        expected_k_epsilon = (
            math.sqrt(omega * omega - omega_gap * omega_gap)
            if omega > omega_gap and spec["source_epsilon"] != 0.0
            else None
        )
        arms[name] = {
            "spec": spec,
            "rho": rho,
            "epsilon": epsilon,
            "fit_rho": fit_rho,
            "fit_epsilon": fit_epsilon,
            "expected_k_rho": expected_k_rho,
            "expected_k_epsilon": expected_k_epsilon,
        }

    d0 = arms["D0_subgap"]
    d1 = arms["D1_tuned"]
    d2 = arms["D2_generic"]
    d3 = arms["D3_rho_only"]

    d0_r = d0["rho"]["r"]
    amp_eps_12 = float(np.abs(_linear_complex(d0_r, d0["epsilon"]["phasor"], np.array([12.0]))[0]))
    amp_eps_30 = float(np.abs(_linear_complex(d0_r, d0["epsilon"]["phasor"], np.array([30.0]))[0]))
    d0_attenuation = amp_eps_30 / max(amp_eps_12, 1.0e-300)

    def fit_quality(arm: dict[str, Any], key: str) -> bool:
        fit = arm[f"fit_{key}"]
        expected = arm[f"expected_k_{key}"]
        return (
            expected is not None
            and fit["median_amplitude"] > 1.0e-6
            and fit["r2"] >= 0.95
            and _relative_error(fit["k"], expected) <= 0.02
        )

    quality = {
        "finite": all(
            arm[mode]["finite"]
            for arm in arms.values()
            for mode in ("rho", "epsilon")
        ),
        "courant": DT / DR,
        "D0_rho_fit": fit_quality(d0, "rho"),
        "D1_rho_fit": fit_quality(d1, "rho"),
        "D1_epsilon_fit": fit_quality(d1, "epsilon"),
        "D2_rho_fit": fit_quality(d2, "rho"),
        "D2_epsilon_fit": fit_quality(d2, "epsilon"),
        "D3_rho_fit": fit_quality(d3, "rho"),
        "D0_epsilon_attenuation": d0_attenuation,
    }

    tuned_ratio = d1["fit_rho"]["k"] / d1["fit_epsilon"]["k"]
    generic_ratio = d2["fit_rho"]["k"] / d2["fit_epsilon"]["k"]
    d3_epsilon_max = float(np.max(np.abs(d3["epsilon"]["phasor"])))

    r = d1["rho"]["r"]
    rho_phase = np.unwrap(np.angle(d1["rho"]["phasor"][(r >= FIT_R_MIN) & (r <= FIT_R_MAX)]))
    epsilon_phase = np.unwrap(np.angle(d1["epsilon"]["phasor"][(r >= FIT_R_MIN) & (r <= FIT_R_MAX)]))
    rel_phase = np.unwrap(rho_phase - epsilon_phase)
    fit_r = r[(r >= FIT_R_MIN) & (r <= FIT_R_MAX)]
    rel_slope, rel_intercept = np.polyfit(fit_r, rel_phase, 1)
    constructive = _phase_surfaces(float(rel_slope), float(rel_intercept), 0.0)
    destructive = _phase_surfaces(float(rel_slope), float(rel_intercept), math.pi)

    delta_k_fit = abs(float(rel_slope))
    expected_spacing = TAU / delta_k_fit
    constructive_spacing = np.diff(constructive)
    destructive_spacing = np.diff(destructive)
    spacing_values = np.concatenate([constructive_spacing, destructive_spacing])
    spacing_median = float(np.median(spacing_values)) if len(spacing_values) else float("nan")
    spacing_residual = _relative_error(spacing_median, expected_spacing)

    y_rho = d1["rho"]["phasor"] / PHI
    y_epsilon = d1["epsilon"]["phasor"] / (PHI * PHI)
    y_total = y_rho + y_epsilon

    rho_fit = d1["fit_rho"]
    epsilon_fit = d1["fit_epsilon"]
    common_slope = 0.5 * (rho_fit["slope"] + epsilon_fit["slope"])
    common_intercept = 0.5 * (rho_fit["intercept"] + epsilon_fit["intercept"])
    y_constructive = _linear_complex(r, y_total, constructive)
    common_phase = common_slope * constructive + common_intercept
    demodulated = y_constructive * np.exp(-1j * common_phase)
    parity_correlations = np.real(demodulated[1:] * np.conj(demodulated[:-1])) / (
        np.abs(demodulated[1:]) * np.abs(demodulated[:-1])
    )
    parity_mean = float(np.mean(parity_correlations))

    y_destructive = _linear_complex(r, y_total, destructive)
    i_constructive = np.abs(y_constructive) ** 2
    i_destructive = np.abs(y_destructive) ** 2
    i_max = float(np.median(i_constructive))
    i_min = float(np.median(i_destructive))
    measured_contrast = (i_max - i_min) / (i_max + i_min)

    mask = (r >= FIT_R_MIN) & (r <= FIT_R_MAX)
    a_rho = float(np.median(np.abs(y_rho[mask])))
    a_epsilon = float(np.median(np.abs(y_epsilon[mask])))
    predicted_contrast = 2.0 * a_rho * a_epsilon / (
        a_rho * a_rho + a_epsilon * a_epsilon
    )
    contrast_residual = abs(measured_contrast - predicted_contrast)

    gates = {
        "quality_finite": quality["finite"],
        "quality_courant": abs(quality["courant"] - 0.4) < TOL,
        "quality_D0_rho_fit": quality["D0_rho_fit"],
        "quality_D1_rho_fit": quality["D1_rho_fit"],
        "quality_D1_epsilon_fit": quality["D1_epsilon_fit"],
        "quality_D2_rho_fit": quality["D2_rho_fit"],
        "quality_D2_epsilon_fit": quality["D2_epsilon_fit"],
        "quality_D3_rho_fit": quality["D3_rho_fit"],
        "D1_channel_gap": d0_attenuation <= 1.0e-2,
        "D2_tuned_ratio": _relative_error(tuned_ratio, PHI) <= 0.02,
        "D3_generic_control": abs(generic_ratio - PHI) >= 0.1,
        "D4_source_requirement": d3_epsilon_max < TOL,
        "D5_layer_spacing": (
            len(constructive) >= 3
            and len(destructive) >= 3
            and spacing_residual <= 0.02
        ),
        "D6_phase_parity": parity_mean <= -0.95,
        "D7_contrast": contrast_residual <= 0.05 and measured_contrast > 0.8,
    }

    serializable_arms: dict[str, Any] = {}
    for name, arm in arms.items():
        serializable_arms[name] = {
            "spec": arm["spec"],
            "expected_k_rho": arm["expected_k_rho"],
            "expected_k_epsilon": arm["expected_k_epsilon"],
            "fit_rho": arm["fit_rho"],
            "fit_epsilon": arm["fit_epsilon"],
            "rho_max_abs": arm["rho"]["max_abs"],
            "epsilon_max_abs": arm["epsilon"]["max_abs"],
        }

    return {
        "omega_gap": omega_gap,
        "omega_tuned": omega_tuned,
        "arms": serializable_arms,
        "D0_epsilon_attenuation": d0_attenuation,
        "tuned_k_ratio": tuned_ratio,
        "tuned_ratio_relative_residual": _relative_error(tuned_ratio, PHI),
        "generic_k_ratio": generic_ratio,
        "generic_phi_distance": abs(generic_ratio - PHI),
        "D3_epsilon_max": d3_epsilon_max,
        "constructive_surfaces": constructive,
        "destructive_surfaces": destructive,
        "spacing_median": spacing_median,
        "spacing_expected": expected_spacing,
        "spacing_relative_residual": spacing_residual,
        "phase_parity_mean": parity_mean,
        "modal_amplitude_rho": a_rho,
        "modal_amplitude_epsilon": a_epsilon,
        "contrast_measured": measured_contrast,
        "contrast_predicted": predicted_contrast,
        "contrast_residual": contrast_residual,
        "gates": gates,
    }


def chain_stage() -> dict[str, Any]:
    cells = 64
    sites = 2 * cells

    def hamiltonian(k1: float, k2: float) -> np.ndarray:
        h = np.zeros((sites, sites), dtype=np.float64)
        for site in range(sites):
            neighbor = (site + 1) % sites
            coupling = k1 if site % 2 == 0 else k2
            h[site, neighbor] = -coupling
            h[neighbor, site] = -coupling
        return h

    uniform = hamiltonian(1.0, 1.0)
    gauge = np.diag((-1.0) ** np.arange(sites))
    gauge_residual = float(np.max(np.abs(gauge @ uniform @ gauge + uniform)))
    uniform_eigenvalues = np.linalg.eigvalsh(uniform)
    uniform_gap = 2.0 * float(np.min(np.abs(uniform_eigenvalues)))
    spectrum_residual = float(
        np.max(np.abs(np.sort(uniform_eigenvalues) - np.sort(-uniform_eigenvalues)))
    )

    k1 = 1.25
    k2 = 0.75
    dimerized = hamiltonian(k1, k2)
    dimerized_eigenvalues = np.linalg.eigvalsh(dimerized)
    dimerized_gap = 2.0 * float(np.min(np.abs(dimerized_eigenvalues)))
    predicted_gap = 2.0 * abs(k1 - k2)
    transmission_intensity = (k2 / k1) ** 24

    gates = {
        "E1_phase_only_null": (
            gauge_residual < TOL
            and spectrum_residual < TOL
            and uniform_gap < TOL
        ),
        "E2_node_modulated_gap": abs(dimerized_gap - predicted_gap) < TOL,
        "E3_transmission_suppression": transmission_intensity < 1.0e-4,
    }

    return {
        "cells": cells,
        "uniform_gauge_residual": gauge_residual,
        "uniform_spectrum_residual": spectrum_residual,
        "uniform_central_gap": uniform_gap,
        "k1": k1,
        "k2": k2,
        "dimerized_central_gap": dimerized_gap,
        "predicted_central_gap": predicted_gap,
        "gap_residual": abs(dimerized_gap - predicted_gap),
        "barrier_cells": 12,
        "transmission_intensity": transmission_intensity,
        "gates": gates,
    }


def _all_gates(stage: dict[str, Any]) -> bool:
    return all(bool(value) for value in stage["gates"].values())


def main() -> int:
    beat = beat_stage()
    spacing = spacing_stage()
    radial = radial_stage()
    chain = chain_stage()

    beat_pass = _all_gates(beat)
    spacing_pass = _all_gates(spacing)
    radial_pass = _all_gates(radial)
    chain_pass = _all_gates(chain)

    verdicts = {
        "beat_layer_claim": "SUPPORTS" if beat_pass else "CONTRADICTS",
        "radial_layer_claim": "EMERGES CONDITIONAL" if radial_pass else "INCONCLUSIVE",
        "automatic_phi_selection": (
            "CONTRADICTS"
            if radial["gates"]["D2_tuned_ratio"] and radial["gates"]["D3_generic_control"]
            else "INCONCLUSIVE"
        ),
        "phase_gap_claim": (
            "CONTRADICTS" if chain["gates"]["E1_phase_only_null"] else "SUPPORTS"
        ),
        "node_modulated_gap_claim": (
            "EMERGES CONDITIONAL"
            if chain["gates"]["E2_node_modulated_gap"]
            and chain["gates"]["E3_transmission_suppression"]
            else "DOES NOT EMERGE"
        ),
    }

    results = {
        "protocol": "field-experience/phase-staggered-scale-gap-pre-registration.md",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "constants": {
            "phi": PHI,
            "c": 1.0,
            "omega0": 1.0,
            "radial": {
                "r_max": R_MAX,
                "dr": DR,
                "dt": DT,
                "t_end": T_END,
                "t_ramp": T_RAMP,
                "phasor_start": PHASOR_START,
                "absorber_start": ABSORBER_START,
                "absorber_max": ABSORBER_MAX,
                "fit_r_min": FIT_R_MIN,
                "fit_r_max": FIT_R_MAX,
                "source_sigma": SOURCE_SIGMA,
            },
        },
        "stages": {
            "beat": beat,
            "spacing": spacing,
            "radial": radial,
            "chain": chain,
        },
        "verdicts": verdicts,
        "all_declared_certificates_passed": beat_pass and spacing_pass and radial_pass and chain_pass,
    }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(__file__).resolve().parents[1] / "runs" / f"{timestamp}_phase_staggered_scale_gap"
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "results.json"
    output_path.write_text(json.dumps(_jsonable(results), indent=2) + "\n", encoding="utf-8")

    print(
        "A/B",
        "PASS" if beat_pass else "FAIL",
        f"closure={beat['closure_residual']:.3e}",
        f"node={beat['node_max']:.3e}",
        f"adjacent={beat['adjacent_correlation']:.12f}",
    )
    print(
        "C",
        "PASS" if spacing_pass else "FAIL",
        f"additive={spacing['ordinary_additive_residual']:.3e}",
        f"ordinary_log_rms={spacing['ordinary_log_rms']:.6f}",
        f"log_ratio={spacing['log_ratio_residual']:.3e}",
    )
    print(
        "D",
        "PASS" if radial_pass else "FAIL",
        f"gap_attenuation={radial['D0_epsilon_attenuation']:.3e}",
        f"tuned_ratio={radial['tuned_k_ratio']:.9f}",
        f"generic_ratio={radial['generic_k_ratio']:.9f}",
        f"spacing_residual={radial['spacing_relative_residual']:.3e}",
        f"phase_parity={radial['phase_parity_mean']:.9f}",
        f"contrast={radial['contrast_measured']:.9f}",
    )
    print(
        "E",
        "PASS" if chain_pass else "FAIL",
        f"uniform_gap={chain['uniform_central_gap']:.3e}",
        f"dimer_gap={chain['dimerized_central_gap']:.12f}",
        f"transmission={chain['transmission_intensity']:.3e}",
    )
    for name, verdict in verdicts.items():
        print(f"VERDICT {name}: {verdict}")
    print(f"RAW {output_path.as_posix()}")

    if results["all_declared_certificates_passed"]:
        print("ALL DECLARED CERTIFICATES PASSED")
        return 0
    print("DECLARED CERTIFICATE FAILURE")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
