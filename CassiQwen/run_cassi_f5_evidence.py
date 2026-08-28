"""Run the bounded F5 evidence campaign.

The campaign deliberately separates transport/correctness receipts from model
quality claims.  It can score a live provider, but it never treats a missing
metric as a pass and it never writes residuals, logits, KV state, teacher
traces, or raw field arrays.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

try:
    from .cassi_f5_provider import CassiF5Provider, ProviderConfig
except ImportError:  # pragma: no cover - direct script execution
    from cassi_f5_provider import CassiF5Provider, ProviderConfig


PROTOCOL = "cassi.field-evidence.v2"
VERSION = 2
SUITE_VERSION = "f5-evidence-qi-v2-2026-08-23"
DEFAULT_N = 12
DEFAULT_MAX_TOKENS = 16
DEFAULT_TIMED_REPEATS = 3
BOOTSTRAP_SAMPLES = 2000
RNG_SEED = 20260823
FORBIDDEN_KEYS = {
    "residual",
    "logits",
    "kv",
    "kv_cache",
    "teacher_trace",
    "raw_wave",
    "field_array",
    "raw_field",
    "hidden_state",
}


@dataclass(frozen=True)
class EvidencePrompt:
    prompt_id: str
    category: str
    prompt: str
    expected_terms: tuple[str, ...]
    instruction: tuple[str, ...] = ()
    continuation: str = ""


PROMPTS: tuple[EvidencePrompt, ...] = (
    EvidencePrompt(
        "fact-orbit",
        "factuality",
        "Answer directly: what does Earth orbit?",
        ("sun",),
        continuation="Earth orbits the Sun.",
    ),
    EvidencePrompt(
        "fact-water",
        "factuality",
        "Answer directly: what is the chemical formula for water?",
        ("h2o",),
        continuation="The chemical formula for water is H2O.",
    ),
    EvidencePrompt(
        "fact-paris",
        "factuality",
        "Answer directly: what is the capital of France?",
        ("paris",),
        continuation="The capital of France is Paris.",
    ),
    EvidencePrompt(
        "fact-pacific",
        "factuality",
        "Answer directly: which ocean is the largest on Earth?",
        ("pacific",),
        continuation="The Pacific Ocean is the largest ocean on Earth.",
    ),
    EvidencePrompt(
        "instruction-terms",
        "instruction",
        "Write one short sentence containing the exact terms CASSI and FIELD. Do not use a numbered list.",
        (),
        ("CASSI", "FIELD", "one_sentence", "no_numbered_list"),
        continuation="CASSI FIELD is one controlled field experiment.",
    ),
    EvidencePrompt(
        "instruction-three",
        "instruction",
        "Return exactly three lines. Start the lines with FIRST, SECOND, and THIRD respectively.",
        (),
        ("three_lines", "FIRST", "SECOND", "THIRD"),
        continuation="FIRST\nSECOND\nTHIRD",
    ),
    EvidencePrompt(
        "instruction-json",
        "instruction",
        "Return one JSON object with the keys answer and confidence, and no Markdown fences.",
        (),
        ("json_object", "answer", "confidence", "no_fence"),
        continuation='{"answer":"stable orbit","confidence":0.9}',
    ),
    EvidencePrompt(
        "coherence-ada-bruno",
        "coherence",
        "Write a short paragraph about a team. Preserve these facts: Ada designs the experiment, Bruno checks the measurements, and the team records a reproducible result.",
        ("ada", "bruno", "experiment", "measurements", "reproducible"),
        ("entity_retention", "constraint_retention"),
        continuation="Ada designs the experiment while Bruno checks the measurements, and the team records a reproducible result.",
    ),
    EvidencePrompt(
        "coherence-orbit",
        "coherence",
        "Explain a stable orbit in several sentences. Keep the same subject, Earth, and mention gravity, the Sun, and a bound trajectory.",
        ("earth", "gravity", "sun", "bound"),
        ("entity_retention", "constraint_retention"),
        continuation="Earth remains in a bound trajectory because gravity provides the force associated with its orbit around the Sun.",
    ),
    EvidencePrompt(
        "task-classify",
        "task",
        "Classify this statement as TRUE or FALSE: water has the chemical formula H2O. Return only the label.",
        ("true",),
        ("single_label", "true_or_false"),
        continuation="TRUE",
    ),
    EvidencePrompt(
        "task-order",
        "task",
        "Return the numbers 1, 2, and 3 in ascending order separated by commas.",
        (),
        ("exact_sequence",),
        continuation="1, 2, 3",
    ),
    EvidencePrompt(
        "task-error",
        "task",
        "State one rule for reproducible software experiments. Keep the answer under twenty words.",
        ("configuration",),
        ("under_twenty_words",),
        continuation="Record the configuration and controls so another person can reproduce the result.",
    ),
)


def _finite(value: Any, label: str = "value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} is non-finite")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{label} has a non-string key")
            _finite(child, f"{label}.{key}")
        return
    if isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            _finite(child, f"{label}[{index}]")
        return
    raise ValueError(f"{label} has unsupported type {type(value).__name__}")


def _forbidden(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_KEYS:
                return normalized
            found = _forbidden(child)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for child in value:
            found = _forbidden(child)
            if found:
                return found
    return None


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    _finite(value, "receipt")
    found = _forbidden(value)
    if found:
        raise ValueError(f"receipt contains forbidden payload key {found}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(dict(value), sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with open(fd, "wb", closefd=True) as stream:
            stream.write(encoded)
            stream.flush()
        Path(temporary).replace(path)
        temporary = ""
    finally:
        if temporary:
            try:
                Path(temporary).unlink()
            except OSError:
                pass


def suite_digest(prompts: Sequence[EvidencePrompt] = PROMPTS) -> str:
    payload = [
        {
            "id": item.prompt_id,
            "category": item.category,
            "prompt": item.prompt,
            "expected_terms": item.expected_terms,
            "instruction": item.instruction,
            "continuation": item.continuation,
        }
        for item in prompts
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    return " ".join(text.lower().replace("\n", " ").split())


def score_factuality(text: str, expected_terms: Sequence[str]) -> dict[str, Any]:
    normalized = normalize_text(text)
    hits = [term for term in expected_terms if term.lower() in normalized]
    score = len(hits) / float(len(expected_terms)) if expected_terms else 0.0
    return {"score": score, "matched": hits, "required": list(expected_terms), "finite": True}


def score_instruction(text: str, requirements: Sequence[str]) -> dict[str, Any]:
    raw_lines = [line for line in text.splitlines() if line.strip()]
    normalized = normalize_text(text)
    checks: dict[str, bool] = {}
    for requirement in requirements:
        if requirement == "CASSI":
            checks[requirement] = "cassi" in normalized
        elif requirement == "FIELD":
            checks[requirement] = "field" in normalized
        elif requirement == "one_sentence":
            checks[requirement] = len([part for part in text.replace("!", ".").replace("?", ".").split(".") if part.strip()]) <= 1
        elif requirement == "no_numbered_list":
            checks[requirement] = not any(line.lstrip()[:2].rstrip(".").isdigit() for line in raw_lines)
        elif requirement == "three_lines":
            checks[requirement] = len(raw_lines) == 3
        elif requirement in {"FIRST", "SECOND", "THIRD"}:
            index = {"FIRST": 0, "SECOND": 1, "THIRD": 2}[requirement]
            checks[requirement] = len(raw_lines) > index and raw_lines[index].startswith(requirement)
        elif requirement == "json_object":
            try:
                parsed = json.loads(text)
                checks[requirement] = isinstance(parsed, dict)
            except (ValueError, TypeError):
                checks[requirement] = False
        elif requirement == "answer":
            try:
                checks[requirement] = "answer" in json.loads(text)
            except (ValueError, TypeError):
                checks[requirement] = False
        elif requirement == "confidence":
            try:
                checks[requirement] = "confidence" in json.loads(text)
            except (ValueError, TypeError):
                checks[requirement] = False
        elif requirement == "no_fence":
            checks[requirement] = "```" not in text
        elif requirement == "single_label":
            checks[requirement] = len(normalized.split()) == 1
        elif requirement == "true_or_false":
            checks[requirement] = normalized.strip() in {"true", "false"}
        elif requirement == "exact_sequence":
            checks[requirement] = normalized.replace(" ", "") == "1,2,3"
        elif requirement == "under_twenty_words":
            checks[requirement] = len(normalized.split()) < 20
        else:
            checks[requirement] = False
    score = sum(checks.values()) / float(len(checks)) if checks else 0.0
    return {"score": score, "checks": checks, "finite": True}


def score_coherence(text: str, required_terms: Sequence[str]) -> dict[str, Any]:
    normalized = normalize_text(text)
    hits = [term for term in required_terms if term.lower() in normalized]
    entity_score = len(hits) / float(len(required_terms)) if required_terms else 0.0
    words = normalized.split()
    unique_ratio = len(set(words)) / float(len(words)) if words else 0.0
    return {
        "score": entity_score,
        "entity_retention": entity_score,
        "unique_word_ratio": unique_ratio,
        "matched": hits,
        "required": list(required_terms),
        "finite": True,
    }


def _mean(values: Sequence[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def bootstrap_mean_ci(values: Sequence[float], *, seed: int = RNG_SEED, samples: int = BOOTSTRAP_SAMPLES) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "lower": 0.0, "upper": 0.0}
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(samples):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / float(n))
    means.sort()
    lower_index = max(0, int(0.025 * samples) - 1)
    upper_index = min(samples - 1, int(0.975 * samples))
    return {
        "mean": _mean(values),
        "lower": float(means[lower_index]),
        "upper": float(means[upper_index]),
    }


def exact_sign_test(values: Sequence[float]) -> dict[str, Any]:
    positive = sum(value > 0 for value in values)
    negative = sum(value < 0 for value in values)
    tied = len(values) - positive - negative
    effective = positive + negative
    if effective == 0:
        p_value = 1.0
    else:
        smaller = min(positive, negative)
        p_value = min(1.0, 2.0 * sum(math.comb(effective, i) for i in range(smaller + 1)) / float(2**effective))
    return {
        "positive": positive,
        "negative": negative,
        "tied": tied,
        "effective_n": effective,
        "p_value_two_sided": float(p_value),
        "finite": True,
    }


def verdict_from_deltas(deltas: Sequence[float], ci: Mapping[str, float], *, alpha: float = 0.05) -> str:
    if not deltas:
        return "INCONCLUSIVE"
    if float(ci["lower"]) > 0.0 and _mean(deltas) > 0.0:
        return "SUPPORTS"
    if float(ci["upper"]) < 0.0 and _mean(deltas) < 0.0:
        return "CONTRADICTS"
    if abs(_mean(deltas)) < 1.0e-12:
        return "DOES NOT EMERGE"
    return "INCONCLUSIVE"


def blind_packet(
    paired: Sequence[Mapping[str, Any]],
    *,
    seed: int = RNG_SEED,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(seed)
    packet: list[dict[str, Any]] = []
    answer_key: list[dict[str, Any]] = []
    for item in paired:
        field_first = bool(rng.randrange(2))
        label_a = "field" if field_first else "baseline"
        label_b = "baseline" if field_first else "field"
        packet.append(
            {
                "prompt_id": item["prompt_id"],
                "prompt": item["prompt"],
                "A": item[label_a],
                "B": item[label_b],
            }
        )
        answer_key.append({"prompt_id": item["prompt_id"], "A": label_a, "B": label_b})
    return packet, answer_key


def _response_text(response: Mapping[str, Any]) -> str:
    try:
        return str(response["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"provider response lacks chat text: {exc}") from exc


def _call(provider: CassiF5Provider, prompt: EvidencePrompt, mode: str, session: str, max_tokens: int) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    response = provider.complete(
        {
            "messages": [{"role": "user", "content": prompt.prompt}],
            "max_tokens": max_tokens,
            "temperature": 0,
            "user": session,
            "cassi_field_mode": mode,
        }
    )
    elapsed = time.perf_counter() - started
    return response, elapsed


def _quality_record(prompt: EvidencePrompt, text: str) -> dict[str, Any]:
    if prompt.category == "factuality":
        scored = score_factuality(text, prompt.expected_terms)
    elif prompt.category == "instruction":
        scored = score_instruction(text, prompt.instruction)
    elif prompt.category == "coherence":
        scored = score_coherence(text, prompt.expected_terms)
    else:
        scored = score_instruction(text, prompt.instruction) if prompt.instruction else score_factuality(text, prompt.expected_terms)
    return {"prompt_id": prompt.prompt_id, "category": prompt.category, **scored}


def teacher_forced_nll(provider: CassiF5Provider, prompt: EvidencePrompt) -> dict[str, Any]:
    """Compute ordinary-Qwen teacher-forced NLL when the runtime exposes it.

    The field reranker changes selected tokens, not the underlying Qwen logits.
    Therefore a true field-conditioned teacher-forced perplexity requires the
    native graph path; this receipt explicitly distinguishes that limitation.
    """

    runtime = getattr(provider, "_runtime", None)
    if runtime is None or not prompt.continuation:
        return {"verdict": "NOT_MEASURED", "reason": "runtime or continuation unavailable", "finite": True}
    try:
        runtime.reset_context()
        prompt_ids = runtime.tokenize(prompt.prompt)
        continuation_ids = runtime.tokenize(prompt.continuation)
        if not prompt_ids or not continuation_ids:
            return {"verdict": "NOT_MEASURED", "reason": "tokenization produced no tokens", "finite": True}
        record = runtime.decode_initial(prompt_ids)
        nll = 0.0
        token_count = 0
        for token_id in continuation_ids:
            logits = np.asarray(record.ordinary_logits, dtype=np.float64)
            if token_id < 0 or token_id >= logits.size or not np.isfinite(logits).all():
                return {"verdict": "NOT_MEASURED", "reason": "invalid runtime logits", "finite": True}
            maximum = float(np.max(logits))
            log_norm = maximum + math.log(float(np.exp(logits - maximum).sum()))
            nll -= float(logits[token_id] - log_norm)
            token_count += 1
            record = runtime.decode_token(int(token_id), record.final_position + 1)
        mean_nll = nll / float(token_count)
        return {
            "verdict": "MEASURED_BASELINE_ONLY",
            "baseline_mean_nll": mean_nll,
            "baseline_perplexity": float(math.exp(min(50.0, mean_nll))),
            "token_count": token_count,
            "field_teacher_forced_verdict": "NOT_APPLICABLE_WITH_LOGIT_RERANKER",
            "finite": True,
        }
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError, OverflowError) as exc:
        return {"verdict": "NOT_MEASURED", "reason": f"runtime NLL unavailable: {type(exc).__name__}", "finite": True}


def _timing_summary(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rates = [float(item["tokens_per_second"]) for item in samples if float(item["tokens_per_second"]) > 0.0]
    elapsed = [float(item["elapsed_seconds"]) for item in samples]
    if not rates:
        return {"count": 0, "verdict": "NOT_MEASURED", "finite": True}
    return {
        "count": len(rates),
        "mean_tokens_per_second": _mean(rates),
        "median_tokens_per_second": float(statistics.median(rates)),
        "min_tokens_per_second": min(rates),
        "max_tokens_per_second": max(rates),
        "mean_elapsed_seconds": _mean(elapsed),
        "verdict": "MEASURED",
        "finite": True,
    }


def run_evidence(
    provider: CassiF5Provider,
    *,
    n: int = DEFAULT_N,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timed_repeats: int = DEFAULT_TIMED_REPEATS,
    packet_dir: Path | None = None,
    seed: int = RNG_SEED,
) -> dict[str, Any]:
    if not 1 <= n <= len(PROMPTS):
        raise ValueError(f"n must be in [1, {len(PROMPTS)}]")
    if not 1 <= max_tokens <= 64:
        raise ValueError("max_tokens must be in [1, 64]")
    if not 1 <= timed_repeats <= 16:
        raise ValueError("timed_repeats must be in [1, 16]")
    selected = PROMPTS[:n]
    paired: list[dict[str, Any]] = []
    category_records: dict[str, list[dict[str, Any]]] = {}
    for prompt in selected:
        baseline_response, baseline_elapsed = _call(provider, prompt, "baseline", f"evidence-b-{prompt.prompt_id}", max_tokens)
        field_response, field_elapsed = _call(provider, prompt, "field", f"evidence-f-{prompt.prompt_id}", max_tokens)
        baseline_text = _response_text(baseline_response)
        field_text = _response_text(field_response)
        baseline_score = _quality_record(prompt, baseline_text)
        field_score = _quality_record(prompt, field_text)
        category_records.setdefault(prompt.category, []).append(
            {
                "prompt_id": prompt.prompt_id,
                "baseline": baseline_score,
                "field": field_score,
                "baseline_elapsed_seconds": baseline_elapsed,
                "field_elapsed_seconds": field_elapsed,
                "baseline_tokens": int(baseline_response.get("usage", {}).get("completion_tokens", 0)),
                "field_tokens": int(field_response.get("usage", {}).get("completion_tokens", 0)),
            }
        )
        paired.append({
            "prompt_id": prompt.prompt_id,
            "prompt": prompt.prompt,
            "baseline": baseline_text,
            "field": field_text,
            "baseline_score": float(baseline_score["score"]),
            "field_score": float(field_score["score"]),
        })
    paired_deltas = [float(item["field_score"]) - float(item["baseline_score"]) for item in paired]
    ci = bootstrap_mean_ci(paired_deltas, seed=seed)
    sign = exact_sign_test(paired_deltas)
    paired_stats = {
        "n": len(paired_deltas),
        "fixed_n": n,
        "deltas": paired_deltas,
        "bootstrap_mean_ci": ci,
        "sign_test": sign,
        "verdict": verdict_from_deltas(paired_deltas, ci),
        "finite": True,
    }
    category_summary: dict[str, Any] = {}
    for category, records in category_records.items():
        deltas = [float(record["field"]["score"]) - float(record["baseline"]["score"]) for record in records]
        category_ci = bootstrap_mean_ci(deltas, seed=seed + len(category))
        category_summary[category] = {
            "n": len(records),
            "baseline_mean": _mean([float(record["baseline"]["score"]) for record in records]),
            "field_mean": _mean([float(record["field"]["score"]) for record in records]),
            "delta_ci": category_ci,
            "verdict": verdict_from_deltas(deltas, category_ci),
            "finite": True,
        }
    timing: dict[str, Any] = {}
    timing_prompt = selected[0]
    for mode in ("baseline", "field"):
        samples: list[dict[str, Any]] = []
        for repeat in range(timed_repeats):
            response, elapsed = _call(provider, timing_prompt, mode, f"timing-{mode}-{repeat}", max_tokens)
            tokens = int(response.get("usage", {}).get("completion_tokens", 0))
            samples.append({
                "elapsed_seconds": elapsed,
                "completion_tokens": tokens,
                "tokens_per_second": tokens / elapsed if elapsed > 0.0 else 0.0,
            })
        timing[mode] = _timing_summary(samples)
    nll = teacher_forced_nll(provider, selected[0])
    packet, answer_key = blind_packet(paired, seed=seed)
    packet_hash = hashlib.sha256(json.dumps(packet, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    answer_hash = hashlib.sha256(json.dumps(answer_key, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    packet_receipt = {
        "status": "PENDING_HUMAN_SCORE",
        "packet_sha256": packet_hash,
        "answer_key_sha256": answer_hash,
        "count": len(packet),
        "blind_seed": seed,
        "finite": True,
    }
    if packet_dir is not None:
        packet_dir.mkdir(parents=True, exist_ok=True)
        _atomic_json(packet_dir / "f5-human-preference-packet.json", {"protocol": PROTOCOL, "version": VERSION, "suite": SUITE_VERSION, "packet": packet})
        _atomic_json(packet_dir / "f5-human-preference-answer-key.json", {"protocol": PROTOCOL, "version": VERSION, "suite": SUITE_VERSION, "answer_key": answer_key})
    provider_health = provider.health()
    receipt = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "suite": SUITE_VERSION,
        "suite_sha256": suite_digest(selected),
        "seed": seed,
        "n": len(selected),
        "max_tokens": max_tokens,
        "timed_repeats": timed_repeats,
        "provider": {
            "protocol": provider_health.get("protocol"),
            "profile": provider_health.get("profile"),
            "field_protocol": provider_health.get("field_protocol"),
            "field_profile": provider_health.get("field_profile"),
            "field_enabled": provider_health.get("field_enabled"),
            "qi_gated": provider_health.get("qi_gated"),
            "field_weight": provider.config.field_weight,
        },
        "timing": timing,
        "perplexity": nll,
        "categories": category_summary,
        "paired_task_benchmark": paired_stats,
        "human_preference": packet_receipt,
        "persistence_and_transport": {
            "field_execution": provider_health.get("field_protocol"),
            "field_profile": provider_health.get("field_profile"),
            "teacher_data_persisted": False,
            "finite": True,
        },
        "finite": True,
    }
    _finite(receipt, "evidence receipt")
    found = _forbidden(receipt)
    if found:
        raise ValueError(f"evidence receipt contains forbidden key {found}")
    return receipt


def build_parser() -> argparse.ArgumentParser:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=here / "Qwen3.8-27B-Q4_K_M.gguf")
    parser.add_argument("--dll-dir", type=Path, default=here)
    parser.add_argument("--state-dir", type=Path, default=here / "_diag" / "f5-evidence-state")
    parser.add_argument("--field-host", default="127.0.0.1")
    parser.add_argument("--field-port", type=int, default=7600)
    parser.add_argument("--context-size", type=int, default=128)
    parser.add_argument("--n-batch", type=int, default=64)
    parser.add_argument("--n-ubatch", type=int, default=64)
    parser.add_argument("--gpu-layers", type=int, default=24)
    parser.add_argument("--field-weight", type=float, default=0.25)
    parser.add_argument("--layer-index", type=int, default=32)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--timed-repeats", type=int, default=DEFAULT_TIMED_REPEATS)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--seed", type=int, default=RNG_SEED)
    parser.add_argument("--output", type=Path, default=here / "_diag" / "f5" / "f5-evidence.json")
    parser.add_argument("--packet-dir", type=Path, default=here / "_diag" / "f5" / "human")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    config = ProviderConfig(
        model_path=args.model,
        dll_dir=args.dll_dir,
        state_dir=args.state_dir,
        field_host=args.field_host,
        field_port=args.field_port,
        context_size=args.context_size,
        n_batch=args.n_batch,
        n_ubatch=args.n_ubatch,
        gpu_layers=args.gpu_layers,
        max_tokens=args.max_tokens,
        field_weight=args.field_weight,
        layer_index=args.layer_index,
        enable_f5=True,
    )
    provider = CassiF5Provider(config)
    started = time.perf_counter()
    try:
        provider.start()
        receipt = run_evidence(
            provider,
            n=args.n,
            max_tokens=args.max_tokens,
            timed_repeats=args.timed_repeats,
            packet_dir=args.packet_dir,
            seed=args.seed,
        )
        receipt["elapsed_seconds_including_start"] = time.perf_counter() - started
        _atomic_json(args.output, receipt)
        print(json.dumps(receipt, sort_keys=True, ensure_ascii=False))
        return 0
    finally:
        provider.close()


__all__ = [
    "EvidencePrompt",
    "PROMPTS",
    "blind_packet",
    "bootstrap_mean_ci",
    "exact_sign_test",
    "main",
    "normalize_text",
    "run_evidence",
    "score_coherence",
    "score_factuality",
    "score_instruction",
    "suite_digest",
    "teacher_forced_nll",
    "verdict_from_deltas",
]


if __name__ == "__main__":
    raise SystemExit(main())
