#!/usr/bin/env python3
"""Primary fixed quadratic cascade-response calculation for report §§37.1--37.5.

The executable is intentionally self-contained.  It binds the five frozen report
sections before evaluating the supplied dimensionless witness and retains all raw
arrays needed by the independent verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORD = ROOT / "computations/matter-formation-continuum-report.md"
SCHEMA = "matter-formation-cascade-response-v1"
VERDICT = "SUPPORTS-conditional cascade response"
INCONCLUSIVE = "INCONCLUSIVE"
FROZEN = (
    ("section1", "### 37.1 Causal exterior elimination and controlled frequency expansion", "4aae773136b8b1743244e981907c7478c92bc1f9a4f1716cadcd6f70d7889b71"),
    ("section2", "### 37.2 Positive collective phase inertia in the first-order action", "e62c9c2a3e94a47b13ddcbec6fc2200d047a706a07335cb0e945eb730647845d"),
    ("section3", "### 37.3 The longitudinal connection changes the mode count", "f2314f5bd9c173545e48a0d6598aee4b6159875a77091d171505bd014c49174c"),
    ("section4", "### 37.4 Initial-state information carried by the exterior", "21434f2bffabed334c0115f00e3d77c5df41be5feff77989b8a87740d00c93c5"),
    ("section5", "### 37.5 Cascade response qualification: pre-execution criteria", "26fb01595a1b4140c07ed1b808cb4ac957fdc7cdb19e5b54ee609e4273b180c8"),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_section(text: str, heading: str) -> bytes:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    hits = list(re.finditer(r"^" + re.escape(heading) + r"$", text, re.MULTILINE))
    if len(hits) != 1:
        raise ValueError(f"frozen heading is not unique: {heading}")
    start = hits[0].start()
    level = len(heading) - len(heading.lstrip("#"))
    tail = text[start:]
    boundary = re.search(r"\n#{1," + str(level) + r"} ", tail)
    if boundary is not None:
        tail = tail[: boundary.start()]
    return (tail.rstrip() + "\n").encode("utf-8")


def finite(value: Any) -> bool:
    try:
        return bool(np.isfinite(value)) and not isinstance(value, (complex, np.complexfloating))
    except (TypeError, ValueError):
        return False


def scalar(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def check(rows: list[dict[str, Any]], name: str, passed: bool, **details: Any) -> None:
    row: dict[str, Any] = {"name": name, "passed": bool(passed)}
    for key, value in details.items():
        if isinstance(value, (np.floating, np.integer)):
            value = value.item()
        if isinstance(value, float) and not math.isfinite(value):
            value = None
        row[key] = value
    rows.append(row)


def exact_algebra(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the source Hessian, eliminations, and exact characteristic identities."""
    n_y, n_i, rho, phi, lr, lp, sig, h, mu = sp.symbols(
        "n_Y n_I rho_0 phi lambda_rho lambda_phi sigma hbar mu", positive=True
    )
    e_y = phi * rho / (1 + phi)
    e_i = rho / (1 + phi)
    aa = sp.Matrix([1, 1])
    bb = sp.Matrix([1, -phi])
    rr = sp.Matrix([1, -1])
    density_energy = lr * (n_y + n_i) ** 2 / 4 + lp * (n_y - phi * n_i) ** 2 / 2
    gradient_energy = sig * (n_y**2 / e_y + n_i**2 / e_i) / 8
    density_hessian = sp.hessian(density_energy + gradient_energy, (n_y, n_i))
    D = sp.diag(e_y, e_i)
    W = lr * (aa * aa.T) / 2 + lp * (bb * bb.T) + sig * D.inv() / 4
    C = sig * D
    residual_hessian = sp.simplify(density_hessian - W)
    check(rows, "density_hessian", residual_hessian == sp.zeros(2), residual=str(residual_hessian))

    # Eliminate the density from the action, including its Berry-term sign.
    nvec = sp.Matrix(sp.symbols("nY nI"))
    thdot = sp.Matrix(sp.symbols("thetaYdot thetaIdot"))
    lagrangian = -h * (nvec.T * thdot)[0] - (nvec.T * W * nvec)[0] / 2
    stationary_n = -h * W.inv() * thdot
    substitution = dict(zip(nvec, stationary_n))
    stationary_residual = sp.simplify(
        sp.Matrix([sp.diff(lagrangian, n) for n in nvec]).subs(substitution)
    )
    reduced_residual = sp.simplify(
        lagrangian.subs(substitution) - h**2 * (thdot.T * W.inv() * thdot)[0] / 2
    )
    check(rows, "density_elimination", stationary_residual == sp.zeros(2, 1)
          and reduced_residual == 0, residual=str(reduced_residual),
          stationary_residual=str(stationary_residual))

    w_rho_sq = (lr * rho * sig / 2 + sig**2 / 4) / h**2
    w_eps_sq = (lp * phi * rho * sig + sig**2 / 4) / h**2
    G = sp.Matrix.vstack(
        sp.Matrix.hstack(sp.zeros(2), C / h),
        sp.Matrix.hstack(-W / h, sp.zeros(2)),
    )
    fixed_char = sp.factor((mu * sp.eye(4) - G).det())
    fixed_expected = sp.expand((mu**2 + w_rho_sq) * (mu**2 + w_eps_sq))
    fixed_residual = sp.factor(sp.together(fixed_char - fixed_expected))
    check(rows, "fixed_connection_characteristic", fixed_residual == 0, residual=str(fixed_residual))
    fixed_zero = sp.factor(fixed_expected.subs(sig, 0))
    check(rows, "fixed_connection_zero_multiplicity", fixed_zero == mu**4, polynomial=str(fixed_zero))
    # The branch formulas follow after imposing the exact ratio composition.
    ratio_sub = {rho: 1, phi: (1 + sp.sqrt(5)) / 2, lr: 4, lp: 4, h: 1}
    branch_values = [sp.simplify(v.subs(ratio_sub)) for v in (w_rho_sq, w_eps_sq)]
    check(rows, "fixed_connection_branches", all(v.is_real for v in branch_values), residual=str(branch_values))

    c = e_y * e_i / rho
    Ctilde = sp.simplify(sig * (D - D * rr * rr.T * D / (rr.T * D * rr)[0]))
    Cexpected = sp.simplify(sig * c * aa * aa.T)
    check(rows, "varied_connection_rank_one_projection", sp.simplify(Ctilde - Cexpected) == sp.zeros(2), residual=str(Ctilde - Cexpected))
    Gtilde = sp.Matrix.vstack(
        sp.Matrix.hstack(sp.zeros(2), Ctilde / h),
        sp.Matrix.hstack(-W / h, sp.zeros(2)),
    )
    long_sq = (sig * c * (2 * lr + lp * (1 - phi) ** 2) + sig**2 / 4) / h**2
    long_char = sp.factor((mu * sp.eye(4) - Gtilde).det())
    long_expected = sp.expand(mu**2 * (mu**2 + long_sq))
    long_residual = sp.factor(sp.together(long_char - long_expected))
    check(rows, "varied_connection_characteristic", long_residual == 0, residual=str(long_residual))
    zero_mult = sp.Poly(long_expected, mu).as_dict().get((2,), 0) != 0
    check(rows, "varied_connection_zero_multiplicity", zero_mult, polynomial=str(long_expected))
    return {
        "phi": (1 + math.sqrt(5.0)) / 2.0,
        "D": np.diag([float(e_y.subs(ratio_sub)), float(e_i.subs(ratio_sub))]),
        "branch_symbols": [str(v) for v in (w_rho_sq, w_eps_sq)],
        "long_symbol": str(long_sq),
    }


