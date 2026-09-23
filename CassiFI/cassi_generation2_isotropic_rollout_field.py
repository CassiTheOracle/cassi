"""Generation-two isotropic rollout with a field-owned regime identity guard.

The V3 hierarchical field can release its radial/transverse departure after two
supporting calls even when both calls came from one chronological regime.  This
wrapper keeps the V3 adaptive coordinates, but appends a bounded identity
registry to the same float64 field tensor.  A rollout support increment is
accepted only for a previously unseen regime identity.  Repeated chunks of one
regime can continue fitting the shared isotropic coefficient, but cannot make
anisotropic support appear twice.

The registry is not a Python sidecar: it is checkpointed, hashed, validated,
and transported with the field tensor.  Regime identities are represented by a
48-bit digest token; the campaign binds the identity to the raw trajectory
manifest so the token is provenance rather than an unbound caller flag.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import torch
from torch import Tensor

from cassi_hierarchical_covariant_recurrent_field import (
    CovariantFieldError,
    CovariantForecast,
    CovariantFrame,
    HierarchicalCovariantFieldConfig,
    HierarchicalCovariantRecurrentField,
    RegimeCovariantState,
)


SCHEMA = "cassifi.generation2-isotropic-regime-guarded-field.v1"
_GUARD_MAGIC = 271828182.0
_GUARD_VERSION = 1.0
_REGISTRY_SLOTS = 8
_METADATA_WORDS = 4 + _REGISTRY_SLOTS
_EXTRA_MODES = 2
_MAX_EXACT_INTEGER = 2**53 - 1


@dataclass(frozen=True, slots=True)
class Generation2GuardedFieldConfig:
    """Static V3 law plus the bounded field-owned regime registry."""

    base: HierarchicalCovariantFieldConfig
    regime_slots: int = _REGISTRY_SLOTS

    def __post_init__(self) -> None:
        if not isinstance(self.base, HierarchicalCovariantFieldConfig):
            raise CovariantFieldError("base must be a hierarchical field configuration")
        if isinstance(self.regime_slots, bool) or not isinstance(self.regime_slots, int):
            raise CovariantFieldError("regime_slots must be an integer")
        if not 1 <= self.regime_slots <= _REGISTRY_SLOTS:
            raise CovariantFieldError(
                f"regime_slots must be in 1..{_REGISTRY_SLOTS}"
            )


class Generation2IsotropicRegimeGuardedField:
    """V3 field whose anisotropic support is unique-regime gated."""

    def __init__(self, config: Generation2GuardedFieldConfig) -> None:
        self.guarded_config = config
        self.base = HierarchicalCovariantRecurrentField(config.base)
        self.config = config.base
        self._base_shape = self.base.config.shape
        self._base_words = math.prod(self._base_shape)
        self._extra_words = 9 * _EXTRA_MODES
        self._metadata_offset = self._base_words
        self._metadata_end = self._metadata_offset + _METADATA_WORDS
        if self._metadata_end > self._base_words + self._extra_words:
            raise CovariantFieldError("guard metadata exceeds bounded field tail")
        self.shape = (
            self._base_shape[0],
            self._base_shape[1] + self._extra_words,
            self._base_shape[2],
        )

    @property
    def regime_slots(self) -> int:
        return self.guarded_config.regime_slots

    @property
    def _guard_slice(self) -> slice:
        return slice(self._metadata_offset, self._metadata_end)

    def _check_outer_tensor(self, state: RegimeCovariantState) -> np.ndarray:
        if not isinstance(state, RegimeCovariantState):
            raise CovariantFieldError("guarded state has the wrong type")
        field = state.field
        if (
            not isinstance(field, Tensor)
            or field.device.type != "cpu"
            or field.dtype != torch.float64
            or tuple(field.shape) != self.shape
            or field.requires_grad
        ):
            raise CovariantFieldError(
                "guarded field must be a non-gradient CPU float64 tensor with the configured shape"
            )
        flat = field.detach().numpy().reshape(-1)
        if not np.isfinite(flat).all():
            raise CovariantFieldError("guarded field contains nonfinite values")
        return flat

    def _base_state_from_flat(self, flat: np.ndarray) -> RegimeCovariantState:
        values = torch.from_numpy(
            np.asarray(flat[: self._base_words], dtype=np.float64).copy()
        ).reshape(self._base_shape)
        return RegimeCovariantState(field=values)

    def _base_state(self, state: RegimeCovariantState) -> RegimeCovariantState:
        flat = self._check_outer_tensor(state)
        base_state = self._base_state_from_flat(flat)
        self.base.validate_state(base_state)
        return base_state

    def _metadata(self, flat: np.ndarray) -> tuple[float, int, int, tuple[int, ...]]:
        guard = flat[self._guard_slice]
        if guard[0] != _GUARD_MAGIC or guard[1] != _GUARD_VERSION:
            raise CovariantFieldError("guard metadata header differs from configuration")
        support = float(guard[2])
        count = float(guard[3])
        if (
            support < 0.0
            or support > _MAX_EXACT_INTEGER
            or support != round(support)
            or count < 0.0
            or count > self.regime_slots
            or count != round(count)
        ):
            raise CovariantFieldError("guard metadata counters are invalid")
        token_count = int(count)
        tokens = tuple(int(round(value)) for value in guard[4 : 4 + self.regime_slots])
        if any(token <= 0 or token > _MAX_EXACT_INTEGER for token in tokens[:token_count]):
            raise CovariantFieldError("guard regime token is invalid")
        if len(set(tokens[:token_count])) != token_count:
            raise CovariantFieldError("guard regime tokens are not unique")
        if any(token != 0 for token in tokens[token_count:]):
            raise CovariantFieldError("guard regime registry has a nonempty gap")
        return support, int(support), token_count, tokens[:token_count]

    def validate_state(self, state: RegimeCovariantState) -> None:
        flat = self._check_outer_tensor(state)
        base_state = self._base_state_from_flat(flat)
        self.base.validate_state(base_state)
        _, support, _, _ = self._metadata(flat)
        base_flat = base_state.field.detach().numpy().reshape(-1)
        if support > int(round(base_flat[11])):
            raise CovariantFieldError("guard support exceeds learned-world count")
        if int(round(base_flat[14])) != support:
            raise CovariantFieldError("guard support and hierarchical support differ")
        tail = flat[self._metadata_end : self._metadata_offset + self._extra_words]
        if not np.array_equal(tail, np.zeros_like(tail)):
            raise CovariantFieldError("guard reserved tail is not zero")

    def _attach(
        self,
        base_state: RegimeCovariantState,
        *,
        support: int,
        tokens: Sequence[int],
    ) -> RegimeCovariantState:
        self.base.validate_state(base_state)
        if not 0 <= support <= _MAX_EXACT_INTEGER:
            raise CovariantFieldError("support is outside the exact field range")
        if len(tokens) > self.regime_slots:
            raise CovariantFieldError("guard regime registry is full")
        if len(set(tokens)) != len(tokens) or any(
            token <= 0 or token > _MAX_EXACT_INTEGER for token in tokens
        ):
            raise CovariantFieldError("guard regime tokens are invalid")
        field = torch.zeros(self.shape, dtype=torch.float64, device="cpu")
        output = field.reshape(-1)
        output[: self._base_words] = base_state.field.reshape(-1)
        guard = output[self._guard_slice]
        guard[0] = _GUARD_MAGIC
        guard[1] = _GUARD_VERSION
        guard[2] = float(support)
        guard[3] = float(len(tokens))
        if tokens:
            guard[4 : 4 + len(tokens)] = torch.tensor(
                tokens, dtype=torch.float64
            )
        state = RegimeCovariantState(field=field)
        self.validate_state(state)
        return state

    @staticmethod
    def _raw_field_bytes(state: RegimeCovariantState) -> bytes:
        return (
            state.field.detach()
            .to(device="cpu", dtype=torch.float64)
            .contiguous()
            .numpy()
            .astype("<f8", copy=False)
            .tobytes(order="C")
        )

    def state_sha256(self, state: RegimeCovariantState) -> str:
        self.validate_state(state)
        return hashlib.sha256(self._raw_field_bytes(state)).hexdigest()

    def export_state(self, state: RegimeCovariantState) -> bytes:
        self.validate_state(state)
        return self._raw_field_bytes(state)

    def import_state(self, raw: bytes) -> RegimeCovariantState:
        if not isinstance(raw, bytes):
            raise CovariantFieldError("field checkpoint must be bytes")
        expected = math.prod(self.shape) * 8
        if len(raw) != expected:
            raise CovariantFieldError(
                f"guarded checkpoint has {len(raw)} bytes; expected {expected}"
            )
        values = np.frombuffer(raw, dtype="<f8").astype(np.float64, copy=True)
        state = RegimeCovariantState(field=torch.from_numpy(values).reshape(self.shape))
        self.validate_state(state)
        return state

    def initial_state(self) -> RegimeCovariantState:
        return self._attach(self.base.initial_state(), support=0, tokens=())

    def fit_snapshot_baseline(
        self,
        state: RegimeCovariantState,
        frames: Iterable[CovariantFrame],
    ) -> RegimeCovariantState:
        _, _, _, tokens = self._metadata(self._check_outer_tensor(state))
        fitted = self.base.fit_snapshot_baseline(self._base_state(state), frames)
        support = int(round(fitted.field.reshape(-1)[14].item()))
        return self._attach(fitted, support=support, tokens=tokens)

    def reset_tracks(self, state: RegimeCovariantState) -> RegimeCovariantState:
        flat = self._check_outer_tensor(state)
        support, _, _, tokens = self._metadata(flat)
        reset = self.base.reset_tracks(self._base_state(state))
        return self._attach(reset, support=support, tokens=tokens)

    def begin_isotropic_rollout(
        self, state: RegimeCovariantState
    ) -> RegimeCovariantState:
        """Start generation two without inherited release support or identities."""

        base_state = self._base_state(state)
        successor = base_state.field.clone()
        flat = successor.reshape(-1)
        flat[14] = 0.0
        flat[15] = 0.0
        started = RegimeCovariantState(field=successor)
        return self._attach(started, support=0, tokens=())

    @staticmethod
    def _regime_token(regime_id: str) -> int:
        if not isinstance(regime_id, str) or not regime_id.strip():
            raise CovariantFieldError("regime_id must be a nonempty string")
        token = int.from_bytes(
            hashlib.sha256(regime_id.strip().encode("utf-8")).digest()[:6],
            "big",
        )
        return max(1, token)

    def learn_world(
        self,
        state: RegimeCovariantState,
        frames: Iterable[CovariantFrame],
        *,
        regime_id: str,
    ) -> RegimeCovariantState:
        """Fit one chunk while admitting anisotropic support once per identity."""

        flat = self._check_outer_tensor(state)
        _, support, _, tokens = self._metadata(flat)
        token = self._regime_token(regime_id)
        if token not in tokens and len(tokens) >= self.regime_slots:
            raise CovariantFieldError("guard regime registry is full")
        base_state = self._base_state(state)
        before_support = int(round(base_state.field.reshape(-1)[14].item()))
        learned = self.base.learn_world(base_state, frames)
        learned_flat = learned.field.reshape(-1)
        local_increment = max(0, int(round(learned_flat[14].item())) - before_support)
        if token in tokens:
            next_support = support
            next_tokens = tokens
        else:
            next_support = support + local_increment
            next_tokens = (*tokens, token)
        learned_flat[14] = float(next_support)
        return self._attach(learned, support=next_support, tokens=next_tokens)

    def forecast_world(
        self,
        state: RegimeCovariantState,
        frames: Iterable[CovariantFrame],
        *,
        break_identity: bool = False,
    ) -> CovariantForecast:
        flat = self._check_outer_tensor(state)
        _, support, _, tokens = self._metadata(flat)
        result = self.base.forecast_world(
            self._base_state(state), frames, break_identity=break_identity
        )
        result_state = self._attach(result.state, support=support, tokens=tokens)
        return CovariantForecast(
            ticks=result.ticks,
            identity_ids=result.identity_ids,
            snapshot_baseline=result.snapshot_baseline,
            causal=result.causal,
            combined=result.combined,
            state=result_state,
            identity_mismatch_fraction=result.identity_mismatch_fraction,
        )

    def forecast_isotropic(
        self,
        state: RegimeCovariantState,
        frames: Iterable[CovariantFrame],
        *,
        break_identity: bool = False,
    ) -> CovariantForecast:
        flat = self._check_outer_tensor(state)
        _, support, _, tokens = self._metadata(flat)
        result = self.base.forecast_isotropic(
            self._base_state(state), frames, break_identity=break_identity
        )
        result_flat = result.state.field.reshape(-1)
        result_flat[14] = float(support)
        result_state = self._attach(result.state, support=support, tokens=tokens)
        return CovariantForecast(
            ticks=result.ticks,
            identity_ids=result.identity_ids,
            snapshot_baseline=result.snapshot_baseline,
            causal=result.causal,
            combined=result.combined,
            state=result_state,
            identity_mismatch_fraction=result.identity_mismatch_fraction,
        )

    def inspect(self, state: RegimeCovariantState) -> dict[str, object]:
        flat = self._check_outer_tensor(state)
        support, _, token_count, tokens = self._metadata(flat)
        result = self.base.inspect(self._base_state(state))
        result.update(
            {
                "schema": SCHEMA,
                "guard_schema": SCHEMA,
                "guard_regime_slots": self.regime_slots,
                "guard_regime_token_count": token_count,
                "guard_regime_tokens": list(tokens),
                "guard_unique_regime_support": int(support),
                "guard_contract": (
                    "anisotropic support increments only on unseen field-owned "
                    "regime identities"
                ),
                "adaptive_owner": "RegimeCovariantState.field",
            }
        )
        return result


__all__ = [
    "SCHEMA",
    "Generation2GuardedFieldConfig",
    "Generation2IsotropicRegimeGuardedField",
    "RegimeCovariantState",
    "CovariantFrame",
    "CovariantForecast",
    "CovariantFieldError",
]
