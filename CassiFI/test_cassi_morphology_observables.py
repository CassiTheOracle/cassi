from __future__ import annotations

import numpy as np
import pytest

from cassi_morphology_observables import (
    MORPHOLOGY_ATOMS,
    MorphologyObservableError,
    augment_observable_alphabet,
    morphology_atoms,
)
from cassi_morphology_operator_language import (
    MORPHOLOGY_MUTATION_COMPANIONS,
    MUTATION_COMPANIONS,
    OPERATOR_ATOMS,
    enrich_snapshot_atoms,
)


def _directions(count: int, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=(count, 3))
    return values / np.linalg.norm(values, axis=1, keepdims=True)


def _tangential_velocity(radial: np.ndarray) -> np.ndarray:
    axis = np.tile(np.array((0.0, 0.0, 1.0)), (len(radial), 1))
    velocity = np.cross(radial, axis)
    near_axis = np.linalg.norm(velocity, axis=1) < 1e-9
    velocity[near_axis] = np.cross(radial[near_axis], np.array((0.0, 1.0, 0.0)))
    return velocity / np.linalg.norm(velocity, axis=1, keepdims=True)


def _thin_shell(count: int = 256) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    radial = _directions(count)
    position = radial * (3.0 + 0.01 * np.sin(np.arange(count)))[:, None]
    return position, _tangential_velocity(radial), np.ones(count)


def _isotropic_cloud(count: int = 256) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(23)
    position = rng.normal(size=(count, 3))
    position += np.array((0.2, -0.1, 0.15))
    velocity = rng.normal(size=(count, 3))
    return position, velocity, np.ones(count)


def test_morphology_atoms_are_finite_deterministic_and_target_independent() -> None:
    position, velocity, mass = _thin_shell()

    first = morphology_atoms(position, velocity, mass)
    replay = morphology_atoms(position.copy(), velocity.copy(), mass.copy())

    assert tuple(first) == MORPHOLOGY_ATOMS
    assert all(value.shape == (len(position),) for value in first.values())
    assert all(np.isfinite(value).all() for value in first.values())
    for name in MORPHOLOGY_ATOMS:
        np.testing.assert_array_equal(first[name], replay[name])

    alphabet = augment_observable_alphabet({"one": np.ones(len(position))}, position, velocity, mass)
    assert tuple(alphabet) == ("one", *MORPHOLOGY_ATOMS)
    with pytest.raises(MorphologyObservableError, match="collides"):
        augment_observable_alphabet({"morphology_compactness": np.ones(len(position))}, position, velocity, mass)


def test_morphology_coordinates_distinguish_shell_scale_shape_and_flow() -> None:
    shell_position, shell_velocity, shell_mass = _thin_shell()
    cloud_position, cloud_velocity, cloud_mass = _isotropic_cloud()
    shell = morphology_atoms(shell_position, shell_velocity, shell_mass)

    cloud = morphology_atoms(cloud_position, cloud_velocity, cloud_mass)

    nested_radial = _directions(256, seed=11)
    nested_position = nested_radial * np.where(np.arange(256) % 2 == 0, 1.0, 4.0)[:, None]
    nested = morphology_atoms(nested_position, _tangential_velocity(nested_radial), np.ones(256))

    disc_angle = np.linspace(0.0, 2.0 * np.pi, 256, endpoint=False)
    disc_radius = np.linspace(0.25, 3.0, 256)
    disc_position = np.column_stack((disc_radius * np.cos(disc_angle), disc_radius * np.sin(disc_angle), 0.002 * np.sin(3.0 * disc_angle)))
    disc_velocity = np.column_stack((-np.sin(disc_angle), np.cos(disc_angle), np.zeros(256)))
    disc = morphology_atoms(disc_position, disc_velocity, np.ones(256))

    radial = shell_position / np.linalg.norm(shell_position, axis=1, keepdims=True)
    coherent = morphology_atoms(shell_position, radial, shell_mass)
    signs = np.where(np.arange(len(radial)) % 2 == 0, -1.0, 1.0)
    counterflow = morphology_atoms(shell_position, signs[:, None] * radial, shell_mass)

    assert float(np.mean(shell["morphology_shell_tangentiality"])) > float(np.mean(cloud["morphology_shell_tangentiality"])) + 0.15
    assert float(np.mean(nested["morphology_radial_spread"])) > float(np.mean(shell["morphology_radial_spread"])) + 0.25
    assert float(np.mean(disc["morphology_anisotropy"])) > float(np.mean(cloud["morphology_anisotropy"])) + 0.45
    assert float(np.mean(disc["morphology_planarity"])) > float(np.mean(cloud["morphology_planarity"])) + 0.45
    assert float(np.mean(counterflow["morphology_counterflow"])) > float(np.mean(coherent["morphology_counterflow"])) + 0.35

def test_morphology_operator_language_merges_exact_successor_alphabet() -> None:
    position, velocity, mass = _thin_shell()
    base = {
        name: np.full(len(position), 0.25 + 0.01 * index)
        for index, name in enumerate(OPERATOR_ATOMS[: -len(MORPHOLOGY_ATOMS)])
    }

    enriched = enrich_snapshot_atoms(base, position, velocity, mass)

    assert tuple(enriched) == OPERATOR_ATOMS
    assert len(MUTATION_COMPANIONS) == len(set(MUTATION_COMPANIONS))
    assert set(MORPHOLOGY_MUTATION_COMPANIONS) <= set(MUTATION_COMPANIONS)
