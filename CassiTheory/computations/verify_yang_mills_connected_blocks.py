#!/usr/bin/env python3
"""Verify fixed pure-SU(2) local dressing and periodic support identities.

Run from CassiTheory with --output pointing to a fresh immutable receipt.
This checks the preregistered finite identities; the volume-uniform theorem
requires the separately reviewed Yarotsky hypothesis map.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.linalg import expm
import sympy as sp

import verify_yang_mills_loop_gap as receipt_checks

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/yang-mills-connected-block-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_connected_blocks/verification.json"
SIDES = (4, 6, 8)
SIZES = (3, 5, 8)
X_VALUES = (-0.25, -0.125, -0.0625, 0.0, 0.0625, 0.125, 0.25)
TOLERANCE = 1e-11
PLANES = tuple(itertools.combinations(range(3), 2))
PARITIES = tuple(itertools.product((0, 1), repeat=3))
check = receipt_checks.check
exact = receipt_checks.exact


def translated(site, axis, side):
    target = list(site)
    target[axis] = (target[axis] + 1) % side
    return tuple(target)


def geometry(result):
    result["geometry_rows"] = []
    for side in SIDES:
        sites = tuple(itertools.product(range(side), repeat=3))
        links = {(site, axis) for site in sites for axis in range(3)}
        support_multiplicity = Counter()
        plaquette_incidence = Counter()
        colors = {(plane, parity): [] for plane in PLANES for parity in PARITIES}
        contained = True
        for site in sites:
            support = {site, *(translated(site, axis, side) for axis in range(3))}
            support_multiplicity.update(support)
            for first, second in PLANES:
                plaquette = ((site, first),
                             (translated(site, first, side), second),
                             (translated(site, second, side), first),
                             (site, second))
                contained = contained and len(set(plaquette)) == 4 and all(
                    edge in links and edge[0] in support for edge in plaquette)
                plaquette_incidence.update(plaquette)
                parity = tuple(coordinate % 2 for coordinate in site)
                colors[((first, second), parity)].append(plaquette)
        color_rows = []
        for (plane, parity), plaquettes in colors.items():
            occupied = [edge for plaquette in plaquettes for edge in plaquette]
            color_rows.append(dict(plane=list(plane), parity=list(parity),
                                   plaquettes=len(plaquettes), links=len(occupied),
                                   repeated_links=len(occupied) - len(set(occupied))))
        row = dict(side=side, sites=len(sites), links=len(links),
                   plaquettes=sum(len(value) for value in colors.values()),
                   plaquette_incidence=[dict(site=list(site), axis=axis,
                                              count=plaquette_incidence[(site, axis)])
                                        for site, axis in sorted(links)],
                   support_multiplicity=[dict(site=list(site), count=support_multiplicity[site])
                                         for site in sites],
                   color_classes=color_rows, anchored_support_containment=contained)
        result["geometry_rows"].append(row)
        check(result, f"periodic inventory L={side}",
              row["sites"] == side**3 and row["links"] == row["plaquettes"] == 3 * side**3,
              {key: row[key] for key in ("sites", "links", "plaquettes")})
        check(result, f"star multiplicity L={side}",
              set(support_multiplicity) == set(sites) and set(support_multiplicity.values()) == {4},
              dict(Counter(support_multiplicity.values())))
        check(result, f"plaquette incidence L={side}",
              set(plaquette_incidence) == links and set(plaquette_incidence.values()) == {4},
              dict(Counter(plaquette_incidence.values())))
        check(result, f"24 disjoint-link layers L={side}",
              len(color_rows) == 24 and all(row["repeated_links"] == 0
                                           and row["plaquettes"] == side**3 // 8
                                           for row in color_rows), color_rows)
        check(result, f"anchored interaction support L={side}", contained, contained)


def symbolic(result):
    x = sp.Symbol("x", real=True)
    k = sp.diag(0, 3, 8)
    v = sp.Matrix(((0, 1, 0), (1, 0, 1), (0, 1, 0)))
    s = sp.Matrix(((0, sp.Rational(1, 3), 0), (-sp.Rational(1, 3), 0, 0), (0, 0, 0)))
    t = sp.Matrix(((0, 1, 0), (1, 0, 0), (0, 0, 0)))
    q = sp.diag(0, 1, 1)
    commutator = s * v - v * s
    double_electric = s * t - t * s
    exact(result, "local generator is anti-Hermitian", s + s.T, sp.zeros(3))
    exact(result, "electric commutator cancels vacuum creation", s * k - k * s, t)
    exact(result, "vacuum split equals compressed Wilson multiplication", v - t, q * v * q)
    exact(result, "relative interaction annihilates vacuum", (v - t)[:, 0], sp.zeros(3, 1))
    exact(result, "Wilson commutator finite-rank matrix", commutator,
          sp.Matrix(((2, 0, 1), (0, -2, 0), (1, 0, 0))) / 3)
    exact(result, "double electric commutator matrix", double_electric, sp.diag(2, -2, 0) / 3)
    eigenvalues = commutator.eigenvals()
    expected_eigenvalues = {-sp.Rational(2, 3): 1,
                            (1 - sp.sqrt(2)) / 3: 1,
                            (1 + sp.sqrt(2)) / 3: 1}
    check(result, "Wilson commutator exact eigenvalues", eigenvalues == expected_eigenvalues,
          {str(key): count for key, count in eigenvalues.items()})
    c, sine = sp.cos(x / 3), sp.sin(x / 3)
    u = sp.Matrix(((c, sine, 0), (-sine, c, 0), (0, 0, 1)))
    transformed = u * (k - x * v) * u.T
    exact(result, "closed rotation unitarity", u * u.T, sp.eye(3))
    exact(result, "closed rotation derivative", u.diff(x) - s * u, sp.zeros(3))
    exact(result, "transformed vacuum energy", transformed[0, 0], 3 * sine**2 - 2 * x * sine * c)
    exact(result, "transformed second-character amplitude", transformed[2, 0], -x * sine)
    leading = sp.simplify((transformed - k + x * (v - t)).diff(x, 2).subs(x, 0) / 2)
    exact(result, "quadratic remainder coefficient", leading,
          sp.Matrix(((-1, 0, -1), (0, 1, 0), (-1, 0, 0))) / 3)
    exact(result, "first-order vacuum cancellation", transformed.diff(x).subs(x, 0)[:, 0], sp.zeros(3, 1))
    n = sp.Symbol("n", integer=True, positive=True)
    exact(result, "unreduced Casimir floor factorization",
          n * (n + 2) / 4 - sp.Rational(3, 4), (n - 1) * (n + 3) / 4)
    exact(result, "local classical normalization", sp.Rational(4, 3) * sp.Rational(3, 4), 1)
    exact(result, "star sum electric coefficient", sp.Rational(4, 3) * 4, sp.Rational(16, 3))
    exact(result, "three plaquette local norm coefficient", sp.Rational(16, 3) * 3 * 2, 32)
    exact(result, "partial-sum relative coefficient", 2 * sp.Rational(4, 3) * 4, sp.Rational(32, 3))
    gamma, g, a = sp.symbols("gamma g a", positive=True)
    exact(result, "physical gap rescaling", gamma * sp.Rational(3, 16) * g**2 / (2 * a),
          3 * gamma * g**2 / (32 * a))
    exact(result, "local bounded perturbation in bare coupling", 32 * 2 / g**4, 64 / g**4)
    result["symbolic"] = dict(
        generator=str(s), wilson_commutator=str(commutator),
        wilson_commutator_norm=str((1 + sp.sqrt(2)) / 3),
        double_electric_norm="2/3", remainder_constant=str((2 + sp.sqrt(2)) / 3),
        integral_bound="||R_square(x)|| <= [1/2 ||[S,[S,K]]|| + ||[S,V]||] x^2",
        remainder_constant_scope="exact isolated square; not the many-plaquette circuit constant",
        leading_remainder=str(leading), local_classical_gap="1", star_sum="16/3 K",
        local_perturbation_norm="32 |x| = 64/g^4", relative_bound="32 |x|/3",
        strong_coupling_gap="3 gamma(g) g^2/(32a), conditional on Yarotsky smallness",
        theorem_smallness_constant="NOT_EVALUATED", circuit_remainder_constant="NOT_EVALUATED")


def local_matrices(size):
    k = np.diag(np.arange(size, dtype=float) * (np.arange(size, dtype=float) + 2))
    v = np.diag(np.ones(size - 1), 1) + np.diag(np.ones(size - 1), -1)
    s = np.zeros((size, size))
    s[0, 1], s[1, 0] = 1 / 3, -1 / 3
    t = np.zeros((size, size))
    t[0, 1] = t[1, 0] = 1.0
    return k, v, s, t


def closed_transformed(k, v, x):
    """Direct matrix elements derived from the two-state rotation."""
    c, sine = np.cos(x / 3), np.sin(x / 3)
    transformed = k - x * v
    transformed[0, 0] = 3 * sine * sine - 2 * x * sine * c
    transformed[1, 1] = 3 * c * c + 2 * x * sine * c
    transformed[0, 1] = transformed[1, 0] = 3 * sine * c - x * (c * c - sine * sine)
    transformed[0, 2] = transformed[2, 0] = -x * sine
    transformed[1, 2] = transformed[2, 1] = -x * c
    return transformed


def local_controls(result):
    result["local_rows"] = []
    coefficient = float((2 + np.sqrt(2)) / 3)
    for size in SIZES:
        k, v, s, t = local_matrices(size)
        first_order = s @ k - k @ s - v
        first_order_error = float(np.max(np.abs(first_order[:, 0])))
        for x in X_VALUES:
            u = expm(x * s)
            closed_u = np.eye(size)
            c, sine = np.cos(x / 3), np.sin(x / 3)
            closed_u[:2, :2] = ((c, sine), (-sine, c))
            h = k - x * v
            transformed = u @ h @ u.T
            expected = closed_transformed(k, v, x)
            remainder = transformed - (k - x * (v - t))
            tail = remainder.copy()
            tail[:3, :3] = 0
            rotated_vacuum = u.T[:, 0]
            original_expectation = float(rotated_vacuum @ h @ rotated_vacuum)
            errors = dict(unitary=float(np.max(np.abs(u.T @ u - np.eye(size)))),
                          rotation=float(np.max(np.abs(u - closed_u))),
                          transformed=float(np.max(np.abs(transformed - expected))),
                          first_order_vacuum=first_order_error,
                          three_character_tail=float(np.max(np.abs(tail))),
                          spectra=float(np.max(np.abs(np.linalg.eigvalsh(h) - np.linalg.eigvalsh(transformed)))),
                          expectation=abs(original_expectation - float(transformed[0, 0])))
            norm = float(np.linalg.norm(remainder, ord=2))
            bound = coefficient * x * x
            row = dict(size=size, x=x, unitary=u.tolist(), transformed=transformed.tolist(),
                       remainder=remainder.tolist(), errors=errors, remainder_norm=norm,
                       remainder_bound=bound, norm_over_x_squared=norm / (x*x) if x else None,
                       vacuum_energy=float(transformed[0, 0]),
                       second_character_amplitude=float(transformed[2, 0]),
                       original_rotated_expectation=original_expectation)
            result["local_rows"].append(row)
            finite = np.isfinite(transformed).all() and np.isfinite(remainder).all() and all(
                np.isfinite(value) for value in errors.values())
            check(result, f"local unitary identities N={size} x={x}",
                  finite and max(errors.values()) < TOLERANCE, errors)
            check(result, f"unfitted remainder bound N={size} x={x}",
                  finite and norm <= bound + TOLERANCE, dict(norm=norm, bound=bound))
    expected = {(size, x) for size in SIZES for x in X_VALUES}
    actual = [(row["size"], row["x"]) for row in result["local_rows"]]
    check(result, "complete unique local schedule", len(actual) == len(set(actual)) and set(actual) == expected,
          dict(rows=len(actual), expected=len(expected)))
    check(result, "complete periodic geometry schedule", [row["side"] for row in result["geometry_rows"]] == list(SIDES),
          [row["side"] for row in result["geometry_rows"]])


def compute(result):
    result.update(checks=[], failures=[])
    geometry(result)
    symbolic(result)
    local_controls(result)
    success = not result["failures"]
    result.update(status="PASS" if success else "FAIL", check_count=len(result["checks"]),
                  classifications=dict(finite_geometry="SUPPORTS" if success else "INCONCLUSIVE",
                                       local_operator_identities="SUPPORTS" if success else "INCONCLUSIVE",
                                       strong_coupling_theorem="REQUIRES_ANALYTICAL_RECONCILIATION",
                                       finite_depth_remainder="REQUIRES_ANALYTICAL_RECONCILIATION"),
                  scope=dict(many_plaquette_spectrum="NOT_COMPUTED", continuum_mass="UNRESOLVED",
                             continuum_construction="UNRESOLVED", cassi_microscopic_identification="UNRESOLVED",
                             negative_x="ALGEBRAIC_CONTROL_ONLY"))
    return success


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path, snapshot_dir = output.with_suffix(".inputs.json"), output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")
    sources = dict(protocol=PROTOCOL, verifier=Path(__file__).resolve(),
                   receipt_helper=Path(receipt_checks.__file__).resolve())
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {key: dict(path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(payloads[key]).hexdigest())
                  for key, path in sources.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        (snapshot_dir / path.name).write_bytes(payloads[key])
    manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), identities=identities,
                    numpy_version=np.__version__, sympy_version=sp.__version__, scipy_version=scipy.__version__)
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
    result = dict(schema="cassi.yang-mills.connected-blocks.v1", **manifest)
    success = False
    try:
        success = compute(result)
        if any(path.read_bytes() != payloads[key] for key, path in sources.items()):
            raise RuntimeError("A frozen source changed during execution")
    except Exception as exc:
        result.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(f"Receipt: {output}")
    print(json.dumps({key: result.get(key) for key in ("status", "check_count", "classifications", "failures", "error")}, indent=2))
    if success and result.get("status") == "PASS":
        for row in result["geometry_rows"]:
            print(f"L={row['side']}: {row['sites']} sites, {row['links']} links, {row['plaquettes']} plaquettes, 24 disjoint-link layers")
        worst_error = max(value for row in result["local_rows"] for value in row["errors"].values())
        largest_ratio = max(row["norm_over_x_squared"] for row in result["local_rows"] if row["x"])
        print(f"Local identities: maximum absolute discrepancy {worst_error:.12g}")
        print(f"Remainder: maximum ||R||/x^2 {largest_ratio:.12g}; exact bound {(2 + np.sqrt(2))/3:.12g}")
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
