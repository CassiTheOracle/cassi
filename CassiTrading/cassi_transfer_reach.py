"""Matched policy-level field-reach arms on heterogeneous transfer targets."""

from __future__ import annotations

from statistics import mean
from typing import Any, Mapping, Sequence

from cassi_market_contracts import Event, digest_value
from cassi_trading_foundry import MarketBar, RefinementField
from cassi_transfer import CrossInstrumentTransferCampaign, TransferConfig
from cassi_world_model import MarketWorldModel


TRANSFER_REACH_SCHEMA = "cassi.market-transfer-reach.v1"


def _target_row(
    campaign: CrossInstrumentTransferCampaign,
    bars: Sequence[MarketBar],
    events: Sequence[Event],
    *,
    instrument: str,
    start: int,
    arm: str,
    field: RefinementField,
) -> dict[str, Any]:
    config = campaign.config
    decision_index = start + config.train_bars - 1
    outcome_index = decision_index + config.horizon_bars
    world = MarketWorldModel()
    world.update(events[: decision_index + 1])
    context = world.observations[-1]
    readout = field.predict_program(config.field_signature, config.program_id)
    strict_authority = readout.get("status") == "supported" and readout.get("outcome") == "promote"
    trend = float(context.value["trend"])
    direction = 0.0 if not strict_authority else (1.0 if trend >= 0.0 else -1.0)
    gross_return = bars[outcome_index].close / bars[decision_index].close - 1.0
    realized_return = direction * gross_return - abs(direction) * config.cost_bps / 10_000.0
    before = field.fingerprint()
    return {
        "instrument": instrument,
        "arm": arm,
        "start_index": start,
        "decision_index": decision_index,
        "outcome_index": outcome_index,
        "decision_available_at": events[decision_index].available_at,
        "outcome_observed_at": events[outcome_index].available_at,
        "decision_event_id": events[decision_index].event_id,
        "outcome_event_id": events[outcome_index].event_id,
        "prediction_input_event_ids": list(context.input_event_ids),
        "regime_id": world.active_regime.regime_id if world.active_regime else "regime:warming",
        "field_readout": readout,
        "strict_promote_authority": strict_authority,
        "direction": direction,
        "realized_return": realized_return,
        "field_before_sha256": before,
        "field_after_sha256": field.fingerprint(),
    }


def run_transfer_reach_matrix(
    bars_by_instrument: Mapping[str, Sequence[MarketBar]],
    *,
    config: TransferConfig | None = None,
    source_manifest: Mapping[str, Any] | None = None,
    source_instruments: Sequence[str] | None = None,
    target_instruments: Sequence[str] | None = None,
    record_source_field_vectors: bool = False,
    source_repeats: int = 1,
) -> dict[str, Any]:
    """Train selected sources, then compare selected target policy arms."""
    campaign = CrossInstrumentTransferCampaign(config or TransferConfig())
    if isinstance(source_repeats, bool) or not isinstance(source_repeats, int) or not 1 <= source_repeats <= 4:
        raise ValueError("source_repeats must be an integer in [1, 4]")
    events_by_instrument = campaign._events(bars_by_instrument)
    available = set(events_by_instrument)
    source_ids = tuple(sorted(source_instruments or available))
    target_ids = tuple(sorted(target_instruments or available))
    if not source_ids or not target_ids:
        raise ValueError("source and target instrument selections cannot be empty")
    if not set(source_ids).issubset(available) or not set(target_ids).issubset(available):
        raise ValueError("source and target selections must be present in bars_by_instrument")
    seed_field = RefinementField()
    seed_checkpoint = seed_field.checkpoint_bytes()
    train_starts = tuple(index * campaign.config.step_bars for index in range(campaign.config.source_windows))
    target_starts = campaign.config.resolved_target_starts()
    cells: list[dict[str, Any]] = []
    for source in source_ids:
        source_field = RefinementField.restore(seed_checkpoint)
        source_rows = []
        for start in train_starts:
            row = campaign._row(
                bars_by_instrument[source],
                events_by_instrument[source],
                instrument=source,
                start=start,
                arm=f"source:{source}",
                field=source_field,
                adaptive=True,
                repeats=source_repeats,
            )
            if record_source_field_vectors:
                row["field_state_vector"] = list(source_field.state_vector())
            source_rows.append(row)
        source_field_checkpoint = source_field.checkpoint_bytes()
        source_field_sha256 = source_field.fingerprint()
        source_field_readout = source_field.predict_program(
            campaign.config.field_signature,
            campaign.config.program_id,
        )
        source_strict_promote_authority = (
            source_field_readout.get("status") == "supported"
            and source_field_readout.get("outcome") == "promote"
        )
        for target in target_ids:
            native = RefinementField.restore(source_field_checkpoint)
            lesion = RefinementField()
            supported = RefinementField()
            supported.learn_program(
                campaign.config.field_signature,
                campaign.config.program_id,
                "promote",
                repeats=1,
            )
            target_arms = {
                "native": [
                    _target_row(
                        campaign,
                        bars_by_instrument[target],
                        events_by_instrument[target],
                        instrument=target,
                        start=start,
                        arm=f"native:{source}->{target}",
                        field=native,
                    )
                    for start in target_starts
                ],
                "lesion": [
                    _target_row(
                        campaign,
                        bars_by_instrument[target],
                        events_by_instrument[target],
                        instrument=target,
                        start=start,
                        arm=f"lesion:{source}->{target}",
                        field=lesion,
                    )
                    for start in target_starts
                ],
                "supported-control": [
                    _target_row(
                        campaign,
                        bars_by_instrument[target],
                        events_by_instrument[target],
                        instrument=target,
                        start=start,
                        arm=f"supported-control:{source}->{target}",
                        field=supported,
                    )
                    for start in target_starts
                ],
            }
            cells.append(
                {
                    "source_instrument": source,
                    "target_instrument": target,
                    "source_training": source_rows,
                    "source_field_sha256": source_field_sha256,
                    "source_field_readout": source_field_readout,
                    "source_strict_promote_authority": source_strict_promote_authority,
                    "target_arms": target_arms,
                    "target_field_stable": {
                        name: all(row["field_before_sha256"] == row["field_after_sha256"] for row in rows)
                        for name, rows in target_arms.items()
                    },
                    "mean_realized_return": {
                        name: mean(row["realized_return"] for row in rows)
                        for name, rows in target_arms.items()
                    },
                }
            )
    body: dict[str, Any] = {
        "schema": TRANSFER_REACH_SCHEMA,
        "config": campaign.config.as_dict(),
        "instruments": sorted(events_by_instrument),
        "source_repeats": source_repeats,
        "source_instruments": list(source_ids),
        "target_instruments": list(target_ids),
        "event_roots": {
            instrument: digest_value([event.as_dict() for event in events])
            for instrument, events in events_by_instrument.items()
        },
        "matched_source_starts": list(train_starts),
        "matched_target_starts": list(target_starts),
        "decision_rule": "status=supported AND outcome=promote",
        "cells": cells,
    }
    if source_manifest is not None:
        body["source_manifest"] = dict(source_manifest)
    body["content_sha256"] = digest_value(body)
    return body


__all__ = ["TRANSFER_REACH_SCHEMA", "run_transfer_reach_matrix"]
