from dataclasses import asdict
import hashlib
import json
import math
import struct
from typing import Any, Literal

import torch

from cassi_bilateral_counterflow import (
    BasinReceipt,
    BilateralCounterflowConfig,
    BilateralCounterflowController,
    CounterflowTelemetry,
)
from cassi_grounded_language import make_grounded_action_command
from cassi_counterflow_runtime import DerivedCounterflowRuntime
from cassi_qi_bootstrap import canonical_hash
from cassi_qi_field import QiFieldState
from cassi_qi_world import DeterministicQiWorld


Mode = Literal[
    "counterflow",
    "uncoupled",
    "swapped",
    "same_up",
    "same_down",
    "single_stream",
    "constant",
    "fixed_phase",
    "reversed",
]
MODES: tuple[Mode, ...] = (
    "counterflow",
    "uncoupled",
    "swapped",
    "same_up",
    "same_down",
    "single_stream",
    "constant",
    "reversed",
    "fixed_phase",
)
SEQUENCE = (1, 2, 0, 3, 1)
RELATIONAL_ACTIONS = (
    "action.gaze-left",
    "action.gaze-right",
    "action.gaze-up",
    "action.gaze-down",
)
RELATIONAL_TARGET = (
    "action.gaze-right",
    "action.gaze-up",
    "action.gaze-right",
)
RELATIONAL_SOURCE_PREFIXES = (
    (),
    ("action.gaze-right", "action.gaze-right"),
    ("action.gaze-up", "action.gaze-up"),
    (
        "action.gaze-right",
        "action.gaze-right",
        "action.gaze-up",
        "action.gaze-up",
    ),
)
RELATIONAL_COMMAND_FIELD_SHA256 = hashlib.sha256(
    b"cassi.grounded-relational-composition.v1"
).hexdigest()


def _emit(kind: str, payload: dict[str, object]) -> None:
    print(json.dumps({"kind": kind, **payload}, sort_keys=True, separators=(",", ":")))


def _operators(dtype: torch.dtype = torch.complex128) -> tuple[torch.Tensor, ...]:
    a = torch.tensor(
        [[0, 0, 0, 1], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]],
        dtype=dtype,
    )
    b = torch.diag(torch.tensor([1, -1, 1j, -1j], dtype=dtype))
    c = torch.fft.fft(torch.eye(4, dtype=dtype), dim=0, norm="ortho")
    d = 0.5 * torch.tensor(
        [[1, 1, 1, 1], [1, -1, 1, -1], [1, 1, -1, -1], [1, -1, -1, 1]],
        dtype=dtype,
    )
    return a, b, c, d


def _train(
    controller: BilateralCounterflowController,
) -> tuple[QiFieldState, tuple[BasinReceipt, ...]]:
    state = controller.initial_state(dtype=torch.float64)
    basis = torch.eye(4, dtype=torch.complex128)
    receipts = []
    for operator in _operators():
        state, receipt = controller.observe_transitions(
            state,
            basis,
            torch.einsum("ij,nj->ni", operator, basis),
        )
        receipts.append(receipt)
    return state, tuple(receipts)

def _basin_id(receipt: BasinReceipt) -> int:
    if receipt.basin_id is None:
        raise RuntimeError("the fixed training scenario did not allocate a basin")
    return receipt.basin_id


def _trajectory(start: torch.Tensor) -> tuple[torch.Tensor, ...]:
    values = [start]
    operators = _operators()
    for index in SEQUENCE:
        values.append(operators[index] @ values[-1])
    return tuple(values)


def _run(
    mode: Mode,
    *,
    beam_width: int = 16,
) -> tuple[
    BilateralCounterflowController,
    QiFieldState,
    tuple[BasinReceipt, ...],
    tuple[CounterflowTelemetry, ...],
]:
    controller = BilateralCounterflowController(
        BilateralCounterflowConfig(
            slot_count=6,
            plan_beam_width=beam_width,
            ablation=mode,
        )
    )
    state, receipts = _train(controller)
    start = torch.tensor(
        [0.23 + 0.61j, -0.71 + 0.17j, 0.42 - 0.38j, 0.55 + 0.09j],
        dtype=torch.complex128,
    )
    values = _trajectory(start)
    state, trace = controller.run_until_closed(
        controller.start_thought(
            state,
            values[0],
            values[-1],
            active_slots=6,
            goal_mask=(1.0, 1.0, 1.0, 0.0),
            constraints={
                2: (values[2], (1.0, 0.0, 1.0, 0.0)),
                4: (values[4], (0.0, 1.0, 0.0, 1.0)),
            },
        )
    )
    return controller, state, receipts, trace


