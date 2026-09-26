"""Target-independent morphology coordinates for the next field-operator regime.

The coordinates are deterministic functions of one recorded particle snapshot.  They
carry no acceleration, future sample, trajectory analysis verdict, or persistent
adaptive state.  A future frozen operator executor can merge them into its alphabet
without changing a receipt-bound predecessor.
"""
from __future__ import annotations

import math
from typing import Mapping

import numpy as np
from scipy.spatial import cKDTree


MORPHOLOGY_ATOMS = (
    "morphology_compactness",
    "morphology_radial_spread",
    "morphology_anisotropy",
    "morphology_planarity",
    "morphology_shell_tangentiality",
    "morphology_counterflow",
)


class MorphologyObservableError(ValueError):
    """A snapshot cannot support deterministic morphology coordinates."""


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, fraction: float) -> float:
    order = np.argsort(values, kind="stable")
    ordered_values = values[order]
    cumulative = np.cumsum(weights[order])
    return float(np.interp(fraction * cumulative[-1], cumulative, ordered_values))


def morphology_atoms(
    position: np.ndarray,
    velocity: np.ndarray,
    mass: np.ndarray,
    *,
    neighbor_count: int = 16,
    minimum_radius: float = 1e-9,
) -> dict[str, np.ndarray]:
    """Return six finite per-particle morphology coordinates for one snapshot.

    ``position`` is measured from the simulation's declared centre.  Global
    coordinates are repeated per particle so the typed local grammar can combine
    them with local density, field-energy, and flow atoms without a side channel.
    """
    position = np.asarray(position, dtype=np.float64)
    velocity = np.asarray(velocity, dtype=np.float64)
    mass = np.asarray(mass, dtype=np.float64)
    if (
        position.ndim != 2
        or position.shape[1] != 3
        or velocity.shape != position.shape
        or mass.shape != (len(position),)
        or len(position) < neighbor_count
        or not np.isfinite(position).all()
        or not np.isfinite(velocity).all()
        or not np.isfinite(mass).all()
        or np.any(mass <= 0.0)
    ):
        raise MorphologyObservableError("snapshot geometry, velocity, or mass is invalid")

    radius = np.linalg.norm(position, axis=1)
    if np.any(radius <= minimum_radius):
        raise MorphologyObservableError("snapshot contains a tracer at the morphology origin")
    radial = position / radius[:, None]
    total_mass = float(np.sum(mass))
    if not math.isfinite(total_mass) or total_mass <= 0.0:
        raise MorphologyObservableError("snapshot mass is invalid")

    r50 = _weighted_quantile(radius, mass, 0.50)
    r90 = _weighted_quantile(radius, mass, 0.90)
    radius_mean = float(np.sum(mass * radius) / total_mass)
    radius_variance = float(np.sum(mass * (radius - radius_mean) ** 2) / total_mass)
    compactness = r50 / max(r90, minimum_radius)
    radial_spread = math.sqrt(max(radius_variance, 0.0)) / max(r50, minimum_radius)

    centroid = np.einsum("n,ni->i", mass, position) / total_mass
    displacement = position - centroid
    covariance = np.einsum("n,ni,nj->ij", mass, displacement, displacement) / total_mass
    eigenvalues = np.linalg.eigvalsh(covariance)
    if not np.isfinite(eigenvalues).all() or eigenvalues[-1] <= minimum_radius**2:
        raise MorphologyObservableError("snapshot shape covariance is degenerate")
    smallest, middle, largest = (float(value) for value in eigenvalues)
    anisotropy = (largest - smallest) / largest
    planarity = (middle - smallest) / max(middle, minimum_radius**2)

    tree = cKDTree(position)
    distance, neighbors = tree.query(position, k=neighbor_count, workers=1)
    if distance.shape != (len(position), neighbor_count) or not np.isfinite(distance).all():
        raise MorphologyObservableError("morphology neighborhood construction failed")
    offset = position[neighbors] - position[:, None, :]
    total_offset_energy = np.mean(np.einsum("nki,nki->nk", offset, offset), axis=1)
    radial_offset = np.einsum("nki,ni->nk", offset, radial)
    radial_offset_energy = np.mean(radial_offset * radial_offset, axis=1)
    shell_tangentiality = 1.0 - radial_offset_energy / np.maximum(total_offset_energy, minimum_radius**2)

    radial_velocity = np.einsum("ni,ni->n", velocity, radial)
    neighbor_radial_velocity = radial_velocity[neighbors]
    mean_radial_velocity = np.mean(neighbor_radial_velocity, axis=1)
    rms_radial_velocity = np.sqrt(np.mean(neighbor_radial_velocity**2, axis=1))
    counterflow = 1.0 - np.abs(mean_radial_velocity) / np.maximum(rms_radial_velocity, minimum_radius)

    result = {
        "morphology_compactness": np.full(len(position), compactness),
        "morphology_radial_spread": np.full(len(position), radial_spread),
        "morphology_anisotropy": np.full(len(position), anisotropy),
        "morphology_planarity": np.full(len(position), planarity),
        "morphology_shell_tangentiality": np.clip(shell_tangentiality, 0.0, 1.0),
        "morphology_counterflow": np.clip(counterflow, 0.0, 1.0),
    }
    if tuple(result) != MORPHOLOGY_ATOMS or not all(np.isfinite(value).all() for value in result.values()):
        raise MorphologyObservableError("morphology coordinate construction is nonfinite")
    return result


def augment_observable_alphabet(
    base_atoms: Mapping[str, np.ndarray],
    position: np.ndarray,
    velocity: np.ndarray,
    mass: np.ndarray,
    *,
    neighbor_count: int = 16,
    minimum_radius: float = 1e-9,
) -> dict[str, np.ndarray]:
    """Merge morphology coordinates into a target-independent atom alphabet."""
    if any(name in base_atoms for name in MORPHOLOGY_ATOMS):
        raise MorphologyObservableError("morphology atom collides with an existing alphabet member")
    result = {name: np.asarray(value, dtype=np.float64) for name, value in base_atoms.items()}
    result.update(
        morphology_atoms(
            position,
            velocity,
            mass,
            neighbor_count=neighbor_count,
            minimum_radius=minimum_radius,
        )
    )
    return result
