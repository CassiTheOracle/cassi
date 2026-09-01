"""Focused contracts for the frozen L44 semantic verifier."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification.verify_l44_semantic_harmonic_replication import (
    SemanticComparisonError,
    require_full_score_match,
    semantic_compare,
)


def semantic_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    scores = np.array([[[1.0, 0.5, 0.0], [0.0, 0.25, 0.0]]])
    symbols = np.array([[0, 1]])
    available = np.array([[True, False]])
    expected = {
        "age_scores": scores.copy(),
        "age_symbols": symbols.copy(),
        "age_available": available.copy(),
    }
    return scores, symbols, available, expected


def test_equal_available_winners_pass_without_mutating_inputs() -> None:
    scores, symbols, available, expected = semantic_inputs()
    before = (
        scores.copy(),
        symbols.copy(),
        available.copy(),
        {name: value.copy() for name, value in expected.items()},
    )

    counts = semantic_compare(scores, symbols, available, expected)

    assert counts == {
        "available_winner_mismatches": 0,
        "ignored_unavailable_winner_mismatches": 0,
    }
    assert np.array_equal(scores, before[0])
    assert np.array_equal(symbols, before[1])
    assert np.array_equal(available, before[2])
    for name, value in expected.items():
        assert np.array_equal(value, before[3][name])


def test_unavailable_winner_disagreement_is_counted_not_failed() -> None:
    scores, symbols, available, expected = semantic_inputs()
    symbols[0, 1] = 2

    counts = semantic_compare(scores, symbols, available, expected)

    assert counts == {
        "available_winner_mismatches": 0,
        "ignored_unavailable_winner_mismatches": 1,
    }


def test_available_winner_disagreement_fails() -> None:
    scores, symbols, available, expected = semantic_inputs()
    symbols[0, 0] = 2

    with pytest.raises(SemanticComparisonError, match="available age-winner"):
        semantic_compare(scores, symbols, available, expected)


def test_availability_disagreement_fails() -> None:
    scores, symbols, available, expected = semantic_inputs()
    available[0, 1] = True

    with pytest.raises(SemanticComparisonError, match="age-availability"):
        semantic_compare(scores, symbols, available, expected)


def test_age_score_disagreement_fails() -> None:
    scores, symbols, available, expected = semantic_inputs()
    scores[0, 0, 0] += 1.0e-2

    with pytest.raises(SemanticComparisonError, match="age-score"):
        semantic_compare(scores, symbols, available, expected)


def test_full_aggregate_score_disagreement_fails() -> None:
    expected = np.array([[8.0, 1.0, 0.0]])
    require_full_score_match(expected.copy(), expected, "equal")
    recorded = expected.copy()
    recorded[0, 1] += 1.0e-2

    with pytest.raises(SemanticComparisonError, match="full-score"):
        require_full_score_match(recorded, expected, "different")
