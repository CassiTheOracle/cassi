"""Let Cassi's field explore a PyBoy cartridge by places, text, and resumable snapshots."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import secrets
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[1]
for _import_root in (str(_ROOT), str(_ROOT / "CassiFI")):
    if _import_root not in sys.path:
        sys.path.insert(0, _import_root)

from cassi_field_atlas import FieldIntelligenceError, canonical_json_bytes
from cassi_world_field import WorldField
from cassi_field_owner import CapacityLimits, SourceInput
from cassi_hive_session import open_field_session
from CassiQwen.surface.core import SurfaceBroker
from CassiQwen.surface.records import SurfaceWaitError
from CassiQwen.surface.pyboy import PyBoySurfaceBackend
import numpy as np

from CassiQwen.pyboy_world import (
    CELL, COLUMNS, CUT_AGREEMENT, DISCOVERIES, EFFECTS, FIGURE_SPAN, HEADINGS, KINDS, MOVE_AGREEMENT, OUTCOMES,
    REGION_SLOTS, ROWS, STEP_PIXELS, TILE, VERBS, WALK_BUTTONS, Figure, PlaceMap, blank, boxes, changed_tiles, compare,
    figures_in, futile, own_cell, place_key, scene, scene_broke, sight, view_of,
)


_ACTIONS = ("up", "down", "left", "right", "a", "b", "start", "select")
_KEYS = {
    "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight",
    "a": "A", "b": "B", "start": "Start", "select": "Select",
}
_OBSERVATIONS = OUTCOMES
_SCHEMA = "cassifi.temporal-episode.v1"
_OBSERVATION_SCHEMA = "cassi.pyboy-thing-use.v1"
_OBJECTIVE_SCHEMA = "seek-new-places-things-and-uses.v1"
# An engagement with a thing ends within this many presses even if a box stays open.
_ENGAGE_STEPS = 64
# A remembered place pulling this many times harder than Cassi's spot draws it back there.
_LEAP = 4.0
# After this many return periods without a discovery, Cassi resumes elsewhere whatever the pull.
_STUCK_RETURN = 4
_POLL_FRAMES = 4
_BUTTON_OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
_SETTLE_QUIET_FRAMES = 12
_SETTLE_MAX_FRAMES = 120
# A partial change this large starts a walk, a box, or a scene change.
_SCENE_TILES = 40
# Differences from the standing view this small are sprites moving about.
_PLACE_NOISE_TILES = 12
# PyBoy's own SDL2 key bindings, read back from SDL during a demonstration.
_DEMO_SCANCODES = {
    "up": "SDL_SCANCODE_UP", "down": "SDL_SCANCODE_DOWN", "left": "SDL_SCANCODE_LEFT",
    "right": "SDL_SCANCODE_RIGHT", "a": "SDL_SCANCODE_A", "b": "SDL_SCANCODE_S",
    "start": "SDL_SCANCODE_RETURN", "select": "SDL_SCANCODE_BACKSPACE",
}
_SEGMENT_STEPS = 128
_MAX_EPISODE_STEPS = 4096
_MAX_EPISODES = 4096
_MAX_TOTAL_STEPS = 131072
_BATCH_SIZE = 8
_BOOT_FRAMES = 300


def _effect(outcome: str) -> str | None:
    """The effect a press's outcome contributes to a use of a thing; None for standing still or turning."""
    for prefix, effect in (("cut", "cut"), ("moved", "moved"), ("panel", "panel"), ("object", "stirred")):
        if outcome.startswith(prefix):
            return effect
    return None


def _pull(value: float) -> float:
    """A field pull for the log, to three significant figures."""
    return float(f"{value:.3g}")


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


_last_sequence = 0


def _operation_id(kind: str, memory_id: str) -> str:
    """One stable replay producer per exploration identity, sequenced by wall-clock nanoseconds.

    The field keeps one watermark per producer, so producer names must not
    grow with runs or generations; the sequence only has to rise.
    """
    global _last_sequence
    _last_sequence = max(_last_sequence + 1, time.time_ns())
    identity = memory_id.rsplit("-gen-", 1)[0]
    return f"pyboy-{kind}-{identity}:{_last_sequence}"


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
        owner.learn_temporal(_operation_id("learn", memory_id), memory_id=memory_id,
                             source=source, context=context)
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


def _learn_episode(owner: Any, *, memory_id: str, context: Mapping[str, Any], source_id: str,
                   steps: Sequence[Mapping[str, str]], parent_revision_id: str | None,
                   observed_timestamp: str | None = None) -> tuple[str, Mapping[str, Any]]:
    if not 1 <= len(steps) <= _SEGMENT_STEPS:
        raise RuntimeError(f"PyBoy temporal evidence must contain 1..{_SEGMENT_STEPS} steps")
    content = canonical_json_bytes({"schema": _SCHEMA, "steps": list(steps)})
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
    result = owner.learn_temporal(
        _operation_id("learn", memory_id),
        memory_id=memory_id,
        source=source,
        context=context,
    )
    return source.revision_id, result["receipt"]



