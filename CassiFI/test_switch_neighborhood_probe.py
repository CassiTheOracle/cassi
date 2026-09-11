"""Fast structural checks for the switch-neighborhood probe.

These tests deliberately avoid the receipt and all brute-force basis censuses.
They pin the legal-switch populations, canonical replay, independent search
agreement, trivial low-nullity handling, and deterministic two-switch walks.
"""

from __future__ import annotations

import random

import run_frame_search_probe as frame_search
import run_frame_separation_probe as frame_separation
import run_switch_neighborhood_probe as probe
import verify_switch_neighborhood_probe as verifier


CONTROLS = (
    ("all-bases-ternary-sat-n12", frame_separation.ALL_BASES_TERNARY_SAT, 424, 368),
    ("all-bases-ternary-unsat-n15", frame_separation.ALL_BASES_TERNARY_UNSAT, 726, 646),
)


def unique_neighbors(formula):
    base = verifier.canonical(formula)
    formulas = {
        probe.canonical_digest(probe.apply_spec(base, spec)): spec
        for spec in probe.switch_specs(base)
    }
    return formulas


def replay_walk(formula, seed: int):
    current = verifier.canonical(formula)
    digests = []
    rng = random.Random(seed)
    for _ in range(2):
        specs = probe.switch_specs(current)
        current = probe.apply_spec(current, specs[rng.randrange(len(specs))])
        digests.append(probe.canonical_digest(current))
    return digests, current


def search_verdict(formula):
    canonical = verifier.canonical(formula)
    _, columns = verifier.kernel_columns(canonical)
    classes = verifier.classes_of(columns)
    nullity = len(columns[0])
    chosen_runner, _nodes, capped_runner = frame_search.frame_search(classes, nullity)
    chosen_verifier, _nodes, capped_verifier = verifier.search(classes, nullity)
    assert not capped_runner and not capped_verifier
    return chosen_runner is not None, chosen_verifier is not None


def test_complete_one_switch_populations_are_pinned() -> None:
    for _name, formula, spec_count, neighbor_count in CONTROLS:
        assert len(probe.switch_specs(formula)) == spec_count
        assert len(unique_neighbors(formula)) == neighbor_count


def test_switch_replay_preserves_cubic_canonical_structure() -> None:
    for _name, formula, _spec_count, _neighbor_count in CONTROLS:
        base = verifier.canonical(formula)
        spec = probe.switch_specs(base)[0]
        switched = probe.apply_spec(base, spec)
        assert switched == verifier.canonical(switched)
        assert all(len(clause) == 3 and len(set(clause)) == 3 for clause in switched)
        assert all(
            sum(variable in clause for clause in switched) == 3
            for variable in range(1, len(switched) + 1)
        )


def test_runner_and_independent_search_agree_on_controls_and_neighbors() -> None:
    for _name, formula, _spec_count, _neighbor_count in CONTROLS:
        assert search_verdict(formula) == (False, False)
        first_neighbor = probe.apply_spec(verifier.canonical(formula), probe.switch_specs(formula)[0])
        assert search_verdict(first_neighbor)[0] == search_verdict(first_neighbor)[1]


def test_low_nullity_search_is_trivially_frame() -> None:
    assert verifier.search([(1,)], 1)[0] == [0]
    assert verifier.search([(1, 0), (0, 1)], 2)[0] == [0, 1]


def test_synthetic_positive_and_negative_anchors_fire() -> None:
    verifier.synthetic_anchors()


def test_two_switch_walk_replay_is_seed_deterministic() -> None:
    for position, (_name, formula, _spec_count, _neighbor_count) in enumerate(CONTROLS):
        first, first_formula = replay_walk(formula, probe.SEED + 1 + position)
        second, second_formula = replay_walk(formula, probe.SEED + 1 + position)
        assert first == second
        assert first_formula == second_formula
        assert first[0] in unique_neighbors(formula)
