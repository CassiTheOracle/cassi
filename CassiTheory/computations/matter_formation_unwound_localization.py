#!/usr/bin/env python3
"""Exact continuum trial integrals for matter-formation notebook section 49.

Run with --manifest PATH --output FRESH_DIR after sealing the declared sources.
This computes comparison fields; it does not minimize or evolve a field.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = "computations/matter-formation-continuum-report.md"
HEADING = "## 49. Working notes:"
MANIFEST_SCHEMA = "matter-formation-unwound-localization-manifest-v1"
SOURCES = {
    "computations/matter_formation_unwound_localization.py",
    "computations/verify_matter_formation_unwound_localization.py",
    "foundations/particle-stationary-action-closure.md",
}
COMPONENTS = (
    "fundamental_gradient", "adjoint_gradient", "gauge_energy",
    "density_potential", "composition_potential", "adjoint_potential",
    "carrier_gradient", "carrier_interaction", "carrier_quartic",
)
RADII = (0, 1, 4, 16, 64)
VOLUME_FACTORS = (2, 8)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_manifest(path: Path) -> str:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["schema"] != MANIFEST_SCHEMA:
        raise ValueError("manifest schema mismatch")
    section = manifest["section"]
    if section["path"] != NOTEBOOK or section["heading"] != HEADING:
        raise ValueError("section identity mismatch")
    snapshot = (path.parent / section["snapshot"]).read_bytes()
    if hashlib.sha256(snapshot).hexdigest() != section["sha256"]:
        raise ValueError("section snapshot hash mismatch")
    text = snapshot.decode("utf-8")
    if not text.startswith(HEADING) or text not in (ROOT / NOTEBOOK).read_text(encoding="utf-8"):
        raise ValueError("live notebook does not contain frozen section")
    records = manifest["sources"]
    if len(records) != len(SOURCES) or {item["path"] for item in records} != SOURCES:
        raise ValueError("source schedule mismatch")
    for item in records:
        if digest(ROOT / item["path"]) != item["sha256"]:
            raise ValueError(f"live source mismatch: {item['path']}")
        if digest(path.parent / item["snapshot"]) != item["sha256"]:
            raise ValueError(f"source snapshot mismatch: {item['path']}")
    return digest(path)


def exact_calculation() -> dict:
    rho, s, rho0, lr, lc, eta = sp.symbols("rho s rho0 lr lc eta", positive=True)
    kx, kc, R, h, t, volume = sp.symbols("Kx KCx R h t volume", positive=True)
    bulk = rho0 * sp.sqrt(lr / (2 * lc))
    mu = rho0 * (sp.sqrt(lr * lc / 2) - eta)
    alpha = eta**2 / lr - lc / 2
    W = lr * (rho - rho0)**2 / 4 + eta * (rho - rho0) * s + lc * s**2 / 2
    coexistence_square = (sp.sqrt(lr) * (rho - rho0) / 2 + sp.sqrt(lc / 2) * s)**2
    coexistence_square += (eta - sp.sqrt(lr * lc / 2)) * rho * s
    lower_square = lr * (rho - rho0 + 2 * eta * s / lr)**2 / 4
    wall_W = W.subs({rho: rho0 * t**2, s: bulk * (1 - t)**2})
    wall_grand = sp.simplify(wall_W - mu * bulk * (1 - t)**2)
    A = kx * rho0 + kc * bulk
    D = lr * rho0**2 / 2 + eta * rho0 * bulk
    core_volume = 4 * sp.pi * R**3 / 3

    def integrate_wall(expression: sp.Expr) -> sp.Expr:
        return sp.simplify(4 * sp.pi * h * sp.integrate(sp.expand((R + h*t)**2 * expression), (t, 0, 1)))

    core = [sp.S.Zero] * len(COMPONENTS)
    core[3] = lr * rho0**2 / 4
    core[7] = -eta * rho0 * bulk
    core[8] = lc * bulk**2 / 2
    wall = [sp.S.Zero] * len(COMPONENTS)
    wall[0] = kx * rho0 / (2 * h**2)
    wall[3] = lr * rho0**2 * (t**2 - 1)**2 / 4
    wall[6] = kc * bulk / (2 * h**2)
    wall[7] = -eta * rho0 * (1 - t**2) * bulk * (1 - t)**2
    wall[8] = lc * bulk**2 * (1 - t)**4 / 2
    components = [sp.simplify(core_volume * a + integrate_wall(b)) for a, b in zip(core, wall)]
    population = sp.simplify(core_volume * bulk + integrate_wall(bulk * (1 - t)**2))
    energy = sp.simplify(sum(components))
    gradient = sp.simplify(components[0] + components[6])
    excess = sp.simplify(energy - mu * population)
    population_formula = 4 * sp.pi * bulk * (R**3/3 + h*R**2/3 + h**2*R/6 + h**3/30)
    excess_formula = 4 * sp.pi * ((A/(2*h) + D*h/30)*R**2 + (A/2 + D*h**2/30)*R + A*h/6 + D*h**3/105)
    dilation = {R: R * volume**sp.Rational(1, 3), h: h * volume**sp.Rational(1, 3)}
    radial = sp.symbols("radial", positive=True)
    tal_mass = sp.integrate(4 * sp.pi * radial**2 / (1 + radial**2)**3, (radial, 0, sp.oo))
    tal_gradient = sp.integrate(4 * sp.pi * radial**4 / (1 + radial**2)**3, (radial, 0, sp.oo))
    CS = (4 / sp.pi**2)**sp.Rational(1, 3) / sp.sqrt(3)
    N_low = kc**sp.Rational(3, 2) / (2 * alpha * CS**3 * sp.sqrt(-2 * mu))
    residuals = {
        "coexistence_square": W - mu*s - coexistence_square,
        "pointwise_quartic_lower_square": W + alpha*s**2 - lower_square,
        "wall_grand_polynomial": wall_grand - D*t**2*(1-t)**2,
        "exact_population_integral": population - population_formula,
        "exact_energy_excess_integral": excess - excess_formula,
        "dilation_population": population.subs(dilation, simultaneous=True) - volume*population,
        "dilation_energy": energy.subs(dilation, simultaneous=True) - volume*energy + (volume-volume**sp.Rational(1, 3))*gradient,
        "talenti_sixth_power_integral": tal_mass - sp.pi**2/4,
        "talenti_gradient_integral": tal_gradient - 3*sp.pi**2/4,
        "sobolev_constant": tal_mass**sp.Rational(1, 3)/tal_gradient - CS**2,
        "large_population_energy_ratio": sp.limit(energy/population, R, sp.oo) - mu,
        "surface_excess_limit": sp.limit(R*excess/population, R, sp.oo) - 3*(A/(2*h)+D*h/30)/bulk,
    }
    checks = {name: bool(sp.simplify(value) == 0) for name, value in residuals.items()}
    controls = []
    control_rho0 = sp.Rational(6, 5)
    sc = control_rho0/2
    delta = sp.symbols("delta", nonnegative=True)
    for coupling in (2, 4):
        low = sp.Rational(coupling - 2, 2)*s**2
        high = control_rho0**2/4 - control_rho0*s + coupling*s**2/2
        polynomial = sp.Poly(sp.expand(high.subs(s, sc+delta)), delta)
        check = bool(coupling >= 2 and all(coefficient >= 0 for coefficient in polynomial.all_coeffs()))
        checks[f"nonbinding_control_lambda_{coupling}"] = check
        controls.append({"lambda_C": coupling, "low_branch": str(low), "high_branch": str(high), "high_branch_in_s_minus_sc": str(polynomial.as_expr()), "nonnegative": check})
    substitutions = {rho0: sp.Rational(6, 5), lr: 1, lc: 1, eta: 1, kx: sp.Rational(83, 100), kc: 1, h: 1}
    constant_expressions = {"rho0": rho0, "Kx": kx, "KCx": kc, "lambda_rho": lr, "lambda_C": lc, "eta": eta,
                            "s_star": bulk, "mu_star": mu, "alpha": alpha, "sobolev_constant": CS, "N_low": N_low, "h": h}
    constants = {name: float(sp.N(value.subs(substitutions), 18)) for name, value in constant_expressions.items()}
    rows = []
    for radius in RADII:
        values = substitutions | {R: radius}

        def number(expression: sp.Expr) -> float:
            return float(sp.N(expression.subs(values), 18))

        row = {"R": radius, "population": number(population), "components": [number(v) for v in components],
               "gradient_energy": number(gradient), "energy": number(energy), "excess_energy": number(excess),
               "energy_per_population": number(energy/population), "dilations": []}
        for factor in VOLUME_FACTORS:
            expressions = {"population": population, "gradient_energy": gradient, "energy": energy, "excess_energy": excess}
            record = {"volume_factor": factor}
            for name, expression in expressions.items():
                record[name] = number(expression.subs(dilation, simultaneous=True).subs(volume, factor))
            record["components"] = [number(expression.subs(dilation, simultaneous=True).subs(volume, factor)) for expression in components]
            row["dilations"].append(record)
        rows.append(row)
        if radius in (16, 64):
            checks[f"negative_trial_R{radius}"] = row["energy"] < 0
    expressions = {"population": population, "energy": energy, "gradient": gradient, "excess": excess,
                   "mu_star": mu, "s_star": bulk, "N_low": N_low, "wall_grand": wall_grand,
                   "talenti_sixth_power": tal_mass, "talenti_gradient": tal_gradient}
    return {"constants": constants, "checks": checks, "controls": controls, "rows": rows,
            "component_names": list(COMPONENTS), "exact_expressions": {name: str(value) for name, value in expressions.items()}}


def all_finite(value: object) -> bool:
    if isinstance(value, dict):
        return all(all_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(all_finite(item) for item in value)
    return not isinstance(value, float) or math.isfinite(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    created = False
    try:
        args.output.mkdir(parents=True, exist_ok=False)
        created = True
        manifest_hash = validate_manifest(args.manifest)
        result = exact_calculation()
        result["checks"]["all_values_finite"] = all_finite(result)
        passed = all(result["checks"].values())
        result.update({"schema": "matter-formation-unwound-localization-v1", "manifest_sha256": manifest_hash,
                       "numeric_pass": passed, "verdict": "PASS" if passed else "INCONCLUSIVE",
                       "complete_physical_matter_formation": False})
        np.savez_compressed(args.output / "arrays.npz", R=np.array(RADII),
                            component_names=np.array(COMPONENTS),
                            components=np.array([row["components"] for row in result["rows"]]),
                            population=np.array([row["population"] for row in result["rows"]]),
                            energy=np.array([row["energy"] for row in result["rows"]]),
                            excess_energy=np.array([row["excess_energy"] for row in result["rows"]]),
                            volume_factors=np.array(VOLUME_FACTORS),
                            dilated_components=np.array([[item["components"] for item in row["dilations"]] for row in result["rows"]]),
                            dilated_population=np.array([[item["population"] for item in row["dilations"]] for row in result["rows"]]))
        result["raw_arrays_sha256"] = digest(args.output / "arrays.npz")
    except Exception as exc:
        result = {"schema": "matter-formation-unwound-localization-v1", "numeric_pass": False,
                  "verdict": "INCONCLUSIVE", "error": f"{type(exc).__name__}: {exc}",
                  "complete_physical_matter_formation": False}
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if created:
        (args.output / "result.json").write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
