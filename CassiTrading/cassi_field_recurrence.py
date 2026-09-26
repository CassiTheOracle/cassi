#!/usr/bin/env python3
"""Accumulate field-owned recurrence evidence before one later frozen authority read."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_aggressive_residency import (
    AggressiveResidencyConfig,
    _atomic_write,
    _load_program_receipt,
    load_fine_context,
    run_aggressive_curriculum,
    run_aggressive_stream,
)
from cassi_temporal_promotion import (
    TemporalPromotionConfig,
    _evaluation_slice,
    _stream_summary,
)
from cassi_trading_foundry import (
    MarketBar,
    RefinementField,
    StrategyProgram,
    content_digest_matches,
    digest_value,
    load_bars_csv,
)


FIELD_RECURRENCE_SCHEMA = "cassi.trading-field-recurrence.v1"


@dataclass(frozen=True, slots=True)
class RecurrenceWindow:
    name: str
    start_timestamp: str
    bars: int = 4_320

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_timestamp": self.start_timestamp,
            "bars": self.bars,
        }


RECURRENCE_WINDOWS = (
    RecurrenceWindow("post-crash-recovery", "2020-04-01T00:00:00Z"),
    RecurrenceWindow("first-bull-continuation", "2020-10-01T00:00:00Z"),
    RecurrenceWindow("pre-etf-recovery", "2023-04-01T00:00:00Z"),
)
HELD_OUT_WINDOW = RecurrenceWindow("post-etf-held-out", "2024-04-01T00:00:00Z", 2_160)


def _sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _window_slice(
    bars: Sequence[MarketBar], window: RecurrenceWindow
) -> tuple[tuple[MarketBar, ...], int]:
    start = next(
        (index for index, bar in enumerate(bars) if bar.timestamp == window.start_timestamp),
        None,
    )
    if start is None:
        raise ValueError(f"recurrence start absent from history: {window.start_timestamp}")
    end = start + window.bars
    if end > len(bars):
        raise ValueError(f"recurrence window exceeds history: {window.name}")
    return tuple(bars[start:end]), start


def _window_source(window: Sequence[MarketBar], *, start_index: int) -> dict[str, Any]:
    return {
        "start_index": start_index,
        "end_index_exclusive": start_index + len(window),
        "bars": len(window),
        "first_timestamp": window[0].timestamp,
        "last_timestamp": window[-1].timestamp,
        "data_sha256": digest_value([bar.as_dict() for bar in window]),
    }


def _authority_decision(
    candidate: Mapping[str, Any],
    incumbent: Mapping[str, Any],
    *,
    config: TemporalPromotionConfig,
) -> dict[str, Any]:
    candidate_metrics = candidate["account"]["metrics"]
    incumbent_metrics = incumbent["account"]["metrics"]
    objective_delta = float(candidate["promotion_objective"]) - float(
        incumbent["promotion_objective"]
    )
    drawdown_delta = float(candidate_metrics["max_drawdown"]) - float(
        incumbent_metrics["max_drawdown"]
    )
    supported_steps = int(candidate["authority"]["field_supported_steps"])
    promote_steps = int(candidate["authority"]["field_promote_steps"])
    checks = {
        "field_reached_evaluation": supported_steps > 0,
        "field_promoted_evaluation": promote_steps > 0,
        "positive_growth": float(candidate_metrics["net_return"]) > 0.0,
        "objective_margin": objective_delta >= config.minimum_objective_delta,
        "drawdown_margin": drawdown_delta <= config.maximum_drawdown_increase,
        "minimum_trades": int(candidate_metrics["trade_count"]) >= config.minimum_trades,
    }
    return {
        "supports_authority": all(checks.values()),
        "checks": checks,
        "objective_delta": objective_delta,
        "drawdown_delta": drawdown_delta,
        "net_return_delta": float(candidate_metrics["net_return"])
        - float(incumbent_metrics["net_return"]),
    }


def run_field_recurrence_program(
    bars: Sequence[MarketBar],
    *,
    initial_checkpoint: bytes,
    program: StrategyProgram,
    recurrence_windows: Sequence[RecurrenceWindow] = RECURRENCE_WINDOWS,
    held_out: RecurrenceWindow = HELD_OUT_WINDOW,
    residency_config: AggressiveResidencyConfig | None = None,
    promotion_config: TemporalPromotionConfig | None = None,
    fine_context: Mapping[str, Mapping[str, float]] | None = None,
) -> tuple[dict[str, Any], bytes, tuple[dict[str, Any], ...]]:
    owned = tuple(bars)
    residency = residency_config or AggressiveResidencyConfig()
    promotion = promotion_config or TemporalPromotionConfig()
    fine = dict(fine_context or {})
    if not recurrence_windows:
        raise ValueError("recurrence program requires at least one development window")

    checkpoint = bytes(initial_checkpoint)
    stages: list[dict[str, Any]] = []
    previous_end = -1
    for window_spec in recurrence_windows:
        window, start = _window_slice(owned, window_spec)
        if start <= previous_end:
            raise ValueError("recurrence windows must be strictly ordered and disjoint")
        previous_end = start + len(window) - 1
        before_sha256 = _sha256(checkpoint)
        stage_receipt, checkpoint, _ = run_aggressive_curriculum(
            window,
            initial_checkpoint=checkpoint,
            program=program,
            config=residency,
            fine_context=fine,
        )
        if stage_receipt["initial_field"]["checkpoint_sha256"] != before_sha256:
            raise RuntimeError("recurrence field lineage did not begin at preceding checkpoint")
        stages.append(
            {
                "window": window_spec.as_dict(),
                "source": _window_source(window, start_index=start),
                "field_before_sha256": before_sha256,
                "field_after_sha256": _sha256(checkpoint),
                "curriculum_content_sha256": stage_receipt["content_sha256"],
                "curriculum_status": stage_receipt["status"],
            }
        )

    held_out_bars, held_out_start = _window_slice(owned, held_out)
    if held_out_start <= previous_end:
        raise ValueError("held-out window must begin after every recurrence window")
    evaluation, context_start = _evaluation_slice(
        owned,
        start=held_out_start,
        end=held_out_start + len(held_out_bars),
        warmup_bars=residency.warmup_bars,
    )
    initial_field = RefinementField.restore(initial_checkpoint)
    candidate_field = RefinementField.restore(checkpoint)
    initial_before = initial_field.fingerprint()
    candidate_before = candidate_field.fingerprint()
    _, incumbent_stream, _ = run_aggressive_stream(
        evaluation,
        field=initial_field,
        program=program,
        config=residency,
        fine_context=fine,
        learning_enabled=False,
    )
    _, candidate_stream, _ = run_aggressive_stream(
        evaluation,
        field=candidate_field,
        program=program,
        config=residency,
        fine_context=fine,
        learning_enabled=False,
    )
    if initial_field.fingerprint() != initial_before or candidate_field.fingerprint() != candidate_before:
        raise RuntimeError("held-out inference mutated a recurrence field")
    incumbent = _stream_summary(incumbent_stream, risk_penalty=residency.risk_penalty)
    candidate = _stream_summary(candidate_stream, risk_penalty=residency.risk_penalty)
    decision = _authority_decision(candidate, incumbent, config=promotion)
    body: dict[str, Any] = {
        "schema": FIELD_RECURRENCE_SCHEMA,
        "status": "PASS",
        "protocol": {
            "field_is_sole_adaptive_state": True,
            "recurrence_windows_are_strictly_ordered_and_disjoint": True,
            "field_checkpoint_chain_is_contiguous": True,
            "held_out_evaluation_is_later_and_learning_disabled": True,
            "positive_authority_requires_field_promote_and_positive_held_out_delta": True,
            "residency_config": residency.as_dict(),
            "promotion_config": promotion.as_dict(),
        },
        "source": {
            "history_sha256": digest_value([bar.as_dict() for bar in owned]),
            "fine_context_sha256": digest_value(fine),
            "initial_checkpoint_sha256": _sha256(initial_checkpoint),
            "program_sha256": digest_value(program.document()),
        },
        "stages": stages,
        "held_out": {
            "window": held_out.as_dict(),
            "source": _window_source(held_out_bars, start_index=held_out_start),
            "context_start_index": context_start,
            "learning_enabled": False,
            "incumbent": incumbent,
            "candidate": candidate,
            "decision": decision,
        },
        "final_checkpoint_sha256": _sha256(checkpoint),
        "verdict": (
            "SUPPORTS_RECURRENCE_AUTHORITY"
            if decision["supports_authority"]
            else "DOES_NOT_SUPPORT_RECURRENCE_AUTHORITY"
        ),
    }
    body["content_sha256"] = digest_value(body)
    return body, checkpoint, tuple(stages)


def verify_field_recurrence_program(
    receipt: Mapping[str, Any],
    *,
    initial_checkpoint: bytes,
    final_checkpoint: bytes,
) -> dict[str, Any]:
    if receipt.get("schema") != FIELD_RECURRENCE_SCHEMA or receipt.get("status") != "PASS":
        raise ValueError("not a successful field recurrence receipt")
    if not content_digest_matches(receipt):
        raise ValueError("field recurrence content digest mismatch")
    if receipt["source"]["initial_checkpoint_sha256"] != _sha256(initial_checkpoint):
        raise ValueError("initial recurrence checkpoint mismatch")
    if receipt["final_checkpoint_sha256"] != _sha256(final_checkpoint):
        raise ValueError("final recurrence checkpoint mismatch")
    stages = receipt["stages"]
    if not stages:
        raise ValueError("recurrence receipt has no stages")
    previous = _sha256(initial_checkpoint)
    prior_end = -1
    for stage in stages:
        if stage["field_before_sha256"] != previous:
            raise ValueError("recurrence field lineage is discontinuous")
        source = stage["source"]
        if int(source["start_index"]) <= prior_end:
            raise ValueError("recurrence windows are not disjoint")
        prior_end = int(source["end_index_exclusive"]) - 1
        previous = stage["field_after_sha256"]
    if previous != _sha256(final_checkpoint):
        raise ValueError("recurrence final lineage mismatch")
    held_out = receipt["held_out"]
    if int(held_out["source"]["start_index"]) <= prior_end:
        raise ValueError("held-out window overlaps recurrence development")
    if held_out["learning_enabled"] is not False:
        raise ValueError("held-out recurrence evaluation enabled learning")
    return {
        "status": "PASS",
        "receipt": "field recurrence",
        "stage_count": len(stages),
        "verdict": receipt["verdict"],
        "content_sha256": receipt["content_sha256"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--fine-history", required=True, type=Path)
    parser.add_argument("--initial-checkpoint", required=True, type=Path)
    parser.add_argument("--program-receipt", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.out.exists():
        raise FileExistsError(f"refusing to overwrite recurrence output: {args.out}")
    receipt, checkpoint, stages = run_field_recurrence_program(
        load_bars_csv(args.history, symbol="BTC-USD"),
        initial_checkpoint=args.initial_checkpoint.read_bytes(),
        program=_load_program_receipt(args.program_receipt),
        fine_context=load_fine_context(args.fine_history),
    )
    args.out.mkdir(parents=True, exist_ok=False)
    _atomic_write(
        args.out / "field_recurrence_receipt.json",
        json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    _atomic_write(args.out / "final_refinement_field.chk", checkpoint)
    _atomic_write(
        args.out / "stage_manifest.json",
        json.dumps(stages, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    print(json.dumps(verify_field_recurrence_program(
        receipt,
        initial_checkpoint=args.initial_checkpoint.read_bytes(),
        final_checkpoint=checkpoint,
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
