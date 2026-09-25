"""Verify market lesson order against an isolated field replay."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from cassi_market_contracts import digest_value
from cassi_trading_foundry import MarketBar, RefinementField
from cassi_persistence_sweep import run_promote_persistence_sweep


SOURCE_ORDER_MATCH_SCHEMA = "cassi.native-source-order-match.v1"


def run_source_order_match(
    bars_by_instrument: Mapping[str, Sequence[MarketBar]],
    *,
    source_instrument: str,
    target_instruments: Sequence[str],
    source_window_counts: Sequence[int] = (1, 2, 3, 4, 5, 6, 7, 8),
    target_starts: Sequence[int] = (32, 64, 96),
    step_bars: int = 32,
) -> dict[str, Any]:
    persistence = run_promote_persistence_sweep(
        bars_by_instrument,
        source_instrument=source_instrument,
        target_instruments=target_instruments,
        source_window_counts=source_window_counts,
        target_starts=target_starts,
        step_bars=step_bars,
    )
    matches: list[dict[str, Any]] = []
    for result in persistence["results"]:
        field = RefinementField()
        for outcome in result["source_lesson_outcomes"]:
            field.learn_program("edge", "synthesized-transfer-program", outcome, repeats=1)
        direct_readout = field.predict_program("edge", "synthesized-transfer-program")
        source_trace = result["source_state_trace"]
        matches.append(
            {
                "source_windows": result["source_windows"],
                "source_lesson_outcomes": result["source_lesson_outcomes"],
                "source_field_sha256": result["source_field_sha256"],
                "replayed_field_sha256": field.fingerprint(),
                "exact_field_match": field.fingerprint() == result["source_field_sha256"],
                "prospective_readout": result["prospective_readout"],
                "prospective_strict_promote_authority": result["prospective_strict_promote_authority"],
                "prospective_matches_replay": result["prospective_readout"] == direct_readout,
                "prospective_matches_native": (
                    result["prospective_strict_promote_authority"]
                    == (result["native_authority_rate"] == 1.0)
                ),
                "direct_readout": direct_readout,
                "native_authority_rate": result["native_authority_rate"],
                "source_trace_final_sha256": source_trace[-1]["field_after_sha256"],
            }
        )
    body: dict[str, Any] = {
        "schema": SOURCE_ORDER_MATCH_SCHEMA,
        "source_instrument": source_instrument,
        "target_instruments": list(sorted(target_instruments)),
        "target_starts": list(target_starts),
        "matches": matches,
        "controls": {
            "replay_signature": "edge",
            "replay_program_id": "synthesized-transfer-program",
            "replay_repeats": 1,
            "exact_field_match_required": True,
            "prospective_readout_before_target_arms": True,
        },
    }
    body["content_sha256"] = digest_value(body)
    return body


__all__ = ["SOURCE_ORDER_MATCH_SCHEMA", "run_source_order_match"]
