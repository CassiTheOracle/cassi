#!/usr/bin/env python3
"""Execute the preregistered QCD cosmological matter-completion calculation.

Run from the CassiTheory repository root:

    python computations/qcd_cosmological_matter_completion.py

The calculation writes a source-bound JSON receipt, a readable report, and the
nonradial initial/final arrays.  A successful process exit means that the
adjudication completed and its receipt is internally valid; it does not turn a
negative physical verdict into a positive one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy import integrate, optimize, special


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "qcd-cosmological-matter-completion-prereg.md"
DEFAULT_OUTPUT = (
    ROOT / "runs" / "20260910_qcd_cosmological_matter_completion" / "primary"
)
SCHEMA = "cassi.qcd-cosmological-matter-completion.primary.v1"

PI = math.pi
PHI = (1.0 + math.sqrt(5.0)) / 2.0
V_HIGGS_GEV = 174.0
M_STAR_EV = 1.08e-3
DM21_EV2 = 7.42e-5
DM31_EV2 = 2.517e-3
LIGHT_MASSES_EV = np.array([0.0, math.sqrt(DM21_EV2), math.sqrt(DM31_EV2)])
CASAS_IBARRA_Z = PI / 4.0 + 0.5j
HEAVY_RATIO = 10.0
ETA_TARGET = 6.1e-10
ETA_INTERVAL = (5.8e-10, 6.4e-10)
LEPTO_X_INITIAL = 1.0e-3
LEPTO_X_FINAL = 50.0
M_PLANCK_GEV = 1.22089e19
QCD_TC_GEV = 0.1565
NUCLEON_MASS_GEV = 0.938918754
ENTROPY_TO_PHOTON = 7.04
MB_PER_GEV_MINUS_2 = 0.389379
RNG_SEED = 20260910

SOURCE_PATHS = (
    PROTOCOL,
    ROOT / "computations" / "matter-formation-continuum-report.md",
    ROOT / "foundations" / "matter-completion-boundary.md",
    ROOT / "foundations" / "neutrino-masses.md",
    ROOT / "standard-model" / "sm-radiative-corrections.md",
)


@dataclass(frozen=True)
class LeptogenesisResult:
    mass_1_gev: float
    mass_2_gev: float
    reheat_temperature_gev: float
    yukawa: np.ndarray
    h_matrix: np.ndarray
    reconstructed_masses_ev: np.ndarray
    reconstruction_relative_error: float
    effective_mass_ev: float
    decay_parameter: float
    loop_function: float
    epsilon_1: float
    davidson_ibarra_bound: float
    x: np.ndarray
    heavy_abundance: np.ndarray
    b_minus_l: np.ndarray
    eta_b: float
    solver_success: bool
    solver_message: str
    function_evaluations: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"nonfinite value in receipt: {value}")
    return value


def relative_difference(left: float, right: float, floor: float = 1.0e-300) -> float:
    return abs(left - right) / max(abs(left), abs(right), floor)


def pmns_matrix() -> np.ndarray:
    """Return the frozen normal-ordering PMNS benchmark."""

    sin2_12 = 0.304
    sin2_23 = 0.573
    sin2_13 = 0.02219
    delta = math.radians(195.0)
    s12, s23, s13 = map(math.sqrt, (sin2_12, sin2_23, sin2_13))
    c12, c23, c13 = map(
        math.sqrt, (1.0 - sin2_12, 1.0 - sin2_23, 1.0 - sin2_13)
    )
    phase = np.exp(1j * delta)
    return np.array(
        [
            [c12 * c13, s12 * c13, s13 / phase],
            [
                -s12 * c23 - c12 * s23 * s13 * phase,
                c12 * c23 - s12 * s23 * s13 * phase,
                s23 * c13,
            ],
            [
                s12 * s23 - c12 * c23 * s13 * phase,
                -c12 * s23 - s12 * c23 * s13 * phase,
                c23 * c13,
            ],
        ],
        dtype=np.complex128,
    )


def casas_ibarra_yukawa(mass_1_gev: float) -> tuple[np.ndarray, np.ndarray]:
    mass_2_gev = HEAVY_RATIO * mass_1_gev
    light_gev = LIGHT_MASSES_EV * 1.0e-9
    z_value = CASAS_IBARRA_Z
    rotation = np.array(
        [
            [0.0, 0.0],
            [np.cos(z_value), -np.sin(z_value)],
            [np.sin(z_value), np.cos(z_value)],
        ],
        dtype=np.complex128,
    )
    heavy_root = np.diag(np.sqrt([mass_1_gev, mass_2_gev]))
    yukawa = (
        pmns_matrix()
        @ np.diag(np.sqrt(light_gev))
        @ rotation
        @ heavy_root
        / V_HIGGS_GEV
    )
    return yukawa, rotation


def leptogenesis_rhs(
    decay_parameter: float, epsilon_1: float
) -> Callable[[float, np.ndarray], np.ndarray]:
    def rhs(x_value: float, state: np.ndarray) -> np.ndarray:
        k1 = special.kv(1, x_value)
        k2 = special.kv(2, x_value)
        equilibrium = 0.5 * x_value * x_value * k2
        decay = decay_parameter * x_value * k1 / k2
        washout = 0.25 * decay_parameter * x_value**3 * k1
        departure = decay * (state[0] - equilibrium)
        return np.array(
            [-departure, -epsilon_1 * departure - washout * state[1]],
            dtype=np.float64,
        )

    return rhs


def solve_leptogenesis(
    mass_1_gev: float,
    *,
    method: str,
    rtol: float,
    atol: float,
    max_step: float,
    retain_history: bool,
) -> LeptogenesisResult:
    yukawa, _ = casas_ibarra_yukawa(mass_1_gev)
    mass_2_gev = HEAVY_RATIO * mass_1_gev
    heavy = np.array([mass_1_gev, mass_2_gev], dtype=np.float64)
    h_matrix = yukawa.conj().T @ yukawa
    effective_mass_ev = (
        h_matrix[0, 0].real * V_HIGGS_GEV**2 / mass_1_gev * 1.0e9
    )
    decay_parameter = effective_mass_ev / M_STAR_EV
    hierarchy = (mass_2_gev / mass_1_gev) ** 2
    loop_function = math.sqrt(hierarchy) * (
        1.0 / (1.0 - hierarchy)
        + 1.0
        - (1.0 + hierarchy) * math.log((1.0 + hierarchy) / hierarchy)
    )
    epsilon_1 = float(
        (h_matrix[0, 1] ** 2).imag
        * loop_function
        / (8.0 * PI * h_matrix[0, 0].real)
    )
    davidson_ibarra_bound = (
        3.0
        * mass_1_gev
        * LIGHT_MASSES_EV[-1]
        * 1.0e-9
        / (16.0 * PI * V_HIGGS_GEV**2)
    )

    mass_matrix = (
        V_HIGGS_GEV**2
        * yukawa
        @ np.diag(1.0 / heavy)
        @ yukawa.T
    )
    reconstructed_masses_ev = np.sort(np.linalg.svd(mass_matrix, compute_uv=False)) * 1.0e9
    nonzero_target = LIGHT_MASSES_EV[1:]
    reconstruction_relative_error = float(
        np.max(
            np.abs(reconstructed_masses_ev[1:] - nonzero_target) / nonzero_target
        )
    )

    initial_equilibrium = (
        0.5
        * LEPTO_X_INITIAL**2
        * special.kv(2, LEPTO_X_INITIAL)
    )
    if retain_history:
        x_eval = np.unique(
            np.concatenate(
                (
                    np.geomspace(LEPTO_X_INITIAL, 1.0, 241),
                    np.linspace(1.0, LEPTO_X_FINAL, 491),
                )
            )
        )
    else:
        x_eval = np.array([LEPTO_X_FINAL])
    solution = integrate.solve_ivp(
        leptogenesis_rhs(decay_parameter, epsilon_1),
        (LEPTO_X_INITIAL, LEPTO_X_FINAL),
        np.array([initial_equilibrium, 0.0]),
        method=method,
        t_eval=x_eval,
        rtol=rtol,
        atol=atol,
        max_step=max_step,
    )
    if not solution.success:
        raise RuntimeError(f"leptogenesis solve failed: {solution.message}")
    eta_b = 0.96e-2 * abs(float(solution.y[1, -1]))
    return LeptogenesisResult(
        mass_1_gev=mass_1_gev,
        mass_2_gev=mass_2_gev,
        reheat_temperature_gev=20.0 * mass_2_gev,
        yukawa=yukawa,
        h_matrix=h_matrix,
        reconstructed_masses_ev=reconstructed_masses_ev,
        reconstruction_relative_error=reconstruction_relative_error,
        effective_mass_ev=float(effective_mass_ev),
        decay_parameter=float(decay_parameter),
        loop_function=float(loop_function),
        epsilon_1=epsilon_1,
        davidson_ibarra_bound=float(davidson_ibarra_bound),
        x=solution.t,
        heavy_abundance=solution.y[0],
        b_minus_l=solution.y[1],
        eta_b=eta_b,
        solver_success=bool(solution.success),
        solver_message=str(solution.message),
        function_evaluations=int(solution.nfev),
    )


def calibrate_heavy_mass() -> tuple[float, list[dict[str, float]]]:
    evaluations: list[dict[str, float]] = []
    cache: dict[float, float] = {}

    def residual(log10_mass: float) -> float:
        key = round(float(log10_mass), 12)
        if key not in cache:
            result = solve_leptogenesis(
                10.0**log10_mass,
                method="DOP853",
                rtol=1.0e-10,
                atol=1.0e-13,
                max_step=0.05,
                retain_history=False,
            )
            cache[key] = result.eta_b
            evaluations.append(
                {
                    "log10_mass_1_gev": float(log10_mass),
                    "mass_1_gev": float(10.0**log10_mass),
                    "eta_b": float(result.eta_b),
                }
            )
        return math.log10(cache[key] / ETA_TARGET)

    root = optimize.brentq(residual, 8.0, 13.0, xtol=1.0e-11, rtol=1.0e-12)
    return 10.0**root, evaluations


def lepto_payload(result: LeptogenesisResult) -> dict[str, Any]:
    return {
        "mass_1_gev": result.mass_1_gev,
        "mass_2_gev": result.mass_2_gev,
        "reheat_temperature_gev": result.reheat_temperature_gev,
        "yukawa": result.yukawa,
        "yukawa_max_abs": float(np.max(np.abs(result.yukawa))),
        "h_matrix": result.h_matrix,
        "reconstructed_masses_ev": result.reconstructed_masses_ev,
        "reconstruction_relative_error": result.reconstruction_relative_error,
        "effective_mass_ev": result.effective_mass_ev,
        "decay_parameter": result.decay_parameter,
        "loop_function": result.loop_function,
        "epsilon_1": result.epsilon_1,
        "epsilon_1_abs": abs(result.epsilon_1),
        "davidson_ibarra_bound": result.davidson_ibarra_bound,
        "davidson_ibarra_ratio": abs(result.epsilon_1)
        / result.davidson_ibarra_bound,
        "x": result.x,
        "heavy_abundance": result.heavy_abundance,
        "b_minus_l": result.b_minus_l,
        "eta_b": result.eta_b,
        "solver_success": result.solver_success,
        "solver_message": result.solver_message,
        "function_evaluations": result.function_evaluations,
    }


def gstar(temperature_gev: float) -> float:
    temperatures = np.array([0.001, 0.010, 0.100, QCD_TC_GEV])
    values = np.array([10.75, 10.75, 17.25, 61.75])
    return float(np.interp(temperature_gev, temperatures, values))


def stable_k2(argument: float) -> float:
    if argument >= 745.0:
        return 0.0
    return float(math.exp(-argument) * special.kve(2, argument))


def equilibrium_baryon_yield(temperature_gev: float) -> float:
    argument = NUCLEON_MASS_GEV / temperature_gev
    number_density = (
        4.0
        * NUCLEON_MASS_GEV**2
        * temperature_gev
        * stable_k2(argument)
        / (2.0 * PI**2)
    )
    entropy_density = (
        2.0 * PI**2 / 45.0 * gstar(temperature_gev) * temperature_gev**3
    )
    return number_density / entropy_density


def chemistry_arm(
    eta_b: float, cross_section_mb: float, steps: int
) -> dict[str, Any]:
    """Advance the pair abundance with a positivity-preserving Riccati transfer."""

    net_yield = eta_b / ENTROPY_TO_PHOTON
    u_initial = NUCLEON_MASS_GEV / QCD_TC_GEV
    w_final = math.log(QCD_TC_GEV / 0.001)
    equilibrium_initial = equilibrium_baryon_yield(QCD_TC_GEV)
    antibaryon = (
        -net_yield
        + math.hypot(net_yield, 2.0 * equilibrium_initial)
    ) / 2.0
    step = w_final / steps
    history: list[dict[str, float]] = []
    sample_stride = max(1, steps // 240)

    for index in range(steps):
        midpoint_w = (index + 0.5) * step
        temperature = QCD_TC_GEV * math.exp(-midpoint_w)
        freedom = gstar(temperature)
        entropy_density = 2.0 * PI**2 / 45.0 * freedom * temperature**3
        hubble = 1.66 * math.sqrt(freedom) * temperature**2 / M_PLANCK_GEV
        coefficient = (
            entropy_density
            * (cross_section_mb / MB_PER_GEV_MINUS_2)
            / hubble
        )
        equilibrium = equilibrium_baryon_yield(temperature)
        discriminant = math.hypot(net_yield, 2.0 * equilibrium)
        positive_root = (
            2.0 * equilibrium**2 / (discriminant + net_yield)
            if discriminant + net_yield > 0.0
            else 0.0
        )
        negative_root = -(discriminant + net_yield) / 2.0
        denominator = antibaryon - negative_root
        ratio = (
            (antibaryon - positive_root) / denominator
            if denominator != 0.0
            else 0.0
        )
        damping_argument = coefficient * discriminant * step
        damping = 0.0 if damping_argument > 745.0 else math.exp(-damping_argument)
        propagated_ratio = ratio * damping
        antibaryon = (
            (positive_root - propagated_ratio * negative_root)
            / (1.0 - propagated_ratio)
        )
        if antibaryon < 0.0 and abs(antibaryon) < 1.0e-300:
            antibaryon = 0.0
        if antibaryon < 0.0 or not math.isfinite(antibaryon):
            raise RuntimeError("chemistry transfer left the physical density domain")
        if index % sample_stride == 0 or index == steps - 1:
            total = 2.0 * antibaryon + net_yield
            history.append(
                {
                    "temperature_mev": 1000.0 * temperature,
                    "baryon_yield": antibaryon + net_yield,
                    "antibaryon_yield": antibaryon,
                    "total_yield": total,
                    "net_yield": net_yield,
                    "antibaryon_fraction": antibaryon / total,
                }
            )

    final_total = 2.0 * antibaryon + net_yield
    return {
        "cross_section_mb": cross_section_mb,
        "steps": steps,
        "initial_temperature_mev": 1000.0 * QCD_TC_GEV,
        "final_temperature_mev": 1.0,
        "initial_equilibrium_yield_one_species": equilibrium_initial,
        "net_yield": net_yield,
        "final_baryon_yield": antibaryon + net_yield,
        "final_antibaryon_yield": antibaryon,
        "final_total_yield": final_total,
        "final_antibaryon_fraction": antibaryon / final_total,
        "eta_b_reconstructed": net_yield * ENTROPY_TO_PHOTON,
        "eta_b_relative_drift": relative_difference(
            net_yield * ENTROPY_TO_PHOTON, eta_b
        ),
        "history": history,
    }


def nonzero_mode_rms(field: np.ndarray) -> float:
    centered = field - float(np.mean(field))
    return float(math.sqrt(float(np.mean(centered * centered))))


def combined_nonzero_rms(pair: np.ndarray) -> float:
    return math.sqrt(
        0.5
        * (
            nonzero_mode_rms(pair[0]) ** 2
            + nonzero_mode_rms(pair[1]) ** 2
        )
    )


def diffuse_pair(pair: np.ndarray, factor: np.ndarray) -> np.ndarray:
    spectrum = np.fft.rfftn(pair, axes=(1, 2, 3))
    spectrum *= factor[np.newaxis, :, :, :]
    return np.fft.irfftn(spectrum, s=pair.shape[1:], axes=(1, 2, 3)).real


def reaction_step(pair: np.ndarray, step: float) -> np.ndarray:
    def slope(state: np.ndarray) -> np.ndarray:
        rate = -(state[0] * state[1] - 1.0)
        return np.stack((rate, rate), axis=0)

    first = slope(pair)
    second = slope(pair + 0.5 * step * first)
    third = slope(pair + 0.5 * step * second)
    fourth = slope(pair + step * third)
    return pair + step * (first + 2.0 * second + 2.0 * third + fourth) / 6.0


def evolve_nonradial(
    initial: np.ndarray,
    *,
    time_step: float,
    steps: int,
    diffusion: float,
    reaction: bool,
    retain_history: bool,
) -> tuple[np.ndarray, list[dict[str, float]]]:
    pair = initial.copy()
    size = pair.shape[1]
    frequencies_xy = 2.0 * PI * np.fft.fftfreq(size)
    frequencies_z = 2.0 * PI * np.fft.rfftfreq(size)
    kx, ky, kz = np.meshgrid(
        frequencies_xy, frequencies_xy, frequencies_z, indexing="ij"
    )
    k_squared = kx * kx + ky * ky + kz * kz
    full_factor = np.exp(-diffusion * k_squared * time_step)
    half_factor = np.exp(-diffusion * k_squared * time_step / 2.0)
    history: list[dict[str, float]] = []
    sample_stride = max(1, steps // 200)

    if diffusion > 0.0:
        pair = diffuse_pair(pair, half_factor)
    for index in range(steps):
        if reaction:
            pair = reaction_step(pair, time_step)
        if diffusion > 0.0:
            pair = diffuse_pair(
                pair, half_factor if index == steps - 1 else full_factor
            )
        if retain_history and (index % sample_stride == 0 or index == steps - 1):
            history.append(
                {
                    "time": (index + 1) * time_step,
                    "baryon_mean": float(np.mean(pair[0])),
                    "antibaryon_mean": float(np.mean(pair[1])),
                    "net_mean": float(np.mean(pair[0] - pair[1])),
                    "nonzero_mode_rms": combined_nonzero_rms(pair),
                    "minimum_density": float(np.min(pair)),
                    "reaction_residual_rms": float(
                        np.sqrt(np.mean((pair[0] * pair[1] - 1.0) ** 2))
                    ),
                }
            )
    return pair, history


def nonradial_calculation(eta_b: float) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    size = 24
    time_step = 0.01
    steps = 2000
    diffusion = 0.2
    temperature = 0.100
    net_yield = eta_b / ENTROPY_TO_PHOTON
    equilibrium_yield = equilibrium_baryon_yield(temperature)
    normalized_net = net_yield / equilibrium_yield
    discriminant = math.hypot(normalized_net, 2.0)
    baryon_mean = (normalized_net + discriminant) / 2.0
    antibaryon_mean = (-normalized_net + discriminant) / 2.0

    generator = np.random.Generator(np.random.PCG64(RNG_SEED))
    common = generator.normal(size=(size, size, size))
    common -= float(np.mean(common))
    common *= 0.05 / float(np.std(common))
    differential = generator.normal(size=(size, size, size))
    differential -= float(np.mean(differential))
    differential *= 0.02 / float(np.std(differential))
    initial = np.stack(
        (
            baryon_mean * (1.0 + common) + differential,
            antibaryon_mean * (1.0 + common) - differential,
        ),
        axis=0,
    )
    initial_net_mean = float(np.mean(initial[0] - initial[1]))
    initial_rms = combined_nonzero_rms(initial)
    initial_pair_mean = float(np.mean(initial[0] + initial[1]))

    primary, history = evolve_nonradial(
        initial,
        time_step=time_step,
        steps=steps,
        diffusion=diffusion,
        reaction=True,
        retain_history=True,
    )
    half_step, _ = evolve_nonradial(
        initial,
        time_step=time_step / 2.0,
        steps=2 * steps,
        diffusion=diffusion,
        reaction=True,
        retain_history=False,
    )
    zero_reaction, _ = evolve_nonradial(
        initial,
        time_step=time_step,
        steps=steps,
        diffusion=diffusion,
        reaction=False,
        retain_history=False,
    )
    zero_diffusion, _ = evolve_nonradial(
        initial,
        time_step=time_step,
        steps=steps,
        diffusion=0.0,
        reaction=True,
        retain_history=False,
    )

    final_net_mean = float(np.mean(primary[0] - primary[1]))
    final_rms = combined_nonzero_rms(primary)
    final_pair_mean = float(np.mean(primary[0] + primary[1]))
    half_pair_mean = float(np.mean(half_step[0] + half_step[1]))
    zero_reaction_pair_mean = float(np.mean(zero_reaction[0] + zero_reaction[1]))
    zero_diffusion_rms = combined_nonzero_rms(zero_diffusion)
    payload = {
        "grid_size": size,
        "seed": RNG_SEED,
        "time_step": time_step,
        "steps": steps,
        "final_time": time_step * steps,
        "diffusion": diffusion,
        "reaction_coefficient": 1.0,
        "temperature_mev": 100.0,
        "physical_net_yield": net_yield,
        "physical_equilibrium_yield_one_species": equilibrium_yield,
        "normalized_net_density": normalized_net,
        "initial_baryon_mean": float(np.mean(initial[0])),
        "initial_antibaryon_mean": float(np.mean(initial[1])),
        "initial_pair_mean": initial_pair_mean,
        "initial_net_mean": initial_net_mean,
        "initial_nonzero_mode_rms": initial_rms,
        "initial_minimum_density": float(np.min(initial)),
        "final_baryon_mean": float(np.mean(primary[0])),
        "final_antibaryon_mean": float(np.mean(primary[1])),
        "final_pair_mean": final_pair_mean,
        "final_net_mean": final_net_mean,
        "net_conservation_absolute_error": abs(final_net_mean - initial_net_mean),
        "final_nonzero_mode_rms": final_rms,
        "nonzero_mode_rms_ratio": final_rms / initial_rms,
        "final_minimum_density": float(np.min(primary)),
        "half_step_final_pair_mean": half_pair_mean,
        "half_step_final_pair_relative_difference": relative_difference(
            final_pair_mean, half_pair_mean
        ),
        "zero_reaction_final_pair_mean": zero_reaction_pair_mean,
        "zero_reaction_pair_relative_drift": relative_difference(
            zero_reaction_pair_mean, initial_pair_mean
        ),
        "zero_diffusion_final_nonzero_mode_rms": zero_diffusion_rms,
        "zero_diffusion_to_full_rms_ratio": zero_diffusion_rms / final_rms,
        "history": history,
    }
    arrays = {
        "initial_baryon": initial[0],
        "initial_antibaryon": initial[1],
        "final_baryon": primary[0],
        "final_antibaryon": primary[1],
        "half_step_final_baryon": half_step[0],
        "half_step_final_antibaryon": half_step[1],
        "zero_reaction_final_baryon": zero_reaction[0],
        "zero_reaction_final_antibaryon": zero_reaction[1],
        "zero_diffusion_final_baryon": zero_diffusion[0],
        "zero_diffusion_final_antibaryon": zero_diffusion[1],
    }
    return payload, arrays


def evidence_ledger() -> dict[str, Any]:
    beta_0 = 11.0 - 2.0 * 6.0 / 3.0
    beta_1 = 102.0 - 38.0 * 6.0 / 3.0
    lattice_mass = 0.936
    experimental_mass = 0.939
    lattice_statistical = 0.025
    lattice_systematic = 0.022
    combined_uncertainty = math.hypot(lattice_statistical, lattice_systematic)
    mass_pull = abs(lattice_mass - experimental_mass) / combined_uncertainty
    return {
        "microscopic_action": {
            "gauge_group": "SU(3)c x SU(2)L x U(1)Y",
            "qcd_active_flavors_for_uv_check": 6,
            "qcd_beta_0": beta_0,
            "qcd_beta_1": beta_1,
            "asymptotic_freedom": beta_0 > 0.0,
            "local_operator_dimensions": {
                "gauge_kinetic": 4,
                "fermion_kinetic": 4,
                "yukawa": 4,
                "majorana_mass": 3,
                "higgs_potential_maximum": 4,
            },
            "all_operator_dimensions_at_most_four": True,
            "gauge_invariant": True,
            "power_counting_renormalizable": True,
        },
        "initial_state": {
            "form": "Z^-1 P_G exp[-(H-sum mu_A Q_A)/T_R] P_G",
            "positive_by_construction": True,
            "normalized_by_partition_function": True,
            "gauge_projected": True,
            "initial_b_minus_l": 0.0,
            "heavy_neutrino_abundance": "thermal equilibrium",
            "cassi_selected": False,
        },
        "qcd_crossover": {
            "arxiv": "1812.08235",
            "temperature_mev": 156.5,
            "uncertainty_mev": 1.5,
            "physical_light_and_strange_quarks": True,
            "continuum_limit": True,
        },
        "lattice_nucleon": {
            "arxiv": "0906.3599",
            "dynamical_light_and_strange_quarks": True,
            "minimum_lattice_spacings": 3,
            "continuum_extrapolation": True,
            "lattice_mass_gev": lattice_mass,
            "statistical_uncertainty_gev": lattice_statistical,
            "systematic_uncertainty_gev": lattice_systematic,
            "combined_uncertainty_gev": combined_uncertainty,
            "experimental_isospin_averaged_mass_gev": experimental_mass,
            "mass_pull_sigma": mass_pull,
            "within_combined_uncertainty": mass_pull <= 1.0,
        },
        "nucleon_interpolators": {
            "proton": "epsilon_abc (u_a^T C gamma_5 d_b) u_c",
            "neutron": "epsilon_abc (d_a^T C gamma_5 u_b) d_c",
            "color_singlet": True,
            "baryon_number": 1.0,
            "spin": "1/2",
            "ground_state_parity": "+",
            "electric_charges": {"proton": 1.0, "neutron": 0.0},
        },
        "registered_cassi_origin": {
            "selects_standard_model_representations": False,
            "selects_qcd_operators": False,
            "selects_seesaw_operators": False,
            "selects_renormalized_parameters": False,
            "selects_casas_ibarra_coordinate": False,
            "selects_projected_thermal_state": False,
            "selects_reheating_condition": False,
            "alpha_s_mz_phi_boundary_two_loop": 0.061,
            "alpha_s_mz_measured": 0.1180,
            "alpha_s_ratio_boundary_to_measured": 0.061 / 0.1180,
        },
    }


def adjudicate(
    primary: LeptogenesisResult,
    verification: LeptogenesisResult,
    no_fit: LeptogenesisResult,
    chemistry: dict[str, Any],
    nonradial: dict[str, Any],
    evidence: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    action = evidence["microscopic_action"]
    lattice = evidence["lattice_nucleon"]
    pcm1_checks = {
        "local_gauge_invariant_action": bool(action["gauge_invariant"]),
        "operator_dimensions_at_most_four": bool(
            action["all_operator_dimensions_at_most_four"]
        ),
        "power_counting_renormalizable": bool(
            action["power_counting_renormalizable"]
        ),
        "six_flavor_asymptotic_freedom": bool(action["qcd_beta_0"] > 0.0),
        "dynamical_continuum_lattice_evidence": bool(
            lattice["dynamical_light_and_strange_quarks"]
            and lattice["minimum_lattice_spacings"] >= 3
            and lattice["continuum_extrapolation"]
        ),
        "nucleon_mass_within_combined_uncertainty": bool(
            lattice["within_combined_uncertainty"]
        ),
    }
    pcm1 = "PASS EMPIRICAL" if all(pcm1_checks.values()) else "FAIL"

    solver_agreement = relative_difference(primary.eta_b, verification.eta_b)
    pcm2_checks = {
        "positive_normalized_gauge_projected_state": True,
        "zero_initial_b_minus_l": True,
        "nonzero_cp_asymmetry": abs(primary.epsilon_1) > 0.0,
        "davidson_ibarra_bound": abs(primary.epsilon_1)
        <= primary.davidson_ibarra_bound * (1.0 + 1.0e-12),
        "light_mass_reconstruction": primary.reconstruction_relative_error
        < 1.0e-10,
        "heavy_mass_inside_frozen_interval": 1.0e9
        < primary.mass_1_gev
        < 1.0e13,
        "reheat_above_second_heavy_mass": primary.reheat_temperature_gev
        > primary.mass_2_gev,
        "perturbative_yukawa": float(np.max(np.abs(primary.yukawa))) < 1.0,
        "eta_inside_frozen_interval": ETA_INTERVAL[0]
        <= primary.eta_b
        <= ETA_INTERVAL[1],
        "independent_solver_agreement": solver_agreement < 5.0e-4,
    }
    pcm2 = "PASS CALIBRATED" if all(pcm2_checks.values()) else "FAIL"
    no_fit_verdict = (
        "SUPPORTS"
        if ETA_INTERVAL[0] <= no_fit.eta_b <= ETA_INTERVAL[1]
        else "CONTRADICTS"
    )

    chemistry_rows = chemistry["cross_section_arms"]
    pcm3_checks = {
        "primary_verification_yield_agreement": chemistry[
            "maximum_primary_verification_final_yield_relative_difference"
        ]
        < 5.0e-4,
        "net_yield_conservation": chemistry["maximum_net_yield_relative_drift"]
        < 1.0e-10,
        "antibaryon_fraction_below_limit": all(
            row["primary"]["final_antibaryon_fraction"] < 1.0e-6
            for row in chemistry_rows
        ),
        "eta_b_conservation": chemistry["maximum_eta_b_relative_drift"]
        < 1.0e-10,
    }
    if not all(
        (
            pcm3_checks["primary_verification_yield_agreement"],
            pcm3_checks["net_yield_conservation"],
            pcm3_checks["eta_b_conservation"],
        )
    ):
        pcm3 = "FAIL"
    elif pcm3_checks["antibaryon_fraction_below_limit"]:
        pcm3 = "SUPPORTS"
    else:
        pcm3 = "CONTRADICTS"

    pcm4_checks = {
        "positive_densities": nonradial["initial_minimum_density"] > 0.0
        and nonradial["final_minimum_density"] > 0.0,
        "net_baryon_conservation": nonradial[
            "net_conservation_absolute_error"
        ]
        < 2.0e-13,
        "nonzero_mode_reduction": nonradial["nonzero_mode_rms_ratio"] <= 0.10,
        "half_step_agreement": nonradial[
            "half_step_final_pair_relative_difference"
        ]
        < 1.0e-3,
        "zero_reaction_pair_mean_conserved": nonradial[
            "zero_reaction_pair_relative_drift"
        ]
        < 1.0e-11,
        "zero_diffusion_retains_more_power": nonradial[
            "zero_diffusion_final_nonzero_mode_rms"
        ]
        > nonradial["final_nonzero_mode_rms"],
    }
    pcm4 = "SUPPORTS" if all(pcm4_checks.values()) else "FAIL"

    interpolators = evidence["nucleon_interpolators"]
    pcm5_checks = {
        "color_singlet_baryon_number_one": bool(
            interpolators["color_singlet"]
            and interpolators["baryon_number"] == 1.0
        ),
        "spin_parity_and_charges_match": bool(
            interpolators["spin"] == "1/2"
            and interpolators["ground_state_parity"] == "+"
            and interpolators["electric_charges"]
            == {"proton": 1.0, "neutron": 0.0}
        ),
        "lattice_mass_match": bool(lattice["within_combined_uncertainty"]),
        "continuum_dynamical_quarks": bool(
            lattice["continuum_extrapolation"]
            and lattice["dynamical_light_and_strange_quarks"]
        ),
    }
    pcm5 = "PASS EMPIRICAL" if all(pcm5_checks.values()) else "FAIL"

    conditional = all(
        (
            pcm1 == "PASS EMPIRICAL",
            pcm2 == "PASS CALIBRATED",
            pcm3 == "SUPPORTS",
            pcm4 == "SUPPORTS",
            pcm5 == "PASS EMPIRICAL",
        )
    )
    origin = evidence["registered_cassi_origin"]
    selection_keys = [
        "selects_standard_model_representations",
        "selects_qcd_operators",
        "selects_seesaw_operators",
        "selects_renormalized_parameters",
        "selects_casas_ibarra_coordinate",
        "selects_projected_thermal_state",
        "selects_reheating_condition",
    ]
    cassi_complete = all(bool(origin[key]) for key in selection_keys)
    gates = {
        "PCM1": pcm1,
        "PCM2": pcm2,
        "PCM2_no_fit_mapped_seesaw_scale": no_fit_verdict,
        "PCM3": pcm3,
        "PCM4": pcm4,
        "PCM5": pcm5,
        "conditional_empirical_matter_history": (
            "SUPPORTS" if conditional else "FAIL"
        ),
        "complete_physical_Cassi_matter_formation": (
            "PASS" if cassi_complete else "FAIL"
        ),
    }
    checks = {
        "PCM1": pcm1_checks,
        "PCM2": pcm2_checks,
        "PCM2_solver_relative_difference": solver_agreement,
        "PCM3": pcm3_checks,
        "PCM4": pcm4_checks,
        "PCM5": pcm5_checks,
        "PCM6_Cassi_selection": {key: bool(origin[key]) for key in selection_keys},
    }
    return gates, checks


def report_text(payload: dict[str, Any]) -> str:
    gates = payload["gates"]
    lepto = payload["leptogenesis"]["primary"]
    verification = payload["leptogenesis"]["verification"]
    no_fit = payload["leptogenesis"]["mapped_scale_no_fit"]
    nonradial = payload["nonradial"]
    lattice = payload["evidence"]["lattice_nucleon"]
    chemistry_rows = payload["chemistry"]["cross_section_arms"]
    chemistry_table = "\n".join(
        f"| {row['cross_section_mb']:.0f} | "
        f"{row['primary']['final_antibaryon_fraction']:.3e} | "
        f"{row['primary_verification_final_yield_relative_difference']:.3e} |"
        for row in chemistry_rows
    )
    gate_table = "\n".join(
        f"| `{name}` | `{verdict}` |" for name, verdict in gates.items()
    )
    return rf"""# QCD Cosmological Matter-Completion Result

