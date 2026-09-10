#!/usr/bin/env python3
"""Section 74 fixed-charge radial stationary pool profiles.

This builder computes the twelve charge/grid/seed endpoints that notebook
section 74 of computations/matter-formation-continuum-report.md requires
before any dispersal trajectory is run. It imports the spherical
finite-volume spatial energy and its exact cell gradient from
computations/matter_formation_radial.py unchanged and adds the prescribed
positive fixed-charge temporal terms

    N/(4a) + Q^2/(4a N),   N = sum(V c^2),

whose direct carrier gradient is 2 V c (1/(4a) - Q^2/(4a N^2)). Because
1/(4a) = B - e_C exactly for the kept coefficients, the reused radial
spatial energy plus N/(4a) is precisely the section 74.2 boxed spatial
functional with (B - h_C + h_C f^2) c^2; see the hand review.

Optimization uses the mass-weighted coordinates sqrt(V)*(f-1) and
sqrt(V)*c with the analytic gradient pullback, L-BFGS-B, bounds 0 <= f <= 1
and c >= 0, and the section 74 stopping settings. Qualification is decided
by the physical checks (stationary residuals of the section 74.2 equations,
charge reconstruction, outer-half population, binding inequalities, seed
agreement, refinement and domain tolerances), never by the optimizer
success flag. Every endpoint is saved as raw NPZ evidence with byte hashes.
A failed prerequisite yields an INCONCLUSIVE receipt; nothing is retuned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "computations") not in sys.path:
    sys.path.insert(0, str(ROOT / "computations"))

from matter_formation_radial import (  # noqa: E402  (sibling module import)
    COEFFICIENTS as RADIAL_COEFFICIENTS,
    Grid,
    finite_volume_energy_gradient,
    raw_sha256,
    write_json,
)

SCHEMA = "matter-formation-pool-profiles-v1"
MANIFEST_SCHEMA = "matter-formation-pool-dispersal-manifest-v1"
OWN_SOURCE = "computations/matter_formation_pool_profiles.py"
NOTEBOOK_PATH = "computations/matter-formation-continuum-report.md"
HEADING_74 = "## 74. Working notes: dispersal of a self-bound field pool"
HEADING_75 = "## 75. Working notes: controlled pool-dispersal experiment"

# Section 74.1 kept coefficients. The reused spatial energy reads its own
# coefficients from the radial module; the identity guard below pins parity.
A = 1.0 / 16.0
URHO = 4.0
UC = 1.0
K_CX = 1.0
EC = 0.75
HC = 2.9598260763447164
B = 4.75
OMEGA_INF = math.sqrt(B / A)

# Section 74.2 interior scales, used only by the declared seed.
N0 = math.sqrt(URHO / (2.0 * UC))
OMEGA0 = math.sqrt((B - HC + math.sqrt(URHO * UC / 2.0)) / A)

Q_DAUGHTER = 256.0
Q_PARENT = 512.0
CHARGES = (Q_DAUGHTER, Q_PARENT)
GRID_IDS = ("S0", "S1", "S2")
GRID_SPECS = {"S0": (24.0, 0.125), "S1": (24.0, 0.0625), "S2": (48.0, 0.0625)}
SEED_SCALES = (0.8, 1.2)
SELECTED = {"Q256": "q256_S1_s0", "Q512": "q512_S1_s0"}

# Section 74 tolerances. Fixed; not tunable at run time.
SEED_TOLERANCE = 1.0e-5
REFINEMENT_TOLERANCE = 2.0e-3
DOMAIN_TOLERANCE = 1.0e-5
RESIDUAL_TOLERANCE = 1.0e-5
CHARGE_TOLERANCE = 1.0e-10
OUTER_TOLERANCE = 1.0e-6
BINDING_FACTOR = 0.999

# Section 74.3 optimizer settings (identical to the radial campaign).
MAX_ITER = 50_000
MAX_EVAL = 200_000
FTOL = 1.0e-15
GTOL = 1.0e-9
MAXCOR = 50



class GuardError(RuntimeError):
    """Raised for any manifest, sealed-section, source, or output violation."""


def json_number(value: float | None) -> float | None:
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def resolve_cli_path(argument: str) -> Path:
    path = Path(argument).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def canonical_section_bytes(text: str, heading: str) -> bytes:
    """Extract heading through the next H2; normalize and rstrip per manifest."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    start = -1
    for index, line in enumerate(lines):
        if line.rstrip() == heading:
            start = index
            break
    if start < 0:
        raise GuardError(f"heading not found in live notebook: {heading!r}")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    body = "\n".join(lines[start:end]).rstrip()
    return (body + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_manifest(manifest_path: Path) -> None:
    """Validate schema, both sealed sections, and every frozen source byte."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GuardError(f"manifest unreadable: {error}") from error
    if not isinstance(manifest, dict):
        raise GuardError("manifest must be a JSON object")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise GuardError(f"manifest schema must be {MANIFEST_SCHEMA!r}")
    sections = manifest.get("sections")
    sources = manifest.get("sources")
    if not isinstance(sections, list) or not isinstance(sources, list):
        raise GuardError("manifest sections and sources must be arrays")

    seen_headings: set[str] = set()
    for entry in sections:
        if not isinstance(entry, dict):
            raise GuardError("manifest section entry must be an object")
        heading = entry.get("heading")
        path_value = entry.get("path")
        snapshot = entry.get("snapshot")
        digest = entry.get("sha256")
        if not all(isinstance(value, str)
                   for value in (heading, path_value, snapshot, digest)):
            raise GuardError(
                "manifest section entry requires string heading/path/snapshot/sha256")
        if heading in seen_headings:
            raise GuardError(f"duplicate manifest section heading: {heading!r}")
        seen_headings.add(heading)
        if path_value != NOTEBOOK_PATH:
            raise GuardError(
                f"manifest section {heading!r} must point at {NOTEBOOK_PATH!r}")
        try:
            live_text = (ROOT / path_value).read_text(encoding="utf-8")
            frozen_text = (ROOT / snapshot).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise GuardError(f"section file unreadable for {heading!r}: {error}") from error
        live_digest = sha256_bytes(canonical_section_bytes(live_text, heading))
        frozen_digest = sha256_bytes(canonical_section_bytes(frozen_text, heading))
        if live_digest != digest:
            raise GuardError(f"live section hash mismatch for {heading!r}")
        if frozen_digest != live_digest:
            raise GuardError(f"frozen snapshot differs from live section for {heading!r}")
    if seen_headings != {HEADING_74, HEADING_75}:
        raise GuardError("manifest must seal exactly the two required headings")

    source_paths: set[str] = set()
    for entry in sources:
        if not isinstance(entry, dict):
            raise GuardError("manifest source entry must be an object")
        path_value = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(path_value, str) or not isinstance(digest, str):
            raise GuardError("manifest source entry requires string path/sha256")
        source_path = ROOT / path_value
        if not source_path.is_file():
            raise GuardError(f"frozen source missing: {path_value}")
        if raw_sha256(source_path) != digest:
            raise GuardError(f"frozen source hash mismatch: {path_value}")
        if path_value in source_paths:
            raise GuardError(f"duplicate source entry: {path_value}")
        source_paths.add(path_value)
    required_sources = {
        OWN_SOURCE,
        "computations/matter_formation_pool_dispersal.py",
        "computations/verify_matter_formation_pool_dispersal.py",
        "computations/matter_formation_radial.py",
        "computations/matter_formation_radial_cloud.py",
        "computations/matter_formation_neutral_packets.py",
    }
    if not required_sources.issubset(source_paths):
        raise GuardError("source inventory incomplete")


@dataclass(frozen=True)
class MassWeighted:
    """Objective E(u,w) and analytic gradient in sqrt(V)-weighted coordinates."""

    grid: Grid
    q: float
    sqrt_v: np.ndarray
    inv_sqrt_v: np.ndarray

    @classmethod
    def build(cls, grid: Grid, q: float) -> "MassWeighted":
        sqrt_v = np.sqrt(grid.volumes)
        return cls(grid, float(q), sqrt_v, 1.0 / sqrt_v)

    def fields(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        n = self.grid.n
        u = np.asarray(x[:n], dtype=np.float64)
        w = np.asarray(x[n:], dtype=np.float64)
        f = 1.0 + u * self.inv_sqrt_v
        c = w * self.inv_sqrt_v
        return u, w, f, c

    def energy_and_gradient(
        self, x: np.ndarray
    ) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
        """Total section 74.2 energy, mass-weighted gradient, and fields."""
        _, _, f, c = self.fields(x)
        spatial, gf, gc = finite_volume_energy_gradient(f, c, self.grid)
        population = float(np.dot(self.grid.volumes, c * c))
        if not math.isfinite(population) or population <= 0.0:
            raise ValueError("carrier population is not positive")
        q2_over_4a = self.q * self.q / (4.0 * A)
        energy = spatial + population / (4.0 * A) + q2_over_4a / population
        # Direct carrier gradient of the added fixed-charge terms:
        #   d/dc [N/(4a) + Q^2/(4aN)] = 2 V c (1/(4a) - Q^2/(4a N^2)).
        gc = gc + 2.0 * self.grid.volumes * c * (
            1.0 / (4.0 * A) - q2_over_4a / (population * population))
        # Exact pullback through df = du/sqrt(V), dc = dw/sqrt(V).
        gradient = np.concatenate((gf * self.inv_sqrt_v, gc * self.inv_sqrt_v))
        return energy, gradient, f, c

    def objective(self, x: np.ndarray) -> tuple[float, np.ndarray]:
        energy, gradient, _, _ = self.energy_and_gradient(x)
        return energy, gradient


def seed_fields(grid: Grid, q: float, scale: float) -> tuple[np.ndarray, np.ndarray]:
    """Section 74.3 droplet seeds with wall radius scale*Rb and interior c^2 = n0."""
    radius_b = (3.0 * q / (8.0 * math.pi * A * OMEGA0 * N0)) ** (1.0 / 3.0)
    wall = np.tanh(grid.r - scale * radius_b)
    f = 0.5 * (1.0 + wall)
    c = math.sqrt(N0) * 0.5 * (1.0 - wall)
    return f, c


def save_profile(path: Path, grid: Grid, q: float, omega: float, energy: float,
                 f: np.ndarray, c: np.ndarray) -> str:
    """Atomically write the raw endpoint evidence schema and return its byte hash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp.npz")
    np.savez(
        temporary,
        r=np.asarray(grid.r, dtype=np.float64),
        volume=np.asarray(grid.volumes, dtype=np.float64),
        f=np.asarray(f, dtype=np.float64),
        c=np.asarray(c, dtype=np.float64),
        Q=np.asarray(float(q), dtype=np.float64),
        omega=np.asarray(float(omega), dtype=np.float64),
        energy=np.asarray(float(energy), dtype=np.float64),
        R=np.asarray(float(grid.R), dtype=np.float64),
        spacing=np.asarray(float(grid.dr), dtype=np.float64),
    )
    os.replace(temporary, path)
    return raw_sha256(path)


def endpoint_row(builder: MassWeighted, key: str, grid_id: str, seed_index: int,
                 output_dir: Path) -> dict[str, Any]:
    """Optimize one endpoint, compute section 74 diagnostics, save raw evidence."""
    grid = builder.grid
    q = builder.q
    seed = SEED_SCALES[seed_index]
    f0, c0 = seed_fields(grid, q, seed)
    x0 = np.concatenate(((f0 - 1.0) * builder.sqrt_v, c0 * builder.sqrt_v))
    bounds = [(float(-sqrt_v), 0.0) for sqrt_v in builder.sqrt_v]
    bounds += [(0.0, None)] * grid.n
    calls = 0

    def objective(x: np.ndarray) -> tuple[float, np.ndarray]:
        nonlocal calls
        calls += 1
        return builder.objective(x)

    row: dict[str, Any] = {
        "key": key, "Q": q, "grid": grid_id, "seed": seed,
        "R": float(grid.R), "spacing": float(grid.dr),
        "omega": None, "energy": None, "population": None, "rms": None,
        "outer_fraction": None, "residual_f": None, "residual_c": None,
        "charge_error": None, "archive": None, "archive_sha256": None,
        "qualified": False, "optimizer": {},
    }
    try:
        result = minimize(
            objective,
            x0,
            method="L-BFGS-B",
            jac=True,
            bounds=bounds,
            options={"maxiter": MAX_ITER, "maxfun": MAX_EVAL,
                     "ftol": FTOL, "gtol": GTOL, "maxcor": MAXCOR},
        )
        x = np.asarray(result.x, dtype=np.float64)
        energy, gradient, f, c = builder.energy_and_gradient(x)
        u, w, _, _ = builder.fields(x)
        population = float(np.dot(grid.volumes, c * c))
        omega = q / (2.0 * A * population)
        # Section 74.2 equations in mass-weighted coordinates:
        #   dE/du_i = sqrt(V_i) * (f-equation at cell i)
        #   dE/dw_i = 2 sqrt(V_i) * (c-equation at cell i)
        # so the raw mass-weighted gradient norms are the equation residuals
        # up to the factor of two that the boxed c-equation carries.
        residual_f = float(np.linalg.norm(gradient[:grid.n])) / max(
            1.0, float(np.linalg.norm(u)))
        residual_c = 0.5 * float(np.linalg.norm(gradient[grid.n:])) / max(
            1.0, math.sqrt(population))
        charge_reconstructed = 2.0 * A * population * omega
        charge_error = abs(charge_reconstructed - q) / q
        rms = math.sqrt(
            float(np.dot(grid.volumes, grid.r * grid.r * c * c)) / population)
        outer = grid.r > 0.5 * grid.R
        outer_fraction = float(
            np.dot(grid.volumes[outer], c[outer] * c[outer]) / population)
        arrays_finite = bool(
            np.all(np.isfinite(u)) and np.all(np.isfinite(w))
            and np.all(np.isfinite(f)) and np.all(np.isfinite(c))
            and np.all(np.isfinite(gradient))
        )
        scalars_finite = all(math.isfinite(value) for value in
                             (energy, omega, population, rms, outer_fraction,
                              residual_f, residual_c, charge_error))
        jac = np.asarray(getattr(result, "jac", np.array([], dtype=np.float64)),
                         dtype=np.float64)
        row.update({
            "omega": json_number(omega),
            "energy": json_number(energy),
            "population": json_number(population),
            "rms": json_number(rms),
            "outer_fraction": json_number(outer_fraction),
            "residual_f": json_number(residual_f),
            "residual_c": json_number(residual_c),
            "charge_error": json_number(charge_error),
            "optimizer": {
                "success": bool(result.success),
                "status": int(result.status),
                "message": str(result.message),
                "nit": int(getattr(result, "nit", 0)),
                "nfev": int(getattr(result, "nfev", calls)),
                "njev": int(getattr(result, "njev", calls)),
                "objective_calls": int(calls),
                "final_objective": json_number(float(result.fun)),
                "final_reduced_gradient_inf": json_number(
                    float(np.max(np.abs(jac)))) if jac.size else None,
            },
        })
        finite_ok = arrays_finite and scalars_finite
        if finite_ok:
            artifact = output_dir / (key + ".npz")
            row["archive"] = artifact.name
            row["archive_sha256"] = save_profile(
                artifact, grid, q, omega, energy, f, c)
        row["qualified"] = bool(
            finite_ok
            and charge_error < CHARGE_TOLERANCE
            and residual_f < RESIDUAL_TOLERANCE
            and residual_c < RESIDUAL_TOLERANCE
            and outer_fraction < OUTER_TOLERANCE
            and energy < BINDING_FACTOR * OMEGA_INF * q
            and omega < BINDING_FACTOR * OMEGA_INF
        )
    except Exception as error:
        row["optimizer"] = {
            "success": False, "status": -1,
            "message": f"endpoint aborted: {type(error).__name__}: {error}",
            "nit": 0, "nfev": int(calls), "njev": int(calls),
            "objective_calls": int(calls), "final_objective": None,
            "final_reduced_gradient_inf": None,
        }
        row["qualified"] = False
    return row


def relative_close(a: float | None, b: float | None, tolerance: float) -> bool:
    if a is None or b is None:
        return False
    if not (math.isfinite(a) and math.isfinite(b)):
        return False
    return abs(a - b) / max(1.0, abs(a), abs(b)) < tolerance


def build_checks(rows: list[dict[str, Any]]) -> dict[str, bool]:
    by_key = {row["key"]: row for row in rows}
    checks: dict[str, bool] = {}

    checks["coefficient_identity"] = bool(
        RADIAL_COEFFICIENTS["u_rho"] == URHO
        and RADIAL_COEFFICIENTS["u_C"] == UC
        and RADIAL_COEFFICIENTS["k_Cx"] == K_CX
        and RADIAL_COEFFICIENTS["e_C"] == EC
        and RADIAL_COEFFICIENTS["h_C"] == HC
        and (B - EC) == 1.0 / (4.0 * A)
    )
    expected_keys = [f"q{int(q)}_{gid}_s{seed_index}"
                     for q in CHARGES for gid in GRID_IDS for seed_index in (0, 1)]
    checks["twelve_rows"] = bool(
        len(rows) == 12
        and set(by_key) == set(expected_keys)
    )
    checks["all_rows_qualified"] = bool(
        len(rows) == 12 and all(row["qualified"] for row in rows))
    checks["finite_raw_evidence"] = bool(
        all(row["archive"] and row["archive_sha256"]
            and all(row[field] is not None for field in
                    ("omega", "energy", "population", "rms", "outer_fraction",
                     "residual_f", "residual_c", "charge_error"))
            for row in rows)
    )
    checks["charge_reconstruction"] = bool(
        all(row["charge_error"] is not None and row["charge_error"] < CHARGE_TOLERANCE
            for row in rows)
    )
    checks["stationary_residuals"] = bool(
        all(row["residual_f"] is not None and row["residual_c"] is not None
            and row["residual_f"] < RESIDUAL_TOLERANCE
            and row["residual_c"] < RESIDUAL_TOLERANCE for row in rows)
    )
    checks["outer_population"] = bool(
        all(row["outer_fraction"] is not None and row["outer_fraction"] < OUTER_TOLERANCE
            for row in rows)
    )
    checks["binding_inequalities"] = bool(
        all(row["energy"] is not None and row["omega"] is not None
            and row["energy"] < BINDING_FACTOR * OMEGA_INF * row["Q"]
            and row["omega"] < BINDING_FACTOR * OMEGA_INF for row in rows)
    )

    for q in CHARGES:
        for gid in GRID_IDS:
            low = by_key.get(f"q{int(q)}_{gid}_s0")
            high = by_key.get(f"q{int(q)}_{gid}_s1")
            checks[f"seed_agreement_q{int(q)}_{gid}"] = bool(
                low is not None and high is not None
                and all(relative_close(low[field], high[field], SEED_TOLERANCE)
                        for field in ("energy", "omega", "rms"))
            )
        for seed_index in (0, 1):
            s0 = by_key.get(f"q{int(q)}_S0_s{seed_index}")
            s1 = by_key.get(f"q{int(q)}_S1_s{seed_index}")
            s2 = by_key.get(f"q{int(q)}_S2_s{seed_index}")
            checks[f"refinement_q{int(q)}_s{seed_index}_S1_vs_S0"] = bool(
                s0 is not None and s1 is not None
                and all(relative_close(s1[field], s0[field], REFINEMENT_TOLERANCE)
                        for field in ("energy", "omega", "rms"))
            )
            checks[f"domain_q{int(q)}_s{seed_index}_S2_vs_S1"] = bool(
                s1 is not None and s2 is not None
                and all(relative_close(s2[field], s1[field], DOMAIN_TOLERANCE)
                        for field in ("energy", "omega", "rms"))
            )

    selected_rows = [by_key.get(SELECTED["Q256"]), by_key.get(SELECTED["Q512"])]
    checks["selected_references_qualified"] = bool(
        all(row is not None and row["qualified"] for row in selected_rows)
    )
    checks["reference_fission_energy_finite"] = (
        reference_fission_energy(rows) is not None)
    return checks


def reference_fission_energy(rows: list[dict[str, Any]]) -> float | None:
    """2 E_256 - E_512 on the fixed selected references; sign is not a bound."""
    by_key = {row["key"]: row for row in rows}
    daughter = by_key.get(SELECTED["Q256"])
    parent = by_key.get(SELECTED["Q512"])
    if daughter is None or parent is None:
        return None
    if daughter["energy"] is None or parent["energy"] is None:
        return None
    value = 2.0 * daughter["energy"] - parent["energy"]
    return value if math.isfinite(value) else None


def make_grid(gid: str) -> Grid:
    R, spacing = GRID_SPECS[gid]
    return Grid.make(R, int(round(R / spacing)))


def run_profiles(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    """Guarded full endpoint campaign; always returns a receipt-able payload."""
    try:
        manifest_sha = raw_sha256(manifest_path)
    except OSError:
        manifest_sha = None
    try:
        verify_manifest(manifest_path)
    except GuardError as error:
        print(f"manifest guard failed: {error}", file=sys.stderr)
        return {
            "schema": SCHEMA,
            "rows": [],
            "checks": {},
            "numeric_pass": False,
            "verdict": "INCONCLUSIVE",
            "selected": dict(SELECTED),
            "reference_fission_energy": None,
            "manifest_sha256": manifest_sha,
            "complete_physical_matter_formation": False,
        }

    rows: list[dict[str, Any]] = []
    for q in CHARGES:
        for gid in GRID_IDS:
            grid = make_grid(gid)
            for seed_index in (0, 1):
                key = f"q{int(q)}_{gid}_s{seed_index}"
                builder = MassWeighted.build(grid, q)
                rows.append(endpoint_row(builder, key, gid, seed_index, output_dir))

    checks = build_checks(rows)
    numeric_pass = bool(checks) and all(checks.values())
    verdict = ("SUPPORTS-conditional stationary pool references" if numeric_pass
               else "INCONCLUSIVE")
    return {
        "schema": SCHEMA,
        "rows": rows,
        "checks": checks,
        "numeric_pass": numeric_pass,
        "verdict": verdict,
        "selected": dict(SELECTED),
        "reference_fission_energy": reference_fission_energy(rows),
        "manifest_sha256": manifest_sha,
        "complete_physical_matter_formation": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True,
                        help="manifest JSON path (absolute or repository-relative)")
    parser.add_argument("--output", required=True,
                        help="fresh output directory for raw NPZ evidence and result.json")
    args = parser.parse_args(argv)
    manifest_path = resolve_cli_path(args.manifest)
    output_dir = resolve_cli_path(args.output)

    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"refusing to write into existing output directory: {output_dir}",
              file=sys.stderr)
        return 1

    receipt = run_profiles(manifest_path, output_dir)
    write_json(output_dir / "result.json", receipt)
    return 0 if receipt["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
