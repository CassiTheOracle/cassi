"""Independent GGUF vocabulary and byte-level BPE tokenizer for Qwen models.

The codec reads tokenizer metadata directly from the GGUF descriptor.  It does
not start a server, download a tokenizer, or consult a model runtime.  GGUF
weights are not read while encoding or decoding; metadata and its provenance
are cached on the tokenizer instance.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

from programs.python.records import digest_value

from .gguf import (
    _MAGIC,
    _TOKENIZER_KEYS,
    _VALUE_TYPES,
    _read_exact,
    _string,
    _u32,
    _u64,
    _value,
)


class TokenizerError(ValueError):
    """The GGUF tokenizer metadata is unavailable or unsupported."""


# GGML token-type values.  CONTROL and USER_DEFINED must remain atomic during
# Qwen chat encoding; BYTE tokens are regular byte fallbacks, not specials.
_TOKEN_NORMAL = 1
_TOKEN_UNKNOWN = 2
_TOKEN_CONTROL = 3
_TOKEN_USER_DEFINED = 4
_TOKEN_UNUSED = 5
_TOKEN_BYTE = 6


def _metadata(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], int, int]:
    """Read only the GGUF header/metadata region, never tensor payloads."""
    try:
        with path.open("rb") as stream:
            if _read_exact(stream, 4) != _MAGIC:
                raise TokenizerError("GGUF magic is invalid")
            version = _u32(stream)
            if version not in {2, 3}:
                raise TokenizerError(f"GGUF version {version} is unsupported")
            tensor_count = _u64(stream)
            metadata_count = _u64(stream)
            if metadata_count > 1_000_000 or tensor_count > 1_000_000:
                raise TokenizerError("GGUF descriptor count exceeds its bound")
            values: dict[str, Any] = {}
            entries: list[dict[str, Any]] = []
            for _ in range(metadata_count):
                key = _string(stream)
                if not key or key in values:
                    raise TokenizerError("GGUF metadata key is empty or duplicated")
                type_id = _u32(stream)
                if type_id not in _VALUE_TYPES:
                    raise TokenizerError(f"GGUF metadata type {type_id} is unsupported")
                item = _value(stream, type_id)
                values[key] = item
                if key in _TOKENIZER_KEYS:
                    entry: dict[str, Any] = {
                        "key": key,
                        "type": _VALUE_TYPES[type_id],
                        "value_sha256": digest_value(item),
                    }
                    if isinstance(item, list):
                        entry["length"] = len(item)
                    entries.append(entry)
            metadata_end = stream.tell()
            return values, entries, int(version), int(metadata_end)
    except OSError as exc:
        raise TokenizerError(f"cannot read GGUF metadata: {path}") from exc


def _bytes_to_unicode() -> dict[int, str]:
    # GPT-2's reversible byte-level alphabet, also used by Qwen2/Qwen3.
    direct = list(range(ord("!"), ord("~") + 1))
    direct += list(range(ord("¡"), ord("¬") + 1))
    direct += list(range(ord("®"), ord("ÿ") + 1))
    mapped = direct[:]
    extra = 0
    for value in range(256):
        if value not in direct:
            direct.append(value)
            mapped.append(256 + extra)
            extra += 1
    return {byte: chr(codepoint) for byte, codepoint in zip(direct, mapped)}


_BYTE_ENCODER = _bytes_to_unicode()
_BYTE_DECODER = {symbol: byte for byte, symbol in _BYTE_ENCODER.items()}
_BYTE_FALLBACK = re.compile(r"^<0x([0-9A-Fa-f]{2})>$")

try:  # ``regex`` supports the Unicode property classes in Qwen's pre-tokenizer.
    import regex as _regex  # type: ignore[import-not-found]

    _QWEN_RE = _regex.compile(
        r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}{1,3}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"
    )
except Exception:  # pragma: no cover - exercised only on minimal Python installs
    _regex = None
    _QWEN_RE = None


class GGUFTokenizer:
    """Tokenize/de-tokenize the vocabulary embedded in a Qwen GGUF."""

    def __init__(self, model_path: str | Path) -> None:
        path = Path(model_path).expanduser().resolve()
        if not path.is_file():
            raise TokenizerError(f"GGUF model is not a regular file: {path}")
        metadata, entries, version, metadata_end = _metadata(path)
        raw_tokens = metadata.get("tokenizer.ggml.tokens")
        raw_merges = metadata.get("tokenizer.ggml.merges")
        if not isinstance(raw_tokens, list) or not raw_tokens or not all(isinstance(item, str) for item in raw_tokens):
            raise TokenizerError("GGUF tokenizer.ggml.tokens is missing or invalid")
        model = metadata.get("tokenizer.ggml.model")
        if not isinstance(model, str) or not model:
            raise TokenizerError("GGUF tokenizer.ggml.model is missing")
        if not isinstance(raw_merges, list) or not all(isinstance(item, str) for item in raw_merges):
            raise TokenizerError("GGUF tokenizer.ggml.merges is missing or invalid")
        raw_types = metadata.get("tokenizer.ggml.token_type", [])
        if raw_types and (not isinstance(raw_types, list) or len(raw_types) != len(raw_tokens)):
            raise TokenizerError("GGUF tokenizer token_type length does not match tokens")
        token_types = [int(value) for value in raw_types] if raw_types else [_TOKEN_NORMAL] * len(raw_tokens)
        if any(value < 0 or value > 255 for value in token_types):
            raise TokenizerError("GGUF tokenizer token_type contains an invalid value")

        self.model_path = path
        self.model = model
        self.tokens = tuple(raw_tokens)
        self.merges = tuple(raw_merges)
        self.token_types = tuple(token_types)
        self._token_to_id: dict[str, int] = {}
        for token_id, piece in enumerate(self.tokens):
            self._token_to_id.setdefault(piece, token_id)
        self._merge_ranks: dict[tuple[str, str], int] = {}
        for rank, merge in enumerate(self.merges):
            fields = merge.split(" ", 1)
            if len(fields) != 2 or not fields[0] or not fields[1]:
                raise TokenizerError(f"invalid tokenizer merge at rank {rank}")
            pair = (fields[0], fields[1])
            self._merge_ranks.setdefault(pair, rank)

        self.bos_token_id = self._optional_id(metadata.get("tokenizer.ggml.bos_token_id"))
        self.eos_token_id = self._optional_id(metadata.get("tokenizer.ggml.eos_token_id"))
        self.unknown_token_id = self._optional_id(metadata.get("tokenizer.ggml.unknown_token_id"))
        self.padding_token_id = self._optional_id(metadata.get("tokenizer.ggml.padding_token_id"))
        self.add_bos_token = bool(metadata.get("tokenizer.ggml.add_bos_token", False))
        self.add_eos_token = bool(metadata.get("tokenizer.ggml.add_eos_token", False))
        self.chat_template = metadata.get("tokenizer.chat_template")

        specials: dict[str, int] = {}
        for token_id, piece in enumerate(self.tokens):
            kind = self.token_types[token_id]
            if kind in {_TOKEN_UNKNOWN, _TOKEN_CONTROL, _TOKEN_USER_DEFINED, _TOKEN_UNUSED} or (
                piece.startswith("<|") and piece.endswith("|>")
            ):
                specials.setdefault(piece, token_id)
        for token_id in (
            self.bos_token_id,
            self.eos_token_id,
            self.unknown_token_id,
            self.padding_token_id,
        ):
            if token_id is not None and 0 <= token_id < len(self.tokens):
                specials.setdefault(self.tokens[token_id], token_id)
        added = metadata.get("tokenizer.ggml.added_tokens", [])
        if isinstance(added, list):
            for item in added:
                if isinstance(item, str) and item in self._token_to_id:
                    specials.setdefault(item, self._token_to_id[item])
        self._special_to_id = specials
        self._special_pieces = tuple(sorted(specials, key=len, reverse=True))
        self._piece_cache: dict[str, tuple[int, ...]] = {}
        self._source_sha256: str | None = None
        self.provenance = {
            "schema": "cassifi.gguf-tokenizer-provenance.v1",
            "source_id": path.name,
            "source_path": str(path),
            "file_size": path.stat().st_size,
            "gguf_version": version,
            "metadata_end": metadata_end,
            "metadata_sha256": digest_value(entries),
            "tokenizer_metadata_sha256": digest_value(entries),
            "model": model,
            "token_count": len(self.tokens),
            "merge_count": len(self.merges),
        }

    @staticmethod
    def _optional_id(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TokenizerError("GGUF tokenizer special-token id is invalid")
        return int(value)

    @property
    def source_sha256(self) -> str:
        """Return the GGUF source digest, computed at most once and never by encode."""
        if self._source_sha256 is None:
            digest = hashlib.sha256()
            with self.model_path.open("rb") as stream:
                while chunk := stream.read(8 << 20):
                    digest.update(chunk)
            self._source_sha256 = digest.hexdigest()
            self.provenance["source_sha256"] = self._source_sha256
        return self._source_sha256

    @staticmethod
    def _bpe_pair(word: tuple[str, ...]) -> Iterable[tuple[str, str]]:
        return zip(word, word[1:])

    def _bpe(self, mapped: str) -> tuple[str, ...]:
        word = tuple(mapped)
        if len(word) < 2:
            return word
        while True:
            ranked = [(self._merge_ranks[pair], pair) for pair in self._bpe_pair(word) if pair in self._merge_ranks]
            if not ranked:
                return word
            _, best = min(ranked, key=lambda item: item[0])
            merged: list[str] = []
            index = 0
            while index < len(word):
                if index + 1 < len(word) and (word[index], word[index + 1]) == best:
                    merged.append(word[index] + word[index + 1])
                    index += 2
                else:
                    merged.append(word[index])
                    index += 1
            word = tuple(merged)
            if len(word) < 2:
                return word

    def _encode_piece(self, text: str) -> tuple[int, ...]:
        cached = self._piece_cache.get(text)
        if cached is not None:
            return cached
        mapped = "".join(_BYTE_ENCODER[value] for value in text.encode("utf-8"))
        result: list[int] = []
        for piece in self._bpe(mapped):
            token_id = self._token_to_id.get(piece)
            if token_id is not None:
                result.append(token_id)
                continue
            # Qwen byte fallback vocabularies use explicit <0xNN> symbols.
            for symbol in piece:
                symbol_id = self._token_to_id.get(symbol)
                if symbol_id is not None:
                    result.append(symbol_id)
                    continue
                byte_value = _BYTE_DECODER.get(symbol)
                fallback = (
                    self._token_to_id.get(f"<0x{byte_value:02X}>")
                    if byte_value is not None
                    else None
                )
                if fallback is not None:
                    result.append(fallback)
                    continue
                if self.unknown_token_id is None:
                    raise TokenizerError(f"GGUF vocabulary cannot encode byte-level piece {piece!r}")
                result.append(self.unknown_token_id)
        encoded = tuple(result)
        self._piece_cache[text] = encoded
        return encoded

    def _pretokenize(self, text: str) -> Iterable[str]:
        if _QWEN_RE is not None:
            return (match.group(0) for match in _QWEN_RE.finditer(text))
        # Minimal environments without ``regex`` still preserve all text and
        # use the same byte-BPE vocabulary; only Unicode-property grouping is
        # less granular.
        return (match.group(0) for match in re.finditer(r"\s+|[^\s]+", text))

    def _encode_text(self, text: str) -> list[int]:
        if not text:
            return []
        output: list[int] = []
        offset = 0
        while offset < len(text):
            selected: str | None = None
            for special in self._special_pieces:
                if text.startswith(special, offset):
                    selected = special
                    break
            if selected is not None:
                output.append(self._special_to_id[selected])
                offset += len(selected)
                continue
            next_special = len(text)
            for special in self._special_pieces:
                position = text.find(special, offset)
                if position >= 0 and position < next_special:
                    next_special = position
            segment = text[offset:next_special]
            output.extend(
                token_id
                for piece in self._pretokenize(segment)
                for token_id in self._encode_piece(piece)
            )
            offset = next_special
        return output

    def encode(self, text: str, add_special: bool = False) -> list[int]:
        if not isinstance(text, str):
            raise TokenizerError("text must be a string")
        if not isinstance(add_special, bool):
            raise TokenizerError("add_special must be boolean")
        output: list[int] = []
        if add_special and self.add_bos_token and self.bos_token_id is not None:
            output.append(self.bos_token_id)
        output.extend(self._encode_text(text))
        if add_special and self.add_eos_token and self.eos_token_id is not None:
            output.append(self.eos_token_id)
        return output

    def decode(self, tokens: Iterable[int]) -> str:
        try:
            values = list(tokens)
        except TypeError as exc:
            raise TokenizerError("tokens must be an iterable of integers") from exc
        output: list[str] = []
        raw = bytearray()

        def flush() -> None:
            if raw:
                output.append(bytes(raw).decode("utf-8", errors="replace"))
                raw.clear()

        for token in values:
            if isinstance(token, bool) or not isinstance(token, (int,)):
                raise TokenizerError("token ids must be integers")
            token_id = int(token)
            if token_id < 0 or token_id >= len(self.tokens):
                raise TokenizerError(f"token id {token_id} is outside vocabulary")
            piece = self.tokens[token_id]
            if token_id in self._special_to_id.values():
                flush()
                output.append(piece)
                continue
            fallback = _BYTE_FALLBACK.fullmatch(piece)
            if fallback:
                raw.append(int(fallback.group(1), 16))
                continue
            try:
                raw.extend(_BYTE_DECODER[char] for char in piece)
            except KeyError:
                # A normal Unicode vocabulary piece (rather than GPT-2's
                # escaped alphabet) is still decoded losslessly.
                raw.extend(piece.encode("utf-8"))
        flush()
        return "".join(output)

    @property
    def eog_ids(self) -> frozenset[int]:
        """Qwen end-of-generation ids (EOS and explicit end/control markers)."""
        values: set[int] = set()
        if self.eos_token_id is not None:
            values.add(self.eos_token_id)
        for piece, token_id in self._special_to_id.items():
            lower = piece.lower()
            if "eot" in lower or "endoftext" in lower or "im_end" in lower or "eog" in lower:
                values.add(token_id)
        return frozenset(values)


__all__ = ["GGUFTokenizer", "TokenizerError"]