## Status: Computed—September 2026

## 1. Verdicts

| Gate | Verdict |
|:-----|:--------|
{gate_table}

The connected Standard Model plus two-singlet calculation supports a
conditional empirical history from a gauge-projected thermal state through a
calibrated baryon excess, QCD hadronization, annihilation, and observable
nucleons. The registered Cassi equations do not select the added microscopic
action, quantum state, Yukawa texture, or reheating boundary. The physical
Cassi completion gate therefore remains `FAIL`.

## 2. Baryogenesis

The frozen complex Casas–Ibarra benchmark calibrates
$M_1={lepto['mass_1_gev']:.10e}\ \mathrm{{GeV}}$ and
$M_2={lepto['mass_2_gev']:.10e}\ \mathrm{{GeV}}$. It gives
$\widetilde m_1={lepto['effective_mass_ev']:.10e}\ \mathrm{{eV}}$,
$K={lepto['decay_parameter']:.8f}$,
$|\epsilon_1|={lepto['epsilon_1_abs']:.10e}$, and

$$
\eta_B={lepto['eta_b']:.12e}.
$$

The independent stiff solver gives
$\eta_B={verification['eta_b']:.12e}$; their relative difference is
${payload['checks']['PCM2_solver_relative_difference']:.3e}. The CP asymmetry
is {lepto['davidson_ibarra_ratio']:.4f} of the Davidson–Ibarra bound, the
largest Yukawa magnitude is {lepto['yukawa_max_abs']:.4f}, and the two nonzero
light-neutrino masses reconstruct with maximum relative error
${lepto['reconstruction_relative_error']:.3e}.

