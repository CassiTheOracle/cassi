"""Bind synthesized programs to canonical market coordinates and regimes."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

_CASSIQWEN_ROOT = Path(__file__).resolve().parents[1] / "CassiQwen"
if str(_CASSIQWEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN_ROOT))
from cassi_market_contracts import DerivedObservation, Event, Program, canonical_bytes, digest_value
from cassi_python import execute_program
from cassi_world_model import WorldModelConfig, classify_coordinate_values


APPLICABILITY_SCHEMA = "cassi.market-program-applicability.v1"


class ApplicabilityError(ValueError):
    """A program cannot be safely bound to the requested market context."""


@dataclass(frozen=True, slots=True)
class MarketContext:
    event_id: str
    observation_id: str
    available_at: str
    regime_id: str
    coordinates: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in ("event_id", "observation_id", "available_at", "regime_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ApplicabilityError(f"{name} must be nonempty text")
        if not isinstance(self.coordinates, Mapping):
            raise ApplicabilityError("coordinates must be an object")
        canonical_bytes(dict(self.coordinates))

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "observation_id": self.observation_id,
            "available_at": self.available_at,
            "regime_id": self.regime_id,
            "coordinates": dict(self.coordinates),
        }


def contexts_from_market_observations(
    events: Sequence[Event],
    observations: Sequence[DerivedObservation],
    *,
    config: WorldModelConfig | None = None,
) -> tuple[MarketContext, ...]:
    """Create chronology-preserving contexts from event/coordinate pairs."""
    if len(events) != len(observations) or not events:
        raise ApplicabilityError("events and observations must be nonempty and equal length")
    world_config = config or WorldModelConfig()
    contexts: list[MarketContext] = []
    previous_available: str | None = None
    for event, observation in zip(events, observations):
        if not isinstance(event, Event) or not isinstance(observation, DerivedObservation):
            raise ApplicabilityError("context inputs must be canonical event and observation contracts")
        if event.event_id not in observation.input_event_ids:
            raise ApplicabilityError("coordinate observation does not include its current event")
        if previous_available is not None and event.available_at <= previous_available:
            raise ApplicabilityError("contexts must be strictly ordered by available_at")
        values = observation.value
        if not isinstance(values, Mapping):
            raise ApplicabilityError("coordinate observation value must be an object")
        regime_id = f"regime:{classify_coordinate_values(values, world_config)}"
        contexts.append(
            MarketContext(
                event_id=event.event_id,
                observation_id=observation.observation_id,
                available_at=event.available_at,
                regime_id=regime_id,
                coordinates=dict(values),
            )
        )
        previous_available = event.available_at
    return tuple(contexts)


@dataclass(frozen=True, slots=True)
class ProgramBinding:
    binding_id: str
    allowed_regimes: tuple[str, ...]
    parameter_map: Mapping[str, str]
    constants: Mapping[str, Any]
    require_ready: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.binding_id, str) or not self.binding_id.strip():
            raise ApplicabilityError("binding_id must be nonempty text")
        if not self.allowed_regimes or any(not isinstance(value, str) or not value.strip() for value in self.allowed_regimes):
            raise ApplicabilityError("allowed_regimes must contain regime IDs")
        if not isinstance(self.parameter_map, Mapping) or not isinstance(self.constants, Mapping):
            raise ApplicabilityError("binding maps must be objects")
        if set(self.parameter_map).intersection(self.constants):
            raise ApplicabilityError("a program parameter cannot be both mapped and constant")
        if any(not isinstance(key, str) or not isinstance(value, str) or not value.strip() for key, value in self.parameter_map.items()):
            raise ApplicabilityError("parameter_map must map text parameters to coordinate names")
        canonical_bytes(dict(self.constants))

    def applies(self, context: MarketContext) -> bool:
        if context.regime_id not in self.allowed_regimes:
            return False
        return not self.require_ready or context.coordinates.get("ready") == 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "allowed_regimes": list(self.allowed_regimes),
            "parameter_map": dict(self.parameter_map),
            "constants": dict(self.constants),
            "require_ready": self.require_ready,
        }


def program_from_contract_dict(value: Mapping[str, Any]) -> Program:
    """Rehydrate a serialized program contract without accepting extra behavior."""
    row = value.get("program", value)
    if not isinstance(row, Mapping):
        raise ApplicabilityError("program contract must be an object")
    try:
        return Program(
            program_id=str(row["program_id"]),
            parent_ids=tuple(str(item) for item in row["parent_ids"]),
            source=str(row["source"]),
            canonical_ast=dict(row["canonical_ast"]),
            typed_inputs=dict(row["typed_inputs"]),
            typed_outputs=dict(row["typed_outputs"]),
            guards=tuple(str(item) for item in row["guards"]),
            state_ports=dict(row["state_ports"]),
            resource_budget=dict(row["resource_budget"]),
            evidence_roots=tuple(str(item) for item in row["evidence_roots"]),
            skill_dependencies=tuple(str(item) for item in row["skill_dependencies"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ApplicabilityError("malformed program contract") from exc


class RegimeConditionedEvaluator:
    """Evaluate a program only where its declared market guard applies."""

    def evaluate(
        self,
        program: Program,
        binding: ProgramBinding,
        contexts: Sequence[MarketContext],
    ) -> dict[str, Any]:
        if not contexts:
            raise ApplicabilityError("applicability evaluation requires contexts")
        parameters = program.typed_inputs.get("parameters")
        if not isinstance(parameters, list) or any(not isinstance(item, str) for item in parameters):
            raise ApplicabilityError("program has no typed parameter list")
        covered = set(binding.parameter_map).union(binding.constants)
        if set(parameters) != covered:
            missing = sorted(set(parameters) - covered)
            extra = sorted(covered - set(parameters))
            raise ApplicabilityError(f"binding parameter closure mismatch: missing={missing}, extra={extra}")
        rows: list[dict[str, Any]] = []
        previous_available: str | None = None
        max_steps = int(program.resource_budget.get("max_steps", 10_000))
        max_call_depth = int(program.resource_budget.get("max_call_depth", 32))
        for context in contexts:
            if previous_available is not None and context.available_at <= previous_available:
                raise ApplicabilityError("applicability contexts must be chronological")
            previous_available = context.available_at
            base = {
                "event_id": context.event_id,
                "observation_id": context.observation_id,
                "available_at": context.available_at,
                "regime_id": context.regime_id,
            }
            if not binding.applies(context):
                rows.append({**base, "status": "inapplicable", "value": None})
                continue
            inputs: dict[str, Any] = dict(binding.constants)
            for parameter, coordinate in binding.parameter_map.items():
                if coordinate not in context.coordinates:
                    raise ApplicabilityError(f"coordinate {coordinate} is missing for parameter {parameter}")
                inputs[parameter] = context.coordinates[coordinate]
            try:
                result = execute_program(
                    program.canonical_ast,
                    inputs,
                    max_steps=max_steps,
                    max_call_depth=max_call_depth,
                )
                rows.append(
                    {
                        **base,
                        "status": "evaluated",
                        "inputs": inputs,
                        "value": result.value,
                        "steps": result.steps,
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        **base,
                        "status": "error",
                        "inputs": inputs,
                        "value": None,
                        "error": type(exc).__name__,
                    }
                )
        body: dict[str, Any] = {
            "schema": APPLICABILITY_SCHEMA,
            "program_id": program.program_id,
            "program_sha256": program.content_sha256,
            "binding": binding.as_dict(),
            "context_count": len(contexts),
            "evaluated_count": sum(row["status"] == "evaluated" for row in rows),
            "inapplicable_count": sum(row["status"] == "inapplicable" for row in rows),
            "error_count": sum(row["status"] == "error" for row in rows),
            "rows": rows,
        }
        body["content_sha256"] = digest_value(body)
        return body


__all__ = [
    "APPLICABILITY_SCHEMA",
    "ApplicabilityError",
    "MarketContext",
    "ProgramBinding",
    "RegimeConditionedEvaluator",
    "contexts_from_market_observations",
    "program_from_contract_dict",
]
