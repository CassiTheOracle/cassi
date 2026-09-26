#!/usr/bin/env python3
"""Measure next-token sensitivity to a token at several distances back.

The measurement uses the local ctypes llama.cpp adapter and compares complete
vocabulary logits, rather than generated text or a top-k approximation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np

HERE = Path(__file__).resolve()
CASSIQWEN = HERE.parents[1]
REPO_ROOT = CASSIQWEN.parent
sys.path.insert(0, str(HERE.parent))
from cassi_llama_capture import NativeLlamaSession  # noqa: E402

DEFAULT_DISTANCES = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
DEFAULT_MODEL = CASSIQWEN / "Qwen3.5-0.8B-Q4_0.gguf"
DEFAULT_OUTPUT = REPO_ROOT / "CassiQwen" / "_diag" / "field-memory-study" / "distance-profile.json"
DEFAULT_SOURCE = CASSIQWEN / "README.md"
DEFAULT_RUNTIME = CASSIQWEN / "native" / "llama.cpp" / "b8" / "bin" / "Release"


def clean_source(text: str) -> str:
    """Remove enough Markdown decoration to leave a natural-language stream."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-+*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\|", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_prompts(session: NativeLlamaSession, source: Path, count: int, words_per_prompt: int) -> list[tuple[str, list[int]]]:
    words = clean_source(source.read_text(encoding="utf-8", errors="replace")).split()
    if len(words) < count * words_per_prompt:
        raise RuntimeError(f"source has only {len(words)} words; need at least {count * words_per_prompt}")
    max_start = len(words) - words_per_prompt
    starts = np.linspace(0, max_start, count, dtype=int).tolist()
    prompts: list[tuple[str, list[int]]] = []
    for start in starts:
        end = start + words_per_prompt
        text = " ".join(words[start:end])
        tokens = session._tokenize(text)  # native tokenizer, including BOS
        # Keep a generous but bounded context while guaranteeing the requested length.
        if len(tokens) < 600:
            text = " ".join(words[start : min(len(words), start + words_per_prompt + 180)])
            tokens = session._tokenize(text)
        if len(tokens) < 600:
            raise RuntimeError(f"prompt starting at word {start} has only {len(tokens)} model tokens")
        if len(tokens) > session.context_tokens:
            tokens = tokens[: session.context_tokens]
        prompts.append((text, tokens))
    return prompts


def replacement_token(original: int, vocab_size: int, seed: int, prompt_index: int, position: int, distance: int) -> int:
    """Choose a reproducible ordinary-vocabulary token distinct from the source."""
    # Keep clear of the low special-token range and the high Qwen control-token range.
    ordinary = max(256, min(vocab_size - 2, 1000))
    upper = max(ordinary + 1, vocab_size - 1024)
    span = upper - ordinary
    if span <= 1:
        ordinary = 1
        upper = vocab_size
        span = upper - ordinary
    payload = f"{seed}:{prompt_index}:{position}:{distance}:{original}".encode("ascii")
    offset = int.from_bytes(hashlib.sha256(payload).digest()[:8], "little") % span
    candidate = ordinary + offset
    if candidate == original:
        candidate = ordinary + ((offset + 1) % span)
    return int(candidate)


def softmax_log_probs(logits: np.ndarray) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float64)
    shifted = values - float(np.max(values))
    log_z = float(np.log(np.exp(shifted).sum()))
    return shifted - log_z


def kl_original_to_perturbed(original: np.ndarray, perturbed: np.ndarray) -> float:
    log_p = softmax_log_probs(original)
    log_q = softmax_log_probs(perturbed)
    p = np.exp(log_p)
    value = float(np.sum(p * (log_p - log_q)))
    # Tiny negative values can result from floating-point summation only.
    return max(0.0, value)


def sampled_positions(length: int, distance: int, max_positions: int) -> list[int]:
    # p is the prediction position; p-distance is the token being replaced.
    low = max(distance + 1, 1)  # do not perturb the BOS row
    high = length - 1
    if high < low:
        return []
    count = min(max_positions, high - low + 1)
    if count == 1:
        return [high]
    return sorted(set(np.linspace(low, high, count, dtype=int).tolist()))


