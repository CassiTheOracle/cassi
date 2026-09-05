"""Observable contract for the adopted chromatic recall runtime."""

from __future__ import annotations

import pytest

from runtime.run_cassi_chromatic_recall import recall_sequence


def test_adopted_runtime_recalls_current_then_predecessor() -> None:
    result = recall_sequence((37, 134))
    first, second = result["receipts"]

    assert result["status"] == "ok"
    assert (
        result["operator_profile_id"]
        == "cassi.qi-ordered-relational-chromatic-recall.v1"
    )
    assert first["current_symbol"] == 37
    assert first["predecessor_symbol"] is None
    assert second["current_symbol"] == 134
    assert second["predecessor_symbol"] == 37
    assert second["current_score"] == 3.0
    assert second["predecessor_score"] == 2.0
    assert first["clamp_count"] == second["clamp_count"] == 0


def test_adopted_runtime_rejects_out_of_range_symbols() -> None:
    with pytest.raises(ValueError, match=r"\[0, 260\)"):
        recall_sequence((260,))
