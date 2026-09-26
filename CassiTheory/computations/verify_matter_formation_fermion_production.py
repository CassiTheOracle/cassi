#!/usr/bin/env python3
"""Independent Pauli/Bloch reconstruction of the frozen fermion-production model."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "primary": ROOT / "computations/matter_formation_fermion_production.py",
    "verifier": Path(__file__).resolve(),
    "prereg": ROOT / "computations/matter-formation-fermion-production-prereg.md",
}
SCHEMA = "cassi.matter-formation.fermion-production.v1"
VERIFY_SCHEMA = "cassi.matter-formation.fermion-production.verification.v1"
V = 4.0 * math.pi
OMEGA = 3.0
MOMENTA = np.array([0.0, 0.5, 1.0, 2.0], dtype=np.float64)
CASES = {
    "closed_coarse": (0.02, 600, 0.25, 3.0 * V, True),
    "closed_medium": (0.01, 1200, 0.25, 3.0 * V, True),
    "closed_fine": (0.005, 2400, 0.25, 3.0 * V, True),
    "feedback_off": (0.005, 2400, 0.25, 3.0 * V, False),
    "coupling_zero": (0.005, 2400, 0.0, 3.0 * V, True),
    "pump_zero": (0.005, 2400, 0.25, 0.0, True),
}
PULSE_KEYS = (
    "kind", "p", "mu_initial", "mu_excursion", "duration", "occupation",
    "hole_occupation", "analytic_occupation", "work", "vacuum_energy_change",
    "excitation_energy", "work_balance_residual", "charge_residual",
    "projector_residual", "hermiticity_residual", "trace_residual",
)
SUMMARY_KEYS = (
    "case", "steps", "dt", "duration", "g", "initial_pi", "final_f", "final_pi",
    "final_particle", "final_hole", "peak_particle", "max_projector_residual",
    "max_hermiticity_residual", "max_trace_residual", "max_charge_residual",
    "min_covariance_eigenvalue", "max_covariance_eigenvalue", "min_mass", "max_mass",
    "initial_total_energy", "final_total_energy", "max_total_energy_error",
    "relative_energy_error", "final_scalar_energy", "final_vacuum_energy",
    "final_excitation_energy", "energy_partition_residual",
)
TOP_KEYS = {
    "schema", "identities", "artifacts", "pulse_rows", "trajectory_summaries",
    "convergence", "verdicts", "numerical_pass", "failures",
}
CONVERGENCE_KEYS = {
    "coarse_medium_difference", "medium_fine_difference", "ratio",
    "feedback_effect", "production_peak",
}
ARRAY_KEYS = ("time", "f", "pi", "covariance_re", "covariance_im")
I2 = np.eye(2, dtype=np.complex128)
I4 = np.eye(4, dtype=np.complex128)
REFERENCE_BLOCH = np.column_stack((
    -MOMENTA / np.sqrt(1.0 + MOMENTA**2), np.zeros(4),
    -1.0 / np.sqrt(1.0 + MOMENTA**2),
))


def sha256(path: Path, canonical: bool = False) -> str:
    data = path.read_bytes()
    if canonical:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def identities() -> dict[str, dict[str, str]]:
    return {key: {"path": path.relative_to(ROOT).as_posix(),
                  "sha256": sha256(path, True) if path.is_file() else ""}
            for key, path in SOURCES.items()}


def finite_tree(value: Any) -> bool:
    if isinstance(value, dict):
        return all(isinstance(k, str) and finite_tree(v) for k, v in value.items())
    if isinstance(value, list):
        return all(finite_tree(v) for v in value)
    if isinstance(value, (bool, str)) or value is None:
        return True
    return isinstance(value, (int, float)) and math.isfinite(value)


def write_json(path: Path, value: dict[str, Any]) -> None:
    encoded = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)


def record(ok: bool, path: str, checks: list[dict[str, Any]], mismatches: list[Any]) -> bool:
    ok = bool(ok)
    checks.append({"path": path, "pass": ok})
    if not ok:
        mismatches.append(path)
    return ok


def compare(actual: Any, expected: Any, path: str,
            checks: list[dict[str, Any]], mismatches: list[Any]) -> None:
    if isinstance(expected, dict):
        if not record(isinstance(actual, dict) and set(actual) == set(expected),
                      path + ".keys", checks, mismatches):
            return
        for key, value in expected.items():
            compare(actual[key], value, f"{path}.{key}", checks, mismatches)
    elif isinstance(expected, list):
        if not record(isinstance(actual, list) and len(actual) == len(expected),
                      path + ".length", checks, mismatches):
            return
        for index, value in enumerate(expected):
            compare(actual[index], value, f"{path}[{index}]", checks, mismatches)
    elif type(expected) is float:
        ok = (type(actual) in (int, float) and math.isfinite(actual)
              and abs(actual - expected) <= 2e-8 * max(1.0, abs(actual), abs(expected)))
        record(ok, path, checks, mismatches)
    else:
        record(type(actual) is type(expected) and actual == expected, path, checks, mismatches)


def compare_array(actual: np.ndarray, expected: np.ndarray, path: str,
                  checks: list[dict[str, Any]], mismatches: list[Any]) -> None:
    if not record(actual.shape == expected.shape, path + ".shape", checks, mismatches):
        return
    error = np.abs(actual - expected)
    mask = (np.isfinite(actual) & np.isfinite(expected)
            & (error <= 2e-10 * np.maximum(1.0, np.maximum(np.abs(actual), np.abs(expected)))))
    ok = bool(np.all(mask))
    checks.append({"path": path, "pass": ok, "scalar_count": int(actual.size),
                   "max_absolute_error": float(np.max(error))})
    if not ok:
        mismatches.append({"path": path, "indices": np.argwhere(~mask).tolist()})


def hamiltonian(p: float, mass: float) -> np.ndarray:
    return np.array([[mass, p], [p, -mass]], dtype=np.complex128)


def covariance(r: np.ndarray) -> np.ndarray:
    """Map one or many Bloch vectors to both spin blocks, without propagation."""
    result = np.zeros(r.shape[:-1] + (4, 4), dtype=np.complex128)
    result[..., 0, 0] = result[..., 1, 1] = (1.0 + r[..., 2]) / 2.0
    result[..., 2, 2] = result[..., 3, 3] = (1.0 - r[..., 2]) / 2.0
    up = (r[..., 0] - 1j * r[..., 1]) / 2.0
    result[..., 0, 2], result[..., 2, 0] = up, up.conj()
    result[..., 1, 3], result[..., 3, 1] = -up, -up.conj()
    return result


def two_covariance(r: np.ndarray) -> np.ndarray:
    return np.array([[1.0 + r[2], r[0] - 1j * r[1]],
                     [r[0] + 1j * r[1], 1.0 - r[2]]], dtype=np.complex128) / 2.0


def rotate_integral(r: np.ndarray, p: float, mass: float,
                    duration: float) -> tuple[np.ndarray, np.ndarray]:
    h = np.array([p, 0.0, mass], dtype=np.float64)
    energy = float(np.linalg.norm(h))
    if energy == 0.0:
        return r.copy(), duration * r
    axis = h / energy
    parallel = axis * float(np.dot(axis, r))
    perpendicular = r - parallel
    angle = 2.0 * energy * duration
    sine_over = duration * float(np.sinc(angle / math.pi))
    cosine_over = duration * angle * 0.5 * float(np.sinc(angle / (2.0 * math.pi)))**2
    cross = np.cross(axis, r)
    integral = duration * parallel + sine_over * perpendicular + cosine_over * cross
    rotated = parallel + math.cos(angle) * perpendicular + math.sin(angle) * cross
    return rotated, integral


def pulse_rows() -> list[dict[str, Any]]:
    rows = []
    for kind in ("quench", "pulse"):
        for p in MOMENTA:
            p = float(p)
            e0 = math.sqrt(p * p + 1.0)
            r0 = np.array([-p / e0, 0.0, -1.0 / e0])
            c0, h0 = two_covariance(r0), hamiltonian(p, 1.0)
            for excursion in (0.5, 2.0):
                e1 = math.sqrt(p * p + excursion**2)
                h1 = hamiltonian(p, excursion)
                for duration in ((0.0,) if kind == "quench" else (0.25, 1.0, 3.0)):
                    if kind == "quench":
                        cov, hfinal, efinal = c0, h1, e1
                        analytic = 0.5 * (1.0 - (p * p + excursion) / (e0 * e1))
                        work = float(np.trace((h1 - h0) @ c0).real)
                        vacuum_change = e0 - e1
                    else:
                        rotated, _ = rotate_integral(r0, p, excursion, duration)
                        cov, hfinal, efinal = two_covariance(rotated), h0, e0
                        analytic = (p * (excursion - 1.0) / (e0 * e1))**2 * math.sin(e1 * duration)**2
                        work = float(np.trace((h1 - h0) @ c0 + (h0 - h1) @ cov).real)
                        vacuum_change = 0.0
                    pp, pm = (I2 + hfinal / efinal) / 2.0, (I2 - hfinal / efinal) / 2.0
                    occupation = float(np.trace(pp @ cov).real)
                    hole = float(np.trace(pm @ (I2 - cov)).real)
                    excitation = 2.0 * efinal * occupation
                    rows.append({
                        "kind": kind, "p": p, "mu_initial": 1.0,
                        "mu_excursion": excursion, "duration": duration,
                        "occupation": occupation, "hole_occupation": hole,
                        "analytic_occupation": analytic, "work": work,
                        "vacuum_energy_change": vacuum_change,
                        "excitation_energy": excitation,
                        "work_balance_residual": abs(work - vacuum_change - excitation),
                        "charge_residual": abs(occupation - hole),
                        "projector_residual": float(np.linalg.norm(cov @ cov - cov)),
                        "hermiticity_residual": float(np.linalg.norm(cov - cov.conj().T)),
                        "trace_residual": abs(float(np.trace(cov).real) - 1.0),
                    })
    return rows


def evolve(case: str) -> dict[str, np.ndarray]:
    dt, steps, g, initial_pi, feedback = CASES[case]
    time = np.arange(steps + 1, dtype=np.float64) * dt
    f, pi = np.empty(steps + 1), np.empty(steps + 1)
    bloch = np.empty((steps + 1, 4, 3), dtype=np.float64)
    f[0], pi[0], bloch[0] = 0.0, initial_pi, REFERENCE_BLOCH
    for step in range(steps):
        f_half = f[step] + 0.5 * dt * pi[step] / V
        mass = 1.0 + g * f_half
        force_integral = 0.0
        for j, p in enumerate(MOMENTA):
            rotated, integral = rotate_integral(bloch[step, j], float(p), mass, dt)
            bloch[step + 1, j] = rotated
            force_integral += integral[2] - dt * REFERENCE_BLOCH[j, 2]
        pi[step + 1] = pi[step] - dt * V * OMEGA**2 * f_half
        if feedback:
            pi[step + 1] -= 2.0 * g * force_integral
        f[step + 1] = f_half + 0.5 * dt * pi[step + 1] / V
    return {"time": time, "f": f, "pi": pi, "bloch": bloch}


def full_hamiltonian(p: float, mass: float) -> np.ndarray:
    h = np.diag([mass, mass, -mass, -mass]).astype(np.complex128)
    h[0, 2] = h[2, 0] = p
    h[1, 3] = h[3, 1] = -p
    return h


def diagnose(case: str, f: np.ndarray, pi: np.ndarray,
             covariances: np.ndarray) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    dt, steps, g, initial_pi, _ = CASES[case]
    c0 = covariance(REFERENCE_BLOCH)
    particles, holes = np.empty((steps + 1, 4)), np.empty((steps + 1, 4))
    total, scalar, vacuum, excitation = (np.empty(steps + 1) for _ in range(4))
    max_projector = max_hermiticity = max_trace = max_charge = partition = 0.0
    min_eigen, max_eigen = math.inf, -math.inf
    for t in range(steps + 1):
        mass = 1.0 + g * float(f[t])
        scalar[t] = pi[t]**2 / (2.0 * V) + V * OMEGA**2 * f[t]**2 / 2.0
        ev = ex = direct_quantum = 0.0
        for j, p in enumerate(MOMENTA):
            h, cov = full_hamiltonian(float(p), mass), covariances[t, j]
            energy = math.sqrt(float(p)**2 + mass**2)
            pp, pm = (I4 + h / energy) / 2.0, (I4 - h / energy) / 2.0
            n = 0.5 * float(np.trace(pp @ cov).real)
            hole = 0.5 * float(np.trace(pm @ (I4 - cov)).real)
            particles[t, j], holes[t, j] = n, hole
            max_projector = max(max_projector, float(np.linalg.norm(cov @ cov - cov) / math.sqrt(2.0)))
            max_hermiticity = max(max_hermiticity, float(np.linalg.norm(cov - cov.conj().T) / math.sqrt(2.0)))
            max_trace = max(max_trace, abs(float(np.trace(cov).real) / 2.0 - 1.0))
            max_charge = max(max_charge, abs(n - hole))
            eig = np.linalg.eigvalsh((cov + cov.conj().T) / 2.0)
            min_eigen, max_eigen = min(min_eigen, float(eig[0])), max(max_eigen, float(eig[-1]))
            ev += -2.0 * energy - float(np.trace(h @ c0[j]).real)
            ex += 4.0 * energy * n
            direct_quantum += float(np.trace(h @ (cov - c0[j])).real)
        vacuum[t], excitation[t] = ev, ex
        total[t] = scalar[t] + direct_quantum
        partition = max(partition, abs(total[t] - (scalar[t] + ev + ex)))
    initial_total = float(total[0])
    max_error = float(np.max(np.abs(total - initial_total)))
    summary = {
        "case": case, "steps": steps, "dt": dt, "duration": steps * dt,
        "g": g, "initial_pi": initial_pi, "final_f": float(f[-1]),
        "final_pi": float(pi[-1]), "final_particle": particles[-1].tolist(),
        "final_hole": holes[-1].tolist(), "peak_particle": np.max(particles, axis=0).tolist(),
        "max_projector_residual": max_projector, "max_hermiticity_residual": max_hermiticity,
        "max_trace_residual": max_trace, "max_charge_residual": max_charge,
        "min_covariance_eigenvalue": min_eigen, "max_covariance_eigenvalue": max_eigen,
        "min_mass": float(np.min(1.0 + g * f)), "max_mass": float(np.max(1.0 + g * f)),
        "initial_total_energy": initial_total, "final_total_energy": float(total[-1]),
        "max_total_energy_error": max_error,
        "relative_energy_error": max_error / max(1.0, abs(initial_total)),
        "final_scalar_energy": float(scalar[-1]), "final_vacuum_energy": float(vacuum[-1]),
        "final_excitation_energy": float(excitation[-1]), "energy_partition_residual": float(partition),
    }
    return summary, {"particle": particles, "hole": holes}


def convergence(dynamics: dict[str, dict[str, np.ndarray]],
                samples: dict[str, dict[str, np.ndarray]]) -> dict[str, float]:
    vectors = {case: np.column_stack((data["f"], data["pi"] / (3.0 * V), samples[case]["particle"]))
               for case, data in dynamics.items()}
    coarse, medium, fine = (vectors[c] for c in ("closed_coarse", "closed_medium", "closed_fine"))
    dcm = float(np.max(np.abs(coarse - medium[::2])))
    dmf = float(np.max(np.abs(medium - fine[::2])))
    return {
        "coarse_medium_difference": dcm, "medium_fine_difference": dmf,
        "ratio": dcm / dmf if dmf != 0.0 else 0.0,
        "feedback_effect": float(np.max(np.abs(fine[:, :2] - vectors["feedback_off"][:, :2]))),
        "production_peak": float(np.max(samples["closed_fine"]["particle"][:, 1:])),
    }


def assess(rows: list[dict[str, Any]], summaries: list[dict[str, Any]],
           conv: dict[str, float], samples: dict[str, dict[str, np.ndarray]]) -> tuple[dict[str, str], list[str]]:
    failures = []
    correspondence_ok = True
    for index, row in enumerate(rows):
        errors = []
        if max(abs(row["occupation"] - row["analytic_occupation"]), row["work_balance_residual"]) > 2e-11:
            errors.append("analytic occupation/work")
        if row["p"] == 0.0:
            if max(abs(row[k]) for k in ("occupation", "hole_occupation", "analytic_occupation")) > 2e-11:
                errors.append("zero-momentum control")
        elif row["analytic_occupation"] <= 1e-8:
            errors.append("resolved analytic production")
        if any(row[k] > 5e-10 for k in ("projector_residual", "hermiticity_residual", "trace_residual", "charge_residual")):
            errors.append("covariance/charge invariant")
        if any(not -5e-10 <= row[k] <= 1.0 + 5e-10 for k in ("occupation", "hole_occupation")):
            errors.append("Pauli bound")
        if errors:
            correspondence_ok = False
            failures.append(f"pulse_rows[{index}]: {', '.join(errors)}")
    for summary in summaries:
        case = summary["case"]
        errors = []
        if any(summary[k] > 5e-10 for k in ("max_projector_residual", "max_hermiticity_residual", "max_trace_residual", "max_charge_residual")):
            errors.append("covariance/charge invariant")
        if summary["min_covariance_eigenvalue"] < -5e-10 or summary["max_covariance_eigenvalue"] > 1.0 + 5e-10:
            errors.append("covariance eigenvalue bound")
        for array in samples[case].values():
            if np.min(array) < -5e-10 or np.max(array) > 1.0 + 5e-10:
                errors.append("all-time occupation bound")
            if case in ("coupling_zero", "pump_zero") and np.max(np.abs(array)) > 5e-10:
                errors.append("all-time zero-production control")
            if np.max(np.abs(array[:, 0])) > 5e-10:
                errors.append("all-time zero-momentum control")
        if summary["energy_partition_residual"] > 5e-10 or summary["min_mass"] <= 0.0:
            errors.append("energy partition/gap")
        if case in ("closed_fine", "coupling_zero", "pump_zero") and summary["relative_energy_error"] > 2e-4:
            errors.append("energy conservation")
        if errors:
            failures.append(f"{case}: {', '.join(errors)}")
    if conv["medium_fine_difference"] <= 1e-10 or not 3.0 <= conv["ratio"] <= 5.0:
        failures.append("time-step convergence qualification")
    if failures:
        backreaction = "INCONCLUSIVE"
    elif conv["production_peak"] > 1e-6 and conv["feedback_effect"] > 1e-6:
        backreaction = "SUPPORTS—energy-accounted semiclassical fermion production in the specified finite-mode model"
    else:
        backreaction = "DOES NOT EMERGE—production and feedback at the registered thresholds"
    return {
        "fermion_correspondence": "SUPPORTS—finite-mode fermion pair correspondence" if correspondence_ok else "INCONCLUSIVE",
        "closed_backreaction": backreaction,
    }, failures


def load_inputs(input_dir: Path, ids: dict[str, Any], checks: list[dict[str, Any]],
                mismatches: list[Any]) -> tuple[dict[str, Any], dict[str, dict[str, np.ndarray]], str]:
    for name, item in ids.items():
        if not record(bool(item["sha256"]), f"source.{name}.exists", checks, mismatches):
            raise ValueError(f"missing required source: {name}")
    path = input_dir / "results.json"
    if not record(path.is_file(), "primary.receipt.exists", checks, mismatches):
        raise ValueError("missing primary receipt")
    raw_hash = sha256(path)
    primary = json.loads(path.read_text(encoding="utf-8"))
    if not record(isinstance(primary, dict) and set(primary) == TOP_KEYS and finite_tree(primary),
                  "primary.receipt.shape_and_finite", checks, mismatches):
        raise ValueError("invalid primary receipt shape or finite values")
    compare(primary["schema"], SCHEMA, "primary.schema", checks, mismatches)
    compare(primary["identities"], ids, "primary.identities", checks, mismatches)
    if not record(type(primary["numerical_pass"]) is bool and isinstance(primary["failures"], list)
                  and all(isinstance(x, str) for x in primary["failures"])
                  and primary["numerical_pass"] == (not primary["failures"]),
                  "primary.outcome_shape", checks, mismatches):
        raise ValueError("invalid primary outcome fields")
    if not record(isinstance(primary["pulse_rows"], list) and len(primary["pulse_rows"]) == 32
                  and all(isinstance(row, dict) and set(row) == set(PULSE_KEYS) for row in primary["pulse_rows"]),
                  "primary.pulse_rows.shape", checks, mismatches):
        raise ValueError("invalid primary pulse rows")
    if not record(isinstance(primary["trajectory_summaries"], list) and len(primary["trajectory_summaries"]) == 6
                  and all(isinstance(row, dict) and set(row) == set(SUMMARY_KEYS) for row in primary["trajectory_summaries"]),
                  "primary.trajectory_summaries.shape", checks, mismatches):
        raise ValueError("invalid primary trajectory summaries")
    if not record(isinstance(primary["convergence"], dict) and set(primary["convergence"]) == CONVERGENCE_KEYS,
                  "primary.convergence.shape", checks, mismatches):
        raise ValueError("invalid convergence shape")
    artifacts = primary["artifacts"]
    if not record(isinstance(artifacts, dict) and list(artifacts) == list(CASES),
                  "primary.artifacts.schedule", checks, mismatches):
        raise ValueError("invalid primary artifact schedule")
    arrays = {}
    for case, (dt, steps, *_rest) in CASES.items():
        item = artifacts[case]
        if not record(isinstance(item, dict) and set(item) == {"path", "sha256"}
                      and item["path"] == f"{case}.npz", f"artifact.{case}.identity_shape", checks, mismatches):
            raise ValueError(f"invalid artifact identity: {case}")
        target = input_dir / item["path"]
        if not record(target.is_file(), f"artifact.{case}.exists", checks, mismatches):
            raise ValueError(f"missing primary artifact: {case}")
        compare(item["sha256"], sha256(target), f"artifact.{case}.sha256", checks, mismatches)
        with np.load(target, allow_pickle=False) as archive:
            if not record(tuple(archive.files) == ARRAY_KEYS, f"artifact.{case}.keys", checks, mismatches):
                raise ValueError(f"invalid archive keys: {case}")
            data = {key: archive[key] for key in ARRAY_KEYS}
        for key, value in data.items():
            shape = (steps + 1, 4, 4, 4) if key.startswith("covariance_") else (steps + 1,)
            if not record(value.shape == shape and value.dtype == np.float64 and np.isfinite(value).all(),
                          f"artifact.{case}.{key}.shape_dtype_finite", checks, mismatches):
                raise ValueError(f"invalid primary array: {case}/{key}")
        if not record(np.array_equal(data["time"], np.arange(steps + 1, dtype=np.float64) * dt),
                      f"artifact.{case}.time_schedule", checks, mismatches):
            raise ValueError(f"invalid time schedule: {case}")
        arrays[case] = data
    if mismatches:
        raise ValueError("primary source or artifact identity mismatch")
    return primary, arrays, raw_hash


def run(input_dir: Path, output_dir: Path) -> int:
    input_dir, output_dir = input_dir.resolve(), output_dir.resolve()
    targets = [output_dir / "verification.json", *(output_dir / f"independent_{case}.npz" for case in CASES)]
    if any(path.exists() for path in targets):
        raise FileExistsError("refusing an existing verification or trajectory target")
    ids, checks, mismatches = identities(), [], []
    receipt = {
        "schema": VERIFY_SCHEMA, "identities": ids, "artifacts": {}, "pulse_rows": [],
        "trajectory_summaries": [], "convergence": {}, "verdicts": {},
        "numerical_pass": False, "failures": [], "input_sha256": "", "input_artifacts": {},
        "independent_checks": {"comparison_count": 0, "scalar_count": 0,
                               "comparisons": checks, "mismatches": mismatches},
    }
    primary_path = input_dir / "results.json"
    if primary_path.is_file():
        receipt["input_sha256"] = sha256(primary_path)
    try:
        primary, inputs, receipt["input_sha256"] = load_inputs(input_dir, ids, checks, mismatches)
    except Exception as exc:
        receipt["failures"] = [f"required-input failure: {type(exc).__name__}: {exc}"]
        receipt["independent_checks"]["comparison_count"] = len(checks)
        write_json(output_dir / "verification.json", receipt)
        print(receipt["failures"][0])
        return 1
    receipt["input_artifacts"] = primary["artifacts"]
    own_dynamics, own_samples, primary_samples = {}, {}, {}
    own_summaries, primary_summaries = [], []
    rows = pulse_rows()
    compare(primary["pulse_rows"], rows, "primary.pulse_rows", checks, mismatches)
    for index, case in enumerate(CASES):
        raw = inputs[case]
        primary_cov = raw["covariance_re"] + 1j * raw["covariance_im"]
        summary, sample = diagnose(case, raw["f"], raw["pi"], primary_cov)
        primary_summaries.append(summary)
        primary_samples[case] = sample
        compare(primary["trajectory_summaries"][index], summary,
                f"primary.raw_summary[{index}]", checks, mismatches)
        own = evolve(case)
        own_dynamics[case] = own
        own_cov = covariance(own["bloch"])
        for key in ("time", "f", "pi"):
            compare_array(raw[key], own[key], f"raw.{case}.{key}", checks, mismatches)
        compare_array(raw["covariance_re"], own_cov.real, f"raw.{case}.covariance_re", checks, mismatches)
        compare_array(raw["covariance_im"], own_cov.imag, f"raw.{case}.covariance_im", checks, mismatches)
        summary, sample = diagnose(case, own["f"], own["pi"], own_cov)
        own_summaries.append(summary)
        own_samples[case] = sample
        compare(primary["trajectory_summaries"][index], summary,
                f"primary.independent_summary[{index}]", checks, mismatches)
        target = output_dir / f"independent_{case}.npz"
        output_dir.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            np.savez_compressed(stream, **own)
        receipt["artifacts"][case] = {"path": target.name, "sha256": sha256(target)}
    own_conv = convergence(own_dynamics, own_samples)
    raw_conv = convergence(inputs, primary_samples)
    compare(primary["convergence"], raw_conv, "primary.raw_convergence", checks, mismatches)
    compare(primary["convergence"], own_conv, "primary.independent_convergence", checks, mismatches)
    own_verdicts, own_failures = assess(rows, own_summaries, own_conv, own_samples)
    raw_verdicts, raw_failures = assess(primary["pulse_rows"], primary_summaries, raw_conv, primary_samples)
    compare(primary["verdicts"], raw_verdicts, "primary.raw_verdicts", checks, mismatches)
    compare(primary["verdicts"], own_verdicts, "primary.independent_verdicts", checks, mismatches)
    compare(primary["numerical_pass"], not raw_failures, "primary.reconstructed_numerical_pass", checks, mismatches)
    failures = [f"independent: {x}" for x in own_failures] + [f"primary raw evidence: {x}" for x in raw_failures]
    if mismatches:
        failures.append("independent receipt, raw-array or summary comparison failed")
        own_verdicts = {key: "INCONCLUSIVE" for key in own_verdicts}
    receipt.update(pulse_rows=rows, trajectory_summaries=own_summaries, convergence=own_conv,
                   verdicts=own_verdicts, numerical_pass=not failures, failures=failures)
    receipt["independent_checks"]["comparison_count"] = len(checks)
    receipt["independent_checks"]["scalar_count"] = sum(item.get("scalar_count", 0) for item in checks)
    if not finite_tree(receipt):
        raise ValueError("nonfinite independent evidence; raw archives retained")
    write_json(output_dir / "verification.json", receipt)
    print(f"numerical_pass={receipt['numerical_pass']} comparisons={len(checks)} mismatches={len(mismatches)}")
    print(f"production_peak={own_conv['production_peak']:.17g} feedback_effect={own_conv['feedback_effect']:.17g} convergence_ratio={own_conv['ratio']:.17g}")
    for key, value in own_verdicts.items():
        print(f"{key}={value}")
    for failure in failures:
        print(f"failure: {failure}")
    return 0 if receipt["numerical_pass"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return run(args.input_dir, args.output_dir)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