def _step_grounded(world: DeterministicQiWorld, action_id: str) -> None:
    acknowledgment = world.step(
        make_grounded_action_command(
            world,
            action_id,
            field_state_sha256=RELATIONAL_COMMAND_FIELD_SHA256,
        )
    )
    if acknowledgment.status != "applied":
        raise RuntimeError(f"grounded action {action_id} was not applied")


def _history_free(snapshot: dict[str, Any]) -> dict[str, Any]:
    body = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    body["tick_log"] = []
    return {
        **body,
        "snapshot_sha256": canonical_hash(body, "cassi.qi-world-snapshot.v1"),
    }


def _pose(world: DeterministicQiWorld) -> torch.Tensor:
    agent = world.snapshot()["state"]["agent"]
    x, y = (
        struct.unpack(">d", bytes.fromhex(str(value)[4:]))[0]
        for value in agent[:2]
    )
    # ponytail: interior affine pose only; add boundary-role features if clamp
    # transfer becomes a measured requirement.
    return torch.tensor((x, y, 1.0, x * y), dtype=torch.complex128)


def _world(
    *,
    seed: int,
    world_id: str,
    episode_id: str,
) -> DeterministicQiWorld:
    return DeterministicQiWorld(
        seed=seed,
        world_id=world_id,
        episode_id=episode_id,
    )


def _source_snapshot(
    prefix: tuple[str, ...],
    *,
    seed: int,
    world_id: str,
    episode_id: str,
) -> dict[str, Any]:
    world = _world(seed=seed, world_id=world_id, episode_id=episode_id)
    for action_id in prefix:
        _step_grounded(world, action_id)
    return _history_free(world.snapshot())


