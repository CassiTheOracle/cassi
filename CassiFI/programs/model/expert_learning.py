"""Field-owned learned expert residency and prefetch policy.

The policy is deliberately a small, JSON-canonical transition system.  It does
not own a cache, a model weight, or a process-local table: the invoking owner
stores the returned state in its regional field and gives the returned decision
to the physical ``WeightBank``.  Routing is an input and is never changed by
this module.  Consequently a policy can alter loading work without altering
expert identity, logits, or answers.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


SCHEMA = "cassifi.expert-residency-policy.v1"
SELECTION_SCHEMA = "cassifi.expert-residency-selection.v1"
LAYOUT = "expert-residency-sparse-bounded-transition-v2"
METHODS = ("baseline", "frequency", "context", "transition")
_MAX_COUNTER = 2**53 - 1
_MAX_LAYERS = 4096
_MAX_EXPERTS = 4096
_MAX_CONTEXTS = 64
_MAX_EVIDENCE = 512
_MAX_TRANSITIONS = 512
_MAX_CONTEXT_BYTES = 4096
_MAX_COST_NS = 10**15


class ExpertPolicyError(ValueError):
    """The expert policy or an observation is not canonical or bounded."""


def _canonical(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        )
    except (TypeError, ValueError) as exc:
        raise ExpertPolicyError("expert policy value is not canonical JSON") from exc


def _int(value: Any, name: str, *, minimum: int = 0, maximum: int = _MAX_COUNTER) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ExpertPolicyError(f"{name} must be a bounded integer")
    return int(value)


def _text(value: Any, name: str, *, empty: bool = False, limit: int = 4096) -> str:
    if not isinstance(value, str) or (not empty and not value) or len(value.encode("utf-8")) > limit:
        raise ExpertPolicyError(f"{name} must be bounded text")
    return value


def _keys(value: Any, name: str, *, maximum: int, upper: int) -> list[int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ExpertPolicyError(f"{name} must be a sequence")
    if len(value) > maximum:
        raise ExpertPolicyError(f"{name} exceeds its bound")
    result: list[int] = []
    for item in value:
        item = _int(item, f"{name} item", maximum=upper - 1)
        result.append(item)
    if len(set(result)) != len(result):
        raise ExpertPolicyError(f"{name} contains duplicates")
    return sorted(result)


def _increment(value: int, amount: int, name: str) -> int:
    amount = _int(amount, name)
    if value > _MAX_COUNTER - amount:
        raise ExpertPolicyError(f"{name} counter overflow")
    return value + amount


def _copy_state(state: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(state, Mapping):
        raise ExpertPolicyError("policy state must be a mapping")
    return _canonical(dict(state))


_EXPERT_KEYS = ("uses", "hits", "misses", "load_cost_ns", "prefetches", "evictions")


def _empty_expert() -> dict[str, int]:
    return {"uses": 0, "hits": 0, "misses": 0, "load_cost_ns": 0, "prefetches": 0, "evictions": 0}


def _empty_layer() -> dict[str, Any]:
    """A layer holds counters only for experts the field has actually seen.

    A 256-expert mixture materializes one row per observed expert instead of a
    dense per-expert matrix, so policy state grows with use rather than with
    routing capacity.
    """
    return {"observations": 0, "experts": {}}


def _expert_row(layer: Mapping[str, Any], expert: int) -> dict[str, int]:
    rows = layer["experts"]
    key = str(int(expert))
    row = rows.get(key)
    if row is None:
        row = _empty_expert()
        rows[key] = row
    return row


def _empty_method() -> dict[str, Any]:
    return {"attempts": 0, "hits": 0, "misses": 0, "load_cost_ns": 0}


def _check_key_list(values: Any, name: str, *, maximum: int, expert_count: int) -> list[int]:
    return _keys(values, name, maximum=maximum, upper=expert_count)


def _validate_evidence(row: Mapping[str, Any], *, layer_count: int, expert_count: int) -> dict[str, Any]:
    required = {"context_key", "layer", "expert", "uses", "hits", "misses", "load_cost_ns", "last_epoch"}
    if set(row) != required:
        raise ExpertPolicyError("context evidence keys are invalid")
    context_key = _text(row["context_key"], "context evidence context_key", empty=True)
    layer = _int(row["layer"], "context evidence layer", maximum=layer_count - 1)
    expert = _int(row["expert"], "context evidence expert", maximum=expert_count - 1)
    uses = _int(row["uses"], "context evidence uses")
    hits = _int(row["hits"], "context evidence hits")
    misses = _int(row["misses"], "context evidence misses")
    if hits + misses != uses:
        raise ExpertPolicyError("context evidence outcomes disagree")
    return {
        "context_key": context_key,
        "layer": layer,
        "expert": expert,
        "uses": uses,
        "hits": hits,
        "misses": misses,
        "load_cost_ns": _int(row["load_cost_ns"], "context evidence load_cost_ns", maximum=_MAX_COST_NS),
        "last_epoch": _int(row["last_epoch"], "context evidence last_epoch"),
    }


def _validate_transition(row: Mapping[str, Any], *, layer_count: int, expert_count: int) -> dict[str, Any]:
    required = {"from_context", "to_context", "layer", "expert", "uses", "hits", "misses", "load_cost_ns", "last_epoch"}
    if set(row) != required:
        raise ExpertPolicyError("transition evidence keys are invalid")
    result = {
        "from_context": _text(row["from_context"], "transition from_context", empty=True),
        "to_context": _text(row["to_context"], "transition to_context", empty=True),
        "layer": _int(row["layer"], "transition layer", maximum=layer_count - 1),
        "expert": _int(row["expert"], "transition expert", maximum=expert_count - 1),
        "uses": _int(row["uses"], "transition uses"),
        "hits": _int(row["hits"], "transition hits"),
        "misses": _int(row["misses"], "transition misses"),
        "load_cost_ns": _int(row["load_cost_ns"], "transition load_cost_ns", maximum=_MAX_COST_NS),
        "last_epoch": _int(row["last_epoch"], "transition last_epoch"),
    }
    if result["hits"] + result["misses"] != result["uses"]:
        raise ExpertPolicyError("transition outcomes disagree")
    return result


def _validate_state(value: Mapping[str, Any]) -> dict[str, Any]:
    state = _copy_state(value)
    required = {
        "schema", "layout", "model_id", "layer_count", "expert_count", "capacity_bytes",
        "max_contexts", "max_evidence", "max_transitions", "epoch", "layers", "methods",
        "contexts", "evidence", "transitions",
    }
    if set(state) != required or state["schema"] != SCHEMA or state["layout"] != LAYOUT:
        raise ExpertPolicyError("expert policy state schema is invalid")
    model_id = _text(state["model_id"], "model_id")
    layer_count = _int(state["layer_count"], "layer_count", minimum=1, maximum=_MAX_LAYERS)
    expert_count = _int(state["expert_count"], "expert_count", minimum=1, maximum=_MAX_EXPERTS)
    capacity = _int(state["capacity_bytes"], "capacity_bytes", minimum=1)
    max_contexts = _int(state["max_contexts"], "max_contexts", minimum=1, maximum=_MAX_CONTEXTS)
    max_evidence = _int(state["max_evidence"], "max_evidence", minimum=1, maximum=_MAX_EVIDENCE)
    max_transitions = _int(state["max_transitions"], "max_transitions", minimum=1, maximum=_MAX_TRANSITIONS)
    epoch = _int(state["epoch"], "epoch")
    layers = state["layers"]
    if not isinstance(layers, list) or len(layers) != layer_count:
        raise ExpertPolicyError("policy layer count is invalid")
    canonical_layers: list[dict[str, Any]] = []
    for layer in layers:
        if not isinstance(layer, Mapping) or set(layer) != {"observations", "experts"}:
            raise ExpertPolicyError("policy layer record is invalid")
        experts = layer["experts"]
        if not isinstance(experts, Mapping) or len(experts) > expert_count:
            raise ExpertPolicyError("policy expert count is invalid")
        canonical_experts: dict[str, dict[str, int]] = {}
        for key, expert in experts.items():
            index = _int(int(key), "expert index", maximum=expert_count - 1)
            if str(index) != key:
                raise ExpertPolicyError("policy expert key is not canonical")
            if not isinstance(expert, Mapping) or set(expert) != set(_EXPERT_KEYS):
                raise ExpertPolicyError("policy expert record is invalid")
            row = {name: _int(expert[name], f"expert {name}", maximum=_MAX_COST_NS if name == "load_cost_ns" else _MAX_COUNTER) for name in _EXPERT_KEYS}
            if row["hits"] + row["misses"] != row["uses"]:
                raise ExpertPolicyError("expert outcomes disagree")
            canonical_experts[key] = row
        canonical_layers.append({"observations": _int(layer["observations"], "layer observations"), "experts": canonical_experts})
    methods = state["methods"]
    if not isinstance(methods, Mapping) or set(methods) != set(METHODS):
        raise ExpertPolicyError("policy methods are invalid")
    canonical_methods: dict[str, dict[str, int]] = {}
    for name in METHODS:
        row = methods[name]
        if not isinstance(row, Mapping) or set(row) != {"attempts", "hits", "misses", "load_cost_ns"}:
            raise ExpertPolicyError("policy method record is invalid")
        normalized = {key: _int(row[key], f"method {key}", maximum=_MAX_COST_NS if key == "load_cost_ns" else _MAX_COUNTER) for key in row}
        if normalized["hits"] + normalized["misses"] != normalized["attempts"]:
            raise ExpertPolicyError("method outcomes disagree")
        canonical_methods[name] = normalized
    contexts = state["contexts"]
    if not isinstance(contexts, list) or len(contexts) > max_contexts:
        raise ExpertPolicyError("context history exceeds its bound")
    canonical_contexts: list[dict[str, Any]] = []
    seen_contexts: set[str] = set()
    for row in contexts:
        if not isinstance(row, Mapping) or set(row) != {"key", "uses", "last_epoch"}:
            raise ExpertPolicyError("context record is invalid")
        key = _text(row["key"], "context key", empty=True)
        if key in seen_contexts:
            raise ExpertPolicyError("context key is duplicated")
        seen_contexts.add(key)
        canonical_contexts.append({"key": key, "uses": _int(row["uses"], "context uses"), "last_epoch": _int(row["last_epoch"], "context last_epoch")})
    evidence = state["evidence"]
    if evidence is None:
        raise ExpertPolicyError("policy evidence is missing")
    if not isinstance(evidence, list) or len(evidence) > max_evidence:
        raise ExpertPolicyError("context evidence exceeds its bound")
    canonical_evidence = [_validate_evidence(row, layer_count=layer_count, expert_count=expert_count) for row in evidence]
    transitions = state["transitions"]
    if not isinstance(transitions, list) or len(transitions) > max_transitions:
        raise ExpertPolicyError("transition evidence exceeds its bound")
    canonical_transitions = [_validate_transition(row, layer_count=layer_count, expert_count=expert_count) for row in transitions]
    state = {
        "schema": SCHEMA,
        "layout": LAYOUT,
        "model_id": model_id,
        "layer_count": layer_count,
        "expert_count": expert_count,
        "capacity_bytes": capacity,
        "max_contexts": max_contexts,
        "max_evidence": max_evidence,
        "max_transitions": max_transitions,
        "epoch": epoch,
        "layers": canonical_layers,
        "methods": canonical_methods,
        "contexts": sorted(canonical_contexts, key=lambda row: row["key"]),
        "evidence": sorted(canonical_evidence, key=lambda row: (row["context_key"], row["layer"], row["expert"])),
        "transitions": sorted(canonical_transitions, key=lambda row: (row["from_context"], row["to_context"], row["layer"], row["expert"])),
    }
    return _canonical(state)


def initial_state(
    model_id: str,
    layer_count: int,
    expert_count: int,
    capacity_bytes: int,
    *,
    max_contexts: int = 16,
    max_evidence: int = 256,
    max_transitions: int = 256,
) -> dict[str, Any]:
    """Create zero-evidence policy state bound to one immutable model identity."""
    state = {
        "schema": SCHEMA,
        "layout": LAYOUT,
        "model_id": _text(model_id, "model_id"),
        "layer_count": _int(layer_count, "layer_count", minimum=1, maximum=_MAX_LAYERS),
        "expert_count": _int(expert_count, "expert_count", minimum=1, maximum=_MAX_EXPERTS),
        "capacity_bytes": _int(capacity_bytes, "capacity_bytes", minimum=1),
        "max_contexts": _int(max_contexts, "max_contexts", minimum=1, maximum=_MAX_CONTEXTS),
        "max_evidence": _int(max_evidence, "max_evidence", minimum=1, maximum=_MAX_EVIDENCE),
        "max_transitions": _int(max_transitions, "max_transitions", minimum=1, maximum=_MAX_TRANSITIONS),
        "epoch": 0,
        "layers": [],
        "methods": {name: _empty_method() for name in METHODS},
        "contexts": [],
        "evidence": [],
        "transitions": [],
    }
    state["layers"] = [_empty_layer() for _ in range(state["layer_count"])]
    return _validate_state(state)


def from_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and detach a state loaded from the owner's field record."""
    return _validate_state(value)


