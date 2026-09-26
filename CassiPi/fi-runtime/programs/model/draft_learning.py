"""Field-owned learned multi-token draft policy.

This module contains only bounded, deterministic policy transitions.  It does
not execute a model, own a KV cache, sample target logits, or retain a Python
sidecar.  A caller places the returned mapping in the model task's canonical
field state (``resident_model.policies.drafting``) and stores an in-flight
proposal in that task state while the target model is sampled once.

The first useful draft is earned from target observations.  A context
continuation is represented as a canonical method record; no host callable or
trained draft model is hidden behind the API.  The target model remains the
source of truth: ``target_sample_and_compare`` consumes one already sampled
target trajectory, commits only its matched prefix plus the first rejection
sample, and reports the speculative suffix/RNG restoration contract to the
mechanical executor.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import json
import math

from programs.python.records import canonical_json_bytes, digest_value


DRAFT_POLICY_SCHEMA = "cassifi.model-draft-policy.v1"
DRAFT_PROPOSAL_SCHEMA = "cassifi.model-draft-proposal.v1"
DRAFT_COMPARISON_SCHEMA = "cassifi.model-draft-comparison.v1"
DRAFT_SPECULATION_SCHEMA = "cassifi.model-speculation.v1"
DRAFT_OBSERVATION_SCHEMA = "cassifi.model-draft-observation.v1"

MAX_CONTEXT_WIDTH = 8
MAX_HORIZON = 8
MAX_METHODS = 8
MAX_ROWS_PER_METHOD = 256
MAX_NEXT_PER_ROW = 8
MAX_HISTORY = 64
MAX_TOKEN = (1 << 31) - 1
MAX_COST_UNITS = (1 << 63) - 1


class DraftLearningError(ValueError):
    """A draft policy, proposal, or observation is not canonical."""


def _plain(value: Any) -> Any:
    try:
        return json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise DraftLearningError("draft value is not canonical JSON") from exc


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise DraftLearningError(f"{label} must be nonempty text")
    if len(value.encode("utf-8")) > 65_536:
        raise DraftLearningError(f"{label} is too large")
    return value


def _digest(value: Any, label: str) -> str:
    text = _text(value, label)
    if len(text) != 64:
        raise DraftLearningError(f"{label} must be a SHA-256 digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise DraftLearningError(f"{label} must be a SHA-256 digest") from exc
    return text.lower()


def _integer(value: Any, label: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise DraftLearningError(f"{label} must be an integer >= {minimum}")
    if maximum is not None and value > maximum:
        raise DraftLearningError(f"{label} exceeds its bound")
    return int(value)


def _token(value: Any, label: str = "token") -> int:
    return _integer(value, label, maximum=MAX_TOKEN)


def _tokens(value: Any, label: str, *, allow_empty: bool = True, maximum: int = 65_536) -> list[int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DraftLearningError(f"{label} must be a token sequence")
    if not allow_empty and not value:
        raise DraftLearningError(f"{label} cannot be empty")
    if len(value) > maximum:
        raise DraftLearningError(f"{label} exceeds its bound")
    return [_token(item, f"{label} token") for item in value]


def _bounded_cost(value: Any, label: str) -> int:
    return _integer(value, label, maximum=MAX_COST_UNITS)


def _model_identity(policy: Mapping[str, Any]) -> Mapping[str, str]:
    model = policy.get("model")
    if not isinstance(model, Mapping):
        raise DraftLearningError("draft policy model identity is missing")
    return {
        "program_id": _text(model.get("program_id"), "model program_id"),
        "source_sha256": _digest(model.get("source_sha256"), "model source_sha256"),
    }


def _context_key(context: Sequence[int]) -> tuple[int, ...]:
    return tuple(int(item) for item in context)


def _canonical_next(values: Any) -> list[dict[str, int]]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise DraftLearningError("continuation next values must be a sequence")
    by_token: dict[int, int] = {}
    for item in values:
        if not isinstance(item, Mapping):
            raise DraftLearningError("continuation next value must be a mapping")
        token = _token(item.get("token"), "continuation token")
        count = _integer(item.get("count"), "continuation count", minimum=1, maximum=MAX_COST_UNITS)
        by_token[token] = by_token.get(token, 0) + count
    if len(by_token) > MAX_NEXT_PER_ROW:
        raise DraftLearningError("continuation row exceeds its next-token bound")
    return [{"token": token, "count": by_token[token]} for token in sorted(by_token)]


def _canonical_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DraftLearningError("continuation rows must be a sequence")
    if len(value) > MAX_ROWS_PER_METHOD:
        raise DraftLearningError("continuation method exceeds its row bound")
    rows: dict[tuple[int, ...], list[dict[str, int]]] = {}
    for raw in value:
        if not isinstance(raw, Mapping):
            raise DraftLearningError("continuation row must be a mapping")
        context = tuple(_tokens(raw.get("context", ()), "continuation context", maximum=MAX_CONTEXT_WIDTH))
        if not context:
            raise DraftLearningError("continuation context cannot be empty")
        next_values = _canonical_next(raw.get("next", ()))
        if not next_values:
            raise DraftLearningError("continuation row cannot be empty")
        if context in rows:
            merged = rows[context] + next_values
            rows[context] = _canonical_next(merged)
        else:
            rows[context] = next_values
    ordered = []
    for context in sorted(rows):
        ordered.append({"context": list(context), "next": rows[context]})
    return ordered


def _canonical_method(value: Any, *, max_horizon: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DraftLearningError("draft method must be a mapping")
    method_id = _text(value.get("method_id"), "draft method_id")
    kind = _text(value.get("kind", "context-continuation"), "draft method kind")
    if kind != "context-continuation":
        raise DraftLearningError("unsupported draft method kind")
    width = _integer(value.get("context_width"), "draft context_width", minimum=1, maximum=MAX_CONTEXT_WIDTH)
    horizon = _integer(value.get("horizon", 1), "draft horizon", minimum=1, maximum=max_horizon)
    rows = _canonical_rows(value.get("rows", ()))
    if any(len(row["context"]) != width for row in rows):
        raise DraftLearningError("continuation row width does not match its method")
    method = {
        "method_id": method_id,
        "kind": kind,
        "origin": _text(value.get("origin", "field-observation"), "draft method origin"),
        "context_width": width,
        "horizon": horizon,
        "rows": rows,
        "attempts": _integer(value.get("attempts", 0), "draft attempts", maximum=MAX_COST_UNITS),
        "accepted_tokens": _integer(value.get("accepted_tokens", 0), "accepted token count", maximum=MAX_COST_UNITS),
        "rejected_tokens": _integer(value.get("rejected_tokens", 0), "rejected token count", maximum=MAX_COST_UNITS),
        "target_tokens": _integer(value.get("target_tokens", 0), "target token count", maximum=MAX_COST_UNITS),
        "target_cost_units": _bounded_cost(value.get("target_cost_units", 0), "target cost units"),
        "draft_cost_units": _bounded_cost(value.get("draft_cost_units", 0), "draft cost units"),
        "full_accepts": _integer(value.get("full_accepts", 0), "full accept count", maximum=MAX_COST_UNITS),
    }
    if method["accepted_tokens"] + method["rejected_tokens"] > MAX_COST_UNITS:
        raise DraftLearningError("draft method outcome counters overflow")
    if method["target_tokens"] < method["accepted_tokens"]:
        raise DraftLearningError("draft method target counter is inconsistent")
    return method


def _canonical_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("schema") != DRAFT_POLICY_SCHEMA:
        raise DraftLearningError("draft policy schema is invalid")
    model = _model_identity(value)
    config_raw = value.get("config")
    if not isinstance(config_raw, Mapping):
        raise DraftLearningError("draft policy config is missing")
    max_horizon = _integer(config_raw.get("max_horizon"), "max_horizon", minimum=1, maximum=MAX_HORIZON)
    max_context_width = _integer(config_raw.get("max_context_width"), "max_context_width", minimum=1, maximum=MAX_CONTEXT_WIDTH)
    max_methods = _integer(config_raw.get("max_methods"), "max_methods", minimum=1, maximum=MAX_METHODS)
    min_support = _integer(config_raw.get("min_support", 1), "min_support", minimum=1, maximum=MAX_COST_UNITS)
    min_confidence = float(config_raw.get("min_confidence", 0.5))
    if not math.isfinite(min_confidence) or not 0.0 < min_confidence <= 1.0:
        raise DraftLearningError("min_confidence must be in (0, 1]")
    cost_unit = _text(config_raw.get("cost_unit", "executor-reported-units"), "cost unit")
    config = {
        "max_horizon": max_horizon,
        "max_context_width": max_context_width,
        "max_methods": max_methods,
        "min_support": min_support,
        "min_confidence": min_confidence,
        "cost_unit": cost_unit,
    }
    methods_raw = value.get("methods", ())
    if isinstance(methods_raw, (str, bytes)) or not isinstance(methods_raw, Sequence):
        raise DraftLearningError("draft methods must be a sequence")
    if len(methods_raw) > max_methods:
        raise DraftLearningError("draft policy has too many methods")
    methods = [_canonical_method(item, max_horizon=max_horizon) for item in methods_raw]
    ids = [item["method_id"] for item in methods]
    if len(ids) != len(set(ids)):
        raise DraftLearningError("draft method identity is duplicated")
    history_raw = value.get("history", ())
    if isinstance(history_raw, (str, bytes)) or not isinstance(history_raw, Sequence) or len(history_raw) > MAX_HISTORY:
        raise DraftLearningError("draft history is invalid or too large")
    history = [_plain(item) for item in history_raw]
    if any(not isinstance(item, Mapping) for item in history):
        raise DraftLearningError("draft history rows must be mappings")
    mtp_raw = value.get("pretrained_mtp")
    if not isinstance(mtp_raw, Mapping):
        raise DraftLearningError("pretrained_mtp declaration is missing")
    mtp_available_raw = mtp_raw.get("available", False)
    if not isinstance(mtp_available_raw, bool):
        raise DraftLearningError("MTP availability must be boolean")
    mtp_available = mtp_available_raw
    mtp_head_id_raw = mtp_raw.get("head_id")
    if mtp_available and mtp_head_id_raw is None:
        raise DraftLearningError("available pretrained MTP requires a head identity")
    if not mtp_available and mtp_head_id_raw is not None:
        raise DraftLearningError("unavailable pretrained MTP cannot name a head")
    mtp = {
        "available": mtp_available,
        "head_id": None if mtp_head_id_raw is None else _text(mtp_head_id_raw, "MTP head_id"),
        "source": _text(mtp_raw.get("source", "gguf-metadata"), "MTP source"),
        "reason": _text(mtp_raw.get("reason", "no admitted pretrained MTP head"), "MTP reason"),
    }
    policy = {
        "schema": DRAFT_POLICY_SCHEMA,
        "model": model,
        "owner_id": _text(value.get("owner_id", "owner"), "draft owner_id"),
        "version": _integer(value.get("version", 0), "draft policy version", maximum=MAX_COST_UNITS),
        "config": config,
        "pretrained_mtp": mtp,
        "methods": methods,
        "active_method_id": None if value.get("active_method_id") is None else _text(value.get("active_method_id"), "active method_id"),
        "attempts": _integer(value.get("attempts", 0), "draft attempts", maximum=MAX_COST_UNITS),
        "accepted_tokens": _integer(value.get("accepted_tokens", 0), "accepted token count", maximum=MAX_COST_UNITS),
        "rejected_tokens": _integer(value.get("rejected_tokens", 0), "rejected token count", maximum=MAX_COST_UNITS),
        "target_tokens": _integer(value.get("target_tokens", 0), "target token count", maximum=MAX_COST_UNITS),
        "target_cost_units": _bounded_cost(value.get("target_cost_units", 0), "target cost units"),
        "draft_cost_units": _bounded_cost(value.get("draft_cost_units", 0), "draft cost units"),
        "history": history,
    }
    if policy["accepted_tokens"] + policy["rejected_tokens"] > MAX_COST_UNITS:
        raise DraftLearningError("draft policy outcome counters overflow")
    if policy["active_method_id"] is not None and policy["active_method_id"] not in ids:
        raise DraftLearningError("active draft method is not resident")
    return _plain(policy)


def initial_policy(
    *,
    model_program_id: str,
    source_sha256: str,
    owner_id: str = "owner",
    max_horizon: int = MAX_HORIZON,
    max_context_width: int = MAX_CONTEXT_WIDTH,
    max_methods: int = MAX_METHODS,
    min_support: int = 1,
    min_confidence: float = 0.5,
    pretrained_mtp_available: bool = False,
    pretrained_mtp_head_id: str | None = None,
    pretrained_mtp_reason: str | None = None,
) -> dict[str, Any]:
    """Create an empty policy bound to one immutable model identity.

    Empty methods are intentional: proposal abstains until target observations
    acquire real context continuations.  ``pretrained_mtp_available`` must be
    set only by an importer that has admitted an actual GGUF MTP head.
    """
    program_id = _text(model_program_id, "model program_id")
    source = _digest(source_sha256, "model source_sha256")
    max_horizon = _integer(max_horizon, "max_horizon", minimum=1, maximum=MAX_HORIZON)
    max_context_width = _integer(max_context_width, "max_context_width", minimum=1, maximum=MAX_CONTEXT_WIDTH)
    max_methods = _integer(max_methods, "max_methods", minimum=1, maximum=MAX_METHODS)
    min_support = _integer(min_support, "min_support", minimum=1, maximum=MAX_COST_UNITS)
    min_confidence = float(min_confidence)
    if not math.isfinite(min_confidence) or not 0.0 < min_confidence <= 1.0:
        raise DraftLearningError("min_confidence must be in (0, 1]")
    if not isinstance(pretrained_mtp_available, bool):
        raise DraftLearningError("MTP availability must be boolean")
    if pretrained_mtp_available and pretrained_mtp_head_id is None:
        raise DraftLearningError("available pretrained MTP requires a head identity")
    methods = [
        {
            "method_id": f"context-{width}",
            "kind": "context-continuation",
            "origin": "field-observation",
            "context_width": width,
            "horizon": 1,
            "rows": [],
            "attempts": 0,
            "accepted_tokens": 0,
            "rejected_tokens": 0,
            "target_tokens": 0,
            "target_cost_units": 0,
            "draft_cost_units": 0,
            "full_accepts": 0,
        }
        for width in range(1, min(max_context_width, max_methods) + 1)
    ]
    return _canonical_policy(
        {
            "schema": DRAFT_POLICY_SCHEMA,
            "model": {"program_id": program_id, "source_sha256": source},
            "owner_id": _text(owner_id, "draft owner_id"),
            "version": 0,
            "config": {
                "max_horizon": max_horizon,
                "max_context_width": max_context_width,
                "max_methods": max_methods,
                "min_support": min_support,
                "min_confidence": min_confidence,
                "cost_unit": "executor-reported-units",
            },
            "pretrained_mtp": {
                "available": bool(pretrained_mtp_available),
                "head_id": pretrained_mtp_head_id,
                "source": "gguf-metadata" if pretrained_mtp_available else "gguf-metadata",
                "reason": pretrained_mtp_reason or ("admitted pretrained MTP head" if pretrained_mtp_available else "no admitted pretrained MTP head; using learned drafts"),
            },
            "methods": methods,
            "active_method_id": None,
            "attempts": 0,
            "accepted_tokens": 0,
            "rejected_tokens": 0,
            "target_tokens": 0,
            "target_cost_units": 0,
            "draft_cost_units": 0,
            "history": [],
        }
    )


def bind_policy(policy: Mapping[str, Any], *, model_program_id: str, source_sha256: str, owner_id: str | None = None) -> dict[str, Any]:
    """Validate a resident policy against the immutable source profile.

    ``program_id`` is descriptive and may change when the same imported GGUF
    receives a new graph label.  The source digest is the binding authority;
    rebasing the descriptive id is a canonical state transition rather than a
    reset of learned continuations.
    """
    result = _canonical_policy(policy)
    requested_source = _digest(source_sha256, "model source_sha256")
    if result["model"]["source_sha256"] != requested_source:
        raise DraftLearningError("draft policy model source identity is stale")
    requested_program = _text(model_program_id, "model program_id")
    if owner_id is not None and result["owner_id"] != _text(owner_id, "draft owner_id"):
        raise DraftLearningError("draft policy owner identity is stale")
    if result["model"]["program_id"] != requested_program:
        result["model"] = {"program_id": requested_program, "source_sha256": requested_source}
        result["version"] += 1
    return _canonical_policy(result)


def declare_pretrained_mtp(
    policy: Mapping[str, Any],
    *,
    available: bool,
    head_id: str | None = None,
    reason: str | None = None,
    source: str = "gguf-metadata",
) -> dict[str, Any]:
    """Replace the explicit MTP capability declaration without learning it."""
    result = _canonical_policy(policy)
    if not isinstance(available, bool):
        raise DraftLearningError("MTP availability must be boolean")
    if available and head_id is None:
        raise DraftLearningError("available pretrained MTP requires a head identity")
    result["pretrained_mtp"] = {
        "available": available,
        "head_id": None if head_id is None else _text(head_id, "MTP head_id"),
        "source": _text(source, "MTP source"),
        "reason": _text(reason or ("admitted pretrained MTP head" if available else "no admitted pretrained MTP head; using learned drafts"), "MTP reason"),
    }
    result["version"] += 1
    return _canonical_policy(result)


def admit_method(
    policy: Mapping[str, Any],
    method: Mapping[str, Any],
    *,
    replace: bool = False,
) -> dict[str, Any]:
    """Admit one canonical field-acquired continuation method.

    Acquisition is data-only: arbitrary Python callables and host model
    objects are rejected by the method validator.  A replacement keeps the
    method identity but resets neither the other resident methods nor policy
    ownership.
    """
    result = _canonical_policy(policy)
    candidate = _canonical_method(method, max_horizon=int(result["config"]["max_horizon"]))
    methods = list(result["methods"])
    existing = next((index for index, item in enumerate(methods) if item["method_id"] == candidate["method_id"]), None)
    if existing is None:
        if len(methods) >= int(result["config"]["max_methods"]):
            raise DraftLearningError("draft method capacity is exhausted")
        methods.append(candidate)
    elif replace:
        methods[existing] = candidate
    else:
        raise DraftLearningError("draft method identity already exists")
    result["methods"] = methods
    result["version"] += 1
    return _canonical_policy(result)


def _row_lookup(method: Mapping[str, Any]) -> dict[tuple[int, ...], Mapping[str, Any]]:
    return {_context_key(row["context"]): row for row in method["rows"]}


def _method_quality(method: Mapping[str, Any], *, target_cost_hint: int | None = None) -> float:
    attempts = int(method["attempts"])
    accepted = int(method["accepted_tokens"])
    if attempts <= 0:
        # Support, rather than a fabricated success rate, breaks ties for new methods.
        total_support = sum(int(next_item["count"]) for row in method["rows"] for next_item in row["next"])
        return min(0.25, total_support / 1000.0)
    rate = accepted / max(1, int(method["target_tokens"]))
    target_cost = int(method["target_cost_units"])
    draft_cost = int(method["draft_cost_units"])
    denominator = target_cost_hint or target_cost
    cost_ratio = (draft_cost / max(1, denominator)) if denominator else 0.0
    return rate - 0.05 * cost_ratio


def _best_next(row: Mapping[str, Any], *, min_support: int, min_confidence: float) -> int | None:
    options = sorted(row["next"], key=lambda item: (-int(item["count"]), int(item["token"])))
    if not options:
        return None
    total = sum(int(item["count"]) for item in options)
    best = options[0]
    if int(best["count"]) < min_support or int(best["count"]) / max(1, total) < min_confidence:
        return None
    return int(best["token"])


def propose_draft(
    policy: Mapping[str, Any],
    context_tokens: Sequence[int],
    *,
    max_tokens: int | None = None,
    target_cost_hint: int | None = None,
) -> dict[str, Any]:
    """Select a resident learned method and construct a bounded draft.

    The proposal is pure and does not increment outcome counters.  Its
    deterministic selector gives each selected token a point-mass proposal
    probability; observed transition frequencies are not the actual q used by
    the sampler.  The caller stores it in task state and folds target outcomes
    back into the resident policy.
    """
    resident = _canonical_policy(policy)
    context = _tokens(context_tokens, "draft context", maximum=65_536)
    config = resident["config"]
    requested = config["max_horizon"] if max_tokens is None else _integer(max_tokens, "draft max_tokens", minimum=1, maximum=MAX_HORIZON)
    requested = min(requested, config["max_horizon"])
    hint = None if target_cost_hint is None else _bounded_cost(target_cost_hint, "target cost hint")
    methods = sorted(
        resident["methods"],
        key=lambda item: (-_method_quality(item, target_cost_hint=hint), -int(item["context_width"]), item["method_id"]),
    )
    selected: Mapping[str, Any] | None = None
    selected_tokens: list[int] = []
    selected_q_rows: list[list[dict[str, Any]]] = []
    for method in methods:
        width = int(method["context_width"])
        lookup = _row_lookup(method)
        generated: list[int] = []
        generated_q_rows: list[list[dict[str, Any]]] = []
        for _ in range(min(requested, int(method["horizon"]))):
            history = (context + generated)[-width:]
            row = lookup.get(_context_key(history))
            if row is None:
                break
            token = _best_next(row, min_support=int(config["min_support"]), min_confidence=float(config["min_confidence"]))
            if token is None:
                break
            generated_q_rows.append([{"token": token, "probability": 1.0}])
            generated.append(token)
        if generated:
            selected = method
            selected_tokens = generated
            selected_q_rows = generated_q_rows
    if selected is None:
        return {
            "schema": DRAFT_PROPOSAL_SCHEMA,
            "model": resident["model"],
            "policy_version": resident["version"],
            "method_id": None,
            "context_tokens": context,
            "draft_tokens": [],
            "horizon": 0,
            "status": "abstain",
            "reason": "no-supported-continuation",
            "draft_source": "learned-context-continuation",
            "pretrained_mtp": resident["pretrained_mtp"],
        }
    proposal = {
        "schema": DRAFT_PROPOSAL_SCHEMA,
        "model": resident["model"],
        "policy_version": resident["version"],
        "method_id": selected["method_id"],
        "context_tokens": context,
        "draft_tokens": selected_tokens,
        "horizon": len(selected_tokens),
        "status": "proposed",
        "reason": "field-supported-continuation",
        "draft_source": "learned-context-continuation",
        "proposal_q": selected_q_rows,
    }
    proposal["proposal_sha256"] = digest_value(proposal)
    return _plain(proposal)


def speculation_frame(proposal: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one draft proposal for operational speculation activation.

    The frame is the explicit bounded hand-off to the model runtime: proposed
    tokens come from a bounded CPU/cache table read, never a model execution.
    Their q distributions describe the deterministic selector and may be used
    only as verification candidates against exact native target distributions;
    they never become model state by themselves.
    """
    if not isinstance(proposal, Mapping) or proposal.get("schema") != DRAFT_PROPOSAL_SCHEMA:
        raise DraftLearningError("draft proposal schema is invalid")
    model = proposal.get("model")
    if not isinstance(model, Mapping):
        raise DraftLearningError("draft proposal model identity is missing")
    _text(model.get("program_id"), "proposal model program_id")
    _digest(model.get("source_sha256"), "proposal model source_sha256")
    draft = _tokens(proposal.get("draft_tokens", ()), "draft tokens")
    if not draft:
        raise DraftLearningError("abstained draft proposal has no speculation frame")
    if len(draft) > MAX_HORIZON:
        raise DraftLearningError("draft proposal exceeds its horizon bound")
    raw_q_rows = proposal.get("proposal_q")
    if (
        isinstance(raw_q_rows, (str, bytes))
        or not isinstance(raw_q_rows, Sequence)
        or len(raw_q_rows) != len(draft)
    ):
        raise DraftLearningError("draft proposal q distributions do not match its horizon")
    q_rows: list[list[dict[str, Any]]] = []
    for index, (draft_token, raw_row) in enumerate(zip(draft, raw_q_rows)):
        if (
            isinstance(raw_row, (str, bytes))
            or not isinstance(raw_row, Sequence)
            or not raw_row
            or len(raw_row) > MAX_NEXT_PER_ROW
        ):
            raise DraftLearningError(f"draft proposal q row {index} is invalid")
        row: list[dict[str, Any]] = []
        seen_tokens: set[int] = set()
        for raw_item in raw_row:
            if not isinstance(raw_item, Mapping):
                raise DraftLearningError(f"draft proposal q row {index} contains an invalid item")
            token = _token(raw_item.get("token"), "draft q token")
            probability_value = raw_item.get("probability")
            if isinstance(probability_value, bool):
                raise DraftLearningError("draft q probability must be numeric")
            try:
                probability = float(probability_value)
            except (TypeError, ValueError) as exc:
                raise DraftLearningError("draft q probability must be numeric") from exc
            if not math.isfinite(probability) or probability <= 0.0 or probability > 1.0:
                raise DraftLearningError("draft q probability must be finite and in (0, 1]")
            if token in seen_tokens:
                raise DraftLearningError("draft q distribution repeats a token")
            seen_tokens.add(token)
            row.append({"token": token, "probability": probability})
        total = math.fsum(item["probability"] for item in row)
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise DraftLearningError("draft q distribution must sum to one")
        if (
            len(row) != 1
            or row[0]["token"] != draft_token
            or row[0]["probability"] != 1.0
        ):
            raise DraftLearningError(
                "deterministic draft q must assign unit mass to its selected token"
            )
        q_rows.append(sorted(row, key=lambda item: item["token"]))
    proposal_digest = proposal.get("proposal_sha256")
    _digest(proposal_digest, "proposal_sha256")
    proposal_body = {key: value for key, value in proposal.items() if key != "proposal_sha256"}
    if digest_value(proposal_body) != proposal_digest:
        raise DraftLearningError("draft proposal digest does not match its content")
    method_id = proposal.get("method_id")
    if not isinstance(method_id, str) or not method_id:
        raise DraftLearningError("draft proposal names no resident method")
    return _plain(
        {
            "schema": DRAFT_SPECULATION_SCHEMA,
            "source": "resident-draft-policy",
            "method_id": method_id,
            "proposal_sha256": proposal.get("proposal_sha256"),
            "draft_tokens": draft,
            "horizon": len(draft),
            "draft_lane": "cpu-cache",
            "proposal_q": q_rows,
        }
    )


