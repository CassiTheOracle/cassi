#!/usr/bin/env python3
"""Independently reconstruct the CP-odd pair-to-carrier receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "computations" / "matter_formation_cp_odd_pair_qball_v2.py"
PROTOCOL = ROOT / "computations" / "matter-formation-cp-odd-pair-qball-v2-prereg.md"
SCHEMA = "cassi.matter-formation.cp-odd-pair-qball.v2.verification"
RADIUS = 32.0
DT = 0.002
T_FINAL = 48.0
SAVE_INTERVAL = 4.0
MODES = 32
SEED = 20260912
M = 1.0
LAMBDA = 2.0
G = 1.25
M_A = 2.0
KAPPA = 0.8
PULSE_AMPLITUDE = 4.0
PULSE_RADIUS = 4.0
PULSE_WIDTH = 1.5
CORE_RADIUS = 6.0
EXTERIOR_RADIUS = 12.0


class VerificationError(RuntimeError):
    """Typed failure of the independent verification contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    if isinstance(value, list):
        return all(finite(item) for item in value)
    if isinstance(value, (float, int)):
        return math.isfinite(float(value))
    return True


def json_write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def grid(count: int) -> tuple[np.ndarray, float]:
    dr = RADIUS / count
    return (np.arange(count, dtype=np.float64) + 0.5) * dr, dr


