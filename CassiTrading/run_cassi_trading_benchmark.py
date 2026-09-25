#!/usr/bin/env python3
"""Run the deterministic Cassi Trading Foundry milestone benchmark."""

from __future__ import annotations

import argparse
import math
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import cassi_trading_foundry as _foundry
from cassi_trading_foundry import (
    FoundryConfig,
    MarketBar,
    RefinementField,
    ReplayConfig,
    StrategyProgram,
    digest_value,
    load_bars_csv,
    run_backtest,
    run_foundry,
)


BENCHMARK_SCHEMA = "cassi.trading-milestone-benchmark.v4"


@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    name: str
    level: int
    description: str
    regime: str


SCENARIOS = (
    BenchmarkScenario("L1-trend", 1, "single persistent directional regime", "trend"),
    BenchmarkScenario("L2-reversal", 2, "direction reverses once at mid-series", "reversal"),
    BenchmarkScenario("L3-mean-reversion", 3, "price oscillates around a restoring center", "mean_reversion"),
    BenchmarkScenario("L4-volatility", 4, "direction and volatility alternate", "volatility"),
    BenchmarkScenario("L5-mixed", 5, "four interacting market regimes", "mixed"),
)


class BlindRefinementField:
    """Control arm that never reads or writes adaptive field memory."""

    def __init__(self) -> None:
        self._blank = RefinementField()
        self._before = self._blank.fingerprint()

    def predict(self, signature: str, mutation: str) -> dict[str, Any]:
        return {
            "status": "unresolved",
            "outcome": None,
            "score": None,
            "margin": None,
            "reason": "benchmark-field-blind-control",
        }

    def learn(self, signature: str, mutation: str, outcome: str, *, repeats: int = 2) -> None:
        return None

    def fingerprint(self) -> str:
        return self._before

    def checkpoint_bytes(self) -> bytes:
        return self._blank.checkpoint_bytes()


class GuidedRefinementField:
    """Carry a deliberately bounded number of field lessons across scenarios."""

    def __init__(self, *, lesson_budget: int = 2) -> None:
        if lesson_budget < 1:
            raise ValueError("lesson_budget must be positive")
        self._field = RefinementField()
        self.lesson_budget = lesson_budget
        self.lessons_written = 0

    def predict(self, signature: str, mutation: str) -> dict[str, Any]:
        return self._field.predict(signature, mutation)

    def learn(self, signature: str, mutation: str, outcome: str, *, repeats: int = 2) -> None:
        if self.lessons_written >= self.lesson_budget:
            return
        self._field.learn(signature, mutation, outcome, repeats=2)
        self.lessons_written += 1

    def fingerprint(self) -> str:
        return self._field.fingerprint()

    def checkpoint_bytes(self) -> bytes:
        return self._field.checkpoint_bytes()


def _guided_lesson_budget(scenarios: tuple[BenchmarkScenario, ...]) -> int:
    return 1


def _field_lessons(field: GuidedRefinementField | BlindRefinementField) -> int:
    return int(getattr(field, "lessons_written", 0))


def _field_mode(field: GuidedRefinementField | BlindRefinementField) -> str:
    return "guided" if isinstance(field, GuidedRefinementField) else "blind"


def _make_field(guided: bool, lesson_budget: int) -> GuidedRefinementField | BlindRefinementField:
    return GuidedRefinementField(lesson_budget=lesson_budget) if guided else BlindRefinementField()


def _field_metadata(field: GuidedRefinementField | BlindRefinementField) -> dict[str, Any]:
    return {
        "mode": _field_mode(field),
        "lessons_written": _field_lessons(field),
        "field_sha256": field.fingerprint(),
    }