def target_sample_and_compare(
    proposal: Mapping[str, Any],
    target_tokens: Sequence[int],
    *,
    rng_state_before: Any = None,
    rng_state_after: Any = None,
) -> dict[str, Any]:
    """Compare one target trajectory against one draft without resampling.

    ``target_tokens`` is the target model's single sequential sample from the
    proposal prefix.  On the first mismatch only that target token is
    committed; the remaining speculative suffix is explicitly returned for
    discard/restore.  Extra supplied target suffix is never silently accepted
    and is marked for target-state restoration.  If RNG snapshots are passed,
    the exact pre-target state is returned as ``rng_state_to_restore``.
    """
    if not isinstance(proposal, Mapping) or proposal.get("schema") != DRAFT_PROPOSAL_SCHEMA:
        raise DraftLearningError("draft proposal schema is invalid")
    model = proposal.get("model")
    if not isinstance(model, Mapping):
        raise DraftLearningError("draft proposal model identity is missing")
    _text(model.get("program_id"), "proposal model program_id")
    _digest(model.get("source_sha256"), "proposal model source_sha256")
    draft = _tokens(proposal.get("draft_tokens", ()), "draft tokens")
    target = _tokens(target_tokens, "target tokens")
    rng_before = None if rng_state_before is None else _plain(rng_state_before)
    rng_after = None if rng_state_after is None else _plain(rng_state_after)
    restoration = {"rng_state_to_restore": rng_before, "rng_state_after_target": rng_after}
    if not draft:
        return {
            "schema": DRAFT_COMPARISON_SCHEMA,
            "status": "abstained",
            "accepted_prefix": [],
            "committed_tokens": [],
            "rejected_suffix": [],
            "rejection_target": None,
            "target_consumed": 0,
            "target_suffix_to_restore": target,
            "restore_speculative_suffix": [],
            "restore_rng": True,
            "restore_target_state": True,
            "target_state_consumed_once": True,
            **restoration,
        }
    if not target:
        raise DraftLearningError("target trajectory is empty")
    match = 0
    while match < len(draft) and match < len(target) and draft[match] == target[match]:
        match += 1
    rejected = draft[match:]
    if match < len(draft):
        if match >= len(target):
            raise DraftLearningError("target trajectory ended before draft rejection")
        rejection_target = target[match]
        committed = target[: match + 1]
        consumed = match + 1
        status = "rejected"
    else:
        rejection_target = None
        committed = target[: len(draft)]
        consumed = len(draft)
        status = "accepted"
    return {
        "schema": DRAFT_COMPARISON_SCHEMA,
        "status": status,
        "accepted_prefix": target[:match],
        "committed_tokens": committed,
        "rejected_suffix": rejected,
        "rejection_target": rejection_target,
        "target_consumed": consumed,
        "target_suffix_to_restore": target[consumed:],
        "restore_speculative_suffix": rejected,
        "restore_rng": True,
        "restore_target_state": True,
        "target_state_consumed_once": True,
        **restoration,
    }


