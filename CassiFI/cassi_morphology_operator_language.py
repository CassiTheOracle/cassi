"""Successor grammar for morphology-aware field-operator invention.

The V4 full-observable executor is receipt-bound and remains untouched.  This module
is the explicit language boundary for its successor: a new frozen executor imports
this alphabet rather than modifying an already published measurement instrument.
"""
from __future__ import annotations

from typing import Mapping

import numpy as np

from cassi_full_observable_invention import ATOMS as BASE_ATOMS
from cassi_full_observable_invention import MUTATION_COMPANIONS as BASE_MUTATION_COMPANIONS
from cassi_morphology_observables import MORPHOLOGY_ATOMS, augment_observable_alphabet


OPERATOR_ATOMS = (*BASE_ATOMS, *MORPHOLOGY_ATOMS)
MORPHOLOGY_MUTATION_COMPANIONS = (
    "morphology_compactness",
    "morphology_radial_spread",
    "morphology_anisotropy",
    "morphology_shell_tangentiality",
    "morphology_counterflow",
)
MUTATION_COMPANIONS = (*BASE_MUTATION_COMPANIONS, *MORPHOLOGY_MUTATION_COMPANIONS)


def enrich_snapshot_atoms(
    base_atoms: Mapping[str, np.ndarray],
    position: np.ndarray,
    velocity: np.ndarray,
    mass: np.ndarray,
    *,
    neighbor_count: int = 16,
    minimum_radius: float = 1e-9,
) -> dict[str, np.ndarray]:
    """Return the exact successor alphabet from one target-independent snapshot."""
    result = augment_observable_alphabet(
        base_atoms,
        position,
        velocity,
        mass,
        neighbor_count=neighbor_count,
        minimum_radius=minimum_radius,
    )
    if tuple(result) != OPERATOR_ATOMS:
        raise ValueError("morphology operator alphabet order drifted")
    return result
