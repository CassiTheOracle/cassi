"""Run a PyBoy cartridge through Cassi's field-owned Surface and temporal learner."""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[1]
for _import_root in (str(_ROOT), str(_ROOT / "CassiFI")):
    if _import_root not in sys.path:
        sys.path.insert(0, _import_root)

from cassi_field_atlas import FieldIntelligenceError, canonical_json_bytes
from cassi_field_owner import CapacityLimits, SourceInput
from cassi_hive_session import open_field_session
from CassiQwen.surface.core import SurfaceBroker
from CassiQwen.surface.records import SurfaceWaitError
from CassiQwen.surface.pyboy import PyBoySurfaceBackend
from CassiQwen.surface.visual_adapter import analyze_field_surface_page


_ACTIONS = ("up", "down", "left", "right", "a", "b", "start", "select")
_KEYS = {
    "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight",
    "a": "A", "b": "B", "start": "Start", "select": "Select",
}
_LEGACY_OBSERVATIONS = ("screen-unchanged", "screen-changed")
_VISUAL_CELL_NAMES = tuple(f"cell_{index}" for index in range(16))
_MOTION_CELL_NAMES = tuple(f"cell_{index}" for index in range(64))
_VISUAL_CODE_COUNT = 45
_VISUAL_STATES = tuple(f"visual-c{index:02d}" for index in range(_VISUAL_CODE_COUNT))
_MOTION_CODE_COUNT = 16
_MOTION_STATES = tuple(f"visual-m{index:02d}" for index in range(_MOTION_CODE_COUNT))
_VISUAL_UNAVAILABLE = "visual-unavailable"
_OBSERVATIONS = (*_LEGACY_OBSERVATIONS, *_VISUAL_STATES, *_MOTION_STATES, _VISUAL_UNAVAILABLE)
_VISUAL_MATCH_DISTANCE = 3
_MOTION_MATCH_DISTANCE = 2
_MOTION_LUMA_DELTA = 24
_VISUAL_CODEBOOK_SCHEMA = "cassi.pyboy-visual-codebook.v2"
_INK_LUMA8 = 245
_SCHEMA = "cassifi.temporal-episode.v1"
_OBSERVATION_SCHEMA = "cassi.pyboy-surface-visual.v3"
_OBJECTIVE_SCHEMA = "seek-unseen-visual-profile.v3"
_SEGMENT_STEPS = 128
_MAX_EPISODE_STEPS = 4096
_MAX_EPISODES = 4096
_MAX_TOTAL_STEPS = 131072
_BATCH_SIZE = 8
_BOOT_FRAMES = 300


def _episode_steps(owner: Any, revision_id: str) -> list[dict[str, str]]:
    stored = owner.evidence.source(revision_id)
    content = owner.evidence.read(
        stored,
        allow_historical=True,
        allowed_labels=frozenset({"pyboy-field-only", "train"}),
    )
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("persisted PyBoy temporal episode is not valid JSON") from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema", "steps"}
        or payload.get("schema") != _SCHEMA
        or not isinstance(payload.get("steps"), list)
        or not 1 <= len(payload["steps"]) <= _MAX_EPISODE_STEPS
    ):
        raise RuntimeError("persisted PyBoy temporal episode has an incompatible schema")
    steps: list[dict[str, str]] = []
    for row in payload["steps"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"action", "observation"}
            or row["action"] not in _ACTIONS
            or row["observation"] not in _OBSERVATIONS
        ):
            raise RuntimeError("persisted PyBoy temporal episode contains an invalid step")
        steps.append({"action": row["action"], "observation": row["observation"]})
    return steps


def _memory_id(identity: str, generation: int) -> str:
    return f"pyboy-{identity}-gen-{generation:04d}"


def _participant_prefix(identity: str, generation: int) -> str:
    return f"pyboy-explorer-{identity}-gen-{generation:04d}-lane-"


def _is_state_saturation(exc: FieldIntelligenceError) -> bool:
    return exc.code == "INVALID_TEMPORAL" and "max_states" in str(exc)


def _is_lease_lapse(exc: BaseException) -> bool:
    if isinstance(exc, SurfaceWaitError):
        return True
    text = str(exc).lower()
    return "control stream" in text or "lease" in text or "grant" in text


def _episode_source_prefix(identity: str, generation: int, lane: int) -> str:
    return f"pyboy-play-{identity}-gen-{generation:04d}-lane-{lane:04d}-segment-"


def _lane_segments(owner: Any, memory: Any, identity: str, generation: int, lane: int
                   ) -> list[tuple[int, str, str, list[dict[str, str]]]]:
    prefix = _episode_source_prefix(identity, generation, lane)
    rows = []
    for revision_id in memory.source_revision_ids:
        source_id = owner.evidence.source(revision_id).source_id
        if not source_id.startswith(prefix):
            continue
        suffix = source_id[len(prefix):]
        if len(suffix) != 8 or not suffix.isdigit():
            raise RuntimeError("PyBoy temporal segment identity is invalid")
        rows.append((int(suffix), revision_id, source_id, _episode_steps(owner, revision_id)))
    rows.sort(key=lambda row: row[0])
    if len({row[0] for row in rows}) != len(rows):
        raise RuntimeError("PyBoy temporal memory contains duplicate segment identities")
    return rows


def _repair_interrupted_admission(owner: Any, *, memory_id: str, context: Mapping[str, Any]
                                  ) -> Mapping[str, Any] | None:
    """Re-admit a segment revision that was stored but never learned.

    A commit that stores the episode revision and then fails before the field
    state is published leaves the memory pointing at the superseded parent.
    The engine admits exactly this recovery: the candidate is the active head
    of the same source identity and appends to the admitted parent.
    """
    row = owner.state.temporal(memory_id)
    active = owner.evidence.active_revision_ids()
    repaired = []
    for revision_id in row.source_revision_ids:
        if revision_id in active:
            continue
        parent = owner.evidence.source(revision_id)
        candidate = None
        for known in owner.evidence.all_revision_ids():
            if known == revision_id or known not in active:
                continue
            stored = owner.evidence.source(known)
            if stored.source_id == parent.source_id and stored.parent_revision_id == revision_id:
                candidate = stored
                break
        if candidate is None:
            continue
        content = owner.evidence.read(candidate)
        parent_content = owner.evidence.read(parent, allow_historical=True)
        source = SourceInput(
            source_id=candidate.source_id,
            content=content,
            media_type=candidate.media_type,
            codec=candidate.codec,
            observed_timestamp=candidate.observed_timestamp,
            scope=candidate.scope,
            claim_category=candidate.claim_category,
            fidelity=candidate.fidelity,
            parent_revision_id=revision_id,
            labels=tuple(candidate.labels),
        )
        digest = hashlib.sha256(content).hexdigest()
        operation_id = hashlib.sha256(f"{candidate.source_id}\0{digest}".encode("utf-8")).hexdigest()[:32]
        owner.learn_temporal(f"pyboy-learn-{operation_id}", memory_id=memory_id, source=source,
                             context=context)
        repaired.append({
            "segment": candidate.source_id.split("segment-")[-1],
            "revision": candidate.revision_id[:12],
            "recovered_steps": len(json.loads(content)["steps"]) - len(json.loads(parent_content)["steps"]),
        })
    if not repaired:
        return None
    return {"temporal_repair": {"memory_id": memory_id, "admissions": repaired}}


