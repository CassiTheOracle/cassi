#!/usr/bin/env python3
"""Independent verifier for the frozen cascade-response calculation.

This program intentionally does not import the primary calculation.  It rebuilds
all algebra, spectra, and trajectories from the registered witness and compares
the resulting artifacts with the primary receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORD = ROOT / "computations" / "matter-formation-continuum-report.md"
SCHEMA = "matter-formation-cascade-response-verification-v1"
PRIMARY_SCHEMA = "matter-formation-cascade-response-v1"
VERDICT_SUPPORTS = "SUPPORTS-conditional cascade response"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"
HBAR = 1.0
KX = 1.0
KS = 1.0
RHO0 = 1.0
LAMBDA_RHO = 4.0
LAMBDA_PHI = 4.0
PHI = (1.0 + math.sqrt(5.0)) / 2.0
SIGMAS = np.array([0.0, 1.0 / 16.0, 1.0 / 4.0, 1.0, 4.0], dtype=np.float64)
TIMES = np.arange(129, dtype=np.float64) / 8.0
SECTION_HEADINGS = (
    "### 37.1 Causal exterior elimination and controlled frequency expansion",
    "### 37.2 Positive collective phase inertia in the first-order action",
    "### 37.3 The longitudinal connection changes the mode count",
    "### 37.4 Initial-state information carried by the exterior",
    "### 37.5 Cascade response qualification: pre-execution criteria",
)
SECTION_HASHES = (
    "4aae773136b8b1743244e981907c7478c92bc1f9a4f1716cadcd6f70d7889b71",
    "e62c9c2a3e94a47b13ddcbec6fc2200d047a706a07335cb0e945eb730647845d",
    "f2314f5bd9c173545e48a0d6598aee4b6159875a77091d171505bd014c49174c",
    "21434f2bffabed334c0115f00e3d77c5df41be5feff77989b8a87740d00c93c5",
    "26fb01595a1b4140c07ed1b808cb4ac957fdc7cdb19e5b54ee609e4273b180c8",
)
RTOL = 1.0e-12
ATOL = 1.0e-14


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, canonical: bool = False) -> str:
    return sha256_bytes(canonical_bytes(path) if canonical else path.read_bytes())


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def strict_json(path: Path) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate JSON key {key}")
            out[key] = value
        return out

    def constant(value: str) -> Any:
        raise ValueError(f"non-standard JSON constant {value}")

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def finite(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value))


def close(a: Any, b: Any, tol: float = 1.0e-10) -> bool:
    try:
        aa, bb = float(a), float(b)
    except (TypeError, ValueError):
        return False
    return math.isfinite(aa) and math.isfinite(bb) and abs(aa - bb) <= tol * max(1.0, abs(aa), abs(bb))


def frozen_sections(record: Path) -> list[str]:
    text = canonical_bytes(record).decode("utf-8")
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    for heading in SECTION_HEADINGS:
        target = heading + "\n"
        try:
            start = next(i for i, line in enumerate(lines) if line == target)
        except StopIteration as exc:
            raise ValueError(f"missing frozen heading {heading}") from exc
        level = len(heading) - len(heading.lstrip("#"))
        end = len(lines)
        pattern = re.compile(r"^(#{1,6})\s+")
        for i in range(start + 1, len(lines)):
            match = pattern.match(lines[i])
            if match and len(match.group(1)) <= level:
                end = i
                break
        result.append("".join(lines[start:end]).rstrip() + "\n")
    return result


def write_snapshot(path: Path, content: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def check(result: dict[str, Any], name: str, passed: bool, **details: Any) -> None:
    row = {"name": name, "passed": bool(passed)}
    row.update(details)
    result["checks"].append(row)


def array(loaded: Any, name: str, shape: tuple[int, ...], dtype: np.dtype[Any]) -> np.ndarray:
    if name not in loaded:
        raise ValueError(f"missing primary array {name}")
    value = np.asarray(loaded[name])
    if value.shape != shape or value.dtype != dtype or not np.all(np.isfinite(value)):
        raise ValueError(f"invalid primary array {name}: shape={value.shape}, dtype={value.dtype}")
    return value


def complex_array(loaded: Any, name: str, shape: tuple[int, ...]) -> np.ndarray:
    if name not in loaded:
        raise ValueError(f"missing primary array {name}")
    value = np.asarray(loaded[name])
    if value.shape != shape or value.dtype != np.dtype("complex128") or not np.all(np.isfinite(value.real)) or not np.all(np.isfinite(value.imag)):
        raise ValueError(f"invalid primary complex array {name}")
    return value


def hessian(sigma: float) -> np.ndarray:
    # Cartesian density Hessian of the registered quadratic potential.
    ey = PHI / (1.0 + PHI)
    ei = 1.0 / (1.0 + PHI)
    a = np.array([1.0, 1.0])
    b = np.array([1.0, -PHI])
    return LAMBDA_RHO / 2.0 * np.outer(a, a) + LAMBDA_PHI * np.outer(b, b) + sigma / 4.0 * np.diag([1.0 / ey, 1.0 / ei])


def phase_stiffness(sigma: float, varied: bool = False) -> np.ndarray:
    ey = PHI / (1.0 + PHI)
    ei = 1.0 / (1.0 + PHI)
    d = np.diag([ey, ei])
    if varied:
        r = np.array([1.0, -1.0])
        d = d - np.outer(d @ r, r @ d) / float(r @ d @ r)
    return sigma * d


def first_order_frequencies(sigma: float, varied: bool = False) -> np.ndarray:
    # Linear Cartesian real/imaginary amplitudes have Berry coefficient 2*hbar.
    root = np.diag(np.sqrt([PHI / (1.0 + PHI), 1.0 / (1.0 + PHI)]))
    inverse_root = np.diag(1.0 / np.diag(root))
    amplitude = 4.0 * root @ hessian(sigma) @ root
    phase = inverse_root @ phase_stiffness(sigma, varied) @ inverse_root
    generator = np.block([
        [np.zeros((2, 2)), phase / (2.0 * HBAR)],
        [-amplitude / (2.0 * HBAR), np.zeros((2, 2))],
    ])
    frequencies = np.sort(np.linalg.eigvals(generator).imag)
    # The exact characteristic identities establish the zero multiplicities.
    return frequencies[-1:] if varied else frequencies[-2:]




def symbolic_checks() -> tuple[list[dict[str, Any]], dict[str, float]]:
    s, lr, lp, rho, ph, hb = sp.symbols(
        "sigma lambda_rho lambda_phi rho phi hbar", positive=True
    )
    ey, ei = ph * rho / (1 + ph), rho / (1 + ph)
    n0, n1, u0, u1, v0, v1 = sp.symbols("n0 n1 u0 u1 v0 v1", real=True)
    aa, bb = sp.Matrix([1, 1]), sp.Matrix([1, -ph])
    potential = lr * (n0 + n1) ** 2 / 4 + lp * (n0 - ph * n1) ** 2 / 2 + s * (n0 ** 2 / ey + n1 ** 2 / ei) / 8
    hs = sp.hessian(potential, (n0, n1))
    declared = lr * (aa * aa.T) / 2 + lp * (bb * bb.T) + s * sp.diag(1 / ey, 1 / ei) / 4
    d = sp.diag(ey, ei)
    root = sp.diag(sp.sqrt(ey), sp.sqrt(ei))
    densities = [(sp.sqrt(ey) + u0) ** 2 + v0 ** 2, (sp.sqrt(ei) + u1) ** 2 + v1 ** 2]
    cartesian_energy = (
        lr * (sum(densities) - rho) ** 2 / 4
        + lp * (densities[0] - ph * densities[1]) ** 2 / 2
        + s * (u0 ** 2 + u1 ** 2 + v0 ** 2 + v1 ** 2) / 2
    )
    cartesian = sp.hessian(cartesian_energy, (u0, u1, v0, v1)).subs({u0: 0, u1: 0, v0: 0, v1: 0})
    cartesian_residual = cartesian - sp.diag(4 * root * declared * root, s * sp.eye(2))
    theta_dot = sp.Matrix(sp.symbols("theta0_dot theta1_dot", real=True))
    nvec = sp.Matrix([n0, n1])
    lagrangian = -hb * (nvec.T * theta_dot)[0] - potential
    equations = [sp.diff(lagrangian, variable) for variable in nvec]
    solution = sp.solve(equations, list(nvec), dict=True)[0]
    density_residual = sp.Matrix([solution[n0], solution[n1]]) + hb * hs.inv() * theta_dot
    action_residual = lagrangian.subs(solution) - hb ** 2 * (theta_dot.T * hs.inv() * theta_dot)[0] / 2
    r = sp.Matrix([1, -1])
    projected = sp.simplify(d - (d * r * r.T * d) / (r.T * d * r)[0])
    q = sp.symbols("q")
    fixed_char = sp.factor((hs * (s * d) - q * sp.eye(2)).det())
    varied_char = sp.factor((hs * (s * projected) - q * sp.eye(2)).det())
    density_sq = lr * rho * s / 2 + s ** 2 / 4
    relative_sq = lp * ph * rho * s + s ** 2 / 4
    long_sq = s * ey * ei / rho * (2 * lr + lp * (1 - ph) ** 2) + s ** 2 / 4
    residuals = {
        "density_hessian": hs - declared,
        "cartesian_hessian": cartesian_residual,
        "density_elimination": density_residual,
        "positive_reduced_action": sp.Matrix([action_residual]),
        "ratio_phi_orthogonality": aa.T * d * bb,
        "connection_projection": projected - ey * ei / rho * aa * aa.T,
        "fixed_characteristic_polynomial": sp.Matrix([fixed_char - (q - density_sq) * (q - relative_sq)]),
        "varied_characteristic_polynomial": sp.Matrix([varied_char - q * (q - long_sq)]),
        "zero_wave_number_characteristic": sp.Matrix([fixed_char.subs(s, 0) - q ** 2, varied_char.subs(s, 0) - q ** 2]),
    }
    checks = []
    for name, residual in residuals.items():
        simplified = residual.applyfunc(lambda value: sp.factor(sp.together(value)))
        checks.append({"name": name, "passed": all(value == 0 for value in simplified), "residual": str(simplified)})
    checks.append({
        "name": "varied_zero_multiplicity", "passed": sp.simplify(varied_char.subs(q, 0)) == 0
        and sp.simplify(sp.diff(varied_char, q).subs(q, 0) + long_sq) == 0,
        "polynomial": str(varied_char),
    })
    return checks, {"characteristic_degree": float(sp.Poly(fixed_char, q).degree())}

def exact_response() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    h = np.array([[1.0, 1.0], [1.0, 4.0]], dtype=np.float64)
    poles, vecs = np.linalg.eigh(h)
    residues = np.abs(vecs[0, :]) ** 2
    roots = np.array([-34.0 - 2.0 * math.sqrt(301.0), -34.0 + 2.0 * math.sqrt(301.0)])
    zeta = np.array([-1.0, -0.5, 0.5, 1.0])
    rem = np.array([z ** 3 / (64.0 * (4.0 - z)) for z in zeta])
    bound = np.array([abs(z) ** 3 / (256.0 * (1.0 - abs(z) / 4.0)) for z in zeta])
    return poles, residues, roots, np.column_stack((rem, bound))


def full_rhs(_t: float, state: np.ndarray) -> np.ndarray:
    x, y = state
    return np.array([-1j * (x + y), -1j * (x + 4.0 * y)])


def memory_rhs(t: float, state: np.ndarray) -> np.ndarray:
    x, aux = state
    return np.array([-1j * x - 1j * np.exp(-4j * t) - aux, x - 4j * aux], dtype=np.complex128)


def integrate() -> dict[str, np.ndarray]:
    controls = {
        "uncoupled": solve_ivp(
            lambda _t, z: -1j * np.array([z[0], 4.0 * z[1]]),
            (0.0, float(TIMES[-1])), np.array([0.0 + 0j, 1.0 + 0j]),
            method="DOP853", t_eval=TIMES, rtol=RTOL, atol=ATOL,
        ),
        "zero": solve_ivp(
            full_rhs, (0.0, float(TIMES[-1])), np.zeros(2, dtype=complex),
            method="DOP853", t_eval=TIMES, rtol=RTOL, atol=ATOL,
        ),
    }
    full = solve_ivp(full_rhs, (0.0, float(TIMES[-1])), np.array([0.0 + 0j, 1.0 + 0j]), method="DOP853", t_eval=TIMES, rtol=RTOL, atol=ATOL)
    mem = solve_ivp(memory_rhs, (0.0, float(TIMES[-1])), np.array([0.0 + 0j, 0.0 + 0j]), method="DOP853", t_eval=TIMES, rtol=RTOL, atol=ATOL)
    for solution in (full, mem, *controls.values()):
        if not solution.success or not np.array_equal(solution.t, TIMES):
            raise ValueError(f"DOP853 did not complete the sampling schedule: {solution.message}")
    return {
        "times": TIMES.copy(), "x": full.y[0], "y": full.y[1],
        "memory_x": mem.y[0], "memory_aux": mem.y[1],
        **{f"control_{part}_{name}": solution.y[index]
           for name, solution in controls.items() for index, part in enumerate(("x", "y"))},
    }


def covariance_initial() -> np.ndarray:
    return np.array([[1.0, 0.2 + 0.1j], [0.2 - 0.1j, 0.7]], dtype=np.complex128)

def covariance_transport() -> np.ndarray:
    gamma0 = covariance_initial()
    h = np.array([[1.0, 1.0], [1.0, 4.0]], dtype=np.complex128)
    eigenvalues, vec = np.linalg.eigh(h)
    result = np.empty((len(TIMES), 2, 2), dtype=np.complex128)
    for i, t in enumerate(TIMES):
        u = vec @ np.diag(np.exp(-1j * eigenvalues * t)) @ np.conjugate(vec.T)
        result[i] = u @ gamma0 @ np.conjugate(u.T)
    return result



def compare_numbers(result: dict[str, Any], primary: dict[str, Any], poles: np.ndarray, residues: np.ndarray, roots: np.ndarray, alpha_long: float) -> None:
    numbers = primary.get("numbers")
    if not isinstance(numbers, dict):
        raise ValueError("primary numbers missing")
    expected: dict[str, Any] = {"exact_poles": poles, "exact_residues": residues, "truncated_roots": roots, "alpha_long": alpha_long}
    independent: dict[str, Any] = {}
    for name, value in expected.items():
        stored = numbers.get(name)
        if name == "alpha_long":
            if not finite(stored):
                raise ValueError("primary alpha_long malformed")
            err = abs(float(stored) - float(value))
            independent[name] = float(value)
        else:
            if not isinstance(stored, list) or len(stored) != len(value):
                raise ValueError(f"primary number field {name} malformed")
            actual = np.asarray(stored, dtype=float)
            err = float(np.max(np.abs(actual - value)))
            independent[name] = value.tolist()
        check(result, f"number_{name}", err <= 1.0e-10, max_abs_error=float(err))
    # The covariance witness is source-declared and must be bound in the receipt.
    if "covariance_initial_real" in numbers or "covariance_initial_imag" in numbers:
        real = np.asarray(numbers.get("covariance_initial_real"), dtype=float)
        imag = np.asarray(numbers.get("covariance_initial_imag"), dtype=float)
        gamma0 = covariance_initial()
        err = float(max(np.max(np.abs(real - gamma0.real)), np.max(np.abs(imag - gamma0.imag))))
        check(result, "number_covariance_initial", real.shape == (2, 2) and imag.shape == (2, 2) and err <= 1.0e-15, max_abs_error=err)
    else:
        raise ValueError("primary covariance witness declaration missing")
    result["numbers"] = independent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, required=True, help="fresh primary output directory")
    parser.add_argument("--expected-primary-sha", required=True, help="expected raw SHA256 of primary results.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    result: dict[str, Any] = {
        "schema": SCHEMA, "passed": False, "verdict": VERDICT_INCONCLUSIVE,
        "complete_physical_matter_formation": False, "source_sha256": sha256_file(Path(__file__)),
        "section_hashes": {}, "array_sha256": "", "primary_sha256": "", "checks": [], "numbers": {}, "failures": [],
    }
    try:
        output.mkdir(parents=True, exist_ok=False)
        record = args.record.resolve()
        sections = frozen_sections(record)
        for i, section in enumerate(sections, 1):
            digest = sha256_bytes(section.encode("utf-8"))
            result["section_hashes"][f"section{i}"] = digest
            if digest != SECTION_HASHES[i - 1]:
                raise ValueError(f"frozen section{i} hash mismatch")
            write_snapshot(output / f"section{i}.txt", section)
        with (output / "program_source.py").open("xb") as stream:
            stream.write(Path(__file__).resolve().read_bytes())
        primary = args.primary.resolve()
        primary_file, primary_data_file = primary / "results.json", primary / "data.npz"
        if not primary_file.is_file() or not primary_data_file.is_file():
            raise ValueError("primary results.json or data.npz missing")
        result["primary_sha256"] = sha256_file(primary_file)
        if result["primary_sha256"].lower() != str(args.expected_primary_sha).lower():
            raise ValueError("primary results SHA256 does not match --expected-primary-sha")
        primary_receipt = strict_json(primary_file)
        if not isinstance(primary_receipt, dict) or primary_receipt.get("schema") != PRIMARY_SCHEMA:
            raise ValueError("primary schema mismatch")
        if primary_receipt.get("complete_physical_matter_formation") is not False:
            raise ValueError("primary physical-formation flag is not false")
        if primary_receipt.get("section_hashes") != result["section_hashes"]:
            raise ValueError("primary frozen section hashes mismatch")
        psource = primary / "program_source.py"
        if not psource.is_file() or not isinstance(primary_receipt.get("source_sha256"), str) or sha256_file(psource) != primary_receipt["source_sha256"]:
            raise ValueError("primary source snapshot missing or hash mismatch")
        for i, section in enumerate(sections, 1):
            pfile = primary / f"section{i}.txt"
            if not pfile.is_file() or canonical_bytes(pfile).decode("utf-8") != section:
                raise ValueError(f"primary section{i}.txt missing or altered")
        if sha256_file(primary_data_file) != primary_receipt.get("array_sha256"):
            raise ValueError("primary array SHA256 mismatch")
        with np.load(primary_data_file, allow_pickle=False) as raw:
            p = {
                "times": array(raw, "times", (129,), np.dtype("float64")),
                "x": complex_array(raw, "x", (129,)), "y": complex_array(raw, "y", (129,)),
                "memory_x": complex_array(raw, "memory_x", (129,)), "memory_aux": complex_array(raw, "memory_aux", (129,)),
                "norm": array(raw, "norm", (129,), np.dtype("float64")), "energy": array(raw, "energy", (129,), np.dtype("float64")),
                "covariance": complex_array(raw, "covariance", (129, 2, 2)), "covariance_initial": complex_array(raw, "covariance_initial", (2, 2)),
                "sigma": array(raw, "sigma", (5,), np.dtype("float64")), "omega_fixed": array(raw, "omega_fixed", (5, 2), np.dtype("float64")),
                "omega_long": array(raw, "omega_long", (5,), np.dtype("float64")), "scale_p": array(raw, "scale_p", (3,), np.dtype("float64")),
                "scale_gaps_fixed": array(raw, "scale_gaps_fixed", (3, 2), np.dtype("float64")),
                "scale_gaps_long": array(raw, "scale_gaps_long", (3,), np.dtype("float64")), "control_x_uncoupled": complex_array(raw, "control_x_uncoupled", (129,)),
                "control_x_zero": complex_array(raw, "control_x_zero", (129,)),
                "control_y_uncoupled": complex_array(raw, "control_y_uncoupled", (129,)),
                "control_y_zero": complex_array(raw, "control_y_zero", (129,)),
            }
        independent = integrate()
        covariance = covariance_transport()
        h = np.array([[1.0, 1.0], [1.0, 4.0]], dtype=np.complex128)
        norm = np.abs(independent["x"]) ** 2 + np.abs(independent["y"]) ** 2
        energy = np.real(np.conjugate(independent["x"]) * (independent["x"] + independent["y"]) + np.conjugate(independent["y"]) * (independent["x"] + 4.0 * independent["y"]))
        poles, residues, roots, remainder = exact_response()
        alpha_long = math.sqrt((PHI / (1.0 + PHI) * 1.0 / (1.0 + PHI)) * (2.0 * LAMBDA_RHO + LAMBDA_PHI * (1.0 - PHI) ** 2)) / HBAR
        compare_numbers(result, primary_receipt, poles, residues, roots, alpha_long)
        check(result, "criterion_1_witness", np.max(np.abs(p["times"] - TIMES)) <= 1e-15 and np.max(np.abs(p["sigma"] - SIGMAS)) <= 1e-15, max_time_error=float(np.max(np.abs(p["times"] - TIMES))), max_sigma_error=float(np.max(np.abs(p["sigma"] - SIGMAS))))
        symbolic, symbolic_meta = symbolic_checks()
        result["checks"].extend(symbolic)
        fixed = np.array([first_order_frequencies(s) for s in SIGMAS])
        longitudinal = np.array([first_order_frequencies(s, True)[0] for s in SIGMAS])
        fixed_formula = np.sqrt(np.column_stack((2.0 * SIGMAS + SIGMAS ** 2 / 4.0, 4.0 * PHI * SIGMAS + SIGMAS ** 2 / 4.0)))
        longitudinal_formula = np.sqrt(alpha_long ** 2 * SIGMAS + SIGMAS ** 2 / 4.0)
        fixed_error = float(max(np.max(np.abs(p["omega_fixed"] - fixed)), np.max(np.abs(fixed - fixed_formula))))
        long_error = float(max(np.max(np.abs(p["omega_long"] - longitudinal)), np.max(np.abs(longitudinal - longitudinal_formula))))
        check(result, "criterion_2_spectra", max(fixed_error, long_error) < 1e-10, max_fixed_error=fixed_error, max_long_error=long_error)
        scale_p = np.array([m * math.pi / 8.0 for m in range(3)])
        scale_fixed = np.array([first_order_frequencies(pv * pv) for pv in scale_p])
        scale_long = np.array([first_order_frequencies(pv * pv, True)[0] for pv in scale_p])
        zero_scale_fixed = np.array([first_order_frequencies(0.0 * pv ** 2) for pv in scale_p])
        zero_scale_long = np.array([first_order_frequencies(0.0 * pv ** 2, True)[0] for pv in scale_p])
        check(result, "criterion_3_scale_gaps",
              np.max(np.abs(p["scale_p"] - scale_p)) <= 1e-14
              and np.max(np.abs(p["scale_gaps_fixed"] - scale_fixed)) <= 1e-10
              and np.max(np.abs(p["scale_gaps_long"] - scale_long)) <= 1e-10
              and np.all(scale_fixed[0] == 0.0) and scale_long[0] == 0.0
              and np.all(scale_fixed[1:] > 0.0) and np.all(scale_long[1:] > 0.0)
              and np.all(zero_scale_fixed == 0.0) and np.all(zero_scale_long == 0.0),
              max_fixed_error=float(np.max(np.abs(p["scale_gaps_fixed"] - scale_fixed))),
              max_long_error=float(np.max(np.abs(p["scale_gaps_long"] - scale_long))))
        check(result, "criterion_4_exact_response",
              np.all(poles > 0.0) and np.all(residues > 0.0)
              and abs(float(np.sum(residues)) - 1.0) <= 1e-12
              and np.all(np.abs(remainder[:, 0]) <= remainder[:, 1] + 1e-12)
              and np.max(np.abs(roots ** 2 + 68.0 * roots - 48.0)) < 1e-10 and roots[0] < -4.0,
              remainder_max=float(np.max(np.abs(remainder[:, 0]) - remainder[:, 1])),
              negative_root=float(roots[0]))
        trajectory_error = max(float(np.max(np.abs(independent["x"] - p["x"]))), float(np.max(np.abs(independent["y"] - p["y"]))), float(np.max(np.abs(independent["memory_x"] - p["memory_x"]))), float(np.max(np.abs(independent["memory_aux"] - p["memory_aux"]))))
        memory_full_error = float(np.max(np.abs(independent["x"] - independent["memory_x"])))
        check(result, "criterion_5_dynamics", memory_full_error <= 1e-9 and trajectory_error <= 1e-9, full_primary_error=trajectory_error, memory_full_error=memory_full_error)
        recompute_norm_error = float(np.max(np.abs(norm - p["norm"])))
        recompute_energy_error = float(np.max(np.abs(energy - p["energy"])))
        covariance_error = float(np.max(np.abs(covariance - p["covariance"])))
        covariance_initial_error = float(np.max(np.abs(p["covariance_initial"] - covariance_initial())))
        conservation_norm = float(np.max(np.abs(norm - norm[0])))
        conservation_energy = float(np.max(np.abs(energy - energy[0])))
        check(result, "criterion_5_conservation_covariance", recompute_norm_error <= 1e-10 and recompute_energy_error <= 1e-10 and covariance_error <= 1e-10 and covariance_initial_error <= 1e-15 and conservation_norm <= 1e-10 and conservation_energy <= 1e-10, norm_reconstruction_error=recompute_norm_error, energy_reconstruction_error=recompute_energy_error, covariance_error=covariance_error, covariance_initial_error=covariance_initial_error, norm_drift=conservation_norm, energy_drift=conservation_energy)
        closed_population = 4.0 / 13.0 * np.sin(math.sqrt(13.0) * TIMES / 2.0) ** 2
        check(result, "criterion_5_closed_population", float(np.max(np.abs(np.abs(independent["x"]) ** 2 - closed_population))) <= 1e-10, max_population_error=float(np.max(np.abs(np.abs(independent["x"]) ** 2 - closed_population))))
        control_error = max(float(np.max(np.abs(p[name] - independent[name])))
                            for name in ("control_x_uncoupled", "control_x_zero", "control_y_uncoupled", "control_y_zero"))
        control_population = max(float(np.max(np.abs(independent[name]) ** 2))
                                 for name in ("control_x_uncoupled", "control_x_zero", "control_y_zero"))
        check(result, "criterion_6_controls", control_error <= 1e-9 and control_population <= 1e-12,
              maximum_amplitude_error=control_error, maximum_forbidden_population=control_population)
        primary_checks = primary_receipt.get("checks")
        primary_pass = bool(
            primary_receipt.get("passed") is True and primary_receipt.get("verdict") == VERDICT_SUPPORTS
            and "error" in primary_receipt and primary_receipt["error"] is None
            and isinstance(primary_checks, list) and primary_checks
            and all(isinstance(row, dict) and row.get("passed") is True for row in primary_checks)
        )
        check(result, "criterion_7_primary_aggregate", primary_pass, primary_passed=primary_receipt.get("passed"), primary_verdict=primary_receipt.get("verdict"))
        all_pass = bool(result["checks"]) and all(bool(row.get("passed")) for row in result["checks"])
        result["passed"] = all_pass
        result["verdict"] = VERDICT_SUPPORTS if all_pass else VERDICT_INCONCLUSIVE
        np.savez(output / "data.npz", **independent, norm=norm, energy=energy,
                 covariance=covariance, covariance_initial=covariance_initial(),
                 sigma=SIGMAS, omega_fixed=fixed, omega_long=longitudinal,
                 scale_p=scale_p, scale_gaps_fixed=scale_fixed, scale_gaps_long=scale_long,
                 scale_stiffness_zero_fixed=zero_scale_fixed, scale_stiffness_zero_long=zero_scale_long,
                 exact_poles=poles, exact_residues=residues, truncated_roots=roots, remainder=remainder)
        result["array_sha256"] = sha256_file(output / "data.npz")
    except Exception as exc:
        result["failures"].append(f"{type(exc).__name__}: {exc}")
        result["passed"] = False
        result["verdict"] = VERDICT_INCONCLUSIVE
    result["failures"] = list(dict.fromkeys(result["failures"]))
    with (output / "verification.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps({"passed": result["passed"], "verdict": result["verdict"], "failures": result["failures"]}, ensure_ascii=False, allow_nan=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