def _expert_bytes(expert_bytes: Mapping[Any, Any] | Sequence[Any], expert_count: int) -> list[int]:
    result = [1] * expert_count
    if isinstance(expert_bytes, Mapping):
        items = expert_bytes.items()
    elif isinstance(expert_bytes, Sequence) and not isinstance(expert_bytes, (str, bytes)):
        if len(expert_bytes) > expert_count:
            raise ExpertPolicyError("expert byte sequence exceeds expert count")
        items = enumerate(expert_bytes)
    else:
        raise ExpertPolicyError("expert_bytes must be a mapping or sequence")
    for key, value in items:
        index = _int(int(key), "expert byte index", maximum=expert_count - 1)
        result[index] = _int(value, "expert byte size", minimum=1)
    return result


def _context_row(state: dict[str, Any], key: str) -> dict[str, Any] | None:
    for row in state["contexts"]:
        if row["key"] == key:
            return row
    return None


def _evidence_row(rows: list[dict[str, Any]], **identity: Any) -> dict[str, Any] | None:
    for row in rows:
        if all(row[name] == value for name, value in identity.items()):
            return row
    return None


def _ensure_context(state: dict[str, Any], key: str) -> dict[str, Any]:
    row = _context_row(state, key)
    if row is not None:
        return row
    if len(state["contexts"]) >= state["max_contexts"]:
        victim = min(state["contexts"], key=lambda item: (item["uses"], item["last_epoch"], item["key"]))
        state["contexts"].remove(victim)
        state["evidence"] = [item for item in state["evidence"] if item["context_key"] != victim["key"]]
    row = {"key": key, "uses": 0, "last_epoch": state["epoch"]}
    state["contexts"].append(row)
    return row


