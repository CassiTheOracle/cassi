#!/usr/bin/env python3
"""Independent, source-bound verifier for the continuum minimizer calculation.

This program intentionally does not import the primary implementation.  It verifies the
frozen report sections and primary receipt before independently reconstructing the trial
integrals and the variational identities.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

import mpmath as mp
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()
DEFAULT_RECORD = ROOT / "computations" / "matter-formation-continuum-report.md"
PRIMARY_REL = "computations/matter_formation_continuum_minimizer.py"
OUTPUT_NAME = "verification.json"
SCHEMA = "matter-formation-continuum-minimizer-verification-v1"

FROZEN = {
    "angular": ("### 36.1 Exact angular variational equations", "b0ab6d5fbae00699bc82b1cb2b31c6494d9a342b0ed9a3b0cd93e80038834f11"),
    "compactness": ("### 36.2 Continuum compactness and evolution obligations", "fef2d801ece9ac5511bddbdad4c2516487ba996552163e5c90696e1799819b61"),
    "trial": ("### 36.3 Explicit continuum binding trial", "a6ef6b749a7fddd5c4fe95c963c944bb3199587fa0ee6d3115104da6775cb551"),
    "protocol": ("### 36.4 Continuum qualification: pre-execution criteria", "170f95ab96f71659a41e6b65124ccc2bf784a22282ff3efda73b39fb9edc574d"),
    "parent": ("### 25.1 Exact carrier-free periodic background", "dce41f8119dd782a4d5593d93ad96a03fad6558bcd3711b8e729803e73e72e6a"),
}
NUMERIC_KEYS = ("N_star", "G_star", "P_star", "omega_trial", "A_star", "Q_trial", "R_256", "energy_per_charge_256")

# Frozen coefficients from report §35.2 and §36.3.
mp.mp.dps = 80
a = mp.mpf(1) / 16
c_psi = mp.mpf(1) / 8
u_rho = mp.mpf(4)
u_C = mp.mpf(1)
k_Cx = mp.mpf(1)
e_C = mp.mpf(3) / 4
h_C = mp.mpf("2.9598260763447164")
B = e_C + 1 / (4 * a)
delta = mp.mpf(1) / 4
Q_FIXED = mp.mpf(256)


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_section(text: str, heading: str) -> str:
    """Extract one unique Markdown heading section using the frozen LF convention."""
    lines = text.replace("\r\n", "\n").split("\n")
    hits = [i for i, line in enumerate(lines) if line == heading]
    if len(hits) != 1:
        raise ValueError(f"heading {heading!r} occurs {len(hits)} times")
    start = hits[0]
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        m = re.match(r"^(#+) ", lines[i])
        if m and len(m.group(1)) <= level:
            end = i
            break
    return "\n".join(lines[start:end]).rstrip() + "\n"


def frozen_sections(record: Path) -> tuple[dict[str, bytes], dict[str, str], list[str]]:
    errors: list[str] = []
    sections: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    try:
        text = record.read_text(encoding="utf-8")
    except Exception as exc:
        return {}, {}, [f"cannot read record: {type(exc).__name__}: {exc}"]
    for name, (heading, expected) in FROZEN.items():
        try:
            data = normalized_section(text, heading).encode("utf-8")
            actual = hashlib.sha256(data).hexdigest()
            sections[name] = data
            hashes[name] = actual
            if actual != expected:
                errors.append(f"frozen section hash mismatch {name}: {actual} != {expected}")
        except Exception as exc:
            errors.append(f"frozen section {name}: {type(exc).__name__}: {exc}")
    return sections, hashes, errors


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def finite_decimal(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        return bool(mp.isfinite(mp.mpf(value)))
    except Exception:
        return False


def empty_science() -> dict[str, Any]:
    return {
        "numbers": {},
        "precise": {},
        "expressions": {},
        "checks": [],
        "symbolic_checks": [],
        "comparisons": [],
        "disabled_coupling": {},
        "omega_infty": None,
        "trial_q256_bound": False,
    }


def receipt_base(*, verdict: str, failures: list[str], section_hashes: dict[str, str], primary_sha: str | None, source_sha: str) -> dict[str, Any]:
    science = empty_science()
    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "passed": False,
        "complete_physical_matter_formation": False,
        "hashes": section_hashes,
        "artifacts": {},
        "source_sha256": source_sha,
        "primary_sha256": primary_sha,
        "failures": failures,
        "error": None,
        "versions": {},
        **science,
    }


def retain_inputs(output: Path, sections: dict[str, bytes]) -> dict[str, str]:
    """Retain exact verifier source and every section recovered before a failure."""
    artifacts: dict[str, str] = {}
    source = SELF_PATH.read_bytes()
    source_path = output / "program_source.py"
    with source_path.open("xb") as stream:
        stream.write(source)
    artifacts[source_path.name] = hashlib.sha256(source).hexdigest()
    for name, data in sections.items():
        path = output / f"{name}.txt"
        with path.open("xb") as stream:
            stream.write(data)
        artifacts[path.name] = hashlib.sha256(data).hexdigest()
    return artifacts



def write_failure(output: Path, receipt: dict[str, Any], sections: dict[str, bytes]) -> int:
    if receipt.get("error") is None and receipt.get("failures"):
        receipt["error"] = "; ".join(str(item) for item in receipt["failures"])
    receipt["artifacts"] = retain_inputs(output, sections)
    write_exclusive(output / OUTPUT_NAME, receipt)
    return 1


def write_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing target: {path}")
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def library_versions() -> dict[str, str]:
    names = ("mpmath", "sympy")
    result = {"python": sys.version.split()[0]}
    for name in names:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "unknown"
    return result


def potential(f: mp.mpf, c: mp.mpf, *, h: mp.mpf = h_C) -> mp.mpf:
    return u_rho / 4 * (f * f - 1) ** 2 + (B - h + h * f * f) * c * c + u_C / 2 * c ** 4


def trial_fields(r: mp.mpf, *, h: mp.mpf = h_C) -> tuple[mp.mpf, mp.mpf, mp.mpf, mp.mpf]:
    """Return f,c,df/dr,dc/dr for the unit-radius actual piecewise trial."""
    n0 = mp.sqrt(u_rho / (2 * u_C))
    if r <= 1:
        return mp.mpf(0), mp.sqrt(n0), mp.mpf(0), mp.mpf(0)
    if r < 1 + delta:
        t = (r - 1) / delta
        return t, mp.sqrt(n0) * (1 - t), 1 / delta, -mp.sqrt(n0) / delta
    return mp.mpf(1), mp.mpf(0), mp.mpf(0), mp.mpf(0)


def integrate_trial(h: mp.mpf = h_C) -> tuple[mp.mpf, mp.mpf, mp.mpf]:
    """Independent >=50-digit composite mpmath quadrature of the trial fields."""
    mp.mp.dps = 80
    four_pi = 4 * mp.pi
    n = lambda r: trial_fields(r, h=h)[1] ** 2 * four_pi * r ** 2
    g = lambda r: (trial_fields(r, h=h)[2] ** 2 + k_Cx * trial_fields(r, h=h)[3] ** 2) * four_pi * r ** 2 / 2
    p = lambda r: potential(trial_fields(r, h=h)[0], trial_fields(r, h=h)[1], h=h) * four_pi * r ** 2
    cuts = [mp.mpf(0), mp.mpf(1), 1 + delta]
    return tuple(mp.quad(fn, cuts) for fn in (n, g, p))  # type: ignore[return-value]


def symbolic_checks() -> list[dict[str, Any]]:
    f, x, y = sp.symbols("f x y")
    aa, cc, kk, ur, uc, ec, hh = sp.symbols("a c_psi k_Cx u_rho u_C e_C h_C", positive=True)
    bb = ec + 1 / (4 * aa)
    vv = ur / 4 * (f ** 2 - 1) ** 2 + (bb - hh + hh * f ** 2) * (x ** 2 + y ** 2) + uc / 2 * (x ** 2 + y ** 2) ** 2
    H = sp.hessian(vv, (f, x, y))
    expected = sp.Matrix([[ur * (3 * f ** 2 - 1) + 2 * hh * (x ** 2 + y ** 2), 4 * hh * f * x, 4 * hh * f * y], [4 * hh * f * x, 2 * (bb - hh + hh * f ** 2 + uc * (3 * x ** 2 + y ** 2)), 4 * uc * x * y], [4 * hh * f * y, 4 * uc * x * y, 2 * (bb - hh + hh * f ** 2 + uc * (x ** 2 + 3 * y ** 2))]])
    phase = sp.Matrix([0, -y, x])
    gradient = sp.Matrix([sp.diff(vv, q) for q in (f, x, y)])
    vf, vx, vy = sp.symbols("v_f v_x v_y", real=True)
    kinetic = cc * vf**2 / 2 + aa * (vx**2 + vy**2)
    mass = sp.hessian(kinetic, (vf, vx, vy))
    checks = [
        ("potential_hessian", sp.simplify(H - expected) == sp.zeros(3)),
        ("angular_mass_factors", sp.simplify(mass.inv() * H - sp.diag(1/cc, 1/(2*aa), 1/(2*aa)) * expected) == sp.zeros(3)),
        ("phase_symmetry_variation", sp.simplify(H * phase - sp.Matrix([0, -gradient[2], gradient[1]])) == sp.zeros(3, 1)),
    ]
    # Translation is the differentiated radial Euler equation.  Build the
    # radial l=0 and l=1 operators and compare the differentiated equations
    # with the angular Hessian action.
    r = sp.symbols("r", positive=True)
    F = sp.Function("F")(r)
    X = sp.Function("X")(r)
    Y = sp.Function("Y")(r)
    field_subs = {f: F, x: X, y: Y}
    fields = (F, X, Y)
    dfields = tuple(sp.diff(value, r) for value in fields)
    lap0 = lambda value: sp.diff(value, r, 2) + 2 * sp.diff(value, r) / r
    lap1 = lambda value: sp.diff(value, r, 2) + 2 * sp.diff(value, r) / r - 2 * value / r ** 2
    gradients = [sp.diff(vv, q).subs(field_subs) for q in (f, x, y)]
    equations = [lap0(F) - gradients[0], kk * lap0(X) - gradients[1], kk * lap0(Y) - gradients[2]]
    radial_derivative = [sp.diff(equation, r) for equation in equations]
    angular_action = [
        lap1(dfields[0]) - sum(H[0, j].subs(field_subs) * dfields[j] for j in range(3)),
        kk * lap1(dfields[1]) - sum(H[1, j].subs(field_subs) * dfields[j] for j in range(3)),
        kk * lap1(dfields[2]) - sum(H[2, j].subs(field_subs) * dfields[j] for j in range(3)),
    ]
    checks.append(("translation_symmetry_variation", all(sp.simplify(lhs - rhs) == 0 for lhs, rhs in zip(radial_derivative, angular_action))))
    q, n_sym, qdot = sp.symbols("Q N qdot", positive=True)
    checks.append(("velocity_square", sp.expand(aa * n_sym * (qdot + q / (2 * aa * n_sym)) ** 2 - (aa * n_sym * qdot ** 2 + q * q / (4 * aa * n_sym) + qdot * q)) == 0))
    s, G, P, K = sp.symbols("s G P K", positive=True)
    changed_charge = s**sp.Rational(1, 3) * G + s * P + (s*q)**2 / (4*aa*s*n_sym)
    dilation_target = s*(G + P + q*q/(4*aa*n_sym)) - (s-s**sp.Rational(1, 3))*G
    checks.append(("changed_charge_dilation", sp.simplify(changed_charge-dilation_target) == 0))
    scaled = s * G + s ** 3 * P + K / s ** 3
    virial = sp.simplify(sp.diff(scaled, s).subs(s, 1))
    checks.append(("spatial_dilation", sp.simplify(virial - (G + 3 * P - 3 * K)) == 0))
    omega, q_charge = sp.symbols("Omega Q", positive=True)
    energy_identity = sp.simplify(
        (G + P + K - (omega * q_charge + sp.Rational(2, 3) * G))
        .subs({omega * q_charge: 2 * K, P: K - G / 3})
    )
    checks.append(("virial_energy_identity", energy_identity == 0))
    # Disabled coupling has V >= B c^2 pointwise; its trial excess is nonnegative.
    checks.append(("disabled_coupling_lower_bound", sp.simplify(vv.subs(hh, 0) - bb * (x**2+y**2) - ur*(f*f-1)**2/4 - uc*(x*x+y*y)**2/2) == 0))
    return [{"name": name, "passed": bool(ok)} for name, ok in checks]

def mp_float(x: mp.mpf) -> float:
    value = float(x)
    if not math.isfinite(value):
        raise ValueError("non-finite numerical result")
    return value


def science_payload() -> tuple[dict[str, Any], list[str]]:
    mp.mp.dps = 80
    n_star, g_star, p_star = integrate_trial()
    omega = mp.sqrt(p_star / (a * n_star))
    A = g_star / (2 * mp.sqrt(a * p_star * n_star)) ** (mp.mpf(1) / 3)
    omega_inf = mp.sqrt(B / a)
    q_trial: mp.mpf | None = (A / (omega_inf - omega)) ** (mp.mpf(3) / 2) if omega < omega_inf else None
    r256 = (Q_FIXED / (2 * mp.sqrt(a * p_star * n_star))) ** (mp.mpf(1) / 3)
    e256_per_q = omega + A * Q_FIXED ** (-mp.mpf(2) / 3)
    numbers = {
        "N_star": mp_float(n_star),
        "G_star": mp_float(g_star),
        "P_star": mp_float(p_star),
        "omega_trial": mp_float(omega),
        "A_star": mp_float(A),
        "Q_trial": None if q_trial is None else mp_float(q_trial),
        "R_256": mp_float(r256),
        "energy_per_charge_256": mp_float(e256_per_q),
    }
    precise_values = {
        "N_star": n_star,
        "G_star": g_star,
        "P_star": p_star,
        "omega_trial": omega,
        "A_star": A,
        "Q_trial": q_trial,
        "R_256": r256,
        "energy_per_charge_256": e256_per_q,
    }
    precise = {key: (None if val is None else mp.nstr(val, 70)) for key, val in precise_values.items()}
    symbolic = symbolic_checks()
    failures = [f"symbolic check failed: {row['name']}" for row in symbolic if not row["passed"]]
    dn, dg, dp = integrate_trial(mp.mpf(0))
    disabled = {"potential_per_population": mp_float(dp / dn), "exterior_mass_coefficient": mp_float(B), "trial_binds": False}
    if dp / dn < B:
        failures.append("disabled-coupling lower bound failed")
    checks = [
        {"name": "all_symbolic_identities", "passed": not failures},
        {"name": "trial_frequency_below_exterior", "passed": omega < omega_inf, "actual": mp.nstr(omega, 30), "expected": f"< {mp.nstr(omega_inf, 30)}"},
        {"name": "disabled_coupling_P_over_N_ge_B", "passed": dp / dn >= B, "actual": mp.nstr(dp / dn, 30), "expected": mp.nstr(B, 30)},
    ]
    return {"numbers": numbers, "precise": precise, "checks": checks, "symbolic_checks": symbolic, "comparisons": [], "disabled_coupling": disabled, "omega_infty": mp_float(omega_inf), "trial_q256_bound": bool(e256_per_q < omega_inf)}, failures



def primary_receipt_path(directory: Path) -> Path:
    candidate = directory / "results.json"
    if not candidate.is_file():
        raise FileNotFoundError(f"missing primary receipt: {candidate}")
    return candidate


def validate_primary(doc: Any, section_hashes: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["primary receipt is not an object"]
    required = ("schema", "passed", "verdict", "numbers", "precise", "checks", "hashes", "artifacts", "trial_q256_bound", "omega_infty", "disabled_coupling", "error", "complete_physical_matter_formation")
    for key in required:
        if key not in doc:
            errors.append(f"primary missing field {key}")
    if doc.get("schema") != "matter-formation-continuum-minimizer-v1":
        errors.append("primary schema mismatch")
    if not isinstance(doc.get("verdict"), str):
        errors.append("primary verdict is not a string")
    if not isinstance(doc.get("passed"), bool) or not isinstance(doc.get("trial_q256_bound"), bool) or doc.get("complete_physical_matter_formation") is not False:
        errors.append("primary boolean contract mismatch")
    nums = doc.get("numbers")
    precise = doc.get("precise")
    if not isinstance(nums, dict) or set(nums) != set(NUMERIC_KEYS):
        errors.append("primary numeric key set mismatch")
    else:
        for key in NUMERIC_KEYS:
            if key == "Q_trial" and nums[key] is None:
                continue
            if not finite_number(nums[key]):
                errors.append(f"primary non-finite numeric field {key}")
    if not isinstance(precise, dict) or set(precise) != set(NUMERIC_KEYS):
        errors.append("primary precise key set mismatch")
    else:
        for key in NUMERIC_KEYS:
            if precise[key] is not None and not finite_decimal(precise[key]):
                errors.append(f"primary invalid precise field {key}")
            if precise[key] is None and nums.get(key) is not None:
                errors.append(f"primary precise null mismatch {key}")
            if key == "Q_trial" and nums.get(key) is None and precise[key] is not None:
                errors.append("primary Q_trial precise value must be null")
    checks = doc.get("checks")
    if not isinstance(checks, list):
        errors.append("primary checks is not a list")
    else:
        for row in checks:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not isinstance(row.get("passed"), bool):
                errors.append("primary malformed check row")
    if not isinstance(doc.get("hashes"), dict) or doc.get("hashes") != section_hashes:
        errors.append("primary frozen hashes mismatch")
    if not isinstance(doc.get("artifacts"), dict) or any(not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for k, v in doc.get("artifacts", {}).items()):
        errors.append("primary artifacts is not a SHA-256 mapping")
    if not finite_number(doc.get("omega_infty")):
        errors.append("primary omega_infty is not finite")
    dc = doc.get("disabled_coupling")
    if not isinstance(dc, dict) or not finite_number(dc.get("potential_per_population")) or not finite_number(dc.get("exterior_mass_coefficient")) or dc.get("trial_binds") is not False:
        errors.append("primary disabled-coupling contract mismatch")
    if doc.get("error") is not None and not isinstance(doc.get("error"), str):
        errors.append("primary error is not string/null")
    return errors


def compare_numbers(primary: dict[str, Any], independent: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in NUMERIC_KEYS:
        x, y = primary.get(key), independent.get(key)
        if x is None or y is None:
            rows.append({"name": key, "primary": x, "independent": y, "passed": x is None and y is None})
            continue
        scale = max(1.0, abs(float(x)), abs(float(y)))
        err = abs(float(x) - float(y))
        rows.append({"name": key, "primary": x, "independent": y, "absolute_error": err, "normalized_error": err / scale, "passed": err / scale <= 1e-10})
    return rows


def run(args: argparse.Namespace) -> int:
    output = Path(args.output_dir).resolve()
    target = output / OUTPUT_NAME
    source_sha = raw_sha256(SELF_PATH)
    output.mkdir(parents=True, exist_ok=False)
    sections, section_hashes, section_errors = frozen_sections(Path(args.record).resolve())
    receipt = receipt_base(verdict="INCONCLUSIVE", failures=section_errors[:], section_hashes=section_hashes, primary_sha=None, source_sha=source_sha)
    receipt["versions"] = library_versions()
    if section_errors:
        return write_failure(output, receipt, sections)
    expected = args.expected_primary_sha.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        receipt["failures"].append("expected primary SHA-256 is not 64 hexadecimal characters")
        return write_failure(output, receipt, sections)
    try:
        primary_path = primary_receipt_path(Path(args.primary).resolve())
        primary_sha = raw_sha256(primary_path)
        receipt["primary_sha256"] = primary_sha
        if primary_sha != expected:
            receipt["failures"].append(f"primary raw SHA-256 mismatch: {primary_sha} != {expected}")
            return write_failure(output, receipt, sections)
        primary_doc = json.loads(primary_path.read_text(encoding="utf-8"))
        schema_errors = validate_primary(primary_doc, section_hashes)
        if schema_errors:
            receipt["failures"].extend(schema_errors)
            return write_failure(output, receipt, sections)
        if primary_doc["passed"] is not True or primary_doc["verdict"] != "SUPPORTS-conditional continuum binding identities" or primary_doc["error"] is not None:
            receipt["failures"].append("primary scientific qualification did not pass")
            return write_failure(output, receipt, sections)
        science, calc_failures = science_payload()
        comparisons = compare_numbers(primary_doc["numbers"], science["numbers"])
        science["comparisons"] = comparisons
        calc_failures.extend(f"numeric mismatch: {row['name']}" for row in comparisons if not row["passed"])
        if primary_doc["trial_q256_bound"] != science["trial_q256_bound"]:
            calc_failures.append("primary charge-256 binding outcome disagrees")
        failed_primary_checks = [row.get("name", "unknown") for row in primary_doc["checks"] if row.get("passed") is not True]
        if failed_primary_checks:
            calc_failures.append("primary failed checks: " + ", ".join(failed_primary_checks))
        receipt.update(science)
        receipt["failures"].extend(calc_failures)
        receipt["passed"] = not calc_failures
        receipt["verdict"] = "SUPPORTS-conditional continuum binding identities" if receipt["passed"] else "INCONCLUSIVE"
        receipt["primary_sha256"] = primary_sha
        receipt["artifacts"] = retain_inputs(output, sections)
        write_exclusive(target, receipt)
        return 0 if receipt["passed"] else 1
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        receipt["failures"].append(f"verification failure: {type(exc).__name__}: {exc}")
        return write_failure(output, receipt, sections)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", required=True, help="directory containing the primary JSON receipt")
    parser.add_argument("--expected-primary-sha", required=True, help="expected raw SHA-256 of the primary receipt")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--record", default=str(DEFAULT_RECORD))
    try:
        return run(parser.parse_args())
    except Exception as exc:
        print(f"verification failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
