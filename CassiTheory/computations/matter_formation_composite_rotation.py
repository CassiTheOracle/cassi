#!/usr/bin/env python3
"""Exact charge-lattice pairing and SU(2) whole-composite rotation witnesses for section 54.

Run from the repository root after sealing the source manifest:
python computations/matter_formation_composite_rotation.py --manifest PATH --output FRESH_DIR

This qualifies rotation characters on an Abelian point-dyon comparison lattice with a
minimal-representation witness. It performs no field evolution, selects no theta term or
topological state, and supplies no formation, exchange-statistics, or particle-spin
assignment. The 2pi axis check is made on the endpoint tensor product tensored with the
relative band, so the expected scalar is eta(g1)*eta(g2)*(-1)^D12 = eta(g1+g2); the
endpoint-only 2pi rotation equals eta(g1)*eta(g2); relative motion supplies the remaining factor.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = "## 54. Working notes: whole-composite magnetic rotation"
MANIFEST_SCHEMA = "matter-formation-composite-rotation-manifest-v1"
SCHEMA = "matter-formation-composite-rotation-v1"
SOURCES = {
    "computations/matter_formation_composite_rotation.py",
    "foundations/particle-stationary-action-closure.md",
    "foundations/nonabelian-magnetic-core-boundary.md",
}
REFINEMENTS = ((0, 0), (0, 1), (1, 0), (1, 1))
PAIR_LATTICE = [(n, nu) for n in (-2, -1, 0, 1, 2) for nu in (-2, -1, 0, 1, 2)]
TRIPLE_LATTICE = [(n, nu) for n in (-1, 0, 1) for nu in (-1, 0, 1)]
MATRIX_PAIRS = (
    ((1, 0), (0, 1)),
    ((1, 1), (0, -1)),
    ((1, 1), (-1, -1)),
    ((0, 1), (0, -1)),
    ((1, 0), (0, 0)),
    ((1, 1), (1, -1)),
)
K_VALUES = (0, 1, 2)
AXIS = np.array([1.0, 2.0, 3.0]) / np.sqrt(14.0)
TOLERANCE = 1e-10
PAIR_CASE_COUNT = len(REFINEMENTS) * len(PAIR_LATTICE) ** 2
TRIPLE_CASE_COUNT = len(REFINEMENTS) * len(TRIPLE_LATTICE) ** 3
MATRIX_CASE_COUNT = len(MATRIX_PAIRS) * len(REFINEMENTS) * len(K_VALUES)


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def section_bytes(path: Path) -> bytes:
    lines = canonical_bytes(path).decode("utf-8").splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.rstrip() == HEADING]
    if len(matches) != 1:
        raise ValueError("section 54 must occur exactly once")
    first = matches[0]
    last = next((i for i in range(first + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return ("".join(lines[first:last]).rstrip() + "\n").encode("utf-8")


def validate_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    record = manifest["section"]
    if record["path"] != REPORT or record["heading"] != HEADING:
        raise ValueError("unexpected notebook section")
    frozen = canonical_bytes(path.parent / record["snapshot"])
    if hashlib.sha256(frozen).hexdigest() != record["sha256"] or section_bytes(ROOT / REPORT) != frozen:
        raise ValueError("frozen or current section mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {item["path"] for item in sources} != SOURCES:
        raise ValueError("incomplete source bindings")
    for item in sources:
        if sha(ROOT / item["path"]) != item["sha256"] or sha(path.parent / item["snapshot"]) != item["sha256"]:
            raise ValueError(f"source mismatch: {item['path']}")
    review = manifest["mathematical_review"]
    if review.get("accepted") is not True or sha(path.parent / review["snapshot"]) != review["sha256"]:
        raise ValueError("mathematical review is not qualified")
    return manifest


def fused_degree(left: tuple[int, int], right: tuple[int, int]) -> int:
    return left[0] * right[1] - right[0] * left[1]


def parity_sign(exponent: int) -> int:
    return -1 if exponent % 2 else 1


def eta(n: int, nu: int, be: int, bm: int) -> int:
    return parity_sign(n * nu + be * n + bm * nu)


def exact_identities() -> tuple[dict[str, bool], dict[str, str]]:
    n1, n2, n3, nu1, nu2, nu3, be, bm, n_total = sp.symbols(
        "n1 n2 n3 nu1 nu2 nu3 be bm n_total", integer=True)
    alpha = sp.Symbol("alpha", real=True)

    def exponent(n: sp.Expr, nu: sp.Expr) -> sp.Expr:
        return n * nu + be * n + bm * nu

    d12 = n1 * nu2 - n2 * nu1
    d13 = n1 * nu3 - n3 * nu1
    d23 = n2 * nu3 - n3 * nu2
    pairing_gap = sp.expand(exponent(n1 + n2, nu1 + nu2) - exponent(n1, nu1) - exponent(n2, nu2) - d12)
    three_body_gap = sp.expand(
        exponent(n1 + n2 + n3, nu1 + nu2 + nu3)
        - exponent(n1, nu1) - exponent(n2, nu2) - exponent(n3, nu3) - (d12 + d13 + d23))
    grouping_left = sp.expand(d12 + (n1 + n2) * nu3 - n3 * (nu1 + nu2))
    grouping_right = sp.expand(d23 + n1 * (nu2 + nu3) - (n2 + n3) * nu1)
    sheared_d = sp.expand((n1 + alpha * nu1) * nu2 - (n2 + alpha * nu2) * nu1)
    neutral_gap = sp.expand(exponent(n_total, sp.Integer(0)) - be * n_total)
    band_parity = all((abs(fused_degree(*pair)) + 2 * k) % 2 == fused_degree(*pair) % 2
                      for pair in MATRIX_PAIRS for k in K_VALUES)
    checks = {
        "pairing_exponent_is_relative_plus_even": sp.simplify(pairing_gap - 2 * n2 * nu1) == 0,
        "pairing_associativity_groups_agree": sp.simplify(grouping_left - grouping_right) == 0,
        "three_body_exponent_even_offset": sp.simplify(three_body_gap - 2 * (n2 * nu1 + n3 * nu1 + n3 * nu2)) == 0,
        "shear_leaves_relative_degree_invariant": sp.simplify(sheared_d - d12) == 0,
        "neutral_total_sign_law": sp.simplify(neutral_gap) == 0,
        "relative_band_two_pi_parity": band_parity,
    }
    witnesses = {
        "pairing_exponent_gap": str(sp.simplify(pairing_gap)),
        "three_body_exponent_gap": str(sp.simplify(three_body_gap)),
        "grouping_exponent": str(sp.simplify(grouping_left)),
        "sheared_relative_degree": str(sp.simplify(sheared_d)),
        "neutral_exponent": str(sp.simplify(exponent(n_total, sp.Integer(0)))),
    }
    return checks, witnesses


def critical_examples() -> bool:
    first, second = (1, 1), (0, -1)
    d = fused_degree(first, second)
    fused = eta(first[0] + second[0], first[1] + second[1], 0, 0)
    product = eta(*first, 0, 0) * eta(*second, 0, 0)
    monopole, other = (1, 0), (0, 1)
    opposite_a, opposite_b = (1, 1), (-1, -1)
    return (eta(*first, 0, 0) == -1 and eta(*second, 0, 0) == 1 and d == -1
            and fused == 1 and product == -1 and fused == product * parity_sign(d)
            and eta(monopole[0] + other[0], monopole[1] + other[1], 0, 0) == -1
            and (monopole[1] + other[1]) != 0
            and (opposite_a[0] + opposite_b[0], opposite_a[1] + opposite_b[1]) == (0, 0)
            and eta(0, 0, 0, 0) == 1
            and parity_sign(fused_degree(opposite_a, opposite_b)) == 1)


def sector_controls() -> tuple[dict[str, bool], list[dict[str, Any]]]:
    rows = []
    for be, bm in REFINEMENTS:
        electric = eta(1, 0, be, bm)
        neutral = eta(0, 0, be, bm)
        rows.append({"be": be, "bm": bm, "pure_electric_character": electric,
                     "charge_only_neutral_character": neutral,
                     "supplied_neutral_fermion_character": -neutral})
    checks = {
        "pure_electric_character_tracks_be": all(
            row["pure_electric_character"] == (1 if row["be"] == 0 else -1) for row in rows),
        "neutral_fermion_requires_additional_sector": all(
            row["charge_only_neutral_character"] == 1
            and row["supplied_neutral_fermion_character"] == -1 for row in rows),
    }
    return checks, rows


def pair_sweep() -> tuple[dict[str, bool], list[dict[str, Any]]]:
    rows = []
    for be, bm in REFINEMENTS:
        for n1, nu1 in PAIR_LATTICE:
            for n2, nu2 in PAIR_LATTICE:
                d12 = fused_degree((n1, nu1), (n2, nu2))
                eta1 = eta(n1, nu1, be, bm)
                eta2 = eta(n2, nu2, be, bm)
                eta_sum = eta(n1 + n2, nu1 + nu2, be, bm)
                relative = parity_sign(d12)
                expected = eta1 * eta2 * relative
                rows.append({"be": be, "bm": bm, "n1": n1, "nu1": nu1, "n2": n2, "nu2": nu2,
                             "d12": d12, "eta1": eta1, "eta2": eta2, "eta_sum": eta_sum,
                             "relative_sign": relative, "pairing_expected": expected,
                             "pairing_ok": bool(eta_sum == expected)})
    checks = {
        "pair_schedule_complete": len(rows) == PAIR_CASE_COUNT,
        "pair_exponent_identity": all(row["pairing_ok"] for row in rows),
    }
    return checks, rows


def triple_sweep() -> tuple[dict[str, bool], int]:
    count = 0
    holds = True
    neutral_holds = True
    for be, bm in REFINEMENTS:
        for g1 in TRIPLE_LATTICE:
            for g2 in TRIPLE_LATTICE:
                for g3 in TRIPLE_LATTICE:
                    count += 1
                    n_total = g1[0] + g2[0] + g3[0]
                    nu_total = g1[1] + g2[1] + g3[1]
                    d_sum = fused_degree(g1, g2) + fused_degree(g1, g3) + fused_degree(g2, g3)
                    expected = eta(*g1, be, bm) * eta(*g2, be, bm) * eta(*g3, be, bm) * parity_sign(d_sum)
                    holds = holds and eta(n_total, nu_total, be, bm) == expected
                    if nu_total == 0:
                        neutral_holds = neutral_holds and eta(n_total, 0, be, bm) == parity_sign(be * n_total)
    checks = {
        "triple_schedule_complete": count == TRIPLE_CASE_COUNT,
        "triple_exponent_identity": bool(holds),
        "triple_neutral_sign_law": bool(neutral_holds),
    }
    return checks, count


def spin_generators(twice_j: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dimension = twice_j + 1
    j = twice_j / 2.0
    magnetic = np.arange(-twice_j, twice_j + 1, 2, dtype=float) / 2.0
    raising = np.zeros((dimension, dimension))
    for index in range(dimension - 1):
        m = magnetic[index]
        raising[index + 1, index] = np.sqrt(j * (j + 1.0) - m * (m + 1.0))
    jx = 0.5 * (raising + raising.T)
    jy = -0.5j * (raising - raising.T)
    jz = np.diag(magnetic)
    return jx.astype(complex), jy, jz.astype(complex)


def commutator_error(generators: tuple[np.ndarray, ...]) -> float:
    jx, jy, jz = generators
    worst = 0.0
    for left, right, target in ((jx, jy, jz), (jy, jz, jx), (jz, jx, jy)):
        reference = 1j * target
        difference = left @ right - right @ left - reference
        scale = max(1.0, float(np.linalg.norm(reference)))
        worst = max(worst, float(np.linalg.norm(difference)) / scale)
    return worst


def two_pi_rotation(axis_generator: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh((axis_generator + axis_generator.conjugate().T) / 2)
    return (vectors * np.exp(-2j * np.pi * values)) @ vectors.conjugate().T


def normalized_error(actual: np.ndarray, reference: np.ndarray) -> float:
    scale = max(1.0, float(np.linalg.norm(reference)))
    return float(np.linalg.norm(actual - reference)) / scale


def coupled_range(twice_a: int, twice_b: int) -> range:
    return range(abs(twice_a - twice_b), twice_a + twice_b + 1, 2)


def casimir_multiplicities(twice_j1: int, twice_j2: int, twice_ell: int) -> dict[int, int]:
    counts: dict[int, int] = {}
    for j12 in coupled_range(twice_j1, twice_j2):
        for total in coupled_range(j12, twice_ell):
            counts[total] = counts.get(total, 0) + total + 1
    return counts


def axis_component(generators: tuple[np.ndarray, ...]) -> np.ndarray:
    return (AXIS[0] * generators[0] + AXIS[1] * generators[1] + AXIS[2] * generators[2]).astype(complex)


def matrix_sweep() -> tuple[dict[str, bool], list[dict[str, Any]], dict[str, np.ndarray]]:
    rows: list[dict[str, Any]] = []
    arrays: dict[str, np.ndarray] = {}
    errors: list[float] = []
    for case_index in range(MATRIX_CASE_COUNT):
        pair_index = case_index // (len(REFINEMENTS) * len(K_VALUES))
        remainder = case_index % (len(REFINEMENTS) * len(K_VALUES))
        (be, bm) = REFINEMENTS[remainder // len(K_VALUES)]
        k = K_VALUES[remainder % len(K_VALUES)]
        g1, g2 = MATRIX_PAIRS[pair_index]
        d = fused_degree(g1, g2)
        eta1 = eta(*g1, be, bm)
        eta2 = eta(*g2, be, bm)
        eta_total = eta(g1[0] + g2[0], g1[1] + g2[1], be, bm)
        lift = parity_sign(d)
        twice_j1 = 0 if eta1 == 1 else 1
        twice_j2 = 0 if eta2 == 1 else 1
        twice_ell = abs(d) + 2 * k
        endpoint_generators = spin_generators(twice_j1)
        partner_generators = spin_generators(twice_j2)
        relative_generators = spin_generators(twice_ell)
        identity1 = np.eye(twice_j1 + 1, dtype=complex)
        identity2 = np.eye(twice_j2 + 1, dtype=complex)
        identity3 = np.eye(twice_ell + 1, dtype=complex)
        identity12 = np.eye((twice_j1 + 1) * (twice_j2 + 1), dtype=complex)
        dimension = (twice_j1 + 1) * (twice_j2 + 1) * (twice_ell + 1)
        endpoint: list[np.ndarray] = []
        composite: list[np.ndarray] = []
        for axis in range(3):
            term = np.kron(endpoint_generators[axis], identity2) + np.kron(identity1, partner_generators[axis])
            endpoint.append(term)
            composite.append(np.kron(term, identity3) + np.kron(identity12, relative_generators[axis]))
        j_squared = sum((generator @ generator for generator in composite), np.zeros((dimension, dimension), dtype=complex))
        composite_axis = axis_component(tuple(composite))
        endpoint_axis = axis_component(tuple(endpoint))
        relative_axis = axis_component(relative_generators)
        composite_rotation = two_pi_rotation(composite_axis)
        endpoint_rotation = two_pi_rotation(endpoint_axis)
        relative_rotation = two_pi_rotation(relative_axis)
        composite_error = normalized_error(composite_rotation, eta_total * np.eye(dimension, dtype=complex))
        endpoint_error = normalized_error(endpoint_rotation,
                                          eta1 * eta2 * np.eye(endpoint_axis.shape[0], dtype=complex))
        relative_error = normalized_error(relative_rotation, lift * np.eye(twice_ell + 1, dtype=complex))
        tensor_commutator = commutator_error(tuple(endpoint))
        relative_commutator = commutator_error(relative_generators)
        composite_commutator = commutator_error(tuple(composite))
        measured = np.linalg.eigvalsh(j_squared)
        expected_counts = casimir_multiplicities(twice_j1, twice_j2, twice_ell)
        expected_levels = sorted(level * (level + 2) / 4.0
                                 for level, multiplicity in expected_counts.items()
                                 for _ in range(multiplicity))
        spectrum_reference = np.array(expected_levels, dtype=float)
        if measured.shape != spectrum_reference.shape:
            raise ValueError("Clebsch-Gordan state count differs from tensor dimension")
        spectrum_error = normalized_error(np.sort(measured), spectrum_reference)
        measured_multiplicities: dict[int, int] = {}
        for value in measured:
            twice = int(round(-1.0 + float(np.sqrt(1.0 + 4.0 * float(value)))))
            measured_multiplicities[twice] = measured_multiplicities.get(twice, 0) + 1
        multiplicities_match = measured_multiplicities == expected_counts
        case_errors = [composite_error, endpoint_error, relative_error, tensor_commutator,
                       relative_commutator, composite_commutator, spectrum_error]
        finite = all(np.isfinite(value) for value in case_errors) and bool(
            np.all(np.isfinite(j_squared)) and np.all(np.isfinite(composite_axis))
            and np.all(np.isfinite(measured)) and np.all(np.isfinite(composite_rotation)))
        within = finite and all(value <= TOLERANCE for value in case_errors)
        rows.append({"case": case_index, "pair_index": pair_index, "n1": g1[0], "nu1": g1[1],
                     "n2": g2[0], "nu2": g2[1], "be": be, "bm": bm, "k": k, "d12": d,
                     "eta1": eta1, "eta2": eta2, "eta_total": eta_total,
                     "expected_relative_sign": lift, "twice_j1": twice_j1, "twice_j2": twice_j2,
                     "twice_ell": twice_ell, "dimension": dimension,
                     "j1": twice_j1 / 2, "j2": twice_j2 / 2, "ell": twice_ell / 2,
                     "composite_rotation_error": composite_error,
                     "endpoint_rotation_error": endpoint_error,
                     "relative_rotation_error": relative_error,
                     "tensor_commutator_error": tensor_commutator,
                     "relative_commutator_error": relative_commutator,
                     "composite_commutator_error": composite_commutator,
                     "spectrum_error": spectrum_error,
                     "measured_twice_j_multiplicities": {str(key): int(value)
                                                         for key, value in sorted(measured_multiplicities.items())},
                     "expected_twice_j_multiplicities": {str(key): int(value)
                                                         for key, value in sorted(expected_counts.items())},
                     "casimir_multiplicities_match": bool(multiplicities_match), "all_finite": finite,
                     "within_tolerance": bool(within),
                     "arrays": {"j2": f"{case_index:02d}_j2", "axis_generator": f"{case_index:02d}_axis_generator",
                                "spectrum": f"{case_index:02d}_spectrum",
                                "expected_spectrum": f"{case_index:02d}_expected_spectrum",
                                "two_pi": f"{case_index:02d}_two_pi"}})
        arrays[f"{case_index:02d}_j2"] = j_squared
        arrays[f"{case_index:02d}_axis_generator"] = composite_axis
        arrays[f"{case_index:02d}_spectrum"] = np.sort(np.real(measured))
        arrays[f"{case_index:02d}_expected_spectrum"] = spectrum_reference
        arrays[f"{case_index:02d}_two_pi"] = composite_rotation
        errors.extend(case_errors)
    arrays["normalized_errors"] = np.array(errors, dtype=float)
    checks = {
        "matrix_schedule_complete": len(rows) == MATRIX_CASE_COUNT,
        "tensor_generators_su2_commutators": all(row["tensor_commutator_error"] <= TOLERANCE for row in rows),
        "relative_generators_su2_commutators": all(row["relative_commutator_error"] <= TOLERANCE for row in rows),
        "composite_generators_su2_commutators": all(row["composite_commutator_error"] <= TOLERANCE for row in rows),
        "j2_casimir_spectra_match": all(row["casimir_multiplicities_match"]
                                        and row["spectrum_error"] <= TOLERANCE for row in rows),
        "two_pi_composite_matches_total_eta": all(row["composite_rotation_error"] <= TOLERANCE for row in rows),
        "two_pi_endpoint_matches_product_sign": all(row["endpoint_rotation_error"] <= TOLERANCE for row in rows),
        "two_pi_relative_matches_lifted_sign": all(row["relative_rotation_error"] <= TOLERANCE for row in rows),
        "matrix_discrepancies_within_tolerance": all(row["within_tolerance"] for row in rows),
        "matrix_values_finite": all(row["all_finite"] for row in rows),
    }
    return checks, rows, arrays


def calculate() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    identity_checks, witnesses = exact_identities()
    pair_checks, pair_rows = pair_sweep()
    triple_checks, triple_count = triple_sweep()
    matrix_checks, matrix_rows, arrays = matrix_sweep()
    control_checks, control_rows = sector_controls()
    checks = {**identity_checks, **pair_checks, **triple_checks, **matrix_checks,
              **control_checks, "critical_examples_exact": critical_examples()}
    checks = {name: bool(value) for name, value in checks.items()}
    passed = all(checks.values())
    result = {"schema": SCHEMA, "numeric_pass": passed,
              "verdict": "SUPPORTS-conditional whole-composite rotation law" if passed else "INCONCLUSIVE",
              "checks": checks, "exact_identities": witnesses,
              "pair_rows": pair_rows, "triple_count": triple_count, "matrix_rows": matrix_rows,
              "sector_controls": control_rows,
              "scope": "Conditional charge-lattice fusion parity and minimal SU(2) witness spectra on the "
                       "point-dyon comparison lattice; not an observed electromagnetic assignment, quantum "
                       "state, exchange-statistics, radial bound state, or formation result.",
              "complete_physical_matter_formation": False}
    return result, arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    created = False
    try:
        output.mkdir(parents=True, exist_ok=False)
        created = True
        validate_manifest(args.manifest.resolve())
        result, arrays = calculate()
        handle = io.BytesIO()
        np.savez_compressed(handle, **arrays)
        payload = handle.getvalue()
        with (output / "arrays.npz").open("xb") as stream:
            stream.write(payload)
        result["arrays_sha256"] = hashlib.sha256(payload).hexdigest()
        result.update(manifest_sha256=sha(args.manifest.resolve()), source_sha256=sha(SELF))
    except Exception as exc:
        result = {"schema": SCHEMA, "numeric_pass": False, "verdict": "INCONCLUSIVE",
                  "error": f"{type(exc).__name__}: {exc}", "complete_physical_matter_formation": False}
    try:
        receipt_text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        result = {"schema": SCHEMA, "numeric_pass": False, "verdict": "INCONCLUSIVE",
                  "error": f"receipt {type(exc).__name__}: {exc}", "complete_physical_matter_formation": False}
        receipt_text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if created:
        try:
            with (output / "result.json").open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(receipt_text)
        except OSError as exc:
            result = {"schema": SCHEMA, "numeric_pass": False, "verdict": "INCONCLUSIVE",
                      "error": f"receipt {type(exc).__name__}: {exc}", "complete_physical_matter_formation": False}
    print(json.dumps({"verdict": result["verdict"], "numeric_pass": result["numeric_pass"],
                      "checks": len(result.get("checks", {})), "pair_rows": len(result.get("pair_rows", [])),
                      "matrix_rows": len(result.get("matrix_rows", [])), "errors": result.get("error"),
                      "complete_physical_matter_formation": False}, allow_nan=False), flush=True)
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
