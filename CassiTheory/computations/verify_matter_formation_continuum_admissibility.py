#!/usr/bin/env python3
"""Independent verifier for the frozen continuum admissibility protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()
PRIMARY_REL = "computations/matter_formation_continuum_admissibility.py"
PREREG_REL = "computations/matter-formation-continuum-admissibility-prereg.md"
FINITE_MODE_REL = "computations/matter-formation-fermion-production-prereg.md"
M0, Y, OMEGA, NU = 1.0, 0.25, 3.0, 0.75
MASSES = (0.5, 2.0)
DURATIONS = (0.25, 1.0, 3.0)
CUTOFFS = (32, 64, 128, 256, 512)
CHECK_NAMES = ("symbolic_identities", "row_contract", "finite_values", "positive_densities",
               "zero_controls", "excitation_count", "number_asymptotes", "energy_asymptotes",
               "vacuum_asymptotes", "static_remainders", "kinetic_primitive",
               "positive_kinetic_factors", "overlap_logarithm", "binding_integral", "binding_trace")
SYMBOLIC_NAMES = ("quench_leading", "quench_next", "vacuum_leading", "vacuum_next", "vacuum_taylor",
                  "static_reference_conditions", "kinetic_primitive", "overlap_leading",
                  "four_component_vacuum_trace", "four_component_excitation_partition")
OCC_KEYS = ("kind", "mass", "duration", "cutoff", "pair_density", "excitation_number_density",
            "excitation_energy_density", "predicted_number_coefficient", "predicted_energy_coefficient",
            "scaled_pair_density", "scaled_excitation_energy")
VAC_KEYS = ("mass", "cutoff", "reference_vacuum_density", "predicted_quadratic_coefficient",
            "scaled_reference_vacuum", "renormalized_static_density", "analytic_static_limit")
KIN_KEYS = ("cutoff", "kinetic_integral", "analytic_kinetic_integral", "z_factor", "overlap_energy_density")
SLOPE_KEYS = ("cutoff_low", "cutoff_high", "measured_log_coefficient", "predicted_log_coefficient")
BIND_KEYS = ("reference_mass", "reduced_mass", "yukawa_coupling", "scalar_mass", "alpha", "radial_integral",
             "analytic_radial_integral", "bargmann_bound", "all_partial_waves_excluded")


def gauss_legendre(n: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    xs, ws = [0.0] * n, [0.0] * n
    for i in range((n + 1) // 2):
        z = math.cos(math.pi * (i + 0.75) / (n + 0.5))
        for _ in range(80):
            p0, p1 = 1.0, z
            for k in range(2, n + 1):
                p0, p1 = p1, ((2.0 * k - 1.0) * z * p1 - (k - 1.0) * p0) / k
            dp = n * (z * p1 - p0) / (z * z - 1.0)
            dz = p1 / dp
            z -= dz
            if abs(dz) < 2e-16:
                break
        xs[i], xs[n - 1 - i] = -z, z
        ws[i] = ws[n - 1 - i] = 2.0 / ((1.0 - z * z) * dp * dp)
    return tuple(xs), tuple(ws)


GL8_X, GL8_W = gauss_legendre(8)
GL32_X, GL32_W = gauss_legendre(32)
RADIAL_CACHE: dict[int, tuple[tuple[float, ...], tuple[float, ...]]] = {}


def radial_grid(cutoff: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if cutoff not in RADIAL_CACHE:
        xs: list[float] = []
        ws: list[float] = []
        for block in range(int(math.ceil(cutoff / 0.25))):
            left, right = block * 0.25, min(cutoff, (block + 1) * 0.25)
            half, mid = (right - left) / 2.0, (right + left) / 2.0
            xs.extend(mid + half * x for x in GL8_X)
            ws.extend(half * w for w in GL8_W)
        RADIAL_CACHE[cutoff] = tuple(xs), tuple(ws)
    return RADIAL_CACHE[cutoff]


def integrate_radial(cutoff: int, fn: Callable[[float], float]) -> float:
    xs, ws = radial_grid(cutoff)
    return math.fsum(w * fn(x) for x, w in zip(xs, ws))


def integrate_s(fn: Callable[[float], float]) -> float:
    return math.fsum(0.5 * w * fn(0.5 * (x + 1.0)) for x, w in zip(GL32_X, GL32_W))


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if finite_number(value):
        return True
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(finite_tree(item) for item in value.values())
    return False


def approx(a: float, b: float) -> bool:
    return abs(a - b) <= 5e-9 + 2e-9 * abs(b)


def rel_ok(a: float, b: float, fraction: float) -> bool:
    return abs(a - b) <= fraction * abs(b)


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), ROOT).replace(os.sep, "/")


def identities(prereg_path: Path) -> dict[str, dict[str, str]]:
    paths = {"primary": ROOT / PRIMARY_REL, "verifier": SELF_PATH, "prereg": prereg_path,
             "finite_mode_prereg": ROOT / FINITE_MODE_REL}
    return {key: {"path": identity_path(path), "sha256": canonical_sha256(path) if path.is_file() else ""}
            for key, path in paths.items()}


def qocc(p: float, mass: float) -> float:
    return math.sin(0.5 * math.atan2(p * (mass - M0), p * p + M0 * mass)) ** 2


def pocc(p: float, mass: float, duration: float) -> float:
    d = mass - M0
    e0, e1 = math.sqrt(p * p + M0 * M0), math.sqrt(p * p + mass * mass)
    return p * p * d * d / (e0 * e0 * e1 * e1) * math.sin(e1 * duration) ** 2


def oocc(p: float) -> float:
    e0 = math.sqrt(p * p + M0 * M0)
    return math.sin(0.5 * math.atan(p * NU / (2.0 * e0 ** 3))) ** 2


def occupation_row(kind: str, mass: float, duration: float, cutoff: int) -> dict[str, Any]:
    d = mass - M0
    occ = (lambda p: qocc(p, mass)) if kind == "quench" else (lambda p: pocc(p, mass, duration))
    eout = (lambda p: math.sqrt(p * p + mass * mass)) if kind == "quench" else (lambda p: math.sqrt(p * p + M0 * M0))
    predicted = d * d / (4.0 * math.pi ** 2) if kind == "quench" else d * d / (2.0 * math.pi ** 2)
    measure = 1.0 / (2.0 * math.pi ** 2)
    pair = 2.0 * measure * integrate_radial(cutoff, lambda p: p * p * occ(p))
    energy = 4.0 * measure * integrate_radial(cutoff, lambda p: p * p * eout(p) * occ(p))
    return {"kind": kind, "mass": float(mass), "duration": float(duration), "cutoff": int(cutoff),
            "pair_density": float(pair), "excitation_number_density": float(2.0 * pair),
            "excitation_energy_density": float(energy), "predicted_number_coefficient": float(predicted),
            "predicted_energy_coefficient": float(predicted), "scaled_pair_density": float(pair / cutoff),
            "scaled_excitation_energy": float(energy / (cutoff * cutoff))}


def vacuum_integrand(p: float, mass: float, remainder: bool = False) -> float:
    d = mass - M0
    if d == 0.0:
        return 0.0
    if not remainder:
        return -2.0 * d * d * integrate_s(lambda s: (1.0 - s) * p * p /
            (p * p + (M0 + s * d) ** 2) ** 1.5)
    return -1.25 * d ** 5 * integrate_s(lambda s: (1.0 - s) ** 4 * p * p * (M0 + s * d) *
        (3.0 * p * p - 4.0 * (M0 + s * d) ** 2) /
        (p * p + (M0 + s * d) ** 2) ** 4.5)


def static_limit(mass: float) -> float:
    d = mass - M0
    q = mass ** 4 * math.log(mass * mass / (M0 * M0)) - 2.0 * M0 ** 3 * d - 7.0 * M0 ** 2 * d ** 2
    q -= (26.0 / 3.0) * M0 * d ** 3 + (25.0 / 6.0) * d ** 4
    return -q / (16.0 * math.pi ** 2)


def vacuum_row(mass: float, cutoff: int) -> dict[str, Any]:
    measure = 1.0 / (2.0 * math.pi ** 2)
    ref = measure * integrate_radial(cutoff, lambda p: p * p * vacuum_integrand(p, mass))
    rem = measure * integrate_radial(cutoff, lambda p: p * p * vacuum_integrand(p, mass, True))
    pred = -(mass - M0) ** 2 / (4.0 * math.pi ** 2)
    return {"mass": float(mass), "cutoff": int(cutoff), "reference_vacuum_density": float(ref),
            "predicted_quadratic_coefficient": float(pred), "scaled_reference_vacuum": float(ref / cutoff ** 2),
            "renormalized_static_density": float(rem), "analytic_static_limit": float(static_limit(mass))}


def kinetic_row(cutoff: int) -> dict[str, Any]:
    measure = 1.0 / (2.0 * math.pi ** 2)
    val = measure * integrate_radial(cutoff, lambda p: p ** 4 / (p * p + M0 * M0) ** 2.5)
    u = cutoff / math.sqrt(cutoff * cutoff + M0 * M0)
    analytic = (math.asinh(cutoff / M0) - u - u ** 3 / 3.0) / (2.0 * math.pi ** 2)
    overlap = 4.0 * measure * integrate_radial(cutoff, lambda p: p * p * math.sqrt(p * p + M0 * M0) * oocc(p))
    return {"cutoff": int(cutoff), "kinetic_integral": float(val), "analytic_kinetic_integral": float(analytic),
            "z_factor": float(1.0 - Y * Y * val / 2.0), "overlap_energy_density": float(overlap)}


def binding() -> dict[str, Any]:
    reduced, alpha, analytic = M0 / 2.0, Y * Y / (4.0 * math.pi), Y * Y / (4.0 * math.pi * OMEGA)
    finite = integrate_radial(32, lambda x: math.exp(-x))
    radial = alpha / OMEGA * (finite + math.exp(-32.0))
    bound = 2.0 * reduced * radial
    return {"reference_mass": float(M0), "reduced_mass": float(reduced), "yukawa_coupling": float(Y),
            "scalar_mass": float(OMEGA), "alpha": float(alpha), "radial_integral": float(radial),
            "analytic_radial_integral": float(analytic), "bargmann_bound": float(bound),
            "all_partial_waves_excluded": bool(bound < 1.0)}


def symbolic_checks() -> list[dict[str, Any]]:
    out = {name: False for name in SYMBOLIC_NAMES}
    try:
        import sympy as sp
        p, m, m0, m1, nu, lam, s = sp.symbols("p m m0 m1 nu lam s", positive=True)
        e0, e1 = sp.sqrt(p ** 2 + m0 ** 2), sp.sqrt(p ** 2 + m1 ** 2)
        d, nq = m1 - m0, sp.Rational(1, 2) * (1 - (p ** 2 + m0 * m1) / (e0 * e1))
        qtarget = -(3 * (m0 ** 4 + m1 ** 4) + 2 * m0 ** 2 * m1 ** 2 - 4 * m0 * m1 * (m0 ** 2 + m1 ** 2)) / 16
        out["quench_leading"] = sp.simplify(sp.limit(p ** 2 * nq, p, sp.oo) - d ** 2 / 4) == 0
        out["quench_next"] = sp.simplify(sp.limit(p ** 4 * (nq - d ** 2 / (4 * p ** 2)), p, sp.oo) - qtarget) == 0
        vv = 2 * ((p ** 2 + m * m0) / e0 - sp.sqrt(p ** 2 + m ** 2))
        out["vacuum_leading"] = sp.simplify(sp.limit(p * vv, p, sp.oo) + (m - m0) ** 2) == 0
        coeff = sp.Rational(3, 2) * m0 ** 2 * (m - m0) ** 2 + m0 * (m - m0) ** 3 + (m - m0) ** 4 / 4
        out["vacuum_next"] = sp.simplify(sp.limit(p ** 3 * (vv + (m - m0) ** 2 / p), p, sp.oo) - coeff) == 0
        ms = m0 + s * (m1 - m0)
        vs = 2 * ((p ** 2 + ms * m0) / e0 - sp.sqrt(p ** 2 + ms ** 2))
        supplied = -sp.Rational(5, 4) * (m1 - m0) ** 5 * p ** 2 * ms * (3 * p ** 2 - 4 * ms ** 2) / (p ** 2 + ms ** 2) ** sp.Rational(9, 2)
        out["vacuum_taylor"] = sp.simplify(sp.diff(vs, s, 5) / 24 - supplied) == 0
        dm = m - m0
        vr = -(m ** 4 * sp.log(m ** 2 / m0 ** 2) - 2 * m0 ** 3 * dm
               - 7 * m0 ** 2 * dm ** 2 - sp.Rational(26, 3) * m0 * dm ** 3
               - sp.Rational(25, 6) * dm ** 4) / (16 * sp.pi ** 2)
        out["static_reference_conditions"] = all(
            sp.simplify(sp.diff(vr, m, k).subs(m, m0)) == 0 for k in range(5))
        u = lam / sp.sqrt(lam ** 2 + m0 ** 2)
        primitive = (sp.asinh(lam / m0) - u - u ** 3 / 3) / (2 * sp.pi ** 2)
        out["kinetic_primitive"] = sp.simplify(sp.diff(primitive, lam) - lam ** 4 / (lam ** 2 + m0 ** 2) ** sp.Rational(5, 2) / (2 * sp.pi ** 2)) == 0
        b = p * nu / (2 * e0 ** 3)
        out["overlap_leading"] = sp.simplify(sp.limit(p ** 4 * sp.Rational(1, 2) * (1 - 1 / sp.sqrt(1 + b ** 2)), p, sp.oo) - nu ** 2 / 16) == 0
        h, ident = sp.Matrix([[m, p], [p, -m]]), sp.eye(2)
        ee = sp.sqrt(p ** 2 + m ** 2)
        pm, pp = (ident - h / ee) / 2, (ident + h / ee) / 2
        h0 = sp.Matrix([[m0, p], [p, -m0]])
        c0 = (ident - h0 / e0) / 2
        h4, c04 = sp.diag(h, h), sp.diag(c0, c0)
        pm4, pp4 = sp.diag(pm, pm), sp.diag(pp, pp)
        out["four_component_vacuum_trace"] = sp.simplify(
            sp.trace(h4 * (pm4 - c04)) - vv) == 0
        covariance = sp.Matrix(4, 4, sp.symbols("c0:16"))
        covariance[3, 3] = 2 - sum(covariance[i, i] for i in range(3))
        nplus = sp.trace(pp4 * covariance) / 2
        nminus = sp.trace(pm4 * (sp.eye(4) - covariance)) / 2
        out["four_component_excitation_partition"] = (
            sp.simplify(nplus - nminus) == 0
            and sp.simplify(sp.trace(h4 * (covariance - c04)) - vv - 4 * ee * nplus) == 0)
    except Exception:
        pass
    return [{"name": name, "pass": bool(out[name])} for name in SYMBOLIC_NAMES]


def science() -> dict[str, Any]:
    occ = [occupation_row("quench", m, 0.0, c) for m in MASSES for c in CUTOFFS]
    occ += [occupation_row("pulse", m, t, c) for m in MASSES for t in DURATIONS for c in CUTOFFS]
    occ += [occupation_row("quench", M0, 0.0, 512), occupation_row("pulse", M0, 1.0, 512)]
    vac = [vacuum_row(m, c) for m in MASSES for c in CUTOFFS]
    kin = [kinetic_row(c) for c in CUTOFFS]
    by_cut = {row["cutoff"]: row["overlap_energy_density"] for row in kin}
    pred = NU * NU / (8.0 * math.pi ** 2)
    slopes = [{"cutoff_low": int(a), "cutoff_high": int(b),
               "measured_log_coefficient": float((by_cut[b] - by_cut[a]) / math.log(2.0)),
               "predicted_log_coefficient": float(pred)} for a, b in zip(CUTOFFS[:-1], CUTOFFS[1:])]
    return {"occupation_rows": occ, "vacuum_rows": vac, "kinetic_rows": kin, "overlap_slopes": slopes,
            "binding": binding(), "symbolic_checks": symbolic_checks()}


def validate_contract(actual: Any, expected: Any, path: str = "receipt") -> list[str]:
    if isinstance(expected, dict):
        if not isinstance(actual, dict): return [f"{path}: expected object"]
        errors = [] if set(actual) == set(expected) else [f"{path}: key set mismatch"]
        for key, value in expected.items():
            errors += [f"{path}.{key}: missing"] if key not in actual else validate_contract(actual[key], value, f"{path}.{key}")
        return errors
    if isinstance(expected, list):
        if not isinstance(actual, list): return [f"{path}: expected array"]
        errors = [] if len(actual) == len(expected) else [f"{path}: length {len(actual)} != {len(expected)}"]
        for i, value in enumerate(expected):
            if i < len(actual): errors += validate_contract(actual[i], value, f"{path}[{i}]")
        return errors
    if isinstance(expected, bool): return [] if isinstance(actual, bool) else [f"{path}: expected boolean"]
    if type(expected) is int: return [] if type(actual) is int else [f"{path}: expected integer"]
    if isinstance(expected, float): return [] if finite_number(actual) else [f"{path}: expected finite number"]
    if isinstance(expected, str): return [] if isinstance(actual, str) else [f"{path}: expected string"]
    return []


def compare(primary: Any, independent: Any, path: str, out: list[dict[str, Any]]) -> None:
    if isinstance(independent, dict):
        if not isinstance(primary, dict):
            out.append({"path": path, "primary": primary, "independent": independent, "pass": False}); return
        if set(primary) != set(independent):
            out.append({"path": path + ".<keys>", "primary": sorted(primary), "independent": sorted(independent), "pass": False})
        for key, value in independent.items():
            compare(primary[key], value, f"{path}.{key}", out) if key in primary else out.append({"path": f"{path}.{key}", "primary": None, "independent": value, "pass": False})
    elif isinstance(independent, list):
        if not isinstance(primary, list):
            out.append({"path": path, "primary": primary, "independent": independent, "pass": False}); return
        if len(primary) != len(independent): out.append({"path": path + ".<length>", "primary": len(primary), "independent": len(independent), "pass": False})
        for i, value in enumerate(independent):
            if i < len(primary): compare(primary[i], value, f"{path}[{i}]", out)
    elif isinstance(independent, bool):
        out.append({"path": path, "primary": primary, "independent": independent, "pass": isinstance(primary, bool) and primary == independent})
    elif finite_number(independent):
        out.append({"path": path, "primary": primary, "independent": independent, "pass": finite_number(primary) and approx(float(primary), float(independent))})
    else:
        out.append({"path": path, "primary": primary, "independent": independent, "pass": primary == independent})


def qualify(sc: dict[str, Any], sym: list[dict[str, Any]], contract: bool, primary_sym: bool) -> tuple[list[dict[str, Any]], list[str], bool]:
    occ, vac, kin, slopes, bind = sc["occupation_rows"], sc["vacuum_rows"], sc["kinetic_rows"], sc["overlap_slopes"], sc["binding"]
    vals = [all(x["pass"] for x in sym) and primary_sym,
            len(occ) == 42 and len(vac) == 10 and len(kin) == 5 and len(slopes) == 4 and contract,
            finite_tree(sc),
            all(r["pair_density"] > 0 and r["excitation_number_density"] > 0 and r["excitation_energy_density"] > 0 for r in occ[:-2]),
            all(abs(occ[i][k]) <= 5e-12 for i in (40, 41) for k in ("pair_density", "excitation_number_density", "excitation_energy_density", "scaled_pair_density", "scaled_excitation_energy")),
            all(approx(r["excitation_number_density"], 2 * r["pair_density"]) for r in occ),
            all(rel_ok(r["scaled_pair_density"], r["predicted_number_coefficient"], .03) for r in occ[:40] if r["cutoff"] == 512),
            all(rel_ok(r["scaled_excitation_energy"], r["predicted_energy_coefficient"], .03) for r in occ[:40] if r["cutoff"] == 512),
            all(rel_ok(r["scaled_reference_vacuum"], r["predicted_quadratic_coefficient"], .002) for r in vac if r["cutoff"] == 512),
            all(abs(r["renormalized_static_density"] - r["analytic_static_limit"]) <= 2e-6 for r in vac if r["cutoff"] == 512),
            all(approx(r["kinetic_integral"], r["analytic_kinetic_integral"]) for r in kin),
            all(r["z_factor"] > 0 for r in kin),
            bool(slopes) and rel_ok(slopes[-1]["measured_log_coefficient"], slopes[-1]["predicted_log_coefficient"], .002),
            approx(bind["radial_integral"], bind["analytic_radial_integral"]),
            approx(bind["bargmann_bound"], 2 * bind["reduced_mass"] * bind["radial_integral"])
            and bind["all_partial_waves_excluded"] is (bind["bargmann_bound"] < 1.0)]
    checks = [{"name": name, "pass": bool(ok)} for name, ok in zip(CHECK_NAMES, vals)]
    failures = [f"qualification failed: {name}" for name, ok in zip(CHECK_NAMES, vals) if not ok]
    return checks, failures, all(vals)


def verdicts(ok: bool, bound: float) -> dict[str, str]:
    if not ok: return {k: "INCONCLUSIVE" for k in ("sudden_source_continuum", "static_subtraction", "initial_overlap", "two_body_binding")}
    return {"sudden_source_continuum": "CONTRADICTS—ultraviolet-finite sudden-source continuum completion",
            "static_subtraction": "SUPPORTS—specified static one-loop subtraction identities",
            "initial_overlap": "SUPPORTS—logarithmic initial adiabatic overlap-energy mismatch",
            "two_body_binding": "SUPPORTS—absence of two-body binding in the stated nonrelativistic Yukawa reduction" if bound < 1 else "INCONCLUSIVE"}


def empty(ids: dict[str, dict[str, str]], input_hash: str, failures: list[str]) -> dict[str, Any]:
    return {"schema": "cassi-continuum-admissibility-verification-v1", "identities": ids,
            "occupation_rows": [], "vacuum_rows": [], "kinetic_rows": [], "overlap_slopes": [], "binding": {}, "symbolic_checks": [], "checks": [], "verdicts": {}, "numerical_pass": False, "failures": failures, "input_sha256": input_hash, "independent_checks": {"comparison_count": 0, "mismatch_paths": [], "comparisons": []}}


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    if path.exists(): raise FileExistsError(f"refusing to overwrite existing target: {path}")
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False); f.write("\n")


def run(args: argparse.Namespace) -> int:
    outdir, prereg = Path(args.output_dir).resolve(), Path(args.prereg).resolve() if args.prereg else ROOT / PREREG_REL
    outdir.mkdir(parents=True, exist_ok=True); target = outdir / "verification.json"
    ids, primary_path = identities(prereg), Path(args.input_dir).resolve() / "results.json"
    raw_hash = raw_sha256(primary_path) if primary_path.is_file() else ""
    if not prereg.is_file(): write_exclusive(target, empty(ids, raw_hash, [f"required-input failure: missing preregistration {prereg}"])); return 1
    if not primary_path.is_file(): write_exclusive(target, empty(ids, "", [f"required-input failure: missing primary results {primary_path}"])); return 1
    if any(not item["sha256"] for item in ids.values()):
        write_exclusive(target, empty(ids, raw_hash, ["required-input failure: missing source identity"])); return 1
    try:
        with primary_path.open("r", encoding="utf-8") as f:
            primary = json.load(f)
        if not finite_tree(primary):
            raise ValueError("primary receipt contains a nonfinite or unsupported value")
    except Exception as exc:
        write_exclusive(target, empty(ids, raw_hash, [f"input failure: {type(exc).__name__}: {exc}"])); return 1
    try:
        sc = science(); sym = sc["symbolic_checks"]
        shape = {"schema": "cassi-continuum-admissibility-v1", "identities": ids, **sc,
                 "checks": [{"name": n, "pass": True} for n in CHECK_NAMES],
                 "verdicts": {n: "" for n in ("sudden_source_continuum", "static_subtraction", "initial_overlap", "two_body_binding")}, "numerical_pass": False}
        actual_shape = {k: v for k, v in primary.items() if k != "failures"} if isinstance(primary, dict) else primary
        shape_errors = validate_contract(actual_shape, shape)
        if not isinstance(primary, dict) or not isinstance(primary.get("failures"), list) or any(not isinstance(x, str) for x in primary.get("failures", [])): shape_errors.append("receipt.failures: expected array of strings")
        if not isinstance(primary, dict) or primary.get("schema") != "cassi-continuum-admissibility-v1":
            shape_errors.append("receipt.schema: schema mismatch")
        primary_sym = isinstance(primary, dict) and isinstance(primary.get("symbolic_checks"), list) and len(primary["symbolic_checks"]) == len(sym) and all(isinstance(x, dict) and x.get("name") == sym[i]["name"] and isinstance(x.get("pass"), bool) and x["pass"] == sym[i]["pass"] for i, x in enumerate(primary["symbolic_checks"]))
        checks, failures, own_ok = qualify(sc, sym, not shape_errors, primary_sym)
        expected = {"schema": "cassi-continuum-admissibility-v1", "identities": ids, **sc, "checks": checks, "verdicts": verdicts(own_ok, sc["binding"]["bargmann_bound"]), "numerical_pass": own_ok, "failures": []}
        comparisons: list[dict[str, Any]] = []
        compare({k: v for k, v in primary.items() if k != "schema"} if isinstance(primary, dict) else primary,
                {k: v for k, v in expected.items() if k != "schema"}, "receipt", comparisons)
        mismatch_paths = [x["path"] for x in comparisons if not x["pass"]]
        failures += shape_errors
        if mismatch_paths: failures.append(f"independent comparison mismatches: {len(mismatch_paths)}")
        ok = own_ok and not shape_errors and not mismatch_paths
        receipt = {"schema": "cassi-continuum-admissibility-verification-v1", "identities": ids, **sc,
                   "checks": checks, "verdicts": verdicts(ok, sc["binding"]["bargmann_bound"]), "numerical_pass": bool(ok), "failures": failures,
                   "input_sha256": raw_hash, "independent_checks": {"comparison_count": len(comparisons), "mismatch_paths": mismatch_paths, "comparisons": comparisons}}
        if not finite_tree(receipt):
            raise ValueError("nonfinite independent evidence")
        write_exclusive(target, receipt); return 0 if ok else 1
    except Exception as exc:
        write_exclusive(target, empty(ids, raw_hash, [f"verification failure: {type(exc).__name__}: {exc}"])); return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--input-dir", required=True); parser.add_argument("--output-dir", required=True); parser.add_argument("--prereg")
    try: return run(parser.parse_args())
    except Exception as exc: print(f"verification failure: {type(exc).__name__}: {exc}"); return 1


if __name__ == "__main__": raise SystemExit(main())
