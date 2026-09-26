#!/usr/bin/env python3
"""Reference kernels for conditional moving multigroup radiation transport.

Run from the CassiTheory root:
    python computations/moving_multigroup_radiation.py

The affine controls are dimensionless. They do not assign a material identity,
physical opacity, or temperature to the Cassi field.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class DopplerAdvance:
    energy: np.ndarray
    minimum_energy: float
    maximum_ledger_residual: float
    steps: int


def validate_frequency_edges(edges: np.ndarray | Iterable[float]) -> np.ndarray:
    values = np.asarray(edges, dtype=np.float64)
    if values.ndim != 1 or values.size < 2:
        raise ValueError("frequency edges must be a one-dimensional array with at least two entries")
    if np.any(~np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("frequency edges must be finite and nonnegative")
    if np.any(np.diff(values) <= 0.0):
        raise ValueError("frequency edges must be strictly increasing")
    return values


def validate_group_energy(energy: np.ndarray | Iterable[float], groups: int) -> np.ndarray:
    values = np.asarray(energy, dtype=np.float64)
    if values.shape != (groups,):
        raise ValueError("group energy shape does not match the frequency grid")
    if np.any(~np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("group energy must be finite and nonnegative")
    return values


def compact_spectrum(frequency: np.ndarray | float) -> np.ndarray | float:
    """Return nu^2 (1-nu)^2 on [0, 1], zero elsewhere."""
    values = np.asarray(frequency, dtype=np.float64)
    result = np.where(
        (values >= 0.0) & (values <= 1.0),
        values**2 * (1.0 - values) ** 2,
        0.0,
    )
    if result.ndim == 0:
        return float(result)
    return result


def compact_energy_primitive(frequency: np.ndarray | float) -> np.ndarray | float:
    """Integral of compact_spectrum from zero to frequency."""
    values = np.asarray(frequency, dtype=np.float64)
    clipped = np.clip(values, 0.0, 1.0)
    result = clipped**3 / 3.0 - clipped**4 / 2.0 + clipped**5 / 5.0
    if result.ndim == 0:
        return float(result)
    return result


def compact_photon_primitive(frequency: np.ndarray | float) -> np.ndarray | float:
    """Integral of compact_spectrum(nu)/nu from zero to frequency for h=1."""
    values = np.asarray(frequency, dtype=np.float64)
    clipped = np.clip(values, 0.0, 1.0)
    result = clipped**2 / 2.0 - 2.0 * clipped**3 / 3.0 + clipped**4 / 4.0
    if result.ndim == 0:
        return float(result)
    return result


def exact_extensive_group_energy(
    edges: np.ndarray | Iterable[float], scale_factor: float, *, initial_volume: float = 1.0
) -> np.ndarray:
    """Exact homogeneous-isotropic group energy U_g for E_nu=a^-3 E_0(a nu)."""
    grid = validate_frequency_edges(edges)
    scale = float(scale_factor)
    volume = float(initial_volume)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("scale factor must be finite and positive")
    if not math.isfinite(volume) or volume <= 0.0:
        raise ValueError("initial volume must be finite and positive")
    primitive = np.asarray(compact_energy_primitive(scale * grid), dtype=np.float64)
    return volume * np.diff(primitive) / scale


def exact_radiation_scalings(scale_factor: float) -> tuple[float, float]:
    """Return homogeneous radiation energy and photon-number densities for h=1."""
    scale = float(scale_factor)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("scale factor must be finite and positive")
    energy0 = float(compact_energy_primitive(1.0))
    photons0 = float(compact_photon_primitive(1.0))
    return energy0 / scale**4, photons0 / scale**3


def frequency_edge_four_flux(
    frequencies: np.ndarray | Iterable[float],
    third_moments: np.ndarray,
    velocity_gradient: np.ndarray,
) -> np.ndarray:
    """Return Phi^alpha=-nu M^{alpha beta gamma} grad_gamma(U_beta/c)."""
    edges = validate_frequency_edges(frequencies)
    moments = np.asarray(third_moments, dtype=np.float64)
    gradient = np.asarray(velocity_gradient, dtype=np.float64)
    if moments.shape != (edges.size, 4, 4, 4):
        raise ValueError("spectral third moments must have shape (edge, 4, 4, 4)")
    if gradient.shape != (4, 4):
        raise ValueError("four-velocity gradient must have shape (4, 4)")
    if np.any(~np.isfinite(moments)) or np.any(~np.isfinite(gradient)):
        raise ValueError("frequency-flux inputs must be finite")
    return -edges[:, None] * np.einsum("eabg,bg->ea", moments, gradient)


def group_frequency_rhs(edge_four_flux: np.ndarray) -> np.ndarray:
    """Return the frequency contribution -(Phi_hi-Phi_lo) for every group."""
    flux = np.asarray(edge_four_flux, dtype=np.float64)
    if flux.ndim != 2 or flux.shape[0] < 2 or flux.shape[1] != 4:
        raise ValueError("edge four-flux must have shape (groups + 1, 4)")
    if np.any(~np.isfinite(flux)):
        raise ValueError("edge four-flux must be finite")
    return -(flux[1:] - flux[:-1])


def validate_shared_interfaces(
    outgoing: np.ndarray, incoming: np.ndarray, *, tolerance: float = 0.0
) -> None:
    """Reject separately represented values that disagree at an internal edge."""
    left = np.asarray(outgoing, dtype=np.float64)
    right = np.asarray(incoming, dtype=np.float64)
    tol = float(tolerance)
    if left.shape != right.shape or left.ndim == 0:
        raise ValueError("interface representations must have equal non-scalar shapes")
    if np.any(~np.isfinite(left)) or np.any(~np.isfinite(right)):
        raise ValueError("interface representations must be finite")
    if not math.isfinite(tol) or tol < 0.0:
        raise ValueError("interface tolerance must be finite and nonnegative")
    if float(np.max(np.abs(left - right))) > tol:
        raise ValueError("internal frequency edge has inconsistent neighboring values")


def require_third_moment_closure(third_moments: np.ndarray | None) -> np.ndarray:
    if third_moments is None:
        raise ValueError("moving multigroup momentum transport requires a third-moment closure")
    values = np.asarray(third_moments, dtype=np.float64)
    if values.ndim < 3 or np.any(~np.isfinite(values)):
        raise ValueError("third-moment closure output is malformed")
    return values


def isotropic_edge_flux(energy: np.ndarray, edges: np.ndarray, hubble_rate: float) -> np.ndarray:
    """Piecewise-constant upwind extensive flux -H nu V E_nu at all edges."""
    grid = validate_frequency_edges(edges)
    groups = grid.size - 1
    state = validate_group_energy(energy, groups)
    rate = float(hubble_rate)
    if not math.isfinite(rate):
        raise ValueError("H must be finite")
    widths = np.diff(grid)
    spectral_extensive = state / widths
    flux = np.zeros(grid.size, dtype=np.float64)
    if rate > 0.0:
        # Frequency velocity -H nu is negative: the higher-frequency cell is upwind.
        flux[:-1] = -rate * grid[:-1] * spectral_extensive
    elif rate < 0.0:
        # Frequency velocity is positive: the lower-frequency cell is upwind.
        flux[1:] = -rate * grid[1:] * spectral_extensive
    return flux


def advance_isotropic_doppler(
    energy: np.ndarray | Iterable[float],
    edges: np.ndarray | Iterable[float],
    hubble_rate: float,
    duration: float,
    *,
    cfl: float = 0.4,
) -> DopplerAdvance:
    """Advance the frozen first-order isotropic frequency operator."""
    grid = validate_frequency_edges(edges)
    state = validate_group_energy(energy, grid.size - 1).copy()
    rate = float(hubble_rate)
    total_time = float(duration)
    courant = float(cfl)
    if not math.isfinite(rate):
        raise ValueError("H must be finite")
    if not math.isfinite(total_time) or total_time < 0.0:
        raise ValueError("duration must be finite and nonnegative")
    if not math.isfinite(courant) or not 0.0 < courant < 1.0:
        raise ValueError("CFL factor must lie strictly between zero and one")
    if total_time == 0.0 or rate == 0.0:
        return DopplerAdvance(state, float(np.min(state)), 0.0, 0)

    widths = np.diff(grid)
    spectral_rate = abs(rate) * float(np.max(grid[1:] / widths))
    step_limit = courant / spectral_rate
    steps = max(1, int(math.ceil(total_time / step_limit)))
    dt = total_time / steps
    minimum = float(np.min(state))
    maximum_ledger_residual = 0.0

    for _ in range(steps):
        edge_flux = isotropic_edge_flux(state, grid, rate)
        expected_sum = -dt * rate * float(np.sum(state)) - dt * (
            float(edge_flux[-1]) - float(edge_flux[0])
        )
        updated = state - dt * rate * state - dt * (edge_flux[1:] - edge_flux[:-1])
        ledger_residual = abs(float(np.sum(updated - state)) - expected_sum)
        maximum_ledger_residual = max(maximum_ledger_residual, ledger_residual)
        if np.min(updated) < -1.0e-14:
            raise ArithmeticError("frequency update left the nonnegative cone")
        state = np.maximum(updated, 0.0)
        minimum = min(minimum, float(np.min(state)))

    return DopplerAdvance(state, minimum, maximum_ledger_residual, steps)


def doppler_factor(beta: float, ray_cosine: float) -> float:
    speed = float(beta)
    cosine = float(ray_cosine)
    if not math.isfinite(speed) or abs(speed) >= 1.0:
        raise ValueError("beta must be finite with magnitude below one")
    if not math.isfinite(cosine) or not -1.0 <= cosine <= 1.0:
        raise ValueError("ray cosine must lie in [-1, 1]")
    gamma = 1.0 / math.sqrt(1.0 - speed**2)
    return 1.0 / (gamma * (1.0 - speed * cosine))


def observer_specific_intensity(frequency: float, beta: float, ray_cosine: float) -> float:
    nu = float(frequency)
    if not math.isfinite(nu) or nu < 0.0:
        raise ValueError("observer frequency must be finite and nonnegative")
    factor = doppler_factor(beta, ray_cosine)
    return factor**3 * float(compact_spectrum(nu / factor))


def observer_group_intensity(
    edges: np.ndarray | Iterable[float], beta: float, ray_cosine: float
) -> np.ndarray:
    """Exact group integral D^4 int I_0 dnu_0 over shifted material bounds."""
    grid = validate_frequency_edges(edges)
    factor = doppler_factor(beta, ray_cosine)
    primitive = np.asarray(compact_energy_primitive(grid / factor), dtype=np.float64)
    return factor**4 * np.diff(primitive)


def main() -> None:
    edges = np.linspace(0.0, 1.2, 65)
    initial = exact_extensive_group_energy(edges, 1.0)
    advanced = advance_isotropic_doppler(initial, edges, 0.2, 0.25)
    exact = exact_extensive_group_energy(edges, math.exp(0.2 * 0.25))
    report = {
        "dimensionless_control": True,
        "groups": initial.size,
        "steps": advanced.steps,
        "minimum_energy": advanced.minimum_energy,
        "l1_error": float(np.sum(np.abs(advanced.energy - exact))),
        "observer_group_sum": float(np.sum(observer_group_intensity(edges, 0.2, 0.8))),
    }
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
