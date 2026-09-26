#!/usr/bin/env python3
"""Primary fixed collective-binding calculation for frozen §15.6.

This program is intentionally independent of the verifier.  It records exact
SymPy/Fraction identities and the registered 80-digit numerical witnesses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

import mpmath as mp
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "computations" / "matter-formation-continuum-report.md"
FERMION_PREREG = ROOT / "computations" / "matter-formation-fermion-production-prereg.md"
SCALAR_PREREG = ROOT / "computations" / "matter-formation-scalar-vacuum-prereg.md"
VERIFIER = ROOT / "computations" / "verify_matter_formation_yukawa_bulk.py"
ACCEPTED_SCALAR = ROOT / "runs" / "20260906_matter_formation_scalar_vacuum" / "results.json"
SCHEMA = "cassi.matter-formation.yukawa-bulk.v1"
VERDICT = "SUPPORTS—absence of subthreshold collective binding in the declared mass-depleting local-density Yukawa functional"
EXPECTED_PROTOCOL_SHA = "2d88b59e469260e4949c3090bc7f7042ddfd461453ad653e5e16769a4b55ff26"
EXPECTED_FERMION_SHA = "45be88814f41327feef41abe79b586b41e61f11a8f880081a691c469b9776bf8"
EXPECTED_SCALAR_SHA = "be6760a8044d909101be87b112c6d0c21a00106951b1a5d93282751cba8e31f0"
EXPECTED_ACCEPTED_SHA = "b2932913890ee3c97f1d8e05f6d94e08eebbdd34d48b438a9fc647fe2c990dc5"
PROTOCOL_HEADING = "### 15.6 Collective binding in the declared Yukawa model: pre-execution criteria"

PRECISION_DPS = 80
mp.mp.dps = PRECISION_DPS
TOLERANCE = mp.mpf("1e-35")
POSITIVE_MASSES = ("0", "1/4", "1/2", "3/4", "15/16", "1")
SIGNED_MASSES = ("-1", "-3/4", "-1/2", "-1/4", "0", "1/4", "1/2", "3/4", "15/16", "1")
K_MODES = ("threshold", "half", "two")


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()

def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(__import__("os").path.relpath(path.resolve(), ROOT)).as_posix()


def frozen_section_bytes(path: Path) -> bytes:
    text = canonical_bytes(path).decode("utf-8")
    heading = PROTOCOL_HEADING + "\n"
    start = text.index(heading)
    body_start = start + len(heading)
    marker = text.find("\n##", body_start)
    if marker < 0:
        raise ValueError("next section after frozen §15.6 not found")
    return text[start:marker + 1].encode("utf-8")

def identity(path: Path, label: str, failures: list[str], *, raw: bool = False) -> dict[str, str]:
    result = {"path": relative_path(path), "sha256": ""}
    try:
        result["sha256"] = raw_sha256(path) if raw else canonical_sha256(path)
    except Exception as exc:
        failures.append(f"missing {label} identity: {type(exc).__name__}: {exc}")
    return result


def protocol_identity(failures: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"path": relative_path(REPORT), "sha256": "", "heading": PROTOCOL_HEADING, "hashes": {"frozen_section_sha256": ""}}
    try:
        digest = hashlib.sha256(frozen_section_bytes(REPORT)).hexdigest()
        result["sha256"] = digest
        result["hashes"]["frozen_section_sha256"] = digest
        if digest != EXPECTED_PROTOCOL_SHA:
            failures.append(f"frozen §15.6 hash mismatch: expected {EXPECTED_PROTOCOL_SHA}, got {digest}")
    except Exception as exc:
        failures.append(f"missing protocol identity: {type(exc).__name__}: {exc}")
    return result


def as_json(value: Any) -> Any:
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
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(as_json(payload), stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def decimal(value: Any) -> str:
    value = mp.mpf(value)
    if not mp.isfinite(value):
        raise ValueError("non-finite numerical witness")
    if value == 0:
        return "0." + "0" * 89
    return mp.nstr(value, 90, strip_zeros=False)




def rational_value(label: str) -> mp.mpf:
    if "/" in label:
        numerator, denominator = label.split("/", 1)
        return mp.mpf(numerator) / mp.mpf(denominator)
    return mp.mpf(label)


def tolerance(a: mp.mpf, b: mp.mpf) -> mp.mpf:
    return TOLERANCE * max(mp.mpf(1), abs(a), abs(b))


def close(a: mp.mpf, b: mp.mpf) -> bool:
    return abs(a - b) <= tolerance(a, b)


def exact_check(name: str, passed: bool, evidence: dict[str, str]) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "evidence": {str(k): str(v) for k, v in evidence.items()}}


def algebraic_checks() -> list[dict[str, Any]]:
    m, s, mu, k, p, x = sp.symbols("m s mu k p x", positive=True)
    u, delta = sp.symbols("u delta", positive=True)
    pi = sp.pi
    dvar = m - 1
    polynomial = 2 * dvar + 7 * dvar**2 + sp.Rational(26, 3) * dvar**3 + sp.Rational(25, 6) * dvar**4
    potential = 72 * dvar**2 - (m**4 * sp.log(m**2) - polynomial) / (16 * pi**2)
    g = m**4 * sp.log(m**2)
    positive_integral = sp.integrate((x - m) ** 4 / x, (x, m, 1))
    positive_closed = (1 - m**4) / 4 - 4 * m * (1 - m**3) / 3 + 3 * m**2 * (1 - m**2) - 4 * m**3 * (1 - m) - m**4 * sp.log(m)
    positive_vr = -(m**4 * sp.log(m**2) - polynomial) / (16 * pi**2)
    negative_poly = sp.expand((2 * (m - 1) + 7 * (m - 1) ** 2 + sp.Rational(26, 3) * (m - 1) ** 3 + sp.Rational(25, 6) * (m - 1) ** 4).subs(m, -s))
    negative_target = sp.Rational(1, 2) + sp.Rational(8, 3) * s + 6 * s**2 + 8 * s**3 + sp.Rational(25, 6) * s**4
    pressure = (4 / (48 * pi**2)) * (mu * sp.sqrt(mu**2 - s**2) * (2 * mu**2 - 5 * s**2) + 3 * s**4 * sp.log((mu + sp.sqrt(mu**2 - s**2)) / s))
    pressure_mu = 4 * (mu**2 - s**2) ** sp.Rational(3, 2) / (6 * pi**2)
    energy = 4 / (16 * pi**2) * (k * sp.sqrt(k**2 + s**2) * (2 * k**2 + s**2) - s**4 * sp.log((k + sp.sqrt(k**2 + s**2)) / s))
    energy_k = 4 * k**2 * sp.sqrt(k**2 + s**2) / (2 * pi**2)
    pressure_primitive = (p * sp.sqrt(p**2 + s**2) * (2 * p**2 - 3 * s**2) + 3 * s**4 * sp.log((p + sp.sqrt(p**2 + s**2)) / s)) / 8
    pressure_integrand = p**4 / sp.sqrt(p**2 + s**2)
    pi_poly = sum((-x**2) ** j for j in range(8))
    pi_integral = sp.integrate(pi_poly, (x, 0, 1))
    margins = [sp.Rational(72) - sp.Rational(d, 45) for d in (2, 4)]
    return [
        exact_check("harmonic_coefficient", sp.diff(potential, m, 2).subs(m, 1) == 144 and sp.Rational(1, 4) ** 2 * 144 == 9 and sp.Integer(9) / (2 * sp.Rational(1, 4) ** 2) == 72, {"harmonic_coefficient": "U''(1)=144; y^2 U''(1)=9; Omega^2/(2 y^2)=9/(2*(1/4)^2)=72"}),
        exact_check("fifth_derivative", sp.simplify(sp.diff(g, m, 5) - 48 / m) == 0, {"fifth_derivative": "d^5[m^4 log(m^2)]/dm^5=48/m"}),
        exact_check("positive_mass_remainder", sp.simplify(positive_closed - positive_integral) == 0 and sp.simplify(positive_vr - positive_integral / (8 * pi**2)) == 0, {"positive_mass_remainder": "V_R(m)=-(m^4 log(m^2)-P(m-1))/(16*pi^2)=1/(8*pi^2)*int_m^1 (t-m)^4/t dt"}),
        exact_check("zero_mass_remainder", sp.limit(positive_closed, m, 0, dir="+") == sp.Rational(1, 4) and sp.limit(positive_vr, m, 0, dir="+") == 1 / (32 * pi**2), {"zero_mass_remainder": "lim_(m->0+) 8*pi^2 V_R(m)=1/4; V_R(0)=1/(32*pi^2)"}),
        exact_check("negative_mass_polynomial", sp.expand(negative_poly - negative_target) == 0, {"negative_mass_polynomial": "P(-1-s)=1/2+8s/3+6s^2+8s^3+25s^4/6"}),
        exact_check("mirrored_harmonic_cost", sp.expand((1 + s) ** 2 - (1 - s) ** 2 - 4 * s) == 0, {"mirrored_harmonic_cost": "(1+s)^2-(1-s)^2=4s>=0 on 0<=s<=1"}),
        exact_check("pressure_mu_derivative", sp.simplify(sp.diff(pressure, mu) - pressure_mu) == 0, {"pressure_mu_derivative": "dP/dmu=4*(mu^2-s^2)^(3/2)/(6*pi^2)"}),
        exact_check("energy_k_derivative", sp.simplify(sp.diff(energy, k) - energy_k) == 0, {"energy_k_derivative": "d epsilon/dk=4*k^2*sqrt(k^2+s^2)/(2*pi^2)"}),
        exact_check("pressure_power_integral", sp.simplify(sp.diff(pressure_primitive, p) - pressure_integrand) == 0 and pressure_primitive.subs(p, 0) == 0 and sp.integrate(u ** sp.Rational(3, 2), (u, 0, delta)) == sp.Rational(2, 5) * delta ** sp.Rational(5, 2), {"pressure_power_integral": "int_0^k p^4/sqrt(p^2+s^2) dp has the stated primitive; int_0^delta u^(3/2)du=2/5 delta^(5/2)"}),
        exact_check("pi_lower_bound", pi_integral == sp.Rational(33976, 45045) and sp.simplify(pi_poly - (1 - x**16) / (1 + x**2)) == 0 and 4 * pi_integral - 3 > 0, {"pi_lower_bound": "geometric identity sum_{j=0}^7(-x^2)^j=(1-x^16)/(1+x^2); integral=33976/45045; 4*integral-3>0, hence pi>3"}),
        exact_check("sqrt_upper_bound", Fraction(9, 4) - 2 > 0, {"sqrt_upper_bound": "9/4-2=1/4>0, hence sqrt(2)<3/2"}),
        exact_check("binding_margins", all(item > 0 for item in margins), {"binding_margins": "d=2: 3238/45; d=4: 3236/45; both positive"}),
    ]


def pressure_closed(s: mp.mpf, mu: mp.mpf, degeneracy: int = 4) -> mp.mpf:
    if s == 0:
        return mp.mpf(degeneracy) * mu**4 / (24 * mp.pi**2)
    k = mp.sqrt(mu**2 - s**2)
    if k == 0:
        return mp.mpf(0)
    return mp.mpf(degeneracy) / (48 * mp.pi**2) * (mu * k * (2 * mu**2 - 5 * s**2) + 3 * s**4 * mp.log((mu + k) / s))


def pressure_quadrature(s: mp.mpf, mu: mp.mpf, degeneracy: int = 4) -> mp.mpf:
    if s == mu:
        return mp.mpf(0)
    if s == 0:
        return mp.mpf(degeneracy) * mu**4 / (24 * mp.pi**2)
    return mp.mpf(degeneracy) / (6 * mp.pi**2) * mp.quad(lambda energy: (energy**2 - s**2) ** mp.mpf("1.5"), [s, mu])


def pressure_rows() -> list[dict[str, Any]]:
    rows = []
    for label in POSITIVE_MASSES:
        s = rational_value(label)
        closed = pressure_closed(s, mp.mpf(1))
        quadrature = pressure_quadrature(s, mp.mpf(1))
        bound = mp.mpf(4) / 45 * (1 - s) ** 2
        rows.append({"s": label, "d": 4, "pressure": decimal(closed), "quadrature_pressure": decimal(quadrature), "rational_bound": decimal(bound), "pass": bool(close(closed, quadrature) and closed >= -tolerance(closed, mp.mpf(0)) and closed <= bound + tolerance(closed, bound))})
    return rows


def positive_remainder(mass: mp.mpf) -> mp.mpf:
    if mass == 0:
        return mp.mpf(1) / (32 * mp.pi**2)
    if mass == 1:
        return mp.mpf(0)
    return ((1 - mass**4) / 4 - 4 * mass * (1 - mass**3) / 3 + 3 * mass**2 * (1 - mass**2) - 4 * mass**3 * (1 - mass) - mass**4 * mp.log(mass)) / (8 * mp.pi**2)


def remainder_rows() -> list[dict[str, Any]]:
    rows = []
    for label in SIGNED_MASSES:
        mass = rational_value(label)
        if mass >= 0:
            closed = positive_remainder(mass)
            independent = closed if mass in (0, 1) else mp.quad(lambda t: (t - mass) ** 4 / t, [mass, 1]) / (8 * mp.pi**2)
        else:
            s = -mass
            dmass = mass - 1
            closed_poly = 2 * dmass + 7 * dmass**2 + mp.mpf(26) / 3 * dmass**3 + mp.mpf(25) / 6 * dmass**4
            closed = (closed_poly - mass**4 * mp.log(mass**2)) / (16 * mp.pi**2)
            independent_poly = mp.mpf(1) / 2 + mp.mpf(8) / 3 * s + 6 * s**2 + 8 * s**3 + mp.mpf(25) / 6 * s**4
            independent = (independent_poly - s**4 * mp.log(s**2)) / (16 * mp.pi**2)
        harmonic = 72 * (mass - 1) ** 2
        deficit = 72 * (1 - abs(mass)) ** 2
        rows.append({"m": label, "closed_remainder": decimal(closed), "independent_form": decimal(independent), "harmonic_energy": decimal(harmonic), "mass_deficit_bound": decimal(deficit), "pass": bool(close(closed, independent) and closed >= -tolerance(closed, mp.mpf(0)) and harmonic + tolerance(harmonic, deficit) >= deficit)})
    return rows


def occupied_energy(k: mp.mpf, s: mp.mpf, degeneracy: int = 4) -> mp.mpf:
    if k == 0:
        return mp.mpf(0)
    if s == 0:
        return mp.mpf(degeneracy) * k**4 / (8 * mp.pi**2)
    root = mp.sqrt(k**2 + s**2)
    return mp.mpf(degeneracy) / (16 * mp.pi**2) * (k * root * (2 * k**2 + s**2) - s**4 * mp.log((k + root) / s))


def grand_rows() -> list[dict[str, Any]]:
    rows = []
    for label in POSITIVE_MASSES:
        s = rational_value(label)
        threshold_k = mp.sqrt(1 - s**2)
        fixed_pressure = pressure_closed(s, mp.mpf(1))
        for mode in K_MODES:
            k = threshold_k if mode == "threshold" else (mp.mpf("0.5") if mode == "half" else mp.mpf(2))
            energy = occupied_energy(k, s)
            density = 4 * k**3 / (6 * mp.pi**2)
            grand = energy - density
            margin = grand + fixed_pressure
            row_pass = bool(abs(margin) <= tolerance(margin, mp.mpf(0)) if mode == "threshold" else margin >= -tolerance(margin, mp.mpf(0)))
            rows.append({"s": label, "k_mode": mode, "k": decimal(k), "occupied_energy": decimal(energy), "number_density": decimal(density), "grand_energy": decimal(grand), "pressure": decimal(fixed_pressure), "duality_margin": decimal(margin), "pass": row_pass})
    return rows


def collect_identities(failures: list[str]) -> dict[str, Any]:
    identities = {
        "primary": identity(Path(__file__), "primary source", failures),
        "verifier": identity(VERIFIER, "verifier source", failures),
        "protocol": protocol_identity(failures),
        "fermion_prereg": identity(FERMION_PREREG, "fermion preregistration", failures),
        "scalar_prereg": identity(SCALAR_PREREG, "scalar preregistration", failures),
        "accepted_scalar_receipt": identity(ACCEPTED_SCALAR, "accepted scalar receipt", failures, raw=True),
    }
    for key, expected in (("fermion_prereg", EXPECTED_FERMION_SHA), ("scalar_prereg", EXPECTED_SCALAR_SHA), ("accepted_scalar_receipt", EXPECTED_ACCEPTED_SHA)):
        actual = identities[key]["sha256"]
        if actual != expected:
            failures.append(f"{key} hash mismatch: expected {expected}, got {actual}")
    return identities

def validate_accepted_receipt(failures: list[str]) -> None:
    """Require the already-accepted scalar receipt to remain sealed and PASS."""
    try:
        with ACCEPTED_SCALAR.open("r", encoding="utf-8") as stream:
            receipt = json.load(stream)
        if not isinstance(receipt, dict):
            raise ValueError("accepted scalar receipt is not an object")
        if receipt.get("schema") != "cassi-scalar-vacuum-boundary-v1":
            raise ValueError("accepted scalar receipt schema mismatch")
        if receipt.get("numerical_pass") is not True or receipt.get("failures") != []:
            raise ValueError("accepted scalar receipt is not a clean PASS")
        receipt_ids = receipt.get("identities")
        if not isinstance(receipt_ids, dict):
            raise ValueError("accepted scalar receipt identities malformed")
        for key, expected_path in (
            ("program", ROOT / "computations" / "verify_matter_formation_scalar_vacuum.py"),
            ("prereg", SCALAR_PREREG),
            ("continuum_prereg", ROOT / "computations" / "matter-formation-continuum-admissibility-prereg.md"),
        ):
            item = receipt_ids.get(key)
            if not isinstance(item, dict) or item.get("path") != relative_path(expected_path):
                raise ValueError(f"accepted scalar identity {key} malformed")
            recorded = item.get("sha256")
            if not isinstance(recorded, str) or not recorded:
                raise ValueError(f"accepted scalar identity {key} missing hash")
            current = canonical_sha256(expected_path)
            if recorded != current:
                raise ValueError(f"accepted scalar identity {key} hash no longer matches current source")
    except Exception as exc:
        failures.append(f"accepted scalar evidence mismatch: {type(exc).__name__}: {exc}")


def base_result(identities: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "identities": identities,
        "parameters": {"m0": "1", "y": "1/4", "Omega": "3", "precision_dps": 80, "comparison_tolerance": "1e-35", "degeneracies": [2, 4]},
        "algebraic_checks": [],
        "pressure_rows": [],
        "remainder_rows": [],
        "grand_rows": [],
        "numerical_pass": False,
        "verdict": "INCONCLUSIVE",
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs" / "20260906_matter_formation_yukawa_bulk")
    parser.add_argument("--note-path", type=Path, default=REPORT)
    args = parser.parse_args()
    target = args.output_dir / "results.json"
    failures: list[str] = []
    identities: dict[str, Any] = {}
    result: dict[str, Any] = {}
    try:
        if target.exists():
            raise FileExistsError(f"refusing to overwrite receipt: {target}")
        identities = collect_identities(failures)
        validate_accepted_receipt(failures)
        if args.note_path.resolve() != REPORT.resolve():
            failures.append("note path does not match frozen working record")
        if not args.note_path.is_file():
            failures.append("missing working note")
        result = base_result(identities, failures)
        if not failures:
            mp.mp.dps = PRECISION_DPS
            result["algebraic_checks"] = algebraic_checks()
            result["pressure_rows"] = pressure_rows()
            result["remainder_rows"] = remainder_rows()
            result["grand_rows"] = grand_rows()
            failed_exact = [item["name"] for item in result["algebraic_checks"] if not item["pass"]]
            failed_rows = [f"pressure:{i}" for i, item in enumerate(result["pressure_rows"]) if not item["pass"]]
            failed_rows += [f"remainder:{i}" for i, item in enumerate(result["remainder_rows"]) if not item["pass"]]
            failed_rows += [f"grand:{i}" for i, item in enumerate(result["grand_rows"]) if not item["pass"]]
            failures.extend(failed_exact + failed_rows)
            result["failures"] = failures
            result["numerical_pass"] = not failures and len(result["algebraic_checks"]) == 12 and len(result["pressure_rows"]) == 6 and len(result["remainder_rows"]) == 10 and len(result["grand_rows"]) == 18
            if result["numerical_pass"]:
                result["verdict"] = VERDICT
    except Exception as exc:
        if not result:
            result = base_result(identities, failures)
        failures.append(f"{type(exc).__name__}: {exc}")
        result["failures"] = failures
        result["numerical_pass"] = False
        result["verdict"] = "INCONCLUSIVE"
    write_json_exclusive(target, result)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if result["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