def _merge_row(rows: list[dict[str, Any]], context: Sequence[int], token: int) -> list[dict[str, Any]]:
    key = _context_key(context)
    index = next((idx for idx, row in enumerate(rows) if _context_key(row["context"]) == key), None)
    if index is None:
        if len(rows) >= MAX_ROWS_PER_METHOD:
            # Keep the canonical table bounded: evict the lexicographically largest
            # row only when the incoming context is earlier, never by recency.
            largest = max(range(len(rows)), key=lambda idx: _context_key(rows[idx]["context"]))
            if key >= _context_key(rows[largest]["context"]):
                return rows
            del rows[largest]
        rows.append({"context": list(key), "next": [{"token": token, "count": 1}]})
    else:
        next_values = list(rows[index]["next"])
        match = next((item for item, row in enumerate(next_values) if int(row["token"]) == token), None)
        if match is not None:
            next_values[match] = {"token": token, "count": min(MAX_COST_UNITS, int(next_values[match]["count"]) + 1)}
        elif len(next_values) < MAX_NEXT_PER_ROW:
            next_values.append({"token": token, "count": 1})
        else:
            weakest = min(range(len(next_values)), key=lambda item: (int(next_values[item]["count"]), int(next_values[item]["token"])))
            if int(next_values[weakest]["count"]) <= 1 and token < int(next_values[weakest]["token"]):
                next_values[weakest] = {"token": token, "count": 1}
        rows[index]["next"] = sorted(next_values, key=lambda item: int(item["token"]))
    return sorted(rows, key=lambda row: _context_key(row["context"]))


