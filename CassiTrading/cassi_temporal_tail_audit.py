#!/usr/bin/env python3
"""Spend a reserved chronological tail once with frozen promoted and control fields."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_aggressive_residency import (
    AggressiveResidencyConfig,
    _atomic_write,
    _program_from_document,
    _sha256,
    load_fine_context,
    run_aggressive_stream,
)
from cassi_temporal_promotion import (
    TEMPORAL_PROMOTION_SCHEMA,
    TEMPORAL_RUNTIME_SCHEMA,
    _promotion_objective,
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


TAIL_AUDIT_SCHEMA = "cassi.trading-temporal-tail-audit.v1"


def _slim_decisions(stream: Mapping[str, Any], *, context_start: int) -> list[dict[str, Any]]:
    return [
        {
            "local_bar_index": int(row["bar_index"]),
            "global_bar_index": context_start + int(row["bar_index"]),
            "global_next_bar_index": context_start + int(row["next_bar_index"]),
            "available_prefix_count": context_start + int(row["available_prefix_count"]),
            "available_until": row["available_until"],
            "execution_timestamp": row["execution_timestamp"],
            "target_requested": float(row["target_requested"]),
            "position_after": float(row["position_after"]),
            "authority": str(row["authority"]),
            "context_sha256": str(row["context_sha256"]),
            "net_return": float(row["net_return"]),
            "equity": float(row["equity"]),
        }
        for row in stream["decisions"]
    ]


def _arm_document(
    stream: Mapping[str, Any],
    *,
    risk_penalty: float,
    context_start: int,
) -> dict[str, Any]:
    decisions = _slim_decisions(stream, context_start=context_start)
    body = _stream_summary(stream, risk_penalty=risk_penalty)
    body["decisions"] = decisions
    body["decision_sha256"] = digest_value(decisions)
    return body


def _tail_comparison(promoted: Mapping[str, Any], control: Mapping[str, Any]) -> dict[str, Any]:
    promoted_decisions = promoted["decisions"]
    control_decisions = control["decisions"]
    if len(promoted_decisions) != len(control_decisions):
        raise ValueError("tail audit arm decision counts differ")
    changed_targets = 0
    changed_positions = 0
    changed_authority = 0
    for promoted_row, control_row in zip(promoted_decisions, control_decisions):
        if promoted_row["global_bar_index"] != control_row["global_bar_index"]:
            raise ValueError("tail audit arms are not aligned")
        changed_targets += int(
            not math.isclose(
                float(promoted_row["target_requested"]),
                float(control_row["target_requested"]),
                rel_tol=0.0,
                abs_tol=1.0e-15,
            )
        )
        changed_positions += int(
            not math.isclose(
                float(promoted_row["position_after"]),
                float(control_row["position_after"]),
                rel_tol=0.0,
                abs_tol=1.0e-15,
            )
        )
        changed_authority += int(promoted_row["authority"] != control_row["authority"])
    promoted_metrics = promoted["account"]["metrics"]
    control_metrics = control["account"]["metrics"]
    return {
        "decision_count": len(promoted_decisions),
        "changed_targets": changed_targets,
        "changed_positions": changed_positions,
        "changed_authority": changed_authority,
        "promoted_minus_control_net_return": float(promoted_metrics["net_return"])
        - float(control_metrics["net_return"]),
        "promoted_minus_control_objective": float(promoted["promotion_objective"])
        - float(control["promotion_objective"]),
        "promoted_minus_control_max_drawdown": float(promoted_metrics["max_drawdown"])
        - float(control_metrics["max_drawdown"]),
    }


def run_temporal_tail_audit(
    bars: Sequence[MarketBar],
    *,
    promoted_checkpoint: bytes,
    starting_checkpoint: bytes,
    program: StrategyProgram,
    residency_config: AggressiveResidencyConfig,
    runtime_state: Mapping[str, Any],
    promotion_receipt: Mapping[str, Any],
    fine_context: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, Any]:
    owned = tuple(bars)
    if promotion_receipt.get("schema") != TEMPORAL_PROMOTION_SCHEMA:
        raise ValueError("tail audit source promotion receipt is invalid")
    if runtime_state.get("schema") != TEMPORAL_RUNTIME_SCHEMA:
        raise ValueError("tail audit source runtime state is invalid")
    if not content_digest_matches(promotion_receipt) or not content_digest_matches(runtime_state):
        raise ValueError("tail audit source content digest mismatch")
    if runtime_state["receipt_content_sha256"] != promotion_receipt["content_sha256"]:
        raise ValueError("tail audit runtime does not link to its promotion receipt")
    if digest_value([bar.as_dict() for bar in owned]) != promotion_receipt["data"]["data_sha256"]:
        raise ValueError("tail audit history differs from the promotion campaign")
    if _sha256(promoted_checkpoint) != runtime_state["field_checkpoint_sha256"]:
        raise ValueError("tail audit promoted checkpoint digest mismatch")
    if _sha256(starting_checkpoint) != promotion_receipt["initial_field"]["checkpoint_sha256"]:
        raise ValueError("tail audit starting checkpoint digest mismatch")

    tail_start = int(runtime_state["next_bar_index"])
    context_start = tail_start - (residency_config.warmup_bars - 1)
    if context_start < 0 or tail_start >= len(owned) - 1:
        raise ValueError("reserved tail is too short or lacks a warmup prefix")
    if owned[tail_start - 1].timestamp != runtime_state["observed_until"]:
        raise ValueError("tail audit runtime boundary does not match history")
    evaluation = owned[context_start:]
    if len(evaluation) < residency_config.warmup_bars + residency_config.outcome_horizon + 2:
        raise ValueError("reserved tail cannot support the declared causal horizon")

    promoted_before = bytes(promoted_checkpoint)
    starting_before = bytes(starting_checkpoint)
    promoted_field = RefinementField.restore(promoted_checkpoint)
    starting_field = RefinementField.restore(starting_checkpoint)
    _, promoted_stream, _ = run_aggressive_stream(
        evaluation,
        field=promoted_field,
        program=program,
        config=residency_config,
        fine_context=dict(fine_context or {}),
        learning_enabled=False,
        initial_account=runtime_state["account"],
    )
    _, control_stream, _ = run_aggressive_stream(
        evaluation,
        field=starting_field,
        program=program,
        config=residency_config,
        fine_context=dict(fine_context or {}),
        learning_enabled=False,
        initial_account=runtime_state["account"],
    )
    if promoted_field.checkpoint_bytes() != promoted_before:
        raise RuntimeError("reserved tail audit mutated the promoted checkpoint")
    if starting_field.checkpoint_bytes() != starting_before:
        raise RuntimeError("reserved tail audit mutated the starting checkpoint")

    promoted = _arm_document(
        promoted_stream,
        risk_penalty=residency_config.risk_penalty,
        context_start=context_start,
    )
    control = _arm_document(
        control_stream,
        risk_penalty=residency_config.risk_penalty,
        context_start=context_start,
    )
    comparison = _tail_comparison(promoted, control)
    promotion_config = promotion_receipt["protocol"]["promotion_config"]
    objective_margin = float(promotion_config["minimum_objective_delta"])
    drawdown_margin = float(promotion_config["maximum_drawdown_increase"])
    checks = {
        "objective_margin": comparison["promoted_minus_control_objective"]
        >= objective_margin,
        "drawdown_margin": comparison["promoted_minus_control_max_drawdown"]
        <= drawdown_margin,
        "field_authority_fired": int(promoted["authority"]["field_supported_steps"]) > 0,
        "checkpoint_immutable": True,
    }
    verdict = "SUPPORTS" if all(checks.values()) else "DOES_NOT_SUPPORT"
    body: dict[str, Any] = {
        "schema": TAIL_AUDIT_SCHEMA,
        "status": "PASS",
        "verdict": verdict,
        "checks": checks,
        "protocol": {
            "one_shot_reserved_tail": True,
            "learning_enabled": False,
            "same_program": True,
            "same_initial_account": True,
            "same_tail_data": True,
            "objective_margin": objective_margin,
            "maximum_drawdown_increase": drawdown_margin,
            "residency_config": residency_config.as_dict(),
        },
        "source": {
            "promotion_receipt_content_sha256": promotion_receipt["content_sha256"],
            "runtime_content_sha256": runtime_state["content_sha256"],
            "promoted_checkpoint_sha256": _sha256(promoted_checkpoint),
            "starting_checkpoint_sha256": _sha256(starting_checkpoint),
            "full_history_data_sha256": promotion_receipt["data"]["data_sha256"],
        },
        "tail": {
            "context_start_index": context_start,
            "start_index": tail_start,
            "end_index_exclusive": len(owned),
            "reserved_bars": len(owned) - tail_start,
            "realized_steps": len(owned) - tail_start - 1,
            "first_timestamp": owned[tail_start].timestamp,
            "last_timestamp": owned[-1].timestamp,
            "data_sha256": digest_value([bar.as_dict() for bar in owned[tail_start:]]),
        },
        "program": program.document(),
        "initial_account": dict(runtime_state["account"]),
        "arms": {
            "promoted_field": promoted,
            "starting_field_control": control,
        },
        "comparison": comparison,
    }
    body["content_sha256"] = digest_value(body)
    return body


def verify_temporal_tail_audit(
    receipt: Mapping[str, Any],
    *,
    promoted_checkpoint: bytes,
    starting_checkpoint: bytes,
) -> dict[str, Any]:
    if receipt.get("schema") != TAIL_AUDIT_SCHEMA or receipt.get("status") != "PASS":
        raise ValueError("temporal tail audit receipt is invalid")
    if not content_digest_matches(receipt):
        raise ValueError("temporal tail audit content digest mismatch")
    protocol = receipt["protocol"]
    if not protocol["one_shot_reserved_tail"] or protocol["learning_enabled"]:
        raise ValueError("temporal tail audit protocol is invalid")
    if not protocol["same_program"] or not protocol["same_initial_account"] or not protocol["same_tail_data"]:
        raise ValueError("temporal tail audit matching contract is invalid")
    if _sha256(promoted_checkpoint) != receipt["source"]["promoted_checkpoint_sha256"]:
        raise ValueError("temporal tail promoted checkpoint mismatch")
    if _sha256(starting_checkpoint) != receipt["source"]["starting_checkpoint_sha256"]:
        raise ValueError("temporal tail starting checkpoint mismatch")
    promoted_field = RefinementField.restore(promoted_checkpoint)
    starting_field = RefinementField.restore(starting_checkpoint)
    arms = receipt["arms"]
    if promoted_field.fingerprint() != arms["promoted_field"]["field"]["before_sha256"]:
        raise ValueError("temporal tail promoted field fingerprint mismatch")
    if starting_field.fingerprint() != arms["starting_field_control"]["field"]["before_sha256"]:
        raise ValueError("temporal tail starting field fingerprint mismatch")
    for name, arm in arms.items():
        if arm["field"]["changed"]:
            raise ValueError(f"{name} mutated during reserved-tail inference")
        if digest_value(arm["decisions"]) != arm["decision_sha256"]:
            raise ValueError(f"{name} decision digest mismatch")
        expected_objective = _promotion_objective(
            arm["account"]["metrics"],
            risk_penalty=float(protocol["residency_config"]["risk_penalty"]),
        )
        if not math.isclose(expected_objective, arm["promotion_objective"], rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"{name} objective mismatch")
        for decision in arm["decisions"]:
            if decision["global_next_bar_index"] != decision["global_bar_index"] + 1:
                raise ValueError(f"{name} contains a noncausal decision")
            if decision["available_prefix_count"] != decision["global_bar_index"] + 1:
                raise ValueError(f"{name} prefix count mismatch")
    comparison = _tail_comparison(arms["promoted_field"], arms["starting_field_control"])
    if comparison != receipt["comparison"]:
        raise ValueError("temporal tail comparison mismatch")
    checks = {
        "objective_margin": comparison["promoted_minus_control_objective"]
        >= float(protocol["objective_margin"]),
        "drawdown_margin": comparison["promoted_minus_control_max_drawdown"]
        <= float(protocol["maximum_drawdown_increase"]),
        "field_authority_fired": int(
            arms["promoted_field"]["authority"]["field_supported_steps"]
        )
        > 0,
        "checkpoint_immutable": True,
    }
    if checks != receipt["checks"]:
        raise ValueError("temporal tail checks are inconsistent")
    expected_verdict = "SUPPORTS" if all(checks.values()) else "DOES_NOT_SUPPORT"
    if receipt["verdict"] != expected_verdict:
        raise ValueError("temporal tail verdict is inconsistent")
    return {
        "status": "PASS",
        "verdict": expected_verdict,
        "content_sha256": receipt["content_sha256"],
        "reserved_bars": receipt["tail"]["reserved_bars"],
        "decisions": comparison["decision_count"],
        "changed_targets": comparison["changed_targets"],
        "promoted_net_return": arms["promoted_field"]["account"]["metrics"]["net_return"],
        "control_net_return": arms["starting_field_control"]["account"]["metrics"]["net_return"],
        "objective_delta": comparison["promoted_minus_control_objective"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--fine-history", type=Path)
    parser.add_argument("--promotion-receipt", type=Path, required=True)
    parser.add_argument("--runtime-state", type=Path, required=True)
    parser.add_argument("--promoted-checkpoint", type=Path, required=True)
    parser.add_argument("--starting-checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite one-shot tail receipt: {args.out}")
    promotion_receipt = json.loads(args.promotion_receipt.read_text(encoding="utf-8"))
    runtime_state = json.loads(args.runtime_state.read_text(encoding="utf-8"))
    config = AggressiveResidencyConfig(
        **promotion_receipt["protocol"]["residency_config"]
    )
    program = _program_from_document(runtime_state["program"])
    bars = load_bars_csv(args.history, symbol="BTC-USD")
    receipt = run_temporal_tail_audit(
        bars,
        promoted_checkpoint=args.promoted_checkpoint.read_bytes(),
        starting_checkpoint=args.starting_checkpoint.read_bytes(),
        program=program,
        residency_config=config,
        runtime_state=runtime_state,
        promotion_receipt=promotion_receipt,
        fine_context=load_fine_context(args.fine_history),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(
        args.out,
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    verification = verify_temporal_tail_audit(
        json.loads(args.out.read_text(encoding="utf-8")),
        promoted_checkpoint=args.promoted_checkpoint.read_bytes(),
        starting_checkpoint=args.starting_checkpoint.read_bytes(),
    )
    print(json.dumps({**verification, "receipt": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
