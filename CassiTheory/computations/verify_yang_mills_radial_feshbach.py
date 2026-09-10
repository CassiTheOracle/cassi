#!/usr/bin/env python3
"""Run the frozen continuous-SU(2) isolated-square radial Feshbach campaign.

The computation is deliberately finite: it verifies exact identities, finite
Jacobi sections, the Weyl self-energy, resolvent brackets, and the five frozen
character cutoffs.  The receipt keeps the analytical assertions separate from
these numerical controls; it does not assert an interacting fibre, a volume
limit, a continuum mass gap, or a microscopic Cassi identification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()
PROTOCOL = ROOT / "computations/yang-mills-radial-feshbach-prereg.md"
INDEPENDENT = ROOT / "computations/verify_yang_mills_radial_feshbach_independent.mjs"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_radial_feshbach/verification.json"

RECEIPT_SCHEMA = "cassi.yang-mills.radial-feshbach.v1"
MANIFEST_SCHEMA = "cassi.yang-mills.radial-feshbach.inputs.v1"
EXPECTED_PROTOCOL_SHA256 = (
    "ebf74019ad289f7619149baff4c1a82beefa3bac560aa8f6b43ce047c2dbb99c"
)
SOURCE_KEYS = ("protocol", "primary", "independent")
EXPECTED_SOURCE_BASENAMES = {
    "protocol": PROTOCOL.name,
    "primary": SELF_PATH.name,
    "independent": INDEPENDENT.name,
}

# Every value below is frozen by the preregistration.  Keep the declarations
# independent of any other Yang-Mills verifier.
X_VALUES = (0.25, 1.0, 16.0, 256.0, 4096.0, 65536.0)
J_VALUES = (0, 1, 2)
SCHEDULE_NAMES = ("fixed", "C", "iso", "grow", "half")
DIRECT_TAIL_LENGTHS = (32, 64)
SYMBOLIC_X_VALUES = (sp.Rational(1, 4), sp.Integer(1), sp.Integer(4))
SYMBOLIC_N_VALUES = (0, 2)
SYMBOLIC_M_VALUES = (6, 8)
SYMBOLIC_Z_VALUES = (-1, 0)
CF_BASE_N_VALUES = (0, 1, 3, 7)
CF_ENERGY_LABELS = ("minus_one", "minus_sqrt_x", "zero")
REFERENCE_LEVELS = 3
REFERENCE_RTOL = 1e-10
CF_RTOL = 1e-11
DERIVATIVE_RTOL = 1e-6
RESOLVENT_SLACK = 1e-10
FESHBACH_RTOL = 1e-9
TAIL_NORM_RTOL = 1e-8
RF20_SLACK = 1e-11


def k_value(n: int) -> float:
    """The frozen electric eigenvalue ``k_n=n(n+2)``."""
    return float(n * (n + 2))


def d_value(n: int, x: float) -> float:
    """The diagonal ``d_n=k_n+2x`` of ``h_x``."""
    return k_value(n) + 2.0 * float(x)


def normalized_error(actual: float, expected: float) -> float:
    """Stable normalized discrepancy used for all numerical comparisons."""
    actual = float(actual)
    expected = float(expected)
    return abs(actual - expected) / max(1.0, abs(actual), abs(expected))


def vector_normalized_error(actual: Any, expected: Any) -> float:
    left = np.asarray(actual, dtype=float)
    right = np.asarray(expected, dtype=float)
    return float(np.max(np.abs(left - right) /
                        np.maximum(1.0, np.maximum(np.abs(left), np.abs(right)))))


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(float(value))


def all_numbers_finite(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(all_numbers_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(all_numbers_finite(item) for item in value)
    return True


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_raw(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def record_check(result: dict[str, Any], name: str, passed: bool,
                 detail: Any) -> None:
    """Append one uniquely named check and fail closed on duplicate checks."""
    if any(row.get("name") == name for row in result["checks"]):
        raise ValueError(f"duplicate check name: {name}")
    passed = bool(passed)
    result["checks"].append({"name": name, "passed": passed, "detail": detail})
    if not passed:
        result["failures"].append(name)


def exact_residual(actual: Any, expected: Any) -> tuple[bool, str]:
    """Return an exact SymPy equality result and a printable residual."""
    difference = actual - expected
    if isinstance(difference, sp.MatrixBase):
        reduced = difference.applyfunc(sp.simplify)
        passed = all(item == 0 for item in reduced)
        return passed, str(reduced)
    reduced = sp.simplify(difference)
    return bool(reduced == 0), str(reduced)


def add_symbolic_row(result: dict[str, Any], name: str, identity: str,
                     actual: Any, expected: Any) -> None:
    passed, residual = exact_residual(actual, expected)
    result["symbolic_rows"].append({
        "name": name,
        "identity": identity,
        "passed": passed,
        "residual": residual,
    })
    record_check(result, f"symbolic:{name}", passed, {"residual": residual})


# ---------------------------------------------------------------------------
# Frozen schedule and Jacobi construction
# ---------------------------------------------------------------------------


def cutoff_schedule(x: float) -> dict[str, int]:
    x = float(x)
    quarter = x ** 0.25
    return {
        "fixed": 8,
        "C": int(math.ceil(2.0 * quarter)),
        "iso": int(math.ceil(4.0 * quarter)),
        "grow": int(math.ceil(quarter * math.log(2.0 + x))),
        "half": int(math.ceil(2.0 * math.sqrt(x))),
    }


def n_control_values(x: float) -> tuple[int, ...]:
    schedules = cutoff_schedule(x)
    return tuple(sorted(set(CF_BASE_N_VALUES) | set(schedules.values())))


def energy_control_values(x: float) -> tuple[float, ...]:
    # x=1 has the intentional duplicate -1=-sqrt(x); retain one row because
    # the preregistration asks for an explicit unique inventory.
    values = (-1.0, -math.sqrt(float(x)), 0.0)
    return tuple(dict.fromkeys(float(value) for value in values))


def reference_terminal(x: float) -> tuple[int, int]:
    half = cutoff_schedule(x)["half"]
    m_ref = max(512, 4 * half)
    return int(m_ref), int(2 * m_ref)


def jacobi_diagonal(x: float, start: int, terminal: int) -> np.ndarray:
    if terminal < start:
        raise ValueError(f"terminal {terminal} precedes start {start}")
    return np.asarray([d_value(n, x) for n in range(start, terminal + 1)], dtype=float)


def jacobi_off_diagonal(x: float, size: int) -> np.ndarray:
    if size < 1:
        raise ValueError("Jacobi size must be positive")
    return np.full(max(0, size - 1), -float(x), dtype=float)


def dense_tridiagonal(diagonal: Any, off_diagonal: Any) -> np.ndarray:
    diagonal = np.asarray(diagonal, dtype=float)
    off_diagonal = np.asarray(off_diagonal, dtype=float)
    matrix = np.diag(diagonal)
    if len(diagonal) > 1:
        matrix += np.diag(off_diagonal, 1) + np.diag(off_diagonal, -1)
    return matrix


def tridiagonal_action(diagonal: Any, off_diagonal: Any,
                       vector: Any) -> np.ndarray:
    diagonal = np.asarray(diagonal, dtype=float)
    off_diagonal = np.asarray(off_diagonal, dtype=float)
    vector = np.asarray(vector, dtype=float)
    result = diagonal * vector
    if len(vector) > 1:
        result[:-1] += off_diagonal * vector[1:]
        result[1:] += off_diagonal * vector[:-1]
    return result


# ---------------------------------------------------------------------------
# Direct finite-tail solves and Sturm/bisection
# ---------------------------------------------------------------------------


def tridiagonal_solve(diagonal: Any, off_diagonal: Any, rhs: Any) -> np.ndarray:
    """Thomas solve for a real symmetric tridiagonal system.

    The routine accepts one or many right-hand sides and never calls a dense
    eigensolver.  The finite-tail controls use it as their direct linear solve.
    """
    diagonal = np.asarray(diagonal, dtype=float)
    off_diagonal = np.asarray(off_diagonal, dtype=float)
    right = np.asarray(rhs, dtype=float)
    was_vector = right.ndim == 1
    if was_vector:
        right = right[:, None]
    if diagonal.ndim != 1 or right.shape[0] != len(diagonal):
        raise ValueError("incompatible tridiagonal solve dimensions")
    if len(off_diagonal) != max(0, len(diagonal) - 1):
        raise ValueError("incompatible tridiagonal off-diagonal length")
    n, columns = len(diagonal), right.shape[1]
    if n == 0:
        raise ValueError("empty tridiagonal system")
    upper = np.zeros(max(0, n - 1), dtype=float)
    modified = np.empty((n, columns), dtype=float)
    pivot = float(diagonal[0])
    if pivot == 0.0:
        raise np.linalg.LinAlgError("zero Thomas pivot")
    if n > 1:
        upper[0] = off_diagonal[0] / pivot
    modified[0] = right[0] / pivot
    for index in range(1, n):
        pivot = diagonal[index] - off_diagonal[index - 1] * upper[index - 1]
        if pivot == 0.0:
            raise np.linalg.LinAlgError("zero Thomas pivot")
        if index < n - 1:
            upper[index] = off_diagonal[index] / pivot
        modified[index] = (right[index] - off_diagonal[index - 1] * modified[index - 1]) / pivot
    solution = np.empty_like(modified)
    solution[-1] = modified[-1]
    for index in range(n - 2, -1, -1):
        solution[index] = modified[index] - upper[index] * solution[index + 1]
    return solution[:, 0] if was_vector else solution


def finite_tail_m(x: float, energy: float, start: int, terminal: int) -> float:
    """Direct boundary Green function for indices start..terminal."""
    diagonal = jacobi_diagonal(x, start, terminal) - float(energy)
    off = jacobi_off_diagonal(x, len(diagonal))
    rhs = np.zeros(len(diagonal), dtype=float)
    rhs[0] = 1.0
    return float(tridiagonal_solve(diagonal, off, rhs)[0])


def finite_cf_m_and_derivative(x: float, energy: float, start: int,
                               terminal: int) -> tuple[float, float]:
    """Backward Weyl recurrence and its exact differentiated recurrence."""
    if terminal < start:
        raise ValueError("continued-fraction terminal precedes start")
    m_next = 0.0  # m_{terminal+1}^{(terminal)}
    derivative_next = 0.0
    for index in range(terminal, start - 1, -1):
        denominator = d_value(index, x) - float(energy) - float(x) ** 2 * m_next
        if denominator == 0.0:
            raise np.linalg.LinAlgError("continued-fraction pole")
        m_now = 1.0 / denominator
        derivative_now = m_now * m_now * (1.0 + float(x) ** 2 * derivative_next)
        m_next, derivative_next = m_now, derivative_now
    return float(m_next), float(derivative_next)


def finite_cf_m(x: float, energy: float, start: int, terminal: int) -> float:
    return finite_cf_m_and_derivative(x, energy, start, terminal)[0]


def sturm_count(diagonal: Any, off_diagonal: Any, value: float) -> int:
    """Count eigenvalues below value through the LDL* Sturm sequence."""
    diagonal = np.asarray(diagonal, dtype=float)
    off_diagonal = np.asarray(off_diagonal, dtype=float)
    if len(diagonal) == 0:
        return 0
    pivot = float(diagonal[0] - value)
    # At an exact pole the standard left-continuous Sturm convention assigns a
    # negative infinitesimal.  Bisection midpoints almost never hit this branch,
    # but the explicit convention keeps counts deterministic.
    if pivot == 0.0:
        pivot = -np.finfo(float).tiny
    count = int(pivot < 0.0)
    for index in range(1, len(diagonal)):
        pivot = float(diagonal[index] - value - off_diagonal[index - 1] ** 2 / pivot)
        if pivot == 0.0:
            pivot = -np.finfo(float).tiny
        count += int(pivot < 0.0)
    return count


def sturm_low_eigenvalues(diagonal: Any, off_diagonal: Any,
                          levels: int = REFERENCE_LEVELS) -> np.ndarray:
    """Low eigenvalues by symmetric-tridiagonal Sturm sequences and bisection."""
    diagonal = np.asarray(diagonal, dtype=float)
    off_diagonal = np.asarray(off_diagonal, dtype=float)
    if len(diagonal) == 0 or levels < 1 or levels > len(diagonal):
        raise ValueError("invalid Sturm eigenvalue request")
    lower = float(np.min(diagonal) - np.sum(np.abs(off_diagonal)) - 1.0)
    upper = float(np.max(diagonal) + np.sum(np.abs(off_diagonal)) + 1.0)
    values: list[float] = []
    for level in range(levels):
        left, right = lower, upper
        for _ in range(150):
            middle = (left + right) / 2.0
            if middle == left or middle == right:
                break
            if sturm_count(diagonal, off_diagonal, middle) <= level:
                left = middle
            else:
                right = middle
        values.append(float((left + right) / 2.0))
    return np.asarray(values, dtype=float)


def sturm_eigenvector(diagonal: Any, coupling: float,
                      eigenvalue: float) -> np.ndarray:
    """Stable finite-section eigenvector from a backward ratio recurrence.

    The tail is generated from v_{M+1}=0, then all magnitudes are accumulated
    in logarithmic form.  This avoids the exponentially growing forward
    solution in the electric barrier while retaining the finite terminal
    boundary exactly.
    """
    diagonal = np.asarray(diagonal, dtype=float)
    size = len(diagonal)
    if size == 0:
        raise ValueError("empty eigenvector request")
    if size == 1:
        return np.ones(1, dtype=float)
    x = float(coupling)
    if x <= 0.0:
        raise ValueError("coupling must be positive")
    log_magnitudes = np.zeros(size, dtype=float)
    signs = np.ones(size, dtype=float)
    next_ratio = 0.0  # v_{M+1}/v_M
    for index in range(size - 1, 0, -1):
        ratio = (diagonal[index] - float(eigenvalue)) / x - next_ratio
        if ratio == 0.0:
            ratio = np.finfo(float).tiny
        log_magnitudes[index - 1] = log_magnitudes[index] + math.log(abs(ratio))
        signs[index - 1] = signs[index] * (1.0 if ratio > 0.0 else -1.0)
        next_ratio = 1.0 / ratio
    offset = float(np.max(log_magnitudes))
    vector = signs * np.exp(log_magnitudes - offset)
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm == 0.0:
        raise FloatingPointError("non-finite backward eigenvector")
    return vector / norm


# ---------------------------------------------------------------------------
# Exact SymPy controls
# ---------------------------------------------------------------------------


def symbolic_controls(result: dict[str, Any]) -> None:
    n = sp.symbols("n", integer=True, nonnegative=True)
    add_symbolic_row(
        result,
        "four_link_casimir",
        "4*(n/2)*(n/2+1)=n*(n+2)",
        4 * (n / 2) * (n / 2 + 1),
        n * (n + 2),
    )

    c = sp.symbols("c", real=True)
    characters = [sp.chebyshevu(index, c) for index in range(6)]
    recurrence_residuals = [2 * c * characters[0] - characters[1]]
    recurrence_residuals.extend(
        2 * c * characters[index] - characters[index - 1] - characters[index + 1]
        for index in range(1, 5)
    )
    add_symbolic_row(
        result,
        "character_recurrence",
        "T|0>=|1>, T|n>=|n-1>+|n+1>",
        sp.Matrix(recurrence_residuals),
        sp.zeros(len(recurrence_residuals), 1),
    )

    x, z = sp.symbols("x z", real=True)
    d0, d1, d2, d3 = sp.symbols("d0 d1 d2 d3", real=True)
    a3 = sp.Matrix([[d0 - z, -x, 0], [-x, d1 - z, -x], [0, -x, d2 - z]])
    tail = sp.Matrix([[d3 - z]])
    coupling = sp.Matrix([[0], [0], [-x]])
    feshbach = a3 - coupling * tail.inv() * coupling.T
    expected_feshbach = sp.Matrix([
        [d0 - z, -x, 0],
        [-x, d1 - z, -x],
        [0, -x, d2 - z - x ** 2 / (d3 - z)],
    ])
    add_symbolic_row(
        result,
        "finite_schur_complement",
        "F=P(h-z)P-V(D-z)^(-1)V*",
        feshbach,
        expected_feshbach,
    )

    recurrence_symbols = sp.symbols("d0:5", real=True)
    deltas: dict[int, sp.Expr] = {5: sp.Integer(1), 6: sp.Integer(0)}
    for index in range(4, -1, -1):
        deltas[index] = sp.expand(
            (recurrence_symbols[index] - z) * deltas[index + 1]
            - x ** 2 * deltas[index + 2]
        )
    tail_matrix = sp.Matrix(5, 5, lambda row, column:
                            (recurrence_symbols[row] - z) if row == column else
                            (-x if abs(row - column) == 1 else 0))
    determinant_residuals = [deltas[index] - tail_matrix[index:, index:].det()
                             for index in range(5)]
    add_symbolic_row(
        result,
        "determinant_recurrence",
        "Delta_n=(d_n-z)Delta_(n+1)-x^2 Delta_(n+2)",
        sp.Matrix(determinant_residuals),
        sp.zeros(5, 1),
    )

    # A generic five-site ratio verifies RF9 without relying on any numerical
    # cancellation; rational M=6,8 rows below provide the frozen data table.
    generic_n = 1
    generic_m = 4
    generic_diagonal = sp.symbols("e0:5", real=True)
    full = sp.Matrix(generic_m + 1, generic_m + 1, lambda row, column:
                     (generic_diagonal[row] - z) if row == column else
                     (-x if abs(row - column) == 1 else 0))
    tail_generic = full[generic_n + 1:, generic_n + 1:]
    retained_generic = full[:generic_n + 1, :generic_n + 1]
    v_generic = sp.zeros(generic_n + 1, generic_m - generic_n)
    v_generic[generic_n, 0] = -x
    schur_generic = retained_generic - v_generic * tail_generic.inv() * v_generic.T
    ratio_residual = sp.factor(full.det() - tail_generic.det() * schur_generic.det())
    add_symbolic_row(
        result,
        "determinant_ratio",
        "det(h^(M)-z)/det(D_N^(M)-z)=det(F_N^(M)(z))",
        ratio_residual,
        sp.Integer(0),
    )

    form_x = sp.symbols("x_form", real=True)
    form_values = sp.symbols("f0:4", real=True)
    form_matrix = sp.Matrix(4, 4, lambda row, column:
                            (row * (row + 2) + 2 * form_x) if row == column else
                            (-form_x if abs(row - column) == 1 else 0))
    quadratic = (sp.Matrix(1, 4, form_values) * form_matrix
                 * sp.Matrix(4, 1, form_values))[0]
    rhs_form = sum(index * (index + 2) * form_values[index] ** 2
                   for index in range(4)) + form_x * (
                       form_values[0] ** 2 + form_values[3] ** 2
                       + sum((form_values[index + 1] - form_values[index]) ** 2
                             for index in range(3)))
    add_symbolic_row(
        result,
        "finite_section_form",
        "<f,A_N f>=sum k_n|f_n|^2+x(|f_0|^2+|f_N|^2+sum|f_(n+1)-f_n|^2)",
        sp.expand(quadratic),
        sp.expand(rhs_form),
    )

    laplace_n = 2
    laplace_theta = sp.pi / (laplace_n + 2)
    laplace_lambda = 4 * sp.sin(laplace_theta / 2) ** 2
    laplace_matrix = sp.diag(2, 2, 2)
    laplace_matrix[0, 1] = laplace_matrix[1, 0] = -1
    laplace_matrix[1, 2] = laplace_matrix[2, 1] = -1
    laplace_vector = sp.Matrix([sp.sin((index + 1) * laplace_theta)
                                for index in range(laplace_n + 1)])
    add_symbolic_row(
        result,
        "discrete_laplacian_eigenvalue",
        "lambda_min(2I-T)=4*sin^2(pi/(2*(N+2)))",
        laplace_matrix * laplace_vector - laplace_lambda * laplace_vector,
        sp.zeros(laplace_n + 1, 1),
    )

    g, a = sp.symbols("g a", positive=True)
    physical_gap = (g ** 2 / (2 * a)) * (4 * sp.sqrt(2) / g ** 2 - sp.Rational(5, 4))
    physical_expected = 2 * sp.sqrt(2) / a - 5 * g ** 2 / (8 * a)
    add_symbolic_row(
        result,
        "physical_conversion",
        "(g^2/(2a))[4*sqrt(x)-5/4], x=2/g^4",
        physical_gap,
        physical_expected,
    )
    names = [row["name"] for row in result["symbolic_rows"]]
    record_check(
        result,
        "symbolic_row_inventory",
        len(names) == 8 and len(set(names)) == 8,
        {"actual": len(names), "expected": 8, "unique": len(set(names))},
    )


def determinant_controls(result: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    for x_value in SYMBOLIC_X_VALUES:
        for n_cut in SYMBOLIC_N_VALUES:
            for terminal in SYMBOLIC_M_VALUES:
                for z_value in SYMBOLIC_Z_VALUES:
                    size = terminal + 1
                    diagonal = [sp.Integer(index * (index + 2)) + 2 * x_value
                                for index in range(size)]
                    matrix = sp.zeros(size, size)
                    for index in range(size):
                        matrix[index, index] = diagonal[index] - z_value
                        if index:
                            matrix[index, index - 1] = matrix[index - 1, index] = -x_value
                    tail = matrix[n_cut + 1:, n_cut + 1:]
                    retained = matrix[:n_cut + 1, :n_cut + 1]
                    coupling = sp.zeros(n_cut + 1, terminal - n_cut)
                    coupling[n_cut, 0] = -x_value
                    schur = retained - coupling * tail.inv() * coupling.T
                    det_full = sp.factor(matrix.det())
                    det_tail = sp.factor(tail.det())
                    det_schur = sp.factor(schur.det())
                    residual = sp.factor(det_full - det_tail * det_schur)
                    passed = bool(residual == 0)
                    row = {
                        "x": float(x_value),
                        "N": int(n_cut),
                        "M": int(terminal),
                        "z": int(z_value),
                        "det_full": str(det_full),
                        "det_tail": str(det_tail),
                        "det_ratio": str(sp.factor(det_full / det_tail)),
                        "schur_determinant": str(det_schur),
                        "residual": str(residual),
                        "passed": passed,
                    }
                    rows.append(row)
                    record_check(
                        result,
                        f"determinant_row:x={float(x_value)}:N={n_cut}:M={terminal}:z={z_value}",
                        passed,
                        {"residual": str(residual)},
                    )
    result["determinant_rows"] = rows
    keys = [(row["x"], row["N"], row["M"], row["z"]) for row in rows]
    expected = [(float(x_value), n_cut, terminal, z_value)
                for x_value in SYMBOLIC_X_VALUES
                for n_cut in SYMBOLIC_N_VALUES
                for terminal in SYMBOLIC_M_VALUES
                for z_value in SYMBOLIC_Z_VALUES]
    record_check(
        result,
        "determinant_row_inventory",
        len(rows) == 24 and len(set(keys)) == 24 and sorted(keys) == sorted(expected),
        {"actual": len(rows), "expected": 24, "unique": len(set(keys))},
    )


# ---------------------------------------------------------------------------
# Continued fractions, bounds, and resolvent controls
def continued_fraction_controls(result: dict[str, Any]) -> None:
    cf_rows: list[dict[str, Any]] = []
    direct_rows: list[dict[str, Any]] = []
    bound_rows: list[dict[str, Any]] = []
    bracket_rows: list[dict[str, Any]] = []
    derivative_rows: list[dict[str, Any]] = []
    for x in X_VALUES:
        m_ref, m_double = reference_terminal(x)
        for n_cut in n_control_values(x):
            start = n_cut + 1
            for energy in energy_control_values(x):
                m_small = finite_cf_m(x, energy, start, m_ref)
                m_large, m_prime = finite_cf_m_and_derivative(
                    x, energy, start, m_double)
                reference_error = normalized_error(m_small, m_large)
                direct_errors: dict[str, float] = {}
                direct_values: dict[str, dict[str, float]] = {}
                for length in DIRECT_TAIL_LENGTHS:
                    terminal = n_cut + int(length)
                    m_cf = finite_cf_m(x, energy, start, terminal)
                    m_direct = finite_tail_m(x, energy, start, terminal)
                    discrepancy = normalized_error(m_cf, m_direct)
                    direct_errors[str(length)] = float(discrepancy)
                    direct_values[str(length)] = {
                        "terminal": int(terminal),
                        "m_continued_fraction": float(m_cf),
                        "m_direct_tail_solve": float(m_direct),
                    }
                    direct_rows.append({
                        "x": float(x), "N": int(n_cut), "E": float(energy),
                        "M": int(length), "terminal": int(terminal),
                        "m_continued_fraction": float(m_cf),
                        "m_direct_tail_solve": float(m_direct),
                        "normalized_discrepancy": float(discrepancy),
                        "pass": discrepancy < CF_RTOL,
                    })

                r = start
                delta = k_value(r) - energy
                if delta <= 0.0:
                    raise ValueError("RF12 requires E<k_(N+1)")
                sigma = float(x) ** 2 * m_large
                lower_sigma = float(x) ** 2 / (delta + 2.0 * float(x))
                upper_sigma = ((delta + 2.0 * float(x)
                                - math.sqrt(delta * (delta + 4.0 * float(x)))) / 2.0)
                alternative_upper = min(float(x), float(x) ** 2 / delta)
                lower_slack = sigma - lower_sigma
                upper_slack = upper_sigma - sigma
                radical_slack = alternative_upper - upper_sigma
                bound_pass = (lower_slack >= -RF20_SLACK
                              and upper_slack >= -RF20_SLACK
                              and radical_slack >= -RF20_SLACK)
                cf_pass = (m_large > 0.0 and m_prime > 0.0
                           and reference_error < CF_RTOL
                           and all(error < CF_RTOL for error in direct_errors.values()))
                # The primary row is the canonical selected CF/bound row.  Its
                # field names are part of the independent-reconstruction API.
                cf_rows.append({
                    "x": float(x), "N": int(n_cut), "E": float(energy),
                    "m": float(m_large), "m_prime": float(m_prime),
                    "m_positive": bool(m_large > 0.0),
                    "m_prime_positive": bool(m_prime > 0.0),
                    "sigma": float(sigma), "lower_bound": float(lower_sigma),
                    "upper_bound": float(upper_sigma),
                    "reference_relative_error": float(reference_error),
                    "direct_relative_errors": direct_errors,
                    "direct_values": direct_values,
                    "pass": cf_pass,
                })
                bound_rows.append({
                    "x": float(x), "N": int(n_cut), "E": float(energy),
                    "delta": float(delta), "self_energy": float(sigma),
                    "lower": float(lower_sigma), "upper": float(upper_sigma),
                    "min_upper": float(alternative_upper),
                    "jensen_slack": float(lower_slack),
                    "free_tail_slack": float(upper_slack),
                    "min_upper_slack": float(radical_slack),
                    "lower_slack": float(lower_slack),
                    "upper_slack": float(upper_slack),
                    "radical_slack": float(radical_slack), "pass": bound_pass,
                })

                # RF12a is an operator inequality between rank-one endpoint
                # updates.  The two differences have no negative spectrum when
                # their scalar coefficients are nonnegative; for N>0 their
                # minimum eigenvalue is exactly zero.
                left_min = 0.0 if n_cut > 0 else float(upper_sigma - sigma)
                right_min = 0.0 if n_cut > 0 else float(sigma - lower_sigma)
                bracket_pass = (left_min >= -RF20_SLACK
                                and right_min >= -RF20_SLACK)
                bracket_rows.append({
                    "x": float(x), "N": int(n_cut), "E": float(energy),
                    "left_min_eigenvalue": left_min,
                    "right_min_eigenvalue": right_min,
                    "left_projector_slack": float(upper_sigma - sigma),
                    "right_projector_slack": float(sigma - lower_sigma),
                    "pass": bracket_pass,
                })

                tail_diagonal = jacobi_diagonal(x, start, m_double) - energy
                tail_off = jacobi_off_diagonal(x, m_double - start + 1)
                tail_rhs = np.zeros(len(tail_diagonal), dtype=float)
                tail_rhs[0] = 1.0
                tail_vector = tridiagonal_solve(tail_diagonal, tail_off, tail_rhs)
                derivative_direct = float(np.dot(tail_vector, tail_vector))
                h = 1e-5 * max(1.0, math.sqrt(float(x)), abs(float(energy)))
                derivative_fd = (finite_cf_m(x, energy + h, start, m_double)
                                 - finite_cf_m(x, energy - h, start, m_double)) / (2.0 * h)
                recurrence_error = normalized_error(m_prime, derivative_direct)
                finite_difference_error = normalized_error(m_prime, derivative_fd)
                derivative_pass = (
                    m_large > 0.0 and m_prime > 0.0
                    and recurrence_error < DERIVATIVE_RTOL
                    and finite_difference_error < DERIVATIVE_RTOL
                )
                derivative_rows.append({
                    "x": float(x), "N": int(n_cut), "E": float(energy),
                    "m": float(m_large), "m_prime_recurrence": float(m_prime),
                    "m_prime_direct_tail": float(derivative_direct),
                    "m_prime_centered_difference": float(derivative_fd),
                    "recurrence_normalized_error": float(recurrence_error),
                    "centered_difference_normalized_error": float(finite_difference_error),
                    "step": float(h), "pass": derivative_pass,
                })

    result["continued_fraction_rows"] = cf_rows
    result["direct_tail_rows"] = direct_rows
    result["bound_rows"] = bound_rows
    result["operator_bracket_rows"] = bracket_rows
    result["derivative_rows"] = derivative_rows

    expected_cf = sum(len(n_control_values(x)) * len(energy_control_values(x)) for x in X_VALUES)
    expected_direct = expected_cf * len(DIRECT_TAIL_LENGTHS)
    row_specs = (
        ("continued_fraction_row_inventory", cf_rows, expected_cf,
         lambda row: (row["x"], row["N"], row["E"])),
        ("direct_tail_row_inventory", direct_rows, expected_direct,
         lambda row: (row["x"], row["N"], row["E"], row["M"])),
        ("RF12_bound_row_inventory", bound_rows, expected_cf,
         lambda row: (row["x"], row["N"], row["E"])),
        ("RF12a_operator_bracket_row_inventory", bracket_rows, expected_cf,
         lambda row: (row["x"], row["N"], row["E"])),
        ("RF10_derivative_row_inventory", derivative_rows, expected_cf,
         lambda row: (row["x"], row["N"], row["E"])),
    )
    for name, rows, expected, key_function in row_specs:
        keys = [key_function(row) for row in rows]
        record_check(result, name, len(rows) == expected and len(set(keys)) == expected,
                     {"actual": len(rows), "expected": expected, "unique": len(set(keys))})
    record_check(
        result,
        "continued_fraction_bounds_and_derivatives",
        all(row["pass"] for row in cf_rows + direct_rows + bound_rows
            + bracket_rows + derivative_rows),
        {
            "continued_fraction_failures": sum(not row["pass"] for row in cf_rows),
            "direct_tail_failures": sum(not row["pass"] for row in direct_rows),
            "bound_failures": sum(not row["pass"] for row in bound_rows),
            "bracket_failures": sum(not row["pass"] for row in bracket_rows),
            "derivative_failures": sum(not row["pass"] for row in derivative_rows),
        },
    )


def resolvent_controls(result: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    x_values = (0.25, 1.0, 16.0)
    n_values = (0, 2, 5)
    for x in x_values:
        for n_cut in n_values:
            terminal = max(128, n_cut + 64)
            full_diagonal = jacobi_diagonal(x, 0, terminal)
            full_off = jacobi_off_diagonal(x, terminal + 1)
            A_diagonal = jacobi_diagonal(x, 0, n_cut)
            A_off = jacobi_off_diagonal(x, n_cut + 1)
            for eta in (1.0, math.sqrt(x)):
                full_rhs = np.zeros((terminal + 1, n_cut + 1), dtype=float)
                full_rhs[:n_cut + 1, :] = np.eye(n_cut + 1)
                full_solution = tridiagonal_solve(
                    full_diagonal + eta, full_off, full_rhs)
                compressed = full_solution[:n_cut + 1, :]
                bare_inverse = tridiagonal_solve(
                    A_diagonal + eta, A_off, np.eye(n_cut + 1))
                P_difference = compressed - bare_inverse
                Q_block = full_solution[n_cut + 1:, :]
                P_norm = float(np.linalg.svd(P_difference, compute_uv=False)[0])
                Q_norm = float(np.linalg.svd(Q_block, compute_uv=False)[0])
                r = n_cut + 1
                P_bound = float(x) ** 2 / (float(eta) ** 2 * (k_value(r) + eta))
                Q_bound = float(x) / (float(eta) * (k_value(r) + eta))
                P_pass = P_norm <= P_bound + RESOLVENT_SLACK * max(1.0, P_bound)
                Q_pass = Q_norm <= Q_bound + RESOLVENT_SLACK * max(1.0, Q_bound)
                rows.append({
                    "x": float(x), "N": int(n_cut), "eta": float(eta),
                    "terminal": int(terminal),
                    "P_block_norm": P_norm, "P_bound_RF13": P_bound,
                    "Q_block_norm": Q_norm, "Q_bound_RF14": Q_bound,
                    "P_normalized_excess": normalized_error(P_norm, min(P_norm, P_bound)),
                    "Q_normalized_excess": normalized_error(Q_norm, min(Q_norm, Q_bound)),
                    "RF13_pass": P_pass, "RF14_pass": Q_pass,
                    "pass": P_pass and Q_pass,
                })
    result["resolvent_rows"] = rows
    keys = [(row["x"], row["N"], row["eta"]) for row in rows]
    expected = len(x_values) * len(n_values) * 2
    record_check(result, "resolvent_row_inventory",
                 len(rows) == expected and len(set(keys)) == expected,
                 {"actual": len(rows), "expected": expected, "unique": len(set(keys))})
    record_check(result, "RF13_RF14_finite_resolvent_bounds",
                 all(row["pass"] for row in rows),
                 {"failures": [
                     {"x": row["x"], "N": row["N"], "eta": row["eta"]}
                     for row in rows if not row["pass"]
                 ]})


# ---------------------------------------------------------------------------
# Reference spectrum, cutoff metrics, weak-coupling controls, Feshbach rows
# ---------------------------------------------------------------------------


def spectrum_and_cutoff_controls(result: dict[str, Any]) -> tuple[
        dict[float, dict[str, Any]], dict[float, np.ndarray]]:
    reference_data: dict[float, dict[str, Any]] = {}
    reference_vectors: dict[float, np.ndarray] = {}
    spectrum_rows: list[dict[str, Any]] = []
    cutoff_rows: list[dict[str, Any]] = []

    for x in X_VALUES:
        m_ref, m_double = reference_terminal(x)
        levels: dict[int, np.ndarray] = {}
        for terminal, label in ((m_ref, "M_ref"), (m_double, "2M_ref")):
            diagonal = jacobi_diagonal(x, 0, terminal)
            off = jacobi_off_diagonal(x, terminal + 1)
            eigenvalues = sturm_low_eigenvalues(diagonal, off, REFERENCE_LEVELS)
            levels[terminal] = eigenvalues
            spectrum_rows.append({
                "x": float(x), "terminal": int(terminal), "reference": label,
                "eigenvalues": [float(value) for value in eigenvalues],
                "method": "symmetric-tridiagonal Sturm sequence and bisection",
                "pass": bool(np.isfinite(eigenvalues).all()
                             and np.all(np.diff(eigenvalues) > 0.0)),
            })
        reference_data[float(x)] = {
            "M_ref": int(m_ref), "2M_ref": int(m_double),
            "M_ref_eigenvalues": levels[m_ref],
            "2M_ref_eigenvalues": levels[m_double],
        }
        reference_diagonal = jacobi_diagonal(x, 0, m_double)
        reference_vectors[float(x)] = np.asarray([
            sturm_eigenvector(reference_diagonal, x, value)
            for value in levels[m_double]
        ], dtype=float)
        convergence_errors = [normalized_error(levels[m_ref][index], levels[m_double][index])
                              for index in range(REFERENCE_LEVELS)]
        record_check(
            result,
            f"reference_doubling:x={float(x)}",
            all(error < REFERENCE_RTOL for error in convergence_errors),
            {"M_ref": int(m_ref), "2M_ref": int(m_double),
             "normalized_errors": convergence_errors},
        )

    result["spectrum_rows"] = spectrum_rows
    spectrum_keys = [(row["x"], row["terminal"]) for row in spectrum_rows]
    record_check(result, "spectrum_row_inventory",
                 len(spectrum_rows) == 12 and len(set(spectrum_keys)) == 12,
                 {"actual": len(spectrum_rows), "expected": 12,
                  "unique": len(set(spectrum_keys))})
    record_check(result, "reference_spectrum_rows_finite_and_ordered",
                 all(row["pass"] for row in spectrum_rows),
                 {"failed": [row for row in spectrum_rows if not row["pass"]]})

    for x in X_VALUES:
        ref = reference_data[float(x)]["2M_ref_eigenvalues"]
        vectors = reference_vectors[float(x)]
        for schedule in SCHEDULE_NAMES:
            n_cut = cutoff_schedule(x)[schedule]
            diagonal = jacobi_diagonal(x, 0, n_cut)
            off = jacobi_off_diagonal(x, n_cut + 1)
            eigenvalues = sturm_low_eigenvalues(diagonal, off, REFERENCE_LEVELS)
            relative_errors = [normalized_error(eigenvalues[index], ref[index])
                               for index in range(REFERENCE_LEVELS)]
            lower_bound = 4.0 * x * math.sin(math.pi / (2.0 * (n_cut + 2))) ** 2
            retained: list[float] = []
            discarded: list[float] = []
            boundary: list[float] = []
            mass_errors: list[float] = []
            terminal = reference_data[float(x)]["2M_ref"]
            for vector in vectors:
                kept = float(np.sum(vector[:n_cut + 1] ** 2))
                dropped = float(np.sum(vector[n_cut + 1:] ** 2))
                retained.append(kept)
                discarded.append(dropped)
            cutoff_rows.append({
                "x": float(x), "schedule": schedule, "cutoff": int(n_cut),
                "eigenvalues": [float(value) for value in eigenvalues],
                "relative_errors": [float(value) for value in relative_errors],
                "ratio_N_x_quarter": float(n_cut / (x ** 0.25)),
                "lower_bound": float(lower_bound),
                "boundary_residuals": boundary,
                "retained_probabilities": retained,
                "discarded_probabilities": discarded,
                "mass_identity_errors": mass_errors,
                "reference_terminal": int(terminal),
                # A schedule row is a measurement, not a claim that its finite
                # error vanishes in a limit.  Only finiteness and RF20 are
                # numerical gates here.
                "pass": bool(np.isfinite(eigenvalues).all() and bound_pass
                             and all(error <= 1e-10 for error in mass_errors)),
            })

    result["cutoff_rows"] = cutoff_rows
    cutoff_keys = [(row["x"], row["schedule"]) for row in cutoff_rows]
    record_check(result, "cutoff_row_inventory",
                 len(cutoff_rows) == 30 and len(set(cutoff_keys)) == 30,
                 {"actual": len(cutoff_rows), "expected": 30,
                  "unique": len(set(cutoff_keys))})
    record_check(result, "finite_section_RF20_and_mass_metrics",
                 all(row["pass"] for row in cutoff_rows),
                 {"failed": [
                     {"x": row["x"], "schedule": row["schedule"],
                      "lower_bound": row["lower_bound"],
                      "eigenvalue": row["eigenvalues"][0]}
                     for row in cutoff_rows if not row["pass"]
                 ]})
    return reference_data, reference_vectors


def weak_coupling_controls(result: dict[str, Any],
                           reference_data: dict[float, dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    leading_failures: list[dict[str, Any]] = []
    subleading_failures: list[dict[str, Any]] = []
    for x in (4096.0, 65536.0):
        levels = reference_data[x]["2M_ref_eigenvalues"]
        for index, value in enumerate(levels):
            leading_error = abs(value / math.sqrt(x) - (4 * index + 3))
            row = {
                "x": float(x), "j": int(index), "eigenvalue": float(value),
                "leading_error": float(leading_error), "leading_tolerance": 0.1,
                "leading_pass": bool(leading_error < 0.1),
            }
            if x == 65536.0:
                c_j = -1.0 - (6.0 * index ** 2 + 9.0 * index + 15.0 / 4.0) / 12.0
                subleading_error = abs(value - (4 * index + 3) * math.sqrt(x) - c_j)
                row.update(c_j=float(c_j), subleading_error=float(subleading_error),
                           subleading_tolerance=0.25,
                           subleading_pass=bool(subleading_error < 0.25))
            else:
                row.update(c_j=None, subleading_error=None,
                           subleading_tolerance=None, subleading_pass=None)
            rows.append(row)
            if not row["leading_pass"]:
                leading_failures.append(row)
            if row["subleading_pass"] is False:
                subleading_failures.append(row)
    result["weak_coupling_rows"] = rows
    record_check(result, "weak_coupling_leading_scale",
                 not leading_failures, {"failures": leading_failures})
    record_check(result, "weak_coupling_subleading_scale",
                 not subleading_failures, {"failures": subleading_failures})


def feshbach_controls(result: dict[str, Any],
                      reference_data: dict[float, dict[str, Any]],
                      reference_vectors: dict[float, np.ndarray]) -> None:
    rows: list[dict[str, Any]] = []
    for x in (4096.0, 65536.0):
        data = reference_data[x]
        terminal = int(data["2M_ref"])
        n_cut = cutoff_schedule(x)["iso"]
        start = n_cut + 1
        k_tail = k_value(start)
        diagonal_tail = jacobi_diagonal(x, start, terminal)
        off_tail = jacobi_off_diagonal(x, terminal - start + 1)
        tail_min = float(sturm_low_eigenvalues(diagonal_tail, off_tail, 1)[0])
        pole_target = k_tail - math.sqrt(x)
        tail_operator_margin = tail_min - pole_target
        vectors = reference_vectors[x]
        for index, energy in enumerate(data["2M_ref_eigenvalues"]):
            isolation_margin = pole_target - float(energy)
            pole_free = bool(
                isolation_margin > 0.0
                and tail_operator_margin >= -RF20_SLACK
            )
            m_value, m_prime = finite_cf_m_and_derivative(x, energy, start, terminal)
            A_diagonal = jacobi_diagonal(x, 0, n_cut)
            A_off = jacobi_off_diagonal(x, n_cut + 1)
            endpoint = np.zeros(n_cut + 1, dtype=float)
            endpoint[-1] = 1.0
            feshbach = (
                dense_tridiagonal(A_diagonal, A_off)
                - energy * np.eye(n_cut + 1)
                - float(x) ** 2 * m_value * np.outer(endpoint, endpoint)
            )
            singular_values = np.linalg.svd(feshbach, compute_uv=False)
            feshbach_normalized_residual = float(
                singular_values[-1] / max(1.0, float(singular_values[0]))
            )

            p = np.asarray(vectors[index][:n_cut + 1], dtype=float)
            retained_norm_sq = float(np.dot(p, p))
            if retained_norm_sq == 0.0:
                raise FloatingPointError("zero retained reference component")
            p /= math.sqrt(retained_norm_sq)
            tail_rhs = np.zeros(len(diagonal_tail), dtype=float)
            tail_rhs[0] = float(x) * p[-1]
            reconstructed_tail = tridiagonal_solve(
                diagonal_tail - energy, off_tail, tail_rhs
            )
            tail_norm_sq_direct = float(np.dot(reconstructed_tail, reconstructed_tail))
            tail_norm_sq_formula = float(float(x) ** 2 * p[-1] ** 2 * m_prime)
            reference_tail_norm_sq = float(np.dot(
                vectors[index][start:], vectors[index][start:]
            ) / retained_norm_sq)
            tail_norm_sq_relative_error = (
                abs(tail_norm_sq_direct - tail_norm_sq_formula)
                / max(abs(tail_norm_sq_formula), np.finfo(float).tiny)
            )
            reference_tail_relative_error = (
                abs(tail_norm_sq_direct - reference_tail_norm_sq)
                / max(abs(reference_tail_norm_sq), np.finfo(float).tiny)
            )
            psi = np.concatenate((p, reconstructed_tail))
            full_diagonal = jacobi_diagonal(x, 0, terminal)
            full_off = jacobi_off_diagonal(x, terminal + 1)
            residual = tridiagonal_action(full_diagonal, full_off, psi) - energy * psi
            residual_norm = float(np.linalg.norm(residual))
            residual_scale = max(
                1.0,
                float(np.linalg.norm(
                    tridiagonal_action(full_diagonal, full_off, psi)
                )),
                abs(float(energy)) * float(np.linalg.norm(psi)),
            )
            full_residual = residual_norm / residual_scale
            row_pass = bool(
                pole_free
                and feshbach_normalized_residual < FESHBACH_RTOL
                and full_residual < FESHBACH_RTOL
                and tail_norm_sq_relative_error < TAIL_NORM_RTOL
            )
            rows.append({
                "x": float(x), "j": int(index), "cutoff": int(n_cut),
                "eigenvalue": float(energy), "k_tail": float(k_tail),
                "isolation_margin": float(isolation_margin),
                "feshbach_normalized_residual": feshbach_normalized_residual,
                "full_residual": float(full_residual),
                "tail_norm_sq_direct": tail_norm_sq_direct,
                "tail_norm_sq_formula": tail_norm_sq_formula,
                "tail_norm_sq_relative_error": float(tail_norm_sq_relative_error),
                "tail_operator_margin": float(tail_operator_margin),
                "reference_tail_norm_sq": reference_tail_norm_sq,
                "reference_tail_relative_error": float(reference_tail_relative_error),
                "pole_free": pole_free, "terminal": terminal,
                "m": float(m_value), "m_prime": float(m_prime),
                "pass": row_pass,
            })
    result["feshbach_rows"] = rows
    keys = [(row["x"], row["j"]) for row in rows]
    record_check(result, "feshbach_row_inventory",
                 len(rows) == 6 and len(set(keys)) == 6,
                 {"actual": len(rows), "expected": 6, "unique": len(set(keys))})
    record_check(result, "N_iso_pole_free_feshbach_reconstruction",
                 all(row["pass"] for row in rows),
                 {"failed": [
                     {"x": row["x"], "j": row["j"],
                      "isolation_margin": row["isolation_margin"],
                      "feshbach_normalized_residual": row["feshbach_normalized_residual"],
                      "full_residual": row["full_residual"],
                      "tail_norm_sq_relative_error": row["tail_norm_sq_relative_error"]}
                     for row in rows if not row["pass"]
                 ]})
# ---------------------------------------------------------------------------
# Source binding, receipt assembly, and command-line entry point
# ---------------------------------------------------------------------------


def relative_source_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def source_map() -> dict[str, Path]:
    return {"protocol": PROTOCOL, "primary": SELF_PATH, "independent": INDEPENDENT}


def prepare_sources(output: Path) -> tuple[
        Path, Path, dict[str, bytes], dict[str, dict[str, str]], dict[str, Any]]:
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    destinations = (output, manifest_path, snapshot_dir)
    if any(path.exists() for path in destinations):
        raise FileExistsError(
            "refusing existing output, manifest, or source directory: "
            + ", ".join(str(path) for path in destinations if path.exists())
        )
    paths = source_map()
    payloads: dict[str, bytes] = {}
    identities: dict[str, dict[str, str]] = {}
    for key in SOURCE_KEYS:
        path = paths[key]
        if not path.is_file():
            raise FileNotFoundError(f"required source is missing: {path}")
        payload = path.read_bytes()
        payloads[key] = payload
        digest = sha256_bytes(payload)
        if key == "protocol" and digest != EXPECTED_PROTOCOL_SHA256:
            raise ValueError(
                "frozen protocol digest mismatch before calculation: "
                f"{digest} != {EXPECTED_PROTOCOL_SHA256}"
            )
        identities[key] = {
            "path": relative_source_path(path),
            "sha256": digest,
        }
        if Path(identities[key]["path"]).name != EXPECTED_SOURCE_BASENAMES[key]:
            raise ValueError(f"unexpected source basename for {key}")

    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    snapshot_hashes: dict[str, str] = {}
    for key in SOURCE_KEYS:
        snapshot = snapshot_dir / EXPECTED_SOURCE_BASENAMES[key]
        with snapshot.open("xb") as handle:
            handle.write(payloads[key])
        snapshot_hashes[key] = sha256_raw(snapshot)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "identities": identities,
        "expected_protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "snapshot_sha256": snapshot_hashes,
        "runtime": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "sympy": sp.__version__,
        },
    }
    with manifest_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    return manifest_path, snapshot_dir, payloads, identities, manifest


def source_binding(output: Path, snapshot_dir: Path,
                   payloads: dict[str, bytes],
                   identities: dict[str, dict[str, str]]) -> tuple[dict[str, Any], list[str]]:
    binding: dict[str, Any] = {}
    failures: list[str] = []
    paths = source_map()
    for key in SOURCE_KEYS:
        path = paths[key]
        snapshot = snapshot_dir / EXPECTED_SOURCE_BASENAMES[key]
        live_hash = sha256_raw(path) if path.is_file() else None
        snapshot_hash = sha256_raw(snapshot) if snapshot.is_file() else None
        declared_hash = identities[key]["sha256"]
        stable = (live_hash == declared_hash == snapshot_hash
                  == sha256_bytes(payloads[key]))
        binding[key] = {
            "declared_path": identities[key]["path"],
            "resolved_path": str(path),
            "snapshot_path": str(snapshot),
            "declared_sha256": declared_hash,
            "live_sha256_at_start": live_hash,
            "snapshot_sha256": snapshot_hash,
            "live_sha256_at_end": None,
            "stable": stable,
        }
        if not stable:
            failures.append(f"source binding mismatch for {key}")
    return binding, failures


def recheck_sources(binding: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    paths = source_map()
    for key in SOURCE_KEYS:
        row = binding.get(key, {})
        path = paths[key]
        live_hash = sha256_raw(path) if path.is_file() else None
        row["live_sha256_at_end"] = live_hash
        if live_hash != row.get("live_sha256_at_start"):
            row["stable"] = False
            failures.append(f"source changed during verification: {key}")
    return failures


def frozen_protocol() -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "expected_protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "hamiltonian": "h_x=K+x(2I-T)",
        "electric_eigenvalue": "k_n=n(n+2)",
        "coupling": "x=2/g^4",
        "physical_gap_symbol": "Delta_square_1",
        "character_cutoff": "P_N=sum_{n=0}^N |n><n|",
        "x_values": [float(x) for x in X_VALUES],
        "j_values": list(J_VALUES),
        "schedule_names": list(SCHEDULE_NAMES),
        "schedules": {
            "fixed": "N_fixed=8",
            "C": "N_C=ceil(2*x^(1/4))",
            "iso": "N_iso=ceil(4*x^(1/4))",
            "grow": "N_grow=ceil(x^(1/4)*log(2+x))",
            "half": "N_1/2=ceil(2*sqrt(x))",
        },
        "cutoff_values": {
            str(float(x)): cutoff_schedule(x) for x in X_VALUES
        },
        "continued_fraction_N_values": {
            str(float(x)): list(n_control_values(x)) for x in X_VALUES
        },
        "continued_fraction_E_values": {
            str(float(x)): list(energy_control_values(x)) for x in X_VALUES
        },
        "direct_tail_lengths": list(DIRECT_TAIL_LENGTHS),
        "reference_terminal": "M_ref=max(512,4*N_1/2); doubled terminal 2*M_ref",
        "reference_method": "symmetric-tridiagonal Sturm sequence and bisection",
        "finite_difference_method": "direct Thomas finite-tail solve",
        "tolerances": {
            "reference_relative": REFERENCE_RTOL,
            "continued_fraction_relative": CF_RTOL,
            "derivative_centered_difference": DERIVATIVE_RTOL,
            "resolvent_slack": RESOLVENT_SLACK,
            "feshbach_residual": FESHBACH_RTOL,
            "tail_norm_relative": TAIL_NORM_RTOL,
            "RF20_slack": RF20_SLACK,
        },
        "analytical_status": {
            "RF4_RF14": "REQUIRES_ANALYTICAL_RECONCILIATION",
            "RF19_RF22": "REQUIRES_ANALYTICAL_RECONCILIATION",
            "continuous_SU2_normalization": "REQUIRES_INDEPENDENT_RECONSTRUCTION",
        },
    }


def initial_receipt(manifest: dict[str, Any], identities: dict[str, dict[str, str]],
                    manifest_path: Path) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "receipt_role": "primary",
        "protocol": frozen_protocol(),
        "runtime": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "sympy": sp.__version__,
        },
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "identities": identities,
        "inputs_manifest": {
            "path": str(manifest_path),
            "sha256": sha256_raw(manifest_path),
            "schema": manifest.get("schema"),
        },
        "checks": [],
        "failures": [],
        "symbolic_rows": [],
        "determinant_rows": [],
        "continued_fraction_rows": [],
        "resolvent_rows": [],
        "spectrum_rows": [],
        "cutoff_rows": [],
        "feshbach_rows": [],
        "weak_coupling_rows": [],
        "direct_tail_rows": [],
        "bound_rows": [],
        "operator_bracket_rows": [],
        "derivative_rows": [],
        "source_binding": {},
        "classifications": {
            "finite_symbolic_controls": "REQUIRES_INDEPENDENT_RECONSTRUCTION",
            "finite_numerical_controls": "REQUIRES_INDEPENDENT_RECONSTRUCTION",
            "exact_feshbach_transfer_and_resolvent_bounds": "REQUIRES_ANALYTICAL_RECONCILIATION",
            "finite_section_form_and_cutoff_limits": "REQUIRES_ANALYTICAL_RECONCILIATION",
            "weak_coupling_asymptotics": "REQUIRES_ANALYTICAL_RECONCILIATION",
            "fixed_or_o_x_quarter_cutoff_as_low_energy_claim": "REQUIRES_ANALYTICAL_RECONCILIATION",
            "interacting_refined_fibre": "UNRESOLVED",
            "volume_uniform_resolvent": "UNRESOLVED",
            "thermodynamic_limit": "UNRESOLVED",
            "continuum_mass_gap": "UNRESOLVED",
            "cassi_microscopic_identification": "UNRESOLVED",
        },
        "scope": {
            "physical_sector": "continuous-SU(2) class-function isolated square",
            "finite_regulation": "character cutoff and finite Jacobi terminal sections",
            "analytical_claims": "not adopted from numerical rows",
            "neighboring_plaquettes": "UNRESOLVED",
            "interacting_lattice_block": "UNRESOLVED",
            "volume_uniform_estimate": "UNRESOLVED",
            "thermodynamic_limit": "UNRESOLVED",
            "continuum_limit": "UNRESOLVED",
            "continuum_mass_gap": "UNRESOLVED",
            "cassi_microscopic_claim": "UNRESOLVED",
        },
        "measured_summary": {},
        "status": "PENDING",
    }


def compute(result: dict[str, Any]) -> bool:
    symbolic_controls(result)
    determinant_controls(result)
    continued_fraction_controls(result)
    resolvent_controls(result)
    reference_data, reference_vectors = spectrum_and_cutoff_controls(result)
    weak_coupling_controls(result, reference_data)
    feshbach_controls(result, reference_data, reference_vectors)

    schedule_errors: dict[str, float] = {}
    for schedule in SCHEDULE_NAMES:
        values = [error for row in result["cutoff_rows"] if row["schedule"] == schedule
                  for error in row["relative_errors"]]
        schedule_errors[schedule] = float(max(values)) if values else 0.0
    result["measured_summary"] = {
        "symbolic_row_count": len(result["symbolic_rows"]),
        "determinant_row_count": len(result["determinant_rows"]),
        "continued_fraction_row_count": len(result["continued_fraction_rows"]),
        "direct_tail_row_count": len(result["direct_tail_rows"]),
        "resolvent_row_count": len(result["resolvent_rows"]),
        "spectrum_row_count": len(result["spectrum_rows"]),
        "cutoff_row_count": len(result["cutoff_rows"]),
        "feshbach_row_count": len(result["feshbach_rows"]),
        "cutoff_max_relative_error_by_schedule": schedule_errors,
        "reference_max_normalized_error": max(
            (float(item["detail"]["normalized_errors"][index])
             for item in result["checks"] if item["name"].startswith("reference_doubling:")
             for index in range(REFERENCE_LEVELS)), default=0.0),
        "analytical_claims_numerically_adopted": False,
    }
    result["check_count"] = len(result["checks"])
    result["status"] = "PASS" if not result["failures"] else "FAIL"
    return result["status"] == "PASS"


def write_exclusive_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {path}")
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def run(output: Path) -> int:
    output = output.expanduser().resolve()
    manifest_path, snapshot_dir, payloads, identities, manifest = prepare_sources(output)
    result = initial_receipt(manifest, identities, manifest_path)
    binding, binding_failures = source_binding(output, snapshot_dir, payloads, identities)
    result["source_binding"] = binding
    if binding_failures:
        result["failures"].extend(binding_failures)
        record_check(result, "source_bindings_frozen", False, {"failures": binding_failures})
    else:
        record_check(result, "source_bindings_frozen", True, {"sources": list(SOURCE_KEYS)})

    success = False
    try:
        success = compute(result)
        drift_failures = recheck_sources(binding)
        if drift_failures:
            result["failures"].extend(drift_failures)
            record_check(result, "sources_stable_during_verification", False,
                         {"failures": drift_failures})
            success = False
        else:
            record_check(result, "sources_stable_during_verification", True,
                         {"sources": list(SOURCE_KEYS)})
        if not all_numbers_finite(result):
            result["failures"].append("receipt contains non-finite number")
            record_check(result, "finite_json_payload", False,
                         "non-finite number detected before serialization")
            success = False
        else:
            record_check(result, "finite_json_payload", True, "all numeric values finite")
    except Exception as exc:  # noqa: BLE001 - receipt must fail closed
        result["status"] = "ERROR"
        result["failures"].append(f"{type(exc).__name__}: {exc}")
        record_check(result, "unhandled_exception", False,
                     {"type": type(exc).__name__, "message": str(exc)})
        success = False

    result["check_count"] = len(result["checks"])
    if result.get("status") != "ERROR":
        result["status"] = "PASS" if success and not result["failures"] else "FAIL"
    write_exclusive_json(output, result)
    print(f"Receipt: {output}")
    print(json.dumps({key: result.get(key) for key in
                      ("status", "check_count", "failures", "classifications")},
                     indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if result["status"] == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="fresh path for the primary verification receipt")
    args = parser.parse_args(argv)
    try:
        return run(args.output)
    except FileExistsError as exc:
        print(f"verification aborted: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - no overwrite on setup failure
        print(f"verification setup failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
