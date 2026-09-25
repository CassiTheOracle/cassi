"""Controlled field-readout reach measurements for transfer experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cassi_market_contracts import digest_value
from cassi_trading_foundry import RefinementField


FIELD_REACH_SCHEMA = "cassi.field-readout-reach.v1"


@dataclass(frozen=True, slots=True)
class FieldReachConfig:
    field_signature: str = "edge"
    program_id: str = "synthesized-transfer-program"
    support_repeats: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.field_signature, str) or not self.field_signature.strip():
            raise ValueError("field_signature must be nonempty")
        if not isinstance(self.program_id, str) or not self.program_id.strip():
            raise ValueError("program_id must be nonempty")
        if isinstance(self.support_repeats, bool) or not isinstance(self.support_repeats, int):
            raise ValueError("support_repeats must be an integer")
        if not 1 <= self.support_repeats <= 4:
            raise ValueError("support_repeats must be in [1, 4]")

    def as_dict(self) -> dict[str, Any]:
        return {
            "field_signature": self.field_signature,
            "program_id": self.program_id,
            "support_repeats": self.support_repeats,
        }


def _arm(name: str, field: RefinementField, config: FieldReachConfig) -> dict[str, Any]:
    before = field.fingerprint()
    readout = field.predict_program(config.field_signature, config.program_id)
    strict_authority = readout.get("status") == "supported" and readout.get("outcome") == "promote"
    return {
        "arm": name,
        "field_before_sha256": before,
        "field_after_sha256": field.fingerprint(),
        "readout": readout,
        "strict_promote_authority": strict_authority,
    }


def run_field_reach_arms(field: RefinementField, config: FieldReachConfig | None = None) -> dict[str, Any]:
    """Compare native, zeroed-readout, and deliberately supported field arms."""
    config = config or FieldReachConfig()
    checkpoint = field.checkpoint_bytes()
    native = RefinementField.restore(checkpoint)
    lesion = RefinementField()
    supported = RefinementField.restore(checkpoint)
    supported.learn_program(
        config.field_signature,
        config.program_id,
        "promote",
        repeats=config.support_repeats,
    )
    arms = [
        _arm("native", native, config),
        _arm("lesion", lesion, config),
        _arm("supported-control", supported, config),
    ]
    body: dict[str, Any] = {
        "schema": FIELD_REACH_SCHEMA,
        "config": config.as_dict(),
        "input_field_sha256": field.fingerprint(),
        "arms": arms,
        "controls": {
            "lesion_is_seed_field": True,
            "supported_control_writes_promote": True,
            "decision_rule": "status=supported AND outcome=promote",
        },
    }
    body["content_sha256"] = digest_value(body)
    return body


__all__ = ["FIELD_REACH_SCHEMA", "FieldReachConfig", "run_field_reach_arms"]
