#!/usr/bin/env python3
"""Independent verifier for the conditional carrier-parent vacuum calculation.

The verifier reconstructs every frozen scalar, finite-vector, Gaussian, and
homogeneous minimizer witness without importing the primary computation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.integrate import quad
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH = ROOT / "computations" / "matter-formation-parent-vacuum-prereg.md"
PRIMARY_PATH = ROOT / "computations" / "matter_formation_parent_vacuum.py"
VERIFIER_PATH = ROOT / "computations" / "verify_matter_formation_parent_vacuum.py"
DEFAULT_INPUT_DIR = ROOT / "runs" / "20260906_matter_formation_parent_vacuum"

SCHEMA = "cassi.matter-formation.parent-vacuum.v1"
VERIFY_SCHEMA = "cassi.matter-formation.parent-vacuum.verification.v1"
COEFFICIENTS = {
    "u_rho": 4.0,
    "u_C": 1.0,
    "k_Cx": 1.0,
    "e_C": 0.75,
    "h_C": 2.9598260763447164,
}
S_VALUES = (0.0, 0.25, 0.5, 1.0, 2.0)
N_VALUES = (0.0, 0.5, 1.0, 3.0, 8.0)
Z_GRID = (0.0, 0.25, 1.0, 2.0)
N_GRID = (0.0, 0.25, math.sqrt(2.0), 4.0, 8.0)
CHARGE_TARGETS = (-2.0, 0.0, 3.0)
LAMBDAS = (0.5, 0.75, 1.0, 1.25, 1.5)
ALG_TOL = 1.0e-11
MIN_TOL = 1.0e-8
GAUSS_TOL = 1.0e-8
PROJECTED_GRADIENT_TOL = 1.0e-7

ROW_KEYS = {
    "index", "a", "B", "depletion", "minimum_value", "mass2_depleted",
    "factorization_max_scaled_residual", "charge_witnesses", "gaussian",
}
CHARGE_KEYS = {
    "target_charge", "transverse", "norm", "measured_charge", "original_energy",
    "canonical_energy", "shift_scaled_residual", "kinetic_energy", "kinetic_bound",
    "kinetic_excess", "transverse_energy", "kinetic_scaled_residual",
    "charge_scaled_residual",
}
GAUSSIAN_KEYS = {"gradient", "potential", "energies"}
ENERGY_KEYS = {"lambda", "energy"}


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def byte_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value))


def finite_tree(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(k, str) and finite_tree(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_tree(v) for v in value)
    if isinstance(value, bool) or isinstance(value, str) or value is None:
        return True
    return finite_number(value)


def json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def close(actual: Any, expected: float, tolerance: float) -> bool:
    return finite_number(actual) and abs(float(actual) - expected) <= tolerance * max(1.0, abs(expected))


def mismatch(failures: list[str], path: str, expected: Any, actual: Any, reason: str) -> None:
    failures.append(f"{path}: {reason}; expected={json_safe(expected)!r}; actual={json_safe(actual)!r}")


def expected_identities() -> dict[str, dict[str, str]]:
    return {
        "primary": {"path": "computations/matter_formation_parent_vacuum.py", "sha256": canonical_sha256(PRIMARY_PATH)},
        "verifier": {"path": "computations/verify_matter_formation_parent_vacuum.py", "sha256": canonical_sha256(VERIFIER_PATH)},
        "preregistration": {"path": "computations/matter-formation-parent-vacuum-prereg.md", "sha256": canonical_sha256(PREREG_PATH)},
    }


def expected_thresholds() -> dict[str, float]:
    s = math.sqrt(COEFFICIENTS["u_rho"] * COEFFICIENTS["u_C"] / 2.0)
    return {
        "s": s,
        "a_depleted": 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"])),
        "a_vacuum": 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"] - s)),
    }


def schedule() -> tuple[float, ...]:
    avac = expected_thresholds()["a_vacuum"]
    return (1.0 / 64.0, 1.0 / 32.0, 1.0 / 16.0, 1.0 / 8.0, 1.0 / 4.0, 0.9 * avac, avac, 1.1 * avac, 0.5, 1.0)


def potential(z: float, n: float, a: float) -> float:
    B = COEFFICIENTS["e_C"] + 1.0 / (4.0 * a)
    return (COEFFICIENTS["u_rho"] / 4.0) * (z - 1.0) ** 2 + (B - COEFFICIENTS["h_C"] * (1.0 - z)) * n + COEFFICIENTS["u_C"] * n * n / 2.0


def potential_gradient(x: np.ndarray, a: float) -> np.ndarray:
    z, n = float(x[0]), float(x[1])
    B = COEFFICIENTS["e_C"] + 1.0 / (4.0 * a)
    return np.array((COEFFICIENTS["u_rho"] / 2.0 * (z - 1.0) + COEFFICIENTS["h_C"] * n,
                     B - COEFFICIENTS["h_C"] * (1.0 - z) + COEFFICIENTS["u_C"] * n), dtype=float)


def projected_gradient(x: np.ndarray, a: float) -> float:
    g = potential_gradient(x, a)
    projected = []
    for value, grad, lower, upper in zip(x, g, (0.0, 0.0), (2.0, 8.0)):
        if value <= lower and grad > 0.0:
            projected.append(0.0)
        elif value >= upper and grad < 0.0:
            projected.append(0.0)
        else:
            projected.append(float(grad))
    return float(np.max(np.abs(projected)))


def predicted_minimum(a: float) -> tuple[float, float, float]:
    B = COEFFICIENTS["e_C"] + 1.0 / (4.0 * a)
    depletion = COEFFICIENTS["h_C"] - B
    n = max(depletion, 0.0) / COEFFICIENTS["u_C"]
    value = min(0.0, COEFFICIENTS["u_rho"] / 4.0 - max(depletion, 0.0) ** 2 / (2.0 * COEFFICIENTS["u_C"]))
    return float(value), float(depletion), float(n)


def independent_minimization(a: float) -> dict[str, Any]:
    predicted, depletion, n_boundary = predicted_minimum(a)
    endpoints: list[dict[str, Any]] = []
    for z0 in S_VALUES:
        for n0 in N_VALUES:
            start = [float(z0), float(n0)]
            try:
                result = minimize(
                    lambda x: potential(float(x[0]), float(x[1]), a),
                    np.asarray(start, dtype=float),
                    jac=lambda x: potential_gradient(np.asarray(x, dtype=float), a),
                    method="L-BFGS-B",
                    bounds=((0.0, 2.0), (0.0, 8.0)),
                    options={"ftol": 1.0e-14, "gtol": 1.0e-10, "maxiter": 2000, "maxls": 40},
                )
                endpoint = np.asarray(result.x, dtype=float)
                endpoints.append({
                    "start": start,
                    "endpoint": endpoint.tolist(),
                    "energy": float(result.fun),
                    "success": bool(result.success),
                    "message": str(result.message),
                    "projected_gradient_inf_norm": projected_gradient(endpoint, a),
                })
            except Exception as exc:
                endpoints.append({
                    "start": start, "endpoint": None, "energy": None, "success": False,
                    "message": f"exception: {exc}", "projected_gradient_inf_norm": None,
                })
    boundaries = [
        {"name": "exterior_vacuum", "point": [1.0, 0.0], "energy": potential(1.0, 0.0, a)},
        {"name": "depleted_boundary", "point": [0.0, n_boundary], "energy": potential(0.0, n_boundary, a)},
    ]
    qualifying = [
        x for x in endpoints
        if x["success"]
        and finite_number(x["energy"])
        and close(x["energy"], predicted, MIN_TOL)
    ]
    failures = [
        x for x in endpoints
        if not x["success"] and (
            not finite_number(x["projected_gradient_inf_norm"])
            or x["projected_gradient_inf_norm"] > PROJECTED_GRADIENT_TOL
        )
    ]
    return {
        "predicted_minimum": predicted,
        "depletion": depletion,
        "boundary_evaluations": boundaries,
        "endpoints": endpoints,
        "best_endpoint": min((x for x in endpoints if finite_number(x["energy"])), key=lambda x: x["energy"], default=None),
        "optimizer_attains_predicted": bool(qualifying),
        "optimizer_failures": failures,
    }


def factorization_residual(a: float) -> float:
    s = math.sqrt(COEFFICIENTS["u_rho"] * COEFFICIENTS["u_C"] / 2.0)
    B = COEFFICIENTS["e_C"] + 1.0 / (4.0 * a)
    maximum = 0.0
    for z in Z_GRID:
        for n in N_GRID:
            lhs = potential(z, n, a)
            rhs = (math.sqrt(COEFFICIENTS["u_rho"]) / 2.0 * (1.0 - z) - math.sqrt(COEFFICIENTS["u_C"] / 2.0) * n) ** 2 + (B - (COEFFICIENTS["h_C"] - s) * (1.0 - z)) * n
            maximum = max(maximum, abs(lhs - rhs) / max(1.0, abs(lhs), abs(rhs)))
    return maximum


def vector_witness(a: float, target: float, transverse: bool) -> dict[str, Any]:
    chi = np.asarray((1.0 + 0.5j, -0.25 + 0.75j, 0.4 - 0.3j), dtype=complex)
    weights = np.asarray((1.0, 0.7, 1.3), dtype=float)
    f = np.asarray((0.2, 0.8, 1.1), dtype=float)
    eta0 = np.asarray((-0.2 + 0.1j, 0.3 - 0.4j, 0.7 + 0.2j), dtype=complex)
    norm = float(np.dot(weights, np.abs(chi) ** 2))
    inner0 = np.dot(weights, np.conjugate(chi) * eta0)
    eta = eta0 - 1j * float(np.imag(inner0) / norm) * chi if transverse else np.zeros(3, dtype=complex)
    kappa = (norm - target) / (2.0 * a * norm)
    dot_chi = 1j * kappa * chi + eta
    measured = norm - 2.0 * a * float(np.imag(np.dot(weights, np.conjugate(chi) * dot_chi)))
    local = (COEFFICIENTS["u_rho"] / 4.0) * (f * f - 1.0) ** 2 + (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)) * np.abs(chi) ** 2 + COEFFICIENTS["u_C"] / 2.0 * np.abs(chi) ** 4
    local_energy = float(np.dot(weights, local))
    kinetic = float(a * np.dot(weights, np.abs(dot_chi) ** 2))
    original = kinetic + local_energy
    canonical = float(a * np.dot(weights, np.abs(dot_chi - 1j * chi / (2.0 * a)) ** 2) + local_energy + np.dot(weights, np.abs(chi) ** 2) / (4.0 * a))
    bound = (norm - target) ** 2 / (4.0 * a * norm)
    excess = kinetic - bound
    transverse_energy = float(a * np.dot(weights, np.abs(eta) ** 2))
    shift = canonical - original - target / (2.0 * a)
    return {
        "target_charge": float(target), "transverse": bool(transverse), "norm": norm,
        "measured_charge": measured, "original_energy": original, "canonical_energy": canonical,
        "shift_scaled_residual": abs(shift) / max(1.0, abs(canonical - original), abs(target / (2.0 * a))),
        "kinetic_energy": kinetic, "kinetic_bound": bound, "kinetic_excess": excess,
        "transverse_energy": transverse_energy,
        "kinetic_scaled_residual": abs(excess - transverse_energy) / max(1.0, abs(excess), abs(transverse_energy)),
        "charge_scaled_residual": abs(measured - target) / max(1.0, abs(measured), abs(target)),
    }


def gaussian_density(r: float, lam: float, a: float) -> tuple[float, float]:
    f = 1.0 - 0.5 * math.exp(-r * r / (2.0 * lam * lam))
    c = math.exp(-r * r / (8.0 * lam * lam))
    df = 0.5 * r / (lam * lam) * math.exp(-r * r / (2.0 * lam * lam))
    dc = -r / (4.0 * lam * lam) * math.exp(-r * r / (8.0 * lam * lam))
    gradient = 0.5 * (df * df + COEFFICIENTS["k_Cx"] * dc * dc)
    B = COEFFICIENTS["e_C"] + 1.0 / (4.0 * a)
    potential_density = COEFFICIENTS["u_rho"] / 4.0 * (f * f - 1.0) ** 2 + (B - COEFFICIENTS["h_C"] * (1.0 - f * f)) * c * c + COEFFICIENTS["u_C"] / 2.0 * c ** 4
    return gradient, potential_density


def radial_integral(lam: float, a: float) -> dict[str, float]:
    grad, grad_error = quad(lambda r: r * r * gaussian_density(r, lam, a)[0], 0.0, math.inf, epsabs=1.0e-10, epsrel=1.0e-10, limit=300)
    pot, pot_error = quad(lambda r: r * r * gaussian_density(r, lam, a)[1], 0.0, math.inf, epsabs=1.0e-10, epsrel=1.0e-10, limit=300)
    angular = 4.0 * math.pi
    return {
        "lambda": lam, "gradient": angular * grad, "potential": angular * pot,
        "energy": angular * (grad + pot), "gradient_error": angular * grad_error,
        "potential_error": angular * pot_error,
    }


def gaussian_witness(a: float) -> dict[str, Any]:
    raw = [radial_integral(lam, a) for lam in LAMBDAS]
    base = raw[LAMBDAS.index(1.0)]
    return {
        "gradient": base["gradient"], "potential": base["potential"],
        "energies": [{"lambda": row["lambda"], "energy": row["energy"]} for row in raw],
        "direct": raw,
        "scaling": [{"lambda": lam, "energy": lam * base["gradient"] + lam ** 3 * base["potential"]} for lam in LAMBDAS],
    }


def compare_number(failures: list[str], path: str, actual: Any, expected: float, tolerance: float) -> bool:
    ok = close(actual, expected, tolerance)
    if not ok:
        mismatch(failures, path, expected, actual, "numeric comparison")
    return ok


def compare_witness(failures: list[str], path: str, reported: Any, expected: Mapping[str, Any]) -> bool:
    if not isinstance(reported, Mapping) or set(reported) != CHARGE_KEYS:
        mismatch(failures, path, sorted(CHARGE_KEYS), sorted(reported) if isinstance(reported, Mapping) else type(reported).__name__, "exact witness schema")
        return False
    ok = True
    for key in CHARGE_KEYS:
        if key == "transverse":
            if reported[key] is not expected[key]:
                mismatch(failures, f"{path}.{key}", expected[key], reported[key], "exact Boolean witness field")
                ok = False
        elif key == "target_charge":
            if not finite_number(reported[key]) or reported[key] != expected[key]:
                mismatch(failures, f"{path}.{key}", expected[key], reported[key], "exact signed-charge schedule")
                ok = False
        else:
            ok = compare_number(failures, f"{path}.{key}", reported[key], float(expected[key]), ALG_TOL) and ok
            if key.endswith("_scaled_residual"):
                if not finite_number(reported[key]) or not 0.0 <= reported[key] <= ALG_TOL:
                    mismatch(failures, f"{path}.{key}", f"0 <= residual <= {ALG_TOL}", reported[key], "reported algebraic criterion")
                    ok = False
                if not finite_number(expected[key]) or not 0.0 <= expected[key] <= ALG_TOL:
                    mismatch(failures, f"{path}.{key}", f"0 <= residual <= {ALG_TOL}", expected[key], "independent algebraic criterion")
                    ok = False
    return ok


def verify_primary(source: Any, input_path: Path, failures: list[str]) -> tuple[list[dict[str, Any]], bool]:
    if not isinstance(source, Mapping):
        mismatch(failures, "results", "object", type(source).__name__, "schema")
        return [], False
    expected_top = {"schema", "coefficients", "thresholds", "identities", "rows", "failures", "pass", "verdict"}
    if set(source) != expected_top:
        mismatch(failures, "results.keys", sorted(expected_top), sorted(source), "exact top-level schema")
    if source.get("schema") != SCHEMA:
        mismatch(failures, "schema", SCHEMA, source.get("schema"), "schema")
    coefficients = source.get("coefficients")
    if not isinstance(coefficients, Mapping) or set(coefficients) != set(COEFFICIENTS):
        mismatch(failures, "coefficients", COEFFICIENTS, coefficients, "exact coefficients schema")
    else:
        for key, value in COEFFICIENTS.items():
            if not finite_number(coefficients[key]) or coefficients[key] != value:
                mismatch(failures, f"coefficients.{key}", value, coefficients[key], "exact frozen coefficient")
    thresholds = source.get("thresholds")
    expected_thr = expected_thresholds()
    if not isinstance(thresholds, Mapping) or set(thresholds) != set(expected_thr):
        mismatch(failures, "thresholds", expected_thr, thresholds, "exact threshold schema")
    else:
        for key, value in expected_thr.items():
            compare_number(failures, f"thresholds.{key}", thresholds.get(key), value, ALG_TOL)
    identities = source.get("identities")
    expected_ids = expected_identities()
    if not isinstance(identities, Mapping) or set(identities) != set(expected_ids):
        mismatch(failures, "identities", expected_ids, identities, "exact identities schema")
    else:
        for key, expected in expected_ids.items():
            actual = identities.get(key)
            if not isinstance(actual, Mapping) or set(actual) != {"path", "sha256"}:
                mismatch(failures, f"identities.{key}", expected, actual, "identity schema")
            else:
                for field in ("path", "sha256"):
                    if actual.get(field) != expected[field]:
                        mismatch(failures, f"identities.{key}.{field}", expected[field], actual.get(field), "identity")
    if failures:
        return [], False
    rows = source.get("rows")
    if not isinstance(rows, list) or len(rows) != len(schedule()):
        mismatch(failures, "rows", len(schedule()), len(rows) if isinstance(rows, list) else type(rows).__name__, "exact schedule length")
        return [], False
    reconstructed: list[dict[str, Any]] = []
    for index, (reported, a) in enumerate(zip(rows, schedule())):
        label = f"rows[{index}]"
        if not isinstance(reported, Mapping) or set(reported) != ROW_KEYS:
            mismatch(failures, f"{label}.keys", sorted(ROW_KEYS), sorted(reported) if isinstance(reported, Mapping) else type(reported).__name__, "exact row schema")
            continue
        if type(reported["index"]) is not int or reported["index"] != index:
            mismatch(failures, f"{label}.index", index, reported["index"], "integer schedule order")
        if not finite_number(reported["a"]) or reported["a"] != a:
            mismatch(failures, f"{label}.a", a, reported["a"], "exact frozen coefficient schedule")
        B = COEFFICIENTS["e_C"] + 1.0 / (4.0 * a)
        predicted, depletion, _ = predicted_minimum(a)
        for key, expected in (("B", B), ("depletion", depletion), ("minimum_value", predicted), ("mass2_depleted", 1.0 / (4.0 * a * a) + (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"]) / a), ("factorization_max_scaled_residual", factorization_residual(a))):
            compare_number(failures, f"{label}.{key}", reported.get(key), expected, MIN_TOL if key in {"minimum_value"} else ALG_TOL)
        for origin, residual in (("reported", reported["factorization_max_scaled_residual"]), ("independent", factorization_residual(a))):
            if not finite_number(residual) or not 0.0 <= residual <= ALG_TOL:
                mismatch(failures, f"{label}.factorization.{origin}", f"0 <= residual <= {ALG_TOL}", residual, "algebraic criterion")
        expected_witnesses = [vector_witness(a, target, transverse) for target in CHARGE_TARGETS for transverse in (False, True)]
        actual_witnesses = reported.get("charge_witnesses")
        if not isinstance(actual_witnesses, list) or len(actual_witnesses) != 6:
            mismatch(failures, f"{label}.charge_witnesses", 6, len(actual_witnesses) if isinstance(actual_witnesses, list) else type(actual_witnesses).__name__, "exact witness count")
        else:
            for wi, (actual, expected) in enumerate(zip(actual_witnesses, expected_witnesses)):
                compare_witness(failures, f"{label}.charge_witnesses[{wi}]", actual, expected)
        actual_gaussian = reported.get("gaussian")
        expected_gaussian = gaussian_witness(a)
        if not isinstance(actual_gaussian, Mapping) or set(actual_gaussian) != GAUSSIAN_KEYS:
            mismatch(failures, f"{label}.gaussian", sorted(GAUSSIAN_KEYS), actual_gaussian, "exact Gaussian schema")
        else:
            compare_number(failures, f"{label}.gaussian.gradient", actual_gaussian.get("gradient"), expected_gaussian["gradient"], GAUSS_TOL)
            compare_number(failures, f"{label}.gaussian.potential", actual_gaussian.get("potential"), expected_gaussian["potential"], GAUSS_TOL)
            energies = actual_gaussian.get("energies")
            if not isinstance(energies, list) or len(energies) != len(LAMBDAS):
                mismatch(failures, f"{label}.gaussian.energies", len(LAMBDAS), len(energies) if isinstance(energies, list) else type(energies).__name__, "exact energy schedule")
            else:
                for ei, (actual_energy, expected_energy) in enumerate(zip(energies, expected_gaussian["energies"])):
                    if not isinstance(actual_energy, Mapping) or set(actual_energy) != ENERGY_KEYS:
                        mismatch(failures, f"{label}.gaussian.energies[{ei}]", sorted(ENERGY_KEYS), actual_energy, "exact energy schema")
                    else:
                        if not finite_number(actual_energy.get("lambda")) or actual_energy["lambda"] != expected_energy["lambda"]:
                            mismatch(failures, f"{label}.gaussian.energies[{ei}].lambda", expected_energy["lambda"], actual_energy.get("lambda"), "energy order")
                        compare_number(failures, f"{label}.gaussian.energies[{ei}].energy", actual_energy.get("energy"), expected_energy["energy"], GAUSS_TOL)
        reconstructed.append({"index": index, "a": a, "reported": reported, "minimizer": independent_minimization(a), "charge_witnesses": expected_witnesses, "gaussian": expected_gaussian})
    primary_failures = source.get("failures")
    if not isinstance(primary_failures, list) or not all(isinstance(x, str) for x in primary_failures):
        mismatch(failures, "failures", "list[str]", primary_failures, "failure list schema")
    elif source.get("pass") is True and primary_failures:
        mismatch(failures, "failures", [], primary_failures, "passing primary must have no failures")
    elif source.get("pass") is False and not primary_failures:
        mismatch(failures, "failures", "non-empty list", primary_failures, "failed primary must report failures")
    if source.get("pass") is not True or source.get("verdict") != "PASS":
        mismatch(failures, "reported_verdict", {"pass": True, "verdict": "PASS"}, {"pass": source.get("pass"), "verdict": source.get("verdict")}, "primary did not pass")
    if not finite_tree(source):
        mismatch(failures, "results", "finite JSON values", "non-finite", "finite field requirement")
    return reconstructed, True


def write_receipt(path: Path, payload: Mapping[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(json_safe(dict(payload)), indent=2, sort_keys=True, allow_nan=False) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(data)
    except FileExistsError:
        return False
    return True


def verify(input_dir: Path, output_dir: Path) -> int:
    failures: list[str] = []
    output_path = output_dir / "verification.json"
    if output_path.exists():
        print(f"Refusing to overwrite receipt: {output_path}", file=sys.stderr)
        return 1
    result_path = input_dir / "results.json"
    raw_hash = byte_sha256(result_path) if result_path.exists() else ""
    source: Any = None
    if not result_path.exists():
        mismatch(failures, "results.json", "existing receipt", None, "missing input")
    else:
        try:
            source = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            mismatch(failures, "results.json", "valid JSON", str(exc), "input parse")
    identities = expected_identities()
    reconstructed: list[dict[str, Any]] = []
    if source is not None:
        reconstructed, _ = verify_primary(source, result_path, failures)
    rows: list[dict[str, Any]] = []
    for item in reconstructed:
        a = item["a"]
        minimizer = item["minimizer"]
        row_failures: list[str] = []
        if not minimizer["optimizer_attains_predicted"]:
            row_failures.append("no successful optimizer endpoint attains predicted minimum")
        if minimizer["optimizer_failures"]:
            row_failures.append("optimizer failure has projected gradient above qualification threshold")
        best = minimizer["best_endpoint"]
        if best is None or not close(best["energy"], minimizer["predicted_minimum"], MIN_TOL):
            row_failures.append("best numerical endpoint differs from the predicted global minimum")
        gaussian = item["gaussian"]
        scaling_checks = []
        for raw, scaled in zip(gaussian["direct"], gaussian["scaling"]):
            residual = (raw["energy"] - scaled["energy"]) / max(1.0, abs(raw["energy"]), abs(scaled["energy"]), abs(raw["gradient"]), abs(raw["potential"]))
            scaling_checks.append({"lambda": raw["lambda"], "direct": raw["energy"], "scaled": scaled["energy"], "scaled_residual": residual, "pass": abs(residual) <= GAUSS_TOL})
            if abs(residual) > GAUSS_TOL:
                row_failures.append(f"Gaussian scaling residual at lambda={raw['lambda']}")
        rows.append({
            "index": item["index"], "a": a,
            "independent": {"B": COEFFICIENTS["e_C"] + 1.0 / (4.0 * a), "depletion": predicted_minimum(a)[1], "minimum_value": predicted_minimum(a)[0], "mass2_depleted": 1.0 / (4.0 * a * a) + (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"]) / a, "factorization_max_scaled_residual": factorization_residual(a), "charge_witnesses": item["charge_witnesses"], "gaussian": gaussian},
            "minimizer": minimizer,
            "gaussian_scaling": scaling_checks,
            "failures": row_failures,
            "pass": not row_failures,
        })
    if len(rows) != len(schedule()):
        mismatch(failures, "independent.rows", len(schedule()), len(rows), "complete independent reconstruction")
    failures.extend(f"row[{row['index']}]: {failure}" for row in rows for failure in row["failures"])
    if not finite_tree(rows):
        failures.append("independent reconstruction contains non-finite numerical values")
    report = {
        "schema": VERIFY_SCHEMA,
        "input_sha256": raw_hash,
        "identities": identities,
        "rows": rows,
        "failures": failures,
        "pass": not failures and len(rows) == len(schedule()),
        "verdict": "PASS" if not failures and len(rows) == len(schedule()) else "FAIL",
        "physical_scope": {
            "verdict": "CONDITIONAL_ONLY",
            "physical_selection": False,
            "statement": (
                "Numerical PASS qualifies only the declared scalar identities; it does "
                "not select a physical coefficient or establish formation, localization, "
                "dynamical stability, or quantum stability."
            ),
        },
    }
    try:
        written = write_receipt(output_path, report)
    except Exception as exc:
        print(f"Cannot preserve verification receipt: {exc}", file=sys.stderr)
        return 1
    if not written:
        print(f"Refusing to overwrite receipt: {output_path}", file=sys.stderr)
        return 1
    print(json.dumps({"schema": VERIFY_SCHEMA, "output_dir": str(output_dir), "pass": report["pass"], "verdict": report["verdict"], "failure_count": len(failures)}, sort_keys=True))
    return 0 if report["pass"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    input_dir = args.input_dir.resolve()
    output_dir = (args.output_dir if args.output_dir is not None else input_dir).resolve()
    return verify(input_dir, output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
