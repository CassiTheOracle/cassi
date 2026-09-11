"""Schedule-wide nodal family probe for the cutoff-projected Ritz density.

Frozen protocol: ``computations/yang-mills-nodal-family-prereg.md``.

For every scheduled row ``(J, x)`` the normalized Ritz vector of the
seven-link cutoff Hamiltonian is evaluated along two paths in the block
manifold.  Path A rotates block link 0 and path B rotates block link 1 along
the conjugacy loop ``exp(i phi sigma_3 / 2)`` with the remaining block links
and the exterior held at the identity.

A resolved sign change along a continuous path inside the block proves that
the cutoff density ``rho ~ |Omega|^2`` has a nonempty nodal set, since
``Omega`` is a polynomial in the link matrix elements.  The vanishing
Dirichlet-energy argument of theorem section 9.23 then makes the
unrestricted conditional Poincare gap of that cutoff measure zero.

The script seals one receipt and refuses to overwrite it.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import sys
import time
from fractions import Fraction
from typing import Any

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_yang_mills_exact_block_spectrum as primary  # noqa: E402

COUPLINGS: tuple[Fraction, ...] = (Fraction(1, 4), Fraction(1), Fraction(4), Fraction(16))
CUTOFFS: tuple[int, ...] = (1, 2, 3)
GRID_POINTS = 48
RESOLUTION = 1.0e-10
CROSS_CHECK_TOLERANCE = 1.0e-9
SCHEMA = "cassi.yang-mills.nodal-family.v1"
DEFAULT_OUTPUT = "runs/yang_mills_nodal_family/verification.json"
PREREG = "computations/yang-mills-nodal-family-prereg.md"
HELPER = "computations/yang_mills_conditional_algebra.py"


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rotation(angle: float) -> np.ndarray:
    """``exp(i angle sigma_3 / 2)`` in the fundamental representation."""
    return np.array(
        [[np.exp(0.5j * angle), 0.0], [0.0, np.exp(-0.5j * angle)]], dtype=complex
    )


def amplitude(row: dict[str, Any], link: int, angle: float) -> complex:
    """Ritz wavefunction value at one block configuration with identity exterior."""
    states = row["states"]
    vector = row["vector"]
    elements: dict[int, np.ndarray] = {}
    for state in states:
        for e in primary.state_leg_spins(state):
            elements.setdefault(e, np.eye(2, dtype=complex))
    elements[link] = rotation(angle)
    total = 0.0 + 0.0j
    for position, state in enumerate(states):
        point = {
            e: primary.rep_matrix(spin, elements[e])
            for e, spin in primary.state_leg_spins(state).items()
        }
        total += float(vector[position]) * complex(primary.evaluate_state(state, point))
    return total


def resolved_sign_changes(values: list[float]) -> dict[str, Any]:
    changes: list[dict[str, float]] = []
    unresolved = [index for index, value in enumerate(values) if abs(value) <= RESOLUTION]
    sign = [0 if abs(value) <= RESOLUTION else (1 if value > 0.0 else -1) for value in values]
    for index in range(len(sign) - 1):
        if sign[index] * sign[index + 1] < 0:
            changes.append(
                {
                    "left_index": index,
                    "right_index": index + 1,
                    "left_value": values[index],
                    "right_value": values[index + 1],
                }
            )
    return {
        "change_count": len(changes),
        "changes": changes,
        "parity_odd": len(changes) % 2 == 1,
        "unresolved_indices": unresolved,
        "minimum_modulus": min(abs(value) for value in values),
        "endpoint_signs": [sign[0], sign[-1]],
    }


def row_record(cutoff: int, coupling: Fraction) -> dict[str, Any]:
    space = primary.SpectrumSpace(cutoff)
    ritz = primary.ritz_row(space, coupling, None)
    states = list(space.states)
    vector = np.asarray(ritz["vector"], dtype=float)
    angles = [2.0 * math.pi * index / GRID_POINTS for index in range(GRID_POINTS + 1)]
    record: dict[str, Any] = {
        "cutoff": cutoff,
        "coupling": str(coupling),
        "basis_dimension": len(states),
        "energy_ground": ritz["energy_ground"],
        "projected_residual": ritz["projected_residual"],
        "path_grid_points": GRID_POINTS + 1,
        "paths": {},
    }
    shared = {"states": states, "vector": vector}
    for name, link in (("A", primary.BLOCK_LINKS[0]), ("B", primary.BLOCK_LINKS[1])):
        raw = [amplitude(shared, link, angle) for angle in angles]
        values = [value.real for value in raw]
        scale = max(abs(value) for value in raw) or 1.0
        record["paths"][name] = {
            "link": link,
            "angles": angles,
            "amplitudes": values,
            "imaginary_max": max(abs(value.imag) for value in raw),
            "imaginary_ratio": max(abs(value.imag) for value in raw) / scale,
            **resolved_sign_changes(values),
        }
    record["endpoint_amplitudes"] = {
        "identity": record["paths"]["A"]["amplitudes"][0],
        "antipodal": record["paths"]["A"]["amplitudes"][-1],
    }
    qualified = [
        record["paths"][name]
        for name in ("A", "B")
        if record["paths"][name]["change_count"] % 2 == 1
        and all(
            abs(change["left_value"]) > RESOLUTION and abs(change["right_value"]) > RESOLUTION
            for change in record["paths"][name]["changes"]
        )
    ]
    witnessed = [
        record["paths"][name] for name in ("A", "B") if record["paths"][name]["changes"]
    ]
    record["odd_parity_sign_change"] = bool(qualified)
    record["nodal_witness"] = bool(witnessed)
    record["classification"] = (
        "ODD_PARITY_NODAL_SET"
        if qualified
        else ("EVEN_PARITY_NODAL_SET" if witnessed else "NO_RESOLVED_SIGN_CHANGE")
    )
    return record


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    output = pathlib.Path(os.environ.get("NODAL_FAMILY_OUTPUT", DEFAULT_OUTPUT))
    if not output.is_absolute():
        output = root / output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing receipt {output}")
    started = time.time()
    control = primary.cutoff_nodal_control()
    sealed_identity, sealed_center = control["identity_and_center_amplitudes"]

    rows: list[dict[str, Any]] = []
    for cutoff in CUTOFFS:
        for coupling in COUPLINGS:
            rows.append(row_record(cutoff, coupling))

    reference = next(
        row for row in rows if row["cutoff"] == 1 and row["coupling"] == "1"
    )
    measured_identity = reference["endpoint_amplitudes"]["identity"]
    measured_center = reference["endpoint_amplitudes"]["antipodal"]
    cross_error = max(
        abs(measured_identity - float(sealed_identity)),
        abs(measured_center - float(sealed_center)),
    )
    if cross_error > CROSS_CHECK_TOLERANCE:
        raise SystemExit(f"cross-check against the sealed nodal control failed ({cross_error:g})")

    odd = [row for row in rows if row["odd_parity_sign_change"]]
    witnessed = [row for row in rows if row["nodal_witness"]]
    silent = [row for row in rows if not row["nodal_witness"]]
    imaginary_ratio_max = max(
        path["imaginary_ratio"] for row in rows for path in row["paths"].values()
    )
    if imaginary_ratio_max > 1.0e-8:
        classification = "INCONCLUSIVE"
        execution = "FAIL"
    elif len(odd) == len(rows):
        classification = "NODAL_PERSISTS_ACROSS_SCHEDULE"
        execution = "PASS"
    elif silent:
        classification = "NODAL_CONFINED"
        execution = "PASS"
    else:
        classification = "INCONCLUSIVE"
        execution = "FAIL"

    receipt = {
        "schema": SCHEMA,
        "execution": execution,
        "classification": classification,
        "summary": {
            "rows": len(rows),
            "rows_with_odd_parity_sign_change": len(odd),
            "rows_with_nodal_witness": len(witnessed),
            "rows_without_nodal_witness": len(silent),
            "cutoffs": list(CUTOFFS),
            "couplings": [str(value) for value in COUPLINGS],
            "grid_points": GRID_POINTS + 1,
            "resolution": RESOLUTION,
        },
        "validation": {
            "sealed_control_amplitudes": [float(sealed_identity), float(sealed_center)],
            "measured_amplitudes": [measured_identity, measured_center],
            "cross_error": cross_error,
            "cross_check_tolerance": CROSS_CHECK_TOLERANCE,
            "imaginary_ratio_max": imaginary_ratio_max,
        },
        "rows": rows,
        "open_obligations": [
            "exact-vacuum fibre rate replacing the projected Ritz density",
            "transport score",
            "cutoff removal",
            "uniform interacting recovery",
            "thermodynamic limit",
            "continuum construction and positive mass gap",
        ],
        "inputs": {
            "computations/verify_yang_mills_nodal_family.py": sha256_file(pathlib.Path(__file__)),
            PREREG: sha256_file(root / PREREG),
            "computations/verify_yang_mills_exact_block_spectrum.py": sha256_file(
                root / "computations/verify_yang_mills_exact_block_spectrum.py"
            ),
            HELPER: sha256_file(root / HELPER),
        },
        "wall_seconds": time.time() - started,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(f"wrote {output}: execution {execution}; classification {classification}")
    for row in rows:
        path_a = row["paths"]["A"]
        path_b = row["paths"]["B"]
        print(
            f"[row] J{row['cutoff']}_x{row['coupling']} identity={row['endpoint_amplitudes']['identity']:+.12f} "
            f"antipodal={row['endpoint_amplitudes']['antipodal']:+.12f} "
            f"changesA={path_a['change_count']} changesB={path_b['change_count']} "
            f"minA={path_a['minimum_modulus']:.3e} {row['classification']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
