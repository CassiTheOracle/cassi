"""Field-resident trajectory learning over the phi harmonic attractor."""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import torch
from torch import Tensor

from cassi_text_codec import CassiFieldTextCodec
from cassi_phi_harmonic_attractor_field import (
    PHI_HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID,
    PHI_HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID,
    PhiHarmonicAttractorFieldConfig,
    PhiHarmonicAttractorFieldController,
)
from cassi_qi_field import QiFieldError, QiFieldState

PHI_HARMONIC_LANGUAGE_LAYOUT_PROFILE_ID = "cassi.qi-phi-harmonic-tape.v1"
PHI_HARMONIC_LANGUAGE_OPERATOR_PROFILE_ID = "cassi.qi-phi-harmonic-language.v1"
PHI_HARMONIC_LANGUAGE_PROJECTION_PROFILE_ID = (
    PHI_HARMONIC_ATTRACTOR_PROJECTION_PROFILE_ID
)
TRAJECTORY_TAPE_PLANES = (2, 3)
PHI_HARMONIC_LANGUAGE_STATE_SCHEMA = "cassi.qi-phi-harmonic-language-state.v2"
PHI_HARMONIC_TEXT_ENGINE_SCHEMA = "cassi.qi-phi-harmonic-text-engine.v2"
PHI_HARMONIC_TEXT_RECEIPT_SCHEMA = "cassi.qi-phi-harmonic-text-receipt.v1"
_REQUIRED_POOL_COUNT = 7
_STATE_FRAME_MAGIC = b"CASSI-PHI-HARMONIC-STATE\x00\x02"
_STATE_FRAME_HEADER_BYTES = len(_STATE_FRAME_MAGIC) + 8 + hashlib.sha256().digest_size


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tensor_sha256(value: Tensor) -> str:
    owned = value.detach().cpu().contiguous()
    identity = json.dumps(
        {
            "dtype": str(owned.dtype),
            "shape": list(owned.shape),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    digest = hashlib.sha256(identity)
    digest.update(b"\x00")
    digest.update(owned.numpy().tobytes(order="C"))
    return digest.hexdigest()

@dataclass(frozen=True)
class PhiHarmonicLanguageConfig(PhiHarmonicAttractorFieldConfig):
    """Phi field geometry whose inactive differential planes hold a trajectory."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.bank_count != _REQUIRED_POOL_COUNT:
            raise QiFieldError(
                f"phi harmonic language requires {_REQUIRED_POOL_COUNT} pools"
            )

    @property
    def trajectory_capacity(self) -> int:
        return self.bank_count * self.wave_mode_count


    def fingerprint_with(self, codebook_fingerprint: str) -> str:
        encoded = json.dumps(
            {
                "base_layout_profile_id": PHI_HARMONIC_ATTRACTOR_LAYOUT_PROFILE_ID,
                "bank_timescales": self.bank_timescales,
                "config": self.to_dict(),
                "layout_profile_id": PHI_HARMONIC_LANGUAGE_LAYOUT_PROFILE_ID,
                "operator_profile_id": PHI_HARMONIC_LANGUAGE_OPERATOR_PROFILE_ID,
                "projection_profile_id": PHI_HARMONIC_LANGUAGE_PROJECTION_PROFILE_ID,
                "shared_codebook_fingerprint": codebook_fingerprint,
                "text_codec_fingerprint": CassiFieldTextCodec().fingerprint,
                "trajectory_tape": {
                    "complex_planes": TRAJECTORY_TAPE_PLANES,
                    "harmonic_lanes": self.bank_count,
                    "capacity": self.trajectory_capacity,
                    "occupancy_floor_rule": {
                        "configured_minimum": self.readout_energy_floor,
                        "floating_point_epsilon_multiplier": (
                            self.bank_count * self.bank_count
                        ),
                    },
                    "matching_rule": {
                        "episode_start_symbol": CassiFieldTextCodec().user_symbol,
                        "precedence": "latest-exact-context",
                    },
                    "symbol_signature": {
                        "amplitude_offset": 1,
                        "amplitude_scale_denominator": self.alphabet_size,
                        "phase": "shared-codebook-at-physical-mode",
                    },
                    "region": "upper-half",
                },
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class PhiHarmonicLanguageController(PhiHarmonicAttractorFieldController):
    """Learn and score codec transitions entirely inside the field tensor."""

    def __init__(self, config: PhiHarmonicLanguageConfig) -> None:
        if not isinstance(config, PhiHarmonicLanguageConfig):
            raise QiFieldError("config must be a PhiHarmonicLanguageConfig")
        super().__init__(config)
        self.config: PhiHarmonicLanguageConfig = config
        self.codec = CassiFieldTextCodec()

    def _symbol_amplitudes(self, state: QiFieldState) -> Tensor:
        constants = self._constants(state)
        cached = constants.get("language_symbol_amplitudes")
        if cached is None:
            cached = 1.0 + torch.arange(
                self.config.alphabet_size,
                device=state.field.device,
                dtype=state.field.dtype,
            ) / float(self.config.alphabet_size)
            constants["language_symbol_amplitudes"] = cached
        return cached

    def _packed(self, state: QiFieldState) -> Tensor:
        return state.field.reshape(
            self.config.bank_count,
            9,
            self.config.mode_count,
            state.batch_size,
        )

    def _require_single_state(self, state: QiFieldState) -> None:
        if state.batch_size != 1:
            raise QiFieldError("phi harmonic language requires batch_size=1")

    def _validate_state(self, state: QiFieldState) -> None:
        if not isinstance(state, QiFieldState) or not torch.is_tensor(state.field):
            raise QiFieldError("state must be a QiFieldState")
        if state.field.layout != torch.strided:
            raise QiFieldError("field must use dense strided layout")
        expected = (self.config.bank_count, 9 * self.config.mode_count)
        if (
            state.field.ndim != 3
            or tuple(state.field.shape[:2]) != expected
            or state.field.shape[2] < 1
        ):
            raise QiFieldError(
                f"field must have shape [{self.config.bank_count}, "
                f"9 * {self.config.mode_count}, B] with B >= 1"
            )
        if state.field.dtype not in (torch.float32, torch.float64):
            raise QiFieldError("prismatic field requires torch.float32 or torch.float64")
        if not bool(torch.isfinite(state.field).all().item()):
            raise QiFieldError("field contains non-finite values")

        width = self.config.wave_mode_count
        inactive = self._packed(state)[:, :, width:]
        tape = inactive[:, 2:4, :]
        forbidden_count = torch.count_nonzero(inactive) - torch.count_nonzero(tape)
        if bool((forbidden_count != 0).item()):
            raise QiFieldError(
                "only trajectory tape planes 2/3 may occupy inactive modes"
            )
        tape_amplitude = torch.complex(tape[:, 0], tape[:, 1]).abs()
        if bool((tape_amplitude > self.config.max_mode_amplitude).any().item()):
            raise QiFieldError("trajectory tape exceeds max_mode_amplitude")

    def state_sha256(self, state: QiFieldState) -> str:
        self._validate_state(state)
        self._require_single_state(state)
        return _tensor_sha256(state.field)

    def tape_sha256(self, state: QiFieldState) -> str:
        self._validate_state(state)
        self._require_single_state(state)
        width = self.config.wave_mode_count
        return _tensor_sha256(self._packed(state)[:, 2:4, width:])

    def dump_state_bytes(self, state: QiFieldState) -> bytes:
        """Serialize the sole adaptive tensor in an exact-length frame."""

        state_sha256 = self.state_sha256(state)
        payload = {
            "schema": PHI_HARMONIC_LANGUAGE_STATE_SCHEMA,
            "config_fingerprint": self.config_fingerprint,
            "codebook_fingerprint": self.codebook_fingerprint,
            "codec_fingerprint": self.codec.fingerprint,
            "state_sha256": state_sha256,
            "field": state.field.detach().cpu().contiguous(),
        }
        buffer = io.BytesIO()
        torch.save(payload, buffer)
        archive = buffer.getvalue()
        return (
            _STATE_FRAME_MAGIC
            + len(archive).to_bytes(8, "big")
            + hashlib.sha256(archive).digest()
            + archive
        )

    def load_state_bytes(
        self,
        payload: bytes | bytearray | memoryview,
        *,
        device: torch.device | str = "cpu",
        dtype: torch.dtype | None = None,
    ) -> QiFieldState:
        """Load one exactly framed language tensor belonging to this controller."""

        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise QiFieldError("language state payload must be bytes")
        framed = bytes(payload)
        maximum_archive_bytes = (
            self.config.bank_count * 9 * self.config.mode_count * 8
            + 1024 * 1024
        )
        if (
            len(framed) < _STATE_FRAME_HEADER_BYTES
            or not framed.startswith(_STATE_FRAME_MAGIC)
        ):
            raise QiFieldError("language state frame is invalid")
        offset = len(_STATE_FRAME_MAGIC)
        archive_length = int.from_bytes(framed[offset : offset + 8], "big")
        digest_offset = offset + 8
        archive_offset = digest_offset + hashlib.sha256().digest_size
        if (
            archive_length < 1
            or archive_length > maximum_archive_bytes
            or len(framed) != archive_offset + archive_length
        ):
            raise QiFieldError("language state frame length is invalid")
        expected_digest = framed[digest_offset:archive_offset]
        serialized = framed[archive_offset:]
        if hashlib.sha256(serialized).digest() != expected_digest:
            raise QiFieldError("language state frame checksum mismatch")
        try:
            target_device = torch.device(device)
            loaded = torch.load(
                io.BytesIO(serialized),
                map_location=target_device,
                weights_only=True,
            )
        except Exception as error:
            raise QiFieldError(
                f"language state payload cannot be loaded: {type(error).__name__}"
            ) from error
        expected_keys = {
            "schema",
            "config_fingerprint",
            "codebook_fingerprint",
            "codec_fingerprint",
            "state_sha256",
            "field",
        }
        if not isinstance(loaded, dict) or set(loaded) != expected_keys:
            raise QiFieldError("language state payload has an unexpected key set")
        expected_identity = {
            "schema": PHI_HARMONIC_LANGUAGE_STATE_SCHEMA,
            "config_fingerprint": self.config_fingerprint,
            "codebook_fingerprint": self.codebook_fingerprint,
            "codec_fingerprint": self.codec.fingerprint,
        }
        if any(loaded.get(key) != value for key, value in expected_identity.items()):
            raise QiFieldError("language state payload identity mismatch")
        field = loaded.get("field")
        if not torch.is_tensor(field):
            raise QiFieldError("language state tensor is missing")
        candidate = QiFieldState(field)
        try:
            self._validate_state(candidate)
            self._require_single_state(candidate)
            actual_sha256 = _tensor_sha256(field)
        except QiFieldError:
            raise
        except Exception as error:
            raise QiFieldError(
                f"language state tensor is invalid: {type(error).__name__}"
            ) from error
        if actual_sha256 != loaded.get("state_sha256"):
            raise QiFieldError("language state tensor checksum mismatch")
        self.learned_exchanges(candidate)
        target_dtype = field.dtype if dtype is None else dtype
        try:
            result = QiFieldState(
                field.detach().to(device=target_device, dtype=target_dtype).clone()
            )
            self._validate_state(result)
            self._require_single_state(result)
        except QiFieldError:
            raise
        except Exception as error:
            raise QiFieldError(
                f"language state tensor conversion failed: {type(error).__name__}"
            ) from error
        return result


    def _restore_tape(
        self, source: QiFieldState, target: QiFieldState
    ) -> QiFieldState:
        width = self.config.wave_mode_count
        self._packed(target)[:, 2:4, width:].copy_(
            self._packed(source)[:, 2:4, width:]
        )
        return target

    def _replace_coordinates(
        self,
        state: QiFieldState,
        common: Tensor,
        differential: Tensor,
        common_velocity: Tensor,
        differential_velocity: Tensor,
        *,
        epsilon: Tensor | None = None,
    ) -> QiFieldState:
        result = super()._replace_coordinates(
            state,
            common,
            differential,
            common_velocity,
            differential_velocity,
            epsilon=epsilon,
        )
        return self._restore_tape(state, result)

    def _bound(self, state: QiFieldState) -> tuple[QiFieldState, int]:
        result, clamp_count = super()._bound(state)
        return self._restore_tape(state, result), clamp_count

    def _evolve_unchecked(
        self, state: QiFieldState, steps: int
    ) -> tuple[QiFieldState, int]:
        result, clamp_count = super()._evolve_unchecked(state, steps)
        return self._restore_tape(state, result), clamp_count

    def _exchange_events(
        self, prompt: bytes, continuation: bytes
    ) -> tuple[int, ...]:
        if not isinstance(prompt, bytes) or not isinstance(continuation, bytes):
            raise QiFieldError("trajectory learning requires byte prompt/continuation")
        return self.codec.encode_training_exchange(prompt, continuation)

    def _trajectory_length(self, occupied: Tensor) -> int:
        length = int(torch.count_nonzero(occupied[0]).item())
        if (
            not bool(occupied[0, :length].all().item())
            or bool(occupied[0, length:].any().item())
        ):
            raise QiFieldError("trajectory tape must be contiguous")
        return length

    def _write_events(
        self,
        state: QiFieldState,
        events: tuple[int, ...],
        *,
        append: bool,
    ) -> QiFieldState:
        self._validate_state(state)
        self._require_single_state(state)
        if not events:
            raise QiFieldError("trajectory learning requires events")

        width = self.config.wave_mode_count
        packed = self._packed(state).clone()
        if append:
            _, occupied = self._tape_scores(state)
            offset = self._trajectory_length(occupied)
            tape = torch.complex(packed[:, 2, width:], packed[:, 3, width:])
        else:
            offset = 0
            codebook_parts = self.codebook(
                0, device=state.field.device, dtype=state.field.dtype
            )
            tape = torch.zeros(
                (self.config.bank_count, width, state.batch_size),
                device=state.field.device,
                dtype=torch.complex(
                    codebook_parts[..., 0], codebook_parts[..., 1]
                ).dtype,
            )
        if offset + len(events) > self.config.trajectory_capacity:
            raise QiFieldError("training exchange exceeds trajectory tape capacity")

        positions = torch.arange(
            offset,
            offset + len(events),
            device=state.field.device,
            dtype=torch.int64,
        )
        modes = torch.div(positions, self.config.bank_count, rounding_mode="floor")
        lanes = torch.remainder(positions, self.config.bank_count)
        symbol_ids = torch.tensor(
            events, device=state.field.device, dtype=torch.int64
        )
        codebook_parts = self.codebook(
            0, device=state.field.device, dtype=state.field.dtype
        )
        codebook = torch.complex(codebook_parts[..., 0], codebook_parts[..., 1])
        event_signature = (
            codebook[symbol_ids, modes]
            * self._symbol_amplitudes(state).index_select(0, symbol_ids)
        )
        harmonic_inverse = self._constants(state)["harmonic_inverse"]
        encoded_events = (
            harmonic_inverse.index_select(1, lanes) * event_signature[None, :]
        )
        lane_offset = offset % self.config.bank_count
        for lane in range(self.config.bank_count):
            event_offset = (
                lane - lane_offset
            ) % self.config.bank_count
            if event_offset >= len(events):
                continue
            start_mode = (
                offset + event_offset
            ) // self.config.bank_count
            lane_events = encoded_events[
                :, event_offset :: self.config.bank_count, None
            ]
            tape[
                :, start_mode : start_mode + lane_events.shape[1], :
            ].add_(lane_events)

        packed[:, 2, width:] = tape.real
        packed[:, 3, width:] = tape.imag
        result = QiFieldState(
            packed.reshape(
                self.config.bank_count,
                9 * self.config.mode_count,
                state.batch_size,
            ).contiguous()
        )
        self._validate_state(result)
        return result

    def learn_exchange(
        self, state: QiFieldState, prompt: bytes, continuation: bytes
    ) -> QiFieldState:
        """Replace the tape with one codec exchange."""

        return self._write_events(
            state, self._exchange_events(prompt, continuation), append=False
        )

    def _exchanges_events(
        self, exchanges: Sequence[tuple[bytes, bytes]]
    ) -> tuple[int, ...]:
        if isinstance(exchanges, (str, bytes, bytearray)) or not exchanges:
            raise QiFieldError("trajectory learning requires exchanges")
        events: list[int] = []
        for exchange in exchanges:
            if not isinstance(exchange, Sequence) or len(exchange) != 2:
                raise QiFieldError("each training exchange requires prompt/continuation")
            events.extend(self._exchange_events(exchange[0], exchange[1]))
        return tuple(events)

    def learn_exchanges(
        self,
        state: QiFieldState,
        exchanges: Sequence[tuple[bytes, bytes]],
    ) -> QiFieldState:
        """Replace the tape with a sequence of codec exchanges."""

        return self._write_events(
            state, self._exchanges_events(exchanges), append=False
        )

    def append_exchange(
        self, state: QiFieldState, prompt: bytes, continuation: bytes
    ) -> QiFieldState:
        """Append one exchange so its exact contexts take precedence."""

        return self._write_events(
            state, self._exchange_events(prompt, continuation), append=True
        )

    def append_exchanges(
        self,
        state: QiFieldState,
        exchanges: Sequence[tuple[bytes, bytes]],
    ) -> QiFieldState:
        """Append exchanges in one field write while preserving their order."""

        return self._write_events(
            state, self._exchanges_events(exchanges), append=True
        )

    def rebuild_exchanges(
        self,
        state: QiFieldState,
        base_state: QiFieldState,
        exchanges: Sequence[tuple[bytes, bytes]],
    ) -> QiFieldState:
        """Replace dynamic exchanges while preserving the base tape and live field."""

        self._validate_state(state)
        self._require_single_state(state)
        self._validate_state(base_state)
        self._require_single_state(base_state)
        if (
            state.field.device != base_state.field.device
            or state.field.dtype != base_state.field.dtype
        ):
            raise QiFieldError("base and live language states must share device/dtype")
        result = self._restore_tape(
            base_state,
            QiFieldState(state.field.detach().clone()),
        )
        if not exchanges:
            return result
        return self.append_exchanges(result, exchanges)

    def _tape_scores(self, state: QiFieldState) -> tuple[Tensor, Tensor]:
        width = self.config.wave_mode_count
        packed = self._packed(state)
        tape = torch.complex(packed[:, 2, width:], packed[:, 3, width:])
        harmonic_forward = self._constants(state)["harmonic_forward"]
        decoded = torch.einsum("lc,cmb->mlb", harmonic_forward, tape).reshape(
            self.config.trajectory_capacity, state.batch_size
        )
        amplitude = decoded.abs()
        occupancy_floor = max(
            self.config.readout_energy_floor,
            torch.finfo(state.field.dtype).eps
            * self.config.bank_count
            * self.config.bank_count,
        )
        occupied = amplitude.transpose(0, 1) >= occupancy_floor

        codebook_parts = self.codebook(
            0, device=state.field.device, dtype=state.field.dtype
        )
        codebook = torch.complex(codebook_parts[..., 0], codebook_parts[..., 1])
        codebook_by_position = codebook.transpose(0, 1).repeat_interleave(
            self.config.bank_count, dim=0
        )
        prototypes = (
            codebook_by_position
            * self._symbol_amplitudes(state)[None, :]
        )
        scores = -(
            decoded.transpose(0, 1)[:, :, None]
            - prototypes[None, :, :]
        ).abs().square()
        return scores, occupied

    def learned_events(self, state: QiFieldState) -> tuple[int, ...]:
        """Decode the occupied trajectory tape without retaining a side copy."""

        self._validate_state(state)
        self._require_single_state(state)
        scores, occupied = self._tape_scores(state)
        length = self._trajectory_length(occupied)
        return tuple(scores[0, :length].argmax(dim=1).tolist())

    def learned_exchanges(
        self, state: QiFieldState
    ) -> tuple[tuple[bytes, bytes], ...]:
        """Decode canonical exchanges directly from the field tape."""

        events = self.learned_events(state)
        exchanges: list[tuple[bytes, bytes]] = []
        cursor = 0
        while cursor < len(events):
            if events[cursor] != self.codec.user_symbol:
                raise QiFieldError("trajectory tape has a malformed exchange")
            try:
                prompt_end = events.index(self.codec.end_turn_symbol, cursor + 1)
                if (
                    prompt_end + 1 >= len(events)
                    or events[prompt_end + 1] != self.codec.assistant_symbol
                ):
                    raise QiFieldError("trajectory tape has a malformed exchange")
                continuation_end = events.index(
                    self.codec.end_turn_symbol, prompt_end + 2
                )
                prompt = bytes(events[cursor + 1 : prompt_end])
                continuation = bytes(events[prompt_end + 2 : continuation_end])
            except ValueError as error:
                raise QiFieldError("trajectory tape has a malformed exchange") from error
            if not prompt or not continuation:
                raise QiFieldError("trajectory tape has an empty exchange")
            exchanges.append((prompt, continuation))
            cursor = continuation_end + 1
        return tuple(exchanges)

    def _next_symbol_scores_batched(
        self,
        state: QiFieldState,
        tape_scores: Tensor | None = None,
        occupied: Tensor | None = None,
    ) -> tuple[Tensor, Tensor]:
        self._validate_state(state)
        if tape_scores is None or occupied is None:
            tape_scores, occupied = self._tape_scores(state)
            if not torch.equal(occupied, occupied[:1].expand_as(occupied)):
                raise QiFieldError("candidate branches must share one trajectory tape")
        tape_scores = tape_scores[:1]
        occupied = occupied[:1]
        length = self._trajectory_length(occupied)
        if length < 2:
            raise QiFieldError("trajectory tape must contain a learned exchange")

        tape_symbols = tape_scores.argmax(dim=2)
        live = self.white_readout(state)
        age_capacity = live.age_symbols.shape[1]
        if age_capacity < 1:
            raise QiFieldError("live field has no harmonic age capacity")

        indices = torch.arange(length, device=state.field.device, dtype=torch.int64)
        user_starts = torch.where(
            tape_symbols[0, :length] == self.codec.user_symbol,
            indices,
            torch.full_like(indices, -1),
        )
        episode_starts = torch.cummax(user_starts, dim=0).values
        positions = indices[1:]
        context_lengths = (
            positions - episode_starts.index_select(0, positions)
        ).clamp(min=0, max=age_capacity)
        offsets = torch.arange(
            age_capacity, device=state.field.device, dtype=torch.int64
        )
        history_indices = (
            positions[:, None] - 1 - offsets[None, :]
        ).clamp_min(0)
        history = tape_symbols[:, history_indices]
        valid = offsets[None, :] < context_lengths[:, None]
        history_matches = (
            ~valid[None, :, :]
            | (
                live.age_available[:, None, :age_capacity]
                & (history == live.age_symbols[:, None, :age_capacity])
            )
        ).all(dim=2)
        context_matches = (
            (context_lengths > 0)[None, :]
            & occupied.index_select(1, positions)
            & history_matches
        )
        latest = torch.where(
            context_matches,
            positions[None, :],
            torch.full_like(positions[None, :], -1),
        ).amax(dim=1)
        available = latest >= 0
        return tape_scores[0, latest.clamp_min(0)], available

    def next_symbol_scores(self, state: QiFieldState) -> Tensor:
        """Score the latest exact codec continuation from the field tape."""

        self._require_single_state(state)
        scores, available = self._next_symbol_scores_batched(state)
        if not bool(available[0].item()):
            raise QiFieldError("live field has no learned trajectory continuation")
        return scores

    def _sense_events(
        self, state: QiFieldState, events: tuple[int, ...]
    ) -> QiFieldState:
        self._validate_state(state)
        self._require_single_state(state)
        for event in events:
            state = self.tick(state, symbols=(event,), steps=8).state
        return state

    def sense_user_message(self, state: QiFieldState, content: str) -> QiFieldState:
        events = CassiFieldTextCodec().encode_messages(
            ({"role": "user", "content": content},)
        )
        return self._sense_events(state, events)

    def sense_symbol(self, state: QiFieldState, symbol: int) -> QiFieldState:
        return self._sense_events(state, (symbol,))

    def batch_candidate_sequence_work(
        self,
        state: QiFieldState,
        prompt: bytes,
        continuations: Sequence[bytes],
    ) -> Tensor:
        """Probe independent candidate continuations without mutating the field."""

        self._validate_state(state)
        self._require_single_state(state)
        if not isinstance(prompt, bytes) or not prompt:
            raise QiFieldError("candidate work requires a nonempty byte prompt")
        if isinstance(continuations, (str, bytes, bytearray)):
            raise QiFieldError("candidate continuations must be a sequence")
        if not continuations:
            return torch.empty(
                0, device=state.field.device, dtype=state.field.dtype
            )
        sequences: list[tuple[int, ...]] = []
        for continuation in continuations:
            if not isinstance(continuation, bytes) or not continuation:
                raise QiFieldError("candidate continuations must be nonempty bytes")
            sequences.append(
                (
                    self.codec.assistant_symbol,
                    *continuation,
                    self.codec.end_turn_symbol,
                )
            )
        prompted = self._sense_events(
            state,
            (self.codec.user_symbol, *prompt, self.codec.end_turn_symbol),
        )
        tape_scores, occupied = self._tape_scores(prompted)
        branches = QiFieldState(
            prompted.field.repeat(1, 1, len(sequences))
        )
        work = torch.zeros(
            len(sequences), device=state.field.device, dtype=state.field.dtype
        )
        max_length = max(len(sequence) for sequence in sequences)
        for position in range(max_length):
            active_values = [position < len(sequence) for sequence in sequences]
            symbol_values = [
                sequence[position] if active else 0
                for sequence, active in zip(sequences, active_values, strict=True)
            ]
            active = torch.tensor(
                active_values, device=state.field.device, dtype=torch.bool
            )
            symbols = torch.tensor(
                symbol_values, device=state.field.device, dtype=torch.long
            )
            scores, available = self._next_symbol_scores_batched(
                branches, tape_scores, occupied
            )
            chosen = scores.gather(1, symbols[:, None]).squeeze(1)
            best = scores.amax(dim=1)
            contribution = torch.exp(chosen - best)
            work += torch.where(active & available, contribution, 0.0)

            successor = self.tick(
                branches,
                symbols=tuple(symbol_values),
                steps=8,
            ).state
            branches = QiFieldState(
                torch.where(
                    active[None, None, :],
                    successor.field,
                    branches.field,
                )
            )

        lengths = torch.tensor(
            [len(sequence) for sequence in sequences],
            device=state.field.device,
            dtype=state.field.dtype,
        )
        return work / lengths

    def _generate_sensed_reply(
        self,
        state: QiFieldState,
        *,
        max_output_symbols: int,
    ) -> tuple[QiFieldState, str, tuple[int, ...], str]:
        if (
            isinstance(max_output_symbols, bool)
            or not isinstance(max_output_symbols, int)
            or max_output_symbols < 1
        ):
            raise QiFieldError("max_output_symbols must be a positive integer")
        working = state
        assistant = int(self.next_symbol_scores(working).argmax(dim=1).item())
        if assistant != self.codec.assistant_symbol:
            raise QiFieldError("learned continuation does not begin with assistant role")
        working = self.sense_symbol(working, assistant)

        output = bytearray()
        emitted: list[int] = []
        safe_state = working
        safe_length = 0
        for _ in range(max_output_symbols):
            scores = self.next_symbol_scores(working)
            mask = self.codec.output_mask(
                bytes(output), device=state.field.device
            )
            eligible = scores.masked_fill(~mask[None, :], -torch.inf)
            if not bool(torch.isfinite(eligible).any().item()):
                raise QiFieldError("learned continuation has no valid UTF-8 port")
            symbol = int(eligible.argmax(dim=1).item())
            working = self.sense_symbol(working, symbol)
            emitted.append(symbol)
            if symbol == self.codec.end_turn_symbol:
                return (
                    working,
                    self.codec.decode_symbols(tuple(output))[1],
                    tuple(emitted),
                    "end_turn",
                )
            output.append(symbol)
            try:
                bytes(output).decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                continue
            safe_state = working
            safe_length = len(output)
        safe_output = tuple(output[:safe_length])
        return (
            safe_state,
            self.codec.decode_symbols(safe_output)[1],
            safe_output,
            "max_output_symbols",
        )

    def generate_reply(
        self,
        state: QiFieldState,
        content: str,
        *,
        max_output_symbols: int = 256,
    ) -> tuple[QiFieldState, str]:
        """Sense one user message and emit its learned UTF-8 continuation."""

        working = self.sense_user_message(state, content)
        result, reply, _, _ = self._generate_sensed_reply(
            working, max_output_symbols=max_output_symbols
        )
        return result, reply


@dataclass(frozen=True)
class PhiHarmonicTextResult:
    state: QiFieldState
    prompt_symbols: tuple[int, ...]
    output_symbols: tuple[int, ...]
    reply: str
    initial_state_sha256: str
    final_state_sha256: str
    tape_sha256: str
    engine_fingerprint: str
    stop_reason: str = "end_turn"

    def receipt_dict(self) -> dict[str, object]:
        return {
            "schema": PHI_HARMONIC_TEXT_RECEIPT_SCHEMA,
            "engine_fingerprint": self.engine_fingerprint,
            "initial_state_sha256": self.initial_state_sha256,
            "final_state_sha256": self.final_state_sha256,
            "tape_sha256": self.tape_sha256,
            "prompt_symbols": list(self.prompt_symbols),
            "output_symbols": list(self.output_symbols),
            "reply_sha256": hashlib.sha256(self.reply.encode("utf-8")).hexdigest(),
            "stop_reason": self.stop_reason,
        }

    @property
    def receipt_sha256(self) -> str:
        return _canonical_sha256(self.receipt_dict())

    def render_text(self) -> tuple[str, str]:
        return self.reply, "field"


class PhiHarmonicTextEngine:
    """Deterministic prompt-to-END_TURN surface over one native field tensor."""

    def __init__(
        self,
        controller: PhiHarmonicLanguageController,
        *,
        max_output_symbols: int = 512,
    ) -> None:
        if not isinstance(controller, PhiHarmonicLanguageController):
            raise QiFieldError(
                "controller must be a PhiHarmonicLanguageController"
            )
        if (
            isinstance(max_output_symbols, bool)
            or not isinstance(max_output_symbols, int)
            or not 1 <= max_output_symbols <= 4096
        ):
            raise QiFieldError("max_output_symbols must lie in [1, 4096]")
        self.controller = controller
        self.codec = controller.codec
        self.max_output_symbols = max_output_symbols
        self.fingerprint = _canonical_sha256(
            {
                "schema": PHI_HARMONIC_TEXT_ENGINE_SCHEMA,
                "state_schema": PHI_HARMONIC_LANGUAGE_STATE_SCHEMA,
                "receipt_schema": PHI_HARMONIC_TEXT_RECEIPT_SCHEMA,
                "config_fingerprint": controller.config_fingerprint,
                "codebook_fingerprint": controller.codebook_fingerprint,
                "codec_fingerprint": self.codec.fingerprint,
                "max_output_symbols": max_output_symbols,
            }
        )

    def state_sha256(self, state: QiFieldState) -> str:
        return self.controller.state_sha256(state)

    def generate(
        self,
        state: QiFieldState,
        messages: Sequence[Mapping[str, object]],
        *,
        max_output_symbols: int | None = None,
    ) -> PhiHarmonicTextResult:
        if (
            isinstance(messages, (str, bytes, bytearray))
            or not isinstance(messages, Sequence)
            or not messages
        ):
            raise QiFieldError("messages must be a nonempty sequence")
        for index, message in enumerate(messages):
            if not isinstance(message, Mapping):
                raise QiFieldError(f"message {index} must be an object")
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "user", "assistant"} or not isinstance(
                content, str
            ):
                raise QiFieldError(f"message {index} has invalid role/content")
        if messages[-1].get("role") != "user":
            raise QiFieldError("final message must have role user")
        limit = self.max_output_symbols if max_output_symbols is None else max_output_symbols
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= self.max_output_symbols
        ):
            raise QiFieldError("max_output_symbols exceeds engine limit")

        initial_state_sha256 = self.controller.state_sha256(state)
        tape_sha256 = self.controller.tape_sha256(state)
        prompt_symbols = self.codec.encode_messages(messages)
        sensed = self.controller._sense_events(state, prompt_symbols)
        successor, reply, output_symbols, stop_reason = (
            self.controller._generate_sensed_reply(
                sensed, max_output_symbols=limit
            )
        )
        if self.controller.state_sha256(state) != initial_state_sha256:
            raise QiFieldError("generation mutated its input field state")
        if self.controller.tape_sha256(successor) != tape_sha256:
            raise QiFieldError("generation changed the learned trajectory tape")
        return PhiHarmonicTextResult(
            state=successor,
            prompt_symbols=prompt_symbols,
            output_symbols=output_symbols,
            reply=reply,
            initial_state_sha256=initial_state_sha256,
            final_state_sha256=self.controller.state_sha256(successor),
            tape_sha256=tape_sha256,
            engine_fingerprint=self.fingerprint,
            stop_reason=stop_reason,
        )


__all__ = [
    "PHI_HARMONIC_LANGUAGE_LAYOUT_PROFILE_ID",
    "PHI_HARMONIC_LANGUAGE_OPERATOR_PROFILE_ID",
    "PHI_HARMONIC_LANGUAGE_PROJECTION_PROFILE_ID",
    "PHI_HARMONIC_LANGUAGE_STATE_SCHEMA",
    "PHI_HARMONIC_TEXT_ENGINE_SCHEMA",
    "PHI_HARMONIC_TEXT_RECEIPT_SCHEMA",
    "TRAJECTORY_TAPE_PLANES",
    "PhiHarmonicLanguageConfig",
    "PhiHarmonicLanguageController",
    "PhiHarmonicTextEngine",
    "PhiHarmonicTextResult",
]
