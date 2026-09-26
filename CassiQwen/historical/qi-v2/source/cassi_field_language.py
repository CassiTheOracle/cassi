"""Cassi-native text boundary over the canonical multi-scale Qi field.

The only adaptive persistent object accepted or returned here is
:class:`cassi_qi_field.QiFieldState`.  UTF-8 framing is fixed protocol code;
sensing, evolution, emission, and consolidation all delegate to
:class:`cassi_qi_field.QiFieldController`.  There are no learned tensors,
neural layers, engineered feature vectors, losses, optimizers, or stochastic
sampling paths in this module.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

import torch
from torch import Tensor

from cassi_qi_field import QiFieldController, QiFieldError, QiFieldReadout, QiFieldState


class CassiFieldLanguageError(RuntimeError):
    """A fixed text boundary or Qi transition failed closed."""


FIELD_TEXT_CODEC_SCHEMA: Final[str] = "cassi.field-text-codec.v1"
QI_TEXT_STEP_SCHEMA: Final[str] = "cassi.qi-text-step.v1"
QI_EMISSION_SCHEMA: Final[str] = "cassi.qi-emission.v1"
QI_OUTPUT_STEP_SCHEMA: Final[str] = "cassi.qi-output-step.v1"
QI_TEXT_RESULT_SCHEMA: Final[str] = "cassi.qi-text-result.v1"
QI_SESSION_SCHEMA: Final[str] = "cassi.qi-session.v1"
QI_TEXT_ENGINE_SCHEMA: Final[str] = "cassi.qi-text-engine.v1"

_BYTE_SYMBOL_COUNT: Final[int] = 256
_ROLE_SYMBOLS: Final[dict[str, int]] = {
    "user": 256,
    "system": 257,
    "assistant": 258,
}
_END_TURN_SYMBOL: Final[int] = 259
_ALPHABET_SIZE: Final[int] = 260
_ALLOWED_ROLES: Final[frozenset[str]] = frozenset(_ROLE_SYMBOLS)
_MAX_MESSAGES: Final[int] = 128
_MAX_MESSAGE_BYTES: Final[int] = 1 << 20
_MAX_SESSION_ID_BYTES: Final[int] = 1024
_MAX_METADATA_BYTES: Final[int] = 4 << 20


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CassiFieldLanguageError(f"receipt is not canonical JSON: {error}") from error


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _tensor_sha256(value: Tensor) -> str:
    if not torch.is_tensor(value):
        raise CassiFieldLanguageError("receipt tensor is invalid")
    finite = value.detach().to(device="cpu").contiguous()
    if not bool(torch.isfinite(finite).all().item()):
        raise CassiFieldLanguageError("receipt tensor contains non-finite values")
    payload = finite.view(torch.uint8).numpy().tobytes()
    identity = json.dumps(
        {"dtype": str(finite.dtype), "shape": list(finite.shape)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(identity + b"\x00" + payload).hexdigest()


def qi_state_sha256(
    controller: QiFieldController,
    state: QiFieldState,
) -> str:
    """Hash one validated Qi tensor and its immutable field identity."""

    if not isinstance(controller, QiFieldController):
        raise CassiFieldLanguageError("Qi controller is required")
    if not isinstance(state, QiFieldState):
        raise CassiFieldLanguageError("Qi state is required")
    try:
        state.validate(controller.config)
    except QiFieldError as error:
        raise CassiFieldLanguageError(f"invalid Qi state: {error}") from error
    if state.field.requires_grad:
        raise CassiFieldLanguageError("live Qi state must not carry an autograd graph")
    field = state.field.detach().to(device="cpu").contiguous()
    identity = {
        "codebook_fingerprint": controller.codebook_fingerprint,
        "config_fingerprint": controller.config_fingerprint,
        "dtype": str(field.dtype),
        "shape": list(field.shape),
    }
    return hashlib.sha256(
        _canonical_json(identity) + b"\x00" + field.view(torch.uint8).numpy().tobytes()
    ).hexdigest()


def _column(values: Tensor) -> tuple[float, ...]:
    finite = values.detach().to(device="cpu", dtype=torch.float64).contiguous()
    if finite.ndim != 2 or finite.shape[1] != 1:
        raise CassiFieldLanguageError("Qi diagnostic must have shape [S, 1]")
    if not bool(torch.isfinite(finite).all().item()):
        raise CassiFieldLanguageError("Qi diagnostic contains non-finite values")
    return tuple(float(item) for item in finite[:, 0].tolist())

def _values(values: Tensor) -> tuple[float, ...]:
    finite = values.detach().to(device="cpu", dtype=torch.float64).contiguous()
    if finite.ndim not in {1, 2} or finite.numel() < 1:
        raise CassiFieldLanguageError("Qi diagnostic must be a nonempty vector or column")
    if finite.ndim == 2 and finite.shape[1] != 1:
        raise CassiFieldLanguageError("Qi diagnostic matrix must have one batch column")
    if not bool(torch.isfinite(finite).all().item()):
        raise CassiFieldLanguageError("Qi diagnostic contains non-finite values")
    return tuple(float(item) for item in finite.reshape(-1).tolist())



def _finite_float(name: str, value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise CassiFieldLanguageError(f"{name} must be finite")
    return result


def _bounded_int(name: str, value: int, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise CassiFieldLanguageError(f"{name} must lie in [{minimum}, {maximum}]")
    return value


@dataclass(frozen=True)
class CassiFieldTextCodec:
    """Frozen 256-byte plus role-control alphabet for Qi-native chat text."""

    schema: str = FIELD_TEXT_CODEC_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != FIELD_TEXT_CODEC_SCHEMA:
            raise CassiFieldLanguageError("field text codec schema mismatch")

    @property
    def alphabet_size(self) -> int:
        return _ALPHABET_SIZE

    @property
    def end_turn_symbol(self) -> int:
        return _END_TURN_SYMBOL

    @property
    def assistant_symbol(self) -> int:
        return _ROLE_SYMBOLS["assistant"]

    @property
    def fingerprint(self) -> str:
        return _digest(
            {
                "alphabet_size": self.alphabet_size,
                "byte_symbols": _BYTE_SYMBOL_COUNT,
                "end_turn_symbol": self.end_turn_symbol,
                "role_symbols": dict(sorted(_ROLE_SYMBOLS.items())),
                "schema": self.schema,
            }
        )

    def role_symbol(self, role: str) -> int:
        if role not in _ROLE_SYMBOLS:
            raise CassiFieldLanguageError(f"unsupported message role: {role!r}")
        return _ROLE_SYMBOLS[role]

    def encode_messages(
        self,
        messages: Sequence[Mapping[str, object]],
    ) -> tuple[int, ...]:
        if isinstance(messages, (str, bytes, bytearray)) or not isinstance(messages, Sequence):
            raise CassiFieldLanguageError("messages must be a sequence")
        if not 1 <= len(messages) <= _MAX_MESSAGES:
            raise CassiFieldLanguageError(f"message count must lie in [1, {_MAX_MESSAGES}]")
        encoded: list[int] = []
        total_bytes = 0
        for index, message in enumerate(messages):
            if not isinstance(message, Mapping):
                raise CassiFieldLanguageError(f"message {index} must be an object")
            role = message.get("role")
            content = message.get("content")
            if not isinstance(role, str) or role not in _ALLOWED_ROLES:
                raise CassiFieldLanguageError(f"message {index} has an unsupported role")
            if not isinstance(content, str):
                raise CassiFieldLanguageError(f"message {index} content must be text")
            raw = content.encode("utf-8", "strict")
            total_bytes += len(raw)
            if total_bytes > _MAX_MESSAGE_BYTES:
                raise CassiFieldLanguageError("encoded message bytes exceed the bounded limit")
            encoded.append(self.role_symbol(role))
            encoded.extend(raw)
            encoded.append(self.end_turn_symbol)
        return tuple(encoded)



def _replacement_count(raw: bytes) -> int:
    offset = 0
    count = 0
    while offset < len(raw):
        try:
            raw[offset:].decode("utf-8", "strict")
            break
        except UnicodeDecodeError as error:
            count += 1
            advance = error.end if error.end > error.start else error.start + 1
            offset += advance
    return count


def _decode_output_bytes(raw: bytes) -> tuple[str, bool, int]:
    try:
        return raw.decode("utf-8", "strict"), True, 0
    except UnicodeDecodeError:
        return raw.decode("utf-8", "replace"), False, _replacement_count(raw)


@dataclass(frozen=True)
class CassiQiTextStepReceipt:
    """One immutable sense/evolve/consolidate transition."""

    phase: str
    position: int
    symbol: int
    state_before_sha256: str
    sensed_state_sha256: str
    state_after_sha256: str
    q: tuple[float, ...]
    chi: tuple[float, ...]
    read_gate: tuple[float, ...]
    write_gate: tuple[float, ...]
    consolidation_gate: tuple[float, ...]
    schema: str = QI_TEXT_STEP_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != QI_TEXT_STEP_SCHEMA:
            raise CassiFieldLanguageError("Qi text step schema mismatch")
        if self.phase not in {"prompt", "output"}:
            raise CassiFieldLanguageError("Qi text step phase is invalid")
        _bounded_int("position", self.position, minimum=0, maximum=(1 << 31) - 1)
        _bounded_int("symbol", self.symbol, minimum=0, maximum=_ALPHABET_SIZE - 1)
        for name in ("state_before_sha256", "sensed_state_sha256", "state_after_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise CassiFieldLanguageError(f"{name} must be a SHA-256 hex digest")
        scale_widths = {len(self.q), len(self.chi), len(self.read_gate), len(self.write_gate)}
        if len(scale_widths) != 1 or not self.q:
            raise CassiFieldLanguageError("Qi per-scale diagnostic widths do not match")
        if len(self.consolidation_gate) != max(0, len(self.q) - 1):
            raise CassiFieldLanguageError("Qi consolidation gate width is invalid")
        for values in (self.q, self.chi, self.read_gate, self.write_gate, self.consolidation_gate):
            if any(not math.isfinite(float(value)) for value in values):
                raise CassiFieldLanguageError("Qi step diagnostics must be finite")

    def receipt_dict(self) -> dict[str, Any]:
        return {
            "chi": list(self.chi),
            "consolidation_gate": list(self.consolidation_gate),
            "phase": self.phase,
            "position": self.position,
            "q": list(self.q),
            "read_gate": list(self.read_gate),
            "schema": self.schema,
            "sensed_state_sha256": self.sensed_state_sha256,
            "state_after_sha256": self.state_after_sha256,
            "state_before_sha256": self.state_before_sha256,
            "symbol": self.symbol,
            "write_gate": list(self.write_gate),
        }

    @property
    def receipt_sha256(self) -> str:
        return _digest(self.receipt_dict())


@dataclass(frozen=True)
class CassiQiEmissionReceipt:
    """One direct phase-conjugate resonance readout."""

    position: int
    state_sha256: str
    available: bool
    symbol: int
    scores_sha256: str
    wave_sha256: str
    flux: float
    margin: float
    uncertainty: float
    q: tuple[float, ...]
    q_max: tuple[float, ...]
    chi: tuple[float, ...]
    cross_scale_coherence: tuple[float, ...]
    read_gate: tuple[float, ...]
    contribution_weights: tuple[float, ...]
    schema: str = QI_EMISSION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != QI_EMISSION_SCHEMA:
            raise CassiFieldLanguageError("Qi emission schema mismatch")
        _bounded_int("position", self.position, minimum=0, maximum=(1 << 31) - 1)
        if not isinstance(self.available, bool):
            raise CassiFieldLanguageError("Qi emission availability must be boolean")
        if self.available:
            _bounded_int("symbol", self.symbol, minimum=0, maximum=_ALPHABET_SIZE - 1)
        elif self.symbol != -1:
            raise CassiFieldLanguageError("unavailable Qi emission must use symbol -1")
        for name in ("state_sha256", "scores_sha256", "wave_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise CassiFieldLanguageError(f"{name} must be a SHA-256 hex digest")
        for name in ("flux", "margin", "uncertainty"):
            _finite_float(name, getattr(self, name))
        for values in (
            self.q,
            self.q_max,
            self.chi,
            self.cross_scale_coherence,
            self.read_gate,
            self.contribution_weights,
        ):
            if not values or any(not math.isfinite(float(value)) for value in values):
                raise CassiFieldLanguageError("Qi emission diagnostics must be nonempty and finite")

    def receipt_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "chi": list(self.chi),
            "contribution_weights": list(self.contribution_weights),
            "cross_scale_coherence": list(self.cross_scale_coherence),
            "flux": self.flux,
            "margin": self.margin,
            "position": self.position,
            "q": list(self.q),
            "q_max": list(self.q_max),
            "read_gate": list(self.read_gate),
            "schema": self.schema,
            "scores_sha256": self.scores_sha256,
            "state_sha256": self.state_sha256,
            "symbol": self.symbol,
            "uncertainty": self.uncertainty,
            "wave_sha256": self.wave_sha256,
        }

    @property
    def receipt_sha256(self) -> str:
        return _digest(self.receipt_dict())


@dataclass(frozen=True)
class CassiQiOutputStepReceipt:
    """One direct field emission and its committed successor transition."""

    emission: CassiQiEmissionReceipt
    commitment: CassiQiTextStepReceipt
    schema: str = QI_OUTPUT_STEP_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != QI_OUTPUT_STEP_SCHEMA:
            raise CassiFieldLanguageError("Qi output step schema mismatch")
        if not self.emission.available:
            raise CassiFieldLanguageError("an unavailable emission cannot be committed")
        if self.emission.symbol != self.commitment.symbol:
            raise CassiFieldLanguageError("emitted and committed symbols differ")
        if self.emission.state_sha256 != self.commitment.state_before_sha256:
            raise CassiFieldLanguageError("emission and commitment state hashes differ")
        if self.commitment.phase != "output":
            raise CassiFieldLanguageError("output commitment has the wrong phase")

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
        return _digest(self.receipt_dict())


@dataclass(frozen=True)
class CassiQiTextResult:
    """One Qi-native completion and its canonical field successor."""

    state: QiFieldState
    initial_state_sha256: str
    final_state_sha256: str
    prompt_symbols: tuple[int, ...]
    prompt_receipts: tuple[CassiQiTextStepReceipt, ...]
    output_symbols: tuple[int, ...]
    output_receipts: tuple[CassiQiOutputStepReceipt, ...]
    output_bytes: bytes
    text: str
    utf8_valid: bool
    replacement_count: int
    stop_reason: str
    config_fingerprint: str
    codebook_fingerprint: str
    codec_fingerprint: str
    engine_fingerprint: str
    schema: str = QI_TEXT_RESULT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != QI_TEXT_RESULT_SCHEMA:
            raise CassiFieldLanguageError("Qi text result schema mismatch")
        if not isinstance(self.state, QiFieldState):
            raise CassiFieldLanguageError("Qi text result state is invalid")
        if len(self.prompt_symbols) != len(self.prompt_receipts):
            raise CassiFieldLanguageError("prompt receipt count mismatch")
        if len(self.output_symbols) != len(self.output_receipts):
            raise CassiFieldLanguageError("output receipt count mismatch")
        if self.stop_reason not in {"end_turn", "role_boundary", "field_abstained", "max_output_symbols"}:
            raise CassiFieldLanguageError("Qi text stop reason is invalid")
        if not isinstance(self.utf8_valid, bool):
            raise CassiFieldLanguageError("UTF-8 validity must be boolean")
        _bounded_int("replacement_count", self.replacement_count, minimum=0, maximum=1 << 30)
        if hashlib.sha256(self.output_bytes).hexdigest() != self.byte_sha256:
            raise CassiFieldLanguageError("output byte hash mismatch")
        for symbol, receipt in zip(self.prompt_symbols, self.prompt_receipts, strict=True):
            if symbol != receipt.symbol or receipt.phase != "prompt":
                raise CassiFieldLanguageError("prompt symbol receipt mismatch")
        for symbol, receipt in zip(self.output_symbols, self.output_receipts, strict=True):
            if symbol != receipt.emission.symbol:
                raise CassiFieldLanguageError("output symbol receipt mismatch")

    @property
    def byte_length(self) -> int:
        return len(self.output_bytes)

    @property
    def byte_sha256(self) -> str:
        return hashlib.sha256(self.output_bytes).hexdigest()

    @property
    def all_outputs_field_owned(self) -> bool:
        return len(self.output_symbols) == len(self.output_receipts)

    def receipt_dict(self) -> dict[str, Any]:
        return {
            "architecture": {
                "adaptive_persistent_tensor_count": 1,
                "boundary": "fixed-scale-prime-quadratic-chirp",
                "emission": "deterministic-phase-conjugate-resonance-argmax",
                "engineered_feature_width": 0,
                "learned_parameter_count": 0,
                "neural_layer_count": 0,
                "optimizer_state_bytes": 0,
                "probabilistic_sampler": False,
                "state_layout": "[S,9M,B]",
            },
            "byte_length": self.byte_length,
            "byte_sha256": self.byte_sha256,
            "codebook_fingerprint": self.codebook_fingerprint,
            "codec_fingerprint": self.codec_fingerprint,
            "config_fingerprint": self.config_fingerprint,
            "engine_fingerprint": self.engine_fingerprint,
            "final_state_sha256": self.final_state_sha256,
            "initial_state_sha256": self.initial_state_sha256,
            "output_receipts": [receipt.receipt_dict() for receipt in self.output_receipts],
            "output_symbols": list(self.output_symbols),
            "prompt_receipts": [receipt.receipt_dict() for receipt in self.prompt_receipts],
            "prompt_symbols": list(self.prompt_symbols),
            "replacement_count": self.replacement_count,
            "schema": self.schema,
            "stop_reason": self.stop_reason,
            "utf8_valid": self.utf8_valid,
        }

    @property
    def receipt_sha256(self) -> str:
        return _digest(self.receipt_dict())


class CassiQiTextEngine:
    """Stateless text protocol over one canonical Qi controller."""

    def __init__(self, controller: QiFieldController, *, max_output_symbols: int = 256) -> None:
        if not isinstance(controller, QiFieldController):
            raise CassiFieldLanguageError("Qi controller is required")
        self.controller = controller
        self.codec = CassiFieldTextCodec()
        self.max_output_symbols = _bounded_int(
            "max_output_symbols",
            max_output_symbols,
            minimum=1,
            maximum=4096,
        )
        if controller.config.alphabet_size != self.codec.alphabet_size:
            raise CassiFieldLanguageError("Qi alphabet and text codec do not match")

    @property
    def fingerprint(self) -> str:
        return _digest(
            {
                "codebook_fingerprint": self.controller.codebook_fingerprint,
                "codec_fingerprint": self.codec.fingerprint,
                "config_fingerprint": self.controller.config_fingerprint,
                "max_output_symbols": self.max_output_symbols,
                "schema": QI_TEXT_ENGINE_SCHEMA,
            }
        )

    def initial_state(self, *, device: torch.device | str = "cpu") -> QiFieldState:
        return self.controller.initial_state(1, device=device, dtype=torch.float32)

    def _advance_symbol(
        self,
        state: QiFieldState,
        symbol: int,
        *,
        phase: str,
        position: int,
    ) -> tuple[QiFieldState, CassiQiTextStepReceipt]:
        _bounded_int("symbol", symbol, minimum=0, maximum=self.codec.alphabet_size - 1)
        before_sha256 = qi_state_sha256(self.controller, state)
        try:
            sensed = self.controller.sense_symbols(state, [symbol])
            sensed_sha256 = qi_state_sha256(self.controller, sensed)
            evolved = self.controller.evolve(sensed)
            successor = self.controller.consolidate(evolved)
            diagnostics = self.controller.diagnostics(successor)
        except QiFieldError as error:
            raise CassiFieldLanguageError(f"Qi symbol transition failed: {error}") from error
        receipt = CassiQiTextStepReceipt(
            phase=phase,
            position=position,
            symbol=symbol,
            state_before_sha256=before_sha256,
            sensed_state_sha256=sensed_sha256,
            state_after_sha256=qi_state_sha256(self.controller, successor),
            q=_column(diagnostics.q),
            chi=_column(diagnostics.chi),
            read_gate=_column(diagnostics.read_gate),
            write_gate=_column(diagnostics.write_gate),
            consolidation_gate=_column(diagnostics.consolidation_gate),
        )
        return successor, receipt

    def _emission_receipt(
        self,
        state: QiFieldState,
        readout: QiFieldReadout,
        *,
        position: int,
    ) -> CassiQiEmissionReceipt:
        if readout.symbols.numel() != 1 or readout.available.numel() != 1:
            raise CassiFieldLanguageError("Qi text emission requires batch size one")
        available = bool(readout.available.reshape(-1)[0].item())
        symbol = int(readout.symbols.reshape(-1)[0].item())
        if not available:
            symbol = -1
        return CassiQiEmissionReceipt(
            position=position,
            state_sha256=qi_state_sha256(self.controller, state),
            available=available,
            symbol=symbol,
            scores_sha256=_tensor_sha256(readout.scores),
            wave_sha256=_tensor_sha256(readout.wave),
            flux=_finite_float("flux", readout.flux.reshape(-1)[0].item()),
            margin=_finite_float("margin", readout.margin.reshape(-1)[0].item()),
            uncertainty=_finite_float("uncertainty", readout.uncertainty.reshape(-1)[0].item()),
            q=_values(readout.q),
            q_max=_values(readout.q_max),
            chi=_values(readout.chi),
            cross_scale_coherence=_values(readout.cross_scale_coherence),
            read_gate=_values(readout.read_gate),
            contribution_weights=_column(readout.contribution_weights),
        )

    def generate(
        self,
        state: QiFieldState,
        messages: Sequence[Mapping[str, object]],
        *,
        max_output_symbols: int | None = None,
    ) -> CassiQiTextResult:
        if not isinstance(state, QiFieldState) or state.batch_size != 1:
            raise CassiFieldLanguageError("Qi text generation requires one field state")
        try:
            state.validate(self.controller.config)
        except QiFieldError as error:
            raise CassiFieldLanguageError(f"invalid initial Qi state: {error}") from error
        limit = self.max_output_symbols if max_output_symbols is None else _bounded_int(
            "max_output_symbols",
            max_output_symbols,
            minimum=1,
            maximum=self.max_output_symbols,
        )
        prompt_symbols = self.codec.encode_messages(messages)
        initial_state_sha256 = qi_state_sha256(self.controller, state)
        current = state
        prompt_receipts: list[CassiQiTextStepReceipt] = []
        for position, symbol in enumerate(prompt_symbols):
            current, receipt = self._advance_symbol(
                current,
                symbol,
                phase="prompt",
                position=position,
            )
            prompt_receipts.append(receipt)

        output_symbols: list[int] = []
        output_receipts: list[CassiQiOutputStepReceipt] = []
        output_bytes = bytearray()
        stop_reason = "max_output_symbols"
        for position in range(limit):
            try:
                readout = self.controller.emit(current)
            except QiFieldError as error:
                raise CassiFieldLanguageError(f"Qi emission failed: {error}") from error
            emission = self._emission_receipt(current, readout, position=position)
            if not emission.available:
                stop_reason = "field_abstained"
                break
            symbol = emission.symbol
            current, commitment = self._advance_symbol(
                current,
                symbol,
                phase="output",
                position=position,
            )
            output_symbols.append(symbol)
            output_receipts.append(CassiQiOutputStepReceipt(emission, commitment))
            if symbol == self.codec.end_turn_symbol:
                stop_reason = "end_turn"
                break
            if not 0 <= symbol < _BYTE_SYMBOL_COUNT:
                stop_reason = "role_boundary"
                break
            output_bytes.append(symbol)

        raw_output = bytes(output_bytes)
        text, utf8_valid, replacement_count = _decode_output_bytes(raw_output)
        return CassiQiTextResult(
            state=current,
            initial_state_sha256=initial_state_sha256,
            final_state_sha256=qi_state_sha256(self.controller, current),
            prompt_symbols=prompt_symbols,
            prompt_receipts=tuple(prompt_receipts),
            output_symbols=tuple(output_symbols),
            output_receipts=tuple(output_receipts),
            output_bytes=raw_output,
            text=text,
            utf8_valid=utf8_valid,
            replacement_count=replacement_count,
            stop_reason=stop_reason,
            config_fingerprint=self.controller.config_fingerprint,
            codebook_fingerprint=self.controller.codebook_fingerprint,
            codec_fingerprint=self.codec.fingerprint,
            engine_fingerprint=self.fingerprint,
        )


def generate_text(
    controller: QiFieldController,
    state: QiFieldState,
    messages: Sequence[Mapping[str, object]],
    *,
    max_output_symbols: int = 256,
) -> CassiQiTextResult:
    """Convenience call through the same deterministic Qi-native engine."""

    return CassiQiTextEngine(
        controller,
        max_output_symbols=max_output_symbols,
    ).generate(state, messages, max_output_symbols=max_output_symbols)


class CassiQiSessionStore:
    """Atomic per-session persistence of one Qi state plus non-adaptive receipt metadata."""

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
            state = self.controller.load_state_bytes(state_bytes, device="cpu", dtype=torch.float32)
        except QiFieldError as error:
            raise CassiFieldLanguageError(f"Qi session field is invalid: {error}") from error
        claimed = payload.get("state_sha256")
        actual = qi_state_sha256(self.controller, state)
        if claimed != actual:
            raise CassiFieldLanguageError("Qi session state hash mismatch")
        return state, metadata, path

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
        stream = io.BytesIO()
        torch.save(payload, stream)
        serialized = stream.getvalue()
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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
        return path, hashlib.sha256(serialized).hexdigest()


__all__ = [
    "CassiFieldLanguageError",
    "CassiFieldTextCodec",
    "CassiQiEmissionReceipt",
    "CassiQiOutputStepReceipt",
    "CassiQiSessionStore",
    "CassiQiTextEngine",
    "CassiQiTextResult",
    "CassiQiTextStepReceipt",
    "FIELD_TEXT_CODEC_SCHEMA",
    "QI_EMISSION_SCHEMA",
    "QI_OUTPUT_STEP_SCHEMA",
    "QI_SESSION_SCHEMA",
    "QI_TEXT_ENGINE_SCHEMA",
    "QI_TEXT_RESULT_SCHEMA",
    "QI_TEXT_STEP_SCHEMA",
    "generate_text",
    "qi_state_sha256",
]
