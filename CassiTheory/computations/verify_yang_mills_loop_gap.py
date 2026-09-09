#!/usr/bin/env python3
"""Run the fixed pure-SU(2) loop-closure controls from CassiTheory.

This checks exact algebra, finite spin networks and an isolated square.
It does not simulate or construct continuum four-dimensional Yang-Mills.
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
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/yang-mills-loop-gap-prereg.md"
INDEPENDENT = ROOT / "computations/verify_yang_mills_loop_gap_independent.py"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_loop_gap/primary.json"
COUPLINGS = (0.125, 0.25, 0.5, 1.0, 2.0, 4.0)
CUTOFFS = (32, 64, 128)
GRIDS = (96, 192)


def discrepancy(actual, expected):
    actual, expected = np.asarray(actual), np.asarray(expected)
    return float(np.max(np.abs(actual - expected)
                        / np.maximum(1.0, np.maximum(np.abs(actual), np.abs(expected)))))


def check(result, name, passed, detail):
    if any(item["name"] == name for item in result["checks"]):
        raise ValueError(f"Duplicate check: {name}")
    passed = bool(passed)
    result["checks"].append(dict(name=name, passed=passed, detail=detail))
    if not passed:
        result["failures"].append(name)


def exact(result, name, actual, expected):
    difference = sp.simplify(actual - expected)
    zero = sp.zeros(*difference.shape) if isinstance(difference, sp.MatrixBase) else 0
    check(result, name, difference == zero, dict(actual=str(actual), expected=str(expected), residual=str(difference)))


def su2(z_y, z_i):
    return sp.Matrix(((z_y, -sp.conjugate(z_i)), (z_i, sp.conjugate(z_y))))


def algebra(result):
    r, s, t, v = sp.symbols("r s t v", real=True)
    group = su2(r + sp.I*s, t + sp.I*v)
    norm = r*r + s*s + t*t + v*v
    exact(result, "SU2 coordinate unitarity", group.H*group, norm*sp.eye(2))
    exact(result, "SU2 coordinate determinant", group.det(), norm)
    pauli = (sp.Matrix(((0, 1), (1, 0))), sp.Matrix(((0, -sp.I), (sp.I, 0))), sp.diag(1, -1))
    exact(result, "fundamental Casimir", sum((matrix*matrix/4 for matrix in pauli), sp.zeros(2)), sp.Rational(3, 4)*sp.eye(2))
    u_plus = su2(sp.Rational(3, 5) + sp.I*sp.Rational(4, 5), 0)
    u_minus = su2(0, sp.Rational(5, 13) + sp.I*sp.Rational(12, 13))
    g_source = su2(1/sp.sqrt(2), sp.I/sp.sqrt(2))
    g_target = su2(sp.Rational(3, 5), sp.Rational(4, 5))
    loop = u_plus*u_minus.H
    transformed = (g_source*u_plus*g_target.H)*(g_source*u_minus*g_target.H).H
    exact(result, "two-path gauge covariance", transformed, g_source*loop*g_source.H)
    exact(result, "two-path trace invariance", sp.trace(transformed), sp.trace(loop))

    phase_rows = []
    for alpha in (sp.Integer(0), sp.pi/2, sp.pi):
        z = sp.Matrix((sp.exp(sp.I*alpha), 0))
        projector = sp.simplify(z*z.H)
        w = su2(*z)
        trace = sp.simplify(sp.trace(w))
        magnetic = sp.simplify(sp.trace(2*sp.eye(2) - w - w.H)/2)
        exact(result, f"equal projectors alpha={alpha}", projector, sp.diag(1, 0))
        exact(result, f"Wilson trace alpha={alpha}", trace, 2*sp.cos(alpha))
        phase_rows.append(dict(alpha=str(alpha), projector=str(projector), trace=str(trace), magnetic_energy=float(magnetic)))
    check(result, "projector does not determine Wilson energy", [row["magnetic_energy"] for row in phase_rows] == [0.0, 2.0, 4.0], phase_rows)
    result["phase_rows"] = phase_rows

    theta = sp.symbols("theta", real=True)
    haar = 2*sp.sin(theta)**2/sp.pi
    exact(result, "class Haar normalization", sp.integrate(haar, (theta, 0, sp.pi)), 1)
    chi = 2*sp.cos(theta)
    exact(result, "fundamental character mean", sp.integrate(chi*haar, (theta, 0, sp.pi)), 0)
    exact(result, "fundamental character norm", sp.integrate(chi*chi*haar, (theta, 0, sp.pi)), 1)
    exact(result, "fundamental character fusion", sp.trigsimp(chi*chi - 1 - sp.sin(3*theta)/sp.sin(theta)), 0)
    f = sp.Function("f")(theta)
    exact(result, "radial Haar unitary transform", sp.sin(theta)*(sp.diff(f, theta, 2) + 2*sp.cot(theta)*sp.diff(f, theta)), sp.diff(sp.sin(theta)*f, theta, 2) + sp.sin(theta)*f)

    x = sp.symbols("x", real=True)
    reduced = sp.Matrix(((0, -x, 0), (-x, 3, -x), (0, -x, 8)))
    # charpoly uses its own symbol; recover it explicitly rather than relying on assumptions.
    polynomial = reduced.charpoly().as_expr()
    lam = next(symbol for symbol in polynomial.free_symbols if symbol != x)
    second = (sp.Rational(-1, 3), sp.Rational(2, 15))
    for index, bare in enumerate((0, 3)):
        residual = sp.series(polynomial.subs(lam, bare + second[index]*x*x), x, 0, 4).removeO()
        exact(result, f"square perturbative eigenvalue {index}", residual, 0)
    exact(result, "square second-order gap coefficient", second[1] - second[0], sp.Rational(7, 15))
    parity = sp.diag(1, -1, 1)
    exact(result, "square even coupling spectrum", parity*reduced*parity, reduced.subs(x, -x))
    result["analytic_formulas"] = dict(
        electric_gap="3*g^2/(2*a)",
        scaled_square_gap="3 + 7*x^2/15 + O(x^4); x=2/g^4",
        scaled_vacuum_energy="2*x*N_p - x^2*N_p/3 + O(x^3), fixed finite box",
        weak_square_levels="sqrt(2)*(2*r+3/2)/a + O(g^2/a), fixed r",
        weak_square_gap="2*sqrt(2)/a + O(g^2/a)",
        scope="Graph theorem requires spin-network proof; square asymptotics are not many-plaquette estimates.")


def rectangular_graph(shape):
    vertices = tuple(itertools.product(*(range(size) for size in shape)))
    index = {vertex: i for i, vertex in enumerate(vertices)}
    edges = []
    incident = [[] for _ in vertices]
    for vertex in vertices:
        for axis, size in enumerate(shape):
            if vertex[axis] + 1 >= size:
                continue
            neighbor = list(vertex)
            neighbor[axis] += 1
            left, right = index[vertex], index[tuple(neighbor)]
            edge = len(edges)
            edges.append((left, right))
            incident[left].append(edge)
            incident[right].append(edge)
    return vertices, edges, incident


def local_singlet(spins):
    # Inputs are twice the spins. Fixtures have valence two or three only.
    if len(spins) == 2:
        return spins[0] == spins[1]
    if len(spins) == 3:
        return sum(spins) % 2 == 0 and 2*max(spins) <= sum(spins)
    raise ValueError(f"Unsupported fixture valence: {len(spins)}")


def graph_controls(result):
    result["graph_rows"] = []
    for name, shape in (("square", (2, 2, 1)), ("two_square", (3, 2, 1)), ("cube", (2, 2, 2))):
        vertices, edges, incident = rectangular_graph(shape)
        allowed = {degree: {spins for spins in itertools.product(range(3), repeat=degree) if local_singlet(spins)}
                   for degree in {len(indices) for indices in incident}}
        histogram = Counter()
        for spins in itertools.product(range(3), repeat=len(edges)):
            if all(tuple(spins[edge] for edge in indices) in allowed[len(indices)] for indices in incident):
                histogram[sum(spin*(spin + 2) for spin in spins)] += 1
        positive = [weight for weight in histogram if weight > 0]
        minimum = min(positive) if positive else None
        row = dict(name=name, shape=shape, vertices=len(vertices), edges=len(edges),
                   labelings=3**len(edges), admissible=sum(histogram.values()),
                   vacuum_count=histogram.get(0, 0), minimum_casimir_sum=None if minimum is None else minimum/4,
                   first_level_count=histogram.get(minimum, 0),
                   casimir_quarters_histogram={str(weight): count for weight, count in sorted(histogram.items())})
        result["graph_rows"].append(row)
        check(result, f"{name} electric vacuum unique", histogram.get(0) == 1, row["vacuum_count"])
        check(result, f"{name} electric gap", minimum == 12, row["minimum_casimir_sum"])
    check(result, "fundamental open endpoint excluded", not local_singlet((1, 0)), "bivalent (1/2,0) has no singlet")
    check(result, "fundamental closed corner admitted", local_singlet((1, 1)), "bivalent (1/2,1/2) has one singlet")


def character_matrix(coupling, cutoff):
    n = np.arange(cutoff, dtype=np.float64)
    diagonal = coupling**2/2*n*(n + 2) + 2/coupling**2
    off = np.full(cutoff - 1, -1/coupling**2)
    return np.diag(diagonal) + np.diag(off, 1) + np.diag(off, -1)


def quadratic_form(coupling, grid):
    theta = (np.arange(grid) + 0.5)*np.pi/grid
    frequencies = np.arange(1, 9)[:, None]
    u = np.sin(frequencies*theta)
    derivative = frequencies*np.cos(frequencies*theta)
    gram = 2/grid*(u @ u.T)
    electric = coupling**2/grid*(derivative @ derivative.T - u @ u.T)
    potential = 2/coupling**2*(1 - np.cos(theta))
    magnetic = 2/grid*((u*potential) @ u.T)
    return gram, electric + magnetic


def spectra(result):
    result.update(spectrum_rows=[], quadratic_form_rows=[], cutoff_comparisons=[])
    for coupling in COUPLINGS:
        levels = {}
        for cutoff in CUTOFFS:
            energies = np.linalg.eigvalsh(character_matrix(coupling, cutoff))[:3]
            gap = float(energies[1] - energies[0])
            levels[cutoff] = energies
            result["spectrum_rows"].append(dict(coupling=coupling, cutoff=cutoff, energies=energies.tolist(), gap=gap))
            check(result, f"square spectrum g={coupling} N={cutoff}", np.isfinite(energies).all() and energies[0] >= -1e-10 and np.all(np.diff(energies) > 0), dict(energies=energies.tolist(), gap=gap))
        for low, high in zip(CUTOFFS, CUTOFFS[1:]):
            error = discrepancy(levels[low], levels[high])
            gap_error = discrepancy(levels[low][1] - levels[low][0], levels[high][1] - levels[high][0])
            result["cutoff_comparisons"].append(dict(coupling=coupling, low=low, high=high, energy_error=error, gap_error=gap_error))
            if low == 64:
                check(result, f"square cutoff convergence g={coupling}", max(error, gap_error) < 1e-8, dict(energy_error=error, gap_error=gap_error))
        for grid in GRIDS:
            gram, hamiltonian = quadratic_form(coupling, grid)
            gram_error = discrepancy(gram, np.eye(8))
            matrix_error = discrepancy(hamiltonian, character_matrix(coupling, 8))
            row = dict(coupling=coupling, grid=grid, gram=gram.tolist(), hamiltonian=hamiltonian.tolist(), gram_error=gram_error, matrix_error=matrix_error)
            result["quadratic_form_rows"].append(row)
            check(result, f"Dirichlet quadratic form g={coupling} grid={grid}", np.isfinite(gram).all() and np.isfinite(hamiltonian).all() and max(gram_error, matrix_error) < 1e-10, dict(gram_error=gram_error, matrix_error=matrix_error))
    check(result, "complete spectrum inventory", len(result["spectrum_rows"]) == 18, len(result["spectrum_rows"]))


def compute(result):
    result.update(checks=[], failures=[])
    algebra(result)
    graph_controls(result)
    spectra(result)
    success = not result["failures"]
    result.update(status="PASS" if success else "FAIL", check_count=len(result["checks"]),
                  classifications=dict(
                      finite_electric_controls="SUPPORTS" if success else "INCONCLUSIVE",
                      autonomous_projector_closure="CONTRADICTS" if success else "INCONCLUSIVE",
                      finite_square_reduction="SUPPORTS" if success else "INCONCLUSIVE"),
                  scope=dict(independent_verification="REQUIRED", interacting_infinite_volume_gap="UNRESOLVED",
                             continuum_construction="UNRESOLVED", cassi_microscopic_identification="UNRESOLVED",
                             every_compact_simple_group="UNRESOLVED", four_dimensional_simulation="NOT_RUN"))
    return success


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path, snapshot_dir = output.with_suffix(".inputs.json"), output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")
    sources = dict(protocol=PROTOCOL, primary=Path(__file__).resolve(), independent=INDEPENDENT)
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {key: dict(path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(payloads[key]).hexdigest()) for key, path in sources.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir()
    for key, path in sources.items():
        (snapshot_dir/path.name).write_bytes(payloads[key])
    manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), identities=identities, numpy_version=np.__version__, sympy_version=sp.__version__)
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
    result = dict(schema="cassi.yang-mills.loop-gap.v1", **manifest)
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
        for row in result["graph_rows"]:
            print(f"{row['name']}: {row['admissible']} invariant labelings, electric gap {row['minimum_casimir_sum']} * g^2/(2a)")
        for row in result["spectrum_rows"]:
            if row["cutoff"] == 128:
                print(f"square g={row['coupling']}: E0={row['energies'][0]:.12g}, gap={row['gap']:.12g}")
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