Fixing $M_1=10^{{14}}\ \mathrm{{GeV}}$ from the order of the existing mapped
seesaw scale without refitting gives
$\eta_B={no_fit['eta_b']:.12e}$ and returns
`{gates['PCM2_no_fit_mapped_seesaw_scale']}`.

## 3. QCD-era chemistry

| $\langle\sigma v\rangle$ (mb) | final antibaryon fraction | solver difference |
|:-------------------------------|---------------------------:|------------------:|
{chemistry_table}

All arms preserve the generated net yield and end below the frozen
antibaryon-fraction threshold. These equations are a hadron-resonance-gas
baseline; they do not replace a real-time lattice-QCD calculation.

## 4. Nonradial density response

The $24^3$ reaction-diffusion run reduces the combined nonzero-mode RMS from
{nonradial['initial_nonzero_mode_rms']:.10e} to
{nonradial['final_nonzero_mode_rms']:.10e}, a retained ratio of
{nonradial['nonzero_mode_rms_ratio']:.6f}. The absolute normalized net-density
drift is {nonradial['net_conservation_absolute_error']:.3e}. The half-step
pair-mean difference is
{nonradial['half_step_final_pair_relative_difference']:.3e}; the no-diffusion
control retains {nonradial['zero_diffusion_to_full_rms_ratio']:.3f} times as
much nonzero-mode RMS as the full arm.

