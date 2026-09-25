"""A field-owned excitable cellular scheduler for CassiFI solver decisions.

Every working value -- per-site excitation, refractory recovery, plasticity
trace, and the previous-excitation delay line -- lives in one exact-integer
float64 lane block.  ``ExcitableConstraintController`` is fixed deterministic
machinery: a synchronous fixed-point ring automaton whose settled lanes pick
which legal solver decision comes next.  There are no adaptive side tables, no
learned weights, no hidden controller-side arrays, and no model fallback.

The stateless raw-lane operations are shared by the stored-program computer's
machine-resident propagation and the standalone solver interface. They
implement an exact ring automaton, not a continuous differential equation or
a proven universal-CA embedding. Selection cannot alter logical truth:
the chosen literal is always a variable the caller marked eligible, and the
sign is read from the caller's own activity counts.

Field layout (``excitable-ring-four-lane-v1``), one flat float64 block of
``4 * size + 8`` lanes:

* ``[0, size)`` excitation: accumulated drive that a selection consumes.
* ``[size, 2 * size)`` recovery: refractory inhibition that selection raises.
* ``[2 * size, 3 * size)`` trace: slow emission/decay history of the site.
* ``[3 * size, 4 * size)`` previous excitation: the delay lane the coupling,
  recovery, and trace updates read, which makes each tick a synchronous
  double-buffered update and therefore order-independent.
* ``[4 * size, 4 * size + 8)`` header ``[magic, size, scale, ticks, selections,
  interventions, update_count, reserved]``; ``reserved`` must stay zero.

Every lane is an exact integer in ``[0, scale]`` except the header counters.

Tick law.  One tick is a synchronous update of all four lanes from the lanes
as they stood at the start of that tick, so site order can never matter. With
``E``, ``R``, ``T`` the excitation, recovery, and trace lanes, ``P`` the delay
lane, and ``D`` the per-site drive integrated from the caller's transient
counts (capped at ``scale``), one tick is::

    E'[s] = clamp(E[s] + (P[s-1] + P[s+1] - 2 * P[s]) // 16 - E[s] // 64
                       - R[s] // 4 + D[s], 0, scale)
    R'[s] = clamp(R[s] + P[s] // 16 - 1 - R[s] // 32, 0, scale)
    T'[s] = clamp(T[s] + P[s] // 4 - 1 - T[s] // 16, 0, scale)
    P'[s] = E[s]

Every ``//`` above denotes exact integer truncation toward zero -- the
module's own ``_trunc_div_into`` -- and not Python's floor division, so the
signed coupling term rounds symmetrically.  Every lane therefore stays an
exact in-range integer over any horizon.  ``advance`` runs at most ``4`` of
these ticks, charged against ``profile.max_ticks``; once the lifetime budget
is spent the field freezes and only selection continues, so the total work of
a controller lifetime is bounded and ``advance`` always terminates.

Selection.  The score of an eligible variable ``v`` at site ``s`` is
``(2 * scale + 1) * (positive[v] + negative[v]) + E[s] - R[s]``: solver
activity is the primary key and the controller's own field -- excitation
minus refractory recovery -- decides between variables of equal activity.
Ties fall to the smallest variable index.  The chosen site's excitation is
then consumed (``E[s] = 0``) and its recovery set to ``scale``, which is how a
decision feeds back into the field that makes the next one.

Intervention.  ``intervene(variable=v, excitation=x)`` writes one exact ``x``
in ``[0, scale]`` onto the excitation lane of site ``(v - 1) % size`` and
advances the header's intervention counter, so the header always agrees with
the writes that were folded in.  ``v`` only has to be a one-based exact
integer (``>= 1``): a site index outside the ring is wrapped rather than
refused, which lets a caller address a decision variable's site without
knowing the ring size.  No other site lane changes.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

SCHEMA = "cassifi.excitable-constraint-field.v1"
PROFILE_LAYOUT = "excitable-ring-four-lane-v1"
STEP_SCHEMA = "cassifi.excitable-step.v1"

_MAGIC = 0xEC51
_SAFE_INTEGER = 2**53 - 1

# Per-site lanes, each one contiguous run of `size` lanes.
_EXCITATION = 0
_RECOVERY = 1
_TRACE = 2
_PREVIOUS = 3
_LANES = 4

# Header lane coordinates at offset `4 * size`.
_H_MAGIC = 0
_H_SIZE = 1
_H_SCALE = 2
_H_TICKS = 3
_H_SELECTIONS = 4
_H_INTERVENTIONS = 5
_H_UPDATES = 6
_H_RESERVED = 7
_H_COUNT = 8

_COUNTER_COORDINATES = (_H_TICKS, _H_SELECTIONS, _H_INTERVENTIONS, _H_UPDATES)

# Fixed-point transition constants. All divisions are exact integer
# truncations toward zero, so a tick is deterministic on every platform.
_COUPLING_DIV = 16
_LEAK_DIV = 64
_INHIBIT_DIV = 4
_RECOVERY_GAIN = 16
_RECOVERY_STEP = 1
_RECOVERY_DECAY = 32
_TRACE_GAIN = 4
_TRACE_STEP = 1
_TRACE_DECAY = 16
_DRIVE_GAIN = 8
# Relaxation ticks performed by one advance call, charged against max_ticks.
_TICKS_PER_ADVANCE = 4
# Lane updates per site per tick: excitation, recovery, trace, delay lane.
_LANE_WRITES_PER_TICK = 4


class ExcitableConstraintError(ValueError):
    """Invalid excitable-constraint profile, state, or operation."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _exact_integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > _SAFE_INTEGER:
        raise ExcitableConstraintError(f"{name} must be an exact bounded integer")
    return value


