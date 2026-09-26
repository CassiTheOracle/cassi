#!/usr/bin/env python3
"""Primary finite-dimensional spinor-closure witnesses from the frozen protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "20260906_matter_formation_spinor_closure"
PREREG_PATH = ROOT / "computations" / "matter-formation-spinor-closure-prereg.md"
VERIFIER_PATH = ROOT / "computations" / "verify_matter_formation_spinor_closure.py"
DEFAULT_BRIDGE = ROOT / "two-fluid" / "cassi_dirac_bridge.py"
BRIDGE_BASE = ROOT / "two-fluid" / "cassi_bridge_v2.py"
SCHEMA = "cassi.matter-formation.spinor-closure.v1"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
LAMBDA = 0.02
NUM_TOL = 1.0e-12


class ContractError(RuntimeError):
    """Raised when a required input or numerical contract is malformed."""


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), ROOT.resolve()).replace("\\", "/")


def identity(path: Path, label: str, failures: list[str]) -> dict[str, str]:
    result = {"path": relative_path(path), "sha256": ""}
    try:
        result["sha256"] = canonical_sha256(path)
    except Exception as exc:
        failures.append(f"missing {label} identity: {type(exc).__name__}: {exc}")
    return result


def make_identities(bridge_path: Path, failures: list[str]) -> dict[str, dict[str, str]]:
    return {
        "primary": identity(SELF_PATH, "primary", failures),
        "verifier": identity(VERIFIER_PATH, "verifier", failures),
        "prereg": identity(PREREG_PATH, "preregistration", failures),
        "bridge": identity(bridge_path, "bridge", failures),
        "bridge_base": identity(BRIDGE_BASE, "bridge base", failures),
    }


def write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if path.exists() or temporary.exists():
        raise FileExistsError(f"refusing existing receipt or temporary artifact: {path}")
    created = False
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.link(temporary, path)
        temporary.unlink()
    except Exception:
        if created:
            temporary.unlink(missing_ok=True)
        raise


def require_finite(value: Any, label: str = "payload") -> None:
    if isinstance(value, (bool, str)) or value is None:
        return
    if isinstance(value, (int, np.integer)):
        return
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            raise ContractError(f"nonfinite {label}")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            require_finite(item, f"{label}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            require_finite(item, f"{label}[{index}]")
    elif isinstance(value, np.ndarray):
        if not np.all(np.isfinite(value)):
            raise ContractError(f"nonfinite {label}")
    else:
        raise ContractError(f"non-JSON value in {label}: {type(value).__name__}")




def constants_payload() -> dict[str, Any]:
    return {
        "phi": PHI,
        "lambda": LAMBDA,
        "phase_mu": 1.0,
        "phase_p_values": [0.5, 1.0 / PHI],
        "phase_theta_values": [-math.pi / 2.0, math.pi / 2.0],
        "phase_momenta": [[0.0, 0.0, 0.0], [0.3, -0.2, 0.4]],
        "positive_energy_cases": [[0.0, 1], [0.5, -1], [0.5, 1], [1.0, -1], [1.0, 1]],
        "stationary_mu_values": [0.0, 0.01, 0.1],
        "stationary_rho_values": [1.0, 4.0],
        "fixed_kappa": 0.02,
    }


def pauli_matrices() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.array([[0, 1], [1, 0]], dtype=np.complex128),
        np.array([[0, -1j], [1j, 0]], dtype=np.complex128),
        np.array([[1, 0], [0, -1]], dtype=np.complex128),
    )


def dirac_matrices() -> tuple[list[np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
    sx, sy, sz = pauli_matrices()
    zero = np.zeros((2, 2), dtype=np.complex128)
    ident = np.eye(2, dtype=np.complex128)
    alphas = [np.block([[zero, sigma], [sigma, zero]]) for sigma in (sx, sy, sz)]
    beta = np.block([[ident, zero], [zero, -ident]])
    gamma5 = np.block([[zero, ident], [ident, zero]])
    U = np.block([[ident, -ident], [ident, ident]]) / math.sqrt(2.0)
    return alphas, beta, gamma5, U


def hamiltonian(alphas: Sequence[np.ndarray], beta: np.ndarray, momentum: Sequence[float], mu: float) -> np.ndarray:
    return sum(float(momentum[i]) * alphas[i] for i in range(3)) + mu * beta


def operator_payload() -> dict[str, float]:
    alphas, beta, gamma5, U = dirac_matrices()
    ident4 = np.eye(4, dtype=np.complex128)
    ident2 = np.eye(2, dtype=np.complex128)
    py = (ident4 - gamma5) / 2.0
    pi = (ident4 + gamma5) / 2.0
    residuals = []
    for momentum in ((0.0, 0.0, 0.0), (0.3, -0.2, 0.4)):
        hd = hamiltonian(alphas, beta, momentum, 1.0)
        sigma_dot = sum(momentum[i] * pauli_matrices()[i] for i in range(3))
        expected = np.block([[-sigma_dot, 1.0 * ident2], [1.0 * ident2, sigma_dot]])
        transformed = U @ hd @ U.conj().T
        residuals.append(float(np.max(np.abs(transformed - expected))))
    return {
        "unitarity": float(np.max(np.abs(U @ U.conj().T - ident4))),
        "projectors": float(max(
            np.max(np.abs(py @ py - py)),
            np.max(np.abs(pi @ pi - pi)),
            np.max(np.abs(py @ pi)),
            np.max(np.abs(py + pi - ident4)),
        )),
        "kinetic_commutator": float(max(np.max(np.abs(a @ gamma5 - gamma5 @ a)) for a in alphas)),
        "mass_anticommutator": float(np.max(np.abs(beta @ gamma5 + gamma5 @ beta))),
        "hamiltonian_transform": float(max(residuals)),
    }

def phase_witnesses(constants: Mapping[str, Any]) -> list[dict[str, Any]]:
    alphas, beta, gamma5, U = dirac_matrices()
    py = 0.5 * (np.eye(4) - gamma5)
    pi = 0.5 * (np.eye(4) + gamma5)
    mu = float(constants["phase_mu"])
    rows: list[dict[str, Any]] = []
    for momentum in constants["phase_momenta"]:
        hd = hamiltonian(alphas, beta, momentum, mu)
        for p in constants["phase_p_values"]:
            for theta in constants["phase_theta_values"]:
                L = np.array([math.sqrt(p), 0.0], dtype=np.complex128)
                R = np.array([np.exp(1j * theta) * math.sqrt(1.0 - p), 0.0], dtype=np.complex128)
                chi = np.concatenate((L, R))
                psi = U.conj().T @ chi
                dpsi = -1j * hd @ psi
                ey = float(np.vdot(psi, py @ psi).real)
                ei = float(np.vdot(psi, pi @ psi).real)
                z = np.vdot(L, R)
                jy = [float(np.vdot(psi, py @ alpha @ psi).real) for alpha in alphas]
                ji = [float(np.vdot(psi, pi @ alpha @ psi).real) for alpha in alphas]
                direct = [float(2.0 * np.vdot(psi, projector @ dpsi).real) for projector in (py, pi)]
                continuity_rhs = [float(2.0 * mu * z.imag), float(-2.0 * mu * z.imag)]
                rho = ey + ei
                epsilon = ey - PHI * ei
                q = rho * rho / (rho * rho + PHI ** -2 + epsilon * epsilon)
                kappa = LAMBDA * (1.0 - q)
                canonical = [float(-kappa * epsilon), float(kappa * epsilon)]
                u, v = psi[:2], psi[2:]
                helper_y = np.vdot(u - v, u - v).real
                helper_i = np.vdot(u + v, u + v).real
                rows.append({
                    "momentum": [float(x) for x in momentum],
                    "p": float(p),
                    "theta": float(theta),
                    "E_Y": ey,
                    "E_I": ei,
                    "coherence_re": float(z.real),
                    "coherence_im": float(z.imag),
                    "q": float(q),
                    "dirac_rhs": direct,
                    "canonical_rhs": canonical,
                    "j_Y": jy,
                    "j_I": ji,
                    "helper_density_residual": float(max(abs(helper_y - 2.0 * ey), abs(helper_i - 2.0 * ei))),
                    "continuity_residual": float(max(abs(direct[0] - continuity_rhs[0]), abs(direct[1] - continuity_rhs[1]))),
                })
    return rows


def positive_energy_witnesses(constants: Mapping[str, Any]) -> list[dict[str, Any]]:
    alphas, beta, _, U = dirac_matrices()
    ident4 = np.eye(4, dtype=np.complex128)
    rows: list[dict[str, Any]] = []
    for pz, helicity in constants["positive_energy_cases"]:
        pz, helicity = float(pz), int(helicity)
        energy = math.sqrt(1.0 + pz * pz)
        w = np.array([1.0, 0.0] if helicity == 1 else [0.0, 1.0], dtype=np.complex128)
        u = math.sqrt((energy + 1.0) / (2.0 * energy)) * w
        v = (helicity * pz / math.sqrt(2.0 * energy * (energy + 1.0))) * w
        psi = np.concatenate((u, v))
        momentum = [0.0, 0.0, pz]
        hd = hamiltonian(alphas, beta, momentum, 1.0)
        chi = U @ psi
        L, R = chi[:2], chi[2:]
        ey, ei = float(np.vdot(L, L).real), float(np.vdot(R, R).real)
        rho = ey + ei
        epsilon = ey - PHI * ei
        q = rho * rho / (rho * rho + PHI ** -2 + epsilon * epsilon)
        kappa = LAMBDA * (1.0 - q)
        canonical = [float(-kappa * epsilon), float(kappa * epsilon)]
        dy = -1j * hd @ psi
        dchi = U @ dy
        direct = [float(2.0 * np.real(np.vdot(L, dchi[:2]))), float(2.0 * np.real(np.vdot(R, dchi[2:])))]
        pminus = (ident4 - hd / energy) / 2.0
        j_y_w = np.block([[np.zeros((2, 2), dtype=np.complex128), np.zeros((2, 2), dtype=np.complex128)], [np.eye(2), np.zeros((2, 2), dtype=np.complex128)]])
        j_i_w = np.block([[np.zeros((2, 2), dtype=np.complex128), np.eye(2)], [np.zeros((2, 2), dtype=np.complex128), np.zeros((2, 2), dtype=np.complex128)]])
        jumps = [math.sqrt(kappa) * (U.conj().T @ j_y_w @ U), math.sqrt(PHI * kappa) * (U.conj().T @ j_i_w @ U)]
        density = np.outer(psi, psi.conj())
        dissipator = np.zeros((4, 4), dtype=np.complex128)
        for jump in jumps:
            jj = jump.conj().T @ jump
            dissipator += jump @ density @ jump.conj().T - 0.5 * (jj @ density + density @ jj)
        leakage = float(np.real(np.trace(pminus @ dissipator)))
        amplitudes = float(sum(np.vdot(pminus @ jump @ psi, pminus @ jump @ psi).real for jump in jumps))
        reference = kappa * (1.0 + PHI) / 4.0 if pz == 0.0 else amplitudes
        rows.append({
            "p_z": pz,
            "helicity": helicity,
            "energy": float(energy),
            "E_Y": ey,
            "E_I": ei,
            "q": float(q),
            "kappa": float(kappa),
            "eigenstate_residual": float(np.max(np.abs(hd @ psi - energy * psi))),
            "dirac_rhs": direct,
            "canonical_rhs": canonical,
            "negative_energy_leakage": leakage,
            "leakage_residual": float(abs(leakage - reference)),
        })
    return rows


def fibre_generator(mu: float, kappa: float) -> np.ndarray:
    sx, _, _ = pauli_matrices()
    h = mu * sx
    jumps = [
        math.sqrt(kappa) * np.array([[0.0, 0.0], [1.0, 0.0]], dtype=np.complex128),
        math.sqrt(PHI * kappa) * np.array([[0.0, 1.0], [0.0, 0.0]], dtype=np.complex128),
    ]

    def gamma(x: np.ndarray) -> np.ndarray:
        ey, ei, zr, zi = x
        return np.array([[ey, zr - 1j * zi], [zr + 1j * zi, ei]], dtype=np.complex128)

    def components(g: np.ndarray) -> np.ndarray:
        dg = -1j * (h @ g - g @ h)
        for jump in jumps:
            jj = jump.conj().T @ jump
            dg += jump @ g @ jump.conj().T - 0.5 * (jj @ g + g @ jj)
        z = dg[1, 0]
        return np.array([dg[0, 0].real, dg[1, 1].real, z.real, z.imag], dtype=np.float64)

    basis = np.eye(4, dtype=np.float64)
    return np.column_stack([components(gamma(basis[:, i])) for i in range(4)])


def stationary_state(rho: float, mu: float, kappa: float) -> tuple[np.ndarray, float]:
    A = fibre_generator(mu, kappa)
    trace_row = np.array([[1.0, 1.0, 0.0, 0.0]], dtype=np.float64)
    system = np.vstack((A[[0, 2, 3], :], trace_row))
    rhs = np.array([0.0, 0.0, 0.0, rho], dtype=np.float64)
    state = np.linalg.solve(system, rhs)
    full_residual = float(np.max(np.abs(A @ state)))
    return state, full_residual


def stationary_row(rho: float, mu: float, kappa: float, gate_residual: float | None) -> dict[str, Any]:
    state, generator_residual = stationary_state(rho, mu, kappa)
    ey, ei, zr, zi = [float(x) for x in state]
    delta = ey - ei
    target = (PHI - 1.0) * rho / (1.0 + PHI)
    epsilon = ey - PHI * ei
    q = rho * rho / (rho * rho + PHI ** -2 + epsilon * epsilon)
    gamma = np.array([[ey, zr - 1j * zi], [zr + 1j * zi, ei]], dtype=np.complex128)
    return {
        "rho": float(rho),
        "mu": float(mu),
        "kappa": float(kappa),
        "E_Y": ey,
        "E_I": ei,
        "coherence_re": zr,
        "coherence_im": zi,
        "imbalance": float(delta),
        "target_imbalance": float(target),
        "ratio": float(ey / ei),
        "suppression": float(delta / target),
        "q": float(q),
        "generator_residual": generator_residual,
        "trace_residual": float(abs(ey + ei - rho)),
        "min_eigenvalue": float(np.min(np.linalg.eigvalsh(gamma))),
        "gate_residual": None if gate_residual is None else float(gate_residual),
    }


def stationary_payload(constants: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fixed: list[dict[str, Any]] = []
    fixed_kappa = float(constants["fixed_kappa"])
    for mu in constants["stationary_mu_values"]:
        fixed.append(stationary_row(1.0, float(mu), fixed_kappa, None))
    gated: list[dict[str, Any]] = []
    for rho in constants["stationary_rho_values"]:
        rho = float(rho)
        qstar = rho * rho / (rho * rho + PHI ** -2)
        for mu in constants["stationary_mu_values"]:
            lo, hi = LAMBDA * (1.0 - qstar), LAMBDA
            mu = float(mu)
            if mu == 0.0:
                kappa = lo
            else:
                for _ in range(90):
                    mid = 0.5 * (lo + hi)
                    state, _ = stationary_state(rho, mu, mid)
                    epsilon = state[0] - PHI * state[1]
                    q = rho * rho / (rho * rho + PHI ** -2 + epsilon * epsilon)
                    gate = LAMBDA * (1.0 - q)
                    if mid - gate > 0.0:
                        hi = mid
                    else:
                        lo = mid
                kappa = 0.5 * (lo + hi)
            gated.append(stationary_row(rho, mu, kappa, 0.0))
            gated[-1]["gate_residual"] = abs(kappa - LAMBDA * (1.0 - gated[-1]["q"]))
    return fixed, gated


def failed_receipt(ids: Mapping[str, Any], failures: list[str]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "identities": ids,
        "constants": {},
        "operators": {},
        "phase_witnesses": [],
        "positive_energy_witnesses": [],
        "fixed_stationary": [],
        "gated_stationary": [],
        "verdicts": {},
        "numerical_pass": False,
        "failures": failures,
    }


def run(output_dir: Path = DEFAULT_OUTPUT_DIR, bridge_source: Path = DEFAULT_BRIDGE) -> dict[str, Any]:
    output_dir, bridge_source = output_dir.resolve(), bridge_source.resolve()
    output_path = output_dir / "results.json"
    if output_path.exists() or output_path.with_name(output_path.name + ".tmp").exists():
        raise FileExistsError(f"refusing existing receipt or temporary artifact: {output_path}")
    failures: list[str] = []
    ids = make_identities(bridge_source, failures)
    receipt = failed_receipt(ids, failures)
    try:
        if any(not item["sha256"] for item in ids.values()):
            raise ContractError("required source identity is missing")
        constants = constants_payload()
        operators = operator_payload()
        phases = phase_witnesses(constants)
        positive = positive_energy_witnesses(constants)
        fixed, gated = stationary_payload(constants)
        groups: dict[str, list[str]] = {
            "observable_map": [],
            "closed_conversion": [],
            "massive_fixed_point": [],
            "positive_energy_channel": [],
        }

        def reject(message: str, *affected: str) -> None:
            for key in affected:
                groups[key].append(message)

        for name, residual in operators.items():
            if residual > NUM_TOL:
                affected = ["closed_conversion", "positive_energy_channel"]
                if name in ("unitarity", "projectors"):
                    affected.append("observable_map")
                reject(f"operator {name}: {residual:.17g}", *affected)
        for index, row in enumerate(phases):
            if row["helper_density_residual"] > NUM_TOL:
                reject(f"helper density at phase row {index}", "observable_map", "closed_conversion")
            if min(row["E_Y"], row["E_I"]) < -NUM_TOL:
                reject(f"density positivity at phase row {index}", "observable_map")
            if row["continuity_residual"] > NUM_TOL:
                reject(f"continuity at phase row {index}", "closed_conversion")
            if abs(row["dirac_rhs"][0]) <= 1.0e-6:
                reject(f"nonzero source at phase row {index}", "closed_conversion")
            if abs(row["p"] - PHI ** -1) <= NUM_TOL and max(map(abs, row["canonical_rhs"])) > NUM_TOL:
                reject(f"canonical equilibrium at phase row {index}", "closed_conversion")
        for index in range(0, len(phases), 2):
            left, right = phases[index:index + 2]
            same = max(abs(left[key] - right[key]) for key in ("E_Y", "E_I", "q"))
            for key in ("j_Y", "j_I"):
                same = max(same, max(abs(a - b) for a, b in zip(left[key], right[key])))
            if same > NUM_TOL:
                reject(f"matched observables in phase pair {index // 2}", "closed_conversion")
            if max(abs(a + b) for a, b in zip(left["dirac_rhs"], right["dirac_rhs"])) > NUM_TOL:
                reject(f"opposite sources in phase pair {index // 2}", "closed_conversion")
        for index, row in enumerate(positive):
            if row["eigenstate_residual"] > NUM_TOL:
                reject(f"positive-energy eigenstate {index}", "closed_conversion", "positive_energy_channel")
            if max(map(abs, row["dirac_rhs"])) > NUM_TOL:
                reject(f"stationary Dirac density at positive-energy row {index}", "closed_conversion")
            if row["leakage_residual"] > NUM_TOL:
                reject(f"leakage identity at positive-energy row {index}", "positive_energy_channel")
            if row["negative_energy_leakage"] <= 1.0e-6:
                reject(f"positive leakage at positive-energy row {index}", "positive_energy_channel")
        if max(map(abs, positive[0]["canonical_rhs"])) <= 1.0e-6:
            reject("nonzero rest canonical source", "closed_conversion")
        for label, rows in (("fixed_stationary", fixed), ("gated_stationary", gated)):
            for index, row in enumerate(rows):
                prefix = f"{label} row {index}"
                if row["generator_residual"] > NUM_TOL or row["trace_residual"] > NUM_TOL:
                    reject(f"{prefix}: stationary identity", "massive_fixed_point")
                if row["min_eigenvalue"] < -NUM_TOL:
                    reject(f"{prefix}: positivity", "massive_fixed_point")
                if row["mu"] > 0.0 and not (0.0 < row["imbalance"] < row["target_imbalance"]):
                    reject(f"{prefix}: massive imbalance bound", "massive_fixed_point")
                if row["mu"] == 0.0:
                    if abs(row["imbalance"] - row["target_imbalance"]) > NUM_TOL or abs(row["ratio"] - PHI) > NUM_TOL:
                        reject(f"{prefix}: massless equilibrium", "massive_fixed_point")
                if row["gate_residual"] is not None and row["gate_residual"] > NUM_TOL:
                    reject(f"{prefix}: gate identity", "massive_fixed_point")
        supported = {
            "observable_map": "SUPPORTS—nonnegative chiral-current interpretation of the component map",
            "closed_conversion": "CONTRADICTS—closed Dirac realization of canonical two-density conversion",
            "massive_fixed_point": "CONTRADICTS—golden population fixed point for the specified massive Dirac and minimal conversion lift",
            "positive_energy_channel": "CONTRADICTS—positive-energy invariance of the specified chiral conversion channel",
        }
        verdicts = {key: "INCONCLUSIVE" if groups[key] else value for key, value in supported.items()}
        failures.extend(f"{key}: {message}" for key, messages in groups.items() for message in messages)
        payload = {
            "constants": constants,
            "operators": operators,
            "phase_witnesses": phases,
            "positive_energy_witnesses": positive,
            "fixed_stationary": fixed,
            "gated_stationary": gated,
            "verdicts": verdicts,
        }
        require_finite(payload, "scientific payload")
        receipt.update(payload)
        receipt["numerical_pass"] = not failures
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
        receipt = failed_receipt(ids, failures)
    receipt["failures"] = failures
    receipt["numerical_pass"] = bool(receipt["numerical_pass"] and not failures)
    write_json_exclusive(output_path, receipt)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bridge-source", type=Path, default=DEFAULT_BRIDGE)
    args = parser.parse_args(argv)
    try:
        receipt = run(args.output_dir, args.bridge_source)
    except Exception as exc:
        print(f"spinor closure failed before receipt: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps({"numerical_pass": receipt["numerical_pass"], "failures": receipt["failures"], "verdicts": receipt["verdicts"]}, sort_keys=True))
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
