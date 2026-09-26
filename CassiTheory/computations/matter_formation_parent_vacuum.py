#!/usr/bin/env python3
"""Produce the conditional scalar parent-vacuum and dilation receipt.

The calculation is deliberately limited to the frozen, topologically trivial
scalar identities in ``matter-formation-parent-vacuum-prereg.md``.  It checks
the homogeneous vacuum boundary, the depleted-carrier mass boundary, the
factorization and exact minimum, finite weighted charge/Hamiltonian witnesses,
and closed Gaussian spatial-dilation witnesses.  The mapped value of ``h_C``
is used as declared; no physical coefficient selection, dynamical formation,
soliton stability, or quantum claim is made.

Run from the repository root with::

    python computations/matter_formation_parent_vacuum.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "20260906_matter_formation_parent_vacuum"
PREREG_PATH = ROOT / "computations" / "matter-formation-parent-vacuum-prereg.md"
VERIFIER_PATH = ROOT / "computations" / "verify_matter_formation_parent_vacuum.py"
SCHEMA = "cassi.matter-formation.parent-vacuum.v1"
COEFFICIENTS = {
    "u_rho": 4.0,
    "u_C": 1.0,
    "k_Cx": 1.0,
    "e_C": 0.75,
    "h_C": 2.9598260763447164,
}
Z_VALUES = (0.0, 0.25, 1.0, 2.0)
N_VALUES = (0.0, 0.25, math.sqrt(2.0), 4.0, 8.0)
S_VALUE = math.sqrt(COEFFICIENTS["u_rho"] * COEFFICIENTS["u_C"] / 2.0)
A_DEPLETED = 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"]))
A_VACUUM = 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"] - S_VALUE))
A_VALUES = (
    1.0 / 64.0,
    1.0 / 32.0,
    1.0 / 16.0,
    1.0 / 8.0,
    1.0 / 4.0,
    0.9 * A_VACUUM,
    A_VACUUM,
    1.1 * A_VACUUM,
    1.0 / 2.0,
    1.0,
)
LAMBDA_VALUES = (0.5, 0.75, 1.0, 1.25, 1.5)
CHI_VALUES = (1.0 + 0.5j, -0.25 + 0.75j, 0.4 - 0.3j)
WEIGHTS = (1.0, 0.7, 1.3)
F_VALUES = (0.2, 0.8, 1.1)
ETA0_VALUES = (-0.2 + 0.1j, 0.3 - 0.4j, 0.7 + 0.2j)
TARGET_CHARGES = (-2.0, 0.0, 3.0)
ALGEBRA_TOL = 1.0e-11
SCALING_TOL = 1.0e-11


class ContractError(RuntimeError):
    """A frozen input, numerical, finiteness, or receipt-contract failure."""


def canonical_sha256(path: Path) -> str:
    """Hash source/specification bytes after CRLF-to-LF normalization."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), ROOT).replace("\\", "/")


def finite_scalar(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{label} is not a scalar float") from exc
    if not math.isfinite(result):
        raise ContractError(f"{label} is not finite")
    return result


def scaled_residual(left: float, right: float) -> float:
    left_f, right_f = finite_scalar(left, "left comparison"), finite_scalar(right, "right comparison")
    return abs(left_f - right_f) / max(1.0, abs(left_f), abs(right_f))


def potential(z: float, n: float, a: float) -> float:
    u_rho, u_c = COEFFICIENTS["u_rho"], COEFFICIENTS["u_C"]
    b = COEFFICIENTS["e_C"] + 1.0 / (4.0 * a)
    return u_rho / 4.0 * (z - 1.0) ** 2 + (b - COEFFICIENTS["h_C"] * (1.0 - z)) * n + u_c / 2.0 * n ** 2


def factorized_potential(z: float, n: float, a: float) -> float:
    u_rho, u_c = COEFFICIENTS["u_rho"], COEFFICIENTS["u_C"]
    b = COEFFICIENTS["e_C"] + 1.0 / (4.0 * a)
    s = math.sqrt(u_rho * u_c / 2.0)
    square = math.sqrt(u_rho) / 2.0 * (1.0 - z) - math.sqrt(u_c / 2.0) * n
    return square ** 2 + (b - (COEFFICIENTS["h_C"] - s) * (1.0 - z)) * n


def local_original_potential(f: float, chi: complex) -> float:
    z, n = f * f, abs(chi) ** 2
    return (
        COEFFICIENTS["u_rho"] / 4.0 * (z - 1.0) ** 2
        + (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - z)) * n
        + COEFFICIENTS["u_C"] / 2.0 * n ** 2
    )


