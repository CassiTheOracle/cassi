"""Compare a paper session's live-bar signals with historical replay."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from cassi_market_contracts import digest_value
from cassi_trading_foundry import MarketBar, ReplayConfig, StrategyProgram, run_backtest


PAPER_REPLAY_SCHEMA = "cassi.paper-replay-parity.v1"


def compare_paper_to_replay(
    bars: Sequence[MarketBar],
    receipts: Mapping[str, Mapping[str, Any]],
    program: StrategyProgram,
    *,
    venue: str = "coinbase-public-paper",
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    initial_equity: float = 10_000.0,
    timeframe_hours: float = 1.0,
) -> dict[str, Any]:
    owned = tuple(bars)
    if len(owned) < 2:
        raise ValueError("parity comparison needs at least two bars")
    replay = run_backtest(
        owned,
        program,
        ReplayConfig(
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            initial_equity=initial_equity,
            timeframe_hours=timeframe_hours,
        ),
    )
    mismatches: list[dict[str, Any]] = []
    matched = 0
    compared = 0
    for row in replay.decisions:
        bar = next(item for item in owned if item.timestamp == row["timestamp"])
        event_id = bar.as_event(source_id=f"paper:{venue}", source_revision="closed-bar-v1").event_id
        paper = receipts.get(event_id)
        if paper is None:
            mismatches.append({"timestamp": row["timestamp"], "reason": "missing-paper-receipt"})
            continue
        compared += 1
        paper_signal = int(paper["signal"]["direction"])
        replay_signal = int(row["signal"])
        if paper_signal == replay_signal:
            matched += 1
        else:
            mismatches.append(
                {
                    "timestamp": row["timestamp"],
                    "reason": "signal-mismatch",
                    "paper_signal": paper_signal,
                    "replay_signal": replay_signal,
                    "paper_policy_target": paper["policy_decision"]["target_exposures"].get(bar.symbol),
                    "replay_position_after": row["position_after"],
                }
            )
    ordered_paper = []
    for bar in owned:
        event_id = bar.as_event(source_id=f"paper:{venue}", source_revision="closed-bar-v1").event_id
        if event_id in receipts:
            ordered_paper.append(receipts[event_id])
    fills = [receipt["fill"] for receipt in ordered_paper if receipt.get("fill") is not None]
    paper_final_equity = (
        float(ordered_paper[-1]["account"]["equity"])
        if ordered_paper
        else float(initial_equity)
    )
    fill_comparison = {
        "paper_fill_count": len(fills),
        "replay_trade_count": int(round(float(replay.metrics["trade_count"]))),
        "fill_count_matches": len(fills) == int(round(float(replay.metrics["trade_count"]))),
        "paper_fees_paid": sum(float(fill["fee"]) for fill in fills),
        "replay_cost_paid": float(replay.metrics["cost_paid"]) * float(initial_equity),
        "paper_final_equity": paper_final_equity,
        "replay_final_equity": float(replay.metrics["final_equity"]),
        "equity_delta": paper_final_equity - float(replay.metrics["final_equity"]),
    }
    body: dict[str, Any] = {
        "schema": PAPER_REPLAY_SCHEMA,
        "program": program.document(),
        "bar_count": len(owned),
        "compared_decisions": compared,
        "matched_decisions": matched,
        "signal_parity": matched == compared == len(replay.decisions),
        "mismatches": mismatches,
        "replay_metrics": dict(replay.metrics),
        "paper_receipt_count": len(receipts),
        "fill_comparison": fill_comparison,
        "controls": {
            "replay_has_no_future_bar": True,
            "comparison_uses_event_ids": True,
            "paper_policy_mode": "shadow",
            "paper_external_effect": "none",
        },
    }
    body["content_sha256"] = digest_value(body)
    return body


__all__ = ["PAPER_REPLAY_SCHEMA", "compare_paper_to_replay"]
