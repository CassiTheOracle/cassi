#!/usr/bin/env python3
"""Independently reconstruct the frozen Yang--Mills vacuum-block controls.

The program validates the primary receipt and source snapshots, regenerates the
fixed SU(2) group/local-energy schedule from its own implementation, and
reconstructs the Gaussian controls from the explicit sine basis.  It never
imports ``verify_yang_mills_vacuum_blocks`` and never converts a finite
reconciliation into an analytical or continuum claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/yang-mills-vacuum-block-prereg.md"
PRIMARY_VERIFIER = ROOT / "computations/verify_yang_mills_vacuum_blocks.py"
RECEIPT_HELPER = ROOT / "computations/verify_yang_mills_loop_gap.py"
X_VALUES = (0.25, 1.0, 16.0)
FD_STEPS = (1e-3, 5e-4)
GAUSSIAN_SIZES = (4, 8, 16, 32, 64)
GAUSSIAN_MASSES = (0.0, 0.5)
GROUP_TOLERANCE = 1e-9
LOCAL_TOLERANCE = 2e-8
MATRIX_TOLERANCE = 2e-10

PAULI = (
    np.array(((0, 1), (1, 0)), dtype=complex),
    np.array(((0, -1j), (1j, 0)), dtype=complex),
    np.array(((1, 0), (0, -1)), dtype=complex),
)
IDENTITY_2 = np.eye(2, dtype=complex)
EDGES = ((0, 1), (1, 2), (3, 2), (0, 3), (1, 5), (4, 5), (0, 4))
WORDS = (
    ((0, 1), (1, 1), (2, -1), (3, -1)),
    ((0, 1), (4, 1), (5, -1), (6, -1)),
)


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return safe(value.item())
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    return value


def finite(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(finite(item) for item in value)
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    return True


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing JSON input: {repo_rel(path)}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON input is not an object: {repo_rel(path)}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(safe(value), indent=2, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def check(checks: list[dict[str, Any]], name: str, passed: bool,
          measured: Any = None, threshold: float | None = None) -> None:
    row: dict[str, Any] = {"name": name, "pass": bool(passed)}
    if measured is not None:
        row["measured"] = safe(measured)
    if threshold is not None:
        row["threshold"] = threshold
    checks.append(row)


def close(actual: Any, expected: Any, tolerance: float = MATRIX_TOLERANCE) -> bool:
    try:
        left = np.asarray(actual)
        right = np.asarray(expected)
        if left.shape != right.shape:
            return False
        if np.iscomplexobj(left) or np.iscomplexobj(right):
            return bool(np.allclose(left, right, atol=tolerance, rtol=tolerance,
                                    equal_nan=False))
        return bool(np.allclose(left.astype(float), right.astype(float),
                                atol=tolerance, rtol=tolerance, equal_nan=False))
    except (TypeError, ValueError):
        return actual == expected


def normalized_error(actual: Any, expected: Any) -> float:
    left, right = np.asarray(actual), np.asarray(expected)
    return float(np.max(np.abs(left - right)
                        / np.maximum(1.0, np.maximum(np.abs(left), np.abs(right)))))


def matrix_json(matrix: np.ndarray) -> list[list[list[float]]]:
    return [[[float(value.real), float(value.imag)] for value in row]
            for row in np.asarray(matrix)]


def matrix_from_json(value: Any) -> np.ndarray:
    return np.asarray([[complex(real, imaginary) for real, imaginary in row]
                       for row in value], dtype=complex)


def su2_exp(theta: float, axis: Any) -> np.ndarray:
    vector = np.asarray(axis, dtype=float)
    vector /= np.linalg.norm(vector)
    generator = sum((vector[index] * PAULI[index] for index in range(3)),
                    np.zeros((2, 2), dtype=complex))
    return math.cos(theta) * IDENTITY_2 + 1j * math.sin(theta) * generator


def factor(links: list[np.ndarray], edge: int, orientation: int) -> np.ndarray:
    return links[edge] if orientation == 1 else links[edge].conj().T


def holonomy(links: list[np.ndarray], word) -> np.ndarray:
    value = IDENTITY_2.copy()
    for edge, orientation in word:
        value = value @ factor(links, edge, orientation)
    return value


def character(links: list[np.ndarray], word) -> float:
    value = np.trace(holonomy(links, word))
    return float(value.real)


def character_derivative(links: list[np.ndarray], word, target_edge: int,
                         generator: int) -> float:
    position = next(index for index, (edge, _) in enumerate(word) if edge == target_edge)
    value = None
    for index, (edge, orientation) in enumerate(word):
        current = factor(links, edge, orientation)
        if index == position:
            if orientation == 1:
                current = 0.5j * PAULI[generator] @ links[edge]
            else:
                current = links[edge].conj().T @ (-0.5j * PAULI[generator])
        value = current if value is None else value @ current
    if value is None:
        raise RuntimeError("empty Wilson word")
    return float(np.trace(value).real)


def fixture_observables(links: list[np.ndarray]) -> dict[str, Any]:
    loops = [holonomy(links, word) for word in WORDS]
    characters = [float(np.trace(loop).real) for loop in loops]
    gradients = []
    for word in WORDS:
        active = {edge for edge, _ in word}
        gradient = np.zeros((len(EDGES), 3), dtype=float)
        for edge in active:
            for generator in range(3):
                gradient[edge, generator] = character_derivative(
                    links, word, edge, generator)
        gradients.append(gradient)
    total = gradients[0] + gradients[1]
    return dict(
        characters=characters,
        loop_matrices=[matrix_json(loop) for loop in loops],
        joined_trace=float(np.trace(loops[0] @ loops[1]).real),
        gradients=[gradient.tolist() for gradient in gradients],
        self_gradient_squares=[float(np.sum(gradient * gradient))
                               for gradient in gradients],
        shared_cross=float(np.dot(gradients[0][0], gradients[1][0])),
        total_gradient_square=float(np.sum(total * total)),
    )


def local_energy(observables: dict[str, Any], x: float, kappa: float) -> float:
    return (4.0 * x + (3.0 * kappa - x) * sum(observables["characters"])
            - kappa * kappa * observables["total_gradient_square"])


def left_perturb(links: list[np.ndarray], edge: int, generator: int,
                 parameter: float) -> list[np.ndarray]:
    changed = [matrix.copy() for matrix in links]
    changed[edge] = su2_exp(parameter / 2.0, np.eye(3)[generator]) @ changed[edge]
    return changed


def five_point(links: list[np.ndarray], observables: dict[str, Any],
               x: float, kappa: float, step: float) -> dict[str, Any]:
    base = sum(observables["characters"])
    analytic = [np.asarray(row) for row in observables["gradients"]]
    first_errors = []
    kinetic = 0.0
    for edge in range(len(EDGES)):
        for generator in range(3):
            values = {}
            chars_by_loop = [{}, {}]
            for multiplier in (-2, -1, 1, 2):
                moved = left_perturb(links, edge, generator, multiplier * step)
                chars = [character(moved, word) for word in WORDS]
                values[multiplier] = math.exp(kappa * (sum(chars) - base))
                for loop_index in range(2):
                    chars_by_loop[loop_index][multiplier] = chars[loop_index]
            for loop_index in range(2):
                derivative = (chars_by_loop[loop_index][-2]
                              - 8.0 * chars_by_loop[loop_index][-1]
                              + 8.0 * chars_by_loop[loop_index][1]
                              - chars_by_loop[loop_index][2]) / (12.0 * step)
                first_errors.append(abs(derivative - analytic[loop_index][edge, generator]))
            second = (-values[2] + 16.0 * values[1] - 30.0
                      + 16.0 * values[-1] - values[-2]) / (12.0 * step * step)
            kinetic -= second
    direct = kinetic + 4.0 * x - x * base
    exact = local_energy(observables, x, kappa)
    return dict(step=step, maximum_first_derivative_error=max(first_errors),
                direct_local_energy=direct, analytic_local_energy=exact,
                local_energy_error=abs(direct - exact),
                local_energy_normalized_error=abs(direct - exact) / max(1.0, abs(exact)))


def make_fixtures() -> list[tuple[str, list[np.ndarray]]]:
    fixtures = [("identity", [IDENTITY_2.copy() for _ in EDGES])]
    commuting = [su2_exp(math.pi * (edge + 1) / 19.0, (0, 0, 1))
                 for edge in range(len(EDGES))]
    fixtures.append(("commuting", commuting))
    for sample in range(3):
        links = []
        for edge in range(len(EDGES)):
            theta = math.pi * (1 + ((edge + 1) * (sample + 2) % 17)) / 19.0
            axis = (1 + ((edge + sample) % 3),
                    ((2 * edge + sample) % 5) - 2,
                    ((3 * edge + 2 * sample) % 7) - 3)
            links.append(su2_exp(theta, axis))
        fixtures.append((f"noncommuting_{sample}", links))
    return fixtures


def gauge_transform(links: list[np.ndarray]) -> list[np.ndarray]:
    gauges = [su2_exp(math.pi * (vertex + 1) / 11.0,
                      np.eye(3)[vertex % 3]) for vertex in range(6)]
    return [gauges[source] @ link @ gauges[target].conj().T
            for link, (source, target) in zip(links, EDGES, strict=True)]


def reconstruct_group(primary: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    primary_fixtures = primary.get("group_fixtures", [])
    primary_rows = primary.get("local_energy_rows", [])
    expected = make_fixtures()
    local_count = 0
    max_local_difference = 0.0
    for fixture_index, (name, links) in enumerate(expected):
        fixture = primary_fixtures[fixture_index] if fixture_index < len(primary_fixtures) else {}
        observed = fixture_observables(links)
        transformed = fixture_observables(gauge_transform(links))
        identity_errors = {
            "first_self": abs(observed["self_gradient_squares"][0]
                               - (4.0 - observed["characters"][0] ** 2)),
            "second_self": abs(observed["self_gradient_squares"][1]
                                - (4.0 - observed["characters"][1] ** 2)),
            "shared_fierz": abs(observed["shared_cross"]
                                 - (observed["characters"][0] * observed["characters"][1] / 4.0
                                    - observed["joined_trace"] / 2.0)),
        }
        gauge_error = max(
            normalized_error(observed["characters"], transformed["characters"]),
            normalized_error(observed["joined_trace"], transformed["joined_trace"]),
            normalized_error(observed["self_gradient_squares"], transformed["self_gradient_squares"]),
            normalized_error(observed["total_gradient_square"], transformed["total_gradient_square"]),
        )
        fixture_good = (fixture.get("name") == name
                        and close([matrix_from_json(item) for item in fixture.get("links", [])], links)
                        and close(fixture.get("observables", {}).get("characters"), observed["characters"])
                        and close(fixture.get("observables", {}).get("joined_trace"), observed["joined_trace"])
                        and close(fixture.get("observables", {}).get("total_gradient_square"), observed["total_gradient_square"])
                        and close(fixture.get("transformed_observables", {}).get("characters"), transformed["characters"])
                        and close(fixture.get("identity_errors"), identity_errors, GROUP_TOLERANCE)
                        and close(fixture.get("gauge_invariance_error"), gauge_error, GROUP_TOLERANCE))
        check(checks, f"independent SU2 fixture {name}", fixture_good,
              {"identity_errors": identity_errors, "gauge_error": gauge_error}, GROUP_TOLERANCE)

        fixture_rows = [row for row in primary_rows if row.get("fixture") == name]
        for x in X_VALUES:
            for label, kappa in (("zero", 0.0), ("strong_series", x / 3.0),
                                 ("weak_scale", math.sqrt(x))):
                matching = next((row for row in fixture_rows
                                 if row.get("x") == x and row.get("kappa_label") == label), None)
                analytic = local_energy(observed, x, kappa)
                gauge_energy_error = abs(analytic - local_energy(transformed, x, kappa))
                fds = [five_point(links, observed, x, kappa, step) for step in FD_STEPS]
                local_count += 1
                row_good = (matching is not None
                            and close(matching.get("characters"), observed["characters"])
                            and close(matching.get("joined_trace"), observed["joined_trace"])
                            and close(matching.get("total_gradient_square"), observed["total_gradient_square"])
                            and close(matching.get("analytic_local_energy"), analytic)
                            and close(matching.get("gauge_energy_error"), gauge_energy_error,
                                       GROUP_TOLERANCE)
                            and len(matching.get("finite_difference", [])) == len(fds))
                if matching is not None:
                    for expected_fd, actual_fd in zip(fds, matching["finite_difference"], strict=True):
                        max_local_difference = max(max_local_difference,
                                                   abs(expected_fd["direct_local_energy"]
                                                       - actual_fd.get("direct_local_energy", math.nan)))
                        row_good = row_good and close(actual_fd, expected_fd, LOCAL_TOLERANCE)
                check(checks, f"independent local-energy row {name} {x} {label}", row_good,
                      {"fixture": name, "x": x, "kappa": kappa,
                       "maximum_difference": max_local_difference}, LOCAL_TOLERANCE)
    check(checks, "complete independent local-energy schedule",
          len(primary_rows) == 45 and local_count == 45, {"primary": len(primary_rows), "recomputed": local_count})

    same_expected = []
    for label, axis in (("parallel", (0, 0, 1)), ("orthogonal", (1, 0, 0)),
                        ("antiparallel", (0, 0, -1))):
        links = [IDENTITY_2.copy() for _ in EDGES]
        links[1] = su2_exp(math.pi / 2.0, (0, 0, 1))
        links[4] = su2_exp(math.pi / 2.0, axis)
        obs = fixture_observables(links)
        same_expected.append(dict(label=label, characters=obs["characters"],
                                  joined_trace=obs["joined_trace"],
                                  total_gradient_square=obs["total_gradient_square"],
                                  local_energy=local_energy(obs, 1.0, 1.0)))
    same_actual = primary.get("same_character_rows", [])
    check(checks, "same-character relative-holonomy reconstruction",
          len(same_actual) == 3 and all(close(same_actual[index], same_expected[index])
                                        for index in range(3)),
          {"primary": len(same_actual), "recomputed": len(same_expected)})
    return {"fixtures": len(expected), "local_rows": local_count,
            "maximum_local_difference": max_local_difference}


def positive_sqrt(matrix: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh(matrix)
    if np.min(values) <= 0.0:
        raise ArithmeticError("positive square root received non-positive spectrum")
    return (vectors * np.sqrt(values)) @ vectors.T


def symplectic(covariance_q: np.ndarray, covariance_p: np.ndarray) -> np.ndarray:
    root = positive_sqrt(covariance_q)
    values = np.linalg.eigvalsh(root @ covariance_p @ root)
    return np.sqrt(np.maximum(values, 0.0))


def reconstruct_gaussian(primary: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    rows = primary.get("gaussian_rows", [])
    expected_keys = {(size, mass) for size in GAUSSIAN_SIZES for mass in GAUSSIAN_MASSES}
    actual_keys = {(row.get("size"), row.get("mass")) for row in rows}
    check(checks, "complete independent Gaussian schedule",
          len(rows) == 10 and actual_keys == expected_keys,
          {"primary": len(rows), "expected": len(expected_keys)})
    max_matrix_difference = 0.0
    for row in rows:
        size, mass = int(row["size"]), float(row["mass"])
        indices = np.arange(1, size + 1, dtype=float)
        sine_vectors = math.sqrt(2.0 / (size + 1)) * np.sin(
            math.pi * np.outer(indices, indices) / (size + 1))
        sine_values = mass * mass + 4.0 * np.sin(
            math.pi * indices / (2.0 * (size + 1))) ** 2
        q = (sine_vectors * np.sqrt(sine_values)) @ sine_vectors.T
        retained = np.arange(0, size, 2)
        eliminated = np.arange(1, size, 2)
        q_rr = q[np.ix_(retained, retained)]
        q_re = q[np.ix_(retained, eliminated)]
        q_ee = q[np.ix_(eliminated, eliminated)]
        q_eff = q_rr - q_re @ np.linalg.solve(q_ee, q_re.T)
        q_inverse_rr = np.linalg.inv(q)[np.ix_(retained, retained)]
        covariance_q = q_inverse_rr / 2.0
        covariance_p = q_rr / 2.0
        difference = (q_rr - q_eff) / 2.0
        symplectic_values = symplectic(covariance_q, covariance_p)
        derived = {
            "sine_precision": q,
            "precision_diagonal": np.diag(q),
            "minimum_precision_eigenvalue": float(np.linalg.eigvalsh(q)[0]),
            "global_poincare_gap": float(2.0 * np.linalg.eigvalsh(q)[0]),
            "conditional_poincare_gaps": 2.0 * np.diag(q),
            "marginal_precision": q_eff,
            "retained_position_covariance": covariance_q,
            "retained_momentum_covariance": covariance_p,
            "pure_marginal_momentum_covariance": q_eff / 2.0,
            "discarded_momentum_term": difference,
            "symplectic_eigenvalues": symplectic_values,
        }
        fields = {
            "sine_precision": row.get("sine_precision"),
            "precision_diagonal": row.get("precision_diagonal"),
            "minimum_precision_eigenvalue": row.get("minimum_precision_eigenvalue"),
            "global_poincare_gap": row.get("global_poincare_gap"),
            "conditional_poincare_gaps": row.get("conditional_poincare_gaps"),
            "marginal_precision": row.get("marginal_precision"),
            "retained_position_covariance": row.get("retained_position_covariance"),
            "retained_momentum_covariance": row.get("retained_momentum_covariance"),
            "pure_marginal_momentum_covariance": row.get("pure_marginal_momentum_covariance"),
            "discarded_momentum_term": row.get("discarded_momentum_term"),
            "symplectic_eigenvalues": row.get("symplectic_eigenvalues"),
        }
        row_errors = {}
        row_good = True
        for field, expected in derived.items():
            error = normalized_error(fields[field], expected)
            row_errors[field] = error
            max_matrix_difference = max(max_matrix_difference, error)
            row_good = row_good and error <= MATRIX_TOLERANCE
        expected_minimum = math.sqrt(mass * mass
                                     + 4.0 * math.sin(math.pi / (2.0 * (size + 1))) ** 2)
        row_good = row_good and abs(derived["minimum_precision_eigenvalue"] - expected_minimum) <= MATRIX_TOLERANCE
        check(checks, f"independent Gaussian reconstruction N={size} m={mass}", row_good,
              {"maximum_normalized_difference": max(row_errors.values()),
               "minimum_eigenvalue_error": abs(derived["minimum_precision_eigenvalue"] - expected_minimum)},
              MATRIX_TOLERANCE)
        check(checks, f"Gaussian mixed-state witness N={size} m={mass}",
              float(np.min(symplectic_values)) >= 0.5 - MATRIX_TOLERANCE
              and float(np.max(symplectic_values)) > 0.500001,
              {"minimum": float(np.min(symplectic_values)),
               "maximum": float(np.max(symplectic_values))})
    uncoupled = np.diag((1.0, 2.0, 3.0, 4.0))
    retained, eliminated = np.array((0, 2)), np.array((1, 3))
    q_rr = uncoupled[np.ix_(retained, retained)]
    q_re = uncoupled[np.ix_(retained, eliminated)]
    q_ee = uncoupled[np.ix_(eliminated, eliminated)]
    q_eff = q_rr - q_re @ np.linalg.solve(q_ee, q_re.T)
    cov_q = np.linalg.inv(uncoupled)[np.ix_(retained, retained)] / 2.0
    uncoupled_symplectic = symplectic(cov_q, q_rr / 2.0)
    stored = primary.get("uncoupled_gaussian", {})
    check(checks, "uncoupled Gaussian zero-coupling control",
          close(stored.get("marginal_precision"), q_eff)
          and close(stored.get("momentum_difference"), (q_rr - q_eff) / 2.0)
          and close(stored.get("symplectic_eigenvalues"), uncoupled_symplectic)
          and close(q_eff, q_rr),
          {"symplectic": uncoupled_symplectic.tolist()})
    return {"rows": len(rows), "maximum_normalized_difference": max_matrix_difference}


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
        details[key] = {"path": repo_rel(expected_path), "snapshot": snapshot.name,
                        "pass": item_good}
    check(checks, "primary source manifest and snapshots", good, details)
    return {"manifest_sha256": raw_sha256(manifest_path),
            "receipt_sha256": raw_sha256(primary)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path,
                        default=ROOT / "runs/yang_mills_vacuum_blocks_recovery_20260914/verification.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "runs/yang_mills_vacuum_blocks_recovery_20260914/verification-independent.json")
    args = parser.parse_args()
    primary = args.primary.resolve()
    output = args.output.resolve()
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh independent output path: {output}")
    checks: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.vacuum-blocks.independent-reconciliation.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "primary": repo_rel(primary),
    }
    success = False
    try:
        primary_result = load_json(primary)
        source_info = validate_primary_snapshot(primary, checks)
        check(checks, "primary receipt status and finite payload",
              primary_result.get("schema") == "cassi.yang-mills.vacuum-blocks.v1"
              and primary_result.get("status") == "PASS"
              and primary_result.get("failures") == []
              and finite(primary_result),
              {"schema": primary_result.get("schema"),
               "status": primary_result.get("status"),
               "failures": len(primary_result.get("failures", []))})
        group_summary = reconstruct_group(primary_result, checks)
        gaussian_summary = reconstruct_gaussian(primary_result, checks)
        analytic = primary_result.get("analytic_formulas", {})
        required_analytic = {"ground_state_transform", "physical_gap", "weighted_cover_gap",
                             "continuum_target", "trial_local_energy", "trial_adjoint_projection",
                             "shared_link_fierz", "weak_vacuum_kernel", "weak_mode_frequency",
                             "trial_kernel", "ir_beta_limit", "fixed_map_linearization"}
        check(checks, "analytic formula inventory remains explicit",
              required_analytic <= set(analytic)
              and all(isinstance(analytic[key], str) and analytic[key] for key in required_analytic),
              {"required": len(required_analytic), "actual": len(analytic)})
        classifications = primary_result.get("classifications", {})
        expected_pending = {
            "exact_trial_vacuum": "REQUIRES_ANALYTICAL_RECONCILIATION",
            "weighted_cover_gap": "REQUIRES_ANALYTICAL_RECONCILIATION",
            "exact_quantum_block_map": "REQUIRES_ANALYTICAL_RECONCILIATION",
            "continuum_mass_gap": "UNRESOLVED",
        }
        check(checks, "analytical and continuum boundaries remain frozen",
              all(classifications.get(key) == value for key, value in expected_pending.items()),
              {"actual": classifications, "expected": expected_pending})
        success = all(row["pass"] for row in checks)
        result.update(
            primary_receipt_sha256=source_info["receipt_sha256"],
            primary_manifest_sha256=source_info["manifest_sha256"],
            checks=checks, check_count=len(checks),
            failures=[row for row in checks if not row["pass"]],
            reconstruction=dict(group=group_summary, gaussian=gaussian_summary),
            classification_stage="NUMERICAL_RECONCILIATION_ONLY",
            classifications={
                "finite_group_and_derivative_controls": "RECONCILED_NUMERICALLY_REVIEW_REQUIRED",
                "Gaussian_block_identities": "RECONCILED_NUMERICALLY_REVIEW_REQUIRED",
                "conditional_gap_only_uniform_implication": "RECONCILED_NUMERICALLY_REVIEW_REQUIRED",
                "exact_trial_vacuum": "REQUIRES_ANALYTICAL_RECONCILIATION",
                "weighted_cover_gap": "REQUIRES_ANALYTICAL_RECONCILIATION",
                "exact_quantum_block_map": "REQUIRES_ANALYTICAL_RECONCILIATION",
                "continuum_mass_gap": "UNRESOLVED",
            },
            scope=dict(interacting_vacuum_tensorization="UNRESOLVED",
                       infinite_volume_GNS_gap="NOT_ESTABLISHED",
                       continuum_construction="UNRESOLVED", continuum_mass="UNRESOLVED",
                       cassi_microscopic_identification="UNRESOLVED"),
            status="PASS" if success else "FAIL")
    except Exception as exc:
        result.update(status="ERROR", checks=checks, check_count=len(checks),
                      failures=[{"error": str(exc)}],
                      error=f"{type(exc).__name__}: {exc}")

    sources = {"protocol": PROTOCOL, "primary_verifier": PRIMARY_VERIFIER,
               "receipt_helper": RECEIPT_HELPER, "independent_reconciler": Path(__file__).resolve()}
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {key: {"path": repo_rel(path), "sha256": hashlib.sha256(payloads[key]).hexdigest()}
                  for key, path in sources.items()}
    result["identities"] = identities
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for path in sources.values():
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
