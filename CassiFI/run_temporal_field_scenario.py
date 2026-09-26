"""Exercise learned predictive memory, context separation and closed-loop skills.

The sandbox owns its hidden mechanics. The learner receives only ordered current
(action, observation) events, never hidden state, delay counters or lag columns.
Training action coverage is supplied; exploration and vocabulary are not learned.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch

from cassi_field_atlas import AtlasState, RelationChart, VariableSpec, canonical_json_bytes, sha256_value
from cassi_field_owner import AuthorityGrant, CapacityLimits, FieldIntelligenceError, FieldIntelligenceOwner, SourceInput
from cassi_resonant_field import ResonantProfile, initial_workspace

ACTIONS = ("sense", "idle", "release", "wait", "move", "clear")
OBSERVATIONS = ("pulse-a", "pulse-b", "quiet", "requested", "released", "blocked", "arrived", "cleared", "fault")
MEMORY = "mechanism"
CONTEXT = {"world": "temporal-mechanism"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


@dataclass
class Mechanism:
    """External world, including the only hidden latch and pending-request state."""
    jammed: bool = False
    latched: bool = True
    pending: int = 0

    def step(self, action: str) -> str:
        if action == "sense":
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
            return "quiet"
        if action == "move":
            return "blocked" if self.latched else "arrived"
        raise ValueError(f"unknown sandbox action: {action}")


def episode(jammed: bool, actions: Sequence[str]) -> list[dict[str, str]]:
    world = Mechanism(jammed=jammed)
    return [{"action": action, "observation": world.step(action)} for action in actions]


def training_episodes(seed: int, jammed: bool) -> list[list[dict[str, str]]]:
    """Cover interventions in reachable states; the learner never sees access labels."""
    rng = random.Random(seed + 1009 * int(jammed))
    access = [(), ("release",), ("release", "wait"), ("release", "wait", "wait")]
    if jammed:
        access += [("clear",), ("clear", "release", "wait", "wait")]
    experiments = [(prefix, action) for prefix in access for action in ACTIONS if action != "sense"]
    rng.shuffle(experiments)
    result = []
    for index, (prefix, action) in enumerate(experiments):
        commands = ["sense", *prefix, *(["idle"] * (index % 3)), action]
        commands += ["idle"] * rng.randrange(3)
        # Repeated acknowledgments before another request distinguish pending
        # work from an untouched latch; a new request would erase that difference.
        commands += ["move", "wait", "wait", "move", "release", "wait", "move", "wait", "move"]
        if jammed:
            commands += ["clear", "release", "wait", "wait", "move"]
        result.append(episode(jammed, commands))
    return result


def source_for(seed: int, label: str, steps: Sequence[Mapping[str, str]]) -> SourceInput:
    return SourceInput(
        source_id=f"temporal:{seed}:{label}",
        content=canonical_json_bytes({"schema": "cassifi.temporal-episode.v1", "steps": steps}),
        media_type="application/json", codec="utf-8", observed_timestamp=label,
        scope="temporal-development", claim_category="controlled-world-observation",
        fidelity="exact-record", labels=("temporal-development", "train"),
    )


class Session:
    def __init__(self, home: Path, seed: int) -> None:
        self.home, self.seed, self.sequence = home, seed, 0
        self.owner = FieldIntelligenceOwner(
            home, limits=CapacityLimits(max_history_entries=48),
            initial_state=AtlasState(resonant_workspace=initial_workspace(ResonantProfile(beta=0.0, damping=0.5))),
        )
        self.training_hashes: set[str] = set()
        self.training: list[dict[str, Any]] = []
        self.costs = {"admission_seconds": 0.0, "inference_publication_seconds": 0.0, "restart_seconds": 0.0}
        self.owner.configure_temporal(self.op(), memory_id=MEMORY, action_ids=ACTIONS,
                                      observation_ids=OBSERVATIONS, max_states=128, context=CONTEXT)

    def op(self) -> str:
        self.sequence += 1
        return f"temporal-{self.seed}:{self.sequence}"

    def reset(self) -> None:
        self.owner.reset_temporal(self.op(), memory_id=MEMORY)

    def consume(self, action: str, observation: str) -> Mapping[str, Any]:
        started = time.perf_counter()
        result = self.owner.advance_temporal(self.op(), memory_id=MEMORY, action=action, observation=observation)
        self.costs["inference_publication_seconds"] += time.perf_counter() - started
        return result

    def train(self, steps: list[dict[str, str]], label: str) -> Mapping[str, Any]:
        source = source_for(self.seed, label, steps)
        started = time.perf_counter()
        result = self.owner.learn_temporal(self.op(), memory_id=MEMORY, source=source, context=CONTEXT)
        elapsed = time.perf_counter() - started
        self.costs["admission_seconds"] += elapsed
        self.training_hashes.add(sha256_value(steps))
        self.training.append({"label": label, "steps": steps, "source_revision_id": source.revision_id,
                              "episode_sha256": sha256_value(steps), "receipt": result["receipt"], "seconds": elapsed})
        return result

    def evaluate(self, jammed: bool, prefix: Sequence[str], dwell: int, label: str) -> dict[str, Any]:
        steps = episode(jammed, ["sense", *prefix, *(["idle"] * dwell), "move"])
        require(sha256_value(steps) not in self.training_hashes, "held-out sequence overlaps training")
        self.reset()
        before = self.owner.state.temporal(MEMORY).memory_sha256
        evidence_clock = self.owner.state.logical_tick
        failure = None
        for step in steps[:-1]:
            try:
                self.consume(step["action"], step["observation"])
            except FieldIntelligenceError as exc:
                failure = {"code": exc.code, "message": str(exc)}
                break
        field = self.owner.state.temporal(MEMORY)
        prediction = field.predict("move") if failure is None else {"supported": False, "probabilities": {}}
        cleared = field.reset().predict("move")
        current_only_counts: dict[str, int] = {}
        for training in self.training:
            previous = None
            for event in training["steps"]:
                if event["action"] == "move" and previous == steps[-2]["observation"]:
                    current_only_counts[event["observation"]] = current_only_counts.get(event["observation"], 0) + 1
                previous = event["observation"]
        current_only_answer = max(sorted(current_only_counts), key=current_only_counts.__getitem__) if current_only_counts else None
        require(field.memory_sha256 == before, "inference changed learned temporal memory")
        require(self.owner.state.logical_tick == evidence_clock, "inference advanced evidence clock")
        probabilities = prediction["probabilities"]
        answer = max(probabilities, key=probabilities.get) if prediction["supported"] and probabilities else None
        return {"label": label, "jammed_world": jammed, "steps": steps,
                "episode_sha256": sha256_value(steps), "target": steps[-1]["observation"],
                "prediction": prediction, "answer": answer, "correct": answer == steps[-1]["observation"],
                "cleared_prediction": cleared, "failure": failure,
                "current_only_diagnostic": {"observed_support": current_only_counts, "answer": current_only_answer,
                                            "correct": current_only_answer == steps[-1]["observation"]},
                "memory_sha256": before, "memory_unchanged": True, "evidence_clock_unchanged": True}

    def restart_probe(self) -> Mapping[str, Any]:
        self.reset()
        self.consume("sense", "pulse-a")
        self.consume("release", "requested")
        self.consume("wait", "quiet")
        before = self.owner.state.encode_bundle()
        identity = self.owner.state.state_sha256
        numerical = self.owner.state.temporal(MEMORY)
        continued, expected = numerical.consume("wait", "released")
        started = time.perf_counter()
        self.owner.close()
        self.owner = FieldIntelligenceOwner(self.home)
        self.costs["restart_seconds"] += time.perf_counter() - started
        require(self.owner.state.encode_bundle() == before, "restart changed canonical closure")
        operation_id = self.op()
        first = self.owner.advance_temporal(operation_id, memory_id=MEMORY, action="wait", observation="released",
                                            expected_state_sha256=identity)
        after = self.owner.state.state_sha256
        require(self.owner.state.temporal(MEMORY).state_sha256 == continued.state_sha256, "restart changed continuation")
        retry = self.owner.advance_temporal(operation_id, memory_id=MEMORY, action="wait", observation="released",
                                            expected_state_sha256=identity)
        require(retry["checkpoint_receipt"]["replayed"] and self.owner.state.state_sha256 == after, "retry consumed observation twice")
        require(first["receipt"] == retry["receipt"], "retry changed frozen receipt")
        try:
            self.owner.advance_temporal(operation_id, memory_id=MEMORY, action="wait", observation="quiet")
        except FieldIntelligenceError as exc:
            require(exc.code == "OPERATION_CONFLICT", "wrong retry-conflict refusal")
        else:
            raise RuntimeError("conflicting observation replay was accepted")
        return {"exact_closure": True, "exact_continuation": True, "exactly_once": True,
                "conflicting_replay_refused": True, "expected_receipt": expected}

    def skill_run(self, jammed: bool, dwell: int, *, interrupt: bool = False) -> Mapping[str, Any]:
        self.reset()
        world = Mechanism(jammed=jammed)
        self.consume("sense", world.step("sense"))
        for _ in range(dwell):
            self.consume("idle", world.step("idle"))
        memory = self.owner.state.temporal(MEMORY).memory_sha256
        actions: list[dict[str, Any]] = []
        done = False
        for step in range(16):
            decision = self.owner.inspect_temporal(MEMORY, skill_id="relocate")["skill"]
            if decision["status"] == "complete":
                done = True
                break
            if decision["status"] != "proposed":
                actions.append({"decision": decision})
                break
            action = decision["action"]
            # Only this explicitly bounded simulator executes actions; runtime
            # proposals do not authorize any host or external-world operation.
            actual = world.step(action)
            if interrupt and action == "wait" and actual == "released":
                actual = "fault"  # observed failure outside this learned branch
            actions.append({"decision": decision, "action": action, "observation": actual})
            self.consume(action, actual)
            if interrupt and actual == "fault":
                stop = self.owner.inspect_temporal(MEMORY, skill_id="relocate")["skill"]
                require(stop["status"] == "unresolved", "skill continued after unexpected acknowledgment")
                return {"jammed_world": jammed, "steps": actions, "stopped_on_unexpected_outcome": True, "final_decision": stop}
        require(self.owner.state.temporal(MEMORY).memory_sha256 == memory, "skill execution changed learned memory")
        moved = any(row.get("observation") == "arrived" for row in actions)
        unsafe = any(row.get("observation") in {"blocked", "fault"} for row in actions)
        return {"jammed_world": jammed, "dwell": dwell, "steps": actions,
                "complete": done and moved, "unsafe_observation": unsafe,
                "memory_unchanged": True}


def seed_instrument(session: Session) -> Mapping[str, Any]:
    owner = session.owner
    for variable in (VariableSpec("bias", kind="constant", constant=1.0),
                     VariableSpec("signal", lower=-8.0, upper=8.0), VariableSpec("response", lower=-16.0, upper=16.0)):
        owner.configure_variable(session.op(), variable)
    owner.configure_chart(session.op(), RelationChart.empty(
        chart_id="retained-instrument", scope=("bias", "signal", "response"), ridge=0.001,
        prior_mass=1e-4, observation_norm_bound=20.0,
    ))
    for index, value in enumerate(np.linspace(-2, 2, 16)):
        observed = {"bias": 1.0, "signal": float(value), "response": float(1.3 * value + 0.25)}
        source = SourceInput(source_id=f"retained:{session.seed}:{index}", content=canonical_json_bytes(observed),
                             media_type="application/json", codec="utf-8", observed_timestamp=str(index),
                             scope="temporal-development", claim_category="observation", fidelity="exact-record")
        owner.admit_observation(operation_id=session.op(), source=source, values=observed, context={},
                                target_chart_ids=("retained-instrument",))
    return {"chart_sha256": sha256_value(owner.state.chart("retained-instrument").as_dict()),
            "predictions": instrument_predictions(session)}


def instrument_predictions(session: Session) -> list[float]:
    chart = session.owner.state.chart("retained-instrument")
    engine = chart.engine
    field = chart.numeric_field
    predictions = []
    for value in (-2.5, 0.35, 2.5):
        conditioned, _ = engine.condition(field, (0, 1), (1.0, value))
        predictions.append(float(engine.workspace(conditioned)[2]))
    return predictions


def summarize(records: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    answered = sum(row["answer"] is not None for row in records)
    correct = sum(row["correct"] for row in records)
    return {"cases": len(records), "answered": answered, "correct": correct,
            "coverage": answered / len(records), "accuracy": correct / len(records)}

def memory_interventions(session: Session) -> Mapping[str, Any]:
    before = session.owner.state.state_sha256
    field = session.owner.state.temporal(MEMORY)
    states = []
    for prefix in (("release",), ("release", "wait", "wait")):
        current = field.reset()
        events = episode(False, ("sense", *prefix, *(["idle"] * 7)))
        for event in events:
            current, _ = current.consume(event["action"], event["observation"])
        states.append(current)
    original = states[0].predict("move")
    other = states[1].predict("move")
    swapped = states[0].at_state(states[1].candidate_states()[0])
    changed = swapped.predict("move")
    require(original["probabilities"] == {"blocked": 1.0} and changed["probabilities"] == {"arrived": 1.0},
            "working-state intervention did not change the matched-input prediction")
    require(changed["probabilities"] == other["probabilities"], "swapped memory failed to transport its learned continuation")
    require(swapped.memory_sha256 == field.memory_sha256, "working intervention changed learned relations")
    require(session.owner.state.state_sha256 == before, "diagnostic intervention mutated the canonical owner")
    return {"current_observation": "quiet", "query_action": "move", "ordinary": original,
            "alternate_history": other, "swapped_working_state": changed,
            "learned_relations_unchanged": True, "owner_unchanged": True}



def run_seed(home: Path, seed: int) -> Mapping[str, Any]:
    session = Session(home, seed)
    started = time.perf_counter()
    try:
        retained = seed_instrument(session)
        for index, steps in enumerate(training_episodes(seed, False)):
            session.train(steps, f"normal-{index}")
        early = [session.evaluate(True, ("release", "wait", "wait"), dwell, f"unseen-context-{dwell}")
                 for dwell in (3, 7, 11)]
        normal_before = [session.evaluate(False, prefix, dwell, f"normal-before-{len(prefix)}-{dwell}")
                         for prefix in ((), ("release",), ("release", "wait"), ("release", "wait", "wait"))
                         for dwell in (3, 7, 11)]
        states_before = session.owner.state.temporal(MEMORY).state_count
        for index, steps in enumerate(training_episodes(seed, True)):
            session.train(steps, f"context-{index}")
        final = []
        for jammed in (False, True):
            prefixes = [(), ("release",), ("release", "wait"), ("release", "wait", "wait")]
            if jammed:
                prefixes.append(("clear", "release", "wait", "wait"))
            for prefix in prefixes:
                for dwell in (3, 7, 11):
                    final.append(session.evaluate(jammed, prefix, dwell, f"final-{jammed}-{prefix}-{dwell}"))
        restart = session.restart_probe()
        interventions = memory_interventions(session)
        session.owner.condense_temporal_skill(session.op(), memory_id=MEMORY, skill_id="relocate",
                                              goal_observations=("arrived",), forbidden_observations=("blocked", "fault"))
        skill_runs = [session.skill_run(jammed, dwell) for jammed in (False, True) for dwell in (3, 11)]
        interrupted = session.skill_run(False, 7, interrupt=True)
        require(all(row["complete"] and not row["unsafe_observation"] for row in skill_runs), "learned skill did not safely complete")
        final_retained = instrument_predictions(session)
        require(retained["chart_sha256"] == sha256_value(session.owner.state.chart("retained-instrument").as_dict()),
                "unrelated instrument memory changed")
        require(retained["predictions"] == final_retained, "unrelated instrument predictions changed")
        numerical = session.owner.state.temporal(MEMORY)
        model_before = numerical.memory_sha256
        long_state = numerical.reset()
        long_state, _ = long_state.consume("sense", "pulse-a")
        long_state, _ = long_state.consume("release", "requested")
        for _ in range(4096):
            long_state, _ = long_state.consume("idle", "quiet")
        require(long_state.memory_sha256 == model_before and long_state.nbytes == numerical.nbytes, "long horizon grew learned state")
        require(long_state.predict("move")["probabilities"].get("blocked", 0.0) > 0.5,
                "long horizon forgot unconfirmed request")
        source_ids = numerical.source_revision_ids
        snapshot = session.owner.state.encode_bundle()
        bundle_file = home.parent / f"owner-{seed}.bundle.json"
        bundle_file.write_bytes(snapshot)
        before_invalid = session.owner.state.state_sha256
        events_before_invalid = session.owner.evidence.event_count
        invalid_source = source_for(seed, "invalid", [{"action": "not-a-codec-action", "observation": "quiet"}])
        try:
            session.owner.learn_temporal(session.op(), memory_id=MEMORY, source=invalid_source)
        except FieldIntelligenceError:
            pass
        else:
            raise RuntimeError("invalid temporal evidence was accepted")
        require(session.owner.state.state_sha256 == before_invalid and session.owner.evidence.event_count == events_before_invalid,
                "invalid admission changed field or evidence")
        result = {
            "seed": seed, "training": session.training, "normal_before_context": normal_before,
            "unseen_context_before_learning": early, "heldout": final,
            "scores": {"normal_before": summarize(normal_before), "novel_context_before": summarize(early), "final": summarize(final)},
            "states_before_context": states_before, "states_after_context": numerical.state_count,
            "restart": restart, "skills": skill_runs, "unexpected_outcome": interrupted,
            "memory_interventions": interventions,
            "retention": {"chart_sha256": retained["chart_sha256"], "before": retained["predictions"], "after": final_retained,
                          "memory_unchanged": True, "predictions_exact": True},
            "long_horizon": {"steps": 4096, "bounded_bytes": long_state.nbytes, "memory_unchanged": True,
                             "prediction": long_state.predict("move")},
            "invalid_admission_atomic": True, "field_bytes": numerical.nbytes,
            "active_closure_bytes": session.owner.state.closure_bytes,
            "source_count": len(source_ids), "model_sha256": numerical.memory_sha256,
            "bundle": str(bundle_file), "bundle_sha256": sha256_value(json.loads(snapshot)),
            "costs": session.costs, "elapsed_seconds": time.perf_counter() - started,
            "live_model_calls": 0,
        }
        require(result["scores"]["final"]["accuracy"] == 1.0, "held-out causal histories were not distinguished")
        old_manifest = session.owner.checkpoints.current_manifest_sha256
        preview = session.owner.preview_forget((source_ids[0],))
        require(MEMORY in preview["binding"]["affected_temporal_ids"], "forget preview omitted affected learned memory")
        session.owner.forget(
            operation_id=session.op(), preview_id=preview["preview_id"], revision_ids=(source_ids[0],),
            grant=AuthorityGrant(grant_id=f"revoke:{seed}", issuer="sandbox", generation=session.owner.authority_generation,
                                 operation="forget", target=sha256_value(sorted((source_ids[0],))), scope="temporal-development"),
            scope="temporal-development",
        )
        revoked = session.owner.inspect_temporal(MEMORY, action="move", skill_id="relocate")
        require(not revoked["prediction"]["supported"] and revoked["skill"]["status"] == "unresolved",
                "revoked temporal memory retained executable learned behavior")
        try:
            session.owner.checkpoints.load_version(old_manifest)
        except FieldIntelligenceError as exc:
            require(exc.code == "STALE_REVOCATION", "revoked checkpoint raised wrong error")
        else:
            raise RuntimeError("historical checkpoint revived revoked temporal memory")
        try:
            session.owner.export_bundle(old_manifest)
        except FieldIntelligenceError as exc:
            require(exc.code == "STALE_REVOCATION", "revoked export raised wrong error")
        else:
            raise RuntimeError("historical bundle exported revoked temporal memory")
        require(instrument_predictions(session) == retained["predictions"], "temporal revocation altered unrelated knowledge")
        result["revocation"] = {"preview_identified_memory": True, "execution_removed": True,
                                "stale_checkpoint_refused": True, "stale_export_refused": True,
                                "unrelated_memory_preserved": True}
        return result
    finally:
        session.owner.close()


def main() -> int:
    torch.set_num_threads(1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[101, 202, 303])
    args = parser.parse_args()
    if args.data_home.exists():
        parser.error("data home must be a new isolated directory")
    args.data_home.mkdir(parents=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    runs = []
    for seed in args.seeds:
        print(f"Running temporal development seed {seed}", flush=True)
        result = run_seed(args.data_home / f"seed-{seed}", seed)
        runs.append(result)
        args.output.write_bytes(canonical_json_bytes({"schema": "cassifi.temporal-development.v1", "runs": runs}))
        print(json.dumps({"seed": seed, "scores": result["scores"], "seconds": result["elapsed_seconds"]}), flush=True)
    print(json.dumps({"completed_seeds": len(runs), "live_model_calls": 0, "report": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