def charge_witness(a: float, target_charge: float, transverse: bool) -> dict[str, Any]:
    chi = np.asarray(CHI_VALUES, dtype=np.complex128)
    weights = np.asarray(WEIGHTS, dtype=np.float64)
    eta0 = np.asarray(ETA0_VALUES, dtype=np.complex128)
    norm = float(np.sum(weights * np.abs(chi) ** 2))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ContractError("carrier witness norm is nonpositive or non-finite")
    kappa = (norm - target_charge) / (2.0 * a * norm)
    if transverse:
        inner_imag = float(np.imag(np.sum(weights * np.conjugate(chi) * eta0)))
        eta = eta0 - 1j * (inner_imag / norm) * chi
    else:
        eta = np.zeros(3, dtype=np.complex128)
    dot_chi = 1j * kappa * chi + eta
    measured_charge = norm - 2.0 * a * float(np.imag(np.sum(weights * np.conjugate(chi) * dot_chi)))
    kinetic_energy = a * float(np.sum(weights * np.abs(dot_chi) ** 2))
    kinetic_bound = (norm - target_charge) ** 2 / (4.0 * a * norm)
    transverse_energy = a * float(np.sum(weights * np.abs(eta) ** 2))
    kinetic_excess = kinetic_energy - kinetic_bound
    original_potential = float(sum(w * local_original_potential(f, c) for w, f, c in zip(WEIGHTS, F_VALUES, CHI_VALUES)))
    original_energy = kinetic_energy + original_potential
    canonical_kinetic = a * float(np.sum(weights * np.abs(dot_chi - 1j * chi / (2.0 * a)) ** 2))
    canonical_energy = canonical_kinetic + original_potential + float(np.sum(weights * np.abs(chi) ** 2)) / (4.0 * a)
    shift_residual = scaled_residual(canonical_energy - original_energy, target_charge / (2.0 * a))
    kinetic_residual = scaled_residual(kinetic_excess, transverse_energy)
    charge_residual = scaled_residual(measured_charge, target_charge)
    values = {
        "target_charge": target_charge,
        "transverse": transverse,
        "norm": norm,
        "measured_charge": measured_charge,
        "original_energy": original_energy,
        "canonical_energy": canonical_energy,
        "shift_scaled_residual": shift_residual,
        "kinetic_energy": kinetic_energy,
        "kinetic_bound": kinetic_bound,
        "kinetic_excess": kinetic_excess,
        "transverse_energy": transverse_energy,
        "kinetic_scaled_residual": kinetic_residual,
        "charge_scaled_residual": charge_residual,
    }
    for key, value in values.items():
        if key != "transverse":
            finite_scalar(value, f"charge witness {key}")
    return values


