#!/usr/bin/env python3
"""Exercise raw-event field acquisition in randomized controlled worlds."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence


from cassi_raw_event_field import (
    AcquisitionProfile,
    CapacityError,
    RawEvent,
    RawEventLearner,
    canonical_packet,
    encode_packet,
)
from cassi_raw_event_store import RawEventStore


SCHEMA = "cassi.raw-event-acquisition-scenario.v2"


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def packet(*spans: bytes, rng: random.Random | None = None) -> bytes:
    values = list(spans)
    if rng is not None:
        rng.shuffle(values)
    return encode_packet(tuple(values))


def same(left: bytes, right_hex: str | None) -> bool:
    return right_hex is not None and canonical_packet(left) == canonical_packet(
        bytes.fromhex(right_hex)
    )


class Driver:
    def __init__(self, learner: RawEventLearner, start: int = 1) -> None:
        self.learner = learner
        self.seq = start
        self.events: list[dict[str, Any]] = []

    def apply(
        self,
        kind: str,
        payload: bytes = b"",
        *,
        learn: bool = True,
        promote: bool = True,
    ) -> dict[str, Any]:
        event = RawEvent(self.seq, kind, payload)
        self.seq += 1
        receipt = self.learner.apply(event, learn=learn, promote=promote)
        self.events.append(
            {
                "event": event.to_dict(),
                "learn": learn,
                "promote": promote,
                "receipt": receipt,
            }
        )
        return receipt

    def relation(
        self,
        observation: bytes,
        action: bytes,
        outcome: bytes,
        *,
        repeats: int = 2,
    ) -> list[dict[str, Any]]:
        receipts: list[dict[str, Any]] = []
        for _ in range(repeats):
            self.apply("reset")
            self.apply("observation", observation)
            self.apply("action", action)
            receipts.append(self.apply("observation", outcome))
        return receipts

    def temporal_relation(
        self,
        start: bytes,
        prior_action: bytes,
        common: bytes,
        target_action: bytes,
        outcome: bytes,
        *,
        repeats: int = 2,
    ) -> None:
        for _ in range(repeats):
            self.apply("reset")
            self.apply("observation", start)
            self.apply("action", prior_action)
            self.apply("observation", common)
            self.apply("action", target_action)
            self.apply("observation", outcome)


def symbols(seed: int) -> dict[str, bytes]:
    rng = random.Random(seed)
    values = rng.sample(range(16, 240), 16)
    names = (
        "train_entity",
        "held_entity",
        "cold",
        "ready",
        "done",
        "op1",
        "op2",
        "novel",
        "pre_a",
        "pre_b",
        "prior_a",
        "prior_b",
        "common",
        "out_a",
        "out_b",
        "target",
    )
    return {name: bytes((value,)) for name, value in zip(names, values)}


def ordinary_case(seed: int) -> dict[str, Any]:
    rng = random.Random(seed ^ 0xC4551)
    value = symbols(seed)
    learner = RawEventLearner()
    driver = Driver(learner)
    train_cold = packet(value["train_entity"], value["cold"], rng=rng)
    train_ready = packet(value["train_entity"], value["ready"], rng=rng)
    train_done = packet(value["train_entity"], value["done"], rng=rng)
    held_cold = packet(value["held_entity"], value["cold"], rng=rng)
    held_ready = packet(value["held_entity"], value["ready"], rng=rng)
    held_done = packet(value["held_entity"], value["done"], rng=rng)
    op1 = packet(value["op1"])
    op2 = packet(value["op2"])
    novel = packet(value["novel"])

    before = learner.fingerprint()
    driver.relation(train_cold, op1, train_ready)
    midpoint = learner.fingerprint()
    driver.relation(train_ready, op2, train_done)
    after = learner.fingerprint()

    first = learner.predict(op1, observation=held_cold, history=None)
    second = learner.predict(op2, observation=held_ready, history=None)
    plan = learner.choose(
        (op2, novel, op1),
        held_done,
        observation=held_cold,
        history=None,
        max_depth=3,
        max_expansions=16,
    )
    unsupported = learner.predict(novel, observation=held_cold, history=None)
    require(same(held_ready, first["payload_hex"]), "held entity first transition failed")
    require(same(held_done, second["payload_hex"]), "held entity second transition failed")
    require(plan["status"] == "supported", "withheld composition was not found")
    require(plan["plan_hex"] == [op1.hex(), op2.hex()], "withheld plan is wrong")
    require(unsupported["status"] == "unresolved", "novel action was guessed")

    # Commit the plan in the actual world with learning disabled.  The world
    # state and transition truth remain outside the learner.
    driver.apply("reset", learn=False)
    driver.apply("observation", held_cold, learn=False)
    first_choice = learner.choose(
        (op2, novel, op1), held_done, history=None, max_expansions=16
    )
    require(first_choice["action_hex"] == op1.hex(), "first committed action is wrong")
    driver.apply("action", op1, learn=False)
    first_outcome = driver.apply("observation", held_ready, learn=False)
    require(not first_outcome["learned"], "inference outcome changed learned memory")
    second_choice = learner.choose(
        (novel, op2, op1), held_done, history=None, max_expansions=16
    )
    require(second_choice["action_hex"] == op2.hex(), "second committed action is wrong")
    driver.apply("action", op2, learn=False)
    driver.apply("observation", held_done, learn=False)
    require(learner.fingerprint() == after, "inference mutated learned field")

    erased, erase_receipt = learner.intervene("all_memory")
    targeted, targeted_receipt = learner.intervene(
        "relation", action=op1, observation=held_cold, history=None
    )
    targeted_prediction = targeted.predict(op1, observation=held_cold, history=None)
    unrelated_prediction = targeted.predict(op2, observation=held_ready, history=None)
    require(
        targeted_prediction["status"] == "unresolved",
        "targeted relation erase did not remove its acquired decision",
    )
    require(
        same(held_done, unrelated_prediction["payload_hex"]),
        "targeted relation erase damaged an unrelated acquired relation",
    )
    erased_prediction = erased.predict(op1, observation=held_cold, history=None)
    require(erased_prediction["status"] == "unresolved", "field erase did not remove decision")

    return {
        "seed": seed,
        "state_progression": [before, midpoint, after],
        "first_prediction": first,
        "second_prediction": second,
        "withheld_plan": plan,
        "unsupported_prediction": unsupported,
        "committed_choices": [first_choice, second_choice],
        "all_memory_intervention": erase_receipt,
        "erased_prediction": erased_prediction,
        "targeted_relation_intervention": targeted_receipt,
        "targeted_prediction": targeted_prediction,
        "unrelated_acquired_prediction": unrelated_prediction,
        "event_count": len(driver.events),
        "events": driver.events,
        "snapshot": learner.snapshot(),
    }


def temporal_case(seed: int) -> dict[str, Any]:
    rng = random.Random(seed ^ 0x7E4F0)
    value = symbols(seed)
    learner = RawEventLearner()
    driver = Driver(learner)
    entity = value["train_entity"]
    start_a = packet(entity, value["pre_a"], rng=rng)
    start_b = packet(entity, value["pre_b"], rng=rng)
    common = packet(entity, value["common"], rng=rng)
    outcome_a = packet(entity, value["out_a"], rng=rng)
    outcome_b = packet(entity, value["out_b"], rng=rng)
    prior_a = packet(value["prior_a"])
    prior_b = packet(value["prior_b"])
    target = packet(value["target"])
    driver.temporal_relation(start_a, prior_a, common, target, outcome_a)
    driver.temporal_relation(start_b, prior_b, common, target, outcome_b)
    prediction_a = learner.predict(
        target, observation=common, history=prior_a, dynamic=True
    )
    prediction_b = learner.predict(
        target, observation=common, history=prior_b, dynamic=True
    )
    no_history = learner.predict(target, observation=common, history=None)
    require(same(outcome_a, prediction_a["payload_hex"]), "temporal branch A failed")
    require(same(outcome_b, prediction_b["payload_hex"]), "temporal branch B failed")
    require(no_history["status"] == "unresolved", "history-free query guessed a branch")
    erased, erase_receipt = learner.intervene("history")
    erased_a = erased.predict(target, observation=common, history=prior_a)
    erased_b = erased.predict(target, observation=common, history=prior_b)
    require(erased_a["status"] == "unresolved", "history erase retained branch A")
    require(erased_b["status"] == "unresolved", "history erase retained branch B")
    return {
        "seed": seed,
        "prediction_a": prediction_a,
        "prediction_b": prediction_b,
        "without_history": no_history,
        "history_intervention": erase_receipt,
        "after_history_erase": [erased_a, erased_b],
        "event_count": len(driver.events),
        "snapshot": learner.snapshot(),
    }


def ambiguity_case(seed: int) -> dict[str, Any]:
    value = symbols(seed)
    learner = RawEventLearner()
    driver = Driver(learner)
    observation = packet(value["cold"])
    action = packet(value["op1"])
    outcome_a = packet(value["ready"])
    outcome_b = packet(value["done"])
    driver.relation(observation, action, outcome_a, repeats=1)
    driver.relation(observation, action, outcome_b, repeats=1)
    prediction = learner.predict(action, observation=observation, history=None)
    require(prediction["status"] == "unresolved", "symmetric outcomes were guessed")
    return {"seed": seed, "prediction": prediction, "snapshot": learner.snapshot()}



def promotion_control_case(seed: int) -> dict[str, Any]:
    """Contrast provisional-only learning with explicitly promoted learning."""

    value = symbols(seed)
    observation = packet(value["cold"])
    action = packet(value["op1"])
    outcome = packet(value["ready"])
    provisional = RawEventLearner()
    driver = Driver(provisional)
    receipts: list[dict[str, Any]] = []
    for _ in range(2):
        driver.apply("reset")
        driver.apply("observation", observation)
        driver.apply("action", action)
        receipts.append(driver.apply("observation", outcome, promote=False))
    require(
        all(not receipt["promoted"] for receipt in receipts),
        "provisional-only control unexpectedly promoted an outcome",
    )
    trained = provisional.fingerprint()
    static = provisional.predict(
        action, observation=observation, history=None, dynamic=False
    )
    dynamic = provisional.predict(
        action, observation=observation, history=None, dynamic=True
    )
    require(same(outcome, static["payload_hex"]), "static provisional read failed")
    require(same(outcome, dynamic["payload_hex"]), "dynamic provisional read failed")
    require(
        provisional.fingerprint() == trained,
        "static or dynamic inference mutated provisional memory",
    )

    no_consolidated, consolidated_receipt = provisional.intervene("consolidated")
    after_consolidated = no_consolidated.predict(
        action, observation=observation, history=None, dynamic=False
    )
    require(
        not consolidated_receipt["changed"],
        "provisional-only control contained consolidated field memory",
    )
    require(
        same(outcome, after_consolidated["payload_hex"]),
        "clearing empty consolidated banks changed provisional recall",
    )
    no_provisional, provisional_receipt = provisional.intervene("provisional")
    after_provisional = no_provisional.predict(
        action, observation=observation, history=None, dynamic=False
    )
    require(
        after_provisional["status"] == "unresolved",
        "provisional-only decision survived removal of provisional banks",
    )

    promoted = RawEventLearner()
    promoted_driver = Driver(promoted)
    promoted_receipts = promoted_driver.relation(observation, action, outcome)
    require(
        all(receipt["promoted"] for receipt in promoted_receipts),
        "explicit promotion did not enter the consolidated bank",
    )
    promoted_without_provisional, promoted_erase = promoted.intervene("provisional")
    promoted_after_erase = promoted_without_provisional.predict(
        action, observation=observation, history=None, dynamic=False
    )
    require(
        same(outcome, promoted_after_erase["payload_hex"]),
        "promoted decision did not survive provisional-bank removal",
    )
    return {
        "seed": seed,
        "provisional_receipts": receipts,
        "static_prediction": static,
        "dynamic_prediction": dynamic,
        "inference_preserved_state": provisional.fingerprint() == trained,
        "consolidated_intervention": consolidated_receipt,
        "after_consolidated_intervention": after_consolidated,
        "provisional_intervention": provisional_receipt,
        "after_provisional_intervention": after_provisional,
        "promoted_receipts": promoted_receipts,
        "promoted_provisional_intervention": promoted_erase,
        "promoted_after_provisional_intervention": promoted_after_erase,
        "snapshot": provisional.snapshot(),
    }

def restart_case(seed: int, root: Path) -> dict[str, Any]:
    value = symbols(seed)
    observation = packet(value["cold"])
    action = packet(value["op1"])
    outcome = packet(value["ready"])
    store_root = root / f"store-{seed}"
    with RawEventStore(store_root) as store:
        store.admit(RawEvent(1, "reset"))
        store.admit(RawEvent(2, "observation", observation))
        store.admit(RawEvent(3, "action", action))
        before = store.learner.fingerprint()
        first_prediction = store.learner.predict(action, observation=observation, history=None)
    with RawEventStore(store_root) as reopened:
        require(reopened.learner.fingerprint() == before, "restart changed field bytes")
        require(reopened.snapshot()["field"]["pending_action"], "pending action was not restored")
        outcome_receipt = reopened.admit(RawEvent(4, "observation", outcome))
        duplicate = reopened.admit(RawEvent(4, "observation", outcome))
        after = reopened.learner.fingerprint()
        require(duplicate["status"] == "duplicate", "identical retry was not deduplicated")
        snapshot = reopened.snapshot()
    with RawEventStore(store_root) as final:
        require(final.learner.fingerprint() == after, "second restart changed field bytes")
        learned = final.learner.predict(action, observation=observation, history=None)
    require(same(outcome, learned["payload_hex"]), "post-restart outcome was not learned")
    return {
        "seed": seed,
        "state_before_outcome": before,
        "state_after_outcome": after,
        "prediction_before_outcome": first_prediction,
        "outcome_receipt": outcome_receipt,
        "duplicate_receipt": duplicate,
        "post_restart_prediction": learned,
        "store_snapshot": snapshot,
    }


def revocation_case(seed: int, root: Path) -> dict[str, Any]:
    value = symbols(seed)
    observation = packet(value["cold"])
    action = packet(value["op1"])
    wrong = packet(value["out_a"])
    right = packet(value["ready"])
    store_root = root / f"revoke-{seed}"
    seq = 1
    with RawEventStore(store_root) as store:
        wrong_episode: list[int] = []
        for outcome in (wrong, right):
            for _ in range(2):
                for event in (
                    RawEvent(seq, "reset"),
                    RawEvent(seq + 1, "observation", observation),
                    RawEvent(seq + 2, "action", action),
                    RawEvent(seq + 3, "observation", outcome),
                ):
                    store.admit(event)
                    if outcome == wrong:
                        wrong_episode.append(event.seq)
                seq += 4
        before = store.learner.predict(action, observation=observation, history=None)
        revocations = [store.revoke(wrong_episode[0]), store.revoke(wrong_episode[4])]
        after = store.learner.predict(action, observation=observation, history=None)
        require(same(right, after["payload_hex"]), "revocation did not recover corrected relation")
        require(all(row["scope"] == "entire-reset-bounded-episode" for row in revocations), "revocation scope is wrong")
    return {
        "seed": seed,
        "before": before,
        "after": after,
        "revocations": revocations,
    }


def capacity_and_horizon_case(seed: int) -> dict[str, Any]:
    value = symbols(seed)
    constrained = RawEventLearner(AcquisitionProfile(energy_limit=1.0e-9))
    driver = Driver(constrained)
    observation = packet(value["cold"])
    action = packet(value["op1"])
    outcome = packet(value["ready"])
    driver.apply("observation", observation)
    driver.apply("action", action)
    predecessor = constrained.fingerprint()
    rejected = False
    try:
        driver.apply("observation", outcome)
    except CapacityError:
        rejected = True
    require(rejected, "energy capacity did not reject the update")
    require(constrained.fingerprint() == predecessor, "capacity rejection changed the field")

    learner = RawEventLearner()
    training = Driver(learner)
    training.relation(observation, action, outcome)
    trained = learner.fingerprint()
    for index in range(1024):
        learner.apply(RawEvent(10000 + index * 2, "reset"), learn=False)
        learner.apply(RawEvent(10001 + index * 2, "observation", observation), learn=False)
        prediction = learner.predict(action, history=None, dynamic=True)
        require(same(outcome, prediction["payload_hex"]), "long-horizon recall failed")
    snapshot = learner.snapshot()
    require(snapshot["all_finite"], "long-horizon field became non-finite")
    require(learner.fingerprint() == trained, "inference horizon mutated learned field")
    return {
        "seed": seed,
        "capacity_rejected": rejected,
        "capacity_predecessor_preserved": constrained.fingerprint() == predecessor,
        "inference_queries": 1024,
        "snapshot": snapshot,
    }


def run(seed_values: Sequence[int], out_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    ordinary = [ordinary_case(seed) for seed in seed_values]
    temporal = [temporal_case(seed) for seed in seed_values]
    ambiguity = [ambiguity_case(seed) for seed in seed_values]
    promotion_controls = [promotion_control_case(seed) for seed in seed_values]
    with tempfile.TemporaryDirectory(
        prefix=".raw-event-scenario-", dir=out_dir
    ) as scratch:
        scratch_root = Path(scratch)
        restart = [restart_case(seed, scratch_root) for seed in seed_values]
        revocation = [revocation_case(seed, scratch_root) for seed in seed_values]
    capacity = [capacity_and_horizon_case(seed) for seed in seed_values]
    snapshots = [
        row["snapshot"]
        for row in ordinary + temporal + ambiguity + promotion_controls + capacity
    ]
    receipt = {
        "schema": SCHEMA,
        "status": "PASS",
        "seeds": list(seed_values),
        "profile": AcquisitionProfile().as_dict(),
        "ordinary_composition": ordinary,
        "temporal_context": temporal,
        "ambiguity": ambiguity,
        "restart_exact_once": restart,
        "correction_revocation": revocation,
        "capacity_and_horizon": capacity,
        "promotion_and_readout_controls": promotion_controls,
        "aggregate": {
            "withheld_compositions_passed": sum(row["withheld_plan"]["status"] == "supported" for row in ordinary),
            "temporal_branches_passed": sum(row["prediction_a"]["status"] == "supported" and row["prediction_b"]["status"] == "supported" for row in temporal),
            "ambiguities_rejected": sum(row["prediction"]["status"] == "unresolved" for row in ambiguity),
            "restart_identities_passed": sum(row["duplicate_receipt"]["status"] == "duplicate" for row in restart),
            "revocations_passed": sum(row["after"]["status"] == "supported" for row in revocation),
            "capacity_rejections_passed": sum(row["capacity_rejected"] for row in capacity),
            "promotion_controls_passed": sum(
                row["after_provisional_intervention"]["status"] == "unresolved"
                and row["promoted_after_provisional_intervention"]["status"] == "supported"
                for row in promotion_controls
            ),
            "static_dynamic_controls_passed": sum(
                row["static_prediction"]["payload_hex"]
                == row["dynamic_prediction"]["payload_hex"]
                and row["inference_preserved_state"]
                for row in promotion_controls
            ),
            "targeted_relation_controls_passed": sum(
                row["targeted_prediction"]["status"] == "unresolved"
                and row["unrelated_acquired_prediction"]["status"] == "supported"
                for row in ordinary
            ),
            "long_horizon_queries": sum(row["inference_queries"] for row in capacity),
            "all_states_finite": all(row["all_finite"] for row in snapshots),
            "max_field_abs": max(row["max_abs"] for row in snapshots),
            "max_field_bytes": max(row["field_bytes"] for row in snapshots),
        },
        "ownership": {
            "adaptive_state": "QiFieldState.field [S,9M,B] only",
            "field_owned_committed_predictions": len(seed_values) * 4,
            "field_owned_plans": len(seed_values),
            "qwen_calls": 0,
            "teacher_calls": 0,
            "learned_sidecars": 0,
            "native_state_bytes_removed": 0,
            "native_ops_skipped": 0,
            "native_layers_skipped": 0,
            "native_output_rows_skipped": 0,
            "qwen_weight_bytes_touched_per_token": 0,
            "native_displacement_claim": "none; isolated field learner, not Qwen replacement",
            "fixed_machinery": [
                "opaque-packet framing",
                "unordered-span canonicalization",
                "single-changed-span copy binding",
                "fixed Qi chirp codebook",
                "bounded depth-first composition",
            ],
        },
        "limitations": [
            "The fixed copy-binding operator supplies the single-changed-span hypothesis; the field learns which transition it supports but did not discover the primitive.",
            "Packets are bounded to three spans, eight bytes per span, and sixteen encoded bytes.",
            "Compositional planning searches only caller-authorized actions and field-supported transitions.",
            "This experiment establishes controlled relational acquisition, not open-vocabulary language understanding.",
            "Static and dynamically evolved readouts are both fixed Qi views; neither is a Qwen comparator.",
        ],
        "elapsed_seconds": time.perf_counter() - started,
    }
    receipt["self_sha256"] = digest(receipt)
    (out_dir / "verification.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (out_dir / "events.jsonl").open("w", encoding="utf-8") as handle:
        for case in ordinary:
            for event in case["events"]:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir", type=Path, default=Path("_diag/raw-event-acquisition")
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=[101, 202, 303])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run(tuple(args.seeds), args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
