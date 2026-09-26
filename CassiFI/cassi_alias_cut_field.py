"""Exact alias search with independently checkable projected matching cuts.

One immutable float64 tensor owns the source, cuts, current resolution journal,
backend ClauseField, final assignment, and cumulative work counters. Controllers
hold only fixed geometry. A matching obstruction eliminates a partial assignment;
the next candidate is found by the existing clause field, not a host SAT solver.
No polynomial worst-case bound is claimed for unrestricted occurrence aliases.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_alias_exact_one_field import recognize_degree_two_three_exact_one
from cassi_alias_obstruction import evaluate_alias_candidate
from cassi_clause_field import ClauseField, ClauseFieldProfile, ClauseFieldState
from cassi_field_regions import KernelResult
from run_p_vs_np_clause_field_probe import build_proof_certificate

SCHEMA = "cassifi.alias-cut-result.v1"
STATE_SCHEMA = "cassifi.alias-cut-state.v1"
REGIONAL_KERNEL_NAME = "exact.alias-cut"
REGIONAL_KERNEL_MAX_WORK = 4096
REGIONAL_STATE_SCHEMA = "cassifi.alias-cut-regional-state.v3"
_MAGIC = 0x414C4354
_VERSION = 1
_SAFE = 2**53 - 1
_STATUS = ("running", "sat", "unsat", "exhausted")
_REASONS = (
    "running", "perfect-matching", "cut-refutation", "step-budget",
    "cut-capacity", "cut-byte-capacity", "journal-capacity", "alias-budget",
)
(H_MAGIC, H_VERSION, H_STATUS, H_REASON, H_STEPS, H_CUTS, H_CUT_BYTES,
 H_JOURNAL_BYTES, H_RESTARTS, H_ORACLES, H_MATCHING, H_BARRIER, H_SCANS,
 H_CONTRACTIONS, H_MATCH_BOUND, H_ALIAS_STEPS, H_ALIAS_DECISIONS,
 H_ALIAS_CONFLICTS, H_CLAUSE_SCANS, H_LITERAL_SCANS, H_SNAPSHOTS,
 H_PROOF_EVENTS) = range(22)
_HEADER = 22


class AliasCutError(ValueError):
    """Invalid source, profile, state, or cut-guided operation."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= _SAFE:
        raise AliasCutError(f"{name} must be an exact bounded integer >= {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class AliasCutProfile:
    clauses: int
    variables: int
    cubic_variables: int
    max_cuts: int = 64
    max_cut_bytes: int = 32768
    max_journal_bytes: int = 32768
    max_steps: int = 100000
    max_learned_clauses: int = 128

    def __post_init__(self) -> None:
        for name in ("clauses", "variables", "max_steps"):
            _integer(getattr(self, name), name, 1)
        for name in ("cubic_variables", "max_cuts", "max_learned_clauses"):
            _integer(getattr(self, name), name)
        for name in ("max_cut_bytes", "max_journal_bytes"):
            _integer(getattr(self, name), name, 2)
        if self.cubic_variables > self.variables:
            raise AliasCutError("cubic variable count exceeds source size")
        # No 2^k counter or array is allocated. This is a bound on actual allowed
        # calls and their conservative matching work, not on an enumerated space.
        if self.max_steps * (self.clauses + 1) * self.clauses**3 > _SAFE:
            raise AliasCutError("matching work bound exceeds exact integer range")
        if self.field_values * max(1, self.max_steps + 2) > _SAFE // 8:
            raise AliasCutError("snapshot accounting exceeds exact integer range")

    @property
    def backend_profile(self) -> ClauseFieldProfile:
        k = max(1, self.cubic_variables)
        return ClauseFieldProfile(k, max(1, self.max_cuts), k,
                                  self.max_learned_clauses, self.max_steps)

    @property
    def field_values(self) -> int:
        return (_HEADER + 3 * self.clauses + self.variables + self.max_cut_bytes
                + self.max_journal_bytes + self.backend_profile.state_bytes // 8)

    @property
    def shape(self) -> tuple[int, int, int]:
        return (1, self.field_values, 1)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical({"schema": STATE_SCHEMA, **asdict(self)})).hexdigest()


@dataclass(frozen=True, slots=True)
class AliasCutState:
    _field: np.ndarray
    profile_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self._field, np.ndarray) or self._field.dtype != np.float64:
            raise AliasCutError("state must be a float64 tensor")
        if self._field.ndim != 3 or not isinstance(self.profile_sha256, str):
            raise AliasCutError("invalid state rank or profile fingerprint")
        # A bytes-backed snapshot cannot be made writable through a retained
        # NumPy view. No producer-owned mutable buffer survives construction.
        snapshot = np.frombuffer(self._field.tobytes(order="C"), dtype=np.float64)
        object.__setattr__(self, "_field", snapshot.reshape(self._field.shape))

    @property
    def field(self) -> np.ndarray:
        return self._field.copy()

    @property
    def nbytes(self) -> int:
        return int(self._field.nbytes)