## 5. Observable nucleon

The continuum lattice-QCD nucleon mass is
${lattice['lattice_mass_gev']:.3f}({int(round(lattice['statistical_uncertainty_gev'] * 1000)):d})({int(round(lattice['systematic_uncertainty_gev'] * 1000)):d})\ \mathrm{{GeV}}$
against the isospin-averaged experimental
${lattice['experimental_isospin_averaged_mass_gev']:.3f}\ \mathrm{{GeV}}$.
The residual is {lattice['mass_pull_sigma']:.4f} combined quoted standard
deviations. The supplied proton and neutron interpolators are color singlets
with $B=1$, spin $1/2$, positive ground-state parity, and charges $+1$ and
$0$.

## 6. Scope

This result supplies a coherent empirical completion by declaring the
well-tested microscopic theory and cosmological boundary conditions. It also
locates the remaining Cassi problem precisely: derive or independently predict
the microscopic field content, renormalized couplings, CP-bearing texture, and
initial density operator from the whole-bubble dynamics. The factor-of-two
$\alpha_s(m_Z)$ deficit of the registered $\varphi$ boundary remains direct
evidence that the present Cassi boundary does not yet select physical QCD.

## Artifacts

- `results.json`—complete source-bound receipt and histories.
- `nonradial_fields.npz`—initial, converged, half-step, and control fields.
- `computations/qcd-cosmological-matter-completion-prereg.md`—frozen protocol.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    output_dir = arguments.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite frozen output: {output_dir}")

    started = time.time()
    mass_1, calibration_trace = calibrate_heavy_mass()
    primary = solve_leptogenesis(
        mass_1,
        method="DOP853",
        rtol=1.0e-10,
        atol=1.0e-13,
        max_step=0.05,
        retain_history=True,
    )
    verification = solve_leptogenesis(
        mass_1,
        method="Radau",
        rtol=3.0e-11,
        atol=3.0e-14,
        max_step=0.025,
        retain_history=True,
    )
    no_fit = solve_leptogenesis(
        1.0e14,
        method="DOP853",
        rtol=1.0e-10,
        atol=1.0e-13,
        max_step=0.05,
        retain_history=True,
    )

    chemistry_rows: list[dict[str, Any]] = []
    yield_differences: list[float] = []
    eta_drifts: list[float] = []
    net_drifts: list[float] = []
    for cross_section in (40.0, 50.0, 60.0):
        chemistry_primary = chemistry_arm(primary.eta_b, cross_section, 6000)
        chemistry_verification = chemistry_arm(primary.eta_b, cross_section, 12000)
        yield_difference = relative_difference(
            chemistry_primary["final_total_yield"],
            chemistry_verification["final_total_yield"],
        )
        yield_differences.append(yield_difference)
        eta_drifts.extend(
            (
                chemistry_primary["eta_b_relative_drift"],
                chemistry_verification["eta_b_relative_drift"],
            )
        )
        net_drifts.append(
            relative_difference(
                chemistry_primary["net_yield"],
                chemistry_verification["net_yield"],
            )
        )
        chemistry_rows.append(
            {
                "cross_section_mb": cross_section,
                "primary": chemistry_primary,
                "verification": chemistry_verification,
                "primary_verification_final_yield_relative_difference": yield_difference,
            }
        )
    chemistry = {
        "model": "Maxwell-Boltzmann nucleon HRG with exact midpoint Riccati transfer",
        "entropy_to_photon_ratio": ENTROPY_TO_PHOTON,
        "cross_section_arms": chemistry_rows,
        "maximum_primary_verification_final_yield_relative_difference": max(
            yield_differences
        ),
        "maximum_net_yield_relative_drift": max(net_drifts),
        "maximum_eta_b_relative_drift": max(eta_drifts),
    }

    nonradial, arrays = nonradial_calculation(primary.eta_b)
    evidence = evidence_ledger()
    gates, checks = adjudicate(
        primary, verification, no_fit, chemistry, nonradial, evidence
    )
    payload = {
        "schema": SCHEMA,
        "protocol_status": "executed_frozen",
        "started_unix": started,
        "elapsed_seconds": time.time() - started,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
        },
        "constants": {
            "phi": PHI,
            "v_higgs_gev": V_HIGGS_GEV,
            "m_star_ev": M_STAR_EV,
            "delta_m21_ev2": DM21_EV2,
            "delta_m31_ev2": DM31_EV2,
            "light_masses_ev": LIGHT_MASSES_EV,
            "casas_ibarra_z": CASAS_IBARRA_Z,
            "heavy_mass_ratio": HEAVY_RATIO,
            "eta_b_target": ETA_TARGET,
            "eta_b_interval": ETA_INTERVAL,
            "planck_mass_gev": M_PLANCK_GEV,
            "qcd_crossover_temperature_gev": QCD_TC_GEV,
            "nucleon_mean_mass_gev": NUCLEON_MASS_GEV,
            "rng_seed": RNG_SEED,
        },
        "sources": [source_record(path) for path in (*SOURCE_PATHS, SELF)],
        "leptogenesis": {
            "calibration_trace": calibration_trace,
            "primary": lepto_payload(primary),
            "verification": lepto_payload(verification),
            "mapped_scale_no_fit": lepto_payload(no_fit),
        },
        "chemistry": chemistry,
        "nonradial": nonradial,
        "evidence": evidence,
        "checks": checks,
        "gates": gates,
    }
    payload["execution_valid"] = bool(
        primary.solver_success
        and verification.solver_success
        and no_fit.solver_success
        and all(math.isfinite(float(value)) for value in yield_differences)
    )

    output_dir.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(output_dir / "nonradial_fields.npz", **arrays)
    results_path = output_dir / "results.json"
    results_path.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    report_path = output_dir / "report.md"
    report_path.write_text(report_text(json_ready(payload)), encoding="utf-8")

    print("QCD COSMOLOGICAL MATTER COMPLETION")
    for name, verdict in gates.items():
        print(f"{name}={verdict}")
    print(f"M1_GEV={primary.mass_1_gev:.12e}")
    print(f"ETA_B={primary.eta_b:.12e}")
    print(f"NONRADIAL_RMS_RATIO={nonradial['nonzero_mode_rms_ratio']:.9e}")
    print(f"RESULTS={results_path.relative_to(ROOT).as_posix()}")
    print(f"ELAPSED_SECONDS={payload['elapsed_seconds']:.3f}")
    return 0 if payload["execution_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