def _is_lane_integer(value: Any) -> bool:
    return isinstance(value, (bool, np.bool_, int, np.integer))


def _trunc_div_into(
    numer: np.ndarray,
    denom: int,
    out: np.ndarray,
    remainder: np.ndarray,
    negative: np.ndarray,
    nonzero: np.ndarray,
) -> None:
    """``out = trunc(numer / denom)`` in exact int64 arithmetic, no allocation."""

    np.floor_divide(numer, denom, out=out)
    np.remainder(numer, denom, out=remainder)
    np.not_equal(remainder, 0, out=nonzero)
    np.less(numer, 0, out=negative)
    np.logical_and(nonzero, negative, out=nonzero)
    np.add(out, nonzero, out=out)


@dataclass(frozen=True, slots=True)
class ExcitableConstraintProfile:
    """Fixed storage and work geometry; it contains no problem-dependent state."""

    size: int
    scale: int = 1024
    max_ticks: int = 100_000

    def __post_init__(self) -> None:
        _exact_integer(self.size, "size", minimum=1)
        _exact_integer(self.scale, "scale", minimum=8)
        _exact_integer(self.max_ticks, "max_ticks", minimum=1)
        if self.lane_count > _SAFE_INTEGER:
            raise ExcitableConstraintError("excitable field exceeds exact address capacity")

    @property
    def lane_count(self) -> int:
        return _LANES * self.size + _H_COUNT

    @property
    def shape(self) -> tuple[int, ...]:
        return (self.lane_count,)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical({"layout": PROFILE_LAYOUT, **asdict(self)})).hexdigest()

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExcitableConstraintState:
    """One immutable field block bound to a fixed profile fingerprint."""

    _field: np.ndarray
    profile_sha256: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self._field, np.ndarray)
            or self._field.dtype != np.float64
            or self._field.ndim != 1
        ):
            raise ExcitableConstraintError("excitable field must be a one-dimensional float64 numpy array")
        if not isinstance(self.profile_sha256, str) or len(self.profile_sha256) != 64:
            raise ExcitableConstraintError("state profile fingerprint is invalid")
        field = np.array(self._field, dtype=np.float64, copy=True, order="C")
        field.flags.writeable = False
        object.__setattr__(self, "_field", field)

    @property
    def field(self) -> np.ndarray:
        return self._field.copy()

    @property
    def nbytes(self) -> int:
        return int(self._field.nbytes)


