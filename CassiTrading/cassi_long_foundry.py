"""Chronological multi-window strategy evolution with a carried field."""

from __future__ import annotations

from dataclasses import replace


from cassi_market_contracts import digest_value
from cassi_trading_foundry import (
    AcquisitionProfile,
    FoundryConfig,
    MarketBar,
    RefinementField,
    ReplayConfig,
    StrategyProgram,
    _child_program,
    run_backtest,
    run_foundry,
)
from cassi_raw_event_field import CapacityError


LONG_FOUNDRY_SCHEMA = "cassi.long-foundry-evolution.v1"


def _program_from_document(document: dict[str, Any]) -> StrategyProgram:
    return StrategyProgram(
        strategy_id=str(document["strategy_id"]),
        source=str(document["source"]),
        parameters=dict(document["parameters"]),
        family=str(document["family"]),
        parent_id=document.get("parent_id"),
        mutation=str(document.get("mutation", "seed")),
    )

def run_long_foundry(
    bars: Sequence[MarketBar],
    *,
    window_bars: int = 720,
    step_bars: int = 720,
    max_windows: int | None = None,
    max_rounds: int = 4,
    max_candidates: int = 12,
    validation_slices: int = 2,
    minimum_improvement: float = 0.0005,
    seed_mutation: str | None = None,
    timeframe_hours: float = 1.0,
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    component_limit: float = 0.5,
) -> dict[str, Any]:
    owned = tuple(bars)
    if not owned:
        raise ValueError("long foundry requires market bars")
    if any(bar.symbol != owned[0].symbol for bar in owned):
        raise ValueError("long foundry requires one instrument")
    if window_bars < 32 or step_bars < 1:
        raise ValueError("window_bars must be >= 32 and step_bars must be positive")
    starts = tuple(range(0, max(0, len(owned) - window_bars + 1), step_bars))
    if max_windows is not None:
        if max_windows < 1:
            raise ValueError("max_windows must be positive when supplied")
        starts = starts[:max_windows]
    if not starts:
        raise ValueError("history does not contain a complete evolution window")
    field = RefinementField(profile=AcquisitionProfile(component_limit=component_limit))
    seed_program = StrategyProgram.seed()
    if seed_mutation is not None:
        seed_program = _child_program(seed_program, seed_mutation)
    program = seed_program
    initial_field_sha = field.fingerprint()
    config = FoundryConfig(
        max_rounds=max_rounds,
        max_candidates_per_round=max_candidates,
        validation_slices=validation_slices,
        replay=ReplayConfig(fee_bps=fee_bps, slippage_bps=slippage_bps, timeframe_hours=timeframe_hours),
    )
    windows: list[dict[str, Any]] = []
    stop: dict[str, Any] | None = None
    learning_enabled = True
    for window_index, start in enumerate(starts):
        end = start + window_bars
        segment = owned[start:end]
        field_before = field.fingerprint()
        field_checkpoint = field.checkpoint_bytes()
        parent_program = program.document()
        active_config = config if learning_enabled else replace(config, learn_field=False)
        field_learning = "adaptive" if learning_enabled else "frozen_after_capacity"
        try:
            receipt = run_foundry(segment, seed=program, config=active_config, field_memory=field)
        except CapacityError as exc:
            if not learning_enabled:
                raise
            field = RefinementField.restore(field_checkpoint)
            stop = {
                "window_index": window_index,
                "start_index": start,
                "end_index": end,
                "start_timestamp": segment[0].timestamp,
                "end_timestamp": segment[-1].timestamp,
                "reason": "field_capacity",
                "error": str(exc),
                "field_sha256": field.fingerprint(),
                "program_sha256": program.program_sha256,
            }
            learning_enabled = False
            field_learning = "frozen_after_capacity"
            receipt = run_foundry(
                segment,
                seed=program,
                config=replace(config, learn_field=False),
                field_memory=field,
            )
        program = _program_from_document(receipt["selected"])
        selected_rounds = [
            row["selected_mutation"]
            for row in receipt["development"]["rounds"]
            if row["selected_mutation"] is not None
        ]
        field_candidates = [
            candidate
            for round_receipt in receipt["development"]["rounds"]
            for candidate in round_receipt["candidates"]
            if isinstance(candidate.get("field_signature"), str)
        ]
        pair_counts: dict[str, int] = {}
        family_mutation_contexts: dict[str, dict[str, set[str]]] = {}
        for candidate in field_candidates:
            pair = f'{candidate["field_signature"]}|{candidate["mutation"]}'
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
            family = candidate.get("field_transfer_family")
            if isinstance(family, str):
                mutation_contexts = family_mutation_contexts.setdefault(family, {})
                mutation_contexts.setdefault(candidate["mutation"], set()).add(
                    candidate["field_signature"]
                )
        family_recurrence = {
            family: {
                mutation: len(signatures)
                for mutation, signatures in mutation_contexts.items()
                if len(signatures) > 1
            }
            for family, mutation_contexts in family_mutation_contexts.items()
        }
        field_admissions = [
            candidate["field_admission"]
            for candidate in field_candidates
            if isinstance(candidate.get("field_admission"), dict)
        ]
        admission_counts = {
            kind: sum(admission["admission"] == kind for admission in field_admissions)
            for kind in sorted({admission["admission"] for admission in field_admissions})
        }
        field_quality = {
            "lesson_count": len(field_admissions),
            "admission_counts": admission_counts,
            "promoted_count": sum(bool(admission["promoted"]) for admission in field_admissions),
            "generalized_count": sum(
                admission.get("prediction_context_scope") == "family"
                for admission in field_admissions
            ),
            "repeats_total": sum(int(admission["repeats"]) for admission in field_admissions),
            "candidate_count": len(field_candidates),
            "distinct_signature_mutations": len(pair_counts),
            "repeated_signature_mutations": sum(
                max(count - 1, 0) for count in pair_counts.values()
            ),
            "family_mutation_context_recurrence": family_recurrence,
            "validation_slice_evidence_count": sum(
                len(candidate.get("validation_slice_evidence", ()))
                for candidate in field_candidates
            ),
        }
        holdout_start = int(receipt["data"]["holdout_start"])
        parent_metrics = run_backtest(
            segment,
            _program_from_document(parent_program),
            config.replay,
            start_index=holdout_start,
            end_index=len(segment) - 1,
        ).metrics
        seed_metrics = run_backtest(
            segment,
            seed_program,
            config.replay,
            start_index=holdout_start,
            end_index=len(segment) - 1,
        ).metrics
        windows.append(
            {
                "window_index": window_index,
                "start_index": start,
                "end_index": end,
                "start_timestamp": segment[0].timestamp,
                "end_timestamp": segment[-1].timestamp,
                "bars": len(segment),
                "field_learning": field_learning,
                "field_quality": field_quality,
                "field_before_sha256": field_before,
                "field_after_sha256": field.fingerprint(),
                "field_changed": field_before != field.fingerprint(),
                "parent_program": parent_program,
                "selected_program": program.document(),
                "selected_mutations": selected_rounds,
                "round_count": len(receipt["development"]["rounds"]),
                "holdout_metrics": receipt["holdout"]["metrics"],
                "parent_holdout_metrics": dict(parent_metrics),
                "seed_holdout_metrics": dict(seed_metrics),
                "objective_delta_vs_parent": float(receipt["holdout"]["metrics"]["objective"]) - float(parent_metrics["objective"]),
                "objective_delta_vs_seed": float(receipt["holdout"]["metrics"]["objective"]) - float(seed_metrics["objective"]),
                "holdout_start": receipt["data"]["holdout_start"],
                "receipt_sha256": receipt["content_sha256"],
            }
        )
    body: dict[str, Any] = {
        "schema": LONG_FOUNDRY_SCHEMA,
        "status": "PASS_WITH_CAPACITY_LIMIT" if stop is not None else "PASS",
        "data": {
            "symbol": owned[0].symbol,
            "bars": len(owned),
            "data_sha256": digest_value([bar.as_dict() for bar in owned]),
            "first_timestamp": owned[0].timestamp,
            "last_timestamp": owned[-1].timestamp,
        },
        "config": {
            "window_bars": window_bars,
            "step_bars": step_bars,
            "max_windows": max_windows,
            "max_rounds": max_rounds,
            "max_candidates": max_candidates,
            "validation_slices": validation_slices,
            "minimum_improvement": minimum_improvement,
            "seed_mutation": seed_mutation,
            "timeframe_hours": timeframe_hours,
            "fee_bps": fee_bps,
            "slippage_bps": slippage_bps,
            "component_limit": component_limit,
        },
        "initial_program": seed_program.document(),
        "final_program": program.document(),
        "initial_field_sha256": initial_field_sha,
        "final_field_sha256": field.fingerprint(),
        "field_changed": initial_field_sha != field.fingerprint(),
        "windows": windows,
        "stop": stop,
        "unused_tail_bars": len(owned) - (starts[-1] + window_bars),
        "ownership": {
            "strategy_executor": "CassiPy bounded interpreter",
            "algorithm_selection": "field-guided bounded refinement",
            "field_owner": "RawEventLearner.state.field",
            "external_effect": "none",
            "exchange_calls": 0,
        },
    }
    body["content_sha256"] = digest_value(body)
    return body