def gaussian_integrals(width: float, a: float) -> tuple[float, float]:
    """Return direct closed-form T,V for the stated radial Gaussian profiles."""
    L = finite_scalar(width, "Gaussian width")
    if L <= 0.0:
        raise ContractError("Gaussian width must be positive")
    pi32 = math.pi ** 1.5
    A = 0.5
    def j(power: float) -> float:
        return pi32 * L ** 3 * (2.0 / power) ** 1.5
    mediator_gradient = 0.5 * (3.0 / 2.0) * pi32 * L * A ** 2
    carrier_gradient = COEFFICIENTS["k_Cx"] * 1.5 * pi32 * L
    T = mediator_gradient + carrier_gradient
    mediator_potential = COEFFICIENTS["u_rho"] * (A ** 2 * j(2.0) - A ** 3 * j(3.0) + A ** 4 / 4.0 * j(4.0))
    carrier_quadratic = COEFFICIENTS["e_C"] * j(0.5)
    carrier_quadratic += -COEFFICIENTS["h_C"] * 2.0 * A * j(1.5)
    carrier_quadratic += COEFFICIENTS["h_C"] * A ** 2 * j(2.5)
    carrier_quartic = COEFFICIENTS["u_C"] / 2.0 * j(1.0)
    canonical_shift = j(0.5) / (4.0 * a)
    V = mediator_potential + carrier_quadratic + carrier_quartic + canonical_shift
    return finite_scalar(T, "Gaussian gradient energy"), finite_scalar(V, "Gaussian potential energy")