def _upsert_evidence(state: dict[str, Any], context_key: str, layer: int, expert: int) -> dict[str, Any]:
    row = _evidence_row(state["evidence"], context_key=context_key, layer=layer, expert=expert)
    if row is not None:
        return row
    if len(state["evidence"]) >= state["max_evidence"]:
        victim = min(state["evidence"], key=lambda item: (item["uses"], item["last_epoch"], item["context_key"], item["layer"], item["expert"]))
        state["evidence"].remove(victim)
    row = {"context_key": context_key, "layer": layer, "expert": expert, "uses": 0, "hits": 0, "misses": 0, "load_cost_ns": 0, "last_epoch": state["epoch"]}
    state["evidence"].append(row)
    return row


def _upsert_transition(state: dict[str, Any], from_context: str, to_context: str, layer: int, expert: int) -> dict[str, Any]:
    row = _evidence_row(state["transitions"], from_context=from_context, to_context=to_context, layer=layer, expert=expert)
    if row is not None:
        return row
    if len(state["transitions"]) >= state["max_transitions"]:
        victim = min(state["transitions"], key=lambda item: (item["uses"], item["last_epoch"], item["from_context"], item["to_context"], item["layer"], item["expert"]))
        state["transitions"].remove(victim)
    row = {"from_context": from_context, "to_context": to_context, "layer": layer, "expert": expert, "uses": 0, "hits": 0, "misses": 0, "load_cost_ns": 0, "last_epoch": state["epoch"]}
    state["transitions"].append(row)
    return row