def verify_long_foundry_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != LONG_FOUNDRY_SCHEMA:
        raise ValueError("long foundry schema mismatch")
    if receipt.get("status") not in {"PASS", "PASS_WITH_CAPACITY_LIMIT"}:
        raise ValueError("long foundry status is invalid")
    expected = dict(receipt)
    actual = expected.pop("content_sha256", None)
    if not isinstance(actual, str):
        raise ValueError("long foundry content digest missing")
    recomputed = digest_value(expected)
    if recomputed != actual:
        raise ValueError("long foundry content digest mismatch")
    windows = receipt.get("windows")
    if not isinstance(windows, list):
        raise ValueError("long foundry windows must be a list")
    if not windows and receipt.get("status") != "PASS_WITH_CAPACITY_LIMIT":
        raise ValueError("successful long foundry requires nonempty windows")
    for previous, current in zip(windows, windows[1:]):
        if current["start_index"] <= previous["start_index"]:
            raise ValueError("long foundry windows are not chronological")
        if current["parent_program"]["program_sha256"] != previous["selected_program"]["program_sha256"]:
            raise ValueError("algorithm evolution chain is broken")
        if current["field_before_sha256"] != previous["field_after_sha256"]:
            raise ValueError("field evolution chain is broken")
    return {
        "status": receipt["status"],
        "content_sha256": actual,
        "window_count": len(windows),
        "initial_program_sha256": receipt["initial_program"]["program_sha256"],
        "final_program_sha256": receipt["final_program"]["program_sha256"],
        "program_changed": receipt["initial_program"]["program_sha256"] != receipt["final_program"]["program_sha256"],
        "field_changed": receipt["field_changed"],
    }


__all__ = ["LONG_FOUNDRY_SCHEMA", "run_long_foundry", "verify_long_foundry_receipt"]
