"""Run the packet-aware reasoning scenario on the ordinary owner path.

Stage 1 prepares one live workshop world and its packet hierarchy.
Stage 2 opens a cue-driven reasoning episode, transports its first resident
child, and stops with that child's return unconsumed.
Stage 3 corrects the shared premise, repairs the unfinished invalidation in
bounded quanta, reopens the episode through the ordinary owner, and finishes
it without renewing its allowance.
Stage 4 compares the declared work-selection methods on the same frontier.
Stage 5 refuses a composition whose packets come from different field states.
Stage 6 forces one refinement from a coarse bound and reads the refined child.

Usage:  python run_cassi_reasoning_scenario.py [--receipt PATH]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
import hashlib
import math
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cassi_field_atlas import (  # noqa: E402
    FieldIntelligenceError,
    canonical_json_bytes,
)
from cassi_field_cognition import semantic_cognition_state  # noqa: E402
from cassi_field_owner import (  # noqa: E402
    FieldIntelligenceError,
    FieldIntelligenceOwner,
    FieldIntelligenceSurface,
    RPC_SCHEMA,
    SourceInput,
)
from cassi_hive_session import open_field_session  # noqa: E402
from cassi_resonant_field import (  # noqa: E402
    HELICAL_PACKET_CHANNELS,
    ResonantNumericalError,
    ResonantWorkspace,
    analyze_helical_packet,
    compose_helical_packets,
    initial_workspace,
    regional_state,
    split_helical_packet,
)

DEFAULT_RECEIPT = Path(__file__).resolve().parent / "_diag" / "reasoning-scenario.json"
ALLOCATION = {
    "branch_count": 4,
    "evidence_reads": 1_000_000,
    "frontier_size": 8,
    "model_calls": 4,
    "refinement_depth": 4,
    "storage_words": 2_000_000,
    "work": 4_096,
}

stages: dict[str, Any] = {}
transcript: list[str] = []


def call(owner: FieldIntelligenceOwner, request_id: str, action: str, **arguments: Any):
    return FieldIntelligenceSurface(owner).handle(
        {
            "schema": RPC_SCHEMA,
            "request_id": request_id,
            "operation": "computer",
            "params": {
                "operation_id": request_id,
                "computer_id": "reasoning",
                "action": action,
                "arguments": arguments,
            },
        }
    )


def consumed(owner: FieldIntelligenceOwner) -> Mapping[str, Any]:
    return owner.state.computers[0].inspect()["consumed_result"]


def invoke(owner: FieldIntelligenceOwner, request_id: str, **arguments: Any):
    """Invoke one semantic operation, refusing kernel faults, and return its result."""

    transcript.append(str(arguments.get("operation", "")))
    receipt = call(owner, request_id, "invoke", arguments=arguments, steps=64)
    run = receipt["result"]["receipt"]["run"]
    for row in run.get("transition_receipts", []):
        if row.get("disposition") == "fault":
            raise AssertionError(
                f"{request_id} faulted the field kernel: {row.get('fault_detail')}"
            )
    result = consumed(owner)
    if result is None:
        raise AssertionError(f"{request_id} produced no consumed result")
    return result


def task_state(owner: FieldIntelligenceOwner) -> Mapping[str, Any]:
    return owner.state.computers[0].inspect()["task"]


def record(owner: FieldIntelligenceOwner, kind: str, identity: str) -> Mapping[str, Any]:
    task = task_state(owner)
    reference = task["current"][kind][identity]
    return task["records"][reference["id"]][-1]


def require(condition: Any, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def asymmetric_world() -> dict[str, Any]:
    """Build one world whose two halves carry different packet activations."""

    import numpy as np

    workspace = initial_workspace()
    profile = workspace.profile
    count = profile.port_count
    page = workspace.field.reshape(-1)
    index = np.arange(count, dtype=np.float64)
    half = count // 2
    lanes = (
        0.2 * np.sin(0.17 * index),
        0.2 * np.cos(0.11 * index),
        0.2 * np.sin(0.07 * index * index),
        -0.2 * np.cos(0.13 * index),
    )
    for lane, values in enumerate(lanes):
        values = values.copy()
        values[half:] *= 6.0
        page[lane:9 * count:9] = values
    workspace = ResonantWorkspace(
        profile=profile,
        field_page=page.reshape(profile.page_shape),
    )
    root = dict(analyze_helical_packet(workspace, path=""))
    left, right = split_helical_packet(root)
    packets = sorted(
        {packet["path"]: dict(packet) for packet in (root, left, right)}.values(),
        key=lambda packet: (packet["support"]["start"], packet["support"]["stop"]),
    )
    return {
        "assembly": {
            "assembly_id": "comparison-assembly",
            "assistance": "supplied",
            "bindings": [
                {"channel": channel, "scale": 1.0}
                for channel in HELICAL_PACKET_CHANNELS
            ],
            "hierarchy_id": "comparison-hierarchy",
            "interface": {
                "kind": "reasoning",
                "channels": list(HELICAL_PACKET_CHANNELS),
            },
            "retained_expansion": 1,
            "workspace_state": regional_state(workspace, ticks=2, demand=0.2),
        },
        "hierarchy": {
            "a_clip": 1.0,
            "active_paths": [left["path"], right["path"]],
            "assembly_id": "comparison-assembly",
            "channel_scales": {channel: 1.0 for channel in HELICAL_PACKET_CHANNELS},
            "channel_units": {channel: "word" for channel in HELICAL_PACKET_CHANNELS},
            "codec": "float64",
            "frame": "world",
            "hierarchy_id": "comparison-hierarchy",
            "packets": packets,
            "priority_scale": 1_000_000,
        },
        "left": left,
        "right": right,
        "workspace": workspace,
    }


def world() -> dict[str, Any]:
    """Build one live world: workspace, sibling views, hierarchy, and assembly."""

    workspace = initial_workspace()
    root = dict(analyze_helical_packet(workspace, path=""))
    left, right = split_helical_packet(root)
    packets = sorted(
        {packet["path"]: dict(packet) for packet in (root, left, right)}.values(),
        key=lambda packet: (packet["support"]["start"], packet["support"]["stop"]),
    )
    assembly_id = "workshop-assembly"
    hierarchy = {
        "a_clip": 1.0,
        "active_paths": [left["path"], right["path"]],
        "assembly_id": assembly_id,
        "channel_scales": {channel: 1.0 for channel in HELICAL_PACKET_CHANNELS},
        "channel_units": {channel: "word" for channel in HELICAL_PACKET_CHANNELS},
        "codec": "float64",
        "frame": "world",
        "hierarchy_id": "workshop-hierarchy",
        "packets": packets,
        "priority_scale": 1,
    }
    return {
        "assembly": {
            "assembly_id": assembly_id,
            "assistance": "supplied",
            "bindings": [
                {"channel": channel, "scale": 1.0}
                for channel in HELICAL_PACKET_CHANNELS
            ],
            "hierarchy_id": "workshop-hierarchy",
            "interface": {
                "kind": "reasoning",
                "channels": list(HELICAL_PACKET_CHANNELS),
            },
            "retained_expansion": 1,
            "workspace_state": regional_state(workspace, ticks=2, demand=0.2),
        },
        "hierarchy": hierarchy,
        "left": left,
        "right": right,
        "workspace": workspace,
    }


def stage_one(owner: FieldIntelligenceOwner, scene: Mapping[str, Any]) -> None:
    call(owner, "scenario-configure", "configure")
    call(
        owner,
        "scenario-submit",
        "submit",
        kernel="cognition.field",
        state=semantic_cognition_state()
        if scene.get("bounds") is None
        else semantic_cognition_state(bounds=scene["bounds"]),
        steps=64,
    )
    reported = invoke(
        owner,
        "scenario-observe",
        operation="observe",
        operation_id="scenario-observe-premise",
        delivery_id="scenario-delivery-premise",
        event_id="scenario-event-premise",
        observations=[
            {
                "binding_id": "binding:workshop-premise",
                "subject": "workshop",
                "attribute": "load",
                "value": 2.0,
            }
        ],
    )
    stages["s1_world"] = {
        "delivery_status": reported["status"],
        "premise": record(owner, "Binding", "binding:workshop-premise")["payload"][
            "value"
        ],
        "workspace_state_phase": scene["assembly"]["workspace_state"]["phase"],
        "active_paths": scene["hierarchy"]["active_paths"],
    }


def stage_two(owner: FieldIntelligenceOwner, scene: Mapping[str, Any]) -> None:
    began = invoke(
        owner,
        "scenario-begin",
        operation="begin-reasoning",
        operation_id="scenario-begin-operation",
        episode_id="workshop-episode",
        question={
            "kind": "workshop-report",
            "task_id": "universal-interpreter-workshop",
            "prompt": "Determine the corrected workshop load and emit its correction.",
            "requested_output": "next-token-correction",
        },
        allocation=dict(ALLOCATION),
        dependencies=[
            {
                "content_version": 1,
                "id": "binding:workshop-premise",
                "kind": "Binding",
            }
        ],
        assemblies=[dict(scene["assembly"])],
        hierarchy=dict(scene["hierarchy"]),
        cues=[
            {
                "consequence": {
                    "frame": "world",
                    "kind": "residual",
                    "scale": 1.0,
                    "scale_units": "word",
                    "units": "word",
                    "value": 0.5,
                },
                "constraint": {
                    "frame": "world",
                    "kind": "residual",
                    "scale": 1.0,
                    "scale_units": "word",
                    "units": "word",
                    "value": 0.25,
                },
                "cue_id": "workshop-report",
                "dependencies": [],
                "event_kind": "reasoning-work",
                "hierarchy_id": "workshop-hierarchy",
                "source_operation_id": "scenario-begin-operation",
                "w_max": 1.0,
            }
        ],
    )
    invitation = began.get("invocation")
    require(isinstance(invitation, Mapping), "the episode published no work")
    call(
        owner,
        "scenario-child",
        "call",
        **invitation,
        steps=64,
    )
    returned = {
        name: value["status"]
        for name, value in task_state(owner)["invocation_returns"].items()
    }
    require(bool(returned), "the resident child published no return")
    episode = record(owner, "Obligation", "obligation:reasoning:workshop-episode")
    require(
        episode["payload"]["active"] is not None,
        "the episode did not retain its reservation",
    )
    stages["s2_open_episode"] = {
        "allowance_id": episode["payload"]["root_allowance_id"],
        "charged": dict(episode["payload"]["resources"]["charged"]),
        "consumed_returns": len(episode["payload"]["consumed_returns"]),
        "interrupted_after_return": True,
        "outstanding_returns": returned,
        "phase": episode["payload"]["phase"],
        "question": {
            "kind": "workshop-report",
            "task_id": "universal-interpreter-workshop",
            "prompt": "Determine the corrected workshop load and emit its correction.",
            "requested_output": "next-token-correction",
        },
        "reserved": dict(episode["payload"]["resources"]["reserved"]),
        "work_items": [
            {
                "item_id": row["item_id"],
                "kind": row["kind"],
                "status": row["status"],
            }
            for row in episode["payload"]["work_items"]
        ],
    }


def stage_three(owner: FieldIntelligenceOwner, scene: Mapping[str, Any]) -> None:
    """Correct the premise, then reopen through the ordinary owner."""

    stale_returns = dict(task_state(owner)["invocation_returns"])
    require(bool(stale_returns), "no interrupted return was retained")
    allowance = dict(
        record(owner, "Obligation", "obligation:reasoning:workshop-episode")["payload"][
            "resources"
        ]["limits"]
    )
    invoke(
        owner,
        "scenario-correct",
        operation="correct",
        operation_id="scenario-correct-operation",
        correction_id="workshop-load",
        target={
            "content_version": 1,
            "id": "binding:workshop-premise",
            "kind": "Binding",
        },
        replacement={"value": 5.0},
    )
    task = task_state(owner)
    barrier_active = bool(task["invalidation"]["active"])
    blocked: str | None = None
    quanta = 0
    if barrier_active:
        try:
            invoke(
                owner,
                "scenario-advance-blocked",
                operation="advance-reasoning",
                operation_id="scenario-advance-blocked-operation",
                episode_id="workshop-episode",
            )
        except FieldIntelligenceError as exc:
            blocked = str(exc)
        require(blocked is not None, "a stale read was not refused")
        while task_state(owner)["invalidation"]["active"]:
            invoke(
                owner,
                f"scenario-repair-{quanta}",
                operation="advance-invalidation",
                operation_id=f"scenario-repair-operation-{quanta}",
                quanta=1,
            )
            quanta += 1
            require(quanta <= 512, "the invalidation did not settle in bounded quanta")
    invalidated = [
        row
        for row in task_state(owner)["records"][
            "obligation:reasoning:workshop-episode"
        ]
        if row["status"] == "invalidated"
    ]
    require(bool(invalidated), "the correction left the dependent episode live")
    resume_window = len(transcript)

    resumed = invoke(
        owner,
        "scenario-advance",
        operation="advance-reasoning",
        operation_id="scenario-advance-operation",
        episode_id="workshop-episode",
    )
    transports = 0
    while isinstance(resumed.get("invocation"), Mapping) and transports < 8:
        call(
            owner,
            f"scenario-resume-child-{transports}",
            "call",
            **resumed["invocation"],
            steps=64,
        )
        resumed = invoke(
            owner,
            f"scenario-advance-{transports + 1}",
            operation="advance-reasoning",
            operation_id=f"scenario-advance-operation-{transports + 1}",
            episode_id="workshop-episode",
        )
        transports += 1
    episode = record(owner, "Obligation", "obligation:reasoning:workshop-episode")
    finished = invoke(
        owner,
        "scenario-finish",
        operation="finish-reasoning",
        operation_id="scenario-finish-operation",
        episode_id="workshop-episode",
    )
    retained = dict(task_state(owner)["invocation_returns"])
    operations_during_resume = transcript[resume_window:]
    stages["s3_correction_and_reopen"] = {
        "allowance_id": episode["payload"]["root_allowance_id"],
        "allowance_unchanged": allowance
        == dict(episode["payload"]["resources"]["limits"]),
        "barrier_retained_by_the_correction": barrier_active,
        "blocked_read": blocked,
        "charged": dict(episode["payload"]["resources"]["charged"]),
        "conclusion": finished["status"],
        "consumed_returns": len(episode["payload"]["consumed_returns"]),
        "phase": episode["payload"]["phase"],
        "premise_after": record(
            owner, "Binding", "binding:workshop-premise"
        )["payload"]["value"],
        "question": {
            "kind": "workshop-report",
            "task_id": "universal-interpreter-workshop",
            "prompt": "Determine the corrected workshop load and emit its correction.",
            "requested_output": "next-token-correction",
        },
        "quanta_to_repair": quanta,
        "releases": episode["payload"].get("releases", []),
        "scope": (
            "the correction settled its invalidation inside the operation at the "
            "default work bound, so the stale-read refusal is exercised by the "
            "narrow-bound regression in test_cassi_packet_reasoning.py"
            if not barrier_active
            else "the correction retained an unfinished invalidation barrier"
        ),
        "repairs": [
            {
                "current_version": row["current"]["content_version"],
                "prior_version": row["prior"]["content_version"],
            }
            for row in episode["payload"].get("repairs", [])
        ],
        "observations_during_resume": sum(
            1 for name in operations_during_resume if name == "observe"
        ),
        "operations_during_resume": operations_during_resume,
        "stale_return_bindings": sorted(
            set(stale_returns) - set(retained)
        ),
        "stale_returns_still_retained": sorted(
            set(stale_returns) & set(retained)
        ),
        "transports_after_reopen": transports,
        "work_items": [
            {"item_id": row["item_id"], "status": row["status"]}
            for row in episode["payload"]["work_items"]
        ],
    }


def bound_packet_readout(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Build the certified affine readout one arm reads a packet through."""

    powers = [
        math.sqrt(
            math.fsum(float(row[index]) ** 2 for row in packet["coefficients"])
        )
        for index in range(len(HELICAL_PACKET_CHANNELS))
    ]
    digest = hashlib.sha256(
        json.dumps(
            {
                "path": packet["path"],
                "powers": powers,
                "source_state_sha256": packet["source_state_sha256"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "bias": 0.0,
        "bound_provider": {
            "arithmetic_epsilon": 1e-12,
            "codec_sha256": digest,
            "construction_work": len(powers),
            "omitted_indices": [],
            "readout_sha256": digest,
            "schema": "cassifi.packet-readout-bound.v1",
            "source_state_sha256": packet["source_state_sha256"],
            "x_norm_upper": 0.0,
        },
        "codec_sha256": digest,
        "comparison": "gt",
        "inspected_indices": list(range(len(powers))),
        "output_units": "word",
        "readout_sha256": digest,
        "scaled_coefficients": powers,
        "scaled_weights": [1.0 for _ in powers],
        "schema": "cassifi.packet-affine-readout.v1",
        "source_state_sha256": packet["source_state_sha256"],
        "threshold": 0.1,
        "tolerance": None,
    }


class selection_world:
    """Give one selection arm its own continuing world and packet state."""

    def __init__(self, template: FieldIntelligenceOwner, method: str) -> None:
        base = Path(template.root) if hasattr(template, "root") else Path("_diag")
        self.root = base / "selection-arms" / method
        self.owner: FieldIntelligenceOwner | None = None

    def __enter__(self) -> FieldIntelligenceOwner:
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        self.owner = FieldIntelligenceOwner(self.root)
        self.owner.__enter__()
        call(self.owner, "scenario-arm-configure", "configure")
        call(
            self.owner,
            "scenario-arm-submit",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            steps=64,
        )
        return self.owner

    def __exit__(self, *exc: Any) -> None:
        if self.owner is not None:
            self.owner.__exit__(*exc)


def stage_four(owner: FieldIntelligenceOwner, scene: Mapping[str, Any]) -> None:
    """Compare the declared work-selection methods on one live frontier."""

    scene = asymmetric_world()

    packet_readout = bound_packet_readout

    packets = {
        str(packet["path"]): packet for packet in scene["hierarchy"]["packets"]
    }
    orders: dict[str, list[str]] = {}
    methods: dict[str, str] = {}
    snapshots: dict[str, list[dict[str, Any]]] = {}
    for method in ("baseline", "hierarchy", "static", "live", "shuffled", "acquired"):
        episode_id = f"selection-{method}"
        with selection_world(owner, method) as arm:
            selection: dict[str, Any] = {"method": method}
            if method == "acquired":
                from cassi_field_program import semantic_program_payload

                registered = invoke(
                    arm,
                    "scenario-selection-selector",
                    operation="register",
                    operation_id="scenario-selection-selector-operation",
                    record_id="program:reasoning-selector",
                    kind="Program",
                    payload={
                        "program": semantic_program_payload(
                            program_kind="affine",
                            body={
                                "outputs": {
                                    "priority": {
                                        "action_terms": {},
                                        "bias": 0.0,
                                        "error": 0.0,
                                        "terms": {"activation": 1.0},
                                    }
                                }
                            },
                            max_work=8,
                        ),
                        "program_role": "reasoning",
                    },
                )
                selection["selector"] = registered["record"]
            invoke(
                arm,
            f"scenario-selection-{method}",
            operation="begin-reasoning",
            operation_id=f"scenario-selection-operation-{method}",
            episode_id=episode_id,
            question={"kind": "selection-comparison", "method": method},
            allocation=dict(ALLOCATION),
            assemblies=[dict(scene["assembly"])],
            hierarchy=dict(scene["hierarchy"]),
            program={
                "selection": selection,
                "work_items": [
                    {
                        "dependencies": [],
                        "item_id": f"compare-{path}",
                        "kind": "readout",
                        "priority": 1,
                        "readout": packet_readout(packets[path]),
                        "support_paths": [path],
                    }
                    for path in scene["hierarchy"]["active_paths"]
                ],
            },
            )
            episode = record(arm, "Obligation", f"obligation:reasoning:{episode_id}")
            orders[method] = [
                str(row["selected"])
                for row in episode["payload"]["scheduler"]["snapshots"]
            ]
            methods[method] = str(episode["payload"]["scheduler"]["method"])
            snapshots[method] = [
                {
                    "dispatch": row["dispatch"],
                    "eligible": [
                        {"item_id": item["item_id"], "score": item["score"]}
                        for item in row["eligible"]
                    ],
                    "cue_kind": (
                        (row.get("selected_score_details") or {})
                        .get("cue", {})
                        or {}
                    ).get("kind"),
                    "reason": row["reason"],
                    "selected": row["selected"],
                }
                for row in episode["payload"]["scheduler"]["snapshots"]
            ]
    stages["s4_selection_methods"] = {
        "dispatch_orders": orders,
        "scheduler_methods": methods,
        "scheduler_snapshots": snapshots,
        "packet_activations": {
            path: {
                "coefficient_count": len(packet["coefficients"]),
                "support": dict(packet["support"]),
            }
            for path, packet in packets.items()
        },
    }


def stage_five(scene: Mapping[str, Any]) -> None:
    changed = ResonantWorkspace(
        profile=scene["workspace"].profile,
        field_page=scene["workspace"].field,
    )
    page = changed.field
    page[0, 0, 0] += 1.0
    changed = ResonantWorkspace(
        profile=changed.profile, field_page=page
    )
    _other_left, other_right = split_helical_packet(
        analyze_helical_packet(changed)
    )
    refused: str | None = None
    try:
        compose_helical_packets(scene["left"], other_right)
    except ResonantNumericalError as exc:
        refused = str(exc)
    require(refused is not None, "cross-source composition was accepted")
    stages["s5_source_bound_composition"] = {"refused": refused}


def stage_six(owner: FieldIntelligenceOwner) -> None:
    """Coarse readout, forced refinement, then a decisive detail on the child."""

    scene = asymmetric_world()

    import hashlib
    import math

    def powers(packet: Mapping[str, Any]) -> list[float]:
        return [
            math.sqrt(
                math.fsum(float(row[index]) ** 2 for row in packet["coefficients"])
            )
            for index in range(len(HELICAL_PACKET_CHANNELS))
        ]

    def contract(
        packet: Mapping[str, Any],
        *,
        weights: list[float],
        inspected: list[int],
        norm_upper: float,
        threshold: float,
    ) -> dict[str, Any]:
        digest = hashlib.sha256(
            json.dumps(
                {
                    "inspected": inspected,
                    "path": packet["path"],
                    "source": packet["source_state_sha256"],
                    "weights": weights,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return {
            "bias": 0.0,
            "bound_provider": {
                "arithmetic_epsilon": 1e-12,
                "codec_sha256": digest,
                "construction_work": len(powers(packet)),
                "omitted_indices": sorted(
                    set(range(len(HELICAL_PACKET_CHANNELS))) - set(inspected)
                ),
                "readout_sha256": digest,
                "schema": "cassifi.packet-readout-bound.v1",
                "source_state_sha256": packet["source_state_sha256"],
                "x_norm_upper": norm_upper,
            },
            "codec_sha256": digest,
            "comparison": "gt",
            "inspected_indices": inspected,
            "output_units": "word",
            "readout_sha256": digest,
            "scaled_coefficients": powers(packet),
            "scaled_weights": weights,
            "schema": "cassifi.packet-affine-readout.v1",
            "source_state_sha256": packet["source_state_sha256"],
            "threshold": threshold,
            "tolerance": None,
        }

    from cassi_resonant_field import split_helical_packet

    packets = {
        str(packet["path"]): packet for packet in scene["hierarchy"]["packets"]
    }
    target = scene["hierarchy"]["active_paths"][1]
    packet = packets[target]
    coarse = powers(packet)
    left, right = split_helical_packet(packet)
    omitted_norm = math.sqrt(
        math.fsum(value * value for value in coarse[1:])
    )
    with selection_world(owner, "refinement") as arm:
        call(
            arm,
            "scenario-refinement-observe",
            "invoke",
            arguments={
                "operation": "observe",
                "operation_id": "scenario-refinement-observe-operation",
                "delivery_id": "scenario-refinement-delivery",
                "event_id": "scenario-refinement-event",
                "observations": [
                    {
                        "binding_id": "binding:workshop-premise",
                        "subject": "workshop",
                        "attribute": "load",
                        "value": 2.0,
                    }
                ],
            },
            steps=64,
        )
        invoke(
            arm,
            "scenario-refinement-begin",
            operation="begin-reasoning",
            operation_id="scenario-refinement-begin-operation",
            episode_id="refinement-episode",
            question={"kind": "coarse-then-fine"},
            allocation=dict(ALLOCATION),
            assemblies=[dict(scene["assembly"])],
            hierarchy=dict(scene["hierarchy"]),
            program={
                "work_items": [
                    {
                        "dependencies": [],
                        "item_id": "coarse-probe",
                        "kind": "readout",
                        "priority": 1,
                        "readout": contract(
                            packet,
                            weights=[1.0, 1.0, 1.0, 1.0],
                            inspected=[0],
                            norm_upper=omitted_norm,
                            threshold=coarse[0],
                        ),
                        "support_paths": [target],
                    },
                    {
                        "dependencies": ["coarse-probe"],
                        "item_id": "refine-target",
                        "kind": "refine",
                        "priority": 1,
                        "refinement": {
                            "hierarchy_id": scene["hierarchy"]["hierarchy_id"],
                            "path": target,
                            "reason": {"kind": "unresolved-bound", "path": target},
                        },
                        "support_paths": [target],
                    },
                    {
                        "dependencies": ["refine-target"],
                        "item_id": "fine-probe",
                        "kind": "readout",
                        "priority": 1,
                        "readout": contract(
                            left,
                            weights=[1.0, 1.0, 1.0, 1.0],
                            inspected=[0, 1, 2, 3],
                            norm_upper=0.0,
                            threshold=0.0,
                        ),
                        "support_paths": [str(left["path"])],
                    },
                ]
            },
        )
        for index in range(6):
            advanced = invoke(
                arm,
                f"scenario-refinement-advance-{index}",
                operation="advance-reasoning",
                operation_id=f"scenario-refinement-advance-operation-{index}",
                episode_id="refinement-episode",
            )
            if advanced["phase"] == "terminal":
                break
        episode = record(arm, "Obligation", "obligation:reasoning:refinement-episode")
        results = episode["payload"]["results"]
        hierarchy = record(
            arm, "Value", f"value:packet-hierarchy:{scene['hierarchy']['hierarchy_id']}"
        )["payload"]
        charged = dict(episode["payload"]["resources"]["charged"])
        kind_counts: dict[str, int] = {}
        for row in episode["payload"]["work_items"]:
            kind_counts[str(row["kind"])] = kind_counts.get(str(row["kind"]), 0) + 1
        stages["s6_refinement"] = {
            "charged": charged,
            "item_kinds": kind_counts,
            "readouts_consumed": sum(
                1
                for row in episode["payload"]["results"].values()
                if row.get("schema") == "cassifi.packet-affine-readout-result.v1"
            ),
            "active_paths": list(hierarchy["active_paths"]),
            "coarse_result": results["coarse-probe"],
            "fine_result": results["fine-probe"],
            "max_depth": int(hierarchy["max_depth"]),
            "refined_children": results["refine-target"]["children"],
            "refinement_status": results["refine-target"]["status"],
            "work_items": [
                {"item_id": row["item_id"], "status": row["status"]}
                for row in episode["payload"]["work_items"]
            ],
        }


def stage_seven(owner: FieldIntelligenceOwner) -> None:
    """Exercise source-span provenance on a real dispatched work item.

    One episode reads a packet through a declared source span, admitted before the
    item dispatches, and the dispatch row records the correspondence. Two control
    episodes cite an unadmitted source and an unknown source revision.
    """

    with selection_world(owner, "source-binding") as arm:
        source_span_scenario(arm)


def source_span_scenario(arm: FieldIntelligenceOwner) -> None:
    """Dispatch one bound readout item through an arm, with admission in between."""

    scene = asymmetric_world()
    packets = {str(packet["path"]): packet for packet in scene["hierarchy"]["packets"]}
    archived = arm.archive_source(
        operation_id="scenario-source",
        source=SourceInput(
            source_id="scenario-record",
            content=canonical_json_bytes({"excerpt": "the workshop premise"}),
            media_type="application/json",
            codec="utf-8",
            observed_timestamp="scenario-time",
            scope="workshop:bay-17",
            claim_category="documented-record",
            fidelity="exact-record",
            span=(0, 14),
            labels=("scenario",),
        ),
        context={},
        event_kind="scenario-source",
    )
    revision = str(archived["source"]["revision_id"])
    unadmitted_archive = arm.archive_source(
        operation_id="scenario-source-unadmitted",
        source=SourceInput(
            source_id="scenario-record-unadmitted",
            content=canonical_json_bytes({"excerpt": "the unused record"}),
            media_type="application/json",
            codec="utf-8",
            observed_timestamp="scenario-time",
            scope="workshop:bay-17",
            claim_category="documented-record",
            fidelity="exact-record",
            span=(0, 14),
            labels=("scenario",),
        ),
        context={},
        event_kind="scenario-source",
    )
    unadmitted_revision = str(unadmitted_archive["source"]["revision_id"])

    def item(
        item_id: str,
        dependencies: list[str],
        readout: Mapping[str, Any],
        path: str,
        binding: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "dependencies": list(dependencies),
            "item_id": item_id,
            "kind": "readout",
            "priority": 1,
            "readout": dict(readout),
            "support_paths": [path],
        }
        if binding is not None:
            row["source_binding"] = dict(binding)
        return row

    binding = {"source_revision_id": revision, "span": [4, 9]}

    def begin(episode_id: str, work_items: list[dict[str, Any]]) -> Mapping[str, Any]:
        return invoke(
            arm,
            f"s7-{episode_id}",
            operation="begin-reasoning",
            operation_id=f"s7-{episode_id}-operation",
            episode_id=episode_id,
            question={"kind": "source-span-provenance"},
            allocation=dict(ALLOCATION),
            assemblies=[dict(scene["assembly"])],
            hierarchy=dict(scene["hierarchy"]),
            program={"selection": {"method": "baseline"}, "work_items": work_items},
        )

    began = begin(
        "source-episode",
        [
            item("source-probe", [], bound_packet_readout(packets["L"]), "L"),
            item(
                "source-readout",
                ["source-probe"],
                bound_packet_readout(packets["L"]),
                "L",
                binding,
            ),
        ],
    )
    admitted = invoke(
        arm,
        "s7-admit",
        operation="admit-reasoning-input",
        operation_id="s7-admit-operation",
        episode_id="source-episode",
        inputs=[
            {
                "input_id": "input:source",
                "payload": {"content_sha256": revision},
                "source_revision_id": revision,
                "span": [0, 14],
            }
        ],
    )
    dispatched = invoke(
        arm,
        "s7-advance",
        operation="advance-reasoning",
        operation_id="s7-advance-operation",
        episode_id="source-episode",
    )
    terminal = invoke(
        arm,
        "s7-terminal",
        operation="advance-reasoning",
        operation_id="s7-terminal-operation",
        episode_id="source-episode",
    )
    episode = record(arm, "Obligation", "obligation:reasoning:source-episode")
    scheduler = episode["payload"]["scheduler"]
    snapshots = list(scheduler["snapshots"])
    bound_rows = [row for row in snapshots if row.get("selected") == "source-readout"]

    refusals: dict[str, Any] = {}

    def refused_episode(label: str, cited: Mapping[str, Any]) -> None:
        """Cite a citation the episode cannot support, with the window in between."""

        episode_id = f"source-refused-{label}"
        try:
            begin(
                episode_id,
                [
                    item("source-probe", [], bound_packet_readout(packets["L"]), "L"),
                    item(
                        "source-readout",
                        ["source-probe"],
                        bound_packet_readout(packets["L"]),
                        "L",
                        cited,
                    ),
                ],
            )
            invoke(
                arm,
                f"s7-{episode_id}-admit",
                operation="admit-reasoning-input",
                operation_id=f"s7-{episode_id}-admit-operation",
                episode_id=episode_id,
                inputs=[
                    {
                        "input_id": "input:source",
                        "payload": {"content_sha256": revision},
                        "source_revision_id": revision,
                        "span": [0, 14],
                    }
                ],
            )
            invoke(
                arm,
                f"s7-{episode_id}-advance",
                operation="advance-reasoning",
                operation_id=f"s7-{episode_id}-advance-operation",
                episode_id=episode_id,
            )
        except FieldIntelligenceError as exc:
            refusals[label] = {"code": exc.code, "message": str(exc)}

    refused_episode(
        "unadmitted_source",
        {"source_revision_id": unadmitted_revision, "span": [4, 9]},
    )
    refused_episode("span_outside_source", {"source_revision_id": revision, "span": [0, 30]})
    try:
        begin(
            "source-refused-unknown",
            [
                item(
                    "source-readout",
                    [],
                    bound_packet_readout(packets["L"]),
                    "L",
                    {"source_revision_id": "e" * 64, "span": [4, 9]},
                )
            ],
        )
    except FieldIntelligenceError as exc:
        refusals["unknown_revision"] = {"code": exc.code, "message": str(exc)}

    stages["s7_source_binding"] = {
        "admission": admitted["admitted"][0],
        "bound_row": bound_rows[0] if bound_rows else None,
        "completed_status": terminal.get("status"),
        "dispatch_status": dispatched.get("status"),
        "episode_begin_status": began.get("status"),
        "item_statuses": [
            {"item_id": row["item_id"], "status": row["status"]}
            for row in episode["payload"]["work_items"]
        ],
        "refusals": refusals,
        "source_revision_id": revision,
        "unadmitted_revision_id": unadmitted_revision,
        "work_item_binding": binding,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    arguments = parser.parse_args()
    root_path = arguments.receipt.with_suffix("")
    if root_path.exists():
        shutil.rmtree(root_path)
    root_path.mkdir(parents=True)
    scene = world()
    with open_field_session(
        root_path,
        role="worker",
        mode="scout",
        metadata={"program": "run_cassi_reasoning_scenario"},
    ) as field:
        owner = field.owner
        stage_one(owner, scene)
        stage_two(owner, scene)
        stage_three(owner, scene)
        stage_four(owner, scene)
        stage_five(scene)
        stage_six(owner)
        stage_seven(owner)
    arguments.receipt.write_text(
        json.dumps(stages, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    print(json.dumps(stages, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
