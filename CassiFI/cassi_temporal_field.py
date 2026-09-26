"""Bounded categorical predictive state computed from direct numeric field planes.

The transition model is the first (shared) field slice.  Working state is kept
in numeric planes in that same slice for the primary stream and in additional
slices for bound participants; no Python history or policy cache is persistent.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_field_regions import KernelResult

SCHEMA = "cassifi.temporal-field.v1"
REGIONAL_KERNEL_NAME = "temporal-memory"
REGIONAL_MAX_WORK = 4_096
REGIONAL_KERNEL_MAX_WORK = REGIONAL_MAX_WORK
REGIONAL_STATE_SCHEMA = "cassifi.temporal-regional-state.v1"
REGIONAL_RESULT_SCHEMA = "cassifi.regional-kernel-result.v1"
_MAX_ACTIONS = 64
_MAX_OBSERVATIONS = 64
_MAX_EPISODES = 4096
_MAX_STEPS = 131072
_MAX_STATES = 128
_MAX_SKILLS = 64
_LAYERS = 9
_LEGACY_LAYERS = 9


class TemporalFieldError(ValueError):
    """Invalid categorical field, source episode or bounded operation."""


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TemporalFieldError("JSON keys must be strings")
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise TemporalFieldError("value is not bounded canonical JSON") from exc


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise TemporalFieldError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise TemporalFieldError(f"{name} must be a bounded nonempty string")
    return value


def _ids(value: Any, name: str, limit: int, *, allow_empty: bool = False) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TemporalFieldError(f"{name} must be an ordered sequence")
    result = tuple(_identifier(item, name) for item in value)
    if (not result and not allow_empty) or len(result) > limit or len(set(result)) != len(result):
        raise TemporalFieldError(f"{name} must contain unique bounded identifiers")
    return result


def _context(value: Any) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise TemporalFieldError("context must be a mapping or None")
    raw = _canonical(value)
    if len(raw) > 16384:
        raise TemporalFieldError("context exceeds bounded size")
    return _freeze(json.loads(raw))


def _trie(actions: tuple[str, ...], observations: tuple[str, ...],
          episodes: Sequence[Sequence[Mapping[str, str]]]) -> list[dict[tuple[int, int], tuple[int, int]]]:
    nodes: list[dict[tuple[int, int], tuple[int, int]]] = [{}]
    action_codes = {name: index for index, name in enumerate(actions)}
    observation_codes = {name: index for index, name in enumerate(observations)}
    steps = 0
    for episode in episodes:
        if isinstance(episode, (str, bytes)) or not isinstance(episode, Sequence) or not episode:
            raise TemporalFieldError("each episode must be a nonempty ordered sequence")
        current = 0
        for item in episode:
            if not isinstance(item, Mapping) or set(item) != {"action", "observation"}:
                raise TemporalFieldError("episode steps must contain action and observation")
            action, observation = item["action"], item["observation"]
            if not isinstance(action, str) or not isinstance(observation, str) or action not in action_codes or observation not in observation_codes:
                raise TemporalFieldError("episode uses an unknown categorical token")
            steps += 1
            if steps > _MAX_STEPS:
                raise TemporalFieldError("episode source work exceeds bounded capacity")
            key = (action_codes[action], observation_codes[observation])
            edge = nodes[current].get(key)
            if edge is None:
                edge = (len(nodes), 0)
                nodes.append({})
            nodes[current][key] = (edge[0], edge[1] + 1)
            current = edge[0]
    return nodes


def _outcome_evidence(counts: Mapping[int, int]) -> float:
    """Integrated categorical likelihood under the fixed Jeffreys prior.

    Used only to compare a pooled and a split model during induction. These
    are not calibrated outcome probabilities, and no prior counts enter the
    field's observed-exposure planes.
    """
    return (math.lgamma(len(counts) / 2) - math.lgamma(sum(counts.values()) + len(counts) / 2)
            + sum(math.lgamma(count + .5) - math.lgamma(.5) for count in counts.values()))


def _fold(nodes: Mapping[int, Mapping[tuple[int, int], tuple[int, int]]], first: int, second: int
          ) -> tuple[dict[int, dict[tuple[int, int], tuple[int, int]]], dict[int, int], int] | None:
    # Disjoint observations are not positive evidence for an equivalence.
    if nodes[first] and nodes[second] and not nodes[first].keys() & nodes[second].keys():
        return None
    rows = {state: dict(row) for state, row in nodes.items()}
    parents = {state: state for state in rows}

    def root(state: int) -> int:
        while parents[state] != state:
            parents[state] = parents[parents[state]]
            state = parents[state]
        return state

    pending: list[tuple[int, int, tuple[int, int] | None]] = [(first, second, None)]
    agreement = 0
    while pending:
        raw_left, raw_right, cause = pending.pop()
        left, right = sorted((root(raw_left), root(raw_right)))
        if left == right:
            continue
        a, b = rows[left], rows[right]
        recurrent = cause is not None and (
            (cause in a and root(a[cause][0]) in (left, right))
            or (cause in b and root(b[cause][0]) in (left, right))
        )
        if a and b and not a.keys() & b.keys() and not recurrent:
            return None
        actions_a = {key[0] for key in a}
        actions_b = {key[0] for key in b}
        for action in actions_a & actions_b:
            counts_a = {key[1]: edge[1] for key, edge in a.items() if key[0] == action}
            counts_b = {key[1]: edge[1] for key, edge in b.items() if key[0] == action}
            if counts_a.keys() != counts_b.keys():
                return None
            if len(counts_a) > 1:
                pooled = {outcome: count + counts_b[outcome] for outcome, count in counts_a.items()}
                if _outcome_evidence(pooled) < _outcome_evidence(counts_a) + _outcome_evidence(counts_b):
                    return None
            agreement += sum(min(count, counts_b[outcome]) for outcome, count in counts_a.items())
        parents[right] = left
        for key, edge in b.items():
            previous = a.get(key)
            if previous is None:
                a[key] = edge
            else:
                pending.append((previous[0], edge[0], key))
                a[key] = (previous[0], previous[1] + edge[1])
        del rows[right]
    mapping = {state: root(state) for state in parents}
    return ({state: {key: (mapping[edge[0]], edge[1]) for key, edge in row.items()} for state, row in rows.items()},
            mapping, agreement)


def _merge(actions: tuple[str, ...], observations: tuple[str, ...],
           episodes: Sequence[Sequence[Mapping[str, str]]], max_states: int
           ) -> tuple[list[dict[tuple[int, int], tuple[int, int]]], list[set[int]]]:
    ordered = sorted(episodes, key=_canonical)
    nodes = dict(enumerate(_trie(actions, observations, ordered)))
    original_actions = {state: {key[0] for key in row} for state, row in nodes.items()}
    members = {state: {state} for state in nodes}
    red = {0}
    while True:
        blue = sorted({edge[0] for state in red for edge in nodes[state].values()} - red)
        if not blue:
            break
        best = None
        # Resolve one canonical prefix before considering later boundaries.
        # Global exposure ranking can merge sparsely observed later contexts
        # before their distinguishing continuations have been established.
        candidate = blue[0]
        for target in sorted(red):
            trial = _fold(nodes, target, candidate)
            if trial is None:
                continue
            # Empty endpoints may share an unknown sink, never inherit an
            # arbitrary earlier state's unobserved future.
            if trial[2] == 0 and (nodes[target] or nodes[candidate]):
                continue
            if best is None or trial[2] > best[2]:
                best = trial
        if best is None:
            red.add(blue[0])
            if len(red) > max_states:
                raise TemporalFieldError("learned predictive states exceed max_states")
        else:
            nodes, mapping, _ = best
            merged_members: dict[int, set[int]] = {}
            for state, origins in members.items():
                merged_members.setdefault(mapping[state], set()).update(origins)
            members = merged_members
            red = {mapping[state] for state in red}
    order = [0]
    ids = {0: 0}
    for state in order:
        for key in sorted(nodes[state]):
            destination = nodes[state][key][0]
            if destination not in ids:
                ids[destination] = len(order)
                order.append(destination)
    if len(order) > max_states:
        raise TemporalFieldError("learned predictive states exceed max_states")
    rows = [{key: (ids[edge[0]], edge[1]) for key, edge in nodes[state].items()} for state in order]
    universally_observed = [
        set.intersection(*(original_actions[origin] for origin in members[state]))
        for state in order
    ]
    return rows, universally_observed


def _tensor(rows: Sequence[Mapping[tuple[int, int], tuple[int, int]]],
            actions: tuple[str, ...], observations: tuple[str, ...], max_states: int,
            participants: int = 1, universally_observed: Sequence[set[int]] | None = None) -> np.ndarray:
    out = np.zeros((participants, _LAYERS * max_states, len(actions) * len(observations)), dtype=np.float64)
    for state, row in enumerate(rows):
        for (action, observation), (destination, exposure) in row.items():
            column = action * len(observations) + observation
            out[0, state, column] = exposure
            out[0, max_states + state, column] = destination
    out[:, 3 * max_states, 0] = len(rows)
    coverage = out[0, 3 * max_states:4 * max_states, :].reshape(-1)
    required = 2 + max_states * len(actions)
    if coverage.size >= required:
        coverage[1] = 1
        observed = universally_observed if universally_observed is not None else [
            {action for action, _ in row} for row in rows
        ]
        for state, action_codes in enumerate(observed):
            for action in action_codes:
                coverage[2 + state * len(actions) + action] = 1
    out[:, 4 * max_states, 0] = -1
    for lane in range(participants):
        scratch = out[lane, 8 * max_states:9 * max_states, :].reshape(-1)
        capacity = max(0, scratch.size - 2 - max_states)
        if capacity:
            scratch[2 + capacity] = 1
    return out


@dataclass(frozen=True, slots=True)
class TemporalField:
    memory_id: str
    action_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    max_states: int = 128
    context: Mapping[str, Any] = field(default_factory=dict)
    _field: np.ndarray = field(repr=False, compare=False, default_factory=lambda: np.empty(0))
    _source_revision_ids: tuple[str, ...] = field(default=(), repr=False, compare=False)
    _skills: Mapping[str, Mapping[str, Any]] = field(default_factory=dict, repr=False, compare=False)
    _participants: tuple[str, ...] = field(default=("",), repr=False, compare=False)
    _legacy: bool = field(default=False, repr=False, compare=False)
    _projection_state: int | None = field(default=None, repr=False, compare=False)
    _materializations: tuple[Mapping[str, Any], ...] = field(default=(), repr=False, compare=False)
    # Frozen instance: digests and encoded bytes are computed once per value.
    _memo: dict[str, Any] = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _identifier(self.memory_id, "memory_id")
        object.__setattr__(self, "action_ids", _ids(self.action_ids, "action_ids", _MAX_ACTIONS))
        object.__setattr__(self, "observation_ids", _ids(self.observation_ids, "observation_ids", _MAX_OBSERVATIONS))
        object.__setattr__(self, "context", _context(self.context))
        if isinstance(self.max_states, bool) or not isinstance(self.max_states, int) or not 1 <= self.max_states <= _MAX_STATES:
            raise TemporalFieldError("max_states must be in [1,128]")
        if not isinstance(self._field, np.ndarray) or self._field.dtype != np.float64:
            raise TemporalFieldError("field tensor has invalid shape or dtype")
        layers = self._field.shape[1] // self.max_states if self._field.ndim == 3 and self._field.shape[1] % self.max_states == 0 else 0
        if self._field.ndim != 3 or layers not in (_LEGACY_LAYERS, _LAYERS) or self._field.shape[0] < 1 or self._field.shape[2] != len(self.action_ids) * len(self.observation_ids):
            raise TemporalFieldError("field tensor has invalid shape or dtype")
        tensor = np.array(self._field, copy=True, order="C")
        object.__setattr__(self, "_field", tensor)
        if isinstance(self._participants, (str, bytes)) or not isinstance(self._participants, Sequence):
            raise TemporalFieldError("participant_ids must be an ordered sequence")
        participants = tuple(self._participants)
        if not participants or len(participants) > _MAX_EPISODES or any(not isinstance(item, str) or len(item) > 256 for item in participants):
            raise TemporalFieldError("participant ids are invalid")
        if len(participants) != tensor.shape[0] or participants[0] != "" or (len(participants) > 1 and "" in participants[1:]) or len(set(participants)) != len(participants):
            raise TemporalFieldError("participant ids do not match field slices")
        object.__setattr__(self, "_participants", participants)
        revisions = _ids(self._source_revision_ids, "source_revision_ids", _MAX_EPISODES, allow_empty=True)
        for revision in revisions:
            _digest(revision, "source_revision_id")
        object.__setattr__(self, "_source_revision_ids", revisions)
        tensor.flags.writeable = False
        object.__setattr__(self, "_materializations", self._validate_materializations(self._materializations))
        object.__setattr__(self, "_skills", self._validate_skills(self._skills))
        self._validate_tensor()
    @classmethod
    def initial(cls, memory_id: str, *, action_ids: Sequence[str], observation_ids: Sequence[str],
                max_states: int = 128, context: Mapping[str, Any] | None = None) -> TemporalField:
        actions = _ids(action_ids, "action_ids", _MAX_ACTIONS)
        observations = _ids(observation_ids, "observation_ids", _MAX_OBSERVATIONS)
        if isinstance(max_states, bool) or not isinstance(max_states, int) or not 1 <= max_states <= _MAX_STATES:
            raise TemporalFieldError("max_states must be in [1,128]")
        return cls(memory_id, actions, observations, max_states, {} if context is None else context,
                   _tensor([{}], actions, observations, max_states))

    @property
    def field(self) -> np.ndarray:
        return self._field.copy()

    @property
    def state_count(self) -> int:
        return int(self._field[0, 3*self.max_states, 0])

    @property
    def nbytes(self) -> int:
        return int(self._field.nbytes)

    @property
    def source_revision_ids(self) -> tuple[str, ...]:
        return self._source_revision_ids

    @property
    def participant_ids(self) -> tuple[str, ...]:
        return tuple(item for item in self._participants if item)

    @property
    def _layers(self) -> int:
        return self._field.shape[1] // self.max_states

    @property
    def _history_capacity(self) -> int:
        # Plane 8 is flattened; reserve two prefix cells and max_states cells
        # for the candidate bitmap.
        return max(0, self.max_states * self._field.shape[2] - 2 - self.max_states)

    @property
    def _candidate_offset(self) -> int:
        return 2 + self._history_capacity
    @property
    def _has_action_coverage(self) -> bool:
        coverage = self._field[0, 3*self.max_states:4*self.max_states, :].reshape(-1)
        required = 2 + self.max_states * len(self.action_ids)
        return coverage.size >= required and coverage[1] == 1

    def _action_fully_observed(self, state: int, action: int) -> bool:
        if not self._has_action_coverage:
            # Descriptors written before the coverage bitmap remain readable;
            # their next source rebuild derives the conservative coordinates.
            return True
        coverage = self._field[0, 3*self.max_states:4*self.max_states, :].reshape(-1)
        return coverage[2 + state * len(self.action_ids) + action] == 1


    def _lane(self, participant_id: str | None) -> int:
        if participant_id is None:
            return 0
        participant_id = _identifier(participant_id, "participant_id")
        try:
            return self._participants.index(participant_id)
        except ValueError as exc:
            raise TemporalFieldError("participant is not bound") from exc

    def _working(self, participant_id: str | None) -> tuple[int, set[int], bool]:
        lane = self._lane(participant_id)
        m = self.max_states
        current = int(self._field[lane, 2*m, 0])
        if self._projection_state is not None:
            return self._projection_state, {self._projection_state}, False
        if self._legacy:
            candidates = {current} if current >= 0 else set()
        else:
            flat = self._field[lane, 8*m:9*m, :].reshape(-1)
            if self._history_capacity:
                candidates = {state for state in range(self.state_count) if flat[self._candidate_offset + state] == 1}
            else:
                candidates = {current} if current >= 0 else set()
        halted = int(self._field[lane, 5*m, 0]) < 0
        return current, candidates, halted

    def _validate_tensor(self) -> None:
        m, tensor = self.max_states, self._field
        if not np.isfinite(tensor).all() or not np.equal(tensor, np.floor(tensor)).all():
            raise TemporalFieldError("numeric planes must contain finite exact integers")
        count = int(tensor[0, 3*m, 0])
        if not 1 <= count <= m:
            raise TemporalFieldError("learned state count is invalid")
        exposures, destinations = tensor[0, :m, :], tensor[0, m:2*m, :]
        if np.any(exposures < 0) or np.any(exposures > _MAX_STEPS) or float(exposures.sum()) > _MAX_STEPS:
            raise TemporalFieldError("transition exposure exceeds bounded source work")
        active = exposures > 0
        if np.any(destinations < 0) or np.any(destinations[active] >= count) or np.any(destinations[~active] != 0):
            raise TemporalFieldError("numeric transition destination is invalid")
        if np.any(tensor[0, count:m, :]) or np.any(tensor[0, m+count:2*m, :]):
            raise TemporalFieldError("numeric planes contain unreachable state slots")
        coverage = tensor[0, 3*m:4*m, :].reshape(-1)
        coverage_size = 2 + m * len(self.action_ids)
        if coverage.size >= coverage_size and coverage[1] == 1:
            bitmap = coverage[2:coverage_size].reshape(m, len(self.action_ids))
            if np.any((bitmap != 0) & (bitmap != 1)) or np.any(bitmap[count:]):
                raise TemporalFieldError("action coverage coordinates are invalid")
            for state, action in np.argwhere(bitmap):
                start = int(action) * len(self.observation_ids)
                if not np.any(exposures[int(state), start:start + len(self.observation_ids)]):
                    raise TemporalFieldError("action coverage lacks transition evidence")
            if np.any(coverage[coverage_size:] != 0):
                raise TemporalFieldError("action coverage coordinates exceed bounds")
        policies, ranks = tensor[0, 6*m:7*m, :], tensor[0, 7*m:8*m, :]
        if np.any(policies < 0) or np.any(policies > len(self.action_ids)) or np.any(ranks < 0) or np.any(ranks > count):
            raise TemporalFieldError("derived skill coordinates are invalid")
        if np.any((policies == 0) != (ranks == 0)) or np.any(policies[count:]) or np.any(ranks[count:]):
            raise TemporalFieldError("derived skill ranks and actions disagree")
        slots = {spec["slot"] for spec in self._skills.values()}
        if any(np.any(policies[:, slot]) or np.any(ranks[:, slot]) for slot in range(policies.shape[1]) if slot not in slots):
            raise TemporalFieldError("unbound derived skill coordinates")
        for lane in range(tensor.shape[0]):
            current = int(tensor[lane, 2*m, 0])
            lane_count = int(tensor[lane, 3*m, 0])
            last, halted = int(tensor[lane, 4*m, 0]), int(tensor[lane, 5*m, 0])
            if lane_count != count or not (-1 <= current < count) or not -1 <= last < len(self.observation_ids) or halted not in (-1, 0, 1):
                raise TemporalFieldError("working numeric coordinates are invalid")
            if not self._legacy and self._history_capacity:
                flat = tensor[lane, 8*m:9*m, :].reshape(-1)
                hcount = int(flat[0])
                history_flags = int(flat[1])
                if not 0 <= hcount <= self._history_capacity or history_flags < 0 or history_flags & ~7:
                    raise TemporalFieldError("numeric history coordinates are invalid")
                if np.any(flat[2:2+hcount] <= 0) or np.any(flat[2:2+hcount] > len(self.action_ids) * len(self.observation_ids)):
                    raise TemporalFieldError("numeric history event is invalid")
                if np.any(flat[2+hcount:self._candidate_offset] != 0):
                    raise TemporalFieldError("numeric history has noncanonical trailing cells")
                if self._history_capacity:
                    candidates = flat[self._candidate_offset:self._candidate_offset+count]
                    if np.any((candidates != 0) & (candidates != 1)):
                        raise TemporalFieldError("candidate state coordinates are invalid")
                    if halted == 0 and not np.any(candidates):
                        raise TemporalFieldError("running participant has no candidate state")
                    if np.any(flat[self._candidate_offset+count:] != 0):
                        raise TemporalFieldError("candidate state coordinates exceed bounds")
            if lane:
                # Learned transition/policy planes are never cloned into working slices.
                for segment in (0, 1, 6, 7):
                    if np.any(tensor[lane, segment*m:(segment+1)*m, :]):
                        raise TemporalFieldError("participant slice duplicates learned planes")
        if (self._legacy or not self._history_capacity) and np.any(tensor[:, 8*m:9*m, :]):
            raise TemporalFieldError("legacy reserved numeric lane must remain zero")
        # Imported policies must descend their declared safe reachability rank.
        for spec in self._skills.values():
            slot = spec["slot"]
            goals, forbidden = set(spec["goal"]), set(spec["forbidden"])
            for state in np.flatnonzero(policies[:, slot]):
                action = int(policies[state, slot]) - 1
                start = action * len(self.observation_ids)
                outcomes = np.flatnonzero(exposures[state, start:start + len(self.observation_ids)])
                if not outcomes.size:
                    raise TemporalFieldError("skill proposes an unsupported action")
                for observation in outcomes:
                    name = self.observation_ids[observation]
                    successor = int(destinations[state, start + observation])
                    if name in forbidden or (name not in goals and not 0 < ranks[successor, slot] < ranks[state, slot]):
                        raise TemporalFieldError("skill action does not make supported safe progress")

    def _validate_materializations(self, records: Any) -> tuple[Mapping[str, Any], ...]:
        if isinstance(records, (str, bytes)) or not isinstance(records, Sequence) or len(records) > _MAX_EPISODES:
            raise TemporalFieldError("materialization register exceeds bounded capacity")
        normalized: list[Mapping[str, Any]] = []
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, Mapping) or set(record) != {
                "participant_id", "skill_id", "history", "action", "observation",
                "template_destination",
            }:
                raise TemporalFieldError("invalid temporal materialization record")
            participant_id = _identifier(record["participant_id"], "materialization participant_id")
            skill_id = _identifier(record["skill_id"], "materialization skill_id")
            action = _identifier(record["action"], "materialization action")
            observation = _identifier(record["observation"], "materialization observation")
            if action not in self.action_ids or observation not in self.observation_ids:
                raise TemporalFieldError("invalid temporal materialization identity")
            history = record["history"]
            if isinstance(history, (str, bytes)) or not isinstance(history, Sequence) or len(history) > self._history_capacity:
                raise TemporalFieldError("invalid temporal materialization history")
            events: list[Mapping[str, str]] = []
            for event in history:
                if not isinstance(event, Mapping) or set(event) != {"action", "observation"}:
                    raise TemporalFieldError("invalid temporal materialization history event")
                event_action = _identifier(event["action"], "history action")
                event_observation = _identifier(event["observation"], "history observation")
                if event_action not in self.action_ids or event_observation not in self.observation_ids:
                    raise TemporalFieldError("history event leaves fixed codec")
                events.append(MappingProxyType({"action": event_action, "observation": event_observation}))
            destination = record["template_destination"]
            if isinstance(destination, bool) or not isinstance(destination, int) or not 0 <= destination < self.max_states:
                raise TemporalFieldError("invalid temporal materialization destination")
            key = hashlib.sha256(_canonical({
                "participant_id": participant_id, "skill_id": skill_id,
                "history": events, "action": action, "observation": observation,
            })).hexdigest()
            if key in seen:
                raise TemporalFieldError("duplicate temporal materialization")
            seen.add(key)
            normalized.append(MappingProxyType({
                "participant_id": participant_id, "skill_id": skill_id,
                "history": tuple(events), "action": action, "observation": observation,
                "template_destination": destination,
            }))
        return tuple(normalized)

    def _validate_skills(self, skills: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Mapping[str, Any]]:
        if not isinstance(skills, Mapping) or len(skills) > min(_MAX_SKILLS, self._field.shape[2]):
            raise TemporalFieldError("skills exceed bounded policy capacity")
        result, used = {}, set()
        for skill_id, spec in skills.items():
            _identifier(skill_id, "skill_id")
            if not isinstance(spec, Mapping) or set(spec) not in (
                {"goal", "forbidden", "bound_memory", "slot"},
                {"goal", "forbidden", "bound_memory", "slot", "formation_source_count"},
            ):
                raise TemporalFieldError("invalid temporal skill metadata")
            goals = _ids(spec["goal"], "goal observations", len(self.observation_ids))
            forbidden = _ids(spec["forbidden"], "forbidden observations", len(self.observation_ids), allow_empty=True)
            if set(goals).intersection(forbidden) or any(item not in self.observation_ids for item in (*goals, *forbidden)):
                raise TemporalFieldError("skill observations conflict or leave the fixed codec")
            slot = spec["slot"]
            if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < min(_MAX_SKILLS, self._field.shape[2]) or slot in used:
                raise TemporalFieldError("skill slot is invalid or already occupied")
            used.add(slot)
            if _digest(spec["bound_memory"], "skill memory") != self.memory_sha256:
                raise TemporalFieldError("skill is bound to different learned memory")
            formation_source_count = spec.get("formation_source_count", len(self._source_revision_ids))
            if (
                isinstance(formation_source_count, bool)
                or not isinstance(formation_source_count, int)
                or formation_source_count < 0
                or formation_source_count > len(self._source_revision_ids)
            ):
                raise TemporalFieldError("skill formation source count is invalid")
            result[skill_id] = MappingProxyType({
                "goal": goals,
                "forbidden": forbidden,
                "bound_memory": spec["bound_memory"],
                "slot": slot,
                "formation_source_count": formation_source_count,
            })
        return MappingProxyType(result)


    @property
    def skill_ids(self) -> tuple[str, ...]:
        return tuple(self._skills)

    @property
    def formed_skill_ids(self) -> tuple[str, ...]:
        ranks = self._field[0, 7*self.max_states:8*self.max_states, :]
        return tuple(
            skill_id
            for skill_id, spec in self._skills.items()
            if ranks[0, spec["slot"]] > 0
        )

    @property
    def pending_skill_ids(self) -> tuple[str, ...]:
        formed = set(self.formed_skill_ids)
        return tuple(skill_id for skill_id in self._skills if skill_id not in formed)

    @property
    def memory_sha256(self) -> str:
        cached = self._memo.get("memory_sha256")
        if cached is not None:
            return cached
        identity: dict[str, Any] = {
            "schema": SCHEMA, "memory_id": self.memory_id, "action_ids": self.action_ids,
            "observation_ids": self.observation_ids, "max_states": self.max_states,
            "context": _plain(self.context), "source_revision_ids": self.source_revision_ids,
            "state_count": float(self._field[0, 3*self.max_states, 0]),
        }
        if self._materializations:
            identity["materializations"] = _plain(self._materializations)
        digest = hashlib.sha256(_canonical(identity))
        digest.update(self._field[0, :2*self.max_states, :])
        self._memo["memory_sha256"] = result = digest.hexdigest()
        return result

    @property
    def state_sha256(self) -> str:
        cached = self._memo.get("state_sha256")
        if cached is not None:
            return cached
        identity: dict[str, Any] = {"memory_sha256": self.memory_sha256, "skills": _plain(self._skills)}
        if not self._legacy:
            identity["participant_ids"] = list(self.participant_ids)
        if self._materializations:
            identity["materializations"] = _plain(self._materializations)
        digest = hashlib.sha256(_canonical(identity))
        digest.update(self._field)
        self._memo["state_sha256"] = result = digest.hexdigest()
        return result

    def as_dict(self) -> Mapping[str, Any]:
        field_b64 = self._memo.get("field_b64")
        if field_b64 is None:
            self._memo["field_b64"] = field_b64 = base64.b64encode(self._field).decode("ascii")
        result = {"schema": SCHEMA, "memory_id": self.memory_id, "action_ids": list(self.action_ids),
                  "observation_ids": list(self.observation_ids), "max_states": self.max_states,
                  "context": _plain(self.context), "source_revision_ids": list(self.source_revision_ids),
                  "skills": _plain(self._skills), "field_b64": field_b64,
                  "state_sha256": self.state_sha256, "memory_sha256": self.memory_sha256}
        if not self._legacy:
            result["participant_ids"] = list(self.participant_ids)
        if self._materializations:
            result["materializations"] = _plain(self._materializations)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> TemporalField:
        required = {"schema", "memory_id", "action_ids", "observation_ids", "max_states", "context",
                    "source_revision_ids", "skills", "field_b64", "state_sha256", "memory_sha256"}
        allowed = required | {"participant_ids", "materializations"}
        if not isinstance(value, Mapping) or not required.issubset(value) or not set(value).issubset(allowed) or value.get("schema") != SCHEMA:
            raise TemporalFieldError("invalid temporal field descriptor")
        actions = _ids(value["action_ids"], "action_ids", _MAX_ACTIONS)
        observations = _ids(value["observation_ids"], "observation_ids", _MAX_OBSERVATIONS)
        m = value["max_states"]
        if isinstance(m, bool) or not isinstance(m, int) or not 1 <= m <= _MAX_STATES:
            raise TemporalFieldError("max_states must be in [1,128]")
        encoded = value["field_b64"]
        if not isinstance(encoded, str) or len(encoded) % 4:
            raise TemporalFieldError("invalid temporal field encoding")
        try:
            raw = base64.b64decode(encoded, validate=True)
            stride = 8 * m * len(actions) * len(observations)
            if stride <= 0 or len(raw) == 0 or len(raw) % stride:
                raise TemporalFieldError("invalid temporal field byte length")
            tensor = np.frombuffer(raw, dtype=np.float64).reshape((-1, _LAYERS*m, len(actions)*len(observations))).copy()
        except (ValueError, TypeError, TemporalFieldError) as exc:
            raise TemporalFieldError("invalid temporal field bytes") from exc
        participant_ids = value.get("participant_ids")
        if "participant_ids" not in value:
            participants = ("",)
            legacy = True
        else:
            if isinstance(participant_ids, (str, bytes)) or not isinstance(participant_ids, Sequence):
                raise TemporalFieldError("participant_ids must be an ordered sequence")
            participants = ("",) if len(participant_ids) == 0 else (
                "", *(_ids(participant_ids, "participant_ids", _MAX_EPISODES, allow_empty=False)))
            legacy = False
        if len(participants) != tensor.shape[0]:
            raise TemporalFieldError("participant ids do not match field slices")
        try:
            result = cls(
                value["memory_id"], actions, observations, m, value["context"], tensor,
                tuple(value["source_revision_ids"]), value["skills"], participants, legacy,
                None, tuple(value.get("materializations", ())),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TemporalFieldError("invalid temporal field descriptor") from exc
        if _digest(value["state_sha256"], "state_sha256") != result.state_sha256 or _digest(value["memory_sha256"], "memory_sha256") != result.memory_sha256:
            raise TemporalFieldError("temporal field digest mismatch")
        return result

    def _replace(self, *, tensor: np.ndarray | None = None, skills: Mapping[str, Mapping[str, Any]] | None = None,
                 participants: tuple[str, ...] | None = None, revisions: tuple[str, ...] | None = None,
                 legacy: bool | None = None,
                 materializations: tuple[Mapping[str, Any], ...] | None = None) -> TemporalField:
        return replace(self, _field=self._field if tensor is None else tensor,
                       _skills=self._skills if skills is None else skills,
                       _participants=self._participants if participants is None else participants,
                       _source_revision_ids=self._source_revision_ids if revisions is None else revisions,
                       _legacy=self._legacy if legacy is None else legacy,
                       _materializations=self._materializations if materializations is None else materializations,
                       _projection_state=None)
    def _expand_layout(self, participants: tuple[str, ...]) -> np.ndarray:
        tensor = np.zeros((len(participants), _LAYERS * self.max_states, self._field.shape[2]), dtype=np.float64)
        tensor[0] = self._field[0]
        # Legacy and new descriptors share the 9*M geometry.  Legacy plane 8
        # was reserved; initialize the new numeric history/candidate encoding.
        if self._legacy:
            flat = tensor[0, 8*self.max_states:9*self.max_states, :].reshape(-1)
            if self._history_capacity:
                flat[1] = 1  # unknown pre-bind context; inference may continue
                current = int(tensor[0, 2*self.max_states, 0])
                if current >= 0:
                    flat[self._candidate_offset + current] = 1
            else:
                tensor[0, 5*self.max_states, 0] = -1
        for lane in range(1, min(len(participants), self._field.shape[0])):
            tensor[lane, 2*self.max_states:6*self.max_states, :] = self._field[lane, 2*self.max_states:6*self.max_states, :]
            tensor[lane, 8*self.max_states:9*self.max_states, :] = self._field[lane, 8*self.max_states:9*self.max_states, :]
        for lane in range(max(1, self._field.shape[0]), len(participants)):
            tensor[lane, 3*self.max_states, 0] = self.state_count
            tensor[lane, 4*self.max_states, 0] = -1
            if self._history_capacity:
                flat = tensor[lane, 8*self.max_states:9*self.max_states, :].reshape(-1)
                flat[self._candidate_offset] = 1
        return tensor

    def bind(self, participant_id: str, *, known_start: bool = True) -> TemporalField:
        participant_id = _identifier(participant_id, "participant_id")
        if participant_id == "":
            raise TemporalFieldError("participant_id cannot be empty")
        if not isinstance(known_start, bool):
            raise TemporalFieldError("known_start must be boolean")
        if participant_id in self._participants:
            return self if known_start else self.reset(participant_id=participant_id, known_start=False)
        participants = (*self._participants, participant_id)
        tensor = self._expand_layout(participants)
        bound = self._replace(tensor=tensor, participants=participants, legacy=False)
        return bound if known_start else bound.reset(participant_id=participant_id, known_start=False)

    def release(self, participant_id: str) -> TemporalField:
        """Remove one participant lane; learned transitions and skills stay in the shared field."""
        lane = self._lane(participant_id)
        if lane == 0:
            raise TemporalFieldError("participant_id cannot be empty")
        tensor = np.delete(self._field, lane, axis=0)
        participants = tuple(item for index, item in enumerate(self._participants) if index != lane)
        return self._replace(tensor=tensor, participants=participants, legacy=False)

    def _history_codes(self, lane: int) -> tuple[list[tuple[int, int]], int]:
        if self._legacy:
            return [], 1
        if not self._history_capacity:
            return [], int(self._field[lane, 4*self.max_states, 0] >= 0)
        flat = self._field[lane, 8*self.max_states:9*self.max_states, :].reshape(-1)
        count = int(flat[0])
        width = len(self.observation_ids)
        codes = [int(flat[index + 2]) - 1 for index in range(count)]
        return [(code // width, code % width) for code in codes], int(flat[1])

    def _write_history(self, tensor: np.ndarray, lane: int, action: int, observation: int) -> None:
        if self._legacy or not self._history_capacity:
            return
        flat = tensor[lane, 8*self.max_states:9*self.max_states, :].reshape(-1)
        count = int(flat[0])
        if count < self._history_capacity:
            flat[count + 2] = action * len(self.observation_ids) + observation + 1
            flat[0] = count + 1
        else:
            flat[1] = int(flat[1]) | 1

    def _next_states(self, candidates: set[int], action: int, observation: int) -> tuple[set[int], list[int]]:
        """Retain a bounded context envelope across unknown successors."""
        width = len(self.observation_ids)
        start = action * width
        next_states, missing = set(), []
        for state in sorted(candidates):
            exposures = self._field[0, state, start:start + width]
            if not np.any(exposures):
                missing.append(state)
            elif exposures[observation] > 0:
                next_states.add(int(self._field[0, self.max_states + state, start + observation]))
        if missing or not next_states:
            # Missing support marks the context unresolved, but supported
            # candidates remain the strongest field evidence.  Only fall back
            # to the global envelope when no carried candidate explains the
            # observation; merging both sets manufactures uncertainty and can
            # drown out a learned continuation.
            if not next_states:
                compatible = set()
                for state in range(self.state_count):
                    exposures = self._field[0, state, start:start + width]
                    if np.any(exposures) and exposures[observation] > 0:
                        compatible.add(int(self._field[0, self.max_states + state, start + observation]))
                if compatible and self._skills:
                    reachable = {
                        destination
                        for destination in compatible
                        if any(
                            self._field[
                                0,
                                7 * self.max_states + destination,
                                spec["slot"],
                            ] > 0
                            for spec in self._skills.values()
                        )
                    }
                    if reachable:
                        compatible = reachable
                next_states.update(compatible or candidates)
        return next_states, missing

    def _replay(
        self, events: Sequence[tuple[int, int]], overflow: bool, *, known_start: bool,
    ) -> tuple[set[int], bool, bool, bool]:
        if overflow:
            return set(), True, False, False
        candidates = {0} if known_start else set(range(self.state_count))
        unknown = False
        uncovered = False
        for action, observation in events:
            candidates, missing = self._next_states(candidates, action, observation)
            unknown = bool(missing) or not candidates or (unknown and len(candidates) != 1)
            uncovered = uncovered or bool(missing)
        return candidates, False, unknown, uncovered

    def learn(self, episodes: Sequence[Sequence[Mapping[str, str]]], *, source_revision_ids: Sequence[str]) -> tuple[TemporalField, Mapping[str, Any]]:
        if isinstance(episodes, (str, bytes)) or not isinstance(episodes, Sequence) or not 1 <= len(episodes) <= _MAX_EPISODES:
            raise TemporalFieldError("episodes exceed bounded capacity")
        revisions = _ids(source_revision_ids, "source_revision_ids", _MAX_EPISODES)
        for revision in revisions:
            _digest(revision, "source_revision_id")
        specs = {key: dict(spec) for key, spec in self._skills.items()}
        previously_formed = set(self.formed_skill_ids)
        rows, universally_observed = _merge(
            self.action_ids, self.observation_ids, episodes, self.max_states,
        )
        old_history = [self._history_codes(lane) for lane in range(self._field.shape[0])]
        tensor = _tensor(rows, self.action_ids, self.observation_ids, self.max_states, len(self._participants),
                         universally_observed)
        materializations = tuple(dict(item) for item in self._materializations)
        if materializations:
            # Reapply canonical state-conditioned writes after rebuilding the
            # learned transition planes.  The register is intentionally
            # bounded and replayed from its provenance history, not from the
            # prior numeric source-state id.
            base = self._replace(
                tensor=tensor, skills={}, revisions=tuple(sorted(revisions)),
                legacy=False, materializations=materializations,
            )
            for record in materializations:
                history = []
                for item in record["history"]:
                    history.append((
                        self.action_ids.index(item["action"]),
                        self.observation_ids.index(item["observation"]),
                    ))
                candidates, halted, unknown, uncovered = base._replay(
                    history, False, known_start=True,
                )
                if halted or unknown or uncovered or len(candidates) != 1:
                    raise TemporalFieldError("materialization provenance is no longer uniquely replayable")
                source_state = next(iter(candidates))
                action_code = self.action_ids.index(record["action"])
                observation_code = self.observation_ids.index(record["observation"])
                column = action_code * len(self.observation_ids) + observation_code
                destination = int(base._field[0, self.max_states, column])
                if destination < 0:
                    raise TemporalFieldError("materialization target is no longer rooted")
                existing = tensor[0, self.max_states + source_state, column]
                if tensor[0, source_state, column] > 0 and int(existing) != destination:
                    raise TemporalFieldError("materialization conflicts with rebuilt transition")
                tensor[0, source_state, column] = 1.0
                tensor[0, self.max_states + source_state, column] = float(destination)
        successor = self._replace(
            tensor=tensor, skills={}, revisions=tuple(sorted(revisions)),
            legacy=False, materializations=materializations,
        )
        if specs:
            # A revised model changes numeric state IDs; retain skill identity and
            # goals while recomputing policy/rank against the new shared planes.
            successor, _ = successor._condense_all(specs)
        unresolved = []
        tensor = successor._field.copy()
        for lane, ((events, flags), participant) in enumerate(zip(old_history, self._participants)):
            if not self._legacy and self._history_capacity:
                old_flat = self._field[lane, 8*self.max_states:9*self.max_states, :].reshape(-1)
                new_flat = tensor[lane, 8*self.max_states:9*self.max_states, :].reshape(-1)
                new_flat[:self._candidate_offset] = old_flat[:self._candidate_offset]
                new_flat[self._candidate_offset:] = 0
            candidates, halted, unknown, uncovered = successor._replay(
                events, bool(flags & 1), known_start=not bool(flags & 2),
            )
            tensor[lane, 2*successor.max_states, 0] = min(candidates) if candidates else -1
            tensor[lane, 4*successor.max_states, 0] = self._field[lane, 4*self.max_states, 0]
            tensor[lane, 5*successor.max_states, 0] = -1 if halted else int(unknown)
            if successor._history_capacity:
                flat = tensor[lane, 8*successor.max_states:9*successor.max_states, :].reshape(-1)
                flat[1] = (int(flat[1]) & 3) | (4 if uncovered else 0)
                flat[successor._candidate_offset:] = 0
                for state in candidates:
                    flat[successor._candidate_offset + state] = 1
            if halted or unknown or len(candidates) != 1:
                unresolved.append(participant or None)
        successor = successor._replace(tensor=tensor)
        currently_formed = set(successor.formed_skill_ids)
        receipt = {
            "memory_id": self.memory_id,
            "previous_state_sha256": self.state_sha256,
            "state_sha256": successor.state_sha256,
            "memory_sha256": successor.memory_sha256,
            "state_count": successor.state_count,
            "source_revision_ids": list(successor.source_revision_ids),
            "status": "unresolved" if unresolved else "resolved",
            "unresolved_participants": unresolved,
            "formed_skills": sorted(currently_formed - previously_formed),
            "withdrawn_skills": sorted(previously_formed - currently_formed),
            "available_skills": sorted(currently_formed),
            "pending_skills": list(successor.pending_skill_ids),
            "algorithm": "evidence-scored-continuation-merge",
            "statistical_limit": "empirical categorical support; no calibration claim",
        }
        return successor, receipt

    def _predict_for(self, candidates: set[int], action: str, *, unknown: bool = False) -> Mapping[str, Any]:
        if action not in self.action_ids:
            raise TemporalFieldError("unknown action")
        m, n = self.max_states, len(self.observation_ids)
        code = self.action_ids.index(action)
        totals = np.zeros(n, dtype=np.float64)
        successors: dict[int, set[int]] = {}
        missing = []
        for state in sorted(candidates):
            exposures = self._field[0, state, code*n:(code+1)*n]
            if not np.any(exposures):
                missing.append(state)
                continue
            for observation in np.flatnonzero(exposures):
                totals[observation] += exposures[observation]
                successors.setdefault(int(observation), set()).add(int(self._field[0, m + state, code*n + observation]))
        total = int(totals.sum())
        outcomes = [{"observation": self.observation_ids[int(index)], "count": int(totals[int(index)]),
                     **({"next_state": next(iter(successors[int(index)]))} if len(successors[int(index)]) == 1 else {})}
                    for index in np.flatnonzero(totals)]
        supported = bool(candidates) and not missing and not unknown and total > 0
        return {"action": action,
                "probabilities": {item["observation"]: item["count"] / total for item in outcomes} if supported else {},
                "supported": supported,
                "support": {"state": min(candidates) if candidates else -1, "exposure": total, "outcomes": outcomes,
                            "missing_states": missing, "unknown_successor": unknown or not candidates},
                "explain": "empirical support from every carried predictive state" if supported else "incomplete transition or history support"}

    def context_status(self, *, participant_id: str | None = None) -> Mapping[str, Any]:
        lane = self._lane(participant_id)
        _, candidates, halted = self._working(participant_id)
        if self._projection_state is not None:
            return {
                "status": "counterfactual",
                "candidate_states": sorted(candidates),
                "uncovered_history": False,
            }
        flags = 0
        if not self._legacy and self._history_capacity:
            flat = self._field[lane, 8*self.max_states:9*self.max_states, :].reshape(-1)
            flags = int(flat[1])
        unknown = self._field[lane, 5*self.max_states, 0] > 0
        if halted:
            status = "unavailable"
        elif unknown or not candidates:
            status = "unresolved"
        elif flags & 4:
            status = "recovered"
        elif flags & 2:
            status = "unknown-start"
        else:
            status = "supported"
        return {
            "status": status,
            "candidate_states": sorted(candidates),
            "uncovered_history": bool(flags & 4),
            "unknown_start": bool(flags & 2),
        }

    def predict(self, action: str, *, participant_id: str | None = None) -> Mapping[str, Any]:
        _, candidates, halted = self._working(participant_id)
        context = self.context_status(participant_id=participant_id)
        unknown = self._projection_state is None and (halted or context["status"] == "unresolved")
        result = dict(self._predict_for(candidates, action, unknown=bool(unknown)))
        support = dict(result["support"])
        support["context"] = context
        result["support"] = support
        return result

    def consume(self, action: str, observation: str, *, participant_id: str | None = None) -> tuple[TemporalField, Mapping[str, Any]]:
        if action not in self.action_ids or observation not in self.observation_ids:
            raise TemporalFieldError("unknown action or observation")
        if self._projection_state is not None:
            raise TemporalFieldError("counterfactual projections cannot consume events")
        lane = self._lane(participant_id)
        current, candidates, halted = self._working(participant_id)
        if halted:
            return self, {"action": action, "observation": observation, "supported": False, "state": current, "halted": True,
                          "unknown_successor": True, "previous_state_sha256": self.state_sha256, "state_sha256": self.state_sha256,
                          "context": self.context_status(participant_id=participant_id)}
        action_code, observation_code = self.action_ids.index(action), self.observation_ids.index(observation)
        next_candidates, missing = self._next_states(candidates, action_code, observation_code)
        was_unknown = self._field[lane, 5*self.max_states, 0] > 0
        unknown = bool(missing) or not next_candidates or (was_unknown and len(next_candidates) != 1)
        tensor = self._field.copy()
        self._write_history(tensor, lane, action_code, observation_code)
        current = min(next_candidates) if next_candidates else -1
        tensor[lane, 2*self.max_states, 0] = current
        tensor[lane, 4*self.max_states, 0] = observation_code
        # 0 = the current context is supported; 1 = current transition support
        # is incomplete; -1 = replay unavailable after history overflow.
        tensor[lane, 5*self.max_states, 0] = int(unknown)
        if not self._legacy and self._history_capacity:
            flat = tensor[lane, 8*self.max_states:9*self.max_states, :].reshape(-1)
            if missing:
                # Retain the earlier support gap after later supported evidence
                # narrows the active candidate context to one learned state.
                flat[1] = int(flat[1]) | 4
            flat[self._candidate_offset:] = 0
            for state in next_candidates:
                flat[self._candidate_offset + state] = 1
        successor = self._replace(tensor=tensor)
        context = successor.context_status(participant_id=participant_id)
        return successor, {"action": action, "observation": observation, "supported": not bool(unknown),
                           "state": current, "halted": False, "unknown_successor": bool(unknown), "missing_states": missing,
                           "context": context, "previous_state_sha256": self.state_sha256,
                           "state_sha256": successor.state_sha256}

    def reset(self, *, participant_id: str | None = None, known_start: bool = True) -> TemporalField:
        if not isinstance(known_start, bool):
            raise TemporalFieldError("known_start must be boolean")
        if self._projection_state is not None:
            return self
        lane = self._lane(participant_id)
        tensor = self._field.copy()
        m = self.max_states
        tensor[lane, 2*m, 0] = 0
        flat = tensor[lane, 8*m:9*m, :].reshape(-1)
        flat[:] = 0
        if self._history_capacity:
            if not known_start:
                flat[1] = 2  # History starts at an unknown learned state, not the root.
                flat[self._candidate_offset:self._candidate_offset+self.state_count] = 1
            else:
                flat[self._candidate_offset] = 1
        return self._replace(tensor=tensor, legacy=False)

    def _condense_all(self, specs: Mapping[str, Mapping[str, Any]]) -> tuple[TemporalField, Mapping[str, Any]]:
        result = self
        for skill_id, spec in specs.items():
            result, _ = result.condense_skill(
                skill_id,
                goal_observations=spec["goal"],
                forbidden_observations=spec["forbidden"],
                _slot=spec["slot"],
                _bound_memory=result.memory_sha256,
            )
            restored = dict(result._skills[skill_id])
            restored["formation_source_count"] = spec.get(
                "formation_source_count",
                len(self._source_revision_ids),
            )
            skills = dict(result._skills)
            skills[skill_id] = restored
            result = result._replace(skills=skills)
        return result, {"skills": list(specs)}
    def candidate_states(self, *, participant_id: str | None = None) -> tuple[int, ...]:
        _, candidates, halted = self._working(participant_id)
        return tuple(sorted(candidates)) if not halted else ()

    def history(self, *, participant_id: str | None = None) -> tuple[Mapping[str, str], ...]:
        lane = self._lane(participant_id)
        events, _ = self._history_codes(lane)
        return tuple(MappingProxyType({"action": self.action_ids[action], "observation": self.observation_ids[observation]}) for action, observation in events)

    def at_state(self, state: int) -> TemporalField:
        if isinstance(state, bool) or not isinstance(state, int) or not 0 <= state < self.state_count:
            raise TemporalFieldError("counterfactual state is out of range")
        projection = copy.copy(self)
        object.__setattr__(projection, "_projection_state", state)
        return projection


    def _derive_skill_policy(
        self,
        *,
        goal_observations: Sequence[str],
        forbidden_observations: Sequence[str] = (),
    ) -> tuple[tuple[str, ...], tuple[str, ...], np.ndarray, np.ndarray]:
        goals = _ids(goal_observations, "goal observations", len(self.observation_ids))
        forbidden = _ids(
            forbidden_observations,
            "forbidden observations",
            len(self.observation_ids),
            allow_empty=True,
        )
        if set(goals).intersection(forbidden) or any(
            item not in self.observation_ids for item in (*goals, *forbidden)
        ):
            raise TemporalFieldError("skill observations conflict or leave the fixed codec")
        m, actions, observations = self.max_states, len(self.action_ids), len(self.observation_ids)
        states = self.state_count
        exposures = self._field[0, :m, :].reshape(m, actions, observations)[:states]
        destinations = (
            self._field[0, m:2*m, :]
            .reshape(m, actions, observations)
            .astype(np.int64)[:states]
        )
        goal = np.array([name in goals for name in self.observation_ids])
        bad = np.array([name in forbidden for name in self.observation_ids])
        supported = exposures > 0
        ranks = np.zeros(states, dtype=np.int64)
        policy = np.zeros(states, dtype=np.int64)
        while True:
            improved = False
            for state in range(states):
                options = []
                for action in range(actions):
                    outcomes = supported[state, action]
                    if not outcomes.any() or np.any(bad[outcomes]):
                        continue
                    successors = destinations[state, action, outcomes]
                    if np.all(goal[np.flatnonzero(outcomes)] | (ranks[successors] > 0)):
                        cost = 1 + int(np.max(np.where(
                            goal[np.flatnonzero(outcomes)],
                            0,
                            ranks[successors],
                        )))
                        options.append((cost, action))
                if options:
                    best = min(options)
                    if (
                        ranks[state] == 0
                        or best[0] < ranks[state]
                        or (best[0] == ranks[state] and best[1] < policy[state])
                    ):
                        ranks[state], policy[state] = best
                        improved = True
            if not improved:
                break
        return goals, forbidden, ranks, policy


    def condense_skill(self, skill_id: str, *, goal_observations: Sequence[str], forbidden_observations: Sequence[str] = (), _slot: int | None = None, _bound_memory: str | None = None) -> tuple[TemporalField, Mapping[str, Any]]:
        _identifier(skill_id, "skill_id")
        goals, forbidden, ranks, policy = self._derive_skill_policy(
            goal_observations=goal_observations,
            forbidden_observations=forbidden_observations,
        )
        m, states = self.max_states, self.state_count
        specs = dict(self._skills)
        if skill_id in specs:
            slot = specs[skill_id]["slot"]
        elif _slot is not None:
            slot = _slot
        else:
            used = {spec["slot"] for spec in specs.values()}
            slot = next((index for index in range(min(_MAX_SKILLS, self._field.shape[2])) if index not in used), None)
        if slot is None:
            raise TemporalFieldError("skill policy capacity exceeded")
        tensor = self._field.copy()
        tensor[0, 6*m:7*m, slot] = 0
        tensor[0, 7*m:8*m, slot] = 0
        tensor[0, 6*m:6*m+states, slot] = np.where(ranks > 0, policy + 1, 0)
        tensor[0, 7*m:7*m+states, slot] = ranks
        bound = self.memory_sha256 if _bound_memory is None else _bound_memory
        formation_source_count = (
            len(self._source_revision_ids)
            if _bound_memory is None or skill_id not in specs
            else specs[skill_id]["formation_source_count"]
        )
        specs[skill_id] = {
            "goal": goals,
            "forbidden": forbidden,
            "bound_memory": bound,
            "slot": slot,
            "formation_source_count": formation_source_count,
        }
        successor = self._replace(tensor=tensor, skills=specs)
        formed = ranks[0] > 0
        return successor, {
            "skill_id": skill_id,
            "bound_memory_sha256": successor.memory_sha256,
            "supported_states": int(np.count_nonzero(ranks)),
            "start_state_supported": bool(formed),
            "status": "formed" if formed else "pending",
            "state_sha256": successor.state_sha256,
        }

    def _policy_action(
        self,
        *,
        skill_id: str | None,
        goals: Sequence[str],
        ranks: np.ndarray,
        policy: np.ndarray,
        participant_id: str | None = None,
    ) -> Mapping[str, Any]:
        _, candidates, halted = self._working(participant_id)
        last = int(self._field[self._lane(participant_id), 4*self.max_states, 0])
        label = {"skill_id": skill_id} if skill_id is not None else {}
        if self._projection_state is None and last >= 0 and self.observation_ids[last] in goals:
            return {**label, "status": "complete", "action": None,
                    "explain": "goal observation was actually consumed"}
        context = self.context_status(participant_id=participant_id)
        goal_bridge = False
        if context["status"] == "unresolved" and skill_id is not None and candidates:
            spec = self._skills.get(skill_id)
            if spec is not None and spec["formation_source_count"] < len(self._source_revision_ids):
                bridge_codes = {
                    int(policy[state]) if ranks[state] > 0 else -1
                    for state in candidates
                }
                action_code = next(iter(bridge_codes), -1)
                repeat_after_gap = False
                events, _ = self._history_codes(self._lane(participant_id))
                if events and events[-1][0] == action_code:
                    previous_action, previous_observation = events[-1]
                    width = len(self.observation_ids)
                    repeat_after_gap = not all(
                        np.any(self._field[0, state, previous_action * width:(previous_action + 1) * width])
                        and self._field[
                            0,
                            state,
                            previous_action * width + previous_observation,
                        ] > 0
                        for state in candidates
                    )
                goal_bridge = (
                    len(bridge_codes) == 1
                    and action_code >= 0
                    and not repeat_after_gap
                    and all(
                        self._action_fully_observed(state, action_code)
                        for state in candidates
                    )
                )
        if halted or not candidates or (context["status"] == "unresolved" and not goal_bridge):
            return {**label, "status": "unresolved", "action": None,
                    "context": context,
                    "explain": "current context lacks complete transition support or cannot be replayed"}
        codes = {int(policy[state]) if ranks[state] > 0 else -1 for state in candidates}
        if len(codes) != 1 or -1 in codes:
            return {**label, "status": "unresolved", "action": None,
                    "context": context,
                    "explain": "candidate states do not agree on a supported safe action"}
        action_code = next(iter(codes))
        if not self._legacy and self._history_capacity:
            flat = self._field[
                self._lane(participant_id),
                8*self.max_states:9*self.max_states,
                :,
            ].reshape(-1)
            if int(flat[1]) & 4 and any(
                not self._action_fully_observed(state, action_code) for state in candidates
            ):
                return {**label, "status": "unresolved", "action": None,
                        "context": context,
                        "explain": "recovered context lacks complete action coverage"}
        action = self.action_ids[action_code]
        remaining = max(int(ranks[state]) for state in candidates)
        return {**label, "status": "proposed", "action": action,
                "remaining_steps": remaining, "supported_states": len(candidates),
                "state_sha256": self.state_sha256, "context": context,
                "explain": "supported decreasing-rank action"}

    def skill_pool_signal(self, skill_id: str) -> Mapping[str, Any]:
        """Project supported safe-policy ranks onto seven longitudinal pools.

        The projection is a fixed bridge codec, not a second learned model:
        rank one maps to the first pool, the largest represented rank maps to
        the seventh, and intermediate ranks are spaced linearly.  The unit
        signal therefore carries temporal-distance structure while its energy
        remains the responsibility of the continuous resonant field.
        """
        _identifier(skill_id, "skill_id")
        spec = self._skills.get(skill_id)
        if spec is None:
            return {
                "schema": "cassifi.temporal-skill-pool-signal.v1",
                "skill_id": skill_id,
                "status": "absent",
                "mapping": "safe-reachability-rank-linear-seven-pool-v1",
                "supported_states": 0,
                "maximum_rank": 0,
                "pool_signal": [0.0] * 7,
            }
        ranks = self._field[
            0,
            7 * self.max_states:8 * self.max_states,
            spec["slot"],
        ]
        supported = np.flatnonzero(ranks > 0)
        signal = np.zeros(7, dtype=np.float64)
        maximum_rank = int(np.max(ranks[supported])) if len(supported) else 0
        if maximum_rank == 1:
            signal[0] = float(len(supported))
        elif maximum_rank > 1:
            for state in supported:
                rank = int(ranks[state])
                pool = int(math.floor(6 * (rank - 1) / (maximum_rank - 1) + 0.5))
                signal[pool] += 1.0
        norm = float(np.linalg.norm(signal))
        if norm:
            signal /= norm
        return {
            "schema": "cassifi.temporal-skill-pool-signal.v1",
            "skill_id": skill_id,
            "status": "formed" if ranks[0] > 0 else "pending",
            "mapping": "safe-reachability-rank-linear-seven-pool-v1",
            "supported_states": int(len(supported)),
            "maximum_rank": maximum_rank,
            "pool_signal": signal.tolist(),
        }

    def episode_pool_signals(
        self,
        episode: Sequence[Mapping[str, str]],
        *,
        previous: TemporalField | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        """Project admitted observations into field-derived skill coordinates.

        The projection is read-only.  A represented destination contributes
        the safe skills reachable there, a goal or forbidden observation
        contributes its registered skill orientation, and an observation
        absent from the predecessor weakens predecessor policies that selected
        the observed action.
        """
        _trie(self.action_ids, self.observation_ids, [episode])
        if previous is not None and (
            not isinstance(previous, TemporalField)
            or previous.memory_id != self.memory_id
            or previous.action_ids != self.action_ids
            or previous.observation_ids != self.observation_ids
        ):
            raise TemporalFieldError(
                "episode coupling predecessor is incompatible"
            )

        action_codes = {
            name: index for index, name in enumerate(self.action_ids)
        }
        observation_codes = {
            name: index for index, name in enumerate(self.observation_ids)
        }
        current_states = {0}
        previous_states = {0} if previous is not None else set()
        rows: list[Mapping[str, Any]] = []
        for step_index, step in enumerate(episode):
            action = step["action"]
            observation = step["observation"]
            action_code = action_codes[action]
            observation_code = observation_codes[observation]
            source_states = set(current_states)
            current_states, current_missing = self._next_states(
                source_states, action_code, observation_code
            )
            if current_missing or not current_states:
                raise TemporalFieldError(
                    "admitted episode is not represented by the learned field"
                )

            predecessor_states = set(previous_states)
            previous_missing: list[int] = []
            if previous is not None and predecessor_states:
                previous_states, previous_missing = previous._next_states(
                    predecessor_states, action_code, observation_code
                )
            else:
                previous_states = set()
            mismatch = previous is not None and (
                not predecessor_states
                or bool(previous_missing)
                or not previous_states
            )

            signal = np.zeros(7, dtype=np.float64)
            contributions: list[Mapping[str, Any]] = []
            if mismatch and previous is not None and predecessor_states:
                for skill_id, spec in sorted(
                    previous._skills.items(),
                    key=lambda item: (int(item[1]["slot"]), item[0]),
                ):
                    slot = int(spec["slot"])
                    ranks = previous._field[
                        0,
                        7 * previous.max_states:8 * previous.max_states,
                        slot,
                    ]
                    policy = previous._field[
                        0,
                        6 * previous.max_states:7 * previous.max_states,
                        slot,
                    ]
                    matched = sum(
                        ranks[state] > 0
                        and int(policy[state]) == action_code + 1
                        for state in predecessor_states
                    )
                    if not matched:
                        continue
                    weight = -float(matched) / float(len(predecessor_states))
                    projection = previous.skill_pool_signal(skill_id)
                    signal += weight * np.asarray(
                        projection["pool_signal"], dtype=np.float64
                    )
                    contributions.append({
                        "skill_id": skill_id,
                        "orientation": weight,
                        "reason": "prediction-mismatch",
                        "source": "predecessor-field",
                    })

            for skill_id, spec in sorted(
                self._skills.items(),
                key=lambda item: (int(item[1]["slot"]), item[0]),
            ):
                slot = int(spec["slot"])
                ranks = self._field[
                    0,
                    7 * self.max_states:8 * self.max_states,
                    slot,
                ]
                if observation in spec["forbidden"]:
                    weight = -1.0
                    reason = "forbidden-outcome"
                elif observation in spec["goal"]:
                    weight = 1.0
                    reason = "goal-outcome"
                else:
                    reachable = [
                        int(ranks[state])
                        for state in current_states
                        if ranks[state] > 0
                    ]
                    if not reachable:
                        continue
                    weight = 1.0 / float(max(1, min(reachable)))
                    reason = "reachable-context"
                projection = self.skill_pool_signal(skill_id)
                signal += weight * np.asarray(
                    projection["pool_signal"], dtype=np.float64
                )
                contributions.append({
                    "skill_id": skill_id,
                    "orientation": weight,
                    "reason": reason,
                    "source": "learned-field",
                })

            norm = float(np.linalg.norm(signal))
            if norm:
                signal /= norm
            reasons = {row["reason"] for row in contributions}
            if "forbidden-outcome" in reasons:
                event_kind = "forbidden-observation"
            elif "goal-outcome" in reasons:
                event_kind = "goal-observation"
            elif mismatch:
                event_kind = "mismatch-observation"
            elif contributions:
                event_kind = "context-observation"
            else:
                event_kind = "unrepresented-observation"
            rows.append({
                "schema": "cassifi.temporal-event-pool-signal.v1",
                "step_index": step_index,
                "action": action,
                "observation": observation,
                "event_kind": event_kind,
                "expected_by_predecessor": previous is not None and not mismatch,
                "source_states": sorted(source_states),
                "destination_states": sorted(current_states),
                "predecessor_source_states": sorted(predecessor_states),
                "predecessor_destination_states": sorted(previous_states),
                "contributions": contributions,
                "pool_signal": signal.tolist(),
                "signal_norm_before_normalization": norm,
            })
        return tuple(rows)


    def admissible_skill_actions(
        self,
        skill_ids: Sequence[str] | None = None,
        *,
        participant_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Return fixed, order-independent records for every requested skill.

        This is a categorical readout only.  It does not rank multiple
        supported skills and it does not mutate learned or working state.
        """
        if participant_id is not None:
            _identifier(participant_id, "participant_id")
        presented = (
            tuple(
                skill_id
                for skill_id, _ in sorted(
                    self._skills.items(),
                    key=lambda item: (int(item[1]["slot"]), item[0]),
                )
            )
            if skill_ids is None
            else _ids(skill_ids, "skill_ids", _MAX_SKILLS, allow_empty=True)
        )
        candidates: list[Mapping[str, Any]] = []
        excluded: list[Mapping[str, Any]] = []
        for skill_id in presented:
            readout = dict(self.skill_action(skill_id, participant_id=participant_id))
            spec = self._skills.get(skill_id)
            signal = self.skill_pool_signal(skill_id)
            semantic = {
                "action": readout.get("action"),
                "context": readout.get("context"),
                "forbidden_observations": (
                    [] if spec is None else list(spec["forbidden"])
                ),
                "goal_observations": [] if spec is None else list(spec["goal"]),
                "memory_id": self.memory_id,
                "participant_id": participant_id,
                "pool_signal": signal["pool_signal"],
                "remaining_steps": readout.get("remaining_steps"),
                "safe_policy": readout.get("status") == "proposed",
                "skill_id": skill_id,
                "slot": None if spec is None else int(spec["slot"]),
                "state_sha256": self.state_sha256,
                "supported_states": readout.get("supported_states"),
            }
            candidate_sha256 = hashlib.sha256(_canonical(semantic)).hexdigest()
            record = {
                **semantic,
                "candidate_sha256": candidate_sha256,
                "status": readout["status"],
                "explain": readout["explain"],
            }
            if readout["status"] == "proposed":
                candidates.append(record)
            else:
                excluded.append(record)
        candidates.sort(key=lambda row: row["candidate_sha256"])
        excluded.sort(key=lambda row: row["candidate_sha256"])
        candidate_set_sha256 = hashlib.sha256(
            _canonical([row["candidate_sha256"] for row in candidates])
        ).hexdigest()
        return {
            "schema": "cassifi.temporal-admissible-skill-actions.v1",
            "memory_id": self.memory_id,
            "participant_id": participant_id,
            "state_sha256": self.state_sha256,
            "memory_sha256": self.memory_sha256,
            "presented_skill_ids": list(presented),
            "presentation_order_sha256": hashlib.sha256(
                _canonical(list(presented))
            ).hexdigest(),
            "candidate_set_sha256": candidate_set_sha256,
            "candidates": candidates,
            "excluded": excluded,
            "memory_unchanged": True,
        }

    def skill_action(self, skill_id: str, *, participant_id: str | None = None) -> Mapping[str, Any]:
        _identifier(skill_id, "skill_id")
        spec = self._skills.get(skill_id)
        if spec is None:
            return {"skill_id": skill_id, "status": "unresolved", "action": None,
                    "explain": "skill absent"}
        slot = spec["slot"]
        return self._policy_action(
            skill_id=skill_id,
            goals=spec["goal"],
            ranks=self._field[0, 7*self.max_states:8*self.max_states, slot],
            policy=self._field[0, 6*self.max_states:7*self.max_states, slot] - 1,
            participant_id=participant_id,
        )
    def synthesize_transition(
        self, skill_id: str, *, participant_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Read-only state-conditioned proposal; never writes canonical planes."""
        _identifier(skill_id, "skill_id")
        spec = self._skills.get(skill_id)
        context = self.context_status(participant_id=participant_id)
        source_state, candidates, _ = self._working(participant_id)
        lane_id = "" if participant_id is None else _identifier(participant_id, "participant_id")
        source = {
            "memory_id": self.memory_id, "participant_id": lane_id,
            "state": source_state, "candidate_states": sorted(candidates),
            "history": [dict(item) for item in self.history(participant_id=participant_id)],
            "state_sha256": self.state_sha256, "memory_sha256": self.memory_sha256,
        }
        base: dict[str, Any] = {
            "schema": "cassifi.temporal-synthesized-transition.v1",
            "status": "unresolved", "memory_id": self.memory_id, "skill_id": skill_id,
            "participant_id": lane_id, "source": source, "action": None,
            "expected_observations": [], "template": None, "context": context,
            "canonical_support": False, "evidence_class": "derived-hypothesis",
            "observed": False, "execution_authorized": False,
        }
        reason = None
        if spec is None:
            reason = "unknown-skill"
        elif context["status"] != "supported" or len(candidates) != 1:
            reason = "ambiguous-or-unresolved-current-context"
        elif self.memory_sha256 != spec["bound_memory"]:
            reason = "stale-skill-memory"
        else:
            slot = int(spec["slot"])
            ranks = self._field[0, 7*self.max_states:8*self.max_states, slot]
            policy = self._field[0, 6*self.max_states:7*self.max_states, slot]
            if int(ranks[0]) != 1 or int(policy[0]) <= 0:
                reason = "target-root-policy-not-deterministic-rank-one"
            else:
                action_code = int(policy[0]) - 1
                width = len(self.observation_ids)
                root_start = action_code * width
                root_exposures = self._field[0, 0, root_start:root_start + width]
                outcomes = [int(index) for index in np.flatnonzero(root_exposures)]
                if len(outcomes) != 1:
                    reason = "target-root-outcome-ambiguous"
                else:
                    observation_code = outcomes[0]
                    observation = self.observation_ids[observation_code]
                    if observation in spec["forbidden"]:
                        reason = "target-root-outcome-forbidden"
                    else:
                        destination = int(self._field[0, self.max_states, root_start + observation_code])
                        source_state = next(iter(candidates))
                        source_start = source_state * width * len(self.action_ids) + root_start
                        if np.any(self._field[0, source_state, root_start:root_start + width]):
                            base.update({
                                "status": "already-supported", "action": self.action_ids[action_code],
                                "expected_observations": [observation],
                                "source_state": source_state, "reason": "source-action-already-supported",
                            })
                        else:
                            base.update({
                                "status": "proposed", "action": self.action_ids[action_code],
                                "expected_observations": [observation], "source_state": source_state,
                                "template": {
                                    "root_state": 0, "action": self.action_ids[action_code],
                                    "observation": observation, "destination_state": destination,
                                    "edge_sha256": hashlib.sha256(_canonical({
                                        "source_state": 0, "action": self.action_ids[action_code],
                                        "observation": observation, "destination_state": destination,
                                    })).hexdigest(),
                                },
                            })
        if reason is not None:
            base["reason"] = reason
        base["hypothesis_sha256"] = hashlib.sha256(_canonical(base)).hexdigest()
        return MappingProxyType(base)

    def materialize_transition_support(
        self, skill_id: str, *, participant_id: str | None = None,
        action: str, observation: str, hypothesis_sha256: str,
        expected_state_sha256: str | None = None,
    ) -> tuple[TemporalField, Mapping[str, Any]]:
        """Write one bounded state-conditioned edge, then consume its observation."""
        _identifier(skill_id, "skill_id")
        lane_id = "" if participant_id is None else _identifier(participant_id, "participant_id")
        _identifier(action, "action")
        _identifier(observation, "observation")
        _digest(hypothesis_sha256, "hypothesis_sha256")
        if expected_state_sha256 is not None and _digest(expected_state_sha256, "expected state") != self.state_sha256:
            raise TemporalFieldError("temporal predecessor does not match current field")
        proposal = self.synthesize_transition(skill_id, participant_id=participant_id)
        if proposal.get("status") != "proposed":
            raise TemporalFieldError("transition proposal is not writable")
        if proposal["hypothesis_sha256"] != hypothesis_sha256:
            raise TemporalFieldError("transition proposal is stale")
        if proposal["action"] != action or observation not in proposal["expected_observations"]:
            raise TemporalFieldError("observed transition does not match proposal")
        source_state = int(proposal["source_state"])
        action_code = self.action_ids.index(action)
        observation_code = self.observation_ids.index(observation)
        width = len(self.observation_ids)
        column = action_code * width + observation_code
        if self._field[0, source_state, column] > 0:
            raise TemporalFieldError("transition is already supported")
        destination = int(proposal["template"]["destination_state"])
        record = {
            "participant_id": lane_id,
            "skill_id": skill_id,
            "history": list(proposal["source"]["history"]),
            "action": action,
            "observation": observation,
            "template_destination": destination,
        }
        write_digest = hashlib.sha256(_canonical(record)).hexdigest()
        tensor = self._field.copy()
        tensor[0, source_state, column] = 1.0
        tensor[0, self.max_states + source_state, column] = float(destination)
        materializations = (*self._materializations, record)
        tensor[0, 6*self.max_states:8*self.max_states, :] = 0
        specs = {key: dict(value) for key, value in self._skills.items()}
        successor = self._replace(tensor=tensor, skills={}, materializations=materializations)
        successor, _ = successor._condense_all(specs)
        successor, consumed = successor.consume(action, observation, participant_id=participant_id)
        receipt = {
            "schema": "cassifi.temporal-materialized-transition.v1",
            "memory_id": self.memory_id,
            "participant_id": lane_id,
            "skill_id": skill_id,
            "action": action,
            "observation": observation,
            "source_state": source_state,
            "destination_state": destination,
            "hypothesis_sha256": hypothesis_sha256,
            "materialization_write_sha256": write_digest,
            "support_origin": "state-conditioned-materialization",
            "evidence_class": "canonical-materialized-support",
            "training_source_admitted": False,
            "observed_outcome": True,
            "supported": bool(consumed.get("supported")),
            "execution_authorized": False,
            "source_revision_ids": list(successor.source_revision_ids),
            "previous_memory_sha256": self.memory_sha256,
            "memory_sha256": successor.memory_sha256,
            "previous_state_sha256": self.state_sha256,
            "state_sha256": successor.state_sha256,
        }
        return successor, receipt


REGIONAL_TASK_SCHEMA = "cassifi.temporal-regional-task.v1"


def _regional_clone(value: Any) -> Any:
    """Clone only canonical JSON values used by the regional continuation."""
    try:
        return json.loads(_canonical(value).decode("utf-8"))
    except (TypeError, ValueError, TemporalFieldError) as exc:
        raise TemporalFieldError("regional temporal value is not canonical JSON") from exc


def _regional_int(value: Any, name: str, *, minimum: int = 0, maximum: int = 2**53 - 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise TemporalFieldError(f"{name} must be an exact bounded integer")
    return int(value)


def _regional_source_id(value: Any) -> str:
    return _identifier(value, "source_id")


def _regional_episode(value: Any, actions: Sequence[str], observations: Sequence[str]) -> list[dict[str, str]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise TemporalFieldError("regional temporal episodes must be nonempty sequences")
    action_set, observation_set = set(actions), set(observations)
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"action", "observation"}:
            raise TemporalFieldError("regional temporal steps must contain action and observation")
        action, observation = item["action"], item["observation"]
        if action not in action_set or observation not in observation_set:
            raise TemporalFieldError("regional temporal episode uses an unknown token")
        result.append({"action": action, "observation": observation})
    if len(result) > _MAX_STEPS:
        raise TemporalFieldError("regional temporal episode exceeds bounded capacity")
    return result


def _regional_rows(states: int, actions: int, observations: int, value: int = 0) -> list[list[list[int]]]:
    return [[[value for _ in range(observations)] for _ in range(actions)] for _ in range(states)]


def _regional_coverage(states: int, actions: int) -> list[list[bool]]:
    return [[False for _ in range(actions)] for _ in range(states)]


def _regional_memory_digest(state: Mapping[str, Any]) -> str:
    model = state["model"]
    return hashlib.sha256(_canonical({
        "schema": REGIONAL_TASK_SCHEMA,
        "memory_id": state["memory"]["memory_id"],
        "action_ids": state["memory"]["action_ids"],
        "observation_ids": state["memory"]["observation_ids"],
        "max_states": state["memory"]["max_states"],
        "context": state["memory"]["context"],
        "state_count": model["state_count"],
        "exposures": model["exposures"],
        "destinations": model["destinations"],
        "coverage": model["coverage"],
        "sources": model["sources"],
    })).hexdigest()


def _regional_participant(participant: Any, *, allow_primary: bool = True) -> str:
    if participant is None:
        return ""
    if not isinstance(participant, str) or len(participant) > 256:
        raise TemporalFieldError("regional participant_id is invalid")
    if not participant and not allow_primary:
        raise TemporalFieldError("regional participant_id is empty")
    return participant


def _regional_validate(state: Any) -> dict[str, Any]:
    if not isinstance(state, Mapping) or state.get("schema") != REGIONAL_STATE_SCHEMA:
        raise TemporalFieldError("regional temporal state schema is invalid")
    required = {
        "schema", "memory", "model", "participants", "projection_scopes",
        "continuation", "last_result",
    }
    if set(state) != required:
        raise TemporalFieldError("regional temporal state keys are invalid")
    memory = state["memory"]
    if not isinstance(memory, Mapping) or set(memory) != {
        "memory_id", "action_ids", "observation_ids", "max_states", "context",
    }:
        raise TemporalFieldError("regional temporal memory descriptor is invalid")
    actions = _ids(memory["action_ids"], "action_ids", _MAX_ACTIONS)
    observations = _ids(memory["observation_ids"], "observation_ids", _MAX_OBSERVATIONS)
    max_states = _regional_int(memory["max_states"], "max_states", minimum=1, maximum=_MAX_STATES)
    _identifier(memory["memory_id"], "memory_id")
    _context(memory["context"])
    model = state["model"]
    if not isinstance(model, Mapping) or set(model) != {
        "state_count", "exposures", "destinations", "coverage", "sources", "skills",
    }:
        raise TemporalFieldError("regional temporal model is invalid")
    count = _regional_int(model["state_count"], "state_count", minimum=1, maximum=max_states)
    exposures, destinations, coverage = model["exposures"], model["destinations"], model["coverage"]
    if not isinstance(exposures, list) or not isinstance(destinations, list) or not isinstance(coverage, list):
        raise TemporalFieldError("regional temporal transition planes are invalid")
    if len(exposures) != count or len(destinations) != count or len(coverage) != count:
        raise TemporalFieldError("regional temporal transition plane count is invalid")
    total_exposure = 0
    for state_index in range(count):
        if (not isinstance(exposures[state_index], list)
                or not isinstance(destinations[state_index], list)
                or not isinstance(coverage[state_index], list)
                or len(exposures[state_index]) != len(actions)
                or len(destinations[state_index]) != len(actions)
                or len(coverage[state_index]) != len(actions)):
            raise TemporalFieldError("regional temporal transition row is invalid")
        for action_index in range(len(actions)):
            erow, drow = exposures[state_index][action_index], destinations[state_index][action_index]
            if not isinstance(erow, list) or not isinstance(drow, list) or len(erow) != len(observations) or len(drow) != len(observations):
                raise TemporalFieldError("regional temporal transition outcome row is invalid")
            if not isinstance(coverage[state_index][action_index], bool):
                raise TemporalFieldError("regional temporal coverage is invalid")
            for observation_index, exposure in enumerate(erow):
                exposure = _regional_int(exposure, "transition exposure", maximum=_MAX_STEPS)
                total_exposure += exposure
                destination = _regional_int(drow[observation_index], "transition destination", maximum=count - 1)
                if exposure == 0 and destination != 0:
                    raise TemporalFieldError("unexposed transition has a destination")
            if coverage[state_index][action_index] and not any(erow):
                raise TemporalFieldError("regional coverage lacks transition evidence")
    if total_exposure > _MAX_STEPS:
        raise TemporalFieldError("regional transition exposure exceeds bounded work")
    sources = model["sources"]
    if not isinstance(sources, list) or len(sources) > _MAX_EPISODES:
        raise TemporalFieldError("regional source inventory exceeds capacity")
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, Mapping) or set(source) != {"source_id", "episodes"}:
            raise TemporalFieldError("regional source record is invalid")
        source_id = _regional_source_id(source["source_id"])
        if source_id in source_ids:
            raise TemporalFieldError("regional source identity is duplicated")
        source_ids.add(source_id)
        episodes = source["episodes"]
        if not isinstance(episodes, list) or not episodes:
            raise TemporalFieldError("regional source episodes are invalid")
        for episode in episodes:
            _regional_episode(episode, actions, observations)
    skills = model["skills"]
    if not isinstance(skills, Mapping) or len(skills) > _MAX_SKILLS:
        raise TemporalFieldError("regional skill inventory exceeds capacity")
    for skill_id, spec in skills.items():
        _identifier(skill_id, "skill_id")
        if not isinstance(spec, Mapping) or set(spec) != {
            "goal", "forbidden", "ranks", "policy", "bound_memory_sha256", "stale",
        }:
            raise TemporalFieldError("regional skill record is invalid")
        goals = _ids(spec["goal"], "goal observations", len(observations))
        forbidden = _ids(spec["forbidden"], "forbidden observations", len(observations), allow_empty=True)
        if set(goals) & set(forbidden) or any(item not in observations for item in (*goals, *forbidden)):
            raise TemporalFieldError("regional skill observations conflict")
        ranks, policy = spec["ranks"], spec["policy"]
        if not isinstance(ranks, list) or not isinstance(policy, list) or len(ranks) != count or len(policy) != count:
            raise TemporalFieldError("regional skill ranks and policy are invalid")
        for rank, action in zip(ranks, policy):
            _regional_int(rank, "skill rank", maximum=count)
            _regional_int(action, "skill policy", maximum=len(actions))
            if (rank == 0) != (action == 0):
                raise TemporalFieldError("regional skill rank and policy disagree")
        if not isinstance(spec["stale"], bool):
            raise TemporalFieldError("regional skill stale flag is invalid")
        if not spec["stale"]:
            goals_set, forbidden_set = set(goals), set(forbidden)
            exposures_for_skill = model["exposures"]
            destinations_for_skill = model["destinations"]
            for state_index, rank in enumerate(ranks):
                if not rank:
                    continue
                action_index = policy[state_index] - 1
                outcomes = [
                    observation_index
                    for observation_index, exposure in enumerate(
                        exposures_for_skill[state_index][action_index]
                    ) if exposure > 0
                ]
                if not outcomes:
                    raise TemporalFieldError("regional skill proposes an unsupported action")
                for observation_index in outcomes:
                    observation = observations[observation_index]
                    destination = destinations_for_skill[state_index][action_index][observation_index]
                    if observation in forbidden_set or (
                        observation not in goals_set
                        and not 0 < ranks[destination] < rank
                    ):
                        raise TemporalFieldError("regional skill action does not make safe decreasing progress")
        _digest(spec["bound_memory_sha256"], "skill memory")
    participants = state["participants"]
    if not isinstance(participants, Mapping) or "" not in participants or len(participants) > _MAX_EPISODES:
        raise TemporalFieldError("regional participant inventory is invalid")
    for participant_id, record in participants.items():
        _regional_participant(participant_id)
        if not isinstance(record, Mapping) or set(record) != {
            "history", "candidates", "current", "last_observation", "unknown",
            "unknown_start", "uncovered", "halted",
        }:
            raise TemporalFieldError("regional participant record is invalid")
        history = record["history"]
        if not isinstance(history, list) or len(history) > _MAX_STEPS:
            raise TemporalFieldError("regional participant history exceeds capacity")
        for item in history:
            _regional_episode([item], actions, observations)
        candidates = record["candidates"]
        if not isinstance(candidates, list) or any(
            _regional_int(item, "candidate state", maximum=count - 1) != item for item in candidates
        ) or len(set(candidates)) != len(candidates):
            raise TemporalFieldError("regional participant candidates are invalid")
        for flag_name in ("unknown", "unknown_start", "uncovered", "halted"):
            if not isinstance(record[flag_name], bool):
                raise TemporalFieldError("regional participant flags are invalid")
        current = record["current"]
        if current != -1 and _regional_int(current, "participant current", maximum=count - 1) != current:
            raise TemporalFieldError("regional participant current is invalid")
        if record["last_observation"] is not None and record["last_observation"] not in observations:
            raise TemporalFieldError("regional participant observation is invalid")
    scopes = state["projection_scopes"]
    if not isinstance(scopes, Mapping) or len(scopes) > _MAX_SKILLS:
        raise TemporalFieldError("regional projection scopes exceed capacity")
    for scope_id, scope in scopes.items():
        _identifier(scope_id, "scope_id")
        if not isinstance(scope, Mapping):
            raise TemporalFieldError("regional projection scope is invalid")
    continuation = state["continuation"]
    if not isinstance(continuation, Mapping) or continuation.get("phase") not in {"ready", "running"}:
        raise TemporalFieldError("regional temporal continuation is invalid")
    if continuation["phase"] == "running":
        _identifier(continuation.get("operation"), "continuation operation")
        if not isinstance(continuation.get("task"), Mapping) or not isinstance(continuation.get("cursor"), Mapping):
            raise TemporalFieldError("regional temporal continuation payload is invalid")
    if state["last_result"] is not None and not isinstance(state["last_result"], Mapping):
        raise TemporalFieldError("regional temporal result is invalid")
    return dict(state)


def regional_state(
    memory_id: str | Mapping[str, Any],
    *,
    action_ids: Sequence[str] | None = None,
    observation_ids: Sequence[str] | None = None,
    max_states: int = _MAX_STATES,
    context: Mapping[str, Any] | None = None,
    episodes: Sequence[Sequence[Mapping[str, str]]] | None = None,
    source_revision_ids: Sequence[str] | None = None,
) -> Mapping[str, Any]:
    """Build one stateless, JSON-serializable temporal regional task.

    The returned value contains all transition, participant, skill, projection,
    and continuation coordinates.  It deliberately does not contain a
    ``TemporalField`` or any other adaptive Python owner.
    """
    if isinstance(memory_id, Mapping):
        config = dict(memory_id)
        memory_name = config.pop("memory_id", config.pop("memory", None))
        configured_actions = config.pop("action_ids", None)
        configured_observations = config.pop("observation_ids", None)
        configured_context = config.pop("context", None)
        configured_episodes = config.pop("episodes", None)
        configured_sources = config.pop("source_revision_ids", config.pop("source_ids", None))
        if action_ids is None:
            action_ids = configured_actions
        if observation_ids is None:
            observation_ids = configured_observations
        if context is None:
            context = configured_context
        if episodes is None:
            episodes = configured_episodes
        if source_revision_ids is None:
            source_revision_ids = configured_sources
        max_states = config.pop("max_states", max_states)
        if config:
            raise TemporalFieldError("regional temporal builder arguments are invalid")
        memory_id = memory_name
    actions = _ids(action_ids, "action_ids", _MAX_ACTIONS)
    observations = _ids(observation_ids, "observation_ids", _MAX_OBSERVATIONS)
    max_states = _regional_int(max_states, "max_states", minimum=1, maximum=_MAX_STATES)
    memory_context = _plain(_context({} if context is None else context))
    state: dict[str, Any] = {
        "schema": REGIONAL_STATE_SCHEMA,
        "memory": {
            "memory_id": memory_id,
            "action_ids": list(actions),
            "observation_ids": list(observations),
            "max_states": max_states,
            "context": memory_context,
        },
        "model": {
            "state_count": 1,
            "exposures": _regional_rows(1, len(actions), len(observations)),
            "destinations": _regional_rows(1, len(actions), len(observations)),
            "coverage": _regional_coverage(1, len(actions)),
            "sources": [],
            "skills": {},
        },
        "participants": {
            "": {
                "history": [], "candidates": [0], "current": 0,
                "last_observation": None, "unknown": False,
                "unknown_start": False, "uncovered": False, "halted": False,
            },
        },
        "projection_scopes": {},
        "continuation": {
            "phase": "ready", "operation": None, "task": None,
            "cursor": {}, "learning_frontier": {"source": 0, "episode": 0, "step": 0},
        },
        "last_result": None,
    }
    if episodes is not None:
        induction_arguments: dict[str, Any] = {
            "operation": "induce", "episodes": episodes,
        }
        if source_revision_ids is not None:
            induction_arguments["source_revision_ids"] = source_revision_ids
        _regional_start(state, induction_arguments)
    _regional_validate(state)
    return state


def _regional_operation(arguments: Mapping[str, Any]) -> str:
    raw = arguments.get("operation", arguments.get("op", arguments.get("kind")))
    if raw is None:
        if "episodes" in arguments or "source_revision_ids" in arguments or "source_ids" in arguments:
            raw = "induce"
        elif "action" in arguments and "observation" in arguments:
            raw = "consume"
        elif "known_start" in arguments and "skill_id" not in arguments:
            raw = "reset"
        elif "skill_id" in arguments and any(
            name in arguments for name in ("goal_observations", "goals", "forbidden_observations", "forbidden")
        ):
            raw = "skill"
        elif "scope_id" in arguments or "projection" in arguments:
            raw = "project"
        elif "skill_id" in arguments:
            raw = "select"
    names = {
        "learn": "induce", "induction": "induce", "advance": "consume",
        "construct_skill": "skill", "build_skill": "skill",
        "selection": "select", "projection": "project",
    }
    if not isinstance(raw, str):
        raise TemporalFieldError("regional temporal operation is invalid")
    operation = names.get(raw, raw)
    if operation not in {"induce", "consume", "reset", "skill", "select", "project"}:
        raise TemporalFieldError("regional temporal operation is invalid")
    return operation


def _regional_start(current: dict[str, Any], arguments: Mapping[str, Any]) -> None:
    operation = _regional_operation(arguments)
    memory = current["memory"]
    model = current["model"]
    if operation == "induce":
        episodes_value = arguments.get("episodes", ())
        if isinstance(episodes_value, (str, bytes)) or not isinstance(episodes_value, Sequence) or not episodes_value:
            raise TemporalFieldError("regional induction requires episodes")
        episodes = [
            _regional_episode(episode, memory["action_ids"], memory["observation_ids"])
            for episode in episodes_value
        ]
        source_values = arguments.get("source_revision_ids", arguments.get("source_ids"))
        if source_values is None:
            source_values = [
                hashlib.sha256(_canonical(episode)).hexdigest() for episode in episodes
            ]
        source_values = _ids(source_values, "source_revision_ids", _MAX_EPISODES)
        if len(source_values) not in {1, len(episodes)}:
            raise TemporalFieldError("source_revision_ids must identify each episode or the batch")
        batches = (
            [{"source_id": source_values[0], "episodes": episodes}]
            if len(source_values) == 1
            else [{"source_id": sid, "episodes": [episode]} for sid, episode in zip(source_values, episodes)]
        )
        known = {row["source_id"]: row for row in model["sources"]}
        pending = []
        for row in batches:
            previous = known.get(row["source_id"])
            if previous is not None:
                if previous["episodes"] != row["episodes"]:
                    raise TemporalFieldError("source identity conflicts with retained episode")
            else:
                pending.append(row)
        current["continuation"] = {
            "phase": "running", "operation": "induce",
            "task": {"sources": pending, "support_added": 0},
            "cursor": {"source": 0, "episode": 0, "step": 0, "state": 0},
            "learning_frontier": {"source": 0, "episode": 0, "step": 0},
        }
        return
    if operation == "consume":
        action, observation = arguments.get("action"), arguments.get("observation")
        if action not in memory["action_ids"] or observation not in memory["observation_ids"]:
            raise TemporalFieldError("regional consumption uses an unknown token")
        participant_id = _regional_participant(arguments.get("participant_id"))
        if participant_id not in current["participants"]:
            current["participants"][participant_id] = {
                "history": [], "candidates": [0], "current": 0,
                "last_observation": None, "unknown": False,
                "unknown_start": False, "uncovered": False, "halted": False,
            }
        current["continuation"] = {
            "phase": "running", "operation": "consume",
            "task": {
                "action": action, "observation": observation,
                "participant_id": participant_id,
            },
            "cursor": {"step": 0},
            "learning_frontier": {"participant": participant_id, "step": 0},
        }
        return
    if operation == "reset":
        participant_id = _regional_participant(arguments.get("participant_id"))
        if participant_id not in current["participants"]:
            current["participants"][participant_id] = {
                "history": [], "candidates": [0], "current": 0,
                "last_observation": None, "unknown": False,
                "unknown_start": False, "uncovered": False, "halted": False,
            }
        current["continuation"] = {
            "phase": "running", "operation": "reset",
            "task": {
                "participant_id": participant_id,
                "known_start": arguments.get("known_start", True),
            },
            "cursor": {"step": 0},
            "learning_frontier": {"participant": participant_id, "step": 0},
        }
        return
    if operation == "skill":
        skill_id = _identifier(arguments.get("skill_id"), "skill_id")
        goals = _ids(arguments.get("goal_observations", arguments.get("goals", ())),
                     "goal observations", len(memory["observation_ids"]))
        forbidden = _ids(arguments.get("forbidden_observations", arguments.get("forbidden", ())),
                         "forbidden observations", len(memory["observation_ids"]), allow_empty=True)
        if set(goals) & set(forbidden) or any(
            item not in memory["observation_ids"] for item in (*goals, *forbidden)
        ):
            raise TemporalFieldError("regional skill observations conflict")
        count = model["state_count"]
        current["continuation"] = {
            "phase": "running", "operation": "skill",
            "task": {
                "skill_id": skill_id, "goal": list(goals),
                "forbidden": list(forbidden), "ranks": [0] * count,
                "policy": [0] * count, "iteration": 0, "changed": False,
            },
            "cursor": {"state": 0},
            "learning_frontier": {"skill_id": skill_id, "state": 0, "iteration": 0},
        }
        return
    if operation == "select":
        skill_id = _identifier(arguments.get("skill_id"), "skill_id")
        participant_id = _regional_participant(arguments.get("participant_id"))
        if participant_id not in current["participants"]:
            current["participants"][participant_id] = {
                "history": [], "candidates": [0], "current": 0,
                "last_observation": None, "unknown": False,
                "unknown_start": False, "uncovered": False, "halted": False,
            }
        current["continuation"] = {
            "phase": "running", "operation": "select",
            "task": {"skill_id": skill_id, "participant_id": participant_id},
            "cursor": {"step": 0},
            "learning_frontier": {"participant": participant_id, "skill_id": skill_id, "step": 0},
        }
        return
    if operation == "project":
        skill_id = _identifier(arguments.get("skill_id"), "skill_id")
        scope_id = _identifier(arguments.get("scope_id", skill_id), "scope_id")
        participant_id = _regional_participant(arguments.get("participant_id"))
        current["continuation"] = {
            "phase": "running", "operation": "project",
            "task": {
                "skill_id": skill_id, "scope_id": scope_id,
                "participant_id": participant_id,
                "kind": arguments.get("projection", "skill_pool"),
            },
            "cursor": {"step": 0},
            "learning_frontier": {"scope_id": scope_id, "step": 0},
        }


def _regional_finish(current: dict[str, Any], operation: str, payload: Mapping[str, Any]) -> None:
    result = {
        "schema": REGIONAL_RESULT_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "operation": operation,
        "status": payload.get("status", "complete"),
        "memory_id": current["memory"]["memory_id"],
        "memory_sha256": _regional_memory_digest(current),
        "frontier": _regional_clone(current["continuation"].get("learning_frontier", {})),
        "state_schema": REGIONAL_STATE_SCHEMA,
        "work_schema": REGIONAL_RESULT_SCHEMA,
        **_regional_clone(dict(payload)),
    }
    current["last_result"] = result
    current["continuation"] = {
        "phase": "ready", "operation": None, "task": None, "cursor": {},
        "learning_frontier": result["frontier"],
    }


def _regional_step_induce(current: dict[str, Any]) -> None:
    continuation = current["continuation"]
    task, cursor = continuation["task"], continuation["cursor"]
    sources = task["sources"]
    model, memory = current["model"], current["memory"]
    if cursor["source"] >= len(sources):
        if task["support_added"]:
            for skill in model["skills"].values():
                skill["stale"] = True
        _regional_finish(current, "induce", {
            "status": "replayed" if not task["support_added"] else "learned",
            "source_count": len(sources),
            "support_added": task["support_added"],
            "state_count": model["state_count"],
        })
        return
    source = sources[cursor["source"]]
    if cursor["episode"] >= len(source["episodes"]):
        model["sources"].append(source)
        cursor["source"] += 1
        cursor["episode"] = 0
        cursor["step"] = 0
        cursor["state"] = 0
        return
    episode = source["episodes"][cursor["episode"]]
    if cursor["step"] >= len(episode):
        cursor["episode"] += 1
        cursor["step"] = 0
        cursor["state"] = 0
        return
    event = episode[cursor["step"]]
    action_index = memory["action_ids"].index(event["action"])
    observation_index = memory["observation_ids"].index(event["observation"])
    state_index = cursor["state"]
    exposure = model["exposures"][state_index][action_index][observation_index]
    if exposure == 0:
        if model["state_count"] >= memory["max_states"]:
            raise TemporalFieldError("regional temporal state capacity exceeded")
        destination = model["state_count"]
        model["state_count"] += 1
        model["exposures"].append(_regional_rows(1, len(memory["action_ids"]), len(memory["observation_ids"]))[0])
        model["destinations"].append(_regional_rows(1, len(memory["action_ids"]), len(memory["observation_ids"]))[0])
        model["coverage"].append([False] * len(memory["action_ids"]))
        model["destinations"][state_index][action_index][observation_index] = destination
    else:
        destination = model["destinations"][state_index][action_index][observation_index]
    model["exposures"][state_index][action_index][observation_index] += 1
    model["coverage"][state_index][action_index] = True
    cursor["state"] = destination
    cursor["step"] += 1
    task["support_added"] += 1
    continuation["learning_frontier"] = {
        "source": cursor["source"], "episode": cursor["episode"], "step": cursor["step"],
    }


def _regional_step_consume(current: dict[str, Any]) -> None:
    continuation = current["continuation"]
    task = continuation["task"]
    participant = current["participants"][task["participant_id"]]
    model, memory = current["model"], current["memory"]
    action_index = memory["action_ids"].index(task["action"])
    observation_index = memory["observation_ids"].index(task["observation"])
    candidates = list(participant["candidates"])
    next_candidates: set[int] = set()
    missing: list[int] = []
    for state_index in candidates:
        if not any(model["exposures"][state_index][action_index]):
            missing.append(state_index)
        elif model["exposures"][state_index][action_index][observation_index] > 0:
            next_candidates.add(model["destinations"][state_index][action_index][observation_index])
    was_unknown = participant["unknown"]
    unknown = bool(missing) or not next_candidates or (was_unknown and len(next_candidates) != 1)
    participant["history"].append({"action": task["action"], "observation": task["observation"]})
    participant["candidates"] = sorted(next_candidates)
    participant["current"] = min(next_candidates) if next_candidates else -1
    participant["last_observation"] = task["observation"]
    participant["unknown"] = unknown
    participant["uncovered"] = participant["uncovered"] or bool(missing)
    continuation["learning_frontier"] = {"participant": task["participant_id"], "step": 1}
    _regional_finish(current, "consume", {
        "status": "supported" if not unknown else "unknown-support",
        "action": task["action"], "observation": task["observation"],
        "participant_id": task["participant_id"], "current": participant["current"],
        "candidate_states": participant["candidates"], "missing_states": missing,
        "supported": not unknown, "unknown_successor": unknown,
    })


def _regional_step_reset(current: dict[str, Any]) -> None:
    continuation = current["continuation"]
    task = continuation["task"]
    participant = current["participants"][task["participant_id"]]
    known_start = task["known_start"]
    if not isinstance(known_start, bool):
        raise TemporalFieldError("known_start must be boolean")
    count = current["model"]["state_count"]
    if not known_start and count > current["memory"]["max_states"]:
        raise TemporalFieldError("regional unknown reset exceeds candidate capacity")
    participant.update({
        "history": [], "candidates": [0] if known_start else list(range(count)),
        "current": 0 if known_start else -1, "last_observation": None,
        "unknown": not known_start, "unknown_start": not known_start,
        "uncovered": False, "halted": False,
    })
    _regional_finish(current, "reset", {
        "status": "reset", "participant_id": task["participant_id"],
        "known_start": known_start, "candidate_states": participant["candidates"],
    })


def _regional_skill_option(
    current: Mapping[str, Any], state_index: int, goal: set[str], forbidden: set[str],
    ranks: Sequence[int],
) -> tuple[int, int] | None:
    model, memory = current["model"], current["memory"]
    best: tuple[int, int] | None = None
    for action_index, action_row in enumerate(model["exposures"][state_index]):
        outcomes = [index for index, count in enumerate(action_row) if count > 0]
        if not outcomes or any(memory["observation_ids"][index] in forbidden for index in outcomes):
            continue
        if not all(
            memory["observation_ids"][index] in goal
            or 0 < ranks[model["destinations"][state_index][action_index][index]] < current["model"]["state_count"]
            for index in outcomes
        ):
            continue
        cost = 1 + max(
            (
                0
                if memory["observation_ids"][index] in goal
                else ranks[model["destinations"][state_index][action_index][index]]
            )
            for index in outcomes
        )
        # Policy zero is the explicit unsupported sentinel; expose stored
        # actions one-based while keeping ``action_index`` zero-based above.
        candidate = (cost, action_index + 1)
        if best is None or candidate < best:
            best = candidate
    return best


def _regional_step_skill(current: dict[str, Any]) -> None:
    continuation = current["continuation"]
    task, cursor = continuation["task"], continuation["cursor"]
    count = current["model"]["state_count"]
    goal, forbidden = set(task["goal"]), set(task["forbidden"])
    if cursor["state"] < count:
        state_index = cursor["state"]
        option = _regional_skill_option(current, state_index, goal, forbidden, task["ranks"])
        if option is not None:
            old_rank = task["ranks"][state_index]
            old_action = (
                task["policy"][state_index]
                if old_rank else len(current["memory"]["action_ids"]) + 1
            )
            if old_rank == 0 or option[0] < old_rank or (
                option[0] == old_rank and option[1] < old_action
            ):
                task["ranks"][state_index] = option[0]
                task["policy"][state_index] = option[1]
                task["changed"] = True
        cursor["state"] += 1
        continuation["learning_frontier"] = {
            "skill_id": task["skill_id"], "state": cursor["state"],
            "iteration": task["iteration"],
        }
        return
    if task["changed"] and task["iteration"] < count:
        task["iteration"] += 1
        task["changed"] = False
        cursor["state"] = 0
        continuation["learning_frontier"] = {
            "skill_id": task["skill_id"], "state": 0, "iteration": task["iteration"],
        }
        return
    bound = _regional_memory_digest(current)
    current["model"]["skills"][task["skill_id"]] = {
        "goal": list(task["goal"]), "forbidden": list(task["forbidden"]),
        "ranks": list(task["ranks"]), "policy": list(task["policy"]),
        "bound_memory_sha256": bound, "stale": False,
    }
    _regional_finish(current, "skill", {
        "status": "formed" if task["ranks"][0] > 0 else "pending",
        "skill_id": task["skill_id"],
        "supported_states": sum(rank > 0 for rank in task["ranks"]),
        "start_state_supported": task["ranks"][0] > 0,
        "ranks": list(task["ranks"]), "policy": list(task["policy"]),
        "bound_memory_sha256": bound,
    })


def _regional_skill_signal(current: Mapping[str, Any], skill_id: str) -> list[float]:
    spec = current["model"]["skills"].get(skill_id)
    signal = [0.0] * 7
    if spec is None or spec["stale"]:
        return signal
    supported = [rank for rank in spec["ranks"] if rank > 0]
    if not supported:
        return signal
    maximum = max(supported)
    if maximum == 1:
        signal[0] = float(len(supported))
    else:
        for rank in supported:
            pool = int(math.floor(6 * (rank - 1) / (maximum - 1) + 0.5))
            signal[pool] += 1.0
    norm = math.sqrt(sum(value * value for value in signal))
    return [value / norm for value in signal] if norm else signal


def _regional_step_select(current: dict[str, Any]) -> None:
    task = current["continuation"]["task"]
    participant = current["participants"][task["participant_id"]]
    skill = current["model"]["skills"].get(task["skill_id"])
    payload: dict[str, Any] = {
        "skill_id": task["skill_id"], "participant_id": task["participant_id"],
        "action": None, "supported_states": len(participant["candidates"]),
    }
    if skill is None or skill["stale"]:
        payload.update(status="unresolved", explain="skill absent or stale")
    elif participant["halted"] or participant["unknown"] or not participant["candidates"]:
        payload.update(status="unresolved", explain="current context lacks complete transition support")
    elif participant["last_observation"] in skill["goal"]:
        payload.update(status="complete", explain="goal observation was consumed")
    else:
        actions = {skill["policy"][state] for state in participant["candidates"] if skill["ranks"][state] > 0}
        if len(actions) != 1 or 0 in actions:
            payload.update(status="unresolved", explain="candidate states do not agree on a supported safe action")
        else:
            action_index = next(iter(actions)) - 1
            payload.update(
                status="proposed", action=current["memory"]["action_ids"][action_index],
                remaining_steps=max(skill["ranks"][state] for state in participant["candidates"]),
                explain="supported decreasing-rank action",
            )
    payload["pool_signal"] = _regional_skill_signal(current, task["skill_id"])
    _regional_finish(current, "select", payload)


def _regional_step_project(current: dict[str, Any]) -> None:
    task = current["continuation"]["task"]
    scope = {
        "scope_id": task["scope_id"], "kind": task["kind"],
        "skill_id": task["skill_id"], "participant_id": task["participant_id"],
        "memory_sha256": _regional_memory_digest(current),
    }
    current["projection_scopes"][task["scope_id"]] = scope
    _regional_finish(current, "project", {
        "status": "projected", "scope": scope,
        "pool_signal": _regional_skill_signal(current, task["skill_id"]),
    })


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance one temporal task continuation by at most ``quantum`` steps."""
    checked = _regional_validate(state)
    if not isinstance(arguments, Mapping):
        raise TemporalFieldError("regional temporal arguments must be a mapping")
    quantum = _regional_int(quantum, "regional temporal quantum", minimum=1, maximum=REGIONAL_MAX_WORK)
    current = _regional_clone(checked)
    if current["continuation"]["phase"] == "ready":
        if not arguments:
            return KernelResult(
                state=current, status="done", work=0, output=current["last_result"],
            )
        _regional_start(current, arguments)
    elif arguments:
        requested = _regional_operation(arguments)
        if requested != current["continuation"]["operation"]:
            raise TemporalFieldError("regional temporal continuation operation conflicts")
    used = 0
    while used < quantum and current["continuation"]["phase"] == "running":
        operation = current["continuation"]["operation"]
        try:
            if operation == "induce":
                _regional_step_induce(current)
            elif operation == "consume":
                _regional_step_consume(current)
            elif operation == "reset":
                _regional_step_reset(current)
            elif operation == "skill":
                _regional_step_skill(current)
            elif operation == "select":
                _regional_step_select(current)
            else:
                _regional_step_project(current)
        except TemporalFieldError as exc:
            _regional_finish(current, operation, {
                "status": "fault", "reason": str(exc),
            })
            used += 1
            return KernelResult(
                state=current, status="fault", work=used, output=current["last_result"],
            )
        used += 1
    _regional_validate(current)
    done = current["continuation"]["phase"] == "ready"
    return KernelResult(
        state=current, status="done" if done else "yield",
        work=used, output=current["last_result"] if done else None,
    )


temporal_regional_state = regional_state
temporal_regional_kernel = regional_kernel


__all__ = [
    "SCHEMA", "TemporalField", "TemporalFieldError",
    "REGIONAL_KERNEL_NAME", "REGIONAL_MAX_WORK", "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_STATE_SCHEMA", "REGIONAL_RESULT_SCHEMA", "REGIONAL_TASK_SCHEMA",
    "regional_state", "regional_kernel", "temporal_regional_state",
    "temporal_regional_kernel",
]
