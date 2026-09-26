#!/usr/bin/env python3
"""Primary frozen spatial-mediator Floquet calculation.

The calculation is deliberately limited to the Fourier--Galerkin edge map and
five linear fundamental matrices specified by report section 27.3.  It makes
no nonlinear, quantum, localization, or particle-identification claim.
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
REPORT = ROOT / "computations" / "matter-formation-continuum-report.md"
ACTION = ROOT / "foundations" / "particle-stationary-action-closure.md"
VERIFIER = ROOT / "computations" / "verify_matter_formation_spatial_pump.py"
PARENT_PRIMARY = ROOT / "runs" / "20260907_matter_formation_autonomous_pump"
PARENT_VERIFICATION = ROOT / "runs" / "20260907_matter_formation_autonomous_pump_verification"
HEADING = "### 27.3 Spatial perturbation calculation: pre-execution criteria"
PROTOCOL_SHA256 = "244024bc6bc7a4822c9173dafc726ed0c152594ddbbdb5c43579c527bce0bdfd"
RECOVERY_HEADING = "### 27.4 Prerequisite identity recovery"
RECOVERY_SHA256 = "7ac1f1ed3375f4cb3607ed17114ae852d82a1a2a555b5d46cbf2222750bbd820"
ACTION_SHA256 = "f0314b16d07bfa3f8839a3e1e131ed7e0e1412719c296095db8a419f832d5c93"
PARENT_PRIMARY_SHA256 = "cad33ef760404c79807570be1269390dfb790574dc13bfe60d61d67c5b1bc9c5"
PARENT_VERIFICATION_SHA256 = "a54c07d1a973f9a915355e26b7c23e7caa7ee75a468f09fda53e13a272959758"
SCHEMA = "cassi.matter-formation.spatial-pump.v1"

M = 2.0 / 3.0
F = math.sqrt(3.0 / 2.0)
OMEGA = math.sqrt(24.0)
C_PSI = 1.0 / 8.0
U_RHO = 4.0
DIMENSIONS = (63, 127, 255)
N_SAMPLES = 1025
RTOL = 2.0e-12
ATOL = 2.0e-14
EDGE_TOL = 2.0e-8
DET_TOL = 1.0e-9
MATRIX_TOL = 2.0e-8
ENDPOINT_TOL = 1.0e-8
CONTROL_TRACE_TOL = 1.0e-9


class ContractError(RuntimeError):
    """A prerequisite or frozen-contract violation."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def finite(value: Any) -> bool:
    try:
        return bool(np.all(np.isfinite(value)))
    except (TypeError, ValueError):
        return False


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return safe(value.tolist())
    if isinstance(value, np.generic):
        return safe(value.item())
    if isinstance(value, complex):
        return [safe(value.real), safe(value.imag)]
    if isinstance(value, (float, np.floating)):
        x = float(value)
        return x if math.isfinite(x) else None
    return value


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(safe(payload), stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def protocol_section(path: Path, heading: str = HEADING) -> bytes:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(heading) != 1:
        raise ContractError(f"frozen heading must occur exactly once: {heading}")
    start = text.index(heading)
    section = text[start:]
    match = re.search(r"\n#{1,3} ", section)
    if match:
        section = section[:match.start()]
    return (section.rstrip() + "\n").encode("utf-8")


def strict_parent(path: Path, expected_hash: str, expected_schema: str) -> tuple[bytes, dict[str, Any]]:
    if not path.is_file():
        raise ContractError(f"missing accepted parent receipt: {path}")
    raw = path.read_bytes()
    if sha256(raw) != expected_hash:
        raise ContractError(f"accepted parent receipt hash mismatch: {path}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid accepted parent receipt: {path}") from exc
    if not isinstance(data, dict) or data.get("schema") != expected_schema:
        raise ContractError(f"accepted parent schema mismatch: {path}")
    if data.get("passed") is not True or data.get("qualified") is not True:
        raise ContractError(f"accepted parent is not passed and qualified: {path}")
    witnesses = data.get("witnesses")
    if not isinstance(witnesses, list):
        raise ContractError(f"accepted parent witness list missing: {path}")
    qualified = [row for row in witnesses if isinstance(row, dict) and row.get("unstable") is True and row.get("passed") is True]
    if len(qualified) != 1:
        raise ContractError(f"accepted parent does not have one unstable passed witness: {path}")
    if not finite(float(qualified[0].get("k"))) or not finite(float(qualified[0].get("mu"))):
        raise ContractError(f"accepted parent witness is nonfinite: {path}")
    return raw, data


def initial_receipt() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "passed": False,
        "qualified": False,
        "verdict": "INCONCLUSIVE",
        "error": None,
        "protocol_sha256": PROTOCOL_SHA256,
        "files": {},
        "parameters": {},
        "arms": [],
        "symbolic": {},
        "checks": {},
        "diagnostics": {},
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
    }


