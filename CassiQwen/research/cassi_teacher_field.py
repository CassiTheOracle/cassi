"""Field-owned control boundary for the offline Qwen teacher."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_qwen_workbench import CassiFieldWorkMemory


TEACHER_OBSERVATION_SCHEMA = "cassi.teacher.field-observation.v1"
TEACHER_ACTION_SCHEMA = "cassi.teacher.field-action.v1"
TEACHER_CONTROL_RECEIPT_SCHEMA = "cassi.teacher.field-control-receipt.v1"
_MAX_CANDIDATES = 4
_MAX_REASONING_CHARS = 8_192
_MAX_COMPLETION_TOKENS = 512


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _bounded_int(value: Any, label: str, *, minimum: int = 0, maximum: int = 1_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer in [{minimum}, {maximum}]")
    return int(value)


def _bounded_text(value: Any, label: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise ValueError(f"{label} must be bounded nonempty text")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _canonical_descriptors(
    descriptors: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    if isinstance(descriptors, (str, bytes)) or not 1 <= len(descriptors) <= _MAX_CANDIDATES:
        raise ValueError("teacher candidate descriptors must contain one to four rows")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in descriptors:
        if not isinstance(raw, Mapping):
            raise ValueError("teacher candidate descriptor must be an object")
        candidate_id = _bounded_text(raw.get("candidate_id"), "candidate_id")
        if candidate_id in seen:
            raise ValueError("teacher candidate identity is duplicated")
        seen.add(candidate_id)
        task_id = _bounded_text(raw.get("task_id"), "task_id")
        candidate_sha256 = _digest(raw.get("candidate_sha256"), "candidate_sha256")
        candidate_steps = _bounded_int(
            raw.get("candidate_steps"), "candidate_steps", minimum=1
        )
        status = _bounded_text(raw.get("status"), "status")
        improved = raw.get("improved")
        if not isinstance(improved, bool):
            raise ValueError("candidate improved flag must be boolean")
        origin = raw.get("candidate_origin", "verified_pool")
        if origin not in {"verified_pool", "model_novel"}:
            raise ValueError("candidate origin is unsupported")
        normalized.append(
            {
                "candidate_id": candidate_id,
                "candidate_origin": origin,
                "candidate_sha256": candidate_sha256,
                "candidate_steps": candidate_steps,
                "improved": improved,
                "status": status,
                "task_id": task_id,
            }
        )
    return tuple(normalized)
def _thinking_capability(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {
            "answer_channel_viable": True,
            "flag_effective": True,
            "probe_max_tokens": 0,
        }
    if not isinstance(value, Mapping) or set(value) != {
        "answer_channel_viable",
        "flag_effective",
        "probe_max_tokens",
    }:
        raise ValueError("teacher thinking capability keys are invalid")
    if not isinstance(value["answer_channel_viable"], bool) or not isinstance(
        value["flag_effective"], bool
    ):
        raise ValueError("teacher thinking capability booleans are invalid")
    return {
        "answer_channel_viable": bool(value["answer_channel_viable"]),
        "flag_effective": bool(value["flag_effective"]),
        "probe_max_tokens": _bounded_int(
            value["probe_max_tokens"],
            "teacher capability probe budget",
            maximum=512,
        ),
    }


def _state_sha(memory: CassiFieldWorkMemory) -> str:
    value = memory.regional_field_receipt().get("field_state_sha256")
    return _digest(value, "regional field state")


class TeacherFieldController:
    """One bounded field action before and one outcome after each teacher call."""

    def __init__(
        self,
        memory: CassiFieldWorkMemory,
        *,
        run_id: str,
        field_off: bool = False,
    ) -> None:
        self.memory = memory
        self.run_id = _bounded_text(run_id, "run_id")
        self.field_off = bool(field_off)

    def _operation_id(self, kind: str, payload: Mapping[str, Any]) -> str:
        return f"teacher-field:{self.run_id}:{kind}:{_sha(payload)[:24]}"

    @staticmethod
    def _promotable(descriptors: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        return [
            row
            for row in descriptors
            if row.get("status") == "PASS" and row.get("improved") is True
        ]

    def _field_off_action(
        self,
        descriptors: Sequence[Mapping[str, Any]],
        *,
        planned_edit_id: str,
        thinking_max_tokens: int,
    ) -> Mapping[str, Any] | None:
        promotable = self._promotable(descriptors)
        selected = next(
            (row for row in promotable if row["candidate_id"] == planned_edit_id),
            promotable[0] if promotable else None,
        )
        if selected is None:
            return None
        core = {
            "candidate_id": selected["candidate_id"],
            "candidate_sha256": selected["candidate_sha256"],
            "edit_id": selected["candidate_id"],
            "task_id": selected["task_id"],
            "proposal_budget": len(promotable),
            "thinking": {
                "enabled": False,
                "effort_code": "field-off",
                "max_tokens": 0,
            },
            "predecessor_field_sha256": None,
        }
        return {"action_id": _sha(core), "schema": TEACHER_ACTION_SCHEMA, **core}
    def begin(
        self,
        *,
        generation: int,
        attempt: int,
        previous_source_sha256: str,
        candidate_descriptors: Sequence[Mapping[str, Any]],
        planned_edit_id: str,
        thinking_max_tokens: int = 256,
        thinking_capability: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        generation = _bounded_int(generation, "generation", maximum=1_000_000)
        attempt = _bounded_int(attempt, "attempt", maximum=1_000_000)
        previous_source_sha256 = _digest(previous_source_sha256, "previous source")
        planned_edit_id = _bounded_text(planned_edit_id, "planned edit")
        thinking_max_tokens = _bounded_int(
            thinking_max_tokens,
            "thinking token bound",
            minimum=1,
            maximum=_MAX_COMPLETION_TOKENS,
        )
        capability = _thinking_capability(thinking_capability)
        descriptors = _canonical_descriptors(candidate_descriptors)
        before = _state_sha(self.memory) if not self.field_off else None
        if self.field_off:
            action = self._field_off_action(
                descriptors,
                planned_edit_id=planned_edit_id,
                thinking_max_tokens=thinking_max_tokens,
            )
            if action is None:
                raise RuntimeError("field-off comparator found no promotable candidate")
            return {
                "schema": TEACHER_CONTROL_RECEIPT_SCHEMA,
                "mode": "field-off",
                "generation": generation,
                "attempt": attempt,
                "previous_source_sha256": previous_source_sha256,
                "candidate_descriptors_sha256": _sha(descriptors),
                "thinking_capability": capability,
                "field_state_in_sha256": None,
                "observation": None,
                "action": dict(action),
                "action_operation_id": None,
                "field_state_out_sha256": None,
            }

        observation_payload = {
            "candidate_descriptors_sha256": _sha(descriptors),
            "generation": generation,
            "previous_source_sha256": previous_source_sha256,
            "thinking_capability": capability,
        }
        observation_operation_id = self._operation_id(
            "request", {"generation": generation, "attempt": attempt, **observation_payload}
        )
        observation = self.memory.semantic(
            {
                "operation": "observe",
                "operation_id": observation_operation_id,
                "delivery_id": observation_operation_id,
                "event_id": f"{observation_operation_id}:event",
                "frame": "cassi-teacher-field-v1",
                "observations": [
                    {
                        "subject": "teacher-control:request",
                        "value": observation_payload,
                    }
                ],
                "receipt": {
                    "clock_domain": "teacher-field-logical",
                    "time": float(1 + generation * 2 + attempt),
                    "uncertainty": 0.0,
                },
                "source": {
                    "kind": "offline-teacher-control",
                    "run_id": self.run_id,
                    "receipt_schema": TEACHER_OBSERVATION_SCHEMA,
                    "generation": generation,
                    "attempt": attempt,
                },
            },
            operation_label=f"teacher-field:request:{generation}:{attempt}",
        )
        after_observation = _state_sha(self.memory)
        control_payload = {
            "operation": "teacher-control",
            "operation_id": self._operation_id(
                "action",
                {
                    "generation": generation,
                    "attempt": attempt,
                    "descriptors": descriptors,
                    "thinking_capability": capability,
                },
            ),
            "candidate_descriptors": list(descriptors),
            "predecessor_field_sha256": after_observation,
            "thinking_capability": capability,
            "thinking_max_tokens": thinking_max_tokens,
        }
        control = self.memory.semantic(
            control_payload,
            operation_label=f"teacher-field:action:{generation}:{attempt}",
        )
        result = control.get("result")
        if not isinstance(result, Mapping):
            raise RuntimeError("teacher-control returned no semantic result")
        action = result.get("action")
        if not isinstance(action, Mapping):
            raise RuntimeError(f"teacher-control abstained: {result.get('abstain_reason')}")
        selected_id = action.get("candidate_id")
        selected = next((row for row in descriptors if row["candidate_id"] == selected_id), None)
        if selected is None:
            raise RuntimeError("teacher-control selected a candidate outside its request")
        if action.get("task_id") != selected["task_id"] or action.get("edit_id") != selected_id:
            raise RuntimeError("teacher-control action identity diverged from its candidate")
        after_control = _state_sha(self.memory)
        return {
            "schema": TEACHER_CONTROL_RECEIPT_SCHEMA,
            "mode": "field",
            "generation": generation,
            "attempt": attempt,
            "previous_source_sha256": previous_source_sha256,
            "candidate_descriptors_sha256": _sha(descriptors),
            "thinking_capability": capability,
            "field_state_in_sha256": before,
            "observation": observation,
            "observation_operation_id": observation_operation_id,
            "observation_field_state_out_sha256": after_observation,
            "action": dict(action),
            "action_operation_id": control_payload["operation_id"],
            "action_result": dict(result),
            "field_state_out_sha256": after_control,
        }

    def observe_outcome(
        self,
        begin_receipt: Mapping[str, Any],
        *,
        status: str,
        candidate_origin: str,
        candidate_sha256: str,
        task_id: str,
        candidate_steps: int,
        original_steps: int,
        reasoning_chars: int,
        completion_tokens: int,
        thinking_requested: bool,
        thinking_effective: bool,
    ) -> Mapping[str, Any]:
        if begin_receipt.get("mode") != "field":
            return {
                "schema": TEACHER_CONTROL_RECEIPT_SCHEMA,
                "mode": begin_receipt.get("mode"),
                "status": "not-applicable",
                "field_state_in_sha256": None,
                "field_state_out_sha256": None,
            }
        before = _state_sha(self.memory)
        expected = begin_receipt.get("field_state_out_sha256")
        if before != expected:
            raise RuntimeError("teacher outcome predecessor does not match field action successor")
        generation = _bounded_int(begin_receipt.get("generation"), "generation")
        attempt = _bounded_int(begin_receipt.get("attempt"), "attempt")
        outcome = {
            "candidate_origin": _bounded_text(candidate_origin, "candidate origin"),
            "candidate_sha256": _digest(candidate_sha256, "candidate source"),
            "candidate_steps": _bounded_int(candidate_steps, "candidate steps", minimum=1),
            "completion_tokens": _bounded_int(
                completion_tokens, "completion tokens", maximum=_MAX_COMPLETION_TOKENS
            ),
            "improved_steps": _bounded_int(
                original_steps - candidate_steps, "improved steps", minimum=-1_000_000
            ),
            "reasoning_chars": _bounded_int(
                reasoning_chars, "reasoning characters", maximum=_MAX_REASONING_CHARS
            ),
            "status": _bounded_text(status, "outcome status"),
            "task_id": _bounded_text(task_id, "task id"),
            "thinking_effective": bool(thinking_effective),
            "thinking_requested": bool(thinking_requested),
        }
        operation_id = self._operation_id(
            "outcome", {"generation": generation, "attempt": attempt, **outcome}
        )
        result = self.memory.semantic(
            {
                "operation": "observe",
                "operation_id": operation_id,
                "delivery_id": operation_id,
                "event_id": f"{operation_id}:event",
                "frame": "cassi-teacher-field-v1",
                "observations": [
                    {"subject": "teacher-control:outcome", "value": outcome}
                ],
                "receipt": {
                    "clock_domain": "teacher-field-logical",
                    "time": float(2 + generation * 2 + attempt),
                    "uncertainty": 0.0,
                },
                "source": {
                    "kind": "offline-teacher-outcome",
                    "run_id": self.run_id,
                    "receipt_schema": TEACHER_OBSERVATION_SCHEMA,
                    "generation": generation,
                    "attempt": attempt,
                },
            },
            operation_label=f"teacher-field:outcome:{generation}:{attempt}",
        )
        after = _state_sha(self.memory)
        return {
            "schema": TEACHER_CONTROL_RECEIPT_SCHEMA,
            "mode": "field",
            "status": "observed",
            "generation": generation,
            "attempt": attempt,
            "operation_id": operation_id,
            "outcome": outcome,
            "field_state_in_sha256": before,
            "field_state_out_sha256": after,
            "semantic_result": result.get("result"),
        }


__all__ = [
    "TEACHER_ACTION_SCHEMA",
    "TEACHER_CONTROL_RECEIPT_SCHEMA",
    "TEACHER_OBSERVATION_SCHEMA",
    "TeacherFieldController",
]
