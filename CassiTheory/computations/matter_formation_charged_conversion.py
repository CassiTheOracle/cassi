#!/usr/bin/env python3
"""Source-bound finite charge-neutral conversion comparison for notebook section 58.

Run after sealing both sources and their mathematical reviews:
python computations/matter_formation_charged_conversion.py --manifest PATH --output FRESH_DIR

The opposite-charge modes, neutral oscillator, vertex, resonance, quantization
and initial state are supplied inputs. This calculation checks total charge
and finite-sector evolution; it selects no physical particle or local quantum
Gauss-law representation and establishes no full-field stability or formation.
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
from scipy.integrate import solve_ivp
from scipy.linalg import expm

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
COUPLING = sp.Rational(1, 4)
BOUND = 1e-9
END = math.pi / (2 * math.sqrt(2) * float(COUPLING))
TIMES = np.array([0., END / 2, END])
SECTORS = {"boson": [(2, 0, 0), (1, 1, 1), (0, 2, 2)],
           "fermion": [(2, 0, 0), (1, 1, 1)]}


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


def zero(entries) -> bool:
    return all(entry == 0 or sp.trigsimp(sp.simplify(entry)) == 0 for entry in entries)


def numeric(matrix) -> np.ndarray:
    return np.array(matrix.tolist(), dtype=np.complex128)


def error(actual, reference) -> float:
    actual, reference = np.asarray(actual), np.asarray(reference)
    if actual.shape != reference.shape or not np.isfinite(actual).all() or not np.isfinite(reference).all():
        raise ValueError("nonfinite value or shape mismatch")
    return float(np.linalg.norm(actual-reference) / max(1., float(np.linalg.norm(reference))))


def ladder(size: int) -> sp.Matrix:
    result = sp.zeros(size)
    for occupation in range(1, size):
        result[occupation-1, occupation] = sp.sqrt(occupation)
    return result


def model(stat: str) -> dict:
    dim = 3 if stat == "boson" else 2
    basis = list(itertools.product(range(3), range(dim), range(dim)))
    pump, charged = ladder(3), ladder(dim)
    eye_b, eye_c = sp.eye(3), sp.eye(dim)
    b = sp.kronecker_product(pump, eye_c, eye_c)
    plus = sp.kronecker_product(eye_b, charged, eye_c)
    # Plus-first occupation convention. The string enforces cross-mode CAR.
    string = eye_c if stat == "boson" else sp.diag(1, -1)
    minus = sp.kronecker_product(eye_b, string, charged)
    nb, np_, nm = b.H*b, plus.H*plus, minus.H*minus
    number, charge, resource = np_+nm, np_-nm, 2*nb+np_+nm
    hint = COUPLING*(b*plus.H*minus.H + b.H*minus*plus)
    return dict(basis=basis, index={state: i for i, state in enumerate(basis)},
                b=b, plus=plus, minus=minus, Nb=nb, N=number, Q=charge,
                R=resource, H0=resource, Hint=hint, H=resource+hint)


def displayed(stat: str) -> sp.Matrix:
    if stat == "boson":
        return COUPLING*sp.Matrix([[0, sp.sqrt(2), 0], [sp.sqrt(2), 0, 2], [0, 2, 0]])
    return COUPLING*sp.Matrix([[0, sp.sqrt(2)], [sp.sqrt(2), 0]])


def amplitudes(stat: str, t) -> sp.Matrix:
    if stat == "boson":
        angle = sp.sqrt(6)*COUPLING*t
        return sp.Matrix([(2+sp.cos(angle))/3, -sp.I*sp.sin(angle)/sp.sqrt(3),
                          sp.sqrt(2)*(sp.cos(angle)-1)/3])
    angle = sp.sqrt(2)*COUPLING*t
    return sp.Matrix([sp.cos(angle), -sp.I*sp.sin(angle)])


def unrestricted_column(stat: str, state: tuple) -> dict:
    """Pair transitions before imposing the numerical occupation cutoff."""
    nb, plus, minus = state
    result = {}
    if nb > 0 and (stat == "boson" or plus == minus == 0):
        result[(nb-1, plus+1, minus+1)] = COUPLING*sp.sqrt(nb*(plus+1)*(minus+1))
    if plus > 0 and minus > 0:
        result[(nb+1, plus-1, minus-1)] = COUPLING*sp.sqrt((nb+1)*plus*minus)
    return result


def exact_checks(stat: str, m: dict) -> tuple[dict, dict]:
    h, hint, q, r, n = (m[name] for name in ("H", "Hint", "Q", "R", "N"))
    indices = [m["index"][state] for state in SECTORS[stat]]
    complement = [i for i in range(h.rows) if i not in indices]
    checks = {"hermitian": zero(h-h.H), "charge_conserved": zero(h*q-q*h),
              "resonant_resource_conserved": zero(h*r-r*h),
              "charged_number_and_same_sign_charge_not_conserved": not zero(h*n-n*h)}
    plus, minus = m["plus"], m["minus"]
    if stat == "fermion":
        checks["fermionic_CAR"] = all(zero(matrix) for matrix in (
            plus*plus, minus*minus, plus*minus+minus*plus,
            plus*minus.H+minus.H*plus, plus*plus.H+plus.H*plus-sp.eye(h.rows),
            minus*minus.H+minus.H*minus-sp.eye(h.rows)))
    else:
        checks["distinct_bosonic_modes_commute"] = zero(plus*minus-minus*plus) and zero(plus*minus.H-minus.H*plus)
    checks["one_sign_charge_nonnegative"] = all(value >= 0 for value in n.diagonal())
    kernel = [state for i, state in enumerate(m["basis"]) if n[i, i] == 0]
    checks["one_sign_neutral_kernel_is_carrier_vacuum"] = kernel == [(nb, 0, 0) for nb in range(3)]
    # R=4,Q=0 implies nplus=nminus=k and nb+k=2: this bound precedes the cutoff.
    untruncated = [(2-k, k, k) for k in range(3 if stat == "boson" else 2)]
    found = [state for state in m["basis"] if 2*state[0]+state[1]+state[2] == 4 and state[1] == state[2]]
    checks["cutoff_contains_complete_neutral_sector"] = set(found) == set(untruncated) == set(SECTORS[stat])
    checks["sector_invariant"] = zero(h.extract(complement, indices))
    checks["sector_matrix"] = zero(h.extract(indices, indices)-4*sp.eye(len(indices))-displayed(stat))
    columns_match = True
    for state in untruncated:
        column = sp.zeros(h.rows, 1)
        for target, weight in unrestricted_column(stat, state).items():
            if target not in m["index"]:
                columns_match = False
            else:
                column[m["index"][target]] += weight
        columns_match = columns_match and zero(column-hint[:, m["index"][state]])
    checks["no_cutoff_lost_reachable_transition"] = columns_match
    tau = sp.symbols("tau", real=True)
    amp = amplitudes(stat, tau)
    checks["analytic_state_solves_equation"] = zero(sp.I*amp.diff(tau)-displayed(stat)*amp)
    checks["analytic_state_initial_condition"] = zero(amp.subs(tau, 0)-sp.eye(len(indices))[:, 0])
    theta = sp.sqrt(6 if stat == "boson" else 2)*COUPLING*tau
    probabilities = ([(2+sp.cos(theta))**2/9, sp.sin(theta)**2/3, 2*(1-sp.cos(theta))**2/9]
                     if stat == "boson" else [sp.cos(theta)**2, sp.sin(theta)**2])
    checks["analytic_probabilities"] = zero([sp.conjugate(a)*a-p for a, p in zip(amp, probabilities)])
    checks["probability_normalization"] = zero([sum(probabilities)-1])
    identities = {"sector_basis": SECTORS[stat], "sector_Hint": str(displayed(stat)),
                  "analytic_amplitudes": str(amp), "one_sign_kernel": kernel,
                  "unrestricted_sector_columns": [{str(target): str(weight) for target, weight in
                     unrestricted_column(stat, state).items()} for state in untruncated]}
    return {name: bool(value) for name, value in checks.items()}, identities


def ode_states(operator: np.ndarray) -> np.ndarray:
    width = len(operator)
    initial = np.zeros(2*width)
    initial[0] = 1.

    def rhs(_t, stacked):
        flow = operator @ (stacked[:width]+1j*stacked[width:])
        return np.concatenate((flow.imag, -flow.real))

    solution = solve_ivp(rhs, (0., END), initial, t_eval=TIMES, method="DOP853",
                         rtol=1e-11, atol=1e-13, max_step=END/64)
    if not solution.success or solution.y.shape != (2*width, 3) or not np.isfinite(solution.y).all():
        raise ValueError("DOP853 failed to return the fixed finite trajectory")
    return (solution.y[:width]+1j*solution.y[width:]).T


def calculate() -> tuple[dict, dict]:
    checks, identities, rows, arrays = {}, {}, [], {}
    for stat in ("boson", "fermion"):
        m = model(stat)
        role_checks, identities[stat] = exact_checks(stat, m)
        checks.update({f"{stat}_{name}": value for name, value in role_checks.items()})
        operators = {name: numeric(m[name]) for name in ("H", "H0", "Hint", "Q", "R", "N", "Nb")}
        for name, value in operators.items():
            arrays[f"{stat}_{'Nbdagb' if name == 'Nb' else name}_full"] = value
        h, h0 = operators["H"], operators["H0"]
        sector = np.array([m["index"][state] for state in SECTORS[stat]], dtype=int)
        initial = np.zeros(len(h), dtype=complex)
        initial[m["index"][(2, 0, 0)]] = 1
        interaction = numeric(displayed(stat))
        ode = ode_states(4*np.eye(len(sector))+interaction)
        states, off_states, probs, analytic_probs, expectations = [], [], [], [], []
        for step, t in enumerate(TIMES):
            state = expm(-1j*h*t) @ initial
            off = expm(-1j*h0*t) @ initial
            expected = numeric(amplitudes(stat, float(t))).ravel()
            observed_probabilities = abs(state[sector])**2
            expected_probabilities = abs(expected)**2
            norm = float(np.vdot(state, state).real)
            exp_values = [float(np.vdot(state, operators[name] @ state).real) for name in ("Q", "R", "H", "Nb", "N")]
            errors = {
                "state_formula": error(state[sector]*np.exp(4j*t), expected),
                "ode_state": error(ode[step], state[sector]),
                "probability_formula": error(observed_probabilities, expected_probabilities),
                "norm": error(norm, 1.), "charge": error(exp_values[0], 0.),
                "resource": error(exp_values[1], 4.), "energy": error(exp_values[2], 4.),
                "leakage": error(np.linalg.norm(np.delete(state, sector)), 0.),
                "disabled_vertex": error(off, np.exp(-4j*t)*initial),
                "disabled_charged_number": error(float(np.vdot(off, operators['N'] @ off).real), 0.),
            }
            rows.append(dict(stat=stat, time=float(t), probabilities=observed_probabilities.tolist(),
                             expectations=[norm]+exp_values, errors=errors))
            checks[f"{stat}_time{step}"] = all(value <= BOUND for value in errors.values())
            states.append(state)
            off_states.append(off)
            probs.append(observed_probabilities)
            analytic_probs.append(expected_probabilities)
            expectations.append([norm]+exp_values)
        arrays.update({f"{stat}_basis_occupations": np.array(m["basis"], dtype=int),
                       f"{stat}_sector_indices": sector, f"{stat}_states": np.array(states),
                       f"{stat}_raw_ode_states": ode, f"{stat}_disabled_vertex_states": np.array(off_states),
                       f"{stat}_pair_probabilities": np.array(probs),
                       f"{stat}_analytic_pair_probabilities": np.array(analytic_probs),
                       f"{stat}_expectations": np.array(expectations).T,
                       f"{stat}_same_sign_commutator": numeric(m['H']*m['N']-m['N']*m['H'])})
    arrays["frozen_times"] = TIMES
    arrays["period_and_coupling"] = np.array([END, float(COUPLING)])
    if not all(np.isfinite(value).all() for value in arrays.values()):
        raise ValueError("nonfinite raw arrays")
    checks["fixed_schedule_complete"] = [(row['stat'], row['time']) for row in rows] == [
        (stat, float(t)) for stat in ("boson", "fermion") for t in TIMES]
    receipt = dict(checks=checks, identities=identities, rows=rows,
                   numerical_maxima={"relative_equality_error": max(value for row in rows for value in row['errors'].values())},
                   expectation_order=["norm", "Q", "R", "energy", "Nb", "Ncharged"],
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
    receipt = dict(schema="matter-formation-charged-conversion-v1", role="conversion", verdict="INCONCLUSIVE",
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
