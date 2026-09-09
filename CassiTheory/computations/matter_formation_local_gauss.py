#!/usr/bin/env python3
"""Source-bound Gauss-reduced finite quantum comparison for notebook section 60.

python computations/matter_formation_local_gauss.py --manifest PATH --output FRESH_DIR
The microscopic sector, compact links, quantum state and coefficients are supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
import sympy as sp
from scipy.linalg import expm

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = "## 60. Working notes: local quantum Gauss law and neutral conversion"
MANIFEST_SCHEMA = "matter-formation-local-gauss-manifest-v1"
VERDICT = "SUPPORTS-conditional local quantum Gauss conversion"
SOURCES = {
    "computations/matter_formation_local_gauss.py",
    "computations/verify_matter_formation_local_gauss.py",
    "foundations/particle-stationary-action-closure.md",
}
LAMBDA, HOPPING, KAPPA = sp.Rational(1, 4), sp.Rational(1, 8), sp.Rational(1, 2)
BOUND = 1e-9
TIMES = np.array([0., math.pi / (4 * math.sqrt(2) * float(LAMBDA)),
                  math.pi / (2 * math.sqrt(2) * float(LAMBDA))])
CASES = ("coupled", "no_hopping", "no_vertex", "bare")
NAMES = ("norm", "Q", "R", "energy", "pair_count", "P_sep", "flux2",
         "gauss_variance", "G0", "G1", "G2")


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
        raise ValueError("section 60 must occur exactly once")
    start = starts[0]
    stop = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    live = ("".join(lines[start:stop]).rstrip() + "\n").encode("utf-8")
    if hashlib.sha256(live).hexdigest() != section["sha256"] or canonical(path.parent / section["snapshot"]) != live:
        raise ValueError("frozen or current section mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {row["path"] for row in sources} != SOURCES:
        raise ValueError("incomplete source bindings")
    for row in sources:
        # The independent program's bytes are used solely for digest validation.
        if digest(ROOT / row["path"]) != row["sha256"] or digest(path.parent / row["snapshot"]) != row["sha256"]:
            raise ValueError(f"source mismatch: {row['path']}")
    review = manifest["mathematical_review"]
    review_file = path.parent / review["snapshot"]
    if (review.get("accepted") is not True or digest(review_file) != review["sha256"]
            or digest(path.parent / review["path"]) != review["sha256"]
            or "accepted: true" not in canonical(review_file).decode("utf-8").splitlines()):
        raise ValueError("mathematical review is not qualified")
    return manifest


def basis(stat: str) -> np.ndarray:
    limit = 3 if stat == "boson" else 2
    return np.array([(nb, *plus, *minus)
                     for nb in range(3)
                     for plus in itertools.product(range(limit), repeat=3)
                     for minus in itertools.product(range(limit), repeat=3)
                     if sum(plus) == sum(minus) == 2 - nb], dtype=np.int64)


def operators(stat: str, occupations: np.ndarray) -> tuple[sp.Matrix, sp.Matrix]:
    """Closed-form reduced creation and nearest-neighbour matrix elements."""
    size = len(occupations)
    index = {tuple(row): i for i, row in enumerate(occupations)}
    vertex, transport = sp.zeros(size), sp.zeros(size)
    for column, row in enumerate(occupations):
        nb, pc, mc = map(int, row[[0, 2, 5]])
        if nb and (stat == "boson" or (pc == 0 and mc == 0)):
            target = row.copy()
            target[[0, 2, 5]] += [-1, 1, 1]
            amplitude = sp.sqrt(nb * (pc + 1) * (mc + 1))
            if stat == "fermion":
                # CAR order plus0..2, minus0..2, with the minus creation first.
                amplitude *= (-1) ** int(row[2] + row[3] + row[4])
            other = index[tuple(target)]
            vertex[other, column] += amplitude
            vertex[column, other] += amplitude
        for offset in (1, 4):
            for link in range(2):
                source, destination = offset + link, offset + link + 1
                count, filled = int(row[source]), int(row[destination])
                if not count or (stat == "fermion" and filled):
                    continue
                target = row.copy()
                target[source] -= 1
                target[destination] += 1
                other = index[tuple(target)]
                # Adjacent equal-species CAR strings cancel in this ordering.
                amplitude = sp.sqrt(count * (filled + 1))
                transport[other, column] += amplitude
                transport[column, other] += amplitude
    return vertex, transport


def error(actual, expected) -> float:
    actual, expected = np.asarray(actual), np.asarray(expected)
    if not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise ValueError("nonfinite comparison")
    return float(np.linalg.norm(actual - expected) / max(1., float(np.linalg.norm(expected))))


def pair_reference(stat: str) -> np.ndarray:
    if stat == "boson":
        angle = math.sqrt(6) * float(LAMBDA) * TIMES
        cosine = np.cos(angle)
        return np.column_stack(((2 + cosine)**2 / 9, np.sin(angle)**2 / 3,
                                2 * (cosine - 1)**2 / 9))
    angle = math.sqrt(2) * float(LAMBDA) * TIMES
    return np.column_stack((np.cos(angle)**2, np.sin(angle)**2, np.zeros(3)))


def leading_coefficient(hamiltonian: sp.Matrix, initial: sp.Matrix, weights: np.ndarray):
    first, second = hamiltonian * initial, hamiltonian**2 * initial
    lower_zero = all(int(weights[i]) * initial[i] == 0 and int(weights[i]) * first[i] == 0
                     for i in range(len(weights)))
    coefficient = sp.simplify(sum(int(weights[i]) * second[i]**2 for i in range(len(weights))) / 4)
    return coefficient, lower_zero


def diagnostics(states: np.ndarray, hamiltonian: np.ndarray, occupations: np.ndarray,
                rho: np.ndarray, flux: np.ndarray, gauss: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    probabilities = np.abs(states)**2
    count = occupations[:, 1:4].sum(axis=1)
    diagonal = np.column_stack((np.ones(len(occupations)), rho.sum(axis=1),
                                2 * occupations[:, 0] + occupations[:, 1:].sum(axis=1),
                                count, np.any(rho != 0, axis=1), (flux**2).sum(axis=1),
                                (gauss**2).sum(axis=1), gauss))
    measured = probabilities @ diagonal
    energies = np.einsum("ti,ij,tj->t", states.conj(), hamiltonian, states).real
    measured = np.insert(measured, 3, energies, axis=1)
    pairs = np.column_stack([probabilities[:, count == k].sum(axis=1) for k in range(3)])
    return measured, pairs


def calculate() -> tuple[dict, dict]:
    checks, rows, identities = {}, [], {}
    arrays = {"times": TIMES, "diagnostic_names": np.array(NAMES)}
    max_error = 0.
    for stat, dimension in (("boson", 46), ("fermion", 19)):
        occupations = basis(stat)
        rho = occupations[:, 1:4] - occupations[:, 4:7]
        physical_flux = np.column_stack((-rho[:, 0], rho[:, 2]))
        start = next(i for i, row in enumerate(occupations) if tuple(row) == (2, 0, 0, 0, 0, 0, 0))
        initial = sp.zeros(len(occupations), 1)
        initial[start] = 1
        vector = np.array(initial, dtype=np.complex128).ravel()
        vertex, transport = operators(stat, occupations)
        checks[stat + "_basis_dimension"] = len(occupations) == dimension
        checks[stat + "_physical_flux_bound"] = bool(np.max(np.abs(physical_flux)) <= 2)
        checks[stat + "_exact_hermiticity"] = vertex == vertex.T and transport == transport.T
        arrays.update({stat + "_basis": occupations, stat + "_rho": rho,
                       stat + "_physical_flux": physical_flux})
        identities[stat] = {}
        for case in CASES:
            prefix = stat + "_" + case
            coupling = sp.S.Zero if case == "no_vertex" else LAMBDA
            hopping = sp.S.Zero if case == "no_hopping" else HOPPING
            flux = np.zeros_like(physical_flux) if case == "bare" else physical_flux
            gauss = -rho if case == "bare" else np.zeros_like(rho)
            electric = sp.diag(*map(int, (flux**2).sum(axis=1)))
            exact = 4 * sp.eye(dimension) + KAPPA * electric / 2 + coupling * vertex - hopping * transport
            hamiltonian = np.array(exact, dtype=np.float64)
            states = np.stack([expm(-1j * time * hamiltonian) @ vector for time in TIMES])
            measured, pairs = diagnostics(states, hamiltonian, occupations, rho, flux, gauss)
            arrays.update({prefix + "_H": hamiltonian, prefix + "_states": states,
                           prefix + "_diagnostics": measured, prefix + "_pair_probabilities": pairs})
            comparisons = {
                "norm": error(measured[:, 0], np.ones(3)),
                "Q": error(measured[:, 1], np.zeros(3)),
                "R": error(measured[:, 2], np.full(3, 4.)),
                "energy": error(measured[:, 3], np.full(3, 4.)),
            }
            if case != "bare":
                comparisons["strong_Gauss"] = error(measured[:, 7:], np.zeros((3, 4)))
            if case == "no_hopping":
                comparisons["single_site_probabilities"] = error(pairs, pair_reference(stat))
                comparisons["no_separation_flux"] = error(measured[:, 5:7], np.zeros((3, 2)))
            if case == "no_vertex":
                comparisons["free_initial_state"] = error(states, np.exp(-4j * TIMES[:, None]) * vector)
            if case == "bare":
                comparisons["mean_Gauss"] = error(measured[:, 8:], np.zeros((3, 3)))
                checks[prefix + "_strong_constraint_violated"] = bool(measured[1, 7] > 1e-6)
                commutator_norm = sp.simplify(sum(
                    int(np.sum((gauss[i] - gauss[j])**2)) * exact[i, j]**2
                    for i in range(dimension) for j in range(dimension)))
                checks[prefix + "_Gauss_commutator_nonzero"] = commutator_norm > 0
                coefficient, lower_zero = leading_coefficient(exact, initial, (gauss**2).sum(axis=1))
                checks[prefix + "_short_time_exact"] = coefficient == sp.Rational(1, 256) and lower_zero
                identities[stat]["bare_Gauss_t4"] = str(coefficient)
                identities[stat]["bare_Gauss_commutator_squared_frobenius"] = str(commutator_norm)
            if case == "coupled":
                checks[prefix + "_separation_and_flux"] = bool(np.all(measured[1, 5:7] > 1e-6))
                for label, weights in (("separation", np.any(rho != 0, axis=1)),
                                       ("flux", (flux**2).sum(axis=1))):
                    coefficient, lower_zero = leading_coefficient(exact, initial, weights)
                    checks[prefix + "_" + label + "_short_time_exact"] = coefficient == sp.Rational(1, 512) and lower_zero
                    identities[stat][label + "_t4"] = str(coefficient)
            for name, value in comparisons.items():
                checks[prefix + "_" + name] = value <= BOUND
                max_error = max(max_error, value)
            for time, diagnostic, pair in zip(TIMES, measured, pairs):
                rows.append(dict(stat=stat, case=case, time=float(time),
                                 **dict(zip(NAMES, map(float, diagnostic))),
                                 pair_probabilities=list(map(float, pair))))
    checks = {key: bool(value) for key, value in checks.items()}
    checks["fixed_row_count"] = len(rows) == 24
    for key, value in arrays.items():
        if np.issubdtype(value.dtype, np.number) and not np.isfinite(value).all():
            raise ValueError(f"nonfinite array: {key}")
    return dict(checks=checks, rows=rows, exact_identities=identities,
                maximum_normalized_error=max_error,
                scope="Finite Gauss-reduced supplied quantum model; no microscopic selection or physical formation.",
                complete_physical_matter_formation=False), arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        print(json.dumps(dict(verdict="INCONCLUSIVE", numeric_pass=False,
                              error="output directory already exists", complete_physical_matter_formation=False)))
        return 1
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema="matter-formation-local-gauss-v1", role="primary", verdict="INCONCLUSIVE",
                   numeric_pass=False, checks={}, rows=[], complete_physical_matter_formation=False)
    try:
        manifest = validate_manifest(args.manifest)
        receipt.update(manifest_sha256=digest(args.manifest), source_bindings=manifest["sources"],
                       section_sha256=manifest["section"]["sha256"])
        result, arrays = calculate()
        receipt.update(result)
        # Serialize finite diagnostics before creating the array archive.
        json.dumps(receipt, allow_nan=False)
        np.savez_compressed(args.output / "arrays.npz", **arrays)
        passed = all(value is True for value in result["checks"].values())
        receipt.update(numeric_pass=passed, verdict=VERDICT if passed else "INCONCLUSIVE",
                       arrays_sha256=hashlib.sha256((args.output / "arrays.npz").read_bytes()).hexdigest())
    except Exception as exc:
        receipt.update(numeric_pass=False, verdict="INCONCLUSIVE", error=f"{type(exc).__name__}: {exc}")
    (args.output / "result.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in ("verdict", "numeric_pass", "error", "complete_physical_matter_formation")}))
    return 0 if receipt["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