def _bar_series(
    regime: str,
    count: int = 192,
    *,
    symbol: str = "BENCH",
    phase_offset: float = 0.0,
) -> tuple[MarketBar, ...]:
    if count < 96:
        raise ValueError("benchmark scenarios require at least 96 bars")
    price = 100.0
    bars: list[MarketBar] = []
    for index in range(count):
        wave_index = index + phase_offset
        phase = index / max(1, count - 1)
        if regime == "trend":
            drift, noise = 0.0045, 0.0007
        elif regime == "reversal":
            drift, noise = (0.005 if phase < 0.5 else -0.005), 0.0009
        elif regime == "mean_reversion":
            center_error = price / 100.0 - 1.0
            drift = 0.012 * math.sin(wave_index * 0.9) - 0.08 * center_error
            noise = 0.0002
        elif regime == "volatility":
            drift = 0.003 if (index // 24) % 2 == 0 else -0.0025
            noise = 0.0006 if (index // 24) % 2 == 0 else 0.0045
        elif regime == "mixed":
            block = (index // 24) % 4
            drift = (0.005, -0.0045, 0.002, -0.001)[block]
            noise = (0.0007, 0.0010, 0.0035, 0.0050)[block]
        else:
            raise ValueError(f"unknown benchmark regime: {regime}")
        oscillation = noise * math.sin(wave_index * 1.37) + (noise / 2.0) * math.sin(wave_index * 0.43)
        opening = price
        closing = opening * (1.0 + drift + oscillation)
        high = max(opening, closing) * (1.0 + abs(noise) * 0.8)
        low = min(opening, closing) * (1.0 - abs(noise) * 0.8)
        bars.append(
            MarketBar(
                timestamp=f"2026-01-01T{index:04d}Z",
                symbol=symbol,
                open=opening,
                high=high,
                low=low,
                close=closing,
                volume=1000.0 + 50.0 * (index % 13),
            )
        )
        price = closing
    return tuple(bars)
def _historical_plan(
    bars: Sequence[MarketBar],
) -> tuple[
    tuple[BenchmarkScenario, ...],
    tuple[MarketBar, ...],
    Mapping[str, tuple[MarketBar, ...]],
    dict[str, int],
]:
    owned = tuple(bars)
    if len(owned) < 6 * 96:
        raise ValueError("historical benchmark input requires at least 576 bars")
    window = len(owned) // 6
    calibration = owned[:window]
    scenarios: list[BenchmarkScenario] = []
    evaluation: dict[str, tuple[MarketBar, ...]] = {}
    for index in range(5):
        name = f"L{index + 1}-historical-window"
        start = (index + 1) * window
        chunk = owned[start : start + window]
        scenarios.append(
            BenchmarkScenario(
                name,
                index + 1,
                f"historical evaluation window {index + 1}",
                "historical",
            )
        )
        evaluation[name] = chunk
    return (
        tuple(scenarios),
        calibration,
        evaluation,
        {
            "source_bars": len(owned),
            "calibration_bars": len(calibration),
            "evaluation_bars_per_scenario": window,
            "unused_bars": len(owned) - 6 * window,
        },
    )


def _calibrate_guided_field(
    field: GuidedRefinementField,
    config: FoundryConfig,
    bars: Sequence[MarketBar] | None = None,
) -> dict[str, Any]:
    owned_bars = (
        tuple(bars)
        if bars is not None
        else _bar_series("mean_reversion", count=160, symbol="CALIBRATION", phase_offset=0.37)
    )
    train_end, validation_end = _foundry._split_indices(len(owned_bars), config)
    seed = StrategyProgram.seed()
    parent = run_backtest(
        owned_bars,
        seed,
        config.replay,
        start_index=train_end - 1,
        end_index=validation_end - 1,
    )
    candidate = _foundry._child_program(seed, "mean_reversion")
    candidate_result = run_backtest(
        owned_bars,
        candidate,
        config.replay,
        start_index=train_end - 1,
        end_index=validation_end - 1,
    )
    signature = _foundry._failure_signature(parent.metrics)
    enough_trades = candidate_result.metrics["trade_count"] >= config.minimum_trades
    safe_drawdown = candidate_result.metrics["max_drawdown"] <= config.maximum_drawdown
    improved = candidate_result.metrics["objective"] >= parent.metrics["objective"] + config.minimum_improvement
    outcome = "promote" if enough_trades and safe_drawdown and improved else "reject"
    if candidate_result.metrics["trade_count"] < config.minimum_trades:
        outcome = "uncertain"
    before = field.fingerprint()
    field.learn(signature, "mean_reversion", outcome)
    return {
        "data_sha256": digest_value([bar.as_dict() for bar in owned_bars]),
        "signature": signature,
        "mutation": "mean_reversion",
        "outcome": outcome,
        "before_sha256": before,
        "after_sha256": field.fingerprint(),
        "parent_metrics": dict(parent.metrics),
        "candidate_metrics": dict(candidate_result.metrics),
    }


def _config(args: argparse.Namespace) -> FoundryConfig:
    return FoundryConfig(
        max_rounds=args.max_rounds,
        max_candidates_per_round=args.max_candidates,
        replay=ReplayConfig(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps),
    )


def _probe_field_before_selection(receipt: Mapping[str, Any]) -> dict[str, Any]:
    first_round = receipt["development"]["rounds"][0]
    candidates = first_round["candidates"]
    if not candidates:
        return {
            "signature": first_round["failure_signature"],
            "mutation": None,
            "status": "unresolved",
            "outcome": None,
            "score": None,
            "margin": None,
            "reason": "no-candidates",
        }
    candidate = candidates[0]
    prediction = candidate["field_prediction"]
    return {
        "signature": first_round["failure_signature"],
        "mutation": candidate["mutation"],
        "status": prediction.get("status"),
        "outcome": prediction.get("outcome"),
        "score": prediction.get("score"),
        "margin": prediction.get("margin"),
        "reason": prediction.get("reason"),
    }


def _run_arm(
    scenarios: tuple[BenchmarkScenario, ...],
    *,
    guided: bool,
    config: FoundryConfig,
    scenario_bars: Mapping[str, tuple[MarketBar, ...]] | None = None,
    calibration_bars: Sequence[MarketBar] | None = None,
    financial_composition_id: str | None = None,
    mode: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lesson_budget = _guided_lesson_budget(scenarios)
    shared_field = _make_field(guided, lesson_budget)
    calibration = None
    if guided:
        if not isinstance(shared_field, GuidedRefinementField):
            raise TypeError("guided benchmark arm did not receive a guided field")
        calibration = _calibrate_guided_field(shared_field, config, calibration_bars)
    results: list[dict[str, Any]] = []
    arm_mode = mode or ("guided" if guided else "blind")
    for scenario in scenarios:
        bars = (
            scenario_bars[scenario.name]
            if scenario_bars is not None
            else _bar_series(scenario.regime)
        )
        field = shared_field if guided else _make_field(False, lesson_budget)
        receipt = run_foundry(
            bars,
            config=config,
            field_memory=field,
            financial_composition_id=financial_composition_id,
        )
        holdout = receipt["holdout"]
        financial = receipt["financial"]
        results.append(
            {
                "scenario": scenario.name,
                "level": scenario.level,
                "regime": scenario.regime,
                "data_sha256": receipt["data"]["data_sha256"],
                "selected_program_sha256": receipt["selected"]["program_sha256"],
                "selected_family": receipt["selected"]["family"],
                "selected_mutation": receipt["selected"]["mutation"],
                "holdout_metrics": holdout["metrics"],
                "financial_composition_id": financial["composition"]["composition_id"],
                "financial_composition_override": financial["override"],
                "financial_selection_signature": financial["selection_signature"],
                "financial_validation_objective": financial["validation"]["objective"],
                "financial_holdout_objective": financial["holdout"]["objective"],
                "financial_holdout_delta_vs_default": financial["holdout"][
                    "objective_delta_vs_default"
                ],
                "field_before_sha256": receipt["field"]["before_sha256"],
                "field_after_sha256": receipt["field"]["after_sha256"],
                "field_metadata": _field_metadata(field),
                "field_probe": _probe_field_before_selection(receipt),
                "rounds": len(receipt["development"]["rounds"]),
            }
        )
    return results, {
        "mode": arm_mode,
        "lesson_budget": lesson_budget,
        "calibration": calibration,
        "financial_composition_id": financial_composition_id,
    }


def _pair_results(
    guided: list[dict[str, Any]],
    blind: list[dict[str, Any]],
    fixed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blind_by_name = {row["scenario"]: row for row in blind}
    fixed_by_name = {row["scenario"]: row for row in fixed}
    paired: list[dict[str, Any]] = []
    for row in guided:
        control = blind_by_name[row["scenario"]]
        fixed_control = fixed_by_name[row["scenario"]]
        guided_metrics = row["holdout_metrics"]
        blind_metrics = control["holdout_metrics"]
        fixed_metrics = fixed_control["holdout_metrics"]
        paired.append(
            {
                "scenario": row["scenario"],
                "level": row["level"],
                "data_match": row["data_sha256"] == control["data_sha256"],
                "fixed_data_match": row["data_sha256"] == fixed_control["data_sha256"],
                "program_changed": row["selected_program_sha256"] != control["selected_program_sha256"],
                "guided_vs_fixed_program_changed": (
                    row["selected_program_sha256"] != fixed_control["selected_program_sha256"]
                ),
                "guided_family": row["selected_family"],
                "blind_family": control["selected_family"],
                "fixed_family": fixed_control["selected_family"],
                "guided_mutation": row["selected_mutation"],
                "blind_mutation": control["selected_mutation"],
                "fixed_mutation": fixed_control["selected_mutation"],
                "guided_field_status": row["field_probe"]["status"],
                "blind_field_status": control["field_probe"]["status"],
                "fixed_field_status": fixed_control["field_probe"]["status"],
                "guided_financial_composition": row["financial_composition_id"],
                "blind_financial_composition": control["financial_composition_id"],
                "fixed_financial_composition": fixed_control["financial_composition_id"],
                "guided_financial_holdout_objective": row["financial_holdout_objective"],
                "blind_financial_holdout_objective": control["financial_holdout_objective"],
                "fixed_financial_holdout_objective": fixed_control["financial_holdout_objective"],
                "guided_minus_blind_financial_holdout_objective": (
                    row["financial_holdout_objective"] - control["financial_holdout_objective"]
                ),
                "guided_minus_fixed_financial_holdout_objective": (
                    row["financial_holdout_objective"]
                    - fixed_control["financial_holdout_objective"]
                ),
                "fixed_minus_blind_financial_holdout_objective": (
                    fixed_control["financial_holdout_objective"]
                    - control["financial_holdout_objective"]
                ),
                "guided_financial_holdout_delta_vs_default": row[
                    "financial_holdout_delta_vs_default"
                ],
                "blind_financial_holdout_delta_vs_default": control[
                    "financial_holdout_delta_vs_default"
                ],
                "fixed_financial_holdout_delta_vs_default": fixed_control[
                    "financial_holdout_delta_vs_default"
                ],
                "guided_net_return": guided_metrics["net_return"],
                "blind_net_return": blind_metrics["net_return"],
                "fixed_net_return": fixed_metrics["net_return"],
                "guided_minus_blind_net_return": guided_metrics["net_return"] - blind_metrics["net_return"],
                "guided_minus_fixed_net_return": guided_metrics["net_return"] - fixed_metrics["net_return"],
                "guided_objective": guided_metrics["objective"],
                "blind_objective": blind_metrics["objective"],
                "fixed_objective": fixed_metrics["objective"],
                "guided_minus_blind_objective": guided_metrics["objective"] - blind_metrics["objective"],
                "guided_minus_fixed_objective": guided_metrics["objective"] - fixed_metrics["objective"],
                "guided_max_drawdown": guided_metrics["max_drawdown"],
                "blind_max_drawdown": blind_metrics["max_drawdown"],
                "fixed_max_drawdown": fixed_metrics["max_drawdown"],
            }
        )
    return paired


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    config = _config(args)
    csv_path = getattr(args, "csv", None)
    symbol = getattr(args, "symbol", None)
    if csv_path is None:
        scenarios = SCENARIOS
        calibration_bars = None
        scenario_bars = None
        source_stats = {
            "input_source": "synthetic",
            "source_endpoint": None,
            "input_data_sha256": None,
            "source_bars": None,
            "calibration_bars": 160,
            "evaluation_bars_per_scenario": 192,
            "unused_bars": 0,
        }
    else:
        bars = load_bars_csv(csv_path, symbol=symbol)
        scenarios, calibration_bars, scenario_bars, historical_stats = _historical_plan(bars)
        source_stats = {
            "input_source": "historical_csv",
            "source_endpoint": f"https://api.exchange.coinbase.com/products/{symbol or bars[0].symbol}/candles",
            "input_data_sha256": digest_value([bar.as_dict() for bar in bars]),
            **historical_stats,
        }
    fixed_composition_id = getattr(args, "fixed_financial_composition", "balanced")
    guided, guided_protocol = _run_arm(
        scenarios,
        guided=True,
        config=config,
        scenario_bars=scenario_bars,
        calibration_bars=calibration_bars,
    )
    blind, blind_protocol = _run_arm(
        scenarios,
        guided=False,
        config=config,
        scenario_bars=scenario_bars,
        calibration_bars=calibration_bars,
    )
    fixed, fixed_protocol = _run_arm(
        scenarios,
        guided=True,
        config=config,
        scenario_bars=scenario_bars,
        calibration_bars=calibration_bars,
        financial_composition_id=fixed_composition_id,
        mode="fixed",
    )
    body: dict[str, Any] = {
        "schema": BENCHMARK_SCHEMA,
        "status": "PASS",
        "protocol": {
            **source_stats,
            "scenario_count": len(scenarios),
            "guided_memory": "one field carried across scenarios after a separate calibration regime",
            "blind_control": "no field prediction or learning",
            "fixed_control": "guided field with a fixed financial composition override",
            "fixed_financial_composition": fixed_composition_id,
            "calibration_phase_offset": None if csv_path is not None else 0.37,
            "config": config.as_dict(),
        },
        "arm_protocol": {
            "guided": guided_protocol,
            "blind": blind_protocol,
            "fixed": fixed_protocol,
        },
        "scenarios": [
            {
                "name": scenario.name,
                "level": scenario.level,
                "description": scenario.description,
                "regime": scenario.regime,
            }
            for scenario in scenarios
        ],
        "guided": guided,
        "blind": blind,
        "fixed": fixed,
        "paired": _pair_results(guided, blind, fixed),
    }
    body["content_sha256"] = digest_value(body)
    return body


def verify_benchmark(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != BENCHMARK_SCHEMA:
        raise ValueError("benchmark schema mismatch")
    if receipt.get("status") != "PASS":
        raise ValueError("benchmark did not pass")
    if (
        not isinstance(receipt.get("guided"), list)
        or not isinstance(receipt.get("blind"), list)
        or not isinstance(receipt.get("fixed"), list)
    ):
        raise ValueError("benchmark arms are missing")
    scenarios = receipt.get("scenarios")
    paired = receipt.get("paired")
    if not isinstance(scenarios, list) or not isinstance(paired, list):
        raise ValueError("benchmark scenarios or pairs are missing")
    if (
        len(receipt["guided"]) != len(scenarios)
        or len(receipt["blind"]) != len(scenarios)
        or len(receipt["fixed"]) != len(scenarios)
    ):
        raise ValueError("benchmark scenario count mismatch")
    if len(paired) != len(scenarios):
        raise ValueError("benchmark pair count mismatch")
    if any(not row["data_match"] or not row["fixed_data_match"] for row in paired):
        raise ValueError("benchmark arms do not share data identities")
    body = dict(receipt)
    stated = body.pop("content_sha256", None)
    if not isinstance(stated, str) or digest_value(body) != stated:
        raise ValueError("benchmark content digest mismatch")
    return {"status": "PASS", "content_sha256": stated}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="historical OHLCV CSV for real-data mode")
    parser.add_argument("--symbol", default=None, help="symbol to select from a multi-symbol CSV")
    parser.add_argument("--out-dir", type=Path, default=Path("_diag/trading-foundry-benchmark"))
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--max-candidates", type=int, default=6)
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument(
        "--fixed-financial-composition",
        default="balanced",
        help="fixed composition used by the guided-field objective control",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run_benchmark(args)
    verification = verify_benchmark(receipt)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / "milestone_benchmark.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "status": verification["status"],
        "receipt": str(path),
        "content_sha256": verification["content_sha256"],
        "paired": receipt["paired"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
