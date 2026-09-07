#!/usr/bin/env python3
"""Primary fixed autonomous-mediator linear-excitation calculation.

This program implements only the finite Fourier--Galerkin, elliptic-orbit, and
linear fundamental-matrix schedule frozen in report section 25.3.  It makes no
quantum, nonlinear, particle, or localization claim.
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
import scipy
from scipy import linalg, special
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "computations/matter-formation-continuum-report.md"
ACTION = ROOT / "foundations/particle-stationary-action-closure.md"
VERIFIER = ROOT / "computations/verify_matter_formation_autonomous_pump.py"
REVIEW_ROOT = ROOT / "runs/20260907_matter_formation_autonomous_pump_review"
PROTOCOL_HEADING = "### 25.3 Autonomous pump calculation: pre-execution criteria"
PROTOCOL_SHA256 = "4c2366c8b0ea8f096b866cff48d0792d6788d820f333be7a8747eb6251cc2648"
REVIEW_HASHES = {
    "ParentPumpMath.json": "7df30d02fa4abc533b342192edf09932e37b107b7669feb416976001d6a9e81d",
    "ParentPumpScope.json": "ea3830047b555e22f97e5db1d67ea12c8ffb74597bec3b7a119c78d3dcc6cc25",
}
SCHEMA = "cassi.matter-formation.autonomous-pump.v1"

# Frozen dimensionless coefficients and numerical schedule.
A = 1.0 / 16.0
C_PSI = 1.0 / 8.0
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
E_C = 0.75
H_C = 2.9598260763447164
M = 2.0 / 3.0
F = math.sqrt(3.0 / 2.0)
OMEGA = math.sqrt(24.0)
RTOL_ORBIT = 2.0e-12
ATOL_ORBIT = 2.0e-14
RTOL_MATRIX = 2.0e-12
ATOL_MATRIX = 2.0e-14
QUAL_TOL_EDGE = 2.0e-8
QUAL_TOL_DET = 1.0e-9
QUAL_TOL_MATRIX = 2.0e-8
QUAL_TOL_CONTROL_TRACE = 1.0e-9
QUAL_TOL_ORBIT = 1.0e-9
DIMENSIONS = (63, 127, 255)
N_SAMPLES = 1025
GAP_COUNT = 6


class ContractError(RuntimeError):
    """A prerequisite or frozen-contract violation."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def finite(value: Any) -> bool:
    try:
        return bool(np.all(np.isfinite(value)))
    except (TypeError, ValueError):
        return False


