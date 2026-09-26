"""Prospective, field-owned causal acquisition over the raw-event Qi tensor.

This isolated v1 policy keeps ``QiFieldState.field`` as the only adaptive
persistent object.  It adds a strict decision protocol around the v2 raw-event
codec and field operations: deterministic exploration is reported as fixed
machinery, predictions are frozen before consequences, ordinary cold-start
acquisition is distinct from mismatch-gated conditional acquisition, and
consolidation requires a later reset-bounded prospective confirmation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import struct
import tempfile
from collections import deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

import torch

import cassi_raw_event_field as _raw
from cassi_raw_event_field import (
    AcquisitionProfile,
    CheckpointError,
    EventError,
    canonical_packet,
    decode_packet,
    encode_packet,
)


_OPERATOR_ID = "cassi.causal-predictive-bifurcation.v1"
_PROFILE_SCHEMA = "cassi.causal-acquisition-profile.v1"
_CHECKPOINT_SCHEMA = "cassi.causal-event-execution-checkpoint.v2"
_CHECKPOINT_MAGIC = b"CASSI-CAUSAL-EVENT-FIELD\x02"
_DECISION_SCHEMA = "cassi.causal-decision.v1"
_OUTCOME_SCHEMA = "cassi.causal-outcome-admission.v1"
_INTERVENTION_SCHEMA = "cassi.causal-relation-intervention.v1"
_POLICY_VALUES = {
    "mismatch-gated",
    "always-conditional",
    "unconditional-only",
}
_HISTORY_AUTO = object()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _packet_sha256(payload: bytes) -> str:
    return _sha256(canonical_packet(payload))




def _positive_int(name: str, value: Any, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [1, {maximum}]")
    return int(value)


@lru_cache(maxsize=1)
def _operator_source_sha256() -> str:
    return _sha256(Path(__file__).read_bytes())


def _default_acquisition_profile() -> AcquisitionProfile:
    return AcquisitionProfile(
        wave_width=1024,
        payload_limit=8,
    )


@dataclass(frozen=True, slots=True)
class CausalProfile:
    """Versioned fixed policy around one bounded raw-event Qi field."""

    acquisition: AcquisitionProfile = field(default_factory=_default_acquisition_profile)
    policy: str = "mismatch-gated"
    max_actions: int = 16
    max_depth: int = 3
    max_expansions: int = 64
    key_channels: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.acquisition, AcquisitionProfile):
            raise ValueError("acquisition must be an AcquisitionProfile")
        if self.policy not in _POLICY_VALUES:
            raise ValueError(f"policy must be one of {sorted(_POLICY_VALUES)}")
        object.__setattr__(
            self, "max_actions", _positive_int("max_actions", self.max_actions, maximum=64)
        )
        object.__setattr__(
            self, "max_depth", _positive_int("max_depth", self.max_depth, maximum=8)
        )
        object.__setattr__(
            self,
            "max_expansions",
            _positive_int("max_expansions", self.max_expansions, maximum=4096),
        )
        maximum_key_channels = max(1, self.acquisition.wave_width // 256)
        channels = (
            min(4, maximum_key_channels)
            if self.key_channels is None
            else _positive_int(
                "key_channels",
                self.key_channels,
                maximum=maximum_key_channels,
            )
        )
        object.__setattr__(self, "key_channels", channels)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": _PROFILE_SCHEMA,
            "operator_id": _OPERATOR_ID,
            "acquisition": self.acquisition.as_dict(),
            "policy": self.policy,
            "max_actions": self.max_actions,
            "max_depth": self.max_depth,
            "max_expansions": self.max_expansions,
            "key_channels": self.key_channels,
            "exploration": "canonical-episode-rotation-v1",
            "history": "immediately-preceding-reset-bounded-observation-v1",
            "readout": "conditional-supported-override-else-ordinary-v1",
            "promotion": "later-reset-bounded-prospective-confirmation-v1",
            "relation_allocation": "fixed-keyed-sparse-mask-v2",
        }

    @property
    def fingerprint(self) -> str:
        return _sha256(_canonical_json(self.as_dict()))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CausalProfile":
        if not isinstance(value, Mapping):
            raise ValueError("causal profile must be a mapping")
        payload = dict(value)
        fixed = {
            "schema": _PROFILE_SCHEMA,
            "operator_id": _OPERATOR_ID,
            "exploration": "canonical-episode-rotation-v1",
            "history": "immediately-preceding-reset-bounded-observation-v1",
            "readout": "conditional-supported-override-else-ordinary-v1",
            "promotion": "later-reset-bounded-prospective-confirmation-v1",
            "relation_allocation": "fixed-keyed-sparse-mask-v2",
        }
        for key, expected in fixed.items():
            if payload.pop(key, None) != expected:
                raise ValueError(f"causal profile {key} mismatch")
        expected_fields = {
            "acquisition",
            "policy",
            "max_actions",
            "max_depth",
            "max_expansions",
            "key_channels",
        }
        if set(payload) != expected_fields:
            raise ValueError("causal profile fields do not match the fixed schema")
        try:
            acquisition = AcquisitionProfile.from_dict(cast(Mapping[str, Any], payload.pop("acquisition")))
            profile = cls(acquisition=acquisition, **payload)
        except Exception as exc:
            raise ValueError(f"causal profile is invalid: {exc}") from exc
        if profile.as_dict() != dict(value):
            raise ValueError("causal profile materialization mismatch")
        return profile


class _CausalFieldKernel:
    """Causal-only Qi kernel built from explicit raw-field primitives.

    The raw learner remains the serializer and fixed Qi implementation, but its
    event ``apply``/``choose``/``plan`` surface is intentionally unreachable
    here.  All adaptive mutation is selected by :class:`CausalEventLearner`.
    """

    def __init__(
        self,
        profile: AcquisitionProfile,
        *,
        state: _raw.QiFieldState | None = None,
        key_channels: int,
    ) -> None:
        self._raw = _raw.RawEventLearner(profile, state=state)
        self._key_channels = key_channels

    @property
    def profile(self) -> AcquisitionProfile:
        return self._raw.profile

    def _state_ref(self) -> _raw.QiFieldState:
        return self._raw.state

    def _state_copy(self) -> _raw.QiFieldState:
        return _raw.QiFieldState(
            self._state_ref().field.detach().clone()
        )

    def _replace_state(self, value: _raw.QiFieldState) -> None:
        if not isinstance(value, _raw.QiFieldState):
            raise EventError("replacement state must be a QiFieldState")
        self._validate_field(value.field)
        self._raw.state = value

    def fingerprint(self) -> str:
        return self._raw.fingerprint()

    def snapshot(self) -> dict[str, Any]:
        return self._raw.snapshot()

    def checkpoint_bytes(self) -> bytes:
        return self._raw.checkpoint_bytes()

    def _validate_payload(
        self, payload: bytes | bytearray | memoryview
    ) -> bytes:
        return self._raw._validate_payload(payload)

    def _parts(self, field_value: torch.Tensor) -> torch.Tensor:
        return self._raw._parts(field_value)

    def _validate_field(self, field_value: torch.Tensor) -> None:
        self._raw._validate_field(field_value)

    def _set_differential(
        self,
        field_value: torch.Tensor,
        scale: int,
        delta_re: torch.Tensor,
        delta_im: torch.Tensor,
    ) -> None:
        self._raw._set_differential(
            field_value, scale, delta_re, delta_im
        )

    def _abstract_transition_packets(
        self, observation: bytes, outcome: bytes
    ) -> tuple[bytes, bytes] | None:
        return self._raw._abstract_transition_packets(observation, outcome)

    def _key_wave(
        self, observation: bytes, action: bytes, history: bytes | None
    ) -> tuple[torch.Tensor, torch.Tensor]:
        return self._raw._key_wave(observation, action, history)

    def _packet_wave(
        self, payload: bytes, *, role: int
    ) -> tuple[torch.Tensor, torch.Tensor]:
        return self._raw._packet_wave(payload, role=role)

    def _complex_conj_mul(
        self,
        left_re: torch.Tensor,
        left_im: torch.Tensor,
        right_re: torch.Tensor,
        right_im: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        return self._raw._complex_conj_mul(
            left_re, left_im, right_re, right_im
        )

    def _complex_mul(
        self,
        left_re: torch.Tensor,
        left_im: torch.Tensor,
        right_re: torch.Tensor,
        right_im: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        return self._raw._complex_mul(
            left_re, left_im, right_re, right_im
        )

    def _read_query_field(self, *, dynamic: bool) -> torch.Tensor:
        return self._raw._read_query_field(dynamic=dynamic)

    def _read_memory(
        self, query_field: torch.Tensor, *, history: bytes | None
    ) -> tuple[torch.Tensor, torch.Tensor, float, tuple[int, int]]:
        return self._raw._read_memory(query_field, history=history)

    def _clear_scales(self, scales: Sequence[int]) -> None:
        candidate = self._state_ref().field.detach().clone()
        parts = self._parts(candidate)
        for scale in scales:
            parts[scale].zero_()
        self._replace_state(_raw.QiFieldState(candidate))

    def _key_mask(
        self,
        observation: bytes,
        action: bytes,
        history: bytes | None,
    ) -> torch.Tensor:
        fields = (
            canonical_packet(observation),
            canonical_packet(action),
            b"" if history is None else canonical_packet(history),
        )
        domain = bytearray(b"cassi.causal.keyed-sparse-mask.v2\x00")
        for payload in fields:
            domain.extend(len(payload).to_bytes(2, "big"))
            domain.extend(payload)
        key_channels = self._key_channels
        selectors = torch.tensor(
            list(hashlib.shake_256(bytes(domain)).digest(self.profile.wave_width)),
            dtype=torch.int16,
        )
        slot_width = self.profile.wave_width // self.profile.payload_limit
        if slot_width < key_channels:
            raise EventError("field wave is too narrow for keyed sharding")
        mask = torch.zeros(self.profile.wave_width, dtype=torch.bool)
        for slot in range(self.profile.payload_limit):
            start = slot * slot_width
            end = (
                self.profile.wave_width
                if slot + 1 == self.profile.payload_limit
                else start + slot_width
            )
            local = selectors[start:end].remainder(key_channels).eq(0)
            if not bool(local.any().item()):
                local[selectors[start] % (end - start)] = True
            mask[start:end] = local
        return mask

    def _write_relation(
        self,
        state: Any,
        *,
        observation: bytes,
        action: bytes,
        history: bytes | None,
        outcome: bytes,
        scale: int,
        gain: float,
    ) -> Any:
        candidate = state.field.detach().clone()
        abstract = self._abstract_transition_packets(observation, outcome)
        if abstract is not None:
            observation, outcome = abstract
        key_re, key_im = self._key_wave(observation, action, history)
        out_re, out_im = self._packet_wave(outcome, role=3)
        relation_re, relation_im = self._complex_conj_mul(
            key_re, key_im, out_re, out_im
        )
        mask = self._key_mask(observation, action, history).to(dtype=torch.float64)
        self._set_differential(
            candidate,
            scale,
            gain * relation_re * mask,
            gain * relation_im * mask,
        )
        self._validate_field(candidate)
        return _raw.QiFieldState(candidate)

    def _decode_keyed_output(
        self,
        real: torch.Tensor,
        imag: torch.Tensor,
        mask: torch.Tensor,
    ) -> tuple[bytes | None, float, float, str]:
        codebook = self._raw._controller.codebook(
            0, device="cpu", dtype=torch.float64
        )
        candidate_ids = torch.tensor(
            list(range(_raw._ATOM_ALPHABET)) + [259], dtype=torch.int64
        )
        candidates = codebook.index_select(0, candidate_ids)
        slot_width = self.profile.wave_width // self.profile.payload_limit
        decoded = bytearray()
        scores: list[float] = []
        margins: list[float] = []
        terminated = False
        for slot in range(self.profile.payload_limit):
            start = slot * slot_width
            end = (
                self.profile.wave_width
                if slot + 1 == self.profile.payload_limit
                else start + slot_width
            )
            local_mask = mask[start:end]
            if not bool(local_mask.any().item()):
                return None, 0.0, 0.0, "field-output-key-channel-is-empty"
            slot_re = real[start:end][local_mask]
            slot_im = imag[start:end][local_mask]
            norm = math.sqrt(
                float((slot_re.square() + slot_im.square()).mean().item())
            )
            if norm <= 1.0e-12:
                return None, 0.0, 0.0, "field-output-key-channel-has-zero-norm"
            selected_candidates = candidates[:, start:end, :][:, local_mask, :]
            slot_scores = (
                slot_re.reshape(1, -1) * selected_candidates[:, :, 0]
                + slot_im.reshape(1, -1) * selected_candidates[:, :, 1]
            ).mean(dim=1) / norm
            top_values, top_indices = torch.topk(slot_scores, k=2)
            score = float(top_values[0].item())
            margin = score - float(top_values[1].item())
            scores.append(score)
            margins.append(margin)
            symbol = int(candidate_ids[int(top_indices[0].item())].item())
            if symbol == 259:
                terminated = True
                break
            decoded.append(symbol)
        if not terminated and len(decoded) != self.profile.payload_limit:
            return (
                None,
                sum(scores) / len(scores),
                min(margins),
                "field-output-has-no-terminator",
            )
        try:
            payload = canonical_packet(bytes(decoded))
        except Exception:
            return (
                None,
                sum(scores) / len(scores),
                min(margins),
                "field-output-packet-is-invalid",
            )
        return (
            payload,
            sum(scores) / len(scores),
            min(margins),
            "field-supported-keyed-packet",
        )

    def _predict_internal(
        self,
        observation: bytes,
        action: bytes,
        history: bytes | None,
        *,
        dynamic: bool,
        relational: bool = True,
    ) -> dict[str, Any]:
        observation = self._validate_payload(observation)
        action = self._validate_payload(action)
        if history is not None:
            history = self._validate_payload(history)
        if relational:
            spans = list(sorted(decode_packet(observation)))
            if len(spans) > 1:
                supported: list[tuple[int, bytes, dict[str, Any]]] = []
                for index, span in enumerate(spans):
                    singleton = encode_packet((span,))
                    candidate = self._predict_internal(
                        singleton,
                        action,
                        history,
                        dynamic=dynamic,
                        relational=False,
                    )
                    if (
                        candidate["status"] == "supported"
                        and candidate["payload_hex"] is not None
                    ):
                        supported.append(
                            (
                                index,
                                bytes.fromhex(str(candidate["payload_hex"])),
                                candidate,
                            )
                        )
                if len(supported) == 1:
                    index, replacement, candidate = supported[0]
                    output_spans = list(spans)
                    output_spans.pop(index)
                    output_spans.extend(decode_packet(replacement))
                    payload = encode_packet(tuple(sorted(output_spans)))
                    return {
                        **candidate,
                        "payload_hex": payload.hex(),
                        "reason": "field-supported-copy-binding",
                        "copy_binding": {
                            "preserved_spans": len(spans) - 1,
                            "changed_span_index": index,
                            "fixed_operator": True,
                        },
                    }
                if len(supported) > 1:
                    return {
                        "status": "unresolved",
                        "payload_hex": None,
                        "reason": "copy-binding-is-ambiguous",
                        "score": min(float(row[2]["score"]) for row in supported),
                        "margin": 0.0,
                        "memory_norm": max(
                            float(row[2]["memory_norm"]) for row in supported
                        ),
                        "bank": (
                            "conditional" if history is not None else "ordinary"
                        ),
                        "scales": [3, 2] if history is not None else [1, 0],
                        "dynamic": bool(dynamic),
                        "observation_sha256": _raw._payload_digest(observation),
                        "action_sha256": _raw._payload_digest(action),
                        "history_sha256": (
                            None
                            if history is None
                            else _raw._payload_digest(history)
                        ),
                        "depth": None,
                    }
        query_field = self._read_query_field(dynamic=dynamic)
        key_re, key_im = self._key_wave(observation, action, history)
        memory_re, memory_im, _, scales = self._read_memory(
            query_field, history=history
        )
        mask = self._key_mask(observation, action, history)
        selected_norm = math.sqrt(
            float(
                (
                    memory_re[mask].square() + memory_im[mask].square()
                ).mean().item()
            )
        )
        base: dict[str, Any] = {
            "status": "unresolved",
            "payload_hex": None,
            "reason": "field-memory-below-support-floor",
            "score": None,
            "margin": None,
            "memory_norm": selected_norm,
            "bank": "conditional" if history is not None else "ordinary",
            "scales": list(scales),
            "dynamic": bool(dynamic),
            "observation_sha256": _raw._payload_digest(observation),
            "action_sha256": _raw._payload_digest(action),
            "history_sha256": (
                None if history is None else _raw._payload_digest(history)
            ),
            "key_channel_sha256": _sha256(
                mask.to(dtype=torch.uint8).numpy().tobytes(order="C")
            ),
            "depth": None,
        }
        if selected_norm < self.profile.minimum_memory_norm:
            return base
        query_re, query_im = self._complex_mul(
            key_re, key_im, memory_re, memory_im
        )
        payload, score, margin, decode_reason = self._decode_keyed_output(
            query_re, query_im, mask
        )
        base["score"] = score
        base["margin"] = margin
        if score < self.profile.minimum_score:
            base["reason"] = "field-emission-score-below-floor"
            return base
        if margin < self.profile.minimum_margin:
            base["reason"] = "field-emission-is-ambiguous"
            return base
        if payload is None:
            base["reason"] = decode_reason
            return base
        base.update(
            {
                "status": "supported",
                "payload_hex": payload.hex(),
                "reason": decode_reason,
                "depth": 1,
            }
        )
        return base


@dataclass(slots=True)
class _PendingDecision:
    observation: bytes
    action: bytes
    history: bytes | None
    goal: bytes
    prediction: dict[str, Any]
    decision: dict[str, Any]
    event_sequence: int
    episode_index: int
    pre_state_sha256: str
    episode_start_state_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_hex": self.observation.hex(),
            "action_hex": self.action.hex(),
            "history_hex": None if self.history is None else self.history.hex(),
            "goal_hex": self.goal.hex(),
            "prediction": copy.deepcopy(self.prediction),
            "decision": copy.deepcopy(self.decision),
            "event_sequence": self.event_sequence,
            "episode_index": self.episode_index,
            "pre_state_sha256": self.pre_state_sha256,
            "episode_start_state_sha256": self.episode_start_state_sha256,
        }


class CausalEventLearner:
    """Bounded online causal learner with one adaptive Qi tensor.

    Current observation, one immediately preceding observation, reset-local
    attempted actions, and a pending committed decision are non-adaptive
    protocol context.  They are checkpointed for exact process continuation but
    never queried as learned transition/value tables.
    """

    def __init__(
        self,
        profile: CausalProfile | None = None,
        *,
        state: Any | None = None,
    ) -> None:
        self.profile = profile or CausalProfile()
        if not isinstance(self.profile, CausalProfile):
            raise EventError("profile must be a CausalProfile")
        self._field = _CausalFieldKernel(
            self.profile.acquisition,
            state=state,
            key_channels=cast(int, self.profile.key_channels),
        )
        self._episode_index = -1
        self._event_sequence = 0
        self._current_observation: bytes | None = None
        self._history: bytes | None = None
        self._attempted_actions: set[bytes] = set()
        self._pending: _PendingDecision | None = None
        self._episode_start_state_sha256 = self.fingerprint()


    @property
    def state(self) -> _raw.QiFieldState:
        """Return a detached state snapshot, never the live adaptive tensor."""

        return self._field._state_copy()

    @property
    def episode_index(self) -> int:
        return self._episode_index

    @property
    def pending(self) -> bool:
        return self._pending is not None

    @property
    def current_observation(self) -> bytes | None:
        return self._current_observation

    @property
    def eligible_history(self) -> bytes | None:
        return self._history

    def fingerprint(self) -> str:
        return self._field.fingerprint()

    def _validate_packet(self, payload: bytes | bytearray | memoryview) -> bytes:
        return self._field._validate_payload(payload)

    def _scale_tensor(
        self,
        scale: int,
        state: _raw.QiFieldState | None = None,
    ) -> torch.Tensor:
        if scale not in range(4):
            raise EventError("scale must be in [0, 3]")
        source = self._field._state_ref() if state is None else state
        return self._field._parts(source.field)[scale]

    def scale_sha256(self, scale: int) -> str:
        owned = (
            self._scale_tensor(scale)
            .detach()
            .to(device="cpu", dtype=torch.float64)
            .contiguous()
        )
        return _sha256(owned.numpy().tobytes(order="C"))

    def _scale_receipts(
        self, state: _raw.QiFieldState | None = None
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for scale in range(4):
            tensor = self._scale_tensor(scale, state)
            owned = (
                tensor.detach()
                .to(device="cpu", dtype=torch.float64)
                .contiguous()
            )
            rows.append(
                {
                    "scale": scale,
                    "sha256": _sha256(owned.numpy().tobytes(order="C")),
                    "mean_square": float(tensor.square().mean().item()),
                    "max_abs": float(tensor.abs().max().item()),
                }
            )
        return rows

    def reset(self) -> dict[str, Any]:
        self._event_sequence += 1
        discarded = self._pending is not None
        self._episode_index += 1
        self._current_observation = None
        self._history = None
        self._attempted_actions.clear()
        self._pending = None
        self._episode_start_state_sha256 = self.fingerprint()
        return {
            "schema": "cassi.causal-reset.v1",
            "event_sequence": self._event_sequence,
            "episode_index": self._episode_index,
            "discarded_pending_action": discarded,
            "state_sha256": self.fingerprint(),
            "episode_start_state_sha256": self._episode_start_state_sha256,
        }

    @staticmethod
    def _unavailable_conditional() -> dict[str, Any]:
        return {
            "status": "unavailable",
            "payload_hex": None,
            "reason": "no-eligible-history",
            "score": None,
            "margin": None,
            "memory_norm": 0.0,
            "bank": "conditional",
            "scales": [3, 2],
            "dynamic": False,
            "depth": None,
        }

    def predict(
        self,
        action: bytes,
        *,
        observation: bytes | None = None,
        history: bytes | None | object = _HISTORY_AUTO,
        dynamic: bool = False,
    ) -> dict[str, Any]:
        """Read ordinary and conditional banks without mutating the field."""

        if observation is None:
            observation = self._current_observation
        if observation is None:
            raise EventError("prediction requires a current observation")
        observation = self._validate_packet(observation)
        action = self._validate_packet(action)
        if history is _HISTORY_AUTO:
            resolved_history = self._history
        elif history is None:
            resolved_history = None
        else:
            resolved_history = self._validate_packet(cast(bytes, history))
        before = self.fingerprint()
        ordinary = self._field._predict_internal(
            observation, action, None, dynamic=dynamic
        )
        conditional = (
            self._unavailable_conditional()
            if resolved_history is None
            else self._field._predict_internal(
                observation, action, resolved_history, dynamic=dynamic
            )
        )
        if conditional["status"] == "supported":
            effective = copy.deepcopy(conditional)
            effective["reason"] = "field-conditional-override"
            branch = "conditional"
        elif ordinary["status"] == "supported":
            effective = copy.deepcopy(ordinary)
            effective["reason"] = "field-ordinary-fallback"
            branch = "ordinary"
        else:
            effective = {
                "status": "unresolved",
                "payload_hex": None,
                "reason": "no-applicable-supported-field-readout",
                "score": None,
                "margin": None,
                "memory_norm": max(
                    float(ordinary.get("memory_norm") or 0.0),
                    float(conditional.get("memory_norm") or 0.0),
                ),
                "bank": "none",
                "scales": [],
                "dynamic": bool(dynamic),
                "depth": None,
            }
            branch = "none"
        if self.fingerprint() != before:
            raise RuntimeError("prediction mutated the adaptive field")
        return {
            "schema": "cassi.causal-prediction.v1",
            "ordinary": ordinary,
            "conditional": conditional,
            "conditional_applicable": conditional["status"] == "supported",
            "effective": effective,
            "effective_branch": branch,
            "observation_sha256": _packet_sha256(observation),
            "action_sha256": _packet_sha256(action),
            "history_sha256": (
                None if resolved_history is None else _packet_sha256(resolved_history)
            ),
            "state_sha256": before,
        }

    def _predict_only_scales(
        self,
        observation: bytes,
        action: bytes,
        history: bytes | None,
        scales: Sequence[int],
    ) -> dict[str, Any]:
        kept = set(scales)
        if not kept or not kept.issubset(set(range(4))):
            raise EventError("prediction scale selection is invalid")
        counterfactual = _CausalFieldKernel(
            self.profile.acquisition,
            state=self._field._state_ref(),
            key_channels=cast(int, self.profile.key_channels),
        )
        counterfactual._clear_scales(
            tuple(scale for scale in range(4) if scale not in kept)
        )
        return counterfactual._predict_internal(
            observation, action, history, dynamic=False
        )

    def _bank_breakdown(
        self, observation: bytes, action: bytes, history: bytes | None
    ) -> dict[str, Any]:
        return {
            "ordinary_provisional": self._predict_only_scales(
                observation, action, None, (0,)
            ),
            "ordinary_consolidated": self._predict_only_scales(
                observation, action, None, (1,)
            ),
            "conditional_provisional": (
                self._unavailable_conditional()
                if history is None
                else self._predict_only_scales(observation, action, history, (2,))
            ),
            "conditional_consolidated": (
                self._unavailable_conditional()
                if history is None
                else self._predict_only_scales(observation, action, history, (3,))
            ),
        }

    @staticmethod
    def _prediction_matches(prediction: Mapping[str, Any], outcome: bytes) -> bool:
        payload_hex = prediction.get("payload_hex")
        if prediction.get("status") != "supported" or not isinstance(payload_hex, str):
            return False
        try:
            return canonical_packet(bytes.fromhex(payload_hex)) == canonical_packet(outcome)
        except Exception:
            return False

    def _wave_mismatch(
        self, prediction: Mapping[str, Any], outcome: bytes
    ) -> float | None:
        payload_hex = prediction.get("payload_hex")
        if prediction.get("status") != "supported" or not isinstance(payload_hex, str):
            return None
        predicted = bytes.fromhex(payload_hex)
        pred_re, pred_im = self._field._packet_wave(predicted, role=3)
        out_re, out_im = self._field._packet_wave(outcome, role=3)
        numerator = torch.sqrt(
            ((out_re - pred_re).square() + (out_im - pred_im).square()).mean()
        )
        denominator = torch.sqrt((out_re.square() + out_im.square()).mean()).clamp_min(
            1.0e-12
        )
        return float((numerator / denominator).item())

    @staticmethod
    def _canonical_actions(actions: Sequence[bytes], limit: int) -> tuple[bytes, ...]:
        if isinstance(actions, (bytes, bytearray, memoryview)) or not isinstance(
            actions, Sequence
        ):
            raise EventError("actions must be a sequence of packets")
        unique: dict[bytes, None] = {}
        for action in actions:
            try:
                unique[canonical_packet(action)] = None
            except Exception as exc:
                raise EventError(f"candidate action is invalid: {exc}") from exc
        if not unique:
            raise EventError("at least one candidate action is required")
        if len(unique) > limit:
            raise EventError("candidate action count exceeds the fixed bound")
        return tuple(sorted(unique))

    def _find_route(
        self,
        observation: bytes,
        history: bytes | None,
        actions: tuple[bytes, ...],
        goal: bytes,
    ) -> dict[str, Any]:
        if canonical_packet(observation) == canonical_packet(goal):
            return {"plan": [], "expanded": 0, "minimum_score": None, "minimum_margin": None}
        queue: deque[tuple[bytes, bytes | None, tuple[bytes, ...], tuple[float, ...], tuple[float, ...]]] = deque()
        queue.append((observation, history, (), (), ()))
        visited = {(canonical_packet(observation), None if history is None else canonical_packet(history))}
        expanded = 0
        while queue:
            current, current_history, plan, scores, margins = queue.popleft()
            if len(plan) >= self.profile.max_depth:
                continue
            for action in actions:
                if expanded >= self.profile.max_expansions:
                    return {
                        "plan": None,
                        "expanded": expanded,
                        "capacity_hit": True,
                        "minimum_score": None,
                        "minimum_margin": None,
                    }
                expanded += 1
                bundle = self.predict(
                    action,
                    observation=current,
                    history=current_history,
                    dynamic=False,
                )
                effective = bundle["effective"]
                if effective["status"] != "supported" or effective["payload_hex"] is None:
                    continue
                successor = bytes.fromhex(str(effective["payload_hex"]))
                next_plan = plan + (action,)
                next_scores = scores + (float(effective["score"]),)
                next_margins = margins + (float(effective["margin"]),)
                if canonical_packet(successor) == canonical_packet(goal):
                    return {
                        "plan": list(next_plan),
                        "expanded": expanded,
                        "capacity_hit": False,
                        "minimum_score": min(next_scores),
                        "minimum_margin": min(next_margins),
                    }
                marker = (canonical_packet(successor), canonical_packet(current))
                if marker in visited:
                    continue
                visited.add(marker)
                queue.append(
                    (successor, current, next_plan, next_scores, next_margins)
                )
        return {
            "plan": None,
            "expanded": expanded,
            "capacity_hit": False,
            "minimum_score": None,
            "minimum_margin": None,
        }

    def decide(
        self,
        actions: Sequence[bytes],
        goal: bytes,
        *,
        inquiry_actions: Sequence[bytes] = (),
    ) -> dict[str, Any]:
        """Commit one action before its consequence exists."""

        if self._pending is not None:
            raise EventError("a committed action is still awaiting its outcome")
        if self._current_observation is None:
            raise EventError("decision requires a current observation")
        action_packets = self._canonical_actions(actions, self.profile.max_actions)
        inquiry_packets = set(
            self._canonical_actions(inquiry_actions, self.profile.max_actions)
            if inquiry_actions
            else ()
        )
        if not inquiry_packets.issubset(set(action_packets)):
            raise EventError("inquiry actions must be present in the candidate set")
        goal = self._validate_packet(goal)
        before = self.fingerprint()
        candidate_rows: list[dict[str, Any]] = []
        predictions: dict[bytes, dict[str, Any]] = {}
        for action in action_packets:
            bundle = self.predict(action, dynamic=False)
            predictions[action] = bundle
            candidate_rows.append(
                {
                    "action_hex": action.hex(),
                    "prediction": bundle,
                    "attempted_this_episode": action in self._attempted_actions,
                    "inquiry": action in inquiry_packets,
                }
            )
        route = self._find_route(
            self._current_observation,
            self._history,
            action_packets,
            goal,
        )
        selected: bytes | None = None
        field_owned = False
        reason: str
        plan: list[bytes] = []
        if route["plan"] is not None and route["plan"]:
            plan = cast(list[bytes], route["plan"])
            selected = plan[0]
            field_owned = True
            reason = "field-supported-bounded-route"
            decision_kind = (
                "field-supported-inquiry"
                if selected in inquiry_packets
                else "field-supported"
            )
        elif route["plan"] == []:
            decision_kind = "goal-already-satisfied"
            reason = "current-observation-equals-goal"
        else:
            rotated = tuple(
                action_packets[(self._episode_index + offset) % len(action_packets)]
                for offset in range(len(action_packets))
            )
            selected = next(
                (
                    action
                    for action in rotated
                    if action not in self._attempted_actions
                ),
                None,
            )
            if selected is None:
                decision_kind = "unresolved"
                reason = (
                    "route-search-capacity-exhausted"
                    if route.get("capacity_hit")
                    else "all-canonical-actions-probed-without-supported-route"
                )
            else:
                decision_kind = "exploration"
                reason = (
                    "deterministic-context-probe-despite-non-goal-prediction"
                    if predictions[selected]["effective"]["status"] == "supported"
                    else "deterministic-canonical-episode-rotation"
                )
        next_event_sequence = self._event_sequence + 1
        receipt: dict[str, Any] = {
            "schema": _DECISION_SCHEMA,
            "operator_id": _OPERATOR_ID,
            "policy": self.profile.policy,
            "event_sequence": next_event_sequence,
            "episode_index": self._episode_index,
            "decision_kind": decision_kind,
            "field_owned": field_owned,
            "reason": reason,
            "observation_hex": self._current_observation.hex(),
            "history_hex": None if self._history is None else self._history.hex(),
            "goal_hex": goal.hex(),
            "candidate_order_hex": [action.hex() for action in action_packets],
            "candidate_order_sha256": _sha256(
                _canonical_json([action.hex() for action in action_packets])
            ),
            "candidates": candidate_rows,
            "action_hex": None if selected is None else selected.hex(),
            "plan_hex": [action.hex() for action in plan],
            "route": {
                "expanded": route["expanded"],
                "capacity_hit": bool(route.get("capacity_hit", False)),
                "minimum_score": route.get("minimum_score"),
                "minimum_margin": route.get("minimum_margin"),
            },
            "actual_outcome_available_at_commit": False,
            "pre_consequence_state_sha256": before,
            "attempted_action_count_before": len(self._attempted_actions),
        }
        pending: _PendingDecision | None = None
        if selected is not None:
            selected_bundle = copy.deepcopy(predictions[selected])
            selected_bundle["banks"] = self._bank_breakdown(
                self._current_observation, selected, self._history
            )
            pending = _PendingDecision(
                observation=self._current_observation,
                action=selected,
                history=self._history,
                goal=goal,
                prediction=selected_bundle,
                decision=copy.deepcopy(receipt),
                event_sequence=next_event_sequence,
                episode_index=self._episode_index,
                pre_state_sha256=before,
                episode_start_state_sha256=self._episode_start_state_sha256,
            )
        if self.fingerprint() != before:
            raise RuntimeError("decision mutated the adaptive field")
        self._event_sequence = next_event_sequence
        if selected is not None:
            self._attempted_actions.add(selected)
            self._pending = pending
        return receipt

    def _write_relation(
        self,
        *,
        pending: _PendingDecision,
        outcome: bytes,
        scale: int,
    ) -> _raw.QiFieldState:
        gain = (
            self.profile.acquisition.provisional_gain
            if scale in (0, 2)
            else self.profile.acquisition.consolidation_gain
        )
        candidate = self._field._write_relation(
            self._field._state_ref(),
            observation=pending.observation,
            action=pending.action,
            history=pending.history if scale in (2, 3) else None,
            outcome=outcome,
            scale=scale,
            gain=gain,
        )
        self._field._validate_field(candidate.field)
        return candidate

    def _promote_relation(
        self,
        *,
        pending: _PendingDecision,
        outcome: bytes,
        target_scale: int,
    ) -> _raw.QiFieldState:
        if target_scale not in (1, 3):
            raise EventError("promotion target must be consolidated scale 1 or 3")
        history = pending.history if target_scale == 3 else None
        source_scale = target_scale - 1
        target_observation = pending.observation
        target_outcome = outcome
        abstract = self._field._abstract_transition_packets(
            target_observation, target_outcome
        )
        if abstract is not None:
            target_observation, target_outcome = abstract
        key_re, key_im = self._field._key_wave(
            target_observation, pending.action, history
        )
        out_re, out_im = self._field._packet_wave(target_outcome, role=3)
        relation_re, relation_im = self._field._complex_conj_mul(
            key_re, key_im, out_re, out_im
        )
        mask = self._field._key_mask(
            target_observation, pending.action, history
        ).to(dtype=torch.float64)
        relation_re = relation_re * mask
        relation_im = relation_im * mask
        candidate = self._field._state_ref().field.detach().clone()
        self._field._set_differential(
            candidate,
            source_scale,
            -self.profile.acquisition.provisional_gain * relation_re,
            -self.profile.acquisition.provisional_gain * relation_im,
        )
        self._field._set_differential(
            candidate,
            target_scale,
            self.profile.acquisition.consolidation_gain * relation_re,
            self.profile.acquisition.consolidation_gain * relation_im,
        )
        self._field._validate_field(candidate)
        return _raw.QiFieldState(candidate)

    def _promotion_scale(
        self,
        pending: _PendingDecision,
        outcome: bytes,
        branch: str,
        *,
        allow_promotion: bool,
    ) -> tuple[int | None, str]:
        if not allow_promotion:
            return None, "promotion-disabled-by-caller"
        if pending.pre_state_sha256 != pending.episode_start_state_sha256:
            return None, "confirmation-did-not-start-from-episode-entry-field"
        if pending.episode_index != self._episode_index:
            return None, "confirmation-episode-identity-mismatch"
        banks = pending.prediction["banks"]
        if branch == "conditional":
            provisional = banks["conditional_provisional"]
            consolidated = banks["conditional_consolidated"]
            target_scale = 3
        else:
            provisional = banks["ordinary_provisional"]
            consolidated = banks["ordinary_consolidated"]
            target_scale = 1
        if self._prediction_matches(consolidated, outcome):
            return None, "relation-already-consolidated"
        if not self._prediction_matches(provisional, outcome):
            return None, "correct-prediction-was-not-supported-by-provisional-bank"
        return target_scale, "reset-bounded-provisional-present-at-entry-confirmation"

    def _admit_outcome(
        self,
        pending: _PendingDecision,
        outcome: bytes,
        *,
        learn: bool,
        allow_promotion: bool,
        outcome_event_sequence: int,
    ) -> dict[str, Any]:
        before = self.fingerprint()
        if pending.episode_index != self._episode_index:
            raise EventError("pending decision belongs to another episode")
        if pending.pre_state_sha256 != before:
            raise EventError("pending decision predecessor field changed")
        if (
            pending.episode_start_state_sha256
            != self._episode_start_state_sha256
        ):
            raise EventError("pending decision episode entry field changed")
        scales_before = self._scale_receipts()
        bundle = pending.prediction
        ordinary = bundle["ordinary"]
        conditional = bundle["conditional"]
        effective = bundle["effective"]
        ordinary_match = self._prediction_matches(ordinary, outcome)
        conditional_match = self._prediction_matches(conditional, outcome)
        effective_match = self._prediction_matches(effective, outcome)
        history_eligible = pending.history is not None
        mismatch = self._wave_mismatch(effective, outcome)
        scale: int | None = None
        admission_kind = "none"
        reason = "learning-disabled"
        mismatch_gate_passed = False
        promotion_reason: str | None = None
        if learn:
            policy = self.profile.policy
            if policy == "unconditional-only":
                if ordinary_match:
                    scale, promotion_reason = self._promotion_scale(
                        pending,
                        outcome,
                        "ordinary",
                        allow_promotion=allow_promotion,
                    )
                    if scale is not None:
                        admission_kind = "ordinary-consolidation"
                        reason = cast(str, promotion_reason)
                    else:
                        reason = cast(str, promotion_reason)
                else:
                    scale = 0
                    admission_kind = "ordinary-provisional"
                    reason = "unconditional-policy-admission"
            elif policy == "always-conditional" and history_eligible:
                if conditional_match:
                    scale, promotion_reason = self._promotion_scale(
                        pending,
                        outcome,
                        "conditional",
                        allow_promotion=allow_promotion,
                    )
                    if scale is not None:
                        admission_kind = "conditional-consolidation"
                        reason = cast(str, promotion_reason)
                    else:
                        reason = cast(str, promotion_reason)
                else:
                    scale = 2
                    admission_kind = "conditional-provisional"
                    reason = "always-conditional-policy-admission"
            elif policy == "always-conditional":
                if ordinary_match:
                    scale, promotion_reason = self._promotion_scale(
                        pending,
                        outcome,
                        "ordinary",
                        allow_promotion=allow_promotion,
                    )
                    if scale is not None:
                        admission_kind = "ordinary-consolidation"
                        reason = cast(str, promotion_reason)
                    else:
                        reason = cast(str, promotion_reason)
                else:
                    scale = 0
                    admission_kind = "ordinary-provisional"
                    reason = "no-history-cold-start-admission"
            else:
                # Default mismatch-gated policy.  Unresolved cold starts and
                # supported contradictions are intentionally distinct.
                if conditional["status"] == "supported":
                    if conditional_match:
                        scale, promotion_reason = self._promotion_scale(
                            pending,
                            outcome,
                            "conditional",
                            allow_promotion=allow_promotion,
                        )
                        if scale is not None:
                            admission_kind = "conditional-consolidation"
                            reason = cast(str, promotion_reason)
                        else:
                            reason = cast(str, promotion_reason)
                    else:
                        reason = "supported-conditional-contradiction-not-overwritten"
                elif ordinary["status"] == "supported":
                    if ordinary_match:
                        scale, promotion_reason = self._promotion_scale(
                            pending,
                            outcome,
                            "ordinary",
                            allow_promotion=allow_promotion,
                        )
                        if scale is not None:
                            admission_kind = "ordinary-consolidation"
                            reason = cast(str, promotion_reason)
                        else:
                            reason = cast(str, promotion_reason)
                    elif history_eligible:
                        scale = 2
                        admission_kind = "conditional-provisional"
                        reason = "prospective-unconditional-mismatch-with-eligible-history"
                    else:
                        scale = 0
                        admission_kind = "ordinary-provisional"
                        reason = "unconditional-collision-or-revision-admission"
                else:
                    scale = 0
                    admission_kind = "ordinary-provisional"
                    reason = "unresolved-cold-start-ordinary-admission"
        current_state = self._field._state_ref()
        candidate_state = current_state
        if scale in (1, 3):
            candidate_state = self._promote_relation(
                pending=pending,
                outcome=outcome,
                target_scale=scale,
            )
        elif scale is not None:
            candidate_state = self._write_relation(
                pending=pending, outcome=outcome, scale=scale
            )
        after = _raw._sha_tensor(candidate_state.field)
        scales_after = self._scale_receipts(candidate_state)
        receipt = {
            "schema": _OUTCOME_SCHEMA,
            "operator_id": _OPERATOR_ID,
            "policy": self.profile.policy,
            "episode_index": self._episode_index,
            "decision_event_sequence": pending.event_sequence,
            "outcome_event_sequence": outcome_event_sequence,
            "decision_kind": pending.decision["decision_kind"],
            "field_owned_decision": bool(pending.decision["field_owned"]),
            "actual_outcome_hex": outcome.hex(),
            "prediction_before_outcome": copy.deepcopy(bundle),
            "ordinary_prediction_correct": ordinary_match,
            "conditional_prediction_correct": conditional_match,
            "effective_prediction_correct": effective_match,
            "mismatch": mismatch,
            "mismatch_source": (
                "supported-effective-output-wave"
                if mismatch is not None
                else "none-unresolved-cold-start"
            ),
            "history_eligible": history_eligible,
            "mismatch_gate_passed": mismatch_gate_passed,
            "admission_kind": admission_kind,
            "admission_scale": scale,
            "learned": before != after,
            "promoted": scale in (1, 3),
            "promotion_reason": promotion_reason,
            "promotion_operation": (
                "move-provisional-to-consolidated"
                if scale in (1, 3)
                else None
            ),
            "reason": reason,
            "confirmation_from_new_reset_bounded_episode": scale in (1, 3),
            "confirmation_episode_index": (
                self._episode_index if scale in (1, 3) else None
            ),
            "provisional_witness_bank": (
                "ordinary-provisional"
                if scale == 1
                else "conditional-provisional" if scale == 3 else None
            ),
            "provisional_witness_state_sha256": (
                pending.episode_start_state_sha256
                if scale in (1, 3)
                else None
            ),
            "provisional_present_at_confirmation_episode_entry": (
                scale in (1, 3)
                and pending.pre_state_sha256
                == pending.episode_start_state_sha256
            ),
            "pre_consequence_state_sha256": pending.pre_state_sha256,
            "predecessor_state_sha256": before,
            "successor_state_sha256": after,
            "scales_before": scales_before,
            "scales_after": scales_after,
        }
        if candidate_state is not current_state:
            self._field._replace_state(candidate_state)
        return receipt

    def observe(
        self,
        payload: bytes,
        *,
        learn: bool = True,
        allow_promotion: bool = True,
    ) -> dict[str, Any]:
        """Consume an observation or the consequence of a pending action."""

        if not isinstance(learn, bool) or not isinstance(allow_promotion, bool):
            raise EventError("learn and allow_promotion must be booleans")
        observation = self._validate_packet(payload)
        next_event_sequence = self._event_sequence + 1
        if self._pending is None:
            previous = self._current_observation
            receipt = {
                "schema": "cassi.causal-observation.v1",
                "event_sequence": next_event_sequence,
                "episode_index": self._episode_index,
                "reason": (
                    "current-observation-established"
                    if previous is None
                    else "eligible-immediate-history-advanced"
                ),
                "observation_hex": observation.hex(),
                "history_hex": None if previous is None else previous.hex(),
                "learned": False,
                "state_sha256": self.fingerprint(),
            }
            self._event_sequence = next_event_sequence
            self._history = previous
            self._current_observation = observation
            return receipt
        pending = self._pending
        receipt = self._admit_outcome(
            pending,
            observation,
            learn=learn,
            allow_promotion=allow_promotion,
            outcome_event_sequence=next_event_sequence,
        )
        self._event_sequence = next_event_sequence
        self._history = pending.observation
        self._current_observation = observation
        self._pending = None
        return receipt

    def clone(self) -> "CausalEventLearner":
        cloned = CausalEventLearner(
            self.profile,
            state=self._field._state_ref(),
        )
        cloned._episode_index = self._episode_index
        cloned._event_sequence = self._event_sequence
        cloned._current_observation = self._current_observation
        cloned._history = self._history
        cloned._attempted_actions = set(self._attempted_actions)
        cloned._pending = copy.deepcopy(self._pending)
        cloned._episode_start_state_sha256 = self._episode_start_state_sha256
        return cloned

    def clear_scales(
        self, scales: Sequence[int]
    ) -> tuple["CausalEventLearner", dict[str, Any]]:
        selected = tuple(sorted(set(scales)))
        if not selected or any(scale not in range(4) for scale in selected):
            raise EventError("clear_scales requires scales in [0, 3]")
        counterfactual = self.clone()
        before = counterfactual.fingerprint()
        scale_before = counterfactual._scale_receipts()
        counterfactual._field._clear_scales(selected)
        return counterfactual, {
            "schema": "cassi.causal-scale-intervention.v1",
            "scales": list(selected),
            "before_state_sha256": before,
            "after_state_sha256": counterfactual.fingerprint(),
            "changed": before != counterfactual.fingerprint(),
            "scales_before": scale_before,
            "scales_after": counterfactual._scale_receipts(),
        }

    def intervene_relation(
        self,
        *,
        observation: bytes,
        action: bytes,
        outcome: bytes,
        history: bytes | None,
        bank: str,
    ) -> tuple["CausalEventLearner", dict[str, Any]]:
        """Remove an explicitly named relation projection from a clone.

        The target outcome is required; it is never inferred by first asking the
        learner what it currently predicts.
        """

        if bank not in {"ordinary", "conditional"}:
            raise EventError("bank must be ordinary or conditional")
        observation = self._validate_packet(observation)
        action = self._validate_packet(action)
        outcome = self._validate_packet(outcome)
        if bank == "conditional":
            if history is None:
                raise EventError("conditional intervention requires explicit history")
            history = self._validate_packet(history)
            scales = (2, 3)
        else:
            history = None
            scales = (0, 1)
        target_observation = observation
        target_outcome = outcome
        abstract = self._field._abstract_transition_packets(observation, outcome)
        if abstract is not None:
            target_observation, target_outcome = abstract
        key_re, key_im = self._field._key_wave(
            target_observation, action, history
        )
        out_re, out_im = self._field._packet_wave(target_outcome, role=3)
        relation_re, relation_im = self._field._complex_conj_mul(
            key_re, key_im, out_re, out_im
        )
        mask = self._field._key_mask(
            target_observation, action, history
        ).to(dtype=torch.float64)
        relation_re = relation_re * mask
        relation_im = relation_im * mask
        counterfactual = self.clone()
        before = counterfactual.fingerprint()
        scales_before = counterfactual._scale_receipts()
        candidate = (
            counterfactual._field._state_ref().field.detach().clone()
        )
        coefficients: list[float] = []
        readable_target_scales: list[int] = []
        for scale in scales:
            scale_prediction = counterfactual._predict_only_scales(
                observation, action, history, (scale,)
            )
            if counterfactual._prediction_matches(scale_prediction, outcome):
                coefficient = (
                    self.profile.acquisition.provisional_gain
                    if scale in (0, 2)
                    else self.profile.acquisition.consolidation_gain
                )
                readable_target_scales.append(scale)
            else:
                coefficient = 0.0
            coefficients.append(coefficient)
            if coefficient > 0.0:
                counterfactual._field._set_differential(
                    candidate,
                    scale,
                    -coefficient * relation_re,
                    -coefficient * relation_im,
                )
        counterfactual._field._validate_field(candidate)
        counterfactual._field._replace_state(
            _raw.QiFieldState(candidate)
        )
        return counterfactual, {
            "schema": _INTERVENTION_SCHEMA,
            "operator_id": _OPERATOR_ID,
            "bank": bank,
            "scales": list(scales),
            "observation_sha256": _packet_sha256(observation),
            "action_sha256": _packet_sha256(action),
            "outcome_sha256": _packet_sha256(outcome),
            "history_sha256": None if history is None else _packet_sha256(history),
            "projection_coefficients": coefficients,
            "removal_basis": "fixed-admission-gain-on-readable-target-scale",
            "readable_target_scales": readable_target_scales,
            "before_state_sha256": before,
            "after_state_sha256": counterfactual.fingerprint(),
            "changed": before != counterfactual.fingerprint(),
            "scales_before": scales_before,
            "scales_after": counterfactual._scale_receipts(),
        }

    def _context_dict(self) -> dict[str, Any]:
        return {
            "episode_index": self._episode_index,
            "event_sequence": self._event_sequence,
            "current_observation_hex": (
                None
                if self._current_observation is None
                else self._current_observation.hex()
            ),
            "history_hex": None if self._history is None else self._history.hex(),
            "attempted_action_hex": sorted(action.hex() for action in self._attempted_actions),
            "pending": None if self._pending is None else self._pending.to_dict(),
            "episode_start_state_sha256": self._episode_start_state_sha256,
        }

    def snapshot(self) -> dict[str, Any]:
        field_snapshot = self._field.snapshot()
        return {
            "schema": "cassi.causal-event-snapshot.v1",
            "operator_id": _OPERATOR_ID,
            "profile_sha256": self.profile.fingerprint,
            "operator_source_sha256": _operator_source_sha256(),
            "adaptive_state": "QiFieldState.field [S,9M,B] only",
            "field": field_snapshot,
            "field_state_sha256": self.fingerprint(),
            "scales": self._scale_receipts(),
            "protocol_context": self._context_dict(),
            "learned_sidecars": 0,
            "qwen_calls": 0,
            "teacher_calls": 0,
        }

    def checkpoint_bytes(self) -> bytes:
        field_checkpoint = self._field.checkpoint_bytes()
        context = self._context_dict()
        header = {
            "schema": _CHECKPOINT_SCHEMA,
            "operator_id": _OPERATOR_ID,
            "profile": self.profile.as_dict(),
            "profile_sha256": self.profile.fingerprint,
            "operator_source_sha256": _operator_source_sha256(),
            "base_operator_source_sha256": _raw._operator_source_sha256(),
            "field_state_sha256": self.fingerprint(),
            "field_checkpoint_sha256": _sha256(field_checkpoint),
            "field_checkpoint_bytes": len(field_checkpoint),
            "context": context,
            "context_sha256": _sha256(_canonical_json(context)),
            "adaptive_payload": "one-qi-field-state",
            "protocol_context_adaptive": False,
            "excluded": [
                "transition-table",
                "action-values",
                "learned-counters",
                "event-journal",
                "qwen-state",
                "teacher-state",
            ],
        }
        header["header_sha256"] = _sha256(_canonical_json(header))
        encoded_header = _canonical_json(header)
        return (
            _CHECKPOINT_MAGIC
            + struct.pack(">Q", len(encoded_header))
            + encoded_header
            + field_checkpoint
        )

    @classmethod
    def restore(
        cls,
        payload: bytes | bytearray | memoryview,
        *,
        expected_profile: CausalProfile | None = None,
    ) -> "CausalEventLearner":
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise CheckpointError("causal checkpoint must be bytes-like")
        owned = bytes(payload)
        prefix = len(_CHECKPOINT_MAGIC)
        if len(owned) < prefix + 8 or owned[:prefix] != _CHECKPOINT_MAGIC:
            raise CheckpointError("causal checkpoint magic mismatch")
        header_size = struct.unpack(">Q", owned[prefix : prefix + 8])[0]
        start = prefix + 8
        end = start + header_size
        if header_size <= 0 or end > len(owned):
            raise CheckpointError("causal checkpoint header length is invalid")
        try:
            header = json.loads(owned[start:end].decode("utf-8"))
        except Exception as exc:
            raise CheckpointError(f"causal checkpoint header is invalid: {exc}") from exc
        if not isinstance(header, Mapping) or header.get("schema") != _CHECKPOINT_SCHEMA:
            raise CheckpointError("causal checkpoint schema mismatch")
        header_without_digest = dict(header)
        header_sha256 = header_without_digest.pop("header_sha256", None)
        if (
            not isinstance(header_sha256, str)
            or len(header_sha256) != 64
            or header_sha256
            != _sha256(_canonical_json(header_without_digest))
        ):
            raise CheckpointError("causal checkpoint header digest mismatch")
        if header.get("operator_id") != _OPERATOR_ID:
            raise CheckpointError("causal checkpoint operator identity mismatch")
        if header.get("operator_source_sha256") != _operator_source_sha256():
            raise CheckpointError("causal checkpoint source identity mismatch")
        if header.get("base_operator_source_sha256") != _raw._operator_source_sha256():
            raise CheckpointError("base raw-event operator source identity mismatch")
        try:
            profile = CausalProfile.from_dict(cast(Mapping[str, Any], header["profile"]))
        except Exception as exc:
            raise CheckpointError(f"causal checkpoint profile is invalid: {exc}") from exc
        if header.get("profile_sha256") != profile.fingerprint:
            raise CheckpointError("causal checkpoint profile digest mismatch")
        if expected_profile is not None:
            if not isinstance(expected_profile, CausalProfile):
                raise CheckpointError("expected profile must be a CausalProfile")
            if profile.fingerprint != expected_profile.fingerprint:
                raise CheckpointError(
                    "causal checkpoint does not match the expected profile"
                )
        field_checkpoint = owned[end:]
        if header.get("field_checkpoint_bytes") != len(field_checkpoint):
            raise CheckpointError("causal field checkpoint byte count mismatch")
        if header.get("field_checkpoint_sha256") != _sha256(field_checkpoint):
            raise CheckpointError("causal field checkpoint digest mismatch")
        field_learner = _raw.RawEventLearner.restore(field_checkpoint)
        if (
            field_learner.profile.fingerprint
            != profile.acquisition.fingerprint
        ):
            raise CheckpointError(
                "causal and raw-field checkpoint profiles differ"
            )
        learner = cls(
            profile,
            state=field_learner.state,
        )
        if header.get("field_state_sha256") != learner.fingerprint():
            raise CheckpointError("causal field state identity mismatch")
        context = header.get("context")
        if not isinstance(context, Mapping):
            raise CheckpointError("causal checkpoint context is invalid")
        if header.get("context_sha256") != _sha256(_canonical_json(context)):
            raise CheckpointError("causal checkpoint context digest mismatch")
        learner._restore_context(context)
        return learner

    def _restore_context(self, context: Mapping[str, Any]) -> None:
        expected = {
            "episode_index",
            "event_sequence",
            "current_observation_hex",
            "history_hex",
            "attempted_action_hex",
            "pending",
            "episode_start_state_sha256",
        }
        if set(context) != expected:
            raise CheckpointError("causal checkpoint context fields mismatch")
        episode = context["episode_index"]
        sequence = context["event_sequence"]
        if isinstance(episode, bool) or not isinstance(episode, int) or episode < -1:
            raise CheckpointError("causal checkpoint episode index is invalid")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise CheckpointError("causal checkpoint event sequence is invalid")

        def packet_from_hex(value: Any, name: str) -> bytes | None:
            if value is None:
                return None
            if not isinstance(value, str):
                raise CheckpointError(f"{name} must be hexadecimal or null")
            try:
                return self._validate_packet(bytes.fromhex(value))
            except Exception as exc:
                raise CheckpointError(f"{name} is invalid: {exc}") from exc

        def required_packet_from_hex(value: Any, name: str) -> bytes:
            packet = packet_from_hex(value, name)
            if packet is None:
                raise CheckpointError(f"{name} cannot be null")
            return packet

        current = packet_from_hex(context["current_observation_hex"], "current observation")
        history = packet_from_hex(context["history_hex"], "history")
        attempted_value = context["attempted_action_hex"]
        if not isinstance(attempted_value, list) or not all(
            isinstance(item, str) for item in attempted_value
        ):
            raise CheckpointError("attempted actions are invalid")
        attempted = {
            cast(bytes, packet_from_hex(item, "attempted action"))
            for item in attempted_value
        }
        episode_start = context["episode_start_state_sha256"]
        if not isinstance(episode_start, str) or len(episode_start) != 64:
            raise CheckpointError("episode start field identity is invalid")
        pending_value = context["pending"]
        pending: _PendingDecision | None = None
        if pending_value is not None:
            if not isinstance(pending_value, Mapping):
                raise CheckpointError("pending decision is invalid")
            required = {
                "observation_hex",
                "action_hex",
                "history_hex",
                "goal_hex",
                "prediction",
                "decision",
                "event_sequence",
                "episode_index",
                "pre_state_sha256",
                "episode_start_state_sha256",
            }
            if set(pending_value) != required:
                raise CheckpointError("pending decision fields mismatch")
            prediction = pending_value["prediction"]
            decision = pending_value["decision"]
            if not isinstance(prediction, Mapping) or not isinstance(decision, Mapping):
                raise CheckpointError("pending prediction or receipt is invalid")
            pending_sequence = pending_value["event_sequence"]
            pending_episode = pending_value["episode_index"]
            pending_pre_state = pending_value["pre_state_sha256"]
            pending_episode_start = pending_value[
                "episode_start_state_sha256"
            ]
            if (
                isinstance(pending_sequence, bool)
                or not isinstance(pending_sequence, int)
                or pending_sequence < 0
            ):
                raise CheckpointError(
                    "pending decision event sequence is invalid"
                )
            if (
                isinstance(pending_episode, bool)
                or not isinstance(pending_episode, int)
                or pending_episode < -1
            ):
                raise CheckpointError(
                    "pending decision episode index is invalid"
                )
            if (
                not isinstance(pending_pre_state, str)
                or len(pending_pre_state) != 64
                or not isinstance(pending_episode_start, str)
                or len(pending_episode_start) != 64
            ):
                raise CheckpointError(
                    "pending decision field identities are invalid"
                )
            pending = _PendingDecision(
                observation=required_packet_from_hex(
                    pending_value["observation_hex"],
                    "pending observation",
                ),
                action=required_packet_from_hex(
                    pending_value["action_hex"],
                    "pending action",
                ),
                history=packet_from_hex(
                    pending_value["history_hex"],
                    "pending history",
                ),
                goal=required_packet_from_hex(
                    pending_value["goal_hex"],
                    "pending goal",
                ),
                prediction=copy.deepcopy(dict(prediction)),
                decision=copy.deepcopy(dict(decision)),
                event_sequence=pending_sequence,
                episode_index=pending_episode,
                pre_state_sha256=pending_pre_state,
                episode_start_state_sha256=pending_episode_start,
            )
            if pending.episode_index != episode:
                raise CheckpointError("pending decision belongs to another episode")
            if pending.event_sequence != sequence:
                raise CheckpointError(
                    "pending decision is not the latest event"
                )
            if pending.episode_start_state_sha256 != episode_start:
                raise CheckpointError(
                    "pending decision episode entry identity mismatch"
                )
            if pending.history != history:
                raise CheckpointError(
                    "pending decision history differs from protocol history"
                )
            if pending.observation != current:
                raise CheckpointError("pending observation differs from current observation")
            if canonical_packet(pending.action) not in attempted:
                raise CheckpointError("pending action is absent from attempted actions")
            if pending.pre_state_sha256 != self.fingerprint():
                raise CheckpointError("pending decision field identity mismatch")
            if attempted_value != sorted(action.hex() for action in attempted):
                raise CheckpointError(
                    "attempted actions are not canonically encoded"
                )
            if (
                decision.get("schema") != _DECISION_SCHEMA
                or decision.get("operator_id") != _OPERATOR_ID
                or decision.get("policy") != self.profile.policy
                or decision.get("event_sequence") != pending.event_sequence
                or decision.get("episode_index") != pending.episode_index
                or decision.get("action_hex") != pending.action.hex()
                or decision.get("goal_hex") != pending.goal.hex()
                or decision.get("pre_consequence_state_sha256")
                != pending.pre_state_sha256
            ):
                raise CheckpointError(
                    "pending decision receipt is inconsistent"
                )
            if prediction.get("state_sha256") != pending.pre_state_sha256:
                raise CheckpointError(
                    "pending prediction field identity mismatch"
                )
        self._episode_index = episode
        self._event_sequence = sequence
        self._current_observation = current
        self._history = history
        self._attempted_actions = attempted
        self._pending = pending
        self._episode_start_state_sha256 = episode_start

    def save(self, path: Path | str) -> str:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = self.checkpoint_bytes()
        handle = tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        )
        temporary = Path(handle.name)
        try:
            with handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return _sha256(payload)

    @classmethod
    def load(
        cls,
        path: Path | str,
        *,
        expected_profile: CausalProfile | None = None,
    ) -> "CausalEventLearner":
        return cls.restore(
            Path(path).read_bytes(), expected_profile=expected_profile
        )


__all__ = [
    "CausalEventLearner",
    "CausalProfile",
]
