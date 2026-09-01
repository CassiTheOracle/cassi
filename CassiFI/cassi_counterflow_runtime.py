from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

import torch

from cassi_bilateral_counterflow import (
    BilateralCounterflowConfig,
    BilateralCounterflowController,
)
from cassi_counterflow_reasoner import (
    MnemicThalamusConstraint,
    ThalamusPolicy,
    TypedActionDescriptor,
    encode_mnemic_address,
    propose_predicted_action,
    propose_typed_actions,
    render_symbolic_trajectory,
    start_mnemic_thalamus_thought,
)
from cassi_qi_field import QiFieldError, QiFieldState


DERIVED_COUNTERFLOW_SCHEMA = "cassi.counterflow.derived-runtime.v2"
DERIVED_COUNTERFLOW_SCHEMA_VERSION = 2
_MAX_OBSERVATIONS = 32
_HEX_ADDRESS = re.compile(r"[0-9a-f]{32}\Z")
_HEX_REVISION = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class _Identity:
    record_id: str
    address: bytes
    revision: str
    byte_start: int
    byte_end: int
    semantic_kind: str


@dataclass(frozen=True, slots=True)
class _ActionEffect:
    record_id: str
    before_revision: str
    after_revision: str
    semantic_kind: str
    byte_start: int
    byte_end: int


@dataclass(frozen=True, slots=True)
class _Action:
    action_id: str
    kind: str
    required_authority: float
    reversible: bool
    effects: tuple[_ActionEffect, ...]


@dataclass(frozen=True, slots=True)
class _Observation:
    observation_id: str
    before: _Identity
    after: _Identity
    symbol: str
    action: _Action | None
    outcome: str | None


@dataclass(frozen=True, slots=True)
class _ObservedCommit:
    observation: _Observation
    stream_id: str
    sequence: int
    event_id: str
    status: str
    authorization_path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _TrajectorySlot:
    identity: _Identity
    mask: tuple[float, ...]
    authority: float
    required: bool


@dataclass(frozen=True, slots=True)
class _PolicyInput:
    eligible_observation_ids: tuple[str, ...]
    permitted_action_kinds: tuple[str, ...]
    authority: float
    authorization_path: tuple[str, ...]


@dataclass(slots=True)
class _LearnedCompanion:
    controller: BilateralCounterflowController
    state: QiFieldState
    observation_basins: dict[str, int]
    basin_observations: dict[int, list[str]]
    symbols: dict[int, str]
    action_catalog: dict[int, TypedActionDescriptor]
    training: list[dict[str, Any]]
    checkpoint_sha256: str


