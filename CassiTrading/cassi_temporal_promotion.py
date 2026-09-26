#!/usr/bin/env python3
"""Chronologically promote one regime-aware Cassi trading field on untouched windows."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_aggressive_residency import (
    AggressiveResidencyConfig,
    _atomic_write,
    _load_program_receipt,
    _sha256,
    load_fine_context,
    run_aggressive_stream,
)
from cassi_trading_foundry import (
    MarketBar,
    RefinementField,
    StrategyProgram,
    content_digest_matches,
    digest_value,
    load_bars_csv,
)


TEMPORAL_PROMOTION_SCHEMA = "cassi.trading-temporal-promotion.v1"
TEMPORAL_RUNTIME_SCHEMA = "cassi.trading-temporal-runtime.v1"


@dataclass(frozen=True, slots=True)
class TemporalPromotionConfig:
    initial_development_bars: int = 8_760
    evaluation_bars: int = 2_160
    minimum_objective_delta: float = 0.005
    maximum_drawdown_increase: float = 0.02
    minimum_trades: int = 8

    def __post_init__(self) -> None:
        if self.initial_development_bars < 1 or self.evaluation_bars < 1:
            raise ValueError("promotion windows must contain positive bar counts")
        if self.minimum_trades < 1:
            raise ValueError("minimum trades must be positive")
        for value in (self.minimum_objective_delta, self.maximum_drawdown_increase):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError("promotion margins must be finite and nonnegative")

    def as_dict(self) -> dict[str, Any]:
        return {
            "initial_development_bars": self.initial_development_bars,
            "evaluation_bars": self.evaluation_bars,
            "minimum_objective_delta": self.minimum_objective_delta,
            "maximum_drawdown_increase": self.maximum_drawdown_increase,
            "minimum_trades": self.minimum_trades,
        }


def _promotion_objective(metrics: Mapping[str, Any], *, risk_penalty: float) -> float:
    final_equity = float(metrics["final_equity"])
    if final_equity <= 0.0:
        return -math.inf
    return math.log(final_equity) - risk_penalty * float(metrics["max_drawdown"])


def _lesson_summary(stream: Mapping[str, Any]) -> dict[str, Any]:
    outcomes: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    regrets: list[float] = []
    for row in stream["lessons"]:
        lesson = row["lesson"]
        if lesson["status"] != "PASS":
            continue
        regrets.append(float(lesson["regret"]))
        for admission in lesson["admissions"]:
            outcomes[str(admission["outcome"])] += 1
            roles[str(admission["memory_role"])] += 1
    return {
        "lesson_count": len(stream["lessons"]),
        "outcomes": dict(sorted(outcomes.items())),
        "memory_roles": dict(sorted(roles.items())),
        "mean_regret": sum(regrets) / len(regrets) if regrets else 0.0,
    }


def _stream_summary(stream: Mapping[str, Any], *, risk_penalty: float) -> dict[str, Any]:
    metrics = dict(stream["account"]["metrics"])
    return {
        "field": dict(stream["field"]),
        "account": {
            "initial": dict(stream["account"]["initial"]),
            "final": dict(stream["account"]["final"]),
            "metrics": metrics,
        },
        "authority": dict(stream["authority"]),
        "capacity_event": stream["capacity_event"],
        "promotion_objective": _promotion_objective(metrics, risk_penalty=risk_penalty),
        "lessons": _lesson_summary(stream),
    }


def _evaluation_slice(
    bars: Sequence[MarketBar],
    *,
    start: int,
    end: int,
    warmup_bars: int,
) -> tuple[tuple[MarketBar, ...], int]:
    context_start = start - (warmup_bars - 1)
    if context_start < 0:
        raise ValueError("evaluation window lacks its causal warmup prefix")
    return tuple(bars[context_start:end]), context_start


def _promotion_decision(
    candidate: Mapping[str, Any],
    incumbent: Mapping[str, Any],
    starting_control: Mapping[str, Any],
    *,
    config: TemporalPromotionConfig,
    hard_drawdown: float,
    capacity_available: bool,
) -> dict[str, Any]:
    objective_delta = float(candidate["promotion_objective"]) - float(
        incumbent["promotion_objective"]
    )
    starting_delta = float(candidate["promotion_objective"]) - float(
        starting_control["promotion_objective"]
    )
    drawdown_delta = float(candidate["account"]["metrics"]["max_drawdown"]) - float(
        incumbent["account"]["metrics"]["max_drawdown"]
    )
    checks = {
        "objective_margin": objective_delta >= config.minimum_objective_delta,
        "starting_control_margin": starting_delta >= config.minimum_objective_delta,
        "drawdown_margin": drawdown_delta <= config.maximum_drawdown_increase,
        "hard_drawdown": float(candidate["account"]["metrics"]["max_drawdown"])
        < hard_drawdown,
        "positive_growth": float(candidate["account"]["metrics"]["net_return"]) > 0.0,
        "minimum_trades": int(candidate["account"]["metrics"]["trade_count"])
        >= config.minimum_trades,
        "capacity": capacity_available,
    }
    if all(checks.values()):
        selection = "candidate"
    elif (
        float(starting_control["promotion_objective"])
        - float(incumbent["promotion_objective"])
        >= config.minimum_objective_delta
    ):
        selection = "starting_field"
    else:
        selection = "incumbent"
    return {
        "selection": selection,
        "promote": selection == "candidate",
        "reset_to_starting": selection == "starting_field",
        "checks": checks,
        "objective_delta": objective_delta,
        "starting_control_delta": starting_delta,
        "drawdown_delta": drawdown_delta,
    }


def run_temporal_promotion_campaign(
    bars: Sequence[MarketBar],
    *,
    initial_checkpoint: bytes,
    program: StrategyProgram,
    residency_config: AggressiveResidencyConfig | None = None,
    promotion_config: TemporalPromotionConfig | None = None,
    fine_context: Mapping[str, Mapping[str, float]] | None = None,
) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    owned = tuple(bars)
    residency = residency_config or AggressiveResidencyConfig()
    promotion = promotion_config or TemporalPromotionConfig()
    fine = dict(fine_context or {})
    if promotion.initial_development_bars < (
        residency.warmup_bars + residency.outcome_horizon + 2
    ):
        raise ValueError("initial development window is too short for causal lessons")
    minimum_length = promotion.initial_development_bars + promotion.evaluation_bars
    if len(owned) < minimum_length:
        raise ValueError("history is too short for a development and untouched evaluation cycle")

    initial_field = RefinementField.restore(initial_checkpoint)
    initial_checkpoint_sha256 = _sha256(initial_checkpoint)
    promoted_checkpoint = bytes(initial_checkpoint)
    promoted_field_sha256 = initial_field.fingerprint()
    starting_checkpoint = bytes(initial_checkpoint)
    campaign_account: dict[str, Any] | None = None
    development_account: dict[str, Any] | None = None
    evaluation_start = promotion.initial_development_bars
    cycles: list[dict[str, Any]] = []
    promotion_count = 0
    reset_count = 0

    while evaluation_start + promotion.evaluation_bars <= len(owned):
        cycle_index = len(cycles)
        evaluation_end = evaluation_start + promotion.evaluation_bars
        if cycle_index == 0:
            development_start = 0
        else:
            development_start = evaluation_start - promotion.evaluation_bars - (
                residency.warmup_bars - 1
            )
        development_end = evaluation_start
        development = tuple(owned[development_start:development_end])
        if len(development) < residency.warmup_bars + residency.outcome_horizon + 2:
            raise RuntimeError("development slice is too short for causal lessons")

        incumbent_before_checkpoint = promoted_checkpoint
        incumbent_before_field = RefinementField.restore(incumbent_before_checkpoint)
        candidate_field = RefinementField.restore(incumbent_before_checkpoint)
        candidate_field, training_stream, _ = run_aggressive_stream(
            development,
            field=candidate_field,
            program=program,
            config=residency,
            fine_context=fine,
            learning_enabled=True,
            record_decisions=False,
            initial_account=development_account,
        )
        candidate_checkpoint = candidate_field.checkpoint_bytes()
        candidate_training = _stream_summary(
            training_stream,
            risk_penalty=residency.risk_penalty,
        )

        evaluation, evaluation_context_start = _evaluation_slice(
            owned,
            start=evaluation_start,
            end=evaluation_end,
            warmup_bars=residency.warmup_bars,
        )
        evaluation_account_start = campaign_account
        _, candidate_stream, _ = run_aggressive_stream(
            evaluation,
            field=RefinementField.restore(candidate_checkpoint),
            program=program,
            config=residency,
            fine_context=fine,
            learning_enabled=False,
            record_decisions=False,
            initial_account=evaluation_account_start,
        )
        _, incumbent_stream, _ = run_aggressive_stream(
            evaluation,
            field=RefinementField.restore(incumbent_before_checkpoint),
            program=program,
            config=residency,
            fine_context=fine,
            learning_enabled=False,
            record_decisions=False,
            initial_account=evaluation_account_start,
        )
        _, starting_stream, _ = run_aggressive_stream(
            evaluation,
            field=RefinementField.restore(starting_checkpoint),
            program=program,
            config=residency,
            fine_context=fine,
            learning_enabled=False,
            record_decisions=False,
            initial_account=evaluation_account_start,
        )
        candidate = _stream_summary(candidate_stream, risk_penalty=residency.risk_penalty)
        incumbent = _stream_summary(incumbent_stream, risk_penalty=residency.risk_penalty)
        starting_control = _stream_summary(
            starting_stream,
            risk_penalty=residency.risk_penalty,
        )
        decision = _promotion_decision(
            candidate,
            incumbent,
            starting_control,
            config=promotion,
            hard_drawdown=residency.hard_drawdown,
            capacity_available=training_stream["capacity_event"] is None,
        )

        if decision["selection"] == "candidate":
            promoted_checkpoint = candidate_checkpoint
            promoted_field_sha256 = candidate_field.fingerprint()
            campaign_account = dict(candidate["account"]["final"])
            promotion_count += 1
        elif decision["selection"] == "starting_field":
            promoted_checkpoint = starting_checkpoint
            promoted_field_sha256 = initial_field.fingerprint()
            campaign_account = dict(starting_control["account"]["final"])
            reset_count += 1
        else:
            campaign_account = dict(incumbent["account"]["final"])
        development_account = (
            None if evaluation_account_start is None else dict(evaluation_account_start)
        )

        cycle = {
            "cycle": cycle_index,
            "development": {
                "start_index": development_start,
                "end_index_exclusive": development_end,
                "bars": len(development),
                "first_timestamp": development[0].timestamp,
                "last_timestamp": development[-1].timestamp,
                "data_sha256": digest_value([bar.as_dict() for bar in development]),
            },
            "evaluation": {
                "context_start_index": evaluation_context_start,
                "start_index": evaluation_start,
                "end_index_exclusive": evaluation_end,
                "bars": promotion.evaluation_bars,
                "first_timestamp": owned[evaluation_start].timestamp,
                "last_timestamp": owned[evaluation_end - 1].timestamp,
                "data_sha256": digest_value(
                    [bar.as_dict() for bar in owned[evaluation_start:evaluation_end]]
                ),
            },
            "incumbent_before": {
                "checkpoint_sha256": _sha256(incumbent_before_checkpoint),
                "field_sha256": incumbent_before_field.fingerprint(),
            },
            "candidate_training": candidate_training,
            "candidate": candidate,
            "incumbent": incumbent,
            "starting_field_control": starting_control,
            "decision": decision,
            "promoted_after": {
                "checkpoint_sha256": _sha256(promoted_checkpoint),
                "field_sha256": promoted_field_sha256,
            },
        }
        cycle["content_sha256"] = digest_value(cycle)
        cycles.append(cycle)
        evaluation_start = evaluation_end

    final_field = RefinementField.restore(promoted_checkpoint)
    receipt: dict[str, Any] = {
        "schema": TEMPORAL_PROMOTION_SCHEMA,
        "status": "PASS",
        "protocol": {
            "field_is_sole_adaptive_state": True,
            "candidate_learns_only_on_chronologically_available_development": True,
            "promotion_reads_only_the_later_untouched_window": True,
            "rejected_candidates_do_not_enter_the_promoted_lineage": True,
            "evaluation_learning_enabled": False,
            "residency_config": residency.as_dict(),
            "promotion_config": promotion.as_dict(),
        },
        "data": {
            "bars": len(owned),
            "first_timestamp": owned[0].timestamp,
            "last_timestamp": owned[-1].timestamp,
            "data_sha256": digest_value([bar.as_dict() for bar in owned]),
            "fine_context_hours": len(fine),
            "fine_context_sha256": digest_value(fine),
        },
        "program": program.document(),
        "initial_field": {
            "checkpoint_sha256": initial_checkpoint_sha256,
            "field_sha256": initial_field.fingerprint(),
        },
        "cycles": cycles,
        "promotion_count": promotion_count,
        "reset_count": reset_count,
        "final_field": {
            "checkpoint_sha256": _sha256(promoted_checkpoint),
            "field_sha256": final_field.fingerprint(),
        },
        "final_account": campaign_account,
    }
    receipt["content_sha256"] = digest_value(receipt)
    runtime_state: dict[str, Any] = {
        "schema": TEMPORAL_RUNTIME_SCHEMA,
        "field_checkpoint_sha256": _sha256(promoted_checkpoint),
        "field_sha256": final_field.fingerprint(),
        "program": program.document(),
        "account": campaign_account,
        "completed_cycles": len(cycles),
        "promotion_count": promotion_count,
        "reset_count": reset_count,
        "observed_until": cycles[-1]["evaluation"]["last_timestamp"],
        "next_bar_index": cycles[-1]["evaluation"]["end_index_exclusive"],
        "receipt_content_sha256": receipt["content_sha256"],
    }
    runtime_state["content_sha256"] = digest_value(runtime_state)
    return receipt, promoted_checkpoint, runtime_state


def verify_temporal_promotion_campaign(
    receipt: Mapping[str, Any],
    *,
    checkpoint: bytes,
    runtime_state: Mapping[str, Any],
) -> dict[str, Any]:
    if receipt.get("schema") != TEMPORAL_PROMOTION_SCHEMA or receipt.get("status") != "PASS":
        raise ValueError("temporal promotion receipt is invalid")
    if runtime_state.get("schema") != TEMPORAL_RUNTIME_SCHEMA:
        raise ValueError("temporal runtime state is invalid")
    if not content_digest_matches(receipt) or not content_digest_matches(runtime_state):
        raise ValueError("temporal promotion content digest mismatch")
    protocol = receipt["protocol"]
    required = (
        "field_is_sole_adaptive_state",
        "candidate_learns_only_on_chronologically_available_development",
        "promotion_reads_only_the_later_untouched_window",
        "rejected_candidates_do_not_enter_the_promoted_lineage",
    )
    if not all(protocol[name] for name in required) or protocol["evaluation_learning_enabled"]:
        raise ValueError("temporal promotion ownership protocol is invalid")

    promoted_checkpoint_sha256 = receipt["initial_field"]["checkpoint_sha256"]
    promoted_field_sha256 = receipt["initial_field"]["field_sha256"]
    prior_evaluation_end: int | None = None
    promotions = 0
    resets = 0
    promotion_config = TemporalPromotionConfig(**protocol["promotion_config"])
    hard_drawdown = float(protocol["residency_config"]["hard_drawdown"])
    risk_penalty = float(protocol["residency_config"]["risk_penalty"])
    for expected_cycle, cycle in enumerate(receipt["cycles"]):
        if not content_digest_matches(cycle) or cycle["cycle"] != expected_cycle:
            raise ValueError("temporal promotion cycle digest or index mismatch")
        evaluation = cycle["evaluation"]
        if evaluation["start_index"] >= evaluation["end_index_exclusive"]:
            raise ValueError("temporal promotion evaluation window is empty")
        if prior_evaluation_end is not None and evaluation["start_index"] != prior_evaluation_end:
            raise ValueError("temporal promotion windows are not chronological and contiguous")
        if cycle["development"]["end_index_exclusive"] != evaluation["start_index"]:
            raise ValueError("candidate development crosses into its untouched evaluation")
        if cycle["incumbent_before"]["checkpoint_sha256"] != promoted_checkpoint_sha256:
            raise ValueError("incumbent checkpoint lineage mismatch")
        if cycle["incumbent_before"]["field_sha256"] != promoted_field_sha256:
            raise ValueError("incumbent field lineage mismatch")
        for arm_name in ("candidate", "incumbent", "starting_field_control"):
            arm = cycle[arm_name]
            recomputed = _promotion_objective(
                arm["account"]["metrics"],
                risk_penalty=risk_penalty,
            )
            if not math.isclose(recomputed, arm["promotion_objective"], rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(f"{arm_name} promotion objective mismatch")
            if arm["field"]["changed"]:
                raise ValueError(f"{arm_name} mutated during untouched evaluation")
        expected = _promotion_decision(
            cycle["candidate"],
            cycle["incumbent"],
            cycle["starting_field_control"],
            config=promotion_config,
            hard_drawdown=hard_drawdown,
            capacity_available=cycle["candidate_training"]["capacity_event"] is None,
        )
        if cycle["decision"] != expected:
            raise ValueError("temporal promotion decision is inconsistent")
        if cycle["decision"]["selection"] == "candidate":
            promotions += 1
            promoted_checkpoint_sha256 = cycle["candidate_training"]["field"][
                "after_checkpoint_sha256"
            ]
            promoted_field_sha256 = cycle["candidate_training"]["field"]["after_sha256"]
        elif cycle["decision"]["selection"] == "starting_field":
            resets += 1
            promoted_checkpoint_sha256 = receipt["initial_field"]["checkpoint_sha256"]
            promoted_field_sha256 = receipt["initial_field"]["field_sha256"]
        if cycle["promoted_after"]["checkpoint_sha256"] != promoted_checkpoint_sha256:
            raise ValueError("promoted checkpoint chain mismatch")
        if cycle["promoted_after"]["field_sha256"] != promoted_field_sha256:
            raise ValueError("promoted field chain mismatch")
        prior_evaluation_end = evaluation["end_index_exclusive"]

    final_field = RefinementField.restore(checkpoint)
    if _sha256(checkpoint) != receipt["final_field"]["checkpoint_sha256"]:
        raise ValueError("temporal promotion checkpoint digest mismatch")
    if final_field.fingerprint() != receipt["final_field"]["field_sha256"]:
        raise ValueError("temporal promotion field fingerprint mismatch")
    if promotions != receipt["promotion_count"]:
        raise ValueError("temporal promotion count mismatch")
    if runtime_state["field_checkpoint_sha256"] != receipt["final_field"]["checkpoint_sha256"]:
        raise ValueError("temporal runtime checkpoint linkage mismatch")
    if resets != receipt["reset_count"]:
        raise ValueError("temporal reset count mismatch")
    if runtime_state["field_sha256"] != receipt["final_field"]["field_sha256"]:
        raise ValueError("temporal runtime field linkage mismatch")
    if runtime_state["receipt_content_sha256"] != receipt["content_sha256"]:
        raise ValueError("temporal runtime receipt linkage mismatch")
    if runtime_state["account"] != receipt["final_account"]:
        raise ValueError("temporal runtime account mismatch")
    return {
        "status": "PASS",
        "content_sha256": receipt["content_sha256"],
        "cycles": len(receipt["cycles"]),
        "promotions": promotions,
        "final_field_sha256": final_field.fingerprint(),
        "resets": resets,
        "final_equity": float(receipt["final_account"]["equity"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--fine-history", type=Path)
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--program-receipt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--initial-development-bars", type=int, default=8_760)
    parser.add_argument("--evaluation-bars", type=int, default=2_160)
    parser.add_argument(
        "--history-bars",
        type=int,
        help="use only this chronological prefix of the loaded history",
    )
    parser.add_argument("--warmup-bars", type=int, default=720)
    parser.add_argument("--decision-interval", type=int, default=4)
    parser.add_argument("--lesson-interval", type=int, default=24)
    parser.add_argument("--outcome-horizon", type=int, default=12)
    parser.add_argument("--minimum-objective-delta", type=float, default=0.005)
    parser.add_argument("--maximum-drawdown-increase", type=float, default=0.02)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    residency = AggressiveResidencyConfig(
        warmup_bars=args.warmup_bars,
        decision_interval=args.decision_interval,
        lesson_interval=args.lesson_interval,
        outcome_horizon=args.outcome_horizon,
    )
    promotion = TemporalPromotionConfig(
        initial_development_bars=args.initial_development_bars,
        evaluation_bars=args.evaluation_bars,
        minimum_objective_delta=args.minimum_objective_delta,
        maximum_drawdown_increase=args.maximum_drawdown_increase,
    )
    bars = load_bars_csv(args.history, symbol="BTC-USD")
    if args.history_bars is not None:
        if args.history_bars < 1:
            raise SystemExit("--history-bars must be positive")
        bars = bars[: args.history_bars]
    fine = load_fine_context(args.fine_history)
    program = _load_program_receipt(args.program_receipt)
    receipt, checkpoint, runtime_state = run_temporal_promotion_campaign(
        bars,
        initial_checkpoint=args.initial_checkpoint.read_bytes(),
        program=program,
        residency_config=residency,
        promotion_config=promotion,
        fine_context=fine,
    )
    args.output_root.mkdir(parents=True, exist_ok=True)
    receipt_path = args.output_root / "temporal_promotion_receipt.json"
    checkpoint_path = args.output_root / "promoted_refinement_field.chk"
    runtime_path = args.output_root / "temporal_runtime_state.json"
    _atomic_write(receipt_path, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    _atomic_write(checkpoint_path, checkpoint)
    _atomic_write(runtime_path, (json.dumps(runtime_state, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    verification = verify_temporal_promotion_campaign(
        json.loads(receipt_path.read_text(encoding="utf-8")),
        checkpoint=checkpoint_path.read_bytes(),
        runtime_state=json.loads(runtime_path.read_text(encoding="utf-8")),
    )
    print(json.dumps({**verification, "receipt": str(receipt_path), "checkpoint": str(checkpoint_path), "runtime_state": str(runtime_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
