from __future__ import annotations

import json
from pathlib import Path

import pytest

from cassi_alias_exact_one_field import regular_monotone_formula, recognize_degree_two_three_exact_one
from cassi_alias_obstruction import evaluate_alias_candidate
from run_alias_cut_complexity import (
    _count_simple_fully_cubic_sources_c7,
    _count_simple_fully_cubic_sources_dp,
    _enumerate_simple_fully_cubic_sources,
    classify_cut_subsumption,
    exact_one_cnf,
    run_analysis,
)
from verify_alias_cut_complexity import (
    VerificationError,
    _count_simple_fully_cubic_sources_c7 as _verify_count_simple_fully_cubic_sources_c7,
    _count_simple_fully_cubic_sources_dp as _verify_count_simple_fully_cubic_sources_dp,
    verify,
    verify_cut_subsumption,
)


def test_source_clause_witness_uses_the_canonical_four_clause_basis() -> None:
    formula = [list(clause) for clause in regular_monotone_formula(6, 6, seed=0)]
    recognized = recognize_degree_two_three_exact_one(formula, variable_count=6)
    candidate = evaluate_alias_candidate(recognized, (0,) * len(recognized.cubic_variables))
    cut = candidate["cut"]
    assert cut is not None
    assert len(exact_one_cnf(formula)) == 4 * len(formula)
    witness = classify_cut_subsumption(formula, cut)
    assert witness is not None
    verify_cut_subsumption(formula, cut, witness)

    tampered = dict(witness)
    tampered["cnf_index"] = witness["cnf_index"] + 1
    with pytest.raises(VerificationError):
        verify_cut_subsumption(formula, cut, tampered)


def test_c7_count_only_dp_matches_bounded_enumeration() -> None:
    for clauses in range(4, 7):
        brute_count = len(_enumerate_simple_fully_cubic_sources(clauses))
        assert _count_simple_fully_cubic_sources_dp(clauses) == brute_count
        assert _verify_count_simple_fully_cubic_sources_dp(clauses) == brute_count
    runner_c7 = _count_simple_fully_cubic_sources_c7()
    verifier_c7 = _verify_count_simple_fully_cubic_sources_c7()
    assert runner_c7 == verifier_c7 == 11_205


def test_complexity_receipt_roundtrip_and_nested_ledger_tamper(tmp_path: Path) -> None:
    receipt_path = tmp_path / "alias_cut_complexity.json"
    receipt = run_analysis(receipt_path)
    checked = verify(receipt_path)
    assert checked["summary"] == receipt["summary"]
    census = receipt["fully_cubic_census"]
    assert census["min_clauses"] == 4
    assert census["max_clauses"] == 6
    assert census["max_variables"] == 6
    assert census["complete_cutoff"] == 6
    universe = census["universe"]
    assert universe["filter_rule"] == (
        "retain iff every variable has degree exactly 3 after selecting all c distinct triples"
    )
    assert universe["universe_kind"] == "labelled_simple_clause_triple_subsets"
    assert universe["clause_labels"] == (
        "not separately labelled; clauses are the selected triples"
    )
    assert universe["graph_isomorphism_quotient"] == "none"
    assert universe["unlabeled_graphs_enumerated"] is False
    assert universe["complete_cutoff"] == 6
    assert universe["by_clause_count"] == {
        "4": {
            "candidate_triples": 4,
            "naive_row_subsets": 1,
            "accepted_sources": 1,
            "degree_filter_rejections": 0,
        },
        "5": {
            "candidate_triples": 10,
            "naive_row_subsets": 252,
            "accepted_sources": 12,
            "degree_filter_rejections": 240,
        },
        "6": {
            "candidate_triples": 20,
            "naive_row_subsets": 38_760,
            "accepted_sources": 330,
            "degree_filter_rejections": 38_430,
        },
    }
    assert universe["total_naive_row_subsets"] == 39_013
    assert universe["total_accepted_sources"] == 343
    assert universe["total_degree_filter_rejections"] == 38_670
    with pytest.raises(ValueError):
        _enumerate_simple_fully_cubic_sources(7)
    assert census["summary"]["sources"] == 343
    assert census["summary"]["connected_sources"] == 343
    assert census["summary"]["candidate_assignments"] == 21_520
    assert census["summary"]["sat_candidates"] == 480
    assert census["summary"]["unsat_candidates"] == 21_040
    assert census["summary"]["emitted_certificate_records"] == 21_040
    assert census["summary"]["distinct_certificate_records"] == 5_807
    assert census["summary"]["distinct_projected_clauses"] == 5_807
    assert census["summary"]["conflict_precedence_violations"] == 0
    assert census["summary"]["cut_kinds"] == {"overfill": 18_653, "tutte": 2_387}
    assert census["summary"]["subsumption_relations"] == {
        "equal": 21_040,
        "proper": 0,
        "null": 0,
    }
    assert census["summary"]["counterexamples"] == 0
    assert checked["refusal_controls_refused"] > 0
    assert checked["summary"]["candidate_nonlocal_mixed_cuts"] > 0
    assert checked["summary"]["strict_weakenings"] > 0

    tampered = json.loads(receipt_path.read_text(encoding="utf-8"))
    for case in tampered["cases"]:
        if case["solver"]["cut_subsumptions"]:
            case["solver"]["cut_subsumptions"][0]["relation"] = "proper"
            break
    receipt_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises((VerificationError, AssertionError)):
        verify(receipt_path)