def json_safe(value: Any) -> Any:
    """Represent nonfinite values explicitly without invalid JSON or fake data."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, complex):
        return [json_safe(value.real), json_safe(value.imag)]
    return value


def dump_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(json_safe(value), stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def frozen_section(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(PROTOCOL_HEADING) != 1:
        raise ContractError("frozen autonomous-pump heading must occur exactly once")
    section = text[text.index(PROTOCOL_HEADING):]
    match = re.search(r"\n#{1,3} ", section)
    if match:
        section = section[:match.start()]
    return (section.rstrip() + "\n").encode("utf-8")


def initial_receipt() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "verdict": "INCONCLUSIVE",
        "passed": False,
        "qualified": False,
        "error": None,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "files": {},
        "protocol_sha256": PROTOCOL_SHA256,
        "review_hashes": dict(REVIEW_HASHES),
        "gaps": [],
        "witnesses": [],
        "orbit": {},
        "spectral": {},
    }


def source_stage(out: Path, report: Path) -> dict[str, str]:
    """Validate and snapshot every frozen/evidence input before numerical work."""
    if not report.is_file():
        raise ContractError(f"missing report: {report}")
    if not ACTION.is_file():
        raise ContractError(f"missing source action: {ACTION}")
    if not VERIFIER.is_file():
        raise ContractError(f"missing verifier source: {VERIFIER}")
    verifier_raw = VERIFIER.read_bytes()
    protocol = frozen_section(report)
    if sha256(protocol) != PROTOCOL_SHA256:
        raise ContractError("frozen protocol hash mismatch")
    review_bytes: dict[str, bytes] = {}
    for name, expected in REVIEW_HASHES.items():
        path = REVIEW_ROOT / name
        if not path.is_file():
            raise ContractError(f"missing analytical review: {name}")
        data = path.read_bytes()
        if sha256(data) != expected:
            raise ContractError(f"analytical review hash mismatch: {name}")
        try:
            json.loads(data)
        except json.JSONDecodeError as exc:
            raise ContractError(f"invalid analytical review JSON: {name}") from exc
        review_bytes[name] = data
    out.mkdir(parents=True)
    retained: dict[str, str] = {}

    def retain(name: str, data: bytes) -> None:
        target = out / name
        with target.open("xb") as handle:
            handle.write(data)
        retained[name] = sha256(data)

    retain("source_primary.py", Path(__file__).read_bytes())
    retain("source_verifier.py", verifier_raw)
    retain("frozen_protocol.txt", protocol)
    retain("source_action.txt", ACTION.read_bytes())
    for name, data in review_bytes.items():
        retain(name, data)
    return retained


def orbit_arrays(K: float, P: float) -> tuple[dict[str, np.ndarray], dict[str, Any], list[str]]:
    t = np.linspace(0.0, P, N_SAMPLES, dtype=np.float64)
    u = OMEGA * t
    sn, cn, dn, _amplitude = special.ellipj(u, M)
    f_exact = F * dn
    ft_exact = -F * M * OMEGA * sn * cn
    exact = np.column_stack((f_exact, ft_exact)).astype(np.float64)
    numeric = np.full_like(exact, np.nan)
    errors: list[str] = []
    try:
        def rhs(_t: float, y: np.ndarray) -> np.ndarray:
            return np.array([y[1], -(U_RHO / C_PSI) * (y[0] * y[0] - 1.0) * y[0]], dtype=np.float64)

        sol = solve_ivp(rhs, (0.0, P), [F, 0.0], method="DOP853", t_eval=t,
                        rtol=RTOL_ORBIT, atol=ATOL_ORBIT)
        count = min(sol.y.shape[1], N_SAMPLES)
        numeric[:count, :] = sol.y[:, :count].T
        if not sol.success or count != N_SAMPLES:
            errors.append(f"orbit solve failed: {sol.message}")
    except Exception as exc:  # preserve partial numerical result and continue schedule
        errors.append(f"orbit solve {type(exc).__name__}: {exc}")
    energy = C_PSI / 2.0 * numeric[:, 1] ** 2 + U_RHO / 4.0 * (numeric[:, 0] ** 2 - 1.0) ** 2
    denom = max(1.0, float(np.max(np.abs(exact[:, 1]))))
    if finite(numeric):
        field_error = float(np.max(np.abs(numeric[:, 0] - exact[:, 0])) / denom)
        velocity_error = float(np.max(np.abs(numeric[:, 1] - exact[:, 1])) / denom)
    else:
        field_error = float("nan")
        velocity_error = float("nan")
    drift = float(np.max(np.abs(energy - 0.25))) if finite(energy) else float("nan")
    orbit = {
        "period": float(P),
        "samples": N_SAMPLES,
        "field_error": field_error,
        "velocity_error": velocity_error,
        "max_normalized_field_error": field_error,
        "max_normalized_velocity_error": velocity_error,
        "energy_density_drift": drift,
        "absolute_energy_density_drift": drift,
        "passed": bool(finite(numeric) and field_error < QUAL_TOL_ORBIT and velocity_error < QUAL_TOL_ORBIT and drift < QUAL_TOL_ORBIT),
        "errors": errors,
    }
    arrays = {"orbit_t": t, "orbit_exact": exact, "orbit_numeric": numeric, "orbit_energy": energy}
    return arrays, orbit, errors


def primary_spectrum(K: float) -> tuple[dict[str, np.ndarray], dict[str, Any], list[str]]:
    eigenvalues = np.full((3, 2, 7), np.nan, dtype=np.float64)
    edges = np.full((3, GAP_COUNT, 2), np.nan, dtype=np.float64)
    arrays: dict[str, np.ndarray] = {"eigenvalues": eigenvalues, "edges": edges}
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for d_index, N in enumerate(DIMENSIONS):
        sample_count = 8 * N
        u_nodes = np.arange(sample_count, dtype=np.float64) * (2.0 * K / sample_count)
        sn, _cn, _dn, _amplitude = special.ellipj(u_nodes, M)
        potential = H_C * M * sn * sn
        fourier = np.fft.fft(potential) / sample_count
        arrays[f"u_n{N}"] = u_nodes
        arrays[f"potential_n{N}"] = potential
        arrays[f"fourier_n{N}"] = fourier.astype(np.complex128)
        for beta_index, beta in enumerate((0.0, 0.5)):
            n = np.arange(-(N // 2), N // 2 + 1, dtype=np.int64)
            diff = n[:, None] - n[None, :]
            matrix = fourier[np.mod(diff, sample_count)]
            matrix = np.asarray(matrix, dtype=np.complex128)
            diagonal = (2.0 * math.pi * (n.astype(np.float64) + beta) / (2.0 * K)) ** 2
            matrix = matrix + np.diag(diagonal)
            row: dict[str, Any] = {"dimension": N, "beta": beta, "status": "attempted"}
            try:
                values = linalg.eigh(matrix, subset_by_index=(0, 6), check_finite=True, eigvals_only=True)
                values = np.asarray(values, dtype=np.float64)
                eigenvalues[d_index, beta_index, :] = values
                row["eigenvalues"] = values.tolist()
                row["passed"] = bool(finite(values) and values.size == 7 and np.all(np.diff(values) >= -1.0e-12))
                if not row["passed"]:
                    errors.append(f"nonfinite or unsorted eigenvalues N={N} beta={beta}")
            except Exception as exc:
                row["passed"] = False
                row["error"] = f"{type(exc).__name__}: {exc}"
                errors.append(f"eigensolve N={N} beta={beta}: {exc}")
            rows.append(row)
    for d_index in range(3):
        for j in range(1, GAP_COUNT + 1):
            beta_index = 1 if j % 2 else 0
            lo = eigenvalues[d_index, beta_index, j - 1]
            hi = eigenvalues[d_index, beta_index, j]
            edges[d_index, j - 1, :] = (lo, hi)
    edge_change_63_127 = float(np.max(np.abs(edges[1] - edges[0])))
    edge_change_127_255 = float(np.max(np.abs(edges[2] - edges[1])))
    spectral = {
        "dimensions": list(DIMENSIONS),
        "rows": rows,
        "edge_change_63_127": edge_change_63_127,
        "edge_change_127_255": edge_change_127_255,
        "passed": bool(all(bool(row.get("passed")) for row in rows) and finite(edges) and
                        edge_change_63_127 < QUAL_TOL_EDGE and edge_change_127_255 < QUAL_TOL_EDGE),
        "errors": errors,
    }
    return arrays, spectral, errors


def gap_rows(edges: np.ndarray, K: float, lambda0: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for j in range(1, GAP_COUNT + 1):
        lo, hi = (float(edges[j - 1, 0]), float(edges[j - 1, 1]))
        width = hi - lo
        midpoint = 0.5 * (lo + hi)
        accessible = bool(math.isfinite(midpoint) and midpoint >= lambda0)
        retained = bool(accessible and math.isfinite(width) and width >= 1.0e-5)
        reason = "retained" if retained else ("inaccessible" if not accessible else "narrow")
        rows.append({
            "j": j, "edges": [lo, hi], "width": width, "midpoint": midpoint,
            "accessible": accessible, "retained": retained,
            "k": math.sqrt(3.0 * (midpoint - lambda0)) if accessible else None,
            "reason": reason,
        })
    return rows


def matrix_for(k: float, P: float, t: np.ndarray, mode: str) -> tuple[np.ndarray, str | None]:
    matrix = np.full((N_SAMPLES, 2, 2), np.nan, dtype=np.float64)
    try:
        def rhs(time: float, state: np.ndarray) -> np.ndarray:
            Mx = state.reshape(2, 2)
            if mode == "pump":
                _sn, _cn, dn, _amplitude = special.ellipj(OMEGA * time, M)
                f0 = F * dn
                omega2 = 8.0 * k * k + 64.0 + 16.0 * (0.75 - H_C + H_C * f0 * f0)
            elif mode == "constant_mediator":
                omega2 = 8.0 * k * k + 64.0 + 16.0 * (0.75 - H_C + H_C)
            elif mode == "disabled_coupling":
                omega2 = 8.0 * k * k + 64.0 + 16.0 * 0.75
            else:
                raise ValueError(f"unknown matrix mode {mode}")
            return (np.array([[0.0, 1.0], [-omega2, 0.0]]) @ Mx).ravel()

        sol = solve_ivp(rhs, (0.0, P), np.eye(2, dtype=np.float64).ravel(),
                        method="DOP853", t_eval=t, rtol=RTOL_MATRIX, atol=ATOL_MATRIX)
        count = min(sol.y.shape[1], N_SAMPLES)
        matrix[:count] = sol.y[:, :count].T.reshape(count, 2, 2)
        if not sol.success or count != N_SAMPLES:
            return matrix, f"{mode} solve failed: {sol.message}"
        return matrix, None
    except Exception as exc:
        return matrix, f"{mode} solve {type(exc).__name__}: {exc}"


def witnesses(gaps: list[dict[str, Any]], K: float, P: float, t: np.ndarray,
              arrays: dict[str, np.ndarray]) -> tuple[list[dict[str, Any]], np.ndarray, list[str]]:
    retained = [row for row in gaps if row["retained"]]
    fundamental = np.full((len(retained), 3, N_SAMPLES, 2, 2), np.nan, dtype=np.float64)
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for wi, gap in enumerate(retained):
        k = float(gap["k"])
        row: dict[str, Any] = {"j": gap["j"], "k": k, "trace": float("nan"),
                               "determinant": float("nan"), "excess": float("nan"),
                               "mu": float("nan"), "unstable": False, "controls": []}
        matrices: dict[str, np.ndarray] = {}
        for mode in ("pump", "constant_mediator", "disabled_coupling"):
            mat, error = matrix_for(k, P, t, mode)
            matrices[mode] = mat
            mode_index = ("pump", "constant_mediator", "disabled_coupling").index(mode)
            fundamental[wi, mode_index] = mat
            if error:
                errors.append(f"j={gap['j']} {error}")
        pump = matrices["pump"]
        if finite(pump):
            final = pump[-1]
            trace = float(np.trace(final))
            determinant = float(np.linalg.det(final))
            excess = abs(trace) - 2.0
            mu = (math.acosh(abs(trace) / 2.0) / P) if abs(trace) > 2.0 else 0.0
            row.update(trace=trace, determinant=determinant, excess=excess, mu=mu,
                       unstable=bool(excess > 1.0e-8))
        else:
            errors.append(f"j={gap['j']} nonfinite pump matrix")
        controls: list[dict[str, Any]] = []
        for mode in ("constant_mediator", "disabled_coupling"):
            mat = matrices[mode]
            if finite(mat):
                final = mat[-1]
                tr = float(np.trace(final))
                det = float(np.linalg.det(final))
                det_error = abs(det - 1.0)
                passed = bool(abs(tr) <= 2.0 + QUAL_TOL_CONTROL_TRACE and det_error < QUAL_TOL_DET)
                controls.append({"name": mode, "trace": tr, "determinant": det,
                                 "determinant_error": det_error, "passed": passed})
            else:
                controls.append({"name": mode, "trace": float("nan"), "determinant": float("nan"),
                                 "determinant_error": float("nan"), "passed": False})
        row["controls"] = controls
        row["determinant_error"] = abs(row["determinant"] - 1.0) if math.isfinite(row["determinant"]) else float("nan")
        row["passed"] = bool(finite(pump) and math.isfinite(row["determinant_error"]) and
                             row["determinant_error"] < QUAL_TOL_DET and all(c["passed"] for c in controls))
        rows.append(row)
    arrays["witness_gaps"] = np.asarray([r["j"] for r in retained], dtype=np.int64)
    arrays["witness_k"] = np.asarray([r["k"] for r in retained], dtype=np.float64)
    arrays["fundamental_t"] = t
    arrays["fundamental"] = fundamental
    return rows, fundamental, errors


def blank_arrays(K: float, P: float) -> dict[str, np.ndarray]:
    """Allocate the complete raw-array schema before any numerical attempt."""
    t = np.linspace(0.0, P, N_SAMPLES, dtype=np.float64)
    arrays: dict[str, np.ndarray] = {
        "orbit_t": t,
        "orbit_exact": np.full((N_SAMPLES, 2), np.nan, dtype=np.float64),
        "orbit_numeric": np.full((N_SAMPLES, 2), np.nan, dtype=np.float64),
        "orbit_energy": np.full(N_SAMPLES, np.nan, dtype=np.float64),
        "edges": np.full((3, GAP_COUNT, 2), np.nan, dtype=np.float64),
        "eigenvalues": np.full((3, 2, 7), np.nan, dtype=np.float64),
        "witness_gaps": np.empty(0, dtype=np.int64),
        "witness_k": np.empty(0, dtype=np.float64),
        "fundamental_t": t,
        "fundamental": np.full((0, 3, N_SAMPLES, 2, 2), np.nan, dtype=np.float64),
    }
    for N in DIMENSIONS:
        count = 8 * N
        arrays[f"u_n{N}"] = np.arange(count, dtype=np.float64) * (2.0 * K / count)
        arrays[f"potential_n{N}"] = np.full(count, np.nan, dtype=np.float64)
        arrays[f"fourier_n{N}"] = np.full(count, np.nan + 1.0j * np.nan, dtype=np.complex128)
    return arrays


def save_arrays(out: Path, arrays: dict[str, np.ndarray]) -> str:
    target = out / "arrays.npz"
    with target.open("xb") as handle:
        np.savez(handle, **arrays)
    return sha256(target.read_bytes())


def run(output: Path, report: Path) -> int:
    if output.exists():
        raise ContractError("output directory must be absent before invocation")
    receipt = initial_receipt()
    arrays: dict[str, np.ndarray] | None = None
    try:
        retained = source_stage(output, report)
        receipt["files"].update(retained)
        K = float(special.ellipk(M))
        P = 2.0 * K / OMEGA
        arrays = blank_arrays(K, P)
        lambda0 = 1.0 / (6.0 * A) + 0.5 + H_C / 3.0
        orbit_arrays_result, orbit, errors = orbit_arrays(K, P)
        arrays.update(orbit_arrays_result)
        receipt["orbit"] = orbit
        spectral_arrays, spectral, spectral_errors = primary_spectrum(K)
        arrays.update(spectral_arrays)
        receipt["spectral"] = spectral
        gaps = gap_rows(spectral_arrays["edges"][2], K, lambda0)
        receipt["gaps"] = gaps
        t = arrays["orbit_t"]
        witness_rows, _fundamental, witness_errors = witnesses(gaps, K, P, t, arrays)
        receipt["witnesses"] = witness_rows
        all_errors = errors + spectral_errors + witness_errors
        arrays["fundamental_t"] = t
        array_hash = save_arrays(output, arrays)
        receipt["files"]["arrays.npz"] = array_hash
        all_rows = len(gaps) == GAP_COUNT and all("j" in g for g in gaps)
        all_finite = all(finite(value) for value in arrays.values())
        witness_qualification = all(bool(row.get("passed")) for row in witness_rows)
        numerical_ok = bool(receipt["orbit"].get("passed") and spectral.get("passed") and all_rows and
                             all_finite and witness_qualification and not all_errors)
        receipt["qualified"] = numerical_ok
        unstable = any(bool(row.get("unstable")) for row in witness_rows)
        if numerical_ok and unstable:
            receipt["verdict"] = "SUPPORTS—neutral linear parametric amplification in the supplied temporal parent"
            receipt["passed"] = True
        elif numerical_ok:
            receipt["verdict"] = "INCONCLUSIVE—no resolved unstable witness in the fixed gap schedule"
        else:
            receipt["verdict"] = "INCONCLUSIVE"
        if all_errors:
            receipt["error"] = "; ".join(all_errors)
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        receipt["verdict"] = "INCONCLUSIVE"
        receipt["passed"] = False
        receipt["qualified"] = False
        if arrays is not None and output.exists() and not (output / "arrays.npz").exists():
            try:
                receipt["files"]["arrays.npz"] = save_arrays(output, arrays)
            except Exception as save_exc:
                receipt["error"] += f"; array preservation {type(save_exc).__name__}: {save_exc}"
    # A prerequisite failure has no numerical scientific payload.  The output
    # directory is created only by source_stage, so this also handles missing
    # prerequisites before that stage without fabricating arrays.
    if not output.exists():
        output.mkdir(parents=True, exist_ok=False)
    dump_json(output / "results.json", receipt)
    print(json.dumps({"verdict": receipt["verdict"], "qualified": receipt["qualified"],
                      "witnesses": len(receipt["witnesses"]), "error": receipt["error"]},
                     ensure_ascii=False, allow_nan=False))
    return 0 if receipt["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--record", type=Path, default=REPORT)
    args = parser.parse_args()
    try:
        return run(args.output_dir.resolve(), args.record.resolve())
    except Exception as exc:
        # Refuse all writes into a pre-existing directory.  For a fresh path,
        # retain a non-scientific failure receipt with the contract shape.
        output = args.output_dir.resolve()
        if output.exists():
            return 1
        output.mkdir(parents=True, exist_ok=False)
        receipt = initial_receipt()
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        dump_json(output / "results.json", receipt)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
