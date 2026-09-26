#!/usr/bin/env python3
"""Source-bound classical Gauss and temporal-parent comparison for notebook section 58.

Run after sealing both sources and their mathematical reviews:
python computations/matter_formation_charged_gauss.py --manifest PATH --output FRESH_DIR

This qualifies the declared charge source, fixed linear mode and periodic
solvability condition. No quantum state, physical particle or formation is selected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = "## 58. Working notes: neutral production in the surviving charged sector"
MANIFEST_SCHEMA = "matter-formation-charged-sector-manifest-v1"
VERDICT = "SUPPORTS-conditional neutral-production charge-spectrum constraint"
SOURCES = {
    "computations/matter_formation_charged_gauss.py",
    "computations/matter_formation_charged_conversion.py",
    "foundations/particle-stationary-action-closure.md",
}
BOUND = 1e-9


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path) -> str:
    return hashlib.sha256(canonical(path)).hexdigest()


def validate_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    section = manifest["section"]
    if section.get("path") != REPORT or section.get("heading") != HEADING:
        raise ValueError("unexpected notebook section")
    lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip() == HEADING]
    if len(starts) != 1:
        raise ValueError("section 58 must occur exactly once")
    start = starts[0]
    stop = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    live = ("".join(lines[start:stop]).rstrip() + "\n").encode("utf-8")
    if hashlib.sha256(live).hexdigest() != section["sha256"] or canonical(path.parent / section["snapshot"]) != live:
        raise ValueError("frozen or current section mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {row["path"] for row in sources} != SOURCES:
        raise ValueError("incomplete source bindings")
    for row in sources:
        # The sibling's bytes are used only for hashing, never parsed or imported.
        if digest(ROOT / row["path"]) != row["sha256"] or digest(path.parent / row["snapshot"]) != row["sha256"]:
            raise ValueError(f"source mismatch: {row['path']}")
    reviews = manifest["mathematical_reviews"]
    if len(reviews) != 2 or {row["role"] for row in reviews} != {"gauss", "conversion"}:
        raise ValueError("exactly two distinct mathematical review roles are required")
    for row in reviews:
        if row.get("accepted") is not True or digest(path.parent / row["snapshot"]) != row["sha256"]:
            raise ValueError(f"mathematical review is not qualified: {row['role']}")
    return manifest


def zero(expression) -> bool:
    return bool(sp.trigsimp(sp.simplify(sp.expand(expression))) == 0)


def numeric(matrix) -> np.ndarray:
    return np.array(matrix.tolist(), dtype=float)


def error(actual, reference) -> float:
    actual, reference = np.asarray(actual), np.asarray(reference)
    if actual.shape != reference.shape or not np.isfinite(actual).all() or not np.isfinite(reference).all():
        raise ValueError("nonfinite value or shape mismatch")
    return float(np.linalg.norm(actual-reference)/max(1., float(np.linalg.norm(reference))))


def exact_temporal() -> tuple[dict, dict, dict]:
    x, y, vx, vy, b, g = sp.symbols("x y vx vy B0 g", real=True)
    c, gamma, up, epsilon = sp.symbols("C gamma U_p epsilon", positive=True)
    chi = x+sp.I*y
    dt = vx+sp.I*vy-sp.I*g*b*chi
    density = x*x+y*y
    lagrangian = sp.expand(c*sp.conjugate(dt)*dt + sp.I*gamma/2*(sp.conjugate(chi)*dt-sp.conjugate(dt)*chi))
    source = sp.diff(lagrangian, b)
    target = g*(gamma*density-2*c*(x*(vy-g*b*x)-y*(vx+g*b*y)))
    canonical_dt = sp.sqrt(c)*(dt-sp.I*gamma/(2*c)*chi)
    canonical_form = sp.conjugate(canonical_dt)*canonical_dt-gamma**2/(4*c)*density
    canonical_source = -2*g*sp.im(sp.sqrt(c)*sp.conjugate(chi)*canonical_dt)
    gradients = sp.symbols("gradB0_1:4", real=True)
    rates = sp.symbols("dotB_1:4", real=True)
    electric = epsilon/2*sum((gradient-rate)**2 for gradient, rate in zip(gradients, rates))
    displacement = [sp.diff(electric, gradient) for gradient in gradients]
    checks = {
        "real_component_variation_matches_source": zero(source-target),
        "first_order_source_is_g_gamma_density": zero(source.subs(c, 0)-g*gamma*density),
        "canonical_temporal_square": zero(lagrangian-canonical_form),
        "canonical_source": zero(source-canonical_source),
        "electric_variation_matches_displacement": all(zero(actual-epsilon*(gradient-rate)) for actual, gradient, rate in zip(displacement, gradients, rates)),
    }
    t, omega = sp.symbols("t omega", real=True)
    xr, yi = sp.Function("xr")(t), sp.Function("yi")(t)
    quadratic = c*(xr.diff(t)**2+yi.diff(t)**2)+gamma*(yi*xr.diff(t)-xr*yi.diff(t))-up*(xr*xr+yi*yi)
    euler = [sp.diff(sp.diff(quadratic, field.diff(t)), t)-sp.diff(quadratic, field) for field in (xr, yi)]
    wave = c*(xr+sp.I*yi).diff(t, 2)-sp.I*gamma*(xr+sp.I*yi).diff(t)+up*(xr+sp.I*yi)
    checks["real_equations_give_complex_wave"] = zero((euler[0]+sp.I*euler[1])/2-wave)
    trial = sp.exp(-sp.I*omega*t)
    mode_equation = sp.simplify((c*trial.diff(t, 2)-sp.I*gamma*trial.diff(t)+up*trial)/trial)
    polynomial = c*omega**2+gamma*omega-up
    checks["frequency_polynomial"] = zero(mode_equation+polynomial)
    delta = sp.sqrt(gamma**2+4*c*up)
    roots = [(-gamma+delta)/(2*c), (-gamma-delta)/(2*c)]
    weights = [sp.simplify(gamma+2*c*root) for root in roots]
    shifted = [sp.simplify(root+gamma/(2*c)) for root in roots]
    checks.update({
        "both_roots_solve_frequency_polynomial": all(zero(polynomial.subs(omega, root)) for root in roots),
        "charge_weights_are_opposite_discriminant_roots": all(zero(actual-expected) for actual, expected in zip(weights, (delta, -delta))),
        "canonical_frequencies_are_opposite": all(zero(actual-expected) for actual, expected in zip(shifted, (delta/(2*c), -delta/(2*c)))),
        "low_frequency_limit": zero(sp.limit(roots[0], c, 0, dir='+')-up/gamma),
        "opposite_branch_diverges_in_first_order_limit": bool(sp.limit(roots[1], c, 0, dir='+') == -sp.oo),
    })
    ap, am, angle = sp.symbols("A_plus A_minus relative_phase", real=True)
    # Expanding the bilinear source gives this cross coefficient. It vanishes
    # pointwise for the two roots of the same fixed linear-mode equation.
    mixed_source = g*(weights[0]*ap**2+weights[1]*am**2+2*ap*am*(gamma+c*(roots[0]+roots[1]))*sp.cos(angle))
    checks["two_mode_charge_cancellation_is_instantaneous"] = zero(mixed_source-g*delta*(ap**2-am**2))
    acceleration = [-(gamma*vy+up*x)/c, (gamma*vx-up*y)/c]
    checks["empty_parent_state_is_invariant"] = all(zero(value.subs({x: 0, y: 0, vx: 0, vy: 0})) for value in acceleration)
    witness = {gamma: 1, c: sp.Rational(1, 16), up: sp.Rational(1, 2)}
    exact_roots = numeric(sp.Matrix([sp.simplify(root.subs(witness)) for root in roots])).ravel()
    numerical_roots = np.sort(np.roots([1/16, 1., -1/2]))[::-1]
    discrepancy = error(numerical_roots, exact_roots)
    checks["numerical_frequency_witness"] = discrepancy <= BOUND
    identities = dict(source=str(source), canonical_current="-2*g*Im(conj(phi)*D_t(phi))",
                      frequency_polynomial=str(polynomial), roots=[str(root) for root in roots],
                      charge_weights=[str(weight) for weight in weights],
                      instantaneous_two_mode_charge=str(g*delta*(ap**2-am**2)),
                      frequency_witness_error=discrepancy,
                      scope="Fixed quadratic spatial mode; no nonlinear two-mode solution or physical charge normalization is inferred.")
    arrays = dict(parent_roots_exact=exact_roots, parent_roots_numeric=numerical_roots,
                  parent_charge_weights=numeric(sp.Matrix([weight.subs(witness) for weight in weights])).ravel(),
                  parent_canonical_frequencies=numeric(sp.Matrix([value.subs(witness) for value in shifted])).ravel())
    return checks, identities, arrays


def periodic_gauss() -> tuple[dict, list, dict]:
    matrix = sp.Matrix(4, 4, lambda i, j: int(i == (j+1) % 4)-int(i == j))
    ones = sp.ones(4, 1)
    # Fix the constant null direction while inverting the normal operator.
    lift = (matrix.T*matrix+ones*ones.T/4).inv()*matrix.T
    checks = {
        "constant_left_null_and_rank_three": bool(ones.T*matrix == sp.zeros(1, 4) and matrix.rank() == 3),
        "exact_uniform_residual_projector": bool(sp.eye(4)-matrix*lift == ones*ones.T/4),
        "exact_lift_is_mean_zero": bool(ones.T*lift == sp.zeros(1, 4)),
    }
    incidence = numeric(matrix)
    sources = np.array([[0., 0., 0., 0.], [1., 0., 0., 0.], [1., 0., -1., 0.]])
    arrays = dict(incidence_matrix=incidence, sources=sources, exact_lift=numeric(lift))
    displacements, original_residuals, neutralized_residuals, rows = [], [], [], []
    for index, (source, required_norm, admissible) in enumerate(zip(sources, (0., .5, 0.), (True, False, True))):
        displacement, _, _, _ = np.linalg.lstsq(incidence, source, rcond=None)
        original = incidence@displacement-source
        altered = incidence@displacement-(source-source.mean())
        residual_norm = float(np.linalg.norm(original))
        discrepancies = dict(displacement=error(displacement, numeric(lift)@source),
                             original_residual=error(original, -np.full(4, source.mean())),
                             residual_norm=error(residual_norm, required_norm),
                             altered_residual=error(altered, np.zeros(4)))
        checks[f"cycle_source_{index}"] = all(value <= BOUND for value in discrepancies.values()) and (residual_norm <= BOUND) == admissible
        rows.append(dict(source=source.tolist(), displacement=displacement.tolist(),
                         original_residual=original.tolist(), source_mean_subtracted_residual=altered.tolist(),
                         original_residual_norm=residual_norm, admissible=residual_norm <= BOUND,
                         errors=discrepancies))
        displacements.append(displacement)
        original_residuals.append(original)
        neutralized_residuals.append(altered)
    arrays.update(displacements=np.array(displacements), original_residuals=np.array(original_residuals),
                  source_mean_subtracted_residuals=np.array(neutralized_residuals))
    return checks, rows, arrays


def calculate() -> tuple[dict, dict]:
    checks, identities, arrays = exact_temporal()
    cycle_checks, rows, cycle_arrays = periodic_gauss()
    checks.update(cycle_checks)
    arrays.update(cycle_arrays)
    if not all(np.isfinite(value).all() for value in arrays.values()):
        raise ValueError("nonfinite raw arrays")
    receipt = dict(checks={key: bool(value) for key, value in checks.items()}, identities=identities,
                   rows=rows, numerical_maxima={"relative_equality_error": max(
                       identities['frequency_witness_error'], *(value for row in rows for value in row['errors'].values()))},
                   complete_physical_matter_formation=False)
    return receipt, arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        print(json.dumps(dict(verdict="INCONCLUSIVE", error="output directory already exists",
                              numeric_pass=False, complete_physical_matter_formation=False)))
        return 1
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema="matter-formation-charged-gauss-v1", role="gauss", verdict="INCONCLUSIVE",
                   numeric_pass=False, checks={}, rows=[], complete_physical_matter_formation=False)
    try:
        manifest = validate_manifest(args.manifest)
        receipt.update(manifest_sha256=digest(args.manifest), source_sha256=digest(Path(__file__)),
                       section_sha256=manifest['section']['sha256'])
        result, arrays = calculate()
        receipt.update(result)
        passed = all(value is True for value in result['checks'].values())
        np.savez_compressed(args.output / "arrays.npz", **arrays)
        receipt.update(numeric_pass=passed, verdict=VERDICT if passed else "INCONCLUSIVE",
                       arrays_sha256=hashlib.sha256((args.output / "arrays.npz").read_bytes()).hexdigest())
        text = json.dumps(receipt, indent=2, allow_nan=False)
    except Exception as exc:
        receipt.update(numeric_pass=False, verdict="INCONCLUSIVE", error=f"{type(exc).__name__}: {exc}")
        text = json.dumps(receipt, indent=2, allow_nan=False)
    (args.output / "result.json").write_text(text+"\n", encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in ('verdict', 'numeric_pass', 'error', 'complete_physical_matter_formation')}))
    return 0 if receipt['numeric_pass'] else 1


if __name__ == "__main__":
    raise SystemExit(main())
