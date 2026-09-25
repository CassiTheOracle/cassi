"""Isolate field phase response to lesson identity and ordering."""

from __future__ import annotations

from itertools import product
from typing import Any, Sequence
from cassi_market_contracts import digest_value
from cassi_trading_foundry import RefinementField
from cassi_raw_event_field import CapacityError


OUTCOME_ORDER_SCHEMA = "cassi.native-promote-outcome-order.v1"


def run_outcome_order_sweep(
    *,
    orders: Sequence[Sequence[str]] | None = None,
    signature: str = "edge",
    program_id: str = "synthesized-transfer-program",
    repeats: int = 1,
) -> dict[str, Any]:
    if isinstance(repeats, bool) or not isinstance(repeats, int) or not 1 <= repeats <= 4:
        raise ValueError("repeats must be an integer in [1, 4]")
    selected = tuple(tuple(order) for order in (orders or tuple(product(("promote", "reject"), repeat=4))) )
    if not selected:
        raise ValueError("orders cannot be empty")
    allowed = {"promote", "reject", "uncertain"}
    if any(len(order) != 4 or any(outcome not in allowed for outcome in order) for order in selected):
        raise ValueError("each order must contain exactly four supported outcomes")
    results: list[dict[str, Any]] = []
    for order in selected:
        field = RefinementField()
        trace: list[dict[str, Any]] = []
        status = "measured"
        error: str | None = None
        try:
            for index, outcome in enumerate(order):
                before = field.fingerprint()
                prediction = field.predict_program(signature, program_id)
                field.learn_program(signature, program_id, outcome, repeats=repeats)
                vector = field.state_vector()
                trace.append(
                    {
                        "lesson_index": index,
                        "outcome_written": outcome,
                        "pre_update_readout": prediction,
                        "field_before_sha256": before,
                        "field_after_sha256": field.fingerprint(),
                        "field_l2": sum(value * value for value in vector) ** 0.5,
                        "field_state_vector": list(vector),
                    }
                )
            final_readout = field.predict_program(signature, program_id)
            final_sha256 = field.fingerprint()
        except CapacityError as exc:
            status = "capacity_rejected"
            error = str(exc)
            final_readout = None
            final_sha256 = field.fingerprint()
        result: dict[str, Any] = {
            "order": list(order),
            "repeats": repeats,
            "status": status,
            "trace": trace,
            "final_readout": final_readout,
            "final_field_sha256": final_sha256,
        }
        if error is not None:
            result["error"] = error
        results.append(result)
    body: dict[str, Any] = {
        "schema": OUTCOME_ORDER_SCHEMA,
        "signature": signature,
        "program_id": program_id,
        "repeats": repeats,
        "orders": [list(order) for order in selected],
        "results": results,
        "controls": {
            "lesson_count": 4,
            "outcome_alphabet": sorted(allowed),
            "capacity_failures_are_reported": True,
        },
    }
    body["content_sha256"] = digest_value(body)
    return body


__all__ = ["OUTCOME_ORDER_SCHEMA", "run_outcome_order_sweep"]