def _score(row: Mapping[str, Any] | None, *, byte_size: int) -> tuple[int, int, int]:
    """Return a cost-aware integer score, support, and estimated cost."""
    if row is None or int(row["uses"]) == 0:
        return 0, 0, 0
    uses = int(row["uses"])
    hits = int(row["hits"])
    cost = int(row["load_cost_ns"])
    # 1024 is a fixed-point hit-rate scale.  Cost and bytes are penalties;
    # integer arithmetic keeps selection platform-independent.
    benefit = hits * 1024 + uses * 16
    penalty = (cost // uses) // 1_000_000 + max(1, byte_size // 1_048_576)
    return max(0, benefit - penalty), uses, cost // uses


def _method_choice(state: Mapping[str, Any], *, has_context: bool, has_transition: bool) -> str:
    # Specific evidence is more informative than an aggregate prior. Keep it
    # selected while it has support so repeated requests actually use what was
    # learned; deterministic fallbacks cover cold and unseen contexts.
    if has_transition:
        return "transition"
    if has_context:
        return "context"
    if any(
        int(row["uses"]) > 0
        for layer in state["layers"]
        for row in layer["experts"].values()
    ):
        return "frequency"
    return "baseline"


def select(
    state: Mapping[str, Any],
    layer: int,
    context_key: str,
    mandatory_experts: Sequence[int],
    expert_bytes: Mapping[Any, Any] | Sequence[Any],
    resident_experts: Sequence[int] = (),
    previous_context_key: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Select physical residency without changing the routed expert set.

    ``mandatory_experts`` is copied verbatim as a sorted exact set in the
    decision.  Every mandatory expert is retained even when its bytes exceed
    capacity; ``capacity_overflow`` makes that physical impossibility explicit
    instead of silently dropping a required weight.
    """
    working = _validate_state(state)
    layer = _int(layer, "layer", maximum=working["layer_count"] - 1)
    context_key = _text(context_key, "context_key", empty=True)
    if previous_context_key is not None:
        previous_context_key = _text(previous_context_key, "previous_context_key", empty=True)
    mandatory = _check_key_list(mandatory_experts, "mandatory_experts", maximum=working["expert_count"], expert_count=working["expert_count"])
    resident = _check_key_list(resident_experts, "resident_experts", maximum=working["expert_count"], expert_count=working["expert_count"])
    sizes = _expert_bytes(expert_bytes, working["expert_count"])
    layer_state = working["layers"][layer]
    context_rows = {row["expert"]: row for row in working["evidence"] if row["context_key"] == context_key and row["layer"] == layer}
    transition_rows = {
        row["expert"]: row for row in working["transitions"]
        if previous_context_key is not None and row["from_context"] == previous_context_key and row["to_context"] == context_key and row["layer"] == layer
    }
    has_context = any(int(row["uses"]) > 0 for row in context_rows.values())
    has_transition = any(int(row["uses"]) > 0 for row in transition_rows.values())
    method = _method_choice(working, has_context=has_context, has_transition=has_transition)
    target = set(mandatory)
    candidates: list[tuple[int, int, int, int]] = []
    for expert in range(working["expert_count"]):
        if expert in target:
            continue
        global_row = layer_state["experts"].get(str(expert))
        if method == "transition":
            source = transition_rows.get(expert)
        elif method == "context":
            source = context_rows.get(expert)
        elif method == "frequency":
            source = global_row
        else:
            source = None
        score, support, cost = _score(source, byte_size=sizes[expert])
        if score > 0:
            # Ratio comparison happens below without floats; expert id is the
            # final deterministic tie break.
            candidates.append((score, support, -cost, expert))
    candidates.sort(key=lambda item: (-item[0] * 1_000_000 // max(1, sizes[item[3]]), -item[1], item[2], item[3]))
    used = sum(sizes[expert] for expert in target)
    for _, _, _, expert in candidates:
        if used + sizes[expert] <= working["capacity_bytes"]:
            target.add(expert)
            used += sizes[expert]
    # Mandatory experts are never sacrificed.  Current nonmandatory residency
    # not selected by the learned policy becomes an actual eviction request.
    prefetch = sorted(target.difference(resident))
    evict = sorted(set(resident).difference(target).difference(mandatory))
    decision = {
        "schema": SELECTION_SCHEMA,
        "model_id": working["model_id"],
        "layer": layer,
        "context_key": context_key,
        "previous_context_key": previous_context_key,
        "method": method,
        "mandatory_experts": mandatory,
        "resident_experts": sorted(target),
        "prefetch_experts": prefetch,
        "evict_experts": evict,
        "capacity_bytes": working["capacity_bytes"],
        "resident_bytes": used,
        "mandatory_bytes": sum(sizes[expert] for expert in mandatory),
        "capacity_overflow": used > working["capacity_bytes"],
        "history_support": sum(item[1] for item in candidates),
    }
    return working, _canonical(decision)


def observe(state: Mapping[str, Any], observation: Mapping[str, Any]) -> dict[str, Any]:
    """Fold one measured route/load result into the continuing field policy."""
    working = _validate_state(state)
    if not isinstance(observation, Mapping):
        raise ExpertPolicyError("expert observation must be a mapping")
    required = {"layer", "context_key", "requested_experts", "hit_experts", "miss_experts", "load_cost_ns"}
    if not required.issubset(observation):
        raise ExpertPolicyError("expert observation is missing required fields")
    layer = _int(observation["layer"], "observation layer", maximum=working["layer_count"] - 1)
    context_key = _text(observation["context_key"], "observation context_key", empty=True)
    requested = _check_key_list(observation["requested_experts"], "requested_experts", maximum=working["expert_count"], expert_count=working["expert_count"])
    hits = set(_check_key_list(observation["hit_experts"], "hit_experts", maximum=working["expert_count"], expert_count=working["expert_count"]))
    misses = set(_check_key_list(observation["miss_experts"], "miss_experts", maximum=working["expert_count"], expert_count=working["expert_count"]))
    if hits & misses or hits | misses != set(requested):
        raise ExpertPolicyError("expert observation outcomes must partition requested experts")
    cost = _int(observation["load_cost_ns"], "load_cost_ns", maximum=_MAX_COST_NS)
    previous = observation.get("previous_context_key")
    if previous is not None:
        previous = _text(previous, "previous_context_key", empty=True)
    method = str(observation.get("method", "baseline"))
    if method not in METHODS:
        raise ExpertPolicyError("expert observation method is invalid")
    working["epoch"] = _increment(working["epoch"], 1, "epoch")
    context = _ensure_context(working, context_key)
    context["uses"] = _increment(context["uses"], 1, "context uses")
    context["last_epoch"] = working["epoch"]
    layer_state = working["layers"][layer]
    layer_state["observations"] = _increment(layer_state["observations"], 1, "layer observations")
    method_row = working["methods"][method]
    method_row["attempts"] = _increment(method_row["attempts"], len(requested), "method attempts")
    method_row["hits"] = _increment(method_row["hits"], len(hits), "method hits")
    method_row["misses"] = _increment(method_row["misses"], len(misses), "method misses")
    method_row["load_cost_ns"] = _increment(method_row["load_cost_ns"], cost, "method load cost")
    per_expert_cost = observation.get("expert_load_cost_ns", {})
    if isinstance(per_expert_cost, Mapping):
        costs: dict[int, int] = {}
        for key, value in per_expert_cost.items():
            index = _int(int(key), "expert load cost index", maximum=working["expert_count"] - 1)
            costs[index] = _int(value, "expert load cost", maximum=_MAX_COST_NS)
    else:
        costs = {}
    prefetches = set(_check_key_list(observation.get("prefetch_experts", ()), "prefetch_experts", maximum=working["expert_count"], expert_count=working["expert_count"]))
    evictions = set(_check_key_list(observation.get("evict_experts", ()), "evict_experts", maximum=working["expert_count"], expert_count=working["expert_count"]))
    for expert in requested:
        hit = expert in hits
        expert_cost = costs.get(expert, cost if expert in misses else 0)
        row = _expert_row(layer_state, expert)
        row["uses"] = _increment(row["uses"], 1, "expert uses")
        row["hits" if hit else "misses"] = _increment(row["hits" if hit else "misses"], 1, "expert outcome")
        row["load_cost_ns"] = _increment(row["load_cost_ns"], expert_cost, "expert load cost")
        evidence = _upsert_evidence(working, context_key, layer, expert)
        evidence["uses"] = _increment(evidence["uses"], 1, "context evidence uses")
        evidence["hits" if hit else "misses"] = _increment(evidence["hits" if hit else "misses"], 1, "context evidence outcome")
        evidence["load_cost_ns"] = _increment(evidence["load_cost_ns"], expert_cost, "context evidence cost")
        evidence["last_epoch"] = working["epoch"]
        if previous is not None:
            transition = _upsert_transition(working, previous, context_key, layer, expert)
            transition["uses"] = _increment(transition["uses"], 1, "transition uses")
            transition["hits" if hit else "misses"] = _increment(transition["hits" if hit else "misses"], 1, "transition outcome")
            transition["load_cost_ns"] = _increment(transition["load_cost_ns"], expert_cost, "transition cost")
            transition["last_epoch"] = working["epoch"]
    for expert in sorted(prefetches):
        if expert not in requested:
            row = _expert_row(layer_state, expert)
            row["prefetches"] = _increment(row["prefetches"], 1, "expert prefetches")
    for expert in sorted(evictions):
        if expert not in requested:
            row = _expert_row(layer_state, expert)
            row["evictions"] = _increment(row["evictions"], 1, "expert evictions")
    working["contexts"] = sorted(working["contexts"], key=lambda row: row["key"])
    working["evidence"] = sorted(working["evidence"], key=lambda row: (row["context_key"], row["layer"], row["expert"]))
    working["transitions"] = sorted(working["transitions"], key=lambda row: (row["from_context"], row["to_context"], row["layer"], row["expert"]))
    return _validate_state(working)


# Explicit names make the owner/runtime integration self-documenting while
# keeping one implementation and one canonical state transition.
select_experts = select
observe_experts = observe
initial_policy = initial_state


__all__ = [
    "ExpertPolicyError",
    "LAYOUT",
    "METHODS",
    "SCHEMA",
    "SELECTION_SCHEMA",
    "from_dict",
    "initial_policy",
    "initial_state",
    "observe",
    "observe_experts",
    "select",
    "select_experts",
]
