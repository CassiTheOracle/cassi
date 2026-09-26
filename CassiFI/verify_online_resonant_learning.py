"""Independently verify a retained online-resonant-learning report.

This verifier deliberately imports no CassiFI production module.  It checks the
content-addressed evidence and checkpoint chain, reconstructs every reported
resonant score from the raw float64 field pages, and recomputes the behavioral
comparison from the retained report.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Mapping, Sequence, cast


REPORT_SCHEMA = "cassifi.online-resonant-learning.v1"
VERIFICATION_SCHEMA = "cassifi.online-resonant-learning-verification.v1"
WORKSPACE_SCHEMA = "cassifi.resonant-workspace.v1"
SCORE_SCHEMA = "cassifi.resonant-pool-probe-scores.v1"
MEMORY = "matched-release-choice"
EXPECTED_WORKSPACE_LAYOUT = "mode-major-9M-1:f64le:N=28:pools=7:ports=4"
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
SKILLS = ("fast-release", "staged-release")
ACTIONS = ("short", "long", "continue")
OBSERVATIONS = ("done-fast", "stage", "done-staged", "jammed")
EXPECTED_SIGNALS = {
    "fast-release": (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    "staged-release": (
        1.0 / math.sqrt(2.0), 0.0, 0.0, 0.0, 0.0, 0.0,
        1.0 / math.sqrt(2.0),
    ),
}
EXPECTED_ACTIONS = {"fast-release": "short", "staged-release": "long"}
EXPECTED_PATHS = {
    "fast-release": (("short", "done-fast"),),
    "staged-release": (("long", "stage"), ("continue", "done-staged")),
}


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_value(value: Any) -> str:
    return digest_bytes(canonical_bytes(value))


def sha256_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def close(actual: Any, expected: float, label: str, *, absolute: float = 1e-13) -> None:
    require(
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and math.isfinite(float(actual))
        and math.isclose(float(actual), expected, rel_tol=1e-11, abs_tol=absolute),
        f"{label} mismatch: reported {actual!r}, reconstructed {expected!r}",
    )


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{label} is not an object")
    return cast(Mapping[str, Any], value)


def sequence(value: Any, label: str) -> Sequence[Any]:
    require(isinstance(value, list), f"{label} is not an array")
    return cast(Sequence[Any], value)


def read_hashed(path: Path, digest: Any, label: str) -> bytes:
    require(
        isinstance(digest, str) and len(digest) == 64
        and all(ch in "0123456789abcdef" for ch in digest),
        f"{label} digest is malformed",
    )
    target = path / cast(str, digest)
    require(target.is_file(), f"{label} is missing")
    payload = target.read_bytes()
    require(digest_bytes(payload) == digest, f"{label} digest mismatch")
    return payload


def verify_sources(run: Mapping[str, Any], home: Path) -> int:
    rows = sequence(run.get("sources"), "source records")
    require(len(rows) == 6, "each run must retain two acquisitions and four outcomes")
    source_root = home / "evidence" / "sources"
    blob_root = home / "evidence" / "blobs"
    heads: dict[str, str] = {}
    prefixes: dict[str, list[Mapping[str, Any]]] = {}
    feedback_count = 0

    for index, raw_row in enumerate(rows):
        row = mapping(raw_row, f"source record {index}")
        revision_id = row.get("source_revision_id")
        require(
            isinstance(revision_id, str)
            and len(revision_id) == 64
            and all(ch in "0123456789abcdef" for ch in revision_id),
            "source revision identity is malformed",
        )
        metadata_path = source_root / cast(str, revision_id)
        require(metadata_path.is_file(), f"source record {index} is missing")
        metadata = mapping(
            json.loads(metadata_path.read_bytes()), f"source metadata {index}"
        )
        revision_identity = {
            key: metadata.get(key)
            for key in (
                "claim_category",
                "codec",
                "content_sha256",
                "fidelity",
                "labels",
                "media_type",
                "observed_timestamp",
                "parent_revision_id",
                "scope",
                "source_id",
                "span",
            )
        }
        require(
            digest_value(revision_identity)
            == metadata.get("revision_id")
            == revision_id,
            "source revision identity mismatch",
        )
        require(metadata.get("source_id") == row.get("source_id"), "source ID mismatch")
        require(metadata.get("parent_revision_id") == row.get("parent_revision_id"), "source parent mismatch")
        require(metadata.get("status") == "active", "reported source is not active")
        require(metadata.get("schema") == "cassifi.exact-source.v1", "source schema mismatch")
        require(metadata.get("scope") == "temporal-active-learning", "source scope mismatch")
        require(metadata.get("claim_category") == "controlled-world-observation", "source claim category mismatch")
        require(metadata.get("fidelity") == "exact-record", "source fidelity mismatch")
        require(metadata.get("labels") == ["temporal-active-learning", "train"], "source labels mismatch")

        content_sha = metadata.get("content_sha256")
        blob = read_hashed(blob_root, content_sha, f"source blob {index}")
        require(metadata.get("object_sha256") == content_sha, "source object/content digest mismatch")
        require(metadata.get("byte_length") == len(blob), "source byte length mismatch")
        episode = mapping(json.loads(blob), f"source episode {index}")
        require(episode.get("schema") == "cassifi.temporal-episode.v1", "episode schema mismatch")
        steps = sequence(episode.get("steps"), f"source episode {index} steps")
        require(list(steps) == row.get("steps"), "reported source steps differ from retained bytes")
        require(digest_value(list(steps)) == row.get("episode_sha256"), "episode digest mismatch")

        source_id = cast(str, row["source_id"])
        prior = prefixes.get(source_id, [])
        require(row.get("parent_revision_id") == heads.get(source_id), "source revision chain is discontinuous")
        require(len(steps) > len(prior) and list(steps[:len(prior)]) == prior,
                "source revision does not append to its predecessor")
        require(list(steps[len(prior):]) == row.get("delta_steps"), "reported source delta mismatch")
        heads[source_id] = cast(str, revision_id)
        prefixes[source_id] = [mapping(step, "source step") for step in steps]

        receipt = mapping(row.get("receipt"), f"source receipt {index}")
        require(receipt.get("source_revision_id") == revision_id, "receipt revision mismatch")
        require(receipt.get("parent_revision_id") == row.get("parent_revision_id"), "receipt parent mismatch")
        require(receipt.get("observation_count") == len(row["delta_steps"]), "receipt observation count mismatch")
        if str(row.get("label", "")).startswith("staged-success-"):
            feedback_count += 1
            coupling = mapping(receipt.get("resonance_coupling"), "outcome coupling receipt")
            require(coupling.get("schema") == "cassifi.temporal-resonance-coupling.v2", "coupling schema mismatch")
            require(coupling.get("applied") is True, "admitted successful outcome did not couple")
            require(coupling.get("formed_skills") == [] and coupling.get("withdrawn_skills") == [],
                    "feedback unexpectedly changed skill lifecycle")
            require(coupling.get("admitted_step_count") == 2, "feedback did not admit exactly two steps")
            events = [
                mapping(event, "feedback coupling event")
                for event in sequence(
                    coupling.get("events"), "feedback coupling events"
                )
            ]
            require(
                [event.get("event_kind") for event in events]
                == ["context-observation", "goal-observation"],
                "feedback event classification mismatch",
            )
            expected_reasons = ("reachable-context", "goal-outcome")
            applied_work = 0.0
            for event, reason in zip(events, expected_reasons, strict=True):
                contributions = sequence(
                    event.get("contributions"), "feedback contributions"
                )
                require(len(contributions) == 1, "feedback contribution count mismatch")
                contribution = mapping(
                    contributions[0], "feedback contribution"
                )
                require(
                    contribution.get("skill_id") == "staged-release"
                    and contribution.get("reason") == reason
                    and contribution.get("orientation") == 1.0
                    and contribution.get("source") == "learned-field",
                    "feedback contribution identity mismatch",
                )
                signal = tuple(
                    float(value)
                    for value in sequence(
                        event.get("pool_signal"), "feedback pool signal"
                    )
                )
                require(
                    len(signal) == 7
                    and signal[0] > 0.0
                    and signal[6] > 0.0
                    and all(value == 0.0 for value in signal[1:6]),
                    "feedback did not address the staged skill pools",
                )
                close(
                    math.sqrt(sum(value * value for value in signal)),
                    1.0,
                    "feedback signal norm",
                )
                impulse = mapping(event.get("impulse"), "feedback impulse")
                require(
                    impulse.get("accepted") is True
                    and impulse.get("event_kind") == event.get("event_kind")
                    and impulse.get("pool_signal") == list(signal),
                    "feedback impulse does not bind its event",
                )
                close(
                    impulse.get("applied_work"),
                    float(coupling["event_work_budget"]),
                    "per-event applied work",
                )
                applied_work += float(impulse["applied_work"])
            close(
                coupling.get("total_applied_work"),
                applied_work,
                "outcome work accounting",
            )
            close(
                coupling.get("total_applied_work"),
                2.0 * float(coupling["event_work_budget"]),
                "bounded outcome work",
            )
            require(applied_work > 0.0, "feedback did not perform field work")

    require(feedback_count == 4, "retained feedback source count mismatch")
    require(len(heads) == 6, "unexpected number of independent source chains")
    return len(rows)


def verify_checkpoint(run: Mapping[str, Any], home: Path) -> tuple[int, Mapping[str, Any]]:
    field_root = home / "field"
    current = (field_root / "CURRENT").read_text(encoding="ascii").strip()
    seen: set[str] = set()
    cursor: str | None = current
    previous_generation: int | None = None
    current_manifest: Mapping[str, Any] | None = None

    while cursor is not None:
        require(cursor not in seen, "checkpoint chain contains a cycle")
        seen.add(cursor)
        payload = read_hashed(field_root / "manifests", cursor, "checkpoint manifest")
        manifest = mapping(json.loads(payload), "checkpoint manifest")
        if current_manifest is None:
            current_manifest = manifest
        generation = manifest.get("generation")
        require(isinstance(generation, int) and not isinstance(generation, bool), "checkpoint generation is invalid")
        if previous_generation is not None:
            require(generation == previous_generation - 1, "checkpoint generations are not contiguous")
        previous_generation = generation
        descriptor_sha = manifest.get("state_descriptor_sha256")
        descriptor_payload = read_hashed(field_root / "objects", descriptor_sha, "atlas descriptor")
        descriptor = mapping(json.loads(descriptor_payload), "atlas descriptor")
        require(descriptor.get("state_sha256") == manifest.get("state_sha256"), "manifest/atlas state mismatch")
        for page_sha in sequence(descriptor.get("pages"), "atlas object list"):
            read_hashed(field_root / "objects", page_sha, "atlas page")
        parent = manifest.get("parent_manifest_sha256")
        require(parent is None or isinstance(parent, str), "checkpoint parent is invalid")
        previous_generation = generation
        cursor = cast(str | None, parent)

    require(previous_generation == 0, "checkpoint chain does not terminate at genesis")
    require(current_manifest is not None, "checkpoint chain is empty")
    final_manifest = mapping(current_manifest, "current checkpoint manifest")
    field = mapping(run.get("field"), "reported final field")
    require(final_manifest.get("state_sha256") == field.get("state_sha256"), "final field identity mismatch")
    return len(seen), final_manifest


def decode_workspace(workspace: Mapping[str, Any], label: str) -> tuple[tuple[float, ...], str]:
    require(workspace.get("schema") == WORKSPACE_SCHEMA, f"{label} schema mismatch")
    profile = mapping(workspace.get("profile"), f"{label} profile")
    require(
        workspace.get("layout") == EXPECTED_WORKSPACE_LAYOUT
        and dict(profile) == EXPECTED_RESONANT_PROFILE
        and workspace.get("bindings") == {}
        and workspace.get("layout_transition") == {}
        and workspace.get("paused") is False,
        f"{label} is not the fixed canonical seven-pool workspace",
    )
    pools = cast(int, profile["pools"])
    ports_per_pool = cast(int, profile["ports_per_pool"])
    encoded_field = workspace.get("field_b64")
    require(isinstance(encoded_field, str), f"{label} field encoding is missing")
    raw = base64.b64decode(cast(str, encoded_field), validate=True)
    expected_count = 9 * (pools * ports_per_pool + 1)
    require(len(raw) == 8 * expected_count, f"{label} field byte length mismatch")
    values = struct.unpack(f"<{expected_count}d", raw)
    require(all(math.isfinite(value) for value in values), f"{label} contains non-finite field values")

    descriptor = dict(workspace)
    expected_sha = descriptor.pop("state_sha256", None)
    descriptor.pop("field_b64", None)
    descriptor.pop("page_sha256", None)
    computed_sha = digest_bytes(raw + json.dumps(
        descriptor, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode())
    require(expected_sha == computed_sha, f"{label} state digest mismatch")
    return values, computed_sha


def verify_persisted_workspace(
    run: Mapping[str, Any], home: Path, manifest: Mapping[str, Any],
) -> str:
    field_root = home / "field"
    atlas_payload = read_hashed(
        field_root / "objects", manifest.get("state_descriptor_sha256"),
        "current atlas descriptor",
    )
    atlas = mapping(json.loads(atlas_payload), "current atlas descriptor")
    state = mapping(atlas.get("state"), "current atlas state")
    pages = mapping(state.get("pages"), "current atlas pages")
    workspace_payload = read_hashed(
        field_root / "objects", pages.get("resonant_workspace"),
        "current workspace descriptor",
    )
    workspace = mapping(json.loads(workspace_payload), "current workspace descriptor")
    page_payload = read_hashed(
        field_root / "objects", workspace.get("page_sha256"),
        "current resonant field page",
    )
    persisted = dict(workspace)
    persisted["field_b64"] = base64.b64encode(page_payload).decode("ascii")
    _, state_sha = decode_workspace(persisted, "persisted workspace")
    field = mapping(run.get("field"), "reported final field")
    require(field.get("resonant_workspace_state_sha256") == state_sha,
            "reported final workspace identity mismatch")
    require(field.get("resonant_field_bytes") == len(page_payload),
            "reported final workspace byte count mismatch")
    return state_sha


def reconstruct_scores(
    workspace: Mapping[str, Any], candidates: Sequence[Any], label: str,
) -> tuple[dict[str, Mapping[str, Any]], float, str]:
    values, state_sha = decode_workspace(workspace, label)
    profile = mapping(workspace.get("profile"), f"{label} profile")
    pools = cast(int, profile["pools"])
    ports_per_pool = cast(int, profile["ports_per_pool"])
    n = pools * ports_per_pool
    q_y = values[0:9 * n:9]
    q_i = values[1:9 * n:9]
    p_y = values[2:9 * n:9]
    p_i = values[3:9 * n:9]
    require(profile.get("projected_inv_mass") is None,
            f"{label} uses an unsupported projected mass")
    single_strand_inverse_mass = tuple(
        1.0 / (1.3 ** (port // ports_per_pool)) for port in range(n)
    )
    inverse_mass = single_strand_inverse_mass + single_strand_inverse_mass
    q_common = tuple(
        (yang + yin) / math.sqrt(2.0)
        for yang, yin in zip(q_y, q_i, strict=True)
    )
    momentum = tuple(p_y) + tuple(p_i)
    metric_momentum = tuple(
        mass * value for mass, value in zip(inverse_mass, momentum, strict=True)
    )
    kinetic_norm_squared = sum(
        value * metric
        for value, metric in zip(momentum, metric_momentum, strict=True)
    )
    require(kinetic_norm_squared >= -1e-12, f"{label} inverse-mass metric is not positive")
    reference_norm = math.sqrt(
        sum(value * value for value in q_common)
        + max(0.0, kinetic_norm_squared)
    )
    phase = float(workspace["heartbeat_phase"])
    cosine, sine = math.cos(phase), math.sin(phase)

    rows: dict[str, Mapping[str, Any]] = {}
    ordered_candidates = sorted(
        (mapping(value, "score candidate") for value in candidates),
        key=lambda candidate: cast(str, candidate["candidate_sha256"]),
    )
    for candidate in ordered_candidates:
        probe_id = cast(str, candidate["candidate_sha256"])
        signal = tuple(
            float(value)
            for value in sequence(candidate.get("pool_signal"), "candidate pool signal")
        )
        require(len(signal) == pools and all(math.isfinite(value) for value in signal),
                "candidate pool signal is invalid")
        signal_norm = math.sqrt(sum(value * value for value in signal))
        require(signal_norm > 0.0, "candidate pool signal is zero")
        unit_signal = tuple(value / signal_norm for value in signal)
        coordinate_probe = tuple(
            value / math.sqrt(ports_per_pool)
            for value in unit_signal
            for _ in range(ports_per_pool)
        )
        momentum_probe = tuple(
            value / math.sqrt(2.0)
            for value in coordinate_probe + coordinate_probe
        )
        metric_probe = tuple(
            mass * value
            for mass, value in zip(inverse_mass, momentum_probe, strict=True)
        )
        coordinate_norm_squared = sum(value * value for value in coordinate_probe)
        momentum_norm_squared = sum(
            value * metric
            for value, metric in zip(momentum_probe, metric_probe, strict=True)
        )
        q_projection = sum(
            probe * value
            for probe, value in zip(coordinate_probe, q_common, strict=True)
        )
        p_projection = sum(
            probe * value
            for probe, value in zip(momentum_probe, metric_momentum, strict=True)
        )
        in_phase_probe_norm = math.sqrt(
            sine * sine * coordinate_norm_squared
            + cosine * cosine * momentum_norm_squared
        )
        quadrature_probe_norm = math.sqrt(
            cosine * cosine * coordinate_norm_squared
            + sine * sine * momentum_norm_squared
        )
        in_phase_denominator = reference_norm * in_phase_probe_norm
        quadrature_denominator = reference_norm * quadrature_probe_norm
        in_phase = (
            0.0
            if in_phase_denominator == 0.0
            else (sine * q_projection + cosine * p_projection)
            / in_phase_denominator
        )
        quadrature = (
            0.0
            if quadrature_denominator == 0.0
            else (cosine * q_projection - sine * p_projection)
            / quadrature_denominator
        )
        signal_value = list(unit_signal)
        rows[probe_id] = {
            "probe_id": probe_id,
            "probe_sha256": digest_value(signal_value),
            "pool_signal": signal_value,
            "probe_norm": signal_norm,
            "in_phase": in_phase,
            "quadrature": quadrature,
            "compatibility": in_phase,
        }
    return rows, reference_norm, state_sha


def verify_selection(
    selection: Mapping[str, Any], workspace: Mapping[str, Any], label: str,
) -> Mapping[str, float]:
    candidates = sequence(selection.get("candidates"), f"{label} candidates")
    require(len(candidates) == 2, f"{label} must expose exactly two candidates")
    require(selection.get("status") == "selected", f"{label} is not selected")
    require(selection.get("reason") == "resonant-compatibility", f"{label} reason mismatch")
    candidate_ids = sorted(
        cast(str, mapping(candidate, "candidate")["candidate_sha256"])
        for candidate in candidates
    )
    require(
        digest_value(candidate_ids) == selection.get("candidate_set_sha256"),
        f"{label} candidate-set digest mismatch",
    )

    expected_by_probe, reference_norm, workspace_sha = reconstruct_scores(
        workspace, candidates, label
    )
    scoring = mapping(selection.get("resonant_scoring"), f"{label} scoring")
    require(scoring.get("schema") == SCORE_SCHEMA, f"{label} scoring schema mismatch")
    require(scoring.get("metric") == "normalized-common-phase-space-energy-projection-v1",
            f"{label} scoring metric mismatch")
    require(scoring.get("workspace_state_sha256") == workspace_sha, f"{label} workspace identity mismatch")
    require(scoring.get("workspace_unchanged") is True, f"{label} scorer was not read-only")
    require(scoring.get("field_ticks") == workspace.get("field_ticks"), f"{label} field clock mismatch")
    require(scoring.get("evidence_tick") == workspace.get("evidence_tick"), f"{label} evidence clock mismatch")
    close(scoring.get("heartbeat_phase"), float(workspace["heartbeat_phase"]), f"{label} heartbeat phase")
    close(scoring.get("reference_norm"), reference_norm, f"{label} reference norm")
    reported_scores = sequence(scoring.get("scores"), f"{label} score rows")
    require(len(reported_scores) == len(expected_by_probe), f"{label} score row count mismatch")
    reported_by_probe = {
        cast(str, mapping(value, "score row")["probe_id"]): mapping(value, "score row")
        for value in reported_scores
    }
    require(set(reported_by_probe) == set(expected_by_probe), f"{label} score identities mismatch")

    by_skill: dict[str, float] = {}
    for candidate_raw in candidates:
        candidate = mapping(candidate_raw, "candidate")
        probe_id = cast(str, candidate["candidate_sha256"])
        expected = expected_by_probe[probe_id]
        reported = reported_by_probe[probe_id]
        require(reported.get("probe_sha256") == expected["probe_sha256"], f"{label} probe digest mismatch")
        require(reported.get("pool_signal") == expected["pool_signal"], f"{label} normalized signal mismatch")
        close(reported.get("probe_norm"), cast(float, expected["probe_norm"]), f"{label} probe norm")
        close(reported.get("in_phase"), cast(float, expected["in_phase"]), f"{label} in-phase score")
        close(reported.get("quadrature"), cast(float, expected["quadrature"]), f"{label} quadrature score")
        close(reported.get("compatibility"), cast(float, expected["compatibility"]), f"{label} compatibility")
        candidate_score = mapping(candidate.get("resonant_score"), "candidate resonant score")
        require(dict(candidate_score) == dict(reported), f"{label} candidate/scorer score mismatch")
        skill_id = cast(str, candidate["skill_id"])
        require(candidate.get("action") == EXPECTED_ACTIONS[skill_id], f"{label} action mismatch")
        require(tuple(candidate.get("pool_signal", ())) == EXPECTED_SIGNALS[skill_id],
                f"{label} skill signal mismatch")
        require(candidate.get("safe_policy") is True, f"{label} included unsafe policy")
        operation = mapping(candidate.get("operation"), "candidate operation")
        require(operation.get("authorized") is True and operation.get("feasible") is True,
                f"{label} selected beyond authorization or feasibility")
        require(operation.get("represented_forbidden") is False,
                f"{label} candidate represents a forbidden observation")
        by_skill[skill_id] = cast(float, expected["compatibility"])

    ranked = sorted(
        (mapping(candidate, "candidate") for candidate in candidates),
        key=lambda candidate: -float(
            mapping(candidate.get("resonant_score"), "candidate score")["compatibility"]
        ),
    )
    winner = ranked[0]
    runner_up = ranked[1]
    selected = mapping(selection.get("selected"), f"{label} selected candidate")
    require(selected.get("candidate_sha256") == winner.get("candidate_sha256"),
            f"{label} did not choose the highest-scoring candidate")
    margin = float(
        mapping(winner.get("resonant_score"), "winner score")["compatibility"]
    ) - float(
        mapping(runner_up.get("resonant_score"), "runner-up score")["compatibility"]
    )
    close(selection.get("selection_margin"), margin, f"{label} selection margin")
    return by_skill


def semantic_candidates(selection: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return sorted(({
        "skill_id": candidate["skill_id"],
        "action": candidate["action"],
        "pool_signal": candidate["pool_signal"],
        "status": candidate["status"],
    } for candidate in map(lambda value: mapping(value, "candidate"), sequence(selection["candidates"], "candidates"))),
        key=lambda row: cast(str, row["skill_id"]))


def verify_behavior(run: Mapping[str, Any]) -> Mapping[str, Any]:
    registrations = sequence(run.get("registrations"), "skill registrations")
    require(len(registrations) == 2, "skill registration count mismatch")
    for expected_skill, raw_registration in zip(SKILLS, registrations, strict=True):
        registration = mapping(raw_registration, "skill registration")
        require(
            registration.get("skill_id") == expected_skill
            and registration.get("status") == "formed",
            f"{expected_skill} was not formed before comparison",
        )
        formation = mapping(
            registration.get("resonance_coupling"), "formation coupling"
        )
        require(
            formation.get("applied") is True
            and formation.get("formed_skills") == [expected_skill]
            and formation.get("withdrawn_skills") == [],
            f"{expected_skill} formation did not enter the shared wave",
        )
    source_rows = {
        cast(str, mapping(value, "source record")["label"]): mapping(
            value, "source record"
        )
        for value in sequence(run.get("sources"), "source records")
    }
    start = mapping(run.get("candidate_start"), "candidate start")
    start_workspace = mapping(start.get("workspace"), "start workspace artifact")
    online_start = mapping(start.get("online"), "initial online selection")
    control_start = mapping(
        start.get("no_outcome_wave_control"), "initial control selection"
    )
    require(
        semantic_candidates(online_start)
        == semantic_candidates(control_start)
        == start.get("candidate_semantics"),
        "initial matched candidates differ",
    )
    initial_online = verify_selection(
        online_start, start_workspace, "initial online"
    )
    initial_control = verify_selection(
        control_start, start_workspace, "initial control"
    )
    for skill in SKILLS:
        close(
            initial_online[skill],
            initial_control[skill],
            f"initial {skill} matched score",
        )
    require(
        mapping(online_start["selected"], "initial selection").get("skill_id")
        == "fast-release",
        "initial field did not prefer the fast skill",
    )

    rounds = sequence(run.get("trajectory"), "feedback trajectory")
    require(len(rounds) == 4, "feedback round count mismatch")
    crossover_rounds: list[int] = []
    prior_online_staged = initial_online["staged-release"]
    previous_workspace_sha = start_workspace.get("state_sha256")
    for expected_round, raw_round in enumerate(rounds, start=1):
        row = mapping(raw_round, f"feedback round {expected_round}")
        require(row.get("round") == expected_round, "feedback rounds are not ordered")
        online = mapping(row.get("online"), "round online selection")
        control = mapping(
            row.get("no_outcome_wave_control"), "round control selection"
        )
        require(
            semantic_candidates(online)
            == semantic_candidates(control)
            == start.get("candidate_semantics"),
            "matched online/control candidates differ",
        )
        require(
            online.get("candidate_set_sha256")
            == control.get("candidate_set_sha256"),
            "matched candidate identities differ",
        )
        current_workspace = mapping(
            row.get("online_workspace"), "round online workspace"
        )
        online_scores = verify_selection(
            online, current_workspace, f"round {expected_round} online"
        )
        control_scores = verify_selection(
            control, start_workspace, f"round {expected_round} control"
        )
        for skill in SKILLS:
            close(
                control_scores[skill],
                initial_control[skill],
                f"round {expected_round} held {skill} score",
            )
        require(
            online_scores["staged-release"] > prior_online_staged,
            "successful staged outcome did not increase staged compatibility",
        )
        prior_online_staged = online_scores["staged-release"]
        if mapping(online["selected"], "round online winner").get("skill_id") == "staged-release":
            crossover_rounds.append(expected_round)
        require(
            mapping(control["selected"], "round control winner").get("skill_id")
            == "fast-release",
            "held-wave control preference changed",
        )
        coupling = mapping(row.get("resonance_coupling"), "round coupling")
        require(
            coupling.get("start_workspace_state_sha256") == previous_workspace_sha,
            "feedback wave did not extend its exact predecessor",
        )
        require(
            coupling.get("end_workspace_state_sha256")
            == current_workspace.get("state_sha256"),
            "round workspace does not match committed outcome coupling",
        )
        source_row = mapping(
            source_rows.get(f"staged-success-{expected_round}"),
            "feedback source record",
        )
        require(
            row.get("source_revision_id") == source_row.get("source_revision_id"),
            "trajectory/source revision identity mismatch",
        )
        source_receipt = mapping(source_row.get("receipt"), "feedback source receipt")
        require(
            dict(coupling)
            == dict(
                mapping(
                    source_receipt.get("resonance_coupling"),
                    "feedback source coupling",
                )
            ),
            "trajectory/source coupling receipts differ",
        )
        previous_workspace_sha = current_workspace.get("state_sha256")

    require(
        bool(crossover_rounds),
        "online field never crossed to the successful staged skill",
    )
    first_crossover = crossover_rounds[0]
    require(
        all(
            mapping(
                mapping(rounds[index - 1], "round")["online"], "online"
            )["selected"]["skill_id"]
            == "staged-release"
            for index in range(first_crossover, len(rounds) + 1)
        ),
        "online preference reverted after crossover",
    )
    require(
        run.get("crossover_round") == first_crossover,
        "reported crossover round mismatch",
    )

    final_round = mapping(rounds[-1], "final round")
    final_online = mapping(final_round.get("online"), "final online selection")
    final_control = mapping(
        final_round.get("no_outcome_wave_control"), "final control selection"
    )
    require(
        semantic_candidates(final_online) == semantic_candidates(final_control),
        "field counterfactual changed categorical candidates",
    )
    require(
        mapping(final_online["selected"], "final online winner").get("skill_id")
        == "staged-release",
        "outcome-trained field did not choose staged skill",
    )
    require(
        mapping(final_control["selected"], "final control winner").get("skill_id")
        == "fast-release",
        "held field did not choose fast skill",
    )
    require(
        final_online.get("resonant_workspace_state_sha256")
        != final_control.get("resonant_workspace_state_sha256"),
        "field-only counterfactual did not change the wave state",
    )

    held_out = mapping(run.get("held_out"), "held-out comparison")
    online_trial = mapping(held_out.get("online"), "online transfer trial")
    control_trial = mapping(
        held_out.get("no_outcome_wave_control"), "control transfer trial"
    )
    require(
        online_trial.get("completed") is True
        and online_trial.get("unsafe_observations") == 0,
        "online transfer did not safely complete",
    )
    require(
        control_trial.get("completed") is False
        and control_trial.get("unsafe_observations") == 1,
        "held-wave control did not encounter the hidden jam",
    )
    require(
        online_trial.get("actions") == ["long", "continue"],
        "online transfer action trace mismatch",
    )
    require(
        online_trial.get("observations") == ["stage", "done-staged"],
        "online transfer observation trace mismatch",
    )
    require(
        control_trial.get("actions") == ["short"],
        "control transfer action trace mismatch",
    )
    require(
        control_trial.get("observations") == ["jammed"],
        "control transfer observation trace mismatch",
    )

    restart = mapping(run.get("restart"), "restart record")
    require(restart.get("exact_closure") is True, "restart closure was not exact")
    require(
        restart.get("before_bundle_sha256") == restart.get("after_bundle_sha256"),
        "restart changed the canonical field bundle",
    )
    require(
        restart.get("before_workspace_state_sha256")
        == restart.get("after_workspace_state_sha256")
        == previous_workspace_sha,
        "restart changed the outcome-trained workspace",
    )
    field = mapping(run.get("field"), "final field")
    require(
        restart.get("state_sha256") == field.get("state_sha256"),
        "restart state identity mismatch",
    )
    restart_selection = mapping(
        restart.get("selection"), "post-restart selection"
    )
    require(
        mapping(
            restart_selection.get("selected"), "post-restart winner"
        ).get("skill_id")
        == "staged-release",
        "post-restart preference was not retained",
    )
    verify_selection(
        restart_selection,
        mapping(final_round.get("online_workspace"), "final round workspace"),
        "post-restart",
    )

    return {
        "seed": run.get("seed"),
        "crossover_round": first_crossover,
        "online_completed": True,
        "control_completed": False,
        "online_unsafe_observations": 0,
        "control_unsafe_observations": 1,
        "restart_exact": True,
    }


def verify_report(report: Mapping[str, Any], data_home: Path, source_path: Path) -> Mapping[str, Any]:
    require(report.get("schema") == REPORT_SCHEMA, "report schema mismatch")
    require(report.get("source_sha256") == sha256_file(source_path), "scenario source digest mismatch")
    configuration = mapping(report.get("configuration"), "configuration")
    require(tuple(configuration.get("skills", ())) == SKILLS, "skill vocabulary mismatch")
    require(tuple(configuration.get("actions", ())) == ACTIONS, "action vocabulary mismatch")
    require(tuple(configuration.get("observations", ())) == OBSERVATIONS, "observation vocabulary mismatch")
    require(configuration.get("memory_id") == MEMORY, "memory identity mismatch")
    require(configuration.get("feedback_rounds") == 4, "feedback schedule mismatch")
    require(configuration.get("feedback_target_skill") == "staged-release", "feedback target mismatch")
    require(float(configuration.get("outcome_work_budget_per_admission", 0.0)) > 0.0,
            "outcome work budget is not positive")
    for skill, expected_path in EXPECTED_PATHS.items():
        actual = configuration.get("paths", {}).get(skill)
        require(tuple((step["action"], step["observation"]) for step in actual) == expected_path,
                f"configured path mismatch for {skill}")

    runs = sequence(report.get("runs"), "runs")
    require(bool(runs), "report contains no runs")
    run_count = len(runs)
    configured_seeds = sequence(configuration.get("seeds"), "configured seeds")
    require(
        [mapping(run, "run").get("seed") for run in runs]
        == list(configured_seeds),
        "run seeds do not match configuration",
    )
    require(
        len(set(configured_seeds)) == run_count,
        "comparison seeds are not distinct",
    )

    summaries: list[Mapping[str, Any]] = []
    manifest_counts: list[int] = []
    source_counts: list[int] = []
    workspace_hashes: list[str] = []
    for raw_run in runs:
        run = mapping(raw_run, "run")
        seed = run.get("seed")
        require(isinstance(seed, int) and not isinstance(seed, bool), "run seed is invalid")
        home = data_home / "owners" / f"seed-{seed}"
        require(home.is_dir(), f"retained owner is missing for seed {seed}")
        source_counts.append(verify_sources(run, home))
        manifest_count, manifest = verify_checkpoint(run, home)
        manifest_counts.append(manifest_count)
        workspace_hashes.append(verify_persisted_workspace(run, home, manifest))
        summaries.append(verify_behavior(run))

    expected_aggregate = {
        "runs": run_count,
        "online_crossovers": run_count,
        "online_completed": run_count,
        "control_completed": 0,
        "online_unsafe_observations": 0,
        "control_unsafe_observations": run_count,
        "online_action_steps": 2 * run_count,
        "control_action_steps": run_count,
        "exact_restarts": run_count,
        "field_only_counterfactuals": run_count,
        "live_model_calls": 0,
        "crossover_rounds": [
            summary["crossover_round"] for summary in summaries
        ],
    }
    aggregate = mapping(report.get("aggregate"), "aggregate")
    for key, expected in expected_aggregate.items():
        require(aggregate.get(key) == expected, f"aggregate {key} mismatch")
    recomputed_work = sum(
        float(
            mapping(row, "trajectory row")["resonance_coupling"][
                "total_applied_work"
            ]
        )
        for raw_run in runs
        for row in sequence(
            mapping(raw_run, "run").get("trajectory"), "trajectory"
        )
    )
    close(
        aggregate.get("outcome_feedback_work"),
        recomputed_work,
        "aggregate outcome feedback work",
    )
    require(recomputed_work > 0.0, "aggregate outcome work is not positive")
    require(
        all(mapping(run, "run").get("live_model_calls") == 0 for run in runs),
        "a live model call was reported",
    )

    return {
        "schema": VERIFICATION_SCHEMA,
        "status": "PASS",
        "report_sha256": digest_bytes(canonical_bytes(report)),
        "scenario_source_sha256": sha256_file(source_path),
        "runs": run_count,
        "seeds": list(configured_seeds),
        "source_records_verified": sum(source_counts),
        "checkpoint_manifests_verified": sum(manifest_counts),
        "workspace_state_sha256": workspace_hashes,
        "reconstructed_score_sets": run_count * (2 + 2 * 4 + 1),
        "online_crossovers": run_count,
        "crossover_rounds": expected_aggregate["crossover_rounds"],
        "safe_online_completions": run_count,
        "unsafe_control_observations": run_count,
        "exact_restarts": run_count,
        "field_only_counterfactuals": run_count,
        "live_model_calls": 0,
        "production_imports": 0,
        "claim_boundary": [
            f"PASS verifies retained content hashes, checkpoint lineage, raw-page score reconstruction, causal held-wave comparisons, transfer traces, and exact restart identities for the supplied deterministic {run_count}-seed scenario.",
            "It does not establish action invention, open-vocabulary learning, calibrated uncertainty, safety under unrepresented outcomes, broad-world generalization, or subjective experience.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).with_name("run_online_resonant_learning_scenario.py"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = mapping(json.loads(args.report.read_text(encoding="utf-8")), "report")
    result = verify_report(report, args.data_home, args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