def _uncommitted_history(owner: Any, memory_id: str, participant_id: str,
                         committed: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    history = [dict(row) for row in owner.state.temporal(memory_id).history(participant_id=participant_id)]
    prefix = [dict(row) for row in committed]
    if history[:len(prefix)] != prefix:
        raise RuntimeError("participant history cannot be reconciled with its persisted temporal episodes")
    return history[len(prefix):]


def _hamming(first: int, second: int) -> int:
    return bin(first ^ second).count("1")


class _VisualCodebook:
    """Bounded 16-bit pattern codebook: nearest-prototype codes with recent-use eviction."""

    def __init__(self, path: Path, *, identity: str, prefix: str, count: int, match_distance: int,
                 bits: int) -> None:
        self._path = path
        self._identity = identity
        self._prefix = prefix
        self._count = count
        self._match_distance = match_distance
        self._bits = bits
        self._patterns: list[int | None] = [None] * count
        self._matches: list[int] = [0] * count
        self._last_use: list[int] = [0] * count
        self.allocations = 0
        self.evictions = 0
        self._load()

    @property
    def size(self) -> int:
        return sum(1 for pattern in self._patterns if pattern is not None)

    @property
    def capacity(self) -> int:
        return self._count

    def save(self) -> None:
        self._save()

    def assign(self, pattern: int, *, clock: int) -> tuple[str, str | None, int | None]:
        """Map a pattern onto a code; returns (token, evicted token, match distance)."""
        best_index: int | None = None
        best_distance: int | None = None
        for index, prototype in enumerate(self._patterns):
            if prototype is None:
                continue
            distance = _hamming(pattern, prototype)
            if best_distance is None or distance < best_distance:
                best_index, best_distance = index, distance
        if best_index is not None and best_distance is not None and best_distance <= self._match_distance:
            self._matches[best_index] += 1
            self._last_use[best_index] = clock
            return self._token(best_index), None, best_distance
        free = next((index for index, prototype in enumerate(self._patterns) if prototype is None), None)
        evicted: str | None = None
        if free is None:
            index = min(range(self._count), key=lambda item: (self._last_use[item], self._matches[item]))
            evicted = self._token(index)
            self.evictions += 1
        else:
            index = free
        self._patterns[index] = pattern
        self._matches[index] = 1
        self._last_use[index] = clock
        self.allocations += 1
        self._save()
        return self._token(index), evicted, best_distance

    def _token(self, index: int) -> str:
        return f"{self._prefix}{index:02d}"

    def _load(self) -> None:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != _VISUAL_CODEBOOK_SCHEMA
            or payload.get("identity") != self._identity
            or payload.get("prefix") != self._prefix
            or payload.get("bits") != self._bits
            or not isinstance(payload.get("patterns"), list)
            or len(payload["patterns"]) != self._count
            or not isinstance(payload.get("matches"), list)
            or len(payload["matches"]) != self._count
            or not isinstance(payload.get("last_use"), list)
            or len(payload["last_use"]) != self._count
        ):
            raise RuntimeError("persisted PyBoy visual codebook has an incompatible schema")
        for index, pattern in enumerate(payload["patterns"]):
            if pattern is not None and (isinstance(pattern, bool) or not isinstance(pattern, int)
                                        or not 0 <= pattern < 1 << self._bits):
                raise RuntimeError("persisted PyBoy visual codebook holds an invalid pattern")
            self._patterns[index] = pattern
        self._matches = [int(value) if isinstance(value, int) and not isinstance(value, bool) else 0
                         for value in payload["matches"]]
        self._last_use = [int(value) if isinstance(value, int) and not isinstance(value, bool) else 0
                          for value in payload["last_use"]]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({
            "schema": _VISUAL_CODEBOOK_SCHEMA,
            "identity": self._identity,
            "prefix": self._prefix,
            "bits": self._bits,
            "patterns": self._patterns,
            "matches": self._matches,
            "last_use": self._last_use,
        }), encoding="utf-8")


_PREVIOUS_LUMAS: list[int | None] | None = None


def _visual_observation(owner: Any, publication: Mapping[str, Any],
                        codebook: _VisualCodebook, motion_codebook: _VisualCodebook, *, clock: int
                        ) -> tuple[str, Mapping[str, Any]]:
    result = analyze_field_surface_page(owner, publication)
    if result.get("status") != "features_ready":
        raise RuntimeError(f"Surface visual analysis was not ready: {result.get('reason_code', result.get('status'))}")
    feature_map = result.get("features")
    grid = feature_map.get("grid_4") if isinstance(feature_map, Mapping) else None
    if not isinstance(grid, Mapping):
        raise RuntimeError("Surface visual adapter did not return its grid-4 feature map")

    selected: dict[str, Any] = {}
    pattern = 0
    available = True
    for bit, name in enumerate(_VISUAL_CELL_NAMES):
        cell = grid.get(name)
        if not isinstance(cell, Mapping):
            raise RuntimeError(f"Surface visual adapter omitted {name}")
        luma = cell.get("mean_luma8")
        masked = cell.get("masked")
        if (
            masked is not False
            or isinstance(luma, bool)
            or not isinstance(luma, int)
            or not 0 <= luma <= 255
        ):
            available = False
            selected[name] = {"masked": masked, "mean_luma8": luma, "ink": None}
            continue
        ink = int(luma < _INK_LUMA8)
        pattern |= ink << bit
        selected[name] = {"masked": False, "mean_luma8": luma, "ink": ink}

    fine_grid = feature_map.get("grid_8") if isinstance(feature_map, Mapping) else None
    if not isinstance(fine_grid, Mapping):
        raise RuntimeError("Surface visual adapter did not return its grid-8 feature map")
    fine_lumas: list[int | None] = []
    fine_available = True
    for name in _MOTION_CELL_NAMES:
        cell = fine_grid.get(name)
        if not isinstance(cell, Mapping):
            raise RuntimeError(f"Surface visual adapter omitted {name} at grid 8")
        luma = cell.get("mean_luma8")
        if cell.get("masked") is not False or isinstance(luma, bool) or not isinstance(luma, int):
            fine_available = False
            fine_lumas.append(None)
            continue
        fine_lumas.append(luma)

    global _PREVIOUS_LUMAS
    motion_pattern = 0
    if fine_available and _PREVIOUS_LUMAS is not None:
        for bit, (current, previous) in enumerate(zip(fine_lumas, _PREVIOUS_LUMAS)):
            if current is not None and previous is not None and abs(current - previous) > _MOTION_LUMA_DELTA:
                motion_pattern |= 1 << bit
    _PREVIOUS_LUMAS = fine_lumas if fine_available else None

    channel = "ink"
    if not available:
        token, evicted, distance = _VISUAL_UNAVAILABLE, None, None
    elif motion_pattern:
        token, evicted, distance = motion_codebook.assign(motion_pattern, clock=clock)
        channel = "motion"
    else:
        token, evicted, distance = codebook.assign(pattern, clock=clock)
    provenance = {
        "schema": _OBSERVATION_SCHEMA,
        "token": token,
        "channel": channel,
        "feature_method": result.get("feature_method"),
        "image_identity": result.get("image_identity"),
        "field_page_ref": result.get("field_page_ref"),
        "coverage": result.get("coverage"),
        "privacy": result.get("privacy"),
        "pattern": f"{pattern:04x}",
        "motion_pattern": f"{motion_pattern:016x}",
        "evicted_code": evicted,
        "match_distance": distance,
        "ink_luma8": _INK_LUMA8,
        "motion_luma_delta": _MOTION_LUMA_DELTA,
        "codebook": {"size": codebook.size, "capacity": codebook.capacity,
                     "allocations": codebook.allocations, "evictions": codebook.evictions},
        "motion_codebook": {"size": motion_codebook.size, "capacity": motion_codebook.capacity,
                            "allocations": motion_codebook.allocations,
                            "evictions": motion_codebook.evictions},
        "cells": selected,
        "motion_lumas": fine_lumas,
    }
    return token, provenance


