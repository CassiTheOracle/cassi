#!/usr/bin/env python3
"""Independent ordered-transition witness for notebook section 62, fermion branch.

python computations/verify_matter_formation_fermion_lower_bound.py --manifest PATH --output FRESH_DIR

The eight scheduled physical fermionic sectors of the supplied three-site Hamiltonian
(section 60.1) are rebuilt from ordered canonical-anticommutation occupation/flux
transitions, not from Jordan-Wigner matrices. Each Hamiltonian is assembled twice: once
from the declared monomials completed by transposition, once from explicitly written
adjoint monomials. The neutral pump is an ordinary commuting tensor factor.

B = b + lambda*A and the four T_{sigma,link} operators are kept as rectangular maps into
their own unrestricted target-label spaces, so no charged image is ever projected onto
G = 0. Their Gram matrices are formed from those retained images. All guards (section,
parent section, four source digests, both accepted mathematical reviews) run before any
scientific array is produced. The primary program is bound by digest only and is never
read or imported.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = "## 62. Working notes: unrestricted quantum Hamiltonian stability"
PARENT_HEADING = "## 60. Working notes: local quantum Gauss law and neutral conversion"
MANIFEST_SCHEMA = "matter-formation-quantum-stability-manifest-v1"
RESULT_SCHEMA = "matter-formation-quantum-stability-v1"
ROLE = "fermion"
VERDICT = "SUPPORTS-conditional whole-Fock stability distinction"
SOURCES = {
    "computations/matter_formation_quantum_stability.py",
    "computations/verify_matter_formation_fermion_lower_bound.py",
    "computations/verify_matter_formation_boson_lower_bound.py",
    "foundations/particle-stationary-action-closure.md",
}
REVIEW_ROLES = {"fermion", "boson"}
LAMBDA, HOPPING, KAPPA = 1/4, 1/8, 1/2
RESOURCES = (0, 2, 4, 6, 8, 16, 32, 64)
DIMENSIONS = (1, 10, 19, 20, 20, 20, 20, 20)
BOUND = 1e-9
FLAG = re.compile(r"^accepted:\s*(true|false)\s*$")

# Charged CAR mode order: 0,1,2 = (+,0),(+,1),(+,2); 3,4,5 = (-,0),(-,1),(-,2).
# A monomial is a tuple of operators written in application order, that is rightmost
# operator of the textual product first. Link shifts act on the rotor factor only.
VERTEX_ANNIHILATE = (("c", 4), ("c", 1), ("b", -1))      # b a+1^dag a-1^dag
VERTEX_CREATE = (("a", 1), ("a", 4), ("b", 1))           # b^dag a-1 a+1
DECLARED = (VERTEX_ANNIHILATE,
            (("a", 0), ("U", 0, 1), ("c", 1)),           # a+1^dag U0 a+0
            (("a", 1), ("U", 1, 1), ("c", 2)),           # a+2^dag U1 a+1
            (("a", 3), ("U", 0, -1), ("c", 4)),          # a-1^dag U0^dag a-0
            (("a", 4), ("U", 1, -1), ("c", 5)))          # a-2^dag U1^dag a-1
ADJOINTS = (VERTEX_CREATE,
            (("a", 1), ("U", 0, -1), ("c", 0)),          # a+0^dag U0^dag a+1
            (("a", 2), ("U", 1, -1), ("c", 1)),          # a+1^dag U1^dag a+2
            (("a", 4), ("U", 0, 1), ("c", 3)),           # a-0^dag U0 a-1
            (("a", 5), ("U", 1, 1), ("c", 4)))           # a-1^dag U1 a-2
VERTEX_COEFFICIENTS = ((VERTEX_ANNIHILATE, LAMBDA), (VERTEX_CREATE, LAMBDA))
HOP_COEFFICIENTS = tuple((monomial, -HOPPING) for monomial in
                         DECLARED[1:] + ADJOINTS[1:])
TERMS_DECLARED = ((VERTEX_ANNIHILATE, LAMBDA),) + tuple(
    (monomial, -HOPPING) for monomial in DECLARED[1:])

# B = b + lambda*A with A = a-1 a+1, and the four hopping lowering operators.
B_TERMS = (((("b", -1),), 1.0), ((("a", 1), ("a", 4)), LAMBDA))
T_TERMS = {
    "Tp0": (+1, 1, (((("a", 1),), 1.0), ((("a", 0), ("U", 0, 1)), -1.0))),
    "Tp1": (+1, 2, (((("a", 2),), 1.0), ((("a", 1), ("U", 1, 1)), -1.0))),
    "Tm0": (-1, 1, (((("a", 4),), 1.0), ((("a", 3), ("U", 0, -1)), -1.0))),
    "Tm1": (-1, 2, (((("a", 5),), 1.0), ((("a", 4), ("U", 1, -1)), -1.0))),
}
IMAGE_TAGS = ("B", "Tp0", "Tp1", "Tm0", "Tm1")
GAUSS_SITES = ("Tp0", "Tp1", "Tm0", "Tm1")


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path) -> str:
    return hashlib.sha256(canonical(path)).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def section_bytes(heading: str) -> bytes:
    """Exact H2 section snapshot: heading line up to the next H2 heading."""
    lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.rstrip() == heading]
    require(len(starts) == 1, f"{heading!r} must occur exactly once")
    start = starts[0]
    stop = next((index for index in range(start + 1, len(lines))
                 if lines[index].startswith("## ")), len(lines))
    return ("".join(lines[start:stop]).rstrip() + "\n").encode("utf-8")


def check_section(manifest: dict, directory: Path, key: str, heading: str) -> str:
    binding = manifest[key]
    require(isinstance(binding, dict) and binding.get("path") == REPORT
            and binding.get("heading") == heading, f"unexpected {key} binding")
    live = section_bytes(heading)
    sha256 = binding.get("sha256")
    require(isinstance(sha256, str), f"{key} hash is missing")
    snapshot = digest(directory / str(binding["snapshot"]))
    require(hashlib.sha256(live).hexdigest() == sha256 == snapshot, f"{key} mismatch")
    return sha256


def check_reviews(manifest: dict, directory: Path) -> list:
    reviews = manifest["mathematical_reviews"]
    require(isinstance(reviews, list) and len(reviews) == 2,
            "manifest must bind exactly two mathematical reviews")
    require({row.get("role") for row in reviews} == REVIEW_ROLES,
            "review roles must be fermion and boson")
    bindings = []
    for row in reviews:
        require(row.get("accepted") is True, f"{row['role']} review flag is not accepted")
        sha256 = row.get("sha256")
        require(isinstance(sha256, str), "review hash is missing")
        for key in ("path", "snapshot"):
            require(digest(directory / str(row[key])) == sha256,
                    f"{row['role']} review {key} mismatch")
        text = canonical(directory / str(row["snapshot"])).decode("utf-8")
        flags = [FLAG.match(line.strip()).group(1)
                 for line in text.splitlines() if FLAG.match(line.strip())]
        require("accepted: true" in text.splitlines() and flags and all(flag == "true" for flag in flags),
                f"{row['role']} review does not literally accept itself")
        bindings.append(dict(role=row["role"], accepted=True, path=row["path"],
                             snapshot=row["snapshot"], sha256=sha256))
    return sorted(bindings, key=lambda row: row["role"])


def validate_manifest(path: Path) -> tuple:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(manifest, dict)
            and manifest.get("schema") == MANIFEST_SCHEMA, "unexpected manifest schema")
    directory = path.resolve().parent
    check_section(manifest, directory, "section", HEADING)
    check_section(manifest, directory, "parent_section", PARENT_HEADING)
    sources = manifest["sources"]
    require(isinstance(sources, list) and len(sources) == len(SOURCES)
            and {row.get("path") for row in sources} == SOURCES, "incomplete source bindings")
    for row in sources:
        # The bound programs are never parsed or imported; only their digests are read.
        require(digest(ROOT / str(row["path"])) == row.get("sha256")
                and digest(directory / str(row["snapshot"])) == row.get("sha256"),
                f"source mismatch: {row['path']}")
    return manifest, check_reviews(manifest, directory)


def row_resource(row) -> int:
    return 2 * row[0] + sum(row[1:7])


def row_charge(row) -> int:
    return sum(row[1:4]) - sum(row[4:7])


def row_gauss(row):
    return (-row[7] - (row[1] - row[4]),
            row[7] - row[8] - (row[2] - row[5]),
            row[8] - (row[3] - row[6]))


def row_flux_square(row) -> int:
    return row[7] * row[7] + row[8] * row[8]


def pauli_term(row) -> int:
    """n_1 - 2P with P = n_{+,1} n_{-,1}; Pauli restricts it to 0 or 1."""
    central = row[2] + row[5]
    return central - 2 * row[2] * row[5]


def diagonal_remainder_value(row) -> float:
    outer = row[1] + row[4] + row[3] + row[6]
    central = row[2] + row[5]
    return 3/8 * outer + 7/32 * central + 1/32 * pauli_term(row)


def diagonal_energy(row) -> float:
    return row_resource(row) + 0.5 * KAPPA * row_flux_square(row)


def apply_monomial(row, operators):
    """Ordered CAR / rotor transition. None means an exact Pauli or vacuum annihilation."""
    occupations = list(row[1:7])
    pump, flux = row[0], [row[7], row[8]]
    coefficient = 1.0
    for operator in operators:
        kind = operator[0]
        if kind == "b":
            step = operator[1]
            if step < 0:
                if pump == 0:
                    return None
                coefficient *= math.sqrt(pump)
                pump -= 1
            else:
                coefficient *= math.sqrt(pump + 1)
                pump += 1
        elif kind == "U":
            flux[operator[1]] += operator[2]
        elif kind == "a":
            index = operator[1]
            if occupations[index] == 0:
                return None
            coefficient *= -1.0 if sum(occupations[:index]) & 1 else 1.0
            occupations[index] = 0
        else:
            index = operator[1]
            if occupations[index] == 1:
                return None
            coefficient *= -1.0 if sum(occupations[:index]) & 1 else 1.0
            occupations[index] = 1
    return (pump, *occupations, *flux), coefficient


def render(operators) -> str:
    return " ".join(operator[0] + str(operator[1:]) for operator in operators) or "identity"


def accumulate(basis, terms):
    """Square sector matrix plus every nonzero target that escaped the exact basis."""
    index = {row: position for position, row in enumerate(basis)}
    matrix = np.zeros((len(basis), len(basis)), dtype=np.float64)
    escaped = []
    hits = 0
    for column, row in enumerate(basis):
        for operators, coefficient in terms:
            target = apply_monomial(row, operators)
            if target is None:
                continue
            label, amplitude = target
            value = coefficient * amplitude
            if value == 0.0:
                continue
            hits += 1
            position = index.get(label)
            if position is None:
                escaped.append(dict(source=list(map(int, row)), term=render(operators),
                                    target=list(map(int, label)), coefficient=float(value)))
                continue
            matrix[position, column] += value
    return matrix, hits, escaped


def build_image(basis, terms):
    """Rectangular coordinates into the operator's own unrestricted target space."""
    columns = {}
    for column, row in enumerate(basis):
        entries = {}
        for operators, coefficient in terms:
            target = apply_monomial(row, operators)
            if target is None:
                continue
            label, amplitude = target
            value = coefficient * amplitude
            if value == 0.0:
                continue
            entries[label] = entries.get(label, 0.0) + value
        for label, value in entries.items():
            columns.setdefault(label, []).append((column, value))
    image_basis = sorted(columns)
    index = {row: position for position, row in enumerate(image_basis)}
    matrix = np.zeros((len(image_basis), len(basis)), dtype=np.float64)
    for row, entries in columns.items():
        for column, value in entries:
            if value != 0.0:
                matrix[index[row], column] = value
    return image_basis, matrix