def record_target_sequence(
    policy: Mapping[str, Any],
    context_tokens: Sequence[int],
    target_tokens: Sequence[int],
    *,
    target_cost_units: int = 0,
) -> dict[str, Any]:
    """Acquire context continuations from a target trajectory without a draft."""
    result = _canonical_policy(policy)
    context = _tokens(context_tokens, "target context", maximum=65_536)
    targets = _tokens(target_tokens, "target sequence", allow_empty=False, maximum=MAX_HORIZON + 1)
    cost = _bounded_cost(target_cost_units, "target cost units")
    for method in result["methods"]:
        width = int(method["context_width"])
        rows = [dict(row, next=[dict(item) for item in row["next"]]) for row in method["rows"]]
        history = list(context)
        for token in targets:
            suffix = history[-width:]
            # A width-``w`` method is keyed by exactly ``w`` tokens.  While the
            # observed history is shorter than its own width there is no
            # width-consistent key, so that method learns nothing yet rather
            # than storing a row it could never look up again.
            if len(suffix) == width:
                rows = _merge_row(rows, suffix, token)
            history.append(token)
        method["rows"] = rows
        method["target_tokens"] = min(MAX_COST_UNITS, int(method["target_tokens"]) + len(targets))
        method["target_cost_units"] = min(MAX_COST_UNITS, int(method["target_cost_units"]) + cost)
    result["target_tokens"] = min(MAX_COST_UNITS, int(result["target_tokens"]) + len(targets))
    result["target_cost_units"] = min(MAX_COST_UNITS, int(result["target_cost_units"]) + cost)
    result["version"] += 1
    return _canonical_policy(result)


