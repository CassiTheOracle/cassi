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