def forward_tokens(session: NativeLlamaSession, tokens: list[int]) -> np.ndarray:
    params = session._params(
        layer=session.layer_count - 1,
        displacement=0,
        injection_scale=0.0,
        substitute=0.0,
        field_enabled=False,
    )
    context = session._new_context(params)
    try:
        return session._decode_logits(context, tokens)
    finally:
        session.lib.llama_free(context)


def run(args: argparse.Namespace) -> dict[str, object]:
    started = time.perf_counter()
    model = Path(args.model).resolve()
    source = Path(args.source).resolve()
    runtime = Path(args.runtime).resolve()
    output = Path(args.output).resolve()
    distances = tuple(int(value) for value in args.distances)
    with NativeLlamaSession(runtime, model, gpu_layers=args.gpu_layers, context_tokens=args.context_tokens) as session:
        prompts = make_prompts(session, source, args.prompts, args.words_per_prompt)
        original_cache: dict[tuple[int, int], np.ndarray] = {}
        values_by_distance: dict[int, list[float]] = {distance: [] for distance in distances}
        observations = 0
        for prompt_index, (_text, tokens) in enumerate(prompts):
            for distance in distances:
                positions = sampled_positions(len(tokens), distance, args.positions)
                for position in positions:
                    key = (prompt_index, position)
                    original = original_cache.get(key)
                    if original is None:
                        original = forward_tokens(session, tokens[: position + 1])
                        original_cache[key] = original
                    changed = list(tokens[: position + 1])
                    source_index = position - distance
                    old_token = changed[source_index]
                    changed[source_index] = replacement_token(
                        old_token,
                        session.vocabulary_size,
                        args.seed,
                        prompt_index,
                        position,
                        distance,
                    )
                    perturbed = forward_tokens(session, changed)
                    values_by_distance[distance].append(kl_original_to_perturbed(original, perturbed))
                    observations += 1
                print(f"prompt {prompt_index + 1}/{len(prompts)} distance {distance}: {len(positions)} positions", flush=True)

        means: list[float] = []
        stderrs: list[float] = []
        for distance in distances:
            values = np.asarray(values_by_distance[distance], dtype=np.float64)
            if values.size == 0:
                raise RuntimeError(f"distance {distance} produced no observations")
            means.append(float(values.mean()))
            stderrs.append(float(values.std(ddof=1) / math.sqrt(values.size)) if values.size > 1 else 0.0)
        baseline = means[0]
        normalized = [float(value / baseline) if baseline > 0 else 0.0 for value in means]
        elapsed = time.perf_counter() - started
        result: dict[str, object] = {
            "model": model.name,
            "method": "For sampled prediction positions in native llama.cpp prefixes, replace the token distance a back with a deterministic ordinary-vocabulary token and measure full-vocabulary KL(original || perturbed) next-token logits.",
            "distances": list(distances),
            "divergence": means,
            "divergence_stderr": stderrs,
            "observations": observations,
            "normalized": normalized,
            "notes": (
                f"{model.name} scope; {len(prompts)} prompts of at least 600 native tokens from {source.name}; "
                f"{args.positions} evenly spaced prediction positions sampled per prompt/distance (BOS excluded); "
                "replacement IDs are deterministic SHA-256 selections from token IDs in [256, vocab_size-1024); "
                "full logits came from the read-only ctypes NativeLlamaSession path using the local Vulkan runtime; "
                f"runtime_seconds={elapsed:.3f}."
            ),
            "source": source.name,
            "prompt_count": len(prompts),
            "positions_per_prompt_distance_max": args.positions,
            "seed": args.seed,
            "runtime_seconds": elapsed,
            "runtime_dir": str(runtime),
            "context_tokens": args.context_tokens,
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--prompts", type=int, default=8)
    parser.add_argument("--words-per-prompt", type=int, default=760)
    parser.add_argument("--positions", type=int, default=8)
    parser.add_argument("--context-tokens", type=int, default=4096)
    parser.add_argument("--gpu-layers", type=int, default=99)
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--distances", type=int, nargs="+", default=list(DEFAULT_DISTANCES))
    return parser.parse_args()


if __name__ == "__main__":
    result = run(parse_args())
    print(json.dumps({key: result[key] for key in ("model", "distances", "divergence", "divergence_stderr", "observations", "runtime_seconds")}, indent=2))