def run_grounded_relational_transfer() -> dict[str, object]:
    controller = BilateralCounterflowController(
        BilateralCounterflowConfig(
            slot_count=4,
            merge_residual=0.02,
            separate_residual=0.05,
            action_residual_tolerance=0.04,
        )
    )
    state = controller.initial_state(dtype=torch.float64)
    training_identity = {
        "seed": 41,
        "world_id": "world.relation-training",
        "episode_id": "episode.relation-training",
    }
    source_snapshots = [
        _source_snapshot(prefix, **training_identity)
        for prefix in RELATIONAL_SOURCE_PREFIXES
    ]
    training_poses = set()
    for snapshot in source_snapshots:
        source = _world(**training_identity)
        source.restore(snapshot)
        training_poses.add(tuple(float(value.real) for value in _pose(source)[:2]))
    action_basins: dict[str, int] = {}
    source_execution_action_counts: list[int] = []
    for action_id in RELATIONAL_ACTIONS:
        before_values = []
        after_values = []
        for snapshot in source_snapshots:
            source = _world(**training_identity)
            source.restore(snapshot)
            before_values.append(_pose(source))
            _step_grounded(source, action_id)
            after_values.append(_pose(source))
            source_execution_action_counts.append(len(source.snapshot()["tick_log"]))
        state, receipt = controller.observe_transitions(
            state,
            torch.stack(before_values),
            torch.stack(after_values),
        )
        if receipt.basin_id is None:
            raise RuntimeError(
                f"{action_id} produced {receipt.decision} without an operator basin"
            )
        action_basins[action_id] = receipt.basin_id
    if (
        len(set(action_basins.values())) != len(RELATIONAL_ACTIONS)
        or set(source_execution_action_counts) != {1}
    ):
        raise RuntimeError("grounded action sources were not isolated field operators")

    holdout_identity = {
        "seed": 97,
        "world_id": "world.relation-holdout",
        "episode_id": "episode.relation-holdout",
    }
    holdout_start = _source_snapshot(
        (
            "action.gaze-left",
            "action.gaze-left",
            "action.gaze-up",
            "action.gaze-up",
            "action.gaze-up",
        ),
        **holdout_identity,
    )
    generator = _world(**holdout_identity)
    generator.restore(holdout_start)
    holdout_values = [_pose(generator)]
    holdout_revisions = [generator.state_sha256]
    for action_id in RELATIONAL_TARGET:
        _step_grounded(generator, action_id)
        holdout_values.append(_pose(generator))
        holdout_revisions.append(generator.state_sha256)
    holdout_pose = tuple(float(value.real) for value in holdout_values[0][:2])
    if holdout_pose in training_poses:
        raise RuntimeError("relational holdout pose overlaps a training source")

    checkpoint = controller.dump_state_bytes(state)
    restored = controller.load_state_bytes(checkpoint)
    active = controller.start_thought(
        restored,
        holdout_values[0],
        holdout_values[-1],
        active_slots=4,
        constraints={
            1: (holdout_values[1], (1.0, 1.0, 1.0, 1.0)),
            2: (holdout_values[2], (1.0, 1.0, 1.0, 1.0)),
        },
        eligible_basins=tuple(action_basins.values()),
    )
    _, trace = controller.run_until_closed(active)
    final = trace[-1]
    basin_actions = {
        basin_id: action_id for action_id, basin_id in action_basins.items()
    }
    selected_actions = tuple(
        basin_actions[basin_id] for basin_id in final.winning_basins
    )
    if final.status != "settled" or selected_actions != RELATIONAL_TARGET:
        raise RuntimeError(
            f"relational holdout settled {selected_actions} with {final.status}"
        )

    execution = _world(**holdout_identity)
    execution.restore(holdout_start)
    for action_id in selected_actions:
        _step_grounded(execution, action_id)
    if execution.state_sha256 != holdout_revisions[-1]:
        raise RuntimeError("relational composition missed the exact held-out world goal")
    if controller.dump_state_bytes(restored) != checkpoint:
        raise RuntimeError("relational inference mutated the restored field memory")

    removed_basin = action_basins["action.gaze-up"]
    ablated = controller.clear_basin(restored, removed_basin)
    _, ablated_trace = controller.run_until_closed(
        controller.start_thought(
            ablated,
            holdout_values[0],
            holdout_values[-1],
            active_slots=4,
            constraints={
                1: (holdout_values[1], (1.0, 1.0, 1.0, 1.0)),
                2: (holdout_values[2], (1.0, 1.0, 1.0, 1.0)),
            },
            eligible_basins=tuple(
                basin_id
                for basin_id in action_basins.values()
                if basin_id != removed_basin
            ),
        )
    )
    ablated_final = ablated_trace[-1]
    if ablated_final.status == "settled":
        raise RuntimeError("missing relational operator did not force abstention")

    return {
        "result": "GROUNDED_RELATIONAL_COMPOSITION_OK",
        "representation": "fixed physical [x,y,1,xy] relation frame",
        "action_labels_in_field_features": False,
        "live_provider_descriptor_law": "unchanged_exact_address_only",
        "training_world_id": training_identity["world_id"],
        "holdout_world_id": holdout_identity["world_id"],
        "holdout_pose": holdout_pose,
        "holdout_pose_seen_in_training": False,
        "source_execution_action_counts": source_execution_action_counts,
        "complete_trajectory_observed": False,
        "target_actions": list(RELATIONAL_TARGET),
        "settled_actions": list(selected_actions),
        "exact_goal_revision": holdout_revisions[-1],
        "exact_goal_reached": True,
        "status": final.status,
        "iterations": len(trace),
        "best_plan_residual": final.best_plan_residual,
        "constraint_residual": final.constraint_residual,
        "field_memory_frozen": len(
            {item.basin_region_sha256 for item in trace}
        ) == 1,
        "checkpoint_restart_exact": controller.dump_state_bytes(restored) == checkpoint,
        "removed_basin": removed_basin,
        "ablation_status": ablated_final.status,
        "ablation_plan": list(ablated_final.winning_basins),
    }