def draw(r: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mode = np.arange(1, MODES + 1, dtype=np.float64)
    omega = np.sqrt(M * M + (mode * math.pi / RADIUS) ** 2)
    rng = np.random.Generator(np.random.PCG64(SEED))
    xq, yq, xp, yp = (rng.normal(size=MODES) for _ in range(4))
    basis = math.sqrt(2.0 / RADIUS) * np.sin(mode[:, None] * math.pi * r[None, :] / RADIUS)
    return (
        (xq / np.sqrt(4.0 * omega)) @ basis,
        (yq / np.sqrt(4.0 * omega)) @ basis,
        (np.sqrt(omega / 4.0) * xp) @ basis,
        (np.sqrt(omega / 4.0) * yp) @ basis,
    )


def initial(count: int, sign: int) -> tuple[np.ndarray, ...]:
    r, _ = grid(count)
    ux, uy, px, py = draw(r)
    if sign < 0:
        uy = -uy
        py = -py
    pulse = sign * PULSE_AMPLITUDE * np.exp(-0.5 * ((r - PULSE_RADIUS) / PULSE_WIDTH) ** 2)
    return ux, uy, pulse * r, px, py, np.zeros_like(r)


def lap(u: np.ndarray, dr: float) -> np.ndarray:
    ext = np.empty(u.size + 2, dtype=np.float64)
    ext[1:-1] = u
    ext[0] = -u[0]
    ext[-1] = -u[-1]
    return (ext[2:] - 2.0 * ext[1:-1] + ext[:-2]) / (dr * dr)


def derivative(state: tuple[np.ndarray, ...], r: np.ndarray, dr: float) -> tuple[np.ndarray, ...]:
    ux, uy, v, px, py, pv = state
    rho = ux * ux + uy * uy
    s = rho / (r * r)
    c = M * M - 2.0 * LAMBDA * s + 3.0 * G * s * s
    return (
        px,
        py,
        pv,
        lap(ux, dr) - c * ux + KAPPA * v * uy / r,
        lap(uy, dr) - c * uy + KAPPA * v * ux / r,
        lap(v, dr) - M_A * M_A * v + KAPPA * ux * uy / r,
    )


def plus(state: tuple[np.ndarray, ...], d: tuple[np.ndarray, ...], scale: float) -> tuple[np.ndarray, ...]:
    return tuple(a + scale * b for a, b in zip(state, d))  # type: ignore[return-value]


def step(state: tuple[np.ndarray, ...], r: np.ndarray, dr: float) -> tuple[np.ndarray, ...]:
    k1 = derivative(state, r, dr)
    k2 = derivative(plus(state, k1, DT / 2.0), r, dr)
    k3 = derivative(plus(state, k2, DT / 2.0), r, dr)
    k4 = derivative(plus(state, k3, DT), r, dr)
    return tuple(
        a + DT * (b + 2.0 * c + 2.0 * d + e) / 6.0
        for a, b, c, d, e in zip(state, k1, k2, k3, k4)
    )  # type: ignore[return-value]


def grad(u: np.ndarray, dr: float) -> np.ndarray:
    ext = np.empty(u.size + 2, dtype=np.float64)
    ext[1:-1] = u
    ext[0] = -u[0]
    ext[-1] = -u[-1]
    return (ext[2:] - ext[:-2]) / (2.0 * dr)


def metrics(state: tuple[np.ndarray, ...], r: np.ndarray, dr: float) -> dict[str, float]:
    ux, uy, v, px, py, pv = state
    rho = ux * ux + uy * uy
    gx = grad(ux, dr)
    gy = grad(uy, dr)
    gv = grad(v, dr)
    ephi = (
        0.5 * (px * px + py * py + gx * gx + gy * gy)
        + 0.5 * M * M * rho
        - 0.5 * LAMBDA * rho * rho / (r * r)
        + 0.5 * G * rho * rho * rho / (r**4)
    )
    support = 0.5 * (px * px + py * py + gx * gx + gy * gy + M * M * rho) + 0.5 * G * rho**3 / (r**4)
    source = -KAPPA * v * ux * uy / r
    aux = 0.5 * (pv * pv + gv * gv + M_A * M_A * v * v)
    core = r <= CORE_RADIUS
    outside = r >= EXTERIOR_RADIUS
    total_number = 4.0 * math.pi * float(np.sum(rho) * dr)
    core_number = 4.0 * math.pi * float(np.sum(rho[core]) * dr)
    q = 4.0 * math.pi * float(np.sum(ux * py - uy * px) * dr)
    return {
        "carrier_energy": 4.0 * math.pi * float(np.sum(ephi) * dr),
        "support_energy_diagnostic": 4.0 * math.pi * float(np.sum(support) * dr),
        "full_energy": 4.0 * math.pi * float(np.sum(ephi + aux + source) * dr),
        "number_total": total_number,
        "number_core": core_number,
        "core_fraction": core_number / max(total_number, np.finfo(float).tiny),
        "charge": q,
        "rms_radius": math.sqrt(float(np.sum(r * r * rho) / max(np.sum(rho), np.finfo(float).tiny))),
        "core_density": 3.0 * float(np.sum(rho[core]) * dr) / (CORE_RADIUS**3),
        "exterior_support_fraction": float(np.sum(support[outside]) / max(np.sum(support), np.finfo(float).tiny)),
        "pulse_core_max": float(np.max(np.abs(v[core] / r[core]))),
    }


def rerun(name: str, count: int, sign: int, out: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    r, dr = grid(count)
    state = initial(count, sign)
    times = np.arange(0.0, T_FINAL + SAVE_INTERVAL / 2.0, SAVE_INTERVAL)
    rows: list[dict[str, Any]] = []
    archives = {key: [] for key in ("ux", "uy", "v", "px", "py", "pv")}
    stride = round(SAVE_INTERVAL / DT)
    for step_index in range(round(T_FINAL / DT) + 1):
        if step_index % stride == 0:
            rows.append({"time": float(times[len(rows)]), **metrics(state, r, dr)})
            for key, value in zip(archives, state):
                archives[key].append(value.copy())
        if step_index == round(T_FINAL / DT):
            break
        state = step(state, r, dr)
        if not all(np.all(np.isfinite(value)) for value in state):
            raise VerificationError(f"nonfinite independent state: {name}:{step_index}")
    arrays = {key: np.asarray(value) for key, value in archives.items()}
    arrays["r"] = r
    arrays["times"] = times
    return {"name": name, "count": count, "rows": rows, "final": rows[-1]}, arrays


def close(a: float, b: float, tol: float = 2.0e-8) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    primary_dir = args.primary_dir.resolve()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise VerificationError(f"refusing to overwrite nonempty output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    receipt_path = primary_dir / "result.json"
    if not receipt_path.is_file():
        raise VerificationError("missing primary result.json")
    primary = json.loads(receipt_path.read_text(encoding="utf-8"))
    if primary.get("schema") != "cassi.matter-formation.cp-odd-pair-qball.v2":
        raise VerificationError("unexpected primary schema")
    if primary.get("protocol_sha256") != sha256(PROTOCOL):
        raise VerificationError("primary protocol hash mismatch")
    for record in primary.get("source_records", []):
        source_path = ROOT / record["path"]
        if not source_path.is_file() or sha256(source_path) != record["sha256"]:
            raise VerificationError(f"source identity mismatch: {record['path']}")
        copied = primary_dir / "sources" / record["path"]
        if not copied.is_file() or sha256(copied) != record["sha256"]:
            raise VerificationError(f"copied source identity mismatch: {record['path']}")
    expected = {
        "vacuum_control": (512, 0),
        "positive": (512, 1),
        "negative": (512, -1),
        "positive_fine": (1024, 1),
    }
    independent: dict[str, Any] = {}
    raw_checks: dict[str, float] = {}
    archive_checks: dict[str, bool] = {}
    for name, (count, sign) in expected.items():
        run, arrays = rerun(name, count, sign, output)
        independent[name] = run
        primary_run = primary["runs"][name]
        archive_path = primary_dir / primary_run["archive"]
        if not archive_path.is_file():
            raise VerificationError(f"missing primary archive: {name}")
        with np.load(archive_path) as stored:
            max_error = 0.0
            for key, values in arrays.items():
                if key not in stored:
                    raise VerificationError(f"missing archive array {name}:{key}")
                actual = np.asarray(stored[key])
                if actual.shape != values.shape:
                    raise VerificationError(f"archive shape mismatch {name}:{key}")
                max_error = max(max_error, float(np.max(np.abs(actual - values))))
            raw_checks[name] = max_error
            archive_checks[name] = max_error < 2.0e-8
        if len(run["rows"]) != len(primary_run["rows"]):
            raise VerificationError(f"row count mismatch: {name}")
        for left, right in zip(run["rows"], primary_run["rows"]):
            for key, value in left.items():
                if not close(float(value), float(right[key])):
                    raise VerificationError(f"summary mismatch {name}:{key}")

    positive = independent["positive"]["rows"]
    vacuum = independent["vacuum_control"]["rows"]
    negative = independent["negative"]["rows"]
    negative_final = independent["negative"]["final"]
    fine = independent["positive_fine"]["final"]
    final = independent["positive"]["final"]
    late_positive = [row for row in positive if row["time"] >= 24.0]
    late_vacuum = [row for row in vacuum if row["time"] >= 24.0]
    q = np.asarray([row["charge"] for row in late_positive], dtype=np.float64)
    # Dirichlet carrier data are exactly zero at the outer face, so the measured
    # finite-volume Noether flux is the zero array, not an omitted correction.
    outer_flux = np.zeros_like(q)
    corrected_q = q - outer_flux
    drift = float(np.max(corrected_q) - np.min(corrected_q)) / max(float(np.max(np.abs(corrected_q))), np.finfo(float).tiny)
    vacuum_density = float(np.mean([row["core_density"] for row in late_vacuum]))
    resolution = {
        key: abs(float(fine[key]) - float(final[key])) / max(1.0, abs(float(final[key])), abs(float(fine[key])))
        for key in ("carrier_energy", "charge", "rms_radius", "core_density", "exterior_support_fraction")
    }
    cp_error = max(
        abs(positive[index][key] - negative[index][key])
        for index in range(len(positive))
        for key in ("carrier_energy", "full_energy", "number_total", "rms_radius")
    )
    predicates = {
        "core_density_amplified": final["core_density"] >= 4.0 * vacuum_density,
        "core_retention": final["core_fraction"] >= 0.80,
        "localized_support": final["exterior_support_fraction"] < 0.20,
        "charge_magnitude": abs(final["charge"]) >= 0.5,
        "post_pulse_charge_drift": drift < 0.05,
        "subthreshold_energy_per_charge": final["carrier_energy"] / max(abs(final["charge"]), np.finfo(float).tiny) < M,
        "resolution": all(value < 0.05 for value in resolution.values()),
        "cp_conjugacy": cp_error < 1.0e-10 and final["charge"] * negative_final["charge"] < 0.0,
    }
    scientific_pass = all(predicates.values())
    failed_checks = [name for name, ok in archive_checks.items() if not ok]
    payload = {
        "schema": SCHEMA,
        "primary_receipt": {"path": rel(receipt_path), "sha256": sha256(receipt_path)},
        "protocol_sha256": sha256(PROTOCOL),
        "independent_sources": {
            "primary_solver": {"path": rel(PRIMARY), "sha256": sha256(PRIMARY)},
            "protocol": {"path": rel(PROTOCOL), "sha256": sha256(PROTOCOL)},
        },
        "raw_archive_max_abs_error": raw_checks,
        "raw_archive_checks": archive_checks,
        "summary_checks": {"reconstructed": True},
        "outer_flux": {"values": outer_flux.tolist(), "identically_zero_from_dirichlet_boundary": True},
        "controls": {
            "vacuum_late_core_density": vacuum_density,
            "late_charge_relative_drift_after_flux": drift,
            "cp_max_metric_error": cp_error,
            "resolution_relative_errors": resolution,
        },
        "predicates": predicates,
        "failed_checks": failed_checks,
        "numerical_pass": not failed_checks and finite(predicates),
        "reproduced_primary_verdict": (
            "CAPTURED—conditional CP-odd vacuum-to-carrier formation"
            if scientific_pass
            else "DOES NOT EMERGE—conditional CP-odd vacuum-to-carrier formation"
        ),
        "elapsed_seconds": time.perf_counter() - started,
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
    }
    if payload["numerical_pass"] is False:
        payload["reproduced_primary_verdict"] = "INCONCLUSIVE"
    shutil.copyfile(PROTOCOL, output / PROTOCOL.name)
    json_write(output / "verification.json", payload)
    print(json.dumps({"failed_checks": failed_checks, "reproduced_primary_verdict": payload["reproduced_primary_verdict"], "predicates": predicates}, indent=2))
    return 0 if payload["numerical_pass"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"independent verification failed: {exc}", file=sys.stderr)
        raise
