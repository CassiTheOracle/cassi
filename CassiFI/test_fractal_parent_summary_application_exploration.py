from __future__ import annotations

import json
from pathlib import Path

import pytest

import cassi_resonant_field as field
import run_fractal_parent_summary_application_exploration as runner


RECEIPT = Path(__file__).resolve().parent / runner.DEFAULT_OUTPUT


def _persisted_receipt() -> dict:
    assert RECEIPT.is_file(), (
        f"Missing receipt {RECEIPT}; run `python run_fractal_parent_summary_application_exploration.py "
        "--output _diag/fractal-parent-summary-application/exploration.json` from CassiFI."
    )
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert runner.verify_receipt(receipt)["content_digest_matches"]
    return receipt


def test_frozen_parent_application_receipt_is_self_consistent() -> None:
    receipt = runner.build_receipt()
    persisted = _persisted_receipt()
    assert receipt["verdict"] == "PASS_FIELD_OWNED_FROZEN_PARENT_APPLICATION"
    assert runner.verify_receipt(receipt)["content_digest_matches"]
    assert persisted["verdict"] == "PASS_FIELD_OWNED_FROZEN_PARENT_APPLICATION"
    assert persisted["content_digest"] == receipt["content_digest"]
    assert all(row["holds"] for row in receipt["comparisons"])
    assert receipt["controls"]["stale_parent"]["can_fail"]
    assert receipt["controls"]["locked_recompute"]["can_fail"]
    tampered = receipt["controls"]["tampered_provenance"]
    assert tampered["can_fail"]
    assert tampered["error_type"] == field.ResonantNumericalError.__name__
    assert tampered["error"] == "frozen parent identity digest mismatch"
    assert tampered["error_type_matches"]
    assert tampered["error_message_matches"]
    assert receipt["controls"]["owner"]["freeze"]["frozen_parent_receipt"]["accepted"]

    on_signal = receipt["arms"]["parent-on"]["application"]["effective_flow_signal"]
    off_signal = receipt["arms"]["parent-off"]["application"]["effective_flow_signal"]
    assert on_signal != off_signal
    assert receipt["arms"]["parent-on"]["sibling_delta_norm"] == 0.0
    assert receipt["arms"]["parent-off"]["sibling_delta_norm"] == 0.0


def test_frozen_parent_blocks_l_register_rewrite() -> None:
    origin = field.initial_workspace(field.ResonantProfile())
    captured, _ = field.write_parent_registers(
        origin, paths=("L", "LL"), ancestry_pairs=(("L", "LL"),)
    )
    frozen, _ = field.freeze_parent(captured)
    with pytest.raises(field.ResonantNumericalError, match="locked"):
        field.write_parent_registers(frozen, paths=("LR",))
    with pytest.raises(field.ResonantNumericalError, match="locked"):
        field.write_parent_summary(frozen)