def main() -> None:
    controller, state, receipts, trace = _run("counterflow")
    for experience_index, receipt in enumerate(receipts):
        record = asdict(receipt)
        if not math.isfinite(record["best_residual"]):
            record["best_residual"] = None
        _emit("training", {"experience_index": experience_index, **record})
    for telemetry in trace:
        _emit("refinement", asdict(telemetry))

    expected = tuple(_basin_id(receipts[index]) for index in SEQUENCE)
    final = trace[-1]
    _emit(
        "result",
        {
            "status": final.status,
            "winning_basins": final.winning_basins,
            "expected_basins": expected,
            "correct": final.winning_basins == expected,
            "active_slot_count": final.active_slot_count,
            "iterations": len(trace),
            "beam_survivors": final.beam_survivor_count,
            "evaluated_plan_extensions": final.evaluated_plan_extensions,
            "beam_widths": final.beam_widths,
            "normalized_beam_entropy": final.normalized_beam_plan_entropy,
            "best_plan_residual": final.best_plan_residual,
            "valid_plan_count": final.valid_plan_count,
            "search_mode": final.search_mode,
            "max_cycle_residual": max(final.cycle_residuals),
            "exhaustive_complete_plans": len(receipts) ** (final.active_slot_count - 1),
            "memory_frozen": len({item.basin_region_sha256 for item in trace}) == 1,
            "checkpoint_bytes": len(controller.dump_state_bytes(state)),
        },
    )

    summaries = {"counterflow": final}
    for mode in MODES[1:]:
        _, _, _, control_trace = _run(mode)
        summaries[mode] = control_trace[-1]
    for mode in MODES:
        telemetry = summaries[mode]
        _emit(
            "control",
            {
                "mode": mode,
                "status": telemetry.status,
                "winning_basins": telemetry.winning_basins,
                "energy": telemetry.energy,
                "constraint_residual": telemetry.constraint_residual,
                "iterations": telemetry.refinement_step,
                "evaluated_plan_extensions": telemetry.evaluated_plan_extensions,
            },
        )

    narrow_controller, narrow_state, _, narrow_trace = _run(
        "counterflow",
        beam_width=1,
    )
    narrow_final = narrow_trace[-1]
    _emit(
        "beam_control",
        {
            "beam_width": narrow_controller.config.plan_beam_width,
            "status": narrow_final.status,
            "winning_basins": narrow_final.winning_basins,
            "expected_basins": expected,
            "evaluated_plan_extensions": narrow_final.evaluated_plan_extensions,
        },
    )

    start = torch.tensor(
        [0.23 + 0.61j, -0.71 + 0.17j, 0.42 - 0.38j, 0.55 + 0.09j],
        dtype=torch.complex128,
    )
    values = _trajectory(start)
    macro_state, macro_receipt = controller.consolidate_plan(state)
    if macro_receipt.basin_id is None:
        raise RuntimeError("the integration scenario requires one free macro basin")
    macro_id = macro_receipt.basin_id
    _, macro_trace = controller.run_until_closed(
        controller.start_thought(
            macro_state,
            values[0],
            values[-1],
            active_slots=2,
            goal_mask=(1.0, 1.0, 1.0, 0.0),
            eligible_basins=(macro_id,),
        )
    )
    _emit(
        "macro",
        {
            **asdict(macro_receipt),
            "direct_status": macro_trace[-1].status,
            "direct_plan": macro_trace[-1].winning_basins,
            "direct_iterations": len(macro_trace),
        },
    )

    runtime = DerivedCounterflowRuntime()

    def runtime_identity(label: str, position: int) -> dict[str, object]:
        record_id = f"runtime:{label}"
        revision = hashlib.sha256(f"revision:{label}".encode()).hexdigest()
        start = position * 16
        end = start + len(label.encode())
        semantic_kind = "field-transition"
        encoded = json.dumps(
            [
                "cassicore.mnemic.counterflow-address.v1",
                record_id,
                revision,
                start,
                end,
                semantic_kind,
            ],
            separators=(",", ":"),
        ).encode()
        return {
            "record_id": record_id,
            "address": hashlib.sha256(encoded).digest()[:16].hex(),
            "revision": revision,
            "start_byte": start,
            "end_byte": end,
            "semantic_kind": semantic_kind,
        }

    runtime_identities = [
        runtime_identity(f"state-{position}", position) for position in range(6)
    ]
    runtime_observations = [
        {
            "id": f"observed-{position}",
            "before": runtime_identities[position],
            "after": runtime_identities[position + 1],
            "symbol": f"op-{position}",
            "action": {
                "id": f"apply-op-{position}",
                "kind": "field-transition",
                "required_authority": 1.0,
                "reversible": True,
            },
        }
        for position in range(5)
    ]
    runtime_request = {
        "mode": "plan",
        "observations": runtime_observations,
        "trajectory": [
            {
                **identity,
                "mask": [1.0, 1.0, 1.0, 1.0],
                "authority": 1.0,
                "required": True,
            }
            for identity in runtime_identities
        ],
        "policy": {
            "eligible_observation_ids": [
                observation["id"] for observation in runtime_observations
            ],
            "permitted_action_kinds": ["field-transition"],
            "authority": 1.0,
            "authorization_path": [
                "thalamus:reasoning",
                "owner:execute-separately",
            ],
        },
        "consolidate_macro": True,
    }
    primary_field_sha256 = hashlib.sha256(
        controller.dump_state_bytes(state)
    ).hexdigest()
    runtime_result = runtime.plan(
        runtime_request,
        primary_field_sha256=primary_field_sha256,
    )
    no_data_result = runtime.plan(
        {"mode": "plan", "observations": [], "trajectory": [], "policy": {}},
        primary_field_sha256=primary_field_sha256,
    )
    _emit(
        "consolidated_runtime",
        {
            "status": runtime_result["status"],
            "derived": runtime_result["derived"],
            "persistent_state": runtime_result["persistent_state"],
            "primary_field_sha256": runtime_result["primary_field_sha256"],
            "companion_shape": runtime_result["companion_shape"],
            "inference_memory_frozen": runtime_result["inference_memory_frozen"],
            "plan": runtime_result["plan"],
            "symbolic": runtime_result["symbolic"],
            "action_proposal": runtime_result["action_proposal"],
            "macro": runtime_result["macro"],
            "no_data_status": no_data_result["status"],
        },
    )

    relational = run_grounded_relational_transfer()
    _emit("grounded_relational_transfer", relational)


    idle, _ = _train(controller)
    first_required = _basin_id(receipts[SEQUENCE[0]])
    reduced = controller.clear_basin(idle, first_required)
    start = values[0]
    _, ablated_trace = controller.run_until_closed(
        controller.start_thought(
            reduced,
            values[0],
            values[-1],
            active_slots=6,
            goal_mask=(1.0, 1.0, 1.0, 0.0),
            constraints={
                2: (values[2], (1.0, 0.0, 1.0, 0.0)),
                4: (values[4], (0.0, 1.0, 0.0, 1.0)),
            },
        )
    )
    _emit(
        "required_basin_control",
        {
            "cleared_basin": first_required,
            "status": ablated_trace[-1].status,
            "winning_basins": ablated_trace[-1].winning_basins,
            "expected_basins": expected,
        },
    )

    passed = (
        final.status == "settled"
        and final.winning_basins == expected
        and final.active_slot_count == 6
        and len(trace) == controller.config.breath_steps
        and final.beam_survivor_count == 8
        and final.evaluated_plan_extensions == 348 < len(receipts) ** 5
        and len({item.basin_region_sha256 for item in trace}) == 1
        and not any(item.clamp_count for item in trace)
        and final.energy < summaries["uncoupled"].energy
        and final.energy < summaries["same_down"].energy
        and all(
            summaries[mode].status == "exhausted"
            for mode in (
                "swapped",
                "same_up",
                "single_stream",
                "constant",
                "reversed",
                "fixed_phase",
            )
        )
        and tuple(narrow_state.field.shape) == tuple(state.field.shape)
        and narrow_final.status == "settled"
        and narrow_final.winning_basins == expected
        and narrow_final.evaluated_plan_extensions == 44
        and ablated_trace[-1].winning_basins != expected
        and macro_trace[-1].status == "settled"
        and macro_trace[-1].winning_basins == (macro_id,)
        and runtime_result["status"] == "settled"
        and runtime_result["symbolic"]["symbols"]
        == [f"op-{position}" for position in range(5)]
        and runtime_result["action_proposal"]["inert"]
        and runtime_result["action_proposal"]["action_ids"]
        == [f"apply-op-{position}" for position in range(5)]
        and runtime_result["macro"]["persisted"] is False
        and runtime_result["inference_memory_frozen"]
        and no_data_result["status"] == "no_transition_data"
        and relational["result"] == "GROUNDED_RELATIONAL_COMPOSITION_OK"
        and relational["status"] == "settled"
        and relational["exact_goal_reached"] is True
        and relational["ablation_status"] != "settled"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
