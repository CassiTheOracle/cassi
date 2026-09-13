#!/usr/bin/env python3
"""Primary unitary-midpoint recovery for regulated vacuum-to-bag formation.

The original RK4 trajectory leaks the negative-energy vacuum through the
finite-step mode update.  This recovery uses a source-bound, self-consistent
implicit midpoint update for the scalar and exact matrix-exponential
propagation for the occupied covariance frame.  The cached propagator is a
numerical reuse rule: it is refreshed whenever the midpoint scalar changes by
more than the frozen cache tolerance.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
from scipy.linalg import expm

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
BASE_PATH = ROOT / "computations" / "matter_formation_fermion_vacuum_bag.py"
PREREG = ROOT / "computations" / "matter-formation-fermion-vacuum-bag-unitary-recovery-prereg.md"
SCHEMA = "cassi.matter-formation.fermion-vacuum-bag-unitary-recovery.v1"
CACHE_TOLERANCE = 1.0e-12
MIDPOINT_CORRECTORS = 1

_spec = importlib.util.spec_from_file_location("cassi_matter_vacuum_bag_primary_base", BASE_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(BASE_PATH)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

_base.SELF = SELF
_base.PREREG = PREREG
_base.SCHEMA = SCHEMA

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
    """One self-consistent implicit-midpoint step.

    The scalar predictor supplies a midpoint guess.  One frozen corrector
    evaluates the source with the half-step unitary propagator and updates the
    midpoint.  The full propagator then advances the occupied frame.  The
    scheme is general for every arm; no arm-specific state is substituted.
    """
    acceleration = _base.scalar_acceleration(
        sigma, modes, dr, volume, area, radius, b0, coupling, source_enabled
    )
    sigma_new = sigma + dt * pi + 0.5 * dt * dt * acceleration
    pi_new = pi + dt * acceleration
    for _ in range(MIDPOINT_CORRECTORS):
        sigma_mid = 0.5 * (sigma + sigma_new)
        full, half = _propagators(sigma_mid, dt, dr, coupling)
        modes_mid = half @ modes
        midpoint_acceleration = _base.scalar_acceleration(
            sigma_mid, modes_mid, dr, volume, area, radius, b0, coupling, source_enabled
        )
        pi_new = pi + dt * midpoint_acceleration
        sigma_new = sigma + 0.5 * dt * (pi + pi_new)
    full, _ = _propagators(0.5 * (sigma + sigma_new), dt, dr, coupling)
    modes_new = full @ modes
    return sigma_new, pi_new, modes_new


_base.rk4_step = midpoint_step


def snapshot_sources(output: Path) -> dict[str, str]:
    source_dir = output / "sources"
    source_dir.mkdir(parents=False, exist_ok=False)
    result: dict[str, str] = {}
    for path in (SELF, PREREG, BASE_PATH):
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
        target = source_dir / relative.replace("/", "__")
        shutil.copyfile(path, target)
        result[relative] = _base.raw_sha(target)
    return result


_base.snapshot_sources = snapshot_sources
_original_writer = _base.write_json_exclusive


def write_json_exclusive(path: Path, value: dict[str, object]) -> None:
    if path.name == "result.json":
        value = dict(value)
        value["integrator"] = {
            "name": "self_consistent_implicit_midpoint_unitary_exponential",
            "midpoint_correctors": MIDPOINT_CORRECTORS,
            "propagator_cache_tolerance": CACHE_TOLERANCE,
        }
    _original_writer(path, value)


_base.write_json_exclusive = write_json_exclusive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = _base.run(args.output_dir.resolve())
    except (FileExistsError, OSError, ValueError, FloatingPointError) as exc:
        print(f"vacuum-bag unitary recovery primary failed before receipt: {exc}")
        return 1
    print(json.dumps({"output": str(args.output_dir.resolve()), "verdict": receipt["verdict"], "numerical_pass": receipt["numerical_pass"]}), flush=True)
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