def _offer(action: str, *, cost: float = 1.0, feasible: bool = True) -> dict[str, Any]:
    return {
        "action": action,
        "cost": cost,
        "risk": 0.0,
        "authorized": True,
        "feasible": feasible,
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
    if args.demo and args.window != "SDL2":
        raise ValueError("--demo needs --window SDL2 so you can play")
    if not -1 <= args.speed <= 64:
        raise ValueError("--speed must be -1 (auto) or an integer in 0..64")
    if not 4 <= args.return_after <= 100_000:
        raise ValueError("--return-after must be an integer in 4..100000")
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
    places = PlaceMap(field_home / f"place-map-{identity}")
    world_field = WorldField(field_home / f"world-field-{identity}.json")
    if not world_field.exists:
        # The field takes over a map drawn before it held the world.
        world_field.seed(
            ((int(cell["zone"]), *map(int, cell["pos"])) for cell in places.cells.values()),
            (((int(places.cells[key]["zone"]), *map(int, places.cells[key]["pos"])), action, outcome)
             for key, row in places.tries.items() if key in places.cells
             for action, (outcome, _) in row.items() if action in WALK_BUTTONS))
    # Scenery is dreamt afresh from the remembered backgrounds on every start.
    places.ground_changed.update(places.grounds)
    rng = random.Random(f"{identity}:{places.returns}")
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
            max_checkpoint_frequency=args.checkpoint_interval,
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
    lane = 0  # journey episode number; names evidence segments
    slot = 0  # participant lane in the temporal field; one is live at a time
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
    screen: np.ndarray | None = None
    world: np.ndarray | None = None
    event_key: str | None = None
    figures: list[Figure] = []
    place: str | None = None
    zone: int | None = None
    position: tuple[int, int] | None = None
    since_discovery = 0
    unproductive_actions = 0
    spent_skipped = 0
    last_step: str | None = None
    # Which way Cassi faces and the use of a thing in progress.
    heading: str | None = None
    engagement: dict[str, Any] | None = None

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
                "discoveries": sum(1 for observation in observations if observation in DISCOVERIES),
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
                              _operation_id("carry", memory_id))
            segment_steps.append(dict(row))
            pending.append(dict(row))
            total_steps += 1
            if recovered:
                recovered_steps += 1
            if len(pending) >= _BATCH_SIZE and not commit_pending():
                spill.extend(dict(item) for item in rows[position + 1:])
                return

    def open_memory(target_generation: int, carry: Sequence[Mapping[str, str]]) -> None:
        nonlocal memory_id, memory_generation, open_context, participant_id, lane, slot
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
                f"pyboy-configure-{identity}:{owner.state.generation}",
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

        lane_prefix = _participant_prefix(identity, target_generation)
        slot = max(
            (int(known[len(lane_prefix):]) for known in memory.participant_ids
             if known.startswith(lane_prefix) and known[len(lane_prefix):].isdigit()),
            default=0,
        )
        participant_id = f"{lane_prefix}{slot:04d}"
        if (
            participant_id in memory.participant_ids
            and len(memory.history(participant_id=participant_id)) >= memory._history_capacity
        ):
            slot += 1
            participant_id = f"{lane_prefix}{slot:04d}"
        if participant_id not in memory.participant_ids:
            if len(memory.participant_ids) >= _MAX_EPISODES - 1:
                raise RuntimeError("PyBoy temporal participant capacity is exhausted")
            owner.bind_temporal(
                f"pyboy-bind-{identity}:{owner.state.generation}",
                memory_id=memory_id,
                participant_id=participant_id,
                known_start=False,
            )
            memory = owner.state.temporal(memory_id)

        # Earlier journeys each held a participant lane; their steps are
        # committed evidence, so only the live lane stays in the field.
        idle = [known for known in memory.participant_ids
                if known.startswith(lane_prefix) and known != participant_id]
        for known in idle:
            owner.release_temporal(
                f"pyboy-release-{identity}:{owner.state.generation}",
                memory_id=memory_id,
                participant_id=known,
            )
        if idle:
            memory = owner.state.temporal(memory_id)
            print(json.dumps({"temporal_lanes_released": {"memory_id": memory_id, "released": len(idle),
                                                          "field_bytes": owner.state.closure_bytes}},
                             ensure_ascii=False))

        repair = _repair_interrupted_admission(owner, memory_id=memory_id, context=open_context)
        if repair is not None:
            print(json.dumps(repair, ensure_ascii=False))
            memory = owner.state.temporal(memory_id)

        episode_prefix = f"pyboy-play-{identity}-gen-{target_generation:04d}-lane-"
        known_lanes = [slot]
        for revision_id in memory.source_revision_ids:
            known_source = owner.evidence.source(revision_id).source_id
            number = known_source[len(episode_prefix):len(episode_prefix) + 4]
            if known_source.startswith(episode_prefix) and number.isdigit():
                known_lanes.append(int(number))
        lane = max(known_lanes)
        segments = _lane_segments(owner, memory, identity, target_generation, lane)
        committed_lane = [step for _, _, _, rows in segments for step in rows]
        history = [dict(row) for row in memory.history(participant_id=participant_id)]
        if history[:len(committed_lane)] != committed_lane:
            # The live lane was reset for a later journey after this
            # episode's last commit, so its history opens the next episode.
            lane += 1
            segments = []
            committed_lane = []
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
            },
        }, ensure_ascii=False))

    def rotate(reason: str) -> None:
        nonlocal rotations, last_heartbeat_ns
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
            retire_generations()
            # The grant stays held across the rotation; the next step renews it
            # at once, and a grant that lapsed meanwhile is replaced there.
            last_heartbeat_ns = 0
            if not spill:
                _uncommitted_history(owner, memory_id, participant_id, segment_steps)
                return
        print(json.dumps({"temporal_memory_rotation_gave_up": len(spill)}, ensure_ascii=False))
        spill.clear()

    def inquire_field(goals: Sequence[str], offers: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        return owner.inquire_temporal(
            memory_id,
            participant_id=participant_id,
            operations=tuple(offers),
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

    def exploration_action(inquiry: Mapping[str, Any], spent: set[str],
                           uses: Mapping[str, Any], approach: Sequence[str]) -> tuple[str, Mapping[str, Any]]:
        def tier(action: str) -> int:
            """Use a curious thing, then walk where the world field pulls."""
            return 0 if action in uses else 1 if action in approach else 2

        memory = owner.state.temporal(memory_id)
        rows = []
        for index, action in enumerate(_ACTIONS):
            if action in spent:
                continue
            support = memory.predict(action, participant_id=participant_id)["support"]
            rows.append((
                (
                    tier(action),
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
            "policy": "curious-then-world-flow.v1",
            "spent": sorted(spent),
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
    action_guard_ns = 10_000_000_000

    def retire_generations() -> None:
        """Release every earlier generation's automaton from the live field."""
        prefix = f"pyboy-{identity}-gen-"
        for row in tuple(owner.state.temporal_fields):
            suffix = row.memory_id[len(prefix):]
            if row.memory_id.startswith(prefix) and suffix.isdigit() and int(suffix) < memory_generation:
                receipt = owner.retire_temporal(
                    f"pyboy-retire-{identity}:{owner.state.generation}", memory_id=row.memory_id)
                print(json.dumps({"temporal_memory_retired": row.memory_id,
                                  "evidence_revisions": len(receipt["receipt"]["source_revision_ids"]),
                                  "field_bytes": owner.state.closure_bytes}, ensure_ascii=False))

    def release_foreign_lanes() -> None:
        """Release explorer lanes held by memories of earlier contexts.

        Their journeys are committed evidence and their learned transitions
        stay; only the idle per-journey belief slices leave the field.
        """
        for row in tuple(owner.state.temporal_fields):
            if not row.memory_id.startswith("pyboy-") or row.memory_id == memory_id:
                continue
            idle = [known for known in row.participant_ids if known.startswith("pyboy-explorer-")]
            for known in idle:
                owner.release_temporal(
                    f"pyboy-release-{identity}:{owner.state.generation}",
                    memory_id=row.memory_id,
                    participant_id=known,
                )
            if idle:
                print(json.dumps({"temporal_lanes_released": {"memory_id": row.memory_id, "released": len(idle),
                                                              "field_bytes": owner.state.closure_bytes}},
                                 ensure_ascii=False))

    try:
        prefix = f"pyboy-{identity}-gen-"
        generations = [
            int(row.memory_id[len(prefix):]) for row in owner.state.temporal_fields
            if row.memory_id.startswith(prefix) and row.memory_id[len(prefix):].isdigit()
        ]
        open_memory(max(generations, default=0), ())
        retire_generations()
        release_foreign_lanes()
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
        backend.set_speed(args.speed if args.speed >= 0 else (1 if args.window == "SDL2" else 0))

        def look() -> np.ndarray:
            return view_of(backend.frame)

        def settle(warped: bool) -> tuple[np.ndarray, bool, int, np.ndarray]:
            """Run until the picture holds still apart from one blinking tile.

            Returns the settled view, whether the scene broke on the way, the
            frames spent, and the blinking tile that novelty ignores.
            """
            last = look()
            warped = warped or blank(last)
            flicker = np.zeros((ROWS, COLUMNS), dtype=bool)
            frames = quiet = 0
            while frames < _SETTLE_MAX_FRAMES and quiet < _SETTLE_QUIET_FRAMES:
                backend.advance(2)
                frames += 2
                now = look()
                changed = changed_tiles(last, now)
                if blank(now):
                    warped = True
                elif (not warped and not blank(last) and int(changed.sum()) > _SCENE_TILES
                      and scene_broke(last, now)):
                    warped = True
                if not blank(now) and int((flicker | changed).sum()) <= 1:
                    flicker |= changed
                    quiet += 2
                else:
                    flicker[:] = False
                    quiet = 0
                last = now
            return last, warped, frames, flicker

        def stand(at_zone: int | None, estimate: tuple[int, int], view: np.ndarray) -> tuple[bool, bool]:
            """Stand at a place in the world view; returns (new place or new object in view, new area).

            A framed window on screen is a message over the world: the view
            then teaches nothing about the place and the message stays open.
            """
            nonlocal place, zone, position, world, event_key, figures
            place, new_place, new_area, zone = places.visit(at_zone, estimate, step=total_steps)
            position = tuple(places.cells[place]["pos"])
            world_field.stand((zone, int(position[0]), int(position[1])))
            world = view
            veil = boxes(view)
            if veil.any():
                event_key = sight(view, veil)
                figures = []
                return new_place, new_area
            places.remember_view(zone, position, view)
            event_key = None
            figures = places.observe(zone, position, view, place) or []
            return new_place or any(figure.new for figure in figures), new_area

        def arrive(view: np.ndarray) -> tuple[bool, bool]:
            """A new scene: relocalize against remembered keyframes, else open a new area."""
            located = places.locate(view)
            return stand(*(located if located is not None else (None, (0, 0))), view)

        def context_of() -> str:
            """Where a press is made: the standing place, or the event open on screen."""
            return place if event_key is None and place is not None else f"e:{event_key}"

        def keep_snapshot() -> None:
            if place is not None and event_key is None and places.stale(place):
                places.store_snapshot(place, backend.state_bytes())

        def things_now() -> dict[tuple[int, int], str]:
            """The salient things of the standing view by screen cell; nothing while a box is open."""
            if event_key is not None or world is None or place is None:
                return {}
            return scene(world, figures, places.self_box())

        def beside(direction: str) -> tuple[int, int] | None:
            me = own_cell(places.self_box())
            if me is None:
                return None
            dx, dy = HEADINGS[direction]
            return me[0] + dx, me[1] + dy

        def cell_key(cell: tuple[int, int]) -> str:
            """The world cell under screen cell ``cell`` at the standing place."""
            me = own_cell(places.self_box())
            return place_key(zone, (position[0] + cell[0] - me[0], position[1] + cell[1] - me[1]))

        def curiosity(things: Mapping[tuple[int, int], str]) -> dict[str, dict[str, str]]:
            """Presses that use a curious verb on a thing beside Cassi.

            A direction walks into the thing on that side; the buttons act on
            the thing Cassi faces.
            """
            if own_cell(places.self_box()) is None or zone is None or position is None:
                return {}
            uses: dict[str, dict[str, str]] = {}
            for direction in HEADINGS:
                cell = beside(direction)
                thing = things.get(cell)
                if thing is None:
                    continue
                for verb in places.curious(thing, cell_key(cell)):
                    if verb == "walk":
                        uses[direction] = {"thing": thing, "verb": verb}
                    elif direction == heading:
                        uses[verb] = {"thing": thing, "verb": verb}
            return uses

        def dream() -> None:
            """Let the world field take in scenery the areas' backgrounds learned since it last dreamt."""
            me = own_cell(places.self_box())
            if me is None or not places.ground_changed:
                return
            for area in sorted(places.ground_changed):
                world_field.dream(area, places.ground_patches(area, me))
            places.ground_changed.clear()

        def feel_walk(origin: tuple[int, int, int] | None, heading_before: str | None, action: str,
                      perception: Mapping[str, Any]) -> None:
            """Teach the world field where a walk from ``origin`` took Cassi: a step, a door, or a wall.

            A press that left Cassi in place while it already faced that way,
            or left the whole screen still, met a wall; a first press only turns.
            """
            if origin is None:
                return
            base = perception["base"]
            if base.startswith(("moved", "cut")):
                if event_key is None and zone is not None and position is not None:
                    arrived = (zone, int(position[0]), int(position[1]))
                    if arrived != origin:
                        world_field.walked(origin, action, arrived)
            elif event_key is None and (base == "still" or heading_before == action):
                world_field.walked(origin, action, None)

        def perceive(action: str, before: np.ndarray, after: np.ndarray, warped: bool,
                     flicker: np.ndarray) -> dict[str, Any]:
            """Name what the press did to the picture and place the result on the map."""
            nonlocal world, event_key, since_discovery, unproductive_actions, last_step, figures
            nonlocal heading, engagement
            context = context_of()
            at_place = event_key is None
            if engagement is None and at_place and place is not None:
                # A direction walks into the thing on that side; a button acts
                # on the thing Cassi faces.
                verb, direction = ("walk", action) if action in HEADINGS else (action, heading)
                cell = beside(direction) if direction is not None else None
                thing = things_now().get(cell) if cell is not None else None
                if thing is not None:
                    engagement = {"thing": thing, "verb": verb, "cell": cell, "where": cell_key(cell),
                                  "place": place, "effects": set(), "steps": 0, "taught": False}
            steady = ~flicker
            (dx, dy), slide, still = compare(before, after)
            steps = (-round(dx / STEP_PIXELS), -round(dy / STEP_PIXELS))
            new_area = False
            if warped or blank(after) or max(slide, still) < CUT_AGREEMENT:
                new_place, new_area = arrive(after)
                outcome = "cut-new" if new_place else "cut-seen"
            elif steps != (0, 0) and slide >= MOVE_AGREEMENT and slide > still:
                if zone is None:
                    new_place, new_area = arrive(after)
                else:
                    base = position or (0, 0)
                    new_place, new_area = stand(zone, (base[0] + steps[0], base[1] + steps[1]), after)
                outcome = "moved-new" if new_place else "moved-seen"
            else:
                pixels = (before != after) & np.repeat(np.repeat(steady, TILE, axis=0), TILE, axis=1)
                if not pixels.any():
                    outcome = "still"
                else:
                    # Standing in the world, read the change as figures
                    # against the area's background; a framed window is a
                    # message, and inside it every change belongs to it.
                    changed = changed_tiles(before, after) & steady
                    off = (changed_tiles(world, after) & steady) if world is not None else changed
                    veil = boxes(after)
                    touched: list[Figure] = []
                    if event_key is None and zone is not None and place is not None and not veil.any():
                        seen = places.observe(zone, position, after, place)
                        touched = [figure for figure in seen or () if figure.touches(pixels)]
                        if not touched:
                            touched = figures_in(pixels, after)
                            places.judge(touched, in_world=True)
                        figures = seen if seen is not None else touched
                    if veil.any() or not touched or any(figure.large for figure in touched):
                        region = places.region(changed)
                        fresh = places.notice(f"{region}:{sight(after, changed)}")
                        outcome = f"panel-{region:02d}-{'new' if fresh else 'seen'}"
                        # A large change can uncover a remembered scene, as
                        # when a menu opened over the world closes again.
                        located = (places.locate(after) if not veil.any() and int(changed.sum()) > _SCENE_TILES
                                   else None)
                        if veil.any():
                            # The open message is its words on screen.
                            event_key = sight(after, veil & steady)
                        elif located is not None and located != (zone, position):
                            stand(*located, after)
                        elif boxes(before).any() or int(off.sum()) <= _PLACE_NOISE_TILES:
                            # The message closed over the world it covered.
                            world = after
                            event_key = None
                            if zone is not None and place is not None:
                                figures = places.observe(zone, position, after, place) or []
                        else:
                            event_key = sight(after, off)
                    else:
                        if any(figure.new for figure in figures):
                            outcome = "object-new"
                        elif all(figure.own for figure in touched):
                            outcome = "self"
                        else:
                            outcome = "object-seen"
                        world = after
            keep_snapshot()
            base = outcome
            used: dict[str, Any] | None = None
            if engagement is not None:
                engagement["steps"] += 1
                effect = _effect(base)
                if effect is not None:
                    engagement["effects"].add(effect)
                engagement["taught"] |= base in DISCOVERIES
                if event_key is None or engagement["steps"] >= _ENGAGE_STEPS:
                    effects = engagement["effects"]
                    if event_key is None and place == engagement["place"] and not effects & {"moved", "cut"}:
                        now = things_now().get(engagement["cell"])
                        if now is None:
                            effects.add("gone")
                        elif now != engagement["thing"]:
                            effects.add("changed")
                    effects = sorted(effects) or ["still"]
                    fresh = places.learn_use(engagement["thing"], engagement["verb"], effects,
                                             engagement["where"], taught=engagement["taught"])
                    used = {"thing": engagement["thing"], "verb": engagement["verb"], "effects": effects,
                            "fresh": fresh, "presses": engagement["steps"]}
                    if fresh and outcome not in DISCOVERIES:
                        outcome = "use-new"
                    engagement = None
            if at_place and action in HEADINGS:
                heading = action
            if base.startswith("cut"):
                heading = None
            facing: str | None = None
            if event_key is None and heading is not None:
                cell = beside(heading)
                facing = things_now().get(cell) if cell is not None else None
                if facing is not None and outcome not in DISCOVERIES and places.curious(facing, cell_key(cell)):
                    outcome = "facing-thing"
            since_discovery = 0 if outcome in DISCOVERIES else since_discovery + 1
            last_step = action if action in _BUTTON_OPPOSITE and base.startswith("moved") else None
            places.note_try(context, action, outcome)
            if futile(outcome, at_place=at_place):
                unproductive_actions += 1
            return {"outcome": outcome, "base": base, "place": place, "area": zone, "new_area": new_area,
                    "position": list(position) if position is not None else None,
                    "event_open": event_key is not None,
                    "slide": [dx, dy, round(slide, 3)],
                    "facing": facing, "use": used,
                    "figures": [figure.record() for figure in figures]}

        backend.advance(30)
        screen, _, _, _ = settle(True)
        arrive(screen)
        keep_snapshot()
        print(json.dumps({
            "pyboy": {"rom": str(rom_path), "rom_sha256": rom_hash, "goal": goal, "window": args.window,
                      "mode": "demonstration" if args.demo else "field-play"},
            "field_home": str(field_home),
            "temporal_memory": memory_id,
            "participant": participant_id,
            "objective": _OBJECTIVE_SCHEMA,
            "perception": {"schema": _OBSERVATION_SCHEMA, "source": "framebuffer pixels",
                           "kinds": list(KINDS), "region_slots": REGION_SLOTS, "object_span": FIGURE_SPAN,
                           "observations": len(OUTCOMES), "curiosity_goals": len(DISCOVERIES),
                           "thing_cell": CELL, "verbs": list(VERBS), "effects": list(EFFECTS)},
            "memory_restored": {"generation": memory_generation, "committed_steps": committed_steps,
                                "rotations": rotations, "recovered_steps": recovered_steps,
                                "total_steps": total_steps},
            "field_capacity": {"state_bytes": owner.state.closure_bytes, "state_limit": state_budget_bytes,
                               "history_entries": history_entries},
            "world": places.summary(),
            "world_field": world_field.summary(),
            "screen": {"place": place, "area": zone, "position": list(position) if position else None},
        }, ensure_ascii=False))

        def new_lane(reason: str, *, fresh_slot: bool = False) -> bool:
            """Open the next journey episode on a cleared lane; False when the memory has no lanes left.

            The live participant lane is reset for a new journey; a lane whose
            history is full is replaced by a fresh one and released.
            """
            nonlocal lane, slot, participant_id
            if not commit_pending():
                rotate("temporal-state-budget")
            if fresh_slot:
                memory = owner.state.temporal(memory_id)
                if len(memory.participant_ids) >= _MAX_EPISODES - 1:
                    return False
                previous = participant_id
                slot += 1
                participant_id = f"{_participant_prefix(identity, memory_generation)}{slot:04d}"
                owner.bind_temporal(
                    f"pyboy-bind-{identity}:{owner.state.generation}",
                    memory_id=memory_id,
                    participant_id=participant_id,
                    known_start=False,
                )
                if previous in owner.state.temporal(memory_id).participant_ids:
                    owner.release_temporal(
                        f"pyboy-release-{identity}:{owner.state.generation}",
                        memory_id=memory_id,
                        participant_id=previous,
                    )
            else:
                owner.reset_temporal(
                    f"pyboy-reset-{identity}:{owner.state.generation}",
                    memory_id=memory_id,
                    participant_id=participant_id,
                    known_start=False,
                )
            lane += 1
            print(json.dumps({"participant_rollover": participant_id, "episode_lane": lane,
                              "field_reason": reason}, ensure_ascii=False))
            if not set_segment(0):
                rotate("temporal-state-budget")
            return True

        def record(action: str, perception: Mapping[str, Any], detail: Mapping[str, Any]) -> None:
            nonlocal step_count, operation_sequence, total_steps, current_observation
            outcome = perception["outcome"]
            before_advance = owner.state.state_sha256
            step_count += 1
            operation_sequence += 1
            advance_operation = _operation_id("advance", memory_id)
            try:
                advance = advance_field(action, outcome, advance_operation)
            except FieldIntelligenceError as exc:
                if not _is_state_saturation(exc):
                    raise
                rotate("temporal-state-budget")
                advance = advance_field(action, outcome, advance_operation)
            if owner.state.state_sha256 == before_advance:
                raise RuntimeError("field did not commit the observed PyBoy temporal transition")
            current_observation = outcome
            row = {"action": action, "observation": outcome}
            segment_steps.append(row)
            pending.append(row)
            total_steps += 1
            print(json.dumps({
                "step": step_count,
                "action": action,
                **perception,
                **detail,
                "world": {"places": len(places.cells), "areas": len(places.zones),
                          "sights": len(places.events), "regions": len(places.regions),
                          "objects": places.kind_count, "self": places.self_box(), "things": len(places.uses)},
                "world_field": world_field.summary(),
                "field_generation": owner.state.generation,
                "total_steps": total_steps,
            }, ensure_ascii=False))
            if (screenshot_path is not None and args.screenshot_every
                    and step_count % args.screenshot_every == 0):
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                periodic = screenshot_path.with_name(f"{screenshot_path.stem}-{step_count:05d}.png")
                backend.pyboy.screen.image.save(str(periodic))
            if len(pending) >= _BATCH_SIZE and not commit_pending():
                rotate("temporal-state-budget")
            if step_count % 16 == 0:
                places.save()
                world_field.save()

        def demo_buttons() -> list[str]:
            import sdl2
            keys = sdl2.SDL_GetKeyboardState(None)
            return [name for name in _ACTIONS if keys[getattr(sdl2, _DEMO_SCANCODES[name])]]

        def acquire_lease() -> None:
            nonlocal lease, lease_expires_ns, lease_remaining, lease_opened_ns
            nonlocal lease_handover_seconds, heartbeat_sequence, last_heartbeat_ns, lease_handovers
            handover_started = None
            if lease is not None:
                # The input domain admits one controlling lease; handing the
                # old grant back lets the watchdog free the domain at once.
                handover_started = time.monotonic_ns()
                broker.relinquish(binding_id, lease["grant_id"])
                # The watchdog frees the domain, then neutralizes the binding;
                # the next grant follows both.
                time.sleep(0.3)
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
            if handover_started is not None:
                lease_handover_seconds = (time.monotonic_ns() - handover_started) / 1_000_000_000
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

        if args.demo:
            print(json.dumps({"demonstration": "play in the PyBoy window: arrows, A=a, B=s, "
                                               "Start=Enter, Select=Backspace; close the window to stop"},
                             ensure_ascii=False))
        while True:
            if args.demo:
                # Run the game at full speed until Carina holds a button.
                while backend.running and not demo_buttons():
                    backend.advance(1)
                if not backend.running:
                    stopped_reason = "window-closed"
                    break
                screen = look()
            if bounded_steps is not None and step_count >= bounded_steps:
                stopped_reason = "bounded-limit"
                break
            if total_steps >= _MAX_TOTAL_STEPS:
                stopped_reason = "temporal-step-capacity"
                break
            try:
                memory = owner.state.temporal(memory_id)
            except FieldIntelligenceError as exc:
                if not _is_state_saturation(exc):
                    raise
                rotate("temporal-state-budget")
                memory = owner.state.temporal(memory_id)
            if len(memory.history(participant_id=participant_id)) >= memory._history_capacity:
                if not new_lane("temporal history lane reached its capacity", fresh_slot=True):
                    stopped_reason = "participant-capacity"
                    break
            if len(segment_steps) >= _SEGMENT_STEPS:
                if not set_segment(segment_index + 1):
                    rotate("temporal-state-budget")
                memory = owner.state.temporal(memory_id)
                if len(memory.source_revision_ids) >= _MAX_EPISODES:
                    stopped_reason = "temporal-episode-capacity"
                    break

            if args.demo:
                # Carina plays; the field learns what each of her presses did.
                held = demo_buttons()
                if not held:
                    continue
                action = held[0]
                before = screen
                warped = False
                frames = 0
                while action in demo_buttons() and backend.running:
                    backend.advance(1)
                    frames += 1
                    warped = warped or blank(look())
                after, warped, settle_frames, flicker = settle(warped)
                screen = after
                origin = ((zone, int(position[0]), int(position[1])) if action in WALK_BUTTONS and event_key is None
                          and place is not None and zone is not None and position is not None else None)
                heading_before = heading
                perception = perceive(action, before, after, warped, flicker)
                feel_walk(origin, heading_before, action, perception)
                record(action, perception, {"source": "demonstration", "frames": frames + settle_frames})
                continue

            now_ns = time.monotonic_ns()
            if lease is None or lease_remaining < 2 or now_ns + action_guard_ns >= lease_expires_ns:
                acquire_lease()
                # A grant moves the Surface authority epoch, which requires a
                # genuinely new source sample before the next control intent.
                backend.advance(1)
                now_ns = time.monotonic_ns()
            if now_ns - last_heartbeat_ns >= _HEARTBEAT_INTERVAL_NS:
                heartbeat_sequence += 1
                try:
                    broker.heartbeat(binding_id, lease["grant_id"], heartbeat_sequence)
                except Exception as exc:
                    print(json.dumps({"input_lease_recovery": {"reason": str(exc)[:160],
                                                               "stage": "heartbeat"}},
                                     ensure_ascii=False))
                    lease = None
                    continue
                last_heartbeat_ns = now_ns

            # The world field: remembered things release their promise, the
            # field dreams over newly seen scenery and settles, and the flow
            # at Cassi's body is the way the whole world pulls it.
            things = things_now()
            me = own_cell(places.self_box())
            body: tuple[int, int, int] | None = None
            if event_key is None and place is not None and me is not None and zone is not None and position is not None:
                places.see(zone, (position[0] - me[0], position[1] - me[1]), things)
                body = (zone, int(position[0]), int(position[1]))
            dream()
            world_field.set_sources({cell: worth for _, cell, worth in places.prospects()})
            world_field.settle()
            way = world_field.flow(body) if body is not None else None
            if since_discovery >= args.return_after:
                # Go-Explore through the field: nothing new for a while, and
                # either no pull here or a remembered place pulls far harder
                # than anything reachable on foot, so resume from there.
                pulls = {key: world_field.pull((int(cell["zone"]), *map(int, cell["pos"])))
                         for key, cell in places.resumable(place).items()}
                here_pull = world_field.pull(body) if body is not None else 0.0
                if pulls and (way is None or since_discovery >= _STUCK_RETURN * args.return_after
                              or max(pulls.values()) > _LEAP * here_pull):
                    target = places.choose_return(rng, exclude=place, pull=pulls)
                else:
                    target = None
                if target is not None:
                    backend.restore_bytes(places.snapshot(target))
                    screen, _, _, _ = settle(False)
                    place = target
                    zone = int(places.cells[target]["zone"])
                    position = tuple(places.cells[target]["pos"])
                    world = screen
                    figures = places.observe(zone, position, screen, target) or []
                    event_key = None
                    since_discovery = 0
                    last_step = None
                    heading = None
                    engagement = None
                    places.save()
                    world_field.save()
                    print(json.dumps({"return": {"place": target, "area": zone, "returns": places.returns,
                                                 "pull": _pull(pulls.get(target, 0.0)),
                                                 "pull_here": _pull(here_pull)}}, ensure_ascii=False))
                    if not new_lane("resumed exploration from a remembered place"):
                        stopped_reason = "participant-capacity"
                        break
                    continue

            # What Cassi has learned about this spot shapes the field's offers:
            # presses that did nothing here are infeasible and a step is not
            # undone while another way is open. Using a curious thing beside
            # Cassi and walking where the world field pulls are cheap.
            spent = places.spent(context_of(), at_place=event_key is None, actions=_ACTIONS)
            if last_step is not None and event_key is None:
                back = _BUTTON_OPPOSITE[last_step]
                if any(way_ not in spent and way_ != back for way_ in _BUTTON_OPPOSITE):
                    spent.add(back)
            uses = curiosity(things) if event_key is None else {}
            approach: dict[str, Any] = {}
            if way is not None and not uses:
                approach = {"ways": [way[0]], "pull": _pull(way[1]), "to": list(way[2]), "toward": way[3]}
            approach_ways = approach.get("ways", [])
            spent.difference_update(uses)
            spent.difference_update(approach_ways)

            def offer_cost(action: str) -> float:
                return 0.5 if action in uses or action in approach_ways else 1.0

            offers = [_offer(action, cost=offer_cost(action), feasible=action not in spent)
                      for action in _ACTIONS]
            memory_before = owner.state.state_sha256
            try:
                inquiry = inquire_field(DISCOVERIES, offers)
            except FieldIntelligenceError as exc:
                if not _is_state_saturation(exc):
                    raise
                rotate("temporal-state-budget")
                inquiry = inquire_field(DISCOVERIES, offers)
            action = inquiry.get("action")
            if owner.state.state_sha256 != memory_before:
                raise RuntimeError("temporal inquiry unexpectedly mutated persistent field state")
            fallback: Mapping[str, Any] | None = None
            if action not in _ACTIONS or action in spent:
                action, fallback = exploration_action(inquiry, spent, uses, approach_ways)
                fallback_actions += 1
            spent_skipped += len(spent)
            recent_actions.append(action)
            del recent_actions[:-8]

            key = _KEYS[action]

            def send(input_state: str) -> None:
                nonlocal operation_index, lease_remaining, lease, latest_publication, current_frame
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

            before = screen
            origin = body if action in WALK_BUTTONS else None
            heading_before = heading
            warped = False
            frames = 0
            send("down")
            if action in WALK_BUTTONS and event_key is None:
                # One tile per press: hold until the picture starts to move,
                # then release; the game finishes the step while the screen settles.
                while frames < 24:
                    backend.advance(1)
                    frames += 1
                    now = look()
                    if blank(now):
                        warped = True
                        break
                    if int(changed_tiles(before, now).sum()) > _SCENE_TILES:
                        break
            else:
                backend.advance(args.frames_per_action)
                frames += args.frames_per_action
            send("up")
            backend.advance(1)
            after, warped, settle_frames, flicker = settle(warped)
            screen = after
            latest_publication, current_frame = _admitted_capture(broker, binding_id, backend)
            perception = perceive(action, before, after, warped, flicker)
            feel_walk(origin, heading_before, action, perception)
            record(action, perception, {
                "field": {"status": inquiry.get("status"), "reason": inquiry.get("reason"),
                          "fallback": bool(fallback)},
                "curious": {"uses": uses, "approach": approach} if uses or approach else None,
                "frames": frames + 1 + settle_frames,
                "since_discovery": since_discovery,
            })

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
            "unproductive_actions": unproductive_actions,
            "spent_presses_withheld": spent_skipped,
            "lease_handovers": lease_handovers,
            "unlearned_steps": len(spill),
            "world": places.summary(),
            "sights": places.progress,
            "field_capacity": {"state_bytes": owner.state.closure_bytes, "state_limit": state_budget_bytes,
                               "history_entries": history_entries},
            "screen": {"place": place, "area": zone, "event_open": event_key is not None},
            "last_observation": current_observation,
            "recovered_steps": recovered_steps,
            "resume": "rerun the same command to continue this field-owned exploration",
        }, ensure_ascii=False))
        try:
            if broker is not None:
                broker.close()
        finally:
            try:
                places.save()
                world_field.save()
                if backend is not None and not registered:
                    backend.close()
            finally:
                session.close()
    return interrupted


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Let Cassi play a Game Boy ROM from its pixels: the field chooses buttons toward"
        " new places, scenes, sights, and what things do, and resumes exploration from remembered places."
    )
    parser.add_argument("--rom", type=Path, help="ROM path (default: CassiQwen/pokemon_yellow.gb)")
    parser.add_argument("--field-home", type=Path, default=Path.home() / ".cassi" / "pyboy-field",
                        help="persistent Cassi and Game Boy save directory")
    parser.add_argument("--steps", type=_step_count, default=None,
                        help=f"stop after this many field-selected actions (1..{_MAX_TOTAL_STEPS}); omit to keep playing")
    parser.add_argument("--frames-per-action", type=_frames_per_action, default=8,
                        help="frames to hold each selected button (1..120)")
    parser.add_argument("--goal", default="explore-places-and-story",
                        help="descriptive field context; the field seeks new places, sights, and uses of things")
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
    parser.add_argument("--checkpoint-interval", type=int, default=16,
                        help="field advances folded into one durable checkpoint; a crash loses at most this many")
    parser.add_argument("--fresh-boot", action="store_true",
                        help="ignore a saved emulator state and boot the cartridge from the start")
    parser.add_argument("--speed", type=int, default=-1,
                        help="emulation pace: 0 unthrottled, N times real time; -1 = 1 in a window, 0 headless")
    parser.add_argument("--return-after", type=int, default=48,
                        help="field steps without a discovery before resuming from a remembered place")
    parser.add_argument("--demo", action="store_true",
                        help="you play in the SDL2 window and the field learns from your presses")
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
