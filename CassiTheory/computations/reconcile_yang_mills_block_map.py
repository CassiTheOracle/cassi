#!/usr/bin/env python3
"""Independently reconstruct the frozen Yang--Mills block-map controls.

This program never imports ``verify_yang_mills_block_map``.  It validates the
primary receipt and its immutable source snapshot, regenerates the seeded
SU(2) path, electric, refined-block and scale controls, and writes a separate
exclusive-create reconciliation receipt.  A numerical reconciliation is not
an analytical adoption of the block-map obstruction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/yang-mills-block-map-prereg.md"
PRIMARY_VERIFIER = ROOT / "computations/verify_yang_mills_block_map.py"
RECEIPT_HELPER = ROOT / "computations/verify_yang_mills_loop_gap.py"
SEED = 20260909
ABS_TOL = 2e-12
SCALE_TOL = 2e-13
PATH_WORDS = {2: (1, 1), 3: (1, -1, 1), 4: (-1, 1, -1, 1)}
B_VALUES = (2, 3, 4)
G_VALUES = (2.0, 1.0, 0.5)
A_VALUES = (1.0, 0.5, 0.25)

I2 = np.eye(2, dtype=complex)
SIGMA = (
    np.array(((0, 1), (1, 0)), dtype=complex),
    np.array(((0, -1j), (1j, 0)), dtype=complex),
    np.array(((1, 0), (0, -1)), dtype=complex),
)
FUNDAMENTAL_GENERATORS = tuple(0.5j * sigma for sigma in SIGMA)


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def finite(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return bool(np.isfinite(value))
    if isinstance(value, list):
        return all(finite(item) for item in value)
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    return True


def safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return safe(value.item())
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(safe(payload), indent=2, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing JSON input: {repo_rel(path)}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON input is not an object: {repo_rel(path)}")
    return value


def check(checks: list[dict[str, Any]], name: str, passed: bool,
          measured: Any = None, threshold: Any = None) -> None:
    row: dict[str, Any] = {"name": name, "pass": bool(passed)}
    if measured is not None:
        row["measured"] = safe(measured)
    if threshold is not None:
        row["threshold"] = threshold
    checks.append(row)


def close(actual: Any, expected: Any, tolerance: float = ABS_TOL) -> bool:
    try:
        left, right = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
        return left.shape == right.shape and bool(np.allclose(
            left, right, atol=tolerance, rtol=tolerance, equal_nan=False))
    except (TypeError, ValueError):
        return actual == expected


def matrix_error(actual: np.ndarray, expected: np.ndarray) -> float:
    return float(np.max(np.abs(np.asarray(actual) - np.asarray(expected))))


def relative_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(abs(expected), np.finfo(float).tiny)


def product(matrices, size: int | None = None):
    matrices = tuple(matrices)
    if not matrices:
        if size is None:
            raise ValueError("empty product requires a size")
        return np.eye(size)
    result = np.eye(matrices[0].shape[0], dtype=matrices[0].dtype)
    for matrix in matrices:
        result = result @ matrix
    return result


def su2_from_quaternion(quaternion: np.ndarray) -> np.ndarray:
    q = np.asarray(quaternion, dtype=float)
    q = q / np.linalg.norm(q)
    return q[0] * I2 + 1j * sum(q[index + 1] * SIGMA[index]
                                for index in range(3))


def random_su2(rng: np.random.Generator) -> np.ndarray:
    return su2_from_quaternion(rng.normal(size=4))


def traversed_factor(edge: np.ndarray, orientation: int) -> np.ndarray:
    return edge if orientation == 1 else edge.conj().T


def path_product(edges, orientations):
    return product(traversed_factor(edge, orientation)
                   for edge, orientation in zip(edges, orientations, strict=True))


def adjoint_representation(group: np.ndarray) -> np.ndarray:
    result = np.empty((3, 3), dtype=float)
    for row, left in enumerate(SIGMA):
        for column, right in enumerate(SIGMA):
            result[row, column] = float(
                (0.5 * np.trace(left @ group @ right @ group.conj().T)).real)
    return result


def levi_civita(i: int, j: int, k: int) -> int:
    if len({i, j, k}) < 3:
        return 0
    return 1 if (i, j, k) in ((0, 1, 2), (1, 2, 0), (2, 0, 1)) else -1


ADJOINT_GENERATORS = tuple(np.array(
    [[levi_civita(axis, row, column) for column in range(3)]
     for row in range(3)], dtype=float) for axis in range(3))
Q8 = tuple(sign * matrix for matrix in (I2, *(1j * sigma for sigma in SIGMA))
            for sign in (1, -1))


def gauge_path(edges, orientations, gauges):
    result = []
    for index, (edge, orientation) in enumerate(zip(edges, orientations, strict=True)):
        if orientation == 1:
            result.append(gauges[index] @ edge @ gauges[index + 1].conj().T)
        else:
            result.append(gauges[index + 1] @ edge @ gauges[index].conj().T)
    return result


def reconstruct_paths(result: dict[str, Any], checks: list[dict[str, Any]],
                      rng: np.random.Generator) -> dict[str, Any]:
    rows = []
    for length, orientations in PATH_WORDS.items():
        traversed = [random_su2(rng) for _ in range(length)]
        edges = [matrix if orientation == 1 else matrix.conj().T
                 for matrix, orientation in zip(traversed, orientations, strict=True)]
        direct = product(traversed)
        gauges = [random_su2(rng) for _ in range(length + 1)]
        transformed = gauge_path(edges, orientations, gauges)
        internal_gauges = [I2.copy(), *(random_su2(rng) for _ in range(length - 1)), I2.copy()]
        errors = {
            "path_reconstruction": matrix_error(path_product(edges, orientations), direct),
            "endpoint_covariance": matrix_error(
                path_product(transformed, orientations),
                gauges[0] @ direct @ gauges[-1].conj().T),
            "internal_cancellation": matrix_error(
                path_product(gauge_path(edges, orientations, internal_gauges), orientations), direct),
            "inverse_path": matrix_error(
                path_product(list(reversed(edges)),
                             tuple(-item for item in reversed(orientations))),
                direct.conj().T),
        }
        rows.append({"length": length, "orientations": list(orientations), "errors": errors})
    primary_rows = result.get("path_rows", [])
    check(checks, "path schedule and seeded reconstruction",
          len(primary_rows) == 3 and [row.get("length") for row in primary_rows] == list(B_VALUES)
          and all(close(primary_rows[i].get("errors"), rows[i]["errors"])
                  for i in range(len(rows))),
          {"primary_rows": len(primary_rows), "reconstructed_rows": len(rows)})
    return {"rows": rows, "maximum_error": max(max(row["errors"].values()) for row in rows)}


def represented_character(edges, orientations, representation, generators):
    factors = [traversed_factor(representation(edge), orientation)
               for edge, orientation in zip(edges, orientations, strict=True)]
    character = np.trace(product(factors))
    total_second = 0.0j
    individual = []
    for index, orientation in enumerate(orientations):
        edge_second = 0.0j
        for generator in generators:
            replacement = (generator @ generator @ factors[index]
                           if orientation == 1 else factors[index] @ generator @ generator)
            modified = list(factors)
            modified[index] = replacement
            edge_second += np.trace(product(modified))
        individual.append(-edge_second)
        total_second += edge_second
    return character, -total_second, individual


def reconstruct_electric(result: dict[str, Any], checks: list[dict[str, Any]],
                          rng: np.random.Generator) -> dict[str, Any]:
    rows = []
    representations = (
        ("fundamental", lambda group: group, FUNDAMENTAL_GENERATORS, 0.75),
        ("adjoint", adjoint_representation, ADJOINT_GENERATORS, 2.0),
    )
    for length, orientations in PATH_WORDS.items():
        traversed = [random_su2(rng) for _ in range(length)]
        edges = [matrix if orientation == 1 else matrix.conj().T
                 for matrix, orientation in zip(traversed, orientations, strict=True)]
        for name, representation, generators, casimir in representations:
            character, compressed, individual = represented_character(
                edges, orientations, representation, generators)
            expected = length * casimir * character
            errors = {
                "compressed": float(abs(compressed - expected)),
                "individual_max": float(max(abs(value - casimir * character)
                                             for value in individual)),
                "generator_casimir": matrix_error(
                    -np.add.reduce([generator @ generator for generator in generators]),
                    casimir * np.eye(representation(I2).shape[0])),
            }
            rows.append({"length": length, "representation": name,
                         "orientations": list(orientations), "casimir": casimir,
                         "character_real": float(character.real),
                         "character_imaginary": float(character.imag), "errors": errors})
    primary_rows = result.get("electric_rows", [])
    check(checks, "electric schedule and seeded reconstruction",
          len(primary_rows) == 6
          and [(row.get("length"), row.get("representation")) for row in primary_rows]
          == [(row["length"], row["representation"]) for row in rows]
          and all(close(primary_rows[i].get("errors"), rows[i]["errors"])
                  and close(primary_rows[i].get("character_real"), rows[i]["character_real"])
                  and close(primary_rows[i].get("character_imaginary"), rows[i]["character_imaginary"])
                  for i in range(len(rows))),
          {"primary_rows": len(primary_rows), "reconstructed_rows": len(rows)})
    return {"rows": rows, "maximum_error": max(max(row["errors"].values()) for row in rows)}


def horizontal(i: int, j: int):
    return ("h", i, j)


def vertical(i: int, j: int):
    return ("v", i, j)


def endpoints(edge):
    direction, i, j = edge
    return ((i, j), (i + 1, j)) if direction == "h" else ((i, j), (i, j + 1))


def plaquette(i: int, j: int):
    return ((horizontal(i, j), 1), (vertical(i + 1, j), 1),
            (horizontal(i, j + 1), -1), (vertical(i, j), -1))


def loop_product(edges, terms):
    return product(traversed_factor(edges[edge], orientation)
                   for edge, orientation in terms)


def loop_character(edges, terms):
    return float(np.trace(loop_product(edges, terms)).real)


def replaced_character(edges, terms, edge, replacement):
    changed = dict(edges)
    changed[edge] = replacement
    return loop_character(changed, terms)


def reconstruct_refined(result: dict[str, Any], checks: list[dict[str, Any]],
                         rng: np.random.Generator) -> dict[str, Any]:
    fine = {**{horizontal(i, j): random_su2(rng) for j in range(3) for i in range(2)},
            **{vertical(i, j): random_su2(rng) for i in range(3) for j in range(2)}}
    coarse = (
        ((horizontal(0, 0), 1), (horizontal(1, 0), 1)),
        ((vertical(2, 0), 1), (vertical(2, 1), 1)),
        ((horizontal(1, 2), -1), (horizontal(0, 2), -1)),
        ((vertical(0, 1), -1), (vertical(0, 0), -1)),
    )
    faces = tuple(plaquette(i, j) for j in range(2) for i in range(2))
    interior = {horizontal(0, 1), horizontal(1, 1), vertical(1, 0), vertical(1, 1)}
    conditional = []
    for index, terms in enumerate(faces):
        witness = next(edge for edge, _ in terms if edge in interior)
        values = np.array([replaced_character(fine, terms, witness, sample) for sample in Q8])
        conditional.append({"plaquette": index, "witness": list(witness),
                            "first_moment": float(values.mean()),
                            "second_moment": float(np.mean(values * values))})
    gram = np.zeros((4, 4), dtype=float)
    for first, first_terms in enumerate(faces):
        first_keys = {edge for edge, _ in first_terms}
        for second, second_terms in enumerate(faces):
            second_keys = {edge for edge, _ in second_terms}
            witness = sorted(first_keys if first == second else first_keys - second_keys)[0]
            products = [replaced_character(fine, first_terms, witness, sample)
                        * replaced_character(fine, second_terms, witness, sample)
                        for sample in Q8]
            gram[first, second] = float(np.mean(products))
    coarse_holonomies = [loop_product(fine, path) for path in coarse]
    outer_terms = tuple(term for path in coarse for term in path)
    fine_outer = loop_product(fine, outer_terms)
    coarse_outer = product(coarse_holonomies)
    gauges = {(i, j): random_su2(rng) for i in range(3) for j in range(3)}
    transformed = {}
    for edge, group in fine.items():
        source, target = endpoints(edge)
        transformed[edge] = gauges[source] @ group @ gauges[target].conj().T
    gauge_errors = [abs(loop_character(transformed, terms) - loop_character(fine, terms))
                    for terms in faces]
    leakage = float(np.sqrt(np.ones(4) @ gram @ np.ones(4)))
    errors = {
        "conditional_first_moment": max(abs(row["first_moment"]) for row in conditional),
        "conditional_second_moment": max(abs(row["second_moment"] - 1.0) for row in conditional),
        "plaquette_gram": matrix_error(gram, np.eye(4)),
        "outer_matrix": matrix_error(coarse_outer, fine_outer),
        "outer_character": abs(float(np.trace(coarse_outer).real
                                      - np.trace(fine_outer).real)),
        "gauge_invariance": float(max(gauge_errors)),
        "leakage_coefficient": abs(leakage - 2.0),
    }
    primary = result.get("refined_block", {})
    check(checks, "refined-block seeded reconstruction",
          primary.get("vertices") == 9 and primary.get("links") == 12
          and close(primary.get("conditional_rows"), conditional)
          and close(primary.get("plaquette_gram"), gram)
          and close(primary.get("dimensionless_leakage_over_abs_x"), leakage)
          and close(primary.get("errors"), errors),
          errors)

    boundary = {edge for path in coarse for edge, _ in path}
    boundary_edges = {edge: fine[edge] for edge in boundary}
    subdivision_coarse = [loop_product(boundary_edges, path) for path in coarse]
    subdivision_face = loop_product(boundary_edges, outer_terms)
    varied = dict(boundary_edges)
    for path, target in zip(coarse, subdivision_coarse, strict=True):
        first = random_su2(rng)
        second = first.conj().T @ target
        for (edge, orientation), traversed in zip(path, (first, second), strict=True):
            varied[edge] = traversed_factor(traversed, orientation)
    varied_coarse = [loop_product(varied, path) for path in coarse]
    varied_face = loop_product(varied, outer_terms)
    subdivision_errors = {
        "face_from_coarse_paths": matrix_error(subdivision_face, product(subdivision_coarse)),
        "coarse_products_under_fibre_variation": max(
            matrix_error(actual, expected)
            for actual, expected in zip(varied_coarse, subdivision_coarse, strict=True)),
        "face_under_fibre_variation": matrix_error(varied_face, subdivision_face),
        "character_under_fibre_variation": abs(
            float(np.trace(varied_face).real - np.trace(subdivision_face).real)),
    }
    primary_subdivision = result.get("subdivision_control", {})
    check(checks, "pure-subdivision seeded reconstruction",
          primary_subdivision.get("vertices") == 8
          and primary_subdivision.get("fine_path_segments") == 8
          and primary_subdivision.get("faces") == 1
          and close(primary_subdivision.get("errors"), subdivision_errors),
          subdivision_errors)
    return {"refined_errors": errors, "subdivision_errors": subdivision_errors,
            "leakage": leakage}


def reconstruct_scales(result: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    expected_rows = []
    for b in B_VALUES:
        for g in G_VALUES:
            for a in A_VALUES:
                x = 2.0 / g**4
                coarse_g2 = b**2 * g**2
                dimensionless = 2.0 * x
                physical = 2.0 / (a * g**2)
                errors = {
                    "physical_leakage": relative_error(g**2 / (2.0 * a) * dimensionless, physical),
                    "coarse_x": relative_error(2.0 / coarse_g2**2, x / b**4),
                }
                expected_rows.append({"b": b, "g_f": g, "a_f": a, "x_f": x,
                                      "g_c_squared": coarse_g2,
                                      "dimensionless_leakage": dimensionless,
                                      "physical_leakage": physical, "errors": errors})
    actual = result.get("scale_rows", [])
    check(checks, "scale schedule and exact unit reconstruction",
          len(actual) == len(expected_rows)
          and all(close(actual[i], expected_rows[i], SCALE_TOL)
                  for i in range(len(expected_rows))),
          {"primary_rows": len(actual), "reconstructed_rows": len(expected_rows)})
    symbolic = result.get("symbolic", {})
    expected_symbolic = {
        "x_f": "2/g**4", "g_c_squared": "b**2*g**2",
        "dimensionless_leakage": "4/g**4", "physical_leakage": "2/(a*g**2)",
        "mass_preserving_delta_c": "delta/b", "electric_vacuum_ratio": "2/(3*g**4)",
    }
    check(checks, "symbolic scale labels remain frozen", symbolic == expected_symbolic,
          {"actual": symbolic, "expected": expected_symbolic})
    return {"rows": len(expected_rows), "maximum_error": max(
        max(row["errors"].values()) for row in expected_rows)}

def validate_primary_snapshot(primary: Path, checks: list[dict[str, Any]]) -> dict[str, Any]:
    manifest_path = primary.with_suffix(".inputs.json")
    snapshot_dir = primary.with_suffix(".sources")
    manifest = load_json(manifest_path)
    identities = manifest.get("identities", {})
    expected = {"protocol": PROTOCOL, "verifier": PRIMARY_VERIFIER,
                "receipt_helper": RECEIPT_HELPER}
    good = True
    details = {}
    for key, expected_path in expected.items():
        identity = identities.get(key, {})
        actual_path = ROOT / identity.get("path", "")
        snapshot = snapshot_dir / expected_path.name
        item_good = (actual_path.resolve() == expected_path.resolve()
                     and expected_path.is_file() and snapshot.is_file()
                     and identity.get("sha256") == raw_sha256(expected_path)
                     and snapshot.read_bytes() == expected_path.read_bytes())
        good = good and item_good
        details[key] = {"live": repo_rel(expected_path), "snapshot": snapshot.name,
                        "pass": item_good}
    check(checks, "primary source manifest and snapshots", good, details)
    return {"manifest": manifest, "manifest_sha256": raw_sha256(manifest_path),
            "receipt_sha256": raw_sha256(primary)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path,
                        default=ROOT / "runs/yang_mills_block_map_recovery_20260914/verification.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "runs/yang_mills_block_map_recovery_20260914/verification-independent.json")
    args = parser.parse_args()
    primary = args.primary.resolve()
    output = args.output.resolve()
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh independent output path: {output}")

    checks: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.block-map.independent-reconciliation.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "primary": repo_rel(primary),
    }
    success = False
    try:
        primary_result = load_json(primary)
        source_info = validate_primary_snapshot(primary, checks)
        check(checks, "primary receipt status and finite payload",
              primary_result.get("schema") == "cassi.yang-mills.block-map.v1"
              and primary_result.get("status") == "PASS"
              and primary_result.get("failures") == []
              and finite(primary_result),
              {"schema": primary_result.get("schema"),
               "status": primary_result.get("status"),
               "failures": len(primary_result.get("failures", []))})
        rng = np.random.default_rng(SEED)
        paths = reconstruct_paths(primary_result, checks, rng)
        electric = reconstruct_electric(primary_result, checks, rng)
        refined = reconstruct_refined(primary_result, checks, rng)
        scales = reconstruct_scales(primary_result, checks)
        expected_classifications = {
            "fixed_path_and_gauge_controls": "PENDING_INDEPENDENT_RECONSTRUCTION",
            "fixed_character_casimir_controls": "PENDING_INDEPENDENT_RECONSTRUCTION",
            "fixed_2x2_refined_block_controls": "PENDING_INDEPENDENT_RECONSTRUCTION",
            "exact_cylindrical_intertwiner_obstruction": "PENDING_ANALYTICAL_RECONCILIATION",
            "weak_coupling_electric_vacuum_diagnostic": "PENDING_ANALYTICAL_RECONCILIATION",
        }
        check(checks, "primary classifications remain non-adoptive",
              primary_result.get("classifications") == expected_classifications,
              {"actual": primary_result.get("classifications"),
               "expected": expected_classifications})
        success = all(row["pass"] for row in checks)
        result.update(
            primary_receipt_sha256=source_info["receipt_sha256"],
            primary_manifest_sha256=source_info["manifest_sha256"],
            seed=SEED,
            checks=checks,
            check_count=len(checks),
            failures=[row for row in checks if not row["pass"]],
            reconstruction=dict(path=paths, electric=electric, refined=refined, scales=scales),
            classification_stage="NUMERICAL_RECONCILIATION_ONLY",
            classifications={
                "fixed_path_and_gauge_controls": "RECONCILED_NUMERICALLY_REVIEW_REQUIRED",
                "fixed_character_casimir_controls": "RECONCILED_NUMERICALLY_REVIEW_REQUIRED",
                "fixed_2x2_refined_block_controls": "RECONCILED_NUMERICALLY_REVIEW_REQUIRED",
                "exact_cylindrical_intertwiner_obstruction": "PENDING_ANALYTICAL_RECONCILIATION",
                "weak_coupling_electric_vacuum_diagnostic": "PENDING_ANALYTICAL_RECONCILIATION",
            },
            scope=dict(interacting_fibre_map="NOT_CONSTRUCTED",
                       feshbach_resolvent_bound="NOT_ESTIMATED",
                       thermodynamic_limit="UNRESOLVED", continuum_construction="UNRESOLVED",
                       continuum_mass="UNRESOLVED", cassi_microscopic_identification="UNRESOLVED"),
            status="PASS" if success else "FAIL")
    except Exception as exc:
        result.update(status="ERROR", checks=checks,
                      check_count=len(checks), failures=[{"error": str(exc)}],
                      error=f"{type(exc).__name__}: {exc}")

    sources = {"protocol": PROTOCOL, "primary_verifier": PRIMARY_VERIFIER,
               "receipt_helper": RECEIPT_HELPER, "independent_reconciler": Path(__file__).resolve()}
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {
        key: {"path": repo_rel(path), "sha256": hashlib.sha256(payloads[key]).hexdigest()}
        for key, path in sources.items()
    }
    result["identities"] = identities
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        shutil.copyfile(path, snapshot_dir / path.name)
    write_json(manifest_path, {"created_utc": result["created_utc"], "identities": identities,
                               "primary_receipt_sha256": result.get("primary_receipt_sha256"),
                               "primary_manifest_sha256": result.get("primary_manifest_sha256")})
    write_json(output, result)
    print(f"Receipt: {output}")
    print(json.dumps({key: result.get(key) for key in
                      ("status", "check_count", "failures", "classification_stage", "error")}, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
