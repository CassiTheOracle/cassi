#!/usr/bin/env python3
"""Source-bound whole-Fock stability comparison for notebook section 62.

python computations/matter_formation_quantum_stability.py --manifest PATH --output FRESH_DIR
The physical microscopic sector remains unselected. Finite spectra check an
operator construction; the unrestricted conclusions use the exact identities.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = "## 62. Working notes: unrestricted quantum Hamiltonian stability"
PARENT = "## 60. Working notes: local quantum Gauss law and neutral conversion"
MANIFEST_SCHEMA = "matter-formation-quantum-stability-manifest-v1"
VERDICT = "SUPPORTS-conditional whole-Fock stability distinction"
SOURCES = {
    "computations/matter_formation_quantum_stability.py",
    "computations/verify_matter_formation_fermion_lower_bound.py",
    "computations/verify_matter_formation_boson_lower_bound.py",
    "foundations/particle-stationary-action-closure.md",
}
LAMBDA, J, KAPPA = 1/4, 1/8, 1/2
RESOURCES = (0, 2, 4, 6, 8, 16, 32, 64)
M_VALUES = (1, 16, 32, 64)
BOUND = 1e-9
D = np.array([[-1, 0], [1, -1], [0, 1]], dtype=np.int64)


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path) -> str:
    return hashlib.sha256(canonical(path)).hexdigest()


def validate_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)
    for key, heading in (("section", HEADING), ("parent_section", PARENT)):
        item = manifest[key]
        if item.get("path") != REPORT or item.get("heading") != heading:
            raise ValueError(f"unexpected {key}")
        starts = [i for i, line in enumerate(lines) if line.rstrip() == heading]
        if len(starts) != 1:
            raise ValueError(f"{key} must occur exactly once")
        start = starts[0]
        stop = next((i for i in range(start+1, len(lines)) if lines[i].startswith("## ")), len(lines))
        live = ("".join(lines[start:stop]).rstrip()+"\n").encode("utf-8")
        if hashlib.sha256(live).hexdigest() != item["sha256"] or canonical(path.parent/item["snapshot"]) != live:
            raise ValueError(f"frozen or current {key} mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {item["path"] for item in sources} != SOURCES:
        raise ValueError("incomplete source bindings")
    for item in sources:
        if digest(ROOT/item["path"]) != item["sha256"] or digest(path.parent/item["snapshot"]) != item["sha256"]:
            raise ValueError(f"source mismatch: {item['path']}")
    reviews = manifest["mathematical_reviews"]
    if len(reviews) != 2 or {item["role"] for item in reviews} != {"fermion", "boson"}:
        raise ValueError("incomplete mathematical reviews")
    for item in reviews:
        review = path.parent/item["snapshot"]
        if (item.get("accepted") is not True or digest(review) != item["sha256"]
                or digest(path.parent/item["path"]) != item["sha256"]
                or "accepted: true" not in canonical(review).decode("utf-8").splitlines()):
            raise ValueError(f"mathematical review is not qualified: {item['role']}")
    return manifest


def relative_error(actual, expected) -> float:
    actual, expected = np.asarray(actual), np.asarray(expected)
    if not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise ValueError("nonfinite comparison")
    return float(np.linalg.norm(actual-expected)/max(1., float(np.linalg.norm(expected))))


def labels(basis):
    rho = basis[:, 1:4]-basis[:, 4:7]
    return (basis[:, 7:] @ D.T-rho, rho.sum(axis=1),
            2*basis[:, 0]+basis[:, 1:7].sum(axis=1))


def physical_row(nb: int, occupation):
    return (int(nb), *map(int, occupation), int(occupation[3]-occupation[0]),
            int(occupation[2]-occupation[5]))


def fermion_basis(resource: int, occupations):
    rows = [physical_row(resource//2-int(sum(occ[:3])), occ) for occ in occupations
            if sum(occ[:3]) == sum(occ[3:]) and 2*sum(occ[:3]) <= resource]
    return np.array(sorted(rows), dtype=np.int64).reshape(-1, 9)


def jordan_wigner():
    identity, parity = np.eye(2, dtype=np.int64), np.diag([1, -1])
    lowering = np.array([[0, 1], [0, 0]], dtype=np.int64)
    modes = []
    for mode in range(6):
        matrix = np.ones((1, 1), dtype=np.int64)
        for pos in range(6):
            matrix = np.kron(matrix, parity if pos < mode else lowering if pos == mode else identity)
        modes.append(matrix)
    number = [mode.T @ mode for mode in modes]
    pair = modes[4] @ modes[1]
    gradients = [modes[offset+link+1]-modes[offset+link] for offset in (0, 3) for link in (0, 1)]
    hopping = sum(-(J)*(modes[offset+link+1].T @ modes[offset+link]
                         + modes[offset+link].T @ modes[offset+link+1])
                  for offset in (0, 3) for link in (0, 1))
    checks = {
        "exact_CAR": all(np.array_equal(a @ b.T+b.T @ a, np.eye(64, dtype=np.int64) if i == j else np.zeros((64, 64), dtype=np.int64))
                         and not np.any(a @ b+b @ a) for i, a in enumerate(modes) for j, b in enumerate(modes)),
        "pair_number_identity": np.array_equal(pair.T @ pair, number[1] @ number[4]),
        "Pauli_remainder_spectrum": set(np.diag(number[1]+number[4]-2*number[1] @ number[4]).tolist()) == {0, 1},
    }
    return modes, pair, hopping, sum(t.T @ t for t in gradients), checks


def exact_algebra():
    nb, n0, n1, n2, p, vertex, electric, hop = sp.symbols("nb n0 n1 n2 P V electric hop", real=True)
    lam, j = sp.Rational(1, 4), sp.Rational(1, 8)
    resource = 2*nb+n0+n1+n2
    b_gram = nb+vertex+lam**2*p
    t_gram = (hop+j*(n0+2*n1+n2))/j
    extra = sp.Rational(3, 8)*(n0+n2)+sp.Rational(7, 32)*n1+sp.Rational(1, 32)*(n1-2*p)
    identity = sp.expand(resource/2+electric+b_gram+j*t_gram+extra-(resource+electric+vertex+hop))
    m = sp.symbols("m", positive=True, integer=True)
    polynomial = 4*m**2-(m**3+m)/4
    rayleigh = 4*m**2-lam*sp.sqrt(m**2)*(m**2+1)
    checks = {
        "exact_sum_of_squares_identity": identity == 0,
        "exact_bosonic_rayleigh_polynomial": sp.simplify(rayleigh-polynomial) == 0,
        "bosonic_negative_leading_coefficient": sp.Poly(polynomial, m).LC() == -sp.Rational(1, 4),
        "bosonic_asymptotic_obstruction": sp.limit(polynomial/m**3, m, sp.oo) == -sp.Rational(1, 4),
    }
    return checks, dict(sum_of_squares_residual=str(identity), bosonic_rayleigh_polynomial=str(polynomial),
                        bosonic_leading_coefficient="-1/4", fermionic_lower_bound="R/2 + kappa*(E0^2+E1^2)/2",
                        physical_gap_lower_bound="1 (model units; not an equality)")


def fermion_frames(arrays):
    occupations = np.array(list(itertools.product((0, 1), repeat=6)), dtype=np.int64)
    _, pair, hopping, t_gram_charged, checks = jordan_wigner()
    rows = []
    weights = np.array([32, 16, 8, 4, 2, 1], dtype=np.int64)
    for resource in RESOURCES:
        prefix = f"fermion_R{resource}"
        basis = fermion_basis(resource, occupations)
        lookup = {tuple(row): i for i, row in enumerate(basis)}
        charged_indices = basis[:, 1:7] @ weights
        size = len(basis)
        flux2 = (basis[:, 7:]**2).sum(axis=1)
        hamiltonian = np.diag(resource+KAPPA*flux2/2)
        b_basis = fermion_basis(resource-2, occupations)
        b_lookup = {tuple(row): i for i, row in enumerate(b_basis)}
        b_image = np.zeros((len(b_basis), size))

        def add_matrix(matrix, target, target_lookup, shift, coefficient):
            for col, (source, charged_index) in enumerate(zip(basis, charged_indices)):
                neutral = int(source[0])
                factor = coefficient(neutral)
                if factor == 0:
                    continue
                for changed in np.flatnonzero(matrix[:, charged_index]):
                    destination = physical_row(neutral+shift, occupations[changed])
                    if destination not in target_lookup:
                        raise ValueError(f"{prefix}: omitted nonzero exact-sector transition")
                    target[target_lookup[destination], col] += factor*matrix[changed, charged_index]

        add_matrix(hopping, hamiltonian, lookup, 0, lambda nb: 1.)
        add_matrix(pair.T, hamiltonian, lookup, -1, lambda nb: LAMBDA*math.sqrt(nb))
        add_matrix(pair, hamiltonian, lookup, 1, lambda nb: LAMBDA*math.sqrt(nb+1))
        add_matrix(np.eye(64, dtype=np.int64), b_image, b_lookup, -1, math.sqrt)
        add_matrix(pair, b_image, b_lookup, 0, lambda nb: LAMBDA)
        b_gram = b_image.T @ b_image
        same_neutral = basis[:, 0, None] == basis[None, :, 0]
        t_gram = t_gram_charged[np.ix_(charged_indices, charged_indices)]*same_neutral
        site_numbers = basis[:, 1:4]+basis[:, 4:7]
        projector = basis[:, 2]*basis[:, 5]
        extra = 3*(site_numbers[:, 0]+site_numbers[:, 2])/8+7*site_numbers[:, 1]/32+(site_numbers[:, 1]-2*projector)/32
        remainder = hamiltonian-np.diag(resource/2+KAPPA*flux2/2)
        reconstructed = b_gram+J*t_gram+np.diag(extra)
        eig = np.linalg.eigvalsh(hamiltonian)
        remainder_eig = np.linalg.eigvalsh(remainder)
        identity_error = relative_error(reconstructed, remainder)
        tolerance = BOUND*max(1., float(np.linalg.norm(hamiltonian)))
        gauss, charge, measured_resource = labels(basis)
        expected_dimension = sum(math.comb(3, k)**2 for k in range(min(3, resource//2)+1))
        checks.update({prefix+"_dimension": size == expected_dimension,
                       prefix+"_physical_labels": bool(not np.any(gauss) and not np.any(charge) and np.all(measured_resource == resource)),
                       prefix+"_Hermiticity": relative_error(hamiltonian, hamiltonian.T) <= BOUND,
                       prefix+"_identity": identity_error <= BOUND,
                       prefix+"_positive_remainder": bool(remainder_eig[0] >= -tolerance),
                       prefix+"_spectral_lower_bound": bool(eig[0] >= resource/2-tolerance),
                       prefix+"_nonnegative_diagonal_terms": bool(np.all(extra >= 0))})
        if resource == 0:
            checks["unique_zero_resource_vacuum"] = size == 1 and not np.any(hamiltonian)
        arrays.update({prefix+"_basis": basis, prefix+"_H": hamiltonian, prefix+"_B_gram": b_gram,
                       prefix+"_T_gram": t_gram, prefix+"_diagonal_remainder": extra,
                       prefix+"_bound_remainder": remainder, prefix+"_eigenvalues": eig,
                       prefix+"_remainder_eigenvalues": remainder_eig})
        rows.append(dict(stat="fermion", R=resource, dimension=size, minimum_energy=float(eig[0]),
                         lower_bound=resource/2, minimum_remainder_eigenvalue=float(remainder_eig[0]), identity_error=identity_error))
    return checks, rows


def boson_columns(basis, coupling):
    """Direct closed-form matrix elements on central-pair source states."""
    columns = []
    for source in basis:
        nb, p = int(source[0]), int(source[2])
        values = {tuple(source): float(2*nb+2*p)}
        if coupling and nb:
            target = source.copy()
            target[0] -= 1
            target[2] += 1
            target[5] += 1
            values[tuple(target)] = coupling*math.sqrt(nb)*(p+1)
        if coupling and p:
            target = source.copy()
            target[0] += 1
            target[2] -= 1
            target[5] -= 1
            values[tuple(target)] = coupling*math.sqrt(nb+1)*p
        for charge, offset in ((1, 1), (-1, 4)):
            for destination, link, direction in ((0, 0, -1), (2, 1, 1)):
                if p:
                    target = source.copy()
                    target[offset+1] -= 1
                    target[offset+destination] += 1
                    target[7+link] += charge*direction
                    values[tuple(target)] = -J*math.sqrt(p)
        columns.append(values)
    image_basis = np.array(sorted(set().union(*(col.keys() for col in columns))), dtype=np.int64)
    image = np.array([[col.get(tuple(row), 0.) for col in columns] for row in image_basis])
    return image_basis, image


def boson_frames(arrays):
    checks, rows = {}, []
    for m in M_VALUES:
        n = m*m
        basis = np.array([[n, 0, n, 0, 0, n, 0, 0, 0],
                          [n-1, 0, n+1, 0, 0, n+1, 0, 0, 0]], dtype=np.int64)
        source_gauss, source_charge, source_resource = labels(basis)
        if m == 1:
            witness = basis[1]
            checks["bosonic_Pauli_premise_rejected"] = int(witness[2]+witness[5]-2*witness[2]*witness[5]) == -4
        for case, coupling in (("coupled", LAMBDA), ("no_vertex", 0.)):
            prefix = f"boson_m{m}_{case}"
            image_basis, columns = boson_columns(basis, coupling)
            image_lookup = {tuple(row): i for i, row in enumerate(image_basis)}
            h2 = columns[[image_lookup[tuple(row)] for row in basis], :]
            trial = np.array([1., -1.])/math.sqrt(2)
            source_vector = np.zeros(len(image_basis))
            for row, amplitude in zip(basis, trial):
                source_vector[image_lookup[tuple(row)]] = amplitude
            energy = float(np.vdot(source_vector, columns @ trial).real)
            expected = float(4*n-coupling*m*(n+1))
            expected_h2 = np.array([[4*n, coupling*m*(n+1)], [coupling*m*(n+1), 4*n]])
            gauss, charge, resource = labels(image_basis)
            error = relative_error(energy, expected)
            checks.update({prefix+"_source_labels": bool(not np.any(source_gauss) and not np.any(source_charge) and np.all(source_resource == 4*n)),
                           prefix+"_complete_image_labels": bool(not np.any(gauss) and not np.any(charge) and np.all(resource == 4*n)),
                           prefix+"_principal_matrix": relative_error(h2, expected_h2) <= BOUND,
                           prefix+"_normalized_trial": relative_error(np.vdot(trial, trial), 1.) <= BOUND,
                           prefix+"_energy": error <= BOUND})
            arrays.update({prefix+"_basis": basis, prefix+"_image_basis": image_basis, prefix+"_columns": columns,
                           prefix+"_H2": h2, prefix+"_trial": trial, prefix+"_energy": np.array(energy),
                           prefix+"_expected_energy": np.array(expected), prefix+"_image_gauss": gauss,
                           prefix+"_image_Q": charge, prefix+"_image_R": resource})
            rows.append(dict(stat="boson", case=case, m=m, N=n, R=4*n, trial_energy=energy,
                             expected_energy=expected, energy_error=error))
    return checks, rows


def calculate():
    arrays = {}
    checks, identities = exact_algebra()
    fermion_checks, fermion_rows = fermion_frames(arrays)
    boson_checks, boson_rows = boson_frames(arrays)
    checks.update(fermion_checks)
    checks.update(boson_checks)
    checks["fixed_row_count"] = len(fermion_rows) == len(boson_rows) == 8
    checks = {key: bool(value) for key, value in checks.items()}
    for key, value in arrays.items():
        if not np.isfinite(value).all():
            raise ValueError(f"nonfinite array: {key}")
    return dict(checks=checks, rows=fermion_rows+boson_rows, exact_identities=identities,
                scope="Supplied three-site whole-Fock Hamiltonian; no microscopic statistics selection or completed physical matter formation.",
                complete_physical_matter_formation=False), arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        print(json.dumps(dict(verdict="INCONCLUSIVE", numeric_pass=False, error="output directory already exists",
                              complete_physical_matter_formation=False)))
        return 1
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema="matter-formation-quantum-stability-v1", role="primary", verdict="INCONCLUSIVE",
                   numeric_pass=False, checks={}, rows=[], complete_physical_matter_formation=False)
    try:
        manifest = validate_manifest(args.manifest)
        receipt.update(manifest_sha256=digest(args.manifest), section_sha256=manifest["section"]["sha256"],
                       parent_section_sha256=manifest["parent_section"]["sha256"], source_bindings=manifest["sources"])
        result, arrays = calculate()
        receipt.update(result)
        json.dumps(receipt, allow_nan=False)
        np.savez_compressed(args.output/"arrays.npz", **arrays)
        passed = all(value is True for value in result["checks"].values())
        receipt.update(numeric_pass=passed, verdict=VERDICT if passed else "INCONCLUSIVE",
                       arrays_sha256=hashlib.sha256((args.output/"arrays.npz").read_bytes()).hexdigest())
    except Exception as exc:
        receipt.update(numeric_pass=False, verdict="INCONCLUSIVE", error=f"{type(exc).__name__}: {exc}")
    (args.output/"result.json").write_text(json.dumps(receipt, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in ("verdict", "numeric_pass", "error", "complete_physical_matter_formation")}))
    return 0 if receipt["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