def sector_basis(resource):
    """Solve Gauss's law analytically: unique flux e0 = -rho0, e1 = rho2, Q = 0."""
    rows = []
    for charged in itertools.product((0, 1), repeat=6):
        matter = sum(charged)
        if matter > resource or (resource - matter) % 2 or sum(charged[:3]) != sum(charged[3:]):
            continue
        charge = (charged[0] - charged[3], charged[1] - charged[4], charged[2] - charged[5])
        rows.append(((resource - matter) // 2, *charged, -charge[0], charge[2]))
    return sorted(rows)


def sector_basis_by_constraint(resource):
    """Independent route: enumerate a generous flux window and keep only G = 0, Q = 0."""
    rows = []
    for pump in range(resource // 2 + 1):
        for charged in itertools.product((0, 1), repeat=6):
            if 2 * pump + sum(charged) != resource:
                continue
            for flux in itertools.product(range(-4, 5), repeat=2):
                row = (pump, *charged, *flux)
                if row_charge(row) == 0 and not any(row_gauss(row)):
                    rows.append(row)
    return sorted(rows)


def expected_dimension(resource):
    half = resource // 2
    return sum(math.comb(3, k) ** 2 for k in range(4) if half - k >= 0)


def relative_error(left, right) -> float:
    return float(np.linalg.norm(left - right) / max(1.0, float(np.linalg.norm(right))))


def spectrum(matrix):
    return np.sort(np.linalg.eigvalsh(matrix)).astype(np.float64)


def label_violations(rows, resource, charge, gauss):
    return sum(1 for row in rows
               if row_resource(row) != resource or row_charge(row) != charge
               or row_gauss(row) != gauss)


def calculate():
    checks, rows, arrays, audits = {}, [], {}, {}
    zero_count, positive_minima = 0, []
    for resource, scheduled in zip(RESOURCES, DIMENSIONS):
        prefix = f"fermion_R{resource}"
        basis = sector_basis(resource)
        size = len(basis)
        require(basis == sorted(basis) and len(set(basis)) == size,
                f"{prefix}: basis is not strictly ordered")
        require(size == expected_dimension(resource) == scheduled,
                f"{prefix}: dimension {size} disagrees with the frozen schedule")
        require(basis == sector_basis_by_constraint(resource),
                f"{prefix}: Gauss-law routes disagree")
        require(all(row_charge(row) == 0 and not any(row_gauss(row))
                    and row_resource(row) == resource for row in basis),
                f"{prefix}: basis is not exactly physical")

        # Two independent assemblies of the same section 60.1 Hamiltonian: the declared
        # monomials completed by transposition, and the section's terms with each adjoint
        # monomial written out by hand.
        diagonal = np.diag(np.array([diagonal_energy(row) for row in basis], dtype=np.float64))
        declared, declared_hits, declared_escaped = accumulate(basis, TERMS_DECLARED)
        hamiltonian_a = diagonal + declared + declared.T
        vertex, vertex_hits, vertex_escaped = accumulate(basis, VERTEX_COEFFICIENTS)
        hop, hop_hits, hop_escaped = accumulate(basis, HOP_COEFFICIENTS)
        explicit = vertex + hop
        hits = vertex_hits + hop_hits
        escaped = declared_escaped + vertex_escaped + hop_escaped
        hamiltonian_b = diagonal + explicit

        # Retained rectangular images and their Gram matrices.
        image_basis, image_matrix = build_image(basis, B_TERMS)
        b_gram = image_matrix.T @ image_matrix
        t_gram = np.zeros((size, size), dtype=np.float64)
        images = {"B": (image_basis, image_matrix)}
        for tag in GAUSS_SITES:
            sigma, site, terms = T_TERMS[tag]
            rows_tag, matrix_tag = build_image(basis, terms)
            images[tag] = (rows_tag, matrix_tag)
            t_gram += matrix_tag.T @ matrix_tag

        remainder = np.array([diagonal_remainder_value(row) for row in basis], dtype=np.float64)
        flux_diagonal = np.diag(np.array([0.5 * KAPPA * row_flux_square(row) for row in basis],
                                         dtype=np.float64))
        identity_left = hamiltonian_b
        identity_right = (0.5 * resource * np.eye(size) + flux_diagonal + b_gram
                          + HOPPING * t_gram + np.diag(remainder))
        bound_remainder = (hamiltonian_b - 0.5 * resource * np.eye(size) - flux_diagonal)
        eigenvalues = spectrum(hamiltonian_b)
        remainder_eigenvalues = spectrum(bound_remainder)
        frobenius = float(np.linalg.norm(hamiltonian_b))
        floor = -BOUND * max(1.0, frobenius)

        identity_error = relative_error(identity_left, identity_right)
        hermiticity_error = relative_error(hamiltonian_b, hamiltonian_b.T)
        route_error = relative_error(hamiltonian_a, hamiltonian_b)
        # The section 62.1 expansions are compared against the retained images, so the
        # Gram matrices are not merely restated as their own products.
        pump_diagonal = np.diag(np.array([row[0] for row in basis], dtype=np.float64))
        pair_diagonal = np.diag(np.array([row[2] * row[5] for row in basis], dtype=np.float64))
        b_gram_expansion = relative_error(
            b_gram, pump_diagonal + vertex + LAMBDA ** 2 * pair_diagonal)
        density = np.array([row[1] + row[4] + 2 * (row[2] + row[5]) + row[3] + row[6]
                            for row in basis], dtype=np.float64)
        t_gram_expansion = relative_error(t_gram, hop / HOPPING + np.diag(density))
        b_gram_floor = float(spectrum(b_gram)[0])
        t_gram_floor = float(spectrum(t_gram)[0])
        pauli_values = np.array([pauli_term(row) for row in basis], dtype=np.int64)

        checks[f"{prefix}_identity"] = identity_error <= BOUND
        checks[f"{prefix}_hermitian"] = hermiticity_error <= BOUND
        checks[f"{prefix}_explicit_adjoint"] = route_error <= BOUND
        checks[f"{prefix}_b_gram_expansion"] = b_gram_expansion <= BOUND
        checks[f"{prefix}_t_gram_expansion"] = t_gram_expansion <= BOUND
        checks[f"{prefix}_no_dropped_target"] = not escaped
        checks[f"{prefix}_b_gram_nonnegative"] = b_gram_floor >= floor
        checks[f"{prefix}_t_gram_nonnegative"] = t_gram_floor >= floor
        checks[f"{prefix}_bound_remainder_nonnegative"] = float(remainder_eigenvalues[0]) >= floor
        checks[f"{prefix}_energy_above_bound"] = float(eigenvalues[0]) >= 0.5 * resource - abs(floor)
        checks[f"{prefix}_pauli_term_in_01"] = bool(pauli_values.min() >= 0
                                                    and pauli_values.max() <= 1)
        checks[f"{prefix}_remainder_diagonal_nonnegative"] = float(remainder.min()) >= 0.0
        for tag in IMAGE_TAGS:
            rows_tag, matrix_tag = images[tag]
            if tag == "B":
                expected = (resource - 2, 0, (0, 0, 0))
            else:
                sigma, site, _ = T_TERMS[tag]
                gauss = tuple(sigma if index == site else 0 for index in range(3))
                expected = (resource - 1, -sigma, gauss)
            violations = label_violations(rows_tag, *expected)
            checks[f"{prefix}_{tag}_labels"] = violations == 0
            reached = (bool(np.all(np.any(matrix_tag != 0.0, axis=1)))
                       if rows_tag else True)
            checks[f"{prefix}_{tag}_basis_reached"] = reached
            checks[f"{prefix}_{tag}_shape"] = (matrix_tag.shape == (len(rows_tag), size)
                                               and rows_tag == sorted(rows_tag))
            if tag in GAUSS_SITES and rows_tag:
                # Anti-projection witness: every retained charged image row violates G = 0.
                checks[f"{prefix}_{tag}_unprojected"] = all(any(row_gauss(row))
                                                            for row in rows_tag)
        if resource == 0:
            checks[f"{prefix}_zero_sector_vanishes"] = (
                size == 1 and not np.any(hamiltonian_b) and not np.any(b_gram)
                and not np.any(t_gram) and not np.any(remainder)
                and all(not rows_tag for rows_tag, _ in images.values()))
        else:
            checks[f"{prefix}_norms_retained"] = (float(np.trace(b_gram)) > 0.0
                                                  and float(np.trace(t_gram)) > 0.0)

        arrays[f"{prefix}_basis"] = np.asarray(basis, dtype=np.int64).reshape(size, 9)
        arrays[f"{prefix}_H"] = hamiltonian_b
        arrays[f"{prefix}_B_gram"] = b_gram
        arrays[f"{prefix}_T_gram"] = t_gram
        arrays[f"{prefix}_diagonal_remainder"] = remainder
        arrays[f"{prefix}_bound_remainder"] = bound_remainder
        arrays[f"{prefix}_eigenvalues"] = eigenvalues
        arrays[f"{prefix}_remainder_eigenvalues"] = remainder_eigenvalues
        for tag in IMAGE_TAGS:
            rows_tag, matrix_tag = images[tag]
            arrays[f"{prefix}_{tag}_image_basis"] = np.asarray(
                rows_tag, dtype=np.int64).reshape(len(rows_tag), 9)
            arrays[f"{prefix}_{tag}_image"] = matrix_tag
            arrays[f"{prefix}_{tag}_gauss"] = np.asarray(
                [row_gauss(row) for row in rows_tag], dtype=np.int64).reshape(len(rows_tag), 3)
            arrays[f"{prefix}_{tag}_Q"] = np.asarray(
                [row_charge(row) for row in rows_tag], dtype=np.int64)
            arrays[f"{prefix}_{tag}_R"] = np.asarray(
                [row_resource(row) for row in rows_tag], dtype=np.int64)

        tag_dimensions = {f"{tag}_image_dimension": len(images[tag][0]) for tag in GAUSS_SITES}
        row = dict(
            stat="fermion", R=int(resource), dimension=int(size),
            minimum_energy=float(eigenvalues[0]), lower_bound=float(0.5 * resource),
            minimum_remainder_eigenvalue=float(remainder_eigenvalues[0]),
            identity_error=identity_error, hermiticity_error=hermiticity_error,
            explicit_adjoint_error=route_error,
            b_gram_expansion_error=b_gram_expansion, t_gram_expansion_error=t_gram_expansion,
            b_gram_minimum_eigenvalue=b_gram_floor,
            t_gram_minimum_eigenvalue=t_gram_floor,
            diagonal_remainder_minimum=float(remainder.min()),
            pauli_term_minimum=int(pauli_values.min()),
            pauli_term_maximum=int(pauli_values.max()),
            b_gram_trace=float(np.trace(b_gram)), t_gram_trace=float(np.trace(t_gram)),
            hamiltonian_frobenius_norm=frobenius,
            h_nonzero_off_diagonal_entries=int(np.count_nonzero(explicit)),
            h_declared_transitions=int(declared_hits), h_explicit_transitions=int(hits),
            h_dropped_targets=len(escaped),
            b_image_dimension=len(images["B"][0]),
            charged_image_physical_rows=sum(
                1 for tag in GAUSS_SITES for entry in images[tag][0] if not any(row_gauss(entry))),
        )
        row.update(tag_dimensions)
        rows.append(row)
        audits[prefix] = dict(
            dimension=int(size), scheduled_dimension=int(scheduled),
            expected_dimension=int(expected_dimension(resource)),
            maximum_abs_eigenvalue=float(np.max(np.abs(eigenvalues))),
            b_image_dimension=len(images["B"][0]),
            dropped_targets=len(escaped), dropped_target_examples=escaped[:8],
            basis_first=list(map(int, basis[0])), basis_last=list(map(int, basis[-1])),
        )
        audits[prefix].update(tag_dimensions)
        zero_count += int(np.sum(np.abs(eigenvalues) <= BOUND))
        if resource:
            positive_minima.append(float(eigenvalues[0]))

    require(len(rows) == 8, "the fermion schedule must emit exactly eight rows")
    checks["row_count_is_eight"] = len(rows) == 8
    checks["dimension_schedule"] = ([row["dimension"] for row in rows] == list(DIMENSIONS))
    checks["unique_zero_energy_state"] = zero_count == 1
    checks["gap_at_least_one"] = bool(positive_minima) and min(positive_minima) >= 1.0 - BOUND
    checks["all_lower_bounds_hold"] = all(row["minimum_energy"] >= row["lower_bound"] - BOUND
                                          for row in rows)
    checks["no_dropped_targets"] = all(row["h_dropped_targets"] == 0 for row in rows)
    checks["charged_images_never_physical"] = all(row["charged_image_physical_rows"] == 0
                                                 for row in rows)
    for key, value in arrays.items():
        if np.issubdtype(value.dtype, np.number) and not np.isfinite(value).all():
            raise ValueError(f"nonfinite array: {key}")
    return dict(checks=checks, rows=rows, source_audits=audits), arrays


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
    receipt = dict(schema=RESULT_SCHEMA, role=ROLE, verdict="INCONCLUSIVE", numeric_pass=False,
                   checks={}, rows=[], complete_physical_matter_formation=False)
    try:
        manifest, reviews = validate_manifest(args.manifest)
        receipt.update(manifest_sha256=digest(args.manifest),
                       section_sha256=manifest["section"]["sha256"],
                       parent_section_sha256=manifest["parent_section"]["sha256"],
                       source_bindings=manifest["sources"],
                       mathematical_reviews=reviews)
        # Every guard above has passed before any scientific row or array is produced.
        result, arrays = calculate()
        receipt.update(result)
        json.dumps(receipt, allow_nan=False)
        np.savez_compressed(args.output / "arrays.npz", **arrays)
        passed = all(value is True for value in result["checks"].values())
        receipt.update(numeric_pass=passed, verdict=VERDICT if passed else "INCONCLUSIVE",
                       arrays_sha256=hashlib.sha256(
                           (args.output / "arrays.npz").read_bytes()).hexdigest(),
                       scope=("Supplied three-site comparison Hamiltonian with Pauli-limited "
                              "charged modes, unbounded neutral pump and integer rotors; the "
                              "lower bound is a whole-Fock-space statement about this operator "
                              "only and physical matter formation remains unresolved."),
                       complete_physical_matter_formation=False)
    except Exception as exc:
        receipt.update(numeric_pass=False, verdict="INCONCLUSIVE",
                       error=f"{type(exc).__name__}: {exc}")
    (args.output / "result.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in
                      ("verdict", "numeric_pass", "error", "complete_physical_matter_formation")}))
    return 0 if receipt["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