class ExcitableConstraintController:
    """Fixed transition law for a field-owned excitable decision scheduler."""

    def __init__(self, profile: ExcitableConstraintProfile) -> None:
        if not isinstance(profile, ExcitableConstraintProfile):
            raise ExcitableConstraintError("ExcitableConstraintProfile required")
        self.profile = profile

    # -- geometry -----------------------------------------------------------

    def _parts(self, state: ExcitableConstraintState, *, validate: bool = True) -> np.ndarray:
        if not isinstance(state, ExcitableConstraintState):
            raise ExcitableConstraintError("ExcitableConstraintState required")
        if state.profile_sha256 != self.profile.fingerprint:
            raise ExcitableConstraintError("state belongs to a different excitable-constraint profile")
        if tuple(state._field.shape) != self.profile.shape:
            raise ExcitableConstraintError("excitable field has an invalid shape")
        if validate:
            self.validate(state)
        return state._field


    def validate_lanes(self, field: np.ndarray) -> None:
        """Validate a raw mutable-or-immutable field lane block."""

        if not isinstance(field, np.ndarray):
            raise ExcitableConstraintError("excitable field must be a numpy array")
        if field.dtype != np.float64 or field.ndim != 1:
            raise ExcitableConstraintError(
                "excitable field must be a one-dimensional float64 numpy array"
            )
        if field.shape != self.profile.shape:
            raise ExcitableConstraintError("excitable field has an invalid shape")

        # Vectorized checks for finite, integer, and range constraints
        if not np.isfinite(field).all():
            raise ExcitableConstraintError("excitable field must contain finite exact integers")
        if not np.equal(field, np.floor(field)).all():
            raise ExcitableConstraintError("excitable field must contain finite exact integers")
        if np.any(np.abs(field) > _SAFE_INTEGER):
            raise ExcitableConstraintError("excitable field exceeds exact float64 integer range")

        size = self.profile.size
        scale = self.profile.scale
        lane_count = _LANES

        # Reshape lane data into 2D for bulk validation
        # field[:_LANES * size] contains the lane data
        lane_data = field[:lane_count * size]
        if lane_data.size != lane_count * size:
            # This should not happen if shape check passed, but for safety
            raise ExcitableConstraintError("excitable field has an invalid shape")

        # Reshape to (num_lanes, size_per_lane)
        # Note: field is 1D, so we reshape the slice
        lanes_2d = lane_data.reshape((lane_count, size))

        # Check if any lane has values < 0 or > scale
        if np.any(lanes_2d < 0) or np.any(lanes_2d > scale):
            raise ExcitableConstraintError("excitable lane value is outside the fixed-point range")

        # Header is the remaining part
        header_start = lane_count * size
        header = field[header_start:]

        # Direct integer conversion for header fields to avoid np.any overhead
        if int(header[_H_MAGIC]) != _MAGIC:
            raise ExcitableConstraintError("excitable field magic is invalid")
        if int(header[_H_SIZE]) != size:
            raise ExcitableConstraintError("stored site count disagrees with the profile")
        if int(header[_H_SCALE]) != scale:
            raise ExcitableConstraintError("stored scale disagrees with the profile")
        if int(header[_H_RESERVED]) != 0:
            raise ExcitableConstraintError("excitable header padding must be zero")

        # Check counter coordinates for negative values
        for coordinate in _COUNTER_COORDINATES:
            if int(header[coordinate]) < 0:
                raise ExcitableConstraintError("excitable counters cannot be negative")

        if int(header[_H_TICKS]) > self.profile.max_ticks:
            raise ExcitableConstraintError("tick counter exceeds the profile bound")

    def validate(self, state: ExcitableConstraintState) -> None:
        if not isinstance(state, ExcitableConstraintState):
            raise ExcitableConstraintError("ExcitableConstraintState required")
        if state.profile_sha256 != self.profile.fingerprint:
            raise ExcitableConstraintError("state belongs to a different excitable-constraint profile")
        self.validate_lanes(state._field)

    def _validate_mutable_lanes(self, field: np.ndarray) -> None:
        self.validate_lanes(field)
        if not field.flags.writeable:
            raise ExcitableConstraintError("excitable field must be writable")


    def state_sha256(self, state: ExcitableConstraintState) -> str:
        """Canonical digest over the field's exact native float64 bytes.

        The state block is always a C-contiguous one-dimensional float64
        array (``ExcitableConstraintState`` guarantees it), so the digest
        covers exactly ``lane_count * 8`` bytes in C order, prefixed by the
        canonical geometry header.
        """

        self._parts(state)
        digest = hashlib.sha256(
            _canonical(
                {
                    "layout": PROFILE_LAYOUT,
                    "profile_sha256": self.profile.fingerprint,
                    "shape": self.profile.shape,
                }
            )
        )
        digest.update(state._field.tobytes(order="C"))
        return digest.hexdigest()

    def _state(self, field: np.ndarray) -> ExcitableConstraintState:
        state = ExcitableConstraintState(field, self.profile.fingerprint)
        self.validate(state)
        return state

    def initial_lanes(self) -> np.ndarray:
        """Return a fresh writable raw field in the resting configuration."""

        field = np.zeros(self.profile.shape, dtype=np.float64)
        header = field[_LANES * self.profile.size :]
        header[_H_MAGIC] = _MAGIC
        header[_H_SIZE] = self.profile.size
        header[_H_SCALE] = self.profile.scale
        return field

    def initial(self) -> ExcitableConstraintState:
        """The resting field: every lane zero, every counter zero."""

        return self._state(self.initial_lanes())

    # -- dynamics -----------------------------------------------------------

    def _drive(self, counts: np.ndarray, variables: int) -> np.ndarray:
        """Per-site drive integrated from the transient solver activity.

        Counts are capped per variable at ``max(1, scale // max(1, variables))``
        and per site at ``scale`` before the gain is applied, so the
        accumulation can neither overflow int64 nor leave the declared
        fixed-point range.
        """

        size = self.profile.size
        scale = self.profile.scale
        ceiling = max(1, scale // max(1, variables))
        np.minimum(counts, ceiling, out=counts)
        sites = np.mod(np.arange(variables, dtype=np.int64), size)
        activity = np.zeros(size, dtype=np.int64)
        np.add.at(activity, sites, counts)
        np.minimum(activity, scale, out=activity)
        np.multiply(activity, _DRIVE_GAIN, out=activity)
        np.minimum(activity, scale, out=activity)
        return activity

    def _relax(
        self,
        excitation: np.ndarray,
        recovery: np.ndarray,
        trace: np.ndarray,
        previous: np.ndarray,
        drive: np.ndarray,
        ticks: int,
    ) -> None:
        """Run `ticks` synchronous bounded ticks in exact int64 arithmetic.

        Every new lane value is derived from the lanes as they stood at the
        start of the tick, so the tick is order-independent. The delay lane
        `previous` is the excitation of the tick before, which is why the
        coupling, recovery, and trace updates read it rather than the lane
        they are about to overwrite.
        """
        size = self.profile.size
        scale = self.profile.scale

        # Precompute indices for neighbor access to avoid np.take overhead
        left = (np.arange(size, dtype=np.int64) - 1) % size
        right = (np.arange(size, dtype=np.int64) + 1) % size

        # Allocate temporary buffers once outside the loop
        total = np.empty(size, dtype=np.int64)
        other = np.empty(size, dtype=np.int64)
        flux = np.empty(size, dtype=np.int64)
        leak = np.empty(size, dtype=np.int64)
        inhibit = np.empty(size, dtype=np.int64)
        remainder = np.empty(size, dtype=np.int64)
        negative = np.empty(size, dtype=bool)
        nonzero = np.empty(size, dtype=bool)
        next_excitation = np.empty(size, dtype=np.int64)
        next_recovery = np.empty(size, dtype=np.int64)
        next_trace = np.empty(size, dtype=np.int64)

        # Cache constants for speed
        COUPLING_DIV = _COUPLING_DIV
        LEAK_DIV = _LEAK_DIV
        INHIBIT_DIV = _INHIBIT_DIV
        RECOVERY_GAIN = _RECOVERY_GAIN
        RECOVERY_STEP = _RECOVERY_STEP
        RECOVERY_DECAY = _RECOVERY_DECAY
        TRACE_GAIN = _TRACE_GAIN
        TRACE_STEP = _TRACE_STEP
        TRACE_DECAY = _TRACE_DECAY

        # Pre-allocate arrays for np.take to avoid repeated lookups if we were doing it differently,
        # but here we just use the precomputed indices with take which is fast.
        # Actually, using take with indices is efficient enough, but we can optimize the inner loop.

        for _ in range(ticks):
            # Coupling: total = (previous[left] + previous[right]) - 2 * previous
            np.take(previous, left, out=total)
            np.take(previous, right, out=other)
            np.add(total, other, out=total)
            np.multiply(previous, 2, out=other)
            np.subtract(total, other, out=total)

            # flux = trunc(total / COUPLING_DIV)
            np.floor_divide(total, COUPLING_DIV, out=flux)
            np.remainder(total, COUPLING_DIV, out=remainder)
            np.not_equal(remainder, 0, out=nonzero)
            np.less(total, 0, out=negative)
            np.logical_and(nonzero, negative, out=nonzero)
            np.add(flux, nonzero, out=flux)

            # leak = trunc(excitation / LEAK_DIV)
            np.floor_divide(excitation, LEAK_DIV, out=leak)
            np.remainder(excitation, LEAK_DIV, out=remainder)
            np.not_equal(remainder, 0, out=nonzero)
            np.less(excitation, 0, out=negative)
            np.logical_and(nonzero, negative, out=nonzero)
            np.add(leak, nonzero, out=leak)

            # inhibit = trunc(recovery / INHIBIT_DIV)
            np.floor_divide(recovery, INHIBIT_DIV, out=inhibit)
            np.remainder(recovery, INHIBIT_DIV, out=remainder)
            np.not_equal(remainder, 0, out=nonzero)
            np.less(recovery, 0, out=negative)
            np.logical_and(nonzero, negative, out=nonzero)
            np.add(inhibit, nonzero, out=inhibit)

            # next_excitation = excitation + flux - leak - inhibit + drive
            np.add(excitation, flux, out=next_excitation)
            np.subtract(next_excitation, leak, out=next_excitation)
            np.subtract(next_excitation, inhibit, out=next_excitation)
            np.add(next_excitation, drive, out=next_excitation)

            # Clip next_excitation to [0, scale]
            np.clip(next_excitation, 0, scale, out=next_excitation)

            # Recovery update
            # total = trunc(previous / RECOVERY_GAIN)
            np.floor_divide(previous, RECOVERY_GAIN, out=total)
            np.add(recovery, total, out=next_recovery)
            np.subtract(next_recovery, RECOVERY_STEP, out=next_recovery)

            # other = trunc(recovery / RECOVERY_DECAY)
            np.floor_divide(recovery, RECOVERY_DECAY, out=other)
            np.subtract(next_recovery, other, out=next_recovery)

            # Clip next_recovery to [0, scale]
            np.clip(next_recovery, 0, scale, out=next_recovery)

            # Trace update
            # total = trunc(previous / TRACE_GAIN)
            np.floor_divide(previous, TRACE_GAIN, out=total)
            np.add(trace, total, out=next_trace)
            np.subtract(next_trace, TRACE_STEP, out=next_trace)

            # other = trunc(trace / TRACE_DECAY)
            np.floor_divide(trace, TRACE_DECAY, out=other)
            np.subtract(next_trace, other, out=next_trace)

            # Clip next_trace to [0, scale]
            np.clip(next_trace, 0, scale, out=next_trace)

            # Update state arrays
            np.copyto(previous, excitation)
            np.copyto(excitation, next_excitation)
            np.copyto(recovery, next_recovery)
            np.copyto(trace, next_trace)

    def _score_weight(self) -> int:
        """One unit of solver activity outweighs the whole field score range."""

        return 2 * self.profile.scale + 1

    @staticmethod
    def _sequence(value: Any, name: str, *, allow_boolean: bool) -> list[int]:
        if isinstance(value, np.ndarray):
            if value.ndim != 1:
                raise ExcitableConstraintError(f"{name} must be an ordered integer sequence")
            items: Sequence[Any] = value.tolist()
        elif isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise ExcitableConstraintError(f"{name} must be an ordered integer sequence")
        else:
            items = value
        result: list[int] = []
        for item in items:
            if not _is_lane_integer(item):
                raise ExcitableConstraintError(f"{name} must contain exact integers")
            if not allow_boolean and isinstance(item, (bool, np.bool_)):
                raise ExcitableConstraintError(f"{name} must contain exact integers")
            result.append(int(item))
        return result

    # -- public transition law ---------------------------------------------

    def advance_lanes(
        self,
        field: np.ndarray,
        *,
        positive: Sequence[int],
        negative: Sequence[int],
        eligible: Sequence[int],
    ) -> tuple[int | None, Mapping[str, Any]]:
        """Advance a writable raw field in place and select one decision.

        The caller owns ``field`` and remains responsible for retaining it.
        Validation completes before any field byte is changed.
        """

        self._validate_mutable_lanes(field)
        positive_counts = self._sequence(positive, "positive", allow_boolean=False)
        negative_counts = self._sequence(negative, "negative", allow_boolean=False)
        eligible_flags = self._sequence(eligible, "eligible", allow_boolean=True)
        variables = len(positive_counts)
        if len(negative_counts) != variables or len(eligible_flags) != variables:
            raise ExcitableConstraintError("positive, negative, and eligible must have equal length")
        if any(count < 0 for count in positive_counts + negative_counts):
            raise ExcitableConstraintError("activity counts cannot be negative")
        if any(count > _SAFE_INTEGER for count in positive_counts + negative_counts):
            raise ExcitableConstraintError("activity counts exceed exact float64 integer range")

        size = self.profile.size
        scale = self.profile.scale
        header = field[_LANES * size :]
        ticks_used = int(header[_H_TICKS])
        budget = min(_TICKS_PER_ADVANCE, self.profile.max_ticks - ticks_used)

        counts = np.array(positive_counts, dtype=np.int64)
        if variables:
            np.add(counts, np.array(negative_counts, dtype=np.int64), out=counts)
        drive = self._drive(counts, variables)

        excitation = field[_EXCITATION * size : (_EXCITATION + 1) * size].astype(np.int64)
        recovery = field[_RECOVERY * size : (_RECOVERY + 1) * size].astype(np.int64)
        trace = field[_TRACE * size : (_TRACE + 1) * size].astype(np.int64)
        previous = field[_PREVIOUS * size : (_PREVIOUS + 1) * size].astype(np.int64)
        self._relax(excitation, recovery, trace, previous, drive, budget)

        weight = self._score_weight()
        selected_variable: int | None = None
        selected_literal: int | None = None
        score = 0
        for index, flag in enumerate(eligible_flags):
            if not flag:
                continue
            site = index % size
            activity = positive_counts[index] + negative_counts[index]
            candidate = weight * activity + int(excitation[site]) - int(recovery[site])
            if selected_variable is None or candidate > score:
                selected_variable = index + 1
                selected_literal = (
                    index + 1 if positive_counts[index] > negative_counts[index] else -(index + 1)
                )
                score = candidate

        if selected_variable is not None:
            site = (selected_variable - 1) % size
            excitation[site] = 0
            recovery[site] = scale

        selections = _exact_integer(
            int(header[_H_SELECTIONS]) + int(selected_variable is not None),
            "selection counter",
        )
        updates = _exact_integer(int(header[_H_UPDATES]) + 1, "update counter")

        field[_EXCITATION * size : (_EXCITATION + 1) * size] = excitation
        field[_RECOVERY * size : (_RECOVERY + 1) * size] = recovery
        field[_TRACE * size : (_TRACE + 1) * size] = trace
        field[_PREVIOUS * size : (_PREVIOUS + 1) * size] = previous
        header[_H_TICKS] = ticks_used + budget
        header[_H_SELECTIONS] = selections
        header[_H_UPDATES] = updates

        receipt = {
            "schema": STEP_SCHEMA,
            "selected_literal": selected_literal,
            "selected_variable": selected_variable,
            "score": score,
            "ticks": int(header[_H_TICKS]),
            "work": {
                "ticks": budget,
                "local_ops": budget * size * _LANE_WRITES_PER_TICK,
            },
        }
        return selected_literal, receipt

    def advance(
        self,
        state: ExcitableConstraintState,
        *,
        positive: Sequence[int],
        negative: Sequence[int],
        eligible: Sequence[int],
    ) -> tuple[ExcitableConstraintState, int | None, Mapping[str, Any]]:
        """Relax the field, then select and consume one eligible decision.

        ``positive`` and ``negative`` are the caller's transient nonnegative
        activity counts (exact integers, booleans rejected) and ``eligible``
        marks the decisions the solver declared legal (any nonzero exact
        integer or boolean). All three need one entry per variable; variable
        ``v`` lives at site ``(v - 1) % size``.

        Returns the successor state, the signed literal (``+v``/``-v``,
        one-based, or ``None`` when no variable is eligible), and a JSON-safe
        receipt whose ``ticks`` is the lifetime tick counter and whose
        ``work.ticks`` is the relaxation this call actually performed.
        Relaxation is charged against ``profile.max_ticks``; once the lifetime
        budget is spent the field freezes (zero further ticks) and selection
        continues from the frozen lanes, which bounds total work.
        """

        field = self._parts(state, validate=False)
        successor = np.array(field, dtype=np.float64, copy=True)
        selected_literal, receipt = self.advance_lanes(
            successor,
            positive=positive,
            negative=negative,
            eligible=eligible,
        )
        return self._state(successor), selected_literal, receipt

    def intervene(
        self,
        state: ExcitableConstraintState,
        *,
        variable: int,
        excitation: int,
    ) -> ExcitableConstraintState:
        """Write one exact bounded excitation onto a site's excitation lane.

        The write is the whole intervention: only ``excitation`` at site
        ``(variable - 1) % size`` and the header's intervention counter
        change, so the successor is exactly bounded and still passes
        ``validate``.
        """

        field = self._parts(state)
        index = _exact_integer(variable, "variable", minimum=1)
        value = _exact_integer(excitation, "excitation")
        if value > self.profile.scale:
            raise ExcitableConstraintError("excitation exceeds the profile scale")

        size = self.profile.size
        successor = np.array(field, dtype=np.float64, copy=True)
        successor[(index - 1) % size] = value
        successor_header = successor[_LANES * size :]
        successor_header[_H_INTERVENTIONS] = int(successor_header[_H_INTERVENTIONS]) + 1
        return self._state(successor)

    # -- codec --------------------------------------------------------------

    def descriptor(self, state: ExcitableConstraintState) -> dict[str, Any]:
        self.validate(state)
        return {
            "schema": SCHEMA,
            "layout": PROFILE_LAYOUT,
            "profile": self.profile.as_dict(),
            "profile_sha256": self.profile.fingerprint,
            "field_b64": base64.b64encode(state._field).decode("ascii"),
            "state_sha256": self.state_sha256(state),
        }

    @classmethod
    def from_descriptor(
        cls, value: Mapping[str, Any]
    ) -> tuple[ExcitableConstraintController, ExcitableConstraintState]:
        required = {
            "schema",
            "layout",
            "profile",
            "profile_sha256",
            "field_b64",
            "state_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise ExcitableConstraintError("invalid excitable-constraint descriptor keys")
        if value["schema"] != SCHEMA or value["layout"] != PROFILE_LAYOUT:
            raise ExcitableConstraintError("unsupported excitable-constraint descriptor")
        if not isinstance(value["profile"], Mapping):
            raise ExcitableConstraintError("descriptor profile is invalid")
        try:
            profile = ExcitableConstraintProfile(**dict(value["profile"]))
        except (TypeError, ExcitableConstraintError) as exc:
            raise ExcitableConstraintError("descriptor profile is invalid") from exc
        controller = cls(profile)
        if value["profile_sha256"] != profile.fingerprint:
            raise ExcitableConstraintError("descriptor profile digest mismatch")
        encoded = value["field_b64"]
        if not isinstance(encoded, str):
            raise ExcitableConstraintError("descriptor field encoding is invalid")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ExcitableConstraintError("descriptor field encoding is invalid") from exc
        if len(raw) != profile.lane_count * np.dtype(np.float64).itemsize:
            raise ExcitableConstraintError("descriptor field block has the wrong byte length")
        field = np.frombuffer(raw, dtype=np.float64).copy()
        state = ExcitableConstraintState(field, profile.fingerprint)
        controller.validate(state)
        if value["state_sha256"] != controller.state_sha256(state):
            raise ExcitableConstraintError("descriptor state digest mismatch")
        return controller, state


__all__ = [
    "SCHEMA",
    "PROFILE_LAYOUT",
    "STEP_SCHEMA",
    "ExcitableConstraintController",
    "ExcitableConstraintError",
    "ExcitableConstraintProfile",
    "ExcitableConstraintState",
]
