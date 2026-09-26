#!/usr/bin/env python3
"""Independent unrestricted bosonic variational obstruction for notebook section 62.3.

python computations/verify_matter_formation_boson_lower_bound.py --manifest PATH --output FRESH_DIR

Ordered bosonic ladder and compact-rotor transitions build the complete untruncated
Hamiltonian columns of the two declared trial sources A and B for m=1,16,32,64 with
N=m*m and R=4*N, in the coupled and the lambda=0 control cases. No occupation cap,
no flux cap and no physical projection is applied: every nonzero output target is
retained with explicit resource, charge and Gauss labels, and the two-state principal
matrix and Rayleigh expectation are reconstructed from the full columns. The two-column
span is not invariant, so this branch is a variational obstruction, not an eigenvalue.
Neither the primary nor the fermionic program is imported or parsed; bound sources
are read only as bytes for their digests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = "## 62. Working notes: unrestricted quantum Hamiltonian stability"
PARENT_HEADING = "## 60. Working notes: local quantum Gauss law and neutral conversion"
MANIFEST_SCHEMA = "matter-formation-quantum-stability-manifest-v1"
RESULT_SCHEMA = "matter-formation-quantum-stability-v1"
VERDICT = "SUPPORTS-conditional whole-Fock stability distinction"
SOURCES = {
    "computations/matter_formation_quantum_stability.py",
    "computations/verify_matter_formation_fermion_lower_bound.py",
    "computations/verify_matter_formation_boson_lower_bound.py",
    "foundations/particle-stationary-action-closure.md",
}
REVIEW_ROLES = {"fermion", "boson"}
LAMBDA, HOPPING, KAPPA = 1/4, 1/8, 1/2
MASS_STEPS = (1, 16, 32, 64)
CASES = ("coupled", "no_vertex")
BOUND = 1e-9
# Basis row order: (nb, np0, np1, np2, nm0, nm1, nm2, e0, e1). All seven modes are
# unbounded bosons here; the pump commutes with every charged mode.
VERTEX_TERMS = (((0, -1), (2, +1), (5, +1)),   # b a+1^dag a-1^dag
                ((2, -1), (5, -1), (0, +1)))   # b^dag a-1 a+1
HOP_TERMS = tuple(
    term
    for link in (0, 1)
    for term in (  # (occupation moves, link, rotor shift) per directed hopping term
        (((1 + link, -1), (2 + link, +1)), link, +1),   # plus rightward: e_link -> e+1
        (((2 + link, -1), (1 + link, +1)), link, -1),   # plus leftward h.c.
        (((4 + link, -1), (5 + link, +1)), link, -1),   # minus rightward: e_link -> e-1
        (((5 + link, -1), (4 + link, +1)), link, +1),   # minus leftward h.c.
    )
)


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path) -> str:
    return hashlib.sha256(canonical(path)).hexdigest()


def section_bytes(lines: list[str], heading: str) -> bytes:
    starts = [i for i, line in enumerate(lines) if line.rstrip("\n") == heading]
    if len(starts) != 1:
        raise ValueError(f"heading must occur exactly once: {heading}")
    start = starts[0]
    stop = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
                len(lines))
    return ("".join(lines[start:stop]).rstrip() + "\n").encode("utf-8")


def validate_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)
    for key, heading in (("section", HEADING), ("parent_section", PARENT_HEADING)):
        entry = manifest[key]
        if entry.get("path") != REPORT or entry.get("heading") != heading:
            raise ValueError(f"unexpected {key} binding")
        live = section_bytes(lines, heading)
        if (hashlib.sha256(live).hexdigest() != entry["sha256"]
                or canonical(path.parent / entry["snapshot"]) != live):
            raise ValueError(f"{key} mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {row["path"] for row in sources} != SOURCES:
        raise ValueError("incomplete source bindings")
    for row in sources:
        # The primary and fermionic sources are digested, never read, imported or parsed.
        if (digest(ROOT / row["path"]) != row["sha256"]
                or digest(path.parent / row["snapshot"]) != row["sha256"]):
            raise ValueError(f"source mismatch: {row['path']}")
    reviews = manifest["mathematical_reviews"]
    if len(reviews) != 2 or {row["role"] for row in reviews} != REVIEW_ROLES:
        raise ValueError("incomplete mathematical review bindings")
    for row in reviews:
        review_file = path.parent / row["path"]
        snapshot_file = path.parent / row["snapshot"]
        # A false accepted flag is rejected even if the literal line occurs in the text.
        if (row["accepted"] is not True
                or digest(review_file) != row["sha256"]
                or digest(snapshot_file) != row["sha256"]
                or "accepted: true" not in canonical(review_file).decode("utf-8").splitlines()
                or "accepted: true" not in canonical(snapshot_file).decode("utf-8").splitlines()):
            raise ValueError(f"mathematical review not accepted: {row['role']}")
    return manifest


def labels(row: tuple[int, ...]) -> tuple[int, int, tuple[int, int, int]]:
    nb, np0, np1, np2, nm0, nm1, nm2, e0, e1 = row
    rho = (np0 - nm0, np1 - nm1, np2 - nm2)
    resource = 2*nb + np0 + np1 + np2 + nm0 + nm1 + nm2
    gauss = (-e0 - rho[0], e0 - e1 - rho[1], e1 - rho[2])
    return resource, sum(rho), gauss


def compose(row: tuple[int, ...], moves, amplitude):
    """Rightmost-first ordered bosonic ladder product on an occupation row."""
    target = list(row)
    for index, delta in moves:
        n = target[index]
        if delta < 0 and n == 0:
            return None
        amplitude *= math.sqrt(n + 1) if delta > 0 else math.sqrt(n)
        target[index] = n + delta
    return tuple(target), amplitude


def hamiltonian_column(row: tuple[int, ...], coupling: float):
    """Full H|row> as an exact nonzero target dictionary, plus vertex and hopping parts."""
    column, vertex, hopping = {}, {}, {}

    def add(bucket: dict, target, amplitude):
        bucket[target] = bucket.get(target, 0.) + amplitude

    resource = 2*row[0] + sum(row[1:7])
    add(column, row, float(resource))
    electric = KAPPA/2 * (row[7]*row[7] + row[8]*row[8])
    if electric:
        add(column, row, electric)
    for moves in VERTEX_TERMS:
        stepped = compose(row, moves, coupling)
        if stepped is not None:
            add(column, *stepped)
            add(vertex, *stepped)
    for moves, link, delta_e in HOP_TERMS:
        stepped = compose(row, moves, -HOPPING)
        if stepped is not None:
            target, amplitude = stepped
            shifted = list(target)
            shifted[7 + link] += delta_e
            add(column, tuple(shifted), amplitude)
            add(hopping, tuple(shifted), amplitude)
    strip = lambda bucket: {k: v for k, v in bucket.items() if v != 0.}
    return strip(column), strip(hopping), strip(vertex)


def relative(actual: float, expected: float) -> float:
    return float(abs(actual - expected) / max(1., abs(expected)))


def build_branch(m: int, case: str, checks: dict, rows: list, arrays: dict) -> float:
    N = m*m
    resource = 4*N
    coupling = LAMBDA if case == "coupled" else 0.
    row_a = (N, 0, N, 0, 0, N, 0, 0, 0)
    row_b = (N - 1, 0, N + 1, 0, 0, N + 1, 0, 0, 0)
    column_a, hop_a, vert_a = hamiltonian_column(row_a, coupling)
    column_b, hop_b, _ = hamiltonian_column(row_b, coupling)

    image = sorted(set(column_a) | set(column_b))
    index = {row: i for i, row in enumerate(image)}
    columns = np.zeros((len(image), 2), dtype=np.float64)
    for row, amplitude in column_a.items():
        columns[index[row], 0] = amplitude
    for row, amplitude in column_b.items():
        columns[index[row], 1] = amplitude
    trial = np.array([1., -1.]) / math.sqrt(2.)
    h2 = np.zeros((2, 2), dtype=np.float64)
    for k, key in enumerate((row_a, row_b)):
        j = index.get(key)
        if j is not None:
            h2[k, :] = columns[j, :]
    energy = float(trial @ h2 @ trial)

    expected = (4*N - LAMBDA*math.sqrt(N)*(N + 1)) if coupling else float(4*N)
    # Same value through the integer polynomial 4*m^2 - (m^3+m)/4, no sqrt path.
    polynomial = (float(4*m*m) - (m**3 + m)/4.0) if coupling else float(4*m*m)
    offdiag = LAMBDA*m*(N + 1)
    prefix = f"boson_m{m}_{case}"
    image_gauss = np.array([labels(row)[2] for row in image], dtype=np.int64)
    image_q = np.array([labels(row)[1] for row in image], dtype=np.int64)
    image_r = np.array([labels(row)[0] for row in image], dtype=np.int64)

    # Hand-derived transition counts: column A = diagonal (A) + up-vertex (B) +
    # down-vertex (C) + four hops = 7 (coupled) or diagonal + four hops = 5 (control);
    # column B = diagonal (B) + down-vertex (A) + up-vertex (D, present only for N>=2
    # because b annihilates at N=1) + four hops = 7, or 6 at m=1, or 5 (control).
    # Image union: 11 (coupled m=1) / 12 (coupled m>=2) / 10 (control).
    expected_nnz = (7, 6 if m == 1 else 7) if coupling else (5, 5)
    expected_image = 11 if (coupling and m == 1) else (12 if coupling else 10)
    # v = (1,-1)/sqrt(2) -> v_k v_l = +-1/2 for the trial projection.
    rayleigh_raw = 0.5*(column_a.get(row_a, 0.) - column_a.get(row_b, 0.)
                        - column_b.get(row_a, 0.) + column_b.get(row_b, 0.))
    hop_projection = 0.5*(hop_a.get(row_a, 0.) - hop_a.get(row_b, 0.)
                          - hop_b.get(row_a, 0.) + hop_b.get(row_b, 0.))
    vertex_offdiag = vert_a.get(row_b, 0.)
    n1_b = row_b[2] + row_b[5]
    pauli_defect = n1_b - 2*row_b[2]*row_b[5]
    basis = np.array([row_a, row_b], dtype=np.int64)

    measured = {
        "energy_error": relative(energy, expected),
        "polynomial_error": relative(energy, polynomial),
        "h2_symmetry_error": relative(float(h2[0, 1]), float(h2[1, 0])),
        "diagonal_error": max(relative(float(h2[0, 0]), float(resource)),
                              relative(float(h2[1, 1]), float(resource))),
        "rayleigh_error": relative(energy, rayleigh_raw),
        "hopping_expectation": abs(hop_projection),
        "vertex_offdiag_error": relative(float(h2[1, 0]), vertex_offdiag) if coupling
                                else abs(float(h2[1, 0])),
        "hopping_quadratic_error": max(
            relative(sum(v*v for v in hop_a.values()), 4*HOPPING*HOPPING*N),
            relative(sum(v*v for v in hop_b.values()), 4*HOPPING*HOPPING*(N + 1))),
    }
    if coupling:
        measured["vertex_offdiag_error"] = relative(float(h2[0, 1]), vertex_offdiag)

    gates = {
        # Contract fixes source order A,B (B is lexicographically smaller, so a
        # larger nb in row 0 witnesses the explicit order rather than a sort.
        "basis_order": bool(basis[0, 0] > basis[1, 0]),
        "image_sorted_unique": image == sorted(set(image)),
        "image_labels_conserved": bool(np.all(image_q == 0) and np.all(image_gauss == 0)
                                       and np.all(image_r == resource)),
        "image_flux_single_hop": bool(np.max(np.abs(np.array(image, np.int64)[:, 7:])) == 1),
        "every_image_row_used": bool(np.all(np.any(columns != 0., axis=1))),
        "columns_nonzero_only": bool(np.count_nonzero(columns) == len(column_a) + len(column_b)),
        "transition_counts_exact": (len(column_a), len(column_b)) == expected_nnz
                                   and len(image) == expected_image,
        "trial_normalized": abs(float(np.linalg.norm(trial)) - 1.) <= BOUND,
        "diagonal_is_pure_resource": measured["diagonal_error"] <= BOUND,
        "hopping_expectation_zero": measured["hopping_expectation"] <= BOUND,
        "h2_symmetric": measured["h2_symmetry_error"] <= BOUND,
        "rayleigh_from_columns": measured["rayleigh_error"] <= BOUND,
        "energy_matches_formula": measured["energy_error"] <= BOUND,
        "energy_matches_integer_polynomial": measured["polynomial_error"] <= BOUND,
        "hopping_quadratic_form": measured["hopping_quadratic_error"] <= BOUND,
        "pauli_premise_fails": pauli_defect == -2*N*(N + 1) < 0,
    }
    if coupling:
        gates["vertex_supplies_offdiag"] = (measured["vertex_offdiag_error"] <= BOUND
                                            and relative(vertex_offdiag, offdiag) <= BOUND)
    else:
        gates["zero_vertex_contract"] = (float(h2[0, 1]) == 0. and float(h2[1, 0]) == 0.
                                         and relative(energy, float(resource)) <= BOUND)
    if m == 1 and coupling:
        gates["excluded_positivity_witness"] = pauli_defect == -4
    for name, passed in gates.items():
        checks[f"{prefix}_{name}"] = bool(passed)
    rows.append(dict(
        stat="boson", case=case, m=int(m), N=int(N), R=int(resource),
        trial_energy=float(energy), expected_energy=float(expected),
        image_dimension=int(len(image)),
        pauli_defect=float(pauli_defect),
        **{key: float(value) for key, value in measured.items()},
    ))
    arrays[prefix + "_basis"] = basis
    arrays[prefix + "_image_basis"] = np.array(image, dtype=np.int64).reshape(len(image), 9)
    arrays[prefix + "_columns"] = columns
    arrays[prefix + "_H2"] = h2
    arrays[prefix + "_trial"] = trial
    arrays[prefix + "_energy"] = np.asarray(energy, dtype=np.float64)
    arrays[prefix + "_expected_energy"] = np.asarray(expected, dtype=np.float64)
    arrays[prefix + "_image_gauss"] = image_gauss
    arrays[prefix + "_image_Q"] = image_q
    arrays[prefix + "_image_R"] = image_r
    return energy


def calculate():
    checks: dict = {}
    rows: list = []
    arrays: dict = {}
    energies: dict = {}
    for m in MASS_STEPS:
        for case in CASES:
            energies[(m, case)] = build_branch(m, case, checks, rows, arrays)
    checks["coupled_below_zero_vertex_control"] = all(
        energies[(m, "coupled")] < energies[(m, "no_vertex")] for m in MASS_STEPS)
    checks["coupled_control_gap_exact"] = all(
        relative(energies[(m, "no_vertex")] - energies[(m, "coupled")], (m**3 + m)/4)
        <= BOUND for m in MASS_STEPS)
    checks["fixed_row_count"] = len(rows) == 8
    for key, value in arrays.items():
        if not np.isfinite(value).all():
            raise ValueError(f"nonfinite array: {key}")
    for row in rows:
        for key, value in row.items():
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"nonfinite row scalar: {key}")
    return dict(checks=checks, rows=rows,
                scope=("Unrestricted bosonic Fock space of the supplied three-site "
                       "Hamiltonian: a Rayleigh-quotient variational obstruction to a "
                       "global lower bound, not an eigenvalue statement and not a claim "
                       "of physical fermion selection or completed matter formation."),
                complete_physical_matter_formation=False), arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        print(json.dumps(dict(verdict="INCONCLUSIVE", numeric_pass=False,
                              error="output directory already exists",
                              complete_physical_matter_formation=False)))
        return 1
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=RESULT_SCHEMA, role="boson", verdict="INCONCLUSIVE",
                   numeric_pass=False, checks={}, rows=[],
                   complete_physical_matter_formation=False)
    try:
        manifest = validate_manifest(args.manifest)
        receipt.update(manifest_sha256=digest(args.manifest),
                       source_bindings=manifest["sources"],
                       section_sha256=manifest["section"]["sha256"],
                       parent_section_sha256=manifest["parent_section"]["sha256"])
        result, arrays = calculate()
        receipt.update(result)
        json.dumps(receipt, allow_nan=False)
        np.savez_compressed(args.output / "arrays.npz", **arrays)
        passed = all(value is True for value in result["checks"].values())
        receipt.update(numeric_pass=passed,
                       verdict=VERDICT if passed else "INCONCLUSIVE",
                       arrays_sha256=hashlib.sha256(
                           (args.output / "arrays.npz").read_bytes()).hexdigest())
    except Exception as exc:
        receipt.update(numeric_pass=False, verdict="INCONCLUSIVE",
                       error=f"{type(exc).__name__}: {exc}")
    (args.output / "result.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in
                      ("verdict", "numeric_pass", "error",
                       "complete_physical_matter_formation")}))
    return 0 if receipt["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