class AliasCutField:
    """A fixed transition law alternating alias-CNF search and matching."""

    def __init__(self, profile: AliasCutProfile) -> None:
        if not isinstance(profile, AliasCutProfile):
            raise AliasCutError("AliasCutProfile required")
        self.profile = profile
        self.backend = ClauseField(profile.backend_profile)
        self.source_start = _HEADER
        self.assignment_start = self.source_start + 3 * profile.clauses
        self.cut_start = self.assignment_start + profile.variables
        self.journal_start = self.cut_start + profile.max_cut_bytes
        self.backend_start = self.journal_start + profile.max_journal_bytes

    def _state(self, raw: np.ndarray) -> AliasCutState:
        raw[H_SNAPSHOTS] += 1
        return AliasCutState(raw.reshape(self.profile.shape), self.profile.fingerprint)

    def _source(self, raw: np.ndarray):
        rows = raw[self.source_start:self.assignment_start].reshape((-1, 3))
        return recognize_degree_two_three_exact_one(
            [[int(v) for v in row] for row in rows], variable_count=self.profile.variables)

    def _backend_state(self, raw: np.ndarray) -> ClauseFieldState:
        return ClauseFieldState(raw[self.backend_start:].reshape(self.backend.profile.shape),
                                self.backend.profile.fingerprint)

    @staticmethod
    def _read_json(raw: np.ndarray, start: int, length: int) -> list:
        try:
            value = json.loads(bytes(int(v) for v in raw[start:start + length]))
        except (ValueError, TypeError, UnicodeError) as exc:
            raise AliasCutError("invalid field JSON record") from exc
        if not isinstance(value, list):
            raise AliasCutError("field journal must be a list")
        return value

    @staticmethod
    def _write_bytes(raw: np.ndarray, start: int, old_length: int, payload: bytes) -> None:
        raw[start:start + max(old_length, len(payload))] = 0
        raw[start:start + len(payload)] = np.frombuffer(payload, dtype=np.uint8)

    def _cuts(self, raw: np.ndarray) -> list[dict[str, Any]]:
        return self._read_json(raw, self.cut_start, int(raw[H_CUT_BYTES]))

    def _journal(self, raw: np.ndarray) -> list[dict[str, Any]]:
        return self._read_json(raw, self.journal_start, int(raw[H_JOURNAL_BYTES]))

    @staticmethod
    def _alias_clauses(cuts: Sequence[Mapping[str, Any]], cubic: Sequence[int]) -> list[list[int]]:
        positions = {variable: index + 1 for index, variable in enumerate(cubic)}
        result = []
        for cut in cuts:
            literals = cut.get("literals")
            if not isinstance(literals, list):
                raise AliasCutError("cut literal list missing")
            if any(type(v) is not int or abs(v) not in positions for v in literals):
                raise AliasCutError("cut contains a non-cubic literal")
            if len({abs(v) for v in literals}) != len(literals):
                raise AliasCutError("cut repeats a variable")
            result.append([(1 if v > 0 else -1) * positions[abs(v)] for v in literals])
        return result
    @staticmethod
    def _alias_bits_by_variable(cubic: Sequence[int], bits: Sequence[int]) -> dict[int, int]:
        raw_bits = tuple(bits[:len(cubic)])
        if len(raw_bits) < len(cubic):
            raise AliasCutError("alias backend returned too few variable bits")
        if any(type(value) is not int or value not in (0, 1) for value in raw_bits):
            raise AliasCutError("alias backend returned a non-binary variable bit")
        return {variable: raw_bits[index] for index, variable in enumerate(cubic)}


    @classmethod
    def initialize(cls, formula: Sequence[Sequence[int]], *, variable_count: int,
                   **limits: int) -> tuple[AliasCutField, AliasCutState]:
        source = recognize_degree_two_three_exact_one(formula, variable_count=variable_count)
        field = cls(AliasCutProfile(len(source.formula), variable_count,
                                    len(source.cubic_variables), **limits))
        raw = np.zeros(field.profile.field_values, dtype=np.float64)
        raw[H_MAGIC], raw[H_VERSION], raw[H_RESTARTS] = _MAGIC, _VERSION, 1
        raw[field.source_start:field.assignment_start] = np.asarray(source.formula).reshape(-1)
        raw[field.assignment_start:field.cut_start] = -1
        for start, header in ((field.cut_start, H_CUT_BYTES),
                              (field.journal_start, H_JOURNAL_BYTES)):
            field._write_bytes(raw, start, 0, b"[]")
            raw[header] = 2
        backend = field.backend.initial([], variable_count=max(1, len(source.cubic_variables)))
        raw[field.backend_start:] = backend._field.reshape(-1)
        state = field._state(raw)
        field.validate(state)
        return field, state

    def validate(self, state: AliasCutState) -> None:
        if not isinstance(state, AliasCutState) or state.profile_sha256 != self.profile.fingerprint:
            raise AliasCutError("state/profile mismatch")
        if state._field.shape != self.profile.shape:
            raise AliasCutError("invalid field shape")
        raw = state._field.reshape(-1)
        if (not np.all(np.isfinite(raw)) or np.any(raw != np.rint(raw))
                or np.any(np.abs(raw) > _SAFE)):
            raise AliasCutError("field values must be exact finite integers")
        if tuple(raw[:2]) != (_MAGIC, _VERSION):
            raise AliasCutError("invalid field header")
        status, reason = int(raw[H_STATUS]), int(raw[H_REASON])
        if not 0 <= status < len(_STATUS) or not 0 <= reason < len(_REASONS):
            raise AliasCutError("invalid status or reason")
        if ((status == 0 and reason != 0) or (status == 1 and reason != 1)
                or (status == 2 and reason != 2) or (status == 3 and reason < 3)):
            raise AliasCutError("status/reason mismatch")
        if np.any(raw[H_STEPS:_HEADER] < 0) or raw[H_STEPS] > self.profile.max_steps:
            raise AliasCutError("invalid work counters")
        if raw[H_CUTS] > self.profile.max_cuts or raw[H_RESTARTS] != raw[H_CUTS] + 1:
            raise AliasCutError("invalid cut/restart count")
        source = self._source(raw)
        if len(source.cubic_variables) != self.profile.cubic_variables:
            raise AliasCutError("source/profile cubic count mismatch")
        for start, header, capacity in (
            (self.cut_start, H_CUT_BYTES, self.profile.max_cut_bytes),
            (self.journal_start, H_JOURNAL_BYTES, self.profile.max_journal_bytes),
        ):
            length = int(raw[header])
            if not 2 <= length <= capacity:
                raise AliasCutError("invalid journal length")
            if np.any(raw[start:start + length] < 0) or np.any(raw[start:start + length] > 255):
                raise AliasCutError("invalid journal byte")
            if np.any(raw[start + length:start + capacity] != 0):
                raise AliasCutError("nonzero journal padding")
        cuts, journal = self._cuts(raw), self._journal(raw)
        if len(cuts) != int(raw[H_CUTS]) or any(not isinstance(cut, dict) for cut in cuts):
            raise AliasCutError("cut count or record mismatch")
        backend = self._backend_state(raw)
        self.backend.validate(backend)
        clauses = self._alias_clauses(cuts, source.cubic_variables)
        if self.backend.clauses(backend, learned=False) != tuple(tuple(row) for row in clauses):
            raise AliasCutError("proof cuts detached from alias clauses")
        backend_info = self.backend.inspect(backend)
        if len(journal) != backend_info["resource_ledger"]["conflicts"]:
            raise AliasCutError("resolution journal detached from backend conflicts")
        if status == 2 and backend_info["status"] != "unsat":
            raise AliasCutError("UNSAT state has no alias refutation")
        assignment = tuple(int(v) for v in raw[self.assignment_start:self.cut_start])
        if status == 1:
            if backend_info["status"] != "sat" or any(v not in (0, 1) for v in assignment):
                raise AliasCutError("SAT state has no complete assignment")
            if not all(sum(assignment[v - 1] for v in row) == 1 for row in source.formula):
                raise AliasCutError("SAT assignment violates the original source")
            alias_bits = {variable: assignment[variable - 1] for variable in source.cubic_variables}
            if any(
                not any(
                    (alias_bits[abs(literal)] == 1) == (literal > 0)
                    for literal in cut["literals"]
                )
                for cut in cuts
            ):
                raise AliasCutError("SAT assignment violates a retained cut")

        elif any(v != -1 for v in assignment):
            raise AliasCutError("non-SAT state exposes an assignment")

    def state_sha256(self, state: AliasCutState) -> str:
        self.validate(state)
        return hashlib.sha256(state._field.tobytes()).hexdigest()

    def _stop(self, raw: np.ndarray, reason: str) -> None:
        raw[H_STATUS] = 3
        raw[H_REASON] = _REASONS.index(reason)

    def step(self, state: AliasCutState) -> tuple[AliasCutState, dict[str, Any]]:
        self.validate(state)
        source_raw = state._field.reshape(-1)
        if source_raw[H_STATUS] != 0:
            return state, {"action": "done", "status": _STATUS[int(source_raw[H_STATUS])]}
        raw = source_raw.copy()
        if raw[H_STEPS] >= self.profile.max_steps:
            self._stop(raw, "step-budget")
            return self._state(raw), {"action": "exhaust", "status": "exhausted"}
        raw[H_STEPS] += 1
        backend_state = self._backend_state(raw)
        backend_status = self.backend.status(backend_state)
        action = "alias-step"
        if backend_status == "running":
            successor, event = self.backend.step(backend_state)
            raw[H_ALIAS_STEPS] += 1
            raw[H_ALIAS_DECISIONS] += int(event["action"] == "decide")
            raw[H_CLAUSE_SCANS] += int(event["work"]["clause_scans"])
            raw[H_LITERAL_SCANS] += int(event["work"]["literal_scans"])
            conflict = event.get("conflict_proof")
            accepted = True
            if conflict is not None:
                raw[H_ALIAS_CONFLICTS] += 1
                raw[H_PROOF_EVENTS] += 1
                payload = _canonical([*self._journal(raw), conflict])
                if len(payload) > self.profile.max_journal_bytes:
                    self._stop(raw, "journal-capacity")
                    accepted = False
                else:
                    self._write_bytes(raw, self.journal_start, int(raw[H_JOURNAL_BYTES]), payload)
                    raw[H_JOURNAL_BYTES] = len(payload)
            if accepted:
                raw[self.backend_start:] = successor._field.reshape(-1)
                status = self.backend.status(successor)
                if status == "unsat":
                    raw[H_STATUS], raw[H_REASON] = 2, 2
                elif status == "exhausted":
                    self._stop(raw, "alias-budget")
        elif backend_status == "sat":
            action = "matching-candidate"
            source = self._source(raw)
            alias_values = self.backend.assignment(backend_state)
            bits = tuple(int(value == 1) for value in alias_values[:self.profile.cubic_variables])
            candidate = evaluate_alias_candidate(source, bits)
            raw[H_ORACLES] += 1
            for header, name in ((H_MATCHING, "matching_runs"), (H_BARRIER, "barrier_matching_runs"),
                                 (H_SCANS, "initial_edge_scans"), (H_CONTRACTIONS, "blossom_contractions"),
                                 (H_MATCH_BOUND, "matching_work_bound")):
                raw[header] += _integer(candidate["work"][name], name)
            if candidate["status"] == "sat":
                raw[self.assignment_start:self.cut_start] = candidate["assignment"]
                raw[H_STATUS], raw[H_REASON] = 1, 1
            else:
                cuts = self._cuts(raw)
                cut = candidate["cut"]
                row = self._alias_clauses([cut], source.cubic_variables)[0]
                alias_bits = self._alias_bits_by_variable(source.cubic_variables, bits)
                if any(
                    (alias_bits[abs(literal)] == 1) == (literal > 0)
                    for literal in cut["literals"]
                ):
                    raise AliasCutError("projected cut does not exclude its triggering candidate")
                if row in self._alias_clauses(cuts, source.cubic_variables):
                    raise AliasCutError("alias search repeated an excluded candidate")
                payload = _canonical([*cuts, cut])
                if len(cuts) >= self.profile.max_cuts:
                    self._stop(raw, "cut-capacity")
                elif len(payload) > self.profile.max_cut_bytes:
                    self._stop(raw, "cut-byte-capacity")
                else:
                    cuts.append(cut)
                    clauses = self._alias_clauses(cuts, source.cubic_variables)
                    restarted = self.backend.initial(clauses, variable_count=max(1, len(bits)))
                    self._write_bytes(raw, self.cut_start, int(raw[H_CUT_BYTES]), payload)
                    raw[H_CUT_BYTES], raw[H_CUTS] = len(payload), len(cuts)
                    self._write_bytes(raw, self.journal_start, int(raw[H_JOURNAL_BYTES]), b"[]")
                    raw[H_JOURNAL_BYTES] = 2
                    raw[self.backend_start:] = restarted._field.reshape(-1)
                    raw[H_RESTARTS] += 1
                    action = "retain-obstruction-cut"
        else:
            raise AliasCutError("running state contains an unhandled terminal backend")
        successor = self._state(raw)
        return successor, {"action": action, "status": _STATUS[int(raw[H_STATUS])]}

    def solve(self, state: AliasCutState) -> tuple[AliasCutState, dict[str, Any]]:
        self.validate(state)
        while state._field.reshape(-1)[H_STATUS] == 0:
            state, _ = self.step(state)
        return state, self.result(state)

    def inspect(self, state: AliasCutState) -> dict[str, Any]:
        self.validate(state)
        raw = state._field.reshape(-1)
        return {
            "status": _STATUS[int(raw[H_STATUS])], "reason": _REASONS[int(raw[H_REASON])],
            "steps": int(raw[H_STEPS]), "cuts": int(raw[H_CUTS]),
            "oracle_calls": int(raw[H_ORACLES]), "matching_runs": int(raw[H_MATCHING]),
            "barrier_matching_runs": int(raw[H_BARRIER]),
            "initial_edge_scans": int(raw[H_SCANS]),
            "initial_blossom_contractions": int(raw[H_CONTRACTIONS]),
            "matching_work_bound": int(raw[H_MATCH_BOUND]),
            "alias_restarts": int(raw[H_RESTARTS]), "alias_transitions": int(raw[H_ALIAS_STEPS]),
            "alias_decisions": int(raw[H_ALIAS_DECISIONS]), "alias_conflicts": int(raw[H_ALIAS_CONFLICTS]),
            "alias_clause_scans": int(raw[H_CLAUSE_SCANS]),
            "alias_literal_scans": int(raw[H_LITERAL_SCANS]),
            "proof_events": int(raw[H_PROOF_EVENTS]),
            "cut_json_bytes": int(raw[H_CUT_BYTES]), "journal_json_bytes": int(raw[H_JOURNAL_BYTES]),
            "field_bytes": state.nbytes, "state_snapshots": int(raw[H_SNAPSHOTS]),
            "state_snapshot_bytes": state.nbytes * int(raw[H_SNAPSHOTS]),
        }

    def result(self, state: AliasCutState) -> dict[str, Any]:
        work = self.inspect(state)
        if work["status"] == "running":
            raise AliasCutError("running state has no result")
        raw = state._field.reshape(-1)
        source = self._source(raw)
        cuts = self._cuts(raw)
        backend = self._backend_state(raw)
        assignment = None
        alias_assignment = None
        proof = None
        if work["status"] == "sat":
            assignment = [int(v) for v in raw[self.assignment_start:self.cut_start]]
            alias_assignment = [assignment[v - 1] for v in source.cubic_variables] or [0]
        elif work["status"] == "unsat":
            proof = build_proof_certificate(self._journal(raw), status="unsat")
        return {
            "schema": SCHEMA, "status": work["status"], "reason": work["reason"],
            "formula": [list(row) for row in source.formula],
            "variable_count": self.profile.variables,
            "cubic_variables": list(source.cubic_variables), "assignment": assignment,
            "cuts": cuts, "alias_clauses": self._alias_clauses(cuts, source.cubic_variables),
            "alias_assignment": alias_assignment,
            "alias_learned_clauses": [list(row) for row in self.backend.clauses(backend, learned=True)],
            "alias_backend_work": self.backend.inspect(backend)["resource_ledger"],
            "proof": proof, "work": work, "profile": asdict(self.profile),
            "state_sha256": hashlib.sha256(state._field.tobytes()).hexdigest(),
        }

    def descriptor(self, state: AliasCutState) -> dict[str, Any]:
        self.validate(state)
        return {
            "schema": STATE_SCHEMA, "profile": asdict(self.profile),
            "profile_sha256": self.profile.fingerprint,
            "state_sha256": hashlib.sha256(state._field.tobytes()).hexdigest(),
            "field_b64": base64.b64encode(state._field.tobytes()).decode("ascii"),
        }

    @classmethod
    def from_descriptor(cls, value: Mapping[str, Any]) -> tuple[AliasCutField, AliasCutState]:
        if not isinstance(value, Mapping) or value.get("schema") != STATE_SCHEMA:
            raise AliasCutError("unsupported descriptor")
        try:
            profile = AliasCutProfile(**value["profile"])
            if value.get("profile_sha256") != profile.fingerprint:
                raise AliasCutError("descriptor profile digest mismatch")
            payload = base64.b64decode(value["field_b64"], validate=True)
            if len(payload) != profile.field_values * 8:
                raise AliasCutError("descriptor byte count mismatch")
            if hashlib.sha256(payload).hexdigest() != value.get("state_sha256"):
                raise AliasCutError("descriptor state digest mismatch")
            state = AliasCutState(np.frombuffer(payload, dtype=np.float64).reshape(profile.shape),
                                  profile.fingerprint)
        except (KeyError, TypeError, ValueError) as exc:
            raise AliasCutError(f"invalid descriptor: {exc}") from exc
        field = cls(profile)
        field.validate(state)
        return field, state

