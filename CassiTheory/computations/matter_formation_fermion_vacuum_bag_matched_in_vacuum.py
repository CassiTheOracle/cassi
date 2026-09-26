#!/usr/bin/env python3
"""Primary matched-in-vacuum regulated vacuum-to-bag formation calculation."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
from scipy.linalg import expm

ROOT = Path(__file__).resolve().parents[1]
COMPUTATIONS = ROOT / "computations"
SELF = Path(__file__).resolve()
BASE_PATH = COMPUTATIONS / "matter_formation_fermion_vacuum_bag.py"
PREREG = COMPUTATIONS / "matter-formation-fermion-vacuum-bag-matched-in-vacuum-prereg.md"
SCHEMA = "cassi.matter-formation.fermion-vacuum-bag-matched-in-vacuum.v1"
CACHE_TOLERANCE = 1.0e-12
MIDPOINT_CORRECTORS = 1

_spec = importlib.util.spec_from_file_location("cassi_matter_matched_primary_base", BASE_PATH)
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
_reference_sigma: np.ndarray | None = None


def matched_basis(
    sigma: np.ndarray, dr: float, coupling: float
) -> tuple[object, np.ndarray, np.ndarray, np.ndarray]:
    """Construct the finite-box vacuum of the actual initial scalar profile."""
    n = sigma.size
    hamiltonian = _base.dense_hamiltonian(sigma, dr, coupling)
    values, vectors = np.linalg.eigh(hamiltonian)
    negative = values < -1.0e-10
    positive = values > 1.0e-10
    if int(np.count_nonzero(negative)) != n or int(np.count_nonzero(positive)) != n:
        raise ValueError(f"matched initial spectrum is not split into {n}+{n} states")
    scale = 1.0 / np.sqrt(dr)
    negative_vectors = vectors[:, negative] * scale
    positive_vectors = vectors[:, positive] * scale
    metric_error = max(
        float(np.max(np.abs(dr * (negative_vectors.conj().T @ negative_vectors) - np.eye(n)))),
        float(np.max(np.abs(dr * (positive_vectors.conj().T @ positive_vectors) - np.eye(n)))),
    )
    if metric_error > 1.0e-12:
        raise ValueError(f"matched radial vacuum basis is not dr-orthonormal: {metric_error}")
    basis = _base.VacuumBasis(values, negative_vectors, positive_vectors)
    b0 = np.sum(np.abs(negative_vectors[:n]) ** 2 - np.abs(negative_vectors[n:]) ** 2, axis=1)
    _, _, volume, _ = _base.grid_arrays(n, dr)
    source0 = dr * b0 / volume
    return basis, hamiltonian, b0, source0


def matched_initial_state(
    n: int, dr: float, amplitude: float, zero_covariance: bool
) -> tuple[np.ndarray, np.ndarray, np.ndarray, object, np.ndarray, np.ndarray]:
    global _reference_sigma
    radius, _, _, _ = _base.grid_arrays(n, dr)
    sigma = _base.V - amplitude * np.exp(-0.5 * (radius / _base.WIDTH) ** 2)
    basis, h0, _b0, source0 = matched_basis(sigma, dr, _base.G_YUKAWA)
    modes0 = basis.negative.copy()
    modes = np.zeros_like(modes0) if zero_covariance else modes0.copy()
    _reference_sigma = sigma.copy()
    pi = np.zeros(n, dtype=np.float64)
    return sigma, pi, modes, basis, h0, source0


def matched_energy(
    sigma: np.ndarray,
    pi: np.ndarray,
    modes: np.ndarray,
    modes0: np.ndarray,
    h0: np.ndarray,
    dr: float,
    volume: np.ndarray,
    area: np.ndarray,
    source0: np.ndarray,
    coupling: float,
) -> tuple[float, float, float, float]:
    if _reference_sigma is None or _reference_sigma.shape != sigma.shape:
        raise RuntimeError("matched initial profile is unavailable for energy evaluation")
    scalar = _base.scalar_energy(sigma, pi, dr, volume, area)
    hamiltonian = _base.dense_hamiltonian(sigma, dr, coupling)
    dynamic = float(np.real(np.trace(modes.conj().T @ hamiltonian @ modes)) * dr)
    initial = float(np.real(np.trace(modes0.conj().T @ h0 @ modes0)) * dr)
    counterterm = float(coupling * np.sum(volume * source0 * (sigma - _reference_sigma)))
    fermion = dynamic - initial - counterterm
    mode_norm = float(np.real(np.trace(modes.conj().T @ modes)) * dr)
    return scalar + fermion, scalar, fermion, mode_norm


def propagators(sigma: np.ndarray, dt: float, dr: float, coupling: float) -> tuple[np.ndarray, np.ndarray]:
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
        _, half = propagators(sigma_mid, dt, dr, coupling)
        modes_mid = half @ modes
        midpoint_acceleration = _base.scalar_acceleration(
            sigma_mid, modes_mid, dr, volume, area, radius, b0, coupling, source_enabled
        )
        pi_new = pi + dt * midpoint_acceleration
        sigma_new = sigma + 0.5 * dt * (pi + pi_new)
    full, _ = propagators(0.5 * (sigma + sigma_new), dt, dr, coupling)
    return sigma_new, pi_new, full @ modes


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


_base.initial_state = matched_initial_state
_base.energy = matched_energy
_base.rk4_step = midpoint_step
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
        value["state_preparation"] = {
            "name": "matched_initial_profile_negative_energy_vacuum",
            "normal_ordering_reference": "same_initial_profile",
            "particle_projector": "same_initial_profile_positive_energy",
        }
    _original_writer(path, value)


_base.write_json_exclusive = write_json_exclusive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = _base.run(args.output_dir.resolve())
    except (FileExistsError, OSError, ValueError, FloatingPointError, RuntimeError) as exc:
        print(f"matched-in-vacuum primary failed before receipt: {exc}")
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output_dir.resolve()),
                "verdict": receipt["verdict"],
                "numerical_pass": receipt["numerical_pass"],
            }
        ),
        flush=True,
    )
    return 0 if receipt["numerical_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
