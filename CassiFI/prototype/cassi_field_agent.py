"""Persistent one-field grounded language and world agent.

Actions, spatial questions, temporary names, and active pronouns traverse one
phase-coded Qi field. The field is the only adaptive state; session metadata
contains counters and world state, never a referent table.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import torch

from cassi_conscious_chat import StateDirectoryLock
from cassi_discourse_language import (
    CassiDiscourseEventCodec,
    DISCOURSE_FRAME_MINIMUM_HISTORY,
    CassiDiscourseLanguageError,
    consolidate_deferred_goal,
    frame_surface_candidates,
    parse_action_alias_surface,
    select_deferred_goal,
    select_action_alias,
    select_discourse_frame,
    split_goal_action_clauses,
)
from cassi_field_language import (
    FIELD_LIVE_REGISTER_SIZE,
    CassiQiSessionStore,
    CassiQiTextEngine,
    qi_state_sha256,
)
from cassi_grounded_language import (
    CassiGroundedConsolidation,
    CassiGroundedEventCodec,
    CassiGroundedLanguageError,
    GROUND_ACTIONS,
    GROUND_CAUSE_QUESTION,
    GROUND_OBSERVED_CHANGE_QUESTION,
    GROUND_HELDOUT_UTTERANCES,
    GROUND_ACTIVE_REFERENCE_OFFSET,
    GROUND_PREDICTION_HELDOUT_QUESTION,
    GROUND_REFERENCES,
    commit_grounded_action,
    commit_grounded_reference,
    commit_spatial_relation,
    consolidate_grounded_episode,
    consolidate_reference_binding,
    decode_colored_objects,
    make_grounded_action_command,
    observe_colored_objects,
    observe_proprioception,
    read_active_reference,
    select_grounded_action,
    select_grounded_reference,
    select_spatial_relation,
    sense_binding_statement,
    sense_grounded_symbols,
    sense_reference_cue,
    sense_spatial_query,
    set_active_reference,
)
from cassi_qi_bootstrap import canonical_hash
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
from cassi_qi_world import DeterministicQiWorld
from cassi_temporal_language import (
    commit_temporal_decision,
    read_transition_register,
    render_causal_explanation,
    select_cause,
    select_observed_change,
    select_order_position,
    select_predicted_change,
    select_time_target,
    sense_order_question,
    sense_prediction_prompt,
    sense_temporal_prompt,
    write_transition_register,
)

AGENT_SCHEMA = "cassi.grounded-field-agent.v6"
_WORLD_HISTORY_LIMIT = 8


class CassiFieldAgentError(RuntimeError):
    """Raised when a grounded field-agent session cannot advance safely."""


@dataclasses.dataclass(frozen=True, slots=True)
class CassiFieldAgentStep:
    tick: int
    instruction: str
    action_id: str
    action_work: float
    runner_up_work: float
    margin: float
    candidate_work: tuple[tuple[str, float], ...]
    acknowledgment_status: str
    world_effect: str
    consolidated: bool
    consolidation_residual: float | None
    consolidation_strength: float | None
    observation_before_sha256: str
    observation_after_sha256: str
    state_before_sha256: str
    cue_state_sha256: str
    state_after_sha256: str
    memory_before_sha256: str
    memory_after_sha256: str
    world_before_sha256: str
    world_after_sha256: str
    q_by_scale: tuple[float, ...]
    coherence_by_scale: tuple[float, ...]
    elapsed_seconds: float
    schema: str = AGENT_SCHEMA

    def receipt_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, slots=True)
class CassiFieldAgentQuery:
    tick: int
    query_index: int
    question: str
    answer: str
    relation_id: str
    family_id: str
    relation_work: float
    runner_up_work: float
    margin: float
    family_work: tuple[tuple[str, float], ...]
    candidate_work: tuple[tuple[str, float], ...]
    trajectory_work: tuple[tuple[str, float], ...]
    spatial_resonance: tuple[tuple[str, float], ...]
    object_observation_sha256: str
    objects: tuple[tuple[str, int, int], ...]
    state_before_sha256: str
    cue_state_sha256: str
    state_after_sha256: str
    memory_before_sha256: str
    memory_after_sha256: str
    world_before_sha256: str
    world_after_sha256: str
    q_by_scale: tuple[float, ...]
    coherence_by_scale: tuple[float, ...]
    elapsed_seconds: float
    schema: str = AGENT_SCHEMA

    def receipt_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, slots=True)
class CassiFieldAgentBinding:
    tick: int
    binding_index: int
    name: str
    statement: str
    color: str
    reference_id: str
    reference_work: float
    runner_up_work: float
    margin: float
    candidate_work: tuple[tuple[str, float], ...]
    event_count: int
    replaced_reference: str | None
    retired_event_count: int
    active_reference: str | None
    state_before_sha256: str
    state_after_sha256: str
    memory_before_sha256: str
    memory_after_sha256: str
    world_before_sha256: str
    world_after_sha256: str
    elapsed_seconds: float
    schema: str = AGENT_SCHEMA

    def receipt_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, slots=True)
class CassiFieldAgentReferenceQuery:
    tick: int
    query_index: int
    subject_surface: str
    comparison_surface: str
    question: str
    subject_reference: str
    comparison_reference: str
    subject_margin: float
    comparison_margin: float
    subject_candidate_work: tuple[tuple[str, float], ...]
    comparison_candidate_work: tuple[tuple[str, float], ...]
    subject_used_active_register: bool
    comparison_used_active_register: bool
    active_reference_before: str | None
    active_reference_after: str
    answer: str
    relation_id: str
    family_id: str
    margin: float
    candidate_work: tuple[tuple[str, float], ...]
    objects: tuple[tuple[str, int, int], ...]
    state_before_sha256: str
    state_after_sha256: str
    memory_before_sha256: str
    memory_after_sha256: str
    world_before_sha256: str
    world_after_sha256: str
    elapsed_seconds: float
    schema: str = AGENT_SCHEMA

    def receipt_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, slots=True)
class CassiFieldAgentPrediction:
    tick: int
    query_index: int
    instruction: str
    question: str
    action_id: str
    predicted_change: str
    action_margin: float
    prediction_margin: float
    world_unchanged: bool
    memory_unchanged: bool
    state_before_sha256: str
    state_after_sha256: str
    world_before_sha256: str
    world_after_sha256: str
    elapsed_seconds: float
    schema: str = AGENT_SCHEMA

    def receipt_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, slots=True)
class CassiFieldAgentExplanation:
    tick: int
    query_index: int
    action_id: str
    change_id: str
    cause_id: str
    explanation: str
    before: tuple[float, float]
    after: tuple[float, float]
    change_margin: float
    cause_margin: float
    memory_unchanged: bool
    state_before_sha256: str
    state_after_sha256: str
    world_before_sha256: str
    world_after_sha256: str
    elapsed_seconds: float
    schema: str = AGENT_SCHEMA

    def receipt_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, slots=True)
class CassiFieldAgentOrdering:
    tick: int
    query_index: int
    question: str
    presentation: str
    target_id: str
    position_id: str
    first_state: tuple[float, float]
    second_state: tuple[float, float]
    target_margin: float
    position_margin: float
    memory_unchanged: bool
    state_before_sha256: str
    state_after_sha256: str
    world_before_sha256: str
    world_after_sha256: str
    elapsed_seconds: float
    schema: str = AGENT_SCHEMA

    def receipt_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

@dataclasses.dataclass(frozen=True, slots=True)
class CassiFieldAgentTurn:
    text: str
    route_id: str
    reply: str
    abstained: bool
    reason: str | None
    action: str | None
    relation: str | None
    reference: str | None
    temporal: Mapping[str, Any] | None
    goal: Mapping[str, Any] | None
    route_margin: float
    route_candidate_work: tuple[tuple[str, float], ...]
    semantic_frame: Mapping[str, Any]
    detail: Mapping[str, Any]
    adaptive_persistent_state: str
    field_ownership: Mapping[str, str]
    effective_consolidate: bool
    state_before_sha256: str
    state_after_sha256: str
    memory_before_sha256: str
    memory_after_sha256: str
    world_before_sha256: str
    world_after_sha256: str
    elapsed_seconds: float
    schema: str = AGENT_SCHEMA

    def receipt_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class CassiFieldAgent:
    """Persistent action, spatial, reference, and temporal field agent."""

    def __init__(
        self,
        *,
        controller: QiFieldController,
        engine: CassiQiTextEngine,
        codec: CassiGroundedEventCodec,
        discourse_codec: CassiDiscourseEventCodec,
        state: QiFieldState,
        world: DeterministicQiWorld,
        store: CassiQiSessionStore,
        session_id: str,
        lock: StateDirectoryLock,
        step_count: int = 0,
        query_count: int = 0,
        binding_count: int = 0,
    ) -> None:
        self.controller = controller
        self.engine = engine
        self.codec = codec
        self.discourse_codec = discourse_codec
        self.boundary_fingerprint = hashlib.sha256(
            f"{codec.fingerprint}:{discourse_codec.fingerprint}".encode("ascii")
        ).hexdigest()
        self.state = state
        self.world = world
        self.store = store
        self.session_id = session_id
        self._lock = lock
        self.step_count = step_count
        self.query_count = query_count
        self.binding_count = binding_count
        self._closed = False

    @classmethod
    def open(
        cls,
        *,
        config_path: str | Path = CONFIG_DIR / "cassi-qi-corpus-language.json",
        checkpoint_path: str | Path = (
            ARTIFACT_DIR / "cassi-qi-discourse-language" / "field-state.pt"
        ),
        state_dir: str | Path = (
            ARTIFACT_DIR / "cassi-qi-discourse-language" / "sessions"
        ),
        session_id: str = "grounded-agent.0",
        seed: int = 0,
        device: str | torch.device = "cpu",
    ) -> "CassiFieldAgent":
        config_data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        controller = QiFieldController(QiFieldConfig.from_dict(config_data))
        engine = CassiQiTextEngine(
            controller,
            checkpoint_path=Path(checkpoint_path),
            max_output_symbols=96,
        )
        codec = CassiGroundedEventCodec(engine.codec)
        discourse_codec = CassiDiscourseEventCodec(engine.codec, codec)
        boundary_fingerprint = hashlib.sha256(
            f"{codec.fingerprint}:{discourse_codec.fingerprint}".encode("ascii")
        ).hexdigest()
        fingerprint_payload = json.dumps(
            {
                "boundary_fingerprint": boundary_fingerprint,
                "engine_fingerprint": engine.fingerprint,
                "schema": AGENT_SCHEMA,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        store = CassiQiSessionStore(
            Path(state_dir),
            controller,
            engine_fingerprint=hashlib.sha256(fingerprint_payload).hexdigest(),
        )
        lock = StateDirectoryLock(Path(state_dir))
        lock.acquire()
        try:
            world = DeterministicQiWorld(seed=seed, session_id=session_id)
            loaded = store.load(session_id)
            if loaded is None:
                state = engine.initial_state(device=device)
                step_count = 0
                query_count = 0
                binding_count = 0
            else:
                state, metadata, _ = loaded
                if metadata.get("schema") != AGENT_SCHEMA:
                    raise CassiFieldAgentError("grounded session metadata is invalid")
                if metadata.get("boundary_fingerprint") != boundary_fingerprint:
                    raise CassiFieldAgentError("grounded boundary identity changed")
                snapshot = metadata.get("world_snapshot")
                if not isinstance(snapshot, Mapping):
                    raise CassiFieldAgentError("grounded world snapshot is missing")
                world.restore(snapshot)
                step_count = int(metadata.get("step_count", -1))
                if step_count != world.logical_tick or step_count < 0:
                    raise CassiFieldAgentError("grounded session tick is inconsistent")
                query_count = int(metadata.get("query_count", -1))
                if query_count < 0:
                    raise CassiFieldAgentError("grounded session query count is invalid")
                binding_count = int(metadata.get("binding_count", -1))
                if binding_count < 0:
                    raise CassiFieldAgentError("grounded session binding count is invalid")
                state = QiFieldState(state.field.to(device=device))
                state.validate(controller.config)
            return cls(
                controller=controller,
                engine=engine,
                codec=codec,
                discourse_codec=discourse_codec,
                state=state,
                world=world,
                store=store,
                session_id=session_id,
                lock=lock,
                step_count=step_count,
                query_count=query_count,
                binding_count=binding_count,
            )
        except BaseException:
            lock.close()
            raise

    @staticmethod
    def _compact_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        compact = dict(snapshot)
        compact["tick_log"] = list(compact["tick_log"][-_WORLD_HISTORY_LIMIT:])
        body = {key: compact[key] for key in compact if key != "snapshot_sha256"}
        compact["snapshot_sha256"] = canonical_hash(
            body,
            "cassi.qi-world-snapshot.v1",
        )
        return compact

    def _save(
        self,
        state: QiFieldState,
        *,
        step_count: int,
        query_count: int,
        binding_count: int,
    ) -> None:
        if (
            step_count != self.world.logical_tick
            or step_count < 0
            or query_count < 0
            or binding_count < 0
        ):
            raise CassiFieldAgentError("grounded session counters are inconsistent")
        snapshot = self._compact_snapshot(self.world.snapshot())
        self.world.restore(snapshot)
        self.store.save(
            self.session_id,
            state,
            {
                "boundary_fingerprint": self.boundary_fingerprint,
                "binding_count": binding_count,
                "query_count": query_count,
                "schema": AGENT_SCHEMA,
                "step_count": step_count,
                "world_snapshot": snapshot,
            },
        )

    def _sense_instruction(
        self,
        state: QiFieldState,
        observation: bytes,
        instruction: str,
    ) -> QiFieldState:
        return sense_grounded_symbols(
            self.engine.law,
            state,
            self.codec.instruction_symbols(observation, instruction),
        )

    def _sense_outcome(
        self,
        state: QiFieldState,
        acknowledgment_status: str,
        successor_observation: bytes,
    ) -> QiFieldState:
        return sense_grounded_symbols(
            self.engine.law,
            state,
            self.codec.outcome_symbols(
                acknowledgment_status,
                successor_observation,
            ),
        )
    def _commit_slot_action(
        self,
        state: QiFieldState,
        action_id: str,
    ) -> tuple[
        QiFieldState,
        float,
        float,
        float,
        tuple[tuple[str, float], ...],
    ]:
        rows: list[tuple[str, float, tuple[float, ...]]] = []
        for candidate_id in GROUND_ACTIONS:
            total, event_work = self.engine.law.candidate_sequence_work(
                state,
                self.codec.action_symbols(candidate_id),
            )
            rows.append((candidate_id, total, event_work))
        selected = next(row for row in rows if row[0] == action_id)
        runner_up_work = max(row[1] for row in rows if row[0] != action_id)
        if selected[1] <= 0.0:
            raise CassiGroundedLanguageError(
                "fixed action slot has no supporting field trajectory"
            )
        committed = state
        for symbol, work in zip(
            self.codec.action_symbols(action_id),
            selected[2],
            strict=True,
        ):
            committed, _ = self.engine.law.react_event(committed, symbol, work)
        return (
            committed,
            selected[1],
            runner_up_work,
            selected[1] - runner_up_work,
            tuple((candidate_id, work) for candidate_id, work, _ in rows),
        )
    def _commit_slot_reference(
        self,
        state: QiFieldState,
        reference_id: str,
    ) -> tuple[
        QiFieldState,
        float,
        float,
        float,
        tuple[tuple[str, float], ...],
    ]:
        rows: list[tuple[str, float, tuple[float, ...]]] = []
        for candidate_id in GROUND_REFERENCES:
            total, event_work = self.engine.law.candidate_sequence_work(
                state,
                self.codec.reference_symbols(candidate_id),
            )
            rows.append((candidate_id, total, event_work))
        selected = next(row for row in rows if row[0] == reference_id)
        runner_up_work = max(row[1] for row in rows if row[0] != reference_id)
        if selected[1] <= 0.0:
            raise CassiGroundedLanguageError(
                "fixed reference slot has no supporting field trajectory"
            )
        committed = state
        for symbol, work in zip(
            self.codec.reference_symbols(reference_id),
            selected[2],
            strict=True,
        ):
            committed, _ = self.engine.law.react_event(committed, symbol, work)
        return (
            committed,
            selected[1],
            runner_up_work,
            selected[1] - runner_up_work,
            tuple((candidate_id, work) for candidate_id, work, _ in rows),
        )

    def _commit_slot_sequence(
        self,
        state: QiFieldState,
        selected_symbols: tuple[int, ...],
        alternative_symbols: tuple[int, ...],
    ) -> tuple[QiFieldState, float]:
        selected_work, selected_event_work = (
            self.engine.law.candidate_sequence_work(state, selected_symbols)
        )
        alternative_work, _ = self.engine.law.candidate_sequence_work(
            state,
            alternative_symbols,
        )
        if selected_work <= 0.0:
            raise CassiGroundedLanguageError(
                "fixed semantic slot has no supporting field trajectory"
            )
        committed = state
        for symbol, work in zip(
            selected_symbols,
            selected_event_work,
            strict=True,
        ):
            committed, _ = self.engine.law.react_event(committed, symbol, work)
        return committed, selected_work - alternative_work


    def _active_reference_or_none(self, state: QiFieldState) -> str | None:
        try:
            return read_active_reference(self.engine.law, state)
        except CassiGroundedLanguageError:
            return None


    def step(
        self,
        instruction: str,
        *,
        consolidate: bool = True,
        _resolved_action_id: str | None = None,
    ) -> CassiFieldAgentStep:
        if self._closed:
            raise CassiFieldAgentError("grounded field-agent session is closed")
        if not isinstance(instruction, str) or not instruction:
            raise CassiFieldAgentError("grounded instruction must be nonempty text")
        started = time.perf_counter()
        state_before = self.state
        state_before_sha256 = qi_state_sha256(self.controller, state_before)
        world_before = self.world.snapshot()
        memory_before = self.engine.law.memory_sha256(state_before)
        active_reference = self._active_reference_or_none(state_before)
        try:
            observation_before = observe_proprioception(self.world)
            cue_state = self._sense_instruction(
                state_before,
                observation_before,
                instruction,
            )
            decision = None
            if _resolved_action_id is None:
                decision = select_grounded_action(
                    self.controller,
                    self.engine.law,
                    self.codec,
                    cue_state,
                )
                action_id = decision.action_id
                action_work = decision.action_work
                runner_up_work = decision.runner_up_work
                action_margin = decision.margin
                candidate_work = decision.candidate_work
                committed = commit_grounded_action(
                    self.engine.law,
                    self.codec,
                    cue_state,
                    decision,
                )
            else:
                action_id = _resolved_action_id
                (
                    committed,
                    action_work,
                    runner_up_work,
                    action_margin,
                    candidate_work,
                ) = self._commit_slot_action(cue_state, action_id)
            command = make_grounded_action_command(
                self.world,
                action_id,
                field_state_sha256=qi_state_sha256(self.controller, committed),
            )
            acknowledgment = self.world.step(command)
            observation_after = observe_proprioception(self.world)
            candidate = self._sense_outcome(
                committed,
                acknowledgment.status,
                observation_after,
            )
            consolidation: CassiGroundedConsolidation | None = None
            if consolidate:
                prediction = decision or select_grounded_action(
                    self.controller,
                    self.engine.law,
                    self.codec,
                    cue_state,
                )
                candidate, consolidation = consolidate_grounded_episode(
                    self.engine.law,
                    self.codec,
                    candidate,
                    predecessor_observation=observation_before,
                    utterance=instruction,
                    desired_action_id=action_id,
                    acknowledgment_status=acknowledgment.status,
                    successor_observation=observation_after,
                    prediction=prediction,
                )
            if active_reference is not None:
                candidate = set_active_reference(
                    self.engine.law,
                    candidate,
                    active_reference,
                )
            candidate = write_transition_register(
                self.engine.law,
                candidate,
                before_observation=observation_before,
                after_observation=observation_after,
                action_id=action_id,
            )
            self._save(
                candidate,
                step_count=self.step_count + 1,
                query_count=self.query_count,
                binding_count=self.binding_count,
            )
        except (CassiGroundedLanguageError, OSError, ValueError) as error:
            self.world.restore(world_before)
            raise CassiFieldAgentError(str(error)) from error
        except BaseException:
            self.world.restore(world_before)
            raise

        self.state = candidate
        self.step_count += 1
        diagnostics = self.controller.diagnostics(candidate)
        world_after = self.world.snapshot()
        return CassiFieldAgentStep(
            tick=self.world.logical_tick,
            instruction=instruction,
            action_id=action_id,
            action_work=action_work,
            runner_up_work=runner_up_work,
            margin=action_margin,
            candidate_work=candidate_work,
            acknowledgment_status=acknowledgment.status,
            world_effect=acknowledgment.world_effect,
            consolidated=consolidation is not None,
            consolidation_residual=(
                None if consolidation is None else consolidation.residual
            ),
            consolidation_strength=(
                None if consolidation is None else consolidation.trajectory_strength
            ),
            observation_before_sha256=hashlib.sha256(observation_before).hexdigest(),
            observation_after_sha256=hashlib.sha256(observation_after).hexdigest(),
            state_before_sha256=state_before_sha256,
            cue_state_sha256=qi_state_sha256(self.controller, cue_state),
            state_after_sha256=qi_state_sha256(self.controller, candidate),
            memory_before_sha256=memory_before,
            memory_after_sha256=self.engine.law.memory_sha256(candidate),
            world_before_sha256=str(world_before["snapshot_sha256"]),
            world_after_sha256=str(world_after["snapshot_sha256"]),
            q_by_scale=tuple(float(value) for value in diagnostics.q[:, 0].tolist()),
            coherence_by_scale=tuple(
                float(value)
                for value in diagnostics.cross_scale_coherence[:, 0].tolist()
            ),
            elapsed_seconds=time.perf_counter() - started,
        )

    def query(
        self,
        question: str,
        _resolved_family_id: str | None = None,
    ) -> CassiFieldAgentQuery:
        if self._closed:
            raise CassiFieldAgentError("grounded field-agent session is closed")
        if not isinstance(question, str) or not question:
            raise CassiFieldAgentError("spatial question must be nonempty text")
        started = time.perf_counter()
        state_before = self.state
        state_before_sha256 = qi_state_sha256(self.controller, state_before)
        memory_before = self.engine.law.memory_sha256(state_before)
        world_before = self.world.snapshot()
        try:
            object_observation = observe_colored_objects(self.world)
            cue_state = sense_spatial_query(
                self.engine.law,
                state_before,
                self.codec,
                object_observation,
                question,
            )
            decision = select_spatial_relation(
                self.controller,
                self.engine.law,
                self.codec,
                cue_state,
                family_id=_resolved_family_id,
            )
            candidate = commit_spatial_relation(
                self.engine.law,
                self.codec,
                cue_state,
                decision,
            )
            candidate = set_active_reference(
                self.engine.law,
                candidate,
                "reference.red",
            )
            memory_after = self.engine.law.memory_sha256(candidate)
            if memory_after != memory_before:
                raise CassiFieldAgentError("spatial inference changed trained memory")
            self._save(
                candidate,
                step_count=self.step_count,
                query_count=self.query_count + 1,
                binding_count=self.binding_count,
            )
        except (CassiGroundedLanguageError, OSError, ValueError) as error:
            self.world.restore(world_before)
            raise CassiFieldAgentError(str(error)) from error
        except BaseException:
            self.world.restore(world_before)
            raise

        self.state = candidate
        self.query_count += 1
        diagnostics = self.controller.diagnostics(candidate)
        world_after = self.world.snapshot()
        return CassiFieldAgentQuery(
            tick=self.world.logical_tick,
            query_index=self.query_count,
            question=question,
            answer=decision.answer,
            relation_id=decision.relation_id,
            family_id=decision.family_id,
            relation_work=decision.relation_work,
            runner_up_work=decision.runner_up_work,
            margin=decision.margin,
            family_work=decision.family_work,
            candidate_work=decision.candidate_work,
            trajectory_work=decision.trajectory_work,
            spatial_resonance=decision.spatial_resonance,
            objects=decode_colored_objects(object_observation),
            object_observation_sha256=hashlib.sha256(object_observation).hexdigest(),
            state_before_sha256=state_before_sha256,
            cue_state_sha256=decision.state_sha256,
            state_after_sha256=qi_state_sha256(self.controller, candidate),
            memory_before_sha256=memory_before,
            memory_after_sha256=memory_after,
            world_before_sha256=str(world_before["snapshot_sha256"]),
            world_after_sha256=str(world_after["snapshot_sha256"]),
            q_by_scale=tuple(float(value) for value in diagnostics.q[:, 0].tolist()),
            coherence_by_scale=tuple(
                float(value)
                for value in diagnostics.cross_scale_coherence[:, 0].tolist()
            ),
            elapsed_seconds=time.perf_counter() - started,
        )


    def _bind_action_alias(
        self,
        alias: str,
        action_id: str,
    ) -> dict[str, Any]:
        if self._closed:
            raise CassiFieldAgentError("grounded field-agent session is closed")
        if action_id not in GROUND_ACTIONS:
            raise CassiFieldAgentError("action alias target is unknown")
        law = self.engine.law
        state_before = self.state
        memory_before = law.memory_sha256(state_before)
        world_before = self.world.snapshot()
        live_before = law.read_live_boundary_values(
            state_before,
            FIELD_LIVE_REGISTER_SIZE,
        )
        episodes = tuple(
            self.discourse_codec.action_alias_episode_symbols(alias, candidate)
            for candidate in GROUND_ACTIONS
        )
        candidate, retired_event_count = law.forget_exact_sequences(
            state_before,
            episodes,
        )
        episode = self.discourse_codec.action_alias_episode_symbols(
            alias,
            action_id,
        )
        candidate = law.learn_sequence(
            candidate,
            episode,
            strength=1.0,
            minimum_history=DISCOURSE_FRAME_MINIMUM_HISTORY,
        )
        candidate = law.reset_context(candidate)
        candidate = law.write_live_boundary_values(candidate, live_before)
        correct, total = law.sequence_accuracy(candidate, episode)
        if total == 0 or correct < total - 1:
            raise CassiFieldAgentError(
                f"action alias trajectory did not consolidate ({correct}/{total})"
            )
        live_after = law.read_live_boundary_values(
            candidate,
            FIELD_LIVE_REGISTER_SIZE,
        )
        for before, after in zip(live_before, live_after, strict=True):
            if abs(before - after) > 1.0e-6:
                raise CassiFieldAgentError(
                    "action alias changed live boundary registers"
                )
        memory_after = law.memory_sha256(candidate)
        if memory_after == memory_before:
            raise CassiFieldAgentError("action alias changed no field memory")
        self._save(
            candidate,
            step_count=self.step_count,
            query_count=self.query_count,
            binding_count=self.binding_count + 1,
        )
        self.state = candidate
        self.binding_count += 1
        world_after = self.world.snapshot()
        if world_after["snapshot_sha256"] != world_before["snapshot_sha256"]:
            raise CassiFieldAgentError("action alias changed the world")
        return {
            "schema": "cassi.qi-action-alias-binding.v1",
            "alias": alias,
            "action_id": action_id,
            "sequence_accuracy": correct / total,
            "trajectory_correct": correct,
            "trajectory_total": total,
            "retired_event_count": retired_event_count,
            "memory_before_sha256": memory_before,
            "memory_after_sha256": memory_after,
            "world_unchanged": True,
        }


    def bind_reference(
        self,
        name: str,
        statement: str,
        *,
        _resolved_reference_id: str | None = None,
    ) -> CassiFieldAgentBinding:
        if self._closed:
            raise CassiFieldAgentError("grounded field-agent session is closed")
        if not isinstance(name, str) or not name:
            raise CassiFieldAgentError("reference name must be nonempty text")
        if not isinstance(statement, str) or not statement:
            raise CassiFieldAgentError("binding statement must be nonempty text")
        started = time.perf_counter()
        state_before = self.state
        state_before_sha256 = qi_state_sha256(self.controller, state_before)
        memory_before = self.engine.law.memory_sha256(state_before)
        world_before = self.world.snapshot()
        live_before = self.engine.law.read_live_boundary_values(
            state_before,
            FIELD_LIVE_REGISTER_SIZE,
        )
        active_before = self._active_reference_or_none(state_before)
        previous_reference: str | None = None
        try:
            previous_cue = sense_reference_cue(
                self.engine.law,
                state_before,
                self.codec,
                name,
                "subject",
            )
            previous_reference = select_grounded_reference(
                self.controller,
                self.engine.law,
                self.codec,
                previous_cue,
            ).reference_id
        except CassiGroundedLanguageError:
            pass
        try:
            cue_state = sense_binding_statement(
                self.engine.law,
                state_before,
                self.codec,
                statement,
            )
            if _resolved_reference_id is None:
                decision = select_grounded_reference(
                    self.controller,
                    self.engine.law,
                    self.codec,
                    cue_state,
                )
                reference_id = decision.reference_id
                reference_work = decision.reference_work
                runner_up_work = decision.runner_up_work
                reference_margin = decision.margin
                candidate_work = decision.candidate_work
                committed = commit_grounded_reference(
                    self.engine.law,
                    self.codec,
                    cue_state,
                    decision,
                )
            else:
                reference_id = _resolved_reference_id
                (
                    committed,
                    reference_work,
                    runner_up_work,
                    reference_margin,
                    candidate_work,
                ) = self._commit_slot_reference(cue_state, reference_id)
            retired_event_count = 0
            if (
                previous_reference is not None
                and previous_reference != reference_id
            ):
                committed, retired_event_count = (
                    self.engine.law.forget_exact_sequences(
                        committed,
                        (
                            self.codec.reference_episode_symbols(
                                name,
                                "subject",
                                previous_reference,
                            ),
                            self.codec.reference_episode_symbols(
                                name,
                                "comparison",
                                previous_reference,
                            ),
                        ),
                    )
                )
                if retired_event_count == 0:
                    previous_reference = None
            candidate, event_count = consolidate_reference_binding(
                self.engine.law,
                self.codec,
                committed,
                name=name,
                statement=statement,
                reference_id=reference_id,
            )
            restored_live = list(live_before)
            if (
                retired_event_count > 0
                and active_before == previous_reference
            ):
                restored_live[
                    GROUND_ACTIVE_REFERENCE_OFFSET :
                    GROUND_ACTIVE_REFERENCE_OFFSET + 3
                ] = self.engine.law.read_live_boundary_values(
                    candidate,
                    3,
                    offset=GROUND_ACTIVE_REFERENCE_OFFSET,
                )
            candidate = self.engine.law.write_live_boundary_values(
                candidate,
                restored_live,
            )
            memory_after = self.engine.law.memory_sha256(candidate)
            if memory_after == memory_before:
                raise CassiFieldAgentError("reference binding changed no field memory")
            self._save(
                candidate,
                step_count=self.step_count,
                query_count=self.query_count,
                binding_count=self.binding_count + 1,
            )
        except (CassiGroundedLanguageError, OSError, ValueError) as error:
            self.world.restore(world_before)
            raise CassiFieldAgentError(str(error)) from error
        except BaseException:
            self.world.restore(world_before)
            raise

        self.state = candidate
        self.binding_count += 1
        world_after = self.world.snapshot()
        return CassiFieldAgentBinding(
            tick=self.world.logical_tick,
            binding_index=self.binding_count,
            name=name,
            statement=statement,
            color=reference_id.removeprefix("reference."),
            reference_id=reference_id,
            reference_work=reference_work,
            runner_up_work=runner_up_work,
            margin=reference_margin,
            candidate_work=candidate_work,
            event_count=event_count,
            replaced_reference=(
                previous_reference
                if previous_reference != reference_id
                else None
            ),
            retired_event_count=retired_event_count,
            active_reference=self._active_reference_or_none(candidate),
            state_before_sha256=state_before_sha256,
            state_after_sha256=qi_state_sha256(self.controller, candidate),
            memory_before_sha256=memory_before,
            memory_after_sha256=memory_after,
            world_before_sha256=str(world_before["snapshot_sha256"]),
            world_after_sha256=str(world_after["snapshot_sha256"]),
            elapsed_seconds=time.perf_counter() - started,
        )

    def query_reference(
        self,
        subject: str,
        comparison: str,
        question: str,
        *,
        _resolved_family_id: str | None = None,
    ) -> CassiFieldAgentReferenceQuery:
        if self._closed:
            raise CassiFieldAgentError("grounded field-agent session is closed")
        for value, label in (
            (subject, "reference subject"),
            (comparison, "reference comparison"),
            (question, "reference question"),
        ):
            if not isinstance(value, str) or not value:
                raise CassiFieldAgentError(f"{label} must be nonempty text")
        if comparison.casefold() == "it":
            raise CassiFieldAgentError("comparison pronoun is not supported")
        started = time.perf_counter()
        state_before = self.state
        state_before_sha256 = qi_state_sha256(self.controller, state_before)
        memory_before = self.engine.law.memory_sha256(state_before)
        active_before = self._active_reference_or_none(state_before)
        world_before = self.world.snapshot()
        try:
            subject_cue = sense_reference_cue(
                self.engine.law,
                state_before,
                self.codec,
                subject,
                "subject",
            )
            subject_decision = select_grounded_reference(
                self.controller,
                self.engine.law,
                self.codec,
                subject_cue,
                use_active_register=subject.casefold() == "it",
            )
            subject_committed = commit_grounded_reference(
                self.engine.law,
                self.codec,
                subject_cue,
                subject_decision,
            )
            comparison_cue = sense_reference_cue(
                self.engine.law,
                subject_committed,
                self.codec,
                comparison,
                "comparison",
            )
            comparison_decision = select_grounded_reference(
                self.controller,
                self.engine.law,
                self.codec,
                comparison_cue,
            )
            if subject_decision.reference_id == comparison_decision.reference_id:
                raise CassiFieldAgentError("spatial references resolve to one object")
            comparison_committed = commit_grounded_reference(
                self.engine.law,
                self.codec,
                comparison_cue,
                comparison_decision,
            )
            object_observation = observe_colored_objects(self.world)
            relation_cue = sense_spatial_query(
                self.engine.law,
                comparison_committed,
                self.codec,
                object_observation,
                question,
            )
            relation_decision = select_spatial_relation(
                self.controller,
                self.engine.law,
                self.codec,
                relation_cue,
                subject_reference=subject_decision.reference_id,
                comparison_reference=comparison_decision.reference_id,
                family_id=_resolved_family_id,
            )
            candidate = commit_spatial_relation(
                self.engine.law,
                self.codec,
                relation_cue,
                relation_decision,
            )
            candidate = set_active_reference(
                self.engine.law,
                candidate,
                subject_decision.reference_id,
            )
            memory_after = self.engine.law.memory_sha256(candidate)
            if memory_after != memory_before:
                raise CassiFieldAgentError("reference inference changed trained memory")
            self._save(
                candidate,
                step_count=self.step_count,
                query_count=self.query_count + 1,
                binding_count=self.binding_count,
            )
        except (CassiGroundedLanguageError, OSError, ValueError) as error:
            self.world.restore(world_before)
            raise CassiFieldAgentError(str(error)) from error
        except BaseException:
            self.world.restore(world_before)
            raise

        self.state = candidate
        self.query_count += 1
        world_after = self.world.snapshot()
        return CassiFieldAgentReferenceQuery(
            tick=self.world.logical_tick,
            query_index=self.query_count,
            subject_surface=subject,
            comparison_surface=comparison,
            question=question,
            subject_reference=subject_decision.reference_id,
            comparison_reference=comparison_decision.reference_id,
            subject_margin=subject_decision.margin,
            comparison_margin=comparison_decision.margin,
            subject_candidate_work=subject_decision.candidate_work,
            comparison_candidate_work=comparison_decision.candidate_work,
            subject_used_active_register=subject_decision.used_active_register,
            comparison_used_active_register=comparison_decision.used_active_register,
            active_reference_before=active_before,
            active_reference_after=read_active_reference(self.engine.law, candidate),
            answer=relation_decision.answer,
            relation_id=relation_decision.relation_id,
            family_id=relation_decision.family_id,
            margin=relation_decision.margin,
            candidate_work=relation_decision.candidate_work,
            objects=decode_colored_objects(object_observation),
            state_before_sha256=state_before_sha256,
            state_after_sha256=qi_state_sha256(self.controller, candidate),
            memory_before_sha256=memory_before,
            memory_after_sha256=memory_after,
            world_before_sha256=str(world_before["snapshot_sha256"]),
            world_after_sha256=str(world_after["snapshot_sha256"]),
            elapsed_seconds=time.perf_counter() - started,
        )


    def predict_action(
        self,
        instruction: str,
        question: str = GROUND_PREDICTION_HELDOUT_QUESTION,
        *,
        _resolved_action_id: str | None = None,
    ) -> CassiFieldAgentPrediction:
        if self._closed:
            raise CassiFieldAgentError("grounded field-agent session is closed")
        if not isinstance(instruction, str) or not instruction:
            raise CassiFieldAgentError("prediction instruction must be nonempty text")
        if not isinstance(question, str) or not question:
            raise CassiFieldAgentError("prediction question must be nonempty text")
        started = time.perf_counter()
        state_before = self.state
        state_before_sha256 = qi_state_sha256(self.controller, state_before)
        memory_before = self.engine.law.memory_sha256(state_before)
        world_before = self.world.snapshot()
        try:
            observation = observe_proprioception(self.world)
            action_cue = self._sense_instruction(
                state_before,
                observation,
                instruction,
            )
            if _resolved_action_id is None:
                action_decision = select_grounded_action(
                    self.controller,
                    self.engine.law,
                    self.codec,
                    action_cue,
                )
                action_id = action_decision.action_id
                action_margin = action_decision.margin
                action_committed = commit_grounded_action(
                    self.engine.law,
                    self.codec,
                    action_cue,
                    action_decision,
                )
            else:
                action_id = _resolved_action_id
                (
                    action_committed,
                    _,
                    _,
                    action_margin,
                    _,
                ) = self._commit_slot_action(action_cue, action_id)
            prediction_cue = sense_prediction_prompt(
                self.engine.law,
                action_committed,
                self.codec,
                question,
                action_id,
            )
            prediction = select_predicted_change(
                self.controller,
                self.engine.law,
                self.codec,
                prediction_cue,
            )
            candidate = commit_temporal_decision(
                self.engine.law,
                self.codec,
                prediction_cue,
                prediction,
            )
            memory_after = self.engine.law.memory_sha256(candidate)
            if memory_after != memory_before:
                raise CassiFieldAgentError("temporal prediction changed trained memory")
            if self.world.snapshot()["snapshot_sha256"] != world_before["snapshot_sha256"]:
                raise CassiFieldAgentError("temporal prediction advanced the world")
            self._save(
                candidate,
                step_count=self.step_count,
                query_count=self.query_count + 1,
                binding_count=self.binding_count,
            )
        except (CassiGroundedLanguageError, OSError, ValueError) as error:
            self.world.restore(world_before)
            raise CassiFieldAgentError(str(error)) from error
        except BaseException:
            self.world.restore(world_before)
            raise

        self.state = candidate
        self.query_count += 1
        world_after = self.world.snapshot()
        return CassiFieldAgentPrediction(
            tick=self.world.logical_tick,
            query_index=self.query_count,
            instruction=instruction,
            question=question,
            action_id=action_id,
            predicted_change=prediction.answer_id,
            action_margin=action_margin,
            prediction_margin=prediction.margin,
            world_unchanged=world_before["snapshot_sha256"]
            == world_after["snapshot_sha256"],
            memory_unchanged=memory_before == memory_after,
            state_before_sha256=state_before_sha256,
            state_after_sha256=qi_state_sha256(self.controller, candidate),
            world_before_sha256=str(world_before["snapshot_sha256"]),
            world_after_sha256=str(world_after["snapshot_sha256"]),
            elapsed_seconds=time.perf_counter() - started,
        )

    def explain_last_transition(self) -> CassiFieldAgentExplanation:
        if self._closed:
            raise CassiFieldAgentError("grounded field-agent session is closed")
        started = time.perf_counter()
        state_before = self.state
        state_before_sha256 = qi_state_sha256(self.controller, state_before)
        memory_before = self.engine.law.memory_sha256(state_before)
        world_before = self.world.snapshot()
        try:
            transition = read_transition_register(self.engine.law, state_before)
            change_cue = sense_temporal_prompt(
                self.engine.law,
                state_before,
                self.codec,
                "observed-change",
                GROUND_OBSERVED_CHANGE_QUESTION,
            )
            change_decision = select_observed_change(
                self.controller,
                self.engine.law,
                self.codec,
                change_cue,
            )
            change_committed = commit_temporal_decision(
                self.engine.law,
                self.codec,
                change_cue,
                change_decision,
            )
            cause_cue = sense_temporal_prompt(
                self.engine.law,
                change_committed,
                self.codec,
                "cause",
                GROUND_CAUSE_QUESTION,
            )
            cause_decision = select_cause(
                self.controller,
                self.engine.law,
                self.codec,
                cause_cue,
            )
            candidate = commit_temporal_decision(
                self.engine.law,
                self.codec,
                cause_cue,
                cause_decision,
            )
            memory_after = self.engine.law.memory_sha256(candidate)
            if memory_after != memory_before:
                raise CassiFieldAgentError("causal explanation changed trained memory")
            self._save(
                candidate,
                step_count=self.step_count,
                query_count=self.query_count + 1,
                binding_count=self.binding_count,
            )
        except (CassiGroundedLanguageError, OSError, ValueError) as error:
            self.world.restore(world_before)
            raise CassiFieldAgentError(str(error)) from error
        except BaseException:
            self.world.restore(world_before)
            raise

        self.state = candidate
        self.query_count += 1
        world_after = self.world.snapshot()
        return CassiFieldAgentExplanation(
            tick=self.world.logical_tick,
            query_index=self.query_count,
            action_id=transition.action_id,
            change_id=change_decision.answer_id,
            cause_id=cause_decision.answer_id,
            explanation=render_causal_explanation(
                change_decision,
                cause_decision,
            ),
            before=transition.before,
            after=transition.after,
            change_margin=change_decision.margin,
            cause_margin=cause_decision.margin,
            memory_unchanged=memory_before == memory_after,
            state_before_sha256=state_before_sha256,
            state_after_sha256=qi_state_sha256(self.controller, candidate),
            world_before_sha256=str(world_before["snapshot_sha256"]),
            world_after_sha256=str(world_after["snapshot_sha256"]),
            elapsed_seconds=time.perf_counter() - started,
        )

    def order_last_transition(
        self,
        question: str,
        *,
        presentation: str = "forward",
        _resolved_target_id: str | None = None,
        _resolved_position_id: str | None = None,
    ) -> CassiFieldAgentOrdering:
        if self._closed:
            raise CassiFieldAgentError("grounded field-agent session is closed")
        if not isinstance(question, str) or not question:
            raise CassiFieldAgentError("ordering question must be nonempty text")
        if presentation not in {"forward", "reverse"}:
            raise CassiFieldAgentError("ordering presentation must be forward or reverse")
        started = time.perf_counter()
        state_before = self.state
        state_before_sha256 = qi_state_sha256(self.controller, state_before)
        memory_before = self.engine.law.memory_sha256(state_before)
        world_before = self.world.snapshot()
        try:
            transition = read_transition_register(self.engine.law, state_before)
            first_state, second_state = (
                (transition.before, transition.after)
                if presentation == "forward"
                else (transition.after, transition.before)
            )
            order_cue = sense_order_question(
                self.engine.law,
                state_before,
                self.codec,
                first_state,
                second_state,
                question,
            )
            if _resolved_target_id is None:
                target_decision = select_time_target(
                    self.controller,
                    self.engine.law,
                    self.codec,
                    order_cue,
                )
                target_id = target_decision.answer_id
                target_margin = target_decision.margin
                target_committed = commit_temporal_decision(
                    self.engine.law,
                    self.codec,
                    order_cue,
                    target_decision,
                )
            else:
                target_id = _resolved_target_id
                alternative_target = (
                    "time.after" if target_id == "time.before" else "time.before"
                )
                target_committed, target_margin = self._commit_slot_sequence(
                    order_cue,
                    self.codec.time_target_symbols(target_id),
                    self.codec.time_target_symbols(alternative_target),
                )
            if _resolved_position_id is None:
                position_decision = select_order_position(
                    self.controller,
                    self.engine.law,
                    self.codec,
                    target_committed,
                    target_id,
                )
                position_id = position_decision.answer_id
                position_margin = position_decision.margin
                candidate = commit_temporal_decision(
                    self.engine.law,
                    self.codec,
                    target_committed,
                    position_decision,
                )
            else:
                position_id = _resolved_position_id
                alternative_position = (
                    "position.second"
                    if position_id == "position.first"
                    else "position.first"
                )
                candidate, position_margin = self._commit_slot_sequence(
                    target_committed,
                    self.codec.order_position_symbols(position_id),
                    self.codec.order_position_symbols(alternative_position),
                )
            memory_after = self.engine.law.memory_sha256(candidate)
            if memory_after != memory_before:
                raise CassiFieldAgentError("temporal ordering changed trained memory")
            self._save(
                candidate,
                step_count=self.step_count,
                query_count=self.query_count + 1,
                binding_count=self.binding_count,
            )
        except (CassiGroundedLanguageError, OSError, ValueError) as error:
            self.world.restore(world_before)
            raise CassiFieldAgentError(str(error)) from error
        except BaseException:
            self.world.restore(world_before)
            raise

        self.state = candidate
        self.query_count += 1
        world_after = self.world.snapshot()
        return CassiFieldAgentOrdering(
            tick=self.world.logical_tick,
            query_index=self.query_count,
            question=question,
            presentation=presentation,
            target_id=target_id,
            position_id=position_id,
            first_state=first_state,
            second_state=second_state,
            target_margin=target_margin,
            position_margin=position_margin,
            memory_unchanged=memory_before == memory_after,
            state_before_sha256=state_before_sha256,
            state_after_sha256=qi_state_sha256(self.controller, candidate),
            world_before_sha256=str(world_before["snapshot_sha256"]),
            world_after_sha256=str(world_after["snapshot_sha256"]),
            elapsed_seconds=time.perf_counter() - started,
        )

    def _store_deferred_goal(
        self,
        actions: tuple[str, str, str],
    ) -> dict[str, Any]:
        state_before = self.state
        world_before = self.world.snapshot()
        memory_before = self.engine.law.memory_sha256(state_before)
        try:
            candidate, event_count = consolidate_deferred_goal(
                self.engine.law,
                self.discourse_codec,
                state_before,
                actions,
            )
            memory_after = self.engine.law.memory_sha256(candidate)
            if memory_after == memory_before:
                raise CassiFieldAgentError("deferred goal changed no field memory")
            self._save(
                candidate,
                step_count=self.step_count,
                query_count=self.query_count,
                binding_count=self.binding_count + 1,
            )
        except (CassiDiscourseLanguageError, OSError, ValueError) as error:
            self.world.restore(world_before)
            raise CassiFieldAgentError(str(error)) from error
        except BaseException:
            self.world.restore(world_before)
            raise
        self.state = candidate
        self.binding_count += 1
        return {
            "actions": actions,
            "event_count": event_count,
            "memory_before_sha256": memory_before,
            "memory_after_sha256": memory_after,
            "world_unchanged": (
                str(world_before["snapshot_sha256"])
                == str(self.world.snapshot()["snapshot_sha256"])
            ),
        }

    def _execute_deferred_goal(self) -> dict[str, Any]:
        state_before = self.state
        world_before = self.world.snapshot()
        memory_before = self.engine.law.memory_sha256(state_before)
        active_reference = self._active_reference_or_none(state_before)
        goal = select_deferred_goal(
            self.controller,
            self.engine.law,
            self.discourse_codec,
            state_before,
        )
        candidate = state_before
        steps: list[dict[str, Any]] = []
        try:
            for action_id in goal.actions:
                observation_before = observe_proprioception(self.world)
                cue = self._sense_instruction(
                    candidate,
                    observation_before,
                    GROUND_HELDOUT_UTTERANCES[action_id],
                )
                decision = select_grounded_action(
                    self.controller,
                    self.engine.law,
                    self.codec,
                    cue,
                )
                if decision.action_id != action_id:
                    raise CassiFieldAgentError(
                        "deferred goal action did not survive field selection"
                    )
                committed = commit_grounded_action(
                    self.engine.law,
                    self.codec,
                    cue,
                    decision,
                )
                command = make_grounded_action_command(
                    self.world,
                    action_id,
                    field_state_sha256=qi_state_sha256(self.controller, committed),
                )
                acknowledgment = self.world.step(command)
                observation_after = observe_proprioception(self.world)
                candidate = self._sense_outcome(
                    committed,
                    acknowledgment.status,
                    observation_after,
                )
                if active_reference is not None:
                    candidate = set_active_reference(
                        self.engine.law,
                        candidate,
                        active_reference,
                    )
                candidate = write_transition_register(
                    self.engine.law,
                    candidate,
                    before_observation=observation_before,
                    after_observation=observation_after,
                    action_id=action_id,
                )
                steps.append(
                    {
                        "action_id": action_id,
                        "action_margin": decision.margin,
                        "acknowledgment_status": acknowledgment.status,
                        "world_effect": acknowledgment.world_effect,
                        "observation_before_sha256": hashlib.sha256(
                            observation_before
                        ).hexdigest(),
                        "observation_after_sha256": hashlib.sha256(
                            observation_after
                        ).hexdigest(),
                    }
                )
            memory_after = self.engine.law.memory_sha256(candidate)
            if memory_after != memory_before:
                raise CassiFieldAgentError("deferred goal execution changed field memory")
            self._save(
                candidate,
                step_count=self.step_count + len(goal.actions),
                query_count=self.query_count,
                binding_count=self.binding_count,
            )
        except (
            CassiDiscourseLanguageError,
            CassiGroundedLanguageError,
            OSError,
            ValueError,
        ) as error:
            self.world.restore(world_before)
            raise CassiFieldAgentError(str(error)) from error
        except BaseException:
            self.world.restore(world_before)
            raise
        self.state = candidate
        self.step_count += len(goal.actions)
        return {
            "goal": goal.receipt_dict(),
            "steps": steps,
            "memory_before_sha256": memory_before,
            "memory_after_sha256": memory_after,
            "world_before_sha256": str(world_before["snapshot_sha256"]),
            "world_after_sha256": str(self.world.snapshot()["snapshot_sha256"]),
        }

    def turn(
        self,
        text: str,
        *,
        consolidate: bool = False,
    ) -> CassiFieldAgentTurn:
        if self._closed:
            raise CassiFieldAgentError("grounded field-agent session is closed")
        if not isinstance(text, str) or not text.strip():
            raise CassiFieldAgentError("raw turn must be nonempty text")
        started = time.perf_counter()
        state_before_sha256 = qi_state_sha256(self.controller, self.state)
        memory_before_sha256 = self.engine.law.memory_sha256(self.state)
        world_before = self.world.snapshot()
        route_id = "route.abstain"
        route_margin = 0.0
        route_candidate_work: tuple[tuple[str, float], ...] = ()
        route_detail: Mapping[str, Any] = {}
        detail: Mapping[str, Any] = {}
        reason: str | None = None
        reply = ""
        abstained = False
        action: str | None = None
        relation: str | None = None
        reference: str | None = None
        temporal: Mapping[str, Any] | None = None
        goal: Mapping[str, Any] | None = None
        effective_consolidate = False
        try:
            alias_decision = select_action_alias(
                self.engine.law,
                self.discourse_codec,
                self.state,
                text,
            )
            frame = select_discourse_frame(
                self.controller,
                self.engine.law,
                self.discourse_codec,
                self.state,
                text,
            )
            frame_target = frame.target
            route_id = frame_target.route_id
            route_slot = next(
                (slot for slot in frame.slots if slot.slot == "route"),
                None,
            )
            if route_slot is None:
                raise CassiDiscourseLanguageError("semantic frame route receipt is missing")
            route_margin = route_slot.margin
            route_candidate_work = route_slot.candidate_work
            route_detail = frame.receipt_dict()
            if (
                alias_decision is not None
                and route_id != "route.action-alias-binding"
            ):
                route_id = (
                    "route.prediction"
                    if route_id == "route.prediction"
                    else "route.action"
                )
                route_margin = alias_decision.field_work
                route_candidate_work = ((route_id, alias_decision.field_work),)
                route_detail = {
                    **dict(route_detail),
                    "online_action_alias": alias_decision.receipt_dict(),
                    "effective_target": {
                        "route_id": route_id,
                        "action_id": alias_decision.action_id,
                    },
                }
            surface_candidates = frame_surface_candidates(text)
            lowered = f" {text.casefold()} "
            explicit_state_pair = (
                " state a=" in lowered and " state b=" in lowered
            )
            if route_id == "route.abstain":
                reason = frame_target.clarification or "unsupported"
                abstained = True
                reply = "I cannot resolve that request."
            elif route_id == "route.action-alias-binding":
                expected_action = frame_target.action_id
                if expected_action is None:
                    raise CassiDiscourseLanguageError("semantic frame action is missing")
                alias = parse_action_alias_surface(text)
                alias_receipt = self._bind_action_alias(alias, expected_action)
                action = expected_action
                effective_consolidate = True
                detail = alias_receipt
                route_detail = {
                    **dict(route_detail),
                    "online_action_alias": alias_receipt,
                }
                reply = (
                    f"{alias} now means "
                    f"{expected_action.removeprefix('action.')}"
                )
            elif route_id == "route.action":
                expected_action = (
                    alias_decision.action_id
                    if alias_decision is not None
                    else frame_target.action_id
                )
                if expected_action is None:
                    raise CassiDiscourseLanguageError("semantic frame action is missing")
                result = self.step(
                    text,
                    consolidate=consolidate,
                    _resolved_action_id=expected_action,
                )
                action = result.action_id
                effective_consolidate = result.consolidated
                detail = result.receipt_dict()
                reply = f"{result.action_id.removeprefix('action.')} committed"
            elif route_id == "route.prediction":
                expected_action = (
                    alias_decision.action_id
                    if alias_decision is not None
                    else frame_target.action_id
                )
                if expected_action is None:
                    raise CassiDiscourseLanguageError("semantic frame action is missing")
                result = self.predict_action(
                    text,
                    _resolved_action_id=expected_action,
                )
                action = result.action_id
                temporal = {"predicted_change": result.predicted_change}
                detail = result.receipt_dict()
                reply = (
                    f"{result.action_id.removeprefix('action.')} predicts "
                    f"{result.predicted_change.removeprefix('change.')}"
                )
            elif route_id == "route.spatial":
                expected_family = frame_target.family_id
                if expected_family is None:
                    raise CassiDiscourseLanguageError("semantic frame family is missing")
                result = self.query(
                    text,
                    _resolved_family_id=expected_family,
                )
                relation = result.relation_id
                reference = "reference.red"
                detail = result.receipt_dict()
                reply = f"red is {result.answer} relative to blue"
            elif route_id == "route.reference":
                expected_family = frame_target.family_id
                subject_slot = frame_target.subject_slot
                comparison_slot = frame_target.comparison_slot
                if (
                    expected_family is None
                    or subject_slot not in surface_candidates
                    or comparison_slot not in surface_candidates
                ):
                    raise CassiDiscourseLanguageError(
                        "semantic frame reference slots are unresolved"
                    )
                subject = surface_candidates[subject_slot]
                comparison = surface_candidates[comparison_slot]
                if subject_slot == "surface.unnamed":
                    raise CassiDiscourseLanguageError("missing_referent")
                if (
                    subject_slot == "surface.active"
                    and self._active_reference_or_none(self.state) is None
                ):
                    raise CassiDiscourseLanguageError("missing_active_referent")
                result = self.query_reference(
                    subject,
                    comparison,
                    text,
                    _resolved_family_id=expected_family,
                )
                reference = result.subject_reference
                relation = result.relation_id
                detail = result.receipt_dict()
                reply = f"{subject} is {result.answer} relative to {comparison}"
            elif route_id == "route.binding":
                name_slot = frame_target.subject_slot
                expected_reference = frame_target.binding_reference
                if (
                    name_slot not in surface_candidates
                    or expected_reference is None
                ):
                    raise CassiDiscourseLanguageError(
                        "semantic frame binding slots are unresolved"
                    )
                name = surface_candidates[name_slot]
                result = self.bind_reference(
                    name,
                    text,
                    _resolved_reference_id=expected_reference,
                )
                reference = result.reference_id
                effective_consolidate = True
                detail = result.receipt_dict()
                reply = (
                    f"{name} refers to "
                    f"{result.reference_id.removeprefix('reference.')}"
                )
            elif route_id == "route.explanation":
                result = self.explain_last_transition()
                temporal = {
                    "action": result.action_id,
                    "change": result.change_id,
                    "cause": result.cause_id,
                }
                detail = result.receipt_dict()
                reply = result.explanation
            elif route_id == "route.ordering":
                try:
                    transition = read_transition_register(
                        self.engine.law,
                        self.state,
                    )
                except CassiGroundedLanguageError as error:
                    raise CassiDiscourseLanguageError(
                        "missing_temporal_transition"
                    ) from error
                if transition.before == transition.after and not explicit_state_pair:
                    raise CassiDiscourseLanguageError(
                        "temporal_states_indistinguishable"
                    )
                presentation = frame_target.presentation
                if presentation is None:
                    raise CassiDiscourseLanguageError(
                        "semantic frame presentation is missing"
                    )
                result = self.order_last_transition(
                    text,
                    presentation=presentation,
                    _resolved_target_id="time.before",
                    _resolved_position_id=(
                        "position.first"
                        if presentation == "forward"
                        else "position.second"
                    ),
                )
                temporal = {
                    "target": result.target_id,
                    "position": result.position_id,
                }
                detail = result.receipt_dict()
                reply = (
                    f"{result.target_id.removeprefix('time.')} is "
                    f"{result.position_id.removeprefix('position.')}"
                )
            elif route_id == "route.neutral":
                detail = {
                    "status": "field-stable",
                    "logical_tick": self.world.logical_tick,
                }
                reply = "field stable; world unchanged"
            elif route_id == "route.goal-declaration":
                clauses = split_goal_action_clauses(text)
                observation = observe_proprioception(self.world)
                selected_actions = tuple(
                    select_grounded_action(
                        self.controller,
                        self.engine.law,
                        self.codec,
                        self._sense_instruction(
                            self.state,
                            observation,
                            clause,
                        ),
                    ).action_id
                    for clause in clauses
                )
                actions = (
                    selected_actions[0],
                    selected_actions[1],
                    selected_actions[2],
                )
                detail = self._store_deferred_goal(actions)
                goal = {"actions": actions, "status": "stored"}
                effective_consolidate = True
                reply = "goal stored: " + ", ".join(
                    action_id.removeprefix("action.") for action_id in actions
                )
            elif route_id == "route.goal-trigger":
                detail = self._execute_deferred_goal()
                stored_goal = detail["goal"]
                actions = stored_goal["actions"]
                goal = {
                    "actions": actions,
                    "status": "completed",
                    "step_count": len(detail["steps"]),
                }
                reply = "goal completed: " + ", ".join(
                    str(action_id).removeprefix("action.") for action_id in actions
                )
            else:
                raise CassiDiscourseLanguageError("field selected an unknown route")
        except (
            CassiDiscourseLanguageError,
            CassiFieldAgentError,
            CassiGroundedLanguageError,
        ) as error:
            if isinstance(error.__cause__, OSError):
                raise
            state_after_error = qi_state_sha256(self.controller, self.state)
            memory_after_error = self.engine.law.memory_sha256(self.state)
            world_after_error = self.world.snapshot()
            if (
                state_after_error != state_before_sha256
                or memory_after_error != memory_before_sha256
                or str(world_after_error["snapshot_sha256"])
                != str(world_before["snapshot_sha256"])
            ):
                raise CassiFieldAgentError(
                    "failed raw turn mutated persistent state"
                ) from error
            abstained = True
            reason = str(error)
            reply = "I cannot resolve that request."
            detail = {"error": reason, **dict(detail)}
        state_after_sha256 = qi_state_sha256(self.controller, self.state)
        memory_after_sha256 = self.engine.law.memory_sha256(self.state)
        world_after = self.world.snapshot()
        return CassiFieldAgentTurn(
            text=text,
            route_id=route_id,
            reply=reply,
            abstained=abstained,
            reason=reason,
            action=action,
            relation=relation,
            reference=reference,
            temporal=temporal,
            goal=goal,
            route_margin=route_margin,
            route_candidate_work=route_candidate_work,
            semantic_frame=route_detail,
            detail={"route": route_detail, "operation": dict(detail)},
            adaptive_persistent_state="QiFieldState.field[S,9M,B] only",
            field_ownership={
                "route": "QiFieldState.field atomic semantic-frame trajectory",
                "slots": "QiFieldState.field autoregressive trajectory work",
                "goal": "QiFieldState.field common-mode trajectory",
                "host_router": "none",
            },
            effective_consolidate=effective_consolidate,
            state_before_sha256=state_before_sha256,
            state_after_sha256=state_after_sha256,
            memory_before_sha256=memory_before_sha256,
            memory_after_sha256=memory_after_sha256,
            world_before_sha256=str(world_before["snapshot_sha256"]),
            world_after_sha256=str(world_after["snapshot_sha256"]),
            elapsed_seconds=time.perf_counter() - started,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._lock.close()

    def __enter__(self) -> "CassiFieldAgent":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


__all__ = [
    "AGENT_SCHEMA",
    "CassiFieldAgent",
    "CassiFieldAgentBinding",
    "CassiFieldAgentExplanation",
    "CassiFieldAgentQuery",
    "CassiFieldAgentError",
    "CassiFieldAgentReferenceQuery",
    "CassiFieldAgentOrdering",
    "CassiFieldAgentPrediction",
    "CassiFieldAgentStep",
    "CassiFieldAgentTurn",
]
