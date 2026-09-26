#!/usr/bin/env python3
"""Independent charged-state threshold and annihilation verifier.

The program binds the frozen report, source snapshots, and mathematical
reviews before constructing the sixteen canonical scalar rows. It imports
no sibling calculation; exact Cartesian potential derivatives and charged
external vectors generate every contact and exchange contribution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from itertools import product
from pathlib import Path
from typing import Any

import sympy as sp

SCHEMA = "matter-formation-scalar-two-body-v1"
MANIFEST_SCHEMA = "matter-formation-scalar-two-body-manifest-v1"
ROLE = "thresholds"
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
REVIEW_ROLES = {"thresholds", "localization"}
N_VALUES = (1, 4, 16, 64)
H_KEYS = ("0", "2", "2.9598260763447164", "6")

ROOT = Path(__file__).resolve().parents[1]


def canonical(path: Path) -> bytes:
    """Return the repository byte convention used by the manifest."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path) -> str:
    return hashlib.sha256(canonical(path)).hexdigest()


def _relative_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"{label} must be a root-relative path")
    return Path(value)


def _check_binding(item: Any, required: set[str], label: str) -> None:
    if not isinstance(item, dict) or set(item) != required:
        raise ValueError(f"malformed {label} binding")
    if not isinstance(item.get("sha256"), str) or len(item["sha256"]) != 64:
        raise ValueError(f"malformed {label} digest")


