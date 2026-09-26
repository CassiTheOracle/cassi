#!/usr/bin/env python3
"""Primary continuum admissibility and two-body localization calculation.

The source is standalone and follows the frozen protocol in
``matter-formation-continuum-admissibility-prereg.md``.  All radial observables
are evaluated with adaptive SciPy quadrature; the static Taylor remainder uses
its integral remainder kernel rather than subtracting two large asymptotic
quantities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable

from scipy.integrate import quad


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "computations" / "matter-formation-continuum-admissibility-prereg.md"
VERIFIER_PATH = ROOT / "computations" / "verify_matter_formation_continuum_admissibility.py"
FINITE_MODE_PREREG = ROOT / "computations" / "matter-formation-fermion-production-prereg.md"
SCHEMA = "cassi-continuum-admissibility-v1"

M0 = 1.0
y = 0.25
OMEGA = 3.0
NU = 0.75
CUTOFFS = (32, 64, 128, 256, 512)
MASSES = (0.5, 2.0)
DURATIONS = (0.25, 1.0, 3.0)
PI2 = math.pi * math.pi
MEASURE = 1.0 / (2.0 * PI2)
CHECK_NAMES = (
    "symbolic_identities",
    "row_contract",
    "finite_values",
    "positive_densities",
    "zero_controls",
    "excitation_count",
    "number_asymptotes",
    "energy_asymptotes",
    "vacuum_asymptotes",
    "static_remainders",
    "kinetic_primitive",
    "positive_kinetic_factors",
    "overlap_logarithm",
    "binding_integral",
    "binding_trace",
)

OCCUPATION_KEYS = (
    "kind", "mass", "duration", "cutoff", "pair_density",
    "excitation_number_density", "excitation_energy_density",
    "predicted_number_coefficient", "predicted_energy_coefficient",
    "scaled_pair_density", "scaled_excitation_energy",
)
VACUUM_KEYS = (
    "mass", "cutoff", "reference_vacuum_density",
    "predicted_quadratic_coefficient", "scaled_reference_vacuum",
    "renormalized_static_density", "analytic_static_limit",
)
KINETIC_KEYS = (
    "cutoff", "kinetic_integral", "analytic_kinetic_integral",
    "z_factor", "overlap_energy_density",
)
OVERLAP_KEYS = ("cutoff_low", "cutoff_high", "measured_log_coefficient", "predicted_log_coefficient")
BINDING_KEYS = (
    "reference_mass", "reduced_mass", "yukawa_coupling", "scalar_mass", "alpha",
    "radial_integral", "analytic_radial_integral", "bargmann_bound",
    "all_partial_waves_excluded",
)


def canonical_sha256(path: Path) -> str:
    """SHA-256 after canonical CRLF-to-LF normalization."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(__import__("os").path.relpath(path.resolve(), ROOT)).as_posix()


def identity(path: Path, label: str, failures: list[str]) -> dict[str, str]:
    result = {"path": relative_path(path), "sha256": ""}
    try:
        result["sha256"] = canonical_sha256(path)
    except Exception as exc:
        failures.append(f"missing {label} identity: {type(exc).__name__}: {exc}")
    return result


