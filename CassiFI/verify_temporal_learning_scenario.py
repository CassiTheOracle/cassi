"""Independently verify a CassiFI temporal learn-during-use report.

This verifier intentionally imports no CassiFI runtime module.  It reconstructs
simulator observations, field payload hashes, source revision chains, report
metrics, and the durable checkpoint closure from standard-library code.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, cast


SCHEMA = "cassifi.temporal-active-learning.v2"
AUTONOMOUS_SCHEMA = "cassifi.temporal-autonomous-learning.v1"
AUTONOMOUS_ACTIONS = ("probe", "read", "inspect", "idle", "clear", "wait")
AUTONOMOUS_PARTICIPANTS = 8
ARMS = ("online", "oracle", "frozen")
GUIDED_ACTIONS = (
    "inspect", "idle", "read", "probe", "read", "inspect",
    "probe", "read", "clear", "release", "wait", "wait",
)
TRANSFER_MODES = ((True, True), (True, False))
LAYERS = 9
FLOAT64_BYTES = 8


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_value(value: Any) -> str:
    return digest_bytes(canonical(value))

@dataclass
class Mechanism:
    jammed: bool
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
        raise AssertionError(f"unknown simulator action {action!r}")
def verify_field(
    field: Mapping[str, Any],
    expected_numeric_sha256: str,
    expected_participants: int = 5,
) -> bytes:
    require(field.get("schema") == "cassifi.temporal-field.v1", "field schema mismatch")
    require(field.get("memory_id") == "mechanism-type", "field memory id mismatch")
    require(field.get("max_states") == 64, "unexpected temporal state capacity")
    require(isinstance(field.get("action_ids"), list), "missing action ids")
    require(isinstance(field.get("observation_ids"), list), "missing observation ids")
    require(isinstance(field.get("participant_ids"), list), "participant layout is missing")
    max_states = cast(int, field["max_states"])
    actions = cast(list[str], field["action_ids"])
    observations = cast(list[str], field["observation_ids"])
    participants = cast(list[str], field["participant_ids"])
    require(len(actions) > 0, "action ids are empty")
    require(len(observations) > 0, "observation ids are empty")
    require(len(participants) == expected_participants, "participant layout mismatch")
    payload = base64.b64decode(field["field_b64"], validate=True)
    lane_width = len(actions) * len(observations)
    shared_bytes = LAYERS * max_states * lane_width * FLOAT64_BYTES
    expected_bytes = (1 + len(participants)) * shared_bytes
    require(len(payload) == expected_bytes, "temporal field payload length mismatch")
    require(digest_bytes(payload[:shared_bytes]) == expected_numeric_sha256,
            "reported learned numeric hash mismatch")
    return payload[:shared_bytes]


def replay_guided(demonstration: Mapping[str, Any]) -> None:
    require(isinstance(demonstration.get("steps"), list), "guided steps are missing")
    require(isinstance(demonstration.get("records"), list), "guided records are missing")
    steps = cast(list[Mapping[str, Any]], demonstration["steps"])
    records = cast(list[Mapping[str, Any]], demonstration["records"])
    require(demonstration.get("completed") is True, "guided use not marked complete")
    require(len(steps) == len(GUIDED_ACTIONS), "guided use length mismatch")
    require(len(records) == len(steps), "guided record count mismatch")
    mechanism = Mechanism(jammed=True)
    for tick, (action, step, record) in enumerate(zip(GUIDED_ACTIONS, steps, records, strict=True)):
        require(step.get("action") == action, "guided action sequence changed")
        observation = mechanism.step(action)
        require(step.get("observation") == observation, "guided observation replay mismatch")
        require(record.get("tick") == tick and record.get("action") == action,
                "guided record identity mismatch")
        require(record.get("observation") == observation,
                "guided record observation mismatch")
    require(not mechanism.latched, "guided replay did not release mechanism")


def verify_source_artifacts(
    sources: Sequence[Mapping[str, Any]],
    home: Path,
) -> dict[str, list[Mapping[str, Any]]]:
    """Reconstruct content-addressed episode sources and their revision chains."""
    by_chain: dict[str, list[Mapping[str, Any]]] = {}
    for source in sources:
        steps = source["steps"]
        delta = source["delta_steps"]
        require(source["episode_sha256"] == digest_value(steps),
                "episode content digest mismatch")
        require(source["receipt"]["observation_count"] == len(delta),
                "source receipt observation count mismatch")
        require(source["receipt"]["source_revision_id"] == source["source_revision_id"],
                "source revision receipt mismatch")
        source_file = home / "evidence" / "sources" / source["source_revision_id"]
        require(source_file.is_file(), "persisted source revision is missing")
        source_row = json.loads(source_file.read_bytes())
        require(source_row["revision_id"] == source["source_revision_id"],
                "persisted source revision identity mismatch")
        require(source_row["source_id"] == source["source_id"],
                "persisted source chain identity mismatch")
        require(source_row["parent_revision_id"] == source["parent_revision_id"],
                "persisted source parent mismatch")
        blob = home / "evidence" / "blobs" / source_row["object_sha256"]
        require(blob.is_file(), "persisted source blob is missing")
        content = blob.read_bytes()
        require(digest_bytes(content) == source_row["content_sha256"],
                "persisted source blob digest mismatch")
        episode = json.loads(content)
        require(episode == {"schema": "cassifi.temporal-episode.v1", "steps": steps},
                "persisted source content mismatch")
        by_chain.setdefault(source["source_id"], []).append(source)
    return by_chain


def verify_sources(run: Mapping[str, Any], home: Path) -> tuple[int, int]:
    arm = cast(str, run["arm"])
    require(isinstance(run.get("sources"), list), "sources are missing")
    sources = cast(list[Mapping[str, Any]], run["sources"])
    guided = [row for row in sources if ":guided-" in row["source_id"]]
    bootstrap = [row for row in sources if ":guided-" not in row["source_id"]]
    require(len(bootstrap) == 6, "normal bootstrap source count mismatch")
    expected_guided_revisions = {"online": 36, "oracle": 3, "frozen": 0}[arm]
    require(len(guided) == expected_guided_revisions,
            "guided admission revision count mismatch")

    by_chain = verify_source_artifacts(sources, home)

    guided_chains = {key: rows for key, rows in by_chain.items() if ":guided-" in key}
    expected_heads = 0 if arm == "frozen" else 3
    require(len(guided_chains) == expected_heads, "guided source-head count mismatch")
    for source_id, chain in guided_chains.items():
        prior_revision = None
        prior_steps: list[Mapping[str, str]] = []
        for index, row in enumerate(chain):
            require(row["parent_revision_id"] == prior_revision,
                    "source revision chain is discontinuous")
            require(row["steps"][:len(prior_steps)] == prior_steps,
                    "source revision did not extend its prefix")
            require(row["delta_steps"] == row["steps"][len(prior_steps):],
                    "source delta does not match appended observations")
            if arm == "online":
                require(len(row["steps"]) == index + 1 and len(row["delta_steps"]) == 1,
                        "online source was not admitted observation by observation")
            else:
                require(len(row["steps"]) == len(GUIDED_ACTIONS),
                        "oracle source is not a complete guided episode")
            prior_steps = row["steps"]
            prior_revision = row["source_revision_id"]
        require(run["source_heads"][source_id] == prior_revision,
                "reported source head mismatch")
        require(run["source_prefixes"][source_id] == prior_steps,
                "reported active source prefix mismatch")
    return len(guided), len(guided_chains)


def verify_autonomous_sources(run: Mapping[str, Any], home: Path) -> tuple[int, int]:
    arm = cast(str, run["arm"])
    require(isinstance(run.get("sources"), list), "sources are missing")
    sources = cast(list[Mapping[str, Any]], run["sources"])
    acquisition = [row for row in sources if ":autonomous-" in row["source_id"]]
    bootstrap = [row for row in sources if ":autonomous-" not in row["source_id"]]
    require(len(bootstrap) == 6, "normal bootstrap source count mismatch")
    expected = 0 if arm == "frozen" else 3
    require(len(acquisition) == expected, "autonomous source revision count mismatch")
    by_chain = verify_source_artifacts(sources, home)
    chains = {key: rows for key, rows in by_chain.items() if ":autonomous-" in key}
    require(len(chains) == expected, "autonomous source-head count mismatch")
    for source_id, chain in chains.items():
        require(len(chain) == 1, "autonomous segment has multiple admission revisions")
        row = chain[0]
        require(row["parent_revision_id"] is None,
                "autonomous segment unexpectedly extends an earlier source")
        require(row["delta_steps"] == row["steps"],
                "autonomous segment delta differs from its episode")
        require(run["source_heads"][source_id] == row["source_revision_id"],
                "reported autonomous source head mismatch")
        require(run["source_prefixes"][source_id] == row["steps"],
                "reported autonomous source prefix mismatch")
    return len(acquisition), len(chains)


def replay_transfer(
    trial: Mapping[str, Any],
    modes: Sequence[bool],
    participants: Sequence[str] = ("left", "right"),
) -> None:
    require(trial.get("evaluation_modes") == list(modes), "transfer mode mismatch")
    require(trial.get("state_count_before_admission") == trial.get("state_count_after_admission"),
            "transfer scoring admitted an episode")
    for record in trial.get("records", []):
        require("online_learning" not in record, "transfer record contains online admission")
    require(isinstance(trial.get("source_episodes"), Mapping),
            "transfer source episodes are missing")
    source_episodes = cast(
        Mapping[str, Sequence[Mapping[str, str]]],
        trial["source_episodes"],
    )
    require(set(source_episodes) == set(participants), "transfer participant set mismatch")
    freed = True
    for participant, jammed in zip(participants, modes, strict=True):
        mechanism = Mechanism(jammed=jammed)
        for step in source_episodes[participant]:
            require(mechanism.step(step["action"]) == step["observation"],
                    "transfer simulator replay mismatch")
        freed = freed and not mechanism.latched
    require(trial.get("load_freed") is freed, "reported transfer world state mismatch")
    require(trial.get("completed") is freed, "task completion does not match world completion")
    require(isinstance(trial.get("final_task"), Mapping), "final task view missing")
    final = cast(Mapping[str, Any], trial["final_task"])
    require((final.get("status") == "complete") is freed,
            "final task status does not match replay")


def verify_checkpoint(run: Mapping[str, Any], home: Path) -> int:
    field_root = home / "field"
    current = (field_root / "CURRENT").read_text(encoding="ascii").strip()
    require(len(current) == 64, "CURRENT checkpoint digest is malformed")
    seen: set[str] = set()
    cursor: str | None = current
    while cursor is not None:
        require(cursor not in seen, "checkpoint manifest chain contains a cycle")
        seen.add(cursor)
        manifest_path = field_root / "manifests" / cursor
        payload = manifest_path.read_bytes()
        require(digest_bytes(payload) == cursor, "checkpoint manifest digest mismatch")
        manifest = json.loads(payload)
        descriptor_sha = manifest["state_descriptor_sha256"]
        descriptor_path = field_root / "objects" / descriptor_sha
        descriptor_payload = descriptor_path.read_bytes()
        require(digest_bytes(descriptor_payload) == descriptor_sha,
                "state descriptor digest mismatch")
        descriptor = json.loads(descriptor_payload)
        require(descriptor["state_sha256"] == manifest["state_sha256"],
                "manifest state identity mismatch")
        for page_sha in descriptor["pages"]:
            page = field_root / "objects" / page_sha
            require(page.is_file() and digest_bytes(page.read_bytes()) == page_sha,
                    "checkpoint page digest mismatch")
        cursor = manifest["parent_manifest_sha256"]
    current_manifest = json.loads((field_root / "manifests" / current).read_bytes())
    require(current_manifest["state_sha256"] == run["restart"]["state_sha256"],
            "final durable state differs from restart receipt")
    require(run["restart"]["exact_closure"] is True, "exact restart closure not reported")
    return len(seen)


def verify_run(run: Mapping[str, Any], data_home: Path) -> Mapping[str, Any]:
    require(isinstance(run.get("arm"), str), "run arm is invalid")
    require(isinstance(run.get("seed"), int), "run seed is invalid")
    arm = cast(str, run["arm"])
    seed = cast(int, run["seed"])
    require(arm in ARMS, "run arm is unknown")
    home = data_home / f"seed-{seed}" / arm
    require(home.is_dir(), "run data home is missing")
    require(isinstance(run.get("demonstrations"), list), "guided uses are missing")
    demonstrations = cast(list[Mapping[str, Any]], run["demonstrations"])
    require(len(demonstrations) == 3, "guided-use count mismatch")
    for index, demonstration in enumerate(demonstrations):
        require(demonstration.get("demonstration") == index,
                "guided-use order mismatch")
        replay_guided(demonstration)
        learning_records = sum("learning" in row for row in demonstration["records"])
        expected = {"online": 12, "oracle": 1, "frozen": 0}[arm]
        require(learning_records == expected, "guided learning receipt count mismatch")
        require(
            demonstration["memory_changed"] is (arm != "frozen"),
            "guided-use memory-change flag mismatch",
        )

    metrics = cast(Mapping[str, Any], run["metrics"])
    initial_shared = verify_field(run["initial_field"], metrics["initial_numeric_sha256"])
    trained_shared = verify_field(run["trained_field"], metrics["trained_numeric_sha256"])
    final_shared = verify_field(run["final_field"], metrics["trained_numeric_sha256"])
    require(final_shared == trained_shared, "learned field changed during transfer scoring")
    require(
        run["final_field"]["memory_sha256"] == run["trained_field"]["memory_sha256"],
        "learned memory digest changed during transfer scoring",
    )
    if arm == "frozen":
        require(initial_shared == trained_shared and metrics["learned_from_use"] is False,
                "frozen arm retained guided experience")
    else:
        require(initial_shared != trained_shared and metrics["learned_from_use"] is True,
                "learning arm did not retain guided experience")
    require(
        (run["trained_field"]["memory_sha256"] == run["initial_field"]["memory_sha256"])
        is (arm == "frozen"),
        "learned memory digest does not match arm behavior",
    )

    revisions, heads = verify_sources(run, home)
    require(isinstance(run.get("transfer_trials"), list), "transfer trials are missing")
    trials = cast(list[Mapping[str, Any]], run["transfer_trials"])
    require(trials == run.get("trials"), "transfer trial aliases differ")
    require(len(trials) == len(TRANSFER_MODES), "transfer trial count mismatch")
    for trial, modes in zip(trials, TRANSFER_MODES, strict=True):
        replay_transfer(trial, modes)
    completed = sum(bool(row["completed"]) for row in trials)
    require(completed == (0 if arm == "frozen" else 2), "transfer outcome mismatch")
    records = [
        record
        for trial in trials
        for record in trial["records"]
        if "prediction" in record
    ]
    answered = [
        record for record in records
        if record["prediction"]["supported"]
    ]
    correct = sum(
        max(
            record["prediction"]["probabilities"],
            key=record["prediction"]["probabilities"].get,
        ) == record["observation"]
        for record in answered
    )
    require(metrics["completed"] == completed and metrics["total"] == len(trials),
            "reported completion metrics mismatch")
    require(metrics["guided_uses_observed"] == 3 and metrics["guided_observations"] == 36,
            "reported acquisition metrics mismatch")
    require(metrics["guided_admission_revisions"] == revisions,
            "reported revision metric mismatch")
    require(metrics["retained_guided_source_heads"] == heads,
            "reported source-head metric mismatch")
    require(metrics["interactions"] == sum(row["interactions"] for row in trials),
            "reported interaction metric mismatch")
    require(metrics["diagnostic_interactions"] == sum(row["diagnostic_interactions"] for row in trials),
            "reported diagnostic metric mismatch")
    require(metrics["support_gap_observations"] == sum(row["support_gap_observations"] for row in trials),
            "reported support-gap metric mismatch")
    require(metrics["predictions"] == len(records), "reported prediction count mismatch")
    require(metrics["answered"] == len(answered), "reported answered count mismatch")
    require(metrics["correct"] == correct, "reported prediction correctness mismatch")
    require(
        metrics["context_recoveries"]
        == sum(row["context_recoveries"] for row in trials),
        "reported context-recovery metric mismatch",
    )
    require(
        metrics["recovery_sequences"]
        == sum(row["recovery_sequences"] for row in trials),
        "reported recovery-sequence metric mismatch",
    )
    require(metrics["unsafe_observations"] == 0, "unsafe outcome occurred")
    require(run.get("live_model_calls") == 0, "live model call count is nonzero")
    require(run["retention"]["unrelated_exact"] is True,
            "unrelated-memory retention is not exact")
    require(run["retention"]["memory_stable_during_transfer"] is True,
            "transfer memory stability is not reported")
    manifests = verify_checkpoint(run, home)
    return {
        "seed": seed,
        "arm": arm,
        "completed": completed,
        "guided_revisions": revisions,
        "guided_heads": heads,
        "checkpoint_manifests": manifests,
        "initial_numeric_sha256": metrics["initial_numeric_sha256"],
        "numeric_sha256": metrics["trained_numeric_sha256"],
    }


def replay_acquisition_segment(
    segment: Mapping[str, Any],
    episode: int,
    arm: str,
) -> None:
    require(segment.get("episode") == episode, "acquisition segment order mismatch")
    require(segment.get("participant_id") == f"acquire-{episode}",
            "acquisition participant mismatch")
    require(isinstance(segment.get("steps"), list), "acquisition steps are missing")
    steps = cast(list[Mapping[str, str]], segment["steps"])
    require(len(steps) >= 2, "acquisition segment is empty")
    mechanism = Mechanism(jammed=True)
    for step in steps:
        require(mechanism.step(step["action"]) == step["observation"],
                "acquisition simulator replay mismatch")
        require(step["observation"] not in {"fault", "blocked"},
                "acquisition reached an unsafe outcome")
    require(segment.get("completed") is (not mechanism.latched),
            "acquisition completion does not match simulator replay")
    require(segment.get("field_selected") is (arm == "online"),
            "acquisition selection provenance mismatch")
    learning = segment.get("learning")
    require(isinstance(learning, Mapping) is (arm != "frozen"),
            "acquisition admission receipt mismatch")
    if isinstance(learning, Mapping):
        require(learning.get("observation_count") == len(steps),
                "acquisition admission observation count mismatch")
    require(isinstance(segment.get("records"), list), "acquisition records are missing")
    records = cast(list[Mapping[str, Any]], segment["records"])
    if arm == "online":
        require(steps[0] == {"action": "inspect", "observation": "closed"},
                "field-selected segment lacks its initial real observation")
        record_steps = [
            {"action": record["action"], "observation": record["observation"]}
            for record in records if record.get("action") is not None
        ]
        require(record_steps == steps[1:],
                "field-selected records do not reconstruct the admitted episode")
        require(any(record.get("kind") == "inquiry" for record in records),
                "field-selected segment contains no inquiry decision")
        for record in records:
            if record.get("kind") == "inquiry" and record.get("action") is not None:
                require(isinstance(record.get("inquiry"), Mapping),
                        "field-selected action lacks an inquiry receipt")
                require(record["action"] == record["inquiry"].get("action"),
                        "executed acquisition action differs from inquiry selection")
                require(record["action"] in AUTONOMOUS_ACTIONS,
                        "field-selected inquiry escaped the permitted surface")
    else:
        replay_steps = [
            {"action": record["action"], "observation": record["observation"]}
            for record in records
        ]
        require(replay_steps == steps, "control replay records differ from source exposure")


def verify_autonomous_run(
    run: Mapping[str, Any],
    data_home: Path,
) -> Mapping[str, Any]:
    require(isinstance(run.get("arm"), str), "run arm is invalid")
    require(isinstance(run.get("seed"), int), "run seed is invalid")
    arm = cast(str, run["arm"])
    seed = cast(int, run["seed"])
    require(arm in ARMS, "run arm is unknown")
    home = data_home / f"seed-{seed}" / arm
    require(home.is_dir(), "run data home is missing")
    require(isinstance(run.get("acquisitions"), list), "acquisition segments are missing")
    acquisitions = cast(list[Mapping[str, Any]], run["acquisitions"])
    require(len(acquisitions) == 3, "acquisition segment count mismatch")
    for episode, segment in enumerate(acquisitions):
        replay_acquisition_segment(segment, episode, arm)
    curve = [bool(segment["completed"]) for segment in acquisitions]
    require(curve == [False, True, True], "autonomous acquisition curve mismatch")

    metrics = cast(Mapping[str, Any], run["metrics"])
    initial_shared = verify_field(
        run["initial_field"],
        metrics["initial_numeric_sha256"],
        AUTONOMOUS_PARTICIPANTS,
    )
    trained_shared = verify_field(
        run["trained_field"],
        metrics["trained_numeric_sha256"],
        AUTONOMOUS_PARTICIPANTS,
    )
    final_shared = verify_field(
        run["final_field"],
        metrics["trained_numeric_sha256"],
        AUTONOMOUS_PARTICIPANTS,
    )
    require(final_shared == trained_shared, "learned field changed during transfer scoring")
    require(
        run["final_field"]["memory_sha256"] == run["trained_field"]["memory_sha256"],
        "learned memory digest changed during transfer scoring",
    )
    if arm == "frozen":
        require(initial_shared == trained_shared
                and metrics["learned_from_autonomous_use"] is False,
                "frozen arm retained autonomous observations")
    else:
        require(initial_shared != trained_shared
                and metrics["learned_from_autonomous_use"] is True,
                "learning arm did not retain autonomous observations")

    revisions, heads = verify_autonomous_sources(run, home)
    require(isinstance(run.get("acquisition_counterfactual"), Mapping),
            "matched acquisition counterfactual is missing")
    counterfactual = cast(Mapping[str, Any], run["acquisition_counterfactual"])
    replay_transfer(
        counterfactual,
        (True,),
        ("acquisition-counterfactual",),
    )
    counterfactual_completed = bool(counterfactual["completed"])
    require(counterfactual_completed is (arm != "frozen"),
            "matched post-admission acquisition result mismatch")

    require(isinstance(run.get("transfer_trials"), list), "transfer trials are missing")
    trials = cast(list[Mapping[str, Any]], run["transfer_trials"])
    require(len(trials) == len(TRANSFER_MODES), "transfer trial count mismatch")
    for index, (trial, modes) in enumerate(zip(trials, TRANSFER_MODES, strict=True)):
        replay_transfer(
            trial,
            modes,
            (f"transfer-{index}-left", f"transfer-{index}-right"),
        )
    completed = sum(bool(row["completed"]) for row in trials)
    require(completed == (0 if arm == "frozen" else 2), "transfer outcome mismatch")
    records = [
        record
        for trial in trials
        for record in trial["records"]
        if "prediction" in record
    ]
    answered = [record for record in records if record["prediction"]["supported"]]
    correct = sum(
        max(
            record["prediction"]["probabilities"],
            key=record["prediction"]["probabilities"].get,
        ) == record["observation"]
        for record in answered
    )
    require(metrics["acquisition_segments"] == len(acquisitions),
            "reported acquisition segment count mismatch")
    require(metrics["acquisition_curve"] == curve,
            "reported acquisition curve mismatch")
    require(
        metrics["acquisition_interactions"]
        == sum(segment["interactions"] for segment in acquisitions),
        "reported acquisition interaction count mismatch",
    )
    require(metrics["autonomous_source_revisions"] == revisions,
            "reported autonomous source revision count mismatch")
    require(metrics["autonomous_source_heads"] == heads,
            "reported autonomous source-head count mismatch")
    require(
        metrics["post_admission_counterfactual_completed"]
        is counterfactual_completed,
        "reported acquisition counterfactual result mismatch",
    )
    require(
        metrics["post_admission_counterfactual_interactions"]
        == counterfactual["interactions"],
        "reported acquisition counterfactual interaction count mismatch",
    )
    require(metrics["completed"] == completed and metrics["total"] == len(trials),
            "reported transfer completion metrics mismatch")
    require(metrics["interactions"] == sum(row["interactions"] for row in trials),
            "reported transfer interaction metric mismatch")
    require(
        metrics["diagnostic_interactions"]
        == sum(row["diagnostic_interactions"] for row in trials),
        "reported diagnostic metric mismatch",
    )
    require(
        metrics["support_gap_observations"]
        == sum(row["support_gap_observations"] for row in trials),
        "reported support-gap metric mismatch",
    )
    require(metrics["predictions"] == len(records), "reported prediction count mismatch")
    require(metrics["answered"] == len(answered), "reported answered count mismatch")
    require(metrics["correct"] == correct, "reported correctness count mismatch")
    require(
        metrics["context_recoveries"]
        == sum(row["context_recoveries"] for row in trials),
        "reported context-recovery metric mismatch",
    )
    require(
        metrics["recovery_sequences"]
        == sum(row["recovery_sequences"] for row in trials),
        "reported recovery-sequence metric mismatch",
    )
    require(metrics["unsafe_observations"] == 0, "unsafe transfer outcome occurred")
    require(run.get("live_model_calls") == 0, "live model call count is nonzero")
    require(run["retention"]["unrelated_exact"] is True,
            "unrelated-memory retention is not exact")
    require(run["retention"]["memory_stable_during_transfer"] is True,
            "transfer memory stability is not reported")
    manifests = verify_checkpoint(run, home)
    return {
        "seed": seed,
        "arm": arm,
        "completed": completed,
        "counterfactual_completed": counterfactual_completed,
        "autonomous_revisions": revisions,
        "autonomous_heads": heads,
        "checkpoint_manifests": manifests,
        "initial_numeric_sha256": metrics["initial_numeric_sha256"],
        "numeric_sha256": metrics["trained_numeric_sha256"],
        "acquisition_sha256": digest_value(
            [segment["steps"] for segment in acquisitions]
        ),
    }


def verify_autonomous_report(
    report: Mapping[str, Any],
    report_bytes: bytes,
    data_home: Path,
    source: Path,
) -> Mapping[str, Any]:
    require(report.get("source_sha256") == digest_bytes(source.read_bytes()),
            "scenario source digest mismatch")
    configuration = cast(Mapping[str, Any], report.get("configuration"))
    require(configuration.get("arms") == list(ARMS), "arm configuration mismatch")
    require(configuration.get("acquisition_actions") == list(AUTONOMOUS_ACTIONS),
            "acquisition action configuration mismatch")
    require(configuration.get("acquisition_segments_per_arm") == 3,
            "acquisition segment configuration mismatch")
    require(configuration.get("acquisition_horizon") == 4,
            "acquisition horizon configuration mismatch")
    require(configuration.get("transfer_modes") == [list(row) for row in TRANSFER_MODES],
            "transfer configuration mismatch")
    require(configuration.get("transfer_admission_enabled") is False,
            "transfer scoring admission was enabled")
    seeds = configuration.get("seeds")
    runs = report.get("runs")
    require(isinstance(seeds, list) and isinstance(runs, list), "report runs are missing")
    seed_values = cast(list[int], seeds)
    run_values = cast(list[Mapping[str, Any]], runs)
    require(len(run_values) == len(seed_values) * len(ARMS), "run matrix is incomplete")
    require(
        {(run.get("seed"), run.get("arm")) for run in run_values}
        == {(seed, arm) for seed in seed_values for arm in ARMS},
        "run matrix identities differ from configuration",
    )
    verified = [verify_autonomous_run(run, data_home) for run in run_values]
    for seed in seed_values:
        rows = {row["arm"]: row for row in verified if row["seed"] == seed}
        require(
            len({row["initial_numeric_sha256"] for row in rows.values()}) == 1,
            "matched arms do not have identical initial learned fields",
        )
        require(
            len({row["acquisition_sha256"] for row in rows.values()}) == 1,
            "control arms did not replay identical autonomous observations",
        )
        require(rows["online"]["numeric_sha256"] == rows["oracle"]["numeric_sha256"],
                "online field differs from replay-oracle field")
        require(rows["online"]["counterfactual_completed"]
                and rows["oracle"]["counterfactual_completed"],
                "learned field did not solve the matched acquisition counterfactual")
        require(not rows["frozen"]["counterfactual_completed"],
                "frozen field solved the matched acquisition counterfactual")
        require(rows["online"]["completed"] == rows["oracle"]["completed"] == 2,
                "learning arms did not meet the transfer ceiling")
        require(rows["frozen"]["completed"] == 0,
                "frozen transfer counterfactual did not remain unresolved")
    return {
        "schema": "cassifi.temporal-autonomous-learning-verification.v1",
        "status": "PASS",
        "report_sha256": digest_bytes(report_bytes),
        "source_sha256": report["source_sha256"],
        "runs_verified": len(verified),
        "seeds_verified": seed_values,
        "completed_by_arm": {
            arm: sum(row["completed"] for row in verified if row["arm"] == arm)
            for arm in ARMS
        },
        "matched_acquisition_counterfactual_by_arm": {
            arm: sum(
                bool(row["counterfactual_completed"])
                for row in verified if row["arm"] == arm
            )
            for arm in ARMS
        },
        "autonomous_revisions_by_arm": {
            arm: sum(
                row["autonomous_revisions"]
                for row in verified if row["arm"] == arm
            )
            for arm in ARMS
        },
        "checkpoint_manifests_verified": sum(
            row["checkpoint_manifests"] for row in verified
        ),
        "checks": [
            "independent simulator replay",
            "field-selected acquisition action surface",
            "matched post-admission acquisition counterfactual",
            "identical acquisition exposure across controls",
            "replay-oracle learned-field equivalence",
            "frozen no-learning counterfactual",
            "admission-free transfer scoring",
            "shared learned-field payload hashes",
            "persisted evidence source blobs",
            "durable manifest ancestry and object hashes",
            "exact restart identity",
            "zero live model calls",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path("run_temporal_learning_scenario.py"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report_bytes = args.report.read_bytes()
    report = json.loads(report_bytes)
    if report.get("schema") == AUTONOMOUS_SCHEMA:
        autonomous = verify_autonomous_report(
            cast(Mapping[str, Any], report),
            report_bytes,
            args.data_home,
            args.source,
        )
        text = json.dumps(autonomous, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        print(text, end="")
        return 0
    require(report.get("schema") == SCHEMA, "report schema mismatch")
    require(report.get("source_sha256") == digest_bytes(args.source.read_bytes()),
            "scenario source digest mismatch")
    configuration = report.get("configuration")
    require(configuration.get("arms") == list(ARMS), "arm configuration mismatch")
    require(configuration.get("guided_actions") == list(GUIDED_ACTIONS),
            "guided action configuration mismatch")
    require(configuration.get("transfer_modes") == [list(row) for row in TRANSFER_MODES],
            "transfer configuration mismatch")
    require(configuration.get("transfer_admission_enabled") is False,
            "transfer scoring admission was enabled")
    seeds = configuration.get("seeds")
    runs = report.get("runs")
    require(isinstance(seeds, list) and isinstance(runs, list), "report runs are missing")
    require(len(runs) == len(seeds) * len(ARMS), "run matrix is incomplete")
    require({(run.get("seed"), run.get("arm")) for run in runs}
            == {(seed, arm) for seed in seeds for arm in ARMS},
            "run matrix identities differ from configuration")

    verified = [verify_run(run, args.data_home) for run in runs]
    for seed in seeds:
        rows = {row["arm"]: row for row in verified if row["seed"] == seed}
        require(
            len({row["initial_numeric_sha256"] for row in rows.values()}) == 1,
            "matched arms do not have identical initial learned fields",
        )
        require(rows["online"]["numeric_sha256"] == rows["oracle"]["numeric_sha256"],
                "online field differs from one-shot oracle field")
        require(rows["online"]["completed"] == rows["oracle"]["completed"] == 2,
                "learning arms did not meet the oracle transfer ceiling")
        require(rows["frozen"]["completed"] == 0,
                "frozen counterfactual did not remain unresolved")

    result = {
        "schema": "cassifi.temporal-active-learning-verification.v2",
        "status": "PASS",
        "report_sha256": digest_bytes(report_bytes),
        "source_sha256": report["source_sha256"],
        "runs_verified": len(verified),
        "seeds_verified": seeds,
        "completed_by_arm": {
            arm: sum(row["completed"] for row in verified if row["arm"] == arm)
            for arm in ARMS
        },
        "guided_revisions_by_arm": {
            arm: sum(row["guided_revisions"] for row in verified if row["arm"] == arm)
            for arm in ARMS
        },
        "checkpoint_manifests_verified": sum(
            row["checkpoint_manifests"] for row in verified
        ),
        "checks": [
            "independent simulator replay",
            "matched guided-use exposure",
            "observation-by-observation source revision chains",
            "one-shot oracle equivalence",
            "frozen no-learning counterfactual",
            "admission-free transfer scoring",
            "shared learned-field payload hashes",
            "persisted evidence source blobs",
            "durable manifest ancestry and object hashes",
            "exact restart identity",
            "zero live model calls",
        ],
    }
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
