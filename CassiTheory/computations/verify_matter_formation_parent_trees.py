#!/usr/bin/env python3
"""Unlabelled-tree reconstruction of the independently hand-derived section 64.

python computations/verify_matter_formation_parent_trees.py --manifest PATH --output FRESH_DIR
Main completed this enumerator after the independent derivation and draft
handoff. It reads no other calculation's implementation or numeric results.
"""
from __future__ import annotations

import argparse
from collections import Counter
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
H = sp.Symbol("h", real=True)
H_KEYS = ("0", "2", "2.9598260763447164", "6")
TWO_COUNTS = {"contact": 1, "mediator_exchange": 1, "carrier_exchange": 2}
THREE_COUNTS = {"charged_chain": 6, "mixed_cubic": 6, "mediator_chain": 3,
                "mediator_quartic": 1, "mixed_quartic": 3, "charged_quartic": 6}
GROUPS = {
    ("g", "g", "g"): "charged_chain",
    ("g", "g", "lambda3"): "mixed_cubic",
    ("g", "lambda3", "lambda3"): "mediator_chain",
    ("g", "lambda4"): "mediator_quartic",
    ("g2", "lambda3"): "mixed_quartic",
    ("g", "g2"): "charged_quartic",
}


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
        raise ValueError("unexpected section binding")
    lines = canonical(ROOT/REPORT).decode("utf-8").splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip() == HEADING]
    if len(starts) != 1:
        raise ValueError("section must occur exactly once")
    start = starts[0]
    stop = next((i for i in range(start+1, len(lines)) if lines[i].startswith("## ")), len(lines))
    live = ("".join(lines[start:stop]).rstrip()+"\n").encode("utf-8")
    if hashlib.sha256(live).hexdigest() != section["sha256"] or canonical(ROOT/section["snapshot"]) != live:
        raise ValueError("frozen or current section mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {row["path"] for row in sources} != SOURCES:
        raise ValueError("incomplete or duplicated source bindings")
    for row in sources:
        if digest(ROOT/row["path"]) != row["sha256"] or digest(ROOT/row["snapshot"]) != row["sha256"]:
            raise ValueError("source mismatch: "+row["path"])
    reviews = manifest["mathematical_reviews"]
    if len(reviews) != 2 or {row["role"] for row in reviews} != {"trees", "kinematics"}:
        raise ValueError("incomplete or duplicated mathematical reviews")
    for row in reviews:
        review = ROOT/row["snapshot"]
        flags = [line.strip() for line in canonical(review).decode("utf-8").splitlines()
                 if line.strip().startswith("accepted:")]
        if row.get("accepted") is not True or digest(review) != row["sha256"] or flags != ["accepted: true"]:
            raise ValueError("mathematical review is not qualified: "+row["role"])
    return manifest


def coefficients() -> dict:
    a, c = sp.Rational(1, 16), sp.Rational(1, 8)
    v = sp.sqrt(c)
    m2, M2 = 8/c, (sp.Rational(3, 4)+1/(4*a))/a
    return dict(v=v, m2=m2, M2=M2, g=2*H/(a*v), g2=2*H/(a*v*v),
                lambda3=3*m2/v, lambda4=3*m2/(v*v))


def vertex(charges: list[int]) -> str:
    """0 is sigma; +1/-1 are the two conjugate carrier field slots."""
    content = tuple(sorted(charges))
    rules = {(0, 0, 0): "lambda3", (-1, 0, 1): "g",
             (0, 0, 0, 0): "lambda4", (-1, 0, 0, 1): "g2"}
    if content not in rules:
        raise ValueError(f"unsupported vertex slots: {content}")
    return rules[content]


def external_legs(count: int, co: dict) -> list[dict]:
    m, M = sp.sqrt(co["m2"]), sp.sqrt(co["M2"])
    if count == 4:
        p = sp.sqrt((co["M2"]-co["m2"])/8)
        values = [(0, M, p), (0, M, -p), (1, -M, 0), (-1, -M, 0)]
    else:
        p = sp.sqrt(((3*m/2)**2-co["M2"])/8)
        values = [(0, m, 0)]*3+[(1, -3*m/2, p), (-1, -3*m/2, -p)]
    return [dict(index=i, charge=q, momentum=[sp.sympify(e), sp.sympify(px), sp.Integer(0), sp.Integer(0)])
            for i, (q, e, px) in enumerate(values)]


def pair_data(pair: tuple[int, int], legs: list[dict], co: dict) -> dict:
    charge = sum(legs[i]["charge"] for i in pair)
    coupling = vertex([legs[i]["charge"] for i in pair]+[-charge])
    momentum = [sp.simplify(sum(legs[i]["momentum"][axis] for i in pair)) for axis in range(4)]
    mass2 = co["m2"] if charge == 0 else co["M2"]
    denominator = sp.simplify(momentum[0]**2-8*sum(p*p for p in momentum[1:])-mass2)
    if denominator == 0:
        raise ValueError("zero internal propagator denominator")
    return dict(charge=charge, coupling=coupling, momentum=momentum, denominator=denominator,
                species="sigma" if charge == 0 else "carrier")


def diagram(partitions, remaining, data, vertices, group, co):
    denominators = [item["denominator"] for item in data]
    value = sp.factor(sp.prod(co[key] for key in vertices)/sp.prod(denominators))
    phase = (-sp.I)**len(vertices)*sp.I**len(data)
    if sp.simplify(phase+sp.I) != 0:
        raise ValueError("global iM=-iF phase is incorrect")
    return dict(partitions=[list(pair) for pair in partitions], remaining=list(remaining),
                internal_species=[item["species"] for item in data],
                internal_momenta=[item["momentum"] for item in data],
                denominators=denominators, vertices=vertices,
                couplings=[co[key] for key in vertices], group=group, value=value)


def enumerate_trees(count: int, legs: list[dict], co: dict) -> list[dict]:
    """Enumerate unlabelled tree topologies, not six preassigned classes."""
    indices = tuple(range(count))
    pairs = list(itertools.combinations(indices, 2))
    result = []
    if count == 4:
        key = vertex([leg["charge"] for leg in legs])
        result.append(diagram([], indices, [], [key], "contact", co))
        for pair in pairs:
            complement = tuple(i for i in indices if i not in pair)
            if pair > complement:
                continue
            first, second = pair_data(pair, legs, co), pair_data(complement, legs, co)
            if sp.simplify(first["denominator"]-second["denominator"]) != 0:
                raise ValueError("opposite internal-line denominators disagree")
            group = "mediator_exchange" if first["charge"] == 0 else "carrier_exchange"
            result.append(diagram([pair], complement, [first], [first["coupling"], second["coupling"]], group, co))
        return result
    # A five-leg cubic tree has two disjoint two-external-leg end vertices.
    for first_pair, second_pair in itertools.combinations(pairs, 2):
        if set(first_pair) & set(second_pair):
            continue
        remaining = tuple(i for i in indices if i not in first_pair and i not in second_pair)
        first, second = pair_data(first_pair, legs, co), pair_data(second_pair, legs, co)
        central = vertex([first["charge"], second["charge"], legs[remaining[0]]["charge"]])
        keys = [first["coupling"], second["coupling"], central]
        result.append(diagram([first_pair, second_pair], remaining, [first, second], keys, GROUPS[tuple(sorted(keys))], co))
    # The remaining topologies have a cubic end and one quartic vertex.
    for pair in pairs:
        remaining = tuple(i for i in indices if i not in pair)
        first = pair_data(pair, legs, co)
        last = vertex([first["charge"]]+[legs[i]["charge"] for i in remaining])
        keys = [first["coupling"], last]
        result.append(diagram([pair], remaining, [first], keys, GROUPS[tuple(sorted(keys))], co))
    return result


def numeric(value, h):
    if isinstance(value, dict):
        return {key: numeric(item, h) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [numeric(item, h) for item in value]
    if isinstance(value, sp.Basic):
        number = float(value.subs(H, h).evalf(17))
        if not math.isfinite(number):
            raise ValueError("nonfinite scientific value")
        return number
    return value


def calculate() -> dict:
    co = coefficients()
    two_legs, three_legs = external_legs(4, co), external_legs(5, co)
    two, three = enumerate_trees(4, two_legs, co), enumerate_trees(5, three_legs, co)
    checks = {
        "two_topology_counts": dict(Counter(row["group"] for row in two)) == TWO_COUNTS,
        "three_topology_counts": dict(Counter(row["group"] for row in three)) == THREE_COUNTS,
    }
    for name, legs in (("two", two_legs), ("three", three_legs)):
        checks[name+"_momentum_conservation"] = all(sp.simplify(sum(leg["momentum"][axis] for leg in legs)) == 0 for axis in range(4))
        checks[name+"_charge_conservation"] = sum(leg["charge"] for leg in legs) == 0
        checks[name+"_external_on_shell"] = all(sp.simplify(leg["momentum"][0]**2-8*sum(p*p for p in leg["momentum"][1:])
                                                                         -co["m2" if leg["charge"] == 0 else "M2"]) == 0 for leg in legs)
    two_groups = {key: sp.factor(sum(row["value"] for row in two if row["group"] == key)) for key in TWO_COUNTS}
    three_groups = {key: sp.factor(sum(row["value"] for row in three if row["group"] == key)) for key in THREE_COUNTS}
    F2, F3 = sp.factor(sum(two_groups.values())), sp.factor(sum(three_groups.values()))
    cubic = sp.factor(sum(three_groups[key] for key in ("charged_chain", "mixed_cubic", "mediator_chain")))
    g, v, mu, big = (co[key] for key in ("g", "v", "m2", "M2"))
    expected2 = co["g2"]+co["lambda3"]*g/(4*big-mu)+2*g*g/(mu-2*big)
    expected3 = 3*g/(2*v*v)*(g*v/mu-1)*(g*v/mu-3)
    checks["exact_two_amplitude"] = sp.simplify(F2-expected2) == 0
    checks["exact_three_amplitude"] = sp.simplify(F3-expected3) == 0
    checks["exact_three_cubic_only"] = sp.simplify(cubic-192*sp.sqrt(2)*H*(H-1)*(H-3)) == 0
    rows = []
    for key in H_KEYS:
        h = sp.Rational(key)
        if key == "0":
            checks["zero_coupling"] = F2.subs(H, h) == 0 and F3.subs(H, h) == 0
        elif key in ("2", "6"):
            checks[f"h{key}_full_cancellation"] = F3.subs(H, h) == 0
            checks[f"h{key}_quartic_omission_breaks_cancellation"] = cubic.subs(H, h) != 0
        else:
            checks["selected_two_channel_nonzero"] = F2.subs(H, h) != 0
            checks["selected_three_channel_nonzero"] = F3.subs(H, h) != 0
        rows.append(dict(h_key=key, h=float(h), coefficients=numeric(co, h),
                         two_groups=numeric(two_groups, h), three_groups=numeric(three_groups, h),
                         F2=numeric(F2, h), F3=numeric(F3, h), F3_cubic_only=numeric(cubic, h),
                         two_external_legs=numeric(two_legs, h), three_external_legs=numeric(three_legs, h),
                         two_diagrams=numeric(two, h), three_diagrams=numeric(three, h)))
    return dict(checks={key: bool(value) for key, value in checks.items()}, rows=rows,
                symbolic=dict(F2=str(F2), F3=str(F3), F3_cubic_only=str(cubic)),
                scope="Tree-order scalar restriction, formal N=1 coefficients, no absolute rate or interacting mass statement")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema="matter-formation-parent-matching-v1", role="trees", checks={}, rows=[],
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
        receipt = dict(schema="matter-formation-parent-matching-v1", role="trees", checks={}, rows=[],
                       numeric_pass=False, verdict="INCONCLUSIVE", error=f"{type(exc).__name__}: {exc}",
                       complete_physical_matter_formation=False)
        text = json.dumps(receipt, allow_nan=False, indent=2)
    (args.output/"result.json").write_text(text+"\n", encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in ("verdict", "numeric_pass", "error", "complete_physical_matter_formation")}, allow_nan=False))
    return 0 if receipt["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
