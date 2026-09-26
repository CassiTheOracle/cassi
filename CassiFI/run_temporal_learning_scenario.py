"""Measure learn-during-use retention and reuse in the temporal field.

The simulator alone owns mechanism state.  Every arm receives the same normal
bootstrap, three actual guided uses of an unfamiliar jammed mechanism, fixed
action/observation codecs, permitted probes, bound goals and transfer tasks.
The online arm admits each growing guided-use prefix as it is observed; the
oracle admits each completed use in one batch; the frozen arm observes but
does not retain them.  Transfer scoring disables all further admission.  No
model, hidden-state label or predicted evidence is admitted into the field.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

from cassi_field_atlas import AtlasState, canonical_json_bytes, sha256_value
from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner, SourceInput
from cassi_temporal_field import TemporalField


ACTIONS = ("sense", "inspect", "probe", "read", "idle", "release", "wait", "clear", "move")
OBSERVATIONS = ("pulse-a", "pulse-b", "closed", "waiting", "open", "ready", "quiet", "requested", "released", "cleared", "arrived", "blocked", "fault")
PROBES = ("probe", "read", "inspect", "idle")
CONTEXT = {"world": "bound-mechanisms"}
MEMORY = "mechanism-type"
SKILL = "release-connection"
GUIDED_ACTIONS = (
    "inspect", "idle", "read", "probe", "read", "inspect",
    "probe", "read", "clear", "release", "wait", "wait",
)
TRANSFER_MODES = ((True, True), (True, False))


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


@dataclass
class Mechanism:
    jammed: bool = False
    latched: bool = True
    pending: int = 0
    armed: bool = False

    def step(self, action: str) -> str:
        if action == "sense":
            return "pulse-b" if self.jammed else "pulse-a"
        if action == "inspect":
            return "open" if not self.latched else "waiting" if self.pending else "closed"
        if action == "probe":
            self.armed = True
            return "ready"
        if action == "read":
            if not self.armed:
                return "quiet"
            return "pulse-b" if self.jammed else "pulse-a"
        if action == "idle":
            return "quiet"
        if action == "clear":
            self.jammed, self.latched, self.pending = False, True, 0
            return "cleared"
        if action == "release":
            if not self.latched:
                return "released"
            self.pending = 2
            return "requested"
        if action == "wait":
            if self.pending:
                self.pending -= 1
                if not self.pending:
                    if self.jammed:
                        return "fault"
                    self.latched = False
                    return "released"
            return "released" if not self.latched else "quiet"
        if action == "move":
            return "blocked" if self.latched else "arrived"
        raise ValueError("unsupported simulator action")


class World:
    """Two unfamiliar connections constrain one load; effects deduplicate by proposal ID."""
    def __init__(
        self,
        modes: Sequence[bool],
        participant_ids: Sequence[str] = ("left", "right"),
    ) -> None:
        if not modes or len(modes) != len(participant_ids):
            raise ValueError("mechanism modes and participant ids must be nonempty and aligned")
        self.mechanisms = {
            name: Mechanism(jammed=mode)
            for name, mode in zip(participant_ids, modes, strict=True)
        }
        self.acknowledgments: dict[str, tuple[str, str, str]] = {}
        self.effects = 0

    def execute(self, proposal: Mapping[str, Any]) -> str:
        key = proposal["proposal_id"]
        prior = self.acknowledgments.get(key)
        identity = (proposal["participant_id"], proposal["action"])
        if prior is not None:
            require(prior[:2] == identity, "external effect identity was reused with different target/action")
            return prior[2]
        require(identity[0] in self.mechanisms and identity[1] != "sense", "unpermitted world effect")
        outcome = self.mechanisms[identity[0]].step(identity[1])
        self.acknowledgments[key] = (*identity, outcome)
        self.effects += 1
        return outcome

    @property
    def freed(self) -> bool:
        return all(not mechanism.latched for mechanism in self.mechanisms.values())


def observe_episode(jammed: bool, actions: Sequence[str]) -> list[dict[str, str]]:
    world = Mechanism(jammed=jammed)
    return [{"action": action, "observation": world.step(action)} for action in actions]


def bootstrap(seed: int) -> list[list[dict[str, str]]]:
    episodes = []
    for jammed in (False, True):
        accesses = [[], ["probe"], ["release"], ["release", "wait"], ["clear"], ["clear", "release", "wait", "wait"]]
        for access in accesses:
            # All are real complete source episodes, including useful probes and
            # observed failures. Access paths never enter the learner as labels.
            actions = ["sense", *access, "inspect", "idle", "read", "probe", "read", "inspect",
                       "release", "wait", "wait", "inspect", "move", "clear", "release", "wait", "wait", "move"]
            episodes.append(observe_episode(jammed, actions))
    random.Random(seed).shuffle(episodes)
    return episodes


def make_source(
    seed: int,
    arm: str,
    label: str,
    steps: Sequence[Mapping[str, str]],
    *,
    source_id: str | None = None,
    parent_revision_id: str | None = None,
    observed_timestamp: str | None = None,
) -> SourceInput:
    """Build one immutable episode revision.

    ``source_id`` identifies the participant/trial chain.  Revisions are
    append-only prefixes of that chain; the parent is carried in the source
    identity and is never treated as a second independent episode.
    """
    resolved_source_id = source_id or f"active:{seed}:{arm}:{label}"
    return SourceInput(
        source_id=resolved_source_id,
        content=canonical_json_bytes({"schema": "cassifi.temporal-episode.v1", "steps": list(steps)}),
        media_type="application/json", codec="utf-8",
        observed_timestamp=observed_timestamp or label,
        scope="temporal-active-learning", claim_category="controlled-world-observation",
        fidelity="exact-record", parent_revision_id=parent_revision_id,
        labels=("temporal-active-learning", "train"),
    )


class Session:
    def __init__(
        self,
        home: Path,
        seed: int,
        arm: str,
        *,
        memory_id: str = MEMORY,
        action_ids: Sequence[str] = ACTIONS,
        observation_ids: Sequence[str] = OBSERVATIONS,
        max_states: int = 64,
        context: Mapping[str, Any] = CONTEXT,
    ) -> None:
        self.home, self.seed, self.arm = home, seed, arm
        self.memory_id = memory_id
        self.context = context
        self.owner = FieldIntelligenceOwner(home, limits=CapacityLimits(max_history_entries=4096),
                                            initial_state=AtlasState(resonant_workspace=None))
        self.sequence = 0
        self.costs = {
            "admission_seconds": 0.0, "publication_seconds": 0.0,
            "inquiry_seconds": 0.0, "restart_seconds": 0.0,
            "evaluation_seconds": 0.0,
        }
        self.sources: list[Mapping[str, Any]] = []
        self.source_heads: dict[str, str] = {}
        self.source_prefixes: dict[str, tuple[Mapping[str, str], ...]] = {}
        self.owner.configure_temporal(
            self.op(),
            memory_id=memory_id,
            action_ids=action_ids,
            observation_ids=observation_ids,
            max_states=max_states,
            context=context,
        )

    def op(self) -> str:
        self.sequence += 1
        return f"active-{self.arm}-{self.seed}:{self.sequence}"

    def mutate(self, method: str, **kwargs: Any) -> Mapping[str, Any]:
        started = time.perf_counter()
        result = getattr(self.owner, method)(self.op(), **kwargs)
        self.costs["publication_seconds"] += time.perf_counter() - started
        return result

    def learn(
        self,
        label: str,
        steps: Sequence[Mapping[str, str]],
        *,
        source_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Admit a new prefix exactly once, retaining its source head.

        Replaying the same prefix is intentionally a local no-op.  A changed
        prefix must extend the current head, which prevents surprise prefixes
        from becoming unrelated training episodes.
        """
        chain_id = source_id or f"active:{self.seed}:{self.arm}:{label}"
        prefix = tuple({"action": row["action"], "observation": row["observation"]} for row in steps)
        prior = self.source_prefixes.get(chain_id)
        prior_length = len(prior) if prior is not None else 0
        if prior is not None:
            require(len(prefix) >= len(prior) and prefix[:len(prior)] == prior,
                    f"source chain {chain_id} was not extended append-only")
            if prefix == prior:
                return {
                    "skipped": True,
                    "receipt": {
                        "status": "skipped-unchanged",
                        "source_id": chain_id,
                        "parent_revision_id": self.source_heads.get(chain_id),
                        "source_revision_id": self.source_heads.get(chain_id),
                        "observation_count": 0,
                    },
                }
        parent_revision_id = self.source_heads.get(chain_id)
        source = make_source(
            self.seed, self.arm, label, prefix,
            source_id=chain_id, parent_revision_id=parent_revision_id,
            observed_timestamp=chain_id,
        )
        started = time.perf_counter()
        result = self.owner.learn_temporal(
            self.op(),
            memory_id=self.memory_id,
            source=source,
            context=self.context,
        )
        self.costs["admission_seconds"] += time.perf_counter() - started
        self.source_heads[chain_id] = source.revision_id
        self.source_prefixes[chain_id] = prefix
        delta_steps = list(prefix[prior_length:])
        source_receipt = {
            **dict(result["receipt"]),
            "source_id": source.source_id,
            "parent_revision_id": source.parent_revision_id,
            "source_revision_id": source.revision_id,
            "observation_count": len(delta_steps),
        }
        self.sources.append({
            "label": label, "source_id": source.source_id,
            "parent_revision_id": source.parent_revision_id,
            "steps": list(prefix), "delta_steps": delta_steps,
            "source_revision_id": source.revision_id,
            "episode_sha256": sha256_value(list(prefix)), "receipt": source_receipt,
        })
        return {**result, "receipt": source_receipt}

    def evaluate(self, function: Any, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            self.costs["evaluation_seconds"] += time.perf_counter() - started

    def restart(self) -> Mapping[str, Any]:
        before = self.owner.state.encode_bundle()
        identity = self.owner.state.state_sha256
        self.owner.close()
        started = time.perf_counter()
        self.owner = FieldIntelligenceOwner(self.home, limits=CapacityLimits(max_history_entries=4096))
        self.costs["restart_seconds"] += time.perf_counter() - started
        require(self.owner.state.encode_bundle() == before, "restart changed canonical field closure")
        return {"state_sha256": identity, "exact_closure": True}


def operations() -> list[dict[str, Any]]:
    # These are the only supplied safe probes.  Both directed and frozen
    # inquiry receive this exact permission set; frozen differs only by
    # disabling online admission below.
    return [{
        "action": action, "cost": 1.0, "risk": 0.0,
        "authorized": True, "feasible": True, "acquisition_allowed": True,
    } for action in PROBES]


def _has_support_gap(prediction: Mapping[str, Any]) -> bool:
    support = prediction.get("support")
    return prediction.get("supported") is False or (
        isinstance(support, Mapping) and bool(support.get("unknown_successor"))
    )


def _trial_source_id(session: Session, trial: int, participant: str) -> str:
    return f"active:{session.seed}:{session.arm}:trial-{trial}-{participant}"
def _learned_numeric_sha256(memory: TemporalField) -> str:
    """Hash the shared learned slice, excluding participant working planes."""
    return hashlib.sha256(memory.field[0].tobytes(order="C")).hexdigest()


def run_guided_use(session: Session, demonstration: int) -> Mapping[str, Any]:
    """Consume one actual use, admitting prefixes only in the online arm."""
    owner = session.owner
    participant = f"guide-{demonstration}"
    source_id = f"active:{session.seed}:{session.arm}:guided-{demonstration}"
    mechanism = Mechanism(jammed=True)
    session.mutate(
        "reset_temporal", memory_id=MEMORY,
        participant_id=participant, known_start=False,
    )
    steps: list[dict[str, str]] = []
    records: list[dict[str, Any]] = []
    memory_before_use = owner.state.temporal(MEMORY).memory_sha256
    for tick, action in enumerate(GUIDED_ACTIONS):
        owner = session.owner
        prediction = owner.inspect_temporal(
            MEMORY, participant_id=participant, action=action,
        )["prediction"]
        memory_before = owner.state.temporal(MEMORY).memory_sha256
        observation = mechanism.step(action)
        result = session.mutate(
            "advance_temporal", memory_id=MEMORY, participant_id=participant,
            action=action, observation=observation,
        )
        require(
            owner.state.temporal(MEMORY).memory_sha256 == memory_before,
            "guided-use inference changed learned memory",
        )
        steps.append({"action": action, "observation": observation})
        record: dict[str, Any] = {
            "tick": tick, "action": action, "observation": observation,
            "prediction": prediction, "receipt": result["receipt"],
        }
        if session.arm == "online":
            history_before = owner.state.temporal(MEMORY).history(
                participant_id=participant,
            )
            learning = session.learn(
                f"guided-{demonstration}-step-{tick}",
                steps,
                source_id=source_id,
            )
            require(
                session.owner.state.temporal(MEMORY).history(
                    participant_id=participant,
                ) == history_before,
                "guided-use admission lost the participant history",
            )
            record["learning"] = learning["receipt"]
        records.append(record)
    require(not mechanism.latched, "guided use did not release the mechanism")
    if session.arm == "oracle":
        learning = session.learn(
            f"guided-{demonstration}-complete",
            steps,
            source_id=source_id,
        )
        records[-1]["learning"] = learning["receipt"]
    memory_after_use = session.owner.state.temporal(MEMORY).memory_sha256
    if session.arm == "frozen":
        require(
            memory_after_use == memory_before_use,
            "frozen arm retained a guided use",
        )
    return {
        "demonstration": demonstration,
        "participant_id": participant,
        "source_id": source_id,
        "steps": steps,
        "records": records,
        "completed": True,
        "memory_changed": memory_after_use != memory_before_use,
        "skill": session.owner.inspect_temporal(
            MEMORY, participant_id=participant, skill_id=SKILL,
        )["skill"],
    }




def run_trial(
    session: Session,
    trial: int,
    modes: Sequence[bool],
    budget: int,
    *,
    learning_enabled: bool | None = None,
    participant_ids: Sequence[str] = ("left", "right"),
    inquiry_operations: Sequence[Mapping[str, Any]] | None = None,
    inquiry_horizon: int = 8,
) -> Mapping[str, Any]:
    allow_learning = session.arm != "frozen" if learning_enabled is None else learning_enabled
    world = World(modes, participant_ids)
    owner = session.owner
    task_id = f"free-load-{trial}"
    traces: dict[str, list[dict[str, str]]] = {name: [] for name in world.mechanisms}
    admitted: set[str] = set()
    records: list[dict[str, Any]] = []
    rng = random.Random(session.seed * 1009 + trial)
    for participant, mechanism in world.mechanisms.items():
        session.mutate("reset_temporal", memory_id=MEMORY, participant_id=participant, known_start=False)
        observation = mechanism.step("inspect")
        traces[participant].append({"action": "inspect", "observation": observation})
        session.mutate("advance_temporal", memory_id=MEMORY, participant_id=participant,
                       action="inspect", observation=observation)
    session.mutate("compose_temporal_task", task_id=task_id, context=CONTEXT, steps=[
        {"memory_id": MEMORY, "participant_id": name, "skill_id": SKILL} for name in world.mechanisms
    ])
    allowed = [{"participant_id": name, "action": action}
               for name in world.mechanisms for action in ACTIONS if action != "sense"]
    inquiry_ops = list(operations() if inquiry_operations is None else inquiry_operations)
    restarts: list[Mapping[str, Any]] = []
    continuity: list[Mapping[str, Any]] = []
    diagnostic_count = 0
    support_gap_count = 0
    retried = False
    for tick in range(budget):
        owner = session.owner
        view = owner.inspect_temporal_task(task_id)
        if view["status"] == "complete":
            break
        index = view["next_step"]
        if index is None or view["status"] == "invalidated":
            break
        participant = view["steps"][index]["participant_id"]
        memory_before = owner.state.temporal(MEMORY).memory_sha256
        evidence_before = owner.state.logical_tick
        proposal_result = None
        proposal = None
        inquiry = None
        if view["steps"][index]["decision"]["status"] == "proposed":
            proposal_result = session.mutate("propose_temporal_task", task_id=task_id, allowed_actions=allowed)
            proposal = proposal_result["receipt"]["proposal"]
            if proposal is None:
                break
            action = proposal["action"]
        else:
            if session.arm != "non-directed":
                started = time.perf_counter()
                inquiry = owner.inquire_temporal(
                    MEMORY, participant_id=participant, operations=inquiry_ops,
                    skill_id=SKILL, horizon=inquiry_horizon, max_nodes=4096,
                    forbidden_observations=("fault", "blocked"),
                )
                session.costs["inquiry_seconds"] += time.perf_counter() - started
                action = inquiry["action"]
            else:
                safe_actions = [operation["action"] for operation in inquiry_ops]
                candidates = owner.state.temporal(MEMORY).candidate_states(
                    participant_id=participant,
                )
                supported = [candidate for candidate in safe_actions if candidates and all(
                    owner.state.temporal(MEMORY).at_state(state).predict(candidate)["supported"]
                    for state in candidates
                )]
                # The baseline has the same safe probe permissions and budget as
                # directed inquiry; it must not require complete support.
                action = rng.choice(supported or safe_actions)
            if action is None:
                # A failed inquiry is a recorded failure, not permission to
                # bypass policy.  Safe supplied probes remain executable.
                records.append({
                    "tick": tick, "participant_id": participant, "kind": "unresolved",
                    "inquiry": inquiry, "failure": "no_safe_probe",
                })
                break
            diagnostic_count += 1
        prediction = owner.inspect_temporal(
            MEMORY, participant_id=participant, action=action,
        )["prediction"]
        if proposal is None:
            observation = world.mechanisms[participant].step(action)
            result = session.mutate(
                "advance_temporal", memory_id=MEMORY, participant_id=participant,
                action=action, observation=observation,
            )
        else:
            # Admit only the completed other participant's actual observations
            # while this participant has an outstanding external effect.
            for other in world.mechanisms:
                if not allow_learning or other == participant or other in admitted:
                    continue
                decision = owner.inspect_temporal(
                    MEMORY, participant_id=other, skill_id=SKILL,
                )["skill"]
                if decision["status"] == "complete":
                    prior_pending = owner.inspect_temporal_task(task_id)["pending_proposal"]
                    prior_decision = owner.inspect_temporal(
                        MEMORY, participant_id=participant, skill_id=SKILL,
                    )["skill"]
                    learning = session.learn(
                        f"trial-{trial}-{other}", traces[other],
                        source_id=_trial_source_id(session, trial, other),
                    )
                    admitted.add(other)
                    after_decision = owner.inspect_temporal(
                        MEMORY, participant_id=participant, skill_id=SKILL,
                    )["skill"]
                    require(
                        owner.inspect_temporal_task(task_id)["pending_proposal"] == prior_pending,
                        "learning lost pending proposal",
                    )
                    continuity.append({
                        "participant_id": participant, "before": prior_decision,
                        "after": after_decision, "pending_preserved": True,
                        "learning": learning["receipt"],
                    })
                    memory_before = owner.state.temporal(MEMORY).memory_sha256
                    evidence_before = owner.state.logical_tick
            observation = world.execute(proposal)
            acknowledgment_id = session.op()
            if trial == 0 and not retried:
                effects = world.effects
                restarts.append(session.restart())
                owner = session.owner
                require(
                    world.execute(proposal) == observation and world.effects == effects,
                    "retry repeated an external effect",
                )
                retried = True
            started = time.perf_counter()
            result = owner.acknowledge_temporal_task(
                acknowledgment_id, task_id=task_id, proposal_id=proposal["proposal_id"],
                participant_id=participant, action=action, observation=observation,
            )
            session.costs["publication_seconds"] += time.perf_counter() - started
            identity = owner.state.state_sha256
            repeated = owner.acknowledge_temporal_task(
                acknowledgment_id, task_id=task_id, proposal_id=proposal["proposal_id"],
                participant_id=participant, action=action, observation=observation,
            )
            require(
                repeated["receipt"] == result["receipt"]
                and repeated["checkpoint_receipt"]["replayed"],
                "ack retry changed receipt",
            )
            require(owner.state.state_sha256 == identity, "ack retry consumed observation twice")
        traces[participant].append({"action": action, "observation": observation})
        require(owner.state.temporal(MEMORY).memory_sha256 == memory_before,
                "inference changed learned memory")
        require(owner.state.logical_tick == evidence_before,
                "inference admitted its prediction as evidence")
        gap = _has_support_gap(prediction)
        if gap:
            support_gap_count += 1
        records.append({
            "tick": tick, "participant_id": participant,
            "kind": "skill" if proposal_result else "inquiry",
            "action": action, "observation": observation,
            "prediction": prediction, "inquiry": inquiry, "support_gap": gap,
            "receipt": result["receipt"],
        })
        # Forbidden outcomes are retained as measured failures.  They are not
        # turned into labels or bypasses, and terminate this unsafe path.
        if observation in {"fault", "blocked"}:
            break
        if allow_learning and gap:
            history_before = owner.state.temporal(MEMORY).history(participant_id=participant)
            learning = session.learn(
                f"trial-{trial}-{participant}-support-gap-{tick}",
                traces[participant], source_id=_trial_source_id(session, trial, participant),
            )
            require(
                owner.state.temporal(MEMORY).history(participant_id=participant) == history_before,
                "admitting a new actual outcome lost the in-progress history",
            )
            records[-1]["online_learning"] = learning["receipt"]
    owner = session.owner
    final = owner.inspect_temporal_task(task_id)
    completed = final["status"] == "complete"
    require(not completed or world.freed,
            "task falsely completed before both distinct connections were released")
    before_count = owner.state.temporal(MEMORY).state_count
    for participant in world.mechanisms:
        if allow_learning and participant not in admitted:
            session.learn(
                f"trial-{trial}-{participant}", traces[participant],
                source_id=_trial_source_id(session, trial, participant),
            )
    return {
        "trial": trial, "evaluation_modes": list(modes), "task_id": task_id,
        "completed": completed, "load_freed": world.freed,
        "interactions": sum("observation" in row for row in records) + 2,
        "diagnostic_interactions": diagnostic_count, "support_gap_observations": support_gap_count,
        "unsafe_observations": sum(row.get("observation") in {"fault", "blocked"} for row in records),
        "context_recoveries": sum(
            row.get("support_gap") is True
            and isinstance(row.get("receipt"), Mapping)
            and isinstance(row["receipt"].get("context"), Mapping)
            and row["receipt"]["context"].get("status") == "recovered"
            for row in records
        ),
        "recovery_sequences": sum(
            isinstance(row.get("inquiry"), Mapping)
            and row["inquiry"].get("reason") == "context-recovery-sequence"
            for row in records
        ),
        "records": records, "source_episodes": traces, "continuity": continuity,
        "restarts": restarts, "deduplicated_external_retry": retried,
        "state_count_before_admission": before_count,
        "state_count_after_admission": owner.state.temporal(MEMORY).state_count,
        "final_task": final, "external_effect_count": world.effects,
    }


def heldout(memory: TemporalField) -> Mapping[str, Any]:
    """Fixed external outcome probes; no evaluation episode is admitted."""
    before = memory.state_sha256
    cases = []
    for jammed in (False, True):
        for access in ((), ("release",), ("release", "wait", "wait"), ("clear",)):
            for dwell in (3, 9):
                for query in ("read", "wait", "move"):
                    world = Mechanism(jammed=jammed)
                    active = memory.reset(known_start=False)
                    steps = []
                    for action in ("inspect", "probe", "read", *access, *(["idle"] * dwell)):
                        observation = world.step(action)
                        steps.append({"action": action, "observation": observation})
                        active, _ = active.consume(action, observation)
                    prediction = active.predict(query)
                    target = world.step(query)
                    prediction_label = max(prediction["probabilities"], key=prediction["probabilities"].get) if prediction["supported"] else None
                    cases.append({"prefix": steps, "query": query, "target": target, "prediction": prediction,
                                  "correct": prediction_label == target,
                                  "episode_sha256": sha256_value([*steps, {"action": query, "observation": target}])})
    require(memory.state_sha256 == before, "held-out evaluation mutated learned or working state")
    return {"cases": cases, "total": len(cases), "answered": sum(row["prediction"]["supported"] for row in cases),
            "correct": sum(row["correct"] for row in cases), "state_unchanged": True}


FRESH_SPLIT_ID = "temporal-fresh-heldout-v1"


def fresh_heldout(
    memory: TemporalField,
    seed: int,
    *,
    training_hashes: Sequence[str] = (),
) -> Mapping[str, Any]:
    """Evaluate deterministic operation orders not used by the old holdout.

    Targets are generated by the simulator at evaluation time and are never
    admitted.  The split deliberately uses delays other than the legacy 3/9
    dwell values and records raw prefixes so provenance remains auditable.
    """
    before = memory.state_sha256
    rng = random.Random(seed * 7919 + 17)
    plans = [
        (False, ("probe", "inspect", "read", "release", "wait", "wait", "move"), 2, "read"),
        (True, ("inspect", "probe", "read", "clear", "release", "wait", "wait"), 5, "move"),
        (False, ("inspect", "idle", "probe", "read", "release", "wait"), 7, "wait"),
        (True, ("probe", "read", "inspect", "release", "wait", "clear"), 11, "read"),
    ]
    rng.shuffle(plans)
    cases: list[dict[str, Any]] = []
    training = set(training_hashes)
    for jammed, order, delay, query in plans:
        world = Mechanism(jammed=jammed)
        active = memory.reset(known_start=False)
        steps: list[dict[str, str]] = []
        for action in (*order, *(["idle"] * delay)):
            observation = world.step(action)
            steps.append({"action": action, "observation": observation})
            active, _ = active.consume(action, observation)
        prediction = active.predict(query)
        target = world.step(query)
        prediction_label = (
            max(prediction["probabilities"], key=prediction["probabilities"].get)
            if prediction["supported"] else None
        )
        episode_sha256 = sha256_value([*steps, {"action": query, "observation": target}])
        require(episode_sha256 not in training,
                "fresh evaluation episode was admitted as training")
        cases.append({
            "split_id": FRESH_SPLIT_ID, "jammed": jammed,
            "operation_order": list(order), "delay": delay, "prefix": steps,
            "query": query, "target": target, "prediction": prediction,
            "correct": prediction_label == target, "episode_sha256": episode_sha256,
            "training_overlap": False,
        })
    require(memory.state_sha256 == before,
            "fresh held-out evaluation mutated learned or working state")
    return {
        "split_id": FRESH_SPLIT_ID, "cases": cases, "total": len(cases),
        "answered": sum(row["prediction"]["supported"] for row in cases),
        "correct": sum(row["correct"] for row in cases),
        "state_unchanged": True, "training_disjoint": True,
    }


def run_arm(home: Path, seed: int, arm: str, budget: int) -> dict[str, Any]:
    session = Session(home, seed, arm)
    started = time.perf_counter()
    try:
        normal_bootstrap = [
            episode for episode in bootstrap(seed)
            if episode[0]["observation"] == "pulse-a"
        ]
        require(len(normal_bootstrap) == 6, "normal bootstrap count changed")
        for index, episode in enumerate(normal_bootstrap):
            session.learn(f"bootstrap-normal-{index}", episode)

        reference_steps = [
            {"action": "start", "observation": "ready"},
            {"action": "finish", "observation": "done"},
        ]
        session.mutate(
            "configure_temporal", memory_id="retained-reference",
            action_ids=("start", "finish"), observation_ids=("ready", "done"),
            max_states=8,
        )
        session.mutate(
            "learn_temporal", memory_id="retained-reference",
            source=make_source(seed, arm, "retained-reference", reference_steps),
        )
        retained = session.owner.state.temporal("retained-reference").as_dict()
        session.mutate(
            "condense_temporal_skill", memory_id=MEMORY, skill_id=SKILL,
            goal_observations=("released",),
            forbidden_observations=("fault", "blocked"),
        )
        for participant in ("left", "right", "guide-0", "guide-1", "guide-2"):
            session.mutate(
                "bind_temporal", memory_id=MEMORY,
                participant_id=participant, known_start=False,
            )

        initial = session.owner.state.temporal(MEMORY).as_dict()
        initial_state_count = session.owner.state.temporal(MEMORY).state_count
        initial_numeric_sha256 = _learned_numeric_sha256(
            session.owner.state.temporal(MEMORY)
        )
        demonstrations: list[Mapping[str, Any]] = []
        for demonstration in range(3):
            demonstrations.append(run_guided_use(session, demonstration))
            if demonstration == 1:
                session.restart()

        trained = session.owner.state.temporal(MEMORY).as_dict()
        trained_state_count = session.owner.state.temporal(MEMORY).state_count
        trained_numeric_sha256 = _learned_numeric_sha256(
            session.owner.state.temporal(MEMORY)
        )
        learned_from_use = trained["memory_sha256"] != initial["memory_sha256"]
        if arm == "frozen":
            require(not learned_from_use, "frozen control retained guided experience")
        else:
            require(learned_from_use, f"{arm} arm failed to retain guided experience")

        transfer_trials: list[Mapping[str, Any]] = []
        transfer_memory_sha256 = trained["memory_sha256"]
        for trial, modes in enumerate(TRANSFER_MODES):
            row = dict(
                run_trial(
                    session, trial, modes, budget,
                    learning_enabled=False,
                )
            )
            require(
                session.owner.state.temporal(MEMORY).memory_sha256
                == transfer_memory_sha256,
                "transfer scoring changed learned memory",
            )
            transfer_trials.append(row)

        if arm in {"online", "oracle"}:
            require(
                all(row["completed"] for row in transfer_trials),
                f"{arm} arm failed a retained transfer task",
            )
        else:
            require(
                not any(row["completed"] for row in transfer_trials),
                "frozen control completed without the withheld experience",
            )

        final = session.owner.state.temporal(MEMORY).as_dict()
        require(
            final["memory_sha256"] == transfer_memory_sha256,
            "transfer altered retained temporal memory",
        )
        require(
            session.owner.state.temporal("retained-reference").as_dict() == retained,
            "guided learning modified unrelated learned knowledge",
        )
        predictions = [
            record
            for row in transfer_trials
            for record in row["records"]
            if "prediction" in record
        ]
        answered = [
            record for record in predictions
            if record["prediction"]["supported"]
        ]
        correct = sum(
            max(
                record["prediction"]["probabilities"],
                key=record["prediction"]["probabilities"].get,
            ) == record["observation"]
            for record in answered
        )
        restart = session.restart()
        storage = {
            "temporal_field_bytes": session.owner.state.temporal(MEMORY).nbytes,
            "active_closure_bytes": session.owner.state.closure_bytes,
            "evidence_bytes": session.owner.evidence.physical_bytes(),
            "data_home_bytes": sum(
                path.stat().st_size for path in home.rglob("*") if path.is_file()
            ),
        }
        elapsed = time.perf_counter() - started
        guided_sources = [
            source for source in session.sources
            if ":guided-" in source["source_id"]
        ]
        guided_heads = [
            source_id for source_id in session.source_heads
            if ":guided-" in source_id
        ]
        metrics = {
            "guided_uses_observed": len(demonstrations),
            "guided_observations": sum(
                len(row["steps"]) for row in demonstrations
            ),
            "guided_admission_revisions": len(guided_sources),
            "retained_guided_source_heads": len(guided_heads),
            "learned_from_use": learned_from_use,
            "initial_state_count": initial_state_count,
            "trained_state_count": trained_state_count,
            "initial_numeric_sha256": initial_numeric_sha256,
            "trained_numeric_sha256": trained_numeric_sha256,
            "completed": sum(row["completed"] for row in transfer_trials),
            "total": len(transfer_trials),
            "interactions": sum(row["interactions"] for row in transfer_trials),
            "diagnostic_interactions": sum(
                row["diagnostic_interactions"] for row in transfer_trials
            ),
            "support_gap_observations": sum(
                row["support_gap_observations"] for row in transfer_trials
            ),
            "predictions": len(predictions),
            "answered": len(answered),
            "correct": correct,
            "unsafe_observations": sum(
                row["unsafe_observations"] for row in transfer_trials
            ),
            "context_recoveries": sum(
                row["context_recoveries"] for row in transfer_trials
            ),
            "recovery_sequences": sum(
                row["recovery_sequences"] for row in transfer_trials
            ),
            "elapsed_seconds": elapsed,
        }
        return {
            "seed": seed,
            "arm": arm,
            "demonstrations": demonstrations,
            "transfer_trials": transfer_trials,
            "trials": transfer_trials,
            "sources": session.sources,
            "source_heads": dict(session.source_heads),
            "source_prefixes": {
                source_id: list(prefix)
                for source_id, prefix in session.source_prefixes.items()
            },
            "initial_field": initial,
            "trained_field": trained,
            "final_field": final,
            "costs": session.costs,
            "storage": storage,
            "retention": {
                "unrelated_field": retained,
                "unrelated_exact": True,
                "memory_stable_during_transfer": True,
            },
            "elapsed_seconds": elapsed,
            "metrics": metrics,
            "restart": restart,
            "live_model_calls": 0,
        }
    finally:
        session.owner.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    parser.add_argument("--budget", type=int, default=32)
    args = parser.parse_args()
    if not 4 <= args.budget <= 128 or not 1 <= len(args.seeds) <= 16:
        parser.error("scenario bounds exceeded")
    if args.data_home.exists() or args.output.exists():
        parser.error("output and data-home must be unused paths")
    torch.set_num_threads(1)
    runs: list[dict[str, Any]] = []
    for seed in args.seeds:
        seed_runs: dict[str, dict[str, Any]] = {}
        for arm in ("online", "oracle", "frozen"):
            started = time.perf_counter()
            run = run_arm(
                args.data_home / f"seed-{seed}" / arm,
                seed,
                arm,
                args.budget,
            )
            run["elapsed_seconds"] = time.perf_counter() - started
            run["metrics"]["elapsed_seconds"] = run["elapsed_seconds"]
            runs.append(run)
            seed_runs[arm] = run
            print(json.dumps({"seed": seed, "arm": arm, **run["metrics"]}), flush=True)

        initial_payloads = {
            row["metrics"]["initial_numeric_sha256"]
            for row in seed_runs.values()
        }
        require(
            len(initial_payloads) == 1,
            "matched arms did not start from the same numeric field",
        )
        require(
            seed_runs["online"]["metrics"]["trained_numeric_sha256"]
            == seed_runs["oracle"]["metrics"]["trained_numeric_sha256"],
            "incremental and one-shot admission produced different numeric fields",
        )
        require(
            seed_runs["frozen"]["metrics"]["trained_numeric_sha256"]
            == seed_runs["frozen"]["metrics"]["initial_numeric_sha256"],
            "frozen guided observations changed learned numeric state",
        )
        require(
            seed_runs["online"]["metrics"]["trained_numeric_sha256"]
            != seed_runs["online"]["metrics"]["initial_numeric_sha256"],
            "online guided experience did not change learned numeric state",
        )
        guided_traces = {
            json.dumps(
                [row["steps"] for row in run["demonstrations"]],
                sort_keys=True,
                separators=(",", ":"),
            )
            for run in seed_runs.values()
        }
        require(
            len(guided_traces) == 1,
            "matched arms did not observe identical guided uses",
        )

    report = {
        "schema": "cassifi.temporal-active-learning.v2",
        "configuration": {
            "seeds": args.seeds,
            "decision_budget_per_transfer": args.budget,
            "normal_bootstrap_episodes_per_arm": 6,
            "guided_uses_per_arm": 3,
            "guided_observations_per_use": len(GUIDED_ACTIONS),
            "guided_actions": list(GUIDED_ACTIONS),
            "transfer_modes": [list(modes) for modes in TRANSFER_MODES],
            "transfer_tasks_per_arm": len(TRANSFER_MODES),
            "transfer_admission_enabled": False,
            "permitted_probes": list(PROBES),
            "arms": ["online", "oracle", "frozen"],
            "online_arm": (
                "admits each growing guided-use prefix immediately, then scores "
                "two transfer tasks with admission disabled"
            ),
            "oracle_arm": (
                "observes the same uses, admits each completed episode once, "
                "then scores the same transfer tasks with admission disabled"
            ),
            "frozen_control": (
                "observes the same uses but admits none, then receives the same "
                "inquiry policy, permissions and transfer budgets"
            ),
            "scope": (
                "closed-vocabulary simulator; supplied normal bootstrap, guided "
                "use actions and participant-bound goals"
            ),
        },
        "runs": runs,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limitations": [
            "Empirical categorical support is not calibrated probability.",
            "The guided action sequence is supplied; this tests learning during use, retention and reuse, not autonomous curriculum discovery.",
            "Participant bindings and goal composition are supplied; transfer actions are selected from learned field structure.",
            "Exactly-once external effects require an idempotent adapter; the simulator implements that contract.",
            "The result concerns two controlled transfer arrangements, not open-vocabulary or broad compositional generalization.",
            "The seven-pool continuous wave law is unchanged.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
