"""Fixed UTF-8 event codec shared by Cassi field runtimes."""

from __future__ import annotations

import codecs
import dataclasses
import hashlib
import json
from typing import Any, Final, Mapping, Sequence

import torch

FIELD_TEXT_CODEC_SCHEMA: Final[str] = "cassi.qi-text-codec.v1"
FIELD_ALPHABET_SIZE: Final[int] = 260
FIELD_BYTE_SYMBOLS: Final[int] = 256


class CassiFieldLanguageError(RuntimeError):
    """Raised when a field-owned language boundary cannot proceed safely."""


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CassiFieldLanguageError(
            f"value is not canonical finite JSON: {error}"
        ) from error


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


@dataclasses.dataclass(frozen=True)
class CassiFieldTextCodec:
    """Frozen UTF-8 byte/control boundary; it owns no adaptive state."""

    byte_symbol_limit: int = FIELD_BYTE_SYMBOLS
    end_turn_symbol: int = 256
    system_symbol: int = 257
    user_symbol: int = 258
    assistant_symbol: int = 259
    schema: str = FIELD_TEXT_CODEC_SCHEMA

    def __post_init__(self) -> None:
        if (
            self.schema != FIELD_TEXT_CODEC_SCHEMA
            or self.byte_symbol_limit != FIELD_BYTE_SYMBOLS
            or (
                self.end_turn_symbol,
                self.system_symbol,
                self.user_symbol,
                self.assistant_symbol,
            )
            != (256, 257, 258, 259)
        ):
            raise CassiFieldLanguageError("the frozen 260-event codec was modified")

    @property
    def alphabet_size(self) -> int:
        return FIELD_ALPHABET_SIZE

    @property
    def fingerprint(self) -> str:
        return _canonical_sha256(
            {
                "byte_symbol_limit": self.byte_symbol_limit,
                "controls": {
                    "assistant": self.assistant_symbol,
                    "end_turn": self.end_turn_symbol,
                    "system": self.system_symbol,
                    "user": self.user_symbol,
                },
                "schema": self.schema,
            }
        )

    def _role_symbol(self, role: str) -> int:
        if role == "system":
            return self.system_symbol
        if role == "user":
            return self.user_symbol
        if role == "assistant":
            return self.assistant_symbol
        raise CassiFieldLanguageError(f"unsupported message role: {role!r}")

    def encode_messages(
        self, messages: Sequence[Mapping[str, Any]]
    ) -> tuple[int, ...]:
        if isinstance(messages, (str, bytes, bytearray)) or not messages:
            raise CassiFieldLanguageError("messages must be a nonempty sequence")
        symbols: list[int] = []
        for message in messages:
            if not isinstance(message, Mapping):
                raise CassiFieldLanguageError("each message must be an object")
            role = message.get("role")
            content = message.get("content")
            if not isinstance(role, str) or not isinstance(content, str):
                raise CassiFieldLanguageError(
                    "message role and content must both be strings"
                )
            symbols.append(self._role_symbol(role))
            symbols.extend(content.encode("utf-8"))
            symbols.append(self.end_turn_symbol)
        return tuple(symbols)

    def encode_training_exchange(
        self, prompt: bytes, continuation: bytes
    ) -> tuple[int, ...]:
        if not prompt or not continuation:
            raise CassiFieldLanguageError(
                "training exchanges require nonempty prompt and continuation bytes"
            )
        return (
            self.user_symbol,
            *prompt,
            self.end_turn_symbol,
            self.assistant_symbol,
            *continuation,
            self.end_turn_symbol,
        )

    def decode_symbols(self, symbols: Sequence[int]) -> tuple[bytes, str]:
        raw = bytearray()
        for symbol in symbols:
            if isinstance(symbol, bool) or not 0 <= int(symbol) < FIELD_BYTE_SYMBOLS:
                raise CassiFieldLanguageError(
                    "only committed byte symbols may cross the text boundary"
                )
            raw.append(int(symbol))
        payload = bytes(raw)
        return payload, payload.decode("utf-8", errors="replace")

    def output_mask(self, prefix: bytes, *, device: torch.device) -> torch.Tensor:
        """Return fixed protocol-valid byte/end-turn channels for one UTF-8 prefix."""
        mask = torch.zeros(FIELD_ALPHABET_SIZE, dtype=torch.bool, device=device)
        decoder_type = codecs.getincrementaldecoder("utf-8")
        for symbol in range(FIELD_BYTE_SYMBOLS):
            try:
                decoder = decoder_type(errors="strict")
                decoder.decode(prefix + bytes((symbol,)), final=False)
            except UnicodeDecodeError:
                continue
            mask[symbol] = True
        try:
            prefix.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            pass
        else:
            mask[self.end_turn_symbol] = True
        return mask


__all__ = [
    "CassiFieldLanguageError",
    "CassiFieldTextCodec",
    "FIELD_ALPHABET_SIZE",
    "FIELD_BYTE_SYMBOLS",
    "FIELD_TEXT_CODEC_SCHEMA",
]
