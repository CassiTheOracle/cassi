"""Risk-aware portfolio and execution-intent policy contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from cassi_market_contracts import Authority, Policy, canonical_bytes, digest_value


POLICY_DECISION_SCHEMA = "cassi.market-policy-decision.v1"


class PolicyError(ValueError):
    """A policy input or constrained decision is invalid."""


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{name} must be nonempty text")
    return value


def _finite(name: str, value: Any, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PolicyError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise PolicyError(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise PolicyError(f"{name} must be >= {minimum}")
    if maximum is not None and result > maximum:
        raise PolicyError(f"{name} must be <= {maximum}")
    return result


def _scale(values: Mapping[str, float], factor: float) -> dict[str, float]:
    return {key: value * factor for key, value in values.items()}


@dataclass(frozen=True, slots=True)
class PortfolioPolicyConfig:
    max_position: float = 1.0
    max_gross_exposure: float = 1.0
    max_net_exposure: float = 1.0
    max_turnover: float = 0.25
    risk_budget_per_position: float = 0.25
    minimum_risk: float = 1.0e-6
    minimum_order: float = 1.0e-6
    flat_on_abstain: bool = False

    def __post_init__(self) -> None:
        for name in (
            "max_position",
            "max_gross_exposure",
            "max_net_exposure",
            "max_turnover",
            "risk_budget_per_position",
            "minimum_order",
        ):
            _finite(name, getattr(self, name), minimum=0.0)
        _finite("minimum_risk", self.minimum_risk, minimum=1.0e-12)
        if self.max_net_exposure > self.max_gross_exposure:
            raise PolicyError("max_net_exposure cannot exceed max_gross_exposure")
        if self.max_position > self.max_gross_exposure:
            raise PolicyError("max_position cannot exceed max_gross_exposure")

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_position": self.max_position,
            "max_gross_exposure": self.max_gross_exposure,
            "max_net_exposure": self.max_net_exposure,
            "max_turnover": self.max_turnover,
            "risk_budget_per_position": self.risk_budget_per_position,
            "minimum_risk": self.minimum_risk,
            "minimum_order": self.minimum_order,
            "flat_on_abstain": self.flat_on_abstain,
        }


@dataclass(frozen=True, slots=True)
class PortfolioState:
    equity: float
    positions: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _finite("equity", self.equity, minimum=1.0e-12)
        if not isinstance(self.positions, Mapping):
            raise PolicyError("positions must be an object")
        for instrument, position in self.positions.items():
            _text("position instrument", instrument)
            _finite(f"position.{instrument}", position)

    def as_dict(self) -> dict[str, Any]:
        return {"equity": self.equity, "positions": dict(self.positions)}


@dataclass(frozen=True, slots=True)
class ProgramSignal:
    signal_id: str
    program_id: str
    instrument: str
    regime_id: str
    direction: float
    expected_edge: float
    expected_risk: float
    applicability_status: str
    event_id: str
    observation_id: str
    available_at: str
    support_roots: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "signal_id",
            "program_id",
            "instrument",
            "regime_id",
            "applicability_status",
            "event_id",
            "observation_id",
            "available_at",
        ):
            _text(name, getattr(self, name))
        _finite("direction", self.direction, minimum=-1.0, maximum=1.0)
        _finite("expected_edge", self.expected_edge, minimum=0.0)
        _finite("expected_risk", self.expected_risk, minimum=0.0)
        if self.applicability_status not in {"evaluated", "inapplicable", "error", "abstain"}:
            raise PolicyError(f"unknown applicability status: {self.applicability_status}")
        if self.applicability_status == "evaluated" and self.expected_risk <= 0.0:
            raise PolicyError("evaluated signal must declare positive expected risk")
        for root in self.support_roots:
            _text("support root", root)

    @property
    def applicable(self) -> bool:
        return self.applicability_status == "evaluated"

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "program_id": self.program_id,
            "instrument": self.instrument,
            "regime_id": self.regime_id,
            "direction": self.direction,
            "expected_edge": self.expected_edge,
            "expected_risk": self.expected_risk,
            "applicability_status": self.applicability_status,
            "event_id": self.event_id,
            "observation_id": self.observation_id,
            "available_at": self.available_at,
            "support_roots": list(self.support_roots),
        }


@dataclass(frozen=True, slots=True)
class OrderIntent:
    operation_id: str
    instrument: str
    side: str
    quantity: float
    target_exposure: float
    mode: str
    status: str
    authority_generation: str

    def __post_init__(self) -> None:
        for name in ("operation_id", "instrument", "side", "mode", "status", "authority_generation"):
            _text(name, getattr(self, name))
        if self.side not in {"buy", "sell"}:
            raise PolicyError("order side must be buy or sell")
        _finite("quantity", self.quantity, minimum=0.0)
        _finite("target_exposure", self.target_exposure)
        if self.mode not in {"research", "shadow", "authorized"}:
            raise PolicyError(f"unknown order mode: {self.mode}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "instrument": self.instrument,
            "side": self.side,
            "quantity": self.quantity,
            "target_exposure": self.target_exposure,
            "mode": self.mode,
            "status": self.status,
            "authority_generation": self.authority_generation,
        }


@dataclass(frozen=True, slots=True)
class Abstention:
    instrument: str
    reason: str
    signal_ids: tuple[str, ...]
    retained_position: float

    def __post_init__(self) -> None:
        _text("abstention instrument", self.instrument)
        _text("abstention reason", self.reason)
        _finite("retained_position", self.retained_position)

    def as_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "reason": self.reason,
            "signal_ids": list(self.signal_ids),
            "retained_position": self.retained_position,
        }


class PortfolioController:
    """Convert applicable program signals into constrained target exposures."""

    def __init__(
        self,
        *,
        policy_id: str,
        config: PortfolioPolicyConfig | None = None,
        support_roots: Sequence[str] = (),
    ) -> None:
        self.policy_id = _text("policy_id", policy_id)
        self.config = config or PortfolioPolicyConfig()
        self.support_roots = tuple(_text("support root", root) for root in support_roots)

    def _policy_contract(self, signals: Sequence[ProgramSignal]) -> Policy:
        return Policy(
            policy_id=self.policy_id,
            regime_bindings={signal.instrument: signal.regime_id for signal in signals},
            program_bindings={signal.instrument: signal.program_id for signal in signals},
            portfolio_controller=self.config.as_dict(),
            execution_controller={"external_effect": "intent-only"},
            abstention_rules=("inapplicable-program", "risk-constraint", "no-applicable-signal"),
            risk_limits={
                "max_position": self.config.max_position,
                "max_gross_exposure": self.config.max_gross_exposure,
                "max_net_exposure": self.config.max_net_exposure,
                "max_turnover": self.config.max_turnover,
            },
            applicability={"requires_status": "evaluated", "requires_positive_risk": True},
            support_roots=self.support_roots,
        )

    def decide(
        self,
        state: PortfolioState,
        signals: Sequence[ProgramSignal],
        *,
        authority: Authority,
        operation_id: str,
    ) -> dict[str, Any]:
        _text("operation_id", operation_id)
        if not isinstance(authority, Authority):
            raise PolicyError("authority must be an Authority contract")
        ordered_signals = tuple(signals)
        by_instrument: dict[str, list[ProgramSignal]] = {}
        abstentions: list[Abstention] = []
        for signal in ordered_signals:
            by_instrument.setdefault(signal.instrument, []).append(signal)
            if not signal.applicable:
                abstentions.append(
                    Abstention(
                        instrument=signal.instrument,
                        reason=f"program-{signal.applicability_status}",
                        signal_ids=(signal.signal_id,),
                        retained_position=float(state.positions.get(signal.instrument, 0.0)),
                    )
                )
        raw_targets: dict[str, float] = dict(state.positions)
        constraints_applied: list[str] = []
        for instrument, instrument_signals in by_instrument.items():
            applicable = [signal for signal in instrument_signals if signal.applicable]
            if not applicable:
                if self.config.flat_on_abstain and instrument in raw_targets:
                    raw_targets[instrument] = 0.0
                    constraints_applied.append(f"flat-on-abstain:{instrument}")
                else:
                    abstentions.append(
                        Abstention(
                            instrument=instrument,
                            reason="no-applicable-signal",
                            signal_ids=tuple(signal.signal_id for signal in instrument_signals),
                            retained_position=float(state.positions.get(instrument, 0.0)),
                        )
                    )
                continue
            targets = []
            for signal in applicable:
                score = signal.direction * signal.expected_edge / max(signal.expected_risk, self.config.minimum_risk)
                target = max(-self.config.max_position, min(self.config.max_position, score * self.config.risk_budget_per_position))
                targets.append(target)
            raw_targets[instrument] = sum(targets) / len(targets)
        gross = sum(abs(value) for value in raw_targets.values())
        if gross > self.config.max_gross_exposure and gross > 0.0:
            raw_targets = _scale(raw_targets, self.config.max_gross_exposure / gross)
            constraints_applied.append("max-gross-exposure")
        net = sum(raw_targets.values())
        if abs(net) > self.config.max_net_exposure and abs(net) > 0.0:
            raw_targets = _scale(raw_targets, self.config.max_net_exposure / abs(net))
            constraints_applied.append("max-net-exposure")
        deltas = {instrument: raw_targets.get(instrument, 0.0) - float(state.positions.get(instrument, 0.0)) for instrument in raw_targets}
        turnover = sum(abs(value) for value in deltas.values())
        if turnover > self.config.max_turnover and turnover > 0.0:
            deltas = _scale(deltas, self.config.max_turnover / turnover)
            constraints_applied.append("max-turnover")
        target_exposures = {instrument: float(state.positions.get(instrument, 0.0)) + deltas.get(instrument, 0.0) for instrument in raw_targets}
        intents: list[OrderIntent] = []
        mode_status = {
            "research": "hypothetical",
            "shadow": "shadow-pending",
            "authorized": "authorized-pending-execution",
        }[authority.mode]
        for instrument in sorted(target_exposures):
            delta = target_exposures[instrument] - float(state.positions.get(instrument, 0.0))
            if abs(delta) < self.config.minimum_order:
                continue
            intents.append(
                OrderIntent(
                    operation_id=f"{operation_id}:{instrument}",
                    instrument=instrument,
                    side="buy" if delta > 0.0 else "sell",
                    quantity=abs(delta),
                    target_exposure=target_exposures[instrument],
                    mode=authority.mode,
                    status=mode_status,
                    authority_generation=authority.permission_generation,
                )
            )
        policy = self._policy_contract(ordered_signals)
        body: dict[str, Any] = {
            "schema": POLICY_DECISION_SCHEMA,
            "operation_id": operation_id,
            "authority": authority.as_dict(),
            "policy": policy.as_dict(),
            "policy_sha256": policy.content_sha256,
            "state": state.as_dict(),
            "signals": [signal.as_dict() for signal in ordered_signals],
            "raw_targets": raw_targets,
            "target_exposures": target_exposures,
            "constraints_applied": constraints_applied,
            "orders": [intent.as_dict() for intent in intents],
            "abstentions": [abstention.as_dict() for abstention in abstentions],
            "external_effect": "none; intent-only",
        }
        body["content_sha256"] = digest_value(body)
        return body


__all__ = [
    "Abstention",
    "OrderIntent",
    "POLICY_DECISION_SCHEMA",
    "PolicyError",
    "PortfolioController",
    "PortfolioPolicyConfig",
    "PortfolioState",
    "ProgramSignal",
]