def _exploration_goals(seen: set[str], current: str) -> tuple[str, ...]:
    states = (*_VISUAL_STATES, *_MOTION_STATES)
    unseen = tuple(token for token in states if token not in seen)
    if unseen:
        return unseen
    return tuple(token for token in states if token != current)


def _legacy_identity(goal: str, rom_hash: str) -> str:
    legacy_context = {
        "domain": "pyboy-field-only",
        "goal": goal,
        "observation_schema": "bgra8-screen-change.v1",
        "rom_sha256": rom_hash,
    }
    return hashlib.sha256(canonical_json_bytes(legacy_context)).hexdigest()[:24]


def _migrate_legacy_memory(owner: Any, *, memory_id: str, identity: str,
                           legacy_memory_id: str, context: Mapping[str, Any]) -> int:
    try:
        legacy = owner.state.temporal(legacy_memory_id)
    except FieldIntelligenceError as exc:
        if exc.code == "TEMPORAL_NOT_FOUND":
            return 0
        raise
    memory = owner.state.temporal(memory_id)
    migrated_prefix = f"pyboy-migrated-{identity}-"
    migrated_lengths: dict[str, int] = {}
    for revision_id in memory.source_revision_ids:
        source_id = owner.evidence.source(revision_id).source_id
        if not source_id.startswith(migrated_prefix):
            continue
        chain, _, index = source_id[len(migrated_prefix):].rpartition("-")
        if not chain or not index.isdigit():
            raise RuntimeError("migrated PyBoy episode identity is invalid")
        row_count = len(_episode_steps(owner, revision_id))
        migrated_lengths[chain] = max(
            migrated_lengths.get(chain, 0), int(index) * _SEGMENT_STEPS + row_count
        )

    chains: dict[str, list[tuple[int, list[dict[str, str]], str]]] = {}
    for revision_id in legacy.source_revision_ids:
        original = owner.evidence.source(revision_id)
        rows = _episode_steps(owner, revision_id)
        chains.setdefault(original.source_id, []).append((len(rows), rows, original.observed_timestamp))

    migrated = 0
    for legacy_source_id, heads in chains.items():
        chain = hashlib.sha256(legacy_source_id.encode("utf-8")).hexdigest()[:16]
        offset = migrated_lengths.get(chain, 0)
        for length, rows, observed_timestamp in sorted(heads, key=lambda head: head[0]):
            while offset < length:
                chunk = rows[offset:offset + _SEGMENT_STEPS]
                _, _ = _learn_episode(
                    owner,
                    memory_id=memory_id,
                    context=context,
                    source_id=f"{migrated_prefix}{chain}-{offset // _SEGMENT_STEPS + 1:04d}",
                    steps=chunk,
                    parent_revision_id=None,
                    observed_timestamp=observed_timestamp,
                )
                migrated += len(chunk)
                offset += len(chunk)
            migrated_lengths[chain] = max(migrated_lengths.get(chain, 0), offset)
    return migrated


def _learn_episode(owner: Any, *, memory_id: str, context: Mapping[str, Any], source_id: str,
                   steps: Sequence[Mapping[str, str]], parent_revision_id: str | None,
                   observed_timestamp: str | None = None) -> tuple[str, Mapping[str, Any]]:
    if not 1 <= len(steps) <= _SEGMENT_STEPS:
        raise RuntimeError(f"PyBoy temporal evidence must contain 1..{_SEGMENT_STEPS} steps")
    content = canonical_json_bytes({"schema": _SCHEMA, "steps": list(steps)})
    digest = hashlib.sha256(content).hexdigest()
    timestamp = observed_timestamp or (
        owner.evidence.source(parent_revision_id).observed_timestamp
        if parent_revision_id is not None
        else source_id
    )
    source = SourceInput(
        source_id=source_id,
        content=content,
        media_type="application/json",
        codec="utf-8",
        observed_timestamp=timestamp,
        scope="pyboy-field-exploration",
        claim_category="controlled-world-observation",
        fidelity="exact-record",
        parent_revision_id=parent_revision_id,
        labels=("pyboy-field-only", "train"),
    )
    operation_id = hashlib.sha256(f"{source_id}\0{digest}".encode("utf-8")).hexdigest()[:32]
    result = owner.learn_temporal(
        f"pyboy-learn-{operation_id}",
        memory_id=memory_id,
        source=source,
        context=context,
    )
    return source.revision_id, result["receipt"]



def _offer(action: str) -> dict[str, Any]:
    return {
        "action": action,
        "cost": 1.0,
        "risk": 0.0,
        "authorized": True,
        "feasible": True,
        "acquisition_allowed": True,
    }


