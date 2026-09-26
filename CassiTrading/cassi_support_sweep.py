"""Bounded sweep for the source-learning support threshold."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from cassi_market_contracts import digest_value
from cassi_trading_foundry import MarketBar, RefinementField
from cassi_transfer import CrossInstrumentTransferCampaign, TransferConfig


SUPPORT_SWEEP_SCHEMA = "cassi.transfer-support-sweep.v1"


def run_support_sweep(
    bars_by_instrument: Mapping[str, Sequence[MarketBar]],
    *,
    base_config: TransferConfig | None = None,
    max_source_windows: int = 8,
    source_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Measure native field readout status after bounded source training prefixes."""
    if isinstance(max_source_windows, bool) or not isinstance(max_source_windows, int) or not 1 <= max_source_windows <= 8:
        raise ValueError("max_source_windows must be in [1, 8]")
    base = base_config or TransferConfig(step_bars=32, target_start=32, target_windows=1)
    seed = RefinementField()
    seed_checkpoint = seed.checkpoint_bytes()
    instruments: dict[str, list[dict[str, Any]]] = {}
    for instrument in sorted(bars_by_instrument):
        rows: list[dict[str, Any]] = []
        for window_count in range(1, max_source_windows + 1):
            config = TransferConfig(
                train_bars=base.train_bars,
                horizon_bars=base.horizon_bars,
                step_bars=base.step_bars,
                source_windows=window_count,
                target_start=base.target_start,
                target_windows=base.target_windows,
                target_starts=base.target_starts,
                cost_bps=base.cost_bps,
                program_id=base.program_id,
                field_signature=base.field_signature,
            )
            campaign = CrossInstrumentTransferCampaign(config)
            events_by_instrument = campaign._events(bars_by_instrument)
            field = RefinementField.restore(seed_checkpoint)
            before = field.fingerprint()
            source_rows = [
                campaign._row(
                    bars_by_instrument[instrument],
                    events_by_instrument[instrument],
                    instrument=instrument,
                    start=index * config.step_bars,
                    arm=f"support-sweep:{instrument}:{window_count}",
                    field=field,
                    adaptive=True,
                )
                for index in range(window_count)
            ]
            readout = field.predict_program(config.field_signature, config.program_id)
            rows.append(
                {
                    "source_instrument": instrument,
                    "source_windows": window_count,
                    "source_starts": [row["start_index"] for row in source_rows],
                    "field_before_sha256": before,
                    "field_after_sha256": field.fingerprint(),
                    "readout": readout,
                    "strict_promote_authority": readout.get("status") == "supported"
                    and readout.get("outcome") == "promote",
                }
            )
        instruments[instrument] = rows
    body: dict[str, Any] = {
        "schema": SUPPORT_SWEEP_SCHEMA,
        "base_config": base.as_dict(),
        "max_source_windows": max_source_windows,
        "instruments": instruments,
        "controls": {
            "window_prefixes_are_chronological": True,
            "max_source_windows_bound": 8,
            "decision_rule": "status=supported AND outcome=promote",
        },
    }
    if source_manifest is not None:
        body["source_manifest"] = dict(source_manifest)
    body["content_sha256"] = digest_value(body)
    return body


__all__ = ["SUPPORT_SWEEP_SCHEMA", "run_support_sweep"]
