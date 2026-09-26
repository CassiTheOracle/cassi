"""Two-parameter block-family nodal surface search.

Frozen protocol: ``computations/yang-mills-nodal-surface-prereg.md``.

The one-parameter probe of ``verify_yang_mills_nodal_family.py`` finds five
witness-free scheduled rows.  A one-parameter path can miss a
codimension-one nodal set, so this probe rotates two block links
independently on a 33x33 torus grid and searches every grid line for
resolved sign changes.  The two one-parameter lines are cross-checked against
the sealed one-parameter receipt on the common angles.

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
import verify_yang_mills_nodal_family as family  # noqa: E402

COUPLINGS: tuple[Fraction, ...] = (Fraction(1, 4), Fraction(1), Fraction(4), Fraction(16))
CUTOFFS: tuple[int, ...] = (1, 2, 3)
GRID_STEPS = 32
RESOLUTION = 1.0e-10
CONFORMANCE_TOLERANCE = 1.0e-9
SCHEMA = "cassi.yang-mills.nodal-surface.v1"
DEFAULT_OUTPUT = "runs/yang_mills_nodal_surface/verification.json"
PREREG = "computations/yang-mills-nodal-surface-prereg.md"
FAMILY_PREREG = "computations/yang-mills-nodal-family-prereg.md"
FAMILY_SOURCE = "computations/verify_yang_mills_nodal_family.py"
FAMILY_RECEIPT = "runs/yang_mills_nodal_family/verification.json"
PRIMARY_SOURCE = "computations/verify_yang_mills_exact_block_spectrum.py"
HELPER = "computations/yang_mills_conditional_algebra.py"


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def surface_amplitude(row: dict[str, Any], phi: float, psi: float) -> float:
    """Ritz wavefunction with block links 0 and 1 rotated by phi and psi."""

    states = row["states"]
    vector = row["vector"]
    left = primary.BLOCK_LINKS[0]
    right = primary.BLOCK_LINKS[1]
    elements: dict[int, np.ndarray] = {}
    for state in states:
        for e in primary.state_leg_spins(state):
            elements.setdefault(e, np.eye(2, dtype=complex))
    elements[left] = family.rotation(phi)
    elements[right] = family.rotation(psi)
    total = 0.0 + 0.0j
    for position, state in enumerate(states):
        point = {
            e: primary.rep_matrix(spin, elements[e])
            for e, spin in primary.state_leg_spins(state).items()
        }
        total += float(vector[position]) * complex(primary.evaluate_state(state, point))
    return float(total.real)


def line_changes(values: list[float]) -> dict[str, Any]:
    changes = []
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
    return {"change_count": len(changes), "changes": changes}


def row_record(cutoff: int, coupling: Fraction) -> dict[str, Any]:
    space = primary.SpectrumSpace(cutoff)
    ritz = primary.ritz_row(space, coupling, None)
    row = {"states": list(space.states), "vector": np.asarray(ritz["vector"], dtype=float)}
    angles = [2.0 * math.pi * index / GRID_STEPS for index in range(GRID_STEPS + 1)]
    grid = [
        [surface_amplitude(row, phi, psi) for psi in angles]
        for phi in angles
    ]
    lines: list[dict[str, Any]] = []
    for index, phi in enumerate(angles):
        lines.append({"kind": "phi", "index": index, **line_changes(list(grid[index]))})
    for index, psi in enumerate(angles):
        column = [grid[position][index] for position in range(len(angles))]
        lines.append({"kind": "psi", "index": index, **line_changes(column)})
    witnessed = [line for line in lines if line["change_count"] > 0]
    record: dict[str, Any] = {
        "cutoff": cutoff,
        "coupling": str(coupling),
        "basis_dimension": len(space.states),
        "projected_residual": ritz["projected_residual"],
        "grid_steps": GRID_STEPS,
        "grid_lines": len(lines),
        "lines_with_resolved_sign_change": len(witnessed),
        "total_sign_changes": sum(line["change_count"] for line in lines),
        "minimum_modulus": min(abs(value) for line in grid for value in line),
        "link0_line": [grid[position][0] for position in range(len(angles))],
        "link1_line": list(grid[0]),
        "grid_sha256": hashlib.sha256(
            np.asarray(grid, dtype=np.float64).tobytes()
        ).hexdigest(),
        "nodal_witness": bool(witnessed),
        "classification": "NODAL_SET" if witnessed else "NO_RESOLVED_SIGN_CHANGE",
    }
    return record


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    output = pathlib.Path(os.environ.get("NODAL_SURFACE_OUTPUT", DEFAULT_OUTPUT))
    if not output.is_absolute():
        output = root / output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing receipt {output}")
    started = time.time()
    sealed = json.loads((root / FAMILY_RECEIPT).read_text(encoding="utf-8"))
    sealed_rows = {
        (row["cutoff"], row["coupling"]): row for row in sealed["rows"]
    }

    rows: list[dict[str, Any]] = []
    for cutoff in CUTOFFS:
        for coupling in COUPLINGS:
            record = row_record(cutoff, coupling)
            reference = sealed_rows[(cutoff, str(coupling))]
            common = [3 * index for index in range(17)]
            checks = {
                "link0_line_vs_path_A": max(
                    abs(record["link0_line"][2 * index] - reference["paths"]["A"]["amplitudes"][common[index]])
                    for index in range(17)
                ),
                "link1_line_vs_path_B": max(
                    abs(record["link1_line"][2 * index] - reference["paths"]["B"]["amplitudes"][common[index]])
                    for index in range(17)
                ),
            }
            record["conformance"] = checks
            rows.append(record)

    conformance = max(
        max(record["conformance"].values()) for record in rows
    )
    witnessed = [record for record in rows if record["nodal_witness"]]
    silent = [record for record in rows if not record["nodal_witness"]]
    if conformance > CONFORMANCE_TOLERANCE:
        classification = "INCONCLUSIVE"
        execution = "FAIL"
    elif not silent:
        classification = "WITNESS_WIDENS_TO_FULL_SCHEDULE"
        execution = "PASS"
    else:
        classification = "WITNESS_CONFINED"
        execution = "PASS"

    receipt = {
        "schema": SCHEMA,
        "execution": execution,
        "classification": classification,
        "summary": {
            "rows": len(rows),
            "rows_with_nodal_witness": len(witnessed),
            "rows_without_nodal_witness": len(silent),
            "cutoffs": list(CUTOFFS),
            "couplings": [str(value) for value in COUPLINGS],
            "grid_points_per_row": (GRID_STEPS + 1) ** 2,
            "resolution": RESOLUTION,
        },
        "validation": {
            "conformance_max_deviation": conformance,
            "conformance_tolerance": CONFORMANCE_TOLERANCE,
        },
        "rows": rows,
        "silent_rows": [
            {"cutoff": record["cutoff"], "coupling": record["coupling"]}
            for record in silent
        ],
        "open_obligations": [
            "exact-vacuum fibre rate replacing the projected Ritz density",
            "transport score",
            "cutoff removal",
            "uniform interacting recovery",
            "thermodynamic limit",
            "continuum construction and positive mass gap",
        ],
        "inputs": {
            "computations/verify_yang_mills_nodal_surface.py": sha256_file(pathlib.Path(__file__)),
            PREREG: sha256_file(root / PREREG),
            FAMILY_PREREG: sha256_file(root / FAMILY_PREREG),
            FAMILY_SOURCE: sha256_file(root / FAMILY_SOURCE),
            FAMILY_RECEIPT: sha256_file(root / FAMILY_RECEIPT),
            PRIMARY_SOURCE: sha256_file(root / PRIMARY_SOURCE),
            HELPER: sha256_file(root / HELPER),
        },
        "wall_seconds": time.time() - started,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(f"wrote {output}: execution {execution}; classification {classification}")
    for record in rows:
        print(
            f"[row] J{record['cutoff']}_x{record['coupling']} "
            f"lines_with_change={record['lines_with_resolved_sign_change']:3d} "
            f"total_changes={record['total_sign_changes']:3d} "
            f"min|Omega|={record['minimum_modulus']:.3e} "
            f"conf={max(record['conformance'].values()):.2e} {record['classification']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
