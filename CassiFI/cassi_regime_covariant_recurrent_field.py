"""Regime-covariant identity memory whose sole adaptive value is a field.

The learned operator is expressed in local kinematic coordinates rather than in
one world's absolute force calibration.  A current velocity and the same
identity's lagged velocities produce causal acceleration estimates.  Their
change is decomposed in the radial/transverse frame defined by current and
lagged position, normalized by the causal acceleration magnitude during
learning, and mapped back with scalar field-owned coefficients.  Consequently
positive length/velocity unit changes and rigid rotations commute with the
trajectory forecast.

The field also retains a complete-present linear comparator.  Comparator
coefficients, covariant residual statistics, identity tracks, positions,
velocities, counters, and checkpoint metadata all inhabit one CPU float64
``field`` tensor.  Configuration and code are fixed; no adaptive sidecar exists.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import torch
from torch import Tensor


SCHEMA = "cassifi.regime-covariant-recurrent-field.v2"
_MAGIC = 314159265.0
_HEADER_WORDS = 20
_MAX_EXACT_INTEGER = 2**53 - 1
_CORRECTION_WIDTH = 2
_VECTOR_WIDTH = 3


class CovariantFieldError(ValueError):
    """Raised when a covariant field request or checkpoint is invalid."""


def _positive_int(value: object, name: str, *, maximum: int = 1_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise CovariantFieldError(f"{name} must be an integer")
    result = int(value)
    if not 1 <= result <= maximum:
        raise CovariantFieldError(f"{name} is outside 1..{maximum}")
    return result


def _positive_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(
        value, (int, float, np.integer, np.floating)
    ):
        raise CovariantFieldError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise CovariantFieldError(f"{name} must be finite and positive")
    return result


def _matrix(value: object, name: str, *, columns: int) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise CovariantFieldError(f"{name} must be numeric") from exc
    if result.ndim != 2 or result.shape[1] != columns:
        raise CovariantFieldError(
            f"{name} must have shape [N, {columns}], got {result.shape}"
        )
    if not np.isfinite(result).all():
        raise CovariantFieldError(f"{name} contains nonfinite values")
    return result


@dataclass(frozen=True, slots=True)
class CovariantFieldConfig:
    """Static layout and numerical law for one covariant recurrent field."""

    present_width: int
    max_identities: int = 256
    lags: tuple[int, ...] = (1, 2, 4, 8)
    snapshot_ridge: float = 1e-10
    correction_ridge: float = 0.1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "present_width",
            _positive_int(self.present_width, "present_width", maximum=4096),
        )
        object.__setattr__(
            self,
            "max_identities",
            _positive_int(self.max_identities, "max_identities", maximum=65_536),
        )
        if isinstance(self.lags, (str, bytes)) or not isinstance(self.lags, Sequence):
            raise CovariantFieldError("lags must be a sequence")
        lags = tuple(_positive_int(value, "lag", maximum=4096) for value in self.lags)
        if tuple(sorted(set(lags))) != lags or len(lags) < 2:
            raise CovariantFieldError("lags must be unique, increasing, and contain 1 and 2")
        if lags[0] != 1 or lags[1] != 2:
            raise CovariantFieldError("the covariant derivative requires leading lags 1 and 2")
        object.__setattr__(self, "lags", lags)
        object.__setattr__(
            self,
            "snapshot_ridge",
            _positive_float(self.snapshot_ridge, "snapshot_ridge"),
        )
        object.__setattr__(
            self,
            "correction_ridge",
            _positive_float(self.correction_ridge, "correction_ridge"),
        )
        if self.total_words > 20_000_000:
            raise CovariantFieldError("covariant field layout exceeds its bounded capacity")

    @property
    def max_lag(self) -> int:
        return self.lags[-1]

    @property
    def total_words(self) -> int:
        return (
            _HEADER_WORDS
            + len(self.lags)
            + self.present_width
            + (self.present_width + 1) * _VECTOR_WIDTH
            + _CORRECTION_WIDTH * _CORRECTION_WIDTH
            + _CORRECTION_WIDTH
            + 3 * self.max_identities
            + 2 * self.max_identities * self.max_lag * _VECTOR_WIDTH
        )

    @property
    def mode_count(self) -> int:
        return (self.total_words + 8) // 9

    @property
    def shape(self) -> tuple[int, int, int]:
        return (1, 9 * self.mode_count, 1)


@dataclass(frozen=True, slots=True)
class RegimeCovariantState:
    """The sole adaptive value for snapshot comparison and recurrent memory."""

    field: Tensor


@dataclass(frozen=True, slots=True)
class CovariantFrame:
    """One simultaneous observation in dimensionless physical coordinates."""

    tick: int
    identity_ids: np.ndarray
    present: np.ndarray
    position: np.ndarray
    velocity: np.ndarray
    delta_time: float
    target: np.ndarray | None = None


@dataclass(frozen=True, slots=True)
class CovariantForecast:
    """Resolved snapshot, causal, and field-corrected trajectory forecasts."""

    ticks: np.ndarray
    identity_ids: np.ndarray
    snapshot_baseline: np.ndarray
    causal: np.ndarray
    combined: np.ndarray
    state: RegimeCovariantState
    identity_mismatch_fraction: float

    @property
    def resolved_count(self) -> int:
        return int(len(self.identity_ids))


@dataclass(frozen=True, slots=True)
class _Layout:
    lags: slice
    present_scale: slice
    snapshot_coefficients: slice
    correction_gram: slice
    correction_cross: slice
    identities: slice
    last_ticks: slice
    depths: slice
    position_ring: slice
    velocity_ring: slice


class RegimeCovariantRecurrentField:
    """Pure field transitions for a scale- and rotation-covariant memory."""

    def __init__(self, config: CovariantFieldConfig) -> None:
        self.config = config
        cursor = _HEADER_WORDS

        def take(words: int) -> slice:
            nonlocal cursor
            result = slice(cursor, cursor + words)
            cursor += words
            return result

        ring_words = config.max_identities * config.max_lag * _VECTOR_WIDTH
        self._layout = _Layout(
            lags=take(len(config.lags)),
            present_scale=take(config.present_width),
            snapshot_coefficients=take((config.present_width + 1) * _VECTOR_WIDTH),
            correction_gram=take(_CORRECTION_WIDTH * _CORRECTION_WIDTH),
            correction_cross=take(_CORRECTION_WIDTH),
            identities=take(config.max_identities),
            last_ticks=take(config.max_identities),
            depths=take(config.max_identities),
            position_ring=take(ring_words),
            velocity_ring=take(ring_words),
        )
        if cursor != config.total_words:
            raise RuntimeError("covariant field layout accounting drifted")

    def initial_state(self) -> RegimeCovariantState:
        field = torch.zeros(self.config.shape, dtype=torch.float64, device="cpu")
        flat = field.reshape(-1)
        flat[0] = _MAGIC
        flat[1] = 2.0
        flat[2] = float(self.config.present_width)
        flat[3] = float(self.config.max_identities)
        flat[4] = float(self.config.max_lag)
        flat[5] = float(len(self.config.lags))
        flat[6] = self.config.snapshot_ridge
        flat[7] = self.config.correction_ridge
        flat[self._layout.lags] = torch.tensor(
            self.config.lags, dtype=torch.float64
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
        expected = math.prod(self.config.shape) * 8
        if len(raw) != expected:
            raise CovariantFieldError(
                f"field checkpoint has {len(raw)} bytes; expected {expected}"
            )
        values = np.frombuffer(raw, dtype="<f8").astype(np.float64, copy=True)
        state = RegimeCovariantState(
            field=torch.from_numpy(values).reshape(self.config.shape)
        )
        self.validate_state(state)
        return state

    def _flat(self, state: RegimeCovariantState) -> np.ndarray:
        self.validate_state(state)
        return state.field.detach().numpy().reshape(-1)

    def _mutable(
        self, state: RegimeCovariantState
    ) -> tuple[RegimeCovariantState, np.ndarray]:
        self.validate_state(state)
        successor = RegimeCovariantState(field=state.field.clone())
        return successor, successor.field.numpy().reshape(-1)

    @staticmethod
    def _view(flat: np.ndarray, span: slice, shape: tuple[int, ...]) -> np.ndarray:
        return flat[span].reshape(shape)

    def validate_state(self, state: RegimeCovariantState) -> None:
        if not isinstance(state, RegimeCovariantState):
            raise CovariantFieldError("covariant state has the wrong type")
        field = state.field
        if (
            not isinstance(field, Tensor)
            or field.device.type != "cpu"
            or field.dtype != torch.float64
            or tuple(field.shape) != self.config.shape
            or field.requires_grad
        ):
            raise CovariantFieldError(
                "field must be a non-gradient CPU float64 tensor with the configured shape"
            )
        flat = field.detach().numpy().reshape(-1)
        if not np.isfinite(flat).all():
            raise CovariantFieldError("field contains nonfinite values")
        expected_header = (
            _MAGIC,
            2.0,
            float(self.config.present_width),
            float(self.config.max_identities),
            float(self.config.max_lag),
            float(len(self.config.lags)),
            self.config.snapshot_ridge,
            self.config.correction_ridge,
        )
        if not np.array_equal(flat[:8], np.asarray(expected_header, dtype=np.float64)):
            raise CovariantFieldError("field header differs from its fixed configuration")
        if not np.array_equal(
            flat[self._layout.lags], np.asarray(self.config.lags, dtype=np.float64)
        ):
            raise CovariantFieldError("field lag coordinates differ from configuration")
        for index, name in ((8, "snapshot-ready"),):
            if flat[index] not in (0.0, 1.0):
                raise CovariantFieldError(f"field {name} marker is invalid")
        for index, name in (
            (9, "snapshot samples"),
            (10, "memory samples"),
            (11, "learned worlds"),
            (12, "rollouts"),
            (13, "zero-scale rows"),
        ):
            if flat[index] < 0.0 or flat[index] > _MAX_EXACT_INTEGER:
                raise CovariantFieldError(f"field {name} counter is invalid")
        identities = flat[self._layout.identities]
        last_ticks = flat[self._layout.last_ticks]
        depths = flat[self._layout.depths]
        if np.any(identities < 0.0) or np.any(identities > _MAX_EXACT_INTEGER):
            raise CovariantFieldError("field identity coordinates are invalid")
        if np.any(last_ticks < 0.0) or np.any(last_ticks > _MAX_EXACT_INTEGER):
            raise CovariantFieldError("field tick coordinates are invalid")
        if np.any(depths < 0.0) or np.any(depths > self.config.max_lag):
            raise CovariantFieldError("field history depths are invalid")

    def _canonical_frame(
        self, frame: CovariantFrame, *, require_target: bool
    ) -> CovariantFrame:
        if not isinstance(frame, CovariantFrame):
            raise CovariantFieldError("frame has the wrong type")
        tick = _positive_int(frame.tick, "tick", maximum=_MAX_EXACT_INTEGER)
        try:
            identities = np.asarray(frame.identity_ids, dtype=np.int64)
        except (TypeError, ValueError) as exc:
            raise CovariantFieldError("identity_ids must be integers") from exc
        if identities.ndim != 1 or not len(identities):
            raise CovariantFieldError("identity_ids must be a nonempty vector")
        if np.any(identities < 0) or np.any(identities >= _MAX_EXACT_INTEGER):
            raise CovariantFieldError("identity_ids are outside the exact field range")
        if len(set(identities.tolist())) != len(identities):
            raise CovariantFieldError("identity_ids must be unique within a frame")
        present = _matrix(
            frame.present, "present", columns=self.config.present_width
        )
        position = _matrix(frame.position, "position", columns=_VECTOR_WIDTH)
        velocity = _matrix(frame.velocity, "velocity", columns=_VECTOR_WIDTH)
        if not (len(present) == len(position) == len(velocity) == len(identities)):
            raise CovariantFieldError("frame arrays must have the same row count")
        if np.any(np.linalg.norm(position, axis=1) <= 1e-15):
            raise CovariantFieldError("position rows must define a local radial axis")
        delta_time = _positive_float(frame.delta_time, "delta_time")
        target = None
        if frame.target is not None:
            target = _matrix(frame.target, "target", columns=_VECTOR_WIDTH)
            if len(target) != len(identities):
                raise CovariantFieldError("target row count differs from identities")
        if require_target and target is None:
            raise CovariantFieldError("learning frame lacks a target")
        order = np.argsort(identities, kind="stable")
        return CovariantFrame(
            tick=tick,
            identity_ids=np.asarray(identities[order], dtype=np.int64),
            present=np.asarray(present[order], dtype=np.float64),
            position=np.asarray(position[order], dtype=np.float64),
            velocity=np.asarray(velocity[order], dtype=np.float64),
            delta_time=delta_time,
            target=None if target is None else np.asarray(target[order], dtype=np.float64),
        )

    @staticmethod
    def _ridge_solve(
        gram: np.ndarray, cross: np.ndarray, *, relative_ridge: float
    ) -> np.ndarray:
        scale = relative_ridge * max(
            1.0, float(np.trace(gram)) / max(1, gram.shape[0])
        )
        return np.linalg.solve(
            0.5 * (gram + gram.T)
            + scale * np.eye(gram.shape[0], dtype=np.float64),
            cross,
        )

    def fit_snapshot_baseline(
        self,
        state: RegimeCovariantState,
        frames: Iterable[CovariantFrame],
    ) -> RegimeCovariantState:
        """Fit the current-snapshot comparator inside the same field."""

        flat = self._flat(state)
        if flat[8] != 0.0:
            raise CovariantFieldError("snapshot baseline is already fitted")
        width = self.config.present_width
        count = 0
        present_sum = np.zeros(width, dtype=np.float64)
        present_gram = np.zeros((width, width), dtype=np.float64)
        present_cross = np.zeros((width, _VECTOR_WIDTH), dtype=np.float64)
        target_sum = np.zeros(_VECTOR_WIDTH, dtype=np.float64)
        for raw in frames:
            frame = self._canonical_frame(raw, require_target=True)
            assert frame.target is not None
            count += len(frame.identity_ids)
            present_sum += np.sum(frame.present, axis=0)
            present_gram += frame.present.T @ frame.present
            present_cross += frame.present.T @ frame.target
            target_sum += np.sum(frame.target, axis=0)
        if count <= width + 1:
            raise CovariantFieldError("snapshot fit has insufficient rows")
        present_scale = np.sqrt(np.maximum(np.diag(present_gram) / count, 0.0))
        present_scale[~np.isfinite(present_scale) | (present_scale <= 1e-12)] = 1.0
        augmented_gram = np.empty((width + 1, width + 1), dtype=np.float64)
        augmented_gram[0, 0] = count
        augmented_gram[0, 1:] = present_sum / present_scale
        augmented_gram[1:, 0] = augmented_gram[0, 1:]
        augmented_gram[1:, 1:] = present_gram / np.outer(
            present_scale, present_scale
        )
        augmented_cross = np.vstack(
            (target_sum[None, :], present_cross / present_scale[:, None])
        )
        coefficients = self._ridge_solve(
            augmented_gram,
            augmented_cross,
            relative_ridge=self.config.snapshot_ridge,
        )
        successor, output = self._mutable(state)
        output[self._layout.present_scale] = present_scale
        output[self._layout.snapshot_coefficients] = coefficients.reshape(-1)
        output[8] = 1.0
        output[9] = float(count)
        self.validate_state(successor)
        return successor

    def _snapshot_baseline(self, flat: np.ndarray, present: np.ndarray) -> np.ndarray:
        if flat[8] != 1.0:
            raise CovariantFieldError("snapshot baseline must be fitted first")
        design = np.column_stack(
            (np.ones(len(present)), present / flat[self._layout.present_scale])
        )
        coefficients = self._view(
            flat,
            self._layout.snapshot_coefficients,
            (self.config.present_width + 1, _VECTOR_WIDTH),
        )
        return design @ coefficients

    def _clear_tracks(self, flat: np.ndarray) -> None:
        flat[self._layout.identities] = 0.0
        flat[self._layout.last_ticks] = 0.0
        flat[self._layout.depths] = 0.0
        flat[self._layout.position_ring] = 0.0
        flat[self._layout.velocity_ring] = 0.0

    def reset_tracks(self, state: RegimeCovariantState) -> RegimeCovariantState:
        successor, flat = self._mutable(state)
        self._clear_tracks(flat)
        self.validate_state(successor)
        return successor

    def _track_views(
        self, flat: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        ring_shape = (self.config.max_identities, self.config.max_lag, _VECTOR_WIDTH)
        return (
            flat[self._layout.identities],
            flat[self._layout.last_ticks],
            flat[self._layout.depths],
            self._view(flat, self._layout.position_ring, ring_shape),
            self._view(flat, self._layout.velocity_ring, ring_shape),
        )

    def _lane_lookup(self, flat: np.ndarray) -> dict[int, int]:
        return {
            int(encoded - 1.0): lane
            for lane, encoded in enumerate(flat[self._layout.identities])
            if encoded > 0.0
        }

    def _past_coordinates(
        self,
        flat: np.ndarray,
        *,
        tick: int,
        query_ids: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        _, last_ticks, depths, position_ring, velocity_ring = self._track_views(flat)
        lookup = self._lane_lookup(flat)
        count = len(query_ids)
        resolved = np.zeros(count, dtype=bool)
        positions = np.zeros((count, len(self.config.lags), _VECTOR_WIDTH))
        velocities = np.zeros_like(positions)
        for row, identity in enumerate(query_ids.tolist()):
            lane = lookup.get(int(identity))
            if (
                lane is None
                or int(last_ticks[lane]) != tick - 1
                or int(depths[lane]) < self.config.max_lag
            ):
                continue
            for lag_index, lag in enumerate(self.config.lags):
                positions[row, lag_index] = position_ring[lane, lag - 1]
                velocities[row, lag_index] = velocity_ring[lane, lag - 1]
            resolved[row] = True
        return positions, velocities, resolved

    def _admit_current(self, flat: np.ndarray, frame: CovariantFrame) -> None:
        identities, last_ticks, depths, position_ring, velocity_ring = self._track_views(flat)
        lookup = self._lane_lookup(flat)
        empty = [index for index, value in enumerate(identities) if value == 0.0]
        for row, identity_value in enumerate(frame.identity_ids.tolist()):
            identity = int(identity_value)
            lane = lookup.get(identity)
            if lane is None:
                if not empty:
                    raise CovariantFieldError(
                        "trajectory introduces more identities than the field can retain"
                    )
                lane = empty.pop(0)
                lookup[identity] = lane
                identities[lane] = float(identity + 1)
            contiguous = int(last_ticks[lane]) == frame.tick - 1
            if not contiguous:
                position_ring[lane] = 0.0
                velocity_ring[lane] = 0.0
                depths[lane] = 0.0
            if self.config.max_lag > 1:
                position_ring[lane, 1:] = position_ring[lane, :-1].copy()
                velocity_ring[lane, 1:] = velocity_ring[lane, :-1].copy()
            position_ring[lane, 0] = frame.position[row]
            velocity_ring[lane, 0] = frame.velocity[row]
            last_ticks[lane] = float(frame.tick)
            depths[lane] = float(min(int(depths[lane]) + 1, self.config.max_lag))

    @staticmethod
    def _covariant_coordinates(
        frame: CovariantFrame,
        past_position: np.ndarray,
        past_velocity: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        d1 = (frame.velocity - past_velocity[:, 0]) / frame.delta_time
        d2 = (frame.velocity - past_velocity[:, 1]) / (2.0 * frame.delta_time)
        jerk = d1 - d2
        midpoint = frame.position + past_position[:, 0]
        norm = np.linalg.norm(midpoint, axis=1)
        fallback = norm <= 1e-15
        if np.any(fallback):
            midpoint = midpoint.copy()
            midpoint[fallback] = frame.position[fallback]
            norm = np.linalg.norm(midpoint, axis=1)
        radial = midpoint / norm[:, None]
        radial_jerk = radial * np.einsum("ni,ni->n", jerk, radial)[:, None]
        transverse_jerk = jerk - radial_jerk
        correction = np.stack((radial_jerk, transverse_jerk), axis=1)
        scale = np.sqrt(np.mean(d1 * d1, axis=1))
        return d1, correction, scale

    def learn_world(
        self,
        state: RegimeCovariantState,
        frames: Iterable[CovariantFrame],
    ) -> RegimeCovariantState:
        """Accumulate normalized radial/transverse correction evidence."""

        successor, flat = self._mutable(state)
        if flat[8] != 1.0:
            raise CovariantFieldError("snapshot baseline must be fitted before learning")
        self._clear_tracks(flat)
        gram = self._view(
            flat,
            self._layout.correction_gram,
            (_CORRECTION_WIDTH, _CORRECTION_WIDTH),
        )
        cross = flat[self._layout.correction_cross]
        learned = 0
        skipped = 0
        previous_tick = 0
        frame_count = 0
        for raw in frames:
            frame = self._canonical_frame(raw, require_target=True)
            if frame.tick <= previous_tick:
                raise CovariantFieldError("world ticks must be strictly increasing")
            previous_tick = frame.tick
            frame_count += 1
            assert frame.target is not None
            past_position, past_velocity, resolved = self._past_coordinates(
                flat, tick=frame.tick, query_ids=frame.identity_ids
            )
            if np.any(resolved):
                causal, correction, scale = self._covariant_coordinates(
                    frame,
                    past_position,
                    past_velocity,
                )
                selected = resolved & (scale > 0.0)
                if np.any(selected):
                    normalized_correction = correction[selected] / scale[
                        selected, None, None
                    ]
                    normalized_residual = (
                        frame.target[selected] - causal[selected]
                    ) / scale[selected, None]
                    gram += np.einsum(
                        "nci,ndi->cd",
                        normalized_correction,
                        normalized_correction,
                    )
                    cross += np.einsum(
                        "nci,ni->c",
                        normalized_correction,
                        normalized_residual,
                    )
                    learned += int(np.count_nonzero(selected))
                skipped += int(np.count_nonzero(resolved & ~selected))
            self._admit_current(flat, frame)
        if frame_count == 0 or learned == 0:
            raise CovariantFieldError("world does not contain usable covariant history")
        gram[:] = 0.5 * (gram + gram.T)
        flat[10] += float(learned)
        flat[11] += 1.0
        flat[13] += float(skipped)
        self.validate_state(successor)
        return successor

    def _correction_coefficients(self, flat: np.ndarray) -> np.ndarray:
        gram = self._view(
            flat,
            self._layout.correction_gram,
            (_CORRECTION_WIDTH, _CORRECTION_WIDTH),
        )
        cross = flat[self._layout.correction_cross]
        if flat[10] == 0.0:
            return np.zeros(_CORRECTION_WIDTH, dtype=np.float64)
        return self._ridge_solve(
            gram,
            cross,
            relative_ridge=self.config.correction_ridge,
        )

    def forecast_world(
        self,
        state: RegimeCovariantState,
        frames: Iterable[CovariantFrame],
        *,
        break_identity: bool = False,
    ) -> CovariantForecast:
        """Forecast before writing the current observation into identity memory."""

        successor, flat = self._mutable(state)
        if flat[8] != 1.0:
            raise CovariantFieldError("snapshot baseline must be fitted before forecasting")
        self._clear_tracks(flat)
        coefficients = self._correction_coefficients(flat)
        output_ticks: list[np.ndarray] = []
        output_ids: list[np.ndarray] = []
        output_snapshot: list[np.ndarray] = []
        output_causal: list[np.ndarray] = []
        output_combined: list[np.ndarray] = []
        mismatch = 0
        queried = 0
        previous_tick = 0
        frame_count = 0
        for raw in frames:
            frame = self._canonical_frame(raw, require_target=False)
            if frame.tick <= previous_tick:
                raise CovariantFieldError("world ticks must be strictly increasing")
            previous_tick = frame.tick
            frame_count += 1
            query_ids = (
                np.roll(frame.identity_ids, 1)
                if break_identity and len(frame.identity_ids) > 1
                else frame.identity_ids
            )
            past_position, past_velocity, resolved = self._past_coordinates(
                flat,
                tick=frame.tick,
                query_ids=query_ids,
            )
            snapshot = self._snapshot_baseline(flat, frame.present)
            if np.any(resolved):
                causal, correction, scale = self._covariant_coordinates(
                    frame,
                    past_position,
                    past_velocity,
                )
                memory = np.einsum("c,nci->ni", coefficients, correction)
                memory[scale == 0.0] = 0.0
                selected_count = int(np.count_nonzero(resolved))
                output_ticks.append(
                    np.full(selected_count, frame.tick, dtype=np.int64)
                )
                output_ids.append(frame.identity_ids[resolved].copy())
                output_snapshot.append(snapshot[resolved].copy())
                output_causal.append(causal[resolved].copy())
                output_combined.append((causal[resolved] + memory[resolved]).copy())
                mismatch += int(
                    np.count_nonzero(query_ids[resolved] != frame.identity_ids[resolved])
                )
                queried += selected_count
            self._admit_current(flat, frame)
        if frame_count == 0 or not output_ids:
            raise CovariantFieldError("world does not contain forecastable covariant history")
        flat[12] += 1.0
        self.validate_state(successor)
        return CovariantForecast(
            ticks=np.concatenate(output_ticks),
            identity_ids=np.concatenate(output_ids),
            snapshot_baseline=np.concatenate(output_snapshot),
            causal=np.concatenate(output_causal),
            combined=np.concatenate(output_combined),
            state=successor,
            identity_mismatch_fraction=float(mismatch / queried) if queried else 0.0,
        )

    def inspect(self, state: RegimeCovariantState) -> dict[str, object]:
        flat = self._flat(state)
        gram = self._view(
            flat,
            self._layout.correction_gram,
            (_CORRECTION_WIDTH, _CORRECTION_WIDTH),
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
            "lags": list(self.config.lags),
            "max_identities": self.config.max_identities,
            "snapshot_ridge": self.config.snapshot_ridge,
            "correction_ridge": self.config.correction_ridge,
            "snapshot_ready": bool(flat[8]),
            "snapshot_samples": int(flat[9]),
            "memory_samples": int(flat[10]),
            "learned_worlds": int(flat[11]),
            "rollouts": int(flat[12]),
            "zero_scale_rows": int(flat[13]),
            "resident_identities": int(
                np.count_nonzero(flat[self._layout.identities])
            ),
            "correction_rank": int(np.count_nonzero(eigenvalues > tolerance)),
            "correction_coefficients": self._correction_coefficients(flat).tolist(),
            "coordinate_contract": (
                "causal d1 plus field-learned radial/transverse jerk correction"
            ),
            "adaptive_owner": "RegimeCovariantState.field",
        }


__all__ = [
    "SCHEMA",
    "CovariantFieldConfig",
    "CovariantFieldError",
    "CovariantForecast",
    "CovariantFrame",
    "RegimeCovariantRecurrentField",
    "RegimeCovariantState",
]
