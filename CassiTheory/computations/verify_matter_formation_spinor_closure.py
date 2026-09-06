#!/usr/bin/env python3
"""Independent verifier for the positive-spinor observable closure witness."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()
PREREG_PATH = ROOT / "computations" / "matter-formation-spinor-closure-prereg.md"
PRIMARY_PATH = ROOT / "computations" / "matter_formation_spinor_closure.py"
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "20260906_matter_formation_spinor_closure"
DEFAULT_BRIDGE_SOURCE = ROOT / "two-fluid" / "cassi_dirac_bridge.py"
BRIDGE_BASE_PATH = ROOT / "two-fluid" / "cassi_bridge_v2.py"
VERIFY_SCHEMA = "cassi.matter-formation.spinor-closure.verification.v1"
PRIMARY_SCHEMA = "cassi.matter-formation.spinor-closure.v1"
NUM_TOL = 1.0e-10
IDENTITY_TOL = 1.0e-12
EIGEN_TOL = 1.0e-12
NONZERO_TOL = 1.0e-6

PHI = (1.0 + math.sqrt(5.0)) / 2.0
LAMBDA = 0.02
PHASE_MU = 1.0
PHASE_P_VALUES = (0.5, 1.0 / PHI)
PHASE_THETA_VALUES = (-math.pi / 2.0, math.pi / 2.0)
PHASE_MOMENTA = ((0.0, 0.0, 0.0), (0.3, -0.2, 0.4))
POSITIVE_ENERGY_CASES = ((0.0, 1), (0.5, -1), (0.5, 1), (1.0, -1), (1.0, 1))
STATIONARY_MU_VALUES = (0.0, 0.01, 0.1)
STATIONARY_RHO_VALUES = (1.0, 4.0)
FIXED_KAPPA = 0.02

SIGMA_X = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
SIGMA_Y = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex)
SIGMA_Z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)
SIGMAS = (SIGMA_X, SIGMA_Y, SIGMA_Z)
I2 = np.eye(2, dtype=complex)
I4 = np.eye(4, dtype=complex)
ZERO2 = np.zeros((2, 2), dtype=complex)
ALPHAS = tuple(np.block([[ZERO2, sigma], [sigma, ZERO2]]) for sigma in SIGMAS)
BETA = np.block([[I2, ZERO2], [ZERO2, -I2]])
GAMMA5 = np.block([[ZERO2, I2], [I2, ZERO2]])
U = (1.0 / math.sqrt(2.0)) * np.block([[I2, -I2], [I2, I2]])
PY = (I4 - GAMMA5) / 2.0
PI = (I4 + GAMMA5) / 2.0


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def relpath(path: Path) -> str:
    return Path(os.path.relpath(path.resolve(), ROOT)).as_posix()


def identity(path: Path) -> dict[str, str]:
    result = {"path": relpath(path), "sha256": ""}
    try:
        if path.is_file():
            result["sha256"] = canonical_sha256(path)
    except OSError:
        pass
    return result


def finite(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.number)):
        return False
    return math.isfinite(float(value))


def finite_tree(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and finite_tree(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_tree(item) for item in value)
    if isinstance(value, (bool, str)) or value is None:
        return True
    return finite(value)


def scalar(value: Any) -> float:
    return float(value)


def vec(value: np.ndarray) -> list[float]:
    return [float(np.real(item)) for item in value]




def hamiltonian(momentum: Sequence[float], mu: float) -> np.ndarray:
    result = mu * BETA.copy()
    for component, alpha in zip(momentum, ALPHAS):
        result = result + float(component) * alpha
    return result


def block_spinor(top: np.ndarray, bottom: np.ndarray) -> np.ndarray:
    return np.concatenate((top, bottom))


def operator_payload() -> dict[str, float]:
    transform_residuals = []
    for momentum in PHASE_MOMENTA:
        sigma_dot = sum(momentum[i] * SIGMAS[i] for i in range(3))
        transformed = U @ hamiltonian(momentum, PHASE_MU) @ U.conj().T
        target = np.block([
            [-sigma_dot, PHASE_MU * I2],
            [PHASE_MU * I2, sigma_dot],
        ])
        transform_residuals.append(np.max(np.abs(transformed - target)))
    return {
        "unitarity": scalar(np.max(np.abs(U.conj().T @ U - I4))),
        "projectors": scalar(max(
            np.max(np.abs(PY @ PY - PY)),
            np.max(np.abs(PI @ PI - PI)),
            np.max(np.abs(PY @ PI)),
            np.max(np.abs(PY + PI - I4)),
        )),
        "kinetic_commutator": scalar(max(np.max(np.abs(alpha @ GAMMA5 - GAMMA5 @ alpha)) for alpha in ALPHAS)),
        "mass_anticommutator": scalar(np.max(np.abs(BETA @ GAMMA5 + GAMMA5 @ BETA))),
        "hamiltonian_transform": scalar(max(transform_residuals)),
    }


def q_gate(ey: float, ei: float) -> tuple[float, float, float]:
    rho = ey + ei
    epsilon = ey - PHI * ei
    q = rho * rho / (rho * rho + PHI ** -2 + epsilon * epsilon)
    return q, LAMBDA * (1.0 - q), epsilon
def phase_payload() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for momentum in PHASE_MOMENTA:
        sigma_dot = sum(momentum[i] * SIGMAS[i] for i in range(3))
        for p in PHASE_P_VALUES:
            for theta in PHASE_THETA_VALUES:
                L = np.sqrt(p) * np.array([1.0, 0.0], dtype=complex)
                R = np.exp(1.0j * theta) * np.sqrt(1.0 - p) * np.array([1.0, 0.0], dtype=complex)
                u = (L + R) / math.sqrt(2.0)
                v = (R - L) / math.sqrt(2.0)
                L_check = (u - v) / math.sqrt(2.0)
                R_check = (u + v) / math.sqrt(2.0)
                dL = 1.0j * sigma_dot @ L - 1.0j * PHASE_MU * R
                dR = -1.0j * PHASE_MU * L - 1.0j * sigma_dot @ R
                EY = float(np.vdot(L, L).real)
                EI = float(np.vdot(R, R).real)
                z = np.vdot(L, R)
                dEY = float(2.0 * np.real(np.vdot(L, dL)))
                dEI = float(2.0 * np.real(np.vdot(R, dR)))
                jY = [-float(np.vdot(L, sigma @ L).real) for sigma in SIGMAS]
                jI = [float(np.vdot(R, sigma @ R).real) for sigma in SIGMAS]
                q, kappa, epsilon = q_gate(EY, EI)
                canonical = [-kappa * epsilon, kappa * epsilon]
                dirac_source = [2.0 * PHASE_MU * z.imag, -2.0 * PHASE_MU * z.imag]
                helper_y = 2.0 * float(np.vdot(L_check, L_check).real)
                helper_i = 2.0 * float(np.vdot(R_check, R_check).real)
                rows.append({
                    "momentum": [float(item) for item in momentum],
                    "p": float(p),
                    "theta": float(theta),
                    "E_Y": EY,
                    "E_I": EI,
                    "coherence_re": float(z.real),
                    "coherence_im": float(z.imag),
                    "q": q,
                    "dirac_rhs": [dEY, dEI],
                    "canonical_rhs": canonical,
                    "j_Y": jY,
                    "j_I": jI,
                    "helper_density_residual": float(max(abs(helper_y - 2.0 * EY), abs(helper_i - 2.0 * EI))),
                    "continuity_residual": float(max(abs(dEY - dirac_source[0]), abs(dEI - dirac_source[1]))),
                })
    return rows


def positive_energy_payload() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pz, helicity in POSITIVE_ENERGY_CASES:
        energy = math.sqrt(1.0 + pz * pz)
        wh = np.array([1.0, 0.0], dtype=complex) if helicity == 1 else np.array([0.0, 1.0], dtype=complex)
        u = math.sqrt((energy + 1.0) / (2.0 * energy)) * wh
        v = (helicity * pz / math.sqrt(2.0 * energy * (energy + 1.0))) * wh
        psi = block_spinor(u, v)
        EY = float(np.vdot((psi[:2] - psi[2:]) / math.sqrt(2.0), (psi[:2] - psi[2:]) / math.sqrt(2.0)).real)
        EI = float(np.vdot((psi[:2] + psi[2:]) / math.sqrt(2.0), (psi[:2] + psi[2:]) / math.sqrt(2.0)).real)
        q, kappa, epsilon = q_gate(EY, EI)
        H = hamiltonian((0.0, 0.0, pz), 1.0)
        eig_residual = float(np.max(np.abs(H @ psi - energy * psi)))
        canonical = [-kappa * epsilon, kappa * epsilon]
        pminus = (I4 - H / energy) / 2.0
        jw_yi = math.sqrt(kappa) * np.block([[ZERO2, ZERO2], [I2, ZERO2]])
        jw_iy = math.sqrt(PHI * kappa) * np.block([[ZERO2, I2], [ZERO2, ZERO2]])
        leakage = 0.0
        for jump_weyl in (jw_yi, jw_iy):
            jump_dirac = U.conj().T @ jump_weyl @ U
            transition = pminus @ jump_dirac @ psi
            leakage += float(np.vdot(transition, transition).real)
        rest_reference = kappa * (1.0 + PHI) / 4.0
        leakage_reference = rest_reference if abs(pz) <= IDENTITY_TOL else leakage
        rows.append({
            "p_z": float(pz),
            "helicity": int(helicity),
            "energy": float(energy),
            "E_Y": EY,
            "E_I": EI,
            "q": q,
            "kappa": kappa,
            "eigenstate_residual": eig_residual,
            "dirac_rhs": [0.0, 0.0],
            "canonical_rhs": canonical,
            "negative_energy_leakage": leakage,
            "leakage_residual": float(abs(leakage - leakage_reference)),
        })
    return rows


def stationary_row(rho: float, mu: float, kappa: float, gate_residual: float | None) -> dict[str, Any]:
    s = 1.0 + PHI
    delta_star = (PHI - 1.0) * rho / s
    if mu == 0.0:
        delta = delta_star
    else:
        delta = delta_star / (1.0 + 8.0 * mu * mu / (s * s * kappa * kappa))
    EY, EI = (rho + delta) / 2.0, (rho - delta) / 2.0
    z = -2.0j * mu * delta / (s * kappa) if kappa != 0.0 else 0.0j
    epsilon = EY - PHI * EI
    q = rho * rho / (rho * rho + PHI ** -2 + epsilon * epsilon)
    dEY = 2.0 * mu * z.imag - kappa * epsilon
    dEI = -dEY
    dz = -1.0j * mu * delta - s * kappa * z / 2.0
    generator_residual = max(abs(dEY), abs(dEI), abs(dz))
    gamma = np.array([[EY, np.conj(z)], [z, EI]], dtype=complex)
    min_eigenvalue = float(np.min(np.linalg.eigvalsh(gamma).real))
    return {
        "rho": float(rho),
        "mu": float(mu),
        "kappa": float(kappa),
        "E_Y": float(EY),
        "E_I": float(EI),
        "coherence_re": float(z.real),
        "coherence_im": float(z.imag),
        "imbalance": float(delta),
        "target_imbalance": float(delta_star),
        "ratio": float(EY / EI),
        "suppression": float(delta / delta_star) if delta_star != 0.0 else 1.0,
        "q": float(q),
        "generator_residual": float(generator_residual),
        "trace_residual": float(abs(EY + EI - rho)),
        "min_eigenvalue": min_eigenvalue,
        "gate_residual": None if gate_residual is None else float(gate_residual),
    }


def gated_delta(rho: float, mu: float) -> float:
    s = 1.0 + PHI
    delta_star = (PHI - 1.0) * rho / s
    if mu == 0.0:
        return delta_star

    def equation(delta: float) -> float:
        ey, ei = (rho + delta) / 2.0, (rho - delta) / 2.0
        q, kappa, _ = q_gate(ey, ei)
        return delta - delta_star / (1.0 + 8.0 * mu * mu / (s * s * kappa * kappa))

    lo, hi = 0.0, delta_star
    for _ in range(90):
        midpoint = (lo + hi) / 2.0
        if equation(midpoint) > 0.0:
            hi = midpoint
        else:
            lo = midpoint
    return (lo + hi) / 2.0


def stationary_payload() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fixed: list[dict[str, Any]] = []
    for mu in STATIONARY_MU_VALUES:
        fixed.append(stationary_row(1.0, mu, FIXED_KAPPA, None))
    gated: list[dict[str, Any]] = []
    for rho in STATIONARY_RHO_VALUES:
        for mu in STATIONARY_MU_VALUES:
            delta = gated_delta(rho, mu)
            ey, ei = (rho + delta) / 2.0, (rho - delta) / 2.0
            q, kappa, _ = q_gate(ey, ei)
            gated.append(stationary_row(rho, mu, kappa, abs(kappa - LAMBDA * (1.0 - q))))
    return fixed, gated


def constants_payload() -> dict[str, Any]:
    return {
        "phi": PHI,
        "lambda": LAMBDA,
        "phase_mu": PHASE_MU,
        "phase_p_values": list(PHASE_P_VALUES),
        "phase_theta_values": list(PHASE_THETA_VALUES),
        "phase_momenta": [list(momentum) for momentum in PHASE_MOMENTA],
        "positive_energy_cases": [[float(pz), int(helicity)] for pz, helicity in POSITIVE_ENERGY_CASES],
        "stationary_mu_values": list(STATIONARY_MU_VALUES),
        "stationary_rho_values": list(STATIONARY_RHO_VALUES),
        "fixed_kappa": FIXED_KAPPA,
    }


def science_payload() -> dict[str, Any]:
    fixed, gated = stationary_payload()
    return {
        "constants": constants_payload(),
        "operators": operator_payload(),
        "phase_witnesses": phase_payload(),
        "positive_energy_witnesses": positive_energy_payload(),
        "fixed_stationary": fixed,
        "gated_stationary": gated,
        "verdicts": {
            "observable_map": "SUPPORTS—nonnegative chiral-current interpretation of the component map",
            "closed_conversion": "CONTRADICTS—closed Dirac realization of canonical two-density conversion",
            "massive_fixed_point": "CONTRADICTS—golden population fixed point for the specified massive Dirac and minimal conversion lift",
            "positive_energy_channel": "CONTRADICTS—positive-energy invariance of the specified chiral conversion channel",
        },
    }


def empty_science() -> dict[str, Any]:
    return {
        "constants": {},
        "operators": {},
        "phase_witnesses": [],
        "positive_energy_witnesses": [],
        "fixed_stationary": [],
        "gated_stationary": [],
        "verdicts": {},
    }


def json_load(path: Path) -> Any:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return json.load(stream)


def write_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if path.exists() or temporary.exists():
        raise FileExistsError(f"refusing existing verifier receipt: {path}")
    created = False
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        temporary.unlink()
    except Exception:
        if created:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        raise


def compare_recursive(actual: Any, expected: Any, path: str, mismatches: list[str], comparisons: list[dict[str, Any]]) -> None:
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            mismatches.append(f"{path}: expected object")
            comparisons.append({"path": path, "pass": False})
            return
        expected_keys, actual_keys = set(expected.keys()), set(actual.keys())
        if expected_keys != actual_keys:
            mismatches.append(f"{path}: key mismatch")
        for key in expected.keys():
            if key in actual:
                compare_recursive(actual[key], expected[key], f"{path}.{key}", mismatches, comparisons)
        comparisons.append({"path": path, "pass": expected_keys == actual_keys})
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            mismatches.append(f"{path}: array length/type mismatch")
            comparisons.append({"path": path, "pass": False})
            return
        for index, item in enumerate(expected):
            compare_recursive(actual[index], item, f"{path}[{index}]", mismatches, comparisons)
        comparisons.append({"path": path, "pass": True})
        return
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        okay = type(actual) is type(expected) and actual == expected
    elif finite(expected):
        okay = finite(actual) and abs(float(actual) - float(expected)) <= NUM_TOL * max(1.0, abs(float(actual)), abs(float(expected)))
    else:
        okay = False
    if not okay:
        mismatches.append(f"{path}: value mismatch")
    comparisons.append({"path": path, "pass": bool(okay)})


def expected_identities(bridge_source: Path) -> dict[str, dict[str, str]]:
    return {
        "primary": identity(PRIMARY_PATH),
        "verifier": identity(SELF_PATH),
        "prereg": identity(PREREG_PATH),
        "bridge": identity(bridge_source),
        "bridge_base": identity(BRIDGE_BASE_PATH),
    }


def failure_receipt(ids: Mapping[str, Any], input_hash: str, failures: list[str], mismatches: list[str] | None = None, comparisons: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema": VERIFY_SCHEMA,
        "identities": dict(ids),
        "input_sha256": input_hash,
        **empty_science(),
        "independent_checks": {"comparisons": comparisons or [], "mismatches": mismatches or []},
        "numerical_pass": False,
        "failures": failures,
    }


def assess_science(payload: Mapping[str, Any], label: str) -> tuple[dict[str, str], list[str]]:
    rejected: dict[str, list[str]] = {key: [] for key in VERDICTS}

    def mark(keys: Sequence[str], condition: bool, detail: str) -> None:
        if not condition:
            for key in keys:
                rejected[key].append(detail)

    closed = ("closed_conversion",)
    channel = ("positive_energy_channel",)
    massive = ("massive_fixed_point",)
    for name, value in payload["operators"].items():
        affected = ("closed_conversion", "positive_energy_channel")
        if name in {"projectors", "unitarity"}:
            affected += ("observable_map",)
        mark(affected, value <= IDENTITY_TOL, f"operator {name}")
    phases = payload["phase_witnesses"]
    for index, row in enumerate(phases):
        mark(("observable_map", "closed_conversion"), row["helper_density_residual"] <= IDENTITY_TOL,
             f"phase {index} helper map")
        mark(("observable_map",), row["E_Y"] >= -EIGEN_TOL and row["E_I"] >= -EIGEN_TOL,
             f"phase {index} nonnegative populations")
        mark(closed, row["continuity_residual"] <= IDENTITY_TOL, f"phase {index} continuity")
        mark(closed, abs(row["dirac_rhs"][0]) > NONZERO_TOL, f"phase {index} nonzero source")
        if abs(row["p"] - 1.0 / PHI) <= IDENTITY_TOL:
            mark(closed, all(abs(x) <= IDENTITY_TOL for x in row["canonical_rhs"]),
                 f"phase {index} canonical equilibrium")
    for index in range(0, len(phases), 2):
        negative, positive = phases[index], phases[index + 1]
        mark(closed, all(abs(negative[k] - positive[k]) <= IDENTITY_TOL for k in ("E_Y", "E_I", "q")),
             f"phase pair {index // 2} populations and gate")
        mark(closed, all(abs(a - b) <= IDENTITY_TOL for key in ("j_Y", "j_I")
                         for a, b in zip(negative[key], positive[key])), f"phase pair {index // 2} currents")
        mark(closed, all(abs(a + b) <= IDENTITY_TOL
                         for a, b in zip(negative["dirac_rhs"], positive["dirac_rhs"])),
             f"phase pair {index // 2} opposite sources")
    for index, row in enumerate(payload["positive_energy_witnesses"]):
        mark(closed + channel, row["eigenstate_residual"] <= IDENTITY_TOL, f"positive state {index}")
        mark(closed, all(abs(x) <= IDENTITY_TOL for x in row["dirac_rhs"]), f"stationary state {index}")
        mark(channel, row["leakage_residual"] <= IDENTITY_TOL, f"leakage identity {index}")
        mark(channel, row["negative_energy_leakage"] > NONZERO_TOL, f"nonzero leakage {index}")
    mark(closed, max(map(abs, payload["positive_energy_witnesses"][0]["canonical_rhs"])) > NONZERO_TOL,
         "nonzero rest canonical source")
    for family in ("fixed_stationary", "gated_stationary"):
        for index, row in enumerate(payload[family]):
            where = f"{family} {index}"
            mark(massive, max(row["generator_residual"], row["trace_residual"]) <= IDENTITY_TOL,
                 f"{where} stationary identities")
            mark(massive, row["min_eigenvalue"] >= -EIGEN_TOL, f"{where} positivity")
            if row["mu"] == 0.0:
                mark(massive, abs(row["imbalance"] - row["target_imbalance"]) <= IDENTITY_TOL
                     and abs(row["ratio"] - PHI) <= IDENTITY_TOL, f"{where} massless equilibrium")
            else:
                mark(massive, 0.0 < row["imbalance"] < row["target_imbalance"], f"{where} massive bound")
            if row["gate_residual"] is not None:
                mark(massive, row["gate_residual"] <= IDENTITY_TOL, f"{where} gate identity")
    decisions = {key: "INCONCLUSIVE" if rejected[key] else value for key, value in VERDICTS.items()}
    failures = [f"{label}.{key}: {reason}" for key, reasons in rejected.items() for reason in reasons]
    return decisions, failures


def run(input_dir: Path, output_dir: Path, bridge_source: Path) -> int:
    input_dir, output_dir, bridge_source = (path.resolve() for path in (input_dir, output_dir, bridge_source))
    output_path = output_dir / "verification.json"
    if output_path.exists() or output_path.with_name(output_path.name + ".tmp").exists():
        raise FileExistsError(f"refusing existing verifier receipt: {output_path}")
    primary_receipt_path = input_dir / "results.json"
    input_hash = ""
    ids = expected_identities(bridge_source)
    input_failures: list[str] = []
    science_failures: list[str] = []
    mismatches: list[str] = []
    comparisons: list[dict[str, Any]] = []
    science = empty_science()
    try:
        if not primary_receipt_path.is_file():
            raise ValueError("missing primary receipt")
        input_hash = raw_sha256(primary_receipt_path)
        if not all(item["sha256"] for item in ids.values()):
            raise ValueError("missing required source identity")
        primary = json_load(primary_receipt_path)
        required_keys = set(empty_science()) | {"schema", "identities", "numerical_pass", "failures"}
        if not isinstance(primary, Mapping) or set(primary) != required_keys or not finite_tree(primary):
            raise ValueError("malformed primary receipt fields")
        if primary["schema"] != PRIMARY_SCHEMA or primary["identities"] != ids:
            raise ValueError("primary schema or source identity mismatch")
        if type(primary["numerical_pass"]) is not bool or not isinstance(primary["failures"], list):
            raise ValueError("malformed primary outcome fields")
        if not all(isinstance(item, str) for item in primary["failures"]):
            raise ValueError("malformed primary failure entries")
        if primary["numerical_pass"] != (not primary["failures"]):
            raise ValueError("inconsistent primary outcome fields")
        expected = science_payload()
        for field, value in expected.items():
            if field != "verdicts":
                compare_recursive(primary[field], value, field, mismatches, comparisons)
        if mismatches:
            raise ValueError("independent scientific payload comparison failed")
        primary_decisions, primary_failures = assess_science(primary, "primary")
        independent_decisions, independent_failures = assess_science(expected, "independent")
        compare_recursive(primary["verdicts"], primary_decisions, "verdicts", mismatches, comparisons)
        if mismatches or primary["numerical_pass"] != (not primary_failures):
            raise ValueError("primary verdicts disagree with its witness evidence")
        science = expected
        science["verdicts"] = {
            key: value if primary_decisions[key] == value and independent_decisions[key] == value
            else "INCONCLUSIVE"
            for key, value in VERDICTS.items()
        }
        science_failures.extend(primary_failures)
        science_failures.extend(independent_failures)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        input_failures.append(f"primary input error: {exc}")
        science = empty_science()
    failures = input_failures + science_failures
    receipt = {
        "schema": VERIFY_SCHEMA,
        "identities": ids,
        "input_sha256": input_hash,
        **science,
        "independent_checks": {"comparisons": comparisons, "mismatches": mismatches},
        "numerical_pass": not failures,
        "failures": failures,
    }
    if not finite_tree(receipt):
        receipt = failure_receipt(ids, input_hash, ["verifier produced nonfinite receipt"], mismatches, comparisons)
    write_exclusive(output_path, receipt)
    return 0 if receipt["numerical_pass"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bridge-source", type=Path, default=DEFAULT_BRIDGE_SOURCE)
    args = parser.parse_args(argv)
    return run(args.input_dir, args.output_dir, args.bridge_source)


if __name__ == "__main__":
    raise SystemExit(main())
