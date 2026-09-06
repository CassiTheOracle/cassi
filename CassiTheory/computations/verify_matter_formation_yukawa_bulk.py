#!/usr/bin/env python3
"""Independently verify the frozen collective-binding Yukawa calculation.

The verifier deliberately duplicates the mathematics rather than importing the
primary calculation.  It consumes results.json from the primary and writes an
exclusive verification.json receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import mpmath as mp
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
NOTE_PATH = ROOT / "computations/matter-formation-continuum-report.md"
PRIMARY_PATH = ROOT / "computations/matter_formation_yukawa_bulk.py"
FERMION_PREREG = ROOT / "computations/matter-formation-fermion-production-prereg.md"
SCALAR_PREREG = ROOT / "computations/matter-formation-scalar-vacuum-prereg.md"
ACCEPTED_SCALAR = ROOT / "runs/20260906_matter_formation_scalar_vacuum/results.json"
RUN_DIR = ROOT / "runs/20260906_matter_formation_yukawa_bulk"
PRIMARY_SCHEMA = "cassi.matter-formation.yukawa-bulk.v1"
VERIFY_SCHEMA = "cassi.matter-formation.yukawa-bulk.verification.v1"
VERDICT = "SUPPORTS—absence of subthreshold collective binding in the declared mass-depleting local-density Yukawa functional"
ACCEPTED_SCALAR_SHA256 = "b2932913890ee3c97f1d8e05f6d94e08eebbdd34d48b438a9fc647fe2c990dc5"
PROTOCOL_SHA256 = "2d88b59e469260e4949c3090bc7f7042ddfd461453ad653e5e16769a4b55ff26"
FERMION_PREREG_SHA256 = "45be88814f41327feef41abe79b586b41e61f11a8f880081a691c469b9776bf8"
SCALAR_PREREG_SHA256 = "be6760a8044d909101be87b112c6d0c21a00106951b1a5d93282751cba8e31f0"
HEADING = "### 15.6 Collective binding in the declared Yukawa model: pre-execution criteria"
PRECISION = 80
POSITIVE_MASSES = ("0", "1/4", "1/2", "3/4", "15/16", "1")
SIGNED_MASSES = ("-1", "-3/4", "-1/2", "-1/4", "0", "1/4", "1/2", "3/4", "15/16", "1")
MODES = ("threshold", "half", "two")

mp.mp.dps = PRECISION
TOLERANCE = mp.mpf("1e-35")


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def protocol_section(path: Path) -> str:
    text = canonical_bytes(path).decode("utf-8")
    start = text.find(HEADING)
    if start < 0:
        raise ValueError("frozen §15.6 heading is missing")
    end = text.find("\n##", start + len(HEADING))
    if end < 0:
        raise ValueError("next top-level heading after §15.6 is missing")
    return text[start:end] + "\n"


def protocol_identity(path: Path) -> dict[str, Any]:
    section = protocol_section(path)
    return {
        "path": relpath(path),
        "sha256": hashlib.sha256(section.encode("utf-8")).hexdigest(),
        "heading": HEADING,
        "hashes": {"frozen_section_sha256": hashlib.sha256(section.encode("utf-8")).hexdigest()},
    }


def identity(path: Path, *, raw: bool = False) -> dict[str, str]:
    return {"path": relpath(path), "sha256": raw_sha256(path) if raw else canonical_sha256(path)}


def current_identities() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if PRIMARY_PATH.is_file():
        out["primary"] = identity(PRIMARY_PATH)
    else:
        out["primary"] = {"path": relpath(PRIMARY_PATH), "sha256": ""}
    if Path(__file__).is_file():
        out["verifier"] = identity(Path(__file__))
    else:
        out["verifier"] = {"path": relpath(Path(__file__)), "sha256": ""}
    if NOTE_PATH.is_file():
        try:
            out["protocol"] = protocol_identity(NOTE_PATH)
        except Exception:
            out["protocol"] = {"path": relpath(NOTE_PATH), "sha256": "", "heading": HEADING, "hashes": {"frozen_section_sha256": ""}}
    else:
        out["protocol"] = {"path": relpath(NOTE_PATH), "sha256": "", "heading": HEADING, "hashes": {"frozen_section_sha256": ""}}
    for key, path, expected in (
        ("fermion_prereg", FERMION_PREREG, FERMION_PREREG_SHA256),
        ("scalar_prereg", SCALAR_PREREG, SCALAR_PREREG_SHA256),
    ):
        out[key] = identity(path) if path.is_file() else {"path": relpath(path), "sha256": ""}
    out["accepted_scalar_receipt"] = (
        identity(ACCEPTED_SCALAR, raw=True)
        if ACCEPTED_SCALAR.is_file()
        else {"path": relpath(ACCEPTED_SCALAR), "sha256": ""}
    )
    return out


def decimal_text(value: mp.mpf) -> str:
    """Return a finite decimal/scientific string with at least 80 digits."""
    value = mp.mpf(value)
    if not mp.isfinite(value):
        raise ValueError("non-finite numerical witness")
    if value == 0:
        return "0." + "0" * (PRECISION - 1)
    text = mp.nstr(value, PRECISION)
    mantissa, sep, exponent = text.partition("e")
    if not sep:
        mantissa, sep, exponent = text.partition("E")
    if not sep:
        if "." not in mantissa:
            mantissa += "."
        mantissa += "0" * max(0, PRECISION - len(mantissa.replace(".", "").replace("-", "")))
        return mantissa
    digits = len(mantissa.replace(".", "").replace("-", ""))
    if digits < PRECISION:
        if "." not in mantissa:
            mantissa += "."
        mantissa += "0" * (PRECISION - digits)
    return mantissa + "e" + exponent


def mp_value(value: Any, path: str, failures: list[str]) -> mp.mpf | None:
    if not isinstance(value, str) or isinstance(value, bool):
        failures.append(f"{path}: expected decimal string")
        return None
    try:
        parsed = mp.mpf(value)
    except (TypeError, ValueError):
        failures.append(f"{path}: invalid decimal string")
        return None
    if not mp.isfinite(parsed):
        failures.append(f"{path}: non-finite decimal string")
        return None
    return parsed


def tolerance(a: mp.mpf, b: mp.mpf) -> mp.mpf:
    return TOLERANCE * max(mp.mpf(1), abs(a), abs(b))


def close(a: mp.mpf, b: mp.mpf) -> bool:
    return abs(a - b) <= tolerance(a, b)


def rational(label: str) -> mp.mpf:
    return mp.mpf(label.split("/")[0]) / mp.mpf(label.split("/")[1]) if "/" in label else mp.mpf(label)


def pressure_closed(s: mp.mpf, d: int) -> mp.mpf:
    if s == 1:
        return mp.mpf(0)
    if s == 0:
        return mp.mpf(d) / (24 * mp.pi**2)
    k = mp.sqrt(1 - s * s)
    return mp.mpf(d) / (48 * mp.pi**2) * (k * (2 - 5 * s * s) + 3 * s**4 * mp.log((1 + k) / s))


def pressure_energy_integral(s: mp.mpf, d: int) -> mp.mpf:
    if s == 1:
        return mp.mpf(0)
    return mp.mpf(d) / (6 * mp.pi**2) * mp.quad(lambda e: (e * e - s * s) ** mp.mpf("1.5"), [s, 1])


def pressure_momentum_integral(s: mp.mpf, d: int, k: mp.mpf) -> mp.mpf:
    if k == 0:
        return mp.mpf(0)
    if s == 0:
        return mp.mpf(d) * k**4 / (24 * mp.pi**2)
    return mp.mpf(d) / (6 * mp.pi**2) * mp.quad(lambda p: p**4 / mp.sqrt(p * p + s * s), [0, k])


def occupied_energy(s: mp.mpf, d: int, k: mp.mpf) -> mp.mpf:
    if k == 0:
        return mp.mpf(0)
    if s == 0:
        return mp.mpf(d) * k**4 / (8 * mp.pi**2)
    return mp.mpf(d) / (2 * mp.pi**2) * mp.quad(lambda p: p**2 * mp.sqrt(p * p + s * s), [0, k])


def number_density(d: int, k: mp.mpf) -> mp.mpf:
    return mp.mpf(d) * k**3 / (6 * mp.pi**2)


def loop_closed(m: mp.mpf) -> mp.mpf:
    if m == 0:
        return mp.mpf(1) / (32 * mp.pi**2)
    delta = m - 1
    polynomial = 2 * delta + 7 * delta**2 + mp.mpf(26) / 3 * delta**3 + mp.mpf(25) / 6 * delta**4
    return -(m**4 * mp.log(m * m) - polynomial) / (16 * mp.pi**2)


def loop_independent(m: mp.mpf) -> mp.mpf:
    if m >= 0:
        if m == 0:
            return mp.mpf(1) / (32 * mp.pi**2)
        return mp.quad(lambda t: (t - m) ** 4 / t, [m, 1]) / (8 * mp.pi**2)
    s = -m
    polynomial = mp.mpf(1) / 2 + mp.mpf(8) / 3 * s + 6 * s**2 + 8 * s**3 + mp.mpf(25) / 6 * s**4
    return (polynomial - s**4 * mp.log(s * s)) / (16 * mp.pi**2)


def exact_checks() -> list[dict[str, Any]]:
    m, s, mu, k, e, x, d = sp.symbols("m s mu k e x d", positive=True)
    pi = sp.pi
    checks: list[dict[str, Any]] = []

    def add(name: str, condition: bool, **evidence: Any) -> None:
        checks.append({"name": name, "pass": bool(condition), "evidence": {key: str(value) for key, value in evidence.items()}})

    harmonic_value = sp.Rational(3) ** 2 / (2 * sp.Rational(1, 4) ** 2)
    harmonic_residual = harmonic_value - 72
    add("harmonic_coefficient", harmonic_residual == 0, harmonic_coefficient=sp.sstr(harmonic_value), residual=sp.sstr(harmonic_residual), formula="Omega^2/(2*y^2)")
    fifth = sp.simplify(sp.diff(m**4 * sp.log(m**2), m, 5) - 48 / m)
    add("fifth_derivative", fifth == 0, derivative=sp.sstr(sp.diff(m**4 * sp.log(m**2), m, 5)), residual=sp.sstr(fifth))

    delta = m - 1
    polynomial = 2 * delta + 7 * delta**2 + sp.Rational(26, 3) * delta**3 + sp.Rational(25, 6) * delta**4
    positive_integral = sp.integrate((x - m) ** 4 / x, (x, m, 1))
    positive_closed = -(m**4 * sp.log(m**2) - polynomial) / 2
    positive_residual = sp.simplify(positive_integral - positive_closed.subs(sp.log(m**2), 2 * sp.log(m)))
    add("positive_mass_remainder", positive_residual == 0, integral=sp.sstr(positive_integral), residual=sp.sstr(positive_residual))

    zero = sp.integrate(x**3, (x, 0, 1)) / 8
    add("zero_mass_remainder", zero == sp.Rational(1, 32), integral=sp.sstr(zero), residual=sp.sstr(zero - sp.Rational(1, 32)))

    neg_s = sp.symbols("s", nonnegative=True)
    neg_poly = sp.expand(polynomial.subs(m, -neg_s))
    target_poly = sp.Rational(1, 2) + sp.Rational(8, 3) * neg_s + 6 * neg_s**2 + 8 * neg_s**3 + sp.Rational(25, 6) * neg_s**4
    neg_residual = sp.expand(neg_poly - target_poly)
    add("negative_mass_polynomial", neg_residual == 0, polynomial=sp.sstr(neg_poly), residual=sp.sstr(neg_residual))

    mirror = sp.expand((1 + neg_s) ** 2 - (1 - neg_s) ** 2)
    add("mirrored_harmonic_cost", mirror == 4 * neg_s, difference=sp.sstr(mirror), residual=sp.sstr(mirror - 4 * neg_s))

    pk = sp.sqrt(mu**2 - s**2)
    pexpr = d / (48 * pi**2) * (mu * pk * (2 * mu**2 - 5 * s**2) + 3 * s**4 * sp.log((mu + pk) / s))
    pderiv_residual = sp.simplify(sp.diff(pexpr, mu) - d / (6 * pi**2) * (mu**2 - s**2) ** sp.Rational(3, 2))
    add("pressure_mu_derivative", pderiv_residual == 0, residual=sp.sstr(pderiv_residual), derivative=sp.sstr(sp.diff(pexpr, mu)))

    q = sp.sqrt(k**2 + s**2)
    eexpr = d / (16 * pi**2) * (k * q * (2 * k**2 + s**2) - s**4 * sp.log((k + q) / s))
    ederiv_residual = sp.simplify(sp.diff(eexpr, k) - d * k**2 * q / (2 * pi**2))
    add("energy_k_derivative", ederiv_residual == 0, residual=sp.sstr(ederiv_residual), derivative=sp.sstr(sp.diff(eexpr, k)))

    jexpr = (mu * pk * (2 * mu**2 - 5 * s**2) + 3 * s**4 * sp.log((mu + pk) / s)) / 8
    jderiv = sp.simplify(sp.diff(jexpr, mu) - (mu**2 - s**2) ** sp.Rational(3, 2))
    jendpoint = sp.limit(jexpr, mu, s, dir="+")
    delta_u = sp.symbols("delta_u", nonnegative=True)
    power_integral = sp.integrate(sp.Symbol("u", nonnegative=True) ** sp.Rational(3, 2), (sp.Symbol("u", nonnegative=True), 0, delta_u))
    power_residual = sp.simplify(power_integral - sp.Rational(2, 5) * delta_u ** sp.Rational(5, 2))
    add("pressure_power_integral", jderiv == 0 and jendpoint == 0 and power_residual == 0, derivative_residual=sp.sstr(jderiv), endpoint=sp.sstr(jendpoint), power_integral=sp.sstr(power_integral), power_residual=sp.sstr(power_residual))

    alt = sum((-x**2) ** j for j in range(8))
    geometric_residual = sp.simplify(alt - (1 - x**16) / (1 + x**2))
    lower = sp.integrate(alt, (x, 0, 1))
    pi_margin = 4 * lower - 3
    add("pi_lower_bound", geometric_residual == 0 and pi_margin > 0, alternating_integral=sp.sstr(lower), margin=sp.sstr(pi_margin), geometric_residual=sp.sstr(geometric_residual))

    sqrt_margin = sp.Rational(9, 4) - 2
    add("sqrt_upper_bound", sqrt_margin > 0, margin=sp.sstr(sqrt_margin), bound="sqrt(2)<3/2")

    binding = [sp.Rational(72) - sp.Rational(dd, 45) for dd in (2, 4)]
    add("binding_margins", all(value > 0 for value in binding), d2=sp.sstr(binding[0]), d4=sp.sstr(binding[1]))
    return checks


def expected_pressure_rows() -> list[dict[str, Any]]:
    rows = []
    for label in POSITIVE_MASSES:
        s = rational(label)
        k = mp.sqrt(1 - s * s)
        momentum = pressure_momentum_integral(s, 4, k)
        energy_int = pressure_energy_integral(s, 4)
        bound = mp.mpf(4) / 45 * (1 - s) ** 2
        rows.append({"s": label, "d": 4, "pressure": decimal_text(momentum), "quadrature_pressure": decimal_text(energy_int), "rational_bound": decimal_text(bound), "pass": close(momentum, energy_int) and momentum >= -tolerance(momentum, mp.mpf(0)) and momentum <= bound + tolerance(momentum, bound)})
    return rows


def expected_remainder_rows() -> list[dict[str, Any]]:
    rows = []
    for label in SIGNED_MASSES:
        m = rational(label)
        closed = loop_closed(m)
        independent = loop_independent(m)
        harmonic = mp.mpf(72) * (m - 1) ** 2
        deficit = mp.mpf(72) * (1 - abs(m)) ** 2
        rows.append({"m": label, "closed_remainder": decimal_text(closed), "independent_form": decimal_text(independent), "harmonic_energy": decimal_text(harmonic), "mass_deficit_bound": decimal_text(deficit), "pass": close(closed, independent) and closed >= -tolerance(closed, mp.mpf(0)) and harmonic >= deficit - tolerance(harmonic, deficit)})
    return rows


def expected_grand_rows() -> list[dict[str, Any]]:
    rows = []
    for label in POSITIVE_MASSES:
        s = rational(label)
        threshold = mp.sqrt(1 - s * s)
        pressure = pressure_momentum_integral(s, 4, threshold)
        for mode in MODES:
            k = threshold if mode == "threshold" else (mp.mpf(1) / 2 if mode == "half" else mp.mpf(2))
            energy = occupied_energy(s, 4, k)
            density = number_density(4, k)
            grand = energy - density
            margin = grand + pressure
            row_pass = abs(margin) <= tolerance(margin, mp.mpf(0)) if mode == "threshold" else margin >= -tolerance(margin, mp.mpf(0))
            rows.append({"s": label, "k_mode": mode, "k": decimal_text(k), "occupied_energy": decimal_text(energy), "number_density": decimal_text(density), "grand_energy": decimal_text(grand), "pressure": decimal_text(pressure), "duality_margin": decimal_text(margin), "pass": row_pass})
    return rows


def check_item(name: str, passed: bool, evidence: str = "") -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "evidence": {"detail": str(evidence)}}


def validate_identities(actual: Any, current: dict[str, dict[str, Any]], failures: list[str]) -> bool:
    if not isinstance(actual, dict):
        failures.append("identities: expected object")
        return False
    ok = True
    if set(actual) != set(current):
        failures.append("identities: key set mismatch")
        ok = False
    for key, expected in current.items():
        item = actual.get(key)
        if not isinstance(item, dict):
            failures.append(f"identities.{key}: expected object")
            ok = False
            continue
        if item.get("path") != expected.get("path"):
            failures.append(f"identities.{key}.path: current path mismatch")
            ok = False
        if key == "protocol":
            hashes = item.get("hashes")
            expected_hashes = expected.get("hashes")
            if item.get("heading") != HEADING or not isinstance(hashes, dict) or hashes.get("frozen_section_sha256") != PROTOCOL_SHA256 or item.get("sha256") != PROTOCOL_SHA256 or expected.get("sha256") != PROTOCOL_SHA256 or not isinstance(expected_hashes, dict) or expected_hashes.get("frozen_section_sha256") != PROTOCOL_SHA256:
                failures.append("identities.protocol: frozen section mismatch")
                ok = False
        elif key in ("fermion_prereg", "scalar_prereg"):
            wanted = FERMION_PREREG_SHA256 if key == "fermion_prereg" else SCALAR_PREREG_SHA256
            if item.get("sha256") != wanted or expected.get("sha256") != wanted:
                failures.append(f"identities.{key}: canonical preregistration hash mismatch")
                ok = False
        elif key == "accepted_scalar_receipt":
            if item.get("sha256") != ACCEPTED_SCALAR_SHA256 or expected.get("sha256") != ACCEPTED_SCALAR_SHA256:
                failures.append("identities.accepted_scalar_receipt: raw receipt hash mismatch")
                ok = False
        elif item.get("sha256") != expected.get("sha256"):
            failures.append(f"identities.{key}.sha256: current source hash mismatch")
            ok = False
    return ok


def compare_exact_rows(stored: Any, fresh: list[dict[str, Any]], failures: list[str]) -> tuple[bool, bool]:
    """Validate exact-row schema and independently compare only qualification flags."""
    if not isinstance(stored, list) or len(stored) != len(fresh):
        failures.append("algebraic_checks: row count mismatch")
        return False, False
    shape_ok = True
    pass_ok = True
    for index, (given, expected) in enumerate(zip(stored, fresh)):
        path = f"algebraic_checks[{index}]"
        if not isinstance(given, dict) or set(given) != {"name", "pass", "evidence"}:
            failures.append(f"{path}: expected name/pass/evidence object")
            shape_ok = False
            continue
        if given.get("name") != expected["name"]:
            failures.append(f"{path}.name: order/name mismatch")
            shape_ok = False
        if not isinstance(given.get("pass"), bool):
            failures.append(f"{path}.pass: expected bool")
            shape_ok = False
        elif given["pass"] != expected["pass"]:
            failures.append(f"{path}.pass: stored exact predicate differs from independent predicate")
            pass_ok = False
        evidence = given.get("evidence")
        if not isinstance(evidence, dict) or not evidence or any(not isinstance(key, str) or not isinstance(value, str) for key, value in evidence.items()):
            failures.append(f"{path}.evidence: expected nonempty string-valued object")
            shape_ok = False
    return shape_ok, pass_ok


def validate_primary(primary: Any, current: dict[str, dict[str, Any]], failures: list[str]) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(primary, dict):
        failures.append("primary receipt: expected JSON object")
        return False, [], [], [], []
    shape_ok = True
    expected_keys = {"schema", "identities", "parameters", "algebraic_checks", "pressure_rows", "remainder_rows", "grand_rows", "numerical_pass", "verdict", "failures"}
    if set(primary) != expected_keys:
        failures.append("primary: top-level key set mismatch")
        shape_ok = False
    if primary.get("schema") != PRIMARY_SCHEMA:
        failures.append("primary.schema: mismatch")
        shape_ok = False
    validate_identities(primary.get("identities"), current, failures)
    expected_params = {"m0": "1", "y": "1/4", "Omega": "3", "precision_dps": 80, "comparison_tolerance": "1e-35", "degeneracies": [2, 4]}
    if primary.get("parameters") != expected_params:
        failures.append("primary.parameters: frozen parameter mismatch")
        shape_ok = False
    if not isinstance(primary.get("failures"), list) or any(not isinstance(item, str) for item in primary.get("failures", [])):
        failures.append("primary.failures: expected string array")
        shape_ok = False
    if not isinstance(primary.get("verdict"), str):
        failures.append("primary.verdict: expected string")
        shape_ok = False
    if not isinstance(primary.get("numerical_pass"), bool):
        failures.append("primary.numerical_pass: expected bool")
        shape_ok = False
    exact = primary.get("algebraic_checks")
    pressure = primary.get("pressure_rows")
    remainder = primary.get("remainder_rows")
    grand = primary.get("grand_rows")
    for value, count, name in ((exact, 12, "algebraic_checks"), (pressure, 6, "pressure_rows"), (remainder, 10, "remainder_rows"), (grand, 18, "grand_rows")):
        if not isinstance(value, list) or len(value) != count:
            failures.append(f"primary.{name}: expected {count} rows")
            shape_ok = False
    return shape_ok, exact if isinstance(exact, list) else [], pressure if isinstance(pressure, list) else [], remainder if isinstance(remainder, list) else [], grand if isinstance(grand, list) else []


def compare_row_fields(stored: Any, fresh: list[dict[str, Any]], kind: str, failures: list[str]) -> bool:
    if not isinstance(stored, list) or len(stored) != len(fresh):
        failures.append(f"{kind}: row count mismatch")
        return False
    ok = True
    for index, (given, expected) in enumerate(zip(stored, fresh)):
        path = f"{kind}[{index}]"
        if not isinstance(given, dict):
            failures.append(f"{path}: expected object")
            ok = False
            continue
        if set(given) != set(expected):
            failures.append(f"{path}: field set mismatch")
            ok = False
            continue
        for key, wanted in expected.items():
            if key == "pass":
                if not isinstance(given.get(key), bool):
                    failures.append(f"{path}.pass: expected bool")
                    ok = False
                elif given[key] != wanted:
                    failures.append(f"{path}.pass: stored qualification differs from independent qualification")
                    ok = False
                continue
            if key in ("s", "m", "k_mode"):
                if given.get(key) != wanted:
                    failures.append(f"{path}.{key}: schedule/order mismatch")
                    ok = False
                continue
            if key == "d":
                if type(given.get(key)) is not int or given[key] != wanted:
                    failures.append(f"{path}.d: exact integer degeneracy mismatch")
                    ok = False
                continue
            observed = mp_value(given.get(key), f"{path}.{key}", failures)
            target = mp_value(wanted, f"fresh {path}.{key}", failures)
            if observed is None or target is None or not close(observed, target):
                failures.append(f"{path}.{key}: independent numerical mismatch")
                ok = False
    return ok

def verify_receipt(input_dir: Path, output_dir: Path, note_path: Path) -> tuple[dict[str, Any], int]:
    current = current_identities()
    receipt: dict[str, Any] = {
        "schema": VERIFY_SCHEMA,
        "identities": current,
        "input_sha256": "",
        "reconstructed": {"algebraic_checks": [], "pressure_rows": [], "remainder_rows": [], "grand_rows": []},
        "checks": [],
        "numerical_pass": False,
        "verdict": "INCONCLUSIVE",
        "failures": ([] if note_path.resolve() == NOTE_PATH.resolve() else [f"required input failure: alternate note path rejected; expected {relpath(NOTE_PATH)}"]),
    }
    failures: list[str] = receipt["failures"]
    if not note_path.is_file():
        failures.append(f"required input failure: missing working note {relpath(note_path)}")
    if not PRIMARY_PATH.is_file():
        failures.append(f"required input failure: missing verifier-bound primary source {relpath(PRIMARY_PATH)}")
    primary_path = input_dir / "results.json"
    if not primary_path.is_file():
        failures.append(f"required input failure: missing primary results {primary_path}")
    if failures:
        return receipt, 1
    try:
        raw = primary_path.read_bytes()
        receipt["input_sha256"] = hashlib.sha256(raw).hexdigest()
        primary = json.loads(raw.decode("utf-8"))
    except Exception as error:
        failures.append(f"input failure: cannot load primary receipt: {type(error).__name__}: {error}")
        return receipt, 1

    exact = exact_checks()
    pressure = expected_pressure_rows()
    remainder = expected_remainder_rows()
    grand = expected_grand_rows()
    receipt["reconstructed"] = {"algebraic_checks": exact, "pressure_rows": pressure, "remainder_rows": remainder, "grand_rows": grand}
    shape_ok, stored_exact, stored_pressure, stored_remainder, stored_grand = validate_primary(primary, current, failures)
    checks: list[dict[str, Any]] = receipt["checks"]
    checks.append(check_item("input_schema", primary.get("schema") == PRIMARY_SCHEMA, "primary schema is frozen"))
    checks.append(check_item("parameter_values", primary.get("parameters") == {"m0": "1", "y": "1/4", "Omega": "3", "precision_dps": 80, "comparison_tolerance": "1e-35", "degeneracies": [2, 4]}, "frozen parameters"))
    identities_ok = validate_identities(primary.get("identities"), current, failures)
    checks.append(check_item("current_hashes", identities_ok, "source, protocol, preregistration and accepted receipt identities"))
    checks.append(check_item("row_shapes", shape_ok, "all required row counts and primary schema fields"))

    exact_shape_ok, exact_flags_ok = compare_exact_rows(stored_exact, exact, failures)
    checks.append(check_item("algebraic_checks", exact_shape_ok and exact_flags_ok and all(row["pass"] for row in exact), "independently constructed SymPy predicates"))
    pressure_ok = compare_row_fields(stored_pressure, pressure, "pressure_rows", failures)
    remainder_ok = compare_row_fields(stored_remainder, remainder, "remainder_rows", failures)
    grand_ok = compare_row_fields(stored_grand, grand, "grand_rows", failures)
    checks.append(check_item("pressure_rows", pressure_ok and all(row["pass"] for row in pressure), "momentum and energy-integral pressure reconstruction"))
    checks.append(check_item("remainder_rows", remainder_ok and all(row["pass"] for row in remainder), "integral and negative-mass polynomial reconstruction"))
    checks.append(check_item("grand_rows", grand_ok and all(row["pass"] for row in grand), "occupied-energy momentum quadrature and duality margins"))

    expected_science = bool(identities_ok and shape_ok and exact_shape_ok and exact_flags_ok and all(row["pass"] for row in exact) and pressure_ok and all(row["pass"] for row in pressure) and remainder_ok and all(row["pass"] for row in remainder) and grand_ok and all(row["pass"] for row in grand))
    primary_failures = primary.get("failures")
    stored_flags_ok = isinstance(primary.get("numerical_pass"), bool) and isinstance(primary_failures, list) and all(isinstance(item, str) for item in primary_failures)
    if stored_flags_ok:
        stored_flags_ok = primary.get("numerical_pass") is expected_science
        if expected_science:
            stored_flags_ok = stored_flags_ok and not primary_failures
        else:
            stored_flags_ok = stored_flags_ok and bool(primary_failures)
    if not stored_flags_ok:
        failures.append("primary pass/failure flags: inconsistent with independently reconstructed qualification")
    checks.append(check_item("stored_pass_flags", stored_flags_ok, "primary flags are checked, never trusted"))
    expected_verdict = VERDICT if expected_science and stored_flags_ok and not failures else "INCONCLUSIVE"
    if primary.get("verdict") != expected_verdict:
        failures.append("primary.verdict: inconsistent with independent qualification")
    checks.append(check_item("stored_verdict", primary.get("verdict") == expected_verdict, expected_verdict))
    receipt["numerical_pass"] = bool(expected_science and stored_flags_ok and not failures)
    receipt["verdict"] = VERDICT if receipt["numerical_pass"] else "INCONCLUSIVE"
    if not identities_ok:
        receipt["numerical_pass"] = False
        receipt["verdict"] = "INCONCLUSIVE"
    return receipt, 0 if receipt["numerical_pass"] else 1


def write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=RUN_DIR)
    parser.add_argument("--note-path", type=Path, default=NOTE_PATH)
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    input_dir = args.input_dir if args.input_dir.is_absolute() else ROOT / args.input_dir
    note_path = args.note_path if args.note_path.is_absolute() else ROOT / args.note_path
    target = output_dir / "verification.json"
    if target.exists():
        raise SystemExit(f"refusing to overwrite existing verification receipt: {target}")
    try:
        receipt, status = verify_receipt(input_dir, output_dir, note_path)
    except Exception as error:
        receipt = {
            "schema": VERIFY_SCHEMA,
            "identities": current_identities(),
            "input_sha256": "",
            "reconstructed": {"algebraic_checks": [], "pressure_rows": [], "remainder_rows": [], "grand_rows": []},
            "checks": [],
            "numerical_pass": False,
            "verdict": "INCONCLUSIVE",
            "failures": [f"verification failure: {type(error).__name__}: {error}"],
        }
        status = 1
    write_exclusive(target, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
