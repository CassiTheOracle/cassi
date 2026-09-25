#!/usr/bin/env python3
"""Measure whether one bounded field relation transfers across later market regimes."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_aggressive_residency import (
    AggressiveResidencyConfig,
    _atomic_write,
    _load_program_receipt,
    _sha256,
    load_fine_context,
)
from cassi_temporal_promotion import (
    TEMPORAL_PROMOTION_SCHEMA,
    TemporalPromotionConfig,
    run_temporal_promotion_campaign,
    verify_temporal_promotion_campaign,
)
from cassi_trading_foundry import (
    MarketBar,
    StrategyProgram,
    content_digest_matches,
    digest_value,
    load_bars_csv,
)


CROSS_REGIME_BOARD_SCHEMA = "cassi.trading-cross-regime-board.v1"


@dataclass(frozen=True, slots=True)
class CrossRegimeScenario:
    name: str
    development_start: str
    evaluation_regime: str
    development_bars: int = 8_760
    evaluation_bars: int = 2_160

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "development_start": self.development_start,
            "evaluation_regime": self.evaluation_regime,
            "development_bars": self.development_bars,
            "evaluation_bars": self.evaluation_bars,
        }


STANDARD_SCENARIOS = (
    CrossRegimeScenario("early-bull", "2016-01-01T00:00:00Z", "early-bull"),
    CrossRegimeScenario("bear-break", "2017-01-01T00:00:00Z", "bear-break"),
    CrossRegimeScenario("volatility-shock", "2019-01-01T00:00:00Z", "volatility-shock"),
    CrossRegimeScenario("recovery-rally", "2020-01-01T00:00:00Z", "recovery-rally"),
)

CONSTRUCTIVE_AUTHORITY_SCENARIOS = (
    CrossRegimeScenario(
        "post-crash-expansion",
        "2020-04-01T00:00:00Z",
        "post-crash expansion",
    ),
    CrossRegimeScenario(
        "pre-etf-expansion",
        "2023-04-01T00:00:00Z",
        "pre-ETF expansion",
    ),
    CrossRegimeScenario(
        "post-etf-transition",
        "2024-01-01T00:00:00Z",
        "post-ETF transition",
    ),
    CrossRegimeScenario(
        "late-cycle-transition",
        "2025-01-01T00:00:00Z",
        "late-cycle transition",
    ),
)


def _scenario_slice(
    bars: Sequence[MarketBar], scenario: CrossRegimeScenario
) -> tuple[tuple[MarketBar, ...], int]:
    start_index = next(
        (
            index
            for index, bar in enumerate(bars)
            if bar.timestamp == scenario.development_start
        ),
        None,
    )
    if start_index is None:
        raise ValueError(
            f"scenario {scenario.name} start is absent from the supplied history"
        )
    end_index = start_index + scenario.development_bars + scenario.evaluation_bars
    if end_index > len(bars):
        raise ValueError(f"scenario {scenario.name} exceeds the supplied history")
    return tuple(bars[start_index:end_index]), start_index


def _classification(
    cycle: Mapping[str, Any], promotion: TemporalPromotionConfig
) -> str:
    candidate = cycle["candidate"]
    control = cycle["starting_field_control"]
    authority = int(candidate["authority"]["field_supported_steps"])
    objective_delta = float(candidate["promotion_objective"]) - float(
        control["promotion_objective"]
    )
    net_delta = float(candidate["account"]["metrics"]["net_return"]) - float(
        control["account"]["metrics"]["net_return"]
    )
    if authority == 0:
        return "ABSTENTION"
    if cycle["decision"]["selection"] == "candidate":
        return "AUTHORITATIVE_TRANSFER"
    if objective_delta >= promotion.minimum_objective_delta and net_delta >= 0.0:
        return "INHIBITORY_TRANSFER"
    if net_delta < 0.0:
        return "HARMFUL_TRANSFER"
    return "NO_PORTABLE_AUTHORITY"


def _scenario_summary(
    scenario: CrossRegimeScenario,
    *,
    source_start_index: int,
    receipt: Mapping[str, Any],
    promotion: TemporalPromotionConfig,
) -> dict[str, Any]:
    cycles = receipt["cycles"]
    if len(cycles) != 1:
        raise ValueError("cross-regime scenario must contain exactly one evaluation")
    cycle = cycles[0]
    candidate = cycle["candidate"]
    control = cycle["starting_field_control"]
    candidate_metrics = candidate["account"]["metrics"]
    control_metrics = control["account"]["metrics"]
    return {
        "scenario": scenario.as_dict(),
        "source": {
            "start_index": source_start_index,
            "development": dict(cycle["development"]),
            "evaluation": dict(cycle["evaluation"]),
        },
        "candidate": {
            "net_return": float(candidate_metrics["net_return"]),
            "max_drawdown": float(candidate_metrics["max_drawdown"]),
            "promotion_objective": float(candidate["promotion_objective"]),
            "authority": dict(candidate["authority"]),
            "field_sha256": candidate["field"]["before_sha256"],
        },
        "starting_field_control": {
            "net_return": float(control_metrics["net_return"]),
            "max_drawdown": float(control_metrics["max_drawdown"]),
            "promotion_objective": float(control["promotion_objective"]),
        },
        "deltas": {
            "net_return": float(candidate_metrics["net_return"])
            - float(control_metrics["net_return"]),
            "max_drawdown": float(candidate_metrics["max_drawdown"])
            - float(control_metrics["max_drawdown"]),
            "promotion_objective": float(candidate["promotion_objective"])
            - float(control["promotion_objective"]),
        },
        "selection": str(cycle["decision"]["selection"]),
        "classification": _classification(cycle, promotion),
        "temporal_receipt_content_sha256": receipt["content_sha256"],
    }


def _board_verdict(rows: Sequence[Mapping[str, Any]]) -> tuple[str, dict[str, int]]:
    counts = {
        label: sum(row["classification"] == label for row in rows)
        for label in (
            "AUTHORITATIVE_TRANSFER",
            "INHIBITORY_TRANSFER",
            "ABSTENTION",
            "HARMFUL_TRANSFER",
            "NO_PORTABLE_AUTHORITY",
        )
    }
    if counts["AUTHORITATIVE_TRANSFER"] >= 2:
        verdict = "SUPPORTS_PORTABLE_AUTHORITY"
    elif counts["INHIBITORY_TRANSFER"] >= 2 and not counts["HARMFUL_TRANSFER"]:
        verdict = "SUPPORTS_INHIBITORY_TRANSFER_ONLY"
    else:
        verdict = "DOES_NOT_SUPPORT_PORTABLE_AUTHORITY"
    return verdict, counts


def run_cross_regime_board(
    bars: Sequence[MarketBar],
    *,
    initial_checkpoint: bytes,
    program: StrategyProgram,
    scenarios: Sequence[CrossRegimeScenario] = STANDARD_SCENARIOS,
    residency_config: AggressiveResidencyConfig | None = None,
    promotion_config: TemporalPromotionConfig | None = None,
    fine_context: Mapping[str, Mapping[str, float]] | None = None,
) -> tuple[dict[str, Any], dict[str, tuple[dict[str, Any], bytes, dict[str, Any]]]]:
    if not scenarios:
        raise ValueError("cross-regime board requires at least one scenario")
    if len({scenario.name for scenario in scenarios}) != len(scenarios):
        raise ValueError("cross-regime scenario names must be unique")
    owned = tuple(bars)
    residency = residency_config or AggressiveResidencyConfig()
    promotion = promotion_config or TemporalPromotionConfig()
    fine = dict(fine_context or {})
    initial_before = bytes(initial_checkpoint)
    artifacts: dict[str, tuple[dict[str, Any], bytes, dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        window, start_index = _scenario_slice(owned, scenario)
        receipt, checkpoint, runtime = run_temporal_promotion_campaign(
            window,
            initial_checkpoint=initial_checkpoint,
            program=program,
            residency_config=residency,
            promotion_config=promotion,
            fine_context=fine,
        )
        if initial_checkpoint != initial_before:
            raise RuntimeError("cross-regime scenario mutated the initial field")
        verification = verify_temporal_promotion_campaign(
            receipt,
            checkpoint=checkpoint,
            runtime_state=runtime,
        )
        if verification["status"] != "PASS":
            raise RuntimeError(f"cross-regime scenario {scenario.name} failed verification")
        artifacts[scenario.name] = (receipt, checkpoint, runtime)
        rows.append(
            _scenario_summary(
                scenario,
                source_start_index=start_index,
                receipt=receipt,
                promotion=promotion,
            )
        )
    verdict, classification_counts = _board_verdict(rows)
    body: dict[str, Any] = {
        "schema": CROSS_REGIME_BOARD_SCHEMA,
        "status": "PASS",
        "verdict": verdict,
        "protocol": {
            "field_is_sole_adaptive_state": True,
            "scenarios_train_on_disjoint_chronological_prefixes": True,
            "each_evaluation_is_later_and_learning_disabled": True,
            "every_scenario_starts_from_the_same_initial_checkpoint": True,
            "authoritative_transfer_requires_two_positive_promotions": True,
            "inhibitory_transfer_requires_two_nonharmful_later_improvements": True,
            "residency_config": residency.as_dict(),
            "promotion_config": promotion.as_dict(),
        },
        "source": {
            "history_sha256": digest_value([bar.as_dict() for bar in owned]),
            "initial_checkpoint_sha256": _sha256(initial_checkpoint),
            "program_sha256": program.program_sha256,
            "fine_context_sha256": digest_value(fine),
        },
        "scenario_rows": rows,
        "classification_counts": classification_counts,
    }
    body["content_sha256"] = digest_value(body)
    return body, artifacts


def verify_cross_regime_board(
    receipt: Mapping[str, Any],
    *,
    initial_checkpoint: bytes,
    artifacts: Mapping[str, tuple[Mapping[str, Any], bytes, Mapping[str, Any]]],
) -> dict[str, Any]:
    if receipt.get("schema") != CROSS_REGIME_BOARD_SCHEMA or receipt.get("status") != "PASS":
        raise ValueError("cross-regime board receipt is invalid")
    if not content_digest_matches(receipt):
        raise ValueError("cross-regime board content digest mismatch")
    if _sha256(initial_checkpoint) != receipt["source"]["initial_checkpoint_sha256"]:
        raise ValueError("cross-regime board initial checkpoint mismatch")
    rows = receipt["scenario_rows"]
    if len(rows) != len(artifacts):
        raise ValueError("cross-regime board artifact count mismatch")
    promotion = TemporalPromotionConfig(**receipt["protocol"]["promotion_config"])
    for row in rows:
        name = row["scenario"]["name"]
        if name not in artifacts:
            raise ValueError(f"cross-regime board is missing artifact {name}")
        nested, checkpoint, runtime = artifacts[name]
        verification = verify_temporal_promotion_campaign(
            nested,
            checkpoint=checkpoint,
            runtime_state=runtime,
        )
        if verification["status"] != "PASS":
            raise ValueError(f"cross-regime scenario {name} verification failed")
        scenario = CrossRegimeScenario(**row["scenario"])
        expected = _scenario_summary(
            scenario,
            source_start_index=int(row["source"]["start_index"]),
            receipt=nested,
            promotion=promotion,
        )
        if expected != row:
            raise ValueError(f"cross-regime scenario {name} summary mismatch")
        if nested.get("schema") != TEMPORAL_PROMOTION_SCHEMA:
            raise ValueError(f"cross-regime scenario {name} receipt schema mismatch")
    verdict, counts = _board_verdict(rows)
    if counts != receipt["classification_counts"] or verdict != receipt["verdict"]:
        raise ValueError("cross-regime board verdict mismatch")
    return {
        "status": "PASS",
        "verdict": verdict,
        "content_sha256": receipt["content_sha256"],
        "scenario_count": len(rows),
        **counts,
    }


SCENARIO_SETS: Mapping[str, tuple[CrossRegimeScenario, ...]] = {
    "standard": STANDARD_SCENARIOS,
    "constructive-authority": CONSTRUCTIVE_AUTHORITY_SCENARIOS,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--fine-history", type=Path)
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--program-receipt", type=Path, required=True)
    parser.add_argument(
        "--scenario-set",
        choices=tuple(SCENARIO_SETS),
        default="standard",
        help="frozen chronological scenario family to evaluate",
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt_path = args.out / "cross_regime_board.json"
    if receipt_path.exists():
        raise SystemExit(f"refusing to overwrite frozen board receipt: {receipt_path}")
    args.out.mkdir(parents=True, exist_ok=True)
    checkpoint = args.initial_checkpoint.read_bytes()
    board, artifacts = run_cross_regime_board(
        load_bars_csv(args.history, symbol="BTC-USD"),
        initial_checkpoint=checkpoint,
        program=_load_program_receipt(args.program_receipt),
        scenarios=SCENARIO_SETS[args.scenario_set],
        fine_context=load_fine_context(args.fine_history),
    )
    persisted: dict[str, tuple[Mapping[str, Any], bytes, Mapping[str, Any]]] = {}
    for name, (receipt, selected_checkpoint, runtime) in artifacts.items():
        scenario_dir = args.out / "scenarios" / name
        scenario_dir.mkdir(parents=True, exist_ok=True)
        nested_path = scenario_dir / "temporal_promotion_receipt.json"
        checkpoint_path = scenario_dir / "selected_refinement_field.chk"
        runtime_path = scenario_dir / "temporal_runtime_state.json"
        _atomic_write(nested_path, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        _atomic_write(checkpoint_path, selected_checkpoint)
        _atomic_write(runtime_path, (json.dumps(runtime, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        persisted[name] = (
            json.loads(nested_path.read_text(encoding="utf-8")),
            checkpoint_path.read_bytes(),
            json.loads(runtime_path.read_text(encoding="utf-8")),
        )
    _atomic_write(receipt_path, (json.dumps(board, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    verification = verify_cross_regime_board(
        json.loads(receipt_path.read_text(encoding="utf-8")),
        initial_checkpoint=checkpoint,
        artifacts=persisted,
    )
    print(json.dumps({**verification, "receipt": str(receipt_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
