#!/usr/bin/env python3
"""Independent raw-profile verifier for the minimum-droplet campaign."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PREREG = ROOT / "computations" / "matter_formation_minimum_droplet_prereg.md"
PRIMARY = ROOT / "computations" / "matter_formation_minimum_droplet.py"
RADIAL = ROOT / "computations" / "matter_formation_radial.py"
SCHEMA = "matter-formation-minimum-droplet-verification-v1"
A = 1.0 / 16.0
URHO = 4.0
UC = 1.0
HC = 2.9598260763447164
EC = 0.75
B = EC + 1.0 / (4.0 * A)
OMEGA_INF = math.sqrt(B / A)
RESIDUAL_TOL = 2.0e-5
OUTER_TOL = 1.0e-6
BINDING_MARGIN = 1.0e-4
RECONSTRUCTION_TOL = 1.0e-8


class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def strict_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationError(f"object required: {path}")
    return value


class IndependentGrid:
    def __init__(self, radius: float, spacing: float) -> None:
        self.R = float(radius)
        self.dr = float(spacing)
        self.n = int(round(self.R / self.dr))
        if abs(self.n * self.dr - self.R) > 1.0e-12 * self.R:
            raise VerificationError("grid does not tile radius")
        self.faces = np.arange(self.n + 1, dtype=np.float64) * self.dr
        self.r = (np.arange(self.n, dtype=np.float64) + 0.5) * self.dr
        self.volume = (4.0 * math.pi / 3.0) * (self.faces[1:] ** 3 - self.faces[:-1] ** 3)
        self.conductance = 4.0 * math.pi * self.faces[1:-1] ** 2 / self.dr
        self.boundary_conductance = 4.0 * math.pi * self.R**2 / (self.dr / 2.0)

    def gradient(self, field: np.ndarray, weight: float) -> float:
        difference = field[1:] - field[:-1]
        return 0.5 * weight * (float(np.dot(self.conductance, difference * difference)) + self.boundary_conductance * float(field[-1] ** 2))

    def laplacian(self, field: np.ndarray) -> np.ndarray:
        out = np.zeros_like(field)
        flux = self.conductance * (field[1:] - field[:-1])
        out[:-1] += flux
        out[1:] -= flux
        out[-1] -= self.boundary_conductance * field[-1]
        return out / self.volume

    def reconstructed(self, f: np.ndarray, c: np.ndarray, charge: float) -> dict[str, float]:
        if f.shape != (self.n,) or c.shape != (self.n,):
            raise VerificationError("profile shape mismatch")
        population = float(np.dot(self.volume, c * c))
        if population <= 0.0:
            raise VerificationError("profile population vanished")
        n = c * c
        potential = URHO / 4.0 * (f * f - 1.0) ** 2 + (B - HC + HC * f * f) * n + UC / 2.0 * n * n
        energy = self.gradient(f - 1.0, 1.0) + self.gradient(c, 1.0) + float(np.dot(self.volume, potential)) + charge * charge / (4.0 * A * population)
        residual_f = -self.laplacian(f - 1.0) + URHO * (f * f - 1.0) * f + 2.0 * HC * f * n
        residual_c = -0.5 * self.laplacian(c) + (B - HC + HC * f * f + UC * n - A * (charge / (2.0 * A * population)) ** 2) * c
        norm_f = max(1.0, math.sqrt(float(np.dot(self.volume, (f - 1.0) ** 2))))
        norm_c = max(1.0, math.sqrt(population))
        frequency = charge / (2.0 * A * population)
        rms = math.sqrt(float(np.dot(self.volume, self.r * self.r * n)) / population)
        outer = self.r > 0.5 * self.R
        outer_fraction = float(np.dot(self.volume[outer], n[outer]) / population)
        return {"energy": energy, "population": population, "omega": frequency, "residual_f": math.sqrt(float(np.dot(self.volume, residual_f * residual_f))) / norm_f, "residual_c": math.sqrt(float(np.dot(self.volume, residual_c * residual_c))) / norm_c, "rms": rms, "outer_fraction": outer_fraction, "binding_ratio": energy / (OMEGA_INF * charge), "charge_error": abs(2.0 * A * population * frequency - charge) / charge}


def verify_row(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    archive_name = row.get("archive")
    if archive_name is None:
        rejected = bool(row.get("stationary") is False and row.get("binding_witness") is False and "carrier population vanished" in str(row.get("error", "")))
        return {"tag": row.get("tag"), "archive": None, "checks": {"rejected_zero_population_seed": rejected}, "reconstructed": {}, "pass": rejected}
    archive = root / "stationary" / str(archive_name)
    if not archive.is_file():
        raise VerificationError(f"missing archive: {archive}")
    with np.load(archive, allow_pickle=False) as data:
        required = {"r", "volume", "f", "c", "Q", "omega", "energy", "R", "spacing"}
        if not required.issubset(set(data.files)):
            raise VerificationError(f"archive fields missing: {archive}")
        f = np.asarray(data["f"], dtype=np.float64)
        c = np.asarray(data["c"], dtype=np.float64)
        charge = float(np.asarray(data["Q"]).item())
        grid = IndependentGrid(float(np.asarray(data["R"]).item()), float(np.asarray(data["spacing"]).item()))
        reconstructed = grid.reconstructed(f, c, charge)
    checks: dict[str, bool] = {}
    for name in ("energy", "population", "omega", "residual_f", "residual_c", "rms", "outer_fraction", "binding_ratio", "charge_error"):
        if row.get(name) is None:
            checks[name] = False
        else:
            checks[name] = abs(float(row[name]) - reconstructed[name]) <= RECONSTRUCTION_TOL * max(1.0, abs(reconstructed[name]))
    stationary = bool(reconstructed["residual_f"] < RESIDUAL_TOL and reconstructed["residual_c"] < RESIDUAL_TOL and reconstructed["charge_error"] < 1.0e-10)
    binding = bool(stationary and reconstructed["outer_fraction"] < OUTER_TOL and reconstructed["binding_ratio"] < 1.0 - BINDING_MARGIN and reconstructed["omega"] < OMEGA_INF * (1.0 - BINDING_MARGIN))
    checks["classification"] = bool(bool(row.get("stationary")) == stationary and bool(row.get("binding_witness")) == binding and bool(row.get("qualified")) == binding)
    checks["archive_hash"] = bool(row.get("archive_sha256") == sha256(archive))
    return {"tag": row.get("tag"), "archive": archive.name, "checks": checks, "reconstructed": reconstructed, "pass": bool(all(checks.values()))}


def mutation_control(root: Path, row: dict[str, Any]) -> bool:
    archive = root / "stationary" / str(row["archive"])
    with np.load(archive, allow_pickle=False) as data:
        arrays = {name: np.array(data[name], copy=True) for name in data.files}
    arrays["c"][0] *= 1.05
    mutated = root / "_verification_mutation.npz"
    np.savez_compressed(mutated, **arrays)
    try:
        with np.load(mutated, allow_pickle=False) as data:
            grid = IndependentGrid(float(np.asarray(data["R"]).item()), float(np.asarray(data["spacing"]).item()))
            rebuilt = grid.reconstructed(np.asarray(data["f"], dtype=np.float64), np.asarray(data["c"], dtype=np.float64), float(np.asarray(data["Q"]).item()))
        return abs(rebuilt["energy"] - float(row["energy"])) > 1.0e-8
    finally:
        mutated.unlink(missing_ok=True)


def run(input_dir: Path, output_path: Path) -> dict[str, Any]:
    receipt = strict_json(input_dir / "result.json")
    if receipt.get("schema") != "matter-formation-minimum-droplet-primary-v1":
        raise VerificationError("primary schema mismatch")
    if receipt.get("protocol_sha256") != sha256(PREREG):
        raise VerificationError("protocol hash mismatch")
    source_receipt = receipt.get("source_sha256", {})
    source_checks = {path.relative_to(ROOT).as_posix(): source_receipt.get(path.relative_to(ROOT).as_posix()) == digest for path, digest in ((PRIMARY, sha256(PRIMARY)), (RADIAL, sha256(RADIAL)), (PREREG, sha256(PREREG)))}
    rows = list(receipt.get("rows", [])) + list(receipt.get("midpoint_rows", []))
    details = [verify_row(input_dir, row) for row in rows]
    mutation = mutation_control(input_dir, next((row for row in rows if row.get("archive")), None)) if rows else False
    analytic_rejected = bool(receipt.get("analytic_bound", {}).get("analytic_no_binding_bound_accepted") is False and "diverges" in str(receipt.get("analytic_bound", {}).get("rejection", "")))
    result = {"schema": SCHEMA, "primary": str(input_dir), "protocol_sha256": sha256(PREREG), "source_checks": source_checks, "row_count": len(details), "rows": details, "rejection_control_mutated_archive_rejected": mutation, "analytic_bound_rejected": analytic_rejected, "global_minimum_charge_established": False, "physical_size_map_established": False, "gravitational_capture_established": False, "complete_physical_matter_formation": False}
    result["numeric_pass"] = bool(all(source_checks.values()) and details and all(item["pass"] for item in details) and mutation and analytic_rejected)
    write_json(output_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "20260911_matter_formation_minimum_droplet")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    output = args.output or (args.input / "verification.json")
    result = run(args.input.resolve(), output.resolve())
    print(json.dumps({"output": str(output.resolve()), "numeric_pass": result["numeric_pass"], "row_count": result["row_count"]}))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
