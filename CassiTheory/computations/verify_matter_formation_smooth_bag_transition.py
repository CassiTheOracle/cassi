#!/usr/bin/env python3
"""Independent verifier for smooth vacuum-to-bound-state formation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PRIMARY = ROOT / "computations" / "matter_formation_smooth_bag_transition.py"
PREREG = ROOT / "computations" / "matter-formation-smooth-bag-transition-prereg.md"
SCHEMA = "cassi.matter-formation.smooth-bag-transition-verification.v1"
CHECK_NAMES = (
    "finite_grid_receipts",
    "positive_pair_number",
    "positive_bound_occupation",
    "particle_hole_agreement",
    "localized_bound_mode",
    "mode_metric",
    "static_control",
    "grid_pair_convergence",
    "grid_bound_convergence",
    "grid_spatial_convergence",
)

PRIMARY_SCHEMA = "cassi.matter-formation.smooth-bag-transition.v1"
V = 1.0
G = 6.0
RADIUS = 16.0
AMPLITUDE = 1.5
WIDTH = 2.5
SWITCH_TIME = 2.0
FINAL_TIME = 12.0
GRIDS = {
    "G0": (48, RADIUS / 48.0, 0.002),
    "G1": (72, RADIUS / 72.0, 0.001),
    "G2": (96, RADIUS / 96.0, 0.0005),
}
CHECKPOINTS = np.asarray((0.0, SWITCH_TIME, 4.0, 8.0, FINAL_TIME), dtype=np.float64)


class VerificationError(RuntimeError):
    pass


def canonical_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def raw_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, np.integer)):
        return True
    if isinstance(value, (float, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(isinstance(k, str) and finite_tree(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_tree(v) for v in value)
    return False


def write_exclusive(path: Path, payload: Any) -> None:
    if path.exists():
        raise VerificationError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def radial_grid(n: int) -> tuple[np.ndarray, float]:
    dr = RADIUS / n
    return (np.arange(n, dtype=np.float64) + 0.5) * dr, dr


def smooth_bump(s: float) -> float:
    if s <= 0.0:
        return 0.0
    if s >= 1.0:
        return 1.0
    left = math.exp(-1.0 / s)
    right = math.exp(-1.0 / (1.0 - s))
    return left / (left + right)


def profile(t: float, radius: np.ndarray, amplitude: float = AMPLITUDE) -> np.ndarray:
    return V - amplitude * smooth_bump(t / SWITCH_TIME) * np.exp(-0.5 * (radius / WIDTH) ** 2)


def assemble_hamiltonian(sigma: np.ndarray, dr: float) -> np.ndarray:
    n = sigma.size
    h = np.zeros((2 * n, 2 * n), dtype=np.complex128)
    for i in range(n):
        h[i, i] = G * sigma[i]
        h[n + i, n + i] = -G * sigma[i]
        h[i, n + i] += -1.0 / ((i + 0.5) * dr)
        h[n + i, i] += -1.0 / ((i + 0.5) * dr)
        if i + 1 < n:
            d = 1.0 / (2.0 * dr)
            h[i, n + i + 1] -= d
            h[i + 1, n + i] += d
            h[n + i, i + 1] += d
            h[n + i + 1, i] -= d
    if not np.allclose(h, h.conj().T, atol=1.0e-13, rtol=0.0):
        raise VerificationError("independent Hamiltonian is not Hermitian")
    return h


def metric_basis(h: np.ndarray, dr: float, negative: bool) -> tuple[np.ndarray, np.ndarray]:
    values, vectors = np.linalg.eigh(h)
    n = h.shape[0] // 2
    selected = values < -1.0e-10 if negative else values > 1.0e-10
    if int(np.count_nonzero(selected)) != n:
        raise VerificationError("independent energy split mismatch")
    columns = vectors[:, selected] / math.sqrt(dr)
    if float(np.max(np.abs(dr * (columns.conj().T @ columns) - np.eye(n)))) > 2.0e-12:
        raise VerificationError("independent basis metric failure")
    return values[selected], columns


def apply_hamiltonian(u: np.ndarray, sigma: np.ndarray, radius: np.ndarray, dr: float) -> np.ndarray:
    n = radius.size
    upper, lower = u[:n], u[n:]
    d_upper = np.empty_like(upper)
    d_lower = np.empty_like(lower)
    d_upper[0] = upper[1] / (2.0 * dr)
    d_upper[1:-1] = (upper[2:] - upper[:-2]) / (2.0 * dr)
    d_upper[-1] = -upper[-2] / (2.0 * dr)
    d_lower[0] = lower[1] / (2.0 * dr)
    d_lower[1:-1] = (lower[2:] - lower[:-2]) / (2.0 * dr)
    d_lower[-1] = -lower[-2] / (2.0 * dr)
    return np.vstack((G * sigma[:, None] * upper - d_lower - lower / radius[:, None], d_upper - G * sigma[:, None] * lower - upper / radius[:, None]))


def independent_evolve(name: str, output: Path) -> tuple[dict[str, float], np.ndarray]:
    n, dr, dt = GRIDS[name]
    radius, _ = radial_grid(n)
    h0 = assemble_hamiltonian(profile(0.0, radius), dr)
    _, u0 = metric_basis(h0, dr, negative=True)
    y0 = u0.reshape(-1)

    def rhs(t: float, y: np.ndarray) -> np.ndarray:
        u = y.reshape(2 * n, n)
        return (-1j * apply_hamiltonian(u, profile(t, radius), radius, dr)).reshape(-1)

    solution = solve_ivp(
        rhs,
        (0.0, FINAL_TIME),
        y0,
        method="DOP853",
        t_eval=CHECKPOINTS,
        rtol=2.0e-9,
        atol=2.0e-11,
        max_step=0.02,
    )
    if not solution.success or solution.y.shape != (2 * n * n, CHECKPOINTS.size):
        raise VerificationError(f"DOP853 failure on {name}: {solution.message}")
    states = np.asarray([solution.y[:, i].reshape(2 * n, n) for i in range(CHECKPOINTS.size)], dtype=np.complex128)
    final = states[-1]
    hf = assemble_hamiltonian(profile(FINAL_TIME, radius), dr)
    values, vectors = np.linalg.eigh(hf)
    positive = values > 1.0e-10
    negative = values < -1.0e-10
    p = vectors[:, positive] / math.sqrt(dr)
    q = vectors[:, negative] / math.sqrt(dr)
    pair_coeff = dr * (p.conj().T @ final)
    hole_coeff = dr * (q.conj().T @ final)
    bound = p[:, :1]
    bound_hole = q[:, -1:]
    bound_coeff = dr * (bound.conj().T @ final)
    hole_bound_coeff = dr * (bound_hole.conj().T @ final)
    density = np.abs(bound[:n, 0]) ** 2 + np.abs(bound[n:, 0]) ** 2
    norm = float(np.sum(density) * dr)
    core = radius < 4.0
    result = {
        "grid": name,
        "N": n,
        "dr": dr,
        "dt": dt,
        "steps": round(FINAL_TIME / dt),
        "pair_number": float(np.sum(np.abs(pair_coeff) ** 2)),
        "bound_occupation": float(np.sum(np.abs(bound_coeff) ** 2)),
        "bound_hole_occupation": float(n - np.sum(np.abs(hole_bound_coeff) ** 2)),
        "pair_hole_gap": float(abs(np.sum(np.abs(pair_coeff) ** 2) - (n - np.sum(np.abs(hole_coeff) ** 2)))),
        "bound_energy": float(values[positive][0]),
        "negative_bound_energy": float(values[negative][-1]),
        "bound_core_probability": float(np.sum(density[core]) * dr / norm),
        "bound_rms_radius": math.sqrt(float(np.sum(radius * radius * density) * dr / norm)),
        "mode_metric_error": float(max(np.max(np.abs(dr * (state.conj().T @ state) - np.eye(n))) for state in states)),
        "final_profile_center_deficit": float(1.0 - profile(FINAL_TIME, radius)[0]),
    }
    archive = output / f"independent_{name}.npz"
    with archive.open("xb") as stream:
        np.savez_compressed(stream, time=CHECKPOINTS, u_re=states.real, u_im=states.imag)
    result["archive"] = archive.name
    result["archive_sha256"] = raw_sha(archive)
    return result, states


def static_control() -> dict[str, float]:
    n, dr, _ = GRIDS["G1"]
    radius, _ = radial_grid(n)
    h = assemble_hamiltonian(profile(0.0, radius, amplitude=0.0), dr)
    values, u = metric_basis(h, dr, negative=True)
    _, p = metric_basis(h, dr, negative=False)
    coeff = dr * (p.conj().T @ u)
    return {"pair_number": float(np.sum(np.abs(coeff) ** 2)), "bound_occupation": 0.0, "mode_metric_error": float(np.max(np.abs(dr * (u.conj().T @ u) - np.eye(n))))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    input_dir = args.input_dir.resolve()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise VerificationError(f"output directory is not empty: {output}")
    primary_path = input_dir / "results.json"
    if not primary_path.is_file():
        raise VerificationError(f"missing primary receipt {primary_path}")
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    if not isinstance(primary, dict) or primary.get("schema") != PRIMARY_SCHEMA:
        raise VerificationError("primary schema mismatch")
    if not finite_tree(primary):
        raise VerificationError("primary receipt is nonfinite")
    output.mkdir(parents=True, exist_ok=True)
    source_dir = output / "sources"
    source_dir.mkdir()
    for path in (SELF, PREREG):
        target = source_dir / relative(path).replace("/", "__")
        shutil.copyfile(path, target)
    independent: dict[str, dict[str, float]] = {}
    states: dict[str, np.ndarray] = {}
    for name in GRIDS:
        independent[name], states[name] = independent_evolve(name, output)
    control = static_control()
    comparisons: list[dict[str, Any]] = []
    for name in GRIDS:
        p = primary.get("runs", {}).get(name, {})
        q = independent[name]
        for key, tolerance in (("pair_number", 2.0e-3), ("bound_occupation", 2.0e-3), ("bound_hole_occupation", 2.0e-3), ("pair_hole_gap", 2.0e-3), ("bound_core_probability", 1.0e-2), ("bound_rms_radius", 1.0e-2), ("bound_energy", 2.0e-3)):
            actual = float(p.get(key, math.nan))
            expected = float(q[key])
            comparisons.append({"path": f"runs.{name}.{key}", "primary": actual, "independent": expected, "pass": math.isfinite(actual) and abs(actual - expected) <= tolerance})
        archive = input_dir / str(p.get("archive", ""))
        independent_archive = output / independent[name]["archive"]
        if not archive.is_file():
            comparisons.append({"path": f"runs.{name}.archive", "primary": "missing", "independent": independent[name]["archive"], "pass": False})
        else:
            with np.load(archive) as pa, np.load(independent_archive) as ia:
                for key in ("time", "u_re", "u_im"):
                    pass_array = pa[key].shape == ia[key].shape and float(np.max(np.abs(pa[key] - ia[key]))) <= 5.0e-4
                    comparisons.append({"path": f"runs.{name}.archive.{key}", "primary_max_abs": float(np.max(np.abs(pa[key] - ia[key]))) if pa[key].shape == ia[key].shape else None, "pass": pass_array})
    static_comparisons = []
    primary_control = primary.get("static_control", {})
    for key, tolerance in (("pair_number", 1.0e-10), ("bound_occupation", 1.0e-10), ("mode_metric_error", 1.0e-8)):
        actual = float(primary_control.get(key, math.nan))
        expected = float(control.get(key, math.nan))
        static_comparisons.append({"path": f"static_control.{key}", "primary": actual, "independent": expected, "pass": math.isfinite(actual) and math.isfinite(expected) and abs(actual - expected) <= tolerance})
    comparisons.extend(static_comparisons)
    checks = {
        "primary_schema": primary.get("schema") == PRIMARY_SCHEMA,
        "primary_source_identity": (
            isinstance(primary.get("source"), dict)
            and primary["source"].get("path") == relative(PRIMARY)
            and primary["source"].get("sha256") == canonical_sha(PRIMARY)
        ),
        "primary_protocol_identity": (
            primary.get("protocol") == relative(PREREG)
            and primary.get("protocol_sha256") == canonical_sha(PREREG)
        ),
        "primary_checks_present": (
            isinstance(primary.get("checks"), list)
            and len(primary["checks"]) == len(CHECK_NAMES)
            and [row.get("name") for row in primary["checks"]] == list(CHECK_NAMES)
            and all(isinstance(row, dict) and isinstance(row.get("pass"), bool) for row in primary["checks"])
            and all(row["pass"] is True for row in primary["checks"])
        ),
        "independent_positive_pair_number": all(row["pair_number"] > 0.05 for row in independent.values()),
        "independent_positive_bound_occupation": all(row["bound_occupation"] > 0.10 for row in independent.values()),
        "independent_particle_hole_agreement": all(row["pair_hole_gap"] < 0.02 for row in independent.values()),
        "independent_localized_bound_mode": all(row["bound_core_probability"] > 0.50 and row["bound_rms_radius"] < 5.0 for row in independent.values()),
        "independent_mode_metric": all(row["mode_metric_error"] < 1.0e-8 for row in independent.values()),
        "static_control": control["pair_number"] < 1.0e-10 and control["bound_occupation"] < 1.0e-10 and control["mode_metric_error"] < 1.0e-8,
        "independent_pair_convergence": all(abs(independent[name]["pair_number"] - independent[next_name]["pair_number"]) < 0.15 for name, next_name in zip(GRIDS, list(GRIDS)[1:])),
        "independent_bound_convergence": all(abs(independent[name]["bound_occupation"] - independent[next_name]["bound_occupation"]) < 0.15 for name, next_name in zip(GRIDS, list(GRIDS)[1:])),
        "independent_spatial_convergence": all(abs(independent[name]["bound_core_probability"] - independent[next_name]["bound_core_probability"]) < 0.10 and abs(independent[name]["bound_rms_radius"] - independent[next_name]["bound_rms_radius"]) < 0.25 for name, next_name in zip(GRIDS, list(GRIDS)[1:])),
        "all_comparisons": all(row["pass"] is True for row in comparisons),
    }
    passed = all(checks.values())
    payload = {
        "schema": SCHEMA,
        "primary_receipt": {"path": relative(primary_path), "sha256": raw_sha(primary_path)},
        "primary_source": primary.get("source"),
        "protocol": {"path": relative(PREREG), "sha256": canonical_sha(PREREG)},
        "verifier_source": {"path": relative(SELF), "sha256": canonical_sha(SELF)},
        "independent_runs": independent,
        "static_control": control,
        "comparisons": comparisons,
        "checks": [{"name": name, "pass": bool(value)} for name, value in checks.items()],
        "numerical_pass": passed,
        "scientific_verdict": "CAPTURED—conditional smooth vacuum-to-bound-state formation" if passed else "INCONCLUSIVE",
        "complete_physical_matter_formation": False,
        "failures": [name for name, value in checks.items() if not value],
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
    }
    write_exclusive(output / "verification.json", payload)
    print(json.dumps({"scientific_verdict": payload["scientific_verdict"], "checks": payload["checks"], "failures": payload["failures"]}, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