def build_row(index: int, a: float) -> dict[str, Any]:
    a = finite_scalar(a, f"a[{index}]")
    if a <= 0.0:
        raise ContractError(f"a[{index}] is not positive")
    b = COEFFICIENTS["e_C"] + 1.0 / (4.0 * a)
    depletion = COEFFICIENTS["h_C"] - b
    minimum_value = min(
        0.0,
        COEFFICIENTS["u_rho"] / 4.0 - max(depletion, 0.0) ** 2 / (2.0 * COEFFICIENTS["u_C"]),
    )
    mass2_depleted = 1.0 / (4.0 * a * a) + (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"]) / a
    factorization_max = 0.0
    for z in Z_VALUES:
        for n in N_VALUES:
            factorization_max = max(factorization_max, scaled_residual(potential(z, n, a), factorized_potential(z, n, a)))
    T, V = gaussian_integrals(1.0, a)
    energies = []
    for lam in LAMBDA_VALUES:
        direct_T, direct_V = gaussian_integrals(lam, a)
        direct_energy = direct_T + direct_V
        scaling_energy = lam * T + lam ** 3 * V
        if scaled_residual(direct_energy, scaling_energy) > SCALING_TOL:
            raise ContractError(f"Gaussian dilation scaling residual at row {index}, lambda={lam}")
        energies.append({"lambda": lam, "energy": direct_energy})
    witnesses = []
    for target in TARGET_CHARGES:
        witnesses.append(charge_witness(a, target, False))
        witnesses.append(charge_witness(a, target, True))
    return {
        "index": index,
        "a": a,
        "B": b,
        "depletion": depletion,
        "minimum_value": finite_scalar(minimum_value, f"minimum value[{index}]"),
        "mass2_depleted": finite_scalar(mass2_depleted, f"depleted mass squared[{index}]"),
        "factorization_max_scaled_residual": finite_scalar(factorization_max, f"factorization residual[{index}]"),
        "charge_witnesses": witnesses,
        "gaussian": {"gradient": T, "potential": V, "energies": energies},
    }


def check_row(row: dict[str, Any], failures: list[str]) -> None:
    index = row["index"]
    if row["factorization_max_scaled_residual"] > ALGEBRA_TOL:
        failures.append(f"factorization residual row {index}")
    for witness_index, witness in enumerate(row["charge_witnesses"]):
        if witness["shift_scaled_residual"] > ALGEBRA_TOL:
            failures.append(f"Hamiltonian shift residual row {index} witness {witness_index}")
        if witness["kinetic_scaled_residual"] > ALGEBRA_TOL:
            failures.append(f"kinetic bound residual row {index} witness {witness_index}")
        if witness["charge_scaled_residual"] > ALGEBRA_TOL:
            failures.append(f"charge residual row {index} witness {witness_index}")
    for key in ("a", "B", "depletion", "minimum_value", "mass2_depleted", "factorization_max_scaled_residual"):
        finite_scalar(row[key], f"row {index} {key}")
    gaussian = row["gaussian"]
    finite_scalar(gaussian["gradient"], f"row {index} Gaussian gradient")
    finite_scalar(gaussian["potential"], f"row {index} Gaussian potential")
    for energy in gaussian["energies"]:
        finite_scalar(energy["lambda"], f"row {index} Gaussian lambda")
        finite_scalar(energy["energy"], f"row {index} Gaussian energy")


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace receipt: {path}")
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def ensure_json_finite(value: Any, label: str = "receipt") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ContractError(f"{label} contains a non-finite number")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            ensure_json_finite(item, f"{label}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            ensure_json_finite(item, f"{label}[{index}]")
        return
    raise ContractError(f"{label} contains unsupported JSON type {type(value).__name__}")


def failure_receipt(output_dir: Path, error: BaseException) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        failed_path = output_dir / "failed.json"
        if failed_path.exists() or (output_dir / "results.json").exists():
            return
        payload = {
            "schema": SCHEMA,
            "verdict": "FAIL",
            "pass": False,
            "failures": [f"{type(error).__name__}: {error}"],
            "identities": {
                "primary": {"path": relative_path(Path(__file__)), "sha256": canonical_sha256(Path(__file__))},
                "verifier": {"path": relative_path(VERIFIER_PATH), "sha256": canonical_sha256(VERIFIER_PATH) if VERIFIER_PATH.is_file() else None},
                "preregistration": {"path": relative_path(PREREG_PATH), "sha256": canonical_sha256(PREREG_PATH) if PREREG_PATH.is_file() else None},
            },
        }
        write_json_exclusive(failed_path, payload)
    except Exception:
        pass


def run(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing nonempty output directory: {output_dir}")
    if not PREREG_PATH.is_file():
        raise FileNotFoundError(PREREG_PATH)
    if not VERIFIER_PATH.is_file():
        raise FileNotFoundError(VERIFIER_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = Path(__file__).resolve()
    identities = {
        "primary": {"path": relative_path(source_path), "sha256": canonical_sha256(source_path)},
        "verifier": {"path": relative_path(VERIFIER_PATH), "sha256": canonical_sha256(VERIFIER_PATH)},
        "preregistration": {"path": relative_path(PREREG_PATH), "sha256": canonical_sha256(PREREG_PATH)},
    }
    s = math.sqrt(COEFFICIENTS["u_rho"] * COEFFICIENTS["u_C"] / 2.0)
    thresholds = {
        "s": s,
        "a_depleted": 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"])),
        "a_vacuum": 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"] - s)),
    }
    for key, value in thresholds.items():
        finite_scalar(value, f"threshold {key}")
    rows = [build_row(index, a) for index, a in enumerate(A_VALUES)]
    failures: list[str] = []
    if len(rows) != 10 or [row["index"] for row in rows] != list(range(10)):
        failures.append("complete ten-row frozen schedule")
    for row in rows:
        check_row(row, failures)
    result = {
        "schema": SCHEMA,
        "coefficients": dict(COEFFICIENTS),
        "thresholds": thresholds,
        "identities": identities,
        "rows": rows,
        "failures": failures,
        "pass": not failures,
        "verdict": "PASS" if not failures else "FAIL",
    }
    ensure_json_finite(result)
    write_json_exclusive(output_dir / "results.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    output_dir = args.output_dir.resolve()
    try:
        result = run(output_dir)
    except KeyboardInterrupt:
        return 130
    except BaseException as error:
        failure_receipt(output_dir, error)
        print(json.dumps({"schema": SCHEMA, "verdict": "FAIL", "error": f"{type(error).__name__}: {error}"}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps({"schema": result["schema"], "output_dir": relative_path(output_dir), "verdict": result["verdict"], "pass": result["pass"]}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