def as_json(value: Any) -> Any:
    """Convert only ordinary JSON-compatible values and reject non-finite floats."""
    if isinstance(value, dict):
        return {str(k): as_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_json(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite JSON value")
        return value
    raise TypeError(f"unsupported JSON value {type(value).__name__}")


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to replace receipt: {path}")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(as_json(payload), stream, indent=2, sort_keys=False, allow_nan=False)
        stream.write("\n")


def _integrate(func: Callable[[float], float], cutoff: float) -> float:
    value, _ = quad(func, 0.0, float(cutoff), epsabs=1.0e-10, epsrel=2.0e-11, limit=10000)
    return float(value)


def _energy(p: float, mass: float) -> float:
    return math.hypot(p, mass)


def _quench_occupation(p: float, mass: float) -> float:
    """Rationalized form of 1-(p^2+m0*m1)/(E0 E1)."""
    delta = mass - M0
    p2 = p * p
    e0 = _energy(p, M0)
    e1 = _energy(p, mass)
    a = p2 + M0 * mass
    return 0.5 * p2 * delta * delta / (e0 * e1 * (e0 * e1 + a))


def _pulse_occupation(p: float, mass: float, duration: float) -> float:
    delta = mass - M0
    e0 = _energy(p, M0)
    e1 = _energy(p, mass)
    return p * p * delta * delta * math.sin(e1 * duration) ** 2 / (e0 * e0 * e1 * e1)


def _overlap_occupation(p: float) -> float:
    e0 = _energy(p, M0)
    b = p * NU / (2.0 * e0 * e0 * e0)
    # Rationalized 1-1/sqrt(1+b^2), safe when b is tiny.
    root = math.hypot(1.0, b)
    return 0.5 * b * b / (root * (root + 1.0))


def _radial_integral(occupation: Callable[[float], float], cutoff: int, energy_mass: float | None = None) -> float:
    if energy_mass is None:
        f = lambda p: MEASURE * p * p * occupation(p)
    else:
        f = lambda p: MEASURE * p * p * _energy(p, energy_mass) * occupation(p)
    return _integrate(f, cutoff)


def occupation_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mass in MASSES:
        delta = mass - M0
        number_coefficient = delta * delta / (4.0 * PI2)
        energy_coefficient = number_coefficient
        for cutoff in CUTOFFS:
            pair_integral = _radial_integral(lambda p, m=mass: _quench_occupation(p, m), cutoff)
            energy_integral = _radial_integral(
                lambda p, m=mass: _quench_occupation(p, m), cutoff, energy_mass=mass
            )
            pair_density = 2.0 * pair_integral
            excitation_number = 4.0 * pair_integral
            excitation_energy = 4.0 * energy_integral
            rows.append({
                "kind": "quench", "mass": float(mass), "duration": 0.0, "cutoff": int(cutoff),
                "pair_density": float(pair_density),
                "excitation_number_density": float(excitation_number),
                "excitation_energy_density": float(excitation_energy),
                "predicted_number_coefficient": float(number_coefficient),
                "predicted_energy_coefficient": float(energy_coefficient),
                "scaled_pair_density": float(pair_density / cutoff),
                "scaled_excitation_energy": float(excitation_energy / (cutoff * cutoff)),
            })
    for mass in MASSES:
        delta = mass - M0
        number_coefficient = delta * delta / (2.0 * PI2)
        energy_coefficient = number_coefficient
        for duration in DURATIONS:
            for cutoff in CUTOFFS:
                pair_integral = _radial_integral(
                    lambda p, m=mass, t=duration: _pulse_occupation(p, m, t), cutoff
                )
                energy_integral = _radial_integral(
                    lambda p, m=mass, t=duration: _pulse_occupation(p, m, t), cutoff, energy_mass=M0
                )
                pair_density = 2.0 * pair_integral
                excitation_number = 4.0 * pair_integral
                excitation_energy = 4.0 * energy_integral
                rows.append({
                    "kind": "pulse", "mass": float(mass), "duration": float(duration), "cutoff": int(cutoff),
                    "pair_density": float(pair_density),
                    "excitation_number_density": float(excitation_number),
                    "excitation_energy_density": float(excitation_energy),
                    "predicted_number_coefficient": float(number_coefficient),
                    "predicted_energy_coefficient": float(energy_coefficient),
                    "scaled_pair_density": float(pair_density / cutoff),
                    "scaled_excitation_energy": float(excitation_energy / (cutoff * cutoff)),
                })
    # Registered controls are appended after all non-control rows.
    for kind, duration in (("quench", 0.0), ("pulse", 1.0)):
        cutoff = 512
        if kind == "quench":
            pair_integral = _radial_integral(lambda p: _quench_occupation(p, M0), cutoff)
            energy_integral = _radial_integral(lambda p: _quench_occupation(p, M0), cutoff, energy_mass=M0)
        else:
            pair_integral = _radial_integral(lambda p: _pulse_occupation(p, M0, duration), cutoff)
            energy_integral = _radial_integral(lambda p: _pulse_occupation(p, M0, duration), cutoff, energy_mass=M0)
        pair_density = 2.0 * pair_integral
        excitation_number = 4.0 * pair_integral
        excitation_energy = 4.0 * energy_integral
        rows.append({
            "kind": kind, "mass": float(M0), "duration": float(duration), "cutoff": cutoff,
            "pair_density": float(pair_density), "excitation_number_density": float(excitation_number),
            "excitation_energy_density": float(excitation_energy),
            "predicted_number_coefficient": 0.0, "predicted_energy_coefficient": 0.0,
            "scaled_pair_density": float(pair_density / cutoff),
            "scaled_excitation_energy": float(excitation_energy / (cutoff * cutoff)),
        })
    return rows


def _vacuum_cell(p: float, mass: float) -> float:
    delta = mass - M0
    if p == 0.0:
        return 0.0
    p2 = p * p
    e0 = _energy(p, M0)
    e1 = _energy(p, mass)
    return -2.0 * p2 * delta * delta / (e0 * (e0 * e1 + p2 + M0 * mass))


def _remainder_cell(p: float, mass: float) -> float:
    """Taylor-integral remainder, O(p^-5), with no large-term subtraction."""
    delta = mass - M0
    if p == 0.0 or delta == 0.0:
        return 0.0

    def s_kernel(s: float) -> float:
        ms = M0 + s * delta
        p2 = p * p
        m2 = ms * ms
        denominator = (p2 + m2) ** 4.5
        return (1.0 - s) ** 4 * p2 * ms * (3.0 * p2 - 4.0 * m2) / denominator

    integral_s, _ = quad(s_kernel, 0.0, 1.0, epsabs=2.0e-13, epsrel=2.0e-13, limit=200)
    return -1.25 * delta ** 5 * integral_s


def _remainder_integral(mass: float, cutoff: int) -> float:
    # Pairwise summation of adaptive block integrals avoids accumulating roundoff
    # in the finite, sign-changing p^-5 tail.
    edges = [0.0, 1.0, 4.0, 16.0, 64.0, 256.0, float(cutoff)]
    edges = sorted(set(edge for edge in edges if edge <= cutoff))
    values: list[float] = []
    for lo, hi in zip(edges, edges[1:]):
        if hi <= lo:
            continue
        value, _ = quad(
            lambda p: MEASURE * p * p * _remainder_cell(p, mass),
            lo, hi, epsabs=2.0e-11, epsrel=2.0e-11, limit=1000,
        )
        values.append(float(value))
    return float(math.fsum(values))


def _analytic_static_limit(mass: float) -> float:
    delta = mass - M0
    numerator = (
        mass ** 4 * math.log(mass * mass / (M0 * M0))
        - 2.0 * M0 ** 3 * delta
        - 7.0 * M0 * M0 * delta * delta
        - (26.0 / 3.0) * M0 * delta ** 3
        - (25.0 / 6.0) * delta ** 4
    )
    return -numerator / (16.0 * PI2)


def vacuum_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mass in MASSES:
        delta = mass - M0
        predicted = -delta * delta / (4.0 * PI2)
        analytic = _analytic_static_limit(mass)
        for cutoff in CUTOFFS:
            density = _integrate(lambda p, m=mass: MEASURE * p * p * _vacuum_cell(p, m), cutoff)
            remainder = _remainder_integral(mass, cutoff)
            rows.append({
                "mass": float(mass), "cutoff": int(cutoff), "reference_vacuum_density": float(density),
                "predicted_quadratic_coefficient": float(predicted),
                "scaled_reference_vacuum": float(density / (cutoff * cutoff)),
                "renormalized_static_density": float(remainder),
                "analytic_static_limit": float(analytic),
            })
    return rows


def _kinetic_primitive(cutoff: int) -> float:
    lam = float(cutoff)
    u = lam / math.sqrt(lam * lam + M0 * M0)
    return (math.asinh(lam / M0) - u - u ** 3 / 3.0) / (2.0 * PI2)


def kinetic_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    energies: dict[int, float] = {}
    for cutoff in CUTOFFS:
        measured = _integrate(lambda p: MEASURE * p ** 4 / _energy(p, M0) ** 5, cutoff)
        analytic = _kinetic_primitive(cutoff)
        z_factor = 1.0 - y * y * measured / 2.0
        overlap_energy = _integrate(
            lambda p: 4.0 * MEASURE * p * p * _energy(p, M0) * _overlap_occupation(p), cutoff
        )
        energies[cutoff] = float(overlap_energy)
        rows.append({
            "cutoff": int(cutoff), "kinetic_integral": float(measured),
            "analytic_kinetic_integral": float(analytic), "z_factor": float(z_factor),
            "overlap_energy_density": float(overlap_energy),
        })
    slopes: list[dict[str, Any]] = []
    predicted = NU * NU / (8.0 * PI2)
    for low, high in zip(CUTOFFS[:-1], CUTOFFS[1:]):
        slopes.append({
            "cutoff_low": int(low), "cutoff_high": int(high),
            "measured_log_coefficient": float((energies[high] - energies[low]) / math.log(2.0)),
            "predicted_log_coefficient": float(predicted),
        })
    return rows, slopes


def binding() -> dict[str, Any]:
    reference_mass = M0
    reduced_mass = M0 / 2.0
    alpha = y * y / (4.0 * math.pi)
    radial, _ = quad(lambda r: alpha * math.exp(-OMEGA * r), 0.0, math.inf, epsabs=2.0e-12, epsrel=2.0e-12, limit=500)
    analytic = alpha / OMEGA
    bound = 2.0 * reduced_mass * radial
    return {
        "reference_mass": float(reference_mass), "reduced_mass": float(reduced_mass),
        "yukawa_coupling": float(y), "scalar_mass": float(OMEGA), "alpha": float(alpha),
        "radial_integral": float(radial), "analytic_radial_integral": float(analytic),
        "bargmann_bound": float(bound), "all_partial_waves_excluded": bool(bound < 1.0),
    }


def _symbolic_checks() -> list[dict[str, Any]]:
    import sympy as sp

    p, m0, m1, d, lam, nu = sp.symbols("p m0 m1 d lam nu", positive=True)
    e0 = sp.sqrt(p * p + m0 * m0)
    e1 = sp.sqrt(p * p + m1 * m1)
    delta = m1 - m0
    nq = sp.Rational(1, 2) * (1 - (p * p + m0 * m1) / (e0 * e1))
    vacuum = 2 * ((p * p + m0 * m1) / e0 - e1)
    expected_qnext = -(3 * (m0 ** 4 + m1 ** 4) + 2 * m0 ** 2 * m1 ** 2 - 4 * m0 * m1 * (m0 ** 2 + m1 ** 2)) / 16
    vacuum_next = sp.Rational(3, 2) * m0 ** 2 * delta ** 2 + m0 * delta ** 3 + delta ** 4 / 4
    t4 = (
        -p * p * d * d / (p * p + m0 * m0) ** sp.Rational(3, 2)
        + p * p * m0 * d ** 3 / (p * p + m0 * m0) ** sp.Rational(5, 2)
        + p * p * (p * p - 4 * m0 * m0) * d ** 4 / (4 * (p * p + m0 * m0) ** sp.Rational(7, 2))
    )
    v_d = vacuum.subs(m1, m0 + d)
    vr = -((
        (m0 + d) ** 4 * sp.log((m0 + d) ** 2 / (m0 * m0))
        - 2 * m0 ** 3 * d - 7 * m0 ** 2 * d ** 2
        - sp.Rational(26, 3) * m0 * d ** 3 - sp.Rational(25, 6) * d ** 4
    ) / (16 * sp.pi ** 2))
    u = lam / sp.sqrt(lam * lam + m0 * m0)
    primitive = (sp.asinh(lam / m0) - u - u ** 3 / 3) / (2 * sp.pi ** 2)
    overlap = sp.Rational(1, 2) * (1 - 1 / sp.sqrt(1 + (p * nu / (2 * e0 ** 3)) ** 2))
    checks: list[tuple[str, bool]] = []

    def prove(name: str, expression: Any) -> None:
        try:
            checks.append((name, bool(sp.simplify(expression) == 0)))
        except Exception:
            checks.append((name, False))

    try:
        prove("quench_leading", sp.limit(p * p * nq, p, sp.oo) - delta ** 2 / 4)
        prove("quench_next", sp.limit(p ** 4 * (nq - delta ** 2 / (4 * p * p)), p, sp.oo) - expected_qnext)
        prove("vacuum_leading", sp.limit(p * vacuum, p, sp.oo) + delta ** 2)
        prove("vacuum_next", sp.limit(p ** 3 * (vacuum + delta ** 2 / p), p, sp.oo) - vacuum_next)
        prove("vacuum_taylor", sp.diff(v_d, d, 2).subs(d, 0) * d ** 2 / 2 + sp.diff(v_d, d, 3).subs(d, 0) * d ** 3 / 6 + sp.diff(v_d, d, 4).subs(d, 0) * d ** 4 / 24 - t4)
        reference_derivatives = [
            sp.simplify(sp.diff(vr, d, order).subs(d, 0)) == 0
            for order in range(5)
        ]
        checks.append(("static_reference_conditions", bool(all(reference_derivatives))))
        prove("kinetic_primitive", sp.diff(primitive, lam) - lam ** 4 / (2 * sp.pi ** 2 * (lam * lam + m0 * m0) ** sp.Rational(5, 2)))
        prove("overlap_leading", sp.limit(p ** 4 * overlap, p, sp.oo) - nu ** 2 / 16)
    except Exception:
        for name in ("quench_leading", "quench_next", "vacuum_leading", "vacuum_next", "vacuum_taylor", "static_reference_conditions", "kinetic_primitive", "overlap_leading"):
            if not any(existing == name for existing, _ in checks):
                checks.append((name, False))

    # Actual four-component Dirac trace identities.
    sz = sp.diag(1, -1)
    zero = sp.zeros(2)
    alpha = sp.Matrix.vstack(sp.Matrix.hstack(zero, sz), sp.Matrix.hstack(sz, zero))
    beta = sp.diag(1, 1, -1, -1)
    eye4 = sp.eye(4)
    h0 = p * alpha + m0 * beta
    h1 = p * alpha + m1 * beta
    p0m = (eye4 - h0 / e0) / 2
    p1m = (eye4 - h1 / e1) / 2
    p1p = (eye4 + h1 / e1) / 2
    nplus = sp.trace(p1p * p0m) / 2
    nminus = sp.trace(p1m * (eye4 - p0m)) / 2
    vacuum_trace = sp.trace(h1 * p1m) - sp.trace(h1 * p0m)
    excitation_energy = sp.trace(h1 * (p0m - p1m))
    prove("four_component_vacuum_trace", vacuum_trace - vacuum)
    prove("four_component_excitation_partition", nplus - nminus)
    # Include the positive excitation-energy partition in the same check.
    checks[-1] = ("four_component_excitation_partition", checks[-1][1] and bool(sp.simplify(excitation_energy - 4 * e1 * nplus) == 0))

    order = ("quench_leading", "quench_next", "vacuum_leading", "vacuum_next", "vacuum_taylor", "static_reference_conditions", "kinetic_primitive", "overlap_leading", "four_component_vacuum_trace", "four_component_excitation_partition")
    result = dict(checks)
    return [{"name": name, "pass": bool(result.get(name, False))} for name in order]


def _scalar_close(a: Any, b: Any) -> bool:
    try:
        x = float(a)
        z = float(b)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x) and math.isfinite(z) and abs(x - z) <= 5.0e-9 + 2.0e-9 * abs(z)


def _all_finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(_all_finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(_all_finite(v) for v in value)
    return False


def _row_contract(occupations: list[dict[str, Any]], vacua: list[dict[str, Any]], kinetics: list[dict[str, Any]], slopes: list[dict[str, Any]], symbolic: list[dict[str, Any]], bind: dict[str, Any]) -> bool:
    if len(occupations) != 42 or len(vacua) != 10 or len(kinetics) != 5 or len(slopes) != 4 or len(symbolic) != 10:
        return False
    if any(tuple(row.keys()) != OCCUPATION_KEYS for row in occupations):
        return False
    if any(type(row["cutoff"]) is not int for row in occupations + vacua):
        return False
    if any(row["duration"] != 0.0 for row in occupations[:10]):
        return False
    if tuple(bind.keys()) != BINDING_KEYS:
        return False
    if any(type(bind[key]) not in (int, float) or isinstance(bind[key], bool) for key in BINDING_KEYS[:-1]):
        return False
    if type(bind["all_partial_waves_excluded"]) is not bool:
        return False
    if any(tuple(row.keys()) != VACUUM_KEYS for row in vacua):
        return False
    if any(tuple(row.keys()) != KINETIC_KEYS for row in kinetics):
        return False
    if any(tuple(row.keys()) != OVERLAP_KEYS for row in slopes):
        return False
    if any(tuple(row.keys()) != ("name", "pass") for row in symbolic):
        return False
    expected_q = [(float(m), int(c)) for m in MASSES for c in CUTOFFS]
    actual_q = [(row["mass"], row["cutoff"]) for row in occupations[:10]]
    if [row["kind"] for row in occupations[:10]] != ["quench"] * 10 or actual_q != expected_q:
        return False
    expected_p = [(float(m), float(t), int(c)) for m in MASSES for t in DURATIONS for c in CUTOFFS]
    actual_p = [(row["mass"], row["duration"], row["cutoff"]) for row in occupations[10:40]]
    if [row["kind"] for row in occupations[10:40]] != ["pulse"] * 30 or actual_p != expected_p:
        return False
    if occupations[40]["kind"] != "quench" or occupations[41]["kind"] != "pulse":
        return False
    if occupations[40]["mass"] != float(M0) or occupations[40]["duration"] != 0.0 or occupations[40]["cutoff"] != 512:
        return False
    if occupations[41]["mass"] != float(M0) or occupations[41]["duration"] != 1.0 or occupations[41]["cutoff"] != 512:
        return False
    if [(row["mass"], row["cutoff"]) for row in vacua] != expected_q:
        return False
    if [row["cutoff"] for row in kinetics] != list(CUTOFFS):
        return False
    if [(row["cutoff_low"], row["cutoff_high"]) for row in slopes] != list(zip(CUTOFFS[:-1], CUTOFFS[1:])):
        return False
    if [row["name"] for row in symbolic] != ["quench_leading", "quench_next", "vacuum_leading", "vacuum_next", "vacuum_taylor", "static_reference_conditions", "kinetic_primitive", "overlap_leading", "four_component_vacuum_trace", "four_component_excitation_partition"]:
        return False
    for row in occupations:
        if any(type(row[key]) not in (int, float) or isinstance(row[key], bool) for key in OCCUPATION_KEYS[1:]):
            return False
    for row in vacua:
        if any(type(row[key]) not in (int, float) or isinstance(row[key], bool) for key in VACUUM_KEYS):
            return False
    for row in kinetics:
        if type(row["cutoff"]) is not int or any(type(row[key]) not in (int, float) or isinstance(row[key], bool) for key in KINETIC_KEYS[1:]):
            return False
    for row in slopes:
        if any(type(row[key]) not in (int, float) or isinstance(row[key], bool) for key in OVERLAP_KEYS):
            return False
    return all(type(row["name"]) is str and type(row["pass"]) is bool for row in symbolic)


def _qualification(occupations: list[dict[str, Any]], vacua: list[dict[str, Any]], kinetics: list[dict[str, Any]], slopes: list[dict[str, Any]], symbolic: list[dict[str, Any]], bind: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    failures: list[str] = []
    def test(name: str, condition: bool) -> None:
        if not condition:
            failures.append(name)

    test("symbolic_identities", all(row.get("pass") is True for row in symbolic) and len(symbolic) == 10)
    test("row_contract", _row_contract(occupations, vacua, kinetics, slopes, symbolic, bind))
    test("finite_values", _all_finite({"occupation_rows": occupations, "vacuum_rows": vacua, "kinetic_rows": kinetics, "overlap_slopes": slopes, "binding": bind}))

    controls = occupations[-2:]
    noncontrols = occupations[:-2]
    test("positive_densities", all(row["pair_density"] > 0 and row["excitation_number_density"] > 0 and row["excitation_energy_density"] > 0 for row in noncontrols) and all(abs(row["excitation_number_density"]) <= 5e-12 and abs(row["excitation_energy_density"]) <= 5e-12 for row in controls))
    test("zero_controls", all(abs(row[key]) <= 5e-12 for row in controls for key in ("pair_density", "excitation_number_density", "excitation_energy_density", "scaled_pair_density", "scaled_excitation_energy")))
    test("excitation_count", all(_scalar_close(row["excitation_number_density"], 2.0 * row["pair_density"]) for row in occupations))

    asymptotic = [row for row in occupations if row["cutoff"] == 512 and row["mass"] != M0]
    test("number_asymptotes", all(abs(row["scaled_pair_density"] - row["predicted_number_coefficient"]) <= 0.03 * abs(row["predicted_number_coefficient"]) for row in asymptotic))
    test("energy_asymptotes", all(abs(row["scaled_excitation_energy"] - row["predicted_energy_coefficient"]) <= 0.03 * abs(row["predicted_energy_coefficient"]) for row in asymptotic))
    vac_asymptotic = [row for row in vacua if row["cutoff"] == 512 and row["mass"] != M0]
    test("vacuum_asymptotes", all(abs(row["scaled_reference_vacuum"] - row["predicted_quadratic_coefficient"]) <= 0.002 * abs(row["predicted_quadratic_coefficient"]) for row in vac_asymptotic))
    vac_remainder = [row for row in vacua if row["cutoff"] == 512 and row["mass"] != M0]
    test("static_remainders", all(abs(row["renormalized_static_density"] - row["analytic_static_limit"]) <= 2e-6 for row in vac_remainder))
    test("kinetic_primitive", all(_scalar_close(row["kinetic_integral"], row["analytic_kinetic_integral"]) for row in kinetics))
    test("positive_kinetic_factors", all(row["z_factor"] > 0 for row in kinetics))
    test("overlap_logarithm", bool(slopes) and abs(slopes[-1]["measured_log_coefficient"] - slopes[-1]["predicted_log_coefficient"]) <= 0.002 * abs(slopes[-1]["predicted_log_coefficient"]))
    test("binding_integral", _scalar_close(bind.get("radial_integral"), bind.get("analytic_radial_integral")))
    expected_bound = 2.0 * float(bind.get("reduced_mass", math.nan)) * float(bind.get("radial_integral", math.nan))
    test("binding_trace", _scalar_close(bind.get("bargmann_bound"), expected_bound) and bind.get("all_partial_waves_excluded") is (float(bind.get("bargmann_bound", math.nan)) < 1.0))
    checks = [{"name": name, "pass": name not in failures} for name in CHECK_NAMES]
    return checks, failures


def _empty_receipt(
    schema: str,
    identities: dict[str, Any],
    failures: list[str],
    *,
    occupations: list[dict[str, Any]] | None = None,
    vacua: list[dict[str, Any]] | None = None,
    kinetics: list[dict[str, Any]] | None = None,
    symbolic: list[dict[str, Any]] | None = None,
    slopes: list[dict[str, Any]] | None = None,
    bind: dict[str, Any] | None = None,
    checks: list[dict[str, Any]] | None = None,
    verdicts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": schema, "identities": identities,
        "occupation_rows": [] if occupations is None else occupations,
        "vacuum_rows": [] if vacua is None else vacua,
        "kinetic_rows": [] if kinetics is None else kinetics,
        "symbolic_checks": [] if symbolic is None else symbolic,
        "overlap_slopes": [] if slopes is None else slopes,
        "binding": {} if bind is None else bind,
        "checks": [] if checks is None else checks,
        "verdicts": {} if verdicts is None else verdicts,
        "numerical_pass": False,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    args = parser.parse_args(argv)
    output = args.output_dir
    target = output / "results.json"
    if target.exists():
        print(f"refusing to replace receipt: {target}", file=sys.stderr)
        return 2

    failures: list[str] = []
    identities = {
        "primary": identity(Path(__file__), "primary", failures),
        "verifier": identity(VERIFIER_PATH, "verifier", failures),
        "prereg": identity(args.prereg, "prereg", failures),
        "finite_mode_prereg": identity(FINITE_MODE_PREREG, "finite-mode prereg", failures),
    }
    if failures:
        failures.append("required source or preregistration identity is unavailable")
        receipt = _empty_receipt(SCHEMA, identities, failures)
        try:
            write_json_exclusive(target, receipt)
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 1

    occupations: list[dict[str, Any]] = []
    vacua: list[dict[str, Any]] = []
    kinetics: list[dict[str, Any]] = []
    symbolic: list[dict[str, Any]] = []
    slopes: list[dict[str, Any]] = []
    bind: dict[str, Any] = {}
    checks: list[dict[str, Any]] = []
    try:
        occupations = occupation_rows()
        vacua = vacuum_rows()
        kinetics, slopes = kinetic_rows()
        bind = binding()
        symbolic = _symbolic_checks()
        checks, qualification_failures = _qualification(occupations, vacua, kinetics, slopes, symbolic, bind)
        failures.extend(qualification_failures)
        numerical_pass = not failures
        verdicts = (
            {
                "sudden_source_continuum": "CONTRADICTS—ultraviolet-finite sudden-source continuum completion",
                "static_subtraction": "SUPPORTS—specified static one-loop subtraction identities",
                "initial_overlap": "SUPPORTS—logarithmic initial adiabatic overlap-energy mismatch",
                "two_body_binding": "SUPPORTS—absence of two-body binding in the stated nonrelativistic Yukawa reduction" if bind["all_partial_waves_excluded"] else "INCONCLUSIVE",
            }
            if numerical_pass else {
                "sudden_source_continuum": "INCONCLUSIVE", "static_subtraction": "INCONCLUSIVE",
                "initial_overlap": "INCONCLUSIVE", "two_body_binding": "INCONCLUSIVE",
            }
        )
        receipt = {
            "schema": SCHEMA, "identities": identities, "occupation_rows": occupations, "vacuum_rows": vacua,
            "kinetic_rows": kinetics, "symbolic_checks": symbolic, "overlap_slopes": slopes, "binding": bind,
            "checks": checks, "verdicts": verdicts, "numerical_pass": bool(numerical_pass), "failures": failures,
        }
        write_json_exclusive(target, receipt)
        return 0 if numerical_pass else 1
    except Exception as exc:
        failures.append(f"calculation failure: {type(exc).__name__}: {exc}")
        receipt = _empty_receipt(
            SCHEMA, identities, failures, occupations=occupations, vacua=vacua,
            kinetics=kinetics, symbolic=symbolic, slopes=slopes, bind=bind, checks=checks,
            verdicts={key: "INCONCLUSIVE" for key in (
                "sudden_source_continuum", "static_subtraction",
                "initial_overlap", "two_body_binding",
            )},
        )
        try:
            write_json_exclusive(target, receipt)
        except Exception as write_exc:
            print(str(write_exc), file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