def schur_checks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    poles = np.sort(np.array([(5 - math.sqrt(13.0)) / 2.0, (5 + math.sqrt(13.0)) / 2.0]))
    residues = np.array([(p - 4.0) / (2.0 * p - 5.0) for p in poles])
    truncated = np.sort(np.array([-34.0 - 2.0 * math.sqrt(301.0), -34.0 + 2.0 * math.sqrt(301.0)]))
    check(rows, "schur_exact_poles", np.max(np.abs(np.polyval([1, -5, 3], poles))) < 1e-13, residual=scalar(np.max(np.abs(np.polyval([1, -5, 3], poles)))))
    check(rows, "schur_positive_residues", bool(np.all(residues > 0.0) and abs(float(np.sum(residues)) - 1.0) < 1e-13), residue_sum=scalar(np.sum(residues)), minimum_residue=scalar(np.min(residues)))
    check(rows, "schur_truncated_roots", np.max(np.abs(-0.75 + 17.0 * truncated / 16.0 + truncated**2 / 64.0)) < 1e-11, residual=scalar(np.max(np.abs(-0.75 + 17.0 * truncated / 16.0 + truncated**2 / 64.0))))
    check(rows, "schur_negative_root_outside_gap", bool(truncated[0] < -4.0), negative_root=scalar(truncated[0]))
    remainder_max = 0.0
    remainder_bound_error = 0.0
    for z in (-1.0, -0.5, 0.5, 1.0):
        exact_kernel = z - 1.0 + 1.0 / (4.0 - z)
        quadratic = -0.75 + 17.0 * z / 16.0 + z * z / 64.0
        rem = exact_kernel - quadratic
        bound = abs(z) ** 3 / (4.0**4 * (1.0 - abs(z) / 4.0))
        remainder_max = max(remainder_max, abs(rem))
        remainder_bound_error = max(remainder_bound_error, max(0.0, abs(rem) - bound))
    check(rows, "schur_remainder_bound", remainder_bound_error <= 1e-12, maximum_bound_excess=scalar(remainder_bound_error), maximum_remainder=scalar(remainder_max))
    return {"poles": poles, "residues": residues, "truncated": truncated}