def _regional_source(value: Mapping[str, Any]) -> dict[str, Any]:
    """Canonical source boundary retained by the v3 regional state."""

    if not isinstance(value, Mapping) or set(value) != {
        "formula", "variable_count", "cubic_variables",
    }:
        raise AliasCutError("regional alias-cut source boundary is invalid")
    try:
        recognized = recognize_degree_two_three_exact_one(
            value["formula"],
            variable_count=value["variable_count"],
        )
    except (TypeError, ValueError) as exc:
        raise AliasCutError("regional alias-cut source boundary is invalid") from exc
    result = {
        "formula": [list(row) for row in recognized.formula],
        "variable_count": len(recognized.degrees),
        "cubic_variables": list(recognized.cubic_variables),
    }
    if dict(value) != result:
        raise AliasCutError("regional alias-cut source boundary is not canonical")
    return result


def _regional_alias_clauses(
    cuts: Sequence[Mapping[str, Any]],
    cubic: Sequence[int],
) -> list[list[int]]:
    positions = {variable: index + 1 for index, variable in enumerate(cubic)}
    result: list[list[int]] = []
    for cut in cuts:
        literals = cut.get("literals")
        if not isinstance(literals, list):
            raise AliasCutError("regional cut literal list is missing")
        if any(type(value) is not int or abs(value) not in positions for value in literals):
            raise AliasCutError("regional cut contains a non-cubic literal")
        result.append([
            (1 if value > 0 else -1) * positions[abs(value)]
            for value in literals
        ])
    return result


