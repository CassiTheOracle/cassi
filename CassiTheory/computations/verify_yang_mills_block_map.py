#!/usr/bin/env python3
"""Verify the fixed SU(2) cylindrical block-map identities and obstruction.

Run from CassiTheory with --output pointing to a fresh immutable receipt.
The finite controls do not construct an interacting block map or continuum
Yang–Mills theory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sympy as sp

import verify_yang_mills_loop_gap as receipt_checks

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/yang-mills-block-map-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_block_map/verification.json"
SEED = 20260909
TOLERANCE = 1e-12
ELECTRIC_TOLERANCE = 1e-11
PATH_WORDS = {
    2: (1, 1),
    3: (1, -1, 1),
    4: (-1, 1, -1, 1),
}
B_VALUES = (2, 3, 4)
G_VALUES = (2.0, 1.0, 0.5)
A_VALUES = (1.0, 0.5, 0.25)
check = receipt_checks.check
exact = receipt_checks.exact

I2 = np.eye(2, dtype=complex)
SIGMA = (
    np.array(((0, 1), (1, 0)), dtype=complex),
    np.array(((0, -1j), (1j, 0)), dtype=complex),
    np.array(((1, 0), (0, -1)), dtype=complex),
)
FUNDAMENTAL_GENERATORS = tuple(0.5j * sigma for sigma in SIGMA)


def levi_civita(i: int, j: int, k: int) -> int:
    if len({i, j, k}) < 3:
        return 0
    return 1 if (i, j, k) in ((0, 1, 2), (1, 2, 0), (2, 0, 1)) else -1


ADJOINT_GENERATORS = tuple(
    np.array([[levi_civita(axis, row, column) for column in range(3)]
              for row in range(3)], dtype=float)
    for axis in range(3)
)
Q8 = tuple(
    sign * matrix
    for matrix in (I2, *(1j * sigma for sigma in SIGMA))
    for sign in (1, -1)
)


def su2_from_quaternion(quaternion: np.ndarray) -> np.ndarray:
    quaternion = np.asarray(quaternion, dtype=float)
    quaternion = quaternion / np.linalg.norm(quaternion)
    return quaternion[0] * I2 + 1j * sum(
        quaternion[index + 1] * SIGMA[index] for index in range(3))


def random_su2(rng: np.random.Generator) -> np.ndarray:
    return su2_from_quaternion(rng.normal(size=4))


def matrix_error(actual: np.ndarray, expected: np.ndarray) -> float:
    return float(np.max(np.abs(np.asarray(actual) - np.asarray(expected))))


def relative_error(actual: float, expected: float) -> float:
    scale = max(abs(expected), np.finfo(float).tiny)
    return abs(actual - expected) / scale


def product(matrices, size: int | None = None):
    matrices = tuple(matrices)
    if not matrices:
        if size is None:
            raise ValueError("An empty product requires a size")
        return np.eye(size)
    result = np.eye(matrices[0].shape[0], dtype=matrices[0].dtype)
    for matrix in matrices:
        result = result @ matrix
    return result


def traversed_factor(edge: np.ndarray, orientation: int) -> np.ndarray:
    return edge if orientation == 1 else edge.conj().T


def path_product(edges, orientations):
    return product(traversed_factor(edge, orientation)
                   for edge, orientation in zip(edges, orientations, strict=True))


def adjoint_representation(group: np.ndarray) -> np.ndarray:
    represented = np.empty((3, 3), dtype=float)
    for row, sigma_row in enumerate(SIGMA):
        for column, sigma_column in enumerate(SIGMA):
            represented[row, column] = float(
                (0.5 * np.trace(sigma_row @ group @ sigma_column @ group.conj().T)).real)
    return represented


def gauge_transformed_path(edges, orientations, gauges):
    transformed = []
    for index, (edge, orientation) in enumerate(zip(edges, orientations, strict=True)):
        if orientation == 1:
            transformed.append(gauges[index] @ edge @ gauges[index + 1].conj().T)
        else:
            transformed.append(gauges[index + 1] @ edge @ gauges[index].conj().T)
    return transformed


def path_controls(result, rng):
    result["path_rows"] = []
    for length, orientations in PATH_WORDS.items():
        traversed = [random_su2(rng) for _ in range(length)]
        edges = [factor if orientation == 1 else factor.conj().T
                 for factor, orientation in zip(traversed, orientations, strict=True)]
        direct = product(traversed)
        reconstructed = path_product(edges, orientations)
        gauges = [random_su2(rng) for _ in range(length + 1)]
        transformed = gauge_transformed_path(edges, orientations, gauges)
        covariant = path_product(transformed, orientations)
        expected_covariant = gauges[0] @ direct @ gauges[-1].conj().T

        internal_gauges = [I2.copy(), *(random_su2(rng) for _ in range(length - 1)), I2.copy()]
        internally_transformed = gauge_transformed_path(edges, orientations, internal_gauges)
        internal_product = path_product(internally_transformed, orientations)
        inverse_error = matrix_error(path_product(
            list(reversed(edges)), tuple(-orientation for orientation in reversed(orientations))),
            direct.conj().T)
        errors = {
            "path_reconstruction": matrix_error(reconstructed, direct),
            "endpoint_covariance": matrix_error(covariant, expected_covariant),
            "internal_cancellation": matrix_error(internal_product, direct),
            "inverse_path": inverse_error,
        }
        result["path_rows"].append({
            "length": length,
            "orientations": list(orientations),
            "errors": errors,
        })
        check(result, f"path and gauge identities b={length}",
              max(errors.values()) < TOLERANCE, errors)
    check(result, "complete path-word schedule",
          [row["length"] for row in result["path_rows"]] == list(B_VALUES),
          [row["length"] for row in result["path_rows"]])


def represented_casimir_character(edges, orientations, representation, generators):
    represented_edges = [representation(edge) for edge in edges]
    factors = [traversed_factor(edge, orientation)
               for edge, orientation in zip(represented_edges, orientations, strict=True)]
    character = np.trace(product(factors))
    total_second = 0.0j
    individual = []
    for index, orientation in enumerate(orientations):
        edge_second = 0.0j
        for generator in generators:
            replacement = (generator @ generator @ factors[index]
                           if orientation == 1
                           else factors[index] @ generator @ generator)
            modified = list(factors)
            modified[index] = replacement
            edge_second += np.trace(product(modified))
        individual.append(-edge_second)
        total_second += edge_second
    return character, -total_second, individual


def electric_controls(result, rng):
    result["electric_rows"] = []
    representations = (
        ("fundamental", lambda group: group, FUNDAMENTAL_GENERATORS, 0.75),
        ("adjoint", adjoint_representation, ADJOINT_GENERATORS, 2.0),
    )
    for length, orientations in PATH_WORDS.items():
        traversed = [random_su2(rng) for _ in range(length)]
        edges = [factor if orientation == 1 else factor.conj().T
                 for factor, orientation in zip(traversed, orientations, strict=True)]
        for name, representation, generators, casimir in representations:
            character, compressed, individual = represented_casimir_character(
                edges, orientations, representation, generators)
            expected = length * casimir * character
            individual_errors = [abs(value - casimir * character) for value in individual]
            generator_casimir = -np.add.reduce(
                [generator @ generator for generator in generators])
            errors = {
                "compressed": float(abs(compressed - expected)),
                "individual_max": float(max(individual_errors)),
                "generator_casimir": matrix_error(
                    generator_casimir,
                    casimir * np.eye(representation(I2).shape[0])),
            }
            result["electric_rows"].append({
                "length": length,
                "orientations": list(orientations),
                "representation": name,
                "casimir": casimir,
                "character_real": float(np.real(character)),
                "character_imaginary": float(np.imag(character)),
                "errors": errors,
            })
            check(result, f"electric compression {name} b={length}",
                  max(errors.values()) < ELECTRIC_TOLERANCE, errors)
    expected = {(length, name) for length in B_VALUES for name in ("fundamental", "adjoint")}
    actual = [(row["length"], row["representation"]) for row in result["electric_rows"]]
    check(result, "complete unique electric schedule",
          len(actual) == len(set(actual)) and set(actual) == expected,
          {"rows": len(actual), "expected": len(expected)})


def horizontal(i, j):
    return ("h", i, j)


def vertical(i, j):
    return ("v", i, j)


def edge_endpoints(edge):
    direction, i, j = edge
    if direction == "h":
        return (i, j), (i + 1, j)
    return (i, j), (i, j + 1)


def loop_product(edges, terms):
    return product(traversed_factor(edges[edge], orientation) for edge, orientation in terms)


def plaquette_terms(i, j):
    return (
        (horizontal(i, j), 1),
        (vertical(i + 1, j), 1),
        (horizontal(i, j + 1), -1),
        (vertical(i, j), -1),
    )


def character(edges, terms):
    return float(np.trace(loop_product(edges, terms)).real)


def replaced_character(edges, terms, replaced_edge, replacement):
    modified = dict(edges)
    modified[replaced_edge] = replacement
    return character(modified, terms)


def refined_block_controls(result, rng):
    fine_edges = {
        **{horizontal(i, j): random_su2(rng) for j in range(3) for i in range(2)},
        **{vertical(i, j): random_su2(rng) for i in range(3) for j in range(2)},
    }
    coarse_paths = (
        ((horizontal(0, 0), 1), (horizontal(1, 0), 1)),
        ((vertical(2, 0), 1), (vertical(2, 1), 1)),
        ((horizontal(1, 2), -1), (horizontal(0, 2), -1)),
        ((vertical(0, 1), -1), (vertical(0, 0), -1)),
    )
    plaquettes = tuple(plaquette_terms(i, j) for j in range(2) for i in range(2))
    interior = {horizontal(0, 1), horizontal(1, 1), vertical(1, 0), vertical(1, 1)}
    witnesses = []
    conditional_rows = []
    for index, terms in enumerate(plaquettes):
        witness = next(edge for edge, _ in terms if edge in interior)
        witnesses.append(witness)
        values = np.array([replaced_character(fine_edges, terms, witness, sample) for sample in Q8])
        conditional_rows.append({
            "plaquette": index,
            "witness": list(witness),
            "first_moment": float(values.mean()),
            "second_moment": float(np.mean(values * values)),
        })

    gram = np.zeros((4, 4), dtype=float)
    for first, first_terms in enumerate(plaquettes):
        first_keys = {edge for edge, _ in first_terms}
        for second, second_terms in enumerate(plaquettes):
            second_keys = {edge for edge, _ in second_terms}
            witness = sorted(first_keys if first == second else first_keys - second_keys)[0]
            products = []
            for sample in Q8:
                first_value = replaced_character(fine_edges, first_terms, witness, sample)
                second_value = replaced_character(fine_edges, second_terms, witness, sample)
                products.append(first_value * second_value)
            gram[first, second] = float(np.mean(products))

    coarse_holonomies = [loop_product(fine_edges, path) for path in coarse_paths]
    coarse_outer = product(coarse_holonomies)
    outer_terms = tuple(term for path in coarse_paths for term in path)
    fine_outer = loop_product(fine_edges, outer_terms)

    gauges = {(i, j): random_su2(rng) for i in range(3) for j in range(3)}
    transformed_edges = {}
    for edge, group in fine_edges.items():
        source, target = edge_endpoints(edge)
        transformed_edges[edge] = gauges[source] @ group @ gauges[target].conj().T
    gauge_errors = [abs(character(transformed_edges, terms) - character(fine_edges, terms))
                    for terms in plaquettes]

    first_moment_error = max(abs(row["first_moment"]) for row in conditional_rows)
    second_moment_error = max(abs(row["second_moment"] - 1.0) for row in conditional_rows)
    gram_error = matrix_error(gram, np.eye(4))
    outer_matrix_error = matrix_error(coarse_outer, fine_outer)
    outer_character_error = abs(float(np.trace(coarse_outer).real - np.trace(fine_outer).real))
    leakage = float(np.sqrt(np.ones(4) @ gram @ np.ones(4)))
    errors = {
        "conditional_first_moment": first_moment_error,
        "conditional_second_moment": second_moment_error,
        "plaquette_gram": gram_error,
        "outer_matrix": outer_matrix_error,
        "outer_character": outer_character_error,
        "gauge_invariance": float(max(gauge_errors)),
        "leakage_coefficient": abs(leakage - 2.0),
    }
    result["refined_block"] = {
        "vertices": 9,
        "links": len(fine_edges),
        "coarse_paths": [[[*edge, orientation] for edge, orientation in path]
                         for path in coarse_paths],
        "interior_links": [list(edge) for edge in sorted(interior)],
        "conditional_rows": conditional_rows,
        "plaquette_gram": gram.tolist(),
        "dimensionless_leakage_over_abs_x": leakage,
        "errors": errors,
    }
    check(result, "2x2 refined-block inventory",
          len(fine_edges) == 12 and len(plaquettes) == 4 and len(interior) == 4,
          {"vertices": 9, "links": len(fine_edges), "plaquettes": len(plaquettes),
           "interior_links": len(interior)})
    check(result, "exact Q8 fibre moments",
          first_moment_error < TOLERANCE and second_moment_error < TOLERANCE,
          {"first": first_moment_error, "second": second_moment_error})
    check(result, "orthonormal plaquette Gram matrix",
          gram_error < TOLERANCE, {"error": gram_error, "gram": gram.tolist()})
    check(result, "retained outer Wilson loop",
          max(outer_matrix_error, outer_character_error) < TOLERANCE,
          {"matrix": outer_matrix_error, "character": outer_character_error})
    check(result, "closed-loop gauge invariance",
          max(gauge_errors) < TOLERANCE, {"maximum_error": max(gauge_errors)})
    check(result, "four-plaquette leakage coefficient",
          abs(leakage - 2.0) < TOLERANCE, {"actual": leakage, "expected": 2.0})

    boundary_keys = {edge for path in coarse_paths for edge, _ in path}
    subdivision_edges = {edge: fine_edges[edge] for edge in boundary_keys}
    subdivision_coarse = [loop_product(subdivision_edges, path) for path in coarse_paths]
    subdivision_face = loop_product(subdivision_edges, outer_terms)
    varied_edges = dict(subdivision_edges)
    for path, target in zip(coarse_paths, subdivision_coarse, strict=True):
        first_traversed = random_su2(rng)
        second_traversed = first_traversed.conj().T @ target
        for (edge, orientation), traversed in zip(
                path, (first_traversed, second_traversed), strict=True):
            varied_edges[edge] = traversed_factor(traversed, orientation)
    varied_coarse = [loop_product(varied_edges, path) for path in coarse_paths]
    varied_face = loop_product(varied_edges, outer_terms)
    subdivision_errors = {
        "face_from_coarse_paths": matrix_error(
            subdivision_face, product(subdivision_coarse)),
        "coarse_products_under_fibre_variation": max(
            matrix_error(actual, expected)
            for actual, expected in zip(varied_coarse, subdivision_coarse, strict=True)),
        "face_under_fibre_variation": matrix_error(varied_face, subdivision_face),
        "character_under_fibre_variation": abs(
            float(np.trace(varied_face).real - np.trace(subdivision_face).real)),
    }
    result["subdivision_control"] = {
        "vertices": 8,
        "fine_path_segments": len(subdivision_edges),
        "coarse_paths": len(coarse_paths),
        "faces": 1,
        "new_elementary_faces": 0,
        "errors": subdivision_errors,
    }
    check(result, "pure graph-subdivision inventory",
          len(subdivision_edges) == 8 and len(boundary_keys) == 8,
          {"vertices": 8, "links": len(subdivision_edges), "faces": 1})
    check(result, "pure graph-subdivision fibre control",
          max(subdivision_errors.values()) < TOLERANCE,
          subdivision_errors)


def symbolic_controls(result):
    b, g, a, delta = sp.symbols("b g a delta", positive=True)
    x = 2 / g**4
    g_coarse_squared = b**2 * g**2
    exact(result, "fundamental plaquette electric energy", 4 * sp.Rational(3, 4), 3)
    exact(result, "electric coefficient matching",
          g_coarse_squared / (2 * b * a), b * g**2 / (2 * a))
    exact(result, "four-plaquette physical leakage",
          g**2 / (2 * a) * 2 * x, 2 / (a * g**2))
    exact(result, "physical-gap unit transport",
          (g**2 / (2 * a) * delta) / (g_coarse_squared / (2 * b * a)), delta / b)
    exact(result, "path-map coarse x", 2 / g_coarse_squared**2, x / b**4)
    check(result, "electric-vacuum diagnostic diverges",
          sp.limit(x / 3, g, 0, dir="+") == sp.oo,
          {"expression": str(x / 3), "limit": "oo"})
    result["symbolic"] = {
        "x_f": str(x),
        "g_c_squared": str(g_coarse_squared),
        "dimensionless_leakage": str(2 * x),
        "physical_leakage": str(2 / (a * g**2)),
        "mass_preserving_delta_c": str(b * g**2 * delta / g_coarse_squared),
        "electric_vacuum_ratio": str(x / 3),
    }


def scale_controls(result):
    rows = []
    for b in B_VALUES:
        for g_f in G_VALUES:
            for a_f in A_VALUES:
                x_f = 2.0 / g_f**4
                g_c_squared = b**2 * g_f**2
                dimensionless_leakage = 2.0 * x_f
                physical_from_prefactor = g_f**2 / (2.0 * a_f) * dimensionless_leakage
                physical_closed = 2.0 / (a_f * g_f**2)
                errors = {
                    "physical_leakage": relative_error(physical_from_prefactor, physical_closed),
                    "coarse_x": relative_error(2.0 / g_c_squared**2, x_f / b**4),
                }
                row = {
                    "b": b,
                    "g_f": g_f,
                    "a_f": a_f,
                    "x_f": x_f,
                    "g_c_squared": g_c_squared,
                    "dimensionless_leakage": dimensionless_leakage,
                    "physical_leakage": physical_closed,
                    "errors": errors,
                }
                rows.append(row)
                check(result, f"unit identities b={b} g={g_f} a={a_f}",
                      max(errors.values()) < 1e-13, errors)
    expected = {(b, g, a) for b in B_VALUES for g in G_VALUES for a in A_VALUES}
    actual = [(row["b"], row["g_f"], row["a_f"]) for row in rows]
    check(result, "complete unique scale schedule",
          len(actual) == len(set(actual)) and set(actual) == expected,
          {"rows": len(actual), "expected": len(expected)})
    result["scale_rows"] = rows


def compute(result):
    result.update(checks=[], failures=[])
    rng = np.random.default_rng(SEED)
    path_controls(result, rng)
    electric_controls(result, rng)
    refined_block_controls(result, rng)
    symbolic_controls(result)
    scale_controls(result)
    success = not result["failures"]
    result.update(
        status="PASS" if success else "FAIL",
        check_count=len(result["checks"]),
        classification_stage="PRIMARY_CONTROLS_ONLY",
        classifications={
            "fixed_path_and_gauge_controls": (
                "PENDING_INDEPENDENT_RECONSTRUCTION" if success else "INCONCLUSIVE"),
            "fixed_character_casimir_controls": (
                "PENDING_INDEPENDENT_RECONSTRUCTION" if success else "INCONCLUSIVE"),
            "fixed_2x2_refined_block_controls": (
                "PENDING_INDEPENDENT_RECONSTRUCTION" if success else "INCONCLUSIVE"),
            "exact_cylindrical_intertwiner_obstruction": "PENDING_ANALYTICAL_RECONCILIATION",
            "weak_coupling_electric_vacuum_diagnostic": "PENDING_ANALYTICAL_RECONCILIATION",
        },
        scope={
            "interacting_fibre_map": "NOT_CONSTRUCTED",
            "feshbach_resolvent_bound": "NOT_ESTIMATED",
            "thermodynamic_limit": "UNRESOLVED",
            "continuum_construction": "UNRESOLVED",
            "continuum_mass": "UNRESOLVED",
            "cassi_microscopic_identification": "UNRESOLVED",
        },
    )
    return success


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")
    receipt_helper_source = receipt_checks.__file__
    if receipt_helper_source is None:
        raise RuntimeError("Cannot locate the receipt helper source")

    sources = {
        "protocol": PROTOCOL,
        "verifier": Path(__file__).resolve(),
        "receipt_helper": Path(receipt_helper_source).resolve(),
    }
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {
        key: {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(payloads[key]).hexdigest(),
        }
        for key, path in sources.items()
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        (snapshot_dir / path.name).write_bytes(payloads[key])
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "identities": identities,
        "numpy_version": np.__version__,
        "sympy_version": sp.__version__,
        "seed": SEED,
    }
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)

    result = {"schema": "cassi.yang-mills.block-map.v1", **manifest}
    success = False
    try:
        success = compute(result)
        if any(path.read_bytes() != payloads[key] for key, path in sources.items()):
            raise RuntimeError("A frozen source changed during execution")
    except Exception as exc:
        result.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)

    print(f"Receipt: {output}")
    print(json.dumps({key: result.get(key) for key in
                      ("status", "check_count", "classifications", "failures", "error")}, indent=2))
    if success and result.get("status") == "PASS":
        path_error = max(value for row in result["path_rows"] for value in row["errors"].values())
        electric_error = max(value for row in result["electric_rows"] for value in row["errors"].values())
        block_error = max(result["refined_block"]["errors"].values())
        print(f"Path identities: maximum discrepancy {path_error:.12g}")
        print(f"Electric compression: maximum discrepancy {electric_error:.12g}")
        print(f"Refined block: maximum discrepancy {block_error:.12g}")
        print("Four-plaquette leakage: ||Q h J1||/|x| = 2")
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