def numerical_witness(rows: list[dict[str, Any]], phi: float) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    e_y = phi / (1.0 + phi)
    e_i = 1.0 / (1.0 + phi)
    D = np.diag([e_y, e_i])
    aa = np.ones(2)
    bb = np.array([1.0, -phi])
    density_potential = 2.0 * np.outer(aa, aa) + 4.0 * np.outer(bb, bb)
    density_gradient = np.diag([1.0 / e_y, 1.0 / e_i]) / 4.0
    constrained_phase = e_y * e_i * np.outer(aa, aa)

    def spectra(sigma: float) -> tuple[np.ndarray, float, np.ndarray]:
        W = density_potential + sigma * density_gradient
        C = sigma * D
        varied_C = sigma * constrained_phase
        generator = np.block([[np.zeros((2, 2)), C], [-W, np.zeros((2, 2))]])
        varied_generator = np.block([[np.zeros((2, 2)), varied_C], [-W, np.zeros((2, 2))]])
        # Zero multiplicities come from the exact characteristic polynomials.
        # Keep the two positive branches and the sole nonzero varied branch.
        fixed = np.sort(np.imag(np.linalg.eigvals(generator)))[-2:]
        varied = float(np.max(np.imag(np.linalg.eigvals(varied_generator))))
        values, vectors = np.linalg.eigh(W)
        Wroot = (vectors * np.sqrt(values)) @ vectors.T
        reduced = np.sqrt(np.linalg.eigvalsh(Wroot @ C @ Wroot))
        return fixed, varied, reduced

    sigma = np.array([0.0, 1.0 / 16.0, 1.0 / 4.0, 1.0, 4.0])
    fixed = np.empty((5, 2), dtype=float)
    long = np.empty(5, dtype=float)
    reduced = np.empty_like(fixed)
    fixed_error = varied_error = reduced_error = 0.0
    coefficient = e_y * e_i * (8.0 + 4.0 * (1.0 - phi) ** 2)
    for j, s in enumerate(sigma):
        fixed[j], long[j], reduced[j] = spectra(float(s))
        expected = np.sqrt([2.0 * s + s * s / 4.0, 4.0 * phi * s + s * s / 4.0])
        fixed_error = max(fixed_error, float(np.max(np.abs(fixed[j] - expected))))
        varied_error = max(varied_error, abs(long[j] - math.sqrt(coefficient * s + s * s / 4.0)))
        reduced_error = max(reduced_error, float(np.max(np.abs(fixed[j] - reduced[j]))))
    for name, error in (
        ("first_order_fixed_spectra", fixed_error),
        ("first_order_varied_spectra", varied_error),
        ("second_order_spectrum_agreement", reduced_error),
    ):
        check(rows, name, error < 1e-10, maximum_frequency_error=scalar(error))
    p = np.arange(3, dtype=float) * math.pi / 8.0
    gaps_fixed = np.empty((3, 2), dtype=float)
    gaps_long = np.empty(3, dtype=float)
    zero_scale_fixed = np.empty_like(gaps_fixed)
    zero_scale_long = np.empty_like(gaps_long)
    for j, pp in enumerate(p):
        gaps_fixed[j], gaps_long[j], _ = spectra(float(pp * pp))
        zero_scale_fixed[j], zero_scale_long[j], _ = spectra(float(0.0 * pp * pp))
    check(rows, "scale_gap_zero_mode", bool(np.all(gaps_fixed[0] == 0.0) and gaps_long[0] == 0.0))
    check(rows, "scale_gap_positive_modes", bool(np.all(gaps_fixed[1:] > 0.0) and np.all(gaps_long[1:] > 0.0)))
    check(rows, "scale_stiffness_zero_control", bool(np.all(zero_scale_fixed == 0.0) and np.all(zero_scale_long == 0.0)))
    return {
        "sigma": sigma, "omega_fixed": fixed, "omega_long": long,
        "omega_reduced": reduced, "scale_p": p, "scale_gaps_fixed": gaps_fixed,
        "scale_gaps_long": gaps_long, "scale_stiffness_zero_fixed": zero_scale_fixed,
        "scale_stiffness_zero_long": zero_scale_long,
    }, {"spectral_error": max(fixed_error, varied_error, reduced_error)}