def _exact_keys(
    value: object,
    *,
    required: set[str],
    optional: set[str] | frozenset[str] = frozenset(),
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise QiFieldError(f"{label} must be an object")
    keys = set(value)
    missing = required - keys
    extra = keys - required - optional
    if missing or extra:
        raise QiFieldError(
            f"{label} keys are invalid: missing={sorted(missing)}, extra={sorted(extra)}"
        )
    return value


def _bounded_text(value: object, *, label: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise QiFieldError(f"{label} must be bounded nonempty text")
    return value


def _address_for(
    record_id: str,
    revision: str,
    start: int,
    end: int,
    semantic_kind: str,
) -> bytes:
    encoded = json.dumps(
        [
            "cassicore.mnemic.counterflow-address.v1",
            record_id,
            revision,
            start,
            end,
            semantic_kind,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).digest()[:16]


def _identity(value: object, *, label: str) -> _Identity:
    item = _exact_keys(
        value,
        required={
            "record_id",
            "address",
            "revision",
            "start_byte",
            "end_byte",
            "semantic_kind",
        },
        label=label,
    )
    record_id = _bounded_text(item["record_id"], label=f"{label}.record_id")
    address_text = item["address"]
    if not isinstance(address_text, str) or _HEX_ADDRESS.fullmatch(address_text) is None:
        raise QiFieldError(f"{label}.address must be 16 lowercase hexadecimal bytes")
    revision = item["revision"]
    if not isinstance(revision, str) or _HEX_REVISION.fullmatch(revision) is None:
        raise QiFieldError(f"{label}.revision must be a lowercase SHA-256 digest")
    start = item["start_byte"]
    end = item["end_byte"]
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or end < start
    ):
        raise QiFieldError(f"{label} must contain an ordered exact byte span")
    semantic_kind = _bounded_text(
        item["semantic_kind"],
        label=f"{label}.semantic_kind",
    )
    address = bytes.fromhex(address_text)
    if address != _address_for(record_id, revision, start, end, semantic_kind):
        raise QiFieldError(f"{label}.address does not match its exact record provenance")
    return _Identity(
        record_id=record_id,
        address=address,
        revision=revision,
        byte_start=start,
        byte_end=end,
        semantic_kind=semantic_kind,
    )


def _identity_payload(identity: _Identity) -> dict[str, Any]:
    return {
        "record_id": identity.record_id,
        "address": identity.address.hex(),
        "revision": identity.revision,
        "start_byte": identity.byte_start,
        "end_byte": identity.byte_end,
        "semantic_kind": identity.semantic_kind,
    }


def _action_effect(value: object, *, label: str) -> _ActionEffect:
    item = _exact_keys(
        value,
        required={
            "record_id",
            "before_revision",
            "after_revision",
            "semantic_kind",
            "start_byte",
            "end_byte",
        },
        label=label,
    )
    before_revision = item["before_revision"]
    after_revision = item["after_revision"]
    if (
        not isinstance(before_revision, str)
        or _HEX_REVISION.fullmatch(before_revision) is None
        or not isinstance(after_revision, str)
        or _HEX_REVISION.fullmatch(after_revision) is None
    ):
        raise QiFieldError(f"{label} revisions must be lowercase SHA-256 digests")
    start = item["start_byte"]
    end = item["end_byte"]
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or end < start
    ):
        raise QiFieldError(f"{label} must contain an ordered exact byte span")
    return _ActionEffect(
        record_id=_bounded_text(item["record_id"], label=f"{label}.record_id"),
        before_revision=before_revision,
        after_revision=after_revision,
        semantic_kind=_bounded_text(
            item["semantic_kind"],
            label=f"{label}.semantic_kind",
        ),
        byte_start=start,
        byte_end=end,
    )


def _action_effect_payload(effect: _ActionEffect) -> dict[str, Any]:
    return {
        "record_id": effect.record_id,
        "before_revision": effect.before_revision,
        "after_revision": effect.after_revision,
        "semantic_kind": effect.semantic_kind,
        "start_byte": effect.byte_start,
        "end_byte": effect.byte_end,
    }


def _action(value: object, *, label: str) -> _Action:
    item = _exact_keys(
        value,
        required={"id", "kind", "required_authority", "reversible"},
        optional={"effects"},
        label=label,
    )
    authority = item["required_authority"]
    if (
        isinstance(authority, bool)
        or not isinstance(authority, (int, float))
        or not math.isfinite(float(authority))
        or not 0.0 <= float(authority) <= 1.0
    ):
        raise QiFieldError(f"{label}.required_authority must be finite in [0, 1]")
    reversible = item["reversible"]
    if not isinstance(reversible, bool):
        raise QiFieldError(f"{label}.reversible must be boolean")
    effects = item.get("effects", ())
    if (
        not isinstance(effects, Sequence)
        or isinstance(effects, (str, bytes))
        or len(effects) > 32
    ):
        raise QiFieldError(f"{label}.effects must be a bounded array")
    return _Action(
        action_id=_bounded_text(item["id"], label=f"{label}.id"),
        kind=_bounded_text(item["kind"], label=f"{label}.kind"),
        required_authority=float(authority),
        reversible=reversible,
        effects=tuple(
            _action_effect(effect, label=f"{label}.effects[{index}]")
            for index, effect in enumerate(effects)
        ),
    )


def _observation(value: object, *, position: int) -> _Observation:
    label = f"observations[{position}]"
    item = _exact_keys(
        value,
        required={"id", "before", "after", "symbol"},
        optional={"action", "outcome"},
        label=label,
    )
    action_value = item.get("action")
    outcome = item.get("outcome")
    if outcome not in {None, "completed", "error"}:
        raise QiFieldError(f"{label}.outcome must be completed or error")
    return _Observation(
        observation_id=_bounded_text(item["id"], label=f"{label}.id"),
        before=_identity(item["before"], label=f"{label}.before"),
        after=_identity(item["after"], label=f"{label}.after"),
        symbol=_bounded_text(item["symbol"], label=f"{label}.symbol"),
        action=None if action_value is None else _action(action_value, label=f"{label}.action"),
        outcome=outcome,
    )


def _observations(value: object) -> tuple[_Observation, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise QiFieldError("observations must be an array")
    if len(value) > _MAX_OBSERVATIONS:
        raise QiFieldError(f"observations may contain at most {_MAX_OBSERVATIONS} items")
    observations = tuple(
        _observation(item, position=position) for position, item in enumerate(value)
    )
    ids = tuple(item.observation_id for item in observations)
    if len(set(ids)) != len(ids):
        raise QiFieldError("observation ids must be unique")
    return observations


def _slot(value: object, *, position: int) -> _TrajectorySlot:
    label = f"trajectory[{position}]"
    identity_keys = (
        "record_id",
        "address",
        "revision",
        "start_byte",
        "end_byte",
        "semantic_kind",
    )
    item = _exact_keys(
        value,
        required={*identity_keys, "mask", "authority", "required"},
        label=label,
    )
    identity = _identity({key: item[key] for key in identity_keys}, label=label)
    mask_value = item["mask"]
    if (
        not isinstance(mask_value, Sequence)
        or isinstance(mask_value, (str, bytes))
        or len(mask_value) != 4
    ):
        raise QiFieldError(f"{label}.mask must contain four numeric components")
    try:
        mask = tuple(float(component) for component in mask_value)
    except (TypeError, ValueError) as error:
        raise QiFieldError(f"{label}.mask must contain four numeric components") from error
    if any(not math.isfinite(component) or not 0.0 <= component <= 1.0 for component in mask):
        raise QiFieldError(f"{label}.mask components must be finite in [0, 1]")
    authority = item["authority"]
    if (
        isinstance(authority, bool)
        or not isinstance(authority, (int, float))
        or not math.isfinite(float(authority))
        or not 0.0 <= float(authority) <= 1.0
    ):
        raise QiFieldError(f"{label}.authority must be finite in [0, 1]")
    required = item["required"]
    if not isinstance(required, bool):
        raise QiFieldError(f"{label}.required must be boolean")
    return _TrajectorySlot(identity, mask, float(authority), required)


def _string_tuple(value: object, *, label: str, allow_empty: bool) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise QiFieldError(f"{label} must be an array")
    result = tuple(_bounded_text(item, label=f"{label}[]") for item in value)
    if not allow_empty and not result:
        raise QiFieldError(f"{label} may not be empty")
    if len(set(result)) != len(result):
        raise QiFieldError(f"{label} may not contain duplicates")
    return result


def _policy(value: object, observations: Sequence[_Observation]) -> _PolicyInput:
    item = _exact_keys(
        value,
        required={
            "eligible_observation_ids",
            "permitted_action_kinds",
            "authority",
            "authorization_path",
        },
        label="policy",
    )
    eligible = _string_tuple(
        item["eligible_observation_ids"],
        label="policy.eligible_observation_ids",
        allow_empty=not observations,
    )
    known = {observation.observation_id for observation in observations}
    unknown = set(eligible) - known
    if unknown:
        raise QiFieldError(f"policy references unknown observations: {sorted(unknown)}")
    authority = item["authority"]
    if (
        isinstance(authority, bool)
        or not isinstance(authority, (int, float))
        or not math.isfinite(float(authority))
        or not 0.0 <= float(authority) <= 1.0
    ):
        raise QiFieldError("policy.authority must be finite in [0, 1]")
    return _PolicyInput(
        eligible_observation_ids=eligible,
        permitted_action_kinds=_string_tuple(
            item["permitted_action_kinds"],
            label="policy.permitted_action_kinds",
            allow_empty=True,
        ),
        authority=float(authority),
        authorization_path=_string_tuple(
            item["authorization_path"],
            label="policy.authorization_path",
            allow_empty=True,
        ),
    )


def _checkpoint_sha256(
    controller: BilateralCounterflowController,
    state: QiFieldState,
) -> str:
    controller.validate_state(state)
    field = state.field.detach().cpu().contiguous()
    identity = json.dumps(
        {
            "config_fingerprint": controller.config.fingerprint(),
            "dtype": str(field.dtype),
            "shape": list(field.shape),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    digest = hashlib.sha256(identity)
    digest.update(b"\x00")
    digest.update(field.numpy().tobytes(order="C"))
    return digest.hexdigest()


def _vector_residual(predicted: torch.Tensor, expected: torch.Tensor) -> float:
    numerator = (predicted - expected).abs().square().mean().sqrt()
    denominator = expected.abs().square().mean().sqrt().clamp_min(
        torch.finfo(expected.real.dtype).eps
    )
    return float((numerator / denominator).item())


class DerivedCounterflowRuntime:
    """Ephemeral counterflow derived only from exact observed transitions."""

    def __init__(self, *, device: str | torch.device = "cpu") -> None:
        self.device = torch.device(device)
        self.controller = BilateralCounterflowController(
            BilateralCounterflowConfig(
                slot_count=8,
                max_basins=_MAX_OBSERVATIONS + 1,
            )
        )

    @property
    def config_fingerprint(self) -> str:
        return self.controller.config.fingerprint()

    def initial_state(self) -> QiFieldState:
        return self.controller.initial_state(device=self.device, dtype=torch.float32)

    def state_sha256(self, state: QiFieldState) -> str:
        return _checkpoint_sha256(self.controller, state)

    def dump_state_bytes(self, state: QiFieldState) -> bytes:
        return self.controller.dump_state_bytes(state)

    def load_state_bytes(self, payload: bytes) -> QiFieldState:
        return self.controller.load_state_bytes(payload, device=self.device)

    def observed_commit(self, request: object) -> _ObservedCommit:
        root = _exact_keys(
            request,
            required={"observation", "acknowledgment"},
            label="counterflow commit",
        )
        observation = _observation(root["observation"], position=0)
        acknowledgment = _exact_keys(
            root["acknowledgment"],
            required={
                "stream_id",
                "sequence",
                "event_id",
                "status",
                "before_revision",
                "after_revision",
                "authorization_path",
            },
            label="counterflow commit acknowledgment",
        )
        stream_id = _bounded_text(
            acknowledgment["stream_id"],
            label="counterflow commit acknowledgment.stream_id",
        )
        sequence = acknowledgment["sequence"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise QiFieldError("counterflow commit acknowledgment.sequence must be positive")
        event_id = _bounded_text(
            acknowledgment["event_id"],
            label="counterflow commit acknowledgment.event_id",
        )
        if _HEX_REVISION.fullmatch(event_id) is None or event_id != observation.observation_id:
            raise QiFieldError("counterflow commit event identity does not match its observation")
        if acknowledgment["before_revision"] != observation.before.revision:
            raise QiFieldError("counterflow commit before revision does not match")
        if acknowledgment["after_revision"] != observation.after.revision:
            raise QiFieldError("counterflow commit after revision does not match")
        status = _bounded_text(
            acknowledgment["status"],
            label="counterflow commit acknowledgment.status",
        )
        authorization_path = _string_tuple(
            acknowledgment["authorization_path"],
            label="counterflow commit acknowledgment.authorization_path",
            allow_empty=False,
        )
        if observation.action is None:
            if (
                observation.symbol != "mnemic:update"
                or observation.outcome is not None
                or status != "committed"
            ):
                raise QiFieldError("non-action counterflow commits require an exact committed mnemic update")
        elif observation.outcome not in {"completed", "error"} or status != observation.outcome:
            raise QiFieldError("action counterflow commits require a matching completed or error acknowledgment")
        return _ObservedCommit(
            observation=observation,
            stream_id=stream_id,
            sequence=sequence,
            event_id=event_id,
            status=status,
            authorization_path=authorization_path,
        )

    def consolidate_observed(
        self,
        state: QiFieldState,
        commit: _ObservedCommit,
    ) -> tuple[QiFieldState, dict[str, Any]]:
        self.controller.validate_state(state)
        before_sha256 = self.state_sha256(state)
        observation = commit.observation
        before = encode_mnemic_address(
            observation.before.address,
            device=self.device,
            dtype=torch.float32,
        ).unsqueeze(0)
        after = encode_mnemic_address(
            observation.after.address,
            device=self.device,
            dtype=torch.float32,
        ).unsqueeze(0)
        result, receipt = self.controller.observe_transitions(state, before, after)
        return result, {
            "schema": "cassi.counterflow.observed-commit-receipt.v1",
            "stream_id": commit.stream_id,
            "sequence": commit.sequence,
            "event_id": commit.event_id,
            "status": commit.status,
            "decision": receipt.decision,
            "basin_id": receipt.basin_id,
            "support_before": receipt.support_before,
            "support_after": receipt.support_after,
            "counterflow_state_in_sha256": before_sha256,
            "counterflow_state_out_sha256": self.state_sha256(result),
        }

    def status(self) -> dict[str, Any]:
        return {
            "schema": DERIVED_COUNTERFLOW_SCHEMA,
            "schema_version": DERIVED_COUNTERFLOW_SCHEMA_VERSION,
            "mode": "derived_nonpersistent",
            "persistent_state": False,
            "latent_codec": "exact_mnemic_address_128",
            "device": str(self.device),
            "slot_range": [2, 8],
            "observation_limit": _MAX_OBSERVATIONS,
            "prediction": "held_out_field_operator",
        }

    def plan(
        self,
        request: object,
        *,
        primary_field_sha256: str,
        counterflow_state: QiFieldState | None = None,
    ) -> dict[str, Any]:
        if _HEX_REVISION.fullmatch(primary_field_sha256) is None:
            raise QiFieldError("primary_field_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(request, Mapping):
            raise QiFieldError("counterflow request must be an object")
        mode = request.get("mode")
        if mode == "plan":
            return self._plan(
                request,
                primary_field_sha256=primary_field_sha256,
                counterflow_state=counterflow_state,
            )
        if mode == "predict":
            return self._predict(
                request,
                primary_field_sha256=primary_field_sha256,
                counterflow_state=counterflow_state,
            )
        raise QiFieldError("counterflow request mode must be plan or predict")

    def _learn(
        self,
        observations: Sequence[_Observation],
        *,
        slot_count: int,
    ) -> _LearnedCompanion:
        controller = BilateralCounterflowController(
            BilateralCounterflowConfig(
                slot_count=slot_count,
                max_basins=max(8, len(observations) + 1),
            )
        )
        state = controller.initial_state(device=self.device, dtype=torch.float32)
        observation_basins: dict[str, int] = {}
        basin_observations: dict[int, list[str]] = {}
        symbols: dict[int, str] = {}
        conflicting_action_basins: set[int] = set()
        action_catalog: dict[int, TypedActionDescriptor] = {}
        training: list[dict[str, Any]] = []
        for observation in observations:
            before = encode_mnemic_address(
                observation.before.address,
                device=self.device,
                dtype=torch.float32,
            ).unsqueeze(0)
            after = encode_mnemic_address(
                observation.after.address,
                device=self.device,
                dtype=torch.float32,
            ).unsqueeze(0)
            state, receipt = controller.observe_transitions(state, before, after)
            training.append(
                {
                    "observation_id": observation.observation_id,
                    "record_id": observation.before.record_id,
                    "decision": receipt.decision,
                    "basin_id": receipt.basin_id,
                    "outcome": observation.outcome,
                    "support_after": receipt.support_after,
                    "best_residual": (
                        receipt.best_residual
                        if math.isfinite(receipt.best_residual)
                        else None
                    ),
                }
            )
            if receipt.basin_id is None:
                continue
            basin_id = receipt.basin_id
            observation_basins[observation.observation_id] = basin_id
            basin_observations.setdefault(basin_id, []).append(observation.observation_id)
            symbols.setdefault(basin_id, observation.symbol)
            if observation.action is not None:
                descriptor = TypedActionDescriptor(
                    basin_id=basin_id,
                    action_id=observation.action.action_id,
                    kind=observation.action.kind,
                    required_authority=observation.action.required_authority,
                    precondition_address=observation.before.address,
                    effect_address=observation.after.address,
                    reversible=observation.action.reversible,
                )
                if basin_id in conflicting_action_basins:
                    continue
                existing = action_catalog.get(basin_id)
                if existing is not None and existing != descriptor:
                    action_catalog.pop(basin_id)
                    conflicting_action_basins.add(basin_id)
                else:
                    action_catalog[basin_id] = descriptor
        return _LearnedCompanion(
            controller=controller,
            state=state,
            observation_basins=observation_basins,
            basin_observations=basin_observations,
            symbols=symbols,
            action_catalog=action_catalog,
            training=training,
            checkpoint_sha256=_checkpoint_sha256(controller, state),
        )

    def _bind(
        self,
        observations: Sequence[_Observation],
        state: QiFieldState,
    ) -> _LearnedCompanion:
        self.controller.validate_state(state)
        observation_basins: dict[str, int] = {}
        basin_observations: dict[int, list[str]] = {}
        symbols: dict[int, str] = {}
        conflicting_action_basins: set[int] = set()
        action_catalog: dict[int, TypedActionDescriptor] = {}
        training: list[dict[str, Any]] = []
        for observation in observations:
            before = encode_mnemic_address(
                observation.before.address,
                device=self.device,
                dtype=torch.float32,
            ).unsqueeze(0)
            after = encode_mnemic_address(
                observation.after.address,
                device=self.device,
                dtype=torch.float32,
            ).unsqueeze(0)
            _, receipt = self.controller.observe_transitions(state, before, after)
            basin_id_value = receipt.basin_id
            matched = receipt.decision == "reinforce" and basin_id_value is not None
            training.append(
                {
                    "observation_id": observation.observation_id,
                    "record_id": observation.before.record_id,
                    "decision": "bound" if matched else "unseen",
                    "basin_id": basin_id_value if matched else None,
                    "outcome": observation.outcome,
                    "support_after": receipt.support_before if matched else 0,
                    "best_residual": (
                        receipt.best_residual
                        if math.isfinite(receipt.best_residual)
                        else None
                    ),
                }
            )
            if not matched or basin_id_value is None:
                continue
            basin_id = int(basin_id_value)
            observation_basins[observation.observation_id] = basin_id
            basin_observations.setdefault(basin_id, []).append(observation.observation_id)
            symbols.setdefault(basin_id, observation.symbol)
            if observation.action is not None:
                descriptor = TypedActionDescriptor(
                    basin_id=basin_id,
                    action_id=observation.action.action_id,
                    kind=observation.action.kind,
                    required_authority=observation.action.required_authority,
                    precondition_address=observation.before.address,
                    effect_address=observation.after.address,
                    reversible=observation.action.reversible,
                )
                existing = action_catalog.get(basin_id)
                if basin_id in conflicting_action_basins:
                    continue
                if existing is not None and existing != descriptor:
                    action_catalog.pop(basin_id)
                    conflicting_action_basins.add(basin_id)
                else:
                    action_catalog[basin_id] = descriptor
        return _LearnedCompanion(
            controller=self.controller,
            state=state,
            observation_basins=observation_basins,
            basin_observations=basin_observations,
            symbols=symbols,
            action_catalog=action_catalog,
            training=training,
            checkpoint_sha256=self.state_sha256(state),
        )

    @staticmethod
    def _eligible_basins(
        learned: _LearnedCompanion,
        policy: _PolicyInput,
    ) -> tuple[int, ...]:
        return tuple(
            dict.fromkeys(
                learned.observation_basins[observation_id]
                for observation_id in policy.eligible_observation_ids
                if observation_id in learned.observation_basins
            )
        )

    @staticmethod
    def _no_data(
        *,
        mode: str,
        primary_field_sha256: str,
        current: _Identity | None = None,
    ) -> dict[str, Any]:
        return {
            "schema": DERIVED_COUNTERFLOW_SCHEMA,
            "schema_version": DERIVED_COUNTERFLOW_SCHEMA_VERSION,
            "mode": mode,
            "status": "no_transition_data",
            "derived": True,
            "persistent_state": False,
            "primary_field_sha256": primary_field_sha256,
            "observation_count": 0,
            **({"current": _identity_payload(current)} if current is not None else {}),
            "plan": None,
            "prediction": None,
            "evaluation": None,
            "symbolic": None,
            "action_proposal": None,
            "macro": None,
            "abstention": {
                "code": "no_transition_data",
                "evidence": {"observation_count": 0},
            },
        }

    def _plan(
        self,
        request: Mapping[str, Any],
        *,
        primary_field_sha256: str,
        counterflow_state: QiFieldState | None,
    ) -> dict[str, Any]:
        root = _exact_keys(
            request,
            required={"mode", "observations", "trajectory", "policy"},
            optional={"consolidate_macro"},
            label="counterflow request",
        )
        observations = _observations(root["observations"])
        if not observations:
            return self._no_data(
                mode="plan",
                primary_field_sha256=primary_field_sha256,
            )

        raw_trajectory = root["trajectory"]
        if not isinstance(raw_trajectory, Sequence) or isinstance(raw_trajectory, (str, bytes)):
            raise QiFieldError("trajectory must be an array")
        if not 2 <= len(raw_trajectory) <= 8:
            raise QiFieldError("trajectory must contain two through eight slots")
        trajectory = tuple(
            _slot(value, position=position)
            for position, value in enumerate(raw_trajectory)
        )
        policy_input = _policy(root["policy"], observations)
        learned = (
            self._learn(observations, slot_count=len(trajectory))
            if counterflow_state is None
            else self._bind(observations, counterflow_state)
        )
        eligible_basins = self._eligible_basins(learned, policy_input)
        if not eligible_basins:
            return {
                "schema": DERIVED_COUNTERFLOW_SCHEMA,
                "schema_version": DERIVED_COUNTERFLOW_SCHEMA_VERSION,
                "mode": "plan",
                "status": "no_eligible_transition_data",
                "derived": True,
                "persistent_state": False,
                "primary_field_sha256": primary_field_sha256,
                "observation_count": len(observations),
                "training": learned.training,
                "companion_checkpoint_sha256": learned.checkpoint_sha256,
                "plan": None,
                "prediction": None,
                "evaluation": None,
                "symbolic": None,
                "action_proposal": None,
                "macro": None,
                "abstention": {
                    "code": "no_eligible_transition_data",
                    "evidence": {"observation_count": len(observations)},
                },
            }

        candidates = tuple(
            MnemicThalamusConstraint(
                record_id=slot.identity.record_id,
                address=slot.identity.address,
                revision=slot.identity.revision,
                byte_start=slot.identity.byte_start,
                byte_end=slot.identity.byte_end,
                slot=position,
                value=tuple(
                    complex(value)
                    for value in encode_mnemic_address(
                        slot.identity.address,
                        device="cpu",
                        dtype=torch.float32,
                    ).tolist()
                ),
                mask=slot.mask,
                authority=slot.authority,
                required=slot.required,
                semantic_kind=slot.identity.semantic_kind,
            )
            for position, slot in enumerate(trajectory)
        )
        policy = ThalamusPolicy(
            eligible_basins=eligible_basins,
            permitted_action_kinds=policy_input.permitted_action_kinds,
            authority=policy_input.authority,
            authorization_path=policy_input.authorization_path,
        )
        active = start_mnemic_thalamus_thought(
            learned.controller,
            learned.state,
            candidates,
            active_slots=len(trajectory),
            policy=policy,
        )
        closed, trace = learned.controller.run_until_closed(active)
        final = trace[-1]
        frozen = all(
            step.basin_region_sha256 == final.basin_region_sha256 for step in trace
        )
        symbolic: dict[str, Any] | None = None
        action_proposal: dict[str, Any] | None = None
        macro: dict[str, Any] | None = None
        if final.status == "settled":
            rendered = render_symbolic_trajectory(
                learned.controller,
                closed,
                learned.symbols,
                source_addresses=tuple(slot.identity.address for slot in trajectory),
            )
            symbolic = {
                "basin_path": list(rendered.basin_path),
                "symbols": list(rendered.symbols),
                "text": rendered.text,
                "source_addresses": [
                    value.hex() for value in rendered.source_addresses
                ],
                "source_record_ids": [
                    slot.identity.record_id for slot in trajectory
                ],
                "field_sha256": rendered.field_sha256,
            }
            if learned.action_catalog and all(
                basin_id in learned.action_catalog for basin_id in rendered.basin_path
            ):
                proposal = propose_typed_actions(
                    learned.controller,
                    closed,
                    learned.action_catalog,
                    policy=policy,
                    start_address=trajectory[0].identity.address,
                    goal_address=trajectory[-1].identity.address,
                )
                action_proposal = {
                    "inert": True,
                    "basin_path": list(proposal.basin_path),
                    "action_ids": [value.action_id for value in proposal.actions],
                    "authorization_path": list(proposal.authorization_path),
                    "field_sha256": proposal.field_sha256,
                }
            if root.get("consolidate_macro", False):
                if not isinstance(root["consolidate_macro"], bool):
                    raise QiFieldError("consolidate_macro must be boolean")
                _, receipt = learned.controller.consolidate_plan(closed)
                macro = {
                    "persisted": False,
                    "decision": receipt.decision,
                    "basin_id": receipt.basin_id,
                    "constituents": list(receipt.constituents),
                    "constituent_generations": list(receipt.constituent_generations),
                    "support_after": receipt.support_after,
                    "field_sha256": receipt.field_sha256,
                }

        winning_observations = [
            learned.basin_observations.get(basin_id, [])
            for basin_id in final.winning_basins
        ]
        return {
            "schema": DERIVED_COUNTERFLOW_SCHEMA,
            "schema_version": DERIVED_COUNTERFLOW_SCHEMA_VERSION,
            "mode": "plan",
            "status": final.status,
            "derived": True,
            "persistent_state": False,
            "primary_field_sha256": primary_field_sha256,
            "observation_count": len(observations),
            "training": learned.training,
            "companion_shape": list(learned.state.field.shape),
            "companion_checkpoint_sha256": learned.checkpoint_sha256,
            "inference_memory_frozen": frozen,
            "plan": {
                "winning_basins": list(final.winning_basins),
                "winning_observation_ids": winning_observations,
                "search_mode": final.search_mode,
                "beam_widths": list(final.beam_widths),
                "evaluated_plan_extensions": final.evaluated_plan_extensions,
                "best_plan_residual": final.best_plan_residual,
                "valid_plan_count": final.valid_plan_count,
                "constraint_residual": final.constraint_residual,
                "iterations": len(trace),
            },
            "prediction": None,
            "evaluation": None,
            "symbolic": symbolic,
            "action_proposal": action_proposal,
            "macro": macro,
            "abstention": None,
        }

    def _predict(
        self,
        request: Mapping[str, Any],
        *,
        primary_field_sha256: str,
        counterflow_state: QiFieldState | None,
    ) -> dict[str, Any]:
        root = _exact_keys(
            request,
            required={"mode", "observations", "current", "policy"},
            optional={
                "expected",
                "observed_outcome",
                "failure_inhibition",
                "trajectory_mode",
            },
            label="counterflow request",
        )
        observations = _observations(root["observations"])
        current = _identity(root["current"], label="current")
        expected = (
            None
            if "expected" not in root
            else _identity(root["expected"], label="expected")
        )
        observed_outcome = root.get("observed_outcome")
        if observed_outcome not in {None, "completed", "error"}:
            raise QiFieldError("observed_outcome must be completed or error")
        failure_inhibition = root.get("failure_inhibition", False)
        if not isinstance(failure_inhibition, bool):
            raise QiFieldError("failure_inhibition must be boolean")
        trajectory_mode = root.get("trajectory_mode")
        if trajectory_mode not in {None, "next-action"}:
            raise QiFieldError("trajectory_mode must be next-action")
        policy_input = _policy(root["policy"], observations)
        if not observations:
            return self._no_data(
                mode="predict",
                primary_field_sha256=primary_field_sha256,
                current=current,
            )

        learned = (
            self._learn(observations, slot_count=4)
            if counterflow_state is None
            else self._bind(observations, counterflow_state)
        )
        eligible_basins = self._eligible_basins(learned, policy_input)
        if not eligible_basins:
            return {
                "schema": DERIVED_COUNTERFLOW_SCHEMA,
                "schema_version": DERIVED_COUNTERFLOW_SCHEMA_VERSION,
                "mode": "predict",
                "status": "no_eligible_transition_data",
                "derived": True,
                "persistent_state": False,
                "primary_field_sha256": primary_field_sha256,
                "observation_count": len(observations),
                "training": learned.training,
                "companion_checkpoint_sha256": learned.checkpoint_sha256,
                "current": _identity_payload(current),
                "prediction": None,
                "evaluation": None,
                "plan": None,
                "symbolic": None,
                "action_proposal": None,
                "macro": None,
                "inference_memory_frozen": True,
                "trajectory_mode": trajectory_mode,
                "inhibition": {
                    "enabled": failure_inhibition,
                    "failure_support": 0,
                    "success_support": 0,
                    "inhibited": False,
                },
                "abstention": {
                    "code": "no_eligible_transition_data",
                    "evidence": {"observation_count": len(observations)},
                },
            }

        policy = ThalamusPolicy(
            eligible_basins=eligible_basins,
            permitted_action_kinds=policy_input.permitted_action_kinds,
            authority=policy_input.authority,
            authorization_path=policy_input.authorization_path,
        )
        before_prediction_sha256 = _checkpoint_sha256(
            learned.controller,
            learned.state,
        )
        receipt = learned.controller.predict_transition(
            learned.state,
            encode_mnemic_address(
                current.address,
                device=self.device,
                dtype=torch.float32,
            ),
            eligible_basins=eligible_basins,
        )
        inference_frozen = before_prediction_sha256 == _checkpoint_sha256(
            learned.controller,
            learned.state,
        )

        source_ids = (
            []
            if receipt.basin_id is None
            else learned.basin_observations.get(receipt.basin_id, [])
        )
        source_observations = [
            observation
            for observation in observations
            if observation.observation_id in source_ids
        ]
        exact_effects = {observation.after for observation in source_observations}
        exact_effect = next(iter(exact_effects)) if len(exact_effects) == 1 else None
        source_outcomes = [observation.outcome for observation in source_observations]
        failure_support = sum(outcome == "error" for outcome in source_outcomes)
        success_support = sum(outcome != "error" for outcome in source_outcomes)
        failure_inhibited = (
            failure_inhibition
            and failure_support > 0
            and failure_support >= success_support
        )
        action_effect_sets = {
            observation.action.effects
            for observation in source_observations
            if observation.action is not None
        }
        exact_action_effects = (
            next(iter(action_effect_sets)) if len(action_effect_sets) == 1 else None
        )
        prediction = None
        if receipt.status != "no_transition_data":
            prediction = {
                "basin_id": receipt.basin_id,
                "source_observation_ids": source_ids,
                "source_record_ids": list(
                    dict.fromkeys(
                        observation.before.record_id
                        for observation in source_observations
                    )
                ),
                "value": (
                    None
                    if receipt.value is None
                    else [
                        [component.real, component.imag]
                        for component in receipt.value
                    ]
                ),
                "score": receipt.score,
                "cycle_residual": receipt.cycle_residual,
                "support": receipt.support,
                "dispersion": receipt.dispersion,
                "margin": receipt.margin,
                "exact_effect": (
                    None if exact_effect is None else _identity_payload(exact_effect)
                ),
                "field_sha256": receipt.field_sha256,
            }

        evaluation = None
        if expected is not None:
            expected_value = encode_mnemic_address(
                expected.address,
                device=self.device,
                dtype=torch.float32,
            )
            current_value = encode_mnemic_address(
                current.address,
                device=self.device,
                dtype=torch.float32,
            )
            prediction_residual = None
            if receipt.value is not None:
                predicted_value = torch.tensor(
                    receipt.value,
                    device=self.device,
                    dtype=expected_value.dtype,
                )
                prediction_residual = _vector_residual(
                    predicted_value,
                    expected_value,
                )
            identity_residual = _vector_residual(current_value, expected_value)
            evaluation = {
                "expected": _identity_payload(expected),
                "prediction_residual": prediction_residual,
                "identity_baseline_residual": identity_residual,
                "improved_over_identity": (
                    None
                    if prediction_residual is None
                    else prediction_residual < identity_residual
                ),
                "observed_outcome": observed_outcome,
            }

        action_proposal = None
        descriptor = (
            learned.action_catalog.get(receipt.basin_id)
            if receipt.basin_id is not None
            else None
        )
        abstention: dict[str, Any] | None = None
        abstention_evidence = {
            "status": receipt.status,
            "support": receipt.support,
            "margin": receipt.margin,
            "failure_support": failure_support,
            "success_support": success_support,
        }
        if receipt.status != "predicted":
            abstention = {
                "code": (
                    "ambiguous_prediction"
                    if receipt.status == "ambiguous"
                    else "no_transition_data"
                ),
                "evidence": abstention_evidence,
            }
        elif observed_outcome == "error":
            abstention = {
                "code": "observed_action_error",
                "evidence": abstention_evidence,
            }
        elif not any(observation.action is not None for observation in source_observations):
            abstention = {
                "code": "prediction_only",
                "evidence": abstention_evidence,
            }
        elif failure_inhibited:
            abstention = {
                "code": "failure_inhibited",
                "evidence": abstention_evidence,
            }
        elif exact_effect is None:
            abstention = {
                "code": "nonunique_exact_effect",
                "evidence": abstention_evidence,
            }
        elif descriptor is None:
            abstention = {
                "code": "missing_action_descriptor",
                "evidence": abstention_evidence,
            }
        elif exact_action_effects is None:
            abstention = {
                "code": "action_effects_disagree",
                "evidence": abstention_evidence,
            }
        elif (
            descriptor.precondition_address != current.address
            or descriptor.effect_address != exact_effect.address
        ):
            abstention = {
                "code": "descriptor_mismatch",
                "evidence": abstention_evidence,
            }
        elif descriptor.kind not in policy_input.permitted_action_kinds:
            abstention = {
                "code": "action_kind_not_permitted",
                "evidence": abstention_evidence,
            }
        elif policy_input.authority < descriptor.required_authority:
            abstention = {
                "code": "insufficient_authority",
                "evidence": abstention_evidence,
            }
        elif not policy_input.authorization_path:
            abstention = {
                "code": "missing_authorization_path",
                "evidence": abstention_evidence,
            }
        else:
            proposal = propose_predicted_action(
                learned.controller,
                learned.state,
                descriptor,
                policy=policy,
                start_address=current.address,
                effect_address=exact_effect.address,
            )
            action_proposal = {
                "inert": True,
                "basin_path": list(proposal.basin_path),
                "action_ids": [value.action_id for value in proposal.actions],
                "action_kinds": [value.kind for value in proposal.actions],
                "precondition": _identity_payload(current),
                "predicted_effect": _identity_payload(exact_effect),
                "effects": [
                    _action_effect_payload(effect)
                    for effect in exact_action_effects
                ],
                "authorization_path": list(proposal.authorization_path),
                "field_sha256": proposal.field_sha256,
            }

        return {
            "schema": DERIVED_COUNTERFLOW_SCHEMA,
            "schema_version": DERIVED_COUNTERFLOW_SCHEMA_VERSION,
            "mode": "predict",
            "status": receipt.status,
            "derived": True,
            "persistent_state": False,
            "primary_field_sha256": primary_field_sha256,
            "observation_count": len(observations),
            "training": learned.training,
            "companion_shape": list(learned.state.field.shape),
            "companion_checkpoint_sha256": learned.checkpoint_sha256,
            "current": _identity_payload(current),
            "prediction": prediction,
            "evaluation": evaluation,
            "plan": None,
            "symbolic": None,
            "action_proposal": action_proposal,
            "macro": None,
            "inference_memory_frozen": inference_frozen,
            "trajectory_mode": trajectory_mode,
            "inhibition": {
                "enabled": failure_inhibition,
                "failure_support": failure_support,
                "success_support": success_support,
                "inhibited": failure_inhibited,
            },
            "abstention": abstention,
        }
