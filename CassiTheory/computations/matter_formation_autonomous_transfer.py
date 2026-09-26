#!/usr/bin/env python3
"""Primary frozen nonlinear energy-transfer calculation in the exact plane-wave sector.

The four prescribed finite-time trajectories are evolved independently with DOP853 in
velocity variables.  This program is the provisional primary only: it never claims the
independent qualification required for the final physical verdict.
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
from scipy import special
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "computations/matter-formation-continuum-report.md"
ACTION = ROOT / "foundations/particle-stationary-action-closure.md"
VERIFIER = ROOT / "computations/verify_matter_formation_autonomous_transfer.py"
PUMP_DIR = ROOT / "runs/20260907_matter_formation_autonomous_pump"
PUMP_VERIFICATION_DIR = ROOT / "runs/20260907_matter_formation_autonomous_pump_verification"
PROTOCOL_HEADING = "### 26.3 Nonlinear transfer calculation: pre-execution criteria"
PROTOCOL_SHA256 = "82c7e628f00b275fde856c2f52b11782de12dfdd686aea3568be15efbb9f6106"
PUMP_SHA256 = "cad33ef760404c79807570be1269390dfb790574dc13bfe60d61d67c5b1bc9c5"
PUMP_VERIFICATION_SHA256 = "a54c07d1a973f9a915355e26b7c23e7caa7ee75a468f09fda53e13a272959758"
SCHEMA = "cassi.matter-formation.autonomous-transfer.v1"

A = 1.0 / 16.0
C_PSI = 1.0 / 8.0
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
H_C = 2.9598260763447164
E_C = 0.75
F0 = math.sqrt(3.0 / 2.0)
M = 2.0 / 3.0
OMEGA = math.sqrt(24.0)
RTOL = 2.0e-12
ATOL = (2.0e-14, 2.0e-14, 2.0e-20, 2.0e-20, 2.0e-16)

ARM_SPECS = (
    ("full", 1.0, H_C, U_C, 1.0e-6),
    ("uncoupled", 0.0, 0.0, U_C, 1.0e-6),
    ("zero_carrier", 1.0, H_C, U_C, 0.0),
    ("linear_reference", 0.0, H_C, 0.0, 1.0e-6),
)


class ContractError(RuntimeError):
    """A frozen prerequisite or protocol violation."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def finite(value: Any) -> bool:
    try:
        return bool(np.all(np.isfinite(value)))
    except (TypeError, ValueError):
        return False


def json_safe(value: Any) -> Any:
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
    return value

