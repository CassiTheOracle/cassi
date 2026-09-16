"""Independently verify a CassiFI autonomous skill-formation report.

This verifier imports no CassiFI production module.  It replays the environment,
reconstructs source blobs and revision chains, checks checkpoint ancestry and
object hashes, independently decodes the persisted wave field, and recomputes
all published aggregate counts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

SCHEMA = "cassifi.temporal-autonomous-skill-formation.v3"
VERIFICATION_SCHEMA = "cassifi.temporal-autonomous-skill-formation-verification.v3"
EXPECTED_ACTIONS = ["prime", "align", "open"]
EXPECTED_OBSERVATIONS = ["primed", "aligned", "opened"]
FORBIDDEN = {"blocked", "misaligned"}
SKILL = "release-three-stage-latch"
EXPECTED_WORKSPACE_SCHEMA = "cassifi.resonant-workspace.v1"
EXPECTED_WORKSPACE_LAYOUT = "mode-major-9M-1:f64le:N=28:pools=7:ports=4"
EXPECTED_ADVANCE_SCHEMA = "cassifi.resonant-advance-receipt.v1"
EXPECTED_ADVANCE_ARITHMETIC = "numpy-matrix-free-float64"
EXPECTED_ADVANCE_INTEGRATION = "average-vector-field-discrete-gradient-v1"
EXPECTED_ZERO_CONTROL_LEDGER = {
    "balance_defect": 0.0,
    "boundary_work": 0.0,
    "dissipated_work": 0.0,
    "extracted_heartbeat_work": 0.0,
    "numerical_dissipated_work": 0.0,
    "parameter_work": 0.0,
    "positive_heartbeat_work": 0.0,
    "residual_work": 0.0,
    "stored_energy": 0.0,
}
EXPECTED_ZERO_CONTROL_RECEIPT = {
    "accepted": True,
    "arithmetic": EXPECTED_ADVANCE_ARITHMETIC,
    "balance_defect": 0.0,
    "boundary_work": 0.0,
    "dissipated_work": 0.0,
    "end_energy": 0.0,
    "evidence_tick": 5,
    "extracted_heartbeat_work": 0.0,
    "field_ticks": 8,
    "integration": EXPECTED_ADVANCE_INTEGRATION,
    "numerical_dissipated_work": 0.0,
    "parameter_work": 0.0,
    "positive_heartbeat_work": 0.0,
    "residual_work": 0.0,
    "schema": EXPECTED_ADVANCE_SCHEMA,
    "source_enabled": False,
    "start_energy": 0.0,
    "subdivisions": 0,
    "ticks": 8,
}
EXPECTED_RESONANT_PROFILE = {
    "activity_tau": 4.0,
    "arithmetic": "numpy-cpu-float64",
    "beta": 0.08,
    "coupling": 0.006,
    "damping": 0.012,
    "heartbeat_amplitude": 0.018,
    "heartbeat_frequency": 0.75,
    "heartbeat_work": 0.006,
    "integration": "average-vector-field-discrete-gradient-v1",
    "layout_identity": EXPECTED_WORKSPACE_LAYOUT,
    "max_subdivisions": 8,
    "pools": 7,
    "ports_per_pool": 4,
    "projected_inv_mass": None,
    "projected_quartic_weights": None,
    "projected_transport": None,
    "quiet_damping": 16.0,
    "relative_stiffness": 1.0,
    "time_step": 0.08,
    "tolerance": 2e-12,
    "topology": "meaningful-helix",
}



def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_value(value: Any) -> str:
    return digest_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii"))


class ThreeStageLatch:
    def __init__(self) -> None:
        self.primed = False
        self.aligned = False
        self.opened = False

    def step(self, action: str) -> str:
        if action == "prime":
            self.primed = True
            return "primed"
        if action == "align":
            if self.primed:
                self.aligned = True
                return "aligned"
            return "misaligned"
        if action == "open":
            if self.aligned:
                self.opened = True
                return "opened"
            return "blocked"
        raise AssertionError(f"unknown action in replay: {action}")


def replay(actions: Sequence[Any], observations: Sequence[Any], label: str) -> None:
    require(list(actions) == EXPECTED_ACTIONS, f"{label} action sequence mismatch")
    require(list(observations) == EXPECTED_OBSERVATIONS, f"{label} observation sequence mismatch")
    mechanism = ThreeStageLatch()
    for action, expected in zip(actions, observations, strict=True):
        require(isinstance(action, str), f"{label} action is not text")
        require(mechanism.step(action) == expected, f"{label} simulator replay mismatch")
    require(mechanism.opened, f"{label} replay did not complete")


def verify_skill_records(section: Mapping[str, Any], label: str) -> None:
    require(section.get("completed") is True, f"{label} is not complete")
    require(section.get("unsafe_observations") == 0, f"{label} reached an unsafe outcome")
    actions = cast(Sequence[Any], section.get("actions"))
    observations = cast(Sequence[Any], section.get("observations"))
    replay(actions, observations, label)
    raw_records = section.get("records")
    require(isinstance(raw_records, list) and len(raw_records) == 3, f"{label} record count mismatch")
    records = cast(list[Mapping[str, Any]], raw_records)
    for tick, (record, action, observation) in enumerate(zip(records, EXPECTED_ACTIONS, EXPECTED_OBSERVATIONS, strict=True)):
        require(isinstance(record, Mapping), f"{label} record is invalid")
        require(record.get("tick") == tick, f"{label} tick mismatch")
        require(record.get("goal_observations_supplied") is False, f"{label} received goal observations")
        require(record.get("observation") == observation, f"{label} record observation mismatch")
        raw_decision = record.get("decision")
        require(isinstance(raw_decision, Mapping), f"{label} skill decision is missing")
        decision = cast(Mapping[str, Any], raw_decision)
        require(decision.get("skill_id") == SKILL, f"{label} skill identity mismatch")
        require(decision.get("status") == "proposed", f"{label} skill was not proposed")
        require(decision.get("action") == action, f"{label} skill action mismatch")
        require(decision.get("remaining_steps") == 3 - tick, f"{label} remaining rank mismatch")
        require(decision.get("supported_states") == 1, f"{label} support count mismatch")


def verify_source_artifacts(sources: Sequence[Mapping[str, Any]], home: Path) -> dict[str, list[Mapping[str, Any]]]:
    by_chain: dict[str, list[Mapping[str, Any]]] = {}
    for source in sources:
        raw_steps = source.get("steps")
        raw_delta = source.get("delta_steps")
        require(isinstance(raw_steps, list) and isinstance(raw_delta, list), "source steps are invalid")
        steps = cast(list[Mapping[str, str]], raw_steps)
        delta = cast(list[Mapping[str, str]], raw_delta)
        require(source.get("episode_sha256") == digest_value(steps), "episode content digest mismatch")
        raw_receipt = source.get("receipt")
        require(isinstance(raw_receipt, Mapping), "source receipt is missing")
        receipt = cast(Mapping[str, Any], raw_receipt)
        require(receipt.get("observation_count") == len(delta), "source observation count mismatch")
        require(receipt.get("source_revision_id") == source.get("source_revision_id"), "source revision receipt mismatch")
        raw_event_id = receipt.get("event_id")
        require(
            isinstance(raw_event_id, str) and len(raw_event_id) == 64,
            "source evidence event id is malformed",
        )
        event_id = cast(str, raw_event_id)
        event_path = home / "evidence" / "events" / event_id
        require(event_path.is_file(), "persisted evidence event is missing")
        raw_event = json.loads(event_path.read_bytes())
        require(isinstance(raw_event, Mapping), "persisted evidence event is invalid")
        event = dict(cast(Mapping[str, Any], raw_event))
        require(
            set(event)
            == {
                "context",
                "derivation_roots",
                "epistemic_type",
                "event_id",
                "event_kind",
                "logical_sequence",
                "operation_id",
                "predecessor_state_sha256",
                "schema",
                "source_revision_id",
                "values",
            }
            and event.get("schema") == "cassifi.field-evidence-event.v1"
            and event.get("event_id") == event_id
            and event.get("source_revision_id") == source.get("source_revision_id"),
            "persisted evidence event identity or source binding is invalid",
        )
        event.pop("schema")
        event.pop("event_id")
        require(
            digest_value(event) == event_id,
            "persisted evidence event content digest mismatch",
        )
        raw_revision = source.get("source_revision_id")
        require(isinstance(raw_revision, str) and len(raw_revision) == 64, "source revision id is malformed")
        revision = cast(str, raw_revision)
        source_file = home / "evidence" / "sources" / revision
        require(source_file.is_file(), "persisted source revision is missing")
        source_row = cast(Mapping[str, Any], json.loads(source_file.read_bytes()))
        require(source_row.get("revision_id") == revision, "persisted source revision identity mismatch")
        require(source_row.get("source_id") == source.get("source_id"), "persisted source chain identity mismatch")
        require(source_row.get("parent_revision_id") == source.get("parent_revision_id"), "persisted source parent mismatch")
        raw_object_sha = source_row.get("object_sha256")
        require(isinstance(raw_object_sha, str) and len(raw_object_sha) == 64, "persisted source object id is malformed")
        object_sha = cast(str, raw_object_sha)
        blob = home / "evidence" / "blobs" / object_sha
        require(blob.is_file(), "persisted source blob is missing")
        content = blob.read_bytes()
        require(digest_bytes(content) == source_row.get("content_sha256"), "persisted source blob digest mismatch")
        require(json.loads(content) == {"schema": "cassifi.temporal-episode.v1", "steps": steps}, "persisted episode content mismatch")
        raw_source_id = source.get("source_id")
        require(isinstance(raw_source_id, str), "source chain id is invalid")
        source_id = cast(str, raw_source_id)
        by_chain.setdefault(source_id, []).append(source)
    return by_chain


def verify_sources(run: Mapping[str, Any], home: Path) -> int:
    raw = run.get("sources")
    require(isinstance(raw, list) and len(raw) == 5, "source revision count mismatch")
    sources = cast(list[Mapping[str, Any]], raw)
    by_chain = verify_source_artifacts(sources, home)
    discovery_id = run["discovery"]["source_id"]
    require(isinstance(discovery_id, str) and discovery_id in by_chain, "discovery source chain is missing")
    chain = by_chain[discovery_id]
    require(len(chain) == 3, "discovery source revision count mismatch")
    prior_revision = None
    prior_steps: list[Mapping[str, str]] = []
    for index, row in enumerate(chain):
        require(row.get("parent_revision_id") == prior_revision, "discovery source chain is discontinuous")
        steps = cast(list[Mapping[str, str]], row["steps"])
        require(steps[:len(prior_steps)] == prior_steps, "discovery source did not extend append-only")
        require(row.get("delta_steps") == steps[len(prior_steps):], "discovery source delta mismatch")
        require(len(steps) == index + 1 and len(cast(list[Any], row["delta_steps"])) == 1, "discovery was not admitted observation by observation")
        require(steps == [
            {"action": action, "observation": observation}
            for action, observation in zip(EXPECTED_ACTIONS[:index + 1], EXPECTED_OBSERVATIONS[:index + 1], strict=True)
        ], "discovery source prefix mismatch")
        prior_steps = steps
        prior_revision = cast(str, row["source_revision_id"])
    require(run["discovery"].get("source_revisions") == 3, "reported discovery revision count mismatch")
    require(run["discovery"].get("source_chain") == chain, "reported discovery source chain mismatch")

    background = [rows for key, rows in by_chain.items() if key != discovery_id]
    require(len(background) == 2 and all(len(rows) == 1 for rows in background), "background source chains mismatch")
    background_steps = [rows[0]["steps"] for rows in background]
    require(all(not any(step.get("observation") == "opened" for step in steps) for steps in background_steps), "background contains a successful outcome")
    return len(sources)


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
        require(manifest_path.is_file(), "checkpoint manifest is missing")
        payload = manifest_path.read_bytes()
        require(digest_bytes(payload) == cursor, "checkpoint manifest digest mismatch")
        manifest = json.loads(payload)
        descriptor_sha = manifest.get("state_descriptor_sha256")
        require(isinstance(descriptor_sha, str), "state descriptor identity is invalid")
        descriptor_path = field_root / "objects" / descriptor_sha
        descriptor_payload = descriptor_path.read_bytes()
        require(digest_bytes(descriptor_payload) == descriptor_sha, "state descriptor digest mismatch")
        descriptor = json.loads(descriptor_payload)
        require(descriptor.get("state_sha256") == manifest.get("state_sha256"), "manifest state identity mismatch")
        pages = descriptor.get("pages")
        require(isinstance(pages, list), "checkpoint page list is invalid")
        for page_sha in pages:
            require(isinstance(page_sha, str), "checkpoint page identity is invalid")
            page = field_root / "objects" / page_sha
            require(page.is_file() and digest_bytes(page.read_bytes()) == page_sha, "checkpoint page digest mismatch")
        raw_parent = manifest.get("parent_manifest_sha256")
        require(raw_parent is None or isinstance(raw_parent, str), "checkpoint parent is invalid")
        cursor = cast(str | None, raw_parent)
    current_manifest = cast(Mapping[str, Any], json.loads((field_root / "manifests" / current).read_bytes()))
    raw_field = run.get("field")
    require(isinstance(raw_field, Mapping), "final field summary is missing")
    field = cast(Mapping[str, Any], raw_field)
    require(current_manifest.get("state_sha256") == field.get("state_sha256"), "final durable state identity mismatch")
    return len(seen)


def close_number(actual: Any, expected: float, label: str, *, absolute: float = 1e-15) -> None:
    require(
        isinstance(actual, (int, float))
        and math.isfinite(float(actual))
        and math.isclose(float(actual), expected, rel_tol=1e-11, abs_tol=absolute),
        f"{label} mismatch",
    )


def read_hashed_object(field_root: Path, digest: Any, label: str) -> bytes:
    require(
        isinstance(digest, str)
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest),
        f"{label} identity is invalid",
    )
    payload = (field_root / "objects" / cast(str, digest)).read_bytes()
    require(digest_bytes(payload) == digest, f"{label} digest mismatch")
    return payload


def verify_resonant_artifact(
    run: Mapping[str, Any],
    home: Path,
) -> str:
    raw_resonance = run.get("resonance")
    raw_field = run.get("field")
    require(
        isinstance(raw_resonance, Mapping) and isinstance(raw_field, Mapping),
        "resonance or final field summary is missing",
    )
    resonance = cast(Mapping[str, Any], raw_resonance)
    field = cast(Mapping[str, Any], raw_field)
    field_root = home / "field"
    current = (field_root / "CURRENT").read_text(encoding="ascii").strip()
    manifest = json.loads((field_root / "manifests" / current).read_bytes())
    atlas_payload = read_hashed_object(
        field_root,
        manifest.get("state_descriptor_sha256"),
        "current atlas descriptor",
    )
    atlas_descriptor = json.loads(atlas_payload)
    state = atlas_descriptor.get("state")
    require(isinstance(state, Mapping), "current atlas state is invalid")
    state = cast(Mapping[str, Any], state)
    pages = state.get("pages")
    require(isinstance(pages, Mapping), "current atlas page index is invalid")
    pages = cast(Mapping[str, Any], pages)
    workspace_payload = read_hashed_object(
        field_root,
        pages.get("resonant_workspace"),
        "resonant workspace descriptor",
    )
    workspace = json.loads(workspace_payload)
    require(
        isinstance(workspace, Mapping)
        and workspace.get("schema") == EXPECTED_WORKSPACE_SCHEMA
        and workspace.get("layout") == EXPECTED_WORKSPACE_LAYOUT
        and workspace.get("bindings") == {}
        and workspace.get("layout_transition") == {}
        and workspace.get("paused") is False,
        "resonant workspace descriptor identity is invalid",
    )
    workspace = cast(Mapping[str, Any], workspace)
    page_payload = read_hashed_object(
        field_root,
        workspace.get("page_sha256"),
        "resonant field page",
    )
    profile = workspace.get("profile")
    require(isinstance(profile, Mapping), "resonant profile is missing")
    profile = cast(Mapping[str, Any], profile)
    require(
        dict(profile) == EXPECTED_RESONANT_PROFILE,
        "resonant profile is not the complete fixed seven-pool reference profile",
    )
    pools = cast(int, profile["pools"])
    ports_per_pool = cast(int, profile["ports_per_pool"])
    port_count = pools * ports_per_pool
    expected_doubles = 9 * (port_count + 1)
    require(
        len(page_payload) == expected_doubles * 8,
        "resonant field page byte length mismatch",
    )
    values = struct.unpack(f"<{expected_doubles}d", page_payload)
    require(all(math.isfinite(value) for value in values), "resonant field page is non-finite")
    for port in range(port_count):
        require(
            all(values[9 * port + lane] == 0.0 for lane in range(4, 9)),
            "unused resonant port lane is nonzero",
        )
    clock_offset = 9 * port_count
    close_number(values[clock_offset], float(workspace["heartbeat_phase"]), "heartbeat field lane")
    close_number(values[clock_offset + 1], float(workspace["breath_phase"]), "breath field lane")
    close_number(values[clock_offset + 2], float(workspace["activity"]), "activity field lane")
    require(
        all(value == 0.0 for value in values[clock_offset + 3:]),
        "unused resonant clock lane is nonzero",
    )

    state_descriptor = dict(workspace)
    expected_workspace_sha256 = state_descriptor.pop("state_sha256", None)
    state_descriptor.pop("page_sha256", None)
    descriptor_bytes = json.dumps(
        state_descriptor,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    computed_workspace_sha256 = digest_bytes(page_payload + descriptor_bytes)
    require(
        computed_workspace_sha256 == expected_workspace_sha256,
        "resonant workspace state digest mismatch",
    )

    q_y = values[0:9 * port_count:9]
    q_i = values[1:9 * port_count:9]
    p_y = values[2:9 * port_count:9]
    p_i = values[3:9 * port_count:9]
    inverse_mass = tuple(
        1.0 / (1.3 ** (port // ports_per_pool))
        for port in range(port_count)
    )
    measured_pool_power = []
    for pool in range(pools):
        start = pool * ports_per_pool
        stop = start + ports_per_pool
        measured_pool_power.append(sum(
            q_y[port] ** 2
            + q_i[port] ** 2
            + inverse_mass[port] * (p_y[port] ** 2 + p_i[port] ** 2)
            for port in range(start, stop)
        ))
    common = tuple((yang + yin) / math.sqrt(2.0) for yang, yin in zip(q_y, q_i, strict=True))
    relative = tuple((yang - yin) / math.sqrt(2.0) for yang, yin in zip(q_y, q_i, strict=True))
    relative_stiffness = float(profile["relative_stiffness"])
    beta = float(profile["beta"])
    measured_energy = 0.5 * (
        sum(value * value for value in common)
        + relative_stiffness * sum(value * value for value in relative)
        + sum(
            inverse_mass[index] * (p_y[index] ** 2 + p_i[index] ** 2)
            for index in range(port_count)
        )
    ) + 0.25 * beta * sum(value ** 4 for value in relative)

    raw_coupled = resonance.get("coupled_after_propagation")
    require(isinstance(raw_coupled, Mapping), "coupled wave summary is missing")
    coupled = cast(Mapping[str, Any], raw_coupled)
    require(
        coupled.get("workspace_state_sha256") == computed_workspace_sha256
        and field.get("resonant_workspace_state_sha256") == computed_workspace_sha256,
        "published and persisted resonant workspace identities differ",
    )
    require(
        field.get("resonant_field_bytes") == len(page_payload),
        "published resonant field byte count mismatch",
    )
    reported_pool_power = coupled.get("pool_power")
    require(
        isinstance(reported_pool_power, list) and len(reported_pool_power) == pools,
        "coupled pool-power summary is invalid",
    )
    reported_pool_power = cast(list[Any], reported_pool_power)
    for pool, expected in enumerate(measured_pool_power):
        close_number(reported_pool_power[pool], expected, f"coupled pool {pool + 1} power")
    close_number(coupled.get("energy"), measured_energy, "coupled field energy")
    ledger = workspace.get("ledger")
    require(isinstance(ledger, Mapping), "resonant energy ledger is missing")
    ledger = cast(Mapping[str, Any], ledger)
    close_number(ledger.get("stored_energy"), measured_energy, "persisted stored energy")
    require(
        workspace.get("field_ticks") == resonance.get("propagation_ticks") == 8
        and coupled.get("field_ticks") == 8
        and workspace.get("evidence_tick") == coupled.get("evidence_tick") == 5,
        "resonant clocks do not match the evidence and propagation schedule",
    )

    raw_coupling = resonance.get("formation_coupling")
    require(isinstance(raw_coupling, Mapping), "formation coupling receipt is missing")
    coupling = cast(Mapping[str, Any], raw_coupling)
    close_number(
        coupling.get("admission_work_budget"),
        1e-3,
        "formation admission work budget",
    )
    close_number(
        coupling.get("event_work_budget"),
        5e-4,
        "formation event work budget",
    )
    close_number(
        coupling.get("total_applied_work"),
        1e-3,
        "total applied formation work",
    )
    raw_events = coupling.get("events")
    require(
        coupling.get("schema") == "cassifi.temporal-resonance-coupling.v2"
        and coupling.get("applied") is True
        and coupling.get("active_event_count") == 2
        and coupling.get("admitted_step_count") == 1
        and coupling.get("formed_skills") == [SKILL]
        and coupling.get("withdrawn_skills") == []
        and isinstance(raw_events, list)
        and len(raw_events) == 2
        and all(isinstance(item, Mapping) for item in raw_events),
        "formation coupling event set is invalid",
    )
    events = cast(list[Mapping[str, Any]], raw_events)
    goal_event, formation_event = events
    discovery = run.get("discovery")
    require(isinstance(discovery, Mapping), "discovery record is missing")
    discovery = cast(Mapping[str, Any], discovery)
    source_chain = discovery.get("source_chain")
    require(
        isinstance(source_chain, list)
        and len(source_chain) == 3
        and isinstance(source_chain[-1], Mapping),
        "discovery source chain is invalid",
    )
    source_chain = cast(list[Mapping[str, Any]], source_chain)
    final_source = cast(Mapping[str, Any], source_chain[-1])
    final_source_receipt = final_source.get("receipt")
    require(
        isinstance(final_source_receipt, Mapping),
        "successful source receipt is missing",
    )
    final_source_receipt = cast(Mapping[str, Any], final_source_receipt)
    expected_evidence_event_id = final_source_receipt.get("event_id")
    evidence_event_id = coupling.get("evidence_event_id")
    require(
        isinstance(evidence_event_id, str)
        and len(evidence_event_id) == 64
        and evidence_event_id == expected_evidence_event_id,
        "formation coupling is not bound to the successful evidence event",
    )
    require(
        goal_event.get("event_kind") == "goal-observation"
        and goal_event.get("evidence_event_id") == evidence_event_id
        and goal_event.get("action") == "open"
        and goal_event.get("observation") == "opened"
        and goal_event.get("source_states") == [3]
        and goal_event.get("destination_states") == [2]
        and goal_event.get("predecessor_source_states") == [2]
        and goal_event.get("predecessor_destination_states") == []
        and goal_event.get("expected_by_predecessor") is False
        and goal_event.get("step_index") == 2
        and goal_event.get("contributions")
        == [
            {
                "orientation": 1.0,
                "reason": "goal-outcome",
                "skill_id": SKILL,
                "source": "learned-field",
            }
        ],
        "goal-observation event identity or learned-field attribution is invalid",
    )
    close_number(
        goal_event.get("signal_norm_before_normalization"),
        1.0,
        "goal-observation signal normalization",
    )
    require(
        formation_event.get("event_kind") == "formation"
        and formation_event.get("evidence_event_id") == evidence_event_id
        and formation_event.get("skill_id") == SKILL
        and formation_event.get("mapping") == "safe-reachability-rank-linear-seven-pool-v1"
        and formation_event.get("supported_states") == 3
        and formation_event.get("maximum_rank") == 3,
        "formation event identity or rank projection is invalid",
    )

    expected_unit = [
        1.0 / math.sqrt(3.0) if pool in {0, 3, 6} else 0.0
        for pool in range(pools)
    ]
    quadratic = sum(
        expected_unit[pool] ** 2 / (1.3 ** pool)
        for pool in range(pools)
    )
    first_impulse_amount = math.sqrt(1e-3 / quadratic)
    total_impulse_amount = math.sqrt(2e-3 / quadratic)
    expected_impulse_amounts = (
        first_impulse_amount,
        total_impulse_amount - first_impulse_amount,
    )
    expected_start_energies = (0.0, 5e-4)
    expected_end_energies = (5e-4, 1e-3)
    impulses: list[Mapping[str, Any]] = []
    for index, (event, event_kind) in enumerate(
        ((goal_event, "goal-observation"), (formation_event, "formation")),
    ):
        raw_impulse = event.get("impulse")
        require(
            isinstance(raw_impulse, Mapping),
            f"{event_kind} impulse receipt is missing",
        )
        impulse = cast(Mapping[str, Any], raw_impulse)
        impulses.append(impulse)
        require(
            impulse.get("schema") == "cassifi.resonant-pool-impulse-receipt.v2"
            and impulse.get("accepted") is True
            and impulse.get("event_kind") == event_kind
            and impulse.get("evidence_tick") == coupling.get("evidence_tick") == 5
            and impulse.get("field_ticks") == 0,
            f"{event_kind} impulse identity or clocks are invalid",
        )
        unit = impulse.get("pool_signal")
        event_signal = event.get("pool_signal")
        require(
            isinstance(unit, list)
            and len(unit) == pools
            and isinstance(event_signal, list)
            and len(event_signal) == pools,
            f"{event_kind} pool signal is invalid",
        )
        unit = cast(list[Any], unit)
        event_signal = cast(list[Any], event_signal)
        for pool, expected in enumerate(expected_unit):
            close_number(
                unit[pool],
                expected,
                f"{event_kind} impulse pool {pool + 1} signal",
            )
            close_number(
                event_signal[pool],
                expected,
                f"{event_kind} event pool {pool + 1} signal",
            )
        close_number(
            impulse.get("requested_work"),
            5e-4,
            f"requested {event_kind} work",
        )
        close_number(
            impulse.get("applied_work"),
            5e-4,
            f"applied {event_kind} work",
        )
        close_number(
            impulse.get("impulse_amount"),
            expected_impulse_amounts[index],
            f"{event_kind} impulse amount",
        )
        close_number(
            impulse.get("recorded_start_energy"),
            expected_start_energies[index],
            f"{event_kind} recorded start energy",
        )
        close_number(
            impulse.get("start_energy"),
            expected_start_energies[index],
            f"{event_kind} start energy",
        )
        close_number(
            impulse.get("end_energy"),
            expected_end_energies[index],
            f"{event_kind} end energy",
        )
        close_number(
            impulse.get("parameter_work"),
            0.0,
            f"{event_kind} parameter work",
        )
        close_number(
            impulse.get("balance_defect"),
            0.0,
            f"{event_kind} balance defect",
        )
    close_number(
        sum(float(impulse["applied_work"]) for impulse in impulses),
        float(coupling["total_applied_work"]),
        "summed formation event work",
    )

    raw_immediate = resonance.get("immediate")
    require(isinstance(raw_immediate, Mapping), "immediate wave summary is missing")
    immediate = cast(Mapping[str, Any], raw_immediate)
    immediate_power = immediate.get("pool_power")
    require(
        isinstance(immediate_power, list) and len(immediate_power) == pools,
        "immediate pool-power summary is invalid",
    )
    immediate_power = cast(list[Any], immediate_power)
    for pool in range(pools):
        expected = (
            total_impulse_amount ** 2
            * expected_unit[pool] ** 2
            / (1.3 ** pool)
        )
        close_number(
            immediate_power[pool],
            expected,
            f"immediate pool {pool + 1} power",
        )
    close_number(immediate.get("energy"), 1e-3, "immediate formation energy")
    require(
        immediate.get("workspace_state_sha256")
        == coupling.get("end_workspace_state_sha256")
        == impulses[-1].get("state_sha256"),
        "formation impulse workspace identity mismatch",
    )

    raw_propagation = resonance.get("propagation_receipt")
    require(isinstance(raw_propagation, Mapping), "wave propagation receipt is missing")
    propagation = cast(Mapping[str, Any], raw_propagation)
    require(
        propagation.get("ticks") == 8
        and propagation.get("source_enabled") is False
        and resonance.get("source_enabled") is False,
        "wave propagation source control mismatch",
    )
    close_number(propagation.get("start_energy"), 1e-3, "propagation start energy")
    close_number(propagation.get("end_energy"), measured_energy, "propagation end energy")
    balance = (
        float(propagation["end_energy"])
        - float(propagation["start_energy"])
        - float(propagation["parameter_work"])
        - float(propagation["boundary_work"])
        - float(propagation["positive_heartbeat_work"])
        + float(propagation["extracted_heartbeat_work"])
        + float(propagation["dissipated_work"])
        + float(propagation["numerical_dissipated_work"])
        - float(propagation["residual_work"])
    )
    close_number(propagation.get("balance_defect"), balance, "propagation work balance")
    close_number(propagation.get("positive_heartbeat_work"), 0.0, "disabled heartbeat work")
    close_number(propagation.get("extracted_heartbeat_work"), 0.0, "disabled heartbeat extraction")
    require(all(power > 0.0 for power in measured_pool_power), "wave did not reach all seven pools")

    raw_control = resonance.get("uncoupled_control_after_propagation")
    raw_control_receipt = resonance.get("uncoupled_control_receipt")
    require(
        isinstance(raw_control, Mapping) and isinstance(raw_control_receipt, Mapping),
        "uncoupled wave control is missing",
    )
    control = cast(Mapping[str, Any], raw_control)
    control_receipt = cast(Mapping[str, Any], raw_control_receipt)
    control_receipt_state = control_receipt.get("state_sha256")
    for key, expected in EXPECTED_ZERO_CONTROL_RECEIPT.items():
        require(
            control_receipt.get(key) == expected,
            f"no-impulse control receipt {key} violates its semantic contract",
        )
    raw_control_ledger = control.get("ledger")
    require(
        isinstance(raw_control_ledger, Mapping)
        and dict(raw_control_ledger) == EXPECTED_ZERO_CONTROL_LEDGER,
        "no-impulse control ledger is not exactly zero",
    )
    control_power = control.get("pool_power")
    require(
        isinstance(control_power, list)
        and len(control_power) == pools
        and all(power == 0.0 for power in control_power),
        "no-impulse control acquired pool power",
    )
    control_amplitude = control.get("pool_amplitude")
    require(
        isinstance(control_amplitude, list)
        and len(control_amplitude) == pools
        and all(amplitude == 0.0 for amplitude in control_amplitude)
        and control.get("common_rail_power") == 0.0
        and control.get("counterflow_rail_power") == 0.0,
        "no-impulse control acquired nonzero field amplitude",
    )
    close_number(control.get("energy"), 0.0, "no-impulse control energy")
    require(
        resonance.get("same_profile_and_clocks") is True,
        "published matched-profile-and-clock flag is not true",
    )
    require(
        resonance.get("categorical_policy_wave_gated") is False,
        "categorical policy was reported as wave-gated",
    )
    control_page = [0.0] * expected_doubles
    control_page[clock_offset] = float(control["heartbeat_phase"])
    control_page[clock_offset + 1] = float(control["breath_phase"])
    control_page[clock_offset + 2] = float(control["activity"])
    control_descriptor = {
        "schema": EXPECTED_WORKSPACE_SCHEMA,
        "profile": dict(EXPECTED_RESONANT_PROFILE),
        "layout": EXPECTED_WORKSPACE_LAYOUT,
        "bindings": {},
        "field_ticks": control["field_ticks"],
        "heartbeat_phase": control["heartbeat_phase"],
        "heartbeat_cycles": control["heartbeat_cycles"],
        "breath_phase": control["breath_phase"],
        "breath_cycles": control["breath_cycles"],
        "activity": control["activity"],
        "evidence_tick": control["evidence_tick"],
        "subdivision_ticks": 0,
        "paused": False,
        "ledger": dict(EXPECTED_ZERO_CONTROL_LEDGER),
        "layout_transition": {},
    }
    control_sha256 = digest_bytes(
        struct.pack(f"<{expected_doubles}d", *control_page)
        + json.dumps(
            control_descriptor,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    )
    require(
        control.get("workspace_state_sha256") == control_sha256
        and control_receipt_state == control_sha256,
        "no-impulse control state identity mismatch",
    )
    for key in (
        "field_ticks",
        "evidence_tick",
        "heartbeat_phase",
        "heartbeat_cycles",
        "breath_phase",
        "breath_cycles",
        "activity",
    ):
        require(coupled.get(key) == control.get(key), f"coupled/control {key} mismatch")
    require(
        coupled.get("workspace_state_sha256") != control.get("workspace_state_sha256"),
        "wave coupling did not change the committed workspace",
    )
    restart = run.get("restart")
    require(isinstance(restart, Mapping), "restart result is missing")
    restart = cast(Mapping[str, Any], restart)
    require(
        restart.get("before_workspace_state_sha256")
        == restart.get("after_workspace_state_sha256")
        == computed_workspace_sha256,
        "restart did not preserve the coupled workspace exactly",
    )
    return computed_workspace_sha256


def verify_run(run: Mapping[str, Any], data_home: Path) -> Mapping[str, Any]:
    raw_seed = run.get("seed")
    require(isinstance(raw_seed, int), "run seed is invalid")
    seed = cast(int, raw_seed)
    raw_discovery = run.get("discovery")
    require(isinstance(raw_discovery, Mapping), "discovery result is missing")
    discovery = cast(Mapping[str, Any], raw_discovery)
    require(discovery.get("completed") is True, "discovery did not complete")
    require(discovery.get("unsafe_observations") == 0, "discovery reached an unsafe outcome")
    replay(cast(Sequence[Any], discovery.get("actions")), cast(Sequence[Any], discovery.get("observations")), "discovery")
    raw_decisions = discovery.get("decisions")
    require(isinstance(raw_decisions, list) and len(raw_decisions) == 3, "discovery decision count mismatch")
    decisions = cast(list[Mapping[str, Any]], raw_decisions)
    for tick, (decision, action, observation) in enumerate(zip(decisions, EXPECTED_ACTIONS, EXPECTED_OBSERVATIONS, strict=True)):
        require(decision.get("tick") == tick and decision.get("action") == action, "discovery decision identity mismatch")
        require(decision.get("observation") == observation, "discovery decision observation mismatch")
        require(decision.get("status") == "acquiring" and decision.get("reason") == "acquisition-permitted", "discovery was not field-selected acquisition")
        require(decision.get("decision_resolved") is False, "discovery gap was represented as resolved")
        raw_acquisition = decision.get("acquisition")
        require(isinstance(raw_acquisition, Mapping), "discovery acquisition receipt is missing")
        acquisition = cast(Mapping[str, Any], raw_acquisition)
        require(acquisition.get("host_permitted") is True, "discovery acquisition was not authorized")

    raw_registration = run.get("registration")
    require(isinstance(raw_registration, Mapping), "prospective skill registration is missing")
    registration = cast(Mapping[str, Any], raw_registration)
    require(registration.get("skill_ids") == [SKILL], "registered skill identity mismatch")
    require(registration.get("formed_skill_ids") == [], "skill formed before discovery")
    require(registration.get("pending_skill_ids") == [SKILL], "prospective skill was not pending")
    require(
        registration.get("pre_transition_sha256") == registration.get("post_transition_sha256"),
        "registration changed transition coordinates",
    )
    require(
        registration.get("pre_memory_sha256") == registration.get("post_memory_sha256"),
        "registration changed learned memory identity",
    )
    require(
        registration.get("pre_state_sha256") != registration.get("post_state_sha256"),
        "registration did not persist the prospective skill",
    )
    raw_registration_receipt = registration.get("receipt")
    require(isinstance(raw_registration_receipt, Mapping), "registration receipt is missing")
    registration_receipt = cast(Mapping[str, Any], raw_registration_receipt)
    require(
        registration_receipt.get("status") == "pending"
        and registration_receipt.get("start_state_supported") is False
        and registration_receipt.get("supported_states") == 0,
        "unsupported prospective skill was marked formed",
    )
    require(
        registration_receipt.get("bound_memory_sha256") == registration.get("pre_memory_sha256"),
        "prospective skill is not bound to its registration memory",
    )
    raw_registration_coupling = registration_receipt.get("resonance_coupling")
    require(
        isinstance(raw_registration_coupling, Mapping)
        and raw_registration_coupling.get("applied") is False
        and raw_registration_coupling.get("events") == [],
        "pending registration emitted wave work",
    )
    raw_pending_readout = registration.get("readout")
    require(isinstance(raw_pending_readout, Mapping), "pending skill readout is missing")
    pending_readout = cast(Mapping[str, Any], raw_pending_readout)
    require(
        pending_readout.get("status") == "unresolved"
        and pending_readout.get("action") is None,
        "pending skill exposed an executable action",
    )

    raw_formation = run.get("formation")
    require(isinstance(raw_formation, Mapping), "evidence-triggered formation is missing")
    formation = cast(Mapping[str, Any], raw_formation)
    require(formation.get("skill_ids") == [SKILL], "formed skill identity mismatch")
    require(formation.get("formed_skill_ids") == [SKILL], "successful evidence did not form the skill")
    require(formation.get("pending_skill_ids") == [], "formed skill remained pending")
    require(formation.get("trigger_tick") == 2, "formation trigger tick mismatch")
    require(
        formation.get("memory_sha256") == formation.get("matched_unregistered_memory_sha256"),
        "prospective skill changed learned memory",
    )
    require(
        formation.get("transition_sha256")
        == formation.get("matched_unregistered_transition_sha256"),
        "prospective skill changed the matched transition field",
    )
    raw_events = formation.get("events")
    require(isinstance(raw_events, list) and len(raw_events) == 3, "formation event count mismatch")
    events = cast(list[Mapping[str, Any]], raw_events)
    for tick, event in enumerate(events):
        require(event.get("tick") == tick, "formation event tick mismatch")
        require(event.get("withdrawn_skills") == [], "skill was withdrawn during discovery")
        raw_event_coupling = event.get("resonance_coupling")
        require(isinstance(raw_event_coupling, Mapping), "formation wave receipt is missing")
        event_coupling = cast(Mapping[str, Any], raw_event_coupling)
        if tick < 2:
            require(event.get("formed_skills") == [], "skill formed before complete evidence")
            require(event.get("available_skills") == [], "skill became available before complete evidence")
            require(event.get("pending_skills") == [SKILL], "skill did not remain pending")
            expected_status = "unresolved"
            require(
                event_coupling.get("applied") is False
                and event_coupling.get("total_applied_work") == 0.0,
                "partial evidence emitted wave work",
            )
        else:
            require(event.get("formed_skills") == [SKILL], "successful evidence did not trigger formation")
            require(event.get("available_skills") == [SKILL], "formed skill is not available")
            require(event.get("pending_skills") == [], "formed skill is still pending")
            expected_status = "complete"
            require(
                event_coupling.get("applied") is True
                and event_coupling.get("formed_skills") == [SKILL],
                "formation boundary did not emit its bounded wave impulse",
            )
            close_number(
                event_coupling.get("total_applied_work"),
                1e-3,
                "formation boundary wave work",
            )
        raw_readout = event.get("readout")
        require(isinstance(raw_readout, Mapping), "formation readout is missing")
        event_readout = cast(Mapping[str, Any], raw_readout)
        require(event_readout.get("status") == expected_status, "formation readout status mismatch")

    raw_transfer = run.get("transfer")
    raw_restart = run.get("restart")
    require(isinstance(raw_transfer, Mapping) and isinstance(raw_restart, Mapping), "transfer or restart result is missing")
    transfer = cast(Mapping[str, Any], raw_transfer)
    restart = cast(Mapping[str, Any], raw_restart)
    verify_skill_records(transfer, "fresh transfer")
    require(restart.get("exact_closure") is True, "exact restart closure is false")
    require(restart.get("before_bundle_sha256") == restart.get("after_bundle_sha256"), "restart bundle digest mismatch")
    require(restart.get("skill_ids") == [SKILL], "restart lost the skill")
    raw_restart_transfer = restart.get("transfer")
    require(isinstance(raw_restart_transfer, Mapping), "restart transfer is missing")
    restart_transfer = cast(Mapping[str, Any], raw_restart_transfer)
    verify_skill_records(restart_transfer, "restart transfer")
    require(run.get("live_model_calls") == 0, "run reports live model calls")

    home = data_home / "owners" / f"seed-{seed}"
    sources = verify_sources(run, home)
    manifests = verify_checkpoint(run, home)
    workspace_sha256 = verify_resonant_artifact(run, home)
    return {
        "seed": seed,
        "source_revisions_verified": sources,
        "checkpoint_manifests_verified": manifests,
        "transition_sha256": formation["transition_sha256"],
        "workspace_sha256": workspace_sha256,
    }


def recompute_aggregate(runs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return {
        "runs": len(runs),
        "discovery_completed": sum(run["discovery"]["completed"] is True for run in runs),
        "transfer_completed": sum(run["transfer"]["completed"] is True for run in runs),
        "restart_transfer_completed": sum(run["restart"]["transfer"]["completed"] is True for run in runs),
        "initial_skill_pending": sum(run["registration"]["pending_skill_ids"] == [SKILL] for run in runs),
        "evidence_triggered_formations": sum(run["formation"]["formed_skill_ids"] == [SKILL] for run in runs),
        "formation_trigger_matches": sum(run["formation"]["trigger_tick"] == 2 for run in runs),
        "matched_unregistered_transitions": sum(
            run["formation"]["transition_sha256"]
            == run["formation"]["matched_unregistered_transition_sha256"]
            for run in runs
        ),
        "formation_wave_couplings": sum(
            run["resonance"]["formation_coupling"]["applied"] is True
            for run in runs
        ),
        "formation_wave_work": sum(
            run["resonance"]["formation_coupling"]["total_applied_work"]
            for run in runs
        ),
        "all_pool_propagations": sum(
            all(power > 0.0 for power in run["resonance"]["coupled_after_propagation"]["pool_power"])
            for run in runs
        ),
        "uncoupled_controls_quiet": sum(
            all(
                power == 0.0
                for power in run["resonance"]["uncoupled_control_after_propagation"]["pool_power"]
            )
            for run in runs
        ),
        "wave_counterfactuals_changed": sum(
            run["resonance"]["coupled_after_propagation"]["workspace_state_sha256"]
            != run["resonance"]["uncoupled_control_after_propagation"]["workspace_state_sha256"]
            for run in runs
        ),
        "wave_clock_matches": sum(
            run["resonance"]["same_profile_and_clocks"] is True
            for run in runs
        ),
        "exact_wave_restarts": sum(
            run["restart"]["before_workspace_state_sha256"]
            == run["restart"]["after_workspace_state_sha256"]
            and run["restart"]["before_workspace_state_sha256"] is not None
            for run in runs
        ),
        "discovery_sequence_matches": sum(run["discovery"]["actions"] == EXPECTED_ACTIONS for run in runs),
        "transfer_sequence_matches": sum(run["transfer"]["actions"] == EXPECTED_ACTIONS for run in runs),
        "restart_sequence_matches": sum(run["restart"]["transfer"]["actions"] == EXPECTED_ACTIONS for run in runs),
        "unsafe_observations": sum(run["discovery"]["unsafe_observations"] + run["transfer"]["unsafe_observations"] + run["restart"]["transfer"]["unsafe_observations"] for run in runs),
        "live_model_calls": sum(run["live_model_calls"] for run in runs),
        "exact_restarts": sum(run["restart"]["exact_closure"] is True for run in runs),
        "total_elapsed_seconds": sum(run["elapsed_seconds"] for run in runs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path("run_autonomous_skill_formation_scenario.py"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_bytes())
    require(report.get("schema") == SCHEMA, "report schema mismatch")
    require(report.get("source_sha256") == digest_bytes(args.source.read_bytes()), "scenario source digest mismatch")
    configuration = report.get("configuration")
    require(isinstance(configuration, Mapping), "configuration is missing")
    require(configuration.get("successful_sequence_supplied") is False, "successful sequence was supplied")
    require(configuration.get("transfer_goal_observations_supplied") is False, "transfer received a goal")
    require(configuration.get("prospective_skill_goal_registered_before_discovery") is True, "prospective skill goal was not registered before discovery")
    require(configuration.get("post_experience_condensation_called") is False, "scenario called post-experience condensation")
    require(configuration.get("actions") == ["prime", "align", "open"], "action vocabulary mismatch")
    require(configuration.get("goal_observations") == ["opened"], "goal mismatch")
    require(set(cast(Sequence[Any], configuration.get("forbidden_observations"))) == FORBIDDEN, "forbidden observations mismatch")
    background = configuration.get("background_sources")
    require(isinstance(background, list) and len(background) == 2, "background configuration mismatch")
    require(all(not any(step.get("observation") == "opened" for step in episode) for episode in background), "background configuration contains success")
    raw_resonant_configuration = configuration.get("resonant_coupling")
    require(
        isinstance(raw_resonant_configuration, Mapping),
        "resonant coupling configuration is missing",
    )
    resonant_configuration = cast(Mapping[str, Any], raw_resonant_configuration)
    require(
        resonant_configuration.get("formation_work_budget") == 1e-3
        and resonant_configuration.get("withdrawal_work_budget") == 1e-3
        and resonant_configuration.get("propagation_ticks") == 8
        and resonant_configuration.get("propagation_source_enabled") is False
        and resonant_configuration.get("categorical_policy_wave_gated") is False,
        "resonant coupling configuration mismatch",
    )

    raw_runs = report.get("runs")
    require(isinstance(raw_runs, list) and len(raw_runs) == 3, "expected exactly three runs")
    runs = cast(list[Mapping[str, Any]], raw_runs)
    seeds = [run.get("seed") for run in runs]
    require(seeds == configuration.get("seeds") and len(set(seeds)) == 3, "run seed matrix mismatch")
    verified = [verify_run(run, args.data_home) for run in runs]
    require(report.get("aggregate") == recompute_aggregate(runs), "aggregate metrics mismatch")
    require(len({row["transition_sha256"] for row in verified}) == 1, "learned transitions differ across seeds")
    require(len({row["workspace_sha256"] for row in verified}) == 1, "coupled wave fields differ across seeds")

    result = {
        "schema": VERIFICATION_SCHEMA,
        "status": "PASS",
        "report_sha256": digest_bytes(args.report.read_bytes()),
        "source_sha256": report["source_sha256"],
        "runs_verified": len(verified),
        "source_revisions_verified": sum(row["source_revisions_verified"] for row in verified),
        "checkpoint_manifests_verified": sum(row["checkpoint_manifests_verified"] for row in verified),
        "shared_transition_sha256": verified[0]["transition_sha256"],
        "shared_workspace_sha256": verified[0]["workspace_sha256"],
        "checks": [
            "independent three-stage simulator replay",
            "goal-only field-selected discovery",
            "observation-by-observation source revision chains",
            "pending prospective skill without executable policy",
            "automatic evidence-triggered field-policy formation",
            "bounded skill-formation impulse into the seven-pool field",
            "complete fixed resonance profile and non-wave-gated policy",
            "bound goal-outcome and formation event identities and total coupling work",
            "independent persisted wave-page decoding and energy reconstruction",
            "canonical-profile zero-ledger semantic control receipt and propagation",
            "exact coupled-workspace restart",
            "matched unregistered transition and memory control",
            "fresh-participant skill-only transfer",
            "exact restart and post-restart transfer",
            "persisted source blobs and content-addressed evidence events",
            "durable manifest ancestry and object hashes",
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