def _intent(broker: SurfaceBroker, *, binding: Mapping[str, Any], grant: Mapping[str, Any],
            mission_id: str, run_id: str, operation_index: int, key: str, state: str,
            publication_generation: int) -> Mapping[str, Any]:
    return broker.submit_intent({
        "operation_id": f"{run_id}-{operation_index:03d}",
        "mission_id": mission_id,
        "binding_id": binding["binding_id"],
        "grant_id": grant["grant_id"],
        "operation": "keyboard.key",
        "payload": {"key": key, "state": state},
        "expected_source_epoch": binding["source_epoch"],
        "expected_geometry_revision": binding["geometry_revision"],
        "dependency_versions": {"publication_generation": publication_generation},
    })


def _admitted_capture(broker: SurfaceBroker, binding_id: str, backend: PyBoySurfaceBackend) -> tuple[Mapping[str, Any], bytes]:
    publication = broker.capture(binding_id, channels=("pixels",))
    frame = backend.frame
    if not isinstance(frame, bytes):
        raise RuntimeError("PyBoy has no published frame")
    return publication, frame


_GRANT_UPDATES = 4096
_GRANT_DURATION_NS = 295_000_000_000
_LEASE_RETRY_ATTEMPTS = 400
_HEARTBEAT_INTERVAL_NS = 10_000_000_000


