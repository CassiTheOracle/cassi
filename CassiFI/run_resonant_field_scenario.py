from __future__ import annotations

"""Exercise the production resonant owner with isolated, controlled evidence."""

import argparse
import hashlib
import json
import tempfile
from dataclasses import replace
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Mapping

import numpy as np
import torch

from cassi_field_atlas import (
    AtlasState,
    FieldIntelligenceError,
    RelationChart,
    VariableSpec,
    canonical_json_bytes,
    sha256_value,
)
from cassi_field_cognition import ActionReadout
from cassi_field_owner import (
    AuthorityGrant,
    DeterministicWorldAdapter,
    FieldIntelligenceOwner,
    SourceInput,
    WorldAcknowledgment,
)
from cassi_resonant_field import (
    ResonantProfile,
    ResonantWorkspace,
    advance_workspace,
    advance_workspace_gpu,
    expand_resolution,
    initial_workspace,
    inspect_workspace,
    measure_body_response,
    reduce_resolution,
    ResonantNumericalError,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def observation(name: str, values: Mapping[str, float]) -> SourceInput:
    return SourceInput(
        source_id=name,
        content=canonical_json_bytes(dict(values)),
        media_type="application/json",
        codec="utf-8",
        observed_timestamp=name,
        scope="resonant-scenario",
        claim_category="controlled-measurement",
        fidelity="exact-record",
        labels=("resonant-scenario",),
    )


def exercise_owner(data_home: Path) -> Mapping[str, Any]:
    owner = FieldIntelligenceOwner(data_home)
    effects: list[Mapping[str, Any]] = []
    try:
        for name in ("bias", "input", "output"):
            variable = (
                VariableSpec(name, kind="constant", constant=1.0)
                if name == "bias"
                else VariableSpec(name, lower=-40.0, upper=40.0)
            )
            owner.configure_variable(f"configure:variable:{name}", variable)
        owner.configure_chart(
            "configure:relation",
            RelationChart.empty(
                chart_id="measured-gain",
                scope=("bias", "input", "output"),
                ridge=1e-5,
                observation_norm_bound=100.0,
                prior_mass=1e-3,
            ),
        )
        revisions = []
        for index, value in enumerate((-4.0, -3.0, -2.0, -1.0, 1.0, 2.0, 3.0, 4.0)):
            values = {"bias": 1.0, "input": value, "output": 2.0 * value}
            admitted = owner.admit_observation(
                operation_id=f"learn:{index}",
                source=observation(f"measurement:{index}", values),
                values=values,
                context={},
            )
            revisions.append(admitted["source"]["revision_id"])

        memory_before = tuple(chart.as_dict() for chart in owner.state.charts)
        evidence_tick = owner.state.logical_tick
        pages_before = owner.state.object_pages()
        wave_before = owner.state.resonant_workspace.state_sha256
        started = perf_counter_ns()
        pulse = owner.advance(operation_id="body:initial", ticks=32)
        pulse_elapsed_ns = perf_counter_ns() - started
        wave_after = owner.state.resonant_workspace.state_sha256
        require(wave_after != wave_before, "powered body did not advance its canonical field")
        require(owner.state.logical_tick == evidence_tick, "rhythm advanced evidence time")
        pulse_head = owner.state.state_sha256
        replay = owner.advance(operation_id="body:initial", ticks=32)
        require(owner.state.state_sha256 == pulse_head, "retry duplicated the heartbeat")
        require(
            replay["resonance_receipt"] == pulse["resonance_receipt"]
            and replay["checkpoint_receipt"] == {**pulse["checkpoint_receipt"], "replayed": True},
            "advance replay did not identify the same committed transition",
        )

        started = perf_counter_ns()
        thought = owner.think(
            operation_id="think:held-out-gain",
            observed={"input": 1.75},
            requested=("output",),
        )
        think_elapsed_ns = perf_counter_ns() - started
        require(thought["status"] == "supported", "held-out learned relation remained unresolved")
        predicted = thought["branches"][0]["values"]["output"]
        require(abs(predicted - 3.5) < 1e-3, "resonant answer changed the learned conditional relation")
        require(
            tuple(chart.as_dict() for chart in owner.state.charts) == memory_before,
            "inference changed learned chart bytes or support",
        )
        require(owner.state.logical_tick == evidence_tick, "thinking consumed an observation again")
        read_head = owner.state.state_sha256
        prepared = owner.query(query_id=thought["query_id"])
        require(prepared["branches"] == thought["branches"], "prepared readout differed from thought")
        snapshot = owner.inspect_resonance()
        require(owner.state.state_sha256 == read_head, "inspection advanced the owner")

        root_bytes = owner.state.encode()
        objects = owner.state.object_pages()
        bundle = owner.state.encode_bundle()
        require(AtlasState.decode_bundle(bundle).encode() == root_bytes, "standalone bundle changed state")
        damaged = dict(objects)
        damaged_key = next(iter(damaged))
        damaged[damaged_key] += b"corruption"
        corrupt_rejected = False
        try:
            AtlasState.decode(root_bytes, objects=damaged)
        except (FieldIntelligenceError, ValueError):
            corrupt_rejected = True
        require(corrupt_rejected, "page corruption was accepted")

        exact_wave = owner.state.resonant_workspace.state_sha256
        owner.close()
        owner = FieldIntelligenceOwner(data_home)
        require(owner.state.encode() == root_bytes, "owner restart changed canonical bytes")
        require(owner.state.resonant_workspace.state_sha256 == exact_wave, "restart lost working phase")
        require(owner.query(query_id=thought["query_id"])["branches"] == prepared["branches"], "restart lost prepared thought")
        readout = ActionReadout(
            readout_id="measured-sign",
            version=1,
            labels=("negative", "positive"),
            coefficients=({"output": -1.0}, {"output": 1.0}),
            observed_error_radius=0.001,
        )
        proposal = owner.propose_effect(
            operation_id="effect:measured-sign",
            observed={"input": 1.75},
            readout=readout,
            target="controlled-sign-recorder",
            scope="resonant-scenario",
            payload={"record": "held-out"},
        )
        require(proposal["status"] == "proposed", "supported phase-space readout could not propose action")
        proposed_head = owner.state.state_sha256
        owner.advance(operation_id="body:while-effect-pending", ticks=2)
        require(owner.state.state_sha256 != proposed_head, "pending action stopped unrelated body evolution")

        def execute(action: str, target: str, payload: Mapping[str, Any]) -> WorldAcknowledgment:
            effects.append({"action": action, "target": target, "payload": dict(payload)})
            return WorldAcknowledgment(
                acknowledgment_id="measured-sign:ack",
                operation_id="effect:measured-sign",
                status="succeeded",
                observed_values={"input": 1.75, "output": 3.5},
                context={},
                source_content=canonical_json_bytes(effects[-1]),
            )

        adapter = DeterministicWorldAdapter(execute)
        grant = AuthorityGrant(
            grant_id="controlled-sign-grant",
            issuer="scenario",
            generation=owner.authority_generation,
            operation="effect",
            target="controlled-sign-recorder",
            scope="resonant-scenario",
        )
        prediction_id = proposal["prediction"]["prediction_id"]
        dispatched = owner.dispatch_effect(prediction_id=prediction_id, grant=grant, adapter=adapter)
        require(dispatched["status"] == "acknowledged", "body heartbeat invalidated a frozen action")
        require(len(effects) == 1 and effects[0]["action"] == "positive", "wrong or repeated controlled effect")
        owner.close()
        owner = FieldIntelligenceOwner(data_home)
        effect_replay = owner.dispatch_effect(prediction_id=prediction_id, grant=grant, adapter=adapter)
        require(effect_replay["status"] == "already-acknowledged" and len(effects) == 1, "effect repeated after restart")

        fresh = owner.think(operation_id="think:before-forget", observed={"input": 1.75}, requested=("output",))
        old_manifest = owner.checkpoints.current_manifest_sha256
        preview = owner.preview_forget((revisions[0],))
        forgotten = owner.forget(
            operation_id="forget:measurement",
            preview_id=preview["preview_id"],
            revision_ids=(revisions[0],),
            grant=AuthorityGrant(
                grant_id="forget:controlled",
                issuer="scenario",
                generation=owner.authority_generation,
                operation="forget",
                target=sha256_value(sorted((revisions[0],))),
                scope="resonant-scenario",
            ),
            scope="resonant-scenario",
        )
        stale_query_rejected = False
        try:
            stale = owner.query(query_id=fresh["query_id"])
            stale_query_rejected = stale["status"] != "supported"
        except FieldIntelligenceError:
            stale_query_rejected = True
        require(stale_query_rejected, "revoked prepared wave remained usable")
        rollback_rejected = False
        try:
            owner.checkpoints.load_version(old_manifest)
        except FieldIntelligenceError as error:
            rollback_rejected = error.code == "STALE_REVOCATION"
        require(rollback_rejected, "old checkpoint revived revoked phase influence")
        remaining = owner.think(operation_id="think:remaining-support", observed={"input": 1.75}, requested=("output",))
        require(remaining["status"] == "supported", "forgetting destroyed unrelated retained support")
        recalled = owner.exact_recall(revision_id=revisions[1], allowed_labels=frozenset({"resonant-scenario"}))
        return {
            "held_out_prediction": predicted,
            "held_out_target": 3.5,
            "think_elapsed_ns": think_elapsed_ns,
            "pulse_elapsed_ns": pulse_elapsed_ns,
            "pulse": pulse,
            "snapshot": snapshot,
            "root_descriptor_bytes": len(root_bytes),
            "reachable_page_bytes": sum(map(len, objects.values())),
            "reused_page_count": len(set(pages_before) & set(objects)),
            "bundle_bytes": len(bundle),
            "corrupt_page_rejected": corrupt_rejected,
            "advance_replayed_exactly": True,
            "chart_memory_unchanged": True,
            "evidence_clock_unchanged_by_rhythm": True,
            "restart_exact": True,
            "frozen_action_survived_heartbeat": True,
            "controlled_effect_count": len(effects),
            "revoked_query_rejected": stale_query_rejected,
            "revoked_checkpoint_rejected": rollback_rejected,
            "forgotten": forgotten["adaptive_forgetting"],
            "retained_source_sha256": recalled["content_sha256"],
            "remaining_prediction": remaining["branches"][0]["values"]["output"],
        }
    finally:
        owner.close()


def _vector(workspace: ResonantWorkspace) -> np.ndarray:
    lanes = np.asarray(workspace.field).reshape(-1, 9)
    return np.concatenate(tuple(lanes[:-1, lane] for lane in range(4)))


def _seed(profile: ResonantProfile, vector: np.ndarray) -> ResonantWorkspace:
    page = np.zeros(profile.page_shape, dtype=np.float64)
    lanes = page.reshape(-1, 9)
    for lane, values in enumerate(np.split(vector, 4)):
        lanes[:-1, lane] = values
    return ResonantWorkspace(profile=profile, field_page=page)


def _frozen_generator(profile: ResonantProfile) -> np.ndarray:
    """Independent RU1/RU2 reconstruction for an empty, linear body at rest."""
    n = profile.port_count
    rail = np.zeros((2 * n, 2 * n))
    for source, destination, weight, _ in profile.edges:
        rail[destination, source] += weight
        rail[source, destination] -= weight
    if profile.projected_transport is not None:
        rail = np.asarray(profile.projected_transport)
    identity = np.eye(2 * n)
    poisson = np.block([[rail, identity], [-identity, rail]])
    potential = np.block(
        [
            [np.eye(n) * (1 + profile.relative_stiffness) / 2, np.eye(n) * (1 - profile.relative_stiffness) / 2],
            [np.eye(n) * (1 - profile.relative_stiffness) / 2, np.eye(n) * (1 + profile.relative_stiffness) / 2],
        ]
    )
    hessian = np.zeros((4 * n, 4 * n))
    hessian[:2 * n, :2 * n] = potential
    hessian[2 * n:, 2 * n:] = np.diag(1 / np.asarray(profile.inertances))
    if profile.projected_inv_mass is not None:
        inverse_mass = np.asarray(profile.projected_inv_mass)
        hessian[2 * n:, 2 * n:] = np.diag(inverse_mass) if inverse_mass.ndim == 1 else inverse_mass
    return (poisson - np.eye(4 * n) * profile.damping) @ hessian


def _transfer_measurement(profile: ResonantProfile) -> Mapping[str, Any]:
    generator = _frozen_generator(profile)
    n = profile.port_count
    inputs = np.zeros((4 * n, 7))
    outputs = np.zeros((7, 4 * n))
    for pool in range(7):
        port = pool * profile.ports_per_pool
        inputs[2 * n + port, pool] = inputs[3 * n + port, pool] = 1 / np.sqrt(2)
        outputs[pool, port] = outputs[pool, n + port] = 1 / np.sqrt(2)
    frequencies = np.linspace(0.15, 1.25, 241)
    spectra = np.empty((len(frequencies), 7))
    localization = np.empty_like(spectra)
    identity = np.eye(4 * n)
    for index, frequency in enumerate(frequencies):
        response = np.linalg.solve(1j * frequency * identity - generator, inputs)
        spectra[index] = np.abs(np.diag(outputs @ response))
        port_power = np.abs(response.reshape(4, n, 7)) ** 2
        pool_power = port_power.sum(axis=0).reshape(7, profile.ports_per_pool, 7).sum(axis=1)
        localization[index] = np.diag(pool_power) / pool_power.sum(axis=0)
    peaks = []
    for pool in range(7):
        peak = int(np.argmax(spectra[:, pool]))
        threshold = spectra[peak, pool] / np.sqrt(2)
        left = right = peak
        while left > 0 and spectra[left - 1, pool] >= threshold:
            left -= 1
        while right + 1 < len(frequencies) and spectra[right + 1, pool] >= threshold:
            right += 1
        peaks.append(
            {
                "pool": pool,
                "frequency": float(frequencies[peak]),
                "amplitude": float(spectra[peak, pool]),
                "half_power_bandwidth": float(frequencies[right] - frequencies[left]),
                "localization_fraction": float(localization[peak, pool]),
            }
        )
    require(len({row["frequency"] for row in peaks}) == 7, "seven cavity responses merged")
    require(min(row["localization_fraction"] for row in peaks) > 1 / 7, "pool response was not locally concentrated")
    return {
        "frozen_rest_operator": True,
        "frequency_grid_spacing": float(frequencies[1] - frequencies[0]),
        "angular_field_time_units": True,
        "peaks": peaks,
    }


def exercise_numerics() -> Mapping[str, Any]:
    profile = ResonantProfile()
    linear_profile = replace(profile, beta=0.0)
    n = profile.port_count
    seed = np.sin(np.arange(4 * n) * 0.71) * 0.025
    initial = _seed(linear_profile, seed)
    evolved, linear_receipt = advance_workspace(initial, ticks=1, source_enabled=False)
    generator = _frozen_generator(linear_profile)
    identity = np.eye(4 * n)
    cayley = np.linalg.solve(
        identity - profile.time_step * generator / 2,
        (identity + profile.time_step * generator / 2) @ seed,
    )
    generator_error = float(np.max(np.abs(_vector(evolved) - cayley)))
    require(generator_error < 1e-8, "actual time evolution disagrees with independently reconstructed RU1/RU2")
    restarted = ResonantWorkspace.from_dict(evolved.as_dict())
    continued, _ = advance_workspace(evolved, ticks=3, source_enabled=False)
    replayed, _ = advance_workspace(restarted, ticks=3, source_enabled=False)
    require(continued.state_sha256 == replayed.state_sha256, "same-profile wave restart changed the next transition")

    passive, passive_receipt = advance_workspace(_seed(profile, seed), ticks=64, source_enabled=False)
    require(passive_receipt["end_energy"] < passive_receipt["start_energy"], "passive field did not dissipate")
    require(abs(passive_receipt["balance_defect"]) < 1e-8, "nonlinear discrete work accounting failed")
    started = perf_counter_ns()
    powered, power_receipt = advance_workspace(initial_workspace(profile), ticks=256)
    powered_elapsed = perf_counter_ns() - started
    require(power_receipt["positive_heartbeat_work"] > 0, "heartbeat supplied no measured work")
    require(abs(power_receipt["balance_defect"]) < 1e-8, "powered work ledger failed")
    source_off, off_receipt = advance_workspace(powered, ticks=512, source_enabled=False)
    require(off_receipt["end_energy"] < off_receipt["start_energy"], "source-off state failed to decay")
    powered_snapshot = inspect_workspace(powered)
    off_snapshot = inspect_workspace(source_off)
    require(abs(powered_snapshot["cycle_power"]) > 1e-14, "powered graph had no signed circulation")

    rest, _ = advance_workspace(initial_workspace(profile), ticks=64, demand=0.0, source_enabled=False)
    busy, _ = advance_workspace(initial_workspace(profile), ticks=64, demand=0.8, source_enabled=False)
    require(busy.activity > rest.activity and busy.breath_phase > rest.breath_phase, "ready workload did not change breath")

    expanded, expansion = expand_resolution(passive)
    old_lanes = passive.field.reshape(-1, 9)[:-1].reshape(7, profile.ports_per_pool, 9)
    new_lanes = expanded.field.reshape(-1, 9)[:-1].reshape(7, expanded.profile.ports_per_pool, 9)
    require(np.array_equal(old_lanes, new_lanes[:, :profile.ports_per_pool]), "resolution expansion changed existing coordinates")
    require(not np.any(new_lanes[:, profile.ports_per_pool:]), "new resolution contained invented state")

    controls = {}
    for topology in ("undivided", "isolated", "meaningful-helix", "rewired"):
        control_profile = replace(linear_profile, topology=topology)
        started = perf_counter_ns()
        control, receipt = advance_workspace(_seed(control_profile, seed), ticks=16, source_enabled=False)
        controls[topology] = {
            "field_bytes": control.field.nbytes,
            "elapsed_ns": perf_counter_ns() - started,
            "operator_applications": receipt["operator_applications"],
            "end_energy": receipt["end_energy"],
            "common_coordinate_pool_zero": float((_vector(control)[0] + _vector(control)[n]) / np.sqrt(2)),
            "edge_count": len(control_profile.edges),
            "edge_strength_l1": sum(abs(edge[2]) for edge in control_profile.edges),
        }
    require(len({row["field_bytes"] for row in controls.values()}) == 1, "topology control storage differed")
    require(controls["meaningful-helix"]["edge_count"] == controls["rewired"]["edge_count"], "rewiring changed edge count")
    require(abs(controls["meaningful-helix"]["edge_strength_l1"] - controls["rewired"]["edge_strength_l1"]) < 1e-12, "rewiring changed total strength")
    topology_difference = abs(controls["meaningful-helix"]["common_coordinate_pool_zero"] - controls["rewired"]["common_coordinate_pool_zero"])
    require(topology_difference > 1e-10, "directional organization had no measured effect")

    cpu_started = perf_counter_ns()
    cpu, cpu_receipt = advance_workspace(initial, ticks=8, source_enabled=False)
    cpu_elapsed = perf_counter_ns() - cpu_started
    torch.cuda.synchronize()
    gpu_started = perf_counter_ns()
    gpu, gpu_receipt = advance_workspace_gpu(initial, ticks=8, source_enabled=False, device="cuda")
    torch.cuda.synchronize()
    gpu_elapsed = perf_counter_ns() - gpu_started
    gpu_error = float(np.max(np.abs(_vector(cpu) - _vector(gpu))))
    require(gpu_error < 1e-8, "GPU phase/readout diverged outside the declared allowance")
    transfer = _transfer_measurement(linear_profile)
    calibration = measure_body_response(profile)
    calibration_error = max(
        abs(actual["frequency"] - reference["frequency"])
        for actual, reference in zip(calibration["peaks"], transfer["peaks"])
    )
    require(calibration_error <= transfer["frequency_grid_spacing"], "viewer calibration disagrees with independent body operator")
    return {
        "independent_generator_step_error": generator_error,
        "linear_step": linear_receipt,
        "nonlinear_passive": passive_receipt,
        "powered": power_receipt,
        "powered_elapsed_ns": powered_elapsed,
        "source_off": off_receipt,
        "powered_cycle_power": powered_snapshot["cycle_power"],
        "source_off_cycle_power": off_snapshot["cycle_power"],
        "rest_activity": rest.activity,
        "ready_activity": busy.activity,
        "rest_breath_phase": rest.breath_phase,
        "ready_breath_phase": busy.breath_phase,
        "expansion": expansion,
        "topology_controls": controls,
        "topology_readout_difference": topology_difference,
        "cpu_gpu": {
            "cpu_elapsed_ns": cpu_elapsed,
            "gpu_elapsed_ns": gpu_elapsed,
            "maximum_coordinate_error": gpu_error,
            "cpu_receipt": cpu_receipt,
            "gpu_receipt": gpu_receipt,
            "device_name": torch.cuda.get_device_name(0),
        },
        "transfer": transfer,
        "viewer_calibration": calibration,
        "viewer_calibration_frequency_error": calibration_error,
    }


def _phase_trajectory(profile: ResonantProfile, phase: float) -> Mapping[str, Any]:
    """A controlled two-pool transition, with no learned target in its input."""
    n = profile.port_count
    source = profile.ports_per_pool - 1
    destination = source + 1
    vector = np.zeros(4 * n)
    vector[source] = float(np.cos(phase))
    vector[2 * n + source] = float(np.sin(phase))
    initial = _seed(profile, vector)
    advanced, receipt = advance_workspace(
        initial, ticks=24, source_enabled=False, demand=0.0
    )
    target = float(_vector(advanced)[destination])
    return {
        "initial": initial,
        "advanced": advanced,
        "source_port": source,
        "destination_port": destination,
        "target": target,
        "receipt": receipt,
    }

def exercise_phase_learning(data_home: Path) -> Mapping[str, Any]:
    """Learn remote-port responses from disjoint phase episodes, using field memory only."""
    results = {}
    for topology in ("undivided", "isolated", "meaningful-helix", "rewired"):
        profile = replace(ResonantProfile(), beta=0.0, topology=topology)
        owner = FieldIntelligenceOwner(
            data_home / topology, initial_state=AtlasState(resonant_workspace=initial_workspace(profile))
        )
        try:
            for name in ("source_q", "source_p", "received"):
                owner.configure_variable(f"variable:{name}", VariableSpec(name, lower=-10, upper=10))
            owner.configure_chart(
                "chart:transfer",
                RelationChart.empty(
                    chart_id="phase-transfer", scope=("source_q", "source_p", "received"),
                    ridge=1e-8, prior_mass=1e-4, observation_norm_bound=32,
                ),
            )
            training = []
            for index, phase in enumerate(np.arange(12) * 2 * np.pi / 12):
                trajectory = _phase_trajectory(profile, float(phase))
                target = 100 * trajectory["target"]
                owner.admit_computation_episode(
                    operation_id=f"episode:{index}",
                    source=observation(f"phase:{index}", {"phase": float(phase), "received": target}),
                    workspace=trajectory["initial"],
                    feature_bindings={
                        "source_q": {"port": trajectory["source_port"], "component": "q_y", "scale": 1.0},
                        "source_p": {"port": trajectory["source_port"], "component": "p_y", "scale": 1.0},
                    },
                    outcomes={"received": target}, context={}, target_chart_ids=("phase-transfer",),
                )
                training.append(float(phase))
            memory = tuple(chart.as_dict() for chart in owner.state.charts)
            evidence_tick = owner.state.logical_tick
            held_out = []
            for index, phase in enumerate((0.37, 0.37 + np.pi, 1.12, 1.12 + np.pi)):
                trajectory = _phase_trajectory(profile, float(phase))
                observed = {"source_q": float(np.cos(phase)), "source_p": float(np.sin(phase))}
                limited = owner.think(f"limited:{index}", observed=observed, requested=("received",), ticks=1)
                started = perf_counter_ns()
                thought = owner.think(f"held-out:{index}", observed=observed, requested=("received",))
                elapsed = perf_counter_ns() - started
                require(thought["status"] == "supported", f"{topology} phase task remained unresolved")
                predicted = thought["branches"][0]["values"]["received"]
                target = 100 * trajectory["target"]
                require(abs(predicted - target) < 1e-5, f"{topology} phase prediction missed its held-out outcome")
                require(
                    abs(thought["branches"][0]["values"]["source_q"] - observed["source_q"]) < 1e-10
                    and abs(thought["branches"][0]["values"]["source_p"] - observed["source_p"]) < 1e-10,
                    "observed quadratures drifted during inference",
                )
                held_out.append({
                    "phase": float(phase), "target": target, "prediction": predicted,
                    "absolute_error": abs(predicted - target), "elapsed_ns": elapsed,
                    "limited_status": limited["status"],
                    "operator_applications": sum(
                        row.get("operator_applications", 0) for row in thought["resonance_receipt"]["resonance"]
                    ),
                })
            require(tuple(chart.as_dict() for chart in owner.state.charts) == memory, "phase inference changed memory")
            require(owner.state.logical_tick == evidence_tick, "phase holdout was admitted as learning")
            results[topology] = {
                "training_phases": training, "held_out": held_out,
                "workspace_bytes": owner.state.resonant_workspace.field.nbytes,
                "edge_count": len(profile.edges),
                "edge_strength_l1": sum(abs(row[2]) for row in profile.edges),
                "chart_memory_unchanged": True, "teacher_calls": 0,
            }
        finally:
            owner.close()
    meaningful = results["meaningful-helix"]["held_out"]
    phase_difference = abs(meaningful[0]["prediction"] - meaningful[1]["prediction"])
    require(phase_difference > 1e-3, "equal-amplitude opposite phases carried no learned distinction")
    require(max(abs(row["target"]) for row in results["isolated"]["held_out"]) < 1e-12, "isolated pools transferred across the cut")
    require(len({row["workspace_bytes"] for row in results.values()}) == 1, "phase controls used different workspace sizes")
    return {"controls": results, "opposite_phase_prediction_difference": phase_difference,
            "output_normalization": "100 times receiving q_y after 24 source-off ticks",
            "scope": "held-out phase-conditioned prediction of this controlled linear field, not natural-language understanding"}


def exercise_resolution() -> Mapping[str, Any]:
    """Measure integration error and nested projections of one fixed resolved body."""
    from scipy.linalg import expm

    profile = replace(ResonantProfile(), beta=0.0)
    seed = np.sin(np.arange(4 * profile.port_count) * 0.31) * 0.02
    duration = 2.56
    breath_rate = profile.heartbeat_frequency / 16
    effective_time = 0.75 * duration + 0.25 * np.sin(breath_rate * duration) / breath_rate
    reference = expm(_frozen_generator(profile) * effective_time) @ seed
    time_errors = []
    n = profile.port_count
    reference_phase = np.angle(reference[:n] + 1j * reference[2 * n:3 * n] / np.sqrt(profile.inertances[:n]))
    for step in (0.08, 0.04, 0.02):
        refined = replace(profile, time_step=step)
        evolved, receipt = advance_workspace(_seed(refined, seed), ticks=round(duration / step), source_enabled=False)
        actual = _vector(evolved)
        phase = np.angle(actual[:n] + 1j * actual[2 * n:3 * n] / np.sqrt(profile.inertances[:n]))
        time_errors.append({
            "time_step": step, "coordinate_error": float(np.linalg.norm(actual - reference)),
            "maximum_quadrature_phase_error": float(np.max(np.abs(np.angle(np.exp(1j * (phase - reference_phase)))))),
            "operator_applications": receipt["operator_applications"],
        })
    require(
        all(b["coordinate_error"] < a["coordinate_error"] for a, b in zip(time_errors, time_errors[1:])),
        "time refinement did not converge to the analytic breath-clock trajectory",
    )
    require(
        all(b["maximum_quadrature_phase_error"] < a["maximum_quadrature_phase_error"] for a, b in zip(time_errors, time_errors[1:])),
        "quadrature phase did not converge under time refinement",
    )

    fine_profile = replace(ResonantProfile(), ports_per_pool=16)
    fine_seed = np.sin(np.arange(4 * fine_profile.port_count) * 0.031) * 0.005
    fine = _seed(fine_profile, fine_seed)
    full, _ = advance_workspace(fine, ticks=16, source_enabled=False)
    reduced_rows = []
    for ports in (4, 8):
        rejected = False
        try:
            reduce_resolution(fine, ports_per_pool=ports, error_allowance=0.0)
        except ResonantNumericalError:
            rejected = True
        require(rejected, "lossy resolution reduction accepted a zero-error allowance")
        # A deliberately loose, explicit allowance exposes the conservative bound
        # and actual error; it is not a recommendation for a production accuracy target.
        reduced, certificate = reduce_resolution(fine, ports_per_pool=ports, error_allowance=1e8)
        basis = np.asarray(reduced.layout_transition["basis"])
        embedding = np.kron(np.eye(4), basis)
        evolved, receipt = advance_workspace(reduced, ticks=16, source_enabled=False)
        error = float(np.linalg.norm(_vector(full) - embedding @ _vector(evolved)))
        require(error <= certificate["nonlinear_trajectory_error_bound"], "trajectory escaped its reduction bound")
        reduced_rows.append({
            "ports_per_pool": ports, "field_bytes": reduced.field.nbytes,
            "actual_trajectory_error": error, "certificate": certificate,
            "zero_allowance_rejected": rejected, "operator_applications": receipt["operator_applications"],
        })
    require(
        reduced_rows[1]["actual_trajectory_error"] < reduced_rows[0]["actual_trajectory_error"],
        "finer nested resolution did not improve the controlled trajectory",
    )
    return {
        "phase_time_convergence": time_errors,
        "reference": "matrix exponential with analytically integrated rest breath mobility",
        "spatial_reference_ports_per_pool": 16, "spatial_reference_bytes": fine.field.nbytes,
        "nested_resolution": reduced_rows,
        "scope": "same fixed 16-port body projected onto 4 and 8 ports per pool; not continuum-limit evidence",
    }



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cassifi-resonant-scenario-") as directory:
        root = Path(directory)
        result = {
            "numerics": exercise_numerics(), "owner": exercise_owner(root / "owner"),
            "phase_learning": exercise_phase_learning(root / "phase"),
            "resolution": exercise_resolution(),
        }
    result["implementation_sha256"] = {
        path: hashlib.sha256(Path(__file__).with_name(path).read_bytes()).hexdigest()
        for path in (
            "cassi_resonant_field.py",
            "cassi_field_atlas.py",
            "cassi_field_cognition.py",
            "cassi_field_owner.py",
            "run_resonant_field_scenario.py",
        )
    }
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    print("ALL RESONANT PRODUCTION SCENARIOS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
