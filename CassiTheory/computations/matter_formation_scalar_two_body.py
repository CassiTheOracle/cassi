#!/usr/bin/env python3
"""Scalar pair interactions and leading localization bound for notebook section 68.

python computations/matter_formation_scalar_two_body.py --manifest PATH --output FRESH_DIR
This conditional scalar calculation does not select physical matter.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
from scipy.integrate import quad
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
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
SCHEMA = "matter-formation-scalar-two-body-v1"
MANIFEST_SCHEMA = "matter-formation-scalar-two-body-manifest-v1"
VERDICT = "SUPPORTS-conditional scalar pair localization and annihilation constraints"
H_KEYS = ("0", "2", "2.9598260763447164", "6")
NORMS = (1, 4, 16, 64)
BOUND = 1e-9


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path) -> str:
    return hashlib.sha256(canonical(path)).hexdigest()


def validate_manifest(path: Path) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    sections = manifest["sections"]
    if len(sections) != len(HEADINGS) or {item["heading"] for item in sections} != HEADINGS:
        raise ValueError("incomplete or duplicate section bindings")
    lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)
    for item in sections:
        if item["path"] != REPORT:
            raise ValueError("unexpected section path")
        starts = [i for i, line in enumerate(lines) if line.rstrip() == item["heading"]]
        if len(starts) != 1:
            raise ValueError("section must occur exactly once")
        start = starts[0]
        stop = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        live = ("".join(lines[start:stop]).rstrip() + "\n").encode("utf-8")
        if hashlib.sha256(live).hexdigest() != item["sha256"] or canonical(ROOT / item["snapshot"]) != live:
            raise ValueError("frozen or live section mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {item["path"] for item in sources} != SOURCES:
        raise ValueError("incomplete or duplicate source bindings")
    for item in sources:
        if digest(ROOT / item["path"]) != item["sha256"] or digest(ROOT / item["snapshot"]) != item["sha256"]:
            raise ValueError("source mismatch: " + item["path"])
    reviews = manifest["mathematical_reviews"]
    if len(reviews) != 2 or {item["role"] for item in reviews} != {"thresholds", "localization"}:
        raise ValueError("incomplete or duplicate reviews")
    for item in reviews:
        snapshot = ROOT / item["snapshot"]
        flags = [line.strip() for line in canonical(snapshot).decode("utf-8").splitlines()
                 if line.strip().startswith("accepted:")]
        if item.get("accepted") is not True or flags != ["accepted: true"] or digest(snapshot) != item["sha256"]:
            raise ValueError("unaccepted mathematical review: " + item["role"])


def zero(value) -> bool:
    return sp.simplify(value) == 0


def compare(actual, expected) -> bool:
    actual = np.asarray(actual, dtype=np.float64)
    expected = np.asarray(expected, dtype=np.float64)
    return bool(actual.shape == expected.shape and np.isfinite(actual).all()
                and np.isfinite(expected).all()
                and np.linalg.norm(actual - expected) / max(1.0, float(np.linalg.norm(expected))) <= BOUND)


def exact_calculation() -> dict:
    sigma, phi, bar = sp.symbols("sigma phi bar")
    m2, M2, kappa, gamma, L, P, U = sp.symbols("m2 M2 kappa gamma L P U", positive=True)
    s, t, u = sp.symbols("s t u", real=True)
    potential = (m2*sigma**2/2 + M2*phi*bar + kappa*sigma**3/6 + L*sigma**4/24
                 + gamma*sigma*phi*bar + P*sigma**2*phi*bar/2 + U*phi**2*bar**2/2)
    fields = (sigma, phi, bar)
    origin = dict.fromkeys(fields, 0)
    cubic = {indices: sp.diff(potential, *(fields[i] for i in indices)).subs(origin)
             for indices in itertools.product(range(3), repeat=3)}
    quartic = {indices: sp.diff(potential, *(fields[i] for i in indices)).subs(origin)
               for indices in itertools.product(range(3), repeat=4)}
    metric = sp.Matrix(((1, 0, 0), (0, 0, 1), (0, 1, 0)))

    def tree(legs):
        result = [quartic[legs]]
        for variable, (a, b, c, d) in zip((s, t, u), ((0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 1, 2))):
            result.append(sp.simplify(sum(
                cubic[(legs[a], legs[b], i)] * metric[i, j] * cubic[(j, legs[c], legs[d])]
                / (variable - (m2 if i == 0 else M2))
                for i in range(3) for j in range(3))))
        return sp.Matrix(result)

    diagrams = {name: tree(legs) for name, legs in {
        "like": (1, 1, 2, 2), "opposite": (1, 2, 2, 1),
        "annihilation": (1, 2, 0, 0), "forbidden": (1, 1, 0, 0),
    }.items()}
    expected_diagrams = {
        "like": (2*U, 0, gamma**2/(t-m2), gamma**2/(u-m2)),
        "opposite": (2*U, gamma**2/(s-m2), gamma**2/(t-m2), 0),
        "annihilation": (P, gamma*kappa/(s-m2), gamma**2/(t-M2), gamma**2/(u-M2)),
        "forbidden": (0, 0, 0, 0),
    }
    checks = {name+"_complete_diagrams": all(zero(a-b) for a, b in zip(value, expected_diagrams[name]))
              for name, value in diagrams.items()}
    n, a, cp, ur, uc, h, e = sp.symbols("N a cp ur uc h e", positive=True)
    c = 1/sp.sqrt(cp)
    vh = sp.sqrt(n*cp*c**3)
    f = 1 + sigma/vh
    density = phi*bar/(n*a*c**3)
    source = n*c**3*(ur*(f*f-1)**2/4 + (e+1/(4*a)-h+h*f*f)*density + uc*density**2/2)
    parent = {m2: 2*ur/cp, M2: (e+1/(4*a))/a, kappa: 6*ur/(cp*vh),
              gamma: 2*h/(a*vh), L: 6*ur/(n*cp**2*c**3),
              P: 2*h/(n*a*cp*c**3), U: uc/(n*a*a*c**3)}
    checks["complete_parent_polynomial"] = zero(sp.expand(source-potential.subs(parent)))
    fixed = {a: sp.Rational(1, 16), cp: sp.Rational(1, 8), ur: 4, uc: 1, e: sp.Rational(3, 4)}
    values = {key: sp.simplify(value.subs(fixed)) for key, value in parent.items()}
    threshold_terms = {}
    for name in ("like", "opposite", "annihilation"):
        point = {s: 4*M2, t: m2-M2, u: m2-M2} if name == "annihilation" else {s: 4*M2, t: 0, u: 0}
        threshold_terms[name] = diagrams[name].subs(point).subs(values).applyfunc(sp.simplify)
    amplitudes = sp.Matrix([sum(terms) for terms in threshold_terms.values()])
    target = sp.Matrix((8*sp.sqrt(2)*(2-h*h)/n,
                        4*sp.sqrt(2)*(60-11*h*h)/(15*n),
                        8*sp.sqrt(2)*h*(99-40*h)/(55*n)))
    checks["three_threshold_coefficients"] = all(zero(x) for x in amplitudes-target)
    original_v = sp.sqrt(n/8)
    original_g = 32*h/original_v
    original_F2 = original_g/original_v + 192/original_v*original_g/240 - 2*original_g**2/88
    checks["parent_reverse_channel_scaling"] = zero(amplitudes[2]-original_F2/sp.sqrt(8)**3)
    checks["zero_coupling_exchange_control"] = all(zero(x.subs(h, 0)) for terms in threshold_terms.values() for x in terms[1:])
    checks["zero_coupling_annihilation"] = zero(amplitudes[2].subs(h, 0))
    checks["interference_root"] = zero(amplitudes[2].subs(h, sp.Rational(99, 40)))
    checks["missing_quartic_destroys_interference"] = not zero((amplitudes[2]-values[P]).subs(h, sp.Rational(99, 40)))

    momentum, mass = sp.symbols("p M", positive=True)
    phase_space = sp.simplify(sp.Rational(1, 2)/(2*sp.pi)**2 * 4*sp.pi
                             * momentum**2/(4*mass**2) * mass/(2*momentum))
    checks["identical_final_phase_space"] = zero(phase_space-momentum/(16*sp.pi*mass))
    checks["threshold_flux_coefficient"] = zero(phase_space/4-momentum/(64*sp.pi*mass))

    A, Ab, B, Bb, phase = sp.symbols("A Ab B Bb phase")
    nr_phi = (A*phase+Bb/phase)/sp.sqrt(2*mass)
    nr_bar = (Ab/phase+B*phase)/sp.sqrt(2*mass)
    averaged = sp.expand(U*nr_phi**2*nr_bar**2/2).coeff(phase, 0)
    eta_like = 2*averaged.coeff(A, 2).coeff(Ab, 2)
    eta_cross = averaged.coeff(A, 1).coeff(Ab, 1).coeff(B, 1).coeff(Bb, 1)
    checks["identical_contact_matching"] = zero(eta_like-U/(4*mass**2))
    checks["opposite_contact_matching"] = zero(eta_cross-U/(2*mass**2))
    fast_source = sp.expand(gamma*nr_phi*nr_bar)
    timelike_energy = fast_source.coeff(phase, 2)*fast_source.coeff(phase, -2)/(4*mass**2-m2)
    eta_ann = sp.expand(timelike_energy).coeff(A, 1).coeff(Ab, 1).coeff(B, 1).coeff(Bb, 1)
    checks["timelike_contact_matching"] = zero(eta_ann-gamma**2/(4*mass**2*(4*mass**2-m2)))
    r, pivot, mediator, alpha = sp.symbols("r pivot m alpha", positive=True)
    ell = sp.symbols("ell", integer=True, nonnegative=True)
    yukawa_green = sp.exp(-mediator*r)/(4*sp.pi*r)
    checks["static_green_equation"] = zero(-sp.diff(r*yukawa_green, r, 2)/r+mediator**2*yukawa_green)
    checks["static_green_flux"] = zero(sp.limit(-4*sp.pi*r*r*sp.diff(yukawa_green, r), r, 0, dir="+")-1)
    left = r**(ell+1)*pivot**(-ell)/(2*ell+1)
    right = pivot**(ell+1)*r**(-ell)/(2*ell+1)
    for name, branch in (("left", left), ("right", right)):
        checks["radial_green_"+name] = zero(-sp.diff(branch, r, 2)+ell*(ell+1)*branch/r**2)
    checks["radial_green_jump"] = zero((sp.diff(right, r)-sp.diff(left, r)).subs(r, pivot)+1)
    checks["radial_green_continuity"] = zero((right-left).subs(r, pivot))
    checks["radial_green_diagonal"] = zero(left.subs(pivot, r)-r/(2*ell+1))
    checks["radial_s_wave_origin"] = zero(left.subs(ell, 0).subs(r, 0))
    trace = sp.integrate(mass*alpha*sp.exp(-mediator*r)/(2*ell+1), (r, 0, sp.oo))
    checks["positive_kernel_trace"] = zero(trace-mass*alpha/(mediator*(2*ell+1)))
    return dict(checks=checks, parameters=(n, h), values=values, variables=(m2, M2, kappa, gamma, L, P, U),
                threshold_terms=threshold_terms,
                symbolic={"general_diagram_terms": {key: [str(x) for x in v] for key, v in diagrams.items()},
                          "threshold_amplitudes": [str(sp.factor(x)) for x in amplitudes],
                          "averaged_carrier_quartic": str(averaged), "timelike_contact": str(eta_ann),
                          "identical_phase_space": str(phase_space), "radial_green_left": str(left),
                          "radial_green_right": str(right), "partial_wave_trace": str(trace),
                          "comparison_scope": "Nonnegative regulated contacts raise the Yukawa quadratic form; trace below one excludes a negative level in this leading pair reduction."})


def calculate() -> dict:
    exact = exact_calculation()
    checks = exact["checks"]
    n, h_symbol = exact["parameters"]
    rows = []
    for norm in NORMS:
        for h_key in H_KEYS:
            h = float(h_key)
            subs = {n: norm, h_symbol: sp.Rational(h_key)}
            m2, M2, kappa, gamma, L, P, U = [float(exact["values"][v].subs(subs)) for v in exact["variables"]]
            m, M = math.sqrt(m2), math.sqrt(M2)
            vhat = math.sqrt(2*math.sqrt(2)*norm)
            terms = {name: [float(x.subs(subs)) for x in values] for name, values in exact["threshold_terms"].items()}
            amplitudes = [math.fsum(value) for value in terms.values()]
            beta = math.sqrt(1-m2/M2)
            phase_space = beta/(16*math.pi)
            rate = phase_space*amplitudes[2]**2/4
            alpha = gamma*gamma/(16*math.pi*M2)
            eta_like = U/(4*M2)
            eta_opposite = U/(2*M2)+gamma*gamma/(4*M2*(4*M2-m2))
            integral, _ = quad(lambda r: alpha*math.exp(-m*r), 0, math.inf, epsabs=1e-12, epsrel=1e-12)
            trace = M*integral
            a0 = (L/4+U+math.sqrt((L-4*U)**2+8*P*P)/4)/(16*math.pi)
            key = f"N{norm}-h{h_key}"
            expected = [8*math.sqrt(2)*(2-h*h)/norm,
                        4*math.sqrt(2)*(60-11*h*h)/(15*norm),
                        8*math.sqrt(2)*h*(99-40*h)/(55*norm)]
            checks[key+"_thresholds"] = compare(amplitudes, expected)
            checks[key+"_yukawa_integral"] = compare(integral, alpha/m)
            checks[key+"_trace"] = compare(trace, math.sqrt(2)*h*h/(math.pi*math.sqrt(19)*norm))
            checks[key+"_repulsive_contacts"] = eta_like >= 0 and eta_opposite >= 0
            checks[key+"_tree_normalization"] = compare(a0, math.sqrt(2)*(5+math.sqrt(1+2*h*h))/(4*math.pi*norm))
            rows.append(dict(key=key, N=norm, h=h, c=math.sqrt(8), m=m, M=M, vhat=vhat,
                             L=L, P=P, U=U, kappa3=kappa, gamma=gamma,
                             a0_radius=a0, tree_bound_pass=a0 <= 0.5,
                             amplitudes=amplitudes, diagram_terms=terms, identical_phase_space=phase_space,
                             annihilation_M2_sigma_v=rate, alpha=alpha, eta_like=eta_like,
                             eta_opposite=eta_opposite, yukawa_integral=integral, B=trace,
                             binding_excluded=trace < 1))
    passed = all(checks.values())
    return dict(schema=SCHEMA, role="primary", verdict=VERDICT if passed else "INCONCLUSIVE",
                numeric_pass=passed, error=None, checks=checks, symbolic=exact["symbolic"], rows=rows,
                complete_physical_matter_formation=False,
                scope="Full tree scalar interactions, threshold annihilation coefficient and leading instantaneous pair comparison. No relativistic bound-state exclusion, physical normalization or formation trajectory.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        validate_manifest(args.manifest)
        result = calculate()
        text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    except Exception as exc:
        result = dict(schema=SCHEMA, role="primary", verdict="INCONCLUSIVE", numeric_pass=False,
                      error=f"{type(exc).__name__}: {exc}", checks={}, rows=[],
                      complete_physical_matter_formation=False)
        text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    (args.output / "result.json").write_text(text, encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("role", "verdict", "numeric_pass", "error", "complete_physical_matter_formation")}, allow_nan=False))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
