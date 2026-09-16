#!/usr/bin/env python3
"""Minimum-charge search for the supplied three-dimensional scalar droplet.

The calculation is deliberately scoped to the real-mediator/complex-carrier
parent action.  It searches a fixed-charge variational family, reconstructs
its observables from raw radial profiles, and records a sufficient analytic
no-binding bound separately from the searched numerical onset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "computations") not in sys.path:
    sys.path.insert(0, str(ROOT / "computations"))

from matter_formation_radial import (  # noqa: E402
    COEFFICIENTS,
    Grid,
    finite_volume_energy_gradient,
)

SELF = Path(__file__).resolve()
PREREG = ROOT / "computations" / "matter_formation_minimum_droplet_prereg.md"
SCHEMA = "matter-formation-minimum-droplet-primary-v1"
A = 1.0 / 16.0
CPSI = 1.0 / 8.0
URHO = 4.0
UC = 1.0
HC = float(COEFFICIENTS["h_C"])
EC = 0.75
B = EC + 1.0 / (4.0 * A)
OMEGA_INF = math.sqrt(B / A)
N0 = math.sqrt(URHO / (2.0 * UC))
OMEGA0 = math.sqrt((B - HC + math.sqrt(URHO * UC / 2.0)) / A)

CHARGES = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0)
GRID_SPECS = {"S0": (32.0, 0.125), "S1": (32.0, 0.0625), "S2": (64.0, 0.125)}
SEEDS = (0.8, 1.2)
RESIDUAL_TOL = 2.0e-5
OUTER_TOL = 1.0e-6
BINDING_MARGIN = 1.0e-4
SEED_TOL = 2.0e-5
SPACE_TOL = 5.0e-3
DOMAIN_TOL = 1.0e-3
MAX_ITER = 50_000
MAX_EVAL = 200_000
FTOL = 1.0e-15
GTOL = 1.0e-9
MAXCOR = 50


class ContractError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value: Any) -> bool:
    if isinstance(value, (float, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, (int, str, bool)) or value is None:
        return True
    if isinstance(value, np.ndarray):
        return bool(np.isfinite(value).all())
    if isinstance(value, dict):
        return all(finite(k) and finite(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite(item) for item in value)
    return False


def write_json(path: Path, value: dict[str, Any]) -> None:
    if not finite(value):
        raise ContractError(f"nonfinite JSON payload: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def snapshot_sources(output: Path) -> dict[str, str]:
    paths = (SELF, PREREG, ROOT / "computations" / "matter_formation_radial.py")
    source_dir = output / "sources"
    source_dir.mkdir(parents=True, exist_ok=False)
    result: dict[str, str] = {}
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        destination = source_dir / rel.replace("/", "__")
        shutil.copyfile(path, destination)
        result[rel] = sha256(path)
    return result


def protocol_hash() -> str:
    return sha256(PREREG)


def reduced_potential_minimum(n: np.ndarray | float) -> np.ndarray | float:
    values = np.asarray(n, dtype=np.float64)
    s = np.maximum(0.0, 1.0 - 2.0 * HC * values / URHO)
    result = URHO / 4.0 * (s - 1.0) ** 2 + (B - HC + HC * s) * values + UC / 2.0 * values**2
    return float(result) if np.ndim(n) == 0 else result


def analytic_bound() -> dict[str, float | bool | str | None]:
    """Record the attempted Sobolev bound and reject its invalid global form."""
    transition = URHO / (2.0 * HC)
    attractive = HC * HC / URHO - UC / 2.0
    n_star = (-4.0 * HC + math.sqrt(16.0 * HC * HC + 10.0 * UC * URHO)) / (2.0 * UC)
    # With W(n)=B*n-min_f V, the small-density branch is W(n)=h_C*n+O(n^2).
    # Therefore W(n)/n^(5/3) diverges as n -> 0.  A finite cutoff scan cannot
    # be promoted to a global Sobolev constant or a no-binding charge bound.
    sample = np.geomspace(1.0e-12, max(10.0, 4.0 * transition), 20_000)
    ratio = np.maximum(0.0, B * sample - reduced_potential_minimum(sample)) / sample ** (5.0 / 3.0)
    return {
        "transition_density": transition,
        "piecewise_attractive_coefficient": attractive,
        "candidate_maximizing_density": n_star,
        "finite_cutoff_ratio_at_1e-12": float(ratio[0]),
        "finite_cutoff_ratio_at_max_density": float(ratio.max()),
        "K": None,
        "N0": None,
        "Q0": None,
        "piecewise_bound_checked": False,
        "analytic_no_binding_bound_accepted": False,
        "rejection": "W(n)/n^(5/3) diverges as n approaches zero for the declared W; no global K or Q0 is inferred.",
    }


@dataclass
class Builder:
    grid: Grid
    charge: float

    def unpack(self, vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        n = self.grid.n
        sqrt_v = np.sqrt(self.grid.volumes)
        f = 1.0 + np.asarray(vector[:n], dtype=np.float64) / sqrt_v
        c = np.asarray(vector[n:], dtype=np.float64) / sqrt_v
        return f, c

    def energy_gradient(self, vector: np.ndarray) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
        f, c = self.unpack(vector)
        spatial, gf, gc = finite_volume_energy_gradient(f, c, self.grid)
        population = float(np.dot(self.grid.volumes, c * c))
        if not math.isfinite(population) or population <= 0.0:
            raise ValueError("carrier population vanished")
        q2_over_4a = self.charge * self.charge / (4.0 * A)
        charge_term = q2_over_4a / population
        energy = spatial + population / (4.0 * A) + charge_term
        gc = gc + 2.0 * self.grid.volumes * c * (1.0 / (4.0 * A) - q2_over_4a / (population * population))
        sqrt_v = np.sqrt(self.grid.volumes)
        gradient = np.concatenate((gf / sqrt_v, gc / sqrt_v))
        return float(energy), gradient, f, c

    def objective(self, vector: np.ndarray) -> tuple[float, np.ndarray]:
        energy, gradient, _, _ = self.energy_gradient(vector)
        return energy, gradient


def compact_seed(grid: Grid, charge: float, scale: float) -> tuple[np.ndarray, np.ndarray]:
    radius = (3.0 * charge / (8.0 * math.pi * A * OMEGA0 * N0)) ** (1.0 / 3.0)
    wall = np.tanh(grid.r - scale * radius)
    f = 0.5 * (1.0 + wall)
    c = math.sqrt(N0) * 0.5 * (1.0 - wall)
    return np.clip(f, 0.0, 1.0), np.maximum(c, 0.0)


def diffuse_seed(grid: Grid, charge: float) -> tuple[np.ndarray, np.ndarray]:
    sigma = max(2.0, grid.R / 4.0)
    profile = np.exp(-0.5 * (grid.r / sigma) ** 2)
    f = 1.0 - 0.4 * np.exp(-0.5 * (grid.r / (1.5 * sigma)) ** 2)
    return f, profile


def optimize_endpoint(grid: Grid, charge: float, seed: str, seed_value: float, output: Path, tag: str) -> dict[str, Any]:
    builder = Builder(grid, charge)
    f0, c0 = compact_seed(grid, charge, seed_value) if seed == "compact" else diffuse_seed(grid, charge)
    sqrt_v = np.sqrt(grid.volumes)
    x0 = np.concatenate(((f0 - 1.0) * sqrt_v, c0 * sqrt_v))
    bounds = [(float(-v), 0.0) for v in sqrt_v] + [(0.0, None)] * grid.n
    calls = 0

    def objective(x: np.ndarray) -> tuple[float, np.ndarray]:
        nonlocal calls
        calls += 1
        return builder.objective(x)

    row: dict[str, Any] = {"tag": tag, "grid": {"R": grid.R, "n": grid.n, "spacing": grid.dr}, "charge": charge, "seed": seed, "seed_value": seed_value, "qualified": False}
    try:
        result = minimize(objective, x0, method="L-BFGS-B", jac=True, bounds=bounds,
                          options={"maxiter": MAX_ITER, "maxfun": MAX_EVAL, "ftol": FTOL, "gtol": GTOL, "maxcor": MAXCOR})
        energy, gradient, f, c = builder.energy_gradient(np.asarray(result.x, dtype=np.float64))
        population = float(np.dot(grid.volumes, c * c))
        omega = charge / (2.0 * A * population)
        charge_reconstructed = 2.0 * A * population * omega
        residual_f = float(np.linalg.norm(gradient[:grid.n])) / max(1.0, float(np.linalg.norm((f - 1.0) * sqrt_v)))
        residual_c = 0.5 * float(np.linalg.norm(gradient[grid.n:])) / max(1.0, math.sqrt(population))
        rms = math.sqrt(float(np.dot(grid.volumes, grid.r * grid.r * c * c)) / population)
        outer = grid.r > 0.5 * grid.R
        outer_fraction = float(np.dot(grid.volumes[outer], c[outer] * c[outer]) / population)
        values = (energy, population, omega, residual_f, residual_c, rms, outer_fraction)
        if not all(math.isfinite(float(value)) for value in values):
            raise FloatingPointError("nonfinite endpoint")
        binding_ratio = energy / (OMEGA_INF * charge)
        row.update({"energy": energy, "population": population, "omega": omega, "rms": rms,
                    "outer_fraction": outer_fraction, "binding_ratio": binding_ratio,
                    "charge_error": abs(charge_reconstructed - charge) / charge,
                    "residual_f": residual_f, "residual_c": residual_c,
                    "optimizer": {"success": bool(result.success), "status": int(result.status), "message": str(result.message), "nit": int(getattr(result, "nit", 0)), "nfev": int(getattr(result, "nfev", calls)), "calls": calls}})
        finite_ok = bool(np.isfinite(f).all() and np.isfinite(c).all() and np.isfinite(gradient).all())
        row["stationary"] = bool(finite_ok and residual_f < RESIDUAL_TOL and residual_c < RESIDUAL_TOL and row["charge_error"] < 1.0e-10)
        row["binding_witness"] = bool(row["stationary"] and outer_fraction < OUTER_TOL and binding_ratio < 1.0 - BINDING_MARGIN and omega < OMEGA_INF * (1.0 - BINDING_MARGIN))
        archive = output / f"{tag}.npz"
        np.savez_compressed(archive, r=grid.r, volume=grid.volumes, f=f, c=c, Q=np.asarray(charge), omega=np.asarray(omega), energy=np.asarray(energy), R=np.asarray(grid.R), spacing=np.asarray(grid.dr))
        row["archive"] = archive.name
        row["archive_sha256"] = sha256(archive)
        row["qualified"] = bool(row["binding_witness"])
    except Exception as error:
        row["error"] = f"{type(error).__name__}: {error}"
        row["stationary"] = False
        row["binding_witness"] = False
    write_json(output / f"{tag}.json", row)
    return row


def relative_error(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(1.0, abs(float(left)), abs(float(right)))


def compare_rows(rows: list[dict[str, Any]], charge: float, seed: str) -> dict[str, Any]:
    selected = [row for row in rows if row.get("charge") == charge and row.get("seed") == seed and row.get("binding_witness")]
    if len(selected) < 3:
        return {"charge": charge, "seed": seed, "pass": False, "reason": "missing qualified endpoints"}
    energies = [float(row["energy"]) for row in selected]
    radii = [float(row["rms"]) for row in selected]
    return {"charge": charge, "seed": seed, "pass": bool(max(relative_error(value, energies[0]) for value in energies[1:]) < SPACE_TOL and max(relative_error(value, radii[0]) for value in radii[1:]) < SPACE_TOL), "energy_relative_error": max(relative_error(value, energies[0]) for value in energies[1:]), "rms_relative_error": max(relative_error(value, radii[0]) for value in radii[1:]), "grids": [row["grid"] for row in selected]}


def run_smoke() -> int:
    grid = Grid.make(24.0, 384)
    charge = 256.0
    work = ROOT / "runs" / "_minimum_droplet_smoke"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    row = optimize_endpoint(grid, charge, "compact", 0.8, work, "smoke_q256")
    assert row.get("binding_witness") is True, row
    vacuum = np.zeros(grid.n)
    energy, _, _ = finite_volume_energy_gradient(np.ones(grid.n), vacuum, grid)
    assert energy == 0.0
    print(json.dumps({"smoke": "PASS", "reference_binding_ratio": row["binding_ratio"], "reference_rms": row["rms"]}))
    shutil.rmtree(work)
    return 0


def run_campaign(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    source_hashes = snapshot_sources(output)
    analytic = analytic_bound()
    stationary_dir = output / "stationary"
    stationary_dir.mkdir()
    rows: list[dict[str, Any]] = []
    for gid, (radius, spacing) in GRID_SPECS.items():
        grid = Grid.make(radius, int(round(radius / spacing)))
        for charge in CHARGES:
            for seed_value in SEEDS:
                rows.append(optimize_endpoint(grid, charge, "compact", seed_value, stationary_dir, f"q{int(charge)}_{gid}_c{str(seed_value).replace('.', 'p')}"))
        if gid == "S0":
            for charge in CHARGES:
                rows.append(optimize_endpoint(grid, charge, "diffuse", 0.0, stationary_dir, f"q{int(charge)}_{gid}_diffuse"))
    comparisons = [compare_rows(rows, charge, seed) for charge in CHARGES for seed in ("compact",)]
    by_charge = {charge: [row for row in rows if row.get("charge") == charge and row.get("grid") == {"R": 32.0, "n": 256, "spacing": 0.125} and row.get("binding_witness")] for charge in CHARGES}
    bracket = None
    for low, high in zip(CHARGES, CHARGES[1:]):
        low_bound = bool(by_charge[low])
        high_bound = bool(by_charge[high])
        if not low_bound and high_bound:
            bracket = [low, high]
            break
    midpoint_rows: list[dict[str, Any]] = []
    if bracket is not None:
        low, high = bracket
        for index in range(6):
            midpoint = 0.5 * (low + high)
            for gid, (radius, spacing) in GRID_SPECS.items():
                grid = Grid.make(radius, int(round(radius / spacing)))
                for seed_value in SEEDS:
                    midpoint_rows.append(optimize_endpoint(grid, midpoint, "compact", seed_value, stationary_dir, f"mid{index}_{midpoint:.8g}_{gid}_c{str(seed_value).replace('.', 'p')}"))
            qualified = all(row.get("binding_witness") for row in midpoint_rows[-6:]) and all(compare_rows(midpoint_rows[-6:], midpoint, "compact").get("pass", False) for _ in (0,))
            if qualified:
                high = midpoint
            else:
                low = midpoint
        bracket = [low, high]
    receipt = {"schema": SCHEMA, "protocol_sha256": protocol_hash(), "source_sha256": source_hashes, "coefficients": {"a": A, "c_psi": CPSI, "u_rho": URHO, "u_C": UC, "h_C": HC, "B": B, "omega_inf": OMEGA_INF}, "analytic_bound": analytic, "rows": rows, "midpoint_rows": midpoint_rows, "comparisons": comparisons, "searched_onset_bracket": bracket, "smallest_qualified_sampled_charge": min((row["charge"] for row in rows if row.get("binding_witness")), default=None), "global_minimum_charge_established": False, "physical_size_map_established": False, "gravitational_capture_established": False, "complete_physical_matter_formation": False, "library_versions": {"python": platform.python_version(), "numpy": np.__version__}}
    write_json(output / "result.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "20260911_matter_formation_minimum_droplet")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        return run_smoke()
    receipt = run_campaign(args.output.resolve())
    print(json.dumps({"output": str(args.output.resolve()), "smallest_qualified_sampled_charge": receipt["smallest_qualified_sampled_charge"], "searched_onset_bracket": receipt["searched_onset_bracket"], "analytic_Q0": receipt["analytic_bound"]["Q0"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