def source_stage(out: Path, report: Path, pump: Path, pump_verification: Path) -> tuple[dict[str, str], dict[str, Any], dict[str, Any]]:
    """Validate all immutable inputs before creating scientific output."""
    if not report.is_file():
        raise ContractError(f"missing report: {report}")
    if not ACTION.is_file():
        raise ContractError(f"missing source action: {ACTION}")
    if not VERIFIER.is_file():
        raise ContractError(f"missing verifier source: {VERIFIER}")
    protocol = protocol_section(report)
    if sha256(protocol) != PROTOCOL_SHA256:
        raise ContractError("frozen spatial-pump protocol hash mismatch")
    recovery = protocol_section(report, RECOVERY_HEADING)
    if sha256(recovery) != RECOVERY_SHA256:
        raise ContractError("frozen prerequisite recovery hash mismatch")
    action = ACTION.read_bytes()
    if sha256(action) != ACTION_SHA256:
        raise ContractError("source action hash mismatch")
    primary_raw, primary = strict_parent(pump / "results.json", PARENT_PRIMARY_SHA256, "cassi.matter-formation.autonomous-pump.v1")
    verification_raw, verification = strict_parent(pump_verification / "results.json", PARENT_VERIFICATION_SHA256, "cassi.matter-formation.autonomous-pump-verification.v1")
    pw = next(row for row in primary["witnesses"] if row.get("unstable") is True and row.get("passed") is True)
    vw = next(row for row in verification["witnesses"] if row.get("unstable") is True and row.get("passed") is True)
    if abs(float(pw["k"]) - float(vw["k"])) >= 1.0e-10:
        raise ContractError("accepted parent witness wave numbers disagree")
    values = {"k": float(pw["k"]), "carrier_mu_primary": float(pw["mu"]), "carrier_mu_verification": float(vw["mu"])}
    retained_data = {
        "source_primary.py": Path(__file__).read_bytes(),
        "source_verifier.py": VERIFIER.read_bytes(),
        "source_action.txt": action,
        "frozen_protocol.txt": protocol,
        "frozen_recovery.txt": recovery,
        "parent_primary_results.json": primary_raw,
        "parent_verification_results.json": verification_raw,
    }
    out.mkdir(parents=True, exist_ok=False)
    files: dict[str, str] = {}
    for name, data in retained_data.items():
        with (out / name).open("xb") as stream:
            stream.write(data)
        files[name] = sha256(data)
    return files, values, {"primary": primary, "verification": verification}


def exact_edges() -> np.ndarray:
    d = math.sqrt(1.0 - M + M * M)
    return np.asarray((2.0 * (1.0 + M) - 2.0 * d, 1.0 + M, 1.0 + 4.0 * M, 4.0 + M, 2.0 * (1.0 + M) + 2.0 * d), dtype=np.float64)


def blank_arrays(K: float) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {
        "t": np.linspace(0.0, 2.0 * K / OMEGA, N_SAMPLES, dtype=np.float64),
        "p": np.full(5, np.nan, dtype=np.float64),
        "matrices": np.full((5, N_SAMPLES, 2, 2), np.nan, dtype=np.float64),
        "basis_sizes": np.asarray(DIMENSIONS, dtype=np.int64),
        "edges": np.full((3, 5), np.nan, dtype=np.float64),
    }
    for n in DIMENSIONS:
        count = 8 * n
        arrays[f"u_n{n}"] = np.arange(count, dtype=np.float64) * (2.0 * K / count)
        arrays[f"potential_n{n}"] = np.full(count, np.nan, dtype=np.float64)
        arrays[f"fourier_n{n}"] = np.full(count, np.nan + 1j * np.nan, dtype=np.complex128)
    return arrays