def dump_json(path: Path, value: Any) -> None:
    with path.open("xb",) as stream:
        stream.write(json.dumps(json_safe(value), ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8"))
        stream.write(b"\n")


def frozen_section(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(PROTOCOL_HEADING) != 1:
        raise ContractError("frozen nonlinear-transfer heading must occur exactly once")
    rest = text.split(PROTOCOL_HEADING, 1)[1]
    match = re.search(r"\n#{1,3} ", rest)
    section = PROTOCOL_HEADING + (rest[:match.start()] if match else rest)
    return (section.rstrip() + "\n").encode("utf-8")


def initial_receipt() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "passed": False,
        "qualified": False,
        "candidate_support": False,
        "G": None,
        "R": None,
        "verdict": "INCONCLUSIVE",
        "error": None,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "protocol_sha256": PROTOCOL_SHA256,
        "files": {},
        "parameters": {},
        "arms": [],
        "checks": {
            "energy_work": False,
            "uncoupled_energy": False,
            "zero_carrier": False,
            "zero_orbit": False,
            "early_linear": False,
            "linear_growth": False,
            "complete_finite": False,
        },
        "diagnostics": {
            "zero_orbit_errors": [None, None],
            "early_linear_errors": [None, None],
            "linear_growth_rate": None,
            "linear_growth_relative_error": None,
            "linear_reference_exceedance_index": None,
            "linear_reference_exceedance_time": None,
        },
    }


def load_parent(path: Path, expected_hash: str, schema: str) -> tuple[dict[str, Any], bytes]:
    if not path.is_file():
        raise ContractError(f"missing inherited receipt: {path}")
    raw = path.read_bytes()
    if sha256(raw) != expected_hash:
        raise ContractError(f"inherited receipt hash mismatch: {path.name}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid inherited receipt JSON: {path.name}") from exc
    if data.get("schema") != schema:
        raise ContractError(f"inherited receipt schema mismatch: {path.name}")
    if data.get("qualified") is not True or not str(data.get("verdict", "")).startswith("SUPPORTS"):
        raise ContractError(f"inherited receipt is not qualified: {path.name}")
    return data, raw


def witness(receipt: dict[str, Any], label: str) -> dict[str, Any]:
    rows = [row for row in receipt.get("witnesses", []) if row.get("j") == 3]
    if len(rows) != 1 or rows[0].get("passed") is not True or rows[0].get("unstable") is not True:
        raise ContractError(f"{label} lacks one resolved j=3 witness")
    row = rows[0]
    for key in ("k", "mu"):
        if not isinstance(row.get(key), (int, float)) or not math.isfinite(float(row[key])):
            raise ContractError(f"{label} j=3 witness has no finite {key}")
    return row


def source_stage(
    out: Path,
    report: Path,
    pump_dir: Path,
    pump_verification_dir: Path,
) -> tuple[dict[str, str], dict[str, Any], dict[str, Any], bytes, bytes]:
    if not report.is_file():
        raise ContractError(f"missing report: {report}")
    protocol = frozen_section(report)
    if sha256(protocol) != PROTOCOL_SHA256:
        raise ContractError("frozen nonlinear-transfer protocol hash mismatch")
    parent, parent_raw = load_parent(pump_dir / "results.json", PUMP_SHA256, "cassi.matter-formation.autonomous-pump.v1")
    parent_verification, parent_verification_raw = load_parent(
        pump_verification_dir / "results.json", PUMP_VERIFICATION_SHA256,
        "cassi.matter-formation.autonomous-pump-verification.v1",
    )
    primary_witness = witness(parent, "primary parent")
    independent_witness = witness(parent_verification, "independent parent")
    if abs(float(primary_witness["k"]) - float(independent_witness["k"])) > 1.0e-10:
        raise ContractError("primary and independent j=3 wave numbers disagree")
    if parent_verification.get("mismatches") != []:
        raise ContractError("independent parent receipt mismatches are not empty")
    if parent_verification.get("files", {}).get("primary_results.json") != PUMP_SHA256:
        raise ContractError("independent parent does not retain the pinned primary receipt")
    if not isinstance(parent.get("orbit", {}).get("period"), (int, float)):
        raise ContractError("primary parent has no period")
    period = float(parent["orbit"]["period"])
    if not math.isfinite(period) or period <= 0.0:
        raise ContractError("primary parent period is not positive and finite")
    if abs(float(parent_verification.get("orbit", {}).get("period", period)) - period) > 1.0e-10:
        raise ContractError("parent periods disagree")
    if not ACTION.is_file():
        raise ContractError(f"missing source action: {ACTION}")
    if not VERIFIER.is_file():
        raise ContractError(f"missing verifier source: {VERIFIER}")

    retained: dict[str, str] = {}

    def retain(name: str, data: bytes) -> None:
        target = out / name
        with target.open("xb") as handle:
            handle.write(data)
        retained[name] = sha256(data)

    retain("source_primary.py", Path(__file__).read_bytes())
    retain("source_verifier.py", VERIFIER.read_bytes())
    retain("frozen_protocol.txt", protocol)
    retain("source_action.txt", ACTION.read_bytes())
    retain("parent_results.json", parent_raw)
    retain("parent_verification_results.json", parent_verification_raw)
    return retained, parent, parent_verification, protocol, parent_raw


def rhs_factory(k: float, b: float, h: float, u: float):
    B = E_C + 1.0 / (4.0 * A)
    carrier_base = K_CX * k * k / 2.0 + B

    def rhs(_t: float, state: np.ndarray) -> np.ndarray:
        f, fdot, y, ydot, _work = state
        fddot = (-U_RHO * (f * f - 1.0) * f - 2.0 * b * h * f * y * y) / C_PSI
        yddot = -(carrier_base - h + h * f * f + u * y * y) * y / A
        workdot = 2.0 * h * f * fdot * y * y
        return np.asarray((fdot, fddot, ydot, yddot, workdot), dtype=np.float64)

    return rhs


def energy_arrays(state: np.ndarray, k: float, h: float, u: float) -> np.ndarray:
    f, fdot, y, ydot, _work = state.T
    B = E_C + 1.0 / (4.0 * A)
    D_k = K_CX * k * k / 2.0 + B - h
    ef = C_PSI / 2.0 * fdot * fdot + U_RHO / 4.0 * (f * f - 1.0) ** 2
    ey = A * ydot * ydot + (D_k + h * f * f) * y * y + u / 2.0 * y ** 4
    return np.column_stack((ef, ey, ef + ey)).astype(np.float64)


def blank_arrays(t: np.ndarray, sample_count: int) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {"t": t.copy()}
    for name, *_ in ARM_SPECS:
        arrays[f"state_{name}"] = np.full((sample_count, 5), np.nan, dtype=np.float64)
        arrays[f"energy_{name}"] = np.full((sample_count, 3), np.nan, dtype=np.float64)
    return arrays


def evolve_arm(name: str, b: float, h: float, u: float, seed: float, t: np.ndarray, k: float, max_step: float) -> tuple[np.ndarray, dict[str, Any], list[str]]:
    state = np.full((t.size, 5), np.nan, dtype=np.float64)
    row: dict[str, Any] = {
        "name": name, "method": "DOP853", "success": False,
        "nfev": None, "njev": None, "nlu": None, "metrics": {},
    }
    errors: list[str] = []
    try:
        y0 = np.asarray((F0, 0.0, seed, 0.0, 0.0), dtype=np.float64)
        sol = solve_ivp(
            rhs_factory(k, b, h, u), (float(t[0]), float(t[-1])), y0,
            method="DOP853", t_eval=t, rtol=RTOL, atol=np.asarray(ATOL, dtype=np.float64), max_step=max_step,
        )
        count = min(int(sol.y.shape[1]), int(t.size))
        if count:
            state[:count, :] = sol.y[:, :count].T
        row["nfev"] = int(getattr(sol, "nfev", 0))
        row["njev"] = int(getattr(sol, "njev", 0))
        row["nlu"] = int(getattr(sol, "nlu", 0))
        row["success"] = bool(sol.success and count == t.size)
        if not row["success"]:
            errors.append(f"{name} solve failed: {sol.message}")
    except Exception as exc:
        errors.append(f"{name} solve {type(exc).__name__}: {exc}")
    return state, row, errors


def arm_metrics(state: np.ndarray, energy: np.ndarray, t: np.ndarray, name: str, b: float, h: float, u: float) -> dict[str, Any]:
    finite_rows = np.all(np.isfinite(state), axis=1) & np.all(np.isfinite(energy), axis=1)
    if not np.any(finite_rows):
        return {key: float("nan") for key in (
            "initial_total_energy", "initial_carrier_energy", "balance_scale", "total_balance_error",
            "carrier_work_error", "mediator_work_error", "peak_carrier_energy", "peak_index", "peak_time",
            "energy_gain", "transfer_fraction", "final_carrier_energy", "final_transfer_fraction",
            "max_abs_f", "max_abs_fdot", "max_abs_y", "max_abs_ydot", "max_fractional_carrier_change",
        )}
    count = int(np.count_nonzero(finite_rows))
    s = state[:count]
    e = energy[:count]
    work = s[:, 4]
    ef0, ey0, et0 = (float(e[0, i]) for i in range(3))
    peak_index = int(np.argmax(e[:, 1]))
    peak_ey = float(e[peak_index, 1])
    scale = max(et0, float(np.max(e[:, 1]))) if name == "linear_reference" else et0
    scale = float(scale)
    mediator_error = float(np.max(np.abs(e[:, 0] - ef0 + b * work)) / scale)
    carrier_error = float(np.max(np.abs(e[:, 1] - ey0 - work)) / scale)
    total_error = float(np.max(np.abs(e[:, 2] - et0 - (1.0 - b) * work)) / scale)
    gain = None if ey0 == 0.0 else peak_ey / ey0
    fraction = (peak_ey - ey0) / et0 if et0 != 0.0 else float("nan")
    final_fraction = (float(e[-1, 1]) - ey0) / et0 if et0 != 0.0 else float("nan")
    fractional_change = None if ey0 == 0.0 else float(np.max(np.abs(e[:, 1] - ey0)) / ey0)
    return {
        "initial_total_energy": et0,
        "initial_carrier_energy": ey0,
        "balance_scale": scale,
        "total_balance_error": total_error,
        "carrier_work_error": carrier_error,
        "mediator_work_error": mediator_error,
        "peak_carrier_energy": peak_ey,
        "peak_index": peak_index,
        "peak_time": float(t[peak_index]),
        "energy_gain": gain,
        "transfer_fraction": float(fraction),
        "final_carrier_energy": float(e[-1, 1]),
        "final_transfer_fraction": float(final_fraction),
        "max_abs_f": float(np.max(np.abs(s[:, 0]))),
        "max_abs_fdot": float(np.max(np.abs(s[:, 1]))),
        "max_abs_y": float(np.max(np.abs(s[:, 2]))),
        "max_abs_ydot": float(np.max(np.abs(s[:, 3]))),
        "max_fractional_carrier_change": fractional_change,
    }


def qualify(
    arrays: dict[str, np.ndarray], arms: list[dict[str, Any]], k: float, mu: float, period: float,
    sample_count: int, early_end_index: int, slope_indices: tuple[int, int],
) -> tuple[dict[str, bool], dict[str, Any], bool, float, float]:
    by_name = {row["name"]: row for row in arms}
    state = {name: arrays[f"state_{name}"] for name, *_ in ARM_SPECS}
    energy = {name: arrays[f"energy_{name}"] for name, *_ in ARM_SPECS}
    metrics = {name: by_name[name]["metrics"] for name, *_ in ARM_SPECS}
    complete = bool(all(by_name[name].get("success") is True for name, *_ in ARM_SPECS))
    complete = complete and all(finite(arrays[f"state_{name}"]) and finite(arrays[f"energy_{name}"]) for name, *_ in ARM_SPECS)
    energy_work = complete and all(
        max(float(metrics[name]["total_balance_error"]), float(metrics[name]["carrier_work_error"]), float(metrics[name]["mediator_work_error"])) < 1.0e-7
        for name, *_ in ARM_SPECS
    )
    uncoupled_energy = bool(complete and metrics["uncoupled"]["max_fractional_carrier_change"] < 1.0e-5)
    zero_state = state["zero_carrier"]
    zero_carrier = bool(complete and np.count_nonzero(zero_state[:, 2:5]) == 0)
    u = OMEGA * arrays["t"]
    sn, cn, dn, _ = special.ellipj(u, M)
    exact_f = F0 * dn
    exact_fd = -F0 * M * OMEGA * sn * cn
    zero_errors = [float(np.max(np.abs(zero_state[:, 0] - exact_f)) / max(1.0, float(np.max(np.abs(exact_f))))), float(np.max(np.abs(zero_state[:, 1] - exact_fd)) / max(1.0, float(np.max(np.abs(exact_fd)))))] if complete else [float("nan"), float("nan")]
    zero_orbit = bool(complete and max(zero_errors) < 2.0e-5)
    end = min(max(int(early_end_index), 0), sample_count - 1)
    full_state = state["full"][: end + 1]
    linear_state = state["linear_reference"][: end + 1]
    if complete:
        early_errors = [
            float(np.max(np.abs(full_state[:, 2] - linear_state[:, 2])) / max(1.0e-6, float(np.max(np.abs(linear_state[:, 2]))))),
            float(np.max(np.abs(full_state[:, 3] - linear_state[:, 3])) / max(1.0e-6, float(np.max(np.abs(linear_state[:, 3]))))),
        ]
    else:
        early_errors = [float("nan"), float("nan")]
    early_linear = bool(complete and max(early_errors) < 2.0e-3)
    i0, i1 = slope_indices
    omega0_sq = (K_CX * k * k / 2.0 + E_C + 1.0 / (4.0 * A) - H_C + H_C * F0 ** 2) / A
    if complete and i1 < sample_count and i0 >= 0 and i1 > i0 and omega0_sq > 0.0:
        omega0 = math.sqrt(omega0_sq)
        amp = np.sqrt(state["linear_reference"][:, 2] ** 2 + (state["linear_reference"][:, 3] / omega0) ** 2)
        growth_rate = float(math.log(float(amp[i1] / amp[i0])) / (float(arrays["t"][i1]) - float(arrays["t"][i0])))
        growth_relative = float(abs(growth_rate - mu) / mu)
    else:
        growth_rate = float("nan")
        growth_relative = float("nan")
    linear_growth = bool(math.isfinite(growth_relative) and growth_relative < 5.0e-3)
    full_initial_total = float(metrics["full"].get("initial_total_energy", float("nan")))
    exceed = np.flatnonzero(energy["linear_reference"][:, 1] > full_initial_total) if complete and math.isfinite(full_initial_total) else np.asarray([], dtype=np.int64)
    exceed_index = int(exceed[0]) if exceed.size else None
    exceed_time = float(arrays["t"][exceed_index]) if exceed_index is not None else None
    checks = {
        "energy_work": bool(energy_work), "uncoupled_energy": uncoupled_energy,
        "zero_carrier": zero_carrier, "zero_orbit": zero_orbit,
        "early_linear": early_linear, "linear_growth": linear_growth,
        "complete_finite": complete,
    }
    diagnostics = {
        "zero_orbit_errors": zero_errors,
        "early_linear_errors": early_errors,
        "linear_growth_rate": growth_rate,
        "linear_growth_relative_error": growth_relative,
        "linear_reference_exceedance_index": exceed_index,
        "linear_reference_exceedance_time": exceed_time,
    }
    full_gain = metrics["full"].get("energy_gain")
    full_fraction = metrics["full"].get("transfer_fraction")
    G = float(full_gain) if isinstance(full_gain, (int, float)) and math.isfinite(float(full_gain)) else float("nan")
    R = float(full_fraction) if isinstance(full_fraction, (int, float)) and math.isfinite(float(full_fraction)) else float("nan")
    qualified = bool(all(checks.values()) and math.isfinite(G) and math.isfinite(R))
    return checks, diagnostics, qualified, G, R


def save_arrays(out: Path, arrays: dict[str, np.ndarray]) -> str:
    target = out / "arrays.npz"
    with target.open("xb") as handle:
        np.savez(handle, **arrays)
    return sha256(target.read_bytes())


def run(output: Path, record: Path, pump_dir: Path, pump_verification_dir: Path) -> int:
    if output.exists():
        raise ContractError(f"refusing existing output directory: {output}")
    output.mkdir(parents=True, exist_ok=False)
    receipt = initial_receipt()
    try:
        retained, parent, parent_verification, _protocol, parent_raw = source_stage(output, record, pump_dir, pump_verification_dir)
        receipt["files"].update(retained)
        primary_witness = witness(parent, "primary parent")
        independent_witness = witness(parent_verification, "independent parent")
        k = float(primary_witness["k"])
        mu = float(primary_witness["mu"])
        period = float(parent["orbit"]["period"])
        J = int(math.ceil(16.0 / (mu * period)))
        sample_count = 16 * J + 1
        t = np.arange(sample_count, dtype=np.float64) * period / 16.0
        early_end_index = 16 * int(math.floor(2.0 / (mu * period)))
        slope_indices = (16 * int(math.floor(4.0 / (mu * period))), 16 * int(math.floor(6.0 / (mu * period))))
        if early_end_index >= sample_count or slope_indices[1] >= sample_count:
            raise ContractError("derived sample schedule does not contain required diagnostics")
        params = {
            "k": k, "mu": mu, "period": period, "period_count": J,
            "sample_count": sample_count, "early_end_index": early_end_index,
            "slope_indices": list(slope_indices), "carrier_seed": 1.0e-6,
            "u_rho": U_RHO, "u_C": U_C, "k_Cx": K_CX, "h_C": H_C,
            "e_C": E_C, "a": A, "c_psi": C_PSI, "F": F0,
        }
        receipt["parameters"] = params
        arrays = blank_arrays(t, sample_count)
        errors: list[str] = []
        max_step = period / 32.0
        for name, b, h, u, seed in ARM_SPECS:
            state, row, arm_errors = evolve_arm(name, b, h, u, seed, t, k, max_step)
            arrays[f"state_{name}"] = state
            try:
                arrays[f"energy_{name}"] = energy_arrays(state, k, h, u)
            except Exception as exc:
                arm_errors.append(f"{name} energy {type(exc).__name__}: {exc}")
            row["metrics"] = arm_metrics(arrays[f"state_{name}"], arrays[f"energy_{name}"], t, name, b, h, u)
            receipt["arms"].append(row)
            print(json.dumps({"arm": name, "success": row["success"], "nfev": row["nfev"], "error": arm_errors}, ensure_ascii=False))
            errors.extend(arm_errors)
        checks, diagnostics, qualified, gain, transfer = qualify(
            arrays, receipt["arms"], k, mu, period, sample_count, early_end_index, slope_indices,
        )
        receipt["checks"] = checks
        receipt["G"] = gain
        receipt["R"] = transfer
        receipt["diagnostics"] = diagnostics
        receipt["diagnostics"]["G"] = gain
        receipt["diagnostics"]["R"] = transfer
        receipt["candidate_support"] = bool(qualified and gain >= 100.0 and transfer >= 1.0e-5)
        receipt["qualified"] = qualified
        receipt["passed"] = False
        receipt["verdict"] = "INCONCLUSIVE—awaiting independent nonlinear qualification" if qualified else "INCONCLUSIVE"
        receipt["error"] = "; ".join(errors) if errors else None
        receipt["files"]["arrays.npz"] = save_arrays(output, arrays)
        dump_json(output / "results.json", receipt)
        return 0 if qualified else 1
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        receipt["verdict"] = "INCONCLUSIVE"
        dump_json(output / "results.json", receipt)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--record", type=Path, default=REPORT)
    parser.add_argument("--pump-dir", type=Path, default=PUMP_DIR)
    parser.add_argument("--pump-verification-dir", type=Path, default=PUMP_VERIFICATION_DIR)
    args = parser.parse_args()
    try:
        return run(args.output_dir.resolve(), args.record.resolve(), args.pump_dir.resolve(), args.pump_verification_dir.resolve())
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