def record_target_outcome(
    policy: Mapping[str, Any],
    proposal: Mapping[str, Any],
    target_tokens: Sequence[int],
    *,
    target_cost_units: int,
    draft_cost_units: int = 0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fold one target comparison into canonical policy and return its receipt."""
    result = _canonical_policy(policy)
    if proposal.get("schema") != DRAFT_PROPOSAL_SCHEMA:
        raise DraftLearningError("draft proposal schema is invalid")
    if proposal.get("model") != result["model"]:
        raise DraftLearningError("draft proposal model identity is stale")
    method_id = proposal.get("method_id")
    if method_id is None:
        # An abstained proposal still learns the target continuation.
        comparison = target_sample_and_compare(proposal, target_tokens)
        successor = record_target_sequence(result, proposal.get("context_tokens", ()), target_tokens, target_cost_units=target_cost_units)
        comparison["policy_version"] = successor["version"]
        return successor, comparison
    method = next((item for item in result["methods"] if item["method_id"] == method_id), None)
    if method is None:
        raise DraftLearningError("draft method is not resident")
    comparison = target_sample_and_compare(proposal, target_tokens)
    accepted = len(comparison["accepted_prefix"])
    rejected = len(comparison["rejected_suffix"])
    consumed = int(comparison["target_consumed"])
    target_cost = _bounded_cost(target_cost_units, "target cost units")
    draft_cost = _bounded_cost(draft_cost_units, "draft cost units")
    method["attempts"] = min(MAX_COST_UNITS, int(method["attempts"]) + 1)
    method["accepted_tokens"] = min(MAX_COST_UNITS, int(method["accepted_tokens"]) + accepted)
    method["rejected_tokens"] = min(MAX_COST_UNITS, int(method["rejected_tokens"]) + rejected)
    method["target_tokens"] = min(MAX_COST_UNITS, int(method["target_tokens"]) + consumed)
    method["target_cost_units"] = min(MAX_COST_UNITS, int(method["target_cost_units"]) + target_cost)
    method["draft_cost_units"] = min(MAX_COST_UNITS, int(method["draft_cost_units"]) + draft_cost)
    if comparison["status"] == "accepted":
        method["full_accepts"] = min(MAX_COST_UNITS, int(method["full_accepts"]) + 1)
    # The horizon is learned from outcomes and measured cost, never from wall time.
    if comparison["status"] == "accepted" and target_cost >= draft_cost:
        method["horizon"] = min(result["config"]["max_horizon"], int(method["horizon"]) + 1)
    elif comparison["status"] == "rejected" or draft_cost > target_cost:
        method["horizon"] = max(1, int(method["horizon"]) - 1)
    result["attempts"] = min(MAX_COST_UNITS, int(result["attempts"]) + 1)
    result["accepted_tokens"] = min(MAX_COST_UNITS, int(result["accepted_tokens"]) + accepted)
    result["rejected_tokens"] = min(MAX_COST_UNITS, int(result["rejected_tokens"]) + rejected)
    result["target_tokens"] = min(MAX_COST_UNITS, int(result["target_tokens"]) + consumed)
    result["target_cost_units"] = min(MAX_COST_UNITS, int(result["target_cost_units"]) + target_cost)
    result["draft_cost_units"] = min(MAX_COST_UNITS, int(result["draft_cost_units"]) + draft_cost)
    result["active_method_id"] = str(method_id)
    history_row = {
        "method_id": str(method_id),
        "horizon": int(proposal.get("horizon", len(proposal.get("draft_tokens", ())))),
        "status": comparison["status"],
        "accepted_tokens": accepted,
        "rejected_tokens": rejected,
        "target_consumed": consumed,
        "target_cost_units": target_cost,
        "draft_cost_units": draft_cost,
    }
    result["history"] = (result["history"] + [history_row])[-MAX_HISTORY:]
    # Also acquire the verified target continuation, including the rejection token.
    context = _tokens(proposal.get("context_tokens", ()), "proposal context", maximum=65_536)
    learned_targets = _tokens(comparison["committed_tokens"], "committed target tokens", allow_empty=False)
    for candidate in result["methods"]:
        width = int(candidate["context_width"])
        rows = [dict(row, next=[dict(item) for item in row["next"]]) for row in candidate["rows"]]
        history_tokens = list(context)
        for token in learned_targets:
            suffix = history_tokens[-width:]
            if len(suffix) == width:
                rows = _merge_row(rows, suffix, token)
            history_tokens.append(token)
        candidate["rows"] = rows
    result["version"] += 1
    comparison["policy_version"] = result["version"]
    comparison["method_id"] = str(method_id)
    return _canonical_policy(result), _plain(comparison)


# Explicit aliases make the integration seam readable at call sites.
initialize_draft_policy = initial_policy
select_draft = propose_draft
verify_target_sample_and_compare = target_sample_and_compare
observe_target_outcome = record_target_outcome


__all__ = [
    "DRAFT_COMPARISON_SCHEMA",
    "DRAFT_OBSERVATION_SCHEMA",
    "DRAFT_POLICY_SCHEMA",
    "DRAFT_PROPOSAL_SCHEMA",
    "admit_method",
    "bind_policy",
    "declare_pretrained_mtp",
    "initial_policy",
    "initialize_draft_policy",
    "observe_target_outcome",
    "propose_draft",
    "record_target_outcome",
    "record_target_sequence",
    "select_draft",
    "speculation_frame",
    "target_sample_and_compare",
    "verify_target_sample_and_compare",
]
