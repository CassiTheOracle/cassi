"""Shared plumbing for the hidden-state lens: GGUF unembedding/tokenizer access,
capture enumeration, and a streaming logit lens.

Everything here is read-only over artifacts that already exist on disk.  No
model is loaded and no llama.cpp code is invoked; the only model-side inputs are
the pinned GGUF's final norm and output projection.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

WORKSPACE = Path(__file__).resolve().parents[2]
CASSIQWEN = WORKSPACE / "CassiQwen"
GGUF_PY = CASSIQWEN / "native" / "llama.cpp" / "gguf-py"
if str(GGUF_PY) not in sys.path:
    sys.path.insert(0, str(GGUF_PY))

CAPTURE_ROOTS = (
    CASSIQWEN / "native" / "llama.cpp" / "_diag",
    CASSIQWEN / "_diag",
)

LAYER_RE = re.compile(r"^layer-(\d+)(-decode-early|-decode)?\.f32$")
DECODE_LOGITS_RE = re.compile(r"^decode-logits-(\d+)\.f32$")

MODELS = {
    5120: CASSIQWEN / "Qwen3.8-27B-Q4_K_M.gguf",
    1024: CASSIQWEN / "Qwen3.5-0.8B-Q4_0.gguf",
}


# --------------------------------------------------------------------------
# tokenizer
# --------------------------------------------------------------------------

def _byte_decoder():
    from gguf.vocab import bytes_to_unicode

    return {ch: byte for byte, ch in bytes_to_unicode().items()}


_BYTE_DECODER = None
_VOCAB_CACHE: dict[str, tuple[list[str], list[int]]] = {}


def gguf_vocab(gguf_path: Path):
    key = str(gguf_path)
    if key not in _VOCAB_CACHE:
        from gguf import GGUFReader

        reader = GGUFReader(str(gguf_path))
        tokens = list(reader.fields["tokenizer.ggml.tokens"].contents())
        types_field = reader.fields.get("tokenizer.ggml.token_type")
        types = list(types_field.contents()) if types_field is not None else [1] * len(tokens)
        _VOCAB_CACHE[key] = (tokens, [int(t) for t in types])
    return _VOCAB_CACHE[key]


def token_bytes(token_id: int, vocab_path: Path) -> bytes:
    """llama_token_to_piece semantics for a byte-level BPE (Qwen/GGUF) vocab."""
    global _BYTE_DECODER
    tokens, types = gguf_vocab(vocab_path)
    if not 0 <= token_id < len(tokens):
        return b""
    text = tokens[token_id]
    kind = types[token_id]
    if kind == 6:  # LLAMA_TOKEN_TYPE_BYTE: "<0xhh>"
        hexed = text[1:-1]
        return bytes([int(hexed, 16)]) if hexed.startswith("0x") else b""
    if kind in (3, 4):  # CONTROL / USER_DEFINED (special tokens)
        return text.encode("utf-8")
    if _BYTE_DECODER is None:
        _BYTE_DECODER = _byte_decoder()
    out = bytearray()
    for ch in text:
        out.append(_BYTE_DECODER.get(ch, ord(ch) & 0xFF))
    return bytes(out)


def token_text(token_id: int, vocab_path: Path) -> str:
    return token_bytes(token_id, vocab_path).decode("utf-8", errors="replace")


def decode_tokens(token_ids, vocab_path: Path) -> str:
    return b"".join(token_bytes(int(t), vocab_path) for t in token_ids).decode(
        "utf-8", errors="replace"
    )


# --------------------------------------------------------------------------
# unembedding + final norm
# --------------------------------------------------------------------------

@dataclass
class Unembed:
    path: Path
    tensor_name: str
    tensor_type: int
    n_vocab: int
    n_embd: int
    bytes_per_row: int
    norm_weight: np.ndarray
    eps: float
    _raw: object = field(repr=False, default=None)

    def dequant_rows(self, start: int, stop: int) -> np.ndarray:
        from gguf import quants
        from gguf.constants import GGMLQuantizationType as QType

        chunk = np.ascontiguousarray(self._raw[start:stop])
        qtype = QType(self.tensor_type)
        values = quants.dequantize(chunk, qtype)
        return np.ascontiguousarray(values, dtype=np.float32).reshape(stop - start, self.n_embd)

    def close(self):
        self._raw = None


def load_unembed(gguf_path: Path, close_raw_after: bool = False) -> Unembed:
    from gguf import GGUFReader

    reader = GGUFReader(str(gguf_path))
    by_name = {t.name: t for t in reader.tensors}
    if "output.weight" in by_name:
        tensor = by_name["output.weight"]
        name = "output.weight"
    elif "token_embd.weight" in by_name:
        tensor = by_name["token_embd.weight"]
        name = "token_embd.weight (tied unembedding)"
    else:
        raise RuntimeError(f"no unembedding tensor in {gguf_path}")
    norm = by_name["output_norm.weight"]
    n_embd = int(tensor.shape[0])
    n_vocab = int(tensor.shape[1])
    raw = tensor.data.reshape(n_vocab, tensor.data.nbytes // n_vocab)
    arch = reader.fields["general.architecture"].contents()
    eps = float(reader.fields[f"{arch}.attention.layer_norm_rms_epsilon"].contents())
    bank = Unembed(
        path=gguf_path,
        tensor_name=name,
        tensor_type=int(tensor.tensor_type),
        n_vocab=n_vocab,
        n_embd=n_embd,
        bytes_per_row=int(raw.shape[1]),
        norm_weight=np.asarray(norm.data, dtype=np.float32).copy(),
        eps=eps,
        _raw=raw,
    )
    return bank


def rms_norm(x: np.ndarray, weight: np.ndarray, eps: float) -> np.ndarray:
    """x: (n_embd, n_states) -> normalized, scaled residual."""
    scale = 1.0 / np.sqrt(np.mean(np.square(x, dtype=np.float64), axis=0) + eps)
    return (x * scale.astype(np.float32)[None, :]) * weight[:, None]


@dataclass
class LensResult:
    top1: np.ndarray          # (n_states,) token id
    top1_logit: np.ndarray
    top5: np.ndarray          # (n_states, 5) token ids
    answer_logit: np.ndarray  # lens logit of the model's own next token
    answer_rank: np.ndarray   # exact 1-based rank of that token in the lens
    log_z: np.ndarray
    entropy: np.ndarray


def lens(X: np.ndarray, bank: Unembed, answer_ids: np.ndarray, batch: int = 384) -> LensResult:
    """Apply the final norm's partner (unembedding) to every column of X.

    X is already rms-normalized and scaled.  Returns per-state statistics of the
    induced distribution, computed exactly (no sampling, no approximation).
    """
    n_states = X.shape[1]
    out = {
        "top1": np.zeros(n_states, dtype=np.int64),
        "top1_logit": np.zeros(n_states, dtype=np.float32),
        "top5": np.zeros((n_states, 5), dtype=np.int64),
        "answer_logit": np.full(n_states, np.nan, dtype=np.float32),
        "answer_rank": np.zeros(n_states, dtype=np.int64),
        "log_z": np.zeros(n_states, dtype=np.float64),
        "entropy": np.zeros(n_states, dtype=np.float64),
    }
    order = np.argsort(answer_ids)
    for begin in range(0, n_states, batch):
        end = min(begin + batch, n_states)
        logits = np.empty((bank.n_vocab, end - begin), dtype=np.float32)
        for start in range(0, bank.n_vocab, 4096):
            stop = min(start + 4096, bank.n_vocab)
            w = bank.dequant_rows(start, stop)
            logits[start:stop] = w @ X[:, begin:end]
        chunk_answer = answer_ids[begin:end]
        row_ids = np.arange(logits.shape[0], dtype=np.int64)[:, None]
        answer_logit = logits[chunk_answer, np.arange(end - begin)]
        answer_rank = (logits > answer_logit[None, :]).sum(axis=0) + 1
        maxes = logits.max(axis=0)
        top1 = logits.argmax(axis=0)
        shifted = np.exp((logits - maxes[None, :]).astype(np.float64))
        sums = shifted.sum(axis=0)
        log_z = maxes.astype(np.float64) + np.log(sums)
        probs = shifted / sums[None, :]
        entropy = -(probs * np.log(np.maximum(probs, 1e-300))).sum(axis=0)
        part = np.argpartition(-logits, 4, axis=0)[:5]
        order_part = np.take_along_axis(logits, part, axis=0).argsort(axis=0)[::-1]
        top5 = np.take_along_axis(part, order_part, axis=0).T
        out["top1"][begin:end] = top1
        out["top1_logit"][begin:end] = logits[top1, np.arange(end - begin)]
        out["top5"][begin:end] = top5
        out["answer_logit"][begin:end] = answer_logit
        out["answer_rank"][begin:end] = answer_rank
        out["log_z"][begin:end] = log_z
        out["entropy"][begin:end] = entropy
        del logits
        del row_ids
    return LensResult(**out)


# --------------------------------------------------------------------------
# capture enumeration
# --------------------------------------------------------------------------

@dataclass
class CaptureDir:
    path: Path
    width: int
    layers: list[int]
    kinds: list[str]
    logits_path: Path | None
    answer_ids: dict[str, int]
    prompt_text: str | None
    prompt_source: str | None
    model_gguf: str | None
    trajectory_sha256: str
    layer_sha256: dict[str, str]


def capture_dirs(roots=CAPTURE_ROOTS):
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            if any(LAYER_RE.match(f) for f in filenames):
                yield Path(dirpath)


def _find_prompt(path: Path):
    current = path
    for _ in range(4):
        candidate = current / "prompt.txt"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="replace"), str(candidate)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None, None


def read_f32(path: Path) -> np.ndarray:
    return np.fromfile(path, dtype=np.float32)


def load_capture_dir(path: Path, want_sha: bool = False) -> CaptureDir | None:
    names = os.listdir(path)
    prompt_layers = sorted(int(m.group(1)) for m in (LAYER_RE.match(f) for f in names) if m and not m.group(2))
    if not prompt_layers:
        return None
    kinds = sorted({m.group(2).lstrip("-") for m in (LAYER_RE.match(f) for f in names) if m and m.group(2)})
    probe = path / f"layer-{prompt_layers[0]}.f32"
    width = probe.stat().st_size // 4
    logits_path = path / "logits.f32"
    answer_ids: dict[str, int] = {}
    if logits_path.is_file():
        answer_ids["prompt"] = int(read_f32(logits_path).argmax())
    decode_files = sorted(
        ((int(m.group(1)), f) for m in (DECODE_LOGITS_RE.match(f) for f in names) if m),
        key=lambda item: item[0],
    )
    if decode_files:
        first_index = decode_files[0][0]
        for index, name in decode_files:
            ids = read_f32(path / name)
            if index == 1:
                answer_ids["decode-early"] = int(ids.argmax())
            if index == decode_files[-1][0]:
                answer_ids["decode"] = int(ids.argmax())
        # The early-decode capture is taken after the i==1 decode completes.
        if "decode-early" not in answer_ids and first_index == 0 and len(decode_files) > 1:
            answer_ids["decode-early"] = int(read_f32(path / decode_files[1][1]).argmax())
    prompt_text, prompt_source = _find_prompt(path)
    trajectory = hashlib.sha256()
    layer_sha: dict[str, str] = {}
    for name in sorted(names):
        if not LAYER_RE.match(name):
            continue
        blob = (path / name).read_bytes()
        trajectory.update(blob)
        if want_sha:
            layer_sha[name] = hashlib.sha256(blob).hexdigest()
    return CaptureDir(
        path=path,
        width=width,
        layers=prompt_layers,
        kinds=kinds,
        logits_path=logits_path if logits_path.is_file() else None,
        answer_ids=answer_ids,
        prompt_text=prompt_text,
        prompt_source=prompt_source,
        model_gguf=None,
        trajectory_sha256=trajectory.hexdigest(),
        layer_sha256=layer_sha,
    )


def load_residual_stack(capture: CaptureDir, kind: str, layer: int) -> np.ndarray | None:
    suffix = {"prompt": "", "decode": "-decode", "decode-early": "-decode-early"}[kind]
    path = capture.path / f"layer-{layer}{suffix}.f32"
    if not path.is_file():
        return None
    return read_f32(path)


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max()
    exp = np.exp(shifted.astype(np.float64))
    return exp / exp.sum()


def entropy_of(probs: np.ndarray) -> float:
    return float(-(probs * np.log(np.maximum(probs, 1e-300))).sum())


def sha256_file(path: Path, chunk: int = 1 << 22) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def quant_name(tensor_type: int) -> str:
    from gguf.constants import GGMLQuantizationType as QType

    try:
        return QType(tensor_type).name
    except ValueError:
        return str(tensor_type)


def bits(x: float) -> float:
    return float(math.log2(max(x, 1e-300)))
