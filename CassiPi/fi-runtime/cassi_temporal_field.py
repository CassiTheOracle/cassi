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

SCHEMA = "cassifi.temporal-field.v1"
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
        object.__setattr__(self, "_skills", self._validate_skills(self._skills))
        self._validate_tensor()
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

    def _validate_skills(self, skills: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Mapping[str, Any]]:
        if not isinstance(skills, Mapping) or len(skills) > min(_MAX_SKILLS, self._field.shape[2]):
            raise TemporalFieldError("skills exceed bounded policy capacity")
        result, used = {}, set()
        for skill_id, spec in skills.items():
            _identifier(skill_id, "skill_id")
            if not isinstance(spec, Mapping) or set(spec) != {"goal", "forbidden", "bound_memory", "slot"}:
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
            result[skill_id] = MappingProxyType({"goal": goals, "forbidden": forbidden, "bound_memory": spec["bound_memory"], "slot": slot})
        return MappingProxyType(result)

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
        digest = hashlib.sha256(_canonical({
            "schema": SCHEMA, "memory_id": self.memory_id, "action_ids": self.action_ids,
            "observation_ids": self.observation_ids, "max_states": self.max_states,
            "context": _plain(self.context), "source_revision_ids": self.source_revision_ids,
            "state_count": float(self._field[0, 3*self.max_states, 0]),
        }))
        digest.update(self._field[0, :2*self.max_states, :])
        return digest.hexdigest()

    @property
    def state_sha256(self) -> str:
        identity = {"memory_sha256": self.memory_sha256, "skills": _plain(self._skills)}
        if not self._legacy:
            identity["participant_ids"] = list(self.participant_ids)
        digest = hashlib.sha256(_canonical(identity))
        digest.update(self._field)
        return digest.hexdigest()
    def as_dict(self) -> Mapping[str, Any]:
        result = {"schema": SCHEMA, "memory_id": self.memory_id, "action_ids": list(self.action_ids),
                  "observation_ids": list(self.observation_ids), "max_states": self.max_states,
                  "context": _plain(self.context), "source_revision_ids": list(self.source_revision_ids),
                  "skills": _plain(self._skills), "field_b64": base64.b64encode(self._field).decode("ascii"),
                  "state_sha256": self.state_sha256, "memory_sha256": self.memory_sha256}
        if not self._legacy:
            result["participant_ids"] = list(self.participant_ids)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> TemporalField:
        required = {"schema", "memory_id", "action_ids", "observation_ids", "max_states", "context",
                    "source_revision_ids", "skills", "field_b64", "state_sha256", "memory_sha256"}
        allowed = required | {"participant_ids"}
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
            result = cls(value["memory_id"], actions, observations, m, value["context"], tensor,
                         tuple(value["source_revision_ids"]), value["skills"], participants, legacy)
        except (KeyError, TypeError, ValueError) as exc:
            raise TemporalFieldError("invalid temporal field descriptor") from exc
        if _digest(value["state_sha256"], "state_sha256") != result.state_sha256 or _digest(value["memory_sha256"], "memory_sha256") != result.memory_sha256:
            raise TemporalFieldError("temporal field digest mismatch")
        return result

    def _replace(self, *, tensor: np.ndarray | None = None, skills: Mapping[str, Mapping[str, Any]] | None = None,
                 participants: tuple[str, ...] | None = None, revisions: tuple[str, ...] | None = None,
                 legacy: bool | None = None) -> TemporalField:
        return replace(self, _field=self._field if tensor is None else tensor,
                       _skills=self._skills if skills is None else skills,
                       _participants=self._participants if participants is None else participants,
                       _source_revision_ids=self._source_revision_ids if revisions is None else revisions,
                       _legacy=self._legacy if legacy is None else legacy,
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
        """An absent action row carries an unknown successor, not a refutation."""
        width = len(self.observation_ids)
        start = action * width
        next_states, missing = set(), []
        for state in sorted(candidates):
            exposures = self._field[0, state, start:start + width]
            if not np.any(exposures):
                missing.append(state)
            elif exposures[observation] > 0:
                next_states.add(int(self._field[0, self.max_states + state, start + observation]))
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
        successor = self._replace(tensor=tensor, skills={}, revisions=tuple(sorted(revisions)), legacy=False)
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
        tensor[lane, 4*m, 0] = -1
        tensor[lane, 5*m, 0] = 0
        if not self._history_capacity and not known_start and self.state_count > 1:
            raise TemporalFieldError("uncertain reset needs bounded candidate capacity")
        flat = tensor[lane, 8*m:9*m, :].reshape(-1)
        flat[:] = 0
        if self._history_capacity:
            if not known_start:
                flat[1] = 2  # History starts at an unknown learned state, not the root.
                flat[self._candidate_offset:self._candidate_offset+self.state_count] = 1
            else:
                flat[self._candidate_offset] = 1
        return self._replace(tensor=tensor, legacy=False)
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

    def _condense_all(self, specs: Mapping[str, Mapping[str, Any]]) -> tuple[TemporalField, Mapping[str, Any]]:
        result = self
        for skill_id, spec in specs.items():
            result, _ = result.condense_skill(skill_id, goal_observations=spec["goal"], forbidden_observations=spec["forbidden"], _slot=spec["slot"], _bound_memory=result.memory_sha256)
        return result, {"skills": list(specs)}

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
        specs[skill_id] = {"goal": goals, "forbidden": forbidden, "bound_memory": bound, "slot": slot}
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
        if halted or context["status"] == "unresolved" or not candidates:
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


__all__ = ["SCHEMA", "TemporalField", "TemporalFieldError"]
