#!/usr/bin/env python3
"""Independent nonrelativistic matching and positive-kernel bound for section 68.

python computations/verify_matter_formation_scalar_localization.py --manifest PATH --output FRESH_DIR
The finite-range quadrature includes its exact exponential tail. No sibling calculation is imported.
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
REPORT = "computations/matter-formation-continuum-report.md"
SCHEMA = "matter-formation-scalar-two-body-v1"
MANIFEST_SCHEMA = "matter-formation-scalar-two-body-manifest-v1"
VERDICT = "SUPPORTS-conditional scalar pair localization and annihilation constraints"
HEADINGS = {
    "## 64. Working notes: matching quantum conversion to the scalar action",
    "## 66. Working notes: quantum coupling normalization and radiative closure",
    "## 68. Working notes: scalar two-body localization and annihilation",
}
SOURCES = {
    "computations/matter_formation_scalar_two_body.py",
    "computations/verify_matter_formation_scalar_thresholds.py",
    "computations/verify_matter_formation_scalar_localization.py",
    "foundations/particle-stationary-action-closure.md",
}
N_VALUES = (1, 4, 16, 64)
H_KEYS = ("0", "2", "2.9598260763447164", "6")
TOL = 1e-9


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path) -> str:
    return hashlib.sha256(canonical(path)).hexdigest()


def validate_manifest(path: Path) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    sections = manifest["sections"]
    if len(sections) != 3 or {item["heading"] for item in sections} != HEADINGS:
        raise ValueError("incomplete or duplicate section bindings")
    lines = canonical(ROOT/REPORT).decode().splitlines(keepends=True)
    for item in sections:
        if item["path"] != REPORT:
            raise ValueError("unexpected section path")
        starts = [i for i, line in enumerate(lines) if line.rstrip() == item["heading"]]
        if len(starts) != 1:
            raise ValueError("section must occur exactly once")
        start = starts[0]
        stop = next((i for i in range(start+1, len(lines)) if lines[i].startswith("## ")), len(lines))
        live = ("".join(lines[start:stop]).rstrip()+"\n").encode()
        if hashlib.sha256(live).hexdigest() != item["sha256"] or canonical(ROOT/item["snapshot"]) != live:
            raise ValueError("frozen or live section mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {item["path"] for item in sources} != SOURCES:
        raise ValueError("incomplete or duplicate source bindings")
    for item in sources:
        if digest(ROOT/item["path"]) != item["sha256"] or digest(ROOT/item["snapshot"]) != item["sha256"]:
            raise ValueError("source mismatch: "+item["path"])
    reviews = manifest["mathematical_reviews"]
    if len(reviews) != 2 or {item["role"] for item in reviews} != {"thresholds", "localization"}:
        raise ValueError("incomplete or duplicate reviews")
    for item in reviews:
        snapshot = ROOT/item["snapshot"]
        flags = [line.strip() for line in canonical(snapshot).decode().splitlines() if line.strip().startswith("accepted:")]
        if item.get("accepted") is not True or flags != ["accepted: true"] or digest(snapshot) != item["sha256"]:
            raise ValueError("unaccepted mathematical review: "+item["role"])


def close(actual, expected) -> bool:
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    return bool(a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all()
                and np.linalg.norm(a-b)/max(1.0, float(np.linalg.norm(b))) <= TOL)


def zero(expression) -> bool:
    return sp.simplify(expression) == 0


def derive() -> dict:
    N, h = sp.symbols("N h", positive=True)
    a, cp, ur, uc, ec = sp.Rational(1, 16), sp.Rational(1, 8), sp.Integer(4), sp.Integer(1), sp.Rational(3, 4)
    c, v = 1/sp.sqrt(cp), sp.sqrt(N*cp)
    vh = c**sp.Rational(3, 2)*v
    mediator2, carrier2 = 2*ur/cp, (ec+1/(4*a))/a
    couplings = dict(c=c, m=sp.sqrt(mediator2), M=sp.sqrt(carrier2), vhat=vh,
                     kappa3=3*mediator2/v/c**sp.Rational(3, 2),
                     gamma=2*h/(a*v*c**sp.Rational(3, 2)),
                     L=3*mediator2/(v*v*c**3), P=2*h/(a*v*v*c**3), U=uc/(N*a*a*c**3))
    checks = {"parent_vacuum_masses": zero(mediator2-64) and zero(carrier2-76),
              "canonical_spatial_normalization": zero(vh*vh-2*sp.sqrt(2)*N)}

    # Normal-ordered particle/antiparticle symbols commute for coefficient extraction.
    A, Ac, B, Bc, z = sp.symbols("A Ac B Bc z")
    M, m, g, quartic = sp.symbols("M m gamma U", positive=True)
    density = (A*z+Bc/z)*(Ac/z+B*z)/(2*M)
    averaged_quartic = sp.expand(quartic*density*density/2).coeff(z, 0)
    same = 2*averaged_quartic.coeff(A, 2).coeff(Ac, 2)
    opposite = averaged_quartic.coeff(A, 1).coeff(Ac, 1).coeff(B, 1).coeff(Bc, 1)
    source = sp.expand(g*density)
    source_plus, source_minus = source.coeff(z, 2), source.coeff(z, -2)
    # Eliminating sigma gives -J D^{-1} J/2 in L; the two fast pairings give +J+J-/D in H.
    fast_energy = sp.expand(source_plus*source_minus/(4*M*M-m*m))
    fast_contact = fast_energy.coeff(A, 1).coeff(Ac, 1).coeff(B, 1).coeff(Bc, 1)
    strength = (g/(2*M))**2/(4*sp.pi)
    checks["same_charge_contact_from_phase_average"] = zero(same-quartic/(4*M*M))
    checks["opposite_charge_contact_from_phase_average"] = zero(opposite-quartic/(2*M*M))
    checks["timelike_contact_from_virtual_elimination"] = zero(fast_contact-g*g/(4*M*M*(4*M*M-m*m)))
    family = {g: couplings["gamma"], quartic: couplings["U"], M: couplings["M"], m: couplings["m"]}
    matched = {"alpha": sp.simplify(strength.subs(family)),
               "eta_like": sp.simplify(same.subs(family)),
               "eta_opposite": sp.simplify((opposite+fast_contact).subs(family))}
    checks["contact_family_coefficients"] = zero(matched["eta_like"]-sp.sqrt(2)/(38*N)) and zero(matched["eta_opposite"]-sp.sqrt(2)*(15+h*h)/(285*N))

    r, rp = sp.symbols("r rp", positive=True)
    ell = sp.symbols("ell", integer=True, nonnegative=True)
    regular, outer = r**(ell+1), r**(-ell)
    wronskian = sp.simplify(regular*sp.diff(outer, r)-sp.diff(regular, r)*outer)
    lo = -regular*rp**(-ell)/wronskian
    hi = -rp**(ell+1)*outer/wronskian
    checks["all_partial_wave_wronskians"] = zero(wronskian+2*ell+1)
    checks["radial_green_equation"] = all(zero(-sp.diff(branch, r, 2)+ell*(ell+1)*branch/(r*r)) for branch in (lo, hi))
    checks["radial_green_continuity"] = zero((lo-hi).subs(r, rp))
    checks["radial_green_derivative_jump"] = zero((sp.diff(hi, r)-sp.diff(lo, r)).subs(r, rp)+1)
    checks["radial_green_diagonal"] = zero(lo.subs(rp, r)-r/(2*ell+1))
    checks["s_wave_origin"] = zero(lo.subs(ell, 0).subs(r, 0))
    checks["s_wave_bounded_outer_branch"] = zero(hi.subs(ell, 0)-rp)
    mu = sp.symbols("mu", positive=True)
    checks["s_wave_positive_resolvent_limit"] = zero(sp.limit((1-sp.exp(-2*mu*rp))/(2*mu), mu, 0)-rp)
    yukawa = sp.exp(-m*r)/(4*sp.pi*r)
    checks["three_dimensional_yukawa_equation"] = zero(-sp.diff(r*yukawa, r, 2)/r+m*m*yukawa)
    checks["three_dimensional_yukawa_source_flux"] = zero(sp.limit(-4*sp.pi*r*r*sp.diff(yukawa, r), r, 0, dir="+")-1)
    alpha = sp.symbols("alpha", nonnegative=True)
    trace = sp.integrate(M*alpha*sp.exp(-m*r)*lo.subs(rp, r)/r, (r, 0, sp.oo))
    checks["all_partial_wave_trace_integrals"] = zero(trace-M*alpha/(m*(2*ell+1)))
    trace_family = sp.simplify((M*alpha/m).subs({M: couplings["M"], m: couplings["m"], alpha: matched["alpha"]}))
    checks["canonical_trace_strength"] = zero(trace_family-sp.sqrt(2)*h*h/(sp.pi*sp.sqrt(19)*N))
    matched["B"] = trace_family
    matched["yukawa_integral"] = sp.simplify(matched["alpha"]/couplings["m"])
    return dict(checks=checks, N=N, h=h, values={**couplings, **matched},
                symbolic={"averaged_carrier_quartic": str(averaged_quartic),
                          "timelike_contact": str(fast_contact),
                          "matched_coefficients": {key: str(value) for key, value in matched.items()},
                          "radial_green_left": str(lo), "radial_green_right": str(hi),
                          "radial_partial_wave_trace": str(trace),
                          "exclusion_proof": "For each ell, K_ell(E)<=K_ell(0) for E<0 and norm K_ell(0)<=tr K_ell(0). Trace B/(2ell+1)<1 excludes a negative level. Adding nonnegative regulated contacts raises the quadratic form. The full-space trace is not used."})


def calculate() -> dict:
    exact = derive()
    checks = exact["checks"]
    roots, legendre_weights = np.polynomial.legendre.leggauss(64)
    edge = 8/8.0
    nodes, weights = edge*(roots+1)/2, edge*legendre_weights/2
    rows, quadrature_rows = [], []
    for norm in N_VALUES:
        for h_key in H_KEYS:
            h = float(h_key)
            subs = {exact["N"]: norm, exact["h"]: sp.Rational(h_key)}
            derived = {key: float(value.subs(subs)) for key, value in exact["values"].items()}
            samples = derived["alpha"]*np.exp(-derived["m"]*nodes)
            finite = math.fsum(float(w*x) for w, x in zip(weights, samples))
            tail = derived["alpha"]*math.exp(-8)/derived["m"]
            integral = finite+tail
            B = derived["M"]*integral
            radius = math.sqrt(2)*(5+math.sqrt(1+2*h*h))/(4*math.pi*norm)
            key = f"N{norm}-h{h_key}"
            checks[key+"_quadrature_plus_tail"] = close(integral, derived["yukawa_integral"])
            checks[key+"_trace_strength"] = close(B, derived["B"])
            checks[key+"_nonnegative_contacts"] = derived["eta_like"] >= 0 and derived["eta_opposite"] >= 0
            row = dict(key=key, N=norm, h=h, **derived, a0_radius=radius, tree_bound_pass=radius <= 0.5,
                       binding_excluded=B < 1)
            row["yukawa_integral"], row["B"] = integral, B
            rows.append(row)
            quadrature_rows.append(dict(key=key, samples=samples.tolist(), finite_integral=finite, tail=tail))
    passed = all(checks.values())
    return dict(schema=SCHEMA, role="localization", verdict=VERDICT if passed else "INCONCLUSIVE",
                numeric_pass=passed, error=None, checks=checks, symbolic=exact["symbolic"], rows=rows,
                quadrature=dict(nodes=nodes.tolist(), weights=weights.tolist(), rows=quadrature_rows),
                complete_physical_matter_formation=False,
                scope="Leading instantaneous nonrelativistic pair reduction, nonnegative regulated contacts and per-partial-wave exclusion. B>=1 is undecided; relativistic binding and the open neutral annihilation channel require separate treatment.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        validate_manifest(args.manifest)
        result = calculate()
        text = json.dumps(result, indent=2, allow_nan=False)+"\n"
    except Exception as exc:
        result = dict(schema=SCHEMA, role="localization", verdict="INCONCLUSIVE", numeric_pass=False,
                      error=f"{type(exc).__name__}: {exc}", checks={}, rows=[],
                      complete_physical_matter_formation=False)
        text = json.dumps(result, indent=2, allow_nan=False)+"\n"
    (args.output/"result.json").write_text(text, encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("role", "verdict", "numeric_pass", "error", "complete_physical_matter_formation")}, allow_nan=False))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