def spectrum(K: float, arrays: dict[str, np.ndarray]) -> tuple[np.ndarray, list[str]]:
    edges = np.full((3, 5), np.nan, dtype=np.float64)
    errors: list[str] = []
    # The edge order is P0,A0,A1,P1,P2.  The full lowest-seven lists are
    # computed in each boundary basis so that this ordering is not inferred
    # from a wave-number or parameter search.
    for di, n_dim in enumerate(DIMENSIONS):
        sample_count = 8 * n_dim
        u_nodes = arrays[f"u_n{n_dim}"]
        try:
            sn, _cn, _dn, _ = special.ellipj(u_nodes, M)
            potential = 4.0 * sn * sn
            fourier = np.fft.fft(potential) / sample_count
            arrays[f"potential_n{n_dim}"] = np.asarray(potential, dtype=np.float64)
            arrays[f"fourier_n{n_dim}"] = np.asarray(fourier, dtype=np.complex128)
            eigen: dict[float, np.ndarray] = {}
            n = np.arange(-(n_dim // 2), n_dim // 2 + 1, dtype=np.int64)
            difference = n[:, None] - n[None, :]
            for beta in (0.0, 0.5):
                matrix = np.asarray(fourier[np.mod(difference, sample_count)], dtype=np.complex128)
                diagonal = (2.0 * math.pi * (n.astype(np.float64) + beta) / (2.0 * K)) ** 2
                matrix = matrix + np.diag(diagonal)
                values = np.asarray(linalg.eigh(matrix, subset_by_index=(0, 6), eigvals_only=True, check_finite=True), dtype=np.float64)
                eigen[beta] = values
            edges[di] = (eigen[0.0][0], eigen[0.5][0], eigen[0.5][1], eigen[0.0][1], eigen[0.0][2])
        except Exception as exc:
            errors.append(f"Galerkin N={n_dim} {type(exc).__name__}: {exc}")
    return edges, errors


def integrate_arm(p: float, t: np.ndarray, K: float, equilibrium: bool = False) -> tuple[np.ndarray, str | None]:
    matrix = np.full((N_SAMPLES, 2, 2), np.nan, dtype=np.float64)
    u_eval = OMEGA * t
    try:
        if equilibrium:
            q = (p * p + 8.0) / 3.0
        def rhs(_u: float, state: np.ndarray) -> np.ndarray:
            if equilibrium:
                coefficient = q
            else:
                sn, _cn, _dn, _ = special.ellipj(_u, M)
                coefficient = (14.0 + p * p) / 3.0 - 4.0 * sn * sn
            local = state.reshape(2, 2)
            return (np.asarray([[0.0, 1.0], [-coefficient, 0.0]], dtype=np.float64) @ local).ravel()
        solution = solve_ivp(rhs, (0.0, 2.0 * K), np.eye(2, dtype=np.float64).ravel(), method="DOP853", t_eval=u_eval, rtol=RTOL, atol=ATOL, max_step=2.0 * K / 128.0)
        count = min(solution.y.shape[1], N_SAMPLES)
        mu_matrices = solution.y[:, :count].T.reshape(count, 2, 2)
        # diag(1,Omega) M_u diag(1,1/Omega), in physical (eta,eta_dot) coordinates.
        matrix[:count] = mu_matrices * np.asarray([[1.0, 1.0 / OMEGA], [OMEGA, 1.0]], dtype=np.float64)
        if not solution.success or count != N_SAMPLES:
            return matrix, f"solve failed: {solution.message}"
        return matrix, None
    except Exception as exc:
        return matrix, f"solve {type(exc).__name__}: {exc}"


def analytic_equilibrium(t: np.ndarray, p: float) -> np.ndarray:
    w = math.sqrt((p * p + 8.0) / C_PSI)
    values = np.zeros((t.size, 2, 2), dtype=np.float64)
    angle = w * t
    values[:, 0, 0] = np.cos(angle)
    values[:, 0, 1] = np.sin(angle) / w
    values[:, 1, 0] = -w * np.sin(angle)
    values[:, 1, 1] = np.cos(angle)
    return values


def arm_record(name: str, p: float, matrix: np.ndarray, error: str | None, equilibrium: bool, t: np.ndarray) -> dict[str, Any]:
    metrics: dict[str, Any] = {"trace": float("nan"), "determinant": float("nan"), "determinant_error": float("nan"), "excess": float("nan"), "mu": float("nan"), "hundredfold_time": None}
    if finite(matrix):
        traces = np.trace(matrix, axis1=1, axis2=2)
        determinants = np.linalg.det(matrix)
        endpoint_trace = float(traces[-1])
        det = float(determinants[-1])
        det_error = float(np.max(np.abs(determinants - 1.0)))
        excess = abs(endpoint_trace) - 2.0
        mu = math.acosh(abs(endpoint_trace) / 2.0) / float(t[-1]) if abs(endpoint_trace) > 2.0 else 0.0
        metrics.update(trace=endpoint_trace, determinant=det, determinant_error=det_error, excess=excess, mu=mu, hundredfold_time=(math.log(100.0) / mu if mu > 0.0 else None))
        if equilibrium:
            metrics["equilibrium_error"] = float(np.max(np.abs(matrix - analytic_equilibrium(t, p))) / max(1.0, float(np.max(np.abs(analytic_equilibrium(t, p))))))
    else:
        metrics["equilibrium_error"] = float("nan") if equilibrium else None
    success = bool(finite(matrix) and math.isfinite(float(metrics["determinant_error"])) and float(metrics["determinant_error"]) < DET_TOL)
    return {"name": name, "p": float(p), "success": success, "metrics": metrics, "error": error}


def save_arrays(out: Path, arrays: dict[str, np.ndarray]) -> str:
    target = out / "arrays.npz"
    with target.open("xb") as stream:
        np.savez(stream, **arrays)
    return sha256(target.read_bytes())


def run(output: Path, report: Path, pump: Path, pump_verification: Path) -> int:
    if output.exists():
        raise ContractError("output directory must be absent before invocation")
    receipt = initial_receipt()
    arrays: dict[str, np.ndarray] | None = None
    try:
        files, parent_values, parents = source_stage(output, report, pump, pump_verification)
        receipt["files"].update(files)
        K = float(special.ellipk(M))
        P = 2.0 * K / OMEGA
        k = parent_values["k"]
        pc = math.sqrt(2.0 * math.sqrt(7.0) - 4.0)
        pstar = k / 4.0
        p_values = np.asarray((0.0, pc, pstar, 2.0 * pc, pstar), dtype=np.float64)
        arrays = blank_arrays(K)
        arrays["p"] = p_values
        edge_values, edge_errors = spectrum(K, arrays)
        arrays["edges"] = edge_values
        exact = exact_edges()
        edge_change = float(np.max(np.abs(edge_values[1:] - edge_values[:-1]))) if finite(edge_values) else float("nan")
        exact_edge_error = float(np.max(np.abs(edge_values - exact[None, :]))) if finite(edge_values) else float("nan")
        names = ("zero_mode", "critical_edge", "spatial_witness", "high_wave_control", "equilibrium_control")
        arms: list[dict[str, Any]] = []
        arm_errors = list(edge_errors)
        for index, (name, p) in enumerate(zip(names, p_values)):
            matrix, arm_error = integrate_arm(float(p), arrays["t"], K, equilibrium=(index == 4))
            arrays["matrices"][index] = matrix
            if arm_error:
                arm_errors.append(f"{name}: {arm_error}")
            arms.append(arm_record(name, float(p), matrix, arm_error, index == 4, arrays["t"]))
        receipt["parameters"] = {
            "m": M, "Omega": OMEGA, "P": P, "K": K, "F": F, "cPsi": C_PSI, "uRho": U_RHO,
            "pc": pc, "pstar": pstar, "k": k, "carrier_mu": parent_values["carrier_mu_primary"],
            "carrier_mu_primary": parent_values["carrier_mu_primary"], "carrier_mu_verification": parent_values["carrier_mu_verification"],
            "critical_length": 2.0 * math.pi / pc, "original_length": 2.0 * math.pi / k, "extended_length": 8.0 * math.pi / k,
            "basis_sizes": list(DIMENSIONS), "sample_count": N_SAMPLES,
        }
        receipt["arms"] = arms
        matrices = arrays["matrices"]
        finite_matrices = finite(matrices)
        endpoint_ok = bool(len(arms) == 5 and all(abs(float(row["metrics"]["trace"]) - 2.0) < ENDPOINT_TOL for row in arms[:2])) if finite_matrices else False
        controls_ok = bool(len(arms) == 5 and all(abs(float(arms[i]["metrics"]["trace"])) <= 2.0 + CONTROL_TRACE_TOL for i in (3, 4))) if finite_matrices else False
        equilibrium_ok = bool(finite_matrices and float(arms[4]["metrics"].get("equilibrium_error", math.inf)) < MATRIX_TOL)
        witness_excess = float(arms[2]["metrics"]["excess"])
        witness_ok = bool(math.isfinite(witness_excess) and witness_excess > 1.0e-8)
        determinant_ok = bool(all(row["success"] for row in arms))
        finite_arrays = bool(all(finite(value) for value in arrays.values()))
        edge_ok = bool(finite(edge_values) and edge_change < EDGE_TOL and exact_edge_error < EDGE_TOL)
        primary_ok = bool(not arm_errors and finite_arrays and edge_ok and determinant_ok and endpoint_ok and controls_ok and equilibrium_ok and witness_ok)
        witness_mu = float(arms[2]["metrics"]["mu"])
        ratio_primary = witness_mu / parent_values["carrier_mu_primary"] if parent_values["carrier_mu_primary"] > 0.0 else float("nan")
        ratio_verification = witness_mu / parent_values["carrier_mu_verification"] if parent_values["carrier_mu_verification"] > 0.0 else float("nan")
        receipt["checks"] = {
            "prerequisites": True, "protocol": True, "parents": True, "finite_arrays": finite_arrays,
            "edge_convergence": bool(finite(edge_values) and edge_change < EDGE_TOL), "exact_edges": bool(finite(edge_values) and exact_edge_error < EDGE_TOL),
            "matrices_present": bool(finite_matrices), "determinant": determinant_ok, "endpoint_traces": endpoint_ok,
            "controls": controls_ok, "equilibrium": equilibrium_ok, "spatial_witness": witness_ok, "all_qualifications": primary_ok,
        }
        receipt["diagnostics"] = {
            "exact_edges": exact.tolist(), "edge_change": edge_change, "exact_edge_error": exact_edge_error,
            "equilibrium_error": arms[4]["metrics"].get("equilibrium_error"), "witness_carrier_ratio": ratio_primary,
            "witness_carrier_ratio_verification": ratio_verification, "tenfold_faster": bool(ratio_primary > 10.0 and ratio_verification > 10.0),
            "carrier_mu_primary": parent_values["carrier_mu_primary"], "carrier_mu_verification": parent_values["carrier_mu_verification"],
            "witness_mu": witness_mu, "errors": arm_errors,
        }
        receipt["qualified"] = primary_ok
        receipt["passed"] = False
        receipt["verdict"] = "INCONCLUSIVE—awaiting independent spatial qualification"
        if arm_errors:
            receipt["error"] = "; ".join(arm_errors)
        receipt["files"]["arrays.npz"] = save_arrays(output, arrays)
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        receipt["verdict"] = "INCONCLUSIVE"
        receipt["passed"] = False
        receipt["qualified"] = False
        if arrays is not None and output.exists() and not (output / "arrays.npz").exists():
            receipt["files"]["arrays.npz"] = save_arrays(output, arrays)
    if not output.exists():
        output.mkdir(parents=True, exist_ok=False)
    dump_json(output / "results.json", receipt)
    print(json.dumps({"verdict": receipt["verdict"], "qualified": receipt["qualified"], "arms": len(receipt["arms"]), "error": receipt["error"]}, ensure_ascii=False, allow_nan=False))
    return 0 if receipt["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--record", type=Path, default=REPORT)
    parser.add_argument("--pump", type=Path, default=PARENT_PRIMARY)
    parser.add_argument("--pump-verification", type=Path, default=PARENT_VERIFICATION)
    args = parser.parse_args()
    try:
        return run(args.output_dir.resolve(), args.record.resolve(), args.pump.resolve(), args.pump_verification.resolve())
    except Exception as exc:
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
