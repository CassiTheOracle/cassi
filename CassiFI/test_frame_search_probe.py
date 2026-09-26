"""Frame-search checks: complete class search against census verdicts.

Pins the search's coverage bookkeeping (the greedy-exchange trap only closes
when the pair formed by the two later additions is counted), the
dimension-general span test, the control verdicts against the
frame-separation census, runner/verifier agreement on a connected chain, and
the certificate path on every width-two frame.
"""

from __future__ import annotations

import hashlib
import json

import run_frame_search_probe as probe
import run_frame_separation_probe as fsp
import run_mixed_schaefer_frame_obstruction as mixed
import verify_frame_search_probe as verifier


def test_control_verdicts_match_the_recorded_census() -> None:
    for name, formula in fsp.CONTROLS:
        record = probe.evaluate_case(name, formula, None)
        expected = "frame" if fsp.census_width(formula) == 2 else "no_frame"
        assert record["verdict"] == expected, name
        assert record["capped"] is False, name
        if record["verdict"] == "frame":
            assert record["width"] == 2, name


def test_search_bookkeeping_finds_the_greedy_exchange_trap_frame() -> None:
    formula = dict(fsp.CONTROLS)["greedy-exchange-trap-sat-n9"]
    record = probe.evaluate_case("trap", formula, "frame")
    assert record["verdict"] == "frame"
    assert record["width"] == 2


def test_span_test_is_dimension_general() -> None:
    left, right = (1, 0, 0, 0, 0), (0, 1, 0, 0, 0)
    inside, outside = (1, 1, 0, 0, 0), (1, 1, 0, 0, 7)
    assert probe.in_span(left, right, inside)
    assert not probe.in_span(left, right, outside)


def test_connected_chain_verdict_and_connectivity() -> None:
    formula = probe.chain([fsp.ALL_BASES_TERNARY_SAT] * 2, [(0, 1)])
    record = probe.evaluate_case("path-sat-x2", formula, "no_frame")
    assert record["verdict"] == "no_frame"
    assert record["capped"] is False
    assert record["connected"] is True
    assert record["size"] == 24 and record["nullity"] == 5


def test_runner_and_verifier_searches_agree_on_a_chain() -> None:
    formula = probe.chain([fsp.ALL_BASES_TERNARY_SAT] * 3, [(0, 1), (1, 2)])
    canonical = verifier.canonical(formula)
    _, columns, _ = verifier.kernel_columns(canonical)
    classes = verifier.classes_of(columns)
    chosen, _nodes, capped = verifier.search(classes, len(columns[0]))
    assert not capped
    assert chosen is None
    record = probe.evaluate_case("path-sat-x3", formula, "no_frame")
    assert record["verdict"] == "no_frame"


def test_certificates_reverify_on_every_frame_case() -> None:
    checked = 0
    for name, formula in fsp.CONTROLS:
        record = probe.evaluate_case(name, formula, None)
        if record["verdict"] != "frame":
            continue
        canonical = verifier.canonical(formula)
        _, columns, _ = verifier.kernel_columns(canonical)
        classes = verifier.classes_of(columns)
        width = verifier.check_certificate(name, canonical, record, columns, classes)
        assert width == 2, name
        checked += 1
    assert checked == 3


def test_switch_population_digest_is_pinned() -> None:
    digests = sorted(probe.digest(formula) for formula in probe.switch_formulas())
    payload = json.dumps(digests, separators=(",", ":"))
    assert len(digests) == 1620
    assert (
        hashlib.sha256(payload.encode("ascii")).hexdigest()
        == "945f9474cc73d8830b7b5a474e993769f7591d5d4c1c262fb7bdb3dbf50c9154"
    )


def test_full_rank_dual_and_frame_screen_are_zero_dimensional() -> None:
    formula = ((1, 2, 3), (1, 2, 4), (1, 3, 4), (2, 3, 4))
    columns = mixed.dual_columns(formula)
    assert columns == ((), (), (), ())

    coverage = mixed.coverage_screen(columns, 2)
    assert coverage == {
        "exists": True,
        "complete": True,
        "ground_size": 4,
        "nullity": 0,
        "candidates_after_filter": 1,
        "candidates_examined": 0,
        "witness_free_columns": [],
    }

    screen = mixed.frame_screen(formula)
    assert screen["canonical_width"] == 0
    assert screen["width_two_basis_exists"] is True
    assert screen["width_two_search_complete"] is True
    assert screen["witness_free_columns"] == []
    assert screen["witness_width"] == 0
    assert screen["omega"] == 0

    record = probe.evaluate_case("full-rank-k4", formula, "frame")
    assert record["verdict"] == "frame"
    assert record["nullity"] == 0
    assert record["width"] == 0

    independent_rank, independent_columns, _ = verifier.kernel_columns(formula)
    assert independent_rank == 4
    independent_classes = verifier.classes_of(independent_columns)
    chosen, nodes, capped = verifier.search(independent_classes, 0)
    assert chosen == []
    assert nodes == 1
    assert capped is False
    assert verifier.width_of(independent_columns, []) == 0



def test_rank_one_dual_uses_singleton_coverage() -> None:
    formula = (
        (1, 2, 4),
        (1, 3, 4),
        (1, 8, 9),
        (2, 5, 11),
        (2, 6, 8),
        (3, 4, 11),
        (3, 14, 15),
        (5, 10, 14),
        (5, 11, 14),
        (6, 8, 9),
        (6, 12, 13),
        (7, 10, 12),
        (7, 10, 15),
        (7, 12, 13),
        (9, 13, 15),
    )
    columns = mixed.dual_columns(formula)
    assert len(columns) == 15
    assert len(columns[0]) == 1
    assert all(len(column) == 1 and column[0] != 0 for column in columns)

    coverage = mixed.coverage_screen(columns, 2)
    assert coverage["exists"] is True
    assert coverage["ground_size"] == 15
    assert coverage["nullity"] == 1
    assert coverage["witness_free_columns"] == [1]

    screen = mixed.frame_screen(formula)
    assert screen["omega"] == 1
    assert screen["witness_width"] == 1

    record = probe.evaluate_case("rank-one", formula, "frame")
    assert record["verdict"] == "frame"
    assert record["nullity"] == 1
    assert record["width"] == 1
    independent_rank, independent_columns, _ = verifier.kernel_columns(formula)
    assert independent_rank == 14
    independent_nullity = len(independent_columns[0]) if independent_columns else 0
    independent_classes = verifier.classes_of(independent_columns)
    chosen, nodes, capped = verifier.search(independent_classes, independent_nullity)
    assert chosen == [0]
    assert nodes == 1
    assert capped is False
    assert verifier.width_of(independent_columns, [0]) == 1
