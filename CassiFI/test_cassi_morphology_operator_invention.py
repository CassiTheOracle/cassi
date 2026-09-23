from __future__ import annotations

import cassi_field_operator_invention as typed
import cassi_full_observable_invention as legacy

from cassi_morphology_operator_invention import OPERATOR_ATOMS, _activated


def test_morphology_activation_is_complete_and_restores_v4_language() -> None:
    original_atoms = legacy.ATOMS
    original_typed_atoms = typed.ATOMS

    with _activated():
        assert legacy.ATOMS == OPERATOR_ATOMS
        assert len(legacy._seed_scalars()) == 16
        assert 2 <= len(legacy._mutations(legacy._seed_scalars()[0])) <= 16
        controls = legacy.calibration_controls()
        assert controls["alphabet"]["status"] == "PASS"
        assert controls["alphabet"]["atom_count"] == 37
        assert controls["morphology-contrast"]["status"] == "PASS"

    assert legacy.ATOMS == original_atoms
    assert typed.ATOMS == original_typed_atoms
