#!/usr/bin/env python3
"""Independent verifier for the unitary-midpoint vacuum-bag recovery."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import expm

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
SELF = Path(__file__).resolve()
PRIMARY = COMPUTATIONS / "matter_formation_fermion_vacuum_bag_unitary_recovery.py"
PREREG = COMPUTATIONS / "matter-formation-fermion-vacuum-bag-unitary-recovery-prereg.md"
BASE_PATH = COMPUTATIONS / "verify_matter_formation_fermion_vacuum_bag.py"
SCHEMA = "cassi.matter-formation.fermion-vacuum-bag-unitary-recovery-verification.v1"
PRIMARY_SCHEMA = "cassi.matter-formation.fermion-vacuum-bag-unitary-recovery.v1"
CACHE_TOLERANCE = 1.0e-12
MIDPOINT_CORRECTORS = 1

_spec = importlib.util.spec_from_file_location("cassi_matter_vacuum_bag_verifier_base", BASE_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(BASE_PATH)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

_base.SELF = SELF
_base.PRIMARY = PRIMARY
_base.PREREG = PREREG
_base.SCHEMA = SCHEMA
_base.PRIMARY_SCHEMA = PRIMARY_SCHEMA

_cache_sigma: np.ndarray | None = None
_cache_dt: float | None = None
_cache_dr: float | None = None
_cache_coupling: float | None = None
_cache_full: np.ndarray | None = None
_cache_half: np.ndarray | None = None


def _propagators(sigma: np.ndarray, dt: float, dr: float, coupling: float) -> tuple[np.ndarray, np.ndarray]:
    global _cache_sigma, _cache_dt, _cache_dr, _cache_coupling, _cache_full, _cache_half
    reusable = (
        _cache_sigma is not None
        and _cache_dt == dt
        and _cache_dr == dr
        and _cache_coupling == coupling
        and float(np.max(np.abs(sigma - _cache_sigma))) <= CACHE_TOLERANCE
    )
    if not reusable:
        hamiltonian = _base.dense_hamiltonian(sigma, dr, coupling)
        _cache_full = expm(-1j * dt * hamiltonian)
        _cache_half = expm(-0.5j * dt * hamiltonian)
        _cache_sigma = sigma.copy()
        _cache_dt = dt
        _cache_dr = dr
        _cache_coupling = coupling
    assert _cache_full is not None and _cache_half is not None
    return _cache_full, _cache_half


def midpoint_step(
    sigma: np.ndarray,
    pi: np.ndarray,
    modes: np.ndarray,
    dt: float,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    radius: np.ndarray,
    b0: np.ndarray,
    coupling: float,
    source_enabled: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    acceleration = _base.scalar_acceleration(
        sigma, modes, dr, volume, area, radius, b0, coupling, source_enabled
    )
    sigma_new = sigma + dt * pi + 0.5 * dt * dt * acceleration
    pi_new = pi + dt * acceleration
    for _ in range(MIDPOINT_CORRECTORS):
        sigma_mid = 0.5 * (sigma + sigma_new)
        _, half = _propagators(sigma_mid, dt, dr, coupling)
        modes_mid = half @ modes
        midpoint_acceleration = _base.scalar_acceleration(
            sigma_mid, modes_mid, dr, volume, area, radius, b0, coupling, source_enabled
        )
        pi_new = pi + dt * midpoint_acceleration
        sigma_new = sigma + 0.5 * dt * (pi + pi_new)
    full, _ = _propagators(0.5 * (sigma + sigma_new), dt, dr, coupling)
    return sigma_new, pi_new, full @ modes


def independent_evolve(
    output: Path,
    arm: str,
    n: int,
    dr: float,
    amplitude: float,
    source_enabled: bool,
    zero_covariance: bool,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Reconstruct the trajectory without importing the primary module."""
    global _cache_sigma, _cache_dt, _cache_dr, _cache_coupling, _cache_full, _cache_half
    _cache_sigma = None
    _cache_dt = None
    _cache_dr = None
    _cache_coupling = None
    _cache_full = None
    _cache_half = None
    radius, _, volume, area = _base.grid_arrays(n, dr)
    basis, h0, b0, source0 = _base.vacuum_basis(n, dr, _base.G_YUKAWA)
    modes0 = basis.negative.copy()
    modes = np.zeros_like(modes0) if zero_covariance else modes0.copy()
    sigma = _base.V - amplitude * np.exp(-0.5 * (radius / _base.WIDTH) ** 2)
    pi = np.zeros(n, dtype=np.float64)
    dt = float(_base.GRIDS[_base.arm_spec(arm)[0]][2])
    steps = int(round(_base.FINAL_TIME / dt))
    sample_steps = int(round(_base.SAMPLE_DT / dt))
    times: list[float] = [0.0]
    sigmas: list[np.ndarray] = [sigma.copy()]
    pis: list[np.ndarray] = [pi.copy()]
    mode_archive: list[np.ndarray] = [modes.copy()]
    diagnostics: list[dict[str, float]] = [
        _base.observables(sigma, pi, modes, modes0, basis, h0, radius, dr, volume, area, source0, _base.G_YUKAWA)
    ]
    for step in range(1, steps + 1):
        sigma, pi, modes = midpoint_step(
            sigma, pi, modes, dt, dr, volume, area, radius, b0, _base.G_YUKAWA, source_enabled
        )
        if step % sample_steps == 0 or step == steps:
            times.append(step * dt)
            sigmas.append(sigma.copy())
            pis.append(pi.copy())
            mode_archive.append(modes.copy())
            diagnostics.append(
                _base.observables(sigma, pi, modes, modes0, basis, h0, radius, dr, volume, area, source0, _base.G_YUKAWA)
            )
    time_array = np.asarray(times, dtype=np.float64)
    modes_array = np.asarray(mode_archive, dtype=np.complex128)
    raw = {
        "time": time_array,
        "sigma": np.asarray(sigmas, dtype=np.float64),
        "pi": np.asarray(pis, dtype=np.float64),
        "u_re": np.asarray(modes_array.real, dtype=np.float64),
        "u_im": np.asarray(modes_array.imag, dtype=np.float64),
    }
    archive_path = output / f"independent_{arm}.npz"
    with archive_path.open("xb") as stream:
        np.savez_compressed(stream, **raw)
    values = {key: np.asarray([row[key] for row in diagnostics], dtype=np.float64) for key in diagnostics[0]}
    late = time_array >= _base.LATE_START - 1.0e-12
    initial_energy = float(values["total_energy"][0])
    energy_error = np.abs(values["total_energy"] - initial_energy)
    row = {
        "arm": arm,
        "N": n,
        "dr": dr,
        "dt": dt,
        "amplitude": amplitude,
        "steps": steps,
        "duration": _base.FINAL_TIME,
        "initial_energy": initial_energy,
        "final_energy": float(values["total_energy"][-1]),
        "max_energy_error": float(np.max(energy_error)),
        "relative_energy_error": float(np.max(energy_error) / max(1.0, abs(initial_energy))),
        "late_means": {key: float(np.mean(value[late])) for key, value in values.items()},
        "late_std": {key: float(np.std(value[late])) for key, value in values.items()},
        "grid": _base.arm_spec(arm)[0],
        "candidate": arm.startswith("pulse_"),
        "source_enabled": source_enabled,
        "zero_covariance": zero_covariance,
    }
    row["captured"] = _base.capture_predicate(row) if row["candidate"] else False
    return row, raw


_base.independent_evolve = independent_evolve


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=False, exist_ok=False)
    result: dict[str, str] = {}
    for path in (SELF, PRIMARY, PREREG, BASE_PATH):
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
        target = source_dir / relative.replace("/", "__")
        shutil.copyfile(path, target)
        result[relative] = _base.raw_sha(target)
    return result


_base.snapshot_sources = snapshot_sources
_original_writer = _base.write_json_exclusive


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    if path.name == "verification.json":
        payload = dict(payload)
        payload["integrator"] = {
            "name": "self_consistent_implicit_midpoint_unitary_exponential",
            "midpoint_correctors": MIDPOINT_CORRECTORS,
            "propagator_cache_tolerance": CACHE_TOLERANCE,
        }
    _original_writer(path, payload)


_base.write_json_exclusive = write_json_exclusive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = _base.run(args.input_dir.resolve(), args.output.resolve())
    except (FileExistsError, OSError, ValueError, RuntimeError) as exc:
        print(f"vacuum-bag unitary recovery verifier failed before receipt: {exc}")
        return 1
    print(json.dumps({"output": str(args.output.resolve()), "verdict": receipt["verdict"], "numerical_pass": receipt["numerical_pass"]}), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
