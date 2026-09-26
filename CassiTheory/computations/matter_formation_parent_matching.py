#!/usr/bin/env python3
"""Source-bound scalar-parent matching for notebook section 64.

python computations/matter_formation_parent_matching.py --manifest PATH --output FRESH_DIR
Tree amplitudes are formal normalization coefficients, not calibrated rates.
The microscopic choice, interacting continuum and physical matter remain open.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = "## 64. Working notes: matching quantum conversion to the scalar action"
MANIFEST_SCHEMA = "matter-formation-parent-matching-manifest-v1"
VERDICT = "SUPPORTS-conditional scalar-parent production matching"
SOURCES = {
    "computations/matter_formation_parent_matching.py",
    "computations/verify_matter_formation_parent_trees.py",
    "computations/verify_matter_formation_parent_kinematics.py",
    "foundations/particle-stationary-action-closure.md",
}
H_KEYS = ("0", "2", "2.9598260763447164", "6")
U_RHO, U_C, K_CX, E_C = 4.0, 1.0, 1.0, 0.75
H_C = float(H_KEYS[2])
BOUND = 1e-9
MOMENTA = ((0., 0., 0.), (1., 0., 0.), (1., 2., -1.), (8., -3., 4.))


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path) -> str:
    return hashlib.sha256(canonical(path)).hexdigest()


def validate_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    item = manifest["section"]
    if item.get("path") != REPORT or item.get("heading") != HEADING:
        raise ValueError("unexpected section")
    lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip() == HEADING]
    if len(starts) != 1:
        raise ValueError("section must occur exactly once")
    start = starts[0]
    stop = next((i for i in range(start+1, len(lines)) if lines[i].startswith("## ")), len(lines))
    live = ("".join(lines[start:stop]).rstrip()+"\n").encode("utf-8")
    if hashlib.sha256(live).hexdigest() != item["sha256"] or canonical(ROOT/item["snapshot"]) != live:
        raise ValueError("frozen or current section mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {row["path"] for row in sources} != SOURCES:
        raise ValueError("incomplete or duplicated source bindings")
    for row in sources:
        if digest(ROOT/row["path"]) != row["sha256"] or digest(ROOT/row["snapshot"]) != row["sha256"]:
            raise ValueError(f"source mismatch: {row['path']}")
    reviews = manifest["mathematical_reviews"]
    if len(reviews) != 2 or {row["role"] for row in reviews} != {"trees", "kinematics"}:
        raise ValueError("incomplete or duplicated mathematical reviews")
    for row in reviews:
        review = ROOT/row["snapshot"]
        flags = [line.strip() for line in canonical(review).decode("utf-8").splitlines()
                 if line.strip().startswith("accepted:")]
        if row.get("accepted") is not True or digest(review) != row["sha256"] or flags != ["accepted: true"]:
            raise ValueError(f"mathematical review is not qualified: {row['role']}")
    return manifest


def relative_error(actual: float, expected: float) -> float:
    if not math.isfinite(actual) or not math.isfinite(expected):
        raise ValueError("nonfinite comparison")
    return abs(actual-expected)/max(1.0, abs(expected))


def exact_algebra() -> tuple[dict, dict]:
    a, c, norm, ur, uc, h, e, k = sp.symbols("a c N u_rho u_C h e k", positive=True)
    f = sp.symbols("f", real=True)
    n, z = sp.symbols("n z", nonnegative=True)
    B, v = e+1/(4*a), sp.sqrt(norm*c)
    m2, M2 = 2*ur/c, B/a
    lam3, lam4, g, g2 = 3*m2/v, 3*m2/v**2, 2*h/(a*v), 2*h/(a*v**2)
    sigma, field_norm = v*(f-1), norm*a*n
    original = ur*(f*f-1)**2/4+(B-h+h*f*f)*n+uc*n*n/2
    expanded = (m2*sigma**2/2+M2*field_norm+lam3*sigma**3/6+lam4*sigma**4/24
                +g*sigma*field_norm+g2*sigma**2*field_norm/2+uc*field_norm**2/(2*norm*a*a))
    displacement = sp.symbols("s", real=True)
    q = sp.symbols("q", real=True)
    carrier_real = q/sp.sqrt(2*norm*a)
    potential_in_coords = norm*original.subs({f: 1+displacement/v, n: carrier_real**2})
    checks = {
        "canonical_potential_identity": sp.simplify(expanded-norm*original) == 0,
        "mediator_mass_from_Hessian": sp.simplify(sp.diff(potential_in_coords, displacement, 2).subs({displacement: 0, q: 0})-m2) == 0,
        "carrier_mass_from_Hessian": sp.simplify(sp.diff(potential_in_coords, q, 2).subs({displacement: 0, q: 0})-M2) == 0,
        "equal_cone_mass_ratio": sp.simplify((m2/(4*M2)).subs(c, 2*a/k)-ur*k*a/(1+4*e*a)) == 0,
    }
    d = sp.symbols("d", nonnegative=True)
    unshifted = ur*(z-1)**2/4+(B-h+h*z)*n+uc*n*n/2
    for name, h_branch, constant, squares in (
        ("depleted", B+d, ur/4+d*d/uc,
         ur*(z-2)**2/8+(B+d)*z*n+uc*(n-2*d/uc)**2/4),
        ("positive_core", B-d, ur/4,
         ur*(z-2)**2/8+(B-d)*z*n+uc*n*n/4+d*n),
    ):
        remainder = unshifted.subs(h, h_branch)-ur*z*z/8-uc*n*n/4+constant
        checks[f"coercivity_{name}_identity"] = sp.expand(remainder-squares) == 0
    # The positive-core branch also requires the original h>=0 premise.
    t = sp.symbols("t", positive=True)
    cubic_ray = (m2*t*t/2+M2*t*t/2-lam3*t**3/6-g*t**3/2)
    checks["cubic_ray_leading_coefficient"] = sp.simplify(sp.Poly(cubic_ray, t).LC()+lam3/6+g/2) == 0
    mu, big, gg, vv = sp.symbols("m2 M2 g v", positive=True)
    l3, l4, gg2 = sp.symbols("lambda3 lambda4 g2", positive=True)
    groups = {
        "charged_chain": 3*gg**3/(2*mu**2),
        "mixed_cubic": -gg**2*l3/mu**2,
        "mediator_chain": gg*l3**2/(8*mu**2),
        "mediator_quartic": gg*l4/(8*mu),
        "mixed_quartic": gg2*l3/mu,
        "charged_quartic": -3*gg*gg2/mu,
    }
    full3 = sum(groups.values())
    related = full3.subs({l3: 3*mu/vv, l4: 3*mu/vv**2, gg2: gg/vv})
    factored = 3*gg/(2*vv**2)*(gg*vv/mu-1)*(gg*vv/mu-3)
    checks["complete_tree_factorization"] = sp.factor(related-factored) == 0
    for root in (1, 3):
        checks[f"symbolic_nullification_x{root}"] = sp.simplify(related.subs(gg, root*mu/vv)) == 0
    full2 = gg2+l3*gg/(4*big-mu)+2*gg**2/(mu-2*big)
    couplings = {mu: m2, big: M2, gg: g, vv: v, l3: lam3, l4: lam4, gg2: g2}
    checks["two_tree_normalization_scaling"] = sp.simplify(sp.diff(norm*full2.subs(couplings, simultaneous=True), norm)) == 0
    checks["three_tree_normalization_scaling"] = sp.simplify(sp.diff(norm**sp.Rational(3, 2)*full3.subs(couplings, simultaneous=True), norm)) == 0
    cold_m, cold_M, speed, p = sp.symbols("m M speed p", positive=True)
    threshold = sp.sqrt(4*cold_M**2+speed*p*p)
    incoming = sp.sqrt(cold_m**2+speed*p*p)
    checks["all_momentum_deficit_identity"] = sp.simplify((threshold-incoming)*(threshold+incoming)-(4*cold_M**2-cold_m**2)) == 0
    checks["pair_boundary_is_one"] = sp.solve(sp.Eq(4*a/(1+3*a), 1), a) == [sp.Integer(1)]
    # The fixed reference permits 3 cold quanta and excludes 1 and 2.
    checks["cold_two_below_pair_threshold"] = sp.Integer(16)**2 < 4*sp.Integer(76)
    checks["cold_three_above_pair_threshold"] = sp.Integer(24)**2 > 4*sp.Integer(76)
    return {key: bool(value) for key, value in checks.items()}, {
        "canonical_potential_residual": str(sp.simplify(expanded-norm*original)),
        "F3_factorization": str(sp.factor(related)),
        "mass_ratio_equal_cone": str(ur*k*a/(1+4*e*a)),
        "normalization_scope": "F2*N and F3*N**(3/2) are formal coefficients; no rate or perturbative accuracy at N=1",
        "finite_cell_scope": "Real scalar restriction, finite positive N times cell volume, Friedrichs realization; no continuum or gauge-theory quantum reduction",
    }


def coefficients(a: float, c: float, h: float) -> dict:
    v = math.sqrt(c)
    m2, M2 = 2*U_RHO/c, (E_C+1/(4*a))/a
    g = 2*h/(a*v)
    return dict(v=v, m2=m2, M2=M2, g=g, g2=g/v, lambda3=3*m2/v, lambda4=3*m2/v**2)


def tree_rows(checks: dict) -> list[dict]:
    rows = []
    for key in H_KEYS:
        co = coefficients(1/16, 1/8, float(key))
        g, g2, l3, l4, mu, big, v = (co[name] for name in ("g", "g2", "lambda3", "lambda4", "m2", "M2", "v"))
        two = dict(contact=g2, mediator_exchange=l3*g/(4*big-mu), carrier_exchange=2*g*g/(mu-2*big))
        three = dict(charged_chain=3*g**3/(2*mu**2), mixed_cubic=-g*g*l3/mu**2,
                     mediator_chain=g*l3*l3/(8*mu**2), mediator_quartic=g*l4/(8*mu),
                     mixed_quartic=g2*l3/mu, charged_quartic=-3*g*g2/mu)
        F2, F3 = math.fsum(two.values()), math.fsum(three.values())
        x = g*v/mu
        factored = 3*g/(2*v*v)*(x-1)*(x-3)
        cubic = math.fsum(three[name] for name in ("charged_chain", "mixed_cubic", "mediator_chain"))
        checks[f"h{key}_factorized_F3"] = relative_error(F3, factored) <= BOUND
        if key == "0":
            checks["zero_coupling"] = F2 == 0 and F3 == 0 and cubic == 0
        elif key in ("2", "6"):
            checks[f"h{key}_full_cancellation"] = abs(F3) <= BOUND
            checks[f"h{key}_quartic_omission_breaks_cancellation"] = abs(cubic) > BOUND
        else:
            checks["selected_two_channel_nonzero"] = abs(F2) > BOUND
            checks["selected_three_channel_nonzero"] = abs(F3) > BOUND
        rows.append(dict(h_key=key, h=float(key), coefficients=co, two_groups=two, three_groups=three,
                         F2=F2, F3=F3, F3_cubic_only=cubic, F3_factored=factored, x=x))
    return rows


def threshold_rows(checks: dict) -> tuple[list, list, dict]:
    avac = 1/(4*(H_C-E_C-math.sqrt(U_RHO*U_C/2)))
    schedule = (("a_1_64", 1/64), ("a_1_32", 1/32), ("a_1_16", 1/16),
                ("a_vac_half", avac/2), ("a_vac", avac))
    checks["vacuum_boundary_below_pair_boundary"] = 0 < avac < 1
    kinematics, potentials = [], []
    for a_key, a in schedule:
        c, B = 2*a, E_C+1/(4*a)
        co = coefficients(a, c, H_C)
        mu, big, speed2 = co["m2"], co["M2"], 1/c
        ratio = mu/(4*big)
        checks[f"{a_key}_closed_one_mediator_channel"] = ratio < 1
        checks[f"{a_key}_classical_exterior_vacuum"] = H_C-B <= math.sqrt(U_RHO*U_C/2)+BOUND
        for idx, momentum in enumerate(MOMENTA):
            pnorm2 = sum(value*value for value in momentum)
            em, ep = math.sqrt(mu+speed2*pnorm2), math.sqrt(4*big+speed2*pnorm2)
            deficit, rational = ep-em, (4*big-mu)/(ep+em)
            checks[f"{a_key}_P{idx}_deficit_identity"] = relative_error(deficit, rational) <= BOUND and deficit > 0
            kinematics.append(dict(a_key=a_key, a=a, P=list(momentum), c=c, speed2=speed2, m2=mu, M2=big,
                                   ratio=ratio, mediator_energy=em, pair_threshold=ep, deficit=deficit,
                                   rationalized_deficit=rational, minimizer=[value/2 for value in momentum],
                                   minimized_energy=ep, gradient_at_minimum=[0., 0., 0.]))
        for f, n in itertools.product((-2., 0., 1., 3.), (0., 0.25, 2., 8.)):
            original = U_RHO/4*(f*f-1)**2+(B-H_C+H_C*f*f)*n+U_C*n*n/2
            sigma, field_norm = co["v"]*(f-1), a*n
            reconstructed = (mu*sigma*sigma/2+big*field_norm+co["lambda3"]*sigma**3/6
                             +co["lambda4"]*sigma**4/24+co["g"]*sigma*field_norm
                             +co["g2"]*sigma*sigma*field_norm/2+U_C*field_norm**2/(2*a*a))
            constant = U_RHO/4+max(H_C-B, 0.)**2/U_C
            lower = U_RHO*f**4/8+U_C*n*n/4-constant
            remainder = original-lower
            row_key = f"{a_key}_f{f}_n{n}"
            checks[row_key+"_canonical"] = relative_error(reconstructed, original) <= BOUND
            checks[row_key+"_coercive"] = remainder >= -BOUND*max(1., abs(original))
            checks[row_key+"_nonnegative_potential"] = original >= -BOUND*max(1., abs(original))
            potentials.append(dict(a_key=a_key, a=a, f=f, n=n, original=original, canonical=reconstructed,
                                   lower_bound=lower, coercivity_remainder=remainder))
    ref = coefficients(1/16, 1/8, H_C)
    m, M, speed2 = math.sqrt(ref["m2"]), math.sqrt(ref["M2"]), 8.
    pin, pout = math.sqrt((M*M-m*m)/speed2), math.sqrt(((3*m/2)**2-M*M)/speed2)
    checks["moving_pair_threshold"] = relative_error(pin, math.sqrt(3/2)) <= BOUND
    checks["three_mediator_outgoing_momentum"] = relative_error(pout, math.sqrt(17/2)) <= BOUND
    checks["minimum_cold_quanta"] = math.ceil(2*M/m) == 3
    return kinematics, potentials, dict(a_vac=avac, a_pair=1., ratio_at_a_vac=4*avac/(1+3*avac),
                                       m=m, M=M, pin_threshold=pin, pout_three=pout, cold_minimum_quanta=3)


def calculate() -> dict:
    checks, symbolic = exact_algebra()
    trees = tree_rows(checks)
    thresholds, potentials, bounds = threshold_rows(checks)
    checks["complete_tree_case_schedule"] = len(trees) == 4
    checks["complete_threshold_schedule"] = len(thresholds) == 20
    checks["complete_potential_schedule"] = len(potentials) == 80
    return dict(checks=checks, rows=trees, threshold_rows=thresholds, potential_rows=potentials,
                analytic_bounds=bounds, symbolic=symbolic,
                exclusions=["renormalized masses", "interacting bound-state thresholds", "absolute production rates",
                            "continuum quantum existence", "physical microscopic selection", "localized persistent matter"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # Never write into a pre-existing output directory.
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema="matter-formation-parent-matching-v1", role="primary", checks={}, rows=[],
                   numeric_pass=False, verdict="INCONCLUSIVE", complete_physical_matter_formation=False)
    try:
        manifest = validate_manifest(args.manifest)
        receipt.update(manifest_sha256=digest(args.manifest), source_bindings=manifest["sources"],
                       section_sha256=manifest["section"]["sha256"])
        receipt.update(calculate())
        passed = all(receipt["checks"].values())
        receipt.update(numeric_pass=passed, verdict=VERDICT if passed else "INCONCLUSIVE")
        text = json.dumps(receipt, allow_nan=False, indent=2)
    except Exception as exc:
        receipt = dict(schema="matter-formation-parent-matching-v1", role="primary", checks={}, rows=[],
                       numeric_pass=False, verdict="INCONCLUSIVE", error=f"{type(exc).__name__}: {exc}",
                       complete_physical_matter_formation=False)
        text = json.dumps(receipt, allow_nan=False, indent=2)
    (args.output/"result.json").write_text(text+"\n", encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in ("verdict", "numeric_pass", "error", "complete_physical_matter_formation")}, allow_nan=False))
    return 0 if receipt["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
