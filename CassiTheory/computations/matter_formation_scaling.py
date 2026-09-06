"""Describe prepared-population scaling without new field relaxation or verdicts.

Run from the CassiTheory root:
    python computations/matter_formation_scaling.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "runs/20260906_matter_formation_radial/results.json"
INPUT_HASH = "3ac6ec265c11d8eed2040c372d8862084be084ad0a640bbe0d8655e06e19a313"
PREREG = ROOT / "computations/matter-formation-scaling-prereg.md"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_difference(a: float, b: float) -> float:
    return abs(a - b) / max(1.0, abs(a), abs(b))


def describe(arm: dict) -> dict:
    path = ROOT / arm["artifact"]
    if sha256(path.read_bytes()) != arm["artifact_sha256"]:
        raise ValueError(f"Raw field hash mismatch: {path}")
    if arm["status"] != "complete":
        raise ValueError(f"Incomplete numerical endpoint: {arm['id']}")
    with np.load(path, allow_pickle=False) as raw:
        radius = raw["r"]
        volumes = raw["volumes"]
        mediator = raw["f"]
        density = np.square(raw["c"])
        population = float(np.dot(volumes, density))
        rms = float(np.sqrt(np.dot(volumes, density * radius**2) / population))
        minimum_f = float(np.min(mediator))
        peak_density = float(np.max(density))
    diagnostic = arm["diagnostics"]
    for label, actual, expected in (
        ("population", population, float(diagnostic["charge"])),
        ("radius", rms, float(diagnostic["carrier_radius"])),
    ):
        if relative_difference(actual, expected) > 1e-9:
            raise ValueError(f"Artifact {label} identity failed: {arm['id']}")
    prepared = float(arm["q"])
    energy = float(diagnostic["energy"])
    return {
        "id": arm["id"], "artifact": arm["artifact"],
        "artifact_sha256": arm["artifact_sha256"],
        "prepared_population": prepared, "population": population,
        "qualified": bool(diagnostic["qualified"]), "bound": bool(diagnostic["bound"]),
        "energy": energy, "energy_per_population": energy / prepared,
        "omega": float(diagnostic["omega"]), "carrier_radius": rms,
        "radius_per_population_cuberoot": rms / np.cbrt(prepared),
        "minimum_f": minimum_f, "peak_carrier_density": peak_density,
        "outer_fraction": float(diagnostic["outer_fraction"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "runs/20260906_matter_formation_scaling")
    args = parser.parse_args()
    destination = args.output_dir / "scaling.json"
    if destination.exists():
        raise FileExistsError(f"Refusing to replace {destination}")
    input_bytes = INPUT.read_bytes()
    if sha256(input_bytes) != INPUT_HASH:
        raise ValueError("The frozen radial input receipt has changed")
    receipt = json.loads(input_bytes)
    arms = {arm["id"]: arm for arm in receipt["arms"]}
    selected = [f"q{q}_R12_n768_refine" for q in (4, 16, 64, 256)]
    domain_ids = [f"q{q}_{suffix}_refine" for q in (4, 16, 256)
                  for suffix in ("R12_n384", "R24_n768")]
    rows = {identifier: describe(arms[identifier]) for identifier in selected + domain_ids}
    parameters = receipt["coefficients"]
    rho_u, carrier_u = float(parameters["u_rho"]), float(parameters["u_C"])
    e, h = float(parameters["e_C"]), float(parameters["h_C"])
    density_minimum = (h - e) / carrier_u
    saturated_density = float(np.sqrt(rho_u / (2 * carrier_u)))
    homogeneous = {
        "density_minimum_n": density_minimum,
        "density_minimum_energy_density": rho_u / 4 - (h - e)**2 / (2 * carrier_u),
        "density_derivative_at_minimum": e - h + carrier_u * density_minimum,
        "zero_pressure_density": saturated_density,
        "zero_pressure_energy_per_population": e - h + np.sqrt(rho_u * carrier_u / 2),
        "pressure_at_saturation": carrier_u * saturated_density**2 / 2 - rho_u / 4,
    }
    if abs(homogeneous["density_derivative_at_minimum"]) > 1e-12:
        raise ValueError("Homogeneous density minimizer identity failed")
    if abs(homogeneous["pressure_at_saturation"]) > 1e-12:
        raise ValueError("Homogeneous zero-pressure identity failed")
    domain = []
    for q in (4, 16, 256):
        small, large = (rows[f"q{q}_{suffix}_refine"]
                        for suffix in ("R12_n384", "R24_n768"))
        domain.append({
            "prepared_population": q,
            "R12_n384": small["id"], "R24_n768": large["id"],
            "energy_relative_difference": relative_difference(small["energy"], large["energy"]),
            "radius_relative_difference": relative_difference(small["carrier_radius"], large["carrier_radius"]),
        })
    single, fragment = rows[selected[3]], rows[selected[1]]
    if not all(row["qualified"] and row["bound"] for row in (single, fragment)):
        raise ValueError("The declared separated-lump comparison requires qualified bound inputs")
    partition = {
        "total_population": 256, "fragment_population": 16, "fragment_count": 16,
        "single_lump_energy": single["energy"],
        "separated_trial_energy": 16 * fragment["energy"],
        "separated_minus_single": 16 * fragment["energy"] - single["energy"],
        "scope": "Only this asymptotically separated partition; no dynamical or universal fission claim",
    }
    result = {
        "schema": "cassi.matter-formation.descriptive-scaling.v1",
        "source_sha256": sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "prereg_sha256": sha256(PREREG.read_bytes().replace(b"\r\n", b"\n")),
        "input_sha256": INPUT_HASH, "original_verdicts": receipt["verdicts"],
        "charge_rows": [rows[identifier] for identifier in selected],
        "domain_rows": [rows[identifier] for identifier in domain_ids],
        "domain_comparisons": domain, "homogeneous": homogeneous, "partition_trial": partition,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("Post-campaign descriptive calculation; no frozen verdict changes")
    print("Q qualified E/Q radius radius/Q^(1/3) min(f) max(c^2)")
    for row in result["charge_rows"]:
        print(f"{row['prepared_population']:g} {row['qualified']} "
              f"{row['energy_per_population']:.12g} {row['carrier_radius']:.12g} "
              f"{row['radius_per_population_cuberoot']:.12g} "
              f"{row['minimum_f']:.12g} {row['peak_carrier_density']:.12g}")
    print(json.dumps({"homogeneous": homogeneous, "partition_trial": partition,
                      "domain_comparisons": domain}, indent=2, allow_nan=False))
    print(f"Wrote {destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
