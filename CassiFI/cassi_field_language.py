"""Trajectory-owned language sensing, memory, and active boundary emission.

The sole adaptive persistent object is ``QiFieldState.field``. Corpus
experience is retained as phase-coded circulation tracks in the inactive
common-mode half of each Qi scale; live multiscale history and port reactions
occupy the active differential half. No count table, finite context order,
learned projection, vocabulary model, or probabilistic sampler exists here.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

import torch
from cassi_text_codec import (
    FIELD_ALPHABET_SIZE,
    FIELD_BYTE_SYMBOLS,
    FIELD_TEXT_CODEC_SCHEMA,
    CassiFieldLanguageError,
    CassiFieldTextCodec,
    _canonical_json,
    _canonical_sha256,
)

from cassi_qi_field import (
    QiFieldConfig,
    QiFieldController,
    QiFieldError,
    QiFieldState,
)


QI_TRAJECTORY_CHECKPOINT_SCHEMA: Final[str] = "cassi.qi-trajectory-field.v1"
QI_SESSION_SCHEMA: Final[str] = "cassi.qi-text-session.v3"
QI_TEXT_STEP_SCHEMA: Final[str] = "cassi.qi-trajectory-text-step.v1"
QI_EMISSION_SCHEMA: Final[str] = "cassi.qi-trajectory-emission.v1"
QI_OUTPUT_STEP_SCHEMA: Final[str] = "cassi.qi-trajectory-output-step.v1"
QI_TEXT_RESULT_SCHEMA: Final[str] = "cassi.qi-trajectory-text-result.v1"
QI_TEXT_ENGINE_SCHEMA: Final[str] = "cassi.qi-trajectory-text-engine.v1"
FIELD_OUTPUT_DWELL_LIMIT: Final[int] = 4
FIELD_PORT_MARGIN_RATIO: Final[float] = 1.0e-6
FIELD_PORT_WORK_FLOOR: Final[float] = 1.0e-12
FIELD_LIVE_REGISTER_SIZE: Final[int] = 24
_MAX_SESSION_ID_BYTES: Final[int] = 512
_MAX_METADATA_BYTES: Final[int] = 1 << 20


def _tensor_sha256(value: torch.Tensor) -> str:
    tensor = value.detach().to(device="cpu", dtype=torch.float32).contiguous()
    return hashlib.sha256(tensor.numpy().tobytes(order="C")).hexdigest()


def _atomic_torch_save(path: Path, payload: object) -> str:
    stream = io.BytesIO()
    torch.save(payload, stream)
    serialized = stream.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
    return hashlib.sha256(serialized).hexdigest()


def qi_state_sha256(controller: QiFieldController, state: QiFieldState) -> str:
    state.validate(controller.config)
    return hashlib.sha256(
        _canonical_json(
            {
                "codebook_fingerprint": controller.codebook_fingerprint,
                "config_fingerprint": controller.config_fingerprint,
                "field_sha256": _tensor_sha256(state.field),
                "schema": QI_TRAJECTORY_CHECKPOINT_SCHEMA,
            }
        )
    ).hexdigest()



class CassiQiTrajectoryLaw:
    """Fixed multiscale circulation law over one canonical Qi field."""

    def __init__(self, controller: QiFieldController) -> None:
        self.controller = controller
        self.config = controller.config
        if self.config.alphabet_size != FIELD_ALPHABET_SIZE:
            raise CassiFieldLanguageError(
                f"trajectory language requires alphabet_size={FIELD_ALPHABET_SIZE}"
            )
        if self.config.scale_count < 2:
            raise CassiFieldLanguageError("trajectory language requires multiple scales")
        self.width = self.config.wave_mode_count
        if self.width < FIELD_ALPHABET_SIZE:
            raise CassiFieldLanguageError(
                "the active Qi sheet lacks 260 independent boundary dimensions"
            )
        if self.config.mode_count != 2 * self.width:
            raise CassiFieldLanguageError("trajectory mode partition is not exact")
        self.codec = CassiFieldTextCodec()
        multipliers = tuple(
            int(prime) % FIELD_ALPHABET_SIZE
            for prime in self.config.primes[: self.config.scale_count]
        )
        if any(math.gcd(value, FIELD_ALPHABET_SIZE) != 1 for value in multipliers):
            raise CassiFieldLanguageError("Qi scale prime does not define a complete event phase code")
        symbols = torch.arange(FIELD_ALPHABET_SIZE, dtype=torch.int64)
        phase_indices = (
            torch.tensor(multipliers, dtype=torch.int64)[:, None] * symbols[None, :]
        ) % FIELD_ALPHABET_SIZE
        angles = phase_indices.to(torch.float32) * (
            math.tau / FIELD_ALPHABET_SIZE
        )
        self.event_phases = torch.polar(torch.ones_like(angles), angles).to(
            torch.complex64
        )
        self.history_limits = tuple(
            min(self.width, 16 << scale)
            for scale in range(self.config.scale_count)
        )
        self.fingerprint = _canonical_sha256(
            {
                "active_width": self.width,
                "boundary": "fixed-260-event-prime-permuted-qi-phase-port",
                "codebook_fingerprint": controller.codebook_fingerprint,
                "config_fingerprint": controller.config_fingerprint,
                "context_law": "multiscale-recency-circulation",
                "emission": "self-timed-integrated-outgoing-work-reaction",
                "history_limits": list(self.history_limits),
                "phase_multipliers": list(multipliers),
                "port_tie_break": "0.02-next-event-phase-resonance",
                "trajectory_match": "contiguous-suffix-plus-0.01-distributed",
                "memory": "phase-coded-corpus-trajectory-banks",
                "memory_strength": "bounded-event-amplitude-(0.5,1]",
                "live_boundary_register": {
                    "modes": [1, FIELD_LIVE_REGISTER_SIZE],
                    "transition_law": "preserved-across-sense-dwell-reaction",
                },
                "memory_modes": [self.width, self.config.mode_count],
                "schema": QI_TEXT_ENGINE_SCHEMA,
            }
        )

    def _phases(self, device: torch.device) -> torch.Tensor:
        return self.event_phases.to(device=device)

    def neutral_context(self, *, device: torch.device) -> torch.Tensor:
        return torch.zeros(
            (self.config.scale_count, self.width),
            dtype=torch.complex64,
            device=device,
        )

    def initial_state(self, *, device: torch.device | str = "cpu") -> QiFieldState:
        target = torch.device(device)
        state = self.controller.initial_state(1, device=target, dtype=torch.float32)
        empty = self.neutral_context(device=target)
        return self._pack(state, memory=empty, context=empty, velocity=empty)

    def _coordinates(
        self, state: QiFieldState
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        state.validate(self.config)
        parts = state.field.reshape(
            self.config.scale_count,
            9,
            self.config.mode_count,
            1,
        )
        phi = self.config.phi
        active = slice(0, self.width)
        memory_modes = slice(self.width, self.config.mode_count)
        context = torch.complex(
            parts[:, 0, active, 0] - phi * parts[:, 2, active, 0],
            parts[:, 1, active, 0] - phi * parts[:, 3, active, 0],
        )
        velocity = torch.complex(
            parts[:, 4, active, 0] - phi * parts[:, 6, active, 0],
            parts[:, 5, active, 0] - phi * parts[:, 7, active, 0],
        )
        memory = torch.complex(
            phi * parts[:, 0, memory_modes, 0] + parts[:, 2, memory_modes, 0],
            phi * parts[:, 1, memory_modes, 0] + parts[:, 3, memory_modes, 0],
        )
        return memory, context, velocity

    def _pack(
        self,
        state: QiFieldState,
        *,
        memory: torch.Tensor | None = None,
        context: torch.Tensor | None = None,
        velocity: torch.Tensor | None = None,
    ) -> QiFieldState:
        field = state.field.detach().clone()
        parts = field.reshape(
            self.config.scale_count,
            9,
            self.config.mode_count,
            1,
        )
        phi = self.config.phi
        denominator = 1.0 + phi * phi
        active = slice(0, self.width)
        memory_modes = slice(self.width, self.config.mode_count)
        if memory is not None:
            bounded = memory / torch.clamp(
                memory.abs() / self.config.physics.max_mode_amplitude,
                min=1.0,
            )
            parts[:, 0, memory_modes, 0] = phi * bounded.real / denominator
            parts[:, 1, memory_modes, 0] = phi * bounded.imag / denominator
            parts[:, 2, memory_modes, 0] = bounded.real / denominator
            parts[:, 3, memory_modes, 0] = bounded.imag / denominator
            parts[:, 4:8, memory_modes, 0] = 0.0
        if context is not None:
            bounded = context / torch.clamp(
                context.abs() / self.config.physics.max_mode_amplitude,
                min=1.0,
            )
            parts[:, 0, active, 0] = bounded.real / denominator
            parts[:, 1, active, 0] = bounded.imag / denominator
            parts[:, 2, active, 0] = -phi * bounded.real / denominator
            parts[:, 3, active, 0] = -phi * bounded.imag / denominator
        if velocity is not None:
            bounded_velocity = velocity / torch.clamp(
                velocity.abs() / self.config.physics.max_mode_amplitude,
                min=1.0,
            )
            parts[:, 4, active, 0] = bounded_velocity.real / denominator
            parts[:, 5, active, 0] = bounded_velocity.imag / denominator
            parts[:, 6, active, 0] = -phi * bounded_velocity.real / denominator
            parts[:, 7, active, 0] = -phi * bounded_velocity.imag / denominator
        if memory is not None:
            imbalance = (
                parts[:, 0, memory_modes, 0].square()
                + parts[:, 1, memory_modes, 0].square()
                - phi
                * (
                    parts[:, 2, memory_modes, 0].square()
                    + parts[:, 3, memory_modes, 0].square()
                )
            )
            parts[:, 8, memory_modes, 0] = imbalance.square()
        if context is not None:
            imbalance = (
                parts[:, 0, active, 0].square()
                + parts[:, 1, active, 0].square()
                - phi
                * (
                    parts[:, 2, active, 0].square()
                    + parts[:, 3, active, 0].square()
                )
            )
            parts[:, 8, active, 0] = imbalance.square()
        result = QiFieldState(field)
        result.validate(self.config)
        if not bool(torch.isfinite(result.field).all().item()):
            raise CassiFieldLanguageError("trajectory law produced nonfinite field state")
        return result

    def memory_sha256(self, state: QiFieldState) -> str:
        state.validate(self.config)
        parts = state.field.reshape(
            self.config.scale_count,
            9,
            self.config.mode_count,
            1,
        )
        return _tensor_sha256(parts[:, :, self.width :, :])

    def memory_event_count(self, state: QiFieldState) -> int:
        memory, _, _ = self._coordinates(state)
        return int((memory.abs() > 0.5).sum().item())

    def reset_context(self, state: QiFieldState) -> QiFieldState:
        neutral = self.neutral_context(device=state.field.device)
        return self._pack(state, context=neutral, velocity=neutral)

    def rotate_live_context(self, state: QiFieldState, angle: float) -> QiFieldState:
        if not math.isfinite(angle):
            raise CassiFieldLanguageError("live context rotation must be finite")
        _, context, velocity = self._coordinates(state)
        if not bool((context.abs() > 0.5).any().item()):
            context = context.clone()
            velocity = velocity.clone()
            context[:, 0] = 1.0
            velocity[:, 0] = 1.0
        phase = torch.polar(
            torch.ones((), dtype=torch.float32, device=state.field.device),
            torch.tensor(float(angle), dtype=torch.float32, device=state.field.device),
        ).to(torch.complex64)
        return self._pack(
            state,
            context=context * phase,
            velocity=velocity * phase,
        )
    def write_live_boundary_values(
        self,
        state: QiFieldState,
        values: Sequence[float],
        *,
        offset: int = 0,
    ) -> QiFieldState:
        if isinstance(offset, bool) or offset < 0:
            raise CassiFieldLanguageError("live boundary register offset is invalid")
        if (
            not values
            or offset + len(values) > FIELD_LIVE_REGISTER_SIZE
            or 1 + offset + len(values) > self.width
        ):
            raise CassiFieldLanguageError("live boundary register size is invalid")
        normalized = tuple(float(value) for value in values)
        if not all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in normalized):
            raise CassiFieldLanguageError("live boundary value lies outside [-1, 1]")
        _, _, velocity = self._coordinates(state)
        successor = velocity.clone()
        start = 1 + offset
        successor[:, start : start + len(normalized)] = torch.tensor(
            normalized,
            dtype=torch.float32,
            device=state.field.device,
        ).to(torch.complex64)
        return self._pack(state, velocity=successor)

    def read_live_boundary_values(
        self,
        state: QiFieldState,
        count: int,
        *,
        offset: int = 0,
    ) -> tuple[float, ...]:
        if isinstance(count, bool) or not 1 <= count <= FIELD_LIVE_REGISTER_SIZE:
            raise CassiFieldLanguageError("live boundary register count is invalid")
        if (
            isinstance(offset, bool)
            or offset < 0
            or offset + count > FIELD_LIVE_REGISTER_SIZE
            or 1 + offset + count > self.width
        ):
            raise CassiFieldLanguageError("live boundary register offset is invalid")
        _, _, velocity = self._coordinates(state)
        start = 1 + offset
        values = velocity[:, start : start + count].real.mean(dim=0)
        if not bool(torch.isfinite(values).all().item()):
            raise CassiFieldLanguageError("live boundary register is nonfinite")
        return tuple(float(value) for value in values.tolist())



    def read_recent_symbols(
        self,
        state: QiFieldState,
        count: int,
    ) -> tuple[int, ...]:
        """Decode newest-first event ages from the live multiscale context."""
        horizon = max(self.history_limits)
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or not 1 <= count <= horizon
        ):
            raise CassiFieldLanguageError(
                f"recent symbol count must lie in [1, {horizon}]"
            )
        _, context, _ = self._coordinates(state)
        recent = context[:, :count]
        occupied = (recent.abs() > 0.5).all(dim=0)
        missing = (~occupied).nonzero(as_tuple=False)
        length = count if missing.numel() == 0 else int(missing[0].item())
        if length == 0:
            return ()
        scores = (
            self._phases(context.device)[:, :, None].conj()
            * recent[:, None, :length]
        ).real.mean(dim=0)
        return tuple(int(symbol) for symbol in scores.argmax(dim=0).tolist())


    def advance_context(self, context: torch.Tensor, symbol: int) -> torch.Tensor:
        if isinstance(symbol, bool) or not 0 <= int(symbol) < FIELD_ALPHABET_SIZE:
            raise CassiFieldLanguageError("trajectory symbol lies outside the fixed codec")
        successor = torch.roll(context, shifts=1, dims=1)
        successor[:, 0] = self._phases(context.device)[:, int(symbol)]
        return successor

    def sense_event(
        self, state: QiFieldState, symbol: int
    ) -> tuple[QiFieldState, float]:
        _, context, prior_velocity = self._coordinates(state)
        next_context = self.advance_context(context, symbol)
        velocity = torch.zeros_like(context)
        velocity[:, 1 : 1 + FIELD_LIVE_REGISTER_SIZE] = prior_velocity[
            :, 1 : 1 + FIELD_LIVE_REGISTER_SIZE
        ]
        velocity[:, 0] = self._phases(state.field.device)[:, int(symbol)]
        return self._pack(
            state,
            context=next_context,
            velocity=velocity,
        ), 1.0

    def dwell(self, state: QiFieldState) -> QiFieldState:
        _, context, velocity = self._coordinates(state)
        damping = math.exp(-self.config.physics.fast_damping * self.config.physics.dt)
        successor = velocity * damping
        successor[:, 1 : 1 + FIELD_LIVE_REGISTER_SIZE] = velocity[
            :, 1 : 1 + FIELD_LIVE_REGISTER_SIZE
        ]
        return self._pack(
            state,
            context=context,
            velocity=successor,
        )

    def react_event(
        self,
        state: QiFieldState,
        symbol: int,
        outgoing_work: float,
    ) -> tuple[QiFieldState, float]:
        _, context, prior_velocity = self._coordinates(state)
        next_context = self.advance_context(context, symbol)
        magnitude = max(
            0.05,
            abs(float(outgoing_work)) / (1.0 + abs(float(outgoing_work))),
        )
        reaction = torch.zeros_like(context)
        reaction[:, 1 : 1 + FIELD_LIVE_REGISTER_SIZE] = prior_velocity[
            :, 1 : 1 + FIELD_LIVE_REGISTER_SIZE
        ]
        reaction[:, 0] = -magnitude * self._phases(state.field.device)[:, int(symbol)]
        return self._pack(
            state,
            context=next_context,
            velocity=reaction,
        ), -float(reaction.abs().square().mean().item())

    def _port_scores(
        self,
        memory: torch.Tensor,
        context: torch.Tensor,
    ) -> torch.Tensor:
        device = memory.device
        phases = self._phases(device)
        scores = torch.zeros(FIELD_ALPHABET_SIZE, dtype=torch.float32, device=device)
        for scale, history_limit in enumerate(self.history_limits):
            query_length = min(
                history_limit,
                int((context[scale].abs() > 0.5).sum().item()),
            )
            if query_length == 0:
                continue
            query = context[scale, :query_length]
            bank = memory[scale]
            occupied = bank.abs() > 0.5
            decoded = (
                phases[scale, :, None].conj() * bank[None, :]
            ).real.argmax(dim=0)
            query_symbols = (
                phases[scale, :, None].conj() * query[None, :]
            ).real.argmax(dim=0)
            bank_symbols = torch.where(
                occupied,
                decoded,
                torch.full_like(decoded, -1),
            )
            previous = torch.cat(
                (
                    torch.full(
                        (query_length,),
                        -1,
                        dtype=bank_symbols.dtype,
                        device=device,
                    ),
                    bank_symbols,
                )
            ).unfold(0, query_length, 1)[: self.width].flip(1)
            valid = torch.cumprod(
                (previous >= 0).to(torch.int32),
                dim=1,
            ).to(torch.bool)
            count = valid.sum(dim=1)
            matched = (previous == query_symbols) & valid
            contiguous = torch.cumprod(
                matched.to(torch.int32),
                dim=1,
            ).sum(dim=1)
            distributed = matched.sum(dim=1) / count.clamp_min(1).sqrt()
            alignment = (contiguous + 0.01 * distributed) * bank.abs()
            alignment = alignment + 0.02 * (bank * query[0].conj()).real
            candidate = occupied & (count > 0)
            scale_scores = torch.zeros_like(scores)
            scale_scores.scatter_reduce_(
                0,
                decoded[candidate],
                alignment[candidate].clamp_min(0.0).to(torch.float32),
                reduce="amax",
                include_self=True,
            )
            scores = torch.maximum(scores, scale_scores)
        if not bool(torch.isfinite(scores).all().item()):
            raise CassiFieldLanguageError("trajectory port score is nonfinite")
        return scores

    def port_scores(self, state: QiFieldState) -> torch.Tensor:
        memory, context, _ = self._coordinates(state)
        return self._port_scores(memory, context)

    def candidate_sequence_work(
        self,
        state: QiFieldState,
        symbols: Sequence[int],
    ) -> tuple[float, tuple[float, ...]]:
        if not symbols or any(
            isinstance(symbol, bool)
            or not isinstance(symbol, int)
            or not 0 <= symbol < FIELD_ALPHABET_SIZE
            for symbol in symbols
        ):
            raise CassiFieldLanguageError("candidate sequence contains an invalid event")
        memory, context, _ = self._coordinates(state)
        event_work: list[float] = []
        for symbol in symbols:
            work = max(0.0, float(self._port_scores(memory, context)[symbol].item()))
            event_work.append(work)
            context = self.advance_context(context, symbol)
        return float(sum(event_work)), tuple(event_work)

    def learn_sequence(
        self,
        state: QiFieldState,
        symbols: Sequence[int],
        *,
        strength: float = 1.0,
        minimum_history: int = 0,
    ) -> QiFieldState:
        if len(symbols) < 2:
            raise CassiFieldLanguageError("trajectory learning needs two or more events")
        if any(
            isinstance(symbol, bool)
            or not isinstance(symbol, int)
            or not 0 <= symbol < FIELD_ALPHABET_SIZE
            for symbol in symbols
        ):
            raise CassiFieldLanguageError("trajectory experience contains an invalid event")
        if not math.isfinite(strength) or not 0.5 < float(strength) <= 1.0:
            raise CassiFieldLanguageError(
                "trajectory strength must be finite in the interval (0.5, 1]"
            )
        if (
            isinstance(minimum_history, bool)
            or not isinstance(minimum_history, int)
            or minimum_history < 0
        ):
            raise CassiFieldLanguageError("minimum trajectory history must be nonnegative")
        memory, _, _ = self._coordinates(state)
        starts: list[tuple[int, int]] = []
        episode_length = len(symbols)
        for scale in range(self.config.scale_count):
            if self.history_limits[scale] < minimum_history:
                continue
            occupied = (
                memory[scale].abs() > 0.5
            ).tolist()
            cursor = 0
            while cursor < self.width:
                while cursor < self.width and occupied[cursor]:
                    cursor += 1
                free_start = cursor
                while cursor < self.width and not occupied[cursor]:
                    cursor += 1
                free_end = cursor
                candidate = free_start if free_start == 0 else free_start + 1
                if candidate + episode_length < free_end:
                    starts.append((candidate, scale))
                    break
        if not starts:
            raise CassiFieldLanguageError(
                "trajectory field capacity is exhausted; increase mode_count or sample fewer episodes"
            )
        start, scale = min(starts)
        learned = memory.clone()
        indices = torch.tensor(symbols, dtype=torch.long, device=state.field.device)
        learned[scale, start : start + len(symbols)] = (
            self._phases(state.field.device)[scale, indices] * float(strength)
        )
        neutral = self.neutral_context(device=state.field.device)
        return self._pack(
            state,
            memory=learned,
            context=neutral,
            velocity=neutral,
        )

    def _exact_sequence_windows(
        self,
        state: QiFieldState,
    ) -> tuple[tuple[int, int, int, tuple[int, ...]], ...]:
        memory, _, _ = self._coordinates(state)
        phases = self._phases(state.field.device)
        windows: list[tuple[int, int, int, tuple[int, ...]]] = []
        for scale in range(self.config.scale_count):
            occupied = (memory[scale].abs() > 0.5).tolist()
            decoded = (
                phases[scale, :, None].conj() * memory[scale][None, :]
            ).real.argmax(dim=0).tolist()
            start = 0
            while start < self.width:
                while start < self.width and not occupied[start]:
                    start += 1
                end = start
                while end < self.width and occupied[end]:
                    end += 1
                if start < end:
                    windows.append((scale, start, end, tuple(decoded[start:end])))
                start = end + 1
        return tuple(windows)

    def exact_sequence_scale(
        self,
        state: QiFieldState,
        symbols: Sequence[int],
    ) -> int | None:
        target = tuple(int(symbol) for symbol in symbols)
        for scale, _, _, sequence in self._exact_sequence_windows(state):
            if sequence == target:
                return scale
        return None

    def age_exact_sequences(
        self,
        state: QiFieldState,
        sequences: Sequence[Sequence[int]],
        *,
        steps: int = 1,
    ) -> tuple[QiFieldState, tuple[tuple[int, ...], ...]]:
        """Age exact learned episodes in their field amplitudes, by scale."""
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise CassiFieldLanguageError("trajectory age steps must be a positive integer")
        targets = {tuple(int(symbol) for symbol in sequence) for sequence in sequences}
        if not targets:
            return state, ()
        memory, _, _ = self._coordinates(state)
        aged = memory.clone()
        retired: list[tuple[int, ...]] = []
        changed = False
        for scale, start, end, sequence in self._exact_sequence_windows(state):
            if sequence not in targets:
                continue
            factor = 0.5 ** (steps / self.history_limits[scale])
            aged[scale, start:end] *= factor
            changed = True
            if float(aged[scale, start:end].abs().max().item()) <= 0.5:
                aged[scale, start:end] = 0.0
                retired.append(sequence)
        if not changed:
            return state, ()
        return self._pack(state, memory=aged), tuple(retired)

    def forget_exact_sequences(
        self,
        state: QiFieldState,
        sequences: Sequence[Sequence[int]],
    ) -> tuple[QiFieldState, int]:
        """Retire complete trajectory episodes while preserving all live state."""
        targets = {
            tuple(int(symbol) for symbol in sequence)
            for sequence in sequences
        }
        if not targets or any(
            len(sequence) < 2
            or any(not 0 <= symbol < FIELD_ALPHABET_SIZE for symbol in sequence)
            for sequence in targets
        ):
            raise CassiFieldLanguageError("forgotten trajectory sequence is invalid")
        memory, _, _ = self._coordinates(state)
        learned = memory.clone()
        removed = 0
        for scale, start, end, sequence in self._exact_sequence_windows(state):
            if sequence in targets:
                learned[scale, start:end] = 0.0
                removed += end - start
        if removed == 0:
            return state, 0
        compacted = torch.zeros_like(learned)
        for scale in range(self.config.scale_count):
            occupied = (learned[scale].abs() > 0.5).tolist()
            source = 0
            target = 0
            while source < self.width:
                while source < self.width and not occupied[source]:
                    source += 1
                end = source
                while end < self.width and occupied[end]:
                    end += 1
                if source < end:
                    length = end - source
                    compacted[scale, target : target + length] = learned[
                        scale, source:end
                    ]
                    target += length + 1
                source = end + 1
        return self._pack(state, memory=compacted), removed

    def sequence_accuracy(
        self, state: QiFieldState, symbols: Sequence[int]
    ) -> tuple[int, int]:
        if len(symbols) < 2:
            return 0, 0
        memory, _, _ = self._coordinates(state)
        context = self.neutral_context(device=state.field.device)
        correct = 0
        total = 0
        for source, target in zip(symbols[:-1], symbols[1:], strict=True):
            context = self.advance_context(context, int(source))
            scores = self._port_scores(memory, context)
            correct += int(int(scores.argmax().item()) == int(target))
            total += 1
        return correct, total


@dataclasses.dataclass(frozen=True)
class CassiQiTextStepReceipt:
    phase: str
    position: int
    symbol: int
    boundary_direction: str
    state_before_sha256: str
    state_after_sha256: str
    boundary_work: float
    schema: str = QI_TEXT_STEP_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != QI_TEXT_STEP_SCHEMA:
            raise CassiFieldLanguageError("text-step receipt schema mismatch")
        if self.boundary_direction not in {"inbound", "outbound"}:
            raise CassiFieldLanguageError("text-step boundary direction is invalid")
        if not math.isfinite(self.boundary_work):
            raise CassiFieldLanguageError("text-step work is nonfinite")

    def receipt_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @property
    def receipt_sha256(self) -> str:
        return _canonical_sha256(self.receipt_dict())


@dataclasses.dataclass(frozen=True)
class CassiQiEmissionReceipt:
    symbol: int | None
    available: bool
    state_sha256: str
    dwell_ticks: int
    accumulated_outgoing_work: float
    runner_up_work: float
    margin: float
    scores_sha256: str
    trained_memory_sha256: str
    schema: str = QI_EMISSION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != QI_EMISSION_SCHEMA:
            raise CassiFieldLanguageError("emission receipt schema mismatch")
        if self.available != (self.symbol is not None):
            raise CassiFieldLanguageError("emission availability is inconsistent")
        if not all(
            math.isfinite(value)
            for value in (
                self.accumulated_outgoing_work,
                self.runner_up_work,
                self.margin,
            )
        ):
            raise CassiFieldLanguageError("emission work is nonfinite")

    def receipt_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @property
    def receipt_sha256(self) -> str:
        return _canonical_sha256(self.receipt_dict())


@dataclasses.dataclass(frozen=True)
class CassiQiOutputStepReceipt:
    emission: CassiQiEmissionReceipt
    commitment: CassiQiTextStepReceipt
    schema: str = QI_OUTPUT_STEP_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != QI_OUTPUT_STEP_SCHEMA:
            raise CassiFieldLanguageError("output-step receipt schema mismatch")
        if self.emission.symbol != self.commitment.symbol:
            raise CassiFieldLanguageError("emission and commitment symbol mismatch")
        if self.emission.state_sha256 != self.commitment.state_before_sha256:
            raise CassiFieldLanguageError("emission and commitment state mismatch")
        if self.commitment.boundary_direction != "outbound":
            raise CassiFieldLanguageError("output commitment is not an outbound action")

    def receipt_dict(self) -> dict[str, Any]:
        return {
            "commitment": self.commitment.receipt_dict(),
            "commitment_receipt_sha256": self.commitment.receipt_sha256,
            "emission": self.emission.receipt_dict(),
            "emission_receipt_sha256": self.emission.receipt_sha256,
            "schema": self.schema,
        }

    @property
    def receipt_sha256(self) -> str:
        return _canonical_sha256(self.receipt_dict())


@dataclasses.dataclass(frozen=True)
class CassiQiTextResult:
    state: QiFieldState
    prompt_symbols: tuple[int, ...]
    output_symbols: tuple[int, ...]
    output_bytes: bytes
    text: str
    stop_reason: str
    prompt_receipts: tuple[CassiQiTextStepReceipt, ...]
    output_receipts: tuple[CassiQiOutputStepReceipt, ...]
    terminal_receipt: CassiQiOutputStepReceipt | None
    initial_state_sha256: str
    final_state_sha256: str
    config_fingerprint: str
    codebook_fingerprint: str
    codec_fingerprint: str
    trajectory_fingerprint: str
    engine_fingerprint: str
    checkpoint_sha256: str
    corpus_identity: str
    corpus_memory_sha256: str
    schema: str = QI_TEXT_RESULT_SCHEMA

    @property
    def byte_sha256(self) -> str:
        return hashlib.sha256(self.output_bytes).hexdigest()

    @property
    def all_outputs_field_owned(self) -> bool:
        receipts = list(self.output_receipts)
        if self.terminal_receipt is not None:
            receipts.append(self.terminal_receipt)
        return bool(receipts) and all(
            receipt.emission.available
            and receipt.emission.state_sha256
            == receipt.commitment.state_before_sha256
            and receipt.commitment.boundary_direction == "outbound"
            for receipt in receipts
        )

    def render_text(
        self,
        controller: QiFieldController,
        input_utf8_bytes: int,
    ) -> tuple[str, str]:
        if self.output_bytes and self.all_outputs_field_owned:
            return self.text, "field-symbols"
        energies = controller.energies(self.state)
        return (
            "Qi field remained silent after "
            f"{int(input_utf8_bytes)} input bytes; mean energy "
            f"{float(energies.mean().item()):.6f}.",
            "field-abstention",
        )

    @property
    def replacement_count(self) -> int:
        return self.text.count("\ufffd")

    def receipt_dict(self) -> dict[str, Any]:
        return {
            "all_outputs_field_owned": self.all_outputs_field_owned,
            "architecture": {
                "adaptive_persistent_tensor_count": 1,
                "boundary_codec": "fixed-utf8-byte-control-v1",
                "corpus_trained": True,
                "engineered_feature_width": 0,
                "external_adaptive_table_count": 0,
                "learned_parameter_count": 0,
                "lexical_boundary": "none",
                "memory_law": "multiscale-phase-coded-trajectory-circulation",
                "neural_layer_count": 0,
                "optimizer_state_bytes": 0,
                "output_commitment": "self-timed-passive-port-reaction",
                "probabilistic_sampler": False,
                "state_layout": "[S,9M,B]",
            },
            "checkpoint_sha256": self.checkpoint_sha256,
            "codebook_fingerprint": self.codebook_fingerprint,
            "codec_fingerprint": self.codec_fingerprint,
            "config_fingerprint": self.config_fingerprint,
            "corpus_identity": self.corpus_identity,
            "corpus_memory_sha256": self.corpus_memory_sha256,
            "engine_fingerprint": self.engine_fingerprint,
            "final_state_sha256": self.final_state_sha256,
            "initial_state_sha256": self.initial_state_sha256,
            "output_bytes_sha256": self.byte_sha256,
            "output_receipts": [value.receipt_dict() for value in self.output_receipts],
            "output_symbols": list(self.output_symbols),
            "prompt_receipts": [value.receipt_dict() for value in self.prompt_receipts],
            "prompt_symbols": list(self.prompt_symbols),
            "schema": self.schema,
            "stop_reason": self.stop_reason,
            "terminal_receipt": (
                None if self.terminal_receipt is None else self.terminal_receipt.receipt_dict()
            ),
            "text": self.text,
            "trajectory_fingerprint": self.trajectory_fingerprint,
        }

    @property
    def receipt_sha256(self) -> str:
        return _canonical_sha256(self.receipt_dict())


class CassiQiTextEngine:
    """The live prompt-to-port runtime over one trained trajectory field."""

    def __init__(
        self,
        controller: QiFieldController,
        *,
        checkpoint_path: Path,
        max_output_symbols: int = 96,
    ) -> None:
        if isinstance(max_output_symbols, bool) or not 1 <= max_output_symbols <= 4096:
            raise CassiFieldLanguageError("max_output_symbols must lie in [1, 4096]")
        self.controller = controller
        self.codec = CassiFieldTextCodec()
        self.law = CassiQiTrajectoryLaw(controller)
        self.max_output_symbols = int(max_output_symbols)
        self.checkpoint_path = Path(checkpoint_path).resolve()
        try:
            checkpoint_bytes = self.checkpoint_path.read_bytes()
        except OSError as error:
            raise CassiFieldLanguageError(
                f"trajectory checkpoint is unavailable: {error}"
            ) from error
        self.checkpoint_sha256 = hashlib.sha256(checkpoint_bytes).hexdigest()
        self._base_state, metadata = self._load_checkpoint(self.checkpoint_path)
        self.corpus_identity = metadata["corpus_identity"]
        self.corpus_memory_sha256 = self.law.memory_sha256(self._base_state)
        self.fingerprint = _canonical_sha256(
            {
                "checkpoint_sha256": self.checkpoint_sha256,
                "codec_fingerprint": self.codec.fingerprint,
                "corpus_identity": self.corpus_identity,
                "max_output_symbols": self.max_output_symbols,
                "schema": QI_TEXT_ENGINE_SCHEMA,
                "trajectory_fingerprint": self.law.fingerprint,
            }
        )

    def _load_checkpoint(self, path: Path) -> tuple[QiFieldState, dict[str, str]]:
        try:
            payload = torch.load(path, map_location="cpu", weights_only=True)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise CassiFieldLanguageError(
                f"failed to load trajectory checkpoint: {error}"
            ) from error
        expected = {
            "codebook_fingerprint",
            "codec_fingerprint",
            "config_fingerprint",
            "corpus_identity",
            "field",
            "memory_sha256",
            "schema",
            "training_episode_count",
            "training_event_count",
            "trajectory_fingerprint",
        }
        if not isinstance(payload, dict) or set(payload) != expected:
            raise CassiFieldLanguageError("trajectory checkpoint has an unexpected key set")
        if payload.get("schema") != QI_TRAJECTORY_CHECKPOINT_SCHEMA:
            raise CassiFieldLanguageError("trajectory checkpoint schema mismatch")
        checks = {
            "codebook_fingerprint": self.controller.codebook_fingerprint,
            "codec_fingerprint": self.codec.fingerprint,
            "config_fingerprint": self.controller.config_fingerprint,
            "trajectory_fingerprint": self.law.fingerprint,
        }
        for key, expected_value in checks.items():
            if payload.get(key) != expected_value:
                raise CassiFieldLanguageError(f"trajectory checkpoint {key} mismatch")
        corpus_identity = payload.get("corpus_identity")
        if not isinstance(corpus_identity, str) or len(corpus_identity) != 64:
            raise CassiFieldLanguageError("trajectory corpus identity is invalid")
        field = payload.get("field")
        if not isinstance(field, torch.Tensor) or field.dtype != torch.float32:
            raise CassiFieldLanguageError("trajectory checkpoint field is not float32")
        state = QiFieldState(field.detach().clone().contiguous())
        state.validate(self.controller.config)
        if self.law.memory_sha256(state) != payload.get("memory_sha256"):
            raise CassiFieldLanguageError("trajectory checkpoint memory mismatch")
        return state, {"corpus_identity": corpus_identity}

    def state_sha256(self, state: QiFieldState) -> str:
        return qi_state_sha256(self.controller, state)

    def initial_state(
        self,
        *,
        device: torch.device | str = "cpu",
        dtype: torch.dtype = torch.float32,
    ) -> QiFieldState:
        if dtype != torch.float32:
            raise CassiFieldLanguageError("trajectory state requires float32")
        return QiFieldState(self._base_state.field.detach().to(device=device).clone())

    def _sense(
        self,
        state: QiFieldState,
        symbol: int,
        *,
        phase: str,
        position: int,
    ) -> tuple[QiFieldState, CassiQiTextStepReceipt]:
        before = self.state_sha256(state)
        successor, work = self.law.sense_event(state, symbol)
        receipt = CassiQiTextStepReceipt(
            phase=phase,
            position=position,
            symbol=int(symbol),
            boundary_direction="inbound",
            state_before_sha256=before,
            state_after_sha256=self.state_sha256(successor),
            boundary_work=work,
        )
        return successor, receipt

    def _emit(
        self,
        state: QiFieldState,
        prefix: bytes,
    ) -> tuple[QiFieldState, CassiQiEmissionReceipt]:
        working = state
        accumulated = torch.zeros(
            FIELD_ALPHABET_SIZE,
            dtype=torch.float32,
            device=state.field.device,
        )
        mask = self.codec.output_mask(prefix, device=state.field.device)
        for dwell_ticks in range(FIELD_OUTPUT_DWELL_LIMIT + 1):
            scores = self.law.port_scores(working)
            accumulated = accumulated + torch.clamp(scores, min=0.0)
            eligible = accumulated.masked_fill(~mask, -torch.inf)
            top_values, top_indices = torch.topk(eligible, k=2)
            top = float(top_values[0].item())
            runner_up = float(top_values[1].item())
            margin = top - runner_up
            required_margin = max(FIELD_PORT_WORK_FLOOR, abs(top) * FIELD_PORT_MARGIN_RATIO)
            if math.isfinite(top) and top > FIELD_PORT_WORK_FLOOR and margin >= required_margin:
                return working, CassiQiEmissionReceipt(
                    symbol=int(top_indices[0].item()),
                    available=True,
                    state_sha256=self.state_sha256(working),
                    dwell_ticks=dwell_ticks,
                    accumulated_outgoing_work=top,
                    runner_up_work=runner_up,
                    margin=margin,
                    scores_sha256=_tensor_sha256(accumulated),
                    trained_memory_sha256=self.law.memory_sha256(working),
                )
            if dwell_ticks < FIELD_OUTPUT_DWELL_LIMIT:
                working = self.law.dwell(working)
        finite = accumulated[mask]
        runner_up = (
            0.0
            if finite.numel() == 0
            else float(
                torch.topk(finite, k=min(2, int(finite.numel()))).values[-1].item()
            )
        )
        return working, CassiQiEmissionReceipt(
            symbol=None,
            available=False,
            state_sha256=self.state_sha256(working),
            dwell_ticks=FIELD_OUTPUT_DWELL_LIMIT,
            accumulated_outgoing_work=0.0,
            runner_up_work=runner_up,
            margin=0.0,
            scores_sha256=_tensor_sha256(accumulated),
            trained_memory_sha256=self.law.memory_sha256(working),
        )

    def generate(
        self,
        state: QiFieldState,
        messages: Sequence[Mapping[str, Any]],
        *,
        max_output_symbols: int | None = None,
    ) -> CassiQiTextResult:
        output_limit = (
            self.max_output_symbols
            if max_output_symbols is None
            else int(max_output_symbols)
        )
        if (
            isinstance(max_output_symbols, bool)
            or not 1 <= output_limit <= self.max_output_symbols
        ):
            raise CassiFieldLanguageError(
                "per-call max_output_symbols must lie within the engine limit"
            )
        state.validate(self.controller.config)
        if self.law.memory_sha256(state) != self.corpus_memory_sha256:
            raise CassiFieldLanguageError("live state changed the trained trajectory memory")
        initial_sha256 = self.state_sha256(state)
        prompt_symbols = self.codec.encode_messages(messages) + (
            self.codec.assistant_symbol,
        )
        prompt_receipts: list[CassiQiTextStepReceipt] = []
        working = state
        for position, symbol in enumerate(prompt_symbols):
            working, receipt = self._sense(
                working,
                symbol,
                phase="prompt",
                position=position,
            )
            prompt_receipts.append(receipt)

        output_symbols: list[int] = []
        output_receipts: list[CassiQiOutputStepReceipt] = []
        terminal_receipt: CassiQiOutputStepReceipt | None = None
        output_bytes = bytearray()
        stop_reason = "max_output_symbols"
        for position in range(output_limit):
            emission_state, emission = self._emit(working, bytes(output_bytes))
            if not emission.available or emission.symbol is None:
                working = emission_state
                stop_reason = "field_abstained"
                break
            before = self.state_sha256(emission_state)
            successor, reaction_work = self.law.react_event(
                emission_state,
                emission.symbol,
                emission.accumulated_outgoing_work,
            )
            commitment = CassiQiTextStepReceipt(
                phase="output",
                position=position,
                symbol=emission.symbol,
                boundary_direction="outbound",
                state_before_sha256=before,
                state_after_sha256=self.state_sha256(successor),
                boundary_work=reaction_work,
            )
            receipt = CassiQiOutputStepReceipt(
                emission=emission,
                commitment=commitment,
            )
            working = successor
            if emission.symbol == self.codec.end_turn_symbol:
                terminal_receipt = receipt
                stop_reason = "end_turn"
                break
            output_symbols.append(emission.symbol)
            output_bytes.append(emission.symbol)
            output_receipts.append(receipt)

        raw, text = self.codec.decode_symbols(output_symbols)
        final_sha256 = self.state_sha256(working)
        if self.law.memory_sha256(working) != self.corpus_memory_sha256:
            raise CassiFieldLanguageError("generation mutated trained trajectory memory")
        return CassiQiTextResult(
            state=working,
            prompt_symbols=prompt_symbols,
            output_symbols=tuple(output_symbols),
            output_bytes=raw,
            text=text,
            stop_reason=stop_reason,
            prompt_receipts=tuple(prompt_receipts),
            output_receipts=tuple(output_receipts),
            terminal_receipt=terminal_receipt,
            initial_state_sha256=initial_sha256,
            final_state_sha256=final_sha256,
            config_fingerprint=self.controller.config_fingerprint,
            codebook_fingerprint=self.controller.codebook_fingerprint,
            codec_fingerprint=self.codec.fingerprint,
            trajectory_fingerprint=self.law.fingerprint,
            engine_fingerprint=self.fingerprint,
            checkpoint_sha256=self.checkpoint_sha256,
            corpus_identity=self.corpus_identity,
            corpus_memory_sha256=self.corpus_memory_sha256,
        )


class CassiQiSessionStore:
    """Atomic per-session persistence of one Qi state plus non-adaptive metadata."""

    def __init__(
        self,
        root: Path,
        controller: QiFieldController,
        *,
        engine_fingerprint: str,
    ) -> None:
        self.root = Path(root)
        self.controller = controller
        if not isinstance(engine_fingerprint, str) or len(engine_fingerprint) != 64:
            raise CassiFieldLanguageError("engine fingerprint must be a SHA-256 digest")
        self.engine_fingerprint = engine_fingerprint
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate_session_id(self, session_id: str) -> str:
        if not isinstance(session_id, str) or not session_id:
            raise CassiFieldLanguageError("session id must be nonempty text")
        if len(session_id.encode("utf-8")) > _MAX_SESSION_ID_BYTES:
            raise CassiFieldLanguageError("session id exceeds the bounded limit")
        return session_id

    def path_for(self, session_id: str) -> Path:
        value = self._validate_session_id(session_id)
        return self.root / f"{hashlib.sha256(value.encode('utf-8')).hexdigest()}.pt"

    def load(self, session_id: str) -> tuple[QiFieldState, dict[str, Any], Path] | None:
        path = self.path_for(session_id)
        if not path.is_file():
            return None
        try:
            payload = torch.load(path, map_location="cpu", weights_only=True)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise CassiFieldLanguageError(f"failed to load Qi session: {error}") from error
        if not isinstance(payload, dict) or payload.get("schema") != QI_SESSION_SCHEMA:
            raise CassiFieldLanguageError("Qi session schema mismatch")
        if payload.get("session_id") != session_id:
            raise CassiFieldLanguageError("Qi session identity mismatch")
        if payload.get("engine_fingerprint") != self.engine_fingerprint:
            raise CassiFieldLanguageError("Qi session engine fingerprint mismatch")
        if payload.get("config_fingerprint") != self.controller.config_fingerprint:
            raise CassiFieldLanguageError("Qi session config fingerprint mismatch")
        if payload.get("codebook_fingerprint") != self.controller.codebook_fingerprint:
            raise CassiFieldLanguageError("Qi session codebook fingerprint mismatch")
        state_bytes = payload.get("state_bytes")
        metadata_bytes = payload.get("metadata")
        if not isinstance(state_bytes, bytes) or not isinstance(metadata_bytes, bytes):
            raise CassiFieldLanguageError("Qi session payload is malformed")
        if len(metadata_bytes) > _MAX_METADATA_BYTES:
            raise CassiFieldLanguageError("Qi session metadata exceeds the bounded limit")
        try:
            metadata = json.loads(metadata_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CassiFieldLanguageError(f"Qi session metadata is invalid: {error}") from error
        if not isinstance(metadata, dict):
            raise CassiFieldLanguageError("Qi session metadata must be an object")
        try:
            loaded = self.controller.load_state_bytes(
                state_bytes,
                device="cpu",
                dtype=torch.float32,
            )
        except QiFieldError as error:
            raise CassiFieldLanguageError(f"Qi session field is invalid: {error}") from error
        claimed = payload.get("state_sha256")
        actual = qi_state_sha256(self.controller, loaded)
        if claimed != actual:
            raise CassiFieldLanguageError("Qi session state hash mismatch")
        return loaded, metadata, path

    def save(
        self,
        session_id: str,
        state: QiFieldState,
        metadata: Mapping[str, Any],
    ) -> tuple[Path, str]:
        path = self.path_for(session_id)
        if not isinstance(metadata, Mapping):
            raise CassiFieldLanguageError("Qi session metadata must be an object")
        metadata_bytes = _canonical_json(dict(metadata))
        if len(metadata_bytes) > _MAX_METADATA_BYTES:
            raise CassiFieldLanguageError("Qi session metadata exceeds the bounded limit")
        try:
            state_bytes = self.controller.dump_state_bytes(state)
        except QiFieldError as error:
            raise CassiFieldLanguageError(f"failed to serialize Qi state: {error}") from error
        payload = {
            "codebook_fingerprint": self.controller.codebook_fingerprint,
            "config_fingerprint": self.controller.config_fingerprint,
            "engine_fingerprint": self.engine_fingerprint,
            "metadata": metadata_bytes,
            "schema": QI_SESSION_SCHEMA,
            "session_id": session_id,
            "state_bytes": state_bytes,
            "state_sha256": qi_state_sha256(self.controller, state),
        }
        serialized_path_hash = _atomic_torch_save(path, payload)
        return path, serialized_path_hash


def save_trajectory_checkpoint(
    path: Path,
    *,
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    corpus_identity: str,
    training_episode_count: int,
    training_event_count: int,
) -> str:
    if not isinstance(corpus_identity, str) or len(corpus_identity) != 64:
        raise CassiFieldLanguageError("corpus identity must be a SHA-256 digest")
    state.validate(law.config)
    payload = {
        "codebook_fingerprint": law.controller.codebook_fingerprint,
        "codec_fingerprint": law.codec.fingerprint,
        "config_fingerprint": law.controller.config_fingerprint,
        "corpus_identity": corpus_identity,
        "field": state.field.detach().to(device="cpu", dtype=torch.float32).contiguous(),
        "memory_sha256": law.memory_sha256(state),
        "schema": QI_TRAJECTORY_CHECKPOINT_SCHEMA,
        "training_episode_count": int(training_episode_count),
        "training_event_count": int(training_event_count),
        "trajectory_fingerprint": law.fingerprint,
    }
    return _atomic_torch_save(Path(path), payload)


def generate_text(
    controller: QiFieldController,
    state: QiFieldState,
    messages: Sequence[Mapping[str, Any]],
    *,
    checkpoint_path: Path,
    max_output_symbols: int = 96,
) -> CassiQiTextResult:
    return CassiQiTextEngine(
        controller,
        checkpoint_path=checkpoint_path,
        max_output_symbols=max_output_symbols,
    ).generate(state, messages)


__all__ = [
    "CassiFieldLanguageError",
    "CassiFieldTextCodec",
    "CassiQiEmissionReceipt",
    "CassiQiOutputStepReceipt",
    "CassiQiSessionStore",
    "CassiQiTextEngine",
    "CassiQiTextResult",
    "CassiQiTextStepReceipt",
    "CassiQiTrajectoryLaw",
    "FIELD_ALPHABET_SIZE",
    "FIELD_BYTE_SYMBOLS",
    "FIELD_TEXT_CODEC_SCHEMA",
    "FIELD_LIVE_REGISTER_SIZE",
    "QI_EMISSION_SCHEMA",
    "QI_OUTPUT_STEP_SCHEMA",
    "QI_SESSION_SCHEMA",
    "QI_TEXT_ENGINE_SCHEMA",
    "QI_TEXT_RESULT_SCHEMA",
    "QI_TEXT_STEP_SCHEMA",
    "QI_TRAJECTORY_CHECKPOINT_SCHEMA",
    "generate_text",
    "qi_state_sha256",
    "save_trajectory_checkpoint",
]
