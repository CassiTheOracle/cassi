#!/usr/bin/env python3
"""Check the conditional scalar reduction and carrier empty-sector obstruction.

Run: python computations/matter_formation_action_check.py
This checks algebraic consequences of PA11–PA12, not physical matter creation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.linalg import expm

ROOT = Path(__file__).resolve().parents[1]


def canonical_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs/20260906_matter_formation")
    args = parser.parse_args()
    destination = args.output_dir / "action.json"
    if destination.exists():
        raise FileExistsError(f"Refusing to replace {destination}")
    phi = (1 + np.sqrt(5.0)) / 2
    psi0 = np.array([phi**-0.5, phi**-1])
    sigma = np.array([[[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]])
    spin = np.einsum("b,abc,c->a", psi0, sigma, psi0).real
    composition = float(((1-phi) * (psi0 @ psi0) + (1+phi) * spin[2]) / 2)
    # Every gauge-current coefficient Im(psi0^dagger T^a psi0) vanishes.
    gauge_current = np.einsum("b,abc,c->a", psi0, sigma / 2, psi0).imag
    rho_u, h, e, carrier_u = 4.0, 2.9598260763447164, 0.75, 1.0
    # Homogeneous core f=0, freely varied number density n >= 0.
    core_n = (h-e) / carrier_u
    core_energy_density = rho_u / 4 - (h-e)**2 / (2*carrier_u)
    saturated_per_carrier = e-h + np.sqrt(rho_u*carrier_u/2)
    # Two truncated bosonic modes: all terms conserve total number exactly.
    annihilate = np.diag(np.sqrt(np.arange(1, 5, dtype=float)), 1)
    ident = np.eye(5)
    left, right = np.kron(annihilate, ident), np.kron(ident, annihilate)
    nl, nr = left.T @ left, right.T @ right
    number = nl + nr
    hamiltonian = (0.75*nl - 1.2*nr + 0.37*(left.T @ right + right.T @ left)
                   + 0.5*(left.T @ left.T @ left @ left + right.T @ right.T @ right @ right))
    vacuum = np.zeros(25)
    vacuum[0] = 1
    commutator = float(np.max(np.abs(hamiltonian @ number - number @ hamiltonian)))
    # Time-dependent external density still supplies only number-conserving potentials.
    evolved = vacuum.astype(complex)
    for density_shift in (0.0, 2.0, -3.0, 0.75):
        evolved = expm(-0.31j * (hamiltonian + density_shift * nl)) @ evolved
    vacuum_difference = float(np.linalg.norm(evolved-vacuum))
    induced_number = float(np.vdot(evolved, number @ evolved).real)
    result = {
        "schema": "cassi.matter-formation.action.v1",
        "prereg_sha256": canonical_hash(ROOT / "computations/matter-formation-continuum-prereg.md"),
        "source_sha256": canonical_hash(Path(__file__)),
        "scalar_representative": {"norm_error": abs(float(psi0 @ psi0)-1),
                                  "composition": composition,
                                  "gauge_current_max": float(np.max(np.abs(gauge_current)))},
        "bulk": {"h_C": h, "core_number_density": core_n,
                 "core_energy_density": core_energy_density,
                 "saturated_energy_per_carrier": saturated_per_carrier},
        "finite_number_conserving_witness": {"commutator_max": commutator,
                                             "vacuum_difference": vacuum_difference,
                                             "induced_number": induced_number,
                                             "minimum_number_eigenvalue": float(np.min(np.diag(number)))},
        "scope": "Algebraic witness only. The first-order carrier Hamiltonian preserves N=0. A signed relativistic charge and pair-production interaction are absent. Bulk values omit gradients and do not establish a localized solution.",
    }
    if abs(composition) > 1e-14 or commutator > 1e-12 or vacuum_difference > 1e-14:
        raise ArithmeticError("Conditional algebraic identity failed")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
