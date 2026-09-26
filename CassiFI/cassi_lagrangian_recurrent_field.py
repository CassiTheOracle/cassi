"""Identity-bound recurrent trajectory memory whose sole adaptive value is a field.

The controller keeps baseline coefficients, trajectory scales, delayed per-identity
coordinates, and residual sufficient statistics inside one float64 ``field`` tensor.
Configuration and code are fixed; there is no learned Python object, cache, or model
sidecar.  A forecast reads an identity's lagged coordinates before admitting the
current observation, which makes the temporal direction explicit and testable.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import torch
from torch import Tensor


SCHEMA = "cassifi.lagrangian-recurrent-field.v1"
_MAGIC = 271828182.0
_HEADER_WORDS = 16
_MAX_EXACT_INTEGER = 2**53 - 1


class LagrangianFieldError(ValueError):
    """Raised when a recurrent field request or state is invalid."""


def _positive_int(value: object, name: str, *, maximum: int = 1_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise LagrangianFieldError(f"{name} must be an integer")
    result = int(value)
    if not 1 <= result <= maximum:
        raise LagrangianFieldError(f"{name} is outside 1..{maximum}")
    return result


def _matrix(value: object, name: str, *, columns: int) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise LagrangianFieldError(f"{name} must be numeric") from exc
    if result.ndim != 2 or result.shape[1] != columns:
        raise LagrangianFieldError(
            f"{name} must have shape [N, {columns}], got {result.shape}"
        )
    if not np.isfinite(result).all():
        raise LagrangianFieldError(f"{name} contains nonfinite values")
    return result


@dataclass(frozen=True, slots=True)
class LagrangianFieldConfig:
    """Static layout and numerical law for one recurrent field."""

    present_width: int
    history_width: int
    target_width: int
    lags: tuple[int, ...] = (1, 2, 4, 8)
    max_identities: int = 256
    ridge: float = 1e-10

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "present_width",
            _positive_int(self.present_width, "present_width", maximum=4096),
        )
        object.__setattr__(
            self,
            "history_width",
            _positive_int(self.history_width, "history_width", maximum=4096),
        )
        object.__setattr__(
            self,
            "target_width",
            _positive_int(self.target_width, "target_width", maximum=1024),
        )
        object.__setattr__(
            self,
            "max_identities",
            _positive_int(self.max_identities, "max_identities", maximum=65_536),
        )
        if isinstance(self.lags, (str, bytes)) or not isinstance(self.lags, Sequence):
            raise LagrangianFieldError("lags must be a sequence")
        lags = tuple(_positive_int(value, "lag", maximum=4096) for value in self.lags)
        if not lags or tuple(sorted(set(lags))) != lags:
            raise LagrangianFieldError("lags must be nonempty, unique, and increasing")
        object.__setattr__(self, "lags", lags)
        if isinstance(self.ridge, bool) or not isinstance(
            self.ridge, (int, float, np.integer, np.floating)
        ):
            raise LagrangianFieldError("ridge must be numeric")
        ridge = float(self.ridge)
        if not math.isfinite(ridge) or ridge <= 0.0:
            raise LagrangianFieldError("ridge must be finite and positive")
        object.__setattr__(self, "ridge", ridge)
        if self.total_words > 20_000_000:
            raise LagrangianFieldError("recurrent field layout exceeds its bounded capacity")

    @property
    def max_lag(self) -> int:
        return self.lags[-1]

    @property
    def history_design_width(self) -> int:
        return 1 + len(self.lags) * self.history_width

    @property
    def total_words(self) -> int:
        design = self.history_design_width
        return (
            _HEADER_WORDS
            + len(self.lags)
            + self.present_width
            + self.history_width
            + (self.present_width + 1) * self.target_width
            + design * design
            + design * self.target_width
            + 3 * self.max_identities
            + self.max_identities * self.max_lag * self.history_width
        )

    @property
    def mode_count(self) -> int:
        return (self.total_words + 8) // 9

    @property
    def shape(self) -> tuple[int, int, int]:
        return (1, 9 * self.mode_count, 1)


@dataclass(frozen=True, slots=True)
class LagrangianRecurrentState:
    """The sole adaptive recurrent value."""

    field: Tensor


@dataclass(frozen=True, slots=True)
class LagrangianFrame:
    """One simultaneous observation of named moving identities."""

    tick: int
    identity_ids: np.ndarray
    present: np.ndarray
    history: np.ndarray
    target: np.ndarray | None = None


@dataclass(frozen=True, slots=True)
class LagrangianForecast:
    """Resolved chronological predictions and the resulting recurrent state."""

    ticks: np.ndarray
    identity_ids: np.ndarray
    baseline: np.ndarray
    combined: np.ndarray
    state: LagrangianRecurrentState
    identity_mismatch_fraction: float

    @property
    def resolved_count(self) -> int:
        return int(len(self.identity_ids))


@dataclass(frozen=True, slots=True)
class _Layout:
    lags: slice
    present_scale: slice
    history_scale: slice
    baseline_coefficients: slice
    history_gram: slice
    history_cross: slice
    identities: slice
    last_ticks: slice
    depths: slice
    ring: slice


class LagrangianRecurrentField:
    """Pure field transitions for delayed identity-bound residual prediction."""

    def __init__(self, config: LagrangianFieldConfig) -> None:
        self.config = config
        cursor = _HEADER_WORDS

        def take(words: int) -> slice:
            nonlocal cursor
            result = slice(cursor, cursor + words)
            cursor += words
            return result

        design = config.history_design_width
        self._layout = _Layout(
            lags=take(len(config.lags)),
            present_scale=take(config.present_width),
            history_scale=take(config.history_width),
            baseline_coefficients=take(
                (config.present_width + 1) * config.target_width
            ),
            history_gram=take(design * design),
            history_cross=take(design * config.target_width),
            identities=take(config.max_identities),
            last_ticks=take(config.max_identities),
            depths=take(config.max_identities),
            ring=take(config.max_identities * config.max_lag * config.history_width),
        )
        if cursor != config.total_words:
            raise RuntimeError("recurrent field layout accounting drifted")

    def initial_state(self) -> LagrangianRecurrentState:
        field = torch.zeros(self.config.shape, dtype=torch.float64, device="cpu")
        flat = field.reshape(-1)
        flat[0] = _MAGIC
        flat[1] = 1.0
        flat[2] = float(self.config.present_width)
        flat[3] = float(self.config.history_width)
        flat[4] = float(self.config.target_width)
        flat[5] = float(self.config.max_identities)
        flat[6] = float(len(self.config.lags))
        flat[7] = float(self.config.max_lag)
        flat[self._layout.lags] = torch.tensor(self.config.lags, dtype=torch.float64)
        state = LagrangianRecurrentState(field=field)
        self.validate_state(state)
        return state

    @staticmethod
    def _raw_field_bytes(state: LagrangianRecurrentState) -> bytes:
        return (
            state.field.detach()
            .to(device="cpu", dtype=torch.float64)
            .contiguous()
            .numpy()
            .astype("<f8", copy=False)
            .tobytes(order="C")
        )

    def state_sha256(self, state: LagrangianRecurrentState) -> str:
        self.validate_state(state)
        return hashlib.sha256(self._raw_field_bytes(state)).hexdigest()

    def export_state(self, state: LagrangianRecurrentState) -> bytes:
        self.validate_state(state)
        return self._raw_field_bytes(state)

    def import_state(self, raw: bytes) -> LagrangianRecurrentState:
        if not isinstance(raw, bytes):
            raise LagrangianFieldError("field checkpoint must be bytes")
        expected = math.prod(self.config.shape) * 8
        if len(raw) != expected:
            raise LagrangianFieldError(
                f"field checkpoint has {len(raw)} bytes, expected {expected}"
            )
        values = np.frombuffer(raw, dtype="<f8").astype(np.float64, copy=True)
        state = LagrangianRecurrentState(
            field=torch.from_numpy(values).reshape(self.config.shape)
        )
        self.validate_state(state)
        return state

    def _flat(self, state: LagrangianRecurrentState) -> np.ndarray:
        self.validate_state(state)
        return state.field.detach().numpy().reshape(-1)

    def _mutable(self, state: LagrangianRecurrentState) -> tuple[LagrangianRecurrentState, np.ndarray]:
        self.validate_state(state)
        successor = LagrangianRecurrentState(field=state.field.clone())
        return successor, successor.field.numpy().reshape(-1)

    def _view(self, flat: np.ndarray, span: slice, shape: tuple[int, ...]) -> np.ndarray:
        return flat[span].reshape(shape)

    def validate_state(self, state: LagrangianRecurrentState) -> None:
        if not isinstance(state, LagrangianRecurrentState):
            raise LagrangianFieldError("recurrent state has the wrong type")
        field = state.field
        if (
            not isinstance(field, Tensor)
            or field.device.type != "cpu"
            or field.dtype != torch.float64
            or field.requires_grad
            or tuple(field.shape) != self.config.shape
            or not field.is_contiguous()
        ):
            raise LagrangianFieldError(
                "recurrent field must be a contiguous CPU float64 tensor with its declared shape"
            )
        if not bool(torch.isfinite(field).all().item()):
            raise LagrangianFieldError("recurrent field contains nonfinite values")
        flat = field.detach().numpy().reshape(-1)
        expected_header = (
            _MAGIC,
            1.0,
            float(self.config.present_width),
            float(self.config.history_width),
            float(self.config.target_width),
            float(self.config.max_identities),
            float(len(self.config.lags)),
            float(self.config.max_lag),
        )
        if tuple(float(value) for value in flat[:8]) != expected_header:
            raise LagrangianFieldError("recurrent field header differs from its controller")
        if tuple(int(value) for value in flat[self._layout.lags]) != self.config.lags:
            raise LagrangianFieldError("recurrent field lag coordinates are corrupt")
        for index, label in ((8, "baseline flag"), (9, "baseline samples"), (10, "memory samples"), (11, "learned worlds"), (12, "rollouts")):
            value = float(flat[index])
            if value < 0.0 or value > _MAX_EXACT_INTEGER or value != math.floor(value):
                raise LagrangianFieldError(f"recurrent {label} is invalid")
        if flat[8] not in (0.0, 1.0):
            raise LagrangianFieldError("recurrent baseline flag is invalid")
        identities = flat[self._layout.identities]
        last_ticks = flat[self._layout.last_ticks]
        depths = flat[self._layout.depths]
        if np.any(identities < 0.0) or np.any(identities > _MAX_EXACT_INTEGER):
            raise LagrangianFieldError("recurrent identity coordinates are invalid")
        if np.any(identities != np.floor(identities)):
            raise LagrangianFieldError("recurrent identity coordinates must be exact integers")
        occupied = identities > 0.0
        if len(set(identities[occupied].tolist())) != int(np.count_nonzero(occupied)):
            raise LagrangianFieldError("recurrent identities must be unique")
        if np.any(last_ticks < 0.0) or np.any(last_ticks != np.floor(last_ticks)):
            raise LagrangianFieldError("recurrent ticks are invalid")
        if np.any(depths < 0.0) or np.any(depths > self.config.max_lag) or np.any(depths != np.floor(depths)):
            raise LagrangianFieldError("recurrent history depths are invalid")
        if np.any((~occupied) & ((last_ticks != 0.0) | (depths != 0.0))):
            raise LagrangianFieldError("empty recurrent lanes retain identity state")
        if flat[8] == 1.0:
            if flat[9] <= 0.0:
                raise LagrangianFieldError("fitted baseline has no samples")
            if np.any(flat[self._layout.present_scale] <= 0.0) or np.any(
                flat[self._layout.history_scale] <= 0.0
            ):
                raise LagrangianFieldError("fitted recurrent scales must be positive")
        gram = self._view(
            flat,
            self._layout.history_gram,
            (self.config.history_design_width,) * 2,
        )
        if not np.allclose(gram, gram.T, rtol=0.0, atol=1e-10):
            raise LagrangianFieldError("recurrent history Gram matrix is not symmetric")

    def _canonical_frame(self, frame: LagrangianFrame, *, require_target: bool) -> LagrangianFrame:
        if not isinstance(frame, LagrangianFrame):
            raise LagrangianFieldError("trajectory frame has the wrong type")
        tick = _positive_int(frame.tick, "tick", maximum=_MAX_EXACT_INTEGER)
        identities = np.asarray(frame.identity_ids)
        if identities.ndim != 1 or not 1 <= len(identities) <= self.config.max_identities:
            raise LagrangianFieldError("identity_ids must be a bounded nonempty vector")
        if np.issubdtype(identities.dtype, np.bool_) or not np.issubdtype(
            identities.dtype, np.integer
        ):
            raise LagrangianFieldError("identity_ids must contain integers")
        identities = identities.astype(np.int64, copy=False)
        if np.any(identities < 0) or np.any(identities >= _MAX_EXACT_INTEGER):
            raise LagrangianFieldError("identity_ids exceed the exact field range")
        if len(set(identities.tolist())) != len(identities):
            raise LagrangianFieldError("identity_ids must be unique within a frame")
        present = _matrix(frame.present, "present", columns=self.config.present_width)
        history = _matrix(frame.history, "history", columns=self.config.history_width)
        if len(present) != len(identities) or len(history) != len(identities):
            raise LagrangianFieldError("frame arrays must have the same row count")
        target = None
        if frame.target is not None:
            target = _matrix(frame.target, "target", columns=self.config.target_width)
            if len(target) != len(identities):
                raise LagrangianFieldError("target row count differs from identities")
        if require_target and target is None:
            raise LagrangianFieldError("learning frame lacks a target")
        order = np.argsort(identities, kind="stable")
        return LagrangianFrame(
            tick=tick,
            identity_ids=np.asarray(identities[order], dtype=np.int64),
            present=np.asarray(present[order], dtype=np.float64),
            history=np.asarray(history[order], dtype=np.float64),
            target=None if target is None else np.asarray(target[order], dtype=np.float64),
        )

    def _ridge_solve(self, gram: np.ndarray, cross: np.ndarray) -> np.ndarray:
        scale = self.config.ridge * max(
            1.0,
            float(np.trace(gram)) / max(1, gram.shape[0]),
        )
        return np.linalg.solve(
            0.5 * (gram + gram.T) + scale * np.eye(gram.shape[0], dtype=np.float64),
            cross,
        )

    def fit_baseline(
        self,
        state: LagrangianRecurrentState,
        batches: Iterable[LagrangianFrame],
    ) -> LagrangianRecurrentState:
        """Fit the complete-present comparator and both feature scales into the field."""

        flat = self._flat(state)
        if flat[8] != 0.0:
            raise LagrangianFieldError("baseline is already fitted")
        width = self.config.present_width
        target_width = self.config.target_width
        count = 0
        present_sum = np.zeros(width, dtype=np.float64)
        present_gram = np.zeros((width, width), dtype=np.float64)
        present_cross = np.zeros((width, target_width), dtype=np.float64)
        target_sum = np.zeros(target_width, dtype=np.float64)
        history_square = np.zeros(self.config.history_width, dtype=np.float64)
        for raw in batches:
            frame = self._canonical_frame(raw, require_target=True)
            assert frame.target is not None
            count += len(frame.identity_ids)
            present_sum += np.sum(frame.present, axis=0)
            present_gram += frame.present.T @ frame.present
            present_cross += frame.present.T @ frame.target
            target_sum += np.sum(frame.target, axis=0)
            history_square += np.sum(frame.history * frame.history, axis=0)
        if count <= width + 1:
            raise LagrangianFieldError("baseline fit has insufficient rows")
        present_scale = np.sqrt(np.maximum(np.diag(present_gram) / count, 0.0))
        present_scale[~np.isfinite(present_scale) | (present_scale <= 1e-12)] = 1.0
        history_scale = np.sqrt(np.maximum(history_square / count, 0.0))
        history_scale[~np.isfinite(history_scale) | (history_scale <= 1e-12)] = 1.0
        augmented_gram = np.empty((width + 1, width + 1), dtype=np.float64)
        augmented_gram[0, 0] = count
        augmented_gram[0, 1:] = present_sum / present_scale
        augmented_gram[1:, 0] = augmented_gram[0, 1:]
        augmented_gram[1:, 1:] = present_gram / np.outer(present_scale, present_scale)
        augmented_cross = np.vstack(
            (target_sum[None, :], present_cross / present_scale[:, None])
        )
        coefficients = self._ridge_solve(augmented_gram, augmented_cross)
        successor, output = self._mutable(state)
        output[self._layout.present_scale] = present_scale
        output[self._layout.history_scale] = history_scale
        output[self._layout.baseline_coefficients] = coefficients.reshape(-1)
        output[8] = 1.0
        output[9] = float(count)
        self.validate_state(successor)
        return successor

    def _baseline(self, flat: np.ndarray, present: np.ndarray) -> np.ndarray:
        if flat[8] != 1.0:
            raise LagrangianFieldError("baseline must be fitted before trajectory use")
        scale = flat[self._layout.present_scale]
        design = np.column_stack((np.ones(len(present)), present / scale))
        coefficients = self._view(
            flat,
            self._layout.baseline_coefficients,
            (self.config.present_width + 1, self.config.target_width),
        )
        return design @ coefficients

    def _clear_tracks(self, flat: np.ndarray) -> None:
        flat[self._layout.identities] = 0.0
        flat[self._layout.last_ticks] = 0.0
        flat[self._layout.depths] = 0.0
        flat[self._layout.ring] = 0.0

    def reset_tracks(self, state: LagrangianRecurrentState) -> LagrangianRecurrentState:
        successor, flat = self._mutable(state)
        self._clear_tracks(flat)
        self.validate_state(successor)
        return successor

    def _track_views(
        self, flat: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        return (
            flat[self._layout.identities],
            flat[self._layout.last_ticks],
            flat[self._layout.depths],
            self._view(
                flat,
                self._layout.ring,
                (
                    self.config.max_identities,
                    self.config.max_lag,
                    self.config.history_width,
                ),
            ),
        )

    def _lane_lookup(self, flat: np.ndarray) -> dict[int, int]:
        identities = flat[self._layout.identities]
        return {
            int(encoded - 1.0): lane
            for lane, encoded in enumerate(identities)
            if encoded > 0.0
        }

    def _history_design(
        self,
        flat: np.ndarray,
        *,
        tick: int,
        query_ids: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        _, last_ticks, depths, ring = self._track_views(flat)
        lookup = self._lane_lookup(flat)
        resolved = np.zeros(len(query_ids), dtype=bool)
        rows = np.zeros(
            (len(query_ids), self.config.history_design_width), dtype=np.float64
        )
        rows[:, 0] = 1.0
        for index, identity in enumerate(query_ids.tolist()):
            lane = lookup.get(int(identity))
            if (
                lane is None
                or int(last_ticks[lane]) != tick - 1
                or int(depths[lane]) < self.config.max_lag
            ):
                continue
            pieces = [ring[lane, lag - 1] for lag in self.config.lags]
            rows[index, 1:] = np.concatenate(pieces)
            resolved[index] = True
        return rows, resolved

    def _admit_current(self, flat: np.ndarray, frame: LagrangianFrame) -> None:
        identities, last_ticks, depths, ring = self._track_views(flat)
        lookup = self._lane_lookup(flat)
        empty = [index for index, value in enumerate(identities) if value == 0.0]
        scaled = frame.history / flat[self._layout.history_scale]
        for row, identity_value in enumerate(frame.identity_ids.tolist()):
            identity = int(identity_value)
            lane = lookup.get(identity)
            if lane is None:
                if not empty:
                    raise LagrangianFieldError(
                        "trajectory introduces more identities than the field can retain"
                    )
                lane = empty.pop(0)
                lookup[identity] = lane
                identities[lane] = float(identity + 1)
            contiguous = int(last_ticks[lane]) == frame.tick - 1
            if not contiguous:
                ring[lane] = 0.0
                depths[lane] = 0.0
            if self.config.max_lag > 1:
                ring[lane, 1:] = ring[lane, :-1].copy()
            ring[lane, 0] = scaled[row]
            last_ticks[lane] = float(frame.tick)
            depths[lane] = float(min(int(depths[lane]) + 1, self.config.max_lag))

    def learn_world(
        self,
        state: LagrangianRecurrentState,
        frames: Iterable[LagrangianFrame],
    ) -> LagrangianRecurrentState:
        """Learn residual trajectory authority chronologically in one independent world."""

        successor, flat = self._mutable(state)
        if flat[8] != 1.0:
            raise LagrangianFieldError("baseline must be fitted before memory learning")
        self._clear_tracks(flat)
        gram = self._view(
            flat,
            self._layout.history_gram,
            (self.config.history_design_width,) * 2,
        )
        cross = self._view(
            flat,
            self._layout.history_cross,
            (self.config.history_design_width, self.config.target_width),
        )
        learned = 0
        previous_tick = 0
        frame_count = 0
        for raw in frames:
            frame = self._canonical_frame(raw, require_target=True)
            if frame.tick <= previous_tick:
                raise LagrangianFieldError("world ticks must be strictly increasing")
            previous_tick = frame.tick
            frame_count += 1
            assert frame.target is not None
            design, resolved = self._history_design(
                flat, tick=frame.tick, query_ids=frame.identity_ids
            )
            if np.any(resolved):
                baseline = self._baseline(flat, frame.present)
                residual = frame.target - baseline
                selected = design[resolved]
                gram += selected.T @ selected
                cross += selected.T @ residual[resolved]
                learned += int(np.count_nonzero(resolved))
            self._admit_current(flat, frame)
        if frame_count == 0 or learned == 0:
            raise LagrangianFieldError("world does not contain a complete lag history")
        gram[:] = 0.5 * (gram + gram.T)
        flat[10] += float(learned)
        flat[11] += 1.0
        self.validate_state(successor)
        return successor

    def _history_coefficients(self, flat: np.ndarray) -> np.ndarray:
        gram = self._view(
            flat,
            self._layout.history_gram,
            (self.config.history_design_width,) * 2,
        )
        cross = self._view(
            flat,
            self._layout.history_cross,
            (self.config.history_design_width, self.config.target_width),
        )
        if flat[10] == 0.0:
            return np.zeros_like(cross)
        return self._ridge_solve(gram, cross)

    def forecast_world(
        self,
        state: LagrangianRecurrentState,
        frames: Iterable[LagrangianFrame],
        *,
        break_identity: bool = False,
    ) -> LagrangianForecast:
        """Forecast before each current write, optionally querying another tracer's past."""

        successor, flat = self._mutable(state)
        if flat[8] != 1.0:
            raise LagrangianFieldError("baseline must be fitted before forecasting")
        self._clear_tracks(flat)
        coefficients = self._history_coefficients(flat)
        output_ticks: list[np.ndarray] = []
        output_ids: list[np.ndarray] = []
        output_baseline: list[np.ndarray] = []
        output_combined: list[np.ndarray] = []
        mismatch = 0
        queried = 0
        previous_tick = 0
        frame_count = 0
        for raw in frames:
            frame = self._canonical_frame(raw, require_target=False)
            if frame.tick <= previous_tick:
                raise LagrangianFieldError("world ticks must be strictly increasing")
            previous_tick = frame.tick
            frame_count += 1
            query_ids = (
                np.roll(frame.identity_ids, 1)
                if break_identity and len(frame.identity_ids) > 1
                else frame.identity_ids
            )
            design, resolved = self._history_design(
                flat, tick=frame.tick, query_ids=query_ids
            )
            baseline = self._baseline(flat, frame.present)
            if np.any(resolved):
                selected_baseline = baseline[resolved]
                memory = design[resolved] @ coefficients
                output_ticks.append(
                    np.full(int(np.count_nonzero(resolved)), frame.tick, dtype=np.int64)
                )
                output_ids.append(frame.identity_ids[resolved].copy())
                output_baseline.append(selected_baseline.copy())
                output_combined.append((selected_baseline + memory).copy())
                mismatch += int(
                    np.count_nonzero(query_ids[resolved] != frame.identity_ids[resolved])
                )
                queried += int(np.count_nonzero(resolved))
            self._admit_current(flat, frame)
        if frame_count == 0 or not output_ids:
            raise LagrangianFieldError("world does not contain a forecastable lag history")
        flat[12] += 1.0
        self.validate_state(successor)
        return LagrangianForecast(
            ticks=np.concatenate(output_ticks),
            identity_ids=np.concatenate(output_ids),
            baseline=np.concatenate(output_baseline),
            combined=np.concatenate(output_combined),
            state=successor,
            identity_mismatch_fraction=float(mismatch / queried) if queried else 0.0,
        )

    def inspect(self, state: LagrangianRecurrentState) -> dict[str, object]:
        flat = self._flat(state)
        occupied = int(np.count_nonzero(flat[self._layout.identities]))
        gram = self._view(
            flat,
            self._layout.history_gram,
            (self.config.history_design_width,) * 2,
        )
        eigenvalues = np.linalg.eigvalsh(0.5 * (gram + gram.T))
        maximum = float(max(eigenvalues[-1], 0.0)) if len(eigenvalues) else 0.0
        tolerance = 1e-10 * maximum
        return {
            "schema": SCHEMA,
            "state_sha256": self.state_sha256(state),
            "shape": list(self.config.shape),
            "field_words": self.config.total_words,
            "field_bytes": math.prod(self.config.shape) * 8,
            "present_width": self.config.present_width,
            "history_width": self.config.history_width,
            "target_width": self.config.target_width,
            "lags": list(self.config.lags),
            "max_identities": self.config.max_identities,
            "baseline_ready": bool(flat[8]),
            "baseline_samples": int(flat[9]),
            "memory_samples": int(flat[10]),
            "learned_worlds": int(flat[11]),
            "rollouts": int(flat[12]),
            "resident_identities": occupied,
            "conditional_history_rank": int(np.count_nonzero(eigenvalues > tolerance)),
            "adaptive_owner": "LagrangianRecurrentState.field",
        }


__all__ = [
    "SCHEMA",
    "LagrangianFieldConfig",
    "LagrangianFieldError",
    "LagrangianForecast",
    "LagrangianFrame",
    "LagrangianRecurrentField",
    "LagrangianRecurrentState",
]
