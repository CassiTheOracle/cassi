#!/usr/bin/env python3
"""Independent full electric-link calculation for notebook section 60.

python computations/verify_matter_formation_local_gauss.py --manifest PATH --output FRESH_DIR
The tensor-space construction uses ordered ladders and unprojected sparse
exponential action. The primary program is read only for its source digest.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import expm_multiply, norm as sparse_norm

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
LAMBDA, HOPPING, KAPPA = 1/4, 1/8, 1/2
END = math.pi / (2 * math.sqrt(2) * LAMBDA)
TIMES = np.array([0., END/2, END])
E_GRID = (-2, -1, 0, 1, 2)
D = np.array([[-1, 0], [1, -1], [0, 1]], dtype=np.int64)
CASES = ("coupled", "no_hopping", "no_vertex", "bare")
NAMES = ("norm", "Q", "R", "energy", "pair_count", "P_sep", "flux2",
         "gauss_variance", "G0", "G1", "G2")
BOUND = 1e-9
# Textual operator order; application runs rightmost first. Charged modes 0..5.
VERTEX = ((("b", -1, 0), ("c", 1, 1), ("c", 1, 4)),
          (("b", 1, 0), ("c", -1, 4), ("c", -1, 1)))
HOPS = ((1, 0, 0, 1), (2, 1, 1, 1), (4, 3, 0, -1), (5, 4, 1, -1))


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
        # The primary source is never parsed or imported; only its digest is read.
        if digest(ROOT / row["path"]) != row["sha256"] or digest(path.parent / row["snapshot"]) != row["sha256"]:
            raise ValueError(f"source mismatch: {row['path']}")
    review = manifest["mathematical_review"]
    review_file = path.parent / review["snapshot"]
    if (review.get("accepted") is not True or digest(review_file) != review["sha256"]
            or digest(path.parent / review["path"]) != review["sha256"]
            or "accepted: true" not in canonical(review_file).decode("utf-8").splitlines()):
        raise ValueError("mathematical review is not qualified")
    return manifest


class TensorSpace:
    """Exact matter sector tensored with an auxiliary five-state rotor window."""

    def __init__(self, stat: str):
        self.fermionic = stat == "fermion"
        options = range(2) if self.fermionic else range(5)
        self.rows = [(nb, *plus, *minus) for nb in range(3)
                     for plus in itertools.product(options, repeat=3)
                     for minus in itertools.product(options, repeat=3)
                     if sum(plus) == sum(minus) and 2*nb+sum(plus)+sum(minus) == 4]
        self.basis = np.array(self.rows, dtype=np.int64)
        self.index = {row: i for i, row in enumerate(self.rows)}
        self.full_basis = np.array([(*row, e0, e1) for row in self.rows
                                    for e0 in E_GRID for e1 in E_GRID], dtype=np.int64)
        self.rho = self.basis[:, 1:4] - self.basis[:, 4:7]
        self.physical_flux = np.column_stack((-self.rho[:, 0], self.rho[:, 2]))
        self.full_rho = self.full_basis[:, 1:4] - self.full_basis[:, 4:7]
        self.flux = self.full_basis[:, 7:]
        self.gauss = self.flux @ D.T - self.full_rho
        self.Q = self.full_rho.sum(axis=1)
        self.R = 2*self.full_basis[:, 0] + self.full_basis[:, 1:7].sum(axis=1)
        self.pair_count = self.full_basis[:, 1:4].sum(axis=1)
        self.flux2 = (self.flux**2).sum(axis=1)
        self.separation = np.any(self.full_rho != 0, axis=1)
        self.gauss2 = (self.gauss**2).sum(axis=1)
        self.initial = np.zeros(len(self.full_basis), dtype=np.complex128)
        self.initial[self.index[(2, 0, 0, 0, 0, 0, 0)]*25 + 12] = 1.

    def coordinates(self, case: str) -> np.ndarray:
        return np.flatnonzero(np.all(self.flux == 0, axis=1) if case == "bare"
                              else np.all(self.gauss == 0, axis=1))


def apply_ladder_factors(row, factors, fermionic: bool):
    matter, amplitude = list(row), 1.
    for kind, change, mode in reversed(factors):
        pos = 0 if kind == "b" else mode + 1
        occupation = matter[pos]
        if change == -1 and occupation == 0:
            return None
        if kind == "c" and fermionic:
            if change == 1 and occupation == 1:
                return None
            if sum(matter[1:pos]) % 2:
                amplitude = -amplitude
        else:
            amplitude *= math.sqrt(occupation if change == -1 else occupation + 1)
        matter[pos] += change
    return tuple(matter), amplitude


def build_case_matrix(space: TensorSpace, case: str):
    coupling = 0. if case == "no_vertex" else LAMBDA
    hopping = 0. if case == "no_hopping" else HOPPING
    size = len(space.full_basis)
    rows, columns = list(range(size)), list(range(size))
    values = list(map(float, space.R + KAPPA*space.flux2/2))
    dropped = []

    def register(factors, coefficient, link=None, delta=0):
        if coefficient == 0:
            return
        for col, full_row in enumerate(space.full_basis):
            target = apply_ladder_factors(full_row[:7], factors, space.fermionic)
            if target is None:
                continue
            matter, unit = target
            if matter not in space.index:
                raise ValueError("nonzero transition leaves the exact matter sector")
            e0, e1 = map(int, full_row[7:])
            if case != "bare":
                e0 += delta if link == 0 else 0
                e1 += delta if link == 1 else 0
            amplitude = coefficient * unit
            if e0 not in E_GRID or e1 not in E_GRID:
                dropped.append(dict(column=col, target_flux=[e0, e1], amplitude=float(amplitude),
                                    gauss=list(map(int, space.gauss[col]))))
                continue
            row = space.index[matter]*25 + (e0+2)*5 + e1+2
            rows.append(row)
            columns.append(col)
            values.append(amplitude)

    for factors in VERTEX:
        register(factors, coupling)
    for destination, source, link, delta in HOPS:
        register((("c", 1, destination), ("c", -1, source)), -hopping, link, delta)
        register((("c", 1, source), ("c", -1, destination)), -hopping, link, -delta)
    hamiltonian = sparse.csr_matrix((values, (rows, columns)), shape=(size, size), dtype=np.float64)
    hamiltonian.eliminate_zeros()
    return hamiltonian, dropped


def error(actual, expected) -> float:
    actual, expected = np.asarray(actual), np.asarray(expected)
    if not np.isfinite(actual).all() or not np.isfinite(expected).all():
        raise ValueError("nonfinite comparison")
    return float(np.linalg.norm(actual-expected) / max(1., float(np.linalg.norm(expected))))


def diagnostics_from_full(space: TensorSpace, hamiltonian, states):
    probability = abs(states)**2
    diagonal = np.column_stack((np.ones(len(space.full_basis)), space.Q, space.R,
                                space.pair_count, space.separation, space.flux2, space.gauss2, space.gauss))
    energy = np.sum(states.conj() * (hamiltonian @ states.T).T, axis=1).real
    measured = np.insert(probability @ diagonal, 3, energy, axis=1)
    pairs = np.column_stack([probability[:, space.pair_count == k].sum(axis=1) for k in (0, 1, 2)])
    return measured, pairs


def short_time_coefficients(space: TensorSpace, hamiltonian, weights):
    first = hamiltonian @ space.initial
    second = hamiltonian @ first
    lower_zero = bool(np.all(weights*space.initial == 0) and np.all(weights*first == 0))
    return float(np.dot(weights, abs(second)**2)/4), lower_zero


def section58_pair_probabilities(stat: str):
    if stat == "boson":
        angle = math.sqrt(6)*LAMBDA*TIMES
        c = np.cos(angle)
        return np.column_stack(((2+c)**2/9, np.sin(angle)**2/3, 2*(1-c)**2/9))
    angle = math.sqrt(2)*LAMBDA*TIMES
    return np.column_stack((np.cos(angle)**2, np.sin(angle)**2, np.zeros(3)))


def calculate():
    checks, rows, audits, coefficients = {}, [], {}, {}
    arrays = {"times": TIMES, "diagnostic_names": np.array(NAMES)}
    max_error = 0.
    for stat, size in (("boson", 46), ("fermion", 19)):
        space = TensorSpace(stat)
        checks[stat+"_basis_dimensions"] = len(space.basis) == size and len(space.full_basis) == 25*size
        checks[stat+"_physical_slice"] = bool(len(space.coordinates("coupled")) == size
            and np.array_equal(space.full_basis[space.coordinates("coupled"), :7], space.basis))
        checks[stat+"_physical_flux_bound"] = bool(np.max(abs(space.physical_flux)) <= 2)
        arrays.update({stat+"_basis": space.basis, stat+"_rho": space.rho,
                       stat+"_physical_flux": space.physical_flux,
                       stat+"_full_basis": space.full_basis, stat+"_full_gauss": space.gauss})
        for case in CASES:
            prefix = stat+"_"+case
            hamiltonian, dropped = build_case_matrix(space, case)
            coo = hamiltonian.tocoo()
            gauss_changes = np.any(space.gauss[coo.row] != space.gauss[coo.col], axis=1)
            checks[prefix+"_conserved_labels"] = bool(np.all(space.Q[coo.row] == space.Q[coo.col])
                                                       and np.all(space.R[coo.row] == space.R[coo.col]))
            checks[prefix+"_Gauss_selection"] = bool(np.any(gauss_changes) if case == "bare"
                                                     else not np.any(gauss_changes))
            physical_dropped = sum(not any(entry["gauss"]) for entry in dropped)
            checks[prefix+"_physical_cutoff_loss_zero"] = physical_dropped == 0
            audits[prefix] = dict(auxiliary_dropped=len(dropped), physical_dropped=physical_dropped,
                                 dropped_transitions=dropped,
                                 gauss_changing_entries=int(np.count_nonzero(gauss_changes)))
            comparisons = {"Hermiticity": float(sparse_norm(hamiltonian-hamiltonian.T)
                                                / max(1., float(sparse_norm(hamiltonian))))}
            # No physical-subspace projection or normalization in the evolution.
            states = np.stack([expm_multiply(-1j*time*hamiltonian, space.initial) for time in TIMES])
            measured, pairs = diagnostics_from_full(space, hamiltonian, states)
            indices = space.coordinates(case)
            arrays.update({prefix+"_H": hamiltonian[indices, :][:, indices].toarray(),
                           prefix+"_states": states[:, indices], prefix+"_diagnostics": measured,
                           prefix+"_pair_probabilities": pairs, prefix+"_coordinate_indices": indices,
                           prefix+"_full_states": states, prefix+"_csr_data": hamiltonian.data,
                           prefix+"_csr_indices": hamiltonian.indices, prefix+"_csr_indptr": hamiltonian.indptr,
                           prefix+"_csr_shape": np.array(hamiltonian.shape, dtype=np.int64)})
            comparisons.update(norm=error(measured[:, 0], np.ones(3)), Q=error(measured[:, 1], np.zeros(3)),
                               R=error(measured[:, 2], np.full(3, 4.)), energy=error(measured[:, 3], np.full(3, 4.)))
            if case != "bare":
                comparisons["strong_Gauss"] = error(measured[:, 7:], np.zeros((3, 4)))
            if case == "coupled":
                checks[prefix+"_separation_and_flux"] = bool(np.all(measured[1, 5:7] > 1e-6))
                for label, weights in (("separation", space.separation), ("flux", space.flux2)):
                    coefficient, lower_zero = short_time_coefficients(space, hamiltonian, weights)
                    coefficients[prefix+"_"+label] = dict(coefficient=coefficient, exact_target="1/512")
                    comparisons[label+"_t4"] = error(coefficient, 1/512)
                    checks[prefix+"_"+label+"_lower_orders_zero"] = lower_zero
            if case == "bare":
                checks[prefix+"_strong_constraint_violated"] = bool(measured[1, 7] > 1e-6)
                comparisons["mean_Gauss"] = error(measured[:, 8:], np.zeros((3, 3)))
                coefficient, lower_zero = short_time_coefficients(space, hamiltonian, space.gauss2)
                coefficients[prefix+"_Gauss"] = dict(coefficient=coefficient, exact_target="1/256")
                comparisons["Gauss_t4"] = error(coefficient, 1/256)
                checks[prefix+"_lower_orders_zero"] = lower_zero
            if case == "no_hopping":
                comparisons["single_site_probabilities"] = error(pairs, section58_pair_probabilities(stat))
                comparisons["zero_separation_flux"] = error(measured[:, 5:7], np.zeros((3, 2)))
            if case == "no_vertex":
                comparisons["free_initial_state"] = error(states, np.exp(-4j*TIMES[:, None])*space.initial)
            for name, value in comparisons.items():
                checks[prefix+"_"+name] = value <= BOUND
                max_error = max(max_error, value)
            for time, diagnostic, pair in zip(TIMES, measured, pairs):
                rows.append(dict(stat=stat, case=case, time=float(time), **dict(zip(NAMES, map(float, diagnostic))),
                                 pair_probabilities=list(map(float, pair))))
    checks = {key: bool(value) for key, value in checks.items()}
    checks["fixed_row_count"] = len(rows) == 24
    for key, value in arrays.items():
        if np.issubdtype(value.dtype, np.number) and not np.isfinite(value).all():
            raise ValueError(f"nonfinite array: {key}")
    return dict(checks=checks, rows=rows, cutoff_audits=audits, short_time_coefficients=coefficients,
                maximum_normalized_error=max_error,
                scope="Supplied finite quantum model with compressed link shifts and unitary Hamiltonian evolution; physical matter formation remains unresolved.",
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
    receipt = dict(schema="matter-formation-local-gauss-v1", role="independent", verdict="INCONCLUSIVE",
                   numeric_pass=False, checks={}, rows=[], complete_physical_matter_formation=False)
    try:
        manifest = validate_manifest(args.manifest)
        receipt.update(manifest_sha256=digest(args.manifest), source_bindings=manifest["sources"],
                       section_sha256=manifest["section"]["sha256"])
        result, arrays = calculate()
        receipt.update(result)
        json.dumps(receipt, allow_nan=False)
        np.savez_compressed(args.output / "arrays.npz", **arrays)
        passed = all(value is True for value in result["checks"].values())
        receipt.update(numeric_pass=passed, verdict=VERDICT if passed else "INCONCLUSIVE",
                       arrays_sha256=hashlib.sha256((args.output / "arrays.npz").read_bytes()).hexdigest())
    except Exception as exc:
        receipt.update(numeric_pass=False, verdict="INCONCLUSIVE", error=f"{type(exc).__name__}: {exc}")
    (args.output / "result.json").write_text(json.dumps(receipt, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in ("verdict", "numeric_pass", "error", "complete_physical_matter_formation")}))
    return 0 if receipt["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
