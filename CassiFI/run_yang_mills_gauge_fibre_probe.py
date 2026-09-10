#!/usr/bin/env python
"""Use CassiFI's clause field to resolve a gauge-compatible SU(2) block fibre.

The probe studies the four internal spokes of a refined 2x2 plaquette with
all eight outer links fixed in the fundamental representation.  Integer labels
are n=2j.  Boundary Gauss constraints and a fixed four-valent recoupling basis
become CNF clauses; every decision, implication, conflict, learned clause, and
work counter then remains in one immutable ClauseFieldState tensor.

This is a representation-support calculation.  It does not compute magnetic
matrix elements, recoupling amplitudes, an interacting-volume estimate, or a
continuum mass gap.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cassi_clause_field import ClauseField, ClauseFieldProfile

SCHEMA = "cassifi.yang-mills-gauge-fibre-probe.v1"
OUTPUT = Path("_diag/yang_mills_gauge_fibre_probe.json")
N_MAX_VALUES = (1, 2, 4)
SPOKES = ("north", "east", "south", "west")
PAIRING = (("north", "east"), ("south", "west"))
BOUNDARY_LABEL = 1  # n=2j=1, hence j=1/2.
ACTION_VOCABULARY = (
    "decide",
    "propagate",
    "conflict-backtrack",
    "sat",
    "unsat",
    "exhaust",
)

Clause = tuple[int, ...]
Formula = tuple[Clause, ...]


@dataclass(frozen=True, slots=True)
class Encoding:
    n_max: int
    variables: int
    clauses: Formula
    spoke_variables: Mapping[str, Mapping[int, int]]
    channel_variables: Mapping[int, int]


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def admissible_triple(left: int, right: int, total: int) -> bool:
    """Return whether V_left tensor V_right contains V_total for n=2j labels."""

    return (
        min(left, right, total) >= 0
        and abs(left - right) <= total <= left + right
        and (left + right + total) % 2 == 0
    )


def coupled_labels(left: int, right: int) -> tuple[int, ...]:
    return tuple(range(abs(left - right), left + right + 1, 2))


def exactly_one(variables: Sequence[int]) -> Formula:
    if not variables:
        raise ValueError("an exactly-one family cannot be empty")
    clauses: list[Clause] = [tuple(variables)]
    clauses.extend(
        (-left, -right)
        for left, right in itertools.combinations(variables, 2)
    )
    return tuple(clauses)


def make_encoding(n_max: int) -> Encoding:
    if isinstance(n_max, bool) or not isinstance(n_max, int) or n_max < 1:
        raise ValueError("n_max must be a positive integer")

    next_variable = 1
    spoke_variables: dict[str, dict[int, int]] = {}
    for spoke in SPOKES:
        spoke_variables[spoke] = {}
        for label in range(n_max + 1):
            spoke_variables[spoke][label] = next_variable
            next_variable += 1

    channel_variables: dict[int, int] = {}
    for label in range(2 * n_max + 1):
        channel_variables[label] = next_variable
        next_variable += 1

    clauses: list[Clause] = []
    for spoke in SPOKES:
        clauses.extend(exactly_one(tuple(spoke_variables[spoke].values())))
    clauses.extend(exactly_one(tuple(channel_variables.values())))

    # Each boundary midpoint is trivalent: 1/2 tensor 1/2 can feed only j=0 or 1.
    for spoke in SPOKES:
        for label, variable in spoke_variables[spoke].items():
            if not admissible_triple(BOUNDARY_LABEL, BOUNDARY_LABEL, label):
                clauses.append((-variable,))

    # The four-valent centre is resolved by one common intermediate channel.
    for left_spoke, right_spoke in PAIRING:
        for left_label, right_label, channel in itertools.product(
            range(n_max + 1),
            range(n_max + 1),
            range(2 * n_max + 1),
        ):
            if admissible_triple(left_label, right_label, channel):
                continue
            clauses.append(
                (
                    -spoke_variables[left_spoke][left_label],
                    -spoke_variables[right_spoke][right_label],
                    -channel_variables[channel],
                )
            )

    return Encoding(
        n_max=n_max,
        variables=next_variable - 1,
        clauses=tuple(clauses),
        spoke_variables=spoke_variables,
        channel_variables=channel_variables,
    )


def satisfies(formula: Formula, assignment: Sequence[int]) -> bool:
    return all(
        any(assignment[abs(literal) - 1] == (1 if literal > 0 else -1) for literal in clause)
        for clause in formula
    )


def selected_label(variables: Mapping[int, int], assignment: Sequence[int]) -> int:
    selected = [
        label
        for label, variable in variables.items()
        if assignment[variable - 1] == 1
    ]
    if len(selected) != 1:
        raise AssertionError(f"expected one selected label, found {selected}")
    return selected[0]


def decode_model(encoding: Encoding, assignment: Sequence[int]) -> dict[str, Any]:
    return {
        "spokes": {
            spoke: selected_label(encoding.spoke_variables[spoke], assignment)
            for spoke in SPOKES
        },
        "channel": selected_label(encoding.channel_variables, assignment),
    }


def profile_for(variables: int, clauses: int) -> ClauseFieldProfile:
    return ClauseFieldProfile(
        max_variables=variables,
        max_original_clauses=clauses,
        max_clause_width=variables,
        max_learned_clauses=8 * variables,
        max_transitions=max(100_000, 64 * variables * max(1, clauses)),
    )


def run_query(
    encoding: Encoding,
    name: str,
    extra_clauses: Iterable[Clause],
    expected_status: str,
    *,
    checkpoint: bool = False,
) -> dict[str, Any]:
    formula = encoding.clauses + tuple(extra_clauses)
    field = ClauseField(profile_for(encoding.variables, len(formula)))
    state = field.initial(formula, variable_count=encoding.variables)
    initial_sha256 = field.state_sha256(state)
    trace = hashlib.sha256()
    action_counts = {action: 0 for action in ACTION_VOCABULARY}
    conflict_proofs = 0

    while field.status(state) == "running":
        state, step = field.step(state)
        action = str(step["action"])
        if action not in action_counts:
            raise AssertionError(f"unexpected field action {action!r}")
        action_counts[action] += 1
        if step.get("conflict_proof") is not None:
            conflict_proofs += 1
        trace.update(
            canonical(
                {
                    "action": action,
                    "selected_literal": step.get("selected_literal"),
                    "conflict_clause": step.get("conflict_clause"),
                    "learned_clause": step.get("learned_clause"),
                    "conflict_proof": step.get("conflict_proof"),
                    "state_sha256": step["state_sha256"],
                    "work": step.get("work"),
                }
            )
        )

    inspected = field.inspect(state)
    status = str(inspected["status"])
    if status != expected_status:
        raise AssertionError(f"{name}: expected {expected_status}, got {status}")

    assignment = tuple(int(value) for value in inspected["assignment"])
    certificate_verified = status != "sat" or satisfies(formula, assignment)
    if not certificate_verified:
        raise AssertionError(f"{name}: field returned an invalid SAT assignment")

    checkpoint_verified: bool | None = None
    if checkpoint:
        descriptor = field.descriptor(state)
        restored_field, restored_state = ClauseField.from_descriptor(descriptor)
        checkpoint_verified = (
            restored_field.state_sha256(restored_state) == field.state_sha256(state)
            and restored_field.inspect(restored_state) == inspected
        )
        if not checkpoint_verified:
            raise AssertionError(f"{name}: field checkpoint did not round-trip exactly")

    return {
        "name": name,
        "status": status,
        "expected_status": expected_status,
        "certificate_verified": certificate_verified,
        "initial_state_sha256": initial_sha256,
        "final_state_sha256": field.state_sha256(state),
        "trace_sha256": trace.hexdigest(),
        "field_bytes": state.nbytes,
        "profile": field.profile.as_dict(),
        "action_counts": action_counts,
        "conflict_proofs": conflict_proofs,
        "resource_ledger": inspected["resource_ledger"],
        "model": decode_model(encoding, assignment) if status == "sat" else None,
        "checkpoint_verified": checkpoint_verified,
    }


def tensor_singlet_multiplicity(labels: Sequence[int]) -> int:
    """Cross-check singlet counts by left-associated SU(2) fusion."""

    multiplicities: dict[int, int] = {0: 1}
    for label in labels:
        successor: dict[int, int] = {}
        for carried, multiplicity in multiplicities.items():
            for total in coupled_labels(carried, label):
                successor[total] = successor.get(total, 0) + multiplicity
        multiplicities = successor
    return multiplicities.get(0, 0)


def analytic_basis(n_max: int) -> list[dict[str, Any]]:
    midpoint_labels = tuple(
        label
        for label in range(n_max + 1)
        if admissible_triple(BOUNDARY_LABEL, BOUNDARY_LABEL, label)
    )
    rows: list[dict[str, Any]] = []
    for labels in itertools.product(midpoint_labels, repeat=len(SPOKES)):
        spokes = dict(zip(SPOKES, labels))
        channels = tuple(
            channel
            for channel in range(2 * n_max + 1)
            if all(
                admissible_triple(spokes[left], spokes[right], channel)
                for left, right in PAIRING
            )
        )
        recurrence_multiplicity = tensor_singlet_multiplicity(labels)
        if len(channels) != recurrence_multiplicity:
            raise AssertionError(
                f"pairing and tensor-product multiplicities disagree for {spokes}"
            )
        for channel in channels:
            interior_four_k = sum(label * (label + 2) for label in labels)
            boundary_four_k = 8 * BOUNDARY_LABEL * (BOUNDARY_LABEL + 2)
            rows.append(
                {
                    "spokes": spokes,
                    "channel": channel,
                    "active_spokes": sum(label != 0 for label in labels),
                    "interior_electric_K": interior_four_k // 4,
                    "total_electric_K": (boundary_four_k + interior_four_k) // 4,
                }
            )
    return rows


def candidate_units(
    encoding: Encoding,
    spokes: Mapping[str, int],
    channel: int,
) -> Formula:
    return tuple(
        [(encoding.spoke_variables[spoke][spokes[spoke]],) for spoke in SPOKES]
        + [(encoding.channel_variables[channel],)]
    )


def basis_key(row: Mapping[str, Any]) -> tuple[int, ...]:
    spokes = row["spokes"]
    return tuple(int(spokes[spoke]) for spoke in SPOKES) + (int(row["channel"]),)


def summarize_cutoff(n_max: int) -> dict[str, Any]:
    encoding = make_encoding(n_max)
    expected_basis = analytic_basis(n_max)
    expected_keys = {basis_key(row) for row in expected_basis}
    midpoint_labels = tuple(
        label
        for label in range(n_max + 1)
        if admissible_triple(BOUNDARY_LABEL, BOUNDARY_LABEL, label)
    )

    base = run_query(
        encoding,
        f"n_max_{n_max}_base",
        (),
        "sat",
        checkpoint=True,
    )

    candidate_rows: list[dict[str, Any]] = []
    for labels in itertools.product(midpoint_labels, repeat=len(SPOKES)):
        spokes = dict(zip(SPOKES, labels))
        for channel in range(2 * n_max + 1):
            key = tuple(labels) + (channel,)
            expected_status = "sat" if key in expected_keys else "unsat"
            query = run_query(
                encoding,
                "candidate_" + "_".join(map(str, key)),
                candidate_units(encoding, spokes, channel),
                expected_status,
            )
            candidate_rows.append(
                {
                    "spokes": spokes,
                    "channel": channel,
                    "status": query["status"],
                    "transitions": query["resource_ledger"]["transitions"],
                    "conflicts": query["resource_ledger"]["conflicts"],
                    "trace_sha256": query["trace_sha256"],
                }
            )

    measured_keys = {
        tuple(int(row["spokes"][spoke]) for spoke in SPOKES) + (int(row["channel"]),)
        for row in candidate_rows
        if row["status"] == "sat"
    }
    if measured_keys != expected_keys:
        raise AssertionError(f"n_max={n_max}: field basis differs from analytic basis")

    forbidden_rows: list[dict[str, Any]] = []
    forbidden_labels = tuple(
        label for label in range(n_max + 1) if label not in midpoint_labels
    )
    for spoke, label in itertools.product(SPOKES, forbidden_labels):
        query = run_query(
            encoding,
            f"forbidden_{spoke}_{label}",
            ((encoding.spoke_variables[spoke][label],),),
            "unsat",
        )
        forbidden_rows.append(
            {
                "spoke": spoke,
                "label": label,
                "status": query["status"],
                "transitions": query["resource_ledger"]["transitions"],
                "conflicts": query["resource_ledger"]["conflicts"],
            }
        )

    one_spoke_query: dict[str, Any] | None = None
    pair_witness_query: dict[str, Any] | None = None
    if 2 in midpoint_labels:
        active = [encoding.spoke_variables[spoke][2] for spoke in SPOKES]
        exactly_one_active: list[Clause] = [tuple(active)]
        exactly_one_active.extend(
            (-left, -right) for left, right in itertools.combinations(active, 2)
        )
        one_spoke_query = run_query(
            encoding,
            f"n_max_{n_max}_exactly_one_active_spoke",
            exactly_one_active,
            "unsat",
            checkpoint=True,
        )
        pair_spokes = {spoke: (2 if spoke in {"north", "east"} else 0) for spoke in SPOKES}
        pair_witness_query = run_query(
            encoding,
            f"n_max_{n_max}_adjacent_pair_witness",
            tuple(
                (encoding.spoke_variables[spoke][label],)
                for spoke, label in pair_spokes.items()
            ),
            "sat",
            checkpoint=True,
        )

    energy_strata: dict[int, dict[str, int]] = {}
    for row in expected_basis:
        active_spokes = int(row["active_spokes"])
        if active_spokes not in energy_strata:
            energy_strata[active_spokes] = {
                "basis_states": 0,
                "interior_electric_K": int(row["interior_electric_K"]),
                "total_electric_K": int(row["total_electric_K"]),
            }
        energy_strata[active_spokes]["basis_states"] += 1

    candidate_transitions = [int(row["transitions"]) for row in candidate_rows]
    return {
        "n_max": n_max,
        "j_max": n_max / 2,
        "variables": encoding.variables,
        "base_clauses": len(encoding.clauses),
        "midpoint_labels": list(midpoint_labels),
        "candidate_queries": len(candidate_rows),
        "candidate_sat": sum(row["status"] == "sat" for row in candidate_rows),
        "candidate_unsat": sum(row["status"] == "unsat" for row in candidate_rows),
        "all_candidate_classifications_match": measured_keys == expected_keys,
        "candidate_transition_range": [
            min(candidate_transitions),
            max(candidate_transitions),
        ],
        "candidate_rows_sha256": sha256(candidate_rows),
        "forbidden_midpoint_queries": forbidden_rows,
        "all_forbidden_midpoint_queries_unsat": all(
            row["status"] == "unsat" for row in forbidden_rows
        ),
        "base_query": base,
        "one_active_spoke_query": one_spoke_query,
        "adjacent_pair_witness_query": pair_witness_query,
        "basis": expected_basis,
        "basis_sha256": sha256(expected_basis),
        "basis_dimension": len(expected_basis),
        "energy_strata": {str(key): value for key, value in sorted(energy_strata.items())},
    }


def run() -> dict[str, Any]:
    cutoffs = [summarize_cutoff(n_max) for n_max in N_MAX_VALUES]
    saturated = [row for row in cutoffs if int(row["n_max"]) >= 2]
    saturated_keys = [
        {basis_key(basis_row) for basis_row in row["basis"]}
        for row in saturated
    ]
    cutoff_saturation = bool(saturated_keys) and all(
        keys == saturated_keys[0] for keys in saturated_keys[1:]
    )
    if not cutoff_saturation:
        raise AssertionError("the fixed-boundary fibre did not saturate at n_max=2")
    if len(saturated_keys[0]) != 14:
        raise AssertionError("the saturated fixed-boundary fibre is not 14-dimensional")

    reference = next(row for row in cutoffs if int(row["n_max"]) == 2)
    one_spoke = reference["one_active_spoke_query"]
    pair_witness = reference["adjacent_pair_witness_query"]
    if one_spoke is None or pair_witness is None:
        raise AssertionError("minimum-excitation queries were not run")
    if one_spoke["status"] != "unsat" or pair_witness["status"] != "sat":
        raise AssertionError("minimum non-bare spoke count was not resolved")

    receipt = {
        "schema": SCHEMA,
        "question": (
            "Can CassiFI's field-owned exact search close the representation-support "
            "part of the smallest genuine SU(2) refined-block fibre?"
        ),
        "geometry": {
            "block": "open 2x2 plaquette refinement",
            "outer_links": 8,
            "outer_link_label_n_equals_2j": BOUNDARY_LABEL,
            "outer_link_spin": "1/2",
            "internal_spokes": list(SPOKES),
            "centre_pairing": [list(pair) for pair in PAIRING],
            "gauss_constraints": (
                "each boundary midpoint couples (1,1,n_spoke) to spin zero; "
                "the centre uses one common intermediate n_channel for the two pairs"
            ),
        },
        "field_ownership": {
            "state": "one immutable ClauseFieldState tensor per fixed query",
            "inside_field": [
                "CNF",
                "assignments",
                "implication reasons",
                "decision trail",
                "learned clauses",
                "resource counters",
            ],
            "fixed_query_schedule": (
                "source-declared Cartesian candidate queries plus source-declared "
                "one-spoke and pair-witness queries"
            ),
            "host_adaptive_search": 0,
            "learned_side_tables": 0,
            "model_calls": 0,
            "label_precision": "validated exact integers in float64 field coordinates",
        },
        "fusion_cross_check": (
            "the same SU(2) fusion rule is accumulated by a left-associated "
            "tensor-product recurrence and agrees with the paired-channel count "
            "configuration by configuration"
        ),
        "cutoffs": cutoffs,
        "measured_result": {
            "cutoff_saturates_at_n_max": 2,
            "cutoff_saturates_at_j_max": 1,
            "saturated_basis_dimension": 14,
            "basis_counts_by_active_spokes": {
                key: value["basis_states"]
                for key, value in reference["energy_strata"].items()
            },
            "electric_K_by_active_spokes": {
                key: value["total_electric_K"]
                for key, value in reference["energy_strata"].items()
            },
            "single_active_spoke_field_status": "unsat in every source-declared fixed one-spoke query",
            "minimum_nonbare_active_spokes": 2,
            "cutoff_stability_sha256": sha256(
                [sorted(keys) for keys in saturated_keys]
            ),
        },
        "usefulness": (
            "The measured clause-field classifications expose a 14-state "
            "fixed-boundary gauge basis and exercise exact gauge-constraint "
            "search without host-adaptive branches."
        ),
        "limits": [
            "The query fixes the outer eight links to the fundamental representation.",
            "The result identifies representation support and intertwiner multiplicity, not 6j amplitudes.",
            "Magnetic plaquette multiplication changes boundary sectors, so neighbouring fibres remain necessary.",
            "No volume-uniform weak-coupling estimate, thermodynamic limit, continuum construction, or mass gap follows.",
            "The receipt has no source-independent reconstruction or global UNSAT-proof audit.",
        ],
    }
    receipt["receipt_sha256"] = sha256(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    receipt = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    measured = receipt["measured_result"]
    print(f"Receipt: {args.output.resolve()}")
    print(f"Receipt SHA-256: {receipt['receipt_sha256']}")
    print(
        "Fixed-boundary fibre: "
        f"dim={measured['saturated_basis_dimension']} "
        f"at n_max>={measured['cutoff_saturates_at_n_max']}"
    )
    print(
        "Basis counts by active spokes: "
        + json.dumps(measured["basis_counts_by_active_spokes"], sort_keys=True)
    )
    print(
        "Electric K by active spokes: "
        + json.dumps(measured["electric_K_by_active_spokes"], sort_keys=True)
    )
    print("Single-spoke sector: UNSAT; adjacent-pair witness: SAT")
    print("All fixed candidate classifications and the fusion multiplicity cross-check agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