def _regional_candidate_bits(cursor: int, count: int) -> list[int]:
    return [
        (cursor >> (count - index - 1)) & 1
        for index in range(count)
    ]


def _regional_excluded(
    bits: Sequence[int],
    cubic: Sequence[int],
    cuts: Sequence[Mapping[str, Any]],
) -> int | None:
    for index, cut in enumerate(cuts):
        literals = cut["literals"]
        if not any(
            (bits[position] == 1) == (literal > 0)
            for position, variable in enumerate(cubic)
            for literal in literals
            if abs(literal) == variable
        ):
            return index
    return None


def _regional_conflict(
    cut: Mapping[str, Any],
    cut_index: int,
    bits: Sequence[int],
    cubic: Sequence[int],
) -> dict[str, Any]:
    positions = {variable: index + 1 for index, variable in enumerate(cubic)}
    decisions = [
        index + 1 if bit else -(index + 1)
        for index, bit in enumerate(bits)
    ]
    return {
        "schema": "cassifi.clause-field-conflict-proof.v1",
        "decision_literals": decisions,
        "conflict_clause_id": cut_index + 1,
        "resolution_steps": [],
        "core_clause": [
            (1 if literal > 0 else -1) * positions[abs(literal)]
            for literal in cut["literals"]
        ],
        "nogood_clause": [-literal for literal in decisions],
        "stored_clause_id": None,
        "stored_new": True,
        "learning_status": "added",
    }




