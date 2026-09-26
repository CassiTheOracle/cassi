#!/usr/bin/env python
"""Run the frozen Cassi P-versus-NP crossover probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
SEED = 20260909
BETA = PHI**2
BOOLEAN_LAMBDA = 0.25
DAMPING = 0.35
COHERENCE_DT = 0.01
STATIC_DT = 0.02
CTDS_DT = 0.01
MAX_VARIABLE_DELTA = 0.02
MAX_STEPS = 12000
STARTS = 4
STRUCTURAL_N = 4
STRUCTURAL_STEPS = 2000
STRUCTURAL_DT = 0.001
STRUCTURAL_OMEGA2 = 20.0
CAP_CTDS = 64.0
EXP_CTDS = 1.0e12

Literal = tuple[int, int]
Formula = tuple[tuple[Literal, ...], ...]


@dataclass(frozen=True)
class Case:
    name: str
    family: str
    n: int
    clauses: Formula
    expected_sat: bool
    local_minima: int | None = None


def clause_products(s: np.ndarray, clauses: Formula) -> tuple[np.ndarray, list[np.ndarray]]:
    values = np.empty(len(clauses), dtype=np.float64)
    others: list[np.ndarray] = []
    for m, clause in enumerate(clauses):
        factors = np.array([(1.0 - sign * s[var]) * 0.5 for var, sign in clause])
        values[m] = float(np.prod(factors))
        products = np.empty(len(clause), dtype=np.float64)
        for j in range(len(clause)):
            products[j] = float(np.prod(np.delete(factors, j)))
        others.append(products)
    return values, others


def certified(s: np.ndarray, clauses: Formula) -> tuple[bool, int, float]:
    assignment = s >= 0.0
    violated = 0
    for clause in clauses:
        if not any(bool(assignment[var]) == (sign > 0) for var, sign in clause):
            violated += 1
    return violated == 0, violated, float(np.min(np.abs(s)))


def all_assignments(n: int) -> np.ndarray:
    integers = np.arange(1 << n, dtype=np.uint32)[:, None]
    bits = ((integers >> np.arange(n, dtype=np.uint32)) & 1).astype(np.int8)
    return bits * 2 - 1


def violated_counts(states: np.ndarray, clauses: Formula) -> np.ndarray:
    counts = np.zeros(states.shape[0], dtype=np.int32)
    for clause in clauses:
        clause_true = np.zeros(states.shape[0], dtype=bool)
        for var, sign in clause:
            clause_true |= states[:, var] == sign
        counts += ~clause_true
    return counts


def exact_sat(n: int, clauses: Formula) -> bool:
    return bool(np.any(violated_counts(all_assignments(n), clauses) == 0))


def local_minima_count(n: int, clauses: Formula) -> int:
    counts = violated_counts(all_assignments(n), clauses)
    answer = 0
    for state in range(1 << n):
        if counts[state] == 0:
            continue
        if all(counts[state] <= counts[state ^ (1 << bit)] for bit in range(n)):
            answer += 1
    return answer


def planted_formula(
    rng: np.random.Generator,
    n: int,
    m: int,
    width: int,
    plant: np.ndarray,
) -> Formula:
    clauses: list[tuple[Literal, ...]] = []
    for _ in range(m):
        variables = rng.choice(n, size=width, replace=False)
        while True:
            signs = rng.choice(np.array([-1, 1], dtype=np.int8), size=width)
            if np.any(signs == plant[variables]):
                break
        clauses.append(tuple((int(var), int(sign)) for var, sign in zip(variables, signs)))
    return tuple(clauses)


def xor_clauses(variables: Iterable[int], parity: int) -> list[tuple[Literal, ...]]:
    variables = tuple(int(variable) for variable in variables)
    clauses: list[tuple[Literal, ...]] = []
    for mask in range(8):
        state = tuple(1 if mask & (1 << bit) else -1 for bit in range(3))
        if math.prod(state) != parity:
            clauses.append(tuple((variables[j], -state[j]) for j in range(3)))
    return clauses


def build_corpus() -> tuple[list[Case], dict[str, Any]]:
    rng = np.random.default_rng(SEED)
    cases: list[Case] = []

    universe = tuple(
        tuple((var, 1 if mask & (1 << var) else -1) for var in range(3))
        for mask in range(8)
    )
    for subset in range(1, 1 << 8):
        clauses = tuple(universe[index] for index in range(8) if subset & (1 << index))
        cases.append(Case(f"exhaustive3_{subset:03d}", "exhaustive3", 3, clauses, exact_sat(3, clauses)))

    for index in range(12):
        plant = rng.choice(np.array([-1, 1], dtype=np.int8), size=8)
        clauses = planted_formula(rng, 8, 16, 2, plant)
        cases.append(Case(f"planted2_{index:02d}", "planted2", 8, clauses, True))

    planted_3sat: dict[int, list[Formula]] = {}
    for n in (6, 8, 10, 12):
        planted_3sat[n] = []
        for index in range(8):
            plant = rng.choice(np.array([-1, 1], dtype=np.int8), size=n)
            clauses = planted_formula(rng, n, round(4.2 * n), 3, plant)
            assert exact_sat(n, clauses)
            planted_3sat[n].append(clauses)
            cases.append(Case(f"planted3_n{n}_{index:02d}", "planted3", n, clauses, True))

    for n in (6, 8, 10, 12):
        for index in range(2):
            plant = rng.choice(np.array([-1, 1], dtype=np.int8), size=n)
            clauses_list: list[tuple[Literal, ...]] = []
            for _ in range(max(2, n // 2)):
                variables = rng.choice(n, size=3, replace=False)
                parity = int(np.prod(plant[variables]))
                clauses_list.extend(xor_clauses(variables, parity))
            clauses = tuple(clauses_list)
            assert exact_sat(n, clauses)
            cases.append(Case(f"xor3_n{n}_{index:02d}", "xor3", n, clauses, True))

    adversarial_choices: dict[str, Any] = {}
    for n in (6, 8, 10, 12):
        best_formula: Formula | None = None
        best_count = -1
        best_index = -1
        for index in range(128):
            plant = np.ones(n, dtype=np.int8)
            clauses = planted_formula(rng, n, round(4.2 * n), 3, plant)
            count = local_minima_count(n, clauses)
            if count > best_count:
                best_formula = clauses
                best_count = count
                best_index = index
        assert best_formula is not None and exact_sat(n, best_formula)
        adversarial_choices[str(n)] = {"candidate_index": best_index, "local_minima": best_count}
        cases.append(Case(f"adversarial_n{n}", "adversarial", n, best_formula, True, best_count))

    pigeonhole: list[tuple[Literal, ...]] = []
    for pigeon in range(3):
        pigeonhole.append(((2 * pigeon, 1), (2 * pigeon + 1, 1)))
    for hole in range(2):
        for first in range(3):
            for second in range(first + 1, 3):
                pigeonhole.append(((2 * first + hole, -1), (2 * second + hole, -1)))
    pigeonhole_formula = tuple(pigeonhole)
    assert not exact_sat(6, pigeonhole_formula)
    cases.append(Case("pigeonhole_3_2", "unsat_control", 6, pigeonhole_formula, False))

    inconsistent = tuple(xor_clauses((0, 1, 2), 1) + xor_clauses((0, 1, 2), -1))
    assert not exact_sat(3, inconsistent)
    cases.append(Case("inconsistent_xor", "unsat_control", 3, inconsistent, False))

    base = planted_3sat[8][0]
    permutation = rng.permutation(8)
    permuted = tuple(
        tuple((int(permutation[var]), sign) for var, sign in clause)
        for clause in reversed(base)
    )
    representation = {
        "base": serial_formula(base),
        "permuted": serial_formula(permuted),
        "old_to_new": permutation.tolist(),
        "padded_n": 16,
    }
    return cases, {"adversarial_choices": adversarial_choices, "representation": representation}


def serial_formula(clauses: Formula) -> list[list[list[int]]]:
    return [[[var, sign] for var, sign in clause] for clause in clauses]


def coherence_gradient(s: np.ndarray, clauses: Formula) -> tuple[np.ndarray, float]:
    k, others = clause_products(s, clauses)
    gradient = np.zeros_like(s)
    for m, clause in enumerate(clauses):
        derivative = 2.0 * BETA * k[m] / (1.0 + BETA * k[m] ** 2) ** 2
        for j, (var, sign) in enumerate(clause):
            gradient[var] += derivative * (-0.5 * sign * others[m][j])
    gradient += BOOLEAN_LAMBDA * s * (s * s - 1.0)
    energy = float(np.sum(BETA * k * k / (1.0 + BETA * k * k)))
    energy += float(0.25 * BOOLEAN_LAMBDA * np.sum((s * s - 1.0) ** 2))
    return gradient, energy


def static_gradient(s: np.ndarray, clauses: Formula) -> tuple[np.ndarray, float]:
    k, others = clause_products(s, clauses)
    gradient = np.zeros_like(s)
    for m, clause in enumerate(clauses):
        for j, (var, sign) in enumerate(clause):
            gradient[var] += 2.0 * k[m] * (-0.5 * sign * others[m][j])
    return gradient, float(np.sum(k * k))


def base_record(arm: str, case: Case, start: int, s: np.ndarray) -> dict[str, Any]:
    solved, violated, margin = certified(s, case.clauses)
    return {
        "arm": arm,
        "case": case.name,
        "family": case.family,
        "n": case.n,
        "m": len(case.clauses),
        "expected_sat": case.expected_sat,
        "start": start,
        "success": solved,
        "first_solution_step": 0 if solved else None,
        "steps": 0,
        "physical_time": 0.0,
        "derivative_evaluations": 0,
        "clamp_count": 0,
        "max_abs_s": float(np.max(np.abs(s))),
        "max_abs_velocity": 0.0,
        "max_abs_gradient": 0.0,
        "max_clause_weight": 1.0,
        "max_log2_clause_weight": 0.0,
        "success_margin": margin if solved else None,
        "final_violated": violated,
        "final_state": s.tolist(),
    }


def finalize_record(
    record: dict[str, Any],
    s: np.ndarray,
    clauses: Formula,
    step: int,
    time: float,
) -> dict[str, Any]:
    solved, violated, margin = certified(s, clauses)
    record["steps"] = step
    record["physical_time"] = time
    record["success"] = solved
    record["final_violated"] = violated
    record["final_state"] = s.tolist()
    if solved and record["first_solution_step"] is None:
        record["first_solution_step"] = step
        record["success_margin"] = margin
    return record


def run_coherence(case: Case, initial: np.ndarray, start: int) -> dict[str, Any]:
    s = initial.copy()
    velocity = np.zeros_like(s)
    record = base_record("coherence", case, start, s)
    if record["success"]:
        return record
    for step in range(1, MAX_STEPS + 1):
        gradient, _ = coherence_gradient(s, case.clauses)
        record["derivative_evaluations"] += 1
        record["max_abs_gradient"] = max(record["max_abs_gradient"], float(np.max(np.abs(gradient))))
        velocity += COHERENCE_DT * (-DAMPING * velocity - gradient)
        proposed = s + COHERENCE_DT * velocity
        clipped = np.clip(proposed, -1.0, 1.0)
        hit = clipped != proposed
        if np.any(hit):
            record["clamp_count"] += int(np.count_nonzero(hit))
            velocity[hit & (np.sign(velocity) == np.sign(proposed))] = 0.0
        s = clipped
        record["max_abs_s"] = max(record["max_abs_s"], float(np.max(np.abs(s))))
        record["max_abs_velocity"] = max(record["max_abs_velocity"], float(np.max(np.abs(velocity))))
        solved, _, margin = certified(s, case.clauses)
        if solved:
            record["first_solution_step"] = step
            record["success_margin"] = margin
            break
    return finalize_record(record, s, case.clauses, step, step * COHERENCE_DT)


def run_static(case: Case, initial: np.ndarray, start: int) -> dict[str, Any]:
    s = initial.copy()
    record = base_record("static_gradient", case, start, s)
    if record["success"]:
        return record
    for step in range(1, MAX_STEPS + 1):
        gradient, _ = static_gradient(s, case.clauses)
        record["derivative_evaluations"] += 1
        record["max_abs_gradient"] = max(record["max_abs_gradient"], float(np.max(np.abs(gradient))))
        proposed = s - STATIC_DT * gradient
        s = np.clip(proposed, -1.0, 1.0)
        record["clamp_count"] += int(np.count_nonzero(s != proposed))
        record["max_abs_s"] = max(record["max_abs_s"], float(np.max(np.abs(s))))
        solved, _, margin = certified(s, case.clauses)
        if solved:
            record["first_solution_step"] = step
            record["success_margin"] = margin
            break
    return finalize_record(record, s, case.clauses, step, step * STATIC_DT)


def ctds_force(s: np.ndarray, clauses: Formula, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    k, others = clause_products(s, clauses)
    force = np.zeros_like(s)
    for m, clause in enumerate(clauses):
        for j, (var, sign) in enumerate(clause):
            force[var] += weights[m] * 2.0 * k[m] * sign * others[m][j]
    return force, k


def run_ctds(case: Case, initial: np.ndarray, start: int, cap: float, arm: str) -> dict[str, Any]:
    s = initial.copy()
    weights = np.ones(len(case.clauses), dtype=np.float64)
    record = base_record(arm, case, start, s)
    if record["success"]:
        return record
    elapsed = 0.0
    for step in range(1, MAX_STEPS + 1):
        force, k = ctds_force(s, case.clauses, weights)
        max_force = float(np.max(np.abs(force))) if force.size else 0.0
        dt = min(CTDS_DT, MAX_VARIABLE_DELTA / max_force) if max_force > 0.0 else CTDS_DT
        proposed = s + dt * force
        s = np.clip(proposed, -1.0, 1.0)
        record["clamp_count"] += int(np.count_nonzero(s != proposed))
        weights = np.minimum(cap, weights * np.exp(np.minimum(dt * k, 700.0)))
        elapsed += dt
        record["derivative_evaluations"] += 1
        record["max_abs_gradient"] = max(record["max_abs_gradient"], max_force)
        record["max_abs_s"] = max(record["max_abs_s"], float(np.max(np.abs(s))))
        record["max_clause_weight"] = max(record["max_clause_weight"], float(np.max(weights)))
        solved, _, margin = certified(s, case.clauses)
        if solved:
            record["first_solution_step"] = step
            record["success_margin"] = margin
            break
    record["max_log2_clause_weight"] = math.log2(record["max_clause_weight"])
    return finalize_record(record, s, case.clauses, step, elapsed)


def laplacian_19(field: np.ndarray) -> np.ndarray:
    result = -12.0 * field
    for axis in range(3):
        result += np.roll(field, 1, axis=axis) + np.roll(field, -1, axis=axis)
    for first, second in ((0, 1), (0, 2), (1, 2)):
        for a in (-1, 1):
            for b in (-1, 1):
                result += 0.5 * np.roll(np.roll(field, a, axis=first), b, axis=second)
    return result


def field_step(
    ey: np.ndarray,
    ei: np.ndarray,
    vy: np.ndarray,
    vi: np.ndarray,
    source_y: np.ndarray | float = 0.0,
    source_i: np.ndarray | float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    epsilon = ey - PHI * ei
    vy = vy + STRUCTURAL_DT * (laplacian_19(ey) - STRUCTURAL_OMEGA2 * epsilon + source_y)
    vi = vi + STRUCTURAL_DT * (laplacian_19(ei) + STRUCTURAL_OMEGA2 * epsilon + source_i)
    ey = ey + STRUCTURAL_DT * vy
    ei = ei + STRUCTURAL_DT * vi
    return ey, ei, vy, vi


def invariant(ey: np.ndarray, ei: np.ndarray, vy: np.ndarray, vi: np.ndarray) -> float:
    epsilon = ey - PHI * ei
    kinetic = float(np.sum(vy * vy + PHI * vi * vi))
    potential = float(np.sum(-ey * laplacian_19(ey) - PHI * ei * laplacian_19(ei)))
    potential += STRUCTURAL_OMEGA2 * float(np.sum(epsilon * epsilon))
    cross = float(np.sum(-ey * laplacian_19(vy) - PHI * ei * laplacian_19(vi)))
    cross += STRUCTURAL_OMEGA2 * float(np.sum(epsilon * (vy - PHI * vi)))
    return 0.5 * (kinetic + potential - STRUCTURAL_DT * cross)


def structural_probe() -> dict[str, float | str]:
    rng = np.random.default_rng(SEED + 1)
    shape = (STRUCTURAL_N,) * 3
    ey0, ei0, vy0, vi0 = (rng.normal(scale=0.2, size=shape) for _ in range(4))
    ey, ei, vy, vi = (array.copy() for array in (ey0, ei0, vy0, vi0))
    r = ey0 + ei0
    epsilon = ey0 - PHI * ei0
    vr = vy0 + vi0
    vepsilon = vy0 - PHI * vi0
    initial_invariant = invariant(ey, ei, vy, vi)
    max_parity = 0.0
    max_drift = 0.0
    for _ in range(STRUCTURAL_STEPS):
        ey, ei, vy, vi = field_step(ey, ei, vy, vi)
        vr += STRUCTURAL_DT * laplacian_19(r)
        vepsilon += STRUCTURAL_DT * (laplacian_19(epsilon) - PHI**2 * STRUCTURAL_OMEGA2 * epsilon)
        r += STRUCTURAL_DT * vr
        epsilon += STRUCTURAL_DT * vepsilon
        reconstructed_y = (PHI * r + epsilon) / PHI**2
        reconstructed_i = (r - epsilon) / PHI**2
        max_parity = max(
            max_parity,
            float(np.max(np.abs(ey - reconstructed_y))),
            float(np.max(np.abs(ei - reconstructed_i))),
        )
        max_drift = max(max_drift, abs(invariant(ey, ei, vy, vi) - initial_invariant) / initial_invariant)

    a = [rng.normal(scale=0.1, size=shape) for _ in range(4)]
    b = [rng.normal(scale=0.1, size=shape) for _ in range(4)]
    combined = [a[index] + b[index] for index in range(4)]
    for _ in range(STRUCTURAL_STEPS):
        a = list(field_step(*a))
        b = list(field_step(*b))
        combined = list(field_step(*combined))
    superposition = max(float(np.max(np.abs(combined[index] - a[index] - b[index]))) for index in range(4))

    lap_eigenvalue = -8.0
    source_r = 0.17
    source_epsilon = -0.11
    gap_eigenvalue = lap_eigenvalue - PHI**2 * STRUCTURAL_OMEGA2
    dt = STRUCTURAL_DT
    matrix = np.array(
        [
            [1 + dt * dt * lap_eigenvalue, dt, 0, 0, dt * dt * source_r],
            [dt * lap_eigenvalue, 1, 0, 0, dt * source_r],
            [0, 0, 1 + dt * dt * gap_eigenvalue, dt, dt * dt * source_epsilon],
            [0, 0, dt * gap_eigenvalue, 1, dt * source_epsilon],
            [0, 0, 0, 0, 1],
        ],
        dtype=np.float64,
    )
    state = np.array([0.2, -0.3, 0.4, 0.1, 1.0], dtype=np.float64)
    iterated = state.copy()
    for _ in range(STRUCTURAL_STEPS):
        iterated = matrix @ iterated
    powered = np.linalg.matrix_power(matrix, STRUCTURAL_STEPS) @ state
    fast_forward = float(np.max(np.abs(iterated - powered)))

    maximum = max(max_parity, max_drift, superposition, fast_forward)
    return {
        "normal_mode_parity_max_abs": max_parity,
        "weighted_invariant_max_relative_drift": max_drift,
        "superposition_max_abs": superposition,
        "affine_fast_forward_max_abs": fast_forward,
        "maximum_residual": maximum,
        "verdict": "PASS" if maximum <= 1.0e-9 else "FAIL",
    }


def representation_probe(representation: dict[str, Any]) -> dict[str, float | str]:
    base: Formula = tuple(tuple((int(v), int(sign)) for v, sign in clause) for clause in representation["base"])
    permuted: Formula = tuple(tuple((int(v), int(sign)) for v, sign in clause) for clause in representation["permuted"])
    permutation = np.array(representation["old_to_new"], dtype=np.int64)
    rng = np.random.default_rng(SEED + 2)
    original = rng.uniform(-0.5, 0.5, size=8)
    mapped = np.empty(8, dtype=np.float64)
    mapped[permutation] = original
    base_gradient, _ = coherence_gradient(original, base)
    permuted_gradient, _ = coherence_gradient(mapped, permuted)
    permutation_residual = float(np.max(np.abs(base_gradient - permuted_gradient[permutation])))

    padded = np.concatenate((original, rng.uniform(-0.5, 0.5, size=8)))
    padded_gradient, _ = coherence_gradient(padded, base)
    irrelevant_residual = float(np.max(np.abs(base_gradient - padded_gradient[:8])))
    maximum = max(permutation_residual, irrelevant_residual)
    return {
        "permutation_vector_field_max_abs": permutation_residual,
        "irrelevant_variable_vector_field_max_abs": irrelevant_residual,
        "maximum_residual": maximum,
        "verdict": "PASS" if maximum <= 1.0e-12 else "FAIL",
    }


def aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    keys = sorted({(run["arm"], run["family"], run["n"]) for run in runs})
    for arm, family, n in keys:
        selected = [run for run in runs if run["arm"] == arm and run["family"] == family and run["n"] == n]
        successful = [run for run in selected if run["success"]]
        result[f"{arm}/{family}/n{n}"] = {
            "runs": len(selected),
            "successes": len(successful),
            "success_rate": len(successful) / len(selected),
            "median_solution_steps": float(np.median([run["first_solution_step"] for run in successful])) if successful else None,
            "max_solution_steps": max((run["first_solution_step"] for run in successful), default=None),
            "max_derivative_evaluations": max(run["derivative_evaluations"] for run in selected),
            "max_clause_weight": max(run["max_clause_weight"] for run in selected),
            "max_log2_clause_weight": max(run["max_log2_clause_weight"] for run in selected),
            "min_success_margin": min((run["success_margin"] for run in successful), default=None),
            "total_clamps": sum(run["clamp_count"] for run in selected),
        }
    return result


def decide(runs: list[dict[str, Any]], structural: dict[str, Any], representation: dict[str, Any]) -> dict[str, str]:
    coherence_sat = [run for run in runs if run["arm"] == "coherence" and run["expected_sat"]]
    coherence_unsat = [run for run in runs if run["arm"] == "coherence" and not run["expected_sat"]]
    s2_ok = (
        all(run["success"] for run in coherence_sat)
        and not any(run["success"] for run in coherence_unsat)
        and min((run["success_margin"] or 0.0 for run in coherence_sat), default=0.0) >= 1.0e-3
    )

    capped = {(run["case"], run["start"]): run for run in runs if run["arm"] == "capped_ctds"}
    expanded = {(run["case"], run["start"]): run for run in runs if run["arm"] == "exp_ctds"}
    s3_ok = True
    for key, expanded_run in expanded.items():
        if not expanded_run["expected_sat"]:
            continue
        capped_run = capped[key]
        if capped_run["success"] != expanded_run["success"]:
            s3_ok = False
        if expanded_run["success"] and expanded_run["max_clause_weight"] > CAP_CTDS and not capped_run["success"]:
            s3_ok = False

    verdicts = {
        "S1_linear_structure": structural["verdict"],
        "S2_bounded_coherence": "SUPPORTS" if s2_ok else "CONTRADICTS",
        "S3_bounded_clause_memory": "SUPPORTS" if s3_ok else "CONTRADICTS",
        "S4_representation_invariance": representation["verdict"],
    }
    all_resources_finite = all(
        math.isfinite(float(value))
        for run in runs
        for key, value in run.items()
        if key.startswith("max_") and value is not None
    )
    verdicts["overall"] = (
        "ADOPT"
        if structural["verdict"] == "PASS"
        and s2_ok
        and s3_ok
        and representation["verdict"] == "PASS"
        and all_resources_finite
        else "REJECT"
    )
    return verdicts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="_diag/p_vs_np_probe.json")
    args = parser.parse_args()

    cases, metadata = build_corpus()
    structural = structural_probe()
    representation = representation_probe(metadata["representation"])
    rng = np.random.default_rng(SEED + 3)
    runs: list[dict[str, Any]] = []
    for case_index, case in enumerate(cases):
        if case_index % 32 == 0:
            print(f"case {case_index + 1}/{len(cases)}: {case.name}", flush=True)
        for start in range(STARTS):
            initial = rng.uniform(-0.5, 0.5, size=case.n)
            runs.append(run_coherence(case, initial, start))
            runs.append(run_static(case, initial, start))
            runs.append(run_ctds(case, initial, start, CAP_CTDS, "capped_ctds"))
            runs.append(run_ctds(case, initial, start, EXP_CTDS, "exp_ctds"))

    prereg_path = Path(__file__).with_name("p_vs_np_prereg.md")
    receipt = {
        "schema": "cassi.p-vs-np-probe.v1",
        "seed": SEED,
        "prereg_sha256": hashlib.sha256(prereg_path.read_bytes()).hexdigest(),
        "parameters": {
            "phi": PHI,
            "beta": BETA,
            "boolean_lambda": BOOLEAN_LAMBDA,
            "damping": DAMPING,
            "coherence_dt": COHERENCE_DT,
            "static_dt": STATIC_DT,
            "ctds_dt": CTDS_DT,
            "max_variable_delta": MAX_VARIABLE_DELTA,
            "max_steps": MAX_STEPS,
            "starts": STARTS,
            "capped_ctds": CAP_CTDS,
            "expanded_ctds": EXP_CTDS,
        },
        "structural": structural,
        "representation": representation,
        "corpus_metadata": metadata,
        "cases": [
            {
                "name": case.name,
                "family": case.family,
                "n": case.n,
                "clauses": serial_formula(case.clauses),
                "expected_sat": case.expected_sat,
                "local_minima": case.local_minima,
            }
            for case in cases
        ],
        "runs": runs,
        "aggregate": aggregate(runs),
    }
    receipt["verdicts"] = decide(runs, structural, representation)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt["verdicts"], indent=2))
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
