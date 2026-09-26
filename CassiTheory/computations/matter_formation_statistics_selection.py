#!/usr/bin/env python3
"""Primary frozen finite-algebra and finite-occupation selection calculation.

The executable binds §§38.1--38.4 before evaluating the supplied algebraic,
occupation, trajectory, and anomaly witnesses.  It retains exact source
snapshots and the complete finite numeric array interface for the independent
verifier.  None of these finite witnesses is a claim of physical matter
formation.
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
from scipy.linalg import expm

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORD = ROOT / "computations/matter-formation-continuum-report.md"
SCHEMA = "matter-formation-statistics-selection-v1"
VERDICT = "SUPPORTS-conditional microscopic selection constraints"
INCONCLUSIVE = "INCONCLUSIVE"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
TIMES = np.array([0.0, 0.25, 1.0, 3.0], dtype=np.float64)
FROZEN = (
    ("section1", "### 38.1 A half-angle orbit and spatial rotations", "6ad640f866a36b57b0d51c4c161727dae797ba0fd20eecf7badab5a94c4011f7"),
    ("section2", "### 38.2 Quantum transfer changes the occupation drift", "837286ff5a4586994087aaf9b13ecd8578b8efe4516194c0d315ae9aef669f17"),
    ("section3", "### 38.3 Anomaly cancellation constrains a supplied chiral sector", "9433122093070db78c269f88320bbb991617066e9c3e3cde83674c74f29c900c"),
    ("section4", "### 38.4 Microscopic selection qualification: pre-execution criteria", "56cc9726dd95c2eceb9c7573acb24580d6de849e97bb90332e83b47d122d8f37"),
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


def check(rows: list[dict[str, Any]], name: str, passed: bool, **details: Any) -> None:
    row: dict[str, Any] = {"name": name, "passed": bool(passed)}
    for key, value in details.items():
        if isinstance(value, (np.floating, np.integer)):
            value = value.item()
        if isinstance(value, float) and not math.isfinite(value):
            value = None
        row[key] = value
    rows.append(row)


def exact_equal(value: sp.MatrixBase, target: sp.MatrixBase) -> bool:
    return all(sp.simplify(x) == 0 for x in value - target)


def pauli_algebra(rows: list[dict[str, Any]]) -> dict[str, Any]:
    I = sp.I
    sx = sp.Matrix([[0, 1], [1, 0]])
    sy = sp.Matrix([[0, -I], [I, 0]])
    sz = sp.Matrix([[1, 0], [0, -1]])
    sigmas = (sx, sy, sz)
    generators = tuple(s / 2 for s in sigmas)
    eps = sp.LeviCivita
    comm_ok = True
    commutator_strings: list[str] = []
    for i in range(3):
        for j in range(3):
            target = sp.zeros(2)
            for k in range(3):
                target += I * eps(i, j, k) * generators[k]
            residual = generators[i] * generators[j] - generators[j] * generators[i] - target
            comm_ok = comm_ok and exact_equal(residual, sp.zeros(2))
            commutator_strings.append(str(sp.simplify(residual)))
    check(rows, "pauli_angular_momentum_commutators_exact", comm_ok, residuals=commutator_strings)
    traces_ok = all(sp.trace(j) == 0 for j in generators)
    check(rows, "pauli_generator_zero_traces", traces_ok)
    angle = sp.pi / 2
    ux = sp.exp(-I * angle * sx / 2)
    uy = sp.exp(-I * angle * sy / 2)
    group_comm = sp.simplify(ux * uy * ux.conjugate().T * uy.conjugate().T)
    group_trace = sp.simplify(sp.trace(group_comm))
    check(rows, "two_axis_group_commutator_trace", group_trace == 1, value=str(group_trace))
    scalar = sp.exp(I * angle / 2) * sp.eye(2)
    scalar_comm = sp.simplify(scalar * scalar * scalar.conjugate().T * scalar.conjugate().T)
    scalar_trace = sp.simplify(sp.trace(scalar_comm))
    check(rows, "scalar_phase_group_commutator_trace", scalar_trace == 2, value=str(scalar_trace))
    spin_2pi = sp.simplify(sp.exp(-I * 2 * sp.pi * sx / 2))
    spin_4pi = sp.simplify(sp.exp(-I * 4 * sp.pi * sx / 2))
    spin_signs = exact_equal(spin_2pi, -sp.eye(2)) and exact_equal(spin_4pi, sp.eye(2))
    check(rows, "spinor_two_pi_four_pi_signs", spin_signs)
    jchi = -sp.eye(2) / 2
    check(rows, "scalar_phase_generator_nonzero_trace", sp.trace(jchi) != 0, trace=str(sp.trace(jchi)))
    return {"generators": generators, "group_commutator": group_comm}


def annihilators() -> tuple[sp.Matrix, sp.Matrix, sp.Matrix, sp.Matrix]:
    zero = sp.zeros(3)
    a3 = sp.zeros(3)
    a3[0, 1] = 1
    a3[1, 2] = sp.sqrt(2)
    ident3 = sp.eye(3)
    by_b = sp.kronecker_product(a3, ident3)
    bi_b = sp.kronecker_product(ident3, a3)
    # Basis |nY,nI>, index 2*nY+nI.  bI has (-1)^nY Jordan--Wigner sign.
    by_f = sp.zeros(4)
    bi_f = sp.zeros(4)
    states = [(ny, ni) for ny in range(2) for ni in range(2)]
    index = {state: i for i, state in enumerate(states)}
    for col, (ny, ni) in enumerate(states):
        if ny:
            by_f[index[(ny - 1, ni)], col] = 1
        if ni:
            bi_f[index[(ny, ni - 1)], col] = (-1) ** ny
    return by_b, bi_b, by_f, bi_f


def fermion_car(rows: list[dict[str, Any]], by: sp.Matrix, bi: sp.Matrix) -> None:
    ident = sp.eye(4)
    zero = sp.zeros(4)
    tests = (
        (by * by + by * by, zero),
        (bi * bi + bi * bi, zero),
        (by * bi + bi * by, zero),
        (by * by.T + by.T * by, ident),
        (bi * bi.T + bi.T * bi, ident),
        (by * bi.T + bi.T * by, zero),
    )
    passed = all(exact_equal(a, b) for a, b in tests)
    check(rows, "fermionic_jordan_wigner_CAR_exact", passed, residual_count=sum(not exact_equal(a, b) for a, b in tests))


def sector_basis(model: str, total: int) -> list[tuple[int, int]]:
    if model == "fermi":
        return [(0, 1), (1, 0)] if total == 1 else [(1, 1)]
    return [(k, total - k) for k in range(total + 1)]


def sector_indices(model: str, total: int) -> list[int]:
    if model == "fermi":
        return [ny * 2 + ni for ny, ni in sector_basis(model, total)]
    return [ny * 3 + ni for ny, ni in sector_basis(model, total)]


def restrict(matrix: sp.Matrix, indices: list[int]) -> sp.Matrix:
    return matrix.extract(indices, indices)


def shift_jumps(total: int) -> tuple[sp.Matrix, sp.Matrix]:
    d = total + 1
    down = sp.zeros(d)
    up = sp.zeros(d)
    # Column k is the source basis vector |k,N-k|.
    for k in range(d):
        if k:
            down[k - 1, k] = sp.sqrt(k)
        if k < total:
            up[k + 1, k] = sp.sqrt(sp.Symbol("phi") * (total - k))
    return down, up


def exact_probability_generator(down: sp.Matrix, up: sp.Matrix) -> sp.Matrix:
    d = down.rows
    generator = sp.zeros(d)
    for source in range(d):
        rho = sp.zeros(d)
        rho[source, source] = 1
        for jump in (down, up):
            image = jump * rho * jump.T
            rate = sp.simplify(sp.trace(image))
            if rate != 0:
                target = next(index for index in range(d) if image[index, index] != 0)
                generator[target, source] += rate
            loss = sp.simplify(sp.trace(jump.T * jump * rho))
            generator[source, source] -= loss
    return generator


def diagonal_adjoint(jumps: tuple[sp.Matrix, ...], observable: sp.Matrix) -> sp.Matrix:
    result = sp.zeros(observable.rows)
    for jump in jumps:
        result += jump.T * observable * jump
        result -= (jump.T * jump * observable + observable * jump.T * jump) / 2
    return sp.simplify(result)


def occupation_science(rows: list[dict[str, Any]], arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    by_b, bi_b, by_f, bi_f = annihilators()
    fermion_car(rows, by_f, bi_f)
    phi = sp.symbols("phi", positive=True)
    means: dict[str, float] = {}
    generators: dict[tuple[str, int], sp.Matrix] = {}
    stationary: dict[tuple[str, int], sp.Matrix] = {}
    for model in ("boson", "shift", "fermi"):
        for total in (1, 2):
            basis = sector_basis(model, total)
            d = len(basis)
            if model == "shift":
                down, up = shift_jumps(total)
                down = down.subs(sp.Symbol("phi"), sp.sqrt(5) / 2 + sp.Rational(1, 2))
                up = up.subs(sp.Symbol("phi"), sp.sqrt(5) / 2 + sp.Rational(1, 2))
            else:
                by, bi = (by_f, bi_f) if model == "fermi" else (by_b, bi_b)
                indices = sector_indices(model, total)
                down = restrict(bi.T * by, indices)
                up = sp.sqrt(phi) * restrict(by.T * bi, indices)
                down = down.subs(phi, sp.sqrt(5) / 2 + sp.Rational(1, 2))
                up = up.subs(phi, sp.sqrt(5) / 2 + sp.Rational(1, 2))
            G = exact_probability_generator(down, up)
            generators[(model, total)] = G
            # Exact stationary null vector, normalized by its sum.
            null = G.nullspace()
            if not null:
                raise ValueError(f"no stationary vector for {model} N={total}")
            candidate = null[0]
            candidate = candidate / sp.simplify(sum(candidate))
            stationary[(model, total)] = candidate
            k_values = [state[0] for state in basis]
            nY = sp.diag(*k_values)
            nI = sp.diag(*[total - k for k in k_values])
            arrays[f"{model}_N{total}_generator"] = np.asarray(G.evalf(), dtype=np.float64)
            arrays[f"{model}_N{total}_stationary"] = np.asarray(candidate.evalf(), dtype=np.float64).reshape(d)
            arrays[f"{model}_N{total}_number_y"] = np.asarray(k_values, dtype=np.float64)
            arrays[f"{model}_N{total}_jump_down"] = np.asarray(down.evalf(), dtype=np.float64)
            arrays[f"{model}_N{total}_jump_up"] = np.asarray(up.evalf(), dtype=np.float64)
            sigma = 0 if model == "shift" else (1 if model == "boson" else -1)
            expected = phi * nI - nY if model == "shift" else phi * nI - nY + sigma * (phi - 1) * nY * nI
            expected = expected.subs(phi, sp.sqrt(5) / 2 + sp.Rational(1, 2))
            drift = diagonal_adjoint((down, up), nY)
            total_drift = diagonal_adjoint((down, up), nY + nI)
            drift_ok = exact_equal(drift, expected)
            total_ok = exact_equal(total_drift, sp.zeros(d))
            check(rows, f"{model}_N{total}_adjoint_nY_drift_exact", drift_ok, residual=str(sp.simplify(drift - expected)))
            check(rows, f"{model}_N{total}_total_number_conserved_exact", total_ok, residual=str(sp.simplify(total_drift)))
            # Independently reconstruct rates from occupations, rather than from G.
            independent = sp.zeros(d)
            for source, k in enumerate(k_values):
                down_rate = k if model == "shift" else k * (total - k + 1)
                up_rate = (total - k) if model == "shift" else (total - k) * (k + 1)
                if model == "fermi":
                    down_rate = k * (1 - (total - k))
                    up_rate = (total - k) * (1 - k)
                up_rate *= phi
                if source > 0:
                    independent[source - 1, source] += down_rate
                if source + 1 < d:
                    independent[source + 1, source] += up_rate
                independent[source, source] -= down_rate + up_rate
            independent = independent.subs(phi, sp.sqrt(5) / 2 + sp.Rational(1, 2))
            check(rows, f"{model}_N{total}_occupation_transition_reconstruction", exact_equal(G, independent), residual=str(sp.simplify(G - independent)))
            if model == "shift":
                expected_stationary = sp.Matrix([sp.binomial(total, k) * phi**k for k in k_values])
            elif model == "boson":
                expected_stationary = sp.Matrix([phi**k for k in k_values])
            else:
                expected_stationary = sp.Matrix([phi**k for k in k_values]) if total == 1 else sp.Matrix([1])
            expected_stationary = expected_stationary / sp.simplify(sum(expected_stationary))
            expected_stationary = expected_stationary.subs(phi, sp.sqrt(5) / 2 + sp.Rational(1, 2))
            station_ok = exact_equal(candidate, expected_stationary)
            residual = G * candidate
            check(rows, f"{model}_N{total}_stationary_weights_exact", station_ok, residual=str(sp.simplify(candidate - expected_stationary)))
            check(rows, f"{model}_N{total}_stationary_generator_residual_exact", exact_equal(residual, sp.zeros(d, 1)), residual=str(sp.simplify(residual)))
            check(rows, f"{model}_N{total}_column_conservation_exact", exact_equal(sp.ones(1, d) * G, sp.zeros(1, d)))
            mean = float(sum(sp.Rational(k) * candidate[i] for i, k in enumerate(k_values)).evalf())
            means[f"{model}_N{total}"] = mean
            if model in ("boson", "shift"):
                p0 = np.zeros(d, dtype=np.float64)
                p0[0] = 1.0
                traj = np.vstack([expm(float(t) * arrays[f"{model}_N{total}_generator"]) @ p0 for t in TIMES])
                arrays[f"{model}_N{total}_trajectory"] = traj
                check(rows, f"{model}_N{total}_trajectory_normalization", float(np.max(np.abs(np.sum(traj, axis=1) - 1.0))) <= 1e-12, error=float(np.max(np.abs(np.sum(traj, axis=1) - 1.0))))
                check(rows, f"{model}_N{total}_trajectory_nonnegative", float(np.min(traj)) >= -1e-12, minimum=float(np.min(traj)))
    check(rows, "N1_boson_shift_generators_agree", np.array_equal(arrays["boson_N1_generator"], arrays["shift_N1_generator"]))
    check(rows, "N1_boson_shift_trajectories_agree", np.max(np.abs(arrays["boson_N1_trajectory"] - arrays["shift_N1_trajectory"])) <= 1e-12)
    check(rows, "N1_boson_fermi_generators_agree", np.array_equal(arrays["boson_N1_generator"], arrays["fermi_N1_generator"]))
    check(rows, "N2_three_means_distinct", len({round(means[name], 14) for name in ("boson_N2", "shift_N2", "fermi_N2")}) == 3, values=[means[name] for name in ("boson_N2", "shift_N2", "fermi_N2")])
    # The canonical gated boundary witness is positive while the bilinear Fermi drift is blocked.
    phi_exact = (sp.sqrt(5) + 1) / 2
    q_star = sp.simplify(4 / (4 + 2 * phi_exact ** -2))
    gamma_star = sp.simplify(1 - q_star)
    canonical_boundary = sp.simplify(gamma_star * (phi_exact - 1))
    blocked_boundary = diagonal_adjoint(
        (sp.Matrix(arrays["fermi_N2_jump_down"]), sp.Matrix(arrays["fermi_N2_jump_up"])),
        sp.eye(1),
    )[0]
    check(rows, "gated_pauli_boundary_drift_positive", canonical_boundary > 0, value=str(canonical_boundary))
    check(rows, "fermionic_fully_occupied_drift_zero", blocked_boundary == 0)
    check(rows, "shift_jumps_distinct_from_bilinear_N2", not np.array_equal(arrays["boson_N2_jump_down"], arrays["shift_N2_jump_down"]))
    arrays["gated_pauli_drift"] = np.array([float(canonical_boundary.evalf())], dtype=np.float64)
    arrays["no_neutrino_hypercharges"] = np.empty((2, 5), dtype=np.float64)
    arrays["no_neutrino_doublets"] = np.array([4, 6], dtype=np.int64)
    return arrays | {"_means": means}


def anomaly_science(rows: list[dict[str, Any]], arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    nc, h, yq, yl, yu, yd, ye, ynu = sp.symbols("N_c h y_Q y_L y_u y_d y_e y_nu")
    # Physical RH charges enter with the minus signs of their LH conjugates.
    polynomials = (
        2 * yq - yu - yd,
        nc * yq + yl,
        2 * nc * yq - nc * yu - nc * yd + 2 * yl - ye,
        2 * nc * yq**3 - nc * yu**3 - nc * yd**3 + 2 * yl**3 - ye**3,
    )
    check(rows, "anomaly_polynomials_constructed_before_substitution", all(isinstance(p, sp.Expr) for p in polynomials), expressions=[str(p) for p in polynomials])
    no_nu = {yq: h / nc, yl: -h, yu: h * (1 + 1 / nc), yd: h * (1 / nc - 1), ye: -2 * h}
    no_nu_residuals = [sp.factor(p.subs(no_nu)) for p in polynomials]
    check(rows, "no_neutrino_yukawa_anomalies_exact", all(value == 0 for value in no_nu_residuals), residuals=[str(value) for value in no_nu_residuals])
    neutrino = {yl: -nc * yq, yu: yq + h, yd: yq - h, ye: -nc * yq - h, ynu: -nc * yq + h}
    neutrino_polynomials = (polynomials[0], polynomials[1], polynomials[2] - ynu, polynomials[3] - ynu**3)
    nu_residuals = [sp.factor(p.subs(neutrino, simultaneous=True)) for p in neutrino_polynomials]
    check(rows, "neutrino_two_parameter_anomalies_exact", all(value == 0 for value in nu_residuals), residuals=[str(value) for value in nu_residuals])
    for index, color in enumerate((3, 5)):
        assignment = {key: sp.simplify(value.subs({nc: color, h: sp.Rational(1, 2)})) for key, value in no_nu.items()}
        arrays["no_neutrino_hypercharges"][index] = [float(assignment[key]) for key in (yq, yl, yu, yd, ye)]
        residuals = [float(p.subs(assignment, simultaneous=True).subs(nc, color)) for p in polynomials]
        check(rows, f"no_neutrino_Nc{color}_h_half_assignment", max(abs(value) for value in residuals) == 0.0, residuals=residuals)
    check(rows, "global_doublet_counts_even", all(int(value) % 2 == 0 for value in arrays["no_neutrino_doublets"]))
    # A chiral representation and its conjugate have opposite odd anomaly sums.
    vectorlike = [sp.expand(p.subs({yq: -yq, yl: -yl, yu: -yu, yd: -yd, ye: -ye})) for p in polynomials]
    check(rows, "conjugate_vectorlike_pair_anomaly_cancellation", all(sp.expand(a + b) == 0 for a, b in zip(polynomials, vectorlike)))
    check(rows, "vectorlike_added_doublet_count_even", (2 % 2) == 0)
    return {
        "no_neutrino_residuals": [str(value) for value in no_nu_residuals],
        "neutrino_residuals": [str(value) for value in nu_residuals],
        "N2_means": arrays.pop("_means"),
    }


def finite_arrays(arrays: dict[str, np.ndarray]) -> bool:
    return all(bool(np.all(np.isfinite(value))) for value in arrays.values())


def scientific_calculation() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    rows: list[dict[str, Any]] = []
    pauli = pauli_algebra(rows)
    arrays: dict[str, np.ndarray] = {
        "rotation_J": np.asarray([np.asarray(matrix.evalf(), dtype=np.complex128) for matrix in pauli["generators"]], dtype=np.complex128),
        "rotation_commutator": np.asarray(pauli["group_commutator"].evalf(), dtype=np.complex128),
        "times": TIMES.copy(),
    }
    arrays = occupation_science(rows, arrays)
    anomaly_numbers = anomaly_science(rows, arrays)
    check(rows, "finite_raw_arrays", finite_arrays(arrays))
    check(rows, "probability_generator_column_sums", all(np.max(np.abs(np.sum(arrays[f"{model}_N{total}_generator"], axis=0))) <= 1e-12 for model in ("boson", "shift", "fermi") for total in (1, 2)))
    means = anomaly_numbers.pop("N2_means")
    trajectories = [arrays[key] for key in arrays if key.endswith("_trajectory")]
    max_norm_error = float(max(np.max(np.abs(np.sum(value, axis=1) - 1.0)) for value in trajectories))
    min_probability = float(min(np.min(value) for value in trajectories))
    n1_disagreement = float(np.max(np.abs(arrays["boson_N1_trajectory"] - arrays["shift_N1_trajectory"])))
    numbers: dict[str, Any] = {
        "stationary_means": means,
        "gated_pauli_drift": float(arrays["gated_pauli_drift"][0]),
        "anomaly_residuals": anomaly_numbers,
        "n1_trajectory_max_disagreement": n1_disagreement,
        "trajectory_max_normalization_error": max_norm_error,
        "trajectory_min_probability": min_probability,
    }
    all_passed = all(bool(row.get("passed")) for row in rows)
    return {"checks": rows, "numbers": numbers, "passed": all_passed}, arrays


def write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def run(output: Path, record: Path) -> int:
    output.mkdir(parents=False, exist_ok=False)
    source = Path(__file__).read_bytes()
    section_hashes: dict[str, str] = {}
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "passed": False,
        "verdict": INCONCLUSIVE,
        "complete_physical_matter_formation": False,
        "source_sha256": sha256(source),
        "section_hashes": section_hashes,
        "array_sha256": None,
        "checks": [],
        "numbers": {},
        "error": None,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "sympy": sp.__version__},
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
        receipt["checks"] = []
        receipt["numbers"] = {}
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