def trajectories(rows: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    H = np.array([[1.0, 1.0], [1.0, 4.0]])
    psi0 = np.array([0.0j, 1.0 + 0.0j])
    times = np.arange(129, dtype=float) / 8.0

    def propagate(matrix: np.ndarray, initial: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        eigvals, eigvecs = np.linalg.eigh(matrix)
        unitary = (eigvecs[None, :, :] * np.exp(-1j * times[:, None] * eigvals)[:, None, :]) @ eigvecs.conj().T
        return unitary @ initial, unitary

    state, unitary = propagate(H, psi0)
    x, y = state.T
    norm = np.sum(np.abs(state) ** 2, axis=1)
    energy = np.einsum("ti,ij,tj->t", state.conj(), H, state).real
    gamma0 = np.array([[1.0, 0.2 + 0.1j], [0.2 - 0.1j, 0.7]], dtype=complex)
    covariance = unitary @ gamma0 @ unitary.conj().transpose(0, 2, 1)
    full_sol = solve_ivp(
        lambda _t, z: -1j * (H @ z),
        (0.0, float(times[-1])), psi0, method="DOP853", t_eval=times,
        rtol=1e-12, atol=1e-14,
    )
    memory_sol = solve_ivp(
        lambda t, z: np.array([-1j * z[0] - 1j * np.exp(-4j * t) - z[1], z[0] - 4j * z[1]]),
        (0.0, float(times[-1])), np.zeros(2, dtype=complex), method="DOP853",
        t_eval=times, rtol=1e-12, atol=1e-14,
    )
    covariance_sol = solve_ivp(
        lambda _t, z: (-1j * (H @ z.reshape(2, 2) - z.reshape(2, 2) @ H)).reshape(4),
        (0.0, float(times[-1])), gamma0.reshape(4), method="DOP853", t_eval=times,
        rtol=1e-12, atol=1e-14,
    )
    for solution in (full_sol, memory_sol, covariance_sol):
        if not solution.success or not np.array_equal(solution.t, times):
            raise ValueError("DOP853 did not complete the frozen sampling schedule")
    full = full_sol.y.T
    memory_x, memory_aux = memory_sol.y
    covariance_reference = covariance_sol.y.T.reshape(129, 2, 2)
    closed_population = 4.0 / 13.0 * np.sin(math.sqrt(13.0) * times / 2.0) ** 2
    full_norm = np.sum(np.abs(full) ** 2, axis=1)
    full_energy = np.einsum("ti,ij,tj->t", full.conj(), H, full).real
    for name, value, tol in (
        ("full_dop853_agreement", np.max(np.abs(full - state)), 1e-9),
        ("retarded_memory_agreement", np.max(np.abs(memory_x - x)), 1e-9),
        ("closed_population_formula", np.max(np.abs(np.abs(x) ** 2 - closed_population)), 1e-10),
        ("norm_conservation", max(np.max(np.abs(norm - 1.0)), np.max(np.abs(full_norm - 1.0))), 1e-10),
        ("energy_conservation", max(np.max(np.abs(energy - 4.0)), np.max(np.abs(full_energy - 4.0))), 1e-10),
        ("covariance_transport", np.max(np.abs(covariance - covariance_reference)), 1e-10),
    ):
        check(rows, name, value <= tol, maximum_error=scalar(value), tolerance=tol)
    control_uncoupled, _ = propagate(np.diag(np.diag(H)), psi0)
    control_zero, _ = propagate(H, np.zeros(2, dtype=complex))
    check(rows, "uncoupled_local_empty_control", np.max(np.abs(control_uncoupled[:, 0]) ** 2) <= 1e-12)
    check(rows, "globally_zero_control", np.max(np.abs(control_zero) ** 2) <= 1e-12)
    return {
        "times": times, "x": x, "y": y, "norm": norm, "energy": energy,
        "covariance": covariance, "covariance_initial": gamma0,
        "control_x_uncoupled": control_uncoupled[:, 0], "control_x_zero": control_zero[:, 0],
        "control_y_uncoupled": control_uncoupled[:, 1], "control_y_zero": control_zero[:, 1],
        "memory_x": memory_x, "memory_aux": memory_aux,
        "full_dop853": full, "full_dop853_norm": full_norm, "full_dop853_energy": full_energy,
    }


def scientific_calculation() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    rows: list[dict[str, Any]] = []
    algebra = exact_algebra(rows)
    schur = schur_checks(rows)
    spectral_arrays, spectral_meta = numerical_witness(rows, algebra["phi"])
    traj = trajectories(rows)
    arrays = {**spectral_arrays, **traj}
    all_finite = all(bool(np.all(np.isfinite(value.real))) and bool(np.all(np.isfinite(value.imag))) for value in arrays.values() if np.iscomplexobj(value)) and all(bool(np.all(np.isfinite(value))) for value in arrays.values() if not np.iscomplexobj(value))
    check(rows, "finite_raw_arrays", all_finite)
    numbers = {
        "exact_poles": schur["poles"].tolist(),
        "exact_residues": schur["residues"].tolist(),
        "truncated_roots": schur["truncated"].tolist(),
        "alpha_long": math.sqrt(algebra["phi"] / (1.0 + algebra["phi"])**2 * (8.0 + 4.0 * (1.0 - algebra["phi"])**2)),
        "maximum_frequency_error": spectral_meta["spectral_error"],
        "maximum_memory_error": float(np.max(np.abs(arrays["memory_x"] - arrays["x"]))),
        "covariance_initial_real": arrays["covariance_initial"].real.tolist(),
        "covariance_initial_imag": arrays["covariance_initial"].imag.tolist(),
    }
    passed = all(bool(row.get("passed")) for row in rows) and all(value is not None for value in numbers.values())
    return {"checks": rows, "numbers": numbers, "passed": passed}, arrays


def write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def run(output: Path, record: Path) -> int:
    output.mkdir(parents=False, exist_ok=False)
    source = Path(__file__).read_bytes()
    section_hashes: dict[str, str] = {}
    receipt: dict[str, Any] = {
        "schema": SCHEMA, "passed": False, "verdict": INCONCLUSIVE,
        "complete_physical_matter_formation": False, "source_sha256": sha256(source),
        "section_hashes": section_hashes, "array_sha256": None, "checks": [],
        "numbers": {"exact_poles": [], "exact_residues": [], "truncated_roots": [], "alpha_long": None},
        "error": None, "environment": {"python": platform.python_version(), "numpy": np.__version__, "sympy": sp.__version__},
    }
    try:
        with (output / "program_source.py").open("xb") as stream:
            stream.write(source)
        text = record.read_text(encoding="utf-8")
        for name, heading, expected in FROZEN:
            data = canonical_section(text, heading)
            section_hashes[name] = sha256(data)
            with (output / f"{name}.txt").open("xb") as stream:
                stream.write(data)
            if section_hashes[name] != expected:
                raise ValueError(f"frozen section hash mismatch for {name}")
        result, arrays = scientific_calculation()
        receipt.update(result)
        data_path = output / "data.npz"
        np.savez_compressed(data_path, **arrays)
        receipt["array_sha256"] = sha256(data_path.read_bytes())
        if receipt["passed"]:
            receipt["verdict"] = VERDICT
    except Exception as error:
        receipt["passed"] = False
        receipt["verdict"] = INCONCLUSIVE
        receipt["error"] = f"{type(error).__name__}: {error}"
    finally:
        write_json(output / "results.json", receipt)
    print(json.dumps({"passed": receipt["passed"], "verdict": receipt["verdict"], "check_count": len(receipt["checks"]), "error": receipt["error"]}, allow_nan=False))
    return 0 if receipt["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    args = parser.parse_args()
    return run(args.output_dir.resolve(), args.record.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