def _regional_refresh_conflicts(
    conflicts: Sequence[Mapping[str, Any]],
    original_count: int,
) -> list[dict[str, Any]]:
    refreshed: list[dict[str, Any]] = []
    for index, conflict in enumerate(conflicts):
        row = dict(conflict)
        row["stored_clause_id"] = original_count + index + 1
        row["stored_new"] = True
        row["learning_status"] = "added"
        refreshed.append(row)
    return refreshed


def _regional_evidence(
    outcome: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if outcome is None:
        return {
            "kind": "unresolved",
            "assignment": None,
            "certificate": None,
            "reason": "running",
        }
    status = outcome["status"]
    if status == "sat":
        return {
            "kind": "sat-witness",
            "assignment": list(outcome["assignment"]),
            "certificate": None,
            "reason": None,
        }
    if status == "unsat":
        return {
            "kind": "unsat-certificate",
            "assignment": None,
            "certificate": outcome["proof"],
            "reason": None,
        }
    if status == "exhausted":
        return {
            "kind": "exhausted",
            "assignment": None,
            "certificate": None,
            "reason": outcome["reason"],
        }
    return {
        "kind": "fault",
        "assignment": None,
        "certificate": None,
        "reason": outcome.get("reason", "fault"),
    }


def _regional_ledger(
    *,
    status: str,
    reason: str,
    steps: int,
    cuts: Sequence[Mapping[str, Any]],
    oracle_calls: int,
    matching: Mapping[str, int],
    skipped: int,
    conflicts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "steps": int(steps),
        "cuts": len(cuts),
        "oracle_calls": int(oracle_calls),
        "matching_runs": int(matching["matching_runs"]),
        "barrier_matching_runs": int(matching["barrier_matching_runs"]),
        "initial_edge_scans": int(matching["initial_edge_scans"]),
        "initial_blossom_contractions": int(matching["blossom_contractions"]),
        "matching_work_bound": int(matching["matching_work_bound"]),
        "alias_restarts": len(cuts) + 1,
        "alias_transitions": int(steps),
        "alias_decisions": int(oracle_calls),
        "alias_conflicts": len(conflicts),
        "alias_clause_scans": 0,
        "alias_literal_scans": 0,
        "proof_events": len(conflicts),
        "cut_json_bytes": len(_canonical(list(cuts))),
        "journal_json_bytes": len(_canonical(list(conflicts))),
        "field_bytes": 0,
        "state_snapshots": int(steps) + 1,
        "state_snapshot_bytes": 0,
        "candidate_steps": int(steps),
        "skipped_candidates": int(skipped),
    }


def _regional_backend_work(
    ledger: Mapping[str, Any],
    conflicts: Sequence[Mapping[str, Any]],
    learned: Sequence[Sequence[int]],
) -> dict[str, Any]:
    return {
        "transitions": int(ledger["alias_transitions"]),
        "decisions": int(ledger["alias_decisions"]),
        "propagations": 0,
        "conflicts": len(conflicts),
        "backtracks": 0,
        "learned_clauses": len(learned),
        "clause_scans": int(ledger["alias_clause_scans"]),
        "literal_scans": int(ledger["alias_literal_scans"]),
        "assignment_writes": 0,
        "clause_writes": 0,
        "peak_trail": 0,
        "peak_depth": 0,
        "proof_resolutions": 0,
        "proof_literal_scans": 0,
    }


def _regional_result(
    source: Mapping[str, Any],
    profile: Mapping[str, Any],
    cuts: Sequence[Mapping[str, Any]],
    conflicts: Sequence[Mapping[str, Any]],
    ledger: Mapping[str, Any],
    *,
    cursor: int,
    status: str,
    reason: str,
    assignment: Sequence[int] | None,
    alias_assignment: Sequence[int] | None,
) -> dict[str, Any]:
    cubic = source["cubic_variables"]
    alias_clauses = _regional_alias_clauses(cuts, cubic)
    proof = (
        build_proof_certificate(conflicts, status="unsat")
        if status == "unsat"
        else None
    )
    learned = (
        [list(conflict["nogood_clause"]) for conflict in conflicts]
        if status == "unsat"
        else []
    )
    backend_work = _regional_backend_work(ledger, conflicts, learned)
    digest = hashlib.sha256(_canonical({
        "source": source,
        "profile": profile,
        "cuts": list(cuts),
        "cursor": int(cursor),
        "ledger": dict(ledger),
    })).hexdigest()
    return {
        "schema": SCHEMA,
        "status": status,
        "reason": reason,
        "formula": [list(row) for row in source["formula"]],
        "variable_count": int(source["variable_count"]),
        "cubic_variables": list(cubic),
        "assignment": None if assignment is None else list(assignment),
        "cuts": [dict(cut) for cut in cuts],
        "alias_clauses": alias_clauses,
        "alias_assignment": (
            None if alias_assignment is None else list(alias_assignment)
        ),
        "proof": proof,
        "work": dict(ledger),
        "profile": dict(profile),
        "state_sha256": digest,
        "alias_learned_clauses": learned,
        "alias_backend_work": backend_work,
    }


def _regional_make_state(
    source: Mapping[str, Any],
    profile: Mapping[str, Any],
    *,
    phase: str,
    cursor: int,
    candidate_limit: int,
    cuts: Sequence[Mapping[str, Any]],
    conflicts: Sequence[Mapping[str, Any]],
    ledger: Mapping[str, Any],
    result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    refreshed = _regional_refresh_conflicts(conflicts, len(cuts))
    evidence = _regional_evidence(result)
    next_bits = (
        _regional_candidate_bits(cursor, len(source["cubic_variables"]))
        if cursor < candidate_limit and phase != "terminal"
        else None
    )
    return {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": dict(source),
        "profile": dict(profile),
        "phase": phase,
        "continuation": {
            "frontier": {
                "next_candidate": next_bits,
                "remaining_candidates": max(0, candidate_limit - cursor),
                "cut_count": len(cuts),
            },
            "candidate_cursor": {
                "index": int(cursor),
                "limit": int(candidate_limit),
                "cubic_variables": list(source["cubic_variables"]),
            },
        },
        "journal": {
            "cut_journal": [dict(cut) for cut in cuts],
            "resolution_journal": refreshed,
            "proof": None if result is None else result["proof"],
            "evidence": evidence,
        },
        "ledger": dict(ledger),
        "result": None if result is None else dict(result),
    }


def _regional_decode(
    value: Any,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    if not isinstance(value, Mapping) or value.get("schema") != REGIONAL_STATE_SCHEMA:
        raise AliasCutError("regional alias-cut state schema is invalid")
    required = {
        "schema", "source", "profile", "phase",
        "continuation", "journal", "ledger", "result",
    }
    if set(value) != required:
        raise AliasCutError("regional alias-cut state keys are invalid")
    source = _regional_source(value["source"])
    if not isinstance(value["profile"], Mapping):
        raise AliasCutError("regional alias-cut profile is invalid")
    try:
        profile_obj = AliasCutProfile(**dict(value["profile"]))
    except (TypeError, ValueError) as exc:
        raise AliasCutError("regional alias-cut profile is invalid") from exc
    profile = asdict(profile_obj)
    if dict(value["profile"]) != profile:
        raise AliasCutError("regional alias-cut profile is not canonical")
    if profile["clauses"] != len(source["formula"]):
        raise AliasCutError("regional alias-cut profile/source mismatch")
    if profile["variables"] != source["variable_count"]:
        raise AliasCutError("regional alias-cut variable mismatch")
    if profile["cubic_variables"] != len(source["cubic_variables"]):
        raise AliasCutError("regional alias-cut cubic mismatch")
    continuation = value["continuation"]
    if not isinstance(continuation, Mapping) or set(continuation) != {
        "frontier", "candidate_cursor",
    }:
        raise AliasCutError("regional alias-cut continuation is invalid")
    cursor_value = continuation["candidate_cursor"]
    if not isinstance(cursor_value, Mapping) or set(cursor_value) != {
        "index", "limit", "cubic_variables",
    }:
        raise AliasCutError("regional alias-cut candidate cursor is invalid")
    cursor = _integer(cursor_value["index"], "candidate cursor")
    candidate_limit = _integer(cursor_value["limit"], "candidate limit", 1)
    if cursor > candidate_limit or cursor_value["cubic_variables"] != source["cubic_variables"]:
        raise AliasCutError("regional alias-cut candidate cursor is detached")
    expected_limit = (
        (1 << len(source["cubic_variables"]))
        if len(source["cubic_variables"]) < 53
        else _SAFE
    )
    if candidate_limit != min(expected_limit, _SAFE):
        raise AliasCutError("regional alias-cut candidate limit is invalid")
    journal = value["journal"]
    if not isinstance(journal, Mapping) or set(journal) != {
        "cut_journal", "resolution_journal", "proof", "evidence",
    }:
        raise AliasCutError("regional alias-cut journal is invalid")
    cuts = journal["cut_journal"]
    conflicts = journal["resolution_journal"]
    if (
        not isinstance(cuts, list)
        or not isinstance(conflicts, list)
        or any(not isinstance(cut, dict) for cut in cuts)
        or any(not isinstance(conflict, dict) for conflict in conflicts)
    ):
        raise AliasCutError("regional alias-cut journal records are invalid")
    if len(cuts) > profile["max_cuts"]:
        raise AliasCutError("regional alias-cut cut capacity exceeded")
    cut_fields = {
        "kind", "literals", "conflict_clause", "barrier",
        "components", "boundary_witnesses",
    }
    for cut in cuts:
        if set(cut) != cut_fields:
            raise AliasCutError("regional alias-cut cut record is invalid")
    _regional_alias_clauses(cuts, source["cubic_variables"])
    refreshed = _regional_refresh_conflicts(conflicts, len(cuts))
    if conflicts != refreshed:
        raise AliasCutError("regional alias-cut proof journal is not canonical")
    frontier = continuation["frontier"]
    expected_frontier = {
        "next_candidate": (
            _regional_candidate_bits(cursor, len(source["cubic_variables"]))
            if cursor < candidate_limit and value["phase"] != "terminal"
            else None
        ),
        "remaining_candidates": max(0, candidate_limit - cursor),
        "cut_count": len(cuts),
    }
    if frontier != expected_frontier:
        raise AliasCutError("regional alias-cut frontier is detached")
    ledger = value["ledger"]
    if not isinstance(ledger, Mapping):
        raise AliasCutError("regional alias-cut ledger is invalid")
    for key in (
        "steps", "cuts", "oracle_calls", "matching_runs",
        "barrier_matching_runs", "initial_edge_scans",
        "initial_blossom_contractions", "matching_work_bound",
        "alias_restarts", "alias_transitions", "alias_decisions",
        "alias_conflicts", "alias_clause_scans", "alias_literal_scans",
        "proof_events", "cut_json_bytes", "journal_json_bytes",
        "field_bytes", "state_snapshots", "state_snapshot_bytes",
        "candidate_steps", "skipped_candidates",
    ):
        _integer(ledger.get(key), f"ledger.{key}")
    if (
        ledger["steps"] > profile["max_steps"]
        or ledger["cuts"] != len(cuts)
        or ledger["candidate_steps"] != ledger["steps"]
        or ledger["alias_transitions"] != ledger["steps"]
        or ledger["alias_decisions"] != ledger["oracle_calls"]
        or ledger["alias_conflicts"] != len(conflicts)
        or ledger["proof_events"] != len(conflicts)
        or ledger["oracle_calls"] + ledger["skipped_candidates"] != ledger["steps"]
    ):
        raise AliasCutError("regional alias-cut ledger is detached")
    phase = value["phase"]
    result = value["result"]
    evidence = journal["evidence"]
    if phase == "terminal":
        if (
            not isinstance(result, Mapping)
            or result.get("schema") != SCHEMA
            or result.get("status") not in {"sat", "unsat", "exhausted"}
            or result.get("status") != ledger["status"]
            or result.get("reason") != ledger["reason"]
        ):
            raise AliasCutError("regional alias-cut terminal result is invalid")
        assignment = result.get("assignment")
        alias_assignment = result.get("alias_assignment")
        if result["status"] == "sat":
            if (
                not isinstance(assignment, list)
                or len(assignment) != source["variable_count"]
                or any(type(bit) is not int or bit not in (0, 1) for bit in assignment)
                or not all(sum(assignment[variable - 1] for variable in row) == 1 for row in source["formula"])
            ):
                raise AliasCutError("regional alias-cut SAT witness is invalid")
            expected_alias = [
                assignment[variable - 1]
                for variable in source["cubic_variables"]
            ] or [0]
            if alias_assignment != expected_alias:
                raise AliasCutError("regional alias-cut SAT witness is invalid")
        elif assignment is not None or alias_assignment is not None:
            raise AliasCutError("regional alias-cut non-SAT result carries a witness")
        try:
            expected_result = _regional_result(
                source,
                profile,
                cuts,
                conflicts,
                ledger,
                cursor=cursor,
                status=result["status"],
                reason=result["reason"],
                assignment=result.get("assignment"),
                alias_assignment=result.get("alias_assignment"),
            )
        except (AssertionError, TypeError, ValueError) as exc:
            raise AliasCutError("regional alias-cut terminal result is invalid") from exc
        if result != expected_result:
            raise AliasCutError("regional alias-cut terminal result is detached")
        if (
            journal["proof"] != result["proof"]
            or evidence != _regional_evidence(result)
        ):
            raise AliasCutError("regional alias-cut terminal evidence is detached")
    elif phase == "candidate-search":
        if (
            result is not None
            or ledger["status"] != "running"
            or ledger["reason"] != "running"
            or journal["proof"] is not None
            or evidence != _regional_evidence(None)
        ):
            raise AliasCutError("regional alias-cut running state has a result")
    elif phase == "fault":
        if (
            not isinstance(result, Mapping)
            or result.get("status") != "fault"
            or not isinstance(evidence, Mapping)
            or evidence.get("kind") != "fault"
        ):
            raise AliasCutError("regional alias-cut fault result is invalid")
    else:
        raise AliasCutError("regional alias-cut phase is invalid")
    return source, profile, dict(cursor_value), cuts, conflicts


def regional_state(
    formula: Sequence[Sequence[int]],
    *,
    variable_count: int,
    **limits: int,
) -> dict[str, Any]:
    """Encode one cut-guided alias workload for the v3 regional computer."""

    try:
        recognized = recognize_degree_two_three_exact_one(
            formula,
            variable_count=variable_count,
        )
        profile_obj = AliasCutProfile(
            len(recognized.formula),
            variable_count,
            len(recognized.cubic_variables),
            **limits,
        )
    except (TypeError, ValueError) as exc:
        raise AliasCutError("regional alias-cut source is invalid") from exc
    source = {
        "formula": [list(row) for row in recognized.formula],
        "variable_count": int(variable_count),
        "cubic_variables": list(recognized.cubic_variables),
    }
    profile = asdict(profile_obj)
    matching = {
        "matching_runs": 0,
        "barrier_matching_runs": 0,
        "initial_edge_scans": 0,
        "blossom_contractions": 0,
        "matching_work_bound": 0,
    }
    ledger = _regional_ledger(
        status="running",
        reason="running",
        steps=0,
        cuts=[],
        oracle_calls=0,
        matching=matching,
        skipped=0,
        conflicts=[],
    )
    candidate_limit = (
        (1 << len(source["cubic_variables"]))
        if len(source["cubic_variables"]) < 53
        else _SAFE
    )
    return _regional_make_state(
        source,
        profile,
        phase="candidate-search",
        cursor=0,
        candidate_limit=min(candidate_limit, _SAFE),
        cuts=[],
        conflicts=[],
        ledger=ledger,
        result=None,
    )


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance at most ``quantum`` typed candidate/cut transitions."""

    if not isinstance(arguments, Mapping) or arguments:
        raise AliasCutError("regional alias-cut kernel takes no arguments")
    quantum = _integer(quantum, "regional alias-cut quantum", minimum=1)
    if quantum > REGIONAL_KERNEL_MAX_WORK:
        raise AliasCutError("regional alias-cut quantum exceeds kernel bound")
    source, profile, cursor_value, cuts_value, conflicts_value = _regional_decode(state)
    if state["phase"] == "fault":
        return KernelResult(state=state, status="fault", work=0, output=state["result"])
    if state["phase"] == "terminal":
        return KernelResult(state=state, status="done", work=0, output=state["result"])

    recognized = recognize_degree_two_three_exact_one(
        source["formula"],
        variable_count=source["variable_count"],
    )
    cursor = int(cursor_value["index"])
    candidate_limit = int(cursor_value["limit"])
    cuts = [dict(cut) for cut in cuts_value]
    conflicts = [dict(conflict) for conflict in conflicts_value]
    ledger_before = dict(state["ledger"])
    steps = int(ledger_before["steps"])
    oracle_calls = int(ledger_before["oracle_calls"])
    skipped = int(ledger_before["skipped_candidates"])
    matching = {
        "matching_runs": int(ledger_before["matching_runs"]),
        "barrier_matching_runs": int(ledger_before["barrier_matching_runs"]),
        "initial_edge_scans": int(ledger_before["initial_edge_scans"]),
        "blossom_contractions": int(ledger_before["initial_blossom_contractions"]),
        "matching_work_bound": int(ledger_before["matching_work_bound"]),
    }
    status = "running"
    reason = "running"
    assignment: list[int] | None = None
    alias_assignment: list[int] | None = None
    executed = 0
    while executed < quantum and status == "running":
        if steps >= profile["max_steps"]:
            status, reason = "exhausted", "step-budget"
            break
        if cursor >= candidate_limit:
            status, reason = (
                ("unsat", "cut-refutation")
                if len(source["cubic_variables"]) < 53
                else ("exhausted", "alias-budget")
            )
            break
        bits = _regional_candidate_bits(cursor, len(source["cubic_variables"]))
        cursor += 1
        steps += 1
        executed += 1
        excluded = _regional_excluded(bits, source["cubic_variables"], cuts)
        if excluded is not None:
            skipped += 1
            conflicts.append(_regional_conflict(
                cuts[excluded],
                excluded,
                bits,
                source["cubic_variables"],
            ))
            continue
        candidate = evaluate_alias_candidate(recognized, bits)
        oracle_calls += 1
        for key in (
            "matching_runs", "barrier_matching_runs",
            "initial_edge_scans", "blossom_contractions",
            "matching_work_bound",
        ):
            matching[key] += _integer(candidate["work"][key], f"candidate.{key}")
        if candidate["status"] == "sat":
            assignment = [int(value) for value in candidate["assignment"]]
            alias_assignment = [
                assignment[variable - 1]
                for variable in source["cubic_variables"]
            ] or [0]
            status, reason = "sat", "perfect-matching"
            break
        cut = candidate["cut"]
        prospective_cuts = [*cuts, cut]
        prospective_conflicts = [
            *conflicts,
            _regional_conflict(
                cut,
                len(cuts),
                bits,
                source["cubic_variables"],
            ),
        ]
        prospective_alias = _regional_alias_clauses(
            prospective_cuts,
            source["cubic_variables"],
        )
        if len(cuts) >= profile["max_cuts"]:
            status, reason = "exhausted", "cut-capacity"
        elif len(_canonical(prospective_alias)) > profile["max_cut_bytes"]:
            status, reason = "exhausted", "cut-byte-capacity"
        elif len(_canonical(prospective_conflicts)) > profile["max_journal_bytes"]:
            status, reason = "exhausted", "journal-capacity"
        else:
            cuts = prospective_cuts
            conflicts = prospective_conflicts

    if status == "running" and cursor >= candidate_limit:
        status, reason = (
            ("unsat", "cut-refutation")
            if len(source["cubic_variables"]) < 53
            else ("exhausted", "alias-budget")
        )
    refreshed = _regional_refresh_conflicts(conflicts, len(cuts))
    final_ledger = _regional_ledger(
        status=status,
        reason=reason,
        steps=steps,
        cuts=cuts,
        oracle_calls=oracle_calls,
        matching=matching,
        skipped=skipped,
        conflicts=refreshed,
    )
    result = None
    if status in {"sat", "unsat", "exhausted"}:
        result = _regional_result(
            source,
            profile,
            cuts,
            refreshed,
            final_ledger,
            cursor=cursor,
            status=status,
            reason=reason,
            assignment=assignment,
            alias_assignment=alias_assignment,
        )
    updated = _regional_make_state(
        source,
        profile,
        phase="terminal" if result is not None else "candidate-search",
        cursor=cursor,
        candidate_limit=candidate_limit,
        cuts=cuts,
        conflicts=refreshed,
        ledger=final_ledger,
        result=result,
    )
    return KernelResult(
        state=updated,
        status="done" if result is not None else "yield",
        work=max(1, executed),
        output=result,
    )


__all__ = [
    "AliasCutError", "AliasCutProfile", "AliasCutState", "AliasCutField",
    "REGIONAL_KERNEL_NAME", "REGIONAL_KERNEL_MAX_WORK", "REGIONAL_STATE_SCHEMA",
    "regional_state", "regional_kernel",
]