def validate_manifest(path: Path) -> None:
    """Reject every frozen-input mismatch before any row calculation."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")

    sections = manifest.get("sections")
    if not isinstance(sections, list) or len(sections) != 3:
        raise ValueError("sections must contain exactly three bindings")
    for item in sections:
        _check_binding(item, {"path", "heading", "snapshot", "sha256"}, "section")
        if item["path"] != REPORT or item["heading"] not in HEADINGS:
            raise ValueError("unexpected section binding")
        snapshot = _relative_path(item["snapshot"], "section snapshot")
        report_lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)
        starts = [i for i, line in enumerate(report_lines) if line.rstrip() == item["heading"]]
        if len(starts) != 1:
            raise ValueError("section heading must occur exactly once")
        start = starts[0]
        stop = next(
            (i for i in range(start + 1, len(report_lines)) if report_lines[i].startswith("## ")),
            len(report_lines),
        )
        live = ("".join(report_lines[start:stop]).rstrip() + "\n").encode("utf-8")
        if hashlib.sha256(live).hexdigest() != item["sha256"]:
            raise ValueError("live section digest mismatch")
        if canonical(ROOT / snapshot) != live:
            raise ValueError("frozen section snapshot mismatch")
    if {item["heading"] for item in sections} != HEADINGS:
        raise ValueError("incomplete or duplicate section bindings")

    sources = manifest.get("sources")
    if not isinstance(sources, list) or len(sources) != len(SOURCES):
        raise ValueError("sources must contain exactly four bindings")
    for item in sources:
        _check_binding(item, {"path", "snapshot", "sha256"}, "source")
        source = _relative_path(item["path"], "source")
        snapshot = _relative_path(item["snapshot"], "source snapshot")
        if item["path"] not in SOURCES:
            raise ValueError("unexpected source binding")
        if digest(ROOT / source) != item["sha256"]:
            raise ValueError("source mismatch: " + item["path"])
        if digest(ROOT / snapshot) != item["sha256"]:
            raise ValueError("source snapshot mismatch: " + item["path"])
    if {item["path"] for item in sources} != SOURCES:
        raise ValueError("incomplete or duplicate source bindings")

    reviews = manifest.get("mathematical_reviews")
    if not isinstance(reviews, list) or len(reviews) != 2:
        raise ValueError("reviews must contain exactly two bindings")
    for item in reviews:
        _check_binding(item, {"role", "accepted", "snapshot", "sha256"}, "review")
        if item["role"] not in REVIEW_ROLES or item["accepted"] is not True:
            raise ValueError("unaccepted mathematical review: " + str(item.get("role")))
        snapshot = _relative_path(item["snapshot"], "review snapshot")
        review_lines = canonical(ROOT / snapshot).decode("utf-8").splitlines()
        flags = [line.strip() for line in review_lines if line.strip().startswith("accepted:")]
        if flags != ["accepted: true"]:
            raise ValueError("review must contain exactly one accepted: true line")
        if digest(ROOT / snapshot) != item["sha256"]:
            raise ValueError("review snapshot mismatch: " + str(item["role"]))
    if {item["role"] for item in reviews} != REVIEW_ROLES:
        raise ValueError("incomplete or duplicate mathematical reviews")


def _derive() -> dict[str, Any]:
    """Differentiate the Cartesian polynomial and contract every internal line."""
    S, X, Y = sp.symbols("S X Y", real=True)
    m2, M2, kappa, gamma, L, P, U = sp.symbols("m2 M2 kappa gamma L P U", positive=True)
    s, t, u = sp.symbols("s t u", real=True)
    fields = (S, X, Y)
    potential = (m2*S**2/2 + M2*(X*X+Y*Y)/2 + kappa*S**3/6 + L*S**4/24
                 + gamma*S*(X*X+Y*Y)/2 + P*S*S*(X*X+Y*Y)/4 + U*(X*X+Y*Y)**2/8)
    zero_fields = dict.fromkeys(fields, 0)
    third = {indices: sp.diff(potential, *(fields[i] for i in indices)).subs(zero_fields)
             for indices in product(range(3), repeat=3)}
    fourth = {indices: sp.diff(potential, *(fields[i] for i in indices)).subs(zero_fields)
              for indices in product(range(3), repeat=4)}
    neutral = sp.Matrix((1, 0, 0))
    plus = sp.Matrix((0, 1, sp.I))/sp.sqrt(2)
    minus = plus.conjugate()

    def attachment(first, second):
        return [sp.simplify(sum(third[i, j, k]*first[i]*second[j]
                               for i, j in product(range(3), repeat=2))) for k in range(3)]

    def tree(vectors):
        contact = sp.simplify(sum(fourth[indices]*sp.prod(vectors[j][indices[j]] for j in range(4))
                                  for indices in product(range(3), repeat=4)))
        terms = [contact]
        for variable, order in zip((s, t, u), ((0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 1, 2))):
            left = attachment(vectors[order[0]], vectors[order[1]])
            right = attachment(vectors[order[2]], vectors[order[3]])
            terms.append(sp.simplify(sum(left[k]*right[k]/(variable-mass)
                                         for k, mass in enumerate((m2, M2, M2)))))
        return sp.Matrix(terms)

    diagrams = {key: tree(vectors) for key, vectors in {
        "like": (plus, plus, minus, minus), "opposite": (plus, minus, minus, plus),
        "annihilation": (plus, minus, neutral, neutral), "forbidden": (plus, plus, neutral, neutral),
    }.items()}
    targets = {
        "like": (2*U, 0, gamma**2/(t-m2), gamma**2/(u-m2)),
        "opposite": (2*U, gamma**2/(s-m2), gamma**2/(t-m2), 0),
        "annihilation": (P, gamma*kappa/(s-m2), gamma**2/(t-M2), gamma**2/(u-M2)),
        "forbidden": (0, 0, 0, 0),
    }
    checks = {key+"_exact_internal_contractions": all(sp.simplify(a-b) == 0 for a, b in zip(terms, targets[key]))
              for key, terms in diagrams.items()}
    N, h = sp.symbols("N h", positive=True)
    speed = sp.sqrt(8)
    vh = speed**sp.Rational(3, 2)*sp.sqrt(N/8)
    values = {m2: sp.Integer(64), M2: sp.Integer(76), kappa: 192/vh, gamma: 32*h/vh,
              L: 48*sp.sqrt(2)/N, P: 8*sp.sqrt(2)*h/N, U: 8*sp.sqrt(2)/N}
    threshold = {}
    for key in ("like", "opposite", "annihilation"):
        point = {s: 4*M2, t: m2-M2, u: m2-M2} if key == "annihilation" else {s: 4*M2, t: 0, u: 0}
        threshold[key] = diagrams[key].subs(point).subs(values).applyfunc(sp.simplify)
    amps = [sp.factor(sum(value)) for value in threshold.values()]
    expected = (8*sp.sqrt(2)*(2-h*h)/N, 4*sp.sqrt(2)*(60-11*h*h)/(15*N),
                8*sp.sqrt(2)*h*(99-40*h)/(55*N))
    checks["general_threshold_polynomials"] = all(sp.simplify(a-b) == 0 for a, b in zip(amps, expected))
    parent_v = sp.sqrt(N/8)
    parent_g, parent_cubic = 32*h/parent_v, 192/parent_v
    parent_F2 = parent_g/parent_v + parent_g*parent_cubic/(4*76-64) + 2*parent_g**2/(64-2*76)
    checks["parent_F2_over_c3"] = sp.simplify(parent_F2/speed**3-amps[2]) == 0
    checks["zero_coupling_annihilation"] = amps[2].subs(h, 0) == 0
    checks["zero_coupling_exchanges"] = all(x.subs(h, 0) == 0 for terms in threshold.values() for x in terms[1:])
    checks["exact_interference_root"] = amps[2].subs(h, sp.Rational(99, 40)) == 0
    checks["mixed_quartic_required_at_root"] = sp.simplify((amps[2]-values[P]).subs(h, sp.Rational(99, 40))) != 0
    momentum, mass = sp.symbols("p M", positive=True)
    radial_delta = momentum**2/(4*mass**2)/(2*momentum/mass)
    integrated_phase = sp.simplify(4*sp.pi/(2*sp.pi)**2*radial_delta/2)
    checks["radial_delta_jacobian"] = sp.simplify(radial_delta-momentum/(8*mass)) == 0
    checks["identical_final_phase_space"] = sp.simplify(integrated_phase-momentum/(16*sp.pi*mass)) == 0
    checks["incoming_covariant_flux"] = sp.simplify(integrated_phase/(4*mass**2)-momentum/(64*sp.pi*mass**3)) == 0
    return dict(checks=checks, N=N, h=h, vhat=vh, values=values,
                variables=(m2, M2, kappa, gamma, L, P, U), terms=threshold,
                symbolic={"Cartesian_potential": str(potential),
                          "charged_vectors": [str(plus), str(minus)],
                          "general_diagram_terms": {key: [str(x) for x in terms] for key, terms in diagrams.items()},
                          "threshold_polynomials": [str(x) for x in amps],
                          "radial_delta_integral": str(radial_delta),
                          "identical_phase_space": str(integrated_phase)})


def _row(exact: dict[str, Any], norm: int, h_key: str) -> dict[str, Any]:
    subs = {exact["N"]: norm, exact["h"]: sp.Rational(h_key)}
    m2, M2, kappa, gamma, L, P, U = [float(exact["values"][symbol].subs(subs)) for symbol in exact["variables"]]
    terms = {key: [float(x.subs(subs)) for x in value] for key, value in exact["terms"].items()}
    amplitudes = [math.fsum(value) for value in terms.values()]
    beta = math.sqrt(1-m2/M2)
    radius = math.sqrt(2)*(5+math.sqrt(1+2*float(h_key)**2))/(4*math.pi*norm)
    return dict(key=f"N{norm}-h{h_key}", N=norm, h=float(h_key), c=math.sqrt(8),
                m=math.sqrt(m2), M=math.sqrt(M2), vhat=float(exact["vhat"].subs(subs)),
                L=L, P=P, U=U, kappa3=kappa, gamma=gamma,
                a0_radius=radius, tree_bound_pass=radius <= 0.5,
                amplitudes=amplitudes, diagram_terms=terms,
                identical_phase_space=beta/(16*math.pi),
                annihilation_M2_sigma_v=beta*amplitudes[2]**2/(64*math.pi))


def calculate() -> dict[str, Any]:
    exact = _derive()
    rows = [_row(exact, N, h_key) for N in N_VALUES for h_key in H_KEYS]
    checks = exact["checks"]
    numeric_pass = all(checks.values())
    return {
        "schema": SCHEMA,
        "role": ROLE,
        "verdict": "SUPPORTS-conditional scalar pair localization and annihilation constraints" if numeric_pass else "INCONCLUSIVE",
        "numeric_pass": bool(numeric_pass),
        "error": None if numeric_pass else "one or more independent threshold checks failed",
        "checks": checks,
        "symbolic": exact["symbolic"],
        "rows": rows,
        "complete_physical_matter_formation": False,
        "scope": "Independent real-Cartesian charged-state tree amplitudes, threshold phase space, crossing and selection controls.",
    }


def _failure(exc: Exception) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "role": ROLE,
        "verdict": "INCONCLUSIVE",
        "numeric_pass": False,
        "error": f"{type(exc).__name__}: {exc}",
        "checks": {},
        "symbolic": {},
        "rows": [],
        "complete_physical_matter_formation": False,
        "scope": "Independent real-Cartesian charged-state tree amplitudes, threshold phase space, crossing and selection controls.",
    }


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
        result = _failure(exc)
        text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    (args.output / "result.json").write_text(text, encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("role", "verdict", "numeric_pass", "error", "complete_physical_matter_formation")}, allow_nan=False))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