def _step_count(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("steps must be an integer") from exc
    if not 1 <= number <= _MAX_TOTAL_STEPS:
        raise argparse.ArgumentTypeError(f"steps must be an integer in 1..{_MAX_TOTAL_STEPS}")
    return number


def _frames_per_action(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("frames per action must be an integer") from exc
    if not 1 <= number <= 120:
        raise argparse.ArgumentTypeError("frames per action must be an integer in 1..120")
    return number


def _run(args: argparse.Namespace) -> bool:
    rom_path = (args.rom or (Path(__file__).resolve().with_name("pokemon_yellow.gb"))).expanduser().resolve()
    if args.screenshot is not None and args.screenshot.expanduser().resolve() == rom_path:
        raise ValueError("--screenshot must not overwrite the ROM")
    if not 0 <= args.screenshot_every <= 10_000:
        raise ValueError("--screenshot-every must be an integer in 0..10000")
    if args.screenshot_every and args.screenshot is None:
        raise ValueError("--screenshot-every requires --screenshot")
    if not 10 <= args.lease_seconds <= 295:
        raise ValueError("--lease-seconds must be an integer in 10..295")
    if not rom_path.is_file():
        raise FileNotFoundError(f"Game Boy ROM not found: {rom_path}")
    rom_hash = hashlib.sha256(rom_path.read_bytes()).hexdigest()
    goal = args.goal.strip()
    if not goal or len(goal) > 160:
        raise ValueError("--goal must be 1..160 non-whitespace characters")

    field_home = args.field_home.expanduser().resolve()
    state_path = field_home / "pyboy-state.bin"
    context = {
        "domain": "pyboy-field-only",
        "goal": goal,
        "observation_schema": _OBSERVATION_SCHEMA,
        "objective_schema": _OBJECTIVE_SCHEMA,
        "rom_sha256": rom_hash,
    }
    identity = hashlib.sha256(canonical_json_bytes(context)).hexdigest()[:24]
    codebook = _VisualCodebook(
        field_home / f"visual-codebook-{identity}.json",
        identity=identity,
        prefix="visual-c",
        count=_VISUAL_CODE_COUNT,
        match_distance=_VISUAL_MATCH_DISTANCE,
        bits=len(_VISUAL_CELL_NAMES),
    )
    motion_codebook = _VisualCodebook(
        field_home / f"motion-codebook-{identity}.json",
        identity=identity,
        prefix="visual-m",
        count=_MOTION_CODE_COUNT,
        match_distance=_MOTION_MATCH_DISTANCE,
        bits=len(_MOTION_CELL_NAMES),
    )
    legacy_memory_id = f"pyboy-{_legacy_identity(goal, rom_hash)}"
    mission_id = f"pyboy-mission-{identity}"
    run_id = secrets.token_hex(12)
    bounded_steps = args.steps

    state_budget_bytes = args.state_budget_mib * 1024 * 1024
    history_entries = args.history_entries or max(8, min(64, args.state_budget_mib // 64))
    session = open_field_session(
        field_home,
        role="researcher",
        metadata={"program": "pyboy-field-only", "goal": goal, "rom_sha256": rom_hash},
        limits=CapacityLimits(
            max_state_bytes=state_budget_bytes,
            max_workspace_bytes=state_budget_bytes,
            max_history_entries=history_entries,
        ),
    )
    owner = session.owner
    backend: PyBoySurfaceBackend | None = None
    broker: SurfaceBroker | None = None
    registered = False

    pending: list[dict[str, str]] = []
    spill: list[dict[str, str]] = []
    segment_steps: list[dict[str, str]] = []
    parent_revision_id: str | None = None
    source_id = ""
    segment_index = 0
    lane = 0
    participant_id = ""
    memory_id = ""
    memory_generation = 0
    open_context: dict[str, Any] = {}
    rotations = 0
    step_count = 0
    total_steps = 0
    committed_steps = 0
    operation_index = 0
    recovered_steps = 0
    fallback_actions = 0
    recent_actions: list[str] = []
    completed = False
    interrupted = False
    stopped_reason = "in-progress"
    latest_publication: Mapping[str, Any] | None = None
    current_frame: bytes | None = None
    current_observation: str | None = None
    seen_visual_states: set[str] = set()

    def commit_pending() -> bool:
        nonlocal parent_revision_id, pending, committed_steps
        if not pending:
            return True
        try:
            parent_revision_id, receipt = _learn_episode(
                owner,
                memory_id=memory_id,
                context=open_context,
                source_id=source_id,
                steps=segment_steps,
                parent_revision_id=parent_revision_id,
            )
        except FieldIntelligenceError as exc:
            if not _is_state_saturation(exc):
                raise
            spill[:] = list(pending)
            del segment_steps[len(segment_steps) - len(pending):]
            pending = []
            print(json.dumps({"temporal_state_budget": {"memory_id": memory_id,
                                                        "uncommitted_steps": len(spill)}},
                             ensure_ascii=False))
            return False
        observations = [row["observation"] for row in segment_steps]
        committed_steps += len(segment_steps)
        pending = []
        print(json.dumps({
            "temporal_episode": {
                "source_id": source_id,
                "steps": len(segment_steps),
                "distinct_observations": len(set(observations)),
                "visual_changes": sum(1 for a, b in zip(observations, observations[1:]) if a != b),
            },
            "learning_receipt": receipt,
        }, ensure_ascii=False))
        return True

    def set_segment(index: int) -> bool:
        nonlocal segment_index, source_id, segment_steps, parent_revision_id
        if not commit_pending():
            return False
        segment_index = index
        source_id = f"{_episode_source_prefix(identity, memory_generation, lane)}{index:08d}"
        segment_steps = []
        parent_revision_id = None
        return True

    def absorb(rows: Sequence[Mapping[str, str]], *, replay: bool, recovered: bool) -> None:
        nonlocal total_steps, recovered_steps, operation_sequence
        for position, row in enumerate(rows):
            if len(segment_steps) >= _SEGMENT_STEPS and not set_segment(segment_index + 1):
                spill.extend(dict(item) for item in rows[position:])
                return
            if replay:
                operation_sequence += 1
                advance_field(dict(row)["action"], dict(row)["observation"],
                              f"pyboy-carry-{run_id}:{operation_sequence}")
            segment_steps.append(dict(row))
            pending.append(dict(row))
            total_steps += 1
            if recovered:
                recovered_steps += 1
            if len(pending) >= _BATCH_SIZE and not commit_pending():
                spill.extend(dict(item) for item in rows[position + 1:])
                return

    def open_memory(target_generation: int, carry: Sequence[Mapping[str, str]]) -> None:
        nonlocal memory_id, memory_generation, open_context, participant_id, lane
        nonlocal segment_index, segment_steps, parent_revision_id, source_id, total_steps
        nonlocal committed_steps
        memory_id = _memory_id(identity, target_generation)
        memory_generation = target_generation
        open_context = {**context, "generation": target_generation}
        try:
            owner.inspect_temporal(memory_id)
        except FieldIntelligenceError as exc:
            if exc.code != "TEMPORAL_NOT_FOUND":
                raise
            owner.configure_temporal(
                f"pyboy-configure-{identity}-{target_generation:04d}",
                memory_id=memory_id,
                action_ids=_ACTIONS,
                observation_ids=_OBSERVATIONS,
                max_states=128,
                context=open_context,
            )
        memory = owner.state.temporal(memory_id)
        if (
            tuple(memory.action_ids) != _ACTIONS
            or tuple(memory.observation_ids) != _OBSERVATIONS
            or dict(memory.context) != open_context
            or memory.max_states != 128
        ):
            raise RuntimeError("persisted PyBoy temporal memory has an incompatible codec, capacity, or context")

        if target_generation == 0:
            migrated_steps = _migrate_legacy_memory(
                owner,
                memory_id=memory_id,
                identity=identity,
                legacy_memory_id=legacy_memory_id,
                context=open_context,
            )
            if migrated_steps:
                memory = owner.state.temporal(memory_id)
                print(json.dumps({
                    "legacy_memory_migration": {"from": legacy_memory_id, "to": memory_id,
                                                "migrated_steps": migrated_steps},
                }, ensure_ascii=False))

        lane_prefix = _participant_prefix(identity, target_generation)
        lane = max(
            (int(known[len(lane_prefix):]) for known in memory.participant_ids
             if known.startswith(lane_prefix) and known[len(lane_prefix):].isdigit()),
            default=0,
        )
        participant_id = f"{lane_prefix}{lane:04d}"
        if (
            participant_id in memory.participant_ids
            and len(memory.history(participant_id=participant_id)) >= memory._history_capacity
        ):
            lane += 1
            participant_id = f"{lane_prefix}{lane:04d}"
        if participant_id not in memory.participant_ids:
            if len(memory.participant_ids) >= _MAX_EPISODES - 1:
                raise RuntimeError("PyBoy temporal participant capacity is exhausted")
            owner.bind_temporal(
                f"pyboy-bind-{identity}-{target_generation:04d}-{lane:04d}",
                memory_id=memory_id,
                participant_id=participant_id,
                known_start=False,
            )
            memory = owner.state.temporal(memory_id)

        repair = _repair_interrupted_admission(owner, memory_id=memory_id, context=open_context)
        if repair is not None:
            print(json.dumps(repair, ensure_ascii=False))
            memory = owner.state.temporal(memory_id)

        segments = _lane_segments(owner, memory, identity, target_generation, lane)
        committed_lane = [step for _, _, _, rows in segments for step in rows]
        if segments and len(segments[-1][3]) < _SEGMENT_STEPS:
            segment_index, parent_revision_id, source_id, last_segment = segments[-1]
            segment_steps = list(last_segment)
        else:
            segment_index = segments[-1][0] + 1 if segments else 0
            parent_revision_id = None
            segment_steps = []
            source_id = f"{_episode_source_prefix(identity, target_generation, lane)}{segment_index:08d}"

        total_steps += sum(len(_episode_steps(owner, revision_id)) for revision_id in memory.source_revision_ids)
        committed_steps = len(committed_lane)
        absorb(_uncommitted_history(owner, memory_id, participant_id, committed_lane),
               replay=False, recovered=True)
        absorb(carry, replay=True, recovered=False)

        memory = owner.state.temporal(memory_id)
        for revision_id in memory.source_revision_ids:
            seen_visual_states.update(
                step["observation"] for step in _episode_steps(owner, revision_id)
                if step["observation"] in _VISUAL_STATES
            )
        for known_participant in memory.participant_ids:
            seen_visual_states.update(
                row["observation"] for row in memory.history(participant_id=known_participant)
                if row["observation"] in _VISUAL_STATES
            )
        print(json.dumps({
            "temporal_memory": {
                "memory_id": memory_id,
                "generation": target_generation,
                "participant": participant_id,
                "episodes": len(memory.source_revision_ids),
                "segments": len(segments),
                "committed_steps": len(committed_lane),
                "segment_steps": len(segment_steps),
                "carried_steps": len(carry),
                "total_steps": total_steps,
                "distinct_perceptual_states": len(seen_visual_states),
            },
        }, ensure_ascii=False))

    def rotate(reason: str) -> None:
        nonlocal rotations, lease, lease_remaining
        for _ in range(3):
            carry = list(spill)
            spill.clear()
            rotations += 1
            print(json.dumps({"temporal_memory_rotation": {
                "field_reason": reason,
                "previous": memory_id,
                "next": _memory_id(identity, memory_generation + 1),
                "carried_steps": len(carry),
            }}, ensure_ascii=False))
            open_memory(memory_generation + 1, carry)
            if lease is not None:
                # A rotation replays up to a segment of transitions, which
                # outlives the input watchdog window; the next step acquires a
                # fresh grant and samples the surface under it.
                lease = None
                lease_remaining = 0
                print(json.dumps({"input_lease_release": "temporal-memory-rotation"},
                                 ensure_ascii=False))
            if not spill:
                _uncommitted_history(owner, memory_id, participant_id, segment_steps)
                return
        print(json.dumps({"temporal_memory_rotation_gave_up": len(spill)}, ensure_ascii=False))
        spill.clear()

    def inquire_field(goals: Sequence[str]) -> Mapping[str, Any]:
        return owner.inquire_temporal(
            memory_id,
            participant_id=participant_id,
            operations=tuple(_offer(action) for action in _ACTIONS),
            goal_observations=goals,
            horizon=3,
            max_nodes=4096,
        )

    def advance_field(action: str, observation: str, operation_id: str) -> Mapping[str, Any]:
        return owner.advance_temporal(
            operation_id,
            memory_id=memory_id,
            participant_id=participant_id,
            action=action,
            observation=observation,
        )

    def exploration_action(inquiry: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
        memory = owner.state.temporal(memory_id)
        rows = []
        for index, action in enumerate(_ACTIONS):
            support = memory.predict(action, participant_id=participant_id)["support"]
            rows.append((
                (
                    0 if support["missing_states"] else 1,
                    1 if recent_actions and recent_actions[-1] == action else 0,
                    int(support["exposure"]),
                    -len(support["outcomes"]),
                    index,
                ),
                action,
                {
                    "action": action,
                    "missing_states": len(support["missing_states"]),
                    "exposure": int(support["exposure"]),
                    "outcomes": [item["observation"] for item in support["outcomes"]],
                },
            ))
        rows.sort(key=lambda row: row[0])
        return rows[0][1], {
            "field_status": inquiry.get("status"),
            "field_reason": inquiry.get("reason"),
            "selected": rows[0][1],
            "selected_evidence": rows[0][2],
            "ranked": [row[2] for row in rows],
            "policy": "least-supported-transition.v1",
        }

    screenshot_path = args.screenshot.expanduser().resolve() if args.screenshot is not None else None
    lease: dict[str, Any] | None = None
    lease_expires_ns = 0
    lease_remaining = 0
    lease_opened_ns = 0
    lease_handover_seconds = 0.0
    lease_handovers = 0
    operation_sequence = 0
    heartbeat_sequence = 0
    last_heartbeat_ns = 0
    action_guard_ns = 5_000_000_000

    try:
        discovered = 0
        while discovered < _MAX_EPISODES:
            try:
                owner.inspect_temporal(_memory_id(identity, discovered))
            except FieldIntelligenceError as exc:
                if exc.code != "TEMPORAL_NOT_FOUND":
                    raise
                break
            discovered += 1
        open_memory(max(0, discovered - 1), ())
        if spill:
            rotate("temporal-state-budget-at-startup")

        backend = PyBoySurfaceBackend(
            rom_path,
            source_id="pyboy-world",
            window=args.window,
            save_home=field_home / "game-save",
        )
        state_path = field_home / "pyboy-state.bin"
        if not args.fresh_boot and state_path.is_file():
            try:
                backend.load_state(state_path)
                print(json.dumps({"emulator_state": {"restored": str(state_path)}}, ensure_ascii=False))
            except Exception as exc:
                print(json.dumps({"emulator_state": {"restored": None, "reason": str(exc)[:200]}},
                                 ensure_ascii=False))
                backend.advance(_BOOT_FRAMES)
        else:
            backend.advance(_BOOT_FRAMES)

        def authorize(proposal: Mapping[str, Any]) -> bool:
            scope = proposal.get("scope")
            return (
                proposal.get("purpose") == "surface-grant"
                and proposal.get("backend_id") == backend.backend_id
                and proposal.get("source_id") == backend.source_id
                and proposal.get("operations") == ["keyboard.key"]
                and isinstance(scope, Mapping)
                and scope.get("source_id") == backend.source_id
                and scope.get("max_updates") == _GRANT_UPDATES
            )

        broker = SurfaceBroker(
            home=field_home / "surface",
            field_owner=owner,
            authorizer=authorize,
        )
        broker.register_backend(backend)
        registered = True
        binding = broker.bind(backend.backend_id, backend.source_id)
        binding_id = binding["binding_id"]
        latest_publication, current_frame = _admitted_capture(broker, binding_id, backend)
        current_observation, visual = _visual_observation(owner, latest_publication, codebook,
                                                         motion_codebook, clock=total_steps)
        seen_visual_states.add(current_observation)
        print(json.dumps({
            "pyboy": {"rom": str(rom_path), "rom_sha256": rom_hash, "goal": goal, "window": args.window},
            "field_home": str(field_home),
            "temporal_memory": memory_id,
            "participant": participant_id,
            "objective": _OBJECTIVE_SCHEMA,
            "observation_codec": {
                "schema": _OBSERVATION_SCHEMA,
                "pattern_bits": len(_VISUAL_CELL_NAMES),
                "motion_pattern_bits": len(_MOTION_CELL_NAMES),
                "ink_luma8": _INK_LUMA8,
                "match_distance": _VISUAL_MATCH_DISTANCE,
                "motion_match_distance": _MOTION_MATCH_DISTANCE,
                "motion_luma_delta": _MOTION_LUMA_DELTA,
                "codebook": {"size": codebook.size, "capacity": codebook.capacity,
                             "allocations": codebook.allocations, "evictions": codebook.evictions},
                "motion_codebook": {"size": motion_codebook.size, "capacity": motion_codebook.capacity,
                                    "allocations": motion_codebook.allocations,
                                    "evictions": motion_codebook.evictions},
            },
            "memory_restored": {"generation": memory_generation, "committed_steps": committed_steps,
                                "rotations": rotations, "recovered_steps": recovered_steps,
                                "total_steps": total_steps},
            "field_capacity": {"state_bytes": owner.state.closure_bytes, "state_limit": state_budget_bytes,
                               "history_entries": history_entries},
            "initial_observation": {
                "token": current_observation,
                "frame_sha256": hashlib.sha256(current_frame).hexdigest(),
                "surface_generation": latest_publication.get("generation"),
                "visual": visual,
            },
            "distinct_perceptual_states": len(seen_visual_states),
        }, ensure_ascii=False))

        def acquire_lease() -> None:
            nonlocal lease, lease_expires_ns, lease_remaining, lease_opened_ns
            nonlocal lease_handover_seconds, heartbeat_sequence, last_heartbeat_ns, lease_handovers
            if lease is not None:
                # The input domain admits one controlling lease, so the next
                # grant waits for the watchdog to free the expired one.
                waiting_ns = lease_expires_ns + 300_000_000 - time.monotonic_ns()
                if waiting_ns > 0:
                    started = time.monotonic_ns()
                    time.sleep(waiting_ns / 1_000_000_000)
                    lease_handover_seconds = (time.monotonic_ns() - started) / 1_000_000_000
                lease = None
                lease_handovers += 1
            attempts = 0
            grant_duration_ns = args.lease_seconds * 1_000_000_000
            while True:
                try:
                    granted = broker.grant(
                        mission_id,
                        binding_id,
                        ("keyboard.key",),
                        time.monotonic_ns() + grant_duration_ns,
                        {
                            "max_updates": _GRANT_UPDATES,
                            "max_duration_ns": grant_duration_ns,
                            "heartbeat_timeout_ns": 30_000_000_000,
                        },
                    )
                    break
                except SurfaceWaitError as exc:
                    attempts += 1
                    if attempts > _LEASE_RETRY_ATTEMPTS:
                        raise RuntimeError(
                            f"input lease remained unavailable: {exc.details.get('reason')}"
                        ) from exc
                    time.sleep(0.25)
            lease = granted
            heartbeat_sequence = 0
            lease_opened_ns = time.monotonic_ns()
            lease_expires_ns = lease_opened_ns + int(granted["max_duration_ns"])
            lease_remaining = int(granted["max_updates"])
            last_heartbeat_ns = lease_opened_ns
            print(json.dumps({"input_lease": {
                "grant_id": granted["grant_id"],
                "seconds": round(int(granted["max_duration_ns"]) / 1_000_000_000, 1),
                "updates": granted["max_updates"],
                "handover_seconds": round(lease_handover_seconds, 2),
            }}, ensure_ascii=False))

        while True:
            if bounded_steps is not None and step_count >= bounded_steps:
                stopped_reason = "bounded-limit"
                break
            now = time.monotonic_ns()
            if lease is None or lease_remaining < 2 or now + action_guard_ns >= lease_expires_ns:
                acquire_lease()
                # A grant moves the Surface authority epoch, which requires a
                # genuinely new source sample before the next control intent.
                backend.advance(1)
                now = time.monotonic_ns()
            if now - last_heartbeat_ns >= _HEARTBEAT_INTERVAL_NS:
                heartbeat_sequence += 1
                try:
                    broker.heartbeat(binding_id, lease["grant_id"], heartbeat_sequence)
                except Exception as exc:
                    print(json.dumps({"input_lease_recovery": {"reason": str(exc)[:160],
                                                               "stage": "heartbeat"}},
                                     ensure_ascii=False))
                    lease = None
                    continue
                last_heartbeat_ns = now

            try:
                memory = owner.state.temporal(memory_id)
            except FieldIntelligenceError as exc:
                if not _is_state_saturation(exc):
                    raise
                rotate("temporal-state-budget")
                memory = owner.state.temporal(memory_id)
            if len(memory.history(participant_id=participant_id)) >= memory._history_capacity:
                if not commit_pending():
                    rotate("temporal-state-budget")
                memory = owner.state.temporal(memory_id)
                if len(memory.participant_ids) >= _MAX_EPISODES - 1:
                    stopped_reason = "participant-capacity"
                    break
                lane += 1
                participant_id = f"{_participant_prefix(identity, memory_generation)}{lane:04d}"
                owner.bind_temporal(
                    f"pyboy-bind-{identity}-{memory_generation:04d}-{lane:04d}",
                    memory_id=memory_id,
                    participant_id=participant_id,
                    known_start=False,
                )
                print(json.dumps({"participant_rollover": participant_id,
                                  "field_reason": "temporal history lane reached its capacity"},
                                 ensure_ascii=False))
                if not set_segment(0):
                    rotate("temporal-state-budget")
                memory = owner.state.temporal(memory_id)

            if total_steps >= _MAX_TOTAL_STEPS:
                stopped_reason = "temporal-step-capacity"
                break
            if len(segment_steps) >= _SEGMENT_STEPS:
                if not set_segment(segment_index + 1):
                    rotate("temporal-state-budget")
                memory = owner.state.temporal(memory_id)
                if len(memory.source_revision_ids) >= _MAX_EPISODES:
                    stopped_reason = "temporal-episode-capacity"
                    break

            goals = _exploration_goals(seen_visual_states, current_observation)
            memory_before = owner.state.state_sha256
            try:
                inquiry = inquire_field(goals)
            except FieldIntelligenceError as exc:
                if not _is_state_saturation(exc):
                    raise
                rotate("temporal-state-budget")
                inquiry = inquire_field(goals)
            action = inquiry.get("action")
            if owner.state.state_sha256 != memory_before:
                raise RuntimeError("temporal inquiry unexpectedly mutated persistent field state")
            fallback: Mapping[str, Any] | None = None
            if action not in _ACTIONS:
                action, fallback = exploration_action(inquiry)
                fallback_actions += 1
                print(json.dumps({"field_fallback": fallback}, ensure_ascii=False))
            recent_actions.append(action)
            del recent_actions[:-8]

            key = _KEYS[action]
            receipts: dict[str, Mapping[str, Any]] = {}
            for input_state, frames in (("down", args.frames_per_action), ("up", 1)):
                operation_index += 1
                lease_remaining -= 1
                for attempt in range(2):
                    # A grant, heartbeat, or capture moves the Surface safety
                    # boundary, so the intent carries the publication captured
                    # immediately before it.
                    latest_publication, current_frame = _admitted_capture(broker, binding_id, backend)
                    generation = latest_publication.get("generation")
                    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
                        raise RuntimeError("Surface capture did not provide a publication generation")
                    try:
                        receipt = _intent(
                            broker,
                            binding=binding,
                            grant=lease,
                            mission_id=mission_id,
                            run_id=run_id,
                            operation_index=operation_index,
                            key=key,
                            state=input_state,
                            publication_generation=generation,
                        )
                        break
                    except Exception as exc:
                        if attempt or not _is_lease_lapse(exc):
                            raise
                        print(json.dumps({"input_lease_recovery": {
                            "reason": str(exc)[:160], "stage": f"intent:{input_state}"}},
                            ensure_ascii=False))
                        lease = None
                        acquire_lease()
                        backend.advance(1)
                if receipt.get("disposition") != "delivered" or receipt.get("delivered_count") != 1:
                    raise RuntimeError(f"Surface did not queue {key} {input_state}: {receipt}")
                receipts[input_state] = receipt
                backend.advance(frames)
            latest_publication, current_frame = _admitted_capture(broker, binding_id, backend)

            previous_observation = current_observation
            current_observation, visual = _visual_observation(owner, latest_publication, codebook,
                                                             motion_codebook, clock=total_steps)
            token = current_observation
            seen_visual_states.add(token)
            before_advance = owner.state.state_sha256
            step_count += 1
            operation_sequence += 1
            advance_operation = f"pyboy-advance-{run_id}:{operation_sequence}"
            try:
                advance = advance_field(action, token, advance_operation)
            except FieldIntelligenceError as exc:
                if not _is_state_saturation(exc):
                    raise
                rotate("temporal-state-budget")
                advance = advance_field(action, token, advance_operation)
            if owner.state.state_sha256 == before_advance:
                raise RuntimeError("field did not commit the observed PyBoy temporal transition")
            row = {"action": action, "observation": token}
            segment_steps.append(row)
            pending.append(row)
            total_steps += 1
            print(json.dumps({
                "step": step_count,
                "field_decision": {
                    "status": inquiry.get("status"),
                    "action": action,
                    "reason": inquiry.get("reason"),
                    "goal_observations": goals[:4],
                    "acquisition_allowed": inquiry.get("acquisition_allowed"),
                    "fallback": fallback,
                },
                "action": {"button": action, "key": key, "frames_held": args.frames_per_action},
                "surface_receipts": {"down": receipts["down"], "up": receipts["up"]},
                "effect_observation": {
                    "token": token,
                    "previous_token": previous_observation,
                    "visual_change": token != previous_observation,
                    "frame_sha256": hashlib.sha256(current_frame).hexdigest(),
                    "surface_generation": latest_publication.get("generation"),
                    "visual": visual,
                },
                "temporal_receipt": advance.get("receipt"),
                "episode": {"source_id": source_id, "steps": len(segment_steps),
                            "new_steps": len(pending), "total_steps": total_steps,
                            "unseen_visual_states": (len(_VISUAL_STATES) + len(_MOTION_STATES)
                                                     - len(seen_visual_states))},
                "note": "Surface input acknowledgement is queued-only; the captured frame is the observed game effect.",
            }, ensure_ascii=False))
            if (screenshot_path is not None and args.screenshot_every
                    and step_count % args.screenshot_every == 0):
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                periodic = screenshot_path.with_name(f"{screenshot_path.stem}-{step_count:05d}.png")
                backend.pyboy.screen.image.save(str(periodic))
                print(json.dumps({"screenshot": str(periodic)}, ensure_ascii=False))
            if len(pending) >= _BATCH_SIZE and not commit_pending():
                rotate("temporal-state-budget")

        completed = True
    except KeyboardInterrupt:
        interrupted = True
        stopped_reason = "keyboard-interrupt"
        print(json.dumps({"interrupted": True}, ensure_ascii=False))
    finally:
        try:
            if backend is not None:
                try:
                    backend.save_state(state_path)
                    print(json.dumps({"emulator_state": {"saved": str(state_path)}}, ensure_ascii=False))
                except Exception as exc:
                    print(json.dumps({"emulator_state": {"saved": None, "reason": str(exc)[:200]}},
                                     ensure_ascii=False))
            if not commit_pending():
                print(json.dumps({"unlearned_steps": len(spill),
                                  "field_reason": "temporal state budget exhausted"}, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"pending_commit_error": str(exc)[:200]}, ensure_ascii=False))
        if backend is not None and args.screenshot is not None:
            try:
                screenshot = args.screenshot.expanduser().resolve()
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                backend.pyboy.screen.image.save(str(screenshot))
                print(json.dumps({"screenshot": str(screenshot)}, ensure_ascii=False))
            except Exception as exc:
                print(json.dumps({"screenshot_error": str(exc)[:200]}, ensure_ascii=False))
        print(json.dumps({
            "run_status": stopped_reason if completed or interrupted else "unexpected-exit",
            "interrupted": interrupted,
            "steps_this_run": step_count,
            "steps_total": total_steps,
            "participant": participant_id,
            "episode_source": source_id,
            "episode_steps": len(segment_steps),
            "temporal_memory": memory_id,
            "temporal_generation": memory_generation,
            "memory_rotations": rotations,
            "fallback_actions": fallback_actions,
            "lease_handovers": lease_handovers,
            "unlearned_steps": len(spill),
            "distinct_perceptual_states": len(seen_visual_states),
            "field_capacity": {"state_bytes": owner.state.closure_bytes, "state_limit": state_budget_bytes,
                               "history_entries": history_entries},
            "visual_codebook": {"size": codebook.size, "capacity": codebook.capacity,
                                "allocations": codebook.allocations, "evictions": codebook.evictions},
            "motion_codebook": {"size": motion_codebook.size, "capacity": motion_codebook.capacity,
                                "allocations": motion_codebook.allocations,
                                "evictions": motion_codebook.evictions},
            "last_observation": current_observation,
            "recovered_steps": recovered_steps,
            "resume": "rerun the same command to continue this field-owned exploration",
        }, ensure_ascii=False))
        try:
            if broker is not None:
                broker.close()
        finally:
            try:
                codebook.save()
                motion_codebook.save()
                if backend is not None and not registered:
                    backend.close()
            finally:
                session.close()
    return interrupted


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Let Cassi play a Game Boy ROM: only field inquiry selects actions (no Qwen loaded)."
    )
    parser.add_argument("--rom", type=Path, help="ROM path (default: CassiQwen/pokemon_yellow.gb)")
    parser.add_argument("--field-home", type=Path, default=Path.home() / ".cassi" / "pyboy-field",
                        help="persistent Cassi and Game Boy save directory")
    parser.add_argument("--steps", type=_step_count, default=None,
                        help=f"stop after this many field-selected actions (1..{_MAX_TOTAL_STEPS}); omit to keep playing")
    parser.add_argument("--frames-per-action", type=_frames_per_action, default=8,
                        help="frames to hold each selected button (1..120)")
    parser.add_argument("--goal", default="explore-visible-screen",
                        help="descriptive field context; the field seeks unseen visible-screen profiles")
    parser.add_argument("--window", choices=("null", "SDL2"), default="null",
                        help="headless (null) or visible PyBoy SDL2 window")
    parser.add_argument("--screenshot", type=Path, help="save the final PyBoy screen image")
    parser.add_argument("--screenshot-every", type=int, default=0,
                        help="also save a screen image every N field steps next to --screenshot (0 disables)")
    parser.add_argument("--lease-seconds", type=int, default=int(_GRANT_DURATION_NS / 1_000_000_000),
                        help="input grant duration in seconds (10..295); short values exercise lease handover")
    parser.add_argument("--state-budget-mib", type=int, default=1024,
                        help="field state ceiling in MiB; the run stops cleanly when the live field reaches it")
    parser.add_argument("--history-entries", type=int, default=0,
                        help="retained field journal entries; 0 derives one per 64 MiB of state budget")
    parser.add_argument("--fresh-boot", action="store_true",
                        help="ignore a saved emulator state and boot the cartridge from the start")
    args = parser.parse_args(argv)
    try:
        interrupted = _run(args)
    except FieldIntelligenceError as exc:
        detail = json.dumps(getattr(exc, "details", None), ensure_ascii=False)
        parser.exit(1, f"cassi-pyboy: {exc} {detail}\n")
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"cassi-pyboy: {exc}\n")
    return 130 if interrupted else 0


if __name__ == "__main__":
    raise SystemExit(main())
